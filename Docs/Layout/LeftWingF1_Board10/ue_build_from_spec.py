"""
Cyber Warden — S01 Left Wing Floor 1 greybox generator for Unreal Engine 5.
Builds the whole layout from LeftWing_F1_spec.json so every door, window and
stair lands exactly where the spec says.

Run inside the Unreal Editor (Python Editor Script Plugin enabled):
    Output Log > Cmd dropdown > Python, then:  py "C:/path/to/ue_build_from_spec.py"
Use a fresh level (with your sky and lighting) so the old hand-built pieces don't overlap.
Re-running deletes and rebuilds everything inside the ROOT outliner folder.
"""
import json
import os
import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_PATH = os.path.join(HERE, "LeftWing_F1_spec.json")
ROOT = "S01_LW_F1_Gen"                      # outliner folder for everything generated
MAT_DIR = "/Game/Greybox/LeftWingF1/Materials"
ORIGIN_CM = unreal.Vector(0.0, 0.0, 0.0)    # move the whole build by changing this
BUILD_ROOF = True                           # True adds a roof slab at Z 7.5 m
BAR_SPACING = 0.5                           # metres between mesh bars on walkway edges
TOL = 0.05

spec = json.load(open(SPEC_PATH, encoding="utf-8"))
T = spec["wall_thickness"]
LV = spec["levels"]
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
CUBE = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
BASE_MAT = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")
_mats = {}
COUNT = {"actors": 0}


def emissive_parent():
    path = f"{MAT_DIR}/M_LW_Emissive"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.EditorAssetLibrary.load_asset(path)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    m = tools.create_asset("M_LW_Emissive", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    lib = unreal.MaterialEditingLibrary
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    col = lib.create_material_expression(m, unreal.MaterialExpressionVectorParameter, -500, 0)
    col.set_editor_property("parameter_name", "Color")
    col.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    glow = lib.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -500, 200)
    glow.set_editor_property("parameter_name", "Glow")
    glow.set_editor_property("default_value", 5.0)
    mul = lib.create_material_expression(m, unreal.MaterialExpressionMultiply, -250, 100)
    lib.connect_material_expressions(col, "", mul, "A")
    lib.connect_material_expressions(glow, "", mul, "B")
    lib.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def emissive_mi(kind, rgb):
    try:
        path = f"{MAT_DIR}/MI_{kind}"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            mi = unreal.EditorAssetLibrary.load_asset(path)
        else:
            tools = unreal.AssetToolsHelpers.get_asset_tools()
            mi = tools.create_asset(f"MI_{kind}", MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        unreal.MaterialEditingLibrary.set_material_instance_parent(mi, emissive_parent())
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Glow", float(spec["emissive"][kind]))
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        return mi
    except Exception as e:
        unreal.log_warning(f"[LW_F1] emissive material for {kind} failed ({e}); using the plain lit colour")
        return None


def mat(kind):
    if kind in _mats:
        return _mats[kind]
    if kind in spec.get("emissive", {}):
        m_ = emissive_mi(kind, spec["colours"].get(kind, [1, 1, 1]))
        if m_ is not None:
            _mats[kind] = m_
            return m_
    rgb = spec["colours"].get(kind, [0.6, 0.6, 0.6])
    path = f"{MAT_DIR}/MI_{kind}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        mi = unreal.EditorAssetLibrary.load_asset(path)
    else:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        mi = tools.create_asset(f"MI_{kind}", MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        unreal.MaterialEditingLibrary.set_material_instance_parent(mi, BASE_MAT)
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    unreal.EditorAssetLibrary.save_loaded_asset(mi)
    _mats[kind] = mi
    return mi


def box(label, folder, x0, y0, x1, y1, z0, z1, kind, camera_ignore=False, collide=True):
    """Axis-aligned box in plan metres (X east, Y south, Z up). The engine cube is 100 cm, so scale = metres."""
    sx, sy, sz = abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)
    if min(sx, sy, sz) < 0.005:
        return None
    loc = ORIGIN_CM + unreal.Vector((x0 + x1) * 50.0, (y0 + y1) * 50.0, (z0 + z1) * 50.0)
    a = actor_sub.spawn_actor_from_object(CUBE, loc)
    a.set_actor_scale3d(unreal.Vector(sx, sy, sz))
    a.set_actor_label(label)
    a.set_folder_path(f"{ROOT}/{folder}")
    comp = a.static_mesh_component
    comp.set_material(0, mat(kind))
    if not collide:
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    elif camera_ignore:
        comp.set_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA, unreal.CollisionResponseType.ECR_IGNORE)
    COUNT["actors"] += 1
    return a


