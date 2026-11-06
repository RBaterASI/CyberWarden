# Floor 1 Rectangle Study V3 (Sector 01 / Left Wing) - V2 + kitchen, laundry and service hallway, PROVISIONAL

Separate map `/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_RectangleStudy_V3`. The accepted M1 greybox, the V1 study and the V2 study
(map, layout, scripts, materials) are not touched: the builder hashes them before/after, refuses to run against their names, and
creates only the new level plus new `MI_RS3_*` material instances.

**Status: authored and analytically validated, not yet play-tested in the editor.**

| Item | Path |
|---|---|
| Layout input | `Docs/Layout/S01_LW_F1_RectangleStudy_V3.json` (same schema as V2) |
| Geometry | `Content/Python/cw_rectstudy_v2.py` (`StudyV2`, unchanged) |
| V3 analysis | `Content/Python/cw_rectstudy_v3.py` |
| Editor builder | `Tools/BuildRectangleStudyV3.py` |
| Standalone validator | `Tools/ValidateRectangleStudyV3.py` -> `Docs/Layout/S01_LW_F1_RectangleStudy_V3_report.txt` |

Build in the open editor (Cmd box): `py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Tools/BuildRectangleStudyV3.py"`.
Then open the map and press Play; you start on the lower tier, west end of the hall, facing east toward the crossover.

## What changed from V2
Unchanged: upper tier (cell ring N/S/W, walkway ring, crossover, lookout, office with the doorway marked as the proposed
restricted boundary), both prisoner stairs (OPEN), lower north cell row, one continuous open hall, view up to the crossover.
The footprint widens on the service (south) side from 61 x 28 m to **61 x 51 m** (y -2300..2800); the upper tier is not extended there.

Lower tier, south side (behind the open seating):
- **Open seating** x 500..3300, y 0..800 (4 x 3 tables with benches; one row out in the hall, two under the south walkway).
- **Kitchen** (x 500..2500, y -1000..0) with a 1600 cm **serving hatch** and counter facing the seating, a hot line, an island and a
  prep bench; **pantry** (x 2500..3300) through a door from the kitchen only (shelving, a cooler in the kitchen); a **recessed
  back door** (240 x 120 niche, x=2000) onto the service hallway.
- **Service hallway** 360 wide (330 clear): west leg (x 0..500, N-S, entered by a staff door in the lower west aisle at y 1300),
  A behind the kitchen (y -1360..-1000), a **dog-leg** V (x 2940..3300) down to the east run B (y -1900..-1540), then the east
  leg E (x 5240..5600) north to a second staff door in the south stair lobby wall (x 5420, y 500). Two distinct hall
  connections, both turning immediately; the dog-leg stops sight between A and B.
- **Laundry** (x 500..2300, y -2300..-1360): recessed door (x=1400), 3 sorting tables with a 300 cm lane to the door, washer/dryer
  banks, 3 tall laundry carts. **Linen store** (x 2300..2940): door onto A, three staggered shelves forming a serpentine.
- **Cover / sight breaks:** 13 solid pieces >= 190 cm (carts in the hallway and rooms, lockers, shelving, cooler), 2 recessed
  door niches, wall corners at the dog-leg. Staff access is marked with yellow floor hatching and signs on all four service doors.
- **Sector Floor 2:** the only blocked route. A secured door (red/crimson panel, keypad, floor hatching, sign) on the lower hall's
  east wall at (5600, 1400); the player can walk right up to it. Floors 2 and 3 are not modelled.

## Analytic verification (no editor, no engine collision) - 0 errors, 0 warnings
- 17 capsule-walk routes pass: hall end to end; under the crossover; lower north cells; seating lanes and counter; **service loop
  (hall west aisle -> west leg -> A -> dog-leg -> east run -> east leg -> stair lobby -> hall) and its reverse**; kitchen and pantry;
  laundry; linen store; a cover dash along the east run; approach to the secured door; **south stair up, the whole upper walkway
  ring, crossover, north stair down**; upper cells; office to lookout and back.
- 10 must-block routes are blocked: the Floor 2 door, four walkway/crossover edges, a cell wall, the lookout window, the serving
  hatch, the pantry's hallway wall, and a straight run along hallway A into B.
- 42 reachability samples match (33 reachable, 9 closed masses); 0 unprotected drop edges.
- **Service hallway see-through:** west door <-> east door: not visible; from the west mouth neither the east run nor the east
  leg is visible; from the east mouth neither A nor the west leg is visible. Longest sightline inside the hallway: 3220 cm (leg A,
  not the whole route). The kitchen-hatch straight line stops at the hallway's south wall and never reaches the laundry.
- **Hiding** (guard watching from 40 positions along the hallway and just inside the room doors; standing player must be fully
  hidden): the 13 cover pieces add hiding cells in the pantry (+77), laundry (+25) and linen store (+91); 11 of 13 pieces create
  hiding cells from at least one position; standing in either recessed niche is visible from only 4 of 15 positions along the hall.
- **Clearance:** hallway corners 165 cm free radius, niches 105, pantry aisle 170, laundry door lane 119, linen serpentine 90.
  Tightest on the loop and rooms 70-95 cm (laundry cart/shelf spots, linen gaps). Camera arm shortened directly behind the player at
  2% of route samples (the linen/laundry rooms and the office doorway are the tightest).
- **Hall legibility:** from the start the crossover, both stairs, the lookout window, the office doorway, the serving-counter sign and
  the secured-door sign are in line of sight; upper tier bands 9/9 and 8/8; 88% of the hall void is walkable (the rest is seating).
- **Views:** lookout sees 85% of the hall floor, 59% of the seating standing / 66% seated (99% of the row out in the hall, 40% of the
  seating under the south walkway); crossover sees 69% of the hall and 62% / 59% of the seating.

## Not verified / limitations
- Not built or played in the editor; no screenshots. The builder runs 18 engine line traces when you execute it (V2's 13 matched).
- Doors are openings (no door panels); the "doors" and staff markings are layout elements only.
- Tables, island and sorting tables are <= 95 cm, so they do not hide a standing player; only the 13 tall pieces count as cover.
- Floor-to-floor assumption as V1/V2 (upper deck z=390, roof 760-790).
- The V2 report/doc remain valid for the unchanged upper tier.
