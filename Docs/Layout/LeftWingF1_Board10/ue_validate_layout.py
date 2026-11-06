"""
Cyber Warden — S01 Left Wing Floor 1 layout validator for Unreal Engine 5.
Checks the built level against LeftWing_F1_spec.json:
  1. DOORS    every non-sealed doorway is clear at 1 m height (line trace through it); sealed doors are blocked
  2. WINDOWS  clear at mid height, solid below the sill (you can see through, not walk through)
  3. REACH    every room is reachable on foot from the PlayerStart (NavMesh path)
Draws green/red debug lines in the viewport for 60 s and writes a report to <Project>/Saved/LW_F1_validation.md.

Run in the editor after building:  py "C:/path/to/ue_validate_layout.py"
NavMesh must be built first (Build > Build Paths, or wait for auto-update after the build script runs).
"""
import json
import os
import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
spec = json.load(open(os.path.join(HERE, "LeftWing_F1_spec.json"), encoding="utf-8"))
ORIGIN_CM = unreal.Vector(0.0, 0.0, 0.0)    # must match the build script
DRAW = unreal.DrawDebugTrace.FOR_DURATION
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
UP = spec["levels"]["upper"]["floor_z"]

# preflight: the REACH rows need a finished NavMesh. Build > Build Paths, wait until "NAVMESH NEEDS TO BE REBUILT" is gone, then run this again.
try:
    if unreal.NavigationSystemV1.is_navigation_being_built(world):
        raise SystemExit("[LW_F1] NavMesh is still building - wait for it to finish (Build > Build Paths), then re-run ue_validate_layout.py")
except SystemExit:
    raise
except Exception:
    unreal.log_warning("[LW_F1] could not query the NavMesh state: make sure Build > Build Paths has finished (the red NAVMESH NEEDS TO BE REBUILT message is gone) before trusting the REACH rows")


def P(x, y, z):
    return ORIGIN_CM + unreal.Vector(x * 100.0, y * 100.0, z * 100.0)


def blocked(a, b):
    """True if the line is blocked. line_trace_single returns either a tuple (use its bool element) or a HitResult (use blocking_hit)."""
    res = unreal.SystemLibrary.line_trace_single(world, a, b, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [], DRAW, True,
                                                 unreal.LinearColor(1, 0, 0, 1), unreal.LinearColor(0, 1, 0, 1), 60.0)
    if isinstance(res, tuple):
        for item in res:
            if isinstance(item, bool):
                return item
        res = res[-1] if res else None
    if res is None:
        return False
    for getter in (lambda h: h.blocking_hit, lambda h: h.get_editor_property("blocking_hit"), lambda h: h.to_tuple()[0]):
        try:
            return bool(getter(res))
        except Exception:
            continue
    return True


def through(op, z):
    """Trace 0.8 m either side of the wall line, through the middle of the opening."""
    mid = (op["span"][0] + op["span"][1]) / 2
    if op["wall"] == "x":
        return P(op["at"] - 0.8, mid, z), P(op["at"] + 0.8, mid, z)
    return P(mid, op["at"] - 0.8, z), P(mid, op["at"] + 0.8, z)


rows, fails = [], 0

for d in spec["doors"]:
    z = (UP if d["tier"] == "upper" else 0.0) + 1.0
    a, b = through(d, z)
    is_blocked = blocked(a, b)
    want_blocked = d["type"] == "sealed" or bool(d.get("closed"))     # sealed doors and the closed red D27 slab
    ok = is_blocked if want_blocked else not is_blocked
    fails += 0 if ok else 1
    rows.append(("DOOR", d["id"], " / ".join(d["connects"]), "blocked" if is_blocked else "clear",
                 "expected blocked" if want_blocked else "expected clear", "PASS" if ok else "FAIL"))

for w in spec["windows"]:
    base = UP if w["tier"] == "upper" else 0.0
    a, b = through(w, base + (w["sill"] + w["head"]) / 2)
    clear_mid = not blocked(a, b)
    a2, b2 = through(w, base + max(0.3, w["sill"] - 0.4))
    solid_low = blocked(a2, b2)
    ok = clear_mid and solid_low
    fails += 0 if ok else 1
    rows.append(("WINDOW", w["id"], w["note"], f"mid {'clear' if clear_mid else 'BLOCKED'}, below sill {'solid' if solid_low else 'OPEN'}",
                 "see through, not walk through", "PASS" if ok else "FAIL"))

sp = spec["spawn"]
start = P(sp["x"], sp["y"], 0.5)
for r in spec["rooms"]:
    if min(r["w"], r["h"]) < 1.0 or r.get("reach") is False:   # sealed rooms (goods lift shaft) are not walkable by design
        continue
    z = (UP if r["tier"] == "upper" else 0.0) + 0.5
    goal = P(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2, z)
    path = unreal.NavigationSystemV1.find_path_to_location_synchronously(world, start, goal)
    ok, note = False, "no path"
    if path is not None:
        pts = list(path.path_points)
        if pts:
            end = pts[-1]
            gap = ((end.x - goal.x) ** 2 + (end.y - goal.y) ** 2) ** 0.5 / 100.0
            partial = path.is_partial() if hasattr(path, "is_partial") else False
            ok = gap < 1.5 and not partial
            note = f"path ends {gap:.1f} m from room centre" + (" (partial)" if partial else "")
    fails += 0 if ok else 1
    rows.append(("REACH", r["id"], r["name"], note, "reachable from spawn", "PASS" if ok else "FAIL"))

# zone volumes: one per spec room, labelled Zone_<id>_<name>
zone_labels = set()
for a_ in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    try:
        zone_labels.add(a_.get_actor_label())
    except Exception:
        pass
for r in spec["rooms"]:
    if min(r["w"], r["h"]) < 0.5:
        continue
    want = f"Zone_{r['id']}_{r['name']}"
    ok = want in zone_labels
    fails += 0 if ok else 1
    rows.append(("ZONE", r["id"], r["name"], "present" if ok else "MISSING", "one zone volume per room", "PASS" if ok else "FAIL"))

lines = ["# S01 Left Wing F1 — validation report", "", f"Failures: **{fails}** of {len(rows)} checks", "",
         "| Check | ID | What | Result | Expected | Status |", "| --- | --- | --- | --- | --- | --- |"]
lines += [f"| {' | '.join(r)} |" for r in rows]
out = os.path.join(unreal.Paths.project_saved_dir(), "LW_F1_validation.md")
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
for r in rows:
    if r[-1] == "FAIL":
        unreal.log_error(f"[LW_F1] FAIL {r[0]} {r[1]} ({r[2]}): {r[3]}")
unreal.log(f"[LW_F1] Validation done: {fails} failures of {len(rows)} checks. Report: {out}")
