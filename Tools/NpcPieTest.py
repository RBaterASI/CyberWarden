"""Headless Play In Editor test of the placed NPC(s). Read-only: nothing is saved.

  set NPC_TEST_MODE=smoke|observe   (default smoke)   set NPC_TEST_SECONDS=<game seconds for observe, default 180>
  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/NpcPieTest.py" -unattended -nop4 -nosplash -NullRHI

smoke   : Python drives the NPC's AIController (MoveToLocation) through the route twice. Proves the pawn, controller,
          capsule, collision, avoidance and the baked navmesh work with real AI movement (no StateTree needed).
observe : Does not command anything. Watches a StateTree-driven NPC and checks the M2.1B acceptance criteria
          (start delay, movement by AI navigation, idle pauses, arrival at stops, no teleporting, navigation failures).
"""
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
MODE = os.environ.get("NPC_TEST_MODE", "smoke")
OBSERVE_SECONDS = float(os.environ.get("NPC_TEST_SECONDS", "180"))
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
st = {"n": 0, "pie": False, "post": 0, "h": None, "phase": "init", "t0": 0.0, "leg": 0, "loops": 0, "legs": [], "pending": None,
      "pos": None, "path": 0.0, "teleports": 0, "maxstep": 0.0, "idle_until": 0.0, "last_t": 0.0, "states": [], "last_state": None,
      "arrivals": 0, "first_move": None}


def log(m):
    unreal.log("[NPCTEST] " + m)


def done(code):
    unreal.unregister_slate_post_tick_callback(st["h"])
    log("exit %d" % code)
    unreal.SystemLibrary.quit_editor()


