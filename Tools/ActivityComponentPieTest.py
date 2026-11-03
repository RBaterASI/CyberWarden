"""Headless PIE test of the C++ UPrisonActivityComponent on QUI01 at Rec_TV (M2.3 Stage A). Saves nothing.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/ActivityComponentPieTest.py -Log <abs log>

The StateTree of QUI01 is stopped in the PIE copy (the activity is not connected to the StateTree yet) and the NPC is walked to the TV
with the real AI navigation (AIController MoveTo; nothing is teleported). Then the component lifecycle is exercised:
too far / unknown marker, smooth alignment and facing, DefaultSlot montage playback (slot node weight), continuation and no repeated
starts, release inside the grace window, clean release and restored locomotion, interruption while aligning, entering and exiting,
queued re-request while exiting, missing animations, and per-tick snapping checks (position and yaw steps).
"""
import math
import os

import unreal

import cw_activity as ca

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SLOMO = float(os.environ.get("ACT_SLOMO", "4"))
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
layout = ca.load_layout()
TV = ca.prop_center(layout, "Prop_Rec_TV")  # (4000, 3365, 220)
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "until": None, "res": [], "fail": [], "samples": [], "win": {}, "last_t": None, "timed_out": False}


def log(m):
    unreal.log("[ACTTEST] " + m)


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


def sample(now):
    a = S["npc"]
    loc = a.get_actor_location()
    yaw = a.get_actor_rotation().yaw
    st = S["comp"].get_editor_property("state").name
    S["samples"].append((now, loc.x, loc.y, yaw, st))


def window(label):
    """Stats over the samples recorded since mark(label)."""
    i = S["win"][label]
    pts = S["samples"][i:]
    if len(pts) < 2:
        return dict(n=len(pts), max_step=0.0, disp=0.0, max_yaw_step=0.0, max_yaw_rate=0.0)
    ms = my = mr = 0.0
    for p, q in zip(pts, pts[1:]):
        ms = max(ms, d2(p[1], p[2], q[1], q[2]))
        dy = abs(ndelta(p[3], q[3]))
        my = max(my, dy)
        mr = max(mr, dy / max(q[0] - p[0], 1e-3))
    return dict(n=len(pts), max_step=ms, disp=d2(pts[0][1], pts[0][2], pts[-1][1], pts[-1][2]), max_yaw_step=my, max_yaw_rate=mr)


def mark(label):
    S["win"][label] = max(len(S["samples"]) - 1, 0)  # include the last sample taken before the request, so the first rotation step is measured


def g(k):
    return S["comp"].get_editor_property(k)


def stname():
    return g("state").name


def mmode():
    return S["cmc"].get_editor_property("movement_mode").name


def walk_to(marker_id, radius=60.0, timeout=90.0):
    tgt = unreal.GameplayStatics.get_all_actors_with_tag(S["gw"], "MarkerId:" + marker_id)[0].get_actor_location()
    S["ctrl"].move_to_location(tgt, radius, True, True, False, False, None, True)
    return tgt


def arrived(tgt):
    loc = S["npc"].get_actor_location()
    return "IDLE" in str(S["ctrl"].get_move_status()) and d2(loc.x, loc.y, tgt.x, tgt.y) < 130.0


