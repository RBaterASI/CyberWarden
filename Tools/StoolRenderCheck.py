"""Rendered Play-In-Editor check of QUI01 sitting on the prototype stool (M2.3 Stage C2). Saves nothing in the project; images go to Saved/StoolCheck/.

  powershell -File Tools\\RunRenderScript.ps1 -Script Tools\\StoolRenderCheck.py -Log <abs log>     (needs the GPU: NOT RunHeadless.ps1)
  env FEAS=1 : one capture and exit (checks that scene captures render in a PIE world)
  env ACT_SLOMO : time dilation, default 1 (the approach lasts only about 0.4 s)

The real StateTree and the real data are used, nothing is driven: QUI01 follows the breakfast schedule to Seat_Table_1_5, walks the final approach, turns,
sits on the stool, stays seated, and a schedule change (breakfast -> work) makes it stand up and walk away. Scene captures are taken in the PIE world:
  sheetA  side view (orthographic) of the approach, turn and stand-to-sit, every few ticks
  sheetB  the seated loop from the front (over the table), two three-quarter views and a low close-up of the stool, legs and feet
  sheetC  side view of the sit-to-stand and the first steps away
Each sheet is one image (tiles drawn into one render target); single frames are exported as well. PNGs are written without extension: rename to .png.
"""
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SEAT = "Seat_Table_1_5"
OUT = unreal.Paths.project_saved_dir() + "StoolCheck/"
SLOMO = float(os.environ.get("ACT_SLOMO", "1"))
FEAS = os.environ.get("FEAS", "") == "1"
W, H = 640, 360
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
# Deferred spawning is not exposed to Python and PIE actors cannot be spawned from here, so one scene-capture rig is placed in the EDITOR world before PIE starts (PIE duplicates it).
# It is tagged and never saved: this script never saves the level.
RIG = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0.0, 0.0, 800.0))
RIG.set_actor_label("StoolCaptureRig_TEMP")
RIG.set_editor_property("tags", [unreal.Name("StoolCaptureRig")])
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "until": None, "timed_out": False, "last_t": None, "out": [], "tiles": {"A": [], "B": [], "C": []}}


def log(m):
    S["out"].append(str(m))
    unreal.log("[STOOLCHK] " + str(m))


def finish(code):
    unreal.unregister_slate_post_tick_callback(S["h"])
    with open(unreal.Paths.project_saved_dir() + "StoolRenderCheck.txt", "w") as fh:
        fh.write("\n".join(S["out"]))
    level_sub.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


def g(c, k):
    return c.get_editor_property(k)


def look_at(frm, to):
    dx, dy, dz = to[0] - frm[0], to[1] - frm[1], to[2] - frm[2]
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw)


def snap(name, frm, to, ortho_width=None, fov=50.0, label=None, sheet=None, flat=False):
    """One scene capture in the PIE world, exported as OUT/<name>; the render target is kept for the contact sheet."""
    gw = S["gw"]
    rt = unreal.RenderingLibrary.create_render_target2d(gw, W, H, unreal.TextureRenderTargetFormat.RTF_RGBA8)
    a = S["rig"]  # the PIE copy of the pre-placed capture rig
    a.set_actor_location_and_rotation(unreal.Vector(*frm), look_at(frm, to), False, False)
    comp = a.capture_component2d
    if ortho_width:
        comp.projection_type = unreal.CameraProjectionMode.ORTHOGRAPHIC
        comp.ortho_width = ortho_width
    else:
        comp.projection_type = unreal.CameraProjectionMode.PERSPECTIVE
        comp.fov_angle = fov
    comp.texture_target = rt
    comp.capture_source = unreal.SceneCaptureSource.SCS_BASE_COLOR if flat else unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR  # flat: unlit base colour (clear silhouettes in the dim cafeteria)
    comp.capture_every_frame = False
    comp.capture_on_movement = False
    comp.capture_scene()
    # The single frame is exported at the end (after the sheets are drawn): exporting right after capture_scene() sometimes wrote a blank (white) file.
    S["tiles"].setdefault(sheet or "X", []).append((rt, label or name, name))
    return rt


