"""Validate the M2.2 schedule JSON and test the clock/period logic. Read-only (writes only a text report).

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/ValidateSchedule.py" -unattended -nop4 -nosplash -NullRHI

Checks: schema; period lookup incl. the midnight wrap; accumulating-clock model (pause, scale change, wrap); every
assignment marker exists, is NavDest:Yes and is not within 250 cm of an opening; lockdown stops are the NPC's own cell
marker; assignments cover every enabled NPC of S01_LW_F1_npcs.json; stagger timing at the default scale.
Report: Docs/Layout/S01_LW_F1_schedule_report.txt. No system Python is installed, so this runs inside UnrealEditor-Cmd.
"""
import json
import math
import os

import unreal

import cw_layout
import cw_schedule as cs

PROJECT = unreal.Paths.project_dir()
out, errs, warns, tests = [], [], [], []


def rep(m=""):
    out.append(m)
    unreal.log("[SCHEDCHK] " + m)


def check(name, cond, detail=""):
    tests.append((name, bool(cond)))
    rep("  %s  %s%s" % ("PASS" if cond else "FAIL", name, (" - " + detail) if detail and not cond else ""))
    if not cond:
        errs.append("test failed: " + name)


data = cs.load()
layout = json.load(open(os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1.json"), encoding="utf-8"))
npcs = json.load(open(os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1_npcs.json"), encoding="utf-8"))

rep("== Schema ==")
cs.validate_schema(data, errs)
rep("  schema errors: %d" % len(errs))
periods = data["periods"]
pids = [p["id"] for p in periods]
table = cs.build_slot_table(periods)

rep("")
rep("== Period lookup (48 half-hour slots, %d periods) ==" % len(periods))
runs = []
for slot, idx in enumerate(table):
    if not runs or runs[-1][0] != idx:
        runs.append([idx, slot])
for idx, slot in runs:
    rep("  %s  %-22s (period index %d)" % (cs.format_time(slot * 1800)[:5], periods[idx]["name"], idx))
rep("  table = %s" % table)

T = lambda hhmm: cs.parse_time(hhmm)
check("table has 48 slots", len(table) == 48)
check("06:00 -> Wake-up", periods[cs.period_at(table, T("06:00"))]["id"] == "wake")
check("05:59:59 -> Lockdown (overnight carry)", periods[cs.period_at(table, T("06:00") - 1)]["id"] == "lockdown")
check("00:00 -> Lockdown (midnight wrap)", periods[cs.period_at(table, 0)]["id"] == "lockdown")
check("23:59:59 -> Lockdown", periods[cs.period_at(table, cs.DAY - 1)]["id"] == "lockdown")
check("86400 s wraps to 00:00 -> Lockdown", periods[cs.period_at(table, cs.DAY)]["id"] == "lockdown")
check("21:00 -> Lockdown", periods[cs.period_at(table, T("21:00"))]["id"] == "lockdown")
check("20:59:59 -> Free time", periods[cs.period_at(table, T("21:00") - 1)]["id"] == "free")
for p in periods:
    check("boundary %s at %s" % (p["id"], p["start"]), periods[cs.period_at(table, T(p["start"]))]["id"] == p["id"] and
          periods[cs.period_at(table, T(p["start"]) - 1)]["id"] != p["id"])

rep("")
rep("== Clock model (mirror of the Blueprint Tick) ==")
c = cs.ClockModel(table, T("06:00"), 30.0)
for _ in range(600):
    c.tick(0.1)  # 60 real seconds
check("30x for 60 real s advances 30 game minutes", abs(c.total - (T("06:00") + 1800)) < 1e-6, "total=%.3f" % c.total)
c.paused = True
before = c.total
for _ in range(100):
    c.tick(0.1)
check("paused clock does not advance", c.total == before)
c.paused = False
c.scale = 120.0
c.tick(1.0)
check("scale change keeps accumulated time (no reset)", abs(c.total - (before + 120.0)) < 1e-6, "total=%.3f" % c.total)
c = cs.ClockModel(table, T("23:59") + 30, 120.0)
seen = []
for _ in range(100):
    c.tick(0.1)
    seen.append((c.period, round(c.clock, 1)))
check("wraps past midnight, lockdown throughout", all(periods[p]["id"] == "lockdown" for p, _ in seen) and seen[-1][1] < 3600, "last=%s" % (seen[-1],))
c = cs.ClockModel(table, T("05:59"), 120.0)
trail = []
for _ in range(60):
    c.tick(0.1)
    trail.append(periods[c.period]["id"])
check("overnight lockdown ends at 06:00 (lockdown -> wake, one change)", trail[0] == "lockdown" and trail[-1] == "wake" and
      sum(1 for a, b in zip(trail, trail[1:]) if a != b) == 1)
c = cs.ClockModel(table, T("06:00"), 120.0)
changes = 0
prev = c.period
for _ in range(int(86400 / 120.0 / 0.05) + 5):
    c.tick(0.05)
    if c.period != prev:
        changes += 1
        prev = c.period
check("a full day at 120x produces one change per period (%d)" % len(periods), changes == len(periods), "changes=%d" % changes)

rep("")
rep("== Timing at the default scale ==")
scale = data["clock"]["time_scale"]
smax = data["clock"]["stagger_max_game_minutes"]
rep("  scale %gx: 1 game hour = %.0f real s; whole day = %.1f real min" % (scale, 3600 / scale, 86400 / scale / 60))
rep("  max stagger %g game min = %.1f real s" % (smax, smax * 60 / scale))
for i, p in enumerate(periods):
    dur = (T(periods[(i + 1) % len(periods)]["start"]) - T(p["start"])) % cs.DAY
    rep("  %-22s %5.1f game h = %5.0f real s at %gx, %5.0f s at dev %gx" % (p["name"], dur / 3600, dur / scale, scale, dur / data["clock"]["dev_time_scale"], data["clock"]["dev_time_scale"]))
for nid, a in data["assignments"].items():
    rep("  %s stagger = %.2f x %g min = %.1f game min = %.1f real s" % (nid, a["stagger_fraction"], smax, a["stagger_fraction"] * smax, a["stagger_fraction"] * smax * 60 / scale))

rep("")
rep("== Assignment markers ==")
ex = cw_layout.expand(layout)
types = layout["marker_types"]
markers = {m["id"]: m for m in layout["markers"] + ex["markers"]}
for b in layout["boxes"]:  # cafeteria seats are generated by the builder: Seat_<Table_n>_<1..6>
    if b.get("seats"):
        cx, cy = (b["x0"] + b["x1"]) / 2.0, (b["y0"] + b["y1"]) / 2.0
        n = 0
        for side in (-1, 1):
            for dx in (-100, 0, 100):
                n += 1
                markers["Seat_%s_%d" % (b["id"].replace("Prop_Caf_", ""), n)] = {"id": "Seat_%s_%d" % (b["id"].replace("Prop_Caf_", ""), n),
                    "type": "CafeteriaSeat", "x": cx + dx, "y": cy + side * 95, "z": 0}
openings = [(o["id"], (o["coord"], o["center"]) if o["axis"] == "v" else (o["center"], o["coord"])) for o in layout["openings"] + ex["openings"]
            if o.get("z0", 0) == 0 and o.get("kind") != "secured"]
enabled = {n["id"]: n for n in npcs["npcs"] if n.get("enabled", True)}
check("assignments cover exactly the enabled NPCs", set(data["assignments"]) == set(enabled), "%s vs %s" % (sorted(data["assignments"]), sorted(enabled)))
used = {}
for nid, a in data["assignments"].items():
    cell = enabled.get(nid, {}).get("cell", "")
    for pid, e in a["schedule"].items():
        for mid in e["stops"]:
            m = markers.get(mid)
            if m is None:
                errs.append("%s/%s: marker %s does not exist" % (nid, pid, mid))
                continue
            if not types.get(m["type"], {}).get("nav", False):
                errs.append("%s/%s: marker %s (%s) is not a navigation destination" % (nid, pid, mid, m["type"]))
            near = min((math.hypot(m["x"] - ox, m["y"] - oy), oid) for oid, (ox, oy) in openings)
            own_cell = m["id"] == "Lockdown_" + cell  # the lockdown spot is inside the NPC's own cell (200 cm from its door by design)
            if near[0] < cs.MIN_OPENING_DISTANCE and not own_cell:
                errs.append("%s/%s: marker %s is %.0f cm from opening %s (< %d)" % (nid, pid, mid, near[0], near[1], cs.MIN_OPENING_DISTANCE))
            used.setdefault(mid, []).append("%s/%s" % (nid, pid))
        if pid == "lockdown" and e["stops"] != ["Lockdown_" + cell]:
            errs.append("%s: lockdown stops must be exactly [Lockdown_%s]" % (nid, cell))
check("all assignment markers exist, NavDest:Yes, >= %d cm from openings, lockdown = own cell" % cs.MIN_OPENING_DISTANCE, not [e for e in errs if "/" in e or "lockdown" in e])
rep("  distinct markers used: %d" % len(used))

rep("")
rep("== Proposed assignments (stops; idle seconds real time) ==")
for nid, a in data["assignments"].items():
    rep("  %s (%s, cell %s, stagger %.2f)" % (nid, enabled.get(nid, {}).get("archetype", "?"), enabled.get(nid, {}).get("cell", "?"), a["stagger_fraction"]))
    for p in periods:
        e = a["schedule"][p["id"]]
        rep("    %s %-22s %-70s idle %g-%g s" % (p["start"], p["name"], ", ".join(e["stops"]), e["idle"][0], e["idle"][1]))

rep("")
if errs:
    rep("RESULT: FAIL (%d problem(s))" % len(errs))
    for e in errs:
        rep("  - " + e)
else:
    rep("RESULT: PASS (%d checks, 0 problems)" % len(tests))

with open(os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1_schedule_report.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
unreal.SystemLibrary.quit_editor()
