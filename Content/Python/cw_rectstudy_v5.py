"""Analytic validation for the Floor 1 RECTANGLE STUDY V5 (V4 with the intake moved to the foot of the NORTH stair and a north arm that completes a U-shaped guard suite).

Pure Python (no `unreal` import). The geometry generator is V2's StudyV2 (same JSON schema); V1/V2 modules are unchanged.
Input: Docs/Layout/S01_LW_F1_RectangleStudy_V5.json. Derived from cw_rectstudy_v4.py (unchanged). Units cm, +X east, +Y north, Z up.
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
    report("Kitchen 2000 x 1000 (hatch 1600 wide), pantry 800 x 1000, laundry 1800 x 940, linen store 640 x 940, recessed doors: kitchen back door and laundry door (240 wide x 120 deep niches); guard suite = south arm 3200 x 500 + east span 500 x 1800 + north arm 3200 x 500 (a U open to the hall), intake 1100 x 500 under the north arm")

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

    # ------------------------------------------------------------------ V5: the U-shaped guard suite, verified from above
    report("== Guard suite: one connected U (verified from above) ==")
    S = {r["id"]: r for r in study.rooms}
    south, span, north = S["Guard_Office"], S["Guard_Lookout"], S["Guard_North_Arm"]
    intake_room = S["Intake"]

    def rect(r):
        return (r["x0"], r["y0"], r["x1"], r["y1"])

    def inside(a_, b_):
        return a_[0] >= b_[0] and a_[1] >= b_[1] and a_[2] <= b_[2] and a_[3] <= b_[3]
    report("  south arm (office)   x %4d..%4d  y %4d..%4d  (%d x %d)" % (south["x0"], south["x1"], south["y0"], south["y1"], south["x1"] - south["x0"], south["y1"] - south["y0"]))
    report("  east span (lookout)  x %4d..%4d  y %4d..%4d  (%d x %d)" % (span["x0"], span["x1"], span["y0"], span["y1"], span["x1"] - span["x0"], span["y1"] - span["y0"]))
    report("  north arm            x %4d..%4d  y %4d..%4d  (%d x %d)" % (north["x0"], north["x1"], north["y0"], north["y1"], north["x1"] - north["x0"], north["y1"] - north["y0"]))
    u_ok = (south["x0"] == north["x0"] and south["x1"] == north["x1"] and (south["y1"] - south["y0"]) == (north["y1"] - north["y0"])
            and span["x1"] == south["x1"] == north["x1"] and span["y0"] == south["y1"] and span["y1"] == north["y0"] and span["x0"] > south["x0"])
    report("  U geometry: arms the same length and depth, flush east ends, the span joins the south arm's north edge (y=%d) to the north arm's south edge (y=%d): %s" % (
        south["y1"], north["y0"], "YES" if u_ok else "NO"))
    if not u_ok:
        err("The guard suite is not a U")
    # top-down plan of the upper deck (z=390): one character per 100 x 100 cm
    decks = [sl for sl in d["slabs"] if sl["z0"] == 360 and sl.get("area")]
    code = {"Restricted": "S", "Lookout": "S", "Walkway": "w", "Crossing": "X", "UpperCells": "c"}

    def deck_char(x, y):
        for sl in decks:
            if sl["x0"] <= x < sl["x1"] and sl["y0"] <= y < sl["y1"]:
                return code.get(sl["area"], "?")
        if 800 <= x < 5600 and 800 <= y < 2000:
            return "."
        return " "
    report("  top-down plan of the upper tier, x 2800..6100 (100 cm per character), north at the top.  S = guard suite deck, w = prisoner walkway, X = crossover, c = cells, . = open to the hall below")
    report("          x=2800                                        x=6000")
    for yy in range(2750, 0, -100):
        row = "".join(deck_char(xx + 50, yy) for xx in range(2800, 6100, 100))
        report("  y=%4d  %s" % (yy, row))
    suite_cells = {(xx, yy) for xx in range(2800, 6100, 100) for yy in range(50, 2800, 100) if deck_char(xx + 50, yy) == "S"}
    xs = sorted({c[0] for c in suite_cells})
    open_between = [(xx, yy) for xx in range(2900, 5600, 100) for yy in range(550, 2250, 100) if deck_char(xx + 50, yy) == "S"]
    report("  suite deck cells: %d (%.0f m2); suite cells in the open side between the arms (x 2900..5600, y 550..2250): %d (must be 0, the open side faces the hall)" % (len(suite_cells), len(suite_cells) * 1.0, len(open_between)))
    if open_between:
        err("Suite deck found in the open side of the U")
    # the north arm sits directly above the relocated intake
    ir, nr = rect(intake_room), rect(north)
    report("  north arm directly above the intake: intake footprint x %d..%d, y %d..%d lies inside the north arm footprint: %s" % (ir[0], ir[2], ir[1], ir[3], inside(ir, nr)))
    if not inside(ir, nr):
        err("North arm is not above the intake")
    # walkable as one staff area
    pth = paths.get("R25_Office_and_Lookout", [])
    n_s = sum(1 for p in pth if p[2] > 380 and south["x0"] <= p[0] <= south["x1"] and south["y0"] <= p[1] <= south["y1"])
    n_l = sum(1 for p in pth if p[2] > 380 and span["x0"] <= p[0] <= span["x1"] and span["y0"] <= p[1] <= span["y1"])
    n_n = sum(1 for p in pth if p[2] > 380 and north["x0"] <= p[0] <= north["x1"] and north["y0"] <= p[1] <= north["y1"])
    report("  one walk (R25) covers the whole suite: samples in the south arm %d, the lookout span %d, the north arm %d (west end of the south arm -> lookout -> west end of the north arm and back)" % (n_s, n_l, n_n))
    if min(n_s, n_l, n_n) == 0:
        err("R25 does not walk all three sections of the suite")
    report("  internal links: open 400 cm passage south arm <-> lookout (y=500, x=5850); open 400 cm passage lookout <-> north arm (y=2300, x=5850); no doors between the sections")
    # restricted boundary: the only opening from the prisoner side into the suite
    doors_in = [o for o in study.openings if o["z0"] >= 390 and o["axis"] == "h" and o["coord"] in (500, 2300) and south["x0"] <= o["center"] <= south["x1"]
                and not o["id"].startswith("Win_") and not o["id"].startswith("Open_")]
    report("  openings from the prisoner walkways into the suite (z>=390, x 2900..6100): %s -> the restricted boundary is the office doorway at x=4000 only; the north arm has windows but no walkway door" % ", ".join(o["id"] for o in doors_in))
    if [o["id"] for o in doors_in] != ["Door_Office"]:
        err("Unexpected walkway openings into the suite")
    # prisoner circulation stays continuous, in front of both arms
    for rid, lo, hi, label in (("R26_Stair_Past_Office_to_Cells", 540.0, 800.0, "south walkway / south arm"), ("R17_North_Stair_Past_Arm_to_Cells", 2000.0, 2260.0, "north walkway / north arm")):
        deck = [p for p in paths.get(rid, []) if p[2] > 380 and 2900 <= p[0] <= 4334 and 0 < p[1] < 2800 and (p[1] > 500 if label.startswith("south") else p[1] < 2300)]
        ys = [p[1] for p in deck if (p[1] < 800 if label.startswith("south") else p[1] > 2000)]
        ok_ = bool(ys) and min(ys) >= lo and max(ys) <= hi
        report("  %-38s in front of the %-26s: %d samples at y %s..%s -> %s" % (rid, label, len(ys), min(ys) if ys else None, max(ys) if ys else None, "continuous, never enters the suite" if ok_ else "PROBLEM"))
        if not ok_:
            err("%s leaves the prisoner walkway" % rid)
    report("  free radius on the south walkway in front of the office doorway (4000,650): %.0f cm; on the north walkway in front of the north arm (4000,2150): %.0f cm" % (clear_radius(4000.0, 650.0, 390.0), clear_radius(4000.0, 2150.0, 390.0)))
    report("  windows: the office (south) and the north arm each have a 600 cm window onto their walkway; guard at the north arm window (3300,2500) sees the north walkway (3300,2150): %s" % an.visible((3300.0, 2500.0, 555.0), (3300.0, 2150.0, 500.0)))
    report("  guards: from the lookout (5850,1400) the north arm passage looks north (5850,2400): %s; the south arm passage looks south (5850,400): %s" % (
        an.visible((5850.0, 1400.0, 555.0), (5850.0, 2400.0, 555.0)), an.visible((5850.0, 1400.0, 555.0), (5850.0, 400.0, 555.0))))

    # ------------------------------------------------------------------ V5: intake at the foot of the NORTH stair
    report("== New Arrival intake: relocated to the foot of the NORTH stair (old east-wall opening closed) ==")
    ss = (ps["x"], ps["y"])
    report("  intake x 5000..6100, y 2300..2800 (1100 x 500), north of the north stair foot lobby (x 4950..5600, y 2000..2300): sealed arrival door in the east wall (y 2550), small processing counter (300 x 70 x 105), waiting bench, 400 cm exit opening onto the lobby (y=2300, x 5150..5550)")
    report("  player start (%d,%d) yaw %d (south): the exit opening is straight ahead; floor z=%s" % (ss[0], ss[1], ps["yaw"], an.floor_at(ss[0], ss[1], 0.0)))
    exit_r = clear_radius(5350.0, 2300.0, 0.0)
    lane_r = min(clear_radius(5350.0, y_, 0.0) for y_ in range(2200, 2600, 50))
    report("  exit: free radius at the opening %.0f cm; along the exit lane (y 2200..2600) %.0f cm; free radius at the player start %.0f cm" % (exit_r, lane_r, clear_radius(float(ss[0]), float(ss[1]), 0.0)))
    if exit_r < 150:
        warn("Intake exit is narrow (free radius %.0f cm)" % exit_r)
    arms = min(an.free_length(ss[0], ss[1], h, 90.0, 200.0) for h in (160.0, 230.0))
    report("  camera arm behind the start (north wall): %.0f cm of the 200 cm arm free" % arms)
    foot = (4950.0, 2150.0)
    report("  the north stair foot (4950,2150) is %.0f cm from the intake exit centre (5350,2300) and %.0f cm along the path from the start; the stair is immediately west of the lobby you step into" % (
        math.hypot(5350 - foot[0], 2300 - foot[1]), 320 + 150 + 400))
    # keep the landing and the hall path clear
    landing_r = clear_radius(5050.0, 2150.0, 0.0)
    mouth = sum(1 for xx in range(4960, 5585, 20) if reachable(xx, 1990, 0))
    report("  stair landing (5050,2150): free radius %.0f cm; the landing opens to the hall along y=2000 over %d cm (x 4960..5585); the intake exit lands on the landing's east half, the stair foot is on its west end" % (landing_r, mouth * 20))
    if mouth * 20 < 400:
        warn("North stair landing mouth narrow")
    r15 = paths.get("R15_North_Stair_Foot_to_Hall", [])
    r12 = paths.get("R12_Intake_Exit_to_Hall", [])
    dmin = min((math.hypot(a_[0] - b_[0], a_[1] - b_[1]) for a_ in r15[::10] for b_ in r12[::10] if b_[1] < 2300 and a_[1] > 1900), default=None)
    report("  a prisoner leaving the north stair foot (R15) never enters the intake (%d samples inside it) and stays %s cm from the intake-exit walk at the closest point" % (
        sum(1 for p in r15 if p[1] > 2300), "%.0f" % dmin if dmin is not None else "n/a"))
    if any(p[1] > 2300 for p in r15):
        err("Stair-foot traffic enters the intake")
    # the old opening is closed
    old_wall = an.blocked_by(5560.0, 1200.0, 0.0)
    report("  old east-wall intake closed: wall at (5560,1200): %s; (5850,1200) reachable: %s (must be False); B15 blocks the old exit line" % (old_wall["id"] if old_wall else None, reachable(5850, 1200, 0)))
    if old_wall is None or reachable(5850, 1200, 0):
        err("Old intake opening is not closed")
    # views
    ieye = (float(ss[0]), float(ss[1]), 170.0)
    icam = (float(ss[0]), float(ss[1]) + 120.0, 230.0)

    def ivis(t):
        return an.visible(ieye, t) or an.visible(icam, t)
    report("  from the intake start (looking south out of the exit):")
    for label, tgt in (("lobby floor beyond the exit (5350,2100)", (5350.0, 2100.0, 60.0)), ("hall beyond the lobby (5350,1700)", (5350.0, 1700.0, 100.0)),
                       ("north stair foot step (4960,2150)", (4960.0, 2150.0, 18.0)), ("north stair side rail (4700,2262)", (4700.0, 2262.0, 200.0)),
                       ("Sector Floor 2 secured-door sign (5585,1750)", (5585.0, 1750.0, 330.0)), ("crossover west rail face", (3045.0, 1400.0, 445.0))):
        report("    intake start -> %-52s %s" % (label, "VISIBLE" if ivis(tgt) else "hidden"))
    th = (5350.0, 2290.0, 170.0)
    report("  from the exit opening (5350,2290), one step out:")
    for label, tgt in (("north stair foot step (4960,2150)", (4960.0, 2150.0, 18.0)), ("north stair side rail (4700,2262)", (4700.0, 2262.0, 200.0)),
                       ("north stair rail, hall side (4600,2015)", (4600.0, 2015.0, 260.0)), ("hall beyond (5350,1700)", (5350.0, 1700.0, 100.0)),
                       ("guard lookout window (5585,1400)", (5585.0, 1400.0, 510.0))):
        v_ = an.visible(th, tgt)
        report("    exit opening -> %-46s %s" % (label, "VISIBLE" if v_ else "hidden"))
    if not an.visible(th, (4960.0, 2150.0, 18.0)):
        err("North stair foot not visible from the intake exit")
    hall_out = (5300.0, 1700.0, 170.0)
    report("  from the hall (5300,1700) the intake exit sign is visible: %s; the north stair foot step: %s; the guard lookout window: %s" % (
        an.visible(hall_out, (5350.0, 2285.0, 305.0)), an.visible(hall_out, (4960.0, 2150.0, 18.0)), an.visible(hall_out, (5585.0, 1400.0, 510.0))))
    r16 = next((r for r in d["routes"] if r["id"] == "R16_Intake_to_North_Stair_to_Walkway"), None)
    ok16, why16, z16, _ = an.simulate(r16)
    report("  walk out of the intake, along the stair foot and climb the north stair to the upper walkway (R16): %s, ends on z=%.0f at (2700,2150)" % ("PASS" if ok16 else "FAIL - " + why16, z16))

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
