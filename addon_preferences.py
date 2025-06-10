import bpy
from .utils.register_extensions import enable_extension
from bpy.props import IntProperty, BoolProperty, FloatProperty, FloatVectorProperty, StringProperty, EnumProperty
from .utils.pref_utils import get_addon_name, get_is_addon_enabled, draw_keymap
from .operators.maya_navigation import update_tablet_navigation
from .operators.auto_delete import update_auto_delete_confirm_delete

current_available_tabs = []
do_once_over705 = False
do_once_under705 = False

def get_window_with():
    wm = bpy.context.window_manager
    for w in wm.windows:
        if w.screen:
            for area in w.screen.areas:
                if area.type == 'PREFERENCES':
                    prefrences_window_size = area.width
    return prefrences_window_size

def prefs_tabs_update(self, context):
    global current_available_tabs

    prefs_tabs = [("EXTENSIONS", "Extensions", ""),
                    ("KEYMAPS", "Keymaps", ""),
                    ("REBIND", "Rebind", "")]
    
    if get_window_with() <= 705:
        prefs_tabs.insert(1, ("SETTINGS", "Settings", ""))
    else:
        prefs_tabs[0] = ("EXTENSIONS", "Extensions / Settings", "")
        
    current_available_tabs = [tab[0] for tab in prefs_tabs]
    return prefs_tabs

