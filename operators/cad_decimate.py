import bpy.types
import os
import time
from ..utils.pref_utils import get_keyops_prefs, get_icon
from ..utils.pref_utils import feature_on
import tempfile


totall_tris = 0

class CADDecimate(bpy.types.Operator):
    bl_idname = "keyops.cad_decimate"
    bl_label = "Auto CAD Decimate"
    bl_description = "Auto CAD Decimate"
    bl_options = {'REGISTER', 'UNDO'}

    totall_time = 0

    def execute(self, context):
        totall_time = time.time()
        if bpy.context.scene.keyops.fast_mode == False:    
            export_time = time.time()
            bpy.ops.keyops.export_cad_decimate()
            export_time = time.time() - export_time
        
        decimate_time = time.time()
        bpy.ops.keyops.import_cad_decimate()
        decimate_time = time.time() - decimate_time

        if bpy.context.scene.keyops.fast_mode == False:    
            import_time = time.time()
            bpy.ops.keyops.import_all_cad_decimate()
            import_time = time.time() - import_time

        totall_time = time.time() - totall_time
        if bpy.context.scene.keyops.fast_mode == False:    
            print(f"Exported in {export_time:.4f} seconds")
            print(f"Decimated in {decimate_time:.4f} seconds")
            print(f"Imported in {import_time:.4f} seconds")
        print(f"Total Time: {totall_time:.4f} seconds")
        
        return {'FINISHED'}
        
def register():
    bpy.utils.register_class(CADDecimate)
    bpy.utils.register_class(ExportCADDecimate)
    bpy.utils.register_class(ImportCADDecimate)
    bpy.utils.register_class(ImportAllCADDecimate)
    bpy.utils.register_class(CADDecimatePanel)
    bpy.utils.register_class(KEYOPS_PT_cad_decimate_panel_manual)