def clear_previous():
    """Delete everything this script built (folder ROOT) and any leftover zone volumes from the old M1 map (tags Zone:* / Room:* outside ROOT)."""
    for a in actor_sub.get_all_level_actors():
        try:
            if str(a.get_folder_path()).startswith(ROOT):
                actor_sub.destroy_actor(a)
                continue
            tags = [str(t) for t in a.get_editor_property("tags")]
            if any(t.startswith("Zone:") or t.startswith("Room:") or t.startswith("ZoneProvisional") for t in tags):
                actor_sub.destroy_actor(a)
        except Exception:
            pass


# ------------------------------------------------------------------ openings
def openings_on(tier, orient, at, a, b):
    """Doors and windows lying on a wall line, clipped to [a, b]. Returns (s, e, zlo_rel, zhi_rel, kind)."""
    out = []
    for d in spec["doors"]:
        if d["tier"] == tier and d["wall"] == orient and abs(d["at"] - at) < TOL:
            s, e = max(d["span"][0], a), min(d["span"][1], b)
            if e - s > 0.01:
                out.append((s, e, 0.0, d["height"], "sealed" if d["type"] == "sealed" else "door"))
    for w in spec["windows"]:
        if w["tier"] == tier and w["wall"] == orient and abs(w["at"] - at) < TOL:
            s, e = max(w["span"][0], a), min(w["span"][1], b)
            if e - s > 0.01:
                out.append((s, e, w["sill"], w["head"], "window"))
    return out


def wall_line(label, tier, orient, at, a, b, z0, z1, folder="Walls", kind="wall"):
    """Build one wall line split around its openings (doors get a lintel, windows a sill and a lintel)."""
    ops = openings_on(tier, orient, at, a, b)
    cuts = sorted({a, b, *[o[0] for o in ops], *[o[1] for o in ops]})
    for s, e in zip(cuts, cuts[1:]):
        if e - s < 0.01:
            continue
        mid = (s + e) / 2
        hole = next((o for o in ops if o[0] <= mid <= o[1]), None)
        bands = [(z0, z1)] if hole is None else [(z0, z0 + hole[2]), (z0 + hole[3], z1)]
        ss = s - T / 2 if abs(s - a) < 1e-6 else s        # square corner: the wall line's own start/end only, never a door or window edge
        ee = e + T / 2 if abs(e - b) < 1e-6 else e
        for zl, zh in bands:
            if zh - zl < 0.01:
                continue
            if orient == "x":
                box(label, folder, at - T / 2, ss, at + T / 2, ee, zl, zh, kind)
            else:
                box(label, folder, ss, at - T / 2, ee, at + T / 2, zl, zh, kind)
        if hole is not None and hole[4] == "sealed":
            zl, zh = z0, z0 + hole[3]
            if orient == "x":
                box(label + "_SEALED", "Doors_Sealed", at - T / 2, s, at + T / 2, e, zl, zh, "seal")
            else:
                box(label + "_SEALED", "Doors_Sealed", s, at - T / 2, e, at + T / 2, zl, zh, "seal")


def rect_minus(r, holes):
    """Subtract axis-aligned holes from rect r = (x0, y0, x1, y1)."""
    pieces = [r]
    for hx0, hy0, hx1, hy1 in holes:
        nxt = []
        for x0, y0, x1, y1 in pieces:
            if hx1 <= x0 or hx0 >= x1 or hy1 <= y0 or hy0 >= y1:
                nxt.append((x0, y0, x1, y1))
                continue
            if hy0 > y0: nxt.append((x0, y0, x1, hy0))
            if hy1 < y1: nxt.append((x0, hy1, x1, y1))
            my0, my1 = max(y0, hy0), min(y1, hy1)
            if hx0 > x0: nxt.append((x0, my0, hx0, my1))
            if hx1 < x1: nxt.append((hx1, my0, x1, my1))
        pieces = nxt
    return pieces


