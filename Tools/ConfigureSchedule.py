"""Create (if missing) and configure the M2.2 schedule manager Blueprint shell. Non-destructive for graphs.

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/ConfigureSchedule.py" -unattended -nop4 -nosplash -NullRHI

Creates /Game/CyberWarden/Schedule/BP_PrisonScheduleManager (Actor) with its variables if the asset does not exist.
If it exists (its Tick graph may have been wired by hand) NOTHING is added or removed: only the default VALUES of the
variables are rewritten from Docs/Layout/S01_LW_F1_schedule.json. The Tick graph itself is manual:
see Docs/NPC/M2_2_Schedule_Design.md. Close the interactive editor first (asset save). No level is modified.
"""
import unreal

import cw_schedule as cs

DIR = "/Game/CyberWarden/Schedule"
NAME = "BP_PrisonScheduleManager"
PATH = "%s/%s" % (DIR, NAME)
bel = unreal.BlueprintEditorLibrary
eal = unreal.EditorAssetLibrary
# NOTE: get_basic_type_by_name("float") yields an INTEGER-like variable (1.75 reads back as 1); "real" is the true float (double).
T = {"float": bel.get_basic_type_by_name("real"), "int": bel.get_basic_type_by_name("int"),
     "bool": bel.get_basic_type_by_name("bool"), "string": bel.get_basic_type_by_name("string")}
for k in ("float", "int", "string"):
    T[k + "_array"] = bel.get_array_type(T[k])


def log(m):
    unreal.log("[SCHEDCFG] " + m)


# (name, type, instance_editable, category)
VARS = [
    ("TimeScale", "float", True, "Clock"),
    ("Paused", "bool", True, "Clock"),
    ("GameSecondsTotal", "float", True, "Clock"),          # unwrapped accumulator; its default is the start time
    ("StaggerMaxGameMinutes", "float", True, "Clock"),
    ("PeriodNames", "string_array", True, "Schedule"),
    ("PeriodStartHours", "float_array", True, "Schedule"),
    ("SlotToPeriod", "int_array", True, "Schedule"),       # 48 half-hour slots -> period index (midnight wrap built in)
    ("ClockSeconds", "float", False, "Runtime"),           # GameSecondsTotal wrapped to 0..86400
    ("CurrentHour", "float", False, "Runtime"),
    ("CurrentPeriodIndex", "int", False, "Runtime"),
    ("CurrentPeriodName", "string", False, "Runtime"),
    ("PeriodChangeCount", "int", False, "Runtime"),        # optional graph part B
    ("LastPeriodIndex", "int", False, "Runtime"),          # optional graph part B
]

data = cs.load()
periods = data["periods"]
table = cs.build_slot_table(periods)
start = cs.parse_time(data["clock"]["start_time"])
start_idx = cs.period_at(table, start)

created = False
if not eal.does_asset_exist(PATH):
    eal.make_directory(DIR)
    fac = unreal.BlueprintFactory()
    fac.set_editor_property("parent_class", unreal.Actor)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, DIR, unreal.Blueprint, fac)
    for name, tkey, editable, cat in VARS:
        if not bel.add_member_variable(bp, name, T[tkey]):
            log("  !! could not add variable " + name)
            continue
        if editable:
            bel.set_blueprint_variable_instance_editable(bp, name, True)
        bel.set_blueprint_variable_category(bp, name, cat)
    bel.compile_blueprint(bp)
    created = True
    log("CREATED " + PATH)
else:
    bp = unreal.load_asset(PATH)
    log("EXISTS: only default values are rewritten (graphs untouched)")

cdo = unreal.get_default_object(bel.generated_class(bp))
vals = {
    "TimeScale": float(data["clock"]["time_scale"]),
    "Paused": False,
    "GameSecondsTotal": float(start),
    "StaggerMaxGameMinutes": float(data["clock"]["stagger_max_game_minutes"]),
    "PeriodNames": [p["name"] for p in periods],
    "PeriodStartHours": [cs.parse_time(p["start"]) / 3600.0 for p in periods],
    "SlotToPeriod": table,
    "ClockSeconds": float(start % cs.DAY),
    "CurrentHour": float(start % cs.DAY) / 3600.0,
    "CurrentPeriodIndex": start_idx,
    "CurrentPeriodName": periods[start_idx]["name"],
    "PeriodChangeCount": 0,
    "LastPeriodIndex": start_idx,
}
for k, v in vals.items():
    cdo.set_editor_property(k, v)
try:
    cdo.set_editor_property("tags", [unreal.Name("S01F1ScheduleManager")])
except Exception as ex:
    log("  tags not set: %s" % ex)
try:
    tick = cdo.get_editor_property("primary_actor_tick")
    tick.set_editor_property("start_with_tick_enabled", True)
    cdo.set_editor_property("primary_actor_tick", tick)
except Exception as ex:
    log("  tick settings not set: %s" % ex)
bel.compile_blueprint(bp)
eal.save_loaded_asset(bp)
log("configured: start %s (period '%s'), scale %gx, stagger max %g game min, %d periods, 48-slot table written" % (
    data["clock"]["start_time"], periods[start_idx]["name"], data["clock"]["time_scale"], data["clock"]["stagger_max_game_minutes"], len(periods)))
log("done (created=%s)" % created)
unreal.SystemLibrary.quit_editor()
