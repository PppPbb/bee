"""Maya visualization layer for the Cloud-Hive Meadow MVP."""

import copy
import math
import random

from bee_task_module import (
    animate_bee_collection_cycle,
    calculate_bee_frames_per_unit,
    create_bee_geometry,
    create_task_path_visuals,
    plan_bee_collection_cycle,
)
from cloud_resource_module import (
    create_cloud_geometry,
    create_drop_particles,
    create_flower_geometry_on_clouds,
)
from hive_module import (
    create_honeycomb_geometry,
    create_merged_voxel_mesh,
    create_voxel_cube_instances,
    create_voxel_material,
    ensure_voxel_cube_prototype,
    get_voxel_dimensions,
    hex_voxel_layer_keys,
)
from main import load_parameters, run_simulation


ROOT_GROUP = "CloudHive_Visualization_GRP"
CAMERA_LIGHT_GROUP = "CloudHive_CameraLight_GRP"
OVERVIEW_CAMERA = "CloudHive_Render_CAM"
LEGACY_ANIMATION_START = 1000
DEMO_STAGE_BASE_RANGES = {
    0: (1, 2),
    1: (10, 58),
    2: (70, 94),
    3: (106, 136),
    4: (148, 196),
    5: (208, 238),
}
DEMO_COLLECTION_START = 250
DEMO_COLLECTION_FRAME_STEP = 6
DEMO_STAGE_FOUR_COMPLETION_HOLD_FRAMES = 6
DEFAULT_DEMO_MAX_ACTIVE_BEES = 0
DEMO_STAGE_LABELS = {
    0: "Base Scene",
    1: "Natural Resource Drop",
    2: "Drop Mapping and Cell Validation",
    3: "Direct Storage or Task Creation",
    4: "Bee Task Selection and BFS Path",
    5: "Resource Check and Collection Trigger",
    6: "Cloud Collection Ready",
    7: "Deposit Update / Next Cycle Ready",
}
DEMO_VISUAL_GROUPS = {
    "natural_drops": "CloudHive_ResourceDrops_GRP",
    "falling_drops": "CloudHive_FallingResources_GRP",
    "mapping": "CloudHive_DropMapping_GRP",
    "validation": "CloudHive_ValidationHighlights_GRP",
    "direct_storage": "CloudHive_DirectStorage_GRP",
    "task_markers": "CloudHive_TaskMarkers_GRP",
    "bee_selections": "CloudHive_BeeSelections_GRP",
    "bfs_paths": "CloudHive_BeeTaskPaths_GRP",
    "blocked_tasks": "CloudHive_BlockedTasks_GRP",
    "collection_triggers": "CloudHive_CollectionTriggers_GRP",
    "collection_visuals": "CloudHive_CollectionVisuals_GRP",
    "deposit_updates": "CloudHive_DepositUpdate_GRP",
}
DEMO_GUIDE_GROUP = "CloudHive_DemoGuide_GRP"
DEMO_GUIDE_STAGE_GROUP = "CloudHive_StageIndicator_GRP"
DEMO_GUIDE_LEGEND_GROUP = "CloudHive_Legend_GRP"
DEMO_GUIDE_HINT_GROUP = "CloudHive_StageHint_GRP"
DEMO_GUIDE_HUDS = {
    "summary": "CloudHive_DemoGuide_Summary_HUD",
    "hint": "CloudHive_DemoGuide_Hint_HUD",
}
LEGACY_DEMO_GUIDE_HUDS = (
    "CloudHive_DemoGuide_Title_HUD",
    "CloudHive_DemoGuide_Description_HUD",
    "CloudHive_DemoGuide_Focus_HUD",
    "CloudHive_DemoGuide_LegendTitle_HUD",
    "CloudHive_DemoGuide_Resources_HUD",
    "CloudHive_DemoGuide_Cells_HUD",
    "CloudHive_DemoGuide_Restricted_HUD",
    "CloudHive_DemoGuide_Tasks_HUD",
    "CloudHive_DemoGuide_Paths_HUD",
)
DEMO_GUIDE_STAGE_CONTENT = {
    0: {
        "title": "Cloud-Hive Bloomfield",
        "description": "Procedural honeycomb resource system",
        "hint": "Click Next Simulation Step to begin.",
        "focus": "Base: honeycomb | queen chamber | clouds | bees | storage",
        "action": "The base hive, clouds, bees, and stored resources are prepared.",
        "watch": "Locate the queen chamber, storage cells, clouds, and idle bees.",
        "difference": "This is the neutral starting view before new resources appear.",
    },
    1: {
        "title": "Stage 1 - Natural Resource Drop",
        "description": "Cloud flowers randomly generate nectar and pollen.",
        "hint": "New resources appear from cloud flowers.",
        "focus": "GOLD / AMBER = nectar | ORANGE / PURPLE = pollen",
        "action": "Cloud flowers release a new randomized set of resource drops.",
        "watch": "Watch gold nectar and orange-purple pollen fall toward the hive.",
        "difference": "New resource objects appear; mapping and validation are not shown yet.",
    },
    2: {
        "title": "Stage 2 - Mapping & Validation",
        "description": (
            "Each drop maps to the nearest cell and is checked against its type."
        ),
        "hint": "Drops are mapped to nearby cells.",
        "focus": "GREEN = matched | ORANGE = wrong type | RED = blocked",
        "action": "Every drop is mapped to its nearest cell and validated by cell type.",
        "watch": "Follow mapping lines and compare green, orange, and red cell markers.",
        "difference": "The drop destinations and validation results are now revealed.",
    },
    3: {
        "title": "Stage 3 - Storage or Task Creation",
        "description": (
            "Matched resources store directly; mismatched or blocked drops "
            "create tasks."
        ),
        "hint": "Correct drops store directly; wrong drops become tasks.",
        "focus": "DIRECT STORAGE | TRANSPORT TASK | CLEANUP TASK",
        "action": "Valid drops store immediately; misplaced or blocked drops become tasks.",
        "watch": "Compare direct-storage, blue transport, and red cleanup markers.",
        "difference": "Validation results are converted into storage updates or queued work.",
    },
    4: {
        "title": "Stage 4 - Bee Task Selection & BFS",
        "description": (
            "Bees select tasks and follow BFS paths to valid storage cells."
        ),
        "hint": "Bees crawl along shortest paths on the honeycomb.",
        "focus": "ACTIVE BEE -> SOURCE CELL -> BFS PATH -> TARGET CELL",
        "action": "Available bees select unique tasks and receive shortest BFS routes.",
        "watch": "Match each active bee to its source, bright path, and target ring.",
        "difference": "Task markers now become assigned bee movements on the hive surface.",
    },
    5: {
        "title": "Stage 5 - Resource Check",
        "description": (
            "The system checks whether honey or pollen storage is insufficient."
        ),
        "hint": "Low storage triggers cloud collection.",
        "focus": "RESOURCE CHECK -> LOW STORAGE -> COLLECTION TRIGGER",
        "action": "Stored nectar and pollen totals are compared with collection thresholds.",
        "watch": "Read the live totals and look for highlighted collection triggers.",
        "difference": "The system pauses transport to decide whether outside collection is needed.",
    },
    6: {
        "title": "Stage 6 - Cloud Collection",
        "description": (
            "Bees collect resources from cloud flowers when storage is low."
        ),
        "hint": "Bees fly only between the honeycomb and cloud flowers.",
        "focus": "HIVE CRAWL -> CLOUD FLIGHT -> COLLECT -> HIVE RE-ENTRY",
        "action": "Collection bees crawl to cloud-base cells, fly up, collect, and return.",
        "watch": "Separate the on-hive crawl from the vertical cloud-flight segment.",
        "difference": "Stage 5 only requested collection; Stage 6 performs the movement.",
    },
    7: {
        "title": "Stage 7 - Deposit & Storage Update",
        "description": (
            "Resources are deposited and storage updates for the next cycle."
        ),
        "hint": "Updated storage is ready for the next cycle.",
        "focus": "DEPOSIT -> STORAGE UPDATE -> NEXT CYCLE READY",
        "action": "Delivered resources update cell storage and capacity state.",
        "watch": "Look for destination-cell flashes, changed resource levels, and full cells.",
        "difference": "Movement is complete and persistent state is ready for the next cycle.",
    },
}
DEMO_GUIDE_LEGEND_LINES = (
    (
        "Resources | Nectar = GOLD / AMBER drop | "
        "Pollen = ORANGE / PURPLE grains"
    ),
    "Cells | Honey stores nectar | Pollen stores pollen | Empty is available",
    "Restricted | Capped is blocked | Queen chamber is reserved",
    "Tasks | Collection = cloud | Transport = relocate | Cleanup = invalid",
    "BFS | Bright path + ring = active bee | Muted path = queued task",
)
DEMO_GUIDE_LEGEND_ITEMS = (
    {
        "key": "nectar_drop",
        "label": "Nectar drop",
        "detail": "Gold sphere falling from a cloud",
        "color": (1.00, 0.64, 0.05),
        "icon_kind": "nectar_sphere",
    },
    {
        "key": "pollen_drop",
        "label": "Pollen drop",
        "detail": "Orange sphere falling from a cloud",
        "color": (1.00, 0.48, 0.05),
        "accent_color": (0.72, 0.20, 1.00),
        "icon_kind": "pollen_sphere",
    },
    {
        "key": "honey_cell",
        "label": "Honey storage cell",
        "detail": "Gold hexagon stores nectar",
        "color": (1.00, 0.55, 0.08),
        "icon_kind": "hex_fill",
    },
    {
        "key": "pollen_cell",
        "label": "Pollen storage cell",
        "detail": "Grained hexagon stores pollen",
        "color": (0.95, 0.48, 0.08),
        "accent_color": (1.00, 0.78, 0.12),
        "icon_kind": "hex_grains",
    },
    {
        "key": "empty_cell",
        "label": "Empty / available cell",
        "detail": "Cream hexagon available for storage",
        "color": (0.82, 0.78, 0.62),
        "icon_kind": "hex_outline",
    },
    {
        "key": "capped_cell",
        "label": "Capped / blocked cell",
        "detail": "Cream capped hexagon cannot accept resources",
        "color": (0.95, 0.86, 0.58),
        "accent_color": (0.55, 0.36, 0.18),
        "icon_kind": "hex_capped",
    },
    {
        "key": "queen_chamber",
        "label": "Queen chamber",
        "detail": "Large amber hexagon is reserved",
        "color": (0.64, 0.39, 0.10),
        "accent_color": (1.00, 0.79, 0.25),
        "icon_kind": "hex_queen",
    },
    {
        "key": "idle_bee",
        "label": "Bee",
        "detail": "Available worker on the honeycomb",
        "color": (1.00, 0.82, 0.15),
        "accent_color": (0.22, 0.16, 0.06),
        "icon_kind": "bee",
    },
    {
        "key": "mapping_line",
        "label": "Drop mapping line",
        "detail": "Cyan line links a drop to its nearest cell",
        "color": (0.10, 0.78, 1.00),
        "icon_kind": "line_mapping",
    },
    {
        "key": "validation_matched",
        "label": "Matched cell",
        "detail": "Green hexagon accepts the resource directly",
        "color": (0.12, 1.00, 0.30),
        "icon_kind": "hex_matched",
    },
    {
        "key": "validation_wrong",
        "label": "Wrong storage type",
        "detail": "Orange hexagon creates a transport task",
        "color": (1.00, 0.42, 0.04),
        "icon_kind": "hex_warning",
    },
    {
        "key": "validation_blocked",
        "label": "Blocked landing",
        "detail": "Red crossed hexagon creates a cleanup task",
        "color": (1.00, 0.04, 0.10),
        "icon_kind": "hex_blocked",
    },
    {
        "key": "validation_unmapped",
        "label": "Unmapped drop",
        "detail": "Gray marker has no valid landing cell",
        "color": (0.45, 0.45, 0.50),
        "icon_kind": "hex_unknown",
    },
    {
        "key": "direct_storage",
        "label": "Direct storage",
        "detail": "Gold resource enters a matching hexagon",
        "color": (1.00, 0.82, 0.08),
        "icon_kind": "direct_storage",
    },
    {
        "key": "transport_task",
        "label": "Transport task",
        "detail": "Blue marker relocates a misplaced resource",
        "color": (0.10, 0.42, 1.00),
        "icon_kind": "task_transport",
    },
    {
        "key": "cleanup_task",
        "label": "Cleanup task",
        "detail": "Red crossed marker handles an invalid drop",
        "color": (1.00, 0.08, 0.08),
        "icon_kind": "task_cleanup",
    },
    {
        "key": "active_transport_bees",
        "label": "Active transport bees",
        "detail": "Selected workers crawl on the honeycomb",
        "color": (1.00, 0.76, 0.16),
        "accent_color": (0.72, 0.24, 1.00),
        "icon_kind": "bee_active",
    },
    {
        "key": "task_endpoints",
        "label": "Source and target cells",
        "detail": "Colored source hexagon points to a target ring",
        "color": (1.00, 0.68, 0.10),
        "accent_color": (0.72, 0.24, 1.00),
        "icon_kind": "source_target",
    },
    {
        "key": "active_bfs_routes",
        "label": "Active BFS routes",
        "detail": "Bright task-colored lines match moving bees",
        "color": (1.00, 0.62, 0.04),
        "accent_color": (0.72, 0.24, 1.00),
        "icon_kind": "line_active_route",
    },
    {
        "key": "queued_bfs_routes",
        "label": "Queued BFS routes",
        "detail": "Muted dashed lines wait for an available bee",
        "color": (0.20, 0.34, 0.44),
        "icon_kind": "line_queued",
    },
    {
        "key": "nectar_collection_trigger",
        "label": "Nectar collection trigger",
        "detail": "Gold halo marks a nectar cloud source",
        "color": (1.00, 0.72, 0.05),
        "icon_kind": "collection_trigger",
    },
    {
        "key": "pollen_collection_trigger",
        "label": "Pollen collection trigger",
        "detail": "Purple halo marks a pollen cloud source",
        "color": (0.72, 0.20, 1.00),
        "accent_color": (1.00, 0.30, 0.05),
        "icon_kind": "collection_trigger",
    },
    {
        "key": "queued_collection",
        "label": "Queued collection",
        "detail": "Muted cloud task waits for an available bee",
        "color": (0.42, 0.32, 0.48),
        "icon_kind": "collection_queued",
    },
    {
        "key": "active_collection_bees",
        "label": "Active collection bees",
        "detail": "Selected workers perform cloud collection",
        "color": (1.00, 0.76, 0.16),
        "accent_color": (0.72, 0.20, 1.00),
        "icon_kind": "bee_active",
    },
    {
        "key": "hive_crawl",
        "label": "Honeycomb crawl",
        "detail": "Mint line is on-hive movement",
        "color": (0.15, 0.95, 0.72),
        "icon_kind": "line_crawl",
    },
    {
        "key": "cloud_flight",
        "label": "Cloud flight",
        "detail": "Magenta rising line is the flying segment",
        "color": (0.95, 0.30, 1.00),
        "icon_kind": "line_flight",
    },
    {
        "key": "nectar_payload",
        "label": "Collected nectar",
        "detail": "Gold droplet carried by a bee",
        "color": (1.00, 0.72, 0.05),
        "icon_kind": "nectar_droplet",
    },
    {
        "key": "pollen_payload",
        "label": "Collected pollen",
        "detail": "Orange-purple grain cluster carried by a bee",
        "color": (1.00, 0.30, 0.05),
        "accent_color": (0.72, 0.20, 1.00),
        "icon_kind": "pollen_cluster",
    },
    {
        "key": "nectar_deposit",
        "label": "Nectar deposit",
        "detail": "Gold marker updates nectar storage",
        "color": (1.00, 0.72, 0.04),
        "icon_kind": "deposit_hex",
    },
    {
        "key": "pollen_deposit",
        "label": "Pollen deposit",
        "detail": "Orange grains update pollen storage",
        "color": (1.00, 0.28, 0.04),
        "accent_color": (1.00, 0.72, 0.08),
        "icon_kind": "deposit_grains",
    },
    {
        "key": "full_storage",
        "label": "Full storage cell",
        "detail": "Cream filled hexagon has reached capacity",
        "color": (0.95, 0.88, 0.68),
        "accent_color": (0.62, 0.42, 0.16),
        "icon_kind": "hex_full",
    },
    {
        "key": "collection_reentry",
        "label": "Hive re-entry",
        "detail": "Purple ring marks a collection return point",
        "color": (0.72, 0.30, 1.00),
        "icon_kind": "reentry",
    },
)
DEMO_GUIDE_LEGEND_CATALOG = {
    item["key"]: item for item in DEMO_GUIDE_LEGEND_ITEMS
}


def _resolve_demo_active_bee_limit(task_count, bee_count, optional_cap=None):
    """Return the active worker count; non-positive caps mean unlimited."""
    available_task_count = max(0, int(task_count))
    available_bee_count = max(0, int(bee_count))
    active_limit = min(available_task_count, available_bee_count)
    try:
        configured_cap = int(optional_cap) if optional_cap is not None else 0
    except (TypeError, ValueError):
        configured_cap = 0
    if configured_cap > 0:
        active_limit = min(active_limit, configured_cap)
    return active_limit


def _demo_legend_item(item_key, **overrides):
    """Return a detached, normalized legend item from the shared catalog."""
    item = dict(DEMO_GUIDE_LEGEND_CATALOG[item_key])
    item.update(overrides)
    item["color"] = tuple(float(value) for value in item["color"])
    if item.get("accent_color") is not None:
        item["accent_color"] = tuple(
            float(value) for value in item["accent_color"]
        )
    item["animated"] = bool(item.get("animated", False))
    normalized_ranges = []
    for frame_range in item.get("pulse_ranges", []) or []:
        if not frame_range or len(frame_range) < 2:
            continue
        try:
            start_frame = int(round(float(frame_range[0])))
            end_frame = int(round(float(frame_range[1])))
        except (TypeError, ValueError):
            continue
        normalized_ranges.append((
            max(1, start_frame),
            max(max(1, start_frame), end_frame),
        ))
    item["pulse_ranges"] = normalized_ranges
    return item


def _demo_stage_frame_range(scene_data, stage):
    """Return a safe frame range for guide pulse metadata."""
    frame_range = (scene_data or {}).get("demo_playback_ranges", {}).get(
        int(stage),
        (1, 2),
    )
    try:
        start_frame = max(1, int(round(float(frame_range[0]))))
        end_frame = max(start_frame + 1, int(round(float(frame_range[1]))))
    except (TypeError, ValueError, IndexError):
        start_frame, end_frame = 1, 2
    return start_frame, end_frame


def _demo_task_frame_ranges(tasks, segment_names=None):
    """Collect valid animation or named movement ranges from active tasks."""
    ranges = []
    for task in tasks:
        if not task.get("demo_active"):
            continue
        if segment_names:
            segments = task.get("movement_segments", {})
            for segment_name in segment_names:
                frame_range = segments.get(segment_name)
                if frame_range and len(frame_range) >= 2:
                    ranges.append(frame_range)
            continue
        start_frame = task.get("animation_start_frame")
        end_frame = task.get("animation_end_frame")
        if start_frame is not None and end_frame is not None:
            ranges.append((start_frame, end_frame))
    return ranges


