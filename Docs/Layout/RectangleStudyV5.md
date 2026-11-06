# Floor 1 Rectangle Study V5 (Sector 01 / Left Wing) - review map, PROVISIONAL

Separate map `/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_RectangleStudy_V5`, built from V4. The accepted M1 greybox and the V1-V4
studies (maps, layouts, scripts, materials) are not touched: the builder hashes them before/after, refuses to run against their
names, and creates only the new level plus new `MI_RS5_*` material instances.

**Status: authored and analytically validated, not yet play-tested in the editor.**

North in this map is +Y. The "NORTH prisoner stair" is `Stair_North` (y 2030..2270, signed "STAIRS UP (NORTH)"), its foot lobby is
x 4950..5600, y 2000..2300. (The screenshot with the labelled stairs did not arrive; orientation comes from the map data.)

| Item | Path |
|---|---|
| Layout input | `Docs/Layout/S01_LW_F1_RectangleStudy_V5.json` (same schema as V2-V4) |
| Geometry | `Content/Python/cw_rectstudy_v2.py` (`StudyV2`, unchanged) |
| V5 analysis | `Content/Python/cw_rectstudy_v5.py` (derived from `cw_rectstudy_v4.py`, unchanged) |
| Editor builder | `Tools/BuildRectangleStudyV5.py` |
| Standalone validator | `Tools/ValidateRectangleStudyV5.py` -> `Docs/Layout/S01_LW_F1_RectangleStudy_V5_report.txt` |
| Schematic renders (not editor captures) | `Tools/RenderRectangleStudyViews.py V5` -> `Docs/Layout/RectangleStudyV5_views/*.png` |

Build in the open editor (Cmd box): `py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Tools/BuildRectangleStudyV5.py"`.
Open the map and press Play: you start inside the relocated intake, facing south toward its exit.

## What changed from V4
**1. Intake relocated to the foot of the north stair; old opening closed**
- New intake room x 5000..6100, y 2300..2800 (1100 x 500), directly north of the north stair foot lobby, under the new north arm:
  sealed arrival door in the east wall (y 2550), small processing counter (300 x 70 x 105), waiting bench, floor walking line from the
  arrival door to the exit, exit sign, and a 400 cm **exit opening** (x 5150..5550) onto the lobby.
- Player start (5350, 2620), yaw -90: the exit is straight ahead, then the lobby, then the hall.
- The V4 east-wall intake is gone: its opening, side walls, counter, bench, markings and signs are removed and the hall east wall is
  solid again at that spot (a ray hits it at x 5585).
- The stair landing stays clear: the stair foot is at the landing's west end, the intake exit lands on its east half, a keep-clear
  floor marking and sign sit on the landing, and the landing opens to the hall over 600 cm.

**2. One connected, U-shaped guard suite (upper tier)**
- South arm = the existing office (x 2900..6100, y 0..500). East span = the lookout (x 5600..6100, y 500..2300). **North arm = new**
  (x 2900..6100, y 2300..2800, the same length and depth as the south arm), replacing upper cells U7-U9 (U1-U6 remain).
- Sections are joined by two open 400 cm passages (no doors), one deck tint on all three, a 600 cm window from the north arm onto
  the north walkway (like the office's), desks, lockers and a records table. The open side of the U faces the hall (west).
- The north arm sits directly above the intake (the intake footprint lies entirely inside the arm's footprint).
- The only opening from the prisoner side into the suite is still the office doorway (x 4000), the restricted boundary. The north
  arm has windows but no walkway door; staff reach it through the lookout.

**3. Unchanged:** both prisoner stairs (open) with their landings connected to the walkways and the crossover; the Sector Floor 2 secured
door (hall east wall, y 1750); the open hall under the crossover; kitchen, laundry, linen store, service hallway and cover.

## Verification from above (analytic, and the schematic renders)
Top-down plan of the upper tier (100 cm per character, north up; S = suite deck, w = prisoner walkway, X = crossover, c = cells,
. = open to the hall):

    y=2750  cSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS      north arm  (x 2900..6100)
    y=2250  wwwwwwwwwwwwwww             SSSSS      north walkway, then open hall side, then the lookout span (x 5600..6100)
    y=1950  ..XXX.......................SSSSS      crossover (X), hall below (.)
    y= 750  wwwwwwwwwwwwwww             SSSSS      south walkway
    y= 450  cSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS      south arm = office (x 2900..6100)

Arms identical, east ends flush, span joins the south arm's north edge to the north arm's south edge, 0 suite cells in the open side.
`V5_topdown_guard_suite_upper_tier.png` shows the same thing as a coloured plan (suite deck red, walkways blue, stairs orange).

## Analytic verification - 0 errors, 0 warnings
- Routes: all pass, including intake exit -> hall (R12), arrival door -> exit (R13), north stair foot -> hall without touching the intake
  (R15), **walk out of the intake, along the stair foot and climb the north stair to the upper walkway (R16, ends on z=390)**, north
  stair up past the north arm to the cells (R17), south stair past the office (R26), the whole suite walk south arm -> lookout ->
  north arm and back (R25: 770 / 458 / 717 samples in the three sections), service loop, kitchen, laundry, linen, crossover.
- Blocked: Floor 2 door, sealed arrival door, intake west wall, north lobby east wall, north arm from the walkway, the closed old
  intake site, edges, hatch. 52 reachability samples match (40 reachable, 12 closed); 0 unprotected drop edges.
- Intake: free radius 200 cm at the exit opening and along the exit lane, 165 cm at the start; camera arm behind the start 160 of
  200 cm free. North stair foot 427 cm from the exit centre, 870 cm walking from the start. Stair landing free radius 100 cm.
- From the intake start you see the lobby and the hall straight ahead and the Sector Floor 2 door sign; the **stair is not visible
  from inside the room** (the exit is on the room's south wall), but from the exit opening one step out the north stair foot and its
  side rail are visible, and from the hall the exit sign and the stair foot are both visible.
- Walkways keep 135-138 cm free radius in front of both arms and never enter them.

## Observations / limitations
- Not built or played in the editor. The renders are software renders of the generated boxes (flat shaded, no text, no lighting);
  the builder runs 27 engine line traces when you execute it.
- The intake exit lines up with the east service door: from the exit you can see about 44 m straight south through the hall and
  down the service hallway's east leg. The dog-leg still stops sight between the two service entrances.
- Floor-to-floor assumption as V1-V4 (upper deck z=390, roof 760-790).
