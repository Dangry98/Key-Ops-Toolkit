import bpy
from .utils.register_extensions import enable_extension
from bpy.props import IntProperty, BoolProperty, FloatProperty, FloatVectorProperty, StringProperty, EnumProperty
from .utils.pref_utils import get_addon_name, get_is_addon_enabled, draw_keymap

def get_window_with():
    wm = bpy.context.window_manager
    for w in wm.windows:
        if w.screen:
            for area in w.screen.areas:
                if area.type == 'PREFERENCES':
                    prefrences_window_size = area.width
    return prefrences_window_size
    
class KeyOpsPreferences(bpy.types.AddonPreferences):
    prefs_tabs = [("EXTENSIONS", "Extensions", ""),
                        ("KEYMAPS", "Keymaps", ""),
                        #("KEYOPS", "Keyops", ""),
                        ("REBIND", "Remap", ""),
                        ("ABOUT", "About", "")]

    tabs: EnumProperty(name="Tabs", items=prefs_tabs, default="EXTENSIONS") # type: ignore
    bl_idname = get_addon_name()
 
    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)
        row = column.row()
        row.prop(self, "tabs", expand=True)

        tab_draw_funcs = {
            "EXTENSIONS": self.draw_extensions,
            "KEYMAPS": self.draw_keymaps,
            #"KEYOPS": self.draw_keyops,
            "REBIND": self.draw_rebind,
            "ABOUT": self.draw_about}

        box = column.box()
        tab_draw_funcs.get(self.tabs, lambda box: None)(box)

    def draw_extensions(self, box):
        def draw_section(box, section_label, data):
            bb = box.box()
            bb.label(text=section_label)
            column = bb.column(align=True)
            for label, property_name, toggle, operator, link in data:
                row = column.split(factor=0.3, align=False)

                if toggle:
                    row.prop(self, property_name, toggle=True)
                elif property_name:
                    row.prop(self, property_name)
                elif operator:
                    row.operator(operator)
                if link:
                    row.operator("wm.url_open", text=label, emboss= False).url = link    
                else:
                    row.label(text=label)

        split = box.split()
        b = split.box()

        maya_data = [("", "enable_maya_navigation", False, None, None),
                    ("Selects Mesh Island in Vert/Face Mode - Left Dbl Click", "enable_double_click_select_island", False, None, "https://key-ops-toolkit.notion.site/Maya-f9a3b12b0da24e82b6fe9f9ed01fdae3"),
                    ("Instantly Delete Objects, Verts, Edges, Faces with Delete", "enable_auto_delete", True, None, "https://key-ops-toolkit.notion.site/Maya-f9a3b12b0da24e82b6fe9f9ed01fdae3"),
                    ("Toggle Retopo Overlay, Tools and Settings - in Toolkit Panel", "enable_toggle_retopology", True, None, "https://key-ops-toolkit.notion.site/Maya-f9a3b12b0da24e82b6fe9f9ed01fdae3"),
                    ("D Pivot that works similar to D in Maya", "enable_maya_pivot", True, None, "https://key-ops-toolkit.notion.site/Maya-f9a3b12b0da24e82b6fe9f9ed01fdae3"),
                    ]
        draw_section(b, "Maya", maya_data)
        
        uv_data = [("Toolkit of UV tools", "enable_uv_tools", True, None, "https://key-ops-toolkit.notion.site/UV-faa2eddaa1cd440088a31f25aa23a2d8"),
                   ("WIP. UV Pies", "enable_uv_pies", True, None, "https://key-ops-toolkit.notion.site/UV-faa2eddaa1cd440088a31f25aa23a2d8"),]
        draw_section(b, "UV", uv_data)

        pie_data = [("Faster way to add mesh primitivs", "enable_add_objects_pie", True, None, "https://key-ops-toolkit.notion.site/Pie-Menu-e3eb5b5c1d85423da9f5bad8867791d7"),
                    ("WIP. Utility Pie Menu in Edit/Object Mode", "enable_utility_pie", True, None, "https://key-ops-toolkit.notion.site/UV-faa2eddaa1cd440088a31f25aa23a2d8"),
                    ("WIP. Faster way to Add Common Modifers", "enable_add_modifier_pie", True, None, "https://key-ops-toolkit.notion.site/Pie-Menu-e3eb5b5c1d85423da9f5bad8867791d7"),
                    ("Switch Workspace Faster", "enable_workspace_pie", True, None, "https://key-ops-toolkit.notion.site/Pie-Menu-e3eb5b5c1d85423da9f5bad8867791d7"),
                    ("Better Shift S Pie Menu", "enable_cursor_pie", True, None, "https://key-ops-toolkit.notion.site/Pie-Menu-e3eb5b5c1d85423da9f5bad8867791d7"),]
        draw_section(b, "Pie Menu", pie_data)

        Extra_data = [("Useful shortcuts from 2.79x, click to learn more", "enable_legacy_shortcuts", False, None, "https://key-ops-toolkit.notion.site/Blender-2-79x-639a8f60b4794927aede4c835a8af4fc"),
                      ("1 Merge to nearest, Shift 1 Connect", "enable_fast_merge", True, None, "https://key-ops-toolkit.notion.site/Extra-de3a011e64b2403a94eeb2d6bc2f12df"),
                      ("Adds more shortcuts to the modifier panel", "enable_modi_key", True, None, "https://key-ops-toolkit.notion.site/Extra-de3a011e64b2403a94eeb2d6bc2f12df"),
                      ("Adds Attributes Operations like select and assign", "enable_atri_op", True, None, "https://key-ops-toolkit.notion.site/Extra-de3a011e64b2403a94eeb2d6bc2f12df"),]
        draw_section (b, "Extra", Extra_data)   

        Game_Art_Toolkit = [("Tool to Decimate meshes that are in the 100 of millions of tris", "enable_cad_decimate", True, None, "https://key-ops-toolkit.notion.site/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c"),
                            ("WIP. Tool to create LODs for meshes", "enable_auto_lod", True, None, "https://key-ops-toolkit.notion.site/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c"),
                            ("Operations for adding bake names for low and highpoly", "enable_quick_bake_name", True, None, "https://key-ops-toolkit.notion.site/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c"),
                            ("Get a list of all the objects and there poly count", "enable_polycount_list", True, None, "https://key-ops-toolkit.notion.site/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c"),
                            ("Adds new modeling and utility operations", "enable_utilities_panel_op", True, None, "https://key-ops-toolkit.notion.site/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c"),
                            ("WIP. CTRL E to export out meshes based on the export settings", "enable_quick_export", True, None, "https://key-ops-toolkit.notion.site/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c"),
                            ("Material Index sorting, usful for 3ds Max multi materials", "enable_material_index", True, None, "https://key-ops-toolkit.notion.site/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c")]
        draw_section(b, "Game Art Toolkit", Game_Art_Toolkit)

        #draw settings    
        if get_window_with() < 700:
            b.separator()
            b.label(text="Settings:")
        else:
            b = split.box()

        if self.enable_auto_delete:
            bb = b.box()
            bb
            def check_delete_menu_keymap():
                is_delete_menu = False
                for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                    if keymap.name == 'Object Mode':
                        for keymap_item in keymap.keymap_items:
                            if keymap_item.name == "Delete" and keymap_item.type == "X":
                                if keymap_item.properties.confirm == True:
                                    is_delete_menu = True
                                    break
                return is_delete_menu
            is_delete_menu = check_delete_menu_keymap()
            if is_delete_menu:
                column = bb.column()
                layout = column.split(factor=0.0)  
                row = layout.row()
                row.label(text="Auto Delete")
                row.prop(self, "auto_delete_dissolv_edge")
                column.label(text="Warning, Delete Menu is still enabled in Object Mode (X)", icon="ERROR")
                column.operator("keyops.remove_delete_menu_object_mode_menu", text="Fix")
            else:
                column = bb.column()
                layout = column
                row = layout.row()
                row.label(text="Auto Delete")
                row.prop(self, "auto_delete_dissolv_edge")
                row.operator("keyops.add_delete_menu_object_mode_menu", icon ="BACK", text="Reset to Default, popup menu")

        if self.enable_toggle_retopology:
            bb = b.box()
            bb.label(text="Toggle Retopology")

            column = bb.column()
            column.prop(self, "toggle_retopology_tool_type")
            if self.toggle_retopology_tool_type == "custom":
                column.prop(self, "toggle_retopology_custom_tool")   
            if self.toggle_retopology_tool_type == "mesh_tool.poly_quilt" and not get_is_addon_enabled ("PolyQuilt"):
                layout = column.split(factor=5.0)
                row = layout.row()
                row.label(text="Poly Quilt is not installed", icon="ERROR")
                row.operator("wm.url_open", text="Download").url = "https://github.com/Dangry98/PolyQuilt-for-Blender-4.0/releases"
            column.prop(self, "toggle_retopology_color_enum")
            layout = column.split(factor=5.0)
            row = layout.row(align = True)
            if self.toggle_retopology_color_enum == "custom_color":
                row.prop(self, "toggle_retopology_custom_color")
                row.prop(self, "toggle_retopology_face_alpha")
                row.prop(self, "toggle_retopology_edge_width")
            else:
                row.label(text="Edge Width:")
                row.prop(self, "toggle_retopology_edge_width")

            row.prop(self, "toggle_retopology_snapping_settings_vert", icon="SNAP_VERTEX")
            row.prop(self, "toggle_retopology_snapping_settings_face", icon="SNAP_FACE")
            row.prop(self, "toggle_retopology_snapping_settings_face_project", icon="SNAP_FACE")
            row.prop(self, "toggle_retopology_snapping_settings_face_nearest", icon="MOD_SHRINKWRAP")

        if self.enable_maya_pivot:
            bb = b.box()
            column = bb.column()

            layout = column.split(factor=2.0)  
            row = layout.row()
            row.label(text="Maya Pivot")
            row.prop(self, "maya_pivot_behavior")
            row.prop(self, "maya_pivot_show_gizmo")

        if self.enable_fast_merge: 
            bb = b.box()
            bb
            column = bb.column()
            row = column.row()
            row.label(text="Fast Merge")
            row.alignment = 'LEFT'
            row.prop(self, "fast_merge_merge_options")
            row.prop(self, "fast_merge_soft_limit")
            if self.fast_merge_soft_limit == "max_polycount" or self.fast_merge_soft_limit == "max_limit_&_all_selected":
                row.prop(self, "fast_merge_polycount")

        if self.enable_add_objects_pie:
            def check_add_mesh_pie_keymap():
                is_add_mesh_pie_alt = False
                for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                    for keymap_item in keymap.keymap_items:
                        if keymap_item.name == "Add Mesh Pie" and keymap_item.type == "A" and keymap_item.shift and keymap_item.alt:
                            is_add_mesh_pie_alt = True
                            break
                return is_add_mesh_pie_alt
            is_add_mesh_pie_alt = check_add_mesh_pie_keymap()

            if is_add_mesh_pie_alt:
                bb = b.box()
                bb.label(text="Warning Add Objects Pie Menu is Currently (Shift Alt A)", icon='ERROR')

                column = bb.column()
                row = column.row()
                row.alignment = 'LEFT'

                row.operator("keyops.add_object_pie_rebind", text="Fix Rebind to (Shift A)?"). type = "Add Object Pie Rebind Shift A"
            else:
                bb = b.box()
                bb.label(text="Add Objects Pie")

                column = bb.column()
                row = column.row()

                row.label(text="Add Menu is currently (Shift Alt A)")
                row.alignment = 'LEFT'
                row.operator("keyops.add_object_pie_rebind", text="Reset Add Menu back to (Shift A)?", icon ="BACK"). type = "Add Object Pie Rebind Shift Alt A" 
            
            layout = column.split(factor=5.0)  
            row = layout.row()
            row.alignment = 'LEFT'
            row.prop(self, "add_object_pie_use_relative")
            row.prop(self, "add_object_pie_relative_scale")   
            row.prop(self, "add_object_pie_min_scale")    
            row.prop(self, "add_object_pie_default_scale")
            layout = column.split(factor=5.0)
            row = layout.row()
            row.alignment = 'LEFT'
            row.prop(self, "add_object_pie_empty")

        # if self.enable_uv_tools:
        #     bb = b.box()
        #     bb
        #     layout = bb.split(factor=0.0)
        #     column = bb.column()
        #     row = column.row()
        #     row.label(text="UV Tools")
        #     row.label(text="panel name (restart required)")  
        #     row.prop(self, "uv_tools_panel_name")

    def draw_keymaps(self, box):
        from .classes_keymap_items import keymap_items
        wm = bpy.context.window_manager
        kc = wm.keyconfigs.user

        if get_window_with() < 800:
            b = box.box()

            b.label(text="Operations")
            self.draw_maya_keymaps(kc, keymap_items, b)

            b.label(text="Pie Menus")
            self.draw_pie_keymaps(kc, keymap_items, b)
        else:
            split = box.split()

            b = split.box()
            b.label(text="Operations")
            self.draw_maya_keymaps(kc, keymap_items, b)

            b = split.box()
            b.label(text="Pie Menus")
            self.draw_pie_keymaps(kc, keymap_items, b)
            


    # def draw_keyops(self, box):
    #     column = box.column()
    #     column.label(text="Nothing here yet... will add somthing cool in the future")

    def draw_rebind(self, box):
        bb = box.box()
        column = bb.column()
        row = column.row()
        row.label(text="Rebind/Cusomize Shortcuts in Blender")
        row.separator()
        row = column.row()
        row.label(text="WIP. Warning this will permanently change your shortcuts", icon='ERROR')
        
        bb = box.box()
        column = bb.column()
        row = column.row()
        row.label(text="Rebind")

        row.separator()
        row.separator()
        
        row = column.row()
        row.label(text="Rebind Context Menu to (W)")
        row.operator("keyops.rebind_w")
        
        row = column.row()
        row.label(text="Rebind Context Menu to Default (RightClick)")
        row.operator("keyops.rebind_rightclick")

        def check_add_mesh_pie_keymap():
            is_add_mesh_pie_alt = False
            for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                for keymap_item in keymap.keymap_items:
                    if keymap_item.name == "Add Mesh Pie" and keymap_item.type == "A" and keymap_item.shift and keymap_item.alt:
                        is_add_mesh_pie_alt = True
                        break
            return is_add_mesh_pie_alt
        
        is_add_mesh_pie_alt = check_add_mesh_pie_keymap()

        if is_add_mesh_pie_alt:
            row = column.row()
            row.label(text="Rebind Add Menu")
            row.operator("keyops.add_object_pie_rebind", text="Add Menu to (Shift Alt A)"). type = "Add Object Pie Rebind Shift A"
        else:
            row = column.row()
            row.label(text="Rebind Add Menu")
            row.operator("keyops.add_object_pie_rebind", text="Reset Add Menu back to (Shift A)", icon ="BACK"). type = "Add Object Pie Rebind Shift Alt A"

        bb = box.box()
        column = bb.column()
        row = column.row()
        row.label(text="Pies")

        #pie menu settings
        row = column.row()
        row.label(text="Pie Menu Animation Timeout")
        if bpy.context.preferences.view.pie_animation_timeout == 6:
            row.operator("keyops.rebind", text="No Lag Pie Menu Settings").type = "No_Lag_Pie"
        else:
            row.operator("keyops.rebind", text = "Reset to Defualt", icon ="BACK").type = "Default_Pie"

        def check_view_camera_pie_keymap():
            is_view_camera_pie_space = False
            for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                for keymap_item in keymap.keymap_items:
                    if keymap_item.name == "Play Animation" and keymap_item.type == "SPACE" and keymap_item.shift==False:
                        is_view_camera_pie_space = True
                        break
            return is_view_camera_pie_space
            
        is_view_camera_pie_space = check_view_camera_pie_keymap()
        
        if is_view_camera_pie_space:
            row = column.row()

            row.label(text="View Camera Pie")
            row.operator("keyops.space_to_view_camera_pie", text="View Camera Pie to (Space)"). type = "Space To View Camera Pie Shift"
        else:
            row = column.row()

            row.label(text="View Camera Pie")
            row.operator("keyops.space_to_view_camera_pie", text="Reset Play back to (Space)", icon ="BACK"). type = "Space To View Camera Pie"            

    def draw_about(self, box):
        links = [("Documentation (incomplete, wip)", "https://key-ops-toolkit.notion.site/Key-Ops-Toolkit-Documentation-8683460f070542669f0dab4a92734dc9", "INFO"),
            ("" ,"", ""),
            ("" ,"", ""),
            
            ("" ,"", ""),
            ("My Favorite Addons:", "", "FUND"),

            ("HardOps/Boxcutter", "https://blendermarket.com/products/hard-ops--boxcutter-ultimate-bundle?ref=100", "WORLD"),
            ("Meshmachine", "https://blendermarket.com/products/meshmachine", "WORLD"),
            ("Machin3Tools", "https://blendermarket.com/products/machin3tools", "WORLD"),
            ("UVToolkit", "https://github.com/oRazeD/UVToolkit", "WORLD"),
            ("ZenUV", "https://blendermarket.com/products/zen-uv", "WORLD"),
            ("Modifier List", "https://github.com/Dangry98/modifier_list-for-Blender-4.0", "WORLD"),
            ("Pie Menu Editor", "https://blendermarket.com/products/pie-menu-editor", "WORLD"),
            ("Poly Quilt", "https://blenderartists.org/t/polyquilt-addon-for-blender-2-8/1168918/590?u=dangry", "WORLD"),
            ("UV Packmaster", "https://blendermarket.com/products/uvpackmaster", "WORLD"),
            ("X-Ray Selection Tools", "https://github.com/BenjaminSauder/EdgeFlow", "WORLD"),
            ("Edge Flow", "https://github.com/BenjaminSauder/EdgeFlow", "WORLD")]
        
        column = box.column()

        for idx, (text, url, icon) in enumerate(links):
            if idx % 2 == 0:
                row = column.row()
                if text == "":
                    row.separator()
                else:
                    row.operator("wm.url_open", text=text, icon=icon).url = url
            else:
                if text == "":
                    row.separator()
                else:
                    row.operator("wm.url_open", text=text, icon=icon).url = url

