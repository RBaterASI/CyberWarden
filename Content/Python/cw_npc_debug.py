"""Dev-only (editor) NPC debug overlay for Play In Editor: floating state text, state-change log, teleport watchdog.

Driven from init_unreal.py's tick. Reads the BP_PrisonNPC variables (MoveState, NpcId, ...) of actors tagged S01F1NPC.
Nothing here runs in packaged builds. Delete this file to remove it.
"""
import unreal

_TRACK = {}


def _log(msg):
    unreal.log("[NPC] " + msg)


def update(world, dt):
    """Call roughly every 0.15 s of real time while a PIE world of the greybox is running."""
    now = unreal.GameplayStatics.get_time_seconds(world)
    npcs = unreal.GameplayStatics.get_all_actors_with_tag(world, "S01F1NPC")
    for a in npcs:
        try:
            nid = str(a.get_editor_property("NpcId"))
            state = str(a.get_editor_property("MoveState"))
            fails = int(a.get_editor_property("NavFailureCount"))
            cur = int(a.get_editor_property("CurrentStopIndex"))
            route = a.get_editor_property("Route")
        except Exception:
            continue
        loc = a.get_actor_location()
        tr = _TRACK.setdefault(nid, {"state": None, "pos": loc, "t": now, "teleports": 0, "first_move": None, "start": loc})
        if tr["state"] != state:
            _log("t=%6.1f  %-6s %s -> %s  stop=%d  fails=%d  pos=(%.0f,%.0f,%.0f)" % (now, nid, tr["state"], state, cur, fails, loc.x, loc.y, loc.z))
            tr["state"] = state
        step = ((loc.x - tr["pos"].x) ** 2 + (loc.y - tr["pos"].y) ** 2 + (loc.z - tr["pos"].z) ** 2) ** 0.5
        span = max(now - tr["t"], 1e-3)
        speed = 400.0  # generous upper bound on any NPC walk speed (cm/s)
        if step > max(speed * span * 3.0, 120.0):
            tr["teleports"] += 1
            _log("WARNING %s moved %.0f cm in %.2f s (possible teleport) pos=(%.0f,%.0f,%.0f)" % (nid, step, span, loc.x, loc.y, loc.z))
        if tr["first_move"] is None and step > 5.0:
            tr["first_move"] = now
            _log("%s first movement at t=%.1f s" % (nid, now))
        tr["pos"], tr["t"] = loc, now
        target = ""
        if 0 <= cur < len(route) and route[cur]:
            target = route[cur].get_actor_label()
        text = "%s | %s | -> %s | fails %d" % (nid, state, target, fails)
        color = unreal.LinearColor(1.0, 0.35, 0.3, 1.0) if "Fail" in state else unreal.LinearColor(0.7, 1.0, 0.7, 1.0)
        unreal.SystemLibrary.draw_debug_string(world, unreal.Vector(loc.x, loc.y, loc.z + 130), text, None, color, 0.2)


def summary():
    for nid, tr in _TRACK.items():
        _log("summary %s: first_move=%s teleports=%d last_state=%s" % (nid, tr["first_move"], tr["teleports"], tr["state"]))
