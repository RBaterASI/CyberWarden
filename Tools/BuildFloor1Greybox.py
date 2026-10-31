"""
Cyber Warden - Sector 01 / Left Wing / Floor 1 greybox builder.

Run inside the Unreal Editor (Python) or headless:
  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs path>/Tools/BuildFloor1Greybox.py"

Reads Docs/Layout/S01_LW_F1.json, spawns basic cube static-mesh actors in a NEW level, validates
the result analytically (character-capsule walk simulation) and writes a report next to the JSON.
It never edits existing assets other than creating/saving the new level.
"""
import json
import math
import os

import unreal

PROJECT = unreal.Paths.project_dir()
LAYOUT = os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1.json")
REPORT = os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1_build_report.txt")
TAG = "S01F1Greybox"
ROOT = "S01_LW_F1"
CUBE_PATH = "/Engine/BasicShapes/Cube.Cube"
MAT_PATH = "/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial"
GAMEMODE_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"

LOG = []
ERRORS = []
WARNINGS = []


def log(msg):
    LOG.append(msg)
    unreal.log("[F1Greybox] " + msg)


def warn(msg):
    WARNINGS.append(msg)
    LOG.append("WARNING: " + msg)
    unreal.log_warning("[F1Greybox] " + msg)


def err(msg):
    ERRORS.append(msg)
    LOG.append("ERROR: " + msg)
    unreal.log_error("[F1Greybox] " + msg)


with open(LAYOUT, "r", encoding="utf-8") as fh:
    DATA = json.load(fh)
P = DATA["params"]
T = float(P["wall_thickness"])
SLAB = float(P["slab_thickness"])
CAP_R = float(P["capsule_radius"])
CAP_HH = float(P["capsule_half_height"])
STEP = float(P["max_step_height"])

actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

# ----------------------------------------------------------------------------
# Expand data (cell rows -> rooms/openings/boxes/markers)
# ----------------------------------------------------------------------------
ROOMS = [dict(r) for r in DATA["rooms"]]
OPENINGS = [dict(o) for o in DATA["openings"]]
BOXES = [dict(b) for b in DATA["boxes"]]
MARKERS = [dict(m) for m in DATA["markers"]]
CELLS = []

for row in DATA["cell_rows"]:
    for i in range(row["count"]):
        x0 = row["x0"] + i * row["width"]
        x1 = x0 + row["width"]
        if row["side"] == "north":
            y0, y1 = row["hall_edge"], row["hall_edge"] + row["depth"]
            door_y = y0
            inside = y0 + 200
            ins_front = y0 - 100
            bunk_y = (y1 - 110, y1 - 20)
        else:
            y0, y1 = row["hall_edge"] - row["depth"], row["hall_edge"]
            door_y = y1
            inside = y1 - 200
            ins_front = y1 + 100
            bunk_y = (y0 + 20, y0 + 110)
        cid = "Cell_%s%d" % (row["prefix"], i + 1)
        cx = (x0 + x1) / 2.0
        CELLS.append(cid)
        ROOMS.append({"id": cid, "name": "Cell %s%d" % (row["prefix"], i + 1), "zone": "A", "x0": x0, "y0": y0,
                      "x1": x1, "y1": y1, "z": 0, "ceil": row["ceil"], "ceiling": row["ceiling"], "cell": True})
        OPENINGS.append({"id": "Door_" + cid, "name": "Cell door " + cid, "axis": "h", "coord": door_y, "center": cx,
                         "width": row["door_width"], "z0": 0, "height": row["door_height"]})
        BOXES.append({"id": "Bunk_" + cid, "name": "Bunk " + cid, "x0": x0 + 30, "x1": x0 + 250, "y0": bunk_y[0],
                      "y1": bunk_y[1], "z0": 0, "z1": 100})
        MARKERS.append({"id": "CellAssign_" + cid, "type": "CellAssignment", "x": x0 + 150, "y": (bunk_y[0] + bunk_y[1]) / 2 + (-90 if row["side"] == "north" else 90), "z": 0})
        MARKERS.append({"id": "Lockdown_" + cid, "type": "Lockdown", "x": cx, "y": inside, "z": 0})
        MARKERS.append({"id": "Inspection_" + cid, "type": "Inspection", "x": cx, "y": ins_front, "z": 0})

