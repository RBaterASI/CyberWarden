"""Geometry + analytic validation for the Floor 1 RECTANGLE STUDY V6 (built from the Greybox Build Sheet, Nov 6 2026).

Pure Python (no `unreal` import). StudyV6 = StudyV2 (unchanged) + the layout's `lines` (floor guide). Coordinates are the sheet's:
cm, +X east, +Y SOUTH (plan), Z up. NOTE the older modules call +Y "north"; in V6 facings in the JSON are generator letters.
"""
import math

import cw_rectstudy_v2 as v2
from cw_rectstudy import Analyzer, load  # noqa: F401  (re-exported)


class StudyV6(v2.StudyV2):
    def _build(self):
        super()._build()
        for ln in self.data.get("lines", []):
            self._line_spec(ln)


def room_at(rooms, x, y, z):
    """The room whose rectangle contains (x,y) and whose floor level matches z (within 60 cm), smallest area first."""
    best = None
    for r in rooms:
        if r["x0"] - 0.5 <= x <= r["x1"] + 0.5 and r["y0"] - 0.5 <= y <= r["y1"] + 0.5 and abs(r["z"] - z) < 60:
            a = (r["x1"] - r["x0"]) * (r["y1"] - r["y0"])
            if best is None or a < best[0]:
                best = (a, r)
    return best[1] if best else None


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
    fp = d["meta"]["footprint"]
    rooms = study.rooms
    area_of = lambda r: r["area"] if r else None   # noqa: E731

    report("== Geometry summary ==")
    kinds = {}
    for b in study.boxes:
        kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    report("Boxes: %d total (%s); collision boxes %d; text signs %d; lights %d; markers %d; floor-guide strips %d" % (
        len(study.boxes), ", ".join("%s=%d" % kv for kv in sorted(kinds.items())), len(an.geo), len(study.texts), len(study.lights), len(study.markers), len(study.lines)))
    report("Footprint: x %d..%d, y %d..%d = %.1f m x %.1f m (61 x 51 m), exterior walls on all four sides, roof slab 750..780" % (
        fp["x0"], fp["x1"], fp["y0"], fp["y1"], (fp["x1"] - fp["x0"]) / 100.0, (fp["y1"] - fp["y0"]) / 100.0))
    n_cells = sum(1 for r in rooms if r.get("cell"))
    report("Cells: %d (lower %d + upper %d); sheet total 33" % (n_cells, sum(1 for r in rooms if r.get("cell") and r["z"] < 100), sum(1 for r in rooms if r.get("cell") and r["z"] >= 100)))
    if n_cells != 33:
        err("Cell count %d, sheet says 33" % n_cells)

    report("== Dimensions ==")
    doors = [o for o in study.openings if not (o["id"].startswith("W0") or o["id"] == "Kitchen_Hatch")]
    narrow = [(o["id"], o["width"]) for o in doors if o["width"] < 2 * R + 20]
    low = [(o["id"], o["height"]) for o in doors if o["height"] < 2 * study.CAP_HH + 20]
    report("Doors/openings: %d, smallest width %d cm (capsule diameter %d); narrow: %s; low: %s" % (
        len(doors), min(o["width"] for o in doors), 2 * R, narrow or "none", low or "none"))
    for o in narrow:
        err("Opening %s only %d cm wide" % o)
    for o in low:
        err("Opening %s only %d cm high" % o)
    for s in d["stairs"]:
        run_total = s["steps"] * s["run"]
        report("Stair %-10s %2d steps, riser %.2f cm, tread %.1f cm, width %d cm, run %.0f cm, z %d -> %d" % (
            s["id"], s["steps"], s["_rise"], s["run"], s["hi"] - s["lo"], run_total, s["z_start"], s["z_start"] + s["total_rise"]))
        if s["_rise"] > 18.0:
            err("Stair %s riser %.1f cm too high" % (s["id"], s["_rise"]))

    # ---- routes
    report("== Walk simulation (capsule r=%d hh=%d, max step %d) ==" % (study.CAP_R, study.CAP_HH, study.STEP))
    paths = {}
    for r in d["routes"]:
        ok, why, zend, path = an.simulate(r)
        paths[r["id"]] = path
        want = r.get("end_z")
        endok = want is None or abs(zend - want) < 3.0
        report("  route %-38s %s%s (end floor z=%.0f%s)" % (r["id"], "PASS" if ok and endok else "FAIL ", "" if ok else " - " + why, zend,
                                                         "" if want is None else ", expected %.0f" % want))
        if not ok:
            err("Route %s failed: %s" % (r["id"], why))
        elif not endok:
            err("Route %s ended at z=%.0f, expected %.0f" % (r["id"], zend, want))
    for r in d["blocked_routes"]:
        ok, why, zend, _ = an.simulate(r)
        report("  blocked %-36s %s (%s)" % (r["id"], "PASS (blocked)" if not ok else "FAIL (passable!)", why))
        if ok:
            err("Route %s should be blocked but is passable" % r["id"])
    f0 = an.floor_at(start[0], start[1], 0.0)
    sb = an.blocked_by(start[0], start[1], f0 if f0 is not None else 0.0)
    report("Player start (%d,%d) yaw %d floor z=%s blocked=%s -> %s" % (start[0], start[1], ps["yaw"], f0, sb and sb["id"], "VALID" if f0 is not None and sb is None else "INVALID"))
    if f0 is None or sb is not None:
        err("Player start invalid")

    # ---- reachability
    report("== Reachability and edges ==")
    seen, expo = an.flood(start)
    report("Reachable walking cells (20 cm grid): %d (~%.0f m2)" % (len(seen), len(seen) * 0.04))
    reach = {}
    for (kx, ky, kz), (x, y, z) in seen.items():
        reach.setdefault((kx, ky), []).append(z)

    def reachable(x, y, zf):
        return any(abs(z - zf) < 3.0 for z in reach.get((int(x // 20.0), int(y // 20.0)), ()))
    bad = 0
    for x, y, zf, expect, label in d["reachability"]["samples"]:
        got = reachable(x, y, zf)
        if got != expect:
            bad += 1
            err("Reachability mismatch: %s (%d,%d,z%d) got %s expected %s" % (label, x, y, zf, got, expect))
        report("  %-48s (%5d,%5d,z%3d) reachable=%-5s expected=%-5s %s" % (label, x, y, zf, got, expect, "ok" if got == expect else "MISMATCH"))
    report("Unprotected walkable edges with drop > 60 cm: %d cells" % len(expo))
    groups = {}
    for x, y, z, dd in expo:
        groups.setdefault((int(x // 200), int(y // 200), int(z // 50)), []).append((x, y, z, dd))
    for key, items in sorted(groups.items())[:20]:
        report("    exposed edge near (%d,%d) walking z=%d drop up to %d (%d cells)" % (
            sum(i[0] for i in items) / len(items), sum(i[1] for i in items) / len(items), items[0][2], max(i[3] for i in items), len(items)))
    if expo:
        err("%d unprotected edge cells (falls possible)" % len(expo))

    # ---- every room reachable (except the closed plant), per the sheet
    report("== Room reach (every sheet block should be walkable from the intake; the plant is closed) ==")
    CLOSED = {"L22"}
    room_cells = {}
    for (kx, ky, kz), (x, y, z) in seen.items():
        r = room_at(rooms, x, y, 0.0 if z < 200 else 390.0)
        if r is not None and not r.get("cell"):
            room_cells[r["id"]] = room_cells.get(r["id"], 0) + 1
        elif r is not None:
            room_cells[r["id"]] = room_cells.get(r["id"], 0) + 1
    missing = [r["id"] for r in rooms if r["id"] not in room_cells and r["id"] not in CLOSED and r["id"] not in ("L06b",)]
    report("  rooms with walkable cells: %d of %d; no reach: %s" % (len(room_cells), len(rooms), missing or "none"))
    for mid in missing:
        err("Room %s has no reachable floor" % mid)
    if "L22" in room_cells:
        err("Plant should be closed but has reachable floor")

    return _rest(study, d, an, seen, reach, paths, start, reachable, report, err, warn, errors, warnings, rooms, R)


def _rest(study, d, an, seen, reach, paths, start, reachable, report, err, warn, errors, warnings, rooms, R):
    def cells(pred):
        return [(x, y, z) for (kx, ky, kz), (x, y, z) in seen.items() if pred(x, y, z)]

    def cover(eyes, pts, h):
        if not pts:
            return 0, 0
        n = sum(1 for (x, y, z) in pts if any(an.visible(e, (x, y, z + h)) for e in eyes))
        return n, len(pts)

    def pct(nt):
        return 100 * nt[0] // max(1, nt[1])

    # ---- first ten seconds
    report("== First ten seconds (player start, camera ~200 cm behind) ==")
    eye = (start[0], start[1], 170.0)
    cam = (start[0] + 200.0, start[1], 230.0)       # start faces west (-X), the camera sits behind (east)

    def vis_any(t):
        return an.visible(eye, t) or an.visible(cam, t)
    for label, tgt in (("D02 intake opening (centre)", (5400.0, 910.0, 120.0)), ("hall long axis, far west end (x=900)", (900.0, 1030.0, 150.0)),
                       ("NE stair first step", (5190.0, 630.0, 20.0)), ("NE stair, void-side rail", (4900.0, 800.0, 200.0)),
                       ("crossover underside", (3100.0, 1030.0, 355.0)), ("lookout window head strip", (5400.0, 1400.0, 685.0))):
        report("  start -> %-38s %s" % (label, "VISIBLE" if vis_any(tgt) else "hidden"))
    if not vis_any((900.0, 1030.0, 150.0)):
        warn("The hall's long axis is not visible from the start")

    # guide line ends on the first step of S1
    gl = [l for l in d.get("lines", []) if l["id"].startswith("Guide_")]
    if gl:
        last = max(gl, key=lambda l: int(l["id"].split("_")[1]))
        report("  floor guide: %d strips from the arrival door (6040,600) to (%d,%d), the first step of S1 (x 5173..5200, y 460..800)" % (len(gl), last["p1"][0], last["p1"][1]))
        if not (5173 <= last["p1"][0] <= 5200 and 460 <= last["p1"][1] <= 800):
            err("Floor guide does not end on the first step of S1")

    report("  guard-side view: secured door D07 (x=5400, y 1350..1650) from the crossover centre (3100, 1400, 555): %s" %
          ("VISIBLE" if an.visible((3100.0, 1400.0, 555.0), (5390.0, 1500.0, 130.0)) else "hidden"))
    if not an.visible((3100.0, 1400.0, 555.0), (5390.0, 1500.0, 130.0)):
        err("Secured door D07 is not framed from the crossover")
    report("  secured door D07 from the player start looking back (camera east of it is behind the wall): not visible by design (spawn is inside the intake)")

    # ---- T05 lookout blind band
    report("== Lookout sightlines (T05 blind band X 8..21, Y 8..20, lower tier) ==")
    look_eyes = [(5500.0, y, 390 + 165.0) for y in (1000.0, 1250.0, 1500.0, 1750.0)]
    band = cells(lambda x, y, z: abs(z) < 2 and 800 < x < 2100 and 800 < y < 2000)
    rest = cells(lambda x, y, z: abs(z) < 2 and 2100 <= x < 5400 and 800 < y < 2000)
    b1 = cover(look_eyes, band, 100.0)
    r1 = cover(look_eyes, rest, 100.0)
    report("  floor visible from the lookout (4 eye positions, knee height): blind band %d%% (%d/%d), rest of the hall %d%% (%d/%d)" % (pct(b1), b1[0], b1[1], pct(r1), r1[0], r1[1]))
    if pct(b1) >= pct(r1):
        report("  NOTE: with the crossover as specified (30 cm slab at z 3.6-3.9, open rails) the T05 band is NOT blind from the lookout: a sightline from "
               "an eye at z 5.5 m to a person standing at x 8-21 m passes 0.3-0.8 m below the crossover underside. The board's hatched band only "
               "appears if the crossover gets a deeper fascia (not in the sheet); the study leaves the crossover as written.")
    sw = cells(lambda x, y, z: abs(z) < 2 and 5 * 100 < x < 54 * 100 and 2000 <= y < 2800)
    sw_v = cover(look_eyes, sw, 150.0)
    report("  seating (under the upper tier) seen through the hall: %d%% of %d cells at head height" % (pct(sw_v), sw_v[1]))
    gp_eye = (5440.0, 2400.0, 160.0)   # guard post window, looking west through W01
    gp = cover([gp_eye], cells(lambda x, y, z: abs(z) < 2 and x < 5400 and 2000 <= y < 2800), 150.0)
    report("  guard post window W01 sees %d%% of the seating (%d/%d cells)" % (pct(gp), gp[0], gp[1]))
    report("  lookout window W05 and the lit strip: visible from the crossover: %s" % ("yes" if an.visible((3100.0, 1400.0, 555.0), (5385.0, 1400.0, 686.0)) else "no"))

    # ---- hiding / cover (service side)
    report("== Hiding opportunities (service side) ==")
    svc = cells(lambda x, y, z: abs(z) < 2 and 820 < x < 5380 and 4620 < y < 4880)
    from_w = [(950.0, 2900.0, 160.0)]
    report("  service south leg: %d walkable cells; the west leg end (950,2900) sees %d%% of the south leg" % (len(svc), pct(cover(from_w, svc, 150.0))))
    d18 = [(2000.0, 4560.0), (3200.0, 4560.0), (4300.0, 4560.0)]
    for x, y in d18:
        report("  recessed door at x=%d: reachable %s; visible from the hall-side west leg corner (950,4700): %s" % (
            x, reachable(x, 4580.0, 0), an.visible((950.0, 4700.0, 150.0), (x, 4580.0, 150.0))))
    for cid in ("Cover_Cart_H1", "Cover_Cart_H2", "Cover_Locker_W", "Cover_Locker_E", "Cover_Shelf_P1", "Cover_Shelf_L1", "Laundry_Machines"):
        b = next((bb for bb in study.boxes if bb["id"] == cid), None)
        if b is None:
            err("Cover piece %s missing" % cid)
    report("  cover pieces present (carts, lockers, shelving, machines)")

    # ---- staff network (guard moves without crossing prisoner space)
    report("== Staff network (flood restricted to guard/staff/intake rooms) ==")
    STAFF_AREAS = {"Guard", "Staff", "Intake"}
    sx, sy = start
    z0 = 0.0
    seen_s = {}
    stack = [(sx, sy, z0)]
    seen_s[(int(sx // 20), int(sy // 20), 0)] = 1
    while stack:
        x, y, z = stack.pop()
        for dx, dy in ((20, 0), (-20, 0), (0, 20), (0, -20)):
            nx, ny = x + dx, y + dy
            f = an.floor_at(nx, ny, z)
            if f is None or f < z - an.STEP or an.blocked_by(nx, ny, f):
                continue
            r = room_at(rooms, nx, ny, 0.0 if f < 200 else 390.0)
            # stair flights between tiers: allow while on a staff-stair step (any z) inside a staff room footprint
            if r is None or r["area"] not in STAFF_AREAS:
                if r is not None and r["area"] in ("Hall",):
                    continue
                if r is None:
                    # S3/S4 interior (stair footprints) are inside staff rooms; unmatched cells (e.g. mid-flight) are allowed inside those footprints only
                    if not (5400 <= nx <= 5870 and 1700 <= ny <= 2000) and not (5440 <= nx <= 5830 and 4440 <= ny <= 5050):
                        continue
                else:
                    continue
            key = (int(nx // 20), int(ny // 20), int(round(f)))
            if key not in seen_s:
                seen_s[key] = 1
                stack.append((nx, ny, f))
    staff_rooms = {}
    for (kx, ky, kz) in seen_s:
        r = room_at(rooms, kx * 20 + 10, ky * 20 + 10, 0.0 if kz < 200 else 390.0)
        if r:
            staff_rooms[r["id"]] = staff_rooms.get(r["id"], 0) + 1
    want_staff = ["L01", "L02", "L04", "L08", "L09", "L10", "L12", "L17", "L18", "U02", "U02b", "U06", "U07", "U17", "U18", "U19", "U20", "U21"]
    got_staff = [i for i in want_staff if i in staff_rooms]
    miss_staff = [i for i in want_staff if i not in staff_rooms]
    report("  staff-only flood from the intake reaches %d of %d staff/guard blocks; not reached: %s" % (len(got_staff), len(want_staff), miss_staff or "none"))
    report("  upper staff blocks reached without touching a prisoner room: %s" % ("yes" if all(i in staff_rooms for i in ("U07", "U18", "U19", "U20", "U21", "U17", "U06", "U02")) else "NO"))
    for i in miss_staff:
        err("Staff network does not reach %s without crossing prisoner space" % i)

    # ---- stair feet
    report("== Stair feet ==")

    def clear_radius(x, y, fl):
        best = 1e9
        for g in an.geo:
            if g["z1"] <= fl + 10 or g["z0"] >= fl + 170:
                continue
            dx = max(g["x0"] - x, 0, x - g["x1"])
            dy = max(g["y0"] - y, 0, y - g["y1"])
            best = min(best, math.hypot(dx, dy))
        return best
    for label, (px, py) in (("S1 NE foot (landing L05, mid)", (5290.0, 640.0)), ("S2 SW foot (hall)", (1600.0, 1830.0))):
        rad = clear_radius(px, py, 0.0)
        report("  %-30s free radius %.0f cm at (%d,%d)" % (label, rad, px, py))
        if rad < 80:
            warn("%s is cramped (free radius %.0f cm)" % (label, rad))
    report("  S1 landing L05 is %d cm wide between the first step and the hall-east wall face (x 5200..5385) and opens south into the hall" % (5385 - 5200))
    arm_back = min(an.free_length(start[0], start[1], 90 + h, 0.0, 200.0) for h in (160.0, 230.0))
    report("  camera arm directly behind the spawn (east, toward the arrival wall): %.0f of 200 cm free; the wall face is %d cm behind the start" % (arm_back, 6085 - int(start[0])))

    # ---- camera clearance
    report("== Camera clearance along the test routes (approximation, arm %d cm) ==" % d["params"]["camera_arm"])
    arm = float(d["params"]["camera_arm"])
    tight = {}
    n_samples = n_back_short = n_arc_short = 0
    for rid, path in paths.items():
        last = None
        for (x, y, z, nxt) in path:
            if last is not None and math.hypot(x - last[0], y - last[1]) < 50:
                continue
            last = (x, y)
            hd = math.degrees(math.atan2(nxt[1] - y, nxt[0] - x))
            back = hd + 180.0
            n_samples += 1
            worst_back = min(an.free_length(x, y, z + h, back, arm) for h in (160.0, 230.0))
            arc = min(an.free_length(x, y, z + h, back + off, arm) for h in (160.0, 230.0) for off in (-90, -45, 45, 90))
            if worst_back < arm - 0.1:
                n_back_short += 1
                key = (int(x // 200) * 200, int(y // 200) * 200, int(z // 100) * 100)
                tight[key] = min(tight.get(key, 1e9), worst_back)
            if arc < 120:
                n_arc_short += 1
    report("Route samples: %d; arm shortened directly behind the player at %d (%.0f%%); an orbit extreme would be < 120 cm at %d" % (
        n_samples, n_back_short, 100.0 * n_back_short / max(1, n_samples), n_arc_short))
    for key, v in sorted(tight.items(), key=lambda kv: kv[1])[:8]:
        report("    tightest around (%d..%d, %d..%d, z~%d): %.0f cm of arm free" % (key[0], key[0] + 200, key[1], key[1] + 200, key[2], v))
    report("Errors: %d  Warnings: %d" % (len(errors), len(warnings)))
    return errors, warnings
