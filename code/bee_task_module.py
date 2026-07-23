"""Bee task creation, assignment, and Maya animation helpers for Cloud-Hive Meadow."""

import math
import re
from collections import deque

from hive_module import create_voxel_material, get_cell_map, update_all_blocked_states


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
    return (
        cell.get("type") == expected_type
        and _remaining_cell_capacity(cell) > 0.000001
    )


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

    return deposit_resource_to_cell(
        cell,
        drop.get("resource_type"),
        float(drop.get("amount", 0.0)),
    )


def get_available_storage_cells(resource_type, cells):
    """Return storage cells that can still receive a resource.

    Parameters:
        resource_type (str): Resource type, usually "nectar" or "pollen".
        cells (list[dict]): Honeycomb cell dictionaries.

    Returns:
        list[dict]: Non-blocked target cells with unreserved capacity.
    """
    target_type = expected_cell_type_for_resource(resource_type)
    if target_type is None:
        return []

    update_all_blocked_states(cells)
    available_cells = []
    for cell in cells:
        if cell.get("type") != target_type:
            continue
        if _cell_is_excluded_from_storage(cell):
            continue
        if _available_storage_capacity(cell) <= 0.000001:
            continue
        available_cells.append(cell)
    return available_cells


def find_nearest_available_storage_cell(start_cell_id, resource_type, cells, graph=None):
    """Find the nearest reachable storage cell with unreserved capacity.

    Parameters:
        start_cell_id (str): Cell id where BFS starts.
        resource_type (str): Resource type to store.
        cells (list[dict]): Honeycomb cell dictionaries.
        graph (dict | None): Optional neighbor map. The current cell dictionaries
            are used when this is None.

    Returns:
        str | None: Target cell id, or None if no valid storage cell is reachable.
    """
    path = bfs_find_path_to_available_storage(
        start_cell_id,
        resource_type,
        cells,
        graph=graph,
    )
    return path[-1] if path else None


def bfs_find_path_to_available_storage(start_cell_id, resource_type, cells, graph=None):
    """Use BFS to find a path to storage with current free capacity.

    Parameters:
        start_cell_id (str): Cell id where BFS starts.
        resource_type (str): Resource type to store.
        cells (list[dict]): Honeycomb cell dictionaries.
        graph (dict | None): Optional neighbor map.

    Returns:
        list[str]: Shortest path to an available storage cell, or [].
    """
    target_type = expected_cell_type_for_resource(resource_type)
    if target_type is None:
        return []

    update_all_blocked_states(cells)
    cell_map = get_cell_map(cells)
    start_cell = cell_map.get(start_cell_id)
    if start_cell is None:
        return []
    if start_cell.get("is_blocked") and not start_cell.get("blocked_by_capacity"):
        return []

    queue = deque([(start_cell_id, [start_cell_id])])
    visited = {start_cell_id}

    while queue:
        current_cell_id, path = queue.popleft()
        current_cell = cell_map[current_cell_id]
        if (
            current_cell.get("type") == target_type
            and not _cell_is_excluded_from_storage(current_cell)
            and _available_storage_capacity(current_cell) > 0.000001
        ):
            return path

        neighbor_ids = (
            graph.get(current_cell_id, [])
            if graph is not None
            else current_cell.get("neighbors", [])
        )
        for neighbor_id in neighbor_ids:
            if neighbor_id in visited:
                continue
            neighbor_cell = cell_map.get(neighbor_id)
            if neighbor_cell is None or neighbor_cell.get("is_blocked"):
                continue
            visited.add(neighbor_id)
            queue.append((neighbor_id, path + [neighbor_id]))

    return []


def reserve_storage_capacity(cell, amount):
    """Reserve part of a storage cell's remaining capacity for a task.

    Parameters:
        cell (dict): Target storage cell.
        amount (float): Requested reservation amount.

    Returns:
        float: Amount actually reserved.
    """
    if cell is None:
        return 0.0
    requested_amount = max(0.0, float(amount))
    reserved_amount = min(requested_amount, _available_storage_capacity(cell))
    cell["reserved_amount"] = float(cell.get("reserved_amount", 0.0)) + reserved_amount
    return reserved_amount


