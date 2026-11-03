"""Create/configure BP_PrisonScheduleManager, a Blueprint child of the C++ class APrisonScheduleManager.

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/ConfigureSchedule.py" -unattended -nop4 -nosplash -NullRHI

Requires the CyberWarden C++ module to be built (Tools/BuildCpp.ps1). The clock and period logic live in C++; this asset
only carries the DEFAULT VALUES from Docs/Layout/S01_LW_F1_schedule.json, so the JSON stays the source of truth.
If /Game/CyberWarden/Schedule/BP_PrisonScheduleManager exists with a non-C++ parent (the M2.2 Stage 1 empty Blueprint
shell), it is replaced. If it already derives from the C++ class, only the default values are rewritten.
Close the interactive editor first (asset save). No level is modified.
"""
import unreal

import cw_schedule as cs

DIR = "/Game/CyberWarden/Schedule"
NAME = "BP_PrisonScheduleManager"
PATH = "%s/%s" % (DIR, NAME)
bel = unreal.BlueprintEditorLibrary
eal = unreal.EditorAssetLibrary


def log(m):
    unreal.log("[SCHEDCFG] " + m)


if not hasattr(unreal, "PrisonScheduleManager"):
    unreal.log_error("[SCHEDCFG] C++ class PrisonScheduleManager not found: build the CyberWarden module first")
    unreal.SystemLibrary.quit_editor()
    raise SystemExit

data = cs.load()
periods = data["periods"]
table = cs.build_slot_table(periods)
start = cs.parse_time(data["clock"]["start_time"])

bp = unreal.load_asset(PATH) if eal.does_asset_exist(PATH) else None
if bp is not None:
    parent = bel.get_blueprint_parent_class(bp)
    if parent is None or parent.get_name() != "PrisonScheduleManager":
        log("replacing the Stage 1 Blueprint shell (parent %s)" % (parent.get_name() if parent else None))
        del bp
        eal.delete_asset(PATH)
        bp = None
if bp is None:
    eal.make_directory(DIR)
    fac = unreal.BlueprintFactory()
    fac.set_editor_property("parent_class", unreal.PrisonScheduleManager)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, DIR, unreal.Blueprint, fac)
    log("CREATED %s (parent PrisonScheduleManager, C++)" % PATH)

# The data asset is the single in-engine copy of periods and per-NPC assignments (generated from the JSON).
DA_NAME = "DA_S01_LW_F1_Schedule"
DA_PATH = "%s/%s" % (DIR, DA_NAME)
da = unreal.load_asset(DA_PATH) if eal.does_asset_exist(DA_PATH) else None
if da is None:
    da = unreal.AssetToolsHelpers.get_asset_tools().create_asset(DA_NAME, DIR, unreal.PrisonScheduleData, unreal.DataAssetFactory())
    log("CREATED " + DA_PATH)
da.set_editor_property("sector_id", data["sector"])
da.set_editor_property("periods", [unreal.PrisonPeriodDef(id=p["id"], name=p["name"], start_hours=cs.parse_time(p["start"]) / 3600.0) for p in periods])
npcs = []
for nid, a in data["assignments"].items():
    npcs.append(unreal.PrisonNpcSchedule(
        npc_id=nid, stagger_fraction=float(a["stagger_fraction"]),
        periods=[unreal.PrisonPeriodAssignment(period_id=pid, stop_marker_ids=list(e["stops"]), idle_min=float(e["idle"][0]), idle_max=float(e["idle"][1]))
                 for pid, e in a["schedule"].items()]))
da.set_editor_property("npcs", npcs)
errs = list(da.validate_data())
if errs:
    unreal.log_error("[SCHEDCFG] schedule data asset is invalid: %s" % errs)
eal.save_loaded_asset(da)
log("data asset: %d periods, %d NPC schedules, %d validation errors" % (len(periods), len(npcs), len(errs)))

bel.compile_blueprint(bp)
cdo = unreal.get_default_object(bel.generated_class(bp))
cdo.set_editor_property("schedule_data", da)
cdo.set_editor_property("time_scale", float(data["clock"]["time_scale"]))
cdo.set_editor_property("paused", False)
cdo.set_editor_property("game_seconds_total", float(start))
cdo.set_editor_property("stagger_max_game_minutes", float(data["clock"]["stagger_max_game_minutes"]))
cdo.set_editor_property("period_names", [p["name"] for p in periods])
cdo.set_editor_property("period_start_hours", [cs.parse_time(p["start"]) / 3600.0 for p in periods])
ok = cdo.rebuild_slot_table()
got = list(cdo.get_editor_property("slot_to_period"))
if not ok or got != table:
    unreal.log_error("[SCHEDCFG] C++ slot table differs from the Python reference table: %s vs %s" % (got, table))
bel.compile_blueprint(bp)
eal.save_loaded_asset(bp)
log("configured: start %s, scale %gx, stagger max %g game min, %d periods, slot table %s" % (
    data["clock"]["start_time"], data["clock"]["time_scale"], data["clock"]["stagger_max_game_minutes"], len(periods),
    "matches the reference" if got == table else "MISMATCH"))
unreal.SystemLibrary.quit_editor()
