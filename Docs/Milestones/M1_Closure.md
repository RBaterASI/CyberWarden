# M1 - Sector 01, Left Wing, Floor 1 (Residential) greybox - CLOSED

**Status:** approved. Passed human Play In Editor testing in Unreal Engine 5.8.4 (all six final tests: main staircase
and railings, guard stairs and observation walkway, Guard Post cabin, hub/cafeteria/recreation, secured Floor 2 exit,
camera and navigation). Earlier rounds also passed: location indicator, room signs, hub navigation, area colours,
cell block, camera and movement.

**Level:** `/Game/CyberWarden/Maps/Sector01/L_S01_LW_F1_Greybox`
**Generated from:** `Docs/Layout/S01_LW_F1.json` by `Tools/BuildFloor1Greybox.py` (Unreal Python).
**Last approved content commit:** `081887f` (Hub, Cafeteria and Recreation ceilings 470 cm; atrium 880 cm).
**Preserved, unmodified:** `BP_CyberWardenCharacter`, the +/-90 degree camera restriction, CameraBoom Target Arm
Length 200 cm, `BP_ThirdPersonGameMode`, input mappings, and the Third Person template level.

## Carried-forward low-priority items
1. **Guard visibility of the south cell doors (S1-S5):** the 110 cm solid walkway/Post rail hides them from the guard
   positions unless a guard leans; about 75% of the hall floor is visible. Consider an open balustrade later.
2. **Missing sign on the hall-to-guard-stair arch.**
3. **Minor wall-corner visual artifacts** (possible surface flicker where wall boxes overlap), if observed.

Also noted earlier: the Guard Post cabin has a 280 cm ceiling; collision was validated analytically (and by human
play), not by an automated engine-level test.

## Related documents
- `Docs/Layout/Floor2_Compatibility.md` - atrium 880 cm, Floor 2 keep-out void, slab alignment, assumptions.
- `Docs/Layout/S01_LW_F1_build_report.txt` - last automated validation run.
