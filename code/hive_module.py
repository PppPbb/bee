"""Honeycomb grid and Maya geometry helpers for Cloud-Hive Meadow."""

import math
import random
from collections import deque


AXIAL_DIRECTIONS = (
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, -1),
    (-1, 1),
)


VOXEL_FACE_DIRECTIONS = (
    (1, 0, 0),
    (-1, 0, 0),
    (0, 1, 0),
    (0, -1, 0),
    (0, 0, 1),
    (0, 0, -1),
)


# Warm sRGB-style colors are intentionally split into several material bands.
# The geometry does not use image textures; all color changes come from voxel
# classification and material assignment.
VOXEL_MATERIAL_SPECS = {
    "wax_shadow": {
        "name": "chm_voxel_wax_shadow_MAT",
        "color": (0.48, 0.27, 0.075),
        "roughness": 0.62,
        "specular": 0.20,
    },
    "wax_side": {
        "name": "chm_voxel_wax_side_MAT",
        "color": (0.72, 0.43, 0.10),
        "roughness": 0.58,
        "specular": 0.24,
    },
    "wax_floor": {
        "name": "chm_voxel_wax_floor_MAT",
        "color": (0.92, 0.61, 0.16),
        "roughness": 0.55,
        "specular": 0.26,
    },
    "wax_mid": {
        "name": "chm_voxel_wax_mid_MAT",
        "color": (1.0, 0.72, 0.27),
        "roughness": 0.50,
        "specular": 0.28,
    },
    "wax_light": {
        "name": "chm_voxel_wax_light_MAT",
        "color": (1.0, 0.84, 0.48),
        "roughness": 0.46,
        "specular": 0.30,
    },
    "wax_highlight": {
        "name": "chm_voxel_wax_highlight_MAT",
        "color": (1.0, 0.94, 0.72),
        "roughness": 0.40,
        "specular": 0.34,
    },
    "honey_deep": {
        "name": "chm_voxel_honey_deep_MAT",
        "color": (0.58, 0.31, 0.055),
        "roughness": 0.24,
        "specular": 0.62,
        "transmission": 0.03,
    },
    "honey": {
        "name": "chm_voxel_honey_MAT",
        "color": (1.0, 0.60, 0.055),
        "roughness": 0.18,
        "specular": 0.72,
        "transmission": 0.06,
    },
    "nectar_glow": {
        "name": "chm_voxel_nectar_glow_MAT",
        "color": (1.0, 0.57, 0.035),
        "roughness": 0.14,
        "specular": 0.78,
        "transmission": 0.08,
        "emission": 0.34,
        "emission_color": (1.0, 0.39, 0.025),
    },
    "honey_glint": {
        "name": "chm_voxel_honey_glint_MAT",
        "color": (1.0, 0.96, 0.72),
        "roughness": 0.12,
        "specular": 0.82,
    },
    "pollen_orange": {
        "name": "chm_voxel_pollen_orange_MAT",
        "color": (1.0, 0.48, 0.035),
        "roughness": 0.78,
        "specular": 0.14,
    },
    "pollen_gold": {
        "name": "chm_voxel_pollen_gold_MAT",
        "color": (1.0, 0.68, 0.055),
        "roughness": 0.76,
        "specular": 0.15,
    },
    "pollen_yellow": {
        "name": "chm_voxel_pollen_yellow_MAT",
        "color": (1.0, 0.88, 0.16),
        "roughness": 0.74,
        "specular": 0.16,
    },
    "cap_shadow": {
        "name": "chm_voxel_cap_shadow_MAT",
        "color": (0.78, 0.55, 0.22),
        "roughness": 0.70,
        "specular": 0.18,
    },
    "cap": {
        "name": "chm_voxel_cap_cream_MAT",
        "color": (1.0, 0.86, 0.58),
        "roughness": 0.66,
        "specular": 0.20,
    },
    "queen": {
        "name": "chm_voxel_queen_amber_MAT",
        "color": (0.64, 0.39, 0.10),
        "roughness": 0.50,
        "specular": 0.30,
    },
}


VOXEL_MATERIAL_PRIORITY = {
    material_key: priority
    for priority, material_key in enumerate(VOXEL_MATERIAL_SPECS, start=1)
}


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
                    "blocked_by_capacity": False,
                    "queen_role": None,
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
    for cell in cells:
        neighbors = []
        q = cell["q"]
        r = cell["r"]

        for dq, dr in AXIAL_DIRECTIONS:
            neighbor_id = coordinate_to_id.get((q + dq, r + dr))
            if neighbor_id is not None:
                neighbors.append(neighbor_id)

        cell["neighbors"] = neighbors

    return cells


