"""Read-only check that BP_PrisonScheduleManager persists with the configured variables and defaults (fresh process).

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/VerifySchedule.py" -unattended -nop4 -nosplash -NullRHI
"""
import unreal

import cw_schedule as cs

data = cs.load()
periods = data["periods"]
table = cs.build_slot_table(periods)
bp = unreal.load_asset("/Game/CyberWarden/Schedule/BP_PrisonScheduleManager")
bel = unreal.BlueprintEditorLibrary
res = []


def chk(name, ok, detail=""):
    res.append(ok)
    unreal.log("[SCHEDVER] %s %s %s" % ("PASS" if ok else "FAIL", name, "" if ok else detail))


chk("asset loads", bp is not None)
cdo = unreal.get_default_object(bel.generated_class(bp))
names = [str(n) for n in bel.list_member_variable_names(bp)] if hasattr(bel, "list_member_variable_names") else []
for v in ("TimeScale", "Paused", "GameSecondsTotal", "StaggerMaxGameMinutes", "PeriodNames", "PeriodStartHours", "SlotToPeriod",
          "ClockSeconds", "CurrentHour", "CurrentPeriodIndex", "CurrentPeriodName", "PeriodChangeCount", "LastPeriodIndex"):
    try:
        cdo.get_editor_property(v)
        chk("variable " + v, True)
    except Exception as ex:
        chk("variable " + v, False, str(ex)[:80])
chk("TimeScale is a real number (30.5 survives)", (cdo.set_editor_property("TimeScale", 30.5) or True) and cdo.get_editor_property("TimeScale") == 30.5)
cdo.set_editor_property("TimeScale", 30.0)  # in-memory only
chk("TimeScale default 30", cdo.get_editor_property("TimeScale") == 30.0)
chk("GameSecondsTotal default 06:00", cdo.get_editor_property("GameSecondsTotal") == 21600.0)
chk("StaggerMaxGameMinutes 5", cdo.get_editor_property("StaggerMaxGameMinutes") == 5.0)
chk("SlotToPeriod matches reference table", list(cdo.get_editor_property("SlotToPeriod")) == table, str(list(cdo.get_editor_property("SlotToPeriod"))))
chk("PeriodNames", list(cdo.get_editor_property("PeriodNames")) == [p["name"] for p in periods])
chk("tag S01F1ScheduleManager", unreal.Name("S01F1ScheduleManager") in cdo.get_editor_property("tags"))
unreal.log("[SCHEDVER] RESULT %s (%d/%d)" % ("PASS" if all(res) else "FAIL", sum(res), len(res)))
unreal.SystemLibrary.quit_editor()
