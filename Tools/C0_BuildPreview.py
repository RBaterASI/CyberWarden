"""M2.3 Stage C0 step 6: builds the standalone preview level /Game/CyberWarden/Anims/Preview/L_C0_SeatPreview and the Level Sequence
LS_C0_SeatPreview. Nothing in the Floor 1 level, navigation, schedules or gameplay is touched; this is a new, separate level.

Level contents (units cm; characters face +Y, the cafeteria geometry is reproduced to scale):
  * "Strip A" (x = 0, y = 0..1200): SKM_Manny_Simple frozen at 7 sample times of stand-to-sit (6) and seated idle (1)
  * "Strip B" (x = 0, y = 1800..3000): sit-to-stand at 6 sample times
  * "Live" (x = 600): one Manny driven by the Level Sequence: stand-to-sit, seated idle x2, sit-to-stand, in front of a full 300 x 100 x 75 table
Every figure stands with its feet on the origin of its slot (the cafeteria marker is 45 cm from the table edge), with a 38 x 38 x 44 cm stool
behind it at the pelvis position of the clip and a table slab whose near edge is 45 cm in front of the marker.
Report: Saved/C0_BuildPreview.txt
"""
import unreal

DEST = "/Game/CyberWarden/Anims/Preview"
LVL = DEST + "/L_C0_SeatPreview"
SEAT = "/Game/CyberWarden/Anims/Seated/"
MANNY = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
CUBE = "/Engine/BasicShapes/Cube"
out = []


def p(m):
    out.append(str(m))
    unreal.log("[C0] " + str(m))


unreal.EditorAssetLibrary.make_directory(DEST)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if unreal.EditorAssetLibrary.does_asset_exist(LVL):
    unreal.EditorAssetLibrary.delete_asset(LVL)
if unreal.EditorAssetLibrary.does_asset_exist(DEST + "/LS_C0_SeatPreview"):
    unreal.EditorAssetLibrary.delete_asset(DEST + "/LS_C0_SeatPreview")
p("new level: %s" % les.new_level(LVL))

manny = unreal.load_asset(MANNY)
cube = unreal.load_asset(CUBE)
s2s = unreal.load_asset(SEAT + "SEAT_StandToSit")
idle = unreal.load_asset(SEAT + "SEAT_SittingIdle")
s2u = unreal.load_asset(SEAT + "SEAT_SitToStand")


def box(label, cx, cy, cz, sx, sy, sz):
    a = eas.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(cx, cy, cz))
    a.static_mesh_component.set_static_mesh(cube)
    a.set_actor_scale3d(unreal.Vector(sx / 100.0, sy / 100.0, sz / 100.0))
    a.set_actor_label(label)
    return a


def figure(label, x, y, anim, t):
    a = eas.spawn_actor_from_class(unreal.SkeletalMeshActor, unreal.Vector(x, y, 0))
    c = a.skeletal_mesh_component
    c.set_skeletal_mesh_asset(manny)
    c.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    c.override_animation_data(anim, False, False, t, 1.0)
    a.set_actor_label(label)
    return a


def furniture(tag, x, y, table_w):
    box("%s_Stool" % tag, x, y - 46.0, 22.0, 38.0, 38.0, 44.0)
    box("%s_Table" % tag, x, y + 45.0 + 50.0, 37.5, table_w, 100.0, 75.0)


box("C0_Floor", 300, 1500, -1, 1500, 3600, 2)
# strip A: stand-to-sit at 6 times + seated idle
a_times = [0.0, 0.45, 0.9, 1.35, 1.8, s2s.get_play_length()]
for i, t in enumerate(a_times):
    figure("A%d_StandToSit_%.2f" % (i, t), 0, i * 200.0, s2s, t)
    furniture("A%d" % i, 0, i * 200.0, 120.0)
figure("A6_SittingIdle_mid", 0, 6 * 200.0, idle, idle.get_play_length() * 0.5)
furniture("A6", 0, 6 * 200.0, 120.0)
# strip B: sit-to-stand
b_times = [0.0, 0.45, 0.9, 1.35, 1.8, s2u.get_play_length()]
for i, t in enumerate(b_times):
    figure("B%d_SitToStand_%.2f" % (i, t), 0, 1800.0 + i * 200.0, s2u, t)
    furniture("B%d" % i, 0, 1800.0 + i * 200.0, 120.0)
# live figure for the sequence
live = figure("Live_Manny", 600, 0, s2s, 0.0)
live.skeletal_mesh_component.set_animation_mode(unreal.AnimationMode.ANIMATION_CUSTOM_MODE)
box("Live_Stool", 600, -46.0, 22.0, 38.0, 38.0, 44.0)
box("Live_Table", 600, 95.0, 37.5, 300.0, 100.0, 75.0)
box("Live_Floor", 600, 100, -1, 400, 600, 2)

# lights
eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(-500, 0, 800), unreal.Rotator(0, -50, 20))
eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 600))
p("level actors: %d" % len(eas.get_all_level_actors()))

# Level Sequence
at = unreal.AssetToolsHelpers.get_asset_tools()
seq = at.create_asset("LS_C0_SeatPreview", DEST, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
seq.set_display_rate(unreal.FrameRate(30, 1))
binding = seq.add_possessable(live)
track = binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
frames = 0
for anim, reps in ((s2s, 1), (idle, 2), (s2u, 1)):
    n = unreal.AnimationLibrary.get_num_frames(anim)
    for _ in range(reps):
        sec = track.add_section()
        sec.set_range(frames, frames + n)
        params = sec.get_editor_property("params")
        params.set_editor_property("animation", anim)
        sec.set_editor_property("params", params)
        frames += n
seq.set_playback_start(0)
seq.set_playback_end(frames)
p("sequence length: %d frames (%.2f s)" % (frames, frames / 30.0))
unreal.EditorAssetLibrary.save_loaded_asset(seq)
try:
    lsa = eas.spawn_actor_from_class(unreal.LevelSequenceActor, unreal.Vector(0, 0, 0))
    lsa.set_sequence(seq)
    p("level sequence actor placed")
except Exception as ex:
    p("level sequence actor failed: %s" % ex)
p("saved level: %s" % les.save_current_level())

with open(unreal.Paths.project_saved_dir() + "C0_BuildPreview.txt", "w") as fh:
    fh.write("\n".join(out))
unreal.SystemLibrary.quit_editor()
