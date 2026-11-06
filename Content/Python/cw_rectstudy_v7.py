"""Geometry + analytic validation for the Floor 1 RECTANGLE STUDY V7 (Greybox Build Sheet, confined layout: board 10 + board 11).

Pure Python (no `unreal` import). StudyV7 = StudyV6 (-> StudyV2) + full-height mesh (collidable bars, see-through) + the safety net (visual only).
Frame: cm, +X east, +Y SOUTH, Z up.
"""
import math

import cw_rectstudy_v6 as v6
from cw_rectstudy import Analyzer, load, _segments_minus  # noqa: F401
from cw_rectstudy_v6 import room_at  # noqa: F401


def _rect_sub(r, holes):
    out = [r]
    for h in holes:
        nxt = []
        for a in out:
            ix0, iy0, ix1, iy1 = max(a[0], h[0]), max(a[1], h[1]), min(a[2], h[2]), min(a[3], h[3])
            if ix0 >= ix1 or iy0 >= iy1:
                nxt.append(a)
                continue
            if iy0 > a[1]:
                nxt.append((a[0], a[1], a[2], iy0))
            if iy1 < a[3]:
                nxt.append((a[0], iy1, a[2], a[3]))
            if ix0 > a[0]:
                nxt.append((a[0], iy0, ix0, iy1))
            if ix1 < a[2]:
                nxt.append((ix1, iy0, a[2], iy1))
        out = nxt
    return out


class StudyV7(v6.StudyV6):
    BAR = 6.0       # mesh bar thickness (cm)
    PITCH = 60.0    # mesh bar pitch: clear gap 54 cm < the 68 cm capsule, so the mesh blocks a walker but stays see-through

    def _build(self):
        super()._build()
        d = self.data
        for m in d.get("meshes", []):
            self._mesh(m)
        for n in d.get("nets", []):
            self._net(n)

    def _mesh(self, m):
        axis, coord, z0, z1 = m["axis"], float(m["coord"]), float(m["z0"]), float(m["z1"])
        t = self.BAR
        for si, (s0, s1) in enumerate(_segments_minus(float(m["a"]), float(m["b"]), m.get("gaps", []))):
            n = max(1, int(round((s1 - s0) / self.PITCH)))
            for k in range(n + 1):
                p = s0 + (s1 - s0) * k / n
                lo, hi = max(s0, p - t / 2), min(s1, p + t / 2)
                if axis == "h":
                    self.box("%s_Bar%d_%d" % (m["id"], si, k), lo, coord - t / 2, z0, hi, coord + t / 2, z1, "mesh", "lit:Mesh", True, "Mesh")
                else:
                    self.box("%s_Bar%d_%d" % (m["id"], si, k), coord - t / 2, lo, z0, coord + t / 2, hi, z1, "mesh", "lit:Mesh", True, "Mesh")
            for ri, rz in enumerate((z0 + 110.0, z0 + 220.0, z1 - 6.0)):
                if rz + t > z1:
                    continue
                if axis == "h":
                    self.box("%s_Rail%d_%d" % (m["id"], si, ri), s0, coord - t / 2, rz, s1, coord + t / 2, rz + t, "mesh", "lit:Mesh", True, "Mesh")
                else:
                    self.box("%s_Rail%d_%d" % (m["id"], si, ri), coord - t / 2, s0, rz, coord + t / 2, s1, rz + t, "mesh", "lit:Mesh", True, "Mesh")

    def _net(self, n):
        x0, y0, x1, y1 = n["rect"]
        z, pitch = float(n["z"]), float(n["pitch"])
        holes = [tuple(h) for h in n.get("holes", [])]
        bars = []
        y = y0
        while y <= y1 + 0.1:
            bars.append((x0, y - 2.0, x1, y + 2.0))
            y += pitch
        x = x0
        while x <= x1 + 0.1:
            bars.append((x - 2.0, y0, x + 2.0, y1))
            x += pitch
        i = 0
        for b in bars:
            for r in _rect_sub(b, holes):
                self.box("Net_%d" % i, r[0], r[1], z, r[2], r[3], z + 4.0, "net", "unlit:Net", False, "Net")
                i += 1


