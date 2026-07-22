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
    create_drop_particles,
    create_flower_geometry_on_clouds,
)
from hive_module import create_honeycomb_geometry
from main import load_parameters, run_simulation


ROOT_GROUP = "CloudHive_Visualization_GRP"
CAMERA_LIGHT_GROUP = "CloudHive_CameraLight_GRP"
OVERVIEW_CAMERA = "CloudHive_Render_CAM"
LEGACY_ANIMATION_START = 1000
DEMO_STAGE_BASE_RANGES = {
    0: (1, 2),
    1: (10, 58),
    2: (70, 94),
    3: (106, 136),
    4: (148, 196),
    5: (208, 238),
}
DEMO_COLLECTION_START = 250
DEMO_COLLECTION_FRAME_STEP = 6
DEMO_STAGE_LABELS = {
    0: "Base Scene",
    1: "Natural Resource Drop",
    2: "Drop Mapping and Cell Validation",
    3: "Direct Storage or Task Creation",
    4: "Bee Task Selection and BFS Path",
    5: "Resource Check and Collection Trigger",
    6: "Cloud Collection Ready",
    7: "Deposit Update / Next Cycle Ready",
}
DEMO_VISUAL_GROUPS = {
    "natural_drops": "CloudHive_ResourceDrops_GRP",
    "falling_drops": "CloudHive_FallingResources_GRP",
    "mapping": "CloudHive_DropMapping_GRP",
    "validation": "CloudHive_ValidationHighlights_GRP",
    "direct_storage": "CloudHive_DirectStorage_GRP",
    "task_markers": "CloudHive_TaskMarkers_GRP",
    "bee_selections": "CloudHive_BeeSelections_GRP",
    "bfs_paths": "CloudHive_BeeTaskPaths_GRP",
    "blocked_tasks": "CloudHive_BlockedTasks_GRP",
    "collection_triggers": "CloudHive_CollectionTriggers_GRP",
    "collection_visuals": "CloudHive_CollectionVisuals_GRP",
    "deposit_updates": "CloudHive_DepositUpdate_GRP",
}


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

    overview_camera_existed = _find_camera_rig_node(cmds, "camera")[0] is not None
    clear_scene(preserve_camera=True)
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
    create_drop_particles(drops)
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
        start_frame=LEGACY_ANIMATION_START,
    )
    animation_end = max(animation_end, scheduled_end)
    # The compact Stage 1 transition uses the existing landing markers. Keep
    # the legacy falling group present for stable group bookkeeping without
    # authoring a second long drop animation that the demo no longer plays.
    _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["falling_drops"])
    create_bee_geometry(bees, bee_scale=bee_scale)
    bee_base_transforms = {
        bee["id"]: list(
            cmds.xform(
                bee["maya_object"],
                query=True,
                translation=True,
                worldSpace=True,
            )
        )
        for bee in bees
        if bee.get("maya_object") and cmds.objExists(bee["maya_object"])
    }
    path_visuals = []
    if show_paths:
        path_visuals = create_task_path_visuals(tasks, cells)
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
    drop_demo_visuals = create_drop_demo_visuals(
        drops,
        tasks,
        cells,
        cell_size=hive_params["cell_size"],
    )
    bee_selection_visuals = create_bee_task_selection_visuals(bees)
    collection_tasks, collection_check = create_collection_demo_tasks(
        cells,
        clouds,
        bees,
        parameters,
    )
    collection_visuals = create_collection_demo_visuals(
        collection_tasks,
        bees,
        cells,
        frame_start=DEMO_COLLECTION_START,
        frame_step=DEMO_COLLECTION_FRAME_STEP,
    )
    deposit_visuals = create_deposit_update_visuals(
        cells,
        simulation["resource_events"],
        cell_size=hive_params["cell_size"],
        collection_tasks=collection_tasks,
    )
    collection_end = max(
        (task.get("animation_end_frame", 1) for task in collection_tasks),
        default=DEMO_COLLECTION_START + 48,
    )
    stage_six_end = max(DEMO_COLLECTION_START + 48, int(collection_end))
    stage_seven_start = stage_six_end + 12
    stage_seven_end = stage_seven_start + 40
    playback_ranges = dict(DEMO_STAGE_BASE_RANGES)
    playback_ranges.update({
        6: (DEMO_COLLECTION_START, stage_six_end),
        7: (stage_seven_start, stage_seven_end),
    })
    stage_frames = {
        stage: frame_range[0]
        for stage, frame_range in playback_ranges.items()
    }
    transition_visuals = author_demo_stage_transitions(
        drops=drops,
        clouds=clouds,
        cells=cells,
        resource_events=simulation["resource_events"],
        bees=bees,
        bee_base_transforms=bee_base_transforms,
        path_visuals=path_visuals,
        blocked_visuals=blocked_visuals,
        drop_demo_visuals=drop_demo_visuals,
        bee_selection_visuals=bee_selection_visuals,
        collection_tasks=collection_tasks,
        deposit_visuals=deposit_visuals,
        stage_ranges=playback_ranges,
        cell_depth=cell_depth,
    )
    natural_worker_frame = max(
        (max(record["frames"]) for record in animation_records if record["frames"]),
        default=LEGACY_ANIMATION_START,
    )
    full_animation_end = max(
        animation_end,
        natural_worker_frame + 5,
        stage_seven_end + 5,
    )
    cmds.playbackOptions(
        animationStartTime=1,
        animationEndTime=full_animation_end,
        maxTime=full_animation_end,
    )
    cycle_group = organize_demo_cycle_groups(simulation["summary"]["cycle_number"])
    camera_setup = setup_camera_and_lighting(ground_radius)
    frame_scene_overview(
        camera_setup["camera"],
        fallback_radius=ground_radius,
    )
    _parent_known_scene_groups(additional_groups=[cycle_group])

    scene_data = {
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
        "drop_demo_visuals": drop_demo_visuals,
        "bee_selection_visuals": bee_selection_visuals,
        "collection_tasks": collection_tasks,
        "collection_check": collection_check,
        "collection_visuals": collection_visuals,
        "deposit_visuals": deposit_visuals,
        "transition_visuals": transition_visuals,
        "demo_visual_groups": dict(DEMO_VISUAL_GROUPS),
        "demo_cycle_group": cycle_group,
        "demo_stage_frames": stage_frames,
        "demo_stage_end_frames": {
            stage: frame_range[1]
            for stage, frame_range in playback_ranges.items()
        },
        "demo_playback_ranges": playback_ranges,
        "animation_full_range": (1, full_animation_end),
        "demo_stage": 0,
    }
    apply_demo_stage(scene_data, 0)

    # A first Generate should present the deliberately wide overview. Later
    # rebuilds preserve whichever viewport camera the user selected.
    if not overview_camera_existed and not cmds.about(batch=True):
        try:
            cmds.lookThru(camera_setup["camera"])
        except RuntimeError:
            pass

    print("Cloud-Hive Bloomfield Maya visualization created.")
    print("Cells: {0}, Clouds: {1}, Drops: {2}, Tasks: {3}, Bees: {4}".format(
        len(cells),
        len(clouds),
        len(drops),
        len(tasks),
        len(bees),
    ))

    return scene_data


