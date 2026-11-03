"""Headless PIE probe: do the prisoners really animate (walk while moving, idle when stopped)? Saves nothing.

  powershell -File Tools/RunHeadless.ps1 -Script Tools/NpcAnimProbe.py -Log <abs log>

Runs the real StateTree for EMU seconds (default 150 game seconds at the 30x schedule clock, slomo 4) and, per prisoner and tick, samples:
the movement speed, the MoveState reported by the StateTree, the animation instance class, any readable animation variables
(Ground Speed / Should Move variants), and the motion of the foot bones relative to the actor (a walking pose swings the feet,
an idle pose does not). Reports the statistics for Moving versus Idle/StartDelay and checks the animation class.
"""
import math
import os

import unreal

LEVEL = "/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox"
SECONDS = float(os.environ.get("ANIM_SECONDS", "150"))
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_sub.load_level(LEVEL)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
S = {"n": 0, "pie": False, "post": 0, "h": None, "t0": None, "npcs": {}, "res": [], "fail": []}
VAR_NAMES = ["GroundSpeed", "Ground Speed", "Speed", "ShouldMove", "Should Move", "bShouldMove", "IsMoving"]


def log(m):
    unreal.log("[ANIMPROBE] " + m)


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


def foot_offsets(mesh, actor):
    """Feet positions in the actor's local frame (cm): they move when a walk cycle plays."""
    out = []
    xf = actor.get_actor_transform()
    for bone in ("foot_l", "foot_r"):
        try:
            w = mesh.get_socket_location(bone)
            out.append(xf.inverse_transform_location(w))
        except Exception:
            return None
    return out


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
            S["t0"] = now
            unreal.SystemLibrary.execute_console_command(gw, "slomo 4")
            for a in unreal.GameplayStatics.get_all_actors_with_tag(gw, "S01F1NPC"):
                mesh = a.get_component_by_class(unreal.SkeletalMeshComponent)
                ai = mesh.get_anim_instance()
                nid = str(a.get_editor_property("NpcId"))
                S["npcs"][nid] = dict(a=a, mesh=mesh, prev=None, prev_feet=None, stats={"Moving": [], "Idle": [], "Other": []}, vars={}, ai_class=ai.get_class().get_name() if ai else None,
                                      var_samples={})
                if ai:
                    for v in VAR_NAMES:
                        try:
                            ai.get_editor_property(v)
                            S["npcs"][nid]["vars"][v] = True
                        except Exception:
                            pass
            log("anim classes: %s ; readable animation variables: %s" % ({k: v["ai_class"] for k, v in S["npcs"].items()},
                {k: list(v["vars"]) for k, v in S["npcs"].items()}))
            return
        for nid, n in S["npcs"].items():
            a, mesh = n["a"], n["mesh"]
            state = str(a.get_editor_property("MoveState"))
            vel = a.get_velocity()
            speed = math.hypot(vel.x, vel.y)
            feet = foot_offsets(mesh, a)
            swing = None
            if feet is not None and n["prev_feet"] is not None:
                swing = sum(math.dist((f.x, f.y, f.z), (p.x, p.y, p.z)) for f, p in zip(feet, n["prev_feet"]))
            n["prev_feet"] = feet
            bucket = "Moving" if state == "Moving" and speed > 20 else ("Idle" if speed < 3 else "Other")
            if swing is not None:
                n["stats"][bucket].append((speed, swing))
            ai = mesh.get_anim_instance()
            if ai and n["vars"]:
                for v in n["vars"]:
                    try:
                        n["var_samples"].setdefault((bucket, v), []).append(ai.get_editor_property(v))
                    except Exception:
                        pass
            # animation state vs real movement. "Settled" samples skip the few frames where the animation variable lags the movement.
            n["still_ticks"] = n.get("still_ticks", 0) + 1 if speed < 3 else 0
            n["move_ticks"] = n.get("move_ticks", 0) + 1 if speed > 20 else 0
            if ai and "ShouldMove" in n["vars"] and "GroundSpeed" in n["vars"]:
                try:
                    sm, gs = bool(ai.get_editor_property("ShouldMove")), float(ai.get_editor_property("GroundSpeed"))
                    if n["move_ticks"] >= 10:
                        n["settled_move"] = n.get("settled_move", 0) + 1
                        n["move_ok"] = n.get("move_ok", 0) + (1 if sm and abs(gs - speed) < 25.0 else 0)
                    if n["still_ticks"] >= 10:
                        n["settled_idle"] = n.get("settled_idle", 0) + 1
                        n["idle_ok"] = n.get("idle_ok", 0) + (1 if (not sm) and gs < 3.0 else 0)
                    if n["still_ticks"] == 1 or n["move_ticks"] == 1:
                        n["transitions"] = n.get("transitions", 0) + 1
                except Exception:
                    pass
        if now - S["t0"] >= SECONDS:
            unreal.SystemLibrary.execute_console_command(gw, "slomo 1")
            for nid, n in S["npcs"].items():
                check("%s: uses ABP_PrisonNPC" % nid, n["ai_class"] is not None and "ABP_PrisonNPC" in n["ai_class"], str(n["ai_class"]))
                mv, idl = n["stats"]["Moving"], n["stats"]["Idle"]
                mv_sw = sum(s for _, s in mv) / max(len(mv), 1)
                id_sw = sum(s for _, s in idl) / max(len(idl), 1)
                log("%s: moving samples=%d avg speed=%.0f cm/s avg foot motion/tick=%.2f cm ; idle samples=%d avg foot motion/tick=%.3f cm" % (
                    nid, len(mv), sum(v for v, _ in mv) / max(len(mv), 1), mv_sw, len(idl), id_sw))
                for (bucket, v), vals in sorted(n["var_samples"].items()):
                    try:
                        log("   %s %s: min=%s max=%s (n=%d)" % (bucket, v, min(vals), max(vals), len(vals)))
                    except Exception:
                        pass
                check("%s: walked (moving samples collected)" % nid, len(mv) > 20, str(len(mv)))
                check("%s: stood idle (idle samples collected)" % nid, len(idl) > 20, str(len(idl)))
                log("%s: foot-bone motion is not measurable headless (no pose evaluation without rendering): %.2f / %.3f cm per tick, informational only" % (nid, mv_sw, id_sw))
                sm_n, si_n = n.get("settled_move", 0), n.get("settled_idle", 0)
                check("%s: while walking the animation blueprint says ShouldMove with GroundSpeed matching the real speed (%d/%d settled samples)" % (nid, n.get("move_ok", 0), sm_n),
                      sm_n > 20 and n.get("move_ok", 0) >= 0.98 * sm_n, "%d/%d" % (n.get("move_ok", 0), sm_n))
                check("%s: while standing still the animation blueprint says not ShouldMove with GroundSpeed ~0 (%d/%d settled samples)" % (nid, n.get("idle_ok", 0), si_n),
                      si_n > 20 and n.get("idle_ok", 0) >= 0.98 * si_n, "%d/%d" % (n.get("idle_ok", 0), si_n))
                log("%s: %d walk/stand transitions observed" % (nid, n.get("transitions", 0)))
            finish(0)
    except Exception as ex:
        import traceback
        log("EXCEPTION %s\n%s" % (ex, traceback.format_exc()))
        finish(9)


S["h"] = unreal.register_slate_post_tick_callback(tick)
