# Sector 01 Left Wing Floor 1 - navigation (M2.1A)

Status: **Static Recast navigation is baked into `L_S01_LW_F1_Greybox` and verified.** `RuntimeGeneration` is still the
engine default (Static); no project config was changed. Results: `S01_LW_F1_nav_report.txt`.

## Pipeline (run with the interactive editor CLOSED - it locks the level file)
1. `Tools/BuildFloor1Greybox.py` - regenerates geometry, signs, markers, lights, nav volume (invalidates baked nav).
2. `Tools/BakeNavigation.py` - builds Static navigation and saves the level. Headless note: a freshly loaded editor
   world holds an async-load navigation lock for ~80 ticks, so the script re-issues `RebuildNavigation` until a build
   starts. (`-run=ResavePackages -BuildNavigationData` does not work: the build is locked.)
3. `Tools/VerifyNavigation.py` - fresh process; persistence, marker reachability, NPC legs, secured spaces, coverage.
4. `Tools/VerifyNavigationPIE.py` - headless Play In Editor; navigation works in the PIE world.
Run each with `UnrealEditor-Cmd.exe CyberWarden.uproject -ExecutePythonScript="<abs path>" -unattended -nop4 -nosplash -NullRHI`.

## Settings
- NavMeshBoundsVolume tightened from extents 13000 x 10000 x 1200 to **5100 x 3100 x 600** centred (3800, 800, 450):
  building footprint (x -800..8400, y -1800..3400, z to 910) plus margin; about 63 tiles instead of about 520.
- Agent: engine defaults (radius 34, height 144, max slope 44, tile 1000). Player/NPC capsule is 35 x 90: use **34**
  for NPC capsules (M2.1B) so the agent radius matches the navmesh.
- Destination flags: markers carry `NavDest:Yes/No` tags (`marker_types` in the layout JSON). 97 yes, 11 no.
- New duty markers: `Work_Servery_S`, `Work_Servery_N`, `Work_Kitchen_Gap`, `DutyStart_Guard_Residential`
  (Post, z 330), `DutyStart_Guard_Roving` (hub).

## Areas to watch / no nav links needed
- No NavLinks, collision changes or alternative agent settings were needed: stairs (about 33 deg, 18 cm risers), the guard
  stair, walkway, Post door (200), cell doors (160) and Gate G1 (300) are all navigable.
- Kitchen interior has an isolated navmesh island behind the sealed door; it is unreachable (verified). Floor 2 exit
  and the outside of the intake door are off-mesh.
- The upper landing (z 500) is reachable; restricting prisoners from Zone C later needs a NavArea/filter (not M2.1).
- Coverage numbers below 100% (cells 75-83%, Post/alcove 68-75%, stair core 87%, cafeteria 88%) come from bunks, tables,
  rails and stair steps removed by agent-radius erosion and from the probe sampling at floor height; every marker in those
  rooms is reachable.
- Any builder re-run requires a re-bake (step 2).