ROOM_BY_ID = {r["id"]: r for r in ROOMS}

# ----------------------------------------------------------------------------
# Level creation
# ----------------------------------------------------------------------------
LEVEL = DATA["meta"]["level"]
if unreal.EditorAssetLibrary.does_asset_exist(LEVEL):
    log("Level exists - loading and clearing previously generated actors")
    level_sub.load_level(LEVEL)
    for a in actor_sub.get_all_level_actors():
        if unreal.Name(TAG) in a.tags:
            actor_sub.destroy_actor(a)
else:
    if not level_sub.new_level(LEVEL):
        err("Could not create level " + LEVEL)
        raise SystemExit
    log("Created new level " + LEVEL)

CUBE = unreal.load_asset(CUBE_PATH)
MAT = unreal.load_asset(MAT_PATH)
if CUBE is None:
    err("Cube mesh missing")

GEO = []  # analytic collision boxes: dict(x0,y0,z0,x1,y1,z1,kind,id)
ACTOR_COUNT = {}


def _count(cls):
    ACTOR_COUNT[cls] = ACTOR_COUNT.get(cls, 0) + 1


def _tag(actor, tags):
    actor.set_editor_property("tags", [unreal.Name(t) for t in tags])


def spawn_box(name, x0, y0, z0, x1, y1, z1, folder, kind, tags=(), collision=True, yaw=0.0):
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    if dx < 0.5 or dy < 0.5 or dz < 0.5:
        return None
    loc = unreal.Vector((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0)
    a = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, loc)
    a.set_actor_label(name)
    a.set_folder_path(ROOT + "/" + folder)
    comp = a.static_mesh_component
    comp.set_static_mesh(CUBE)
    if MAT is not None:
        comp.set_material(0, MAT)
    a.set_actor_scale3d(unreal.Vector(dx / 100.0, dy / 100.0, dz / 100.0))
    if not collision:
        a.set_actor_enable_collision(False)
    _tag(a, [TAG, "Kind:" + kind] + list(tags))
    _count("StaticMeshActor")
    if collision:
        GEO.append({"x0": x0, "y0": y0, "z0": z0, "x1": x1, "y1": y1, "z1": z1, "kind": kind, "id": name})
    return a


def zone_tags(item):
    z = item.get("zone")
    if not z:
        return []
    t = ["Zone:" + z]
    if item.get("zone_provisional"):
        t.append("ZoneProvisional")
    return t


# ----------------------------------------------------------------------------
# Floors / ceilings
# ----------------------------------------------------------------------------
for r in ROOMS:
    zt = zone_tags(r) + ["Room:" + r["id"]]
    spawn_box("Floor_" + r["id"], r["x0"], r["y0"], r["z"] - SLAB, r["x1"], r["y1"], r["z"], "Floors", "floor", zt)
    if P.get("build_ceilings", True) and r.get("ceiling", True):
        top = r["z"] + r["ceil"]
        spawn_box("Ceiling_" + r["id"], r["x0"], r["y0"], top, r["x1"], r["y1"], top + SLAB, "Ceilings", "ceiling", zt)

# ----------------------------------------------------------------------------
# Walls (union of room edges, minus openings)
# ----------------------------------------------------------------------------
LINES = {}
for r in ROOMS:
    base, top = r["z"], r["z"] + r["ceil"]
    for axis, coord, a, b in (("h", r["y0"], r["x0"], r["x1"]), ("h", r["y1"], r["x0"], r["x1"]),
                              ("v", r["x0"], r["y0"], r["y1"]), ("v", r["x1"], r["y0"], r["y1"])):
        LINES.setdefault((axis, float(coord)), []).append((a, b, base, top))

