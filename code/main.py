"""Pure Python end-to-end integration script for Cloud-Hive Meadow."""

from bee_task_module import (
    assign_paths_to_tasks,
    complete_task,
    create_bees,
    create_tasks_from_drops,
    create_tasks_from_existing_cell_resources,
    consume_stored_resources,
    select_task_for_bee,
    summarize_tasks,
)
from cloud_resource_module import (
    create_cloud_data,
    generate_resource_drops,
    map_drops_to_cells,
    summarize_drop_mapping,
)
from hive_module import (
    calculate_neighbors,
    assign_cell_types,
    generate_hex_grid,
    storage_cell_is_full,
    update_all_blocked_states,
)

try:
    from config import DEFAULT_INTEGRATION_PARAMETERS
except ImportError:
    DEFAULT_INTEGRATION_PARAMETERS = None


FALLBACK_PARAMETERS = {
    "hive": {
        "size": 3,
        "cell_size": 1.0,
        "honey_ratio": 0.3,
        "pollen_ratio": 0.3,
        "empty_ratio": 0.3,
        "capped_ratio": 0.1,
        "seed": 42,
    },
    "clouds": {
        "cloud_count": 3,
        "scene_radius": 5.0,
        "min_height": 4.0,
        "max_height": 6.0,
        "nectar_amount": 0.8,
        "pollen_amount": 0.6,
        "seed": 10,
    },
    "drops": {
        "nectar_drop_rate": 3,
        "pollen_drop_rate": 3,
        "wind_strength": 1.0,
        "wind_direction_degrees": 45.0,
        "spread_radius": 1.2,
        "seed": 20,
    },
    "bees": {
        "bee_count": 3,
        "start_position": [0.0, 0.8, 0.0],
    },
    "tasks": {
        "max_tasks_to_complete": 999,
    },
    "resources": {
        "consumption_per_cycle": 0.05,
    },
    "simulation": {
        "cycle": 0,
    },
}


def load_parameters():
    """Load integration parameters from config.py when available.

    Returns:
        dict: Nested parameter dictionary for hive, clouds, drops, bees, and tasks.
    """
    if DEFAULT_INTEGRATION_PARAMETERS is not None:
        return DEFAULT_INTEGRATION_PARAMETERS
    return FALLBACK_PARAMETERS


def count_cell_types(cells):
    """Count honeycomb cells by type.

    Parameters:
        cells (list[dict]): Honeycomb cell dictionaries.

    Returns:
        dict: Mapping from cell type to count.
    """
    counts = {}
    for cell in cells:
        cell_type = cell.get("type", "unknown")
        counts[cell_type] = counts.get(cell_type, 0) + 1
    return counts


def complete_reachable_tasks(tasks, cells, max_tasks_to_complete):
    """Complete a limited number of tasks that already have BFS paths.

    Parameters:
        tasks (list[dict]): Task dictionaries with assigned paths.
        cells (list[dict]): Honeycomb cell dictionaries.
        max_tasks_to_complete (int): Maximum number of path tasks to complete.

    Returns:
        list[dict]: Task dictionaries that were completed.
    """
    completed_tasks = []

    # Capped/blocked cleanup tasks usually have no BFS path, so this integration
    # demo completes transport tasks with reachable storage targets first.
    for task in tasks:
        if len(completed_tasks) >= max_tasks_to_complete:
            break
        if not task.get("path"):
            continue
        if task.get("status") == "done":
            continue

        target_cell_id = task.get("path", [None])[-1]
        target_cell = next((cell for cell in cells if cell["id"] == target_cell_id), None)
        resource_field = task.get("resource_type")
        before_amount = (
            float(target_cell.get(resource_field, 0.0))
            if target_cell is not None and resource_field in ("nectar", "pollen")
            else 0.0
        )

        moved_amount = complete_task(task, cells)
        if moved_amount > 0.0:
            task["resource_event"] = {
                "task_id": task["id"],
                "source_cell": task.get("source_cell"),
                "target_cell": task.get("target_cell"),
                "resource_type": task.get("resource_type"),
                "amount": moved_amount,
                "before_amount": before_amount,
                "after_amount": before_amount + moved_amount,
                "became_capped": bool(task.get("became_capped")),
            }
            completed_tasks.append(task)

    return completed_tasks


def _apply_prior_cell_state(cells, prior_cell_state):
    """Restore persistent resource and capped state for a new simulation step."""
    if not prior_cell_state:
        return
    state_by_id = {item["id"]: item for item in prior_cell_state}
    for cell in cells:
        state = state_by_id.get(cell["id"])
        if state is None:
            continue
        for field in (
            "type",
            "nectar",
            "pollen",
            "capacity",
            "reserved_amount",
            "is_blocked",
            "blocked_by_capacity",
            "queen_role",
        ):
            if field in state:
                cell[field] = state[field]
    update_all_blocked_states(cells)


def _assign_task_queues(bees, completed_tasks):
    """Distribute all successful transport tasks across worker queues."""
    for bee in bees:
        bee["task_queue"] = []
        bee["current_task"] = None
    if not bees:
        return

    for index, task in enumerate(completed_tasks):
        bee = bees[index % len(bees)]
        bee["task_queue"].append(task["id"])
        task["status"] = "queued"

    for bee in bees:
        if bee["task_queue"]:
            bee["current_task"] = bee["task_queue"][0]


