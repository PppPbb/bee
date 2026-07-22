"""Cloud resource generation and Maya visualization helpers for Cloud-Hive Meadow."""

import math
import random


FLOWER_ARCHETYPES = (
    "pink",
    "daisy",
    "yellow_cluster",
    "lavender",
    "blue",
    "orange",
)

# Measured against the current multi-puff generator and presentation camera.
# Keeping this value explicit lets size composition use actual rendered width
# instead of the wider local-X bounding box of a cloud.
CLOUD_VIEW_WIDTH_PER_SCALE = 2.58


CLOUD_SHAPE_PROFILES = (
    {
        "name": "towered",
        "width_factor": 0.85,
        "depth_factor": 0.92,
        "vertical_factor": 1.04,
        "anchors": (
            (0.00, 0.18, "peak", True),
            (-0.23, 0.08, "high", True),
            (0.26, 0.04, "high", True),
            (-0.47, 0.14, "mid", True),
            (0.49, 0.12, "mid", True),
            (-0.31, -0.25, "mid", True),
            (0.33, -0.24, "mid", True),
            (-0.04, 0.43, "mid", True),
            (-0.73, 0.00, "rim", True),
            (0.72, -0.02, "rim", True),
            (-0.57, -0.36, "rim", True),
            (-0.18, -0.48, "rim", True),
            (0.22, -0.46, "rim", True),
            (0.56, -0.34, "rim", True),
        ),
    },
    {
        "name": "double_peak",
        "width_factor": 1.18,
        "depth_factor": 1.00,
        "vertical_factor": 1.00,
        "anchors": (
            (-0.37, 0.16, "peak", True),
            (0.39, 0.12, "peak", True),
            (0.00, -0.10, "mid", True),
            (-0.54, 0.10, "mid", True),
            (0.56, 0.06, "mid", True),
            (-0.34, -0.27, "mid", True),
            (0.35, -0.28, "mid", True),
            (0.02, 0.42, "mid", True),
            (-0.79, -0.02, "rim", True),
            (0.80, -0.04, "rim", True),
            (-0.64, -0.37, "rim", True),
            (-0.24, -0.50, "rim", True),
            (0.18, -0.50, "rim", True),
            (0.61, -0.37, "rim", True),
            (-0.50, 0.42, "rim", False),
            (0.52, 0.40, "rim", False),
        ),
    },
    {
        "name": "swept",
        "width_factor": 1.28,
        "depth_factor": 0.85,
        "vertical_factor": 0.98,
        "anchors": (
            (-0.37, 0.16, "peak", True),
            (-0.08, 0.10, "high", True),
            (0.24, 0.05, "high", True),
            (-0.55, -0.14, "mid", True),
            (0.48, 0.00, "mid", True),
            (-0.25, -0.31, "mid", True),
            (0.24, -0.28, "mid", True),
            (0.58, -0.24, "mid", True),
            (-0.78, 0.05, "rim", True),
            (-0.67, -0.38, "rim", True),
            (-0.18, -0.50, "rim", True),
            (0.22, -0.46, "rim", True),
            (0.63, -0.37, "rim", True),
            (1.02, -0.13, "rim", True),
            (0.48, 0.36, "rim", False),
        ),
    },
    {
        "name": "clustered",
        "width_factor": 0.82,
        "depth_factor": 1.22,
        "vertical_factor": 0.96,
        "anchors": (
            (0.18, 0.22, "peak", True),
            (-0.26, 0.08, "high", True),
            (0.02, -0.14, "high", True),
            (-0.49, 0.19, "mid", True),
            (0.48, 0.12, "mid", True),
            (-0.38, -0.25, "mid", True),
            (0.36, -0.31, "mid", True),
            (-0.10, 0.48, "mid", True),
            (-0.70, -0.02, "rim", True),
            (0.69, -0.05, "rim", True),
            (-0.50, -0.43, "rim", True),
            (-0.08, -0.53, "rim", True),
            (0.48, -0.45, "rim", True),
            (0.39, 0.46, "rim", False),
        ),
    },
)


def _cloud_shape_variant(cloud_index, seed):
    """Choose a deterministic profile while keeping adjacent clouds distinct."""
    return (int(seed) + int(cloud_index) * 3) % len(CLOUD_SHAPE_PROFILES)


def _cloud_row_sizes(cloud_count):
    """Split a cloud count into view-balanced rows of at most four."""
    count = max(0, int(cloud_count))
    if count == 0:
        return []
    row_count = max(1, int(math.ceil(count / 4.0)))
    base_row_size = count // row_count
    extra_slots = count % row_count
    return [
        base_row_size + (1 if row_index < extra_slots else 0)
        for row_index in range(row_count)
    ]


def calculate_hive_view_span(cells, cell_size, camera_y_rotation=38.0):
    """Estimate honeycomb width along the presentation camera's image axis."""
    if not cells:
        return max(0.01, float(cell_size) * 2.0)
    camera_angle = math.radians(float(camera_y_rotation))
    right_x = math.cos(camera_angle)
    right_z = -math.sin(camera_angle)
    projected = [
        float(cell["position"][0]) * right_x
        + float(cell["position"][2]) * right_z
        for cell in cells
    ]
    return (
        max(projected)
        - min(projected)
        + max(0.01, float(cell_size) * 2.0)
    )


def _balanced_cloud_visual_scales(
    cloud_count,
    scene_radius,
    base_visual_scale,
    hive_visual_span,
    seed,
):
    """Return varied cloud scales whose combined width balances the hive."""
    row_sizes = _cloud_row_sizes(cloud_count)
    if not row_sizes:
        return []

    base_scale = max(0.05, float(base_visual_scale))
    target_span = (
        float(hive_visual_span)
        if hive_visual_span is not None and float(hive_visual_span) > 0.0
        else max(0.1, float(scene_radius) * 2.0)
    )
    # One generated puff cluster is about 2.58 times its input scale in view
    # width. Covering 84% of the honeycomb keeps the two systems balanced while
    # leaving breathing room between neighboring clouds.
    maximum_row_size = max(row_sizes)
    nominal_scale = (
        target_span
        * 0.84
        / (CLOUD_VIEW_WIDTH_PER_SCALE * float(maximum_row_size))
    )
    nominal_scale = max(0.35, nominal_scale)
    composition_cap = max(
        base_scale * 1.90,
        target_span * 0.20,
    )
    nominal_scale = min(composition_cap, nominal_scale)

    rng = random.Random(int(seed) + 5179)
    factors = []
    for row_size in row_sizes:
        if row_size == 1:
            row_factors = [1.0]
        elif row_size == 2:
            row_factors = [
                rng.uniform(0.80, 0.90),
                rng.uniform(1.12, 1.24),
            ]
            if rng.random() < 0.5:
                row_factors.reverse()
        elif row_size == 3:
            # A dominant central cloud and two unequal side clouds echo the
            # reference composition without forcing identical sizes.
            side_factors = [
                rng.uniform(0.77, 0.87),
                rng.uniform(0.94, 1.06),
            ]
            if rng.random() < 0.5:
                side_factors.reverse()
            row_factors = [
                side_factors[0],
                rng.uniform(1.27, 1.40),
                side_factors[1],
            ]
        else:
            row_factors = [
                rng.uniform(0.82, 0.94),
                rng.uniform(1.13, 1.25),
                rng.uniform(0.74, 0.84),
                rng.uniform(1.05, 1.16),
            ]
            if rng.random() < 0.5:
                row_factors.reverse()
        factors.extend(row_factors)

    factor_average = sum(factors) / float(len(factors))
    return [
        nominal_scale * factor / factor_average
        for factor in factors
    ]


