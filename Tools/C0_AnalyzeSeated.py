"""M2.3 Stage C0 step 5 (read-only): measures the retargeted SEAT_* clips against MM_Idle and the Mixamo sources: root drift,
pelvis path, foot planting, pose continuity at the hand-offs (sit end -> idle start, idle loop point, idle end -> stand start,
stand end -> MM_Idle) and the Mixamo-vs-Manny pelvis height ratio. Component space, cm; the mannequin faces +Y.
Report: Saved/C0_AnalyzeSeated.txt
"""
import math
import unreal

SEAT = "/Game/CyberWarden/Anims/Seated/"
MX = "/Game/CyberWarden/Anims/Mixamo/"
IDLE = "/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle"
BONES = ["root", "pelvis", "spine_05", "head", "thigh_l", "calf_l", "foot_l", "ball_l", "thigh_r", "calf_r", "foot_r", "ball_r", "hand_l", "hand_r", "upperarm_l", "upperarm_r"]
out = []


def p(m):
    out.append(str(m))
    unreal.log("[C0] " + str(m))


WORLD = unreal.AnimPoseSpaces.WORLD
OPTS = unreal.AnimPoseEvaluationOptions()


def pose_at(anim, t, bones):
    ps = unreal.AnimPoseExtensions.get_anim_pose_at_time(anim, t, OPTS)
    return {b: unreal.AnimPoseExtensions.get_bone_pose(ps, b, WORLD) for b in bones}


def pos(tr):
    v = tr.translation
    return (v.x, v.y, v.z)


def angle_deg(q1, q2):
    d = abs(q1.x * q2.x + q1.y * q2.y + q1.z * q2.z + q1.w * q2.w)
    return math.degrees(2.0 * math.acos(min(1.0, d)))


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def pose_diff(pa, pb):
    """max/mean position and rotation difference over bones (component space)."""
    mp, mr, sp, sr = 0.0, 0.0, 0.0, 0.0
    worst = ""
    for b in BONES:
        d = dist(pos(pa[b]), pos(pb[b]))
        r = angle_deg(pa[b].rotation, pb[b].rotation)
        sp += d
        sr += r
        if d > mp:
            mp, worst = d, b
        mr = max(mr, r)
    return mp, sp / len(BONES), mr, sr / len(BONES), worst


def f(v):
    return "(%.1f, %.1f, %.1f)" % v


clips = {n: unreal.load_asset(SEAT + n) for n in ("SEAT_StandToSit", "SEAT_SittingIdle", "SEAT_SitToStand")}
idle = unreal.load_asset(IDLE)
poses = {}
for n, a in clips.items():
    L = a.get_play_length()
    N = unreal.AnimationLibrary.get_num_frames(a)
    p("== %s len=%.3fs frames=%d root_lock=%s root_motion=%s" % (n, L, N, a.get_editor_property("force_root_lock"), a.get_editor_property("enable_root_motion")))
    first, last = pose_at(a, 0.0, BONES), pose_at(a, L, BONES)
    poses[n] = (first, last)
    # root drift and pelvis / foot paths
    samples = [pose_at(a, L * i / 20.0, BONES) for i in range(21)]
    rootmax = max(dist(pos(s["root"]), pos(first["root"])) for s in samples)
    p("  root bone max drift %.3f cm (root pos %s)" % (rootmax, f(pos(first["root"]))))
    p("  pelvis start %s end %s" % (f(pos(first["pelvis"])), f(pos(last["pelvis"]))))
    p("  pelvis z range %.1f..%.1f ; pelvis y range %.1f..%.1f ; pelvis x range %.1f..%.1f" % (
        min(pos(s["pelvis"])[2] for s in samples), max(pos(s["pelvis"])[2] for s in samples),
        min(pos(s["pelvis"])[1] for s in samples), max(pos(s["pelvis"])[1] for s in samples),
        min(pos(s["pelvis"])[0] for s in samples), max(pos(s["pelvis"])[0] for s in samples)))
    for fb in ("foot_l", "foot_r", "ball_l", "ball_r"):
        xy0 = pos(first[fb])[:2]
        drift = max(math.hypot(pos(s[fb])[0] - xy0[0], pos(s[fb])[1] - xy0[1]) for s in samples)
        zs = [pos(s[fb])[2] for s in samples]
        p("  %s start %s ; max xy travel from start %.1f cm ; z %.1f..%.1f" % (fb, f(pos(first[fb])), drift, min(zs), max(zs)))
    # largest per-frame pelvis step (smoothness)
    step = 0.0
    prev = None
    for i in range(N):
        cur = pos(pose_at(a, min(L, i / 30.0), ["pelvis"])["pelvis"])
        if prev:
            step = max(step, dist(cur, prev))
        prev = cur
    p("  largest per-frame pelvis step %.2f cm (%.0f cm/s)" % (step, step * 30))

