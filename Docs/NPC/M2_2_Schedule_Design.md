# M2.2 - Prison Daily Routine System: design and Stage 1 foundation

> **Update:** the clock now lives in C++ (`APrisonScheduleManager`, see `M2_2_Cpp_Foundation.md`). Section 5 (manual Tick graph) is obsolete; the rest of this design still applies.

Status: **Stage 1 only** (data, validators, manager shell, clock tests, overlay). `STT_ChooseNextStop`, `ST_NPCRoutine`, `BP_PrisonNPC` and the placed NPCs are unchanged: the four prisoners still run their M2.1B routes. Stage 2 (assignment-driven routing) and Stage 3 (boundary response) are not started.

## 1. Approved architecture (minimal hybrid)
JSON configuration (`Docs/Layout/S01_LW_F1_schedule.json`) -> Python writes the asset data -> `BP_PrisonScheduleManager` (Blueprint, one per sector) holds an accumulating clock and a 48-slot (half-hour) period table -> NPCs (Stages 2/3) read the manager through a reference and the reusable StateTree re-plans on a period change. No C++.

## 2. Timing (corrected)
The earlier assessment quoted a 15 game-minute stagger of about 7.5 real seconds. That was wrong at any scale. Approved: **maximum stagger 5 game minutes = 10 real seconds at 30x**.

| Quantity | Default 30x | Dev 120x |
|---|---|---|
| 1 game hour | 120 s | 30 s |
| Full day | 48 min | 12 min |
| Wake-up / Breakfast / Lunch / Evening meal (1 h each) | 120 s | 30 s |
| Free time (2 h) | 240 s | 60 s |
| Work (4 h) / Recreation (5 h) | 480 s / 600 s | 120 s / 150 s |
| Lockdown (21:00-06:00, 9 h) | 1080 s | 270 s |
| Stagger, max 5 game min | 10 s | 2.5 s |

Per-NPC stagger (`stagger_fraction x 5 min`): EXP01 0.20 = 1 game min = 2 s; QUI01 0.80 = 4 min = 8 s; TRB01 0.00 = 0 s; WRK01 0.50 = 2.5 min = 5 s (real seconds at 30x).
NPC walking speed and idle timers are **not** scaled by the clock. At 120x a 35-70 s trip exceeds a 30 s period, so 120x is for clock, boundary and logic tests only; arrival acceptance uses 30x.

## 3. Created assets and data (Stage 1)
| Item | Purpose |
|---|---|
| `Docs/Layout/S01_LW_F1_schedule.json` | Clock settings, 8 periods, PROPOSED per-NPC assignments (section 7). Lockdown (21:00) wraps midnight until the first period (06:00). |
| `Content/Python/cw_schedule.py` | Loader, schema validation, 48-slot table, period lookup, `ClockModel` (reference model of the Blueprint Tick). |
| `/Game/CyberWarden/Schedule/BP_PrisonScheduleManager` | Actor Blueprint shell: variables and defaults only, EMPTY graph. Tagged `S01F1ScheduleManager`. NOT placed in any level yet. |
| `Tools/ConfigureSchedule.py` | Creates the shell if missing; otherwise only rewrites default VALUES from the JSON (never touches graphs). |
| `Tools/ValidateSchedule.py` | Schema, period lookup, midnight wrap, clock model, marker/assignment validation, timing report to `Docs/Layout/S01_LW_F1_schedule_report.txt` (24 checks, PASS). |
| `Tools/VerifySchedule.py` | Fresh-process check that the asset persisted with the right defaults (21 checks, PASS). |
| `Tools/ClockPieTest.py` | Headless PIE clock test for the wired Tick graph (section 6). |
| `Content/Python/cw_npc_debug.py` (updated) | Editor-only overlay: clock line plus per-NPC Activity / Dest / State. Needs an editor restart to load. |

## 4. Manager variables (`BP_PrisonScheduleManager`)
Real numbers are true doubles (type "real", see finding F1).