def release_storage_reservation(cell, amount):
    """Release a previous target-capacity reservation.

    Parameters:
        cell (dict): Target storage cell.
        amount (float): Reservation amount to release.

    Returns:
        float: Amount released.
    """
    if cell is None:
        return 0.0
    requested_amount = max(0.0, float(amount))
    current_reserved = max(0.0, float(cell.get("reserved_amount", 0.0)))
    released_amount = min(requested_amount, current_reserved)
    cell["reserved_amount"] = max(0.0, current_reserved - released_amount)
    return released_amount


def deposit_resource_to_cell(cell, resource_type, amount):
    """Deposit a resource into a cell while respecting actual capacity.

    Parameters:
        cell (dict): Honeycomb cell dictionary.
        resource_type (str): Resource type, usually "nectar" or "pollen".
        amount (float): Requested deposit amount.

    Returns:
        float: Amount actually deposited.
    """
    if cell is None or cell.get("is_blocked") and not cell.get("blocked_by_capacity"):
        return 0.0

    resource_field = _resource_field(resource_type)
    if resource_field is None:
        return 0.0

    requested_amount = max(0.0, float(amount))
    deposited_amount = min(requested_amount, _remaining_cell_capacity(cell))
    cell[resource_field] = float(cell.get(resource_field, 0.0)) + deposited_amount
    update_all_blocked_states([cell])
    return deposited_amount


def consume_stored_resources(cells, amount_per_cycle):
    """Consume a small amount from honey and pollen storage cells.

    Parameters:
        cells (list[dict]): Honeycomb cell dictionaries.
        amount_per_cycle (float | dict): Amount to consume from each storage
            cell. A dictionary may provide separate "nectar" and "pollen" keys.

    Returns:
        dict: Total consumed nectar and pollen.
    """
    if isinstance(amount_per_cycle, dict):
        nectar_amount = max(0.0, float(amount_per_cycle.get("nectar", 0.0)))
        pollen_amount = max(0.0, float(amount_per_cycle.get("pollen", 0.0)))
    else:
        nectar_amount = pollen_amount = max(0.0, float(amount_per_cycle))

    consumed = {"nectar": 0.0, "pollen": 0.0}
    for cell in cells:
        if cell.get("type") == "honey":
            used = min(float(cell.get("nectar", 0.0)), nectar_amount)
            cell["nectar"] = max(0.0, float(cell.get("nectar", 0.0)) - used)
            consumed["nectar"] += used
        elif cell.get("type") == "pollen":
            used = min(float(cell.get("pollen", 0.0)), pollen_amount)
            cell["pollen"] = max(0.0, float(cell.get("pollen", 0.0)) - used)
            consumed["pollen"] += used

        cell["reserved_amount"] = 0.0

    update_all_blocked_states(cells)
    return consumed


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
    is_blocked_source = (
        source_cell.get("type") == "capped"
        or (
            source_cell.get("is_blocked")
            and not source_cell.get("blocked_by_capacity")
        )
    )

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
        "origin": drop.get("origin", "natural_drop"),
        "source_cloud": drop.get("source_cloud"),
        "source_cell": source_cell["id"],
        "target_type": target_type,
        "target_cell": None,
        "resource_type": resource_type,
        "amount": float(drop.get("amount", 0.0)),
        "priority": priority,
        "status": "pending",
        "path": [],
        "reserved_amount": 0.0,
        "source_contains_resource": not is_blocked_source,
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
        drop["origin"] = drop.get("origin", "natural_drop")
        drop["validation_result"] = "unmapped"
        drop["direct_storage_amount"] = 0.0
        drop["task_id"] = None
        mapped_cell_id = drop.get("mapped_cell_id")
        source_cell = cell_map.get(mapped_cell_id)
        if source_cell is None:
            continue

        drop["mapped_cell_type"] = source_cell.get("type")
        resource_field = _resource_field(drop.get("resource_type"))
        landing_before_amount = (
            float(source_cell.get(resource_field, 0.0))
            if resource_field is not None
            else 0.0
        )

        if validate_resource_cell(drop, source_cell):
            drop["validation_result"] = "matched"
            deposited_amount = deposit_resource(drop, source_cell)
            drop["direct_storage_amount"] = deposited_amount
            drop["landing_cell_id"] = source_cell["id"]
            drop["landing_deposited_amount"] = deposited_amount
            drop["landing_before_amount"] = landing_before_amount
            drop["landing_after_amount"] = landing_before_amount + deposited_amount
            drop["landing_is_valid"] = True
            drop["landing_became_full"] = bool(
                source_cell.get("blocked_by_capacity")
            )
            remaining_amount = max(0.0, float(drop.get("amount", 0.0)) - deposited_amount)
            if remaining_amount <= 0.000001:
                continue

            overflow_drop = dict(drop)
            overflow_drop["amount"] = remaining_amount
            task = create_transport_task(overflow_drop, source_cell)
            task["source_contains_resource"] = False
            drop["task_id"] = task["id"]
            tasks.append(task)
            continue

        drop["validation_result"] = (
            "blocked" if source_cell.get("is_blocked") else "mismatched"
        )

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
        drop["landing_became_full"] = bool(
            source_cell.get("blocked_by_capacity")
        )

        task = create_transport_task(drop, source_cell)
        drop["task_id"] = task["id"]
        if not source_cell.get("is_blocked"):
            if deposited_amount > 0.000001:
                task["amount"] = deposited_amount
                task["source_contains_resource"] = True
            else:
                task["amount"] = float(drop.get("amount", 0.0))
                task["source_contains_resource"] = False
        else:
            task["source_contains_resource"] = False
        tasks.append(task)

    update_all_blocked_states(cells)
    return tasks


