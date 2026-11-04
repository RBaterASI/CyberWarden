"""Headless PIE measurement of real seat arrivals of QUI01 at Seat_Table_1_5 with the final approach (M2.3 Stage C2). Saves nothing in the project.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/SeatArrivalMeasure.py -Log <abs log>
  (env ACT_SLOMO overrides the time dilation, default 3; env ARR_ONLY="1,3" runs only those arrivals)

Nothing is driven and nothing is overridden: the real ST_NPCRoutine and the real regenerated activity data asset are used. Only the schedule hour is jumped,
so QUI01 reaches the seat from different places: it is first let settle at an origin of its own schedule (cell, the two recreation spots, the hall), then the
hour changes to a meal and QUI01 walks to the seat by itself (Move To, then the final approach, then the seated activity).
For every arrival: the origin, where the final approach started (and the heading of the Move To walk-in), the capsule-to-marker distance when the activity
began and after sitting (3 decimals), the approach duration, travelled distance and result as the component reports them, top speed and largest step during
the approach (no teleport), drift after the confirmation (no slide), the yaw error, whether the seated animation began, and the seated pelvis relative to the
table edge (Prop_Caf_Table_1: y -150..-50). The first failed arrival stops the run. Report: Saved/SeatArrivalMeasure.txt
"""
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SLOMO = float(os.environ.get("ACT_SLOMO", "3"))
SEAT = "Seat_Table_1_5"
TABLE_EDGE_Y = -50.0
LIMIT_CM = 7.0
GOAL_ERR_LIMIT_CM = 1.0  # actual stopping error: distance of the stopping point to the projected navigable goal
SPREAD_LIMIT_CM = 1.0  # the six final capsule positions must agree to within this (7 cm is a tolerance, not permission for scatter)
# (label, hour that makes QUI01 go to the origin, origin marker of its own schedule, meal hour)
ARRIVALS = [
    ("1 breakfast from the cell", 6.0, "CellAssign_Cell_N5", 7.0),
    ("2 lunch from Rec_Table_B", 10.0, "Rec_Table_B", 12.0),
    ("3 lunch from the TV", 10.0, "Rec_TV", 12.0),
    ("4 dinner from Rec_Table_B", 15.0, "Rec_Table_B", 18.0),
    ("5 dinner from the TV", 15.0, "Rec_TV", 18.0),
    ("6 breakfast from the hall", 20.0, "Conv_Hall_A", 7.0),
]
ONLY = [int(x) for x in os.environ.get("ARR_ONLY", "").split(",") if x.strip()]
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "until": None, "timed_out": False, "last_t": None, "samples": [], "rows": [], "out": [], "stop": False}


def log(m):
    S["out"].append(m)
    unreal.log("[SEATMEAS] " + m)


def finish(code):
    unreal.unregister_slate_post_tick_callback(S["h"])
    with open(unreal.Paths.project_saved_dir() + "SeatArrivalMeasure.txt", "w") as fh:
        fh.write("\n".join(S["out"]))
    level_sub.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


def g(c, k):
    return c.get_editor_property(k)