| Variable | Type | Editable | Default | Meaning |
|---|---|---|---|---|
| `TimeScale` | real | yes (Clock) | 30.0 | game seconds per real second (120 for dev) |
| `Paused` | bool | yes (Clock) | false | freezes the clock |
| `GameSecondsTotal` | real | yes (Clock) | 21600.0 (06:00) | unwrapped accumulator; its default is the start time; never reset by pause or scale changes |
| `StaggerMaxGameMinutes` | real | yes (Clock) | 5.0 | used by NPCs in Stage 3 |
| `PeriodNames` | String[] | yes (Schedule) | 8 names | |
| `PeriodStartHours` | real[] | yes (Schedule) | 6,7,8,12,13,18,19,21 | display only |
| `SlotToPeriod` | int[48] | yes (Schedule) | generated | half-hour slot -> period index; slots 00:00-05:59 are Lockdown (midnight wrap is in the table) |
| `ClockSeconds` | real | no (Runtime) | 21600 | `GameSecondsTotal` wrapped to 0..86400 |
| `CurrentHour` | real | no | 6.0 | ClockSeconds / 3600 |
| `CurrentPeriodIndex` | int | no | 0 | |
| `CurrentPeriodName` | String | no | "Wake-up" | |
| `PeriodChangeCount`, `LastPeriodIndex` | int | no | 0, 0 | optional graph part B |

## 5. MANUAL STEP: wire the Tick graph (about 15 nodes)
Open `Content/CyberWarden/Schedule/BP_PrisonScheduleManager` > **Event Graph**. Everything is a plain variable of this Blueprint (drag from the My Blueprint panel: click = *Get*, Alt+click = *Set*).

