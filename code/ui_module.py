"""Maya control panel for Cloud-Hive Meadow."""

import copy


WINDOW_NAME = "CloudHiveControlPanel"
WINDOW_TITLE = "Cloud-Hive Bloomfield Control Panel"
GUIDE_WINDOW_NAME = "CloudHiveDemoGuidePanel"
GUIDE_WINDOW_TITLE = "Cloud-Hive Bloomfield Demo Guide"
CONTROLS = {}
GUIDE_CONTROLS = {}
LAST_SCENE_DATA = None
CURRENT_PARAMETERS = None
SIMULATION_STEP = 0
CURRENT_DEMO_STAGE = 0
PLAYBACK_ACTIVE = False
PLAYBACK_JOB_ID = None
PLAYBACK_SERIAL = 0
PLAYBACK_END_FRAME = None
CYCLE_AUTHORING_BUSY = False
GUIDE_PLAYBACK_STATUS = "Ready"
LAST_GUIDE_PANEL_DATA = None
GUIDE_PULSE_JOB_ID = None
GUIDE_PULSE_PHASE = None

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
GUIDE_STATUS_FIELDS = (
    ("new_drops", "New Drops", "int"),
    ("direct_storage", "Direct Storage", "int"),
    ("transport_tasks", "Transport Tasks", "int"),
    ("cleanup_tasks", "Cleanup Tasks", "int"),
    ("collection_tasks", "Collection Tasks", "int"),
    ("active_bees", "Active Bees", "int"),
    ("queued_tasks", "Queued Tasks", "int"),
    ("stored_nectar", "Stored Nectar", "float"),
    ("stored_pollen", "Stored Pollen", "float"),
)
GUIDE_COMPACT_LEGEND_DETAILS = {
    "nectar_drop": "Gold sphere",
    "pollen_drop": "Orange sphere",
    "honey_cell": "Gold hex  |  nectar",
    "pollen_cell": "Grained hex  |  pollen",
    "empty_cell": "Cream outline  |  available",
    "capped_cell": "Cream cap  |  blocked",
    "queen_chamber": "Amber hex  |  reserved",
    "idle_bee": "Worker waiting on hive",
    "mapping_line": "Cyan drop-to-cell line",
    "validation_matched": "Green hex  |  direct",
    "validation_wrong": "Orange hex  |  transport",
    "validation_blocked": "Red crossed hex  |  cleanup",
    "validation_unmapped": "Gray hex  |  no valid cell",
    "direct_storage": "Gold resource enters cell",
    "transport_task": "Blue relocation marker",
    "cleanup_task": "Red invalid-drop marker",
    "active_transport_bees": "Selected workers crawling",
    "task_endpoints": "Source hex -> target ring",
    "active_bfs_routes": "Bright task-colored paths",
    "queued_bfs_routes": "Muted dashed paths",
    "nectar_collection_trigger": "Gold cloud-source halo",
    "pollen_collection_trigger": "Purple cloud-source halo",
    "queued_collection": "Muted  |  waiting for bee",
    "active_collection_bees": "Workers collecting",
    "hive_crawl": "Mint  |  on-hive movement",
    "cloud_flight": "Magenta  |  cloud flight",
    "nectar_payload": "Gold droplet payload",
    "pollen_payload": "Orange-purple grains",
    "nectar_deposit": "Gold storage update",
    "pollen_deposit": "Orange grain update",
    "full_storage": "Cream hex at capacity",
    "collection_reentry": "Purple return ring",
}


def _int_value(cmds, name):
    """Return an integer slider value from the active Maya UI."""
    return cmds.intSliderGrp(CONTROLS[name], query=True, value=True)


def _float_value(cmds, name):
    """Return a float slider value from the active Maya UI."""
    return cmds.floatSliderGrp(CONTROLS[name], query=True, value=True)


def _bool_value(cmds, name):
    """Return a checkbox value from the active Maya UI."""
    return cmds.checkBox(CONTROLS[name], query=True, value=True)


def _ensure_controls(cmds):
    """Rebuild the panel when Maya invokes a callback from a stale window."""
    required = (
        "hive_size",
        "cell_size",
        "voxel_density",
        "honey_ratio",
        "pollen_ratio",
        "capped_ratio",
        "cloud_count",
        "flower_count",
        "nectar_drop_rate",
        "pollen_drop_rate",
        "wind_strength",
        "wind_direction",
        "bee_count",
        "animation_end",
        "drop_fall_frames",
        "bee_frame_step",
        "show_paths",
        "show_demo_guide",
        "show_demo_legend",
        "show_demo_stage_hint",
        "open_demo_guide",
        "next_step",
        "status",
    )
    controls_are_valid = all(
        name in CONTROLS and cmds.control(CONTROLS[name], exists=True)
        for name in required
    )
    if not controls_are_valid:
        show_ui(LAST_SCENE_DATA)


def _read_parameters(cmds):
    """Build a fresh parameter dictionary from the current GUI values."""
    from main import load_parameters

    parameters = copy.deepcopy(load_parameters())
    hive = parameters["hive"]
    clouds = parameters["clouds"]
    drops = parameters["drops"]
    bees = parameters["bees"]
    visual = parameters.setdefault("visual", {})
    simulation = parameters.setdefault("simulation", {})

    hive["size"] = _int_value(cmds, "hive_size")
    hive["cell_size"] = _float_value(cmds, "cell_size")
    visual["voxel_density"] = _int_value(cmds, "voxel_density")

    honey_ratio = _float_value(cmds, "honey_ratio")
    pollen_ratio = _float_value(cmds, "pollen_ratio")
    capped_ratio = _float_value(cmds, "capped_ratio")
    hive["honey_ratio"] = honey_ratio
    hive["pollen_ratio"] = pollen_ratio
    hive["capped_ratio"] = capped_ratio
    hive["empty_ratio"] = max(0.0, 1.0 - honey_ratio - pollen_ratio - capped_ratio)

    clouds["cloud_count"] = _int_value(cmds, "cloud_count")
    drops["nectar_drop_rate"] = _int_value(cmds, "nectar_drop_rate")
    drops["pollen_drop_rate"] = _int_value(cmds, "pollen_drop_rate")
    drops["wind_strength"] = _float_value(cmds, "wind_strength")
    drops["wind_direction_degrees"] = _float_value(cmds, "wind_direction")
    bees["bee_count"] = _int_value(cmds, "bee_count")

    visual["flowers_per_cloud"] = _int_value(cmds, "flower_count")
    visual["animation_end"] = _int_value(cmds, "animation_end")
    visual["drop_fall_frames"] = _int_value(cmds, "drop_fall_frames")
    visual["bee_frame_step"] = _int_value(cmds, "bee_frame_step")
    visual["show_paths"] = _bool_value(cmds, "show_paths")
    visual["show_demo_guide"] = _bool_value(cmds, "show_demo_guide")
    visual["show_demo_legend"] = _bool_value(cmds, "show_demo_legend")
    visual["show_demo_stage_hint"] = _bool_value(
        cmds,
        "show_demo_stage_hint",
    )
    simulation["cycle"] = SIMULATION_STEP
    return parameters


def build_config_from_ui(controls=None):
    """Build an integration config dictionary from the current Maya UI controls.

    Parameters:
        controls (dict | None): Optional control mapping. When provided, it
            becomes the active mapping used by the UI callbacks.

    Returns:
        dict: Configuration dictionary for run_simulation() or create_maya_scene().
    """
    import maya.cmds as cmds

    if controls is not None:
        CONTROLS.update(controls)
    _ensure_controls(cmds)
    return _read_parameters(cmds)


def update_demo_guide_options(*_args):
    """Apply presentation-guide checkboxes without rebuilding the Maya scene."""
    import maya.cmds as cmds
    from main import load_parameters
    from visual_module import clear_demo_guide, update_demo_guide

    global CURRENT_PARAMETERS

    _ensure_controls(cmds)
    enabled = _bool_value(cmds, "show_demo_guide")
    show_legend = _bool_value(cmds, "show_demo_legend")
    show_stage_hint = _bool_value(cmds, "show_demo_stage_hint")

    if CURRENT_PARAMETERS is None:
        CURRENT_PARAMETERS = copy.deepcopy(load_parameters())
    visual = CURRENT_PARAMETERS.setdefault("visual", {})
    visual["show_demo_guide"] = enabled
    visual["show_demo_legend"] = show_legend
    visual["show_demo_stage_hint"] = show_stage_hint

    for control_name in ("show_demo_legend", "show_demo_stage_hint"):
        control = CONTROLS.get(control_name)
        if control and cmds.control(control, exists=True):
            cmds.checkBox(control, edit=True, enable=enabled)
    open_button = CONTROLS.get("open_demo_guide")
    if open_button and cmds.control(open_button, exists=True):
        cmds.button(open_button, edit=True, enable=enabled)

    if LAST_SCENE_DATA is None:
        if enabled:
            show_demo_guide_panel(None)
        else:
            clear_demo_guide()
            close_demo_guide_panel()
        return None

    scene_visual = LAST_SCENE_DATA.setdefault(
        "parameters",
        {},
    ).setdefault("visual", {})
    scene_visual["show_demo_guide"] = enabled
    scene_visual["show_demo_legend"] = show_legend
    scene_visual["show_demo_stage_hint"] = show_stage_hint
    guide_state = update_demo_guide(
        LAST_SCENE_DATA,
        CURRENT_DEMO_STAGE,
        enabled=enabled,
        show_legend=show_legend,
        show_stage_hint=show_stage_hint,
    )
    if enabled:
        show_demo_guide_panel(LAST_SCENE_DATA)
    else:
        close_demo_guide_panel()
    cmds.refresh(force=True)
    print(
        "Demo Guide: {0} | Legend: {1} | Stage Hint: {2}".format(
            "on" if enabled else "off",
            "on" if show_legend else "off",
            "on" if show_stage_hint else "off",
        )
    )
    return guide_state


