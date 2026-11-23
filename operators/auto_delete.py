import bpy.types
from ..utils.pref_utils import get_keyops_prefs
from ..utils.pref_utils import clear_registered_keymaps
registered_auto_delete_keymaps = []

def register_auto_delete_keymaps():
    global registered_auto_delete_keymaps
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:  # background mode
        return
    km = kc.keymaps.new(name='Mesh', space_type='EMPTY')
    kmi = km.keymap_items.new('keyops.auto_delete', 'DEL', 'PRESS')
    registered_auto_delete_keymaps.append((km, kmi))

    # Object Mode X: our own delete shortcut, on top of Blender's, so the confirm popup can be
    # skipped without changing Blender's own keymap item.
    km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')
    kmi = km.keymap_items.new('object.delete', 'X', 'PRESS')
    registered_auto_delete_keymaps.append((km, kmi))
    sync_confirm_delete()


def sync_confirm_delete():
    """Set the confirm option of our own Object Mode X delete item from the preference."""
    prefs = get_keyops_prefs()
    confirm = bool(prefs and prefs.auto_delete_confirm_object_mode)
    for _km, kmi in registered_auto_delete_keymaps:
        if kmi.idname == 'object.delete':
            kmi.properties.confirm = confirm


def update_auto_delete_confirm_delete(self, context):
    sync_confirm_delete()

class AutoDelete(bpy.types.Operator):
    bl_idname = "keyops.auto_delete"
    bl_label = "KeyOps: Auto Delete"
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    # def invoke(self, context, event):
    #     prefs = get_keyops_prefs()
    #     if prefs.auto_delete_confirm_object_mode:
    #         return context.window_manager.invoke_confirm(self, event)
    #     return self.execute(context)


    def execute(self, context):
        prefs = get_keyops_prefs()
        select_mode = context.tool_settings.mesh_select_mode
        if select_mode[0]:
            bpy.ops.mesh.delete(type='VERT')
        elif select_mode[1]:
            if prefs.auto_delete_dissolv_edge:
                bpy.ops.mesh.dissolve_edges()
            else:
                bpy.ops.mesh.delete(type='EDGE')
        elif select_mode[2]:
            bpy.ops.mesh.delete(type='FACE')
        else:
            self.report({'ERROR'}, "Invalid selection mode")

        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(AutoDelete)
    register_auto_delete_keymaps()


def unregister():
    clear_registered_keymaps(registered_auto_delete_keymaps)
    bpy.utils.unregister_class(AutoDelete)



def set_enabled(on):
    """Preferences may not exist yet at register time: apply the confirm setting once they do."""
    if on:
        sync_confirm_delete()