OPENING_USED = {o["id"]: False for o in OPENINGS}
wall_count = 0


def subtract_openings(a, b, base, top, cuts):
    """Return boxes (xa, xb, za, zb) covering [a,b]x[base,top] minus cuts (ox0,ox1,oz0,oz1)."""
    xs = sorted({a, b} | {c[0] for c in cuts} | {c[1] for c in cuts})
    slabs = []
    for xa, xb in zip(xs, xs[1:]):
        if xb - xa < 0.01:
            continue
        covered = sorted((c[2], c[3]) for c in cuts if c[0] <= xa + 0.01 and c[1] >= xb - 0.01)
        z = base
        for c0, c1 in covered:
            if c0 > z + 0.01:
                slabs.append([xa, xb, z, min(c0, top)])
            z = max(z, c1)
        if z < top - 0.01:
            slabs.append([xa, xb, z, top])
    merged = []
    for s in slabs:
        if merged and abs(merged[-1][1] - s[0]) < 0.01 and abs(merged[-1][2] - s[2]) < 0.01 and abs(merged[-1][3] - s[3]) < 0.01:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return merged


for (axis, coord), edges in sorted(LINES.items()):
    pts = sorted({e[0] for e in edges} | {e[1] for e in edges})
    elem = []
    for p, q in zip(pts, pts[1:]):
        cov = [e for e in edges if e[0] <= p + 0.01 and e[1] >= q - 0.01]
        if cov:
            elem.append([p, q, min(e[2] for e in cov), max(e[3] for e in cov)])
    # merge equal neighbours into runs; remember chain ends for corner extension
    runs = []
    for e in elem:
        if runs and abs(runs[-1][1] - e[0]) < 0.01 and abs(runs[-1][2] - e[2]) < 0.01 and abs(runs[-1][3] - e[3]) < 0.01:
            runs[-1][1] = e[1]
        else:
            runs.append(list(e))
    for i, run in enumerate(runs):
        run.append(i == 0 or abs(runs[i - 1][1] - run[0]) > 0.01)  # chain start
        run.append(i == len(runs) - 1 or abs(runs[i + 1][0] - run[1]) > 0.01)  # chain end
    line_openings = [o for o in OPENINGS if o["axis"] == axis and abs(o["coord"] - coord) < 0.01]
    for a, b, base, top, c_start, c_end in runs:
        cuts = []
        for o in line_openings:
            ox0, ox1 = o["center"] - o["width"] / 2.0, o["center"] + o["width"] / 2.0
            oz0, oz1 = o["z0"], o["z0"] + o["height"]
            ox0c, ox1c, oz0c, oz1c = max(a, ox0), min(b, ox1), max(base, oz0), min(top, oz1)
            if ox1c > ox0c and oz1c > oz0c:
                cuts.append((ox0c, ox1c, oz0c, oz1c))
                OPENING_USED[o["id"]] = True
        ext0 = T / 2.0 if (axis == "h" and c_start) else 0.0
        ext1 = T / 2.0 if (axis == "h" and c_end) else 0.0
        for xa, xb, za, zb in subtract_openings(a, b, base, top, cuts):
            xa2 = xa - (ext0 if abs(xa - a) < 0.01 else 0.0)
            xb2 = xb + (ext1 if abs(xb - b) < 0.01 else 0.0)
            if axis == "h":
                spawn_box("Wall_h%d_%d" % (coord, xa), xa2, coord - T / 2, za, xb2, coord + T / 2, zb, "Walls", "wall")
            else:
                spawn_box("Wall_v%d_%d" % (coord, xa), coord - T / 2, xa2, za, coord + T / 2, xb2, zb, "Walls", "wall")
            wall_count += 1

for oid, used in OPENING_USED.items():
    if not used:
        err("Opening %s did not intersect any wall (check coord/center)" % oid)

