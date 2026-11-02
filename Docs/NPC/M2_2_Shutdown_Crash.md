# Headless shutdown crash (access violation after a completed run): bounded A/B investigation

Status: **UNRESOLVED, tracked.** Not caused by the native automation-test registration. No evidence of gameplay/runtime instability.

## Symptom
A headless `UnrealEditor-Cmd` run finishes its workload, logs `LogExit: Exiting.` and `Log file closed`, then the process dies with `0xC0000005` (access violation; reported as exit 139 by Git Bash, as `-1073741819` by PowerShell). Windows writes no crash dump or Application event, and `Saved/Crashes` stays empty.

## Controlled serial A/B experiment (`Tools/ExitStress.ps1`, `Tools/ExitProbe.py`)
- One Unreal process at a time (parallel headless instances deadlock at Python startup on this machine: 4 and then 2 simultaneous instances hung indefinitely).
- 40 runs, strictly interleaved A, B, A, B ... so machine drift affects both arms equally.
- Arm A = production module (native automation tests registered, DLL sha B41324CB). Arm B = module built with `CW_NO_TESTS=1`, tests compiled out (sha 1239884C). The DLL actually installed is hashed before every run and recorded.
- Same fixed launcher and workload in every run: `ExitProbe.py` asserts the C++ classes (`PrisonScheduleManager`, `PrisonScheduleComponent`, `PrisonScheduleData`) exist, then runs `ValidateSchedule.py` (24 checks).
- Recorded separately per run: module loaded, workload completion marker, normal-shutdown log line, real process exit code, signature. Raw data: `Docs/NPC/M2_2_ExitStress_results.csv`.

| Arm | Runs | Module loaded | Workload completed | Shutdown logged | Access violations |
|---|---|---|---|---|---|
| A (tests registered) | 20 | 20 | 20 | 20 | 1 (run 15) |
| B (tests compiled out) | 20 | 20 | 20 | 20 | 2 (runs 26, 38) |

Reading: every crashing run had completed its workload and logged a normal shutdown. Removing the test registration did not reduce the crash rate (5% vs 10%; the difference is within noise). **The automation tests are not the cause.**

All observations so far (every one with the C++ module loaded): PowerShell 1/24 (earlier batch), 3/40 (this experiment), 1/~12 (the final `VerifyNavigation` regression run); Git Bash about 4/50. Pre-C++ baseline through Git Bash: 0/16 plus about 40 earlier runs. The module is therefore still a suspect, but the pre-C++ sample is small and no pre-C++ PowerShell run was made, so the module is not proven to be the cause.

## What was ruled out or checked
- The Git Bash launcher: PowerShell shows the same access violation.
- The native automation tests: arm B crashes.
- Runtime/gameplay faults: the crash always follows a completed workload and a logged normal engine shutdown; all runtime assertions in this milestone passed in runs whose results lines were read.
- Module shutdown code review: no threads, no raw UObject pointers held across teardown, delegate is an ordinary member; the module is the stock `FDefaultGameModuleImpl`.

## Not possible without unsafe changes
A dump cannot be captured at this point of teardown without enabling WER LocalDumps (needs administrator rights and a system registry change) or installing a debugger (WinDbg). Neither was done.

## Classification and handling
- Unresolved shutdown defect, low severity for gameplay (tooling only, after all work is done), but it can fail CI-style checks.
- Rule: a run whose process exits nonzero is never recorded as an unqualified PASS. Reports say "PASS, process crashed at exit" and give the exit code. `Tools/RunHeadless.ps1` returns the real exit code and the result line is read from the log.
- Next steps if it must be eliminated: capture a dump (administrator or WinDbg), then test a module-less project against this build with the same launcher for a fair baseline, and try engine plugins that could unload after the module (Python, Chaos Visual Debugger) disabled one at a time.

## Production configuration restored
`CW_NO_TESTS` is unset; the committed module builds with the automation tests (`CyberWarden.Prison.*`, 3 tests, all pass).
