"""Headless PIE test of the schedule manager clock (run AFTER the Tick graph has been wired by hand). Saves nothing.

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/ClockPieTest.py" -unattended -nop4 -nosplash -NullRHI

Spawns a temporary BP_PrisonScheduleManager (CLOCK_TEST_CLASS=cpp: the C++ APrisonScheduleManager) in the PIE world (never saved) and drives it from Python at 120x: rate,
pause, time-scale change without reset, the midnight wrap (overnight lockdown), the 06:00 boundary, all 48 half-hour
slots against the reference table, and the optional PeriodChangeCount. No full-day playthrough is needed: the clock is
jumped to just before each boundary. Exit code 6 with "TICK GRAPH NOT WIRED" means the manual step is not done yet.
"""
import os
import sys

import unreal

import cw_schedule as cs

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
data = cs.load()
periods = data["periods"]
table = cs.build_slot_table(periods)
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "wait_until": None, "res": []}


def log(m):
    unreal.log("[CLOCKTEST] " + m)


def check(name, ok, detail=""):
    S["res"].append(bool(ok))
    log("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  (%s)" % detail))


def finish(code):
    unreal.unregister_slate_post_tick_callback(S["h"])
    log("RESULT %s (%d/%d checks)" % ("PASS" if code == 0 else "FAIL/INCOMPLETE", sum(S["res"]), len(S["res"])))
    level_sub.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


CPP = os.environ.get("CLOCK_TEST_CLASS", "bp") in ("cpp", "bp")  # default: the BP child of the C++ class; "cpp" = the native class; "legacy" = the Stage 1 empty Blueprint shell
_CPP_NAMES = {"TimeScale": "time_scale", "Paused": "paused", "GameSecondsTotal": "game_seconds_total", "ClockSeconds": "clock_seconds",
              "CurrentHour": "current_hour", "CurrentPeriodIndex": "current_period_index", "CurrentPeriodName": "current_period_name",
              "PeriodChangeCount": "period_change_count", "LastPeriodIndex": "last_period_index"}


def pn(k):
    return _CPP_NAMES.get(k, k) if CPP else k


def sp(m, k, v):
    m.set_editor_property(pn(k), v)


def g(m, k):
    if os.environ.get("CLOCK_TEST_SIMULATE") == "1" and k in S.get("shadow", {}):
        return S["shadow"][k]  # runtime variables are not instance-editable, so the simulation keeps them here
    return m.get_editor_property(pn(k))


def run(gw):
    found = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")
    if not found:
        log("FAILED: temporary manager missing in the PIE world")
        finish(4)
        return
    m = found[0]
    S["mgr"] = m
    log("temporary manager in PIE world: %s" % m.get_name())
    sp(m, "TimeScale", 120.0)
    sp(m, "GameSecondsTotal", float(cs.parse_time("06:00")))
    t0 = g(m, "GameSecondsTotal")
    yield ("ticks", 20)
    if g(m, "GameSecondsTotal") == t0:
        log("TICK GRAPH NOT WIRED: GameSecondsTotal did not advance (see Docs/NPC/M2_2_Schedule_Design.md section 5). Nothing else can be tested.")
        finish(6)
        return
    # 1. rate: game-time vs clock-time
    a = g(m, "GameSecondsTotal")
    ga = unreal.GameplayStatics.get_time_seconds(gw)
    yield ("secs", 3.0)
    b = g(m, "GameSecondsTotal")
    gb = unreal.GameplayStatics.get_time_seconds(gw)
    rate = (b - a) / max(gb - ga, 1e-6)
    check("advances at TimeScale 120 (+-2%%): %.1f game s per real s" % rate, abs(rate - 120.0) < 2.4, "rate=%.2f" % rate)
    # 2. pause
    sp(m, "Paused", True)
    yield ("ticks", 3)
    a = g(m, "GameSecondsTotal")
    yield ("secs", 1.5)
    check("pause freezes the clock", g(m, "GameSecondsTotal") == a, "%.2f -> %.2f" % (a, g(m, "GameSecondsTotal")))
    sp(m, "Paused", False)
    yield ("secs", 0.5)
    check("unpause resumes from the same time (no reset)", g(m, "GameSecondsTotal") > a and g(m, "GameSecondsTotal") - a < 400, "total=%.2f was %.2f" % (g(m, "GameSecondsTotal"), a))
    # 3. scale change
    a = g(m, "GameSecondsTotal")
    sp(m, "TimeScale", 30.0)
    yield ("secs", 1.0)
    d = g(m, "GameSecondsTotal") - a
    check("scale 120 -> 30 keeps accumulated time and slows to ~30/s (delta %.1f)" % d, 15.0 < d < 60.0, "delta=%.2f paused=%s scale=%s a=%.1f now=%.1f" % (d, g(m, "Paused"), g(m, "TimeScale"), a, g(m, "GameSecondsTotal")))
    sp(m, "TimeScale", 120.0)
    # 4. midnight wrap
    sp(m, "GameSecondsTotal", float(cs.DAY - 90.0))
    seen, wrapped = [], False
    for _ in range(16):
        yield ("secs", 0.25)
        cl = g(m, "ClockSeconds")
        seen.append((round(cl, 1), int(g(m, "CurrentPeriodIndex"))))
    wrapped = any(cl < 600 for cl, _ in seen)
    check("clock wraps past 24:00 (ClockSeconds back near 0)", wrapped, str(seen[-3:]))
    check("lockdown (index 7) held across midnight", all(i == 7 for _, i in seen), str(seen))
    check("total keeps counting (unwrapped) after the wrap", g(m, "GameSecondsTotal") > cs.DAY, "total=%.1f" % g(m, "GameSecondsTotal"))
    check("CurrentPeriodName is Lockdown", str(g(m, "CurrentPeriodName")) == "Lockdown", str(g(m, "CurrentPeriodName")))
    # 5. 06:00 boundary
    sp(m, "GameSecondsTotal", float(cs.parse_time("06:00") - 60.0))
    idx = []
    for _ in range(16):
        yield ("secs", 0.25)
        idx.append(int(g(m, "CurrentPeriodIndex")))
    changes = sum(1 for x, y in zip(idx, idx[1:]) if x != y)
    check("06:00 boundary: Lockdown -> Wake-up exactly once", idx[0] == 7 and idx[-1] == 0 and changes == 1, str(idx))
    # 6. every half hour slot
    sp(m, "Paused", True)
    bad = []
    for slot in range(48):
        sp(m, "GameSecondsTotal", slot * 1800.0 + 900.0)
        sp(m, "Paused", False)
        yield ("ticks", 2)
        sp(m, "Paused", True)
        got = int(g(m, "CurrentPeriodIndex"))
        if got != table[slot]:
            bad.append((slot, got, table[slot]))
    check("all 48 half-hour slots match the reference table", not bad, str(bad[:4]))
    # 7. optional graph part B
    sp(m, "Paused", False)
    sp(m, "TimeScale", 120.0)
    sp(m, "GameSecondsTotal", float(cs.parse_time("11:59") + 30.0))
    c0 = int(g(m, "PeriodChangeCount"))
    yield ("secs", 1.0)
    c1 = int(g(m, "PeriodChangeCount"))
    log("optional part B (PeriodChangeCount): %d -> %d %s" % (c0, c1, "(wired)" if c1 > c0 else "(not wired or not triggered - optional)"))
    finish(0 if all(S["res"]) else 3)


