# Cyber Warden — S01 Left Wing Floor 1: greybox build brief

Paste this whole file to your coding agent along with the three files beside it.

## Your job

Build the Sector 01 Left Wing Floor 1 greybox in Unreal Engine 5.8 (project `CyberWarden`) exactly as described in `LeftWing_F1_spec.json`. **Take your time. Correctness beats speed.** Work in stages, verify each stage before moving on, and never mark a stage done while any check fails.

## Files

| File | What it is |
| --- | --- |
| `LeftWing_F1_spec.json` | The single source of truth: 83 rooms, 83 doors, 7 windows, 4 stairs, walkway mesh edges, spawn, guide line, triggers, colours |
| `ue_build_from_spec.py` | UE Python script that generates the whole greybox from the spec |
| `ue_validate_layout.py` | UE Python script that checks every door, window and room against the spec and writes a report |

## Hard rules

1. **Do not place or edit layout geometry by hand.** All geometry comes from the spec through `ue_build_from_spec.py`. If something is wrong, fix the spec or the script and regenerate.
2. **Do not invent rooms, doors or sizes.** If the spec looks wrong or contradicts itself, stop and list the problem for Ricky instead of guessing.
3. **Every door is a full-height floor-level opening** cut through every wall segment on its line. A door is never a window. Only `sealed` doors (D03 and D06) are blocked, by a maroon block.
4. **Windows** keep wall below the sill and above the head. You can see through them but not walk through.
5. **Coordinates:** plan metres, X east, Y south, Z up. UE = metres × 100 (cm). The origin is the interior north-west corner. Don't mirror anything.
6. Build into a **fresh level** (for example `L_S01_LW_F1_Gen`) with sky and lighting only, so old hand-built pieces can't hide errors.

## Stages

Do them in order. After each stage, run the listed check and fix every failure before continuing.

1. **Set up.** Enable the Python Editor Script Plugin. Create the fresh level. Put all three files in one folder.
2. **First build.** Run `py "<folder>/ue_build_from_spec.py"` from the Output Log (Cmd → Python). Fix any Python errors (UE API names can differ slightly between versions). Expected result: everything sits under the outliner folder `S01_LW_F1_Gen`, with no errors in the log.
3. **Openings check.** Build Paths, then run `py "<folder>/ue_validate_layout.py"`. Open `Saved/LW_F1_validation.md`. Every DOOR and WINDOW row must be PASS. A failing door means a wall segment wasn't cut: fix the script's opening logic, regenerate and re-run.
4. **Reachability check.** Every REACH row must be PASS. A failing room means it can't be walked to from the spawn. Find out why (a missing doorway, a stair that doesn't meet its landing, a NavMesh gap) and fix it.
5. **Walkthrough screenshots.** In PIE, capture these six views and save them to `Saved/Screenshots/LW_F1/`:
    1. the spawn view facing west
    2. the hall from the crossover looking east
    3. the SW corner, showing the showers doorway in the "01" wall
    4. the sally port from the south walkway
    5. the back-of-house work corridor from the east clock-in
    6. the north walkway from the top of S1
6. **Report back to Ricky** with the validation summary (failures must be 0), the six screenshots, and a list of anything you changed in the spec or scripts and why.

## Known details to get right

- **Showers (L09):** the entrance is D13 in the "01" wall at X 8, Y 12.5–15.5. The lockers (L16) open into the showers through D14, a 2 m floor-level doorway, not a window.
- **Commissary (L18):** prisoners use only the counter window W03. Staff enter through D38 from the service alley.
- **Upper walkways** are 2.2 m wide and cantilever 0.8 m over the hall. Full-height mesh bars on the void edges use camera-ignore collision.
- **Stairs S1 and S2** are 1.8 m wide straight runs. **S3 and S4** are switchbacks. The upper slab must have openings over S3 and S4.
- **Every cell door** opens onto a walkway or corridor, never through another room.
- **The staff chase** runs north, west and south only. The east side is the chain of guard rooms linked door to door.

## Done means

- The validation report shows 0 failures.
- The six screenshots match the plan (board 10).
- No hand-placed layout geometry remains.