# Secured panels fill the opening
for o in OPENINGS:
    if o.get("kind") == "secured":
        w2 = o["width"] / 2.0
        if o["axis"] == "h":
            spawn_box("SECURED_" + o["id"], o["center"] - w2, o["coord"] - 8, o["z0"], o["center"] + w2, o["coord"] + 8,
                      o["z0"] + o["height"], "SecuredPanels", "secured", ["Secured", "Door:" + o["id"]])
        else:
            spawn_box("SECURED_" + o["id"], o["coord"] - 8, o["center"] - w2, o["z0"], o["coord"] + 8, o["center"] + w2,
                      o["z0"] + o["height"], "SecuredPanels", "secured", ["Secured", "Door:" + o["id"]])

# ----------------------------------------------------------------------------
# Stairs
# ----------------------------------------------------------------------------
STAIR_STEPS = {}
for s in DATA["stairs"]:
    rise = s["total_rise"] / float(s["steps"])
    run = s["run"]
    steps = []
    for k in range(1, s["steps"] + 1):
        top = s["z_start"] + rise * k
        if s["axis"] == "-x":
            xa, xb = s["start"] - run * k, s["start"] - run * (k - 1)
            box = (xa, s["lo"], xb, s["hi"])
        elif s["axis"] == "-y":
            ya, yb = s["start"] - run * k, s["start"] - run * (k - 1)
            box = (s["lo"], ya, s["hi"], yb)
        else:  # +y
            ya, yb = s["start"] + run * (k - 1), s["start"] + run * k
            box = (s["lo"], ya, s["hi"], yb)
        # solid from below the flight so there is no gap under a step
        spawn_box("%s_Step%02d" % (s["id"], k), box[0], box[1], 0 if s["z_start"] == 0 else s["z_start"], box[2], box[3], top,
                  "Stairs", "stair", zone_tags(s) + ["Stair:" + s["id"]])
        steps.append(top)
    STAIR_STEPS[s["id"]] = (rise, steps)
    log("Stair %s: %d steps, riser %.2f cm, run %d cm" % (s["id"], s["steps"], rise, run))
    if rise > 20:
        warn("Stair %s riser %.1f cm is steep" % (s["id"], rise))

# ----------------------------------------------------------------------------
# Plain boxes / props
# ----------------------------------------------------------------------------
SEATS = []
for b in BOXES:
    kind = "prop" if b["id"].startswith(("Prop_", "Bunk_", "Col_")) else "structure"
    spawn_box(b["name"].replace(" ", "_") + "_" + b["id"], b["x0"], b["y0"], b["z0"], b["x1"], b["y1"], b["z1"],
              "Props" if kind == "prop" else "Structure", kind, zone_tags(b) + ["Id:" + b["id"]],
              collision=b.get("collision", True))
    if b.get("seats"):
        cx = (b["x0"] + b["x1"]) / 2.0
        cy = (b["y0"] + b["y1"]) / 2.0
        n = 0
        for side in (-1, 1):
            for dx in (-100, 0, 100):
                n += 1
                SEATS.append({"id": "Seat_%s_%d" % (b["id"].replace("Prop_Caf_", ""), n), "type": "CafeteriaSeat",
                              "x": cx + dx, "y": cy + side * 95, "z": 0})
MARKERS.extend(SEATS)

# ----------------------------------------------------------------------------
# Markers (TargetPoints) + labels
# ----------------------------------------------------------------------------
MARKER_COUNT = {}
for m in MARKERS:
    loc = unreal.Vector(m["x"], m["y"], m["z"] + 12)
    a = actor_sub.spawn_actor_from_class(unreal.TargetPoint, loc)
    a.set_actor_label("MK_%s_%s" % (m["type"], m["id"]))
    a.set_folder_path("%s/Markers/%s" % (ROOT, m["type"]))
    _tag(a, [TAG, "Marker:" + m["type"], "MarkerId:" + m["id"]])
    _count("TargetPoint")
    MARKER_COUNT[m["type"]] = MARKER_COUNT.get(m["type"], 0) + 1

