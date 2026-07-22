"""Maya control panel for Cloud-Hive Meadow."""

import copy


WINDOW_NAME = "CloudHiveControlPanel"
WINDOW_TITLE = "Cloud-Hive Bloomfield Control Panel"
CONTROLS = {}
LAST_SCENE_DATA = None
CURRENT_PARAMETERS = None
SIMULATION_STEP = 0
CURRENT_DEMO_STAGE = 0
PLAYBACK_ACTIVE = False
PLAYBACK_JOB_ID = None
PLAYBACK_SERIAL = 0
PLAYBACK_END_FRAME = None

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
    if CURRENT_DEMO_STAGE == 5:
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
        label += "\nCloud collection transition"
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
    cmds.currentTime(int(end_frame))
    if LAST_SCENE_DATA is not None:
        LAST_SCENE_DATA["active_demo_frame"] = cmds.currentTime(query=True)
        LAST_SCENE_DATA["transition_complete"] = True
    _update_status(cmds)
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
    global PLAYBACK_ACTIVE
    _ensure_controls(cmds)

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
        prior_cell_state = _capture_cell_state(LAST_SCENE_DATA)
        SIMULATION_STEP += 1
        CURRENT_PARAMETERS = copy.deepcopy(CURRENT_PARAMETERS)
        CURRENT_PARAMETERS.setdefault("simulation", {})["cycle"] = SIMULATION_STEP
        _set_status(
            cmds,
            "Cycle {0} | Preparing Stage 1 visuals...".format(SIMULATION_STEP),
        )
        cmds.refresh(force=True)
        LAST_SCENE_DATA = _build_scene_without_viewport_scrub(
            cmds,
            create_maya_scene,
            CURRENT_PARAMETERS,
            prior_cell_state=prior_cell_state,
        )
        CURRENT_DEMO_STAGE = 1
    else:
        CURRENT_DEMO_STAGE += 1

    stage_state = apply_demo_stage(LAST_SCENE_DATA, CURRENT_DEMO_STAGE)
    _update_status(cmds)

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


def reset_animation(*_args):
    """Reset the Maya timeline to frame 1."""
    import maya.cmds as cmds

    global PLAYBACK_ACTIVE

    _cancel_stage_playback(cmds)
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

    global LAST_SCENE_DATA, CURRENT_PARAMETERS, SIMULATION_STEP, CURRENT_DEMO_STAGE
    global PLAYBACK_ACTIVE
    _cancel_stage_playback(cmds)
    saved_parameters = (
        initial_scene_data.get("parameters")
        if initial_scene_data
        else None
    )
    parameter_source = saved_parameters or (
        CURRENT_PARAMETERS
        if initial_scene_data and CURRENT_PARAMETERS is not None
        else load_parameters()
    )
    defaults = copy.deepcopy(parameter_source)
    LAST_SCENE_DATA = initial_scene_data
    CURRENT_PARAMETERS = copy.deepcopy(defaults)
    SIMULATION_STEP = int(
        initial_scene_data.get("summary", {}).get(
            "cycle_number",
            defaults.get("simulation", {}).get("cycle", 0),
        )
        if initial_scene_data
        else 0
    )
    CURRENT_PARAMETERS.setdefault("simulation", {})["cycle"] = SIMULATION_STEP
    CURRENT_DEMO_STAGE = int(
        initial_scene_data.get("demo_stage", 0) if initial_scene_data else 0
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
        label="Adjust parameters, then generate.", align="left", height=70,
    )

    cmds.showWindow(window)
    _update_status(cmds)
    return window