def assign_cell_types(
    cells,
    honey_ratio,
    pollen_ratio,
    empty_ratio,
    capped_ratio,
    seed,
    queen_enabled=True,
):
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

    assign_queen_chamber(cells, enabled=queen_enabled)
    assignable_indices = [
        index
        for index, cell in enumerate(cells)
        if cell.get("queen_role") not in ("center", "reserved")
    ]
    normalized_ratios = [ratio / ratio_total for ratio in safe_ratios]
    cell_count = len(assignable_indices)
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
    shuffled_indices = list(assignable_indices)
    rng.shuffle(shuffled_indices)

    for cell_index, cell_type in zip(shuffled_indices, assignments):
        cell = cells[cell_index]
        cell["type"] = cell_type
        cell["is_blocked"] = cell_type == "capped"
        cell["blocked_by_capacity"] = False
        cell["queen_role"] = None

    return cells


def queen_zone_cell_ids(cells):
    """Return ids for the center and six cells reserved by the queen chamber."""
    coordinate_to_id = {(cell["q"], cell["r"]): cell["id"] for cell in cells}
    zone_ids = []
    for coordinate in ((0, 0),) + AXIAL_DIRECTIONS:
        cell_id = coordinate_to_id.get(coordinate)
        if cell_id is not None:
            zone_ids.append(cell_id)
    return zone_ids


def assign_queen_chamber(cells, enabled=True):
    """Merge the central seven grid units into one large blocked queen room."""
    cell_map = get_cell_map(cells)
    for cell in cells:
        if cell.get("queen_role") in ("center", "reserved"):
            cell["type"] = "empty"
            cell["queen_role"] = None
            cell["is_blocked"] = False
            cell["blocked_by_capacity"] = False

    if not enabled:
        return cells

    center_id = "cell_q0_r0"
    for cell_id in queen_zone_cell_ids(cells):
        cell = cell_map[cell_id]
        is_center = cell_id == center_id
        cell["type"] = "queen" if is_center else "queen_reserved"
        cell["queen_role"] = "center" if is_center else "reserved"
        cell["nectar"] = 0.0
        cell["pollen"] = 0.0
        cell["is_blocked"] = True
        cell["blocked_by_capacity"] = False
    return cells


def hive_cell_count_from_radius(radius, queen_enabled=True):
    """Return the visible chamber count for an axial hex grid."""
    radius = max(0, int(radius))
    total = 1 + 3 * radius * (radius + 1)
    if queen_enabled and radius >= 1:
        return total - 6
    return total


def visible_cell_count(cells):
    """Count visible cells, excluding the hidden queen footprint cells."""
    return sum(1 for cell in cells if cell.get("type") != "queen_reserved")


def cell_used_capacity(cell):
    """Return the total nectar and pollen currently stored in one cell."""
    nectar = max(0.0, float(cell.get("nectar", 0.0)))
    pollen = max(0.0, float(cell.get("pollen", 0.0)))
    return nectar + pollen


def storage_cell_is_full(cell):
    """Return True when a honey/pollen storage cell has reached capacity."""
    if cell.get("type") not in ("honey", "pollen"):
        return False
    capacity = max(0.0, float(cell.get("capacity", 1.0)))
    return cell_used_capacity(cell) >= capacity - 0.000001


def update_cell_blocked_state(cell):
    """Block full storage cells and reopen them after resources are removed.

    Capped cells always remain blocked. ``blocked_by_capacity`` distinguishes
    an automatic full-cell block from an optional manual block supplied by
    another module.
    """
    was_blocked_by_capacity = bool(cell.get("blocked_by_capacity", False))
    blocked_by_capacity = storage_cell_is_full(cell)
    manually_blocked = bool(cell.get("manually_blocked", False))

    cell["blocked_by_capacity"] = blocked_by_capacity
    if cell.get("type") in ("capped", "queen", "queen_reserved"):
        cell["is_blocked"] = True
    elif blocked_by_capacity:
        cell["is_blocked"] = True
    elif was_blocked_by_capacity:
        cell["is_blocked"] = manually_blocked
    elif manually_blocked:
        cell["is_blocked"] = True

    return cell["is_blocked"]


