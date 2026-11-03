# M2.3 Stage B - native StateTree integration of the activity system (QUI01 watching TV)

Branch `m2-3-activity-foundation` (Stage A: `58d00fc`). **Native code, tests and this guide are done. `ST_NPCRoutine` has NOT been edited**: until the manual steps in section 4 are done, the real tree still behaves exactly as in M2.2 and nobody performs an activity.

## 1. Implementation
| Piece | What it does |
|---|---|
| `Prison: Perform Activity` (`FPrisonPerformActivityTask`) | Place it in **IdleAtStop**. `EnterState`: `RequestActivity(MarkerId)` on the NPC's activity component (an ordinary stop with no interaction point is refused harmlessly). `ExitState`: `ReleaseActivity()`. It has no per-tick work and is **not considered for completion**, so it can never end the state or interfere with the Delay task, which still decides how long the NPC idles. Inputs: Actor (context), Marker Id. |
| `Prison: Plan Destination` (extended) | New float output **Arrival Tolerance** (cm) for Move To's Acceptable Radius: 60 for ordinary stops; for an interaction point `tolerance - capsule radius - 20 cm`, floored at 10 and capped at 60 (Rec_TV: 60). Its **Start Delay Seconds** output now also covers a still-running exit: if the NPC is leaving an activity (and is not simply continuing the same one at the same single stop), the delay is raised to the component's predicted time until free. |
| `UPrisonActivityComponent` additions | `GetSecondsUntilFree()`, `GetSecondsUntilFreeFor(NextMarker, bMoveRequired)` (0 when the next plan continues the same activity), `GetMoveAcceptableRadius(MarkerId, Default)`. Release grace window raised from 0.25 s to **0.5 s** (a StateTree needs several ticks to leave and re-enter the idle state, and the tests run at 4x speed; a re-request within the window continues the activity without a restart). |
| Movement authority | The component, not a predicted duration, decides when the NPC may move: while an activity is aligning, entering, performing or exiting, movement is held (`MOVE_None`) and the component itself restores walking when it is really free. Tested: a Move To issued while the activity was still releasing did **not** move the NPC (0.0 cm in 0.35 s), stayed pending, and proceeded without failing once the component released movement (566 cm in 4 s). A wrong prediction therefore cannot slide the NPC out of its pose. |
| Preserved | `STT_ReportState` (and the StartDelay label fix), the Delay and Move To tasks, the Recover state, the replan transition, avoidance, the animation Blueprint, the schedule data. |
| New tests | `ActivityScheduleTest.py` (QUI01 end to end; `ACT_MODE=emulation` now, `ACT_MODE=statetree` after your edit), extended `ActivityComponentPieTest.py` (59 checks), `VerifyStateTreeNodes.py` (10 checks). |

### How the task lifecycle fits the existing tree
- **Idle duration:** unchanged. The Delay Task in IdleAtStop ends the state after Idle Seconds; Perform Activity runs for exactly that long (enter on state entry, release on exit).
- **Single-stop destinations** (meals, lockdown, and the single-stop case tested below): at the end of an idle cycle the tree leaves IdleAtStop (release starts the 0.5 s grace window), re-plans the same stop (no movement needed, no wait) and re-enters IdleAtStop within the window: the request is a **continuation**, the activity never restarts.
- **Schedule change while watching:** the root transition fires after QUI01's stagger, leaves IdleAtStop (release), the plan task picks the new destination and adds the remaining exit time to the start delay, StartDelay waits, Move To starts only after the component has restored movement.
- **Recover / navigation failure while performing:** leaving IdleAtStop always releases; nothing can keep the NPC held.
- **Tree stops:** ExitState and the component's `EndPlay` release movement.

## 2. Automated results (all Unreal runs serial; process exit codes recorded separately)
| Test | Assertions | Process exit |
|---|---|---|
| `Tools/BuildCpp.ps1` | Succeeded | 0 |
| Native automation tests `CyberWarden.Prison.*` | 5 / 5 Success | 0 |
| `VerifyStateTreeNodes.py` (both new nodes registered) | 10 / 10 | 0 |
| `ValidateActivities.py` / `ValidateSchedule.py` / `VerifySchedule.py` / `VerifyNpcFoundation.py` | 0 problems / 24/24 / 23/23 / 33/33 | 0 each |
| `ActivityComponentPieTest.py` (adds the plan helpers and the movement-authority test) | **59 / 59** | 0 |
| **`ActivityScheduleTest.py`, driver emulation of the new tree** (QUI01 end to end, real navigation) | **24 / 24** | 0 |
| `ScheduleComponentPieTest.py` (M2.2 component) | 87 / 87 | 0 |
| Real-StateTree full-day acceptance (`EMU_MODE=statetree`, four prisoners, M2.2 behaviour) | 96 / 96 (0 navigation failures, stuck, teleports, repeated Move To) | 0 |
| `NpcAnimProbe.py` / `ScheduleRecoveryTest.py` / `VerifyNavigation.py` | 20/20, 9/9, 0 failures | 0 each |

