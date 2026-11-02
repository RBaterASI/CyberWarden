# M2.1B - NPC foundation: asset status and manual Unreal Editor setup (UE 5.8.4)

Goal of this phase: ONE NPC (EXP01, Experienced inmate, cell N2) that waits for a configurable start delay, walks by
AI navigation to a communal marker, idles, walks to a second destination, and repeats - driven by a StateTree.

## 1. Asset status

| Asset (`/Game/CyberWarden/NPC/`) | Status | Automated (done) | Manual (you) |
|---|---|---|---|
| `BP_PrisonNPC` (Character) | **Complete, no graph needed** | Manny mesh + `ABP_Unarmed` (originals untouched), capsule 34 x 90, RVO avoidance on, orient-to-movement, AI controller = `BP_NPCController`, auto-possess when placed, config + runtime variables with defaults | none |
| `BP_NPCController` (AIController) | **Shell complete** | `StateTreeAI` component (StateTree AI Component) added | assign the State Tree asset (step C) |
| `STT_ChooseNextStop` (StateTree task) | **Variables only - graph is manual** | variables + categories (Context/Output), flags: not considered for completion, re-run on reselect | event graph (step B1) |
| `STT_ReportState` (StateTree task, added; not in the original list) | **Variables only - graph is manual** | variables + categories (Context/Parameter), same flags | event graph (step B2) |
| `ST_NPCRoutine` (StateTree) | **Not created** - Python cannot set a StateTree's schema or build states | - | create with the AI schema and build the states (steps A, D) |
| Level `L_S01_LW_F1_Greybox` | NPC `NPC_EXP01` placed in N2 with Route = `Conv_Hall_A -> Rec_Bench -> Lockdown_Cell_N2`, start delay 6 s, idle 4-8 s, speed 180 | yes | none |

Why `STT_ReportState`: it writes the NPC's `MoveState` (StartDelay / Moving / Idle / NavFail), counts navigation failures and
logs them. Without it there is no movement-state or failure reporting. It is generic (one graph reused by every NPC).

Already proven without any StateTree (headless PIE, `Tools/NpcPieTest.py`, mode `smoke`): the placed NPC is possessed by
`BP_NPCController`, and Python-commanded AI MoveTo walked it N2 -> Conv_Hall_A -> Rec_Bench -> back to N2, twice, through
the 160 cm cell door, Gate G1, the hub and the north link: 6/6 legs, 0 teleports, largest per-tick step 27 cm.

Expected harmless log noise until step C: `StateTreeComponent ... The State Tree asset is not set`.

## 2. Manual steps (about 30-45 minutes, one-time)

Open `CyberWarden.uproject`. All assets are in Content Browser `Content/CyberWarden/NPC`.

### A. Create `ST_NPCRoutine`
1. In `Content/CyberWarden/NPC`: right-click > **Artificial Intelligence > State Tree** (or **Add > Artificial Intelligence > State Tree**).
2. In "Pick State Tree Schema" choose **StateTree AI Component** > Select. Name it `ST_NPCRoutine`.
3. Open it. In the **Details** of the tree/root, set the schema's **AI Controller Class** to `BP_NPCController` (if shown).

### B1. `STT_ChooseNextStop` - event graph
Open the Blueprint (variables already exist: `ContextActor` Context, `TargetActor`/`IdleSeconds`/`StartDelay` Output, `Idx` int).
Right-click the Event Graph > add **Event EnterState** (not the deprecated one). Then, left to right:

1. **Cast To BP_PrisonNPC**, Object = `ContextActor`.
2. *Cast Failed* > **Print String** "STT_ChooseNextStop: context actor is not a BP_PrisonNPC". (End.)
3. *Cast Success* > **Branch**. Condition = `Length(Route) > 0` (drag `Route` from *As BP Prison NPC*, use **Length**, then **> (integer)** with 0).
4. *False* > **Print String** from **Append**("NPC ", NpcId, " has an empty Route"). (End. `TargetActor` keeps its previous value, so an empty Route is only printed, not reported as NavFail.)
5. *True*, chain these in order:
   1. **Set Idx** = `NextStopIndex` **%** `Length(Route)` (integer modulo node).
   2. **Set TargetActor** = **Get (a copy)** of `Route` at index `Idx`.
   3. **Set IdleSeconds** = **Random Float in Range**(Min = `IdleMin`, Max = `IdleMax`).
   4. **Set StartDelay** = **Select Float**(A = `StartDelaySeconds`, B = 0.0, Pick A = `StartDelayPending`).
   5. **Set Start Delay Pending** (on *As BP Prison NPC*) = false.
   6. **Set Current Stop Index** (on *As BP Prison NPC*) = `Idx`.
   7. **Set Next Stop Index** (on *As BP Prison NPC*) = (`Idx` + 1) **%** `Length(Route)`.
   8. **Print String** (Print to Screen and Log on, Duration 5) from **Append**: "[NPC ", NpcId, "] stop ", ToString(Idx), "/", ToString(Length(Route)), " -> ", **Get Display Name**(TargetActor), " startDelay=", ToString(StartDelay), " idle=", ToString(IdleSeconds).
6. Do **not** add Finish Task: this task runs in the background for the whole routine (already flagged "not considered for completion").
7. Compile, Save.

