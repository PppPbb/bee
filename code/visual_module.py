"""Maya visualization layer for the Cloud-Hive Meadow MVP."""

import math
import random

from bee_task_module import (
    animate_bee_collection_cycle,
    create_bee_geometry,
    create_task_path_visuals,
)
from cloud_resource_module import (
    create_cloud_geometry,
    create_flower_geometry_on_clouds,
)
from hive_module import create_honeycomb_geometry
from main import load_parameters, run_simulation


ROOT_GROUP = "CloudHive_Visualization_GRP"


def create_maya_scene(config=None, prior_cell_state=None):
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
    simulation = run_simulation(parameters, prior_cell_state=prior_cell_state)

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
    show_paths = visual_params.get("show_paths", True)
    create_honeycomb_geometry(cells, hive_params["cell_size"], cell_depth)
    create_cloud_geometry(clouds, cloud_scale=cloud_scale)
    create_flower_geometry_on_clouds(clouds, flowers_per_cloud=flowers_per_cloud)
    frame_duration_multiplier = max(
        0.01,
        float(visual_params.get("frame_duration_multiplier", 4.0)),
    )
    animation_end = int(visual_params.get("animation_end", 320) * frame_duration_multiplier)
    drop_fall_frames = int(visual_params.get("drop_fall_frames", 64) * frame_duration_multiplier)
    bee_frame_step = int(visual_params.get("bee_frame_step", 22) * frame_duration_multiplier)
    scheduled_end = schedule_task_animation(
        bees,
        tasks,
        drops,
        fall_duration=drop_fall_frames,
        frame_step=bee_frame_step,
    )
    animation_end = max(animation_end, scheduled_end)
    create_falling_resource_effects(
        drops,
        clouds,
        end_frame=animation_end,
        fall_duration=drop_fall_frames,
    )
    create_bee_geometry(bees, bee_scale=bee_scale)
    if show_paths:
        create_task_path_visuals(tasks, cells)
    animation_records = animate_assigned_bees(
        bees,
        tasks,
        cells,
        clouds,
        drops,
        frame_step=bee_frame_step,
    )
    resource_visuals = create_cell_resource_visuals(
        cells,
        simulation["resource_events"],
        animation_records,
        cell_size=hive_params["cell_size"],
        cell_depth=cell_depth,
    )
    blocked_visuals = create_blocked_task_visuals(
        tasks,
        cells,
        animation_end=animation_end,
    )
    latest_worker_frame = max(
        (max(record["frames"]) for record in animation_records if record["frames"]),
        default=animation_end,
    )
    cmds.playbackOptions(maxTime=max(animation_end, latest_worker_frame + 5))
    setup_camera_and_lighting(ground_radius)
    _parent_known_scene_groups()
    cmds.currentTime(1)

    print("Cloud-Hive Bloomfield Maya visualization created.")
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
        "animation_records": animation_records,
        "resource_events": simulation["resource_events"],
        "resource_visuals": resource_visuals,
        "blocked_visuals": blocked_visuals,
    }


def schedule_task_animation(bees, tasks, drops, fall_duration=64, frame_step=22):
    """Lay out each worker's complete task queue on one Maya timeline."""
    task_by_id = {task["id"]: task for task in tasks}
    drop_by_id = {drop["id"]: drop for drop in drops}
    latest_frame = 1

    for bee_index, bee in enumerate(bees):
        cursor = 1 + bee_index * 6
        for task_id in bee.get("task_queue", []):
            task = task_by_id.get(task_id)
            if task is None or not task.get("path"):
                continue
            drop_id = task_id[5:] if task_id.startswith("task_") else task_id
            drop = drop_by_id.get(drop_id)
            if drop is None:
                continue

            drop_start = cursor + int(frame_step)
            drop_end = drop_start + max(24, int(fall_duration))
            delivery_frame = drop_end + max(0, len(task["path"]) - 1) * int(frame_step)
            return_frame = delivery_frame + int(frame_step)

            drop["animation_start_frame"] = drop_start
            drop["animation_end_frame"] = drop_end
            task["animation_frame_start"] = cursor
            task["planned_delivery_frame"] = delivery_frame
            cursor = return_frame + int(frame_step)
            latest_frame = max(latest_frame, cursor)

    return latest_frame


