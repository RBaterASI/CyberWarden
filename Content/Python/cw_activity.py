"""M2.3 activity data support: loading, facing resolution and structural validation of Docs/Layout/S01_LW_F1_activities.json.

Pure Python (no `unreal` import), used by Tools/ConfigureActivities.py, Tools/ValidateActivities.py and the tests.
"""
import json
import os

FACING_MODES = ("none", "yaw", "point", "prop")
# Optional per-point final approach (M2.3 Stage C2): the NPC walks the last stretch to the exact marker with AI navigation before the activity starts.
FINAL_APPROACH_DEFAULTS = {"accept_cm": 3.0, "tolerance_cm": 5.0, "max_distance_cm": 80.0, "timeout_seconds": 3.0}
# Optional per-phase timing (M2.3 Stage C1); a missing or negative value inherits blend_in / blend_out / the component's grace.
TIMING_KEYS = ("enter_blend_in_seconds", "loop_blend_in_seconds", "exit_blend_in_seconds", "exit_blend_out_seconds", "release_grace_seconds")


def project_dir():
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def load(path=None):
    path = path or os.path.join(project_dir(), "Docs", "Layout", "S01_LW_F1_activities.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_layout():
    with open(os.path.join(project_dir(), "Docs", "Layout", "S01_LW_F1.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


def prop_center(layout, prop_id):
    """XY centre and top height of a layout box, or None."""
    for b in layout.get("boxes", []):
        if b["id"] == prop_id:
            return ((b["x0"] + b["x1"]) / 2.0, (b["y0"] + b["y1"]) / 2.0, b.get("z1", 0.0))
    return None


def resolve_facing(point, layout):
    """Returns (mode, yaw_degrees, (x, y, z)) with mode in none/yaw/point; 'prop' facing becomes a point at the prop centre."""
    f = point.get("facing", {"mode": "none"})
    mode = f.get("mode", "none")
    if mode == "prop":
        c = prop_center(layout, f.get("prop_id", ""))
        if c is None:
            raise ValueError("unknown prop %s" % f.get("prop_id"))
        return "point", 0.0, c
    if mode == "point":
        return "point", 0.0, (f["x"], f["y"], f.get("z", 0.0))
    if mode == "yaw":
        return "yaw", float(f["degrees"]), (0.0, 0.0, 0.0)
    return "none", 0.0, (0.0, 0.0, 0.0)


def validate_schema(data, layout, errs):
    def need(cond, msg):
        if not cond:
            errs.append(msg)
        return cond

    ids = set()
    for a in data.get("activities", []):
        aid = a.get("id")
        need(bool(aid), "activity without id")
        need(aid not in ids, "duplicate activity id %s" % aid)
        ids.add(aid)
        need(bool(a.get("slot")), "%s: no animation slot" % aid)
        need(a.get("blend_in_seconds", 0) >= 0 and a.get("blend_out_seconds", 0) >= 0, "%s: negative blend time" % aid)
        need(a.get("play_rate", 1) > 0, "%s: play rate must be > 0" % aid)
        for k in TIMING_KEYS:
            need(isinstance(a.get(k, -1), (int, float)), "%s: %s must be a number (negative = inherit)" % (aid, k))
        need(not a.get("commit_enter", False) or bool(a.get("enter_animation")), "%s: commit_enter needs an enter animation" % aid)
        need(a.get("align_yaw_rate_deg_per_sec", 1) > 0 and a.get("yaw_tolerance_degrees", 1) > 0, "%s: align rate and yaw tolerance must be > 0" % aid)
    markers = set()
    for p in data.get("interaction_points", []):
        mid = p.get("marker_id")
        need(bool(mid), "interaction point without marker id")
        need(mid not in markers, "duplicate interaction point for %s" % mid)
        markers.add(mid)
        need(p.get("activity") in ids, "%s: unknown activity %s" % (mid, p.get("activity")))
        need(p.get("arrival_tolerance_cm", 0) > 0, "%s: arrival tolerance must be > 0" % mid)
        need(p.get("capacity", 1) >= 1, "%s: capacity must be >= 1" % mid)
        fa = p.get("final_approach")  # M2.3 Stage C2: optional precision approach; absent or enabled=false leaves the point exactly as before
        if fa is not None:
            need(isinstance(fa.get("enabled", False), bool), "%s: final_approach.enabled must be true or false" % mid)
            vals = [fa.get(k, d) for k, d in FINAL_APPROACH_DEFAULTS.items()]
            need(all(isinstance(v, (int, float)) and v > 0 for v in vals), "%s: final_approach accept radius, tolerance, maximum distance and timeout must be numbers > 0" % mid)
            need(fa.get("tolerance_cm", FINAL_APPROACH_DEFAULTS["tolerance_cm"]) >= fa.get("accept_cm", FINAL_APPROACH_DEFAULTS["accept_cm"]), "%s: final_approach tolerance must be >= its accept radius" % mid)
        mode = p.get("facing", {"mode": "none"}).get("mode", "none")
        need(mode in FACING_MODES, "%s: unknown facing mode %s" % (mid, mode))
        if mode == "prop":
            need(prop_center(layout, p["facing"].get("prop_id", "")) is not None, "%s: facing prop %s is not in the layout" % (mid, p["facing"].get("prop_id")))
