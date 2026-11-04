# M2.3 Stage C2 - QUI01 seated on a physical stool (final approach + stool)

Branch `m2-3-activity-foundation` (Stage C1: `6e5116a`). **Closed: human visual acceptance recorded (2026-11-04).** C2 makes the prototype seat `Seat_Table_1_5` real: QUI01 walks to it with the
routine's Move To, takes a short precise **final approach** to the exact standing point, turns toward the table, sits on a visible **stool**, stays seated through the meal, stands up when the
schedule changes and walks away. It adds one native phase to the activity component, data for one seat point, one prop and the tools and tests that prove it.

**Not changed:** M1 geometry, tables and markers (the seat marker `Seat_Table_1_5` stays at (6150, -5, 12)), the navigation mesh and navigation settings, `ST_NPCRoutine` and every other StateTree,
prisoner schedules, the other NPCs' activity assignments, the player / camera / input / GameMode, `ABP_PrisonNPC`, the seated animations. No animation or furniture polish was done (not part of the greybox milestone).

## 1. Why a final approach: what the routine's Move To really leaves
Phase 1 measurement (real StateTree, five arrivals): Move To (radius 10, stop on overlap) leaves QUI01 **40-47 cm** from the marker, in a direction that depends on where it came from (49 cm of spread in X, 26 cm
in Y), so the seated pelvis ended 107-134 cm from the table edge instead of the planned 88 cm. A fixed stool cannot be matched to that. The approved fix is an opt-in per-point final walk, not a teleport, snap or slide.

## 2. Native change (`UPrisonActivityComponent`)
New state `Approaching`, active only for points with `bFinalApproach`:
- One ordinary AI move request to the exact marker (goal projected on the navmesh, pathfinding, no partial path, **no agent or goal radius in the reach test**, acceptance radius `FinalApproachAcceptCm` from data).
  Normal navigation, collision, avoidance and locomotion animation. Movement is **not** held during the approach; the component only ever touches its own request.
