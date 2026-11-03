"""Read-only (M2.3 Stage C0): which skeleton the NPC meshes use, MM_Idle's skeleton / root-motion settings, and which IK Rig,
IK Retargeter and Control Rig assets the project already has. Loads assets only, never saves or modifies one; the only file
it writes is the text report in the git-ignored Saved/ folder.

  powershell -File Tools\RunHeadless.ps1 -Script Tools\InspectSeatedSkeleton.py
Output: Saved/InspectSeatedSkeleton.txt
"""
import unreal

out = []


def p(m):
    out.append(str(m))
    unreal.log("[C0] " + str(m))


def safe(f, default="<n/a>"):
    try:
        return f()
    except Exception as ex:
        return "%s(%s)" % (default, str(ex)[:100])


M = "/Game/Characters/Mannequins/"
for name in ("Meshes/SKM_Manny_Simple", "Meshes/SKM_Quinn_Simple", "Meshes/SK_Mannequin"):
    a = unreal.load_asset(M + name)
    p("%s: %s" % (name, a.get_class().get_name() if a else "MISSING"))
    if a and isinstance(a, unreal.SkeletalMesh):
        sk = a.get_editor_property("skeleton")
        p("  skeleton = %s" % (sk.get_path_name() if sk else None))
        p("  bounds extent = %s" % a.get_bounds().box_extent)

sk = unreal.load_asset(M + "Meshes/SK_Mannequin")
if sk:
    mesh = unreal.load_asset(M + "Meshes/SKM_Manny_Simple")
    p("skeleton obj dir hints: %s" % [d for d in dir(sk) if "bone" in d.lower()][:20])
    p("mesh dir hints: %s" % [d for d in dir(mesh) if "bone" in d.lower() or "ref" in d.lower()][:20])

idle = unreal.load_asset(M + "Anims/Unarmed/MM_Idle")
p("MM_Idle: %s skeleton=%s length=%.3f rate=%s root_motion=%s force_root_lock=%s" % (
    idle.get_class().get_name(), idle.get_editor_property("skeleton").get_path_name(), idle.get_play_length(),
    safe(lambda: idle.get_editor_property("rate_scale")), safe(lambda: idle.get_editor_property("enable_root_motion")),
    safe(lambda: idle.get_editor_property("force_root_lock"))))

ar = unreal.AssetRegistryHelpers.get_asset_registry()
flt = unreal.ARFilter(package_paths=["/Game"], recursive_paths=True)
for ad in ar.get_assets(flt):
    c = str(ad.asset_class_path.asset_name)
    if c in ("IKRigDefinition", "IKRetargeter", "ControlRigBlueprint", "AnimSequence") and ("Rig" in str(ad.asset_name) or "RTG" in str(ad.asset_name) or c != "AnimSequence"):
        p("asset %s (%s)" % (ad.package_name, c))

with open(unreal.Paths.project_saved_dir() + "InspectSeatedSkeleton.txt", "w") as fh:
    fh.write("\n".join(out))
unreal.SystemLibrary.quit_editor()
