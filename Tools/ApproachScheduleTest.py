"""Headless PIE test of the final approach on the REAL StateTree (M2.3 Stage C2). Saves nothing.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/ApproachScheduleTest.py -Log <abs log>

Nothing is driven: QUI01 runs the real ST_NPCRoutine on the real regenerated activity data.
Part 1 - a schedule change DURING the approach: QUI01 follows breakfast to Seat_Table_1_5 at time dilation 1; the moment its activity component reports
  APPROACHING the schedule hour is changed (breakfast -> work). The Perform Activity task exits and releases the component, which must cancel the approach
  (a cancel, not a failure: no lockout, nothing started, no seated pose), leave the NPC standing with movement free, and QUI01 must walk on to its work stops.
  Then the hour goes back to breakfast: QUI01 walks to the seat again, the approach succeeds within the 7 cm tolerance and it sits (proves the cancel left no state behind).
  The race (the approach lasts about 0.4 s) is retried up to three times; if it is never caught the check reports that instead of passing silently.
Part 2 - a FAILED approach in the real tree: only in memory the seat point's final-approach timeout is 0.05 s (the walk cannot finish). The NPC must stay
  standing next to the seat for the rest of its meal, the point must not be retried inside the 120 s lockout (the routine's idle cycle re-requests it and is
  refused), nothing may be teleported, no navigation failure may appear, and the point is tried again once the lockout has passed.
"""
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SEAT = "Seat_Table_1_5"
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "until": None, "res": [], "fail": [], "samples": [], "last_t": None, "timed_out": False}


def log(m):
    unreal.log("[APPRSCHED] " + m)


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


def g(c, k):
    return c.get_editor_property(k)


