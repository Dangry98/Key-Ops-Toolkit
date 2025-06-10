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
    bl_options = {'REGISTER', 'UNDO'}

    scale: bpy.props.FloatProperty(name="Scale", default=1.0) # type: ignore
    format: bpy.props.EnumProperty(name="Format", items=[("OBJ", "Wavefront (.obj", "Wavefront (.obj)"), ("FBX", ".fbx", ".fbx"), ("GLTF", "GLTF", "GLTF"), ("USD", "USD", "USD"),("ABC", "Alembic (.ABC)", "Alembic")], default="OBJ") # type: ignore
    selected: bpy.props.BoolProperty(name="Selected", default=True) # type: ignore
    skip_wire: bpy.props.BoolProperty(name="Skip Wire Display", default=True) # type: ignore
    only_visible: bpy.props.BoolProperty(name="Only Visible", default=True) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scale")
        layout.prop(self, "selected")
        layout.prop(self, "skip_wire")
        layout.prop(self, "only_visible")
        layout.prop(self, "format")

    def execute(self, context):
        active_collection = bpy.context.view_layer.active_layer_collection
        blend_file_name = bpy.path.basename(bpy.context.blend_data.filepath)
        file_name, file_ext = os.path.splitext(blend_file_name)
        file_name = ''.join([c for c in file_name if not c.isdigit() and c != '.'])
        blend_file_path = bpy.data.filepath
        dirs = blend_file_path.split(os.sep)
        dirs.pop()

        if not dirs:
            self.report({'ERROR'}, "Blend file not saved")
            return {'CANCELLED'}
        export_path = blend_file_path 

        if "low" in active_collection.name.lower() or "high" in active_collection.name.lower():
            suffix = "_high" if "high" in active_collection.name.lower() else "_low"
            file_name += suffix

            export_path = os.path.join(os.path.dirname(blend_file_path), "Bake", file_name + f".{self.format.lower()}")
            if not os.path.exists(os.path.dirname(export_path)):
                os.makedirs(os.path.dirname(export_path))
                self.report({'INFO'}, f"Exported: {file_name} to Bake Folder")
        else:
            export_path = os.path.join(os.path.dirname(blend_file_path), file_name + f".{self.format.lower()}")
            self.report({'INFO'}, f"Exported: {file_name} to .blend file folder")

        if self.selected:
            if self.only_visible:
                selected = context.selected_objects
                for obj in context.scene.objects:
                    if obj.select_get():
                        obj.select_set(False)

                for obj in selected:
                    obj.select_set(True)

            if self.skip_wire:
                deselect_objects = context.selected_objects
                deselect_objects_skip_wire = [obj for obj in deselect_objects if obj.display_type == 'WIRE']
                for obj in deselect_objects_skip_wire:
                    obj.select_set(False)


        if self.format == "OBJ":
            bpy.ops.wm.obj_export(filepath=export_path, apply_modifiers=True, export_selected_objects=self.selected, global_scale=self.scale)
        elif self.format == "FBX":
            bpy.ops.export_scene.fbx(filepath=export_path, use_selection=self.selected, global_scale=self.scale)
        elif self.format == "GLTF":
            bpy.ops.export_scene.gltf(filepath=export_path, use_selection=self.selected)
        elif self.format == "USD":
            bpy.ops.wm.usd_export(filepath=export_path, selected_objects_only=self.selected)
        elif self.format == "ABC":
            bpy.ops.wm.alembic_export(filepath=export_path, selected=self.selected, global_scale=self.scale)
        return {'FINISHED'}

    
#     def register():
#         bpy.utils.register_class(QuickExportPanel)
#     def unregister():
#         bpy.utils.unregister_class(QuickExportPanel)
                                
# class QuickExportPanel(bpy.types.Panel):
#     bl_description = "Quick Export Panel"
#     bl_label = "Quick Export"
#     bl_idname = "KEYOPS_PT_quick_export_panel"
#     bl_space_type = 'VIEW_3D'
#     bl_region_type = 'UI'
#     bl_category = 'Toolkit'
#     bl_options = {'DEFAULT_CLOSED'}

#     @classmethod
#     def poll(cls, context):
#         if context.mode == "OBJECT":
#             return True
    
#     def draw(self, context):
#         layout = self.layout
#         row = layout.row()
#         row.operator("keyops.quick_export", text="Quick Export", icon="TRIA_RIGHT")
#         row.scale_y = 1.25
#         row = layout.row()
#         row.prop(context.scene, "scale", text="Scale")

#     def register():
#         bpy.types.Scene.scale = bpy.props.FloatProperty(name="Scale", default=1.0)

#     def unregister():
#         del bpy.types.Scene.scale
