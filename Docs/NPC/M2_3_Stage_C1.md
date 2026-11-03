# M2.3 Stage C1 - native seated-activity support (Enter -> Loop -> Exit)

Branch `m2-3-activity-foundation` (Stage C0: `57715bf`). Native code, tests and data tooling only. **Not changed:** cafeteria geometry, markers, navigation, M1 assets, the level, the player / camera / input / GameMode, `ST_NPCRoutine`, `ABP_PrisonNPC`, schedules. No stool, no seat interaction point (Stage C2). No animation assets were added; the approved C0 clips `SEAT_StandToSit`, `SEAT_SittingIdle`, `SEAT_SitToStand` are used as they are.

## 1. Native changes
| Where | Change |
|---|---|
| `FPrisonActivityDefinition` (data) | Optional per-phase timing, all "inherit" when negative so every Stage A/B definition behaves exactly as before: `EnterBlendInSeconds`, `LoopBlendInSeconds` (the enter-to-loop cross-fade), `ExitBlendInSeconds` (loop-to-exit cross-fade), `ExitBlendOutSeconds`, `bCommitEnter`, `ReleaseGraceSeconds`. `Validate` rejects `bCommitEnter` without an enter animation. |
| Enter -> Loop hand-off | The loop montage now starts one cross-fade (`LoopBlendIn`) **before** the enter montage ends, replacing it in the same slot, so the slot never falls back to the standing pose. Driven by the montage's real remaining time (`Montage_GetPosition`), with the planned end and "no longer playing" as fallbacks. The enter montage's blend-out equals the cross-fade, so both fade over the same interval. |
| Loop -> Exit | The exit montage cross-fades in over `ExitBlendIn`; the loop's blend-out is set to the same value (or to `ExitBlendOut` when there is no exit animation). |
| Committed enter (`bCommitEnter`) | A release, or a request for another point, while sitting down no longer blends out of the half-seated pose: the sit finishes (cross-faded straight into the stand-up when the release has already expired), then the exit runs. A request for the same point inside the grace window is still a continuation. Without the flag the Stage A behaviour (blend out) is unchanged. |
| Exit completion | Movement is restored when the exit animation reports it is finished, not at a predicted time: `ExitComplete(now, plannedEnd, animationFinished, ExitSafetyMarginSeconds)`; the planned end is the earliest time and a 1.0 s safety margin (property) frees the NPC if a montage never reports completion. |
| Release grace | Per definition (`ReleaseGraceSeconds`), falling back to the component's 0.5 s. `ExpediteRelease(NextMarker, bMoveRequired)` (new, called by the `Prison: Plan Destination` task after the Perform Activity task released) skips what is left of the grace when the NPC is really leaving (another stop, or the same one but it must walk), so a seated NPC stands up at once on a schedule change; a single-stop re-plan (same marker, no move) is untouched. |
| Diagnostics | `CompleteCount`, `HandoffCount`, `MaxDisplacementCm` (the capsule never moves during an activity). |
| `PrisonActivityMath` | Pure helpers `ResolveBlend`, `RemainingPlaySeconds`, `HandoffDue`, `ExitComplete`. |
| Unchanged by design | Capsule position (no root motion, no snapping, no settling), movement hold (`MOVE_None` until the component itself is free), queued requests, abort, `ABP_PrisonNPC`, `ST_NPCRoutine` (the native plan task gained one call). |
| Data tooling | `Docs/Layout/S01_LW_F1_activities.json` has a new generic `SeatedIdle` definition (the three clips; enter blend-in 0.4, enter->loop 0.25, loop->exit 0.25, exit blend-out 0.4, commit enter, grace 1.5 s, no random loop start) and **no interaction point**; `cw_activity.py`, `ConfigureActivities.py`, `ValidateActivities.py` support the new fields (the validator also checks cross-fades against the clip lengths); `DA_S01_LW_F1_Activities` regenerated (2 activities, 1 point, 0 errors). |

## 2. Animation lifecycle results (real clips, QUI01 at the real marker `Seat_Table_1_5`)
`Tools/SeatedActivityPieTest.py`: **50 / 50** (AI navigation to the seat, nothing teleported, in-memory data only):
- Order Aligning -> Entering -> Performing; Entering lasts 1.93 s (2.23 s clip minus the 0.25 s cross-fade); one start, one hand-off; the loop starts at its first frame; nine seconds (two loops) seated with slot weight 1.00 and no unexpected stop; facing error 0.00 deg.
- Release reports 3.77 s (1.5 s grace + 2.27 s exit); Exiting lasts 2.20 s; whole release 3.87 s; movement restored only after the animation finished.
- Single-stop continuation: re-requests 0.3 / 0.9 / 1.3 s after a release keep the NPC seated (start 1, complete 0).
- Expedite: not applied to a same-stop continuation; applied for another stop (exit starts 0.55 s after the release instead of 1.5 s).
- Interruption: while entering (committed: sit finished, then stood up; interrupt count unchanged; re-request inside the grace continues), request for another seat while entering and while performing (exit, then the queued seat starts), release / same-seat request while exiting (queue cancelled / genuine second cycle), abort in performing / entering / exiting, release while aligning, Move To issued during the stand-up does not move the NPC (0.0 cm in 1 s) and proceeds afterwards (594 cm in 4 s).
- Invariants over 1,050 samples: movement held on every busy tick; capsule step 0.000 cm and height range 0.00 cm; slot weight >= 0.9 with a montage present through every hand-off and cross-fade (0 gaps); **poses do evaluate headless**: pelvis 50.8..53.2 cm while seated (clip 52.9), and it never rises back towards standing between sitting down and standing up (0 violations, i.e. no standing-pose flash).

