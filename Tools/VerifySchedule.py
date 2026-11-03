"""Read-only check that BP_PrisonScheduleManager (child of the C++ APrisonScheduleManager) persists with the JSON defaults.

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/VerifySchedule.py" -unattended -nop4 -nosplash -NullRHI
"""
import unreal

import cw_schedule as cs

data = cs.load()
periods = data["periods"]
table = cs.build_slot_table(periods)
bel = unreal.BlueprintEditorLibrary
bp = unreal.load_asset("/Game/CyberWarden/Schedule/BP_PrisonScheduleManager")
res = []


def chk(name, ok, detail=""):
    res.append(bool(ok))
    unreal.log("[SCHEDVER] %s %s %s" % ("PASS" if ok else "FAIL", name, "" if ok else detail))


chk("asset loads", bp is not None)
parent = bel.get_blueprint_parent_class(bp)
chk("parent is the C++ class PrisonScheduleManager", parent is not None and parent.get_name() == "PrisonScheduleManager", str(parent))
cdo = unreal.get_default_object(bel.generated_class(bp))
for v in ("time_scale", "paused", "game_seconds_total", "stagger_max_game_minutes", "period_names", "period_start_hours", "slot_to_period",
          "clock_seconds", "current_hour", "current_period_index", "current_period_name", "day_number", "period_change_count", "last_period_index"):
    try:
        cdo.get_editor_property(v)
        chk("property " + v, True)
    except Exception as ex:
        chk("property " + v, False, str(ex)[:80])
chk("time_scale default 30", cdo.get_editor_property("time_scale") == 30.0)
chk("game_seconds_total default 06:00", cdo.get_editor_property("game_seconds_total") == cs.parse_time(data["clock"]["start_time"]))
chk("stagger_max_game_minutes 5", cdo.get_editor_property("stagger_max_game_minutes") == data["clock"]["stagger_max_game_minutes"])
chk("period_names match JSON", list(cdo.get_editor_property("period_names")) == [p["name"] for p in periods])
chk("period_start_hours match JSON", [round(x, 6) for x in cdo.get_editor_property("period_start_hours")] == [round(cs.parse_time(p["start"]) / 3600.0, 6) for p in periods])
chk("slot_to_period matches the reference table", list(cdo.get_editor_property("slot_to_period")) == table)
chk("tag S01F1ScheduleManager", unreal.Name("S01F1ScheduleManager") in cdo.get_editor_property("tags"))
unreal.log("[SCHEDVER] RESULT %s (%d/%d)" % ("PASS" if all(res) else "FAIL", sum(res), len(res)))
unreal.SystemLibrary.quit_editor()
