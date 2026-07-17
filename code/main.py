"""Pure Python end-to-end integration script for Cloud-Hive Meadow."""

from bee_task_module import (
    assign_paths_to_tasks,
    complete_task,
    create_bees,
    create_tasks_from_drops,
    select_task_for_bee,
    summarize_tasks,
)
from cloud_resource_module import (
    create_cloud_data,
    generate_resource_drops,
    map_drops_to_cells,
    summarize_drop_mapping,
)
from hive_module import calculate_neighbors, assign_cell_types, generate_hex_grid

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
        "max_tasks_to_complete": 3,
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

        moved_amount = complete_task(task, cells)
        if moved_amount > 0.0 and task.get("status") == "done":
            completed_tasks.append(task)

    return completed_tasks


def run_simulation(parameters=None):
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

    clouds = create_cloud_data(**cloud_params)
    drops = generate_resource_drops(clouds, **drop_params)
    map_drops_to_cells(drops, cells)

    tasks = create_tasks_from_drops(drops, cells)
    assign_paths_to_tasks(tasks, cells)

    bees = create_bees(
        bee_count=bee_params["bee_count"],
        start_position=bee_params["start_position"],
    )
    for bee in bees:
        select_task_for_bee(bee, tasks, cells)

    completed_tasks = complete_reachable_tasks(
        tasks,
        cells,
        max_tasks_to_complete=task_params["max_tasks_to_complete"],
    )

    tasks_with_paths = [task for task in tasks if task.get("path")]
    example_task = tasks_with_paths[0] if tasks_with_paths else None
    drop_summary = summarize_drop_mapping(drops)

    return {
        "cells": cells,
        "clouds": clouds,
        "drops": drops,
        "tasks": tasks,
        "bees": bees,
        "completed_tasks": completed_tasks,
        "summary": {
            "cell_count": len(cells),
            "cell_type_counts": count_cell_types(cells),
            "cloud_count": len(clouds),
            "drop_count": len(drops),
            "mapped_drop_count": drop_summary["mapped"],
            "task_count": len(tasks),
            "task_summary": summarize_tasks(tasks),
            "tasks_with_paths": len(tasks_with_paths),
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

    print("Cloud-Hive Meadow Integration Summary")
    print("------------------------------------")
    print("Cells:", summary["cell_count"])
    print("Cell type counts:", summary["cell_type_counts"])
    print("Clouds:", summary["cloud_count"])
    print("Drops:", summary["drop_count"])
    print("Mapped drops:", summary["mapped_drop_count"])
    print("Tasks:", summary["task_count"])
    print("Task summary:", summary["task_summary"])
    print("Tasks with BFS paths:", summary["tasks_with_paths"])
    print("Example task path:", summary["example_task_path"])

    completed_tasks = simulation_result["completed_tasks"]
    print("Completed tasks:", len(completed_tasks))
    if completed_tasks:
        print("First completed task:", completed_tasks[0])


if __name__ == "__main__":
    result = run_simulation()
    print_summary(result)