def unregister():
    bpy.utils.unregister_class(KEYOPS_PT_cad_decimate_panel_manual)
    bpy.utils.unregister_class(CADDecimate)
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
        return bpy.context.scene.keyops.fast_mode == False    

    def execute(self, context):
        global totall_tris

        export_time = time.time()
        export_type = None
        
        if bpy.context.scene.keyops.fast_mode == False:
            if bpy.context.scene.keyops.export_selected_only:
                export_type = [obj for obj in context.selected_objects if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']
            else:
                export_type = [obj for obj in context.scene.objects if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']
        else:
            export_type = [obj for obj in context.selected_objects if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']

        # if bpy.context.scene.keyops.procent_or_amount == 'AMOUNT':
        #     for obj in export_type:
        #         if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'SURFACE' or obj.type == 'FONT' or obj.type == 'META':
        #             m = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        #             tris = len(m.loop_triangles)
        #             totall_tris += tris

        if not bpy.app.background and "console_toggle" in dir(bpy.ops.wm):  # the system console only exists on Windows
            bpy.ops.wm.console_toggle()
        output_directory = bpy.context.scene.keyops.cad_decimate_export_path
        os.makedirs(output_directory, exist_ok=True)
        bpy.ops.object.select_all(action='DESELECT')
        preserv_uv = bpy.context.scene.keyops.preserv_uvs

        for obj in export_type:
            if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META':
                obj.select_set(True)

                export_file = os.path.join(output_directory, f"{obj.name}.obj")
                #export_file = os.path.join(output_directory, f"{obj.name}.ply")

                bpy.ops.wm.obj_export(filepath=export_file, export_selected_objects=True, export_uv=preserv_uv, export_materials=False)
                #bpy.ops.wm.ply_export(filepath=export_file, export_selected_objects=True, export_uv=preserv_uv, ascii_format=True) 

                bpy.ops.object.delete()
            if bpy.context.scene.keyops.auto_clear_garbage_data:
                bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
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

    # view_layer.objects.active, not context.object: from the Properties editor
    # context.object is the pinned/stale object (or None)
    obj = bpy.context.view_layer.objects.active
    decimate = obj.modifiers.new(name="Decimate", type='DECIMATE')
    if bpy.context.scene.keyops.procent_or_amount == 'PROCENT':
        decimate.ratio = bpy.context.scene.keyops.decimation_ratio
    else:
        obj.data.calc_loop_triangles()
        tris = len(obj.data.loop_triangles)
        decimate.ratio = min(1.0, bpy.context.scene.keyops.tris_count / tris) if tris else 1.0
def medium_quality_decimate():
    obj = bpy.context.view_layer.objects.active
    weld = obj.modifiers.new(name="Weld", type='WELD')
    weld.merge_threshold = bpy.context.scene.keyops.merge_distance
def low_quality_decimate():
    weld_modifier = bpy.context.view_layer.objects.active.modifiers.new(name="Weld", type='WELD')
    weld_modifier.mode = 'CONNECTED'
    weld_modifier.merge_threshold = bpy.context.scene.keyops.merge_distance


def _evaluated_tris(obj):
    """Triangle count of obj with its current modifier stack."""
    import numpy as np
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ob_eval = obj.evaluated_get(dg)
    if obj.type == 'MESH':
        polys = ob_eval.data.polygons
        totals = np.empty(len(polys), np.int32)
        polys.foreach_get("loop_total", totals)
        return int((totals - 2).sum())
    me = ob_eval.to_mesh()
    count = len(me.loop_triangles)
    ob_eval.to_mesh_clear()
    return count


def _target_tris(source_tris):
    scene = bpy.context.scene
    if scene.keyops.procent_or_amount == 'PROCENT':
        return int(source_tris * scene.keyops.decimation_ratio)
    return scene.keyops.tris_count


def _edge_stats(obj):
    """(median edge length, bounding box diagonal) of obj with its modifier stack, in local space."""
    import numpy as np
    dg = bpy.context.evaluated_depsgraph_get()
    ob_eval = obj.evaluated_get(dg)
    me = ob_eval.data if obj.type == 'MESH' else ob_eval.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    edges = np.empty(len(me.edges) * 2, np.int32)
    me.edges.foreach_get("vertices", edges)
    if obj.type != 'MESH':
        ob_eval.to_mesh_clear()
    if len(co) == 0 or len(edges) == 0:
        return 0.0, 0.0
    edges = edges.reshape(-1, 2)
    if len(edges) > 200_000:
        edges = edges[np.random.default_rng(0).choice(len(edges), 200_000, replace=False)]
    lengths = np.linalg.norm(co[edges[:, 0]] - co[edges[:, 1]], axis=1)
    return float(np.median(lengths)), float(np.linalg.norm(co.max(0) - co.min(0)))


# Weld never merges further than this fraction of the object size, so small details survive
WELD_MAX_DISTANCE = 0.002


def weld_decimate():
    """Medium: Weld (Connected) first does the cheap part of the reduction, Decimate
    does the last, quality-sensitive part.

    The weld distance is found automatically: it aims for the geometric middle between
    the source and target tri count (10M -> 100k welds to about 1M), never goes below
    1.5x the target, and never merges further than WELD_MAX_DISTANCE of the object size.
    Decimate is always the final step that hits the target."""
    import math
    obj = bpy.context.view_layer.objects.active
    source_tris = _evaluated_tris(obj)
    target = _target_tris(source_tris)
    if source_tris == 0 or target >= source_tris:
        return

    median_edge, diag = _edge_stats(obj)
    weld_goal = max(int(math.sqrt(source_tris * max(target, 1))), int(target * 1.5))
    max_dist = diag * WELD_MAX_DISTANCE

    weld = None
    if median_edge > 0 and max_dist > 0:
        weld = obj.modifiers.new(name="Weld", type='WELD')
        weld.mode = 'CONNECTED'

        def welded(dist):
            weld.merge_threshold = dist
            return _evaluated_tris(obj)

        best_dist, best_tris = 0.0, source_tris
        hi = min(median_edge * 4.0, max_dist)
        hi_tris = welded(hi)
        if hi_tris >= weld_goal:
            best_dist, best_tris = hi, hi_tris          # weld as much as allowed, still above goal
        else:
            lo = min(median_edge * 0.05, hi)
            for _ in range(7):                          # bisect: largest distance that stays above goal
                mid = math.sqrt(lo * hi)
                mid_tris = welded(mid)
                if mid_tris >= weld_goal:
                    lo, best_dist, best_tris = mid, mid, mid_tris
                    if mid_tris <= weld_goal * 1.3:
                        break
                else:
                    hi = mid

        if best_dist > 0 and best_tris < source_tris:
            weld.merge_threshold = best_dist
        else:                                           # weld can't help without hurting detail
            obj.modifiers.remove(weld)
            weld, best_tris = None, source_tris
    else:
        best_tris = source_tris

    decimate = obj.modifiers.new(name="Decimate", type='DECIMATE')
    decimate.ratio = min(1.0, target / max(best_tris, 1))
    print(f"Weld + Decimate '{obj.name}': {source_tris:,} -> weld "
          f"{best_tris:,} ({weld.merge_threshold if weld else 0:.6f}) -> decimate {target:,}")


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
        output_directory = bpy.context.scene.keyops.cad_decimate_export_path
        os.makedirs(output_directory, exist_ok=True)


        # export_type = [obj for obj in context.selected_objects if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']

        # if bpy.context.scene.keyops.procent_or_amount == 'AMOUNT' and bpy.context.scene.keyops.fast_mode == True:
        #     for obj in export_type:
        #         if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'SURFACE' or obj.type == 'FONT' or obj.type == 'META':
        #             m = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        #             tris = len(m.loop_triangles)
        #             totall_tris += tris

        # print(totall_tris)

        preserv_uv = bpy.context.scene.keyops.preserv_uvs

        if bpy.context.scene.keyops.deceimate_type == 'DECIMATE':
            self.decimate_type = high_quality_decimate
        elif bpy.context.scene.keyops.deceimate_type == 'WELD_DECIMATE':
            self.decimate_type = weld_decimate
        elif bpy.context.scene.keyops.deceimate_type == 'WELD':
            self.decimate_type = medium_quality_decimate
        elif bpy.context.scene.keyops.deceimate_type == 'CONNECT':
            self.decimate_type = low_quality_decimate
        if bpy.context.scene.keyops.fast_mode == False:
        
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

        if bpy.context.scene.keyops.auto_clear_garbage_data:
                bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
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
        return bpy.context.scene.keyops.fast_mode == False    

    def execute(self, context):
        output_directory = bpy.context.scene.keyops.cad_decimate_export_path
        os.makedirs(output_directory, exist_ok=True)

        imported_files = []  

        for file_name in os.listdir(output_directory):
            if file_name.endswith(".obj"):  
                input_file = os.path.join(output_directory, file_name)
                imported_files.append(file_name)  

        bpy.ops.wm.obj_import(filepath=input_file, directory=output_directory, files=[{"name": file_name} for file_name in imported_files])
        
        if bpy.context.scene.keyops.delete_files_after_import:
            for file_name in os.listdir(output_directory):
                if file_name.endswith(".obj"):  
                    input_file = os.path.join(output_directory, file_name)
                    imported_files.append(file_name)  
                    os.remove(input_file)

        if not bpy.app.background and "console_toggle" in dir(bpy.ops.wm):  # the system console only exists on Windows
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
        if context.mode == "OBJECT" and bpy.context.scene.keyops.fast_mode == False:
            return True

    def draw(self, context):
        layout = self.layout
        layout.operator("keyops.export_cad_decimate", text="Export")
        layout.operator("keyops.import_cad_decimate", text="CAD Decimate")
        layout.operator("keyops.import_all_cad_decimate", text="Import All")

def draw_cad_decimate_panel(self, context, draw_header=False):
        layout = self.layout
        box = layout.box()

        if feature_on("cad_decimate"):
            if draw_header:
                box.label(text="CAD Decimate", icon_value=get_icon("mod_decim"))
            decimate_type = context.scene.keyops.deceimate_type
            box.prop(context.scene.keyops, "deceimate_type", text="")
            if decimate_type != 'DECIMATE':
                box.label(text="Does not preserv UVs", icon='ERROR')
            box.prop(context.scene.keyops, "fast_mode", text="Enable Fast Mode", toggle=True)
            col = box.column(align=True)
            row = col.row(align=True)
            if decimate_type in {'DECIMATE', 'WELD_DECIMATE'}:
                row.prop(context.scene.keyops, "procent_or_amount", text="Procent or Amount", expand=True)
                row = col.row(align=True)
                if bpy.context.scene.keyops.procent_or_amount == 'PROCENT':
                    row.prop(context.scene.keyops, "decimation_ratio", text="Decimation %")
                else:
                    row.prop(context.scene.keyops, "tris_count", text="Target Tris:")
            if decimate_type in {'WELD', 'CONNECT'}:
                box.prop(context.scene.keyops, "merge_distance", text="Merge Amount")
            if decimate_type == 'WELD_DECIMATE':
                box.label(text="Weld distance is automatic", icon='INFO')
            if bpy.context.scene.keyops.fast_mode == False:
                box.prop(context.scene.keyops, "export_selected_only", text="Selected Only")
            if bpy.context.scene.keyops.fast_mode == False and bpy.context.scene.keyops.deceimate_type == 'DECIMATE':
                box.prop(context.scene.keyops, "preserv_uvs", text="Preserve UVs")
            if bpy.context.scene.keyops.fast_mode == False:
                box.prop(context.scene.keyops, "delete_files_after_import", text="Delete Files After Import")
                box.prop(context.scene.keyops, "auto_clear_garbage_data", text="Clear Mesh Data")
                box.prop(context.scene.keyops, "cad_decimate_export_path", text="Path")

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
        return False
        # if context.mode == "OBJECT":
        #     return True

    def draw(self, context):
        draw_cad_decimate_panel(self, context, draw_header=False)