def build_demo_stage_legend(scene_data, stage):
    """Return only the guide symbols that exist in one prepared stage.

    The returned list is pure data. Maya UI code can rebuild the small legend
    region from these records without touching the scene or stage state.
    """
    if not scene_data:
        return []

    safe_stage = max(0, min(7, int(stage)))
    active_scene = scene_data
    cells = active_scene.get("cells", [])
    drops = active_scene.get("drops", [])
    tasks = active_scene.get("tasks", [])
    outcomes = active_scene.get("drop_demo_visuals", {}).get("outcomes", [])
    drop_visuals = active_scene.get("drop_demo_visuals", {})
    transport_demo = active_scene.get("transport_demo", {})
    collection_tasks = active_scene.get("collection_tasks", [])
    resource_events = active_scene.get("resource_events", [])
    summary = active_scene.get("summary", {})
    stage_range = _demo_stage_frame_range(active_scene, safe_stage)
    legend = []
    used_keys = set()

    drop_resource_types = {
        str(drop.get("resource_type"))
        for drop in drops
        if drop.get("resource_type") in ("nectar", "pollen")
    }
    collection_resource_types = {
        str(task.get("resource_type"))
        for task in collection_tasks
        if task.get("resource_type") in ("nectar", "pollen")
    }
    active_collection_tasks = [
        task for task in collection_tasks if task.get("demo_active")
    ]
    active_collection_resource_types = {
        str(task.get("resource_type"))
        for task in active_collection_tasks
        if task.get("resource_type") in ("nectar", "pollen")
    }

    def add(item_key, condition=True, **overrides):
        if not condition or item_key in used_keys:
            return
        if overrides.get("animated") and not overrides.get("pulse_ranges"):
            overrides["pulse_ranges"] = [stage_range]
        legend.append(_demo_legend_item(item_key, **overrides))
        used_keys.add(item_key)

    if safe_stage == 0:
        cell_types = {str(cell.get("type", "")) for cell in cells}
        has_honey = "honey" in cell_types or any(
            float(cell.get("nectar", 0.0)) > 0.000001 for cell in cells
        )
        has_pollen = "pollen" in cell_types or any(
            float(cell.get("pollen", 0.0)) > 0.000001 for cell in cells
        )
        has_capped = "capped" in cell_types or any(
            cell.get("is_blocked")
            and cell.get("type") not in ("queen", "queen_reserved")
            for cell in cells
        )
        has_queen = bool(
            {"queen", "queen_reserved"}.intersection(cell_types)
        ) or any(cell.get("queen_role") for cell in cells)
        add("honey_cell", has_honey)
        add("pollen_cell", has_pollen)
        add("empty_cell", "empty" in cell_types)
        add("capped_cell", has_capped)
        add("queen_chamber", has_queen)
        add("idle_bee", bool(active_scene.get("bees")))

    elif safe_stage == 1:
        for resource_type in ("nectar", "pollen"):
            resource_drops = [
                drop for drop in drops
                if drop.get("resource_type") == resource_type
            ]
            pulse_ranges = [
                (
                    drop.get(
                        "demo_transition_start",
                        drop.get("animation_start_frame", stage_range[0]),
                    ),
                    drop.get(
                        "demo_transition_end",
                        drop.get("animation_end_frame", stage_range[1]),
                    ),
                )
                for drop in resource_drops
            ]
            add(
                "{0}_drop".format(resource_type),
                bool(resource_drops),
                animated=True,
                pulse_ranges=pulse_ranges,
            )

    elif safe_stage == 2:
        add("nectar_drop", "nectar" in drop_resource_types)
        add("pollen_drop", "pollen" in drop_resource_types)
        mapping_nodes = drop_visuals.get("mapping", [])
        add(
            "mapping_line",
            bool(mapping_nodes or outcomes),
            animated=True,
        )
        validation_results = {
            str(outcome.get("validation", "unmapped"))
            for outcome in outcomes
        }
        add(
            "validation_matched",
            "matched" in validation_results,
            animated=True,
        )
        add(
            "validation_wrong",
            "mismatched" in validation_results,
            animated=True,
        )
        add(
            "validation_blocked",
            "blocked" in validation_results,
            animated=True,
        )
        add(
            "validation_unmapped",
            "unmapped" in validation_results,
            animated=True,
        )

    elif safe_stage == 3:
        direct_count = sum(
            float(outcome.get("direct_storage_amount", 0.0)) > 0.000001
            for outcome in outcomes
        )
        transport_count = sum(
            str(task.get("type", "")).startswith("transport_")
            for task in tasks
        )
        cleanup_count = sum(
            task.get("type") == "clean_blocked" for task in tasks
        )
        add(
            "direct_storage",
            direct_count > 0,
            label="Direct storage  x{0}".format(direct_count),
            animated=True,
        )
        add(
            "transport_task",
            transport_count > 0,
            label="Transport tasks  x{0}".format(transport_count),
            animated=True,
        )
        add(
            "cleanup_task",
            cleanup_count > 0,
            label="Cleanup tasks  x{0}".format(cleanup_count),
            animated=True,
        )

    elif safe_stage == 4:
        assignments = transport_demo.get("assignments", [])
        active_path_nodes = transport_demo.get("active_path_visuals", [])
        secondary_tasks = transport_demo.get("secondary_tasks", [])
        secondary_path_nodes = transport_demo.get(
            "secondary_path_visuals",
            [],
        )
        timing = active_scene.get("transition_visuals", {}).get(
            "stage_four_timing",
            {},
        )
        movement_frames = timing.get("active_bee_final_movement_frames", [])
        movement_end = max(
            [stage_range[0] + 1]
            + [
                int(frame)
                for frame in movement_frames
                if frame is not None
            ]
        )
        movement_range = (stage_range[0], min(stage_range[1], movement_end))
        add(
            "active_transport_bees",
            bool(assignments),
            label="Active transport bees  x{0}".format(len(assignments)),
            animated=True,
            pulse_ranges=[movement_range],
        )
        add(
            "task_endpoints",
            bool(
                transport_demo.get("source_markers")
                or transport_demo.get("target_markers")
            ),
            label="Source -> target pairs  x{0}".format(len(assignments)),
            animated=True,
        )
        add(
            "active_bfs_routes",
            bool(assignments and active_path_nodes),
            label="Active BFS routes  x{0}".format(len(assignments)),
            animated=True,
            pulse_ranges=[movement_range],
        )
        add(
            "queued_bfs_routes",
            bool(secondary_tasks and secondary_path_nodes),
            label="Queued / secondary routes  x{0}".format(
                len(secondary_tasks)
            ),
        )
        transport_count = sum(
            str(task.get("type", "")).startswith("transport_")
            for task in tasks
        )
        cleanup_count = sum(
            task.get("type") == "clean_blocked" for task in tasks
        )
        add(
            "transport_task",
            transport_count > 0,
            label="Transport task markers  x{0}".format(transport_count),
        )
        add(
            "cleanup_task",
            cleanup_count > 0,
            label="Cleanup task markers  x{0}".format(cleanup_count),
        )

    elif safe_stage == 5:
        collection_check = active_scene.get("collection_check", {})
        needed_resources = set(
            collection_check.get("needed_resources", [])
        )
        presentation_resource = collection_check.get("presentation_resource")
        presentation_only = not needed_resources
        for resource_type in ("nectar", "pollen"):
            resource_tasks = [
                task for task in collection_tasks
                if task.get("resource_type") == resource_type
            ]
            if not resource_tasks:
                continue
            if presentation_only:
                detail = (
                    "Storage is sufficient; this cloud marker previews "
                    "the collection pathway"
                )
            else:
                detail = (
                    "Low {0} storage selects this cloud source"
                ).format(resource_type)
            add(
                "{0}_collection_trigger".format(resource_type),
                resource_type in collection_resource_types
                and (
                    resource_type in needed_resources
                    or resource_type == presentation_resource
                ),
                label=(
                    "{0} demo trigger".format(resource_type.title())
                    if presentation_only
                    else "{0} collection trigger".format(
                        resource_type.title()
                    )
                ),
                detail=detail,
                animated=True,
            )
        queued_count = sum(
            not task.get("demo_active") for task in collection_tasks
        )
        add(
            "queued_collection",
            queued_count > 0,
            label="Queued collection tasks  x{0}".format(queued_count),
        )

    elif safe_stage == 6:
        active_count = len(active_collection_tasks)
        active_ranges = _demo_task_frame_ranges(active_collection_tasks)
        crawl_ranges = _demo_task_frame_ranges(
            active_collection_tasks,
            ("on_hive",),
        )
        flight_ranges = _demo_task_frame_ranges(
            active_collection_tasks,
            ("cloud_flight", "on_hive_reentry"),
        )
        add(
            "active_collection_bees",
            active_count > 0,
            label="Active collection bees  x{0}".format(active_count),
            animated=True,
            pulse_ranges=active_ranges,
        )
        add(
            "hive_crawl",
            any(task.get("crawl_curve_object") for task in active_collection_tasks),
            animated=True,
            pulse_ranges=crawl_ranges,
        )
        add(
            "cloud_flight",
            any(task.get("flight_curve_object") for task in active_collection_tasks),
            animated=True,
            pulse_ranges=flight_ranges,
        )
        for resource_type in ("nectar", "pollen"):
            payload_ranges = [
                (task.get("collection_frame"), task.get("reentry_frame"))
                for task in active_collection_tasks
                if task.get("resource_type") == resource_type
            ]
            add(
                "{0}_payload".format(resource_type),
                resource_type in active_collection_resource_types,
                animated=True,
                pulse_ranges=payload_ranges,
            )
        queued_count = sum(
            not task.get("demo_active") for task in collection_tasks
        )
        add(
            "queued_collection",
            queued_count > 0,
            label="Queued collection tasks  x{0}".format(queued_count),
        )

    elif safe_stage == 7:
        deposited_resources = {
            str(event.get("resource_type"))
            for event in resource_events
            if event.get("resource_type") in ("nectar", "pollen")
            and float(event.get("amount", 0.0)) > 0.000001
        }
        add(
            "nectar_deposit",
            "nectar" in deposited_resources,
            animated=True,
        )
        add(
            "pollen_deposit",
            "pollen" in deposited_resources,
            animated=True,
        )
        full_count = int(summary.get("full_storage_cell_count", 0))
        if not full_count:
            full_count = sum(
                bool(cell.get("blocked_by_capacity")) for cell in cells
            )
        add(
            "full_storage",
            full_count > 0,
            label="Full storage cells  x{0}".format(full_count),
            animated=True,
        )
        add(
            "collection_reentry",
            bool(active_collection_tasks),
            label="Collection re-entry points  x{0}".format(
                len(active_collection_tasks)
            ),
            animated=True,
        )
        cleanup_count = sum(
            task.get("type") == "clean_blocked" for task in tasks
        )
        add(
            "cleanup_task",
            cleanup_count > 0,
            label="Cleanup task markers  x{0}".format(cleanup_count),
        )

    return legend


def _maya_safe_name_component(value):
    """Return a Maya-safe node-name component without changing data ids."""
    safe_value = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in str(value)
    )
    if not safe_value:
        return "unnamed"
    if safe_value[0].isdigit():
        return "n_{0}".format(safe_value)
    return safe_value


def build_demo_guide_text(scene_data, stage):
    """Return concise presentation text for one prepared demo stage.

    This helper is intentionally pure Python so guide copy and scene-specific
    counts can be checked without importing Maya.
    """
    safe_stage = max(0, min(7, int(stage)))
    content = dict(DEMO_GUIDE_STAGE_CONTENT[safe_stage])
    active_scene = scene_data or {}
    summary = active_scene.get("summary", {})
    cycle_number = int(summary.get("cycle_number", 0))

    if safe_stage == 3:
        outcomes = active_scene.get("drop_demo_visuals", {}).get("outcomes", [])
        direct_count = sum(
            float(outcome.get("direct_storage_amount", 0.0)) > 0.000001
            for outcome in outcomes
        )
        transport_count = sum(
            str(outcome.get("task_type", "")).startswith("transport_")
            for outcome in outcomes
        )
        cleanup_count = sum(
            outcome.get("task_type") == "clean_blocked"
            for outcome in outcomes
        )
        content["focus"] = (
            "Cycle {0} | DIRECT {1} | TRANSPORT {2} | CLEANUP {3}"
        ).format(
            cycle_number,
            direct_count,
            transport_count,
            cleanup_count,
        )
    elif safe_stage == 4:
        transport_demo = active_scene.get("transport_demo", {})
        active_count = len(transport_demo.get("assignments", []))
        waiting_count = len(transport_demo.get("secondary_tasks", []))
        content["focus"] = (
            "Cycle {0} | ACTIVE BEES {1} -> SOURCE -> BFS -> TARGET | "
            "WAITING {2}"
        ).format(cycle_number, active_count, waiting_count)
    elif safe_stage == 5:
        collection_check = active_scene.get("collection_check", {})
        totals = collection_check.get("totals", {})
        thresholds = collection_check.get("thresholds", {})
        needed = collection_check.get("needed_resources", [])
        trigger = (
            "LOW: {0}".format(" + ".join(item.upper() for item in needed))
            if needed
            else "NO SHORTAGE - DEMO COLLECTION PREVIEW"
        )
        content["focus"] = (
            "Cycle {0} | Nectar {1:.2f}/{2:.2f} | "
            "Pollen {3:.2f}/{4:.2f} | {5}"
        ).format(
            cycle_number,
            float(totals.get("nectar", 0.0)),
            float(thresholds.get("nectar", 0.0)),
            float(totals.get("pollen", 0.0)),
            float(thresholds.get("pollen", 0.0)),
            trigger,
        )
    elif safe_stage == 6:
        collection_tasks = active_scene.get("collection_tasks", [])
        active_tasks = [
            task for task in collection_tasks if task.get("demo_active")
        ]
        resource_types = sorted({
            str(task.get("resource_type", "")).upper()
            for task in active_tasks
            if task.get("resource_type")
        })
        content["focus"] = (
            "Cycle {0} | ACTIVE COLLECTION BEES {1} | {2} | "
            "HIVE CRAWL -> CLOUD FLIGHT -> RETURN"
        ).format(
            cycle_number,
            len(active_tasks),
            " + ".join(resource_types) if resource_types else "NO COLLECTION",
        )
    elif safe_stage == 7:
        content["focus"] = (
            "Cycle {0} | STORED NECTAR {1:.2f} | STORED POLLEN {2:.2f} | "
            "FULL CELLS {3}"
        ).format(
            cycle_number,
            float(summary.get("stored_nectar_total", 0.0)),
            float(summary.get("stored_pollen_total", 0.0)),
            int(summary.get("full_storage_cell_count", 0)),
        )
    else:
        content["focus"] = "Cycle {0} | {1}".format(
            cycle_number,
            content["focus"],
        )

    content["stage"] = safe_stage
    return content


def build_demo_guide_panel_data(scene_data, stage):
    """Build pure presentation data for the separate Demo Guide Panel."""
    safe_stage = max(0, min(7, int(stage)))
    active_scene = scene_data or {}
    text = build_demo_guide_text(active_scene, safe_stage)
    summary = active_scene.get("summary", {})
    outcomes = active_scene.get("drop_demo_visuals", {}).get("outcomes", [])
    tasks = active_scene.get("tasks", [])
    collection_tasks = active_scene.get("collection_tasks", [])
    transport_demo = active_scene.get("transport_demo", {})

    direct_storage_count = sum(
        float(outcome.get("direct_storage_amount", 0.0)) > 0.000001
        for outcome in outcomes
    )
    transport_task_count = sum(
        str(task.get("type", "")).startswith("transport_")
        for task in tasks
    )
    cleanup_task_count = sum(
        task.get("type") == "clean_blocked"
        for task in tasks
    )
    active_transport_count = len(transport_demo.get("assignments", []))
    active_collection_count = sum(
        bool(task.get("demo_active"))
        for task in collection_tasks
    )
    if safe_stage == 4:
        active_bee_count = active_transport_count
        queued_task_count = len(transport_demo.get("secondary_tasks", []))
    elif safe_stage == 6:
        active_bee_count = active_collection_count
        queued_task_count = len(collection_tasks) - active_collection_count
    else:
        active_bee_count = 0
        queued_task_count = int(summary.get("queued_task_count", 0))

    cycle_number = int(summary.get("cycle_number", 0))
    legend_items = build_demo_stage_legend(scene_data, safe_stage)
    return {
        "has_scene": bool(scene_data),
        "cycle": cycle_number,
        "stage": safe_stage,
        "stage_name": DEMO_STAGE_LABELS[safe_stage],
        "stage_title": text["title"],
        "description": text["description"],
        "hint": text["hint"],
        "focus": text["focus"],
        "action": text["action"],
        "watch": text["watch"],
        "difference": text["difference"],
        "hud_summary": "Cycle {0} | Stage {1} - {2}".format(
            cycle_number,
            safe_stage,
            DEMO_STAGE_LABELS[safe_stage],
        ),
        "legend": legend_items,
        "legend_active_keys": [
            item["key"] for item in legend_items if item.get("animated")
        ],
        "status": {
            "new_drops": int(summary.get(
                "drop_count",
                len(active_scene.get("drops", [])),
            )),
            "direct_storage": int(direct_storage_count),
            "transport_tasks": int(transport_task_count),
            "cleanup_tasks": int(cleanup_task_count),
            "collection_tasks": int(len(collection_tasks)),
            "active_bees": int(active_bee_count),
            "queued_tasks": int(queued_task_count),
            "stored_nectar": float(summary.get("stored_nectar_total", 0.0)),
            "stored_pollen": float(summary.get("stored_pollen_total", 0.0)),
        },
    }


def _remove_demo_guide_huds(cmds, hud_names=None):
    """Remove only Cloud-Hive guide HUD entries."""
    names = hud_names or tuple(DEMO_GUIDE_HUDS.values()) + LEGACY_DEMO_GUIDE_HUDS
    for hud_name in names:
        try:
            if cmds.headsUpDisplay(hud_name, exists=True):
                cmds.headsUpDisplay(hud_name, remove=True)
        except RuntimeError:
            pass


def _upsert_demo_guide_hud(
    cmds,
    hud_name,
    section,
    block,
    label,
    font_size="small",
    block_size="small",
    label_width=480,
):
    """Create or update one screen-anchored, playblast-visible HUD line."""
    if cmds.headsUpDisplay(hud_name, exists=True):
        cmds.headsUpDisplay(hud_name, edit=True, label=str(label))
        return hud_name

    options = {
        "section": int(section),
        "block": int(block),
        "label": str(label),
        "labelFontSize": font_size,
        "blockSize": block_size,
        "labelWidth": int(label_width),
        "allowOverlap": True,
    }
    try:
        cmds.headsUpDisplay(hud_name, **options)
    except RuntimeError:
        free_block = cmds.headsUpDisplay(nextFreeBlock=int(section))
        options["block"] = int(free_block)
        cmds.headsUpDisplay(hud_name, **options)
    return hud_name


def _set_demo_guide_attribute(cmds, node, attribute, value, value_type):
    """Store readable guide state on lightweight Outliner groups."""
    if not node or not cmds.objExists(node):
        return
    if not cmds.attributeQuery(attribute, node=node, exists=True):
        if value_type == "string":
            cmds.addAttr(node, longName=attribute, dataType="string")
        else:
            cmds.addAttr(node, longName=attribute, attributeType=value_type)
    if value_type == "string":
        cmds.setAttr(
            "{0}.{1}".format(node, attribute),
            str(value),
            type="string",
        )
    else:
        cmds.setAttr("{0}.{1}".format(node, attribute), value)


def _enable_demo_guide_in_model_panels(cmds):
    """Ensure Maya model panels display HUD ornaments without changing cameras."""
    try:
        model_panels = cmds.getPanel(type="modelPanel") or []
    except RuntimeError:
        model_panels = []
    for panel in model_panels:
        try:
            cmds.modelEditor(panel, edit=True, headsUpDisplay=True)
        except RuntimeError:
            pass


def _sync_demo_guide_huds(cmds, guide_state):
    """Keep only a compact stage line and optional one-line viewport hint."""
    _remove_demo_guide_huds(cmds, LEGACY_DEMO_GUIDE_HUDS)
    if not guide_state.get("enabled"):
        _remove_demo_guide_huds(cmds)
        guide_state["hud_names"] = []
        return []

    panel_data = guide_state["panel_data"]
    created = [
        _upsert_demo_guide_hud(
            cmds,
            DEMO_GUIDE_HUDS["summary"],
            0,
            0,
            panel_data["hud_summary"],
            font_size="large",
            block_size="medium",
            label_width=500,
        ),
    ]

    if guide_state.get("show_stage_hint"):
        created.append(_upsert_demo_guide_hud(
            cmds,
            DEMO_GUIDE_HUDS["hint"],
            0,
            1,
            panel_data["hint"],
            font_size="small",
            block_size="small",
            label_width=500,
        ))
    else:
        _remove_demo_guide_huds(cmds, (DEMO_GUIDE_HUDS["hint"],))

    _enable_demo_guide_in_model_panels(cmds)
    guide_state["hud_names"] = created
    return created


def _write_demo_guide_group_state(cmds, guide_state):
    """Mirror current HUD copy onto named Maya groups for inspection/testing."""
    groups = guide_state.get("groups", {})
    text = guide_state["text"]
    guide_group = groups.get("guide")
    stage_group = groups.get("stage_indicator")
    legend_group = groups.get("legend")
    hint_group = groups.get("stage_hint")

    _set_demo_guide_attribute(
        cmds, guide_group, "guideEnabled", guide_state["enabled"], "bool"
    )
    _set_demo_guide_attribute(
        cmds, guide_group, "legendVisible", guide_state["show_legend"], "bool"
    )
    _set_demo_guide_attribute(
        cmds,
        guide_group,
        "stageHintVisible",
        guide_state["show_stage_hint"],
        "bool",
    )
    _set_demo_guide_attribute(
        cmds,
        guide_group,
        "playblastNote",
        "Enable Show Ornaments so Maya HUD text appears in playblast.",
        "string",
    )
    _set_demo_guide_attribute(
        cmds, stage_group, "currentStage", int(text["stage"]), "long"
    )
    _set_demo_guide_attribute(
        cmds, stage_group, "stageTitle", text["title"], "string"
    )
    _set_demo_guide_attribute(
        cmds,
        stage_group,
        "stageDescription",
        text["description"],
        "string",
    )
    _set_demo_guide_attribute(
        cmds,
        legend_group,
        "legendText",
        " || ".join(DEMO_GUIDE_LEGEND_LINES),
        "string",
    )
    _set_demo_guide_attribute(
        cmds, hint_group, "stageHint", text["hint"], "string"
    )
    _set_demo_guide_attribute(
        cmds, hint_group, "stageFocus", text["focus"], "string"
    )


def clear_demo_guide():
    """Remove guide HUD entries and lifecycle groups without touching the scene."""
    import maya.cmds as cmds

    _remove_demo_guide_huds(cmds)
    if cmds.objExists(DEMO_GUIDE_GROUP):
        cmds.delete(DEMO_GUIDE_GROUP)


def create_demo_guide(
    scene_data,
    stage=0,
    enabled=True,
    show_legend=True,
    show_stage_hint=True,
):
    """Create one lightweight HUD guide and its named lifecycle groups."""
    import maya.cmds as cmds

    clear_demo_guide()
    safe_stage = max(0, min(7, int(stage)))
    guide_state = {
        "enabled": bool(enabled),
        "show_legend": bool(show_legend),
        "show_stage_hint": bool(show_stage_hint),
        "stage": safe_stage,
        "text": build_demo_guide_text(scene_data, safe_stage),
        "panel_data": build_demo_guide_panel_data(scene_data, safe_stage),
        "groups": {},
        "hud_names": [],
        "viewport_overlay": "maya_heads_up_display",
        "playblast_requires_show_ornaments": True,
    }
    scene_data["demo_guide"] = guide_state
    if not guide_state["enabled"]:
        return guide_state

    guide_group = cmds.group(empty=True, name=DEMO_GUIDE_GROUP)
    stage_group = cmds.group(empty=True, name=DEMO_GUIDE_STAGE_GROUP)
    legend_group = cmds.group(empty=True, name=DEMO_GUIDE_LEGEND_GROUP)
    hint_group = cmds.group(empty=True, name=DEMO_GUIDE_HINT_GROUP)
    cmds.parent(stage_group, legend_group, hint_group, guide_group)
    if cmds.objExists(ROOT_GROUP):
        parented = cmds.parent(guide_group, ROOT_GROUP)
        if parented:
            guide_group = parented[0]

    guide_state["groups"] = {
        "guide": DEMO_GUIDE_GROUP,
        "stage_indicator": DEMO_GUIDE_STAGE_GROUP,
        "legend": DEMO_GUIDE_LEGEND_GROUP,
        "stage_hint": DEMO_GUIDE_HINT_GROUP,
    }
    _write_demo_guide_group_state(cmds, guide_state)
    _sync_demo_guide_huds(cmds, guide_state)
    return guide_state


def update_demo_guide(
    scene_data,
    stage=None,
    enabled=None,
    show_legend=None,
    show_stage_hint=None,
):
    """Update guide copy and visibility for one stage without rebuilding Maya."""
    import maya.cmds as cmds

    if scene_data is None:
        clear_demo_guide()
        return None

    prior_state = scene_data.get("demo_guide") or {}
    visual_params = scene_data.get("parameters", {}).get("visual", {})
    safe_stage = max(
        0,
        min(
            7,
            int(
                scene_data.get("demo_stage", 0)
                if stage is None
                else stage
            ),
        ),
    )
    resolved_enabled = bool(
        visual_params.get("show_demo_guide", True)
        if enabled is None
        else enabled
    )
    resolved_legend = bool(
        prior_state.get(
            "show_legend",
            visual_params.get("show_demo_legend", True),
        )
        if show_legend is None
        else show_legend
    )
    resolved_hint = bool(
        prior_state.get(
            "show_stage_hint",
            visual_params.get("show_demo_stage_hint", True),
        )
        if show_stage_hint is None
        else show_stage_hint
    )

    if not resolved_enabled:
        clear_demo_guide()
        guide_state = {
            "enabled": False,
            "show_legend": resolved_legend,
            "show_stage_hint": resolved_hint,
            "stage": safe_stage,
            "text": build_demo_guide_text(scene_data, safe_stage),
            "panel_data": build_demo_guide_panel_data(scene_data, safe_stage),
            "groups": {},
            "hud_names": [],
            "viewport_overlay": "maya_heads_up_display",
            "playblast_requires_show_ornaments": True,
        }
        scene_data["demo_guide"] = guide_state
        return guide_state

    if not cmds.objExists(DEMO_GUIDE_GROUP):
        return create_demo_guide(
            scene_data,
            stage=safe_stage,
            enabled=True,
            show_legend=resolved_legend,
            show_stage_hint=resolved_hint,
        )

    prior_state.update({
        "enabled": True,
        "show_legend": resolved_legend,
        "show_stage_hint": resolved_hint,
        "stage": safe_stage,
        "text": build_demo_guide_text(scene_data, safe_stage),
        "panel_data": build_demo_guide_panel_data(scene_data, safe_stage),
        "viewport_overlay": "maya_heads_up_display",
        "playblast_requires_show_ornaments": True,
    })
    prior_state.setdefault("groups", {
        "guide": DEMO_GUIDE_GROUP,
        "stage_indicator": DEMO_GUIDE_STAGE_GROUP,
        "legend": DEMO_GUIDE_LEGEND_GROUP,
        "stage_hint": DEMO_GUIDE_HINT_GROUP,
    })
    _write_demo_guide_group_state(cmds, prior_state)
    _sync_demo_guide_huds(cmds, prior_state)
    scene_data["demo_guide"] = prior_state
    return prior_state


