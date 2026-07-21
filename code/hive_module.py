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
                    "reserved_amount": 0.0,
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
        cell["reserved_amount"] = 0.0
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
        cell["reserved_amount"] = 0.0
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
    blocked_by_capacity = storage_cell_is_full(cell)
    manually_blocked = bool(cell.get("manually_blocked", False))

    cell["blocked_by_capacity"] = blocked_by_capacity
    if cell.get("type") in ("capped", "queen", "queen_reserved"):
        cell["is_blocked"] = True
    elif blocked_by_capacity:
        cell["is_blocked"] = True
    else:
        cell["is_blocked"] = manually_blocked

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

    wax_floor_material = _create_maya_material(
        cmds, "chm_pixel_wax_floor_MAT", (0.96, 0.68, 0.28)
    )
    wax_wall_material = _create_maya_material(
        cmds, "chm_pixel_wax_wall_MAT", (1.0, 0.84, 0.48)
    )
    honey_material = _create_maya_material(
        cmds, "chm_pixel_honey_inside_MAT", (1.0, 0.36, 0.015)
    )
    honey_highlight_material = _create_maya_material(
        cmds, "chm_pixel_honey_highlight_MAT", (1.0, 0.78, 0.16)
    )
    pollen_materials = [
        _create_maya_material(cmds, "chm_pixel_pollen_orange_MAT", (1.0, 0.25, 0.01)),
        _create_maya_material(cmds, "chm_pixel_pollen_gold_MAT", (1.0, 0.63, 0.02)),
        _create_maya_material(cmds, "chm_pixel_pollen_yellow_MAT", (1.0, 0.88, 0.08)),
    ]
    cap_material = _create_maya_material(
        cmds, "chm_pixel_cap_cream_MAT", (1.0, 0.91, 0.66)
    )
    queen_material = _create_maya_material(
        cmds, "chm_pixel_queen_violet_MAT", (0.64, 0.24, 0.72)
    )

    pollen_offsets = [
        (-0.42, -0.18), (-0.20, -0.34), (0.03, -0.38), (0.29, -0.27),
        (0.43, -0.04), (-0.34, 0.06), (-0.10, -0.02), (0.16, 0.01),
        (0.37, 0.17), (-0.26, 0.29), (0.01, 0.32), (0.25, 0.34),
    ]

    for cell in cells:
        if cell.get("type") == "queen_reserved":
            cell["maya_object"] = None
            continue

        x, _, z = cell["position"]
        object_name = "{0}_CELL_GRP".format(cell["id"])
        is_queen = cell.get("type") == "queen"
        cell_group = cmds.group(empty=True, name=object_name)
        cmds.parent(cell_group, group_name)

        if is_queen:
            # A scaled regular hex cannot fill the union of seven hex cells.
            # Build the real 18-edge footprint so every outer segment shares
            # the same boundary as a neighbouring cell in the second ring.
            outline = queen_footprint_outline(cell_size)
            base_height = max(0.12, cell_depth * 0.36)
            wall_height = max(0.58, cell_depth * 2.15)
            wall_thickness = max(cell_size * 0.13, 0.10)
            seam_overlap = max(0.015, cell_depth * 0.04)

            base = _create_outline_prism(
                cmds,
                "{0}_floor".format(cell["id"]),
                outline,
                base_height,
            )
            cmds.parent(base, cell_group)
            _assign_maya_material(cmds, base, wax_floor_material)

            for wall_index in range(len(outline)):
                start_x, start_z = outline[wall_index]
                end_x, end_z = outline[(wall_index + 1) % len(outline)]
                delta_x = end_x - start_x
                delta_z = end_z - start_z
                edge_length = math.sqrt(delta_x * delta_x + delta_z * delta_z)
                edge_angle = -math.degrees(math.atan2(delta_z, delta_x))
                wall, _wall_shape = cmds.polyCube(
                    width=edge_length * 1.04,
                    height=wall_height,
                    depth=wall_thickness,
                    name="{0}_wall_{1:02d}".format(cell["id"], wall_index),
                )
                cmds.xform(
                    wall,
                    translation=(
                        (start_x + end_x) * 0.5,
                        base_height + wall_height * 0.5 - seam_overlap,
                        (start_z + end_z) * 0.5,
                    ),
                    rotation=(0.0, edge_angle, 0.0),
                    worldSpace=True,
                )
                cmds.parent(wall, cell_group)
                _assign_maya_material(cmds, wall, wax_wall_material)

            queen_floor = _create_outline_prism(
                cmds,
                "{0}_queen_floor".format(cell["id"]),
                _scale_outline(outline, 0.78),
                max(0.08, cell_depth * 0.24),
                base_y=base_height + 0.015,
            )
            cmds.parent(queen_floor, cell_group)
            _assign_maya_material(cmds, queen_floor, queen_material)

            cell["maya_object"] = cell_group
            cell["content_objects"] = [queen_floor]
            continue

        visual_radius = cell_size
        visual_depth = cell_depth
        base_height = max(0.10, cell_depth * 0.30)
        wall_height = max(0.42, visual_depth * 0.92)
        wall_radius = visual_radius * 0.93
        wall_thickness = max(cell_size * 0.13, visual_radius * 0.075)
        seam_overlap = max(0.015, cell_depth * 0.04)

        base, _base_shape = cmds.polyCylinder(
            # Extend the floor under the wall ring.  The previous 0.91 scale
            # exposed dark triangular gaps around the lower wall corners.
            radius=visual_radius * 0.99,
            height=base_height,
            subdivisionsX=6,
            subdivisionsY=1,
            subdivisionsZ=0,
            axis=(0, 1, 0),
            name="{0}_floor".format(cell["id"]),
        )
        cmds.xform(base, translation=(x, base_height * 0.5, z), worldSpace=True)
        # Maya's six-sided cylinder starts at a different angular offset from
        # the pointy-top axial hex used by the wall vertices.  Rotate it so the
        # floor edges and the wall edges are parallel.
        cmds.rotate(0.0, 30.0, 0.0, base, relative=True, objectSpace=True)
        cmds.parent(base, cell_group)
        _assign_maya_material(cmds, base, wax_floor_material)

        vertices = []
        for vertex_index in range(6):
            angle = math.radians(30.0 + vertex_index * 60.0)
            vertices.append((
                x + math.cos(angle) * wall_radius,
                z + math.sin(angle) * wall_radius,
            ))

        for wall_index in range(6):
            start_x, start_z = vertices[wall_index]
            end_x, end_z = vertices[(wall_index + 1) % 6]
            delta_x = end_x - start_x
            delta_z = end_z - start_z
            edge_length = math.sqrt(delta_x * delta_x + delta_z * delta_z)
            edge_angle = -math.degrees(math.atan2(delta_z, delta_x))
            wall, _wall_shape = cmds.polyCube(
                width=edge_length * 1.05,
                height=wall_height,
                depth=wall_thickness,
                name="{0}_wall_{1:02d}".format(cell["id"], wall_index),
            )
            cmds.xform(
                wall,
                    translation=(
                        (start_x + end_x) * 0.5,
                        base_height + wall_height * 0.5 - seam_overlap,
                        (start_z + end_z) * 0.5,
                    ),
                rotation=(0.0, edge_angle, 0.0),
                worldSpace=True,
            )
            cmds.parent(wall, cell_group)
            _assign_maya_material(cmds, wall, wax_wall_material)

        cell_type = cell.get("type")
        content_objects = []
        if cell_type == "honey":
            pool, _pool_shape = cmds.polyCylinder(
                radius=visual_radius * 0.70,
                height=max(0.075, cell_depth * 0.22),
                subdivisionsX=6,
                subdivisionsY=1,
                subdivisionsZ=0,
                axis=(0, 1, 0),
                name="{0}_honey_pool".format(cell["id"]),
            )
            cmds.xform(
                pool,
                translation=(x, base_height + max(0.045, cell_depth * 0.12), z),
                worldSpace=True,
            )
            cmds.rotate(0.0, 30.0, 0.0, pool, relative=True, objectSpace=True)
            cmds.parent(pool, cell_group)
            _assign_maya_material(cmds, pool, honey_material)
            content_objects.append(pool)

            highlight, _highlight_shape = cmds.polyCube(
                width=visual_radius * 0.30,
                height=0.035,
                depth=visual_radius * 0.10,
                name="{0}_honey_glint".format(cell["id"]),
            )
            cmds.xform(
                highlight,
                translation=(
                    x - visual_radius * 0.18,
                    base_height + max(0.095, cell_depth * 0.27),
                    z + visual_radius * 0.12,
                ),
                worldSpace=True,
            )
            cmds.parent(highlight, cell_group)
            _assign_maya_material(cmds, highlight, honey_highlight_material)
            content_objects.append(highlight)

        elif cell_type == "pollen":
            grain_size = max(0.09, cell_size * 0.13)
            for grain_index, (offset_x, offset_z) in enumerate(pollen_offsets):
                grain, _grain_shape = cmds.polyCube(
                    width=grain_size,
                    height=grain_size * (0.75 + (grain_index % 3) * 0.12),
                    depth=grain_size,
                    name="{0}_pollen_pixel_{1:02d}".format(cell["id"], grain_index),
                )
                cmds.xform(
                    grain,
                    translation=(
                        x + offset_x * visual_radius,
                        base_height + grain_size * (0.40 + (grain_index % 2) * 0.18),
                        z + offset_z * visual_radius,
                    ),
                    worldSpace=True,
                )
                cmds.parent(grain, cell_group)
                _assign_maya_material(
                    cmds, grain, pollen_materials[grain_index % len(pollen_materials)]
                )
                content_objects.append(grain)

        elif cell_type == "capped":
            cap_height = max(0.09, cell_depth * 0.24)
            cap, _cap_shape = cmds.polyCylinder(
                radius=visual_radius * 0.82,
                height=cap_height,
                subdivisionsX=6,
                subdivisionsY=1,
                subdivisionsZ=0,
                axis=(0, 1, 0),
                name="{0}_wax_cap".format(cell["id"]),
            )
            cmds.xform(
                cap,
                translation=(x, base_height + wall_height - cap_height * 0.55, z),
                worldSpace=True,
            )
            cmds.rotate(0.0, 30.0, 0.0, cap, relative=True, objectSpace=True)
            cmds.parent(cap, cell_group)
            _assign_maya_material(cmds, cap, cap_material)
            content_objects.append(cap)

        cell["maya_object"] = cell_group
        cell["content_objects"] = content_objects

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
