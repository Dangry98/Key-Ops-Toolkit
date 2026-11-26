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

import traceback

import bpy

from . import features, pie_menus, properties
from .addon_preferences import KeyOpsPreferences
from .menu import pies
from .operators import (
    add_mesh, add_modifier, atri_op, auto_delete, auto_lod, cad_decimate, curve_tools, double_click_select_island,
    edge_trim, extract_geometry, extrude_edge_along_normals, fast_merge, fast_mirror, fast_solidify,
    flatten, legacy_shortcuts, looptools_menu, material_index, maya_navigation, maya_pivot, mesh_cleanup,
    modi_key, offset_extrude_edge, optional_keys, origin_to_selection, outliner_options,
    parent_used_objects, poly_count_list, quick_bake_name, quick_export, realign_rotation, rebevel, resample_edges, select_similar,
    set_cylinder_sides, set_flow, slide_scale, smart_apply_scale, snap_to_floor, subobject_modes, toggle_retopology, toolkit_panel,
    uv_tools, viewport_menu,
)
from .operators.xray_select import register_xray_select, unregister_xray_select
from .tools import cutter_tool, fast_loop_cut, merge_tool
from .ui import hide_ui, toolkit_paneL_ui, welcome
from .utils.pref_utils import get_keyops_prefs, register_icon_refresh, unregister_icon_refresh, unregister_icons


def register_module(module):
    """Register one module. If it fails, say which one and carry on, so one broken
    feature never takes the rest of the add-on (tools, panels, menus) down with it."""
    try:
        module.register()
    except Exception:
        print(f"Key Ops: could not register {module.__name__}")
        traceback.print_exc()


def unregister_module(module):
    try:
        module.unregister()
    except Exception:
        print(f"Key Ops: could not unregister {module.__name__}")
        traceback.print_exc()


def register():
    properties.register_properties()
    pie_menus.register_properties()
    bpy.utils.register_class(KeyOpsPreferences)
    register_icon_refresh()

    # Toolbar tools
    register_module(merge_tool)
    register_module(fast_loop_cut)
    register_module(cutter_tool)

    # Modeling
    register_module(fast_merge)
    register_module(auto_delete)
    register_module(atri_op)
    register_module(looptools_menu)
    register_module(uv_tools)

    # Object Toolkit (N-panel) and the operators it uses
    register_module(toolkit_panel)
    register_module(extract_geometry)
    register_module(subobject_modes)
    register_module(edge_trim)
    register_module(resample_edges)
    register_module(set_cylinder_sides)
    register_module(rebevel)
    register_module(slide_scale)
    register_module(mesh_cleanup)
    register_module(set_flow)
    register_module(curve_tools)
    register_module(fast_mirror)
    register_module(snap_to_floor)
    register_module(parent_used_objects)
    register_module(extrude_edge_along_normals)
    register_module(offset_extrude_edge)
    register_module(smart_apply_scale)
    register_module(realign_rotation)
    register_module(select_similar)
    register_module(modi_key)
    register_module(material_index)

    # Industry standard
    register_module(maya_navigation)
    register_module(maya_pivot)
    register_module(double_click_select_island)
    register_module(toggle_retopology)

    # Game art
    register_module(quick_export)
    register_module(quick_bake_name)
    register_module(auto_lod)
    register_module(cad_decimate)
    register_module(poly_count_list)

    # Interface
    register_module(viewport_menu)
    register_module(outliner_options)
    register_module(optional_keys)
    register_module(legacy_shortcuts)
    register_xray_select()

    # Pie menus and the operators they call
    register_module(add_mesh)
    register_module(add_modifier)
    register_module(fast_solidify)
    register_module(origin_to_selection)
    register_module(flatten)
    register_module(pies)
    register_module(pie_menus)

    # Panels and the welcome screen
    register_module(toolkit_paneL_ui)
    register_module(welcome)
    register_module(hide_ui)

    # The preferences only exist once the add-on is enabled in Preferences. With Blender's
    # --addons command line flag they don't yet: tools, panels and menus still work, with no shortcuts.
    if get_keyops_prefs() is not None:
        pie_menus.load_from_disk()  # pies are saved in pie_menus.json in the add-on's user folder
        features.migrate()          # new install: no shortcuts until the welcome screen. Upgrade: keep everything
        pie_menus.sync_keymaps()
        welcome.schedule_welcome()
    features.apply_all()            # turn each feature on or off to match its switch in the preferences


def unregister():
    toggle_retopology.reset_retopo_themes_on_unregister_addon()
    features.switch_all_off()

    unregister_module(hide_ui)
    unregister_module(welcome)
    unregister_module(toolkit_paneL_ui)

    unregister_module(pie_menus)
    unregister_module(pies)
    unregister_module(flatten)
    unregister_module(origin_to_selection)
    unregister_module(fast_solidify)
    unregister_module(add_modifier)
    unregister_module(add_mesh)

    unregister_xray_select()
    unregister_module(legacy_shortcuts)
    unregister_module(optional_keys)
    unregister_module(outliner_options)
    unregister_module(viewport_menu)

    unregister_module(poly_count_list)
    unregister_module(cad_decimate)
    unregister_module(auto_lod)
    unregister_module(quick_bake_name)
    unregister_module(quick_export)

    unregister_module(toggle_retopology)
    unregister_module(double_click_select_island)
    unregister_module(maya_pivot)
    unregister_module(maya_navigation)

    unregister_module(material_index)
    unregister_module(modi_key)
    unregister_module(select_similar)
    unregister_module(realign_rotation)
    unregister_module(smart_apply_scale)
    unregister_module(offset_extrude_edge)
    unregister_module(extrude_edge_along_normals)
    unregister_module(parent_used_objects)
    unregister_module(snap_to_floor)
    unregister_module(fast_mirror)
    unregister_module(curve_tools)
    unregister_module(set_flow)
    unregister_module(mesh_cleanup)
    unregister_module(slide_scale)
    unregister_module(rebevel)
    unregister_module(set_cylinder_sides)
    unregister_module(resample_edges)
    unregister_module(edge_trim)
    unregister_module(subobject_modes)
    unregister_module(extract_geometry)
    unregister_module(toolkit_panel)

    unregister_module(uv_tools)
    unregister_module(looptools_menu)
    unregister_module(atri_op)
    unregister_module(auto_delete)
    unregister_module(fast_merge)

    unregister_module(cutter_tool)
    unregister_module(fast_loop_cut)
    unregister_module(merge_tool)

    unregister_icon_refresh()
    unregister_icons()
    bpy.utils.unregister_class(KeyOpsPreferences)
    pie_menus.unregister_properties()
    properties.unregister_properties()