def create_maya_scene(config=None, prior_cell_state=None):
    """Create the first Maya visualization MVP for Cloud-Hive Meadow.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so this module can still be compiled and imported outside Autodesk Maya.

    Parameters:
        config (dict | None): Optional integration parameter dictionary. When
            None, defaults are loaded from code/config.py through main.py.

    Returns:
        dict: Dictionary containing cells, clouds, drops, tasks, bees, and summary.
    """
    import maya.cmds as cmds

    parameters = config or load_parameters()
    simulation = run_simulation(parameters, prior_cell_state=prior_cell_state)

    cells = simulation["cells"]
    clouds = simulation["clouds"]
    drops = simulation["drops"]
    tasks = simulation["tasks"]
    bees = simulation["bees"]

    overview_camera_existed = _find_camera_rig_node(cmds, "camera")[0] is not None
    clear_scene(preserve_camera=True)
    cmds.group(empty=True, name=ROOT_GROUP)

    visual_params = parameters.get("visual", {})
    hive_params = parameters["hive"]
    cloud_params = parameters["clouds"]

    ground_radius = visual_params.get(
        "ground_radius",
        max(cloud_params["scene_radius"] * 1.8, hive_params["size"] * hive_params["cell_size"] * 3.0),
    )
    cell_depth = visual_params.get("cell_depth", 0.35)
    voxel_density = int(visual_params.get("voxel_density", 14))
    cloud_scale = visual_params.get("cloud_scale", 0.85)
    flowers_per_cloud = visual_params.get("flowers_per_cloud", 5)
    bee_scale = visual_params.get("bee_scale", 1.0)
    show_paths = visual_params.get("show_paths", True)
    show_demo_guide = visual_params.get("show_demo_guide", True)
    show_demo_legend = visual_params.get("show_demo_legend", True)
    show_demo_stage_hint = visual_params.get(
        "show_demo_stage_hint",
        True,
    )
    demo_max_active_bees = visual_params.get(
        "demo_max_active_bees",
        DEFAULT_DEMO_MAX_ACTIVE_BEES,
    )
    create_honeycomb_geometry(
        cells,
        hive_params["cell_size"],
        cell_depth,
        voxel_density=voxel_density,
        seed=hive_params.get("seed", 42),
    )
    generated_pitch = next(
        (cell.get("voxel_pitch") for cell in cells if cell.get("voxel_pitch")),
        None,
    )
    if generated_pitch:
        voxel_density = int(round(float(hive_params["cell_size"]) / generated_pitch))
    create_cloud_geometry(
        clouds,
        cloud_scale=cloud_scale,
        voxel_pitch=generated_pitch,
    )
    create_flower_geometry_on_clouds(clouds, flowers_per_cloud=flowers_per_cloud)
    create_drop_particles(drops)
    frame_duration_multiplier = max(
        0.01,
        float(visual_params.get("frame_duration_multiplier", 4.0)),
    )
    animation_end = int(visual_params.get("animation_end", 320) * frame_duration_multiplier)
    drop_fall_frames = int(visual_params.get("drop_fall_frames", 64) * frame_duration_multiplier)
    bee_frame_step = int(visual_params.get("bee_frame_step", 22) * frame_duration_multiplier)
    scheduled_end = schedule_task_animation(
        bees,
        tasks,
        drops,
        cells,
        clouds,
        fall_duration=drop_fall_frames,
        frame_step=bee_frame_step,
        start_frame=LEGACY_ANIMATION_START,
    )
    stage_one_start, stage_one_end = DEMO_STAGE_BASE_RANGES[1]
    for drop_index, drop in enumerate(drops):
        drop.setdefault(
            "animation_start_frame",
            stage_one_start + (drop_index % 6) * 2,
        )
        drop.setdefault(
            "animation_end_frame",
            stage_one_end - ((len(drops) - drop_index - 1) % 4),
        )
    animation_end = max(animation_end, scheduled_end)
    # The compact Stage 1 transition uses the existing landing markers. Keep
    # the legacy falling group present for stable group bookkeeping without
    # authoring a second long drop animation that the demo no longer plays.
    _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["falling_drops"])
    create_bee_geometry(bees, bee_scale=bee_scale)
    bee_base_transforms = {
        bee["id"]: list(
            cmds.xform(
                bee["maya_object"],
                query=True,
                translation=True,
                worldSpace=True,
            )
        )
        for bee in bees
        if bee.get("maya_object") and cmds.objExists(bee["maya_object"])
    }
    visual_bees = [
        bee
        for bee in bees
        if bee.get("maya_object") and cmds.objExists(bee["maya_object"])
    ]
    transport_assignments, secondary_transport_tasks = (
        select_demo_transport_assignments(
            visual_bees,
            tasks,
            demo_max_active_bees,
        )
    )
    path_visuals = []
    if show_paths:
        path_visuals = create_task_path_visuals(tasks, cells)
    path_visual_layers = style_demo_transport_paths(
        tasks,
        transport_assignments,
    )
    animation_records = animate_assigned_bees(
        bees,
        tasks,
        cells,
        clouds,
        drops,
        frame_step=bee_frame_step,
    )
    resource_visuals = create_cell_resource_visuals(
        cells,
        drops,
        simulation["resource_events"],
        animation_records,
        cell_size=hive_params["cell_size"],
        cell_depth=cell_depth,
        voxel_density=voxel_density,
    )
    blocked_visuals = create_blocked_task_visuals(
        tasks,
        cells,
        animation_end=animation_end,
    )
    drop_demo_visuals = create_drop_demo_visuals(
        drops,
        tasks,
        cells,
        cell_size=hive_params["cell_size"],
    )
    transport_demo = create_bee_task_selection_visuals(
        bees,
        tasks,
        cells,
        transport_assignments,
        cell_size=hive_params["cell_size"],
    )
    transport_demo.update(path_visual_layers)
    transport_demo["secondary_tasks"] = secondary_transport_tasks
    bee_selection_visuals = transport_demo["all_markers"]
    collection_tasks, collection_check = create_collection_demo_tasks(
        cells,
        clouds,
        bees,
        parameters,
        bee_base_transforms=bee_base_transforms,
    )
    collection_visuals = create_collection_demo_visuals(
        collection_tasks,
        bees,
        cells,
        frame_start=DEMO_COLLECTION_START,
        frame_step=DEMO_COLLECTION_FRAME_STEP,
    )
    collection_check["active_task_count"] = sum(
        bool(task.get("demo_active")) for task in collection_tasks
    )
    collection_check["queued_task_count"] = (
        len(collection_tasks) - collection_check["active_task_count"]
    )
    deposit_visuals = create_deposit_update_visuals(
        cells,
        simulation["resource_events"],
        cell_size=hive_params["cell_size"],
        collection_tasks=collection_tasks,
    )
    collection_end = max(
        (task.get("animation_end_frame", 1) for task in collection_tasks),
        default=DEMO_COLLECTION_START + 48,
    )
    stage_six_end = max(DEMO_COLLECTION_START + 48, int(collection_end))
    stage_seven_start = stage_six_end + 12
    stage_seven_end = stage_seven_start + 40
    playback_ranges = dict(DEMO_STAGE_BASE_RANGES)
    playback_ranges.update({
        6: (DEMO_COLLECTION_START, stage_six_end),
        7: (stage_seven_start, stage_seven_end),
    })
    stage_frames = {
        stage: frame_range[0]
        for stage, frame_range in playback_ranges.items()
    }
    transition_visuals = author_demo_stage_transitions(
        drops=drops,
        clouds=clouds,
        cells=cells,
        resource_events=simulation["resource_events"],
        bees=bees,
        tasks=tasks,
        bee_base_transforms=bee_base_transforms,
        path_visuals=path_visuals,
        blocked_visuals=blocked_visuals,
        drop_demo_visuals=drop_demo_visuals,
        bee_selection_visuals=bee_selection_visuals,
        transport_demo=transport_demo,
        collection_tasks=collection_tasks,
        deposit_visuals=deposit_visuals,
        stage_ranges=playback_ranges,
        cell_depth=cell_depth,
    )
    natural_worker_frame = max(
        (max(record["frames"]) for record in animation_records if record["frames"]),
        default=LEGACY_ANIMATION_START,
    )
    full_animation_end = max(
        animation_end,
        natural_worker_frame + 5,
        stage_seven_end + 5,
    )
    cmds.playbackOptions(
        animationStartTime=1,
        animationEndTime=full_animation_end,
        maxTime=full_animation_end,
    )
    cycle_group = organize_demo_cycle_groups(simulation["summary"]["cycle_number"])
    camera_setup = setup_camera_and_lighting(ground_radius)
    frame_scene_overview(
        camera_setup["camera"],
        fallback_radius=ground_radius,
    )
    render_background = None
    if visual_params.get("render_background", True):
        render_background = create_render_background(
            camera_setup["camera"],
            camera_setup["camera_shape"],
            scene_radius=ground_radius,
        )
    _parent_known_scene_groups(additional_groups=[cycle_group])

    scene_data = {
        "parameters": copy.deepcopy(parameters),
        "cells": cells,
        "clouds": clouds,
        "drops": drops,
        "tasks": tasks,
        "bees": bees,
        "summary": simulation["summary"],
        "completed_tasks": simulation["completed_tasks"],
        "animation_records": animation_records,
        "resource_events": simulation["resource_events"],
        "resource_visuals": resource_visuals,
        "blocked_visuals": blocked_visuals,
        "drop_demo_visuals": drop_demo_visuals,
        "bee_selection_visuals": bee_selection_visuals,
        "transport_demo": transport_demo,
        "active_transport_bee_count": len(transport_assignments),
        "collection_tasks": collection_tasks,
        "active_collection_bee_count": sum(
            bool(task.get("demo_active")) for task in collection_tasks
        ),
        "collection_check": collection_check,
        "collection_visuals": collection_visuals,
        "deposit_visuals": deposit_visuals,
        "transition_visuals": transition_visuals,
        "demo_visual_groups": dict(DEMO_VISUAL_GROUPS),
        "demo_cycle_group": cycle_group,
        "demo_stage_frames": stage_frames,
        "demo_stage_end_frames": {
            stage: frame_range[1]
            for stage, frame_range in playback_ranges.items()
        },
        "demo_playback_ranges": playback_ranges,
        "animation_full_range": (1, full_animation_end),
        "demo_stage": 0,
        "camera_setup": camera_setup,
        "render_background": render_background,
    }
    scene_data["demo_guide"] = create_demo_guide(
        scene_data,
        stage=0,
        enabled=show_demo_guide,
        show_legend=show_demo_legend,
        show_stage_hint=show_demo_stage_hint,
    )
    apply_demo_stage(scene_data, 0)

    # A first Generate should present the deliberately wide overview. Later
    # rebuilds preserve whichever viewport camera the user selected.
    if not overview_camera_existed and not cmds.about(batch=True):
        try:
            cmds.lookThru(camera_setup["camera"])
        except RuntimeError:
            pass

    print("Cloud-Hive Bloomfield Maya visualization created.")
    print("Cells: {0}, Clouds: {1}, Drops: {2}, Tasks: {3}, Bees: {4}".format(
        len(cells),
        len(clouds),
        len(drops),
        len(tasks),
        len(bees),
    ))

    return scene_data


def schedule_task_animation(
    bees,
    tasks,
    drops,
    cells,
    clouds,
    fall_duration=64,
    frame_step=22,
    start_frame=1,
):
    """Plan continuous bee queues at one constant world-space speed.

    The optional start frame keeps the full worker animation outside the compact
    seven-stage presentation timeline. Path-only carryover tasks use the same
    route planner and always receive a numeric delivery frame.
    """
    task_by_id = {task["id"]: task for task in tasks}
    drop_by_id = {drop["id"]: drop for drop in drops}
    safe_start = max(1, int(start_frame))
    latest_frame = safe_start
    frames_per_unit = calculate_bee_frames_per_unit(
        tasks,
        cells,
        frame_step=frame_step,
    )

    for bee_index, bee in enumerate(bees):
        lane_offset = (
            bee_index - (len(bees) - 1) * 0.5
        ) * 0.55
        initial_x, initial_y, initial_z = bee.get("position", [0.0, 0.8, 0.0])
        current_position = (
            initial_x + lane_offset,
            initial_y,
            initial_z,
        )
        bee["animation_start_position"] = list(current_position)
        cursor = safe_start + bee_index * 6
        for task_id in bee.get("task_queue", []):
            task = task_by_id.get(task_id)
            if task is None or not task.get("path"):
                continue
            drop_id = task_id[5:] if task_id.startswith("task_") else task_id
            drop = drop_by_id.get(drop_id)
            plan = plan_bee_collection_cycle(
                bee,
                task,
                cells,
                clouds,
                drops,
                start_position=current_position,
                frame_start=cursor,
                frames_per_unit=frames_per_unit,
                fall_duration=fall_duration,
                lane_offset=lane_offset,
            )
            if not plan:
                continue
            task["animation_plan"] = plan
            task["animation_frame_start"] = plan["frames"][0]
            task["planned_delivery_frame"] = plan["frames"][
                plan["delivery_waypoint_index"]
            ]
            task["delivery_frame"] = int(task["planned_delivery_frame"])
            if drop is not None and plan.get("drop_start_frame") is not None:
                drop["animation_start_frame"] = plan["drop_start_frame"]
            if drop is not None and plan.get("drop_end_frame") is not None:
                drop["animation_end_frame"] = plan["drop_end_frame"]
            current_position = plan["end_position"]
            # A short stationary beat separates jobs without teleporting or
            # returning the worker to a shared origin.
            cursor = plan["frames"][-1] + max(3, int(round(frame_step * 0.25)))
            latest_frame = max(latest_frame, cursor)

        bee["animation_end_position"] = list(current_position)

    return latest_frame


def animate_assigned_bees(bees, tasks, cells, clouds, drops, frame_step=22):
    """Animate every queued task as one continuous per-worker flight chain."""
    task_by_id = {task["id"]: task for task in tasks}
    records = []
    for index, bee in enumerate(bees):
        for task_id in bee.get("task_queue", []):
            task = task_by_id.get(task_id)
            if task is None or not task.get("path"):
                continue
            frames = animate_bee_collection_cycle(
                bee,
                task,
                cells,
                clouds,
                drops,
                frame_start=task.get("animation_frame_start", 1 + index * 5),
                frame_step=frame_step,
                bee_index=index,
            )
            records.append({
                "bee_id": bee["id"],
                "task_id": task["id"],
                "bfs_path": list(task["path"]),
                "frames": frames,
                "pickup_frame": task.get("pickup_frame"),
                "delivery_frame": task.get("delivery_frame"),
            })
    return records


def create_collection_demo_tasks(
    cells,
    clouds,
    bees,
    parameters,
    bee_base_transforms=None,
):
    """Create shortage-driven collection-ready records without mutating storage.

    These records drive the explanatory Stage 5/6 visuals. Natural drops and
    capacity-aware deposits remain owned by the existing pure simulation.
    """
    resource_params = parameters.get("resources", {})
    thresholds = resource_params.get("collection_thresholds", {})
    collection_amount = max(0.0, float(resource_params.get("collection_amount", 0.4)))
    totals = {
        "nectar": sum(float(cell.get("nectar", 0.0)) for cell in cells),
        "pollen": sum(float(cell.get("pollen", 0.0)) for cell in cells),
    }
    normalized_thresholds = {
        "nectar": max(0.0, float(thresholds.get("nectar", 0.0))),
        "pollen": max(0.0, float(thresholds.get("pollen", 0.0))),
    }
    check = {
        "totals": totals,
        "thresholds": normalized_thresholds,
        "needed_resources": [],
        "presentation_resource": None,
        "active_task_count": 0,
        "queued_task_count": 0,
    }

    traversable_cells = [
        cell
        for cell in cells
        if not cell.get("is_blocked")
        and cell.get("type") not in ("queen", "queen_reserved", "capped")
    ]
    if not traversable_cells or not clouds:
        return [], check

    cycle_number = int(parameters.get("simulation", {}).get("cycle", 0))
    tasks = []
    resource_types = ("nectar", "pollen")
    needed_resources = [
        resource_type
        for resource_type in resource_types
        if totals[resource_type] + 0.000001
        < normalized_thresholds[resource_type]
    ]
    presentation_only = not needed_resources
    if presentation_only:
        def reserve_ratio(resource_type):
            threshold = max(0.000001, normalized_thresholds[resource_type])
            return totals[resource_type] / threshold

        planned_resources = [min(resource_types, key=reserve_ratio)]
        check["presentation_resource"] = planned_resources[0]
    else:
        planned_resources = needed_resources
        check["needed_resources"] = list(needed_resources)

    max_active_bees = parameters.get("visual", {}).get(
        "demo_max_active_bees",
        DEFAULT_DEMO_MAX_ACTIVE_BEES,
    )
    active_limit = _resolve_demo_active_bee_limit(
        len(planned_resources),
        len(bees),
        max_active_bees,
    )
    base_transforms = bee_base_transforms or {}

    for task_index, resource_type in enumerate(planned_resources):
        resource_index = resource_types.index(resource_type)
        total = totals[resource_type]
        threshold = normalized_thresholds[resource_type]

        active_task_index = len(tasks)
        demo_active = active_task_index < active_limit
        assigned_bee = bees[active_task_index] if demo_active else None
        bee_start = (
            base_transforms.get(
                assigned_bee.get("id"),
                assigned_bee.get("position", [0.0, 0.8, 0.0]),
            )
            if assigned_bee
            else [0.0, 0.8, 0.0]
        )
        start_cell = min(
            traversable_cells,
            key=lambda cell: _horizontal_distance_squared(
                cell["position"], bee_start
            ),
        )
        reachable_paths = _reachable_hive_paths(start_cell["id"], cells)
        reachable_cells = [
            cell for cell in traversable_cells if cell["id"] in reachable_paths
        ]
        if not reachable_cells:
            continue

        cloud = clouds[resource_index % len(clouds)]
        base_cell = min(
            reachable_cells,
            key=lambda cell: _horizontal_distance_squared(
                cell["position"], cloud["position"]
            ),
        )
        resource_points = cloud.get("resource_points") or [cloud["position"]]
        resource_point = resource_points[resource_index % len(resource_points)]
        flower_position = [
            float(resource_point[0]),
            float(cloud["position"][1]) + 0.80,
            float(resource_point[2]),
        ]
        shortage = max(0.0, threshold - total)
        cloud_available = max(
            0.0,
            float(cloud.get("{0}_amount".format(resource_type), collection_amount)),
        )
        requested_amount = collection_amount if presentation_only else shortage
        amount = min(requested_amount, collection_amount, cloud_available)
        if amount <= 0.000001:
            continue

        task = {
            "id": "task_{0}_cycle_{1}_{2}".format(
                "collection_demo" if presentation_only else "collection",
                cycle_number,
                resource_type,
            ),
            "type": "collect_{0}".format(resource_type),
            "origin": "collection_demo" if presentation_only else "collection",
            "presentation_only": presentation_only,
            "resource_type": resource_type,
            "amount": amount,
            "shortage": shortage,
            "source_cloud": cloud["id"],
            "assigned_bee_id": assigned_bee.get("id") if assigned_bee else None,
            "demo_active": demo_active,
            "demo_queue_state": "active" if demo_active else "queued",
            "target_flower_position": flower_position,
            "hive_start_cell": start_cell["id"],
            "cloud_base_cell": base_cell["id"],
            "path": list(reachable_paths[base_cell["id"]]),
            "movement_modes": ["on_hive", "cloud_flight", "on_hive_reentry"],
            "status": "collection_ready",
        }
        tasks.append(task)

    check["active_task_count"] = sum(
        bool(task.get("demo_active")) for task in tasks
    )
    check["queued_task_count"] = len(tasks) - check["active_task_count"]
    return tasks, check


def _horizontal_distance_squared(first, second):
    """Return squared XZ distance between two 3D points."""
    delta_x = float(first[0]) - float(second[0])
    delta_z = float(first[2]) - float(second[2])
    return delta_x * delta_x + delta_z * delta_z


def _reachable_hive_paths(start_cell_id, cells):
    """Return shortest on-hive paths from one traversable start cell."""
    cell_by_id = {cell["id"]: cell for cell in cells}
    start_cell = cell_by_id.get(start_cell_id)
    if start_cell is None or start_cell.get("is_blocked"):
        return {}

    paths = {start_cell_id: [start_cell_id]}
    queue = [start_cell_id]
    while queue:
        cell_id = queue.pop(0)
        for neighbor_id in cell_by_id[cell_id].get("neighbors", []):
            if neighbor_id in paths:
                continue
            neighbor = cell_by_id.get(neighbor_id)
            if neighbor is None or neighbor.get("is_blocked"):
                continue
            paths[neighbor_id] = paths[cell_id] + [neighbor_id]
            queue.append(neighbor_id)
    return paths


def _sample_demo_points(points, max_points=6):
    """Keep endpoints while reducing a long path to a readable preview."""
    safe_points = list(points)
    limit = max(2, int(max_points))
    if len(safe_points) <= limit:
        return safe_points
    last_index = len(safe_points) - 1
    indices = sorted({
        int(round(step * last_index / float(limit - 1)))
        for step in range(limit)
    })
    return [safe_points[index] for index in indices]


