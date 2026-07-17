"""Maya visualization layer for the Cloud-Hive Meadow MVP."""

from bee_task_module import create_bee_geometry, create_task_path_visuals
from cloud_resource_module import (
    create_cloud_geometry,
    create_drop_particles,
    create_flower_geometry_on_clouds,
)
from hive_module import create_honeycomb_geometry
from main import load_parameters, run_simulation


ROOT_GROUP = "CloudHive_Visualization_GRP"


def create_maya_scene(config=None):
    """Create the first Maya visualization MVP for Cloud-Hive Meadow.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so this module can still be compiled and imported outside Autodesk Maya.

    Parameters:
        config (dict | None): Optional integration parameter dictionary. When
            None, defaults are loaded from code/config.py through main.py.

    Returns:
        dict: Dictionary containing cells, clouds, drops, tasks, bees, and summary.
    """
    import maya.cmds as cmds

    parameters = config or load_parameters()
    simulation = run_simulation(parameters)

    cells = simulation["cells"]
    clouds = simulation["clouds"]
    drops = simulation["drops"]
    tasks = simulation["tasks"]
    bees = simulation["bees"]

    clear_scene()
    cmds.group(empty=True, name=ROOT_GROUP)

    visual_params = parameters.get("visual", {})
    hive_params = parameters["hive"]
    cloud_params = parameters["clouds"]

    ground_radius = visual_params.get(
        "ground_radius",
        max(cloud_params["scene_radius"] * 1.8, hive_params["size"] * hive_params["cell_size"] * 3.0),
    )
    cell_depth = visual_params.get("cell_depth", 0.35)
    cloud_scale = visual_params.get("cloud_scale", 0.85)
    flowers_per_cloud = visual_params.get("flowers_per_cloud", 5)
    bee_scale = visual_params.get("bee_scale", 1.0)

    create_ground_plane(ground_radius)
    create_honeycomb_geometry(cells, hive_params["cell_size"], cell_depth)
    create_cloud_geometry(clouds, cloud_scale=cloud_scale)
    create_flower_geometry_on_clouds(clouds, flowers_per_cloud=flowers_per_cloud)
    create_drop_particles(drops)
    create_bee_geometry(bees, bee_scale=bee_scale)
    create_task_path_visuals(tasks, cells)
    setup_camera_and_lighting(ground_radius)
    create_scene_labels_optional(simulation["summary"])
    _parent_known_scene_groups()

    print("Cloud-Hive Meadow Maya visualization created.")
    print("Cells: {0}, Clouds: {1}, Drops: {2}, Tasks: {3}, Bees: {4}".format(
        len(cells),
        len(clouds),
        len(drops),
        len(tasks),
        len(bees),
    ))

    return {
        "cells": cells,
        "clouds": clouds,
        "drops": drops,
        "tasks": tasks,
        "bees": bees,
        "summary": simulation["summary"],
        "completed_tasks": simulation["completed_tasks"],
    }


def clear_scene():
    """Remove previous Cloud-Hive Meadow generated objects from the Maya scene.

    Parameters:
        None.

    Returns:
        None.
    """
    import maya.cmds as cmds

    groups_to_delete = [
        ROOT_GROUP,
        "CloudHive_Honeycomb_GRP",
        "CloudHive_Clouds_GRP",
        "CloudHive_CloudFlowers_GRP",
        "CloudHive_ResourceDrops_GRP",
        "CloudHive_Bees_GRP",
        "CloudHive_BeeTaskPaths_GRP",
        "CloudHive_Ground_GRP",
        "CloudHive_CameraLight_GRP",
        "CloudHive_Labels_GRP",
        "CloudHiveMeadow_GRP",
    ]

    for group_name in groups_to_delete:
        if cmds.objExists(group_name):
            cmds.delete(group_name)


