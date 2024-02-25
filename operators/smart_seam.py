import bpy
import bmesh
from ..utils.pref_utils import get_keyops_prefs    

#finish this in 4.1 or remove it
class SmartSeam(bpy.types.Operator):
    bl_idname = "keyops.smart_seam"
    bl_label = "KeyOps: Smart Seam"
    bl_options = {'REGISTER', 'UNDO'}

    mark_sharp: bpy.props.BoolProperty(name="Mark Sharp", default=False)# type: ignore

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH' and bpy.context.scene.tool_settings.mesh_select_mode[1]

    def execute(self, context):
        prefs = get_keyops_prefs()
        seam_settings = prefs.smart_seam_settings

        if seam_settings == True:

            selected_objects = bpy.context.selected_objects
            
            all_seams = True
            for obj in selected_objects:
                if obj.type == 'MESH' and obj.mode == 'EDIT':
                    bm = bmesh.from_edit_mesh(obj.data)
                    selected_edges = [e for e in bm.edges if e.select]
                    if any(not e.seam for e in selected_edges):
                        all_seams = False
                        break

            for obj in selected_objects:
                if obj.type == 'MESH' and obj.mode == 'EDIT':
                    bm = bmesh.from_edit_mesh(obj.data)
                    selected_edges = [e for e in bm.edges if e.select]

                    if all_seams:
                        bpy.ops.mesh.mark_seam(clear=True)
                        bpy.ops.mesh.mark_sharp(clear=True)
                    else:
                        bpy.ops.mesh.mark_seam(clear=False)
                        if self.mark_sharp:
                            bpy.ops.mesh.mark_sharp()

                    bmesh.update_edit_mesh(obj.data)
            return {'FINISHED'}

        else:
            bpy.ops.mesh.mark_seam(clear=False)
            if self.mark_sharp:
                bpy.ops.mesh.mark_sharp()
            return {'FINISHED'}
        
    # def register():
    #     bpy.app.handlers.depsgraph_update_post.append(bpy.app.handlers.persistent(update_edge, persistent=True))

    # def unregister():
    #     bpy.app.handlers.depsgraph_update_post.remove(bpy.app.handlers.persistent(update_edge, persistent=True))

class RemoveSeam(bpy.types.Operator):
    bl_idname = "keyops.remove_seam"
    bl_label = "KeyOps: Remove Seam"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return context.active_object.type == 'MESH'
    
    def execute(self, context):
        bpy.ops.mesh.mark_seam(clear=True)
        bpy.ops.mesh.mark_sharp(clear=True)
        return {'FINISHED'}
    
# def update_edge_selection(self, scene):
#     if scene is None:
#         scene = bpy.context.scene
    
#     has_view_3d_area = False

#     for screen in bpy.data.screens:
#         for area in screen.areas:
#             if area.type == 'VIEW_3D':
#                 has_view_3d_area = True
#                 break
#         if has_view_3d_area:
#             break
    
#     if has_view_3d_area and bpy.context.mode == 'EDIT_MESH' and not bpy.context.space_data.overlay.show_retopology:
#         obj = bpy.context.active_object
#         if obj is not None and obj.type == 'MESH' and bpy.context.preferences.themes.get('Default') is not None:
#             theme = bpy.context.preferences.themes['Default']
#             face_select_alpha_def = 0.18039216101169586
#             edge_select_yellow = (1.0, 0.890196, 0.0)
#             edge_select_def = (1.0, 0.6274510025978088, 0.0)
#             edge_select_off = (0,0,0)
    
#             if bpy.context.tool_settings.mesh_select_mode[0]:
#                 theme.view_3d.edge_select = edge_select_def
#                 theme.view_3d.face_select[3] = face_select_alpha_def
            
#             elif bpy.context.tool_settings.mesh_select_mode[1]:
#                 theme.view_3d.edge_select = edge_select_yellow
            
#             elif bpy.context.tool_settings.mesh_select_mode[2]:
#                 theme.view_3d.edge_select = edge_select_off
#                 theme.view_3d.edge_select = edge_select_def
#                 theme.view_3d.face_select[3] = face_select_alpha_def

#     else:
#         pass

# def update_edge(self, context):
#     update_edge_selection(context.scene, None)

