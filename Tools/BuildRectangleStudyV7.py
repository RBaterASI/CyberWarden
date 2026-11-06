"""
Cyber Warden - Sector 01 / Left Wing / Floor 1 RECTANGLE STUDY V7 builder (review map) (Unreal Python).

Creates the NEW level /Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_RectangleStudy_V7 from
Docs/Layout/S01_LW_F1_RectangleStudy_V7.json (the Greybox Build Sheet CONFINED LAYOUT, boards 10 + 11: 61 x 51 m, 32 lower + 24 upper blocks, full-height mesh,
safety net, three-sided staff chase, 30 cells). Geometry lives in Content/Python/cw_rectstudy_v2.py (StudyV2), cw_rectstudy_v6.py (StudyV6) and
cw_rectstudy_v7.py (StudyV7 mesh/net layer and the V7 validation, pure Python);
this script only spawns what they generate and sets the
world's game mode to the existing BP_ThirdPersonGameMode (BP_CyberWardenCharacter, existing controller, camera and +-90 deg
orbit - none of it modified).

Run in the OPEN editor (Cmd box):   py "<abs path to this file>"
or headless:  powershell -File Tools\\RunHeadless.ps1 -Script Tools\\BuildRectangleStudyV7.py

Source files are read from the project that contains THIS script; the level and the new MI_RS7_* material instances are
created in whichever project is open. It writes only: the new level, new MI_RS7_* assets (reusing the existing M_GB_Lit /
M_GB_Unlit parents) and Docs/Layout/S01_LW_F1_RectangleStudy_V7_build_report.txt. It never touches L_S01_LW_F1_Greybox,
the V1-V6 study maps, their layouts, or any existing asset, and it records SHA-256 hashes of those files before and after.
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
import cw_rectstudy_v7 as cw7  # noqa: E402  (StudyV7 + V7 analysis)

LAYOUT = os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V7.json")
REPORT = os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V7_build_report.txt")
PROTECTED_LEVELS = ("L_S01_LW_F1_Greybox", "L_S01_LW_F1_RectangleStudy", "L_S01_LW_F1_RectangleStudy_V2", "L_S01_LW_F1_RectangleStudy_V3", "L_S01_LW_F1_RectangleStudy_V4", "L_S01_LW_F1_RectangleStudy_V5", "L_S01_LW_F1_RectangleStudy_V6")   # the accepted M1 map and the V1-V6 studies (exact names)
KEEP_FILES = [os.path.join(PROJECT, "Content", "CyberWarden", "Maps", "Sector01", "L_S01_LW_F1_Greybox.umap"),
              os.path.join(PROJECT, "Content", "CyberWarden", "Maps", "Sector01", "L_S01_LW_F1_RectangleStudy.umap"),
              os.path.join(PROJECT, "Content", "CyberWarden", "Maps", "Sector01", "L_S01_LW_F1_RectangleStudy_V2.umap"),
              os.path.join(PROJECT, "Content", "CyberWarden", "Maps", "Sector01", "L_S01_LW_F1_RectangleStudy_V3.umap"),
              os.path.join(PROJECT, "Content", "CyberWarden", "Maps", "Sector01", "L_S01_LW_F1_RectangleStudy_V4.umap"),
              os.path.join(PROJECT, "Content", "CyberWarden", "Maps", "Sector01", "L_S01_LW_F1_RectangleStudy_V5.umap"),
              os.path.join(PROJECT, "Content", "CyberWarden", "Maps", "Sector01", "L_S01_LW_F1_RectangleStudy_V6.umap"),
              os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1.json"),
              os.path.join(PROJECT, "Content", "Python", "cw_layout.py"),
              os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy.json"),
              os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V2.json"),
              os.path.join(SRC, "Content", "Python", "cw_rectstudy.py"),
              os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V4.json"),
              os.path.join(SRC, "Content", "Python", "cw_rectstudy_v2.py"),
              os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V4.json"),
              os.path.join(SRC, "Content", "Python", "cw_rectstudy_v3.py"),
              os.path.join(SRC, "Content", "Python", "cw_rectstudy_v4.py"),
              os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V5.json"),
              os.path.join(SRC, "Content", "Python", "cw_rectstudy_v5.py"),
              os.path.join(SRC, "Docs", "Layout", "S01_LW_F1_RectangleStudy_V6.json"),
              os.path.join(SRC, "Content", "Python", "cw_rectstudy_v6.py")]
TAG = "S01F1RectStudyV7"
ROOT = "S01_LW_F1_RectangleStudy_V7"
CUBE_PATH = "/Engine/BasicShapes/Cube.Cube"
GRID_MAT_PATH = "/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial"
GAMEMODE_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"
MAT_DIR = "/Game/CyberWarden/Materials"

LOG, ERRORS, WARNINGS = [], [], []


def log(msg):
    LOG.append(msg)
    unreal.log("[RectStudyV7] " + msg)


def warn(msg):
    WARNINGS.append(msg)
    LOG.append("WARNING: " + msg)
    unreal.log_warning("[RectStudyV7] " + msg)


def err(msg):
    ERRORS.append(msg)
    LOG.append("ERROR: " + msg)
    unreal.log_error("[RectStudyV7] " + msg)


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
study = cw7.StudyV7(data)

actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

# ----------------------------------------------------------------------------
# Level
# ----------------------------------------------------------------------------
if unreal.EditorAssetLibrary.does_asset_exist(LEVEL):
    log("V7 level exists - loading and clearing previously generated V7 actors only")
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
# Materials: reuse M_GB_Lit / M_GB_Unlit parents; NEW MI_RS7_* instances only (V1's MI_RS_* are left alone)
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
    """None -> engine grid; 'lit:Area' / 'unlit:Area' -> MI_RS7_Lit_Area / MI_RS7_Unlit_Area."""
    if key is None:
        return GRID
    if key in _MATS:
        return _MATS[key]
    kind, area = key.split(":", 1)
    rgb = data["areas"][area]["color"]
    scale = 0.55 if kind == "lit" else 1.0
    name = "MI_RS7_%s_%s" % ("Lit" if kind == "lit" else "Unlit", area)
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


CAM_IGNORED = 0
CAM_FAILED = None
for b in study.boxes:
    dx, dy, dz = b["x1"] - b["x0"], b["y1"] - b["y0"], b["z1"] - b["z0"]
    actor = spawn_cube(b["id"], unreal.Vector((b["x0"] + b["x1"]) / 2.0, (b["y0"] + b["y1"]) / 2.0, (b["z0"] + b["z1"]) / 2.0),
                       unreal.Vector(dx / 100.0, dy / 100.0, dz / 100.0), b["folder"], ["Kind:" + b["kind"]] + b["tags"], b["collision"], b["mat"])
    if b["kind"] in ("mesh", "net") and CAM_FAILED is None:
        try:   # the sheet: camera collision ignores the walkway mesh and the safety net (the character and its camera are not modified)
            actor.static_mesh_component.set_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA, unreal.CollisionResponseType.ECR_IGNORE)
            CAM_IGNORED += 1
        except Exception as ex:
            CAM_FAILED = str(ex)
            warn("Could not set the camera-channel response to Ignore on the mesh: %s (camera may clip against the mesh)" % ex)
log("Spawned %d axis-aligned boxes; mesh/net boxes set to ignore the camera channel: %d" % (len(study.boxes), CAM_IGNORED))

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
pstart.set_actor_label("PlayerStart_Intake")
pstart.set_folder_path(ROOT + "/Gameplay")
_tag(pstart, [TAG, "Spawn:Intake"])
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


a_errors, a_warnings = cw7.run_analysis(study, rep)
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


CHECKS = [("intake floor at the player start", (5940, 1030, 100), (5940, 1030, -50), 2, 0.0),
          ("hall floor, west end", (1100, 1400, 100), (1100, 1400, -50), 2, 0.0),
          ("hall floor under the crossover", (3100, 1400, 300), (3100, 1400, -50), 2, 0.0),
          ("crossover deck", (3100, 1400, 450), (3100, 1400, 300), 2, 390.0),
          ("north walkway deck", (2200, 773, 450), (2200, 773, 300), 2, 390.0),
          ("south walkway deck", (2200, 2030, 450), (2200, 2030, 300), 2, 390.0),
          ("west walkway deck", (773, 1400, 450), (773, 1400, 300), 2, 390.0),
          ("library floor", (520, 1400, 450), (520, 1400, 300), 2, 390.0),
          ("rec corridor floor", (2200, 3230, 450), (2200, 3230, 300), 2, 390.0),
          ("sally port floor", (3100, 2600, 450), (3100, 2600, 300), 2, 390.0),
          ("guard lookout floor", (5700, 1200, 450), (5700, 1200, 300), 2, 390.0),
          ("guard office floor", (5000, 2300, 450), (5000, 2300, 300), 2, 390.0),
          ("north arm floor directly above the intake", (5800, 300, 450), (5800, 300, 300), 2, 390.0),
          ("staff spine floor", (4510, 4000, 450), (4510, 4000, 300), 2, 390.0),
          ("S1 NE stair step at x=4600 (23rd step)", (4600, 790, 450), (4600, 790, 100), 2, 345.0),
          ("S2 SW stair step at x=1000 (22nd step)", (1000, 1780, 450), (1000, 1780, 100), 2, 330.0),
          ("S3 staff stair, lower flight step at x=5800 (8th step)", (5800, 1720, 300), (5800, 1720, 50), 2, 120.0),
          ("S3 staff stair, upper flight step at x=5800 (6th upper step)", (5800, 1853, 450), (5800, 1853, 100), 2, 285.0),
          ("S4 staff stair, lower flight step at y=4700 (7th step)", (5935, 4700, 300), (5935, 4700, 50), 2, 105.0),
          ("secured door D06 panel (blocks at x~5392)", (5250, 1500, 90), (5450, 1500, 90), 0, 5392.0),
          ("sealed arrival door D03 panel (blocks at x~6092)", (5900, 600, 90), (6150, 600, 90), 0, 6092.0),
          ("D02 is OPEN: spawn -> hall axis -> the green 01 wall (x~815)", (5900, 1030, 150), (600, 1030, 150), 0, 815.0),
          ("kitchen hatch W04 is OPEN: seating -> kitchen -> work-corridor wall (y~3585)", (3000, 2650, 170), (3000, 3700, 170), 1, 3585.0),
          ("kitchen north wall is SOLID away from the hatch (y~2785)", (2000, 2650, 170), (2000, 3500, 170), 1, 2785.0),
          ("lookout window W07 is OPEN: hall -> lookout -> exterior wall (x~6085)", (5000, 1400, 560), (6200, 1400, 560), 0, 6085.0),
          ("guard post window W01 is OPEN: seating -> guard post -> exterior wall (x~6085)", (5000, 2300, 150), (6200, 2300, 150), 0, 6085.0),
          ("staff room window W02 is OPEN: staff room -> work corridor -> plant wall (x~875)", (5560, 3690, 150), (700, 3690, 150), 0, 875.0),
          ("service alley D15 is OPEN: hall -> alley -> west leg -> dry store wall (y~3765)", (950, 1950, 150), (950, 4000, 150), 1, 3765.0),
          ("north void mesh blocks (top rail at y~871)", (2000, 773, 503), (2000, 1000, 503), 1, 871.0)]
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
unreal.log("[RectStudyV7] DONE errors=%d warnings=%d" % (len(ERRORS), len(WARNINGS)))
