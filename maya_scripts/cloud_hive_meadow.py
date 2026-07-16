r"""
Cloud-Hive Meadow
Maya Python visual prototype.

Run inside Maya Script Editor:
exec(open(r"C:\Users\YUN\Desktop\CloudHiveMeadow_Maya\maya_scripts\cloud_hive_meadow.py").read())
"""

from __future__ import division

import math
import random
from collections import deque

import maya.cmds as cmds


WINDOW_NAME = "CloudHiveMeadowUI"
ROOT_GROUP = "CloudHiveMeadow_GRP"

CELL_DIRECTIONS = (
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, -1),
    (-1, 1),
)


DEFAULT_SETTINGS = {
    "hive_radius": 5,
    "cell_size": 1.0,
    "height_variation": 1.0,
    "seed": 18,
    "cloud_count": 5,
    "bee_count": 10,
    "resource_count": 28,
    "honey_rain_count": 90,
    "wind_x": 0.6,
    "wind_z": -0.25,
    "show_paths": True,
    "show_wrong_cells": True,
}


def reset_scene():
    """Delete the previous generated group."""
    if cmds.objExists(ROOT_GROUP):
        cmds.delete(ROOT_GROUP)
    root = cmds.group(empty=True, name=ROOT_GROUP)
    return root


def ensure_material(name, color, transparency=0.0, specular=0.2):
    if cmds.objExists(name):
        return name
    mat = cmds.shadingNode("lambert", asShader=True, name=name)
    cmds.setAttr(mat + ".color", color[0], color[1], color[2], type="double3")
    cmds.setAttr(mat + ".transparency", transparency, transparency, transparency, type="double3")
    if cmds.objExists(mat + ".diffuse"):
        cmds.setAttr(mat + ".diffuse", 0.78)
    return mat


def assign_material(node, mat):
    try:
        cmds.select(node, replace=True)
        cmds.hyperShade(assign=mat)
    except Exception as exc:
        print("Material assignment skipped for %s: %s" % (node, exc))
    finally:
        cmds.select(clear=True)


def create_materials():
    return {
        "ground": ensure_material("chm_ground_green_MAT", (0.23, 0.46, 0.24)),
        "empty": ensure_material("chm_empty_wax_MAT", (0.86, 0.68, 0.32)),
        "honey": ensure_material("chm_honey_gold_MAT", (1.0, 0.58, 0.05), 0.08),
        "pollen": ensure_material("chm_pollen_orange_MAT", (1.0, 0.38, 0.08)),
        "capped": ensure_material("chm_capped_cream_MAT", (0.95, 0.82, 0.54)),
        "wrong": ensure_material("chm_wrong_red_MAT", (1.0, 0.12, 0.08)),
        "cloud": ensure_material("chm_cloud_soft_MAT", (0.82, 0.9, 1.0), 0.35),
        "bee": ensure_material("chm_bee_yellow_MAT", (1.0, 0.76, 0.05)),
        "bee_stripe": ensure_material("chm_bee_stripe_MAT", (0.05, 0.035, 0.02)),
        "nectar": ensure_material("chm_nectar_drop_MAT", (1.0, 0.72, 0.03), 0.05),
        "pollen_drop": ensure_material("chm_pollen_drop_MAT", (1.0, 0.42, 0.02)),
        "path": ensure_material("chm_path_gold_MAT", (1.0, 0.95, 0.25)),
        "wax_highlight": ensure_material("chm_wax_highlight_MAT", (0.98, 0.78, 0.38)),
        "hive_shadow": ensure_material("chm_hive_shadow_MAT", (0.36, 0.19, 0.04)),
    }


def axial_to_world(q, r, cell_size):
    x = cell_size * math.sqrt(3.0) * (q + r * 0.5)
    z = cell_size * 1.5 * r
    return x, z