# ==========================================================================================
# Analysis
# ==========================================================================================
STAFF_AREAS = {"Guard", "Staff", "Intake"}
STAIR_BOXES = ((5620.0, 6070.0, 1650.0, 1930.0), (5650.0, 6030.0, 4490.0, 5090.0))   # S3 / S4 footprints (cells mid-flight have no room)


def run_analysis(study, report):
    d = study.data
    errors, warnings = [], []

    def err(m):
        errors.append(m)
        report("ERROR: " + m)

    def warn(m):
        warnings.append(m)
        report("WARNING: " + m)

    an = Analyzer(study)
    ps = d["meta"]["player_start"]
    start = (ps["x"], ps["y"])
    R = study.CAP_R
    rooms = study.rooms
    fp = d["meta"]["footprint"]

    report("== Geometry summary ==")
    kinds = {}
    for b in study.boxes:
        kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    report("Boxes: %d total (%s); collision boxes %d; text signs %d; lights %d; markers %d; floor-guide strips %d" % (
        len(study.boxes), ", ".join("%s=%d" % kv for kv in sorted(kinds.items())), len(an.geo), len(study.texts), len(study.lights), len(study.markers), len(study.lines)))
    report("Footprint: %.1f m x %.1f m; lower blocks %d, upper blocks %d (cell rows excluded)" % (
        (fp["x1"] - fp["x0"]) / 100.0, (fp["y1"] - fp["y0"]) / 100.0, sum(1 for r in rooms if r["z"] < 100 and not r.get("cell")), sum(1 for r in rooms if r["z"] >= 100 and not r.get("cell"))))
    low_c = sum(1 for r in rooms if r.get("cell") and r["z"] < 100)
    up_c = sum(1 for r in rooms if r.get("cell") and r["z"] >= 100)
    report("Cells: %d (lower %d + upper %d); sheet total 30 = 9 + 7 + 7 + 7" % (low_c + up_c, low_c, up_c))
    if low_c != 9 or up_c != 21:
        err("Cell count %d + %d, sheet says 9 + 21" % (low_c, up_c))

    report("== Dimensions ==")
    doors = [o for o in study.openings if not (o["id"].startswith("W0") or o["id"] in ("W03", "W04"))]
    narrow = [(o["id"], o["width"]) for o in doors if o["width"] < 2 * R + 20]
    low = [(o["id"], o["height"]) for o in doors if o["height"] < 2 * study.CAP_HH + 20]
    report("Doors/openings: %d, smallest width %d cm (capsule diameter %d); narrow: %s; low: %s" % (len(doors), min(o["width"] for o in doors), 2 * R, narrow or "none", low or "none"))
    for o in narrow:
        err("Opening %s only %d cm wide" % o)
    for o in low:
        err("Opening %s only %d cm high" % o)
    for s in d["stairs"]:
        report("Stair %-10s %2d steps, riser %.2f cm, tread %.1f cm, width %d cm, run %.0f cm, z %d -> %d" % (
            s["id"], s["steps"], s["_rise"], s["run"], s["hi"] - s["lo"], s["steps"] * s["run"], s["z_start"], s["z_start"] + s["total_rise"]))

    def clear_diam(x, y, fl, up=170.0):
        best = 1e9
        for g in an.geo:
            if g["z1"] <= fl + 10 or g["z0"] >= fl + up or g["kind"] == "stair":
                continue
            dx = max(g["x0"] - x, 0, x - g["x1"])
            dy = max(g["y0"] - y, 0, y - g["y1"])
            best = min(best, math.hypot(dx, dy))
        return 2.0 * best
    report("Clear widths (wall face to wall face / mesh, at the sample point; the sheet's widths are centre to centre):")
    for label, x, y, fl, want in (("north walkway", 2200.0, 773.0, 390.0, 1.8), ("west walkway", 773.0, 1400.0, 390.0, 1.8), ("south walkway", 2200.0, 2030.0, 390.0, 1.8),
                                  ("crossover", 3100.0, 1400.0, 390.0, 1.8), ("rec corridor", 1500.0, 3230.0, 390.0, 2.3), ("sally port", 3100.0, 2600.0, 390.0, 1.7),
                                  ("S1 prisoner stair", 4800.0, 790.0, 225.0, 1.6), ("work corridor", 3000.0, 3690.0, 0.0, 1.4), ("service alley", 950.0, 2400.0, 0.0, 1.4),
                                  ("north staff chase", 2000.0, 90.0, 0.0, 1.4), ("staff spine", 4510.0, 4000.0, 390.0, 1.8)):
        w = clear_diam(x, y, fl) / 100.0
        report("  %-18s %.2f m clear" % (label, w))
        if w < want:
            warn("%s clear width %.2f m below %.1f m" % (label, w, want))
    report("Ceilings: 2.7 m drop ceilings (z 270..300 lower, 660..690 upper) over chases, work corridor, service alley, rec corridor, staff spine; walkways/cells/rooms 3.6 m; hall and void to 7.5 m")

    report("== Walk simulation (capsule r=%d hh=%d, max step %d) ==" % (study.CAP_R, study.CAP_HH, study.STEP))
    paths = {}
    for r in d["routes"]:
        ok, why, zend, path = an.simulate(r)
        paths[r["id"]] = path
        want = r.get("end_z")
        endok = want is None or abs(zend - want) < 3.0
        report("  route %-62s %s%s (end floor z=%.0f%s)" % (r["id"], "PASS" if ok and endok else "FAIL ", "" if ok else " - " + why, zend, "" if want is None else ", expected %.0f" % want))
        if not ok:
            err("Route %s failed: %s" % (r["id"], why))
        elif not endok:
            err("Route %s ended at z=%.0f, expected %.0f" % (r["id"], zend, want))
    for r in d["blocked_routes"]:
        ok, why, zend, _ = an.simulate(r)
        report("  blocked %-52s %s (%s)" % (r["id"], "PASS (blocked)" if not ok else "FAIL (passable!)", why))
        if ok:
            err("Route %s should be blocked but is passable" % r["id"])
    f0 = an.floor_at(start[0], start[1], 0.0)
    sb = an.blocked_by(start[0], start[1], f0 if f0 is not None else 0.0)
    report("Player start (%d,%d) yaw %d floor z=%s blocked=%s -> %s" % (start[0], start[1], ps["yaw"], f0, sb and sb["id"], "VALID" if f0 is not None and sb is None else "INVALID"))
    if f0 is None or sb is not None:
        err("Player start invalid")

    report("== Reachability and edges ==")
    seen, expo = an.flood(start)
    report("Reachable walking cells (20 cm grid): %d (~%.0f m2)" % (len(seen), len(seen) * 0.04))
    reach = {}
    for (kx, ky, kz), (x, y, z) in seen.items():
        reach.setdefault((kx, ky), []).append(z)

    def reachable(x, y, zf):
        return any(abs(z - zf) < 3.0 for z in reach.get((int(x // 20.0), int(y // 20.0)), ()))
    for x, y, zf, expect, label in d["reachability"]["samples"]:
        got = reachable(x, y, zf)
        if got != expect:
            err("Reachability mismatch: %s (%d,%d,z%d) got %s expected %s" % (label, x, y, zf, got, expect))
        report("  %-56s (%5d,%5d,z%3d) reachable=%-5s expected=%-5s %s" % (label, x, y, zf, got, expect, "ok" if got == expect else "MISMATCH"))
    report("Unprotected walkable edges with drop > 60 cm: %d cells" % len(expo))
    groups = {}
    for x, y, z, dd in expo:
        groups.setdefault((int(x // 200), int(y // 200), int(z // 50)), []).append((x, y, z, dd))
    for key, items in sorted(groups.items())[:20]:
        report("    exposed edge near (%d,%d) walking z=%d drop up to %d (%d cells)" % (sum(i[0] for i in items) / len(items), sum(i[1] for i in items) / len(items), items[0][2], max(i[3] for i in items), len(items)))
    if expo:
        err("%d unprotected edge cells (falls possible)" % len(expo))

    report("== Room reach (every sheet block should be walkable from the intake; the commissary has no door in the sheet) ==")
    room_cells = {}
    for (kx, ky, kz), (x, y, z) in seen.items():
        r = room_at(rooms, x, y, 0.0 if z < 200 else 390.0)
        if r is not None:
            room_cells[r["id"]] = room_cells.get(r["id"], 0) + 1
    missing = [r["id"] for r in rooms if r["id"] not in room_cells and r["id"] != "L18"]
    report("  rooms with walkable cells: %d of %d; no reach: %s (L18 commissary is closed: the sheet gives it a window only)" % (len(room_cells), len(rooms), missing or "none"))
    for mid in missing:
        err("Room %s has no reachable floor" % mid)
    if "L18" in room_cells:
        err("Commissary should be window-only but has reachable floor")

    def cells(pred):
        return [(x, y, z) for (kx, ky, kz), (x, y, z) in seen.items() if pred(x, y, z)]

    def cover(eyes, pts, h):
        if not pts:
            return 0, 0
        n = sum(1 for (x, y, z) in pts if any(an.visible(e, (x, y, z + h)) for e in eyes))
        return n, len(pts)

    def pct(nt):
        return 100 * nt[0] // max(1, nt[1])

    report("== First ten seconds (spawn, camera ~200 cm behind) ==")
    eye = (start[0], start[1], 170.0)
    cam = (start[0] + 140.0, start[1], 230.0)

    def vis_any(t):
        return an.visible(eye, t) or an.visible(cam, t)
    for label, tgt in (("D02 intake opening (centre)", (5400.0, 925.0, 120.0)), ("hall long axis, far west (01 wall x=815)", (830.0, 1030.0, 150.0)),
                       ("S1 first step", (5190.0, 790.0, 20.0)), ("crossover underside", (3100.0, 1030.0, 355.0)), ("S2 stair body", (1580.0, 1780.0, 100.0))):
        report("  spawn -> %-40s %s" % (label, "VISIBLE" if vis_any(tgt) else "hidden"))
    if not vis_any((830.0, 1030.0, 150.0)):
        warn("The hall's long axis / 01 wall is not visible from the spawn")
    gl = [l for l in d.get("lines", []) if l["id"].startswith("Guide_")]
    if gl:
        last = max(gl, key=lambda l: int(l["id"].split("_")[1]))
        report("  floor guide: %d strips from the arrival door to (%d,%d), at the foot of S1 (first step x 5173..5200, y 700..880)" % (len(gl), last["p1"][0], last["p1"][1]))
        if not (5150 <= last["p1"][0] <= 5280 and 700 <= last["p1"][1] <= 880):
            err("Floor guide does not end at the first step of S1")
    ok = an.visible((3100.0, 1400.0, 555.0), (5390.0, 1500.0, 130.0))
    report("  secured door D06 (x=5400, y 1350..1650) from the crossover centre: %s" % ("VISIBLE" if ok else "hidden"))
    if not ok:
        err("Secured door D06 is not framed from the crossover")
    arm_back = min(an.free_length(start[0], start[1], 90 + h, 0.0, 200.0) for h in (160.0, 230.0))
    report("  camera arm directly behind the spawn (east): %.0f of 200 cm free (arrival wall face %d cm behind the start)" % (arm_back, 6085 - int(start[0])))

    report("== Sightlines ==")
    look_eyes = [(5520.0, y, 390 + 165.0) for y in (1000.0, 1250.0, 1500.0, 1750.0)]
    band = cells(lambda x, y, z: abs(z) < 2 and 800 < x < 2100 and 880 < y < 1920)
    rest = cells(lambda x, y, z: abs(z) < 2 and 2100 <= x < 5400 and 880 < y < 1920)
    b1, r1 = cover(look_eyes, band, 100.0), cover(look_eyes, rest, 100.0)
    report("  T06 lookout (4 eyes, knee height) sees: blind band X 8-21 %d%% (%d/%d), rest of the hall %d%% (%d/%d)" % (pct(b1), b1[0], b1[1], pct(r1), r1[0], r1[1]))
    if pct(b1) >= pct(r1):
        report("  NOTE: the T06 band is not blind from the lookout with the crossover as specified (30 cm slab, see-through mesh): sightlines from an eye at z 5.5 m pass below the crossover underside.")
    seat = cells(lambda x, y, z: abs(z) < 2 and 1600 < x < 5400 and 2000 <= y < 2800)
    gp = cover([(5440.0, 2400.0, 160.0)], seat, 150.0)
    report("  guard post window W01 sees %d%% of the seating (%d/%d cells)" % (pct(gp), gp[0], gp[1]))
    corr = (5560.0, 3690.0, 160.0)
    far = [(x, 3690.0, 120.0) for x in (5200.0, 4000.0, 3000.0, 2000.0, 1200.0, 950.0)]
    report("  staff room window W02 down the work corridor: sees %d of %d targets out to x=%d (%.1f m)" % (sum(1 for t in far if an.visible(corr, t)), len(far), 950, (corr[0] - 950.0) / 100.0))
    if not an.visible(corr, far[-1]):
        err("W02 does not give a sightline down the whole work corridor")
    report("  crossover sees the lookout window W07 and its lit strip: %s" % ("yes" if an.visible((3100.0, 1400.0, 555.0), (5385.0, 1400.0, 686.0)) else "no"))
    net_ok = any(b["kind"] == "net" for b in study.boxes)
    report("  safety net at z 3.6 over the void: %s (visual only, no collision); mesh bars are collidable with a %d cm gap < the %d cm capsule" % ("present" if net_ok else "MISSING", int(StudyV7.PITCH - StudyV7.BAR), 2 * R))
    if not net_ok:
        err("Safety net missing")

    report("== Hiding opportunities (back of house) ==")
    covers = ["Walkin_Shelves", "Dry_Shelf_1", "Dry_Shelf_3", "Laundry_Machines", "Laundry_Chute_Outlet", "Linen_Shelf_1", "Maint_Rack", "Bay_Pallets", "Bay_Crates", "Heater_Tank", "Plant_Boiler_1", "Cover_Cart_L1"]
    miss = [c_ for c_ in covers if not any(b["id"] == c_ for b in study.boxes)]
    report("  cover pieces present: %d of %d%s" % (len(covers) - len(miss), len(covers), "" if not miss else "; missing %s" % miss))
    wc = cells(lambda x, y, z: abs(z) < 2 and 880 < x < 5340 and 3615 < y < 3765)
    wc_v = cover([(950.0, 3690.0, 160.0)], wc, 150.0)
    report("  work corridor: the west clock-in end sees %d%% of its length (a straight 45 m run, as drawn)" % pct(wc_v))

    report("== Staff network (flood restricted to guard/staff/intake rooms) ==")

    def staff_flood(exclude=()):
        seen_s = {(int(start[0] // 20), int(start[1] // 20), 0): 1}
        stack = [(start[0], start[1], 0.0)]
        while stack:
            x, y, z = stack.pop()
            for dx, dy in ((20, 0), (-20, 0), (0, 20), (0, -20)):
                nx, ny = x + dx, y + dy
                f = an.floor_at(nx, ny, z)
                if f is None or f < z - an.STEP or an.blocked_by(nx, ny, f):
                    continue
                r = room_at(rooms, nx, ny, 0.0 if f < 200 else 390.0)
                if r is None:
                    if not any(a <= nx <= b and c_ <= ny <= e for a, b, c_, e in STAIR_BOXES):
                        continue
                elif r["area"] not in STAFF_AREAS or r["id"] in exclude:
                    continue
                key = (int(nx // 20), int(ny // 20), int(round(f)))
                if key not in seen_s:
                    seen_s[key] = 1
                    stack.append((nx, ny, f))
        out = {}
        for (kx, ky, kz) in seen_s:
            r = room_at(rooms, kx * 20 + 10, ky * 20 + 10, 0.0 if kz < 200 else 390.0)
            if r:
                out[r["id"]] = 1
        return out
    want_staff = ["L01", "L02", "L03", "L04", "L06", "L10", "L11", "L12", "L13", "L14", "L15", "L31", "L32", "U01", "U02", "U03", "U11", "U12", "U13", "U21", "U22", "U23", "U24"]
    got = staff_flood()
    miss_s = [i for i in want_staff if i not in got]
    report("  staff-only flood from the intake reaches %d of %d staff/guard blocks on both tiers; not reached: %s" % (len(want_staff) - len(miss_s), len(want_staff), miss_s or "none"))
    for i in miss_s:
        err("Staff network does not reach %s without crossing prisoner space" % i)
    got2 = staff_flood(exclude=("L02", "U02"))
    loop = [i for i in ("L03", "U03", "U21") if i in got2]
    report("  loop closure: with the west chase (L02, U02) removed, the south chases and spine are still reached through the east column: %s" % ("yes" if len(loop) == 3 else "NO (%s)" % loop))
    if len(loop) != 3:
        err("Staff loop is not closed on the east (south chase / spine not reachable without the west chase)")

    report("== Stair feet ==")
    for label, (px, py) in (("S1 landing (mid)", (5300.0, 640.0)), ("S2 foot (hall)", (1700.0, 1780.0)), ("S3 foot apron (vestibule)", (5520.0, 1720.0)), ("S4 foot apron (SE block)", (5935.0, 4457.0))):
        rad = clear_diam(px, py, 0.0) / 2.0
        report("  %-28s free radius %.0f cm at (%d,%d)" % (label, rad, px, py))
        if rad < 34:
            warn("%s is cramped (free radius %.0f cm)" % (label, rad))

    report("== Camera clearance along the test routes (approximation; the sheet asks for a 2 m arm in corridors and the camera ignoring mesh and net) ==")
    arm = float(d["params"]["camera_arm"])
    tight = {}
    n_samples = n_back_short = n_arc_short = 0
    nomesh = Analyzer(study, include=lambda b: b["kind"] not in ("mesh",))
    for rid, path in paths.items():
        last = None
        for (x, y, z, nxt) in path:
            if last is not None and math.hypot(x - last[0], y - last[1]) < 50:
                continue
            last = (x, y)
            back = math.degrees(math.atan2(nxt[1] - y, nxt[0] - x)) + 180.0
            n_samples += 1
            worst_back = min(nomesh.free_length(x, y, z + h, back, arm) for h in (160.0, 230.0))
            arc = min(nomesh.free_length(x, y, z + h, back + off, arm) for h in (160.0, 230.0) for off in (-90, -45, 45, 90))
            if worst_back < arm - 0.1:
                n_back_short += 1
                key = (int(x // 200) * 200, int(y // 200) * 200, int(z // 100) * 100)
                tight[key] = min(tight.get(key, 1e9), worst_back)
            if arc < 120:
                n_arc_short += 1
    report("Route samples: %d; arm shortened directly behind the player at %d (%.0f%%) even with the mesh ignored; an orbit extreme would be < 120 cm at %d" % (
        n_samples, n_back_short, 100.0 * n_back_short / max(1, n_samples), n_arc_short))
    for key, v in sorted(tight.items(), key=lambda kv: kv[1])[:8]:
        report("    tightest around (%d..%d, %d..%d, z~%d): %.0f cm of arm free" % (key[0], key[0] + 200, key[1], key[1] + 200, key[2], v))
    report("Errors: %d  Warnings: %d" % (len(errors), len(warnings)))
    return errors, warnings
