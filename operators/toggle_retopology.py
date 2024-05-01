import bpy
from ..utils.pref_utils import get_keyops_prefs
from ..utils.pref_utils import get_is_addon_enabled

xray_select = None

def save_current_snap_settings_to_prefs():
    prefs = get_keyops_prefs()
    settings = bpy.context.scene.tool_settings

    prefs.toggle_retopology_snapping_settings_save_string = f"{settings.use_snap},{','.join(map(str, settings.snap_elements))}"

def load_snap_settings_from_prefs():
    prefs = get_keyops_prefs()
    settings = bpy.context.scene.tool_settings
    savde_snap_settings = prefs.toggle_retopology_snapping_settings_save_string.split(",")

    if savde_snap_settings[0] == "True":
        settings.use_snap = True
    else:
        settings.use_snap = False

    snapping_settings_list_to_apply = set()

    for element in savde_snap_settings[1:]:
        snapping_settings_list_to_apply.add(element)

    settings.snap_elements = snapping_settings_list_to_apply

def save_current_theme_colors_to_prefs():
    prefs = get_keyops_prefs()
    theme = bpy.context.preferences.themes[0].view_3d
    prefs.savede_colors_theme_settings_string = f"{theme.edge_width},{','.join(map(str, theme.face_retopology))},{','.join(map(str, theme.face_select))},{','.join(map(str, theme.edge_select))},{','.join(map(str, theme.vertex_select))}"
    if bpy.app.version >= (4, 1, 0):
        prefs.savede_colors_theme_settings_string += f",{','.join(map(str, theme.edge_mode_select))},{','.join(map(str, theme.face_mode_select))}"

def load_theme_colors_from_prefs():
    prefs = get_keyops_prefs()
    theme = bpy.context.preferences.themes[0].view_3d
    if prefs.savede_colors_theme_settings_string:
        theme_settings = prefs.savede_colors_theme_settings_string.split(",")
        theme.edge_width = int(theme_settings[0])
        theme.face_retopology = (float(theme_settings[1]), float(theme_settings[2]), float(theme_settings[3]), float(theme_settings[4]))
        theme.face_select = (float(theme_settings[5]), float(theme_settings[6]), float(theme_settings[7]), float(theme_settings[8]))
        theme.edge_select = (float(theme_settings[9]), float(theme_settings[10]), float(theme_settings[11]))
        theme.vertex_select = (float(theme_settings[12]), float(theme_settings[13]), float(theme_settings[14]))
        if bpy.app.version >= (4, 1, 0):
            theme.edge_mode_select = (float(theme_settings[15]), float(theme_settings[16]), float(theme_settings[17]))
            theme.face_mode_select = (float(theme_settings[18]), float(theme_settings[19]), float(theme_settings[20]), float(theme_settings[21]))
            