for r in ROOMS:
    try:
        cx, cy = (r["x0"] + r["x1"]) / 2.0, (r["y0"] + r["y1"]) / 2.0
        a = actor_sub.spawn_actor_from_class(unreal.TextRenderActor, unreal.Vector(cx, cy, r["z"] + 6),
                                             unreal.Rotator(90, 0, 0))
        tr = a.text_render
        tr.set_editor_property("text", r["name"] if not r.get("cell") else r["id"].replace("Cell_", ""))
        tr.set_editor_property("world_size", 40 if r.get("cell") else 70)
        tr.set_editor_property("horizontal_alignment", unreal.HorizTextAligment.EHTA_CENTER)
        a.set_actor_label("Label_" + r["id"])
        a.set_folder_path(ROOT + "/Labels")
        _tag(a, [TAG, "Label"])
        _count("TextRenderActor")
    except Exception as ex:  # labels are cosmetic
        warn("Label failed for %s: %s" % (r["id"], ex))
        break

# ----------------------------------------------------------------------------
# Lights
# ----------------------------------------------------------------------------
ZONE_COLOR = {"A": (255, 236, 205), "B": (255, 200, 120), "C": (170, 200, 255)}
light_n = 0
for r in ROOMS:
    w, d = r["x1"] - r["x0"], r["y1"] - r["y0"]
    nx, ny = max(1, int(round(w / 700.0))), max(1, int(round(d / 700.0)))
    if r.get("cell"):
        nx = ny = 1
    zt = r["z"] + min(r["ceil"], 480) - 50
    col = ZONE_COLOR.get(r.get("zone", "A"), ZONE_COLOR["A"])
    for ix in range(nx):
        for iy in range(ny):
            lx = r["x0"] + w * (ix + 0.5) / nx
            ly = r["y0"] + d * (iy + 0.5) / ny
            a = actor_sub.spawn_actor_from_class(unreal.PointLight, unreal.Vector(lx, ly, zt))
            lc = a.light_component
            lc.set_mobility(unreal.ComponentMobility.MOVABLE)
            lc.set_editor_property("intensity", 4000.0 if not r.get("cell") else 1200.0)
            lc.set_editor_property("attenuation_radius", max(w / nx, d / ny, 500.0) * 0.9)
            lc.set_editor_property("light_color", unreal.Color(col[0], col[1], col[2], 255))
            lc.set_editor_property("cast_shadows", False)
            a.set_actor_label("Light_%s_%d" % (r["id"], light_n))
            a.set_folder_path(ROOT + "/Lights")
            _tag(a, [TAG, "Light"])
            _count("PointLight")
            light_n += 1

# ----------------------------------------------------------------------------
# Player start, nav volume, world settings
# ----------------------------------------------------------------------------
ps = DATA["meta"]["player_start"]
start_loc = unreal.Vector(ps["x"], ps["y"], 100.0)
pstart = actor_sub.spawn_actor_from_class(unreal.PlayerStart, start_loc, unreal.Rotator(0, 0, ps["yaw"]))
pstart.set_actor_label("PlayerStart_Intake")
pstart.set_folder_path(ROOT + "/Gameplay")
_tag(pstart, [TAG, "Spawn:Intake"])
_count("PlayerStart")

try:
    nav = actor_sub.spawn_actor_from_class(unreal.NavMeshBoundsVolume, unreal.Vector(3300, 800, 400))
    nav.set_actor_scale3d(unreal.Vector(130.0, 100.0, 12.0))  # default brush 200 cm -> ~26 x 20 x 2.4 m*100
    nav.set_actor_label("NavMeshBounds_F1")
    nav.set_folder_path(ROOT + "/Gameplay")
    _tag(nav, [TAG])
    _count("NavMeshBoundsVolume")
except Exception as ex:
    warn("NavMeshBoundsVolume not created: %s" % ex)

