"""Maya UI controls for the Cloud-Hive Meadow MVP."""

from config import DEFAULT_INTEGRATION_PARAMETERS
from main import print_summary, run_simulation
from visual_module import clear_scene, create_maya_scene


WINDOW_NAME = "CloudHiveControlPanel"
WINDOW_TITLE = "Cloud-Hive Control Panel"


def create_cloud_hive_ui():
    """Create the Maya control panel for Cloud-Hive Meadow.

    This is a Maya-only function. It imports maya.cmds inside the function body
    so this module can still be compiled and imported outside Autodesk Maya.

    Parameters:
        None.

    Returns:
        str: Maya window name.
    """
    import maya.cmds as cmds

    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    controls = {}
    defaults = DEFAULT_INTEGRATION_PARAMETERS
    hive = defaults["hive"]
    clouds = defaults["clouds"]
    drops = defaults["drops"]
    bees = defaults["bees"]
    visual = defaults.get("visual", {})

    window = cmds.window(WINDOW_NAME, title=WINDOW_TITLE, sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=("both", 10))

    cmds.text(label="Cloud-Hive Meadow", align="center", height=28)
    cmds.separator(height=8, style="in")

    controls["hive_size"] = cmds.intSliderGrp(
        label="Honeycomb Size",
        field=True,
        minValue=1,
        maxValue=8,
        fieldMinValue=1,
        fieldMaxValue=20,
        value=hive["size"],
    )
    controls["cell_size"] = cmds.floatSliderGrp(
        label="Cell Size",
        field=True,
        minValue=0.5,
        maxValue=2.0,
        fieldMinValue=0.1,
        fieldMaxValue=5.0,
        value=hive["cell_size"],
        precision=2,
    )
    controls["honey_ratio"] = cmds.floatSliderGrp(
        label="Honey Ratio",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=hive["honey_ratio"],
        precision=2,
    )
    controls["pollen_ratio"] = cmds.floatSliderGrp(
        label="Pollen Ratio",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=hive["pollen_ratio"],
        precision=2,
    )
    controls["capped_ratio"] = cmds.floatSliderGrp(
        label="Capped Ratio",
        field=True,
        minValue=0.0,
        maxValue=1.0,
        value=hive["capped_ratio"],
        precision=2,
    )

    cmds.separator(height=8, style="in")

    controls["cloud_count"] = cmds.intSliderGrp(
        label="Cloud Count",
        field=True,
        minValue=1,
        maxValue=8,
        fieldMinValue=1,
        fieldMaxValue=20,
        value=clouds["cloud_count"],
    )
    controls["nectar_drop_rate"] = cmds.intSliderGrp(
        label="Nectar Drop Rate",
        field=True,
        minValue=0,
        maxValue=8,
        fieldMinValue=0,
        fieldMaxValue=30,
        value=drops["nectar_drop_rate"],
    )
    controls["pollen_drop_rate"] = cmds.intSliderGrp(
        label="Pollen Drop Rate",
        field=True,
        minValue=0,
        maxValue=8,
        fieldMinValue=0,
        fieldMaxValue=30,
        value=drops["pollen_drop_rate"],
    )
    controls["wind_strength"] = cmds.floatSliderGrp(
        label="Wind Strength",
        field=True,
        minValue=0.0,
        maxValue=3.0,
        fieldMinValue=0.0,
        fieldMaxValue=10.0,
        value=drops["wind_strength"],
        precision=2,
    )
    controls["wind_direction"] = cmds.floatSliderGrp(
        label="Wind Direction",
        field=True,
        minValue=0.0,
        maxValue=360.0,
        fieldMinValue=0.0,
        fieldMaxValue=360.0,
        value=drops["wind_direction_degrees"],
        precision=1,
    )

    cmds.separator(height=8, style="in")

    controls["bee_count"] = cmds.intSliderGrp(
        label="Bee Count",
        field=True,
        minValue=1,
        maxValue=12,
        fieldMinValue=1,
        fieldMaxValue=40,
        value=bees["bee_count"],
    )
    controls["show_paths"] = cmds.checkBox(
        label="Show Paths",
        value=visual.get("show_paths", True),
    )

    cmds.separator(height=10, style="in")

    cmds.button(
        label="Generate Scene",
        height=34,
        command=lambda *_: _on_generate_scene(controls),
    )
    cmds.button(
        label="Clear Scene",
        height=28,
        command=lambda *_: _on_clear_scene(),
    )
    cmds.button(
        label="Run Pure Python Summary",
        height=28,
        command=lambda *_: _on_run_summary(controls),
    )

    cmds.setParent("..")
    cmds.showWindow(window)
    return window


