"""Headless PIE test of the final approach of UPrisonActivityComponent (M2.3 Stage C2). Saves nothing.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/ActivityApproachPieTest.py -Log <abs log>

QUI01's StateTree is stopped in the PIE copy and the NPC is walked by AI navigation (nothing is teleported) to a point about 40-47 cm from the real marker
Seat_Table_1_5, exactly where the routine's Move To (radius 10, stop on overlap) leaves it. Then the component is driven directly. The regenerated data asset
is read first (only the prototype seat has the final approach); afterwards the component gets an in-memory data override holding a COPY of the real seat
point plus two test-only points on existing markers (Seat_Table_1_4: final approach with a 0.05 s timeout, for the failure and lockout checks;
Seat_Table_1_6: an ordinary point, as "another interaction point"). No marker, stool, level or data asset is changed.

Covered: the approach starts at the right moment (movement not held, no activity yet), uses normal AI navigation (move status MOVING, walking speed, no
teleport), the activity starts only after the position is confirmed within the point's tolerance (7 cm for the prototype seat), an NPC already within tolerance does not walk, too-far requests are
refused without a lockout, a timed-out approach leaves the NPC standing and is locked out for 120 s (refused at +5 / +60 / +119 s, allowed again after),
and a release / abort / request for another point / competing move request cancels the approach safely without a failure and without touching the
competing request.
"""
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SLOMO = float(os.environ.get("ACT_SLOMO", "2"))
SEAT, SEAT_B, SEAT_C = "Seat_Table_1_5", "Seat_Table_1_4", "Seat_Table_1_6"
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "until": None, "res": [], "fail": [], "samples": [], "last_t": None, "timed_out": False}


def log(m):
    unreal.log("[APPRTEST] " + m)


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


def refetch_all():
    npc = S["npc"]
    S.update(comp=npc.get_component_by_class(unreal.PrisonActivityComponent), ctrl=npc.get_controller(), cmc=npc.get_component_by_class(unreal.CharacterMovementComponent),
             mesh=npc.get_component_by_class(unreal.SkeletalMeshComponent))


def mloc(mid):
    return unreal.GameplayStatics.get_all_actors_with_tag(S["gw"], "MarkerId:" + mid)[0].get_actor_location()


def here():
    l = S["npc"].get_actor_location()
    return l.x, l.y


def dist_to(mid):
    m = mloc(mid)
    x, y = here()
    return d2(x, y, m.x, m.y)


def sample(now):
    a, mesh = S["npc"], S["mesh"]
    loc = a.get_actor_location()
    pel = mesh.get_socket_location("pelvis")
    anim = mesh.get_anim_instance()
    S["samples"].append(dict(t=now, x=loc.x, y=loc.y, yaw=a.get_actor_rotation().yaw, st=stname(), mm=mmode(), w=g("slot_node_weight"), sc=g("start_count"),
                             mont=anim.get_current_active_montage() is not None, pz=pel.z - mesh.get_world_location().z, ms=str(S["ctrl"].get_move_status())))


def go(mid, radius):
    S["ctrl"].move_to_location(mloc(mid), radius, True, True, True, False, None, True)  # same shape as the routine's Move To: stop on overlap, pathfinding


def settled(mid, within):
    return "IDLE" in str(S["ctrl"].get_move_status()) and dist_to(mid) < within


def states_until(pred, timeout):
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