def generate_hex_grid(radius, cell_size):
    cells = {}
    idx = 0
    for q in range(-radius, radius + 1):
        r_min = max(-radius, -q - radius)
        r_max = min(radius, -q + radius)
        for r in range(r_min, r_max + 1):
            x, z = axial_to_world(q, r, cell_size)
            cells[(q, r)] = {
                "id": idx,
                "q": q,
                "r": r,
                "position": (x, z),
                "type": "empty",
                "height": 0.25,
                "neighbors": [],
                "node": None,
            }
            idx += 1
    for key, cell in cells.items():
        q, r = key
        for dq, dr in CELL_DIRECTIONS:
            neighbor_key = (q + dq, r + dr)
            if neighbor_key in cells:
                cell["neighbors"].append(neighbor_key)
    return cells


def assign_cell_types(cells, rng):
    weights = (
        ("honey", 0.34),
        ("pollen", 0.24),
        ("empty", 0.30),
        ("capped", 0.12),
    )
    for key in sorted(cells.keys()):
        roll = rng.random()
        total = 0.0
        selected = "empty"
        for cell_type, weight in weights:
            total += weight
            if roll <= total:
                selected = cell_type
                break
        cells[key]["type"] = selected


def create_cell_geometry(cell, settings, mats, parent):
    cell_size = settings["cell_size"]
    height_base = {
        "honey": 0.55,
        "pollen": 0.42,
        "empty": 0.24,
        "capped": 0.35,
    }[cell["type"]]
    noise = random.uniform(0.0, settings["height_variation"]) * 0.35
    height = height_base + noise
    cell["height"] = height
    x, z = cell["position"]
    node = cmds.polyCylinder(
        radius=cell_size * 0.96,
        height=height,
        subdivisionsX=6,
        subdivisionsY=1,
        axis=(0, 1, 0),
        name="chm_cell_%s_%s_%s" % (cell["type"], cell["q"], cell["r"]),
    )[0]
    cmds.move(x, height * 0.5, z, node)
    cmds.rotate(0, 30, 0, node, relative=True)
    assign_material(node, mats[cell["type"]])
    cmds.parent(node, parent)
    cell["node"] = node
    create_wax_rim(cell, settings, mats, parent)

    if cell["type"] == "honey":
        create_honey_fill(cell, mats, parent)
    elif cell["type"] == "pollen":
        create_pollen_grains(cell, mats, parent)
    elif cell["type"] == "capped":
        create_cap(cell, mats, parent)
    return node


def create_wax_rim(cell, settings, mats, parent):
    cell_size = settings["cell_size"]
    x, z = cell["position"]
    rim = cmds.polyCylinder(
        radius=cell_size * 0.78,
        height=0.08,
        subdivisionsX=6,
        subdivisionsY=1,
        name="chm_wax_rim_%s_%s" % (cell["q"], cell["r"]),
    )[0]
    cmds.move(x, cell["height"] + 0.05, z, rim)
    cmds.rotate(0, 30, 0, rim, relative=True)
    assign_material(rim, mats["wax_highlight"])
    cmds.parent(rim, parent)

    if random.random() < 0.28:
        for _ in range(random.randint(1, 3)):
            angle = random.uniform(0.0, math.pi * 2.0)
            lump = cmds.polySphere(radius=random.uniform(0.05, 0.11), subdivisionsX=8, subdivisionsY=6, name="chm_wax_lump")[0]
            cmds.move(
                x + math.cos(angle) * random.uniform(cell_size * 0.62, cell_size * 0.86),
                cell["height"] + random.uniform(0.02, 0.16),
                z + math.sin(angle) * random.uniform(cell_size * 0.62, cell_size * 0.86),
                lump,
            )
            assign_material(lump, mats["wax_highlight"])
            cmds.parent(lump, parent)