def schedule_task_animation(
    bees,
    tasks,
    drops,
    fall_duration=64,
    frame_step=22,
    start_frame=1,
):
    """Lay out each worker's complete task queue on one Maya timeline."""
    task_by_id = {task["id"]: task for task in tasks}
    drop_by_id = {drop["id"]: drop for drop in drops}
    latest_frame = max(1, int(start_frame))

    for bee_index, bee in enumerate(bees):
        cursor = max(1, int(start_frame)) + bee_index * 6
        for task_id in bee.get("task_queue", []):
            task = task_by_id.get(task_id)
            if task is None or not task.get("path"):
                continue
            drop_id = task_id[5:] if task_id.startswith("task_") else task_id
            drop = drop_by_id.get(drop_id)
            if drop is None:
                delivery_frame = cursor + max(0, len(task["path"]) - 1) * int(frame_step)
                task["animation_frame_start"] = int(cursor)
                task["planned_delivery_frame"] = int(delivery_frame)
                task["delivery_frame"] = int(delivery_frame)
                cursor = delivery_frame + (2 * int(frame_step))
                latest_frame = max(latest_frame, cursor)
                continue

            drop_start = cursor
            drop_end = drop_start + max(24, int(fall_duration))
            delivery_frame = drop_end + max(0, len(task["path"]) - 1) * int(frame_step)
            return_frame = delivery_frame + int(frame_step)

            drop["animation_start_frame"] = drop_start
            drop["animation_end_frame"] = drop_end
            task["animation_frame_start"] = drop_end
            task["planned_delivery_frame"] = delivery_frame
            task["delivery_frame"] = int(delivery_frame)
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


def create_collection_demo_tasks(cells, clouds, bees, parameters):
    """Create shortage-driven collection-ready records without mutating storage.

    These records drive the explanatory Stage 5/6 visuals. Natural drops and
    capacity-aware deposits remain owned by the existing pure simulation.
    """
    resource_params = parameters.get("resources", {})
    thresholds = resource_params.get("collection_thresholds", {})
    collection_amount = max(0.0, float(resource_params.get("collection_amount", 0.4)))
    totals = {
        "nectar": sum(float(cell.get("nectar", 0.0)) for cell in cells),
        "pollen": sum(float(cell.get("pollen", 0.0)) for cell in cells),
    }
    normalized_thresholds = {
        "nectar": max(0.0, float(thresholds.get("nectar", 0.0))),
        "pollen": max(0.0, float(thresholds.get("pollen", 0.0))),
    }
    check = {
        "totals": totals,
        "thresholds": normalized_thresholds,
        "needed_resources": [],
        "presentation_resource": None,
    }

    traversable_cells = [
        cell
        for cell in cells
        if not cell.get("is_blocked")
        and cell.get("type") not in ("queen", "queen_reserved", "capped")
    ]
    if not traversable_cells or not clouds:
        return [], check

    cycle_number = int(parameters.get("simulation", {}).get("cycle", 0))
    tasks = []
    resource_types = ("nectar", "pollen")
    needed_resources = [
        resource_type
        for resource_type in resource_types
        if totals[resource_type] + 0.000001
        < normalized_thresholds[resource_type]
    ]
    presentation_only = not needed_resources
    if presentation_only:
        def reserve_ratio(resource_type):
            threshold = max(0.000001, normalized_thresholds[resource_type])
            return totals[resource_type] / threshold

        planned_resources = [min(resource_types, key=reserve_ratio)]
        check["presentation_resource"] = planned_resources[0]
    else:
        planned_resources = needed_resources
        check["needed_resources"] = list(needed_resources)

    for task_index, resource_type in enumerate(planned_resources):
        resource_index = resource_types.index(resource_type)
        total = totals[resource_type]
        threshold = normalized_thresholds[resource_type]

        assigned_bee = bees[task_index % len(bees)] if bees else None
        bee_start = (
            assigned_bee.get("position", [0.0, 0.8, 0.0])
            if assigned_bee
            else [0.0, 0.8, 0.0]
        )
        start_cell = min(
            traversable_cells,
            key=lambda cell: _horizontal_distance_squared(
                cell["position"], bee_start
            ),
        )
        reachable_paths = _reachable_hive_paths(start_cell["id"], cells)
        reachable_cells = [
            cell for cell in traversable_cells if cell["id"] in reachable_paths
        ]
        if not reachable_cells:
            continue

        cloud = clouds[resource_index % len(clouds)]
        base_cell = min(
            reachable_cells,
            key=lambda cell: _horizontal_distance_squared(
                cell["position"], cloud["position"]
            ),
        )
        resource_points = cloud.get("resource_points") or [cloud["position"]]
        resource_point = resource_points[resource_index % len(resource_points)]
        flower_position = [
            float(resource_point[0]),
            float(cloud["position"][1]) + 0.80,
            float(resource_point[2]),
        ]
        shortage = max(0.0, threshold - total)
        cloud_available = max(
            0.0,
            float(cloud.get("{0}_amount".format(resource_type), collection_amount)),
        )
        requested_amount = collection_amount if presentation_only else shortage
        amount = min(requested_amount, collection_amount, cloud_available)
        if amount <= 0.000001:
            continue

        task = {
            "id": "task_{0}_cycle_{1}_{2}".format(
                "collection_demo" if presentation_only else "collection",
                cycle_number,
                resource_type,
            ),
            "type": "collect_{0}".format(resource_type),
            "origin": "collection_demo" if presentation_only else "collection",
            "presentation_only": presentation_only,
            "resource_type": resource_type,
            "amount": amount,
            "shortage": shortage,
            "source_cloud": cloud["id"],
            "assigned_bee_id": assigned_bee.get("id") if assigned_bee else None,
            "target_flower_position": flower_position,
            "hive_start_cell": start_cell["id"],
            "cloud_base_cell": base_cell["id"],
            "path": list(reachable_paths[base_cell["id"]]),
            "movement_modes": ["on_hive", "cloud_flight", "on_hive_reentry"],
            "status": "collection_ready",
        }
        tasks.append(task)

    return tasks, check


def _horizontal_distance_squared(first, second):
    """Return squared XZ distance between two 3D points."""
    delta_x = float(first[0]) - float(second[0])
    delta_z = float(first[2]) - float(second[2])
    return delta_x * delta_x + delta_z * delta_z


def _reachable_hive_paths(start_cell_id, cells):
    """Return shortest on-hive paths from one traversable start cell."""
    cell_by_id = {cell["id"]: cell for cell in cells}
    start_cell = cell_by_id.get(start_cell_id)
    if start_cell is None or start_cell.get("is_blocked"):
        return {}

    paths = {start_cell_id: [start_cell_id]}
    queue = [start_cell_id]
    while queue:
        cell_id = queue.pop(0)
        for neighbor_id in cell_by_id[cell_id].get("neighbors", []):
            if neighbor_id in paths:
                continue
            neighbor = cell_by_id.get(neighbor_id)
            if neighbor is None or neighbor.get("is_blocked"):
                continue
            paths[neighbor_id] = paths[cell_id] + [neighbor_id]
            queue.append(neighbor_id)
    return paths


def _sample_demo_points(points, max_points=6):
    """Keep endpoints while reducing a long path to a readable preview."""
    safe_points = list(points)
    limit = max(2, int(max_points))
    if len(safe_points) <= limit:
        return safe_points
    last_index = len(safe_points) - 1
    indices = sorted({
        int(round(step * last_index / float(limit - 1)))
        for step in range(limit)
    })
    return [safe_points[index] for index in indices]


