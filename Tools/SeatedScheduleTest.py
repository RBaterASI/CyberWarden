"""Headless PIE end-to-end test of a seated activity on the REAL StateTree (M2.3 Stage C1). Saves nothing.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/SeatedScheduleTest.py -Log <abs log>

Nothing is driven: QUI01 runs the real ST_NPCRoutine. The sector's regenerated activity data (Stage C2) already holds the SeatedIdle point on the existing
marker Seat_Table_1_5 (with its final approach) and is reused as it is; if the data has no seat point (Stage C1 data) the original behaviour applies: only in
memory (the PIE copy) the manager's data is replaced by a copy with an ordinary SeatedIdle point. QUI01's lunch is reduced (in memory) to the single stop
Seat_Table_1_5 with short idle cycles. Then, following only its schedule, QUI01 walks to the seat and sits;
the single-stop destination re-plans at the end of every idle cycle and must never stand the NPC up or restart the sit; a schedule change
(lunch -> recreation) must stand it up at once (the release grace is skipped because the NPC is leaving), restore movement only after the stand-up
and send it on to the TV (WatchTV starts again). Per-tick invariants: movement held while busy, capsule never moved, slot never empty.
"""
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SLOMO = float(os.environ.get("ACT_SLOMO", "4"))
SEAT = "Seat_Table_1_5"
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "until": None, "res": [], "fail": [], "samples": [], "last_t": None, "timed_out": False, "events": []}


def log(m):
    unreal.log("[SEATSCHED] " + m)


def check(name, ok, detail=""):
    S["res"].append(bool(ok))
    if not ok:
        S["fail"].append(name)
    log("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  (%s)" % detail))


def finish(code):
    unreal.unregister_slate_post_tick_callback(S["h"])
    log("RESULT %s (%d/%d checks)" % ("PASS" if not S["fail"] and code == 0 else "FAIL", sum(S["res"]), len(S["res"])))
    level_sub.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