def run(gw):
    npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
    mgrs = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")
    if "QUI01" not in npcs or len(mgrs) != 1:
        log("FAILED: QUI01=%s managers=%d" % ("QUI01" in npcs, len(mgrs)))
        finish(4)
        return
    S.update(gw=gw, npc=npcs["QUI01"], mgr=mgrs[0])
    npc = S["npc"]
    S["comp"] = npc.get_component_by_class(unreal.PrisonActivityComponent)
    S["ctrl"] = npc.get_controller()
    S["cmc"] = npc.get_component_by_class(unreal.CharacterMovementComponent)
    S["mesh"] = npc.get_component_by_class(unreal.SkeletalMeshComponent)
    check("QUI01 has the PrisonActivityComponent", S["comp"] is not None)
    check("activity data reaches the NPC through the schedule manager", mgrs[0].get_editor_property("activity_data") is not None and
          len(list(mgrs[0].get_editor_property("activity_data").validate_data())) == 0)
    S["mgr"].set_editor_property("paused", True)
    stc = S["ctrl"].get_component_by_class(unreal.StateTreeAIComponent)
    if stc is not None:
        stc.stop_logic("activity test")  # PIE copy only
    unreal.SystemLibrary.execute_console_command(gw, "slomo %g" % SLOMO)
    yield ("ticks", 10)
    check("starts idle with normal movement", stname() == "IDLE" and mmode() == "MOVE_WALKING", "%s %s" % (stname(), mmode()))

    # ---- 1. refusals --------------------------------------------------------------------------------------------
    ok = S["comp"].request_activity("Rec_TV")
    check("too far from the point: request refused with a distance reason, nothing held", (not ok) and "too far" in str(g("last_failure_reason")) and stname() == "IDLE" and
          mmode() == "MOVE_WALKING" and g("start_count") == 0, str(g("last_failure_reason")))
    ok = S["comp"].request_activity("Rec_Bench")
    check("marker without an interaction point: refused with a reason", (not ok) and "no interaction point" in str(g("last_failure_reason")), str(g("last_failure_reason")))
    check("HasInteractionPoint", S["comp"].has_interaction_point("Rec_TV") and not S["comp"].has_interaction_point("Rec_Bench"))

    # ---- 2. real navigation to the TV -------------------------------------------------------------------------------
    tgt = walk_to("Rec_TV")
    yield ("until", lambda: arrived(tgt), 120.0)
    loc = npc.get_actor_location()
    check("QUI01 walked to Rec_TV by navigation (%.0f cm from the marker)" % d2(loc.x, loc.y, tgt.x, tgt.y), not S["timed_out"] and d2(loc.x, loc.y, tgt.x, tgt.y) < 150.0)
    yield ("secs", 0.5)

    # ---- 3. start: smooth alignment, facing, DefaultSlot playback ----------------------------------------------------
    start_loc = npc.get_actor_location()
    expect_yaw = math.degrees(math.atan2(TV[1] - start_loc.y, TV[0] - start_loc.x))
    start_yaw = npc.get_actor_rotation().yaw
    log("before the request: yaw %.1f, expected facing %.1f (turn of %.1f degrees)" % (start_yaw, expect_yaw, ndelta(start_yaw, expect_yaw)))
    mark("align")
    ok = S["comp"].request_activity("Rec_TV")
    check("request accepted at Rec_TV", ok, str(g("last_failure_reason")))
    check("movement is held while the activity runs", mmode() == "MOVE_NONE" and g("movement_held"), mmode())
    yield ("until", lambda: stname() == "PERFORMING", 8.0)
    check("reached Performing", not S["timed_out"], stname())
    yield ("secs", 1.2)
    w = window("align")
    yaw_now = npc.get_actor_rotation().yaw
    check("facing the TV: yaw error %.2f degrees (limit 3.5)" % abs(ndelta(yaw_now, expect_yaw)), abs(ndelta(yaw_now, expect_yaw)) <= 3.5, "%.2f" % ndelta(yaw_now, expect_yaw))
    check("smooth turn: max %.0f deg/s (configured 120)" % w["max_yaw_rate"], w["max_yaw_rate"] <= 120.0 * 1.15 + 5.0, str(w))
    check("no snapping: max position step %.2f cm, total displacement %.2f cm" % (w["max_step"], w["disp"]), w["max_step"] < 1.0 and w["disp"] < 1.0, str(w))
    check("DefaultSlot plays the montage (montage playing, slot node weight %.2f)" % g("slot_node_weight"), g("montage_playing") and g("slot_node_weight") >= 0.95, "%s %s" % (g("montage_playing"), g("slot_node_weight")))
    check("real loop animation used (no fallback)", not g("using_fallback_idle"))
    check("one start recorded", g("start_count") == 1 and g("active_marker_id") == "Rec_TV" and g("active_activity_id") == "WatchTV",
          "%s %s %s" % (g("start_count"), g("active_marker_id"), g("active_activity_id")))
    check("locomotion variables still respond (ShouldMove false while standing)", S["mesh"].get_anim_instance().get_editor_property("ShouldMove") is False)

    # ---- 4. repeated requests = continuation, never a restart ------------------------------------------------------
    for _ in range(6):
        S["comp"].request_activity("Rec_TV")
        yield ("secs", 0.2)
    check("6 repeated requests: no restart (starts %d, continuations %d)" % (g("start_count"), g("continuation_count")), g("start_count") == 1 and g("continuation_count") == 6 and
          stname() == "PERFORMING" and g("montage_playing"), "%s %s" % (g("start_count"), g("continuation_count")))

    # ---- 5. release + re-request inside the grace window ------------------------------------------------------------
    secs = S["comp"].release_activity()
    check("release reports the time until free: %.2f s (grace 0.25 + blend out 0.3)" % secs, 0.5 <= secs <= 0.6, str(secs))
    yield ("secs", 0.08)
    S["comp"].request_activity("Rec_TV")
    yield ("secs", 0.8)
    check("re-request inside the grace window continues without a restart", g("start_count") == 1 and stname() == "PERFORMING" and not g("release_pending") and g("montage_playing"),
          "%s %s %s" % (g("start_count"), stname(), g("release_pending")))

    # ---- 6. clean release, locomotion restored ----------------------------------------------------------------------
    secs = S["comp"].release_activity()
    yield ("until", lambda: stname() == "IDLE", secs + 3.0)
    check("release ends the activity (%s)" % stname(), not S["timed_out"] and stname() == "IDLE")
    check("movement restored to walking", mmode() == "MOVE_WALKING" and not g("movement_held"), mmode())
    check("no montage left in the slot", S["mesh"].get_anim_instance().get_current_active_montage() is None)
    here = npc.get_actor_location()
    tgt2 = walk_to("Rec_Table_B")
    yield ("secs", 4.0)
    moved = d2(here.x, here.y, npc.get_actor_location().x, npc.get_actor_location().y)
    check("NPC walks away again after the activity (%.0f cm in 4 s)" % moved, moved > 150.0, str(moved))
    ms = S["mesh"].get_anim_instance().get_editor_property("ShouldMove")
    check("walking animation variables respond again (ShouldMove)", ms is True, str(ms))

    # ---- 7. interruption while aligning -----------------------------------------------------------------------------
    tgt = walk_to("Rec_TV")
    yield ("until", lambda: arrived(tgt), 120.0)
    yield ("secs", 0.5)
    r = npc.get_actor_rotation()
    npc.set_actor_rotation(unreal.Rotator(r.roll, r.pitch, ndelta(0, expect_yaw + 180.0)), False)  # test only: turn the NPC away from the TV
    yield ("ticks", 3)  # let the test setup rotation settle so it is not measured as part of the turn
    starts0, ints0 = g("start_count"), g("interrupt_count")
    mark("turn")
    S["comp"].request_activity("Rec_TV")
    yield ("secs", 0.3)
    wt = window("turn")
    check("180 degree turn is smooth and in place: max %.0f deg/s (configured 120), max step %.2f cm" % (wt["max_yaw_rate"], wt["max_step"]), 60.0 <= wt["max_yaw_rate"] <= 120.0 * 1.15 + 5.0 and wt["max_step"] < 1.0, str(wt))
    check("turning from the far side takes time (still aligning after 0.3 s)", stname() == "ALIGNING", stname())
    secs = S["comp"].release_activity()
    check("release while aligning: free immediately (%.2f s), idle, movement restored, no montage ever played" % secs,
          secs == 0.0 and stname() == "IDLE" and mmode() == "MOVE_WALKING" and not g("montage_playing") and g("interrupt_count") == ints0 + 1 and g("start_count") == starts0 + 1,
          "%s %s %s %s" % (secs, stname(), mmode(), g("interrupt_count")))

    # ---- 8. a request while exiting is queued and runs after the exit -----------------------------------------------
    S["comp"].request_activity("Rec_TV")
    yield ("until", lambda: stname() == "PERFORMING", 8.0)
    starts1 = g("start_count")
    S["comp"].release_activity()
    yield ("until", lambda: stname() == "EXITING", 2.0)
    check("reached Exiting", not S["timed_out"], stname())
    ok = S["comp"].request_activity("Rec_TV")
    check("request during Exiting is accepted and queued", ok and g("pending_marker_id") == "Rec_TV", str(g("pending_marker_id")))
    yield ("until", lambda: stname() in ("ALIGNING", "ENTERING", "PERFORMING") and g("start_count") == starts1 + 1, 4.0)
    check("queued activity started after the exit (starts %d -> %d)" % (starts1, g("start_count")), not S["timed_out"] and g("start_count") == starts1 + 1)
    yield ("until", lambda: stname() == "PERFORMING", 4.0)

    # ---- 9. enter / exit animations: full cycle and interruption while entering ---------------------------------------
    S["comp"].release_activity()
    yield ("until", lambda: stname() == "IDLE", 3.0)
    data = unreal.new_object(unreal.PrisonActivityData)
    land = unreal.load_asset("/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Land")
    idle = unreal.load_asset("/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle")
    full = unreal.PrisonActivityDefinition(id="TestEnterExit", enter_animation=land, loop_animation=idle, exit_animation=land, slot_name="DefaultSlot", blend_in_seconds=0.2,
                                           blend_out_seconds=0.2, play_rate=1.0, randomize_loop_start=False, align_yaw_rate_deg_per_sec=120.0, yaw_tolerance_degrees=3.0)
    bare = unreal.PrisonActivityDefinition(id="TestNoAnim", slot_name="DefaultSlot", align_yaw_rate_deg_per_sec=120.0, yaw_tolerance_degrees=3.0, blend_out_seconds=0.2)
    data.set_editor_property("activities", [full, bare])
    pt = unreal.PrisonInteractionPoint(marker_id="Rec_TV", activity_id="TestEnterExit", facing_mode=unreal.PrisonFacingMode.POINT,
                                       facing_point=unreal.Vector(TV[0], TV[1], TV[2]), arrival_tolerance_cm=150.0, capacity=1)
    data.set_editor_property("points", [pt])
    check("test data validates", len(list(data.validate_data())) == 0, str(list(data.validate_data())))
    S["comp"].set_editor_property("activity_data_override", data)
    S["comp"] = S["npc"].get_component_by_class(unreal.PrisonActivityComponent)  # editing an instance property can re-create the component: re-fetch
    seen = []
    t0 = None
    S["comp"].request_activity("Rec_TV")
    while True:
        yield ("ticks", 1)
        s = stname()
        if not seen or seen[-1] != s:
            seen.append(s)
            if s == "ENTERING":
                t0 = S["last_t"]
            if s == "PERFORMING" and t0 is not None and "enter_dur" not in S:
                S["enter_dur"] = S["last_t"] - t0
        if s == "PERFORMING" or S["last_t"] is None:
            break
    yield ("secs", 0.6)
    check("full cycle: Aligning/Entering/Performing in order %s, enter took %.2f s (MM_Land 0.87 s)" % (seen, S.get("enter_dur", -1)),
          "ENTERING" in seen and seen[-1] == "PERFORMING" and 0.7 <= S.get("enter_dur", 0) <= 1.1, str(seen))
    check("loop montage playing after the enter animation (slot weight %.2f)" % g("slot_node_weight"), g("montage_playing") and g("slot_node_weight") >= 0.95)
    secs = S["comp"].release_activity()
    check("release time includes the exit animation: %.2f s (grace 0.25 + 0.87)" % secs, 1.0 <= secs <= 1.25, str(secs))
    yield ("until", lambda: stname() == "EXITING", 2.0)
    check("exit animation phase entered", not S["timed_out"])
    yield ("until", lambda: stname() == "IDLE", 3.0)
    check("exit finished: idle, movement restored", stname() == "IDLE" and mmode() == "MOVE_WALKING", "%s %s" % (stname(), mmode()))

    ints = g("interrupt_count")
    S["comp"].request_activity("Rec_TV")
    yield ("until", lambda: stname() == "ENTERING", 3.0)
    yield ("secs", 0.2)
    secs = S["comp"].release_activity()
    check("release while entering: blend out only (%.2f s), interrupt counted" % secs, 0.1 <= secs <= 0.35 and g("interrupt_count") == ints + 1, "%s %s" % (secs, g("interrupt_count")))
    yield ("until", lambda: stname() == "IDLE", 2.0)
    check("back to idle with movement restored after the interrupted enter", stname() == "IDLE" and mmode() == "MOVE_WALKING" and S["mesh"].get_anim_instance().get_current_active_montage() is None)

    # ---- 10. missing animations degrade gracefully ----------------------------------------------------------------------
    pt2 = unreal.PrisonInteractionPoint(marker_id="Rec_TV", activity_id="TestNoAnim", facing_mode=unreal.PrisonFacingMode.POINT,
                                        facing_point=unreal.Vector(TV[0], TV[1], TV[2]), arrival_tolerance_cm=150.0, capacity=1)
    data.set_editor_property("points", [pt2])
    S["comp"] = S["npc"].get_component_by_class(unreal.PrisonActivityComponent)
    ok = S["comp"].request_activity("Rec_TV")
    yield ("until", lambda: stname() == "PERFORMING", 4.0)
    check("activity without animations: accepted, performing in the normal idle pose (fallback), no montage", ok and stname() == "PERFORMING" and g("using_fallback_idle") and not g("montage_playing"),
          "%s %s %s" % (ok, stname(), g("using_fallback_idle")))
    secs = S["comp"].release_activity()
    yield ("until", lambda: stname() == "IDLE", 2.0)
    check("fallback activity releases cleanly (%.2f s)" % secs, not S["timed_out"] and mmode() == "MOVE_WALKING", str(secs))

    # ---- 11. unknown data cases ---------------------------------------------------------------------------------------------
    S["comp"].set_editor_property("activity_data_override", None)
    S["comp"] = S["npc"].get_component_by_class(unreal.PrisonActivityComponent)
    ok = S["comp"].request_activity("Rec_TV")
    check("back on the sector data: Rec_TV works again", ok)
    yield ("until", lambda: stname() == "PERFORMING", 5.0)
    S["comp"].abort_activity()
    check("abort stops everything now and restores movement", stname() == "IDLE" and mmode() == "MOVE_WALKING" and not g("montage_playing"), "%s %s" % (stname(), mmode()))

    w_all = {"max_step": max(d2(p[1], p[2], q[1], q[2]) for p, q in zip(S["samples"], S["samples"][1:]) if p[4] != "IDLE" and q[4] != "IDLE")} if len(S["samples"]) > 2 else {"max_step": 0}
    check("no position jumps at any time while an activity was active (max step %.2f cm)" % w_all["max_step"], w_all["max_step"] < 1.0)
    finish(0)


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 100000:
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
        S["last_t"] = now if S["last_t"] is None else now
        if "comp" in S and "npc" in S and S["comp"] is not None:
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