class KeyOpsPreferences(bpy.types.AddonPreferences):
    tabs: bpy.props.EnumProperty(name="Tabs", items=prefs_tabs_update, default=None) # type: ignore
    bl_idname = get_addon_name()
 
    def draw(self, context):
        global current_available_tabs
        global do_once_over705
        global do_once_under705

        layout = self.layout
        column = layout.column(align=True)
        row = column.row()
        row.prop(self, "tabs", expand=True)

        tab_draw_funcs = {
            "EXTENSIONS": self.draw_extensions,
            "KEYMAPS": self.draw_keymaps,
            "REBIND": self.draw_rebind}

        if get_window_with() < 705 and "SETTINGS" in current_available_tabs:
            tab_draw_funcs["SETTINGS"] = self.draw_extensions

        was_extension = False
        if self.tabs == "EXTENSIONS":
            was_extension = True

        #compensate for the fact that the tabs enum is offset by 1 when settings is added so it does not jump around
        if get_window_with() > 705 and do_once_over705 == True:
            tab_to_switch = current_available_tabs
            current_tab_index = tab_to_switch.index(self.tabs) if self.tabs in tab_to_switch else 0
            if was_extension == False:
                self.tabs = tab_to_switch[current_tab_index - 1]
            do_once_over705 = False
        
        if get_window_with() < 705 and do_once_under705 == True:
            tab_to_switch = current_available_tabs
            current_tab_index = tab_to_switch.index(self.tabs) if self.tabs in tab_to_switch else 0
            if was_extension == False:
                self.tabs = tab_to_switch[current_tab_index + 1]
            do_once_under705 = False
         
        if get_window_with() <= 705:
            draw_func_type = layout
            do_once_over705 = True
        if get_window_with() > 705:
            draw_func_type = "box"
            do_once_under705 = True

        if draw_func_type == "box":
            box = column.box()
            tab_draw_funcs.get(self.tabs)(box)
        else:
            tab_draw_funcs.get(self.tabs)(layout)

    def draw_extensions(self, draw_func_type):
        def draw_section(draw_func_type, section_label, data):
            bb = draw_func_type
            bb.label(text=section_label)
            column = bb.column(align=True)
            for label, property_name, toggle, link, experimental in data:
                if experimental == 1 and not self.experimental:
                    continue
                row = column.split(factor=0.3, align=False)

                if toggle:
                    row.prop(self, property_name, toggle=True)
                elif property_name:
                    row.prop(self, property_name)
                if link:
                    row.operator("wm.url_open", text=label, emboss=False).url = link    
                else:
                    row.label(text=label)
            if section_label != "Game Art Toolkit":
                column.separator(type='LINE')
        
        if get_window_with() > 705:
            split = draw_func_type.split()
            b = split.box()
        else:
            b = draw_func_type

        if not self.tabs == "SETTINGS":
            maya_data = [("", "enable_maya_navigation", False, False, 0),
                        ("Selects Mesh Island in Vert/Face Mode - Left Dbl Click", "enable_double_click_select_island", False, "https://key-ops-toolkit.notion.site/Maya-f9a3b12b0da24e82b6fe9f9ed01fdae3", 0),
                        ("Instantly Delete Verts, Edges, Faces with Delete", "enable_auto_delete", True, "https://www.notion.so/key-ops-toolkit/Industri-Standard-f9a3b12b0da24e82b6fe9f9ed01fdae3?pvs=4#1d850b06529c4ed2acdcb5d6f9aa1adc", 0),
                        ("Toggle Retopo Overlay, Tools and Settings - in Toolkit Panel", "enable_toggle_retopology", True, "https://www.notion.so/key-ops-toolkit/Industri-Standard-f9a3b12b0da24e82b6fe9f9ed01fdae3?pvs=4#d6f58b151f544bcfb4635bd34a822495", 0),
                        ("Pivot in Object Mode that works similar to D in Maya", "enable_maya_pivot", True, "https://www.notion.so/key-ops-toolkit/Industri-Standard-f9a3b12b0da24e82b6fe9f9ed01fdae3?pvs=4#861885b3779c41cea910606072362507", 0),]
            draw_section(b, "Industry Standard", maya_data)

            pie_data = [("Faster way to Add Mesh Primitivs", "enable_add_objects_pie", True, "https://www.notion.so/key-ops-toolkit/Pie-Menu-e3eb5b5c1d85423da9f5bad8867791d7?pvs=4#778f4f17fb27436fa8eb83e89f19d2ae", 0),
                        ("WIP. Utility Pie Menu in Edit/Object Mode", "enable_utility_pie", True, "https://www.notion.so/key-ops-toolkit/Pie-Menu-e3eb5b5c1d85423da9f5bad8867791d7?pvs=4#84cef3262de2491c8e7fa7644c472f27", 1),
                        ("WIP. Faster way to Add Common Modifers", "enable_add_modifier_pie", True, "https://www.notion.so/key-ops-toolkit/Pie-Menu-e3eb5b5c1d85423da9f5bad8867791d7?pvs=4#ed8407c4f8944eeab6fe5be1444c4da2", 1),
                        ("Switch Workspace Faster", "enable_workspace_pie", True, "https://www.notion.so/key-ops-toolkit/Pie-Menu-e3eb5b5c1d85423da9f5bad8867791d7?pvs=4#2ac346b432b14864922c785ce6a0c89d", 0),
                        ("Better Shift S Pie Menu", "enable_cursor_pie", True, "https://www.notion.so/key-ops-toolkit/Pie-Menu-e3eb5b5c1d85423da9f5bad8867791d7?pvs=4#6c9d3f0da9a14256aefff33f73817a9f", 0),
                        ("WIP. UV Pies", "enable_uv_pies", True, "https://www.notion.so/key-ops-toolkit/Pie-Menu-e3eb5b5c1d85423da9f5bad8867791d7?pvs=4#37ab2bddffe242e58cde51b2c7896e1b", 1),]
            draw_section(b, "Pie Menu", pie_data)

            Extra_data = [("Useful shortcuts from 2.79x, click to learn more", "enable_legacy_shortcuts", False, "https://www.notion.so/key-ops-toolkit/Extra-de3a011e64b2403a94eeb2d6bc2f12df?pvs=4#00fbdb6e03e247ef87c75f51e295e616", 0),
                        ("1 Key in vert mode to Merge to nearest, Shift 1 Connect", "enable_fast_merge", True, "https://www.notion.so/key-ops-toolkit/Extra-de3a011e64b2403a94eeb2d6bc2f12df?pvs=4#de4f361b488740f8b06e76d7f16532ab", 0),
                        ("Adds more shortcuts to the modifier panel", "enable_modi_key", True, "https://www.notion.so/key-ops-toolkit/Extra-de3a011e64b2403a94eeb2d6bc2f12df?pvs=4#9549bb450f0942e9a0287c05fc4a4164", 0),
                        ("Adds Attributes Operations like select and assign", "enable_atri_op", True, "https://www.notion.so/key-ops-toolkit/Extra-de3a011e64b2403a94eeb2d6bc2f12df?pvs=4#7f69e4bcf6834fa1aabc1b2b11eb3b1f", 0),
                        ("Quick access to Viewport Overlays", "enable_viewport_menu", True, "https://www.notion.so/key-ops-toolkit/Extra-de3a011e64b2403a94eeb2d6bc2f12df?pvs=4#7f69e4bcf6834fa1aabc1b2b11eb3b1f", 0),
                        ("Adds extra options in the outliner", "enable_outliner_options", True, "https://www.notion.so/key-ops-toolkit/Extra-de3a011e64b2403a94eeb2d6bc2f12df?pvs=4#7f69e4bcf6834fa1aabc1b2b11eb3b1f", 0)]
            draw_section (b, "Extra", Extra_data)   

            Game_Art_Toolkit = [("Toolkit of UV tools in the N Panel", "enable_uv_tools", True, "https://www.notion.so/key-ops-toolkit/UV-faa2eddaa1cd440088a31f25aa23a2d8?pvs=4#53765f9f6be84ee1b0c1be85acf898b7", 0),
                                ("Decimate meshes that are in the 100 of millions of tris", "enable_cad_decimate", True, "https://www.notion.so/key-ops-toolkit/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c?pvs=4#108ee1e458744896aeec69d85a74e437", 0),
                                ("Tool to create LODs for meshes", "enable_auto_lod", True, "https://www.notion.so/key-ops-toolkit/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c?pvs=4#f512e65060d14450a310e4e4d8ed8aea", 0),
                                ("Operations for adding bake names for low and highpoly", "enable_quick_bake_name", True, "https://www.notion.so/key-ops-toolkit/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c?pvs=4#e5af43e833e14c3f8ba48d422a09f2dd", 0),
                                ("List of all the objects and there poly count", "enable_polycount_list", True, "https://www.notion.so/key-ops-toolkit/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c?pvs=4#9663042f6cfe448e88195ccc29aef9ef", 0),
                                ("New Object & Edit Mode operations in N Panel", "enable_toolkit_panel", True, "https://www.notion.so/key-ops-toolkit/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c?pvs=4#c333e08fe40348f29129f05ea749b07d", 0),
                                ("CTRL E to export out meshes", "enable_quick_export", True, "https://www.notion.so/key-ops-toolkit/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c?pvs=4#e45daeb724a648c09af8e0d719e6fbbc", 0),
                                ("Useful Matieral Utils and UI", "enable_material_index", True, "https://www.notion.so/key-ops-toolkit/Game-Art-Toolkit-4b6f85e7504c4cf1bf7ece9a095d929c?pvs=4#d0ae8f40d3784ae0b63be11184911700", 0)]
            draw_section(b, "Game Art Toolkit", Game_Art_Toolkit)

        #draw settings, should only draw in extensions tab if over 705, otherwise it should draw in settings tab
        if self.tabs == "SETTINGS" or get_window_with() > 705:
            if get_window_with() > 705:
                b = split.box()
                b.label(text="Settings:")

            if self.enable_maya_navigation:
                prefrences_input = bpy.context.preferences.inputs
                bb = b.box()
                bb
                column = bb.column()
                row = column.row()
                row.label(text="Alt Navigation")
                row = column.row()
                row.prop(self, "maya_navigation_tablet_navigation")
                row.prop(prefrences_input, "use_zoom_to_mouse", text="Zoom to Mouse")
                row = column.row()
                row.label(text="Drag Threshold")
                row.prop(prefrences_input, "drag_threshold_mouse", text="Mouse")
                row.prop(prefrences_input, "drag_threshold_tablet", text="Tablet")

            if self.enable_auto_delete:
                bb = b.box()
                bb

                def check_delete_menu_keymap():
                    for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                        if keymap.name == 'Object Mode':
                            for keymap_item in keymap.keymap_items:
                                if keymap_item.name == "Delete" and keymap_item.type == "X":
                                    return keymap_item.properties.confirm
                self.auto_delete_confirm_object_mode = check_delete_menu_keymap()

                column = bb.column()
                layout = column.split(factor=2.0)  
                row = layout.row()
                row.label(text="Auto Delete")
                row.prop(self, "auto_delete_dissolv_edge")
                row.prop(self, "auto_delete_confirm_object_mode", text="Confirm X in ObjectMode")
                #get the kemap item for the delete key in object mode and show the confirm option
                # row = layout.row()
                # row.prop(self, "auto_delete_confirm_edit_mode", text="Confirm X in EditMode")
                    # column.label(text="Delete Menu is still enabled in Object Mode", icon="QUESTION")
                    # row.operator("keyops.remove_delete_menu_object_mode_menu", text="Fix")
                # else:
                #     column = bb.column()
                #     layout = column
                #     row = layout.row()
                #     row.label(text="Auto Delete")
                #     row.prop(self, "auto_delete_dissolv_edge")
                #     row.operator("keyops.add_delete_menu_object_mode_menu", icon ="BACK", text="Reset to Default, popup menu")

            if self.enable_toggle_retopology:
                bb = b.box()
                bb.label(text="Toggle Retopology")

                column = bb.column()
                column.prop(self, "toggle_retopology_tool_type")
                if self.toggle_retopology_tool_type == "custom":
                    column.prop(self, "toggle_retopology_custom_tool")   
                if self.toggle_retopology_tool_type == "mesh_tool.poly_quilt" and not get_is_addon_enabled ("PolyQuilt_Fork"):
                    layout = column.split(factor=5.0)
                    row = layout.row()
                    row.label(text="Poly Quilt is not installed", icon="QUESTION")
                    repo_index = 0
                    pkg_id = "PolyQuilt_Fork"            
                    props = row.operator("extensions.package_install", text="Install")
                    props.repo_index = repo_index
                    props.pkg_id = pkg_id
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
                if self.maya_pivot_experimental:
                    row.prop(self, "maya_pivot_in_edit_mode")
                row.prop(self, "maya_pivot_experimental")

            if self.enable_fast_merge: 
                bb = b.box()
                bb
                column = bb.column()
                row = column.row()
                row.label(text="Fast Merge")
                row.alignment = 'EXPAND'
                row.prop(self, "fast_merge_merge_options", text="")
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
                    bb.label(text="Add Objects Pie Menu is Currently (Shift Alt A)", icon='QUESTION')

                    column = bb.column()
                    row = column.row()
                    row.alignment = 'LEFT'

                    row.operator("keyops.add_object_pie_rebind", text="Rebind to (Shift A)?"). type = "Add Object Pie Rebind Shift A"
                else:
                    bb = b.box()
                    bb.label(text="Add Objects Pie")

                    column = bb.column()
                    row = column.row()

                    row.label(text="Currently (Shift A)")
                    row.operator("keyops.add_object_pie_rebind", text="Reset to Default", icon ="BACK"). type = "Add Object Pie Rebind Shift Alt A" 
                
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
                row.prop(self, "add_object_pie_Enum")
                if self.add_object_pie_Enum == "BLEND":
                    row.prop(self, "add_object_pie_blend_file_path", text ="")
                    row.prop(self, "add_object_pie_blend_object_name", text ="Name")
                if self.add_object_pie_Enum == "CUSTOM":
                    row.prop(self, "add_object_pie_bpy_ops", text ="")

            if self.enable_toolkit_panel:
                bb = b.box()
                bb
                column = bb.column()
                row = column.row()
                row.label(text="Toolkit Panel")
                row.prop(self, "max_layout", text="3ds Max Inspired Layout")

            if self.enable_material_index:
                bb = b.box()
                bb
                column = bb.column()
                row = column.row()
                row.label(text="Material Utilities")
                row = column.row()
                row.prop(self, "material_list_type")
                if self.material_list_show_icons and self.material_list_type == "PREVIEW_ICONS":
                    row.prop(self, "material_list_icon_scale")
                else:
                    row.prop(self, "material_list_show_icons")
                row = column.row()
                row.prop(self, "material_utilities_panel")
                row.label(text="Material List Menu: Alt + M")
            
            bb = b.box()
            bb
            column = bb.column()
            row = column.row()
            row.label(text="Experimental")
            row.prop(self, "experimental", text="Enable Experimental", icon = "ERROR")

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
        row.label(text="Warning, this will permanently change your keymaps", icon='ERROR')
        
        bb = box.box()
        column = bb.column()
        row = column.row()
        row.label(text="Rebind")

        row.separator()
        row.separator()
        
        row = column.row()
        row.label(text="Rebind Context Menu")
        row.operator("keyops.rebind_rightclick")
        row.operator("keyops.rebind_w")

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
       
        row = column.row()
        row.label(text="Pie Menu Animation Timeout")
        if bpy.context.preferences.view.pie_animation_timeout == 6:
            row.operator("keyops.rebind", text="No Lag Pie Menu Settings").type = "No_Lag_Pie"
        else:
            row.operator("keyops.rebind", text = "Reset to Defualt", icon ="BACK").type = "Default_Pie"

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
    
    if get_is_addon_enabled ("PolyQuilt_Fork"):
        default_retology_tool = "mesh_tool.poly_quilt"
        toggle_retopology_default = True
    else:
        default_retology_tool = "mesh_tool.poly_quilt"
        #default_retology_tool = "builtin.select_box"
        toggle_retopology_default = False

    enable_auto_delete: BoolProperty(name="Auto Delete", default=True, update=enable_deco("auto_delete")) # type: ignore
    enable_toggle_retopology: BoolProperty(name="Toggle Retopology", default=toggle_retopology_default, update=enable_deco("toggle_retopology")) # type: ignore
    enable_maya_pivot: BoolProperty(name="Maya Pivot", default=True, update=enable_deco("maya_pivot")) # type: ignore
    enable_maya_navigation: BoolProperty(name="Alt Navigation", description="Adds Navigation that works like in Maya", default=True, update=enable_deco("maya_navigation")) # type: ignore
    enable_double_click_select_island: BoolProperty(name="Dbl-Click Select Mesh", description="Double Click to Select Mesh Island/Element", default=True, update=enable_deco("double_click_select_island")) # type: ignore
    enable_uv_tools: BoolProperty(name="UV Tools", default=True, update=enable_deco("uv_tools")) # type: ignore
    enable_uv_pies: BoolProperty(name="UV Pies", default=False, update=enable_deco("uv_pies")) # type: ignore
    enable_utility_pie: BoolProperty(name="Utility Pie", default=False, update=enable_deco("utility_pie")) # type: ignore
    enable_add_objects_pie: BoolProperty(name="Add Objects Pie", default=not get_is_addon_enabled ("Non_Destructive_Primitives"), update=enable_deco("add_objects_pie")) # type: ignore
    enable_add_modifier_pie: BoolProperty(name="Add Modifier Pie", default=False, update=enable_deco("add_modifier_pie")) # type: ignore
    enable_legacy_shortcuts: BoolProperty(name="Legacy Shortcuts", default=True, update=enable_deco("legacy_shortcuts")) # type: ignore
    enable_workspace_pie: BoolProperty(name="Workspace Pie", default=False, update=enable_deco("workspace_pie")) # type: ignore
    enable_cursor_pie: BoolProperty(name="Cursor Pie", default=True, update=enable_deco("cursor_pie")) # type: ignore
    enable_fast_merge: BoolProperty(name="Fast Merge & Connect", default=True, update=enable_deco("fast_merge")) # type: ignore
    enable_modi_key: BoolProperty(name="Modifier Key", default=True, update=enable_deco("modi_key")) # type: ignore
    enable_cad_decimate: BoolProperty(name="CAD Decimate", default=False, update=enable_deco("cad_decimate"))     # type: ignore
    enable_auto_lod: BoolProperty(name="Auto LOD", default=True, update=enable_deco("auto_lod")) # type: ignore
    enable_quick_bake_name: BoolProperty(name="Quick Bake Name", default=True, update=enable_deco("quick_bake_name")) # type: ignore
    enable_polycount_list: BoolProperty(name="Polycount List", default=True, update=enable_deco("polycount_list")) # type: ignore
    enable_toolkit_panel: BoolProperty(name="Toolkit Panel", default=True, update=enable_deco("toolkit_panel")) # type: ignore
    enable_quick_export: BoolProperty(name="Quick Export", default=True, update=enable_deco("quick_export")) # type: ignore
    enable_atri_op: BoolProperty(name="Atributes Operations", default=True, update=enable_deco("atri_op")) # type: ignore
    enable_material_index: BoolProperty(name="Material Utilities", default=True, update=enable_deco("material_index")) # type: ignore
    enable_outliner_options: BoolProperty(name="Outliner Options", default=True, update=enable_deco("outliner_options")) # type: ignore
    enable_viewport_menu: BoolProperty(name="Viewport Menu", default=True, update=enable_deco("viewport_menu")) # type: ignore

    #prefs settings variables
    maya_navigation_tablet_navigation: BoolProperty(name="Tablet Navigation", description="Makes it easier to use tablet by adding zoom and pan to ctrl alt lmb and shift alt lmb", default=True, update= update_tablet_navigation) # type: ignore 
    auto_delete_dissolv_edge: BoolProperty(name="Dissolve Edge", default=False, description="Dissolve Edge in Edge Mode ") # type: ignore
    auto_delete_confirm_object_mode: BoolProperty(name="Confirm on X in Object Mode", description="Confirm Delete in Object Mode on the X key", default=False, update= update_auto_delete_confirm_delete) # type: ignore
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
        name="Theme",
        items=[
            ("blender_default", "Blender Default", "Choose this option for the blender default color"),
            ("maya", "Maya", "Choose this option for maya color"),
            ("custom_color", "Custom Color", "Choose this option for custom tool")],
        default="maya") # type: ignore
    toggle_retopology_custom_color: FloatVectorProperty(name="", subtype='COLOR', size=4, default=(0.313726, 0.784314, 1.0, 0.058824), min=0.0, max=1.0) # type: ignore
    toggle_retopology_face_alpha: FloatProperty(name="Face Alpha", default=0.301961, min=0.0, max=1.0) # type: ignore
    toggle_retopology_edge_width: IntProperty(name="", default=2, min=1, max=5) # type: ignore
    toggle_retopology_snapping_settings_save_string: StringProperty(name="Snap Settings", default="") # type: ignore
    toggle_retopology_snapping_settings_vert: BoolProperty(name="Vert", default=False) # type: ignore
    toggle_retopology_snapping_settings_face: BoolProperty(name="Face", default=True) # type: ignore
    toggle_retopology_snapping_settings_face_project: BoolProperty(name="Face Project", default=False) # type: ignore
    toggle_retopology_snapping_settings_face_nearest: BoolProperty(name="Face Nearest", default=False) # type: ignore

    savede_colors_theme_settings_string: StringProperty(name="Saved Colors", default="") # type: ignore
    savede_colors_theme_settings_string_backup2: StringProperty(name="Saved Colors Backup", default="") # type: ignore
    maya_pivot_behavior: EnumProperty(
        name="Behavior",
        items=[
            ("TOGGLE", "Toggle", "Toggle key to move Pivot"),
            ("HOLD", "Hold", "Hold key to move Pivot")],
        default="HOLD") # type: ignore
    maya_pivot_show_gizmo: BoolProperty(name="Show Gizmo", default=True) # type: ignore
    maya_pivot_in_edit_mode: BoolProperty(name="In Edit Mode", default=True) # type: ignore
    maya_pivot_experimental: BoolProperty(name="Experimental", default=False) # type: ignore
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
    add_object_pie_relative_scale: FloatProperty(name="Screen Size", default=7.0, min=1.0, max=25.0, description="Default Relative Scale Value") # type: ignore
    add_object_pie_default_scale: FloatProperty(name="Size", default=2.0, min=0.1, max=10.0, unit='LENGTH', description="Default Regular Scale Size Value") # type: ignore
    add_object_pie_min_scale: FloatProperty(name="Min Size", default=0.01, min=0.0001, max=10.0, unit='LENGTH', description="Relative Scale Min Size Value") # type: ignore
    add_object_pie_Enum: EnumProperty(
        name="Top Right Option",
        items=[
            ("OTHER", "Other", "Deafult Add Menu", "ADD", 0),
            ("EMPTY", "Empty", "Empty", "EMPTY_ARROWS", 2),
            ("MONKEY", "Monkey", "Monkey", "MONKEY", 4),
            ("BLEND", ".blend", "Blender File", "BLENDER", 8)],
        default="OTHER") # type: ignore
            # ("CUSTOM", "Custom", "bpy.ops operation", "FILE_SCRIPT", 16)],
    add_object_pie_blend_file_path: StringProperty(name="Path", subtype='FILE_PATH') #type: ignore
    add_object_pie_blend_object_name: StringProperty(name="Object Name: add a , to add many objects; cube,cylinder,sphere etc") #type: ignore
    add_object_pie_bpy_ops: StringProperty(name="Operation") #type: ignore
    uv_tools_panel_name: StringProperty(name="", default="Toolkit") # type: ignore
    max_layout: BoolProperty(name="Max Layout", default=False, description="Edit mode - Toolkit Panel") # type: ignore
    material_utilities_panel: BoolProperty(name="Material Index Panel", default=True) # type: ignore
    material_list_icon_scale: FloatProperty(name="Icon Scale", default=2.0, min=0.1, max=10.0) # type: ignore
    material_list_type: EnumProperty(
        name="Type",
        items=[
            ("PREVIEW_ICONS", "Big Preview Icons", "Preview Icons", "IMAGE_DATA", 0),
            ("COMPACT_LIST", "Compact List", "Compact List", "PRESET", 1)],
        default="COMPACT_LIST") # type: ignore  
    material_list_show_icons: BoolProperty(name="Show Icons", default=True) # type: ignore
    experimental: BoolProperty(name="Experimental", default=False, description="Enable Experimental Features") # type: ignore
