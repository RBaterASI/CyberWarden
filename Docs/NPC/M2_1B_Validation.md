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
