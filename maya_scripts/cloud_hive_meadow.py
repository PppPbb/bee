r"""
Cloud-Hive Meadow Maya entry script.

Run inside Maya Script Editor:

exec(open(r"/path/to/bee/maya_scripts/cloud_hive_meadow.py").read())

Default behavior:
    run() opens the control panel and generates one scene from UI defaults.

Alternatives:
    run(open_control_panel=False) generates a scene without opening the UI.
    open_ui() opens only the Cloud-Hive Control Panel.
"""

import importlib
import os
import sys


def _find_project_code_dir():
    """Find the repository code directory for the Maya entry script.

    Returns:
        str: Absolute path to the repository's code directory.
    """
    candidate_roots = []

    script_file = globals().get("__file__")
    if script_file:
        candidate_roots.append(os.path.abspath(os.path.join(os.path.dirname(script_file), os.pardir)))

    user_home = os.path.expanduser("~")
    candidate_roots.append(os.path.join(user_home, "Desktop", "bee"))
    candidate_roots.append(r"C:\Users\YUN\Desktop\bee")
    candidate_roots.append(os.getcwd())
    candidate_roots.append(os.path.abspath(os.path.join(os.getcwd(), os.pardir)))
    candidate_roots.append(os.path.abspath(os.path.join(os.getcwd(), "bee")))

    for search_path in list(sys.path):
        if search_path:
            candidate_roots.append(os.path.abspath(search_path))
            candidate_roots.append(os.path.abspath(os.path.join(search_path, os.pardir)))

    seen = set()
    for root in candidate_roots:
        if root in seen:
            continue
        seen.add(root)

        code_dir = os.path.join(root, "code")
        visual_module_path = os.path.join(code_dir, "visual_module.py")
        if os.path.isfile(visual_module_path):
            return code_dir

    raise RuntimeError(
        "Could not find Cloud-Hive Bloomfield code directory. "
        "Expected to find code/visual_module.py under C:\\Users\\YUN\\Desktop\\bee. "
        "Add the repository code folder to sys.path before running this script."
    )


def _prepare_project_modules():
    """Add project code to sys.path and reload project modules for Maya."""
    code_dir = _find_project_code_dir()
    if code_dir not in sys.path:
        sys.path.insert(0, code_dir)
    print("Cloud-Hive Bloomfield code directory:", code_dir)
    _reload_project_modules()
    return code_dir


def run(open_control_panel=True):
    """Run the Cloud-Hive Meadow Maya visualization.

    Parameters:
        open_control_panel (bool): When True, open the UI and generate from the
            UI defaults. When False, call visual_module.create_maya_scene()
            directly.

    Returns:
        dict: Scene data returned by visual_module.create_maya_scene().
    """
    _prepare_project_modules()

    if open_control_panel:
        from ui_module import generate_from_ui, show_ui

        show_ui()
        scene_data = generate_from_ui()
    else:
        from visual_module import create_maya_scene

        scene_data = create_maya_scene()

    print("Cloud-Hive Bloomfield Maya scene created successfully.")
    return scene_data


def open_ui():
    """Open the Cloud-Hive Meadow Maya control panel without generating a scene.

    Returns:
        str: Maya window name.
    """
    _prepare_project_modules()

    from ui_module import create_cloud_hive_ui

    window = create_cloud_hive_ui()
    print("Cloud-Hive Bloomfield UI opened.")
    return window


def _reload_project_modules():
    """Reload project modules so Maya does not keep stale imported code."""
    module_names = [
        "config",
        "hive_module",
        "cloud_resource_module",
        "bee_task_module",
        "main",
        "visual_module",
        "ui_module",
    ]
    for module_name in module_names:
        module = sys.modules.get(module_name)
        if module is not None:
            importlib.reload(module)
            print("Reloaded", module_name)


if __name__ == "__main__":
    SCENE_DATA = run()
