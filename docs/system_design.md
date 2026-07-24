# System Design

## Overall Architecture

Cloud-Hive Bloomfield is organized as a modular Maya Python project with a strict separation between pure Python simulation logic and Maya-specific scene construction.

Final English title: **Cloud-Hive Bloomfield: A Procedural Honeycomb Resource System in Maya**

Final Chinese title: **云上蜜源驱动的程序化蜂巢花田系统**

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
- Store cell coordinates, world positions, neighbors, cell types, and current resource state.
- Assign storage types such as honey and pollen, while also reserving a special queen chamber footprint.
- Model both static blocked cells (`capped`) and dynamic capacity-based blocked states.
- Find the nearest cell for a falling resource.
- Provide graph data for BFS pathfinding.
- Provide Maya-only functions for terrain geometry and material assignment.

Planned module: `code/hive_module.py`

Current pure Python interface:

- `axial_to_world(q, r, cell_size)`: converts axial coordinates to a flat XZ-plane world position.
- `generate_hex_grid(size, cell_size)`: creates cell dictionaries for a circular axial hex grid.
- `calculate_neighbors(cells)`: fills graph edges using the six axial neighbor directions.
- `assign_cell_types(cells, ...)`: assigns honey, pollen, empty, capped, and reserved queen-chamber-related states reproducibly.
- `assign_queen_chamber(cells, enabled=True)`: reserves the center seven cells as a blocked queen chamber footprint.
- `update_cell_blocked_state(cell)`: refreshes whether a cell is blocked because of capacity or manual block flags.
- `update_all_blocked_states(cells)`: recalculates blocked status for every cell before BFS.
- `find_nearest_storage_cell(cells, start_cell_id, target_type)`: returns the closest reachable matching storage cell.
- `bfs_find_path(cells, start_cell_id, target_type)`: returns the shortest non-blocked path to a matching target type.
- `visible_cell_count(cells)`: counts visible grid cells excluding hidden queen-reserved footprint cells.

Implementation notes:

- The current pure Python system uses additional internal cell fields such as `queen_role`, `blocked_by_capacity`, `capacity`, `nectar`, and `pollen` to represent runtime state.
- `queen` and `queen_reserved` cells are special hidden structural cells rather than normal storage cells.
- Capped cells remain blocked permanently, while honey/pollen cells may become blocked dynamically when their capacity is reached.

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

- `calculate_hive_view_span(cells, cell_size)`: estimates the honeycomb's presentation-camera width for cloud composition.
- `create_cloud_data(...)`: creates deterministic cloud dictionaries with hive-balanced random sizes, packed horizontal slots and depth rows, resource amounts, and emission points.
- `apply_wind_offset(position, wind_strength, wind_direction_degrees)`: shifts positions horizontally on the XZ plane.
- `generate_resource_drops(...)`: creates nectar and pollen drop records with wind-influenced landing positions.
- `distance_2d(pos_a, pos_b)`: measures XZ-plane distance.
- `find_nearest_cell_for_drop(drop, cells)`: maps one drop to the closest honeycomb cell.
- `map_drops_to_cells(drops, cells)`: maps every drop to the honeycomb grid.
- `summarize_drop_mapping(drops)`: reports total, nectar, pollen, and mapped drop counts.

Current Maya-only interface:

- `generate_cloud_voxel_data(cloud, cloud_scale, voxel_pitch)`: builds a full three-dimensional cloud from independent ellipsoid puffs using one of four distinct silhouettes, then adds deterministic rim erosion, stepped surface chips, connected-component cleanup, and warm multi-color voxel patches. Cloud blocks use a coarser grid than the hive while flower blocks retain the hive pitch.
- `create_cloud_geometry(clouds, cloud_scale, voxel_pitch)`: creates independently scaled five-tone merged voxel clouds on a shared grid roughly 1.85 times coarser than the hive for clearer silhouettes and lower mesh cost.
- `generate_cloud_flower_voxel_data(cloud, flowers_per_cloud)`: creates deterministic pink, daisy, yellow-cluster, lavender, blue, and orange flower voxel layouts.
- `create_flower_geometry_on_clouds(clouds, flowers_per_cloud)`: creates six reference-inspired, multi-tone merged-voxel flower types on top of clouds.
- `create_drop_particles(drops)`: creates nectar and pollen drop markers in Maya.

### Bee Task And Animation System

Responsibilities:

- Check whether a resource matches the cell it landed on.
- Create transport or cleanup tasks when resources are misplaced.
- Temporarily store mis-landed resources in the source cell when the source cell is not blocked.
- Find the nearest valid destination cell with BFS.
- Return path data for visualization and testing.
- Provide Maya-only functions for bee animation, path curves, and visible resource movement.

Planned module: `code/bee_task_module.py`

Current pure Python interface:

