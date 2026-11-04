"""M2.3 Stage C2: creates the reusable prototype cafeteria stool and places ONE of them at QUI01's seat. Idempotent.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/CreateSeatStool.py -Log <abs log>
  (env STOOL_Y="37.5" STOOL_X="6150" overrides the placement for tuning)

Creates (new assets only):
  /Game/CyberWarden/Props/BP_CafeteriaStool   Actor Blueprint: 38 x 38 cm seat plate (3 cm thick), four 3.5 cm square legs, four 2 cm stretcher bars (seat top 41.5 cm
                                              above the actor origin). Static-mesh primitives (the engine cube), no collision, does NOT affect navigation.
  /Game/CyberWarden/Props/MI_GB_Stool_Seat    neutral grey instances of the existing greybox material M_GB_Lit
  /Game/CyberWarden/Props/MI_GB_Stool_Frame
Places (new actor, one external-actor file): "Stool_Seat_Table_1_5" in the level, folder S01_LW_F1/Props, tags S01F1Prop / Kind:SeatStool / SeatMarker:Seat_Table_1_5.
It is NOT part of the M1 geometry generation: it does not carry the S01F1Greybox tag, so Tools/BuildFloor1Greybox.py neither removes nor regenerates it, and
nothing of M1 (geometry, navmesh, markers, tables) is touched. Only the packages created here are saved (never the map itself).

Position: the seated pose measured by Tools/SeatPoseMeasure.py - capsule (6150, 0) facing -Y, pelvis joint 43.45 cm behind the capsule (y 43.45), thighs horizontal
towards the knees at y 0 - so the seat plate is centred under the pelvis and thighs: y = pelvis y - STOOL_FORWARD (the seat centre is a little in front of the pelvis
joint because the buttocks extend behind it and the thighs in front of it).
"""
import os

import unreal

DIR = "/Game/CyberWarden/Props"
BP_NAME = "BP_CafeteriaStool"
MAT_PARENT = "/Game/CyberWarden/Materials/M_GB_Lit"
CUBE = "/Engine/BasicShapes/Cube.Cube"
LABEL = "Stool_Seat_Table_1_5"
MARKER = "Seat_Table_1_5"
STOOL_X = float(os.environ.get("STOOL_X", "6150.0"))
# Tuned from the rendered check (Saved/StoolCheck, zoomed side and top views of the real seated pose): with the seat plate centred at y 37.5 and 44 cm high the buttocks were
# flush with the rear edge and about 3 cm INTO the plate (the lowest point of the body is z 40.7). So the seat is 4 cm further back and its top 41.5 cm above the floor.
STOOL_Y = float(os.environ.get("STOOL_Y", "41.5"))
STOOL_TOP = float(os.environ.get("STOOL_TOP", "41.5"))  # seat top above the actor origin (the floor); an existing Blueprint is updated in place
YAW = -90.0  # the seat faces -Y (the table side); the stool is square, the yaw only documents it

tools = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
bel = unreal.BlueprintEditorLibrary
mel = unreal.MaterialEditingLibrary
sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
saved = []


def log(m):
    unreal.log("[STOOL] " + m)


def srgb_to_linear(c):
    return unreal.LinearColor(*[((x / 255.0) / 12.92) if (x / 255.0) <= 0.04045 else (((x / 255.0) + 0.055) / 1.055) ** 2.4 for x in c[:3]] + [1.0])


def ensure_mi(name, rgb):
    path = "%s/%s" % (DIR, name)
    if eal.does_asset_exist(path):
        mic = unreal.load_asset(path)
        log("EXISTS: %s" % path)
    else:
        mic = tools.create_asset(name, DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mic.set_editor_property("parent", unreal.load_asset(MAT_PARENT))
        log("CREATED: %s" % path)
    mel.set_material_instance_vector_parameter_value(mic, "Color", srgb_to_linear(rgb))
    eal.save_loaded_asset(mic)
    saved.append(path)
    return mic


cube = unreal.load_asset(CUBE)
if cube is None or unreal.load_asset(MAT_PARENT) is None:
    unreal.log_error("[STOOL] engine cube or M_GB_Lit missing")
    unreal.SystemLibrary.quit_editor()
    raise SystemExit
if not eal.does_directory_exist(DIR):
    eal.make_directory(DIR)
mi_seat = ensure_mi("MI_GB_Stool_Seat", (150, 152, 156))   # light steel grey
mi_frame = ensure_mi("MI_GB_Stool_Frame", (88, 90, 95))    # dark steel grey

# ---- the Blueprint ---------------------------------------------------------------------------------------------------------------------------------
bp_path = "%s/%s" % (DIR, BP_NAME)
if eal.does_asset_exist(bp_path):
    bp = unreal.load_asset(bp_path)
    SEAT_T = 3.0
    n_upd = 0
    for h_ in sub.k2_gather_subobject_data_for_blueprint(bp):  # re-apply the seat height to the seat plate and the four legs
        o_ = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h_))
        nm_ = o_.get_name() if o_ else ""
        if nm_.startswith("Seat"):
            l_ = o_.get_editor_property("relative_location")
            o_.set_editor_property("relative_location", unreal.Vector(l_.x, l_.y, STOOL_TOP - SEAT_T / 2.0))
            n_upd += 1
        elif nm_.startswith("Leg_"):
            l_, s_ = o_.get_editor_property("relative_location"), o_.get_editor_property("relative_scale3d")
            o_.set_editor_property("relative_location", unreal.Vector(l_.x, l_.y, (STOOL_TOP - SEAT_T) / 2.0))
            o_.set_editor_property("relative_scale3d", unreal.Vector(s_.x, s_.y, (STOOL_TOP - SEAT_T) / 100.0))
            n_upd += 1
    bel.compile_blueprint(bp)
    eal.save_loaded_asset(bp)
    saved.append(bp_path)
    log("EXISTS: %s updated in place: seat top %.1f cm (%d components: the seat plate and four legs)" % (bp_path, STOOL_TOP, n_upd))
