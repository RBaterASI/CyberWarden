# Board 10 spec + scripts: patched copies (Ricky's rulings)

Originals are untouched in `C:\Users\ricky\Downloads\` (`LeftWing_F1_spec.json`, `ue_build_from_spec.py`, `ue_validate_layout.py`, `BUILD_INSTRUCTIONS.md`).
This folder holds the patched copies. Counts: 83 rooms, 84 doors (D39 added), 7 windows, 4 stairs.

## Applied as ruled
| Item | Change |
|---|---|
| S3 | Footprint X 58.2-60.8, Y 14.0-18.4 (long axis N-S). Foot (lane A, west) and top (lane B, east) both at the north end. 1.5 m apron below D07, 1.6 m apron in front of D08. The upper-slab hole is only over this footprint, inside the lookout. |
| D37a | X 55-57.5 (clear of the hole). |
| S4 | Footprint X 57.2-60.8, Y 45.6-50.6. Foot north under D10 (1.6 m apron), top exits north into the break room, D11 enters over the 3.2 m west apron. |
| S2 | Y 15.6-17.4, X 8.8-15.8, top at X 8.8. D13 moved to Y 12-15. Mesh on both sides of S2 (Y 15.6 and Y 17.4, ground up). West void edge at X 8.8 is now Y 8.8-15.6. |
| C01 | Lower N block = 9 cells x 3.889 m, X 8-43, every door faces the hall (D01 spans recomputed). Utility X 1.8-8, Y 1.8-8, staff only, door D12a from the west chase. |
| U25 | Deleted. S1 widened to Y 6.6-8.8 (2.2 m). |
| Rails | 1.1 m rails on the open side of every staff flight (per step), on the landing sides, a solid divider between the two flights, and around both slab holes (the lane B top exit stays open). |
| Safety net | Built, no collision, translucent unlit material `M_Net_Translucent` (created on first run; falls back to the plain wall colour if material creation fails). |
| Goods lift | Room L33 in L31, X 50-53.4, Y 45-48.6, staff-only shaft (not walkable: `reach: false`), sealed placeholder door D39 (X 50.8-52.6, 2.1 m) in its north face toward the loading bay. |
| Validator | `blocked()` handles both return shapes: tuple -> its bool element, HitResult -> `blocking_hit`. Rooms with `reach: false` (the lift shaft) are skipped by the REACH check. |

## Added by me because the rulings imply it (please confirm)
- **S1 north side is caged** (`[45, 6.6, 52, 6.6]`, ground up): the stair's north side opens onto the 2 m landing strip (Y 4.6-6.6) under the arm; without a barrier a walker falls 0.7-1.8 m (offline edge check found 11 exposed cells).
- **West void edge south of S2** (`[8.8, 17.4, 8.8, 19.2]`): otherwise the west walkway opens onto the void pocket beside S2.
- The net is cut around the S2 body and the crossover deck; it is one translucent plane per piece.
- Lift door width 1.8 m (not in the rulings); sealed doors are now D03, D06 and D39.
- New helper functions in the build script: `build_staff_rails`, `build_net`, `net_material`. New wrapper `run_board10_build.py` (stages 1-3 in one command).

## Resolved after review
- **D22b moved to X 48.4-49.8 at Y 49.2** (the lift stays against the south wall; deliveries come in from the chase beside it). Offline: 91 of 91 door/window traces pass, 0 failed door lanes, 0 unprotected edges, all routes pass.
- Ricky approved the additions above (S1 north cage, west edge cage, net cut-outs, D39 as a sealed 1.8 m lift door).

## Round 3 (Ricky): corners, lighting, furniture
- **Wall corners:** `wall_line` extends each wall box by T/2 (0.15 m) at the start/end of the wall line (never at a door or window edge); the outer shell uses the same function. Offline corner-gap check: 43 gaps before, 0 after.
- **Lighting** is now built by `ue_build_from_spec.py` itself (`build_lighting`, folder `S01_LW_F1_Gen/Lighting`): Directional Light (pitch -50), Sky Light (real-time capture), Sky Atmosphere, Exponential Height Fog, an unbound Post Process Volume with manual exposure (exposure mode and light levels are constants at the top of the lighting block; see `tune_board10_lighting.py`), and a ceiling Point Light every 6 m in every room and corridor (just under the 2.7 / 3.6 m ceilings, the hall just under the roof line). The separate `add_board10_lighting.py` was removed. The roof is still off (`BUILD_ROOF = False`).
- **Furniture** is a `furniture` list in the spec (83 plain coloured collision boxes, folder `S01_LW_F1_Gen/Furniture`): a bed 2.0 x 0.9 x 0.5 and a toilet block 0.6 x 0.6 x 0.8 in each of the 30 cells (against the wall opposite the door; the last N and C cells have the bed turned along the west wall to stay 1 m from D31/D04), 8 seating tables 7 x 1.2 x 0.75 (X is the west end), kitchen cook line + serving counter + commissary counter (0.9 m), 8 washers (0.8 m cubes) along the laundry's south wall, control desk and 2 office desks (0.75 m), and the **review desk = the intake counter (X 56-59.6, Y 2.2-3.8, 1.0 m)** - my reading of "the review desk"; tell me if you meant another one.
- Offline re-run: 91 of 91 door/window traces, 0 failed door lanes, 0 unprotected edges, all rooms reachable, all routes pass, furniture within 1 m of a door opening: 0.

## Round 4 (stage 5 walkthrough fixes)
- **Navmesh first:** the validator now refuses to run while the NavMesh is building and warns if it cannot tell. Use Build > Build Paths and wait for the red "NAVMESH NEEDS TO BE REBUILT" message to go.
- **Zones:** `build_zones()` spawns one TriggerBox per spec room (84 rooms, both tiers) labelled `Zone_<id>_<name>`, tagged `Zone:<id>`, `ZoneName:<name>`, `Room:<id>`, folder `S01_LW_F1_Gen/Zones`. `clear_previous()` also deletes any actor tagged `Zone:*` / `Room:*` / `ZoneProvisional` outside the generated folder (the old M1 zone volumes). The HUD (`init_unreal.py`, `_tick_gen`) reads the spec rooms for this map: "ROOM-ID NAME". The validator has a ZONE row per room.
- **Roof:** `BUILD_ROOF = True`. The roof/ceiling slab is Z 7.5-7.8 over the whole footprint (upper tier and hall); the upper outer walls run to 7.8, so no sky shows.
- **Gameplay markers** (no collision unless noted, emissive): yellow 2 cm tiles for T01, T02, T03 and the two sally-port gate lines; red frames (0.1 m proud on both faces, 0.1 m wide) around every `staff` and `restricted` door (29 doors incl. D27 and the other staff links); yellow frames on D28a, D28b, D30a, D30b; a **solid closed red slab at D27** (actor `D27_Door_Closed`, folder `Doors_Toggle`, collision on) - `toggle_door.py` opens/closes it in the editor. The validator expects D27 blocked while the slab is closed (`"closed": true` in the spec).
- **Landmarks:** large "01" text on the showers' east wall (hall face, X 8.22, Y 17.4) plus a green emissive strip along that wall; the W07 lookout band is a bright emissive yellow strip on both faces of the wall above the window head.
- **Work corridor:** cart bay alcove (new room L34, opening D40) **on the north wall directly opposite the laundry door D19b, carved 1.2 m deep (clear) out of the kitchen** - see the note below; a ceiling lamp in a different emissive colour with a matching coloured point light at each of the 11 room doors (D18a-e, D19a-d, D21, D40); a name sign (dark plate + text) over each door on the corridor side.
- **Floor labels** rotated 180 deg (`Rotator(0, 90, 180)`).
- **Review camera:** motion blur off in the unbound post process volume. The spring-arm socket offset (0, +60, 0) is applied **to the PIE pawn at runtime by the HUD script**, for this map only; the character Blueprint asset is not changed (M1 and the other maps keep their camera). Say if you want it baked into the Blueprint instead.

### Needs your confirmation
- **Cart bay side:** you wrote "on the south side opposite the laundry door", but the laundry door D19b is on the corridor's *south* wall, so the only wall opposite it is the *north* wall. I put the bay there (carved from the kitchen, X 22.8-25.2). If you meant a bay on the south side next to the laundry door, tell me the X range.
- The 1.2 m depth is clear floor depth (wall-centre depth 1.5 m).

## Still conflicting
- None found offline (92 of 92 door/window traces, 0 failed door lanes, 0 unprotected edges, 0 corner gaps, no furniture within 1 m of a door, every room reachable, all routes pass, D27 slab blocks as intended). Engine-side untested: the translucent net and emissive materials, `RebuildNavigation`, `is_navigation_being_built`, the trace return shape, the post process / fog / sky setters, the spring-arm lookup, and the toggle script.