def d2(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def ndelta(a, b):
    d = (b - a) % 360.0
    return d - 360.0 if d > 180.0 else d


def hd(ax, ay, bx, by):
    return math.degrees(math.atan2(by - ay, bx - ax))


def mloc(gw, mid):
    return unreal.GameplayStatics.get_all_actors_with_tag(gw, "MarkerId:" + mid)[0].get_actor_location()


def sample(now):
    npc, ac, mesh = S["npc"], S["ac"], S["mesh"]
    loc = npc.get_actor_location()
    pel = mesh.get_socket_location("pelvis")
    anim = mesh.get_anim_instance()
    S["samples"].append(dict(t=now, x=loc.x, y=loc.y, yaw=npc.get_actor_rotation().yaw, st=g(ac, "state").name, mm=S["cmc"].get_editor_property("movement_mode").name,
                             w=g(ac, "slot_node_weight"), mont=anim.get_current_active_montage() is not None, pz=pel.z - mesh.get_world_location().z, sc=g(ac, "start_count"),
                             ms=str(S["ctrl"].get_move_status()), v=npc.get_velocity().length(), mk=str(g(ac, "active_marker_id"))))


def set_hour(mgr, sc, hour):
    serial0 = g(sc, "replan_serial")
    mgr.set_time_of_day_hours(hour)
    mgr.set_editor_property("paused", False)
    yield ("until", lambda: g(sc, "replan_serial") > serial0, 80.0)
    mgr.set_editor_property("paused", True)


def analyse(label, origin, mk, gw):
    """Builds the row of one arrival from the samples recorded since the hour jump."""
    ac, npc, mesh = S["ac"], S["npc"], S["mesh"]
    pg = S["pg"]  # the projected navigable goal: the reachable position closest to the marker
    smp = S["samples"]
    appr_idx = [i for i, s in enumerate(smp) if s["st"] == "APPROACHING"]
    row = dict(label=label, origin=origin, ok=False)
    row["result"], row["fail_reason"] = g(ac, "last_approach_result"), str(g(ac, "last_failure_reason"))
    if not appr_idx:
        row["note"] = "no approach was started (state sequence %s)" % sorted(set(s["st"] for s in smp))
        return row
    i0, i1 = appr_idx[0], appr_idx[-1]
    s0 = smp[i0]
    # Move To walk-in heading: from the sample about 100 cm of path before the approach started
    back, acc, j = i0, 0.0, i0
    while j > 0 and acc < 100.0:
        acc += d2(smp[j]["x"], smp[j]["y"], smp[j - 1]["x"], smp[j - 1]["y"])
        j -= 1
    row["walk_in_heading"] = hd(smp[j]["x"], smp[j]["y"], s0["x"], s0["y"]) if acc > 30.0 else float("nan")
    row["start"] = (s0["x"], s0["y"])
    row["start_d"] = d2(s0["x"], s0["y"], mk.x, mk.y)
    row["appr_heading"] = hd(s0["x"], s0["y"], mk.x, mk.y)
    after = [s for s in smp[i1 + 1:] if s["st"] in ("ALIGNING", "ENTERING", "PERFORMING")]
    row["began"] = after[0] if after else None
    if row["began"] is None:
        row["note"] = "the activity never began after the approach (%s)" % g(ac, "last_approach_result")
        loc_f = npc.get_actor_location()  # where the NPC stands after the failed approach: lets the failure be analysed instead of only reported
        row["final_xy"] = (loc_f.x, loc_f.y)
        row["final_d"] = d2(loc_f.x, loc_f.y, mk.x, mk.y)
        row["final_goal_d"] = d2(loc_f.x, loc_f.y, pg.x, pg.y)
        row["failed_start"] = (s0["x"], s0["y"], row["start_d"], row["appr_heading"], row["walk_in_heading"])
        row["failed_diag"] = (g(ac, "last_approach_start_cm"), g(ac, "last_approach_end_cm"), g(ac, "last_approach_seconds"), g(ac, "last_approach_travel_cm"))
        return row
    b = row["began"]
    row["begin_d"] = d2(b["x"], b["y"], mk.x, mk.y)
    row["begin_dx"], row["begin_dy"] = b["x"] - mk.x, b["y"] - mk.y
    appr = smp[i0:i1 + 2]
    steps = [(d2(p["x"], p["y"], q["x"], q["y"]), q["t"] - p["t"]) for p, q in zip(appr, appr[1:]) if q["t"] > p["t"]]
    row["top_speed"] = max([s / dt for s, dt in steps] + [0.0])
    row["max_step"] = max([s for s, _ in steps] + [0.0])
    row["moving_samples"] = sum("MOVING" in s["ms"] for s in smp[i0:i1 + 1])
    row["appr_samples"] = i1 - i0 + 1
    row["held_during_approach"] = sum(1 for s in smp[i0:i1 + 1] if s["mm"] == "MOVE_NONE")
    row["start_count_during_approach"] = max(s["sc"] for s in smp[i0:i1 + 1]) - smp[max(i0 - 1, 0)]["sc"]
    row["montage_during_approach"] = sum(1 for s in smp[i0:i1 + 1] if s["mont"])
    # final state after sitting
    fin = smp[-1]
    loc = npc.get_actor_location()
    pel = mesh.get_socket_location("pelvis")
    row["final_d"] = d2(loc.x, loc.y, mk.x, mk.y)
    row["final_xy"] = (loc.x, loc.y)
    dg = [d2(s["x"], s["y"], pg.x, pg.y) for s in smp[i0:i1 + 2]]  # distance to the projected goal over the approach and the first sample after it
    row["begin_goal_d"] = d2(b["x"], b["y"], pg.x, pg.y)
    row["final_goal_d"] = d2(loc.x, loc.y, pg.x, pg.y)
    row["closest_goal"] = min(dg)
    row["overshoot"] = max(0.0, dg[-1] - min(dg))
    row["grew"] = sum(1 for a_, b_ in zip(dg, dg[1:]) if b_ > a_ + 0.25)  # oscillation: the distance to the goal grew again during the approach
    row["drift"] = d2(loc.x, loc.y, b["x"], b["y"])
    row["yaw"] = npc.get_actor_rotation().yaw
    row["yaw_err"] = abs(ndelta(row["yaw"], -90.0))
    row["state"], row["montage"], row["weight"], row["pz"] = g(ac, "state").name, g(ac, "montage_playing"), g(ac, "slot_node_weight"), fin["pz"]
    row["pel_dx"], row["pel_dy"], row["edge"] = pel.x - mk.x, pel.y - mk.y, pel.y - TABLE_EDGE_Y
    row["disp"] = g(ac, "max_displacement_cm")
    row["diag"] = dict(start_cm=g(ac, "last_approach_start_cm"), end_cm=g(ac, "last_approach_end_cm"), secs=g(ac, "last_approach_seconds"), travel=g(ac, "last_approach_travel_cm"),
                       starts=g(ac, "approach_start_count"), success=g(ac, "approach_success_count"), fail=g(ac, "approach_fail_count"), cancel=g(ac, "approach_cancel_count"),
                       refusals=g(ac, "approach_lockout_refusals"))
    row["ok"] = (row["begin_d"] <= LIMIT_CM and row["final_d"] <= LIMIT_CM and row["state"] == "PERFORMING" and row["montage"] and row["weight"] >= 0.95 and row["pz"] < 75.0 and
                 g(ac, "approach_fail_count") == 0 and row["drift"] < 0.5 and row["final_goal_d"] <= GOAL_ERR_LIMIT_CM and row["grew"] == 0 and row["overshoot"] <= 0.5 and
                 g(ac, "last_approach_seconds") < 1.5 and row["held_during_approach"] == 0 and row["montage_during_approach"] == 0)
    return row


def run(gw):
    npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
    mgr = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")[0]
    npc = npcs["QUI01"]
    npc.get_component_by_class(unreal.SkeletalMeshComponent).set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    yield ("ticks", 5)  # headless meshes are not rendered: without this the bones (pelvis, feet) keep the standing pose. Editing the property re-runs construction,
    sc, ac = npc.get_component_by_class(unreal.PrisonScheduleComponent), npc.get_component_by_class(unreal.PrisonActivityComponent)  # so fetch the components afterwards
    mesh = npc.get_component_by_class(unreal.SkeletalMeshComponent)
    S.update(npc=npc, ac=ac, mesh=mesh, ctrl=npc.get_controller(), cmc=npc.get_component_by_class(unreal.CharacterMovementComponent))
    mk = mloc(gw, SEAT)
    max_walk = float(S["cmc"].get_editor_property("max_walk_speed"))
    log("marker %s at (%.3f, %.3f, %.3f); table edge y=%.0f; max walk speed %.0f cm/s; activity point present: %s" % (SEAT, mk.x, mk.y, mk.z, TABLE_EDGE_Y, max_walk, ac.has_interaction_point(SEAT)))
    for extent in ((0, 0, 0), (50, 50, 250)):
        names = [n for n in dir(unreal.NavigationSystemV1) if "project" in n.lower()]
        try:
            fn = getattr(unreal.NavigationSystemV1, "project_point_to_navigation", None) or getattr(unreal.NavigationSystemV1, "k2_project_point_to_navigation", None)
            r = fn(gw, mk, None, None, unreal.Vector(*extent))
            log("navmesh projection of the marker with extent %s: %s" % (extent, r))
        except Exception as ex:
            log("navmesh projection with extent %s unavailable: %s (projection-like names: %s)" % (extent, ex, names))
    S["pg"] = unreal.NavigationSystemV1.project_point_to_navigation(gw, mk, None, None, unreal.Vector(50, 50, 250))
    log("requested goal = marker (%.3f, %.3f); projected navigable goal (%.3f, %.3f): the marker is %.3f cm from the nearest reachable position" % (mk.x, mk.y, S["pg"].x, S["pg"].y, d2(mk.x, mk.y, S["pg"].x, S["pg"].y)))
    pt_fa = None
    for p_ in mgr.get_editor_property("activity_data").get_editor_property("points"):
        if str(p_.get_editor_property("marker_id")) == SEAT:
            pt_fa = p_
    if pt_fa is not None:
        log("final-approach settings read from the data asset: accept %.1f cm, tolerance %.1f cm, max %.0f cm, timeout %.1f s" % (
            pt_fa.get_editor_property("final_approach_accept_cm"), pt_fa.get_editor_property("final_approach_tolerance_cm"),
            pt_fa.get_editor_property("final_approach_max_distance_cm"), pt_fa.get_editor_property("final_approach_timeout_seconds")))
    data = g(S["ac"], "activity_data_override")
    log("component data override: %s (None = the sector's regenerated asset is used)" % data)
    nf0 = int(npc.get_editor_property("NavFailureCount"))
    others = {k: v for k, v in npcs.items() if k != "QUI01"}
    others0 = {k: int(v.get_editor_property("NavFailureCount")) for k, v in others.items()}
    mgr.set_editor_property("time_scale", 30.0)
    mgr.set_editor_property("paused", False)
    unreal.SystemLibrary.execute_console_command(gw, "slomo %g" % SLOMO)
    for idx, (label, setup_h, origin, meal_h) in enumerate(ARRIVALS, 1):
        if ONLY and idx not in ONLY:
            continue
        om = mloc(gw, origin)
        yield from set_hour(mgr, sc, setup_h)
        yield ("until", lambda: d2(npc.get_actor_location().x, npc.get_actor_location().y, om.x, om.y) < 220.0 and npc.get_velocity().length() < 3.0 and g(ac, "state").name in ("IDLE", "PERFORMING"), 1500.0)
        if S["timed_out"]:
            log("%s: QUI01 did not settle at %s within the timeout" % (label, origin))
            S["rows"].append(dict(label=label, origin=origin, ok=False, note="did not reach the origin"))
            S["stop"] = True
            break
        yield ("secs", 2.0)
        o = npc.get_actor_location()
        log("-- %s: settled at %s, capsule (%.0f, %.0f), %.0f cm from it" % (label, origin, o.x, o.y, d2(o.x, o.y, om.x, om.y)))
        st0, ap0, f0, c0 = g(ac, "start_count"), g(ac, "approach_start_count"), g(ac, "approach_fail_count"), g(ac, "approach_cancel_count")
        S["samples"] = []
        yield from set_hour(mgr, sc, meal_h)  # leaves the clock paused: the meal period stays fixed
        yield ("until", lambda: (g(ac, "state").name == "PERFORMING" and str(g(ac, "active_marker_id")) == SEAT and g(ac, "start_count") > st0) or g(ac, "approach_fail_count") > f0, 1500.0)
        if S["timed_out"]:
            log("%s: NO SEAT ARRIVAL within the timeout; activity %s, last failure: %s" % (label, g(ac, "state").name, g(ac, "last_failure_reason")))
            S["rows"].append(dict(label=label, origin=origin, ok=False, note="no arrival"))
            S["stop"] = True
            break
        yield ("secs", 2.5)
        row = analyse(label, origin, mk, gw)
        row["origin_xy"] = (o.x, o.y)
        S["rows"].append(row)
        report(row)
        if not row["ok"]:
            log("STOP: arrival %s did not meet the criteria (accuracy limit %.1f cm); no further arrivals are run" % (label, LIMIT_CM))
            S["stop"] = True
            break
    rows = S["rows"]
    done = [r for r in rows if r.get("began")]
    log("== %d arrivals recorded, %d within %.1f cm and fully seated ==" % (len(rows), sum(1 for r in rows if r["ok"]), LIMIT_CM))
    if done:
        for k, label in (("begin_d", "capsule distance when the activity began"), ("final_d", "capsule distance after sitting"), ("final_goal_d", "stopping error to the projected goal"), ("begin_dx", "dx from the marker"), ("begin_dy", "dy from the marker"),
                         ("edge", "pelvis to table edge"), ("pz", "pelvis height seated")):
            v = [r[k] for r in done if k in r]
            if v:
                log("  %-42s mean %8.3f  min %8.3f  max %8.3f  spread %7.3f" % (label, sum(v) / len(v), min(v), max(v), max(v) - min(v)))
    xy = [r["final_xy"] for r in done if "final_xy" in r]
    if len(xy) >= 2:
        sx, sy = max(p[0] for p in xy) - min(p[0] for p in xy), max(p[1] for p in xy) - min(p[1] for p in xy)
        pair = max(d2(a[0], a[1], b[0], b[1]) for a in xy for b in xy)
        log("final capsule coordinates over %d arrivals: x %.3f..%.3f (spread %.3f), y %.3f..%.3f (spread %.3f), largest pairwise distance %.3f cm -> %s (limit %.1f cm)" % (
            len(xy), min(p[0] for p in xy), max(p[0] for p in xy), sx, min(p[1] for p in xy), max(p[1] for p in xy), sy, pair, "REPEATABLE" if pair <= SPREAD_LIMIT_CM else "NOT REPEATABLE", SPREAD_LIMIT_CM))
    log("QUI01 navigation failures during the run: %d" % (int(npc.get_editor_property("NavFailureCount")) - nf0))
    nfo = {k: int(v.get_editor_property("NavFailureCount")) - others0[k] for k, v in others.items()}
    log("other prisoners' navigation failures during the run: %s" % nfo)
    log("RESULT %s" % ("ALL ARRIVALS PASS" if rows and all(r["ok"] for r in rows) and not S["stop"] else "STOPPED / FAILED"))
    finish(0)


def report(r):
    if "begin_d" not in r:
        log("ARRIVAL %s: %s (result '%s', %s)" % (r["label"], r.get("note"), r.get("result"), r.get("fail_reason")))
        if "final_xy" in r:
            fs, fd = r.get("failed_start"), r.get("failed_diag")
            log("   after the failed approach QUI01 stands at (%.3f, %.3f) = %+.3f, %+.3f from the marker (%.3f cm); %.3f cm from the projected navigable goal" % (
                r["final_xy"][0], r["final_xy"][1], r["final_xy"][0] - 6150.0, r["final_xy"][1] + 5.0, r["final_d"], r["final_goal_d"]))
            if fs:
                log("   the approach started at (%.1f, %.1f), %.2f cm out, heading %.0f deg to the marker, Move To walk-in heading %.0f deg; component: start %.2f cm, end %.3f cm, %.2f s, travelled %.2f cm" % (
                    fs[0], fs[1], fs[2], fs[3], fs[4], fd[0], fd[1], fd[2], fd[3]))
        return
    d = r["diag"]
    log("ARRIVAL %s: %s" % (r["label"], "OK" if r["ok"] else "FAILED"))
    log("   origin %s (%.0f, %.0f); Move To walk-in heading %.0f deg; the final approach started at (%.1f, %.1f), %.2f cm from the marker, heading %.0f deg to it" % (
        r["origin"], r["origin_xy"][0], r["origin_xy"][1], r["walk_in_heading"], r["start"][0], r["start"][1], r["start_d"], r["appr_heading"]))
    log("   navigation result '%s': %.2f s, travelled %.2f cm, end %.3f cm (component); %d of %d approach samples reported MOVING; samples with movement held %d, with a montage %d, activities started during it %d" % (
        r["result"], d["secs"], d["travel"], d["end_cm"], r["moving_samples"], r["appr_samples"], r["held_during_approach"], r["montage_during_approach"], r["start_count_during_approach"]))
    log("   confirmation '%s' (component: end %.3f cm, limit %.1f); capsule when the activity began: %+.3f, %+.3f from the marker = %.3f cm; after sitting %.3f cm (drift since the confirmation %.3f cm, max displacement %.3f cm)" % (
        r["result"], d["end_cm"], LIMIT_CM, r["begin_dx"], r["begin_dy"], r["begin_d"], r["final_d"], r["drift"], r["disp"]))
    log("   final capsule coordinates (%.3f, %.3f); distance to the original marker %.3f cm; distance to the projected navigable goal (actual stopping error) %.3f cm (when the activity began %.3f cm)" % (
        r["final_xy"][0], r["final_xy"][1], r["final_d"], r["final_goal_d"], r["begin_goal_d"]))
    log("   closest approach to the goal %.3f cm, overshoot %.3f cm, distance grew again %d time(s); approach duration %.2f s" % (r["closest_goal"], r["overshoot"], r["grew"], d["secs"]))
    log("   approach top speed %.0f cm/s (walk speed 150), largest step %.1f cm; yaw %.2f (error %.2f deg)" % (r["top_speed"], r["max_step"], r["yaw"], r["yaw_err"]))
    log("   seated animation: state %s, montage %s, slot weight %.2f, pelvis height %.1f cm; pelvis %+.1f, %+.1f from the marker = %.1f cm from the table edge" % (
        r["state"], r["montage"], r["weight"], r["pz"], r["pel_dx"], r["pel_dy"], r["edge"]))
    log("   counters: approaches %d, success %d, fail %d, cancel %d, lockout refusals %d" % (d["starts"], d["success"], d["fail"], d["cancel"], d["refusals"]))


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 600000:
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
        if "npc" in S and "ac" in S and S["ac"] is not None:
            sample(now)
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