def create_drop_demo_visuals(drops, tasks, cells, cell_size):
    """Create static mapping, validation, and outcome layers for one cycle."""
    import maya.cmds as cmds

    mapping_group = _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["mapping"])
    validation_group = _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["validation"])
    direct_group = _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["direct_storage"])
    task_group = _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["task_markers"])

    validation_materials = {
        "matched": _create_maya_material(
            cmds, "chm_demo_validation_green_MAT", (0.12, 1.0, 0.30)
        ),
        "mismatched": _create_maya_material(
            cmds, "chm_demo_validation_orange_MAT", (1.0, 0.42, 0.04)
        ),
        "blocked": _create_maya_material(
            cmds, "chm_demo_validation_red_MAT", (1.0, 0.04, 0.10)
        ),
        "unmapped": _create_maya_material(
            cmds, "chm_demo_validation_gray_MAT", (0.45, 0.45, 0.50)
        ),
    }
    direct_material = _create_maya_material(
        cmds, "chm_demo_direct_storage_gold_MAT", (1.0, 0.82, 0.08)
    )
    transport_material = _create_maya_material(
        cmds, "chm_demo_transport_task_blue_MAT", (0.10, 0.42, 1.0)
    )
    cleanup_material = _create_maya_material(
        cmds, "chm_demo_cleanup_task_red_MAT", (1.0, 0.05, 0.05)
    )

    cell_by_id = {cell["id"]: cell for cell in cells}
    task_by_id = {task["id"]: task for task in tasks}
    created = {
        "mapping": [],
        "validation": [],
        "direct_storage": [],
        "task_markers": [],
        "outcomes": [],
    }
    for index, drop in enumerate(drops):
        cell = cell_by_id.get(drop.get("mapped_cell_id"))
        if cell is None:
            continue
        drop_x, drop_y, drop_z = drop["position"]
        cell_x, cell_y, cell_z = cell["position"]
        mapping_curve = cmds.curve(
            degree=1,
            point=[
                (drop_x, drop_y + 0.34, drop_z),
                (cell_x, cell_y + 0.62, cell_z),
            ],
            name="CloudHive_mapping_{0:03d}_CRV".format(index),
        )
        cmds.parent(mapping_curve, mapping_group)
        _style_demo_curve(cmds, mapping_curve, (0.10, 0.78, 1.0), line_width=3)
        created["mapping"].append(mapping_curve)

        validation = drop.get("validation_result", "unmapped")
        highlight, _shape = cmds.polyCylinder(
            radius=float(cell_size) * 0.76,
            height=0.055,
            subdivisionsX=6,
            name="CloudHive_validation_{0:03d}".format(index),
        )
        cmds.xform(
            highlight,
            translation=(cell_x, cell_y + 0.57, cell_z),
            rotation=(0.0, 30.0, 0.0),
            worldSpace=True,
        )
        cmds.parent(highlight, validation_group)
        _assign_maya_material(
            cmds,
            highlight,
            validation_materials.get(validation, validation_materials["unmapped"]),
        )
        created["validation"].append(highlight)

        direct_amount = float(drop.get("direct_storage_amount", 0.0))
        if direct_amount > 0.000001:
            direct_marker, _shape = cmds.polyCylinder(
                radius=float(cell_size) * 0.30,
                height=0.16,
                subdivisionsX=6,
                name="CloudHive_direct_storage_{0:03d}".format(index),
            )
            cmds.xform(
                direct_marker,
                translation=(cell_x, cell_y + 0.78, cell_z),
                rotation=(0.0, 30.0, 0.0),
                worldSpace=True,
            )
            cmds.parent(direct_marker, direct_group)
            _assign_maya_material(cmds, direct_marker, direct_material)
            created["direct_storage"].append(direct_marker)

        task = task_by_id.get(drop.get("task_id"))
        if task is not None:
            cleanup = task.get("type") == "clean_blocked"
            task_marker, _shape = cmds.polyCube(
                width=0.24 if cleanup else 0.20,
                height=0.62 if cleanup else 0.42,
                depth=0.24 if cleanup else 0.20,
                name="CloudHive_{0}_task_{1:03d}".format(
                    "cleanup" if cleanup else "transport",
                    index,
                ),
            )
            cmds.xform(
                task_marker,
                translation=(cell_x, cell_y + 0.92, cell_z),
                rotation=(0.0, 45.0 if cleanup else 0.0, 0.0),
                worldSpace=True,
            )
            cmds.parent(task_marker, task_group)
            _assign_maya_material(
                cmds,
                task_marker,
                cleanup_material if cleanup else transport_material,
            )
            created["task_markers"].append(task_marker)

        created["outcomes"].append({
            "drop_id": drop.get("id"),
            "cell_id": cell.get("id"),
            "validation": validation,
            "direct_storage_amount": direct_amount,
            "task_id": task.get("id") if task else None,
            "task_type": task.get("type") if task else None,
        })

    return created