def stand_near(via, target, radius):
    """Walk to marker `via` (so the final leg comes from a known side), then Move To `target` with `radius`: leaves the NPC radius + capsule out, like the routine."""
    go(via, 30.0)
    yield ("until", lambda: settled(via, 150.0), 120.0)
    yield ("secs", 0.4)
    go(target, radius)
    yield ("until", lambda: settled(target, 130.0), 60.0)
    yield ("secs", 0.6)


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
    refetch_all()
    S["mgr"].set_editor_property("paused", True)
    stc = S["ctrl"].get_component_by_class(unreal.StateTreeAIComponent)
    if stc is not None:
        stc.stop_logic("approach test")  # PIE copy only
    unreal.SystemLibrary.execute_console_command(gw, "slomo %g" % SLOMO)
    max_walk = float(S["cmc"].get_editor_property("max_walk_speed"))
    log("QUI01 max walk speed %.0f cm/s; marker %s at (%.0f, %.0f)" % (max_walk, SEAT, mloc(SEAT).x, mloc(SEAT).y))

    # ---- 0. the regenerated data asset ------------------------------------------------------------------------------------------------------------
    sector = S["mgr"].get_editor_property("activity_data")
    check("the component resolves the sector's regenerated data (no override) and knows the seat point", g("activity_data_override") is None and S["comp"].has_interaction_point(SEAT))
    pts = {str(p.get_editor_property("marker_id")): p for p in sector.get_editor_property("points")}
    real = pts[SEAT]
    fa = [(k, bool(p.get_editor_property("final_approach"))) for k, p in pts.items()]
    check("final approach is enabled only on the designated prototype seat: %s" % fa, [k for k, v in fa if v] == [SEAT], str(fa))
    check("seat point values: accept 1, tolerance 7, max 80, timeout 3, arrival tolerance 60, yaw -90, capacity 1",
          real.get_editor_property("final_approach_accept_cm") == 1.0 and real.get_editor_property("final_approach_tolerance_cm") == 7.0 and
          real.get_editor_property("final_approach_max_distance_cm") == 80.0 and real.get_editor_property("final_approach_timeout_seconds") == 3.0 and
          real.get_editor_property("arrival_tolerance_cm") == 60.0 and real.get_editor_property("facing_yaw_degrees") == -90.0 and real.get_editor_property("capacity") == 1)
    check("the component's retry lockout defaults to 120 s", abs(g("approach_retry_lockout_seconds") - 120.0) < 1e-6, str(g("approach_retry_lockout_seconds")))
    rad = S["comp"].get_move_acceptable_radius(SEAT, 60.0)
    check("Move To radius for the seat is its 10 cm floor (%.0f cm)" % rad, rad == 10.0)

    acts = list(sector.get_editor_property("activities"))
    data = unreal.new_object(unreal.PrisonActivityData)
    data.set_editor_property("activities", acts)
    fast = unreal.PrisonInteractionPoint(marker_id=SEAT_B, activity_id="SeatedIdle", facing_mode=unreal.PrisonFacingMode.YAW, facing_yaw_degrees=-90.0, arrival_tolerance_cm=60.0, capacity=1,
                                         final_approach=True, final_approach_accept_cm=3.0, final_approach_tolerance_cm=5.0, final_approach_max_distance_cm=80.0, final_approach_timeout_seconds=0.05)
    plain = unreal.PrisonInteractionPoint(marker_id=SEAT_C, activity_id="SeatedIdle", facing_mode=unreal.PrisonFacingMode.YAW, facing_yaw_degrees=-90.0, arrival_tolerance_cm=400.0, capacity=1)
    data.set_editor_property("points", [real, fast, plain])
    check("test data (copy of the real seat point + 2 test-only points) validates", len(list(data.validate_data())) == 0, str(list(data.validate_data())))
    S["comp"].set_editor_property("activity_data_override", data)
    refetch_all()  # editing an instance property can re-create the component
    check("the component uses the test data", g("activity_data_override") is not None and S["comp"].has_interaction_point(SEAT_B) and S["comp"].has_interaction_point(SEAT_C))
    yield ("ticks", 10)
    check("starts idle, walking, all approach counters zero", stname() == "IDLE" and mmode() == "MOVE_WALKING" and g("approach_start_count") == 0 and g("approach_fail_count") == 0 and g("approach_cancel_count") == 0)

    # ---- 1. a real approach from where Move To leaves the NPC -------------------------------------------------------------------------------------
    yield from stand_near(SEAT_B, SEAT, 10.0)
    start_d = dist_to(SEAT)
    start_xy = here()
    check("Move To (radius 10) leaves QUI01 %.1f cm from the marker (expected 40-47; the final approach is allowed 80)" % start_d, 25.0 <= start_d <= 80.0, str(start_d))
    check("idle and holding no movement before the request", stname() == "IDLE" and mmode() == "MOVE_WALKING")
    i0 = len(S["samples"])
    ok = S["comp"].request_activity(SEAT)
    check("the request is accepted", ok, str(g("last_failure_reason")))
    check("the final approach begins at the request: state APPROACHING, 1 approach started, activity not yet started", stname() == "APPROACHING" and g("approach_start_count") == 1 and g("start_count") == 0, "%s %s %s" % (stname(), g("approach_start_count"), g("start_count")))
    check("movement is NOT held during the approach (normal walking)", mmode() == "MOVE_WALKING" and not g("movement_held"), "%s %s" % (mmode(), g("movement_held")))
    yield from states_until(lambda: stname() in ("PERFORMING", "IDLE"), 10.0)
    seen = S["seen"]
    smp = S["samples"][i0:]
    appr = [s for s in smp if s["st"] == "APPROACHING"]
    check("lifecycle order %s: APPROACHING first, then the normal seated lifecycle" % seen, not S["seen_timeout"] and seen[0] == "APPROACHING" and seen[-1] == "PERFORMING" and "ALIGNING" in seen and "ENTERING" in seen and seen.index("APPROACHING") < seen.index("ALIGNING") < seen.index("ENTERING") and "EXITING" not in seen, str(seen))
    check("nothing of the seated activity started during the approach (start count 0, no montage, held movement never applied)", all(s["sc"] == 0 and not s["mont"] and s["mm"] != "MOVE_NONE" for s in appr), str(appr[:2]))
    check("the approach used normal AI navigation: path following reported MOVING on %d of %d approach samples" % (sum("MOVING" in s["ms"] for s in appr), len(appr)), len(appr) >= 1 and any("MOVING" in s["ms"] for s in appr))
    first_al = next((s for s in smp if s["st"] in ("ALIGNING", "ENTERING", "PERFORMING")), None)
    m = mloc(SEAT)
    d_first = d2(first_al["x"], first_al["y"], m.x, m.y) if first_al else 999.0
    check("accurate arrival is confirmed BEFORE sitting: %.2f cm from the marker when the activity began (limit 7)" % d_first, d_first <= 7.0, str(d_first))
    check("diagnostics: result 'success', start %.1f cm, end %.2f cm, %.2f s, travelled %.1f cm" % (g("last_approach_start_cm"), g("last_approach_end_cm"), g("last_approach_seconds"), g("last_approach_travel_cm")),
          g("last_approach_result") == "success" and g("approach_success_count") == 1 and g("approach_fail_count") == 0 and g("approach_cancel_count") == 0 and g("last_approach_end_cm") <= 7.0 and 0.0 < g("last_approach_seconds") < 3.0)
    steps = [(d2(p["x"], p["y"], q["x"], q["y"]), q["t"] - p["t"]) for p, q in zip(smp, smp[1:]) if q["t"] > p["t"]]
    vmax = max([s / dt for s, dt in steps] + [0.0])
    check("no teleport or snap: top speed %.0f cm/s (walk speed %.0f), largest step %.1f cm" % (vmax, max_walk, max([s for s, _ in steps] + [0.0])), vmax <= max_walk * 1.35, str(vmax))
    check("the walk was real: travelled %.1f cm in %.2f s" % (g("last_approach_travel_cm"), g("last_approach_seconds")), g("last_approach_travel_cm") > 15.0)
    yield ("secs", 2.0)
    x, y = here()
    yaw = npc.get_actor_rotation().yaw
    check("seated at %.2f cm from the marker, yaw error %.2f deg" % (d2(x, y, m.x, m.y), abs(ndelta(yaw, -90.0))), d2(x, y, m.x, m.y) <= 7.0 and abs(ndelta(yaw, -90.0)) <= 3.5)
    check("seated animation is playing: montage, slot weight %.2f, pelvis %.1f cm" % (g("slot_node_weight"), S["samples"][-1]["pz"]), stname() == "PERFORMING" and g("montage_playing") and g("slot_node_weight") >= 0.95 and S["samples"][-1]["pz"] < 75.0)
    check("capsule did not slide while seated: displacement %.2f cm, movement held" % g("max_displacement_cm"), g("max_displacement_cm") < 0.5 and mmode() == "MOVE_NONE")
    S["row1"] = dict(start=start_xy, start_d=start_d, end=g("last_approach_end_cm"), secs=g("last_approach_seconds"), travel=g("last_approach_travel_cm"))

    # ---- 2. release, then request again from the seat position: no walk needed ("already there") ----------------------------------------------------
    S["comp"].release_activity()
    yield ("until", lambda: stname() == "IDLE", 10.0)
    check("released and stood up; movement restored", stname() == "IDLE" and mmode() == "MOVE_WALKING" and g("complete_count") == 1)
    starts0 = g("approach_start_count")
    ok = S["comp"].request_activity(SEAT)
    yield ("ticks", 3)
    check("standing on the marker: no approach is started ('%s'), the activity starts at once (state %s)" % (g("last_approach_result"), stname()),
          ok and g("approach_start_count") == starts0 and g("last_approach_result") == "already there" and stname() in ("ALIGNING", "ENTERING") and g("start_count") == 2, "%s %s %s" % (ok, g("approach_start_count"), stname()))
    S["comp"].abort_activity()
    yield ("ticks", 3)
    check("abort returns to idle and walking", stname() == "IDLE" and mmode() == "MOVE_WALKING")

    # ---- 3. too far: refused without a walk and without a lockout -----------------------------------------------------------------------------------
    go("Seat_Table_1_1", 30.0)
    yield ("until", lambda: settled("Seat_Table_1_1", 150.0), 120.0)
    yield ("secs", 0.5)
    far = dist_to(SEAT)
    p0, starts0, fails0 = here(), g("approach_start_count"), g("approach_fail_count")
    ok = S["comp"].request_activity(SEAT)
    reason = str(g("last_failure_reason"))
    check("%.0f cm away (> 80): refused, nothing started, standing: '%s'" % (far, reason), (not ok) and "too far" in reason and stname() == "IDLE" and g("approach_start_count") == starts0 and mmode() == "MOVE_WALKING")
    yield ("secs", 0.5)
    p1 = here()
    check("the refused request moved nothing (%.2f cm) and did not count as a failed approach or a lockout" % d2(p0[0], p0[1], p1[0], p1[1]), d2(p0[0], p0[1], p1[0], p1[1]) < 1.0 and g("approach_fail_count") == fails0 and g("approach_lockout_refusals") == 0)

    # ---- 4. cancellation: release during the approach ------------------------------------------------------------------------------------------------
    yield from stand_near(SEAT_B, SEAT, 30.0)  # ~64 cm out: a longer walk, easier to catch mid-way
    d_start = dist_to(SEAT)
    st0, canc0, fail0, sc0 = g("approach_start_count"), g("approach_cancel_count"), g("approach_fail_count"), g("start_count")
    check("setup: %.0f cm from the marker" % d_start, 5.0 < d_start <= 80.0, str(d_start))
    S["comp"].request_activity(SEAT)
    yield ("ticks", 1)
    cont0 = g("continuation_count")
    again = S["comp"].request_activity(SEAT)
    check("a repeated request for the same point during the approach is a continuation (no second walk)", again and g("continuation_count") == cont0 + 1 and g("approach_start_count") == st0 + 1 and stname() == "APPROACHING", "%s %s" % (stname(), g("approach_start_count")))
    r = S["comp"].release_activity()
    check("release during the approach: free at once (%.2f s), state %s, cancelled (not failed), result '%s'" % (r, stname(), g("last_approach_result")),
          r == 0.0 and stname() == "IDLE" and g("approach_cancel_count") == canc0 + 1 and g("approach_fail_count") == fail0 and g("last_approach_result") == "cancelled: released" and g("start_count") == sc0)
    check("movement was never held: walking", mmode() == "MOVE_WALKING" and not g("movement_held"))
    yield ("secs", 0.3)
    pa = here()
    yield ("secs", 1.0)
    pb = here()
    check("the NPC stops where it is: %.2f cm of drift in the next second (its own move request was dropped)" % d2(pa[0], pa[1], pb[0], pb[1]), d2(pa[0], pa[1], pb[0], pb[1]) < 6.0 and "IDLE" in str(S["ctrl"].get_move_status()))
    check("no lockout after a cancel: the same point is accepted again", S["comp"].request_activity(SEAT) and stname() in ("APPROACHING", "ALIGNING"), stname())
    yield ("ticks", 1)

    # ---- 5. cancellation: another interaction point requested during the approach -------------------------------------------------------------------
    canc1 = g("approach_cancel_count")
    sc1 = g("start_count")
    ok = S["comp"].request_activity(SEAT_C)
    check("another point (%s) requested during the approach: accepted, approach cancelled, the new point starts (state %s, active %s)" % (SEAT_C, stname(), g("active_marker_id")),
          ok and g("approach_cancel_count") == canc1 + 1 and "another interaction point" in g("last_approach_result") and str(g("active_marker_id")) == SEAT_C and stname() in ("ALIGNING", "ENTERING") and g("start_count") == sc1 + 1,
          "%s %s %s" % (ok, g("last_approach_result"), g("active_marker_id")))
    S["comp"].abort_activity()
    yield ("ticks", 3)

    # ---- 6. cancellation: abort during the approach ------------------------------------------------------------------------------------------------
    yield from stand_near(SEAT_B, SEAT, 30.0)
    canc2 = g("approach_cancel_count")
    S["comp"].request_activity(SEAT)
    yield ("ticks", 1)
    in_appr = stname() == "APPROACHING"
    S["comp"].abort_activity()
    check("abort during the approach (was approaching: %s): idle, walking, result '%s'" % (in_appr, g("last_approach_result")), in_appr and stname() == "IDLE" and mmode() == "MOVE_WALKING" and g("last_approach_result") == "cancelled: aborted" and g("approach_cancel_count") == canc2 + 1)

    # ---- 7. a competing move request (the routine's Move To) supersedes the approach; the component must not fight it ------------------------------------
    yield from stand_near(SEAT_B, SEAT, 30.0)
    canc3 = g("approach_cancel_count")
    S["comp"].request_activity(SEAT)
    yield ("ticks", 1)
    in_appr = stname() == "APPROACHING"
    go("Seat_Table_1_1", 30.0)  # someone else issues a move request
    yield ("ticks", 3)
    p_c = here()
    check("a competing move request drops the approach (was approaching: %s): state %s, result '%s'" % (in_appr, stname(), g("last_approach_result")),
          in_appr and stname() == "IDLE" and g("approach_cancel_count") == canc3 + 1 and "another move request" in g("last_approach_result") and g("approach_fail_count") == fail0, "%s" % g("last_approach_result"))
    yield ("until", lambda: settled("Seat_Table_1_1", 150.0), 120.0)
    p_d = here()
    check("...and the competing request was NOT aborted by the component: the NPC walked %.0f cm on to it (now %.0f cm from Seat_Table_1_1)" % (d2(p_c[0], p_c[1], p_d[0], p_d[1]), dist_to("Seat_Table_1_1")),
          not S["timed_out"] and d2(p_c[0], p_c[1], p_d[0], p_d[1]) > 100.0)

    # ---- 8. a timed-out approach leaves the NPC standing and the point locked out for 120 s -----------------------------------------------------------
    yield from stand_near(SEAT, SEAT_B, 10.0)
    dB = dist_to(SEAT_B)
    fail1, st1, sc2 = g("approach_fail_count"), g("approach_start_count"), g("start_count")
    pA = here()
    ok = S["comp"].request_activity(SEAT_B)  # 0.05 s timeout: the walk cannot finish
    yield from states_until(lambda: stname() == "IDLE", 5.0)
    t_fail = S["last_t"]
    reason = str(g("last_failure_reason"))
    check("%.0f cm out, 0.05 s timeout: the approach fails and the NPC stays standing (state %s): '%s'" % (dB, stname(), g("last_approach_result")),
          ok and not S["seen_timeout"] and g("approach_fail_count") == fail1 + 1 and str(g("last_approach_result")).startswith("failed: timed out") and "timed out" in reason and g("start_count") == sc2 and mmode() == "MOVE_WALKING" and not g("movement_held"))
    yield ("secs", 1.0)
    pB = here()
    check("standing: no montage, drifted %.1f cm, move request dropped" % d2(pA[0], pA[1], pB[0], pB[1]), not S["samples"][-1]["mont"] and "IDLE" in str(S["ctrl"].get_move_status()) and d2(pA[0], pA[1], pB[0], pB[1]) < 40.0 and S["samples"][-1]["pz"] > 80.0)
    ref0 = g("approach_lockout_refusals")
    for label, wait_until in (("immediately", 0.0), ("+5 s", 5.0), ("+60 s", 60.0), ("+119 s", 119.0)):
        if wait_until:
            tgt_t = t_fail + wait_until
            yield ("until", lambda tt=tgt_t: S["last_t"] >= tt, wait_until + 5.0)
        ok = S["comp"].request_activity(SEAT_B)
        check("locked out %s after the failure: refused ('%s'), no new approach" % (label, str(g("last_failure_reason"))[:70]), (not ok) and "not retried" in str(g("last_failure_reason")) and g("approach_start_count") == st1 + 1 and stname() == "IDLE")
    check("%d lockout refusals counted" % (g("approach_lockout_refusals") - ref0), g("approach_lockout_refusals") - ref0 == 4)
    yield ("until", lambda: S["last_t"] >= t_fail + 121.0, 130.0)
    ok = S["comp"].request_activity(SEAT_B)
    check("after 121 s the point is tried again (new approach started: %d)" % g("approach_start_count"), ok and g("approach_start_count") == st1 + 2, "%s %s" % (ok, g("approach_start_count")))
    yield from states_until(lambda: stname() == "IDLE", 5.0)
    S["comp"].abort_activity()
    yield ("ticks", 3)

    # ---- invariants over the whole run ---------------------------------------------------------------------------------------------------------------
    smp = S["samples"]
    held_wrong = [s for s in smp if s["st"] in ("ALIGNING", "ENTERING", "PERFORMING", "EXITING") and s["mm"] != "MOVE_NONE"]
    check("movement held on every tick of the seated lifecycle (%d samples; the approach itself is never held)" % len([s for s in smp if s["st"] in ("ALIGNING", "ENTERING", "PERFORMING", "EXITING")]), not held_wrong, str(held_wrong[:2]))
    big = max(d2(p["x"], p["y"], q["x"], q["y"]) / max(q["t"] - p["t"], 1e-3) for p, q in zip(smp, smp[1:]) if q["t"] > p["t"])
    check("no teleport anywhere in the run: top speed %.0f cm/s" % big, big <= max_walk * 1.35, str(big))
    log("counters: approaches %d, success %d, fail %d, cancel %d, lockout refusals %d" % (g("approach_start_count"), g("approach_success_count"), g("approach_fail_count"), g("approach_cancel_count"), g("approach_lockout_refusals")))
    finish(0)


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 400000:
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
