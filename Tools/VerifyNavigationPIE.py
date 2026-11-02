"""Start a headless Play In Editor session of the Floor 1 greybox and check that the Static navigation data works in PIE.

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/VerifyNavigationPIE.py" -unattended -nop4 -nosplash -NullRHI
Read-only: nothing is saved.
"""
import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
st = {"n": 0, "pie": False, "h": None, "post": 0}


def log(m):
    unreal.log("[NAVPIE] " + m)


def done(code):
    unreal.unregister_slate_post_tick_callback(st["h"])
    log("exit %d" % code)
    unreal.SystemLibrary.quit_editor()


def tick(dt):
    st["n"] += 1
    n = st["n"]
    try:
        if n == 200 and not st["pie"]:  # let the editor world settle first
            level_sub.editor_request_begin_play()
            st["pie"] = True
            log("PIE requested")
            return
        if n > 4000:
            log("FAILED: PIE never started")
            done(2)
            return
        if not st["pie"]:
            return
        gw = ues.get_game_world()
        if gw is None:
            return
        st["post"] += 1
        if st["post"] < 60:
            return
        pawn = unreal.GameplayStatics.get_player_pawn(gw, 0)
        log("PIE world=%s pawn=%s" % (gw.get_name(), pawn.get_class().get_name() if pawn else None))
        log("nav being built in PIE: %s" % unreal.NavigationSystemV1.is_navigation_being_built(gw))
        res = []
        for a, b in (((-400, 400, 0), (3800, 400, 0)), ((3800, 400, 0), (4050, -900, 500)), ((3800, 400, 0), (1500, -250, 330)), ((200, 1000, 0), (7150, 250, 0))):
            p = unreal.NavigationSystemV1.find_path_to_location_synchronously(gw, unreal.Vector(*a), unreal.Vector(*b))
            ok = p is not None and p.is_valid() and not p.is_partial()
            res.append(ok)
            log("PIE path %s -> %s : %s (%s cm)" % (a, b, "OK" if ok else "FAIL", "%.0f" % p.get_path_length() if ok else "-"))
        if pawn:
            loc = pawn.get_actor_location()
            log("player spawned at (%.0f, %.0f, %.0f)" % (loc.x, loc.y, loc.z))
        level_sub.editor_request_end_play()
        done(0 if all(res) and pawn else 3)
    except Exception as ex:
        log("EXCEPTION %s" % ex)
        done(4)


st["h"] = unreal.register_slate_post_tick_callback(tick)