def _capture_cell_state(scene_data):
    """Keep resource and capped state between simulation steps."""
    if not scene_data:
        return None
    fields = (
        "id",
        "type",
        "nectar",
        "pollen",
        "capacity",
        "reserved_amount",
        "is_blocked",
        "blocked_by_capacity",
        "queen_role",
    )
    return [
        {field: cell[field] for field in fields if field in cell}
        for cell in scene_data.get("cells", [])
    ]


def _set_status(cmds, label):
    """Update the UI status label when the window is available."""
    if "status" in CONTROLS and cmds.control(CONTROLS["status"], exists=True):
        cmds.text(CONTROLS["status"], edit=True, label=label)


def _guide_control_exists(cmds, control_name):
    """Return whether one cached Demo Guide Panel control is still valid."""
    control = GUIDE_CONTROLS.get(control_name)
    return bool(control and cmds.control(control, exists=True))


def _set_guide_control_text(cmds, control_name, label):
    """Update one cached guide text control when its window is open."""
    if _guide_control_exists(cmds, control_name):
        cmds.text(
            GUIDE_CONTROLS[control_name],
            edit=True,
            label=str(label),
        )


def _mix_guide_color(color, target, amount):
    """Blend an RGB color toward another RGB color."""
    safe_amount = max(0.0, min(1.0, float(amount)))
    return tuple(
        max(
            0.0,
            min(
                1.0,
                float(component) * (1.0 - safe_amount)
                + float(target_component) * safe_amount,
            ),
        )
        for component, target_component in zip(color, target)
    )


def _guide_hex_color(color):
    """Return an XPM-compatible hex color from normalized RGB values."""
    channels = [
        max(0, min(255, int(round(float(component) * 255.0))))
        for component in color
    ]
    return "#{0:02X}{1:02X}{2:02X}".format(*channels)