def create_collection_demo_visuals(collection_tasks, bees, cells, frame_start, frame_step):
    """Create collection trigger/routes and key bee crawl-vs-flight segments."""
    import maya.cmds as cmds

    trigger_group = _replace_empty_group(
        cmds, DEMO_VISUAL_GROUPS["collection_triggers"]
    )
    visual_group = _replace_empty_group(
        cmds, DEMO_VISUAL_GROUPS["collection_visuals"]
    )
    nectar_material = _create_maya_material(
        cmds, "chm_demo_collection_nectar_MAT", (1.0, 0.72, 0.05)
    )
    pollen_material = _create_maya_material(
        cmds, "chm_demo_collection_pollen_MAT", (1.0, 0.30, 0.05)
    )
    cell_by_id = {cell["id"]: cell for cell in cells}
    created = []
    bee_by_id = {bee.get("id"): bee for bee in bees}
    base_cursor = max(1, int(frame_start))
    safe_step = max(1, int(frame_step))

    for index, task in enumerate(collection_tasks):
        cursor = base_cursor + index * max(1, safe_step // 2)
        resource_type = task.get("resource_type", "nectar")
        resource_material = (
            nectar_material if resource_type == "nectar" else pollen_material
        )
        flower_position = tuple(task["target_flower_position"])
        trigger, _shape = cmds.polySphere(
            radius=0.26,
            name="CloudHive_collection_trigger_{0:02d}".format(index),
        )
        cmds.xform(trigger, translation=flower_position, worldSpace=True)
        cmds.parent(trigger, trigger_group)
        _assign_maya_material(cmds, trigger, resource_material)
        created.append(trigger)

        halo, _shape = cmds.polyCylinder(
            radius=0.48,
            height=0.045,
            subdivisionsX=18,
            name="CloudHive_collection_shortage_halo_{0:02d}".format(index),
        )
        cmds.xform(
            halo,
            translation=(flower_position[0], flower_position[1] - 0.16, flower_position[2]),
            worldSpace=True,
        )
        cmds.parent(halo, trigger_group)
        _assign_maya_material(cmds, halo, resource_material)
        created.append(halo)

        base_cell = cell_by_id.get(task.get("cloud_base_cell"))
        if base_cell is not None:
            base_x, base_y, base_z = base_cell["position"]
            task_marker, _shape = cmds.polyCube(
                width=0.24,
                height=0.62,
                depth=0.24,
                name="CloudHive_collection_task_marker_{0:02d}".format(index),
            )
            cmds.xform(
                task_marker,
                translation=(base_x, base_y + 0.92, base_z),
                worldSpace=True,
            )
            cmds.parent(task_marker, trigger_group)
            _assign_maya_material(cmds, task_marker, resource_material)
            created.append(task_marker)

        crawl_points = []
        for cell_id in task.get("path", []):
            cell = cell_by_id.get(cell_id)
            if cell is not None:
                x, y, z = cell["position"]
                crawl_points.append((x, y + 0.62, z))
        crawl_points = _sample_demo_points(crawl_points, max_points=6)
        if not crawl_points:
            continue

        if len(crawl_points) > 1:
            crawl_curve = cmds.curve(
                degree=1,
                point=crawl_points,
                name="CloudHive_collection_crawl_{0:02d}_CRV".format(index),
            )
            cmds.parent(crawl_curve, visual_group)
            _style_demo_curve(
                cmds,
                crawl_curve,
                (0.15, 0.95, 0.72),
                line_width=4,
            )
            created.append(crawl_curve)

        hive_position = crawl_points[-1]
        flight_midpoint = (
            (hive_position[0] + flower_position[0]) * 0.5,
            (hive_position[1] + flower_position[1]) * 0.5 + 0.45,
            (hive_position[2] + flower_position[2]) * 0.5,
        )
        flight_curve = cmds.curve(
            degree=1,
            point=[hive_position, flight_midpoint, flower_position],
            name="CloudHive_collection_flight_{0:02d}_CRV".format(index),
        )
        cmds.parent(flight_curve, visual_group)
        _style_demo_curve(
            cmds,
            flight_curve,
            (0.95, 0.30, 1.0),
            line_width=4,
        )
        created.append(flight_curve)

        crawl_frames = [cursor + point_index * safe_step for point_index in range(len(crawl_points))]
        takeoff_frame = crawl_frames[-1]
        midpoint_frame = takeoff_frame + safe_step
        collection_frame = midpoint_frame + safe_step
        return_midpoint_frame = collection_frame + safe_step
        reentry_frame = return_midpoint_frame + safe_step
        task["animation_start_frame"] = crawl_frames[0]
        task["collection_frame"] = collection_frame
        task["reentry_frame"] = reentry_frame
        task["animation_end_frame"] = reentry_frame
        task["frames"] = crawl_frames + [
            midpoint_frame,
            collection_frame,
            return_midpoint_frame,
            reentry_frame,
        ]

        if bees:
            bee = bee_by_id.get(task.get("assigned_bee_id"))
            if bee is None:
                bee = bees[index % len(bees)]
            bee_object = bee.get("maya_object")
            task["bee_id"] = bee.get("id")
            if bee_object and cmds.objExists(bee_object):
                keyed_positions = list(zip(crawl_frames, crawl_points)) + [
                    (midpoint_frame, flight_midpoint),
                    (collection_frame, flower_position),
                    (return_midpoint_frame, flight_midpoint),
                    (reentry_frame, hive_position),
                ]
                for frame, position in keyed_positions:
                    cmds.currentTime(frame)
                    cmds.xform(bee_object, translation=position, worldSpace=True)
                    cmds.setKeyframe(bee_object, attribute="translate", time=frame)

                payload, _shape = cmds.polyCube(
                    width=0.14,
                    height=0.14,
                    depth=0.14,
                    name="CloudHive_collection_payload_{0:02d}".format(index),
                )
                parented = cmds.parent(payload, bee_object)
                if parented:
                    payload = parented[0]
                if cmds.objExists(payload):
                    cmds.xform(payload, translation=(0.0, -0.25, 0.0), objectSpace=True)
                    _assign_maya_material(cmds, payload, resource_material)
                    cmds.setKeyframe(
                        payload,
                        attribute="visibility",
                        time=max(1, collection_frame - 1),
                        value=0,
                    )
                    cmds.setKeyframe(
                        payload,
                        attribute="visibility",
                        time=collection_frame,
                        value=1,
                    )
                    cmds.setKeyframe(
                        payload,
                        attribute="visibility",
                        time=reentry_frame,
                        value=1,
                    )
                    cmds.setKeyframe(
                        payload,
                        attribute="visibility",
                        time=reentry_frame + 1,
                        value=0,
                    )
                    task["payload_object"] = payload

    return created


def create_bee_task_selection_visuals(bees):
    """Create static Stage 4 markers over bees that received hive tasks."""
    import maya.cmds as cmds

    group_name = _replace_empty_group(
        cmds,
        DEMO_VISUAL_GROUPS["bee_selections"],
    )
    material = _create_maya_material(
        cmds,
        "chm_demo_bee_selected_MAT",
        (0.10, 0.95, 1.0),
    )
    created = []
    for index, bee in enumerate(bees):
        if not bee.get("task_queue"):
            continue
        bee_object = bee.get("maya_object")
        if bee_object and cmds.objExists(bee_object):
            bounds = cmds.exactWorldBoundingBox(bee_object)
            x = (bounds[0] + bounds[3]) * 0.5
            y = bounds[4]
            z = (bounds[2] + bounds[5]) * 0.5
        else:
            x, y, z = bee.get("position", [0.0, 0.8, 0.0])
        marker, _shape = cmds.polyCylinder(
            radius=0.34,
            height=0.045,
            subdivisionsX=6,
            name="CloudHive_bee_selected_{0:02d}".format(index),
        )
        cmds.xform(
            marker,
            translation=(x, y + 0.48, z),
            worldSpace=True,
        )
        cmds.parent(marker, group_name)
        _assign_maya_material(cmds, marker, material)
        if bee_object and cmds.objExists(bee_object):
            cmds.pointConstraint(
                bee_object,
                marker,
                maintainOffset=True,
                name="CloudHive_bee_selected_{0:02d}_pointConstraint".format(index),
            )
        created.append(marker)
    return created


def create_deposit_update_visuals(cells, resource_events, cell_size, collection_tasks=None):
    """Create static Stage 7 markers for deposits, full cells, and re-entry."""
    import maya.cmds as cmds

    group_name = _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["deposit_updates"])
    nectar_material = _create_maya_material(
        cmds, "chm_demo_deposit_nectar_MAT", (1.0, 0.72, 0.04)
    )
    pollen_material = _create_maya_material(
        cmds, "chm_demo_deposit_pollen_MAT", (1.0, 0.28, 0.04)
    )
    full_material = _create_maya_material(
        cmds, "chm_demo_storage_full_MAT", (0.95, 0.88, 0.68)
    )
    reentry_material = _create_maya_material(
        cmds, "chm_demo_collection_reentry_MAT", (0.72, 0.30, 1.0)
    )
    cell_by_id = {cell["id"]: cell for cell in cells}
    created = []

    for index, event in enumerate(resource_events):
        cell = cell_by_id.get(event.get("target_cell"))
        if cell is None:
            continue
        x, y, z = cell["position"]
        marker, _shape = cmds.polyCylinder(
            radius=float(cell_size) * 0.36,
            height=0.10,
            subdivisionsX=6,
            name="CloudHive_deposit_update_{0:03d}".format(index),
        )
        cmds.xform(
            marker,
            translation=(x, y + 0.82, z),
            rotation=(0.0, 30.0, 0.0),
            worldSpace=True,
        )
        cmds.parent(marker, group_name)
        _assign_maya_material(
            cmds,
            marker,
            nectar_material
            if event.get("resource_type") == "nectar"
            else pollen_material,
        )
        created.append(marker)

    for index, cell in enumerate(cells):
        if not cell.get("blocked_by_capacity"):
            continue
        x, y, z = cell["position"]
        full_marker, _shape = cmds.polyCylinder(
            radius=float(cell_size) * 0.70,
            height=0.07,
            subdivisionsX=6,
            name="CloudHive_full_storage_{0:03d}".format(index),
        )
        cmds.xform(
            full_marker,
            translation=(x, y + 1.02, z),
            rotation=(0.0, 30.0, 0.0),
            worldSpace=True,
        )
        cmds.parent(full_marker, group_name)
        _assign_maya_material(cmds, full_marker, full_material)
        created.append(full_marker)

    for index, task in enumerate(collection_tasks or []):
        cell = cell_by_id.get(task.get("cloud_base_cell"))
        if cell is None:
            continue
        x, y, z = cell["position"]
        marker, _shape = cmds.polySphere(
            radius=0.20,
            name="CloudHive_collection_reentry_{0:02d}".format(index),
        )
        cmds.xform(marker, translation=(x, y + 0.90, z), worldSpace=True)
        cmds.parent(marker, group_name)
        _assign_maya_material(cmds, marker, reentry_material)
        created.append(marker)

    return created


