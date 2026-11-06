"""Make the navmesh finer so 1.0 m cell doors stay open for the 35 cm-radius agent (level-local setting; no layout change).

    py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Docs/Layout/LeftWingF1_Board10/set_navmesh_resolution.py"

Sets the RecastNavMesh actor in the open level: cell size 10 cm and cell height 5 cm (the defaults are coarser), and tries
agent max step height 45 cm to match the character. Logs which properties exist and their before/after values.
Then use Build > Build Paths, wait for it, and re-run ue_validate_layout.py.
If the log says a property is missing, set it by hand: select RecastNavMesh-Default > Details > Generation > Cell Size 10, Cell Height 5.
"""
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
navs = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.RecastNavMesh)
if not navs:
    raise SystemExit("[LW_F1] no RecastNavMesh in the level: run Build > Build Paths first")
WANT = (("cell_size", 10.0), ("cell_height", 5.0), ("agent_max_step_height", 45.0))
for nav in navs:
    for prop, val in WANT:
        try:
            before = nav.get_editor_property(prop)
            nav.set_editor_property(prop, val)
            unreal.log("[LW_F1] navmesh %s: %s -> %s" % (prop, before, nav.get_editor_property(prop)))
        except Exception as ex:
            unreal.log_warning("[LW_F1] navmesh %s: could not set (%s) - set it by hand in the Details panel" % (prop, ex))
unreal.log("[LW_F1] now Build > Build Paths, wait, then re-run ue_validate_layout.py")