def create_honey_fill(cell, mats, parent):
    x, z = cell["position"]
    fill = cmds.polyCylinder(
        radius=0.56,
        height=0.08,
        subdivisionsX=6,
        name="chm_honey_fill_%s_%s" % (cell["q"], cell["r"]),
    )[0]
    cmds.move(x, cell["height"] + 0.05, z, fill)
    cmds.rotate(0, 30, 0, fill, relative=True)
    assign_material(fill, mats["nectar"])
    cmds.parent(fill, parent)


def create_pollen_grains(cell, mats, parent):
    x, z = cell["position"]
    for i in range(3):
        grain = cmds.polySphere(radius=0.08, subdivisionsX=8, subdivisionsY=6, name="chm_pollen_grain")[0]
        cmds.move(
            x + random.uniform(-0.28, 0.28),
            cell["height"] + 0.08 + random.uniform(0.0, 0.06),
            z + random.uniform(-0.28, 0.28),
            grain,
        )
        assign_material(grain, mats["pollen_drop"])
        cmds.parent(grain, parent)


def create_cap(cell, mats, parent):
    x, z = cell["position"]
    cap = cmds.polyCylinder(radius=0.68, height=0.12, subdivisionsX=6, name="chm_wax_cap")[0]
    cmds.move(x, cell["height"] + 0.06, z, cap)
    cmds.rotate(0, 30, 0, cap, relative=True)
    assign_material(cap, mats["capped"])
    cmds.parent(cap, parent)


def create_honeycomb(cells, settings, mats, parent):
    group = cmds.group(empty=True, name="HoneycombCells_GRP", parent=parent)
    for cell in cells.values():
        create_cell_geometry(cell, settings, mats, group)
    return group


def create_ground(settings, mats, parent):
    size = settings["hive_radius"] * settings["cell_size"] * 4.2
    ground = cmds.polyPlane(width=size, height=size, subdivisionsX=1, subdivisionsY=1, name="chm_meadow_ground")[0]
    cmds.move(0, -0.02, 0, ground)
    assign_material(ground, mats["ground"])
    cmds.parent(ground, parent)
    return ground


def create_central_hive_marker(cells, mats, parent):
    center_key = nearest_cell(cells, 0, 0)
    center = cells[center_key]
    x, z = center["position"]
    group = cmds.group(empty=True, name="CentralHivePlaceholder_GRP", parent=parent)
    mound = cmds.polySphere(radius=0.78, subdivisionsX=18, subdivisionsY=10, name="chm_central_wax_mound")[0]
    cmds.scale(1.45, 0.52, 1.05, mound)
    cmds.move(x, center["height"] + 0.28, z, mound)
    assign_material(mound, mats["wax_highlight"])
    cmds.parent(mound, group)

    entrance = cmds.polyCylinder(radius=0.22, height=0.08, subdivisionsX=18, name="chm_hive_entrance")[0]
    cmds.rotate(90, 0, 0, entrance)
    cmds.scale(1.0, 0.58, 1.0, entrance)
    cmds.move(x + 0.58, center["height"] + 0.28, z - 0.14, entrance)
    assign_material(entrance, mats["hive_shadow"])
    cmds.parent(entrance, group)

    for i in range(10):
        lump = cmds.polySphere(radius=random.uniform(0.08, 0.18), subdivisionsX=8, subdivisionsY=6, name="chm_mound_lump")[0]
        angle = random.uniform(0.0, math.pi * 2.0)
        dist = random.uniform(0.55, 1.1)
        cmds.move(x + math.cos(angle) * dist, center["height"] + random.uniform(0.12, 0.45), z + math.sin(angle) * dist, lump)
        assign_material(lump, mats["wax_highlight"])
        cmds.parent(lump, group)
    return group


def create_cloud_cluster(index, position, mats, parent, rng):
    group = cmds.group(empty=True, name="Cloud_%02d_GRP" % index, parent=parent)
    for i in range(rng.randint(12, 18)):
        sphere = cmds.polySphere(
            radius=rng.uniform(0.28, 0.62),
            subdivisionsX=12,
            subdivisionsY=8,
            name="chm_cloud_particle",
        )[0]
        cmds.move(
            position[0] + rng.uniform(-1.1, 1.1),
            position[1] + rng.uniform(-0.25, 0.32),
            position[2] + rng.uniform(-0.8, 0.8),
            sphere,
        )
        assign_material(sphere, mats["cloud"])
        cmds.parent(sphere, group)
    return group


