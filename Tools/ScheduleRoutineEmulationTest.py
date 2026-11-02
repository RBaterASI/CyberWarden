"""Headless PIE acceptance test of schedule-driven NPC movement WITHOUT the (manually edited) StateTree. Saves nothing.

  powershell -File Tools\RunHeadless.ps1 -Script Tools\ScheduleRoutineEmulationTest.py -Log <abs log>

The StateTree of each NPC is stopped in the PIE copy and a Python driver runs exactly the routine the Checkpoint B StateTree is
specified to run, calling the same native component API the "Prison: Plan Destination" task calls, with real AI navigation
(AIController MoveTo) on the baked navmesh:
    plan (PlanForCurrentPeriod) -> start delay -> [Move To when MoveRequired] -> idle -> plan ... ;
    replan request (after the stagger) -> stop the movement and plan again; failed move -> 2 s recover -> plan.
The 30x clock is jumped to each period start (periods are shortened to <= 150 s) so a whole day is covered in minutes. It measures
arrivals per period, replans per boundary, teleports, stuck windows, navigation failures, repeated Move To at a destination,
NPC proximity and doorway congestion.
"""
import json
import math
import os

import unreal

import cw_schedule as cs

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SLOMO = float(os.environ.get("EMU_SLOMO", "4"))
STATETREE_MODE = os.environ.get("EMU_MODE", "emulation") == "statetree"  # observe the real StateTree instead of the Python driver
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
data = cs.load()
layout = json.load(open(os.path.join(unreal.Paths.project_dir(), "Docs", "Layout", "S01_LW_F1.json"), encoding="utf-8"))
OPEN = [(o["id"], (o["coord"], o["center"]) if o["axis"] == "v" else (o["center"], o["coord"]))
        for o in layout["openings"] if o.get("z0", 0) == 0 and o.get("kind") != "secured"]
PERIODS = {p["id"]: p for p in data["periods"]}

# (label, period id or None, time of day in hours at the start, world seconds to run)
H = lambda hh, mm=0, ss=0: hh + mm / 60.0 + ss / 3600.0
SEGMENTS = [("wake", "wake", H(6), 100), ("breakfast", "breakfast", H(7), 100), ("work", "work", H(8), 150), ("lunch", "lunch", H(12), 100),
            ("recreation", "recreation", H(13), 150), ("dinner", "dinner", H(18), 100), ("free", "free", H(19), 150),
            ("lockdown", "lockdown", H(21), 150),
            ("midnight", None, H(23, 58), 12),            # lockdown must continue across midnight: no replan
            ("dawn", "wake", H(5, 59, 30), 75)]           # lockdown -> wake-up at 06:00: one replan after the stagger
S = {"n": 0, "pie": False, "post": 0, "h": None, "phase": "init", "seg": -1, "seg_end": 0.0, "last_t": 0.0, "npcs": {}, "pair": {}, "door": {},
     "res": [], "fail": [], "mgr": None, "segstats": []}


def log(m):
    unreal.log("[EMUTEST] " + m)


def check(name, ok, detail=""):
    S["res"].append(bool(ok))
    if not ok:
        S["fail"].append(name)
    log("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  (%s)" % detail))


