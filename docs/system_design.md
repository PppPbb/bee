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

Current pure Python interface:

- `create_cloud_data(...)`: creates deterministic cloud dictionaries with resource amounts and emission points.
- `apply_wind_offset(position, wind_strength, wind_direction_degrees)`: shifts positions horizontally on the XZ plane.
- `generate_resource_drops(...)`: creates nectar and pollen drop records with wind-influenced landing positions.
- `distance_2d(pos_a, pos_b)`: measures XZ-plane distance.
- `find_nearest_cell_for_drop(drop, cells)`: maps one drop to the closest honeycomb cell.
- `map_drops_to_cells(drops, cells)`: maps every drop to the honeycomb grid.
- `summarize_drop_mapping(drops)`: reports total, nectar, pollen, and mapped drop counts.

Current Maya-only interface:

- `create_cloud_geometry(clouds, cloud_scale)`: creates stylized sphere-cluster cloud objects.
- `create_flower_geometry_on_clouds(clouds, flowers_per_cloud)`: creates simple flowers on top of clouds.
- `create_drop_particles(drops)`: creates nectar and pollen drop markers in Maya.

### Bee Task And Animation System

Responsibilities:

- Check whether a resource matches the cell it landed on.
- Create transport or cleaning tasks when resources are misplaced.
- Find the nearest valid destination cell with BFS.
- Return path data for visualization and testing.
- Provide Maya-only functions for bee animation, path curves, and visible resource movement.

Planned module: `code/bee_task_module.py`

Current pure Python interface:

- `expected_cell_type_for_resource(resource_type)`: maps nectar to honey storage and pollen to pollen storage.
- `validate_resource_cell(drop, cell)`: checks whether a mapped drop landed in a valid non-blocked storage cell.
- `deposit_resource(drop, cell)`: adds nectar or pollen to a cell while respecting capacity.
- `create_transport_task(drop, source_cell)`: creates transport or blocked-cleanup task dictionaries.
- `create_tasks_from_drops(drops, cells)`: consumes mapped drops from `cloud_resource_module`, deposits valid drops, and creates tasks for invalid drops.
- `create_bees(bee_count, start_position)`: creates bee dictionaries for assignment.
- `select_task_for_bee(bee, tasks, cells)`: assigns the highest-priority pending task, using XZ distance as a tie-breaker.
- `assign_paths_to_tasks(tasks, cells)`: calls `hive_module.bfs_find_path()` to attach shortest paths to tasks.
- `complete_task(task, cells)`: moves stored resources from source cells to BFS target cells and marks completed tasks.
- `summarize_tasks(tasks)`: reports task counts by status and task type.

Current Maya-only interface:

- `create_bee_geometry(bees, bee_scale)`: creates simple stylized bee objects in Maya.
- `animate_bee_on_path(bee, task, cells, frame_start, frame_step)`: keyframes bee movement along a task path.
- `create_task_path_visuals(tasks, cells)`: creates simple curve and marker path visuals for task paths.

Integration notes:

- `bee_task_module` expects drops to already have `mapped_cell_id` values from `cloud_resource_module.map_drops_to_cells()`.
- `bee_task_module` uses honeycomb cells and BFS paths from `hive_module`.
- Capped cells are treated as blocked; they create high-priority cleanup tasks and are not used as storage or BFS path cells.

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
