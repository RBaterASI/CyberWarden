"""Place the configured NPCs into the Floor 1 greybox level (M2.1B).

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/PlaceNpcs.py" -unattended -nop4 -nosplash -NullRHI

Reads Docs/Layout/S01_LW_F1_npcs.json. Removes previously placed NPCs (tag S01F1NPC) and re-spawns the enabled ones
at their spawn markers, sets their routine configuration and a Route array of references to the placed marker actors.
Geometry is untouched, so the baked Static navigation stays valid. Re-run after every builder run + bake (the builder
deletes the markers the Route arrays point to). Close the interactive editor first (level save).
"""
import json
import os

import unreal

PROJECT = unreal.Paths.project_dir()
LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
TAG = "S01F1NPC"
errors = []


def log(m):
    unreal.log("[PLACENPCS] " + m)


def err(m):
    errors.append(m)
    unreal.log_error("[PLACENPCS] " + m)


cfg = json.load(open(os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1_npcs.json"), encoding="utf-8"))
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_sub.load_level(LEVEL)

cls = unreal.EditorAssetLibrary.load_blueprint_class(cfg["npc_blueprint"])
if cls is None:
    err("NPC Blueprint missing: %s (run Tools/CreateNpcFoundation.py)" % cfg["npc_blueprint"])
    raise SystemExit

markers = {}
for a in actor_sub.get_all_level_actors():
    tags = [str(t) for t in a.tags]
    mid = next((t.split(":", 1)[1] for t in tags if t.startswith("MarkerId:")), None)
    if mid:
        markers[mid] = (a, "NavDest:Yes" in tags)

removed = 0
for a in actor_sub.get_all_level_actors():
    if unreal.Name(TAG) in a.tags:
        actor_sub.destroy_actor(a)
        removed += 1
log("removed %d previously placed NPC actor(s)" % removed)

placed = 0
for n in cfg["npcs"]:
    if not n.get("enabled", True):
        log("skip disabled NPC %s" % n["id"])
        continue
    route = []
    for mid in n["route"]:
        if mid not in markers:
            err("%s: route marker %s does not exist" % (n["id"], mid))
        elif not markers[mid][1]:
            err("%s: route marker %s is not a navigation destination (NavDest:No)" % (n["id"], mid))
        else:
            route.append(markers[mid][0])
    if n["spawn_marker"] not in markers:
        err("%s: spawn marker %s missing" % (n["id"], n["spawn_marker"]))
        continue
    sm = markers[n["spawn_marker"]][0].get_actor_location()
    loc = unreal.Vector(sm.x, sm.y, sm.z - 12.0 + 92.0)  # marker sits 12 cm above the floor; capsule half height 90 (+2)
    npc = actor_sub.spawn_actor_from_class(cls, loc, unreal.Rotator(0, 0, n.get("spawn_yaw", 0)))
    npc.set_actor_label("NPC_" + n["id"])
    npc.set_folder_path("S01_LW_F1/NPCs")
    npc.set_editor_property("tags", [unreal.Name(TAG), unreal.Name("NpcId:" + n["id"])])
    npc.set_editor_property("NpcId", n["id"])
    npc.set_editor_property("ArchetypeName", n["archetype"])
    npc.set_editor_property("StartDelaySeconds", float(n["start_delay_seconds"]))
    npc.set_editor_property("IdleMin", float(n["idle_min"]))
    npc.set_editor_property("IdleMax", float(n["idle_max"]))
    npc.set_editor_property("Route", route)
    cmc = npc.get_component_by_class(unreal.CharacterMovementComponent)
    cmc.set_editor_property("max_walk_speed", float(n["walk_speed"]))
    log("placed %s (%s) at (%.0f, %.0f, %.0f) in %s; route: %s" % (
        n["id"], n["archetype"], loc.x, loc.y, loc.z, n["cell"], " -> ".join(n["route"])))
    placed += 1

if errors:
    log("FAILED with %d error(s); level NOT saved" % len(errors))
else:
    saved = level_sub.save_current_level()
    log("placed %d NPC(s); level saved: %s" % (placed, saved))
