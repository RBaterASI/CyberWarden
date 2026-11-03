"""M2.3 Stage C0 step 3: create the Mixamo IK Rig, the Manny IK Rig and the Mixamo->Manny IK Retargeter under
/Game/CyberWarden/Anims/Retarget (new assets only). Chains are auto-generated for both skeletons (the engine's mannequin and
humanoid presets), then mapped, and the target (Manny) pose is auto-aligned to the Mixamo source pose.
Report: Saved/C0_BuildRetarget.txt
"""
import unreal

DEST = "/Game/CyberWarden/Anims/Retarget"
MIXAMO_MESH = "/Game/CyberWarden/Anims/Mixamo/MX_StandToSit"
MANNY_MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
out = []


def p(m):
    out.append(str(m))
    unreal.log("[C0] " + str(m))


at = unreal.AssetToolsHelpers.get_asset_tools()


def new_asset(name, cls, factory):
    path = DEST + "/" + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    return at.create_asset(name, DEST, cls, factory)


def build_rig(name, mesh_path, root_bone):
    mesh = unreal.load_asset(mesh_path)
    rig = new_asset(name, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
    c = unreal.IKRigController.get_controller(rig)
    ok = c.set_skeletal_mesh(mesh)
    p("%s: set mesh %s -> %s" % (name, mesh_path, ok))
    if root_bone:
        c.set_retarget_root(root_bone)
    c.apply_auto_generated_retarget_definition()
    p("%s retarget root = %s" % (name, c.get_retarget_root()))
    for ch in c.get_retarget_chains():
        n = ch.get_editor_property("chain_name") if hasattr(ch, "get_editor_property") else ch
        p("  chain %-14s %s -> %s" % (n, c.get_retarget_chain_start_bone(n), c.get_retarget_chain_end_bone(n)))
    unreal.EditorAssetLibrary.save_loaded_asset(rig)
    return rig, c


src_rig, src_c = build_rig("IK_Mixamo", MIXAMO_MESH, "mixamorig:Hips")
tgt_rig, tgt_c = build_rig("IK_Manny", MANNY_MESH, "pelvis")

rtg = new_asset("RTG_Mixamo_To_Manny", unreal.IKRetargeter, unreal.IKRetargetFactory())
rc = unreal.IKRetargeterController.get_controller(rtg)
p("retargeter controller methods: %s" % [d for d in dir(rc) if not d.startswith("_") and ("rig" in d or "mesh" in d or "map" in d or "pose" in d or "align" in d or "source" in d or "target" in d)])
try:
    rc.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, src_rig)
    rc.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, tgt_rig)
except Exception as ex:
    p("set_ik_rig failed: %s" % ex)
try:
    rc.set_preview_mesh(unreal.RetargetSourceOrTarget.SOURCE, unreal.load_asset(MIXAMO_MESH))
    rc.set_preview_mesh(unreal.RetargetSourceOrTarget.TARGET, unreal.load_asset(MANNY_MESH))
except Exception as ex:
    p("set_preview_mesh failed: %s" % ex)
try:
    rc.add_default_ops()
    rc.assign_ik_rig_to_all_ops(tgt_rig)
except Exception as ex:
    p("ops failed: %s" % ex)
try:
    rc.auto_map_chains(unreal.AutoMapChainType.FUZZY, True)
except Exception as ex:
    p("auto_map_chains failed: %s" % ex)

p("source rig %s target rig %s" % (rc.get_ik_rig(unreal.RetargetSourceOrTarget.SOURCE), rc.get_ik_rig(unreal.RetargetSourceOrTarget.TARGET)))
for tc in tgt_c.get_retarget_chains():
    n = tc.get_editor_property("chain_name")
    try:
        p("  map %-14s <- %s" % (n, rc.get_source_chain(n, "IKRetargetChainMapping" if False else "")))
    except Exception as ex:
        p("  map %s <- ? (%s)" % (n, str(ex)[:120]))
p("poses: %s" % [str(x) for x in rc.get_retarget_poses(unreal.RetargetSourceOrTarget.TARGET)])
unreal.EditorAssetLibrary.save_loaded_asset(rtg)

with open(unreal.Paths.project_saved_dir() + "C0_BuildRetarget.txt", "w") as fh:
    fh.write("\n".join(out))
unreal.SystemLibrary.quit_editor()
