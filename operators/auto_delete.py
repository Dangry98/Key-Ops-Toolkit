import bpy.types
from ..utils.pref_utils import get_keyops_prefs

def remove_confirm_delete():
    prefs = get_keyops_prefs()

    if not prefs.auto_delete_confirm_object_mode:
        # wm = bpy.context.window_manager
        # km = wm.keyconfigs.active.keymaps['Object Mode']                    
        # km.keymap_items.new('object.delete', 'X', 'PRESS').properties.confirm = False
        
        #this does not work since the keymap is not aviable at startup
        for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
            if keymap.name == 'Object Mode':
                for keymap_item in keymap.keymap_items:
                    if keymap_item.name == "Delete" and keymap_item.type == "X":
                        if keymap_item.properties.confirm == True:
                            keymap_item.properties.confirm = False
        # for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
        #     if keymap.name == 'Object Mode':
        #         for keymap_item in keymap.keymap_items:
        #             if keymap_item.name == "Delete" and keymap_item.type == "X":
        #                 if keymap_item.properties.use_global == True:
        #                     keymap_item.properties.use_global = True
        #                     print("delete")
        
def default_confirm_delete():   
    for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
        if keymap.name == 'Object Mode':
            for keymap_item in keymap.keymap_items:
                if keymap_item.name == "Delete" and keymap_item.type == "X":
                    if keymap_item.properties.confirm == False:
                        keymap_item.properties.confirm = True

def update_auto_delete_confirm_delete(self, context):
    if self.auto_delete_confirm_object_mode:
        default_confirm_delete()
    else:
        remove_confirm_delete()

class AutoDelete(bpy.types.Operator):
    bl_idname = "keyops.auto_delete"
    bl_label = "KeyOps: Auto Delete"
    bl_options = {'REGISTER', 'UNDO'}

    object_mode: bpy.props.BoolProperty(
        name="Object Mode",
        description="Delete objects in object mode",
        default=False
    ) # type:ignore

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.mode == 'EDIT'

    # def invoke(self, context, event):
    #     prefs = get_keyops_prefs()
    #     if prefs.auto_delete_confirm_object_mode:
    #         return context.window_manager.invoke_confirm(self, event)
    #     return self.execute(context)
       

    def execute(self, context):
        if self.object_mode:
            # fast delete test
            import time
            start = time.time()
            for obj in bpy.context.selected_objects:
                for collection in list(obj.users_collection):
                    collection.objects.unlink(obj)
            #     bpy.data.objects.remove(obj)

            # bpy.data.batch_remove()
            # bpy.ops.object.delete(use_global=False, confirm=True)

            print("Time: ", time.time() - start)

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
        remove_confirm_delete()
    
    def unregister():
        default_confirm_delete()
