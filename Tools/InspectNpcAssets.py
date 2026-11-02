"""Read-only inspection of the manually authored M2.1B assets (StateTree, tasks, NPC animation setup). Saves nothing.

  UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs>/Tools/InspectNpcAssets.py" -unattended -nop4 -nosplash -NullRHI
"""
import unreal

N = "/Game/CyberWarden/NPC/"
out = []


def p(m):
    out.append(str(m))
    unreal.log("[INSPECT] " + str(m))


def safe(f, default="<n/a>"):
    try:
        return f()
    except Exception as ex:
        return "%s(%s)" % (default, str(ex)[:80])


for name in ("ST_NPCRoutine", "BP_NPCController", "BP_PrisonNPC", "STT_ChooseNextStop", "STT_ReportState"):
    a = unreal.load_asset(N + name)
    p("%s: %s" % (name, a.get_class().get_name() if a else "MISSING"))

st = unreal.load_asset(N + "ST_NPCRoutine")
if st:
    for prop in ("schema", "editor_data", "states", "tasks"):
        p("  ST.%s = %s" % (prop, safe(lambda: st.get_editor_property(prop))))
    p("  dir(st) editor-ish: %s" % [d for d in dir(st) if not d.startswith("_")][:40])
    sch = safe(lambda: st.get_editor_property("schema"))
    p("  schema class: %s" % (sch.get_class().get_name() if hasattr(sch, "get_class") else sch))

ctrl = unreal.load_asset(N + "BP_NPCController")
cdo = unreal.get_default_object(ctrl.generated_class())
comp = safe(lambda: cdo.get_editor_property("StateTreeAI"))
p("Controller StateTreeAI component: %s" % comp)
if hasattr(comp, "get_editor_property"):
    ref = safe(lambda: comp.get_editor_property("state_tree_ref"))
    p("  state_tree_ref = %s" % ref)
    p("  start_logic_automatically = %s" % safe(lambda: comp.get_editor_property("start_logic_automatically")))
    p("  state_tree prop = %s" % safe(lambda: comp.get_editor_property("state_tree")))

npc = unreal.load_asset(N + "BP_PrisonNPC")
ncdo = unreal.get_default_object(npc.generated_class())
mesh = ncdo.get_editor_property("mesh")
p("BP_PrisonNPC anim_class = %s" % mesh.get_editor_property("anim_class"))
p("BP_PrisonNPC anim mode = %s" % mesh.get_editor_property("animation_mode"))
p("BP_PrisonNPC controller class = %s" % ncdo.get_editor_property("ai_controller_class"))
cap = ncdo.get_editor_property("capsule_component")
p("capsule r=%s hh=%s" % (cap.get_editor_property("capsule_radius"), cap.get_editor_property("capsule_half_height")))

for abp in ("ABP_Unarmed", "ABP_PrisonNPC"):
    a = unreal.load_asset("/Game/Characters/Mannequins/Anims/Unarmed/" + abp)
    p("%s: %s skeleton=%s parent=%s" % (abp, a.get_class().get_name() if a else "MISSING",
      safe(lambda: a.get_editor_property("target_skeleton").get_name()), safe(lambda: a.get_editor_property("parent_class"))))

# player character must still use ABP_Unarmed
pc = unreal.load_asset("/Game/ThirdPerson/Blueprints/BP_CyberWardenCharacter") or unreal.load_asset("/Game/CyberWarden/Blueprints/BP_CyberWardenCharacter")
if pc:
    pcdo = unreal.get_default_object(pc.generated_class())
    p("Player anim_class = %s" % pcdo.get_editor_property("mesh").get_editor_property("anim_class"))

# placed NPC in level
lvl = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
lvl.load_level("/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox")
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if "S01F1NPC" in [str(t) for t in a.tags]:
        p("Placed %s class=%s route=%s start_delay=%s idle=%s-%s" % (a.get_actor_label(), a.get_class().get_name(),
          [r.get_actor_label() for r in a.get_editor_property("Route")], a.get_editor_property("StartDelaySeconds"),
          a.get_editor_property("IdleMin"), a.get_editor_property("IdleMax")))

with open(unreal.Paths.project_saved_dir() + "InspectNpcAssets.txt", "w") as fh:
    fh.write("\n".join(out))
unreal.SystemLibrary.quit_editor()
