# Floor 1 Rectangle Study V6 (Sector 01 / Left Wing) - built from the Greybox Build Sheet, PROVISIONAL

Separate map `/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_RectangleStudy_V6`, built from the pasted **Left Wing F1 - Greybox Build Sheet
(Nov 6, 2026)** and plan board **07 - revised greybox plan v2**. Where the two disagree the sheet wins (as the sheet says). The accepted
M1 greybox and the V1-V5 studies (maps, layouts, scripts, materials) are not touched: the builder hashes them before/after, refuses to run
against their names, and creates only the new level plus new `MI_RS6_*` material instances.

**Status: authored and analytically validated (0 errors, 0 warnings), not yet built or play-tested in the editor.**

| Item | Path |
|---|---|
| Layout data | `Docs/Layout/S01_LW_F1_RectangleStudy_V6.json` (same schema as V2-V5, plus `lines`) |
| Geometry | `Content/Python/cw_rectstudy_v2.py` (`StudyV2`, unchanged) + `Content/Python/cw_rectstudy_v6.py` (`StudyV6`, V6 analysis) |
| Editor builder | `Tools/BuildRectangleStudyV6.py` |
| Standalone validator | `Tools/ValidateRectangleStudyV6.py` -> `Docs/Layout/S01_LW_F1_RectangleStudy_V6_report.txt` |
| Schematic renders (not editor captures) | `Tools/RenderRectangleStudyViews.py V6` -> `Docs/Layout/RectangleStudyV6_views/*.png` |

Build in the open editor (Cmd box): `py "C:/Users/ricky/Documents/Unreal Projects/CyberWarden/Tools/BuildRectangleStudyV6.py"`, open the map,
press Play: you spawn in the intake at (59.4, 10.3) m facing west through D02 (UE yaw 180), existing controller and +-90 deg camera orbit.

## Coordinate frame (different from V1-V5)
Sheet metres from the interior NW corner: **+X east, +Y south**, UE X = X x 100, UE Y = Y x 100, Z up (UE's own left-handed frame, no mirroring).
In the editor's top view X runs right and Y runs *down*, so the map reads exactly like board 07 without flipping. V1-V5 labelled +Y "north",
which is mirrored N-S against the editor's top view; V6 does not do that (V5's `RenderRectangleStudyViews` images used the same +Y-up convention).
Heights: ground 0, lower ceiling 3.6, slab 3.6-3.9, upper floor 3.9, upper ceiling 7.5, roof slab 7.5-7.8 (V1-V5 used 7.6/7.9).

## What is built (from the sheet)
- **Footprint** 61 x 51 m, exterior walls 0.3 m on all sides, roof slab.
- **Lower tier, 22 blocks L01-L22**: north staff chase, utility, 9 cells C01-C09 (4.333 x 5.6 m, doors on the south face), staff store, NE stair foot landing,
  46 x 12 m double-height hall, showers, intake (counter X 56-59.6 / Y 2.2-3.8, 1.0 m high), vestibule, east staff corridor, open seating (8 tables 7 x 1.2 m
  at X 18/27/36/45, Y 23.2/25.6), guard post, kitchen with serving hatch, pantry, laundry, linen store, SE staff stair block, staff room, three-leg dog-leg service
  hallway, plant.
- **Upper tier, 21 blocks U01-U21**: north cells N01-N08, guard suite (north arm over the intake + lookout east span + office south arm, joined by two open 3 m passages),
  library, north/west/south walkways, crossover (X 29.3-32.7), rec gate passage, rec corridor, west link, rec room, fitness, workshop, south corridor, 8 W cells, south staff chase,
  staff spine, control, kit and armoury, break room. **33 cells total** (9 + 24).
- **4 stairs** (15 cm risers): S1 NE and S2 SW prisoner stairs (26 risers, straight 7 m runs, rise west, rails on the void sides), S3 vestibule and S4 SE staff
  switchbacks. Upper slab cut over S3/S4; S1/S2 sit in the void.
- **34 doors/openings D01-D34** with the sheet's positions and types; only **D03 (arrival door) and D07 (secured door to Floor 2) are blocked** (sealed panels,
  hatch markings, signs). Staff doors get dark-red floor strips. **Windows W01-W05** are real wall cut-outs at the sheet's sills/heads; W05 has the lit strip along its head.
- **Triggers/markers**: T01 office strip, T02/T03 service-entrance strips, T04 rec gate, T05 reference point, floor guide line through the sheet's five points ending on the first step of S1.
- Colour key as in the sheet (cells blue, walkways light blue, stairs orange, crossover purple, guard red, staff dark red, boundary yellow, windows bright yellow, sealed maroon,
  destinations green, job duties ochre). Signs on every room; HUD location text works for V6 (additive branch in `init_unreal.py`).

