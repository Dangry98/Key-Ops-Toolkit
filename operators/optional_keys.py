"""Opt-in shortcuts that replace the old Rebind tab.

The old Rebind buttons edited the user's keymap directly. These add Key Ops'
own items to ``keyconfigs.addon`` instead, so turning them off or disabling the
add-on gives Blender's keys back untouched.
"""

import bpy
from ..utils.pref_utils import unregister_keymaps

registered_w_context_menu_keymaps = []
registered_add_menu_shift_a_keymaps = []
registered_view_pie_space_keymaps = []


def _new(store, keymap, idname, key, menu, space_type="EMPTY", **mods):
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name=keymap, space_type=space_type)
    kmi = km.keymap_items.new(idname, key, "PRESS", **mods)
    kmi.properties.name = menu
    store.append((km, kmi))


def register_w_context_menu():
    _new(registered_w_context_menu_keymaps, "Object Mode", "wm.call_menu", "W", "VIEW3D_MT_object_context_menu")
    _new(registered_w_context_menu_keymaps, "Mesh", "wm.call_menu", "W", "VIEW3D_MT_edit_mesh_context_menu")
    _new(registered_w_context_menu_keymaps, "Curve", "wm.call_menu", "W", "VIEW3D_MT_edit_curve_context_menu")


def unregister_w_context_menu():
    unregister_keymaps(registered_w_context_menu_keymaps)
    registered_w_context_menu_keymaps.clear()


def register_add_menu_shift_a():
    for keymap in ("Object Mode", "Mesh"):
        _new(registered_add_menu_shift_a_keymaps, keymap, "wm.call_menu_pie", "A",
             "KEYOPS_MT_add_objects_pie_menu", shift=True)


def unregister_add_menu_shift_a():
    unregister_keymaps(registered_add_menu_shift_a_keymaps)
    registered_add_menu_shift_a_keymaps.clear()


def register_view_pie_space():
    _new(registered_view_pie_space_keymaps, "3D View", "wm.call_menu_pie", "SPACE",
         "VIEW3D_MT_view_pie", space_type="VIEW_3D")


def unregister_view_pie_space():
    unregister_keymaps(registered_view_pie_space_keymaps)
    registered_view_pie_space_keymaps.clear()