def _balanced_cloud_positions(
    cloud_count,
    scene_radius,
    min_height,
    max_height,
    seed,
    visual_scales=None,
    shape_width_factors=None,
):
    """Create deterministic cloud positions balanced in the render view.

    Up to four clouds occupy separated screen-horizontal slots. Larger counts
    are split into balanced depth rows. Small bounded jitter prevents a rigid
    grid while preserving the composition and minimum visual separation.
    """
    count = max(0, int(cloud_count))
    if count == 0:
        return []

    rng = random.Random(int(seed) + 2713)
    radius = float(scene_radius)
    row_sizes = _cloud_row_sizes(count)
    row_count = len(row_sizes)

    # The presentation camera uses Y rotation 38 degrees. These orthogonal XZ
    # vectors spread clouds across its horizontal image axis and scene depth.
    camera_angle = math.radians(38.0)
    right_x = math.cos(camera_angle)
    right_z = -math.sin(camera_angle)
    depth_x = math.sin(camera_angle)
    depth_z = math.cos(camera_angle)
    row_depth_extent = 0.34 * radius
    positions = []
    scale_index = 0

    for row_index, row_size in enumerate(row_sizes):
        if row_count == 1:
            base_depth = rng.uniform(-0.10, 0.10) * radius
        else:
            row_fraction = float(row_index) / float(row_count - 1)
            base_depth = -row_depth_extent + row_fraction * row_depth_extent * 2.0

        row_scales = (
            list(visual_scales[scale_index:scale_index + row_size])
            if visual_scales and len(visual_scales) >= scale_index + row_size
            else []
        )
        row_width_factors = (
            list(shape_width_factors[scale_index:scale_index + row_size])
            if shape_width_factors
            and len(shape_width_factors) >= scale_index + row_size
            else [1.0] * row_size
        )
        if row_scales:
            estimated_widths = [
                CLOUD_VIEW_WIDTH_PER_SCALE * scale * width_factor
                for scale, width_factor in zip(row_scales, row_width_factors)
            ]
            gap = max(0.28, radius * 0.10)
            total_width = sum(estimated_widths) + gap * max(0, row_size - 1)
            edge = -total_width * 0.5
            horizontal_slots = []
            for estimated_width in estimated_widths:
                horizontal_slots.append(edge + estimated_width * 0.5)
                edge += estimated_width + gap
            common_shift = rng.uniform(-0.025, 0.025) * radius
            horizontal_slots = [
                slot + common_shift + rng.uniform(-0.012, 0.012) * radius
                for slot in horizontal_slots
            ]
        elif row_size <= 1:
            horizontal_slots = [0.0]
        else:
            slot_extent = {
                2: 0.56,
                3: 0.74,
                4: 0.84,
            }.get(row_size, 0.84)
            horizontal_slots = [
                -slot_extent + (2.0 * slot_extent * slot_index / (row_size - 1))
                for slot_index in range(row_size)
            ]

        for slot_index, slot in enumerate(horizontal_slots):
            horizontal = slot if row_scales else (
                slot * radius + rng.uniform(-0.035, 0.035) * radius
            )
            depth = base_depth + rng.uniform(-0.055, 0.055) * radius
            x = horizontal * right_x + depth * depth_x
            z = horizontal * right_z + depth * depth_z
            if row_scales and max_height > min_height:
                relative_scale = row_scales[slot_index] / max(
                    0.001,
                    sum(row_scales) / float(len(row_scales)),
                )
                height_range = max_height - min_height
                y = (
                    (min_height + max_height) * 0.5
                    + height_range * 0.10
                    + rng.uniform(-0.16, 0.16) * height_range
                    + (relative_scale - 1.0) * height_range * 0.42
                )
                y = max(min_height, min(max_height, y))
            else:
                y = rng.uniform(min_height, max_height)
            positions.append([x, y, z])
        scale_index += row_size

    return positions


def create_cloud_data(
    cloud_count,
    scene_radius,
    min_height,
    max_height,
    nectar_amount,
    pollen_amount,
    seed,
    hive_visual_span=None,
    base_visual_scale=1.0,
):
    """Create deterministic cloud resource data around the honeycomb scene.

    Parameters:
        cloud_count (int): Number of clouds to generate.
        scene_radius (float): Approximate horizontal radius of the scene.
        min_height (float): Minimum cloud height in world units.
        max_height (float): Maximum cloud height in world units.
        nectar_amount (float): Nectar available on each cloud.
        pollen_amount (float): Pollen available on each cloud.
        seed (int): Random seed for reproducible cloud placement.
        hive_visual_span (float | None): Honeycomb width in the render view.
        base_visual_scale (float): Fallback scale reference from visual config.

    Returns:
        list[dict]: Cloud dictionaries with resource amounts and emission points.
    """
    if cloud_count < 0:
        raise ValueError("cloud_count must be 0 or greater")
    if scene_radius < 0:
        raise ValueError("scene_radius must be 0 or greater")
    if min_height > max_height:
        raise ValueError("min_height must be less than or equal to max_height")

    rng = random.Random(seed)
    clouds = []
    visual_scales = _balanced_cloud_visual_scales(
        cloud_count,
        scene_radius,
        base_visual_scale,
        hive_visual_span,
        seed,
    )
    shape_variants = [
        _cloud_shape_variant(index, seed)
        for index in range(int(cloud_count))
    ]
    shape_width_factors = [
        CLOUD_SHAPE_PROFILES[variant]["width_factor"]
        for variant in shape_variants
    ]
    balanced_positions = _balanced_cloud_positions(
        cloud_count,
        scene_radius,
        min_height,
        max_height,
        seed,
        visual_scales=visual_scales,
        shape_width_factors=shape_width_factors,
    )

    resource_point_count = 5
    resource_point_spread = max(scene_radius * 0.12, 0.25)
    resource_point_vertical_offset = -0.35

    for index in range(int(cloud_count)):
        position = list(balanced_positions[index])
        x, y, z = position
        visual_scale = visual_scales[index]
        shape_variant = shape_variants[index]
        shape_profile = CLOUD_SHAPE_PROFILES[shape_variant]
        cloud_resource_spread = max(
            resource_point_spread,
            visual_scale * 0.55,
        )

        resource_points = []
        for point_index in range(resource_point_count):
            point_angle = math.tau * point_index / resource_point_count
            point_radius = cloud_resource_spread * (0.55 + 0.45 * rng.random())
            resource_points.append(
                [
                    x + math.cos(point_angle) * point_radius,
                    y + resource_point_vertical_offset,
                    z + math.sin(point_angle) * point_radius,
                ]
            )

        clouds.append(
            {
                "id": "cloud_{0:02d}".format(index),
                "position": position,
                "visual_seed": int(seed) * 1009 + index * 9176,
                "visual_scale": visual_scale,
                "shape_variant": shape_variant,
                "shape_profile": shape_profile["name"],
                "nectar_amount": float(nectar_amount),
                "pollen_amount": float(pollen_amount),
                "resource_points": resource_points,
                "maya_object": None,
            }
        )

    return clouds