- On arrival the capsule is held and the position is confirmed within `FinalApproachToleranceCm`; only then does the normal Aligning -> Entering -> Performing lifecycle start. An NPC already within tolerance does not walk ("already there").
- Bounds: `FinalApproachMaxDistanceCm` (a request from farther away is refused, no lockout), `FinalApproachTimeoutSeconds`.
- **Failure** (timeout, blocked path, left the bound, stopped outside the tolerance): the NPC stays standing, `LastFailureReason` and `LastApproachResult` say why, the point is locked out for `ApproachRetryLockoutSeconds` (120 s).
- **Cancel** (release, abort, another point, a competing move request such as the routine's own Move To) is not a failure: the component drops only its own request, no lockout.
- Diagnostics: `ApproachStartCount/SuccessCount/FailCount/CancelCount`, `ApproachLockoutRefusals`, `LastApproachStartCm/EndCm/Seconds/TravelCm`, `LastApproachResult`.
- Pure helpers in `PrisonActivityMath` (`ApproachInReach/Confirmed/TimedOut/LockedOut`); data fields and validation in `PrisonActivityData`.
Native defaults are unchanged (accept 3 cm, tolerance 5 cm, max 80 cm, timeout 3 s, lockout 120 s); the seat point overrides the first two in data.

## 3. Seat point data (frozen)
`Docs/Layout/S01_LW_F1_activities.json`, regenerated into `DA_S01_LW_F1_Activities` with `Tools/ConfigureActivities.py`:

| Field | Value |
|---|---|
| marker / activity | `Seat_Table_1_5` / `SeatedIdle` |
| facing | yaw -90 (toward the table), capacity 1, arrival tolerance 60 cm |
| `final_approach.accept_cm` | **1.0** |
| `final_approach.tolerance_cm` | **7.0** |
| `final_approach.max_distance_cm` / `timeout_seconds` | 80 / 3.0 |

`Rec_TV` (WatchTV) is unchanged and has no final approach. Only the seat has it enabled.

## 4. What the measurements showed about stopping
- **The marker is not reachable.** (6150, -5, 12) projects onto the navmesh at (6150, 0, 10): the nearest walkable point is exactly **5.000 cm** from the marker (table erosion). Every arrival therefore ends about 5 cm from the marker.
  The tolerance was raised 5 -> 7 cm (user decision) because 5.000 cm sat on the limit.
- **The acceptance radius is honoured** (`Tools/ApproachStopProbe.py`, the same kind of request as the component, four approach directions, two time dilations): radius 3 stops up to 2.5 cm short of the reachable point;
  radius 1 stops within 0.015 cm in 8 of 8 trials; overshoot 0.000 and no oscillation in all 16; every path-following result was SUCCESS. The earlier 7.5 cm failure (radius 3) was therefore the accept radius, not the tolerance.
  The radius was lowered 3 -> 1 cm (user decision), keeping 7 cm.
- **Six real-StateTree arrivals** (QUI01, origins: cell, Rec_Table_B, TV, hall; two walk-in directions, -28 and -107 deg): all six confirmed, all at **(6150.000, 0.000)**, 0.000 cm from the reachable point, 5.000 cm from the marker,
  approach 0.35-0.50 s, no overshoot, no oscillation, no drift while seated, yaw error 0.84-1.49 deg, seated pelvis 93.3 cm from the table edge, pelvis height 50.7-50.9 cm. The arrival measurement was repeated against the final level
  with the stool and gave the same result.
- **Stopping error is up to about 1 cm, not exactly zero.** Other sits measured 5.516, 5.901 cm (standalone interruption runs) and (6149.52, 0.20) / (6149.08, 0.38) (rendered runs): all inside the 1 cm accept radius.
  Yaw error up to 2.8 deg was also seen (the alignment tolerance is 3 deg), which moves the pelvis about +-2 cm sideways.
- Only two walk-in directions occur in QUI01's real schedule; the other directions are covered by the probe, not by the real tree.

## 5. The stool
Seated pose measured in world space with the real animation (`Tools/SeatPoseMeasure.py`, three arrivals, two directions): capsule (6150, 0) facing -Y, pelvis joint 43.2-43.6 cm behind the capsule (y), 50.7-50.9 cm above the feet,
thighs near-horizontal at about 50 cm with the knees at y ~ 0, **lowest point of the body at z ~ 40.7 cm**. The stool is placed from that pose, not from the marker.

| | |
|---|---|
| Blueprint | `/Game/CyberWarden/Props/BP_CafeteriaStool`: 38 x 38 x 3 cm seat plate, four 3.5 cm legs, four 2 cm stretcher bars (engine cubes), neutral grey `MI_GB_Stool_Seat` / `MI_GB_Stool_Frame` (parent `M_GB_Lit`) |
| Actor | `Stool_Seat_Table_1_5` at **(6150, 41.5, 0)**, yaw -90, folder `S01_LW_F1/Props`, tags `S01F1Prop`, `Kind:SeatStool`, `SeatMarker:Seat_Table_1_5` |
| **Seat top** | **41.5 cm** above the floor (the brief said about 44 cm) |
| Seat footprint | x 6131..6169, y 22.5..60.5 (about 3.8 cm of plate behind the buttocks) |
| Collision / navigation | every component `NO_COLLISION`, `CanEverAffectNavigation` false, no overlap events; the stool footprint is still walkable navmesh |
| Independence | no `S01F1Greybox` tag: `Tools/BuildFloor1Greybox.py` neither removes nor regenerates it; it is not part of the M1 generation |

**Why 41.5 cm and 4 cm further back than first placed.** The first placement (centre y 37.5, top 44 cm) rendered with the buttocks flush with the seat's rear edge and about 3 cm *into* the plate (zoomed orthographic side and top views,
`Saved/StoolCheck/sheetD`). Lowering the top to the body's lowest point and moving the seat back put the buttocks on the plate with margin. The animation was not changed.
The level change is exactly one actor: a comparison of all 637 original actors (label, class, transform, scale, tags, folder, mesh) against the new level found the stool as the only difference. The map file itself was re-saved with that actor added.

