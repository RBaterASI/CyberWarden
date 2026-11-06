"""Retune the board-10 lighting in the OPEN level without rebuilding (Output Log > Cmd > Python):

    py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Docs/Layout/LeftWingF1_Board10/tune_board10_lighting.py"

EXPOSURE_MODE = "auto"   : eye adaptation (the scene always lands at a readable brightness; ROOM_CD / HALL_CD then only set the contrast)
EXPOSURE_MODE = "manual" : fixed exposure. EXPOSURE_EV is an exposure COMPENSATION: HIGHER = BRIGHTER (+1 = twice as bright).
                           Scene too bright -> lower EXPOSURE_EV by 1-2 and run again; too dark -> raise it.
Only actors under the outliner folder S01_LW_F1_Gen/Lighting are touched. Save the level afterwards (Ctrl+S) to keep it.
Keep the same values in ue_build_from_spec.py (EXPOSURE_MODE, EXPOSURE_EV, ROOM_CD, HALL_CD) so a rebuild matches.
"""
import unreal

EXPOSURE_MODE = "auto"
EXPOSURE_EV = 4.0     # manual mode only
ROOM_CD = 3000.0      # point light intensity in rooms and corridors (unitless)
HALL_CD = 9000.0      # ... in the double-height hall (lights named Light_L08_*)

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
n = 0
for a in sub.get_all_level_actors():
    try:
        if not str(a.get_folder_path()).endswith("/Lighting"):
            continue
        label = a.get_actor_label()
        if label.startswith("Light_"):
            a.light_component.set_editor_property("intensity", HALL_CD if label.startswith("Light_L08_") else ROOM_CD)
            n += 1
        elif label == "PostProcess_Unbound":
            st = a.get_editor_property("settings")
            st.set_editor_property("override_auto_exposure_method", True)
            st.set_editor_property("override_auto_exposure_bias", True)
            if EXPOSURE_MODE == "manual":
                st.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
                st.set_editor_property("auto_exposure_bias", EXPOSURE_EV)
            else:
                st.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
                st.set_editor_property("auto_exposure_bias", 0.0)
            a.set_editor_property("settings", st)
    except Exception as ex:
        unreal.log_warning("[LW_F1] tune: %s" % ex)
unreal.log("[LW_F1] lighting retuned: %d point lights, room %.0f / hall %.0f, exposure %s%s" % (
    n, ROOM_CD, HALL_CD, EXPOSURE_MODE, (" EV %.1f" % EXPOSURE_EV) if EXPOSURE_MODE == "manual" else ""))
