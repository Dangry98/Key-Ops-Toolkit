import bpy.types
from ..utils.pref_utils import get_keyops_prefs
        
class PivotPress(bpy.types.Operator):
    bl_idname = "keyops.pivot_press"
    bl_label = "KeyOps: Pivot Press"
    bl_description = "Move Pivot Key Press"
    bl_options = {'REGISTER', 'PRESET'}

    type: bpy.props.StringProperty(default="") # type: ignore

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.mode == 'OBJECT'
    
    def execute(self, context):
        prefs =  get_keyops_prefs()
        pivot_behavior = prefs.maya_pivot_behavior
        show_gizmo = prefs.maya_pivot_show_gizmo

        if self.type == 'PivotPress':
            if pivot_behavior == 'TOGGLE':
                context.scene.tool_settings.use_transform_data_origin = not context.scene.tool_settings.use_transform_data_origin
                if show_gizmo and bpy.context.space_data.show_gizmo_object_translate == False:
                    bpy.context.space_data.show_gizmo_object_translate = True
                elif show_gizmo:
                    bpy.context.space_data.show_gizmo_object_translate = False
                              
            else:
                context.scene.tool_settings.use_transform_data_origin = True
                if show_gizmo and bpy.context.space_data.show_gizmo_object_translate == False:
                    bpy.context.space_data.show_gizmo_object_translate = True
                bpy.ops.transform.translate()

        elif self.type == 'PivotRelease':
            if pivot_behavior == 'HOLD':
                context.scene.tool_settings.use_transform_data_origin = False
                if show_gizmo:
                    bpy.context.space_data.show_gizmo_object_translate = False
            
        return {'FINISHED'}

 