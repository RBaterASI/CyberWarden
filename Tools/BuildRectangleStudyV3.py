"""
Cyber Warden - Sector 01 / Left Wing / Floor 1 RECTANGLE STUDY V3 builder (Unreal Python).

Creates the NEW level /Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_RectangleStudy_V3 from
Docs/Layout/S01_LW_F1_RectangleStudy_V3.json (V2 + kitchen / laundry / service hallway on a widened service side). Geometry
lives in Content/Python/cw_rectstudy_v2.py (StudyV2, pure Python) and the V3 validation in Content/Python/cw_rectstudy_v3.py;
this script only spawns what they generate and sets the
world's game mode to the existing BP_ThirdPersonGameMode (BP_CyberWardenCharacter, existing controller, camera and +-90 deg
orbit - none of it modified).

Run in the OPEN editor (Cmd box):   py "<abs path to this file>"
or headless:  powershell -File Tools\\RunHeadless.ps1 -Script Tools\\BuildRectangleStudyV3.py

Source files are read from the project that contains THIS script; the level and the new MI_RS3_* material instances are
created in whichever project is open. It writes only: the new level, new MI_RS3_* assets (reusing the existing M_GB_Lit /
M_GB_Unlit parents) and Docs/Layout/S01_LW_F1_RectangleStudy_V3_build_report.txt. It never touches L_S01_LW_F1_Greybox,
the V1/V2 study maps, their layouts, or any existing asset, and it records SHA-256 hashes of those files before and after.
"""
import hashlib
import os
import sys

import unreal

PROJECT = unreal.Paths.project_dir()          # the project that is OPEN (where the level/materials are created)
try:                                          # the project that holds THIS script and the study sources (may differ)
    SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    SRC = PROJECT
sys.path.insert(0, os.path.join(SRC, "Content", "Python"))
import cw_rectstudy_v2 as cw  # noqa: E402  (StudyV2 geometry + load)
import cw_rectstudy_v3 as cw3  # noqa: E402  (V3 analysis)

LAYOUT = os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V3.json")
REPORT = os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V3_build_report.txt")
PROTECTED_LEVELS = ("L_S01_LW_F1_Greybox", "L_S01_LW_F1_RectangleStudy", "L_S01_LW_F1_RectangleStudy_V2")   # the accepted M1 map, the V1 and V2 studies (exact names)
KEEP_FILES = [os.path.join(PROJECT, "Content", "CyberWarden", "Maps", "Sector01", "L_S01_LW_F1_Greybox.umap"),
              os.path.join(PROJECT, "Content", "CyberWarden", "Maps", "Sector01", "L_S01_LW_F1_RectangleStudy.umap"),
              os.path.join(PROJECT, "Content", "CyberWarden", "Maps", "Sector01", "L_S01_LW_F1_RectangleStudy_V2.umap"),
              os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1.json"),
              os.path.join(PROJECT, "Content", "Python", "cw_layout.py"),
              os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy.json"),
              os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V2.json"),
              os.path.join(SRC, "Content", "Python", "cw_rectstudy.py"),
              os.path.join(SRC, "Content", "Python", "cw_rectstudy_v2.py")]
TAG = "S01F1RectStudyV3"
ROOT = "S01_LW_F1_RectangleStudy_V3"
CUBE_PATH = "/Engine/BasicShapes/Cube.Cube"
GRID_MAT_PATH = "/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial"
GAMEMODE_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"
MAT_DIR = "/Game/CyberWarden/Materials"

LOG, ERRORS, WARNINGS = [], [], []


def log(msg):
    LOG.append(msg)
    unreal.log("[RectStudyV3] " + msg)


def warn(msg):
    WARNINGS.append(msg)
    LOG.append("WARNING: " + msg)
    unreal.log_warning("[RectStudyV3] " + msg)


def err(msg):
    ERRORS.append(msg)
    LOG.append("ERROR: " + msg)
    unreal.log_error("[RectStudyV3] " + msg)