def _build_guide_icon_pixels(icon_kind, pulse=False, size=24):
    """Build a tiny semantic icon as an XPM character grid."""
    grid = [["." for _column in range(size)] for _row in range(size)]

    def set_pixel(x_value, y_value, character="X"):
        x_value = int(round(x_value))
        y_value = int(round(y_value))
        if 0 <= x_value < size and 0 <= y_value < size:
            grid[y_value][x_value] = character

    def draw_line(x_start, y_start, x_end, y_end, character="X", width=1):
        delta_x = int(x_end) - int(x_start)
        delta_y = int(y_end) - int(y_start)
        steps = max(abs(delta_x), abs(delta_y), 1)
        for step in range(steps + 1):
            x_value = int(round(x_start + delta_x * step / float(steps)))
            y_value = int(round(y_start + delta_y * step / float(steps)))
            for offset_x in range(-(width // 2), width // 2 + 1):
                for offset_y in range(-(width // 2), width // 2 + 1):
                    set_pixel(
                        x_value + offset_x,
                        y_value + offset_y,
                        character,
                    )

    def draw_circle(
        center_x,
        center_y,
        radius,
        character="X",
        fill=True,
    ):
        radius_squared = float(radius) * float(radius)
        inner_radius_squared = max(0.0, float(radius - 1.5) ** 2)
        for y_value in range(
            int(center_y - radius - 1),
            int(center_y + radius + 2),
        ):
            for x_value in range(
                int(center_x - radius - 1),
                int(center_x + radius + 2),
            ):
                distance_squared = (
                    (float(x_value) - float(center_x)) ** 2
                    + (float(y_value) - float(center_y)) ** 2
                )
                if distance_squared > radius_squared:
                    continue
                if fill or distance_squared >= inner_radius_squared:
                    set_pixel(x_value, y_value, character)

    def hex_points(center_x=12, center_y=12, radius=9):
        half_height = max(2, int(round(radius * 0.78)))
        half_width = int(radius)
        inset = max(2, int(round(radius * 0.48)))
        return (
            (center_x - inset, center_y - half_height),
            (center_x + inset, center_y - half_height),
            (center_x + half_width, center_y),
            (center_x + inset, center_y + half_height),
            (center_x - inset, center_y + half_height),
            (center_x - half_width, center_y),
        )

    def draw_hex(
        center_x=12,
        center_y=12,
        radius=9,
        character="X",
        fill=False,
    ):
        points = hex_points(center_x, center_y, radius)
        if fill:
            half_height = max(2, int(round(radius * 0.78)))
            half_width = int(radius)
            inset = max(2, int(round(radius * 0.48)))
            for y_value in range(center_y - half_height, center_y + half_height + 1):
                relative_y = abs(y_value - center_y) / float(half_height)
                row_half_width = int(round(
                    half_width - max(0.0, relative_y - 0.05)
                    * (half_width - inset)
                ))
                for x_value in range(
                    center_x - row_half_width,
                    center_x + row_half_width + 1,
                ):
                    set_pixel(x_value, y_value, character)
        for index, first_point in enumerate(points):
            second_point = points[(index + 1) % len(points)]
            draw_line(
                first_point[0],
                first_point[1],
                second_point[0],
                second_point[1],
                character,
                width=2,
            )

    def draw_arrow(x_start, y_start, x_end, y_end, character="A"):
        draw_line(x_start, y_start, x_end, y_end, character, width=2)
        if abs(x_end - x_start) >= abs(y_end - y_start):
            direction = 1 if x_end >= x_start else -1
            draw_line(x_end, y_end, x_end - direction * 4, y_end - 3, character, 2)
            draw_line(x_end, y_end, x_end - direction * 4, y_end + 3, character, 2)
        else:
            direction = 1 if y_end >= y_start else -1
            draw_line(x_end, y_end, x_end - 3, y_end - direction * 4, character, 2)
            draw_line(x_end, y_end, x_end + 3, y_end - direction * 4, character, 2)

    if icon_kind == "nectar_sphere":
        draw_circle(12, 12, 7, "X", fill=True)
        draw_circle(9, 9, 2, "H", fill=True)
    elif icon_kind == "pollen_sphere":
        draw_circle(12, 12, 7, "X", fill=True)
        for grain_x, grain_y in ((9, 9), (15, 10), (11, 15), (15, 15)):
            draw_circle(grain_x, grain_y, 1.4, "A", fill=True)
    elif icon_kind in (
        "hex_fill",
        "hex_grains",
        "hex_capped",
        "hex_queen",
        "hex_full",
    ):
        draw_hex(character="X", fill=True)
        if icon_kind == "hex_grains":
            for grain_x, grain_y in ((9, 10), (14, 9), (11, 14), (16, 14)):
                draw_circle(grain_x, grain_y, 1.2, "A", fill=True)
        elif icon_kind == "hex_capped":
            draw_line(6, 9, 18, 9, "A", width=2)
            draw_line(5, 13, 19, 13, "A", width=2)
        elif icon_kind == "hex_queen":
            draw_hex(12, 12, 5, "A", fill=False)
            draw_line(9, 12, 11, 9, "H", width=1)
            draw_line(11, 9, 13, 12, "H", width=1)
            draw_line(13, 12, 15, 9, "H", width=1)
        elif icon_kind == "hex_full":
            draw_line(6, 8, 18, 8, "A", width=2)
            draw_line(5, 12, 19, 12, "A", width=2)
            draw_line(7, 16, 17, 16, "A", width=2)
    elif icon_kind in (
        "hex_outline",
        "hex_matched",
        "hex_warning",
        "hex_blocked",
        "hex_unknown",
    ):
        draw_hex(character="X", fill=False)
        if icon_kind == "hex_matched":
            draw_line(8, 12, 11, 15, "A", width=2)
            draw_line(11, 15, 17, 8, "A", width=2)
        elif icon_kind == "hex_warning":
            draw_line(12, 7, 12, 14, "A", width=2)
            draw_circle(12, 17, 1.3, "A", fill=True)
        elif icon_kind == "hex_blocked":
            draw_line(8, 8, 16, 16, "A", width=2)
            draw_line(16, 8, 8, 16, "A", width=2)
        elif icon_kind == "hex_unknown":
            draw_line(9, 9, 12, 7, "A", width=2)
            draw_line(12, 7, 15, 9, "A", width=2)
            draw_line(15, 9, 12, 13, "A", width=2)
            draw_circle(12, 17, 1.3, "A", fill=True)
    elif icon_kind in ("bee", "bee_active"):
        if icon_kind == "bee_active":
            draw_circle(12, 12, 10, "A", fill=False)
        draw_circle(8, 9, 4, "H", fill=False)
        draw_circle(16, 9, 4, "H", fill=False)
        draw_circle(12, 13, 6, "X", fill=True)
        draw_line(8, 11, 16, 11, "A", width=2)
        draw_line(8, 15, 16, 15, "A", width=2)
        draw_line(12, 18, 12, 21, "A", width=1)
    elif icon_kind == "line_mapping":
        draw_circle(4, 6, 2, "H", fill=True)
        draw_circle(20, 18, 2, "A", fill=False)
        draw_arrow(6, 7, 18, 17, "X")
    elif icon_kind == "direct_storage":
        draw_hex(12, 16, 7, "X", fill=False)
        draw_circle(12, 5, 3, "A", fill=True)
        draw_arrow(12, 8, 12, 14, "A")
    elif icon_kind in ("task_transport", "task_cleanup"):
        draw_line(12, 3, 20, 12, "X", width=2)
        draw_line(20, 12, 12, 21, "X", width=2)
        draw_line(12, 21, 4, 12, "X", width=2)
        draw_line(4, 12, 12, 3, "X", width=2)
        if icon_kind == "task_transport":
            draw_arrow(7, 12, 17, 12, "A")
        else:
            draw_line(8, 8, 16, 16, "A", width=2)
            draw_line(16, 8, 8, 16, "A", width=2)
    elif icon_kind == "source_target":
        draw_hex(5, 12, 4, "X", fill=False)
        draw_arrow(9, 12, 16, 12, "A")
        draw_circle(19, 12, 4, "X", fill=False)
    elif icon_kind == "line_active_route":
        draw_circle(4, 16, 2, "X", fill=True)
        draw_line(5, 15, 10, 10, "X", width=2)
        draw_line(10, 10, 15, 14, "A", width=2)
        draw_line(15, 14, 20, 7, "X", width=2)
        draw_circle(20, 7, 3, "A", fill=False)
    elif icon_kind == "line_queued":
        for x_start in (2, 8, 14):
            draw_line(x_start, 12, x_start + 3, 12, "X", width=1)
        draw_circle(21, 12, 2, "A", fill=False)
    elif icon_kind == "collection_trigger":
        draw_circle(12, 12, 9, "A", fill=False)
        draw_circle(12, 12, 5, "X", fill=True)
        draw_circle(10, 9, 1.4, "H", fill=True)
    elif icon_kind == "collection_queued":
        draw_circle(9, 10, 4, "X", fill=True)
        draw_circle(14, 8, 5, "X", fill=True)
        draw_circle(18, 11, 4, "X", fill=True)
        draw_line(5, 13, 20, 13, "X", width=2)
        for x_start in (8, 14):
            draw_line(x_start, 17, x_start + 3, 20, "A", width=1)
    elif icon_kind == "line_crawl":
        draw_hex(4, 15, 3, "A", fill=False)
        draw_line(7, 15, 11, 10, "X", width=2)
        draw_line(11, 10, 16, 14, "X", width=2)
        draw_line(16, 14, 21, 8, "X", width=2)
    elif icon_kind == "line_flight":
        draw_hex(5, 19, 3, "A", fill=False)
        draw_line(7, 17, 11, 13, "X", width=2)
        draw_line(11, 13, 14, 8, "X", width=2)
        draw_arrow(14, 8, 20, 4, "X")
    elif icon_kind == "nectar_droplet":
        draw_circle(12, 14, 6, "X", fill=True)
        draw_line(12, 3, 7, 13, "X", width=2)
        draw_line(12, 3, 17, 13, "X", width=2)
        draw_circle(10, 12, 1.5, "H", fill=True)
    elif icon_kind == "pollen_cluster":
        draw_circle(8, 14, 5, "X", fill=True)
        draw_circle(15, 14, 5, "A", fill=True)
        draw_circle(12, 8, 5, "X", fill=True)
        draw_circle(10, 7, 1.3, "H", fill=True)
    elif icon_kind in ("deposit_hex", "deposit_grains"):
        draw_hex(12, 16, 7, "X", fill=False)
        if icon_kind == "deposit_hex":
            draw_circle(12, 5, 3, "A", fill=True)
        else:
            for grain_x, grain_y in ((9, 5), (13, 4), (16, 7)):
                draw_circle(grain_x, grain_y, 1.7, "A", fill=True)
        draw_arrow(12, 8, 12, 14, "A")
    elif icon_kind == "reentry":
        draw_circle(12, 12, 8, "X", fill=False)
        draw_arrow(20, 8, 17, 15, "A")
        draw_circle(12, 12, 2, "A", fill=True)
    else:
        draw_circle(12, 12, 7, "X", fill=False)

    if pulse:
        halo_pixels = []
        for y_value, row in enumerate(grid):
            for x_value, character in enumerate(row):
                if character == ".":
                    continue
                for offset_x, offset_y in (
                    (-1, 0),
                    (1, 0),
                    (0, -1),
                    (0, 1),
                ):
                    halo_x = x_value + offset_x
                    halo_y = y_value + offset_y
                    if (
                        0 <= halo_x < size
                        and 0 <= halo_y < size
                        and grid[halo_y][halo_x] == "."
                    ):
                        halo_pixels.append((halo_x, halo_y))
        for halo_x, halo_y in halo_pixels:
            set_pixel(halo_x, halo_y, "G")
    return ["".join(row) for row in grid]


def _guide_icon_xpm_path(cmds, item, pulse=False):
    """Create or reuse one tiny Maya-native XPM icon in the user temp cache."""
    import os

    icon_kind = str(item.get("icon_kind", "unknown"))
    color = tuple(item.get("color", (0.75, 0.75, 0.75)))
    accent = tuple(item.get(
        "accent_color",
        _mix_guide_color(color, (1.0, 1.0, 1.0), 0.35),
    ))
    primary = _mix_guide_color(
        color,
        (1.0, 1.0, 1.0),
        0.28 if pulse else 0.0,
    )
    accent = _mix_guide_color(
        accent,
        (1.0, 1.0, 1.0),
        0.22 if pulse else 0.0,
    )
    highlight = _mix_guide_color(primary, (1.0, 1.0, 1.0), 0.58)
    glow = _mix_guide_color(primary, (1.0, 1.0, 1.0), 0.72)
    pixels = _build_guide_icon_pixels(icon_kind, pulse=pulse)
    safe_kind = "".join(
        character if character.isalnum() else "_"
        for character in icon_kind
    )
    cache_root = cmds.internalVar(userTmpDir=True)
    cache_directory = os.path.join(cache_root, "CloudHiveDemoGuideIcons")
    os.makedirs(cache_directory, exist_ok=True)
    color_token = _guide_hex_color(color).replace("#", "")
    accent_token = _guide_hex_color(accent).replace("#", "")
    file_name = "chm_{0}_{1}_{2}{3}.xpm".format(
        safe_kind,
        color_token,
        accent_token,
        "_pulse" if pulse else "",
    )
    icon_path = os.path.join(cache_directory, file_name)
    variable_name = os.path.splitext(file_name)[0]
    lines = [
        "/* XPM */",
        "static char * {0}[] = {{".format(variable_name),
        '"24 24 5 1",',
        '". c None",',
        '"X c {0}",'.format(_guide_hex_color(primary)),
        '"A c {0}",'.format(_guide_hex_color(accent)),
        '"H c {0}",'.format(_guide_hex_color(highlight)),
        '"G c {0}",'.format(_guide_hex_color(glow)),
    ]
    for row_index, row in enumerate(pixels):
        suffix = "," if row_index < len(pixels) - 1 else ""
        lines.append('"{0}"{1}'.format(row, suffix))
    lines.append("};")
    content = "\n".join(lines) + "\n"
    try:
        prior_content = None
        if os.path.exists(icon_path):
            with open(icon_path, "r", encoding="ascii") as icon_file:
                prior_content = icon_file.read()
        if prior_content != content:
            with open(icon_path, "w", encoding="ascii", newline="\n") as icon_file:
                icon_file.write(content)
        return icon_path
    except OSError:
        return None


def _guide_legend_signature(items):
    """Return a stable signature for the currently visible legend rows."""
    return tuple(
        (
            item.get("key"),
            item.get("label"),
            item.get("detail"),
            tuple(item.get("color", ())),
            tuple(item.get("accent_color", ())),
            item.get("icon_kind"),
            bool(item.get("animated")),
            tuple(tuple(value) for value in item.get("pulse_ranges", [])),
        )
        for item in items
    )


def _create_guide_legend_item(cmds, parent, item):
    """Create one semantic icon and concise two-line legend item."""
    neutral_background = (0.20, 0.20, 0.20)
    item_frame = cmds.frameLayout(
        labelVisible=False,
        borderVisible=False,
        enableBackground=True,
        backgroundColor=neutral_background,
        width=252,
        height=46,
        marginWidth=4,
        marginHeight=2,
        parent=parent,
    )
    item_row = cmds.rowLayout(
        numberOfColumns=2,
        columnWidth2=(36, 208),
        adjustableColumn=2,
        width=244,
        height=40,
        parent=item_frame,
    )
    base_image = _guide_icon_xpm_path(cmds, item, pulse=False)
    pulse_image = _guide_icon_xpm_path(cmds, item, pulse=True)
    if base_image:
        icon_control = cmds.iconTextStaticLabel(
            style="iconOnly",
            image1=base_image,
            width=32,
            height=32,
            parent=item_row,
        )
    else:
        icon_control = cmds.canvas(
            width=24,
            height=24,
            rgbValue=tuple(item["color"]),
            parent=item_row,
        )
    text_column = cmds.columnLayout(
        adjustableColumn=True,
        rowSpacing=1,
        parent=item_row,
    )
    cmds.text(
        label=item["label"],
        align="left",
        font="boldLabelFont",
        recomputeSize=False,
        width=204,
        height=19,
        parent=text_column,
    )
    cmds.text(
        label=GUIDE_COMPACT_LEGEND_DETAILS.get(
            item.get("key"),
            item["detail"],
        ),
        align="left",
        recomputeSize=False,
        width=204,
        height=18,
        annotation=item["detail"],
        parent=text_column,
    )
    return {
        "frame": item_frame,
        "icon": icon_control,
        "base_image": base_image,
        "pulse_image": pulse_image or base_image,
        "item": dict(item),
    }


def _rebuild_guide_legend(cmds, panel_data):
    """Replace only the small legend region when its stage contents change."""
    signature = _guide_legend_signature(panel_data.get("legend", []))
    if GUIDE_CONTROLS.get("legend_signature") == signature:
        return False

    _stop_guide_legend_pulse(cmds)
    prior_grid = GUIDE_CONTROLS.get("legend_grid")
    if prior_grid and cmds.layout(prior_grid, exists=True):
        cmds.deleteUI(prior_grid)

    legend_frame = GUIDE_CONTROLS.get("legend_frame")
    if not legend_frame or not cmds.frameLayout(legend_frame, exists=True):
        return False
    legend_grid = cmds.rowColumnLayout(
        numberOfColumns=2,
        width=520,
        columnWidth=[(1, 260), (2, 260)],
        columnSpacing=[(1, 0), (2, 0)],
        rowSpacing=[(1, 2), (2, 2)],
        parent=legend_frame,
    )
    GUIDE_CONTROLS["legend_grid"] = legend_grid
    GUIDE_CONTROLS["legend_items"] = {}
    legend_items = panel_data.get("legend", [])
    if legend_items:
        for item in legend_items:
            GUIDE_CONTROLS["legend_items"][item["key"]] = (
                _create_guide_legend_item(cmds, legend_grid, item)
            )
    else:
        empty_frame = cmds.frameLayout(
            labelVisible=False,
            borderVisible=False,
            marginWidth=8,
            marginHeight=8,
            parent=legend_grid,
        )
        cmds.text(
            label="Generate Scene to show stage-specific symbols.",
            align="left",
            parent=empty_frame,
        )
    GUIDE_CONTROLS["legend_signature"] = signature
    return True


def _guide_item_is_pulsing(item, current_frame):
    """Return whether an animated legend item is active at this frame."""
    if not item.get("animated"):
        return False
    pulse_ranges = item.get("pulse_ranges", []) or []
    if not pulse_ranges:
        return True
    return any(
        float(frame_range[0]) <= float(current_frame) <= float(frame_range[1])
        for frame_range in pulse_ranges
        if frame_range and len(frame_range) >= 2
    )


def _set_guide_legend_pulse_state(cmds, phase, current_frame=None):
    """Apply one throttled glow phase to only the moving legend symbols."""
    global GUIDE_PULSE_PHASE

    legend_controls = GUIDE_CONTROLS.get("legend_items", {})
    if not legend_controls:
        GUIDE_PULSE_PHASE = (bool(phase), ())
        return
    if current_frame is None:
        try:
            current_frame = cmds.currentTime(query=True)
        except RuntimeError:
            current_frame = 1

    neutral_background = (0.20, 0.20, 0.20)
    pulsing_keys = []
    for item_key, item_controls in legend_controls.items():
        item = item_controls.get("item", {})
        item_is_active = bool(
            PLAYBACK_ACTIVE
            and _guide_item_is_pulsing(item, current_frame)
        )
        if item_is_active:
            pulsing_keys.append(item_key)
        should_glow = bool(phase and item_is_active)
        frame_control = item_controls.get("frame")
        icon_control = item_controls.get("icon")
        if frame_control and cmds.frameLayout(frame_control, exists=True):
            background = (
                _mix_guide_color(
                    item.get("color", (0.75, 0.75, 0.75)),
                    (1.0, 1.0, 1.0),
                    0.32,
                )
                if should_glow
                else neutral_background
            )
            try:
                cmds.frameLayout(
                    frame_control,
                    edit=True,
                    enableBackground=True,
                    backgroundColor=background,
                )
            except RuntimeError:
                pass
        if (
            icon_control
            and cmds.control(icon_control, exists=True)
            and item_controls.get("base_image")
        ):
            image_path = (
                item_controls.get("pulse_image")
                if should_glow
                else item_controls.get("base_image")
            )
            try:
                cmds.iconTextStaticLabel(
                    icon_control,
                    edit=True,
                    image1=image_path,
                )
            except RuntimeError:
                pass
    GUIDE_PULSE_PHASE = (bool(phase), tuple(sorted(pulsing_keys)))


def _guide_legend_pulse_tick():
    """Maya time-change callback for lightweight legend animation feedback."""
    import maya.cmds as cmds

    if (
        not PLAYBACK_ACTIVE
        or cmds.about(batch=True)
        or not cmds.window(GUIDE_WINDOW_NAME, exists=True)
    ):
        return
    current_frame = cmds.currentTime(query=True)
    phase = (int(current_frame) // 4) % 2 == 0
    pulsing_keys = tuple(sorted(
        item_key
        for item_key, controls in GUIDE_CONTROLS.get(
            "legend_items",
            {},
        ).items()
        if _guide_item_is_pulsing(controls.get("item", {}), current_frame)
    ))
    if GUIDE_PULSE_PHASE == (phase, pulsing_keys):
        return
    _set_guide_legend_pulse_state(cmds, phase, current_frame=current_frame)


def _stop_guide_legend_pulse(cmds):
    """Stop the unique guide pulse callback and restore base icon artwork."""
    global GUIDE_PULSE_JOB_ID, GUIDE_PULSE_PHASE

    job_id = GUIDE_PULSE_JOB_ID
    GUIDE_PULSE_JOB_ID = None
    if job_id:
        try:
            if cmds.scriptJob(exists=job_id):
                cmds.scriptJob(kill=job_id, force=True)
        except RuntimeError:
            pass
    GUIDE_PULSE_PHASE = None
    try:
        _set_guide_legend_pulse_state(
            cmds,
            False,
            current_frame=cmds.currentTime(query=True),
        )
    except RuntimeError:
        pass


def _start_guide_legend_pulse(cmds):
    """Start one window-owned time-change callback for animated legend rows."""
    global GUIDE_PULSE_JOB_ID, GUIDE_PULSE_PHASE

    _stop_guide_legend_pulse(cmds)
    if (
        cmds.about(batch=True)
        or not PLAYBACK_ACTIVE
        or not cmds.window(GUIDE_WINDOW_NAME, exists=True)
    ):
        return None
    legend_frame = GUIDE_CONTROLS.get("legend_frame")
    if (
        legend_frame
        and cmds.frameLayout(legend_frame, exists=True)
        and not cmds.frameLayout(legend_frame, query=True, visible=True)
    ):
        return None
    legend_controls = GUIDE_CONTROLS.get("legend_items", {})
    if not any(
        controls.get("item", {}).get("animated")
        for controls in legend_controls.values()
    ):
        return None
    GUIDE_PULSE_PHASE = None
    GUIDE_PULSE_JOB_ID = cmds.scriptJob(
        timeChange=_guide_legend_pulse_tick,
        parent=GUIDE_WINDOW_NAME,
        replacePrevious=True,
    )
    _set_guide_legend_pulse_state(
        cmds,
        True,
        current_frame=cmds.currentTime(query=True),
    )
    return GUIDE_PULSE_JOB_ID


def _guide_window_position(cmds):
    """Place the guide beside the Control Panel instead of below the screen."""
    default_position = (80, 50)
    if not cmds.window(WINDOW_NAME, exists=True):
        return default_position
    try:
        control_corner = cmds.window(
            WINDOW_NAME,
            query=True,
            topLeftCorner=True,
        )
        control_width = int(cmds.window(WINDOW_NAME, query=True, width=True))
        control_x = int(control_corner[0])
        control_y = max(20, int(control_corner[1]))
        if control_x >= 600:
            return (max(20, control_x - 580), control_y)
        return (control_x + max(420, control_width) + 12, control_y)
    except (RuntimeError, TypeError, ValueError):
        return default_position


def _on_demo_guide_window_closed(*_args):
    """Stop UI-only animation feedback when a retained guide is hidden."""
    import maya.cmds as cmds

    _stop_guide_legend_pulse(cmds)


def update_demo_guide_panel(
    scene_data=None,
    stage=None,
    playback_status=None,
):
    """Update the separate guide window from current simulation state."""
    import maya.cmds as cmds
    from visual_module import build_demo_guide_panel_data

    global GUIDE_PLAYBACK_STATUS, LAST_GUIDE_PANEL_DATA

    active_scene = LAST_SCENE_DATA if scene_data is None else scene_data
    active_stage = CURRENT_DEMO_STAGE if stage is None else int(stage)
    if playback_status is not None:
        GUIDE_PLAYBACK_STATUS = str(playback_status)

    panel_data = build_demo_guide_panel_data(active_scene, active_stage)
    panel_data["playback_status"] = GUIDE_PLAYBACK_STATUS
    LAST_GUIDE_PANEL_DATA = panel_data
    if cmds.about(batch=True) or not cmds.window(GUIDE_WINDOW_NAME, exists=True):
        return panel_data

    if panel_data["has_scene"]:
        cycle_stage = "Cycle {0}  |  Stage {1}".format(
            panel_data["cycle"],
            panel_data["stage"],
        )
        stage_title = panel_data["stage_title"]
        description = panel_data["description"]
        focus = "What to look at: {0}".format(panel_data["focus"])
    else:
        cycle_stage = "No generated scene"
        stage_title = "Cloud-Hive Bloomfield"
        description = "Generate Scene to begin the guided workflow."
        focus = "The panel will follow every cycle and stage automatically."

    _set_guide_control_text(cmds, "cycle_stage", cycle_stage)
    _set_guide_control_text(cmds, "stage_title", stage_title)
    _set_guide_control_text(cmds, "stage_description", description)
    _set_guide_control_text(cmds, "stage_focus", focus)
    _set_guide_control_text(cmds, "explanation_action", panel_data["action"])
    _set_guide_control_text(cmds, "explanation_watch", panel_data["watch"])
    _set_guide_control_text(
        cmds,
        "explanation_difference",
        panel_data["difference"],
    )

    for key, _label, value_type in GUIDE_STATUS_FIELDS:
        value = panel_data["status"][key]
        formatted = "{0:.2f}".format(value) if value_type == "float" else str(value)
        _set_guide_control_text(cmds, "status_{0}".format(key), formatted)
    _set_guide_control_text(
        cmds,
        "status_playback",
        GUIDE_PLAYBACK_STATUS,
    )
    _rebuild_guide_legend(cmds, panel_data)

    show_legend = True
    guide_state = active_scene.get("demo_guide", {}) if active_scene else {}
    if guide_state:
        show_legend = bool(guide_state.get("show_legend", True))
    elif CURRENT_PARAMETERS:
        show_legend = bool(
            CURRENT_PARAMETERS.get("visual", {}).get(
                "show_demo_legend",
                True,
            )
        )
    legend_frame = GUIDE_CONTROLS.get("legend_frame")
    if legend_frame and cmds.frameLayout(legend_frame, exists=True):
        cmds.frameLayout(legend_frame, edit=True, visible=show_legend)
    return panel_data


def show_demo_guide_panel(scene_data=None, *_args):
    """Open or refresh the separate presentation/tutorial guide window."""
    import maya.cmds as cmds
    from visual_module import build_demo_guide_panel_data

    active_scene = LAST_SCENE_DATA if scene_data is None else scene_data
    panel_data = build_demo_guide_panel_data(
        active_scene,
        CURRENT_DEMO_STAGE,
    )
    if cmds.about(batch=True):
        return update_demo_guide_panel(active_scene, CURRENT_DEMO_STAGE)

    if cmds.window(GUIDE_WINDOW_NAME, exists=True):
        if _guide_control_exists(cmds, "stage_title"):
            cmds.showWindow(GUIDE_WINDOW_NAME)
            update_demo_guide_panel(active_scene, CURRENT_DEMO_STAGE)
            if PLAYBACK_ACTIVE:
                _start_guide_legend_pulse(cmds)
            return GUIDE_WINDOW_NAME
        # A retained window can survive a Script Editor module reload while
        # the Python-side control cache is reset. Rebuild that stale window
        # once so subsequent stage updates address valid controls.
        cmds.deleteUI(GUIDE_WINDOW_NAME, window=True)

    GUIDE_CONTROLS.clear()
    window_position = _guide_window_position(cmds)
    window = cmds.window(
        GUIDE_WINDOW_NAME,
        title=GUIDE_WINDOW_TITLE,
        widthHeight=(560, 840),
        topLeftCorner=window_position,
        sizeable=True,
        retain=True,
        closeCommand=_on_demo_guide_window_closed,
    )
    scroll = cmds.scrollLayout(
        childResizable=True,
        horizontalScrollBarThickness=0,
        verticalScrollBarThickness=14,
    )
    root_column = cmds.columnLayout(
        adjustableColumn=True,
        width=530,
        rowSpacing=8,
        parent=scroll,
    )
    cmds.text(
        label="Cloud-Hive Bloomfield",
        width=520,
        height=34,
        font="boldLabelFont",
        parent=root_column,
    )
    cmds.text(
        label="Presentation Guide",
        width=520,
        height=22,
        parent=root_column,
    )

    current_frame = cmds.frameLayout(
        label="Current Stage",
        collapsable=False,
        width=528,
        marginWidth=10,
        marginHeight=8,
        parent=root_column,
    )
    current_column = cmds.columnLayout(
        adjustableColumn=True,
        width=508,
        rowSpacing=5,
        parent=current_frame,
    )
    GUIDE_CONTROLS["cycle_stage"] = cmds.text(
        label="Cycle 0 | Stage 0",
        align="left",
        font="boldLabelFont",
        height=24,
        parent=current_column,
    )
    GUIDE_CONTROLS["stage_title"] = cmds.text(
        label=panel_data["stage_title"],
        align="left",
        font="boldLabelFont",
        height=28,
        parent=current_column,
    )
    GUIDE_CONTROLS["stage_description"] = cmds.text(
        label=panel_data["description"],
        align="left",
        recomputeSize=False,
        wordWrap=True,
        width=500,
        height=36,
        parent=current_column,
    )
    GUIDE_CONTROLS["stage_focus"] = cmds.text(
        label=panel_data["focus"],
        align="left",
        recomputeSize=False,
        wordWrap=True,
        width=500,
        height=34,
        parent=current_column,
    )

    legend_frame = cmds.frameLayout(
        label="Legend",
        collapsable=True,
        collapse=False,
        width=528,
        marginWidth=8,
        marginHeight=8,
        parent=root_column,
    )
    GUIDE_CONTROLS["legend_frame"] = legend_frame
    _rebuild_guide_legend(cmds, panel_data)

    status_frame = cmds.frameLayout(
        label="Live Status",
        collapsable=True,
        collapse=False,
        width=528,
        marginWidth=10,
        marginHeight=8,
        parent=root_column,
    )
    status_grid = cmds.rowColumnLayout(
        numberOfColumns=4,
        columnWidth=[(1, 145), (2, 70), (3, 145), (4, 90)],
        parent=status_frame,
    )
    status_items = list(GUIDE_STATUS_FIELDS) + [
        ("playback", "Playback", "text"),
    ]
    for key, label, _value_type in status_items:
        cmds.text(
            label=label,
            align="left",
            font="boldLabelFont",
            parent=status_grid,
        )
        GUIDE_CONTROLS["status_{0}".format(key)] = cmds.text(
            label="-",
            align="left",
            parent=status_grid,
        )

    explanation_frame = cmds.frameLayout(
        label="Stage-Specific Explanation",
        collapsable=True,
        collapse=False,
        width=528,
        marginWidth=10,
        marginHeight=8,
        parent=root_column,
    )
    explanation_column = cmds.columnLayout(
        adjustableColumn=True,
        width=508,
        rowSpacing=4,
        parent=explanation_frame,
    )
    for control_name, heading, value in (
        (
            "explanation_action",
            "What the system is doing",
            panel_data["action"],
        ),
        (
            "explanation_watch",
            "What to look at",
            panel_data["watch"],
        ),
        (
            "explanation_difference",
            "Difference from the previous stage",
            panel_data["difference"],
        ),
    ):
        cmds.text(
            label=heading,
            align="left",
            font="boldLabelFont",
            parent=explanation_column,
        )
        GUIDE_CONTROLS[control_name] = cmds.text(
            label=value,
            align="left",
            recomputeSize=False,
            wordWrap=True,
            width=500,
            height=40,
            parent=explanation_column,
        )
        cmds.separator(
            height=4,
            style="none",
            parent=explanation_column,
        )

    cmds.text(
        label=(
            "Screen recording shows this panel. Maya playblast records only "
            "the compact viewport HUD when Show Ornaments is enabled."
        ),
        align="left",
        recomputeSize=False,
        wordWrap=True,
        width=510,
        height=36,
        parent=root_column,
    )
    cmds.showWindow(window)
    update_demo_guide_panel(active_scene, CURRENT_DEMO_STAGE)
    if PLAYBACK_ACTIVE:
        _start_guide_legend_pulse(cmds)
    return window


def close_demo_guide_panel(*_args):
    """Close the separate guide window without changing simulation state."""
    import maya.cmds as cmds

    _stop_guide_legend_pulse(cmds)
    GUIDE_CONTROLS.clear()
    if not cmds.about(batch=True) and cmds.window(
        GUIDE_WINDOW_NAME,
        exists=True,
    ):
        cmds.deleteUI(GUIDE_WINDOW_NAME, window=True)


def open_demo_guide_panel(*_args):
    """Maya callback that opens the guide with the current scene state."""
    return show_demo_guide_panel(LAST_SCENE_DATA)


def _set_cycle_authoring_busy(cmds, is_busy):
    """Lock or unlock cycle-boundary authoring without trapping the UI."""
    global CYCLE_AUTHORING_BUSY

    CYCLE_AUTHORING_BUSY = bool(is_busy)
    next_control = CONTROLS.get("next_step")
    try:
        if next_control and cmds.control(next_control, exists=True):
            cmds.button(next_control, edit=True, enable=not CYCLE_AUTHORING_BUSY)
    except RuntimeError:
        # The lock state must still be released if the window closes mid-build.
        pass


def _update_status(cmds):
    """Show a compact summary of the latest scene data."""
    if not LAST_SCENE_DATA:
        _set_status(cmds, "Adjust parameters, then generate.")
        return

    summary = LAST_SCENE_DATA["summary"]
    label = (
        "Cycle: {0} | Stage: {1} - {2}\n"
        "Drops {3} | Queued {4} | Full {5} | Nectar {6:.2f} | Pollen {7:.2f}"
    ).format(
        SIMULATION_STEP,
        CURRENT_DEMO_STAGE,
        DEMO_STAGE_LABELS[CURRENT_DEMO_STAGE],
        summary["drop_count"],
        summary.get("queued_task_count", 0),
        summary.get("full_storage_cell_count", 0),
        summary.get("stored_nectar_total", 0.0),
        summary.get("stored_pollen_total", 0.0),
    )
    if CURRENT_DEMO_STAGE == 4:
        transport_demo = LAST_SCENE_DATA.get("transport_demo", {})
        active_count = len(transport_demo.get("assignments", []))
        secondary_tasks = transport_demo.get("secondary_tasks", [])
        queued_count = sum(
            task.get("demo_transport_state") == "queued"
            for task in secondary_tasks
        )
        secondary_count = len(secondary_tasks) - queued_count
        label += (
            "\n{0} active transport bees | {1} queued | "
            "{2} secondary paths"
        ).format(
            active_count,
            queued_count,
            secondary_count,
        )
    elif CURRENT_DEMO_STAGE == 5:
        collection_check = LAST_SCENE_DATA.get("collection_check", {})
        needed = collection_check.get("needed_resources", [])
        if needed:
            label += "\nCollection task triggered: {0}".format(", ".join(needed))
        else:
            demo_resource = (
                collection_check.get("presentation_resource") or "resource"
            )
            label += "\nNo shortage; demonstrating {0} collection".format(
                demo_resource
            )
    elif CURRENT_DEMO_STAGE == 6:
        collection_check = LAST_SCENE_DATA.get("collection_check", {})
        label += "\nCloud collection: {0} active bees | {1} queued tasks".format(
            collection_check.get("active_task_count", 0),
            collection_check.get("queued_task_count", 0),
        )
    _set_status(cmds, label)


def _build_scene_without_viewport_scrub(cmds, create_scene, *args, **kwargs):
    """Build Maya keyframes without visibly scrubbing through the timeline."""
    cmds.refresh(suspend=True)
    try:
        scene_data = create_scene(*args, **kwargs)
        cmds.currentTime(1)
        return scene_data
    finally:
        # Always resume drawing, including when scene creation raises an error.
        cmds.refresh(suspend=False)
        cmds.refresh(force=True)


def _kill_playback_job(cmds):
    """Remove the one-shot Maya playback completion callback, when present."""
    global PLAYBACK_JOB_ID

    job_id = PLAYBACK_JOB_ID
    PLAYBACK_JOB_ID = None
    if job_id:
        try:
            if cmds.scriptJob(exists=job_id):
                cmds.scriptJob(kill=job_id, force=True)
        except RuntimeError:
            pass


def _cancel_stage_playback(cmds):
    """Stop an active stage preview without jumping to its end frame."""
    global PLAYBACK_ACTIVE, PLAYBACK_SERIAL, PLAYBACK_END_FRAME

    _kill_playback_job(cmds)
    _stop_guide_legend_pulse(cmds)
    PLAYBACK_SERIAL += 1
    cmds.play(state=False)
    PLAYBACK_ACTIVE = False
    PLAYBACK_END_FRAME = None


def _stage_playback_finished(serial, end_frame):
    """Leave a completed stage on its authored final visual state."""
    import maya.cmds as cmds

    global PLAYBACK_ACTIVE, PLAYBACK_JOB_ID, PLAYBACK_END_FRAME

    if serial != PLAYBACK_SERIAL:
        return False
    PLAYBACK_JOB_ID = None
    PLAYBACK_ACTIVE = False
    PLAYBACK_END_FRAME = None
    _stop_guide_legend_pulse(cmds)
    cmds.currentTime(int(end_frame))
    if LAST_SCENE_DATA is not None:
        LAST_SCENE_DATA["active_demo_frame"] = cmds.currentTime(query=True)
        LAST_SCENE_DATA["transition_complete"] = True
    _update_status(cmds)
    update_demo_guide_panel(
        LAST_SCENE_DATA,
        CURRENT_DEMO_STAGE,
        playback_status="Ready",
    )
    cmds.refresh(force=True)
    return True


def play_stage_transition(scene_data=None, stage=None):
    """Play one prepared stage segment once, then stop on its final frame."""
    import maya.cmds as cmds

    global PLAYBACK_ACTIVE, PLAYBACK_JOB_ID, PLAYBACK_SERIAL
    global PLAYBACK_END_FRAME

    active_scene = scene_data or LAST_SCENE_DATA
    active_stage = CURRENT_DEMO_STAGE if stage is None else int(stage)
    if not active_scene:
        return False
    playback_range = active_scene.get("demo_playback_ranges", {}).get(active_stage)
    if not playback_range:
        return False
    start_frame = int(playback_range[0])
    end_frame = max(start_frame + 1, int(playback_range[1]))

    _cancel_stage_playback(cmds)
    cmds.playbackOptions(
        minTime=start_frame,
        maxTime=end_frame,
        loop="once",
        view="active",
    )
    cmds.currentTime(start_frame)
    cmds.refresh(force=True)

    PLAYBACK_SERIAL += 1
    serial = PLAYBACK_SERIAL
    PLAYBACK_END_FRAME = end_frame
    PLAYBACK_ACTIVE = True
    active_scene["transition_complete"] = False
    active_scene["last_played_stage"] = active_stage
    active_scene["last_played_range"] = (start_frame, end_frame)
    update_demo_guide_panel(
        active_scene,
        active_stage,
        playback_status="Playing",
    )
    _start_guide_legend_pulse(cmds)

    if cmds.about(batch=True):
        cmds.play(forward=True)
        _stage_playback_finished(serial, end_frame)
        return True

    conditions = cmds.scriptJob(listConditions=True) or []
    if "playingBack" in conditions:
        job_options = {
            "conditionFalse": [
                "playingBack",
                lambda: _stage_playback_finished(serial, end_frame),
            ],
            "runOnce": True,
        }
        if cmds.window(WINDOW_NAME, exists=True):
            job_options["parent"] = WINDOW_NAME
        PLAYBACK_JOB_ID = cmds.scriptJob(**job_options)
        try:
            cmds.play(forward=True)
        except Exception:
            _kill_playback_job(cmds)
            PLAYBACK_ACTIVE = False
            PLAYBACK_END_FRAME = None
            _stop_guide_legend_pulse(cmds)
            raise
        return True

    # Defensive fallback for an unusual interactive Maya session without the
    # playingBack condition. Stage ranges are deliberately short.
    try:
        cmds.play(forward=True, wait=True)
    finally:
        _stage_playback_finished(serial, end_frame)
    return True


def generate_from_ui(*_args):
    """Read UI values, rerun the algorithms, and rebuild the Maya scene."""
    import maya.cmds as cmds
    from main import print_summary
    from visual_module import create_maya_scene

    global LAST_SCENE_DATA, CURRENT_PARAMETERS, SIMULATION_STEP, CURRENT_DEMO_STAGE
    global PLAYBACK_ACTIVE
    _ensure_controls(cmds)
    _cancel_stage_playback(cmds)
    CURRENT_PARAMETERS = _read_parameters(cmds)
    CURRENT_PARAMETERS.setdefault("simulation", {})["cycle"] = 0
    SIMULATION_STEP = 0
    CURRENT_DEMO_STAGE = 0

    _set_status(cmds, "Generating scene...")
    cmds.refresh(force=True)
    LAST_SCENE_DATA = _build_scene_without_viewport_scrub(
        cmds,
        create_maya_scene,
        CURRENT_PARAMETERS,
    )
    guide_enabled = bool(
        CURRENT_PARAMETERS.get("visual", {}).get("show_demo_guide", True)
    )
    if guide_enabled:
        show_demo_guide_panel(LAST_SCENE_DATA)
        update_demo_guide_panel(
            LAST_SCENE_DATA,
            0,
            playback_status="Ready",
        )
    else:
        close_demo_guide_panel()
    _update_status(cmds)
    print("Generated Cloud-Hive Bloomfield base scene. No autoplay.")
    print("Base Scene - click Next Simulation Step to show natural resource drops.")
    print_summary(LAST_SCENE_DATA)
    return LAST_SCENE_DATA


def clear_scene_from_ui(*_args):
    """Clear generated Cloud-Hive Meadow scene objects from Maya."""
    import maya.cmds as cmds
    from visual_module import clear_scene

    global LAST_SCENE_DATA, SIMULATION_STEP, CURRENT_DEMO_STAGE, PLAYBACK_ACTIVE
    _cancel_stage_playback(cmds)
    clear_scene()
    LAST_SCENE_DATA = None
    SIMULATION_STEP = 0
    CURRENT_DEMO_STAGE = 0
    guide_enabled = bool(
        (CURRENT_PARAMETERS or {}).get("visual", {}).get(
            "show_demo_guide",
            True,
        )
    )
    if guide_enabled:
        show_demo_guide_panel(None)
        update_demo_guide_panel(None, 0, playback_status="Scene cleared")
    else:
        close_demo_guide_panel()
    _update_status(cmds)
    print("Cleared Cloud-Hive Bloomfield scene objects.")


def run_pure_python_summary(*_args):
    """Run the pure Python simulation with current UI values and print a summary."""
    import maya.cmds as cmds
    from main import print_summary, run_simulation

    _ensure_controls(cmds)
    parameters = _read_parameters(cmds)
    simulation = run_simulation(parameters)
    print_summary(simulation)
    _set_status(cmds, "Pure Python summary printed to Script Editor.")
    return simulation


def next_simulation_step(*_args):
    """Advance and play one prepared demo-stage transition.

    A new simulation cycle is authored once, under suspended redraw, when the
    user advances after Stage 7. Other clicks only use prepared keyframes.
    """
    import maya.cmds as cmds
    from main import print_summary
    from visual_module import apply_demo_stage, create_maya_scene

    global LAST_SCENE_DATA, CURRENT_PARAMETERS, SIMULATION_STEP, CURRENT_DEMO_STAGE
    global PLAYBACK_ACTIVE, CYCLE_AUTHORING_BUSY
    _ensure_controls(cmds)

    if CYCLE_AUTHORING_BUSY:
        message = "Preparing next cycle... Please wait."
        _set_status(cmds, message)
        update_demo_guide_panel(
            LAST_SCENE_DATA,
            CURRENT_DEMO_STAGE,
            playback_status="Preparing next cycle",
        )
        print(message)
        return LAST_SCENE_DATA

    if PLAYBACK_ACTIVE:
        is_running = True
        try:
            queried_state = cmds.play(query=True, state=True)
            if queried_state is not None:
                is_running = bool(queried_state)
        except RuntimeError:
            pass
        if is_running:
            message = "Current stage transition is still playing."
            _set_status(cmds, message)
            print(message)
            return LAST_SCENE_DATA
        _stage_playback_finished(
            PLAYBACK_SERIAL,
            PLAYBACK_END_FRAME or cmds.currentTime(query=True),
        )

    if LAST_SCENE_DATA is None:
        generate_from_ui()

    if CURRENT_DEMO_STAGE >= 7:
        prior_scene_data = LAST_SCENE_DATA
        prior_parameters = CURRENT_PARAMETERS
        prior_step = SIMULATION_STEP
        prior_stage = CURRENT_DEMO_STAGE
        prior_cell_state = _capture_cell_state(prior_scene_data)
        next_step = prior_step + 1
        next_parameters = copy.deepcopy(prior_parameters)
        next_parameters.setdefault("simulation", {})["cycle"] = next_step
        undo_chunk_open = False
        scene_rollback_available = False

        _set_cycle_authoring_busy(cmds, True)
        try:
            message = "Cycle {0} | Preparing next cycle...".format(next_step)
            _set_status(cmds, message)
            update_demo_guide_panel(
                LAST_SCENE_DATA,
                CURRENT_DEMO_STAGE,
                playback_status="Preparing Cycle {0}".format(next_step),
            )
            print(message)
            cmds.refresh(force=True)
            try:
                scene_rollback_available = bool(
                    cmds.undoInfo(query=True, state=True)
                )
                if scene_rollback_available:
                    cmds.undoInfo(
                        openChunk=True,
                        chunkName="CloudHivePrepareNextCycle",
                    )
                    undo_chunk_open = True
            except RuntimeError:
                scene_rollback_available = False

            next_scene_data = _build_scene_without_viewport_scrub(
                cmds,
                create_maya_scene,
                next_parameters,
                prior_cell_state=prior_cell_state,
            )
            next_stage = 1
            stage_state = apply_demo_stage(next_scene_data, next_stage)

            LAST_SCENE_DATA = next_scene_data
            CURRENT_PARAMETERS = next_parameters
            SIMULATION_STEP = next_step
            CURRENT_DEMO_STAGE = next_stage
        except Exception as error:
            if undo_chunk_open:
                try:
                    cmds.undoInfo(closeChunk=True)
                except RuntimeError:
                    scene_rollback_available = False
                finally:
                    undo_chunk_open = False
            if scene_rollback_available:
                try:
                    cmds.undo()
                except RuntimeError:
                    scene_rollback_available = False

            LAST_SCENE_DATA = prior_scene_data
            CURRENT_PARAMETERS = prior_parameters
            SIMULATION_STEP = prior_step
            CURRENT_DEMO_STAGE = prior_stage
            message = (
                "Could not prepare Cycle {0}; staying on Cycle {1}, Stage {2}: "
                "{3}"
            ).format(next_step, prior_step, prior_stage, error)
            if not scene_rollback_available:
                message += " Maya scene rollback was unavailable."
            try:
                _set_status(cmds, message)
            except RuntimeError:
                pass
            update_demo_guide_panel(
                LAST_SCENE_DATA,
                CURRENT_DEMO_STAGE,
                playback_status="Cycle preparation failed",
            )
            try:
                cmds.warning(message)
            finally:
                cmds.refresh(force=True)
            return LAST_SCENE_DATA
        finally:
            try:
                if undo_chunk_open:
                    cmds.undoInfo(closeChunk=True)
            finally:
                _set_cycle_authoring_busy(cmds, False)
    else:
        CURRENT_DEMO_STAGE += 1
        stage_state = apply_demo_stage(LAST_SCENE_DATA, CURRENT_DEMO_STAGE)
    _update_status(cmds)
    update_demo_guide_panel(
        LAST_SCENE_DATA,
        CURRENT_DEMO_STAGE,
        playback_status="Ready",
    )

    print("Stage {0} - {1}.".format(
        CURRENT_DEMO_STAGE,
        DEMO_STAGE_LABELS[CURRENT_DEMO_STAGE],
    ))
    print(
        "Cycle {0} | Transition range {1:g}-{2:g}".format(
            SIMULATION_STEP,
            stage_state["playback_range"][0],
            stage_state["playback_range"][1],
        )
    )

    if CURRENT_DEMO_STAGE == 5:
        collection_check = LAST_SCENE_DATA.get("collection_check", {})
        totals = collection_check.get("totals", {})
        thresholds = collection_check.get("thresholds", {})
        needed = collection_check.get("needed_resources", [])
        print(
            "Resource check: nectar {0:.2f}/{1:.2f}, pollen {2:.2f}/{3:.2f}.".format(
                totals.get("nectar", 0.0),
                thresholds.get("nectar", 0.0),
                totals.get("pollen", 0.0),
                thresholds.get("pollen", 0.0),
            )
        )
        if needed:
            print("Collection triggered for: {0}.".format(", ".join(needed)))
        else:
            demo_resource = (
                collection_check.get("presentation_resource") or "resource"
            )
            print(
                "No shortage this cycle; showing a presentation-safe {0} "
                "collection preview.".format(demo_resource)
            )
    elif CURRENT_DEMO_STAGE == 6:
        if LAST_SCENE_DATA.get("collection_tasks"):
            print("Stage 6 - Cloud Collection transition playing.")
        else:
            print("No cloud collection segment is required this cycle.")
    elif CURRENT_DEMO_STAGE == 7:
        print_summary(LAST_SCENE_DATA)
        print("Next Simulation Step will prepare Cycle {0}.".format(SIMULATION_STEP + 1))

    play_stage_transition(LAST_SCENE_DATA, CURRENT_DEMO_STAGE)
    return LAST_SCENE_DATA


def play_animation(*_args):
    """Replay the current stage's prepared transition segment once."""
    return play_stage_transition(LAST_SCENE_DATA, CURRENT_DEMO_STAGE)


def pause_animation(*_args):
    """Pause the Maya timeline."""
    import maya.cmds as cmds

    global PLAYBACK_ACTIVE

    _cancel_stage_playback(cmds)
    update_demo_guide_panel(
        LAST_SCENE_DATA,
        CURRENT_DEMO_STAGE,
        playback_status="Paused",
    )


def reset_animation(*_args):
    """Reset the Maya timeline to frame 1."""
    import maya.cmds as cmds
    from visual_module import update_demo_guide

    global PLAYBACK_ACTIVE

    _cancel_stage_playback(cmds)
    cmds.currentTime(1)
    if LAST_SCENE_DATA is not None:
        update_demo_guide(LAST_SCENE_DATA, CURRENT_DEMO_STAGE)
        update_demo_guide_panel(
            LAST_SCENE_DATA,
            CURRENT_DEMO_STAGE,
            playback_status="Reset at frame 1",
        )
        cmds.refresh(force=True)
    else:
        update_demo_guide_panel(
            None,
            0,
            playback_status="Reset at frame 1",
        )


def create_cloud_hive_ui(initial_scene_data=None):
    """Create and show the Cloud-Hive Control Panel.

    Parameters:
        initial_scene_data (dict | None): Optional scene data used to seed the
            status label.

    Returns:
        str: Maya window name.
    """
    return show_ui(initial_scene_data)


def show_ui(initial_scene_data=None):
    """Create and show the Cloud-Hive Meadow Maya control panel."""
    import maya.cmds as cmds
    from main import load_parameters

    global LAST_SCENE_DATA, CURRENT_PARAMETERS, SIMULATION_STEP, CURRENT_DEMO_STAGE
    global PLAYBACK_ACTIVE
    _cancel_stage_playback(cmds)
    active_scene = (
        initial_scene_data
        if initial_scene_data is not None
        else LAST_SCENE_DATA
    )
    saved_parameters = (
        active_scene.get("parameters")
        if active_scene
        else None
    )
    parameter_source = saved_parameters or (
        CURRENT_PARAMETERS
        if CURRENT_PARAMETERS is not None
        else load_parameters()
    )
    defaults = copy.deepcopy(parameter_source)
    LAST_SCENE_DATA = active_scene
    CURRENT_PARAMETERS = copy.deepcopy(defaults)
    SIMULATION_STEP = int(
        active_scene.get("summary", {}).get(
            "cycle_number",
            defaults.get("simulation", {}).get("cycle", 0),
        )
        if active_scene
        else defaults.get("simulation", {}).get("cycle", 0)
    )
    CURRENT_PARAMETERS.setdefault("simulation", {})["cycle"] = SIMULATION_STEP
    CURRENT_DEMO_STAGE = int(
        active_scene.get("demo_stage", CURRENT_DEMO_STAGE)
        if active_scene
        else 0
    )
    PLAYBACK_ACTIVE = False

    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)
    CONTROLS.clear()

    window = cmds.window(
        WINDOW_NAME,
        title=WINDOW_TITLE,
        widthHeight=(420, 760),
        sizeable=True,
        resizeToFitChildren=False,
    )
    cmds.scrollLayout(
        childResizable=True,
        horizontalScrollBarThickness=0,
        verticalScrollBarThickness=14,
    )
    cmds.columnLayout(adjustableColumn=True, rowSpacing=7)
    cmds.text(label="Cloud-Hive Bloomfield", height=30)

    hive_defaults = defaults["hive"]
    cloud_defaults = defaults["clouds"]
    drop_defaults = defaults["drops"]
    bee_defaults = defaults["bees"]
    visual_defaults = defaults.get("visual", {})

    cmds.frameLayout(label="Hive", collapsable=True, marginWidth=8, marginHeight=8)
    CONTROLS["hive_size"] = cmds.intSliderGrp(
        label="Honeycomb Size", field=True, minValue=1, maxValue=8,
        fieldMinValue=1, fieldMaxValue=20, value=hive_defaults["size"],
    )
    CONTROLS["cell_size"] = cmds.floatSliderGrp(
        label="Cell Size", field=True, minValue=0.5, maxValue=2.0,
        fieldMinValue=0.1, fieldMaxValue=5.0,
        value=hive_defaults["cell_size"], precision=2,
    )
    CONTROLS["voxel_density"] = cmds.intSliderGrp(
        label="Pixel Density", field=True, minValue=8, maxValue=20,
        fieldMinValue=8, fieldMaxValue=24,
        value=visual_defaults.get("voxel_density", 14),
    )
    CONTROLS["honey_ratio"] = cmds.floatSliderGrp(
        label="Honey Ratio", field=True, minValue=0.0, maxValue=1.0,
        value=hive_defaults["honey_ratio"], precision=2,
    )
    CONTROLS["pollen_ratio"] = cmds.floatSliderGrp(
        label="Pollen Ratio", field=True, minValue=0.0, maxValue=1.0,
        value=hive_defaults["pollen_ratio"], precision=2,
    )
    CONTROLS["capped_ratio"] = cmds.floatSliderGrp(
        label="Capped Ratio", field=True, minValue=0.0, maxValue=1.0,
        value=hive_defaults["capped_ratio"], precision=2,
    )
    cmds.setParent("..")

    cmds.frameLayout(label="Cloud Resources", collapsable=True, marginWidth=8, marginHeight=8)
    CONTROLS["cloud_count"] = cmds.intSliderGrp(
        label="Cloud Count", field=True, minValue=1, maxValue=8,
        fieldMinValue=1, fieldMaxValue=20, value=cloud_defaults["cloud_count"],
    )
    CONTROLS["flower_count"] = cmds.intSliderGrp(
        label="Flowers / Cloud", field=True, minValue=1, maxValue=16,
        value=visual_defaults.get("flowers_per_cloud", 7),
    )
    CONTROLS["nectar_drop_rate"] = cmds.intSliderGrp(
        label="Nectar Drop Rate", field=True, minValue=0, maxValue=12,
        fieldMinValue=0, fieldMaxValue=30, value=drop_defaults["nectar_drop_rate"],
    )
    CONTROLS["pollen_drop_rate"] = cmds.intSliderGrp(
        label="Pollen Drop Rate", field=True, minValue=0, maxValue=12,
        fieldMinValue=0, fieldMaxValue=30, value=drop_defaults["pollen_drop_rate"],
    )
    cmds.setParent("..")

    cmds.frameLayout(label="Wind and Bees", collapsable=True, marginWidth=8, marginHeight=8)
    CONTROLS["wind_strength"] = cmds.floatSliderGrp(
        label="Wind Strength", field=True, minValue=0.0, maxValue=4.0,
        fieldMinValue=0.0, fieldMaxValue=10.0,
        value=drop_defaults["wind_strength"], precision=2,
    )
    CONTROLS["wind_direction"] = cmds.floatSliderGrp(
        label="Wind Direction", field=True, minValue=0.0, maxValue=360.0,
        fieldMinValue=0.0, fieldMaxValue=360.0,
        value=drop_defaults["wind_direction_degrees"], precision=1,
    )
    CONTROLS["bee_count"] = cmds.intSliderGrp(
        label="Bee Count", field=True, minValue=1, maxValue=12,
        fieldMinValue=1, fieldMaxValue=40, value=bee_defaults["bee_count"],
    )
    CONTROLS["animation_end"] = cmds.intSliderGrp(
        label="Animation Frames", field=True, minValue=160, maxValue=600,
        value=visual_defaults.get("animation_end", 320),
    )
    CONTROLS["drop_fall_frames"] = cmds.intSliderGrp(
        label="Drop Fall Frames", field=True, minValue=24, maxValue=140,
        value=visual_defaults.get("drop_fall_frames", 64),
    )
    CONTROLS["bee_frame_step"] = cmds.intSliderGrp(
        label="Bee Speed (Lower = Faster)", field=True, minValue=8, maxValue=50,
        value=visual_defaults.get("bee_frame_step", 22),
    )
    CONTROLS["show_paths"] = cmds.checkBox(
        label="Show Paths",
        value=visual_defaults.get("show_paths", True),
    )
    cmds.setParent("..")

    cmds.frameLayout(
        label="Presentation Guide",
        collapsable=True,
        marginWidth=8,
        marginHeight=8,
    )
    guide_enabled = bool(visual_defaults.get("show_demo_guide", True))
    CONTROLS["show_demo_guide"] = cmds.checkBox(
        label="Show Demo Guide",
        value=guide_enabled,
        changeCommand=update_demo_guide_options,
    )
    CONTROLS["show_demo_legend"] = cmds.checkBox(
        label="Show Legend",
        value=visual_defaults.get("show_demo_legend", True),
        enable=guide_enabled,
        changeCommand=update_demo_guide_options,
    )
    CONTROLS["show_demo_stage_hint"] = cmds.checkBox(
        label="Show Viewport Hint",
        value=visual_defaults.get("show_demo_stage_hint", True),
        enable=guide_enabled,
        changeCommand=update_demo_guide_options,
    )
    CONTROLS["open_demo_guide"] = cmds.button(
        label="Open Demo Guide Panel",
        height=28,
        enable=guide_enabled,
        command=open_demo_guide_panel,
    )
    cmds.text(
        label=(
            "Viewport HUD is compact. Use screen recording to include the "
            "separate guide panel."
        ),
        align="left",
        recomputeSize=False,
        wordWrap=True,
        height=34,
    )
    cmds.setParent("..")

    cmds.button(label="Generate Scene", height=38, command=generate_from_ui)
    cmds.button(label="Clear Scene", height=32, command=clear_scene_from_ui)
    cmds.button(label="Run Pure Python Summary", height=32, command=run_pure_python_summary)
    CONTROLS["next_step"] = cmds.button(
        label="Next Simulation Step",
        height=32,
        command=next_simulation_step,
    )

    cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnWidth3=(135, 135, 135))
    cmds.button(label="Play", command=play_animation)
    cmds.button(label="Pause", command=pause_animation)
    cmds.button(label="Reset", command=reset_animation)
    cmds.setParent("..")

    CONTROLS["status"] = cmds.text(
        label="Adjust parameters, then generate.", align="left", height=70,
    )

    cmds.showWindow(window)
    _update_status(cmds)
    if guide_enabled:
        show_demo_guide_panel(LAST_SCENE_DATA)
    else:
        close_demo_guide_panel()
    return window
