# Floor 1 Rectangle Study (Sector 01 / Left Wing) - alternative layout, PROVISIONAL

A playable layout study, **not** the accepted M1 map. One continuous rectangular footprint (64.0 m x 28.3 m) with a
central atrium hall; two tiers of cells on the north side; cafeteria, work area and a guard level on the south side.
Both tiers belong to Sector Floor 1.

**Status: authored and analytically validated, NOT yet built in the editor or play-tested.** The primary tree's module
DLL (`62D53AE0...`) is blocked by Smart App Control (see `Docs/NPC/ArtifactSigning_Setup.md`), so the editor could not be
launched. No DLL was rebuilt, replaced or restored.

| Item | Path |
|---|---|
| New map (created by the builder) | `/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_RectangleStudy` = `Content/CyberWarden/Maps/Sector01/L_S01_LW_F1_RectangleStudy.umap` |
| Layout input | `Docs/Layout/S01_LW_F1_RectangleStudy.json` |
| Geometry + validation (pure Python) | `Content/Python/cw_rectstudy.py` |
| Editor builder | `Tools/BuildRectangleStudy.py` |
| Standalone validator (no editor) | `Tools/ValidateRectangleStudy.py` -> `Docs/Layout/S01_LW_F1_RectangleStudy_report.txt` |
| Location HUD for the study | `Content/Python/init_unreal.py` (additive branch; M1 path unchanged) |

Untouched: `L_S01_LW_F1_Greybox.umap`, `S01_LW_F1.json`, `cw_layout.py`, `BP_CyberWardenCharacter`, the +/-90 degree
camera, `BP_ThirdPersonGameMode`, input mappings, every DLL. The study reuses the existing player setup through the same
GameMode override the M1 builder uses, and reuses the `M_GB_Lit` / `M_GB_Unlit` material parents (new `MI_RS_*` instances).

## Build, open, play
1. Resolve the DLL question first (see the report in the hand-over message).
2. Build: `powershell -File Tools\RunHeadless.ps1 -Script Tools\BuildRectangleStudy.py` (or Tools > Execute Python Script in
   the open editor). It creates the level, prints the analytic report plus engine line-trace spot checks, and records
   SHA-256 hashes proving the M1 map/layout/`cw_layout.py` did not change.
3. Open `L_S01_LW_F1_RectangleStudy` (Content Browser > CyberWarden > Maps > Sector01) and press **Play**
   (Play In Editor, default player start). You spawn at the intake at (500, 450) facing east, down the hall.

## Provisional dimensions (cm; +X down the hall, +Y north, Z up)
- Footprint x 0..6400, y -1200..1630. Hall (atrium) 900 wide x 5600 long, roof underside z=760. Upper tier deck z=390.
- **North side (left from intake):** lower aisle 280 wide x 360 high (open to the hall, columns every 400), 8 lower cells
  400 x 450 (door 160 x 260), upper walkway 280 deep above the aisle with open balustrade, 8 upper cells (ceiling 300),
  prisoner stair (22 risers of 17.7 cm, run 28, 220 wide) from a lobby at x 700..984 up to the walkway at x=1600.
  Colour bands (blue / light blue) run along both tiers so they read from the hall floor.
- **South side (right):** orientation room (x 0..1200), staff stair bay (door at x 1850), cafeteria and common seating
  (x 2116..3500, 6 tables with benches 50 cm so tables cannot be climbed), work area with service counter (x 3500..5300).
- **Guard level (z=390):** staff stair (260 wide) arrives on a 600-deep gallery that overlooks the hall; **lookout cabin**
  (500 x 260, projects over the hall, windows on three sides); guard office (1000 x 600, ceiling 300) north door from the
  gallery, east door onto the **authorized landing** (600 x 900, gold floor, red/yellow restricted-boundary strips at the
  door). Upper crossing (300 wide bridge, x 3700..4000) joins the north walkway to the landing. Roster on the desk.
- **Far end (x 5600):** secured gate (bars, 30 cm gaps) with a visible stair behind it: "SECTOR FLOOR 2 - SECURED STAIR".
- **Markings (no collision):** lime Rail track at z=690 from (2000,450) to (4800,450) with endpoint blocks, hangers and a
  dashed floor strip; CCTV-01 housing at the walkway/crossing junction (3850,1145) with a wireframe frustum
  (70 x 40 deg, 2200 range) aimed south over the crossing and landing; orange dashed guard route (staff door -> stair ->
  gallery -> office north door); six cover pieces (cabinet, pillar, 200 cm wall, locker, crates, partition).
- Colour key: orange intake, purple orientation, grey-blue hall, blue lower cells, light blue upper cells, green cafeteria,
  teal work, amber guard level, sky crossing, gold landing, red restricted office, crimson secured, lime rail, cyan CCTV.

## Assumption to confirm: floor-to-floor
The M1 notes (`Floor2_Compatibility.md`) use floor-to-floor 500 with a mezzanine at 330. A second *upper cell tier*
needs more height: here the upper deck is z=390, upper cell ceiling z=690 and the roof slab z 760-790, so Sector Floor 2
would sit around z ~800+. This study does not satisfy the 500 cm assumption; that file's keep-out void analysis does not
apply to it. Decide which floor height wins before adopting any of this.

## Analytic verification (no editor, no engine collision) - `Tools/ValidateRectangleStudy.py`
0 errors, 0 warnings. 13 capsule-walk routes pass (intake to every cell row, cafeteria, work counter, orientation, prisoner
stair, upper cells, crossing, landing, office and roster and back, staff stair, gallery, lookout cabin, cover run, hall
end); 8 must-block routes are blocked (gate, sealed door, five edge/wall cases, work roof); 22 reachability samples match
(including unreachable voids); 0 unprotected drop edges. From the intake start: 8/8 upper-tier bands and door tops, 6/8
upper door middles, 5/8 lower door faces, the lookout cabin, gallery balustrade, crossing rail, rail endpoints, CCTV
housing and the secured-gate sign are in line of sight. Lookout cabin sees 64% of hall floor at head height (the 36% it
cannot see is mostly the floor under and near the cabin, hidden by its sill and deck; cabin + upper walkway together 84%). Cover pieces create hiding cells for a standing player
from the guard-route, office-east-door and CCTV viewpoints. CCTV-01 covers 100% of the crossing and 98% of the landing.

These are geometric estimates. Camera clearance is an approximation of a 200 cm arm (not the engine spring arm); the
engine-side collision traces and everything visual still need the editor.

## Known limitations / open
- Not built, not opened, not play-tested; no screenshots yet.
- No navmesh (no AI in this study). Rail, CCTV, roster and restriction marks are layout props only.
- Lower-tier doors are partly hidden from the intake by the aisle columns (5/8); the landing rail is hidden behind the lookout cabin.
- Camera: tightest spots are the stair lobby corner, the staff-stair vestibule and the cabin interior; judge in PIE.
