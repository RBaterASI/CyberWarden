"""Editor-only dev tool: shows the player's current area on screen while playing the Floor 1 greybox in PIE.

Runs only inside the Unreal Editor (Python Script Plugin). It does not touch any Blueprint, the character or
the camera, and it is not part of packaged builds. Delete this file to remove it.
"""
import json
import os

import unreal

import cw_layout

LEVEL_KEY = "L_S01_LW_F1"
_state = {"t": 0.0, "rooms": None, "errors": 0, "handle": None}


def _load_rooms():
    path = os.path.join(unreal.Paths.project_dir(), "Docs", "Layout", "S01_LW_F1.json")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    _state["areas"] = data.get("areas", {})
    return cw_layout.expand(data)["rooms"]


def _tick(delta):
    try:
        _state["t"] += delta
        if _state["t"] < 0.15:
            return
        _state["t"] = 0.0
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        if world is None or LEVEL_KEY not in world.get_name():
            return
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        if pawn is None:
            return
        if _state["rooms"] is None:
            _state["rooms"] = _load_rooms()
        loc = pawn.get_actor_location()
        feet = loc.z - 90.0
        room = cw_layout.locate(_state["rooms"], loc.x, loc.y, feet)
        if room is None:
            text = "SECTOR 01 | LEFT WING | FLOOR 1 | (outside mapped rooms)"
        else:
            area = _state["areas"].get(room.get("area", ""), {}).get("label", room.get("area", "?"))
            level = "FLOOR 1" if feet < 480 else "FLOOR 1 (Floor 2 level landing - secured)"
            text = "SECTOR 01 | LEFT WING | %s | %s | %s | Zone %s" % (level, area.upper(), room.get("name", room["id"]), room.get("zone", "?"))
        unreal.SystemLibrary.print_string(world, text, True, False, unreal.LinearColor(1.0, 0.92, 0.35, 1.0), 0.4, "CW_LOCATION")
    except Exception as ex:  # never let a dev tool spam or break the editor
        _state["errors"] += 1
        if _state["errors"] <= 3:
            unreal.log_warning("[CW location indicator] %s" % ex)
        if _state["errors"] >= 5 and _state["handle"] is not None:
            unreal.unregister_slate_post_tick_callback(_state["handle"])
            _state["handle"] = None
            unreal.log_warning("[CW location indicator] disabled after repeated errors")


if _state["handle"] is None:
    _state["handle"] = unreal.register_slate_post_tick_callback(_tick)
    unreal.log("[CW location indicator] registered (active only in the Floor 1 greybox PIE)")