## 6. Results
Assertions and process exit codes are recorded separately. All runs serial. The C2 DLL hash was verified unchanged after every run and Code Integrity logged no events at any point.

| Run | Assertions | Process exit |
|---|---|---|
| Native automation `CyberWarden.Prison.*` (7 tests, incl. `ActivityApproach`) | 7 / 7 | 0 |
| `ValidateActivities.py` | PASS, 0 problems | 0 (one earlier run: shutdown access violation) |
| `ValidateStool.py` (new, read-only: components, dimensions, collision, navigation influence, tags, marker, navmesh) | 21 / 21 | 0 |
| `ActivityApproachPieTest.py` (new, component under PIE: start, navigation, confirmation, already-there, too far, timeout, 120 s lockout, cancel by release / abort / other point / competing Move To) | 48 / 48 | 0 |
| `ApproachScheduleTest.py` (new, real StateTree: schedule change delivered during the approach, forced failure, lockout, no retry loop) | 20 / 20 in the standalone runs; **12 / 13 once, see 8** | 0 |
| `SeatArrivalMeasure.py` (six real-StateTree arrivals, repeatability verdict) | 6 / 6, REPEATABLE | 0 (one run: shutdown access violation) |
| `SeatedActivityPieTest.py` (C1 lifecycle) | 50 / 50; **47 / 50 once, see 8** | 0 |
| `SeatedScheduleTest.py` (C1, real StateTree; adapted to reuse the real seat point) | 21 / 21 | 0 |
| `ActivityComponentPieTest.py` (WatchTV and Stage A lifecycle) | 59 / 59 | 0 |
| `ActivityScheduleTest.py` emulation / real StateTree (adapted to count WatchTV starts only) | 24 / 24, 24 / 24 | 0 |
| `ScheduleRoutineEmulationTest.py` `EMU_MODE=statetree` (four prisoners, full day) | 96 / 96 (run twice) | 0 |
| `ScheduleComponentPieTest.py` / `NpcAnimProbe.py` / `ScheduleRecoveryTest.py` | 87/87, 20/20, 9/9 | 0 each |
| `VerifyNavigation.py` / `VerifyNpcFoundation.py` / `VerifySchedule.py` / `ValidateSchedule.py` / `VerifyStateTreeNodes.py` | 0 failures, 33/33, 23/23, 24 checks 0 problems, 10/10 | 0 each |

**Which runs saw the stool.** The stool was added after the first regression chain. After it, these were re-run: `ValidateStool`, `VerifyNavigation`, `ValidateActivities`, `SeatArrivalMeasure`, `ActivityApproachPieTest`, `SeatedActivityPieTest`,
`SeatedScheduleTest`, `ApproachScheduleTest`, `ActivityScheduleTest` (real tree), `ScheduleRoutineEmulationTest` (real tree), `VerifyNpcFoundation`, `VerifyStateTreeNodes`. The remaining rows above were run before the stool was placed; the level comparison shows
the stool is the only level change.

**Two test-side findings that were understood and fixed (not reliability issues).** (1) `ActivityScheduleTest` failed 22 / 24 in both modes because QUI01's lunch seat became a real activity point and its start was counted as an extra start; the assertions now count WatchTV
starts only. (2) The first `ApproachScheduleTest` runs could not deliver a schedule change during the 0.35 s approach because QUI01 has a 240 clock-second departure stagger (about 8 s of real time); the test now runs the manager clock at time scale 6000
in memory for that step. No schedule data is changed.

**Shutdown access violation:** the known intermittent `0xC0000005` (exit -1073741819) after a completed run (see `M2_2_Shutdown_Crash.md`) occurred in three processes during C2 validation (the first `ValidateActivities` run, one six-arrival run, one read-only asset dump), always after `LogExit`
and after the workload finished. It did not occur in the 29 processes of the two regression chains. It remains unresolved; those runs are not counted as unqualified passes.

