# M2.3 Stage C0 - seated animation feasibility (Mixamo to SK_Mannequin)

Branch `m2-3-activity-foundation` (Stage B: `9af0680`, C0 tooling: `cd24517`). **Closed: human visual acceptance recorded.** C0 proves that a natural
stand-to-sit, seated-idle and sit-to-stand set can be obtained for the existing NPC skeleton. It adds assets and tools only: no gameplay, StateTree,
schedule, level geometry, navigation, player, camera, input, GameMode or animation Blueprint was touched. Nothing is connected to the activity system yet (that is C1).

## 1. Sources and licence
| Clip (Mixamo, default character, FBX binary, 30 fps, no keyframe reduction) | Length | Imported as |
|---|---|---|
| `Stand To Sit.fbx` | 2.23 s | `MX_StandToSit_Anim` (+ `MX_StandToSit` skeletal mesh, `MX_StandToSit_Skeleton`) |
| `Sitting Idle.fbx` | 4.30 s | `MX_SittingIdle` |
| `Sit To Stand.fbx` | 2.27 s | `MX_SitToStand` |

The raw FBX files live in `ArtSource/Mixamo/` and are **excluded from Git** (`.gitignore`: `/ArtSource/Mixamo/`); imported Unreal assets are tracked. No seated eating clip was found
and none was imported. Licence (to be re-confirmed against the current official page before shipping): Adobe's [Mixamo FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)
states that Mixamo characters and animations are free with an Adobe ID and royalty-free for personal, commercial and non-profit projects (games included); the raw files may not be redistributed.
The Mixamo-derived `MX_*` assets are committed to this (private) project repository only as retarget sources; they must not be published as standalone assets.

## 2. Skeleton and retargeting
- `SKM_Manny_Simple` and `SKM_Quinn_Simple` both use `/Game/Characters/Mannequins/Meshes/SK_Mannequin`. The Mixamo files use the standard 65-bone `mixamorig:` skeleton (root `mixamorig:Hips`, no separate root bone).
- `IK_Mixamo` (on `MX_StandToSit`), `IK_Manny` (on `SKM_Manny_Simple`) and `RTG_Mixamo_To_Manny`. The engine's auto-generated retarget chains matched on both skeletons (spine, neck, head, legs, arms, clavicles, fingers); Manny's A-pose was auto-aligned to the Mixamo pose. The engine's own `IK_Mannequin` (Mover example plugin, not mounted in this project) was not needed.
- Outputs (`/Game/CyberWarden/Anims/Seated/`): `SEAT_StandToSit` (67 frames), `SEAT_SittingIdle` (129), `SEAT_SitToStand` (68); `AnimSequence` on `SK_Mannequin`, root motion off, rate 1.0.

Corrections that were needed:
1. **Root bone drift.** With the retargeter's default Root Motion op the `root` bone followed the Mixamo hips (61 cm of drift). The op is disabled in `C0_RunRetarget.py`; root drift is now 0.000 cm.
2. **Different clip origins.** Stand-to-sit leaves the pelvis 46.4 cm behind where sitting-idle starts, and sit-to-stand ends 48 cm ahead of standing. `C0_AlignSeated.py` shifts the pelvis track of `SEAT_SittingIdle` and `SEAT_SitToStand` by 46.3 cm (idempotent: the second run changed nothing).

## 3. Measurements (component space, cm; the character faces +Y)
| Check | Result |
|---|---|
| Root drift, all three clips | 0.000 cm |
| Stand-to-sit end to idle start | max 2.9, mean 0.4 cm; max rotation 10 deg |
| Idle loop (end to start) | 0.0 (last frame equals the first: a one-frame hold per loop, trimmable later) |
| Idle end to sit-to-stand start | 3.1 cm; 17 deg (hand only) |
| Round trip (standing start to standing end) | 0.6 cm |
| Feet planted during the idle loop | 0.1 cm |
| Largest per-frame pelvis step | 3.1 cm in the transitions, 0.01 cm in the idle |
| Start / end pose vs `MM_Idle` | up to 21-23 cm and 46-52 deg at the feet (a 0.3 s blend covers it; use a longer blend-in for seated activities) |
| Heights | Mixamo 180.9 cm, Manny 180.5 cm |

Seated pose: pelvis 52.9 cm high (fits a stool of about 44 cm), thighs 43 cm long, knees and feet at the standing position (the marker), hands resting on the thighs at 60 cm, head at 119 cm.