**Part A (required)**, one execution chain:
1. Right-click > **Event Tick** (output *Delta Seconds*).
2. Exec pin > **Branch**. Condition = **NOT Boolean** of `Paused`. Continue from **True** (the clock only advances while not paused).
3. **Set Game Seconds Total** = `GameSecondsTotal` **+** ( *Delta Seconds* **x** `TimeScale` ). Do not wrap here: the accumulator is unwrapped.
4. **Set Clock Seconds** = **FMod**( `GameSecondsTotal`, **86400.0** ) (search "FMod", the float modulo node). Use the Get of `GameSecondsTotal` after step 3.
5. **Set Current Hour** = `ClockSeconds` **/** 3600.0.
6. **Set Current Period Index** = **Get (a copy)** of array `SlotToPeriod` at **Index** = **Clamp (Integer)**( **Truncate**( `ClockSeconds` / 1800.0 ), Min 0, Max 47 ).
7. **Set Current Period Name** = **Get (a copy)** of array `PeriodNames` at **Index** = `CurrentPeriodIndex`.
8. **Compile**, **Save**.

**Part B (optional, 5 nodes)**, after step 7: **Branch** (`CurrentPeriodIndex` **!=** `LastPeriodIndex`); True > **Set Period Change Count** = `PeriodChangeCount` + 1 > **Set Last Period Index** = `CurrentPeriodIndex`. `LastPeriodIndex` starts equal to the first period, so there is no spurious count at start.

Do NOT add a Delay, a BeginPlay, or anything that resets `GameSecondsTotal`: pausing and changing the time scale must keep the accumulated time.

Then, with Unreal Editor closed, run `Tools/ClockPieTest.py` (command in the script header). Expected: `RESULT PASS (10/10 checks)`. Until the graph is wired it prints `TICK GRAPH NOT WIRED` and exits with code 6; this is the current state.

## 6. Test strategy (no full-day playthrough)
1. **Pure logic (done, passes now):** `ValidateSchedule.py`:
   - lookup of all 48 slots and all 8 boundaries (the second before and after each);
   - midnight wrap: 23:59:59, 00:00 and 05:59:59 are all Lockdown, and 05:59:59 to 06:00 is exactly one change to Wake-up;
   - the accumulating clock model: 60 s at 30x equals 30 game minutes, pause freezes it, a scale change from 120 to 30 keeps the total, 86400 wraps, and one full day at 120x produces exactly 8 period changes.
2. **Blueprint clock in PIE (after your wiring):** `ClockPieTest.py` puts a temporary manager into the PIE world (never saved) and jumps the clock instead of waiting. It checks:
   - rate within 2% at 120x;
   - pause freezes the clock and unpausing resumes without a reset;
   - a scale change without a reset;
   - the midnight wrap, with Lockdown held throughout and the unwrapped total still counting;
   - the 06:00 boundary changing exactly once;
   - all 48 half-hour slots against the reference table;
   - the optional part-B counter.
3. **Harness proof:** with `CLOCK_TEST_SIMULATE=1` a Python stand-in for the Tick graph (the reference model) passes 10/10, which proves the test logic itself. Never use that mode for acceptance.
4. **Later (Stages 3/4):** jump the clock to a few minutes before each boundary at 120x for boundary behaviour; use 30x with jumps to each period start for arrival and lockdown acceptance.

## 7. Proposed NPC assignments (for review; marker ids, idle in real seconds)
Validated: every marker exists, is `NavDest:Yes` and is at least 250 cm from every opening; each lockdown stop is the NPC's own cell marker (200 cm inside its door, by design); 25 distinct markers are used; no geometry or navigation change is needed.

| Time | Period | EXP01 Experienced (N2) | QUI01 Quiet (N5) | TRB01 Troublemaker (S2) | WRK01 Worker (S4) |
|---|---|---|---|---|---|
| 06:00 | Wake-up | CellAssign_Cell_N2, Conv_Hall_A (10-20) | CellAssign_Cell_N5 (20-40) | CellAssign_Cell_S2, Conv_Hall_A (4-8) | CellAssign_Cell_S4 (10-20) |
| 07:00 | Breakfast | Seat_Table_2_1 (40-70) | Seat_Table_1_5 (50-80) | Seat_Table_4_2 (25-45) | Work_Servery_S, Work_Servery_N (6-12) |
| 08:00 | Work and activities | Conv_Hall_A, Rec_Bench (15-30) | Rec_Table_B, Rec_TV (30-60) | Conv_Cafe_A, Conv_Rec_B, Rec_Weights (5-12) | Work_Servery_S, Work_Servery_N (6-12) |
| 12:00 | Lunch | Seat_Table_2_2 (40-70) | Seat_Table_1_5 (50-80) | Seat_Table_4_3 (25-45) | Work_Servery_S, Work_Servery_N (6-12) |
| 13:00 | Recreation | Rec_Bench, Conv_Rec_A, Rec_Yard_Walk (10-25) | Rec_TV, Rec_Table_B (30-50) | Rec_Weights, Conv_Rec_B, Conv_Rec_A, Rec_Yard_Walk (4-10) | Rec_Table_A, Rec_Bench (20-40) |
| 18:00 | Evening meal | Seat_Table_2_1 (40-70) | Seat_Table_1_5 (50-80) | Seat_Table_4_2 (25-45) | Work_Servery_S, Work_Servery_N (6-12) |
| 19:00 | Free time | Conv_Hall_A, Rec_Bench (8-16) | CellAssign_Cell_N5, Conv_Hall_A (30-60) | Conv_Hall_A, Conv_Rec_A (4-10) | Rec_Table_A (30-60) |
| 21:00-06:00 | Lockdown | Lockdown_Cell_N2 (60-120) | Lockdown_Cell_N5 (60-120) | Lockdown_Cell_S2 (60-120) | Lockdown_Cell_S4 (60-120) |

Design notes: `Work_Kitchen_Gap` is excluded (next to the secured kitchen door). The Worker serves at both servery counters during all meals and the work period. Seats come from the 24 cafeteria seat markers. Several NPCs share markers in the recreation area (for example Conv_Hall_A and Rec_Bench); shared destinations are intended, and proximity and avoidance are checked in Stage 3.

## 8. Findings and unresolved risks
- **F1 (important):** `BlueprintEditorLibrary.get_basic_type_by_name("float")` produces an INTEGER-like variable (1.75 is stored as 1). The true double type is `"real"`, which the manager uses. The existing M2.1B variables created with `"float"` (`BP_PrisonNPC` StartDelaySeconds, IdleMin, IdleMax; `STT_ChooseNextStop` IdleSeconds, StartDelay) are therefore integers. They work with the current whole-second data, but fractional seconds would be truncated. They are NOT changed in Stage 1 (working and approved). New Stage 2 variables will use "real". Whether to retype the old ones (the graphs may need reconnecting) is a Stage 2 decision.
- **F2:** lockdown spots are 200 cm from the cell door centre (inside the cell), so the 250 cm opening rule is waived for the NPC's own lockdown marker only.
- **R1:** at 30x the 1-hour periods last 120 s, and trips take 35-70 s plus up to 10 s stagger. Meal arrival is tight but feasible; 120x cannot test arrival.
- **R2:** idle timers are unscaled. In a single-stop period (meals, lockdown) the NPC re-"moves" to the stop it is standing at after every idle. Stage 2 must skip the move when already within the acceptance radius, or the Moving/Idle state will flicker.
- **R3:** simultaneous departures at 06:00 and 21:00 may bunch at the 160 cm cell doors and the 300 cm Gate G1 despite the stagger (to be measured in Stage 3).
- **R4:** the Tick graph and the later StateTree edits are manual and untested until you wire them; `ClockPieTest.py` confirms the first one.
- **R5:** the placed NPCs do not yet have the manager reference or the per-period arrays (Stage 2).

## 9. Not changed in Stage 1
Player character, camera, input, GameMode, approved M1 geometry, navigation (no re-bake), `BP_PrisonNPC`, `BP_NPCController`, `ST_NPCRoutine`, `STT_*`, `ABP_*`, the placed level actors and `S01_LW_F1_npcs.json`.
