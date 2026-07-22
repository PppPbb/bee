"""Bee task creation, assignment, and Maya animation helpers for Cloud-Hive Meadow."""

import math
import re

from hive_module import bfs_find_path, create_voxel_material, get_cell_map


def _sanitize_maya_name_component(value):
    """Return one Maya-safe object-name component.

    Maya DAG separators, namespaces, whitespace, and other punctuation are
    replaced with underscores. The helper stays pure Python so importing this
    module outside Maya remains supported.
    """
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or ""))
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    if not sanitized:
        return "unnamed"
    if sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized


def expected_cell_type_for_resource(resource_type):
    """Return the storage cell type expected for a resource.

    Parameters:
        resource_type (str): Resource type, usually "nectar" or "pollen".

    Returns:
        str | None: Expected cell type, or None for an unknown resource type.
    """
    if resource_type == "nectar":
        return "honey"
    if resource_type == "pollen":
        return "pollen"
    return None


def validate_resource_cell(drop, cell):
    """Check whether a resource drop landed in a correct storage cell.

    Parameters:
        drop (dict): Resource drop dictionary from cloud_resource_module.
        cell (dict): Honeycomb cell dictionary from hive_module.

    Returns:
        bool: True when the cell is non-blocked and matches the resource type.
    """
    if cell is None or cell.get("is_blocked"):
        return False

    expected_type = expected_cell_type_for_resource(drop.get("resource_type"))
    if expected_type is None:
        return False

    # Empty, capped, and mismatched storage cells all fail validation.
    return cell.get("type") == expected_type


def deposit_resource(drop, cell):
    """Deposit a resource amount into a honeycomb cell.

    Parameters:
        drop (dict): Resource drop-like dictionary with resource_type and amount.
        cell (dict): Honeycomb cell dictionary to update.

    Returns:
        float: Amount actually deposited after respecting cell capacity.
    """
    if cell is None or cell.get("is_blocked"):
        return 0.0

    resource_field = _resource_field(drop.get("resource_type"))
    if resource_field is None:
        return 0.0

    requested_amount = max(0.0, float(drop.get("amount", 0.0)))
    remaining_capacity = _remaining_cell_capacity(cell)
    deposited_amount = min(requested_amount, remaining_capacity)

    cell[resource_field] = float(cell.get(resource_field, 0.0)) + deposited_amount
    return deposited_amount


def create_transport_task(drop, source_cell):
    """Create a transport or blocked-cleanup task for an invalid drop.

    Parameters:
        drop (dict): Resource drop dictionary with resource_type and amount.
        source_cell (dict): Cell where the resource landed.

    Returns:
        dict: Task dictionary for bee assignment and BFS pathing.
    """
    resource_type = drop.get("resource_type")
    target_type = expected_cell_type_for_resource(resource_type)
    is_blocked_source = source_cell.get("is_blocked") or source_cell.get("type") == "capped"

    # Blocked/capped drops become high-priority cleanup tasks because bees cannot
    # use capped cells as storage or path cells.
    if is_blocked_source:
        task_type = "clean_blocked"
        priority = 100
    elif resource_type == "nectar":
        task_type = "transport_nectar"
        priority = 20
    else:
        task_type = "transport_pollen"
        priority = 20

    return {
        "id": "task_{0}".format(drop.get("id")),
        "type": task_type,
        "source_cell": source_cell["id"],
        "target_type": target_type,
        "resource_type": resource_type,
        "amount": float(drop.get("amount", 0.0)),
        "priority": priority,
        "status": "pending",
        "path": [],
    }


