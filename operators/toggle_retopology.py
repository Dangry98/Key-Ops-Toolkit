import bpy
from ..utils.pref_utils import get_keyops_prefs, get_icon
from ..utils.pref_utils import clear_registered_keymaps
from ..utils.utilities import get_edit_mesh_tool_defs, get_tool_icon_value, get_tool_display_name

theme_wrong = False
check_theme_once = False
cached_theme_colors = None
BLENDER_VERSION = bpy.app.version
registered_toggle_retopology_keymaps = []

def register_toggle_retopology_keymaps():
    global registered_toggle_retopology_keymaps
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='Mesh', space_type='EMPTY')
    kmi = km.keymap_items.new('keyops.toggle_retopology', 'FIVE', 'PRESS')
    kmi.properties.type = ''
    registered_toggle_retopology_keymaps.append((km, kmi))

def reset_retopo_themes_on_unregister_addon():
    if bpy.context.preferences.use_preferences_save == True:
        prefs = get_keyops_prefs()
        if prefs.enable_toggle_retopology:
            load_theme_colors_from_prefs()

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
    global theme_wrong, cached_theme_colors
    prefs = get_keyops_prefs()
    theme = bpy.context.preferences.themes[0].view_3d
    prefs.savede_colors_theme_settings_string = f"{theme.edge_width},{','.join(map(str, theme.face_retopology))},{','.join(map(str, theme.face_select))},{','.join(map(str, theme.edge_select))},{','.join(map(str, theme.vertex_select))},{','.join(map(str, theme.edge_mode_select))},{','.join(map(str, theme.face_mode_select))}"

    #if the regualre none backup settings does match the current theme settings, then use the backup settings since it then it might been overwriten by mistake
    if prefs.savede_colors_theme_settings_string_backup2 != prefs.savede_colors_theme_settings_string and prefs.savede_colors_theme_settings_string_backup2 != "":
        prefs.savede_colors_theme_settings_string = prefs.savede_colors_theme_settings_string_backup2 
        theme_wrong = True
    else:
        prefs.savede_colors_theme_settings_string_backup2 = prefs.savede_colors_theme_settings_string
        theme_wrong = False

    cached_theme_colors = str(prefs.savede_colors_theme_settings_string_backup2)

def load_theme_colors_from_prefs(use_cache=False):
    theme_settings = ""
    theme = bpy.context.preferences.themes[0].view_3d

    if use_cache:
        global cached_theme_colors
        if cached_theme_colors:
            theme_settings = cached_theme_colors.split(",")
    else:
        prefs = get_keyops_prefs()
        if not prefs.savede_colors_theme_settings_string:
            # print("Keyops Failed to load retopo theme color from addon prefrences")
            return
        
        theme_settings = prefs.savede_colors_theme_settings_string.split(",")

    if theme_settings:
        theme.edge_width = int(theme_settings[0])
        theme.face_retopology = (float(theme_settings[1]), float(theme_settings[2]), float(theme_settings[3]), float(theme_settings[4]))
        theme.face_select = (float(theme_settings[5]), float(theme_settings[6]), float(theme_settings[7]), float(theme_settings[8]))
        theme.edge_select = (float(theme_settings[9]), float(theme_settings[10]), float(theme_settings[11]))
        theme.vertex_select = (float(theme_settings[12]), float(theme_settings[13]), float(theme_settings[14]))
        theme.edge_mode_select = (float(theme_settings[15]), float(theme_settings[16]), float(theme_settings[17]))
        theme.face_mode_select = (float(theme_settings[18]), float(theme_settings[19]), float(theme_settings[20]), float(theme_settings[21]))

def get_workspace_tool_items(self, context):
    tool_items = {}

    for tool_def in get_edit_mesh_tool_defs(context):
        tool_idname = getattr(tool_def, "idname", "")
        if tool_idname:
            tool_items[tool_idname] = get_tool_display_name(tool_idname, context)

    tool_ids = sorted(tool_items.keys())

    if not tool_ids:
        tool_ids = ["builtin.select_box"]
        tool_items["builtin.select_box"] = get_tool_display_name("builtin.select_box", context)

    return [(tool_id, tool_items.get(tool_id, tool_id), tool_id) for tool_id in tool_ids]

class SearchRetopologyTool(bpy.types.Operator):
    bl_idname = "keyops.search_retopology_tool"
    bl_label = "Search Retopology Tool"
    bl_description = "Search all available tools and assign one"
    bl_property = "tool"

    tool: bpy.props.EnumProperty(items=get_workspace_tool_items) # type: ignore

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        prefs.toggle_retopology_custom_tool = self.tool
        return {'FINISHED'}
        
