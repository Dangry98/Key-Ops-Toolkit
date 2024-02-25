import bpy
from ..utils.pref_utils import get_keyops_prefs

class ToggleRetopology(bpy.types.Operator):
    bl_idname = "keyops.toggle_retopology"
    bl_label = "KeyOps: Toggle Retopology"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        overlay = bpy.context.space_data.overlay
        settings = bpy.context.scene.tool_settings
        prefs = get_keyops_prefs()

        retopology_overlay_color = prefs.toggle_retopology_color_enum

        Tool = prefs.toggle_retopology_tool_type  
        face_alpha = prefs.toggle_retopology_face_alpha
        if retopology_overlay_color == "custom_color":
            retopology_overlay_face_alpha = (retopology_overlay_color[0], retopology_overlay_color[1], retopology_overlay_color[2], face_alpha)
        theme = bpy.context.preferences.themes[0].view_3d

        if retopology_overlay_color == "custom_color":
            retopology_overlay_color = prefs.toggle_retopology_custom_color
            retopology_overlay_face_alpha = (retopology_overlay_color[0], retopology_overlay_color[1], retopology_overlay_color[2], prefs.toggle_retopology_face_alpha) 
        elif retopology_overlay_color == "maya":
            retopology_overlay_color = (0.0, 0.6, 1.0, 0.725)
            retopology_overlay_face_alpha = (retopology_overlay_color[0], retopology_overlay_color[1], retopology_overlay_color[2], 1.0)
        elif retopology_overlay_color == "blender_default":
            retopology_overlay_color = (0.313726, 0.784314, 1.0, 0.058824)
            retopology_overlay_face_alpha = (retopology_overlay_color[0], retopology_overlay_color[1], retopology_overlay_color[2], 0.301961)

        if not overlay.show_retopology:
            self.report({'INFO'}, "Retopology Mode, Toggle 5")
            overlay.show_retopology = True
            settings.use_snap = True
            settings.snap_elements = {'FACE'}

            if Tool == "custom":
                CustomTool = prefs.toggle_retopology_custom_tool
                if "bpy.ops" in CustomTool:
                    CustomTool = CustomTool.replace('bpy.ops.wm.tool_set_by_id(name=', '')
                    CustomTool = CustomTool.replace('"', '')
                    CustomTool = CustomTool.replace(")", "")
      
                bpy.ops.wm.tool_set_by_id(name=CustomTool)
            elif not Tool == "none":
                bpy.ops.wm.tool_set_by_id(name=Tool)

            theme.edge_width = prefs.toggle_retopology_edge_width
            theme.face_retopology = retopology_overlay_color
            theme.face_select = retopology_overlay_face_alpha 
            theme.edge_select = (0.98, 0.98, 0.98)
            theme.vertex_select = (0.98, 0.98, 0.98)

            if Tool == "mesh_tool.poly_quilt":
                bpy.ops.mesh.select_mode(type='EDGE')   

        else:
            self.report({'INFO'}, "Exit Retopology Mode, Toggle 5")
            
            settings.use_snap = False
            settings.snap_elements = {'INCREMENT', 'VERTEX'}
            if not Tool == "none":
                bpy.ops.wm.tool_set_by_id(name="mesh_tool.select_box_xray")
            settings.use_snap = False
            overlay.show_retopology = False

            theme.edge_width = 1
            theme.face_select = (1.0, 0.647, 0.322, 0.301961)
            theme.edge_select = (1.0, 0.67, 0.0)
            theme.vertex_select = (1.0, 0.478431, 0.0)

        return {'FINISHED'}
