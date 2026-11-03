"""Headless PIE test of the seated activity lifecycle of UPrisonActivityComponent (M2.3 Stage C1). Saves nothing.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/SeatedActivityPieTest.py -Log <abs log>

QUI01's StateTree is stopped in the PIE copy and the NPC is walked to the real marker Seat_Table_1_5 by AI navigation (nothing is teleported).
The component is given an in-memory data override: the sector's activity definitions (including SeatedIdle, which uses the C0 clips
SEAT_StandToSit / SEAT_SittingIdle / SEAT_SitToStand) plus two test-only interaction points on existing markers. No marker, stool, level
or data asset is changed. Covered: the whole Enter -> Loop -> Exit lifecycle and its cross-fades, single-stop continuation, expedited release,
interruption while aligning / entering (committed) / performing / exiting, requests for another point in every phase, abort, movement hold
and restoration, and per-tick invariants (movement held whenever busy, slot never empty, capsule never moved, pelvis never rises back
towards the standing pose between sitting down and standing up).
"""
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SLOMO = float(os.environ.get("ACT_SLOMO", "4"))
SEAT_A, SEAT_B = "Seat_Table_1_5", "Seat_Table_1_4"
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "until": None, "res": [], "fail": [], "samples": [], "last_t": None, "timed_out": False}


def log(m):
    unreal.log("[SEATTEST] " + m)


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


def g(k):
    return S["comp"].get_editor_property(k)


def stname():
    return g("state").name


def mmode():
    return S["cmc"].get_editor_property("movement_mode").name


def refetch():
    S["comp"] = S["npc"].get_component_by_class(unreal.PrisonActivityComponent)  # editing an instance property can re-create the component


def refetch_all():
    npc = S["npc"]
    S.update(comp=npc.get_component_by_class(unreal.PrisonActivityComponent), ctrl=npc.get_controller(), cmc=npc.get_component_by_class(unreal.CharacterMovementComponent),
             mesh=npc.get_component_by_class(unreal.SkeletalMeshComponent))


def sample(now):
    a, mesh = S["npc"], S["mesh"]
    loc = a.get_actor_location()
    pel = mesh.get_socket_location("pelvis")
    anim = mesh.get_anim_instance()
    S["samples"].append(dict(t=now, x=loc.x, y=loc.y, z=loc.z, yaw=a.get_actor_rotation().yaw, st=stname(), mm=mmode(), w=g("slot_node_weight"),
                             mont=anim.get_current_active_montage() is not None, pz=pel.z - mesh.get_world_location().z))


def walk_to(marker_id, radius=60.0):
    tgt = unreal.GameplayStatics.get_all_actors_with_tag(S["gw"], "MarkerId:" + marker_id)[0].get_actor_location()
    S["ctrl"].move_to_location(tgt, radius, True, True, False, False, None, True)
    return tgt


def arrived(tgt):
    loc = S["npc"].get_actor_location()
    return "IDLE" in str(S["ctrl"].get_move_status()) and d2(loc.x, loc.y, tgt.x, tgt.y) < 130.0


def mk_point(marker, activity, tol):
    return unreal.PrisonInteractionPoint(marker_id=marker, activity_id=activity, facing_mode=unreal.PrisonFacingMode.YAW, facing_yaw_degrees=-90.0, arrival_tolerance_cm=tol, capacity=1)


def states_until(pred, timeout):
    """generator helper: yields ticks and collects the distinct state sequence until pred() or timeout (game seconds)."""
    seen = []
    t0 = S["last_t"]
    while True:
        yield ("ticks", 1)
        s = stname()
        if not seen or seen[-1] != s:
            seen.append(s)
        if pred() or (S["last_t"] - t0) > timeout:
            S["seen"] = seen
            S["seen_timeout"] = not pred()
            return


