"""Cloud resource generation and Maya visualization helpers for Cloud-Hive Meadow."""

import math
import random


def create_cloud_data(
    cloud_count,
    scene_radius,
    min_height,
    max_height,
    nectar_amount,
    pollen_amount,
    seed,
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

    resource_point_count = 5
    resource_point_spread = max(scene_radius * 0.12, 0.25)
    resource_point_vertical_offset = -0.35

    for index in range(int(cloud_count)):
        angle = rng.uniform(0.0, math.tau)
        radius = math.sqrt(rng.random()) * scene_radius
        x = math.cos(angle) * radius
        y = rng.uniform(min_height, max_height)
        z = math.sin(angle) * radius
        position = [x, y, z]

        resource_points = []
        for point_index in range(resource_point_count):
            point_angle = math.tau * point_index / resource_point_count
            point_radius = resource_point_spread * (0.55 + 0.45 * rng.random())
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


def create_cloud_geometry(clouds, cloud_scale=1.0):
    """Create stylized Maya cloud geometry from cloud dictionaries.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so the module can still be imported and tested outside Autodesk Maya.

    Parameters:
        clouds (list[dict]): Cloud dictionaries created by create_cloud_data().
        cloud_scale (float): Visual scale multiplier for cloud sphere clusters.

    Returns:
        list[dict]: The same clouds list with maya_object group names updated.
    """
    import maya.cmds as cmds

    if cloud_scale <= 0:
        raise ValueError("cloud_scale must be greater than 0")

    root_group = "CloudHive_Clouds_GRP"
    if not cmds.objExists(root_group):
        cmds.group(empty=True, name=root_group)

    cloud_material = _create_maya_material(cmds, "chm_cloud_soft_white_MAT", (0.88, 0.92, 0.96))
    sphere_offsets = [
        (0.0, 0.0, 0.0, 0.85),
        (-0.55, 0.0, 0.05, 0.6),
        (0.55, 0.0, 0.02, 0.65),
        (-0.2, 0.25, -0.25, 0.55),
        (0.3, 0.22, 0.25, 0.5),
    ]

    for cloud in clouds:
        cloud_group = cmds.group(empty=True, name="{0}_cloud_GRP".format(cloud["id"]))
        cmds.parent(cloud_group, root_group)
        base_x, base_y, base_z = cloud["position"]

        for index, (offset_x, offset_y, offset_z, radius) in enumerate(sphere_offsets):
            sphere_name = "{0}_cloud_sphere_{1:02d}".format(cloud["id"], index)
            sphere, _shape = cmds.polySphere(
                radius=radius * cloud_scale,
                name=sphere_name,
            )
            cmds.xform(
                sphere,
                translation=(
                    base_x + offset_x * cloud_scale,
                    base_y + offset_y * cloud_scale,
                    base_z + offset_z * cloud_scale,
                ),
                worldSpace=True,
            )
            cmds.parent(sphere, cloud_group)
            _assign_maya_material(cmds, sphere, cloud_material)

        cloud["maya_object"] = cloud_group

    return clouds


def create_flower_geometry_on_clouds(clouds, flowers_per_cloud=5):
    """Create simple stylized Maya flowers on top of each cloud.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so the module can still be imported and tested outside Autodesk Maya.

    Parameters:
        clouds (list[dict]): Cloud dictionaries created by create_cloud_data().
        flowers_per_cloud (int): Number of simple flowers to add to each cloud.

    Returns:
        list[str]: Maya object names created for flower groups.
    """
    import maya.cmds as cmds

    flower_count = max(0, int(flowers_per_cloud))
    created_groups = []

    root_group = "CloudHive_CloudFlowers_GRP"
    if not cmds.objExists(root_group):
        cmds.group(empty=True, name=root_group)

    stem_material = _create_maya_material(cmds, "chm_flower_stem_green_MAT", (0.16, 0.48, 0.18))
    petal_material = _create_maya_material(cmds, "chm_flower_petal_pink_MAT", (1.0, 0.48, 0.72))
    center_material = _create_maya_material(cmds, "chm_flower_center_gold_MAT", (1.0, 0.72, 0.08))

    stem_height = 0.35
    petal_count = 5
    petal_radius = 0.055
    center_radius = 0.07

    for cloud in clouds:
        cloud_group = cmds.group(empty=True, name="{0}_flowers_GRP".format(cloud["id"]))
        cmds.parent(cloud_group, root_group)
        created_groups.append(cloud_group)

        resource_points = cloud.get("resource_points") or [cloud["position"]]
        for index in range(flower_count):
            point = resource_points[index % len(resource_points)]
            flower_x = point[0]
            flower_y = cloud["position"][1] + 0.45
            flower_z = point[2]

            stem, _stem_shape = cmds.polyCylinder(
                radius=0.025,
                height=stem_height,
                subdivisionsX=8,
                name="{0}_flower_{1:02d}_stem".format(cloud["id"], index),
            )
            cmds.xform(
                stem,
                translation=(flower_x, flower_y + stem_height * 0.5, flower_z),
                worldSpace=True,
            )
            cmds.parent(stem, cloud_group)
            _assign_maya_material(cmds, stem, stem_material)

            center_y = flower_y + stem_height
            center, _center_shape = cmds.polySphere(
                radius=center_radius,
                name="{0}_flower_{1:02d}_center".format(cloud["id"], index),
            )
            cmds.xform(center, translation=(flower_x, center_y, flower_z), worldSpace=True)
            cmds.parent(center, cloud_group)
            _assign_maya_material(cmds, center, center_material)

            for petal_index in range(petal_count):
                petal_angle = math.tau * petal_index / petal_count
                petal_offset = center_radius + petal_radius
                petal, _petal_shape = cmds.polySphere(
                    radius=petal_radius,
                    name="{0}_flower_{1:02d}_petal_{2:02d}".format(
                        cloud["id"],
                        index,
                        petal_index,
                    ),
                )
                cmds.xform(
                    petal,
                    translation=(
                        flower_x + math.cos(petal_angle) * petal_offset,
                        center_y,
                        flower_z + math.sin(petal_angle) * petal_offset,
                    ),
                    worldSpace=True,
                )
                cmds.parent(petal, cloud_group)
                _assign_maya_material(cmds, petal, petal_material)

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
