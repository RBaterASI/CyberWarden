"""Read-only validation of the prototype cafeteria stool (M2.3 Stage C2). Saves nothing.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/ValidateStool.py -Log <abs log>

Checks the Blueprint /Game/CyberWarden/Props/BP_CafeteriaStool and the one placed actor in the greybox level: nine static-mesh components (seat plate 38 x 38 x 3 cm,
four legs, four stretcher bars), the seat top height, every component without collision and without influence on navigation, neutral greybox materials, the actor
independent of the M1 geometry generation (no S01F1Greybox tag, own folder and tags), exactly one stool in the level, its position against the measured seated pose, and
that the navigation mesh is unaffected (the stool footprint is still walkable, the seat marker still projects to the same reachable point).
"""
import math

import unreal

BP = "/Game/CyberWarden/Props/BP_CafeteriaStool"
LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
res, fail = [], []


def check(name, ok, detail=""):
    res.append(bool(ok))
    if not ok:
        fail.append(name)
    unreal.log("[STOOLVAL] %s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  (%s)" % detail))


bp = unreal.load_asset(BP)
check("the Blueprint exists", bp is not None)
sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
comps = {}
for h in sub.k2_gather_subobject_data_for_blueprint(bp):
    o = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h))
    if isinstance(o, unreal.StaticMeshComponent):
        comps[o.get_name().replace("_GEN_VARIABLE", "")] = o
check("nine static mesh components (1 seat, 4 legs, 4 stretcher bars): %s" % sorted(comps), len(comps) == 9 and "Seat" in comps and sum(1 for k in comps if k.startswith("Leg_")) == 4 and sum(1 for k in comps if k.startswith("Bar_")) == 4)

cube = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
seat = comps["Seat"]
ss, sl = seat.get_editor_property("relative_scale3d"), seat.get_editor_property("relative_location")
size = (ss.x * 100.0, ss.y * 100.0, ss.z * 100.0)
top = sl.z + size[2] / 2.0
check("seat plate %.1f x %.1f x %.1f cm (about 38 x 38)" % size, abs(size[0] - 38.0) < 0.5 and abs(size[1] - 38.0) < 0.5 and 2.0 <= size[2] <= 4.0)
check("seat top %.1f cm above the actor origin (about 44 cm asked; 41.5 cm from the measured pose: the lowest point of the seated body is 40.7 cm)" % top, 40.0 <= top <= 46.0)
legs = [c for k, c in comps.items() if k.startswith("Leg_")]
leg_bottoms = [c.get_editor_property("relative_location").z - c.get_editor_property("relative_scale3d").z * 50.0 for c in legs]
leg_tops = [c.get_editor_property("relative_location").z + c.get_editor_property("relative_scale3d").z * 50.0 for c in legs]
check("the four legs stand on the floor (bottom z %.2f) and meet the seat plate underside (top z %.2f vs %.2f)" % (max(leg_bottoms), min(leg_tops), sl.z - size[2] / 2.0),
      all(abs(b) < 0.01 for b in leg_bottoms) and all(abs(t - (sl.z - size[2] / 2.0)) < 0.01 for t in leg_tops))
check("all components use the engine cube, simple primitives only", all(c.get_editor_property("static_mesh") == cube for c in comps.values()))
mats = {c.get_material(0).get_name() for c in comps.values() if c.get_material(0)}
check("neutral greybox materials only: %s" % sorted(mats), mats <= {"MI_GB_Stool_Seat", "MI_GB_Stool_Frame"} and len(mats) == 2)
check("collision disabled on every component (NO_COLLISION)", all(c.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION for c in comps.values()),
      str({k: str(c.get_collision_enabled()) for k, c in comps.items() if c.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION}))
check("no component can affect navigation", all(not c.get_editor_property("can_ever_affect_navigation") for c in comps.values()),
      str([k for k, c in comps.items() if c.get_editor_property("can_ever_affect_navigation")]))
check("no overlap events generated", all(not c.get_editor_property("generate_overlap_events") for c in comps.values()))

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les.load_level(LEVEL)
actors = [a for a in eas.get_all_level_actors() if "Stool" in a.get_actor_label() or a.get_class().get_name() == "BP_CafeteriaStool_C"]
check("exactly one stool in the level: %s" % [a.get_actor_label() for a in actors], len(actors) == 1)
a = actors[0]
tags = sorted(str(t) for t in a.tags)
loc, rot = a.get_actor_location(), a.get_actor_rotation()
check("independent of the M1 generation: no S01F1Greybox tag (tags %s), folder %s" % (tags, a.get_folder_path()), "S01F1Greybox" not in tags and "S01F1Prop" in tags and "SeatMarker:Seat_Table_1_5" in tags and str(a.get_folder_path()) == "S01_LW_F1/Props")
check("actor collision disabled", not a.get_actor_enable_collision())
mk = [x for x in eas.get_all_level_actors() if "MarkerId:Seat_Table_1_5" in [str(t) for t in x.tags]]
check("the seat marker is still at (6150, -5, 12) and unchanged", len(mk) == 1 and abs(mk[0].get_actor_location().x - 6150.0) < 0.01 and abs(mk[0].get_actor_location().y + 5.0) < 0.01 and abs(mk[0].get_actor_location().z - 12.0) < 0.01)
unreal.log("[STOOLVAL] stool actor at (%.2f, %.2f, %.2f) yaw %.1f" % (loc.x, loc.y, loc.z, rot.yaw))
# measured seated pose (Tools/SeatPoseMeasure.py): capsule (6150, 0), pelvis (6148.9..6150.8, 43.4..43.6), lowest body point z 40.7
rear, front = loc.y + 19.0, loc.y - 19.0
check("the seat plate (y %.1f..%.1f) lies under the measured pelvis (y 43.4) with about 3-5 cm of plate behind the buttocks (rear edge %.1f)" % (front, rear, rear), front < 30.0 and 57.0 <= rear <= 65.0)
check("centred on the standing position in x (%.1f vs 6150)" % loc.x, abs(loc.x - 6150.0) < 1.0)
check("on the floor: z %.2f" % loc.z, abs(loc.z) < 0.01)

# navigation: nothing changes. The projection of the marker is still the reachable point (6150, 0), and the stool footprint is still walkable (the stool is not an obstacle).
world = unreal.EditorLevelLibrary.get_editor_world()
nav = unreal.NavigationSystemV1
pg = nav.project_point_to_navigation(world, unreal.Vector(6150.0, -5.0, 12.0), None, None, unreal.Vector(50, 50, 250))
check("the seat marker still projects to the reachable point (6150, 0): (%.3f, %.3f, %.3f)" % (pg.x, pg.y, pg.z), abs(pg.x - 6150.0) < 0.01 and abs(pg.y) < 0.01)
for label, (x, y) in (("centre", (loc.x, loc.y)), ("front-left corner", (loc.x - 18.0, loc.y - 18.0)), ("rear-right corner", (loc.x + 18.0, loc.y + 18.0))):
    p = nav.project_point_to_navigation(world, unreal.Vector(x, y, 100.0), None, None, unreal.Vector(2, 2, 250))  # probe from z 100: an unreachable point would come back at z 100
    check("the stool footprint is still walkable navmesh at its %s (%.1f, %.1f) -> (%.2f, %.2f, z %.1f)" % (label, x, y, p.x, p.y, p.z), math.hypot(p.x - x, p.y - y) < 2.5 and abs(p.z - 10.0) < 5.0)
unreal.log("[STOOLVAL] RESULT %s (%d/%d checks)" % ("PASS" if not fail else "FAIL", sum(res), len(res)))
unreal.SystemLibrary.quit_editor()