### B2. `STT_ReportState` - event graph
Variables exist: `ContextActor` (Context), `StateLabel` (Parameter string).
1. **Event EnterState**.
2. **Cast To BP_PrisonNPC**, Object = `ContextActor` (Cast Failed: end).
3. Cast Success > **Set Move State** (on *As BP Prison NPC*) = `StateLabel`.
4. > **Branch**, Condition = **Equal (String)**(`StateLabel`, "NavFail").
5. *True* > **Set Nav Failure Count** (on NPC) = NavFailureCount + 1 > (continue to step 6).
6. *False* and the end of *True* both > **Print String** (screen + log, Duration 5) from **Append**: "[NPC ", NpcId, "] ", StateLabel, " | stop ", ToString(CurrentStopIndex), " | fails ", ToString(NavFailureCount).
7. No Finish Task. Compile, Save.

### C. `BP_NPCController`
Open it > select the **StateTreeAI** component > Details > **State Tree** > **State Tree** = `ST_NPCRoutine` (leave *Start Logic Automatically* on). Compile, Save.

### D. Build the states in `ST_NPCRoutine`
1. Rename the root state **Routine** (Selection Behavior: *Try Select Children In Order*).
2. Routine > Tasks > **+** > `STT_ChooseNextStop`. Check its **Context Actor** shows as bound to *Context > Actor*; if it says unbound, right-click the property > Bind > Context > Actor.
3. Add four **child states** under Routine (select Routine > **+ Add Child State**), in this order, with these tasks and transitions:

| # | State | Tasks | Transitions (besides the default "On State Completed > Next State") |
|---|---|---|---|
| 1 | `StartDelay` | `STT_ReportState` (StateLabel = `StartDelay`); **Delay Task**: Duration bound to `Routine > STT_ChooseNextStop > Start Delay` | none (default goes to the next state) |
| 2 | `MoveToStop` | `STT_ReportState` (StateLabel = `Moving`); **Move To**: Target Actor bound to `Routine > STT_ChooseNextStop > Target Actor`, Acceptable Radius = 60, Allow Partial Path off | **On State Failed > Go to State > `Recover`** |
| 3 | `IdleAtStop` | `STT_ReportState` (StateLabel = `Idle`); **Delay Task**: Duration bound to `Routine > STT_ChooseNextStop > Idle Seconds` | **On State Completed > Go to State > `Routine`** (replaces "Next State"; this is the loop) |
| 4 | `Recover` | `STT_ReportState` (StateLabel = `NavFail`); **Delay Task**: Duration = 2.0 | **On State Completed > Go to State > `Routine`** |

4. For every `STT_ReportState` check *Context Actor* is bound to Context > Actor.
5. **Compile** the StateTree (toolbar). It should succeed with no errors. Save All.

### E. Try it
1. Restart the editor once so the dev overlay (`Content/Python/init_unreal.py`) loads.
2. Open `L_S01_LW_F1_Greybox`, press **Play**. Within a few seconds `NPC_EXP01` (in cell N2) should log `stop 0/3 -> MK_Conversation_Conv_Hall_A startDelay=6.0`, stand ~6 s (state `StartDelay`), walk out of the cell to the hall point (`Moving`), pause 4-8 s (`Idle`), walk to the recreation bench, pause, return to N2, and repeat.
3. Floating text above the NPC shows `EXP01 | state | -> next stop | fails n`; state changes also appear in the Output Log as `[NPC] t=...`.
4. To force a failure test: temporarily move a route marker outside the navmesh (or empty `Route` on the placed NPC); the NPC should print `NavFail`, wait 2 s and continue to the next stop.

When done, tell me; with the editor closed I can run the automated acceptance check: `NPC_TEST_MODE=observe NPC_TEST_SECONDS=240 UnrealEditor-Cmd ... Tools/NpcPieTest.py`.

## 3. Troubleshooting
| Symptom | Check |
|---|---|
| Log: "The State Tree asset is not set" | Step C not done. |
| NPC never moves, no `[NPC ...]` logs | StateTree not compiled/assigned; NPC `AIControllerClass` must be `BP_NPCController` (it is by default); StateTreeAI component must reference `ST_NPCRoutine`. |
| `Moving` then immediately `NavFail` | `TargetActor` unbound/empty (Move To binding) or marker not on the navmesh; press **P** in the viewport to see the navmesh. |
| Delay never ends | Duration not bound (still 1.0 default is fine; a bound output of 0 completes next frame). |
| Compile error "unbound Context" | Bind *Context Actor* to Context > Actor on both Blueprint tasks. |
| NPC stands in a doorway | Report where; idle points are inside rooms, avoidance is RVO. |

## 4. Data and pipeline reference
- NPC definitions: `Docs/Layout/S01_LW_F1_npcs.json` (id, cell, spawn marker, start delay, idle range, speed, ordered route of marker ids; only NavDest:Yes markers are accepted).
- Scripts (run with the interactive editor closed): `Tools/CreateNpcFoundation.py` (creates missing assets only, never overwrites), `Tools/VerifyNpcFoundation.py`, `Tools/PlaceNpcs.py`, `Tools/NpcPieTest.py`.
- After any `BuildFloor1Greybox.py` run: `BakeNavigation.py`, then `PlaceNpcs.py` (the builder deletes the markers the Route arrays reference).
