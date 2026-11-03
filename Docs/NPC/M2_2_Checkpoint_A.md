# M2.2 Checkpoint A - C++ prisoner schedule foundation

Branch `m2-2-cpp-clock`, starting at `4d3686f`. Scope: investigate the headless exit crash, fix the animation verifier, add the C++ schedule component. The NPC StateTree, `STT_ChooseNextStop`, `STT_ReportState` and `ST_NPCRoutine` are NOT touched; nothing connects scheduling to NPC movement yet.

## 1. Headless exit crash: findings (UNRESOLVED)

Symptom: a headless `UnrealEditor-Cmd` run finishes all its work, logs `LogExit: Exiting.` and `Log file closed`, and then the process dies with an access violation.

| Evidence | Result |
|---|---|
| Git Bash, C++ module loaded, scripts run | exit 139 (SIGSEGV) in about 4 of ~50 runs (`ValidateSchedule`: 1/8 with `timeout`, 1/12 without it; earlier runs 2 more) |
| Git Bash, `quit_only` script (module loaded) | 0 / 8 |
| Git Bash, pre-C++ baseline project (worktree of `pre-cpp-baseline`), `ValidateSchedule` | 0 / 16 (and ~40 earlier pre-C++ runs of other scripts: 0 crashes) |
| PowerShell launcher, C++ module loaded, script really executed | **1 / 24: exit -1073741819 = 0xC0000005 (access violation)** |
| In every failing run's log | the script finished and wrote its RESULT line; the engine logged a normal shutdown (`Exiting.`, `Log file closed`) before the process died |
| Windows Application event log / crash dumps / `Saved/Crashes` | nothing recorded for these crashes (the crash handler is already gone at that point) |

Corrections made during the investigation:
- My first PowerShell comparison (36 runs, "0 crashes") was INVALID: `-ExecutePythonScript="C:\Users\ricky\..."` is read with `\r` as an escape, so the script never loaded and the runs ended early. `Tools/RunHeadless.ps1` now passes forward slashes. Do not quote that earlier number.
- Running several Unreal instances in parallel is unsafe here: batches of 4 and then 2 simultaneous headless editors hung forever at `LogPython: Using Python 3.11.8` (about 75 min and 30 min lost). Run headless scripts one at a time.

What this means:
- The tests are genuinely passing before the crash (their RESULT lines are in the logs), so cleanup is not hiding a runtime failure. All results in this document were produced by runs whose results lines were read.
- The fault is real and native (0xC0000005 from PowerShell), not only a Git Bash artifact.
- It is only seen with the C++ module present (0 / ~56 pre-C++ runs vs ~5 / ~75 with it), but the sample is too small and the A/B experiment was not completed, so the module is a suspect, not a proven cause. I reviewed the module's shutdown path and found no defect: no threads, no static objects with non-trivial destructors apart from engine-standard module and automation-test registrations; the delegate and the component hold no raw pointers across teardown.
- Probable cause (unproven): an exit-time static/DLL teardown fault. Most likely suspects are the statically registered automation tests (`IMPLEMENT_SIMPLE_AUTOMATION_TEST`) or the module DLL unload order.
- Severity: low for the game (editor/headless tooling only, after all work is done, no data written after the log closes, no effect on a shipped build as far as can be told), but it can break CI-style scripts that check exit codes. Not harmless until explained.
- Not done (needs another ~30 min of serial runs, or a debugger): rebuild without `Tests/`, run 40+ serial runs and compare; or capture a dump (needs WER LocalDumps, which needs administrator rights, or WinDbg).
- Mitigation now: use `Tools/RunHeadless.ps1` (real exit code, forward-slash paths). Treat a missing RESULT line, not the exit code alone, as a test failure.

## 2. Animation verifier
`Tools/VerifyNpcFoundation.py` now expects the NPC mesh to use `ABP_PrisonNPC_C` and the player (`BP_CyberWardenCharacter`) to use `ABP_Unarmed_C`. All other checks are unchanged. Result: 33 / 33.

## 3. C++ schedule architecture
| Piece | Role |
|---|---|
| `UPrisonScheduleData` (UDataAsset) with `FPrisonPeriodDef`, `FPrisonPeriodAssignment`, `FPrisonNpcSchedule` | The ONE in-engine copy of the periods and per-NPC assignments (marker ids, idle range, stagger fraction). Generated from `Docs/Layout/S01_LW_F1_schedule.json`, which stays the source of truth. Has structural validation (`ValidateData`). |
| `/Game/CyberWarden/Schedule/DA_S01_LW_F1_Schedule` | The generated asset (8 periods, 4 NPC schedules, 0 validation errors). |
| `APrisonScheduleManager` (extended) | New `ScheduleData` reference; periods, names and start hours are now taken from it (no duplicated period list); new derived `PeriodIds`. Clock behaviour unchanged. |
| `PrisonScheduleSelect` (pure functions) | Stop choice (never repeats the previous stop when there are several; single stop flagged; reversed idle range repaired; empty or null assignment fails safely) and stagger maths. Unit tested without a world. |
| `UPrisonScheduleComponent` (on `BP_PrisonNPC`) | Finds the manager (property or tag), reads its NPC id from the owner's `NpcId` (or `NpcIdOverride`), detects period changes, waits the deterministic stagger (fraction x `StaggerMaxGameMinutes`, measured in game seconds), raises a ONE-SHOT replan request, plans a destination, exposes diagnostics. Never moves the NPC. |

