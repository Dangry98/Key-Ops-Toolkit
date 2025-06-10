import bpy.types
import os
import time
from ..utils.pref_utils import get_keyops_prefs, get_icon
import tempfile

prefs = get_keyops_prefs()
totall_tris = 0

class CADDecimate(bpy.types.Operator):
    bl_idname = "keyops.cad_decimate"
    bl_label = "Auto CAD Decimate"
    bl_description = "Auto CAD Decimate"
    bl_options = {'REGISTER', 'UNDO'}

    totall_time = 0

    def execute(self, context):        
        totall_time = time.time()
        if bpy.context.scene.fast_mode == False:    
            export_time = time.time()
            bpy.ops.keyops.export_cad_decimate()
            export_time = time.time() - export_time
        
        decimate_time = time.time()
        bpy.ops.keyops.import_cad_decimate()
        decimate_time = time.time() - decimate_time

        if bpy.context.scene.fast_mode == False:    
            import_time = time.time()
            bpy.ops.keyops.import_all_cad_decimate()
            import_time = time.time() - import_time

        totall_time = time.time() - totall_time
        if bpy.context.scene.fast_mode == False:    
            print(f"Exported in {export_time:.4f} seconds")
            print(f"Decimated in {decimate_time:.4f} seconds")
            print(f"Imported in {import_time:.4f} seconds")
        print(f"Total Time: {totall_time:.4f} seconds")
        
        return {'FINISHED'}
        
    def register():
        bpy.utils.register_class(ExportCADDecimate)
        bpy.utils.register_class(ImportCADDecimate)
        bpy.utils.register_class(ImportAllCADDecimate)
        bpy.utils.register_class(CADDecimatePanel)
    def unregister():
        bpy.utils.unregister_class(ExportCADDecimate)
        bpy.utils.unregister_class(ImportCADDecimate)
        bpy.utils.unregister_class(ImportAllCADDecimate)
        bpy.utils.unregister_class(CADDecimatePanel)

