# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ***** END GPL LICENSE BLOCK *****

from .addon_preferences import KeyOpsPreferences
from .operators.rebind import Rebind
from .ui.toolkit_paneL_ui import NewToolkitPanel

default_classes = [KeyOpsPreferences,Rebind, NewToolkitPanel]
debug = True

import bpy

def extension_register_unregister(extension, register):
    if extension == "auto_delete":
        if register:
            from .operators.auto_delete import register_auto_delete
            register_auto_delete()
        else:
            from .operators.auto_delete import unregister_auto_delete
            unregister_auto_delete()
    elif extension == "toggle_retopology":
        if register:
            from .operators.toggle_retopology import register_toggle_retopology
            register_toggle_retopology()
        else:
            from .operators.toggle_retopology import unregister_toggle_retopology
            unregister_toggle_retopology()
    elif extension == "maya_pivot":
        if register:
            from .operators.maya_pivot import register_maya_pivot
            register_maya_pivot()
        else:
            from .operators.maya_pivot import unregister_maya_pivot
            unregister_maya_pivot()
    elif extension == "maya_navigation":
        if register:
            from .operators.maya_navigation import register_maya_navigation
            register_maya_navigation()
        else:
            from .operators.maya_navigation import unregister_maya_navigation
            unregister_maya_navigation()
    elif extension == "double_click_select_island":
        if register:
            from .operators.double_click_select_island import register_double_click_select_island
            register_double_click_select_island()
        else:
            from .operators.double_click_select_island import unregister_double_click_select_island
            unregister_double_click_select_island()
    elif extension == "uv_tools":
        if register:
            from .operators.uv_tools import register_uv_tools
            register_uv_tools()
        else:
            from .operators.uv_tools import unregister_uv_tools
            unregister_uv_tools()
    elif extension == "uv_pies":
        if register:
            from .menu.pies import register_uv_pies
            register_uv_pies()
        else:
            from .menu.pies import unregister_uv_pies
            unregister_uv_pies()
    elif extension == "utility_pie":
        if register:
            from .menu.pies import register_utility_pie
            register_utility_pie()
        else:
            from .menu.pies import unregister_utility_pie
            unregister_utility_pie()

    elif extension == "add_objects_pie":
        if register:
            from .operators.add_mesh import register_add_objects_pie
            register_add_objects_pie()
        else:
            from .operators.add_mesh import unregister_add_objects_pie
            unregister_add_objects_pie()
    elif extension == "add_modifier_pie":
        if register:
            from .operators.add_modifier import register_add_modifier_pie
            register_add_modifier_pie()
        else:
            from .operators.add_modifier import unregister_add_modifier_pie
            unregister_add_modifier_pie()
    elif extension == "legacy_shortcuts":
        if register:
            from .operators.legacy_shortcuts import register_legacy_shortcuts_keymaps
            register_legacy_shortcuts_keymaps()
        else:
            from .operators.legacy_shortcuts import unregister_legacy_shortcuts
            unregister_legacy_shortcuts()
    elif extension == "cursor_pie":
        if register:
            from .operators.origin_to_selection import register_cursor_pie
            register_cursor_pie()
        else:
            from .operators.origin_to_selection import unregister_cursor_pie
            unregister_cursor_pie()
    elif extension == "fast_merge":
        if register:
            from .operators.fast_merge import register_fast_merge
            register_fast_merge()
        else:
            from .operators.fast_merge import unregister_fast_merge
            unregister_fast_merge()
    elif extension == "merge_tool":
        if register:
            from .tools.merge_tool import register_merge_tool
            register_merge_tool()
        else:
            from .tools.merge_tool import unregister_merge_tool
            unregister_merge_tool()
    elif extension == "modi_key":
        if register:
            from .operators.modi_key import register_modi_key
            register_modi_key()
        else:
            from .operators.modi_key import unregister_modi_key
            unregister_modi_key()
    elif extension == "cad_decimate":
        if register:
            from .operators.cad_decimate import register_cad_decimate
            register_cad_decimate()
        else:
            from .operators.cad_decimate import unregister_cad_decimate
            unregister_cad_decimate()
    elif extension == "auto_lod":
        if register:
            from .operators.auto_lod import register_auto_lod
            register_auto_lod()
        else:
            from .operators.auto_lod import unregister_auto_lod
            unregister_auto_lod()
    elif extension == "polycount_list":
        if register:
            from .operators.poly_count_list import register_polycount_list
            register_polycount_list()
        else:
            from .operators.poly_count_list import unregister_polycount_list
            unregister_polycount_list()
    elif extension == "toolkit_panel":
        if register:
            from .operators.toolkit_panel import register_toolkit_panel
            register_toolkit_panel()
        else:
            from .operators.toolkit_panel import unregister_toolkit_panel
            unregister_toolkit_panel()
    elif extension == "quick_bake_name":
        if register:
            from .operators.quick_bake_name import register_quick_bake_name
            register_quick_bake_name()
        else:
            from .operators.quick_bake_name import unregister_quick_bake_name
            unregister_quick_bake_name()
    elif extension == "quick_export":
        if register:
            from .operators.quick_export import register_quick_export
            register_quick_export()
        else:
            from .operators.quick_export import unregister_quick_export
            unregister_quick_export()
    elif extension == "atri_op":
        if register:
            from .operators.atri_op import register_atri_op
            register_atri_op()
        else:
            from .operators.atri_op import unregister_atri_op
            unregister_atri_op()
    elif extension == "material_index":
        if register:
            from .operators.material_index import register_material_index
            register_material_index()
        else:
            from .operators.material_index import unregister_material_index
            unregister_material_index()
    elif extension == "outliner_options":
        if register:
            from .operators.outliner_options import register_outliner_options
            register_outliner_options()
        else:
            from .operators.outliner_options import unregister_outliner_options
            unregister_outliner_options()
    elif extension == "viewport_menu":
        if register:
            from .operators.viewport_menu import register_viewport_menu
            register_viewport_menu()
        else:
            from .operators.viewport_menu import unregister_viewport_menu
            unregister_viewport_menu()

    elif extension == "workspace_pie":
        if register:
            from .menu.pies import register_workspace_pie
            register_workspace_pie()
        else:
            from .menu.pies import unregister_workspace_pie
            unregister_workspace_pie()