def animate_assigned_bees(bees, tasks, cells, clouds, drops, frame_step=22):
    """Animate every queued Yichen task, including return-to-idle movement."""
    task_by_id = {task["id"]: task for task in tasks}
    records = []
    for index, bee in enumerate(bees):
        for task_id in bee.get("task_queue", []):
            task = task_by_id.get(task_id)
            if task is None or not task.get("path"):
                continue
            frames = animate_bee_collection_cycle(
                bee,
                task,
                cells,
                clouds,
                drops,
                frame_start=task.get("animation_frame_start", 1 + index * 5),
                frame_step=frame_step,
                bee_index=index,
            )
            records.append({
                "bee_id": bee["id"],
                "task_id": task["id"],
                "bfs_path": list(task["path"]),
                "frames": frames,
                "delivery_frame": task.get("delivery_frame"),
            })
    return records


def create_cell_resource_visuals(
    cells,
    resource_events,
    animation_records,
    cell_size,
    cell_depth,
):
    """Visualize resource levels, delivery flashes, and capped transitions."""
    import maya.cmds as cmds

    group_name = "CloudHive_CellResources_GRP"
    cmds.group(empty=True, name=group_name)
    honey_material = _create_maya_material(
        cmds, "chm_cell_nectar_fill_MAT", (1.0, 0.62, 0.02)
    )
    pollen_material = _create_maya_material(
        cmds, "chm_cell_pollen_grain_MAT", (1.0, 0.32, 0.04)
    )
    cap_material = _create_maya_material(
        cmds, "chm_cell_new_cap_MAT", (0.96, 0.84, 0.55)
    )
    flash_material = _create_maya_material(
        cmds, "chm_cell_delivery_flash_MAT", (1.0, 0.95, 0.32)
    )

    delivery_by_task = {
        record["task_id"]: record.get("delivery_frame")
        for record in animation_records
    }
    events_by_cell = {}
    for event in resource_events:
        event = dict(event)
        event["delivery_frame"] = delivery_by_task.get(event["task_id"], 1)
        events_by_cell.setdefault(event["target_cell"], []).append(event)

    created = []
    max_fill_height = max(0.12, float(cell_depth) * 0.72)
    pollen_count = 8
    pollen_offsets = [
        (-0.28, -0.18), (0.0, -0.24), (0.27, -0.13), (-0.19, 0.07),
        (0.12, 0.02), (0.29, 0.19), (-0.08, 0.25), (-0.31, 0.22),
    ]

    for cell in cells:
        cell_id = cell["id"]
        initial_type = cell.get("initial_type", cell.get("type"))
        capacity = max(0.000001, float(cell.get("capacity", 1.0)))
        x, _y, z = cell["position"]
        cell_events = sorted(
            events_by_cell.get(cell_id, []),
            key=lambda item: item.get("delivery_frame", 1),
        )

        if initial_type == "honey":
            fill, _shape = cmds.polyCylinder(
                radius=float(cell_size) * 0.56,
                height=max_fill_height,
                subdivisionsX=6,
                name="{0}_nectar_level".format(cell_id),
            )
            cmds.parent(fill, group_name)
            _assign_maya_material(cmds, fill, honey_material)
            cmds.setAttr(fill + ".translateX", x)
            cmds.setAttr(fill + ".translateZ", z)
            initial_amount = float(cell.get("initial_nectar", 0.0))
            _key_resource_level(
                cmds, fill, 1, initial_amount / capacity, cell_depth, max_fill_height
            )
            for event in cell_events:
                if event["resource_type"] != "nectar":
                    continue
                frame = int(event["delivery_frame"])
                _key_resource_level(
                    cmds,
                    fill,
                    max(1, frame - 1),
                    event["before_amount"] / capacity,
                    cell_depth,
                    max_fill_height,
                )
                _key_resource_level(
                    cmds,
                    fill,
                    frame,
                    event["after_amount"] / capacity,
                    cell_depth,
                    max_fill_height,
                )
            created.append(fill)

        if initial_type == "pollen":
            initial_amount = float(cell.get("initial_pollen", 0.0))
            for grain_index, (offset_x, offset_z) in enumerate(pollen_offsets):
                grain, _shape = cmds.polyCube(
                    width=float(cell_size) * 0.12,
                    height=max_fill_height * 0.35,
                    depth=float(cell_size) * 0.12,
                    name="{0}_pollen_{1:02d}".format(cell_id, grain_index),
                )
                cmds.xform(
                    grain,
                    translation=(
                        x + offset_x * float(cell_size),
                        float(cell_depth) + max_fill_height * 0.18,
                        z + offset_z * float(cell_size),
                    ),
                    worldSpace=True,
                )
                cmds.parent(grain, group_name)
                _assign_maya_material(cmds, grain, pollen_material)
                threshold = float(grain_index + 1) / pollen_count
                initial_visible = 1 if initial_amount / capacity >= threshold else 0
                cmds.setKeyframe(
                    grain, attribute="visibility", time=1, value=initial_visible
                )
                for event in cell_events:
                    if event["resource_type"] != "pollen":
                        continue
                    frame = int(event["delivery_frame"])
                    before_visible = 1 if event["before_amount"] / capacity >= threshold else 0
                    after_visible = 1 if event["after_amount"] / capacity >= threshold else 0
                    cmds.setKeyframe(
                        grain,
                        attribute="visibility",
                        time=max(1, frame - 1),
                        value=before_visible,
                    )
                    cmds.setKeyframe(
                        grain, attribute="visibility", time=frame, value=after_visible
                    )
                created.append(grain)

        if initial_type == "capped" or cell.get("type") == "capped":
            cap, _shape = cmds.polyCylinder(
                radius=float(cell_size) * 0.72,
                height=max(0.06, float(cell_depth) * 0.18),
                subdivisionsX=6,
                name="{0}_cap_lid".format(cell_id),
            )
            cmds.xform(
                cap,
                translation=(x, float(cell_depth) + 0.08, z),
                worldSpace=True,
            )
            cmds.parent(cap, group_name)
            _assign_maya_material(cmds, cap, cap_material)
            cap_frame = 1
            if initial_type != "capped":
                cap_event = next(
                    (event for event in cell_events if event.get("became_capped")),
                    None,
                )
                cap_frame = int(cap_event["delivery_frame"]) if cap_event else 1
                cmds.setKeyframe(
                    cap, attribute="visibility", time=max(1, cap_frame - 1), value=0
                )
            cmds.setKeyframe(cap, attribute="visibility", time=cap_frame, value=1)
            created.append(cap)

    for event_index, event in enumerate(resource_events):
        cell = next(
            (item for item in cells if item["id"] == event["target_cell"]),
            None,
        )
        frame = delivery_by_task.get(event["task_id"])
        if cell is None or frame is None:
            continue
        x, _y, z = cell["position"]
        flash, _shape = cmds.polyCylinder(
            radius=float(cell_size) * 0.86,
            height=0.045,
            subdivisionsX=6,
            name="CloudHive_delivery_flash_{0:03d}".format(event_index),
        )
        cmds.xform(
            flash,
            translation=(x, float(cell_depth) + 0.16, z),
            worldSpace=True,
        )
        cmds.parent(flash, group_name)
        _assign_maya_material(cmds, flash, flash_material)
        cmds.setKeyframe(
            flash, attribute="visibility", time=max(1, int(frame) - 1), value=0
        )
        cmds.setKeyframe(flash, attribute="visibility", time=int(frame), value=1)
        cmds.setKeyframe(
            flash, attribute="visibility", time=int(frame) + 8, value=0
        )
        created.append(flash)

    return created