Component API: `PlanForCurrentPeriod()` (returns `FPrisonDestination`: valid, marker id, marker actor, idle real seconds, move required, single stop, period index, reason; it also acknowledges the request), `AcknowledgeReplan()`, `IsReplanRequested()`, `GetStaggerRealSeconds()`, `ResolveMarker()`, `ValidateAssignments()`, `RefreshContext()`. Diagnostics (Blueprint/Python readable): `ResolvedNpcId`, `bHasSchedule`, `AppliedPeriodIndex/Name`, `ManagerPeriodIndex`, `CurrentStopMarkerId`, `CurrentIdleSeconds`, `StaggerGameSeconds`, `bStaggerPending`, `bReplanRequested`, `ReplanSerial`, `ReplanAckCount`, `PlanCount`, `PeriodChangeObservedAt`, `LastDiagnostic`.

Rules implemented: one request per schedule change (a second change while a request is pending only updates the target; the plan uses the latest period); the request is raised only after the first plan has set the applied period; a clock moved backwards restarts the stagger; a period change that reverts before the stagger elapses cancels the wait; a single-destination period returns `bMoveRequired = false` when the NPC is already within `ArrivalRadius` (150 cm) of the marker so no repeated movement request is needed; markers are resolved from the level tags `MarkerId:<id>` (existing marker naming unchanged) and must carry `NavDest:Yes`.

## 4. Automated test results
| Test | Result |
|---|---|
| C++ build (`Tools/BuildCpp.ps1`) | Succeeded |
| Native automation tests `CyberWarden.Prison.ClockMath`, `.ScheduleSelect`, `.ScheduleData` | 3 / 3 Success |
| `Tools/ConfigureSchedule.py` | Data asset 8 periods / 4 NPCs / 0 errors; manager slot table equals the Python reference table |
| `Tools/VerifySchedule.py` | 23 / 23 |
| `Tools/VerifyNpcFoundation.py` | 33 / 33 |
| `Tools/ScheduleComponentPieTest.py` (headless PIE, all four prisoners, clock stepped from Python) | **79 / 79** |
| `Tools/NpcPopulationTest.py`, 400 game seconds (existing routes) | PASS: loops EXP01 5, QUI01 3, TRB01 4, WRK01 14; 0 navigation failures, 0 stuck, 0 teleports, 0 repeated StartDelay, no overlap (closest 68 cm) |

What the 79 checks cover:
- all four NPCs resolve their schedule and the data asset equals the JSON for all 8 periods;
- every scheduled destination exists in the level and is `NavDest:Yes`;
- stagger is 60 / 240 / 0 / 150 game seconds (2 / 8 / 0 / 5 real seconds at 30x) and the replan fires after exactly that long (5 s test steps);
- exactly one replan per change, none without a change, acknowledgement clears it;
- lockdown change at 21:00 detected once; destination is the NPC's own cell marker; no replan while lockdown continues across midnight; one new request when lockdown ends at 06:00;
- an NPC already standing at its only breakfast stop gets the same stop with no movement requested;
- an unknown NPC id and a manager without schedule data fail safely with a reason and without crashing.

Test-harness note: setting a property on a placed Blueprint component from Python re-runs the owning actor's construction and replaces the component object; the test re-fetches the component after each such edit (an earlier version failed three checks because it kept a stale reference).

## 5. Files and assets changed
- Added: `Source/CyberWarden/{Public,Private}/PrisonScheduleData|PrisonScheduleSelect|PrisonScheduleComponent`, `Private/Tests/PrisonScheduleTest.cpp`, `Content/CyberWarden/Schedule/DA_S01_LW_F1_Schedule.uasset`, `Tools/AddScheduleComponent.py`, `Tools/ScheduleComponentPieTest.py`, `Tools/RunHeadless.ps1`, this document.
- Modified: `PrisonScheduleManager.{h,cpp}` (ScheduleData, PeriodIds), `Tools/ConfigureSchedule.py` (generates the data asset), `Tools/VerifyNpcFoundation.py`, `Content/CyberWarden/Schedule/BP_PrisonScheduleManager.uasset` (references the data asset), `Content/CyberWarden/NPC/BP_PrisonNPC.uasset` (one added component `PrisonSchedule`).
- Not touched: level, navigation, M1 geometry, player, camera, input, GameMode, `Config/`, `BP_NPCController`, `STT_*`, `ST_NPCRoutine`, `ABP_*`.

## 6. Remaining StateTree work (Checkpoint B, not started)
1. Place the schedule manager in the level (extend `PlaceNpcs.py`) so NPCs find it without the test spawn.
2. A C++ StateTree task (or Blueprint task calling the component) that, on enter, calls `PlanForCurrentPeriod()` and outputs `TargetActor`, `IdleSeconds` and `bMoveRequired` with the same output names the Delay and Move To tasks already bind to; empty plan -> the existing Recover/NavFail path.
3. Skip `MoveToStop` when `bMoveRequired` is false (condition on the state).
4. One transition on `Routine` (On Tick, condition `IsReplanRequested` true -> go to `Routine`), replacing today's endless route loop; the first start delay and the `STT_ReportState` labels stay.
5. Manual editor work: swap the task in `ST_NPCRoutine`, rebind its outputs, add the transition and the condition (about 20-30 minutes, no Blueprint nodes).

## 7. Risks needing approval before Checkpoint B
- The exit crash is unexplained (section 1). Decide whether to spend about 30 serial minutes on the A/B (tests removed), or to proceed and treat exit codes as advisory.
- Existing integer-typed variables (idle seconds etc.) truncate fractional seconds; the schedule data uses whole seconds, so it works, but new C++ outputs should use real numbers and the StateTree bindings must accept them.
- Meal and lockdown periods have one stop: with `bMoveRequired` the NPC idles repeatedly in place; confirm that is the desired look (alternative: longer idles).
- Many NPCs leaving at 06:00 / 21:00 may still bunch at cell doors and Gate G1 despite the stagger; to be measured in Checkpoint B.