def create_clouds(settings, mats, parent, rng):
    group = cmds.group(empty=True, name="CloudParticleGroups_GRP", parent=parent)
    clouds = []
    radius = settings["hive_radius"] * settings["cell_size"] * 1.65
    for i in range(settings["cloud_count"]):
        angle = (math.pi * 2.0 / max(1, settings["cloud_count"])) * i + rng.uniform(-0.35, 0.35)
        distance = rng.uniform(radius * 0.25, radius)
        position = (
            math.cos(angle) * distance,
            rng.uniform(5.2, 7.4),
            math.sin(angle) * distance,
        )
        node = create_cloud_cluster(i, position, mats, group, rng)
        clouds.append({"id": i, "position": position, "node": node})
    return clouds


def create_honey_rain(clouds, settings, mats, parent, rng):
    group = cmds.group(empty=True, name="HoneyRain_GRP", parent=parent)
    if not clouds:
        return group
    for i in range(settings["honey_rain_count"]):
        cloud = rng.choice(clouds)
        cx, cy, cz = cloud["position"]
        x = cx + rng.uniform(-1.5, 1.5) + settings["wind_x"] * rng.uniform(0.0, 0.65)
        z = cz + rng.uniform(-1.0, 1.0) + settings["wind_z"] * rng.uniform(0.0, 0.65)
        top = cy - rng.uniform(0.45, 0.9)
        bottom = rng.uniform(1.4, 4.6)
        if rng.random() < 0.18:
            curve = cmds.curve(
                degree=1,
                point=[(x, top, z), (x + rng.uniform(-0.05, 0.05), bottom, z + rng.uniform(-0.05, 0.05))],
                name="chm_hanging_nectar",
            )
            shape = cmds.listRelatives(curve, shapes=True)[0]
            cmds.setAttr(shape + ".lineWidth", rng.uniform(2.0, 4.0))
            assign_material(curve, mats["nectar"])
            cmds.parent(curve, group)
            drop = cmds.polySphere(radius=rng.uniform(0.06, 0.13), subdivisionsX=10, subdivisionsY=8, name="chm_hanging_nectar_drop")[0]
            cmds.scale(0.8, 1.35, 0.8, drop)
            cmds.move(x, bottom, z, drop)
            assign_material(drop, mats["nectar"])
            cmds.parent(drop, group)
        else:
            speck = cmds.polySphere(radius=rng.uniform(0.025, 0.055), subdivisionsX=6, subdivisionsY=4, name="chm_honey_speck")[0]
            cmds.move(x, rng.uniform(bottom, top), z, speck)
            assign_material(speck, mats["nectar"])
            cmds.parent(speck, group)
    return group


def nearest_cell(cells, x, z):
    best_key = None
    best_dist = None
    for key, cell in cells.items():
        cx, cz = cell["position"]
        dist = (cx - x) ** 2 + (cz - z) ** 2
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_key = key
    return best_key


def bfs_find_path(cells, start_key, target_type):
    visited = set([start_key])
    queue = deque([(start_key, [start_key])])
    while queue:
        key, path = queue.popleft()
        cell = cells[key]
        if key != start_key and cell["type"] == target_type:
            return path
        for neighbor in cell["neighbors"]:
            if neighbor in visited:
                continue
            if cells[neighbor]["type"] == "capped":
                continue
            visited.add(neighbor)
            queue.append((neighbor, path + [neighbor]))
    return []


