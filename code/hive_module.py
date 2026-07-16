"""Honeycomb grid and Maya geometry helpers for Cloud-Hive Meadow."""

import math
import random
from collections import deque


def axial_to_world(q, r, cell_size):
    """Convert axial hex coordinates to a flat Maya/world position.

    Parameters:
        q (int): Axial q coordinate.
        r (int): Axial r coordinate.
        cell_size (float): Radius of one hex cell.

    Returns:
        list[float]: World-space position as [x, y, z].
    """
    # Axial coordinates describe a hex grid with two axes, q and r.
    # For a pointy-top hex layout on Maya's XZ ground plane:
    # - q moves mostly along world X.
    # - r moves diagonally, shifting both X and Z.
    # - y stays 0 so the honeycomb remains flat on the ground plane.
    x = cell_size * math.sqrt(3.0) * (q + (r / 2.0))
    y = 0.0
    z = cell_size * 1.5 * r
    return [x, y, z]


def generate_hex_grid(size, cell_size):
    """Generate a roughly circular axial-coordinate honeycomb grid.

    Parameters:
        size (int): Hex radius of the grid. A size of 0 creates one cell.
        cell_size (float): Radius of one hex cell in world units.

    Returns:
        list[dict]: Cell dictionaries with default values and empty neighbors.
    """
    if size < 0:
        raise ValueError("size must be 0 or greater")
    if cell_size <= 0:
        raise ValueError("cell_size must be greater than 0")

    cells = []

    # A circular-looking hex grid includes axial coordinates where
    # q, r, and the implicit third cube coordinate (-q-r) are all within
    # the requested radius.
    for q in range(-size, size + 1):
        r_min = max(-size, -q - size)
        r_max = min(size, -q + size)
        for r in range(r_min, r_max + 1):
            cell_id = "cell_q{0}_r{1}".format(q, r)
            cells.append(
                {
                    "id": cell_id,
                    "q": q,
                    "r": r,
                    "position": axial_to_world(q, r, cell_size),
                    "type": "empty",
                    "nectar": 0.0,
                    "pollen": 0.0,
                    "capacity": 1.0,
                    "neighbors": [],
                    "is_blocked": False,
                    "maya_object": None,
                }
            )

    return cells


def get_cell_map(cells):
    """Create a lookup table from cell id to cell dictionary.

    Parameters:
        cells (list[dict]): Honeycomb cell dictionaries.

    Returns:
        dict: Mapping of cell id strings to cell dictionaries.
    """
    return {cell["id"]: cell for cell in cells}


def get_cell_by_id(cells, cell_id):
    """Find a cell dictionary by id.

    Parameters:
        cells (list[dict]): Honeycomb cell dictionaries.
        cell_id (str): Cell id to find.

    Returns:
        dict | None: Matching cell dictionary, or None if it is not found.
    """
    for cell in cells:
        if cell["id"] == cell_id:
            return cell
    return None


def calculate_neighbors(cells):
    """Fill each cell's neighbor list using axial coordinate directions.

    Parameters:
        cells (list[dict]): Honeycomb cell dictionaries.

    Returns:
        list[dict]: The same cells list with updated neighbor ids.
    """
    coordinate_to_id = {(cell["q"], cell["r"]): cell["id"] for cell in cells}
    axial_neighbor_directions = [
        (1, 0),
        (-1, 0),
        (0, 1),
        (0, -1),
        (1, -1),
        (-1, 1),
    ]

    for cell in cells:
        neighbors = []
        q = cell["q"]
        r = cell["r"]

        for dq, dr in axial_neighbor_directions:
            neighbor_id = coordinate_to_id.get((q + dq, r + dr))
            if neighbor_id is not None:
                neighbors.append(neighbor_id)

        cell["neighbors"] = neighbors

    return cells


