# M2.2 - Prison Daily Routine System: closure

Status: **approved** by the project owner after the manual Play In Editor visual acceptance test (prisoner movement, animations and general navigation behaviour all looked good). Tag: `m2-2-daily-routine-approved`.
Branch history: `m2-2-daily-routine` (Stage 1) -> `m2-2-cpp-clock` (C++ foundation, Checkpoints A and B, StateTree integration). Last validated commit before closure: `729bf52`. Baseline before the C++ transition: tag `pre-cpp-baseline` (`147cce1`).

## Delivered
- **Hybrid C++ + Blueprint architecture** (approved decision): C++ runtime module `CyberWarden` built with the Visual Studio 2022 Build Tools (MSVC 14.44, Windows SDK 22621, .NET Framework 4.8 SDK) and `Tools/BuildCpp.ps1`; `Tools/RunHeadless.ps1` runs headless Python with the real exit code.
- **Prison clock and schedule**: `APrisonScheduleManager` (30x default clock from 06:00, pause/resume, accumulated game time, midnight wrap, 48-slot half-hour lookup, test controls), `UPrisonScheduleData` (periods + per-NPC assignments generated from `Docs/Layout/S01_LW_F1_schedule.json`), `BP_PrisonScheduleManager` placed once in the Sector 01 level (`SCHED_S01_LW_F1`).
- **Per-prisoner logic**: `UPrisonScheduleComponent` on `BP_PrisonNPC` (period-change detection, deterministic stagger, one-shot replan request, destination planning, back-off, safe handling of empty or unknown assignments).
- **Native StateTree nodes**: `Prison: Plan Destination` and `Prison: Replan Requested`; `ST_NPCRoutine` integrated by hand (enter conditions, on-tick replan transition). Existing Delay, Move To, `STT_ReportState` (including the StartDelay label fix), Recover state, avoidance and animation preserved.
- **Schedule (approved)**: Wake-up 06:00, Breakfast 07:00, Work 08:00, Lunch 12:00, Recreation 13:00, Evening meal 18:00, Free time 19:00, Lockdown 21:00 to 06:00; per-NPC assignments for EXP01, QUI01, TRB01, WRK01 (`Docs/NPC/M2_2_Schedule_Design.md`).
- Documentation: `Docs/NPC/M2_2_*.md`.

## Final automated results
| Test | Result |
|---|---|
| C++ module build (`Tools/BuildCpp.ps1`) | Succeeded (last build on the committed sources) |
| Native automation tests `CyberWarden.Prison.*` | 3 / 3 Success |
| Clock live test (PIE) on the C++ class and on the Blueprint child | 10 / 10 each |
| `ValidateSchedule.py` / `VerifySchedule.py` / `VerifyNpcFoundation.py` / `VerifyStateTreeNodes.py` | 24/24, 23/23, 33/33, 8/8 |
| `ScheduleComponentPieTest.py` (placed manager, four prisoners) | 87 / 87 |
| `ScheduleRoutineEmulationTest.py` with the Python driver, full day with real navigation | 96 / 96 |
| **Same test against the real StateTree (`EMU_MODE=statetree`)** | run 1: 96 / 96; run 2: 95 / 96 (one transient stall, below) |
| `NpcAnimProbe.py` (real tree) | 20 / 20 (ShouldMove and GroundSpeed matched the real movement in every settled sample) |
| `ScheduleRecoveryTest.py` (real tree, unreachable stop) | 9 / 9 |
| `VerifyNavigation.py` | 0 marker failures, all NPC legs OK |
| Human visual PIE acceptance | **Approved** |

Not re-run at closure: your Unreal Editor was open (Live Coding blocks `BuildCpp.ps1`, and headless runs were not started next to the open editor), so the build and the Python tools were not re-executed after the final commit. They were last run on the same sources (no `Source/` or tool changes since the last build and test pass) and the editor loaded the built module for the visual test.

## Tracked issues
1. **Headless Unreal shutdown access violation (UNRESOLVED, technical issue, separate from this milestone's behaviour).** After a completed run and a normal engine shutdown log, the process sometimes dies with `0xC0000005` (exit 139 from Git Bash, -1073741819 from PowerShell). Seen only with the C++ module loaded; controlled serial A/B (40 runs): 1/20 with the native automation tests, 2/20 without, so the tests are not the cause. Not fixed, not diagnosed (a dump needs administrator rights or a debugger). A run that completes but crashes at exit is reported as "complete, process crashed", never as an unconditional pass. Details: `Docs/NPC/M2_2_Shutdown_Crash.md`, data `Docs/NPC/M2_2_ExitStress_results.csv`.
2. **Gate G1 transient stall (LOW priority, monitor).** In one of two real-StateTree acceptance runs EXP01 stopped for over 5 seconds inside the Gate G1 passage while four prisoners converged, then resumed on its own with no navigation failure; a similar self-resolving stall was seen once near the Hub-East arch in an earlier driver-based run. Likely momentary avoidance (RVO) blocking in the doorway. Watch it when the population grows (more prisoners, guards); mitigations if it worsens: larger departure stagger, more door clearance, fewer simultaneous departures at 06:00 and 21:00.
3. Minor: the legacy integer-typed `BP_PrisonNPC` timing variables remain (unused by the new tree); new native timing outputs use real numbers.
4. Do not run several headless Unreal instances in parallel on this machine (they deadlock at Python startup).

## Preservation check (versus `main` at `9ec23b8`)
Unchanged: `Content/ThirdPerson` (player character, GameMode), `Content/Input`, `Content/Characters` (including `ABP_Unarmed` and `ABP_PrisonNPC`), `Config/`, M1 layout (`Docs/Layout/S01_LW_F1.json`), the greybox builder, `Tools/BakeNavigation.py`, the navigation report and the materials. Intended changes only: `CyberWarden.uproject` (the C++ module entry), the Sector 01 level (one added schedule-manager actor; NPC actors re-spawned identically; baked navigation untouched), NPC and schedule assets, `Source/`, tools and docs.

## Carried forward
Guard AI, ARC, Rails and sector AI on the same hybrid architecture; population expansion (watch Gate G1); resolve the shutdown access violation (dump or debugger); consider retyping the legacy integer variables; optional automated StateTree generation experiment.