def make_curve_from_points(name, points, mats, parent):
    if len(points) < 2:
        return None
    curve = cmds.curve(degree=1, point=points, name=name)
    shape = cmds.listRelatives(curve, shapes=True)[0]
    cmds.setAttr(shape + ".lineWidth", 4)
    assign_material(curve, mats["path"])
    cmds.parent(curve, parent)
    return curve


def create_resource_drop(index, drop_type, cloud, cells, settings, mats, parent, rng):
    wind_x = settings["wind_x"]
    wind_z = settings["wind_z"]
    start = cloud["position"]
    x = start[0] + rng.uniform(-2.2, 2.2) + wind_x
    z = start[2] + rng.uniform(-2.2, 2.2) + wind_z
    cell_key = nearest_cell(cells, x, z)
    cell = cells[cell_key]
    cx, cz = cell["position"]
    y = cell["height"] + rng.uniform(0.18, 0.45)
    node = cmds.polySphere(radius=0.12 if drop_type == "nectar" else 0.10, subdivisionsX=10, subdivisionsY=8, name="chm_%s_drop" % drop_type)[0]
    cmds.move(cx + rng.uniform(-0.26, 0.26), y, cz + rng.uniform(-0.26, 0.26), node)
    assign_material(node, mats["nectar"] if drop_type == "nectar" else mats["pollen_drop"])
    cmds.parent(node, parent)

    target_type = "honey" if drop_type == "nectar" else "pollen"
    is_wrong = cell["type"] != target_type
    if is_wrong and settings["show_wrong_cells"]:
        assign_material(cell["node"], mats["wrong"])
    return {
        "id": index,
        "type": drop_type,
        "cell_key": cell_key,
        "target_type": target_type,
        "is_wrong": is_wrong,
        "node": node,
    }


def create_resource_drops(clouds, cells, settings, mats, parent, rng):
    group = cmds.group(empty=True, name="ResourceDrops_GRP", parent=parent)
    drops = []
    if not clouds:
        return drops
    for i in range(settings["resource_count"]):
        drop_type = "nectar" if rng.random() < 0.58 else "pollen"
        cloud = rng.choice(clouds)
        drops.append(create_resource_drop(i, drop_type, cloud, cells, settings, mats, group, rng))
    return drops


def create_bfs_paths(drops, cells, mats, parent):
    group = cmds.group(empty=True, name="BFSPaths_GRP", parent=parent)
    path_count = 0
    for drop in drops:
        if not drop["is_wrong"]:
            continue
        path = bfs_find_path(cells, drop["cell_key"], drop["target_type"])
        if not path:
            continue
        points = []
        for key in path:
            cell = cells[key]
            x, z = cell["position"]
            points.append((x, cell["height"] + 0.35, z))
        make_curve_from_points("chm_bfs_path_%02d" % path_count, points, mats, group)
        path_count += 1
        if path_count >= 5:
            break
    return group


def create_bee_placeholder(index, start_pos, end_pos, mats, parent):
    group = cmds.group(empty=True, name="Bee_%02d_GRP" % index, parent=parent)
    body = cmds.polyCube(width=0.28, height=0.18, depth=0.62, name="chm_bee_body")[0]
    stripe = cmds.polyCube(width=0.30, height=0.19, depth=0.08, name="chm_bee_stripe")[0]
    cmds.move(0, 0, 0, body)
    cmds.move(0, 0.005, -0.08, stripe)
    assign_material(body, mats["bee"])
    assign_material(stripe, mats["bee_stripe"])
    cmds.parent(body, group)
    cmds.parent(stripe, group)
    cmds.move(start_pos[0], start_pos[1], start_pos[2], group)

    mid = (
        (start_pos[0] + end_pos[0]) * 0.5,
        max(start_pos[1], end_pos[1]) + 1.2,
        (start_pos[2] + end_pos[2]) * 0.5,
    )
    flight = cmds.curve(degree=2, point=[start_pos, mid, end_pos], name="chm_bee_flight_%02d" % index)
    shape = cmds.listRelatives(flight, shapes=True)[0]
    cmds.setAttr(shape + ".lineWidth", 2)
    assign_material(flight, mats["path"])
    cmds.parent(flight, parent)

    start_frame = 1 + index * 5
    end_frame = start_frame + 80
    cmds.setKeyframe(group, attribute="translateX", time=start_frame, value=start_pos[0])
    cmds.setKeyframe(group, attribute="translateY", time=start_frame, value=start_pos[1])
    cmds.setKeyframe(group, attribute="translateZ", time=start_frame, value=start_pos[2])
    cmds.setKeyframe(group, attribute="translateX", time=end_frame, value=end_pos[0])
    cmds.setKeyframe(group, attribute="translateY", time=end_frame, value=end_pos[1])
    cmds.setKeyframe(group, attribute="translateZ", time=end_frame, value=end_pos[2])
    return group