- `expected_cell_type_for_resource(resource_type)`: maps nectar to honey storage and pollen to pollen storage.
- `validate_resource_cell(drop, cell)`: checks whether a mapped drop landed in a valid non-blocked storage cell.
- `deposit_resource(drop, cell)`: adds nectar or pollen to a cell while respecting capacity.
- `create_transport_task(drop, source_cell)`: creates transport or blocked-cleanup task dictionaries.
- `create_tasks_from_drops(drops, cells)`: consumes mapped drops from `cloud_resource_module`, deposits valid drops, and creates tasks for invalid drops. Wrong non-blocked source cells temporarily hold the resource before a bee moves it onward.
- `create_bees(bee_count, start_position)`: creates bee dictionaries for assignment.
- `select_task_for_bee(bee, tasks, cells)`: assigns the highest-priority pending task, using XZ distance as a tie-breaker.
- `assign_paths_to_tasks(tasks, cells)`: calls `hive_module.bfs_find_path()` to attach shortest paths to tasks.
- `complete_task(task, cells)`: moves stored resources from source cells to BFS target cells, updates storage capacity, and marks completed tasks.
- `summarize_tasks(tasks)`: reports task counts by status and task type.

Implementation notes:

- Valid resource drops are deposited directly into the mapped storage cell.
- Invalid drops on non-blocked cells are still deposited into that source cell first, then converted into a transport task.
- Invalid drops on blocked cells create `clean_blocked` tasks and do not use the blocked cell as a valid transport/storage node.
- When a target storage cell reaches capacity during `complete_task()`, it can be converted into a `capped` cell, which then becomes blocked in subsequent BFS iterations.

Current Maya-only interface:

- `create_bee_geometry(bees, bee_scale)`: creates simple stylized bee objects in Maya.
- `calculate_bee_frames_per_unit(tasks, cells, frame_step)`: converts frames-per-cell into one constant world-space flight speed.
- `plan_bee_collection_cycle(...)`: chains each worker from its real previous endpoint through the cloud, landed resource, and BFS target without returning to a shared idle point.
- `animate_bee_collection_cycle(...)`: applies the planned route with linear translation tangents, preserving constant speed between waypoints and intentional stationary waits.
- `animate_bee_on_path(bee, task, cells, frame_start, frame_step)`: keyframes bee movement along a task path.
- `create_task_path_visuals(tasks, cells)`: creates simple curve and marker path visuals for task paths.

Integration notes:

- `bee_task_module` expects drops to already have `mapped_cell_id` values from `cloud_resource_module.map_drops_to_cells()`.
- `bee_task_module` uses honeycomb cells and BFS paths from `hive_module`.
- Capped cells are treated as blocked; they create high-priority cleanup tasks and are not used as storage or BFS path cells.

### Main Integration Script

Responsibilities:

- Run the pure Python MVP loop outside Autodesk Maya.
- Load default integration parameters from `code/config.py`.
- Generate honeycomb cells, cloud resources, resource drops, mapped drops, tasks, BFS paths, and bees.
- Assign tasks to bees and complete a small number of reachable transport tasks in pure Python.
- Print a readable summary for course debugging and milestone demos.

Planned module: `code/main.py`

Current pure Python interface:

- `load_parameters()`: loads default integration parameters from `code/config.py` when available.
- `count_cell_types(cells)`: summarizes generated honeycomb cell types.
- `complete_reachable_tasks(tasks, cells, max_tasks_to_complete)`: completes path-bearing transport tasks.
- `run_simulation(parameters)`: executes the full non-Maya core loop and returns simulation data.
- `print_summary(simulation_result)`: prints the integration summary.

Integration notes:

- `main.py` must not import `maya.cmds`.
- Maya geometry and animation remain in module-specific Maya-only helper functions for later Autodesk Maya testing.

### Maya Visualization Layer

Responsibilities:

- Build the first visible Cloud-Hive Bloomfield scene in Autodesk Maya.
- Reuse the pure Python integration flow to get cells, clouds, drops, tasks, paths, and bees.
- Call module-specific Maya helper functions for honeycomb geometry, cloud geometry, cloud flower geometry, falling resource effects, bee geometry, task path visuals, resource state visuals, and blocked-task markers.
- Add camera and light setup for a presentable honeycomb flower-field scene.

Planned module: `code/visual_module.py`

Current Maya-only interface:

- `create_maya_scene(config, prior_cell_state=None)`: runs the pure Python data flow and creates the Maya scene.
- `clear_scene()`: removes previous generated Cloud-Hive Bloomfield objects.
- `setup_camera_and_lighting(scene_radius)`: creates a camera plus a warm key, cool fill, top fill, low ambient light, and an Arnold skydome fill when MtoA is available. Cast shadows are disabled for the flat, bright pixel-art presentation.
- `create_render_background(camera_transform, camera_shape, ...)`: creates a world-space, inward-facing 360-degree sky sphere with a seamless texture-free purple-to-gold vertical ramp and a varied ring of two-tone pixel-cloud accents. It remains visible from orbiting viewport and render cameras while preserving the user's existing Maya output resolution.
- `create_falling_resource_effects(drops, clouds, ...)`: animates shared-shape voxel instances for nectar, pollen, and glints.
- `create_cell_resource_visuals(...)`: keeps cell contents synchronized with the action timeline: visible resource increases when a drop lands, decreases when a bee picks it up, and increases again in the target cell at delivery. Nectar uses discrete merged voxel stacks, pollen uses shared cube instances, and caps use voxel plates.
- `create_blocked_task_visuals(...)`: marks cells whose cleanup/transport tasks have no BFS path.

