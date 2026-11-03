# M2.2 Checkpoint B - schedule-driven NPC movement (native implementation)

Branch `m2-2-cpp-clock`. State: **native code, level placement and automated tests are done. The StateTree has NOT been edited**; `ST_NPCRoutine` still runs the old looping routes until you do the manual steps in section 4. Shutdown crash: see `M2_2_Shutdown_Crash.md` (unresolved, tracked).

## 1. What was implemented
| Piece | Detail |
|---|---|
| Schedule manager in the level | `SCHED_S01_LW_F1` (Blueprint child of `APrisonScheduleManager`, folder `S01_LW_F1/Systems`) placed by `Tools/PlaceNpcs.py`; 30x clock starting 06:00; period data from `DA_S01_LW_F1_Schedule`. Only an actor was added to the level; M1 geometry and navigation are untouched. |
| Native task `Prison: Plan Destination` (`FPrisonPlanDestinationTask`) | Runs once on entering the routine's root state. Calls `PlanForCurrentPeriod()` of the NPC's schedule component. Outputs: `TargetActor` (cleared when the plan is invalid, never stale), `IdleSeconds` (float), `StartDelaySeconds` (float), `bMoveRequired`, `bPlanValid`, `MarkerId`, `PeriodIndex`. Inputs: `Actor` (context, auto-bound). |
| Native condition `Prison: Replan Requested` (`FPrisonReplanRequestedCondition`) | True while the component's one-shot replan request is raised. For one transition on the root state. |
| `UPrisonScheduleComponent` changes | `StartDelaySeconds` in the plan (the NPC's stagger on its very first plan, a back-off 2, 4, 8, 16, max 30 s when the same required movement is re-planned within 8 s, else 0); a routine re-plan made while a schedule change's stagger is still running keeps the previous assignment (the new period is followed only when the replan request fires, so exactly one replan per change and no stagger bypass); `RetryStreakCount` diagnostic. |
| Timing types | All new timing outputs are `float` (real). Legacy integer-typed Blueprint variables were not retyped. |
| Preserved | `STT_ReportState` (including the StartDelay label fix), `Delay Task`, `Move To` (radius 60), the Recover state, avoidance and animation are untouched. |

Behaviour built into the plan:
- Already at the destination (inside 150 cm): `bMoveRequired` = false, so the movement state is skipped and the NPC just idles (meals and lockdown, which have a single stop).
- Empty or unknown assignment: `bPlanValid` = false, `TargetActor` empty, `bMoveRequired` = false: the routine falls through to Recover (NavFail is reported, 2 s wait, then re-plan). This also fixes the earlier empty-Route issue.
- Lockdown: the single stop is the NPC's own cell marker; it stays until the 06:00 period change plus its stagger.
- Period change while moving, idling or recovering: the root-state transition (below) fires once after the NPC's stagger; leaving the state stops the Move To and the Delay; the NPC re-plans and walks straight to its new destination from where it stands (no teleport).

## 2. Automated test results
| Test | Result |
|---|---|
| `Tools/BuildCpp.ps1` | Succeeded |
| Native automation tests (`CyberWarden.Prison.ClockMath`, `.ScheduleSelect`, `.ScheduleData`) | 3 / 3 Success (now include the back-off values) |
| `VerifyStateTreeNodes.py` | 8 / 8: both native nodes are registered; built-in Move To, Delay and Bool Compare exist |
| `ScheduleComponentPieTest.py` (placed manager, 4 prisoners) | **87 / 87** |
| `ScheduleRoutineEmulationTest.py` (full day, real navigation; see below) | **96 / 96** |
| Existing routes `NpcPopulationTest.py`, 400 game s | PASS, unchanged: loops 5/3/4/14, 0 navigation failures, 0 stuck, 0 teleports |
| `VerifySchedule.py` / `VerifyNpcFoundation.py` / `ValidateSchedule.py` | 23/23, 33/33, 24/24 |
| `VerifyNavigation.py` | 0 failures, all NPC legs OK. **Note: the process crashed at exit (0xC0000005) after finishing** |

The emulation test stops each NPC's StateTree in the PIE copy and runs the exact routine the new StateTree will run (plan, delay, move if required, idle, replan on the request, 2 s recover on failure) from Python, with real AI navigation, jumping the 30x clock to each period start (periods shortened to 100-150 s) plus the midnight crossing and the 21:00 / 06:00 transitions. Result: every prisoner followed its schedule in all 8 periods; exactly one replan per boundary; lockdown held (and no replan across midnight); movement was interrupted cleanly at boundaries (8 interruptions per prisoner over the day, including mid-move interruptions); 0 teleports, 0 stuck, 0 navigation failures, 0 repeated Move To at a destination; no capsule overlap (closest approach 68 cm). Doorway co-presence of 2+ NPCs within 200 cm was brief (Gate G1: 2.0 s east and 2.4 s west over the whole day; Door_Rec_EastLink 2.5 s; others below 2 s).
One earlier run of this test saw TRB01 stuck near Arch_Hub_East while heading to breakfast, then a navigation failure that recovered after 2 s; it did not recur in two later full runs. It is logged as a possible rare congestion event at the hub east arch, to be watched in the human PIE test.

Not yet testable until the manual edit: the real StateTree integration. After the edit run the same acceptance test against it: `powershell -File Tools\RunHeadless.ps1 -Script Tools\ScheduleRoutineEmulationTest.py -Log <abs log> -Env EMU_MODE=statetree`.

## 3. Changed assets and files
- Level `L_S01_LW_F1_Greybox.umap`: one actor added (`SCHED_S01_LW_F1`), NPC actors re-spawned identically by `PlaceNpcs.py`.
- New native code: `PrisonScheduleStateTree.{h,cpp}`; changed `PrisonScheduleComponent`, `PrisonScheduleSelect`, `CyberWarden.Build.cs` (AI and StateTree module dependencies, test-exclusion switch for the crash experiment).
- Tools: `PlaceNpcs.py` (places the manager), `ScheduleComponentPieTest.py`, `ScheduleRoutineEmulationTest.py`, `VerifyStateTreeNodes.py`, `ExitStress.ps1`, `ExitProbe.py`.
- Not touched: player, camera, input, GameMode, M1 geometry, navigation data, `Config/`, `ST_NPCRoutine`, `STT_ChooseNextStop`, `STT_ReportState`, animation Blueprints.

## 4. Manual StateTree steps (beginner friendly, about 20-30 minutes)
Do this once. Nothing here needs Blueprint nodes. Close and reopen the Unreal Editor first so it loads the newly built game module (if it asks to rebuild modules, click No; the DLL is already built).

**A. Open the tree.** In the Content Browser open `Content > CyberWarden > NPC` and double-click `ST_NPCRoutine`.

**B. The root state "Routine": swap the first task.**
1. Click the state **Routine** (the top state). In the Details panel find **Tasks**.
2. You will see `STT_ChooseNextStop`. Right-click it and choose **Delete**. (The asset itself stays in the project; the tree just stops using it. Red/unbound fields will appear in the child states; you fix them in steps C-E.)
3. Click the **+** next to Tasks, type **Prison** in the search box, and pick **Prison: Plan Destination**.
4. Open the new task. Its **Actor** field must show a chain/bound icon pointing to **Context > Actor**. If it is empty: right-click the field, **Bind > Context > Actor**.
5. If `STT_ReportState` is not in Routine's tasks, leave it alone (it is used in the child states).

**C. State "StartDelay".**
1. Click **StartDelay**. In its **Delay Task**, find **Duration**. Click the small chain icon at its left, choose **Routine > Prison: Plan Destination > Start Delay Seconds**.
2. In the state's **Transitions** list, find the row **On State Completed**. Change its target (currently "Next State") to **Next Selectable State**.

**D. State "MoveToStop".**
1. Click **MoveToStop**. In **Move To**, bind **Target Actor** to **Routine > Prison: Plan Destination > Target Actor** (chain icon). Keep **Acceptable Radius** = 60.
2. Find **Enter Conditions**, click **+**, choose **Bool Compare**. For its **Left** value use the chain icon and bind to **Routine > Prison: Plan Destination > Move Required**. Tick the **Right** checkbox (so it compares with true).
3. Keep the existing transition **On State Failed > Go to State > Recover**.

**E. State "IdleAtStop".**
1. Click **IdleAtStop**. In **Delay Task**, bind **Duration** to **Routine > Prison: Plan Destination > Idle Seconds**.
2. **Enter Conditions** > **+** > **Bool Compare**: bind **Left** to **Routine > Prison: Plan Destination > Plan Valid**, tick **Right**.
3. Keep **On State Completed > Go to State > Routine**.

**F. State "Recover".** No change (it must stay the LAST child, after IdleAtStop, with its 2 second delay and **On State Completed > Go to State > Routine**).

**G. The schedule-change transition (the only new transition).**
1. Click the root state **Routine** again. In **Transitions** click **+**.
2. Set **Trigger** to **On Tick**.
3. In the transition's **Conditions** click **+** and choose **Prison: Replan Requested**. Its **Actor** must be bound to **Context > Actor** (right-click the field, Bind, Context, Actor, if empty).
4. Set the transition target to **Go to State > Routine**.

**H. Compile and save.** Click **Compile** in the toolbar (it must say it succeeded; no red errors, no unbound input on the Delay and Move To tasks), then **Save**.

Final shape (for checking):
```
Routine                 task: Prison: Plan Destination          transition: On Tick + Replan Requested -> Routine
  StartDelay            ReportState "StartDelay" + Delay(Start Delay Seconds)   completed -> Next Selectable State
  MoveToStop            enter if Move Required; ReportState "Moving" + Move To(Target Actor, 60)   failed -> Recover
  IdleAtStop            enter if Plan Valid;   ReportState "Idle" + Delay(Idle Seconds)             completed -> Routine
  Recover               ReportState "NavFail" + Delay 2.0                                           completed -> Routine
```
What you should see when playing `L_S01_LW_F1_Greybox` (30x clock, 06:00 start): the editor overlay shows the prison time, the activity, each prisoner's destination and state; prisoners leave their cells for the wake-up stops, go to meals at the 07:00, 12:00 and 18:00 changes, work/recreate, and are back in their cells after 21:00 and stay there until 06:00. To skip ahead, pause and set the time from Python (the tests do this) or wait: one game hour is 2 real minutes.

Then tell me it is done; with the editor closed I run the real-StateTree acceptance test (command in section 2).

## 5. Remaining risks
- The shutdown crash is unresolved (separate document).
- StateTree "Next Selectable State" and the two enter conditions are the only structural assumptions about the editor; if any option has a different name in your editor, tell me what you see.
- The very first start delay is now each prisoner's stagger (2 / 8 / 0 / 5 s) instead of the legacy 6 / 14 / 3 / 9 s start delays; the legacy NPC variables are no longer used by the tree.
- Rare hub-east-arch congestion event (section 2) and brief Gate G1 co-presence need the human visual PIE check before milestone closure.