def create_bees(clouds, cells, settings, mats, parent, rng):
    group = cmds.group(empty=True, name="BeePlaceholders_GRP", parent=parent)
    entry_key = nearest_cell(cells, 0, 0)
    entry_cell = cells[entry_key]
    sx, sz = entry_cell["position"]
    if not clouds:
        return group
    for i in range(settings["bee_count"]):
        cloud = rng.choice(clouds)
        start_pos = (sx + rng.uniform(-0.6, 0.6), entry_cell["height"] + 0.8, sz + rng.uniform(-0.6, 0.6))
        end_pos = (
            cloud["position"][0] + rng.uniform(-0.8, 0.8),
            cloud["position"][1] + rng.uniform(-0.4, 0.4),
            cloud["position"][2] + rng.uniform(-0.8, 0.8),
        )
        create_bee_placeholder(i, start_pos, end_pos, mats, group)
    return group


def setup_camera_and_lights(settings):
    cmds.currentTime(1)
    cmds.playbackOptions(minTime=1, maxTime=120)
    if not cmds.objExists("chm_key_light"):
        light = cmds.directionalLight(name="chm_key_light", intensity=1.2)
        cmds.rotate(-45, 35, 0, light)
    if not cmds.objExists("chm_fill_light"):
        ambient = cmds.ambientLight(name="chm_fill_light", intensity=0.35)
        cmds.move(0, 6, 0, ambient)
    camera = "persp"
    distance = settings["hive_radius"] * settings["cell_size"] * 5.0
    cmds.setAttr(camera + ".translateX", distance * 0.75)
    cmds.setAttr(camera + ".translateY", distance * 0.58)
    cmds.setAttr(camera + ".translateZ", distance * 0.92)
    cmds.setAttr(camera + ".rotateX", -35)
    cmds.setAttr(camera + ".rotateY", 42)
    cmds.setAttr(camera + ".rotateZ", 0)


def build_scene(settings=None):
    settings = dict(DEFAULT_SETTINGS if settings is None else settings)
    rng = random.Random(settings["seed"])
    random.seed(settings["seed"])
    root = reset_scene()
    mats = create_materials()
    cells = generate_hex_grid(settings["hive_radius"], settings["cell_size"])
    assign_cell_types(cells, rng)
    create_ground(settings, mats, root)
    create_honeycomb(cells, settings, mats, root)
    create_central_hive_marker(cells, mats, root)
    clouds = create_clouds(settings, mats, root, rng)
    create_honey_rain(clouds, settings, mats, root, rng)
    drops = create_resource_drops(clouds, cells, settings, mats, root, rng)
    if settings["show_paths"]:
        create_bfs_paths(drops, cells, mats, root)
    create_bees(clouds, cells, settings, mats, root, rng)
    setup_camera_and_lights(settings)
    cmds.select(root)
    print("Cloud-Hive Meadow generated: %d cells, %d clouds, %d drops." % (len(cells), len(clouds), len(drops)))


