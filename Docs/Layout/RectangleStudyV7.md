# Floor 1 Rectangle Study V7 (Sector 01 / Left Wing) - confined layout, PROVISIONAL

Separate map `/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_RectangleStudy_V7`, built from the pasted **Greybox Build Sheet - confined layout**
(board 10 "Confined Layout" with board 11 back of house folded in; it replaces the board 07 sheet that V6 was built from). The accepted M1 greybox and the
V1-V6 studies are not touched: the builder hashes them before/after, refuses to run against their names, and creates only the new level plus new `MI_RS7_*` material instances.

**Status: authored and analytically validated (0 errors, 0 warnings), not yet built or play-tested in the editor.**

| Item | Path |
|---|---|
| Layout data | `Docs/Layout/S01_LW_F1_RectangleStudy_V7.json` (V2 schema plus `lines`, `meshes`, `nets`) |
| Geometry | `Content/Python/cw_rectstudy_v2.py` (adds an optional cell-number offset `num0`; V2-V6 unaffected) + `cw_rectstudy_v6.py` + `cw_rectstudy_v7.py` (`StudyV7`: mesh, net, V7 analysis) |
| Editor builder | `Tools/BuildRectangleStudyV7.py` |
| Standalone validator | `Tools/ValidateRectangleStudyV7.py` -> `Docs/Layout/S01_LW_F1_RectangleStudy_V7_report.txt` |
| Schematic renders (not editor captures) | `Tools/RenderRectangleStudyViews.py V7` -> `Docs/Layout/RectangleStudyV7_views/*.png` |

Build in the open editor (Cmd box): `py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Tools/BuildRectangleStudyV7.py"`, open the map, press Play. You spawn in the intake at
(59.4, 10.3) m facing west through D02 (yaw 180). Same frame as V6: sheet metres from the interior NW corner, +X east, +Y south, UE cm = metres x 100.

## What is built
- **61 x 51 m**, 3.6 m lower rooms, slab 3.6-3.9, upper floor 3.9, upper ceiling 7.5, roof slab 7.5-7.8; **2.7 m drop ceilings** (z 270-300, upper 660-690) over the staff chase, work corridor,
  service alley, rec corridor and staff spine.
- **Lower tier, 32 blocks (L01-L32)**: three-sided staff chase (north, west, south), utility, 9 cells C01-C09 (6.2 m deep), staff store, NE landing, 46 x 12 m hall, showers behind the green
  "01" wall, intake, vestibule, guard post, staff room, SE stair block, water heater, shower lockers, service alley, commissary, seating (8 tables, counters), the U-shaped work corridor with
  clock-ins at both ends, walk-in, kitchen, dish pit, waste, dry store, laundry (chute outlet X 31 / Y 41), linen, maintenance, loading bay (sealed goods-lift volume), plant.
- **Upper tier, 24 blocks (U01-U24)**: staff chase on three sides feeding the guard suite, N cells N01-N07, walkways 2.2 m, library, hall void 45.2 x 10.4 m, 2 m crossover, guard suite
  (north arm over the intake, lookout, office), S block S01-S07 and W block W01-W07 back to back, sally port, rec corridor 2.6 m, rec room, fitness, workshop (chute inlet), staff spine,
  control, kit and armoury, break room. **30 cells** (9 + 7 + 7 + 7).
- **Confinement**: full-height mesh (collidable 6 cm bars, 54 cm gaps, see-through) on every walkway, crossover and prisoner-stair edge up to the 7.5 m ceiling; a safety net at z 3.6 across the void
  (visual only, no collision). The builder sets the mesh and net to **ignore the camera collision channel** (the character and camera are not modified).
- **4 stairs**: S1/S2 prisoner stairs 1.8 m wide (26 risers, 29 deg), S3/S4 staff switchbacks. Doors D01-D37, windows W01-W08 (W08 optional, not built), triggers T01-T07, floor guide line.
  **Sealed: D03 (arrival) and D06 (secured door to Floor 2) only**, plus the sealed goods-lift volume. Scheduled gates (D28 sally port, D30 walkway block gates) are drawn with yellow strips and are **open** in the greybox.
- Colour key, wall bands (blue N / teal S / green rec wing and W block), staff doors (dark red flush strips, light red links), status lights, signs, HUD location text (additive `init_unreal.py` branch).

