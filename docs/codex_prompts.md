# Codex Prompts

## Development Prompt 1

```text
We are working in a local clone of the GitHub repository:

https://github.com/PppPbb/bee

This is a Maya Python course project called Cloud-Hive Bloomfield.

Important context:
I am currently not on a computer with Autodesk Maya installed, so please separate pure Python logic from Maya-specific functions. Pure Python logic should be testable outside Maya. Maya functions using maya.cmds should be clearly marked and will be tested later inside Autodesk Maya.

Project goal:
Build a stylized procedural honeycomb resource-management scene in Maya Python.

Core loop:
1. Cloud flowers generate nectar and pollen.
2. Resource drops fall toward the honeycomb terrain.
3. Drops are mapped to the nearest honeycomb cells.
4. The system checks whether the resource landed in the correct cell type.
5. Wrong cell types create transport or cleaning tasks.
6. Bees use BFS on the hexagonal honeycomb graph to move resources to the nearest correct storage cell.
7. The final result visualizes resource drops, paths, bee movement, and cell state changes.

Please reorganize or initialize the repository structure.

Target structure:

code/
  main.py
  config.py
  hive_module.py
  cloud_resource_module.py
  bee_task_module.py
  ui_module.py
  visual_module.py

docs/
  system_design.md
  task_plan.md
  codex_prompts.md

presentation/
report/
results/images/
results/video/
scenes/
assets/

The current repository may already contain folders such as assets, docs, and maya_scripts. Please do not delete existing files unless they are clearly unnecessary. If existing files are useful, keep them and create the missing target folders and files.

Create or update README.md.

README.md should include:
1. Project name: Cloud-Hive Bloomfield
2. Goal: a stylized procedural honeycomb resource-management scene in Maya Python
3. MVP features:
   - hexagonal honeycomb terrain
   - cell type assignment
   - cloud resource generation
   - resource drop mapping
   - task creation
   - BFS pathfinding
   - bee animation
   - Maya UI
   - visual demonstration
4. Code organization
5. Development note:
   - pure Python logic can be tested outside Maya
   - maya.cmds functions must be tested inside Autodesk Maya

docs/system_design.md should explain:
1. Overall system architecture
2. The core loop
3. The three main subsystems:
   - honeycomb system
   - cloud resource system
   - bee task and animation system
4. Data interfaces between modules
5. MVP scope and non-goals

docs/task_plan.md should explain:
1. Three-person division of work
2. Suggested development phases
3. MVP checklist
4. Final presentation and report outputs

docs/codex_prompts.md should record this prompt as the first development prompt.

For each Python file, add a module-level docstring and TODO comments only. Do not implement the full project yet.

Please make the repository clean and suitable for a Maya Python assignment.
```

## Development Prompt 2

```text
Implement the first core module, code/hive_module.py, for the honeycomb system.
Keep pure Python logic testable outside Maya, import maya.cmds only inside Maya-specific functions, and add a pure Python self-test.
```

Implemented:

- Added axial-coordinate world conversion for flat XZ-plane honeycomb placement.
- Added hex grid generation with cell dictionaries matching the project data interface.
- Added cell lookup helpers, neighbor calculation, deterministic cell type assignment, nearest-storage lookup, and BFS pathfinding.
- Added Maya-only honeycomb prism geometry creation and BFS path highlighting helpers.
- Documented the hive module interface in `docs/system_design.md`.

## Development Prompt 3

```text
Implement the second core module, code/cloud_resource_module.py, for the cloud resource system.
Keep pure Python logic testable outside Maya, import maya.cmds only inside Maya-specific functions, generate cloud/drop data, apply wind offset, map drops to nearest honeycomb cells, and add a pure Python self-test.
```

Implemented:

- Added deterministic cloud data generation with resource amounts and cloud emission points.
- Added wind-influenced nectar and pollen drop generation with concentrated nectar and more scattered pollen.
- Added XZ-plane distance and nearest-cell mapping helpers for honeycomb cells.
- Added mapping summary output for resource drops.
- Added Maya-only cloud geometry, flower geometry, and drop marker helpers.
- Documented the cloud resource module interface in `docs/system_design.md`.

## Development Prompt 4

```text
Implement the third core module, code/bee_task_module.py, for validating mapped resource drops, creating transport and cleanup tasks, assigning tasks to bees, calling hive_module BFS, completing resource transport, and adding Maya-only bee animation helpers.
```