def create_tasks_from_existing_cell_resources(cells, cycle_number=0):
    """Create carryover transport tasks for resources still in wrong cells.

    Parameters:
        cells (list[dict]): Honeycomb cell dictionaries with persistent resource
            amounts from prior cycles.
        cycle_number (int): Cycle number used to make stable task ids.

    Returns:
        list[dict]: Carryover tasks for misplaced nectar or pollen.
    """
    tasks = []
    for cell in cells:
        if cell.get("type") in ("queen", "queen_reserved"):
            continue

        for resource_type in ("nectar", "pollen"):
            resource_field = _resource_field(resource_type)
            amount = float(cell.get(resource_field, 0.0))
            if amount <= 0.000001:
                continue
            if cell.get("type") == expected_cell_type_for_resource(resource_type):
                continue

            safe_cell_id = _sanitize_maya_name_component(cell["id"].replace("-", "neg"))
            drop = {
                "id": "carryover_cycle_{0}_{1}_{2}".format(
                    int(cycle_number),
                    safe_cell_id,
                    resource_type,
                ),
                "resource_type": resource_type,
                "amount": amount,
                "origin": "carryover",
            }
            task = create_transport_task(drop, cell)
            task["source_contains_resource"] = not (
                cell.get("type") == "capped"
                or (
                    cell.get("is_blocked")
                    and not cell.get("blocked_by_capacity")
                )
            )
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
    for cell in cells:
        cell["reserved_amount"] = 0.0

    ordered_tasks = sorted(
        tasks,
        key=lambda task: (-int(task.get("priority", 0)), task.get("id", "")),
    )
    for task in ordered_tasks:
        # Always recalculate paths from current cell state.  This prevents a
        # later cycle from reusing stale targets after storage cells fill up.
        task["path"] = []
        task["target_cell"] = None
        task["reserved_amount"] = 0.0

        if task.get("source_cell") is None or task.get("resource_type") is None:
            task["status"] = "waiting"
            continue

        path = bfs_find_path_to_available_storage(
            task["source_cell"],
            task["resource_type"],
            cells,
        )
        if not path:
            task["status"] = "waiting"
            continue

        target_cell = get_cell_map(cells).get(path[-1])
        reserved_amount = reserve_storage_capacity(target_cell, task.get("amount", 0.0))
        if reserved_amount <= 0.000001:
            task["status"] = "waiting"
            continue

        task["path"] = path
        task["target_cell"] = target_cell["id"]
        task["reserved_amount"] = reserved_amount
        if task.get("amount", 0.0) > reserved_amount:
            task["amount"] = reserved_amount
        if task.get("status") == "waiting":
            task["status"] = "pending"

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
    target_cell = cell_map.get(task.get("target_cell") or path[-1])
    resource_field = _resource_field(task.get("resource_type"))
    if source_cell is None or target_cell is None or resource_field is None:
        return 0.0

    requested_amount = max(0.0, float(task.get("amount", 0.0)))
    if task.get("source_contains_resource", True):
        available_amount = max(0.0, float(source_cell.get(resource_field, 0.0)))
        movable_amount = min(available_amount, requested_amount)
    else:
        movable_amount = requested_amount

    target_was_full = bool(target_cell.get("blocked_by_capacity"))
    release_storage_reservation(target_cell, task.get("reserved_amount", 0.0))
    deposited_amount = deposit_resource_to_cell(
        target_cell,
        task.get("resource_type"),
        movable_amount,
    )
    if task.get("source_contains_resource", True):
        source_cell[resource_field] = max(
            0.0,
            float(source_cell.get(resource_field, 0.0)) - deposited_amount,
        )

    update_all_blocked_states(cells)
    target_became_full = bool(target_cell.get("blocked_by_capacity"))
    became_capped = target_became_full and not target_was_full

    task["completed_amount"] = deposited_amount
    task["target_cell"] = target_cell["id"]
    task["became_capped"] = became_capped
    task["target_became_full"] = target_became_full
    task["reserved_amount"] = 0.0

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


