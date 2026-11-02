"""Add the C++ PrisonScheduleComponent to BP_PrisonNPC (idempotent). Close the interactive editor first (asset save).

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/AddScheduleComponent.py" -unattended -nop4 -nosplash -NullRHI

Only adds the component. It does not touch the StateTree, the controller, the tasks, the placed NPCs or any graph.
"""
import unreal

PATH = "/Game/CyberWarden/NPC/BP_PrisonNPC"
bel = unreal.BlueprintEditorLibrary


def log(m):
    unreal.log("[ADDSCHED] " + m)


if not hasattr(unreal, "PrisonScheduleComponent"):
    unreal.log_error("[ADDSCHED] C++ class PrisonScheduleComponent missing: build the module first (Tools/BuildCpp.ps1)")
    unreal.SystemLibrary.quit_editor()
    raise SystemExit

bp = unreal.load_asset(PATH)
sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
handles = sub.k2_gather_subobject_data_for_blueprint(bp)
names = []
for h in handles:
    d = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h)
    obj = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(d)
    names.append(obj.get_name() if obj else "?")
if any("PrisonSchedule" in n for n in names):
    log("EXISTS: component already present (%s)" % [n for n in names if "PrisonSchedule" in n])
else:
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=unreal.PrisonScheduleComponent, blueprint_context=bp)
    new_handle, fail = sub.add_new_subobject(params)
    sub.rename_subobject(new_handle, "PrisonSchedule")
    bel.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    log("added component PrisonSchedule (PrisonScheduleComponent) to BP_PrisonNPC; fail reason: %r" % (fail,))
unreal.SystemLibrary.quit_editor()