def update_all_blocked_states(cells):
    """Refresh capacity-based blocked states for every honeycomb cell."""
    for cell in cells:
        update_cell_blocked_state(cell)
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
    update_all_blocked_states(cells)
    cell_map = get_cell_map(cells)
    start_cell = cell_map.get(start_cell_id)
    if start_cell is None:
        return []
    # A bee may leave a full source cell to remove its resource, but capped or
    # manually blocked cells cannot be used as path starts.
    if start_cell.get("is_blocked") and not start_cell.get("blocked_by_capacity"):
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
    """Assign a Maya material through an explicit shading-engine connection.

    Parameters:
        cmds: Imported maya.cmds module.
        node (str): Maya object name.
        material (str): Maya material node name.

    Returns:
        None.
    """
    shading_groups = cmds.listConnections(
        material,
        source=False,
        destination=True,
        type="shadingEngine",
    ) or []
    if shading_groups:
        shading_group = shading_groups[0]
    else:
        shading_group_name = material + "_SG"
        if cmds.objExists(shading_group_name):
            shading_group = shading_group_name
        else:
            shading_group = cmds.sets(
                renderable=True,
                noSurfaceShader=True,
                empty=True,
                name=shading_group_name,
            )

    surface_plug = shading_group + ".surfaceShader"
    connected_shader = cmds.listConnections(
        surface_plug,
        source=True,
        destination=False,
    ) or []
    if material not in connected_shader:
        cmds.connectAttr(material + ".outColor", surface_plug, force=True)

    cmds.sets(node, edit=True, forceElement=shading_group)


def queen_footprint_outline(cell_size):
    """Return the exact outer boundary of the seven-cell queen footprint.

    The queen chamber occupies axial coordinates (0, 0) and its six direct
    neighbours.  Cancelling the shared internal hex edges leaves an 18-edge
    perimeter that fits the second ring of ordinary cells without triangular
    gaps.
    """
    coordinates = [(0, 0)] + list(AXIAL_DIRECTIONS)
    edge_counts = {}
    point_values = {}

    for q, r in coordinates:
        center_x, _center_y, center_z = axial_to_world(q, r, cell_size)
        vertices = []
        for vertex_index in range(6):
            angle = math.radians(30.0 + vertex_index * 60.0)
            point = (
                center_x + math.cos(angle) * cell_size,
                center_z + math.sin(angle) * cell_size,
            )
            key = (round(point[0], 6), round(point[1], 6))
            point_values[key] = point
            vertices.append(key)

        for vertex_index in range(6):
            edge = tuple(sorted((
                vertices[vertex_index],
                vertices[(vertex_index + 1) % 6],
            )))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1

    adjacency = {}
    for (start, end), count in edge_counts.items():
        if count != 1:
            continue
        adjacency.setdefault(start, []).append(end)
        adjacency.setdefault(end, []).append(start)

    start = min(adjacency, key=lambda value: (value[0], value[1]))
    outline_keys = [start]
    previous = None
    current = start
    while True:
        candidates = [point for point in adjacency[current] if point != previous]
        next_key = candidates[0]
        if next_key == start:
            break
        outline_keys.append(next_key)
        previous, current = current, next_key

    return [point_values[key] for key in outline_keys]


def _scale_outline(outline, scale):
    """Scale an XZ outline around its centroid."""
    center_x = sum(point[0] for point in outline) / len(outline)
    center_z = sum(point[1] for point in outline) / len(outline)
    return [
        (
            center_x + (point[0] - center_x) * scale,
            center_z + (point[1] - center_z) * scale,
        )
        for point in outline
    ]


def _create_outline_prism(cmds, name, outline, height, base_y=0.0):
    """Create an extruded Maya polygon from an arbitrary XZ outline."""
    points = [(x, base_y, z) for x, z in outline]
    transform = cmds.polyCreateFacet(
        point=points,
        name=name,
        constructionHistory=False,
    )[0]
    cmds.polyExtrudeFacet(
        "{0}.f[0]".format(transform),
        keepFacesTogether=True,
        translateY=height,
        constructionHistory=False,
    )
    return transform


def get_voxel_dimensions(cell_size, cell_depth, voxel_density=14):
    """Return a stable cubic voxel pitch and quantized hive layer counts."""
    if cell_size <= 0:
        raise ValueError("cell_size must be greater than 0")
    if cell_depth <= 0:
        raise ValueError("cell_depth must be greater than 0")

    density = max(8, min(24, int(round(voxel_density))))
    pitch = float(cell_size) / float(density)
    base_layers = max(3, int(round(float(cell_depth) / pitch)))
    wall_height = max(0.42, float(cell_depth) * 1.25)
    wall_layers = max(5, int(round(wall_height / pitch)))
    wall_thickness = max(pitch * 2.0, float(cell_size) * 0.14)
    return {
        "density": density,
        "pitch": pitch,
        "base_layers": base_layers,
        "wall_layers": wall_layers,
        "wall_thickness": wall_thickness,
    }