def author_demo_stage_transitions(
    drops,
    clouds,
    cells,
    resource_events,
    bees,
    bee_base_transforms,
    path_visuals,
    blocked_visuals,
    drop_demo_visuals,
    bee_selection_visuals,
    collection_tasks,
    deposit_visuals,
    stage_ranges,
    cell_depth,
):
    """Author compact keyed previews for the seven prepared demo stages."""
    import maya.cmds as cmds

    stage_objects = {stage: [] for stage in range(1, 8)}

    stage_one_start, stage_one_end = stage_ranges[1]
    cloud_by_id = {cloud["id"]: cloud for cloud in clouds}
    for index, drop in enumerate(drops):
        marker = drop.get("maya_object")
        cloud = cloud_by_id.get(drop.get("source_cloud"))
        if not marker or not cmds.objExists(marker) or cloud is None:
            continue
        local_start = stage_one_start + (index % 6) * 2
        local_end = stage_one_end - ((len(drops) - index - 1) % 4)
        cloud_x, cloud_y, cloud_z = cloud["position"]
        landing_x, landing_y, landing_z = drop["position"]
        source = (
            cloud_x + math.sin(index * 1.7) * 0.42,
            cloud_y - 0.50,
            cloud_z + math.cos(index * 1.3) * 0.42,
        )
        landing = (landing_x, landing_y + 0.18, landing_z)
        _key_visibility_hold(cmds, marker, stage_one_start, local_start, stage_one_end)
        _key_translation(cmds, marker, local_start, source)
        _key_translation(cmds, marker, local_end, landing)
        _key_scale_values(cmds, marker, local_start, 0.45)
        _key_scale_values(cmds, marker, local_end, 1.0)
        drop["demo_transition_start"] = local_start
        drop["demo_transition_end"] = local_end
        stage_objects[1].append(marker)

    stage_two_start, stage_two_end = stage_ranges[2]
    mapping_nodes = list(drop_demo_visuals.get("mapping", []))
    validation_nodes = list(drop_demo_visuals.get("validation", []))
    _key_reveal_sequence(cmds, mapping_nodes, stage_two_start, stage_two_end)
    _key_pop_sequence(cmds, validation_nodes, stage_two_start, stage_two_end)
    stage_objects[2].extend(mapping_nodes + validation_nodes)

    stage_three_start, stage_three_end = stage_ranges[3]
    direct_nodes = list(drop_demo_visuals.get("direct_storage", []))
    task_nodes = list(drop_demo_visuals.get("task_markers", []))
    stage_three_nodes = direct_nodes + task_nodes + list(blocked_visuals)
    _key_pop_sequence(cmds, stage_three_nodes, stage_three_start, stage_three_end)
    for node in direct_nodes:
        if not cmds.objExists(node + ".translateY"):
            continue
        final_y = float(cmds.getAttr(node + ".translateY"))
        cmds.setKeyframe(
            node,
            attribute="translateY",
            time=stage_three_start,
            value=final_y + 0.55,
        )
        cmds.setKeyframe(
            node,
            attribute="translateY",
            time=stage_three_end,
            value=final_y,
        )
    stage_objects[3].extend(stage_three_nodes)

    stage_four_start, stage_four_end = stage_ranges[4]
    _key_reveal_sequence(cmds, path_visuals, stage_four_start, stage_four_end)
    _key_pop_sequence(
        cmds,
        bee_selection_visuals,
        stage_four_start,
        stage_four_end,
        peak_scale=1.45,
    )
    stage_objects[4].extend(list(path_visuals) + list(bee_selection_visuals))

    stage_five_start, stage_five_end = stage_ranges[5]
    trigger_nodes = _group_transform_children(
        cmds,
        DEMO_VISUAL_GROUPS["collection_triggers"],
    )
    _key_pop_sequence(
        cmds,
        trigger_nodes,
        stage_five_start,
        stage_five_end,
        peak_scale=1.35,
    )
    stage_objects[5].extend(trigger_nodes)

    stage_six_start, stage_six_end = stage_ranges[6]
    collection_nodes = _group_transform_children(
        cmds,
        DEMO_VISUAL_GROUPS["collection_visuals"],
    )
    _key_reveal_sequence(
        cmds,
        collection_nodes,
        stage_six_start,
        min(stage_six_end, stage_six_start + 18),
    )
    _key_bee_demo_holds(
        cmds,
        bees,
        bee_base_transforms,
        collection_tasks,
        stage_six_start,
        stage_six_end,
        stage_ranges[7][1],
    )
    for task in collection_tasks:
        payload = task.get("payload_object")
        if not payload or not cmds.objExists(payload):
            continue
        cmds.setKeyframe(
            payload,
            attribute="visibility",
            time=stage_six_end,
            value=1,
        )
        cmds.setKeyframe(
            payload,
            attribute="visibility",
            time=stage_ranges[7][0],
            value=0,
        )
    stage_objects[6].extend(collection_nodes)
    stage_objects[6].extend([
        task.get("payload_object")
        for task in collection_tasks
        if task.get("payload_object")
    ])

    stage_seven_start, stage_seven_end = stage_ranges[7]
    _key_pop_sequence(
        cmds,
        deposit_visuals,
        stage_seven_start,
        stage_seven_end,
        peak_scale=1.40,
    )
    for node in deposit_visuals:
        if not cmds.objExists(node + ".translateY"):
            continue
        final_y = float(cmds.getAttr(node + ".translateY"))
        cmds.setKeyframe(
            node,
            attribute="translateY",
            time=stage_seven_start,
            value=final_y + 0.42,
        )
        cmds.setKeyframe(
            node,
            attribute="translateY",
            time=stage_seven_end,
            value=final_y,
        )
    _key_compact_resource_updates(
        cmds,
        cells,
        resource_events,
        stage_ranges[3],
        stage_ranges[7],
        cell_depth,
    )
    stage_objects[7].extend(list(deposit_visuals))

    cmds.currentTime(1)
    return {
        "stage_objects": stage_objects,
        "keyed_object_count": sum(len(nodes) for nodes in stage_objects.values()),
    }


def _group_transform_children(cmds, group_name):
    """Return transform descendants of a generated demo group."""
    if not cmds.objExists(group_name):
        return []
    descendants = cmds.listRelatives(
        group_name,
        allDescendents=True,
        type="transform",
        fullPath=False,
    ) or []
    return list(reversed(descendants))


def _key_visibility_hold(cmds, node, stage_start, reveal_frame, stage_end):
    """Hide at the stage start, reveal once, and hold the final state."""
    if not node or not cmds.objExists(node):
        return
    reveal_frame = max(int(stage_start) + 1, int(reveal_frame))
    cmds.setKeyframe(node, attribute="visibility", time=stage_start, value=0)
    cmds.setKeyframe(
        node,
        attribute="visibility",
        time=max(int(stage_start), reveal_frame - 1),
        value=0,
    )
    cmds.setKeyframe(node, attribute="visibility", time=reveal_frame, value=1)
    cmds.setKeyframe(node, attribute="visibility", time=stage_end, value=1)


def _key_translation(cmds, node, frame, position):
    """Key one transform translation without scrubbing the Maya timeline."""
    for axis, value in zip("XYZ", position):
        cmds.setKeyframe(
            node,
            attribute="translate{0}".format(axis),
            time=frame,
            value=float(value),
        )


def _key_scale_values(cmds, node, frame, value):
    """Key uniform scale and hold it after the final authored key."""
    if not node or not cmds.objExists(node):
        return
    for axis in "XYZ":
        attribute = "scale{0}".format(axis)
        cmds.setKeyframe(node, attribute=attribute, time=frame, value=float(value))
        try:
            cmds.setInfinity(node + "." + attribute, postInfinite="constant")
        except RuntimeError:
            pass