def setup_camera_and_lighting(scene_radius=9.0):
    """Create a simple Maya camera and light setup.

    Parameters:
        scene_radius (float): Approximate radius used to position camera/lights.

    Returns:
        dict: Names of created camera, directional light, and ambient light nodes.
    """
    import maya.cmds as cmds

    group_name = "CloudHive_CameraLight_GRP"
    if not cmds.objExists(group_name):
        cmds.group(empty=True, name=group_name)

    camera_distance = max(6.0, float(scene_radius))
    camera_transform, camera_shape = cmds.camera(name="CloudHive_Render_CAM")
    cmds.xform(
        camera_transform,
        translation=(camera_distance * 0.85, camera_distance * 0.65, camera_distance),
        rotation=(-35.0, 38.0, 0.0),
        worldSpace=True,
    )
    cmds.setAttr(camera_shape + ".focalLength", 35)
    cmds.parent(camera_transform, group_name)

    sun_shape = cmds.directionalLight(name="CloudHive_Sun_LGT", intensity=1.15)
    sun_light = cmds.listRelatives(sun_shape, parent=True)[0]
    cmds.xform(sun_light, rotation=(-45.0, -30.0, 0.0), worldSpace=True)
    cmds.parent(sun_light, group_name)

    ambient_shape = cmds.ambientLight(name="CloudHive_Ambient_LGT", intensity=0.35)
    ambient_light = cmds.listRelatives(ambient_shape, parent=True)[0]
    cmds.parent(ambient_light, group_name)

    try:
        cmds.lookThru(camera_transform)
    except RuntimeError:
        pass

    return {
        "camera": camera_transform,
        "camera_shape": camera_shape,
        "sun_light": sun_light,
        "sun_shape": sun_shape,
        "ambient_light": ambient_light,
        "ambient_shape": ambient_shape,
    }


def create_ground_plane(scene_radius=9.0):
    """Create a simple ground plane under the honeycomb scene.

    Parameters:
        scene_radius (float): Approximate half-size for the ground plane.

    Returns:
        str: Maya transform name for the ground plane.
    """
    import maya.cmds as cmds

    group_name = "CloudHive_Ground_GRP"
    if not cmds.objExists(group_name):
        cmds.group(empty=True, name=group_name)

    ground_size = max(4.0, float(scene_radius) * 2.0)
    ground, _shape = cmds.polyPlane(
        width=ground_size,
        height=ground_size,
        subdivisionsX=1,
        subdivisionsY=1,
        name="CloudHive_Ground_PLN",
    )
    cmds.xform(ground, translation=(0.0, -0.02, 0.0), worldSpace=True)
    cmds.parent(ground, group_name)

    material = _create_maya_material(cmds, "chm_visual_ground_green_MAT", (0.24, 0.46, 0.26))
    _assign_maya_material(cmds, ground, material)
    return ground


def create_scene_labels_optional(summary=None):
    """Create optional Maya text labels for presentation/debugging.

    Parameters:
        summary (dict | None): Optional summary dictionary from main.run_simulation().

    Returns:
        list[str]: Maya object names created for labels.
    """
    import maya.cmds as cmds

    group_name = "CloudHive_Labels_GRP"
    if not cmds.objExists(group_name):
        cmds.group(empty=True, name=group_name)

    if summary is None:
        label_text = "Cloud-Hive Meadow"
    else:
        label_text = (
            "Cloud-Hive Meadow\\n"
            "Cells: {0}  Drops: {1}\\n"
            "Tasks: {2}  Paths: {3}"
        ).format(
            summary.get("cell_count", 0),
            summary.get("drop_count", 0),
            summary.get("task_count", 0),
            summary.get("tasks_with_paths", 0),
        )

    text_nodes = cmds.textCurves(
        font="Arial",
        text=label_text,
        name="CloudHive_Summary_Label",
    )
    created = text_nodes if isinstance(text_nodes, list) else [text_nodes]
    for node in created:
        if cmds.objExists(node):
            cmds.xform(node, translation=(-5.8, 0.05, -6.3), rotation=(90.0, 0.0, 0.0), worldSpace=True)
            cmds.scale(0.25, 0.25, 0.25, node, relative=True)
            cmds.parent(node, group_name)

    return created


def _create_maya_material(cmds, material_name, color):
    """Create or reuse a Maya lambert material.

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
        node (str): Maya object name.
        material (str): Maya material node name.

    Returns:
        None.
    """
    cmds.select(node, replace=True)
    cmds.hyperShade(assign=material)
    cmds.select(clear=True)


def _parent_known_scene_groups():
    """Parent generated CloudHive groups under the visualization root group.

    Parameters:
        None.

    Returns:
        None.
    """
    import maya.cmds as cmds

    if not cmds.objExists(ROOT_GROUP):
        return

    generated_groups = [
        "CloudHive_Honeycomb_GRP",
        "CloudHive_Clouds_GRP",
        "CloudHive_CloudFlowers_GRP",
        "CloudHive_ResourceDrops_GRP",
        "CloudHive_Bees_GRP",
        "CloudHive_BeeTaskPaths_GRP",
        "CloudHive_Ground_GRP",
        "CloudHive_CameraLight_GRP",
        "CloudHive_Labels_GRP",
    ]

    for group_name in generated_groups:
        if not cmds.objExists(group_name):
            continue
        parent = cmds.listRelatives(group_name, parent=True)
        if parent and parent[0] == ROOT_GROUP:
            continue
        try:
            cmds.parent(group_name, ROOT_GROUP)
        except RuntimeError:
            pass