def _hex_margin(local_x, local_z, radius):
    """Return inward distance from a point to a pointy-top hex boundary."""
    apothem = float(radius) * math.cos(math.radians(30.0))
    maximum_projection = max(
        local_x * math.cos(math.radians(angle))
        + local_z * math.sin(math.radians(angle))
        for angle in range(0, 360, 60)
    )
    return apothem - maximum_projection


def _point_in_polygon_with_margin(x, z, outline):
    """Return polygon containment and distance to the closest outline edge."""
    inside = False
    closest_distance = None
    point_count = len(outline)
    for index in range(point_count):
        start_x, start_z = outline[index]
        end_x, end_z = outline[(index + 1) % point_count]

        crosses_ray = (start_z > z) != (end_z > z)
        if crosses_ray:
            denominator = end_z - start_z
            intersection_x = start_x + (z - start_z) * (end_x - start_x) / denominator
            if x < intersection_x:
                inside = not inside

        delta_x = end_x - start_x
        delta_z = end_z - start_z
        length_squared = delta_x * delta_x + delta_z * delta_z
        if length_squared <= 0.0000001:
            distance = math.sqrt((x - start_x) ** 2 + (z - start_z) ** 2)
        else:
            factor = max(
                0.0,
                min(
                    1.0,
                    ((x - start_x) * delta_x + (z - start_z) * delta_z)
                    / length_squared,
                ),
            )
            nearest_x = start_x + delta_x * factor
            nearest_z = start_z + delta_z * factor
            distance = math.sqrt((x - nearest_x) ** 2 + (z - nearest_z) ** 2)
        closest_distance = distance if closest_distance is None else min(closest_distance, distance)

    return inside, (closest_distance or 0.0)


def _write_voxel(voxels, key, material_key):
    """Write one voxel while resolving overlaps by visible-material priority."""
    current_material = voxels.get(key)
    if current_material is None or (
        VOXEL_MATERIAL_PRIORITY[material_key]
        >= VOXEL_MATERIAL_PRIORITY[current_material]
    ):
        voxels[key] = material_key


def _cell_seed(cell, seed):
    """Create a deterministic integer seed without Python's randomized hash."""
    return (
        int(seed)
        + (int(cell.get("q", 0)) + 97) * 73856093
        + (int(cell.get("r", 0)) + 193) * 19349663
    )


def _pollen_instance_records(cell, pitch, base_layers, cell_size, seed):
    """Create a dense but deterministic pile of instanced pollen pixels."""
    rng = random.Random(_cell_seed(cell, seed))
    center_x, _center_y, center_z = cell["position"]
    records = []
    used_keys = set()
    attempts = 0
    target_count = 24

    while len(records) < target_count and attempts < target_count * 8:
        attempts += 1
        angle = rng.uniform(0.0, math.tau)
        radius = math.sqrt(rng.random()) * float(cell_size) * 0.56
        ix = int(round((center_x + math.cos(angle) * radius) / pitch))
        iz = int(round((center_z + math.sin(angle) * radius) / pitch))
        stack = 0 if len(records) < 18 else 1
        key = (ix, iz, stack)
        if key in used_keys:
            continue
        used_keys.add(key)
        material_key = (
            "pollen_orange",
            "pollen_gold",
            "pollen_yellow",
        )[len(records) % 3]
        records.append({
            "position": (
                ix * pitch,
                (base_layers + 0.55 + stack * 0.78) * pitch,
                iz * pitch,
            ),
            "scale": (
                rng.uniform(0.72, 0.92),
                rng.uniform(0.62, 1.05),
                rng.uniform(0.72, 0.92),
            ),
            "material": material_key,
            "cell_id": cell["id"],
        })
    return records


def _honey_glint_instance_records(cell, pitch, base_layers, cell_size):
    """Return a small pixel-art reflection pattern for one honey pool."""
    center_x, _center_y, center_z = cell["position"]
    offsets = (
        (-0.34, 0.25),
        (-0.22, 0.25),
        (-0.34, 0.13),
        (0.27, -0.27),
    )
    records = []
    for offset_x, offset_z in offsets:
        ix = int(round((center_x + offset_x * cell_size) / pitch))
        iz = int(round((center_z + offset_z * cell_size) / pitch))
        if _hex_margin(ix * pitch - center_x, iz * pitch - center_z, cell_size) <= pitch * 2.4:
            continue
        records.append({
            "position": (
                ix * pitch,
                (base_layers + 1.32) * pitch,
                iz * pitch,
            ),
            "scale": (0.96, 0.28, 0.96),
            "material": "honey_glint",
            "cell_id": cell["id"],
        })
    return records