else:
    fac = unreal.BlueprintFactory()
    fac.set_editor_property("parent_class", unreal.Actor)
    bp = tools.create_asset(BP_NAME, DIR, unreal.Blueprint, fac)
    log("CREATED: %s" % bp_path)
    handles = sub.k2_gather_subobject_data_for_blueprint(bp)
    root = handles[0]
    SEAT_T = 3.0
    LEG = 3.5
    INSET = 19.0 - 2.5 - LEG / 2.0  # leg centres 2.5 cm in from the seat edge: +-14.75
    BAR = 2.0
    BAR_Z = 18.0
    parts = [("Seat", (0.0, 0.0, STOOL_TOP - SEAT_T / 2.0), (38.0, 38.0, SEAT_T), mi_seat)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(("Leg_%s%s" % ("R" if sx > 0 else "L", "F" if sy > 0 else "B"), (sx * INSET, sy * INSET, (STOOL_TOP - SEAT_T) / 2.0), (LEG, LEG, STOOL_TOP - SEAT_T), mi_frame))
    span = 2.0 * INSET - LEG  # clear distance between two legs
    for sx in (-1, 1):
        parts.append(("Bar_Side_%s" % ("R" if sx > 0 else "L"), (sx * INSET, 0.0, BAR_Z), (BAR, span, BAR), mi_frame))
    for sy in (-1, 1):
        parts.append(("Bar_End_%s" % ("F" if sy > 0 else "B"), (0.0, sy * INSET, BAR_Z), (span, BAR, BAR), mi_frame))
    for name, loc, size, mat in parts:
        params = unreal.AddNewSubobjectParams(parent_handle=root, new_class=unreal.StaticMeshComponent, blueprint_context=bp)
        h, fail = sub.add_new_subobject(params)
        sub.rename_subobject(h, name)
        comp = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h))
        comp.set_editor_property("static_mesh", cube)
        comp.set_editor_property("relative_location", unreal.Vector(*loc))
        comp.set_editor_property("relative_scale3d", unreal.Vector(size[0] / 100.0, size[1] / 100.0, size[2] / 100.0))
        comp.set_material(0, mat)
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        comp.set_collision_profile_name("NoCollision")
        try:
            comp.set_editor_property("can_ever_affect_navigation", False)
        except Exception:
            comp.set_can_ever_affect_navigation(False)
        comp.set_editor_property("generate_overlap_events", False)
    bel.compile_blueprint(bp)
    eal.save_loaded_asset(bp)
    saved.append(bp_path)
    log("  %d components (1 seat, 4 legs, 4 stretcher bars); collision NoCollision, CanEverAffectNavigation false" % len(parts))

# ---- the level -----------------------------------------------------------------------------------------------------------------------------------------
les.load_level("/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox")
world = unreal.EditorLevelLibrary.get_editor_world()
floor_z = 0.0
try:
    hit = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(STOOL_X, STOOL_Y, 150.0), unreal.Vector(STOOL_X, STOOL_Y, -150.0), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [],
                                                 unreal.DrawDebugTrace.NONE, True)
    if isinstance(hit, tuple):
        ok, res = hit[0], hit[-1]
    else:
        ok, res = bool(hit), hit
    if ok:
        impact = res.to_tuple()[5] if hasattr(res, "to_tuple") else None  # (blocking, initial overlap, time, distance, location, impact point, ...)
        log("floor trace at the stool: %s" % (impact,))
        if impact is not None:
            floor_z = float(impact.z)
    else:
        log("floor trace found nothing: using the layout floor level z = 0")
except Exception as ex:
    log("floor trace unavailable (%s): using the layout floor level z = 0" % ex)

existing = [a for a in eas.get_all_level_actors() if a.get_actor_label() == LABEL]
loc = unreal.Vector(STOOL_X, STOOL_Y, floor_z)
rot = unreal.Rotator(0.0, 0.0, YAW)
if existing:
    actor = existing[0]
    actor.set_actor_location_and_rotation(loc, rot, False, False)
    log("UPDATED actor %s at (%.2f, %.2f, %.2f) yaw %.1f" % (LABEL, loc.x, loc.y, loc.z, YAW))
else:
    actor = eas.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(bp_path), loc, rot)
    actor.set_actor_label(LABEL)
    log("PLACED actor %s at (%.2f, %.2f, %.2f) yaw %.1f" % (LABEL, loc.x, loc.y, loc.z, YAW))
actor.set_folder_path("S01_LW_F1/Props")
actor.set_editor_property("tags", [unreal.Name("S01F1Prop"), unreal.Name("Kind:SeatStool"), unreal.Name("SeatMarker:" + MARKER)])
actor.set_actor_enable_collision(False)

dirty_maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
dirty_content = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
log("dirty map packages before saving: %s" % dirty_maps)
log("dirty content packages before saving: %s" % dirty_content)
ok = unreal.EditorLoadingAndSavingUtils.save_packages([actor.get_package()], False)  # only the stool actor's own (external) package; never the map
log("saved the stool actor package: %s (%s)" % (ok, actor.get_package().get_name()))
log("seat plate top at z = %.1f (floor %.1f + %.1f), seat footprint x %.1f..%.1f, y %.1f..%.1f" % (floor_z + STOOL_TOP, floor_z, STOOL_TOP, STOOL_X - 19, STOOL_X + 19, STOOL_Y - 19, STOOL_Y + 19))
unreal.SystemLibrary.quit_editor()
