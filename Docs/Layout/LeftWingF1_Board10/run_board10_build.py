"""Editor stages 1-3 for the patched board-10 greybox, in ONE command (Output Log > Cmd > Python):

    py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Docs/Layout/LeftWingF1_Board10/run_board10_build.py"

 - creates (or reloads) the FRESH level /Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Gen (never touches L_S01_LW_F1_Greybox or the RectangleStudy maps)
 - sets the world's game mode to the existing BP_ThirdPersonGameMode (existing controller and camera; nothing modified)
 - runs ue_build_from_spec.py (it clears and rebuilds only its own outliner folder S01_LW_F1_Gen)
 - (the build script itself now builds the furniture and the lighting under S01_LW_F1_Gen/Furniture and /Lighting)
 - saves the level and starts a NavMesh rebuild

Then WAIT for the navmesh to finish (Output Log shows "Navmesh build finished" / the green area appears with P held), and run:

    py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Docs/Layout/LeftWingF1_Board10/ue_validate_layout.py"

and read <Project>/Saved/LW_F1_validation.md.
"""
import os
import runpy

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Gen"
PROTECTED = ("L_S01_LW_F1_Greybox", "L_S01_LW_F1_RectangleStudy", "L_S01_LW_F1_RectangleStudy_V2", "L_S01_LW_F1_RectangleStudy_V3",
             "L_S01_LW_F1_RectangleStudy_V4", "L_S01_LW_F1_RectangleStudy_V5", "L_S01_LW_F1_RectangleStudy_V6", "L_S01_LW_F1_RectangleStudy_V7")
GAMEMODE_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"

if LEVEL.rsplit("/", 1)[-1] in PROTECTED:
    raise SystemExit("refusing to run against a protected map")
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if unreal.EditorAssetLibrary.does_asset_exist(LEVEL):
    unreal.log("[LW_F1] level exists - loading it (the build script clears only its own folder)")
    level_sub.load_level(LEVEL)
else:
    if not level_sub.new_level(LEVEL):
        raise SystemExit("could not create " + LEVEL)
    unreal.log("[LW_F1] created fresh level " + LEVEL)

try:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    gm = unreal.EditorAssetLibrary.load_blueprint_class(GAMEMODE_PATH)
    world.get_world_settings().set_editor_property("default_game_mode", gm)
    unreal.log("[LW_F1] game mode override: " + gm.get_name())
except Exception as ex:
    unreal.log_warning("[LW_F1] game mode override failed: %s (set it in World Settings by hand)" % ex)

runpy.run_path(os.path.join(HERE, "ue_build_from_spec.py"), run_name="__main__")

level_sub.save_current_level()
try:
    unreal.SystemLibrary.execute_console_command(world, "RebuildNavigation")
    unreal.log("[LW_F1] RebuildNavigation sent (the engine may refuse it while the build is locked: if the log says so, use Build > Build Paths), then run ue_validate_layout.py once the navmesh exists")
except Exception as ex:
    unreal.log_warning("[LW_F1] could not start the NavMesh rebuild (%s): use Build > Build Paths" % ex)