## Deviations and judgement calls (please check these)
1. **Showers**: Y 9.8-20 (sheet Y 8-20). With the sheet's showers touching the cell fronts, cell C01 opened into the showers; Y 8-9.8 is now a 1.8 m bay corridor in front of C01 that opens to the hall.
2. **S2 moved north 0.5 m** (Y 16.9-18.7, sheet 17.4-19.2): at the sheet position only 65 cm remains between the stair and the Y 20 wall, so D15 (hall -> service alley) could not be reached.
3. **S3 moved 0.6 m north** (Y 16.6-19.2, sheet 17.2-19.8, which ran under the lookout/office wall) with its foot at the west end (the sheet's footprint leaves no apron at the east end); **S4 moved 0.4 m south** (Y 45.0-50.8) for an 0.85 m apron under D10.
4. **D08 (vestibule -> guard post) moved to X 54.6-55.8** (sheet X 59-60.2): that span opens onto the S3 landing.
5. **D37a (office -> lookout) moved to X 54.4-56.0** (sheet X 56.5-59.5): it opened onto the S3 hole. D37b (lookout -> north arm) is as in the sheet.
6. **Goods lift volume moved 0.6 m north** (Y 44.4-48.0, sheet 45-48.6) so door D22b (loading bay -> south chase) has a lane.
7. **Commissary is a closed room**: the sheet gives it a counter window only, no door.
8. **Tables**: "at X 18, 27, 36, 45" is read as the west end of each 7 m table (centred, the first table would cross the commissary wall); benches on the outer side only, 50 cm high.
9. **Vent crawl T07 and the optional W08 grille are not built** (a marker and a strip only); the capsule cannot crawl.
10. Gaps: rooms the sheet lists with 0.2-0.3 m gaps share one wall in the gap; the east work-corridor leg stops 0.15 m short of the staff-room wall so window W02 sees down the corridor.
11. Added by me (the sheet leaves them open): all furniture and cover pieces, kitchen hatch X 24-34, 100 cm cell doors, amber/cyan status-light semantics, neutral room fill lights (the sheet says lighting is left out; unlit greybox is not reviewable).
12. **The sheet asks for a 2 m camera arm and a narrower FOV in corridors**: that is character/camera configuration, which this study does not change. 13% of route samples have the arm shortened behind the player.

## Analytic verification - 0 errors, 0 warnings (offline; no editor)
- 32 walkthrough routes pass (start down the hall; guide line to S1 and up; S2 up; cells via the bay corridor; showers and lockers; service alley -> clock-in -> work corridor -> east leg -> seating;
  seating lanes; hatch lane; walk-in, kitchen, dish pit, waste; dry store, laundry, linen, maintenance; loading bay; all three chases; every west-chase door; the east column door to door; **S3 and S4 up to z 390**;
  every walkway, N/S/W cells, library, crossover, sally port, rec corridor and rooms, office door, spine and every room off it, office -> lookout -> north arm -> north chase). 20 blocked-route checks pass.
- 70 reachability samples match; **0 unprotected drop edges**; every block has reachable floor except the commissary.
- **Staff network**: a flood restricted to guard/staff/intake rooms reaches all 23 staff/guard blocks on both tiers (S3/S4 link the tiers); with the west chase removed, the south chases and spine are still reached
  through the east column, so the loop is closed on the east as the sheet describes.
- Clear widths (wall/mesh face to face): walkways 1.90-1.96 m, crossover 1.82, S1 1.86, rec corridor 2.30, sally port 1.70, work corridor / alley / chase 1.50, spine 1.90.
- Spawn: D02, the hall's long axis to the "01" wall, the S1 first step and the crossover underside are visible; D06 is framed from the crossover; W02 gives a 46 m sightline down the work corridor; the guard post sees all of the seating.
- T06 lookout blind band: not blind with the crossover as specified (same finding as V6; a deeper crossover fascia would create it).
- Builder dry-run on a mock `unreal` module passes (1061 mesh actors, 80 signs, 18 markers, 200 lights); the builder also runs 29 engine line traces when you execute it.

## Notes
- Not built or played in the editor. The renders are flat-shaded software renders of the generated boxes (no text, no lighting), not editor captures.
- The primary-tree DLL is still blocked by Smart App Control; the map is built into whichever project is open (C2Build here).
- If the HUD shows the M1 text again, restart the editor (the C2Build `init_unreal.py` now has the study branch).
