"""Editor-only dev tool: shows the player's current area on screen while playing the Floor 1 greybox in PIE.

Runs only inside the Unreal Editor (Python Script Plugin). It does not touch any Blueprint, the character or
the camera, and it is not part of packaged builds. Delete this file to remove it.
"""
import json
import os
import sys

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


def _tick_study(world, pawn):
    """Location text for the Floor 1 RECTANGLE STUDY map (own layout file; M1 data and NPC overlay are not used)."""
    wname = world.get_name()
    ver = 7 if "RectangleStudy_V7" in wname else (6 if "RectangleStudy_V6" in wname else (5 if "RectangleStudy_V5" in wname else (4 if "RectangleStudy_V4" in wname else (3 if "RectangleStudy_V3" in wname else (2 if "RectangleStudy_V2" in wname else 1)))))
    v2 = ver >= 2   # V2-V7 share the V2 generator (same JSON schema; V6 only adds the floor-guide lines, which the HUD does not need)
    if _state.get("study_rooms") is None or _state.get("study_ver") != ver:
        # Look for the sources in the open project first, then next to this script's project.
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # A worktree (e.g. CyberWarden_C2Build) may not hold the study sources: fall back to the sibling "CyberWarden" project.
        sibling = os.path.join(os.path.dirname(os.path.normpath(unreal.Paths.project_dir())), "CyberWarden")
        for cand in (root, sibling):
            src_py = os.path.join(cand, "Content", "Python")
            if os.path.exists(os.path.join(src_py, "cw_rectstudy_v2.py")) and src_py not in sys.path:
                sys.path.append(src_py)
        name = {1: "S01_LW_F1_RectangleStudy.json", 2: "S01_LW_F1_RectangleStudy_V2.json", 3: "S01_LW_F1_RectangleStudy_V3.json", 4: "S01_LW_F1_RectangleStudy_V4.json", 5: "S01_LW_F1_RectangleStudy_V5.json", 6: "S01_LW_F1_RectangleStudy_V6.json", 7: "S01_LW_F1_RectangleStudy_V7.json"}[ver]
        path = os.path.join(unreal.Paths.project_dir(), "Docs", "Layout", name)
        if not os.path.exists(path):
            path = os.path.join(root, "Docs", "Layout", name)
        if not os.path.exists(path):
            path = os.path.join(sibling, "Docs", "Layout", name)
        if v2:
            import cw_rectstudy_v2 as study_mod
            data = study_mod.load(path)
            _state["study_rooms"] = study_mod.StudyV2(data).rooms
        else:
            import cw_rectstudy as study_mod
            data = study_mod.load(path)
            _state["study_rooms"] = study_mod.Study(data).rooms
        _state["study_areas"] = data.get("areas", {})
        _state["study_ver"] = ver
    loc = pawn.get_actor_location()
    feet = loc.z - 90.0
    room = cw_layout.locate(_state["study_rooms"], loc.x, loc.y, feet)
    tier = "GROUND TIER" if feet < 195 else "UPPER TIER"
    if room is None:
        text = "SECTOR 01 | LEFT WING | FLOOR 1 (RECTANGLE STUDY) | %s | (outside mapped rooms)" % tier
    else:
        area = _state["study_areas"].get(room.get("area", ""), {}).get("label", room.get("area", "?"))
        text = "SECTOR 01 | LEFT WING | FLOOR 1 (RECTANGLE STUDY) | %s | %s | %s" % (tier, area.upper(), room.get("name", room["id"]))
    unreal.SystemLibrary.print_string(world, text, True, False, unreal.LinearColor(1.0, 0.92, 0.35, 1.0), 0.4, "CW_LOCATION")


def _gen_spec():
    """Board-10 spec (Docs/Layout/LeftWingF1_Board10): open project first, then this script's project, then the sibling CyberWarden project."""
    if _state.get("gen") is not None:
        return _state["gen"]
    rel = os.path.join("Docs", "Layout", "LeftWingF1_Board10", "LeftWing_F1_spec.json")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sibling = os.path.join(os.path.dirname(os.path.normpath(unreal.Paths.project_dir())), "CyberWarden")
    for base in (unreal.Paths.project_dir(), root, sibling):
        path = os.path.join(base, rel)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                spec = json.load(fh)
            up = spec["levels"]["upper"]["floor_z"]
            rooms = []
            for r in spec["rooms"]:
                upper = r["tier"] == "upper"
                ch = 3.6 if upper else (r.get("ceiling") or spec["levels"]["roof_z"])
                rooms.append({"id": r["id"], "name": r["name"], "x0": r["x"] * 100.0, "y0": r["y"] * 100.0, "x1": (r["x"] + r["w"]) * 100.0, "y1": (r["y"] + r["h"]) * 100.0,
                              "z": (up if upper else 0.0) * 100.0, "ceil": ch * 100.0 + (30.0 if upper else 0.0)})
            _state["gen"] = {"rooms": rooms, "camera": spec.get("review_camera", {})}
            return _state["gen"]
    _state["gen"] = {"rooms": [], "camera": {}}
    unreal.log_warning("[CW location indicator] board-10 spec not found")
    return _state["gen"]


def _tick_gen(world, pawn):
    """Board-10 greybox (L_S01_LW_F1_Gen): room id + name from the spec, and the review camera (spring arm socket offset) applied to the PIE pawn only."""
    gen = _gen_spec()
    if _state.get("gen_pawn") != id(pawn):
        _state["gen_pawn"] = id(pawn)
        off = gen["camera"].get("spring_arm_socket_offset")
        if off:
            try:
                arm = pawn.get_component_by_class(unreal.SpringArmComponent)
                arm.set_editor_property("socket_offset", unreal.Vector(off[0], off[1], off[2]))
                unreal.log("[CW location indicator] review camera: spring arm socket offset %s (PIE pawn only, the Blueprint is unchanged)" % (off,))
            except Exception as ex:
                unreal.log_warning("[CW location indicator] review camera offset failed: %s" % ex)
    loc = pawn.get_actor_location()
    feet = loc.z - 90.0
    room = cw_layout.locate(gen["rooms"], loc.x, loc.y, feet)
    tier = "GROUND TIER" if feet < 195 else "UPPER TIER"
    if room is None:
        text = "SECTOR 01 | LEFT WING | FLOOR 1 | %s | (outside mapped rooms)" % tier
    else:
        text = "SECTOR 01 | LEFT WING | FLOOR 1 | %s | %s %s" % (tier, room["id"], room["name"].upper())
    unreal.SystemLibrary.print_string(world, text, True, False, unreal.LinearColor(1.0, 0.92, 0.35, 1.0), 0.4, "CW_LOCATION")


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
        if "L_S01_LW_F1_Gen" in world.get_name():
            _tick_gen(world, pawn)
            return
        if "RectangleStudy" in world.get_name():
            _tick_study(world, pawn)
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
        try:
            import cw_npc_debug
            cw_npc_debug.update(world, delta)
        except Exception as nex:
            _state["npc_errors"] = _state.get("npc_errors", 0) + 1
            if _state["npc_errors"] <= 3:
                unreal.log_warning("[CW NPC debug] %s" % nex)
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
