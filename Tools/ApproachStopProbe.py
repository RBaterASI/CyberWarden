"""Headless PIE probe: does an AI move request honour its acceptance radius, and where does the NPC really stop? (M2.3 Stage C2). Saves nothing.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/ApproachStopProbe.py -Log <abs log>

QUI01's StateTree is stopped in the PIE copy. The activity component is not involved: the AI controller is given the same kind of request the component's
final approach issues (exact marker as goal, small acceptance radius, no agent radius or goal radius in the reach test, pathfinding, goal projected on the
navmesh, no partial path) after the routine's own Move To (radius 10, stop on overlap) has left the NPC about 40-47 cm out, from several directions.
For every trial: the requested goal (the marker), the projected navigable goal, the start, the stopping coordinates and the three distances (to the marker, to
the projected goal = the actual stopping error, and the gap between marker and projected goal), the path-following result, the duration, the closest
approach to the goal during the walk (overshoot = final minus closest) and the number of times the distance to the goal grew (oscillation). Radius 3 (the
previous value) and radius 1 (the new one) are compared at identical starts and at two time dilations (the per-tick step is 150 cm/s x dt).
"""
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SEAT = "Seat_Table_1_5"
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
S = {"n": 0, "pie": False, "post": 0, "h": None, "gen": None, "wait": 0, "until": None, "timed_out": False, "last_t": None, "samples": [], "rows": [], "out": [], "result": None}


def log(m):
    S["out"].append(m)
    unreal.log("[STOPPROBE] " + m)


def finish(code):
    unreal.unregister_slate_post_tick_callback(S["h"])
    with open(unreal.Paths.project_saved_dir() + "ApproachStopProbe.txt", "w") as fh:
        fh.write("\n".join(S["out"]))
    level_sub.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