def apply_enabled_extensions(prefs, should_register):
    """We loop troguht the prefrences varibles and get the extensions name from the prefrences if 'enable_' in name. 
    Then we call the extension_register_unregister function with the extension name.
    While this is a bit unconventional, this is to avoid a lot of extra repetitive code in the register and unregister functions"""
    
    for pref_name in KeyOpsPreferences.__annotations__:
        if not pref_name.startswith("enable_"): # means its an prefrences that will register/unregister classes/keymaps
            continue

        extension = pref_name.removeprefix("enable_")
        if getattr(prefs, pref_name, False):
            extension_register_unregister(extension, should_register) # register the addon extension if the prefrences is enabled

def register():
    global default_classes

    if debug:
        import time 
        addon_start_time = time.time()

    # Register default classes
    for cls in default_classes:
        bpy.utils.register_class(cls)
    
    from .utils.pref_utils import get_keyops_prefs
    prefs = get_keyops_prefs()

    apply_enabled_extensions(prefs, True)

    if debug:
        print(f"{__package__} addon registered in {time.time() - addon_start_time:.4f} seconds")

def unregister():
    from .operators.toggle_retopology import reset_retopo_themes_on_unregister_addon
    from .utils.pref_utils import unregister_icons
    reset_retopo_themes_on_unregister_addon()

    from .utils.pref_utils import get_keyops_prefs
    prefs = get_keyops_prefs()

    apply_enabled_extensions(prefs, False)

    unregister_icons()

    for cls in default_classes:
        bpy.utils.unregister_class(cls)