def build_honeycomb_voxel_data(
    cells,
    cell_size,
    cell_depth,
    voxel_density=14,
    seed=42,
):
    """Build texture-free voxel occupancy and lightweight instance records.

    The returned structure contains only Python values and can be tested
    without Maya.  Every voxel uses a shared global integer lattice so adjacent
    cells deduplicate cleanly and cannot create sub-pixel cracks.
    """
    dimensions = get_voxel_dimensions(cell_size, cell_depth, voxel_density)
    visible_count = max(1, visible_cell_count(cells))
    adaptive_limit = max(
        8,
        min(24, int(round(14.0 * (96.0 / visible_count) ** (1.0 / 3.0)))),
    )
    if dimensions["density"] > adaptive_limit:
        dimensions = get_voxel_dimensions(
            cell_size,
            cell_depth,
            adaptive_limit,
        )
    pitch = dimensions["pitch"]
    base_layers = dimensions["base_layers"]
    wall_layers = dimensions["wall_layers"]
    wall_thickness = dimensions["wall_thickness"]
    voxels = {}
    instances = {material_key: [] for material_key in (
        "pollen_orange",
        "pollen_gold",
        "pollen_yellow",
        "honey_glint",
    )}

    for cell in cells:
        # Scene generation runs after the simulation has calculated its final
        # state.  Build the frame-one look from initial_type so newly filled
        # cells can visibly cap at their delivery frame instead of starting
        # already closed.
        cell_type = cell.get("initial_type", cell.get("type", "empty"))
        if cell_type == "queen_reserved":
            continue

        center_x, _center_y, center_z = cell["position"]
        is_queen = cell_type == "queen"
        outline = queen_footprint_outline(cell_size) if is_queen else None
        if outline:
            minimum_x = min(point[0] for point in outline)
            maximum_x = max(point[0] for point in outline)
            minimum_z = min(point[1] for point in outline)
            maximum_z = max(point[1] for point in outline)
        else:
            minimum_x = center_x - cell_size
            maximum_x = center_x + cell_size
            minimum_z = center_z - cell_size
            maximum_z = center_z + cell_size

        ix_min = int(math.floor(minimum_x / pitch)) - 1
        ix_max = int(math.ceil(maximum_x / pitch)) + 1
        iz_min = int(math.floor(minimum_z / pitch)) - 1
        iz_max = int(math.ceil(maximum_z / pitch)) + 1

        for ix in range(ix_min, ix_max + 1):
            x = ix * pitch
            for iz in range(iz_min, iz_max + 1):
                z = iz * pitch
                if is_queen:
                    inside, boundary_margin = _point_in_polygon_with_margin(x, z, outline)
                else:
                    boundary_margin = _hex_margin(x - center_x, z - center_z, cell_size)
                    inside = boundary_margin >= -pitch * 0.06
                if not inside:
                    continue

                is_wall = boundary_margin <= wall_thickness
                for layer in range(base_layers):
                    if layer == 0 or boundary_margin <= pitch * 1.2:
                        material_key = "wax_shadow"
                    elif layer == base_layers - 1:
                        if not is_wall and cell_type in ("empty", "pollen"):
                            material_key = "wax_shadow"
                        else:
                            material_key = "wax_floor"
                    else:
                        material_key = "wax_side"
                    _write_voxel(voxels, (ix, layer, iz), material_key)

                if is_wall:
                    variation_hash = abs(ix * 92821 + iz * 68917 + _cell_seed(cell, seed))
                    column_layers = wall_layers - (1 if variation_hash % 29 == 0 else 0)
                    for upper_index in range(column_layers):
                        layer = base_layers + upper_index
                        if upper_index == column_layers - 1:
                            material_key = "wax_highlight"
                        elif upper_index >= column_layers - 3:
                            material_key = "wax_light"
                        elif upper_index <= 1:
                            material_key = "wax_shadow"
                        else:
                            material_key = "wax_mid"
                        _write_voxel(voxels, (ix, layer, iz), material_key)

                if is_queen and not is_wall:
                    _write_voxel(voxels, (ix, base_layers, iz), "queen")
                elif cell_type == "honey" and not is_wall:
                    edge_band = boundary_margin <= wall_thickness + pitch * 2.2
                    honey_material = "honey_deep" if edge_band else "honey"
                    _write_voxel(voxels, (ix, base_layers, iz), honey_material)
                elif cell_type == "capped" and not is_wall:
                    cap_hash = abs(ix * 31337 + iz * 6971 + _cell_seed(cell, seed))
                    cap_layer = base_layers + wall_layers - 2
                    if cap_hash % 17 == 0:
                        cap_layer += 1
                    cap_material = "cap_shadow" if cap_hash % 7 == 0 else "cap"
                    _write_voxel(voxels, (ix, cap_layer, iz), cap_material)

        if cell_type == "pollen":
            for record in _pollen_instance_records(
                cell, pitch, base_layers, cell_size, seed
            ):
                instances[record["material"]].append(record)
        elif cell_type == "honey":
            instances["honey_glint"].extend(
                _honey_glint_instance_records(cell, pitch, base_layers, cell_size)
            )

    return {
        "pitch": pitch,
        "requested_density": max(8, min(24, int(round(voxel_density)))),
        "density": dimensions["density"],
        "base_layers": base_layers,
        "wall_layers": wall_layers,
        "wall_thickness": wall_thickness,
        "voxels": voxels,
        "instances": instances,
    }


