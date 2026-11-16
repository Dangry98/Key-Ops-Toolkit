"""Per-feature settings, drawn inside each feature card in the preferences.

Moved out of the old draw_extensions() so every feature's options live in one
place and stay visible while the feature is off.
"""

import bpy


def _maya_navigation(p, col):
    inputs = bpy.context.preferences.inputs
    row = col.row()
    row.prop(p, "maya_navigation_tablet_navigation")
    if bpy.app.version >= (5, 1, 0):
        row.prop(p, "maya_navigation_sculpt_navigation")
    col.label(text="Blender settings that affect Alt navigation:")
    row = col.row()
    row.prop(inputs, "use_zoom_to_mouse", text="Zoom to Mouse")
    row.prop(inputs, "drag_threshold_mouse", text="Drag Mouse")
    row.prop(inputs, "drag_threshold_tablet", text="Drag Tablet")


def _auto_delete(p, col):
    col.prop(p, "auto_delete_dissolv_edge")


def _toggle_retopology(p, col):
    from ..utils.utilities import get_tool_icon_value
    row = col.row(align=True)
    icon_value = get_tool_icon_value(p.toggle_retopology_custom_tool, bpy.context)
    if icon_value:
        row.label(text="", icon_value=icon_value)
    else:
        row.label(text="", icon='TOOL_SETTINGS')
    row.prop(p, "toggle_retopology_custom_tool", text="Tool")
    row.operator("keyops.search_retopology_tool", text="", icon="VIEWZOOM")
    col.prop(p, "toggle_retopology_color_enum")
    row = col.row(align=True)
    if p.toggle_retopology_color_enum == "custom_color":
        row.prop(p, "toggle_retopology_custom_color")
        row.prop(p, "toggle_retopology_face_alpha")
    row.prop(p, "toggle_retopology_edge_width", text="Edge Width")
    row = col.row(align=True)
    row.label(text="Snapping")
    row.prop(p, "toggle_retopology_snapping_settings_vert", icon="SNAP_VERTEX", text="")
    row.prop(p, "toggle_retopology_snapping_settings_face", icon="SNAP_FACE", text="")
    row.prop(p, "toggle_retopology_snapping_settings_face_project", icon="SNAP_FACE", text="")
    row.prop(p, "toggle_retopology_snapping_settings_face_nearest", icon="MOD_SHRINKWRAP", text="")


def _maya_pivot(p, col):
    row = col.row()
    row.prop(p, "maya_pivot_behavior")
    row.prop(p, "maya_pivot_show_gizmo")
    if p.experimental:
        row = col.row()
        row.prop(p, "maya_pivot_experimental")
        if p.maya_pivot_experimental:
            row.prop(p, "maya_pivot_in_edit_mode")


def _fast_merge(p, col):
    col.prop(p, "fast_merge_merge_options")
    row = col.row()
    row.prop(p, "fast_merge_soft_limit")
    if p.fast_merge_soft_limit in {"max_polycount", "max_limit_&_all_selected"}:
        row.prop(p, "fast_merge_polycount")


def _add_objects_pie(p, col):
    row = col.row()
    row.prop(p, "add_object_pie_use_relative")
    sub = row.row()
    sub.active = p.add_object_pie_use_relative
    sub.prop(p, "add_object_pie_relative_scale")
    row = col.row()
    row.prop(p, "add_object_pie_min_scale")
    row.prop(p, "add_object_pie_default_scale")
    col.prop(p, "add_object_pie_Enum")
    if p.add_object_pie_Enum == "BLEND":
        col.prop(p, "add_object_pie_blend_file_path", text="File")
        col.prop(p, "add_object_pie_blend_object_name", text="Objects")


def _legacy_shortcuts(p, col):
    row = col.row()
    row.enabled = bpy.app.version >= (5, 0, 0)
    row.prop(p, "enable_legacy_collection_shortcuts", text="Collection hide/show on number keys (Blender 5.0+)")


def _material_index(p, col):
    row = col.row()
    row.prop(p, "material_list_type", text="List")
    if p.material_list_type == "PREVIEW_ICONS":
        row.prop(p, "material_list_icon_scale", text="Scale")
    else:
        row.prop(p, "material_list_show_icons")


SETTINGS = {
    "maya_navigation": _maya_navigation,
    "auto_delete": _auto_delete,
    "toggle_retopology": _toggle_retopology,
    "maya_pivot": _maya_pivot,
    "fast_merge": _fast_merge,
    "add_objects_pie": _add_objects_pie,
    "legacy_shortcuts": _legacy_shortcuts,
    "material_index": _material_index,
}


def draw_settings(feature_id, prefs, layout):
    fn = SETTINGS.get(feature_id)
    if fn is None:
        return False
    fn(prefs, layout)
    return True
