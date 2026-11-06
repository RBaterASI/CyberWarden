"""Geometry + analytic validation for the Sector 01 / Left Wing / Floor 1 RECTANGLE STUDY.

Pure Python (no `unreal` import) so it runs standalone (Tools/ValidateRectangleStudy.py, using the engine's bundled
python.exe - no editor, no project DLL) and inside the editor (Tools/BuildRectangleStudy.py, which only spawns what
this module generates). Input: Docs/Layout/S01_LW_F1_RectangleStudy.json. Units cm, +X east, +Y north, Z up.

Nothing here touches the accepted M1 layout (S01_LW_F1.json / cw_layout.py).
"""
import json
import math

FACE = {"E": (1, 0, 0.0), "N": (0, 1, 90.0), "W": (-1, 0, 180.0), "S": (0, -1, -90.0)}


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _lum(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def subtract_openings(a, b, base, top, cuts):
    """Boxes (xa, xb, za, zb) covering [a,b] x [base,top] minus cuts (ox0, ox1, oz0, oz1). Same scheme as the M1 builder."""
    xs = sorted({a, b} | {c[0] for c in cuts} | {c[1] for c in cuts})
    slabs = []
    for xa, xb in zip(xs, xs[1:]):
        if xb - xa < 0.01:
            continue
        covered = sorted((c[2], c[3]) for c in cuts if c[0] <= xa + 0.01 and c[1] >= xb - 0.01)
        z = base
        for c0, c1 in covered:
            if c0 > z + 0.01:
                slabs.append([xa, xb, z, min(c0, top)])
            z = max(z, c1)
        if z < top - 0.01:
            slabs.append([xa, xb, z, top])
    merged = []
    for s in slabs:
        if merged and abs(merged[-1][1] - s[0]) < 0.01 and abs(merged[-1][2] - s[2]) < 0.01 and abs(merged[-1][3] - s[3]) < 0.01:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return merged


def _segments_minus(a, b, gaps):
    segs = [(a, b)]
    for g0, g1 in sorted(gaps):
        nxt = []
        for s0, s1 in segs:
            if g1 <= s0 or g0 >= s1:
                nxt.append((s0, s1))
                continue
            if g0 > s0:
                nxt.append((s0, g0))
            if g1 < s1:
                nxt.append((g1, s1))
        segs = nxt
    return [s for s in segs if s[1] - s[0] > 1.0]


class Study:
    """Expands the study JSON into boxes / texts / lines / lights / markers (all plain dicts)."""

    def __init__(self, data):
        self.data = data
        p = data["params"]
        self.T = float(p["wall_thickness"])
        self.SLAB = float(p["slab_thickness"])
        self.CAP_R = float(p["capsule_radius"])
        self.CAP_HH = float(p["capsule_half_height"])
        self.STEP = float(p["max_step_height"])
        self.areas = data["areas"]
        self.boxes = []      # axis-aligned boxes (collision flag, kind, material key)
        self.texts = []      # TextRender records
        self.lines = []      # oriented thin strips (visual only)
        self.lights = []
        self.markers = []
        self.rooms = [dict(r) for r in data["rooms"]]
        self.openings = []   # for reports / sign logic
        self.cell_doors = []
        self.warnings = []
        self.sign_count = 0
        self._build()

    # ------------------------------------------------------------------ primitives
    def box(self, id, x0, y0, z0, x1, y1, z1, kind, mat=None, collision=True, folder="Misc", tags=()):
        if x1 - x0 < 0.5 or y1 - y0 < 0.5 or z1 - z0 < 0.5:
            return None
        b = {"id": id, "x0": x0, "y0": y0, "z0": z0, "x1": x1, "y1": y1, "z1": z1, "kind": kind, "mat": mat,
             "collision": collision, "folder": folder, "tags": list(tags)}
        self.boxes.append(b)
        return b

    def line(self, id, p0, p1, w, h, mat, folder="Markings"):
        dx, dy, dz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        horiz = math.hypot(dx, dy)
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length < 0.5:
            return
        yaw = math.degrees(math.atan2(dy, dx)) if horiz > 1e-6 else 0.0
        pitch = math.degrees(math.atan2(dz, horiz))
        self.lines.append({"id": id, "cx": (p0[0] + p1[0]) / 2, "cy": (p0[1] + p1[1]) / 2, "cz": (p0[2] + p1[2]) / 2,
                           "len": length, "w": w, "h": h, "yaw": yaw, "pitch": pitch, "mat": mat, "folder": folder})

    # ------------------------------------------------------------------ build
    def _build(self):
        d = self.data
        T, SLAB = self.T, self.SLAB
        # tiers (cells) -> rooms
        ct = d["cell_tiers"]
        for i in range(ct["count"]):
            x0 = ct["x0"] + i * ct["width"]
            x1 = x0 + ct["width"]
            for tier, z, ceil, area, pre in (("L", ct["lower_z"], ct["lower_ceil"], "CellBlock", "Cell_L"),
                                             ("U", ct["upper_z"], ct["upper_ceil"], "UpperCells", "Cell_U")):
                self.rooms.append({"id": "%s%d" % (pre, i + 1), "name": "Cell %s%d" % (tier, i + 1), "area": area,
                                   "sign": "%s%d" % (tier, i + 1), "x0": x0, "y0": ct["y0"], "x1": x1, "y1": ct["y1"],
                                   "z": z, "ceil": ceil, "floor": tier == "L", "cell": True})
            cx = (x0 + x1) / 2.0
            self.cell_doors.append({"id": "Door_L%d" % (i + 1), "c": cx, "w": ct["door_w"], "z0": ct["lower_z"], "h": ct["door_h"], "label": "L%d" % (i + 1), "tier": "L"})
            self.cell_doors.append({"id": "Door_U%d" % (i + 1), "c": cx, "w": ct["door_w"], "z0": ct["upper_z"], "h": ct["door_h"], "label": "U%d" % (i + 1), "tier": "U"})
            # bunks (same placement rule as M1 north cells)
            for tier, z in (("L", ct["lower_z"]), ("U", ct["upper_z"])):
                self.box("Bunk_%s%d" % (tier, i + 1), x0 + 30, ct["y1"] - 110, z, x0 + 250, ct["y1"] - 20, z + 100, "prop",
                         "lit:CellBlock" if tier == "L" else "lit:UpperCells", True, "Props")
        for k in range(ct["count"] + 1):
            x = ct["x0"] + k * ct["width"]
            self.box("CellWall_%d" % k, x - T / 2, ct["y0"], 0, x + T / 2, ct["y1"], ct["upper_z"] + ct["upper_ceil"], "wall", None, True, "Walls")

        # ground floors
        for r in self.rooms:
            if r.get("floor"):
                self.box("Floor_" + r["id"], r["x0"], r["y0"], r["z"] - SLAB, r["x1"], r["y1"], r["z"], "floor", "lit:" + r["area"], True, "Floors")
        # slabs
        for s in d["slabs"]:
            mat = ("lit:" + s["area"]) if s.get("area") else None
            self.box("Slab_" + s["id"], s["x0"], s["y0"], s["z0"], s["x1"], s["y1"], s["z1"], "slab", mat, True, "Slabs")
        # walls
        for w in d["walls"]:
            self._wall(w)
        # balustrades
        for r in d["rails"]:
            self._balustrade(r)
        # stairs
        for s in d["stairs"]:
            self._stair(s)
        # columns
        c = d["columns"]
        x = c["x_from"]
        while x <= c["x_to"]:
            if not (c["skip_between"][0] <= x <= c["skip_between"][1]):
                h = c["size"] / 2.0
                self.box("Col_%d" % x, x - h, c["y"] - h, 0, x + h, c["y"] + h, c["z1"], "prop", None, True, "Props")
            x += c["step"]
        # cafeteria tables + benches (common seating)
        for ri, ry in enumerate((-380, -720, -1060)):
            for ci, cx in enumerate((2450, 2900)):
                self.box("Caf_Table_%d_%d" % (ri + 1, ci + 1), cx - 130, ry - 50, 0, cx + 130, ry + 50, 75, "prop", "lit:Cafeteria", True, "Props")
                for side in (-1, 1):
                    self.box("Caf_Bench_%d_%d_%d" % (ri + 1, ci + 1, side), cx - 130, ry + side * 85 - 18, 0, cx + 130, ry + side * 85 + 18, 50, "prop", "lit:Cafeteria", True, "Props")
        # data boxes / props / markings
        for b in d["boxes"]:
            mat = b.get("mat")
            kind = "marking" if not b.get("collision", True) else "prop"
            self.box(b["id"], b["x0"], b["y0"], b["z0"], b["x1"], b["y1"], b["z1"], kind, mat, b.get("collision", True),
                     "Markings" if kind == "marking" else "Props", ["Id:" + b["id"]])
        # gate / sealed / sign / line / marker / light
        for ln in d["lines"]:
            self._line_spec(ln)
        self._guard_route()
        for s in d["signs"]:
            self._sign(s)
        for door in self.cell_doors:
            ct_y = ct["y0"]
            self._sign({"text": door["label"], "x": door["c"], "y": ct_y - T / 2, "z": door["z0"] + door["h"] + 24, "f": "S",
                        "size": 14, "area": "CellBlock" if door["tier"] == "L" else "UpperCells", "_name": "Door_" + door["label"]})
        for m in d["markers"]:
            self.markers.append(dict(m))
        self._lights()

    # ------------------------------------------------------------------ walls
    def _wall(self, w):
        T = self.T
        cuts_in = list(w.get("cuts", []))
        if w.get("cuts_from") == "cell_doors":
            for door in self.cell_doors:
                cuts_in.append({"id": door["id"], "name": "Cell door " + door["label"], "c": door["c"], "w": door["w"], "z0": door["z0"], "h": door["h"]})
        axis, coord = w["axis"], float(w["coord"])
        a, b, base, top = float(w["a"]), float(w["b"]), float(w["z0"]), float(w["z1"])
        cuts = []
        for o in cuts_in:
            ox0, ox1 = o["c"] - o["w"] / 2.0, o["c"] + o["w"] / 2.0
            oz0, oz1 = o["z0"], o["z0"] + o["h"]
            ox0c, ox1c, oz0c, oz1c = max(a, ox0), min(b, ox1), max(base, oz0), min(top, oz1)
            if ox1c > ox0c and oz1c > oz0c:
                cuts.append((ox0c, ox1c, oz0c, oz1c))
            self.openings.append({"id": o["id"], "axis": axis, "coord": coord, "center": o["c"], "width": o["w"], "z0": o["z0"], "height": o["h"], "kind": o.get("kind")})
            if o.get("kind") == "sealed":
                w2 = o["w"] / 2.0
                if axis == "h":
                    self.box("SECURED_" + o["id"], o["c"] - w2, coord - 8, o["z0"], o["c"] + w2, coord + 8, o["z0"] + o["h"], "secured", "lit:Secured", True, "Secured")
                else:
                    self.box("SECURED_" + o["id"], coord - 8, o["c"] - w2, o["z0"], coord + 8, o["c"] + w2, o["z0"] + o["h"], "secured", "lit:Secured", True, "Secured")
            elif o.get("kind") == "gate":
                self._gate(o, axis, coord)
        ext = T / 2.0 if axis == "h" else 0.0
        for xa, xb, za, zb in subtract_openings(a, b, base, top, cuts):
            xa2 = xa - (ext if abs(xa - a) < 0.01 else 0.0)
            xb2 = xb + (ext if abs(xb - b) < 0.01 else 0.0)
            if axis == "h":
                self.box("%s_%d" % (w["id"], xa), xa2, coord - T / 2, za, xb2, coord + T / 2, zb, "wall", None, True, "Walls")
            else:
                self.box("%s_%d" % (w["id"], xa), coord - T / 2, xa2, za, coord + T / 2, xb2, zb, "wall", None, True, "Walls")

    def _gate(self, o, axis, coord):
        """Secured gate: vertical bars (30 cm gaps < capsule diameter) + two cross beams. See-through so the stair is visible."""
        lo, hi = o["c"] - o["w"] / 2.0, o["c"] + o["w"] / 2.0
        z0, z1 = o["z0"], o["z0"] + o["h"]
        bar, pitch = 12.0, 42.0
        pos = lo + 6.0
        n = 0
        while pos <= hi - 6.0 + 0.01:
            if axis == "v":
                self.box("GateBar_%d" % n, coord - 6, pos - bar / 2, z0, coord + 6, pos + bar / 2, z1, "secured", "lit:Secured", True, "Secured")
            else:
                self.box("GateBar_%d" % n, pos - bar / 2, coord - 6, z0, pos + bar / 2, coord + 6, z1, "secured", "lit:Secured", True, "Secured")
            n += 1
            pos += pitch
        for k, (bz0, bz1) in enumerate(((z1 - 14, z1), (z0 + 140, z0 + 154), (z0, z0 + 14))):
            if axis == "v":
                self.box("GateBeam_%d" % k, coord - 7, lo, bz0, coord + 7, hi, bz1, "secured", "lit:Secured", True, "Secured")
            else:
                self.box("GateBeam_%d" % k, lo, coord - 7, bz0, hi, coord + 7, bz1, "secured", "lit:Secured", True, "Secured")

    # ------------------------------------------------------------------ rails / stairs
    def _balustrade(self, r):
        """Open balustrade: 50 cm kick plate + 10 cm top bar at 100-110 + posts every 200 (see-through, but every
        capsule-sized gap is closed). All collide."""
        kick, top_h = float(self.data["params"]["kick_height"]), float(self.data["params"]["rail_height"])
        t = 12.0
        axis, coord, z = r["axis"], float(r["coord"]), float(r["z"])
        for si, (s0, s1) in enumerate(_segments_minus(float(r["a"]), float(r["b"]), r.get("gaps", []))):
            def put(name, p0, p1, h0, h1):
                if axis == "h":
                    self.box("%s_%s_%d" % (r["id"], name, si), p0, coord - t / 2, z + h0, p1, coord + t / 2, z + h1, "rail", None, True, "Rails")
                else:
                    self.box("%s_%s_%d" % (r["id"], name, si), coord - t / 2, p0, z + h0, coord + t / 2, p1, z + h1, "rail", None, True, "Rails")
            put("Kick", s0, s1, 0, kick)
            put("Bar", s0, s1, top_h - 10, top_h)
            n = max(1, int(round((s1 - s0) / 200.0)))
            for k in range(n + 1):
                p = s0 + (s1 - s0) * k / n
                put("Post%d" % k, max(s0, p - t / 2), min(s1, p + t / 2), kick, top_h - 10)

    def _stair(self, s):
        rise = s["total_rise"] / float(s["steps"])
        run = s["run"]
        sign = 1 if s["axis"][0] == "+" else -1
        along_x = s["axis"][1] == "x"
        base = s["z_start"] if s["z_start"] > 0 else 0
        area = s.get("area")
        for k in range(1, s["steps"] + 1):
            top = s["z_start"] + rise * k
            a0 = s["start"] + sign * run * (k - 1)
            a1 = s["start"] + sign * run * k
            lo_a, hi_a = min(a0, a1), max(a0, a1)
            if along_x:
                box = (lo_a, s["lo"], hi_a, s["hi"])
            else:
                box = (s["lo"], lo_a, s["hi"], hi_a)
            self.box("%s_Step%02d" % (s["id"], k), box[0], box[1], base, box[2], box[3], top, "stair", "lit:" + area if area else None, True, "Stairs", ["Stair:" + s["id"]])
            for side in s.get("rails", []):
                if along_x:
                    y0, y1 = (s["lo"] - 10, s["lo"]) if side == "lo" else (s["hi"], s["hi"] + 10)
                    self.box("%s_Rail%02d_%s" % (s["id"], k, side), box[0], y0, top, box[2], y1, top + 100, "rail", None, True, "Rails")
                else:
                    x0, x1 = (s["lo"] - 10, s["lo"]) if side == "lo" else (s["hi"], s["hi"] + 10)
                    self.box("%s_Rail%02d_%s" % (s["id"], k, side), x0, box[1], top, x1, box[3], top + 100, "rail", None, True, "Rails")
        s["_rise"] = rise

    # ------------------------------------------------------------------ lines / route
    def _line_spec(self, ln):
        mat = ln["mat"]
        if "p0" in ln and "dashes" not in ln:
            self.line(ln["id"], ln["p0"], ln["p1"], ln["thick"], ln["thick"], mat)
        elif "dashes" in ln:
            ds = ln["dashes"]
            self._dashed(ln["id"], ds["p0"], ds["p1"], ds["len"], ds["gap"], ds["thick"], 2.0, mat)
        elif "hangers" in ln:
            h = ln["hangers"]
            x = h["x_from"]
            while x <= h["x_to"] + 0.1:
                self.box("%s_%d" % (ln["id"], x), x - h["thick"] / 2, h["y"] - h["thick"] / 2, h["z0"], x + h["thick"] / 2, h["y"] + h["thick"] / 2, h["z1"], "marking", mat, False, "Markings")
                x += h["step"]
        elif "frustum" in ln:
            f = ln["frustum"]
            self.frustum = dict(f)
            px, py, pz = f["pos"]
            yaw, pitch = math.radians(f["yaw"]), math.radians(f["pitch"])
            corners = []
            for sh in (-1, 1):
                for sv in (-1, 1):
                    ya = yaw + sh * math.radians(f["hfov"] / 2.0)
                    pa = pitch + sv * math.radians(f["vfov"] / 2.0)
                    d = (math.cos(pa) * math.cos(ya), math.cos(pa) * math.sin(ya), math.sin(pa))
                    corners.append((px + d[0] * f["range"], py + d[1] * f["range"], pz + d[2] * f["range"]))
            for i, c in enumerate(corners):
                self.line("%s_Edge%d" % (ln["id"], i), (px, py, pz), c, f["thick"], f["thick"], mat)
            order = [0, 1, 3, 2, 0]   # (-,-),(-,+),(+,+),(+,-)
            for a, b in zip(order, order[1:]):
                self.line("%s_Far%d" % (ln["id"], a), corners[a], corners[b], f["thick"], f["thick"], mat)

    def _dashed(self, id, p0, p1, length, gap, w, h, mat):
        dx, dy, dz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        total = math.sqrt(dx * dx + dy * dy + dz * dz)
        if total < 1:
            return
        ux, uy, uz = dx / total, dy / total, dz / total
        pos, n = 0.0, 0
        while pos < total - 1:
            e = min(pos + length, total)
            self.line("%s_%d" % (id, n), (p0[0] + ux * pos, p0[1] + uy * pos, p0[2] + uz * pos),
                      (p0[0] + ux * e, p0[1] + uy * e, p0[2] + uz * e), w, h, mat)
            pos += length + gap
            n += 1

    def _guard_route(self):
        pts = self.data["guard_route"]["points"]
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            self._dashed("GuardRoute_%d" % i, (a[0], a[1], a[2] + 3), (b[0], b[1], b[2] + 3), 70, 50, 22, 3, "unlit:Route")
        for i, p in enumerate(pts):
            self.markers.append({"id": "Guard_Route_%02d" % i, "type": "GuardRoute", "x": p[0], "y": p[1], "z": p[2]})

    # ------------------------------------------------------------------ signs
    def _sign(self, s):
        area = s["area"]
        col = self.areas[area]["color"]
        dark_text = _lum(col) > 150
        size = float(s["size"])
        text = s["text"]
        width = max(80.0, len(text) * size * 0.62 + 24.0)
        height = max(26.0, size * 1.5)
        x, y, z = float(s["x"]), float(s["y"]), float(s["z"])
        name = s.get("_name") or ("Sign%02d_%s" % (self.sign_count, "".join(ch for ch in text if ch.isalnum())[:18]))
        self.sign_count += 1
        mat = "unlit:" + area
        if "hang" in s:
            plate = s["hang"]
            if plate == "x":   # plate normal along X: faces E and W
                self.box("Plate_" + name, x - 3, y - width / 2, z - height / 2, x + 3, y + width / 2, z + height / 2, "sign", mat, False, "Signs")
                faces = (("E", x + 4, y), ("W", x - 4, y))
            else:              # plate normal along Y: faces N and S
                self.box("Plate_" + name, x - width / 2, y - 3, z - height / 2, x + width / 2, y + 3, z + height / 2, "sign", mat, False, "Signs")
                faces = (("N", x, y + 4), ("S", x, y - 4))
            for facing, tx, ty in faces:
                self._text(text, tx, ty, z, facing, size, dark_text, area, name)
            top = z + height / 2
            if top < 745:
                self.box("Tether_" + name, x - 2, y - 2, top, x + 2, y + 2, 760, "sign", None, False, "Signs")
            return
        facing = s["f"]
        dx, dy, yaw = FACE[facing]
        if dx != 0:
            x0, x1 = (x, x + 4) if dx > 0 else (x - 4, x)
            y0, y1 = y - width / 2, y + width / 2
        else:
            y0, y1 = (y, y + 4) if dy > 0 else (y - 4, y)
            x0, x1 = x - width / 2, x + width / 2
        self.box("Plate_" + name, x0, y0, z - height / 2, x1, y1, z + height / 2, "sign", mat, False, "Signs")
        self._text(text, x + dx * 5.0, y + dy * 5.0, z, facing, size, dark_text, area, name)

    def _text(self, text, x, y, z, facing, size, dark, area, name):
        dx, dy, yaw = FACE[facing]
        self.texts.append({"id": "Text_%s_%s" % (name, facing), "text": text, "x": x, "y": y, "z": z, "yaw": yaw, "size": size,
                           "color": [15, 15, 15] if dark else [255, 255, 255], "area": area})

    # ------------------------------------------------------------------ lights
    def _lights(self):
        n = 0
        for r in self.rooms:
            if r.get("cell"):
                nx = ny = 1
                inten, rad = 1200.0, 450.0
            else:
                w, d = r["x1"] - r["x0"], r["y1"] - r["y0"]
                big = r["ceil"] >= 700
                spacing = 800.0 if big else 650.0
                nx, ny = max(1, int(round(w / spacing))), max(1, int(round(d / spacing)))
                inten = 14000.0 if big else 4500.0
                rad = max(w / nx, d / ny, 600.0) * (1.1 if big else 0.95)
            zt = r["z"] + min(r["ceil"], 700) - 60
            col = self.areas[r["area"]]["color"]
            col = [int((c + 255) / 2) for c in col]
            for ix in range(nx):
                for iy in range(ny):
                    self.lights.append({"id": "Light_%s_%d" % (r["id"], n), "x": r["x0"] + (r["x1"] - r["x0"]) * (ix + 0.5) / nx,
                                        "y": r["y0"] + (r["y1"] - r["y0"]) * (iy + 0.5) / ny, "z": zt, "intensity": inten, "radius": rad, "color": col})
                    n += 1

    # ------------------------------------------------------------------ queries
    def collision_boxes(self):
        return [b for b in self.boxes if b["collision"]]


# ==========================================================================================
# Analysis (capsule walk, reachability, edges, sightlines, camera clearance)
# ==========================================================================================
class Analyzer:
    BUCKET = 100.0

    def __init__(self, study, include=None):
        self.s = study
        self.R, self.HH, self.STEP = study.CAP_R, study.CAP_HH, study.STEP
        geo = [b for b in study.collision_boxes() if include is None or include(b)]
        self.geo = geo
        self.grid = {}
        B = self.BUCKET
        for g in geo:
            for ix in range(int((g["x0"] - 40) // B), int((g["x1"] + 40) // B) + 1):
                for iy in range(int((g["y0"] - 40) // B), int((g["y1"] + 40) // B) + 1):
                    self.grid.setdefault((ix, iy), []).append(g)

    def near(self, x, y):
        return self.grid.get((int(x // self.BUCKET), int(y // self.BUCKET)), ())

    def floor_at(self, px, py, ref):
        best = None
        R2 = self.R * self.R
        for g in self.near(px, py):
            if g["z1"] > ref + self.STEP + 0.01:
                continue
            dx = max(g["x0"] - px, 0, px - g["x1"])
            dy = max(g["y0"] - py, 0, py - g["y1"])
            if dx * dx + dy * dy < R2 and (best is None or g["z1"] > best):
                best = g["z1"]
        return best

    def blocked_by(self, px, py, fl):
        zt = fl + 2 * self.HH
        r2 = (self.R - 0.5) ** 2
        for g in self.near(px, py):
            if g["z1"] <= fl + 0.5 or g["z0"] >= zt - 0.5:
                continue
            dx = max(g["x0"] - px, 0, px - g["x1"])
            dy = max(g["y0"] - py, 0, py - g["y1"])
            if dx * dx + dy * dy < r2:
                return g
        return None

    def simulate(self, route):
        z = float(route["z"])
        first = route["points"][0]
        f = self.floor_at(first[0], first[1], z)
        if f is None:
            return False, "no floor at start %s" % (first,), z, []
        z = f
        path = []
        for p0, p1 in zip(route["points"], route["points"][1:]):
            dist = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            n = max(1, int(dist / 8))
            for k in range(n + 1):
                t = k / float(n)
                x, y = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
                f = self.floor_at(x, y, z)
                if f is None:
                    return False, "floor lost at (%d,%d) z=%.0f" % (x, y, z), z, path
                if f < z - self.STEP:
                    return False, "drop of %.0f cm at (%d,%d)" % (z - f, x, y), z, path
                z = f
                hit = self.blocked_by(x, y, z)
                if hit:
                    return False, "blocked by %s at (%d,%d) z=%.0f" % (hit["id"], x, y, z), z, path
                path.append((x, y, z, p1))
        return True, "ok", z, path

    def flood(self, start, cell=20.0):
        sx, sy = start
        z0 = self.floor_at(sx, sy, 0.0) or 0.0
        seen = {(int(sx // cell), int(sy // cell), int(round(z0))): (sx, sy, z0)}
        stack = [(sx, sy, z0)]
        exposures = []
        while stack:
            x, y, z = stack.pop()
            for dx, dy in ((cell, 0), (-cell, 0), (0, cell), (0, -cell)):
                nx, ny = x + dx, y + dy
                f = self.floor_at(nx, ny, z)
                if f is None:
                    continue
                if f < z - self.STEP:
                    if not self.blocked_by(nx, ny, z) and z - f > 60:
                        exposures.append((nx, ny, z, z - f))
                    continue
                if self.blocked_by(nx, ny, f):
                    continue
                key = (int(nx // cell), int(ny // cell), int(round(f)))
                if key not in seen:
                    seen[key] = (nx, ny, f)
                    stack.append((nx, ny, f))
        return seen, exposures

    # -------------------------------------------------------------- sightlines
    @staticmethod
    def _seg_hits(p, q, g):
        t0, t1 = 0.0, 1.0
        for a, b, lo, hi in ((p[0], q[0], g["x0"], g["x1"]), (p[1], q[1], g["y0"], g["y1"]), (p[2], q[2], g["z0"], g["z1"])):
            d = b - a
            if abs(d) < 1e-9:
                if a < lo or a > hi:
                    return False
            else:
                ta, tb = (lo - a) / d, (hi - a) / d
                if ta > tb:
                    ta, tb = tb, ta
                t0, t1 = max(t0, ta), min(t1, tb)
                if t0 > t1:
                    return False
        return t1 > 0.002 and t0 < 0.998

    def visible(self, eye, tgt, skip_kinds=()):
        minx, maxx = min(eye[0], tgt[0]), max(eye[0], tgt[0])
        miny, maxy = min(eye[1], tgt[1]), max(eye[1], tgt[1])
        minz, maxz = min(eye[2], tgt[2]), max(eye[2], tgt[2])
        for g in self.geo:
            if g["x1"] < minx or g["x0"] > maxx or g["y1"] < miny or g["y0"] > maxy or g["z1"] < minz or g["z0"] > maxz:
                continue
            if g["kind"] in skip_kinds:
                continue
            if self._seg_hits(eye, tgt, g):
                return False
        return True

    # -------------------------------------------------------------- camera clearance
    def solid_at(self, x, y, z):
        for g in self.near(x, y):
            if g["x0"] <= x <= g["x1"] and g["y0"] <= y <= g["y1"] and g["z0"] <= z <= g["z1"]:
                return True
        return False

    def free_length(self, x, y, z, ang_deg, limit=200.0, step=10.0):
        a = math.radians(ang_deg)
        dx, dy = math.cos(a), math.sin(a)
        d = step
        while d <= limit:
            if self.solid_at(x + dx * d, y + dy * d, z):
                return d - step
            d += step
        return limit


def run_analysis(study, report):
    """Runs every check and appends human-readable lines to `report` (callable). Returns (errors, warnings)."""
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

    report("== Geometry summary ==")
    kinds = {}
    for b in study.boxes:
        kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    report("Boxes: %d total (%s); collision boxes %d; text signs %d; lines %d; lights %d; markers %d" % (
        len(study.boxes), ", ".join("%s=%d" % kv for kv in sorted(kinds.items())), len(an.geo), len(study.texts), len(study.lines), len(study.lights), len(study.markers)))
    fp = d["meta"]["footprint"]
    report("Exterior footprint: x %d..%d, y %d..%d = %.1f m x %.1f m (continuous exterior walls on all four sides: %s)" % (
        fp["x0"], fp["x1"], fp["y0"], fp["y1"], (fp["x1"] - fp["x0"]) / 100.0, (fp["y1"] - fp["y0"]) / 100.0,
        all(any(w["id"] == n for w in d["walls"]) for n in ("W_South", "W_North", "W_West", "W_East"))))

    # ---- dimensions
    report("== Dimensions ==")
    narrow = []
    for o in study.openings:
        if o["kind"] != "gate" and o["width"] < 2 * R + 40:
            narrow.append((o["id"], o["width"]))
        if o["height"] < 2 * study.CAP_HH + 40 and not o["id"].startswith("Win_"):
            warn("Opening %s only %d cm high" % (o["id"], o["height"]))
    openings_ok = [o for o in study.openings if not o["id"].startswith("Win_") and o["kind"] != "gate"]
    report("Doors/arches: %d, smallest width %d cm (capsule diameter %d); narrow (<%d): %s" % (
        len(openings_ok), min(o["width"] for o in openings_ok), 2 * R, 2 * R + 40, narrow or "none"))
    for s in d["stairs"]:
        report("Stair %-15s %d steps, riser %.2f cm, run %d cm, width %d cm (max step %d)" % (s["id"], s["steps"], s["_rise"], s["run"], s["hi"] - s["lo"], study.STEP))
        if s["_rise"] > 20:
            warn("Stair %s riser %.1f cm is steep" % (s["id"], s["_rise"]))
    report("Hall clear width 900 cm (y 0..900), hall length 5600 cm; lower aisle / upper walkway 280 cm deep x 360 cm high (open to the hall); "
           "gallery 600 cm deep; lookout cabin 500 x 260 cm projecting over the hall; crossing 300 cm wide (276 clear between rails); "
           "landing 600 x 900 cm; atrium roof underside z=760; upper deck z=390")

    # ---- routes
    report("== Walk simulation (capsule r=%d hh=%d, max step %d) ==" % (study.CAP_R, study.CAP_HH, study.STEP))
    fails = 0
    paths = {}
    for r in d["routes"]:
        ok, why, zend, path = an.simulate(r)
        paths[r["id"]] = path
        report("  route %-30s %s%s (end floor z=%.0f)" % (r["id"], "PASS" if ok else "FAIL ", "" if ok else " - " + why, zend))
        if not ok:
            err("Route %s failed: %s" % (r["id"], why))
            fails += 1
    for r in d["blocked_routes"]:
        ok, why, zend, _ = an.simulate(r)
        report("  blocked %-28s %s (%s)" % (r["id"], "PASS (blocked)" if not ok else "FAIL (passable!)", why))
        if ok:
            err("Route %s should be blocked but is passable" % r["id"])
            fails += 1
    f0 = an.floor_at(start[0], start[1], 0.0)
    sb = an.blocked_by(start[0], start[1], f0 if f0 is not None else 0.0)
    report("Player start (%d,%d) floor z=%s blocked=%s -> %s" % (start[0], start[1], f0, sb and sb["id"], "VALID" if f0 is not None and sb is None else "INVALID"))
    if f0 is None or sb is not None:
        err("Player start invalid")

    # ---- reachability + edges
    report("== Reachability and edges ==")
    seen, expo = an.flood(start)
    report("Reachable walking cells (20 cm grid): %d (~%.0f m2)" % (len(seen), len(seen) * 0.04))
    reach = {}
    for (kx, ky, kz), (x, y, z) in seen.items():
        reach.setdefault((kx, ky), []).append(z)

    def reachable(x, y, zf):
        for z in reach.get((int(x // 20.0), int(y // 20.0)), ()):
            if abs(z - zf) < 3.0:
                return True
        return False
    for x, y, zf, expect, label in d["reachability"]["samples"]:
        got = reachable(x, y, zf)
        report("  %-34s (%5d,%5d,z%3d) reachable=%-5s expected=%-5s %s" % (label, x, y, zf, got, expect, "ok" if got == expect else "MISMATCH"))
        if got != expect:
            err("Reachability mismatch: %s (%d,%d,z%d) got %s expected %s" % (label, x, y, zf, got, expect))
    report("Unprotected walkable edges with drop > 60 cm: %d cells" % len(expo))
    groups = {}
    for x, y, z, dd in expo:
        groups.setdefault((int(x // 200), int(y // 200), int(z // 50)), []).append((x, y, z, dd))
    for key, items in sorted(groups.items())[:15]:
        report("    exposed edge near (%d,%d) walking z=%d drop up to %d (%d cells)" % (
            sum(i[0] for i in items) / len(items), sum(i[1] for i in items) / len(items), items[0][2], max(i[3] for i in items), len(items)))
    if expo:
        err("%d unprotected edge cells (falls possible)" % len(expo))

    # ---- sightlines
    report("== Sightlines ==")
    cam = (start[0] - 200.0, start[1], 230.0)
    eye = (start[0], start[1], 170.0)
    ct = d["cell_tiers"]
    cx = [ct["x0"] + ct["width"] * (i + 0.5) for i in range(ct["count"])]
    face_y = ct["y0"] - study.T / 2.0 - 5.0

    def vis_any(tgt):
        return an.visible(eye, tgt) or an.visible(cam, tgt)
    report("From the intake start (eye z=170, camera ~200 cm behind at z=230):")
    for label, z in (("lower cell door faces (z=130)", 130.0), ("lower tier colour band (z=300)", 300.0), ("upper cell door tops (z=620)", 620.0), ("upper cell door middles (z=540)", 540.0), ("upper tier colour band (z=695)", 695.0)):
        vis = [vis_any((x, face_y, z)) for x in cx]
        report("  %-34s %d/%d visible" % (label, sum(vis), len(vis)))
    look_pts = [("lookout cabin west wall + sign", (2780.0, 130.0, 430.0)), ("lookout cabin front wall + sign", (3050.0, 280.0, 430.0)),
                ("lookout cabin front window", (3050.0, 280.0, 540.0)), ("gallery balustrade (x=2400)", (2400.0, 2.0, 495.0)),
                ("upper crossing side rail", (3697.0, 450.0, 440.0)), ("authorized landing rail", (3600.0, 2.0, 495.0)),
                ("Floor 2 secured gate sign", (5585.0, 450.0, 440.0)), ("rail endpoint A", (2000.0, 450.0, 690.0)),
                ("rail endpoint B", (4800.0, 450.0, 690.0)), ("CCTV housing", (3850.0, 1130.0, 620.0)),
                ("hall -> prisoner stair foot", (900.0, 1000.0, 60.0)), ("hall -> staff stair door", (1850.0, 20.0, 150.0)),
                ("hall -> cafeteria arch interior", (2675.0, -150.0, 150.0))]
    for label, tgt in look_pts:
        report("  intake -> %-34s %s" % (label, "VISIBLE" if vis_any(tgt) else "hidden"))
    ok_up = sum(vis_any((x, face_y, 695.0)) for x in cx)
    if ok_up < 4 or not vis_any((3050.0, 280.0, 430.0)):
        warn("From the intake start the upper tier / lookout cabin are not clearly visible")

    cab_eyes = [(2900.0, 170.0, 555.0), (3050.0, 170.0, 555.0), (3200.0, 170.0, 555.0)]
    hall_pts = [(x, y) for x in range(100, 5600, 100) for y in range(50, 900, 100)]
    vis_hall = {p for p in hall_pts if any(an.visible(e, (p[0], p[1], 150.0)) for e in cab_eyes)}
    report("From the lookout cabin (3 eye positions behind the console, z=555): hall floor visible at head height %d%% (%d/%d points)" % (100 * len(vis_hall) // len(hall_pts), len(vis_hall), len(hall_pts)))
    wk_eyes = [(x, 1045.0, 390 + 165.0) for x in (1900, 3000, 4700)]
    vis_walk = {p for p in hall_pts if any(an.visible(e, (p[0], p[1], 150.0)) for e in wk_eyes)}
    report("From the upper cell walkway (3 eyes): hall floor visible %d%%; cabin or walkway: %d%%" % (100 * len(vis_walk) // len(hall_pts), 100 * len(vis_hall | vis_walk) // len(hall_pts)))
    for label, z in (("lower cell door faces", 130.0), ("upper cell door faces", 390 + 130.0)):
        n = sum(1 for x in cx if any(an.visible(e, (x, face_y, z)) for e in cab_eyes))
        report("  cabin sees %-24s %d/%d" % (label, n, len(cx)))
    for label, tgt in (("intake entrance (60,450)", (60.0, 450.0, 150.0)), ("Floor 2 gate approach (5400,450)", (5400.0, 450.0, 150.0)),
                       ("cafeteria arch (2750,20)", (2750.0, 20.0, 150.0)), ("prisoner stair foot (900,1000)", (900.0, 1000.0, 20.0)),
                       ("upper crossing mid (3850,450)", (3850.0, 450.0, 420.0)), ("staff stair door (1850,10)", (1850.0, 10.0, 150.0))):
        report("  cabin sees %-34s %s" % (label, any(an.visible(e, tgt) for e in cab_eyes)))

    # guard approach / hiding, with and without the cover pieces
    report("== Guard approach and cover ==")
    gp = [tuple(p) for p in d["guard_route"]["points"] if p[2] >= 380]
    samples = []
    for a_, b_ in zip(gp, gp[1:]):
        L = math.hypot(b_[0] - a_[0], b_[1] - a_[1])
        n = max(1, int(L // 100))
        for k in range(n + 1):
            t = k / float(n)
            samples.append((a_[0] + (b_[0] - a_[0]) * t, a_[1] + (b_[1] - a_[1]) * t))
    guard_eyes = [(x, y, 390 + 165.0) for x, y in samples]
    guard_eyes += [(3470.0, -750.0, 555.0), (3420.0, -750.0, 555.0)]   # guard leaving by the office east door
    cctv_eye = tuple(d["lines"][-1]["frustum"]["pos"]) if "frustum" in d["lines"][-1] else None
    if cctv_eye:
        guard_eyes.append(cctv_eye)                                      # fixed CCTV-01 as a watcher
    zone = [(x, y) for (kx, ky, kz), (x, y, z) in seen.items() if abs(z - 390) < 2 and ((-600 < y < 0 and 2116 < x < 3500) or (-900 < y < 0 and 3500 <= x < 4100))]
    an_nocover = Analyzer(study, include=lambda b: not b["id"].startswith("Cover_"))

    def hidden_from(analyzer, e):
        hid = set()
        for (x, y) in zone:
            # a standing player (capsule 180 high) is out of sight only if neither torso nor head can be seen
            if not analyzer.visible(e, (x, y, 390 + 90.0)) and not analyzer.visible(e, (x, y, 390 + 170.0)):
                hid.add((int(x // 40), int(y // 40)))
        return hid
    covers = [b for b in d["boxes"] if b["id"].startswith("Cover_")]
    gained_by = {b["id"]: 0 for b in covers}
    gained_union = set()
    per_sample = []
    for e in guard_eyes:
        h_c, h_n = hidden_from(an, e), hidden_from(an_nocover, e)
        gain = h_c - h_n
        gained_union |= gain
        per_sample.append((e, len(h_n), len(h_c), len(gain)))
        for b in covers:
            near = {c for c in gain if (b["x0"] - 200) / 40 <= c[0] <= (b["x1"] + 200) / 40 and (b["y0"] - 200) / 40 <= c[1] <= (b["y1"] + 200) / 40}
            gained_by[b["id"]] = max(gained_by[b["id"]], len(near))
    cells40 = {(int(x // 40), int(y // 40)) for x, y in zone}
    report("Watcher eye positions: %d (guard route ~every 100 cm, eye z=555; guard leaving the office east door x2; CCTV-01); gallery+landing walkable cells (40 cm): %d" % (len(guard_eyes), len(cells40)))
    for (e, n0, n1, g) in per_sample:
        report("  watcher at (%4d,%4d): %3d cells hidden by walls/fittings alone, %3d with cover pieces (+%d from cover)" % (e[0], e[1], n0, n1, g))
    report("  cells hidden from at least one guard position only because of cover: %d" % len(gained_union))
    for b in covers:
        report("    %-18s best single guard position: +%d hiding cells within 200 cm" % (b["id"], gained_by[b["id"]]))
        if gained_by[b["id"]] == 0:
            warn("%s gives no hiding cells for any guard route position" % b["id"])
    report("  roster (3120,-1088) visible from the office north door (2800,-560): %s; from the landing door line (3520,-750): %s" % (
        an.visible((2800, -560, 555.0), (3120, -1088, 474.0)), an.visible((3560, -750, 555.0), (3120, -1088, 474.0))))
    report("  office north door visible from the stair top (2150,-450): %s; from the hall floor below (2800,450): %s" % (
        an.visible((2150, -450, 555.0), (2800, -590, 500.0)), an.visible((2800, 450, 170.0), (2800, -590, 500.0))))
    report("  office east door visible from the bridge mid (3850,450): %s; from the landing (3850,-200): %s" % (
        an.visible((3850, 450, 555.0), (3500, -750, 500.0)), an.visible((3850, -200, 555.0), (3500, -750, 500.0))))

    # CCTV coverage
    f = getattr(study, "frustum", None)
    report("== CCTV-01 (fixed, placeholder) ==")
    if f:
        px, py, pz = f["pos"]
        yaw, pitch = math.radians(f["yaw"]), math.radians(f["pitch"])
        fwd = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))

        def in_frustum(t):
            v = (t[0] - px, t[1] - py, t[2] - pz)
            dist = math.sqrt(sum(c * c for c in v))
            if dist < 1 or dist > f["range"]:
                return False
            # horizontal / vertical angle relative to the camera axis
            ang_h = math.degrees(math.atan2(v[1], v[0])) - f["yaw"]
            ang_h = (ang_h + 180) % 360 - 180
            horiz = math.hypot(v[0], v[1])
            ang_v = math.degrees(math.atan2(v[2], horiz)) - f["pitch"]
            return abs(ang_h) <= f["hfov"] / 2 and abs(ang_v) <= f["vfov"] / 2

        def covered(x, y, z):
            t = (x, y, z + 140.0)
            return in_frustum(t) and an.visible((px, py, pz), t)
        zones = {"upper walkway": lambda x, y, z: abs(z - 390) < 2 and 900 < y < 1180,
                 "upper crossing": lambda x, y, z: abs(z - 390) < 2 and 0 < y < 900 and 3700 < x < 4000,
                 "authorized landing": lambda x, y, z: abs(z - 390) < 2 and 3500 < x < 4100 and -900 < y < 0,
                 "guard gallery": lambda x, y, z: abs(z - 390) < 2 and 2116 < x < 3500 and -600 < y < 0,
                 "lookout cabin": lambda x, y, z: abs(z - 390) < 2 and 2800 < x < 3300 and 0 <= y < 260,
                 "hall floor": lambda x, y, z: abs(z) < 2 and 0 < y < 900 and 1200 < x < 5600,
                 "guard office": lambda x, y, z: abs(z - 390) < 2 and 2500 < x < 3500 and -1200 < y < -600}
        report("Frustum: pos (%d,%d,%d) yaw %d pitch %d, %d x %d deg, range %d" % (px, py, pz, f["yaw"], f["pitch"], f["hfov"], f["vfov"], f["range"]))
        for zn, pred in zones.items():
            cells = [(x, y, z) for (kx, ky, kz), (x, y, z) in seen.items() if pred(x, y, z)]
            cov = sum(1 for c in cells if covered(*c))
            report("  %-20s covered %3d%% (%d/%d walkable cells at head height)" % (zn, 100 * cov // max(1, len(cells)), cov, len(cells)))
        for label, tgt in (("office east door threshold", (3500, -750, 390)), ("office north door threshold", (2800, -600, 390)), ("landing centre", (3800, -450, 390))):
            report("  %-28s in frustum=%s  line of sight=%s" % (label, in_frustum((tgt[0], tgt[1], tgt[2] + 140)), an.visible((px, py, pz), (tgt[0], tgt[1], tgt[2] + 140))))

    # camera clearance
    report("== Camera clearance along the test routes (approximation, arm %d cm, heights floor+160 / +230) ==" % d["params"]["camera_arm"])
    arm = float(d["params"]["camera_arm"])
    tight = {}
    n_samples = 0
    n_back_short = 0
    n_arc_short = 0
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
    report("Route samples: %d; camera arm shortened directly behind the player at %d (%.0f%%); an orbit extreme (+/-45/90 deg) would be < 120 cm at %d" % (
        n_samples, n_back_short, 100.0 * n_back_short / max(1, n_samples), n_arc_short))
    for key, v in sorted(tight.items(), key=lambda kv: kv[1])[:10]:
        report("    tightest around (%d..%d, %d..%d, z~%d): %.0f cm of arm free" % (key[0], key[0] + 200, key[1], key[1] + 200, key[2], v))
    report("Errors: %d  Warnings: %d" % (len(errors), len(warnings)))
    return errors, warnings