def build_config_from_ui(controls):
    """Build an integration config dictionary from Maya UI controls.

    Parameters:
        controls (dict): Maya control names created by create_cloud_hive_ui().

    Returns:
        dict: Configuration dictionary for main.run_simulation() or create_maya_scene().
    """
    import maya.cmds as cmds

    config = _copy_default_config()
    hive = config["hive"]
    clouds = config["clouds"]
    drops = config["drops"]
    bees = config["bees"]
    visual = config.setdefault("visual", {})

    hive["size"] = cmds.intSliderGrp(controls["hive_size"], query=True, value=True)
    hive["cell_size"] = cmds.floatSliderGrp(controls["cell_size"], query=True, value=True)

    honey_ratio = cmds.floatSliderGrp(controls["honey_ratio"], query=True, value=True)
    pollen_ratio = cmds.floatSliderGrp(controls["pollen_ratio"], query=True, value=True)
    capped_ratio = cmds.floatSliderGrp(controls["capped_ratio"], query=True, value=True)
    empty_ratio = max(0.0, 1.0 - honey_ratio - pollen_ratio - capped_ratio)

    hive["honey_ratio"] = honey_ratio
    hive["pollen_ratio"] = pollen_ratio
    hive["capped_ratio"] = capped_ratio
    hive["empty_ratio"] = empty_ratio

    clouds["cloud_count"] = cmds.intSliderGrp(controls["cloud_count"], query=True, value=True)
    drops["nectar_drop_rate"] = cmds.intSliderGrp(
        controls["nectar_drop_rate"],
        query=True,
        value=True,
    )
    drops["pollen_drop_rate"] = cmds.intSliderGrp(
        controls["pollen_drop_rate"],
        query=True,
        value=True,
    )
    drops["wind_strength"] = cmds.floatSliderGrp(
        controls["wind_strength"],
        query=True,
        value=True,
    )
    drops["wind_direction_degrees"] = cmds.floatSliderGrp(
        controls["wind_direction"],
        query=True,
        value=True,
    )

    bees["bee_count"] = cmds.intSliderGrp(controls["bee_count"], query=True, value=True)
    visual["show_paths"] = cmds.checkBox(controls["show_paths"], query=True, value=True)
    return config


def _copy_default_config():
    """Create a plain nested copy of DEFAULT_INTEGRATION_PARAMETERS.

    Returns:
        dict: Mutable copy of the default integration parameters.
    """
    copied = {}
    for section_name, section_values in DEFAULT_INTEGRATION_PARAMETERS.items():
        copied[section_name] = {}
        for key, value in section_values.items():
            if isinstance(value, list):
                copied[section_name][key] = list(value)
            else:
                copied[section_name][key] = value
    copied.setdefault("visual", {})
    return copied


def _on_generate_scene(controls):
    """Generate the Maya scene from current UI parameters.

    Parameters:
        controls (dict): Maya control names.

    Returns:
        None.
    """
    config = build_config_from_ui(controls)
    scene_data = create_maya_scene(config)
    print("Generated Cloud-Hive scene from UI.")
    print_summary(scene_data)


def _on_clear_scene():
    """Clear generated Cloud-Hive Meadow objects from the Maya scene.

    Parameters:
        None.

    Returns:
        None.
    """
    clear_scene()
    print("Cleared Cloud-Hive Meadow scene objects.")


def _on_run_summary(controls):
    """Run the pure Python simulation and print its summary.

    Parameters:
        controls (dict): Maya control names.

    Returns:
        None.
    """
    config = build_config_from_ui(controls)
    simulation = run_simulation(config)
    print_summary(simulation)
