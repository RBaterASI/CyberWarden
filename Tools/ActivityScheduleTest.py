"""Headless PIE end-to-end test: QUI01 follows its schedule, watches TV at Rec_TV, and a schedule change ends the activity cleanly.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/ActivityScheduleTest.py -Log <abs log>                       (driver emulation)
  powershell -File Tools/RunHeadless.ps1 -Script Tools/ActivityScheduleTest.py -Log <abs log> -Env ACT_MODE=statetree  (real StateTree)

ACT_MODE=emulation (default): QUI01's StateTree is stopped in the PIE copy and a Python driver runs exactly the routine of the
Checkpoint B tree plus the M2.3 Stage B additions, calling the same native component API the StateTree tasks call (plan task: plan,
Move To radius, wait for the exit; Perform Activity task: request on entering the idle state, release on leaving it).
ACT_MODE=statetree: nothing is driven; the real StateTree (after the manual Stage B edit) is observed.
Both modes check the same things: the activity starts once per arrival at Rec_TV, faces the TV, plays through DefaultSlot, a schedule change
(work -> lunch, then lunch -> recreation) ends it before the NPC moves, movement is restored, nobody teleports, no navigation failures, the
other three prisoners are unaffected.
"""
import math
import os

import unreal

import cw_activity as ca

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
MODE = os.environ.get("ACT_MODE", "emulation")
SLOMO = float(os.environ.get("ACT_SLOMO", "4"))
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
layout = ca.load_layout()
TV = ca.prop_center(layout, "Prop_Rec_TV")
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "until": None, "timed_out": False, "res": [], "fail": [], "samples": [],
     "events": [], "last_t": None, "driving": False, "others": {}, "others_nf": {}, "others_fail": []}
D = {"state": "init", "until": 0.0, "dest": None, "radius": 60.0, "move_t": 0.0, "arrivals_tv": 0, "moves": 0, "navfail": 0}


def log(m):
    unreal.log("[ACTSCHED] " + m)


def check(name, ok, detail=""):
    S["res"].append(bool(ok))
    if not ok:
        S["fail"].append(name)
    log("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  (%s)" % detail))


def finish(code):
    unreal.unregister_slate_post_tick_callback(S["h"])
    log("RESULT %s (%d/%d checks) mode=%s" % ("PASS" if not S["fail"] and code == 0 else "FAIL", sum(S["res"]), len(S["res"]), MODE))
    level_sub.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


