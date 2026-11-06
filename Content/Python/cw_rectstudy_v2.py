"""Geometry + analytic validation for the Floor 1 RECTANGLE STUDY V2 (follows the user's upper-tier sketch).

Pure Python (no `unreal` import). Reuses the primitives of cw_rectstudy (V1) by subclassing; V1 itself is unchanged.
Input: Docs/Layout/S01_LW_F1_RectangleStudy_V2.json. Units cm, +X east, +Y north, Z up.
"""
import math

import cw_rectstudy as base
from cw_rectstudy import Analyzer, load  # noqa: F401  (load re-exported)


class StudyV2(base.Study):
    """Expands the V2 JSON: cell rows, slabs, walls (cuts from cell rows), balustrades, stairs, columns, tables, signs, lights."""

    def _build(self):
        d = self.data
        T = self.T
        self.rows = {}
        self.row_doors = {}
        for row in d["cell_rows"]:
            self._cell_row(row)
        # ground pads (thin colour tint on the base floor; no collision)
        for r in self.rooms:
            if r.get("pad"):
                self.box("Pad_" + r["id"], r["x0"], r["y0"], r["z"], r["x1"], r["y1"], r["z"] + 2.0, "marking", "lit:" + r["area"], False, "Floors")
        for s in d["slabs"]:
            mat = ("lit:" + s["area"]) if s.get("area") else None
            self.box("Slab_" + s["id"], s["x0"], s["y0"], s["z0"], s["x1"], s["y1"], s["z1"], "slab", mat, True, "Slabs")
        for w in d["walls"]:
            w2 = dict(w)
            cuts = list(w.get("cuts", []))
            for rid in w.get("cuts_from", []):
                cuts += self.row_doors.get(rid, [])
            w2["cuts"] = cuts
            w2.pop("cuts_from", None)
            self._wall(w2)
        for r in d["rails"]:
            self._balustrade(r)
        for s in d["stairs"]:
            self._stair(s)
        for c in d["columns"]:
            x = c["from"]
            h = c["size"] / 2.0
            while x <= c["to"]:
                if not any(a <= x <= b for a, b in c.get("skip", [])):
                    if c["axis"] == "x":
                        self.box("Col_%s_%d" % (c["axis"] + str(c["line"]), x), x - h, c["line"] - h, 0, x + h, c["line"] + h, c["z1"], "prop", None, True, "Props")
                    else:
                        self.box("Col_%s_%d" % (c["axis"] + str(c["line"]), x), c["line"] - h, x - h, 0, c["line"] + h, x + h, c["z1"], "prop", None, True, "Props")
                x += c["step"]
        tb = d["tables"]
        for ri, ry in enumerate(tb["rows"]):
            for ci, cx in enumerate(tb["cols"]):
                self.box("Table_%d_%d" % (ri + 1, ci + 1), cx - tb["len"] / 2, ry - tb["dep"] / 2, 0, cx + tb["len"] / 2, ry + tb["dep"] / 2, tb["h"], "prop", "lit:" + tb["area"], True, "Props")
                for side in (-1, 1):
                    self.box("Bench_%d_%d_%d" % (ri + 1, ci + 1, side), cx - tb["len"] / 2, ry + side * tb["bench_off"] - 18, 0,
                             cx + tb["len"] / 2, ry + side * tb["bench_off"] + 18, tb["bench_h"], "prop", "lit:" + tb["area"], True, "Props")
        for b in d["boxes"]:
            kind = "marking" if not b.get("collision", True) else "prop"
            self.box(b["id"], b["x0"], b["y0"], b["z0"], b["x1"], b["y1"], b["z1"], kind, b.get("mat"), b.get("collision", True),
                     "Markings" if kind == "marking" else "Props", ["Id:" + b["id"]])
        for s in d["signs"]:
            self._sign(s)
        for row_id, doors in self.row_doors.items():
            row = self.rows[row_id]
            for i, dc in enumerate(doors):
                self._door_label(row, i, dc)
        for m in d["markers"]:
            self.markers.append(dict(m))
        self._lights()

    def _cell_row(self, row):
        T = self.T
        rid = row["id"]
        self.rows[rid] = row
        doors = []
        along_x = row["along"] == "x"
        front, back, z, ceil = float(row["front"]), float(row["back"]), float(row["z"]), float(row["ceil"])
        lo_s, hi_s = min(front, back), max(front, back)
        for i in range(row["count"]):
            s0 = row["from"] + i * row["width"]
            s1 = s0 + row["width"]
            c = (s0 + s1) / 2.0
            if along_x:
                x0, x1, y0, y1 = s0, s1, lo_s, hi_s
            else:
                x0, x1, y0, y1 = lo_s, hi_s, s0, s1
            self.rooms.append({"id": "Cell_%s%d" % (row["label"], i + 1 + row.get("num0", 0)), "name": "Cell %s%d" % (row["label"], i + 1 + row.get("num0", 0)), "area": row["area"],
                               "sign": "%s%d" % (row["label"], i + 1 + row.get("num0", 0)), "x0": x0, "y0": y0, "x1": x1, "y1": y1, "z": z, "ceil": ceil, "cell": True})
            if row.get("pad"):
                self.box("Pad_Cell_%s%d" % (row["label"], i + 1 + row.get("num0", 0)), x0, y0, z, x1, y1, z + 2.0, "marking", "lit:" + row["area"], False, "Floors")
            doors.append({"id": "Door_%s%d" % (row["label"], i + 1 + row.get("num0", 0)), "name": "Cell door %s%d" % (row["label"], i + 1 + row.get("num0", 0)), "c": c, "w": row["door_w"],
                          "z0": z, "h": row["door_h"], "label": "%s%d" % (row["label"], i + 1 + row.get("num0", 0))})
            # bunk against the back wall
            if along_x:
                by0, by1 = (back - 110, back - 20) if back > front else (back + 20, back + 110)
                self.box("Bunk_%s%d" % (row["label"], i + 1 + row.get("num0", 0)), s0 + 30, by0, z, s0 + 250, by1, z + 100, "prop", "lit:" + row["area"], True, "Props")
            else:
                self.box("Bunk_%s%d" % (row["label"], i + 1 + row.get("num0", 0)), back + 20, c - 110, z, back + 110, c + 110, z + 100, "prop", "lit:" + row["area"], True, "Props")
        for k in range(row["count"] + 1):
            p = row["from"] + k * row["width"]
            if along_x:
                self.box("CellWall_%s_%d" % (rid, k), p - T / 2, lo_s, z, p + T / 2, hi_s, z + ceil, "wall", None, True, "Walls")
            else:
                self.box("CellWall_%s_%d" % (rid, k), lo_s, p - T / 2, z, hi_s, p + T / 2, z + ceil, "wall", None, True, "Walls")
        self.row_doors[rid] = doors

    def _door_label(self, row, i, dc):
        T = self.T
        face = row["face"]
        front = float(row["front"])
        c = dc["c"]
        zc = dc["z0"] + dc["h"] + 24
        if face == "S":
            x, y = c, front - T / 2
        elif face == "N":
            x, y = c, front + T / 2
        else:
            x, y = front + T / 2, c
        self._sign({"text": dc["label"], "x": x, "y": y, "z": zc, "f": face, "size": 14, "area": row["area"], "_name": "Door_" + dc["label"]})


