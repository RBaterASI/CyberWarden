"""Headless PIE test: navigation-failure recovery of the REAL StateTree with the schedule integration. Saves nothing.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/ScheduleRecoveryTest.py -Log <abs log>

At the 08:00 work period WRK01 alternates between Work_Servery_S and Work_Servery_N. In the PIE copy only, Work_Servery_N is moved
far off the navmesh so every Move To to it fails. Expected with the Checkpoint B tree: the failure is reported (MoveState NavFail, counter
increments), the Recover state waits 2 s, the routine re-plans (no restart storm, no teleport) and WRK01 keeps working at the
reachable counter; the other prisoners are unaffected.
"""
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
S = {"n": 0, "pie": False, "post": 0, "h": None, "t0": None, "res": [], "fail": [], "states": [], "last": None, "pos": None, "tele": 0, "plans0": 0, "arrivals": 0}


def log(m):
    unreal.log("[RECOVERYTEST] " + m)


def check(name, ok, detail=""):
    S["res"].append(bool(ok))
    if not ok:
        S["fail"].append(name)
    log("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  (%s)" % detail))


def finish(code):
    unreal.unregister_slate_post_tick_callback(S["h"])
    log("RESULT %s (%d/%d checks)" % ("PASS" if not S["fail"] and code == 0 else "FAIL", sum(S["res"]), len(S["res"])))
    level_sub.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


def tick(dt):
    S["n"] += 1
    try:
        if S["n"] == 200 and not S["pie"]:
            level_sub.editor_request_begin_play()
            S["pie"] = True
            return
        if S["n"] > 80000:
            log("FAILED: timeout")
            finish(2)
            return
        if not S["pie"]:
            return
        gw = ues.get_game_world()
        if gw is None:
            return
        S["post"] += 1
        if S["post"] < 80:
            return
        now = unreal.GameplayStatics.get_time_seconds(gw)
        if S["t0"] is None:
            mgr = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1ScheduleManager")[0]
            npcs = {str(a.get_editor_property("NpcId")): a for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")}
            S.update(mgr=mgr, npcs=npcs, wrk=npcs["WRK01"], t0=now)
            S["wrk_c"] = S["wrk"].get_component_by_class(unreal.PrisonScheduleComponent)
            bad = unreal.GameplayStatics.get_all_actors_with_tag(gw, "MarkerId:Work_Servery_N")[0]
            bad.set_actor_location(unreal.Vector(-3000, -3000, 0), False, False)  # PIE copy only: unreachable
            log("moved Work_Servery_N off the navmesh (PIE copy only)")
            mgr.set_time_of_day_hours(8.0)  # work period, WRK01 serves at both counters
            unreal.SystemLibrary.execute_console_command(gw, "slomo 4")
            S["pos"] = S["wrk"].get_actor_location()
            S["nf0"] = int(S["wrk"].get_editor_property("NavFailureCount"))
            S["others_nf0"] = {k: int(v.get_editor_property("NavFailureCount")) for k, v in npcs.items() if k != "WRK01"}
            return
        loc = S["wrk"].get_actor_location()
        step = math.hypot(loc.x - S["pos"].x, loc.y - S["pos"].y)
        if step > 120.0:
            S["tele"] += 1
        S["pos"] = loc
        st = str(S["wrk"].get_editor_property("MoveState"))
        if st != S["last"]:
            S["states"].append((round(now - S["t0"], 1), st))
            S["last"] = st
        if now - S["t0"] >= 160.0:
            unreal.SystemLibrary.execute_console_command(gw, "slomo 1")
            seq = [s for _, s in S["states"]]
            nf = int(S["wrk"].get_editor_property("NavFailureCount")) - S["nf0"]
            c = S["wrk_c"]
            log("WRK01 state sequence: %s" % " ".join("%s@%.0f" % (s, t) for t, s in S["states"][:40]))
            log("WRK01 navigation failures reported: %d ; plans=%d acks=%d retry streak=%d ; teleports=%d" % (nf, c.get_editor_property("plan_count"),
                c.get_editor_property("replan_ack_count"), c.get_editor_property("retry_streak_count"), S["tele"]))
            check("failure reported by the real tree (NavFail state seen, counter incremented)", nf >= 1 and "NavFail" in seq, "nf=%d" % nf)
            after = [seq[i + 1] for i in range(len(seq) - 1) if seq[i] == "NavFail"]
            check("recovered after every NavFail: the routine went on to Idle (reachable counter) or Moving, never stayed in NavFail (%d recoveries)" % len(after), len(after) >= 1 and all(s in ("Idle", "Moving", "StartDelay") for s in after), str(after))
            check("the reachable counter was still served (Idle states between the failures)", seq.count("Idle") >= 3, str(seq.count("Idle")))
            check("no restart storm: fewer than 40 plans in 160 world seconds", c.get_editor_property("plan_count") < 40, str(c.get_editor_property("plan_count")))
            check("no teleports while recovering", S["tele"] == 0, str(S["tele"]))
            check("failures are not endless: fewer than 20 in 160 world seconds", nf < 20, str(nf))
            for k, v in S["npcs"].items():
                if k != "WRK01":
                    d = int(v.get_editor_property("NavFailureCount")) - S["others_nf0"][k]
                    check("%s unaffected (0 navigation failures)" % k, d == 0, str(d))
            finish(0)
    except Exception as ex:
        import traceback
        log("EXCEPTION %s\n%s" % (ex, traceback.format_exc()))
        finish(9)


S["h"] = unreal.register_slate_post_tick_callback(tick)