def _key_resource_level(cmds, node, frame, ratio, cell_depth, max_height):
    """Key a hexagonal resource fill to a normalized cell capacity."""
    safe_ratio = max(0.01, min(1.0, float(ratio)))
    cmds.setKeyframe(node, attribute="scaleY", time=frame, value=safe_ratio)
    cmds.setKeyframe(
        node,
        attribute="translateY",
        time=frame,
        value=float(cell_depth) + max_height * safe_ratio * 0.5 + 0.025,
    )


def create_blocked_task_visuals(tasks, cells, animation_end=320):
    """Place pulsing red markers above cells with unreachable cleanup tasks."""
    import maya.cmds as cmds

    group_name = "CloudHive_BlockedTasks_GRP"
    cmds.group(empty=True, name=group_name)
    material = _create_maya_material(
        cmds, "chm_blocked_task_red_MAT", (1.0, 0.08, 0.04)
    )
    cell_by_id = {cell["id"]: cell for cell in cells}
    blocked_cell_ids = sorted({
        task.get("source_cell")
        for task in tasks
        if not task.get("path") and task.get("source_cell")
    })
    created = []

    for index, cell_id in enumerate(blocked_cell_ids):
        cell = cell_by_id.get(cell_id)
        if cell is None:
            continue
        x, _y, z = cell["position"]
        marker, _shape = cmds.polyCube(
            width=0.18,
            height=0.55,
            depth=0.18,
            name="CloudHive_blocked_marker_{0:02d}".format(index),
        )
        cmds.xform(marker, translation=(x, 0.85, z), worldSpace=True)
        cmds.parent(marker, group_name)
        _assign_maya_material(cmds, marker, material)
        cmds.setKeyframe(marker, attribute="scaleY", time=1, value=0.75)
        cmds.setKeyframe(marker, attribute="scaleY", time=12, value=1.2)
        cmds.setKeyframe(marker, attribute="scaleY", time=24, value=0.75)
        cmds.setInfinity(marker + ".scaleY", postInfinite="cycle")
        created.append(marker)

    return created


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
        "CloudHive_MeadowDetails_GRP",
        "CloudHive_BeehiveBoxes_GRP",
        "CloudHive_FallingResources_GRP",
        "CloudHive_CellResources_GRP",
        "CloudHive_BlockedTasks_GRP",
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

    sun_shape = cmds.directionalLight(name="CloudHive_Sun_LGT", intensity=1.28)
    sun_light = cmds.listRelatives(sun_shape, parent=True)[0]
    cmds.xform(sun_light, rotation=(-45.0, -30.0, 0.0), worldSpace=True)
    cmds.setAttr(sun_shape + ".color", 1.0, 0.78, 0.48, type="double3")
    cmds.parent(sun_light, group_name)

    ambient_shape = cmds.ambientLight(name="CloudHive_Ambient_LGT", intensity=0.42)
    ambient_light = cmds.listRelatives(ambient_shape, parent=True)[0]
    cmds.setAttr(ambient_shape + ".color", 0.72, 0.74, 1.0, type="double3")
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