def _key_reveal_sequence(cmds, nodes, stage_start, stage_end):
    """Reveal prepared objects progressively across one short stage."""
    valid_nodes = [node for node in nodes if node and cmds.objExists(node)]
    if not valid_nodes:
        return
    reveal_span = max(1, int(stage_end) - int(stage_start) - 4)
    for index, node in enumerate(valid_nodes):
        reveal = int(stage_start) + 2 + int(
            round(index * reveal_span / float(max(1, len(valid_nodes) - 1)))
        )
        _key_visibility_hold(cmds, node, stage_start, reveal, stage_end)


def _key_pop_sequence(
    cmds,
    nodes,
    stage_start,
    stage_end,
    peak_scale=1.25,
):
    """Reveal and pulse simple markers while leaving them visible at the end."""
    valid_nodes = [node for node in nodes if node and cmds.objExists(node)]
    if not valid_nodes:
        return
    reveal_span = max(1, int(stage_end) - int(stage_start) - 8)
    for index, node in enumerate(valid_nodes):
        reveal = int(stage_start) + 2 + int(
            round(index * reveal_span / float(max(1, len(valid_nodes) - 1)))
        )
        peak = min(int(stage_end) - 2, reveal + 4)
        _key_visibility_hold(cmds, node, stage_start, reveal, stage_end)
        _key_scale_values(cmds, node, stage_start, 0.05)
        _key_scale_values(cmds, node, reveal, 0.15)
        _key_scale_values(cmds, node, peak, peak_scale)
        _key_scale_values(cmds, node, stage_end, 1.0)


def _key_bee_demo_holds(
    cmds,
    bees,
    base_transforms,
    collection_tasks,
    stage_six_start,
    stage_six_end,
    stage_seven_end,
):
    """Hold bees still outside the compact Stage 6 collection preview."""
    task_end_by_bee = {}
    for task in collection_tasks:
        bee_id = task.get("bee_id") or task.get("assigned_bee_id")
        if bee_id:
            task_end_by_bee[bee_id] = max(
                task_end_by_bee.get(bee_id, stage_six_start),
                int(task.get("animation_end_frame", stage_six_start)),
            )

    for bee in bees:
        bee_object = bee.get("maya_object")
        if not bee_object or not cmds.objExists(bee_object):
            continue
        base_position = base_transforms.get(bee.get("id"), [0.0, 0.0, 0.0])
        _key_translation(cmds, bee_object, 1, base_position)
        _key_translation(cmds, bee_object, int(stage_six_start) - 1, base_position)

        task_end = task_end_by_bee.get(bee.get("id"))
        if task_end is None:
            final_position = base_position
        else:
            cmds.currentTime(task_end)
            final_position = cmds.xform(
                bee_object,
                query=True,
                translation=True,
                worldSpace=True,
            )
        _key_translation(cmds, bee_object, stage_six_end, final_position)
        _key_translation(cmds, bee_object, stage_seven_end, final_position)


def _key_compact_resource_updates(
    cmds,
    cells,
    resource_events,
    stage_three_range,
    stage_seven_range,
    cell_depth,
):
    """Show direct deposits in Stage 3 and transported deposits in Stage 7."""
    first_event_by_cell_resource = {}
    for event in resource_events:
        key = (event.get("target_cell"), event.get("resource_type"))
        first_event_by_cell_resource.setdefault(key, event)

    stage_three_start, stage_three_end = stage_three_range
    stage_seven_start, stage_seven_end = stage_seven_range
    max_fill_height = max(0.12, float(cell_depth) * 0.72)
    pollen_count = 8

    for cell in cells:
        capacity = max(0.000001, float(cell.get("capacity", 1.0)))
        cell_id = cell["id"]
        initial_type = cell.get("initial_type", cell.get("type"))
        for resource_type in ("nectar", "pollen"):
            initial_amount = float(cell.get("initial_{0}".format(resource_type), 0.0))
            final_amount = float(cell.get(resource_type, 0.0))
            first_event = first_event_by_cell_resource.get((cell_id, resource_type))
            pre_transport_amount = (
                float(first_event.get("before_amount", initial_amount))
                if first_event
                else final_amount
            )

            if resource_type == "nectar" and initial_type == "honey":
                fill = "{0}_nectar_level".format(cell_id)
                if not cmds.objExists(fill):
                    continue
                _key_resource_level(
                    cmds,
                    fill,
                    stage_three_start,
                    initial_amount / capacity,
                    cell_depth,
                    max_fill_height,
                )
                _key_resource_level(
                    cmds,
                    fill,
                    stage_three_end,
                    pre_transport_amount / capacity,
                    cell_depth,
                    max_fill_height,
                )
                _key_resource_level(
                    cmds,
                    fill,
                    stage_seven_start,
                    pre_transport_amount / capacity,
                    cell_depth,
                    max_fill_height,
                )
                _key_resource_level(
                    cmds,
                    fill,
                    stage_seven_end,
                    final_amount / capacity,
                    cell_depth,
                    max_fill_height,
                )

            if resource_type == "pollen" and initial_type == "pollen":
                for grain_index in range(pollen_count):
                    grain = "{0}_pollen_{1:02d}".format(cell_id, grain_index)
                    if not cmds.objExists(grain):
                        continue
                    threshold = float(grain_index + 1) / pollen_count
                    values = (
                        (stage_three_start, initial_amount),
                        (stage_three_end, pre_transport_amount),
                        (stage_seven_start, pre_transport_amount),
                        (stage_seven_end, final_amount),
                    )
                    for frame, amount in values:
                        cmds.setKeyframe(
                            grain,
                            attribute="visibility",
                            time=frame,
                            value=1 if amount / capacity >= threshold else 0,
                        )

        cap = "{0}_cap_lid".format(cell_id)
        if cmds.objExists(cap):
            initially_capped = initial_type == "capped"
            finally_capped = cell.get("type") == "capped"
            cmds.setKeyframe(
                cap,
                attribute="visibility",
                time=stage_seven_start,
                value=1 if initially_capped else 0,
            )
            cmds.setKeyframe(
                cap,
                attribute="visibility",
                time=stage_seven_end,
                value=1 if finally_capped else 0,
            )


def organize_demo_cycle_groups(cycle_number):
    """Nest all prepared stage layers under one cycle-specific Maya group."""
    import maya.cmds as cmds

    cycle_group = "CloudHive_Cycle_{0:03d}_Stages_GRP".format(int(cycle_number))
    if cmds.objExists(cycle_group):
        cmds.delete(cycle_group)
    cmds.group(empty=True, name=cycle_group)
    for group_name in DEMO_VISUAL_GROUPS.values():
        if not cmds.objExists(group_name):
            continue
        parents = cmds.listRelatives(group_name, parent=True) or []
        if not parents or parents[0] != cycle_group:
            cmds.parent(group_name, cycle_group)
    return cycle_group


def apply_demo_stage(scene_data, stage):
    """Show one prepared stage and select its short transition segment."""
    import maya.cmds as cmds

    safe_stage = max(0, min(7, int(stage)))
    visible_by_stage = {
        0: set(),
        1: {"natural_drops"},
        2: {"natural_drops", "mapping", "validation"},
        3: {"direct_storage", "task_markers", "blocked_tasks"},
        4: {"task_markers", "bee_selections", "bfs_paths", "blocked_tasks"},
        5: {"collection_triggers"},
        6: {"collection_triggers", "collection_visuals"},
        7: {"deposit_updates", "blocked_tasks"},
    }
    visible_keys = visible_by_stage[safe_stage]
    groups = scene_data.get("demo_visual_groups", DEMO_VISUAL_GROUPS)
    for group_key, group_name in groups.items():
        if cmds.objExists(group_name + ".visibility"):
            cmds.setAttr(group_name + ".visibility", group_key in visible_keys)

    frame = int(scene_data.get("demo_stage_frames", {}).get(safe_stage, 1))
    playback_range = scene_data.get("demo_playback_ranges", {}).get(
        safe_stage,
        (frame, frame + 1),
    )
    range_start = max(1, int(playback_range[0]))
    range_end = max(range_start + 1, int(playback_range[1]))
    cmds.playbackOptions(
        minTime=range_start,
        maxTime=range_end,
        loop="once",
        view="active",
    )
    cmds.currentTime(max(range_start, min(frame, range_end)))
    cmds.refresh(force=True)
    scene_data["demo_stage"] = safe_stage
    scene_data["active_demo_frame"] = cmds.currentTime(query=True)
    scene_data["active_playback_range"] = (range_start, range_end)
    scene_data["visible_demo_groups"] = sorted(visible_keys)
    return {
        "stage": safe_stage,
        "label": DEMO_STAGE_LABELS[safe_stage],
        "frame": scene_data["active_demo_frame"],
        "playback_range": scene_data["active_playback_range"],
        "visible_groups": scene_data["visible_demo_groups"],
    }