def d2(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def hd(ax, ay, bx, by):
    return math.degrees(math.atan2(by - ay, bx - ax))


def here():
    l = S["npc"].get_actor_location()
    return l.x, l.y


def mloc(mid):
    return unreal.GameplayStatics.get_all_actors_with_tag(S["gw"], "MarkerId:" + mid)[0].get_actor_location()


def idle():
    return "IDLE" in str(S["ctrl"].get_move_status())


def on_completed(request_id, result):
    S["result"] = str(result)


def trial(label, via, radius, slomo):
    mk, pg = S["mk"], S["pg"]
    unreal.SystemLibrary.execute_console_command(S["gw"], "slomo %g" % slomo)
    S["ctrl"].move_to_location(via, 30.0, True, True, True, False, None, True)
    yield ("ticks", 3)
    yield ("until", idle, 120.0)
    yield ("secs", 0.5)
    S["ctrl"].move_to_location(mk, 10.0, True, True, True, False, None, True)  # the routine's Move To
    yield ("ticks", 3)
    yield ("until", idle, 120.0)
    yield ("secs", 0.6)
    sx, sy = here()
    S["samples"] = []
    S["result"] = None
    t_issue = S["last_t"]
    req = S["ctrl"].move_to_location(mk, radius, False, True, True, False, None, False)  # the final approach's request
    yield ("ticks", 2)
    yield ("until", idle, 8.0)
    t_idle = S["last_t"]
    yield ("secs", 0.7)  # braking
    ex, ey = here()
    smp = S["samples"]
    dist_pg = [d2(s["x"], s["y"], pg.x, pg.y) for s in smp]
    closest = min(dist_pg) if dist_pg else float("nan")
    grew = sum(1 for a, b in zip(dist_pg, dist_pg[1:]) if b > a + 0.25)
    steps = [d2(p["x"], p["y"], q["x"], q["y"]) for p, q in zip(smp, smp[1:])]
    row = dict(label=label, radius=radius, slomo=slomo, start=(sx, sy), start_d=d2(sx, sy, mk.x, mk.y), heading=hd(sx, sy, mk.x, mk.y), end=(ex, ey),
               d_marker=d2(ex, ey, mk.x, mk.y), d_goal=d2(ex, ey, pg.x, pg.y), closest=closest, overshoot=d2(ex, ey, pg.x, pg.y) - closest, grew=grew,
               secs=t_idle - t_issue, result=S["result"], req=str(req), max_step=max(steps + [0.0]), n=len(smp))
    S["rows"].append(row)
    log("%-28s r=%.0f slomo %g: start (%.1f, %.1f) %.1f cm out heading %.0f deg | stopped (%.3f, %.3f) | marker %.3f cm | projected goal %.3f cm (closest %.3f, overshoot %.3f, distance grew %dx) | %.2f s | path result %s | request %s | max step %.1f cm" % (
        label, radius, slomo, sx, sy, row["start_d"], row["heading"], ex, ey, row["d_marker"], row["d_goal"], closest, row["overshoot"], grew, row["secs"], row["result"], row["req"], row["max_step"]))


def run(gw):
    npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
    mgr = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")[0]
    npc = npcs["QUI01"]
    S.update(gw=gw, npc=npc, ctrl=npc.get_controller())
    mgr.set_editor_property("paused", True)
    stc = S["ctrl"].get_component_by_class(unreal.StateTreeAIComponent)
    if stc is not None:
        stc.stop_logic("stop probe")
    yield ("ticks", 5)
    mk = mloc(SEAT)
    try:
        pg = unreal.NavigationSystemV1.project_point_to_navigation(gw, mk, None, None, unreal.Vector(50, 50, 250))
    except Exception as ex:
        log("projection failed: %s" % ex)
        finish(3)
        return
    S.update(mk=mk, pg=pg)
    log("requested goal = marker (%.3f, %.3f, %.3f); projected navigable goal (%.3f, %.3f, %.3f); the marker is %.3f cm from the reachable position" % (mk.x, mk.y, mk.z, pg.x, pg.y, pg.z, d2(mk.x, mk.y, pg.x, pg.y)))
    try:
        S["ctrl"].receive_move_completed.add_callable(on_completed)
        log("move-completed delegate bound: the path-following result is recorded")
    except Exception as ex:
        log("move-completed delegate not available from Python (%s): the result is inferred from the stop" % ex)
    vias = [("from the west (Seat_Table_1_4)", mloc("Seat_Table_1_4")), ("from the east (Seat_Table_1_6)", mloc("Seat_Table_1_6")),
            ("from the south side (Seat_Table_1_1)", mloc("Seat_Table_1_1")), ("from the north (6150, 220)", unreal.Vector(6150.0, 220.0, mk.z))]
    for slomo in (3.0, 1.0):
        for label, via in vias:
            for radius in (3.0, 1.0):
                yield from trial(label, via, radius, slomo)
    rows = S["rows"]
    log("== summary (distance of the stopping point to the projected navigable goal) ==")
    for slomo in (3.0, 1.0):
        for radius in (3.0, 1.0):
            v = [r["d_goal"] for r in rows if r["radius"] == radius and r["slomo"] == slomo]
            ends = [r["end"] for r in rows if r["radius"] == radius and r["slomo"] == slomo]
            pair = max([d2(a[0], a[1], b[0], b[1]) for a in ends for b in ends] + [0.0])
            log("  slomo %g radius %.0f: %d trials, error to the goal mean %.3f max %.3f; largest distance between two stopping points %.3f cm; max overshoot %.3f; trials where the distance grew %d" % (
                slomo, radius, len(v), sum(v) / max(len(v), 1), max(v + [0.0]), pair, max([r["overshoot"] for r in rows if r["radius"] == radius and r["slomo"] == slomo] + [0.0]),
                sum(1 for r in rows if r["radius"] == radius and r["slomo"] == slomo and r["grew"] > 0)))
    finish(0)


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 400000:
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
        now = unreal.GameplayStatics.get_time_seconds(gw)
        if S["gen"] is None:
            S["gen"] = run(gw)
        S["last_t"] = now
        if "npc" in S:
            l = S["npc"].get_actor_location()
            S["samples"].append(dict(t=now, x=l.x, y=l.y))
        if S["wait"] > 0:
            S["wait"] -= 1
            return
        if S["until"] is not None:
            cond, deadline = S["until"]
            if cond():
                S["until"], S["timed_out"] = None, False
            elif now >= deadline:
                S["until"], S["timed_out"] = None, True
            else:
                return
        try:
            kind, *rest = next(S["gen"])
        except StopIteration:
            return
        if kind == "ticks":
            S["wait"] = int(rest[0])
        elif kind == "secs":
            end = now + rest[0]
            S["until"] = ((lambda e=end: unreal.GameplayStatics.get_time_seconds(gw) >= e), end + 1.0)
        elif kind == "until":
            S["until"] = (rest[0], now + rest[1])
    except Exception as ex:
        import traceback
        log("EXCEPTION %s\n%s" % (ex, traceback.format_exc()))
        finish(9)


S["h"] = unreal.register_slate_post_tick_callback(tick)
