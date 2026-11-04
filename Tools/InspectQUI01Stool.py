"""Helper for the HUMAN visual check of QUI01 on the prototype stool. Run it while Play In Editor is running; it changes nothing on disk.

  Output Log (Window > Developer Tools > Output Log) > Cmd box at the bottom:
      py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden_C2Build/Tools/InspectQUI01Stool.py"

First run: jumps the schedule clock to 07:00 (breakfast) so QUI01 walks to Seat_Table_1_5, and moves the PLAYER pawn (only the PIE copy) to a viewing spot east of the
stool, looking at it. QUI01 needs about 45 s: it waits out its departure stagger, walks from the cell, takes the final approach (about 0.4 s), turns toward the table
(about 0.6 s), sits down (about 2 s) and stays seated.
Second run (while QUI01 is seated): jumps the clock to 10:00 (work), which makes QUI01 stand up and walk away.
F8 ejects the camera so you can fly around the interaction (WASD + mouse); Shift+F1 frees the mouse. Nothing in the project is modified.
"""
import math

import unreal

ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
gw = ues.get_game_world()
if gw is None:
    unreal.log_warning("[INSPECT] Play In Editor is not running: press Play first, then run this command again.")
else:
    mgr = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")[0]
    npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
    ac = npcs["QUI01"].get_component_by_class(unreal.PrisonActivityComponent)
    seated = ac.get_editor_property("state").name == "PERFORMING" and str(ac.get_editor_property("active_marker_id")) == "Seat_Table_1_5"
    mgr.set_editor_property("time_scale", 30.0)
    mgr.set_editor_property("paused", False)
    if seated:
        mgr.set_time_of_day_hours(10.0)  # work period: the schedule changes, QUI01 stands up and leaves
        unreal.log("[INSPECT] QUI01 is seated: clock set to %s (work). It will stand up in a few seconds and walk away." % mgr.get_clock_string())
    else:
        mgr.set_time_of_day_hours(7.0)  # breakfast: QUI01 goes to Seat_Table_1_5
        unreal.log("[INSPECT] clock set to %s (breakfast): QUI01 will walk to Seat_Table_1_5 and sit on the stool in about 45 seconds. Run this command again once it sits to watch it stand up." % mgr.get_clock_string())
        pawn = unreal.GameplayStatics.get_player_pawn(gw, 0)
        pc = unreal.GameplayStatics.get_player_controller(gw, 0)
        if pawn is not None:
            view = unreal.Vector(6420.0, 150.0, 100.0)
            target = (6150.0, 41.5, 70.0)
            yaw = math.degrees(math.atan2(target[1] - view.y, target[0] - view.x))
            pitch = math.degrees(math.atan2(target[2] - view.z, math.hypot(target[0] - view.x, target[1] - view.y)))
            pawn.set_actor_location(view, False, False)
            if pc is not None:
                pc.set_control_rotation(unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))
            unreal.log("[INSPECT] player moved to (%.0f, %.0f) looking at the stool at (6150, 41.5); press F8 to eject and fly around" % (view.x, view.y))
        else:
            unreal.log_warning("[INSPECT] no player pawn found: eject with F8 and fly to (6150, 40, 80)")