def _replace_empty_group(cmds, group_name):
    """Replace one generated visual group and return its transform name."""
    if cmds.objExists(group_name):
        cmds.delete(group_name)
    return cmds.group(empty=True, name=group_name)


def _style_demo_curve(cmds, curve, color, line_width=3):
    """Give a Maya curve an explicit viewport color and readable width."""
    shapes = cmds.listRelatives(curve, shapes=True, fullPath=True) or []
    for shape in shapes:
        cmds.setAttr(shape + ".overrideEnabled", 1)
        cmds.setAttr(shape + ".overrideRGBColors", 1)
        cmds.setAttr(
            shape + ".overrideColorRGB",
            float(color[0]),
            float(color[1]),
            float(color[2]),
            type="double3",
        )
        if cmds.attributeQuery("lineWidth", node=shape, exists=True):
            cmds.setAttr(shape + ".lineWidth", int(line_width))


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

    delivery_by_task = {}
    for record in animation_records:
        task_id = record["task_id"]
        delivery_frame = record.get("delivery_frame")
        try:
            delivery_frame = int(round(float(delivery_frame)))
        except (TypeError, ValueError):
            keyed_frames = record.get("frames") or []
            fallback_frame = keyed_frames[-1] if keyed_frames else 1
            try:
                delivery_frame = int(round(float(fallback_frame)))
            except (TypeError, ValueError):
                delivery_frame = 1
            cmds.warning(
                "Cloud-Hive Bloomfield: task '{0}' has no valid delivery frame; "
                "using animation frame {1} for its resource visual.".format(
                    task_id,
                    max(1, delivery_frame),
                )
            )
        delivery_by_task[task_id] = max(1, delivery_frame)

    events_by_cell = {}
    for event in resource_events:
        event = dict(event)
        task_id = event.get("task_id", "<unknown>")
        if task_id not in delivery_by_task:
            delivery_frame = 1
            cmds.warning(
                "Cloud-Hive Bloomfield: task '{0}' has no animation record; "
                "using frame 1 for its resource visual.".format(task_id)
            )
            delivery_by_task[task_id] = delivery_frame
        event["delivery_frame"] = delivery_by_task[task_id]
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


def clear_scene(preserve_camera=False):
    """Remove previous Cloud-Hive Meadow generated objects from the Maya scene.

    Parameters:
        preserve_camera (bool): Keep the generated camera/light rig while the
            visualization is rebuilt. The public Clear action uses the default
            False value and removes the rig with the rest of the scene.

    Returns:
        None.
    """
    import maya.cmds as cmds

    if preserve_camera and cmds.objExists(CAMERA_LIGHT_GROUP):
        camera_parent = cmds.listRelatives(
            CAMERA_LIGHT_GROUP,
            parent=True,
            fullPath=True,
        ) or []
        if camera_parent:
            try:
                cmds.parent(CAMERA_LIGHT_GROUP, world=True)
            except RuntimeError:
                # If Maya cannot detach it, deleting the root will remove it and
                # setup_camera_and_lighting() will recreate one clean rig.
                pass

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
        "CloudHive_DropMapping_GRP",
        "CloudHive_ValidationHighlights_GRP",
        "CloudHive_DirectStorage_GRP",
        "CloudHive_TaskMarkers_GRP",
        "CloudHive_BeeSelections_GRP",
        "CloudHive_CollectionTriggers_GRP",
        "CloudHive_CollectionVisuals_GRP",
        "CloudHive_DepositUpdate_GRP",
        CAMERA_LIGHT_GROUP,
        "CloudHive_Labels_GRP",
        "CloudHiveMeadow_GRP",
    ]
    groups_to_delete.extend(
        cmds.ls("CloudHive_Cycle_*_Stages_GRP", type="transform") or []
    )

    for group_name in groups_to_delete:
        if preserve_camera and group_name == CAMERA_LIGHT_GROUP:
            continue
        if cmds.objExists(group_name):
            cmds.delete(group_name)


def setup_camera_and_lighting(scene_radius=9.0):
    """Create or reuse a stable Maya overview camera and light setup.

    Parameters:
        scene_radius (float): Approximate radius used to position camera/lights.

    Returns:
        dict: Names of created camera, directional light, and ambient light nodes.
    """
    import maya.cmds as cmds

    group_name = CAMERA_LIGHT_GROUP
    if not cmds.objExists(group_name):
        cmds.group(empty=True, name=group_name)

    camera_transform, camera_shape = _find_camera_rig_node(cmds, "camera")
    if camera_transform is None:
        camera_transform, camera_shape = cmds.camera()
        camera_transform = cmds.rename(camera_transform, OVERVIEW_CAMERA)
    camera_transform = _parent_to_camera_rig(cmds, camera_transform, group_name)
    camera_shape = cmds.listRelatives(
        camera_transform,
        shapes=True,
        type="camera",
        fullPath=True,
    )[0]
    cmds.setAttr(camera_shape + ".focalLength", 35)

    sun_light, sun_shape = _find_camera_rig_node(cmds, "directionalLight")
    if sun_light is None:
        sun_shape = cmds.directionalLight(intensity=1.28)
        sun_light = cmds.listRelatives(sun_shape, parent=True, fullPath=True)[0]
        sun_light = cmds.rename(sun_light, "CloudHive_Sun_LGT")
    sun_light = _parent_to_camera_rig(cmds, sun_light, group_name)
    sun_shape = cmds.listRelatives(
        sun_light,
        shapes=True,
        type="directionalLight",
        fullPath=True,
    )[0]
    cmds.xform(sun_light, rotation=(-45.0, -30.0, 0.0), worldSpace=True)
    cmds.setAttr(sun_shape + ".intensity", 1.28)
    cmds.setAttr(sun_shape + ".color", 1.0, 0.78, 0.48, type="double3")

    ambient_light, ambient_shape = _find_camera_rig_node(cmds, "ambientLight")
    if ambient_light is None:
        ambient_shape = cmds.ambientLight(intensity=0.42)
        ambient_light = cmds.listRelatives(
            ambient_shape,
            parent=True,
            fullPath=True,
        )[0]
        ambient_light = cmds.rename(ambient_light, "CloudHive_Ambient_LGT")
    ambient_light = _parent_to_camera_rig(cmds, ambient_light, group_name)
    ambient_shape = cmds.listRelatives(
        ambient_light,
        shapes=True,
        type="ambientLight",
        fullPath=True,
    )[0]
    cmds.setAttr(ambient_shape + ".intensity", 0.42)
    cmds.setAttr(ambient_shape + ".color", 0.72, 0.74, 1.0, type="double3")

    return {
        "camera": camera_transform.rsplit("|", 1)[-1],
        "camera_shape": camera_shape.rsplit("|", 1)[-1],
        "sun_light": sun_light.rsplit("|", 1)[-1],
        "sun_shape": sun_shape.rsplit("|", 1)[-1],
        "ambient_light": ambient_light.rsplit("|", 1)[-1],
        "ambient_shape": ambient_shape.rsplit("|", 1)[-1],
    }