def _available_storage_capacity(cell):
    """Return remaining capacity after existing task reservations.

    Parameters:
        cell (dict): Honeycomb cell dictionary.

    Returns:
        float: Capacity available for new task reservations.
    """
    reserved_amount = max(0.0, float(cell.get("reserved_amount", 0.0)))
    return max(0.0, _remaining_cell_capacity(cell) - reserved_amount)


def _cell_is_excluded_from_storage(cell):
    """Return True when a cell cannot be used as a storage target."""
    if cell is None:
        return True
    if cell.get("type") in ("capped", "queen", "queen_reserved"):
        return True
    if cell.get("queen_role") in ("center", "reserved"):
        return True
    return bool(cell.get("is_blocked"))


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
    """Plan one continuous task route from a worker's previous endpoint.

    Natural-drop and carryover transport stays on the honeycomb surface: the
    worker moves to the landed source cell and then follows the capacity-aware
    BFS path. Only explicit collection tasks may leave the hive surface to
    visit a cloud before returning to the source cell and following the path.
    Movement duration remains proportional to world-space distance, and the
    worker finishes at the real delivery endpoint instead of a shared origin.
    """
    path = task.get("path") or []
    if not path:
        return None

    drop_id = task.get("id", "")
    if drop_id.startswith("task_"):
        drop_id = drop_id[5:]
    drop = next((item for item in drops if item.get("id") == drop_id), None)
    cell_map = get_cell_map(cells)
    source_cell = cell_map.get(task.get("source_cell"))
    if source_cell is None:
        return None

    source_cloud_id = task.get("source_cloud")
    if source_cloud_id is None and drop is not None:
        source_cloud_id = drop.get("source_cloud")
    cloud = next(
        (item for item in clouds if item.get("id") == source_cloud_id),
        None,
    )

    waypoints = [tuple(float(value) for value in start_position)]
    frames = [int(frame_start)]
    drop_start = None
    drop_end = None
    task_origin = task.get("origin", "natural_drop")
    is_cloud_collection = task_origin in ("collection", "collection_demo")
    surface_height = 0.75
    source_x, source_y, source_z = source_cell["position"]
    source_hover = (source_x, source_y + surface_height, source_z)

    # Reaching the source is an on-hive move for every task. Collection tasks
    # then make a deliberate surface-to-cloud flight and return to this point.
    _append_constant_speed_waypoint(
        waypoints,
        frames,
        source_hover,
        frames_per_unit,
    )

    if is_cloud_collection and cloud is not None:
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
        collection_hold_frames = max(5, int(round(frames_per_unit * 0.40)))
        waypoints.append(cloud_hover)
        frames.append(frames[-1] + collection_hold_frames)
        pickup_waypoint_index = len(waypoints) - 1
        _append_constant_speed_waypoint(
            waypoints,
            frames,
            source_hover,
            frames_per_unit,
        )
    else:
        if drop is not None:
            # Natural falling is a separate visual. The worker waits at the
            # mapped cell only when it arrives before that drop has landed.
            drop_start = int(frame_start)
            drop_end = drop_start + max(1, int(fall_duration))
            if frames[-1] < drop_end:
                waypoints.append(source_hover)
                frames.append(drop_end)
        pickup_hold_frames = max(3, int(round(frames_per_unit * 0.25)))
        waypoints.append(source_hover)
        frames.append(frames[-1] + pickup_hold_frames)
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
        "movement_mode": (
            "cloud_collection" if is_cloud_collection and cloud is not None
            else "on_hive_transport"
        ),
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


