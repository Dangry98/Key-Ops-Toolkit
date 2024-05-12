import bpy.types
from ..utils.pref_utils import get_keyops_prefs


class AutoDelete(bpy.types.Operator):
    bl_idname = "keyops.auto_delete"
    bl_label = "KeyOps: Auto Delete"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object.mode == 'EDIT'

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