def d2(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def ndelta(a, b):
    d = (b - a) % 360.0
    return d - 360.0 if d > 180.0 else d


def mloc(mid):
    return unreal.GameplayStatics.get_all_actors_with_tag(S["gw"], "MarkerId:" + mid)[0].get_actor_location()


def sample(now):
    npc, ac, mesh = S["npc"], S["ac"], S["mesh"]
    loc = npc.get_actor_location()
    S["samples"].append(dict(t=now, x=loc.x, y=loc.y, st=g(ac, "state").name, mm=S["cmc"].get_editor_property("movement_mode").name, mont=mesh.get_anim_instance().get_current_active_montage() is not None,
                             pz=mesh.get_socket_location("pelvis").z - mesh.get_world_location().z, ms=str(S["ctrl"].get_move_status()), sc=g(ac, "start_count")))


def set_hour(hour, wait_replan=True, fast=False):
    """Jumps the schedule hour. QUI01 has a departure stagger of 240 clock seconds (0.8 x 5 min): at the normal time scale 30 the replan is raised about 8 s after the
    change, far longer than the 0.35 s final approach. fast=True runs the manager clock at time scale 6000 (in memory, restored afterwards) so the stagger passes in
    a couple of ticks and the change reaches the routine while the approach is still running. No schedule data is changed."""
    mgr, sc = S["mgr"], S["sc"]
    serial0 = g(sc, "replan_serial")
    if fast:
        mgr.set_editor_property("time_scale", 6000.0)
    mgr.set_time_of_day_hours(hour)
    mgr.set_editor_property("paused", False)
    if wait_replan:
        yield ("until", lambda: g(sc, "replan_serial") > serial0, 80.0)
        mgr.set_editor_property("paused", True)
    if fast:
        mgr.set_editor_property("time_scale", 30.0)


def fetch(gw):
    npc = S["npc"]
    S.update(sc=npc.get_component_by_class(unreal.PrisonScheduleComponent), ac=npc.get_component_by_class(unreal.PrisonActivityComponent), ctrl=npc.get_controller(),
             cmc=npc.get_component_by_class(unreal.CharacterMovementComponent), mesh=npc.get_component_by_class(unreal.SkeletalMeshComponent),
             mgr=unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")[0])


def run(gw):
    npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
    npc = npcs["QUI01"]
    S.update(gw=gw, npc=npc)
    fetch(gw)
    S["mesh"].set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    yield ("ticks", 5)
    fetch(gw)
    ac, mgr = S["ac"], S["mgr"]
    others = {k: v for k, v in npcs.items() if k != "QUI01"}
    others0 = {k: int(v.get_editor_property("NavFailureCount")) for k, v in others.items()}
    nf0 = int(npc.get_editor_property("NavFailureCount"))
    max_walk = float(S["cmc"].get_editor_property("max_walk_speed"))
    mk = mloc(SEAT)
    mgr.set_editor_property("time_scale", 30.0)
    check("the real regenerated data is in use: seat point present, no override", ac.has_interaction_point(SEAT) and g(ac, "activity_data_override") is None)

    # ================= Part 1: a schedule change during the approach ==========================================================================================
    unreal.SystemLibrary.execute_console_command(gw, "slomo 1")
    caught = None
    for attempt in (1, 2, 3):
        yield from set_hour(7.0)  # breakfast
        a_start0, canc0, succ0, st0, fail0 = g(ac, "approach_start_count"), g(ac, "approach_cancel_count"), g(ac, "approach_success_count"), g(ac, "start_count"), g(ac, "approach_fail_count")
        yield ("until", lambda: g(ac, "state").name == "APPROACHING" and g(ac, "approach_start_count") > a_start0, 150.0)  # the walk from the cell takes about 45 s; 150 s keeps a miss cheap
        if S["timed_out"]:
            log("attempt %d: the approach never started (state %s, %s)" % (attempt, g(ac, "state").name, g(ac, "last_failure_reason")))
            continue
        t_appr = S["last_t"]
        d_at = d2(npc.get_actor_location().x, npc.get_actor_location().y, mk.x, mk.y)
        i_mark = len(S["samples"])
        yield from set_hour(10.0, fast=True)  # work: the schedule changes while the approach is running
        log("attempt %d: schedule changed %.0f cm from the marker; component state right after the replan: %s" % (attempt, d_at, g(ac, "state").name))
        yield ("secs", 4.0)
        cancelled = g(ac, "approach_cancel_count") == canc0 + 1 and g(ac, "approach_success_count") == succ0
        log("attempt %d: cancel count +%d, success count +%d, start count +%d, result '%s'" % (attempt, g(ac, "approach_cancel_count") - canc0, g(ac, "approach_success_count") - succ0, g(ac, "start_count") - st0, g(ac, "last_approach_result")))
        if cancelled:
            caught = (attempt, i_mark, t_appr)
            break
        # the approach had already succeeded (the race was lost): the NPC sits and stands up on the schedule change; try again
        yield ("until", lambda: g(ac, "state").name == "IDLE", 15.0)
        yield ("secs", 2.0)
    check("a schedule change was delivered while the component was APPROACHING (attempt %s)" % (caught[0] if caught else "none"), caught is not None, "the approach always finished first")
    if caught:
        smp = S["samples"][caught[1]:]
        check("the approach was CANCELLED, not failed: result '%s', fail count unchanged, nothing started" % g(ac, "last_approach_result"),
              str(g(ac, "last_approach_result")).startswith("cancelled") and g(ac, "approach_fail_count") == fail0 and g(ac, "start_count") == st0)
        check("the NPC was never held and never sat down after the change (states %s)" % sorted(set(s["st"] for s in smp)), all(s["mm"] != "MOVE_NONE" and s["st"] in ("IDLE", "APPROACHING") and not s["mont"] for s in smp))
        check("component idle, movement free, standing (pelvis %.0f cm)" % smp[-1]["pz"], g(ac, "state").name == "IDLE" and not g(ac, "movement_held") and smp[-1]["pz"] > 80.0)
        p0 = smp[-1]
        yield ("secs", 120.0)
        p1 = S["samples"][-1]
        walked = d2(p0["x"], p0["y"], p1["x"], p1["y"])
        check("the routine took over: QUI01 walked %.0f cm on to its work stops (movement authority is back with the routine)" % walked, walked > 400.0, str(walked))
        check("no lockout was created by a cancel", g(ac, "approach_lockout_refusals") == 0 and g(ac, "approach_fail_count") == fail0)
        # back to a meal: the same seat must work normally
        yield from set_hour(12.0)
        s_before = g(ac, "approach_success_count")
        yield ("until", lambda: g(ac, "state").name == "PERFORMING" and str(g(ac, "active_marker_id")) == SEAT and g(ac, "approach_success_count") > s_before, 900.0)
        check("back at a meal QUI01 walked to the seat again, the approach succeeded and it sat", not S["timed_out"], "%s %s" % (g(ac, "state").name, g(ac, "last_approach_result")))
        yield ("secs", 2.5)
        loc = npc.get_actor_location()
        dfin = d2(loc.x, loc.y, mk.x, mk.y)
        check("...%.3f cm from the marker (limit 7), yaw error %.2f deg, seated pose (pelvis %.1f cm)" % (dfin, abs(ndelta(npc.get_actor_rotation().yaw, -90.0)), S["samples"][-1]["pz"]),
              dfin <= 7.0 and abs(ndelta(npc.get_actor_rotation().yaw, -90.0)) <= 3.5 and S["samples"][-1]["pz"] < 75.0 and g(ac, "montage_playing"))
    else:
        log("part 1 could not be exercised; continuing with part 2")

    # ================= Part 2: a failed approach in the real tree =============================================================================================
    # The component's lockout map cannot be cleared, so the failure scenario uses the OTHER meal marker flow: the real seat point is replaced in memory by a copy
    # with a 0.05 s timeout, and QUI01 is sent away and back; its earlier success does not matter (a success sets no lockout).
    sector = mgr.get_editor_property("activity_data")
    new_pts = []
    for p in sector.get_editor_property("points"):
        if str(p.get_editor_property("marker_id")) == SEAT:
            p = unreal.PrisonInteractionPoint(marker_id=SEAT, activity_id=p.get_editor_property("activity_id"), facing_mode=p.get_editor_property("facing_mode"),
                                              facing_yaw_degrees=p.get_editor_property("facing_yaw_degrees"), facing_point=p.get_editor_property("facing_point"),
                                              arrival_tolerance_cm=p.get_editor_property("arrival_tolerance_cm"), capacity=p.get_editor_property("capacity"), final_approach=True,
                                              final_approach_accept_cm=p.get_editor_property("final_approach_accept_cm"), final_approach_tolerance_cm=p.get_editor_property("final_approach_tolerance_cm"),
                                              final_approach_max_distance_cm=p.get_editor_property("final_approach_max_distance_cm"), final_approach_timeout_seconds=0.05)
        new_pts.append(p)
    data = unreal.new_object(unreal.PrisonActivityData)
    data.set_editor_property("activities", list(sector.get_editor_property("activities")))
    data.set_editor_property("points", new_pts)
    check("failure-test data (seat timeout 0.05 s, in memory only) validates", len(list(data.validate_data())) == 0, str(list(data.validate_data())))
    yield from set_hour(10.0)  # work: stand up and leave the seat first
    yield ("until", lambda: g(ac, "state").name == "IDLE", 20.0)
    yield ("secs", 90.0)  # let QUI01 get well away from the seat
    mgr.set_editor_property("activity_data", data)
    fetch(gw)
    ac, mgr = S["ac"], S["mgr"]
    check("the component now serves the failure-test data", ac.has_interaction_point(SEAT))
    unreal.SystemLibrary.execute_console_command(gw, "slomo 3")
    base_starts, base_fail, base_ref, base_sc = g(ac, "approach_start_count"), g(ac, "approach_fail_count"), g(ac, "approach_lockout_refusals"), g(ac, "start_count")
    i_fail0 = len(S["samples"])
    yield from set_hour(12.0)  # lunch: single stop at the seat, idle cycles of 50-80 s
    yield ("until", lambda: g(ac, "approach_fail_count") > base_fail, 900.0)
    check("the approach failed in the real tree: '%s'" % g(ac, "last_approach_result"), not S["timed_out"] and str(g(ac, "last_approach_result")).startswith("failed: timed out"))
    if S["timed_out"]:
        finish(5)
        return
    t_fail = S["last_t"]
    fpos = (npc.get_actor_location().x, npc.get_actor_location().y)
    d_stand = d2(fpos[0], fpos[1], mk.x, mk.y)
    check("QUI01 stays standing %.1f cm from the seat: idle, movement free, no activity started" % d_stand, g(ac, "state").name == "IDLE" and not g(ac, "movement_held") and g(ac, "start_count") == base_sc)
    yield ("until", lambda: S["last_t"] >= t_fail + 112.0, 140.0)
    smp = [s for s in S["samples"][i_fail0:] if s["t"] >= t_fail]
    check("inside the 120 s lockout (%.0f s observed): the point was NOT tried again (approaches +%d)" % (S["last_t"] - t_fail, g(ac, "approach_start_count") - base_starts - 1),
          g(ac, "approach_start_count") == base_starts + 1)
    check("the routine's idle cycle re-requested the point and was refused %d time(s); no request storm" % (g(ac, "approach_lockout_refusals") - base_ref), 1 <= g(ac, "approach_lockout_refusals") - base_ref <= 4, str(g(ac, "approach_lockout_refusals") - base_ref))
    check("QUI01 never sat, was never held, stayed standing (states %s)" % sorted(set(s["st"] for s in smp)), all(s["st"] == "IDLE" and s["mm"] != "MOVE_NONE" and not s["mont"] and s["pz"] > 80.0 for s in smp))
    far = max(d2(s["x"], s["y"], fpos[0], fpos[1]) for s in smp)
    big = max(d2(p["x"], p["y"], q["x"], q["y"]) / max(q["t"] - p["t"], 1e-3) for p, q in zip(smp, smp[1:]) if q["t"] > p["t"])
    check("no teleport: top speed %.0f cm/s; it stayed within %.0f cm of where the approach failed" % (big, far), big <= max_walk * 1.35)
    check("no navigation failures for QUI01 (%d)" % (int(npc.get_editor_property("NavFailureCount")) - nf0), int(npc.get_editor_property("NavFailureCount")) == nf0)
    yield ("until", lambda: g(ac, "approach_start_count") > base_starts + 1 or S["last_t"] > t_fail + 300.0, 320.0)
    t_retry = S["last_t"] - t_fail
    check("once the lockout passed the point was tried again after %.0f s (at the next idle cycle after 120 s)" % t_retry, g(ac, "approach_start_count") > base_starts + 1 and t_retry >= 119.0, str(t_retry))
    nfo = {k: int(v.get_editor_property("NavFailureCount")) - others0[k] for k, v in others.items()}
    log("INFO other prisoners' navigation failures during the run: %s" % nfo)
    check("other prisoners: no navigation failures", sum(nfo.values()) == 0, str(nfo))
    finish(0)


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 800000:
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
        if "npc" in S and S.get("ac") is not None and S.get("mesh") is not None:
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
