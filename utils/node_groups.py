"""Geometry Nodes groups used by the add-on.

The groups live in .blend files in resources/ instead of being rebuilt from Python, so Blender's own file
versioning keeps them working across releases:
- resources/node_groups.blend: every group, saved in the OLDEST Blender the add-on supports
  (blender_version_min in blender_manifest.toml). Newer Blender versions read older files, not the other way.
- resources/node_groups_<major>_<minor>.blend: only the groups that use nodes added in that version (e.g.
  viewport gizmos in 4.3), saved in exactly that version.
get_node_group() takes a group from the newest file the running Blender can read that has it, so every
supported version gets the best build it can open, and 4.2 keeps working.

To change a group: rebuild it with scripts/build_node_groups.py (see its docstring), or edit it by hand in the
right Blender version. Keep its name and socket identifiers (operators set inputs by identifier, e.g.
"Socket_2"), the same in every file, and keep its fake user.
"""
import os
import re

import bpy

RESOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")
NODE_GROUPS_BLEND = os.path.join(RESOURCES, "node_groups.blend")


def candidate_files(version=None):
    """The node group files this Blender can read, newest first; the base file last."""
    version = tuple(version or bpy.app.version)[:2]
    newer = []
    try:
        names = os.listdir(RESOURCES)
    except OSError:
        names = []
    for name in names:
        m = re.fullmatch(r"node_groups_(\d+)_(\d+)\.blend", name)
        if m:
            v = (int(m.group(1)), int(m.group(2)))
            if v <= version:
                newer.append((v, os.path.join(RESOURCES, name)))
    newer.sort(reverse=True)
    return [path for _v, path in newer] + [NODE_GROUPS_BLEND]


def get_node_group(name):
    """Return the node group `name`, appending it from the best file in resources/ when the file doesn't have it
    yet."""
    node_group = bpy.data.node_groups.get(name)
    if node_group is not None:
        return node_group

    for path in candidate_files():
        with bpy.data.libraries.load(path, link=False) as (data_from, data_to):
            if name not in data_from.node_groups:
                continue
            data_to.node_groups = [name]
        node_group = data_to.node_groups[0]
        # The asset file keeps groups with a fake user so they are saved; in the user's file they should
        # behave like any other group and be purged when no modifier uses them.
        node_group.use_fake_user = False
        return node_group
    raise KeyError(f"Node group '{name}' not found in {RESOURCES}")