def apply_wind_offset(position, wind_strength, wind_direction_degrees):
    """Apply horizontal wind drift to a world-space position.

    Parameters:
        position (list[float]): Position as [x, y, z].
        wind_strength (float): Distance to offset the point horizontally.
        wind_direction_degrees (float): Wind direction in degrees, where 0 is +X.

    Returns:
        list[float]: Shifted position as [x, y, z].
    """
    angle_radians = math.radians(wind_direction_degrees)

    # Wind affects only the horizontal XZ plane. The Y value is preserved so the
    # same helper can be used for high cloud points or ground-level landing spots.
    wind_x = math.cos(angle_radians) * wind_strength
    wind_z = math.sin(angle_radians) * wind_strength
    return [position[0] + wind_x, position[1], position[2] + wind_z]


def generate_resource_drops(
    clouds,
    nectar_drop_rate,
    pollen_drop_rate,
    wind_strength,
    wind_direction_degrees,
    spread_radius,
    seed,
):
    """Generate nectar and pollen landing drops from cloud data.

    Parameters:
        clouds (list[dict]): Cloud dictionaries created by create_cloud_data().
        nectar_drop_rate (int): Nectar drops to generate for each cloud.
        pollen_drop_rate (int): Pollen drops to generate for each cloud.
        wind_strength (float): Horizontal wind drift amount.
        wind_direction_degrees (float): Wind direction in degrees, where 0 is +X.
        spread_radius (float): Maximum random horizontal spread for pollen drops.
        seed (int): Random seed for reproducible drop placement.

    Returns:
        list[dict]: Resource drop dictionaries with ground-plane landing positions.
    """
    if spread_radius < 0:
        raise ValueError("spread_radius must be 0 or greater")

    rng = random.Random(seed)
    drops = []
    nectar_count = max(0, int(nectar_drop_rate))
    pollen_count = max(0, int(pollen_drop_rate))
    nectar_spread_ratio = 0.45

    for cloud in clouds:
        cloud_id = cloud["id"]
        emission_points = cloud.get("resource_points") or [cloud["position"]]

        nectar_amount_per_drop = (
            float(cloud.get("nectar_amount", 0.0)) / nectar_count
            if nectar_count
            else 0.0
        )
        pollen_amount_per_drop = (
            float(cloud.get("pollen_amount", 0.0)) / pollen_count
            if pollen_count
            else 0.0
        )

        for index in range(nectar_count):
            source_point = emission_points[index % len(emission_points)]
            landing_position = _create_drop_landing_position(
                source_point,
                spread_radius * nectar_spread_ratio,
                wind_strength,
                wind_direction_degrees,
                rng,
            )
            drops.append(
                {
                    "id": "{0}_nectar_drop_{1:02d}".format(cloud_id, index),
                    "resource_type": "nectar",
                    "position": landing_position,
                    "amount": nectar_amount_per_drop,
                    "source_cloud": cloud_id,
                    "mapped_cell_id": None,
                    "maya_object": None,
                }
            )

        for index in range(pollen_count):
            source_point = emission_points[index % len(emission_points)]
            landing_position = _create_drop_landing_position(
                source_point,
                spread_radius,
                wind_strength,
                wind_direction_degrees,
                rng,
            )
            drops.append(
                {
                    "id": "{0}_pollen_drop_{1:02d}".format(cloud_id, index),
                    "resource_type": "pollen",
                    "position": landing_position,
                    "amount": pollen_amount_per_drop,
                    "source_cloud": cloud_id,
                    "mapped_cell_id": None,
                    "maya_object": None,
                }
            )

    return drops


def _create_drop_landing_position(
    source_point,
    random_spread_radius,
    wind_strength,
    wind_direction_degrees,
    rng,
):
    """Create one ground-plane landing position from a cloud source point.

    Parameters:
        source_point (list[float]): Cloud emission point as [x, y, z].
        random_spread_radius (float): Maximum horizontal random scatter.
        wind_strength (float): Horizontal wind drift amount.
        wind_direction_degrees (float): Wind direction in degrees, where 0 is +X.
        rng (random.Random): Random generator used for deterministic placement.

    Returns:
        list[float]: Ground-plane drop position as [x, y, z].
    """
    scatter_angle = rng.uniform(0.0, math.tau)
    scatter_radius = math.sqrt(rng.random()) * random_spread_radius

    # Drops are projected to y=0 because the honeycomb mapping uses the landing
    # position on the ground plane rather than the cloud's airborne position.
    landing_position = [
        source_point[0] + math.cos(scatter_angle) * scatter_radius,
        0.0,
        source_point[2] + math.sin(scatter_angle) * scatter_radius,
    ]
    return apply_wind_offset(landing_position, wind_strength, wind_direction_degrees)


def distance_2d(pos_a, pos_b):
    """Measure distance between two positions on the XZ ground plane.

    Parameters:
        pos_a (list[float]): First position as [x, y, z].
        pos_b (list[float]): Second position as [x, y, z].

    Returns:
        float: Euclidean distance using x and z only.
    """
    dx = pos_a[0] - pos_b[0]
    dz = pos_a[2] - pos_b[2]
    return math.sqrt((dx * dx) + (dz * dz))


def find_nearest_cell_for_drop(drop, cells):
    """Map one resource drop to the nearest honeycomb cell.

    Parameters:
        drop (dict): Resource drop dictionary with a world-space position.
        cells (list[dict]): Honeycomb cell dictionaries from hive_module.

    Returns:
        dict | None: The nearest cell dictionary, or None when cells is empty.
    """
    if not cells:
        drop["mapped_cell_id"] = None
        return None

    # Drop-to-cell mapping compares only XZ distance because the honeycomb is
    # flat on the ground plane and drop Y height should not affect ownership.
    nearest_cell = min(
        cells,
        key=lambda cell: distance_2d(drop["position"], cell["position"]),
    )
    drop["mapped_cell_id"] = nearest_cell["id"]
    return nearest_cell


def map_drops_to_cells(drops, cells):
    """Map every resource drop to its nearest honeycomb cell.

    Parameters:
        drops (list[dict]): Resource drop dictionaries.
        cells (list[dict]): Honeycomb cell dictionaries from hive_module.

    Returns:
        list[dict]: The same drops list with mapped_cell_id values updated.
    """
    for drop in drops:
        find_nearest_cell_for_drop(drop, cells)
    return drops


def summarize_drop_mapping(drops):
    """Summarize resource drop types and mapping status.

    Parameters:
        drops (list[dict]): Resource drop dictionaries.

    Returns:
        dict: Summary with total, nectar, pollen, and mapped counts.
    """
    summary = {
        "total": len(drops),
        "nectar": 0,
        "pollen": 0,
        "mapped": 0,
    }

    for drop in drops:
        if drop.get("resource_type") == "nectar":
            summary["nectar"] += 1
        elif drop.get("resource_type") == "pollen":
            summary["pollen"] += 1

        if drop.get("mapped_cell_id") is not None:
            summary["mapped"] += 1

    return summary