# ------------------------------------------------------------------ build steps
def build_floors_and_walls():
    W, H = spec["footprint"]
    up = LV["upper"]["floor_z"]
    slab = LV["slab"]
    box("Ground", "Floors", 0, 0, W, H, -slab, 0, "outer")
    staff_holes = [(s["footprint"][0], s["footprint"][1], s["footprint"][0] + s["footprint"][2], s["footprint"][1] + s["footprint"][3])
                   for s in spec["stairs"] if "footprint" in s]
    for r in spec["rooms"]:
        x0, y0, x1, y1 = r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]
        tier = r["tier"]
        if tier == "lower":
            box(f"{r['id']}_{r['name']}_Floor", "Floors/Lower", x0, y0, x1, y1, 0, 0.02, r["kind"])
            if r["ceiling"] == LV["lower"]["corridor_ceiling"]:
                box(f"{r['id']}_Ceiling", "Ceilings", x0, y0, x1, y1, 2.7, 2.8, "outer")
            z0, z1 = 0.0, r["ceiling"] or LV["lower"]["room_ceiling"]
        else:
            for i, (a0, b0, a1, b1) in enumerate(rect_minus((x0, y0, x1, y1), staff_holes)):
                box(f"{r['id']}_{r['name']}_Slab{i}", "Floors/Upper", a0, b0, a1, b1, up - slab, up, r["kind"])
            z0, z1 = up, LV["upper"]["ceiling"]
        if r["walls"]:
            lab = f"{r['id']}_{r['name']}"
            wall_line(lab + "_WallN", tier, "y", y0, x0, x1, z0, z1)
            wall_line(lab + "_WallS", tier, "y", y1, x0, x1, z0, z1)
            wall_line(lab + "_WallW", tier, "x", x0, y0, y1, z0, z1)
            wall_line(lab + "_WallE", tier, "x", x1, y0, y1, z0, z1)
    for tier, z0, z1 in (("lower", 0.0, up), ("upper", up, LV["roof_z"] + slab)):
        wall_line(f"Outer_{tier}_N", tier, "y", 0, 0, W, z0, z1, "Outer", "outer")
        wall_line(f"Outer_{tier}_S", tier, "y", H, 0, W, z0, z1, "Outer", "outer")
        wall_line(f"Outer_{tier}_W", tier, "x", 0, 0, H, z0, z1, "Outer", "outer")
        wall_line(f"Outer_{tier}_E", tier, "x", W, 0, H, z0, z1, "Outer", "outer")
    if BUILD_ROOF:
        box("Roof", "Ceilings", 0, 0, W, H, LV["roof_z"], LV["roof_z"] + slab, "outer")


def build_stairs():
    for s in spec["stairs"]:
        if "x_foot" in s:
            n, rise = s["risers"], s["rise"]
            run = (s["x_foot"] - s["x_top"]) / n
            for i in range(n):
                xa = s["x_foot"] - run * i
                box(f"{s['id']}_Step{i+1:02d}", f"Stairs/{s['id']}", xa - run, s["y0"], xa, s["y1"], 0, rise / n * (i + 1), "stair")
        else:
            x, y, w, h = s["footprint"]
            half = 3.9 / 2
            long_x = w >= h
            L, Wd = (w, h) if long_x else (h, w)
            landing = 1.2 if s["id"] == "S3" else 1.6
            flight_len = L - landing
            fw = (Wd - 0.2) / 2
            steps = 13
            for k in range(steps):
                ra = flight_len / steps
                top = half / steps * (k + 1)
                a0, a1 = ra * k, ra * (k + 1)                     # flight A rises away from the start edge
                b0, b1 = flight_len - ra * (k + 1), flight_len - ra * k   # flight B rises back toward it
                if long_x:
                    box(f"{s['id']}_A{k+1:02d}", f"Stairs/{s['id']}", x + a0, y, x + a1, y + fw, 0, top, "stair")
                    box(f"{s['id']}_B{k+1:02d}", f"Stairs/{s['id']}", x + b0, y + Wd - fw, x + b1, y + Wd, 0, half + top, "stair")
                else:
                    box(f"{s['id']}_A{k+1:02d}", f"Stairs/{s['id']}", x, y + a0, x + fw, y + a1, 0, top, "stair")
                    box(f"{s['id']}_B{k+1:02d}", f"Stairs/{s['id']}", x + Wd - fw, y + b0, x + Wd, y + b1, 0, half + top, "stair")
            if long_x:
                box(f"{s['id']}_Landing", f"Stairs/{s['id']}", x + flight_len, y, x + w, y + h, 0, half, "stair")
            else:
                box(f"{s['id']}_Landing", f"Stairs/{s['id']}", x, y + flight_len, x + w, y + h, 0, half, "stair")