Maya entry script:

- `maya_scripts/cloud_hive_meadow.py` keeps its historical filename, adds the project `code/` directory to `sys.path`, reloads project modules for Maya testing, and can either run `create_maya_scene()` directly or open the Maya UI.

Integration notes:

- The Maya visualization layer is intentionally separate from the pure Python logic.
- The honeycomb uses a global texture-free voxel lattice. Hidden faces are culled and visible voxels are merged by material before Maya mesh creation.
- `visual.voxel_density` controls cell-radius pixel density; the default `14` produces about 28 pixels across a cell. Large hives automatically lower the effective density to keep generation bounded.
- `visual_module.py` and the Maya entry script do not import `maya.cmds` at top level.
- Maya-specific functions import `maya.cmds` inside function bodies and should be tested later inside Autodesk Maya.

### Maya UI Module

Responsibilities:

- Provide a simple Maya control panel for the Bloomfield MVP scene.
- Expose core generation parameters such as honeycomb size, ratios, cloud count, drop rates, wind settings, bee count, and path visibility.
- Generate a Maya scene by building a config dictionary and calling `visual_module.create_maya_scene(config)`.
- Clear generated scene objects through `visual_module.clear_scene()`.
- Run the pure Python summary through `main.run_simulation(config)` and print the result to the Script Editor.

Planned module: `code/ui_module.py`

Current Maya-only interface:

- `create_cloud_hive_ui()`: creates the Cloud-Hive Control Panel window.
- `build_config_from_ui(controls)`: reads Maya UI values and builds an integration config dictionary.

Integration notes:

- `ui_module.py` imports no Maya APIs at top level.
- Maya UI commands import `maya.cmds` inside function bodies.
- The Maya entry script exposes `open_ui()` as an optional way to launch the control panel.

## Data Interfaces

The MVP should use simple Python data structures first, then move to dataclasses if needed.

Suggested records:

- `Cell`: cell id, hex coordinate, world position, cell type, current resource state, neighbor ids, `is_blocked`, `blocked_by_capacity`, `queen_role`, and optional `maya_object` handle.
- `ResourceDrop`: resource id, resource type, source position, landing position, mapped cell id, and optional `maya_object` handle.
- `Task`: task id, task type, source cell id, target cell id, resource id, BFS path, priority, status, and optional `completed_amount`/`resource_event` metadata.
- `Bee`: bee id, current cell id, assigned task id, movement path, and optional `task_queue` or `current_task` state from the integration layer.

Suggested module interfaces:

- `hive_module` returns cell dictionaries, neighbor maps, and nearest-cell results.
- `cloud_resource_module` returns resource drop records.
- `bee_task_module` consumes cells and drops, then returns tasks and paths.
- `visual_module` consumes cells, drops, tasks, and paths to build Maya visuals.
- `ui_module` calls `main.py` entry points with user-selected parameters.

## Runtime State Clarifications

The current implementation has a few runtime rules that are stronger than the original high-level prose:

- The honeycomb uses `queen` and `queen_reserved` cells to reserve the central chamber footprint and keep it structurally hidden from normal pathfinding.
- `is_blocked` is not only a static cell-type property; it is refreshed dynamically from `capacity` and `blocked_by_capacity` during path computation.
- `bfs_find_path()` recomputes the blocked state of the whole cell graph before searching, so path reachability depends on the current resource fill state of the honeycomb.
- The task layer is not purely a planner for "wrong drop" events. It also carries per-task resource transfer data and records post-transfer state such as whether a target cell became capped.

## MVP Scope

- Generate a small honeycomb terrain.
- Assign visible cell types.
- Generate nectar and pollen drops from cloud flowers.
- Map drops to honeycomb cells.
- Detect correct and incorrect resource placement.
- Create tasks for incorrect placement.
- Use BFS to find a valid destination cell.
- Show bee movement and resource transport.
- Provide a simple Maya UI to regenerate or demonstrate the honeycomb flower-field scene.
- Produce screenshots, short video output, presentation slides, and a written report.

## Non-Goals

- Physically accurate fluid, bee, or pollen simulation.
- Complex production asset pipeline.
- Full gameplay balancing.
- Real-time interactive strategy gameplay.
- Advanced AI planning beyond BFS for the MVP.
- External database or network integration.
