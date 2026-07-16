# Cloud-Hive Meadow Maya Project

Procedural visual prototype for a stylized honeycomb resource scene in Maya.

## What This Version Contains

- Hexagonal honeycomb terrain made from tightly packed prism cells.
- Uneven cell heights and type-based materials.
- Cloud clusters represented by particle-like spheres.
- Honey rain and hanging nectar drops under the cloud clusters.
- Placeholder bees represented by small cuboids.
- Nectar and pollen resource drops represented by small colored spheres.
- BFS path visualization across the honeycomb graph.
- A simple Maya UI for regenerating the scene with core parameters.

## How To Run In Maya

1. Open Maya.
2. Open the Script Editor.
3. Run:

```python
exec(open(r"C:\Users\YUN\Desktop\CloudHiveMeadow_Maya\maya_scripts\cloud_hive_meadow.py").read())
```

If you run it from another location, change the path to the script.

## Replace Placeholder Models Later

Asset placeholders are reserved in `assets/models/`:

- `bee_placeholder.ma` or `bee_placeholder.fbx`
- `cloud_particle_placeholder.ma` or `cloud_particle_placeholder.fbx`
- `honey_cell_detail.ma`
- `pollen_cell_detail.ma`
- `capped_cell_detail.ma`
- `resource_nectar.ma`
- `resource_pollen.ma`
- `central_hive_placeholder.ma`

The current script uses Maya primitive shapes only. Later, replace the body of:

- `create_bee_placeholder`
- `create_cloud_cluster`
- `create_resource_drop`
- `create_cell_geometry`

## Algorithm Handoff

See `docs/algorithm_interface_todo.md` for the interface plan and TODO list for turning the static visual prototype into a running resource collection system.

## Folder Layout

```text
CloudHiveMeadow_Maya/
  assets/
    models/
    textures/
    references/
  docs/
    algorithm_interface_todo.md
    asset_placeholders.md
  maya_scripts/
    cloud_hive_meadow.py
  scenes/
```

## Visual Scope

This first version focuses on visual effect and project scaffolding:

- Bees are small cuboids.
- Clouds are sphere clusters.
- Flowers are intentionally skipped.
- Honeycomb cells are close-packed hexagonal columns with varied heights and simple wax rims.
- Paths, wrong drops, and resource particles are visible for algorithm presentation.