def create_falling_resource_effects(
    drops,
    clouds,
    start_frame=1,
    end_frame=320,
    fall_duration=64,
):
    """Create animated nectar and pollen falling from clouds to the honeycomb.

    Parameters:
        drops (list[dict]): Resource drops from cloud_resource_module.
        clouds (list[dict]): Cloud dictionaries with source positions.
        start_frame (int): First animation frame.
        end_frame (int): Last animation frame.
        fall_duration (int): Frames used by each drop to reach the honeycomb.

    Returns:
        list[str]: Created Maya object names.
    """
    import maya.cmds as cmds

    group_name = "CloudHive_FallingResources_GRP"
    if cmds.objExists(group_name):
        cmds.delete(group_name)
    cmds.group(empty=True, name=group_name)

    cloud_by_id = {cloud["id"]: cloud for cloud in clouds}
    nectar_material = _create_maya_material(cmds, "chm_pixel_nectar_MAT", (1.0, 0.62, 0.02))
    pollen_material = _create_maya_material(cmds, "chm_pixel_pollen_MAT", (1.0, 0.42, 0.05))
    streak_material = _create_maya_material(cmds, "chm_pixel_nectar_streak_MAT", (1.0, 0.78, 0.12))

    created = []
    frame_span = max(1, int(end_frame) - int(start_frame))
    for index, drop in enumerate(drops):
        cloud = cloud_by_id.get(drop.get("source_cloud"))
        if cloud is None:
            continue

        resource_type = drop.get("resource_type", "nectar")
        cloud_x, cloud_y, cloud_z = cloud["position"]
        end_x, end_y, end_z = drop["position"]
        safe_duration = max(24, int(fall_duration))
        if "animation_start_frame" in drop and "animation_end_frame" in drop:
            local_start = int(drop["animation_start_frame"])
            local_end = int(drop["animation_end_frame"])
        else:
            start_window = max(1, frame_span - safe_duration - 4)
            local_start = int(start_frame) + (index * 10) % start_window
            local_end = min(
                int(end_frame),
                local_start + safe_duration + (index % 10),
            )
        drop["animation_start_frame"] = local_start
        drop["animation_end_frame"] = local_end

        jitter = 0.55 if resource_type == "nectar" else 0.95
        start_x = cloud_x + math.sin(index * 1.7) * jitter
        start_y = cloud_y - 0.55
        start_z = cloud_z + math.cos(index * 1.3) * jitter
        size = 0.13 if resource_type == "nectar" else 0.09

        particle, _shape = cmds.polyCube(
            width=size,
            height=size * (1.55 if resource_type == "nectar" else 1.0),
            depth=size,
            name="CloudHive_{0}_falling_{1:03d}".format(resource_type, index),
        )
        cmds.xform(particle, translation=(start_x, start_y, start_z), worldSpace=True)
        cmds.parent(particle, group_name)
        _assign_maya_material(cmds, particle, nectar_material if resource_type == "nectar" else pollen_material)

        if local_start > int(start_frame):
            cmds.setKeyframe(particle, attribute="visibility", time=local_start - 1, value=0)
        cmds.setKeyframe(particle, attribute="visibility", time=local_start, value=1)
        cmds.setKeyframe(particle, attribute="translateX", time=local_start, value=start_x)
        cmds.setKeyframe(particle, attribute="translateY", time=local_start, value=start_y)
        cmds.setKeyframe(particle, attribute="translateZ", time=local_start, value=start_z)
        cmds.setKeyframe(particle, attribute="translateX", time=local_end, value=end_x)
        cmds.setKeyframe(particle, attribute="translateY", time=local_end, value=end_y + 0.35)
        cmds.setKeyframe(particle, attribute="translateZ", time=local_end, value=end_z)
        cmds.setKeyframe(particle, attribute="visibility", time=local_end, value=1)
        cmds.setKeyframe(particle, attribute="visibility", time=min(int(end_frame), local_end + 2), value=0)
        created.append(particle)

        if resource_type == "nectar":
            streak = cmds.curve(
                degree=1,
                point=[
                    (start_x, start_y, start_z),
                    ((start_x + end_x) * 0.5, (start_y + end_y) * 0.5, (start_z + end_z) * 0.5),
                    (end_x, end_y + 0.35, end_z),
                ],
                name="CloudHive_nectar_fall_streak_{0:03d}".format(index),
            )
            shape = cmds.listRelatives(streak, shapes=True)[0]
            cmds.setAttr(shape + ".lineWidth", 2)
            cmds.parent(streak, group_name)
            _assign_maya_material(cmds, streak, streak_material)
            if local_start > int(start_frame):
                cmds.setKeyframe(streak, attribute="visibility", time=local_start - 1, value=0)
            cmds.setKeyframe(streak, attribute="visibility", time=local_start, value=1)
            cmds.setKeyframe(streak, attribute="visibility", time=local_end, value=1)
            cmds.setKeyframe(streak, attribute="visibility", time=min(int(end_frame), local_end + 2), value=0)
            created.append(streak)

    cmds.playbackOptions(minTime=start_frame, maxTime=end_frame, loop="continuous")
    return created


