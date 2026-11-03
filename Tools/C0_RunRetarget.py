"""M2.3 Stage C0 step 4: finish the Mixamo->Manny retargeter (ops, pose alignment) and retarget the three clips onto SK_Mannequin.
Outputs /Game/CyberWarden/Anims/Seated/SEAT_StandToSit, SEAT_SittingIdle, SEAT_SitToStand. Report: Saved/C0_RunRetarget.txt
"""
import unreal

R = "/Game/CyberWarden/Anims/Retarget/"
MX = "/Game/CyberWarden/Anims/Mixamo/"
SEAT = "/Game/CyberWarden/Anims/Seated"
SRC_ANIMS = [MX + "MX_StandToSit_Anim", MX + "MX_SittingIdle", MX + "MX_SitToStand"]
out = []


def p(m):
    out.append(str(m))
    unreal.log("[C0] " + str(m))


S, T = unreal.RetargetSourceOrTarget.SOURCE, unreal.RetargetSourceOrTarget.TARGET
rtg = unreal.load_asset(R + "RTG_Mixamo_To_Manny")
src_rig = unreal.load_asset(R + "IK_Mixamo")
tgt_rig = unreal.load_asset(R + "IK_Manny")
rc = unreal.IKRetargeterController.get_controller(rtg)
rc.set_ik_rig(S, src_rig)
rc.set_ik_rig(T, tgt_rig)
p("ops before: %s" % rc.get_num_retarget_ops())
try:
    rc.assign_ik_rig_to_all_ops(T, tgt_rig)
except Exception as ex:
    p("assign_ik_rig_to_all_ops failed: %s" % ex)
p("ops after: %s" % rc.get_num_retarget_ops())
for i in range(rc.get_num_retarget_ops()):
    p("  op %d: %s enabled=%s" % (i, rc.get_op_name(i) if hasattr(rc, "get_op_name") else i, rc.get_retarget_op_enabled(i)))
# The Root Motion op makes the target "root" bone follow the Mixamo hips (61 cm of vertical drift in the first retarget); the clips
# are used in place, so it is disabled and the pelvis alone carries the motion.
for i in range(rc.get_num_retarget_ops()):
    if rc.get_op_name(i) == "Root Motion":
        rc.set_retarget_op_enabled(i, False)
        p("disabled op %d Root Motion" % i)
rc.auto_map_chains(unreal.AutoMapChainType.FUZZY, True)
try:
    rc.auto_align_all_bones(T)
    p("auto-aligned target pose to source")
except Exception as ex:
    p("auto_align_all_bones failed: %s" % ex)
unreal.EditorAssetLibrary.save_loaded_asset(rtg)

assets = [unreal.EditorAssetLibrary.find_asset_data(a) for a in SRC_ANIMS]
p("sources: %s" % [str(a.asset_name) for a in assets])
batch = unreal.IKRetargetBatchOperation
src_mesh = unreal.load_asset(MX + "MX_StandToSit")
tgt_mesh = unreal.load_asset("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple")
unreal.EditorAssetLibrary.make_directory(SEAT)
for old in ("SEAT_StandToSit", "SEAT_StandToSit_Anim", "SEAT_SittingIdle", "SEAT_SitToStand"):
    if unreal.EditorAssetLibrary.does_asset_exist(SEAT + "/" + old):
        unreal.EditorAssetLibrary.delete_asset(SEAT + "/" + old)
res = batch.duplicate_and_retarget(assets, src_mesh, tgt_mesh, rtg, search="MX_", replace="SEAT_", target_path=SEAT,
                                   include_referenced_assets=False, overwrite_existing_files=True)
p("retargeted: %s" % [str(a.package_name) for a in res])

final = {"SEAT_StandToSit_Anim": "SEAT_StandToSit"}
for a in res:
    old = str(a.package_name)
    nm = old.split("/")[-1]
    new = SEAT + "/" + final.get(nm, nm)
    p("move %s -> %s: %s" % (old, new, unreal.EditorAssetLibrary.rename_asset(old, new)))
unreal.EditorAssetLibrary.save_directory(SEAT)
for pth in sorted(unreal.EditorAssetLibrary.list_assets(SEAT)):
    a = unreal.load_asset(pth)
    if isinstance(a, unreal.AnimSequence):
        p("%s len=%.3f frames=%s skeleton=%s root_motion=%s" % (pth, a.get_play_length(), unreal.AnimationLibrary.get_num_frames(a), a.get_editor_property("skeleton").get_name(), a.get_editor_property("enable_root_motion")))

with open(unreal.Paths.project_saved_dir() + "C0_RunRetarget.txt", "w") as fh:
    fh.write("\n".join(out))
unreal.SystemLibrary.quit_editor()