def simulate(gw):
    """CLOCK_TEST_SIMULATE=1: stand in for the Blueprint Tick graph with the Python reference model (proves THIS test).
    Never use for acceptance: the real result requires the hand-wired graph."""
    if os.environ.get("CLOCK_TEST_SIMULATE") != "1" or "mgr" not in S:
        return
    now = unreal.GameplayStatics.get_time_seconds(gw)
    last, S["sim_t"] = S.get("sim_t", now), now
    m = S["mgr"]
    if os.environ.get("CLOCK_TEST_TRACE") == "1" and 6.5 < now < 7.7:
        log("sim now=%.3f last=%.3f paused=%s scale=%s total=%.1f" % (now, last, g(m, "Paused"), g(m, "TimeScale"), g(m, "GameSecondsTotal")))
    if not g(m, "Paused"):
        sp(m, "GameSecondsTotal", g(m, "GameSecondsTotal") + (now - last) * g(m, "TimeScale"))
    clock = g(m, "GameSecondsTotal") % cs.DAY
    idx = cs.period_at(table, clock)
    sh = S.setdefault("shadow", {"PeriodChangeCount": 0, "LastPeriodIndex": idx})
    if idx != sh["LastPeriodIndex"]:
        sh["PeriodChangeCount"] += 1
        sh["LastPeriodIndex"] = idx
    sh.update(ClockSeconds=clock, CurrentHour=clock / 3600.0, CurrentPeriodIndex=idx, CurrentPeriodName=periods[idx]["name"])


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            cls = unreal.PrisonScheduleManager if os.environ.get("CLOCK_TEST_CLASS") == "cpp" else unreal.EditorAssetLibrary.load_blueprint_class("/Game/CyberWarden/Schedule/BP_PrisonScheduleManager")
            unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(cls, unreal.Vector(0, 0, 0))  # editor world copy only, never saved
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 40000:
            log("FAILED: timeout")
            finish(2)
            return
        if not S["pie"]:
            return
        gw = ues.get_game_world()
        if gw is None:
            return
        S["post"] += 1
        if S["post"] < 60:
            return
        if S["gen"] is None:
            S["gen"] = run(gw)
        simulate(gw)
        if S["wait"] > 0:
            S["wait"] -= 1
            return
        if S["wait_until"] is not None:
            if unreal.GameplayStatics.get_time_seconds(gw) < S["wait_until"]:
                return
            S["wait_until"] = None
        try:
            kind, v = next(S["gen"])
            if os.environ.get("CLOCK_TEST_TRACE") == "1":
                log("trace %s %s at game t=%.3f total=%.1f" % (kind, v, unreal.GameplayStatics.get_time_seconds(gw), g(S["mgr"], "GameSecondsTotal")))
        except StopIteration:
            return
        if kind == "ticks":
            S["wait"] = int(v)
        else:
            S["wait_until"] = unreal.GameplayStatics.get_time_seconds(gw) + v
    except Exception as ex:
        import traceback
        log("EXCEPTION %s\n%s" % (ex, traceback.format_exc()))
        finish(9)


S["h"] = unreal.register_slate_post_tick_callback(tick)