class ToggleRetopology(bpy.types.Operator):
    bl_idname = "keyops.toggle_retopology"
    bl_label = "KeyOps: Toggle Retopology"
    bl_description = "Toggle Retopology Mode"
    bl_options = {'UNDO', 'PRESET', 'INTERNAL'}

    type: bpy.props.StringProperty(default="")#type:ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' or context.mode == 'OBJECT' and context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        global xray_select

        overlay = bpy.context.space_data.overlay
        settings = bpy.context.scene.tool_settings
        prefs = get_keyops_prefs()
        retopology_was_active = False
        theme = bpy.context.preferences.themes[0].view_3d
        tool = prefs.toggle_retopology_tool_type  

        if xray_select is None:
            xray_select = get_is_addon_enabled("space_view3d_xray_selection_tools")
        


        def enter_exit_retopology():
            save_current_theme_colors_to_prefs()
            save_current_snap_settings_to_prefs()

            self.report({'INFO'}, "Retopology Mode, Toggle press 5")
            overlay.show_retopology = True
            settings.use_snap = True

            if tool == "custom":
                CustomTool = prefs.toggle_retopology_custom_tool
                if "bpy.ops" in CustomTool:
                    CustomTool = CustomTool.replace('bpy.ops.wm.tool_set_by_id(name=', '').replace('"', '').replace(")", "")

                bpy.ops.wm.tool_set_by_id(name=CustomTool)
            elif not tool == "none":
                bpy.ops.wm.tool_set_by_id(name=tool)

            retopology_overlay_color = prefs.toggle_retopology_color_enum
            face_alpha = prefs.toggle_retopology_face_alpha

            if retopology_overlay_color == "custom_color":
                retopology_overlay_face_alpha = (retopology_overlay_color[0], retopology_overlay_color[1], retopology_overlay_color[2], face_alpha)

            if retopology_overlay_color == "custom_color":
                retopology_overlay_color = prefs.toggle_retopology_custom_color
                retopology_overlay_face_alpha = (retopology_overlay_color[0], retopology_overlay_color[1], retopology_overlay_color[2], prefs.toggle_retopology_face_alpha) 
            elif retopology_overlay_color == "maya":
                retopology_overlay_color = (0.0, 0.6, 1.0, 0.725)
                retopology_overlay_face_alpha = (retopology_overlay_color[0], retopology_overlay_color[1], retopology_overlay_color[2], 0.8)
            elif retopology_overlay_color == "blender_default":
                retopology_overlay_color = (0.313726, 0.784314, 1.0, 0.058824)
                retopology_overlay_face_alpha = (retopology_overlay_color[0], retopology_overlay_color[1], retopology_overlay_color[2], 0.301961)
            if bpy.app.version >= (4, 1, 0):
                theme.edge_mode_select = (1.0, 1.0, 1.0)
                theme.face_mode_select = (0.0, 0.6, 1.0, 0.8)

            theme.edge_width = prefs.toggle_retopology_edge_width
            theme.face_retopology = retopology_overlay_color
            theme.face_select = retopology_overlay_face_alpha 
            theme.edge_select = (0.98, 0.98, 0.98)
            theme.vertex_select = (0.98, 0.98, 0.98)

            snapping_settings_list_to_apply = set()

            if prefs.toggle_retopology_snapping_settings_vert == True:
                snapping_settings_list_to_apply.add("VERTEX")
            if prefs.toggle_retopology_snapping_settings_face == True:
                snapping_settings_list_to_apply.add("FACE")
            if prefs.toggle_retopology_snapping_settings_face_project == True:
                snapping_settings_list_to_apply.add("FACE_PROJECT")
            if prefs.toggle_retopology_snapping_settings_face_nearest == True:
                snapping_settings_list_to_apply.add("FACE_NEAREST")
            
            settings.snap_elements = snapping_settings_list_to_apply

            if tool == "mesh_tool.poly_quilt":
                bpy.ops.mesh.select_mode(type='EDGE')   

        def exit_retopology(context):
                self.report({'INFO'}, "Exit Retopology Mode")
                
                if not tool == "none":
                    if xray_select:
                        bpy.ops.wm.tool_set_by_id(name="mesh_tool.select_box_xray")
                    else:
                        bpy.ops.wm.tool_set_by_id(name="builtin.select_box")

                overlay.show_retopology = False

                load_theme_colors_from_prefs()
                load_snap_settings_from_prefs()


        if self.type == "new_target":
            cursor_loc = context.scene.cursor.location
            pos2 = (cursor_loc[0], cursor_loc[1], cursor_loc[2])
            bpy.ops.view3d.snap_cursor_to_selected()
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.mesh.primitive_plane_add(enter_editmode=False, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
            bpy.ops.object.mode_set(mode='EDIT')
            if overlay.show_retopology == True:
                overlay.show_retopology = False
            bpy.ops.mesh.delete(type='VERT')
            bpy.context.object.name = "New_Retopology_Mesh"
            context.scene.cursor.location = (pos2[0], pos2[1], pos2[2])

        if context.mode == 'OBJECT':
            if overlay.show_retopology == True:
                retopology_was_active = True
            bpy.ops.object.mode_set(mode='EDIT')
      
        if not overlay.show_retopology:
            enter_exit_retopology()
        else:
            exit_retopology(context)
            if retopology_was_active:
                bpy.ops.object.mode_set(mode='OBJECT')

        return {'FINISHED'}
    def register():
        bpy.utils.register_class(Retopolgy_Panel)
        bpy.utils.register_class(RETOPOLOGY_PT_Settings)
    def unregister():
        bpy.utils.unregister_class(Retopolgy_Panel)
        bpy.utils.unregister_class(RETOPOLOGY_PT_Settings)


class Retopolgy_Panel(bpy.types.Panel):
    bl_label = "Retopology"
    bl_idname = "RETOPOLOGY_PT_Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'
    
    def draw(self, context):
        layout = self.layout
        prefs = get_keyops_prefs()
        
        layout.scale_y = 1.5
        overlay = bpy.context.space_data.overlay
        if overlay.show_retopology == True:
            layout.operator("keyops.toggle_retopology", text="Exit Retopology", icon="CANCEL").type = ""
        else:
            row = layout.row(align=True)
            row.operator("keyops.toggle_retopology", text="Toggle Retopology", icon="GREASEPENCIL").type = ""
            row.popover(panel="RETOPOLOGY_PT_Settings", text="", icon="PREFERENCES")

        row = layout.row()
        row.scale_y = 0.7
        row.operator("keyops.toggle_retopology", text="New Retopology at Active", icon="ADD").type = "new_target"

        if prefs.toggle_retopology_tool_type == "mesh_tool.poly_quilt" and not get_is_addon_enabled("PolyQuilt"):
            row = layout.row()
            row.label(text="Poly Quilt Tool is not installed", icon="ERROR")
            row = layout.row()
            row.scale_y = 0.8
            row.operator("wm.url_open", text="Download").url = "https://github.com/Dangry98/PolyQuilt-for-Blender-4.0/releases"
        
class RETOPOLOGY_PT_Settings(bpy.types.Panel):
    bl_label = "Retopology Settings"
    bl_idname = "RETOPOLOGY_PT_Settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        prefs = get_keyops_prefs()

        row = layout.row()
        row.label(text="Settings:")

        row = layout.row()
        row.prop(prefs, "toggle_retopology_tool_type")
        if prefs.toggle_retopology_tool_type == "custom":
            row = layout.row()
            row.prop(prefs, "toggle_retopology_custom_tool")
        row = layout.row()

        row.prop(prefs, "toggle_retopology_color_enum")
        if prefs.toggle_retopology_color_enum == "custom_color":
            row.prop(prefs, "toggle_retopology_custom_color")
        row = layout.row()

        if prefs.toggle_retopology_color_enum == "custom_color":
            row.prop(prefs, "toggle_retopology_face_alpha")
        row.prop(prefs, "toggle_retopology_edge_width")

        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)

        
        col.label(text="Snapping Settings:")
        row = col.row(align=True)
        row.prop(prefs, "toggle_retopology_snapping_settings_vert", icon="SNAP_VERTEX")
        row.prop(prefs, "toggle_retopology_snapping_settings_face", icon="SNAP_FACE")
        row = col.row(align=True)
        row.prop(prefs, "toggle_retopology_snapping_settings_face_project", icon="SNAP_FACE")
        row.prop(prefs, "toggle_retopology_snapping_settings_face_nearest", icon="MOD_SHRINKWRAP")


        if prefs.toggle_retopology_tool_type == "mesh_tool.poly_quilt" and not get_is_addon_enabled("PolyQuilt"):
            row = layout.row()
            row.label(text="Poly Quilt Tool is not installed", icon="ERROR")
            row = layout.row()
            row.operator("wm.url_open", text="Download").url = "https://github.com/Dangry98/PolyQuilt-for-Blender-4.0/releases"