def create_tasks_from_drops(drops, cells):
    """Validate mapped drops, deposit correct drops, and create tasks for wrong drops.

    Parameters:
        drops (list[dict]): Resource drops with mapped_cell_id values.
        cells (list[dict]): Honeycomb cell dictionaries.

    Returns:
        list[dict]: Transport and cleanup tasks for invalid drops.
    """
    cell_map = get_cell_map(cells)
    tasks = []

    for drop in drops:
        mapped_cell_id = drop.get("mapped_cell_id")
        source_cell = cell_map.get(mapped_cell_id)
        if source_cell is None:
            continue

        resource_field = _resource_field(drop.get("resource_type"))
        landing_before_amount = (
            float(source_cell.get(resource_field, 0.0))
            if resource_field is not None
            else 0.0
        )

        if validate_resource_cell(drop, source_cell):
            deposited_amount = deposit_resource(drop, source_cell)
            drop["landing_cell_id"] = source_cell["id"]
            drop["landing_deposited_amount"] = deposited_amount
            drop["landing_before_amount"] = landing_before_amount
            drop["landing_after_amount"] = landing_before_amount + deposited_amount
            drop["landing_is_valid"] = True
            continue

        # Wrong non-blocked cells temporarily hold the resource until a bee moves
        # it to a valid storage cell. Blocked cells create cleanup tasks but do
        # not store the resource because they are not valid path/storage nodes.
        deposited_amount = 0.0
        if not source_cell.get("is_blocked"):
            deposited_amount = deposit_resource(drop, source_cell)

        drop["landing_cell_id"] = source_cell["id"]
        drop["landing_deposited_amount"] = deposited_amount
        drop["landing_before_amount"] = landing_before_amount
        drop["landing_after_amount"] = landing_before_amount + deposited_amount
        drop["landing_is_valid"] = False

        task = create_transport_task(drop, source_cell)
        if not source_cell.get("is_blocked"):
            task["amount"] = deposited_amount
        tasks.append(task)

    return tasks


def create_bees(bee_count, start_position):
    """Create simple bee dictionaries for task assignment.

    Parameters:
        bee_count (int): Number of bees to create.
        start_position (list[float]): Initial [x, y, z] position for every bee.

    Returns:
        list[dict]: Bee dictionaries.
    """
    if bee_count < 0:
        raise ValueError("bee_count must be 0 or greater")
    if len(start_position) != 3:
        raise ValueError("start_position must contain [x, y, z]")

    bees = []
    for index in range(int(bee_count)):
        bees.append(
            {
                "id": "bee_{0:02d}".format(index),
                "position": list(start_position),
                "current_task": None,
                "maya_object": None,
            }
        )
    return bees


def select_task_for_bee(bee, tasks, cells):
    """Assign the best pending task to a bee.

    Parameters:
        bee (dict): Bee dictionary.
        tasks (list[dict]): Task dictionaries.
        cells (list[dict]): Honeycomb cell dictionaries.

    Returns:
        dict | None: Selected task dictionary, or None when no task is pending.
    """
    # A blocked-cell cleanup task has no traversable BFS path. Keep it in the
    # data for reporting, but assign workers only tasks they can demonstrate.
    pending_tasks = [
        task
        for task in tasks
        if task.get("status") == "pending" and task.get("path")
    ]
    if not pending_tasks:
        bee["current_task"] = None
        return None

    cell_map = get_cell_map(cells)

    def task_sort_key(task):
        source_cell = cell_map.get(task.get("source_cell"))
        if source_cell is None:
            distance = float("inf")
        else:
            distance = _distance_2d(bee["position"], source_cell["position"])
        return (-int(task.get("priority", 0)), distance, task.get("id", ""))

    selected_task = min(pending_tasks, key=task_sort_key)
    selected_task["status"] = "assigned"
    bee["current_task"] = selected_task["id"]
    return selected_task


def assign_paths_to_tasks(tasks, cells):
    """Assign BFS paths from task source cells to target storage cell types.

    Parameters:
        tasks (list[dict]): Task dictionaries.
        cells (list[dict]): Honeycomb cell dictionaries.

    Returns:
        list[dict]: The same task list with path values updated.
    """
    for task in tasks:
        # BFS comes from hive_module.py, so bee tasks reuse the honeycomb graph
        # and blocked-cell rules already defined by the hive system.
        if task.get("source_cell") is None or task.get("target_type") is None:
            task["path"] = []
            continue

        task["path"] = bfs_find_path(
            cells,
            task["source_cell"],
            task["target_type"],
        )

    return tasks