def hex_voxel_layer_keys(
    center_x,
    center_z,
    radius,
    pitch,
    y_layer,
    inset=0.0,
):
    """Return global voxel keys for one inset hexagonal layer."""
    keys = set()
    ix_min = int(math.floor((center_x - radius) / pitch)) - 1
    ix_max = int(math.ceil((center_x + radius) / pitch)) + 1
    iz_min = int(math.floor((center_z - radius) / pitch)) - 1
    iz_max = int(math.ceil((center_z + radius) / pitch)) + 1
    for ix in range(ix_min, ix_max + 1):
        for iz in range(iz_min, iz_max + 1):
            margin = _hex_margin(
                ix * pitch - center_x,
                iz * pitch - center_z,
                radius,
            )
            if margin >= float(inset):
                keys.add((ix, int(y_layer), iz))
    return keys


def voxel_mesh_data(voxel_keys, pitch, occupied_keys=None):
    """Build vertices and exposed quad faces for a set of cubic voxels."""
    keys = set(voxel_keys)
    occupied = keys if occupied_keys is None else set(occupied_keys)
    half = float(pitch) * 0.5
    vertices = []
    face_counts = []
    face_connects = []

    face_offsets = (
        ((1, 0, 0), ((half, -half, -half), (half, half, -half), (half, half, half), (half, -half, half))),
        ((-1, 0, 0), ((-half, -half, half), (-half, half, half), (-half, half, -half), (-half, -half, -half))),
        ((0, 1, 0), ((-half, half, -half), (-half, half, half), (half, half, half), (half, half, -half))),
        ((0, -1, 0), ((-half, -half, half), (-half, -half, -half), (half, -half, -half), (half, -half, half))),
        ((0, 0, 1), ((half, -half, half), (half, half, half), (-half, half, half), (-half, -half, half))),
        ((0, 0, -1), ((-half, -half, -half), (-half, half, -half), (half, half, -half), (half, -half, -half))),
    )

    for ix, iy, iz in sorted(keys):
        center_x = ix * pitch
        center_y = (iy + 0.5) * pitch
        center_z = iz * pitch
        for direction, offsets in face_offsets:
            neighbor = (ix + direction[0], iy + direction[1], iz + direction[2])
            if neighbor in occupied:
                continue
            first_index = len(vertices)
            vertices.extend(
                (
                    center_x + offset_x,
                    center_y + offset_y,
                    center_z + offset_z,
                )
                for offset_x, offset_y, offset_z in offsets
            )
            face_counts.append(4)
            face_connects.extend(range(first_index, first_index + 4))

    return vertices, face_counts, face_connects


