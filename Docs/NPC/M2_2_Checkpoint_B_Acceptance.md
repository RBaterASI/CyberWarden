# M2.2 Checkpoint B - acceptance against the REAL StateTree

`ST_NPCRoutine` was edited by hand (native `Prison: Plan Destination` task, enter conditions, `Prison: Replan Requested` on-tick transition). All Unreal processes were run serially, one at a time, with `Tools/RunHeadless.ps1` (real exit codes). No code or asset was changed during this test pass.

## Results
| Test | Result | Process exit |
|---|---|---|
| `ScheduleRoutineEmulationTest.py`, `EMU_MODE=statetree`, run 1 (full day: 8 period changes, midnight, dawn) | PASS 96 / 96 | 0 |
| Same, run 2 | **95 / 96**: one stuck window (EXP01 at Gate G1, see below); everything else passes | 0 |
| `NpcAnimProbe.py` (150 game s, real StateTree) | PASS 20 / 20 | 0 |
| `ScheduleRecoveryTest.py` (real tree; Work_Servery_N moved off the navmesh in the PIE copy) | PASS 9 / 9 | 0 |
| Earlier in this milestone: `VerifyNavigation.py` 0 failures | results complete, **process crashed at exit (0xC0000005)** | -1073741819 |

Every exit code above is the real process code; the one crash is the tracked shutdown defect (`M2_2_Shutdown_Crash.md`) and is reported as "complete, process crashed", not as an unconditional pass.

## What the real tree does (run 1 and run 2)
- **Schedule transitions:** all four prisoners went to their own assignment in every period (wake-up, breakfast, work, lunch, recreation, evening meal, free time, lockdown) with exactly one replan per period change and none while lockdown continued across midnight (replan counts per segment: 0 for the first segment and the midnight segment, 1 for every real boundary, for all four NPCs).
- **Lockdown:** all four were inside their own cells at the end of lockdown; QUI01 (already inside its radius) correctly did not move; no replan across 23:58 -> 00:04; at 06:00 each replanned once after its stagger and left the cell.
- **Navigation:** 0 navigation failures and 0 teleports in both runs; Move To was never requested while already at the destination.
- **Movement interrupted by a boundary:** mid-move boundaries (for example EXP01 work -> lunch, EXP01 and WRK01 recreation -> dinner, EXP01 free -> lockdown) ended at the NEW period's stop with no failure; the Move To is aborted by leaving the root state and a new one starts from where the NPC stands.
- **Animations:** all four use `ABP_PrisonNPC`; in thousands of settled samples the animation Blueprint's `ShouldMove` was true with `GroundSpeed` equal to the real speed while walking (701/701, 340/340, 1032/1032, 385/385) and false with `GroundSpeed` ~0 while standing (1409/1409, 1876/1876, 984/984, 1832/1832); 4-26 walk/stand transitions per prisoner. Limitation: foot-bone motion cannot be measured headless (no pose evaluation without rendering), so the visible walk cycle still needs the human PIE check.
- **Recovery:** with an unreachable counter, WRK01's failed Move To was reported (NavFail state, counter +12 in 160 world s), the Recover state waited, the routine re-planned and WRK01 kept serving the reachable counter; plans 24 in 160 s (no restart storm), 0 teleports, the other prisoners had 0 failures. The failure repeats about every 11 s while the bad stop remains in the schedule (bounded by the idle time + 2 s recover); the schedule validator already rejects unreachable stops statically.
- **Stability:** no `Plan Destination` warnings in the logs; plan counts stayed proportional to movements (no restart loops).
- **Proximity:** no capsule overlap in either run (closest approach 68 cm).

## Open finding: transient stall at Gate G1 (run 2)
`STUCK EXP01 at (3130, 494)` - inside the 400 cm Gate G1 passage (east door at x = 3200) while EXP01 was walking, flagged by a 5 s window with less than 40 cm of progress. Four prisoners were within the gate area (2+ within 200 cm of Gate G1 east for 3.3 s and west for 4.1 s). EXP01 resumed on its own, reached its destination and no navigation failure was raised. It did not occur in run 1, which had similar gate co-presence (3.5 s / 3.9 s). Earlier driver-based runs showed one similar stall near the Hub-East arch that also resolved itself. Interpretation: RVO avoidance momentarily blocks two NPCs meeting head-on in a doorway; it resolves within seconds. Not changed. Needs the human visual check at Gate G1 and the hub arches; options if it looks wrong in play: larger stagger, a bit more door clearance, or lowering the acceptance of simultaneous departures at 06:00 / 21:00.

## Not covered by headless tests
- The visible walk/idle pose (human PIE check).
- Long real-time play at 1x for hours (periods were shortened and the clock jumped).
- The shutdown crash remains unresolved and tracked.