## 4. Known limitation: the 88 cm table gap
This is a "chair behind you" sit: the pelvis travels **43 cm backwards** from the standing spot while the feet stay planted. The cafeteria markers stand **45 cm** from the table edge (table 100 x 300 x 75, seat marker 95 cm from the table centreline), so the seated pelvis ends about **88 cm from the table edge** (knees at the marker, 45 cm short of the table; hands in the lap, 54 cm short). The clip suits sitting and waiting; **it cannot show a prisoner eating from the table.**
Options, none decided: (1) accept seated-idle at the table for the Stage C prototype (recommended for C1); (2) add a small seated eating loop in Control Rig (does not close the gap); (3) find or author a sit with about 15 cm of pelvis travel; (4) change table or seat geometry (touches M1, needs separate approval).

## 5. Visual proof and acceptance
- `L_C0_SeatPreview` (new, standalone level) holds two rows of Manny frozen at sampled frames of the clips beside a 38 x 38 x 44 cm stool and a table slab at the cafeteria spacing, and one live Manny; `LS_C0_SeatPreview` (13.1 s) plays stand-to-sit, seated idle twice, sit-to-stand.
- Offline renders (GPU, `Tools/RunRenderScript.ps1` + `C0_RenderPreview.py`): the sit leans forward, settles onto the stool and ends upright; the stand-up mirrors it and ends standing on the marker with no pop; no body distortion or foot sliding visible.
- **Human visual acceptance: approved.** The project owner reviewed `LS_C0_SeatPreview` in the Unreal Editor and reported that the sitting, the seated idle and the standing animations look good.

## 6. Dependency audit (`Tools/C0_AuditDependencies.py`)
13 assets under `/Game/CyberWarden/Anims`, all kept:
- `SEAT_*` depend only on `SK_Mannequin` and `SKM_Manny_Simple` (existing, tracked); they need no `MX_*` asset to load.
- `RTG_Mixamo_To_Manny` needs `IK_Mixamo`, `IK_Manny` and `MX_StandToSit`; `IK_Mixamo` needs `MX_StandToSit` (reference mesh); the skeleton `MX_StandToSit_Skeleton` is needed by every `MX_*` asset.
- `MX_StandToSit_Anim`, `MX_SittingIdle`, `MX_SitToStand` are referenced by nothing but are the source clips `C0_RunRetarget.py` retargets; removing them would stop the SEAT clips being regenerated after any retargeter or alignment change (about 1.8 MB together). No duplicates exist, so nothing was excluded.
- The preview level and sequence reference only the SEAT clips, `SKM_Manny_Simple` and engine shapes.

## 7. Rebuilding the animations (reusable pipeline)
Put the three FBX files in `ArtSource/Mixamo/` (new Mixamo clips follow the same recipe), then run serially with `powershell -File Tools\RunHeadless.ps1 -Script <script>`:
`C0_ImportMixamo.py` -> `C0_BuildRetarget.py` -> `C0_RunRetarget.py` -> `C0_AlignSeated.py` -> `C0_AnalyzeSeated.py` (measurements, `Saved/C0_AnalyzeSeated.txt`) -> `C0_BuildPreview.py`; `C0_RenderPreview.py` needs `Tools\RunRenderScript.ps1` (GPU). Read-only helpers: `InspectSeatedSkeleton.py`, `ProbeRetargetApi.py`, `C0_ProbeAnimApi.py`, `C0_AuditDependencies.py`.
Note: an Unreal Python error does not change the process exit code (several early runs exited 0 with a script error), so always check the report file.

## 8. Process exit codes (all Unreal runs serial)
All C0 runs exited 0 except two that exited `-1073741819` (0xC0000005) **after** their script had completed and written its report: the first measurement run and the GPU render run. That is the tracked, unresolved headless shutdown access violation (`M2_2_Shutdown_Crash.md`); it is not attributed to the C0 assets. No gameplay test was run in C0 (nothing gameplay-related changed).

## 9. Carry-forward for C1 (not started)
Findings from the Stage C assessment that the C1 native work must address: seamless enter-to-loop hand-off (the enter montage blends out before the loop starts), committed enter (a release while sitting must finish the sit), per-activity release grace (a stand-up takes 2.3 s), no random loop start for seated loops, and the open decision on final positioning (settle) and the table gap (section 4). Seat clips need a longer blend-in than 0.3 s (up to about 0.4 s) from the walking idle.
Open items unchanged: headless shutdown access violation (unresolved), Gate G1 stall and cafeteria east-aisle congestion (monitor).