#The following code is based on the MACHIN3 addon: MACHIN3tools
#Check out there awesome addons here: https://machin3.io/
    def draw_maya_keymaps(self, kc, keysdict, layout):
        drawn = False
        
        ignore_list = ["MAYA_NAVIGATION", 
                        "DOUBLE_CLICK_SELECT_ISLAND",
                        "ADD_OBJECTS_PIE",
                        "VIEW_PIE",
                        "SELECT_EDGE_LOOP",
                        "WORKSPACE_PIE",
                        "CURSOR_PIE",
                        "ADD_MODIFIER_PIE",
                        "VIEW_CAMERA_PIE",
                        "UV_U_PIE",
                        "UV_SPACE_PIE",
                        "LEGACY_SHORTCUTS",
                        "UTILITY_PIE",
                        "UV_PIES"]

        for name in keysdict:
            if not any(string in name for string in ignore_list):
                keylist = keysdict.get(name)

                if draw_keymap(kc, name, keylist, layout):
                    drawn = True
        return drawn

    def draw_pie_keymaps(self, kc, keysdict, layout):
        drawn = False

        for name in keysdict:
            if "PIE" in name:
                keylist = keysdict.get(name)

                if draw_keymap(kc, name, keylist, layout):
                    drawn = True
        return drawn


    def enable_deco(extension):
        def update_enable(self, context):
            enable_extension(self, register=getattr(self, f"enable_{extension}"), extension=extension)
        return update_enable
    enable_auto_delete: BoolProperty(name="Auto Delete", default=True, update=enable_deco("auto_delete")) # type: ignore
    enable_toggle_retopology: BoolProperty(name="Toggle Retopology", default=True, update=enable_deco("toggle_retopology")) # type: ignore
    enable_maya_pivot: BoolProperty(name="Maya Pivot", default=True, update=enable_deco("maya_pivot")) # type: ignore
    enable_maya_navigation: BoolProperty(name="Maya Navigation", description="Adds Navigation that works like in Maya", default=True, update=enable_deco("maya_navigation")) # type: ignore
    enable_double_click_select_island: BoolProperty(name="Double Click Select Island", description="Double Click to Select Mesh Island like in Maya", default=True, update=enable_deco("double_click_select_island")) # type: ignore
    enable_uv_tools: BoolProperty(name="UV Tools", default=True, update=enable_deco("uv_tools")) # type: ignore
    enable_uv_pies: BoolProperty(name="UV Pies", default=False, update=enable_deco("uv_pies")) # type: ignore
    enable_utility_pie: BoolProperty(name="Utility Pie", default=True, update=enable_deco("utility_pie")) # type: ignore
    enable_add_objects_pie: BoolProperty(name="Add Objects Pie", default=True, update=enable_deco("add_objects_pie")) # type: ignore
    enable_add_modifier_pie: BoolProperty(name="Add Modifier Pie", default=False, update=enable_deco("add_modifier_pie")) # type: ignore
    enable_legacy_shortcuts: BoolProperty(name="Legacy Shortcuts", default=True, update=enable_deco("legacy_shortcuts")) # type: ignore
    enable_workspace_pie: BoolProperty(name="Workspace Pie", default=True, update=enable_deco("workspace_pie")) # type: ignore
    enable_cursor_pie: BoolProperty(name="Cursor Pie", default=True, update=enable_deco("cursor_pie")) # type: ignore
    enable_fast_merge: BoolProperty(name="Fast Merge & Connect", default=True, update=enable_deco("fast_merge")) # type: ignore
    enable_modi_key: BoolProperty(name="Modifier Key", default=True, update=enable_deco("modi_key")) # type: ignore
    enable_cad_decimate: BoolProperty(name="CAD Decimate", default=False, update=enable_deco("cad_decimate"))     # type: ignore
    enable_auto_lod: BoolProperty(name="Auto LOD", default=False, update=enable_deco("auto_lod")) # type: ignore
    enable_quick_bake_name: BoolProperty(name="Quick Bake Name", default=False, update=enable_deco("quick_bake_name")) # type: ignore
    enable_polycount_list: BoolProperty(name="Polycount List", default=True, update=enable_deco("polycount_list")) # type: ignore
    enable_utilities_panel_op: BoolProperty(name="Utilities Panel", default=True, update=enable_deco("utilities_panel_op")) # type: ignore
    enable_quick_export: BoolProperty(name="Quick Export", default=False, update=enable_deco("quick_export")) # type: ignore
    enable_atri_op: BoolProperty(name="Atributes Operations", default=True, update=enable_deco("atri_op")) # type: ignore
    enable_material_index: BoolProperty(name="Material Utilities", default=False, update=enable_deco("material_index")) # type: ignore

    default_retology_tool = "mesh_tool.poly_quilt"

    #prefs settings variables
    auto_delete_dissolv_edge: BoolProperty(name="Dissolve Edge", default=False) # type: ignore
    toggle_retopology_tool_type: EnumProperty(
        name="Tool",
        items=[
            ("builtin.select_box", "Select Box", "Choose this option for select box tool"),
            ("mesh_tool.poly_quilt", "Poly Quilt", "Choose this option for poly quilt tool"),
            ("none", "None", "Choose this option for no tool"),
            ("custom", "Custom Tool", "Choose this option for custom tool")],
        default=default_retology_tool)  # type: ignore
    toggle_retopology_custom_tool: StringProperty(name="Custom Tool", default="") # type: ignore
    toggle_retopology_color_enum: EnumProperty(
        name="Color",
        items=[
            ("blender_default", "Blender Default", "Choose this option for the blender default color"),
            ("maya", "Maya", "Choose this option for maya color"),
            ("custom_color", "Custom Color", "Choose this option for custom tool")],
        default="maya") # type: ignore
    toggle_retopology_custom_color: FloatVectorProperty(name="", subtype='COLOR', size=4, default=(0.313726, 0.784314, 1.0, 0.058824), min=0.0, max=1.0) # type: ignore
    toggle_retopology_face_alpha: FloatProperty(name="Face Alpha", default=0.301961, min=0.0, max=1.0) # type: ignore
    toggle_retopology_edge_width: IntProperty(name="", default=3, min=1, max=5) # type: ignore
    toggle_retopology_snapping_settings_save_string: StringProperty(name="Snap Settings", default="") # type: ignore
    toggle_retopology_snapping_settings_vert: BoolProperty(name="Vert", default=False) # type: ignore
    toggle_retopology_snapping_settings_face: BoolProperty(name="Face", default=True) # type: ignore
    toggle_retopology_snapping_settings_face_project: BoolProperty(name="Face Project", default=False) # type: ignore
    toggle_retopology_snapping_settings_face_nearest: BoolProperty(name="Face Nearest", default=False) # type: ignore

    savede_colors_theme_settings_string: StringProperty(name="Saved Colors", default="") # type: ignore
    maya_pivot_behavior: EnumProperty(
        name="Behavior",
        items=[
            ("TOGGLE", "Toggle", "Toggle key to move Pivot"),
            ("HOLD", "Hold", "Hold key to move Pivot")],
        default="HOLD") # type: ignore
    maya_pivot_show_gizmo: BoolProperty(name="Show Gizmo", default=True) # type: ignore
    fast_merge_merge_options: EnumProperty( 
        name="Options",
        items=[
            ("merge to nerest vert if no active", "Merge nearest if no Active and > 1 Vert Selected", "Merge to nearest vert if no active vert and over 1 vert is selected"),
            ("always merge to nearest vert", "Always merge to nearest vert", "Always merge to nearest vert"),
            ("only merge if active or only 1 verts is selected", "Merge nearest if 1 Vert is Selected, Otherwise Active", "(legacy) only merge if active vert or only 1 verts is selected")],
        default="merge to nerest vert if no active") # type: ignore
    fast_merge_soft_limit: EnumProperty(
        name="Limit",
        items=[
            ("max_polycount", "Max Polycount", "Limit the polycount of the mesh"),
            ("all_selected", "All Selected", "Do not merge if all verts are selected"),
            ("max_limit_&_all_selected", "Max Limit & All Selected", "Do not merge if all verts are selected and polycount is above limit"),
            ("ask_if_no_active_vert", "Confirm to Merge if No Active", "Ask if no active vert"),
            ("no_limit", "No Limit", "Merge all selected verts")],
        default="ask_if_no_active_vert") # type: ignore
    fast_merge_polycount: IntProperty(name="Verts", default=1000, min=1, max=1000000) # type: ignore
    add_object_pie_use_relative: BoolProperty(name="Relative Scale", default=True, description="Default Relative Scale Value") # type: ignore
    add_object_pie_relative_scale: FloatProperty(name="Screen Size", default=6.0, min=1.0, max=25.0, description="Default Relative Scale Value") # type: ignore
    add_object_pie_default_scale: FloatProperty(name="Size", default=2.0, min=0.1, max=10.0, unit='LENGTH', description="Default Regular Scale Size Value") # type: ignore
    add_object_pie_min_scale: FloatProperty(name="Min Size", default=0.01, min=0.0001, max=10.0, unit='LENGTH', description="Relative Scale Min Size Value") # type: ignore
    add_object_pie_empty: BoolProperty(name="Add Empty Instead of Monkey", default=False) # type: ignore
    uv_tools_panel_name: StringProperty(name="", default="Toolkit") # type: ignore
   