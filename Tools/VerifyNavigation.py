"""Verify the baked Static navigation of the Floor 1 greybox (read-only).

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/VerifyNavigation.py" -unattended -nop4 -nosplash -NullRHI

Checks (all against the navigation data loaded from the saved level):
  - persistence: navigation is not being rebuilt on load and paths resolve immediately
  - every NavDest:Yes marker projects onto the navmesh and is reachable from the intake spawn
  - NPC-relevant legs (guard stair, observation walkway, duty markers, loops)
  - secured spaces stay unreachable
  - per-room navmesh coverage on a 100 cm grid
Writes Docs/Layout/S01_LW_F1_nav_report.txt. Never saves anything.
"""
import json
import math
import os
import sys

import unreal

PROJECT = unreal.Paths.project_dir()
sys.path.insert(0, os.path.join(PROJECT, "Content", "Python"))
import cw_layout  # noqa: E402

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
REPORT = os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1_nav_report.txt")
unreal.EditorPythonScripting.set_keep_python_script_alive(True)

level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
NAV = unreal.NavigationSystemV1
LINES = []
state = {"n": 0, "handle": None}


def rep(s):
    LINES.append(s)
    unreal.log("[NAVVERIFY] " + s)


def project(pt, ext=(60, 60, 150)):
    res = NAV.project_point_to_navigation(world, pt, None, None, unreal.Vector(*ext))
    if isinstance(res, tuple):
        ok, loc = res[0], res[1]
    else:
        ok, loc = (res is not None), res
    return (loc if ok else None)


def path(a, b):
    p = NAV.find_path_to_location_synchronously(world, a, b)
    if p is None or not p.is_valid():
        return None
    return p


def tags_of(a):
    return [str(t) for t in a.tags]