def sha(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return "missing"


data = cw.load(LAYOUT)
LEVEL = data["meta"]["level"]
if LEVEL.rsplit("/", 1)[-1] in PROTECTED_LEVELS:
    err("Refusing to run: layout level path points at a protected map")
    raise SystemExit
BEFORE = {p: sha(p) for p in KEEP_FILES}
study = cw.StudyV2(data)

actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

# ----------------------------------------------------------------------------
# Level
# ----------------------------------------------------------------------------
if unreal.EditorAssetLibrary.does_asset_exist(LEVEL):
    log("V3 level exists - loading and clearing previously generated V3 actors only")
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
GRID = unreal.load_asset(GRID_MAT_PATH)
if CUBE is None:
    err("Cube mesh missing")

# ----------------------------------------------------------------------------
# Materials: reuse M_GB_Lit / M_GB_Unlit parents; NEW MI_RS3_* instances only (V1's MI_RS_* are left alone)
# ----------------------------------------------------------------------------
ASSETS_CREATED = []
_MATS = {}


def _parent(name, unlit):
    path = "%s/%s" % (MAT_DIR, name)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.load_asset(path)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(name, MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    lib = unreal.MaterialEditingLibrary
    param = lib.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -400, 0)
    param.set_editor_property("parameter_name", "Color")
    param.set_editor_property("default_value", unreal.LinearColor(0.5, 0.5, 0.5, 1.0))
    if unlit:
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        lib.connect_material_property(param, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    else:
        lib.connect_material_property(param, "", unreal.MaterialProperty.MP_BASE_COLOR)
        rough = lib.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 200)
        rough.set_editor_property("r", 0.9)
        lib.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    lib.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    ASSETS_CREATED.append(path)
    return mat


P_LIT = _parent("M_GB_Lit", False)
P_UNLIT = _parent("M_GB_Unlit", True)


def material(key):
    """None -> engine grid; 'lit:Area' / 'unlit:Area' -> MI_RS3_Lit_Area / MI_RS3_Unlit_Area."""
    if key is None:
        return GRID
    if key in _MATS:
        return _MATS[key]
    kind, area = key.split(":", 1)
    rgb = data["areas"][area]["color"]
    scale = 0.55 if kind == "lit" else 1.0
    name = "MI_RS3_%s_%s" % ("Lit" if kind == "lit" else "Unlit", area)
    path = "%s/%s" % (MAT_DIR, name)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mic = unreal.load_asset(path)
    else:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        mic = tools.create_asset(name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        ASSETS_CREATED.append(path)
    mic.set_editor_property("parent", P_LIT if kind == "lit" else P_UNLIT)
    lin = unreal.LinearColor((rgb[0] / 255.0) ** 2.2 * scale, (rgb[1] / 255.0) ** 2.2 * scale, (rgb[2] / 255.0) ** 2.2 * scale, 1.0)
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mic, "Color", lin)
    unreal.EditorAssetLibrary.save_loaded_asset(mic)
    _MATS[key] = mic
    return mic


# ----------------------------------------------------------------------------
# Spawning
# ----------------------------------------------------------------------------
COUNT = {}


def _count(cls):
    COUNT[cls] = COUNT.get(cls, 0) + 1


def _tag(actor, tags):
    actor.set_editor_property("tags", [unreal.Name(t) for t in tags])


def spawn_cube(label, loc, scale, folder, tags, collision, mat_key, rot=None):
    a = actor_sub.spawn_actor_from_class(unreal.StaticMeshActor, loc)
    a.set_actor_label(label)
    a.set_folder_path(ROOT + "/" + folder)
    comp = a.static_mesh_component
    comp.set_static_mesh(CUBE)
    m = material(mat_key)
    if m is not None:
        comp.set_material(0, m)
    if rot is not None:
        a.set_actor_rotation(rot, False)
    a.set_actor_scale3d(scale)
    if not collision:
        a.set_actor_enable_collision(False)
    _tag(a, [TAG] + list(tags))
    _count("StaticMeshActor")
    return a


for b in study.boxes:
    dx, dy, dz = b["x1"] - b["x0"], b["y1"] - b["y0"], b["z1"] - b["z0"]
    spawn_cube(b["id"], unreal.Vector((b["x0"] + b["x1"]) / 2.0, (b["y0"] + b["y1"]) / 2.0, (b["z0"] + b["z1"]) / 2.0),
               unreal.Vector(dx / 100.0, dy / 100.0, dz / 100.0), b["folder"], ["Kind:" + b["kind"]] + b["tags"], b["collision"], b["mat"])
log("Spawned %d axis-aligned boxes" % len(study.boxes))

for ln in study.lines:
    spawn_cube(ln["id"], unreal.Vector(ln["cx"], ln["cy"], ln["cz"]), unreal.Vector(ln["len"] / 100.0, ln["w"] / 100.0, ln["h"] / 100.0),
               ln["folder"], ["Kind:marking"], False, ln["mat"], rot=unreal.Rotator(roll=0.0, pitch=ln["pitch"], yaw=ln["yaw"]))

for t in study.texts:
    a = actor_sub.spawn_actor_from_class(unreal.TextRenderActor, unreal.Vector(t["x"], t["y"], t["z"]), unreal.Rotator(0, 0, t["yaw"]))
    tr = a.text_render
    tr.set_editor_property("text", t["text"])
    tr.set_editor_property("world_size", t["size"])
    tr.set_editor_property("horizontal_alignment", unreal.HorizTextAligment.EHTA_CENTER)
    tr.set_editor_property("vertical_alignment", unreal.VerticalTextAligment.EVRTA_TEXT_CENTER)
    c = t["color"]
    tr.set_editor_property("text_render_color", unreal.Color(c[0], c[1], c[2], 255))
    a.set_actor_label(t["id"])
    a.set_folder_path(ROOT + "/Signs")
    _tag(a, [TAG, "Sign", "Area:" + t["area"]])
    a.set_actor_enable_collision(False)
    _count("TextRenderActor")
log("Spawned %d text signs" % len(study.texts))

MARKER_COUNT = {}
for m in study.markers:
    a = actor_sub.spawn_actor_from_class(unreal.TargetPoint, unreal.Vector(m["x"], m["y"], m["z"] + 12))
    a.set_actor_label("MK_%s_%s" % (m["type"], m["id"]))
    a.set_folder_path("%s/Markers/%s" % (ROOT, m["type"]))
    _tag(a, [TAG, "Marker:" + m["type"], "MarkerId:" + m["id"], "NavDest:No"])
    a.set_actor_hidden_in_game(True)
    _count("TargetPoint")
    MARKER_COUNT[m["type"]] = MARKER_COUNT.get(m["type"], 0) + 1
log("Spawned %d metadata markers (hidden in game): %s" % (len(study.markers), ", ".join("%s=%d" % kv for kv in sorted(MARKER_COUNT.items()))))

for l in study.lights:
    a = actor_sub.spawn_actor_from_class(unreal.PointLight, unreal.Vector(l["x"], l["y"], l["z"]))
    lc = a.light_component
    lc.set_mobility(unreal.ComponentMobility.MOVABLE)
    lc.set_editor_property("intensity", l["intensity"])
    lc.set_editor_property("attenuation_radius", l["radius"])
    lc.set_editor_property("light_color", unreal.Color(l["color"][0], l["color"][1], l["color"][2], 255))
    lc.set_editor_property("cast_shadows", False)
    a.set_actor_label(l["id"])
    a.set_folder_path(ROOT + "/Lights")
    _tag(a, [TAG, "Light"])
    _count("PointLight")
log("Spawned %d point lights" % len(study.lights))

ps = data["meta"]["player_start"]
pstart = actor_sub.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(ps["x"], ps["y"], 100.0), unreal.Rotator(0, 0, ps["yaw"]))
pstart.set_actor_label("PlayerStart_LowerHallWest")
pstart.set_folder_path(ROOT + "/Gameplay")
_tag(pstart, [TAG, "Spawn:LowerHallWest"])
_count("PlayerStart")

