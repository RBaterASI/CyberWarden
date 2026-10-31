"""Create the reusable NPC Blueprint shells (M2.1B phase 1). Idempotent and NON-DESTRUCTIVE:
assets that already exist are never modified (graphs may have been wired in them); only missing assets are created.

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/CreateNpcFoundation.py" -unattended -nop4 -nosplash -NullRHI

Creates /Game/CyberWarden/NPC/: BP_PrisonNPC (Character), BP_NPCController (AIController + StateTree AI component),
STT_ChooseNextStop and STT_ReportState (StateTree task Blueprints). ST_NPCRoutine and all graph logic are manual
(see Docs/NPC/M2_1B_Manual_Setup.md). Close the interactive editor first.
"""
import unreal

NPC_DIR = "/Game/CyberWarden/NPC"
SKM = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
ABP = "/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"
tools = unreal.AssetToolsHelpers.get_asset_tools()
bel = unreal.BlueprintEditorLibrary
eal = unreal.EditorAssetLibrary


def log(m):
    unreal.log("[NPCFOUNDATION] " + m)


def ensure_bp(name, parent):
    path = "%s/%s" % (NPC_DIR, name)
    if eal.does_asset_exist(path):
        log("EXISTS (left untouched): %s" % path)
        return None
    fac = unreal.BlueprintFactory()
    fac.set_editor_property("parent_class", parent)
    bp = tools.create_asset(name, NPC_DIR, unreal.Blueprint, fac)
    log("CREATED: %s (parent %s)" % (path, parent.__name__))
    return bp


T = {
    "float": bel.get_basic_type_by_name("float"),
    "int": bel.get_basic_type_by_name("int"),
    "bool": bel.get_basic_type_by_name("bool"),
    "string": bel.get_basic_type_by_name("string"),
    "actor": bel.get_object_reference_type(unreal.Actor),
}
T["actor_array"] = bel.get_array_type(T["actor"])


def add_var(bp, name, tkey, instance_editable=False, category=None):
    if not bel.add_member_variable(bp, name, T[tkey]):
        log("  !! could not add variable %s" % name)
        return
    if instance_editable:
        bel.set_blueprint_variable_instance_editable(bp, name, True)
    if category:
        bel.set_blueprint_variable_category(bp, name, category)


# --- BP_PrisonNPC --------------------------------------------------------------------------------
eal.make_directory(NPC_DIR)
npc = ensure_bp("BP_PrisonNPC", unreal.Character)
if npc:
    # Routine configuration (set per placed NPC by Tools/PlaceNpcs.py)
    add_var(npc, "NpcId", "string", True)
    add_var(npc, "ArchetypeName", "string", True)
    add_var(npc, "StartDelaySeconds", "float", True)
    add_var(npc, "IdleMin", "float", True)
    add_var(npc, "IdleMax", "float", True)
    add_var(npc, "Route", "actor_array", True)
    # Runtime state (written by the StateTree tasks, read by the debug overlay)
    add_var(npc, "NextStopIndex", "int")
    add_var(npc, "CurrentStopIndex", "int")
    add_var(npc, "StartDelayPending", "bool")
    add_var(npc, "MoveState", "string")
    add_var(npc, "NavFailureCount", "int")
    bel.compile_blueprint(npc)
    cdo = unreal.get_default_object(bel.generated_class(npc))
    for k, v in (("NpcId", "NPC"), ("ArchetypeName", "Prisoner"), ("StartDelaySeconds", 6.0), ("IdleMin", 4.0),
                 ("IdleMax", 8.0), ("NextStopIndex", 0), ("CurrentStopIndex", -1), ("StartDelayPending", True),
                 ("MoveState", "Spawned"), ("NavFailureCount", 0)):
        cdo.set_editor_property(k, v)
    cap = cdo.get_component_by_class(unreal.CapsuleComponent)
    cap.set_editor_property("capsule_radius", 34.0)
    cap.set_editor_property("capsule_half_height", 90.0)
    mesh = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
    mesh.set_editor_property("skeletal_mesh_asset", unreal.load_asset(SKM))
    mesh.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_BLUEPRINT)
    mesh.set_editor_property("anim_class", unreal.load_asset(ABP).generated_class())
    mesh.set_editor_property("relative_location", unreal.Vector(0, 0, -90))
    mesh.set_editor_property("relative_rotation", unreal.Rotator(0, 0, -90))
    cmc = cdo.get_component_by_class(unreal.CharacterMovementComponent)
    cmc.set_editor_property("max_walk_speed", 180.0)
    cmc.set_editor_property("orient_rotation_to_movement", True)
    cmc.set_editor_property("use_controller_desired_rotation", False)
    cmc.set_editor_property("rotation_rate", unreal.Rotator(0, 0, 500))
    cmc.set_editor_property("use_rvo_avoidance", True)
    cdo.set_editor_property("auto_possess_ai", unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)

# --- BP_NPCController ------------------------------------------------------------------------------
ctrl = ensure_bp("BP_NPCController", unreal.AIController)
if ctrl:
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = sub.k2_gather_subobject_data_for_blueprint(ctrl)
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=unreal.StateTreeAIComponent, blueprint_context=ctrl)
    new_handle, fail = sub.add_new_subobject(params)
    sub.rename_subobject(new_handle, "StateTreeAI")
    bel.compile_blueprint(ctrl)
    log("  added component StateTreeAI (StateTree AI Component); its State Tree asset is assigned manually")

# link NPC -> controller (needs both to exist)
if npc and ctrl:
    cdo = unreal.get_default_object(bel.generated_class(npc))
    cdo.set_editor_property("ai_controller_class", bel.generated_class(ctrl))
    log("  BP_PrisonNPC.AIControllerClass = BP_NPCController")


# --- StateTree task blueprints ---------------------------------------------------------------------
def make_task(name, vars_):
    bp = ensure_bp(name, unreal.StateTreeTaskBlueprintBase)
    if not bp:
        return
    for vname, tkey, cat in vars_:
        add_var(bp, vname, tkey, False, cat)
    bel.compile_blueprint(bp)
    cdo = unreal.get_default_object(bel.generated_class(bp))
    cdo.set_editor_property("considered_for_completion", False)       # background task: never completes the state
    cdo.set_editor_property("should_state_change_on_reselect", True)  # re-run EnterState when the loop re-enters Routine
    log("  %s: considered_for_completion=False, should_state_change_on_reselect=True" % name)


make_task("STT_ChooseNextStop", [("ContextActor", "actor", "Context"), ("TargetActor", "actor", "Output"),
                                 ("IdleSeconds", "float", "Output"), ("StartDelay", "float", "Output"),
                                 ("Idx", "int", None)])
make_task("STT_ReportState", [("ContextActor", "actor", "Context"), ("StateLabel", "string", "Parameter")])

# --- save everything that was created ------------------------------------------------------------------
for n in ("BP_PrisonNPC", "BP_NPCController", "STT_ChooseNextStop", "STT_ReportState"):
    p = "%s/%s" % (NPC_DIR, n)
    if eal.does_asset_exist(p):
        eal.save_loaded_asset(unreal.load_asset(p))
log("ST_NPCRoutine exists: %s (manual asset)" % eal.does_asset_exist(NPC_DIR + "/ST_NPCRoutine"))
log("done")
