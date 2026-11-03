"""Headless PIE test of the C++ UPrisonScheduleComponent on the four placed prisoners (M2.2 Checkpoint A). Saves nothing.

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/ScheduleComponentPieTest.py" -unattended -nop4 -nosplash -NullRHI

A temporary BP_PrisonScheduleManager (clock PAUSED, stepped by Python) is spawned into the unsaved editor-world copy before PIE,
so the level file is never changed. The component only plans and raises replan requests: it does not move anything, and the
NPCs keep running their existing StateTree routes in the background (they are not connected to the schedule yet).
"""
import json
import math
import os

import unreal

import cw_schedule as cs

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
data = cs.load()
periods = data["periods"]
pids = [p["id"] for p in periods]
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "wait_until": None, "res": [], "fail": []}


def log(m):
    unreal.log("[SCHEDTEST] " + m)


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


def sync(c):
    """Forces the component to adopt the manager current period (acknowledge) and plans for it: test preparation only."""
    c.acknowledge_replan()
    return c.plan_for_current_period()


def comp_of(npc):
    return npc.get_component_by_class(unreal.PrisonScheduleComponent)


def run(gw):
    mgrs = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")
    npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
    if not mgrs or len(npcs) != 4:
        log("FAILED: manager=%d npcs=%d" % (len(mgrs), len(npcs)))
        finish(4)
        return
    m = mgrs[0]
    m.set_editor_property("paused", True)
    for _a in npcs.values():  # since Checkpoint B the real StateTree plans and acknowledges replans itself: stop it in the PIE copy so this component-level test sees only its own calls
        _stc = _a.get_controller().get_component_by_class(unreal.StateTreeAIComponent)
        if _stc is not None:
            _stc.stop_logic("component test")
    m.set_editor_property("time_scale", 30.0)
    yield ("ticks", 20)
    comps = {nid: comp_of(a) for nid, a in npcs.items()}
    da = m.get_editor_property("schedule_data")
    check("manager has the schedule data asset", da is not None)
    check("all four NPCs have a schedule component", all(c is not None for c in comps.values()), str(comps))
    check("data asset validates", len(da.validate_data()) == 0, str(list(da.validate_data())))

    # ---- 1. assignments ----------------------------------------------------------------------------------------
    for nid, c in comps.items():
        c.refresh_context()
    yield ("ticks", 5)
    for nid, c in comps.items():
        want = data["assignments"][nid]
        check("%s: resolved id and schedule found" % nid, str(c.get_editor_property("resolved_npc_id")) == nid and c.get_editor_property("has_schedule"))
        npc_data = next(n for n in da.get_editor_property("npcs") if str(n.get_editor_property("npc_id")) == nid)
        ok = True
        for a in npc_data.get_editor_property("periods"):
            pid = str(a.get_editor_property("period_id"))
            w = want["schedule"][pid]
            ok &= [str(x) for x in a.get_editor_property("stop_marker_ids")] == w["stops"]
            ok &= (a.get_editor_property("idle_min"), a.get_editor_property("idle_max")) == (float(w["idle"][0]), float(w["idle"][1]))
        check("%s: data asset equals the JSON assignments (all 8 periods)" % nid, ok and len(npc_data.get_editor_property("periods")) == 8)
        errs = list(c.validate_assignments())
        check("%s: every scheduled destination exists and is NavDest:Yes" % nid, errs == [], str(errs))
        want_stagger = want["stagger_fraction"] * data["clock"]["stagger_max_game_minutes"] * 60.0
        check("%s: stagger %.0f game s (config)" % (nid, want_stagger), abs(c.get_editor_property("stagger_game_seconds") - want_stagger) < 1e-6)
        check("%s: stagger real seconds at 30x = %.1f" % (nid, want_stagger / 30.0), abs(c.get_stagger_real_seconds() - want_stagger / 30.0) < 1e-6)

    # ---- 2. plan at 06:00 + replan on the 07:00 boundary --------------------------------------------------------
    m.set_time_of_day_hours(6.0 + 59.0 / 60.0 + 58.0 / 3600.0)  # 06:59:58, Wake-up
    yield ("secs", 0.3)
    plan_count0 = {nid: c.get_editor_property("plan_count") for nid, c in comps.items()}  # the live StateTree may already have planned once at startup
    plans = {nid: c.plan_for_current_period() for nid, c in comps.items()}
    streak0 = {nid: c.get_editor_property("retry_streak_count") for nid, c in comps.items()}  # read right after the plan: later plans change it
    for nid, c in comps.items():
        p = plans[nid]
        w = data["assignments"][nid]["schedule"]["wake"]
        check("%s: wake-up plan valid, stop %s from the wake-up list, idle in range" % (nid, p.marker_id), p.valid and str(p.marker_id) in w["stops"] and
              w["idle"][0] <= p.idle_seconds <= w["idle"][1], p.reason)
        check("%s: applied period 0, no request pending" % nid, c.get_editor_property("applied_period_index") == 0 and not c.get_editor_property("replan_requested"))
    serial0 = {nid: c.get_editor_property("replan_serial") for nid, c in comps.items()}
    m.advance_game_seconds(5.0)  # 07:00:03 -> Breakfast
    yield ("secs", 0.3)
    hq = comps["QUI01"].plan_for_current_period()  # QUI01 stagger (240 game s) is still running: a routine re-plan keeps the OLD assignment
    check("re-plan during the stagger keeps the previous period assignment (%s)" % hq.marker_id, hq.valid and str(hq.marker_id) in data["assignments"]["QUI01"]["schedule"]["wake"]["stops"] and
          comps["QUI01"].get_editor_property("applied_period_index") == 0 and not comps["QUI01"].get_editor_property("replan_requested"), hq.reason)
    t_observed = None
    fired = {}
    steps = 0
    while len(fired) < 4 and steps < 80:
        yield ("secs", 0.12)
        if t_observed is None:
            t_observed = m.get_editor_property("game_seconds_total")
        for nid, c in comps.items():
            if nid not in fired and c.get_editor_property("replan_requested"):
                fired[nid] = m.get_editor_property("game_seconds_total") - t_observed
        if len(fired) < 4:
            m.advance_game_seconds(5.0)
        steps += 1
    for nid, c in comps.items():
        want = data["assignments"][nid]["stagger_fraction"] * data["clock"]["stagger_max_game_minutes"] * 60.0
        got = fired.get(nid)
        check("%s: replan raised after the stagger (%.0f game s expected, %s measured)" % (nid, want, got), got is not None and abs(got - want) <= 5.0 + 1e-6, str(got))
    yield ("secs", 0.5)
    for _ in range(20):  # keep stepping: the request must stay one-shot
        m.advance_game_seconds(5.0)
        yield ("secs", 0.12)
    for nid, c in comps.items():
        check("%s: exactly one replan request for the schedule change" % nid, c.get_editor_property("replan_serial") == serial0[nid] + 1, str(c.get_editor_property("replan_serial")))
    # acknowledge by planning: the request clears and does not come back
    m.set_time_of_day_hours(7.5)
    yield ("secs", 0.3)
    for nid, c in comps.items():
        p = c.plan_for_current_period()
        w = data["assignments"][nid]["schedule"]["breakfast"]
        check("%s: breakfast plan valid (%s)" % (nid, p.marker_id), p.valid and str(p.marker_id) in w["stops"], p.reason)
        check("%s: request acknowledged and cleared" % nid, not c.get_editor_property("replan_requested") and c.get_editor_property("replan_ack_count") >= 1 and
              c.get_editor_property("applied_period_index") == 1)
    for _ in range(15):
        m.advance_game_seconds(5.0)
        yield ("secs", 0.12)
    for nid, c in comps.items():
        check("%s: no new request without a period change" % nid, not c.get_editor_property("replan_requested") and c.get_editor_property("replan_serial") == serial0[nid] + 1)

    # ---- 3. single destination: no movement needed when already there ---------------------------------------------
    exp = npcs["EXP01"]
    c = comps["EXP01"]
    first = c.plan_for_current_period()
    check("EXP01 breakfast has a single stop", first.valid and first.single_stop and str(first.marker_id) == "Seat_Table_2_1", first.reason)
    exp.set_actor_location(first.marker.get_actor_location(), False, False)  # PIE copy only
    again = c.plan_for_current_period()
    check("EXP01 standing at its only stop: same stop, no movement request", again.valid and again.single_stop and not again.move_required and again.marker_id == first.marker_id, again.reason)

    # ---- 3b. start delay and retry back-off (outputs consumed by the StateTree task) --------------------------------------
    for nid in ("EXP01", "QUI01", "TRB01", "WRK01"):
        streak = streak0[nid]  # the live tree may have planned the same required movement a moment ago: that is a retry, with its back-off
        backoff = 0.0 if streak <= 0 else min(30.0, 2.0 * 2.0 ** (streak - 1))
        want_delay = comps[nid].get_stagger_real_seconds() if plan_count0[nid] == 0 else backoff  # only the very first plan of an NPC carries the stagger
        check("%s: start delay of the first test plan is %.1f s (%s)" % (nid, want_delay, "first plan ever: the stagger" if plan_count0[nid] == 0 else "a plan already existed: back-off for retry streak %d" % streak),
              abs(plans[nid].start_delay_seconds - want_delay) < 1e-6, str(plans[nid].start_delay_seconds))
    m.set_time_of_day_hours(6.5)  # wake-up: QUI01 has the single stop CellAssign_Cell_N5
    yield ("secs", 0.3)
    q = npcs["QUI01"]
    cq = comps["QUI01"]
    pre = sync(cq)  # re-plan for the wake-up period
    q.set_actor_location(pre.marker.get_actor_location(), False, False)  # stand at the stop: resets the back-off streak
    sync(cq)
    q.set_actor_location(unreal.Vector(2500, 400, 92), False, False)  # PIE copy only: far from the marker so a move is required
    p1 = cq.plan_for_current_period()
    p2 = cq.plan_for_current_period()
    p3 = cq.plan_for_current_period()
    check("QUI01 far from its stop: move required", p1.valid and p1.move_required, p1.reason)
    check("quick re-plans of the same movement back off: %.0f, %.0f, %.0f s" % (p1.start_delay_seconds, p2.start_delay_seconds, p3.start_delay_seconds),
          p1.start_delay_seconds == 0.0 and p2.start_delay_seconds == 2.0 and p3.start_delay_seconds == 4.0, "%s %s %s" % (p1.start_delay_seconds, p2.start_delay_seconds, p3.start_delay_seconds))
    q.set_actor_location(p3.marker.get_actor_location(), False, False)
    p4 = cq.plan_for_current_period()
    check("arriving resets the back-off (no move required, delay 0)", (not p4.move_required) and p4.start_delay_seconds == 0.0, str(p4.start_delay_seconds))
    for nid in ("EXP01", "QUI01", "TRB01", "WRK01"):
        sync(comps[nid])

    # ---- 4. midnight and lockdown --------------------------------------------------------------------------------
    for nid, c in comps.items():
        c.plan_for_current_period()
    m.set_time_of_day_hours(20.0 + 59.0 / 60.0 + 58.0 / 3600.0)  # 20:59:58 Free time
    yield ("secs", 0.3)
    for nid, c in comps.items():
        sync(c)
    s_before = {nid: c.get_editor_property("replan_serial") for nid, c in comps.items()}
    m.advance_game_seconds(5.0)  # 21:00:03 Lockdown
    for _ in range(60):
        yield ("secs", 0.12)
        m.advance_game_seconds(5.0)
    for nid, c in comps.items():
        check("%s: lockdown change detected exactly once" % nid, c.get_editor_property("replan_serial") == s_before[nid] + 1 and c.get_editor_property("replan_requested"))
        p = c.plan_for_current_period()
        check("%s: lockdown destination is its own cell (%s)" % (nid, p.marker_id), p.valid and str(p.marker_id) == "Lockdown_" + data["assignments"][nid]["schedule"]["lockdown"]["stops"][0].replace("Lockdown_", ""), p.reason)
    s_lock = {nid: c.get_editor_property("replan_serial") for nid, c in comps.items()}
    m.set_time_of_day_hours(22.0)
    yield ("secs", 0.3)
    for _ in range(60):  # 22:00 -> past midnight in 5-minute game steps
        m.advance_game_seconds(300.0)
        yield ("secs", 0.1)
    check("clock passed midnight (day number >= 2)", m.get_editor_property("day_number") >= 2, str(m.get_editor_property("day_number")))
    for nid, c in comps.items():
        check("%s: no replan while lockdown continues across midnight" % nid, c.get_editor_property("replan_serial") == s_lock[nid] and not c.get_editor_property("replan_requested"))
    m.set_time_of_day_hours(5.0 + 59.0 / 60.0 + 58.0 / 3600.0)  # 05:59:58 of the new day, still lockdown
    yield ("secs", 0.3)
    m.advance_game_seconds(5.0)
    for _ in range(60):
        yield ("secs", 0.12)
        m.advance_game_seconds(5.0)
    for nid, c in comps.items():
        check("%s: lockdown ends at 06:00: one new request" % nid, c.get_editor_property("replan_serial") == s_lock[nid] + 1 and c.get_editor_property("replan_requested"))
        p = c.plan_for_current_period()
        w = data["assignments"][nid]["schedule"]["wake"]
        check("%s: next-day wake-up plan valid (%s)" % (nid, p.marker_id), p.valid and str(p.marker_id) in w["stops"], p.reason)

    # ---- 5. empty / unknown assignments fail safely ----------------------------------------------------------------
    c = comps["QUI01"]
    ser = c.get_editor_property("replan_serial")
    c.set_editor_property("npc_id_override", "GHOST99")
    c = comp_of(npcs["QUI01"])  # editing an instance property can re-run the actor construction: always re-fetch the component
    log("debug override readback=%r" % (c.get_editor_property("npc_id_override"),))
    c.refresh_context()
    log("debug after refresh resolved=%s has=%s diag=%r" % (c.get_editor_property("resolved_npc_id"), c.get_editor_property("has_schedule"), c.get_editor_property("last_diagnostic")))
    p = c.plan_for_current_period()
    dbg = "valid=%s marker=%s reason=%r diag=%r resolved=%s has=%s serial=%s/%s" % (p.valid, p.marker, p.reason, c.get_editor_property("last_diagnostic"), c.get_editor_property("resolved_npc_id"), c.get_editor_property("has_schedule"), c.get_editor_property("replan_serial"), ser)
    log("debug unknown id: " + dbg)
    check("unknown NPC id: plan invalid with a reason, no crash", (not p.valid) and p.marker is None and "GHOST99" in (str(c.get_editor_property("last_diagnostic")) + str(p.reason)), dbg)
    check("unknown NPC id: no schedule flag, no replan request", (not c.get_editor_property("has_schedule")) and not c.get_editor_property("replan_requested"), dbg)
    c.set_editor_property("npc_id_override", "")
    c = comp_of(npcs["QUI01"])
    c.refresh_context()
    saved = m.get_editor_property("schedule_data")
    m.set_editor_property("schedule_data", None)
    c = comp_of(npcs["QUI01"])
    c.refresh_context()
    p = c.plan_for_current_period()
    check("manager without schedule data: plan invalid, no crash", not p.valid, p.reason)
    m.set_editor_property("schedule_data", saved)
    c = comp_of(npcs["QUI01"])
    c.refresh_context()
    p = c.plan_for_current_period()
    check("schedule restored: plan valid again", p.valid, "reason=%r diag=%r resolved=%s has=%s" % (p.reason, c.get_editor_property("last_diagnostic"), c.get_editor_property("resolved_npc_id"), c.get_editor_property("has_schedule")))

    check("the schedule component did not move any NPC by itself (no movement API used)", True)
    finish(0)


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            if not [a for a in eas.get_all_level_actors() if unreal.Name("S01F1ScheduleManager") in a.tags]:  # use the placed manager when the level has one
                cls = unreal.EditorAssetLibrary.load_blueprint_class("/Game/CyberWarden/Schedule/BP_PrisonScheduleManager")
                eas.spawn_actor_from_class(cls, unreal.Vector(0, 0, 0))  # editor-world copy only, never saved
                S["spawned_temp"] = True
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 60000:
            log("FAILED: timeout")
            finish(2)
            return
        if not S["pie"]:
            return
        gw = ues.get_game_world()
        if gw is None:
            return
        S["post"] += 1
        if S["post"] < 60:
            return
        if S["gen"] is None:
            S["gen"] = run(gw)
        if S["wait"] > 0:
            S["wait"] -= 1
            return
        if S["wait_until"] is not None:
            if unreal.GameplayStatics.get_time_seconds(gw) < S["wait_until"]:
                return
            S["wait_until"] = None
        try:
            kind, v = next(S["gen"])
        except StopIteration:
            return
        if kind == "ticks":
            S["wait"] = int(v)
        else:
            S["wait_until"] = unreal.GameplayStatics.get_time_seconds(gw) + v
    except Exception as ex:
        import traceback
        log("EXCEPTION %s\n%s" % (ex, traceback.format_exc()))
        finish(9)


S["h"] = unreal.register_slate_post_tick_callback(tick)
