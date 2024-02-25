import bpy
import os
from ..utils.pref_utils import get_keyops_prefs

"""""
TODO:
add more filetypes, settings and rules what should be exported
skip objects that has wire shading mode, to not export out booleons
"""

class QuickExport(bpy.types.Operator):
    bl_idname = "keyops.quick_export"
    bl_label = "KeyOps: Quick Export"
    bl_options = {'REGISTER'}

    def execute(self, context):

        active_collection = bpy.context.view_layer.active_layer_collection

        blend_file_name = bpy.path.basename(bpy.context.blend_data.filepath)

        file_name, file_ext = os.path.splitext(blend_file_name)

        file_name = ''.join([c for c in file_name if not c.isdigit() and c != '.'])

        blend_file_path = bpy.data.filepath

        dirs = blend_file_path.split(os.sep)

        dirs.pop()

        if active_collection.name == "high":
            file_name += "_high"
        elif active_collection.name == "low":
            file_name += "_low"

        if active_collection.name in ["high", "low"]:
            export_path = os.sep.join(dirs)
            export_path = os.path.join(export_path, "Bake")
            if not os.path.exists(export_path):
                # Create the "Bake" folder if it doesn't exist
                os.makedirs(export_path)
            export_path = os.path.join(export_path, file_name + ".obj")
        else:
            export_path = blend_file_path + ".obj"

        bpy.ops.wm.obj_export(filepath=export_path, apply_modifiers=True, export_selected_objects=True, global_scale=bpy.context.scene.scale)
        return {'FINISHED'}
    def register():
        bpy.utils.register_class(QuickExportPanel)
    def unregister():
        bpy.utils.unregister_class(QuickExportPanel)
                                

class QuickExportPanel(bpy.types.Panel):
    bl_description = "Quick Export Panel"
    bl_label = "Quick Export"
    bl_idname = "KEYOPS_PT_quick_export_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ToolKit'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return get_keyops_prefs().enable_quick_export
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("keyops.quick_export", text="Quick Export", icon="TRIA_RIGHT")
        row.scale_y = 1.25
        row = layout.row()
        row.prop(context.scene, "scale", text="Scale")

    def register():
        bpy.types.Scene.scale = bpy.props.FloatProperty(name="Scale", default=1.0)

    def unregister():
        del bpy.types.Scene.scale
