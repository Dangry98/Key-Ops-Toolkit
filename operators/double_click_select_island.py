import bpy.types

class DoubleClickSelectIsland(bpy.types.Operator):
    bl_idname = "keyops.double_click_select_island"
    bl_label = "KeyOps: Double Click Select Island"
    bl_description = ""
    bl_options = {'INTERNAL', 'UNDO'}  

    def execute(self, context):
        if context.active_object is not None and context.active_object.type == 'MESH':
            if bpy.context.scene.tool_settings.use_uv_select_sync:
                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
            bpy.ops.uv.select_linked_pick('INVOKE_DEFAULT')
        elif context.active_object is not None and context.active_object.type == 'CURVE':
            bpy.ops.curve.select_linked_pick('INVOKE_DEFAULT')
        elif context.active_object is not None and context.active_object.type == 'CURVES':
            bpy.ops.curves.select_linked_pick('INVOKE_DEFAULT')
        return {'FINISHED'}

    def register():
        bpy.utils.register_class(SelectEdgeLoop)
        bpy.utils.register_class(SelectEdgeLoopShift)
    def unregister():
        bpy.utils.unregister_class(SelectEdgeLoop)
        bpy.utils.unregister_class(SelectEdgeLoopShift)
    
class SelectEdgeLoop(bpy.types.Operator):
    bl_idname = "keyops.select_edge_loop"
    bl_label = "KeyOps: Select Edge Loop"
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH' and context.scene.tool_settings.mesh_select_mode[1]
        
    def execute(self, context):
        bpy.ops.mesh.loop_select("INVOKE_DEFAULT", extend=True)
        return {'FINISHED'}
    

#needs a seperate class, registering two keymaps of the same operator causes issues for some reason
class SelectEdgeLoopShift(bpy.types.Operator):
    bl_idname = "keyops.select_edge_loop_shift"
    bl_label = "KeyOps: Select Edge Loop Shift"
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH' and context.scene.tool_settings.mesh_select_mode[1]
        
    def execute(self, context):
        bpy.ops.mesh.loop_select("INVOKE_DEFAULT", extend=True)
        return {'FINISHED'}
