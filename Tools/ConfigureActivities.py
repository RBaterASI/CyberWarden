"""Generate the M2.3 activity data asset from Docs/Layout/S01_LW_F1_activities.json, reference it from the schedule manager and
add the activity component to BP_PrisonNPC. Idempotent. Close the interactive editor first (asset saves).

  powershell -File Tools/RunHeadless.ps1 -Script Tools/ConfigureActivities.py -Log <abs log>

Touches: DA_S01_LW_F1_Activities (new), BP_PrisonScheduleManager (default ActivityData) and BP_PrisonNPC (one added component).
Not touched: any StateTree, the controller, the tasks, the level, ABP_PrisonNPC.
"""
import unreal

import cw_activity as ca

DIR = "/Game/CyberWarden/Schedule"
NAME = "DA_S01_LW_F1_Activities"
PATH = "%s/%s" % (DIR, NAME)
bel = unreal.BlueprintEditorLibrary
eal = unreal.EditorAssetLibrary


def log(m):
    unreal.log("[ACTCFG] " + m)


if not hasattr(unreal, "PrisonActivityComponent"):
    unreal.log_error("[ACTCFG] C++ activity classes missing: build the module first (Tools/BuildCpp.ps1)")
    unreal.SystemLibrary.quit_editor()
    raise SystemExit

data = ca.load()
layout = ca.load_layout()
errs = []
ca.validate_schema(data, layout, errs)
if errs:
    unreal.log_error("[ACTCFG] activity JSON is invalid: %s" % errs)
    unreal.SystemLibrary.quit_editor()
    raise SystemExit

da = unreal.load_asset(PATH) if eal.does_asset_exist(PATH) else None
if da is None:
    da = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, DIR, unreal.PrisonActivityData, unreal.DataAssetFactory())
    log("CREATED " + PATH)


def seq(path):
    return unreal.load_asset(path) if path else None


FACING = {"none": unreal.PrisonFacingMode.NONE, "yaw": unreal.PrisonFacingMode.YAW, "point": unreal.PrisonFacingMode.POINT}
acts = []
for a in data["activities"]:
    acts.append(unreal.PrisonActivityDefinition(
        id=a["id"], enter_animation=seq(a.get("enter_animation")), loop_animation=seq(a.get("loop_animation")), exit_animation=seq(a.get("exit_animation")),
        slot_name=a["slot"], blend_in_seconds=a["blend_in_seconds"], blend_out_seconds=a["blend_out_seconds"], play_rate=a["play_rate"],
        randomize_loop_start=a["randomize_loop_start"], align_yaw_rate_deg_per_sec=a["align_yaw_rate_deg_per_sec"], yaw_tolerance_degrees=a["yaw_tolerance_degrees"]))
pts = []
for p in data["interaction_points"]:
    mode, yaw, target = ca.resolve_facing(p, layout)
    pts.append(unreal.PrisonInteractionPoint(
        marker_id=p["marker_id"], activity_id=p["activity"], facing_mode=FACING[mode], facing_yaw_degrees=yaw,
        facing_point=unreal.Vector(target[0], target[1], target[2]), arrival_tolerance_cm=p["arrival_tolerance_cm"], capacity=p["capacity"]))
da.set_editor_property("activities", acts)
da.set_editor_property("points", pts)
errors = list(da.validate_data())
if errors:
    unreal.log_error("[ACTCFG] data asset is invalid: %s" % errors)
eal.save_loaded_asset(da)
log("data asset: %d activities, %d interaction points, %d validation errors" % (len(acts), len(pts), len(errors)))

# schedule manager default
mgr_bp = unreal.load_asset("/Game/CyberWarden/Schedule/BP_PrisonScheduleManager")
bel.compile_blueprint(mgr_bp)
unreal.get_default_object(bel.generated_class(mgr_bp)).set_editor_property("activity_data", da)
bel.compile_blueprint(mgr_bp)
eal.save_loaded_asset(mgr_bp)
log("BP_PrisonScheduleManager.ActivityData -> %s" % NAME)

# activity component on the prisoner Blueprint
npc = unreal.load_asset("/Game/CyberWarden/NPC/BP_PrisonNPC")
sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
handles = sub.k2_gather_subobject_data_for_blueprint(npc)
names = []
for h in handles:
    d = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h)
    obj = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(d)
    names.append(obj.get_name() if obj else "?")
if any("PrisonActivity" in n for n in names):
    log("BP_PrisonNPC already has the activity component")
else:
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=unreal.PrisonActivityComponent, blueprint_context=npc)
    new_handle, fail = sub.add_new_subobject(params)
    sub.rename_subobject(new_handle, "PrisonActivity")
    bel.compile_blueprint(npc)
    eal.save_loaded_asset(npc)
    log("added component PrisonActivity to BP_PrisonNPC (fail reason: %r)" % (fail,))
unreal.SystemLibrary.quit_editor()
