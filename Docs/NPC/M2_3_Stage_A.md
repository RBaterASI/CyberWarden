# M2.3 Stage A - activity data and native foundation

Branch `m2-3-activity-foundation` (from `main` at `1cf2f21`). Scope: reusable activity definitions, interaction-point data and validation, the C++ activity component and its diagnostics, the QUI01 / `Rec_TV` television definition, and tests. **Nothing is connected to the StateTree**; `ST_NPCRoutine`, `STT_*`, the level, M1 geometry and navigation are untouched.

## Architecture
| Piece | Role |
|---|---|
| `Docs/Layout/S01_LW_F1_activities.json` | Source of truth: activity definitions and interaction points. `Tools/ConfigureActivities.py` turns it into the data asset; the facing target is resolved from the layout (the TV centre comes from `Prop_Rec_TV`, not from a typed coordinate). |
| `UPrisonActivityData` (`DA_S01_LW_F1_Activities`) | Data asset: `FPrisonActivityDefinition` (optional enter / loop / exit animations, slot name, blend times, play rate, random loop start, align rate, yaw tolerance) and `FPrisonInteractionPoint` (marker id, activity id, facing mode none / yaw / point, arrival tolerance, capacity). Native validation (`ValidateData`). |
| `APrisonScheduleManager.ActivityData` | The sector manager references the activity data (default set on `BP_PrisonScheduleManager`). |
| `UPrisonActivityComponent` (`PrisonActivity` on `BP_PrisonNPC`) | Runs one activity at a time for its owner: `RequestActivity(MarkerId)`, `ReleaseActivity()`, `AbortActivity()`, `IsBusy()`, `HasInteractionPoint()`. It knows nothing about NPC names, the schedule or the StateTree. |
| `PrisonActivityMath` | Pure yaw helpers (normalise, shortest delta, bearing, constant-rate step without overshoot). |

Interaction points are keyed by marker id, so they apply to every NPC the schedule sends there. Today the only point is `Rec_TV` (QUI01 is the only NPC scheduled there, in the work and recreation periods); a new archetype or a guard activity is a new data row.

### Lifecycle (state machine)
`Idle -> Aligning -> [Entering] -> Performing -> [Exiting] -> Idle`
- **Request**: accepted only when the NPC already stands within the point's arrival tolerance (150 cm for `Rec_TV`; navigation stops at about 95 cm). Otherwise it is refused with a reason ("too far from Rec_TV: 400 cm > 150 cm ..."). The component never moves the NPC to the marker: no teleport, no snapping.
- **Aligning**: smooth constant-rate yaw turn (120 deg/s, 3 deg tolerance) while movement is held (`MOVE_None`). Only the actor yaw changes.
- **Entering / Performing / Exiting**: optional enter animation, then the loop as a dynamic montage in `DefaultSlot` with a random start offset, then the optional exit animation or a blend-out. Missing animations degrade to the normal idle pose (`bUsingFallbackIdle`, one logged warning). A loop montage that stops by itself is restarted (bounded to 3).
- **Continuation**: a request for the same point while it is aligning, entering, performing or pending release only counts as a continuation. After `ReleaseActivity()` the activity keeps running for a 0.25 s grace window; a re-request inside it continues without a restart (single-stop destinations re-plan every idle cycle).
- **Release**: returns the seconds until the NPC is free to move (grace + exit animation or blend-out). Releasing while aligning is immediate (interrupt counted); while entering it blends out; while performing it waits the grace window; while exiting it reports the remaining time.
- **Requests during an exit**: a request for another point, or the same point while exiting, is queued (`PendingMarkerId`) and starts when the NPC is free.
- **Movement is always restored** (to walking) when the activity ends, is interrupted, is aborted, or the component ends play.
- **Diagnostics** (Blueprint / Python readable): state, active activity and marker, start / continuation / interrupt / unexpected-stop counts, last failure reason, yaw error and target, distance to the marker, montage playing, slot node weight, movement held, fallback idle, release pending, pending marker.

## Verified: `ABP_PrisonNPC` plays montages through `DefaultSlot`
`ABP_PrisonNPC` contains an `AnimGraphNode_Slot` with `DefaultSlot`. In the headless PIE test the loop was played as a dynamic montage in `DefaultSlot`; the animation instance reported the montage playing and **the slot node's global weight reached 1.00** (the weight is only written by a slot node inside the animation graph, so the graph really processes the slot). The 0.87 s enter / exit test animations (`MM_Land`) blended in and out through the same slot. Locomotion is preserved: after each activity the NPC walked away again (581 cm in 4 s) and the animation Blueprint's `ShouldMove` flipped back to true while walking and was false while standing. The `ABP_PrisonNPC` asset was not modified. (A pose cannot be inspected headless; the visual pose check belongs to Stage B.)