gm_report = "unknown"
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    gm_class = unreal.EditorAssetLibrary.load_blueprint_class(GAMEMODE_PATH)
    ws = world.get_world_settings()
    ws.set_editor_property("default_game_mode", gm_class)
    cdo = unreal.get_default_object(gm_class)
    pawn = cdo.get_editor_property("default_pawn_class")
    gm_report = "GameMode=%s DefaultPawn=%s" % (gm_class.get_name(), pawn.get_name() if pawn else "None")
    log("World Settings override: " + gm_report)
    if not pawn or "CyberWardenCharacter" not in pawn.get_name():
        warn("GameMode default pawn is not BP_CyberWardenCharacter: " + gm_report)
except Exception as ex:
    err("GameMode setup failed: %s" % ex)

# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------
REPORT_LINES = []


def rep(s):
    REPORT_LINES.append(s)
    log(s)


rep("== Validation ==")

# 1. Room overlap (3D)
overlaps = 0
for i, a in enumerate(ROOMS):
    for b in ROOMS[i + 1:]:
        ox = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
        oy = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
        oz = min(a["z"] + a["ceil"], b["z"] + b["ceil"]) - max(a["z"], b["z"])
        if ox > 0.5 and oy > 0.5 and oz > 0.5:
            err("Rooms overlap: %s / %s" % (a["id"], b["id"]))
            overlaps += 1
rep("Room volume overlaps: %d" % overlaps)

# 2. Door dimensions
min_door = min(o["width"] for o in OPENINGS if o.get("z0", 0) == 0 and o["height"] < 500)
rep("Smallest walkable opening width: %d cm (capsule diameter %d cm)" % (min_door, 2 * CAP_R))
for o in OPENINGS:
    if o["width"] < 2 * CAP_R + 40 and "Win_" not in o["id"]:
        warn("Opening %s only %d cm wide" % (o["id"], o["width"]))
    if o["height"] < 2 * CAP_HH + 40 and o["height"] < 500 and "Win_" not in o["id"] and "Rail" not in o["id"]:
        warn("Opening %s only %d cm high" % (o["id"], o["height"]))
corr = [(r["id"], min(r["x1"] - r["x0"], r["y1"] - r["y0"])) for r in ROOMS if "Corridor" in r["id"] or "Link" in r["id"] or "Vestibule" in r["id"]]
rep("Corridor clear widths (centre-to-centre): " + ", ".join("%s=%d" % c for c in corr))

# 3. Prop vs structure overlaps
bad = 0
for p in [g for g in GEO if g["kind"] == "prop"]:
    for g in GEO:
        if g["kind"] in ("wall", "floor", "ceiling", "stair", "secured") or (g["kind"] == "prop" and g is not p and g["id"] < p["id"]):
            ox = min(p["x1"], g["x1"]) - max(p["x0"], g["x0"])
            oy = min(p["y1"], g["y1"]) - max(p["y0"], g["y0"])
            oz = min(p["z1"], g["z1"]) - max(p["z0"], g["z0"])
            if ox > 1 and oy > 1 and oz > 1:
                warn("Prop %s intersects %s %s" % (p["id"], g["kind"], g["id"]))
                bad += 1
rep("Prop/structure intersections: %d" % bad)

# 4. Capsule walk simulation
walls = [g for g in GEO]


def walk_blocked(px, py, floor):
    """Return blocking geo id or None for a capsule standing on 'floor' at (px,py)."""
    zb, zt = floor, floor + 2 * CAP_HH
    for g in walls:
        if g["z1"] <= floor + 0.5 or g["z0"] >= zt - 0.5:
            continue
        dx = max(g["x0"] - px, 0, px - g["x1"])
        dy = max(g["y0"] - py, 0, py - g["y1"])
        if dx * dx + dy * dy < (CAP_R - 0.5) ** 2:
            return g["id"]
    return None


def floor_at(px, py, ref):
    best = None
    for g in walls:
        if g["z1"] > ref + STEP + 0.01:
            continue
        dx = max(g["x0"] - px, 0, px - g["x1"])
        dy = max(g["y0"] - py, 0, py - g["y1"])
        if dx * dx + dy * dy < CAP_R ** 2:
            if best is None or g["z1"] > best:
                best = g["z1"]
    return best