def build_mesh():
    up, top = LV["upper"]["floor_z"], LV["upper"]["ceiling"]
    stair_sides = {(45, 8.8, 52, 8.8), (45, 6.6, 52, 6.6), (8.8, 15.6, 15.8, 15.6), (8.8, 17.4, 15.8, 17.4)}   # these cage the prisoner stairs from the ground up
    for x0, y0, x1, y1 in spec["mesh_edges_upper"]:
        zb = 0.0 if (x0, y0, x1, y1) in stair_sides else up
        length = max(abs(x1 - x0), abs(y1 - y0))
        n = max(1, int(length / BAR_SPACING))
        for i in range(n + 1):
            t = i / n
            bx, by = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            box("MeshBar", "Mesh", bx - 0.02, by - 0.02, bx + 0.02, by + 0.02, zb, top, "wall", camera_ignore=True)
        for zr in (zb + 1.1, top - 0.05):
            if x0 == x1:
                box("MeshRail", "Mesh", x0 - 0.03, y0, x0 + 0.03, y1, zr - 0.03, zr + 0.03, "wall", camera_ignore=True)
            else:
                box("MeshRail", "Mesh", x0, y0 - 0.03, x1, y0 + 0.03, zr - 0.03, zr + 0.03, "wall", camera_ignore=True)


RAIL_H = 1.1
RAIL_T = 0.06


def build_staff_rails():
    """1.1 m rails on the open side of every staff flight and around both upper-slab holes. Staff stairs run along Y (S3, S4) or X."""
    up = LV["upper"]["floor_z"]
    half = up / 2.0
    for s in spec["stairs"]:
        if "footprint" not in s:
            continue
        x, y, w, h = s["footprint"]
        long_x = w >= h
        L, Wd = (w, h) if long_x else (h, w)
        landing = 1.2 if s["id"] == "S3" else 1.6
        flight = L - landing
        fw = (Wd - 0.2) / 2
        steps = 13
        ra = flight / steps
        sid = s["id"]

        def ub(label, u0, v0, u1, v1, z0, z1):
            """box in stair-local (along u, across v) coordinates"""
            if long_x:
                return box(label, f"Rails/{sid}", x + u0, y + v0, x + u1, y + v1, z0, z1, "wall")
            return box(label, f"Rails/{sid}", x + v0, y + u0, x + v1, y + u1, z0, z1, "wall")

        for k in range(steps):                                     # lane A outer side, following the steps
            top = half / steps * (k + 1)
            ub(f"{sid}_RailA{k+1:02d}", ra * k, -RAIL_T, ra * (k + 1), 0.0, top, top + RAIL_H)
        ub(f"{sid}_RailLandingSide", flight, -RAIL_T, L, 0.0, 0.0, half + RAIL_H)            # landing, lane A side
        ub(f"{sid}_RailLandingEnd", L, -RAIL_T, L + RAIL_T, Wd, 0.0, half + RAIL_H)          # landing, far end (open to the apron)
        ub(f"{sid}_Divider", 0.0, fw, flight, fw + 0.2, 0.0, up + RAIL_H)                     # solid divider between the flights
        # upper-slab hole: rails on the floor side of every open edge; the lane B top exit (north end, east lane) stays open
        ub(f"{sid}_HoleRailSide", -RAIL_T, -RAIL_T, L + RAIL_T, 0.0, up, up + RAIL_H)
        ub(f"{sid}_HoleRailEnd", L, 0.0, L + RAIL_T, Wd, up, up + RAIL_H)
        ub(f"{sid}_HoleRailExitSide", -RAIL_T, 0.0, 0.0, fw + 0.1, up, up + RAIL_H)           # north end, over lane A and the divider only


def rect_minus_list(r, holes):
    return rect_minus(r, [(hx, hy, hx + hw, hy + hh) for hx, hy, hw, hh in holes])