def d2(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def ndelta(a, b):
    d = (b - a) % 360.0
    return d - 360.0 if d > 180.0 else d


def g(c, k):
    return c.get_editor_property(k)


def sample(now):
    npc, ac, mesh = S["npc"], S["ac"], S["mesh"]
    loc = npc.get_actor_location()
    st = g(ac, "state").name
    if st != S.get("last_st"):
        S["events"].append((round(now, 2), st, str(g(ac, "active_marker_id"))))
        log("t=%7.1f activity %s -> %s marker=%s starts=%d completes=%d" % (now, S.get("last_st"), st, g(ac, "active_marker_id"), g(ac, "start_count"), g(ac, "complete_count")))
        S["last_st"] = st
    S["samples"].append(dict(t=now, x=loc.x, y=loc.y, z=loc.z, st=st, mm=S["cmc"].get_editor_property("movement_mode").name, w=g(ac, "slot_node_weight"),
                             mont=mesh.get_anim_instance().get_current_active_montage() is not None, pz=mesh.get_socket_location("pelvis").z - mesh.get_world_location().z))


def run(gw):
    npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
    mgr = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")[0]
    npc = npcs["QUI01"]
    S.update(gw=gw, npc=npc, mgr=mgr, sc=npc.get_component_by_class(unreal.PrisonScheduleComponent), ac=npc.get_component_by_class(unreal.PrisonActivityComponent),
             cmc=npc.get_component_by_class(unreal.CharacterMovementComponent), mesh=npc.get_component_by_class(unreal.SkeletalMeshComponent))
    S["mesh"].set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    yield ("ticks", 5)
    S.update(sc=npc.get_component_by_class(unreal.PrisonScheduleComponent), ac=npc.get_component_by_class(unreal.PrisonActivityComponent),
             cmc=npc.get_component_by_class(unreal.CharacterMovementComponent), mesh=npc.get_component_by_class(unreal.SkeletalMeshComponent))
    others = {k: v for k, v in npcs.items() if k != "QUI01"}
    others0 = {k: int(v.get_editor_property("NavFailureCount")) for k, v in others.items()}
    nf0 = int(npc.get_editor_property("NavFailureCount"))

    # ---- in-memory data: the sector's activities + a SeatedIdle point on Seat_Table_1_5 (not saved) -----------------------------------------------
    sector = mgr.get_editor_property("activity_data")
    have_seat = any(str(p.get_editor_property("marker_id")) == SEAT for p in sector.get_editor_property("points"))
    if have_seat:
        # Stage C2: the regenerated data asset already holds the seat point (with its final approach). It is reused as it is, not duplicated and not replaced.
        check("the sector's regenerated data already holds the %s point and validates (reused, nothing replaced)" % SEAT, len(list(sector.validate_data())) == 0, str(list(sector.validate_data())))
    else:
        # Stage C1 data (no seat point yet): the original behaviour, a copy with an ordinary SeatedIdle point (tolerance 150), in memory only.
        data = unreal.new_object(unreal.PrisonActivityData)
        data.set_editor_property("activities", list(sector.get_editor_property("activities")))
        seat_pt = unreal.PrisonInteractionPoint(marker_id=SEAT, activity_id="SeatedIdle", facing_mode=unreal.PrisonFacingMode.YAW, facing_yaw_degrees=-90.0, arrival_tolerance_cm=150.0, capacity=1)
        data.set_editor_property("points", list(sector.get_editor_property("points")) + [seat_pt])
        check("test activity data validates", len(list(data.validate_data())) == 0, str(list(data.validate_data())))
        mgr.set_editor_property("activity_data", data)
        mgr = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")[0]
        S["mgr"] = mgr
    check("the schedule manager serves data with the seat point and Rec_TV", mgr.get_editor_property("activity_data") is not None and S["ac"].has_interaction_point(SEAT) and S["ac"].has_interaction_point("Rec_TV"))
    sd = mgr.get_editor_property("schedule_data")  # QUI01 lunch: single stop at the seat with short idle cycles (in memory only)
    rows = sd.get_editor_property("npcs")
    for i, row in enumerate(rows):
        if str(row.get_editor_property("npc_id")) == "QUI01":
            periods = list(row.get_editor_property("periods"))
            for j, ap in enumerate(periods):
                if str(ap.get_editor_property("period_id")) == "lunch":
                    ap.set_editor_property("stop_marker_ids", [SEAT])
                    ap.set_editor_property("idle_min", 10.0)
                    ap.set_editor_property("idle_max", 12.0)
                    periods[j] = ap
            row.set_editor_property("periods", periods)
            rows[i] = row
    sd.set_editor_property("npcs", rows)

    ac, sc = S["ac"], S["sc"]
    mgr.set_editor_property("time_scale", 30.0)
    mgr.set_editor_property("paused", False)
    serial0 = g(sc, "replan_serial")
    mgr.set_time_of_day_hours(12.0)  # lunch
    unreal.SystemLibrary.execute_console_command(gw, "slomo %g" % SLOMO)
    yield ("until", lambda: g(sc, "replan_serial") > serial0, 60.0)
    mgr.set_editor_property("paused", True)  # keep the period fixed once QUI01 has adopted it
    check("QUI01 adopted the lunch period", not S["timed_out"])
    yield ("until", lambda: g(ac, "state").name == "PERFORMING" and str(g(ac, "active_marker_id")) == SEAT, 400.0)
    check("QUI01 followed its schedule to %s and sat down (real StateTree)" % SEAT, not S["timed_out"],
          "%s %s %s" % (g(ac, "state").name, g(ac, "last_failure_reason"), S["mgr"].get_clock_string()))
    if S["timed_out"]:
        finish(5)
        return
    loc = npc.get_actor_location()
    seat_loc = unreal.GameplayStatics.get_all_actors_with_tag(gw, "MarkerId:" + SEAT)[0].get_actor_location()
    log("seated %.0f cm from the marker, yaw %.1f" % (d2(loc.x, loc.y, seat_loc.x, seat_loc.y), npc.get_actor_rotation().yaw))
    check("one start, one enter-to-loop hand-off for this arrival", g(ac, "start_count") == 1 and g(ac, "handoff_count") == 1, "%s %s" % (g(ac, "start_count"), g(ac, "handoff_count")))
    check("facing the table side: yaw error %.2f deg" % abs(ndelta(npc.get_actor_rotation().yaw, -90.0)), abs(ndelta(npc.get_actor_rotation().yaw, -90.0)) <= 3.5)
    yield ("secs", 2.0)
    check("seated: loop playing (slot weight %.2f), movement held" % g(ac, "slot_node_weight"), g(ac, "montage_playing") and g(ac, "slot_node_weight") >= 0.95 and S["cmc"].get_editor_property("movement_mode").name == "MOVE_NONE")

    # ---- single-stop destination: every idle cycle (10-12 s) re-plans the same stop and must not stand the NPC up -----------------------------------
    base_cont, base_events = g(ac, "continuation_count"), len(S["events"])
    yield ("secs", 70.0)
    cyc = g(ac, "continuation_count") - base_cont
    check("%d idle cycles at the single seat stop: all continuations, still one start, no completes, no state change (%d events)" % (cyc, len(S["events"]) - base_events),
          cyc >= 4 and g(ac, "start_count") == 1 and g(ac, "complete_count") == 0 and len(S["events"]) == base_events and g(ac, "state").name == "PERFORMING",
          "cont+%d starts %d completes %d events+%d" % (cyc, g(ac, "start_count"), g(ac, "complete_count"), len(S["events"]) - base_events))
    check("the loop montage never stopped by itself over %.0f loops" % (70.0 / 4.3), g(ac, "unexpected_stop_count") == 0 and g(ac, "montage_playing"))
    check("capsule never moved: %.2f cm" % g(ac, "max_displacement_cm"), g(ac, "max_displacement_cm") < 0.5)

    # ---- schedule change while seated: lunch -> recreation -----------------------------------------------------------------------------------------
    here = npc.get_actor_location()
    serial1 = g(sc, "replan_serial")
    mgr.set_time_of_day_hours(13.0)
    mgr.set_editor_property("paused", False)
    yield ("until", lambda: g(sc, "replan_serial") > serial1, 60.0)
    t_replan = S["last_t"]
    mgr.set_editor_property("paused", True)
    check("the schedule change raised exactly one replan", not S["timed_out"] and g(sc, "replan_serial") == serial1 + 1)
    yield ("until", lambda: g(ac, "state").name == "EXITING", 5.0)
    t_exit = S["last_t"]
    check("the stand-up started %.2f s after the replan (the 1.5 s release grace is skipped when leaving)" % (t_exit - t_replan), not S["timed_out"] and (t_exit - t_replan) < 0.9, str(t_exit - t_replan))
    yield ("until", lambda: g(ac, "state").name == "IDLE", 6.0)
    t_idle = S["last_t"]
    leave = npc.get_actor_location()
    check("the stand-up ended by the animation %.2f s after it started (clip 2.27 s), complete count %d" % (t_idle - t_exit, g(ac, "complete_count")), not S["timed_out"] and 1.9 <= t_idle - t_exit <= 2.8 and g(ac, "complete_count") == 1)
    check("movement restored only after the stand-up; no slide while standing up (%.1f cm)" % d2(here.x, here.y, leave.x, leave.y), S["cmc"].get_editor_property("movement_mode").name in ("MOVE_WALKING", "MOVE_NAV_WALKING") and d2(here.x, here.y, leave.x, leave.y) < 40.0)
    yield ("until", lambda: g(ac, "state").name == "PERFORMING" and str(g(ac, "active_marker_id")) == "Rec_TV", 500.0)
    check("QUI01 walked on to the TV and started WatchTV (the existing activity still works after a seated one)", not S["timed_out"])
    yield ("secs", 3.0)

    # ---- invariants and regression ----------------------------------------------------------------------------------------------------------------
    smp = S["samples"]
    # Stage C2: the APPROACHING state (the final walk to the marker) is the one busy state in which movement is deliberately NOT held; every other busy state is.
    busy = [s for s in smp if s["st"] not in ("IDLE", "APPROACHING")]
    check("movement held on every tick while an activity was busy (%d samples; the final approach walk is excluded by design)" % len(busy), all(s["mm"] == "MOVE_NONE" for s in busy), str([s for s in busy if s["mm"] != "MOVE_NONE"][:2]))
    steps = [d2(p["x"], p["y"], q["x"], q["y"]) for p, q in zip(smp, smp[1:]) if p["st"] not in ("IDLE", "APPROACHING") and q["st"] not in ("IDLE", "APPROACHING")]
    check("no snapping while an activity was active: largest step %.3f cm" % max(steps + [0.0]), max(steps + [0.0]) < 1.0)
    big = max(d2(p["x"], p["y"], q["x"], q["y"]) for p, q in zip(smp, smp[1:]))
    check("no teleport: largest per-tick step %.1f cm" % big, big < 40.0)
    seat_samples = [s for s in smp if s["st"] == "PERFORMING" and s["t"] < t_replan]
    if seat_samples and max(s["pz"] for s in smp) - min(s["pz"] for s in smp) > 20.0:
        seated = [s["pz"] for s in seat_samples if s["pz"] < 75.0]
        check("seated pelvis %.1f..%.1f cm over %d samples (clip 52.9 cm)" % (min(seated), max(seated), len(seated)), len(seated) > 100 and 48.0 <= min(seated) and max(seated) <= 58.0)
    check("no navigation failures for QUI01 (%d)" % (int(npc.get_editor_property("NavFailureCount")) - nf0), int(npc.get_editor_property("NavFailureCount")) == nf0)
    nfo = {k: int(v.get_editor_property("NavFailureCount")) - others0[k] for k, v in others.items()}
    log("INFO other prisoners' navigation failures during the run: %s" % nfo)
    check("other prisoners: no navigation failures (see the cafeteria-aisle note in the Stage B record if this fails)", sum(nfo.values()) == 0, str(nfo))
    finish(0)


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 300000:
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
        if "ac" in S and S["ac"] is not None and "mesh" in S and S["mesh"] is not None:
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
