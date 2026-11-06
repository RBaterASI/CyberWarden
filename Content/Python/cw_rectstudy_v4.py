"""Analytic validation for the Floor 1 RECTANGLE STUDY V4 (V3 + extended guard office joined to the lookout, New Arrival intake beside the south stair foot).

Pure Python (no `unreal` import). The geometry generator is V2's StudyV2 (same JSON schema); V1/V2 modules are unchanged.
Input: Docs/Layout/S01_LW_F1_RectangleStudy_V4.json. Derived from cw_rectstudy_v3.py (unchanged). Units cm, +X east, +Y north, Z up.
"""
import math

import cw_rectstudy_v2 as v2
from cw_rectstudy_v2 import StudyV2, Analyzer, load  # noqa: F401  (re-exported)

HALLWAY_RECTS = [(0, 500, -1360, -1000), (500, 3300, -1360, -1000), (2940, 3300, -1900, -1360), (3300, 5600, -1900, -1540), (5240, 5600, -1540, 500)]
SERVICE_ROOMS = {
    "Kitchen": [(500, 2500, -1000, 0)], "Pantry": [(2500, 3300, -1000, 0)],
    "Laundry": [(500, 2300, -2300, -1360)], "Linen store": [(2300, 2940, -2300, -1360)],
    "Service hallway (A,V,B,E)": [(0, 3300, -1360, -1000), (2940, 3300, -1900, -1360), (3300, 5600, -1900, -1540), (5240, 5600, -1540, 500)],
}
COVER_PREFIXES = ("Cover_",)   # tall pieces (>= 190 cm) only; tables / island / prep benches (<= 95 cm) cannot hide a standing player


