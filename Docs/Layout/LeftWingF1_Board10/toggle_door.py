"""Toggle a closed door slab (default D27, the office door) in the OPEN editor level (Output Log > Cmd > Python):

    py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Docs/Layout/LeftWingF1_Board10/toggle_door.py"

Edit DOOR below for another closed door. Run again to close it. The slab is the actor "<DOOR>_Door_Closed" (outliner folder S01_LW_F1_Gen/Doors_Toggle).
It is hidden + collision off when open. Save the level (Ctrl+S) to keep the state. (Do this before pressing Play; PIE copies the editor world.)
"""
import unreal

DOOR = "D27"

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
done = False
for a in sub.get_all_level_actors():
    if a.get_actor_label() == f"{DOOR}_Door_Closed":
        hidden = not a.is_temporarily_hidden_in_editor()          # toggle
        a.set_is_temporarily_hidden_in_editor(hidden)
        a.set_actor_hidden_in_game(hidden)
        a.set_actor_enable_collision(not hidden)
        unreal.log(f"[LW_F1] {DOOR} door slab is now {'OPEN (hidden, no collision)' if hidden else 'CLOSED (red slab, collision)'}")
        done = True
if not done:
    unreal.log_warning(f"[LW_F1] no actor named {DOOR}_Door_Closed in this level")