def create_meadow_background(scene_radius=9.0, hive_radius=5.0, flower_count=70, grass_tuft_count=45, seed=77):
    """Create simple meadow flowers and grass around the honeycomb.

    Parameters:
        scene_radius (float): Approximate scene radius.
        hive_radius (float): Radius kept clear around the honeycomb.
        flower_count (int): Number of small field flowers.
        grass_tuft_count (int): Number of simple grass tufts.
        seed (int): Random seed for stable placement.

    Returns:
        dict: Created group and object counts.
    """
    import maya.cmds as cmds

    rng = random.Random(seed)
    group_name = "CloudHive_MeadowDetails_GRP"
    if cmds.objExists(group_name):
        cmds.delete(group_name)
    cmds.group(empty=True, name=group_name)

    stem_material = _create_maya_material(cmds, "chm_meadow_stem_green_MAT", (0.12, 0.42, 0.16))
    grass_material = _create_maya_material(cmds, "chm_meadow_grass_MAT", (0.18, 0.52, 0.2))
    petal_materials = [
        _create_maya_material(cmds, "chm_meadow_petal_white_MAT", (0.95, 0.92, 0.78)),
        _create_maya_material(cmds, "chm_meadow_petal_pink_MAT", (1.0, 0.52, 0.72)),
        _create_maya_material(cmds, "chm_meadow_petal_yellow_MAT", (1.0, 0.82, 0.18)),
    ]
    center_material = _create_maya_material(cmds, "chm_meadow_flower_center_MAT", (0.95, 0.55, 0.05))

    for index in range(max(0, int(flower_count))):
        x, z = _random_ring_position(rng, hive_radius, scene_radius * 0.92)
        flower_group = cmds.group(empty=True, name="CloudHive_FieldFlower_{0:03d}_GRP".format(index))
        cmds.parent(flower_group, group_name)

        stem_height = rng.uniform(0.18, 0.42)
        stem, _shape = cmds.polyCylinder(
            radius=0.018,
            height=stem_height,
            subdivisionsX=6,
            name="CloudHive_FieldFlower_{0:03d}_stem".format(index),
        )
        cmds.xform(stem, translation=(x, stem_height * 0.5, z), worldSpace=True)
        cmds.parent(stem, flower_group)
        _assign_maya_material(cmds, stem, stem_material)

        center_y = stem_height + 0.035
        center, _shape = cmds.polySphere(
            radius=0.045,
            name="CloudHive_FieldFlower_{0:03d}_center".format(index),
        )
        cmds.xform(center, translation=(x, center_y, z), worldSpace=True)
        cmds.parent(center, flower_group)
        _assign_maya_material(cmds, center, center_material)

        petal_material = rng.choice(petal_materials)
        petal_count = rng.choice([5, 6])
        for petal_index in range(petal_count):
            angle = math.tau * petal_index / petal_count
            petal, _shape = cmds.polySphere(
                radius=0.035,
                name="CloudHive_FieldFlower_{0:03d}_petal_{1:02d}".format(index, petal_index),
            )
            cmds.scale(1.35, 0.45, 0.9, petal, relative=True)
            cmds.xform(
                petal,
                translation=(x + math.cos(angle) * 0.07, center_y, z + math.sin(angle) * 0.07),
                worldSpace=True,
            )
            cmds.parent(petal, flower_group)
            _assign_maya_material(cmds, petal, petal_material)

    for index in range(max(0, int(grass_tuft_count))):
        x, z = _random_ring_position(rng, hive_radius * 0.85, scene_radius * 0.96)
        tuft_group = cmds.group(empty=True, name="CloudHive_GrassTuft_{0:03d}_GRP".format(index))
        cmds.parent(tuft_group, group_name)
        blade_count = rng.randint(3, 6)
        for blade_index in range(blade_count):
            blade_height = rng.uniform(0.16, 0.34)
            blade, _shape = cmds.polyCube(
                width=0.025,
                height=blade_height,
                depth=0.025,
                name="CloudHive_GrassTuft_{0:03d}_blade_{1:02d}".format(index, blade_index),
            )
            cmds.xform(
                blade,
                translation=(x + rng.uniform(-0.08, 0.08), blade_height * 0.5, z + rng.uniform(-0.08, 0.08)),
                rotation=(0.0, rng.uniform(0.0, 180.0), rng.uniform(-18.0, 18.0)),
                worldSpace=True,
            )
            cmds.parent(blade, tuft_group)
            _assign_maya_material(cmds, blade, grass_material)

    return {
        "group": group_name,
        "flower_count": max(0, int(flower_count)),
        "grass_tuft_count": max(0, int(grass_tuft_count)),
    }


