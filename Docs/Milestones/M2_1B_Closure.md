# M2.1B - Population Movement: closure

Status: **approved** by the project owner after manual Play In Editor testing (movement, animation, StateTree loop, StartDelay fix). Tag: `m2-1b-population-approved`.
Includes M2.1A (Static navigation foundation, approved earlier).

## Delivered
- Reusable NPC system: `BP_PrisonNPC`, `BP_NPCController`, `ST_NPCRoutine` (StateTree), `STT_ChooseNextStop`, `STT_ReportState`, NPC-only `ABP_PrisonNPC` (`Should Move` on ground speed > 3.0; `ABP_Unarmed` untouched).
- Four prisoners driven from `Docs/Layout/S01_LW_F1_npcs.json`: EXP01 (Experienced), QUI01 (Quiet), TRB01 (Troublemaker), WRK01 (Worker). No per-NPC assets.
- Tools: `PlaceNpcs.py`, `NpcPopulationTest.py`, `NpcPieTest.py`, `InspectNpcAssets.py`, `CreateNpcFoundation.py`, `VerifyNpcFoundation.py`; debug overlay `Content/Python/cw_npc_debug.py` (editor only).
- Docs: `Docs/NPC/M2_1B_Manual_Setup.md`, `Docs/NPC/M2_1B_Validation.md`.

## Final automated results (headless PIE, 4 prisoners together, 400 game seconds)
| NPC | Route loops | Stop arrivals | Nav failures | Stuck | Teleports | Repeated StartDelay |
|---|---|---|---|---|---|---|
| EXP01 | 5 | 17 | 0 | 0 | 0 | 0 |
| QUI01 | 3 | 11 | 0 | 0 | 0 | 0 |
| TRB01 | 4 | 19 | 0 | 0 | 0 | 0 |
| WRK01 | 15 | 30 | 0 | 0 | 0 | 0 |
- First movement 5.1 / 13.1 / 2.1 / 8.1 s (configured 6 / 14 / 3 / 9 s). No capsule overlap; closest approach 68 cm. No idling near openings; brief 2+ NPC co-presence at Gate G1 west (4.1 s total) and Arch_North_Rec (2.1 s).
- Failure injection (last route marker moved off the navmesh, PIE copy only): NavFail reported, counter incremented, 2 s recovery, routine continued.
- Human PIE playtest: approved.

## Deferred (low priority): empty Route robustness
An NPC with an empty `Route` is not reported as `NavFail`: `STT_ChooseNextStop` keeps the previous `TargetActor`, so it re-"moves" to its current stop and only prints "empty Route". No placed NPC has an empty route. Possible later fix: clear `TargetActor` (or report NavFail) in the empty-Route branch. Not changed at closure.

## Preservation check (versus M1 tag `m1-floor1-approved`, 81e2784)
- Unchanged: `Content/ThirdPerson` (incl. `BP_CyberWardenCharacter`, GameMode), `Content/Input`, `Config/*` (no committed config changes), `CyberWarden.uproject`, all existing `Content/Characters` assets (only new `ABP_PrisonNPC` added), M1 geometry (layout rooms, openings, stairs, boxes, builder geometry code).
- Intentional M2.1A changes: marker `NavDest` metadata and Duty markers in the layout JSON/builder, tighter nav volume, baked Static navigation, NPC actors in the level.
- `Config/DefaultEditor.ini` has an unrelated local editor-generated change; deliberately not committed.

## Carried forward
Remaining two guard NPCs and further archetypes (M2.1C+), empty-Route robustness, Gate G1 head-on crossing and doorway congestion re-check when guards are added.
