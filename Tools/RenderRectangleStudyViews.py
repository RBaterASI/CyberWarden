"""Schematic renders of a rectangle-study layout (NOT Unreal captures): top-down plans and ground-level perspective views.

Pure Python (zlib + struct for PNG; no numpy/PIL, no editor, no project DLL). Renders the SAME generated boxes the Unreal
builder spawns (cw_rectstudy_v2.StudyV2 over the layout JSON), flat-shaded, so you can check placement before opening the map.

  "C:\\Program Files\\Epic Games\\UE_5.8\\Engine\\Binaries\\ThirdParty\\Python3\\Win64\\python.exe" -I Tools\\RenderRectangleStudyViews.py V5

Writes Docs/Layout/RectangleStudy<ver>_views/*.png. Text on signs is not drawn (only the plates).
"""
import math
import os
import struct
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJECT, "Content", "Python"))
import cw_rectstudy_v2 as cw  # noqa: E402

VER = sys.argv[1] if len(sys.argv) > 1 else "V5"
LAYOUT = os.path.join(PROJECT, "Docs", "Layout", "S01_LW_F1_RectangleStudy_%s.json" % VER)
OUT = os.path.join(PROJECT, "Docs", "Layout", "RectangleStudy%s_views" % VER)
os.makedirs(OUT, exist_ok=True)

# V6 follows the build sheet / Unreal frame: +X east (right), +Y SOUTH (down in a plan, to the RIGHT of an east-facing camera).
# V1-V5 labelled +Y "north" and were drawn with +Y up / to the left of an east-facing camera (i.e. mirrored N-S relative to Unreal's own top view).
UE_FRAME = VER in ("V6", "V7")
data = cw.load(LAYOUT)
study = cw.StudyV2(data)
AREAS = data["areas"]
BOXES = [b for b in study.boxes]


def base_color(b):
    m = b.get("mat")
    if m:
        kind, area = m.split(":", 1)
        c = AREAS[area]["color"]
        k = 0.82 if kind == "lit" else 1.0
        return (min(255, c[0] * k), min(255, c[1] * k), min(255, c[2] * k))
    kd = b["kind"]
    if kd == "wall":
        return (214, 214, 220)
    if kd in ("floor", "slab"):
        return (70, 74, 90) if b["z0"] >= 700 else (128, 134, 146)
    if kd == "rail":
        return (96, 98, 110)
    return (160, 160, 160)


def write_png(path, w, h, rows):
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, payload):
        c = struct.pack(">I", len(payload)) + tag + payload
        return c + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------------------------------------- top-down plan
