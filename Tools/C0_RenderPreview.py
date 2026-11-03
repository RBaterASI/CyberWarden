"""M2.3 Stage C0 step 6b: renders the two pose strips of L_C0_SeatPreview with an orthographic side-view scene capture (needs a GPU:
launch with Tools\\RunRenderScript.ps1, not RunHeadless.ps1). Does not save the level. The files go to Saved/C0_Preview/ and are PNGs
without an extension (rename them to .png to open them).
"""
import unreal

LVL = "/Game/CyberWarden/Anims/Preview/L_C0_SeatPreview"
OUT = unreal.Paths.project_saved_dir() + "C0_Preview/"
out = []


def p(m):
    out.append(str(m))
    unreal.log("[C0] " + str(m))


les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les.load_level(LVL)
world = unreal.EditorLevelLibrary.get_editor_world()
for a in eas.get_all_level_actors():
    if isinstance(a, unreal.SkyLight):
        a.light_component.recapture_sky()
    if isinstance(a, unreal.SkeletalMeshActor):
        c = a.skeletal_mesh_component
        for fn in ("tick_animation", "refresh_bone_transforms", "finalize_bone_transforms", "update_component_to_world", "mark_render_state_dirty"):
            if hasattr(c, fn):
                try:
                    getattr(c, fn)(0.0, False) if fn == "tick_animation" else getattr(c, fn)()
                except Exception as ex:
                    p("%s failed: %s" % (fn, ex))


def shot(name, center_y, width, z_center, height_px, width_px):
    rt = unreal.RenderingLibrary.create_render_target2d(world, width_px, height_px, unreal.TextureRenderTargetFormat.RTF_RGBA8)
    cap = eas.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(-3000, center_y, z_center), unreal.Rotator(0, 0, 0))
    comp = cap.capture_component2d
    comp.projection_type = unreal.CameraProjectionMode.ORTHOGRAPHIC
    comp.ortho_width = width
    comp.texture_target = rt
    comp.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
    comp.capture_every_frame = False
    comp.capture_on_movement = False
    comp.capture_scene()
    unreal.RenderingLibrary.export_render_target(world, rt, OUT, name)
    eas.destroy_actor(cap)
    p("shot %s" % name)


shot("stripA_StandToSit", 600.0, 1500.0, 120.0, 400, 1500)
shot("stripB_SitToStand", 1800.0 + 500.0, 1500.0, 120.0, 400, 1500)

with open(unreal.Paths.project_saved_dir() + "C0_RenderPreview.txt", "w") as fh:
    fh.write("\n".join(out))
unreal.SystemLibrary.quit_editor()
