"""Headless PIE measurement of the seated pose of QUI01 at Seat_Table_1_5 in WORLD space (M2.3 Stage C2, stool placement). Saves nothing.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/SeatPoseMeasure.py -Log <abs log>
  (env ARR_ONLY="1,3" runs only those arrivals)

The real StateTree and the real regenerated activity data are used; only the schedule hour is jumped (as in SeatArrivalMeasure.py) so QUI01 arrives from
different places. After each arrival has been seated for a few seconds the capsule, the floor height, the yaw and the world position of the bones that decide
where a stool must be (pelvis, spine, thighs, calves, feet, hands) are logged, plus - when the physics asset can be queried - a map of the lowest point of
the body above each cell under the pelvis (the underside of the buttocks and thighs). Report: Saved/SeatPoseMeasure.txt
"""
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SLOMO = float(os.environ.get("ACT_SLOMO", "3"))
SEAT = "Seat_Table_1_5"
ARRIVALS = [("1 breakfast from the cell", 6.0, "CellAssign_Cell_N5", 7.0), ("2 lunch from Rec_Table_B", 10.0, "Rec_Table_B", 12.0), ("3 lunch from the TV", 10.0, "Rec_TV", 12.0)]
ONLY = [int(x) for x in os.environ.get("ARR_ONLY", "").split(",") if x.strip()]
BONES = ["pelvis", "spine_01", "spine_02", "spine_03", "neck_01", "head", "thigh_l", "thigh_r", "calf_l", "calf_r", "foot_l", "foot_r", "ball_l", "ball_r",
         "upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r", "hand_l", "hand_r"]
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "until": None, "timed_out": False, "last_t": None, "out": []}


def log(m):
    S["out"].append(m)
    unreal.log("[POSEMEAS] " + m)


def finish(code):
    unreal.unregister_slate_post_tick_callback(S["h"])
    with open(unreal.Paths.project_saved_dir() + "SeatPoseMeasure.txt", "w") as fh:
        fh.write("\n".join(S["out"]))
    level_sub.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


def g(c, k):
    return c.get_editor_property(k)