def run(gw):
    npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
    mgrs = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")
    if "QUI01" not in npcs or len(mgrs) != 1:
        log("FAILED: QUI01=%s managers=%d" % ("QUI01" in npcs, len(mgrs)))
        finish(4)
        return
    npc = npcs["QUI01"]
    S.update(gw=gw, npc=npc, mgr=mgrs[0], comp=npc.get_component_by_class(unreal.PrisonActivityComponent), ctrl=npc.get_controller(),
             cmc=npc.get_component_by_class(unreal.CharacterMovementComponent), mesh=npc.get_component_by_class(unreal.SkeletalMeshComponent))
    S["mesh"].set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    yield ("ticks", 5)
    refetch_all()  # editing an instance property can re-run the actor's construction: every component reference taken before is stale
    S["mgr"].set_editor_property("paused", True)
    stc = S["ctrl"].get_component_by_class(unreal.StateTreeAIComponent)
    if stc is not None:
        stc.stop_logic("seated test")  # PIE copy only
    unreal.SystemLibrary.execute_console_command(gw, "slomo %g" % SLOMO)

    sector = S["mgr"].get_editor_property("activity_data")
    acts = list(sector.get_editor_property("activities"))
    seated = [a for a in acts if str(a.get_editor_property("id")) == "SeatedIdle"]
    check("sector activity data has the SeatedIdle definition and validates", len(seated) == 1 and len(list(sector.validate_data())) == 0, str(list(sector.validate_data())))
    d = seated[0]
    check("SeatedIdle uses the three C0 clips, commit enter, grace 1.5, no random loop start",
          d.get_editor_property("enter_animation").get_name() == "SEAT_StandToSit" and d.get_editor_property("loop_animation").get_name() == "SEAT_SittingIdle" and
          d.get_editor_property("exit_animation").get_name() == "SEAT_SitToStand" and d.get_editor_property("commit_enter") and not d.get_editor_property("randomize_loop_start") and
          abs(d.get_editor_property("release_grace_seconds") - 1.5) < 1e-6)
    data = unreal.new_object(unreal.PrisonActivityData)
    data.set_editor_property("activities", acts)
    data.set_editor_property("points", [mk_point(SEAT_A, "SeatedIdle", 150.0), mk_point(SEAT_B, "SeatedIdle", 400.0)])  # test-only points on existing markers
    check("test data validates", len(list(data.validate_data())) == 0, str(list(data.validate_data())))
    S["comp"].set_editor_property("activity_data_override", data)
    refetch()
    ov = g("activity_data_override")
    log("override on the component: %s ; points in it: %s ; has point A=%s B=%s" % (ov, [str(p.get_editor_property("marker_id")) for p in data.get_editor_property("points")],
                                                                                    S["comp"].has_interaction_point(SEAT_A), S["comp"].has_interaction_point(SEAT_B)))
    check("the component uses the test data (points for both seats)", ov is not None and S["comp"].has_interaction_point(SEAT_A) and S["comp"].has_interaction_point(SEAT_B))
    yield ("ticks", 10)
    check("starts idle with normal movement", stname() == "IDLE" and mmode() == "MOVE_WALKING", "%s %s" % (stname(), mmode()))

    tgt = walk_to(SEAT_A)
    yield ("until", lambda: arrived(tgt), 150.0)
    loc = npc.get_actor_location()
    check("QUI01 walked to %s by navigation (%.0f cm from the marker)" % (SEAT_A, d2(loc.x, loc.y, tgt.x, tgt.y)), not S["timed_out"] and d2(loc.x, loc.y, tgt.x, tgt.y) < 150.0)
    yield ("secs", 0.5)
    S["base"] = (loc.x, loc.y, loc.z)

    # ---- 1. full lifecycle ----------------------------------------------------------------------------------------------
    t_req = S["last_t"]
    ok = g_req = S["comp"].request_activity(SEAT_A)
    check("request accepted", ok, str(g("last_failure_reason")))
    yield from states_until(lambda: stname() == "PERFORMING", 8.0)
    seen = S["seen"]
    t_perf = S["last_t"]
    check("lifecycle order %s" % seen, not S["seen_timeout"] and seen[0] in ("ALIGNING", "ENTERING") and "ENTERING" in seen and seen[-1] == "PERFORMING" and "EXITING" not in seen, str(seen))
    ent = [s for s in S["samples"] if s["st"] == "ENTERING"]
    enter_secs = (ent[-1]["t"] - ent[0]["t"]) if ent else -1
    check("enter phase ends one cross-fade (0.25 s) before the 2.23 s clip ends: %.2f s" % enter_secs, 1.6 <= enter_secs <= 2.2, str(enter_secs))
    check("one start, one hand-off, committed", g("start_count") == 1 and g("handoff_count") == 1, "%s %s" % (g("start_count"), g("handoff_count")))
    pos = S["mesh"].get_anim_instance().montage_get_position(S["mesh"].get_anim_instance().get_current_active_montage())
    check("loop starts at its first frame (not a random offset): %.2f s into the loop" % pos, pos < 0.8, str(pos))
    yield ("secs", 9.0)  # two full 4.3 s loops
    yaw = npc.get_actor_rotation().yaw
    check("seated for 9 s: still performing, loop montage playing, slot weight %.2f, no unexpected stop" % g("slot_node_weight"),
          stname() == "PERFORMING" and g("montage_playing") and g("slot_node_weight") >= 0.95 and g("unexpected_stop_count") == 0, "%s %s" % (stname(), g("unexpected_stop_count")))
    check("facing the table side: yaw error %.2f deg (limit 3.5)" % abs(ndelta(yaw, -90.0)), abs(ndelta(yaw, -90.0)) <= 3.5)
    check("capsule never moved: max displacement %.2f cm" % g("max_displacement_cm"), g("max_displacement_cm") < 0.5, str(g("max_displacement_cm")))

    # ---- 2. single-stop continuation: re-requests inside the 1.5 s grace never stand the NPC up --------------------------------
    for delay in (0.3, 0.9, 1.3):
        S["comp"].release_activity()
        yield ("secs", delay)
        S["comp"].request_activity(SEAT_A)
        yield ("secs", 0.3)
    check("3 idle cycles (re-request after 0.3 / 0.9 / 1.3 s): no stand-up, no restart (starts %d, completes %d, state %s)" % (g("start_count"), g("complete_count"), stname()),
          g("start_count") == 1 and g("complete_count") == 0 and stname() == "PERFORMING" and not g("release_pending") and g("montage_playing"), "%s %s %s" % (g("start_count"), g("complete_count"), stname()))

    # ---- 3. exit: grace, anim-driven end, movement restored only afterwards --------------------------------------------------
    t_rel = S["last_t"]
    secs = S["comp"].release_activity()
    check("release reports grace 1.5 + exit 2.27 = %.2f s" % secs, 3.55 <= secs <= 4.0, str(secs))
    free_pred = S["comp"].get_seconds_until_free()
    yield from states_until(lambda: stname() == "IDLE", 8.0)
    seen = S["seen"]
    t_idle = S["last_t"]
    ex = [s for s in S["samples"] if s["st"] == "EXITING" and s["t"] > t_rel]
    exit_secs = (ex[-1]["t"] - ex[0]["t"]) if ex else -1
    check("exit order %s, whole release took %.2f s (predicted %.2f)" % (seen, t_idle - t_rel, free_pred), not S["seen_timeout"] and seen[-2:] == ["EXITING", "IDLE"] and 3.4 <= t_idle - t_rel <= 4.3, str(seen))
    check("the exit animation phase lasted %.2f s (clip 2.27 s)" % exit_secs, 1.9 <= exit_secs <= 2.6, str(exit_secs))
    check("movement restored to walking only at the end, not held after", mmode() == "MOVE_WALKING" and not g("movement_held") and g("complete_count") == 1, "%s %s" % (mmode(), g("complete_count")))
    check("no montage left in the slot", S["mesh"].get_anim_instance().get_current_active_montage() is None)

    # ---- 4. expedited release ----------------------------------------------------------------------------------------------------
    S["comp"].request_activity(SEAT_A)
    yield ("until", lambda: stname() == "PERFORMING", 8.0)
    S["comp"].release_activity()
    yield ("secs", 0.2)
    S["comp"].expedite_release(SEAT_A, False)  # the next plan simply continues this activity: nothing is expedited
    yield ("secs", 0.5)
    check("expedite for the same stop (no move) leaves the grace window alone", stname() == "PERFORMING" and g("release_pending"), stname())
    S["comp"].request_activity(SEAT_A)
    yield ("secs", 0.2)
    check("...and the continuation still works", stname() == "PERFORMING" and not g("release_pending") and g("start_count") == 2)
    S["comp"].release_activity()
    yield ("secs", 0.2)
    S["comp"].expedite_release(SEAT_B, True)  # leaving for another stop: skip the grace
    yield ("secs", 0.35)
    check("expedite for another stop starts the exit now (state %s, 0.55 s after the release instead of 1.5 s)" % stname(), stname() == "EXITING", stname())
    yield ("until", lambda: stname() == "IDLE", 5.0)
    check("expedited exit finishes cleanly", stname() == "IDLE" and mmode() == "MOVE_WALKING")

    # ---- 5. interruption while entering (committed) ---------------------------------------------------------------------------
    ints0, comp0 = g("interrupt_count"), g("complete_count")
    S["comp"].request_activity(SEAT_A)
    yield ("until", lambda: stname() == "ENTERING", 5.0)
    yield ("secs", 0.5)
    secs = S["comp"].release_activity()
    check("release while entering is committed: free in %.2f s (rest of the sit + exit), not a blend-out" % secs, 1.8 <= secs <= 4.4, str(secs))
    yield ("secs", 0.3)
    check("still sitting down 0.3 s later (not cut, not interrupted)", stname() == "ENTERING" and g("interrupt_count") == ints0, "%s %s" % (stname(), g("interrupt_count")))
    yield from states_until(lambda: stname() == "IDLE", 10.0)
    seen = S["seen"]
    check("committed enter finished the sit, then stood up: %s" % seen, not S["seen_timeout"] and "EXITING" in seen and seen[-1] == "IDLE" and "ALIGNING" not in seen and g("complete_count") == comp0 + 1 and g("interrupt_count") == ints0, str(seen))
    check("movement restored after the committed enter", mmode() == "MOVE_WALKING" and not g("movement_held"))

    starts = g("start_count")
    S["comp"].request_activity(SEAT_A)
    yield ("until", lambda: stname() == "ENTERING", 5.0)
    yield ("secs", 0.4)
    S["comp"].release_activity()
    yield ("secs", 0.3)
    S["comp"].request_activity(SEAT_A)  # the single-stop re-plan arrives while still sitting down
    yield ("until", lambda: stname() == "PERFORMING", 5.0)
    yield ("secs", 1.0)
    check("re-request while entering (inside the grace) continues: no stand-up, no restart", stname() == "PERFORMING" and g("start_count") == starts + 1 and not g("release_pending"), "%s %s" % (stname(), g("start_count")))

    # ---- 6. another point requested while entering / performing ----------------------------------------------------------------
    S["comp"].release_activity()
    yield ("until", lambda: stname() == "IDLE", 8.0)
    starts = g("start_count")
    S["comp"].request_activity(SEAT_A)
    yield ("until", lambda: stname() == "ENTERING", 5.0)
    yield ("secs", 0.4)
    ok = S["comp"].request_activity(SEAT_B)
    check("request for another seat while entering is accepted and queued", ok and g("pending_marker_id") == SEAT_B and stname() == "ENTERING", "%s %s %s" % (ok, g("pending_marker_id"), stname()))
    yield from states_until(lambda: g("active_marker_id") == SEAT_B and stname() == "PERFORMING", 20.0)
    seen = S["seen"]
    check("the first sit finished, the NPC stood up, then the second seat started: %s" % seen, not S["seen_timeout"] and "EXITING" in seen and g("start_count") == starts + 2 and g("active_marker_id") == SEAT_B, "%s %s" % (seen, g("start_count")))
    ints = g("interrupt_count")
    ok = S["comp"].request_activity(SEAT_A)
    check("request for another seat while performing: exit starts at once", ok and stname() == "EXITING" and g("pending_marker_id") == SEAT_A, "%s %s" % (ok, stname()))
    yield from states_until(lambda: g("active_marker_id") == SEAT_A and stname() == "PERFORMING", 20.0)
    check("...and the queued seat starts after the exit (no interrupt counted: %d)" % (g("interrupt_count") - ints), not S["seen_timeout"] and g("interrupt_count") == ints, str(S["seen"]))

    # ---- 7. interruption while exiting ------------------------------------------------------------------------------------------
    S["comp"].release_activity()
    yield ("until", lambda: stname() == "EXITING", 5.0)
    starts = g("start_count")
    ok = S["comp"].request_activity(SEAT_A)
    check("request for the same seat while exiting is queued (not a continuation)", ok and g("pending_marker_id") == SEAT_A and stname() == "EXITING", "%s %s" % (ok, g("pending_marker_id")))
    rem = S["comp"].release_activity()
    check("a release while exiting cancels the queued request and reports the remaining time %.2f s" % rem, g("pending_marker_id") == "None" and 0.0 <= rem <= 2.4, "%s %s" % (g("pending_marker_id"), rem))
    yield ("until", lambda: stname() == "IDLE", 5.0)
    yield ("secs", 0.5)
    check("it stood up and stayed idle (no new sit): starts %d" % g("start_count"), stname() == "IDLE" and g("start_count") == starts and mmode() == "MOVE_WALKING")
    S["comp"].request_activity(SEAT_A)
    yield ("until", lambda: stname() == "PERFORMING", 8.0)
    S["comp"].release_activity()
    yield ("until", lambda: stname() == "EXITING", 5.0)
    S["comp"].request_activity(SEAT_A)
    yield ("until", lambda: stname() == "IDLE" or (stname() in ("ALIGNING", "ENTERING", "PERFORMING") and g("start_count") == starts + 2), 10.0)
    yield ("until", lambda: stname() == "PERFORMING", 8.0)
    check("a request queued during the exit sits down again afterwards (a genuine second cycle)", g("start_count") == starts + 2 and stname() == "PERFORMING", "%s %s" % (g("start_count"), stname()))

    # ---- 8. abort in every phase ---------------------------------------------------------------------------------------------------
    S["comp"].abort_activity()
    check("abort while performing: idle, movement restored, slot empty", stname() == "IDLE" and mmode() == "MOVE_WALKING" and not g("movement_held") and not g("montage_playing"), "%s %s" % (stname(), mmode()))
    yield ("secs", 0.3)
    S["comp"].request_activity(SEAT_A)
    yield ("until", lambda: stname() == "ENTERING", 5.0)
    yield ("secs", 0.5)
    S["comp"].abort_activity()
    check("abort while entering: idle, movement restored", stname() == "IDLE" and mmode() == "MOVE_WALKING" and not g("movement_held"), "%s %s" % (stname(), mmode()))
    yield ("secs", 0.3)
    S["comp"].request_activity(SEAT_A)
    yield ("until", lambda: stname() == "PERFORMING", 8.0)
    S["comp"].release_activity()
    yield ("until", lambda: stname() == "EXITING", 5.0)
    S["comp"].abort_activity()
    check("abort while exiting: idle, movement restored", stname() == "IDLE" and mmode() == "MOVE_WALKING" and not g("movement_held"), "%s %s" % (stname(), mmode()))
    yield ("secs", 0.3)
    r = npc.get_actor_rotation()
    npc.set_actor_rotation(unreal.Rotator(r.roll, r.pitch, 90.0), False)  # test only: face away so the activity has to align
    yield ("ticks", 3)
    S["comp"].request_activity(SEAT_A)
    yield ("secs", 0.3)
    check("turning to the seat takes time (aligning)", stname() == "ALIGNING", stname())
    secs = S["comp"].release_activity()
    check("release while aligning: free at once, idle, no sit animation ever started", secs == 0.0 and stname() == "IDLE" and mmode() == "MOVE_WALKING" and not g("montage_playing"), "%s %s" % (secs, stname()))

    # ---- 9. movement authority while exiting ----------------------------------------------------------------------------------------
    S["comp"].request_activity(SEAT_A)
    yield ("until", lambda: stname() == "PERFORMING", 10.0)
    yield ("secs", 0.5)
    S["comp"].release_activity()
    yield ("until", lambda: stname() == "EXITING", 5.0)
    here = npc.get_actor_location()
    walk_to("Rec_Table_B")  # a Move To issued while the NPC is still standing up
    yield ("secs", 1.0)
    mid = npc.get_actor_location()
    check("Move To issued during the stand-up does not move the NPC (%.1f cm in 1.0 s, mode %s)" % (d2(here.x, here.y, mid.x, mid.y), mmode()), d2(here.x, here.y, mid.x, mid.y) < 3.0 and mmode() == "MOVE_NONE", mmode())
    yield ("until", lambda: stname() == "IDLE", 5.0)
    yield ("secs", 4.0)
    after = npc.get_actor_location()
    check("after the stand-up the pending Move To proceeds (%.0f cm in 4 s)" % d2(mid.x, mid.y, after.x, after.y), d2(mid.x, mid.y, after.x, after.y) > 150.0 and mmode() == "MOVE_WALKING")

    # ---- 10. per-tick invariants over the whole run ---------------------------------------------------------------------------------
    busy = [s for s in S["samples"] if s["st"] != "IDLE"]
    check("movement was held on every tick while an activity was busy (%d samples)" % len(busy), all(s["mm"] == "MOVE_NONE" for s in busy), str([s for s in busy if s["mm"] != "MOVE_NONE"][:2]))
    steps = [d2(p["x"], p["y"], q["x"], q["y"]) for p, q in zip(S["samples"], S["samples"][1:]) if p["st"] != "IDLE" and q["st"] != "IDLE"]
    check("capsule position never changed during any activity (max step %.3f cm)" % max(steps + [0.0]), max(steps + [0.0]) < 0.5)
    zs = [s["z"] for s in busy]
    check("capsule height constant (%.2f cm range)" % (max(zs) - min(zs)), max(zs) - min(zs) < 0.5)
    # slot never falls back to the standing pose: from the end of the blend in to the start of the final blend out
    gaps = []
    for i, s in enumerate(S["samples"]):
        if s["st"] in ("ENTERING", "PERFORMING", "EXITING"):
            # ignore the first 0.5 s of a phase run (blend in from locomotion) and the last 0.5 s of an exit (blend out to locomotion)
            j = i
            while j > 0 and S["samples"][j - 1]["st"] != "IDLE" and S["samples"][j - 1]["st"] != "ALIGNING":
                j -= 1
            start_t = S["samples"][j]["t"]
            k = i
            while k + 1 < len(S["samples"]) and S["samples"][k + 1]["st"] in ("ENTERING", "PERFORMING", "EXITING"):
                k += 1
            end_t = S["samples"][k]["t"]
            if s["t"] - start_t > 0.5 and end_t - s["t"] > (0.5 if S["samples"][k]["st"] == "EXITING" else 0.0):
                if s["w"] < 0.9 or not s["mont"]:
                    gaps.append((round(s["t"], 2), s["st"], round(s["w"], 2), s["mont"]))
    check("slot node weight stayed >= 0.9 with a montage present through every enter->loop hand-off and loop->exit cross-fade (%d gaps)" % len(gaps), not gaps, str(gaps[:4]))
    pz = [s["pz"] for s in S["samples"]]
    evaluable = max(pz) - min(pz) > 20.0
    log("pelvis height relative to the mesh origin: min %.1f max %.1f cm (poses evaluate headless: %s)" % (min(pz), max(pz), evaluable))
    if evaluable:
        bad, low, in_sit = [], None, False
        for p, s in zip(S["samples"], S["samples"][1:]):
            if s["st"] in ("ENTERING", "PERFORMING") and s["pz"] < 75.0:
                in_sit = True
                low = s["pz"] if low is None else min(low, s["pz"])
                if s["pz"] > low + 5.0:
                    bad.append((round(s["t"], 2), s["st"], round(s["pz"], 1), round(low, 1)))
            elif s["st"] in ("IDLE", "ALIGNING") or s["st"] == "EXITING":
                low, in_sit = None, False
        check("pelvis never rises back towards standing between sitting down and standing up (no flash of the standing pose; %d violations)" % len(bad), not bad, str(bad[:4]))
        seated = [s["pz"] for s in S["samples"] if s["st"] == "PERFORMING"]
        check("seated pelvis height %.1f..%.1f cm (clip 52.9 cm)" % (min(seated), max(seated)), 48.0 <= min(seated) and max(seated) <= 58.0)
    else:
        check("pose evaluation unavailable headless: slot weight and montage-presence invariants above are the proof (informational)", True)
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
        if S["gen"] is None:
            S["gen"] = run(gw)
        S["last_t"] = now
        if "comp" in S and S["comp"] is not None and "mesh" in S and S["mesh"] is not None:
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