gm_report = "unknown"
try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    gm_class = unreal.EditorAssetLibrary.load_blueprint_class(GAMEMODE_PATH)
    ws = world.get_world_settings()
    ws.set_editor_property("default_game_mode", gm_class)
    pawn = unreal.get_default_object(gm_class).get_editor_property("default_pawn_class")
    gm_report = "GameMode=%s DefaultPawn=%s" % (gm_class.get_name(), pawn.get_name() if pawn else "None")
    log("World Settings override: " + gm_report)
    if not pawn or "CyberWardenCharacter" not in pawn.get_name():
        warn("GameMode default pawn is not BP_CyberWardenCharacter: " + gm_report)
except Exception as ex:
    err("GameMode setup failed: %s" % ex)

# ----------------------------------------------------------------------------
# Analytic validation (same code as Tools/ValidateRectangleStudyV3.py)
# ----------------------------------------------------------------------------
def rep(s):
    log(s)


a_errors, a_warnings = cw3.run_analysis(study, rep)
ERRORS.extend(a_errors)
WARNINGS.extend(a_warnings)

# ----------------------------------------------------------------------------
# Engine-side collision spot checks (line traces; traces start BELOW the roof slab, z<=450)
# ----------------------------------------------------------------------------
rep("== Engine-side collision spot checks (line traces, Visibility channel) ==")


