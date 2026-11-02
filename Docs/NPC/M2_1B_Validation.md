# M2.1B - First NPC validation (NPC_EXP01)

Manual PIE result (user): StateTree-driven navigation, route following, walk animation while moving and idle animation when stopped all work.

## Authored assets (manual, committed)
- `ST_NPCRoutine` (StateTree, AI component schema) and its wiring; `STT_ChooseNextStop` / `STT_ReportState` graphs; `BP_NPCController` StateTree assignment.
- `Content/Characters/Mannequins/Anims/Unarmed/ABP_PrisonNPC`: NPC-only duplicate of `ABP_Unarmed`. `Should Move` now depends on `Ground Speed > 3.0` (the original also required acceleration, so AI-driven pawns stayed in idle). Assigned to `BP_PrisonNPC`.
- `ABP_Unarmed` is byte-identical to the baseline and is still the player character's animation Blueprint.

## Automated checks (`Tools/InspectNpcAssets.py`, `Tools/NpcPieTest.py` observe mode, headless PIE)
- BP_PrisonNPC: anim class `ABP_PrisonNPC_C`, AI controller `BP_NPCController`, capsule 34 x 90. Player: anim class `ABP_Unarmed_C`.
- Observe 150 s: Moving x7, Idle x7, NavFail x0, first movement after 5.0 s (6 s start delay), 0 teleports, max step 5 cm per tick, 18,586 cm walked, route N2 -> Conv_Hall_A -> Rec_Bench -> N2 repeated. No StateTree errors in the log.
- Note: the StateTree re-enters `StartDelay` on every loop (0 s after the first pass), so `MoveState` briefly reads StartDelay between Idle and Moving. Cosmetic.

## Limits
Python cannot read StateTree internals (schema/states are protected), so state wiring is validated behaviourally, not by structure.

## Population expansion: four prisoners (`Tools/NpcPopulationTest.py`)
Data: `Docs/Layout/S01_LW_F1_npcs.json` (shared `BP_PrisonNPC`, `BP_NPCController`, `ST_NPCRoutine`, `ABP_PrisonNPC`; no per-NPC assets). Placed with `Tools/PlaceNpcs.py`; geometry and baked navigation untouched.

| NPC | Start cell | Start delay | Idle | Speed | Route (idle stops are open floor) |
|---|---|---|---|---|---|
| EXP01 Experienced | N2 | 6 s | 4-8 s | 180 | Conv_Hall_A, Rec_Bench, own cell |
| QUI01 Quiet | N5 | 14 s | 10-18 s | 150 | Rec_TV, Rec_Table_B, own cell |
| TRB01 Troublemaker | S2 | 3 s | 2-5 s | 210 | Conv_Cafe_A, Conv_Rec_B, Rec_Weights, Conv_Hall_A |
| WRK01 Worker | S4 | 9 s | 6-12 s | 190 | Work_Servery_S, Work_Servery_N (Work_Kitchen_Gap skipped: next to the secured kitchen door) |

Headless PIE, 400 game seconds at slomo 4, all four simultaneously (result PASS):

| NPC | Stop arrivals | Full route loops | Nav failures | Stuck | Repeat attempts | Teleports | Max step/tick |
|---|---|---|---|---|---|---|---|
| EXP01 | 17 | 5 | 0 | 0 | 0 | 0 | 22 cm |
| QUI01 | 11 | 3 | 0 | 0 | 0 | 0 | 18 cm |
| TRB01 | 18 | 4 | 0 | 0 | 0 | 0 | 25 cm |
| WRK01 | 31 | 15 | 0 | 0 | 0 | 0 | 13 cm |

- Proximity: no capsule overlap (<68 cm) at any time. Closest approaches: EXP01/QUI01 68 cm in the hall at (2733,499), EXP01/TRB01 68 cm in recreation at (3522,1792), QUI01/TRB01 81 cm at (3253,494). Time under 120 cm: 2.7 s, 1.7 s, 1.3 s. Avoidance (RVO) is working; NPCs touch but do not interpenetrate.
- Doorway congestion: two NPCs within 200 cm of the same opening at once only at Gate G1 (about 3 s each side, EXP01/QUI01/TRB01) and Arch_North_Rec (0.3 s). No NPC idled within 250 cm of any opening, and no stuck windows.
- Needs a human eye: whether two NPCs head-on in the 300 cm Gate G1 pass cleanly or visibly shuffle, the look of NPCs touching at ~68 cm, and the player squeezing past an NPC in the Gate G1 / hall corridor.

## StartDelay label flicker (pending one manual edit)
Cause: `STT_ReportState` runs for the `StartDelay` state on every loop, although the delay is 0 s after the first pass. The fix lives in the `STT_ReportState` event graph, which Python cannot edit.
Edit: right after **Event EnterState** insert a **Branch** with Condition = `StateLabel == "StartDelay"` AND `MoveState != "Spawned"` (MoveState read from the cast NPC, so put the cast first). True: end (do nothing). False: the existing flow. `MoveState` is "Spawned" only before the first report, so the first start delay is unchanged and later cycles keep the previous label (Idle/NavFail) until Moving. Verify with `NpcPopulationTest.py`: transitions should no longer show `StartDelay` after the first one.

## Final validation after the StartDelay fix (`STT_ReportState` edited by hand)
- Structure (asset string scan; Python cannot walk graph nodes): the Blueprint now contains a Branch, `BooleanAND`, `EqualEqual_StrStr` (StateLabel == "StartDelay"), `NotEqual_StrStr` (MoveState != "Spawned"), the "Spawned" literal, the casts to `BP_PrisonNPC` and the NavFail counter. Behaviour below confirms the flow.
- Population test, 400 game seconds, 4 prisoners: PASS. Loops EXP01 5, QUI01 3, TRB01 4, WRK01 15; arrivals 17/11/19/30; navigation failures 0; stuck 0; repeated attempts 0; teleports 0; bad arrivals 0; `StartDelay` reported again after the first report: 0 (previously once per cycle). First movement after 5.1 / 13.1 / 2.1 / 8.1 s, matching the 6 / 14 / 3 / 9 s start delays. Idle periods match the configured ranges. Closest approach 68 cm, no overlap, nothing idled near an opening. Gate G1 west had 2+ NPCs within 200 cm for 4.1 s in total, Arch_North_Rec for 2.1 s.
- Failure reporting (`NPC_TEST_FAIL_NPC=WRK01`, PIE-only copy, last route marker moved off the navmesh): Moving to the bad stop failed, state `NavFail` reported, `NavFailureCount` incremented (10 in 160 s), 2 s Recover delay, routine continued to the next stop each time. The level file is not modified.
- Finding: an empty `Route` does NOT produce `NavFail`. `STT_ChooseNextStop` leaves the previous `TargetActor` in place, so the NPC just re-"moves" to its current stop. Only prints "empty Route". Harmless for the placed NPCs; the earlier setup doc's claim is incorrect.