def _find_camera_rig_node(cmds, shape_type):
    """Return one generated transform/shape pair by Maya node type."""
    if not cmds.objExists(CAMERA_LIGHT_GROUP):
        return None, None

    shapes = cmds.listRelatives(
        CAMERA_LIGHT_GROUP,
        allDescendents=True,
        fullPath=True,
        type=shape_type,
    ) or []
    if not shapes:
        return None, None

    shape = sorted(shapes)[0]
    parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
    if not parents:
        return None, None
    return parents[0], shape


def _parent_to_camera_rig(cmds, transform, group_name):
    """Parent a generated transform under the rig and return its full DAG path."""
    group_paths = cmds.ls(group_name, long=True) or [group_name]
    group_path = group_paths[0]
    parents = cmds.listRelatives(transform, parent=True, fullPath=True) or []
    if not parents or parents[0] != group_path:
        parented = cmds.parent(transform, group_path)
        if parented:
            transform = parented[0]
    transform_paths = cmds.ls(transform, long=True) or [transform]
    return transform_paths[0]


def frame_scene_overview(camera_transform=OVERVIEW_CAMERA, fallback_radius=9.0, padding=1.35):
    """Place the render camera in a wide 3/4 view around generated content.

    The placement is recomputed from world-space scene bounds, so cloud height,
    drops, bees, and BFS paths are included. It never changes the active viewport
    camera; callers may opt into the camera only for the first Generate action.

    Parameters:
        camera_transform (str): Camera transform to position.
        fallback_radius (float): Safe framing radius if Maya cannot read bounds.
        padding (float): Extra space around the bounded scene.

    Returns:
        dict | None: Overview center, radius, and camera distance.
    """
    import maya.cmds as cmds

    if not cmds.objExists(camera_transform):
        cmds.warning(
            "Cloud-Hive Bloomfield: overview camera '{0}' does not exist.".format(
                camera_transform
            )
        )
        return None

    content_groups = [
        "CloudHive_Honeycomb_GRP",
        "CloudHive_Clouds_GRP",
        "CloudHive_CloudFlowers_GRP",
        "CloudHive_ResourceDrops_GRP",
        "CloudHive_Bees_GRP",
        "CloudHive_BeeTaskPaths_GRP",
        "CloudHive_FallingResources_GRP",
        "CloudHive_CellResources_GRP",
        "CloudHive_BlockedTasks_GRP",
        "CloudHive_DropMapping_GRP",
        "CloudHive_ValidationHighlights_GRP",
        "CloudHive_DirectStorage_GRP",
        "CloudHive_TaskMarkers_GRP",
        "CloudHive_BeeSelections_GRP",
        "CloudHive_CollectionTriggers_GRP",
        "CloudHive_CollectionVisuals_GRP",
        "CloudHive_DepositUpdate_GRP",
        "CloudHive_Labels_GRP",
    ]
    bounded_nodes = [node for node in content_groups if cmds.objExists(node)]
    bounds = None
    if bounded_nodes:
        try:
            bounds = cmds.exactWorldBoundingBox(*bounded_nodes)
        except RuntimeError:
            bounds = None

    safe_fallback = max(1.0, float(fallback_radius))
    if bounds and len(bounds) == 6 and all(math.isfinite(value) for value in bounds):
        center = (
            (bounds[0] + bounds[3]) * 0.5,
            (bounds[1] + bounds[4]) * 0.5,
            (bounds[2] + bounds[5]) * 0.5,
        )
        span_x = max(0.1, bounds[3] - bounds[0])
        span_y = max(0.1, bounds[4] - bounds[1])
        span_z = max(0.1, bounds[5] - bounds[2])
        bounds_radius = 0.5 * math.sqrt(
            (span_x * span_x) + (span_y * span_y) + (span_z * span_z)
        )
        scene_radius = max(bounds_radius, safe_fallback)
    else:
        center = (0.0, safe_fallback * 0.25, 0.0)
        scene_radius = safe_fallback

    camera_shapes = cmds.listRelatives(
        camera_transform,
        shapes=True,
        type="camera",
    ) or []
    if not camera_shapes:
        cmds.warning(
            "Cloud-Hive Bloomfield: overview transform '{0}' has no camera shape.".format(
                camera_transform
            )
        )
        return None

    camera_shape = camera_shapes[0]
    focal_length = 35.0
    cmds.setAttr(camera_shape + ".focalLength", focal_length)
    vertical_aperture = cmds.getAttr(camera_shape + ".verticalFilmAperture") * 25.4
    vertical_fov = 2.0 * math.atan(vertical_aperture / (2.0 * focal_length))
    half_fov_tangent = max(0.1, math.tan(vertical_fov * 0.5))
    distance = max(12.0, scene_radius * max(1.0, float(padding)) / half_fov_tangent)

    view_vector = (1.0, 0.82, 1.15)
    view_length = math.sqrt(sum(component * component for component in view_vector))
    view_direction = tuple(component / view_length for component in view_vector)
    camera_position = tuple(
        center[index] + view_direction[index] * distance
        for index in range(3)
    )
    target_vector = tuple(
        center[index] - camera_position[index]
        for index in range(3)
    )
    horizontal_length = math.sqrt(
        (target_vector[0] * target_vector[0])
        + (target_vector[2] * target_vector[2])
    )
    pitch = math.degrees(math.atan2(target_vector[1], horizontal_length))
    yaw = math.degrees(math.atan2(-target_vector[0], -target_vector[2]))

    cmds.xform(
        camera_transform,
        translation=camera_position,
        rotation=(pitch, yaw, 0.0),
        worldSpace=True,
    )
    cmds.setAttr(camera_shape + ".nearClipPlane", 0.1)
    cmds.setAttr(
        camera_shape + ".farClipPlane",
        max(1000.0, distance + scene_radius * 4.0),
    )

    return {
        "center": center,
        "radius": scene_radius,
        "distance": distance,
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

        # At the static Stage 1 frame, future scheduled drops would otherwise
        # be invisible. Preview markers keep every new drop legible under its
        # source cloud, then disappear as soon as the user presses Play.
        if local_start > int(start_frame):
            preview, _shape = cmds.polySphere(
                radius=size * 1.15,
                name="CloudHive_{0}_drop_preview_{1:03d}".format(
                    resource_type,
                    index,
                ),
            )
            cmds.xform(
                preview,
                translation=(start_x, start_y, start_z),
                worldSpace=True,
            )
            cmds.parent(preview, group_name)
            _assign_maya_material(
                cmds,
                preview,
                nectar_material if resource_type == "nectar" else pollen_material,
            )
            cmds.setKeyframe(
                preview,
                attribute="visibility",
                time=int(start_frame),
                value=1,
            )
            cmds.setKeyframe(
                preview,
                attribute="visibility",
                time=int(start_frame) + 1,
                value=0,
            )
            created.append(preview)

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


def _parent_known_scene_groups(additional_groups=None):
    """Parent generated CloudHive groups under the visualization root group.

    Parameters:
        additional_groups (list[str] | None): Extra generated groups, such as
            the current cycle's prepared stage container.

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
        "CloudHive_MeadowDetails_GRP",
        "CloudHive_BeehiveBoxes_GRP",
        "CloudHive_Bees_GRP",
        "CloudHive_CellResources_GRP",
        "CloudHive_Ground_GRP",
        "CloudHive_CameraLight_GRP",
        "CloudHive_Labels_GRP",
    ]
    generated_groups.extend(additional_groups or [])

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