def assign_cell_types(cells, honey_ratio, pollen_ratio, empty_ratio, capped_ratio, seed):
    """Assign honeycomb cell types from normalized ratios.

    Parameters:
        cells (list[dict]): Honeycomb cell dictionaries.
        honey_ratio (float): Desired share of honey storage cells.
        pollen_ratio (float): Desired share of pollen storage cells.
        empty_ratio (float): Desired share of empty cells.
        capped_ratio (float): Desired share of capped blocked cells.
        seed (int): Random seed for deterministic assignment.

    Returns:
        list[dict]: The same cells list with updated type and blocked state.
    """
    cell_types = ["honey", "pollen", "empty", "capped"]
    raw_ratios = [honey_ratio, pollen_ratio, empty_ratio, capped_ratio]
    safe_ratios = []

    for ratio in raw_ratios:
        try:
            numeric_ratio = float(ratio)
        except (TypeError, ValueError):
            numeric_ratio = 0.0
        safe_ratios.append(max(0.0, numeric_ratio))

    ratio_total = sum(safe_ratios)
    if ratio_total <= 0.0:
        safe_ratios = [0.0, 0.0, 1.0, 0.0]
        ratio_total = 1.0

    normalized_ratios = [ratio / ratio_total for ratio in safe_ratios]
    cell_count = len(cells)
    raw_counts = [ratio * cell_count for ratio in normalized_ratios]
    counts = [int(math.floor(value)) for value in raw_counts]
    remaining = cell_count - sum(counts)

    # Distribute leftover cells to the largest fractional remainders so the
    # final counts stay close to the requested ratios and always sum exactly.
    remainder_order = sorted(
        range(len(cell_types)),
        key=lambda index: (raw_counts[index] - counts[index], -index),
        reverse=True,
    )
    for index in remainder_order[:remaining]:
        counts[index] += 1

    assignments = []
    for cell_type, count in zip(cell_types, counts):
        assignments.extend([cell_type] * count)

    rng = random.Random(seed)
    shuffled_indices = list(range(cell_count))
    rng.shuffle(shuffled_indices)

    for cell_index, cell_type in zip(shuffled_indices, assignments):
        cell = cells[cell_index]
        cell["type"] = cell_type
        cell["is_blocked"] = cell_type == "capped"

    return cells


def find_nearest_storage_cell(cells, start_cell_id, target_type):
    """Find the nearest non-blocked cell matching a target storage type.

    Parameters:
        cells (list[dict]): Honeycomb cell dictionaries.
        start_cell_id (str): Cell id where the search starts.
        target_type (str): Desired destination type, such as "honey" or "pollen".

    Returns:
        str | None: Nearest matching cell id, or None if no cell is reachable.
    """
    path = bfs_find_path(cells, start_cell_id, target_type)
    if not path:
        return None
    return path[-1]


def bfs_find_path(cells, start_cell_id, target_type):
    """Find the shortest path to the nearest non-blocked target cell with BFS.

    Parameters:
        cells (list[dict]): Honeycomb cell dictionaries with neighbor ids.
        start_cell_id (str): Cell id where the search starts.
        target_type (str): Desired destination type, such as "honey" or "pollen".

    Returns:
        list[str]: Ordered cell ids from start to target, or [] if not found.
    """
    cell_map = get_cell_map(cells)
    start_cell = cell_map.get(start_cell_id)
    if start_cell is None or start_cell.get("is_blocked"):
        return []

    # Breadth-first search explores the graph in distance order.
    # The first matching target found is therefore the shortest reachable path.
    queue = deque([(start_cell_id, [start_cell_id])])
    visited = {start_cell_id}

    while queue:
        current_cell_id, path = queue.popleft()
        current_cell = cell_map[current_cell_id]

        if (
            not current_cell.get("is_blocked")
            and current_cell.get("type") == target_type
        ):
            return path

        for neighbor_id in current_cell.get("neighbors", []):
            if neighbor_id in visited:
                continue

            neighbor_cell = cell_map.get(neighbor_id)
            if neighbor_cell is None or neighbor_cell.get("is_blocked"):
                continue

            visited.add(neighbor_id)
            queue.append((neighbor_id, path + [neighbor_id]))

    return []


def _create_maya_material(cmds, material_name, color):
    """Create or reuse a Maya lambert material.

    Parameters:
        cmds: Imported maya.cmds module.
        material_name (str): Name of the material node.
        color (tuple[float, float, float]): RGB color in 0..1 range.

    Returns:
        str: Maya material node name.
    """
    if cmds.objExists(material_name):
        return material_name

    material = cmds.shadingNode("lambert", asShader=True, name=material_name)
    cmds.setAttr(
        material + ".color",
        color[0],
        color[1],
        color[2],
        type="double3",
    )
    return material


def _assign_maya_material(cmds, node, material):
    """Assign a Maya material to an object.

    Parameters:
        cmds: Imported maya.cmds module.
        node (str): Maya object name.
        material (str): Maya material node name.

    Returns:
        None.
    """
    cmds.select(node, replace=True)
    cmds.hyperShade(assign=material)
    cmds.select(clear=True)