def net_material():
    """Translucent unlit material for the safety net (created once under MAT_DIR)."""
    path = f"{MAT_DIR}/M_Net_Translucent"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.EditorAssetLibrary.load_asset(path)
    try:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        m = tools.create_asset("M_Net_Translucent", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
        lib = unreal.MaterialEditingLibrary
        m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        col = lib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -400, 0)
        rgb = spec["colours"].get("net", [0.8, 0.8, 0.85])
        col.set_editor_property("constant", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
        lib.connect_material_property(col, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        op = lib.create_material_expression(m, unreal.MaterialExpressionConstant, -400, 200)
        op.set_editor_property("r", 0.25)
        lib.connect_material_property(op, "", unreal.MaterialProperty.MP_OPACITY)
        lib.recompile_material(m)
        unreal.EditorAssetLibrary.save_loaded_asset(m)
        return m
    except Exception as e:
        unreal.log_warning(f"[LW_F1] translucent net material failed ({e}); using the plain wall colour")
        return None


def build_net():
    """Safety net across the hall void at Z 3.6: no collision, translucent. Cut around the S2 body and the crossover deck."""
    n = spec.get("safety_net")
    if not n:
        return
    m = net_material()
    pieces = rect_minus_list((n["x"], n["y"], n["x"] + n["w"], n["y"] + n["h"]), n.get("holes", []))
    for i, (x0, y0, x1, y1) in enumerate(pieces):
        a = box(f"SafetyNet{i}", "Net", x0, y0, x1, y1, n["z"], n["z"] + 0.02, "net", collide=False)
        if a is not None and m is not None:
            a.static_mesh_component.set_material(0, m)


def build_furniture():
    """Plain coloured collision boxes from spec['furniture']."""
    up = LV["upper"]["floor_z"]
    for f in spec.get("furniture", []):
        z0 = up if f["tier"] == "upper" else 0.0
        box(f["id"], "Furniture", f["x0"], f["y0"], f["x1"], f["y1"], z0, z0 + f["h"], f["kind"])


EXPOSURE_MODE = "auto"    # "auto": eye adaptation keeps every room readable whatever the light level; "manual": fixed exposure, set EXPOSURE_EV (HIGHER = BRIGHTER)
EXPOSURE_EV = 4.0          # manual mode only; see tune_board10_lighting.py to change the look without a rebuild
ROOM_CD = 3000.0           # ceiling point light intensity in rooms and corridors (unitless)
HALL_CD = 9000.0           # ... in the double-height hall
LIGHT_SPACING = 6.0        # metres between ceiling point lights in every room and corridor


def build_lighting():
    """Sun, sky, fog, manual-exposure post process, and a ceiling point light every 6 m in every room and corridor (all under S01_LW_F1_Gen/Lighting)."""
    folder = f"{ROOT}/Lighting"
    up = LV["upper"]["floor_z"]

    def put(cls, label, loc, rot=None):
        a = actor_sub.spawn_actor_from_class(cls, ORIGIN_CM + loc, rot) if rot is not None else actor_sub.spawn_actor_from_class(cls, ORIGIN_CM + loc)
        a.set_actor_label(label)
        a.set_folder_path(folder)
        return a
    try:
        sun = put(unreal.DirectionalLight, "Sun", unreal.Vector(0, 0, 2000), unreal.Rotator(0, -50, 35))
        sun.light_component.set_editor_property("intensity", 6.0)
    except Exception as ex:
        unreal.log_warning(f"[LW_F1] directional light: {ex}")
    try:
        sky = put(unreal.SkyLight, "SkyLight", unreal.Vector(0, 0, 2500))
        sky.light_component.set_editor_property("real_time_capture", True)
    except Exception as ex:
        unreal.log_warning(f"[LW_F1] sky light: {ex}")
    try:
        put(unreal.SkyAtmosphere, "SkyAtmosphere", unreal.Vector(0, 0, 2500))
    except Exception as ex:
        unreal.log_warning(f"[LW_F1] sky atmosphere: {ex}")
    try:
        fog = put(unreal.ExponentialHeightFog, "HeightFog", unreal.Vector(0, 0, 300))
        fog.component.set_editor_property("fog_density", 0.004)
    except Exception as ex:
        unreal.log_warning(f"[LW_F1] height fog: {ex}")
    try:
        ppv = put(unreal.PostProcessVolume, "PostProcess_Unbound", unreal.Vector(0, 0, 400))
        ppv.set_editor_property("unbound", True)
        st = ppv.get_editor_property("settings")
        st.set_editor_property("override_auto_exposure_method", True)
        if EXPOSURE_MODE == "manual":
            st.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
            st.set_editor_property("override_auto_exposure_bias", True)
            st.set_editor_property("auto_exposure_bias", EXPOSURE_EV)
        else:
            st.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
            st.set_editor_property("override_auto_exposure_bias", True)
            st.set_editor_property("auto_exposure_bias", 0.0)
        st.set_editor_property("override_motion_blur_amount", True)
        st.set_editor_property("motion_blur_amount", float(spec["review_camera"]["motion_blur"]))
        ppv.set_editor_property("settings", st)
    except Exception as ex:
        unreal.log_warning(f"[LW_F1] post process volume (manual exposure): {ex}")
    count = 0
    for r in spec["rooms"]:
        if min(r["w"], r["h"]) < 0.5:
            continue
        upper = r["tier"] == "upper"
        floor = up if upper else 0.0
        ceil_h = 3.6 if upper else (r.get("ceiling") or LV["roof_z"])        # height of the ceiling above this room's floor
        hall = (not upper) and r.get("ceiling") is None
        zt = floor + (LV["roof_z"] - 0.5 if hall else ceil_h - 0.3)          # just under the ceiling (the hall: just under the roof line)
        nx, ny = max(1, round(r["w"] / LIGHT_SPACING)), max(1, round(r["h"] / LIGHT_SPACING))
        inten, rad = (HALL_CD, 1100.0) if hall else (ROOM_CD, 700.0)
        for ix in range(nx):
            for iy in range(ny):
                cx, cy = r["x"] + r["w"] * (ix + 0.5) / nx, r["y"] + r["h"] * (iy + 0.5) / ny
                a = put(unreal.PointLight, f"Light_{r['id']}_{ix}{iy}", unreal.Vector(cx * 100.0, cy * 100.0, zt * 100.0))
                lc = a.light_component
                lc.set_mobility(unreal.ComponentMobility.MOVABLE)
                lc.set_editor_property("intensity", inten)
                lc.set_editor_property("attenuation_radius", rad)
                lc.set_editor_property("cast_shadows", False)
                count += 1
    unreal.log(f"[LW_F1] lighting built: sky/fog/post process + {count} ceiling point lights under {folder}")


def tier_z(tier):
    return LV["upper"]["floor_z"] if tier == "upper" else 0.0


def door_frame(d, kind):
    """Frame 0.1 m proud of the wall on both faces, 0.1 m wide, no collision."""
    fr = spec["door_frames"]
    pr, fw = fr["proud"], fr["width"]
    z0 = tier_z(d["tier"])
    top = z0 + d["height"]
    s0, s1 = d["span"]
    lo, hi = d["at"] - T / 2 - pr, d["at"] + T / 2 + pr
    parts = [("L", s0 - fw, s0, z0, top + fw), ("R", s1, s1 + fw, z0, top + fw), ("H", s0 - fw, s1 + fw, top, top + fw)]
    for tag, a0, a1, zl, zh in parts:
        if d["wall"] == "x":
            box(f"Frame_{d['id']}_{tag}", "Markers/Frames", lo, a0, hi, a1, zl, zh, kind, collide=False)
        else:
            box(f"Frame_{d['id']}_{tag}", "Markers/Frames", a0, lo, a1, hi, zl, zh, kind, collide=False)


def build_markers():
    """Gameplay markers: yellow floor tiles (2 cm), red frames on staff/restricted doors, yellow frames on gates, closed red slab on D27."""
    for t in spec["marker_tiles"]:
        z = tier_z(t["tier"]) + (0.02 if t["tier"] == "lower" else 0.0)
        box(t["id"], "Markers/Tiles", t["x0"], t["y0"], t["x1"], t["y1"], z, z + 0.02, t["kind"], collide=False)
    types = spec["door_frames"]["types"]
    n = 0
    for d in spec["doors"]:
        kind = types.get(d["type"])
        if kind:
            door_frame(d, kind)
            n += 1
    for d in spec["doors"]:
        if d.get("closed"):
            z0 = tier_z(d["tier"])
            s0, s1 = d["span"]
            if d["wall"] == "x":
                box(f"{d['id']}_Door_Closed", "Doors_Toggle", d["at"] - 0.1, s0, d["at"] + 0.1, s1, z0, z0 + d["height"], "door_red")
            else:
                box(f"{d['id']}_Door_Closed", "Doors_Toggle", s0, d["at"] - 0.1, s1, d["at"] + 0.1, z0, z0 + d["height"], "door_red")
    unreal.log(f"[LW_F1] markers: {len(spec['marker_tiles'])} tiles, {n} door frames")


def text_actor(label, text, x, y, z, yaw, size, rgb, folder):
    a = actor_sub.spawn_actor_from_class(unreal.TextRenderActor, ORIGIN_CM + unreal.Vector(x * 100, y * 100, z * 100), unreal.Rotator(0, 0, yaw))
    comp = a.text_render
    comp.set_text(text)
    comp.set_editor_property("horizontal_alignment", unreal.HorizTextAligment.EHTA_CENTER)
    comp.set_editor_property("vertical_alignment", unreal.VerticalTextAligment.EVRTA_TEXT_CENTER)
    comp.set_editor_property("world_size", float(size))
    comp.set_editor_property("text_render_color", unreal.Color(rgb[0], rgb[1], rgb[2], 255))
    a.set_actor_label(label)
    a.set_folder_path(f"{ROOT}/{folder}")
    return a


def build_landmarks():
    for b in spec["landmarks"]:
        box(b["id"], "Landmarks", b["x0"], b["y0"], b["x1"], b["y1"], b["z0"], b["z1"], b["kind"], collide=False)
    for t in spec["texts"]:
        text_actor(t["id"], t["text"], t["x"], t["y"], t["z"], t["yaw"], t["size"], t["color"], "Landmarks")


def build_corridor_details():
    """Work corridor: coloured ceiling light + room-name sign over every room door."""
    for c in spec["corridor_details"]:
        x, cy = c["x"], 36.9
        box(f"Lamp_{c['door']}", "Corridor", x - 0.25, cy - 0.25, x + 0.25, cy + 0.25, 2.62, 2.68, c["lamp"], collide=False)
        a = actor_sub.spawn_actor_from_class(unreal.PointLight, ORIGIN_CM + unreal.Vector(x * 100, cy * 100, 245))
        lc = a.light_component
        lc.set_mobility(unreal.ComponentMobility.MOVABLE)
        lc.set_editor_property("intensity", 1500.0)
        lc.set_editor_property("attenuation_radius", 450.0)
        lc.set_editor_property("light_color", unreal.Color(c["rgb"][0], c["rgb"][1], c["rgb"][2], 255))
        lc.set_editor_property("cast_shadows", False)
        a.set_actor_label(f"DoorLight_{c['door']}")
        a.set_folder_path(f"{ROOT}/Lighting")
        face = c["sign_y"]
        if c["yaw"] == 90:
            box(f"SignPlate_{c['door']}", "Corridor", x - 0.7, face - 0.03, x + 0.7, face + 0.01, 2.22, 2.5, "sign_dark", collide=False)
            text_actor(f"Sign_{c['door']}", c["room"], x, face + 0.02, 2.36, 90, 18, [255, 255, 255], "Corridor")
        else:
            box(f"SignPlate_{c['door']}", "Corridor", x - 0.7, face - 0.01, x + 0.7, face + 0.03, 2.22, 2.5, "sign_dark", collide=False)
            text_actor(f"Sign_{c['door']}", c["room"], x, face - 0.02, 2.36, -90, 18, [255, 255, 255], "Corridor")


def build_zones():
    """One trigger volume per spec room (both tiers), tagged Zone:<id> / ZoneName:<name> / Room:<id> for the HUD and gameplay."""
    n = 0
    for r in spec["rooms"]:
        if min(r["w"], r["h"]) < 0.5:
            continue
        upper = r["tier"] == "upper"
        floor = LV["upper"]["floor_z"] if upper else 0.0
        ch = 3.6 if upper else (r["ceiling"] or LV["roof_z"])
        tb = actor_sub.spawn_actor_from_class(unreal.TriggerBox, ORIGIN_CM + unreal.Vector((r["x"] + r["w"] / 2) * 100, (r["y"] + r["h"] / 2) * 100, (floor + ch / 2) * 100))
        try:
            tb.collision_component.set_box_extent(unreal.Vector(r["w"] * 50, r["h"] * 50, ch * 50), True)
        except Exception as e:
            unreal.log_warning(f"zone {r['id']} extent: {e}")
        tb.set_actor_label(f"Zone_{r['id']}_{r['name']}")
        tb.set_folder_path(f"{ROOT}/Zones")
        tb.set_editor_property("tags", [unreal.Name(t) for t in (f"Zone:{r['id']}", f"ZoneName:{r['name']}", f"Room:{r['id']}", f"Tier:{r['tier']}")])
        n += 1
    unreal.log(f"[LW_F1] zones: {n} volumes (one per spec room)")


def build_guide_and_markers():
    pts = spec["guide_line"]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        if abs(ax - bx) < 0.01:
            box("GuideLine", "Guide", ax - 0.15, min(ay, by), ax + 0.15, max(ay, by), 0.02, 0.035, "job", collide=False)
        elif abs(ay - by) < 0.01:
            box("GuideLine", "Guide", min(ax, bx), ay - 0.15, max(ax, bx), ay + 0.15, 0.02, 0.035, "job", collide=False)
        else:   # diagonal: approximate with a short run of tiles
            for i in range(12):
                t0, t1 = i / 12, (i + 1) / 12
                cx, cy = ax + (bx - ax) * (t0 + t1) / 2, ay + (by - ay) * (t0 + t1) / 2
                box("GuideLine", "Guide", cx - 0.15, cy - 0.15, cx + 0.15, cy + 0.15, 0.02, 0.035, "job", collide=False)
    sp = spec["spawn"]
    ps = actor_sub.spawn_actor_from_class(unreal.PlayerStart, ORIGIN_CM + unreal.Vector(sp["x"] * 100, sp["y"] * 100, 100), unreal.Rotator(0, 0, sp["ue_yaw"]))
    ps.set_actor_label("PlayerStart_Intake")
    ps.set_folder_path(f"{ROOT}/Gameplay")
    for t in spec["triggers"]:
        if "box" not in t:
            continue
        x, y, w, h = t["box"]
        z = LV["upper"]["floor_z"] if t["tier"] == "upper" else 0.0
        tb = actor_sub.spawn_actor_from_class(unreal.TriggerBox, ORIGIN_CM + unreal.Vector((x + w / 2) * 100, (y + h / 2) * 100, (z + 1.0) * 100))
        try:
            tb.collision_component.set_box_extent(unreal.Vector(w * 50, h * 50, 100), True)
        except Exception as e:
            unreal.log_warning(f"trigger {t['id']} extent: {e}")
        tb.set_actor_label(f"{t['id']}_{t['does']}")
        tb.set_folder_path(f"{ROOT}/Gameplay")
    W, H = spec["footprint"]
    nav = actor_sub.spawn_actor_from_class(unreal.NavMeshBoundsVolume, ORIGIN_CM + unreal.Vector(W * 50, H * 50, 400))
    nav.set_actor_scale3d(unreal.Vector(W * 100 / 200 + 1, H * 100 / 200 + 1, 10))
    nav.set_actor_label("NavBounds_LeftWingF1")
    nav.set_folder_path(f"{ROOT}/Gameplay")


def build_labels():
    for r in spec["rooms"]:
        if min(r["w"], r["h"]) < 1.5:
            continue
        z = (LV["upper"]["floor_z"] if r["tier"] == "upper" else 0.0) + 0.05
        try:
            a = actor_sub.spawn_actor_from_class(unreal.TextRenderActor, ORIGIN_CM + unreal.Vector((r["x"] + r["w"] / 2) * 100, (r["y"] + r["h"] / 2) * 100, z * 100),
                                                 unreal.Rotator(0, 90, 180))
            comp = a.text_render
            comp.set_text(f"{r['id']} {r['name']}")
            comp.set_editor_property("horizontal_alignment", unreal.HorizTextAligment.EHTA_CENTER)
            comp.set_editor_property("world_size", 40.0)
            a.set_actor_label(f"Label_{r['id']}")
            a.set_folder_path(f"{ROOT}/Labels")
        except Exception as e:
            unreal.log_warning(f"label {r['id']}: {e}")


def main():
    with unreal.ScopedSlowTask(6, "Building S01 Left Wing F1 greybox") as task:
        task.make_dialog(True)
        clear_previous(); task.enter_progress_frame(1)
        build_floors_and_walls(); task.enter_progress_frame(1)
        build_stairs(); task.enter_progress_frame(1)
        build_mesh(); build_staff_rails(); build_net(); task.enter_progress_frame(1)
        build_guide_and_markers(); build_labels(); build_furniture(); build_lighting(); build_markers(); build_landmarks(); build_corridor_details(); build_zones(); task.enter_progress_frame(1)
    unreal.log(f"[LW_F1] Built {COUNT['actors']} greybox pieces into outliner folder '{ROOT}'. Now run ue_validate_layout.py.")


main()