def _create_maya_material(cmds, material_name, color):
    """Create or reuse a simple Maya lambert material.

    Parameters:
        cmds: Imported maya.cmds module.
        material_name (str): Maya material node name.
        color (tuple[float, float, float]): RGB color in 0..1 range.

    Returns:
        str: Maya material node name.
    """
    if cmds.objExists(material_name):
        if cmds.attributeQuery("color", node=material_name, exists=True):
            cmds.setAttr(material_name + ".color", *color, type="double3")
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
        node (str): Maya transform node name.
        material (str): Maya material node name.

    Returns:
        None.
    """
    cmds.select(node, replace=True)
    cmds.hyperShade(assign=material)
    cmds.select(clear=True)


def _cloud_voxel_noise(ix, iy, iz, seed):
    """Return stable 0..1 noise for one integer voxel coordinate."""
    value = (
        int(ix) * 73856093
        ^ int(iy) * 19349663
        ^ int(iz) * 83492791
        ^ int(seed) * 2654435761
    ) & 0xFFFFFFFF
    value ^= value >> 13
    value = (value * 1274126177) & 0xFFFFFFFF
    value ^= value >> 16
    return float(value & 0xFFFFFFFF) / float(0xFFFFFFFF)


def _retain_largest_cloud_component(voxels):
    """Remove tiny voxel islands created by coarse silhouette erosion."""
    remaining = set(voxels)
    components = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            ix, iy, iz = stack.pop()
            for neighbor in (
                (ix + 1, iy, iz),
                (ix - 1, iy, iz),
                (ix, iy + 1, iz),
                (ix, iy - 1, iz),
                (ix, iy, iz + 1),
                (ix, iy, iz - 1),
            ):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)

    if not components:
        return {}, 0
    largest = max(components, key=len)
    removed_count = len(voxels) - len(largest)
    return {
        key: material_key
        for key, material_key in voxels.items()
        if key in largest
    }, removed_count


def generate_cloud_voxel_data(cloud, cloud_scale=1.0, voxel_pitch=None):
    """Generate one connected cloud as an overlap of many small voxel puffs.

    The footprint is the union of restrained elliptical puffs instead of one
    large ellipse. This creates a scalloped outer silhouette and individually
    readable domes while deterministic overlap keeps the whole cloud connected.
    """
    if cloud_scale <= 0:
        raise ValueError("cloud_scale must be greater than 0")

    if voxel_pitch is not None and float(voxel_pitch) > 0.0:
        # Use the shared coarse cloud grid resolved by create_cloud_geometry().
        pitch = float(voxel_pitch)
    else:
        pitch = float(cloud_scale) / 12.0
    seed = int(cloud.get("visual_seed", 0))
    if not seed:
        digits = "".join(character for character in cloud.get("id", "") if character.isdigit())
        seed = 7001 + (int(digits) if digits else 0) * 9176
    rng = random.Random(seed)

    base_x, base_y, base_z = cloud["position"]
    size = float(cloud_scale) * rng.uniform(0.96, 1.08)
    shape_variant = cloud.get("shape_variant")
    if shape_variant is None:
        digits = "".join(
            character for character in cloud.get("id", "")
            if character.isdigit()
        )
        shape_variant = int(digits) % len(CLOUD_SHAPE_PROFILES) if digits else 0
    shape_variant = int(shape_variant) % len(CLOUD_SHAPE_PROFILES)
    shape_profile = CLOUD_SHAPE_PROFILES[shape_variant]
    half_width = (
        size
        * rng.uniform(1.30, 1.48)
        * shape_profile["width_factor"]
    )
    half_depth = (
        size
        * rng.uniform(0.72, 0.84)
        * shape_profile["depth_factor"]
    )
    vertical_factor = shape_profile["vertical_factor"]
    lobe_anchors = list(shape_profile["anchors"])
    if rng.random() < 0.5:
        lobe_anchors = [
            (-anchor_x, anchor_z, role, required)
            for anchor_x, anchor_z, role, required in lobe_anchors
        ]

    lobes = []
    for anchor_x, anchor_z, role, required in lobe_anchors:
        if not required and rng.random() < 0.38:
            continue
        if role == "peak":
            radius_x = rng.uniform(0.29, 0.36) * half_width
            radius_z = rng.uniform(0.36, 0.47) * half_depth
            center_y = rng.uniform(0.16, 0.24) * size * vertical_factor
            radius_y = rng.uniform(0.62, 0.73) * size * vertical_factor
            jitter = 0.030
        elif role == "high":
            radius_x = rng.uniform(0.27, 0.34) * half_width
            radius_z = rng.uniform(0.34, 0.44) * half_depth
            center_y = rng.uniform(0.10, 0.18) * size * vertical_factor
            radius_y = rng.uniform(0.50, 0.62) * size * vertical_factor
            jitter = 0.035
        elif role == "mid":
            radius_x = rng.uniform(0.24, 0.31) * half_width
            radius_z = rng.uniform(0.31, 0.40) * half_depth
            center_y = rng.uniform(0.01, 0.09) * size * vertical_factor
            radius_y = rng.uniform(0.38, 0.49) * size * vertical_factor
            jitter = 0.045
        else:
            radius_x = rng.uniform(0.22, 0.28) * half_width
            radius_z = rng.uniform(0.29, 0.37) * half_depth
            center_y = rng.uniform(-0.05, 0.01) * size * vertical_factor
            radius_y = rng.uniform(0.27, 0.37) * size * vertical_factor
            jitter = 0.035
        lobes.append({
            "x": (anchor_x + rng.uniform(-jitter, jitter)) * half_width,
            "z": (anchor_z + rng.uniform(-jitter, jitter)) * half_depth,
            "radius_x": radius_x,
            "radius_z": radius_z,
            "center_y": center_y,
            "radius_y": radius_y,
            "role": role,
        })

    local_min_x = min(lobe["x"] - lobe["radius_x"] for lobe in lobes)
    local_max_x = max(lobe["x"] + lobe["radius_x"] for lobe in lobes)
    local_min_z = min(lobe["z"] - lobe["radius_z"] for lobe in lobes)
    local_max_z = max(lobe["z"] + lobe["radius_z"] for lobe in lobes)
    ix_min = int(math.floor((base_x + local_min_x) / pitch)) - 1
    ix_max = int(math.ceil((base_x + local_max_x) / pitch)) + 1
    iz_min = int(math.floor((base_z + local_min_z) / pitch)) - 1
    iz_max = int(math.ceil((base_z + local_max_z) / pitch)) + 1

    voxels = {}
    removed_edge_columns = 0
    chipped_surface_voxels = 0
    for ix in range(ix_min, ix_max + 1):
        world_x = ix * pitch
        local_x = world_x - base_x
        for iz in range(iz_min, iz_max + 1):
            world_z = iz * pitch
            local_z = world_z - base_z
            covering_lobes = []
            for lobe in lobes:
                lobe_distance = (
                    ((local_x - lobe["x"]) / lobe["radius_x"]) ** 2
                    + ((local_z - lobe["z"]) / lobe["radius_z"]) ** 2
                )
                if lobe_distance <= 1.0:
                    vertical_extent = (
                        max(0.0, 1.0 - lobe_distance) ** 0.52
                        * lobe["radius_y"]
                    )
                    covering_lobes.append((
                        lobe_distance,
                        lobe,
                        lobe["center_y"] - vertical_extent,
                        lobe["center_y"] + vertical_extent,
                    ))
            if not covering_lobes:
                continue

            strongest_distance = min(item[0] for item in covering_lobes)
            edge_ratio = math.sqrt(max(0.0, strongest_distance))
            # Each puff owns a complete vertical ellipsoid interval. Filling
            # the union between the lowest and highest overlapping intervals
            # produces a full cumulus volume rather than a shared flat slab.
            bottom_local_y = min(item[2] for item in covering_lobes)
            top_local_y = max(item[3] for item in covering_lobes)

            bottom_layer = int(math.ceil((base_y + bottom_local_y) / pitch - 0.5))
            top_layer = int(math.floor((base_y + top_local_y) / pitch - 0.5))
            if top_layer < bottom_layer:
                top_layer = bottom_layer

            # Break up the mathematically smooth ellipsoid outline with stable,
            # sparse bites. Cuts are concentrated at puff rims, so the cloud
            # stays connected while its silhouette gains natural missing blocks.
            edge_cut_strength = max(0.0, (edge_ratio - 0.66) / 0.34)
            edge_cut_chance = 0.05 + edge_cut_strength * 0.26
            if (
                edge_ratio >= 0.66
                and _cloud_voxel_noise(ix, 0, iz, seed + 149) < edge_cut_chance
            ):
                removed_edge_columns += 1
                continue

            column_height = max(1, top_layer - bottom_layer + 1)
            if column_height >= 4:
                top_chip_chance = 0.07 + edge_ratio * 0.13
                if (
                    _cloud_voxel_noise(ix, top_layer, iz, seed + 307)
                    < top_chip_chance
                ):
                    top_layer -= 1
                    chipped_surface_voxels += 1
                if (
                    top_layer - bottom_layer + 1 >= 6
                    and 0.24 <= edge_ratio <= 0.78
                    and _cloud_voxel_noise(ix, top_layer, iz, seed + 613) < 0.045
                ):
                    top_layer -= 1
                    chipped_surface_voxels += 1
            if (
                top_layer - bottom_layer + 1 >= 4
                and edge_ratio >= 0.58
                and _cloud_voxel_noise(ix, bottom_layer, iz, seed + 887) < 0.09
            ):
                bottom_layer += 1
                chipped_surface_voxels += 1
            if top_layer < bottom_layer:
                continue

            column_height = max(1, top_layer - bottom_layer + 1)
            shadow_field = (
                (local_x / max(0.001, half_width)) * 0.68
                + (local_z / max(0.001, half_depth)) * 0.22
                + math.sin(
                    local_x * 4.7 / max(0.001, size) + seed * 0.017
                ) * 0.10
            )
            is_shadow_patch = shadow_field < -0.38
            for iy in range(bottom_layer, top_layer + 1):
                height_ratio = float(iy - bottom_layer + 1) / column_height
                is_top_voxel = iy == top_layer
                if height_ratio <= 0.17 and is_shadow_patch:
                    material_key = "shadow"
                elif height_ratio <= 0.60:
                    material_key = "mid"
                else:
                    material_key = "light"
                # Peach-colored puff edges visually separate adjacent cream
                # crowns and keep the many-small-clouds structure readable.
                if is_top_voxel and edge_ratio >= 0.66:
                    material_key = "mid"

                # Two-voxel color patches create soft, readable variegation
                # instead of noisy one-cube speckles across the cloud surface.
                patch_noise = _cloud_voxel_noise(
                    ix // 2,
                    iy // 2,
                    iz // 2,
                    seed + 1217,
                )
                detail_noise = _cloud_voxel_noise(ix, iy, iz, seed + 1601)
                if material_key == "light":
                    if patch_noise < 0.17:
                        material_key = "warm"
                    elif patch_noise < 0.29:
                        material_key = "blush"
                    elif detail_noise < 0.035:
                        material_key = "mid"
                elif material_key == "mid":
                    if patch_noise < 0.12:
                        material_key = "blush"
                    elif patch_noise > 0.88:
                        material_key = "warm"
                voxels[(ix, iy, iz)] = material_key
    voxels, removed_island_voxels = _retain_largest_cloud_component(voxels)
    surface_heights = {}
    for ix, iy, iz in voxels:
        surface_heights[(ix, iz)] = max(
            surface_heights.get((ix, iz), float("-inf")),
            (iy + 1.0) * pitch,
        )

    return {
        "pitch": pitch,
        "voxels": voxels,
        "surface_heights": surface_heights,
        "top_y": max(surface_heights.values()) if surface_heights else base_y,
        "lobe_count": len(lobes),
        "shape_variant": shape_variant,
        "shape_profile": shape_profile["name"],
        "removed_edge_columns": removed_edge_columns,
        "chipped_surface_voxels": chipped_surface_voxels,
        "removed_island_voxels": removed_island_voxels,
    }


def create_cloud_geometry(clouds, cloud_scale=1.0, voxel_pitch=None):
    """Create randomly shaped merged-voxel Maya clouds.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so the module can still be imported and tested outside Autodesk Maya.

    Parameters:
        clouds (list[dict]): Cloud dictionaries created by create_cloud_data().
        cloud_scale (float): Visual scale multiplier for each cloud.
        voxel_pitch (float | None): Preferred pixel size, normally the hive pitch.

    Returns:
        list[dict]: The same clouds list with maya_object group names updated.
    """
    import maya.cmds as cmds
    from hive_module import create_merged_voxel_mesh

    if cloud_scale <= 0:
        raise ValueError("cloud_scale must be greater than 0")

    root_group = "CloudHive_Clouds_GRP"
    if not cmds.objExists(root_group):
        cmds.group(empty=True, name=root_group)

    materials = {
        "light": _create_maya_material(
            cmds, "chm_voxel_cloud_cream_MAT", (1.0, 0.91, 0.75)
        ),
        "warm": _create_maya_material(
            cmds, "chm_voxel_cloud_warm_MAT", (1.0, 0.83, 0.57)
        ),
        "blush": _create_maya_material(
            cmds, "chm_voxel_cloud_blush_MAT", (1.0, 0.78, 0.68)
        ),
        "mid": _create_maya_material(
            cmds, "chm_voxel_cloud_peach_MAT", (0.93, 0.68, 0.57)
        ),
        "shadow": _create_maya_material(
            cmds, "chm_voxel_cloud_lavender_MAT", (0.72, 0.68, 0.78)
        ),
    }

    effective_scales = [
        max(0.05, float(cloud.get("visual_scale", cloud_scale)))
        for cloud in clouds
    ]
    resolved_voxel_pitch = voxel_pitch
    if (
        voxel_pitch is not None
        and float(voxel_pitch) > 0.0
        and effective_scales
    ):
        # Clouds occupy much more screen area than one honeycomb cell, so using
        # the exact hive pitch made them visually over-detailed. A 1.85x grid
        # keeps the same pixel language but gives each cloud block more weight.
        resolved_voxel_pitch = max(
            float(voxel_pitch) * 1.85,
            max(effective_scales) / 12.0,
        )

    for cloud, effective_scale in zip(clouds, effective_scales):
        cloud_group = cmds.group(empty=True, name="{0}_cloud_GRP".format(cloud["id"]))
        cmds.parent(cloud_group, root_group)
        voxel_data = generate_cloud_voxel_data(
            cloud,
            cloud_scale=effective_scale,
            voxel_pitch=resolved_voxel_pitch,
        )
        occupied_keys = set(voxel_data["voxels"])
        created_meshes = []
        for material_key in ("shadow", "mid", "blush", "warm", "light"):
            keys = [
                key
                for key, value in voxel_data["voxels"].items()
                if value == material_key
            ]
            if not keys:
                continue
            mesh = create_merged_voxel_mesh(
                keys,
                voxel_data["pitch"],
                "{0}_cloud_voxels_{1}".format(cloud["id"], material_key),
                materials[material_key],
                parent=cloud_group,
                occupied_keys=occupied_keys,
            )
            if mesh:
                created_meshes.append(mesh)

        cloud["maya_object"] = cloud_group
        cloud["voxel_pitch"] = voxel_data["pitch"]
        # Flowers retain the finer hive grid even though their supporting cloud
        # now uses larger blocks.
        cloud["flower_voxel_pitch"] = (
            float(voxel_pitch)
            if voxel_pitch is not None and float(voxel_pitch) > 0.0
            else voxel_data["pitch"]
        )
        cloud["visual_top_y"] = voxel_data["top_y"]
        cloud["visual_surface_heights"] = voxel_data["surface_heights"]
        cloud["visual_meshes"] = created_meshes
        cloud["effective_visual_scale"] = effective_scale
        cloud["generated_lobe_count"] = voxel_data["lobe_count"]
        cloud["generated_shape_profile"] = voxel_data["shape_profile"]
        cloud["removed_edge_columns"] = voxel_data["removed_edge_columns"]
        cloud["chipped_surface_voxels"] = voxel_data["chipped_surface_voxels"]
        cloud["removed_island_voxels"] = voxel_data["removed_island_voxels"]

    return clouds


def _cloud_surface_y(cloud, world_x, world_z):
    """Find the nearest generated voxel-column top for a flower position."""
    pitch = cloud.get("voxel_pitch")
    heights = cloud.get("visual_surface_heights") or {}
    fallback = float(cloud.get("visual_top_y", cloud["position"][1] + 0.45))
    if not pitch or not heights:
        return fallback

    center_ix = int(round(float(world_x) / pitch))
    center_iz = int(round(float(world_z) / pitch))
    for search_radius in range(5):
        candidates = []
        for offset_x in range(-search_radius, search_radius + 1):
            for offset_z in range(-search_radius, search_radius + 1):
                if max(abs(offset_x), abs(offset_z)) != search_radius:
                    continue
                height = heights.get((center_ix + offset_x, center_iz + offset_z))
                if height is not None:
                    candidates.append(height)
        if candidates:
            return max(candidates)
    return fallback


def _rotate_flower_offset(offset_x, offset_z, quarter_turns):
    """Rotate one integer flower-voxel offset around the vertical axis."""
    turns = int(quarter_turns) % 4
    if turns == 1:
        return -offset_z, offset_x
    if turns == 2:
        return -offset_x, -offset_z
    if turns == 3:
        return offset_z, -offset_x
    return offset_x, offset_z


def _put_flower_voxel(voxels, priorities, key, material_key, priority):
    """Write one flower voxel, allowing petals to replace intersecting leaves."""
    if priority >= priorities.get(key, -1):
        voxels[key] = material_key
        priorities[key] = priority


def _add_stem_and_leaves(
    voxels,
    priorities,
    base_key,
    stem_height,
    quarter_turns,
):
    """Add a block stem and two rising leaf sprays in a reference-like V."""
    base_ix, base_iy, base_iz = base_key

    def put(offset_x, offset_y, offset_z, material_key, priority=10):
        rotated_x, rotated_z = _rotate_flower_offset(
            offset_x,
            offset_z,
            quarter_turns,
        )
        _put_flower_voxel(
            voxels,
            priorities,
            (base_ix + rotated_x, base_iy + offset_y, base_iz + rotated_z),
            material_key,
            priority,
        )

    for offset_y in range(max(1, int(stem_height))):
        material_key = "stem_light" if offset_y % 4 == 2 else "stem"
        put(0, offset_y, 0, material_key)

    leaf_offsets = (
        (-1, 2, 0, "leaf"),
        (-1, 3, 0, "leaf"),
        (-2, 3, 0, "leaf"),
        (-2, 3, 1, "leaf_light"),
        (-1, 4, 0, "leaf_light"),
        (1, 2, 0, "leaf"),
        (1, 3, 0, "leaf"),
        (2, 3, 0, "leaf"),
        (2, 3, -1, "leaf_light"),
        (1, 4, 0, "leaf_light"),
    )
    for offset_x, offset_y, offset_z, material_key in leaf_offsets:
        if offset_y < stem_height:
            put(offset_x, offset_y, offset_z, material_key)

    return put


def _petal_shade(offset_x, offset_z, material_keys):
    """Pick a deterministic highlight/main/shadow shade across one bloom."""
    light_key, main_key, shadow_key = material_keys
    shade_score = offset_x - offset_z
    if shade_score <= -1:
        return light_key
    if shade_score >= 2:
        return shadow_key
    return main_key


def _add_flat_bloom(
    put,
    center_offset,
    petal_offsets,
    material_keys,
    center_material="center_gold",
    thick=True,
):
    """Create a horizontal pixel bloom with a colored underside and gold core."""
    center_x, center_y, center_z = center_offset
    shadow_key = material_keys[2]
    for petal_x, petal_z in petal_offsets:
        if thick:
            put(
                center_x + petal_x,
                center_y - 1,
                center_z + petal_z,
                shadow_key,
                priority=20,
            )
        put(
            center_x + petal_x,
            center_y,
            center_z + petal_z,
            _petal_shade(petal_x, petal_z, material_keys),
            priority=22,
        )
    put(center_x, center_y, center_z, center_material, priority=30)


def _add_flower_archetype(
    voxels,
    priorities,
    base_key,
    flower_type,
    quarter_turns,
):
    """Build one of the six reference flower silhouettes on an integer grid."""
    if flower_type == "yellow_cluster":
        put = _add_stem_and_leaves(
            voxels,
            priorities,
            base_key,
            stem_height=10,
            quarter_turns=quarter_turns,
        )
        branch_offsets = (
            (-1, 5, 0),
            (-1, 6, 0),
            (-2, 6, 0),
            (-2, 7, 0),
            (-3, 7, 0),
            (1, 5, 0),
            (1, 6, 0),
            (2, 6, 0),
            (2, 7, 0),
            (3, 7, 0),
        )
        for offset_x, offset_y, offset_z in branch_offsets:
            put(offset_x, offset_y, offset_z, "stem_light")
        small_petals = (
            (-1, 0), (1, 0), (0, -1), (0, 1),
            (-1, 1), (1, -1),
        )
        for bloom_center in ((-3, 8, 0), (0, 10, 0), (3, 8, 0)):
            _add_flat_bloom(
                put,
                bloom_center,
                small_petals,
                ("yellow_light", "yellow", "yellow_shadow"),
                thick=False,
            )
        return

    if flower_type == "lavender":
        put = _add_stem_and_leaves(
            voxels,
            priorities,
            base_key,
            stem_height=10,
            quarter_turns=quarter_turns,
        )
        spike_voxels = (
            (-1, 5, 0, "lavender_shadow"),
            (0, 5, 1, "lavender"),
            (1, 6, 0, "lavender_shadow"),
            (0, 6, -1, "lavender_light"),
            (-1, 7, 0, "lavender_light"),
            (0, 7, 1, "lavender"),
            (1, 8, 0, "lavender_shadow"),
            (0, 8, -1, "lavender_light"),
            (-1, 9, 0, "lavender_light"),
            (0, 9, 1, "lavender"),
            (0, 10, 0, "lavender_light"),
        )
        for offset_x, offset_y, offset_z, material_key in spike_voxels:
            put(offset_x, offset_y, offset_z, material_key, priority=22)
        return

    stem_heights = {
        "pink": 8,
        "daisy": 8,
        "blue": 7,
        "orange": 8,
    }
    put = _add_stem_and_leaves(
        voxels,
        priorities,
        base_key,
        stem_height=stem_heights[flower_type],
        quarter_turns=quarter_turns,
    )
    head_y = stem_heights[flower_type]

    if flower_type == "pink":
        petal_offsets = (
            (-2, 0), (-1, 0), (1, 0), (2, 0),
            (0, -2), (0, -1), (0, 1), (0, 2),
            (-1, -1), (-1, 1), (1, -1), (1, 1),
        )
        _add_flat_bloom(
            put,
            (0, head_y, 0),
            petal_offsets,
            ("pink_light", "pink", "pink_shadow"),
        )
    elif flower_type == "daisy":
        petal_offsets = (
            (-2, 0), (-1, 0), (1, 0), (2, 0),
            (0, -2), (0, -1), (0, 1), (0, 2),
            (-1, -1), (1, 1),
        )
        _add_flat_bloom(
            put,
            (0, head_y, 0),
            petal_offsets,
            ("daisy_light", "daisy", "daisy_shadow"),
        )
    elif flower_type == "blue":
        petal_offsets = (
            (-1, 0), (1, 0), (0, -1), (0, 1),
            (-1, -1), (-1, 1), (1, -1), (1, 1),
        )
        _add_flat_bloom(
            put,
            (0, head_y, 0),
            petal_offsets,
            ("blue_light", "blue", "blue_shadow"),
        )
    elif flower_type == "orange":
        lower_ring = (
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1), (0, 0), (0, 1),
            (1, -1), (1, 0), (1, 1),
        )
        for offset_x, offset_z in lower_ring:
            put(
                offset_x,
                head_y - 1,
                offset_z,
                "orange_shadow",
                priority=20,
            )
            put(
                offset_x,
                head_y,
                offset_z,
                _petal_shade(
                    offset_x,
                    offset_z,
                    ("orange_light", "orange", "orange_shadow"),
                ),
                priority=22,
            )
        for offset_x, offset_z in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            put(offset_x, head_y + 1, offset_z, "orange", priority=22)
        put(0, head_y + 1, 0, "yellow_light", priority=30)


def _select_cloud_flower_columns(cloud, flower_count):
    """Choose separated, interior cloud-top columns for flower placement."""
    count = max(0, int(flower_count))
    if count == 0:
        return []

    cloud_pitch = float(cloud.get("voxel_pitch") or 0.075)
    flower_pitch = float(cloud.get("flower_voxel_pitch") or cloud_pitch)
    heights = cloud.get("visual_surface_heights") or {}
    rng = random.Random(int(cloud.get("visual_seed", 0)) + 4049)
    if not heights:
        resource_points = cloud.get("resource_points") or [cloud["position"]]
        columns = []
        for index in range(count):
            point = resource_points[index % len(resource_points)]
            world_x = point[0] + rng.uniform(-0.7, 0.7) * flower_pitch
            world_z = point[2] + rng.uniform(-0.7, 0.7) * flower_pitch
            columns.append((
                int(round(world_x / flower_pitch)),
                int(round(
                    _cloud_surface_y(cloud, world_x, world_z) / flower_pitch
                )),
                int(round(world_z / flower_pitch)),
            ))
        return columns

    candidates = []
    for (ix, iz), height in heights.items():
        neighbor_count = sum(
            (ix + offset_x, iz + offset_z) in heights
            for offset_x, offset_z in ((-1, 0), (1, 0), (0, -1), (0, 1))
        )
        if neighbor_count >= 3:
            candidates.append((ix, iz, height))
    if not candidates:
        candidates = [(ix, iz, height) for (ix, iz), height in heights.items()]

    min_ix = min(item[0] for item in candidates)
    max_ix = max(item[0] for item in candidates)
    min_iz = min(item[1] for item in candidates)
    max_iz = max(item[1] for item in candidates)
    center_ix = (min_ix + max_ix) * 0.5
    center_iz = (min_iz + max_iz) * 0.5
    radius_ix = max(1.0, (max_ix - min_ix) * 0.5)
    radius_iz = max(1.0, (max_iz - min_iz) * 0.5)
    anchor_pattern = (
        (-0.50, 0.10),
        (0.50, 0.14),
        (0.00, 0.48),
        (-0.28, -0.38),
        (0.30, -0.38),
        (0.00, 0.00),
        (-0.62, -0.24),
        (0.62, -0.20),
        (-0.30, 0.44),
        (0.32, 0.46),
    )
    if rng.random() < 0.5:
        anchor_pattern = tuple((-x, z) for x, z in anchor_pattern)

    selected = []
    available = list(candidates)
    minimum_spacing = max(2.0, 4.25 * flower_pitch / cloud_pitch)
    for index in range(count):
        anchor_x, anchor_z = anchor_pattern[index % len(anchor_pattern)]
        target_ix = center_ix + anchor_x * radius_ix
        target_iz = center_iz + anchor_z * radius_iz
        spaced = [
            item
            for item in available
            if all(
                (item[0] - chosen[0]) ** 2 + (item[1] - chosen[1]) ** 2
                >= minimum_spacing ** 2
                for chosen in selected
            )
        ]
        pool = spaced or available
        if not pool:
            break
        chosen = min(
            pool,
            key=lambda item: (
                (item[0] - target_ix) ** 2 + (item[1] - target_iz) ** 2,
                -item[2],
                item[0],
                item[1],
            ),
        )
        selected.append(chosen)
        available.remove(chosen)

    return [
        (
            int(round(ix * cloud_pitch / flower_pitch)),
            int(round(height / flower_pitch)),
            int(round(iz * cloud_pitch / flower_pitch)),
        )
        for ix, iz, height in selected
    ]


def generate_cloud_flower_voxel_data(cloud, flowers_per_cloud=5):
    """Generate six distinct reference-inspired voxel flower archetypes."""
    flower_count = max(0, int(flowers_per_cloud))
    columns = _select_cloud_flower_columns(cloud, flower_count)
    seed = int(cloud.get("visual_seed", 0)) + 8123
    rng = random.Random(seed)
    # Offset the six-type cycle directly from the deterministic seed so nearby
    # clouds cannot coincidentally receive the same color sequence.
    start_type = seed % len(FLOWER_ARCHETYPES)
    voxels = {}
    priorities = {}
    flowers = []

    for index, base_key in enumerate(columns):
        flower_type = FLOWER_ARCHETYPES[
            (start_type + index) % len(FLOWER_ARCHETYPES)
        ]
        quarter_turns = rng.randrange(4)
        _add_flower_archetype(
            voxels,
            priorities,
            base_key,
            flower_type,
            quarter_turns,
        )
        flowers.append({
            "type": flower_type,
            "base_key": base_key,
            "quarter_turns": quarter_turns,
        })

    return {
        "pitch": float(
            cloud.get("flower_voxel_pitch")
            or cloud.get("voxel_pitch")
            or 0.075
        ),
        "voxels": voxels,
        "flowers": flowers,
    }


def create_flower_geometry_on_clouds(clouds, flowers_per_cloud=5):
    """Create six reference-inspired voxel flower types on every cloud.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so the module can still be imported and tested outside Autodesk Maya.

    Parameters:
        clouds (list[dict]): Cloud dictionaries created by create_cloud_data().
        flowers_per_cloud (int): Number of voxel flowers to add to each cloud.

    Returns:
        list[str]: Maya object names created for flower groups.
    """
    import maya.cmds as cmds

    flower_count = max(0, int(flowers_per_cloud))
    created_groups = []

    root_group = "CloudHive_CloudFlowers_GRP"
    if not cmds.objExists(root_group):
        cmds.group(empty=True, name=root_group)

    from hive_module import create_merged_voxel_mesh

    material_specs = {
        "stem": ("chm_flower_stem_green_MAT", (0.22, 0.42, 0.07)),
        "stem_light": ("chm_flower_stem_light_MAT", (0.36, 0.58, 0.10)),
        "leaf": ("chm_flower_leaf_green_MAT", (0.30, 0.52, 0.08)),
        "leaf_light": ("chm_flower_leaf_light_MAT", (0.48, 0.66, 0.12)),
        "center_gold": ("chm_flower_center_gold_MAT", (1.0, 0.70, 0.04)),
        "pink_light": ("chm_flower_pink_light_MAT", (1.0, 0.62, 0.78)),
        "pink": ("chm_flower_pink_MAT", (0.96, 0.36, 0.64)),
        "pink_shadow": ("chm_flower_pink_shadow_MAT", (0.76, 0.22, 0.48)),
        "daisy_light": ("chm_flower_daisy_light_MAT", (1.0, 0.98, 0.86)),
        "daisy": ("chm_flower_daisy_MAT", (0.94, 0.91, 0.81)),
        "daisy_shadow": ("chm_flower_daisy_shadow_MAT", (0.75, 0.72, 0.68)),
        "yellow_light": ("chm_flower_yellow_light_MAT", (1.0, 0.86, 0.18)),
        "yellow": ("chm_flower_yellow_MAT", (1.0, 0.68, 0.02)),
        "yellow_shadow": ("chm_flower_yellow_shadow_MAT", (0.82, 0.48, 0.01)),
        "lavender_light": ("chm_flower_lavender_light_MAT", (0.72, 0.50, 0.88)),
        "lavender": ("chm_flower_lavender_MAT", (0.52, 0.29, 0.74)),
        "lavender_shadow": ("chm_flower_lavender_shadow_MAT", (0.35, 0.18, 0.58)),
        "blue_light": ("chm_flower_blue_light_MAT", (0.48, 0.75, 0.94)),
        "blue": ("chm_flower_blue_MAT", (0.28, 0.58, 0.84)),
        "blue_shadow": ("chm_flower_blue_shadow_MAT", (0.18, 0.39, 0.68)),
        "orange_light": ("chm_flower_orange_light_MAT", (1.0, 0.62, 0.08)),
        "orange": ("chm_flower_orange_MAT", (0.96, 0.40, 0.01)),
        "orange_shadow": ("chm_flower_orange_shadow_MAT", (0.72, 0.24, 0.01)),
    }
    materials = {
        key: _create_maya_material(cmds, material_name, color)
        for key, (material_name, color) in material_specs.items()
    }

    for cloud in clouds:
        cloud_group = cmds.group(empty=True, name="{0}_flowers_GRP".format(cloud["id"]))
        cmds.parent(cloud_group, root_group)
        created_groups.append(cloud_group)
        flower_data = generate_cloud_flower_voxel_data(
            cloud,
            flowers_per_cloud=flower_count,
        )
        occupied_keys = set(flower_data["voxels"])
        flower_meshes = []
        for material_key, material in materials.items():
            keys = [
                key
                for key, value in flower_data["voxels"].items()
                if value == material_key
            ]
            if not keys:
                continue
            mesh = create_merged_voxel_mesh(
                keys,
                flower_data["pitch"],
                "{0}_flower_voxels_{1}".format(cloud["id"], material_key),
                material,
                parent=cloud_group,
                occupied_keys=occupied_keys,
            )
            if mesh:
                flower_meshes.append(mesh)
        cloud["flower_types"] = [
            flower["type"] for flower in flower_data["flowers"]
        ]
        cloud["flower_meshes"] = flower_meshes

    return created_groups


def create_drop_particles(drops):
    """Create simple Maya visual markers for nectar and pollen drops.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so the module can still be imported and tested outside Autodesk Maya.

    Parameters:
        drops (list[dict]): Resource drop dictionaries.

    Returns:
        list[dict]: The same drops list with maya_object names updated.
    """
    import maya.cmds as cmds

    root_group = "CloudHive_ResourceDrops_GRP"
    if not cmds.objExists(root_group):
        cmds.group(empty=True, name=root_group)

    material_by_type = {
        "nectar": _create_maya_material(cmds, "chm_drop_nectar_gold_MAT", (1.0, 0.64, 0.05)),
        "pollen": _create_maya_material(cmds, "chm_drop_pollen_orange_MAT", (1.0, 0.48, 0.05)),
    }
    marker_radius = 0.12
    marker_y_offset = 0.18

    for drop in drops:
        x, y, z = drop["position"]
        marker_name = "{0}_marker".format(drop["id"])
        marker, _shape = cmds.polySphere(radius=marker_radius, name=marker_name)
        cmds.xform(marker, translation=(x, y + marker_y_offset, z), worldSpace=True)
        cmds.parent(marker, root_group)

        material = material_by_type.get(drop.get("resource_type"), material_by_type["nectar"])
        _assign_maya_material(cmds, marker, material)
        drop["maya_object"] = marker

    return drops


if __name__ == "__main__":
    from hive_module import assign_cell_types, calculate_neighbors, generate_hex_grid

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

    clouds = create_cloud_data(
        cloud_count=3,
        scene_radius=5.0,
        min_height=4.0,
        max_height=6.0,
        nectar_amount=0.8,
        pollen_amount=0.6,
        seed=10,
    )

    drops = generate_resource_drops(
        clouds,
        nectar_drop_rate=3,
        pollen_drop_rate=3,
        wind_strength=1.0,
        wind_direction_degrees=45,
        spread_radius=1.2,
        seed=20,
    )

    map_drops_to_cells(drops, cells)

    print("Clouds:")
    for cloud in clouds:
        print(cloud)

    print("Drop mapping summary:")
    print(summarize_drop_mapping(drops))

    print("First mapped drops:")
    for drop in drops[:5]:
        print(drop)
