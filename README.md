# Cloud-Hive Meadow

Cloud-Hive Meadow is a Maya Python course project for building a stylized procedural honeycomb resource-management scene in Autodesk Maya.

## Goal

A stylized procedural honeycomb resource-management scene in Maya Python.

Cloud flowers generate resources, resource drops fall onto a honeycomb terrain, bees correct misplaced resources, and the final scene visualizes resource flow, bee movement, paths, and cell state changes.

## MVP Features

- Hexagonal honeycomb terrain
- Cell type assignment
- Cloud resource generation
- Resource drop mapping
- Task creation
- BFS pathfinding
- Bee animation
- Maya UI
- Visual demonstration

## Code Organization

```text
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
  algorithm_interface_todo.md
  asset_placeholders.md

presentation/
report/
results/images/
results/video/
scenes/
assets/
maya_scripts/
```

### Planned Module Roles

- `code/config.py`: shared constants, resource names, cell types, and scene settings.
- `code/hive_module.py`: pure Python honeycomb grid logic, cell assignment, nearest-cell lookup, and Maya-only honeycomb geometry creation.
- `code/cloud_resource_module.py`: pure Python resource generation and drop mapping, plus Maya-only cloud and drop visualization.
- `code/bee_task_module.py`: pure Python task creation and BFS pathfinding, plus Maya-only bee movement animation.
- `code/ui_module.py`: Maya UI controls and callbacks.
- `code/visual_module.py`: Maya scene materials, debug overlays, path drawing, and final presentation visuals.
- `code/main.py`: future entry point that coordinates modules.

The existing `maya_scripts/cloud_hive_meadow.py` is kept as a useful visual prototype/reference script while the new modular structure is developed.

## Core Loop

1. Cloud flowers generate nectar and pollen.
2. Resource drops fall toward the honeycomb terrain.
3. Drops are mapped to the nearest honeycomb cells.
4. The system checks whether the resource landed in the correct cell type.
5. Wrong cell types create transport or cleaning tasks.
6. Bees use BFS on the hexagonal honeycomb graph to move resources to the nearest correct storage cell.
7. The final result visualizes resource drops, paths, bee movement, and cell state changes.

## Development Note

Pure Python logic should be testable outside Maya. This includes hex-grid data structures, nearest-cell mapping, resource validation, task creation, and BFS pathfinding.

Functions that import or call `maya.cmds` must be clearly marked as Maya-specific and tested later inside Autodesk Maya.