def create_beehive_box(scene_radius=9.0, box_count=2, seed=88):
    """Create simple stylized beehive boxes near the edge of the meadow.

    Parameters:
        scene_radius (float): Approximate scene radius.
        box_count (int): Number of beehive boxes.
        seed (int): Random seed for stable placement.

    Returns:
        list[str]: Created beehive box group names.
    """
    import maya.cmds as cmds

    rng = random.Random(seed)
    group_name = "CloudHive_BeehiveBoxes_GRP"
    if cmds.objExists(group_name):
        cmds.delete(group_name)
    cmds.group(empty=True, name=group_name)

    wood_material = _create_maya_material(cmds, "chm_beehive_wood_MAT", (0.78, 0.56, 0.24))
    roof_material = _create_maya_material(cmds, "chm_beehive_roof_MAT", (0.46, 0.28, 0.12))
    entrance_material = _create_maya_material(cmds, "chm_beehive_entrance_MAT", (0.08, 0.05, 0.025))

    created = []
    for index in range(max(0, int(box_count))):
        angle = (math.tau / max(1, int(box_count))) * index + rng.uniform(-0.35, 0.35)
        radius = scene_radius * rng.uniform(0.62, 0.78)
        x = math.cos(angle) * radius
        z = math.sin(angle) * radius

        hive_group = cmds.group(empty=True, name="CloudHive_BeehiveBox_{0:02d}_GRP".format(index))
        cmds.parent(hive_group, group_name)
        created.append(hive_group)

        base, _shape = cmds.polyCube(
            width=0.9,
            height=0.55,
            depth=0.65,
            name="CloudHive_BeehiveBox_{0:02d}_base".format(index),
        )
        cmds.xform(base, translation=(x, 0.275, z), rotation=(0.0, -math.degrees(angle) + 90.0, 0.0), worldSpace=True)
        cmds.parent(base, hive_group)
        _assign_maya_material(cmds, base, wood_material)

        roof, _shape = cmds.polyCube(
            width=1.05,
            height=0.12,
            depth=0.78,
            name="CloudHive_BeehiveBox_{0:02d}_roof".format(index),
        )
        cmds.xform(roof, translation=(x, 0.62, z), rotation=(0.0, -math.degrees(angle) + 90.0, 0.0), worldSpace=True)
        cmds.parent(roof, hive_group)
        _assign_maya_material(cmds, roof, roof_material)

        entrance, _shape = cmds.polyCylinder(
            radius=0.09,
            height=0.035,
            subdivisionsX=16,
            name="CloudHive_BeehiveBox_{0:02d}_entrance".format(index),
        )
        front_x = x + math.cos(angle + math.pi) * 0.34
        front_z = z + math.sin(angle + math.pi) * 0.34
        cmds.xform(
            entrance,
            translation=(front_x, 0.31, front_z),
            rotation=(90.0, 0.0, -math.degrees(angle)),
            worldSpace=True,
        )
        cmds.parent(entrance, hive_group)
        _assign_maya_material(cmds, entrance, entrance_material)

        for stripe_index in range(2):
            stripe, _shape = cmds.polyCube(
                width=0.96,
                height=0.035,
                depth=0.68,
                name="CloudHive_BeehiveBox_{0:02d}_stripe_{1:02d}".format(index, stripe_index),
            )
            cmds.xform(
                stripe,
                translation=(x, 0.22 + stripe_index * 0.18, z),
                rotation=(0.0, -math.degrees(angle) + 90.0, 0.0),
                worldSpace=True,
            )
            cmds.parent(stripe, hive_group)
            _assign_maya_material(cmds, stripe, roof_material)

    return created


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
        label_text = "Cloud-Hive Bloomfield"
    else:
        label_text = (
            "Cloud-Hive Bloomfield\\n"
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


def _random_ring_position(rng, inner_radius, outer_radius):
    """Return a deterministic random XZ position between two radii."""
    safe_inner = max(0.0, float(inner_radius))
    safe_outer = max(safe_inner + 0.1, float(outer_radius))
    angle = rng.uniform(0.0, math.tau)
    radius = math.sqrt(rng.uniform(safe_inner * safe_inner, safe_outer * safe_outer))
    return math.cos(angle) * radius, math.sin(angle) * radius


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
        "CloudHive_MeadowDetails_GRP",
        "CloudHive_BeehiveBoxes_GRP",
        "CloudHive_Bees_GRP",
        "CloudHive_BeeTaskPaths_GRP",
        "CloudHive_FallingResources_GRP",
        "CloudHive_CellResources_GRP",
        "CloudHive_BlockedTasks_GRP",
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
