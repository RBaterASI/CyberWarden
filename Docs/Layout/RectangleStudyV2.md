# Floor 1 Rectangle Study V2 (Sector 01 / Left Wing) - follows the user's upper-tier sketch, PROVISIONAL

Separate map `/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_RectangleStudy_V2`. The accepted M1 greybox and the V1 study map are
not touched (the builder hashes both before/after and refuses to run against their names). Sketch:
`C:/Users/ricky/Documents/Unreal Projects/ChatGPT Image Nov 5, 2026, 01_34_13 PM.jpg`.

**Status: authored and analytically validated, not yet play-tested in the editor.**

| Item | Path |
|---|---|
| Layout input | `Docs/Layout/S01_LW_F1_RectangleStudy_V2.json` |
| Geometry + analysis (pure Python) | `Content/Python/cw_rectstudy_v2.py` (builds on V1's `cw_rectstudy.py`, which is unchanged) |
| Editor builder | `Tools/BuildRectangleStudyV2.py` |
| Standalone validator | `Tools/ValidateRectangleStudyV2.py` -> `Docs/Layout/S01_LW_F1_RectangleStudy_V2_report.txt` |

Build in the open editor (Cmd box): `py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Tools/BuildRectangleStudyV2.py"`.
The script reads its sources from the project that holds the script and writes the level + new `MI_RS2_*` materials into the open
project. Then open the map and press Play; you start in the lower hall, west end, facing east toward the crossover.

## Layout (cm; +X east = right end of the sketch, +Y north = top; footprint 6100 x 2800 = 61 m x 28 m)
Upper tier (deck z=390) is a ring:
- **Cells** along the north row (U1-U9, x 500..4100), the south row (S1-S8, x 500..3700) and the west short end (W1-W4,
  y 500..2300); cells are 400 x 500 (west 450 x 500), door 160 x 260, ceiling 300. Colour band along each cell wall.
- **Inner walkway** 300 wide on the south, west and north sides, open balustrade (25 cm toe board + 110 cm top bar + posts)
  overlooking the hall; columns every 400 cm along the void edge.
- **One crossover** (300 wide, x 3050..3350, deck z=390) joining the south and north walkways; the walkway rails have gaps
  for it and both sides stay open to the hall; underside z=360 so the lower hall walks straight under it.
- **Two stairs near the east end**, one per long side, open to prisoners: 22 risers of 17.7 cm, run 28, 240 wide. They start
  at the walkway end (x=4334), run east along the walkway strip and land at x=4950 in a 635 x 300 lobby that is open to the
  hall (free radius 135 cm, 580-600 cm wide mouth).
- **Guard lookout** along the east short end (x 5600..6100, y 500..2300): a long window onto the hall (sill 50 cm), console
  along the window. **Guard office** in the south-east corner (x 3700..6100, y 0..500): the doorway (x 4000) opens onto the
  south walkway and is the **proposed restricted boundary** (red threshold line, yellow hatching, sign) - it is NOT blocked.
  The lookout is reached through the office (door at x 5850).

Lower tier:
- **Lower north cells** L1-L9 directly beneath the upper north row.
- **One continuous open hall** 4800 x 1200 (x 800..5600, y 800..2000): no partition; the crossover is overhead only.
- **South side:** open seating (3 x 5 tables with benches; two rows under the south walkway, one row out in the hall) from
  x 500..3000, and **one enclosed room** (x 3000..4334, y 0..800, purpose undecided) with a 500 cm opening onto the hall.
- Under-walkway aisles on the north and west; closed blocks everywhere else inside the same rectangle.

## Assumption to confirm: floor-to-floor
Same as V1: upper deck z=390, roof slab z 760-790, so Sector Floor 2 would sit above z ~800; this is not the 500 cm
floor-to-floor of `Floor2_Compatibility.md`.

## Analytic verification (no editor, no engine collision) - 0 errors, 0 warnings
- 10 capsule-walk routes pass: hall end to end; under the crossover; lower north cells; seating lanes and the enclosed room;
  south stair up; the full upper walkway ring; crossover south to north and back; north stair down; cells W/S/U; office to
  lookout and back. 8 must-block routes are blocked (east wall, four walkway/crossover edges, cell wall, lookout window, west wall).
- 28 reachability samples match (including closed blocks); 0 unprotected drop edges.
- From the lower-hall start: crossover, lookout window and sign, both stair rails, the office doorway and the room opening are
  in line of sight; upper north band 9/9, upper south band 8/8, lower north door faces 9/9.
- **From the lookout** (behind the console): 85% of the lower hall floor at head height; **seating 56% (standing) / 66% (seated)**:
  98% of the seating row out in the hall, only 37% of the seating under the south walkway (its deck hides it); all 9 + 9 + 8 + 4
  cell doors visible; enclosed room interior 18%.
- **From the crossover looking down:** 70% of the hall floor, 77% of the seating, 7/9 lower north doors, 9/9 upper north, 8/8 upper south, 4/4 west.
- Camera (estimate): arm shortened behind the player at only 1% of route samples. Tightest: a route start beside the enclosed-room wall (30 cm, an artefact of where the test route starts), the office doorway (90 cm) and the walkway end by the crossover (130 cm); the rest have 170+ cm of the 200 cm arm.

## Not verified / limitations
- Not built or played in the editor; no screenshots. Engine collision checks run when you execute the builder (13 line traces).
- Camera clearance is an estimate, not the engine's spring arm. Characters can jump rails; no fall protection beyond the rails.
- The lookout is guard-only by position only (reached through the office); only the office doorway is marked restricted.