def build_sheet(sheet, cols):
    tiles = S["tiles"][sheet]
    if not tiles:
        return
    gw = S["gw"]
    rows = (len(tiles) + cols - 1) // cols
    big = unreal.RenderingLibrary.create_render_target2d(gw, W * cols, H * rows, unreal.TextureRenderTargetFormat.RTF_RGBA8)
    try:
        canvas, size, ctx = unreal.RenderingLibrary.begin_draw_canvas_to_render_target(gw, big)
        for i, (rt, label, _name) in enumerate(tiles):
            x, y = (i % cols) * W, (i // cols) * H
            canvas.draw_texture(rt, unreal.Vector2D(x, y), unreal.Vector2D(W, H), unreal.Vector2D(0, 0), unreal.Vector2D(1, 1), unreal.LinearColor(1, 1, 1, 1), unreal.BlendMode.BLEND_OPAQUE, 0.0, unreal.Vector2D(0, 0))
            log("sheet%s tile %d: %s" % (sheet, i + 1, label))
        unreal.RenderingLibrary.end_draw_canvas_to_render_target(gw, ctx)
        unreal.RenderingLibrary.export_render_target(gw, big, OUT, "sheet%s" % sheet)
        log("sheet%s written: %d tiles, %d x %d" % (sheet, len(tiles), W * cols, H * rows))
    except Exception as ex:
        log("sheet%s could not be drawn (%s): the single frames are still exported" % (sheet, ex))


def run(gw):
    S["gw"] = gw
    rigs = unreal.GameplayStatics.get_all_actors_with_tag(gw, "StoolCaptureRig")
    log("capture rigs in the PIE world: %d" % len(rigs))
    S["rig"] = rigs[0]
    npcs ={str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
    mgr = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")[0]
    npc = npcs["QUI01"]
    npc.get_component_by_class(unreal.SkeletalMeshComponent).set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    yield ("ticks", 5)
    sc, ac = npc.get_component_by_class(unreal.PrisonScheduleComponent), npc.get_component_by_class(unreal.PrisonActivityComponent)
    mesh = npc.get_component_by_class(unreal.SkeletalMeshComponent)
    stools = [a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "Kind:SeatStool")]
    log("stool actors in the PIE world: %s" % [(a.get_actor_label(), str(a.get_actor_location())) for a in stools])
    CX, CY = 6150.0, 20.0
    if FEAS:
        yield ("ticks", 20)
        snap("feas_side", (CX + 300, CY, 70), (CX, CY, 70), ortho_width=260.0, label="feasibility side")
        snap("feas_persp", (CX + 160, CY + 150, 110), (CX, 35, 35), fov=55.0, label="feasibility 3/4")
        log("feasibility captures exported to %s" % OUT)
        finish(0)
        return

    unreal.SystemLibrary.execute_console_command(gw, "slomo %g" % SLOMO)
    mgr.set_editor_property("time_scale", 30.0)

    def side(name, label, sheet):
        snap(name, (CX + 300, CY, 72), (CX, CY, 72), ortho_width=260.0, label=label, sheet=sheet, flat=True)

    # ---- breakfast: walk to the seat, approach, turn, sit ---------------------------------------------------------------------------------------
    serial0 = g(sc, "replan_serial")
    mgr.set_time_of_day_hours(7.0)
    mgr.set_editor_property("paused", False)
    yield ("until", lambda: g(sc, "replan_serial") > serial0, 80.0)
    mgr.set_editor_property("paused", True)
    st0 = g(ac, "start_count")
    yield ("until", lambda: g(ac, "state").name == "APPROACHING", 1500.0)
    if S["timed_out"]:
        log("QUI01 never started the final approach")
        finish(3)
        return
    t_a = S["last_t"]
    log("final approach started; capsule %s" % npc.get_actor_location())
    k = 0
    last = -1.0
    while not (g(ac, "state").name == "PERFORMING" and S["last_t"] - t_a > 3.2):
        if S["last_t"] - last >= 0.2:
            last = S["last_t"]
            k += 1
            loc = npc.get_actor_location()
            side("A_%02d" % k, "t=+%.2f s %s capsule (%.1f, %.1f) yaw %.1f" % (S["last_t"] - t_a, g(ac, "state").name, loc.x, loc.y, npc.get_actor_rotation().yaw), "A")
        yield ("ticks", 1)
        if S["last_t"] - t_a > 12.0:
            break
    log("sit sequence captured: %d frames" % k)

    # ---- the seated loop from several sides -------------------------------------------------------------------------------------------------------
    yield ("secs", 1.0)
    pel = mesh.get_socket_location("pelvis")
    log("seated: capsule %s, pelvis (%.2f, %.2f, %.2f), montage %s weight %.2f" % (npc.get_actor_location(), pel.x, pel.y, pel.z, g(ac, "montage_playing"), g(ac, "slot_node_weight")))
    snap("B_front_high", (CX, -300.0, 190.0), (CX, 40.0, 75.0), fov=48.0, label="front, over the table", sheet="B")
    snap("B_34_front", (CX + 210, -150.0, 150.0), (CX, 35.0, 65.0), fov=50.0, label="three-quarter front", sheet="B")
    snap("B_34_rear", (CX + 190, 190.0, 125.0), (CX, 35.0, 55.0), fov=50.0, label="three-quarter rear", sheet="B")
    snap("B_close_legs", (CX + 120, 20.0, 38.0), (CX, 28.0, 30.0), fov=62.0, label="close-up: stool, legs, feet", sheet="B")
    snap("B_top", (CX, 30.0, 260.0), (CX, 30.0, 40.0), fov=40.0, label="from above", sheet="B")
    snap("B_side_loop", (CX + 300, CY, 72), (CX, CY, 72), ortho_width=260.0, label="side, orthographic", sheet="B")
    yield ("secs", 2.2)
    snap("B_side_loop2", (CX + 300, CY, 72), (CX, CY, 72), ortho_width=260.0, label="side, 2.2 s later (loop stable)", sheet="B")
    # zoomed orthographic views of the contact between body and seat (0.16 cm per pixel): side, unlit and lit, and straight down
    snap("D_side_zoom_flat", (CX + 300, 38.0, 48.0), (CX, 38.0, 48.0), ortho_width=100.0, label="side zoom, unlit (seat plate y 18.5..56.5, top z 44)", sheet="D", flat=True)
    snap("D_side_zoom_lit", (CX + 300, 38.0, 48.0), (CX, 38.0, 48.0), ortho_width=100.0, label="side zoom, lit", sheet="D")
    snap("D_top_zoom_flat", (CX, 38.0, 320.0), (CX, 38.0, 40.0), ortho_width=100.0, label="from above, unlit (seat plate x 6131..6169, y 18.5..56.5)", sheet="D", flat=True)
    snap("D_front_zoom_flat", (CX, -300.0, 46.0), (CX, 40.0, 46.0), ortho_width=100.0, label="front, unlit (looking +Y; the table hides nothing at this height)", sheet="D", flat=True)

    # ---- schedule change: stand up and walk away -------------------------------------------------------------------------------------------------
    serial1 = g(sc, "replan_serial")
    mgr.set_editor_property("time_scale", 6000.0)
    mgr.set_time_of_day_hours(10.0)
    mgr.set_editor_property("paused", False)
    yield ("until", lambda: g(ac, "state").name == "EXITING", 60.0)
    mgr.set_editor_property("paused", True)
    mgr.set_editor_property("time_scale", 30.0)
    t_e = S["last_t"]
    log("exit started at +0 s; state %s" % g(ac, "state").name)
    k = 0
    last = -1.0
    while S["last_t"] - t_e < 6.0:
        if S["last_t"] - last >= 0.35:
            last = S["last_t"]
            k += 1
            loc = npc.get_actor_location()
            side("C_%02d" % k, "exit +%.2f s %s capsule (%.1f, %.1f)" % (S["last_t"] - t_e, g(ac, "state").name, loc.x, loc.y), "C")
        if 1.9 <= S["last_t"] - t_e <= 3.7 and S["last_t"] - S.get("last_e", -1.0) >= 0.2:  # the first steps away: lit three-quarter view from behind
            S["last_e"] = S["last_t"]
            loc = npc.get_actor_location()
            snap("E_%02d" % (len(S["tiles"].get("E", [])) + 1), (CX + 190, 190.0, 125.0), (CX, 35.0, 55.0), fov=50.0, label="exit +%.2f s %s capsule (%.1f, %.1f)" % (S["last_t"] - t_e, g(ac, "state").name, loc.x, loc.y), sheet="E")
        yield ("ticks", 1)
    log("stand-up sequence captured: %d frames; QUI01 now at %s" % (k, npc.get_actor_location()))

    for sh, cols in (("A", 4), ("B", 3), ("C", 4), ("D", 2), ("E", 4)):
        build_sheet(sh, cols)
    yield ("ticks", 3)
    for sh, tiles in S["tiles"].items():  # every single frame, exported after the sheets
        for rt, _label, name in tiles:
            unreal.RenderingLibrary.export_render_target(gw, rt, OUT, name)
    finish(0)


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
