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

import bpy

from . import features, pie_menus, properties
from .addon_preferences import KeyOpsPreferences
from .menu import pies
from .operators import (
    add_mesh, add_modifier, atri_op, auto_delete, auto_lod, cad_decimate, double_click_select_island,
    edge_trim, extract_geometry, extrude_edge_along_normals, fast_merge, fast_mirror, fast_solidify,
    flatten, legacy_shortcuts, looptools_menu, material_index, maya_navigation, maya_pivot, mesh_cleanup,
    modi_key, offset_extrude_edge, optional_keys, origin_to_selection, outliner_options,
    parent_used_objects, poly_count_list, quick_bake_name, quick_export, resample_edges, select_similar,
    set_flow, smart_apply_scale, snap_to_floor, subobject_modes, toggle_retopology, toolkit_panel,
    uv_tools, viewport_menu,
)
from .operators.xray_select import register_xray_select, unregister_xray_select
from .tools import cutter_tool, fast_loop_cut, merge_tool
from .ui import toolkit_paneL_ui, welcome
from .utils.pref_utils import KeyOpsPrefsMock, get_keyops_prefs, unregister_icons


def register():
    properties.register_properties()
    pie_menus.register_properties()
    bpy.utils.register_class(KeyOpsPreferences)

    # Toolbar tools
    merge_tool.register()
    fast_loop_cut.register()
    cutter_tool.register()

    # Modeling
    fast_merge.register()
    auto_delete.register()
    atri_op.register()
    looptools_menu.register()
    uv_tools.register()

    # Object Toolkit (N-panel) and the operators it uses
    toolkit_panel.register()
    extract_geometry.register()
    subobject_modes.register()
    edge_trim.register()
    resample_edges.register()
    mesh_cleanup.register()
    set_flow.register()
    fast_mirror.register()
    snap_to_floor.register()
    parent_used_objects.register()
    extrude_edge_along_normals.register()
    offset_extrude_edge.register()
    smart_apply_scale.register()
    select_similar.register()
    modi_key.register()
    material_index.register()

    # Industry standard
    maya_navigation.register()
    maya_pivot.register()
    double_click_select_island.register()
    toggle_retopology.register()

    # Game art
    quick_export.register()
    quick_bake_name.register()
    auto_lod.register()
    cad_decimate.register()
    poly_count_list.register()

    # Interface
    viewport_menu.register()
    outliner_options.register()
    optional_keys.register()
    legacy_shortcuts.register()
    register_xray_select()

    # Pie menus and the operators they call
    add_mesh.register()
    add_modifier.register()
    fast_solidify.register()
    origin_to_selection.register()
    flatten.register()
    pies.register()
    pie_menus.register()

    # Panels and the welcome screen
    toolkit_paneL_ui.register()
    welcome.register()

    if prefs_ready():
        finish_register()
    else:
        # Enabled from the command line: the preferences exist once Blender has started
        bpy.app.timers.register(finish_register_when_ready, first_interval=0.1)


def prefs_ready():
    return not isinstance(get_keyops_prefs(), KeyOpsPrefsMock)


def finish_register():
    pie_menus.load_from_disk()     # pies are saved in pie_menus.json in the add-on's user folder
    features.migrate()             # new install: no shortcuts until the welcome screen. Upgrade: keep everything
    features.apply_all()           # turn each feature on or off to match its switch in the preferences
    pie_menus.sync_keymaps()
    welcome.schedule_welcome()


def finish_register_when_ready():
    if not prefs_ready():
        return 0.2  # check again shortly
    finish_register()
    return None


def unregister():
    if bpy.app.timers.is_registered(finish_register_when_ready):
        bpy.app.timers.unregister(finish_register_when_ready)
    toggle_retopology.reset_retopo_themes_on_unregister_addon()
    features.switch_all_off()

    welcome.unregister()
    toolkit_paneL_ui.unregister()

    pie_menus.unregister()
    pies.unregister()
    flatten.unregister()
    origin_to_selection.unregister()
    fast_solidify.unregister()
    add_modifier.unregister()
    add_mesh.unregister()

    unregister_xray_select()
    legacy_shortcuts.unregister()
    optional_keys.unregister()
    outliner_options.unregister()
    viewport_menu.unregister()

    poly_count_list.unregister()
    cad_decimate.unregister()
    auto_lod.unregister()
    quick_bake_name.unregister()
    quick_export.unregister()

    toggle_retopology.unregister()
    double_click_select_island.unregister()
    maya_pivot.unregister()
    maya_navigation.unregister()

    material_index.unregister()
    modi_key.unregister()
    select_similar.unregister()
    smart_apply_scale.unregister()
    offset_extrude_edge.unregister()
    extrude_edge_along_normals.unregister()
    parent_used_objects.unregister()
    snap_to_floor.unregister()
    fast_mirror.unregister()
    set_flow.unregister()
    mesh_cleanup.unregister()
    resample_edges.unregister()
    edge_trim.unregister()
    subobject_modes.unregister()
    extract_geometry.unregister()
    toolkit_panel.unregister()

    uv_tools.unregister()
    looptools_menu.unregister()
    atri_op.unregister()
    auto_delete.unregister()
    fast_merge.unregister()

    cutter_tool.unregister()
    fast_loop_cut.unregister()
    merge_tool.unregister()

    unregister_icons()
    bpy.utils.unregister_class(KeyOpsPreferences)
    pie_menus.unregister_properties()
    properties.unregister_properties()