def d2(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def finish(code):
    unreal.unregister_slate_post_tick_callback(S["h"])
    log("RESULT %s (%d/%d checks)" % ("PASS" if not S["fail"] and code == 0 else "FAIL", sum(S["res"]), len(S["res"])))
    level_sub.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


def comp_of(npc):
    return npc.get_component_by_class(unreal.PrisonScheduleComponent)


def new_state(npc, nid):
    return dict(a=npc, c=comp_of(npc), ctrl=npc.get_controller(), state="init", until=0.0, dest=None, pos=npc.get_actor_location(),
                tele=0, maxstep=0.0, stuck=0, navfail=0, win_t=0.0, win_pos=npc.get_actor_location(), move_t=0.0, arrivals=[],
                moves=0, interrupts=0, repeat_moves=0, last_plan_marker=None, last_serial=0, serial_in_seg=0, first_arrival=None, start_t=0.0)


def plan(n, now):
    n["dest"] = n["c"].plan_for_current_period()
    d = n["dest"]
    if not d.valid:
        n["state"], n["until"] = "recover", now + 2.0
        return
    n["state"], n["until"] = "delay", now + float(d.start_delay_seconds)


def observe_npc(nid, n, now, loc):
    """EMU_MODE=statetree: the real StateTree drives the NPC; only watch MoveState and the component diagnostics."""
    c = n["c"]
    ms = str(n["a"].get_editor_property("MoveState"))
    if ms != n.get("ms"):
        prev, n["ms"] = n.get("ms"), ms
        stop = str(c.get_editor_property("current_stop_marker_id"))
        marker = unreal.GameplayStatics.get_all_actors_with_tag(S["gw"], "MarkerId:" + stop) if stop and stop != "None" else []
        dist = d2(loc, marker[0].get_actor_location()) if marker else 1e9
        if ms == "Moving":
            n["moves"] += 1
            n["move_t"], n["win_t"], n["win_pos"] = now, now, loc
            if dist < 150.0:
                n["repeat_moves"] += 1
        elif ms == "NavFail":
            n["navfail"] += 1
            log("NAV FAIL %s -> %s at distance %.0f" % (nid, stop, dist))
        elif ms == "Idle" and prev == "Moving" and dist < 150.0:
            n["arrivals"].append((stop, now))
            if n["first_arrival"] is None:
                n["first_arrival"] = now - n["start_t"]
    if ms == "Moving" and now - n["win_t"] >= 5.0:
        if d2(loc, n["win_pos"]) < 40:
            n["stuck"] += 1
            log("STUCK %s at (%.0f,%.0f)" % (nid, loc.x, loc.y))
        n["win_t"], n["win_pos"] = now, loc
    n["state"] = ms.lower()


def step_npc(nid, n, now, span):
    c, a, ctrl = n["c"], n["a"], n["ctrl"]
    loc = a.get_actor_location()
    step = d2(loc, n["pos"]) + abs(loc.z - n["pos"].z)
    if step > max(450.0 * span * 1.5, 120.0):
        n["tele"] += 1
        log("WARNING %s moved %.0f cm in %.2f s (teleport?)" % (nid, step, span))
    n["maxstep"] = max(n["maxstep"], step)
    n["pos"] = loc
    if STATETREE_MODE:
        observe_npc(nid, n, now, loc)
        return
    if n["state"] != "init" and c.get_editor_property("replan_requested"):
        if n["state"] == "moving":
            ctrl.stop_movement()
        n["interrupts"] += 1
        n["seg_interrupted_state"] = n["state"]
        plan(n, now)
        return
    st = n["state"]
    if st == "init":
        plan(n, now)
    elif st == "delay" and now >= n["until"]:
        d = n["dest"]
        if d.move_required:
            if d2(loc, d.marker.get_actor_location()) < 150.0:
                n["repeat_moves"] += 1  # a Move To request although already within the arrival radius
            ctrl.move_to_location(d.marker.get_actor_location(), 60.0, True, True, False, False, None, True)
            n["moves"] += 1
            n["state"], n["move_t"], n["win_t"], n["win_pos"] = "moving", now, now, loc
        else:
            n["last_plan_marker"], n["last_needed_move"] = str(d.marker_id), False
            n["state"], n["until"] = "idle", now + float(d.idle_seconds)
    elif st == "moving":
        d = n["dest"]
        dist = d2(loc, d.marker.get_actor_location())
        status = str(ctrl.get_move_status())
        if "IDLE" in status and dist < 110:
            n["arrivals"].append((str(d.marker_id), now))
            if n["first_arrival"] is None:
                n["first_arrival"] = now - n["start_t"]
            n["state"], n["until"] = "idle", now + float(d.idle_seconds)
        elif "IDLE" in status and now - n["move_t"] > 1.0:
            n["navfail"] += 1
            log("NAV FAIL %s -> %s at distance %.0f" % (nid, d.marker_id, dist))
            n["state"], n["until"] = "recover", now + 2.0
        elif now - n["win_t"] >= 5.0:
            if d2(loc, n["win_pos"]) < 40:
                n["stuck"] += 1
                others = ["%s d=%.0f %s" % (o, d2(loc, S["npcs"][o]["pos"]), S["npcs"][o]["state"]) for o in S["npcs"] if o != nid]
                log("STUCK %s -> %s at (%.0f,%.0f) clock %s; others: %s" % (nid, d.marker_id, loc.x, loc.y, S["mgr"].get_clock_string(), "; ".join(others)))
            n["win_t"], n["win_pos"] = now, loc
    elif st in ("idle", "recover") and now >= n["until"]:
        plan(n, now)


def begin_segment(i, now):
    label, pid, hour, secs = SEGMENTS[i]
    m = S["mgr"]
    m.set_time_of_day_hours(hour)
    S["seg"], S["seg_end"] = i, now + secs
    for nid, n in S["npcs"].items():
        n["seg_serial0"] = n["c"].get_editor_property("replan_serial")
        n["seg_arr0"] = len(n["arrivals"])
        n["seg_moves0"] = n["moves"]
        n["seg_navfail0"] = n["navfail"]
        n["seg_interrupts0"] = n["interrupts"]
        n["seg_interrupted_state"] = None
        n["start_t"] = now
        n["first_arrival"] = None
    log("segment %d '%s': clock %s, period %s, %d world s" % (i, label, m.get_clock_string(), m.get_editor_property("current_period_name"), secs))


def end_segment(i, now):
    label, pid, hour, secs = SEGMENTS[i]
    m = S["mgr"]
    for nid, n in S["npcs"].items():
        sched = data["assignments"][nid]["schedule"]
        stops = sched[pid]["stops"] if pid else sched["lockdown"]["stops"]
        serial = n["c"].get_editor_property("replan_serial") - n["seg_serial0"]
        arrived = [mk for mk, t in n["arrivals"][n["seg_arr0"]:] if mk in stops]
        at_stop = min(d2(n["a"].get_actor_location(), unreal.GameplayStatics.get_all_actors_with_tag(S["gw"], "MarkerId:" + sid)[0].get_actor_location())
                      if unreal.GameplayStatics.get_all_actors_with_tag(S["gw"], "MarkerId:" + sid) else 1e9 for sid in stops)
        moves = n["moves"] - n["seg_moves0"]
        log("  %-5s %-10s replans=%d interrupted=%s arrivals=%s first_arrival=%s moves=%d navfail=%d dist_to_nearest_stop=%.0f state=%s" % (
            nid, label, serial, n["seg_interrupted_state"], arrived[:3], "%.0fs" % n["first_arrival"] if n["first_arrival"] is not None else "-",
            moves, n["navfail"] - n["seg_navfail0"], at_stop, n["state"]))
        if label == "midnight":
            check("%s: no replan while lockdown continues across midnight" % nid, serial == 0, str(serial))
        else:
            want = 0 if i == 0 else 1  # the very first segment starts with the initial plan, not a boundary
            check("%s: %d replan(s) for the %s boundary" % (nid, want, label), serial == want, "replans=%d" % serial)
            check("%s: obeyed the %s schedule (arrived at %s)" % (nid, label, arrived[:1]), len(arrived) >= 1 or at_stop < 200.0, "dist=%.0f arrived=%s state=%s" % (at_stop, arrived, n["state"]))  # already standing at a stop (inside the arrival radius) counts
        if label == "lockdown":
            check("%s: held in its own cell at the end of lockdown" % nid, at_stop < 200.0)


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 120000:
            log("FAILED: timeout")
            finish(2)
            return
        if not S["pie"]:
            return
        gw = ues.get_game_world()
        if gw is None:
            return
        S["post"] += 1
        if S["post"] < 80:
            return
        S["gw"] = gw
        now = unreal.GameplayStatics.get_time_seconds(gw)
        if S["phase"] == "init":
            mgrs = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")
            npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
            check("exactly one placed schedule manager", len(mgrs) == 1, str(len(mgrs)))
            check("four prisoners present", len(npcs) == 4, str(sorted(npcs)))
            if len(mgrs) != 1 or len(npcs) != 4:
                finish(4)
                return
            S["mgr"] = mgrs[0]
            for nid, a in npcs.items():
                stc = a.get_controller().get_component_by_class(unreal.StateTreeAIComponent)
                try:
                    if STATETREE_MODE:
                        raise RuntimeError("StateTree mode: left running")
                    stc.stop_logic("schedule emulation test")  # PIE copy only: the Python driver replaces the StateTree
                except Exception as ex:
                    log("could not stop the StateTree of %s: %s" % (nid, ex))
                S["npcs"][nid] = new_state(a, nid)
            for nid, n in S["npcs"].items():
                cmc = n["a"].get_component_by_class(unreal.CharacterMovementComponent)
                data_speed = next(x for x in json.load(open(os.path.join(unreal.Paths.project_dir(), "Docs", "Layout", "S01_LW_F1_npcs.json")))["npcs"] if x["id"] == nid)["walk_speed"]
                cmc.set_editor_property("max_walk_speed", float(data_speed))
            S["mgr"].set_editor_property("time_scale", 30.0)
            S["phase"], S["last_t"] = "run", now
            unreal.SystemLibrary.execute_console_command(gw, "slomo %g" % SLOMO)
            begin_segment(0, now)
            return
        span = max(now - S["last_t"], 1e-3)
        S["last_t"] = now
        for nid, n in S["npcs"].items():
            step_npc(nid, n, now, span)
        ids = list(S["npcs"])
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                p, q = S["npcs"][ids[i]]["pos"], S["npcs"][ids[j]]["pos"]
                r = S["pair"].setdefault((ids[i], ids[j]), dict(min=1e9, overlap=0.0, close=0.0, where=None))
                if abs(p.z - q.z) > 100:
                    continue
                d = d2(p, q)
                if d < r["min"]:
                    r["min"], r["where"] = d, (p.x, p.y)
                if d < 68:
                    r["overlap"] += span
                if d < 120:
                    r["close"] += span
        for oid, (ox, oy) in OPEN:
            near = [nid for nid, n in S["npcs"].items() if math.hypot(n["pos"].x - ox, n["pos"].y - oy) < 200]
            r = S["door"].setdefault(oid, dict(peak=0, t2=0.0, who=set()))
            r["peak"] = max(r["peak"], len(near))
            if len(near) >= 2:
                r["t2"] += span
                r["who"].update(near)
        if now >= S["seg_end"]:
            end_segment(S["seg"], now)
            if S["seg"] + 1 < len(SEGMENTS):
                begin_segment(S["seg"] + 1, now)
            else:
                report(gw)
    except Exception as ex:
        import traceback
        log("EXCEPTION %s\n%s" % (ex, traceback.format_exc()))
        finish(9)


def report(gw):
    unreal.SystemLibrary.execute_console_command(gw, "slomo 1")
    log("=== TOTALS ===")
    for nid, n in S["npcs"].items():
        log("%s: moves=%d arrivals=%d interrupts=%d repeat_moves_at_destination=%d navfail=%d stuck=%d teleports=%d maxstep=%.0f" % (
            nid, n["moves"], len(n["arrivals"]), n["interrupts"], n["repeat_moves"], n["navfail"], n["stuck"], n["tele"], n["maxstep"]))
        check("%s: no teleports / stuck windows / navigation failures" % nid, n["tele"] == 0 and n["stuck"] == 0 and n["navfail"] == 0,
              "tele=%d stuck=%d navfail=%d" % (n["tele"], n["stuck"], n["navfail"]))
        check("%s: never re-requested a move while already at its destination" % nid, n["repeat_moves"] == 0, str(n["repeat_moves"]))
    for (a, b), r in sorted(S["pair"].items()):
        log("pair %s/%s: min %.0f cm at (%.0f,%.0f), overlap<68cm %.1fs, close<120cm %.1fs" % (a, b, r["min"], r["where"][0] if r["where"] else 0, r["where"][1] if r["where"] else 0, r["overlap"], r["close"]))
        check("%s/%s: capsules never overlapped" % (a, b), r["overlap"] < 1.0, "%.1fs" % r["overlap"])
    for oid, r in sorted(S["door"].items()):
        if r["peak"] >= 2:
            log("doorway %s: peak %d NPCs within 200 cm, %.1fs with 2+ (%s)" % (oid, r["peak"], r["t2"], ",".join(sorted(r["who"]))))
    finish(0)


S["h"] = unreal.register_slate_post_tick_callback(tick)