def create_drop_demo_visuals(drops, tasks, cells, cell_size):
    """Create static mapping, validation, and outcome layers for one cycle."""
    import maya.cmds as cmds

    mapping_group = _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["mapping"])
    validation_group = _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["validation"])
    direct_group = _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["direct_storage"])
    task_group = _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["task_markers"])

    validation_materials = {
        "matched": _create_maya_material(
            cmds, "chm_demo_validation_green_MAT", (0.12, 1.0, 0.30)
        ),
        "mismatched": _create_maya_material(
            cmds, "chm_demo_validation_orange_MAT", (1.0, 0.42, 0.04)
        ),
        "blocked": _create_maya_material(
            cmds, "chm_demo_validation_red_MAT", (1.0, 0.04, 0.10)
        ),
        "unmapped": _create_maya_material(
            cmds, "chm_demo_validation_gray_MAT", (0.45, 0.45, 0.50)
        ),
    }
    direct_material = _create_maya_material(
        cmds, "chm_demo_direct_storage_gold_MAT", (1.0, 0.82, 0.08)
    )
    transport_material = _create_maya_material(
        cmds, "chm_demo_transport_task_blue_MAT", (0.10, 0.42, 1.0)
    )
    cleanup_material = _create_maya_material(
        cmds, "chm_demo_cleanup_task_red_MAT", (1.0, 0.05, 0.05)
    )

    cell_by_id = {cell["id"]: cell for cell in cells}
    task_by_id = {task["id"]: task for task in tasks}
    created = {
        "mapping": [],
        "validation": [],
        "direct_storage": [],
        "task_markers": [],
        "outcomes": [],
    }
    for index, drop in enumerate(drops):
        cell = cell_by_id.get(drop.get("mapped_cell_id"))
        if cell is None:
            continue
        drop_x, drop_y, drop_z = drop["position"]
        cell_x, cell_y, cell_z = cell["position"]
        mapping_curve = cmds.curve(
            degree=1,
            point=[
                (drop_x, drop_y + 0.34, drop_z),
                (cell_x, cell_y + 0.62, cell_z),
            ],
            name="CloudHive_mapping_{0:03d}_CRV".format(index),
        )
        cmds.parent(mapping_curve, mapping_group)
        _style_demo_curve(cmds, mapping_curve, (0.10, 0.78, 1.0), line_width=3)
        created["mapping"].append(mapping_curve)

        validation = drop.get("validation_result", "unmapped")
        highlight, _shape = cmds.polyCylinder(
            radius=float(cell_size) * 0.76,
            height=0.055,
            subdivisionsX=6,
            name="CloudHive_validation_{0:03d}".format(index),
        )
        cmds.xform(
            highlight,
            translation=(cell_x, cell_y + 0.57, cell_z),
            rotation=(0.0, 30.0, 0.0),
            worldSpace=True,
        )
        cmds.parent(highlight, validation_group)
        _assign_maya_material(
            cmds,
            highlight,
            validation_materials.get(validation, validation_materials["unmapped"]),
        )
        created["validation"].append(highlight)

        direct_amount = float(drop.get("direct_storage_amount", 0.0))
        if direct_amount > 0.000001:
            direct_marker, _shape = cmds.polyCylinder(
                radius=float(cell_size) * 0.30,
                height=0.16,
                subdivisionsX=6,
                name="CloudHive_direct_storage_{0:03d}".format(index),
            )
            cmds.xform(
                direct_marker,
                translation=(cell_x, cell_y + 0.78, cell_z),
                rotation=(0.0, 30.0, 0.0),
                worldSpace=True,
            )
            cmds.parent(direct_marker, direct_group)
            _assign_maya_material(cmds, direct_marker, direct_material)
            created["direct_storage"].append(direct_marker)

        task = task_by_id.get(drop.get("task_id"))
        if task is not None:
            cleanup = task.get("type") == "clean_blocked"
            task_marker, _shape = cmds.polyCube(
                width=0.24 if cleanup else 0.20,
                height=0.62 if cleanup else 0.42,
                depth=0.24 if cleanup else 0.20,
                name="CloudHive_{0}_task_{1:03d}".format(
                    "cleanup" if cleanup else "transport",
                    index,
                ),
            )
            cmds.xform(
                task_marker,
                translation=(cell_x, cell_y + 0.92, cell_z),
                rotation=(0.0, 45.0 if cleanup else 0.0, 0.0),
                worldSpace=True,
            )
            cmds.parent(task_marker, task_group)
            _assign_maya_material(
                cmds,
                task_marker,
                cleanup_material if cleanup else transport_material,
            )
            created["task_markers"].append(task_marker)

        created["outcomes"].append({
            "drop_id": drop.get("id"),
            "cell_id": cell.get("id"),
            "validation": validation,
            "direct_storage_amount": direct_amount,
            "task_id": task.get("id") if task else None,
            "task_type": task.get("type") if task else None,
        })

    return created


