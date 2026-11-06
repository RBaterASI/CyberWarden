"""Why do some REACH rows fail? Run AFTER Build Paths (Output Log > Cmd):

    py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Docs/Layout/LeftWingF1_Board10/diagnose_reach.py"

Prints the navmesh agent settings, then for every room that the validator can fail (cells, office) walks three
queries from the spawn: to a point 0.9 m OUTSIDE its door, to a point 0.9 m INSIDE the door, and to the room centre
(and to 0.8 m off-centre toward the door). The first query that stops short shows what blocks it.
Results go to the Output Log (lines starting [LW_F1] DIAG) and to <Project>/Saved/LW_F1_reach_diag.md.
"""
import json
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
spec = json.load(open(os.path.join(HERE, "LeftWing_F1_spec.json"), encoding="utf-8"))
UP = spec["levels"]["upper"]["floor_z"]
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
NAV = unreal.NavigationSystemV1


def P(x, y, z):
    return unreal.Vector(x * 100.0, y * 100.0, z * 100.0)


out = []


def log(s):
    out.append(s)
    unreal.log("[LW_F1] DIAG " + s)


for nav in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.RecastNavMesh):
    for prop in ("agent_radius", "agent_height", "agent_max_step_height", "agent_max_slope", "cell_size", "cell_height", "tile_size_uu"):
        try:
            log("RecastNavMesh %s = %s" % (prop, nav.get_editor_property(prop)))
        except Exception:
            pass

sp = spec["spawn"]
start = P(sp["x"], sp["y"], 0.5)


def query(goal):
    path = NAV.find_path_to_location_synchronously(world, start, goal)
    if path is None:
        return "no path object"
    pts = list(path.path_points)
    if not pts:
        return "no points"
    end = pts[-1]
    gap = ((end.x - goal.x) ** 2 + (end.y - goal.y) ** 2) ** 0.5 / 100.0
    partial = path.is_partial() if hasattr(path, "is_partial") else False
    return "ends %.1f m short%s (end z %.0f)" % (gap, " PARTIAL" if partial else "", end.z)


rooms = {r["id"]: r for r in spec["rooms"]}
targets = [r for r in spec["rooms"] if r["kind"] in ("cell", "cellw") or r["id"] == "U13"]
for r in targets:
    z = (UP if r["tier"] == "upper" else 0.0) + 0.5
    cx, cy = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
    door = next((d for d in spec["doors"] if r["id"] in d.get("connects", []) or d["id"].endswith(r["id"])), None)
    if door is None:
        log("%s: no door found" % r["id"])
        continue
    mid = (door["span"][0] + door["span"][1]) / 2
    if door["wall"] == "x":
        a, b = (door["at"] - 0.9, mid), (door["at"] + 0.9, mid)
    else:
        a, b = (mid, door["at"] - 0.9), (mid, door["at"] + 0.9)
    inside = lambda p: r["x"] < p[0] < r["x"] + r["w"] and r["y"] < p[1] < r["y"] + r["h"]
    pin, pout = (a, b) if inside(a) else (b, a)
    toward = (pin[0] + (cx - pin[0]) * 0.0, pin[1])
    off = (cx + (pin[0] - cx) * 0.3, cy + (pin[1] - cy) * 0.3)
    log("%s door %s (%.2f m wide): outside %s | inside %s | centre %s | off-centre %s" % (
        r["id"], door["id"], door["span"][1] - door["span"][0],
        query(P(pout[0], pout[1], z)), query(P(pin[0], pin[1], z)), query(P(cx, cy, z)), query(P(off[0], off[1], z))))

with open(os.path.join(unreal.Paths.project_saved_dir(), "LW_F1_reach_diag.md"), "w", encoding="utf-8") as f:
    f.write("# REACH diagnosis\n\n" + "\n".join("- " + s for s in out) + "\n")
unreal.log("[LW_F1] DIAG done")