# ==========================================================================================
# Analysis
# ==========================================================================================
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

    report("== Geometry summary ==")
    kinds = {}
    for b in study.boxes:
        kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    report("Boxes: %d total (%s); collision boxes %d; text signs %d; lights %d; markers %d" % (
        len(study.boxes), ", ".join("%s=%d" % kv for kv in sorted(kinds.items())), len(an.geo), len(study.texts), len(study.lights), len(study.markers)))
    report("Footprint: x %d..%d, y %d..%d = %.1f m x %.1f m, one continuous rectangle with exterior walls on all four sides" % (
        fp["x0"], fp["x1"], fp["y0"], fp["y1"], (fp["x1"] - fp["x0"]) / 100.0, (fp["y1"] - fp["y0"]) / 100.0))

    report("== Dimensions ==")
    doors = [o for o in study.openings if not o["id"].startswith("Win_")]
    narrow = [(o["id"], o["width"]) for o in doors if o["width"] < 2 * R + 40]
    low = [(o["id"], o["height"]) for o in doors if o["height"] < 2 * study.CAP_HH + 40]
    report("Doors/openings: %d, smallest width %d cm (capsule diameter %d); narrow: %s; low: %s" % (
        len(doors), min(o["width"] for o in doors), 2 * R, narrow or "none", low or "none"))
    for o in low:
        warn("Opening %s only %d cm high" % o)
    for s in d["stairs"]:
        report("Stair %-12s %d steps, riser %.2f cm, run %d cm, width %d cm; foot at x=%d, head at x=%d" % (
            s["id"], s["steps"], s["_rise"], s["run"], s["hi"] - s["lo"], s["start"], s["start"] - s["steps"] * s["run"]))
    report("Lower hall: one open space %d x %d cm (x 800..5600, y 800..2000), no partition, crossover underside z=360; walkways 300 cm wide "
           "(south/north/west), crossover 300 cm wide (276 clear), cells 400 x 500 (west cells 450 x 500), lookout 500 x 1800, office 2400 x 500" % (4800, 1200))

    # ---- routes
    report("== Walk simulation (capsule r=%d hh=%d, max step %d) ==" % (study.CAP_R, study.CAP_HH, study.STEP))
    paths = {}
    for r in d["routes"]:
        ok, why, zend, path = an.simulate(r)
        paths[r["id"]] = path
        report("  route %-30s %s%s (end floor z=%.0f)" % (r["id"], "PASS" if ok else "FAIL ", "" if ok else " - " + why, zend))
        if not ok:
            err("Route %s failed: %s" % (r["id"], why))
    for r in d["blocked_routes"]:
        ok, why, zend, _ = an.simulate(r)
        report("  blocked %-28s %s (%s)" % (r["id"], "PASS (blocked)" if not ok else "FAIL (passable!)", why))
        if ok:
            err("Route %s should be blocked but is passable" % r["id"])
    f0 = an.floor_at(start[0], start[1], 0.0)
    sb = an.blocked_by(start[0], start[1], f0 if f0 is not None else 0.0)
    report("Player start (%d,%d) floor z=%s blocked=%s -> %s" % (start[0], start[1], f0, sb and sb["id"], "VALID" if f0 is not None and sb is None else "INVALID"))
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
    for x, y, zf, expect, label in d["reachability"]["samples"]:
        got = reachable(x, y, zf)
        report("  %-42s (%5d,%5d,z%3d) reachable=%-5s expected=%-5s %s" % (label, x, y, zf, got, expect, "ok" if got == expect else "MISMATCH"))
        if got != expect:
            err("Reachability mismatch: %s got %s expected %s" % (label, got, expect))
    report("Unprotected walkable edges with drop > 60 cm: %d cells" % len(expo))
    groups = {}
    for x, y, z, dd in expo:
        groups.setdefault((int(x // 200), int(y // 200), int(z // 50)), []).append((x, y, z, dd))
    for key, items in sorted(groups.items())[:15]:
        report("    exposed edge near (%d,%d) walking z=%d drop up to %d (%d cells)" % (
            sum(i[0] for i in items) / len(items), sum(i[1] for i in items) / len(items), items[0][2], max(i[3] for i in items), len(items)))
    if expo:
        err("%d unprotected edge cells (falls possible)" % len(expo))

    def cells(pred):
        return [(x, y, z) for (kx, ky, kz), (x, y, z) in seen.items() if pred(x, y, z)]

    def cover(eyes, pts, h):
        if not pts:
            return 0, 0
        n = sum(1 for (x, y, z) in pts if any(an.visible(e, (x, y, z + h)) for e in eyes))
        return n, len(pts)

    def pct(n_tot):
        return 100 * n_tot[0] // max(1, n_tot[1])

    hall = cells(lambda x, y, z: abs(z) < 2 and 800 < x < 5600 and 800 < y < 2000)
    seat_deck = cells(lambda x, y, z: abs(z) < 2 and 500 < x < 3000 and 0 < y < 800)
    seat_open = cells(lambda x, y, z: abs(z) < 2 and 800 < x < 3000 and 800 <= y < 1200)
    room_in = cells(lambda x, y, z: abs(z) < 2 and 3000 < x < 4334 and 0 < y < 800)
    ln_face_y, us_face_y, uw_face_x = 2285.0, 515.0, 515.0
    rows = study.rows

    def door_cs(rid):
        return [dc["c"] for dc in study.row_doors[rid]]

    # ---- sightlines from the start (lower hall, west end, facing the crossover)
    report("== Sightlines ==")
    eye = (start[0], start[1], 170.0)
    cam = (start[0] - 200.0, start[1], 230.0)

    def vis_any(t):
        return an.visible(eye, t) or an.visible(cam, t)
    report("From the lower hall start (1100,1400), facing east (camera ~200 cm behind):")
    for label, tgt in (("crossover west rail face", (3045.0, 1400.0, 445.0)), ("crossover deck underside", (3200.0, 1400.0, 355.0)),
                       ("lookout sign (east wall, below the deck line)", (5585.0, 1400.0, 330.0)), ("lookout window opening", (5585.0, 1400.0, 510.0)),
                       ("south stair, void-side rail face", (4600.0, 785.0, 260.0)), ("north stair, void-side rail face", (4600.0, 2015.0, 260.0)),
                       ("office doorway (z=520)", (4000.0, 515.0, 520.0)), ("enclosed room opening", (3600.0, 800.0, 150.0))):
        report("  start -> %-34s %s" % (label, "VISIBLE" if vis_any(tgt) else "hidden"))
    n_un = sum(vis_any((c, ln_face_y, 695.0)) for c in door_cs("UN"))
    n_us = sum(vis_any((c, us_face_y, 695.0)) for c in door_cs("US"))
    n_ln = sum(vis_any((c, ln_face_y, 130.0)) for c in door_cs("LN"))
    n_uw = sum(vis_any((uw_face_x, c, 520.0)) for c in door_cs("UW"))
    report("  upper north tier band %d/%d, upper south tier band %d/%d, lower north door faces %d/%d, upper west doors %d/%d (behind the viewer)" % (
        n_un, len(door_cs("UN")), n_us, len(door_cs("US")), n_ln, len(door_cs("LN")), n_uw, len(door_cs("UW"))))
    if n_un < 5 or n_us < 4:
        warn("Upper tiers are poorly visible from the start")
    if not vis_any((3045.0, 1400.0, 445.0)):
        err("Crossover not visible from the lower hall start")

    def from_eyes(label, eyes):
        report("%s" % label)
        report("  lower hall floor visible at head height: %d%%" % pct(cover(eyes, hall, 150.0)))
        a, b = cover(eyes, seat_deck, 150.0)
        c, dd = cover(eyes, seat_open, 150.0)
        e, f = cover(eyes, seat_deck + seat_open, 100.0)
        report("  seating area (standing, head height): under the south walkway %d%% (%d/%d), open row in the hall %d%% (%d/%d), both %d%%" % (
            100 * a // max(1, b), a, b, 100 * c // max(1, dd), c, dd, 100 * (a + c) // max(1, b + dd)))
        report("  seating area seen at seated height (floor+100): %d%%" % (100 * e // max(1, f)))
        report("  enclosed room interior %d%% (door sightline only)" % pct(cover(eyes, room_in, 150.0)))
        for rid, face_y, kind in (("LN", ln_face_y, "y"), ("UN", ln_face_y, "y"), ("US", us_face_y, "y"), ("UW", uw_face_x, "x")):
            zt = rows[rid]["z"] + 130.0
            if kind == "y":
                n = sum(1 for c_ in door_cs(rid) if any(an.visible(e, (c_, face_y, zt)) for e in eyes))
            else:
                n = sum(1 for c_ in door_cs(rid) if any(an.visible(e, (face_y, c_, zt)) for e in eyes))
            report("  cell doors %-2s (%s) visible: %d/%d" % (rid, {"LN": "lower north", "UN": "upper north", "US": "upper south", "UW": "upper west"}[rid], n, len(door_cs(rid))))

    lookout_eyes = [(5740.0, y, 390 + 165.0) for y in (900.0, 1150.0, 1400.0, 1650.0, 1900.0)]
    from_eyes("From the guard lookout (5 eye positions behind the console, x=5740, z=555):", lookout_eyes)
    cross_eyes = [(3200.0, y, 390 + 165.0) for y in (1000.0, 1400.0, 1800.0)]
    from_eyes("From the crossover looking down (3 eye positions, z=555):", cross_eyes)
    report("  crossover sees the lookout window face: %s" % any(an.visible(e, (5585.0, 1400.0, 510.0)) for e in cross_eyes))

    # ---- stairs: foot circulation
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
    for label, (px, py) in (("south stair foot lobby", (5300.0, 650.0)), ("north stair foot lobby", (5300.0, 2150.0))):
        rad = clear_radius(px, py, 0.0)
        mouth = sum(1 for xx in range(4960, 5585, 20) if reachable(xx, 810 if py < 1400 else 1990, 0))
        report("  %-24s free radius %.0f cm at (%d,%d); open mouth to the hall %d cm wide (x 4960..5585 at the hall edge)" % (label, rad, px, py, mouth * 20))
        if rad < 100:
            warn("%s is cramped (free radius %.0f cm)" % (label, rad))
        if mouth * 20 < 400:
            warn("%s mouth only %d cm" % (label, mouth * 20))

    # ---- camera clearance along the routes
    report("== Camera clearance along the test routes (approximation, arm %d cm, heights floor+160 / +230) ==" % d["params"]["camera_arm"])
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
    report("Route samples: %d; arm shortened directly behind the player at %d (%.0f%%); an orbit extreme (+/-45/90 deg) would be < 120 cm at %d" % (
        n_samples, n_back_short, 100.0 * n_back_short / max(1, n_samples), n_arc_short))
    for key, v in sorted(tight.items(), key=lambda kv: kv[1])[:10]:
        report("    tightest around (%d..%d, %d..%d, z~%d): %.0f cm of arm free" % (key[0], key[0] + 200, key[1], key[1] + 200, key[2], v))
    report("Errors: %d  Warnings: %d" % (len(errors), len(warnings)))
    return errors, warnings