def create_collection_demo_visuals(collection_tasks, bees, cells, frame_start, frame_step):
    """Create distinct shortage triggers and unique multi-bee collection routes."""
    import maya.cmds as cmds

    trigger_group = _replace_empty_group(
        cmds, DEMO_VISUAL_GROUPS["collection_triggers"]
    )
    visual_group = _replace_empty_group(
        cmds, DEMO_VISUAL_GROUPS["collection_visuals"]
    )
    nectar_material = _create_maya_material(
        cmds, "chm_demo_collection_nectar_MAT", (1.0, 0.72, 0.05)
    )
    pollen_material = _create_maya_material(
        cmds, "chm_demo_collection_pollen_MAT", (0.72, 0.20, 1.0)
    )
    pollen_grain_material = _create_maya_material(
        cmds, "chm_demo_collection_pollen_grain_MAT", (1.0, 0.30, 0.05)
    )
    queued_nectar_material = _create_maya_material(
        cmds, "chm_demo_collection_queued_nectar_MAT", (0.48, 0.36, 0.16)
    )
    queued_pollen_material = _create_maya_material(
        cmds, "chm_demo_collection_queued_pollen_MAT", (0.38, 0.26, 0.46)
    )
    cell_by_id = {cell["id"]: cell for cell in cells}
    created = []
    bee_by_id = {bee.get("id"): bee for bee in bees}
    base_cursor = max(1, int(frame_start))
    safe_step = max(1, int(frame_step))
    active_index = 0
    used_bee_ids = set()

    for index, task in enumerate(collection_tasks):
        resource_type = task.get("resource_type", "nectar")
        active_resource_material = (
            nectar_material if resource_type == "nectar" else pollen_material
        )
        queued_resource_material = (
            queued_nectar_material
            if resource_type == "nectar"
            else queued_pollen_material
        )
        assigned_bee_id = task.get("assigned_bee_id")
        bee = bee_by_id.get(assigned_bee_id)
        bee_object = bee.get("maya_object") if bee else None
        is_active = bool(
            task.get("demo_active")
            and assigned_bee_id
            and assigned_bee_id not in used_bee_ids
            and bee_object
            and cmds.objExists(bee_object)
        )
        if not is_active:
            task["demo_active"] = False
            task["demo_queue_state"] = "queued"
            task["assigned_bee_id"] = None
            bee = None
            bee_object = None
        resource_material = (
            active_resource_material if is_active else queued_resource_material
        )
        flower_position = tuple(task["target_flower_position"])
        if resource_type == "nectar":
            trigger, _shape = cmds.polySphere(
                radius=0.28 if is_active else 0.19,
                name="CloudHive_nectar_collection_trigger_{0:02d}".format(index),
            )
            cmds.setAttr(trigger + ".scaleX", 0.72)
            cmds.setAttr(trigger + ".scaleY", 1.28)
            cmds.setAttr(trigger + ".scaleZ", 0.72)
        else:
            trigger, _shape = cmds.polyCube(
                width=0.34 if is_active else 0.22,
                height=0.34 if is_active else 0.22,
                depth=0.34 if is_active else 0.22,
                name="CloudHive_pollen_collection_trigger_{0:02d}".format(index),
            )
            cmds.xform(trigger, rotation=(18.0, 45.0, 18.0), worldSpace=True)
        cmds.xform(trigger, translation=flower_position, worldSpace=True)
        cmds.parent(trigger, trigger_group)
        _assign_maya_material(cmds, trigger, resource_material)
        created.append(trigger)

        halo, _shape = cmds.polyCylinder(
            radius=0.48 if is_active else 0.32,
            height=0.045,
            subdivisionsX=18,
            name="CloudHive_collection_shortage_halo_{0:02d}".format(index),
        )
        cmds.xform(
            halo,
            translation=(flower_position[0], flower_position[1] - 0.16, flower_position[2]),
            worldSpace=True,
        )
        cmds.parent(halo, trigger_group)
        _assign_maya_material(cmds, halo, resource_material)
        created.append(halo)

        base_cell = cell_by_id.get(task.get("cloud_base_cell"))
        if base_cell is not None:
            base_x, base_y, base_z = base_cell["position"]
            task_marker, _shape = cmds.polyCube(
                width=0.24 if is_active else 0.16,
                height=0.62 if is_active else 0.34,
                depth=0.24 if is_active else 0.16,
                name="CloudHive_collection_task_marker_{0:02d}".format(index),
            )
            cmds.xform(
                task_marker,
                translation=(base_x, base_y + 0.92, base_z),
                worldSpace=True,
            )
            cmds.parent(task_marker, trigger_group)
            _assign_maya_material(cmds, task_marker, resource_material)
            created.append(task_marker)

        task["trigger_visuals"] = [
            node
            for node in (trigger, halo, task_marker if base_cell is not None else None)
            if node
        ]
        task["visual_state"] = "active" if is_active else "queued"
        if not is_active:
            continue

        used_bee_ids.add(assigned_bee_id)
        cursor = base_cursor + active_index * max(1, safe_step // 2)
        active_index += 1

        crawl_points = []
        for cell_id in task.get("path", []):
            cell = cell_by_id.get(cell_id)
            if cell is not None:
                x, y, z = cell["position"]
                crawl_points.append((x, y + 0.62, z))
        crawl_points = _sample_demo_points(crawl_points, max_points=6)
        if not crawl_points:
            task["demo_active"] = False
            task["demo_queue_state"] = "queued"
            task["assigned_bee_id"] = None
            used_bee_ids.discard(assigned_bee_id)
            continue

        if len(crawl_points) > 1:
            crawl_curve = cmds.curve(
                degree=1,
                point=crawl_points,
                name="CloudHive_collection_crawl_{0:02d}_CRV".format(index),
            )
            cmds.parent(crawl_curve, visual_group)
            _style_demo_curve(
                cmds,
                crawl_curve,
                (0.15, 0.95, 0.72),
                line_width=4,
            )
            created.append(crawl_curve)
            task["crawl_curve_object"] = crawl_curve

        hive_position = crawl_points[-1]
        flight_midpoint = (
            (hive_position[0] + flower_position[0]) * 0.5,
            (hive_position[1] + flower_position[1]) * 0.5 + 0.45,
            (hive_position[2] + flower_position[2]) * 0.5,
        )
        flight_curve = cmds.curve(
            degree=1,
            point=[hive_position, flight_midpoint, flower_position],
            name="CloudHive_collection_flight_{0:02d}_CRV".format(index),
        )
        cmds.parent(flight_curve, visual_group)
        _style_demo_curve(
            cmds,
            flight_curve,
            (0.95, 0.30, 1.0),
            line_width=4,
        )
        created.append(flight_curve)
        task["flight_curve_object"] = flight_curve

        bee_bounds = cmds.exactWorldBoundingBox(bee_object)
        selected_marker, _shape = cmds.polyTorus(
            radius=0.42,
            sectionRadius=0.065,
            subdivisionsX=12,
            subdivisionsY=4,
            name="CloudHive_collection_bee_selected_{0:02d}".format(index),
        )
        cmds.xform(
            selected_marker,
            translation=(
                (bee_bounds[0] + bee_bounds[3]) * 0.5,
                bee_bounds[4] + 0.44,
                (bee_bounds[2] + bee_bounds[5]) * 0.5,
            ),
            worldSpace=True,
        )
        cmds.parent(selected_marker, visual_group)
        _assign_maya_material(cmds, selected_marker, active_resource_material)
        cmds.pointConstraint(
            bee_object,
            selected_marker,
            maintainOffset=True,
            name="CloudHive_collection_bee_selected_{0:02d}_pointConstraint".format(
                index
            ),
        )
        created.append(selected_marker)
        task["selected_bee_marker"] = selected_marker

        crawl_frames = [cursor + point_index * safe_step for point_index in range(len(crawl_points))]
        takeoff_frame = crawl_frames[-1]
        midpoint_frame = takeoff_frame + safe_step
        collection_frame = midpoint_frame + safe_step
        return_midpoint_frame = collection_frame + safe_step
        reentry_frame = return_midpoint_frame + safe_step
        task["animation_start_frame"] = crawl_frames[0]
        task["collection_frame"] = collection_frame
        task["reentry_frame"] = reentry_frame
        task["animation_end_frame"] = reentry_frame
        task["frames"] = crawl_frames + [
            midpoint_frame,
            collection_frame,
            return_midpoint_frame,
            reentry_frame,
        ]
        task["crawl_frames"] = list(crawl_frames)
        task["flight_frames"] = [
            takeoff_frame,
            midpoint_frame,
            collection_frame,
            return_midpoint_frame,
            reentry_frame,
        ]
        task["bee_id"] = assigned_bee_id
        task["movement_segments"] = {
            "on_hive": (crawl_frames[0], takeoff_frame),
            "cloud_flight": (takeoff_frame, collection_frame),
            "on_hive_reentry": (collection_frame, reentry_frame),
        }
        keyed_positions = list(zip(crawl_frames, crawl_points)) + [
            (midpoint_frame, flight_midpoint),
            (collection_frame, flower_position),
            (return_midpoint_frame, flight_midpoint),
            (reentry_frame, hive_position),
        ]
        for frame, position in keyed_positions:
            _key_translation(cmds, bee_object, frame, position)
        try:
            cmds.keyTangent(
                bee_object,
                attribute=("translateX", "translateY", "translateZ"),
                time=(crawl_frames[0], reentry_frame),
                inTangentType="linear",
                outTangentType="linear",
            )
        except RuntimeError:
            pass

        if resource_type == "nectar":
            payload, _shape = cmds.polySphere(
                radius=0.13,
                name="CloudHive_nectar_collection_payload_{0:02d}".format(index),
            )
            cmds.setAttr(payload + ".scaleX", 0.72)
            cmds.setAttr(payload + ".scaleY", 1.28)
            cmds.setAttr(payload + ".scaleZ", 0.72)
            _assign_maya_material(cmds, payload, nectar_material)
            task["payload_style"] = "amber_droplet"
        else:
            payload = cmds.group(
                empty=True,
                name="CloudHive_pollen_collection_payload_{0:02d}".format(index),
            )
            grain_offsets = (
                (-0.07, 0.0, 0.0),
                (0.07, 0.0, 0.0),
                (0.0, 0.08, 0.04),
            )
            for grain_index, offset in enumerate(grain_offsets):
                grain, _shape = cmds.polyCube(
                    width=0.10,
                    height=0.10,
                    depth=0.10,
                    name="CloudHive_pollen_payload_{0:02d}_grain_{1}".format(
                        index,
                        grain_index,
                    ),
                )
                cmds.parent(grain, payload)
                cmds.xform(grain, translation=offset, objectSpace=True)
                _assign_maya_material(
                    cmds,
                    grain,
                    pollen_material if grain_index == 1 else pollen_grain_material,
                )
            task["payload_style"] = "orange_purple_grain_cluster"

        parented = cmds.parent(payload, bee_object)
        if parented:
            payload = parented[0]
        if cmds.objExists(payload):
            cmds.xform(payload, translation=(0.0, -0.25, 0.0), objectSpace=True)
            cmds.setKeyframe(
                payload,
                attribute="visibility",
                time=max(1, collection_frame - 1),
                value=0,
            )
            cmds.setKeyframe(
                payload,
                attribute="visibility",
                time=collection_frame,
                value=1,
            )
            cmds.setKeyframe(
                payload,
                attribute="visibility",
                time=reentry_frame,
                value=1,
            )
            cmds.setKeyframe(
                payload,
                attribute="visibility",
                time=reentry_frame + 1,
                value=0,
            )
            task["payload_object"] = payload

    return created


def _demo_task_color(task, assignment_index):
    """Return a strong task color while preserving resource identity."""
    if task.get("resource_type") == "nectar":
        palette = ((1.0, 0.62, 0.04), (1.0, 0.82, 0.18))
    else:
        palette = ((0.72, 0.24, 1.0), (1.0, 0.30, 0.06))
    return palette[int(assignment_index) % len(palette)]


def select_demo_transport_assignments(bees, tasks, max_active_bees=None):
    """Select one unique queued on-hive task per available Stage 4 worker."""
    task_by_id = {task.get("id"): task for task in tasks}
    candidate_ids_by_bee = []
    eligible_task_ids = set()
    for bee in bees:
        preferred_task_ids = []
        current_task_id = bee.get("current_task")
        if current_task_id:
            preferred_task_ids.append(current_task_id)
        preferred_task_ids.extend(
            task_id
            for task_id in bee.get("task_queue", [])
            if task_id not in preferred_task_ids
        )
        candidate_task_ids = [
            task_id
            for task_id in preferred_task_ids
            if task_by_id.get(task_id)
            and len(task_by_id[task_id].get("path") or []) > 1
            and task_by_id[task_id].get("origin")
            not in ("collection", "collection_demo")
        ]
        candidate_ids_by_bee.append(candidate_task_ids)
        eligible_task_ids.update(candidate_task_ids)

    safe_limit = _resolve_demo_active_bee_limit(
        len(eligible_task_ids),
        len(bees),
        max_active_bees,
    )
    assignments = []
    selected_task_ids = set()

    for bee, preferred_task_ids in zip(bees, candidate_ids_by_bee):
        if len(assignments) >= safe_limit:
            break
        task = next(
            (
                task_by_id.get(task_id)
                for task_id in preferred_task_ids
                if task_id not in selected_task_ids
            ),
            None,
        )
        if task is None:
            continue
        assignment_index = len(assignments)
        assignment = {
            "bee_id": bee.get("id"),
            "bee": bee,
            "bee_object": bee.get("maya_object"),
            "task_id": task.get("id"),
            "task": task,
            "source_cell": task.get("source_cell"),
            "target_cell": task.get("target_cell")
            or (task.get("path") or [None])[-1],
            "resource_type": task.get("resource_type"),
            "path": list(task.get("path") or []),
            "color": _demo_task_color(task, assignment_index),
            "visual_state": "active",
        }
        task["demo_transport_state"] = "active"
        task["demo_transport_bee_id"] = bee.get("id")
        task["demo_transport_color"] = assignment["color"]
        assignments.append(assignment)
        selected_task_ids.add(task.get("id"))

    queued_task_ids = {
        task_id
        for candidate_task_ids in candidate_ids_by_bee
        for task_id in candidate_task_ids
    }
    secondary_tasks = []
    for task in tasks:
        if (
            len(task.get("path") or []) > 1
            and task.get("id") not in selected_task_ids
            and task.get("origin") not in ("collection", "collection_demo")
        ):
            task["demo_transport_state"] = (
                "queued" if task.get("id") in queued_task_ids else "secondary"
            )
            task["demo_transport_bee_id"] = None
            secondary_tasks.append(task)

    return assignments, secondary_tasks


def _set_demo_viewport_color(cmds, node, color, line_width=None):
    """Apply a readable viewport override to a curve or marker transform."""
    if not node or not cmds.objExists(node):
        return
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
    for shape in shapes:
        cmds.setAttr(shape + ".overrideEnabled", 1)
        cmds.setAttr(shape + ".overrideRGBColors", 1)
        cmds.setAttr(shape + ".overrideColorRGB", *color, type="double3")
        if (
            line_width is not None
            and cmds.attributeQuery("lineWidth", node=shape, exists=True)
        ):
            cmds.setAttr(shape + ".lineWidth", int(line_width))


def style_demo_transport_paths(tasks, assignments):
    """Make active task paths strong and unanimated queued paths subtle."""
    import maya.cmds as cmds

    assignment_by_task = {
        assignment["task_id"]: assignment for assignment in assignments
    }
    active_nodes = []
    secondary_nodes = []
    for task in tasks:
        nodes = [
            node
            for node in task.get("path_visual_objects", [])
            if node and cmds.objExists(node)
        ]
        if not nodes:
            continue
        assignment = assignment_by_task.get(task.get("id"))
        if assignment is not None:
            color = assignment["color"]
            for node in nodes:
                is_curve = node == task.get("path_curve_object")
                _set_demo_viewport_color(
                    cmds,
                    node,
                    color,
                    line_width=6 if is_curve else None,
                )
            assignment["path_visuals"] = list(nodes)
            active_nodes.extend(nodes)
        else:
            for node in nodes:
                is_curve = node == task.get("path_curve_object")
                _set_demo_viewport_color(
                    cmds,
                    node,
                    (0.20, 0.34, 0.44),
                    line_width=1 if is_curve else None,
                )
                if not is_curve:
                    for axis in "XYZ":
                        cmds.setAttr(node + ".scale" + axis, 0.55)
            secondary_nodes.extend(nodes)
    return {
        "active_path_visuals": active_nodes,
        "secondary_path_visuals": secondary_nodes,
    }


def create_bee_task_selection_visuals(
    bees,
    tasks,
    cells,
    assignments,
    cell_size,
):
    """Create matched bee/source/target markers for active Stage 4 tasks."""
    import maya.cmds as cmds

    group_name = _replace_empty_group(
        cmds,
        DEMO_VISUAL_GROUPS["bee_selections"],
    )
    cell_by_id = {cell.get("id"): cell for cell in cells}
    bee_by_id = {bee.get("id"): bee for bee in bees}
    all_markers = []
    bee_markers = []
    source_markers = []
    target_markers = []

    for index, assignment in enumerate(assignments):
        color = assignment["color"]
        material = _create_maya_material(
            cmds,
            "chm_demo_active_task_{0:02d}_MAT".format(index),
            color,
        )
        bee = bee_by_id.get(assignment.get("bee_id"), assignment.get("bee"))
        bee_object = bee.get("maya_object") if bee else None
        if bee_object and cmds.objExists(bee_object):
            bounds = cmds.exactWorldBoundingBox(bee_object)
            bee_position = (
                (bounds[0] + bounds[3]) * 0.5,
                bounds[4] + 0.50,
                (bounds[2] + bounds[5]) * 0.5,
            )
        else:
            x, y, z = bee.get("position", [0.0, 0.8, 0.0]) if bee else (0, 0.8, 0)
            bee_position = (x, y + 0.50, z)

        bee_marker, _shape = cmds.polyCylinder(
            radius=float(cell_size) * 0.42,
            height=0.065,
            subdivisionsX=6,
            name="CloudHive_active_bee_{0:02d}".format(index),
        )
        cmds.xform(bee_marker, translation=bee_position, worldSpace=True)
        cmds.parent(bee_marker, group_name)
        _assign_maya_material(cmds, bee_marker, material)
        _set_demo_viewport_color(cmds, bee_marker, color)
        if bee_object and cmds.objExists(bee_object):
            cmds.pointConstraint(
                bee_object,
                bee_marker,
                maintainOffset=True,
                name="CloudHive_active_bee_{0:02d}_pointConstraint".format(index),
            )

        source_cell = cell_by_id.get(assignment.get("source_cell"))
        target_cell = cell_by_id.get(assignment.get("target_cell"))
        source_marker = None
        target_marker = None
        if source_cell is not None:
            x, y, z = source_cell["position"]
            source_marker, _shape = cmds.polyCylinder(
                radius=float(cell_size) * 0.34,
                height=0.13,
                subdivisionsX=6,
                name="CloudHive_active_source_{0:02d}".format(index),
            )
            cmds.xform(
                source_marker,
                translation=(x, y + 0.82, z),
                rotation=(0.0, 30.0, 0.0),
                worldSpace=True,
            )
            cmds.parent(source_marker, group_name)
            _assign_maya_material(cmds, source_marker, material)
            _set_demo_viewport_color(cmds, source_marker, color)
        if target_cell is not None:
            x, y, z = target_cell["position"]
            target_marker, _shape = cmds.polyTorus(
                radius=float(cell_size) * 0.46,
                sectionRadius=float(cell_size) * 0.055,
                subdivisionsX=12,
                subdivisionsY=4,
                name="CloudHive_active_target_{0:02d}".format(index),
            )
            cmds.xform(target_marker, translation=(x, y + 0.86, z), worldSpace=True)
            cmds.parent(target_marker, group_name)
            _assign_maya_material(cmds, target_marker, material)
            _set_demo_viewport_color(cmds, target_marker, color)

        assignment["bee_marker"] = bee_marker
        assignment["source_marker"] = source_marker
        assignment["target_marker"] = target_marker
        bee_markers.append(bee_marker)
        if source_marker:
            source_markers.append(source_marker)
        if target_marker:
            target_markers.append(target_marker)
        all_markers.extend(
            marker
            for marker in (bee_marker, source_marker, target_marker)
            if marker
        )

    return {
        "assignments": assignments,
        "all_markers": all_markers,
        "bee_markers": bee_markers,
        "source_markers": source_markers,
        "target_markers": target_markers,
    }


def create_deposit_update_visuals(cells, resource_events, cell_size, collection_tasks=None):
    """Create static Stage 7 markers for deposits, full cells, and re-entry."""
    import maya.cmds as cmds

    group_name = _replace_empty_group(cmds, DEMO_VISUAL_GROUPS["deposit_updates"])
    nectar_material = _create_maya_material(
        cmds, "chm_demo_deposit_nectar_MAT", (1.0, 0.72, 0.04)
    )
    pollen_material = _create_maya_material(
        cmds, "chm_demo_deposit_pollen_MAT", (1.0, 0.28, 0.04)
    )
    full_material = _create_maya_material(
        cmds, "chm_demo_storage_full_MAT", (0.95, 0.88, 0.68)
    )
    reentry_material = _create_maya_material(
        cmds, "chm_demo_collection_reentry_MAT", (0.72, 0.30, 1.0)
    )
    cell_by_id = {cell["id"]: cell for cell in cells}
    created = []

    for index, event in enumerate(resource_events):
        cell = cell_by_id.get(event.get("target_cell"))
        if cell is None:
            continue
        x, y, z = cell["position"]
        marker, _shape = cmds.polyCylinder(
            radius=float(cell_size) * 0.36,
            height=0.10,
            subdivisionsX=6,
            name="CloudHive_deposit_update_{0:03d}".format(index),
        )
        cmds.xform(
            marker,
            translation=(x, y + 0.82, z),
            rotation=(0.0, 30.0, 0.0),
            worldSpace=True,
        )
        cmds.parent(marker, group_name)
        _assign_maya_material(
            cmds,
            marker,
            nectar_material
            if event.get("resource_type") == "nectar"
            else pollen_material,
        )
        created.append(marker)

    for index, cell in enumerate(cells):
        if not cell.get("blocked_by_capacity"):
            continue
        x, y, z = cell["position"]
        full_marker, _shape = cmds.polyCylinder(
            radius=float(cell_size) * 0.70,
            height=0.07,
            subdivisionsX=6,
            name="CloudHive_full_storage_{0:03d}".format(index),
        )
        cmds.xform(
            full_marker,
            translation=(x, y + 1.02, z),
            rotation=(0.0, 30.0, 0.0),
            worldSpace=True,
        )
        cmds.parent(full_marker, group_name)
        _assign_maya_material(cmds, full_marker, full_material)
        created.append(full_marker)

    for index, task in enumerate(collection_tasks or []):
        if not task.get("demo_active"):
            continue
        cell = cell_by_id.get(task.get("cloud_base_cell"))
        if cell is None:
            continue
        x, y, z = cell["position"]
        marker, _shape = cmds.polySphere(
            radius=0.20,
            name="CloudHive_collection_reentry_{0:02d}".format(index),
        )
        cmds.xform(marker, translation=(x, y + 0.90, z), worldSpace=True)
        cmds.parent(marker, group_name)
        _assign_maya_material(cmds, marker, reentry_material)
        created.append(marker)

    return created


def author_demo_stage_transitions(
    drops,
    clouds,
    cells,
    resource_events,
    bees,
    tasks,
    bee_base_transforms,
    path_visuals,
    blocked_visuals,
    drop_demo_visuals,
    bee_selection_visuals,
    transport_demo,
    collection_tasks,
    deposit_visuals,
    stage_ranges,
    cell_depth,
):
    """Author compact keyed previews for the seven prepared demo stages."""
    import maya.cmds as cmds

    stage_objects = {stage: [] for stage in range(1, 8)}

    stage_one_start, stage_one_end = stage_ranges[1]
    cloud_by_id = {cloud["id"]: cloud for cloud in clouds}
    for index, drop in enumerate(drops):
        marker = drop.get("maya_object")
        cloud = cloud_by_id.get(drop.get("source_cloud"))
        if not marker or not cmds.objExists(marker) or cloud is None:
            continue
        local_start = stage_one_start + (index % 6) * 2
        local_end = stage_one_end - ((len(drops) - index - 1) % 4)
        cloud_x, cloud_y, cloud_z = cloud["position"]
        landing_x, landing_y, landing_z = drop["position"]
        source = (
            cloud_x + math.sin(index * 1.7) * 0.42,
            cloud_y - 0.50,
            cloud_z + math.cos(index * 1.3) * 0.42,
        )
        landing = (landing_x, landing_y + 0.18, landing_z)
        _key_visibility_hold(cmds, marker, stage_one_start, local_start, stage_one_end)
        _key_translation(cmds, marker, local_start, source)
        _key_translation(cmds, marker, local_end, landing)
        _key_scale_values(cmds, marker, local_start, 0.45)
        _key_scale_values(cmds, marker, local_end, 1.0)
        drop["demo_transition_start"] = local_start
        drop["demo_transition_end"] = local_end
        stage_objects[1].append(marker)

    stage_two_start, stage_two_end = stage_ranges[2]
    mapping_nodes = list(drop_demo_visuals.get("mapping", []))
    validation_nodes = list(drop_demo_visuals.get("validation", []))
    _key_reveal_sequence(cmds, mapping_nodes, stage_two_start, stage_two_end)
    _key_pop_sequence(cmds, validation_nodes, stage_two_start, stage_two_end)
    stage_objects[2].extend(mapping_nodes + validation_nodes)

    stage_three_start, stage_three_end = stage_ranges[3]
    direct_nodes = list(drop_demo_visuals.get("direct_storage", []))
    task_nodes = list(drop_demo_visuals.get("task_markers", []))
    stage_three_nodes = direct_nodes + task_nodes + list(blocked_visuals)
    _key_pop_sequence(cmds, stage_three_nodes, stage_three_start, stage_three_end)
    for node in direct_nodes:
        if not cmds.objExists(node + ".translateY"):
            continue
        final_y = float(cmds.getAttr(node + ".translateY"))
        cmds.setKeyframe(
            node,
            attribute="translateY",
            time=stage_three_start,
            value=final_y + 0.55,
        )
        cmds.setKeyframe(
            node,
            attribute="translateY",
            time=stage_three_end,
            value=final_y,
        )
    stage_objects[3].extend(stage_three_nodes)

    stage_four_start, stage_four_end = stage_ranges[4]
    active_path_nodes = list(transport_demo.get("active_path_visuals", []))
    secondary_path_nodes = list(
        transport_demo.get("secondary_path_visuals", [])
    )
    active_path_reveal_end = max(
        stage_four_start + 8,
        stage_four_end - 8,
    )
    _key_reveal_sequence(
        cmds,
        active_path_nodes,
        stage_four_start,
        active_path_reveal_end,
    )
    _key_reveal_sequence(
        cmds,
        secondary_path_nodes,
        min(stage_four_end - 6, stage_four_start + 16),
        stage_four_end,
    )
    _key_pop_sequence(
        cmds,
        bee_selection_visuals,
        stage_four_start,
        stage_four_end,
        peak_scale=1.45,
    )
    stage_four_crawls = _key_stage_four_bee_crawls(
        cmds,
        transport_demo.get("assignments", []),
        cells,
        bee_base_transforms,
        stage_four_start,
        stage_four_end,
        stage_ranges[5][0],
    )
    active_bee_final_keyframes = [
        int(crawl["final_keyframe"])
        for crawl in stage_four_crawls
        if crawl.get("final_keyframe") is not None
    ]
    active_bee_final_movement_frames = [
        int(crawl["final_movement_frame"])
        for crawl in stage_four_crawls
        if crawl.get("final_movement_frame") is not None
    ]
    corrected_stage_four_end = max(
        [int(stage_four_end), int(active_path_reveal_end)]
        + active_bee_final_keyframes
    )
    stage_ranges[4] = (int(stage_four_start), corrected_stage_four_end)
    stage_objects[4].extend(list(path_visuals) + list(bee_selection_visuals))
    stage_objects[4].extend([
        crawl["bee_object"] for crawl in stage_four_crawls
    ])

    stage_five_start, stage_five_end = stage_ranges[5]
    trigger_nodes = _group_transform_children(
        cmds,
        DEMO_VISUAL_GROUPS["collection_triggers"],
    )
    _key_pop_sequence(
        cmds,
        trigger_nodes,
        stage_five_start,
        stage_five_end,
        peak_scale=1.35,
    )
    stage_objects[5].extend(trigger_nodes)

    stage_six_start, stage_six_end = stage_ranges[6]
    collection_nodes = _group_transform_children(
        cmds,
        DEMO_VISUAL_GROUPS["collection_visuals"],
    )
    _key_reveal_sequence(
        cmds,
        collection_nodes,
        stage_six_start,
        min(stage_six_end, stage_six_start + 18),
    )
    _key_bee_demo_holds(
        cmds,
        bees,
        bee_base_transforms,
        collection_tasks,
        stage_six_start,
        stage_six_end,
        stage_ranges[7][1],
    )
    for task in collection_tasks:
        payload = task.get("payload_object")
        if not payload or not cmds.objExists(payload):
            continue
        cmds.setKeyframe(
            payload,
            attribute="visibility",
            time=stage_six_end,
            value=1,
        )
        cmds.setKeyframe(
            payload,
            attribute="visibility",
            time=stage_ranges[7][0],
            value=0,
        )
    stage_objects[6].extend(collection_nodes)
    stage_objects[6].extend([
        task.get("payload_object")
        for task in collection_tasks
        if task.get("payload_object")
    ])

    stage_seven_start, stage_seven_end = stage_ranges[7]
    _key_pop_sequence(
        cmds,
        deposit_visuals,
        stage_seven_start,
        stage_seven_end,
        peak_scale=1.40,
    )
    for node in deposit_visuals:
        if not cmds.objExists(node + ".translateY"):
            continue
        final_y = float(cmds.getAttr(node + ".translateY"))
        cmds.setKeyframe(
            node,
            attribute="translateY",
            time=stage_seven_start,
            value=final_y + 0.42,
        )
        cmds.setKeyframe(
            node,
            attribute="translateY",
            time=stage_seven_end,
            value=final_y,
        )
    _key_compact_resource_updates(
        cmds,
        cells,
        resource_events,
        stage_ranges[3],
        stage_ranges[7],
        cell_depth,
    )
    stage_objects[7].extend(list(deposit_visuals))

    cmds.currentTime(1)
    return {
        "stage_objects": stage_objects,
        "keyed_object_count": sum(len(nodes) for nodes in stage_objects.values()),
        "stage_four_crawl": stage_four_crawls[0] if stage_four_crawls else None,
        "stage_four_crawls": stage_four_crawls,
        "stage_four_timing": {
            "start_frame": int(stage_four_start),
            "end_frame": corrected_stage_four_end,
            "active_bee_final_keyframes": active_bee_final_keyframes,
            "active_bee_final_movement_frames": (
                active_bee_final_movement_frames
            ),
            "active_path_reveal_end": int(active_path_reveal_end),
            "marker_pulse_end": int(stage_four_end),
            "completion_hold_frames": DEMO_STAGE_FOUR_COMPLETION_HOLD_FRAMES,
        },
        "active_transport_task_ids": [
            assignment.get("task_id")
            for assignment in transport_demo.get("assignments", [])
        ],
        "queued_transport_task_ids": [
            task.get("id")
            for task in transport_demo.get("secondary_tasks", [])
            if task.get("demo_transport_state") == "queued"
        ],
        "secondary_transport_task_ids": [
            task.get("id")
            for task in transport_demo.get("secondary_tasks", [])
            if task.get("demo_transport_state") == "secondary"
        ],
        "active_collection_task_ids": [
            task.get("id") for task in collection_tasks if task.get("demo_active")
        ],
        "queued_collection_task_ids": [
            task.get("id") for task in collection_tasks if not task.get("demo_active")
        ],
    }


def _group_transform_children(cmds, group_name):
    """Return transform descendants of a generated demo group."""
    if not cmds.objExists(group_name):
        return []
    descendants = cmds.listRelatives(
        group_name,
        allDescendents=True,
        type="transform",
        fullPath=False,
    ) or []
    return list(reversed(descendants))


def _key_visibility_hold(cmds, node, stage_start, reveal_frame, stage_end):
    """Hide at the stage start, reveal once, and hold the final state."""
    if not node or not cmds.objExists(node):
        return
    reveal_frame = max(int(stage_start) + 1, int(reveal_frame))
    cmds.setKeyframe(node, attribute="visibility", time=stage_start, value=0)
    cmds.setKeyframe(
        node,
        attribute="visibility",
        time=max(int(stage_start), reveal_frame - 1),
        value=0,
    )
    cmds.setKeyframe(node, attribute="visibility", time=reveal_frame, value=1)
    cmds.setKeyframe(node, attribute="visibility", time=stage_end, value=1)


def _key_translation(cmds, node, frame, position):
    """Key one transform translation without scrubbing the Maya timeline."""
    for axis, value in zip("XYZ", position):
        cmds.setKeyframe(
            node,
            attribute="translate{0}".format(axis),
            time=frame,
            value=float(value),
        )


def _key_scale_values(cmds, node, frame, value):
    """Key uniform scale and hold it after the final authored key."""
    if not node or not cmds.objExists(node):
        return
    for axis in "XYZ":
        attribute = "scale{0}".format(axis)
        cmds.setKeyframe(node, attribute=attribute, time=frame, value=float(value))
        try:
            cmds.setInfinity(node + "." + attribute, postInfinite="constant")
        except RuntimeError:
            pass


def _key_reveal_sequence(cmds, nodes, stage_start, stage_end):
    """Reveal prepared objects progressively across one short stage."""
    valid_nodes = [node for node in nodes if node and cmds.objExists(node)]
    if not valid_nodes:
        return
    reveal_span = max(1, int(stage_end) - int(stage_start) - 4)
    for index, node in enumerate(valid_nodes):
        reveal = int(stage_start) + 2 + int(
            round(index * reveal_span / float(max(1, len(valid_nodes) - 1)))
        )
        _key_visibility_hold(cmds, node, stage_start, reveal, stage_end)


def _key_pop_sequence(
    cmds,
    nodes,
    stage_start,
    stage_end,
    peak_scale=1.25,
):
    """Reveal and pulse simple markers while leaving them visible at the end."""
    valid_nodes = [node for node in nodes if node and cmds.objExists(node)]
    if not valid_nodes:
        return
    reveal_span = max(1, int(stage_end) - int(stage_start) - 8)
    for index, node in enumerate(valid_nodes):
        reveal = int(stage_start) + 2 + int(
            round(index * reveal_span / float(max(1, len(valid_nodes) - 1)))
        )
        peak = min(int(stage_end) - 2, reveal + 4)
        _key_visibility_hold(cmds, node, stage_start, reveal, stage_end)
        _key_scale_values(cmds, node, stage_start, 0.05)
        _key_scale_values(cmds, node, reveal, 0.15)
        _key_scale_values(cmds, node, peak, peak_scale)
        _key_scale_values(cmds, node, stage_end, 1.0)


def _key_bee_demo_holds(
    cmds,
    bees,
    base_transforms,
    collection_tasks,
    stage_six_start,
    stage_six_end,
    stage_seven_end,
):
    """Hold bees still outside the compact Stage 6 collection preview."""
    task_end_by_bee = {}
    for task in collection_tasks:
        bee_id = task.get("bee_id") or task.get("assigned_bee_id")
        if bee_id:
            task_end_by_bee[bee_id] = max(
                task_end_by_bee.get(bee_id, stage_six_start),
                int(task.get("animation_end_frame", stage_six_start)),
            )

    for bee in bees:
        bee_object = bee.get("maya_object")
        if not bee_object or not cmds.objExists(bee_object):
            continue
        base_position = base_transforms.get(bee.get("id"), [0.0, 0.0, 0.0])
        _key_translation(cmds, bee_object, 1, base_position)
        _key_translation(cmds, bee_object, int(stage_six_start) - 1, base_position)

        task_end = task_end_by_bee.get(bee.get("id"))
        if task_end is None:
            final_position = base_position
        else:
            cmds.currentTime(task_end)
            final_position = cmds.xform(
                bee_object,
                query=True,
                translation=True,
                worldSpace=True,
            )
        _key_translation(cmds, bee_object, stage_six_end, final_position)
        _key_translation(cmds, bee_object, stage_seven_end, final_position)


def _key_stage_four_bee_crawls(
    cmds,
    assignments,
    cells,
    base_transforms,
    stage_start,
    stage_end,
    next_stage_start,
):
    """Preview unique assigned workers crawling on their own Stage 4 paths."""
    cell_by_id = {cell.get("id"): cell for cell in cells}
    crawls = []
    used_bee_ids = set()
    used_bee_objects = set()

    for assignment_index, assignment in enumerate(assignments):
        bee_id = assignment.get("bee_id")
        bee_object = assignment.get("bee_object")
        task = assignment.get("task") or {}
        if (
            not bee_id
            or bee_id in used_bee_ids
            or not bee_object
            or bee_object in used_bee_objects
            or not cmds.objExists(bee_object)
        ):
            continue

        crawl_points = []
        for cell_id in assignment.get("path") or task.get("path", []):
            cell = cell_by_id.get(cell_id)
            if cell is None:
                continue
            x, y, z = cell["position"]
            crawl_points.append((x, y + 0.75, z))
        crawl_points = _sample_demo_points(crawl_points, max_points=6)
        if len(crawl_points) < 2:
            continue

        base_position = base_transforms.get(bee_id, crawl_points[0])
        last_frame = max(
            int(stage_start) + 3,
            int(stage_end) - DEMO_STAGE_FOUR_COMPLETION_HOLD_FRAMES,
        )
        first_frame = min(
            last_frame - 1,
            int(stage_start) + 2 + assignment_index * 3,
        )
        span = max(1, last_frame - first_frame)
        keyed_frames = []
        for index, point in enumerate(crawl_points):
            frame = first_frame + int(
                round(index * span / float(len(crawl_points) - 1))
            )
            _key_translation(cmds, bee_object, frame, point)
            keyed_frames.append(frame)
        _key_translation(cmds, bee_object, int(stage_start) - 1, base_position)
        _key_translation(cmds, bee_object, stage_start, crawl_points[0])
        _key_translation(cmds, bee_object, stage_end, crawl_points[-1])

        # Return during the unplayed gap so Stage 5 begins from its clean,
        # static trigger state rather than showing incidental worker motion.
        _key_translation(cmds, bee_object, next_stage_start, base_position)
        try:
            cmds.keyTangent(
                bee_object,
                attribute=("translateX", "translateY", "translateZ"),
                time=(int(stage_start), int(stage_end)),
                inTangentType="linear",
                outTangentType="linear",
            )
        except RuntimeError:
            pass
        crawl = {
            "bee_id": bee_id,
            "bee_object": bee_object,
            "task_id": task.get("id"),
            "path": list(task.get("path", [])),
            "frames": keyed_frames,
            "final_movement_frame": keyed_frames[-1],
            "final_hold_frame": int(stage_end),
            "final_keyframe": int(stage_end),
            "movement_mode": "on_hive_transport",
            "color": assignment.get("color"),
            "bee_marker": assignment.get("bee_marker"),
            "source_marker": assignment.get("source_marker"),
            "target_marker": assignment.get("target_marker"),
        }
        assignment["crawl_preview"] = crawl
        task["demo_transport_frames"] = list(keyed_frames)
        crawls.append(crawl)
        used_bee_ids.add(bee_id)
        used_bee_objects.add(bee_object)

    return crawls


def _key_compact_resource_updates(
    cmds,
    cells,
    resource_events,
    stage_three_range,
    stage_seven_range,
    cell_depth,
):
    """Show direct deposits in Stage 3 and transported deposits in Stage 7."""
    first_event_by_cell_resource = {}
    for event in resource_events:
        key = (event.get("target_cell"), event.get("resource_type"))
        first_event_by_cell_resource.setdefault(key, event)

    stage_three_start, stage_three_end = stage_three_range
    stage_seven_start, stage_seven_end = stage_seven_range
    max_fill_height = max(0.12, float(cell_depth) * 0.72)

    for cell in cells:
        capacity = max(0.000001, float(cell.get("capacity", 1.0)))
        cell_id = cell["id"]
        maya_cell_id = _maya_safe_name_component(cell_id)
        initial_type = cell.get("initial_type", cell.get("type"))
        for resource_type in ("nectar", "pollen"):
            initial_amount = float(cell.get("initial_{0}".format(resource_type), 0.0))
            final_amount = float(cell.get(resource_type, 0.0))
            first_event = first_event_by_cell_resource.get((cell_id, resource_type))
            pre_transport_amount = (
                float(first_event.get("before_amount", initial_amount))
                if first_event
                else final_amount
            )

            if resource_type == "nectar":
                voxel_levels = sorted(
                    cmds.ls(
                        "{0}_nectar_voxel_level_*".format(maya_cell_id),
                        type="transform",
                    ) or []
                )
                for level_index, level in enumerate(voxel_levels, start=1):
                    for frame, amount in (
                        (stage_three_start, initial_amount),
                        (stage_three_end, pre_transport_amount),
                        (stage_seven_start, pre_transport_amount),
                        (stage_seven_end, final_amount),
                    ):
                        _key_discrete_level_visibility(
                            cmds,
                            level,
                            frame,
                            amount / capacity,
                            level_index,
                            len(voxel_levels),
                        )

            if resource_type == "nectar" and initial_type == "honey":
                fill = "{0}_nectar_level".format(maya_cell_id)
                if not cmds.objExists(fill):
                    continue
                _key_resource_level(
                    cmds,
                    fill,
                    stage_three_start,
                    initial_amount / capacity,
                    cell_depth,
                    max_fill_height,
                )
                _key_resource_level(
                    cmds,
                    fill,
                    stage_three_end,
                    pre_transport_amount / capacity,
                    cell_depth,
                    max_fill_height,
                )
                _key_resource_level(
                    cmds,
                    fill,
                    stage_seven_start,
                    pre_transport_amount / capacity,
                    cell_depth,
                    max_fill_height,
                )
                _key_resource_level(
                    cmds,
                    fill,
                    stage_seven_end,
                    final_amount / capacity,
                    cell_depth,
                    max_fill_height,
                )

            if resource_type == "pollen":
                grains = sorted(
                    cmds.ls(
                        "{0}_pollen_*".format(maya_cell_id),
                        type="transform",
                    ) or []
                )
                legacy_grains = [
                    "{0}_pollen_{1:02d}".format(maya_cell_id, grain_index)
                    for grain_index in range(8)
                    if cmds.objExists(
                        "{0}_pollen_{1:02d}".format(maya_cell_id, grain_index)
                    )
                ]
                grains = list(dict.fromkeys(grains + legacy_grains))
                for grain_index, grain in enumerate(grains):
                    threshold = float(grain_index + 1) / max(1, len(grains))
                    values = (
                        (stage_three_start, initial_amount),
                        (stage_three_end, pre_transport_amount),
                        (stage_seven_start, pre_transport_amount),
                        (stage_seven_end, final_amount),
                    )
                    for frame, amount in values:
                        cmds.setKeyframe(
                            grain,
                            attribute="visibility",
                            time=frame,
                            value=1 if amount / capacity >= threshold else 0,
                        )

        caps = [
            cap
            for cap in (
                "{0}_new_voxel_cap".format(maya_cell_id),
                "{0}_cap_lid".format(maya_cell_id),
            )
            if cmds.objExists(cap)
        ]
        for cap in caps:
            initially_capped = initial_type == "capped"
            finally_capped = cell.get("type") == "capped"
            cmds.setKeyframe(
                cap,
                attribute="visibility",
                time=stage_seven_start,
                value=1 if initially_capped else 0,
            )
            cmds.setKeyframe(
                cap,
                attribute="visibility",
                time=stage_seven_end,
                value=1 if finally_capped else 0,
            )


def organize_demo_cycle_groups(cycle_number):
    """Nest all prepared stage layers under one cycle-specific Maya group."""
    import maya.cmds as cmds

    cycle_group = "CloudHive_Cycle_{0:03d}_Stages_GRP".format(int(cycle_number))
    if cmds.objExists(cycle_group):
        cmds.delete(cycle_group)
    cmds.group(empty=True, name=cycle_group)
    for group_name in DEMO_VISUAL_GROUPS.values():
        if not cmds.objExists(group_name):
            continue
        parents = cmds.listRelatives(group_name, parent=True) or []
        if not parents or parents[0] != cycle_group:
            cmds.parent(group_name, cycle_group)
    return cycle_group


def apply_demo_stage(scene_data, stage):
    """Show one prepared stage and select its short transition segment."""
    import maya.cmds as cmds

    safe_stage = max(0, min(7, int(stage)))
    visible_by_stage = {
        0: set(),
        1: {"natural_drops"},
        2: {"natural_drops", "mapping", "validation"},
        3: {"direct_storage", "task_markers", "blocked_tasks"},
        4: {"task_markers", "bee_selections", "bfs_paths", "blocked_tasks"},
        5: {"collection_triggers"},
        6: {"collection_triggers", "collection_visuals"},
        7: {"deposit_updates", "blocked_tasks"},
    }
    visible_keys = visible_by_stage[safe_stage]
    groups = scene_data.get("demo_visual_groups", DEMO_VISUAL_GROUPS)
    for group_key, group_name in groups.items():
        if cmds.objExists(group_name + ".visibility"):
            cmds.setAttr(group_name + ".visibility", group_key in visible_keys)

    frame = int(scene_data.get("demo_stage_frames", {}).get(safe_stage, 1))
    playback_range = scene_data.get("demo_playback_ranges", {}).get(
        safe_stage,
        (frame, frame + 1),
    )
    range_start = max(1, int(playback_range[0]))
    range_end = max(range_start + 1, int(playback_range[1]))
    cmds.playbackOptions(
        minTime=range_start,
        maxTime=range_end,
        loop="once",
        view="active",
    )
    cmds.currentTime(max(range_start, min(frame, range_end)))
    cmds.refresh(force=True)
    scene_data["demo_stage"] = safe_stage
    scene_data["active_demo_frame"] = cmds.currentTime(query=True)
    scene_data["active_playback_range"] = (range_start, range_end)
    scene_data["visible_demo_groups"] = sorted(visible_keys)
    guide_state = update_demo_guide(scene_data, safe_stage)
    return {
        "stage": safe_stage,
        "label": DEMO_STAGE_LABELS[safe_stage],
        "frame": scene_data["active_demo_frame"],
        "playback_range": scene_data["active_playback_range"],
        "visible_groups": scene_data["visible_demo_groups"],
        "demo_guide": guide_state,
    }


def _replace_empty_group(cmds, group_name):
    """Replace one generated visual group and return its transform name."""
    if cmds.objExists(group_name):
        cmds.delete(group_name)
    return cmds.group(empty=True, name=group_name)


def _style_demo_curve(cmds, curve, color, line_width=3):
    """Give a Maya curve an explicit viewport color and readable width."""
    shapes = cmds.listRelatives(curve, shapes=True, fullPath=True) or []
    for shape in shapes:
        cmds.setAttr(shape + ".overrideEnabled", 1)
        cmds.setAttr(shape + ".overrideRGBColors", 1)
        cmds.setAttr(
            shape + ".overrideColorRGB",
            float(color[0]),
            float(color[1]),
            float(color[2]),
            type="double3",
        )
        if cmds.attributeQuery("lineWidth", node=shape, exists=True):
            cmds.setAttr(shape + ".lineWidth", int(line_width))


def build_cell_resource_animation_events(
    cells,
    drops,
    resource_events,
    animation_records,
):
    """Build one chronological visual resource timeline for every cell.

    The simulation updates cell amounts immediately, while Maya shows the same
    changes later: a drop adds resource when it lands, a worker removes it when
    pickup finishes, and the destination gains it when delivery finishes. This
    pure-Python helper keeps those representations synchronized without Maya.
    """
    cell_by_id = {cell["id"]: cell for cell in cells}
    warnings = []

    def normalized_frame(value, fallback, task_id, label):
        """Return a positive integer frame and record visible fallback use."""
        try:
            frame = int(round(float(value)))
        except (TypeError, ValueError):
            try:
                frame = int(round(float(fallback)))
            except (TypeError, ValueError):
                frame = 1
            warnings.append(
                "Cloud-Hive Bloomfield: task '{0}' has no valid {1}; "
                "using animation frame {2} for its resource visual.".format(
                    task_id or "<unknown>",
                    label,
                    max(1, frame),
                )
            )
        return max(1, frame)

    delivery_by_task = {}
    pickup_by_task = {}
    for record in animation_records:
        task_id = record.get("task_id")
        if not task_id:
            continue
        keyed_frames = record.get("frames") or []
        last_keyed_frame = keyed_frames[-1] if keyed_frames else 1
        delivery_by_task[task_id] = normalized_frame(
            record.get("delivery_frame"),
            last_keyed_frame,
            task_id,
            "delivery frame",
        )
        pickup_by_task[task_id] = normalized_frame(
            record.get("pickup_frame"),
            keyed_frames[0] if keyed_frames else 1,
            task_id,
            "pickup frame",
        )
    drop_by_task = {
        "task_{0}".format(drop.get("id")): drop
        for drop in drops
        if drop.get("id")
    }

    raw_events = []
    sequence = 0
    for drop in drops:
        amount = max(0.0, float(drop.get("landing_deposited_amount", 0.0)))
        cell_id = drop.get("landing_cell_id")
        resource_type = drop.get("resource_type")
        if amount <= 0.000001 or cell_id not in cell_by_id:
            continue
        if resource_type not in ("nectar", "pollen"):
            continue
        task_id = "task_{0}".format(drop.get("id"))
        frame = normalized_frame(
            drop.get("animation_end_frame"),
            1,
            task_id,
            "landing frame",
        )
        raw_events.append({
            "event_kind": "landing",
            "task_id": task_id,
            "cell_id": cell_id,
            "resource_type": resource_type,
            "amount": amount,
            "delta": amount,
            "frame": frame,
            "event_order": 0,
            "sequence": sequence,
            "became_capped": False,
        })
        sequence += 1

    for transfer in resource_events:
        task_id = transfer.get("task_id")
        resource_type = transfer.get("resource_type")
        amount = max(0.0, float(transfer.get("amount", 0.0)))
        if amount <= 0.000001 or resource_type not in ("nectar", "pollen"):
            continue

        linked_drop = drop_by_task.get(task_id, {})
        landing_frame = normalized_frame(
            linked_drop.get("animation_end_frame"),
            1,
            task_id,
            "landing frame",
        )
        pickup_frame = max(
            landing_frame,
            normalized_frame(
                pickup_by_task.get(task_id),
                landing_frame + 5,
                task_id,
                "pickup frame",
            ),
        )
        delivery_frame = max(
            pickup_frame,
            normalized_frame(
                delivery_by_task.get(task_id),
                pickup_frame + 8,
                task_id,
                "delivery frame",
            ),
        )

        source_cell_id = transfer.get("source_cell")
        if source_cell_id in cell_by_id:
            raw_events.append({
                "event_kind": "pickup",
                "task_id": task_id,
                "cell_id": source_cell_id,
                "resource_type": resource_type,
                "amount": amount,
                "delta": -amount,
                "frame": pickup_frame,
                "event_order": 1,
                "sequence": sequence,
                "became_capped": False,
            })
            sequence += 1

        target_cell_id = transfer.get("target_cell")
        if target_cell_id in cell_by_id:
            raw_events.append({
                "event_kind": "delivery",
                "task_id": task_id,
                "cell_id": target_cell_id,
                "resource_type": resource_type,
                "amount": amount,
                "delta": amount,
                "frame": delivery_frame,
                "event_order": 2,
                "sequence": sequence,
                "became_capped": bool(transfer.get("became_capped")),
            })
            sequence += 1

    raw_by_cell = {}
    for event in raw_events:
        raw_by_cell.setdefault(event["cell_id"], []).append(event)

    events_by_cell = {}
    all_events = []
    for cell_id, cell_events in raw_by_cell.items():
        cell = cell_by_id[cell_id]
        running_amounts = {
            "nectar": float(cell.get("initial_nectar", 0.0)),
            "pollen": float(cell.get("initial_pollen", 0.0)),
        }
        ordered_events = sorted(
            cell_events,
            key=lambda item: (
                int(item["frame"]),
                int(item["event_order"]),
                int(item["sequence"]),
            ),
        )
        processed = []
        for event in ordered_events:
            event = dict(event)
            resource_type = event["resource_type"]
            before_amount = running_amounts[resource_type]
            after_amount = max(0.0, before_amount + float(event["delta"]))
            event["before_amount"] = before_amount
            event["after_amount"] = after_amount
            # Retain this old key for the existing Maya keying code below.
            event["delivery_frame"] = int(event["frame"])
            running_amounts[resource_type] = after_amount
            processed.append(event)
            all_events.append(event)
        events_by_cell[cell_id] = processed

    return {
        "events_by_cell": events_by_cell,
        "all_events": all_events,
        "warnings": warnings,
        "addition_events": [
            event for event in all_events if float(event.get("delta", 0.0)) > 0.0
        ],
    }


def create_cell_resource_visuals(
    cells,
    drops,
    resource_events,
    animation_records,
    cell_size,
    cell_depth,
    voxel_density=14,
):
    """Animate landing, pickup, and delivery changes inside honeycomb cells."""
    import maya.cmds as cmds

    group_name = "CloudHive_CellResources_GRP"
    if cmds.objExists(group_name):
        cmds.delete(group_name)
    cmds.group(empty=True, name=group_name)
    mesh_group = cmds.group(empty=True, name="CloudHive_CellResourceMeshes_GRP")
    instance_group = cmds.group(empty=True, name="CloudHive_CellResourceInstances_GRP")
    prototype_group = cmds.group(empty=True, name="CloudHive_CellResourcePrototypes_GRP")
    cmds.parent(mesh_group, instance_group, prototype_group, group_name)
    cmds.setAttr(prototype_group + ".visibility", 0)

    dimensions = get_voxel_dimensions(cell_size, cell_depth, voxel_density)
    pitch = dimensions["pitch"]
    base_layers = dimensions["base_layers"]
    wall_layers = dimensions["wall_layers"]
    honey_material = create_voxel_material(cmds, "honey")
    cap_material = create_voxel_material(cmds, "cap")
    glint_material = create_voxel_material(cmds, "honey_glint")
    pollen_materials = {
        material_key: create_voxel_material(cmds, material_key)
        for material_key in ("pollen_orange", "pollen_gold", "pollen_yellow")
    }
    pollen_prototypes = {
        material_key: ensure_voxel_cube_prototype(
            cmds,
            "CloudHive_dynamic_{0}_PROTOTYPE".format(material_key),
            pitch,
            material,
            prototype_group,
        )
        for material_key, material in pollen_materials.items()
    }
    glint_prototype = ensure_voxel_cube_prototype(
        cmds,
        "CloudHive_dynamic_glint_PROTOTYPE",
        pitch,
        glint_material,
        prototype_group,
    )

    event_timeline = build_cell_resource_animation_events(
        cells,
        drops,
        resource_events,
        animation_records,
    )
    events_by_cell = event_timeline["events_by_cell"]
    for warning in event_timeline.get("warnings", []):
        cmds.warning(warning)

    created = []
    max_honey_layers = max(2, min(4, wall_layers - 3))
    pollen_offsets = [
        (-0.34, -0.24), (-0.12, -0.31), (0.12, -0.28), (0.34, -0.18),
        (-0.39, 0.02), (-0.14, -0.02), (0.11, 0.03), (0.37, 0.08),
        (-0.28, 0.25), (-0.02, 0.29), (0.24, 0.26), (0.02, 0.10),
    ]

    for cell in cells:
        cell_id = cell["id"]
        maya_cell_id = _maya_safe_name_component(cell_id)
        initial_type = cell.get("initial_type", cell.get("type"))
        capacity = max(0.000001, float(cell.get("capacity", 1.0)))
        x, _y, z = cell["position"]
        cell_events = sorted(
            events_by_cell.get(cell_id, []),
            key=lambda item: item.get("delivery_frame", 1),
        )
        animated_resource_types = {
            event["resource_type"] for event in cell_events
        }
        show_nectar = (
            initial_type == "honey"
            or float(cell.get("initial_nectar", 0.0)) > 0.000001
            or "nectar" in animated_resource_types
        )
        show_pollen = (
            initial_type == "pollen"
            or float(cell.get("initial_pollen", 0.0)) > 0.000001
            or "pollen" in animated_resource_types
        )

        if show_nectar:
            initial_amount = float(cell.get("initial_nectar", 0.0))
            for level_index in range(max_honey_layers):
                keys = set()
                for stack_index in range(level_index + 1):
                    keys.update(hex_voxel_layer_keys(
                        x,
                        z,
                        float(cell_size) * 0.58,
                        pitch,
                        base_layers + 1 + stack_index,
                        inset=pitch * 0.35,
                    ))
                fill = create_merged_voxel_mesh(
                    keys,
                    pitch,
                    "{0}_nectar_voxel_level_{1:02d}".format(
                        maya_cell_id,
                        level_index,
                    ),
                    honey_material,
                    parent=mesh_group,
                )
                if not fill:
                    continue
                _key_discrete_level_visibility(
                    cmds,
                    fill,
                    1,
                    initial_amount / capacity,
                    level_index + 1,
                    max_honey_layers,
                )
                for event in cell_events:
                    if event["resource_type"] != "nectar":
                        continue
                    frame = int(event["delivery_frame"])
                    _key_discrete_level_visibility(
                        cmds,
                        fill,
                        max(1, frame - 1),
                        event["before_amount"] / capacity,
                        level_index + 1,
                        max_honey_layers,
                    )
                    _key_discrete_level_visibility(
                        cmds,
                        fill,
                        frame,
                        event["after_amount"] / capacity,
                        level_index + 1,
                        max_honey_layers,
                    )
                created.append(fill)

        if show_pollen:
            initial_amount = float(cell.get("initial_pollen", 0.0))
            records_by_material = {material_key: [] for material_key in pollen_materials}
            for grain_index, (offset_x, offset_z) in enumerate(pollen_offsets):
                material_key = tuple(pollen_materials)[grain_index % 3]
                records_by_material[material_key].append({
                    "position": (
                        round((x + offset_x * float(cell_size)) / pitch) * pitch,
                        (base_layers + 1.1 + (grain_index // 8) * 0.72) * pitch,
                        round((z + offset_z * float(cell_size)) / pitch) * pitch,
                    ),
                    "scale": (0.82, 0.72 + (grain_index % 3) * 0.12, 0.82),
                    "threshold": float(grain_index + 1) / len(pollen_offsets),
                })

            for material_key, records in records_by_material.items():
                grains = create_voxel_cube_instances(
                    cmds,
                    pollen_prototypes[material_key],
                    records,
                    "{0}_{1}".format(maya_cell_id, material_key),
                    instance_group,
                )
                for grain, record in zip(grains, records):
                    threshold = record["threshold"]
                    _key_threshold_visibility(
                        cmds,
                        grain,
                        1,
                        initial_amount / capacity,
                        threshold,
                    )
                    for event in cell_events:
                        if event["resource_type"] != "pollen":
                            continue
                        frame = int(event["delivery_frame"])
                        _key_threshold_visibility(
                            cmds,
                            grain,
                            max(1, frame - 1),
                            event["before_amount"] / capacity,
                            threshold,
                        )
                        _key_threshold_visibility(
                            cmds,
                            grain,
                            frame,
                            event["after_amount"] / capacity,
                            threshold,
                        )
                    created.append(grain)

        if initial_type != "capped" and cell.get("type") == "capped":
            cap_keys = hex_voxel_layer_keys(
                x,
                z,
                float(cell_size) * 0.76,
                pitch,
                base_layers + wall_layers - 2,
                inset=pitch * 0.25,
            )
            cap = create_merged_voxel_mesh(
                cap_keys,
                pitch,
                "{0}_new_voxel_cap".format(maya_cell_id),
                cap_material,
                parent=mesh_group,
            )
            if cap:
                cap_event = next(
                    (event for event in cell_events if event.get("became_capped")), None
                )
                cap_frame = int(cap_event["delivery_frame"]) if cap_event else 1
                cmds.setKeyframe(
                    cap, attribute="visibility", time=max(1, cap_frame - 1), value=0
                )
                cmds.setKeyframe(cap, attribute="visibility", time=cap_frame, value=1)
                created.append(cap)

    cell_by_id = {cell["id"]: cell for cell in cells}
    for event_index, event in enumerate(event_timeline["addition_events"]):
        cell = cell_by_id.get(event["cell_id"])
        frame = event.get("frame")
        if cell is None or frame is None:
            continue
        x, _y, z = cell["position"]
        flash_offsets = (
            (-0.46, 0.0),
            (0.46, 0.0),
            (0.0, -0.40),
            (0.0, 0.40),
        )
        flash_records = [
            {
                "position": (
                    round((x + offset_x * cell_size) / pitch) * pitch,
                    (base_layers + wall_layers + 0.45) * pitch,
                    round((z + offset_z * cell_size) / pitch) * pitch,
                ),
                "scale": (0.86, 0.28, 0.86),
            }
            for offset_x, offset_z in flash_offsets
        ]
        flashes = create_voxel_cube_instances(
            cmds,
            glint_prototype,
            flash_records,
            "CloudHive_delivery_glint_{0:03d}".format(event_index),
            instance_group,
        )
        for flash in flashes:
            cmds.setKeyframe(
                flash, attribute="visibility", time=max(1, int(frame) - 1), value=0
            )
            cmds.setKeyframe(flash, attribute="visibility", time=int(frame), value=1)
            cmds.setKeyframe(flash, attribute="scaleX", time=int(frame), value=0.35)
            cmds.setKeyframe(flash, attribute="scaleZ", time=int(frame), value=0.35)
            cmds.setKeyframe(flash, attribute="scaleX", time=int(frame) + 4, value=1.30)
            cmds.setKeyframe(flash, attribute="scaleZ", time=int(frame) + 4, value=1.30)
            cmds.setKeyframe(
                flash, attribute="visibility", time=int(frame) + 8, value=0
            )
            created.append(flash)

    return created


def _key_threshold_visibility(cmds, node, frame, ratio, threshold):
    """Reveal a whole voxel or voxel layer at a discrete resource threshold."""
    visible = 1 if max(0.0, min(1.0, float(ratio))) >= float(threshold) else 0
    cmds.setKeyframe(node, attribute="visibility", time=int(frame), value=visible)


def _key_discrete_level_visibility(cmds, node, frame, ratio, level, level_count):
    """Show exactly one premerged honey stack for a quantized fill level."""
    safe_ratio = max(0.0, min(1.0, float(ratio)))
    active_level = int(math.ceil(safe_ratio * int(level_count) - 0.000001))
    visible = 1 if active_level == int(level) else 0
    cmds.setKeyframe(node, attribute="visibility", time=int(frame), value=visible)


def create_blocked_task_visuals(tasks, cells, animation_end=320):
    """Create hidden debug markers for cells with unreachable cleanup tasks."""
    import maya.cmds as cmds

    group_name = "CloudHive_BlockedTasks_GRP"
    cmds.group(empty=True, name=group_name)
    # Keep the diagnostic data available in the Outliner without allowing the
    # red debug columns to affect the warm honeycomb presentation by default.
    cmds.setAttr(group_name + ".visibility", 0)
    material = _create_maya_material(
        cmds, "chm_blocked_task_red_MAT", (1.0, 0.08, 0.04)
    )
    cell_by_id = {cell["id"]: cell for cell in cells}
    blocked_cell_ids = sorted({
        task.get("source_cell")
        for task in tasks
        if not task.get("path") and task.get("source_cell")
    })
    created = []

    for index, cell_id in enumerate(blocked_cell_ids):
        cell = cell_by_id.get(cell_id)
        if cell is None:
            continue
        x, _y, z = cell["position"]
        marker, _shape = cmds.polyCube(
            width=0.18,
            height=0.55,
            depth=0.18,
            name="CloudHive_blocked_marker_{0:02d}".format(index),
        )
        cmds.xform(marker, translation=(x, 0.85, z), worldSpace=True)
        cmds.parent(marker, group_name)
        _assign_maya_material(cmds, marker, material)
        cmds.setKeyframe(marker, attribute="scaleY", time=1, value=0.75)
        cmds.setKeyframe(marker, attribute="scaleY", time=12, value=1.2)
        cmds.setKeyframe(marker, attribute="scaleY", time=24, value=0.75)
        cmds.setInfinity(marker + ".scaleY", postInfinite="cycle")
        created.append(marker)

    return created


def clear_scene(preserve_camera=False):
    """Remove previous Cloud-Hive Meadow generated objects from the Maya scene.

    Parameters:
        preserve_camera (bool): Keep the generated camera/light rig while the
            visualization is rebuilt. The public Clear action uses the default
            False value and removes the rig with the rest of the scene.

    Returns:
        None.
    """
    import maya.cmds as cmds

    clear_demo_guide()

    if preserve_camera and cmds.objExists(CAMERA_LIGHT_GROUP):
        camera_parent = cmds.listRelatives(
            CAMERA_LIGHT_GROUP,
            parent=True,
            fullPath=True,
        ) or []
        if camera_parent:
            try:
                cmds.parent(CAMERA_LIGHT_GROUP, world=True)
            except RuntimeError:
                # If Maya cannot detach it, deleting the root will remove it and
                # setup_camera_and_lighting() will recreate one clean rig.
                pass

    groups_to_delete = [
        ROOT_GROUP,
        "CloudHive_Honeycomb_GRP",
        "CloudHive_Clouds_GRP",
        "CloudHive_CloudFlowers_GRP",
        "CloudHive_ResourceDrops_GRP",
        "CloudHive_Bees_GRP",
        "CloudHive_BeeTaskPaths_GRP",
        "CloudHive_Ground_GRP",
        "CloudHive_MeadowDetails_GRP",
        "CloudHive_BeehiveBoxes_GRP",
        "CloudHive_FallingResources_GRP",
        "CloudHive_CellResources_GRP",
        "CloudHive_BlockedTasks_GRP",
        "CloudHive_DropMapping_GRP",
        "CloudHive_ValidationHighlights_GRP",
        "CloudHive_DirectStorage_GRP",
        "CloudHive_TaskMarkers_GRP",
        "CloudHive_BeeSelections_GRP",
        "CloudHive_CollectionTriggers_GRP",
        "CloudHive_CollectionVisuals_GRP",
        "CloudHive_DepositUpdate_GRP",
        CAMERA_LIGHT_GROUP,
        "CloudHive_RenderBackground_GRP",
        "CloudHive_Labels_GRP",
        "CloudHiveMeadow_GRP",
        DEMO_GUIDE_GROUP,
    ]
    groups_to_delete.extend(
        cmds.ls("CloudHive_Cycle_*_Stages_GRP", type="transform") or []
    )

    for group_name in groups_to_delete:
        if preserve_camera and group_name == CAMERA_LIGHT_GROUP:
            continue
        if cmds.objExists(group_name):
            cmds.delete(group_name)


def setup_camera_and_lighting(scene_radius=9.0):
    """Create or reuse a stable overview camera with expanded render lighting.

    Parameters:
        scene_radius (float): Approximate radius used to position camera/lights.

    Returns:
        dict: Names of the created camera and light nodes.
    """
    import maya.cmds as cmds

    group_name = CAMERA_LIGHT_GROUP
    if not cmds.objExists(group_name):
        cmds.group(empty=True, name=group_name)

    camera_transform, camera_shape = _find_camera_rig_node(cmds, "camera")
    if camera_transform is None:
        camera_transform, camera_shape = cmds.camera()
        camera_transform = cmds.rename(camera_transform, OVERVIEW_CAMERA)
    camera_transform = _parent_to_camera_rig(cmds, camera_transform, group_name)
    camera_shape = cmds.listRelatives(
        camera_transform,
        shapes=True,
        type="camera",
        fullPath=True,
    )[0]
    cmds.setAttr(camera_shape + ".focalLength", 35)

    # The camera survives cycle rebuilds, but lights are recreated inside this
    # generated rig so teammate lighting upgrades never accumulate duplicates.
    _clear_generated_camera_lights(cmds, group_name)
    key_light, key_shape = _create_native_render_light(
        cmds,
        group_name,
        "directionalLight",
        "CloudHive_Key_LGT",
        2.25,
        (1.0, 0.82, 0.62),
        rotation=(-48.0, -32.0, 0.0),
    )
    fill_light, fill_shape = _create_native_render_light(
        cmds,
        group_name,
        "directionalLight",
        "CloudHive_Fill_LGT",
        1.15,
        (0.76, 0.82, 1.0),
        rotation=(-28.0, 142.0, 0.0),
    )
    top_light, top_shape = _create_native_render_light(
        cmds,
        group_name,
        "directionalLight",
        "CloudHive_TopFill_LGT",
        0.65,
        (1.0, 0.92, 0.78),
        rotation=(-82.0, 18.0, 0.0),
    )
    ambient_light, ambient_shape = _create_native_render_light(
        cmds,
        group_name,
        "ambientLight",
        "CloudHive_Ambient_LGT",
        0.38,
        (0.78, 0.80, 1.0),
    )

    for light_shape in (key_shape, fill_shape, top_shape, ambient_shape):
        if cmds.attributeQuery("useRayTraceShadows", node=light_shape, exists=True):
            cmds.setAttr(light_shape + ".useRayTraceShadows", 0)
        if cmds.attributeQuery("aiCastShadows", node=light_shape, exists=True):
            cmds.setAttr(light_shape + ".aiCastShadows", 0)
    for light_shape, exposure in (
        (key_shape, 1.50),
        (fill_shape, 1.25),
        (top_shape, 1.00),
    ):
        if cmds.attributeQuery("aiExposure", node=light_shape, exists=True):
            cmds.setAttr(light_shape + ".aiExposure", exposure)
    if cmds.attributeQuery("aiAngle", node=key_shape, exists=True):
        cmds.setAttr(key_shape + ".aiAngle", 4.0)

    sky_fill_light = None
    sky_fill_shape = None
    try:
        sky_node = cmds.shadingNode(
            "aiSkyDomeLight",
            asLight=True,
            name="CloudHive_SkyFill_LGT",
        )
        sky_parent = cmds.listRelatives(sky_node, parent=True, fullPath=True) or []
        if sky_parent:
            sky_fill_shape = sky_node
            sky_fill_light = _parent_to_camera_rig(cmds, sky_parent[0], group_name)
        else:
            sky_fill_light = _parent_to_camera_rig(cmds, sky_node, group_name)
            sky_shapes = cmds.listRelatives(
                sky_fill_light, shapes=True, fullPath=True
            ) or []
            sky_fill_shape = sky_shapes[0] if sky_shapes else None
        if sky_fill_shape:
            if cmds.attributeQuery("color", node=sky_fill_shape, exists=True):
                cmds.setAttr(
                    sky_fill_shape + ".color", 1.0, 0.78, 0.64, type="double3"
                )
            if cmds.attributeQuery("intensity", node=sky_fill_shape, exists=True):
                cmds.setAttr(sky_fill_shape + ".intensity", 0.45)
            if cmds.attributeQuery("exposure", node=sky_fill_shape, exists=True):
                cmds.setAttr(sky_fill_shape + ".exposure", 1.0)
            if cmds.attributeQuery("camera", node=sky_fill_shape, exists=True):
                cmds.setAttr(sky_fill_shape + ".camera", 0)
            if cmds.attributeQuery("aiCastShadows", node=sky_fill_shape, exists=True):
                cmds.setAttr(sky_fill_shape + ".aiCastShadows", 0)
    except (RuntimeError, ValueError):
        sky_fill_light = None
        sky_fill_shape = None

    return {
        "camera": camera_transform.rsplit("|", 1)[-1],
        "camera_shape": camera_shape.rsplit("|", 1)[-1],
        "key_light": key_light.rsplit("|", 1)[-1],
        "key_shape": key_shape.rsplit("|", 1)[-1],
        "fill_light": fill_light.rsplit("|", 1)[-1],
        "fill_shape": fill_shape.rsplit("|", 1)[-1],
        "top_light": top_light.rsplit("|", 1)[-1],
        "top_shape": top_shape.rsplit("|", 1)[-1],
        "sky_fill_light": (
            sky_fill_light.rsplit("|", 1)[-1] if sky_fill_light else None
        ),
        "sky_fill_shape": (
            sky_fill_shape.rsplit("|", 1)[-1] if sky_fill_shape else None
        ),
        "ambient_light": ambient_light.rsplit("|", 1)[-1],
        "ambient_shape": ambient_shape.rsplit("|", 1)[-1],
    }


def _clear_generated_camera_lights(cmds, group_name):
    """Delete only generated light transforms while preserving the camera."""
    transforms = set()
    for light_type in ("directionalLight", "ambientLight", "aiSkyDomeLight"):
        try:
            shapes = cmds.listRelatives(
                group_name,
                allDescendents=True,
                fullPath=True,
                type=light_type,
            ) or []
        except RuntimeError:
            shapes = []
        for shape in shapes:
            transforms.update(
                cmds.listRelatives(shape, parent=True, fullPath=True) or [shape]
            )
    if transforms:
        cmds.delete(sorted(transforms, key=len, reverse=True))


def _create_native_render_light(
    cmds,
    group_name,
    light_type,
    transform_name,
    intensity,
    color,
    rotation=None,
):
    """Create one named native Maya light inside the generated camera rig."""
    if light_type == "ambientLight":
        shape = cmds.ambientLight(intensity=float(intensity))
    else:
        shape = cmds.directionalLight(intensity=float(intensity))
    transform = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
    transform = cmds.rename(transform, transform_name)
    transform = _parent_to_camera_rig(cmds, transform, group_name)
    shape = (cmds.listRelatives(transform, shapes=True, fullPath=True) or [shape])[0]
    cmds.setAttr(shape + ".intensity", float(intensity))
    cmds.setAttr(shape + ".color", *color, type="double3")
    if rotation is not None:
        cmds.xform(transform, rotation=rotation, worldSpace=True)
    return transform, shape


def _find_camera_rig_node(cmds, shape_type):
    """Return one generated transform/shape pair by Maya node type."""
    if not cmds.objExists(CAMERA_LIGHT_GROUP):
        return None, None

    shapes = cmds.listRelatives(
        CAMERA_LIGHT_GROUP,
        allDescendents=True,
        fullPath=True,
        type=shape_type,
    ) or []
    if not shapes:
        return None, None

    shape = sorted(shapes)[0]
    parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
    if not parents:
        return None, None
    return parents[0], shape


def _parent_to_camera_rig(cmds, transform, group_name):
    """Parent a generated transform under the rig and return its full DAG path."""
    group_paths = cmds.ls(group_name, long=True) or [group_name]
    group_path = group_paths[0]
    parents = cmds.listRelatives(transform, parent=True, fullPath=True) or []
    if not parents or parents[0] != group_path:
        parented = cmds.parent(transform, group_path)
        if parented:
            transform = parented[0]
    transform_paths = cmds.ls(transform, long=True) or [transform]
    return transform_paths[0]


def frame_scene_overview(camera_transform=OVERVIEW_CAMERA, fallback_radius=9.0, padding=1.35):
    """Place the render camera in a wide 3/4 view around generated content.

    The placement is recomputed from world-space scene bounds, so cloud height,
    drops, bees, and BFS paths are included. It never changes the active viewport
    camera; callers may opt into the camera only for the first Generate action.

    Parameters:
        camera_transform (str): Camera transform to position.
        fallback_radius (float): Safe framing radius if Maya cannot read bounds.
        padding (float): Extra space around the bounded scene.

    Returns:
        dict | None: Overview center, radius, and camera distance.
    """
    import maya.cmds as cmds

    if not cmds.objExists(camera_transform):
        cmds.warning(
            "Cloud-Hive Bloomfield: overview camera '{0}' does not exist.".format(
                camera_transform
            )
        )
        return None

    content_groups = [
        "CloudHive_Honeycomb_GRP",
        "CloudHive_Clouds_GRP",
        "CloudHive_CloudFlowers_GRP",
        "CloudHive_ResourceDrops_GRP",
        "CloudHive_Bees_GRP",
        "CloudHive_BeeTaskPaths_GRP",
        "CloudHive_FallingResources_GRP",
        "CloudHive_CellResources_GRP",
        "CloudHive_BlockedTasks_GRP",
        "CloudHive_DropMapping_GRP",
        "CloudHive_ValidationHighlights_GRP",
        "CloudHive_DirectStorage_GRP",
        "CloudHive_TaskMarkers_GRP",
        "CloudHive_BeeSelections_GRP",
        "CloudHive_CollectionTriggers_GRP",
        "CloudHive_CollectionVisuals_GRP",
        "CloudHive_DepositUpdate_GRP",
        "CloudHive_Labels_GRP",
    ]
    bounded_nodes = [node for node in content_groups if cmds.objExists(node)]
    bounds = None
    if bounded_nodes:
        try:
            bounds = cmds.exactWorldBoundingBox(*bounded_nodes)
        except RuntimeError:
            bounds = None

    safe_fallback = max(1.0, float(fallback_radius))
    if bounds and len(bounds) == 6 and all(math.isfinite(value) for value in bounds):
        center = (
            (bounds[0] + bounds[3]) * 0.5,
            (bounds[1] + bounds[4]) * 0.5,
            (bounds[2] + bounds[5]) * 0.5,
        )
        span_x = max(0.1, bounds[3] - bounds[0])
        span_y = max(0.1, bounds[4] - bounds[1])
        span_z = max(0.1, bounds[5] - bounds[2])
        bounds_radius = 0.5 * math.sqrt(
            (span_x * span_x) + (span_y * span_y) + (span_z * span_z)
        )
        scene_radius = max(bounds_radius, safe_fallback)
    else:
        center = (0.0, safe_fallback * 0.25, 0.0)
        scene_radius = safe_fallback

    camera_shapes = cmds.listRelatives(
        camera_transform,
        shapes=True,
        type="camera",
    ) or []
    if not camera_shapes:
        cmds.warning(
            "Cloud-Hive Bloomfield: overview transform '{0}' has no camera shape.".format(
                camera_transform
            )
        )
        return None

    camera_shape = camera_shapes[0]
    focal_length = 35.0
    cmds.setAttr(camera_shape + ".focalLength", focal_length)
    vertical_aperture = cmds.getAttr(camera_shape + ".verticalFilmAperture") * 25.4
    vertical_fov = 2.0 * math.atan(vertical_aperture / (2.0 * focal_length))
    half_fov_tangent = max(0.1, math.tan(vertical_fov * 0.5))
    distance = max(12.0, scene_radius * max(1.0, float(padding)) / half_fov_tangent)

    view_vector = (1.0, 0.82, 1.15)
    view_length = math.sqrt(sum(component * component for component in view_vector))
    view_direction = tuple(component / view_length for component in view_vector)
    camera_position = tuple(
        center[index] + view_direction[index] * distance
        for index in range(3)
    )
    target_vector = tuple(
        center[index] - camera_position[index]
        for index in range(3)
    )
    horizontal_length = math.sqrt(
        (target_vector[0] * target_vector[0])
        + (target_vector[2] * target_vector[2])
    )
    pitch = math.degrees(math.atan2(target_vector[1], horizontal_length))
    yaw = math.degrees(math.atan2(-target_vector[0], -target_vector[2]))

    cmds.xform(
        camera_transform,
        translation=camera_position,
        rotation=(pitch, yaw, 0.0),
        worldSpace=True,
    )
    cmds.setAttr(camera_shape + ".nearClipPlane", 0.1)
    cmds.setAttr(
        camera_shape + ".farClipPlane",
        max(1000.0, distance + scene_radius * 4.0),
    )

    return {
        "center": center,
        "radius": scene_radius,
        "distance": distance,
    }


def create_render_background(
    camera_transform,
    camera_shape,
    scene_radius=9.0,
):
    """Create a camera-locked procedural sunset backdrop and distant clouds.

    The background uses a Maya ramp feeding a surface shader, so it requires no
    image texture and renders consistently without receiving scene lighting.
    """
    import maya.cmds as cmds

    group_name = "CloudHive_RenderBackground_GRP"
    if cmds.objExists(group_name):
        cmds.delete(group_name)
    background_group = cmds.group(empty=True, name=group_name)
    cmds.parent(background_group, camera_transform, relative=True)
    # Remove shader nodes left by the earlier visible sun-disk version.
    for legacy_sun_node in ("chm_sunset_sun_SG", "chm_sunset_sun_SURF"):
        if cmds.objExists(legacy_sun_node):
            cmds.delete(legacy_sun_node)

    # Respect the user's existing Maya render size. The background adapts to
    # that aspect ratio but never changes Render Settings or Render View scale.
    if cmds.objExists("defaultResolution"):
        safe_width = max(1, int(cmds.getAttr("defaultResolution.width")))
        safe_height = max(1, int(cmds.getAttr("defaultResolution.height")))
        # Undo the exact 1500x1000 size forced by the previous background
        # version. This one-time migration keeps the same 3:2 framing while
        # making Render View display the image at a comfortable size again.
        if (safe_width, safe_height) == (1500, 1000):
            safe_width, safe_height = 960, 640
            cmds.setAttr("defaultResolution.width", safe_width)
            cmds.setAttr("defaultResolution.height", safe_height)
            if cmds.attributeQuery(
                "deviceAspectRatio",
                node="defaultResolution",
                exists=True,
            ):
                cmds.setAttr("defaultResolution.deviceAspectRatio", 1.5)
    else:
        safe_width = 960
        safe_height = 540
    aspect_ratio = float(safe_width) / float(safe_height)

    for scene_camera_shape in cmds.ls(type="camera") or []:
        if cmds.attributeQuery("renderable", node=scene_camera_shape, exists=True):
            cmds.setAttr(
                scene_camera_shape + ".renderable",
                1 if scene_camera_shape == camera_shape else 0,
            )

    focal_length = max(1.0, float(cmds.getAttr(camera_shape + ".focalLength")))
    film_aperture_mm = max(
        1.0,
        float(cmds.getAttr(camera_shape + ".horizontalFilmAperture")) * 25.4,
    )
    backdrop_distance = max(36.0, float(scene_radius) * 5.5)
    if cmds.attributeQuery("farClipPlane", node=camera_shape, exists=True):
        current_far_clip = float(cmds.getAttr(camera_shape + ".farClipPlane"))
        cmds.setAttr(
            camera_shape + ".farClipPlane",
            max(current_far_clip, backdrop_distance + 20.0),
        )
    half_view_width = backdrop_distance * film_aperture_mm / (2.0 * focal_length)
    backdrop_width = half_view_width * 2.0 * 1.18
    backdrop_height = backdrop_width / aspect_ratio

    backdrop = cmds.polyPlane(
        width=backdrop_width,
        height=backdrop_height,
        subdivisionsX=1,
        subdivisionsY=1,
        constructionHistory=False,
        name="CloudHive_Sunset_Backdrop_GEO",
    )[0]
    cmds.parent(backdrop, background_group, relative=True)
    cmds.setAttr(backdrop + ".translate", 0.0, 0.0, -backdrop_distance, type="double3")
    # A Maya polyPlane is born on XZ. Rotating -90 degrees places it on XY
    # while retaining a bottom-to-top V coordinate for the vertical ramp.
    cmds.setAttr(backdrop + ".rotateX", -90.0)

    ramp_name = "chm_sunset_sky_gradient_RMP"
    if cmds.objExists(ramp_name) and cmds.nodeType(ramp_name) != "ramp":
        cmds.delete(ramp_name)
    ramp = (
        ramp_name
        if cmds.objExists(ramp_name)
        else cmds.shadingNode("ramp", asTexture=True, name=ramp_name)
    )
    place_name = "chm_sunset_sky_place2d"
    if cmds.objExists(place_name) and cmds.nodeType(place_name) != "place2dTexture":
        cmds.delete(place_name)
    place_2d = (
        place_name
        if cmds.objExists(place_name)
        else cmds.shadingNode("place2dTexture", asUtility=True, name=place_name)
    )
    cmds.connectAttr(place_2d + ".outUV", ramp + ".uvCoord", force=True)
    cmds.connectAttr(
        place_2d + ".outUvFilterSize",
        ramp + ".uvFilterSize",
        force=True,
    )
    cmds.setAttr(ramp + ".type", 0)
    cmds.setAttr(ramp + ".interpolation", 3)
    gradient_entries = (
        # The primitive plane's rendered V direction runs from image top to
        # bottom, so purple is entered first and warm gold last.
        (0, 0.00, (0.29, 0.30, 0.58)),
        (1, 0.34, (0.66, 0.45, 0.64)),
        (2, 0.68, (1.00, 0.67, 0.40)),
        (3, 1.00, (1.00, 0.55, 0.18)),
    )
    for entry_index, position, color in gradient_entries:
        entry = "{0}.colorEntryList[{1}]".format(ramp, entry_index)
        cmds.setAttr(entry + ".position", position)
        cmds.setAttr(entry + ".color", *color, type="double3")

    sky_shader_name = "chm_sunset_sky_SURF"
    if (
        cmds.objExists(sky_shader_name)
        and cmds.nodeType(sky_shader_name) != "surfaceShader"
    ):
        cmds.delete(sky_shader_name)
    sky_shader = (
        sky_shader_name
        if cmds.objExists(sky_shader_name)
        else cmds.shadingNode("surfaceShader", asShader=True, name=sky_shader_name)
    )
    cmds.connectAttr(ramp + ".outColor", sky_shader + ".outColor", force=True)
    sky_shading_group = _ensure_surface_shading_group(
        cmds,
        sky_shader,
        "chm_sunset_sky_SG",
    )
    cmds.sets(backdrop, edit=True, forceElement=sky_shading_group)

    distant_light_shader, distant_light_sg = _ensure_constant_surface_shader(
        cmds,
        "chm_sunset_distant_cloud_light_SURF",
        "chm_sunset_distant_cloud_light_SG",
        (1.0, 0.86, 0.69),
    )
    distant_shadow_shader, distant_shadow_sg = _ensure_constant_surface_shader(
        cmds,
        "chm_sunset_distant_cloud_shadow_SURF",
        "chm_sunset_distant_cloud_shadow_SG",
        (0.77, 0.65, 0.75),
    )
    distant_cloud_specs = (
        (
            -0.43,
            0.24,
            0.024,
            (
                (-2, 0, "shadow"), (-1, 0, "shadow"), (0, 0, "shadow"),
                (1, 0, "shadow"), (2, 0, "shadow"),
                (-1, 1, "light"), (0, 1, "light"), (1, 1, "light"),
                (2, 1, "light"), (0, 2, "light"), (1, 2, "light"),
            ),
        ),
        (
            -0.10,
            0.30,
            0.019,
            (
                (-2, 0, "shadow"), (-1, 0, "shadow"), (0, 0, "shadow"),
                (1, 0, "shadow"), (2, 0, "shadow"),
                (-1, 1, "light"), (0, 1, "light"), (1, 1, "light"),
                (0, 2, "light"),
            ),
        ),
        (
            0.29,
            0.34,
            0.017,
            (
                (-2, 0, "shadow"), (-1, 0, "shadow"), (0, 0, "shadow"),
                (1, 0, "shadow"), (2, 0, "shadow"),
                (-1, 1, "light"), (0, 1, "light"), (1, 1, "light"),
                (1, 2, "light"),
            ),
        ),
    )
    distant_cloud_groups = []
    distant_cloud_shapes = []
    for cloud_index, (
        anchor_x_ratio,
        anchor_y_ratio,
        block_ratio,
        block_pattern,
    ) in enumerate(distant_cloud_specs):
        cloud_group = cmds.group(
            empty=True,
            name="CloudHive_DistantCloud_{0:02d}_GRP".format(cloud_index),
        )
        cmds.parent(cloud_group, background_group, relative=True)
        cmds.setAttr(
            cloud_group + ".translate",
            backdrop_width * anchor_x_ratio,
            backdrop_height * anchor_y_ratio,
            0.0,
            type="double3",
        )
        distant_cloud_groups.append(cloud_group)
        block_size = backdrop_height * block_ratio
        for block_index, (grid_x, grid_y, shade) in enumerate(block_pattern):
            block = cmds.polyCube(
                width=block_size * 1.02,
                height=block_size * 1.02,
                depth=0.04,
                constructionHistory=False,
                name="CloudHive_DistantCloud_{0:02d}_block_{1:02d}".format(
                    cloud_index,
                    block_index,
                ),
            )[0]
            cmds.parent(block, cloud_group, relative=True)
            cmds.setAttr(
                block + ".translate",
                grid_x * block_size,
                grid_y * block_size,
                -backdrop_distance + 0.26,
                type="double3",
            )
            shading_group = (
                distant_light_sg if shade == "light" else distant_shadow_sg
            )
            cmds.sets(block, edit=True, forceElement=shading_group)
            block_shape = (cmds.listRelatives(block, shapes=True) or [None])[0]
            if block_shape:
                _set_background_render_stats(cmds, block_shape)
                distant_cloud_shapes.append(block_shape)

    backdrop_shape = (cmds.listRelatives(backdrop, shapes=True) or [None])[0]
    if backdrop_shape:
        _set_background_render_stats(cmds, backdrop_shape)

    return {
        "group": background_group,
        "backdrop": backdrop,
        "backdrop_shape": backdrop_shape,
        "ramp": ramp,
        "place_2d": place_2d,
        "sky_shader": sky_shader,
        "distant_cloud_groups": distant_cloud_groups,
        "distant_cloud_shapes": distant_cloud_shapes,
        "distant_cloud_light_shader": distant_light_shader,
        "distant_cloud_shadow_shader": distant_shadow_shader,
        "render_width": safe_width,
        "render_height": safe_height,
    }


def _ensure_surface_shading_group(cmds, shader, shading_group_name):
    """Create a shading group and connect one surface shader to it."""
    if (
        cmds.objExists(shading_group_name)
        and cmds.nodeType(shading_group_name) != "shadingEngine"
    ):
        cmds.delete(shading_group_name)
    shading_group = (
        shading_group_name
        if cmds.objExists(shading_group_name)
        else cmds.sets(
            renderable=True,
            noSurfaceShader=True,
            empty=True,
            name=shading_group_name,
        )
    )
    cmds.connectAttr(
        shader + ".outColor",
        shading_group + ".surfaceShader",
        force=True,
    )
    return shading_group


def _ensure_constant_surface_shader(
    cmds,
    shader_name,
    shading_group_name,
    color,
):
    """Create or update an unlit solid-color surface shader."""
    if cmds.objExists(shader_name) and cmds.nodeType(shader_name) != "surfaceShader":
        cmds.delete(shader_name)
    shader = (
        shader_name
        if cmds.objExists(shader_name)
        else cmds.shadingNode("surfaceShader", asShader=True, name=shader_name)
    )
    cmds.setAttr(shader + ".outColor", *color, type="double3")
    shading_group = _ensure_surface_shading_group(
        cmds,
        shader,
        shading_group_name,
    )
    return shader, shading_group


def _set_background_render_stats(cmds, shape):
    """Keep backdrop geometry camera-visible but absent from lighting rays."""
    attributes = {
        "primaryVisibility": 1,
        "castsShadows": 0,
        "receiveShadows": 0,
        "visibleInReflections": 0,
        "visibleInRefractions": 0,
        "aiVisibleInDiffuseReflection": 0,
        "aiVisibleInSpecularReflection": 0,
        "aiVisibleInTransmission": 0,
        "aiVisibleInVolume": 0,
        "aiVisibleInShadow": 0,
        "aiSelfShadows": 0,
    }
    for attribute, value in attributes.items():
        if cmds.attributeQuery(attribute, node=shape, exists=True):
            cmds.setAttr(shape + "." + attribute, value)


def create_ground_plane(scene_radius=9.0):
    """Create a simple ground plane under the honeycomb scene.

    Parameters:
        scene_radius (float): Approximate half-size for the ground plane.

    Returns:
        str: Maya transform name for the ground plane.
    """
    import maya.cmds as cmds

    group_name = "CloudHive_Ground_GRP"
    if not cmds.objExists(group_name):
        cmds.group(empty=True, name=group_name)

    ground_size = max(4.0, float(scene_radius) * 2.0)
    ground, _shape = cmds.polyPlane(
        width=ground_size,
        height=ground_size,
        subdivisionsX=1,
        subdivisionsY=1,
        name="CloudHive_Ground_PLN",
    )
    cmds.xform(ground, translation=(0.0, -0.02, 0.0), worldSpace=True)
    cmds.parent(ground, group_name)

    material = _create_maya_material(cmds, "chm_visual_ground_green_MAT", (0.24, 0.46, 0.26))
    _assign_maya_material(cmds, ground, material)
    return ground


def create_falling_resource_effects(
    drops,
    clouds,
    start_frame=1,
    end_frame=320,
    fall_duration=64,
):
    """Create animated nectar and pollen falling from clouds to the honeycomb.

    Parameters:
        drops (list[dict]): Resource drops from cloud_resource_module.
        clouds (list[dict]): Cloud dictionaries with source positions.
        start_frame (int): First animation frame.
        end_frame (int): Last animation frame.
        fall_duration (int): Frames used by each drop to reach the honeycomb.

    Returns:
        list[str]: Created Maya object names.
    """
    import maya.cmds as cmds

    group_name = "CloudHive_FallingResources_GRP"
    if cmds.objExists(group_name):
        cmds.delete(group_name)
    cmds.group(empty=True, name=group_name)
    prototype_group = cmds.group(
        empty=True,
        name="CloudHive_FallingResourcePrototypes_GRP",
    )
    cmds.parent(prototype_group, group_name)
    cmds.setAttr(prototype_group + ".visibility", 0)

    cloud_by_id = {cloud["id"]: cloud for cloud in clouds}
    nectar_material = create_voxel_material(cmds, "nectar_glow")
    pollen_material = create_voxel_material(cmds, "pollen_orange")
    glint_material = create_voxel_material(cmds, "honey_glint")
    nectar_prototype = ensure_voxel_cube_prototype(
        cmds,
        "CloudHive_falling_nectar_PROTOTYPE",
        0.22,
        nectar_material,
        prototype_group,
    )
    pollen_prototype = ensure_voxel_cube_prototype(
        cmds,
        "CloudHive_falling_pollen_PROTOTYPE",
        0.09,
        pollen_material,
        prototype_group,
    )
    glint_prototype = ensure_voxel_cube_prototype(
        cmds,
        "CloudHive_falling_glint_PROTOTYPE",
        0.07,
        glint_material,
        prototype_group,
    )

    created = []
    frame_span = max(1, int(end_frame) - int(start_frame))
    for index, drop in enumerate(drops):
        cloud = cloud_by_id.get(drop.get("source_cloud"))
        if cloud is None:
            continue

        resource_type = drop.get("resource_type", "nectar")
        cloud_x, cloud_y, cloud_z = cloud["position"]
        end_x, end_y, end_z = drop["position"]
        safe_duration = max(24, int(fall_duration))
        if "animation_start_frame" in drop and "animation_end_frame" in drop:
            local_start = int(drop["animation_start_frame"])
            local_end = int(drop["animation_end_frame"])
        else:
            start_window = max(1, frame_span - safe_duration - 4)
            local_start = int(start_frame) + (index * 10) % start_window
            local_end = min(
                int(end_frame),
                local_start + safe_duration + (index % 10),
            )
        drop["animation_start_frame"] = local_start
        drop["animation_end_frame"] = local_end

        jitter = 0.55 if resource_type == "nectar" else 0.95
        start_x = cloud_x + math.sin(index * 1.7) * jitter
        start_y = cloud_y - 0.55
        start_z = cloud_z + math.cos(index * 1.3) * jitter
        prototype = nectar_prototype if resource_type == "nectar" else pollen_prototype
        particle = create_voxel_cube_instances(
            cmds,
            prototype,
            [{
                "position": (start_x, start_y, start_z),
                "scale": (
                    1.12 if resource_type == "nectar" else 1.0,
                    1.72 if resource_type == "nectar" else 1.0,
                    1.12 if resource_type == "nectar" else 1.0,
                ),
            }],
            "CloudHive_{0}_falling_{1:03d}".format(resource_type, index),
            group_name,
        )[0]

        if local_start > int(start_frame):
            cmds.setKeyframe(particle, attribute="visibility", time=local_start - 1, value=0)
        cmds.setKeyframe(particle, attribute="visibility", time=local_start, value=1)
        cmds.setKeyframe(particle, attribute="translateX", time=local_start, value=start_x)
        cmds.setKeyframe(particle, attribute="translateY", time=local_start, value=start_y)
        cmds.setKeyframe(particle, attribute="translateZ", time=local_start, value=start_z)
        cmds.setKeyframe(particle, attribute="translateX", time=local_end, value=end_x)
        cmds.setKeyframe(particle, attribute="translateY", time=local_end, value=end_y + 0.35)
        cmds.setKeyframe(particle, attribute="translateZ", time=local_end, value=end_z)
        cmds.setKeyframe(particle, attribute="visibility", time=local_end, value=1)
        cmds.setKeyframe(particle, attribute="visibility", time=min(int(end_frame), local_end + 2), value=0)
        created.append(particle)

        if resource_type == "nectar":
            glint_records = []
            for glint_index in range(3):
                glint_records.append({
                    "position": (
                        start_x + (glint_index - 1) * 0.055,
                        start_y + 0.10 + glint_index * 0.08,
                        start_z - glint_index * 0.035,
                    ),
                    "scale": (
                        0.70 - glint_index * 0.12,
                        0.32,
                        0.70 - glint_index * 0.12,
                    ),
                })
            glints = create_voxel_cube_instances(
                cmds,
                glint_prototype,
                glint_records,
                "CloudHive_nectar_glint_{0:03d}".format(index),
                group_name,
            )
            for glint_index, glint in enumerate(glints):
                glint_start = min(local_end - 1, local_start + 2 + glint_index * 2)
                glint_end = min(int(end_frame), local_end + glint_index)
                if glint_start > int(start_frame):
                    cmds.setKeyframe(
                        glint,
                        attribute="visibility",
                        time=glint_start - 1,
                        value=0,
                    )
                cmds.setKeyframe(glint, attribute="visibility", time=glint_start, value=1)
                cmds.setKeyframe(glint, attribute="translateX", time=glint_start, value=start_x)
                cmds.setKeyframe(
                    glint,
                    attribute="translateY",
                    time=glint_start,
                    value=start_y + 0.10 + glint_index * 0.08,
                )
                cmds.setKeyframe(glint, attribute="translateZ", time=glint_start, value=start_z)
                cmds.setKeyframe(glint, attribute="translateX", time=glint_end, value=end_x)
                cmds.setKeyframe(
                    glint,
                    attribute="translateY",
                    time=glint_end,
                    value=end_y + 0.47 + glint_index * 0.08,
                )
                cmds.setKeyframe(glint, attribute="translateZ", time=glint_end, value=end_z)
                cmds.setKeyframe(
                    glint,
                    attribute="visibility",
                    time=min(int(end_frame), glint_end + 2),
                    value=0,
                )
                created.append(glint)

    cmds.playbackOptions(minTime=start_frame, maxTime=end_frame, loop="continuous")
    return created


def create_meadow_background(scene_radius=9.0, hive_radius=5.0, flower_count=70, grass_tuft_count=45, seed=77):
    """Create simple meadow flowers and grass around the honeycomb.

    Parameters:
        scene_radius (float): Approximate scene radius.
        hive_radius (float): Radius kept clear around the honeycomb.
        flower_count (int): Number of small field flowers.
        grass_tuft_count (int): Number of simple grass tufts.
        seed (int): Random seed for stable placement.

    Returns:
        dict: Created group and object counts.
    """
    import maya.cmds as cmds

    rng = random.Random(seed)
    group_name = "CloudHive_MeadowDetails_GRP"
    if cmds.objExists(group_name):
        cmds.delete(group_name)
    cmds.group(empty=True, name=group_name)

    stem_material = _create_maya_material(cmds, "chm_meadow_stem_green_MAT", (0.12, 0.42, 0.16))
    grass_material = _create_maya_material(cmds, "chm_meadow_grass_MAT", (0.18, 0.52, 0.2))
    petal_materials = [
        _create_maya_material(cmds, "chm_meadow_petal_white_MAT", (0.95, 0.92, 0.78)),
        _create_maya_material(cmds, "chm_meadow_petal_pink_MAT", (1.0, 0.52, 0.72)),
        _create_maya_material(cmds, "chm_meadow_petal_yellow_MAT", (1.0, 0.82, 0.18)),
    ]
    center_material = _create_maya_material(cmds, "chm_meadow_flower_center_MAT", (0.95, 0.55, 0.05))

    for index in range(max(0, int(flower_count))):
        x, z = _random_ring_position(rng, hive_radius, scene_radius * 0.92)
        flower_group = cmds.group(empty=True, name="CloudHive_FieldFlower_{0:03d}_GRP".format(index))
        cmds.parent(flower_group, group_name)

        stem_height = rng.uniform(0.18, 0.42)
        stem, _shape = cmds.polyCylinder(
            radius=0.018,
            height=stem_height,
            subdivisionsX=6,
            name="CloudHive_FieldFlower_{0:03d}_stem".format(index),
        )
        cmds.xform(stem, translation=(x, stem_height * 0.5, z), worldSpace=True)
        cmds.parent(stem, flower_group)
        _assign_maya_material(cmds, stem, stem_material)

        center_y = stem_height + 0.035
        center, _shape = cmds.polySphere(
            radius=0.045,
            name="CloudHive_FieldFlower_{0:03d}_center".format(index),
        )
        cmds.xform(center, translation=(x, center_y, z), worldSpace=True)
        cmds.parent(center, flower_group)
        _assign_maya_material(cmds, center, center_material)

        petal_material = rng.choice(petal_materials)
        petal_count = rng.choice([5, 6])
        for petal_index in range(petal_count):
            angle = math.tau * petal_index / petal_count
            petal, _shape = cmds.polySphere(
                radius=0.035,
                name="CloudHive_FieldFlower_{0:03d}_petal_{1:02d}".format(index, petal_index),
            )
            cmds.scale(1.35, 0.45, 0.9, petal, relative=True)
            cmds.xform(
                petal,
                translation=(x + math.cos(angle) * 0.07, center_y, z + math.sin(angle) * 0.07),
                worldSpace=True,
            )
            cmds.parent(petal, flower_group)
            _assign_maya_material(cmds, petal, petal_material)

    for index in range(max(0, int(grass_tuft_count))):
        x, z = _random_ring_position(rng, hive_radius * 0.85, scene_radius * 0.96)
        tuft_group = cmds.group(empty=True, name="CloudHive_GrassTuft_{0:03d}_GRP".format(index))
        cmds.parent(tuft_group, group_name)
        blade_count = rng.randint(3, 6)
        for blade_index in range(blade_count):
            blade_height = rng.uniform(0.16, 0.34)
            blade, _shape = cmds.polyCube(
                width=0.025,
                height=blade_height,
                depth=0.025,
                name="CloudHive_GrassTuft_{0:03d}_blade_{1:02d}".format(index, blade_index),
            )
            cmds.xform(
                blade,
                translation=(x + rng.uniform(-0.08, 0.08), blade_height * 0.5, z + rng.uniform(-0.08, 0.08)),
                rotation=(0.0, rng.uniform(0.0, 180.0), rng.uniform(-18.0, 18.0)),
                worldSpace=True,
            )
            cmds.parent(blade, tuft_group)
            _assign_maya_material(cmds, blade, grass_material)

    return {
        "group": group_name,
        "flower_count": max(0, int(flower_count)),
        "grass_tuft_count": max(0, int(grass_tuft_count)),
    }


def create_beehive_box(scene_radius=9.0, box_count=2, seed=88):
    """Create simple stylized beehive boxes near the edge of the meadow.

    Parameters:
        scene_radius (float): Approximate scene radius.
        box_count (int): Number of beehive boxes.
        seed (int): Random seed for stable placement.

    Returns:
        list[str]: Created beehive box group names.
    """
    import maya.cmds as cmds

    rng = random.Random(seed)
    group_name = "CloudHive_BeehiveBoxes_GRP"
    if cmds.objExists(group_name):
        cmds.delete(group_name)
    cmds.group(empty=True, name=group_name)

    wood_material = _create_maya_material(cmds, "chm_beehive_wood_MAT", (0.78, 0.56, 0.24))
    roof_material = _create_maya_material(cmds, "chm_beehive_roof_MAT", (0.46, 0.28, 0.12))
    entrance_material = _create_maya_material(cmds, "chm_beehive_entrance_MAT", (0.08, 0.05, 0.025))

    created = []
    for index in range(max(0, int(box_count))):
        angle = (math.tau / max(1, int(box_count))) * index + rng.uniform(-0.35, 0.35)
        radius = scene_radius * rng.uniform(0.62, 0.78)
        x = math.cos(angle) * radius
        z = math.sin(angle) * radius

        hive_group = cmds.group(empty=True, name="CloudHive_BeehiveBox_{0:02d}_GRP".format(index))
        cmds.parent(hive_group, group_name)
        created.append(hive_group)

        base, _shape = cmds.polyCube(
            width=0.9,
            height=0.55,
            depth=0.65,
            name="CloudHive_BeehiveBox_{0:02d}_base".format(index),
        )
        cmds.xform(base, translation=(x, 0.275, z), rotation=(0.0, -math.degrees(angle) + 90.0, 0.0), worldSpace=True)
        cmds.parent(base, hive_group)
        _assign_maya_material(cmds, base, wood_material)

        roof, _shape = cmds.polyCube(
            width=1.05,
            height=0.12,
            depth=0.78,
            name="CloudHive_BeehiveBox_{0:02d}_roof".format(index),
        )
        cmds.xform(roof, translation=(x, 0.62, z), rotation=(0.0, -math.degrees(angle) + 90.0, 0.0), worldSpace=True)
        cmds.parent(roof, hive_group)
        _assign_maya_material(cmds, roof, roof_material)

        entrance, _shape = cmds.polyCylinder(
            radius=0.09,
            height=0.035,
            subdivisionsX=16,
            name="CloudHive_BeehiveBox_{0:02d}_entrance".format(index),
        )
        front_x = x + math.cos(angle + math.pi) * 0.34
        front_z = z + math.sin(angle + math.pi) * 0.34
        cmds.xform(
            entrance,
            translation=(front_x, 0.31, front_z),
            rotation=(90.0, 0.0, -math.degrees(angle)),
            worldSpace=True,
        )
        cmds.parent(entrance, hive_group)
        _assign_maya_material(cmds, entrance, entrance_material)

        for stripe_index in range(2):
            stripe, _shape = cmds.polyCube(
                width=0.96,
                height=0.035,
                depth=0.68,
                name="CloudHive_BeehiveBox_{0:02d}_stripe_{1:02d}".format(index, stripe_index),
            )
            cmds.xform(
                stripe,
                translation=(x, 0.22 + stripe_index * 0.18, z),
                rotation=(0.0, -math.degrees(angle) + 90.0, 0.0),
                worldSpace=True,
            )
            cmds.parent(stripe, hive_group)
            _assign_maya_material(cmds, stripe, roof_material)

    return created


def create_scene_labels_optional(summary=None):
    """Create optional Maya text labels for presentation/debugging.

    Parameters:
        summary (dict | None): Optional summary dictionary from main.run_simulation().

    Returns:
        list[str]: Maya object names created for labels.
    """
    import maya.cmds as cmds

    group_name = "CloudHive_Labels_GRP"
    if not cmds.objExists(group_name):
        cmds.group(empty=True, name=group_name)

    if summary is None:
        label_text = "Cloud-Hive Bloomfield"
    else:
        label_text = (
            "Cloud-Hive Bloomfield\\n"
            "Cells: {0}  Drops: {1}\\n"
            "Tasks: {2}  Paths: {3}"
        ).format(
            summary.get("cell_count", 0),
            summary.get("drop_count", 0),
            summary.get("task_count", 0),
            summary.get("tasks_with_paths", 0),
        )

    text_nodes = cmds.textCurves(
        font="Arial",
        text=label_text,
        name="CloudHive_Summary_Label",
    )
    created = text_nodes if isinstance(text_nodes, list) else [text_nodes]
    for node in created:
        if cmds.objExists(node):
            cmds.xform(node, translation=(-5.8, 0.05, -6.3), rotation=(90.0, 0.0, 0.0), worldSpace=True)
            cmds.scale(0.25, 0.25, 0.25, node, relative=True)
            cmds.parent(node, group_name)

    return created


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
        if cmds.attributeQuery("color", node=material_name, exists=True):
            cmds.setAttr(material_name + ".color", *color, type="double3")
        _apply_visual_lambert_fill(cmds, material_name, color)
        return material_name

    material = cmds.shadingNode("lambert", asShader=True, name=material_name)
    cmds.setAttr(
        material + ".color",
        color[0],
        color[1],
        color[2],
        type="double3",
    )
    _apply_visual_lambert_fill(cmds, material, color)
    return material


def _apply_visual_lambert_fill(cmds, material, color):
    """Keep bees and auxiliary stylized geometry readable in render shadows."""
    if cmds.attributeQuery("ambientColor", node=material, exists=True):
        cmds.setAttr(
            material + ".ambientColor",
            *(component * 0.16 for component in color),
            type="double3",
        )
    if cmds.attributeQuery("incandescence", node=material, exists=True):
        cmds.setAttr(
            material + ".incandescence",
            *(component * 0.07 for component in color),
            type="double3",
        )


def _assign_maya_material(cmds, node, material):
    """Assign a Maya material to an object.

    Parameters:
        cmds: Imported maya.cmds module.
        node (str): Maya object name.
        material (str): Maya material node name.

    Returns:
        None.
    """
    cmds.select(node, replace=True)
    cmds.hyperShade(assign=material)
    cmds.select(clear=True)


def _random_ring_position(rng, inner_radius, outer_radius):
    """Return a deterministic random XZ position between two radii."""
    safe_inner = max(0.0, float(inner_radius))
    safe_outer = max(safe_inner + 0.1, float(outer_radius))
    angle = rng.uniform(0.0, math.tau)
    radius = math.sqrt(rng.uniform(safe_inner * safe_inner, safe_outer * safe_outer))
    return math.cos(angle) * radius, math.sin(angle) * radius


def _parent_known_scene_groups(additional_groups=None):
    """Parent generated CloudHive groups under the visualization root group.

    Parameters:
        additional_groups (list[str] | None): Extra generated groups, such as
            the current cycle's prepared stage container.

    Returns:
        None.
    """
    import maya.cmds as cmds

    if not cmds.objExists(ROOT_GROUP):
        return

    generated_groups = [
        "CloudHive_Honeycomb_GRP",
        "CloudHive_Clouds_GRP",
        "CloudHive_CloudFlowers_GRP",
        "CloudHive_MeadowDetails_GRP",
        "CloudHive_BeehiveBoxes_GRP",
        "CloudHive_Bees_GRP",
        "CloudHive_CellResources_GRP",
        "CloudHive_Ground_GRP",
        "CloudHive_CameraLight_GRP",
        "CloudHive_Labels_GRP",
    ]
    generated_groups.extend(additional_groups or [])

    for group_name in generated_groups:
        if not cmds.objExists(group_name):
            continue
        parent = cmds.listRelatives(group_name, parent=True)
        if parent and parent[0] == ROOT_GROUP:
            continue
        try:
            cmds.parent(group_name, ROOT_GROUP)
        except RuntimeError:
            pass