def run():
    data = json.load(open(os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1.json"), encoding="utf-8"))
    rooms = cw_layout.expand(data)["rooms"]
    actors = actor_sub.get_all_level_actors()
    markers = {}
    for a in actors:
        t = tags_of(a)
        mid = next((x.split(":", 1)[1] for x in t if x.startswith("MarkerId:")), None)
        if mid:
            mtype = next(x.split(":", 1)[1] for x in t if x.startswith("Marker:"))
            markers[mid] = (a.get_actor_location(), mtype, "NavDest:Yes" in t)
    pstart = next(a for a in actors if a.get_class().get_name() == "PlayerStart")
    spawn = pstart.get_actor_location()

    rep("== Persistence ==")
    rep("navigation being built right after load: %s" % NAV.is_navigation_being_built(world))
    first = path(unreal.Vector(-400, 400, 0), unreal.Vector(3800, 400, 0))
    rep("immediate path Intake->Hub (no ticks waited): %s" % ("VALID (%d pts, %.0f cm)" % (len(first.path_points), first.get_path_length()) if first else "NONE"))
    recast = [a for a in actors if a.get_class().get_name() == "RecastNavMesh"]
    rep("RecastNavMesh actors in level: %d" % len(recast))
    vols = [a for a in actors if a.get_class().get_name() == "NavMeshBoundsVolume"]
    for v in vols:
        o, e = v.get_actor_bounds(False)
        rep("NavMeshBoundsVolume origin=(%.0f,%.0f,%.0f) extent=(%.0f,%.0f,%.0f)" % (o.x, o.y, o.z, e.x, e.y, e.z))

    start_nav = project(spawn) or spawn
    rep("")
    rep("== Marker reachability from intake spawn (NavDest:Yes) ==")
    by_type = {}
    fails = []
    detour = []
    for mid, (loc, mtype, nav_yes) in sorted(markers.items()):
        if not nav_yes:
            continue
        pr = project(loc)
        ok = False
        why = ""
        if pr is None:
            why = "does not project onto navmesh"
        else:
            p = path(start_nav, pr)
            if p is None:
                why = "no path"
            elif p.is_partial():
                why = "partial path"
            else:
                ok = True
                straight = math.dist((start_nav.x, start_nav.y, start_nav.z), (pr.x, pr.y, pr.z))
                detour.append((p.get_path_length() / max(straight, 1.0), mid))
                if abs(pr.z - loc.z) > 40:
                    why = "projected %.0f cm from marker height" % (pr.z - loc.z)
        t = by_type.setdefault(mtype, [0, 0])
        t[1] += 1
        if ok and not why:
            t[0] += 1
        else:
            fails.append("%s (%s): %s" % (mid, mtype, why or "failed"))
    for k, (ok, tot) in sorted(by_type.items()):
        rep("  %-14s %d/%d reachable" % (k, ok, tot))
    rep("  failures: %d" % len(fails))
    for f in fails:
        rep("    FAIL " + f)

    rep("")
    rep("== Legs relevant to NPC routes ==")

    def leg(a, b, expect_min_z=None, via=None):
        la, lb = markers[a][0], markers[b][0]
        pa, pb = project(la), project(lb)
        if pa is None or pb is None:
            rep("  %-52s FAIL (marker not on navmesh)" % ("%s -> %s" % (a, b)))
            return False
        p = path(pa, pb)
        if p is None or p.is_partial():
            rep("  %-52s FAIL (%s)" % ("%s -> %s" % (a, b), "no path" if p is None else "partial"))
            return False
        pts = list(p.path_points)
        maxz = max(q.z for q in pts)
        note = ""
        if expect_min_z is not None and maxz < expect_min_z:
            rep("  %-52s FAIL (peak z %.0f < %.0f)" % ("%s -> %s" % (a, b), maxz, expect_min_z))
            return False
        rep("  %-52s OK %5.0f cm, %2d pts, peak z %.0f%s" % ("%s -> %s" % (a, b), p.get_path_length(), len(pts), maxz, note))
        return True

    allok = True
    legs = [
        ("DutyStart_Guard_Residential", "Patrol_C_01_Walkway", 320),
        ("Patrol_C_01_Walkway", "Patrol_A_02_HallWest", None),
        ("Patrol_A_02_HallWest", "Patrol_A_04_HallEast", None),
        ("Patrol_A_04_HallEast", "DutyStart_Guard_Residential", 320),
        ("Patrol_A_01_Post", "Patrol_A_03_HallMid", 320),
        ("DutyStart_Guard_Roving", "Patrol_A_07_EastCorr", None),
        ("Patrol_A_07_EastCorr", "Patrol_A_08_Cafeteria", None),
        ("Patrol_A_08_Cafeteria", "Patrol_A_09_EastLinkNS", None),
        ("Patrol_A_09_EastLinkNS", "Patrol_A_10_EastLinkEW", None),
        ("Patrol_A_10_EastLinkEW", "Patrol_A_11_Recreation", None),
        ("Patrol_A_11_Recreation", "Patrol_A_12_NorthLink", None),
        ("Patrol_A_12_NorthLink", "Patrol_A_06_Hub", None),
        ("Patrol_A_05_GateG1", "Patrol_A_02_HallWest", None),
        ("Patrol_B_02_Vestibule", "Patrol_B_03_StairLobby", None),
        ("Patrol_B_03_StairLobby", "Patrol_B_04_UpperLanding", 490),
        ("Patrol_B_04_UpperLanding", "Patrol_B_01_Hub", None),
        ("Work_Servery_S", "Work_Kitchen_Gap", None),
        ("Work_Kitchen_Gap", "Work_Servery_N", None),
        ("Work_Servery_N", "Intake_Desk_Position", None),
        ("CellAssign_Cell_N2", "Rec_Table_A", None),
        ("CellAssign_Cell_S2", "Conv_Cafe_B", None),
        ("CellAssign_Cell_N5", "Rec_Weights", None),
        ("CellAssign_Cell_S4", "Work_Servery_S", None),
        ("Seat_Table_1_1" if "Seat_Table_1_1" in markers else sorted(m for m in markers if m.startswith("Seat_"))[0], "Rec_Yard_Walk", None),
    ]
    for a, b, mz in legs:
        if a in markers and b in markers:
            allok &= leg(a, b, mz)
        else:
            rep("  %-52s SKIP (marker id missing: %s)" % ("%s -> %s" % (a, b), a if a not in markers else b))
            allok = False
    rep("  all NPC legs OK: %s" % allok)

    rep("")
    rep("== Secured / unreachable spaces ==")
    for name, pt in (("kitchen interior (7800,600)", unreal.Vector(7800, 600, 12)),
                     ("beyond Floor 2 exit (4600,-900,512)", unreal.Vector(4600, -900, 512)),
                     ("outside intake arrival door (-1000,400)", unreal.Vector(-1000, 400, 12))):
        pr = project(pt, (30, 30, 60))
        if pr is None:
            rep("  %-44s not on navmesh (OK)" % name)
        else:
            p = path(start_nav, pr)
            rep("  %-44s on navmesh; path %s" % (name, "NONE (OK)" if p is None or p.is_partial() else "EXISTS (PROBLEM)"))

    rep("")
    rep("== Navmesh coverage by room (100 cm grid, 70 cm inset, floor height) ==")
    low = []
    for r in rooms:
        if r["ceil"] <= 120:
            continue
        pts = []
        x = r["x0"] + 70
        while x <= r["x1"] - 70:
            y = r["y0"] + 70
            while y <= r["y1"] - 70:
                pts.append((x, y))
                y += 100
            x += 100
        if not pts:
            continue
        hit = sum(1 for x, y in pts if project(unreal.Vector(x, y, r["z"] + 10), (20, 20, 40)) is not None)
        frac = hit / len(pts)
        if frac < 0.85:
            low.append((r["id"], hit, len(pts)))
        if not r.get("cell"):
            rep("  %-20s %3d/%3d (%.0f%%)" % (r["id"], hit, len(pts), 100 * frac))
    cells_low = [x for x in low if x[0].startswith("Cell_")]
    rep("  cells below 85%% coverage: %s" % (", ".join("%s %d/%d" % c for c in cells_low) or "none (props such as bunks excluded by navmesh are expected to reduce cells slightly)"))
    other_low = [x for x in low if not x[0].startswith("Cell_")]
    rep("  other rooms below 85%%: %s" % (", ".join("%s %d/%d" % c for c in other_low) or "none"))

    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LINES))


def tick(dt):
    state["n"] += 1
    if state["n"] < 4:
        return
    unreal.unregister_slate_post_tick_callback(state["handle"])
    try:
        run()
    except Exception as ex:
        import traceback
        unreal.log_error("[NAVVERIFY] EXCEPTION %s\n%s" % (ex, traceback.format_exc()))
    unreal.SystemLibrary.quit_editor()


state["handle"] = unreal.register_slate_post_tick_callback(tick)
