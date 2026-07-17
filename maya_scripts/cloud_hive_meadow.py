r"""
Cloud-Hive Meadow Maya entry script.

Run inside Maya Script Editor:

exec(open(r"/path/to/bee/maya_scripts/cloud_hive_meadow.py").read())

Optional UI:

open_ui()
"""

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

    candidate_roots.append(os.getcwd())
    candidate_roots.append(os.path.abspath(os.path.join(os.getcwd(), os.pardir)))

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
        "Could not find Cloud-Hive Meadow code directory. "
        "Add the repository code folder to sys.path before running this script."
    )


def run():
    """Run the Cloud-Hive Meadow Maya visualization MVP.

    Returns:
        dict: Scene data returned by visual_module.create_maya_scene().
    """
    code_dir = _find_project_code_dir()
    if code_dir not in sys.path:
        sys.path.insert(0, code_dir)

    from visual_module import create_maya_scene

    scene_data = create_maya_scene()
    print("Cloud-Hive Meadow Maya scene created successfully.")
    return scene_data


def open_ui():
    """Open the Cloud-Hive Meadow Maya control panel.

    Returns:
        str: Maya window name.
    """
    code_dir = _find_project_code_dir()
    if code_dir not in sys.path:
        sys.path.insert(0, code_dir)

    from ui_module import create_cloud_hive_ui

    window = create_cloud_hive_ui()
    print("Cloud-Hive Meadow UI opened.")
    return window


if __name__ == "__main__":
    SCENE_DATA = run()