def d2(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def ndelta(a, b):
    d = (b - a) % 360.0
    return d - 360.0 if d > 180.0 else d


def g(c, k):
    return c.get_editor_property(k)


def ev(kind, detail=""):
    S["events"].append((S["last_t"], kind, detail))
    log("t=%7.1f %s %s" % (S["last_t"], kind, detail))


# ------------------------------------------------------------------------------------------------ driver (emulation mode)
def plan(now):
    sc, ac = S["sc"], S["ac"]
    d = sc.plan_for_current_period()
    D["dest"] = d
    if not d.valid:
        D["state"], D["until"] = "recover", now + 2.0
        return
    delay = float(d.start_delay_seconds)
    D["radius"] = ac.get_move_acceptable_radius(d.marker_id, 60.0)
    ac.expedite_release(d.marker_id, d.move_required)  # Stage C1: leaving for another stop skips the release grace window (as the plan task does)
    delay = max(delay, ac.get_seconds_until_free_for(d.marker_id, d.move_required))
    D["state"], D["until"] = "delay", now + delay


def start_idle(now):
    d = D["dest"]
    D["state"], D["until"] = "idle", now + float(d.idle_seconds)
    S["ac"].request_activity(d.marker_id)


def drive(now):
    sc, ac, ctrl, npc = S["sc"], S["ac"], S["ctrl"], S["npc"]
    st = D["state"]
    if st != "init" and g(sc, "replan_requested"):
        if st == "idle":
            ac.release_activity()  # Perform Activity ExitState
        elif st == "moving":
            ctrl.stop_movement()
        plan(now)
        return
    if st == "init":
        plan(now)
    elif st == "delay" and now >= D["until"]:
        d = D["dest"]
        if d.move_required:
            ctrl.move_to_location(d.marker.get_actor_location(), D["radius"], True, True, False, False, None, True)
            D["moves"] += 1
            D["state"], D["move_t"] = "moving", now
        else:
            start_idle(now)
    elif st == "moving":
        d = D["dest"]
        loc = npc.get_actor_location()
        m = d.marker.get_actor_location()
        if "IDLE" in str(ctrl.get_move_status()) and d2(loc.x, loc.y, m.x, m.y) < D["radius"] + 34.0 + 45.0:
            if str(d.marker_id) == "Rec_TV":
                D["arrivals_tv"] += 1
            start_idle(now)
        elif "IDLE" in str(ctrl.get_move_status()) and now - D["move_t"] > 1.5:
            D["navfail"] += 1
            D["state"], D["until"] = "recover", now + 2.0
    elif st == "idle" and now >= D["until"]:
        ac.release_activity()  # Perform Activity ExitState (the idle Delay ended)
        plan(now)
    elif st == "recover" and now >= D["until"]:
        plan(now)


# ------------------------------------------------------------------------------------------------ observation
def observe(now):
    npc, ac = S["npc"], S["ac"]
    loc = npc.get_actor_location()
    for k, v in S["others"].items():  # navigation failures of the other prisoners, with where they happened
        nf = int(v.get_editor_property("NavFailureCount"))
        if nf > S["others_nf"][k]:
            ol = v.get_actor_location()
            S["others_fail"].append((k, round(now, 1), ol.x, ol.y, d2(ol.x, ol.y, loc.x, loc.y)))
            S["others_nf"][k] = nf
    st = g(ac, "state").name
    S["samples"].append((now, loc.x, loc.y, npc.get_actor_rotation().yaw, st, g(ac, "start_count")))
    if S["last_st"] != st:
        ev("activity %s -> %s" % (S["last_st"], st), "marker=%s start_count=%d" % (g(ac, "active_marker_id"), g(ac, "start_count")))
        S["last_st"] = st
    if MODE == "statetree":
        ms = str(npc.get_editor_property("MoveState"))
        if ms != S.get("ms"):
            prev, S["ms"] = S.get("ms"), ms
            tvm = unreal.GameplayStatics.get_all_actors_with_tag(S["gw"], "MarkerId:Rec_TV")[0].get_actor_location()
            if ms == "Idle" and prev == "Moving" and d2(loc.x, loc.y, tvm.x, tvm.y) < 150.0:
                D["arrivals_tv"] += 1
            if ms == "NavFail":
                D["navfail"] += 1


def tv_loc():
    return unreal.GameplayStatics.get_all_actors_with_tag(S["gw"], "MarkerId:Rec_TV")[0].get_actor_location()


def run(gw):
    npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
    mgr = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")[0]
    S.update(gw=gw, npc=npcs["QUI01"], mgr=mgr, last_st=None)
    npc = S["npc"]
    S["sc"] = npc.get_component_by_class(unreal.PrisonScheduleComponent)
    S["ac"] = npc.get_component_by_class(unreal.PrisonActivityComponent)
    S["ctrl"] = npc.get_controller()
    S["cmc"] = npc.get_component_by_class(unreal.CharacterMovementComponent)
    ctl = S["ctrl"]
    if MODE == "emulation":
        stc = ctl.get_component_by_class(unreal.StateTreeAIComponent)
        if stc is not None:
            stc.stop_logic("activity schedule test")  # QUI01 only; the other prisoners keep running the real tree
    others0 = {k: int(v.get_editor_property("NavFailureCount")) for k, v in npcs.items() if k != "QUI01"}
    S["others"] = {k: v for k, v in npcs.items() if k != "QUI01"}
    S["others_nf"] = dict(others0)
    pos0 = {k: v.get_actor_location() for k, v in npcs.items() if k != "QUI01"}
    mgr.set_editor_property("time_scale", 30.0)
    mgr.set_editor_property("paused", False)
    mgr.set_time_of_day_hours(8.0)  # work period: QUI01 alternates Rec_Table_B and Rec_TV (the 30x clock keeps running)
    yield ("ticks", 5)
    if MODE == "emulation":
        S["sc"].acknowledge_replan()  # adopt the work period before the driver starts, as a fresh plan would
        S["driving"] = True
    unreal.SystemLibrary.execute_console_command(gw, "slomo %g" % SLOMO)
    check("%s: QUI01 has the schedule and activity components" % MODE, S["sc"] is not None and S["ac"] is not None)

    # ---- first visit to the TV ---------------------------------------------------------------------------------------
    yield ("until", lambda: g(S["ac"], "state").name == "PERFORMING" and str(g(S["ac"], "active_marker_id")) == "Rec_TV", 500.0)
    check("QUI01 reached Rec_TV and started WatchTV by following its schedule", not S["timed_out"])
    if S["timed_out"]:
        l = npc.get_actor_location()
        log("DEBUG driver=%s dest=%s pos=(%.0f,%.0f) activity=%s reason=%s clock=%s plans=%s serial=%s mode=%s" % (D["state"], D["dest"].marker_id if D["dest"] else None, l.x, l.y, g(S["ac"], "state").name, g(S["ac"], "last_failure_reason"), S["mgr"].get_clock_string(), g(S["sc"], "plan_count"), g(S["sc"], "replan_serial"), S["cmc"].get_editor_property("movement_mode").name))
        finish(5)
        return
    t_perf = S["last_t"]
    yield ("secs", 2.0)
    ac = S["ac"]
    loc = npc.get_actor_location()
    tvm = tv_loc()
    want = math.degrees(math.atan2(TV[1] - loc.y, TV[0] - loc.x))
    check("facing the TV: yaw error %.2f degrees" % abs(ndelta(npc.get_actor_rotation().yaw, want)), abs(ndelta(npc.get_actor_rotation().yaw, want)) <= 3.5)
    check("stopped %.0f cm from the marker (within the point tolerance 150)" % d2(loc.x, loc.y, tvm.x, tvm.y), d2(loc.x, loc.y, tvm.x, tvm.y) <= 150.0)
    check("idle animation plays through DefaultSlot (weight %.2f)" % g(ac, "slot_node_weight"), g(ac, "montage_playing") and g(ac, "slot_node_weight") >= 0.95)
    check("movement is held while watching", S["cmc"].get_editor_property("movement_mode").name == "MOVE_NONE")
    check("one start for this arrival (starts %d, arrivals %d)" % (g(ac, "start_count"), D["arrivals_tv"] if MODE == "emulation" else -1), g(ac, "start_count") == 1)
    yield ("secs", 3.0)
    check("still watching 5 s later without a restart", g(ac, "start_count") == 1 and g(ac, "state").name == "PERFORMING")
    here = npc.get_actor_location()

    # ---- schedule change: work -> lunch while watching -----------------------------------------------------------------
    serial0 = g(S["sc"], "replan_serial")
    ev("JUMP", "clock to 12:00 (lunch) while watching")
    mgr.set_time_of_day_hours(12.0)
    mgr.set_editor_property("paused", False)
    t_jump = S["last_t"]
    yield ("until", lambda: g(S["sc"], "replan_serial") > serial0, 40.0)
    check("QUI01 raised exactly one replan after its stagger", not S["timed_out"] and g(S["sc"], "replan_serial") == serial0 + 1, str(g(S["sc"], "replan_serial")))
    t_req = S["last_t"]
    yield ("until", lambda: g(ac, "state").name == "IDLE", 10.0)
    t_idle = S["last_t"]
    leave_loc = npc.get_actor_location()
    check("the activity ended cleanly after the schedule change (%.2f s after the request)" % (t_idle - t_req), not S["timed_out"] and (t_idle - t_req) < 3.0)
    check("movement restored after the interruption", S["cmc"].get_editor_property("movement_mode").name == "MOVE_WALKING")
    check("the NPC had not slid away while the activity ended (%.0f cm)" % d2(here.x, here.y, leave_loc.x, leave_loc.y), d2(here.x, here.y, leave_loc.x, leave_loc.y) < 40.0)
    seat = unreal.GameplayStatics.get_all_actors_with_tag(gw, "MarkerId:Seat_Table_1_5")[0].get_actor_location()
    yield ("until", lambda: d2(npc.get_actor_location().x, npc.get_actor_location().y, seat.x, seat.y) < 160.0, 200.0)
    check("QUI01 walked to its lunch seat (locomotion resumed)", not S["timed_out"])
    mgr.set_editor_property("paused", True)

    # ---- second visit after the next change (lunch -> recreation) ---------------------------------------------------------
    starts_before = g(ac, "start_count")
    serial1 = g(S["sc"], "replan_serial")
    mgr.set_time_of_day_hours(13.0)  # recreation: Rec_TV and Rec_Table_B
    mgr.set_editor_property("paused", False)
    yield ("until", lambda: g(ac, "state").name == "PERFORMING" and str(g(ac, "active_marker_id")) == "Rec_TV", 500.0)
    check("recreation: QUI01 came back to the TV and started WatchTV again", not S["timed_out"])
    yield ("secs", 3.0)
    check("a second arrival is a second start (%d -> %d), still no restarts" % (starts_before, g(ac, "start_count")), g(ac, "start_count") == starts_before + 1 and g(ac, "state").name == "PERFORMING")
    mgr.set_editor_property("paused", True)

    # ---- single-stop destination: re-planning at the end of every idle cycle must not restart the activity ----------------------
    da = mgr.get_editor_property("schedule_data")
    npc_rows = da.get_editor_property("npcs")
    for i, row in enumerate(npc_rows):  # struct elements are copies: write every level back
        if str(row.get_editor_property("npc_id")) == "QUI01":
            periods = list(row.get_editor_property("periods"))
            for j, ap in enumerate(periods):
                if str(ap.get_editor_property("period_id")) == "work":
                    ap.set_editor_property("stop_marker_ids", ["Rec_TV"])  # in memory only, never saved: work now has the single stop Rec_TV
                    ap.set_editor_property("idle_min", 20.0)
                    ap.set_editor_property("idle_max", 25.0)
                    periods[j] = ap
            row.set_editor_property("periods", periods)
            npc_rows[i] = row
    da.set_editor_property("npcs", npc_rows)
    for row in da.get_editor_property("npcs"):
        if str(row.get_editor_property("npc_id")) == "QUI01":
            for ap in row.get_editor_property("periods"):
                if str(ap.get_editor_property("period_id")) == "work":
                    log("QUI01 work stops now: %s idle %s-%s" % ([str(x) for x in ap.get_editor_property("stop_marker_ids")], ap.get_editor_property("idle_min"), ap.get_editor_property("idle_max")))
    serial2 = g(S["sc"], "replan_serial")
    mgr.set_time_of_day_hours(8.0)  # recreation -> work (the clock moves backwards: the stagger restarts)
    mgr.set_editor_property("paused", False)
    yield ("until", lambda: g(S["sc"], "replan_serial") > serial2, 40.0)
    check("work (single stop Rec_TV) replans once", not S["timed_out"])
    yield ("secs", 4.0)
    check("QUI01 was already at the TV: the replan continued the activity instead of restarting it", g(ac, "state").name == "PERFORMING" and g(ac, "start_count") == starts_before + 1,
          "%s %s" % (g(ac, "state").name, g(ac, "start_count")))
    base_start, base_cont, base_n = g(ac, "start_count"), g(ac, "continuation_count"), len(S["events"])
    yield ("secs", 70.0)  # three or more idle cycles of 20-25 s, each ending in a re-plan of the same stop
    cycles = g(ac, "continuation_count") - base_cont
    check("several idle cycles at the single stop: %d continuations, still %d start, no state changes" % (cycles, g(ac, "start_count")),
          cycles >= 2 and g(ac, "start_count") == base_start and len(S["events"]) == base_n and g(ac, "state").name == "PERFORMING",
          "cont+%d start %d events+%d" % (cycles, g(ac, "start_count"), len(S["events"]) - base_n))
    check("the loop montage never stopped by itself", g(ac, "unexpected_stop_count") == 0 and g(ac, "montage_playing"))
    mgr.set_editor_property("paused", True)

    # ---- global checks --------------------------------------------------------------------------------------------------------
    pts = S["samples"]
    big = max(d2(p[1], p[2], q[1], q[2]) for p, q in zip(pts, pts[1:]))
    check("no teleport: largest per-tick step %.1f cm (walk speed 150 cm/s)" % big, big < 40.0)
    held = [(p, q) for p, q in zip(pts, pts[1:]) if p[4] in ("ALIGNING", "ENTERING", "PERFORMING", "EXITING") and q[4] in ("ALIGNING", "ENTERING", "PERFORMING", "EXITING")]
    held_max = max([d2(p[1], p[2], q[1], q[2]) for p, q in held] or [0.0])
    check("no visible snapping while an activity is active: largest step %.2f cm" % held_max, held_max < 1.0)
    check("no navigation failures for QUI01 (%d)" % D["navfail"], D["navfail"] == 0)
    check("no StateTree/driver restart storm: %d plans in the run" % g(S["sc"], "plan_count"), g(S["sc"], "plan_count") < 60)
    for f in S["others_fail"]:
        log("INFO other prisoner navigation failure: %s at t=%.1f (%.0f, %.0f), %.0f cm from QUI01" % f)
    near = [f for f in S["others_fail"] if f[4] < 1000.0]
    check("other prisoners unaffected by QUI01 activity: %d navigation failure(s) within 10 m of QUI01 (%d elsewhere, reported above)" % (len(near), len(S["others_fail"]) - len(near)), not near, str(near))
    finish(0)


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 200000:
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
        S["last_t"] = now
        if S["gen"] is None:
            S["gen"] = run(gw)
        if "ac" in S:
            observe(now)
            if MODE == "emulation" and S["driving"]:
                drive(now)
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