def plan(name, x0, x1, y0, y1, cm_per_px, cut_z, skip_kinds=("sign",), min_z0=-9999):
    W, H = int((x1 - x0) / cm_per_px), int((y1 - y0) / cm_per_px)
    img = [[(26, 28, 36)] * W for _ in range(H)]
    items = []
    for b in BOXES:
        if b["kind"] in skip_kinds or b["z0"] >= cut_z or b["z1"] < min_z0:
            continue
        top = min(b["z1"], cut_z)
        items.append((top, b["z0"], b))
    items.sort(key=lambda t: (t[0], t[1]))
    for top, z0, b in items:
        c = base_color(b)
        shade = 0.72 + 0.28 * min(1.0, max(0.0, top) / 700.0)
        if b["kind"] == "wall":
            col = (40, 42, 52)
        elif b["kind"] == "rail":
            col = (30, 30, 36)
        else:
            col = tuple(int(min(255, v * shade)) for v in c)
        px0, px1 = int((b["x0"] - x0) / cm_per_px), int(math.ceil((b["x1"] - x0) / cm_per_px))
        if UE_FRAME:
            py0, py1 = int((b["y0"] - y0) / cm_per_px), int(math.ceil((b["y1"] - y0) / cm_per_px))
        else:
            py0, py1 = int((y1 - b["y1"]) / cm_per_px), int(math.ceil((y1 - b["y0"]) / cm_per_px))
        px0, px1 = max(0, px0), min(W, max(px1, px0 + 1))
        py0, py1 = max(0, py0), min(H, max(py1, py0 + 1))
        if px0 >= px1 or py0 >= py1:
            continue
        row = [col] * (px1 - px0)
        for yy in range(py0, py1):
            img[yy][px0:px1] = row
    # 1 m grid ticks every 10 m (small marks on the border) for scale
    for gx in range(int(x0 // 1000 + 1) * 1000, int(x1), 1000):
        px = int((gx - x0) / cm_per_px)
        for yy in range(0, 6):
            img[yy][px] = (255, 255, 255)
    for gy in range(int(y0 // 1000 + 1) * 1000, int(y1), 1000):
        py = int((gy - y0) / cm_per_px) if UE_FRAME else int((y1 - gy) / cm_per_px)
        for xx in range(0, 6):
            img[py][xx] = (255, 255, 255)
    rows = [[v for px in r for v in px] for r in img]
    write_png(os.path.join(OUT, name), W, H, rows)
    return name, W, H


# ---------------------------------------------------------------------------------------------- perspective ray cast
def perspective(name, cam, target, fov, W, H, hide_roof=False):
    t0 = time.time()
    cx, cy, cz = cam
    fx, fy, fz = target[0] - cx, target[1] - cy, target[2] - cz
    fl = math.sqrt(fx * fx + fy * fy + fz * fz)
    fx, fy, fz = fx / fl, fy / fl, fz / fl
    rx, ry, rz = (-fy, fx, 0.0) if UE_FRAME else (fy, -fx, 0.0)
    rl = math.hypot(rx, ry)
    rx, ry = rx / rl, ry / rl
    ux, uy, uz = ry * fz - rz * fy, rz * fx - rx * fz, rx * fy - ry * fx
    tanf = math.tan(math.radians(fov) / 2.0)
    aspect = W / float(H)
    TILE = 16
    tw, th = (W + TILE - 1) // TILE, (H + TILE - 1) // TILE
    tiles = [[[] for _ in range(tw)] for _ in range(th)]
    boxes = [b for b in BOXES if not (hide_roof and b["z0"] >= 700)]
    packed = []
    for b in boxes:
        xs, ys, zs = (b["x0"], b["x1"]), (b["y0"], b["y1"]), (b["z0"], b["z1"])
        sxmin = symin = 1e9
        sxmax = symax = -1e9
        behind = False
        for X in xs:
            for Y in ys:
                for Z in zs:
                    dx, dy, dz = X - cx, Y - cy, Z - cz
                    depth = dx * fx + dy * fy + dz * fz
                    if depth <= 5.0:
                        behind = True
                        continue
                    sx = ((dx * rx + dy * ry) / (depth * tanf * aspect) + 1.0) * 0.5 * W
                    sy = (1.0 - (dx * ux + dy * uy + dz * uz) / (depth * tanf)) * 0.5 * H
                    sxmin, sxmax, symin, symax = min(sxmin, sx), max(sxmax, sx), min(symin, sy), max(symax, sy)
        if behind:
            sxmin, sxmax, symin, symax = 0, W, 0, H
        if sxmax < 0 or sxmin > W or symax < 0 or symin > H:
            continue
        idx = len(packed)
        c = base_color(b)
        packed.append((b["x0"], b["x1"], b["y0"], b["y1"], b["z0"], b["z1"], c))
        for ty in range(max(0, int(symin) // TILE), min(th - 1, int(symax) // TILE) + 1):
            for tx in range(max(0, int(sxmin) // TILE), min(tw - 1, int(sxmax) // TILE) + 1):
                tiles[ty][tx].append(idx)
    light = (0.35, -0.45, 0.82)
    ll = math.sqrt(sum(v * v for v in light))
    light = tuple(v / ll for v in light)
    rows = []
    for j in range(H):
        row = []
        for i in range(W):
            u = (2.0 * (i + 0.5) / W - 1.0) * tanf * aspect
            v = (1.0 - 2.0 * (j + 0.5) / H) * tanf
            dx, dy, dz = fx + rx * u + ux * v, fy + ry * u + uy * v, fz + rz * u + uz * v
            inv = (1.0 / dx if abs(dx) > 1e-9 else 1e12, 1.0 / dy if abs(dy) > 1e-9 else 1e12, 1.0 / dz if abs(dz) > 1e-9 else 1e12)
            best, hit = 1e12, None
            for idx in tiles[j // TILE][i // TILE]:
                bx0, bx1, by0, by1, bz0, bz1, col = packed[idx]
                t1, t2 = (bx0 - cx) * inv[0], (bx1 - cx) * inv[0]
                if t1 > t2:
                    t1, t2 = t2, t1
                ax = 0
                tn, tf = t1, t2
                s1, s2 = (by0 - cy) * inv[1], (by1 - cy) * inv[1]
                if s1 > s2:
                    s1, s2 = s2, s1
                if s1 > tn:
                    tn, ax = s1, 1
                if s2 < tf:
                    tf = s2
                r1, r2 = (bz0 - cz) * inv[2], (bz1 - cz) * inv[2]
                if r1 > r2:
                    r1, r2 = r2, r1
                if r1 > tn:
                    tn, ax = r1, 2
                if r2 < tf:
                    tf = r2
                if tn > tf or tf < 0 or tn < 1.0 or tn >= best:
                    continue
                best, hit = tn, (col, ax)
            if hit is None:
                g = int(30 + 40 * (1.0 - j / H))
                row += [g, g + 4, g + 14]
                continue
            col, ax = hit
            nrm = [0.0, 0.0, 0.0]
            nrm[ax] = -1.0 if (dx, dy, dz)[ax] > 0 else 1.0
            lam = max(0.0, nrm[0] * light[0] + nrm[1] * light[1] + nrm[2] * light[2])
            k = 0.42 + 0.58 * lam
            fog = max(0.35, 1.0 - best / 14000.0)
            row += [int(min(255, col[0] * k * fog)), int(min(255, col[1] * k * fog)), int(min(255, col[2] * k * fog))]
        rows.append(row)
    write_png(os.path.join(OUT, name), W, H, rows)
    return name, W, H, time.time() - t0


if __name__ == "__main__":
    made = []
    only = sys.argv[2] if len(sys.argv) > 2 else None
    if VER == "V7":
        made.append(plan("V7_plan_lower_tier.png", 0, 6100, 0, 5100, 6, 260))
        made.append(plan("V7_plan_upper_tier.png", 0, 6100, 0, 5100, 6, 640))
        if only != "plans":
            made.append(perspective("V7_view_spawn_looking_west_through_D02.png", (5940, 1030, 235), (3000, 1030, 150), 80, 640, 360))
            made.append(perspective("V7_view_hall_from_the_west_to_lookout_mesh_and_net.png", (1300, 1400, 170), (5300, 1000, 330), 80, 640, 360))
            made.append(perspective("V7_view_work_corridor_from_the_staff_room_window.png", (5560, 3690, 160), (900, 3690, 150), 70, 640, 360))
            made.append(perspective("V7_view_north_walkway_behind_the_mesh.png", (4200, 773, 560), (1500, 773, 540), 80, 640, 360))
    elif VER == "V6" and only == "plans":
        made.append(plan("V6_plan_lower_tier.png", 0, 6100, 0, 5100, 6, 300))
        made.append(plan("V6_plan_upper_tier.png", 0, 6100, 0, 5100, 6, 740))
    elif VER == "V5" and only == "lower":
        made.append(plan("V5_lower_plan_intake_beside_north_stair.png", 4100, 6200, 1700, 2900, 3, 200))
    elif VER == "V5":
        made.append(plan("V5_topdown_guard_suite_upper_tier.png", 2600, 6300, -100, 2950, 4, 680))
        made.append(plan("V5_lower_plan_intake_beside_north_stair.png", 4100, 6200, 1700, 2900, 3, 200))
        made.append(perspective("V5_ground_view_intake_beside_north_stair.png", (4900, 1350, 190), (5150, 2300, 110), 78, 640, 360, hide_roof=False))
        made.append(perspective("V5_ground_view_from_intake_start.png", (5350, 2740, 235), (5350, 2150, 110), 80, 640, 360, hide_roof=False))
        made.append(perspective("V5_ground_view_north_stair_to_walkway.png", (5300, 2150, 175), (4300, 2150, 330), 80, 640, 360, hide_roof=False))
        made.append(perspective("V5_hall_view_toward_suite_from_crossover.png", (3200, 1400, 560), (5600, 1400, 520), 85, 640, 360, hide_roof=False))
    elif VER == "V6":
        made.append(plan("V6_plan_lower_tier.png", 0, 6100, 0, 5100, 6, 300))
        made.append(plan("V6_plan_upper_tier.png", 0, 6100, 0, 5100, 6, 740))
        made.append(perspective("V6_view_spawn_looking_west_through_D02.png", (5940, 1030, 235), (3000, 1030, 150), 80, 640, 360))
        made.append(perspective("V6_view_hall_from_crossover_toward_lookout_and_S1.png", (3100, 1400, 560), (5400, 900, 430), 85, 640, 360))
        made.append(perspective("V6_view_S1_and_intake_opening_from_hall.png", (4300, 1650, 170), (5300, 800, 130), 80, 640, 360))
        made.append(perspective("V6_view_lookout_looking_west_over_hall.png", (5560, 1400, 555), (2000, 1400, 330), 85, 640, 360))
    for m in made:
        print("wrote", m)