def create_voxel_material(cmds, material_key):
    """Create or reuse a physically distinct texture-free voxel material."""
    spec = VOXEL_MATERIAL_SPECS[material_key]
    material_name = spec["name"]
    if cmds.objExists(material_name):
        node_type = cmds.nodeType(material_name)
        if node_type == "standardSurface":
            cmds.setAttr(material_name + ".baseColor", *spec["color"], type="double3")
            cmds.setAttr(material_name + ".base", 1.0)
            cmds.setAttr(material_name + ".specular", spec.get("specular", 0.25))
            cmds.setAttr(
                material_name + ".specularRoughness",
                spec.get("roughness", 0.5),
            )
            if cmds.attributeQuery("transmission", node=material_name, exists=True):
                cmds.setAttr(
                    material_name + ".transmission",
                    spec.get("transmission", 0.0),
                )
            if cmds.attributeQuery("emission", node=material_name, exists=True):
                cmds.setAttr(material_name + ".emission", spec.get("emission", 0.14))
            if cmds.attributeQuery("emissionColor", node=material_name, exists=True):
                cmds.setAttr(
                    material_name + ".emissionColor",
                    *spec.get("emission_color", spec["color"]),
                    type="double3",
                )
        elif node_type == "lambert":
            cmds.setAttr(material_name + ".color", *spec["color"], type="double3")
            if cmds.attributeQuery("incandescence", node=material_name, exists=True):
                emission = max(0.0, float(spec.get("emission", 0.14)))
                emission_color = spec.get("emission_color", spec["color"])
                cmds.setAttr(
                    material_name + ".incandescence",
                    *(component * emission for component in emission_color),
                    type="double3",
                )
        return material_name

    material = None
    try:
        material = cmds.shadingNode("standardSurface", asShader=True, name=material_name)
        cmds.setAttr(material + ".baseColor", *spec["color"], type="double3")
        cmds.setAttr(material + ".base", 1.0)
        cmds.setAttr(material + ".specular", spec.get("specular", 0.25))
        cmds.setAttr(material + ".specularRoughness", spec.get("roughness", 0.5))
        if cmds.attributeQuery("transmission", node=material, exists=True):
            cmds.setAttr(material + ".transmission", spec.get("transmission", 0.0))
        if cmds.attributeQuery("emission", node=material, exists=True):
            cmds.setAttr(material + ".emission", spec.get("emission", 0.14))
        if cmds.attributeQuery("emissionColor", node=material, exists=True):
            cmds.setAttr(
                material + ".emissionColor",
                *spec.get("emission_color", spec["color"]),
                type="double3",
            )
        return material
    except (RuntimeError, ValueError):
        if material and cmds.objExists(material):
            cmds.delete(material)
        material = cmds.shadingNode("lambert", asShader=True, name=material_name)
        cmds.setAttr(material + ".color", *spec["color"], type="double3")
        if cmds.attributeQuery("incandescence", node=material, exists=True):
            emission = max(0.0, float(spec.get("emission", 0.14)))
            emission_color = spec.get("emission_color", spec["color"])
            cmds.setAttr(
                material + ".incandescence",
                *(component * emission for component in emission_color),
                type="double3",
            )
        return material


def create_merged_voxel_mesh(
    voxel_keys,
    pitch,
    name,
    material,
    parent=None,
    occupied_keys=None,
):
    """Create one Maya mesh containing only the exposed faces of many voxels."""
    import maya.api.OpenMaya as om
    import maya.cmds as cmds

    vertices, face_counts, face_connects = voxel_mesh_data(
        voxel_keys,
        pitch,
        occupied_keys=occupied_keys,
    )
    if not face_counts:
        return None

    points = om.MPointArray()
    for vertex in vertices:
        points.append(om.MPoint(vertex[0], vertex[1], vertex[2]))
    mesh_object = om.MFnMesh().create(
        points,
        face_counts,
        face_connects,
    )
    # Maya versions differ here: MFnMesh.create() may return the mesh shape or
    # the automatically created transform.  Taking parent(0) unconditionally
    # can therefore resolve to the world node ("|"), which cannot be renamed.
    if mesh_object.hasFn(om.MFn.kTransform):
        transform_object = mesh_object
    else:
        transform_object = om.MFnDagNode(mesh_object).parent(0)
    transform = om.MFnDagNode(transform_object).fullPathName()
    transform = cmds.rename(transform, name)
    shape_name = cmds.listRelatives(transform, shapes=True, fullPath=False)[0]
    cmds.rename(shape_name, name + "Shape")
    if parent:
        cmds.parent(transform, parent)
    _assign_maya_material(cmds, transform, material)
    return transform


def ensure_voxel_cube_prototype(cmds, name, pitch, material, parent):
    """Create one hidden cube whose shape can be shared by many instances."""
    if cmds.objExists(name):
        return name
    cube_result = cmds.polyCube(
        width=float(pitch),
        height=float(pitch),
        depth=float(pitch),
        name=name,
        constructionHistory=False,
    )
    prototype = cube_result[0] if isinstance(cube_result, (list, tuple)) else cube_result
    cmds.parent(prototype, parent)
    _assign_maya_material(cmds, prototype, material)
    cmds.setAttr(prototype + ".visibility", 0)
    return prototype