def _create_queen_cube(
    cmds,
    parent,
    name,
    dimensions,
    translation,
    material,
    rotation=(0.0, 0.0, 0.0),
):
    """Create one box-shaped component of the pixel-style queen bee."""
    cube, _shape = cmds.polyCube(
        width=dimensions[0],
        height=dimensions[1],
        depth=dimensions[2],
        name=name,
    )
    cmds.parent(cube, parent)
    cmds.setAttr(cube + ".translate", *translation, type="double3")
    cmds.setAttr(cube + ".rotate", *rotation, type="double3")
    _assign_maya_material(cmds, cube, material)
    return cube


def create_queen_geometry(cells, queen_scale=1.45, cell_depth=0.35):
    """Create one large pixel-style queen in the central queen chamber.

    The queen is a static presentation character and is intentionally kept out
    of worker task assignment and flight animation.  Its vertical position is
    derived from the generated hive voxel pitch so it stays seated on the
    amber queen-room floor at different voxel densities.

    Parameters:
        cells (list[dict]): Honeycomb cells containing one queen center cell.
        queen_scale (float): Absolute visual scale for the queen model.
        cell_depth (float): Honeycomb base depth used as a pitch fallback.

    Returns:
        dict | None: Queen metadata, or None when no queen chamber is present.
    """
    import maya.cmds as cmds

    if queen_scale <= 0:
        raise ValueError("queen_scale must be greater than 0")
    if cell_depth <= 0:
        raise ValueError("cell_depth must be greater than 0")

    queen_cell = next(
        (
            cell
            for cell in cells
            if cell.get("queen_role") == "center" or cell.get("type") == "queen"
        ),
        None,
    )
    if queen_cell is None:
        return None

    root_group = "CloudHive_Bees_GRP"
    if not cmds.objExists(root_group):
        cmds.group(empty=True, name=root_group)

    queen_group = "CloudHive_Queen_GRP"
    if cmds.objExists(queen_group):
        cmds.delete(queen_group)
    cmds.group(empty=True, name=queen_group)
    cmds.parent(queen_group, root_group)

    body_material = _create_maya_material(
        cmds,
        "chm_bee_body_gold_MAT",
        (1.0, 0.72, 0.05),
    )
    stripe_material = _create_maya_material(
        cmds,
        "chm_bee_stripe_dark_MAT",
        (0.08, 0.06, 0.04),
    )
    thorax_material = _create_maya_material(
        cmds,
        "chm_queen_thorax_amber_MAT",
        (0.94, 0.48, 0.035),
    )
    wing_material = _create_maya_material(
        cmds,
        "chm_queen_wing_cream_MAT",
        (1.0, 0.91, 0.68),
    )
    crown_material = _create_maya_material(
        cmds,
        "chm_queen_crown_gold_MAT",
        (1.0, 0.84, 0.16),
    )
    highlight_material = _create_maya_material(
        cmds,
        "chm_queen_highlight_MAT",
        (1.0, 0.96, 0.62),
    )

    scale = float(queen_scale)

    def scaled(values):
        return tuple(float(value) * scale for value in values)

    parts = []

    def add_part(
        suffix,
        dimensions,
        translation,
        material,
        rotation=(0.0, 0.0, 0.0),
    ):
        part = _create_queen_cube(
            cmds,
            queen_group,
            "CloudHive_Queen_{0}".format(suffix),
            scaled(dimensions),
            scaled(translation),
            material,
            rotation=rotation,
        )
        parts.append(part)
        return part

    # A long abdomen is the strongest natural silhouette difference from the
    # compact worker model.  The smaller rear block gives it a pixel taper.
    add_part("abdomen", (0.92, 0.36, 0.44), (-0.24, 0.0, 0.0), body_material)
    add_part("abdomen_tip", (0.22, 0.28, 0.34), (-0.80, -0.02, 0.0), body_material)
    add_part("thorax", (0.42, 0.44, 0.46), (0.40, 0.03, 0.0), thorax_material)
    add_part("head", (0.32, 0.34, 0.36), (0.77, 0.02, 0.0), body_material)

    for stripe_index, offset_x in enumerate((-0.49, -0.24, 0.01)):
        add_part(
            "stripe_{0:02d}".format(stripe_index),
            (0.06, 0.375, 0.455),
            (offset_x, 0.0, 0.0),
            stripe_material,
        )

    # A small cream pixel on the back reads as a specular highlight even in a
    # low-resolution render and keeps the long abdomen from looking flat.
    add_part(
        "abdomen_highlight",
        (0.20, 0.045, 0.09),
        (-0.45, 0.20, -0.11),
        highlight_material,
    )

    # Two wing pairs are larger than the worker wings but retain the same box
    # construction.  Their slight fan angles make the top silhouette readable.
    for side_index, side in enumerate((-1.0, 1.0)):
        add_part(
            "wing_front_{0:02d}".format(side_index),
            (0.44, 0.05, 0.34),
            (0.24, 0.30, side * 0.37),
            wing_material,
            rotation=(0.0, side * 12.0, 0.0),
        )
        add_part(
            "wing_rear_{0:02d}".format(side_index),
            (0.34, 0.045, 0.25),
            (-0.18, 0.25, side * 0.33),
            wing_material,
            rotation=(0.0, side * 8.0, 0.0),
        )

    # Eyes, antennae, and three leg pairs provide a more complete silhouette
    # than the task workers while staying within the same hard-edged style.
    for side_index, side in enumerate((-1.0, 1.0)):
        add_part(
            "eye_{0:02d}".format(side_index),
            (0.065, 0.13, 0.075),
            (0.92, 0.04, side * 0.145),
            stripe_material,
        )
        add_part(
            "antenna_{0:02d}".format(side_index),
            (0.27, 0.045, 0.045),
            (1.02, 0.18, side * 0.12),
            stripe_material,
            rotation=(0.0, 0.0, -32.0),
        )

    for leg_index, offset_x in enumerate((-0.28, 0.10, 0.43)):
        for side_index, side in enumerate((-1.0, 1.0)):
            add_part(
                "leg_{0:02d}_{1:02d}".format(leg_index, side_index),
                (0.065, 0.065, 0.26),
                (offset_x, -0.18, side * 0.29),
                stripe_material,
                rotation=(side * 14.0, 0.0, 0.0),
            )

    # A simple three-prong pixel crown is deliberately stylized so the queen
    # can be identified immediately when the full hive is framed in camera.
    add_part("crown_base", (0.31, 0.07, 0.30), (0.72, 0.25, 0.0), crown_material)
    crown_heights = (0.15, 0.22, 0.15)
    for crown_index, (offset_z, height) in enumerate(
        zip((-0.11, 0.0, 0.11), crown_heights)
    ):
        add_part(
            "crown_tip_{0:02d}".format(crown_index),
            (0.075, height, 0.075),
            (0.72, 0.285 + height * 0.5, offset_z),
            crown_material,
        )

    pitch = float(queen_cell.get("voxel_pitch") or max(cell_depth / 5.0, 0.05))
    base_layers = max(3, int(round(float(cell_depth) / pitch)))
    chamber_floor_y = (base_layers + 1) * pitch
    queen_center_y = chamber_floor_y + 0.22 * scale + pitch * 0.04
    center_x, _center_y, center_z = queen_cell["position"]
    queen_position = (center_x, queen_center_y, center_z)
    cmds.xform(
        queen_group,
        translation=queen_position,
        rotation=(0.0, -28.0, 0.0),
        worldSpace=True,
    )

    return {
        "id": "queen_00",
        "position": list(queen_position),
        "chamber_cell": queen_cell["id"],
        "scale": scale,
        "maya_object": queen_group,
        "parts": parts,
    }


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
    """Animate one task continuously from the bee's prior endpoint.

    Natural and carryover transport follows the task's capacity-aware BFS path
    on the honeycomb. Explicit collection tasks alone may include the planned
    hive-to-cloud flight segment. Moving segments use distance-based frames and
    linear Maya tangents.
    """
    import maya.cmds as cmds

    bee_object = bee.get("maya_object")
    path = task.get("path", []) if task else []
    if not bee_object or not cmds.objExists(bee_object) or not path:
        if task is not None and path:
            fallback_frame = task.get("planned_delivery_frame")
            if fallback_frame is not None:
                task["delivery_frame"] = int(fallback_frame)
            task["visual_animation_status"] = "skipped"
        return []

    def animate_path_only_task():
        """Animate an on-hive task and record its actual delivery frame."""
        frames = animate_bee_on_path(bee, task, cells, frame_start, frame_step)
        task["payload_object"] = None
        if not frames:
            fallback_frame = task.get("planned_delivery_frame")
            if fallback_frame is None:
                fallback_frame = frame_start + max(0, len(path) - 1) * frame_step
            task["delivery_frame"] = int(fallback_frame)
            task["visual_animation_status"] = "skipped"
            cmds.warning(
                "Cloud-Hive Bloomfield: task '{0}' could not create path "
                "animation keyframes; using delivery frame {1}.".format(
                    task.get("id", "<unknown>"),
                    task["delivery_frame"],
                )
            )
            return frames

        task["delivery_frame"] = int(frames[-1])
        task["pickup_frame"] = int(frames[0])
        task["visual_animation_status"] = "path_only"
        bee["animation_frames"] = frames
        bee["resource_type"] = task.get("resource_type")
        bee["animation_current_position"] = list(bee.get("position", []))
        return frames

    drop_id = task.get("id", "")
    if drop_id.startswith("task_"):
        drop_id = drop_id[5:]
    drop = next((item for item in drops if item.get("id") == drop_id), None)
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
        return animate_path_only_task()

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

    resource_type = task.get("resource_type") or (
        drop.get("resource_type") if drop is not None else "nectar"
    )
    pickup_frame = int(frames[pickup_waypoint_index])
    delivery_frame = int(frames[delivery_waypoint_index])
    bee["animation_frames"] = frames
    bee["animation_current_position"] = list(plan["end_position"])
    bee["position"] = list(plan["end_position"])
    bee["resource_type"] = resource_type
    task["delivery_frame"] = delivery_frame
    task["pickup_frame"] = pickup_frame
    task["payload_object"] = None
    task["visual_animation_status"] = plan.get("movement_mode", "planned")

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
    surface_height = 0.62

    for index, cell_id in enumerate(task.get("path", [])):
        cell = cell_map.get(cell_id)
        if cell is None:
            continue

        frame = frame_start + (index * frame_step)
        x, y, z = cell["position"]
        cmds.currentTime(frame)
        cmds.xform(bee_object, translation=(x, y + surface_height, z), worldSpace=True)
        cmds.setKeyframe(bee_object, attribute="translate", time=frame)
        frames.append(frame)
        bee["position"] = [x, y + surface_height, z]

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

    marker_material = _create_maya_material(cmds, "chm_task_marker_white_MAT", (0.92, 0.96, 1.0))
    start_material = _create_maya_material(cmds, "chm_task_start_red_MAT", (1.0, 0.08, 0.04))
    target_material = _create_maya_material(cmds, "chm_task_target_green_MAT", (0.08, 1.0, 0.28))

    for task in tasks:
        safe_task_id = _sanitize_maya_name_component(task.get("id", "task"))
        task_path_objects = []
        task["path_visual_objects"] = task_path_objects
        task["path_curve_object"] = None
        task["path_marker_objects"] = []
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
                name="{0}_path_CRV".format(safe_task_id),
            )
            cmds.parent(curve, root_group)
            curve_shapes = cmds.listRelatives(curve, shapes=True) or []
            for curve_shape in curve_shapes:
                if cmds.attributeQuery("lineWidth", node=curve_shape, exists=True):
                    cmds.setAttr(curve_shape + ".lineWidth", 5)
                cmds.setAttr(curve_shape + ".overrideEnabled", 1)
                cmds.setAttr(curve_shape + ".overrideRGBColors", 1)
                cmds.setAttr(curve_shape + ".overrideColorRGB", 0.0, 0.95, 1.0)
            created_objects.append(curve)
            task_path_objects.append(curve)
            task["path_curve_object"] = curve

        for index, point in enumerate(points):
            marker, _shape = cmds.polySphere(
                radius=0.15,
                name="{0}_path_marker_{1:02d}".format(safe_task_id, index),
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
            task_path_objects.append(marker)
            task["path_marker_objects"].append(marker)

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
