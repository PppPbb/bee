"""Maya control panel for Cloud-Hive Meadow."""

import copy


WINDOW_NAME = "CloudHiveControlPanel"
WINDOW_TITLE = "Cloud-Hive Control Panel"
CONTROLS = {}
LAST_SCENE_DATA = None
CURRENT_PARAMETERS = None
SIMULATION_STEP = 0


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

    hive["size"] = _int_value(cmds, "hive_size")
    hive["cell_size"] = _float_value(cmds, "cell_size")

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


def _capture_cell_state(scene_data):
    """Keep resource and capped state between simulation steps."""
    if not scene_data:
        return None
    fields = ("id", "type", "nectar", "pollen", "capacity", "is_blocked")
    return [
        {field: cell[field] for field in fields if field in cell}
        for cell in scene_data.get("cells", [])
    ]


def _set_status(cmds, label):
    """Update the UI status label when the window is available."""
    if "status" in CONTROLS and cmds.control(CONTROLS["status"], exists=True):
        cmds.text(CONTROLS["status"], edit=True, label=label)


def _update_status(cmds):
    """Show a compact summary of the latest scene data."""
    if not LAST_SCENE_DATA:
        _set_status(cmds, "Adjust parameters, then generate.")
        return

    summary = LAST_SCENE_DATA["summary"]
    label = (
        "Step {0} | Drops {1} | Queued {2} | Blocked {3} | Animated tasks {4}"
    ).format(
        SIMULATION_STEP,
        summary["drop_count"],
        summary.get("queued_task_count", 0),
        summary.get("blocked_task_count", 0),
        len(LAST_SCENE_DATA.get("animation_records", [])),
    )
    _set_status(cmds, label)


def generate_from_ui(*_args):
    """Read UI values, rerun the algorithms, and rebuild the Maya scene."""
    import maya.cmds as cmds
    from main import print_summary
    from visual_module import create_maya_scene

    global LAST_SCENE_DATA, CURRENT_PARAMETERS, SIMULATION_STEP
    _ensure_controls(cmds)
    CURRENT_PARAMETERS = _read_parameters(cmds)
    SIMULATION_STEP = 0

    _set_status(cmds, "Generating scene...")
    cmds.refresh(force=True)
    LAST_SCENE_DATA = create_maya_scene(CURRENT_PARAMETERS)
    _update_status(cmds)
    cmds.currentTime(1)
    print("Generated Cloud-Hive scene from UI.")
    print_summary(LAST_SCENE_DATA)
    return LAST_SCENE_DATA


def clear_scene_from_ui(*_args):
    """Clear generated Cloud-Hive Meadow scene objects from Maya."""
    import maya.cmds as cmds
    from visual_module import clear_scene

    global LAST_SCENE_DATA, SIMULATION_STEP
    cmds.play(state=False)
    clear_scene()
    LAST_SCENE_DATA = None
    SIMULATION_STEP = 0
    _update_status(cmds)
    print("Cleared Cloud-Hive Meadow scene objects.")


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
    """Generate new drops while preserving honeycomb resource state."""
    import maya.cmds as cmds
    from visual_module import create_maya_scene

    global LAST_SCENE_DATA, CURRENT_PARAMETERS, SIMULATION_STEP
    _ensure_controls(cmds)
    if CURRENT_PARAMETERS is None:
        CURRENT_PARAMETERS = _read_parameters(cmds)

    prior_cell_state = _capture_cell_state(LAST_SCENE_DATA)
    SIMULATION_STEP += 1
    CURRENT_PARAMETERS = copy.deepcopy(CURRENT_PARAMETERS)
    CURRENT_PARAMETERS["drops"]["seed"] += 97
    cmds.play(state=False)
    _set_status(cmds, "Building next step...")
    cmds.refresh(force=True)
    LAST_SCENE_DATA = create_maya_scene(
        CURRENT_PARAMETERS,
        prior_cell_state=prior_cell_state,
    )
    _update_status(cmds)
    cmds.currentTime(1)
    return LAST_SCENE_DATA


def play_animation(*_args):
    """Play the Maya timeline."""
    import maya.cmds as cmds

    cmds.play(forward=True)


def pause_animation(*_args):
    """Pause the Maya timeline."""
    import maya.cmds as cmds

    cmds.play(state=False)


def reset_animation(*_args):
    """Reset the Maya timeline to frame 1."""
    import maya.cmds as cmds

    cmds.play(state=False)
    cmds.currentTime(1)


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

    global LAST_SCENE_DATA, CURRENT_PARAMETERS, SIMULATION_STEP
    defaults = copy.deepcopy(load_parameters())
    LAST_SCENE_DATA = initial_scene_data
    CURRENT_PARAMETERS = copy.deepcopy(defaults)
    SIMULATION_STEP = 0

    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)
    CONTROLS.clear()

    window = cmds.window(
        WINDOW_NAME,
        title=WINDOW_TITLE,
        widthHeight=(420, 760),
        sizeable=True,
    )
    cmds.columnLayout(adjustableColumn=True, rowSpacing=7)
    cmds.text(label="Cloud-Hive Meadow", height=30)

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
        label="Bee Speed (Frames)", field=True, minValue=8, maxValue=50,
        value=visual_defaults.get("bee_frame_step", 22),
    )
    CONTROLS["show_paths"] = cmds.checkBox(
        label="Show Paths",
        value=visual_defaults.get("show_paths", True),
    )
    cmds.setParent("..")

    cmds.button(label="Generate Scene", height=38, command=generate_from_ui)
    cmds.button(label="Clear Scene", height=32, command=clear_scene_from_ui)
    cmds.button(label="Run Pure Python Summary", height=32, command=run_pure_python_summary)
    cmds.button(label="Next Simulation Step", height=32, command=next_simulation_step)

    cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnWidth3=(135, 135, 135))
    cmds.button(label="Play", command=play_animation)
    cmds.button(label="Pause", command=pause_animation)
    cmds.button(label="Reset", command=reset_animation)
    cmds.setParent("..")

    CONTROLS["status"] = cmds.text(
        label="Adjust parameters, then generate.", align="left", height=40,
    )

    cmds.showWindow(window)
    _update_status(cmds)
    return window
