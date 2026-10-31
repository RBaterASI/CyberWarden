"""Build Static Recast navigation for the Floor 1 greybox and save it into the level.

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/BakeNavigation.py" -unattended -nop4 -nosplash -NullRHI

Navigation generation is asynchronous, so the script keeps the editor alive and polls on slate ticks.
A freshly loaded editor world holds an "async load" navigation lock for a while, so the rebuild is re-issued
until a build actually starts. Re-run after every builder run (the builder replaces the geometry, which
invalidates the baked data). Close the interactive editor first: it locks the level file and the save fails.
"""
import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
MAX_TICKS = 20000
unreal.EditorPythonScripting.set_keep_python_script_alive(True)

level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
state = {"n": 0, "quiet": 0, "started": False, "handle": None}


def log(msg):
    unreal.log("[NAVBAKE] " + msg)


def finish(code):
    unreal.unregister_slate_post_tick_callback(state["handle"])
    log("exit code %d" % code)
    unreal.SystemLibrary.quit_editor()


def tick(dt):
    state["n"] += 1
    n = state["n"]
    try:
        building = unreal.NavigationSystemV1.is_navigation_being_built(world)
        locked = unreal.NavigationSystemV1.is_navigation_being_built_or_locked(world) and not building
        if n % 60 == 0:
            log("tick %d building=%s locked=%s started=%s" % (n, building, locked, state["started"]))
        if not state["started"]:
            if building:
                state["started"] = True
                log("build started at tick %d" % n)
            elif n >= 5 and n % 20 == 5:
                unreal.SystemLibrary.execute_console_command(world, "RebuildNavigation")
            if n > MAX_TICKS:
                log("FAILED: navigation build never started")
                finish(5)
            return
        if building:
            state["quiet"] = 0
            return
        state["quiet"] += 1
        if state["quiet"] < 30:
            return
        start = unreal.Vector(-400, 400, 0)
        end = unreal.Vector(3800, 400, 0)
        p = unreal.NavigationSystemV1.find_path_to_location_synchronously(world, start, end)
        ok = p is not None and p.is_valid()
        log("smoke path Intake->Hub valid=%s points=%d" % (ok, len(p.path_points) if p else 0))
        if not ok:
            log("FAILED: no navigation data")
            finish(2)
            return
        saved = level_sub.save_current_level()
        log("level saved: %s (ticks=%d)" % (saved, n))
        finish(0 if saved else 3)
    except Exception as ex:
        log("EXCEPTION %s" % ex)
        finish(4)


state["handle"] = unreal.register_slate_post_tick_callback(tick)
log("registered")