def create_voxel_cube_instances(cmds, prototype, records, name_prefix, parent):
    """Create transform instances that all share one prototype cube shape."""
    created = []
    for index, record in enumerate(records):
        instance = cmds.instance(
            prototype,
            name="{0}_{1:04d}".format(name_prefix, index),
        )[0]
        cmds.parent(instance, parent)
        cmds.setAttr(instance + ".visibility", 1)
        cmds.xform(
            instance,
            translation=record["position"],
            scale=record.get("scale", (1.0, 1.0, 1.0)),
            worldSpace=True,
        )
        created.append(instance)
    return created


def create_honeycomb_geometry(
    cells,
    cell_size,
    cell_depth,
    voxel_density=14,
    seed=42,
):
    """Create a texture-free honeycomb from merged voxel meshes and instances."""
    import maya.cmds as cmds

    voxel_data = build_honeycomb_voxel_data(
        cells,
        cell_size,
        cell_depth,
        voxel_density=voxel_density,
        seed=seed,
    )
    if voxel_data["density"] < voxel_data["requested_density"]:
        print(
            "Cloud-Hive voxel density reduced from {0} to {1} for this hive size.".format(
                voxel_data["requested_density"],
                voxel_data["density"],
            )
        )
    group_name = "CloudHive_Honeycomb_GRP"
    if cmds.objExists(group_name):
        cmds.delete(group_name)
    cmds.group(empty=True, name=group_name)
    cmds.addAttr(group_name, longName="voxelPitch", attributeType="double")
    cmds.setAttr(group_name + ".voxelPitch", voxel_data["pitch"])
    cmds.addAttr(group_name, longName="voxelDensity", attributeType="long")
    cmds.setAttr(group_name + ".voxelDensity", voxel_data["density"])

    mesh_group = cmds.group(empty=True, name="CloudHive_VoxelMeshes_GRP")
    instance_group = cmds.group(empty=True, name="CloudHive_VoxelInstances_GRP")
    prototype_group = cmds.group(empty=True, name="CloudHive_VoxelPrototypes_GRP")
    cmds.parent(mesh_group, instance_group, prototype_group, group_name)
    cmds.setAttr(prototype_group + ".visibility", 0)

    occupied_keys = set(voxel_data["voxels"])
    mesh_objects = []
    for material_key in VOXEL_MATERIAL_SPECS:
        keys = [
            key
            for key, voxel_material in voxel_data["voxels"].items()
            if voxel_material == material_key
        ]
        if not keys:
            continue
        material = create_voxel_material(cmds, material_key)
        mesh = create_merged_voxel_mesh(
            keys,
            voxel_data["pitch"],
            "CloudHive_voxels_{0}".format(material_key),
            material,
            parent=mesh_group,
            occupied_keys=occupied_keys,
        )
        if mesh:
            mesh_objects.append(mesh)

    instance_objects = []
    for material_key, records in voxel_data["instances"].items():
        if not records:
            continue
        material = create_voxel_material(cmds, material_key)
        prototype = ensure_voxel_cube_prototype(
            cmds,
            "CloudHive_{0}_voxel_PROTOTYPE".format(material_key),
            voxel_data["pitch"],
            material,
            prototype_group,
        )
        created = create_voxel_cube_instances(
            cmds,
            prototype,
            records,
            "CloudHive_{0}_instance".format(material_key),
            instance_group,
        )
        instance_objects.extend(created)

        if material_key == "honey_glint":
            for index, instance in enumerate(created):
                phase = 1 + (index % 5) * 3
                cmds.setKeyframe(instance, attribute="scaleX", time=phase, value=0.72)
                cmds.setKeyframe(instance, attribute="scaleZ", time=phase, value=0.72)
                cmds.setKeyframe(instance, attribute="scaleX", time=phase + 8, value=1.12)
                cmds.setKeyframe(instance, attribute="scaleZ", time=phase + 8, value=1.12)
                cmds.setKeyframe(instance, attribute="scaleX", time=phase + 16, value=0.72)
                cmds.setKeyframe(instance, attribute="scaleZ", time=phase + 16, value=0.72)
                cmds.setInfinity(instance, attribute="scaleX", preInfinite="cycle", postInfinite="cycle")
                cmds.setInfinity(instance, attribute="scaleZ", preInfinite="cycle", postInfinite="cycle")

    content_objects = mesh_objects + instance_objects
    for cell in cells:
        if cell.get("type") == "queen_reserved":
            cell["maya_object"] = None
            cell["content_objects"] = []
        else:
            cell["maya_object"] = group_name
            cell["content_objects"] = content_objects
            cell["voxel_pitch"] = voxel_data["pitch"]

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