def d2(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def finish(gw, ok_all):
    log("RESULT %s: legs=%d arrivals=%d path_cm=%.0f max_step_cm=%.0f teleports=%d" % ("PASS" if ok_all else "FAIL", len(st["legs"]), st["arrivals"], st["path"], st["maxstep"], st["teleports"]))
    unreal.SystemLibrary.execute_console_command(gw, "slomo 1")
    level_sub.editor_request_end_play()
    done(0 if ok_all else 3)


def tick(dt):
    st["n"] += 1
    try:
        if st["n"] == 200 and not st["pie"]:
            level_sub.editor_request_begin_play()
            st["pie"] = True
            log("PIE requested, mode=%s" % MODE)
            return
        if st["n"] > 40000:
            log("FAILED: timeout")
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
        now = unreal.GameplayStatics.get_time_seconds(gw)
        npcs = unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC")
        if st["phase"] == "init":
            log("NPCs in PIE world: %d" % len(npcs))
            if not npcs:
                log("FAILED: no NPC placed (run Tools/PlaceNpcs.py)")
                done(4)
                return
            npc = npcs[0]
            ctrl = npc.get_controller()
            log("NPC=%s controller=%s class=%s" % (npc.get_actor_label(), ctrl.get_name() if ctrl else None, ctrl.get_class().get_name() if ctrl else None))
            if ctrl is None:
                log("FAILED: NPC has no AI controller")
                done(5)
                return
            route = list(npc.get_editor_property("Route"))
            log("route: " + " -> ".join(r.get_actor_label() for r in route))
            cmc = npc.get_editor_property("character_movement")
            log("capsule r=%.0f hh=%.0f  walk speed=%.0f  RVO=%s" % (npc.get_component_by_class(unreal.CapsuleComponent).get_editor_property("capsule_radius"),
                npc.get_component_by_class(unreal.CapsuleComponent).get_editor_property("capsule_half_height"), cmc.get_editor_property("max_walk_speed"), cmc.get_editor_property("use_rvo_avoidance")))
            st.update(npc=npc, ctrl=ctrl, route=route, pos=npc.get_actor_location(), t0=now, last_t=now, spawn=npc.get_actor_location())
            if MODE == "smoke":
                cmc.set_editor_property("max_walk_speed", 400.0)  # PIE copy only
                unreal.SystemLibrary.execute_console_command(gw, "slomo 4")
                st["phase"] = "wait_start"
                st["idle_until"] = now + 2.0
            else:
                st["phase"] = "observe"
            return
        npc, ctrl, route = st["npc"], st["ctrl"], st["route"]
        loc = npc.get_actor_location()
        step = d2(loc, st["pos"]) + abs(loc.z - st["pos"].z)
        span = max(now - st["last_t"], 1e-3)
        if step > max(450.0 * span * 3.0, 120.0):
            st["teleports"] += 1
            log("WARNING possible teleport: %.0f cm in %.2f s at (%.0f,%.0f,%.0f)" % (step, span, loc.x, loc.y, loc.z))
        st["maxstep"] = max(st["maxstep"], step)
        st["path"] += step
        if st["first_move"] is None and d2(loc, st["spawn"]) > 20:
            st["first_move"] = now - st["t0"]
            log("first movement after %.1f s" % st["first_move"])
        st["pos"], st["last_t"] = loc, now

        if MODE == "smoke":
            if st["phase"] == "wait_start" and now >= st["idle_until"]:
                st["phase"] = "move"
                st["pending"] = route[st["leg"] % len(route)]
                tgt = st["pending"].get_actor_location()
                res = ctrl.move_to_location(tgt, 60.0, True, True, False, False, None, True)
                st["leg_t0"] = now
                log("leg %d -> %s : request=%s" % (st["leg"], st["pending"].get_actor_label(), res))
            elif st["phase"] == "move":
                tgt = st["pending"].get_actor_location()
                status = ctrl.get_move_status()
                dist = d2(loc, tgt)
                if dist < 110 and "IDLE" in str(status):
                    st["legs"].append((st["pending"].get_actor_label(), now - st["leg_t0"], True))
                    st["arrivals"] += 1
                    log("  arrived %s in %.1f s (dist %.0f)" % (st["pending"].get_actor_label(), now - st["leg_t0"], dist))
                    st["leg"] += 1
                    st["phase"] = "wait_start"
                    st["idle_until"] = now + 1.5
                    if st["leg"] >= 2 * len(route):
                        finish(gw, all(l[2] for l in st["legs"]) and st["teleports"] == 0)
                elif "IDLE" in str(status) and now - st["leg_t0"] > 3.0:
                    st["legs"].append((st["pending"].get_actor_label(), now - st["leg_t0"], False))
                    log("  FAILED leg to %s: move ended idle at distance %.0f" % (st["pending"].get_actor_label(), dist))
                    finish(gw, False)
                elif now - st["leg_t0"] > 120:
                    st["legs"].append((st["pending"].get_actor_label(), 120, False))
                    log("  FAILED leg to %s: timeout, distance %.0f" % (st["pending"].get_actor_label(), dist))
                    finish(gw, False)
        else:  # observe
            state = str(npc.get_editor_property("MoveState"))
            if state != st["last_state"]:
                cur = int(npc.get_editor_property("CurrentStopIndex"))
                log("t=%6.1f state %s -> %s  stop=%d  fails=%d  dist_to_stop=%s" % (now - st["t0"], st["last_state"], state, cur,
                    int(npc.get_editor_property("NavFailureCount")), "%.0f" % d2(loc, route[cur].get_actor_location()) if 0 <= cur < len(route) else "-"))
                st["states"].append((now - st["t0"], state))
                st["last_state"] = state
            if now - st["t0"] > OBSERVE_SECONDS:
                seq = [s for _, s in st["states"]]
                moving = seq.count("Moving")
                idles = seq.count("Idle")
                fails = int(npc.get_editor_property("NavFailureCount"))
                ok = (st["first_move"] is not None and moving >= 3 and idles >= 2 and st["teleports"] == 0 and fails == 0)
                log("observed %.0f s: Moving x%d, Idle x%d, NavFail x%d, first_move=%s, path=%.0f cm" % (OBSERVE_SECONDS, moving, idles, fails, st["first_move"], st["path"]))
                finish(gw, ok)
    except Exception as ex:
        import traceback
        log("EXCEPTION %s\n%s" % (ex, traceback.format_exc()))
        done(9)


st["h"] = unreal.register_slate_post_tick_callback(tick)