def simulate(route):
    z = float(route["z"])
    first = route["points"][0]
    f = floor_at(first[0], first[1], z)
    if f is None:
        return False, "no floor at start %s" % (first,), z
    z = f
    for p0, p1 in zip(route["points"], route["points"][1:]):
        dist = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        n = max(1, int(dist / 8))
        for k in range(n + 1):
            t = k / float(n)
            x, y = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
            f = floor_at(x, y, z)
            if f is None:
                return False, "floor lost at (%d,%d) z=%.0f" % (x, y, z), z
            if f < z - STEP:
                return False, "drop of %.0f cm at (%d,%d)" % (z - f, x, y), z
            z = f
            hit = walk_blocked(x, y, z)
            if hit:
                return False, "blocked by %s at (%d,%d) z=%.0f" % (hit, x, y, z), z
    return True, "ok", z


failures = 0
for route in DATA["routes"]:
    ok, why, zend = simulate(route)
    rep("  route %-34s %s%s (end floor z=%.0f)" % (route["id"], "PASS" if ok else "FAIL ", "" if ok else " - " + why, zend))
    if not ok:
        err("Route %s failed: %s" % (route["id"], why))
        failures += 1
for route in DATA["blocked_routes"]:
    ok, why, zend = simulate(route)
    rep("  secured %-32s %s (%s)" % (route["id"], "PASS (blocked)" if not ok else "FAIL (passable!)", why))
    if ok:
        err("Secured route %s is passable" % route["id"])
        failures += 1

# Spawn validity
sf = floor_at(ps["x"], ps["y"], 0.0)
sb = walk_blocked(ps["x"], ps["y"], sf if sf is not None else 0.0)
rep("Intake spawn: floor z=%s, blocked=%s -> %s" % (sf, sb, "VALID" if sf is not None and sb is None else "INVALID"))
if sf is None or sb is not None:
    err("Player start invalid")
rep("PlayerStart placed at z=100 (engine drops it to floor on spawn); capsule fits with %.0f cm headroom" % (380 - 2 * CAP_HH))

# Stair elevation
final_top = max(STAIR_STEPS["Stair_F1_Flight2"][1])
rep("Staircase top step z=%.1f (floor-to-floor %s) -> %s" % (final_top, DATA["meta"]["floor_to_floor"], "MATCH" if abs(final_top - DATA["meta"]["floor_to_floor"]) < 0.5 else "MISMATCH"))
if abs(final_top - DATA["meta"]["floor_to_floor"]) > 0.5:
    err("Stair elevation mismatch")

# Engine-side collision sanity
try:
    cnt = unreal.EditorStaticMeshLibrary.get_simple_collision_count(CUBE)
    rep("Engine cube mesh simple collision shapes: %d" % cnt)
    if cnt < 1:
        err("Cube has no simple collision")
except Exception as ex:
    warn("Could not query cube collision: %s" % ex)

# ----------------------------------------------------------------------------
# Save + report
# ----------------------------------------------------------------------------
saved = level_sub.save_current_level()
rep("Level saved: %s" % saved)
total = sum(ACTOR_COUNT.values())
rep("== Actor counts (generated) ==")
for k in sorted(ACTOR_COUNT):
    rep("  %-22s %d" % (k, ACTOR_COUNT[k]))
rep("  TOTAL                  %d  (walls: %d)" % (total, wall_count))
rep("Markers by type: " + ", ".join("%s=%d" % kv for kv in sorted(MARKER_COUNT.items())))
rep("Cells: %d (%s)" % (len(CELLS), ", ".join(CELLS)))
rep("GameMode: " + gm_report)
rep("Assets created: 1 (%s)" % LEVEL)
rep("Errors: %d  Warnings: %d" % (len(ERRORS), len(WARNINGS)))

with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(LOG))
unreal.log("[F1Greybox] DONE errors=%d warnings=%d" % (len(ERRORS), len(WARNINGS)))
