"""Geometry Nodes groups used by the add-on.

The groups live in resources/node_groups.blend instead of being rebuilt from Python, so Blender's own
file versioning keeps them working across releases. To change one, open that file in the OLDEST Blender
the add-on supports (blender_version_min in blender_manifest.toml), edit the group, keep its name and
socket identifiers (operators set inputs by identifier, e.g. "Socket_2"), make sure it still has a fake
user, and save. Newer Blender versions read older files, but not the other way around.
"""
import os
import bpy

NODE_GROUPS_BLEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "node_groups.blend")


def get_node_group(name):
    """Return the node group `name`, appending it from resources/node_groups.blend when the file doesn't have it yet."""
    node_group = bpy.data.node_groups.get(name)
    if node_group is not None:
        return node_group

    with bpy.data.libraries.load(NODE_GROUPS_BLEND, link=False) as (data_from, data_to):
        if name not in data_from.node_groups:
            raise KeyError(f"Node group '{name}' not found in {NODE_GROUPS_BLEND}")
        data_to.node_groups = [name]

    node_group = data_to.node_groups[0]
    # The asset file keeps groups with a fake user so they are saved; in the user's file they should
    # behave like any other group and be purged when no modifier uses them.
    node_group.use_fake_user = False
    return node_group
