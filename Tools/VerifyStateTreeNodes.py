"""Read-only check that the native StateTree nodes of M2.2 Checkpoint B are registered (they must appear in the StateTree editor).

  powershell -File Tools\RunHeadless.ps1 -Script Tools\VerifyStateTreeNodes.py
"""
import unreal

res = []


def chk(name, ok, detail=""):
    res.append(bool(ok))
    unreal.log("[STNODES] %s %s %s" % ("PASS" if ok else "FAIL", name, "" if ok else detail))


for path, label in (("/Script/CyberWarden.PrisonPlanDestinationTask", "Prison: Plan Destination (task)"),
                    ("/Script/CyberWarden.PrisonReplanRequestedCondition", "Prison: Replan Requested (condition)"),
                    ("/Script/CyberWarden.PrisonPlanDestinationInstanceData", "task instance data"),
                    ("/Script/CyberWarden.PrisonReplanRequestedConditionInstanceData", "condition instance data")):
    s = unreal.load_object(None, path)
    chk("registered: " + label, s is not None, path)
    if s is not None:
        try:
            sup = s.get_super_struct() if hasattr(s, "get_super_struct") else None
            unreal.log("[STNODES]   %s super=%s" % (label, sup.get_name() if sup else "n/a"))
        except Exception as ex:
            unreal.log("[STNODES]   (super struct not readable: %s)" % str(ex)[:60])
for built_in, label in (("/Script/GameplayStateTreeModule.StateTreeMoveToTask", "built-in Move To task"),
                        ("/Script/StateTreeModule.StateTreeDelayTask", "built-in Delay Task"),
                        ("/Script/StateTreeModule.StateTreeCompareBoolCondition", "built-in Bool Compare condition")):
    chk("available: " + label, unreal.load_object(None, built_in) is not None, built_in)
chk("component class available", hasattr(unreal, "PrisonScheduleComponent"))
unreal.log("[STNODES] RESULT %s (%d/%d)" % ("PASS" if all(res) else "FAIL", sum(res), len(res)))
unreal.SystemLibrary.quit_editor()