def d2(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def mloc(gw, mid):
    return unreal.GameplayStatics.get_all_actors_with_tag(gw, "MarkerId:" + mid)[0].get_actor_location()


def set_hour(mgr, sc, hour):
    serial0 = g(sc, "replan_serial")
    mgr.set_time_of_day_hours(hour)
    mgr.set_editor_property("paused", False)
    yield ("until", lambda: g(sc, "replan_serial") > serial0, 80.0)
    mgr.set_editor_property("paused", True)


def underside_map(mesh, px, py, floor_z, probe):
    """Lowest z (relative to the floor) at which the body is found above each (x, y) cell around the pelvis, via the physics asset. None where nothing is found."""
    rows = []
    for dy in range(-20, 41, 5):
        row = []
        for dx in range(-20, 21, 5):
            low = None
            for zi in range(30, 70):
                z = floor_z + zi
                ok = probe(unreal.Vector(px + dx, py + dy, z))
                if ok is not None and ok <= 0.3:
                    low = zi
                    break
            row.append(low)
        rows.append((dy, row))
    return rows


def run(gw):
    npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
    mgr = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")[0]
    npc = npcs["QUI01"]
    npc.get_component_by_class(unreal.SkeletalMeshComponent).set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    yield ("ticks", 5)
    sc, ac = npc.get_component_by_class(unreal.PrisonScheduleComponent), npc.get_component_by_class(unreal.PrisonActivityComponent)
    mesh = npc.get_component_by_class(unreal.SkeletalMeshComponent)
    mk = mloc(gw, SEAT)
    mgr.set_editor_property("time_scale", 30.0)
    mgr.set_editor_property("paused", False)
    unreal.SystemLibrary.execute_console_command(gw, "slomo %g" % SLOMO)
    log("marker %s (%.1f, %.1f, %.1f)" % (SEAT, mk.x, mk.y, mk.z))
    # physics asset probe
    state = {"first": True}

    def probe(v):
        try:
            r = mesh.get_closest_point_on_physics_asset(v, "None")
        except Exception as ex:
            if state["first"]:
                log("physics asset query raised: %s" % ex)
                state["first"] = False
            return None
        if state["first"]:
            log("physics asset query raw result for the first point: %s" % (r,))
            state["first"] = False
        try:
            return float(r[-1]) if r[0] else None
        except Exception:
            return None

    for idx, (label, setup_h, origin, meal_h) in enumerate(ARRIVALS, 1):
        if ONLY and idx not in ONLY:
            continue
        om = mloc(gw, origin)
        yield from set_hour(mgr, sc, setup_h)
        yield ("until", lambda: d2(npc.get_actor_location().x, npc.get_actor_location().y, om.x, om.y) < 220.0 and npc.get_velocity().length() < 3.0 and g(ac, "state").name in ("IDLE", "PERFORMING"), 1500.0)
        yield ("secs", 2.0)
        st0 = g(ac, "start_count")
        yield from set_hour(mgr, sc, meal_h)
        yield ("until", lambda: g(ac, "state").name == "PERFORMING" and str(g(ac, "active_marker_id")) == SEAT and g(ac, "start_count") > st0, 1500.0)
        if S["timed_out"]:
            log("%s: no arrival" % label)
            continue
        yield ("secs", 3.7)  # two loops in
        loc = npc.get_actor_location()
        floor_z = mesh.get_world_location().z
        yaw = npc.get_actor_rotation().yaw
        log("-- %s: capsule (%.3f, %.3f, %.3f), mesh origin (floor) z %.3f, capsule yaw %.2f, montage %s, slot weight %.2f" % (label, loc.x, loc.y, loc.z, floor_z, yaw, g(ac, "montage_playing"), g(ac, "slot_node_weight")))
        for b in BONES:
            try:
                p = mesh.get_socket_location(b)
                log("   %-11s world (%8.2f, %8.2f, %8.2f) | rel capsule: dx %+7.2f dy %+7.2f height above floor %7.2f" % (b, p.x, p.y, p.z, p.x - loc.x, p.y - loc.y, p.z - floor_z))
            except Exception as ex:
                log("   %-11s unavailable (%s)" % (b, ex))
        pel = mesh.get_socket_location("pelvis")
        rows = underside_map(mesh, pel.x, pel.y, floor_z, probe)
        found = [v for _, r in rows for v in r if v is not None]
        if found:
            log("   body underside map above the floor in cm (rows: y offset from the pelvis, + is behind the NPC, - towards the table; columns: x offset -20..+20 step 5):")
            for dy, r in rows:
                log("     dy %+3d : %s" % (dy, " ".join(("%3d" % v) if v is not None else "  -" for v in r)))
            log("   lowest body point found above the floor: %d cm" % min(found))
        else:
            log("   the physics asset returned no body points (no physics state on the mesh?)")
    finish(0)


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 500000:
            log("FAILED: timeout")
            finish(2)
            return
        if not S["pie"]:
            return
        gw = ues.get_game_world()
        if gw is None:
            return
        S["post"] += 1
        if S["post"] < 80:
            return
        now = unreal.GameplayStatics.get_time_seconds(gw)
        if S["gen"] is None:
            S["gen"] = run(gw)
        S["last_t"] = now
        if S["wait"] > 0:
            S["wait"] -= 1
            return
        if S["until"] is not None:
            cond, deadline = S["until"]
            if cond():
                S["until"], S["timed_out"] = None, False
            elif now >= deadline:
                S["until"], S["timed_out"] = None, True
            else:
                return
        try:
            kind, *rest = next(S["gen"])
        except StopIteration:
            return
        if kind == "ticks":
            S["wait"] = int(rest[0])
        elif kind == "secs":
            end = now + rest[0]
            S["until"] = ((lambda e=end: unreal.GameplayStatics.get_time_seconds(gw) >= e), end + 1.0)
        elif kind == "until":
            S["until"] = (rest[0], now + rest[1])
    except Exception as ex:
        import traceback
        log("EXCEPTION %s\n%s" % (ex, traceback.format_exc()))
        finish(9)


S["h"] = unreal.register_slate_post_tick_callback(tick)