def trace(p0, p1):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    res = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(*p0), unreal.Vector(*p1), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                 False, [], unreal.DrawDebugTrace.NONE, True)
    if isinstance(res, tuple):
        ok, hit = res[0], res[1]
    else:
        ok, hit = res is not None, res
    if not ok:
        return None
    for attr in ("impact_point", "location"):
        try:
            v = getattr(hit, attr)
        except Exception:
            try:
                v = hit.get_editor_property(attr)
            except Exception:
                continue
        return (v.x, v.y, v.z)
    for v in hit.to_tuple():
        if hasattr(v, "x") and hasattr(v, "z"):
            return (v.x, v.y, v.z)
    return None


CHECKS = [("lower hall floor at the player start", (1100, 1400, 100), (1100, 1400, -50), 2, 0.0),
          ("lower hall floor under the crossover", (3200, 1400, 300), (3200, 1400, -50), 2, 0.0),
          ("crossover deck", (3200, 1400, 450), (3200, 1400, 300), 2, 390.0),
          ("south walkway deck", (2000, 650, 450), (2000, 650, 300), 2, 390.0),
          ("north walkway deck", (2000, 2150, 450), (2000, 2150, 300), 2, 390.0),
          ("west walkway deck", (650, 1400, 450), (650, 1400, 300), 2, 390.0),
          ("guard office floor", (4500, 300, 450), (4500, 300, 300), 2, 390.0),
          ("guard lookout floor", (5850, 1400, 450), (5850, 1400, 300), 2, 390.0),
          ("south stair step at x=4600 (13th step)", (4600, 650, 450), (4600, 650, 100), 2, 230.5),
          ("north stair step at x=4600 (13th step)", (4600, 2150, 450), (4600, 2150, 100), 2, 230.5),
          ("service hallway floor behind the kitchen", (1000, -1180, 100), (1000, -1180, -50), 2, 0.0),
          ("laundry floor", (1400, -2000, 100), (1400, -2000, -50), 2, 0.0),
          ("hall east wall / Sector Floor 2 secured door panel (blocks at x~5592)", (5400, 1400, 90), (5700, 1400, 90), 0, 5592.0),
          ("hall east wall beside the secured door (blocks at x~5585)", (5400, 1800, 300), (5700, 1800, 300), 0, 5585.0),
          ("lookout window is OPEN (ray z=520 reaches the exterior wall at x~6085)", (5400, 1400, 520), (6200, 1400, 520), 0, 6085.0),
          ("south walkway balustrade blocks (top bar at y~788)", (2000, 650, 495), (2000, 1000, 495), 1, 788.0),
          ("kitchen hatch is OPEN: seating -> kitchen -> back door -> hallway south wall (y~-1345)", (2000, 100, 170), (2000, -1500, 170), 1, -1345.0),
          ("service hallway east run: dog-leg wall stops sight (ray along A hits x~3285)", (250, -1180, 170), (4500, -1180, 170), 0, 3285.0)]
try:
    for label, p0, p1, axis, expect in CHECKS:
        hit = trace(p0, p1)
        if hit is None:
            err("Engine trace '%s' hit nothing" % label)
            rep("  %-70s NO HIT" % label)
            continue
        val = hit[axis]
        good = abs(val - expect) <= 3.0
        rep("  %-70s hit %s=%.1f expected %.1f -> %s" % (label, "xyz"[axis], val, expect, "ok" if good else "MISMATCH"))
        if not good:
            err("Engine trace '%s' mismatch: %.1f vs %.1f" % (label, val, expect))
except Exception as ex:
    warn("Engine-side trace checks skipped: %s" % ex)
    rep("  skipped (%s)" % ex)

# ----------------------------------------------------------------------------
# Save + report
# ----------------------------------------------------------------------------
saved = level_sub.save_current_level()
rep("Level saved: %s (%s)" % (saved, LEVEL))
rep("== Actor counts (generated) ==")
for k in sorted(COUNT):
    rep("  %-22s %d" % (k, COUNT[k]))
rep("  TOTAL                  %d" % sum(COUNT.values()))
rep("GameMode: " + gm_report)
rep("New assets created: level + %s" % (", ".join(ASSETS_CREATED) or "none new beyond the level"))
AFTER = {p: sha(p) for p in KEEP_FILES}
for p in KEEP_FILES:
    same = BEFORE[p] == AFTER[p]
    rep("Preservation: %-84s %s" % (p.replace("\\", "/").split("Unreal Projects/")[-1], ("UNCHANGED" if BEFORE[p] != "missing" else "not present") if same else "CHANGED!"))
    if not same:
        err("Protected file changed: " + p)
rep("Errors: %d  Warnings: %d" % (len(ERRORS), len(WARNINGS)))
with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(LOG))
unreal.log("[RectStudyV3] DONE errors=%d warnings=%d" % (len(ERRORS), len(WARNINGS)))