## Automated results (all Unreal runs serial)
| Test | Result |
|---|---|
| `Tools/BuildCpp.ps1` | Succeeded |
| Native automation tests `CyberWarden.Prison.*` (ClockMath, ScheduleData, ScheduleSelect, **ActivityMath, ActivityData**) | 5 / 5 Success |
| `ValidateActivities.py` (schema, marker is `NavDest:Yes`, prop exists and faces the TV, 1,221 cm from the nearest opening, tolerance >= 100 cm, animation exists on `SK_Mannequin`, used by QUI01/work and QUI01/recreation) | PASS, 0 problems |
| `ConfigureActivities.py` | data asset 1 activity / 1 point / 0 validation errors |
| **`ActivityComponentPieTest.py`** (QUI01, real navigation to the TV, StateTree stopped in the PIE copy) | **44 / 44** |
| `ValidateSchedule.py` / `VerifySchedule.py` / `VerifyNpcFoundation.py` / `VerifyStateTreeNodes.py` | 24/24, 23/23, 33/33, 8/8 |
| `ScheduleComponentPieTest.py` (M2.2 component) | 87 / 87 (test updated, see below) |
| `ScheduleRoutineEmulationTest.py` against the REAL StateTree (full day, four prisoners) | 96 / 96 (0 navigation failures, 0 stuck, 0 teleports, 0 repeated Move To) |
| `NpcAnimProbe.py` (animation regression) | 20 / 20 |
| `ScheduleRecoveryTest.py` (navigation-failure recovery) | 9 / 9 |
| `VerifyNavigation.py` | 0 failures, all NPC legs OK |

What the 44 component checks cover: refusal when too far (reason, nothing held) and for a marker without a point; navigation to the TV; start accepted; movement held; reaching Performing; **facing error 0.00 deg** (limit 3.5); smooth turn (110 deg/s for the 7 deg turn, 120 deg/s for a 180 deg turn, limit 120); no snapping (0.00 cm position step and displacement during the whole activity); DefaultSlot playback (weight 1.00); one start; 6 repeated requests = 6 continuations and no restart; release reports 0.55 s (0.25 grace + 0.3 blend-out); re-request inside the grace window continues; clean release, movement restored, slot empty, NPC walks away; interruption while aligning (free immediately, no montage ever played); a request during Exiting is queued and starts afterwards; full enter / loop / exit cycle (enter 0.80 s, release 1.12 s, exit finished); interruption while entering (blend-out only, interrupt counted); activity without animations (fallback, no montage); abort stops everything and restores movement; no position step above 1 cm at any time during an activity.

Defects found and fixed during Stage A: `AbortActivity` left the montage diagnostic stale until the next tick (diagnostics now update with the state); a unit test tripped an engine assertion by adding an array element from the array itself (test fixed).

Test maintenance (not product changes): since the real StateTree is integrated, `ScheduleComponentPieTest.py` now stops the tree in the PIE copy and accounts for the plans and retry back-off the live tree already made (an earlier run showed 72 / 87 for exactly that reason); the full-day real-StateTree run (96 / 96) confirms the product behaviour is unchanged.

## Tracked issues (unchanged)
- **Headless shutdown access violation: still unresolved.** About 25 Unreal runs were made for Stage A; none ended with the access violation, which says nothing about the cause (observed rate was 5-10%). Two other abnormal process exits were seen and explained or noted: the first automation run exited 3 because of an engine assertion in my own new unit test (fixed), and one run directly after a rebuild exited 1 at start-up without loading the script and did not recur on retry (unexplained, noted). See `M2_2_Shutdown_Crash.md`.
- **Gate G1 transient stall:** low priority, monitor (not touched).

## Remaining manual StateTree configuration (Stage B, not started)
Stage B adds one native task, `Prison: Perform Activity`, with no Blueprint nodes, and then needs these hand edits in `ST_NPCRoutine` (about 10-15 minutes):
1. In **IdleAtStop**: add the task **Prison: Perform Activity**; bind its **Actor** to Context > Actor and its **Marker Id** to Routine > Prison: Plan Destination > Marker Id. (The existing Delay still decides how long the activity lasts; leaving the state releases the activity.)
2. In **MoveToStop**: bind **Move To > Acceptable Radius** to Plan Destination's new arrival-tolerance output (a float output to be added in Stage B so seats and benches can later require a tighter stop than the TV).
3. Compile and save.
Stage B also extends `Prison: Plan Destination` so the exit animation length is added to its start delay (the existing StartDelay state then waits for a stand-up before the NPC walks off).

## Animation assets
- **Needed for Stage B (QUI01 watching TV): none.** The prototype reuses `MM_Idle` as a placeholder loop; the activity is the purposeful alignment (facing the TV) through the real slot pipeline.
- **Needed to make later activities look right** (UE5 Manny/Quinn skeleton `SK_Mannequin`, in place with root motion off, loop-friendly, licence permitting; otherwise retarget with an IK Rig / IK Retargeter, which the project does not have yet):
  - Watching TV / standing idle variants: arms-crossed idle loop, weight-shift idle loop, a slow look-around idle.
  - Sitting and eating (needs bench or stool props and a separate geometry approval): stand-to-sit, sit idle loop, sit eating loop, sit drinking loop, sit-to-stand.
  - Sleeping (needs lowered bunks and a separate geometry approval): stand-to-lie (bunk), sleeping loop, lie-to-stand.
  - Work: serving loop at a counter, wipe / clean loop, mop loop.
  - Recreation: push-up loop, stretch loop, bench-press loop (with bench prop), card-table sit idle.
  - Conversation: talking gesture loops (3 variants), listening idle, laugh.
  - Crouch / kneel idle for general variety.

## Risks for Stage B
- The `DefaultSlot` pose is verified by slot weight, not visually (headless has no pose evaluation).
- Alignment accuracy depends on the Move To stop distance (about 95 cm); fine for the TV, too loose for seats (hence the planned arrival-tolerance output).
- A single-stop destination re-plans each idle cycle: the grace window covers it, but only the real-tree run proves it.
- Shared interaction points (`Conv_Hall_A` is used by three prisoners) will need slot offsets and enforced capacity before they get activities.