## 7. Visual results and human acceptance
Rendered Play-In-Editor captures (GPU, scene captures in the PIE world, real StateTree, nothing driven; `Tools/StoolRenderCheck.py`, images in `Saved/StoolCheck/`, not committed) showed:
- **Approach:** a natural 0.4 s walk of about 40-47 cm; no shuffle or slide. **Turn:** about 0.6 s in place, from the walk-in heading to -90 deg. **Stand-to-sit:** about 2 s, the hips travel back and down onto the stool.
- **Seated:** thighs and buttocks rest on the seat plate, knees past its front edge, feet flat on the floor, no visible foot-IK distortion; the loop is identical 2 s later. Table clearance is fine for waiting (knees about 40 cm from the table edge).
- **Stand-up:** continuous; QUI01 walks away at about 143 cm/s without sliding.

**Human visual acceptance: approved (2026-11-04).** The project owner watched QUI01 approach the stool, sit, stand up and walk away and judged it good enough for the greybox milestone, and approved deferring the minor departure clipping.
Final animation and furniture polish are explicitly not part of this milestone.

### Accepted greybox limitation: stool clipping on departure
The stool has no collision (required, so it cannot block the NPC or navigation) and stands directly behind the standing position. When QUI01 stands and walks away, its legs pass through the seat and the stool's front legs for about 0.5 s
(`sheetE` tiles 3-4; the path leaves diagonally across the stool's front-left corner). **Accepted and deferred by the project owner.** Possible later treatments, none implemented: a small stool slide-back driven by the activity state,
an exit direction that clears the stool, or real furniture with animation. Related, also accepted: the seated pelvis is 93.3 cm from the table edge (88 cm planned), so a sitting NPC cannot reach the table; no eating animation exists.

## 8. UNRESOLVED test-reliability issues (tracked, not fixed)
The passing re-runs below are **not** proof that these are resolved.

1. **`ApproachScheduleTest.py` intermittent failure: cause unknown.** In the second regression chain (after the stool was placed) Part 1 failed all three attempts ("the approach never started (state PERFORMING)"), each waiting out its 600 s timeout, for 12 / 13 checks and 2,190 s
   (the standalone run takes about 7 min). In that run QUI01 had already reached and entered the seat at about t = 42 s, before the test started watching, and its position was logged as (6150, **-5**) (the marker itself) instead of the usual (6150, 0);
   no final approach was observed. The run had no frame-hitch warnings and its navigation log lines are identical to passing runs. Part 2 (forced failure, lockout) passed in the same run.
   **Re-runs:** a standalone re-run passed 20 / 20 (schedule change delivered on attempt 1, approach cancelled at 47 cm, no lockout, back at the meal the approach succeeded); the six-arrival run in the same chain (all at (6150.000, 0.000)), the rendered
   runs and an earlier 20 / 20 all behaved normally. So it is intermittent (1 failure in the 2 runs of this test since the stool was placed; the failure was not reproduced) and **not explained**. It might be a real rare path (arrival without a final approach) or a test race.
   The per-attempt timeout was cut from 600 s to 150 s so a repeat costs minutes. Suggested next step: repeat the test several times, and log the capsule position and component state each tick around the arrival if it recurs.
2. **Transient CPU-starvation failures in timing-sensitive tests.** `SeatedActivityPieTest.py` scored 47 / 50 once ("turning to the seat takes time (aligning)", "release while aligning...", "seated pelvis height 50.8..91.9") in the same chain.
   That run's log has 20 `LogCharacterMovement: GetSimulationTimeStep() ... Max iterations 8 hit while remaining time 1.25` warnings (single frames over a second long); no earlier run of this test had any; other programs (Blender, the Epic launcher and others) were running.
   A re-run alone passed 50 / 50 with 0 such warnings, and one six-arrival run had a single such warning but passed. The explanation (frame hitches make short phases unobservable) fits, but is **inferred**, not proven. Suggested: run the suite on an idle machine,
   repeat any failure before judging it, and consider making the timing tests report an invalid run when hitch warnings appear.
3. Carried forward unchanged from earlier stages: the headless shutdown access violation (`M2_2_Shutdown_Crash.md`), the Gate G1 transient stall and the cafeteria east-aisle congestion (see `M2_3_Stage_B.md` section 7).

## 9. Build and binary state (so the result can be reproduced)
- Smart App Control stays enabled. A freshly built unsigned module DLL is accepted or blocked by its hash and cloud reputation, so a rebuild is a gamble. The C1 DLL was overwritten by the first C2 build, which Smart App Control then blocked; a C1 DLL was rebuilt in a separate worktree (`CyberWarden_C1Recovery`, it loads) as the known-working fallback.
- **The C2 DLL that passed all of the above:** `Binaries/Win64/UnrealEditor-CyberWarden.dll` in the worktree `CyberWarden_C2Build`, SHA-256 `081A6A4923FEE1E1CB8B8BD308819D7F198EBEA31471D535C8E12CA21552D4B8`, built 2026-11-03 20:04:58 from `6e5116a` plus the C2 native changes,
  unsigned, BuildId 55116800. A copy (DLL, PDB, `UnrealEditor.modules`, `.target`, SHA-256 list) is kept outside every build directory at `Documents/Unreal Projects/_CyberWarden_Backups/C2_081A6A49/`. **It must not be rebuilt, relinked, signed or replaced.**
  Nothing in C2 after that build changed native code; the stool, data and tests are assets and scripts.
- The primary project's own C2 DLL (SHA-256 `62D53AE0...A91F`) is blocked by Smart App Control. Artifact Signing integration (`Tools/BuildCpp.ps1` v2, default Off) exists in the primary working tree, uncommitted, and is unaffected by C2.

## 10. Files
- **Native:** `PrisonActivityComponent.h/.cpp`, `PrisonActivityData.h/.cpp`, `PrisonActivityMath.h/.cpp`, `Tests/PrisonActivityTest.cpp` (adds `CyberWarden.Prison.ActivityApproach`).
- **Data and its tooling:** `Docs/Layout/S01_LW_F1_activities.json`, `Content/CyberWarden/Schedule/DA_S01_LW_F1_Activities.uasset`, `Docs/Layout/S01_LW_F1_activities_report.txt`, `Content/Python/cw_activity.py`, `Tools/ConfigureActivities.py`, `Tools/ValidateActivities.py`.
- **Stool:** `Content/CyberWarden/Props/BP_CafeteriaStool.uasset`, `MI_GB_Stool_Seat.uasset`, `MI_GB_Stool_Frame.uasset`; the placed actor in `Content/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox.umap`; `Tools/CreateSeatStool.py` (idempotent create / update / place), `Tools/ValidateStool.py`.
- **Measurement and inspection tools:** `Tools/SeatPoseMeasure.py`, `Tools/SeatArrivalMeasure.py`, `Tools/ApproachStopProbe.py`, `Tools/StoolRenderCheck.py` (needs the GPU: `Tools/RunRenderScript.ps1`), `Tools/InspectQUI01Stool.py`.
- **New and adapted tests:** `Tools/ActivityApproachPieTest.py`, `Tools/ApproachScheduleTest.py`; adapted `Tools/SeatedScheduleTest.py` and `Tools/ActivityScheduleTest.py`.

## 11. Inspect it yourself in Play In Editor
Open `CyberWarden.uproject`, open `/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox`, press Play, then in the Output Log Cmd box run
`py "<project>/Tools/InspectQUI01Stool.py"`: it sets the clock to breakfast and puts the player camera east of the stool; QUI01 sits after about 45 s. Run the same command again once it sits and it stands up and walks away about 8 s later (departure stagger).
F8 ejects the camera to fly around. Nothing on disk is changed.

## 12. Open items carried forward
1. The two unresolved test-reliability issues above (section 8) and the earlier tracked items (shutdown access violation, Gate G1 stall, east-aisle congestion).
2. Accepted greybox limitations: stool clipping on departure; seated pelvis 93.3 cm from the table edge; stopping error up to about 1 cm; yaw up to 3 deg.
3. Not done, by decision: stool slide-back or other departure treatment, eating animation, final furniture, additional seats (each needs its own interaction point and a stool; the pose and offsets in section 5 are the reference).
