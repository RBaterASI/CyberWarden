"""M2.2 schedule support: loading, validation, half-hour period lookup and a reference model of the clock.

Pure Python (no `unreal` import) so it can be used by the asset configuration tool, the validator, the editor-only
debug overlay and the tests. The Blueprint clock (BP_PrisonScheduleManager.Tick) must behave exactly like ClockModel.
"""
import json
import math
import os

DAY = 86400.0
SLOT_SECONDS = 1800.0
SLOTS = 48
MIN_OPENING_DISTANCE = 250.0


def project_dir():
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def load(path=None):
    path = path or os.path.join(project_dir(), "Docs", "Layout", "S01_LW_F1_schedule.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_time(text):
    """'HH:MM' -> seconds since midnight."""
    h, m = text.split(":")
    return int(h) * 3600.0 + int(m) * 60.0


def format_time(seconds):
    s = int(seconds % DAY)
    return "%02d:%02d:%02d" % (s // 3600, (s % 3600) // 60, s % 60)


def build_slot_table(periods):
    """48 half-hour slots -> period index. Slots before the first period start belong to the LAST period (midnight wrap)."""
    starts = [parse_time(p["start"]) for p in periods]
    table = []
    for slot in range(SLOTS):
        t = slot * SLOT_SECONDS
        idx = len(periods) - 1  # overnight carry-over from the last period
        for i, st in enumerate(starts):
            if st <= t:
                idx = i
        table.append(idx)
    return table


def period_at(table, seconds):
    """Mirrors the Blueprint: Slot = Clamp(Truncate(Fmod(seconds, 86400) / 1800), 0, 47); Period = Table[Slot]."""
    slot = min(max(int((seconds % DAY) // SLOT_SECONDS), 0), SLOTS - 1)
    return table[slot]


class ClockModel(object):
    """Reference model of BP_PrisonScheduleManager.Tick. total is the unwrapped accumulator (GameSecondsTotal)."""

    def __init__(self, table, start_seconds, time_scale=30.0):
        self.table, self.total, self.scale, self.paused = table, float(start_seconds), float(time_scale), False

    @property
    def clock(self):
        return math.fmod(self.total, DAY)

    @property
    def period(self):
        return period_at(self.table, self.clock)

    def tick(self, dt):
        if not self.paused:
            self.total += dt * self.scale


def validate_schema(data, errs):
    """Structural validation of the schedule JSON (no marker knowledge needed)."""
    def need(cond, msg):
        if not cond:
            errs.append(msg)
        return cond

    clock = data.get("clock", {})
    for k in ("start_time", "time_scale", "dev_time_scale", "stagger_max_game_minutes"):
        need(k in clock, "clock.%s missing" % k)
    if "time_scale" in clock:
        need(clock["time_scale"] > 0 and clock.get("dev_time_scale", 1) > 0, "time scales must be > 0")
    if "stagger_max_game_minutes" in clock:
        need(0 <= clock["stagger_max_game_minutes"] <= 30, "stagger_max_game_minutes must be 0..30")
    periods = data.get("periods", [])
    if not need(len(periods) >= 2, "at least two periods required"):
        return
    ids, last = set(), -1.0
    for p in periods:
        for k in ("id", "name", "start"):
            need(k in p, "period missing %s: %s" % (k, p))
        if "id" not in p or "start" not in p:
            continue
        need(p["id"] not in ids, "duplicate period id %s" % p["id"])
        ids.add(p["id"])
        try:
            st = parse_time(p["start"])
        except Exception:
            need(False, "bad time '%s' in period %s" % (p["start"], p["id"]))
            continue
        need(st % SLOT_SECONDS == 0, "period %s start %s is not on the 30 minute grid" % (p["id"], p["start"]))
        need(0 <= st < DAY, "period %s start out of range" % p["id"])
        need(st > last, "period %s start %s is not after the previous period (list must be ascending)" % (p["id"], p["start"]))
        last = st
    if "start_time" in clock:
        need(any(p.get("start") == clock["start_time"] for p in periods), "clock.start_time should equal a period start (prototype begins at a boundary)")
    need(len(periods) <= SLOTS, "too many periods")
    for nid, a in data.get("assignments", {}).items():
        need(0.0 <= a.get("stagger_fraction", -1) <= 1.0, "%s: stagger_fraction must be 0..1" % nid)
        sched = a.get("schedule", {})
        for pid in ids:
            e = sched.get(pid)
            if not need(e is not None, "%s: no assignment for period %s" % (nid, pid)):
                continue
            need(isinstance(e.get("stops"), list) and len(e["stops"]) > 0, "%s/%s: stops must be a non-empty list" % (nid, pid))
            idle = e.get("idle", [])
            need(len(idle) == 2 and 0 < idle[0] <= idle[1], "%s/%s: idle must be [min, max] seconds with 0 < min <= max" % (nid, pid))
        for pid in sched:
            need(pid in ids, "%s: assignment for unknown period %s" % (nid, pid))
