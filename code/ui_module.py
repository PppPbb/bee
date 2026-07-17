"""Maya control panel for Cloud-Hive Meadow."""

import copy


WINDOW_NAME = "CloudHiveMeadowControlWindow"
CONTROLS = {}
LAST_SCENE_DATA = None
CURRENT_PARAMETERS = None
SIMULATION_STEP = 0


def _int_value(cmds, name):
    return cmds.intSliderGrp(CONTROLS[name], query=True, value=True)


def _float_value(cmds, name):
    return cmds.floatSliderGrp(CONTROLS[name], query=True, value=True)


def _ensure_controls(cmds):
    """Rebuild the panel when Maya invokes a callback from a stale window."""
    required = (
        "hive_size",
        "cloud_count",
        "flower_count",
        "nectar_rate",
        "pollen_rate",
        "wind_strength",
        "wind_direction",
        "bee_count",
        "animation_end",
        "drop_fall_frames",
        "bee_frame_step",
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
    parameters["hive"]["size"] = _int_value(cmds, "hive_size")
    parameters["clouds"]["cloud_count"] = _int_value(cmds, "cloud_count")
    parameters["drops"]["nectar_drop_rate"] = _int_value(cmds, "nectar_rate")
    parameters["drops"]["pollen_drop_rate"] = _int_value(cmds, "pollen_rate")
    parameters["drops"]["wind_strength"] = _float_value(cmds, "wind_strength")
    parameters["drops"]["wind_direction_degrees"] = _float_value(cmds, "wind_direction")
    parameters["bees"]["bee_count"] = _int_value(cmds, "bee_count")
    parameters["visual"]["flowers_per_cloud"] = _int_value(cmds, "flower_count")
    parameters["visual"]["animation_end"] = _int_value(cmds, "animation_end")
    parameters["visual"]["drop_fall_frames"] = _int_value(cmds, "drop_fall_frames")
    parameters["visual"]["bee_frame_step"] = _int_value(cmds, "bee_frame_step")
    return parameters


def _capture_cell_state(scene_data):
    """Keep resource and capped state between simulation steps."""
    if not scene_data:
        return None
    fields = ("id", "type", "nectar", "pollen", "capacity", "is_blocked")
    return [
        {field: cell[field] for field in fields if field in cell}
        for cell in scene_data.get("cells", [])
    ]


def _update_status(cmds):
    if not LAST_SCENE_DATA or "status" not in CONTROLS:
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
    cmds.text(CONTROLS["status"], edit=True, label=label)


def generate_from_ui(*_args):
    """Read UI values, rerun the algorithms, and rebuild the Maya scene."""
    import maya.cmds as cmds
    from visual_module import create_maya_scene

    global LAST_SCENE_DATA, CURRENT_PARAMETERS, SIMULATION_STEP
    _ensure_controls(cmds)
    CURRENT_PARAMETERS = _read_parameters(cmds)
    SIMULATION_STEP = 0

    cmds.text(CONTROLS["status"], edit=True, label="Generating...")
    cmds.refresh(force=True)
    LAST_SCENE_DATA = create_maya_scene(CURRENT_PARAMETERS)
    _update_status(cmds)
    cmds.currentTime(1)
    return LAST_SCENE_DATA


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
    cmds.text(CONTROLS["status"], edit=True, label="Building next step...")
    cmds.refresh(force=True)
    LAST_SCENE_DATA = create_maya_scene(
        CURRENT_PARAMETERS,
        prior_cell_state=prior_cell_state,
    )
    _update_status(cmds)
    cmds.currentTime(1)
    return LAST_SCENE_DATA


def play_animation(*_args):
    import maya.cmds as cmds
    cmds.play(forward=True)


def pause_animation(*_args):
    import maya.cmds as cmds
    cmds.play(state=False)


def reset_animation(*_args):
    import maya.cmds as cmds
    cmds.play(state=False)
    cmds.currentTime(1)


def show_ui(initial_scene_data=None):
    """Create and show the Cloud-Hive Meadow Maya control panel."""
    import maya.cmds as cmds
    from main import load_parameters

    global LAST_SCENE_DATA, CURRENT_PARAMETERS, SIMULATION_STEP
    defaults = load_parameters()
    LAST_SCENE_DATA = initial_scene_data
    CURRENT_PARAMETERS = copy.deepcopy(defaults)
    SIMULATION_STEP = 0

    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)
    CONTROLS.clear()

    window = cmds.window(
        WINDOW_NAME,
        title="Cloud-Hive Meadow Controls",
        widthHeight=(380, 640),
        sizeable=True,
    )
    cmds.columnLayout(adjustableColumn=True, rowSpacing=7)
    cmds.text(label="Cloud, Resource and Worker Simulation", height=30)

    cmds.frameLayout(label="Hive", collapsable=True, marginWidth=8, marginHeight=8)
    CONTROLS["hive_size"] = cmds.intSliderGrp(
        label="Grid Radius", field=True, minValue=2, maxValue=7,
        fieldMinValue=1, fieldMaxValue=12, value=defaults["hive"]["size"],
    )
    cmds.setParent("..")

    cmds.frameLayout(label="Cloud Resources", collapsable=True, marginWidth=8, marginHeight=8)
    CONTROLS["cloud_count"] = cmds.intSliderGrp(
        label="Cloud Count", field=True, minValue=1, maxValue=8,
        value=defaults["clouds"]["cloud_count"],
    )
    CONTROLS["flower_count"] = cmds.intSliderGrp(
        label="Flowers / Cloud", field=True, minValue=1, maxValue=16,
        value=defaults["visual"]["flowers_per_cloud"],
    )
    CONTROLS["nectar_rate"] = cmds.intSliderGrp(
        label="Nectar Frequency", field=True, minValue=1, maxValue=12,
        value=defaults["drops"]["nectar_drop_rate"],
    )
    CONTROLS["pollen_rate"] = cmds.intSliderGrp(
        label="Pollen Frequency", field=True, minValue=1, maxValue=12,
        value=defaults["drops"]["pollen_drop_rate"],
    )
    cmds.setParent("..")

    cmds.frameLayout(label="Wind and Workers", collapsable=True, marginWidth=8, marginHeight=8)
    CONTROLS["wind_strength"] = cmds.floatSliderGrp(
        label="Wind Strength", field=True, minValue=0.0, maxValue=4.0,
        value=defaults["drops"]["wind_strength"], precision=2,
    )
    CONTROLS["wind_direction"] = cmds.floatSliderGrp(
        label="Wind Direction", field=True, minValue=0.0, maxValue=360.0,
        value=defaults["drops"]["wind_direction_degrees"], precision=1,
    )
    CONTROLS["bee_count"] = cmds.intSliderGrp(
        label="Worker Bees", field=True, minValue=1, maxValue=10,
        value=defaults["bees"]["bee_count"],
    )
    CONTROLS["animation_end"] = cmds.intSliderGrp(
        label="Animation Frames", field=True, minValue=160, maxValue=600,
        value=defaults["visual"].get("animation_end", 320),
    )
    CONTROLS["drop_fall_frames"] = cmds.intSliderGrp(
        label="Rain Fall Frames", field=True, minValue=24, maxValue=140,
        value=defaults["visual"].get("drop_fall_frames", 64),
    )
    CONTROLS["bee_frame_step"] = cmds.intSliderGrp(
        label="Bee Move Frames", field=True, minValue=8, maxValue=50,
        value=defaults["visual"].get("bee_frame_step", 22),
    )
    cmds.setParent("..")

    cmds.button(label="Generate Scene and Tasks", height=38, command=generate_from_ui)
    cmds.button(label="Next Simulation Step", height=34, command=next_simulation_step)
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnWidth3=(120, 120, 120))
    cmds.button(label="Play", command=play_animation)
    cmds.button(label="Pause", command=pause_animation)
    cmds.button(label="Reset", command=reset_animation)
    cmds.setParent("..")
    CONTROLS["status"] = cmds.text(
        label="Adjust parameters, then generate.", align="left", height=36,
    )

    cmds.showWindow(window)
    _update_status(cmds)
    return window