What the end-to-end test (`ActivityScheduleTest.py`, emulation) proved for QUI01, following only its schedule:
- reaches `Rec_TV` by navigation (stops 94 cm from the marker, inside the 150 cm point tolerance) and **starts WatchTV exactly once for the arrival** (start count 1, arrival count 1);
- faces the TV with **0.00 deg** error; the idle animation plays through `DefaultSlot` (slot weight 1.00); movement is held while watching; no restart over the next 5 s;
- **a schedule change (work to lunch, injected while watching)** produces exactly one replan after QUI01's stagger; the activity ends 0.6 s later (Exiting, then Idle) before the NPC has moved at all (0 cm), movement is restored to walking, and QUI01 walks to its lunch seat;
- the next change (lunch to recreation) brings it back to the TV: a **second arrival is a second start** (1 to 2), with no restart while watching;
- **single-stop phase** (work reduced to the single stop `Rec_TV` in memory only): the replan with QUI01 already at the TV continued the activity (no restart), and over 70 s with idle cycles of 20-25 s there were 3 continuations, still 1 start and no state change; the loop montage never stopped by itself;
- no teleport (largest step 10-12 cm at 150 cm/s), no visible snapping during the activity (0.00 cm), no navigation failure for QUI01, no restart storm (4-9 plans per run), other prisoners unaffected.

Findings during Stage B:
- The grace window of 0.25 s was too short for a StateTree's exit/re-enter chain; raised to 0.5 s (tests updated).
- The end-to-end test originally ran with the clock paused so the stagger never elapsed (a test mistake); it now runs the 30x clock.
- **Intermittent cafeteria aisle conflict (pre-existing, low priority):** in one of three end-to-end runs WRK01 had one navigation failure (recovered in 1.9 s) at (6987, 616), 3,000 cm from QUI01: about 5 s earlier TRB01 had just stopped at its lunch seat in the narrow aisle between table 4 and the servery counter and WRK01 was squeezed between the table corner and TRB01. It is not related to the activity code, did not recur in later runs, and is recorded with the Gate G1 stall as a congestion item to watch (candidate fix later: a different lunch seat for TRB01 or more clearance).
- Tracked and unchanged: the headless shutdown access violation (no run of this stage crashed at exit; one run directly after a rebuild exited with code 1 at start-up in Stage A and did not recur) and the Gate G1 stall.

## 3. Not covered headless
The real-tree behaviour of the new task (the assertions above use a Python driver that calls exactly the same native component functions in the same order) and the visible pose. After your edit run the same test against the real tree: `powershell -File Tools\RunHeadless.ps1 -Script Tools\ActivityScheduleTest.py -Log <abs log> -Env ACT_MODE=statetree`, then the human visual Play In Editor check.

## 4. Manual StateTree steps (about 10 minutes, no Blueprint nodes)
Close the Unreal Editor first if it is open, then reopen the project so it loads the rebuilt game module.

1. Open `Content > CyberWarden > NPC` and double-click **ST_NPCRoutine**.
2. Click the state **IdleAtStop**. In the Details panel find **Tasks**.
3. Click the **+** next to Tasks, type **Prison** in the search box and choose **Prison: Perform Activity**. Leave the other tasks (the reporting task and the **Delay Task**) exactly as they are. Do not change the Delay.
4. Open the new task's properties:
   - **Actor**: it should already show it is bound to **Context > Actor**. If it is empty, right-click it, choose **Bind > Context > Actor**.
   - **Marker Id**: click the small chain icon at its left and choose **Routine > Prison: Plan Destination > Marker Id**.
5. Click the state **MoveToStop**. In its **Move To** task find **Acceptable Radius**. Click the chain icon at its left and choose **Routine > Prison: Plan Destination > Arrival Tolerance**. (This replaces the typed 60; the plan task outputs 60 for ordinary stops.)
6. Click **Compile** in the toolbar (it should say it succeeded, with no unbound inputs), then **Save**.

Nothing else changes: no new state, no new transition. Then tell me it is done and I run the real-tree test above with the editor closed; after that you do the visual check below.

**What to look for in Play In Editor** (open `L_S01_LW_F1_Greybox`, the clock starts at 06:00 and runs at 30x, one game hour is 2 real minutes): from 08:00 QUI01 walks to the recreation area. When it stops at the TV it should turn smoothly toward the TV and stand there for its idle period (the debug overlay shows the activity state); it should not snap, slide or restart when its idle period ends and it picks the other recreation stop (it walks to the table) or stays. When the period changes (for example at 12:00 it goes to the cafeteria) it should stop watching and then walk off without sliding. The other three prisoners should behave as before. With the standard idle pose as a placeholder the only visible difference is the deliberate facing; real watching, sitting or eating poses come with the later animation stages.

## 5. Risks / items needing approval
- The placeholder pose is the ordinary idle: Stage B proves the facing, lifecycle, interruption and movement logic, not a new look. Real animations (and the seat / bunk geometry) are the separately approved later stages.
- The 0.5 s grace window means a stand-up exit starts half a second after the idle ends; it is deliberate and configurable (`ReleaseGraceSeconds`).
- The cafeteria aisle conflict and the Gate G1 stall remain open congestion items; neither is changed here.
- The headless shutdown access violation remains unresolved and tracked (`M2_2_Shutdown_Crash.md`).
