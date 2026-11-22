"""Opt-in shortcut that replaces the old Rebind tab's W context menu button.

The old Rebind buttons edited the user's keymap directly. These add Key Ops'
own items to ``keyconfigs.addon`` instead, so turning them off or disabling the
add-on gives Blender's keys back untouched.
"""

import bpy
from ..utils.pref_utils import unregister_keymaps

registered_w_context_menu_keymaps = []


def _new(store, keymap, idname, key, menu, space_type="EMPTY", **mods):
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name=keymap, space_type=space_type)
    kmi = km.keymap_items.new(idname, key, "PRESS", **mods)
    kmi.properties.name = menu
    store.append((km, kmi))


def register():
    _new(registered_w_context_menu_keymaps, "Object Mode", "wm.call_menu", "W", "VIEW3D_MT_object_context_menu")
    _new(registered_w_context_menu_keymaps, "Mesh", "wm.call_menu", "W", "VIEW3D_MT_edit_mesh_context_menu")
    _new(registered_w_context_menu_keymaps, "Curve", "wm.call_menu", "W", "VIEW3D_MT_edit_curve_context_menu")


def unregister():
    unregister_keymaps(registered_w_context_menu_keymaps)
    registered_w_context_menu_keymaps.clear()
