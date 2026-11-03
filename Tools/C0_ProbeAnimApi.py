"""Read-only probe (Stage C0): which animation-analysis Python calls exist, and the Mixamo asset list. Saves nothing."""
import unreal

out = []
for cls in ("AnimationLibrary", "AnimPoseExtensions", "AnimPose", "AnimPoseEvaluationOptions", "AnimationBlueprintLibrary", "SkeletonModifier"):
    c = getattr(unreal, cls, None)
    out.append("%s: %s" % (cls, [d for d in dir(c) if not d.startswith("_") and any(k in d for k in ("pose", "bone", "frame", "root", "num", "length", "rate", "key", "track"))][:40] if c else None))
for pth in sorted(unreal.EditorAssetLibrary.list_assets("/Game/CyberWarden/Anims")):
    a = unreal.load_asset(pth)
    line = "%s (%s)" % (pth, a.get_class().get_name())
    if isinstance(a, unreal.AnimSequence):
        line += " len=%.3f frames=%s root_motion=%s root_lock=%s" % (a.get_play_length(), unreal.AnimationLibrary.get_num_frames(a), a.get_editor_property("enable_root_motion"), a.get_editor_property("force_root_lock"))
    out.append(line)
for l in out:
    unreal.log("[C0] " + l)
with open(unreal.Paths.project_saved_dir() + "C0_ProbeAnimApi.txt", "w") as fh:
    fh.write("\n".join(out))
unreal.SystemLibrary.quit_editor()
