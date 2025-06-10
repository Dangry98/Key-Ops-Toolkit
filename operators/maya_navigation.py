import bpy.types
from ..utils.pref_utils import get_keyops_prefs

tablet_keymap_config = [
    ('3D View', 'view3d.zoom', 'LEFTMOUSE', 'CLICK_DRAG', {'ctrl': True, 'alt': True}),
    ('3D View', 'view3d.move', 'LEFTMOUSE', 'CLICK_DRAG', {'alt': True, 'shift': True}),
    ('View2D', 'view2d.pan', 'LEFTMOUSE', 'CLICK_DRAG', {'alt': True}),
    ('View2D', 'view2d.zoom', 'LEFTMOUSE', 'CLICK_DRAG', {'ctrl': True, 'alt': True}),
    ('View2D', 'view2d.pan', 'LEFTMOUSE', 'PRESS', {'alt': True, 'shift': True}),
    ('View2D Buttons List', 'view2d.pan', 'LEFTMOUSE', 'PRESS', {'alt': True}),
    ('Image', 'image.view_zoom', 'LEFTMOUSE', 'PRESS', {'ctrl': True, 'alt': True}),
    ('Image', 'image.view_pan', 'LEFTMOUSE', 'PRESS', {'alt': True, 'shift': True}),
    ('Image', 'image.view_pan', 'LEFTMOUSE', 'PRESS', {'alt': True}),
]
def add_tablet_navigation():
    prefs = get_keyops_prefs()

    if prefs.maya_navigation_tablet_navigation:
        wm = bpy.context.window_manager
        try:
            for keymap_name, idname, key, value, modifiers in tablet_keymap_config:
                km = wm.keyconfigs.active.keymaps[keymap_name]
                kmi = km.keymap_items.new(idname, key, value)
                for mod, enabled in modifiers.items():
                    setattr(kmi, mod, enabled)
        except KeyError as e:
            print(f"Error adding tablet navigation keymap: {e}")
            return

def remove_tablet_navigation():
    wm = bpy.context.window_manager

    try:
        for keymap_name, idname, key, value, modifiers in tablet_keymap_config:
            km = wm.keyconfigs.active.keymaps[keymap_name]
            items_to_remove = [
                kmi for kmi in km.keymap_items
                if kmi.idname == idname and kmi.type == key and kmi.value == value and all(
                    getattr(kmi, mod) == enabled for mod, enabled in modifiers.items()
                )
            ]
            for kmi in items_to_remove:
                km.keymap_items.remove(kmi)
    except KeyError as e:
        print(f"Error removing tablet navigation keymap: {e}")
        return

def update_tablet_navigation(self, context):
    if self.maya_navigation_tablet_navigation:
        add_tablet_navigation()
    else:
        remove_tablet_navigation()


class MayaNavigation(bpy.types.Operator):
    bl_idname = "keyops.maya_navigation"
    bl_label = "KeyOps: Maya Navigation"
    bl_options = {'INTERNAL'}

    def register():
        add_tablet_navigation()
        
    def unregister():
        remove_tablet_navigation()