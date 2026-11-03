"""Read-only probe (M2.3 Stage C0): is the IK Rig / IK Retargeter / FBX import Python API available in this editor? Only checks
that the classes exist; never loads, creates or saves an asset. The only file it writes is the text report in the git-ignored
Saved/ folder.

  powershell -File Tools\\RunHeadless.ps1 -Script Tools\\ProbeRetargetApi.py
"""
import unreal

out = []
for n in ("IKRigDefinition", "IKRigController", "IKRetargeter", "IKRetargeterController", "IKRigDefinitionFactory",
          "IKRetargetFactory", "IKRetargetBatchOperation", "FbxImportUI", "AssetImportTask", "AnimSequence"):
    out.append("%s: %s" % (n, hasattr(unreal, n)))
if hasattr(unreal, "IKRigController"):
    out.append("IKRigController methods: %s" % [d for d in dir(unreal.IKRigController) if not d.startswith("_")][:60])
if hasattr(unreal, "IKRetargeterController"):
    out.append("IKRetargeterController methods: %s" % [d for d in dir(unreal.IKRetargeterController) if not d.startswith("_")][:60])
if hasattr(unreal, "IKRetargetBatchOperation"):
    out.append("IKRetargetBatchOperation: %s" % [d for d in dir(unreal.IKRetargetBatchOperation) if not d.startswith("_")][:30])
for l in out:
    unreal.log("[C0] " + l)
with open(unreal.Paths.project_saved_dir() + "ProbeRetargetApi.txt", "w") as fh:
    fh.write("\n".join(out))
unreal.SystemLibrary.quit_editor()