def read_ui_settings():
    return {
        "hive_radius": cmds.intSliderGrp("chm_hive_radius", query=True, value=True),
        "cell_size": cmds.floatSliderGrp("chm_cell_size", query=True, value=True),
        "height_variation": cmds.floatSliderGrp("chm_height_var", query=True, value=True),
        "seed": cmds.intSliderGrp("chm_seed", query=True, value=True),
        "cloud_count": cmds.intSliderGrp("chm_cloud_count", query=True, value=True),
        "bee_count": cmds.intSliderGrp("chm_bee_count", query=True, value=True),
        "resource_count": cmds.intSliderGrp("chm_resource_count", query=True, value=True),
        "honey_rain_count": cmds.intSliderGrp("chm_honey_rain_count", query=True, value=True),
        "wind_x": cmds.floatSliderGrp("chm_wind_x", query=True, value=True),
        "wind_z": cmds.floatSliderGrp("chm_wind_z", query=True, value=True),
        "show_paths": cmds.checkBox("chm_show_paths", query=True, value=True),
        "show_wrong_cells": cmds.checkBox("chm_show_wrong_cells", query=True, value=True),
    }


def create_ui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)
    cmds.window(WINDOW_NAME, title="Cloud-Hive Meadow Generator", widthHeight=(360, 520), sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=("both", 10))
    cmds.text(label="Cloud-Hive Meadow", align="center", height=26)
    cmds.separator(height=8, style="in")
    cmds.intSliderGrp("chm_hive_radius", label="Honeycomb Size", field=True, minValue=2, maxValue=9, value=DEFAULT_SETTINGS["hive_radius"])
    cmds.floatSliderGrp("chm_cell_size", label="Cell Size", field=True, minValue=0.5, maxValue=1.8, value=DEFAULT_SETTINGS["cell_size"])
    cmds.floatSliderGrp("chm_height_var", label="Height Variation", field=True, minValue=0.0, maxValue=2.0, value=DEFAULT_SETTINGS["height_variation"])
    cmds.intSliderGrp("chm_seed", label="Random Seed", field=True, minValue=1, maxValue=999, value=DEFAULT_SETTINGS["seed"])
    cmds.separator(height=8, style="in")
    cmds.intSliderGrp("chm_cloud_count", label="Cloud Count", field=True, minValue=1, maxValue=12, value=DEFAULT_SETTINGS["cloud_count"])
    cmds.intSliderGrp("chm_resource_count", label="Resource Drops", field=True, minValue=0, maxValue=120, value=DEFAULT_SETTINGS["resource_count"])
    cmds.intSliderGrp("chm_honey_rain_count", label="Honey Rain", field=True, minValue=0, maxValue=240, value=DEFAULT_SETTINGS["honey_rain_count"])
    cmds.floatSliderGrp("chm_wind_x", label="Wind X", field=True, minValue=-3.0, maxValue=3.0, value=DEFAULT_SETTINGS["wind_x"])
    cmds.floatSliderGrp("chm_wind_z", label="Wind Z", field=True, minValue=-3.0, maxValue=3.0, value=DEFAULT_SETTINGS["wind_z"])
    cmds.separator(height=8, style="in")
    cmds.intSliderGrp("chm_bee_count", label="Bee Count", field=True, minValue=0, maxValue=40, value=DEFAULT_SETTINGS["bee_count"])
    cmds.checkBox("chm_show_paths", label="Show BFS Paths", value=DEFAULT_SETTINGS["show_paths"])
    cmds.checkBox("chm_show_wrong_cells", label="Highlight Wrong Cells", value=DEFAULT_SETTINGS["show_wrong_cells"])
    cmds.separator(height=10, style="in")
    cmds.button(label="Generate / Regenerate Scene", height=34, command=lambda *_: build_scene(read_ui_settings()))
    cmds.button(label="Reset Generated Scene", height=28, command=lambda *_: reset_scene())
    cmds.showWindow(WINDOW_NAME)
    build_scene(DEFAULT_SETTINGS)


create_ui()