class ExportCADDecimate(bpy.types.Operator):
    bl_idname = "keyops.export_cad_decimate"
    bl_label = "Export CAD Decimate"
    bl_description = "CAD Decimate"
    bl_options = {'REGISTER', 'UNDO'}

    export_time = 0

    @classmethod
    def poll(cls, context):
        return bpy.context.scene.fast_mode == False    

    def execute(self, context):
        global totall_tris

        export_time = time.time()
        export_type = None
        
        if bpy.context.scene.fast_mode == False:
            if bpy.context.scene.export_selected_only:
                export_type = [obj for obj in context.selected_objects if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']
            else:
                export_type = [obj for obj in context.scene.objects if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']
        else:
            export_type = [obj for obj in context.selected_objects if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']

        # if bpy.context.scene.procent_or_amount == 'AMOUNT':
        #     for obj in export_type:
        #         if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'SURFACE' or obj.type == 'FONT' or obj.type == 'META':
        #             m = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        #             tris = len(m.loop_triangles)
        #             totall_tris += tris

        bpy.ops.wm.console_toggle()
        output_directory = bpy.context.scene.cad_decimate_export_path
        os.makedirs(output_directory, exist_ok=True)
        bpy.ops.object.select_all(action='DESELECT')
        preserv_uv = bpy.context.scene.preserv_uvs

        for obj in export_type:
            if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META':
                obj.select_set(True)

                export_file = os.path.join(output_directory, f"{obj.name}.obj")
                #export_file = os.path.join(output_directory, f"{obj.name}.ply")

                bpy.ops.wm.obj_export(filepath=export_file, export_selected_objects=True, export_uv=preserv_uv, export_materials=False)
                #bpy.ops.wm.ply_export(filepath=export_file, export_selected_objects=True, export_uv=preserv_uv, ascii_format=True) 

                bpy.ops.object.delete()
            if bpy.context.scene.auto_clear_garbage_data:
                bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        export_time = time.time() - export_time
        print(f"Exported in {export_time:.4f} seconds")

        return {'FINISHED'}
    
#High Quality (Slow)
# OBJ =
# Exported in 92.2890 seconds
# Decimated in 587.5323 seconds
# Imported in 39.3740 seconds
# Total Time: 719.1953 seconds


# PLY =
# Exported in 58.7132 seconds
# Decimated in 624.0251 seconds
# Imported in 46.0575 seconds
# Total Time: 728.7957 seconds


#Medium Quality (Fast)
# OBJ =    
# Exported in 72.8535 seconds
# Decimated in 91.0822 seconds
# Imported in 29.1319 seconds
# Total Time: 193.0676 seconds

#PLY =
# Exported in 86.0192 seconds
# Decimated in 53.5972 seconds
# Imported in 36.6675 seconds
# Total Time: 176.2838 seconds

def high_quality_decimate():
    global totall_tris

    bpy.ops.object.modifier_add(type='DECIMATE')
    if bpy.context.scene.procent_or_amount == 'PROCENT':
        bpy.context.object.modifiers["Decimate"].ratio = bpy.context.scene.decimation_ratio
    else:
        bpy.context.object.modifiers["Decimate"].ratio = bpy.context.scene.tris_count / len(bpy.context.object.data.loop_triangles)
def medium_quality_decimate():
    bpy.ops.object.modifier_add(type='WELD')
    bpy.context.object.modifiers["Weld"].merge_threshold = bpy.context.scene.merge_distance
def low_quality_decimate():
    weld_modifier = bpy.context.object.modifiers.new(name="Weld", type='WELD')
    weld_modifier.mode = 'CONNECTED'
    weld_modifier.merge_threshold = bpy.context.scene.merge_distance
    
class ImportCADDecimate(bpy.types.Operator):
    bl_idname = "keyops.import_cad_decimate"
    bl_label = "Import CAD Decimate"
    bl_description = "Import and Decimate, then Export"
    bl_options = {'REGISTER', 'UNDO'}

    decimate_time = 0
    decimate_type = None

    def execute(self, context):      
        global totall_tris

        export_time = time.time()
        output_directory = bpy.context.scene.cad_decimate_export_path
        os.makedirs(output_directory, exist_ok=True)


        # export_type = [obj for obj in context.selected_objects if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']

        # if bpy.context.scene.procent_or_amount == 'AMOUNT' and bpy.context.scene.fast_mode == True:
        #     for obj in export_type:
        #         if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'SURFACE' or obj.type == 'FONT' or obj.type == 'META':
        #             m = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        #             tris = len(m.loop_triangles)
        #             totall_tris += tris

        # print(totall_tris)

        preserv_uv = bpy.context.scene.preserv_uvs

        if bpy.context.scene.deceimate_type == 'DECIMATE':
            self.decimate_type = high_quality_decimate
        elif bpy.context.scene.deceimate_type == 'WELD':
            self.decimate_type = medium_quality_decimate
        elif bpy.context.scene.deceimate_type == 'CONNECT':
            self.decimate_type = low_quality_decimate
        if bpy.context.scene.fast_mode == False:
        
            for file_name in os.listdir(output_directory):
                if file_name.endswith(".obj"):  
                    input_file = os.path.join(output_directory, file_name)
                    output_file = os.path.join(output_directory, file_name)

                    bpy.ops.wm.obj_import(filepath=input_file)
                
                    self.decimate_type()

                    #bpy.ops.wm.ply_export(filepath=output_file, export_selected_objects=True, export_uv=preserv_uv, ascii_format=True)
                    bpy.ops.wm.obj_export(filepath=output_file, export_selected_objects=True, export_uv=preserv_uv, export_materials=False)


                    bpy.ops.object.delete()
        else:
            selection = [obj for obj in context.selected_objects if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']
            for o in selection:
                bpy.context.view_layer.objects.active = o
                self.decimate_type()

        if bpy.context.scene.auto_clear_garbage_data:
                bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        decimate_time = time.time() - export_time
        print(f"Decimated in {decimate_time:.4f} seconds")

        return {'FINISHED'}   

class ImportAllCADDecimate(bpy.types.Operator):
    bl_idname = "keyops.import_all_cad_decimate"
    bl_label = "Import CAD Decimate"
    bl_description = "Import all in folder"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bpy.context.scene.fast_mode == False    

    def execute(self, context):
        output_directory = bpy.context.scene.cad_decimate_export_path
        os.makedirs(output_directory, exist_ok=True)

        imported_files = []  

        for file_name in os.listdir(output_directory):
            if file_name.endswith(".obj"):  
                input_file = os.path.join(output_directory, file_name)
                imported_files.append(file_name)  

        bpy.ops.wm.obj_import(filepath=input_file, directory=output_directory, files=[{"name": file_name} for file_name in imported_files])
        
        if bpy.context.scene.delete_files_after_import:
            for file_name in os.listdir(output_directory):
                if file_name.endswith(".obj"):  
                    input_file = os.path.join(output_directory, file_name)
                    imported_files.append(file_name)  
                    os.remove(input_file)

        bpy.ops.wm.console_toggle()
        return {'FINISHED'}


class KEYOPS_PT_cad_decimate_panel_manual(bpy.types.Panel):
    bl_parent_id = "KEYOPS_PT_cad_decimate_panel"
    bl_label = "Manual Decimation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT" and bpy.context.scene.fast_mode == False:
            return True

    def draw(self, context):
        layout = self.layout
        layout.operator("keyops.export_cad_decimate", text="Export")
        layout.operator("keyops.import_cad_decimate", text="CAD Decimate")
        layout.operator("keyops.import_all_cad_decimate", text="Import All")

def draw_cad_decimate_panel(self, context, draw_header=False):
        layout = self.layout
        box = layout.box()

        if get_keyops_prefs().enable_cad_decimate:
            if draw_header:
                box.label(text="CAD Decimate", icon_value=get_icon("mod_decim"))
            box.prop(context.scene, "deceimate_type", text="")
            if context.scene.deceimate_type != 'DECIMATE':
                box.label(text="Does not preserv UVs", icon='ERROR')
            box.prop(context.scene, "fast_mode", text="Enable Fast Mode", toggle=True)
            col = box.column(align=True)
            row = col.row(align=True)
            if bpy.context.scene.deceimate_type == 'DECIMATE':
                row.prop(context.scene, "procent_or_amount", text="Procent or Amount", expand=True)
                row = col.row(align=True)
                if bpy.context.scene.procent_or_amount == 'PROCENT':
                    row.prop(context.scene, "decimation_ratio", text="Decimation %")
                else:
                    row.prop(context.scene, "tris_count", text="Target Tris:")
            else:
                box.prop(context.scene, "merge_distance", text="Merge Amount")
            if bpy.context.scene.fast_mode == False:
                box.prop(context.scene, "export_selected_only", text="Selected Only")
            if bpy.context.scene.fast_mode == False and bpy.context.scene.deceimate_type == 'DECIMATE':
                box.prop(context.scene, "preserv_uvs", text="Preserve UVs")
            if bpy.context.scene.fast_mode == False:
                box.prop(context.scene, "delete_files_after_import", text="Delete Files After Import")
                box.prop(context.scene, "auto_clear_garbage_data", text="Clear Mesh Data")
                box.prop(context.scene, "cad_decimate_export_path", text="Path")

            row = box.row()
            row.operator("keyops.cad_decimate", text="CAD Decimate", icon='MOD_DECIM')
            row.scale_y = 1.4
class CADDecimatePanel(bpy.types.Panel):
    bl_description = "CAD Decimate Panel"
    bl_label = "CAD Decimate"
    bl_idname = "KEYOPS_PT_cad_decimate_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'
    bl_options = {'DEFAULT_CLOSED'}
    # bl_parent_id = "KEYOPS_PT_toolkit_panel"

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon_value=get_icon("mod_decim"))


    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT":
            return True

    def draw(self, context):
        draw_cad_decimate_panel(self, context, draw_header=False)

    def register():
        bpy.utils.register_class(KEYOPS_PT_cad_decimate_panel_manual)
        bpy.types.Scene.auto_clear_garbage_data = bpy.props.BoolProperty(name="Auto Clear Garbage Data", default=True, description="Auto Clear Mesh Data Blocks (Saves a lot of Memory, but is slower)")
        bpy.types.Scene.preserv_uvs = bpy.props.BoolProperty(name="Preserve UVs",default=True, description="Preserve UVs")
        bpy.types.Scene.cad_decimate_export_path = bpy.props.StringProperty(name="Path",subtype='FILE_PATH',description="Path for exporting files",default=os.path.join(tempfile.gettempdir(),"CAD_Decimate"))
        bpy.types.Scene.decimation_ratio = bpy.props.FloatProperty(name="Decimation Ratio",default=0.2, min=0.0,max=1.0,subtype='FACTOR',description="Decimation Ratio")
        bpy.types.Scene.delete_files_after_import = bpy.props.BoolProperty(name="Delete Files After Import", default=True, description="Delete Files After Import")
        bpy.types.Scene.export_selected_only = bpy.props.BoolProperty(name="Export Selected Only",default=True,description="Export Selected Only")
        bpy.types.Scene.deceimate_type = bpy.props.EnumProperty(name="deceimate_type",
            items=[('DECIMATE', 'High Quality (Slow)', 'High Quality, but slow'),
                ('WELD', 'Medium Quality (Fast)', 'Medium Quality, does not preserv UVs'),
                ('CONNECT', 'Low Quality (Fastest)', 'Low Quality, very fast! But does not preserv UVs')],
            default='DECIMATE',description="Decimate Quality")
        bpy.types.Scene.merge_distance = bpy.props.FloatProperty(name="Merge Distance",default=0.02,min=0.001,max=1.0,subtype='FACTOR',description="Merge Distance (higher value = more decimation)")
        bpy.types.Scene.format = bpy.props.EnumProperty(name="format",
            items=[('OBJ', 'OBJ(Reliable, but slower)', 'OBJ'),
                ('PLY', 'PLY (Faster, but more error prone)', 'PLY'),
                ('COLLADA', 'COLLADA (Fastest, but always triangulated)', 'COLLADA')],
            default='COLLADA',description="Format")
        bpy.types.Scene.fast_mode = bpy.props.BoolProperty(default=True, description="Disabling 'Fast Mode' is Slower, but it can handle way more polygons without crashing Blender")
        bpy.types.Scene.procent_or_amount = bpy.props.EnumProperty(name="Procent or Amount",
            items=[('PROCENT', 'By Procent', 'By Procent'),
                ('AMOUNT', 'By Tris Count', 'By Tris Amount')],
            default='PROCENT',description="Procent or Amount")
        bpy.types.Scene.tris_count = bpy.props.IntProperty(name="Target Tris Count",default=10000,min=1,description="Target Tris Count")

    def unregister():
        bpy.utils.unregister_class(KEYOPS_PT_cad_decimate_panel_manual)
        del bpy.types.Scene.auto_clear_garbage_data
        del bpy.types.Scene.preserv_uvs
        del bpy.types.Scene.cad_decimate_export_path
        del bpy.types.Scene.decimation_ratio
        del bpy.types.Scene.delete_files_after_import
        del bpy.types.Scene.export_selected_only
        del bpy.types.Scene.deceimate_type
        del bpy.types.Scene.merge_distance
        del bpy.types.Scene.format
        del bpy.types.Scene.fast_mode
        del bpy.types.Scene.procent_or_amount
        del bpy.types.Scene.tris_count