## Deviations and judgement calls (please check these)
1. **Showers north wall at Y 10, not Y 9.** With Y 9 the door of cell C01 (X 6.17) opens onto a 70 cm slot between its wall and the showers - a 68 cm capsule cannot use it.
2. **S3/S4 staff stairs changed to be enterable.** The sheet's footprints run wall to wall, so the foot of the first flight sits inside the wall and cannot be approached along the
   stair. S3: flights now start 0.9 m from the vestibule's east wall (apron) with a 19 cm tread (sheet 26.7), landing 0.9 m; S4: footprint moved 0.35 m south (Y 44.95-50.75)
   to leave an 0.8 m apron. Both are steep (about 38 deg for S3). Treads/footprints can be restored if you give the stairs more room.
3. **D16 (service hallway -> SE stair block) opens onto a 45 cm gap** beside S4 (the sheet puts S4 at X 54.6, 0.6 m from the wall), so it is effectively blocked. D17 (staff room link) works.
4. **Rec gate D24 is open in the greybox** so the south wing can be walked from the prisoner side; the T04 schedule is not simulated. (The wing is also reachable through the staff doors.)
5. **Crossover has no deeper fascia, so the T05 "lookout blind band" is not blind**: analytic sightlines from the lookout see 100% of the band at knee height (79% of the rest of the hall).
   The sheet's "solid rails" would not change that; a hanging fascia under the crossover would. Left as written.
6. **0.2-0.3 m gaps in the sheet** (X 8.0/8.2, Y 36.0/36.3, 45.4/46.2) are closed with a wall in the gap; the pantry/laundry/linen doors at Y 45.4 are paired with openings at Y 46.2 so
   they read as recessed doors.
7. **Unassigned strips filled solid**: X 10.8-14 and the mirror X 48-51.2 beside the kitchen block, and the 2.2 m south margin. The plant has no door in the sheet, so it is a closed shell.
8. Items the sheet leaves open, chosen by me: kitchen hatch X 20-42 (sill 1.05, head 2.4), bench height 50 cm on the *outer* side of each table only (a bench on the inner side would close the 1.2 m gap),
   serving counter 45 cm deep, furniture and cover pieces in the back-of-house rooms, 100 cm cell doors, 210 cm doors, **amber/cyan status lights** (amber at restricted/violation boundaries,
   cyan at D02 and the stair feet - semantics assumed), and **neutral room fill lights** (the sheet leaves lighting out, but unlit greybox is not reviewable).
9. **Library is its own room (changed after your first review).** The sheet's library (X 0-4.6, Y 4.6-23.4) made cells N01 and S01 open into it. It is now X 0-4.6, Y 8-20 with its own walls; the north and south walkways run on to X 0, so N01 and S01 open onto them. The library is entered only from the west walkway (D21).
10. **W06 (optional floor grille over the intake) is not built.** Doors are openings only (no leaves) apart from the sealed D03/D07 panels.

## Analytic verification - 0 errors, 0 warnings (offline; no editor)
- 38 walkthrough routes pass (start down the hall, guide line to S1 and up, S2 up, all lower cells, showers, seating lanes, serving counter, service hallway end to end, pantry/kitchen, laundry, linen,
  staff store/chase/utility, east staff corridor and every door off it, **S3 and S4 up to z 390**, all three upper walkways, crossover, N/S/W cells, library, rec gate -> rec corridor -> west link -> south corridor,
  rec room/fitness/workshop, office door, spine and every room off it, office -> lookout -> north arm, down S1 to the intake). 22 blocked-route checks pass (D03, D07, rails, windows, hatch, plant, solid fill...).
- 66 reachability samples match (56 reachable, 10 closed); **0 unprotected drop edges**; every sheet block has reachable floor except the closed plant.
- **Staff network**: a flood restricted to guard/staff/intake rooms from the intake reaches all 18 staff/guard blocks on both tiers (S3/S4 link the tiers) without touching a prisoner room.
- First ten seconds: from the spawn D02, the hall's long axis, the NE stair first step and the crossover underside are visible; D07 is framed from the crossover; the camera arm behind the spawn has
  140 of 200 cm (the exterior wall is 145 cm behind the start).
- Camera arm along all routes: 10% of samples have the arm shortened directly behind the player (cells, narrow service legs, staff stairs).
- Builder dry-run on a mock `unreal` module passes (829 mesh actors, 76 signs, 14 markers, 175 lights); the builder also runs 26 engine line traces when you execute it.

## Notes
- HUD: the location text needs the study branch of `Content/Python/init_unreal.py`; the C2Build copy was the old M1-only version, so it was replaced (original kept as `init_unreal.py.bak_before_study_hud`). It reads the layout from the open project or the sibling `CyberWarden` project. Restart the editor to load it.
- Built once in the C2Build editor; 4 engine-trace failures were mistakes in my test rays (too short or aligned with a door), fixed in the builder.
- Not played in the editor by me. `Docs/Layout/RectangleStudyV6_views/` holds flat-shaded software renders of the generated boxes (no sign text, no lighting), not editor captures.
- The primary-tree DLL is still blocked by Smart App Control; the map is built into whichever project is open (the C2Build worktree in this setup), same as V2-V5.
