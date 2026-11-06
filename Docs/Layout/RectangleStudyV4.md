# Floor 1 Rectangle Study V4 (Sector 01 / Left Wing) - review map, PROVISIONAL

Separate map `/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_RectangleStudy_V4` (the brief did not name it; V4 follows V3).
The accepted M1 greybox and the V1, V2 and V3 studies (maps, layouts, scripts, materials) are not touched: the builder hashes them
before/after, refuses to run against their names, and creates only the new level plus new `MI_RS4_*` material instances.

**Status: authored and analytically validated, not yet play-tested in the editor.**

The corner in the brief was identified from the editor's auto-screenshot of the last session (the attachment itself did not
arrive): the player stands at the east end of the hall facing the lookout wall (window + sign) with the orange stair on the
right. Facing east, right is south, so it is the **south-east corner**: the south stair, the lookout wall and the guard office behind it.

| Item | Path |
|---|---|
| Layout input | `Docs/Layout/S01_LW_F1_RectangleStudy_V4.json` (same schema as V2/V3) |
| Geometry | `Content/Python/cw_rectstudy_v2.py` (`StudyV2`, unchanged) |
| V4 analysis | `Content/Python/cw_rectstudy_v4.py` (derived from `cw_rectstudy_v3.py`, which is unchanged) |
| Editor builder | `Tools/BuildRectangleStudyV4.py` |
| Standalone validator | `Tools/ValidateRectangleStudyV4.py` -> `Docs/Layout/S01_LW_F1_RectangleStudy_V4_report.txt` |

Build in the open editor (Cmd box): `py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Tools/BuildRectangleStudyV4.py"`.
Open the map and press Play: you start inside the intake, facing west toward the exit into the hall.

## What changed from V3
**Upper tier**
- The guard office now runs from the lookout end west along the south side: x 2900..6100 (3200 x 500, was 2400 x 500). It replaced
  upper cells S7 and S8 (S1-S6 remain). Two more desks, staff lockers and a briefing table.
- Office and lookout are one staff area: an **open 400 cm passage** (no door) joins them, one floor tint covers both decks, signs
  read "GUARD OFFICE + LOOKOUT (ONE STAFF AREA)", and a 600 cm window looks from the office onto the prisoner walkway.
- The prisoner walkway is untouched and continuous: south stair head (x 4334) -> in front of the office -> past the crossover
  junction -> cells S1-S6 -> west walkway -> north walkway. The **restricted boundary is the office doorway** (x 4000): a red threshold
  line and yellow hatching on both sides, the doorway is open and prisoners pass on the walkway.

**Lower tier**
- **New Arrival intake** (x 5600..6100, y 900..1500, under the lookout deck), recessed 500 cm into the hall's east wall just north
  of the south stair foot lobby: a sealed **arrival door** in the east wall, a small **processing counter** (70 x 270 x 105), a waiting
  bench, floor lines, and a **400 cm exit opening** into the hall. The east wall plus a 100 cm wall return separate it from the stair
  lobby, so stair traffic never goes through processing.
- The Sector Floor 2 secured door moved north on the hall east wall to y 1750 (it was at y 1400, where the intake now is). It is
  still the only blocked route to another floor, with hatching, keypad and signs.

Unchanged: both prisoner stairs (open), the crossover, the continuous open hall, the lower cell row, seating, kitchen, pantry,
laundry, linen store and the service hallway with its dog-leg and two hall connections, the cover pieces, the recessed doors.

## Analytic verification (no editor, no engine collision) - 0 errors, 0 warnings
- 22 capsule-walk routes pass, including: **intake exit to the hall**, arrival door to exit, stair foot lobby to the hall (never touches
  the intake), the service loop both ways, kitchen/pantry, laundry, linen store, hall end to end, under the crossover, **south stair
  up -> walkway past the office -> cells S1-S6**, walkway to the crossover from the stair, north stair down, office and lookout.
- 13 must-block routes are blocked (Floor 2 door, sealed arrival door, stair lobby into the intake, intake south wall, edges, hatch...).
- 48 reachability samples match (38 reachable, 10 closed); 0 unprotected drop edges.
- **Staff area:** continuous office-to-lookout walk; a guard at the passage sees down into the office and one in the office sees up
  the lookout; office window lets guard and walkway see each other. In front of the office doorway the walkway has 138 cm free radius
  and never enters the office (lowest walkway y = 650).
- **Intake:** start valid; exit 180 cm free radius at the opening, 130 cm along the exit lane; 130 cm at the start; east wall is 185
  cm behind the start (camera arm 180 of 200 free). From the intake start you can see: the hall beyond the exit, the south stair
  rail and the stair foot lobby. **Not visible from inside the intake:** the lookout window and sign (above and behind the exit wall),
  the north stair, the crossover. From the exit threshold (one step out) the south stair, the lookout window and sign and the secured
  door sign are visible; from the hall just outside, looking back east, the lookout and the intake exit sign are visible.
- Hall, crossover and service checks from V3 still pass from the old hall viewpoint (1100,1400): crossover, both stairs, lookout
  window, office doorway and secured-door sign in line of sight; service hallway still cannot be seen straight through; 11 of 13
  cover pieces hide a standing player; seating coverage from the lookout 59% standing / 66% seated.

## Not verified / limitations
- Not built or played in the editor; no screenshots. The builder runs 26 engine line traces when you execute it (V2's 13 matched).
- The lookout is intentionally not visible from inside the intake (see above); if you want it in the intake's first view, the intake
  exit would have to move or face along the wall - say so after the walkthrough.
- Doors are openings (no panels); the arrival door is a sealed panel like M1's arrival door.
- Floor-to-floor assumption as V1-V3 (upper deck z=390, roof 760-790).