def complete_task(task, cells):
    """Move a task resource from its source cell to the final BFS target cell.

    Parameters:
        task (dict): Task dictionary with a BFS path.
        cells (list[dict]): Honeycomb cell dictionaries.

    Returns:
        float: Amount moved into the target cell.
    """
    path = task.get("path", [])
    if not path:
        return 0.0

    cell_map = get_cell_map(cells)
    source_cell = cell_map.get(task.get("source_cell"))
    target_cell = cell_map.get(path[-1])
    resource_field = _resource_field(task.get("resource_type"))
    if source_cell is None or target_cell is None or resource_field is None:
        return 0.0

    available_amount = max(0.0, float(source_cell.get(resource_field, 0.0)))
    requested_amount = max(0.0, float(task.get("amount", 0.0)))
    movable_amount = min(available_amount, requested_amount)

    transfer_drop = {
        "resource_type": task.get("resource_type"),
        "amount": movable_amount,
    }
    deposited_amount = deposit_resource(transfer_drop, target_cell)
    source_cell[resource_field] = max(
        0.0,
        float(source_cell.get(resource_field, 0.0)) - deposited_amount,
    )

    capacity = max(0.0, float(target_cell.get("capacity", 0.0)))
    used_capacity = float(target_cell.get("nectar", 0.0)) + float(
        target_cell.get("pollen", 0.0)
    )
    became_capped = capacity > 0.0 and used_capacity >= capacity - 0.000001
    if became_capped:
        target_cell["type"] = "capped"
        target_cell["is_blocked"] = True
        target_cell["became_capped"] = True

    task["completed_amount"] = deposited_amount
    task["target_cell"] = target_cell["id"]
    task["became_capped"] = became_capped

    remaining_requested = max(0.0, requested_amount - deposited_amount)
    source_remaining = float(source_cell.get(resource_field, 0.0))

    # Mark the task done only when the requested movement is complete, or when
    # the source cell no longer contains that resource to move.
    if (
        requested_amount == 0.0
        or remaining_requested <= 0.000001
        or source_remaining <= 0.000001
    ):
        task["status"] = "done"

    return deposited_amount


def summarize_tasks(tasks):
    """Summarize tasks by status and task type.

    Parameters:
        tasks (list[dict]): Task dictionaries.

    Returns:
        dict: Summary with total count, status counts, and type counts.
    """
    summary = {
        "total": len(tasks),
        "by_status": {},
        "by_type": {},
    }

    for task in tasks:
        status = task.get("status", "unknown")
        task_type = task.get("type", "unknown")
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
        summary["by_type"][task_type] = summary["by_type"].get(task_type, 0) + 1

    return summary


def _resource_field(resource_type):
    """Return the cell amount field for a resource type.

    Parameters:
        resource_type (str): Resource type, usually "nectar" or "pollen".

    Returns:
        str | None: Cell field name, or None for an unknown resource type.
    """
    if resource_type == "nectar":
        return "nectar"
    if resource_type == "pollen":
        return "pollen"
    return None


def _remaining_cell_capacity(cell):
    """Calculate remaining total resource capacity for a cell.

    Parameters:
        cell (dict): Honeycomb cell dictionary.

    Returns:
        float: Remaining capacity after nectar and pollen already in the cell.
    """
    capacity = max(0.0, float(cell.get("capacity", 0.0)))
    used_capacity = float(cell.get("nectar", 0.0)) + float(cell.get("pollen", 0.0))
    return max(0.0, capacity - used_capacity)