def run_simulation(parameters=None, prior_cell_state=None):
    """Run the pure Python Cloud-Hive Meadow resource-management loop.

    Parameters:
        parameters (dict | None): Optional nested parameter dictionary. When None,
            defaults are loaded from config.py if possible.

    Returns:
        dict: Simulation data and summary values.
    """
    parameters = parameters or load_parameters()
    hive_params = parameters["hive"]
    cloud_params = parameters["clouds"]
    drop_params = parameters["drops"]
    bee_params = parameters["bees"]
    task_params = parameters["tasks"]
    resource_params = parameters.get("resources", {})
    simulation_params = parameters.get("simulation", {})
    cycle_number = int(simulation_params.get("cycle", 0))

    cells = generate_hex_grid(
        size=hive_params["size"],
        cell_size=hive_params["cell_size"],
    )
    calculate_neighbors(cells)
    assign_cell_types(
        cells,
        honey_ratio=hive_params["honey_ratio"],
        pollen_ratio=hive_params["pollen_ratio"],
        empty_ratio=hive_params["empty_ratio"],
        capped_ratio=hive_params["capped_ratio"],
        seed=hive_params["seed"],
    )
    _apply_prior_cell_state(cells, prior_cell_state)
    consumed_resources = consume_stored_resources(
        cells,
        resource_params.get("consumption_per_cycle", 0.0),
    )

    clouds = create_cloud_data(**cloud_params)
    effective_drop_params = dict(drop_params)
    effective_drop_params["seed"] = int(drop_params.get("seed", 0)) + cycle_number * 97
    drops = generate_resource_drops(clouds, **effective_drop_params)
    map_drops_to_cells(drops, cells)

    tasks = create_tasks_from_existing_cell_resources(cells, cycle_number=cycle_number)
    tasks.extend(create_tasks_from_drops(drops, cells))
    assign_paths_to_tasks(tasks, cells)

    for cell in cells:
        cell["initial_type"] = cell.get("type")
        cell["initial_nectar"] = float(cell.get("nectar", 0.0))
        cell["initial_pollen"] = float(cell.get("pollen", 0.0))

    bees = create_bees(
        bee_count=bee_params["bee_count"],
        start_position=bee_params["start_position"],
    )
    completed_tasks = complete_reachable_tasks(
        tasks,
        cells,
        max_tasks_to_complete=task_params["max_tasks_to_complete"],
    )
    _assign_task_queues(bees, completed_tasks)

    tasks_with_paths = [task for task in tasks if task.get("path")]
    example_task = tasks_with_paths[0] if tasks_with_paths else None
    drop_summary = summarize_drop_mapping(drops)
    blocked_tasks = [task for task in tasks if not task.get("path")]
    full_storage_cells = [
        cell for cell in cells
        if cell.get("type") in ("honey", "pollen") and storage_cell_is_full(cell)
    ]
    stored_nectar_total = sum(float(cell.get("nectar", 0.0)) for cell in cells)
    stored_pollen_total = sum(float(cell.get("pollen", 0.0)) for cell in cells)
    resource_events = [
        task["resource_event"]
        for task in completed_tasks
        if task.get("resource_event")
    ]

    return {
        "cells": cells,
        "clouds": clouds,
        "drops": drops,
        "tasks": tasks,
        "bees": bees,
        "completed_tasks": completed_tasks,
        "resource_events": resource_events,
        "summary": {
            "cycle_number": cycle_number,
            "cell_count": len(cells),
            "cell_type_counts": count_cell_types(cells),
            "cloud_count": len(clouds),
            "drop_count": len(drops),
            "new_drop_count": len(drops),
            "mapped_drop_count": drop_summary["mapped"],
            "task_count": len(tasks),
            "tasks_created": len(tasks),
            "task_summary": summarize_tasks(tasks),
            "tasks_with_paths": len(tasks_with_paths),
            "blocked_task_count": len(blocked_tasks),
            "queued_task_count": len(completed_tasks),
            "assigned_task_count": len(completed_tasks),
            "completed_task_count": len(completed_tasks),
            "full_storage_cell_count": len(full_storage_cells),
            "stored_nectar_total": stored_nectar_total,
            "stored_pollen_total": stored_pollen_total,
            "consumed_resources": consumed_resources,
            "example_task_path": example_task.get("path") if example_task else [],
        },
    }


def print_summary(simulation_result):
    """Print a readable summary of an integration run.

    Parameters:
        simulation_result (dict): Result dictionary returned by run_simulation().

    Returns:
        None.
    """
    summary = simulation_result["summary"]

    print("Cloud-Hive Bloomfield Integration Summary")
    print("------------------------------------")
    print("Cycle:", summary.get("cycle_number", 0))
    print("Cells:", summary["cell_count"])
    print("Cell type counts:", summary["cell_type_counts"])
    print("Clouds:", summary["cloud_count"])
    print("New drops:", summary.get("new_drop_count", summary["drop_count"]))
    print("Mapped drops:", summary["mapped_drop_count"])
    print("Tasks created:", summary.get("tasks_created", summary["task_count"]))
    print("Task summary:", summary["task_summary"])
    print("Tasks assigned:", summary.get("assigned_task_count", 0))
    print("Tasks with BFS paths:", summary["tasks_with_paths"])
    print("Example task path:", summary["example_task_path"])

    completed_tasks = simulation_result["completed_tasks"]
    print("Completed tasks:", len(completed_tasks))
    print("Full storage cells:", summary.get("full_storage_cell_count", 0))
    print("Stored nectar total:", round(summary.get("stored_nectar_total", 0.0), 3))
    print("Stored pollen total:", round(summary.get("stored_pollen_total", 0.0), 3))
    print("Consumed resources:", summary.get("consumed_resources", {}))
    if completed_tasks:
        print("First completed task:", completed_tasks[0])


if __name__ == "__main__":
    result = run_simulation()
    print_summary(result)
