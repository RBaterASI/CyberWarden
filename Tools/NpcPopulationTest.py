"""Headless PIE population test: all placed NPCs (tag S01F1NPC) run their StateTree routine at the same time. Read-only.

  set NPC_TEST_SECONDS=<game seconds, default 360>   set NPC_TEST_SLOMO=<default 4>
  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/NpcPopulationTest.py" -unattended -nop4 -nosplash -NullRHI

Nothing is commanded. Per NPC it reports stop arrivals, full route loops, navigation failures, stuck windows (little
progress while Moving), repeated move attempts, teleports. Across NPCs: minimum pair distance, overlap and close-approach
time, and doorway congestion (NPCs within 200 cm of an opening centre, and idling within 250 cm of one).
"""
import json
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SECONDS = float(os.environ.get("NPC_TEST_SECONDS", "360"))
SLOMO = float(os.environ.get("NPC_TEST_SLOMO", "4"))
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)

layout = json.load(open(os.path.join(unreal.Paths.project_dir(), "Docs", "Layout", "S01_LW_F1.json"), encoding="utf-8"))
OPEN = []
for o in layout["openings"]:
    if o.get("z0", 0) != 0 or o.get("kind") == "secured":
        continue
    OPEN.append((o["id"], (o["coord"], o["center"]) if o["axis"] == "v" else (o["center"], o["coord"])))

S = {"n": 0, "pie": False, "post": 0, "h": None, "phase": "init", "t0": 0.0, "npcs": {}, "pair": {}, "door": {}, "last_t": 0.0}


def log(m):
    unreal.log("[POPTEST] " + m)