def _distance_2d(pos_a, pos_b):
    """Measure distance between two positions on the XZ ground plane.

    Parameters:
        pos_a (list[float]): First [x, y, z] position.
        pos_b (list[float]): Second [x, y, z] position.

    Returns:
        float: Euclidean distance using x and z only.
    """
    dx = pos_a[0] - pos_b[0]
    dz = pos_a[2] - pos_b[2]
    return math.sqrt((dx * dx) + (dz * dz))


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
        node (str): Maya transform node name.
        material (str): Maya material node name.

    Returns:
        None.
    """
    cmds.select(node, replace=True)
    cmds.hyperShade(assign=material)
    cmds.select(clear=True)


def _distance_3d(pos_a, pos_b):
    """Measure full three-dimensional distance between two positions."""
    return math.sqrt(sum(
        (float(pos_a[index]) - float(pos_b[index])) ** 2
        for index in range(3)
    ))


def calculate_bee_frames_per_unit(tasks, cells, frame_step=22):
    """Convert the UI's frames-per-cell value to frames per world unit.

    Adjacent honeycomb centers are equally spaced, so their median distance is
    a stable scene-scale reference. The resulting value can then time cloud,
    vertical, and hive movement with one consistent world-space speed.
    """
    cell_map = get_cell_map(cells)
    path_distances = []
    for task in tasks:
        path = task.get("path") or []
        for index in range(1, len(path)):
            previous_cell = cell_map.get(path[index - 1])
            current_cell = cell_map.get(path[index])
            if previous_cell is None or current_cell is None:
                continue
            distance = _distance_3d(
                previous_cell["position"],
                current_cell["position"],
            )
            if distance > 0.000001:
                path_distances.append(distance)

    if path_distances:
        sorted_distances = sorted(path_distances)
        middle = len(sorted_distances) // 2
        if len(sorted_distances) % 2:
            reference_distance = sorted_distances[middle]
        else:
            reference_distance = (
                sorted_distances[middle - 1] + sorted_distances[middle]
            ) * 0.5
    else:
        reference_distance = 1.0
    return max(1.0, float(frame_step) / max(0.000001, reference_distance))


def _append_constant_speed_waypoint(
    waypoints,
    frames,
    position,
    frames_per_unit,
):
    """Append a waypoint whose frame is proportional to traveled distance."""
    point = tuple(float(value) for value in position)
    if not waypoints:
        waypoints.append(point)
        return
    distance = _distance_3d(waypoints[-1], point)
    duration = max(1, int(round(distance * float(frames_per_unit))))
    waypoints.append(point)
    frames.append(frames[-1] + duration)


def plan_bee_collection_cycle(
    bee,
    task,
    cells,
    clouds,
    drops,
    start_position,
    frame_start=1,
    frames_per_unit=12.0,
    fall_duration=64,
    lane_offset=0.0,
):
    """Plan one continuous, constant-speed bee collection route.

    A worker begins at its real previous endpoint, visits the source cloud,
    waits at the landed resource only when necessary, follows the BFS path, and
    finishes at the delivery cell. It does not return to a shared idle point.
    """
    path = task.get("path") or []
    if not path:
        return None

    drop_id = task.get("id", "")
    if drop_id.startswith("task_"):
        drop_id = drop_id[5:]
    drop = next((item for item in drops if item.get("id") == drop_id), None)
    cloud = None
    if drop is not None:
        cloud = next(
            (item for item in clouds if item.get("id") == drop.get("source_cloud")),
            None,
        )

    cell_map = get_cell_map(cells)
    source_cell = cell_map.get(task.get("source_cell"))
    waypoints = [tuple(float(value) for value in start_position)]
    frames = [int(frame_start)]
    drop_start = None
    drop_end = None

    if cloud is not None and source_cell is not None:
        cloud_x, cloud_y, cloud_z = cloud["position"]
        cloud_hover = (
            cloud_x + float(lane_offset) * 0.35,
            cloud_y + 0.55,
            cloud_z,
        )
        _append_constant_speed_waypoint(
            waypoints,
            frames,
            cloud_hover,
            frames_per_unit,
        )
        drop_start = frames[-1]

        source_x, source_y, source_z = source_cell["position"]
        source_hover = (source_x, source_y + 0.75, source_z)
        _append_constant_speed_waypoint(
            waypoints,
            frames,
            source_hover,
            frames_per_unit,
        )
        drop_end = drop_start + max(1, int(fall_duration))
        if frames[-1] < drop_end:
            # Repeating the same position creates a deliberate hover, not a
            # change of flight speed, while the resource finishes falling.
            waypoints.append(source_hover)
            frames.append(drop_end)
        # Leave the landed resource visible briefly before pickup so the cell
        # fill animation reads as an actual deposit rather than a one-frame pop.
        collection_hold_frames = max(5, int(round(frames_per_unit * 0.40)))
        waypoints.append(source_hover)
        frames.append(frames[-1] + collection_hold_frames)
        pickup_waypoint_index = len(waypoints) - 1
    else:
        source_position = None
        if source_cell is not None:
            x, y, z = source_cell["position"]
            source_position = (x, y + 0.75, z)
        if source_position is not None:
            _append_constant_speed_waypoint(
                waypoints,
                frames,
                source_position,
                frames_per_unit,
            )
        pickup_waypoint_index = len(waypoints) - 1

    for cell_id in path[1:]:
        cell = cell_map.get(cell_id)
        if cell is None:
            continue
        x, y, z = cell["position"]
        _append_constant_speed_waypoint(
            waypoints,
            frames,
            (x, y + 0.75, z),
            frames_per_unit,
        )

    return {
        "waypoints": waypoints,
        "frames": frames,
        "pickup_waypoint_index": pickup_waypoint_index,
        "delivery_waypoint_index": len(waypoints) - 1,
        "drop_start_frame": drop_start,
        "drop_end_frame": drop_end,
        "start_position": waypoints[0],
        "end_position": waypoints[-1],
        "frames_per_unit": float(frames_per_unit),
    }


def create_bee_geometry(bees, bee_scale=1.0):
    """Create simple stylized Maya bee objects.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so the module can still be imported and tested outside Autodesk Maya.

    Parameters:
        bees (list[dict]): Bee dictionaries.
        bee_scale (float): Visual scale multiplier for bee objects.

    Returns:
        list[dict]: The same bees list with maya_object names updated.
    """
    import maya.cmds as cmds

    if bee_scale <= 0:
        raise ValueError("bee_scale must be greater than 0")

    root_group = "CloudHive_Bees_GRP"
    if not cmds.objExists(root_group):
        cmds.group(empty=True, name=root_group)

    body_material = _create_maya_material(cmds, "chm_bee_body_gold_MAT", (1.0, 0.72, 0.05))
    stripe_material = _create_maya_material(cmds, "chm_bee_stripe_dark_MAT", (0.08, 0.06, 0.04))
    wing_material = _create_maya_material(cmds, "chm_bee_wing_blue_MAT", (0.62, 0.86, 1.0))

    for bee_index, bee in enumerate(bees):
        bee_group = cmds.group(empty=True, name="{0}_GRP".format(bee["id"]))
        cmds.parent(bee_group, root_group)
        default_x, default_y, default_z = bee["position"]
        default_x += (bee_index - (len(bees) - 1) * 0.5) * 0.55 * bee_scale
        base_x, base_y, base_z = bee.get(
            "animation_start_position",
            (default_x, default_y, default_z),
        )
        cmds.xform(
            bee_group,
            translation=(base_x, base_y, base_z),
            worldSpace=True,
        )

        body, _body_shape = cmds.polyCube(
            width=0.52 * bee_scale,
            height=0.28 * bee_scale,
            depth=0.30 * bee_scale,
            name="{0}_body".format(bee["id"]),
        )
        cmds.parent(body, bee_group)
        cmds.setAttr(body + ".translate", 0.0, 0.0, 0.0, type="double3")
        _assign_maya_material(cmds, body, body_material)

        for stripe_index, offset_x in enumerate((-0.12, 0.12)):
            stripe, _stripe_shape = cmds.polyCube(
                width=0.055 * bee_scale,
                height=0.295 * bee_scale,
                depth=0.315 * bee_scale,
                name="{0}_stripe_{1:02d}".format(bee["id"], stripe_index),
            )
            cmds.parent(stripe, bee_group)
            cmds.setAttr(
                stripe + ".translate",
                offset_x * bee_scale,
                0.0,
                0.0,
                type="double3",
            )
            _assign_maya_material(cmds, stripe, stripe_material)

        for wing_index, offset_z in enumerate((-0.16, 0.16)):
            wing, _wing_shape = cmds.polyCube(
                width=0.26 * bee_scale,
                height=0.035 * bee_scale,
                depth=0.20 * bee_scale,
                name="{0}_wing_{1:02d}".format(bee["id"], wing_index),
            )
            cmds.parent(wing, bee_group)
            cmds.setAttr(
                wing + ".translate",
                0.0,
                0.18 * bee_scale,
                offset_z * bee_scale,
                type="double3",
            )
            _assign_maya_material(cmds, wing, wing_material)

        bee["maya_object"] = bee_group

    return bees


def animate_bee_collection_cycle(
    bee,
    task,
    cells,
    clouds,
    drops,
    frame_start=1,
    frame_step=10,
    bee_index=0,
):
    """Animate one worker continuously from its prior endpoint to a target.

    The task path remains the path calculated by hive_module.bfs_find_path.
    Moving segments use distance-based frames and linear Maya tangents.
    """
    import maya.cmds as cmds

    bee_object = bee.get("maya_object")
    path = task.get("path", []) if task else []
    if not bee_object or not cmds.objExists(bee_object) or not path:
        return []

    drop_id = task.get("id", "")
    if drop_id.startswith("task_"):
        drop_id = drop_id[5:]
    drop = next((item for item in drops if item.get("id") == drop_id), None)
    if drop is None:
        return animate_bee_on_path(bee, task, cells, frame_start, frame_step)

    plan = task.get("animation_plan")
    if not plan:
        lane_offset = (bee_index - 1) * 0.55
        start_position = bee.get(
            "animation_current_position",
            bee.get("animation_start_position", bee.get("position", [0.0, 0.8, 0.0])),
        )
        plan = plan_bee_collection_cycle(
            bee,
            task,
            cells,
            clouds,
            drops,
            start_position=start_position,
            frame_start=frame_start,
            frames_per_unit=calculate_bee_frames_per_unit(
                [task],
                cells,
                frame_step=frame_step,
            ),
            fall_duration=max(24, int(frame_step) * 2),
            lane_offset=lane_offset,
        )
    if not plan:
        return animate_bee_on_path(bee, task, cells, frame_start, frame_step)

    waypoints = plan["waypoints"]
    waypoint_frames = plan["frames"]
    delivery_waypoint_index = int(plan["delivery_waypoint_index"])
    pickup_waypoint_index = int(plan["pickup_waypoint_index"])

    frames = []
    for frame, position in zip(waypoint_frames, waypoints):
        cmds.currentTime(frame)
        cmds.xform(bee_object, translation=position, worldSpace=True)
        cmds.setKeyframe(bee_object, attribute="translate", time=frame)
        frames.append(frame)

    if len(frames) >= 2:
        cmds.keyTangent(
            bee_object,
            attribute=("translateX", "translateY", "translateZ"),
            time=(frames[0], frames[-1]),
            inTangentType="linear",
            outTangentType="linear",
        )

    resource_type = drop.get("resource_type", "nectar")
    pickup_frame = frames[pickup_waypoint_index]
    delivery_frame = frames[delivery_waypoint_index]
    bee["animation_frames"] = frames
    bee["animation_current_position"] = list(plan["end_position"])
    bee["position"] = list(plan["end_position"])
    bee["resource_type"] = resource_type
    task["delivery_frame"] = delivery_frame
    task["pickup_frame"] = pickup_frame
    task["payload_object"] = None

    safe_bee_id = _sanitize_maya_name_component(bee.get("id", "bee"))
    safe_task_id = _sanitize_maya_name_component(task.get("id", "task"))
    safe_resource_type = _sanitize_maya_name_component(resource_type)
    payload_name = "{0}_{1}_{2}_payload".format(
        safe_bee_id,
        safe_task_id,
        safe_resource_type,
    )
    if resource_type == "nectar":
        payload_material = create_voxel_material(cmds, "nectar_glow")
        payload_width = 0.20
        payload_height = 0.24
    else:
        payload_material = _create_maya_material(
            cmds,
            "chm_bee_payload_{0}_MAT".format(safe_resource_type),
            (1.0, 0.35, 0.08),
        )
        payload_width = 0.13
        payload_height = 0.13
    payload_nodes = cmds.polyCube(
        width=payload_width,
        height=payload_height,
        depth=payload_width,
        name=payload_name,
    )
    payload = payload_nodes[0] if payload_nodes else None
    if not payload or not cmds.objExists(payload):
        cmds.warning(
            "Cloud-Hive Bloomfield: payload '{0}' was not created for task "
            "'{1}'; skipping payload animation.".format(payload_name, task.get("id"))
        )
        return frames

    parented = cmds.parent(payload, bee_object)
    if parented:
        payload = parented[0]

    if not payload or not cmds.objExists(payload):
        cmds.warning(
            "Cloud-Hive Bloomfield: payload '{0}' is missing after parenting "
            "for task '{1}'; skipping payload animation.".format(
                payload_name,
                task.get("id"),
            )
        )
        return frames

    cmds.xform(payload, translation=(0.0, -0.25, 0.0), objectSpace=True)

    if not cmds.objExists(payload):
        cmds.warning(
            "Cloud-Hive Bloomfield: payload '{0}' disappeared before material "
            "assignment; skipping payload animation.".format(payload_name)
        )
        return frames
    _assign_maya_material(cmds, payload, payload_material)

    visibility_keys = (
        (pickup_frame - 1, 0),
        (pickup_frame, 1),
        (delivery_frame, 1),
        (delivery_frame + 1, 0),
    )
    payload_animation_complete = True
    for keyframe, visibility in visibility_keys:
        if not cmds.objExists(payload):
            cmds.warning(
                "Cloud-Hive Bloomfield: payload '{0}' disappeared before frame "
                "{1}; skipping remaining payload keyframes.".format(
                    payload_name,
                    keyframe,
                )
            )
            payload_animation_complete = False
            break
        cmds.setKeyframe(
            payload,
            attribute="visibility",
            time=keyframe,
            value=visibility,
        )

    if not payload_animation_complete:
        return frames
    if not cmds.objExists(payload):
        cmds.warning(
            "Cloud-Hive Bloomfield: payload '{0}' disappeared after keyframing; "
            "skipping payload registration.".format(payload_name)
        )
        return frames

    task["payload_object"] = payload
    bee.setdefault("payload_objects", []).append(payload)

    return frames


def animate_bee_on_path(bee, task, cells, frame_start=1, frame_step=12):
    """Animate a Maya bee object along a task path with simple keyframes.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so the module can still be imported and tested outside Autodesk Maya.

    Parameters:
        bee (dict): Bee dictionary with a maya_object value.
        task (dict): Task dictionary with a path.
        cells (list[dict]): Honeycomb cell dictionaries.
        frame_start (int): First animation frame.
        frame_step (int): Frame spacing between path cells.

    Returns:
        list[int]: Frames where keyframes were set.
    """
    import maya.cmds as cmds

    bee_object = bee.get("maya_object")
    if not bee_object or not cmds.objExists(bee_object):
        return []

    cell_map = get_cell_map(cells)
    frames = []
    flight_height = 0.7

    for index, cell_id in enumerate(task.get("path", [])):
        cell = cell_map.get(cell_id)
        if cell is None:
            continue

        frame = frame_start + (index * frame_step)
        x, y, z = cell["position"]
        cmds.currentTime(frame)
        cmds.xform(bee_object, translation=(x, y + flight_height, z), worldSpace=True)
        cmds.setKeyframe(bee_object, attribute="translate", time=frame)
        frames.append(frame)
        bee["position"] = [x, y + flight_height, z]

    if len(frames) >= 2:
        cmds.keyTangent(
            bee_object,
            attribute=("translateX", "translateY", "translateZ"),
            time=(frames[0], frames[-1]),
            inTangentType="linear",
            outTangentType="linear",
        )

    return frames


def create_task_path_visuals(tasks, cells):
    """Create Maya curves and markers for task BFS paths.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so the module can still be imported and tested outside Autodesk Maya.

    Parameters:
        tasks (list[dict]): Task dictionaries with path values.
        cells (list[dict]): Honeycomb cell dictionaries.

    Returns:
        list[str]: Maya object names created for path visualization.
    """
    import maya.cmds as cmds

    cell_map = get_cell_map(cells)
    created_objects = []

    root_group = "CloudHive_BeeTaskPaths_GRP"
    if not cmds.objExists(root_group):
        cmds.group(empty=True, name=root_group)

    path_material = _create_maya_material(cmds, "chm_task_path_cyan_MAT", (0.0, 0.95, 1.0))
    marker_material = _create_maya_material(cmds, "chm_task_marker_white_MAT", (0.92, 0.96, 1.0))
    start_material = _create_maya_material(cmds, "chm_task_start_red_MAT", (1.0, 0.08, 0.04))
    target_material = _create_maya_material(cmds, "chm_task_target_green_MAT", (0.08, 1.0, 0.28))

    for task in tasks:
        points = []
        for cell_id in task.get("path", []):
            cell = cell_map.get(cell_id)
            if cell is None:
                continue
            x, y, z = cell["position"]
            points.append((x, y + 1.05, z))

        if not points:
            continue

        if len(points) > 1:
            curve = cmds.curve(
                d=1,
                p=points,
                name="{0}_path_CRV".format(task["id"]),
            )
            cmds.parent(curve, root_group)
            _assign_maya_material(cmds, curve, path_material)
            curve_shapes = cmds.listRelatives(curve, shapes=True) or []
            for curve_shape in curve_shapes:
                if cmds.attributeQuery("lineWidth", node=curve_shape, exists=True):
                    cmds.setAttr(curve_shape + ".lineWidth", 5)
                cmds.setAttr(curve_shape + ".overrideEnabled", 1)
                cmds.setAttr(curve_shape + ".overrideRGBColors", 1)
                cmds.setAttr(curve_shape + ".overrideColorRGB", 0.0, 0.95, 1.0)
            created_objects.append(curve)

        for index, point in enumerate(points):
            marker, _shape = cmds.polySphere(
                radius=0.15,
                name="{0}_path_marker_{1:02d}".format(task["id"], index),
            )
            cmds.xform(marker, translation=point, worldSpace=True)
            cmds.parent(marker, root_group)
            if index == 0:
                point_material = start_material
            elif index == len(points) - 1:
                point_material = target_material
            else:
                point_material = marker_material
            _assign_maya_material(cmds, marker, point_material)
            created_objects.append(marker)

    return created_objects


if __name__ == "__main__":
    from cloud_resource_module import (
        create_cloud_data,
        generate_resource_drops,
        map_drops_to_cells,
    )
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

    tasks = create_tasks_from_drops(drops, cells)
    assign_paths_to_tasks(tasks, cells)

    bees = create_bees(bee_count=3, start_position=[0.0, 0.8, 0.0])
    for bee in bees:
        select_task_for_bee(bee, tasks, cells)

    first_task_with_path = None
    for task in tasks:
        if task.get("path"):
            first_task_with_path = task
            break

    print("Number of drops:", len(drops))
    print("Number of tasks:", len(tasks))
    print("Task summary:", summarize_tasks(tasks))
    print("First task with path:")
    print(first_task_with_path)
