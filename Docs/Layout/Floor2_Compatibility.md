# Sector 01 Left Wing - Floor 2 compatibility notes (from the Floor 1 greybox)

Provisional, centimetres. +X east, +Y north, Z up from the Floor 1 floor (z = 0). Floor-to-floor = 500, so the
Floor 2 walking level is **z = 500** (slab z 470-500). Source of truth: `S01_LW_F1.json`.

## 1. Residential atrium (double-height) - footprint and clearance

| Volume | Footprint (x, y) | Floor z | Clear height | Roof slab |
|---|---|---|---|---|
| Cell Block Hall (atrium) | 0..2800, 0..800 (224 m2) | 0 | 800 | 800-830 |
| Guard Stair Alcove (open to hall by an 800-wide arch) | 2000..2800, -500..0 (40 m2) | 0 | 800 | 800-830 |
| Guard Walkway (mezzanine) | 0..1200, -500..0 (60 m2) | 330 | open to atrium; rail top at 440 | none (open to hall roof) |
| Guard Observation Post | 1200..2000, -500..0 (40 m2) | 330 | 280 (top of interior 610) | 610-640 |

The walkway and Post sit on the roofs of cells S1-S5 (cell roof/walkway deck = z 300-330). They are a mezzanine
**inside Floor 1**; they are not a numbered floor.

**Floor 2 keep-out void:** the rectangle x 0..2800, y -500..800 (about 364 m2: hall + alcove + walkway + Post)
must contain no Floor 2 slab. Reasons:
- walkway headroom to a Floor 2 slab (z 470) would be only 140 cm;
- the Post roof reaches z 640, i.e. 140 cm above the Floor 2 walking level, so it rises through the void;
- the hall/alcove are 800 tall, which is 300 cm above the Floor 2 level.

Hidden markers `Floor2Keepout` (`Floor2_Void_SW/SE/NE/NW`, z = 500) in the level mark the void corners.

## 2. Open design decision for Floor 2

The atrium roof (800) leaves only **300 cm** clear above the Floor 2 walking level, below the 380 cm ceiling used on
other floors. Options:
- **A. Keep 800.** Floor 2 surrounds the void with solid walls (z 500 to 830); no gallery overlooking the atrium.
- **B. Raise the atrium and alcove ceiling to 880** (a one-number change to `ceil` for `Cell_Block_Hall` and
  `Hall_Stair_Alcove`; matches the stair-shaft height). This allows a Floor 2 gallery with a 380 cm ceiling and
  110 cm rail around the void. Needs your decision; not applied because it alters approved geometry.

The Post (top 640) still intrudes 140 cm above the Floor 2 level in either option, so any Floor 2 gallery must
clear it (keep the void rectangle above) or the Post roof must be lowered.

## 3. Other Floor 2 constraints from Floor 1

- **Stair shaft** x 3200..4400, y -1800..-700, clear to z 880. Upper landing at z 500 (slab 470-500) covers
  x 3700..4400, y -1000..-800. The **Floor 2 exit** is the secured opening in the east wall at x = 4400, centred on
  y = -900, 200 wide, z 500-770. Floor 2 geometry must meet it at floor level 500 heading east.
- **Cell roofs** (N1-N7, y 800..1300) top out at z 330; Floor 2 may use that footprint with 140 cm of build-up.
- Floor 3 (z 1000) and the Floor 3 core entrance are not represented here.
