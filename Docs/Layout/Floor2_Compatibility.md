# Sector 01 Left Wing - Floor 2 compatibility notes (from the Floor 1 greybox)

Provisional, centimetres. +X east, +Y north, Z up from the Floor 1 floor (z = 0). Floor-to-floor = 500, so the
Floor 2 walking level is **z = 500** (slab z 470-500). Source of truth: `S01_LW_F1.json` (`future_floor2` block holds
the allowances used below). **Approved decision: the residential atrium ceiling is 880 cm** (raised from 800).

Terms: *nominal* clearance = geometric height between two surfaces. *Usable* clearance = nominal minus the assumed
service/finish allowance (20 cm, an assumption, not a GDD value; the Floor 2 slab thickness is 30 cm).

## 1. Residential atrium (double-height) - footprint and clearance

| Volume | Footprint (x, y) | Floor z | Ceiling (underside) | Roof slab |
|---|---|---|---|---|
| Cell Block Hall (atrium) | 0..2800, 0..800 (224 m2) | 0 | 880 | 880-910 |
| Guard Stair Alcove (open to hall by an 880-high, 800-wide arch) | 2000..2800, -500..0 (40 m2) | 0 | 880 | 880-910 |
| Guard Walkway (mezzanine) | 0..1200, -500..0 (60 m2) | 330 | open to atrium; rail top 440 | none |
| Guard Observation Post | 1200..2000, -500..0 (40 m2) | 330 | 610 (interior 280) | 610-640 |

| Clearance | Nominal | Usable (-20 services) |
|---|---|---|
| Floor 1 hall floor to atrium roof underside | 880 | 860 |
| Floor 2 walking level (z 500) to atrium roof underside | **380** | **360** |
| Walkway deck (z 330) to atrium roof underside | 550 | 530 |
| Guard Post roof (top z 640) to atrium roof underside | 240 | 220 |
| Guard Post roof above the Floor 2 walking level | +140 (intrudes) | n/a |

The walkway and Post sit on the roofs of cells S1-S5 (cell roof/walkway deck = z 300-330). They are a mezzanine
**inside Floor 1**; they are not a numbered floor.

## 2. Floor 2 keep-out void

The rectangle **x 0..2800, y -500..800 (about 364 m2)** must contain no Floor 2 slab. It encloses the hall, alcove,
walkway, Post and cells S1-S5 (S cells stay below the Floor 2 slab at z <= 470). The Post (roof top z 640) rises 140
cm through the void but stays 240 cm below the atrium roof. The build check confirms nothing else inside the void
reaches the Floor 2 slab zone. With the 880 ceiling a Floor 2 gallery around the void has a nominal 380 cm
(usable 360 cm) ceiling and a 110 cm rail, matching the other Floor 2 ceiling height. Hidden `Floor2Keepout`
markers (`Floor2_Void_SW/SE/NE/NW`, z = 500) mark the corners in the level.

## 3. Other Floor 2 constraints from Floor 1

- **Stair shaft** x 3200..4400, y -1800..-700, ceiling 880 (nominal 380 above Floor 2, usable 360). Upper landing at
  z 500 (slab 470-500) covers x 3700..4400, y -1000..-800. The **Floor 2 exit** is the secured opening in the east
  wall at x = 4400, centred on y = -900, 200 wide, z 500-770. Floor 2 geometry must meet it at floor level 500.
- **Cell roofs** (N1-N7, y 800..1300) top out at z 330; Floor 2 may use that footprint with 140 cm of build-up.
- Floor 3 (z 1000, slab 970-1000) is not represented. The atrium/shaft roof slab (880-910) leaves 60 cm below the
  Floor 3 slab.

## 4. Ceiling slab alignment (resolved)

Central Hub, Cafeteria and Recreation now have a 470 cm ceiling plus a 30 cm slab, so the slab occupies z 470-500 and
its top coincides with the Floor 2 walking level (500) and the Floor 2 slab. Clear height on Floor 1 in those rooms is
470 nominal (450 usable after the 20 cm service allowance). The build check verifies the alignment and that no prop,
column, sign, opening or light reaches the lowered ceilings (lights are at z 420, signs below z 340). Corridors
(ceiling 380, slab 380-410) leave a 60 cm service plenum below the Floor 2 slab.
