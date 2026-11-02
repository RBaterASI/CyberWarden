"""Read-only check (fresh process) that the NPC foundation assets persisted with the intended defaults.

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/VerifyNpcFoundation.py" -unattended -nop4 -nosplash -NullRHI
"""
import unreal

D = "/Game/CyberWarden/NPC"
bel = unreal.BlueprintEditorLibrary
OK = []


def P(s):
    unreal.log("[NPCVERIFY] " + s)


def get(o, n):
    try:
        return o.get_editor_property(n)
    except Exception as ex:
        return "ERR(%s)" % str(ex)[:50]


def check(label, cond):
    OK.append(bool(cond))
    P("%-58s %s" % (label, "OK" if cond else "FAIL"))


npc = unreal.load_asset(D + "/BP_PrisonNPC")
ctrl = unreal.load_asset(D + "/BP_NPCController")
t1 = unreal.load_asset(D + "/STT_ChooseNextStop")
t2 = unreal.load_asset(D + "/STT_ReportState")
for n, a in (("BP_PrisonNPC", npc), ("BP_NPCController", ctrl), ("STT_ChooseNextStop", t1), ("STT_ReportState", t2)):
    check("asset loads: " + n, a is not None)

cls = bel.generated_class(npc)
cdo = unreal.get_default_object(cls)
P("BP_PrisonNPC variables: " + ", ".join(bel.list_member_variable_names(npc)))
cap = cdo.get_component_by_class(unreal.CapsuleComponent)
mesh = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
cmc = cdo.get_component_by_class(unreal.CharacterMovementComponent)
check("capsule radius 34 / half height 90", get(cap, "capsule_radius") == 34.0 and get(cap, "capsule_half_height") == 90.0)
check("mesh = SKM_Manny_Simple", "SKM_Manny_Simple" in str(get(mesh, "skeletal_mesh_asset")))
check("anim class = ABP_Unarmed", "ABP_Unarmed" in str(get(mesh, "anim_class")))
check("mesh offset (0,0,-90) yaw -90", abs(get(mesh, "relative_location").z + 90) < 0.01 and abs(get(mesh, "relative_rotation").yaw + 90) < 0.01)
check("RVO avoidance on, orient to movement", get(cmc, "use_rvo_avoidance") is True and get(cmc, "orient_rotation_to_movement") is True)
check("AIControllerClass = BP_NPCController", "BP_NPCController" in str(get(cdo, "ai_controller_class")))
check("AutoPossessAI = placed in world or spawned", "PLACED_IN_WORLD_OR_SPAWNED" in str(get(cdo, "auto_possess_ai")))
for k, v in (("StartDelaySeconds", 6.0), ("IdleMin", 4.0), ("IdleMax", 8.0), ("NextStopIndex", 0), ("CurrentStopIndex", -1),
             ("StartDelayPending", True), ("MoveState", "Spawned"), ("NavFailureCount", 0), ("NpcId", "NPC")):
    check("default %s == %s" % (k, v), get(cdo, k) == v)

sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
names = []
for h in sub.k2_gather_subobject_data_for_blueprint(ctrl):
    d = sub.k2_find_subobject_data_from_handle(h)
    d = d[1] if isinstance(d, tuple) else d
    names.append(str(unreal.SubobjectDataBlueprintFunctionLibrary.get_display_name(d)))
P("BP_NPCController components: " + ", ".join(names))
check("controller has StateTreeAI component", any("StateTreeAI" in n for n in names))

for bp, expect in ((t1, {"ContextActor": "Context", "TargetActor": "Output", "IdleSeconds": "Output", "StartDelay": "Output"}),
                   (t2, {"ContextActor": "Context", "StateLabel": "Parameter"})):
    for v, cat in expect.items():
        got = str(bel.get_blueprint_variable_category(bp, v))
        check("%s.%s category == %s" % (bp.get_name(), v, cat), got == cat)
    tc = unreal.get_default_object(bel.generated_class(bp))
    check("%s considered_for_completion False" % bp.get_name(), get(tc, "considered_for_completion") is False)
    check("%s should_state_change_on_reselect True" % bp.get_name(), get(tc, "should_state_change_on_reselect") is True)

check("ST_NPCRoutine present (manual step)", unreal.EditorAssetLibrary.does_asset_exist(D + "/ST_NPCRoutine"))
P("RESULT: %d/%d checks passed" % (sum(OK), len(OK)))
