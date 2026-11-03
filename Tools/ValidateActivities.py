"""Validate the M2.3 activity JSON against the layout, the schedule and the animation assets. Read-only (writes one text report).

  powershell -File Tools/RunHeadless.ps1 -Script Tools/ValidateActivities.py -Log <abs log>

Checks: schema; every interaction point is a NavDest:Yes marker of the layout; the facing prop exists and is in front of the marker;
the arrival tolerance covers the distance the navigation actually stops at (about 95 cm for Move To radius 60); the marker is not
close to an opening; every referenced animation exists, is an AnimSequence on SK_Mannequin (the NPC skeleton); which scheduled
NPCs/periods use each point. Report: Docs/Layout/S01_LW_F1_activities_report.txt.
"""
import math
import os

import unreal

import cw_activity as ca
import cw_layout
import cw_schedule as cs

P = unreal.Paths.project_dir()
data = ca.load()
layout = ca.load_layout()
sched = cs.load()
ex = cw_layout.expand(layout)
types = layout["marker_types"]
markers = {m["id"]: m for m in layout["markers"] + ex["markers"]}
openings = [(o["id"], (o["coord"], o["center"]) if o["axis"] == "v" else (o["center"], o["coord"])) for o in layout["openings"] + ex["openings"]
            if o.get("z0", 0) == 0 and o.get("kind") != "secured"]
errs, out = [], []


def rep(m=""):
    out.append(m)
    unreal.log("[ACTCHK] " + m)


rep("== Schema ==")
ca.validate_schema(data, layout, errs)
rep("  schema errors: %d" % len(errs))

rep("")
rep("== Interaction points ==")
for pt in data["interaction_points"]:
    mid = pt["marker_id"]
    m = markers.get(mid)
    if m is None:
        errs.append("%s: marker does not exist in the layout" % mid)
        continue
    if not types.get(m["type"], {}).get("nav", False):
        errs.append("%s: marker type %s is not a navigation destination" % (mid, m["type"]))
    mode, yaw, target = ca.resolve_facing(pt, layout)
    dist_target = math.hypot(target[0] - m["x"], target[1] - m["y"]) if mode == "point" else None
    bearing = math.degrees(math.atan2(target[1] - m["y"], target[0] - m["x"])) if mode == "point" else yaw
    od = min((math.hypot(m["x"] - ox, m["y"] - oy), oid) for oid, (ox, oy) in openings)
    if od[0] < 250:
        errs.append("%s: only %.0f cm from opening %s (< 250)" % (mid, od[0], od[1]))
    if dist_target is not None and dist_target < 50:
        errs.append("%s: facing target is only %.0f cm away" % (mid, dist_target))
    if pt["arrival_tolerance_cm"] < 100:
        errs.append("%s: tolerance %.0f cm is below the ~95 cm at which Move To (radius 60 + capsule 34) stops" % (mid, pt["arrival_tolerance_cm"]))
    users = []
    for nid, a in sched["assignments"].items():
        for pid, e in a["schedule"].items():
            if mid in e["stops"]:
                users.append("%s/%s" % (nid, pid))
    rep("  %-10s -> %-9s marker (%d, %d) facing %s %.1f deg%s ; nearest opening %s %.0f cm ; tolerance %.0f cm ; capacity %d" % (
        mid, pt["activity"], m["x"], m["y"], mode, bearing, (" at distance %.0f cm" % dist_target) if dist_target is not None else "", od[1], od[0], pt["arrival_tolerance_cm"], pt["capacity"]))
    rep("             scheduled use: %s" % (", ".join(users) if users else "NONE (no NPC is scheduled there)"))
    if not users:
        errs.append("%s: no NPC is scheduled to this interaction point" % mid)

rep("")
rep("== Animations ==")
ar = unreal.AssetRegistryHelpers.get_asset_registry()
for a in data["activities"]:
    for key in ("enter_animation", "loop_animation", "exit_animation"):
        path = a.get(key)
        if not path:
            rep("  %-10s %-15s (none - falls back to the normal idle pose)" % (a["id"], key))
            continue
        asset = unreal.load_asset(path)
        if asset is None or not isinstance(asset, unreal.AnimSequence):
            errs.append("%s.%s: %s is not an existing AnimSequence" % (a["id"], key, path))
            continue
        skel = asset.get_editor_property("skeleton")
        ok = skel is not None and skel.get_name() == "SK_Mannequin"
        rep("  %-10s %-15s %s (%.2f s, skeleton %s)%s" % (a["id"], key, path, asset.get_play_length(), skel.get_name() if skel else None, "" if ok else "  INCOMPATIBLE"))
        if not ok:
            errs.append("%s.%s: skeleton is not SK_Mannequin" % (a["id"], key))

rep("")
rep("RESULT: %s" % ("PASS (0 problems)" if not errs else "FAIL (%d problem(s))" % len(errs)))
for e in errs:
    rep("  - " + e)
with open(os.path.join(P, "Docs", "Layout", "S01_LW_F1_activities_report.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
unreal.SystemLibrary.quit_editor()