def d2(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def done(code):
    unreal.unregister_slate_post_tick_callback(S["h"])
    log("exit %d" % code)
    unreal.SystemLibrary.quit_editor()


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 60000:
            log("FAILED: timeout")
            done(2)
            return
        if not S["pie"]:
            return
        gw = ues.get_game_world()
        if gw is None:
            return
        S["post"] += 1
        if S["post"] < 60:
            return
        now = unreal.GameplayStatics.get_time_seconds(gw)
        npcs = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")
        if S["phase"] == "init":
            if not npcs:
                log("FAILED: no NPCs placed")
                done(4)
                return
            for a in npcs:
                nid = str(a.get_editor_property("NpcId"))
                route = list(a.get_editor_property("Route"))
                S["npcs"][nid] = dict(a=a, route=route, pos=a.get_actor_location(), spawn=a.get_actor_location(), state=None, cur=-1,
                                      arrivals=0, loops=0, fails=0, teleports=0, maxstep=0.0, path=0.0, first_move=None, stuck=0,
                                      win_t=now, win_pos=a.get_actor_location(), moving_since=None, repeats=0, last_moving_stop=None,
                                      idle_in_door=[], seq=[], bad_arrival=0, sd_repeat=0)
                log("%s: %s route %s" % (nid, a.get_editor_property("ArchetypeName"), " -> ".join(r.get_actor_label() for r in route)))
            if os.environ.get("NPC_TEST_FAIL_NPC") in S["npcs"]:
                S["npcs"][os.environ["NPC_TEST_FAIL_NPC"]]["route"][-1].set_actor_location(unreal.Vector(-3000, -3000, 0), False, False)  # PIE copy only: last route marker off the navmesh forces navigation failures
                log("moved last route marker off-navmesh for %s" % os.environ["NPC_TEST_FAIL_NPC"])
            S.update(t0=now, last_t=now, phase="run")
            unreal.SystemLibrary.execute_console_command(gw, "slomo %g" % SLOMO)
            return
        span = max(now - S["last_t"], 1e-3)
        S["last_t"] = now
        for nid, n in S["npcs"].items():
            a = n["a"]
            loc = a.get_actor_location()
            step = d2(loc, n["pos"]) + abs(loc.z - n["pos"].z)
            if step > max(450.0 * span * 1.5, 120.0):
                n["teleports"] += 1
                log("WARNING %s moved %.0f cm in %.2f s (teleport?) at (%.0f,%.0f,%.0f)" % (nid, step, span, loc.x, loc.y, loc.z))
            n["maxstep"] = max(n["maxstep"], step)
            n["path"] += step
            n["pos"] = loc
            if n["first_move"] is None and d2(loc, n["spawn"]) > 20:
                n["first_move"] = now - S["t0"]
            state = str(a.get_editor_property("MoveState"))
            cur = int(a.get_editor_property("CurrentStopIndex"))
            if state != n["state"]:
                prev = n["state"]
                if state == "Moving":
                    if n["last_moving_stop"] == (cur, n["arrivals"]):
                        n["repeats"] += 1
                        log("%s repeated move attempt to stop %d" % (nid, cur))
                    n["last_moving_stop"] = (cur, n["arrivals"])
                    n["win_t"], n["win_pos"] = now, loc
                if prev == "Moving" and state == "Idle":
                    stop = n["route"][cur].get_actor_location() if 0 <= cur < len(n["route"]) else None
                    if stop is not None and d2(loc, stop) < 150:
                        n["arrivals"] += 1
                        if cur == len(n["route"]) - 1:
                            n["loops"] += 1
                    else:
                        n["bad_arrival"] += 1
                        log("%s left Moving for Idle %.0f cm from stop %d" % (nid, d2(loc, stop) if stop else -1, cur))
                    for oid, (ox, oy) in OPEN:
                        if math.hypot(loc.x - ox, loc.y - oy) < 250:
                            n["idle_in_door"].append(oid)
                if state == "StartDelay" and prev is not None:
                    n["sd_repeat"] += 1
                if state == "NavFail":
                    n["fails"] += 1
                n["seq"].append((round(now - S["t0"], 1), state, cur))
                n["state"], n["cur"] = state, cur
            if state == "Moving" and now - n["win_t"] >= 5.0:
                if d2(loc, n["win_pos"]) < 40:
                    n["stuck"] += 1
                    log("WARNING %s stuck: %.0f cm in 5 s while Moving to stop %d at (%.0f,%.0f)" % (nid, d2(loc, n["win_pos"]), cur, loc.x, loc.y))
                n["win_t"], n["win_pos"] = now, loc
        ids = list(S["npcs"])
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                p, q = S["npcs"][ids[i]]["pos"], S["npcs"][ids[j]]["pos"]
                if abs(p.z - q.z) > 100:
                    continue
                d = d2(p, q)
                r = S["pair"].setdefault((ids[i], ids[j]), dict(min=1e9, overlap=0.0, close=0.0, where=None))
                if d < r["min"]:
                    r["min"], r["where"] = d, (p.x, p.y)
                if d < 68:
                    r["overlap"] += span
                if d < 120:
                    r["close"] += span
        for oid, (ox, oy) in OPEN:
            near = [nid for nid, n in S["npcs"].items() if math.hypot(n["pos"].x - ox, n["pos"].y - oy) < 200]
            r = S["door"].setdefault(oid, dict(peak=0, t2=0.0, who=set()))
            if len(near) > r["peak"]:
                r["peak"] = len(near)
            if len(near) >= 2:
                r["t2"] += span
                r["who"].update(near)
        if now - S["t0"] >= SECONDS:
            report(gw, now)
    except Exception as ex:
        import traceback
        log("EXCEPTION %s\n%s" % (ex, traceback.format_exc()))
        done(9)


def report(gw, now):
    unreal.SystemLibrary.execute_console_command(gw, "slomo 1")
    ok = True
    log("=== RESULT after %.0f game seconds (slomo %g) ===" % (now - S["t0"], SLOMO))
    for nid, n in S["npcs"].items():
        log("%s: first_move=%s arrivals=%d loops=%d navfail=%d stuck=%d repeats=%d teleports=%d bad_arrivals=%d startdelay_repeats=%d maxstep=%.0f path=%.0f" % (
            nid, "%.1fs" % n["first_move"] if n["first_move"] is not None else None, n["arrivals"], n["loops"], n["fails"], n["stuck"], n["repeats"],
            n["teleports"], n["bad_arrival"], n["sd_repeat"], n["maxstep"], n["path"]))
        if n["idle_in_door"]:
            log("   idled within 250 cm of opening(s): %s" % sorted(set(n["idle_in_door"])))
        ok = ok and n["sd_repeat"] == 0 and n["loops"] >= 1 and n["fails"] == 0 and n["stuck"] == 0 and n["teleports"] == 0 and n["bad_arrival"] == 0 and not n["idle_in_door"]
    for (a, b), r in sorted(S["pair"].items()):
        log("pair %s/%s: min %.0f cm at (%.0f,%.0f), overlap<68cm %.1fs, close<120cm %.1fs" % (a, b, r["min"], r["where"][0], r["where"][1], r["overlap"], r["close"]))
        ok = ok and r["overlap"] < 1.0
    for oid, r in sorted(S["door"].items()):
        if r["peak"] >= 2:
            log("doorway %s: peak %d NPCs within 200 cm, %.1fs with 2+ (%s)" % (oid, r["peak"], r["t2"], ",".join(sorted(r["who"]))))
    for nid, n in S["npcs"].items():
        log("%s transitions: %s" % (nid, " ".join("%s@%.0f" % (s, t) for t, s, _ in n["seq"][:40])))
    log("RESULT %s" % ("PASS" if ok else "REVIEW"))
    level_sub.editor_request_end_play()
    done(0 if ok else 3)


S["h"] = unreal.register_slate_post_tick_callback(tick)
