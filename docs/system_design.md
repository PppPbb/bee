# System Design

## Overall Architecture

Cloud-Hive Meadow is organized as a modular Maya Python project with a strict separation between pure Python simulation logic and Maya-specific scene construction.

The pure Python layer owns data, rules, graph traversal, resource validation, and task decisions. These parts should run in a normal Python interpreter without Autodesk Maya.

The Maya layer owns geometry, materials, UI, animation curves, cameras, lights, and visual debugging. These functions may import `maya.cmds` and must be tested inside Autodesk Maya.

## Core Loop

1. Cloud flowers generate nectar and pollen.
2. Resource drops fall toward the honeycomb terrain.
3. Each drop is mapped to the nearest honeycomb cell.
4. The system checks whether the drop landed in the correct cell type.
5. Incorrect landings create transport or cleaning tasks.
6. Bees use BFS on the hexagonal honeycomb graph to move resources to the nearest correct storage cell.
7. The final scene visualizes generated resources, wrong drops, BFS paths, bee movement, and cell state changes.

## Main Subsystems

### Honeycomb System

Responsibilities:

- Generate a hexagonal honeycomb grid.
- Store cell coordinates, world positions, neighbors, and cell types.
- Assign storage types such as nectar and pollen.
- Find the nearest cell for a falling resource.
- Provide graph data for BFS pathfinding.
- Provide Maya-only functions for terrain geometry and material assignment.

Planned module: `code/hive_module.py`

Current pure Python interface:

- `axial_to_world(q, r, cell_size)`: converts axial coordinates to a flat XZ-plane world position.
- `generate_hex_grid(size, cell_size)`: creates cell dictionaries for a circular axial hex grid.
- `calculate_neighbors(cells)`: fills graph edges using the six axial neighbor directions.
- `assign_cell_types(cells, ...)`: assigns honey, pollen, empty, and capped states reproducibly.
- `find_nearest_storage_cell(cells, start_cell_id, target_type)`: returns the closest reachable matching storage cell.
- `bfs_find_path(cells, start_cell_id, target_type)`: returns the shortest non-blocked path to a matching target type.

Current Maya-only interface:

- `create_honeycomb_geometry(cells, cell_size, cell_depth)`: creates six-sided prism cell geometry and type materials in Maya.
- `highlight_path(path, cells)`: creates a simple Maya path visualization for BFS output.

### Cloud Resource System

Responsibilities:

- Define cloud flower resource generation rules.
- Create nectar and pollen drop events.
- Store resource identity, origin, intended landing position, and mapped cell.
- Support deterministic test data for non-Maya testing.
- Provide Maya-only functions for clouds, flowers, falling drops, and resource markers.

Planned module: `code/cloud_resource_module.py`

### Bee Task And Animation System

Responsibilities:

- Check whether a resource matches the cell it landed on.
- Create transport or cleaning tasks when resources are misplaced.
- Find the nearest valid destination cell with BFS.
- Return path data for visualization and testing.
- Provide Maya-only functions for bee animation, path curves, and visible resource movement.

Planned module: `code/bee_task_module.py`

## Data Interfaces

The MVP should use simple Python data structures first, then move to dataclasses if needed.

Suggested records:

- `Cell`: cell id, hex coordinate, world position, cell type, current resource state, neighbor ids.
- `ResourceDrop`: resource id, resource type, source position, landing position, mapped cell id.
- `Task`: task id, task type, source cell id, target cell id, resource id, BFS path.
- `Bee`: bee id, current cell id, assigned task id, movement path.

Suggested module interfaces:

- `hive_module` returns cell dictionaries, neighbor maps, and nearest-cell results.
- `cloud_resource_module` returns resource drop records.
- `bee_task_module` consumes cells and drops, then returns tasks and paths.
- `visual_module` consumes cells, drops, tasks, and paths to build Maya visuals.
- `ui_module` calls `main.py` entry points with user-selected parameters.

## MVP Scope

- Generate a small honeycomb terrain.
- Assign visible cell types.
- Generate nectar and pollen drops from cloud flowers.
- Map drops to honeycomb cells.
- Detect correct and incorrect resource placement.
- Create tasks for incorrect placement.
- Use BFS to find a valid destination cell.
- Show bee movement and resource transport.
- Provide a simple Maya UI to regenerate or demonstrate the scene.
- Produce screenshots, short video output, presentation slides, and a written report.

## Non-Goals

- Physically accurate fluid, bee, or pollen simulation.
- Complex production asset pipeline.
- Full gameplay balancing.
- Real-time interactive strategy gameplay.
- Advanced AI planning beyond BFS for the MVP.
- External database or network integration.