class ToggleRetopology(bpy.types.Operator):
    bl_idname = "keyops.toggle_retopology"
    bl_label = "KeyOps: Toggle Retopology"
    bl_description = "Toggle Retopology Mode"
    bl_options = {'UNDO', 'INTERNAL'}

    type: bpy.props.StringProperty(default="") # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' or context.mode == 'OBJECT' and context.active_object is not None and context.active_object.type == 'MESH'
    
    def invoke(self, context, event):
        return self.execute(context)
    
    def draw(self, context):
        layout = self.layout
        box = layout.box()
        row = box.row()
        row.scale_y = 1.35
        row.operator("keyops.toggle_retopology", text="Toggle Retopology").type = ""
            

    def execute(self, context):
        prefs = get_keyops_prefs()
        overlay = bpy.context.space_data.overlay
        settings = bpy.context.scene.tool_settings
        retopology_was_active = False
        theme = bpy.context.preferences.themes[0].view_3d
        tool = prefs.toggle_retopology_custom_tool

        def enter_retopology(selected_tool):
            if retopology_was_active != True:
                save_current_theme_colors_to_prefs()
                save_current_snap_settings_to_prefs()

            self.report({'INFO'}, "Entered Retopology Mode, Toggle by pressing 5")
            overlay.show_retopology = True
            settings.use_snap = True

            resolved_tool = selected_tool
            if resolved_tool:
                if "bpy.ops" in resolved_tool:
                    resolved_tool = resolved_tool.replace('bpy.ops.wm.tool_set_by_id(name=', '').replace('"', '').replace(")", "")
                bpy.ops.wm.tool_set_by_id(name=resolved_tool)

            retopology_overlay_color = prefs.toggle_retopology_color_enum
            face_alpha = prefs.toggle_retopology_face_alpha

            if retopology_overlay_color == "custom_color":
                retopology_overlay_face_alpha = (retopology_overlay_color[0], retopology_overlay_color[1], retopology_overlay_color[2], face_alpha)

            if retopology_overlay_color == "custom_color":
                retopology_overlay_color = prefs.toggle_retopology_custom_color
                retopology_overlay_face_alpha = (retopology_overlay_color[0], retopology_overlay_color[1], retopology_overlay_color[2], prefs.toggle_retopology_face_alpha) 
            elif retopology_overlay_color == "maya":
                retopology_overlay_color = (0.0, 0.6, 1.0, 0.65)
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

        def exit_retopology(context, selected_tool):
            global theme_wrong
            self.report({'INFO'}, "Exit Retopology Mode")
            
            if selected_tool:
                try:
                    bpy.ops.wm.tool_set_by_id(name="mesh_tool.select_box_xray")
                except:
                    bpy.ops.wm.tool_set_by_id(name="builtin.select_box")

            overlay.show_retopology = False

            load_theme_colors_from_prefs()
            load_snap_settings_from_prefs()
            theme_wrong = False

        retopology_was_active = False

        if self.type == "new_target":
            cursor_loc = context.scene.cursor.location
            pos2 = (cursor_loc[0], cursor_loc[1], cursor_loc[2])
            bpy.ops.view3d.snap_cursor_to_selected()
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.mesh.primitive_plane_add(enter_editmode=False, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
            bpy.ops.object.mode_set(mode='EDIT')
            if overlay.show_retopology == True:
                retopology_was_active = True
                overlay.show_retopology = False
            bpy.ops.mesh.delete(type='VERT')
            bpy.context.object.name = "New_Retopology_Mesh"
            context.scene.cursor.location = (pos2[0], pos2[1], pos2[2])

        if context.mode == 'OBJECT':
            if overlay.show_retopology == True:
                retopology_was_active = True
            bpy.ops.object.mode_set(mode='EDIT')

        if self.type == "exit":
            exit_retopology(context, tool)
            if retopology_was_active:
                bpy.ops.object.mode_set(mode='OBJECT')
            return {'FINISHED'}
      
        if not overlay.show_retopology:
            enter_retopology(tool)
        else:
            exit_retopology(context, tool)
            if retopology_was_active:
                bpy.ops.object.mode_set(mode='OBJECT')
        
        return {'FINISHED'}

def draw_retopology_panel(self, context, draw_header=False):
    prefs = get_keyops_prefs()
    if prefs.enable_toggle_retopology == False:
        return
    global theme_wrong
    global check_theme_once

    layout = self.layout.box()
    prefs = get_keyops_prefs()

    if check_theme_once == False:
        theme = bpy.context.preferences.themes[0].view_3d
        prefs.savede_colors_theme_settings_string = f"{theme.edge_width},{','.join(map(str, theme.face_retopology))},{','.join(map(str, theme.face_select))},{','.join(map(str, theme.edge_select))},{','.join(map(str, theme.vertex_select))},{','.join(map(str, theme.edge_mode_select))},{','.join(map(str, theme.face_mode_select))}"

        if prefs.savede_colors_theme_settings_string_backup2 != prefs.savede_colors_theme_settings_string and prefs.savede_colors_theme_settings_string_backup2 != "":
            prefs.savede_colors_theme_settings_string = prefs.savede_colors_theme_settings_string_backup2 
            theme_wrong = True
        check_theme_once = True

    if draw_header:
        row = layout.row()
        row.label(text="Retopology", icon_value=get_icon("retopo"))
    
    overlay = bpy.context.space_data.overlay
    if theme_wrong:
        row = layout.row(align=True)
        row.scale_y =1.35
        row.operator("keyops.toggle_retopology", text="Reset Theme to Backup", icon="ERROR").type = "exit"
        row = layout.row(align=True)
        row.label(text="Theme settings are wrong")
    else:
        if overlay.show_retopology == True:
            row = layout.row(align=True)
         
            row.scale_y = 1.35
            row.operator("keyops.toggle_retopology", text="Exit Retopology", icon="CANCEL").type = ""
        else:
            row = layout.row(align=True)
        
            row.scale_y = 1.35
            row.scale_x = 1.15
            row.operator("keyops.toggle_retopology", text="Toggle Retopology").type = ""
            row.popover(panel="RETOPOLOGY_PT_Settings", text="", icon="PREFERENCES")
    row = layout.row()

    row.operator("keyops.toggle_retopology", text="New Retopology at Active", icon="ADD").type = "new_target"

    # if bpy.context.preferences.use_preferences_save == True:
    #     row = layout.row()
    #     row.scale_y = 0.8

    #     row.label(text="AutoSave Prefs is enabled", icon="ERROR")
    #     row = layout.row()
    #     row.scale_y = 0.8

    #     row.label(text="Please Disable")
    #     row.prop(bpy.context.preferences, "use_preferences_save", text="Disable", toggle=True)
    #     #link to website
    #     row = layout.row()
    #     row.scale_y = 0.8
    #     row.operator("wm.url_open", text="More Info").url = "https://key-ops-toolkit.notion.site/Maya-f9a3b12b0da24e82b6fe9f9ed01fdae3"


class Retopolgy_Panel(bpy.types.Panel):
    bl_label = "Retopology"
    bl_idname = "RETOPOLOGY_PT_Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon_value=get_icon("retopo"))
    
    def draw(self, context):
        draw_retopology_panel(self, context, draw_header=False)
       
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
        row.prop(prefs, "toggle_retopology_custom_tool")
        row.operator("keyops.search_retopology_tool", text="", icon="VIEWZOOM")
        row = layout.row(align=True)
        icon_value = get_tool_icon_value(prefs.toggle_retopology_custom_tool, context)
        if icon_value:
            row.label(text="", icon_value=icon_value)
        else:
            row.label(text="", icon='TOOL_SETTINGS')
        current_tool_name = get_tool_display_name(prefs.toggle_retopology_custom_tool, context) if prefs.toggle_retopology_custom_tool else "None"
        row.label(text=f"     Current Tool: {current_tool_name}")
        row = layout.row()

        row.prop(prefs, "toggle_retopology_color_enum")
        if prefs.toggle_retopology_color_enum == "custom_color":
            row.prop(prefs, "toggle_retopology_custom_color")
        row = layout.row()

        if prefs.toggle_retopology_color_enum == "custom_color":
            row.prop(prefs, "toggle_retopology_face_alpha")
        row = layout.row()
        row.label(text="Edge Width:")
        row.prop(prefs, "toggle_retopology_edge_width")

        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        
        col.label(text="Snapp Settings:")
        row = col.row(align=True)
        row.prop(prefs, "toggle_retopology_snapping_settings_vert", icon="SNAP_VERTEX")
        row.prop(prefs, "toggle_retopology_snapping_settings_face", icon="SNAP_FACE")
        row = col.row(align=True)
        row.prop(prefs, "toggle_retopology_snapping_settings_face_project", icon="SNAP_FACE")
        row.prop(prefs, "toggle_retopology_snapping_settings_face_nearest", icon="MOD_SHRINKWRAP")

def register_toggle_retopology():
    bpy.utils.register_class(SearchRetopologyTool)
    bpy.utils.register_class(ToggleRetopology)
    # bpy.utils.register_class(Retopolgy_Panel)
    bpy.utils.register_class(RETOPOLOGY_PT_Settings)
    register_toggle_retopology_keymaps()

def unregister_toggle_retopology():
    clear_registered_keymaps(registered_toggle_retopology_keymaps)
    bpy.utils.unregister_class(ToggleRetopology)
    bpy.utils.unregister_class(SearchRetopologyTool)
    # bpy.utils.unregister_class(Retopolgy_Panel)
    bpy.utils.unregister_class(RETOPOLOGY_PT_Settings)