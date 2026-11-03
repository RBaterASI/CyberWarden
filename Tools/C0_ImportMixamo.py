"""M2.3 Stage C0 step 1: import the three Mixamo FBX clips (ArtSource/Mixamo, git-ignored) into /Game/CyberWarden/Anims/Mixamo.
Stand To Sit is imported with its skin (creates the Mixamo skeleton + a reference mesh); the other two are animation-only on that
skeleton. Creates new assets only under /Game/CyberWarden/Anims/Mixamo; touches nothing else.

  powershell -File Tools\\RunHeadless.ps1 -Script Tools\\C0_ImportMixamo.py
Report: Saved/C0_ImportMixamo.txt
"""
import unreal

SRC = "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/ArtSource/Mixamo/"
DEST = "/Game/CyberWarden/Anims/Mixamo"
CLIPS = [("Stand To Sit.fbx", "MX_StandToSit", True), ("Sitting Idle.fbx", "MX_SittingIdle", False), ("Sit To Stand.fbx", "MX_SitToStand", False)]
out = []


def p(m):
    out.append(str(m))
    unreal.log("[C0] " + str(m))


def make_task(fname, asset_name, with_mesh, skeleton):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", with_mesh)
    ui.set_editor_property("import_as_skeletal", True)
    ui.set_editor_property("import_animations", True)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("create_physics_asset", False)
    ui.set_editor_property("automated_import_should_detect_type", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH if with_mesh else unreal.FBXImportType.FBXIT_ANIMATION)
    if skeleton:
        ui.set_editor_property("skeleton", skeleton)
    ad = ui.get_editor_property("anim_sequence_import_data")
    ad.set_editor_property("import_uniform_scale", 1.0)
    ad.set_editor_property("use_default_sample_rate", True)
    ad.set_editor_property("import_bone_tracks", True)
    ad.set_editor_property("remove_redundant_keys", False)
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", SRC + fname)
    t.set_editor_property("destination_path", DEST)
    t.set_editor_property("destination_name", asset_name)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", True)
    t.set_editor_property("options", ui)
    return t


skeleton = None
for fname, name, with_mesh in CLIPS:
    t = make_task(fname, name, with_mesh, skeleton)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    p("%s -> %s" % (fname, [str(x) for x in t.get_editor_property("imported_object_paths")]))
    if with_mesh:
        for pth in unreal.EditorAssetLibrary.list_assets(DEST):
            a = unreal.load_asset(pth)
            if isinstance(a, unreal.Skeleton):
                skeleton = a
                p("skeleton asset: %s" % pth)
        if not skeleton:
            p("ERROR: no skeleton created")

for pth in sorted(unreal.EditorAssetLibrary.list_assets(DEST)):
    a = unreal.load_asset(pth)
    line = "%s (%s)" % (pth, a.get_class().get_name())
    if isinstance(a, unreal.AnimSequence):
        line += " len=%.3fs keys=%s rate=%s skeleton=%s root_motion=%s" % (a.get_play_length(), unreal.AnimationLibrary.get_num_frames(a),
                                                                          a.get_editor_property("rate_scale"), a.get_editor_property("skeleton").get_name(),
                                                                          a.get_editor_property("enable_root_motion"))
    p(line)

with open(unreal.Paths.project_saved_dir() + "C0_ImportMixamo.txt", "w") as fh:
    fh.write("\n".join(out))
unreal.SystemLibrary.quit_editor()