`Tools/SeatedScheduleTest.py` (**real StateTree**, in-memory seat point and a lunch reduced to the single stop `Seat_Table_1_5`): **21 / 21**. QUI01 followed its schedule, sat (hand-off 1, yaw error 0.00), stayed seated through 6 idle cycles with only continuations (1 start, 0 completes, 0 state changes, 16 loops, no unexpected stop), stood up **0.07 s** after the schedule change, stand-up 2.27 s, movement restored afterwards, no slide (0.0 cm), then walked to the TV and started WatchTV; no snapping, largest step 10.0 cm, no navigation failures for any prisoner.

## 3. Regression (all Unreal runs serial; process exit codes separate from assertions)
| Run | Assertions | Process exit |
|---|---|---|
| `Tools/BuildCpp.ps1` | Succeeded | 0 |
| Native automation `CyberWarden.Prison.*` (adds `ActivityTiming`) | 6 / 6 Success | 0 |
| `ValidateActivities.py` | PASS, 0 problems | 0 |
| `ActivityComponentPieTest.py` (WatchTV and Stage A lifecycle) | 59 / 59 | 0 |
| `ActivityScheduleTest.py` emulation / real StateTree | 24 / 24 / 24 / 24 | 0 / 0 |
| `ScheduleRoutineEmulationTest.py` `EMU_MODE=statetree` (four prisoners, full day) | 96 / 96 | 0 |
| `ScheduleComponentPieTest.py` / `NpcAnimProbe.py` / `ScheduleRecoveryTest.py` | 87/87, 20/20, 9/9 | 0 each |
| `VerifyNavigation.py` / `VerifyNpcFoundation.py` / `VerifySchedule.py` / `ValidateSchedule.py` / `VerifyStateTreeNodes.py` | 0 failures, 33/33, 23/23, 24 checks 0 problems, 10/10 | 0 each |
| `SeatedActivityPieTest.py` / `SeatedScheduleTest.py` | 50 / 50, 21 / 21 | 0 each |

One existing assertion was updated on purpose: the Stage A enter check expected the Entering phase to last 0.7-1.1 s; it now ends one cross-fade early by design, so the bound is 0.5-0.85 s (MM_Land 0.87 s minus 0.2 s). The emulation driver in `ActivityScheduleTest.py` now also calls `expedite_release` (as the real plan task does). No run of this stage ended with the headless shutdown access violation, which says nothing about its cause (tracked, unresolved).

## 4. Remaining visual risks (not seen by a human yet)
- The cross-fades are verified by slot weight, montage presence and the evaluated pelvis height, not by eye: the blend from the walking idle into the sit (0.4 s) and out of the stand-up (0.4 s) may show some foot sliding (C0 measured up to 21-23 cm / 46-52 deg at the feet between the walking idle and the clip poses).
- `ABP_PrisonNPC` references a foot-IK Control Rig; whether it distorts seated feet is unconfirmed (nothing sits on a stool yet).
- A sit without a stool shows the NPC seated in the air; the NPC will stand where Move To stops it (see below).

## 5. Required for Stage C2 (data and geometry; none done in C1)
1. **Where the NPC actually stands.** With the point tolerance of 150 cm, Move To stopped QUI01 **90 cm** from `Seat_Table_1_5` (99 cm in the component test; the Stage B TV stop was 94-96 cm). The seat clip assumes the NPC starts at the spot the stool is placed against: the pelvis then travels 43 cm backwards. A tight stop needs a small tolerance on the seat point (the plan task already derives the Move To radius from it; floor 10 cm) and probably a bounded positional settle (explicitly not introduced in C1, needs approval), otherwise the stool cannot line up with the pose. The stop distance with a tight tolerance must be measured on the real tree.
2. **Interaction points** for the chosen seat(s) in `S01_LW_F1_activities.json` (activity `SeatedIdle`, yaw -90 for the table side, capacity 1); the validator requires a scheduled user (QUI01 meals already use `Seat_Table_1_5`). `ConfigureActivities.py` regenerates the data asset.
3. **Geometry** (separate approval): a non-navigation-affecting, no-collision stool about 38 x 38 x 44 cm behind the standing spot (pelvis 43 cm back, seat top 44 cm); the 88 cm table gap from the C0 record still applies (hands in the lap, no eating).
4. **Visual acceptance** in Play In Editor after 1-3.

## 6. Manual Unreal Editor work
None required for C1. Optional: open Play In Editor only after C2 for the visual check.