Implemented:

- Added resource-to-cell validation rules for nectar/honey and pollen/pollen storage.
- Added capacity-aware resource deposit logic for honeycomb cells.
- Added task creation for wrong drops, including high-priority cleanup tasks for capped or blocked cells.
- Added bee dictionaries, task selection by priority and XZ distance, BFS path assignment through `hive_module.bfs_find_path()`, task completion, and task summaries.
- Added Maya-only bee geometry, bee path animation, and task path visualization helpers.
- Documented how `bee_task_module` connects mapped drops from `cloud_resource_module` with BFS paths from `hive_module`.

## Development Prompt 5

```text
Implement code/main.py as the first pure Python end-to-end integration script for Cloud-Hive Bloomfield.
Update local main, create feature/main-integration, run the core loop outside Maya, load defaults from config.py if possible, print a clear summary, and update project documentation.
```

Implemented:

- Added default pure Python integration parameters in `code/config.py`.
- Added `code/main.py` to generate the hive, clouds, drops, mapped cells, tasks, BFS paths, bees, and completed reachable transport tasks.
- Added readable integration summary output for cell counts, drop counts, task summaries, BFS path counts, and an example path.
- Documented the main integration script interface in `docs/system_design.md`.

## Development Prompt 6

```text
Implement the first Maya visualization MVP for Cloud-Hive Bloomfield.
Update local main, create feature/maya-visualization-mvp, add create_maya_scene() in visual_module.py, call existing Maya helper functions, add camera/light/ground/labels, update the Maya entry script, and keep pure Python files compilable outside Maya.
```

Implemented:

- Added `code/visual_module.py` as the Maya visualization layer for the MVP scene.
- Added `create_maya_scene(config=None)` to run the pure Python data flow and call existing Maya helper functions for honeycomb cells, clouds, flowers, drops, bees, and task path visuals.
- Added helper functions for clearing generated scene groups, creating a ground plane, setting up camera/lighting, and creating optional labels.
- Replaced `maya_scripts/cloud_hive_meadow.py` with a lightweight Maya entry script that adds the project `code/` folder to `sys.path`, imports `create_maya_scene`, runs it, and prints a success message.
- Documented that Maya visualization is separated from pure Python logic and that `maya.cmds` imports happen inside Maya-specific functions.

## Development Prompt 7

```text
Implement the first Maya UI MVP for Cloud-Hive Bloomfield.
Update local main, create feature/maya-ui-mvp, add create_cloud_hive_ui() in ui_module.py, expose controls for core scene parameters, wire Generate Scene, Clear Scene, and Run Pure Python Summary buttons, update the Maya entry script, and keep non-Maya checks passing.
```

Implemented:

- Added `code/ui_module.py` with a Maya-only Cloud-Hive Control Panel.
- Added UI controls for honeycomb size, cell size, cell ratios, cloud count, drop rates, wind settings, bee count, and path visibility.
- Wired Generate Scene to `visual_module.create_maya_scene(config)`, Clear Scene to `visual_module.clear_scene()`, and Run Pure Python Summary to `main.run_simulation(config)`.
- Added visual defaults in `code/config.py` and made `visual_module.create_maya_scene()` respect the Show Paths setting.
- Added optional `open_ui()` support to `maya_scripts/cloud_hive_meadow.py`.
- Documented the UI module role and Maya/Pure Python separation in `docs/system_design.md`.

## Development Prompt 8

```text
Rename the project concept to Cloud-Hive Bloomfield.
Use the final English title "Cloud-Hive Bloomfield: A Procedural Honeycomb Resource System in Maya" and the final Chinese title "云上蜜源驱动的程序化蜂巢花田系统".
Update documentation to describe a honeycomb flower-field system rather than a meadow, grassland, ground-flower, or beehive-prop scene.
Do not rename Python files, directories, maya_scripts/cloud_hive_meadow.py, or function names.
Do not change runtime behavior.
```

Implemented:

- Updated project documentation to use Cloud-Hive Bloomfield as the final concept name.
- Added the final English and Chinese titles to project-facing documentation.
- Revised visual wording toward a honeycomb flower-field resource system.
- Kept the existing `maya_scripts/cloud_hive_meadow.py` filename as a compatibility detail.
