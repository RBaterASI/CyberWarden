# M2.2 - C++ foundation and prison clock proof of concept

Branch `m2-2-cpp-clock` (from `m2-2-daily-routine`). Rollback baseline: tag `pre-cpp-baseline` (147cce1, Blueprint-only project).
Approved decisions: hybrid C++ + Blueprint; VS 2022 Build Tools; VS Code + Claude/Codex workflow; clock-only proof of concept; StateTree generation deferred.

## What changed
| Item | Detail |
|---|---|
| `CyberWarden.uproject` | Added the `Modules` entry for the runtime module `CyberWarden`. Nothing else. |
| `Source/` | `CyberWarden.Target.cs`, `CyberWardenEditor.Target.cs`, module `CyberWarden` (`Build.cs`, module class, log category). Dependencies: Core, CoreUObject, Engine only. |
| `PrisonClockMath` | Pure, unit-testable clock math: wrap, slot (half hour), 48-slot period table with the overnight wrap, `HH:MM:SS` formatting. |
| `APrisonScheduleManager` | The clock actor. Config: `TimeScale` (30), `bPaused`, `GameSecondsTotal` (accumulated, default 21600 = 06:00), `StaggerMaxGameMinutes` (5), `PeriodNames`, `PeriodStartHours`. Derived/runtime (read-only in Blueprints): `SlotToPeriod`, `ClockSeconds`, `CurrentHour`, `CurrentPeriodIndex`, `CurrentPeriodName`, `DayNumber`, `PeriodChangeCount`, `LastPeriodIndex`, `OnPeriodChanged` delegate. Test-friendly controls: `PauseClock`, `ResumeClock`, `SetTimeScale`, `SetTimeOfDayHours`, `SetGameSecondsTotal`, `JumpToPeriod(index, offset)`, `AdvanceGameSeconds`, `GetClockString`, `RebuildSlotTable`. Pausing or changing the scale never resets the accumulated time. Tagged `S01F1ScheduleManager` (the overlay finds it by tag). |
| `BP_PrisonScheduleManager` | Replaced the empty Stage 1 shell (nothing referenced it: only Python tools and docs) with a Blueprint child of the C++ class that carries the defaults from `S01_LW_F1_schedule.json`. **No graph wiring is required any more.** |
| `Tools/ConfigureSchedule.py`, `VerifySchedule.py`, `ClockPieTest.py` | Adapted to the C++ class (Python property names are snake_case, e.g. `time_scale`, `paused`). The JSON schedule and `ValidateSchedule.py` are unchanged. |
| `Tools/BuildCpp.ps1` | Builds the editor target. Run it before headless `UnrealEditor-Cmd` scripts. |
| `Source/CyberWarden/Private/Tests/PrisonClockMathTest.cpp` | Native automation test `CyberWarden.Prison.ClockMath`. |

The manual Tick-graph instructions (section 5 of `M2_2_Schedule_Design.md`) are obsolete.

## Toolchain (installed during this step)
Visual Studio 2022 Build Tools 17.14 with: `VC.14.44.17.14.x86.x64`, `Windows11SDK.22621`, `Microsoft.Net.Component.4.8.SDK` (the engine needs the NetFx SDK directory), plus the latest `VC.Tools.x86.x64`. UnrealBuildTool reports `Win64 VALID 10.0.22621.0` and builds with "Visual Studio 14.44.35229 toolchain" (the folder is named 14.44.35207, but the compiler is 35229, past the engine's banned 14.44.0-35210 range). Commands:
```
winget install --id Microsoft.VisualStudio.2022.BuildTools --exact --override "--quiet --wait --norestart --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows11SDK.22621 --add Microsoft.Net.Component.4.8.SDK"
powershell -File Tools\BuildCpp.ps1
```
Build output (`Binaries/`, `Intermediate/`) is git-ignored: every clone must build once.

## Results
| Test | Result |
|---|---|
| C++ module build (`CyberWardenEditor Win64 Development`) | Succeeded (first full build 52 s) |
| Native automation test `CyberWarden.Prison.ClockMath` | Success |
| Live clock test (PIE) vs the C++ class | 10/10 (plus the optional change counter) |
| Live clock test vs `BP_PrisonScheduleManager` (the asset the project uses) | 10/10 |
| `ValidateSchedule.py` (schema, 48 slots, midnight wrap, assignments) | 24/24, 0 problems |
| `VerifySchedule.py` (asset persistence, C++ slot table equals the Python table) | 23/23 |
| `VerifyNavigation.py` | 0 marker failures, all NPC legs OK |
| Four-prisoner PIE test, 400 game seconds | PASS: loops 5/3/4/15, 0 navigation failures, 0 stuck, 0 teleports, 0 repeated StartDelay; min pair distance 68 cm, no overlap |
| `InspectNpcAssets.py` | NPCs on `ABP_PrisonNPC`, player on `ABP_Unarmed`, four NPCs placed with their routes |

Notes:
- `VerifyNpcFoundation.py` reports 31/32: its "anim class = ABP_Unarmed" expectation predates the approved `ABP_PrisonNPC` (M2.1B); unrelated to C++.
- Some headless runs exit with code 139 (segmentation fault) *after* "LogExit: Exiting" and after all results are written; no crash report is created. It appeared in 2 of about 10 runs with the C++ module loaded (the same scripts always exited 0 before). Under observation, not understood yet.
- No approved asset changed: the only asset diff is the replaced `BP_PrisonScheduleManager`. `Config/`, the player, camera, input, GameMode, M1 geometry, navigation and NPC assets are untouched.

## Rollback
1. Uncommitted: delete `Source/`, `Binaries/`, `Intermediate/` and restore `CyberWarden.uproject`.
2. Committed on the branch: `git checkout m2-2-daily-routine`, delete `m2-2-cpp-clock`, remove leftover untracked `Source/`, `Binaries/`, `Intermediate/`.
3. Anything else: `git checkout pre-cpp-baseline` (or the folder copy). The Build Tools can stay installed.