def create_honeycomb_geometry(cells, cell_size, cell_depth):
    """Create Maya hexagonal prism geometry for the honeycomb cells.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so the module can still be imported and tested outside Autodesk Maya.

    Parameters:
        cells (list[dict]): Honeycomb cell dictionaries.
        cell_size (float): Radius of each hexagonal prism.
        cell_depth (float): Height/depth of each hexagonal prism.

    Returns:
        list[dict]: The same cells list with each cell's maya_object updated.
    """
    import maya.cmds as cmds

    if cell_size <= 0:
        raise ValueError("cell_size must be greater than 0")
    if cell_depth <= 0:
        raise ValueError("cell_depth must be greater than 0")

    group_name = "CloudHive_Honeycomb_GRP"
    if not cmds.objExists(group_name):
        cmds.group(empty=True, name=group_name)

    material_by_type = {
        "honey": _create_maya_material(cmds, "chm_honey_amber_MAT", (1.0, 0.58, 0.08)),
        "pollen": _create_maya_material(cmds, "chm_pollen_yellow_MAT", (1.0, 0.78, 0.12)),
        "empty": _create_maya_material(cmds, "chm_empty_wax_MAT", (0.92, 0.78, 0.48)),
        "capped": _create_maya_material(cmds, "chm_capped_beige_MAT", (0.72, 0.60, 0.42)),
    }

    for cell in cells:
        x, _, z = cell["position"]
        object_name = "{0}_HEX".format(cell["id"])
        transform, _shape = cmds.polyCylinder(
            radius=cell_size,
            height=cell_depth,
            subdivisionsX=6,
            subdivisionsY=1,
            subdivisionsZ=0,
            axis=(0, 1, 0),
            name=object_name,
        )
        cmds.xform(transform, translation=(x, cell_depth * 0.5, z), worldSpace=True)
        cmds.parent(transform, group_name)

        material = material_by_type.get(cell.get("type"), material_by_type["empty"])
        _assign_maya_material(cmds, transform, material)

        cell["maya_object"] = transform

    return cells


def highlight_path(path, cells):
    """Create Maya visual markers and a curve for a BFS path.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so the module can still be imported and tested outside Autodesk Maya.

    Parameters:
        path (list[str]): Ordered cell ids forming a BFS path.
        cells (list[dict]): Honeycomb cell dictionaries.

    Returns:
        list[str]: Maya object names created for the path visualization.
    """
    import maya.cmds as cmds

    cell_map = get_cell_map(cells)
    path_points = []
    created_objects = []

    for cell_id in path:
        cell = cell_map.get(cell_id)
        if cell is None:
            continue
        x, y, z = cell["position"]
        path_points.append((x, y + 0.25, z))

    if not path_points:
        return created_objects

    group_name = "CloudHive_PathHighlight_GRP"
    if not cmds.objExists(group_name):
        cmds.group(empty=True, name=group_name)

    path_material = _create_maya_material(cmds, "chm_bfs_path_blue_MAT", (0.12, 0.45, 1.0))

    if len(path_points) > 1:
        curve_name = cmds.curve(d=1, p=path_points, name="chm_bfs_path_CRV")
        cmds.parent(curve_name, group_name)
        created_objects.append(curve_name)

    for index, point in enumerate(path_points):
        marker_name = "chm_bfs_path_marker_{0:02d}".format(index)
        marker, _shape = cmds.polySphere(radius=0.12, name=marker_name)
        cmds.xform(marker, translation=point, worldSpace=True)
        cmds.parent(marker, group_name)
        _assign_maya_material(cmds, marker, path_material)
        created_objects.append(marker)

    return created_objects


if __name__ == "__main__":
    cells = generate_hex_grid(size=3, cell_size=1.0)
    calculate_neighbors(cells)
    assign_cell_types(
        cells,
        honey_ratio=0.3,
        pollen_ratio=0.3,
        empty_ratio=0.3,
        capped_ratio=0.1,
        seed=42,
    )

    print("Cell count:", len(cells))
    print("Sample cells:")
    for sample_cell in cells[:3]:
        print(sample_cell)

    first_cell_id = cells[0]["id"]
    honey_path = bfs_find_path(cells, first_cell_id, "honey")
    print("BFS path from {0} to nearest honey cell:".format(first_cell_id))
    print(honey_path)