p("== reference: MM_Idle")
ip = pose_at(idle, 0.0, BONES)
for b in ("pelvis", "foot_l", "foot_r", "head", "hand_l", "hand_r"):
    p("  %s %s" % (b, f(pos(ip[b]))))

p("== continuity (max position diff cm / mean pos / max rot deg / mean rot deg, worst bone)")
S2S, SI, S2U = poses["SEAT_StandToSit"], poses["SEAT_SittingIdle"], poses["SEAT_SitToStand"]
for label, a, b in (("StandToSit START vs MM_Idle", S2S[0], ip), ("StandToSit END -> SittingIdle START", S2S[1], SI[0]),
                    ("SittingIdle END -> START (loop)", SI[1], SI[0]), ("SittingIdle END -> SitToStand START", SI[1], S2U[0]),
                    ("SitToStand END vs MM_Idle", S2U[1], ip)):
    r = pose_diff(a, b)
    p("  %-38s %.1f / %.1f / %.1f / %.1f  (%s)" % ((label,) + r))

# seated geometry for the stool fit (SittingIdle mid pose)
a = clips["SEAT_SittingIdle"]
mid = pose_at(a, a.get_play_length() * 0.5, BONES)
p("== seated pose (SittingIdle midpoint; +Y = facing direction)")
for b in BONES:
    p("  %-12s %s" % (b, f(pos(mid[b]))))
stand = ip
p("pelvis drop standing->seated: %.1f cm ; pelvis shift back (Y): %.1f cm" % (pos(stand["pelvis"])[2] - pos(mid["pelvis"])[2], pos(mid["pelvis"])[1] - pos(stand["pelvis"])[1]))
p("knee (calf) forward of pelvis: %.1f cm ; foot forward of pelvis: %.1f cm ; hand forward of pelvis: %.1f cm at z %.1f" % (
    pos(mid["calf_l"])[1] - pos(mid["pelvis"])[1], pos(mid["foot_l"])[1] - pos(mid["pelvis"])[1], pos(mid["hand_l"])[1] - pos(mid["pelvis"])[1], pos(mid["hand_l"])[2]))

# fidelity: Mixamo vs retargeted pelvis height ratio
mxm = unreal.load_asset(MX + "MX_StandToSit")
mx_h = mxm.get_bounds().box_extent.z * 2.0
manny = unreal.load_asset("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple")
mn_h = manny.get_bounds().box_extent.z * 2.0
p("== fidelity: mesh heights Mixamo %.1f cm, Manny %.1f cm" % (mx_h, mn_h))
src = unreal.load_asset(MX + "MX_SittingIdle")
sp = pose_at(src, src.get_play_length() * 0.5, ["mixamorig:Hips", "mixamorig:LeftFoot", "mixamorig:RightFoot"])
p("Mixamo seated hips z %.1f (%.2f of height) ; Manny seated pelvis z %.1f (%.2f of height)" % (pos(sp["mixamorig:Hips"])[2], pos(sp["mixamorig:Hips"])[2] / mx_h, pos(mid["pelvis"])[2], pos(mid["pelvis"])[2] / mn_h))

with open(unreal.Paths.project_saved_dir() + "C0_AnalyzeSeated.txt", "w") as fh:
    fh.write("\n".join(out))
unreal.SystemLibrary.quit_editor()