def _in(rects, x, y):
    return any(a <= x <= b and c <= y <= d for a, b, c, d in rects)


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
    report("Footprint: x %d..%d, y %d..%d = %.1f m x %.1f m, one continuous rectangle (same footprint as V3)" % (
        fp["x0"], fp["x1"], fp["y0"], fp["y1"], (fp["x1"] - fp["x0"]) / 100.0, (fp["y1"] - fp["y0"]) / 100.0))

    report("== Dimensions ==")
    doors = [o for o in study.openings if not o["id"].startswith(("Win_", "Kitchen_Hatch", "Opening_B"))]
    narrow = [(o["id"], o["width"]) for o in doors if o["width"] < 2 * R + 40]
    low = [(o["id"], o["height"]) for o in doors if o["height"] < 2 * study.CAP_HH + 40]
    report("Doors/openings: %d, smallest width %d cm (capsule diameter %d); narrow: %s; low: %s" % (
        len(doors), min(o["width"] for o in doors), 2 * R, narrow or "none", low or "none"))
    for o in low:
        warn("Opening %s only %d cm high" % o)
    report("Service hallway: 360 cm centre-to-centre (330 clear); legs: west x0..500 (500 wide, N-S), A y-1360..-1000 (x 0..3300, behind the kitchen), "
           "dog-leg V x 2940..3300 (y -1900..-1360), east run B y -1900..-1540 (x 3300..5600), east leg E x 5240..5600 (N-S to the stair lobby)")
    report("Kitchen 2000 x 1000 (hatch 1600 wide), pantry 800 x 1000, laundry 1800 x 940, linen store 640 x 940, recessed doors: kitchen back door and laundry door (240 wide x 120 deep niches); guard office now 3200 x 500 (was 2400), lookout 500 x 1800, intake 500 x 600")

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
        report("  blocked %-30s %s (%s)" % (r["id"], "PASS (blocked)" if not ok else "FAIL (passable!)", why))
        if ok:
            err("Route %s should be blocked but is passable" % r["id"])
    f0 = an.floor_at(start[0], start[1], 0.0)
    sb = an.blocked_by(start[0], start[1], f0 if f0 is not None else 0.0)
    report("Player start (%d,%d) on the lower tier: floor z=%s blocked=%s -> %s" % (start[0], start[1], f0, sb and sb["id"], "VALID" if f0 is not None and sb is None else "INVALID"))
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
    bad = 0
    for x, y, zf, expect, label in d["reachability"]["samples"]:
        got = reachable(x, y, zf)
        if got != expect:
            bad += 1
            report("  MISMATCH %-44s (%5d,%5d,z%3d) reachable=%s expected=%s" % (label, x, y, zf, got, expect))
            err("Reachability mismatch: %s got %s expected %s" % (label, got, expect))
    report("  %d reachability samples checked, %d mismatches (reachable: %d, must-be-closed: %d)" % (
        len(d["reachability"]["samples"]), bad, sum(1 for s in d["reachability"]["samples"] if s[3]), sum(1 for s in d["reachability"]["samples"] if not s[3])))
    report("Unprotected walkable edges with drop > 60 cm: %d cells" % len(expo))
    if expo:
        err("%d unprotected edge cells (falls possible)" % len(expo))

    def cells(pred):
        return [(x, y, z) for (kx, ky, kz), (x, y, z) in seen.items() if pred(x, y, z)]

    def cover(eyes, pts, h):
        if not pts:
            return 0, 0
        return sum(1 for (x, y, z) in pts if any(an.visible(e, (x, y, z + h)) for e in eyes)), len(pts)

    def pct(nt):
        return 100 * nt[0] // max(1, nt[1])

    # ------------------------------------------------------------------ main hall legibility
    report("== Main hall: legibility and the view up to the crossover ==")
    void_total = (5600 - 800) // 20 * ((2000 - 800) // 20)
    void_free = len(cells(lambda x, y, z: abs(z) < 2 and 800 < x < 5600 and 800 < y < 2000))
    report("Hall void x 800..5600, y 800..2000 (4800 x 1200, no partition): %d%% of its 20 cm cells are walkable (the rest are seating tables/benches in the south part)" % (100 * void_free // void_total))
    eye = (1100.0, 1400.0, 170.0)         # hall west viewpoint (the V3 start) - the player now starts in the intake
    cam = (900.0, 1400.0, 230.0)

    def vis_any(t):
        return an.visible(eye, t) or an.visible(cam, t)
    report("From the hall west viewpoint (1100,1400), facing east (camera ~200 cm behind; this was the V3 start):")
    for label, tgt in (("crossover west rail face", (3045.0, 1400.0, 445.0)), ("crossover deck underside", (3200.0, 1400.0, 355.0)),
                       ("far hall: Sector Floor 2 secured door sign", (5585.0, 1750.0, 330.0)), ("lookout window opening", (5585.0, 1800.0, 510.0)),
                       ("south stair, void-side rail face", (4600.0, 785.0, 260.0)), ("north stair, void-side rail face", (4600.0, 2015.0, 260.0)),
                       ("office doorway (z=520)", (4000.0, 515.0, 520.0)),
                       ("kitchen serving counter sign", (1500.0, 15.0, 320.0))):
        report("  start -> %-44s %s" % (label, "VISIBLE" if vis_any(tgt) else "hidden"))
    if not vis_any((3045.0, 1400.0, 445.0)):
        err("Crossover not visible from the hall west viewpoint")
    report("  east service door sign (lobby wall) from the hall east end (5000,1400): %s; west service door sign from the west aisle (700,1700): %s" % (
        an.visible((5000.0, 1400.0, 170.0), (5420.0, 515.0, 330.0)), an.visible((700.0, 1700.0, 170.0), (515.0, 1300.0, 330.0))))
    cds = [dc["c"] for dc in study.row_doors["UN"]]
    n_un = sum(vis_any((c, 2285.0, 695.0)) for c in cds)
    n_us = sum(vis_any((dc["c"], 515.0, 695.0)) for dc in study.row_doors["US"])
    report("  upper north tier band %d/%d, upper south tier band %d/%d (the tiers still read from the hall)" % (n_un, len(cds), n_us, len(study.row_doors["US"])))
    if n_un < 5 or n_us < 4:
        warn("Upper tiers poorly visible from the hall west viewpoint")

    # ------------------------------------------------------------------ seating coverage from lookout / crossover
    seat_deck = cells(lambda x, y, z: abs(z) < 2 and 500 < x < 3300 and 0 < y < 800)
    seat_open = cells(lambda x, y, z: abs(z) < 2 and 800 < x < 2900 and 800 <= y < 1250)
    lookout_eyes = [(5740.0, y, 390 + 165.0) for y in (900.0, 1150.0, 1400.0, 1650.0, 1900.0)]
    cross_eyes = [(3200.0, y, 390 + 165.0) for y in (1000.0, 1400.0, 1800.0)]
    for label, eyes in (("From the guard lookout (5 eyes, x=5740, z=555):", lookout_eyes), ("From the crossover looking down (3 eyes, z=555):", cross_eyes)):
        a, b = cover(eyes, seat_deck, 150.0)
        c, dd = cover(eyes, seat_open, 150.0)
        e, f = cover(eyes, seat_deck + seat_open, 100.0)
        report(label)
        report("  seating under the south walkway %d%% (%d/%d), seating row out in the hall %d%% (%d/%d), both %d%% standing / %d%% seated" % (
            100 * a // max(1, b), a, b, 100 * c // max(1, dd), c, dd, 100 * (a + c) // max(1, b + dd), 100 * e // max(1, f)))
    hall_cells = cells(lambda x, y, z: abs(z) < 2 and 800 < x < 5600 and 800 < y < 2000)
    report("  hall floor visible at head height: lookout %d%%, crossover %d%%" % (pct(cover(lookout_eyes, hall_cells, 150.0)), pct(cover(cross_eyes, hall_cells, 150.0))))
    report("  straight line seating -> hatch -> kitchen -> back door (x=2000) reaches the hallway's south wall but never the laundry: %s" % (
        not an.visible((2000.0, 125.0, 165.0), (2000.0, -1700.0, 150.0)) and an.visible((2000.0, 125.0, 165.0), (2000.0, -1340.0, 150.0))))
    report("  kitchen hatch lets a customer at the counter (1500,125) see into the kitchen: %s; the kitchen line (1500,-200) sees the seating beyond the counter: %s" % (
        an.visible((1500.0, 125.0, 165.0), (1500.0, -300.0, 150.0)), an.visible((1500.0, -200.0, 165.0), (1500.0, 400.0, 150.0))))

    # ------------------------------------------------------------------ service hallway sightlines
    report("== Service hallway: no straight see-through ==")
    mouth_w = (250.0, -1180.0, 165.0)       # inside the west leg where it turns into A
    mouth_e = (5420.0, -1720.0, 165.0)      # inside the east run where it turns into E
    door_w = (400.0, 1300.0, 165.0)         # just inside the west service door
    door_e = (5420.0, 400.0, 165.0)         # just inside the east service door
    report("  west service door <-> east service door in line of sight: %s (must be False)" % an.visible(door_w, door_e))
    report("  west mouth (250,-1180) -> east leg far end (5420,0): %s; -> east run (4500,-1720): %s; -> kitchen back-door niche: %s" % (
        an.visible(mouth_w, (5420.0, 0.0, 150.0)), an.visible(mouth_w, (4500.0, -1720.0, 150.0)), an.visible(mouth_w, (2000.0, -950.0, 150.0))))
    report("  east mouth (5420,-1720) -> west leg (250,-1180): %s; -> A midpoint (1500,-1180): %s; -> V corner (3120,-1700): %s" % (
        an.visible(mouth_e, (250.0, -1180.0, 150.0)), an.visible(mouth_e, (1500.0, -1180.0, 150.0)), an.visible(mouth_e, (3120.0, -1700.0, 150.0))))
    if an.visible(door_w, door_e) or an.visible(mouth_w, (4500.0, -1720.0, 150.0)) or an.visible(mouth_e, (1500.0, -1180.0, 150.0)):
        err("Service hallway can be seen straight through")
    hall_cells_svc = [(x, y, z) for (kx, ky, kz), (x, y, z) in seen.items() if abs(z) < 2 and _in(HALLWAY_RECTS, x, y) and not (x < 500 and y > -1000)]
    longest = (0.0, None)
    for (x, y, z) in hall_cells_svc[::7]:
        for ang in range(0, 360, 15):
            L = 0.0
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            while L < 4000.0 and _in(HALLWAY_RECTS, x + ca * (L + 20.0), y + sa * (L + 20.0)) and not an.solid_at(x + ca * (L + 20.0), y + sa * (L + 20.0), 165.0):
                L += 20.0
            if L > longest[0]:
                longest = (L, (x, y, ang))
    report("  longest uninterrupted sightline inside the hallway legs A/V/B/E at eye height: %.0f cm (from (%d,%d) heading %d deg); leg lengths A 3300, B 2300, E 2040; the dog-leg stops sight between A and B" % (
        longest[0], longest[1][0], longest[1][1], longest[1][2]))

    # ------------------------------------------------------------------ hiding / cover in the service area
    report("== Service area: hiding places and breaking sight (watcher = a guard walking the hallway, eye z=165; player standing, torso z+90 and head z+170) ==")
    watch = []
    for x in range(300, 3121, 200):
        watch.append((float(x), -1180.0, 165.0))
    for y in range(-1400, -1700, -150):
        watch.append((3120.0, float(y), 165.0))
    for x in range(3320, 5421, 200):
        watch.append((float(x), -1720.0, 165.0))
    for y in range(-1500, 460, 250):
        watch.append((5420.0, float(y), 165.0))
    watch += [(2000.0, -905.0, 165.0), (2400.0, -500.0, 165.0), (1400.0, -1500.0, 165.0), (2620.0, -1400.0, 165.0)]   # a guard just inside the kitchen, pantry door, laundry and linen store
    an_nocover = Analyzer(study, include=lambda b: not b["id"].startswith(COVER_PREFIXES))
    svc_cells = {}
    for name, rects in SERVICE_ROOMS.items():
        seenbin, pts = set(), []
        for (kx, ky, kz), (x, y, z) in seen.items():
            if abs(z) < 2 and _in(rects, x, y) and not (name.startswith("Service") and x < 500 and y > -1000):
                k = (int(x // 60), int(y // 60))
                if k not in seenbin:
                    seenbin.add(k)
                    pts.append((x, y, z))
        svc_cells[name] = pts

    def hidden_set(analyzer, pts, eyes):
        out = set()
        for (x, y, z) in pts:
            if not any(analyzer.visible(e, (x, y, z + 90.0)) or analyzer.visible(e, (x, y, z + 170.0)) for e in eyes):
                out.add((x, y))
        return out
    report("  watcher eye positions: %d (along the hallway legs + 4 just inside the kitchen, pantry door, laundry and linen store doors)" % len(watch))
    total_gain = 0
    for name, pts in svc_cells.items():
        h_c = hidden_set(an, pts, watch)
        h_n = hidden_set(an_nocover, pts, watch)
        gain = len(h_c) - len(h_n)
        total_gain += max(0, gain)
        report("  %-28s walkable 60 cm cells %3d: never seen from the hallway %3d (%d%%); without the cover pieces %3d; cover adds %+d" % (
            name, len(pts), len(h_c), 100 * len(h_c) // max(1, len(pts)), len(h_n), gain))
    covers = [b for b in d["boxes"] if b["id"].startswith(COVER_PREFIXES)]
    report("  cover pieces: %d tall solid pieces (linen/laundry carts 190, shelving 200, lockers 200, walk-in cooler 200)" % len(covers))
    allpts = [p for pts in svc_cells.values() for p in pts]
    by_piece = {}
    for b in covers:
        near = [p for p in allpts if b["x0"] - 150 <= p[0] <= b["x1"] + 150 and b["y0"] - 150 <= p[1] <= b["y1"] + 150]
        if not near:
            by_piece[b["id"]] = 0
            continue
        best = 0
        for e in watch:
            if math.hypot(e[0] - (b["x0"] + b["x1"]) / 2, e[1] - (b["y0"] + b["y1"]) / 2) > 1800:
                continue
            h_c = hidden_set(an, near, [e])
            h_n = hidden_set(an_nocover, near, [e])
            best = max(best, len(h_c) - len(h_n))
        by_piece[b["id"]] = best
    for k, v in sorted(by_piece.items()):
        report("    %-24s best single watcher position: +%d hiding cells within 150 cm" % (k, v))
    useful = sum(1 for v in by_piece.values() if v > 0)
    report("  %d of %d cover pieces create hiding cells from at least one hallway position" % (useful, len(covers)))
    if useful < max(3, len(covers) // 2):
        warn("Few cover pieces create hiding cells")
    # recessed doors / niches: standing in a niche is out of sight from the hallway line
    for label, cxn, cyn, ey in (("kitchen back-door niche", 2000.0, -940.0, -1180.0), ("laundry door niche", 1400.0, -1420.0, -1180.0)):
        seen_by = sum(1 for ex in range(300, 3121, 200) if an.visible((float(ex), ey, 165.0), (cxn, cyn, 90.0)) or an.visible((float(ex), ey, 165.0), (cxn, cyn, 170.0)))
        n_eye = len(range(300, 3121, 200))
        report("  standing in the %-24s is seen from %d of %d positions along hallway A (a guard has to be roughly in front of the niche)" % (label, seen_by, n_eye))

    # ------------------------------------------------------------------ turning clearance along the loop
    report("== Turning clearance along the service loop and rooms (free radius at floor+10..+170) ==")

    def clear_radius(x, y, fl):
        best = 1e9
        for g in an.geo:
            if g["z1"] <= fl + 10 or g["z0"] >= fl + 170:
                continue
            dx = max(g["x0"] - x, 0, x - g["x1"])
            dy = max(g["y0"] - y, 0, y - g["y1"])
            best = min(best, math.hypot(dx, dy))
        return best
    tight = []
    for rid in ("R05_Service_Loop", "R06_Service_Loop_Reverse", "R07_Kitchen_and_Pantry", "R08_Laundry", "R09_Linen_Store", "R10_Cover_Dash_East_Run"):
        last = None
        rmin = (1e9, None)
        for (x, y, z, nxt) in paths.get(rid, []):
            if last is not None and math.hypot(x - last[0], y - last[1]) < 40:
                continue
            last = (x, y)
            if y > 200:
                continue                      # only the service side
            r_ = clear_radius(x, y, z)
            if r_ < rmin[0]:
                rmin = (r_, (x, y))
        tight.append((rmin[0], rid, rmin[1]))
    for r_, rid, pos in sorted(tight):
        report("  %-26s tightest free radius %.0f cm at (%d,%d)" % (rid, r_, pos[0], pos[1]))
        if r_ < 65:
            warn("%s has a very tight spot (radius %.0f cm) at %s" % (rid, r_, pos))
    for label, (px, py) in (("hallway corner W/A", (250.0, -1180.0)), ("hallway corner A/V", (3120.0, -1180.0)), ("hallway corner V/B", (3120.0, -1720.0)),
                            ("hallway corner B/E", (5420.0, -1720.0)), ("kitchen niche (inside)", (2000.0, -940.0)), ("laundry niche (inside)", (1400.0, -1420.0)),
                            ("pantry aisle", (2880.0, -500.0)), ("linen store serpentine gap", (2835.0, -1700.0)), ("laundry lane to the door", (1400.0, -1560.0))):
        report("    %-30s free radius %.0f cm" % (label, clear_radius(px, py, 0.0)))

    # ------------------------------------------------------------------ Floor 2 route / stairs
    report("== Sector Floor 2 route and the stairs ==")
    ok_b, why_b, _, _ = an.simulate(next(r for r in d["blocked_routes"] if r["id"] == "B01_Floor2_secured_door"))
    report("  secured door: %s; the player can approach it (reachable at (5400,1750): %s); sign visible from the hall west viewpoint: %s" % (
        "blocks the route (%s)" % why_b if not ok_b else "NOT BLOCKED", reachable(5400, 1750, 0), vis_any((5585.0, 1750.0, 330.0))))
    report("  the only blocked route to another floor is that door; both prisoner stairs stay open (routes R20, R21, R23 pass: south stair up, walkway ring, north stair down)")

    # ------------------------------------------------------------------ V4: staff area + walkway continuity
    report("== Guard office + lookout as one connected staff area; the prisoner walkway stays continuous ==")
    office = next(r for r in study.rooms if r["id"] == "Guard_Office")
    look = next(r for r in study.rooms if r["id"] == "Guard_Lookout")
    report("  office x %d..%d, y %d..%d (%.0f m2); lookout x %d..%d, y %d..%d (%.0f m2); joined by an OPEN 400 cm passage (no door) at x=5850; one tint on both decks" % (
        office["x0"], office["x1"], office["y0"], office["y1"], (office["x1"] - office["x0"]) * (office["y1"] - office["y0"]) / 1e4,
        look["x0"], look["x1"], look["y0"], look["y1"], (look["x1"] - look["x0"]) * (look["y1"] - look["y0"]) / 1e4))
    report("  upper south cells remaining: %d (S1-S%d); the office replaced S7-S8" % (len(study.row_doors["US"]), len(study.row_doors["US"])))
    report("  walking from the west end of the office to the far end of the lookout: %s; a guard standing in the lookout at the passage (5850,900) sees down into the office floor (5850,200): %s; one in the office (5850,300) sees up the lookout (5850,1400): %s" % (
        "R25 passes" if "R25_Office_and_Lookout" in paths and len(paths["R25_Office_and_Lookout"]) > 0 else "R25 missing",
        an.visible((5850.0, 900.0, 555.0), (5850.0, 200.0, 400.0)), an.visible((5850.0, 300.0, 555.0), (5850.0, 1400.0, 555.0))))
    for rid in ("R26_Stair_Past_Office_to_Cells", "R27_Walkway_to_Crossover_from_Stair"):
        deck = [p for p in paths.get(rid, []) if p[2] > 380 and 2900 <= p[0] <= 4334 and p[1] < 800]
        ymin = min((p[1] for p in deck), default=None)
        report("  %-38s walkway in front of the office: %d samples, lowest y = %s (office wall face y=515; walkway y 500..800) -> %s" % (
            rid, len(deck), ymin, "continuous, never enters the office" if deck and ymin >= 540 else "PROBLEM"))
        if not deck or ymin < 540:
            err("%s does not keep to the prisoner walkway in front of the office" % rid)
    rad = clear_radius(4000.0, 650.0, 390.0)
    report("  free radius on the walkway in front of the office doorway (4000,650): %.0f cm; restricted boundary = threshold line + yellow hatching at the doorway (x 3860..4140), the doorway itself is open and not blocked" % rad)
    report("  guard at the office walkway window (3300,300) sees the walkway in front (3300,650): %s; the walkway (3300,650) sees the office interior (3300,300) through the window: %s" % (
        an.visible((3300.0, 300.0, 555.0), (3300.0, 650.0, 500.0)), an.visible((3300.0, 650.0, 555.0), (3300.0, 300.0, 520.0))))

    # ------------------------------------------------------------------ V4: intake
    report("== New Arrival intake: recessed off the hall beside the foot of the south (orange) stair ==")
    ss = (ps["x"], ps["y"])
    report("  intake x 5600..6100, y 900..1500 (500 x 600): sealed arrival door in the east wall (y 1200), small processing counter (70 x 270 x 105), waiting bench, 400 cm exit opening into the hall (x=5600, y 1000..1400)")
    report("  player start (%d,%d) yaw %d: facing the exit; floor z=%s" % (ss[0], ss[1], ps["yaw"], an.floor_at(ss[0], ss[1], 0.0)))
    exit_r = clear_radius(5600.0, 1200.0, 0.0)
    lane_r = min(clear_radius(x, 1200.0, 0.0) for x in range(5450, 5700, 50))
    report("  exit: free radius at the opening %.0f cm; along the exit lane (x 5450..5650) %.0f cm; free radius at the player start %.0f cm" % (exit_r, lane_r, clear_radius(float(ss[0]), float(ss[1]), 0.0)))
    if exit_r < 150:
        warn("Intake exit is narrow (free radius %.0f cm)" % exit_r)
    arms = min(an.free_length(ss[0], ss[1], 0.0 + h, 0.0, 200.0) for h in (160.0, 230.0))
    report("  camera arm behind the start (east wall): %.0f cm of the 200 cm arm free (the east wall is 185 cm behind the start, so the boom is almost fully out)" % arms)
    rects_intake = (5600, 6100, 900, 1500)
    lobby_cells = [(x, y) for (kx, ky, kz), (x, y, z) in seen.items() if abs(z) < 2 and 4950 <= x <= 5600 and 500 <= y <= 800]
    in_intake = [(x, y) for (kx, ky, kz), (x, y, z) in seen.items() if abs(z) < 2 and rects_intake[0] < x < rects_intake[1] and rects_intake[2] < y < rects_intake[3]]
    report("  stair foot lobby cells (x 4950..5600, y 500..800): %d; intake cells: %d; no walkable cell joins them directly: %s (the east wall and a 100 cm wall return at y 800..900 separate them)" % (
        len(lobby_cells), len(in_intake), not any(abs(a[0] - b[0]) <= 20 and abs(a[1] - b[1]) <= 20 for a in lobby_cells for b in in_intake)))
    stair_route_ok = "R14_Stair_Lobby_to_Hall" in paths and len(paths["R14_Stair_Lobby_to_Hall"]) > 0
    touches = [p for p in paths.get("R14_Stair_Lobby_to_Hall", []) if p[0] > 5560 and 900 < p[1] < 1500]
    report("  a prisoner leaving the south stair foot for the hall (R14) %s and never enters the intake (%d samples inside it)" % ("walks clear" if stair_route_ok else "FAILED", len(touches)))
    if touches:
        err("Stair-foot traffic route enters the intake")
    # views from the intake start
    ieye = (float(ss[0]), float(ss[1]), 170.0)
    icam = (float(ss[0]) + 120.0, float(ss[1]), 230.0)

    def ivis(t):
        return an.visible(ieye, t) or an.visible(icam, t)
    report("  from the intake start (looking west out of the exit):")
    for label, tgt in (("hall beyond the exit (5000,1200)", (5000.0, 1200.0, 150.0)), ("south stair, void-side rail face", (4600.0, 785.0, 260.0)),
                       ("south stair foot lobby floor", (5250.0, 650.0, 60.0)), ("north stair, void-side rail face", (4600.0, 2015.0, 260.0)),
                       ("crossover west rail face", (3045.0, 1400.0, 445.0)), ("kitchen serving-counter sign", (1500.0, 15.0, 320.0)),
                       ("guard lookout window (east wall, above/behind the exit wall)", (5585.0, 1400.0, 510.0)), ("guard lookout sign (z=640)", (5585.0, 1400.0, 640.0))):
        report("    intake start -> %-62s %s" % (label, "VISIBLE" if ivis(tgt) else "hidden"))
    if not ivis((4600.0, 785.0, 260.0)):
        err("South stair not visible from the intake start")
    th = (5560.0, 1200.0, 170.0)
    report("  from the exit threshold one step into the hall (5560,1200):")
    for label, tgt in (("south stair, void-side rail face", (4600.0, 785.0, 260.0)), ("guard lookout window", (5585.0, 1400.0, 510.0)), ("guard lookout sign (z=640)", (5585.0, 1400.0, 640.0)),
                       ("Sector Floor 2 secured door sign", (5585.0, 1750.0, 330.0)), ("crossover west rail face", (3045.0, 1400.0, 445.0))):
        report("    exit threshold -> %-40s %s" % (label, "VISIBLE" if an.visible(th, tgt) else "hidden"))
    hall_out = (5300.0, 1200.0, 170.0)
    report("  from the hall just outside (5300,1200), looking back east: lookout window %s, lookout sign %s, intake exit sign %s" % (
        an.visible(hall_out, (5585.0, 1400.0, 510.0)), an.visible(hall_out, (5585.0, 1400.0, 640.0)), an.visible(hall_out, (5585.0, 1200.0, 305.0))))
    report("  the lookout sits above and behind the exit wall, so it is NOT in line of sight from inside the intake; it is the wall you turn to face once you step out into the hall.")

    # ------------------------------------------------------------------ camera clearance
    report("== Camera clearance along the test routes (approximation, arm %d cm, heights floor+160 / +230) ==" % d["params"]["camera_arm"])
    arm = float(d["params"]["camera_arm"])
    tightc = {}
    n_samples = n_back_short = n_arc_short = 0
    for rid, path in paths.items():
        last = None
        for (x, y, z, nxt) in path:
            if last is not None and math.hypot(x - last[0], y - last[1]) < 50:
                continue
            last = (x, y)
            back = math.degrees(math.atan2(nxt[1] - y, nxt[0] - x)) + 180.0
            n_samples += 1
            wb = min(an.free_length(x, y, z + h, back, arm) for h in (160.0, 230.0))
            arc = min(an.free_length(x, y, z + h, back + off, arm) for h in (160.0, 230.0) for off in (-90, -45, 45, 90))
            if wb < arm - 0.1:
                n_back_short += 1
                key = (int(x // 200) * 200, int(y // 200) * 200, int(z // 100) * 100)
                tightc[key] = min(tightc.get(key, 1e9), wb)
            if arc < 120:
                n_arc_short += 1
    report("Route samples: %d; arm shortened directly behind the player at %d (%.0f%%); an orbit extreme (+/-45/90 deg) would be < 120 cm at %d" % (
        n_samples, n_back_short, 100.0 * n_back_short / max(1, n_samples), n_arc_short))
    for key, v in sorted(tightc.items(), key=lambda kv: kv[1])[:10]:
        report("    tightest around (%d..%d, %d..%d, z~%d): %.0f cm of arm free" % (key[0], key[0] + 200, key[1], key[1] + 200, key[2], v))
    report("Errors: %d  Warnings: %d" % (len(errors), len(warnings)))
    return errors, warnings
