"""Shared layout helpers for the Sector 01 Floor 1 greybox (builder + dev location indicator).

Pure Python (no `unreal` import) so it can be unit-tested anywhere.
"""


def expand(data):
    """Expand compact JSON (cell_rows) into full rooms/openings/boxes/markers lists."""
    rooms = [dict(r) for r in data["rooms"]]
    openings = [dict(o) for o in data["openings"]]
    boxes = [dict(b) for b in data["boxes"]]
    markers = [dict(m) for m in data["markers"]]
    cells = []
    info = data.get("room_info", {})
    for row in data["cell_rows"]:
        for i in range(row["count"]):
            x0 = row["x0"] + i * row["width"]
            x1 = x0 + row["width"]
            if row["side"] == "north":
                y0, y1 = row["hall_edge"], row["hall_edge"] + row["depth"]
                door_y, inside, ins_front = y0, y0 + 200, y0 - 100
                bunk_y = (y1 - 110, y1 - 20)
            else:
                y0, y1 = row["hall_edge"] - row["depth"], row["hall_edge"]
                door_y, inside, ins_front = y1, y1 - 200, y1 + 100
                bunk_y = (y0 + 20, y0 + 110)
            short = "%s%d" % (row["prefix"], i + 1)
            cid = "Cell_" + short
            cx = (x0 + x1) / 2.0
            cells.append(cid)
            rooms.append({"id": cid, "name": "Cell " + short, "zone": "A", "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                          "z": 0, "ceil": row["ceil"], "ceiling": row["ceiling"], "cell": True, "area": "CellBlock",
                          "sign": short})
            openings.append({"id": "Door_" + cid, "name": "Cell door " + cid, "axis": "h", "coord": door_y,
                             "center": cx, "width": row["door_width"], "z0": 0, "height": row["door_height"],
                             "cell_door": short})
            boxes.append({"id": "Bunk_" + cid, "name": "Bunk " + cid, "x0": x0 + 30, "x1": x0 + 250, "y0": bunk_y[0],
                          "y1": bunk_y[1], "z0": 0, "z1": 100})
            markers.append({"id": "CellAssign_" + cid, "type": "CellAssignment", "x": x0 + 150,
                            "y": (bunk_y[0] + bunk_y[1]) / 2 + (-90 if row["side"] == "north" else 90), "z": 0})
            markers.append({"id": "Lockdown_" + cid, "type": "Lockdown", "x": cx, "y": inside, "z": 0})
            markers.append({"id": "Inspection_" + cid, "type": "Inspection", "x": cx, "y": ins_front, "z": 0})
    for r in rooms:
        ri = info.get(r["id"])
        if ri:
            r["area"] = ri["area"]
            r["sign"] = ri["sign"]
    return {"rooms": rooms, "openings": openings, "boxes": boxes, "markers": markers, "cells": cells}


def locate(rooms, x, y, feet_z):
    """Return the room dict containing (x, y) at the given foot height, or None."""
    best = None
    for r in rooms:
        if r["x0"] <= x <= r["x1"] and r["y0"] <= y <= r["y1"]:
            if r["z"] - 8 <= feet_z <= r["z"] + r["ceil"]:
                if best is None or r["z"] > best["z"]:
                    best = r
    return best
