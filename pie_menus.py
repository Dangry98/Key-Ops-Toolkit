"""User-editable pie menus.

Every Key Ops pie is now a preset stored in the add-on preferences: users can
change any slot, change its key, and add pies of their own. One operator
(wm.keyops_call_pie) opens any of them, and each enabled pie gets one Key Ops
keymap item in keyconfigs.addon. The user's keymap is never edited.
"""

import ast
import json
import re
import time
import uuid

import re
import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator, PropertyGroup

from .utils.pref_utils import get_keyops_prefs, get_icon, icons_directory
from .ui import menu_canvas

# Blender's pie order: the 8 slots are filled in this sequence
ORDER = ("W", "E", "S", "N", "NW", "NE", "SW", "SE")
POSITION_NAMES = {"W": "Left", "E": "Right", "S": "Bottom", "N": "Top",
                  "NW": "Top Left", "NE": "Top Right", "SW": "Bottom Left", "SE": "Bottom Right"}
GRID = ("NW", "N", "NE", "W", None, "E", "SW", "S", "SE")

EDITORS = (
    ("3D View Generic", "3D Viewport", "Any mode in the 3D Viewport", 'VIEW3D'),
    ("Object Mode", "Object Mode", "Only in Object Mode", 'OBJECT_DATAMODE'),
    ("Mesh", "Edit Mesh", "Only in mesh Edit Mode", 'EDITMODE_HLT'),
    ("Sculpt", "Sculpt Mode", "Only in Sculpt Mode", 'SCULPTMODE_HLT'),
    ("Weight Paint", "Weight Paint", "Only in Weight Paint Mode", 'WPAINT_HLT'),
    ("UV Editor", "UV Editor", "Only in the UV Editor", 'UV'),
    ("Image", "Image Editor", "In the Image Editor", 'IMAGE'),
    ("Node Editor", "Node Editors", "Shader, Geometry and other node editors", 'NODETREE'),
    ("Graph Editor", "Graph Editor", "In the Graph Editor", 'GRAPH'),
    ("Dopesheet", "Dope Sheet", "In the Dope Sheet", 'ACTION'),
    ("Outliner", "Outliner", "In the Outliner", 'OUTLINER'),
    ("Property Editor", "Properties", "In the Properties editor", 'PROPERTIES'),
    ("Sequencer", "Video Sequencer", "In the Video Sequencer", 'SEQUENCE'),
    ("Text", "Text Editor", "In the Text Editor", 'TEXT'),
    ("Window", "Everywhere", "In every editor", 'WINDOW'),
    ("Curve", "Edit Curve", "Only in curve Edit Mode", 'CURVE_DATA'),
)

MENU_TYPES = (
    ("PIE", "Pie Menu", "Up to 8 actions around the mouse", 'keyops:menu_pie', 0),
    ("MENU", "Popup Menu", "A list of actions under the mouse, as long as you like", 'COLLAPSEMENU', 1),
    ("DIALOG", "Dialog", "Buttons and settings in a small window, in columns", 'WINDOW', 2),
    ("PANEL", "Sidebar Panel", "Your buttons and settings as a panel in the editor's sidebar (N)", 'MENU_PANEL', 3),
    ("STACK", "Stack Key", "Each press runs the next item, then starts over", 'keyops:menu_stack', 4),
    ("STICKY", "Sticky Key", "One action while the key is held, another when it's released", 'keyops:menu_sticky', 5),
    ("MODAL", "Modal Value", "Move the mouse or scroll to change a setting, click to confirm", 'keyops:menu_modal', 6),
    ("MACRO_OP", "Macro Operator", "A shortcut that runs several actions one after another", 'keyops:menu_macro', 7),
)
TYPE_ICON = {t[0]: t[3] for t in MENU_TYPES}  # "keyops:<name>" is Key Ops' own icon: draw it with icon_kw()
_menu_type_items_cache = []


def _menu_type_items(_self=None, _context=None):
    """MENU_TYPES with Key Ops' own icons as icon ids, which enum items need (a callback, so the icons load late)."""
    if not _menu_type_items_cache:
        _menu_type_items_cache.extend((t, n, d, enum_icon(i), x) for t, n, d, i, x in MENU_TYPES)
    return _menu_type_items_cache
ITEM_LIMIT = {"PIE": 24, "STICKY": 2, "MODAL": 1}  # others: up to LIST_LIMIT. Pies: 8 directions + 16 extra items
LIST_LIMIT = 1024  # popup menus, dialogs and panels: room to rebuild a whole add-on panel
PIE_SLOTS = 8  # a pie's first 8 items are its directions; the rest are extra items (a list, like Maya's)
ITEM_MIN = {"PIE": 8, "STICKY": 2, "MODAL": 1, "MACRO_OP": 1}
RUN_TYPES = {"MACRO_OP"}  # a key that runs its items instead of opening a menu

ONLY_MODES = (
    ("ANY", "Any Mode", "Works in every mode of that editor"),
    ("OBJECT", "Object Mode", ""), ("EDIT_MESH", "Edit Mesh", ""), ("EDIT_CURVE", "Edit Curve", ""),
    ("SCULPT", "Sculpt", ""), ("PAINT_WEIGHT", "Weight Paint", ""), ("PAINT_VERTEX", "Vertex Paint", ""),
    ("PAINT_TEXTURE", "Texture Paint", ""), ("POSE", "Pose", ""), ("EDIT_ARMATURE", "Edit Armature", ""),
)
_MODE_IDS = [m[0] for m in ONLY_MODES[1:]]
_MODE_LABELS = {m[0]: m[1] for m in ONLY_MODES}
_MODE_ICONS = {"ANY": 'WORLD', "OBJECT": 'OBJECT_DATAMODE', "EDIT_MESH": 'EDITMODE_HLT', "EDIT_CURVE": 'EDITMODE_HLT',
               "SCULPT": 'SCULPTMODE_HLT', "PAINT_WEIGHT": 'WPAINT_HLT', "PAINT_VERTEX": 'VPAINT_HLT',
               "PAINT_TEXTURE": 'TPAINT_HLT', "POSE": 'POSE_HLT', "EDIT_ARMATURE": 'EDITMODE_HLT'}


def only_modes(pie):
    """The modes a menu opens in (only_mode is a comma list, e.g. "OBJECT, EDIT_MESH"). Empty: any mode."""
    names = [n.strip() for n in (pie.only_mode or "").split(",")]
    if "ANY" in names:
        return set()
    return {n for n in names if n in _MODE_LABELS}


def mode_ok(context, pie):
    modes = only_modes(pie)
    return not modes or context.mode in modes


def _summary(labels, plural, empty):
    """The text of a pick-several dropdown: the one picked, else how many, so every dropdown reads the same."""
    if not labels:
        return empty
    return labels[0] if len(labels) == 1 else f"{len(labels)} {plural}"


def only_mode_text(pie):
    return _summary([_MODE_LABELS[m] for m in _MODE_IDS if m in only_modes(pie)], "Modes", "Any Mode")


def only_mode_icon(pie):
    modes = [m for m in _MODE_IDS if m in only_modes(pie)]
    return _MODE_ICONS[modes[0]] if len(modes) == 1 else ('WORLD' if not modes else 'OBJECT_DATAMODE')


def _mode_bits_get(self):
    modes = only_modes(self)
    return sum(1 << i for i, m in enumerate(_MODE_IDS) if m in modes)


def _mode_bits_set(self, bits):
    modes = [m for i, m in enumerate(_MODE_IDS) if bits & (1 << i)]
    self.only_mode = ", ".join(modes) if modes else "ANY"
KEY_EVENTS = (
    ("PRESS", "Press", "Opens as soon as the key goes down"),
    ("CLICK", "Click", "Opens on a quick press and release, so holding the key can do something else"),
    ("DOUBLE_CLICK", "Double Click", "Opens on a double press"),
    ("CLICK_DRAG", "Press and Drag", "Opens when you press the key and move the mouse"),
    ("HOLD", "Hold", "Opens when you hold the key (marking menus open at once). A quick tap does what the key normally does in Blender"),
)
HOLD_TIME = 0.3  # seconds a key must be held for a Hold menu to open

O, M, P, N, MACRO, SUB = "OPERATOR", "MENU", "PROPERTY", "NONE", "MACRO", "SUBMENU"
# How an operator item is called. Popup menus invoke by default (as Blender's own menus
# do): Blender's popup menus would otherwise execute, which skips invoke, so modal tools never start.
CALL_MODES = (
    ("DEFAULT", "As the Menu Does", "Pies and popup menus invoke the operator in the editor under the mouse, "
                                    "like a key press"),
    ("INVOKE_REGION_WIN", "Invoke", "Like a key press in the editor under the mouse: tools that follow the mouse "
                                    "and operators that ask first work"),
    ("INVOKE_DEFAULT", "Invoke (Here)", "Like a key press, where the button is"),
    ("EXEC_REGION_WIN", "Execute", "Run straight away with its options, no popup or mouse following, "
                                   "in the editor under the mouse"),
    ("EXEC_DEFAULT", "Execute (Here)", "Run straight away with its options, where the button is"),
)
SCRIPT, PANEL_ITEM, LABEL = "SCRIPT", "POPOVER", "LABEL"
DRAW = "DRAW"  # Python that draws into the layout itself, for what items can't build (lists, templates, loops)
DRAW_DEFAULT = "# layout, context (C), bpy and D are ready to use\nlayout.label(text=\"Hello\")\n"
BREAK = "BREAK"  # dialogs and panels: start the next column
BOX, BOX_END = "BOX", "BOX_END"  # popup menus, dialogs and panels: a framed group of items
LAYOUT_KINDS = (BREAK, BOX, BOX_END)  # items that shape the layout instead of being buttons
GROUP_TYPES = (
    ("BOX", "Box", "A framed box, its label as the heading", 'MESH_PLANE', 0),
    ("ROW", "Row", "Items side by side", 'SNAP_EDGE', 1),
    ("COLUMN", "Column", "Items one under the other", 'ALIGN_JUSTIFY', 2),
    ("SPLIT", "Split", "Items in columns: Split sets the first one's width", 'SPLIT_HORIZONTAL', 3),
    ("GRID", "Grid Flow", "Items in a grid, row by row", 'MESH_GRID', 4),
    ("PANEL", "Panel", "A panel that opens and closes, its label as the header (a box in Blender before 4.1)",
     'DOWNARROW_HLT', 5),
)
GROUP_NAMES = {g[0]: g[1] for g in GROUP_TYPES}
SETTING_STYLES = (
    ("AUTO", "Automatic", "A button in pies, a checkbox or field in menus, dialogs and panels"),
    ("BUTTON", "Button", "A toggle button that lights up when it's on"),
    ("CHECKBOX", "Checkbox", "A checkbox with the name beside it"),
    ("EXPAND", "Expanded", "For choices: every option as its own button in a row"),
    ("SLIDER", "Slider", "For numbers: a slider"),
    # added later: kept after the first five so menus saved before still load the same
    ("MENU", "Dropdown", "For choices: a dropdown button showing the current option (prop_menu_enum)"),
    ("SEARCH", "Search", "For an object, material, vertex group or other item: a field that searches the list "
                         "set in Search In, like Blender's material and vertex group pickers (prop_search)"),
    ("TABS", "Tabs", "For choices: every option as a tab (prop_tabs_enum)"),
    ("VALUE", "One Option", "For choices: one button that sets the option named in Option, lit while it's set "
                            "(prop_enum)"),
    ("LIST", "List", "For a collection (material slots, UV maps, vertex groups): a scrolling list like "
                     "Blender's own (template_list). Active Index names the setting that holds the selected row"),
    ("ID", "Data-Block", "For a material, world, image, action...: Blender's data-block selector with its "
                         "name field and New button (template_ID)"),
    ("ICONS", "Icon Picker", "For choices with previews: a big icon picker (template_icon_view)"),
    ("COLOR", "Color Wheel", "For a color: the color wheel (template_color_picker)"),
    ("RAMP", "Color Ramp", "For a color ramp: Blender's ramp editor (template_color_ramp)"),
    ("CURVE", "Curve", "For a curve mapping (falloff, RGB curves): Blender's curve editor (template_curve_mapping)"),
    ("PALETTE", "Palette", "For a palette: its swatches (template_palette)"),
    ("POPOVER", "With Popover", "The setting with a dropdown arrow that opens one of Blender's panels, like the "
                                "snapping and proportional editing buttons in the 3D View header (prop_with_popover)"),
)
TEMPLATE_STYLES = {"SEARCH", "LIST", "ID", "COLOR", "RAMP", "CURVE", "PALETTE"}  # Blender templates, not buttons
PANEL_ONLY_STYLES = TEMPLATE_STYLES - {"SEARCH"}  # too big for a popup menu row: such a menu opens as a panel
# Styles that need a second setting path (Search In / Active Index / Option / New operator)
SETTING_SOURCE = {"SEARCH": ("Search In", "Where to search, e.g. bpy.data.materials or object.vertex_groups"),
                  "LIST": ("Active Index", "The setting that holds the selected row, e.g. object.active_material_index"),
                  "VALUE": ("Option", "The option this button sets, e.g. MEDIAN_POINT"),
                  "ID": ("New", "Optional: the operator its New button runs, e.g. material.new"),
                  "POPOVER": ("Panel", "The panel the arrow opens, e.g. VIEW3D_PT_snapping")}
MENU_STYLES = (
    ("AUTO", "Automatic", "A submenu that opens on hover in popup menus (like Blender's own), a button elsewhere"),
    ("BUTTON", "Button", "A button that opens the menu on its own (wm.call_menu)"),
    ("SUBMENU", "Dropdown", "A dropdown button with an arrow that opens the menu below it (layout.menu)"),
    ("INLINE", "Inline", "The menu's own items, drawn right here as if they were part of this menu "
                         "(menu_contents, Blender 4.1+)"),
)
SUB_STYLES = (
    ("OPEN", "Button", "A button that opens the menu"),
    ("INLINE", "Group", "The menu's items drawn right here as a group: a box, column or row of buttons. In a pie "
                        "this puts several buttons in one direction, like many add-on pies do"),
)
OP_STYLES = (
    ("BUTTON", "Button", "One button that runs the operator"),
    ("MENU", "Dropdown", "A dropdown listing every value of one of the operator's choice options "
                         "(operator_menu_enum), like Add Modifier or Snap Cursor To"),
    ("EXPAND", "Buttons", "One button per value of one of the operator's choice options (operator_enum)"),
)
_ = (N, "", "", "", "")


def _orient(label, icon, value):
    """A preset item that sets the transform orientation."""
    return (O, label, icon, "wm.context_set_enum",
            f"data_path='scene.transform_orientation_slots[0].type', value='{value}'")


def _pivot(label, icon, value):
    """A preset item that sets the pivot point."""
    return (O, label, icon, "wm.context_set_enum", f"data_path='tool_settings.transform_pivot_point', value='{value}'")


def _op(label, icon, idname, props=""):
    return (O, label, icon, idname, props)


def _q_sections():
    """The Q Menu's items by section, {key: [(kind, label, icon, idname, props, show_if), ...]}, and when
    each section has something to show. Each item's Show If test picks it for the mode and selection."""
    obj_mesh = "mode == 'OBJECT' and obj and obj.type == 'MESH'"
    booleans = obj_mesh + " and sel > 1"
    has_bool = "mode == 'OBJECT' and 'BOOLEAN' in mods"
    mesh = "obj and obj.type == 'MESH' and mode in ('OBJECT', 'EDIT_MESH')"
    edit = "mode == 'EDIT_MESH'"
    obj_mode = "mode == 'OBJECT'"
    has_obj = "mode == 'OBJECT' and obj"
    # curves: Object Mode with a curve active, curve Edit Mode, or edges selected in mesh Edit Mode
    curve_obj = "mode == 'OBJECT' and obj and obj.type == 'CURVE'"
    curve_edit = "mode == 'EDIT_CURVE'"
    edge_sel = "mode == 'EDIT_MESH' and tool.mesh_select_mode[1]"
    bool_op = "object.add_boolean_modifier_operator"
    # as the N panel: Blender 4.2 has no mouse wheel icon
    scroll_icon = "EVENT_CAPSLOCK" if bpy.app.version < (4, 3, 0) else "MOUSE_MMB_SCROLL"

    def op(test, label, icon, idname, props=""):
        return (O, label, icon, idname, props, test)

    def setting(test, label, icon, path):
        # drawn the way Blender draws it: expanded rows don't fit in popup menus (the labels overlap)
        return (P, label, icon, path, "", test)

    def value(test, label, icon, path, option):
        # one button per choice, right in the menu (no submenu): it sets the setting to that option
        return (P, label, icon, path, option, test, "VALUE")

    items = {
        "boolean": [
            op(booleans, "Difference", "keyops:difference", bool_op, "type='DIFFERENCE'"),
            op(booleans, "Union", "keyops:union", bool_op, "type='UNION'"),
            op(booleans, "Intersect", "keyops:intersect", bool_op, "type='INTERSECT'"),
            op(booleans, "Slice", "keyops:slice", bool_op, "type='SLICE'"),
            op(has_bool, "Boolean Scroll", scroll_icon, "object.boolean_scroll"),
            op(edit, "Boolean Cut Selected", "keyops:difference", "mesh.intersect_boolean", "operation='DIFFERENCE'"),
            op(edit, "Boolean Union Selected", "keyops:union", "mesh.intersect_boolean", "operation='UNION'"),
        ],
        "mesh": [
            op(edit, "Extract Geometry", "DUPLICATE", "keyops.extract_geometry"),
            op(edit, "Merge", "AUTOMERGE_OFF", "keyops.fast_merge"),
            op(edit, "Set Flow", "MOD_SMOOTH", "mesh.set_mesh_edge_flow"),
            op(edit, "Slide Scale", "FULLSCREEN_EXIT", "keyops.slide_scale"),
            op(edit, "Resample Edges", "CURVE_PATH", "keyops.resample_edges"),
            op(edit, "Make Edge Trim", "MOD_EDGESPLIT", "keyops.edge_trim"),
            op(edit, "Mark Sharp", "SHARPCURVE", "mesh.mark_sharp"),
            op(edit, "Clear Sharp", "SMOOTHCURVE", "mesh.mark_sharp", "clear=True"),
            op(edit, "Mark Seam", "UV_EDGESEL", "mesh.mark_seam"),
        ],
        "modifiers": [
            op(mesh, "Mirror", "MOD_MIRROR", "keyops.fast_mirror"),
            op(mesh, "Bevel", "MOD_BEVEL", "keyops.fast_bevel"),
            op(mesh, "Array", "MOD_ARRAY", "keyops.fast_array"),
            op(mesh, "Solidify", "MOD_SOLIDIFY", "keyops.fast_solidify"),
            op(mesh, "Weighted Normal", "MOD_NORMALEDIT", "keyops.add_modifier", "type='WEIGHTED_NORMAL'"),
            op(mesh, "Triangulate", "MOD_TRIANGULATE", "keyops.add_modifier", "type='TRIANGULATE'"),
            op("mode == 'OBJECT' and len(mods) > 0", "Apply All Modifiers", "keyops:mesh", "object.convert", "target='MESH'"),
        ],
        "object": [
            op(obj_mode, "Smart Apply Scale", "FREEZE", "object.smart_apply_scale"),
            op(obj_mesh, "Re-Align Rotation", "ORIENTATION_LOCAL", "keyops.realign_rotation"),
            op(obj_mode, "Snap to Floor", "VIEW_PERSPECTIVE", "keyops.snap_to_floor"),
            op(obj_mode, "Origin to Selection", "LAYER_USED", "keyops.origin_to_selection", "type='origin_to_geometry'"),
            op(obj_mesh, "Clean Up", "BRUSH_DATA", "keyops.mesh_cleanup"),
        ],
        "display": [
            setting(has_obj, "Wireframe", "SHADING_WIRE", "object.show_wire"),
            setting(has_obj, "In Front", "XRAY", "object.show_in_front"),
            value(has_obj, "Bounds", "SHADING_BBOX", "object.display_type", "BOUNDS"),
            value(has_obj, "Wire", "SHADING_WIRE", "object.display_type", "WIRE"),
            value(has_obj, "Solid", "SHADING_SOLID", "object.display_type", "SOLID"),
            value(has_obj, "Textured", "SHADING_TEXTURE", "object.display_type", "TEXTURED"),
        ],
        "curve": [
            op(f"({curve_obj}) or ({curve_edit})", "Radius", "PROP_ON", "keyops.curve_radius"),
            op(curve_obj, "Convert to Mesh", "keyops:mesh", "object.convert", "target='MESH'"),
            op(edge_sel, "Edges to Curve", "CURVE_DATA", "keyops.edges_to_curve"),
        ],
    }
    shows = {"boolean": f"({booleans}) or ({has_bool}) or ({edit})", "mesh": edit, "modifiers": mesh,
             "object": obj_mode, "display": has_obj,
             "curve": f"({curve_obj}) or ({curve_edit}) or ({edge_sel})",
             # one mesh selected in Object Mode: the modifier modals go to the top, booleans need two
             "single": obj_mesh + " and sel <= 1"}
    return items, shows


# The Q Menu's sections: (key, title, icon). The one-column Q Menu shows the boolean actions that fit,
# then opens each other section as a submenu (preset "q_<key>"); Q Menu (Columns) shows them side by side.
Q_SECTIONS = (("boolean", "Boolean", "keyops:difference"), ("mesh", "Mesh", "keyops:editmode"),
              ("modifiers", "Modifiers", "keyops:modifier"),
              ("object", "Object", "keyops:mesh_cube"), ("display", "Display", "HIDE_OFF"))
# the curve items have no section of their own (one or two at a time): they sit at the top when they apply


def _q_menu_items():
    """One column: what fits right now at the top (booleans for several meshes, the modifier modals for
    one), then a submenu for each section."""
    items, shows = _q_sections()
    # what fits right now first: Edges to Curve with edges selected, Radius on a curve
    out = list(items["curve"])
    out += list(items["boolean"])
    # Fast Mirror, Bevel, Array and Solidify, right at the top while one mesh is selected
    out += [it[:5] + (shows["single"],) for it in items["modifiers"][:4]]
    # a separator, only when there's something above it
    out.append((N, "", "", "", "", f"({shows['curve']}) or ({shows['boolean']}) or ({shows['single']})"))
    for key, title, icon in Q_SECTIONS[1:]:
        out.append((SUB, title, icon, f"preset:q_{key}", "", shows[key]))
    return tuple(out)


def _q_columns_items():
    """Q Menu (Columns): the sections side by side, each under its heading."""
    items, shows = _q_sections()
    out = list(items["curve"])  # at the top, when they apply
    for key, title, icon in Q_SECTIONS:
        if key in ("modifiers", "object"):  # Mesh goes under Boolean, Display under Object
            out.append((BREAK, "", "", "", "", shows[key]))
        out.append((LABEL, title, icon, "", "", shows[key]))
        out.extend(items[key])
    return tuple(out)


def _q_submenu_presets():
    """The one-column Q Menu's submenus: hidden presets, added with the Q Menu."""
    items, _shows = _q_sections()
    return tuple(dict(id=f"q_{key}", name=f"Q Menu: {title}", editor="Object Mode, Mesh, Curve", key="NONE",
                      menu_type="MENU", optional=True, sub=True, styles=set(), items=tuple(items[key]))
                 for key, title, _icon in Q_SECTIONS[1:])


PRESETS = (
    dict(id="add_objects", name="Add Objects", editor="3D View Generic", key="A", shift=True, alt=True,
         styles={"BLENDER_PLUS", "INDUSTRY"}, items=(
             _op("UV Sphere", "SHADING_WIRE", "keyops.add_mesh", "mesh_type='UVSPHERE'"),
             _op("Cube", "MESH_CUBE", "keyops.add_mesh", "mesh_type='CUBE'"),
             # Blender's own cylinder: its Adjust Last Operation panel (vertices, cap fill, align...) shows;
             # Mod Cylinder is the Screw-modifier one
             _op("Cylinder", "MESH_CYLINDER", "mesh.primitive_cylinder_add"),
             _op("Plane", "MESH_PLANE", "keyops.add_mesh", "mesh_type='PLANE'"),
             _op("Mod Cylinder", "MOD_SCREW", "keyops.add_mesh", "mesh_type='MODCYLINDER'"),
             (M, "Other", "ADD", "VIEW3D_MT_add", ""),
             _op("Quad Sphere", "MESH_UVSPHERE", "keyops.add_mesh", "mesh_type='QUADSPHERE'"),
             _op("Circle", "MESH_CIRCLE", "keyops.add_mesh", "mesh_type='CIRCLE'"))),
    dict(id="add_modifier", name="Add Modifier", editor="3D View Generic", key="Q", shift=True,
         styles={"BLENDER_PLUS", "INDUSTRY"}, items=(
             _op("Array", "MOD_ARRAY", "keyops.fast_array"),
             _op("Solidify", "MOD_SOLIDIFY", "keyops.fast_solidify"),
             _op("Bevel", "MOD_BEVEL", "keyops.fast_bevel"),
             _op("Weighted Normal", "MOD_NORMALEDIT", "keyops.add_modifier", "type='WEIGHTED_NORMAL'"),
             _op("Lattice", "MOD_LATTICE", "keyops.add_modifier", "type='LATTICE'"),
             _op("Weld", "AUTOMERGE_OFF", "keyops.add_modifier", "type='WELD'"),
             _op("Triangulate", "MOD_TRIANGULATE", "keyops.add_modifier", "type='TRIANGULATE'"),
             _op("Shrinkwrap", "MOD_SHRINKWRAP", "keyops.add_modifier", "type='SHRINKWRAP'"))),
    dict(id="flatten", name="Flatten", editor="Mesh, UV Editor", key="THREE", alt=True,
         styles={"BLENDER_PLUS", "INDUSTRY"}, items=(
             _op("Left", "TRIA_LEFT", "keyops.flatten", "direction='LEFT'"),
             _op("Right", "TRIA_RIGHT", "keyops.flatten", "direction='RIGHT'"),
             _op("Bottom", "TRIA_DOWN", "keyops.flatten", "direction='BOTTOM'"),
             _op("Top", "TRIA_UP", "keyops.flatten", "direction='TOP'"), _, _, _, _)),
    dict(id="cursor", name="Cursor & Origin", editor="3D View Generic", key="S", shift=True,
         styles={"INDUSTRY"}, items=(
             _op("Origin to 3D Cursor", "LAYER_USED", "keyops.origin_to_selection", "type='origin_to_3d_cursor'"),
             _op("Origin to Selection", "LAYER_USED", "keyops.origin_to_selection", "type='origin_to_geometry'"),
             _op("Cursor to Selection", "CURSOR", "view3d.snap_cursor_to_selected"),
             _op("Selection to Cursor", "RESTRICT_SELECT_OFF", "view3d.snap_selected_to_cursor"),
             _op("Selection to Grid", "SNAP_GRID", "view3d.snap_selected_to_grid"),
             _op("Cursor to Grid", "SNAP_GRID", "view3d.snap_cursor_to_grid"),
             _op("Cursor to World Origin", "PIVOT_CURSOR", "view3d.snap_cursor_to_center"),
             _op("Cursor to Active", "CURSOR", "view3d.snap_cursor_to_active"))),
    # Blender's own View pie (VIEW3D_MT_view_pie), slot for slot, on Space like Key Ops 0.2's option
    dict(id="view", name="View", editor="3D View Generic", key="SPACE", styles=set(), items=(
        _op("Left", "TRIA_LEFT", "view3d.view_axis", "type='LEFT'"),
        _op("Right", "TRIA_RIGHT", "view3d.view_axis", "type='RIGHT'"),
        _op("Bottom", "TRIA_DOWN", "view3d.view_axis", "type='BOTTOM'"),
        _op("Top", "TRIA_UP", "view3d.view_axis", "type='TOP'"),
        _op("Front", "", "view3d.view_axis", "type='FRONT'"),
        _op("Back", "", "view3d.view_axis", "type='BACK'"),
        _op("View Camera", "CAMERA_DATA", "view3d.view_camera"),
        _op("View Selected", "ZOOM_SELECTED", "view3d.view_selected"))),
    dict(id="workspace", name="Workspaces", editor="Window", key="BACK_SLASH", shift=True, styles=set(), items=tuple(
        _op(label, icon, "keyops.switch_workspace", f"workspace_name='{ws}'") for label, icon, ws in (
            ("Layout", "GRID", "Layout"), ("Modeling", "EDITMODE_HLT", "Modeling"), ("Shading", "MATERIAL", "Shading"),
            ("UV Editor", "UV", "UV Editing"), ("Scripting", "SCRIPT", "Scripting"),
            ("Texture Paint", "BRUSHES_ALL", "Texture Paint"), ("Geometry Nodes", "GEOMETRY_NODES", "Geometry Nodes"),
            ("Sculpting", "SCULPTMODE_HLT", "Sculpting")))),
    dict(id="utility", name="Utility", editor="Object Mode, Mesh", key="U", styles=set(), items=(
        (P, "Live Unwrap", "", "scene.tool_settings.use_edge_path_live_unwrap", ""),
        (M, "UV Mapping Menu", "", "VIEW3D_MT_uv_map", ""),
        _op("Seam by Angle", "MOD_EDGESPLIT", "keyops.seam_by_angle"),
        _op("Unfold and Pack", "UV_FACESEL", "uv.unwrap"),
        (P, "Correct Face Attributes", "", "scene.tool_settings.use_transform_correct_face_attributes", ""),
        _op("Make Single User", "", "keyops.make_single_user"),
        (P, "Auto Merge", "", "scene.tool_settings.use_mesh_automerge", ""), _)),
    dict(id="uv_space", name="UV Unwrap", editor="UV Editor", key="SPACE", styles=set(), items=(
        _op("Straighten Quads", "UV_ISLANDSEL", "keyops.streighten_selection"),
        _op("Isolate Island (Toggle)", "", "keyops.isolate_uv_island"),
        _op("Quick Pack", "CON_SAMEVOL", "uv.keyops_quick_pack"),
        _op("Unwrap in Place", "STICKY_UVS_VERT", "uv.keyops_unwrap_in_place"),
        _op("Unwrap and Pack", "UV_FACESEL", "uv.unwrap"),
        _op("Unwrap Selected", "UV_VERTEXSEL", "keyops.unwrap_selected"),
        _op("Straighten after Edge", "UV_EDGESEL", "keyops.streighten_after_edge"),
        _op("View Selected", "ZOOM_SELECTED", "image.view_selected"))),
    dict(id="uv_islands", name="UV Islands", editor="UV Editor", key="Q", styles=set(), items=(
        _op("Select Overlapping", "", "uv.select_overlap"),
        _op("Orient Island to Edge", "", "keyops.orient_island_to_edge"),
        _op("Stack Similar Islands", "CON_SIZELIKE", "keyops.stack_similar_islands"),
        _op("Sharp Edges from UV Islands", "MOD_EDGESPLIT", "keyops.sharp_from_uv_islands"),
        _op("Seams from Islands", "", "uv.seams_from_islands"),
        _op("Mirror Selected Seams", "MOD_MIRROR", "keyops.mirror_seams"),
        _op("Select Similar Islands", "", "keyops.select_similar_islands"), _)),
    # One popup menu whose items change with the mode and the selection: booleans when
    # two or more meshes are selected, then submenus for the modifiers, the active modifier, mesh and
    # object tools. Each item's Show If does the picking. Q Menu (Columns) shows it all side by side. In the list on new installs, switched off,
    # since it takes Blender's Quick Favorites key.
    dict(id="q_menu", name="Q Menu", editor="Object Mode, Mesh, Curve", key="Q", menu_type="MENU",
         styles=set(), items=_q_menu_items()),
    dict(id="q_menu_columns", name="Q Menu (Columns)", editor="Object Mode, Mesh, Curve", key="Q", menu_type="MENU",
         optional=True, styles=set(), items=_q_columns_items()),
    *_q_submenu_presets(),
) + (
    # ---- Marking menus: optional presets (Add Preset only), opened by holding a right mouse button combo.
    # Hold opens the menu; a quick click still does what Blender does with that click.
    # Slot order: left, right, bottom, top, top left, top right, bottom left, bottom right.
    dict(id="marking_select", name="Selection Modes", editor="Object Mode, Mesh", key="RIGHTMOUSE", key_event="HOLD",
         optional=True, styles=set(), items=(
             _op("Vertex", "VERTEXSEL", "keyops.component_mode", "mode='VERT'"),
             _op("Face", "FACESEL", "keyops.component_mode", "mode='FACE'"),
             _op("Object Mode", "OBJECT_DATAMODE", "keyops.component_mode", "mode='OBJECT'"),
             _op("Edge", "EDGESEL", "keyops.component_mode", "mode='EDGE'"),
             _,
             _op("UV Editing", "UV", "keyops.switch_workspace", "workspace_name='UV Editing'"),
             _,
             _op("All Modes", "SELECT_SET", "keyops.component_mode", "mode='MULTI'"))),
    # Shift + right-click in Object Mode: add primitives
    dict(id="marking_create", name="Add Primitives", editor="Object Mode", key="RIGHTMOUSE", shift=True, key_event="HOLD",
         optional=True, styles=set(), items=(
             _op("Sphere", "MESH_UVSPHERE", "mesh.primitive_uv_sphere_add"),
             _op("Cube", "MESH_CUBE", "mesh.primitive_cube_add"),
             _op("Plane", "MESH_PLANE", "mesh.primitive_plane_add"),
             _op("Cylinder", "MESH_CYLINDER", "mesh.primitive_cylinder_add"),
             _op("Cone", "MESH_CONE", "mesh.primitive_cone_add"),
             _op("Torus", "MESH_TORUS", "mesh.primitive_torus_add"),
             _op("Disc", "MESH_CIRCLE", "mesh.primitive_circle_add", "fill_type='NGON'"),
             _op("Platonic", "MESH_ICOSPHERE", "mesh.primitive_ico_sphere_add"))),
    # Shift + right-click in Edit Mode: the most used modeling tools, the rest one flick further
    dict(id="marking_poly_tools", name="Modeling Tools", editor="Mesh", key="RIGHTMOUSE", shift=True, key_event="HOLD",
         optional=True, styles=set(), items=(
             _op("Merge Tool", "AUTOMERGE_OFF", "wm.tool_set_by_id", "name='edit_mesh.merge_tool_workspace_tool'"),
             _op("Knife", "MOD_EDGESPLIT", "mesh.knife_tool"),
             _op("Bevel", "MOD_BEVEL", "mesh.bevel", "affect='EDGES'"),
             _op("Extrude", "EXTRUDE_REGION", "view3d.edit_mesh_extrude_move_normal"),
             _op("Loop Cut", "MOD_SUBSURF", "mesh.loopcut_slide"),
             _op("Offset Edge Loop", "MOD_OFFSET", "mesh.offset_edge_loops_slide"),
             _op("Connect", "SNAP_EDGE", "mesh.vert_connect_path"),
             (SUB, "More Tools", "", "preset:marking_mesh_tools", ""))),
    dict(id="marking_mesh_tools", name="More Modeling Tools", editor="Mesh", key="NONE", optional=True, styles=set(), items=(
             _op("Fill Holes", "OUTLINER_OB_SURFACE", "mesh.fill_holes"),
             _op("Mirror", "MOD_MIRROR", "mesh.symmetrize"),
             (M, "Cleanup", "BRUSH_DATA", "VIEW3D_MT_edit_mesh_clean", ""),
             _op("Smooth", "MOD_SMOOTH", "mesh.subdivide", "smoothness=1.0"),
             _op("Triangulate", "MOD_TRIANGULATE", "mesh.quads_convert_to_tris"),
             _op("Quadrangulate", "MESH_GRID", "mesh.tris_convert_to_quads"),
             _op("Separate", "UNLINKED", "mesh.separate", "type='SELECTED'"),
             (M, "Mapping", "UV", "VIEW3D_MT_uv_map", ""))),
    # Ctrl + right-click in Edit Mode: convert the selection
    dict(id="marking_convert", name="Convert Selection", editor="Mesh", key="RIGHTMOUSE", ctrl=True, key_event="HOLD",
         optional=True, styles=set(), items=(
             _op("To Vertices", "VERTEXSEL", "mesh.select_mode", "type='VERT', use_expand=True"),
             _op("To Faces", "FACESEL", "mesh.select_mode", "type='FACE', use_expand=True"),
             _op("To Shell", "SNAP_VOLUME", "mesh.select_linked"),
             _op("To Edges", "EDGESEL", "mesh.select_mode", "type='EDGE', use_expand=True"),
             _op("To Edge Loop", "MESH_CIRCLE",
                 *(("mesh.select_edge_loop_multi",) if bpy.app.version >= (5, 1, 0) else ("mesh.loop_multi_select", "ring=False"))),
             _op("To Edge Ring", "MESH_GRID",
                 *(("mesh.select_edge_ring_multi",) if bpy.app.version >= (5, 1, 0) else ("mesh.loop_multi_select", "ring=True"))),
             _op("To Inner Region", "SNAP_FACE", "mesh.loop_to_region"),
             _op("To Edge Perimeter", "MESH_CAPSULE", "mesh.region_to_loop"))),
    # Maya's tool marking menus: hold W, E or R and click (drag to pick)
    dict(id="marking_move", name="Move Options", editor="Object Mode, Mesh", key="LEFTMOUSE", key_mod="W",
         optional=True, styles=set(), items=(
             _orient("Object", "ORIENTATION_LOCAL", "LOCAL"),
             _orient("Component", "ORIENTATION_NORMAL", "NORMAL"),
             _op("Move Tool", "CON_LOCLIKE", "wm.tool_set_by_id", "name='builtin.move'"),
             _orient("World", "ORIENTATION_GLOBAL", "GLOBAL"),
             _orient("View", "ORIENTATION_VIEW", "VIEW"),
             _orient("Gimbal", "ORIENTATION_GIMBAL", "GIMBAL"),
             _orient("Cursor", "ORIENTATION_CURSOR", "CURSOR"),
             _orient("Parent", "ORIENTATION_PARENT", "PARENT"))),
    dict(id="marking_rotate", name="Rotate Options", editor="Object Mode, Mesh", key="LEFTMOUSE", key_mod="E",
         optional=True, styles=set(), items=(
             _pivot("Individual Origins", "PIVOT_INDIVIDUAL", "INDIVIDUAL_ORIGINS"),
             _pivot("Active Element", "PIVOT_ACTIVE", "ACTIVE_ELEMENT"),
             _op("Rotate Tool", "CON_ROTLIKE", "wm.tool_set_by_id", "name='builtin.rotate'"),
             _pivot("Median Point", "PIVOT_MEDIAN", "MEDIAN_POINT"),
             _pivot("Bounding Box", "PIVOT_BOUNDBOX", "BOUNDING_BOX_CENTER"),
             _pivot("3D Cursor", "PIVOT_CURSOR", "CURSOR"),
             (P, "Snap", "SNAP_ON", "tool_settings.use_snap", ""),
             (P, "Affect Only Origins", "OBJECT_ORIGIN", "tool_settings.use_transform_data_origin", ""))),
    dict(id="marking_scale", name="Scale Options", editor="Object Mode, Mesh", key="LEFTMOUSE", key_mod="R",
         optional=True, styles=set(), items=(
             (P, "Soft Select", "PROP_ON", "tool_settings.use_proportional_edit", ""),
             (P, "Connected Only", "PROP_CON", "tool_settings.use_proportional_connected", ""),
             _op("Scale Tool", "CON_SIZELIKE", "wm.tool_set_by_id", "name='builtin.scale'"),
             _pivot("Median Point", "PIVOT_MEDIAN", "MEDIAN_POINT"),
             _pivot("Individual Origins", "PIVOT_INDIVIDUAL", "INDIVIDUAL_ORIGINS"),
             _pivot("3D Cursor", "PIVOT_CURSOR", "CURSOR"),
             (P, "Snap", "SNAP_ON", "tool_settings.use_snap", ""),
             _op("Apply Scale", "CON_SIZELIKE", "object.transform_apply", "location=False, rotation=False, scale=True"))),
)
MAYA_PRESETS = {p["id"] for p in PRESETS if p["id"].startswith("marking_")}  # need the Marking style
PRESET_BY_ID = {p["id"]: p for p in PRESETS}
# The presets that existed before files recorded which presets they had seen
FIRST_PRESETS = ("add_objects", "add_modifier", "flatten", "cursor", "workspace", "utility", "uv_space", "uv_islands")

_ICONS = set(bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys())
_KEY_NAMES = {i.identifier: i.name for i in bpy.types.KeyMapItem.bl_rna.properties["type"].enum_items}
_KEY_NAMES.update({f"BUTTON{n}MOUSE": f"Mouse {n}" for n in range(4, 8)})
_MODIFIER_KEYS = {"LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_ALT", "RIGHT_ALT", "OSKEY"}


_loading = False  # True while pies are read from disk, so reading doesn't trigger a save
loaded_from_disk = False


def _panels_changed(self=None, context=None):
    _changed()
    schedule_panel_sync()


def _changed(self=None, context=None):
    if not _loading and getattr(get_keyops_prefs(), "pies", None) is not None:
        schedule_panel_sync()  # a panel's name or tab may have changed (cheap when nothing did)
    if not _loading:
        from . import settings_store
        settings_store.save_soon("pie_menus")


def _sync_update(self, context):
    sync_keymaps()


# ---------------------------------------------------------------- data


# ---------------------------------------------------------------- action catalog (simple mode dropdowns)

def _build_catalog():
    seen, out = set(), []
    for preset in PRESETS:
        for kind, label, icon, idname, props, *_show_if in preset["items"]:
            if kind in (N, SUB, LABEL) or (kind, idname, props) in seen:
                continue
            seen.add((kind, idname, props))
            out.append((preset["name"], kind, label, icon, idname, props))
    return out


_CATALOG = _build_catalog()
_BASE_ITEMS = [("EMPTY", "Empty", "Leave this slot empty", 'NONE', 0)]
_group = None
for _i, (_g, _kind, _label, _icon, _idname, _props) in enumerate(_CATALOG):
    if _g != _group:
        _BASE_ITEMS.append(("", _g, ""))
        _group = _g
    _BASE_ITEMS.append((f"C{_i}", _label, f"{_idname}  {_props}".strip(), _icon if _icon in _ICONS else 'NONE', _i + 1))
del _group, _i, _g, _kind, _label, _icon, _idname, _props
CUSTOM_VALUE = 9999
_choice_cache = {}


def _choice_items(self, context):
    if _choice_get(self) != CUSTOM_VALUE:
        return _BASE_ITEMS  # "Your own" only appears for slots that hold a custom command
    key = (self.label or self.idname or "Custom", self.icon if self.icon in _ICONS else 'NONE')
    if key not in _choice_cache:
        _choice_cache[key] = _BASE_ITEMS + [("", "Your own", ""),
                                            ("CUSTOM", key[0], "Your own command. Change it with Customize", key[1], CUSTOM_VALUE)]
    return _choice_cache[key]


def _choice_get(self):
    if self.kind == N or not self.idname.strip():
        return 0
    for i, (_g, kind, label, _icon, idname, props) in enumerate(_CATALOG):
        if (kind, idname, props, label) == (self.kind, self.idname.strip(), self.props.strip(), self.label):
            return i + 1
    return CUSTOM_VALUE


def _choice_set(self, value):
    if value == 0:
        self.kind = N
    elif value != CUSTOM_VALUE and 0 < value <= len(_CATALOG):
        _g, self.kind, self.label, self.icon, self.idname, self.props = _CATALOG[value - 1]


ITEM_TYPES = (  # the Type dropdown: what an item is (groups, columns and ends are made from Add)
    (O, "Operator", "Run an operator, e.g. bpy.ops.mesh.primitive_cube_add()", 'RADIOBUT_OFF', 0),
    (M, "Menu", "Open one of Blender's menus, e.g. VIEW3D_MT_add", 'COLLAPSEMENU', 1),
    (P, "Setting", "Toggle or change a setting, e.g. scene.tool_settings.use_snap", 'PROPERTIES', 2),
    (SUB, "Key Ops Menu", "Open another of your Key Ops menus", 'MENU_PANEL', 3),
    (PANEL_ITEM, "Panel", "Open one of Blender's panels, e.g. VIEW3D_PT_overlay", 'WINDOW', 4),
    (SCRIPT, "Python", "Run Python, the same way Blender's Text Editor runs a script", 'SCRIPT', 5),
    (MACRO, "Macro", "Run several operators one after another", 'SEQUENCE', 6),
    (LABEL, "Label", "A heading (popup menus, dialogs and panels)", 'FONT_DATA', 7),
    (N, "Empty", "Nothing (a separator in popup menus)", 'BLANK1', 8),
    (DRAW, "Draw Code", "Python that draws into the menu itself, like an add-on's draw(): lists, templates, "
                        "loops over objects. Popup menus, dialogs and panels", 'CONSOLE', 9),
)
_ITEM_TYPE_VALUE = {t[0]: t[4] for t in ITEM_TYPES}


def _item_type_get(self):
    return _ITEM_TYPE_VALUE.get(self.kind, _ITEM_TYPE_VALUE[N])


def _item_type_set(self, value):
    new = next((t[0] for t in ITEM_TYPES if t[4] == value), None)
    old = self.kind
    if new is None or new == old:
        return
    if old == MACRO:  # back to a single action: keep its first step
        first = self.steps[0] if len(self.steps) else None
        self.idname, self.props = (first.idname, first.props) if first else ("", "")
        self.steps.clear()
        if new == O:
            self.kind = O
            return
    if new == MACRO:  # an operator becomes the first step
        self.steps.clear()
        if old == O and self.idname.strip():
            st = self.steps.add()
            st.idname, st.props = self.idname, self.props
        if not len(self.steps):
            self.steps.add()
        self.kind, self.idname, self.props = MACRO, "", ""
        self.label = self.label or "Macro"
        return
    if old != MACRO:  # its command was for the old type
        self.idname, self.props = "", ""
    self.kind = new
    if new == SCRIPT and not self.script:
        self.script = "import bpy\n"
        self.label = self.label or "Python"
    if new == LABEL:
        self.label = self.label or "Heading"
    if new == DRAW and not self.script.strip():
        self.script = DRAW_DEFAULT


class KeyOpsMacroStep(PropertyGroup):
    idname: StringProperty(name="Operator", description="Operator to run in this step, e.g. mesh.select_all", update=_changed) # type: ignore
    props: StringProperty(name="Options", description="Options for this step, e.g. action='SELECT'", update=_changed) # type: ignore
    interactive: BoolProperty(name="Interactive", update=_changed,
                              description="Run this step like a key press, so tools that follow the mouse can be used. Later steps don't wait for it") # type: ignore


VALUE_OWNERS = (
    ("ADDON", "Key Ops", "Saved with Key Ops' settings, the same in every file. Use it as values:Name", 'PREFERENCES', 0),
    ("SCENE", "Scene", "A real property of each scene, saved in the .blend. Use it as scene.keyops_name", 'SCENE_DATA', 1),
    ("OBJECT", "Object", "A real property of each object, saved in the .blend. Use it as object.keyops_name "
                         "(the active object)", 'OBJECT_DATA', 2),
    ("WINDOW_MANAGER", "Window Manager", "A real property for this session only, not saved. Use it as "
                                         "window_manager.keyops_name", 'WINDOW', 3),
)
# where each owner's real property lives, and how an item's setting path reaches it
_OWNER_TYPES = {"SCENE": ("Scene", "scene"), "OBJECT": ("Object", "object"),
                "WINDOW_MANAGER": ("WindowManager", "window_manager")}
_choice_cache = {}  # options text -> enum items (Blender needs the strings kept alive)


def choice_items_from(text):
    """'Low, Medium, High' as enum items: [("LOW", "Low", ""), ...]. Empty: one item, so the enum stays valid."""
    if text not in _choice_cache:
        out, seen = [], set()
        for name in (n.strip() for n in text.split(",")):
            ident = re.sub(r"\W+", "_", name).strip("_").upper()
            if name and ident and ident not in seen:
                seen.add(ident)
                out.append((ident, name, "", len(out)))
        _choice_cache[text] = out or [("NONE", "None", "", 0)]
    return _choice_cache[text]


def _value_choice_items(self, context):
    return choice_items_from(self.choices)


def _value_choice_get(self):
    items = choice_items_from(self.choices)
    return next((i for i, it in enumerate(items) if it[0] == self.string_value), 0)


def _value_choice_set(self, value):
    items = choice_items_from(self.choices)
    self.string_value = items[value][0] if 0 <= value < len(items) else ""


def _value_def_changed(self, context):
    _values_changed()
    schedule_custom_props_sync()


class KeyOpsValue(PropertyGroup):
    """A property of your own (number, toggle, text or choice), usable in menus, tests and scripts. Kept by
    Key Ops, or made a real property of every scene, object or the window manager."""
    vtype: EnumProperty(name="Type", items=(("FLOAT", "Number", "A number like 0.25", 'DRIVER_DISTANCE', 0),
                                            ("INT", "Whole Number", "A whole number like 3", 'LINENUMBERS_ON', 1),
                                            ("BOOL", "Toggle", "On or off", 'CHECKBOX_HLT', 2),
                                            ("STRING", "Text", "Some text", 'SYNTAX_OFF', 3),
                                            ("ENUM", "Choice", "One of a list of options you write, like Low, "
                                                               "Medium, High", 'PRESET', 4)),
                        update=_value_def_changed) # type: ignore
    owner: EnumProperty(name="Stored On", items=VALUE_OWNERS, update=_value_def_changed,
                        description="Where the property lives") # type: ignore
    choices: StringProperty(name="Options", default="Low, Medium, High", update=_value_def_changed,
                            description="Choice: the options, separated by commas") # type: ignore
    float_value: FloatProperty(name="Value", update=_value_def_changed) # type: ignore
    int_value: IntProperty(name="Value", update=_value_def_changed) # type: ignore
    bool_value: BoolProperty(name="Value", update=_value_def_changed) # type: ignore
    string_value: StringProperty(name="Value", update=_value_def_changed) # type: ignore
    enum_value: EnumProperty(name="Value", items=_value_choice_items, get=_value_choice_get, set=_value_choice_set,
                             options={'SKIP_SAVE'}) # type: ignore

    @property
    def field(self):
        return {"FLOAT": "float_value", "INT": "int_value", "BOOL": "bool_value", "STRING": "string_value",
                "ENUM": "enum_value"}[self.vtype]

    @property
    def attr(self):
        """The real property's name: keyops_ and the name in lower case, e.g. keyops_bevel_size."""
        return custom_prop_attr(self.name)

    @property
    def path(self):
        """What an item's setting path, a test or a script uses to reach it."""
        if self.owner in _OWNER_TYPES:
            return f"{_OWNER_TYPES[self.owner][1]}.{self.attr}"
        return f"values:{self.name}"


def custom_prop_attr(name):
    return ("keyops_" + re.sub(r"\W+", "_", name.strip().lower()).strip("_"))[:63]


_custom_props = []  # (type name, attribute) of the real properties made from My Properties


def _custom_prop(v):
    """The bpy.props definition for a property of your own, with its value as the default."""
    desc = f"Key Ops: one of your own properties ({v.name})"
    if v.vtype == "FLOAT":
        return FloatProperty(name=v.name, description=desc, default=v.float_value)
    if v.vtype == "INT":
        return IntProperty(name=v.name, description=desc, default=v.int_value)
    if v.vtype == "BOOL":
        return BoolProperty(name=v.name, description=desc, default=v.bool_value)
    if v.vtype == "ENUM":
        items = [it[:3] for it in choice_items_from(v.choices)]
        default = v.string_value if any(it[0] == v.string_value for it in items) else items[0][0]
        return EnumProperty(name=v.name, description=desc, items=items, default=default)
    return StringProperty(name=v.name, description=desc, default=v.string_value)


def remove_custom_props():
    while _custom_props:
        type_name, attr = _custom_props.pop()
        cls = getattr(bpy.types, type_name, None)
        if cls is not None and hasattr(cls, attr):
            delattr(cls, attr)


def sync_custom_props():
    """Make (or remake) the real Scene, Object and Window Manager properties from My Properties. Values already
    set in a file stay: Blender keeps them by name, and a property made again reads them back."""
    remove_custom_props()
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None or not hasattr(wm, "keyops_values"):
        return
    taken = set()
    for v in wm.keyops_values:
        if v.owner not in _OWNER_TYPES or not v.name.strip():
            continue
        type_name = _OWNER_TYPES[v.owner][0]
        cls = getattr(bpy.types, type_name)
        attr = v.attr
        if (type_name, attr) in taken or (hasattr(cls, attr) and (type_name, attr) not in _custom_props):
            continue  # two with the same name, or a property someone else made
        setattr(cls, attr, _custom_prop(v))
        _custom_props.append((type_name, attr))
        taken.add((type_name, attr))


def schedule_custom_props_sync():
    if _loading:
        return
    if not bpy.app.timers.is_registered(_custom_props_timer):
        bpy.app.timers.register(_custom_props_timer, first_interval=0.05)


def _custom_props_timer():
    sync_custom_props()
    return None


def values_by_name(context=None):
    """My Properties by name, with their values here (a scene or object property: the current scene's or the
    active object's). For tests and Draw Code: values["Bevel Size"]."""
    context = context or bpy.context
    out = {}
    wm = getattr(context, "window_manager", None)
    for v in (getattr(wm, "keyops_values", None) or ()):
        if v.owner in _OWNER_TYPES:
            base = {"SCENE": getattr(context, "scene", None), "OBJECT": getattr(context, "active_object", None),
                    "WINDOW_MANAGER": wm}[v.owner]
            out[v.name] = getattr(base, v.attr, None) if base is not None else None
        else:
            out[v.name] = getattr(v, v.field)
    return out


def _values_changed():
    if not _loading:
        from . import settings_store
        settings_store.save_soon("values")


def _append_targets(text):
    """Blender menus, headers and panels whose name contains the typed text (Add To search)."""
    text = text.strip().lower()
    names = [n for n in dir(bpy.types) if ("_MT_" in n or "_HT_" in n or "_PT_" in n) and not n.startswith("KEYOPS")]
    return [n for n in sorted(names) if text in n.lower()][:300]


_EDITOR_IDS = [e[0] for e in EDITORS]
_EDITOR_LABELS = {e[0]: e[1] for e in EDITORS}
_EDITOR_ICONS = {e[0]: e[3] for e in EDITORS}


def editor_names(pie_or_text):
    """The editors a menu works in, as a list of EDITORS ids (unknown names are dropped)."""
    text = pie_or_text if isinstance(pie_or_text, str) else pie_or_text.editor
    return [n for n in (x.strip() for x in text.split(",")) if n in _EDITOR_LABELS]


# the editor (area type) each Works In choice means; None: every editor
_EDITOR_AREAS = {"3D View Generic": 'VIEW_3D', "Object Mode": 'VIEW_3D', "Mesh": 'VIEW_3D', "Sculpt": 'VIEW_3D',
                 "Weight Paint": 'VIEW_3D', "UV Editor": 'IMAGE_EDITOR', "Image": 'IMAGE_EDITOR',
                 "Node Editor": 'NODE_EDITOR', "Graph Editor": 'GRAPH_EDITOR', "Dopesheet": 'DOPESHEET_EDITOR',
                 "Outliner": 'OUTLINER', "Property Editor": 'PROPERTIES', "Sequencer": 'SEQUENCE_EDITOR',
                 "Text": 'TEXT_EDITOR', "Window": None, "Curve": 'VIEW_3D'}


def editor_ok(context, pie):
    """Whether the mouse is over an editor the menu works in (the UV Editor: an image editor showing UVs)."""
    area = context.area
    if area is None:
        return True
    for name in editor_names(pie):
        want = _EDITOR_AREAS.get(name)
        if want is None:
            return True
        if area.type != want:
            continue
        if name == "UV Editor" and getattr(area, "ui_type", 'UV') != 'UV':
            continue
        return True
    return False


BAR_FIELD_UNITS = 6.5  # the Works In bar's fields: all one width


def _bar_label(layout, text):
    """A field's name in the Works In bar: grey, before the field."""
    r = layout.row()
    r.alignment = 'RIGHT'
    r.ui_units_x = 3.2
    r.active = False
    r.label(text=text)


def editor_text(pie):
    names = editor_names(pie)
    return ", ".join(_EDITOR_LABELS[n] for n in names) if names else "Nowhere"


def _editor_bits(text):
    return sum(1 << _EDITOR_IDS.index(n) for n in editor_names(text))


def _set_editor_bits(self, bits):
    names = [e for i, e in enumerate(_EDITOR_IDS) if bits & (1 << i)]
    self.editor = ", ".join(names or [self.editor])  # never leave a menu working nowhere


def _command_get(self):
    """The operator and its options as one line, the way Python writes it: bpy.ops.mesh.primitive_cube_add(size=2)."""
    return f"bpy.ops.{self.idname}({self.props})" if self.idname else ""


def _command_set(self, value):
    """Typed or pasted (also bpy.ops.... from the Info editor): split into operator and options.
    Text that doesn't read as a command is kept as the operator, so nothing typed is lost."""
    parsed = parse_command(value) if value.strip() else ("", "")
    if parsed is None:
        self.idname, self.props = value.strip().removeprefix("bpy.ops."), ""
    else:
        self.idname, self.props = parsed
    _changed()


class KeyOpsPieItem(PropertyGroup):
    kind: EnumProperty(name="Type", items=(
        (N, "Empty", "Leave this slot empty (a separator in popup menus)"),
        (O, "Operator", "Run an operator, e.g. mesh.primitive_cube_add"),
        (M, "Menu", "Open a menu, e.g. VIEW3D_MT_add"),
        (P, "Toggle", "Toggle a setting, e.g. scene.tool_settings.use_snap"),
        (MACRO, "Macro", "Run several operators one after another"),
        (SUB, "Key Ops Menu", "Open another of your Key Ops menus"),
        (SCRIPT, "Python", "Run Python, the same way Blender's Text Editor runs a script"),
        (PANEL_ITEM, "Blender Panel", "Open one of Blender's panels, e.g. VIEW3D_PT_overlay"),
        (LABEL, "Label", "A heading (popup menus, dialogs and panels)"),
        (DRAW, "Draw Code", "Python that draws into the menu itself, like an add-on's draw()"),
        (BREAK, "Next Column", "Popup menus, dialogs and panels: the items after this go in the next column"),
        (BOX, "Group", "Popup menus, dialogs and panels: the items after this go in a box, row, column, split or grid, "
                       "until End Group. Groups can sit inside groups"),
        (BOX_END, "End Group", "Ends the group, the items after this are outside it again")), update=_changed) # type: ignore
    emboss: BoolProperty(name="Emboss", default=True, update=_changed,
                         description="Draw the button with its frame (Blender's emboss). Off: flat, only the icon and text") # type: ignore
    active: BoolProperty(name="Active", default=True, update=_changed,
                         description="Off: drawn greyed out, like a button that doesn't apply right now. It still works") # type: ignore
    depress: BoolProperty(name="Depress", default=False, update=_changed,
                          description="Draw the button pressed in, like a toggle that's on") # type: ignore
    call_mode: EnumProperty(name="Run As", items=CALL_MODES, update=_changed,
                            description="How the operator is called when the button is clicked") # type: ignore
    height: FloatProperty(name="Scale Y", default=1.0, min=0.2, max=6.0, step=10, precision=2, update=_changed,
                          description="Scale on the Y axis (Blender's scale_y): taller, 1 is normal") # type: ignore
    width: FloatProperty(name="Scale X", default=1.0, min=0.2, max=6.0, step=10, precision=2, update=_changed,
                         description="Scale on the X axis (Blender's scale_x): wider, compared to the others in its row. "
                                     "1 is normal") # type: ignore
    group_type: EnumProperty(name="Layout", default="BOX", update=_changed, items=GROUP_TYPES,
                             description="How a group lays out its items") # type: ignore
    align: BoolProperty(name="Align", default=False, update=_changed,
                        description="Join the group's buttons together, with no space between them (Blender's align)") # type: ignore
    alignment: EnumProperty(name="Alignment", default="EXPAND", update=_changed, items=(
        ("EXPAND", "Expand", "Items fill the width"), ("LEFT", "Left", "Items at their own width, on the left"),
        ("CENTER", "Center", "Items at their own width, in the middle"), ("RIGHT", "Right", "Items at their own width, on the right")),
        description="Where the group's items sit across its width") # type: ignore
    factor: FloatProperty(name="Split", default=0.0, min=0.0, max=1.0, update=_changed, subtype='FACTOR',
                          description="Split: how much of the width the first column takes. 0: equal columns") # type: ignore
    grid_columns: IntProperty(name="Columns", default=0, min=0, max=16, update=_changed,
                              description="Grid Flow: how many columns. 0: as many as fit") # type: ignore
    closed: BoolProperty(name="Start Closed", default=False, update=_changed,
                         description="Panel: closed until you open it") # type: ignore
    sep_type: EnumProperty(name="Separator", default="AUTO", update=_changed, items=(
        ("AUTO", "Auto", "A line in menus, a gap elsewhere"), ("LINE", "Line", "A line"), ("SPACE", "Space", "A gap"),
        ("SPACER", "Spacer", "In a row or header: a gap that pushes everything after it to the far end "
                             "(separator_spacer)")),
        description="How a separator is drawn (Line and Space need Blender 4.2)") # type: ignore
    sep_factor: FloatProperty(name="Size", default=1.0, min=0.0, max=10.0, step=10, update=_changed,
                              description="How much space the separator takes, 1 is normal") # type: ignore
    prop_split: BoolProperty(name="Property Split", default=False, update=_changed,
                             description="Settings with their name on the left and the field on the right, like Blender's "
                                         "Properties editor (use_property_split)") # type: ignore
    in_header: BoolProperty(name="In Header", default=False, update=_changed,
                            description="Sidebar panels: draw this item in the panel's header, on the right "
                                        "(like a Prefs button)") # type: ignore
    same_row: BoolProperty(name="Same Row", default=False, update=_changed,
                           description="Popup menus, dialogs and panels: put this item beside the one before it") # type: ignore
    alert: BoolProperty(name="Alert", default=False, update=_changed,
                        description="Draw the button in red (Blender's alert), for something to think twice about") # type: ignore
    setting_style: EnumProperty(name="Draw As", items=SETTING_STYLES, update=_changed,
                                description="How a setting is drawn") # type: ignore
    enabled: BoolProperty(name="Enabled", default=True, update=_changed,
                          description="Off: drawn greyed out and can't be clicked (Blender's enabled). "
                                      "Active off only greys it out") # type: ignore
    menu_style: EnumProperty(name="Draw As", items=MENU_STYLES, update=_changed,
                             description="How a menu item is drawn") # type: ignore
    sub_style: EnumProperty(name="Draw As", items=SUB_STYLES, update=_changed,
                            description="How a Key Ops Menu item is drawn") # type: ignore
    op_style: EnumProperty(name="Draw As", items=OP_STYLES, update=_changed,
                           description="How an operator is drawn") # type: ignore
    enum_prop: StringProperty(name="Choice Option", update=_changed,
                              description="The operator's choice option the dropdown or buttons list, e.g. type") # type: ignore
    source: StringProperty(name="Source", update=_changed,
                           description="Search: where to search. List: the active index setting. One Option: the "
                                       "option. Data-Block: the New operator") # type: ignore
    index: IntProperty(name="Index", default=-1, min=-1, max=63, update=_changed,
                       description="For a setting with several values (location, a layer mask): only this one, "
                                   "0 is the first. -1: all of them") # type: ignore
    invert: BoolProperty(name="Invert", default=False, update=_changed,
                         description="Checkbox ticked while the setting is off (invert_checkbox)") # type: ignore
    decorate: BoolProperty(name="Keyframe Button", default=False, update=_changed,
                           description="Show the keyframe dot after the setting, like the Properties editor "
                                       "(use_property_decorate)") # type: ignore
    script: StringProperty(name="Python", description="Python to run. Use the Text Editor button for longer scripts",
                           update=_changed) # type: ignore
    steps: CollectionProperty(type=KeyOpsMacroStep) # type: ignore
    extra: StringProperty(options={'HIDDEN'}) # type: ignore  # fields from newer versions, kept as JSON
    label: StringProperty(name="Label", update=_changed,
                          description="The button's text. Leave it empty to show only the icon") # type: ignore
    icon: StringProperty(name="Icon", description="Blender icon name, e.g. MESH_CUBE. Leave empty for no icon", update=_changed) # type: ignore
    idname: StringProperty(name="Command", description="Operator id, menu id or setting path", update=_changed) # type: ignore
    props: StringProperty(name="Options", description="Operator options, e.g. type='WELD', segments=4", update=_changed) # type: ignore
    command: StringProperty(name="Operator", get=_command_get, set=_command_set, options={'SKIP_SAVE'},
                            description="The operator and its options on one line, e.g. "
                                        "bpy.ops.mesh.primitive_cube_add(size=2). Paste a command copied from "
                                        "Blender's Info editor or Python Console, or from a button "
                                        "(right-click > Copy Python Command). The bpy.ops. part is optional") # type: ignore
    show_if: StringProperty(name="Poll", update=_changed,
                            description="Poll: decides when this item shows. Write a test, and the item only shows "
                                        "while it's true. Empty: always shown. E.g. mode == 'EDIT_MESH', sel > 1, "
                                        "'BOOLEAN' in mods. Names: C, obj, space, scene, tool, mode, mods (modifier "
                                        "types), sel (selected count). The ? button shows more examples") # type: ignore
    item_type: EnumProperty(name="Type", description="What this item is", items=ITEM_TYPES,
                            get=_item_type_get, set=_item_type_set, options={'SKIP_SAVE'}) # type: ignore
    choice: EnumProperty(name="Action", description="What this slot does. Pick any Key Ops action",
                         items=_choice_items, get=_choice_get, set=_choice_set) # type: ignore


class KeyOpsPie(PropertyGroup):
    uid: StringProperty() # type: ignore
    menu_type: EnumProperty(name="Menu Type", items=_menu_type_items, update=_sync_update) # type: ignore
    # the modes it opens in, comma separated ("ANY": every mode). Older versions saved one mode, which still reads
    only_mode: StringProperty(name="Only In", default="ANY", update=_changed,
                              description="Only open in these modes; anywhere else the key does what Blender does") # type: ignore
    only_mode_set: EnumProperty(name="Only In", options={'ENUM_FLAG'}, get=_mode_bits_get, set=_mode_bits_set,
                                description="Only open in these modes; anywhere else the key does what Blender does. "
                                            "None picked: any mode",
                                items=[(m[0], m[1], m[2], _MODE_ICONS[m[0]], 1 << i)
                                       for i, m in enumerate(ONLY_MODES[1:])]) # type: ignore
    key_event: EnumProperty(name="Key Event", items=KEY_EVENTS, update=_sync_update) # type: ignore
    key_mod: EnumProperty(name="While Holding", update=_sync_update,
                          description="Optional: a second key that must be held, for two-key shortcuts",
                          items=[(i.identifier, "Nothing" if i.identifier == "NONE" else _KEY_NAMES.get(i.identifier, i.name), "")
                                 for i in bpy.types.KeyMapItem.bl_rna.properties["key_modifier"].enum_items]) # type: ignore
    columns: IntProperty(name="Columns", default=2, min=1, max=6, update=_changed) # type: ignore
    tab: StringProperty(name="Tab", default="Toolkit", update=_panels_changed,
                        description="Sidebar panels: the sidebar (N) tab the panel is in. A new name makes a new tab") # type: ignore
    dialog_mode: EnumProperty(name="Behaviour", items=(
        ("POPUP", "Popup", "Closes when the mouse moves away"),
        ("DIALOG", "Dialog", "Stays open until you close it")), update=_changed) # type: ignore
    stack_reset: FloatProperty(name="Start Over After", default=2.0, min=0.0, max=30.0, subtype='TIME_ABSOLUTE', unit='TIME_ABSOLUTE',
                               description="Seconds without a press before the stack starts at the first item again (0 = never)",
                               update=_changed) # type: ignore
    extra: StringProperty(options={'HIDDEN'}) # type: ignore
    name: StringProperty(name="Name", default="New Pie", update=_changed) # type: ignore
    preset: StringProperty(description="Preset this pie was made from") # type: ignore
    # the menu this one is a submenu of: it's edited from that menu and isn't listed on its own
    owner: StringProperty(options={'HIDDEN'}) # type: ignore
    enabled: BoolProperty(name="Enabled", default=True, update=_sync_update) # type: ignore
    # one or more EDITORS ids, comma separated, e.g. "Object Mode, Mesh"
    editor: StringProperty(name="Works In", default="3D View Generic", update=_sync_update) # type: ignore
    editor_set: EnumProperty(name="Works In", options={'ENUM_FLAG'}, description="Where the key works. Pick one or more",
                             items=[(e[0], e[1], e[2], e[3], 1 << i) for i, e in enumerate(EDITORS)],
                             get=lambda self: _editor_bits(self.editor), set=_set_editor_bits) # type: ignore
    key: StringProperty(name="Key", default="NONE", update=_changed) # type: ignore
    ctrl: BoolProperty(name="Ctrl", update=_changed) # type: ignore
    shift: BoolProperty(name="Shift", update=_changed) # type: ignore
    alt: BoolProperty(name="Alt", update=_changed) # type: ignore
    condition: StringProperty(
        name="Show When", update=_changed,
        description="Optional test on settings, e.g. obj and obj.type == 'MESH' or space.shading.type == 'SOLID'. "
                    "Names: C (context), obj, space, scene, tool, mode, mods (modifier types), sel (selected count). "
                    "When it's false, the key does what Blender does") # type: ignore
    append_to: StringProperty(name="Add To", update=_sync_update, search=lambda self, context, text: _append_targets(text),
                              description="Also show this menu inside one of Blender's menus, headers or panels, "
                                          "e.g. VIEW3D_MT_object_context_menu (right-click menu in Object Mode)") # type: ignore
    append_as: EnumProperty(name="As", update=_sync_update, items=(
        ("BUTTON", "Button", "A button that opens this menu"),
        ("ITEMS", "Items", "This menu's items, placed right there"))) # type: ignore
    tags: StringProperty(name="Tags", update=_changed,
                         description="Words to group your menus by, separated by commas, e.g. modeling, uv. "
                                     "Use the filter beside the search to show one tag") # type: ignore
    radius: IntProperty(name="Pie Size", default=0, min=0, max=1000, subtype='PIXEL', update=_changed,
                        description="Marking menus only: how far from the mouse the buttons sit. "
                                    "0 uses Blender's Pie Menu Radius") # type: ignore
    threshold: IntProperty(name="Flick Distance", default=0, min=0, max=1000, subtype='PIXEL', update=_changed,
                           description="Marking menus only: how far to move the mouse before a direction is "
                                       "chosen. 0 uses Blender's Pie Menu Threshold") # type: ignore
    panel_icon: StringProperty(name="Header Icon", update=_changed,
                               description="Sidebar panels: an icon before the panel's name, e.g. MODIFIER or "
                                           "keyops:union. Empty: none") # type: ignore
    panel_hide_header: BoolProperty(name="Hide Header", default=False, update=_panels_changed,
                                    description="Sidebar panels: no header, the items only. The panel can't be "
                                                "closed or moved") # type: ignore
    panel_closed: BoolProperty(name="Start Closed", default=False, update=_panels_changed,
                               description="Sidebar panels: closed until you open it") # type: ignore
    panel_order: IntProperty(name="Order", default=0, min=-1000, max=1000, update=_panels_changed,
                             description="Sidebar panels: lower numbers sit higher in the tab. 0: in the order "
                                         "they were made") # type: ignore
    panel_parent: StringProperty(name="Inside", update=_panels_changed,
                                 description="Sidebar panels: show this panel as a sub-panel inside another of your "
                                             "sidebar panels (its menu id). Empty: a panel of its own") # type: ignore
    items: CollectionProperty(type=KeyOpsPieItem) # type: ignore


def key_text(pie):
    if pie.key in ("", "NONE"):
        return "No key"
    mods = [m for m, on in (("Ctrl", pie.ctrl), ("Shift", pie.shift), ("Alt", pie.alt)) if on]
    if getattr(pie, "key_mod", "NONE") not in ("NONE", ""):
        mods.append(_KEY_NAMES.get(pie.key_mod, pie.key_mod) + " +")
    return " ".join(mods + [_KEY_NAMES.get(pie.key, pie.key)])


def _fill(pie, preset):
    pie.name = preset["name"]
    pie.preset = preset["id"]
    pie.editor = preset["editor"]
    pie.key = preset["key"]
    pie.ctrl = preset.get("ctrl", False)
    pie.shift = preset.get("shift", False)
    pie.alt = preset.get("alt", False)
    pie.key_event = preset.get("key_event", "PRESS")
    pie.menu_type = preset.get("menu_type", "PIE")
    pie.condition = preset.get("condition", "")
    pie.key_mod = preset.get("key_mod", "NONE")
    pie.items.clear()
    # items are (kind, label, icon, idname, props), optionally followed by the item's Show If test
    # and, for settings, how it's drawn (SETTING_STYLES)
    for kind, label, icon, idname, props, *extra in preset["items"]:
        it = pie.items.add()
        if kind == SUB and idname.startswith("preset:"):
            sub_id = idname[len("preset:"):]
            idname = _pie_for_preset(sub_id, owner=pie.uid if PRESET_BY_ID.get(sub_id, {}).get("sub") else "")
        it.kind, it.label, it.icon, it.idname, it.props = kind, label, icon, idname, props
        it.show_if = extra[0] if extra else ""
        it.setting_style = extra[1] if len(extra) > 1 else "AUTO"
        if kind == P and it.setting_style in SETTING_SOURCE:
            it.source, it.props = props, ""  # e.g. the option a One Option button sets


def _pie_for_preset(preset_id, owner=""):
    """The menu made from this preset (added, switched off, if there isn't one yet), for submenus.
    With an owner: that menu's own copy, which belongs to it (edited from it, not listed on its own)."""
    prefs = get_keyops_prefs()
    mine = [p for p in prefs.pies if p.preset == preset_id and (p.owner == owner or not p.owner)]
    found = next((p for p in mine if p.owner == owner), None) or (mine[0] if mine else None)
    if found is None and preset_id in PRESET_BY_ID:
        found = _new_pie(prefs)
        _fill(found, PRESET_BY_ID[preset_id])
        found["enabled"] = False
    if found is not None and owner and found.uid != owner:
        found.owner = owner
    return found.uid if found else ""


# ---------------------------------------------------------------- submenus that belong to a menu

def submenus_of(prefs, uid):
    """The menus that belong to this one (its own submenus), in list order."""
    return [p for p in prefs.pies if p.owner == uid and p.uid != uid] if uid else []


def menu_family(prefs, pie):
    """This menu and every submenu that belongs to it, however deep (each once, even if they loop)."""
    out, todo, seen = [], [pie], set()
    while todo:
        cur = todo.pop(0)
        if cur.uid in seen:
            continue
        seen.add(cur.uid)
        out.append(cur)
        todo.extend(submenus_of(prefs, cur.uid))
    return out


def owner_chain(prefs, pie):
    """The menus above this one, top first: [Q Menu] for Q Menu: Modifiers. Empty for a top-level menu."""
    chain, seen = [], {pie.uid}
    cur = find_pie(pie.owner) if pie.owner else None
    while cur is not None and cur.uid not in seen:
        chain.insert(0, cur)
        seen.add(cur.uid)
        cur = find_pie(cur.owner) if cur.owner else None
    return chain


def listed(pie):
    """Shown in the menu list: top-level menus. A submenu that belongs to a menu is edited from it."""
    return not pie.owner or find_pie(pie.owner) is None


def _new_pie(prefs):
    pie = prefs.pies.add()
    pie.uid = uuid.uuid4().hex[:12]
    return pie


def install_presets(prefs, style):
    """Fill the pie list from the presets, enabling the ones the chosen keyboard style includes."""
    global _loading
    _loading = True  # one save at the end, not one per field
    try:
        prefs.pies.clear()
        for preset in PRESETS:
            if preset.get("optional"):
                continue  # only from Add Preset
            pie = _new_pie(prefs)
            _fill(pie, preset)
            pie["enabled"] = style in preset["styles"]  # no update callback while filling
        prefs.pies_installed = True
    finally:
        _loading = False
    _changed()
    sync_keymaps()


# ---------------------------------------------------------------- saving to pie_menus.json

PIE_FIELDS = ("uid", "name", "preset", "enabled", "menu_type", "editor", "key", "ctrl", "shift", "alt",
              "key_event", "only_mode", "columns", "dialog_mode", "stack_reset", "key_mod", "condition", "radius", "threshold",
              "append_to", "append_as", "tags", "tab", "owner", "panel_icon", "panel_hide_header", "panel_closed",
              "panel_order", "panel_parent")
ITEM_FIELDS = ("kind", "label", "icon", "idname", "props", "script", "show_if",
               "emboss", "active", "depress", "group_type", "align", "alignment", "factor", "grid_columns",
               "prop_split", "closed", "sep_type", "sep_factor", "height", "width", "same_row", "alert", "setting_style", "in_header",
               "call_mode", "enabled", "menu_style", "op_style", "enum_prop", "source", "index", "invert", "decorate",
               "sub_style")
STEP_FIELDS = ("idname", "props", "interactive")
PIE_SCHEMA = 15  # bump when the saved layout changes, and add a migration below


def _extra(obj):
    try:
        return json.loads(obj.extra) if obj.extra else {}
    except ValueError:
        return {}


def _item_to_data(it):
    d = dict(_extra(it))  # unknown fields from newer versions go back out unchanged
    d.update({f: getattr(it, f) for f in ITEM_FIELDS})
    if it.kind == MACRO:
        d["steps"] = [{f: getattr(st, f) for f in STEP_FIELDS} for st in it.steps]
    return d


def _item_from_data(it, d):
    it.steps.clear()
    _apply(it, ITEM_FIELDS, d)
    for st_data in d.get("steps", []):
        if isinstance(st_data, dict):
            st = it.steps.add()
            for f in STEP_FIELDS:
                if f in st_data:
                    try:
                        setattr(st, f, st_data[f])
                    except (TypeError, ValueError):
                        pass


def pies_to_data(prefs):
    out = []
    for p in prefs.pies:
        d = dict(_extra(p))
        d.update({f: getattr(p, f) for f in PIE_FIELDS})
        d["items"] = [_item_to_data(it) for it in p.items]
        out.append(d)
    return {"pies": out, "presets_seen": sorted(PRESET_BY_ID)}


def _apply(obj, fields, entry):
    for f in fields:
        if f in entry:
            try:
                setattr(obj, f, entry[f])
            except (TypeError, ValueError):
                pass  # e.g. an editor name from another version: keep the default
    unknown = {k: v for k, v in entry.items() if k not in fields and k not in ("items", "steps", "uid")}
    obj.extra = json.dumps(unknown) if unknown else ""


def pies_from_data(prefs, data, merge):
    """Replace the menu list (or, with merge, add/update menus by id) from saved data."""
    global _loading
    _loading = True
    try:
        if not merge:
            prefs.pies.clear()
        by_uid = {p.uid: p for p in prefs.pies}
        for entry in data.get("pies", []):
            if not isinstance(entry, dict):
                continue
            uid = str(entry.get("uid") or uuid.uuid4().hex[:12])
            pie = by_uid.get(uid) or prefs.pies.add()
            pie.uid = uid
            _apply(pie, PIE_FIELDS[1:], entry)
            pie.items.clear()
            limit = ITEM_LIMIT.get(pie.menu_type, LIST_LIMIT)
            for it_data in entry.get("items", [])[:limit]:
                it = pie.items.add()
                if isinstance(it_data, dict):
                    _item_from_data(it, it_data)
            while len(pie.items) < ITEM_MIN.get(pie.menu_type, 0):
                pie.items.add()
        for pie in [p for p in prefs.pies if p.uid in _refill_uids and p.preset in PRESET_BY_ID]:
            # rebuilt from the preset, but your key and on/off stay as they were
            keep = {f: getattr(pie, f) for f in ("enabled", "key", "ctrl", "shift", "alt", "key_event", "key_mod")}
            _fill(pie, PRESET_BY_ID[pie.preset])
            for field, value in keep.items():
                setattr(pie, field, value)
        _refill_uids.clear()
        if not merge:
            # Presets added in a newer Key Ops show up once, switched off; your own pies are untouched
            seen = set(data.get("presets_seen", FIRST_PRESETS)) | {p.preset for p in prefs.pies}
            for preset in PRESETS:
                if preset["id"] not in seen and not preset.get("optional"):
                    pie = _new_pie(prefs)
                    _fill(pie, preset)
                    pie["enabled"] = False
        prefs.pies_installed = True
        prefs.active_pie = min(prefs.active_pie, max(0, len(prefs.pies) - 1))
    finally:
        _loading = False
    sync_keymaps()


def _migrate_pies_1_to_2(data):
    """Schema 1 (first JSON version) had pies only: mark them as pies; items have no steps."""
    for p in data.get("pies", []):
        p.setdefault("menu_type", "PIE")
    return data


def _migrate_pies_2_to_3(data):
    """Schema 3 added more menu types and per-menu options; older menus keep the defaults."""
    for p in data.get("pies", []):
        p.setdefault("key_event", "PRESS")
        p.setdefault("only_mode", "ANY")
    return data


def _migrate_pies_3_to_4(data):
    """Schema 4 added Python, panel and label items, and two-key shortcuts. Nothing to convert."""
    return data


def _migrate_pies_4_to_5(data):
    """Schema 5 added Hold, conditions, several editors per menu, pie size, tags and adding menus to
    Blender's own menus. All optional with defaults, so nothing to convert."""
    return data


def _migrate_pies_5_to_6(data):
    """Schema 6 added how each button is drawn (icon/text, frame, size, colour), Same Row and boxes.
    All optional with defaults, so nothing to convert."""
    return data


def _migrate_pies_6_to_7(data):
    """Schema 7 dropped the Show setting (icon and text / icon only / text only): an item with an icon and no
    label shows only its icon, an item without an icon only its text. Icon-only items lose their label,
    text-only items their icon, so they look the same as before."""
    for p in data.get("pies", []):
        for it in p.get("items", []):
            if not isinstance(it, dict):
                continue
            show = it.pop("display", "AUTO")
            if show == "ICON" and it.get("icon"):
                it["label"] = ""
            elif show == "TEXT":
                it["icon"] = ""
        # boxes became groups that can sit inside each other: a box used to end at the next box or column,
        # so close it there explicitly
        out, open_box = [], False
        for it in p.get("items", []):
            kind = it.get("kind") if isinstance(it, dict) else None
            if kind in (BOX, BREAK) and open_box:
                out.append({"kind": BOX_END, "label": "End Group"})
                open_box = False
            if kind == BOX:
                open_box = True
            elif kind == BOX_END:
                open_box = False
            out.append(it)
        if "items" in p:
            p["items"] = out
    return data


def _migrate_pies_7_to_8(data):
    """Schema 8: the Flatten preset also works in the UV Editor (Flatten straightens UVs there)."""
    for p in data.get("pies", []):
        if p.get("preset") == "flatten" and p.get("editor") == "Mesh":
            p["editor"] = "Mesh, UV Editor"
    return data


_refill_uids = set()  # menus a migration asked to rebuild from their preset, done by pies_from_data


def _migrate_pies_8_to_9(data):
    """Schema 9: the Q Menu became one column with submenus. Menus made from the earlier Q Menu
    (columns, with the Cutter Tool) are rebuilt from the new preset; their key and on/off stay."""
    for p in data.get("pies", []):
        if p.get("preset") == "q_menu" and p.get("uid"):
            _refill_uids.add(str(p["uid"]))
    return data


def _migrate_pies_9_to_10(data):
    """Schema 10: the Q Menu and its submenus use the N panel's icons, settings with choices open as
    submenus. Menus made from those presets are rebuilt from them; their key and on/off stay."""
    for p in data.get("pies", []):
        if str(p.get("preset", "")).startswith("q_") and p.get("uid"):
            _refill_uids.add(str(p["uid"]))
    return data


def _migrate_pies_10_to_11(data):
    """Schema 11: a menu's own submenus belong to it (edited from it, not listed on their own). The Q Menu's
    submenus, made from its preset, become its own."""
    pies = data.get("pies", [])
    owners = {p.get("uid"): p for p in pies}
    for p in pies:
        if not str(p.get("preset", "")).startswith("q_") or p.get("preset") in ("q_menu", "q_menu_columns"):
            continue
        parent = next((q for q in pies if q.get("preset") == "q_menu"
                       and any(i.get("kind") == SUB and i.get("idname") == p.get("uid") for i in q.get("items", []))), None)
        if parent is not None and parent.get("uid") in owners:
            p["owner"] = parent["uid"]
    return data


def _migrate_pies_11_to_12(data):
    """Schema 12: the Q Menu's labels drop "Fast" (Mirror, Bevel, Array, Solidify, Merge). Menus made from
    the Q Menu presets are rebuilt from them; their key and on/off stay."""
    return _migrate_pies_9_to_10(data)


def _migrate_pies_12_to_13(data):
    """Schema 13: Add Modifier works in the 3D Viewport (any mode), not in every editor. Menus made from it
    that still work everywhere move too; a menu whose Works In was changed by hand keeps it."""
    for p in data.get("pies", []):
        if p.get("preset") == "add_modifier" and p.get("editor") == "Window":
            p["editor"] = "3D View Generic"
    return data


def _migrate_pies_13_to_14(data):
    """Schema 14: the Q Menu drops its Active Modifier submenu, More Modifiers and Shade Auto Smooth, shows
    Display As as one button per choice, gains a Curve section and also opens in curve Edit Mode. Menus made
    from the Q Menu presets are rebuilt from them (key and on/off stay); the old Active Modifier submenu goes.
    The UV Islands pie works only in the UV Editor; Add Objects' Cylinder is Blender's own cylinder."""
    data = _migrate_pies_9_to_10(data)
    for p in data.get("pies", []):
        # the Q UV Islands pie belongs to the UV Editor only (older setups could have it in more editors)
        if p.get("preset") == "uv_islands" and p.get("editor") != "UV Editor":
            p["editor"] = "UV Editor"
        # Add Objects: Cylinder is Blender's own cylinder (with its own redo panel), not a copy of Mod Cylinder's
        if p.get("preset") == "add_objects":
            for it in p.get("items", []):
                if isinstance(it, dict) and it.get("idname") == "keyops.add_mesh" \
                        and it.get("props", "").replace(" ", "") == "mesh_type='CYLINDER'":
                    it["idname"], it["props"] = "mesh.primitive_cylinder_add", ""
        if p.get("preset") in ("q_menu", "q_menu_columns") or (
                str(p.get("preset", "")).startswith("q_") and p.get("owner")):
            if p.get("editor") == "Object Mode, Mesh":
                p["editor"] = "Object Mode, Mesh, Curve"
    data["pies"] = [p for p in data.get("pies", []) if not (isinstance(p, dict) and p.get("preset") == "q_active_modifier")]
    return data


def _migrate_pies_14_to_15(data):
    """Schema 15: the Q Menu's Curve submenu goes; Edges to Curve and Radius sit at the top of the Q Menu when
    they apply. Menus made from the Q Menu presets are rebuilt from them (key and on/off stay)."""
    data = _migrate_pies_9_to_10(data)
    data["pies"] = [p for p in data.get("pies", []) if not (isinstance(p, dict) and p.get("preset") == "q_curve")]
    return data


PIE_MIGRATIONS = {1: _migrate_pies_1_to_2, 2: _migrate_pies_2_to_3, 3: _migrate_pies_3_to_4, 4: _migrate_pies_4_to_5,
                  5: _migrate_pies_5_to_6, 6: _migrate_pies_6_to_7, 7: _migrate_pies_7_to_8, 8: _migrate_pies_8_to_9,
                  9: _migrate_pies_9_to_10, 10: _migrate_pies_10_to_11, 11: _migrate_pies_11_to_12,
                  12: _migrate_pies_12_to_13, 13: _migrate_pies_13_to_14, 14: _migrate_pies_14_to_15}


def load_from_disk():
    """Read pie_menus.json if it exists. Returns True when pies came from the file."""
    global loaded_from_disk
    from . import settings_store
    loaded_from_disk = settings_store.load_section("pie_menus")
    settings_store.load_section("values")
    return loaded_from_disk


def find_pie(uid):
    for pie in get_keyops_prefs().pies:
        if pie.uid == uid:
            return pie
    return None


# ---------------------------------------------------------------- keymaps

_pie_keymaps = []
_VIEWPORT_KEYMAPS = ("Object Mode", "Mesh", "Curve", "3D View Generic")


def _remove_pie_keymaps():
    """Remove our menu shortcuts, skipping any that are already gone (Blender prints an error otherwise)."""
    for km, kmi in _pie_keymaps:
        try:
            if kmi.as_pointer() in {x.as_pointer() for x in km.keymap_items}:
                km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _pie_keymaps.clear()


def pie_keymap_names(pie):
    """The keymaps a menu's key goes into."""
    names = []
    for ed in editor_names(pie):
        for name in (_VIEWPORT_KEYMAPS if ed == "3D View Generic" else (ed,)):
            if name not in names:
                names.append(name)
    return names


def _pie_value(pie):
    return 'PRESS' if pie.menu_type in {"STICKY", "MODAL"} or pie.key_event == "HOLD" else pie.key_event


def _values_clash(a, b):
    """A press fires before a click or drag on the same key, so those clash; a double click doesn't."""
    return a == b or ('PRESS' in (a, b) and 'DOUBLE_CLICK' not in (a, b))


def _kmi_label(kmi):
    name = getattr(kmi.properties, "name", "") if kmi.idname in {"wm.call_menu", "wm.call_menu_pie", "wm.call_panel"} else ""
    cls = getattr(bpy.types, name, None) if name else None
    return (getattr(cls, "bl_label", "") or name) if name else (kmi.name or kmi.idname)


def key_conflicts(pie):
    """(clashes, replaces): other Key Ops menus and shortcuts on the same key where they overlap,
    and Blender's own shortcuts this key takes over."""
    if pie.key in ("", "NONE") or pie.menu_type == "PANEL":
        return [], []
    prefs = get_keyops_prefs()
    mine = set(pie_keymap_names(pie))
    keys = (pie.key, pie.ctrl, pie.shift, pie.alt, pie.key_mod)
    value = _pie_value(pie)
    clashes, replaces = [], []
    for other in prefs.pies:
        if other.uid == pie.uid or not other.enabled or other.menu_type == "PANEL":
            continue
        if (other.key, other.ctrl, other.shift, other.alt, other.key_mod) != keys or not _values_clash(value, _pie_value(other)):
            continue
        theirs = set(pie_keymap_names(other))
        if mine & theirs or "Window" in mine | theirs:
            clashes.append(other.name)
    wm = bpy.context.window_manager
    # an editor's own keys win over window-wide ones (Frames, Window, Screen), so those are replaced too
    look_in = mine | {"Frames", "Window", "Screen"} | ({"3D View"} if "3D View Generic" in mine else set())
    for kc, keyops_only in ((wm.keyconfigs.addon, True), (wm.keyconfigs.user, False)):
        if kc is None:
            continue
        for km in kc.keymaps:
            if km.name not in look_in:
                continue
            for kmi in km.keymap_items:
                if not kmi.active or kmi.idname == "wm.keyops_call_pie" or kmi.type != pie.key:
                    continue
                if not (kmi.any or (bool(kmi.ctrl), bool(kmi.shift), bool(kmi.alt)) == (pie.ctrl, pie.shift, pie.alt)):
                    continue
                if kmi.key_modifier != pie.key_mod or not _values_clash(value, kmi.value):
                    continue
                if kmi.idname.startswith("keyops."):
                    if keyops_only:
                        clashes.append(f"Key Ops: {kmi.name or kmi.idname}")
                elif not keyops_only:
                    text = f"{_kmi_label(kmi)} ({km.name})"
                    if text not in replaces:
                        replaces.append(text)
    return clashes, replaces


_appended = []  # (Blender class, draw function) added with Add To


def _append_draw(uid):
    def draw(self, context):
        pie = find_pie(uid)
        if pie is None or not pie.enabled or not condition_ok(context, pie):
            return
        if not mode_ok(context, pie):
            return
        layout = self.layout
        if pie.append_as == "ITEMS":
            for i, item in enumerate(pie.items):
                if not _is_empty(item):
                    draw_item(layout, context, item, uid, i, slider=pie.menu_type in {"DIALOG", "PANEL"})
        else:
            op = layout.operator("wm.keyops_call_pie", text=pie.name, **icon_kw(TYPE_ICON.get(pie.menu_type, 'NONE')))
            op.pie, op.direct = uid, True
    return draw


def _remove_appends():
    for cls, fn in _appended:
        try:
            cls.remove(fn)
        except Exception:  # noqa: BLE001  the class may be gone already
            pass
    _appended.clear()


def sync_appends():
    _remove_appends()
    prefs = get_keyops_prefs()
    # Before the add-on preferences exist (first enable) get_keyops_prefs() returns a mock whose attributes are False
    for pie in getattr(prefs, "pies", None) or ():
        name = pie.append_to.strip()
        cls = getattr(bpy.types, name, None) if name else None
        if not pie.enabled or cls is None or not hasattr(cls, "append"):
            continue
        fn = _append_draw(pie.uid)
        cls.append(fn)
        _appended.append((cls, fn))


def sync_keymaps():
    _remove_pie_keymaps()
    sync_appends()
    schedule_panel_sync()
    kc = bpy.context.window_manager.keyconfigs.addon
    prefs = get_keyops_prefs()
    if kc is None or not getattr(prefs, "pies_installed", False) or prefs.pause_shortcuts:
        return
    for pie in prefs.pies:
        if not pie.enabled or pie.key in ("", "NONE") or pie.menu_type == "PANEL":
            continue
        # Mode keymaps (Object Mode, Mesh) are checked before "3D View Generic", so a
        # viewport-wide pie also goes into them, or Blender's own Shift A / Ctrl J would win.
        for name in pie_keymap_names(pie):
            km = kc.keymaps.new(name=name, space_type='EMPTY')
            value = 'PRESS' if pie.menu_type in {"STICKY", "MODAL"} or pie.key_event == "HOLD" else pie.key_event
            kmi = km.keymap_items.new("wm.keyops_call_pie", pie.key, value, ctrl=pie.ctrl, shift=pie.shift, alt=pie.alt,
                                      key_modifier=pie.key_mod)
            kmi.properties.pie = pie.uid
            _pie_keymaps.append((km, kmi))
    _changed()  # every structural change ends here, so this keeps pie_menus.json up to date


def live_count():
    """Number of pies that have an active key."""
    return len({kmi.properties.pie for _km, kmi in _pie_keymaps})


# ---------------------------------------------------------------- drawing a pie

def _parse_props(text):
    if not text.strip():
        return {}
    call = ast.parse(f"f({text})", mode="eval").body
    return {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords}


MENU_ICON_SUFFIX = "_menu"  # icons/<name>_menu.png: a darker copy of a coloured icon, used in menu entries
CUSTOM_ICON = "keyops:"  # an item icon "keyops:<name>" is Key Ops' own icons/<name>.png, as the N panel uses
_custom_icons = None


def custom_icon_names():
    """Key Ops' own icons, by name (the PNG files in icons/)."""
    global _custom_icons
    if _custom_icons is None:
        import os
        folder = os.path.normpath(icons_directory)
        _custom_icons = sorted(f[:-4] for f in os.listdir(folder) if f.endswith(".png")) if os.path.isdir(folder) else []
    return _custom_icons


def _icon(name):
    if name.startswith(CUSTOM_ICON):
        return name if name[len(CUSTOM_ICON):] in custom_icon_names() else 'NONE'
    return name if name in _ICONS else 'NONE'


def palette_icon_names():
    """Key Ops' own icons offered in the icon palette (not the darker menu copies, see icon_kw)."""
    return [n for n in custom_icon_names() if not n.endswith(MENU_ICON_SUFFIX)]


_sidebar_depth = 0  # above 0 while a sidebar panel made from a menu draws


def icon_kw(name):
    """The icon argument for a layout call: icon=<Blender icon>, or icon_value for one of Key Ops' own."""
    name = _icon(name) if name else 'NONE'
    if name.startswith(CUSTOM_ICON):
        own = name[len(CUSTOM_ICON):]
        # its darker copy: bright colours don't shout in a menu. Sidebar panels keep the bright icon, as Key Ops' own panel does
        if not _sidebar_depth and own + MENU_ICON_SUFFIX in custom_icon_names():
            own += MENU_ICON_SUFFIX
        return {"icon_value": get_icon(own)}
    return {"icon": name}


def enum_icon(name):
    """The icon of an enum item: a Blender icon name, or the icon id of one of Key Ops' own."""
    kw = icon_kw(name)
    return kw.get("icon_value", kw.get("icon"))


# Menus that have a mode-specific version, as Blender's own Shift A does
_MODE_MENUS = {("VIEW3D_MT_add", "EDIT_MESH"): "VIEW3D_MT_mesh_add"}
# Pie items Key Ops 0.2 only drew in Object Mode; elsewhere the items after them move up a slot
_OBJECT_MODE_ONLY = {"keyops.make_single_user"}


def _menu_for_mode(context, name):
    return _MODE_MENUS.get((name, context.mode), name)


def _styled(layout, item):
    """A sub-layout carrying the item's button look: height, width, emboss, alert and active.
    (Depress is set on the button itself, see _press.)"""
    h, w = getattr(item, "height", 1.0), getattr(item, "width", 1.0)
    if h == 1.0 and w == 1.0 and getattr(item, "emboss", True) and not getattr(item, "alert", False) \
            and getattr(item, "active", True) and getattr(item, "enabled", True) \
            and not getattr(item, "decorate", False):
        return layout
    sub = layout.row(align=True) if w != 1.0 else layout.column(align=True)
    sub.scale_y, sub.scale_x = h, w
    if not item.emboss:
        sub.emboss = 'NONE'
    sub.alert = item.alert
    sub.active = getattr(item, "active", True)
    sub.enabled = getattr(item, "enabled", True)
    if getattr(item, "decorate", False) and item.kind == P:
        sub.use_property_decorate = True
    return sub


def _press(item):
    """Keyword arguments for an operator button: drawn pressed in when the item says so."""
    return {"depress": True} if getattr(item, "depress", False) else {}


def action_name(item):
    """A readable name for what an item does (for an item without a label): the Key Ops action's name,
    the operator's or menu's name in Blender, else its id."""
    idname, props = item.idname.strip(), item.props.strip()
    if item.kind == SUB:
        target = find_pie(idname)
        return target.name if target else idname
    if item.kind == SCRIPT:
        return "Python"
    if item.kind == DRAW:
        return "Draw Code"
    if item.kind == MACRO:
        return "Macro"
    name = _catalog_name(idname, props)
    if name:
        return name
    if item.kind == M or item.kind == PANEL_ITEM:
        cls = getattr(bpy.types, idname, None)
        return getattr(cls, "bl_label", "") or idname
    if item.kind == P:  # Blender's own name for the setting
        try:
            data, prop = _resolve(bpy.context, idname)
            return data.bl_rna.properties[prop].name or prop
        except Exception:  # noqa: BLE001
            return idname.rsplit(".", 1)[-1].replace("_", " ").title()
    if "." in idname and item.kind == O:
        return _operator_name(idname)
    return idname


def _catalog_name(idname, props):
    """The Key Ops catalog's name for this command (an exact options match first), or ""."""
    for entry in _CATALOG:
        if entry[4] == idname and entry[5].strip() == props and entry[2]:
            return entry[2]
    for entry in _CATALOG:
        if entry[4] == idname and entry[2]:
            return entry[2]
    return ""


def _operator_name(idname):
    """Blender's own name for an operator id like mesh.select_all."""
    mod, op = idname.split(".", 1)
    try:
        return getattr(getattr(bpy.ops, mod), op).get_rna_type().name or idname
    except Exception:  # noqa: BLE001
        return op.replace("_", " ").title()


def step_name(step):
    """A readable name for one macro step: the Key Ops action or Blender operator it runs."""
    idname = step.idname.strip()
    if not idname:
        return ""
    return _catalog_name(idname, step.props.strip()) or (_operator_name(idname) if "." in idname else idname)


def item_text(item, default):
    """The text a button shows: its label. No label and an icon: only the icon. No label and no icon: the
    default (the action's own name), so a button is never blank."""
    if not item.label.strip() and item.icon:
        return ""
    return default


def item_icon(item, default='NONE'):
    """The button's icon. No icon picked: none (or the default some kinds of item bring along)."""
    return _icon(item.icon) if item.icon else default


def draw_separator(layout, item):
    """A separator with its style and size. The type argument (line/space) is new in Blender 4.2."""
    if item.sep_type == "SPACER":
        layout.separator_spacer()
        return
    try:
        layout.separator(factor=item.sep_factor, type=item.sep_type)
    except TypeError:
        layout.separator(factor=item.sep_factor)


def setting_rna(item, context=None):
    """(Blender's property, its value) for a setting item, or None when it can't be found here."""
    try:
        data, prop = _resolve(context or bpy.context, item.idname)
        return data.bl_rna.properties[prop], getattr(data, prop)
    except Exception:  # noqa: BLE001  a setting that isn't there right now (no active object, a typo)
        return None


def popup_menu_look(item, context=None):
    """How a popup menu draws this item, the one place the real menu and the preview both ask:
    'SUBMENU' (opens on hover, with an arrow), 'CHECKBOX', 'FIELD' ("Label: value"), 'ICONS' or 'BUTTON'."""
    if item.kind == SUB:
        target = find_pie(item.idname)
        return "SUBMENU" if target is not None and target.menu_type == "MENU" and not needs_panel_popup(target.items) \
            else "BUTTON"
    if item.kind == M:
        style = getattr(item, "menu_style", "AUTO")
        return "SUBMENU" if style in ("AUTO", "SUBMENU") and hasattr(bpy.types, item.idname.strip()) else "BUTTON"
    if item.kind != P or not item.idname.strip():
        return "BUTTON"
    style = getattr(item, "setting_style", "AUTO")
    if _parse_props(item.props).get("view") == "ICONS" or style == "ICONS":
        return "ICONS"
    if style in TEMPLATE_STYLES:  # searches, lists and editors draw as themselves, not as a menu row
        return "FIELD"
    if style in ("VALUE", "TABS", "POPOVER"):
        return "BUTTON"
    found = setting_rna(item, context)
    if found is None:
        return "BUTTON"
    rna = found[0]
    if rna.type == 'ENUM' and not rna.is_enum_flag:
        return "SUBMENU"  # also when set to Expanded: expanded buttons overlap in a popup menu
    if rna.type == 'BOOLEAN' and not getattr(rna, "array_length", 0):
        return "CHECKBOX"
    return "FIELD"


class _PanelHost:
    """Stands in for a panel while its draw() runs into another layout: `layout` is ours, every other
    attribute (class settings, helper methods) comes from the panel's class."""

    def __init__(self, cls, layout):
        object.__setattr__(self, "_cls", cls)
        object.__setattr__(self, "layout", layout)

    def __getattr__(self, name):
        value = getattr(self._cls, name)
        if callable(value) and not isinstance(value, type) and hasattr(value, "__get__"):
            return value.__get__(self, type(self))  # a method: bound to this stand-in
        return value

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)


def draw_panel(panel, layout, context, header=False):
    """Draw Code's draw_panel("SOME_PT_name"): any registered panel's own draw() (and with header=True its
    header too), drawn into this layout. How a whole add-on panel, lists and all, goes into your own."""
    cls = getattr(bpy.types, panel, None) if isinstance(panel, str) else panel
    if cls is None or not hasattr(cls, "draw"):
        layout.label(text=f"{panel}: panel not found", icon='ERROR')
        return False
    poll = getattr(cls, "poll", None)
    if poll is not None and not poll(context):
        return False
    host = _PanelHost(cls, layout)
    if header:
        row = layout.row(align=True)
        for fn in ("draw_header", "draw_header_preset"):
            if hasattr(cls, fn):
                object.__setattr__(host, "layout", row)
                getattr(cls, fn)(host, context)
        object.__setattr__(host, "layout", layout)
    cls.draw(host, context)
    return True


_draw_code_cache = {}  # source -> compiled code, or the SyntaxError it gave
_draw_code_errors = set()


def draw_code(layout, context, item, owner=""):
    """A Draw Code item: its Python runs on every redraw with the layout to draw into, like an add-on's
    draw(). Errors are drawn in place (and printed once), so one bad line never breaks the menu."""
    src = item.script
    if not src.strip():
        return
    code = _draw_code_cache.get(src)
    if code is None:
        try:
            code = compile(src, f"<Key Ops draw code: {item.label or 'Draw Code'}>", "exec")
        except SyntaxError as e:
            code = e
        if len(_draw_code_cache) > 256:
            _draw_code_cache.clear()
        _draw_code_cache[src] = code
    err = code if isinstance(code, SyntaxError) else None
    if err is None:
        names = {"bpy": bpy, "C": context, "context": context, "D": bpy.data, "layout": layout,
                 "icon": icon_kw, "values": values_by_name(context), "__name__": "keyops_draw_code",
                 "draw_panel": lambda panel, into=None, header=False: draw_panel(panel, into or layout, context,
                                                                                 header)}
        try:
            exec(code, names)
        except Exception as e:  # noqa: BLE001  the person's own code
            err = e
    if err is not None:
        msg = f"{type(err).__name__}: {err}"
        layout.label(text=f"{item.label or 'Draw Code'}: {msg}", icon='ERROR')
        if (owner, src, msg) not in _draw_code_errors:
            _draw_code_errors.add((owner, src, msg))
            print(f"Key Ops: the draw code '{item.label or 'Draw Code'}' failed: {msg}")


_inline_drawing = []  # uids of the inline groups drawing right now: a group that contains itself stops there


def inline_target(item):
    """The menu an item draws in place as a group (Key Ops Menu drawn as Group), or None."""
    if item.kind != SUB or getattr(item, "sub_style", "OPEN") != "INLINE":
        return None
    return find_pie(item.idname)


def _draw_inline_group(layout, context, item, target):
    """A Key Ops Menu drawn as a group: its items in a box, column, row, split or grid, right here. In a pie
    it takes one direction (its own sub-layout), which is how add-on pies put several buttons in one slot."""
    if target.uid in _inline_drawing:
        layout.label(text=f"{target.name}: contains itself", icon='ERROR')
        return
    host = layout.column()  # one sub-layout: one pie direction, whatever the group draws inside
    g = make_group(host, item, f"keyops_{target.uid}_inline")
    if g is None:
        return
    _inline_drawing.append(target.uid)
    try:
        draw_columns(g, context, list(target.items), target.uid)
    finally:
        _inline_drawing.pop()


def _draw_menu_item(layout, context, item, label):
    """A Menu item: a hover submenu in popup menus (like Blender's own), a dropdown, the menu's items drawn
    inline, or a button that opens it."""
    name = _menu_for_mode(context, item.idname)
    style = getattr(item, "menu_style", "AUTO")
    known = hasattr(bpy.types, name)
    if style == "INLINE" and known and hasattr(layout, "menu_contents"):  # Blender 4.1+
        layout.menu_contents(name)
        return
    if known and (style == "SUBMENU" or (style == "AUTO" and _popup_menu_depth)):
        layout.menu(name, text=item_text(item, label), **icon_kw(item_icon(item)))
        return
    layout.operator("wm.call_menu", text=item_text(item, label),
                    **icon_kw(item_icon(item)), **_press(item)).name = name


def _list_active(data, prop):
    """(owner, name) of the setting holding a collection's selected row, guessed the way Blender names them:
    object.material_slots -> object.active_material_index, object.vertex_groups -> vertex_groups.active_index."""
    base = prop[:-6] if prop.endswith("_slots") else prop.rstrip("s")
    for owner, name in ((data, f"active_{base}_index"), (data, f"active_{prop}_index"),
                        (getattr(data, prop, None), "active_index")):
        if owner is not None and hasattr(owner, "bl_rna") and name in owner.bl_rna.properties \
                and owner.bl_rna.properties[name].type == 'INT':
            return owner, name
    return None


def _draw_setting_template(layout, context, item, data, prop, style, opts, named, pie_uid, index):
    """A setting drawn with one of Blender's templates or special buttons: search field, list, data-block
    selector, tabs, one option, dropdown, icon picker, color wheel, ramp, curve or palette."""
    src = getattr(item, "source", "").strip()
    icon = icon_kw(item_icon(item))
    text = item_text(item, item.label or data.bl_rna.properties[prop].name)
    if style == "MENU":
        layout.prop_menu_enum(data, prop, text=text, icon=icon.get("icon", 'NONE'))
    elif style == "TABS":
        layout.prop_tabs_enum(data, prop)
    elif style == "VALUE":
        if not src:
            layout.label(text=f"{text}: set Option", icon='ERROR')
            return
        layout.prop_enum(data, prop, src, **named, **icon)
    elif style == "POPOVER":
        if not src or not hasattr(bpy.types, src):
            layout.label(text=f"{text}: set Panel", icon='ERROR')
            return
        layout.prop_with_popover(data, prop, text=text, panel=src, **icon)
    elif style == "ICONS":
        layout.template_icon_view(data, prop, show_labels=bool(opts.get("show_labels", True)),
                                  scale=float(opts.get("scale", 3.5)), scale_popup=float(opts.get("scale_popup", 4)))
    elif style == "SEARCH":
        if not src:
            layout.label(text=f"{text}: set Search In", icon='ERROR')
            return
        sdata, sprop = _resolve(context, src)
        layout.prop_search(data, prop, sdata, sprop, text=text, **icon)
    elif style == "LIST":
        found = _resolve(context, src) if src else _list_active(data, prop)
        if found is None:
            layout.label(text=f"{text}: set Active Index", icon='ERROR')
            return
        if item.label.strip():
            layout.label(text=item.label, **icon)
        layout.template_list("UI_UL_list", f"keyops_{pie_uid}_{index}", data, prop, found[0], found[1],
                             rows=int(opts.get("rows", 4)))
    elif style == "ID":
        if item.label.strip():
            layout.label(text=item.label, **icon)
        layout.template_ID(data, prop, new=src)
    else:  # COLOR, RAMP, CURVE, PALETTE: Blender's editors for those
        if item.label.strip():
            layout.label(text=item.label, **icon)
        if style == "COLOR":
            layout.template_color_picker(data, prop, value_slider=True)
        elif style == "RAMP":
            layout.template_color_ramp(data, prop, expand=True)
        elif style == "CURVE":
            layout.template_curve_mapping(data, prop)
        else:
            layout.template_palette(data, prop, color=True)


def draw_item(layout, context, item, pie_uid="", index=-1, slider=False):
    if item.kind in (BREAK, BOX, BOX_END):  # columns and boxes are made by draw_columns; anywhere else a gap
        layout.separator()
        return
    if item.kind == LABEL:
        layout.label(text=item_text(item, item.label), **icon_kw(item_icon(item)))
        return
    layout = _styled(layout, item)
    if item.kind == SUB:
        target = find_pie(item.idname)
        if target is None:
            layout.separator()
            return
        if getattr(item, "sub_style", "OPEN") == "INLINE":
            _draw_inline_group(layout, context, item, target)
            return
        if _popup_menu_depth and popup_menu_look(item) == "SUBMENU":
            # inside a popup menu, another popup menu opens as a real submenu on hover, like Blender's own
            layout.context_pointer_set("keyops_submenu", target)
            layout.menu(KEYOPS_MT_pie_submenu.bl_idname, text=item_text(item, item.label or target.name),
                        **icon_kw(item_icon(item)))
            return
        layout.operator("wm.keyops_call_pie", text=item_text(item, item.label or target.name),
                        **icon_kw(item_icon(item, TYPE_ICON.get(target.menu_type, 'NONE'))), **_press(item)).pie = target.uid
        return
    if item.kind == DRAW:
        draw_code(layout, context, item, pie_uid)
        return
    if item.kind == SCRIPT:
        if not item.script.strip():
            layout.separator()
            return
        op = layout.operator("wm.keyops_run_script", text=item_text(item, item.label or "Python"),
                             **icon_kw(item_icon(item, 'SCRIPT')), **_press(item))
        op.pie, op.slot = pie_uid, index
        return
    if item.kind == PANEL_ITEM:
        if not item.idname.strip() or not hasattr(bpy.types, item.idname.strip()):
            layout.label(text=f"{item.label or item.idname} (panel not found)", icon='ERROR')
            return
        # no label: the panel's own name, as the preview shows it
        layout.popover(panel=item.idname.strip(), text=item_text(item, item.label or action_name(item)),
                       **icon_kw(item_icon(item)))
        return
    if item.kind == MACRO:
        if not item.steps:
            layout.separator()
            return
        op = layout.operator("wm.keyops_run_macro", text=item_text(item, item.label or "Macro"), **icon_kw(item_icon(item)),
                             **_press(item))
        op.pie, op.slot = pie_uid, index
        return
    if item.kind == N or not item.idname.strip():
        draw_separator(layout, item)
        return
    label = item.label or action_name(item)
    try:
        if item.kind == M:
            _draw_menu_item(layout, context, item, label)
        elif item.kind == P:
            data, prop = _resolve(context, item.idname)
            opts = _parse_props(item.props)
            # no label: Blender's own name for the setting
            named = {"text": item_text(item, item.label)} if item.label or item_text(item, "x") == "" else {}
            style = getattr(item, "setting_style", "AUTO")
            if style in TEMPLATE_STYLES or style in ("MENU", "TABS", "VALUE", "ICONS", "POPOVER"):
                _draw_setting_template(layout, context, item, data, prop, style, opts, named, pie_uid, index)
                return
            if item.index >= 0:  # one value of an array setting (X of a location, one layer of a mask)
                named["index"] = item.index
            if item.invert:
                named["invert_checkbox"] = True
            if _popup_menu_depth and popup_menu_look(item) == "SUBMENU":
                # in a popup menu, a choice opens its choices as a submenu on hover, like Blender's own menus.
                # Drawn as a field it shows as "Label: value", which pushes the rows after it out of line,
                # and expanded its buttons overlap
                rna = data.bl_rna.properties[prop]
                layout.prop_menu_enum(data, prop, text=item_text(item, item.label or rna.name),
                                      icon=icon_kw(item_icon(item)).get("icon", 'NONE'))
                return
            if opts.get("view") == "ICONS":  # a big icon picker, like the studio light one in Blender's menus
                layout.template_icon_view(data, prop, show_labels=bool(opts.get("show_labels", True)),
                                          scale=float(opts.get("scale", 3.5)), scale_popup=float(opts.get("scale_popup", 4)))
            elif style == "EXPAND":
                layout.row(align=True).prop(data, prop, expand=True, **icon_kw(item_icon(item)), **named)
            elif style == "SLIDER":
                layout.prop(data, prop, slider=True, **icon_kw(item_icon(item)), **named)
            elif style == "CHECKBOX":  # Blender draws a setting with an icon as a button, so no icon here
                layout.prop(data, prop, toggle=False, **named)
            elif style == "BUTTON" or not slider:
                layout.prop(data, prop, toggle=True, **icon_kw(item_icon(item)), **named)
            else:  # dialogs and panels show settings as real fields and sliders
                layout.prop(data, prop, **icon_kw(item_icon(item)), **named)
        else:
            mode = getattr(item, "call_mode", "DEFAULT")
            before = layout.operator_context
            if mode != "DEFAULT":  # the button keeps the context it was made with
                layout.operator_context = mode
            style, enum_prop = getattr(item, "op_style", "BUTTON"), getattr(item, "enum_prop", "").strip()
            try:
                if style == "EXPAND" and enum_prop:
                    # one button per value; Blender gives these no text or icon of their own
                    layout.operator_enum(item.idname.strip(), enum_prop)
                    return
                if style == "MENU" and enum_prop:
                    layout.operator_menu_enum(item.idname.strip(), enum_prop, text=item_text(item, label),
                                              **icon_kw(item_icon(item)))
                    return
                op = layout.operator(item.idname.strip(), text=item_text(item, label), **icon_kw(item_icon(item)),
                                     **_press(item))
            finally:
                layout.operator_context = before
            for name, value in _parse_props(item.props).items():
                setattr(op, name, value)
    except Exception:
        layout.label(text=f"{label} (check command)", icon='ERROR')


def slot_name(i):
    """A pie item's place: its direction, or Extra n for the items after the 8 directions."""
    return POSITION_NAMES[ORDER[i]] if i < PIE_SLOTS else f"Extra {i - PIE_SLOTS + 1}"


def pie_extras(context, items):
    """The indices of a pie's extra items (after its 8 directions) shown here."""
    return [i for i in range(PIE_SLOTS, len(items)) if not _is_empty(items[i]) and item_visible(context, items[i])
            and not (context.mode != 'OBJECT' and items[i].idname.strip() in _OBJECT_MODE_ONLY)]


def pie_slots(context, items):
    """(direction, item index) for the items a pie shows here, in Blender's slot order
    (left, right, bottom, top, then the corners). Skipped items move the later ones up a slot."""
    shown = [i for i, item in enumerate(items[:8])
             if not (context.mode != 'OBJECT' and item.idname.strip() in _OBJECT_MODE_ONLY)
             and item_visible(context, item)]
    return list(zip(ORDER, shown))


def draw_pie_items(layout, context, items, pie_uid):
    """The eight slots of a pie, drawn by Blender."""
    extras = pie_extras(context, items)

    def draw_extras(col):
        box = col.box().column(align=True)
        for x in extras:
            draw_item(box, context, items[x], pie_uid, x)

    slots = pie_slots(context, items)
    for direction, i in slots:
        item = items[i]
        if direction == "N" and extras:  # the extra items: a column on top of the pie's top item
            col = layout.column()
            draw_extras(col)
            draw_item(col, context, item, pie_uid, i)
            continue
        # Blender gives a pie's labels no direction (the items after them would move up a slot): in a
        # sub-layout of its own a label keeps the slot the editor shows it in
        draw_item(layout.column() if item.kind == LABEL else layout, context, item, pie_uid, i)
    if extras and not any(d == "N" for d, _i in slots):  # no top item here: they take the next direction
        draw_extras(layout.column())


_stack_state = {}  # menu id -> (next index, time of last press)


def _resolve(context, path):
    path = path.strip()
    if path.startswith("values:"):  # one of your own values: values:Size
        v = context.window_manager.keyops_values.get(path[len("values:"):].strip())
        if v is None:
            raise KeyError(path)
        return v, v.field
    if "[" not in path and not path.startswith(("bpy.", "D.", "C.")):  # the common case, kept fast
        *parts, prop = path.split(".")
        data = context
        for part in parts:
            data = getattr(data, part)
        return data, prop
    # bpy.data.materials, D.objects, C.object, scene.transform_orientation_slots[0].type, modifiers["Bevel"].width
    tokens = _PATH_TOKEN.findall(path)
    if not tokens or "".join(t[0] for t in tokens) != path or not tokens[-1][1]:
        raise ValueError(f"not a setting path: {path}")
    steps = [(t[1], t[2]) for t in tokens]
    data = context
    first = steps[0][0]
    if first == "bpy" and len(steps) > 1 and steps[1][0] == "data":
        data, steps = bpy.data, steps[2:]
    elif first == "bpy" and len(steps) > 1 and steps[1][0] == "context":
        steps = steps[2:]
    elif first == "D":
        data, steps = bpy.data, steps[1:]
    elif first == "C":
        steps = steps[1:]
    for name, key in steps[:-1]:
        if name:
            data = getattr(data, name)
        else:
            data = data[int(key)] if key.lstrip("-").isdigit() else data[key.strip("\"'")]
    return data, steps[-1][0]


_PATH_TOKEN = re.compile(r"""(\.?([A-Za-z_]\w*)|\[(-?\d+|"[^"]*"|'[^']*')\])""")


def run_item(context, pie, index):
    """Do what an item does, outside of a menu (stack, sticky and modal keys)."""
    item = pie.items[index]
    if _is_empty(item) or item.kind in (LABEL,) + LAYOUT_KINDS:
        return
    if item.kind == MACRO:
        bpy.ops.wm.keyops_run_macro(pie=pie.uid, slot=index)
    elif item.kind == SUB:
        bpy.ops.wm.keyops_call_pie('INVOKE_DEFAULT', pie=item.idname)
    elif item.kind == SCRIPT:
        run_script(context, item.script, item.label)
    elif item.kind == PANEL_ITEM:
        bpy.ops.wm.call_panel(name=item.idname.strip())
    elif item.kind == M:
        bpy.ops.wm.call_menu(name=_menu_for_mode(context, item.idname))
    elif item.kind == P:
        data, prop = _resolve(context, item.idname)
        if isinstance(getattr(data, prop), bool):
            setattr(data, prop, not getattr(data, prop))
    else:  # invoked, like a key press, unless the item says Execute
        _run_step(item.idname, item.props, not getattr(item, "call_mode", "DEFAULT").startswith("EXEC"))


_MODE_KEYMAPS = {
    'OBJECT': "Object Mode", 'EDIT_MESH': "Mesh", 'EDIT_CURVE': "Curve", 'EDIT_SURFACE': "Curve", 'EDIT_CURVES': "Curves",
    'EDIT_TEXT': "Font", 'EDIT_ARMATURE': "Armature", 'EDIT_METABALL': "Metaball", 'EDIT_LATTICE': "Lattice",
    'POSE': "Pose", 'SCULPT': "Sculpt", 'PAINT_WEIGHT': "Weight Paint", 'PAINT_VERTEX': "Vertex Paint",
    'PAINT_TEXTURE': "Image Paint", 'PARTICLE': "Particle"}
_AREA_KEYMAPS = {
    'VIEW_3D': ("3D View", "3D View Generic"), 'IMAGE_EDITOR': ("UV Editor", "Image", "Image Generic"),
    'NODE_EDITOR': ("Node Editor", "Node Generic"), 'GRAPH_EDITOR': ("Graph Editor", "Graph Editor Generic"),
    'DOPESHEET_EDITOR': ("Dopesheet", "Dopesheet Generic"), 'NLA_EDITOR': ("NLA Editor", "NLA Generic"),
    'OUTLINER': ("Outliner",), 'PROPERTIES': ("Property Editor",), 'SEQUENCE_EDITOR': ("Sequencer", "SequencerCommon"),
    'TEXT_EDITOR': ("Text", "Text Generic")}


def _keymap_chain(context):
    """The keymaps Blender checks for a key press here, most specific first (close enough for a tap)."""
    area = context.area.type if context.area else ""
    names = []
    if area == 'VIEW_3D' and context.mode in _MODE_KEYMAPS:
        names.append(_MODE_KEYMAPS[context.mode])
    names += list(_AREA_KEYMAPS.get(area, ())) + ["Frames", "Window", "Screen"]
    return names


def find_blender_key(context, key, ctrl, shift, alt):
    """The shortcut Blender (or another add-on) would run for this key here, skipping Key Ops menus."""
    kc = context.window_manager.keyconfigs.user
    for name in _keymap_chain(context):
        km = kc.keymaps.get(name)
        if km is None:
            continue
        for kmi in km.keymap_items:
            if not kmi.active or kmi.type != key or kmi.idname == "wm.keyops_call_pie" or kmi.key_modifier != 'NONE':
                continue
            if kmi.value not in {'PRESS', 'CLICK', 'ANY'}:
                continue
            if kmi.any or (bool(kmi.ctrl) == ctrl and bool(kmi.shift) == shift and bool(kmi.alt) == alt and not kmi.oskey):
                return kmi
    return None


def run_keymap_item(kmi):
    mod, name = kmi.idname.split(".", 1)
    props = {}
    for prop in kmi.properties.bl_rna.properties:
        pid = prop.identifier
        if pid == "rna_type" or prop.type in {'POINTER', 'COLLECTION'} or not kmi.properties.is_property_set(pid):
            continue
        value = getattr(kmi.properties, pid)
        props[pid] = value if not hasattr(value, "__len__") or isinstance(value, (str, set)) else tuple(value)
    getattr(getattr(bpy.ops, mod), name)('INVOKE_DEFAULT', **props)


_condition_errors = set()


_CMP = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b, ast.Lt: lambda a, b: a < b,
        ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
        ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
        ast.Is: lambda a, b: a is b, ast.IsNot: lambda a, b: a is not b}


def _test_names(context):
    obj = getattr(context, "active_object", None)
    return {"C": context, "context": context, "obj": obj,
            "space": getattr(context, "space_data", None), "scene": getattr(context, "scene", None),
            "tool": getattr(getattr(context, "scene", None), "tool_settings", None), "mode": context.mode,
            # mods: the active object's modifier types, e.g. 'BOOLEAN' in mods
            "mods": tuple(m.type for m in getattr(obj, "modifiers", ())),
            # sel: how many objects are selected, e.g. sel > 1
            "sel": len(getattr(context, "selected_objects", None) or ()),
            # values: My Properties by name, e.g. values["Detail"] == 'HIGH'
            "values": values_by_name(context),
            "True": True, "False": False, "None": None}


def _test_value(node, names):
    """Reads one part of a test. Only settings, comparisons, and/or/not and plain values: nothing is run."""
    if isinstance(node, ast.Expression):
        return _test_value(node.body, names)
    if isinstance(node, ast.BoolOp):
        values = (_test_value(v, names) for v in node.values)
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _test_value(node.operand, names)
    if isinstance(node, ast.Compare):
        left = _test_value(node.left, names)
        for op, right_node in zip(node.ops, node.comparators):
            right = _test_value(right_node, names)
            if type(op) not in _CMP or not _CMP[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Constant):
        return node.value
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len"
            and len(node.args) == 1 and not node.keywords):  # len() is the one call a test may make
        value = _test_value(node.args[0], names)
        return 0 if value is None else len(value)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return tuple(_test_value(e, names) for e in node.elts)
    if isinstance(node, ast.Subscript):  # values["Name"], or an item of a list
        base = _test_value(node.value, names)
        key = _test_value(node.slice, names)
        if isinstance(base, dict):
            return base.get(key)
        return None if base is None else base[key]
    if isinstance(node, ast.Name):
        if node.id not in names:
            raise NameError(f"'{node.id}' is not known here (use C, obj, space, scene, tool, mode, mods, sel or values)")
        return names[node.id]
    if isinstance(node, ast.Attribute):
        if node.attr.startswith("_"):
            raise AttributeError(node.attr)
        base = _test_value(node.value, names)
        return None if base is None else getattr(base, node.attr)
    raise ValueError(f"'{ast.unparse(node)}' can't be used in a test")


def safe_test(code, context):
    """Show When / Show If: a test on settings, e.g. space.shading.type == 'SOLID' or obj and obj.type == 'MESH'.
    Read with a small reader of its own, never run as Python."""
    return bool(_test_value(ast.parse(code, mode="eval"), _test_names(context)))


def _tested(context, key, code, name):
    if not code.strip():
        return True
    try:
        return safe_test(code, context)
    except Exception as e:  # noqa: BLE001  the person's own test
        if (key, code) not in _condition_errors:
            _condition_errors.add((key, code))
            print(f"Key Ops: the test of '{name}' failed and is ignored: {e}")
        return True


def _in_editor(context, editor):
    """Is the mouse in this EDITORS entry right now? Blender's keymaps are looser than
    their names: the UV Editor keymap also runs outside UV editing, for example."""
    area = context.area.type if context.area else ""
    if editor == "UV Editor":
        space = context.space_data
        return area == 'IMAGE_EDITOR' and context.mode == 'EDIT_MESH' and getattr(space, "mode", "") == 'UV'
    if editor == "Mesh":
        return area == 'VIEW_3D' and context.mode == 'EDIT_MESH'
    if editor == "Curve":
        return area == 'VIEW_3D' and context.mode in ('EDIT_CURVE', 'EDIT_SURFACE')
    return True  # the other keymaps only run in their own editor


def works_here(context, pie):
    """True when the menu's Works In list includes the editor the key was pressed in."""
    return any(_in_editor(context, editor) for editor in editor_names(pie))


def condition_ok(context, pie):
    """A menu's Show When test. Empty means always; a broken test is reported once and ignored."""
    return _tested(context, pie.uid, pie.condition, pie.name)


# ---- Preview In: the preview in Custom Menus shows the menu as it looks in a chosen mode (items whose Poll is
# false there are hidden), handy for big menus with many items that only show sometimes
PREVIEW_MODES = (
    ('EDITING', "Every Item", "Show every item, whatever its Poll says (for editing)", 'PREFERENCES', 0),
    ('CURRENT', "As Now", "Test each Poll against Blender as it is now (mode, selection, active object)", 'TIME', 1),
    ('OBJECT', "Object Mode", "", 'OBJECT_DATAMODE', 2),
    ('EDIT_MESH', "Edit Mesh", "", 'EDITMODE_HLT', 3),
    ('EDIT_CURVE', "Edit Curve", "", 'OUTLINER_DATA_CURVE', 4),
    ('SCULPT', "Sculpt Mode", "", 'SCULPTMODE_HLT', 5),
    ('PAINT_WEIGHT', "Weight Paint", "", 'WPAINT_HLT', 6),
    ('PAINT_VERTEX', "Vertex Paint", "", 'VPAINT_HLT', 7),
    ('PAINT_TEXTURE', "Texture Paint", "", 'TPAINT_HLT', 8),
    ('EDIT_ARMATURE', "Edit Armature", "", 'ARMATURE_DATA', 9),
    ('POSE', "Pose Mode", "", 'POSE_HLT', 10),
)


def _redraw_all_areas(self, context):
    for win in context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()


class _PreviewContext:
    """Blender's context with another mode, for testing Polls in the preview."""
    def __init__(self, context, mode):
        self._ctx, self.mode = context, mode

    def __getattr__(self, name):
        return getattr(self._ctx, name)


def preview_hidden(item, owner=""):
    """True when the preview's Preview In mode hides this item (its Poll is false there)."""
    wm = bpy.context.window_manager
    mode = getattr(wm, "keyops_preview_mode", 'EDITING')
    if mode == 'EDITING' or not getattr(item, "show_if", "").strip():
        return False
    ctx = bpy.context if mode == 'CURRENT' else _PreviewContext(bpy.context, mode)
    return not item_visible(ctx, item, owner)


class KEYOPS_PT_menu_preview_mode(bpy.types.Panel):
    bl_label = "Preview In"
    bl_space_type = 'TOPBAR'
    bl_region_type = 'HEADER'
    bl_options = {'INSTANCED'}
    bl_ui_units_x = 10

    def draw(self, context):
        layout = self.layout
        layout.label(text="Preview the menu as it shows in")
        col = layout.column(align=True)
        col.prop(context.window_manager, "keyops_preview_mode", expand=True)
        note = layout.column(align=True)
        note.active = False
        note.label(text="Items whose Poll is false there")
        note.label(text="are hidden from the preview")


def item_visible(context, item, owner=""):
    """An item's Show If test (empty: always shown)."""
    return _tested(context, f"{owner}:{item.label}", getattr(item, "show_if", ""), item.label or item.idname)


def shown_items(context, items, owner=""):
    """The (index, item) pairs to draw. A group whose Show If is false hides everything in it, up to its
    End Group (or the next column), so its items don't spill into the group around it."""
    shown, i, n = [], 0, len(items)
    while i < n:
        it = items[i]
        if getattr(it, "in_header", False) and it.kind not in LAYOUT_KINDS:
            i += 1  # drawn in the sidebar panel's header instead
        elif item_visible(context, it, owner):
            shown.append((i, it))
            i += 1
        elif it.kind == BOX:
            end = group_end(items, i)
            if end is None:  # runs to the next column (kept, it starts the column) or to the end
                end = next((j - 1 for j in range(i + 1, n) if items[j].kind == BREAK), n - 1)
            i = end + 1
        else:
            i += 1
    return shown


def open_held_menu(uid):
    bpy.ops.wm.keyops_call_pie('INVOKE_DEFAULT', pie=uid, direct=True)


def run_tapped_key(context, key, ctrl, shift, alt):
    """A Hold key was only tapped: do what the key normally does."""
    kmi = find_blender_key(context, key, ctrl, shift, alt)
    if kmi is not None:
        try:
            run_keymap_item(kmi)
        except Exception as e:  # noqa: BLE001  the other shortcut may not run here
            print(f"Key Ops: tap fallback {kmi.idname} failed: {e}")


class WM_OT_keyops_call_pie(Operator):
    bl_idname = "wm.keyops_call_pie"
    bl_label = "Key Ops Menu"
    bl_description = "Open a Key Ops menu"
    bl_options = {'INTERNAL'}

    pie: StringProperty() # type: ignore
    direct: BoolProperty(options={'SKIP_SAVE', 'HIDDEN'}) # type: ignore  # open now, skipping Hold

    def invoke(self, context, event):
        pie = find_pie(self.pie)
        if pie is None:
            return {'CANCELLED'}
        if not mode_ok(context, pie):
            return {'PASS_THROUGH'}  # let Blender's own key do its thing here
        if not self.direct and not editor_ok(context, pie):
            return {'PASS_THROUGH'}  # a key shared with another editor: only where the menu works
        if not self.direct and not (works_here(context, pie) and condition_ok(context, pie)):
            return {'PASS_THROUGH'}
        self._hold = None
        marking = pie.menu_type == "PIE" and getattr(get_keyops_prefs(), "pie_style", "BLENDER") == "MARKING"
        # Marking menus open on the press itself, like Maya: no Hold wait, so a fast flick still picks.
        # A quick tap without moving does what the key normally does instead (see the marking menu).
        if pie.key_event == "HOLD" and not self.direct and not marking \
                and pie.menu_type not in {"STICKY", "MODAL", "PANEL"} and event.type == pie.key:
            self._hold = (event.type, event.ctrl, event.shift, event.alt, time.time())
            self._timer = context.window_manager.event_timer_add(0.02, window=context.window)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        items = list(pie.items)
        uid = pie.uid
        kind = pie.menu_type
        self._uid = uid

        if kind == "MENU" and needs_panel_popup(items):
            # Blender's popup menus can't draw rows, sizes or boxes: open the same items as a popup panel
            n = 1 + sum(1 for it in items if it.kind == BREAK)
            return context.window_manager.invoke_popup(self, width=200 * n)

        if kind == "MENU":
            def draw_menu(menu, ctx):
                # settings as checkboxes, like Blender's own menus; Next Column items make columns
                draw_popup_menu(menu.layout, ctx, items, uid)
            context.window_manager.popup_menu(draw_menu, title=pie.name)
            return {'FINISHED'}

        if kind in {"DIALOG", "PANEL"}:
            width = 180 * max(1, pie.columns)
            if pie.dialog_mode == "DIALOG" and kind == "DIALOG":
                return context.window_manager.invoke_props_dialog(self, width=width, title=pie.name, confirm_text="Close")
            return context.window_manager.invoke_popup(self, width=width)

        if kind == "STACK":
            return self._run_stack(context, pie)

        if kind in RUN_TYPES:
            return self._run_all(pie)

        if kind == "STICKY":
            self._key = event.type
            self._restore = None
            first = items[0]
            if first.kind == P and first.idname.strip():
                data, prop = _resolve(context, first.idname)
                if isinstance(getattr(data, prop), bool):
                    self._restore = (data, prop, getattr(data, prop))  # changed only while held
            run_item(context, pie, 0)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        if kind == "MODAL":
            item = items[0] if items else None
            if item is None or item.kind != P or not item.idname.strip():
                self.report({'WARNING'}, f"{pie.name}: pick a setting to change")
                return {'CANCELLED'}
            self._data, self._prop = _resolve(context, item.idname)
            self._start = getattr(self._data, self._prop)
            if not isinstance(self._start, (int, float)) or isinstance(self._start, bool):
                self.report({'WARNING'}, f"{pie.name}: the setting must be a number")
                return {'CANCELLED'}
            opts = _parse_props(item.props)
            self._step = float(opts.get("step", 0.1 if isinstance(self._start, float) else 1))
            self._min, self._max = opts.get("min"), opts.get("max")
            self._x0 = event.mouse_x
            self._offset = 0.0
            self._label = item.label or self._prop.replace("_", " ").title()
            context.window_manager.modal_handler_add(self)
            self._show(context)
            return {'RUNNING_MODAL'}

        if getattr(get_keyops_prefs(), "pie_style", "BLENDER") == "MARKING":
            # the key to watch for release: the pie's key when a key opened it, else whatever was pressed (Try It)
            key = pie.key if event.type == pie.key or event.type.startswith("TIMER") or event.type == 'NONE' else event.type
            tap_key = pie.key_event == "HOLD" and not self.direct and event.type == pie.key
            bpy.ops.wm.keyops_marking_menu('INVOKE_DEFAULT', pie=uid, key=key, tap_key=tap_key)
            return {'FINISHED'}

        def draw(menu, ctx):
            draw_pie_items(menu.layout.menu_pie(), ctx, items, uid)

        context.window_manager.popup_menu_pie(event, draw, title=pie.name)
        return {'FINISHED'}

    # ---- dialog / popup panel
    def draw(self, context):
        pie = find_pie(self.pie)
        if pie is None:
            return
        layout = self.layout
        if pie.menu_type == "MENU" or pie.menu_type == "DIALOG" and pie.dialog_mode == "POPUP":
            layout.label(text=pie.name)
        if pie.menu_type == "MENU":
            draw_columns(layout, context, list(pie.items), pie.uid)
            return
        draw_grid(layout, context, pie)

    def execute(self, context):
        # Called from a script (no key press): stack keys still step, other menus need invoke.
        pie = find_pie(self.pie)
        if pie is None:
            return {'CANCELLED'}
        if not mode_ok(context, pie):
            return {'PASS_THROUGH'}
        if pie.menu_type == "STACK":
            return self._run_stack(context, pie)
        if pie.menu_type in RUN_TYPES:
            return self._run_all(pie)
        return {'FINISHED'}

    def _run_all(self, pie):
        """Macro Operator: run every item in order, stopping at the first that fails."""
        context = bpy.context  # fresh after each step: an earlier step may change the mode
        ran = 0
        for i, item in enumerate(pie.items):
            if _is_empty(item):
                continue
            try:
                run_item(context, pie, i)
            except Exception as e:  # noqa: BLE001  report it like Blender would, and stop
                name = item.label or item.idname or f"step {i + 1}"
                self.report({'WARNING'}, f"{pie.name} stopped at {name}: {str(e).splitlines()[0]}")
                return {'FINISHED'} if ran else {'CANCELLED'}
            ran += 1
        if not ran:
            self.report({'WARNING'}, f"{pie.name}: pick what it runs first")
            return {'CANCELLED'}
        return {'FINISHED'}

    def _run_stack(self, context, pie):
        uid, items = pie.uid, list(pie.items)
        now = time.time()
        idx, last = _stack_state.get(uid, (0, 0.0))
        if pie.stack_reset and now - last > pie.stack_reset:
            idx = 0
        filled = [i for i, it in enumerate(items) if not _is_empty(it)]
        if not filled:
            return {'CANCELLED'}
        target = filled[idx % len(filled)]
        _stack_state[uid] = ((idx + 1) % len(filled), now)
        run_item(context, pie, target)
        self.report({'INFO'}, f"{pie.name}: {items[target].label or items[target].idname}")
        return {'FINISHED'}

    # ---- sticky / modal
    def _value(self):
        v = self._start + self._offset
        if self._min is not None:
            v = max(self._min, v)
        if self._max is not None:
            v = min(self._max, v)
        return int(round(v)) if isinstance(self._start, int) else v

    def _show(self, context):
        v = self._value()
        text = f"{self._label}: {v:.3f}" if isinstance(v, float) else f"{self._label}: {v}"
        if context.area:
            context.area.header_text_set(text)
        if context.workspace:
            def status(header, ctx):
                row = header.layout.row(align=False)
                for icons, label in ((('MOUSE_MOVE',), "Change"), (('MOUSE_MMB_SCROLL',), "Step"),
                                     (('MOUSE_LMB',), "Confirm"), (('EVENT_ESC', 'MOUSE_RMB'), "Cancel")):
                    for icon in icons[:-1]:
                        row.label(text="", icon=_safe_icon(icon))
                    row.label(text=label, icon=_safe_icon(icons[-1]))
                    row.separator(factor=1.5)
            context.workspace.status_text_set(status)

    @staticmethod
    def _clear(context):
        if context.area:
            context.area.header_text_set(None)
        if context.workspace:
            context.workspace.status_text_set(None)

    def _modal_hold(self, context, event):
        key, ctrl, shift, alt, start = self._hold
        released = event.type == key and event.value == 'RELEASE'
        held = event.type == 'TIMER' and time.time() - start >= HOLD_TIME
        if not (released or held):
            return {'PASS_THROUGH'} if event.type != key else {'RUNNING_MODAL'}
        context.window_manager.event_timer_remove(self._timer)
        self._hold = None
        if held:
            open_held_menu(self.pie)
        else:
            run_tapped_key(context, key, ctrl, shift, alt)
        return {'FINISHED'}

    def modal(self, context, event):
        pie = find_pie(self.pie)
        if pie is None:
            return {'CANCELLED'}
        if getattr(self, "_hold", None):
            return self._modal_hold(context, event)
        if pie.menu_type == "STICKY":
            if event.type == self._key and event.value == 'RELEASE':
                if self._restore is not None:
                    data, prop, value = self._restore
                    setattr(data, prop, value)
                if len(pie.items) > 1:
                    run_item(context, pie, 1)
                return {'FINISHED'}
            return {'PASS_THROUGH'}
        # modal value
        if event.type == 'MOUSEMOVE':
            self._offset = round((event.mouse_x - self._x0) / 20) * self._step
        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            self._x0 -= 20 if event.type == 'WHEELUPMOUSE' else -20
            self._offset = round((event.mouse_x - self._x0) / 20) * self._step
        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
            self._clear(context)
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            setattr(self._data, self._prop, self._start)
            self._clear(context)
            return {'CANCELLED'}
        else:
            return {'RUNNING_MODAL'}
        try:
            setattr(self._data, self._prop, self._value())
        except (TypeError, ValueError, AttributeError):
            pass
        self._show(context)
        return {'RUNNING_MODAL'}


def _split_columns(layout, n):
    """n equal columns made with splits, the way Blender's own menus lay out columns."""
    cols, cur = [], layout
    for k in range(n - 1):
        cur = cur.split(factor=1.0 / (n - k))
        cols.append(cur.column())
    cols.append(cur.column())
    return cols


def layout_groups(items):
    """Split items into columns (by Next Column) of blocks: ("BOX", index, [runs]) or ("RUN", [(i, item)]).
    A run is the items drawn in one row: an item with Same Row joins the one before it."""
    columns = [[]]
    box = None
    for i, it in items:
        if it.kind == BREAK:
            if columns[-1]:  # no empty columns, e.g. when Show If hid everything before this
                columns.append([])
            box = None
            continue
        if it.kind == BOX:
            box = ("BOX", i, [])
            columns[-1].append(box)
            continue
        if it.kind == BOX_END:
            box = None
            continue
        target = box[2] if box else columns[-1]
        last = target[-1] if target else None
        if it.same_row and last is not None and last[0] == "RUN":
            last[1].append((i, it))
        else:
            target.append(("RUN", [(i, it)]))
    return columns


def group_end(items, start):
    """Index of the End Group closing the group that starts at `start` (None if it runs to the end)."""
    depth = 0
    for i in range(start, len(items)):
        k = items[i].kind
        if k == BOX:
            depth += 1
        elif k == BOX_END:
            depth -= 1
            if depth == 0:
                return i
        elif k == BREAK and i > start:
            return None  # a column ends every open group
    return None


def items_can_share_row(pie, index):
    """Whether an item can have others beside it on its row ("Same Row"): not in a row, split or grid
    group, which lay items side by side already."""
    if pie is None or pie.menu_type == "PIE" or not 0 <= index < len(pie.items):
        return False
    items = list(pie.items)
    parent = parent_group(items, index)
    return parent is None or items[parent].group_type in ("BOX", "COLUMN", "PANEL")


def pie_items_kind(pie, index):
    return pie.items[index].kind if pie is not None and 0 <= index < len(pie.items) else ""


def parent_group(items, index):
    """Start index of the innermost group the item at `index` is in, or None."""
    stack = []
    for i in range(min(index, len(items))):
        k = items[i].kind
        if k == BOX:
            stack.append(i)
        elif k == BOX_END and stack:
            stack.pop()
        elif k == BREAK:
            stack.clear()
    return stack[-1] if stack else None


def layout_tree(items, shown):
    """Columns (split by Next Column) of nested nodes: ["ITEM", i], ["RUN", [i, ...]] (Same Row items) or
    ["GROUP", i, children, end index]. `shown` is the (index, item) pairs to lay out."""
    columns = [[]]
    stack = [columns[-1]]
    groups = []
    for i, it in shown:
        if it.kind == BREAK:
            if columns[-1]:  # no empty columns, e.g. when Show If hid everything before this
                columns.append([])
            stack, groups = [columns[-1]], []
            continue
        if it.kind == BOX:
            node = ["GROUP", i, [], None]
            stack[-1].append(node)
            stack.append(node[2])
            groups.append(node)
            continue
        if it.kind == BOX_END:
            if groups:
                groups.pop()[3] = i
                stack.pop()
            continue
        target = stack[-1]
        last = target[-1] if target else None
        parent = items[groups[-1][1]].group_type if groups else "COLUMN"
        if it.same_row and last is not None and last[0] in ("ITEM", "RUN") and parent in ("COLUMN", "BOX", "PANEL"):
            if last[0] == "ITEM":
                target[-1] = ["RUN", [last[1], i]]
            else:
                last[1].append(i)
        else:
            target.append(["ITEM", i])
    return columns


def make_group(parent, head, idname="keyops_group"):
    """The Blender layout a group item makes: a box, row, column, split, grid flow or panel with its look.
    Returns None for a closed panel (nothing to draw in it)."""
    t = getattr(head, "group_type", "BOX")
    label = head.label.strip()
    if t == "PANEL" and hasattr(parent, "panel"):  # Blender 4.1+
        header, body = parent.panel(idname, default_closed=head.closed)
        header.label(text=label or "Panel", **icon_kw(item_icon(head)))
        if body is None:
            return None
        g = body.column(align=head.align)
    elif t in ("BOX", "PANEL"):
        box = parent.box()
        if label:
            box.label(text=label, **icon_kw(item_icon(head)))
        g = box.column(align=head.align)
    else:
        if label:
            parent.label(text=label, **icon_kw(item_icon(head)))
        if t == "ROW":
            g = parent.row(align=head.align)
        elif t == "SPLIT":
            g = parent.split(factor=head.factor, align=head.align)
        elif t == "GRID":
            g = parent.grid_flow(row_major=True, columns=head.grid_columns, even_columns=True, even_rows=False,
                                 align=head.align)
        else:
            g = parent.column(align=head.align)
    g.alignment = head.alignment
    g.scale_x, g.scale_y = head.width, head.height
    if not head.emboss:
        g.emboss = 'NONE'
    g.alert = head.alert
    g.active = head.active
    g.enabled = head.enabled
    g.use_property_split = head.prop_split
    if head.prop_split:  # Blender's Properties editor: split settings without the keyframe column unless asked
        g.use_property_decorate = head.decorate
    return g


def draw_nodes(layout, context, items, nodes, uid, slider=True):
    for node in nodes:
        if node[0] == "ITEM":
            draw_item(layout, context, items[node[1]], uid, node[1], slider=slider)
        elif node[0] == "RUN":
            row = layout.row(align=True)
            for i in node[1]:
                draw_item(row, context, items[i], uid, i, slider=slider)
        else:
            g = make_group(layout, items[node[1]], f"keyops_{uid}_{node[1]}")
            if g is not None:
                draw_nodes(g, context, items, node[2], uid, slider)


_popup_menu_depth = 0  # above 0 while a popup menu draws: its Key Ops Menu items become real submenus


def draw_popup_menu(layout, context, items, uid):
    """A popup menu's items, with other popup menus as submenus that open on hover."""
    global _popup_menu_depth
    _popup_menu_depth += 1
    # Blender's popup menus execute their buttons by default, which skips invoke: modal tools such as
    # Boolean Scroll or Fast Bevel never start. Its own menus invoke in the editor under the mouse.
    layout.operator_context = 'INVOKE_REGION_WIN'
    try:
        draw_columns(layout, context, items, uid)
    finally:
        _popup_menu_depth -= 1


class KEYOPS_MT_pie_submenu(bpy.types.Menu):
    """One of your popup menus shown as a submenu (the menu comes from the button's context)."""
    bl_idname = "KEYOPS_MT_pie_submenu"
    bl_label = "Key Ops Menu"

    def draw(self, context):
        pie = getattr(context, "keyops_submenu", None)
        if pie is None:
            self.layout.label(text="Menu not found", icon='ERROR')
            return
        draw_popup_menu(self.layout, context, list(pie.items), pie.uid)


def needs_panel_popup(items):
    """A popup menu whose items use rows, sizes or boxes: Blender's menus can't draw those."""
    return any(it.kind in (BOX, BOX_END) or it.same_row or it.height != 1.0 or it.width != 1.0
               or (it.kind == P and it.setting_style in PANEL_ONLY_STYLES)
               or (inline_target(it) is not None and it.group_type != "COLUMN") for it in items)


def _has_layout(items):
    return any(it.kind in LAYOUT_KINDS or getattr(it, "same_row", False) for it in items)


def _draw_run(layout, context, run, uid, slider):
    if len(run) == 1:
        i, it = run[0]
        draw_item(layout, context, it, uid, i, slider=slider)
        return
    row = layout.row(align=True)
    for i, it in run:
        draw_item(row, context, it, uid, i, slider=slider)


def draw_columns(layout, context, items, uid, slider=True):
    """Items in one column, or in several split by Next Column items, with boxes and rows.
    Settings drawn as real fields. (Popup menus with rows or boxes open as popup panels, see
    needs_panel_popup: Blender's menus can't draw those.)"""
    shown = shown_items(context, items, uid)
    columns = layout_tree(items, shown)
    cols = _split_columns(layout, len(columns)) if len(columns) > 1 else [layout.column()]
    for col, nodes in zip(cols, columns):
        draw_nodes(col, context, items, nodes, uid, slider)
    return True


def draw_grid(layout, context, pie):
    """Dialogs and sidebar panels: items in columns, settings as real fields. With Next Column, boxes or
    Same Row items the layout is exactly as set; without them the items fill the Columns row by row."""
    shown = shown_items(context, list(pie.items), pie.uid)
    if _has_layout([it for _i, it in shown]):
        draw_columns(layout, context, list(pie.items), pie.uid)
        return
    grid = layout.grid_flow(row_major=True, columns=max(1, pie.columns), even_columns=True, align=False)
    for i, item in shown:
        draw_item(grid, context, item, pie.uid, i, slider=True)


# ---------------------------------------------------------------- your own sidebar panels
# Every Sidebar Panel menu is a real panel of its own, in the tab you name, in each editor it works in.
PANEL_SPACES = (("VIEW_3D", {"3D View Generic", "Object Mode", "Mesh", "Sculpt", "Weight Paint", "Window"}),
                ("IMAGE_EDITOR", {"UV Editor", "Image", "Window"}),
                ("NODE_EDITOR", {"Node Editor", "Window"}))
_user_panels = []        # the panel classes made from your menus
_panel_signature = None  # what they were made from, so they're only remade when that changes


def _user_panel_class(pie, space, n, parent=""):
    uid = pie.uid

    def poll(cls, context):
        p = find_pie(uid)
        return p is not None and p.enabled and mode_ok(context, p) \
            and condition_ok(context, p)

    def draw(self, context):
        global _sidebar_depth
        p = find_pie(uid)
        if p is not None:
            _sidebar_depth += 1
            try:
                draw_grid(self.layout, context, p)
            finally:
                _sidebar_depth -= 1

    def draw_header(self, context):
        p = find_pie(uid)
        if p is not None and p.panel_icon.strip():
            global _sidebar_depth
            _sidebar_depth += 1
            try:
                self.layout.label(text="", **icon_kw(p.panel_icon.strip()))
            finally:
                _sidebar_depth -= 1

    def draw_header_preset(self, context):
        p = find_pie(uid)
        if p is None:
            return
        items = list(p.items)
        shown = [(i, it) for i, it in enumerate(items) if it.in_header and it.kind not in LAYOUT_KINDS
                 and item_visible(context, it, uid)]
        if not shown:
            return
        global _sidebar_depth
        _sidebar_depth += 1
        try:
            row = self.layout.row(align=True)
            for i, it in shown:
                draw_item(row, context, it, uid, i, slider=True)
        finally:
            _sidebar_depth -= 1

    name = f"KEYOPS_PT_user_{n}_{space.lower()}"
    attrs = {"bl_idname": name, "bl_label": pie.name or "Panel", "bl_space_type": space, "bl_region_type": 'UI',
             "bl_category": (pie.tab or "Toolkit").strip() or "Toolkit", "poll": classmethod(poll), "draw": draw,
             "draw_header": draw_header, "draw_header_preset": draw_header_preset,
             "bl_order": pie.panel_order}
    options = set()
    if pie.panel_hide_header:
        options.add('HIDE_HEADER')
    if pie.panel_closed:
        options.add('DEFAULT_CLOSED')
    if options:
        attrs["bl_options"] = options
    if parent:
        attrs["bl_parent_id"] = parent
    return type(name, (bpy.types.Panel,), attrs)


def sync_user_panels():
    """Make (or remake) a sidebar panel for every Sidebar Panel menu."""
    global _panel_signature
    prefs = get_keyops_prefs()
    pies = [p for p in (getattr(prefs, "pies", None) or ()) if p.menu_type == "PANEL"]
    sig = tuple((p.uid, p.name, p.tab, tuple(sorted(editor_names(p))), p.panel_hide_header, p.panel_closed,
                 p.panel_order, p.panel_parent.strip()) for p in pies)
    if sig == _panel_signature:
        return
    remove_user_panels()
    _panel_signature = sig
    number = {p.uid: n for n, p in enumerate(pies)}
    made = set()  # (uid, space) of the panels registered so far: a sub-panel needs its parent first
    pending = list(pies)
    while pending:
        later = []
        for pie in pending:
            parent_uid = pie.panel_parent.strip()
            if parent_uid == pie.uid or parent_uid not in number or _parent_loops(pies, pie):
                parent_uid = ""  # no such panel, or a loop: a panel of its own
            if parent_uid and not any((parent_uid, s) in made for s, _e in PANEL_SPACES) \
                    and any(q.uid == parent_uid for q in pending if q is not pie):
                later.append(pie)  # its parent isn't made yet
                continue
            names = set(editor_names(pie))
            for space, editors in PANEL_SPACES:
                if not names & editors:
                    continue
                parent = ""
                if parent_uid:
                    if (parent_uid, space) not in made:
                        continue  # the parent isn't in this editor: a sub-panel can't be there either
                    parent = f"KEYOPS_PT_user_{number[parent_uid]}_{space.lower()}"
                cls = _user_panel_class(pie, space, number[pie.uid], parent)
                try:
                    bpy.utils.register_class(cls)
                    _user_panels.append(cls)
                    made.add((pie.uid, space))
                except (RuntimeError, ValueError):
                    pass
        if len(later) == len(pending):  # nothing could be placed: give up on the rest
            break
        pending = later


def _parent_loops(pies, pie):
    """Whether following Inside from this panel comes back round to it."""
    by_uid = {p.uid: p for p in pies}
    seen, cur = {pie.uid}, by_uid.get(pie.panel_parent.strip())
    while cur is not None:
        if cur.uid in seen:
            return True
        seen.add(cur.uid)
        cur = by_uid.get(cur.panel_parent.strip())
    return False


def remove_user_panels():
    global _panel_signature
    while _user_panels:
        cls = _user_panels.pop()
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    _panel_signature = None


def schedule_panel_sync():
    """Panels can't be registered from inside a property update: do it right after."""
    if not bpy.app.timers.is_registered(_panel_sync_timer):
        bpy.app.timers.register(_panel_sync_timer, first_interval=0.05)


def _panel_sync_timer():
    try:
        sync_user_panels()
    except Exception:  # noqa: BLE001  never break over a panel
        pass
    return None



def parse_command(text):
    """'bpy.ops.mesh.primitive_monkey_add(size=2)' (as shown in Blender's Info editor) -> (idname, options)."""
    text = text.strip()
    if text.startswith("bpy.ops."):
        text = text[len("bpy.ops."):]
    try:
        node = ast.parse(text, mode="eval").body
    except SyntaxError:
        return None
    if isinstance(node, ast.Call):
        func, args = node.func, node.keywords
    else:
        func, args = node, []
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    parts.reverse()
    if len(parts) != 2:
        return None
    opts = ", ".join(f"{kw.arg}={ast.unparse(kw.value)}" for kw in args if kw.arg)
    return ".".join(parts), opts


def _run_step(idname, props, interactive):
    mod, op = idname.strip().split(".", 1)
    fn = getattr(getattr(bpy.ops, mod), op)
    return fn('INVOKE_DEFAULT' if interactive else 'EXEC_DEFAULT', **_parse_props(props))


def run_script(context, code, name=""):
    """Run Python the same way Blender's Text Editor does (Text > Run Script).
    The script goes into a temporary text block that is removed again afterwards."""
    text = bpy.data.texts.new(".Key Ops Script")
    try:
        text.from_string(code)
        with context.temp_override(edit_text=text):
            bpy.ops.text.run_script()
    finally:
        bpy.data.texts.remove(text)


class WM_OT_keyops_run_script(Operator):
    bl_idname = "wm.keyops_run_script"
    bl_label = "Run Python"
    bl_description = "Run this item's Python, the way the Text Editor runs a script"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    pie: StringProperty() # type: ignore
    slot: IntProperty() # type: ignore

    def execute(self, context):
        pie = find_pie(self.pie)
        if pie is None or not (0 <= self.slot < len(pie.items)):
            return {'CANCELLED'}
        item = pie.items[self.slot]
        try:
            run_script(context, item.script, item.label)
        except Exception as e:
            lines = [ln.strip() for ln in str(e).splitlines() if ln.strip() and not ln.strip().startswith("Location:")]
            errs = [ln for ln in lines if ln.split(":")[0].endswith(("Error", "Exception"))]
            msg = (errs or lines or [type(e).__name__])[-1]
            self.report({'WARNING'}, f"{item.label or 'Python'}: {msg}  (see the console for details)")
            return {'CANCELLED'}
        return {'FINISHED'}


class KEYOPS_OT_script_edit(Operator):
    bl_idname = "keyops.script_edit"
    bl_label = "Edit in Text Editor"
    bl_description = "Open this item's Python in Blender's Text Editor. Press Save to Item when you're done"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        item = _active_item(prefs, prefs.pie_slot)
        if item is None:
            return {'CANCELLED'}
        name = f"Key Ops - {_active_pie(prefs).name} - {item.label or 'Python'}"
        text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
        text.from_string(item.script or "import bpy\n\n")
        context.window_manager.keyops_script_text = name
        try:
            bpy.ops.wm.window_new()
        except RuntimeError:  # no window to open one from: the text is ready in any Text Editor
            self.report({'INFO'}, f"Edit \"{name}\" in a Text Editor")
            return {'FINISHED'}
        win = context.window_manager.windows[-1]
        area = win.screen.areas[0]
        area.type = 'TEXT_EDITOR'
        area.spaces.active.text = text
        return {'FINISHED'}


class KEYOPS_OT_script_save(Operator):
    bl_idname = "keyops.script_save"
    bl_label = "Save to Item"
    bl_description = "Copy the script from the Text Editor back into this item"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        item = _active_item(prefs, prefs.pie_slot)
        text = bpy.data.texts.get(context.window_manager.keyops_script_text)
        if item is None or text is None:
            self.report({'WARNING'}, "Open the script in the Text Editor first")
            return {'CANCELLED'}
        item.script = text.as_string()
        self.report({'INFO'}, "Saved the script to the item")
        return {'FINISHED'}


class WM_OT_keyops_run_macro(Operator):
    bl_idname = "wm.keyops_run_macro"
    bl_label = "Run Macro"
    bl_description = "Run this macro's steps one after another"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    pie: StringProperty() # type: ignore
    slot: IntProperty() # type: ignore

    def execute(self, context):
        pie = find_pie(self.pie)
        if pie is None or not (0 <= self.slot < len(pie.items)):
            return {'CANCELLED'}
        for n, step in enumerate(pie.items[self.slot].steps, 1):
            if not step.idname.strip():
                continue
            try:
                result = _run_step(step.idname, step.props, step.interactive)
            except Exception as e:
                self.report({'WARNING'}, f"Macro stopped at step {n} ({step.idname}): {str(e).splitlines()[0]}")
                return {'CANCELLED'} if n == 1 else {'FINISHED'}
            if 'CANCELLED' in result and not step.interactive:
                self.report({'WARNING'}, f"Macro stopped at step {n} ({step.idname}): it could not run here")
                return {'FINISHED'} if n > 1 else {'CANCELLED'}
        return {'FINISHED'}


# ---------------------------------------------------------------- editing operators

class KEYOPS_OT_pie_select(Operator):
    bl_idname = "keyops.pie_select"
    bl_label = "Edit Pie"
    bl_description = "Edit this menu"
    bl_options = {'INTERNAL'}
    index: IntProperty() # type: ignore

    def execute(self, context):
        get_keyops_prefs().active_pie = self.index
        return {'FINISHED'}


class KEYOPS_OT_pie_add(Operator):
    bl_idname = "keyops.pie_add"
    bl_label = "New Pie"
    bl_description = "Make a new empty menu"
    bl_options = {'INTERNAL'}
    preset: StringProperty(options={'SKIP_SAVE'}) # type: ignore
    menu_type: StringProperty(default="PIE", options={'SKIP_SAVE'}) # type: ignore

    @classmethod
    def description(cls, context, props):
        preset = PRESET_BY_ID.get(props.preset)
        if preset:
            text = f"{_preset_key_text(preset)}: {_preset_summary(preset, limit=8)}"
            if any(p.preset == preset["id"] for p in get_keyops_prefs().pies):
                text += ".\nAlready in your list. Adding it again makes a second copy"
            return text
        return next((desc for tid, _n, desc, _i, _x in MENU_TYPES if tid == props.menu_type), cls.bl_description)

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _new_pie(prefs)
        if self.preset in PRESET_BY_ID:
            _fill(pie, PRESET_BY_ID[self.preset])
            if self.preset in MAYA_PRESETS and prefs.pie_style != "MARKING":
                prefs.pie_style = "MARKING"  # Maya's marking menus only work as marking menus
                self.report({'INFO'}, "Pie menus now use the Marking style, for Maya's marking menus")
        elif self.menu_type != "PIE":
            names = {"MENU": "My Menu", "DIALOG": "My Dialog", "PANEL": "My Panel", "STACK": "My Stack Key",
                     "STICKY": "My Sticky Key", "MODAL": "My Modal Value", "MACRO_OP": "My Macro"}
            pie.name = names.get(self.menu_type, "My Menu")
            pie.menu_type = self.menu_type
            pie["enabled"] = self.menu_type == "PANEL"  # panels need no key
            for _i in range({"DIALOG": 4, "PANEL": 4, "STACK": 2, "STICKY": 2, "MACRO_OP": 2}.get(self.menu_type, 1)):
                it = pie.items.add()
                it.kind = P if self.menu_type == "MODAL" else O  # empty buttons, ready to pick operators for
        else:
            pie.name = "My Pie"
            pie["enabled"] = False  # enable once it has a key and items
            for _i in ORDER:
                pie.items.add()
        prefs.active_pie = len(prefs.pies) - 1
        sync_keymaps()
        return {'FINISHED'}


def _active_pie(prefs):
    return prefs.pies[max(0, min(prefs.active_pie, len(prefs.pies) - 1))] if prefs.pies else None


class KEYOPS_OT_menu_item_add(Operator):
    bl_idname = "keyops.menu_item_add"
    bl_label = "Add Item"
    bl_description = "Add an item to this menu (a pie: an extra item, beyond its 8 directions)"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _active_pie(prefs)
        if pie is None or len(pie.items) >= ITEM_LIMIT.get(pie.menu_type, LIST_LIMIT):
            return {'CANCELLED'}
        pie.items.add()
        prefs.pie_slot = len(pie.items) - 1
        _changed()
        return {'FINISHED'}


class KEYOPS_OT_menu_item_remove(Operator):
    bl_idname = "keyops.menu_item_remove"
    bl_label = "Remove Item"
    bl_description = "Remove this item from the menu"
    bl_options = {'INTERNAL'}
    slot: IntProperty(default=-1, options={'SKIP_SAVE'}) # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _active_pie(prefs)
        if self.slot >= 0:
            prefs.pie_slot = self.slot
        if pie is None or not (0 <= prefs.pie_slot < len(pie.items)) or len(pie.items) <= ITEM_MIN.get(pie.menu_type, 0):
            return {'CANCELLED'}
        if pie.menu_type == "PIE" and prefs.pie_slot < PIE_SLOTS:
            return {'CANCELLED'}  # a direction: emptied, not removed (see Clear)
        if pie.items[prefs.pie_slot].kind == BOX:  # a group: its End Group goes too, its items stay
            end = group_end(list(pie.items), prefs.pie_slot)
            if end is not None:
                pie.items.remove(end)
        pie.items.remove(prefs.pie_slot)
        prefs.pie_slot = max(0, prefs.pie_slot - 1)
        _changed()
        return {'FINISHED'}


class KEYOPS_OT_component_mode(Operator):
    bl_idname = "keyops.component_mode"
    bl_label = "Component Mode"
    bl_description = "Switch to vertex, edge or face selection (entering Edit Mode if needed), or back to Object Mode"
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(items=(("VERT", "Vertex", ""), ("EDGE", "Edge", ""), ("FACE", "Face", ""),
                              ("MULTI", "Multi", "Vertices, edges and faces at once"), ("OBJECT", "Object Mode", ""))) # type: ignore

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        if self.mode == "OBJECT":
            bpy.ops.object.mode_set(mode='OBJECT')
            return {'FINISHED'}
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        context.tool_settings.mesh_select_mode = {
            "VERT": (True, False, False), "EDGE": (False, True, False),
            "FACE": (False, False, True), "MULTI": (True, True, True)}[self.mode]
        return {'FINISHED'}


_item_clipboard = None  # an item copied with Copy, as saved data


_slot_target_cache = []  # Blender keeps pointers to these strings: keep the list alive


def _slot_targets(self, context):
    _slot_target_cache[:] = _slot_target_list()
    return _slot_target_cache


def _slot_target_list():
    prefs = get_keyops_prefs()
    pie = _active_pie(prefs)
    if pie is None:
        return [("NONE", "", "")]
    return [(str(i), f"{slot_name(i)}  ·  {pie.items[i].label or ('Empty' if _is_empty(pie.items[i]) else pie.items[i].idname)}",
             "Swap with this slot") for i in range(len(pie.items)) if i != prefs.pie_slot] or [("NONE", "", "")]


class KEYOPS_OT_slot_swap(Operator):
    bl_idname = "keyops.slot_swap"
    bl_label = "Move to"
    bl_description = "Move this item to another slot. The item there takes this slot"
    bl_options = {'INTERNAL'}
    target: EnumProperty(name="Slot", items=_slot_targets) # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _active_pie(prefs)
        if pie is None or not self.target.isdigit():
            return {'CANCELLED'}
        a, b = prefs.pie_slot, int(self.target)
        if not (0 <= a < len(pie.items) and 0 <= b < len(pie.items)):
            return {'CANCELLED'}
        da, db = _item_to_data(pie.items[a]), _item_to_data(pie.items[b])
        _item_from_data(pie.items[a], db)
        _item_from_data(pie.items[b], da)
        prefs.pie_slot = b
        _changed()
        return {'FINISHED'}


class KEYOPS_OT_slot_copy(Operator):
    bl_idname = "keyops.slot_copy"
    bl_label = "Copy Item"
    bl_description = "Copy this item, to paste it into another slot or menu"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        global _item_clipboard
        prefs = get_keyops_prefs()
        pie = _active_pie(prefs)
        if pie is None or not 0 <= prefs.pie_slot < len(pie.items):
            return {'CANCELLED'}
        _item_clipboard = _item_to_data(pie.items[prefs.pie_slot])
        return {'FINISHED'}


class KEYOPS_OT_slot_paste(Operator):
    bl_idname = "keyops.slot_paste"
    bl_label = "Paste Item"
    bl_description = "Replace this item with the copied one"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return _item_clipboard is not None

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _active_pie(prefs)
        if pie is None or not 0 <= prefs.pie_slot < len(pie.items):
            return {'CANCELLED'}
        _item_from_data(pie.items[prefs.pie_slot], _item_clipboard)
        _changed()
        return {'FINISHED'}


INSERT_KINDS = (
    (O, "Button", "A button: pick what it does", 'RADIOBUT_OFF'),
    (MACRO, "Macro", "A button that runs several operators one after another", 'SEQUENCE'),
    (N, "Separator", "A line between items (popup menus) or a gap", 'REMOVE'),
    (LABEL, "Label", "A heading", 'FONT_DATA'),
) + tuple((f"G:{g}", name, f"A new {name.lower()} group with one item in it. {desc}", icon)
          for g, name, desc, icon, _n in GROUP_TYPES) + (
    (BREAK, "Next Column", "The items after this go in the next column", 'CENTER_ONLY'),
    ("HIDE_UI", "Hide Blender UI", "A button that hides one of Blender's own panels, menus or headers (press it "
                                   "again to show it). Pick which one from a list", 'HIDE_ON'),
)


def _insert_item(pie, pos, kind):
    it = pie.items.add()
    it.kind = kind
    new = len(pie.items) - 1
    if pos < new:
        pie.items.move(new, pos)
    return pie.items[pos]


class KEYOPS_OT_item_wrap(Operator):
    bl_idname = "keyops.item_wrap"
    bl_label = "Wrap In"
    bl_description = "Put this item (or this whole group) in a new box, row, column, split or grid"
    bl_options = {'INTERNAL'}
    slot: IntProperty(default=-1) # type: ignore
    group_type: EnumProperty(items=GROUP_TYPES) # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _active_pie(prefs)
        slot = self.slot if self.slot >= 0 else prefs.pie_slot
        if pie is None or pie.menu_type == "PIE" or not 0 <= slot < len(pie.items) \
                or len(pie.items) + 2 > ITEM_LIMIT.get(pie.menu_type, LIST_LIMIT):
            return {'CANCELLED'}
        end = slot
        if pie.items[slot].kind == BOX:
            end = group_end(list(pie.items), slot)
            if end is None:
                return {'CANCELLED'}
        _insert_item(pie, end + 1, BOX_END).label = "End Group"
        head = _insert_item(pie, slot, BOX)
        head.group_type, head.label = self.group_type, ""
        prefs.pie_slot = slot
        _changed()
        _redraw_all(context)
        return {'FINISHED'}


class KEYOPS_OT_item_ungroup(Operator):
    bl_idname = "keyops.item_ungroup"
    bl_label = "Ungroup"
    bl_description = "Remove this group, keeping its items where they are"
    bl_options = {'INTERNAL'}
    slot: IntProperty(default=-1) # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _active_pie(prefs)
        slot = self.slot if self.slot >= 0 else prefs.pie_slot
        if pie is None or not 0 <= slot < len(pie.items) or pie.items[slot].kind != BOX:
            return {'CANCELLED'}
        end = group_end(list(pie.items), slot)
        if end is not None:
            pie.items.remove(end)
        pie.items.remove(slot)
        prefs.pie_slot = min(slot, len(pie.items) - 1)
        _changed()
        _redraw_all(context)
        return {'FINISHED'}


class KEYOPS_MT_item_wrap(bpy.types.Menu):
    bl_label = "Wrap In"
    bl_idname = "KEYOPS_MT_item_wrap"

    def draw(self, context):
        slot = get_keyops_prefs().pie_slot
        self.layout.operator_context = 'EXEC_DEFAULT'
        for g, name, _desc, icon, _n in GROUP_TYPES:
            op = self.layout.operator("keyops.item_wrap", text=name, icon=icon)
            op.slot, op.group_type = slot, g


class KEYOPS_OT_menu_item_insert(Operator):
    bl_idname = "keyops.menu_item_insert"
    bl_label = "Insert"
    bl_description = "Add an item, a separator, a label, a box or a column right after this one"
    bl_options = {'INTERNAL'}
    slot: IntProperty(default=-1) # type: ignore
    kind: EnumProperty(items=[(k, n, d, i, x) for x, (k, n, d, i) in enumerate(INSERT_KINDS)]) # type: ignore
    at_end: BoolProperty(default=False, options={'SKIP_SAVE'}) # type: ignore

    @classmethod
    def description(cls, context, props):
        return next(d for k, _n, d, _i in INSERT_KINDS if k == props.kind)

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _active_pie(prefs)
        if pie is None or pie.menu_type == "PIE" or len(pie.items) >= ITEM_LIMIT.get(pie.menu_type, LIST_LIMIT):
            return {'CANCELLED'}
        base = len(pie.items) - 1 if self.at_end else (self.slot if self.slot >= 0 else prefs.pie_slot)
        if 0 <= base < len(pie.items) and pie.items[base].kind == BOX and not self.at_end:  # after a whole group
            base = group_end(list(pie.items), base) or base
        pos = min(len(pie.items), base + 1)
        if self.kind.startswith("G:"):
            if len(pie.items) + 3 > ITEM_LIMIT.get(pie.menu_type, LIST_LIMIT):
                return {'CANCELLED'}
            head = _insert_item(pie, pos, BOX)
            head.group_type, head.label = self.kind[2:], ""
            _insert_item(pie, pos + 1, O)  # an empty button inside, to pick an action for
            _insert_item(pie, pos + 2, BOX_END).label = "End Group"
            prefs.pie_slot = pos
            _changed()
            _redraw_all(context)
            return {'FINISHED'}
        if self.kind == "HIDE_UI":  # a button running keyops.toggle_ui_element: pick the element next
            it = _insert_item(pie, pos, O)
            it.idname, it.label, it.icon = "keyops.toggle_ui_element", "Hide Blender UI", 'HIDE_ON'
            prefs.pie_slot = pos
            _changed()
            _redraw_all(context)
            if context.window:
                bpy.ops.keyops.pick_ui_element('INVOKE_DEFAULT', slot=pos)
            return {'FINISHED'}
        it = _insert_item(pie, pos, self.kind)  # a Button starts empty (no action yet)
        it.label = {LABEL: "Heading", BREAK: "Next Column", MACRO: "Macro"}.get(self.kind, "")
        if self.kind == MACRO:
            it.steps.add()  # its first step, to pick an operator for
        prefs.pie_slot = pos
        _changed()
        _redraw_all(context)
        if self.kind == O:  # straight on to picking what it does
            bpy.ops.keyops.pie_slot_search('INVOKE_DEFAULT', slot=pos, scope="ALL")
        elif self.kind == MACRO and context.window:  # straight on to picking its first step
            bpy.ops.keyops.pie_slot_search('INVOKE_DEFAULT', slot=pos, scope="ALL", step=0)
        return {'FINISHED'}


class KEYOPS_MT_item_insert(bpy.types.Menu):
    """What to insert after the item that was right-clicked."""
    bl_label = "New Below"
    bl_idname = "KEYOPS_MT_item_insert"

    def draw(self, context):
        slot = get_keyops_prefs().pie_slot
        self.layout.operator_context = 'EXEC_DEFAULT'
        for kind, name, _desc, icon in INSERT_KINDS:
            op = self.layout.operator("keyops.menu_item_insert", text=name, icon=icon)
            op.slot, op.kind = slot, kind


def draw_item_options(layout, prefs):
    """Everything about one item, for the right-click menu in the preview."""
    pie = _active_pie(prefs)
    item = _active_item(prefs, prefs.pie_slot)
    if pie is None or item is None:
        layout.label(text="No item")
        return
    slot = prefs.pie_slot
    layout.operator_context = 'INVOKE_DEFAULT'
    layouty = item.kind in LAYOUT_KINDS
    empty = _is_empty(item)
    if item.kind not in (BREAK, BOX_END) and not (empty and item.kind == N):
        layout.prop(item, "label", text="", icon='FONT_DATA')  # first, so it opens under the mouse
    if not layouty and item.kind != LABEL:
        op = layout.operator("keyops.pie_slot_search", text="Operator", icon='VIEWZOOM')
        op.slot, op.scope = slot, "ALL"
    if not layouty and not empty:
        _icon_button(layout, item, slot)
    if item.kind == BOX:  # a group: how it lays out its items
        layout.separator()
        layout.prop_menu_enum(item, "group_type", text=f"Layout: {GROUP_NAMES.get(item.group_type, '')}")
        layout.prop(item, "align")
        layout.prop_menu_enum(item, "alignment", text=f"Alignment: {item.alignment.title()}")
        if item.group_type == "SPLIT":
            layout.prop(item, "factor")
        if item.group_type == "GRID":
            layout.prop(item, "grid_columns")
        if item.group_type == "PANEL":
            layout.prop(item, "closed")
        layout.prop(item, "prop_split")
        if not item.label.strip():
            _icon_button(layout, item, slot)
    looks = look_options(pie, item)
    if looks:  # only what Blender can do for this kind of item
        layout.separator()
        for name in ("width", "height", "emboss", "alert", "active", "enabled", "depress", "invert", "decorate",
                     "same_row"):
            if name in looks:
                layout.prop(item, name)
    if item.kind == P:
        layout.prop_menu_enum(item, "setting_style", text="Draw As")
    if empty and item.kind == N and pie.menu_type != "PIE":  # a separator
        layout.prop_menu_enum(item, "sep_type", text=f"Separator: {item.sep_type.title()}")
        layout.prop(item, "sep_factor")
    layout.separator()
    if pie.menu_type != "PIE":
        layout.menu("KEYOPS_MT_item_insert", text="New Below", icon='ADD')
        layout.menu("KEYOPS_MT_item_wrap", text="Wrap In", icon='SELECT_SUBTRACT')
        parent = parent_group(list(pie.items), slot)
        if parent is not None:
            head = pie.items[parent]
            op = layout.operator("keyops.item_options", text=f"Edit Group ({GROUP_NAMES.get(head.group_type, '')})...",
                                 icon='GROUP')
            op.slot = parent
        if item.kind == BOX:
            layout.operator("keyops.item_ungroup", icon='UNLINKED').slot = slot
    if pie.menu_type == "PIE":  # other menus: drag items in the preview to move them
        layout.operator_menu_enum("keyops.slot_swap", "target", text="Swap With", icon='ARROW_LEFTRIGHT')
    layout.operator("keyops.slot_copy", text="Copy", icon='COPYDOWN')
    layout.operator("keyops.slot_paste", text="Paste", icon='PASTEDOWN')
    if (pie.menu_type != "PIE" and len(pie.items) > ITEM_MIN.get(pie.menu_type, 0)) or             (pie.menu_type == "PIE" and slot >= PIE_SLOTS):
        layout.operator("keyops.menu_item_remove", text="Remove", icon='X').slot = slot


# ---------------------------------------------------------------- right-click any button: add it to a menu
_last_button = None  # (kind, idname, props, label) of the button the context menu was opened on


def _context_path(context, ptr):
    """The data path of `ptr` from the context (space_data.overlay, scene.tool_settings, ...), or None."""
    for name in ("space_data", "tool_settings", "scene", "object", "view_layer", "world", "region_data",
                 "area", "region", "preferences", "workspace", "window_manager"):
        base = getattr(context, name, None)
        if base is None:
            continue
        try:
            if base == ptr:
                return name
            r, br = repr(ptr), repr(base)
        except (ReferenceError, TypeError):
            continue
        if r.startswith(br + "."):
            return name + r[len(br):]
    return None


def button_info(context):
    """What the button under the mouse does, as a menu item: (kind, idname, options, label), or None.
    An operator keeps the options it was set up with; a setting is found from the context."""
    op = getattr(context, "button_operator", None)
    if op is not None:
        ident = op.bl_rna.identifier
        if "_OT_" in ident:
            mod, name = ident.split("_OT_", 1)
            opts = []
            for pr in op.bl_rna.properties:
                pid = pr.identifier
                if pid == "rna_type" or pr.type in {'POINTER', 'COLLECTION'} or not op.is_property_set(pid):
                    continue
                value = getattr(op, pid)
                if not isinstance(value, (str, set, int, float, bool)) and hasattr(value, "__len__"):
                    value = tuple(value)
                opts.append(f"{pid}={value!r}")
            return O, f"{mod.lower()}.{name}", ", ".join(opts), op.bl_rna.name
    ptr, prop = getattr(context, "button_pointer", None), getattr(context, "button_prop", None)
    if ptr is not None and prop is not None:
        path = _context_path(context, ptr)
        if path:
            return P, f"{path}.{prop.identifier}", "", prop.name
    return None


def add_button_to(pie, info, position=-1):
    """Put the button (from button_info) in the menu. position -1: a pie's first empty slot, the end of
    anything else. A pie: the slot to put it in (an extra item past the last one). Others: the index it goes in at."""
    kind, idname, opts, label = info
    if pie.menu_type == "PIE":
        if 0 <= position < len(pie.items):
            item = pie.items[position]
        elif position >= len(pie.items) and len(pie.items) < ITEM_LIMIT["PIE"]:
            item = pie.items.add()
        else:
            item = next((it for it in pie.items if _is_empty(it)), None)
        if item is None:
            return None
    else:
        if len(pie.items) >= ITEM_LIMIT.get(pie.menu_type, LIST_LIMIT):
            return None
        if position >= 0:
            pie.items.add()
            new = len(pie.items) - 1
            pos = min(position, new)
            pie.items.move(new, pos)
            item = pie.items[pos]
        else:
            # an empty button waiting for an operator is filled; separators are left alone
            empty = next((it for it in pie.items if it.kind == O and not it.idname.strip()), None)
            item = empty or pie.items.add()
    item.kind, item.idname, item.props, item.label, item.icon = kind, idname, opts, label, ""
    _changed()
    return item


class KEYOPS_OT_add_button_to_menu(Operator):
    bl_idname = "keyops.add_button_to_menu"
    bl_label = "Add to Key Ops Menu"
    bl_description = "Add this button to one of your Key Ops menus"
    bl_options = {'INTERNAL'}
    pie: StringProperty(options={'SKIP_SAVE'}) # type: ignore  # empty: a new menu of new_type
    position: IntProperty(default=-1, options={'SKIP_SAVE'}) # type: ignore  # see add_button_to
    new_type: StringProperty(default="MENU", options={'SKIP_SAVE'}) # type: ignore  # MENU or MACRO_OP

    @classmethod
    def description(cls, context, props):
        if not props.pie and props.new_type == "MACRO_OP":
            return "Make a new macro shortcut with this button as its first step"
        return cls.bl_description

    def execute(self, context):
        prefs = get_keyops_prefs()
        if _last_button is None:
            return {'CANCELLED'}
        if self.pie:
            pie = find_pie(self.pie)
        else:
            pie = _new_pie(prefs)
            kind = self.new_type if self.new_type in RUN_TYPES else "MENU"
            pie.name = "My Macro" if kind == "MACRO_OP" else "My Menu"
            pie.menu_type = kind
            pie["enabled"] = False
        if pie is None:
            return {'CANCELLED'}
        item = add_button_to(pie, _last_button, self.position)
        if item is None:
            self.report({'WARNING'}, f"{pie.name} is full")
            return {'CANCELLED'}
        prefs.active_pie = list(prefs.pies).index(pie)
        prefs.pie_slot = list(pie.items).index(item)
        sync_keymaps()
        self.report({'INFO'}, f"Added {item.label or item.idname} to {pie.name}")
        return {'FINISHED'}


class KEYOPS_MT_add_to_menu(bpy.types.Menu):
    bl_label = "Add to Key Ops Menu"
    bl_idname = "KEYOPS_MT_add_to_menu"

    def draw(self, context):
        layout = self.layout
        layout.operator("keyops.add_button_to_menu", text="New Popup Menu", icon='ADD').pie = ""
        layout.operator("keyops.add_button_to_menu", text="New Macro", **icon_kw(TYPE_ICON["MACRO_OP"])).new_type = "MACRO_OP"
        layout.separator()
        for p in get_keyops_prefs().pies:
            if p.menu_type in ("STICKY", "MODAL"):
                continue
            layout.context_pointer_set("keyops_menu", p)  # which menu the next submenu places it in
            layout.menu("KEYOPS_MT_add_to_where", text=p.name, **icon_kw(TYPE_ICON.get(p.menu_type, 'NONE')))


class KEYOPS_MT_add_to_where(bpy.types.Menu):
    """Where in the menu the right-clicked button goes."""
    bl_label = "Where"
    bl_idname = "KEYOPS_MT_add_to_where"

    def draw(self, context):
        layout = self.layout
        pie = getattr(context, "keyops_menu", None)
        if pie is None:
            return
        layout.label(text=pie.name)

        def put(text, position, icon='NONE'):
            op = layout.operator("keyops.add_button_to_menu", text=text, icon=icon)
            op.pie, op.position = pie.uid, position

        if pie.menu_type == "PIE":
            for i in range(min(PIE_SLOTS, len(pie.items))):
                it = pie.items[i]
                put(f"{slot_name(i)}" + ("" if _is_empty(it) else f"  ·  replaces {item_title(pie, it)}"), i,
                    'RADIOBUT_OFF' if _is_empty(it) else 'FILE_REFRESH')
            if len(pie.items) < ITEM_LIMIT["PIE"]:
                layout.separator()
                put("As an Extra Item", len(pie.items), 'ADD')
            return
        put("At the Top", 0, 'TRIA_UP_BAR')
        shown = [(i, it) for i, it in enumerate(pie.items) if it.kind not in (BOX_END,)][:24]
        if shown:
            layout.separator()
        for i, it in shown:
            put(f"After {item_title(pie, it)}", i + 1 if it.kind != BOX else (group_end(list(pie.items), i) or i) + 1)
        layout.separator()
        put("At the End", len(pie.items), 'TRIA_DOWN_BAR')


# ---------------------------------------------------------------- your menus in Blender's own UI

def _here_targets(context):
    """What a Key Ops menu can be added to where the right-click was: this editor's header, and the panels of
    the sidebar tab (or Properties tab) on screen. [(class name, readable name, is a panel)]"""
    area, region = context.area, context.region
    if area is None or region is None:
        return []
    out = []
    space = area.type
    prefix = {"VIEW_3D": "VIEW3D", "IMAGE_EDITOR": "IMAGE", "NODE_EDITOR": "NODE", "PROPERTIES": "PROPERTIES",
              "OUTLINER": "OUTLINER", "TEXT_EDITOR": "TEXT", "SEQUENCE_EDITOR": "SEQUENCER",
              "GRAPH_EDITOR": "GRAPH", "DOPESHEET_EDITOR": "DOPESHEET"}.get(space)
    if prefix and hasattr(bpy.types, f"{prefix}_HT_header"):
        out.append((f"{prefix}_HT_header", "This Editor's Header", False))
    if region.type in ('UI', 'WINDOW'):
        tab = getattr(region, "active_panel_category", "") if region.type == 'UI' else ""
        ctx = getattr(context.space_data, "context", "") if space == 'PROPERTIES' else ""
        for cls in bpy.types.Panel.__subclasses__():
            if getattr(cls, "bl_space_type", "") != space or getattr(cls, "bl_region_type", "") != region.type:
                continue
            if getattr(cls, "bl_parent_id", "") or cls.__name__.startswith("KEYOPS_PT_user_"):
                continue
            if tab and getattr(cls, "bl_category", "") != tab:
                continue
            if ctx and getattr(cls, "bl_context", ctx).lower() != ctx.lower():
                continue
            try:
                if hasattr(cls, "poll") and not cls.poll(context):
                    continue
            except Exception:  # noqa: BLE001
                continue
            name = getattr(cls, "bl_idname", "") or cls.__name__
            if hasattr(bpy.types, name):
                out.append((name, getattr(cls, "bl_label", name), True))
    return out[:30]


class KEYOPS_OT_menu_append_here(Operator):
    bl_idname = "keyops.menu_append_here"
    bl_label = "Show Key Ops Menu Here"
    bl_description = "Show this Key Ops menu in Blender's own header or panel, below what's there"
    bl_options = {'INTERNAL'}
    pie: StringProperty(options={'SKIP_SAVE'}) # type: ignore  # empty: a new popup menu
    target: StringProperty(options={'SKIP_SAVE'}) # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = find_pie(self.pie) if self.pie else None
        if pie is None:
            pie = _new_pie(prefs)
            pie.name, pie.menu_type = "My Menu", "MENU"
            it = pie.items.add()
            it.kind = O
        pie.append_to = self.target
        pie.append_as = "ITEMS" if pie.menu_type == "MENU" else pie.append_as
        pie["enabled"] = True
        prefs.active_pie = list(prefs.pies).index(pie)
        sync_keymaps()
        self.report({'INFO'}, f"{pie.name} now shows in {self.target}. Edit it in Preferences > Custom Menus")
        return {'FINISHED'}


class KEYOPS_OT_panel_to_menu(Operator):
    bl_idname = "keyops.panel_to_menu"
    bl_label = "Add Panel to Key Ops Menu"
    bl_description = "Add this Blender panel to one of your Key Ops menus (it opens from there)"
    bl_options = {'INTERNAL'}
    pie: StringProperty(options={'SKIP_SAVE'}) # type: ignore
    panel: StringProperty(options={'SKIP_SAVE'}) # type: ignore

    def execute(self, context):
        global _last_button
        cls = getattr(bpy.types, self.panel, None)
        pie = find_pie(self.pie)
        if cls is None or pie is None:
            return {'CANCELLED'}
        item = add_button_to(pie, (PANEL_ITEM, self.panel, "", getattr(cls, "bl_label", self.panel)))
        if item is None:
            self.report({'WARNING'}, f"{pie.name} is full")
            return {'CANCELLED'}
        sync_keymaps()
        self.report({'INFO'}, f"Added {item.label} to {pie.name}")
        return {'FINISHED'}


_here = []  # (class name, readable name, is a panel): where the last right-click was, see _here_targets
HERE_MENUS = 30


def _draw_here_menu(self, context):
    """For one header or panel: which Key Ops menu to show in it, or which menu to add the panel to."""
    layout = self.layout
    n = int(type(self).bl_idname.rsplit("_", 1)[-1])
    if n >= len(_here):
        return
    name = _here[n][0]
    layout.label(text="Show in it")
    op = layout.operator("keyops.menu_append_here", text="New Popup Menu", icon='ADD')
    op.target, op.pie = name, ""
    for p in get_keyops_prefs().pies:
        if p.menu_type in ("PIE", "MENU", "DIALOG"):
            op = layout.operator("keyops.menu_append_here", text=p.name, **icon_kw(TYPE_ICON.get(p.menu_type, 'NONE')))
            op.target, op.pie = name, p.uid
    if "_PT_" in name:
        layout.separator()
        layout.label(text="Add this panel to")
        for p in get_keyops_prefs().pies:
            if p.menu_type not in ("STICKY", "MODAL", "STACK", "MACRO_OP"):
                op = layout.operator("keyops.panel_to_menu", text=p.name, **icon_kw(TYPE_ICON.get(p.menu_type, 'NONE')))
                op.pie, op.panel = p.uid, name


_here_menu_classes = [type(f"KEYOPS_MT_here_{n}", (bpy.types.Menu,), {
    "bl_idname": f"KEYOPS_MT_here_{n}", "bl_label": "Key Ops Menus", "draw": _draw_here_menu}) for n in range(HERE_MENUS)]


class KEYOPS_MT_extend_here(bpy.types.Menu):
    """Right-click anywhere: put your menus in Blender's own header and panels here, or its panels in your menus."""
    bl_label = "Key Ops: Customize This UI"
    bl_idname = "KEYOPS_MT_extend_here"

    def draw(self, context):
        layout = self.layout
        if not _here:
            layout.label(text="Nothing here can show a menu")
            return
        for n, (_name, label, panel) in enumerate(_here[:HERE_MENUS]):
            layout.menu(f"KEYOPS_MT_here_{n}", text=label, icon='MENU_PANEL' if panel else 'TOPBAR')


def _button_context_draw(self, context):
    """Blender's right-click menu on any button: Add to Key Ops Menu, and put your menus in this UI."""
    global _last_button
    try:
        _last_button = button_info(context)
    except Exception:  # noqa: BLE001  never break Blender's own menu
        _last_button = None
    # remembered now, for the submenus; not when it's redrawn from inside the menu itself (a popup region)
    if context.region is None or context.region.type != 'TEMPORARY':
        try:
            _here[:] = _here_targets(context)
        except Exception:  # noqa: BLE001
            _here[:] = []
    here = bool(_here)
    if _last_button is not None or here:
        self.layout.separator()
    if _last_button is not None:
        self.layout.menu("KEYOPS_MT_add_to_menu", icon='ADD')
    if here:
        self.layout.menu("KEYOPS_MT_extend_here", icon='MENU_PANEL')


def _button_context_menu():
    return getattr(bpy.types, "UI_MT_button_context_menu", None) or getattr(bpy.types, "WM_MT_button_context", None)


class KEYOPS_MT_item_add(bpy.types.Menu):
    """Add to the end of the menu: a button, label, separator, or a group to lay items out in."""
    bl_label = "Add"
    bl_idname = "KEYOPS_MT_item_add"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'EXEC_DEFAULT'
        for n, (kind, name, _desc, icon) in enumerate(INSERT_KINDS):
            if (kind.startswith("G:") and not INSERT_KINDS[n - 1][0].startswith("G:")) or kind in (BREAK, "HIDE_UI"):
                layout.separator()
            op = layout.operator("keyops.menu_item_insert", text=name, icon=icon)
            op.kind, op.at_end = kind, True


class KEYOPS_OT_item_options(Operator):
    """Right-click an item in the preview: its label, action, icon, look and more, in one menu"""
    bl_idname = "keyops.item_options"
    bl_label = "Item Options"
    bl_options = {'INTERNAL'}
    slot: IntProperty() # type: ignore

    def invoke(self, context, event):
        prefs = get_keyops_prefs()
        item = _active_item(prefs, self.slot)
        if item is None:
            return {'CANCELLED'}
        prefs.pie_slot = self.slot
        if _is_empty(item):
            title = "Empty"
        elif item.kind == BOX:
            title = item.label or GROUP_NAMES.get(item.group_type, "Group")
        elif item.kind in LAYOUT_KINDS:
            title = item.label or item.kind.replace("_", " ").title()
        else:
            title = item.label or action_name(item)
        # titled with the item, so Blender remembers the last used row per item, not across all of them
        context.window_manager.popup_menu(lambda menu, ctx: draw_item_options(menu.layout, prefs),
                                          title=f"{title}  ({self.slot + 1})")
        return {'FINISHED'}


class KEYOPS_OT_pie_move(Operator):
    bl_idname = "keyops.pie_move"
    bl_label = "Move Menu"
    bl_description = "Move the selected menu up or down in the list"
    bl_options = {'INTERNAL'}
    direction: IntProperty() # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        new = prefs.active_pie + self.direction
        while 0 <= new < len(prefs.pies) and not listed(prefs.pies[new]):  # past the hidden submenus
            new += self.direction
        if not (0 <= prefs.active_pie < len(prefs.pies) and 0 <= new < len(prefs.pies)):
            return {'CANCELLED'}
        prefs.pies.move(prefs.active_pie, new)
        prefs.active_pie = new
        _changed()
        return {'FINISHED'}


class KEYOPS_OT_menu_item_move(Operator):
    bl_idname = "keyops.menu_item_move"
    bl_label = "Move Item"
    bl_description = "Move this item up or down"
    bl_options = {'INTERNAL'}
    direction: IntProperty() # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _active_pie(prefs)
        new = prefs.pie_slot + self.direction
        if pie is None or not (0 <= new < len(pie.items)):
            return {'CANCELLED'}
        pie.items.move(prefs.pie_slot, new)
        prefs.pie_slot = new
        _changed()
        return {'FINISHED'}


class KEYOPS_OT_slot_make_macro(Operator):
    bl_idname = "keyops.slot_make_macro"
    bl_label = "Macro"
    bl_description = "Turn this item into a macro (several operators in a row), or back into a single action"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        item = _active_item(prefs, prefs.pie_slot)
        if item is None:
            return {'CANCELLED'}
        if item.kind == MACRO:
            first = item.steps[0] if len(item.steps) else None
            item.kind = O if first else N
            item.idname, item.props = (first.idname, first.props) if first else ("", "")
            item.steps.clear()
        else:
            item.steps.clear()
            if item.kind == O and item.idname.strip():
                st = item.steps.add()
                st.idname, st.props = item.idname, item.props
            item.kind = MACRO
            item.label = item.label or "Macro"
            if not len(item.steps):
                item.steps.add()
        _changed()
        return {'FINISHED'}


class KEYOPS_OT_slot_set_kind(Operator):
    bl_idname = "keyops.slot_set_kind"
    bl_label = "Item Type"
    bl_description = "Make this item a Python script or a label"
    bl_options = {'INTERNAL'}
    kind: StringProperty() # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        item = _active_item(prefs, prefs.pie_slot)
        if item is None or not self.kind:
            return {'CANCELLED'}
        item.kind = self.kind
        if self.kind == SCRIPT and not item.script:
            item.script = "import bpy\n"
            item.label = item.label or "Python"
        if self.kind == DRAW and not item.script.strip():
            item.script = DRAW_DEFAULT
        if self.kind == LABEL:
            item.label = item.label or "Heading"
        if self.kind == BREAK:
            item.idname, item.props, item.label = "", "", "Next Column"
        if self.kind == BOX:
            item.idname, item.props = "", ""
            item.label = item.label if item.label not in ("Next Column", "End Group", "End Box") else ""
        if self.kind == BOX_END:
            item.idname, item.props, item.label = "", "", "End Group"
        _changed()
        return {'FINISHED'}


class KEYOPS_OT_pie_duplicate(Operator):
    bl_idname = "keyops.pie_duplicate"
    bl_label = "Duplicate"
    bl_description = "Make a copy of the selected menu, without a key. Click No key in the list to give it one"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        src = _active_pie(prefs)
        if src is None:
            return {'CANCELLED'}
        all_data = pies_to_data(prefs)["pies"]
        index = {p.uid: i for i, p in enumerate(prefs.pies)}
        family = menu_family(prefs, src)  # the menu and its own submenus, copied together
        new_uid = {p.uid: uuid.uuid4().hex[:12] for p in family}
        copies = []
        for p in family:
            data = json.loads(json.dumps(all_data[index[p.uid]]))
            data["uid"] = new_uid[p.uid]
            data["owner"] = new_uid.get(data.get("owner", ""), data.get("owner", "")) if p is not src else src.owner
            for it in data.get("items", []):  # buttons that open one of the copied submenus open the copy
                if it.get("kind") == SUB and it.get("idname") in new_uid:
                    it["idname"] = new_uid[it["idname"]]
            copies.append(data)
        data = copies[0]
        data["name"] = src.name + " Copy"
        # same on/off as the original, but no key, so the two never fight over one shortcut
        data.update(key="NONE", ctrl=False, shift=False, alt=False, key_mod="NONE", preset="")
        pies_from_data(prefs, {"pies": copies}, True)
        prefs.active_pie = next(i for i, p in enumerate(prefs.pies) if p.uid == data["uid"])
        sync_keymaps()
        return {'FINISHED'}


class KEYOPS_OT_value_add(Operator):
    bl_idname = "keyops.value_add"
    bl_label = "Add Property"
    bl_description = "Add a property of your own: a number, toggle, text or choice, kept by Key Ops or on every " \
                     "scene, object or the window manager"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        vals = context.window_manager.keyops_values
        v = vals.add()
        n = 1
        while f"Property {n}" in vals:
            n += 1
        v.name = f"Property {n}"
        _values_changed()
        schedule_custom_props_sync()
        return {'FINISHED'}


class KEYOPS_OT_value_remove(Operator):
    bl_idname = "keyops.value_remove"
    bl_label = "Remove Property"
    bl_description = "Remove this property. A scene or object property's values stay in the file until it's saved"
    bl_options = {'INTERNAL'}
    index: IntProperty() # type: ignore

    def execute(self, context):
        vals = context.window_manager.keyops_values
        if 0 <= self.index < len(vals):
            vals.remove(self.index)
            _values_changed()
            schedule_custom_props_sync()
        return {'FINISHED'}


def _op_rna(idname):
    """The operator's RNA properties (name -> property), or None when there's no such operator."""
    mod, _dot, name = idname.strip().partition(".")
    if not name or name not in dir(getattr(bpy.ops, mod, object())):
        return None
    try:
        return getattr(getattr(bpy.ops, mod), name).get_rna_type().properties
    except (AttributeError, KeyError, RuntimeError):
        return None


def _param_names(rna):
    return [p.identifier for p in rna if p.identifier != "rna_type" and not p.is_hidden and not p.is_readonly]


def _plain(value):
    """A setting's value as a plain Python literal (tuples for vectors, sets for flag choices)."""
    if isinstance(value, (bool, int, float, str, set)):
        return value
    try:
        return tuple(_plain(v) for v in value)
    except TypeError:
        return value


_params_saved = {}  # the operator's own "last used" values while the parameters dialog borrows them


def _serialize_params(props):
    """The options an operator's property set holds, as the "name=value, ..." text an item stores."""
    rna = props.bl_rna.properties
    parts = []
    for n in _param_names(rna):
        value = _plain(getattr(props, n))
        if props.is_property_set(n) or value != _plain(rna[n].default if not getattr(rna[n], "is_array", False)
                                                           else tuple(rna[n].default_array)):
            parts.append(f"{n}={value!r}")
    return ", ".join(parts)


def _borrow_params(idname, target_props):
    """Fill the operator's "last used" property set with an item's options (the old values are kept to put back)."""
    props = bpy.context.window_manager.operator_properties_last(idname)
    rna = props.bl_rna.properties
    if idname not in _params_saved:
        _params_saved[idname] = {n: _plain(getattr(props, n)) for n in _param_names(rna) if props.is_property_set(n)}
    for n in _param_names(rna):
        props.property_unset(n)
    try:
        for k, v in _parse_props(target_props).items():
            if k in rna:
                setattr(props, k, v)
    except (SyntaxError, ValueError, TypeError, AttributeError):
        pass
    return props


def _give_back_params(idname):
    """Put the operator's own "last used" values back after borrowing them."""
    try:
        props = bpy.context.window_manager.operator_properties_last(idname)
    except (RuntimeError, AttributeError):
        _params_saved.pop(idname, None)
        return
    for n in _param_names(props.bl_rna.properties):
        props.property_unset(n)
    for n, v in _params_saved.pop(idname, {}).items():
        try:
            setattr(props, n, v)
        except (TypeError, ValueError, AttributeError):
            pass


# ---- operator parameters drawn inline in the item card (a dropdown, no popup dialog)
# The fields are the operator's own "last used" property set, borrowed while the dropdown is open: Blender
# draws every option exactly as its own redo panel does (ranges, units, dynamic choices). A draw can't write
# data, so a timer copies the fields into the item's options when they change, and loads them when the
# item, the step or the options text change.
_inline = {"key": None, "idname": "", "synced": None, "pending": False, "last_run": 0}


def _last_run_of(idname):
    """The newest run of this operator in the window manager's history (0: none), to tell a run elsewhere,
    which also writes the "last used" values, from a field changed in the dropdown."""
    want = idname.split(".")[0].upper() + "_OT_" + idname.split(".")[-1]
    try:
        for op in reversed(bpy.context.window_manager.operators):
            if op.bl_idname == want:
                return op.as_pointer()
    except (AttributeError, ReferenceError):
        pass
    return 0
_open_step = {"slot": -1, "step": -1}  # the macro step whose parameters are shown


def _inline_target(prefs, key):
    uid, slot, step = key
    pie = find_pie(uid)
    if pie is None or not (0 <= slot < len(pie.items)):
        return None
    item = pie.items[slot]
    if step >= 0:
        return item.steps[step] if item.kind == MACRO and step < len(item.steps) else None
    return item


def _inline_close():
    if _inline["idname"]:
        _give_back_params(_inline["idname"])
    _inline.update(key=None, idname="", synced=None)


def _inline_sync():
    """Timer: load the fields for the item now shown, or store edited fields in the item."""
    _inline["pending"] = False
    want = _inline.get("want")
    prefs = get_keyops_prefs()
    target = _inline_target(prefs, want) if want else None
    idname = target.idname.strip() if target is not None else ""
    if target is None or _op_rna(idname) is None:
        _inline_close()
    elif (want != _inline["key"] or idname != _inline["idname"] or target.props != _inline["synced"]
          or _last_run_of(idname) != _inline["last_run"]):
        # (a run of the operator elsewhere overwrote the fields: they're loaded from the item again)
        # another item, operator or options typed in the text field: (re)load the fields from the item
        if _inline["idname"] and _inline["idname"] != idname:
            _give_back_params(_inline["idname"])
        props = _borrow_params(idname, target.props)
        _inline.update(key=want, idname=idname, synced=_serialize_params(props), last_run=_last_run_of(idname))
        if target.props != _inline["synced"] and not target.props.strip():
            _inline["synced"] = target.props = ""
    else:
        props = bpy.context.window_manager.operator_properties_last(idname)
        text = _serialize_params(props)
        if text != _inline["synced"]:
            target.props = text
            _inline["synced"] = text
            _changed()
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()
    return None


def _inline_request(key):
    _inline["want"] = key
    if not _inline["pending"]:
        _inline["pending"] = True
        bpy.app.timers.register(_inline_sync, first_interval=0.05)


def draw_inline_params(layout, pie, slot, step, target, extra=None):
    """The operator's options as fields, right in the card. Changing one stores it in the item."""
    idname = target.idname.strip()
    key = (pie.uid, slot, step)
    col = layout.column()
    if _inline["key"] != key or _inline["idname"] != idname:
        _inline_request(key)
        col.label(text="Loading...", icon='TIME')
        return
    props = bpy.context.window_manager.operator_properties_last(idname)
    if target.props != _inline["synced"] or _serialize_params(props) != _inline["synced"]:
        _inline_request(key)  # typed in the text field, or a field changed: sync on the next tick
    col.use_property_split = True
    col.use_property_decorate = False
    names = _param_names(props.bl_rna.properties)
    if not names and not extra:
        _note(col, "This operator has no options")
    for n in names:
        # options the item sets are drawn normally, the rest (the operator's defaults) greyed out
        r = col.row()
        r.active = props.is_property_set(n)
        r.prop(props, n)
    if extra is not None:
        extra(col)
    if names:
        col.operator("keyops.operator_params_reset", text="Reset to Defaults", icon='LOOP_BACK')


class KEYOPS_OT_operator_params_reset(Operator):
    """Clear the options this item runs its operator with: it runs with the operator's defaults"""
    bl_idname = "keyops.operator_params_reset"
    bl_label = "Reset Parameters"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        key = _inline["key"]
        target = _inline_target(get_keyops_prefs(), key) if key else None
        if target is None:
            return {'CANCELLED'}
        target.props = ""
        _changed()
        _inline_request(key)
        return {'FINISHED'}


class KEYOPS_OT_macro_step_params(Operator):
    """Show or hide the options this step runs its operator with"""
    bl_idname = "keyops.macro_step_params"
    bl_label = "Step Parameters"
    bl_options = {'INTERNAL'}
    slot: IntProperty() # type: ignore
    step: IntProperty() # type: ignore

    def execute(self, context):
        if _open_step["slot"] == self.slot and _open_step["step"] == self.step:
            _open_step.update(slot=-1, step=-1)
        else:
            _open_step.update(slot=self.slot, step=self.step)
        return {'FINISHED'}


class KEYOPS_OT_operator_params(Operator):
    """Set the parameters this step (or button) runs its operator with: every option the operator has, as fields"""
    bl_idname = "keyops.operator_params"
    bl_label = "Operator Parameters"
    bl_options = {'INTERNAL'}

    slot: IntProperty(options={'SKIP_SAVE'}) # type: ignore
    step: IntProperty(default=-1, options={'SKIP_SAVE'}) # type: ignore
    op_idname: StringProperty(options={'SKIP_SAVE', 'HIDDEN'}) # type: ignore

    def _target(self, context):
        prefs = get_keyops_prefs()
        item = _active_item(prefs, self.slot)
        if item is None:
            return None, None
        if self.step >= 0:
            if item.kind != MACRO or self.step >= len(item.steps):
                return None, None
            return item.steps[self.step], item.steps[self.step].idname
        return item, item.idname

    def invoke(self, context, event):
        target, idname = self._target(context)
        rna = _op_rna(idname or "")
        if target is None or rna is None:
            self.report({'WARNING'}, "Pick an operator first")
            return {'CANCELLED'}
        self.op_idname = idname.strip()
        _inline_close()  # the dialog and the inline fields share the operator's property set
        # the operator's "last used" values are borrowed for the dialog and put back afterwards
        _borrow_params(self.op_idname, target.props)
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        props = context.window_manager.operator_properties_last(self.op_idname)
        layout = self.layout
        layout.use_property_split = True
        layout.label(text=self.op_idname, icon='TOOL_SETTINGS')
        names = _param_names(props.bl_rna.properties)
        if not names:
            layout.label(text="This operator has no options")
        for n in names:
            layout.prop(props, n)

    def _restore(self, context):
        _give_back_params(self.op_idname)

    def execute(self, context):
        target, _idname = self._target(context)
        props = context.window_manager.operator_properties_last(self.op_idname)
        if target is not None:
            target.props = _serialize_params(props)
            _changed()
        self._restore(context)
        return {'FINISHED'}

    def cancel(self, context):
        self._restore(context)


class KEYOPS_OT_macro_step_add(Operator):
    bl_idname = "keyops.macro_step_add"
    bl_label = "Add Step"
    bl_description = "Add a step to this macro"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        item = _active_item(prefs, prefs.pie_slot)
        if item is None or item.kind != MACRO:
            return {'CANCELLED'}
        item.steps.add()
        _changed()
        return {'FINISHED'}


class KEYOPS_OT_macro_step_remove(Operator):
    bl_idname = "keyops.macro_step_remove"
    bl_label = "Remove Step"
    bl_description = "Remove this step"
    bl_options = {'INTERNAL'}
    step: IntProperty() # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        item = _active_item(prefs, prefs.pie_slot)
        if item is None or not (0 <= self.step < len(item.steps)):
            return {'CANCELLED'}
        item.steps.remove(self.step)
        _changed()
        return {'FINISHED'}


class KEYOPS_OT_macro_step_move(Operator):
    bl_idname = "keyops.macro_step_move"
    bl_label = "Move Step"
    bl_description = "Move this step up or down"
    bl_options = {'INTERNAL'}
    step: IntProperty() # type: ignore
    direction: IntProperty() # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        item = _active_item(prefs, prefs.pie_slot)
        new = self.step + self.direction
        if item is None or not (0 <= self.step < len(item.steps)) or not (0 <= new < len(item.steps)):
            return {'CANCELLED'}
        item.steps.move(self.step, new)
        _changed()
        return {'FINISHED'}


def _paste_command(self, context):
    """A command pasted from the Info editor fills the selected item (or adds a macro step)."""
    text = self.keyops_paste_command
    if not text.strip():
        return
    parsed = parse_command(text)
    self["keyops_paste_command"] = ""  # clear without calling this again
    prefs = get_keyops_prefs()
    item = _active_item(prefs, prefs.pie_slot)
    if parsed is None or item is None:
        return
    idname, opts = parsed
    if item.kind == MACRO:
        empty = next((st for st in item.steps if not st.idname.strip()), None)
        st = empty or item.steps.add()
        st.idname, st.props = idname, opts
    else:
        apply_action(item, "O:" + idname)
        item.props = opts
    _changed()


class KEYOPS_OT_pie_remove(Operator):
    bl_idname = "keyops.pie_remove"
    bl_label = "Delete Pie"
    bl_description = "Delete the selected menu. Presets can be added back from Add Preset"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        prefs = get_keyops_prefs()
        if not 0 <= prefs.active_pie < len(prefs.pies):
            return {'CANCELLED'}
        pie = prefs.pies[prefs.active_pie]
        subs = len(menu_family(prefs, pie)) - 1
        also = f" and its {subs} submenu{'s' if subs != 1 else ''}" if subs else ""
        return context.window_manager.invoke_confirm(
            self, event, title=f"Delete '{pie.name}'{also}?", message="This can't be undone.",
            confirm_text="Delete", icon='WARNING')

    def execute(self, context):
        prefs = get_keyops_prefs()
        if 0 <= prefs.active_pie < len(prefs.pies):
            pie = prefs.pies[prefs.active_pie]
            owner = find_pie(pie.owner) if pie.owner else None
            gone = {p.uid for p in menu_family(prefs, pie)}  # with the submenus that belong to it
            for i in reversed(range(len(prefs.pies))):
                if prefs.pies[i].uid in gone:
                    prefs.pies.remove(i)
            if owner is not None:  # the button that opened the deleted submenu goes too
                for i in reversed(range(len(owner.items))):
                    it = owner.items[i]
                    if it.kind == SUB and it.idname in gone:
                        if owner.menu_type == "PIE" and len(owner.items) <= ITEM_MIN.get("PIE", 8):
                            it.kind, it.idname, it.label, it.icon = N, "", "", ""  # a pie keeps its 8 slots
                        else:
                            owner.items.remove(i)
            # a deleted submenu: back to the menu it belonged to
            index = {p.uid: i for i, p in enumerate(prefs.pies)}
            prefs.active_pie = index.get(owner.uid, 0) if owner is not None else max(0, min(prefs.active_pie, len(prefs.pies) - 1))
            sync_keymaps()
        return {'FINISHED'}


class KEYOPS_OT_pie_reset(Operator):
    bl_idname = "keyops.pie_reset"
    bl_label = "Reset to Preset"
    bl_description = "Put this pie's slots and key back to the Key Ops preset"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = prefs.pies[prefs.active_pie]
        if pie.preset in PRESET_BY_ID:
            enabled = pie.enabled
            _fill(pie, PRESET_BY_ID[pie.preset])
            pie["enabled"] = enabled
            sync_keymaps()
        return {'FINISHED'}


class KEYOPS_OT_pie_set_key(Operator):
    bl_idname = "keyops.pie_set_key"
    bl_label = "Set Key"
    bl_description = "Click, then press the key (with Ctrl/Shift/Alt) that should open this pie. Right, middle and side mouse buttons work too. Esc cancels, Backspace clears"
    bl_options = {'INTERNAL'}

    capturing = -1
    index: IntProperty(default=-1, options={'SKIP_SAVE'}) # type: ignore

    @classmethod
    def description(cls, context, props):
        prefs = get_keyops_prefs()
        if 0 <= props.index < len(prefs.pies):
            pie = prefs.pies[props.index]
            text = f"{key_text(pie)} in {editor_text(pie)}."
            clashes, replaces = key_conflicts(pie)
            if clashes:
                text += "\nSame key as: " + ", ".join(clashes)
            if replaces:
                text += "\nReplaces Blender's: " + ", ".join(replaces[:4]) + (", ..." if len(replaces) > 4 else "")
            return f"{text}\n{cls.bl_description}"
        return cls.bl_description

    def invoke(self, context, event):
        prefs = get_keyops_prefs()
        if 0 <= self.index < len(prefs.pies):
            prefs.active_pie = self.index
        KEYOPS_OT_pie_set_key.capturing = prefs.active_pie
        context.window_manager.modal_handler_add(self)
        self._redraw(context)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.value != 'PRESS' or event.type in _MODIFIER_KEYS or "MOUSEMOVE" in event.type or event.type.startswith("TIMER"):
            return {'RUNNING_MODAL'}
        prefs = get_keyops_prefs()
        pie = prefs.pies[KEYOPS_OT_pie_set_key.capturing]
        if event.type in {'ESC', 'LEFTMOUSE'}:
            pass  # right, middle and side mouse buttons can be used as keys
        elif event.type == 'BACK_SPACE':
            pie.key = "NONE"
        else:
            pie.key, pie.ctrl, pie.shift, pie.alt = event.type, event.ctrl, event.shift, event.alt
            if not pie.enabled:
                pie.enabled = True
        KEYOPS_OT_pie_set_key.capturing = -1
        sync_keymaps()
        self._redraw(context)
        return {'FINISHED'}

    @staticmethod
    def _redraw(context):
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()


from bpy_extras.io_utils import ExportHelper, ImportHelper  # noqa: E402


class KeyOpsExportChoice(PropertyGroup):
    uid: StringProperty() # type: ignore
    use: BoolProperty(default=True) # type: ignore

_SCOPES = (("ALL", "All Settings", "Features, shortcuts, settings and menus"),
           ("PIES", "Custom Menus", "Only your custom menus"))


class KEYOPS_OT_settings_export(Operator, ExportHelper):
    bl_idname = "keyops.settings_export"
    bl_label = "Export Key Ops Settings"
    bl_description = "Save Key Ops settings to a .json file, to back them up or use them on another computer"

    @classmethod
    def description(cls, context, props):
        if props.scope == "PIES":
            return "Export menus to a .json file, to back them up or use them on another computer"
        return cls.bl_description
    bl_options = {'INTERNAL'}
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'}) # type: ignore
    scope: EnumProperty(name="Export", items=_SCOPES) # type: ignore
    include_settings: BoolProperty(name="Features & Settings", default=True,
                                   description="Which features and shortcuts are on, and their options") # type: ignore
    include_menus: BoolProperty(name="Pie & Popup Menus", default=True, description="The menus picked below") # type: ignore

    def invoke(self, context, event):
        self.filepath = "key_ops_pie_menus.json" if self.scope == "PIES" else "key_ops_settings.json"
        self.include_settings = self.scope == "ALL"
        wm = context.window_manager
        wm.keyops_export_menus.clear()
        prefs = get_keyops_prefs()
        for i, p in enumerate(prefs.pies):
            e = wm.keyops_export_menus.add()
            e.name, e.uid = p.name, p.uid
            e.use = True
        return super().invoke(context, event)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Include")
        layout.prop(self, "include_settings")
        layout.prop(self, "include_menus")
        col = layout.box().column(align=True)
        col.enabled = self.include_menus
        for e in context.window_manager.keyops_export_menus:
            col.prop(e, "use", text=e.name)

    def execute(self, context):
        from . import settings_store
        settings_store.flush_now()
        names, options = [], {}
        if self.include_settings:
            names.append("preferences")
        if self.include_menus:
            chosen = {e.uid for e in context.window_manager.keyops_export_menus if e.use} or \
                     {p.uid for p in get_keyops_prefs().pies}
            names.append("pie_menus")
            options["pie_menus"] = lambda d: dict(d, pies=[p for p in d["pies"] if p["uid"] in chosen])
        if not names:
            self.report({'WARNING'}, "Pick something to export")
            return {'CANCELLED'}
        if not self.filepath.strip():
            self.report({'ERROR'}, "Pick a file to export to")
            return {'CANCELLED'}
        settings_store.export_file(self.filepath, names, options)
        self.report({'INFO'}, f"Exported to {self.filepath}")
        return {'FINISHED'}


class KEYOPS_OT_settings_import(Operator, ImportHelper):
    bl_idname = "keyops.settings_import"
    bl_label = "Import Key Ops Settings"
    bl_description = "Load Key Ops settings from a .json file made with Export"

    @classmethod
    def description(cls, context, props):
        if props.scope == "PIES":
            return "Import menus from a .json file made with Export"
        return cls.bl_description
    bl_options = {'INTERNAL'}
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'}) # type: ignore
    scope: EnumProperty(name="Import", items=_SCOPES) # type: ignore
    mode: EnumProperty(name="Custom Menus", items=(
        ("REPLACE", "Replace", "Use the pies from the file instead of the current ones"),
        ("ADD", "Add", "Add the pies from the file and update ones with the same id"))) # type: ignore

    def execute(self, context):
        from . import settings_store
        names = ["pie_menus"] if self.scope == "PIES" else None
        try:
            done = settings_store.import_file(self.filepath, merge=(self.mode == "ADD"), names=names)
        except (OSError, ValueError) as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if not done:
            self.report({'WARNING'}, "Nothing to import in that file")
            return {'CANCELLED'}
        self.report({'INFO'}, "Imported " + ", ".join(n.replace("_", " ") for n in done))
        _redraw_all(context)
        return {'FINISHED'}


def pie_tags(pie):
    return [t for t in (x.strip().lower() for x in pie.tags.split(",")) if t]


def all_tags():
    return sorted({t for p in getattr(get_keyops_prefs(), "pies", ()) for t in pie_tags(p)})


def _filter_tag(wm):
    return wm.keyops_menu_filter_tag.strip().lower() or "ANY"


def _filter_active(wm):
    return bool(wm.keyops_menu_filter_types) or wm.keyops_menu_filter_state != "ALL" \
        or wm.keyops_menu_filter_editor != "ANY" or _filter_tag(wm) != "ANY"


def _menu_matches(wm, pie):
    flt = wm.keyops_menu_filter.strip().lower()
    if flt and flt not in pie.name.lower() and flt not in key_text(pie).lower() and flt not in pie.tags.lower():
        return False
    tag = _filter_tag(wm)
    if tag != "ANY" and tag not in pie_tags(pie):
        return False
    if wm.keyops_menu_filter_types and pie.menu_type not in wm.keyops_menu_filter_types:
        return False
    if wm.keyops_menu_filter_state == "ON" and not pie.enabled:
        return False
    if wm.keyops_menu_filter_state == "OFF" and pie.enabled:
        return False
    return wm.keyops_menu_filter_editor == "ANY" or wm.keyops_menu_filter_editor in editor_names(pie)


class KEYOPS_OT_pie_filter_clear(Operator):
    bl_idname = "keyops.pie_filter_clear"
    bl_label = "Clear Filters"
    bl_description = "Show every menu again"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = context.window_manager
        wm.keyops_menu_filter_types = set()
        wm.keyops_menu_filter_state = "ALL"
        wm.keyops_menu_filter_editor = "ANY"
        wm.keyops_menu_filter_tag = ""
        return {'FINISHED'}


class KEYOPS_OT_pie_filter_popup(Operator):
    bl_idname = "keyops.pie_filter_popup"
    bl_label = "Filter"
    bl_description = "Show only some menus: by type, on or off, or where they work"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=220)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        wm = context.window_manager
        layout = self.layout
        layout.label(text="Type")
        layout.column(align=True).prop(wm, "keyops_menu_filter_types", expand=True)
        layout.label(text="Show")
        layout.row(align=True).prop(wm, "keyops_menu_filter_state", expand=True)
        layout.label(text="Works In")
        layout.prop(wm, "keyops_menu_filter_editor", text="")
        if _filter_active(wm):
            layout.separator()
            layout.operator("keyops.pie_filter_clear", icon='X')


class KEYOPS_OT_pie_new_popup(Operator):
    bl_idname = "keyops.pie_new_popup"
    bl_label = "New"
    bl_description = "Make a new pie menu, popup menu, dialog, panel or special key"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        def draw(menu, ctx):  # a real menu: dark items, left aligned, like Blender's Add menus
            for tid, name, _desc, icon, _n in MENU_TYPES:
                menu.layout.operator("keyops.pie_add", text=name, **icon_kw(icon)).menu_type = tid
        context.window_manager.popup_menu(draw, title="New")
        return {'FINISHED'}

    def execute(self, context):
        return {'FINISHED'}


def _preset_key_text(preset):
    if preset["key"] in ("", "NONE"):
        return "No key"
    mods = [m for m, k in (("Ctrl", "ctrl"), ("Shift", "shift"), ("Alt", "alt")) if preset.get(k)]
    text = " ".join(mods + [_KEY_NAMES.get(preset["key"], preset["key"])])
    return text + " (hold)" if preset.get("key_event") == "HOLD" else text


def _preset_summary(preset, limit=3):
    labels = [item[1] for item in preset["items"] if item[1] and item[0] != LABEL]
    return ", ".join(labels[:limit]) + (", ..." if len(labels) > limit else "")


class KEYOPS_OT_pie_preset_popup(Operator):
    bl_idname = "keyops.pie_preset_popup"
    bl_label = "Add Preset"
    bl_description = "Add one of the ready-made menus"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=680)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        self.layout.emboss = 'PULLDOWN_MENU'  # dark menu items, like Blender's Add menus
        col = self.layout.column(align=True)
        marking_heading = False
        for preset in PRESETS:
            if preset.get("sub"):
                continue  # only used as another preset's submenu, added along with it
            if preset["id"] in MAYA_PRESETS and not marking_heading:
                marking_heading = True
                self.layout.separator()
                self.layout.label(text="Maya Marking Menus")
                if get_keyops_prefs().pie_style != "MARKING":
                    note = self.layout.row()
                    note.active = False
                    note.label(text="Adding one switches pie menus to the Marking style (Pie Menu Settings)",
                               icon='INFO')
                col = self.layout.column(align=True)
                col.emboss = 'PULLDOWN_MENU'
            split = col.split(factor=0.3, align=True)
            split.operator("keyops.pie_add", text=preset["name"], icon='MESH_CIRCLE').preset = preset["id"]
            info = split.split(factor=0.22, align=True)
            key = info.row()
            key.active = False
            key.label(text=_preset_key_text(preset))
            desc = info.row()
            desc.active = False
            desc.label(text=_preset_summary(preset))


# ---------------------------------------------------------------- preferences tab

# ---------------------------------------------------------------- searchable pickers

_op_items_cache = []


def _all_operator_items():
    """Every registered operator, for the 'All of Blender' search. Built once, on first use."""
    if not _op_items_cache:
        n = 20000
        for mod_name in dir(bpy.ops):
            mod = getattr(bpy.ops, mod_name)
            for op_name in dir(mod):
                idname = f"{mod_name}.{op_name}"
                try:
                    rna = getattr(mod, op_name).get_rna_type()
                    name = rna.name or op_name
                    desc = (rna.description or "").split("\n")[0][:120]
                except Exception:
                    continue
                _op_items_cache.append((f"O:{idname}", f"{name}  ·  {idname}", desc, 'NONE', n))
                n += 1
    return _op_items_cache


_KEYOPS_SEARCH = [("EMPTY", "Empty slot", "Leave this slot empty", 'X', 0)] + [
    (f"C{i}", f"{label}  ·  {group}", f"{idname}  {props}".strip(), icon if icon in _ICONS else 'NONE', i + 1)
    for i, (group, _kind, label, icon, idname, props) in enumerate(_CATALOG)]


_menu_items_cache = {}
_menu_type_filter_cache = []


def _menu_type_filter_items(_self, _context):
    """The menu types as flags for the list filter, with the same icons as everywhere else."""
    if not _menu_type_filter_cache:
        _menu_type_filter_cache.extend((t, n, d, i, 1 << k) for k, (t, n, d, i, _x) in enumerate(_menu_type_items()))
    return _menu_type_filter_cache


def _user_menu_items():
    """Your own Key Ops menus, so an item can open another menu."""
    prefs = get_keyops_prefs()
    menus = tuple((p.uid, p.name, p.menu_type) for p in (getattr(prefs, "pies", None) or ()) if p.menu_type != "PANEL")
    if menus not in _menu_items_cache:  # Blender keeps pointers to these strings: keep every list alive
        _menu_items_cache[menus] = [(f"K:{uid}", f"{name}  ·  open this Key Ops menu", "", enum_icon(TYPE_ICON.get(t, 'NONE')), 10000 + i)
                                    for i, (uid, name, t) in enumerate(menus)]
    return _menu_items_cache[menus]


_panel_items_cache = []


def _blender_panel_items():
    if not _panel_items_cache:
        for i, name in enumerate(sorted(n for n in dir(bpy.types) if "_PT_" in n and not n.startswith("KEYOPS"))):
            cls = getattr(bpy.types, name)
            label = getattr(cls, "bl_label", "") or name
            _panel_items_cache.append((f"P:{name}", f"{label}  ·  panel {name}", "", 'MENU_PANEL', 30000 + i))
    return _panel_items_cache


_blender_menu_cache = []


def _blender_menu_items():
    """Blender's menus (and other add-ons' menus), so a slot can open one, e.g. the Add menu."""
    if not _blender_menu_cache:
        for i, name in enumerate(sorted(n for n in dir(bpy.types) if "_MT_" in n and not n.startswith("KEYOPS"))):
            cls = getattr(bpy.types, name)
            label = getattr(cls, "bl_label", "") or name
            _blender_menu_cache.append((f"M:{name}", f"{label}  ·  menu {name}", "", 'COLLAPSEMENU', 40000 + i))
    return _blender_menu_cache


def _search_items(self, context):
    prefs = get_keyops_prefs()
    pies = getattr(prefs, "pies", None) or ()
    pie = pies[max(0, min(prefs.active_pie, len(pies) - 1))] if len(pies) else None
    # only a pie has slots to leave empty; in other menus an item is removed with its X
    own = _KEYOPS_SEARCH if pie is None or pie.menu_type == "PIE" else _KEYOPS_SEARCH[1:]
    base = own + _user_menu_items()
    if self.scope == "PANELS":
        return _blender_panel_items()
    if self.scope == "OPERATORS":
        return _all_operator_items()
    return base if self.scope == "KEYOPS" else base + _all_operator_items() + _blender_menu_items()


def _active_item(prefs, slot):
    pie = prefs.pies[max(0, min(prefs.active_pie, len(prefs.pies) - 1))]
    return pie.items[slot] if 0 <= slot < len(pie.items) else None


_grabbed = None  # (menu uid, item index) picked up with Ctrl+click, waiting for a Ctrl+click on its new place


def ctrl_click_move(op, context, slot):
    """Ctrl+click an item to pick it up, Ctrl+click another slot to put it there.
    Pie slots swap places; in menus and lists the item moves to that position."""
    global _grabbed
    prefs = get_keyops_prefs()
    pie = _active_pie(prefs)
    if pie is None or not 0 <= slot < len(pie.items):
        return {'CANCELLED'}
    if _grabbed is None or _grabbed[0] != pie.uid or _grabbed[1] >= len(pie.items):
        _grabbed = (pie.uid, slot)
        item = pie.items[slot]
        op.report({'INFO'}, f"Moving '{item.label or item.idname or 'Empty'}': Ctrl+click where it should go")
        return {'FINISHED'}
    src, _grabbed = _grabbed[1], None
    if src != slot:
        if pie.menu_type == "PIE":
            a, b = _item_to_data(pie.items[src]), _item_to_data(pie.items[slot])
            _item_from_data(pie.items[src], b)
            _item_from_data(pie.items[slot], a)
        else:
            pie.items.move(src, slot)
        prefs.pie_slot = slot
        _changed()
    _redraw_all(context)
    return {'FINISHED'}


class KEYOPS_OT_pie_slot_search(Operator):
    bl_idname = "keyops.pie_slot_search"
    bl_label = "Operator"
    bl_description = ("Search for what this slot should do: a Key Ops action, any operator or a menu.\n"
                      "Ctrl+click to pick it up, then Ctrl+click another slot to move it there")
    bl_options = {'INTERNAL'}
    bl_property = "action"

    slot: IntProperty() # type: ignore
    step: IntProperty(default=-1, options={'SKIP_SAVE'}) # type: ignore  # >= 0: a macro step
    scope: EnumProperty(items=(("KEYOPS", "Key Ops", ""), ("ALL", "All of Blender", ""), ("PANELS", "Blender Panels", ""),
                               ("OPERATORS", "Operators", ""))) # type: ignore
    action: EnumProperty(items=_search_items) # type: ignore

    def invoke(self, context, event):
        if event.ctrl and self.step < 0:
            return ctrl_click_move(self, context, self.slot)
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        item = _active_item(get_keyops_prefs(), self.slot)
        if item is None:
            return {'CANCELLED'}
        if self.step >= 0:
            if self.step < len(item.steps):
                apply_step_action(item.steps[self.step], self.action)
        else:
            apply_action(item, self.action)
        _redraw_all(context)
        return {'FINISHED'}


def apply_step_action(step, action):
    if action == "EMPTY":
        step.idname, step.props = "", ""
    elif action.startswith("C"):
        _g, kind, _label, _icon_name, idname, props = _CATALOG[int(action[1:])]
        if kind == O:
            step.idname, step.props = idname, props
    elif action.startswith("O:"):
        step.idname, step.props = action[2:], ""


def apply_action(item, action):
    if action.startswith("P:"):
        name = action[2:]
        cls = getattr(bpy.types, name, None)
        item.kind, item.idname, item.props = PANEL_ITEM, name, ""
        item.label, item.icon = (getattr(cls, "bl_label", "") or name), ""
        return
    if action.startswith("M:"):
        name = action[2:]
        cls = getattr(bpy.types, name, None)
        item.kind, item.idname, item.props = M, name, ""
        item.label, item.icon = (getattr(cls, "bl_label", "") or name), ""
        return
    if action.startswith("K:"):
        target = find_pie(action[2:])
        if target is not None:
            item.kind, item.idname, item.props, item.label, item.icon = SUB, target.uid, "", target.name, ""
        return
    if action == "EMPTY":
        item.kind, item.label, item.icon, item.idname, item.props = N, "", "", "", ""
    elif action.startswith("C"):
        _g, item.kind, item.label, item.icon, item.idname, item.props = _CATALOG[int(action[1:])]
    elif action.startswith("O:"):
        idname = action[2:]
        mod, op = idname.split(".", 1)
        try:
            name = getattr(getattr(bpy.ops, mod), op).get_rna_type().name
        except Exception:
            name = op.replace("_", " ").title()
        item.kind, item.idname, item.props, item.label, item.icon = O, idname, "", name, ""


from .utils.utilities import redraw_all_areas as _redraw_all  # noqa: E402
from .utils.utilities import safe_icon as _safe_icon  # noqa: E402


class KEYOPS_OT_pie_slot_select(Operator):
    bl_idname = "keyops.pie_slot_select"
    bl_label = "Edit Slot"
    bl_description = "Edit this slot below. Ctrl+click to pick it up, then Ctrl+click another slot to move it there"
    bl_options = {'INTERNAL'}
    slot: IntProperty() # type: ignore

    def invoke(self, context, event):
        if event.ctrl:
            return ctrl_click_move(self, context, self.slot)
        return self.execute(context)

    def execute(self, context):
        get_keyops_prefs().pie_slot = self.slot
        return {'FINISHED'}


class KEYOPS_PT_icon_palette(bpy.types.Panel):
    """Icon palette popup. Shown with wm.call_panel, so it closes when an icon is clicked."""
    bl_idname = "KEYOPS_PT_icon_palette"
    bl_label = "Icon"
    bl_space_type = 'TOPBAR'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 24

    def draw(self, context):
        wm = context.window_manager
        prefs = get_keyops_prefs()
        current = _palette_current(prefs)
        layout = self.layout

        head = layout.row()
        head.label(text="Icons")
        right = head.row(align=True)
        right.alignment = 'RIGHT'
        if current:
            cur = right.row()
            cur.active = False
            cur.label(text=current.removeprefix(CUSTOM_ICON).replace("_", " ").title(), **icon_kw(current))
        right.operator("keyops.pie_set_icon", text="No Icon", icon='X', emboss=False).icon = ""

        search = layout.row()
        search.scale_y = 1.2
        if bpy.app.version >= (4, 1, 0):
            search.prop(wm, "keyops_icon_filter", text="", icon='VIEWZOOM', placeholder="Search icons")
        else:
            search.prop(wm, "keyops_icon_filter", text="", icon='VIEWZOOM')
        words = [w for w in wm.keyops_icon_filter.strip().split() if w]

        tabs = layout.row(align=True)
        tabs.scale_y = 1.1
        tabs.prop(wm, "keyops_icon_category", expand=True)  # a property: switching redraws the palette in place
        layout.separator(factor=0.6)
        # wm.keyops_icon_rows is filled by the search bar and tabs (rebuild_icon_rows), never while drawing
        # a list, so the palette has a scroll bar and scrolls with the mouse wheel. With grid lists each
        # cell holds one icon (hovering lights up only that icon); without them (Blender 5.4+) each list
        # row holds a whole row of icons
        if _grid_lists():
            layout.template_list("KEYOPS_UL_icon_rows", "", wm, "keyops_icon_rows", wm, "keyops_icon_row_index",
                                 type='GRID', columns=ICON_COLUMNS, rows=ICON_ROWS, maxrows=ICON_ROWS)
        else:
            layout.template_list("KEYOPS_UL_icon_rows", "", wm, "keyops_icon_rows", wm, "keyops_icon_row_index",
                                 rows=ICON_ROWS, maxrows=ICON_ROWS)
        foot = layout.row()
        foot.active = False
        count = _icon_rows_state.get("count", 0)
        if not count:
            foot.label(text="No icons match." if words else "No icons in this tab.")
        else:
            foot.label(text=f"{count} icons  ·  scroll for more" if count > ICON_ROWS * (ICON_COLUMNS if _grid_lists() else ROW_ICON_COLUMNS) else f"{count} icons")


ICON_COLUMNS = 14
ROW_ICON_COLUMNS = 22  # Blender 5.4+ (no grid lists): icons per list row, enough to fill the palette's width
ICON_ROWS = 9
_icon_rows_state = {"key": None, "count": 0}


def icon_row(row, names, current):
    """One row of the palette: a button per icon, the current one pressed in."""
    for name in names:
        is_current = name == current
        row.operator("keyops.pie_set_icon", text="", **icon_kw(name), emboss=is_current, depress=is_current).icon = name
    for _i in range(len(names), ROW_ICON_COLUMNS if not _grid_lists() else 0):  # keep a short last row's icons in their columns
        row.label(text="")


def _grid_lists():
    """True when this Blender still has grid lists (template_list type 'GRID'); 5.4 removed them."""
    if "grid" not in _icon_rows_state:
        param = bpy.types.UILayout.bl_rna.functions["template_list"].parameters["type"]
        _icon_rows_state["grid"] = "GRID" in {i.identifier for i in param.enum_items}
    return _icon_rows_state["grid"]


def rows_key(wm):
    return (wm.keyops_icon_category, wm.keyops_icon_filter.strip().upper())


def rebuild_icon_rows(wm):
    """Fill the palette's list: the icons of the tab (or every icon matching the search), one per cell."""
    key = rows_key(wm)
    cat, text = key
    words = [w for w in text.replace(" ", "_").split("_") if w]
    own = [CUSTOM_ICON + n for n in palette_icon_names()]  # Key Ops' own icons, first
    if words:  # searching looks through every tab
        matches = [n for n in own + _ICON_LIST if all(w in n.upper() for w in words)]
    elif cat == "KEYOPS":
        matches = own
    else:
        matches = (own if cat == "ALL" else []) + [n for n in _ICON_LIST if cat == "ALL" or _ICON_CAT.get(n) == cat]
    wm.keyops_icon_rows.clear()
    step = 1 if _grid_lists() else ROW_ICON_COLUMNS  # without grid lists, one list row holds a row of icons
    for i in range(0, len(matches), step):
        wm.keyops_icon_rows.add().names = " ".join(matches[i:i + step])
    wm.keyops_icon_row_index = -1
    _icon_rows_state.update(key=key, count=len(matches))


def _icon_rows_update(self, context):
    rebuild_icon_rows(context.window_manager)


def _icon_row_index_update(self, context):
    if self.keyops_icon_row_index != -1:  # rows aren't picked, only the icons in them
        self.keyops_icon_row_index = -1


class KeyOpsIconRow(PropertyGroup):
    names: StringProperty() # type: ignore  # icon names, space separated: one per grid cell, or a whole row


class KEYOPS_UL_icon_rows(bpy.types.UIList):
    """The icon palette: a grid list (one icon per cell), so it has a scroll bar and scrolls with the mouse wheel."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        current = _palette_current(get_keyops_prefs())
        names = item.names.split()
        icon_row(layout.row(align=True) if len(names) > 1 or not _grid_lists() else layout, names, current)

    def draw_filter(self, context, layout):
        pass  # the palette's own search bar filters


class KEYOPS_OT_pie_icon_picker(Operator):
    bl_idname = "keyops.pie_icon_picker"
    bl_label = "Icon"
    bl_description = "Choose this slot's icon from Blender's icons or Key Ops' own"
    bl_options = {'INTERNAL'}
    slot: IntProperty() # type: ignore

    def execute(self, context):
        item = _active_item(get_keyops_prefs(), self.slot)
        if item is None or _is_empty(item):
            self.report({'INFO'}, "Pick an action for this slot first")
            return {'CANCELLED'}
        get_keyops_prefs().pie_slot = self.slot
        _palette_target["panel"] = False
        context.window_manager.keyops_icon_filter = ""  # each time a fresh search (rebuilds the list)
        rebuild_icon_rows(context.window_manager)
        # kept open, so the search and category tabs work in place; it closes when the mouse leaves
        bpy.ops.wm.call_panel(name="KEYOPS_PT_icon_palette", keep_open=True)
        return {'FINISHED'}


_palette_target = {"panel": False}  # True while the palette picks the menu's sidebar panel icon, not a slot's


def _palette_current(prefs):
    """The icon the palette shows as current: the selected slot's, or the panel header's."""
    if _palette_target["panel"]:
        pie = _active_pie(prefs)
        return pie.panel_icon.strip() if pie is not None else ""
    item = _active_item(prefs, prefs.pie_slot)
    return item.icon if item is not None else ""


def _palette_apply(prefs, slot, icon):
    """Give the picked icon to the slot, or to the panel header when the palette was opened for it."""
    if slot < 0 and _palette_target["panel"]:
        pie = _active_pie(prefs)
        if pie is None:
            return False
        pie.panel_icon = icon
        return True
    item = _active_item(prefs, slot if slot >= 0 else prefs.pie_slot)
    if item is None:
        return False
    item.icon = icon
    return True


class KEYOPS_OT_panel_icon_picker(Operator):
    bl_idname = "keyops.panel_icon_picker"
    bl_label = "Header Icon"
    bl_description = "Choose the icon shown in this panel's header, from Blender's icons or Key Ops' own"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        if _active_pie(get_keyops_prefs()) is None:
            return {'CANCELLED'}
        _palette_target["panel"] = True
        context.window_manager.keyops_icon_filter = ""  # each time a fresh search (rebuilds the list)
        rebuild_icon_rows(context.window_manager)
        bpy.ops.wm.call_panel(name="KEYOPS_PT_icon_palette", keep_open=True)
        return {'FINISHED'}


class KEYOPS_OT_pie_set_icon(Operator):
    bl_idname = "keyops.pie_set_icon"
    bl_label = "Use Icon"
    bl_options = {'INTERNAL'}
    icon: StringProperty() # type: ignore
    slot: IntProperty(default=-1) # type: ignore

    @classmethod
    def description(cls, context, properties):
        return properties.icon or "No icon"

    def execute(self, context):
        _palette_apply(get_keyops_prefs(), self.slot, self.icon)
        _redraw_all(context)
        return {'FINISHED'}


ICON_CATEGORIES = (
    ("ALL", "All", ()),
    ("KEYOPS", "Key Ops", ()),  # Key Ops' own icons, as the N panel uses them
    ("OBJECTS", "Objects", ("MESH_", "OUTLINER_", "OBJECT", "CURVE", "SURFACE", "META", "EMPTY", "LIGHT", "CAMERA",
                            "ARMATURE", "LATTICE", "GREASEPENCIL", "FORCE_", "SPEAKER", "VOLUME", "POINTCLOUD", "MONKEY")),
    ("MODIFIERS", "Modifiers", ("MOD_", "CON_", "AUTOMERGE", "GEOMETRY_NODES", "NODETREE")),
    ("EDITING", "Editing", ("EDITMODE", "VERTEXSEL", "EDGESEL", "FACESEL", "SELECT", "SNAP", "PIVOT", "ORIENTATION",
                            "TRANSFORM", "TOOL", "SCULPT", "BRUSH", "MIRROR", "UV", "STICKY", "SEAM", "SHARP",
                            "NORMAL", "FREEZE", "CENTER", "CURSOR", "DECORATE", "PROP_", "AUTO")),
    ("VIEW", "View", ("VIEW", "HIDE", "RESTRICT", "ZOOM", "OVERLAY", "XRAY", "SHADING", "MATERIAL", "TEXTURE",
                      "IMAGE", "NODE", "WORLD", "RENDER", "SCENE", "WINDOW", "WORKSPACE", "AREA", "SPLIT",
                      "FULLSCREEN", "GRID", "AXIS")),
    ("KEYS", "Keys", ("EVENT_", "MOUSE_")),
)


def _icon_category(name):
    for cid, _label, prefixes in ICON_CATEGORIES[1:]:
        if any(name.startswith(pre) or (len(pre) > 3 and pre in name) for pre in prefixes):
            return cid
    return "OTHER"


_ICON_LIST = sorted(n for n in _ICONS if n not in {"NONE", "BLANK1"} and not n.startswith(("BRUSH_", "MATPLANE", "COLORSET_")))
_ICON_CAT = {n: _icon_category(n) for n in _ICON_LIST}
# every icon as a search entry: "Mesh Cube" with its picture, so typing "mesh cube" finds MESH_CUBE
_ICON_SEARCH_ITEMS = [(n, n.replace("_", " ").title(), n, n, i) for i, n in enumerate(_ICON_LIST)]


class KEYOPS_OT_pie_icon_search(Operator):
    bl_idname = "keyops.pie_icon_search"
    bl_label = "Search Icons"
    bl_description = "Type to find an icon by name. Arrow keys and Enter pick one"
    bl_options = {'INTERNAL'}
    bl_property = "icon"
    icon: EnumProperty(name="Icon", items=_ICON_SEARCH_ITEMS) # type: ignore
    slot: IntProperty(default=-1, options={'SKIP_SAVE'}) # type: ignore

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not _palette_apply(get_keyops_prefs(), self.slot, self.icon):
            return {'CANCELLED'}
        _redraw_all(context)
        return {'FINISHED'}


# ---------------------------------------------------------------- pie overview

SLOT_W = 7.0  # units


def _slot_button(row, pie, index, prefs, width=SLOT_W):
    cell = row.row(align=True)
    if width:
        cell.ui_units_x = width
    cell.scale_y = 1.25
    if index >= len(pie.items):
        cell.label(text="")
        return
    item = pie.items[index]
    empty = _is_empty(item)
    text = ("Separator" if pie.menu_type == "MENU" else "Empty") if empty else (item.label or item.idname or "Macro")
    selected = prefs.pie_slot == index
    styled = not selected and not empty  # the preview shows each button the way the menu draws it
    if styled:
        cell.scale_y = 1.25 * item.height
        cell.scale_x = item.width
        cell.alert = item.alert
    # One rounded item, like an entry in a real pie: the icon and the label are two
    # frameless click zones inside it (icon opens the palette, label picks the action).
    if item.kind in (LABEL, BOX) and not empty and not selected:  # a heading: plain text, still clickable
        r = cell.row(align=True)
        r.alignment = 'CENTER'
        icon = icon_kw(item_icon(item))
        if True:
            r.operator("keyops.pie_slot_select", text=item_text(item, text), emboss=False, **icon).slot = index
        else:
            r.label(text=item_text(item, text), **icon)
        return
    icon_only = styled and not item.label.strip() and item.icon
    no_icon = False
    framed = selected or not styled or item.emboss
    item_box = cell.box() if framed and not selected else cell.column()
    r = item_box.row(align=True)
    r.scale_y = 0.85 if not selected else 1.0
    emboss = selected
    if icon_only:  # one click zone: the icon picks the action (its icon is changed with the item selected)
        if True:
            r.operator("keyops.pie_slot_select", text="", **icon_kw(item.icon), emboss=False).slot = index
        else:
            op = r.operator("keyops.pie_slot_search", text="", **icon_kw(item.icon), emboss=False)
            op.slot, op.scope = index, "ALL"
        return
    if not no_icon:
        r.operator("keyops.pie_icon_picker", text="", **icon_kw(item.icon or 'BLANK1'),
                   emboss=emboss, depress=selected).slot = index
    op = r.operator("keyops.pie_slot_select", text=text, emboss=emboss, depress=selected)  # edited in the card below
    op.slot = index


def _is_empty(item):
    if item.kind in LAYOUT_KINDS:
        return False
    if item.kind == MACRO:
        return not len(item.steps)
    if item.kind in (SCRIPT, DRAW):
        return not item.script.strip()
    if item.kind == LABEL:
        return not item.label.strip()
    return item.kind == N or not item.idname.strip()


def _remove_button(row, pie, index, prefs):
    """A small remove button beside a list item (Customize has its own in the slot editor)."""
    if len(pie.items) <= ITEM_MIN.get(pie.menu_type, 0):
        return
    row.operator("keyops.menu_item_remove", text="", icon='X', emboss=False).slot = index


def _layout_marker(layout, pie, index, prefs, text, icon):
    """Next Column and End Box in the preview: small, dim, still selectable and removable."""
    r = layout.row(align=True)
    r.alignment = 'CENTER'
    selected = prefs.pie_slot == index
    r.active = selected
    r.operator("keyops.pie_slot_select", text=text, icon=icon, emboss=selected, depress=selected).slot = index
    _remove_button(r, pie, index, prefs)


def draw_menu_overview(layout, pie, prefs):
    """Popup menus, dialogs and panels drawn as they will look: columns, boxes, rows and each button's look."""
    col = layout.column(align=False)
    head = col.row()
    head.alignment = 'CENTER'
    head.label(text=pie.name, **icon_kw(TYPE_ICON.get(pie.menu_type, 'NONE') if pie.menu_type != "MENU" else 'NONE'))
    k = col.row()
    k.alignment = 'CENTER'
    k.active = False
    key = "" if pie.menu_type == "PANEL" else (key_text(pie) if pie.enabled else "Off")
    hint = TYPE_HINT.get(pie.menu_type, "")
    if pie.menu_type == "MENU" and needs_panel_popup(pie.items):
        hint = "Opens as a popup panel, since menus can't draw rows, sizes or boxes"
    k.label(text=key + ("  ·  " + hint if key and hint else hint))

    n_cols = 1 + sum(1 for it in pie.items if it.kind == BREAK)
    outer = col.row()
    outer.alignment = 'CENTER'
    area = outer.column()
    area.ui_units_x = 12.0 * n_cols
    cols = _split_columns(area, n_cols) if n_cols > 1 else [area]
    c, box, last_row = 0, None, None
    for i, it in enumerate(pie.items):
        if it.kind == BREAK:
            c, box, last_row = min(c + 1, n_cols - 1), None, None
            _layout_marker(cols[c], pie, i, prefs, "Next Column", 'CENTER_ONLY')
            continue
        if it.kind == BOX:
            b = cols[c].box()
            hr = b.row()
            _slot_button(hr, pie, i, prefs, width=0)
            _remove_button(hr, pie, i, prefs)
            box, last_row = b.column(), None
            continue
        if it.kind == BOX_END:
            _layout_marker(box or cols[c], pie, i, prefs, "End Box", 'REMOVE')
            box, last_row = None, None
            continue
        dest = box or cols[c]
        if it.same_row and last_row is not None:
            row = last_row
        else:
            row = dest.row(align=True)
            last_row = row
        _slot_button(row, pie, i, prefs, width=0)
        _remove_button(row, pie, i, prefs)
    if len(pie.items) < ITEM_LIMIT.get(pie.menu_type, LIST_LIMIT):
        row = col.row()
        row.alignment = 'CENTER'
        add = row.row()
        add.ui_units_x = 11.0
        add.operator("keyops.menu_item_add", text="Add Item", icon='ADD')


LIST_LABELS = {
    "STACK": lambda i: f"Press {i + 1}",
    "STICKY": lambda i: ("While Held", "On Release")[i] if i < 2 else "",
    "MODAL": lambda i: "Setting",
    "MACRO_OP": lambda i: f"Step {i + 1}",
}
TYPE_HINT = {
    "DIALOG": "Opens a small window with these buttons and settings",
    "PANEL": "Shows in the editor's sidebar (N), in its own tab (set beside Works In)",
    "STACK": "Each press runs the next item",
    "STICKY": "A toggle setting here is only changed while the key is held",
    "MODAL": "Move the mouse or scroll to change it. Options like step=0.1, min=0, max=1",
    "MACRO_OP": "The key runs every step in order, stopping if one fails",
}


def draw_list_overview(layout, pie, prefs):
    """Stack, sticky and modal keys, dialogs and panels: a labelled list of their items."""
    col = layout.column(align=False)
    head = col.row()
    head.alignment = 'CENTER'
    head.label(text=pie.name, **icon_kw(TYPE_ICON.get(pie.menu_type, 'NONE')))
    hint = col.row()
    hint.alignment = 'CENTER'
    hint.active = False
    key = "" if pie.menu_type == "PANEL" else (key_text(pie) if pie.enabled else "Off") + "  ·  "
    hint.label(text=key + TYPE_HINT.get(pie.menu_type, ""))
    labels = LIST_LABELS.get(pie.menu_type)
    for i in range(len(pie.items)):
        row = col.row()
        row.alignment = 'CENTER'
        if labels:
            lab = row.row()
            lab.ui_units_x = 5
            lab.alignment = 'RIGHT'
            lab.active = False
            lab.label(text=labels(i))
        _slot_button(row, pie, i, prefs, width=11.0)
        _remove_button(row, pie, i, prefs)
    if len(pie.items) < ITEM_LIMIT.get(pie.menu_type, LIST_LIMIT):
        row = col.row()
        row.alignment = 'CENTER'
        add = row.row()
        add.ui_units_x = 11.0
        add.operator("keyops.menu_item_add", text="Add Item", icon='ADD')


def draw_pie_overview(layout, pie, prefs):
    """The pie drawn as buttons, in roughly the proportions Blender draws it."""
    if pie.menu_type in {"MENU", "DIALOG", "PANEL"}:
        return draw_menu_overview(layout, pie, prefs)
    if pie.menu_type != "PIE":
        return draw_list_overview(layout, pie, prefs)
    col = layout.column(align=False)
    rows = ((("N",), 0.0), (("NW", "NE"), 1.5), (("W", "E"), 5.0), (("SW", "SE"), 1.5), (("S",), 0.0))
    for spec, gap in rows:
        row = col.row()
        row.alignment = 'CENTER'
        _slot_button(row, pie, ORDER.index(spec[0]), prefs)
        if len(spec) == 2:
            mid = row.column(align=True)
            mid.ui_units_x = gap
            if spec == ("W", "E"):
                for text, dim in ((pie.name, False), (key_text(pie) if pie.enabled else "Off", True)):
                    t = mid.row()
                    t.alignment = 'CENTER'
                    t.active = not dim
                    t.label(text=text)
            else:
                mid.label(text="")
            _slot_button(row, pie, ORDER.index(spec[1]), prefs)
        col.separator(factor=0.35)


def draw_canvas_overview(layout, context, pie, prefs):
    """Pies, popup menus, dialogs and panels, drawn with the GPU the way they really look (ui/menu_canvas.py)."""
    if pie.menu_type != "PIE":
        hint = TYPE_HINT.get(pie.menu_type, "")
        if pie.menu_type == "MENU" and needs_panel_popup(pie.items):
            hint = "Opens as a popup panel, since menus can't draw rows, sizes or boxes"
        if hint:
            k = layout.row()
            k.alignment = 'CENTER'
            k.active = False
            k.label(text=hint)
    menu_canvas.draw_layout(layout, context, pie, prefs)
    row = layout.row()  # in the middle, under the menu: add to it, and try it
    row.alignment = 'CENTER'
    if pie.menu_type != "PIE" and len(pie.items) < ITEM_LIMIT.get(pie.menu_type, LIST_LIMIT):
        add = row.row()
        add.ui_units_x = 8.0
        add.menu("KEYOPS_MT_item_add", text="Add", icon='ADD')
    elif pie.menu_type == "PIE" and len(pie.items) < ITEM_LIMIT["PIE"]:  # beyond the 8 directions
        add = row.row()
        add.ui_units_x = 8.0
        add.operator("keyops.menu_item_add", text="Add Extra", icon='ADD')
    if pie.menu_type != "PANEL":
        tryit = row.row()
        tryit.ui_units_x = 5.0
        op = tryit.operator("wm.keyops_call_pie", text="Try It", icon='PLAY')
        op.pie, op.direct = pie.uid, True


class KEYOPS_MT_menu_list_specials(bpy.types.Menu):
    """The ▾ menu beside the Custom Menus list."""
    bl_label = "Custom Menus"
    bl_idname = "KEYOPS_MT_menu_list_specials"

    def draw(self, context):
        layout = self.layout
        layout.operator("keyops.pie_preset_popup", text="Add Preset...", icon='PRESET')
        layout.operator("keyops.pie_duplicate", text="Duplicate", icon='DUPLICATE')
        layout.separator()
        layout.operator("keyops.settings_import", text="Import Menus...", icon='IMPORT').scope = "PIES"
        layout.operator("keyops.settings_export", text="Export Menus...", icon='EXPORT').scope = "PIES"


class KEYOPS_UL_menus(bpy.types.UIList):
    """The Custom Menus list: on/off, type and name, and the key that opens it (click to change)."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        p = item
        row = layout.row(align=True)
        row.prop(p, "enabled", text="")
        name = row.row(align=True)
        name.active = p.enabled or index == data.active_pie
        name.prop(p, "name", text="", emboss=False, **icon_kw(TYPE_ICON.get(p.menu_type, 'NONE')))
        subs = len(menu_family(data, p)) - 1
        if subs:  # its own submenus are inside it, not separate rows
            n = name.row()
            n.active = False
            n.alignment = 'RIGHT'
            n.label(text=f"+{subs}")
        k = row.row(align=True)
        k.ui_units_x = 4.2
        k.alignment = 'RIGHT'
        if p.menu_type == "PANEL":  # panels open from the sidebar, they have no key
            k.active = False
            k.label(text="Sidebar")
        else:
            capturing = KEYOPS_OT_pie_set_key.capturing == index
            k.alert = capturing or (p.enabled and bool(key_conflicts(p)[0]))
            k.active = capturing or p.enabled or index == data.active_pie
            k.operator("keyops.pie_set_key", text="Press a key..." if capturing else key_text(p),
                       emboss=False).index = index

    def filter_items(self, context, data, propname):
        wm = context.window_manager  # the search box and filter popup above the list decide what shows
        flags = [self.bitflag_filter_item if listed(p) and _menu_matches(wm, p) else 0 for p in getattr(data, propname)]
        return flags, []

    def draw_filter(self, context, layout):
        pass  # filtered with the search box and filter button above the list


def draw_menu_path(prefs, layout, pie):
    """Above the editor: the menu you're in and the menus above it (click one to go back), then the
    submenus that belong to this menu (click one to edit it) and Add Submenu."""
    chain = owner_chain(prefs, pie)
    subs = submenus_of(prefs, pie.uid)
    index = {p.uid: i for i, p in enumerate(prefs.pies)}
    row = layout.row()
    row.alignment = 'LEFT'
    path = row.row(align=True)  # the path: plain text, the menus above it clickable
    path.alignment = 'LEFT'
    for up in chain:
        path.operator("keyops.pie_select", text=up.name, emboss=False).index = index[up.uid]
        path.label(text="", icon='RIGHTARROW_THIN')
    path.label(text=pie.name)
    if subs:
        row.separator(factor=1.0)
        dim = row.row()
        dim.alignment = 'LEFT'
        dim.active = False
        dim.label(text="Submenus:")
        buttons = row.row(align=True)  # the submenus: one joined strip of buttons
        buttons.alignment = 'LEFT'
        for sub in subs:
            buttons.operator("keyops.pie_select", text=sub.name.removeprefix(pie.name + ": ")).index = index[sub.uid]
    if pie.menu_type in ("MENU", "PIE", "DIALOG", "PANEL"):
        row.separator(factor=0.5)
        row.operator("keyops.submenu_add", text="Add Sub-pie" if pie.menu_type == "PIE" else "Add Submenu", icon='ADD')
        if pie.menu_type == "PIE":
            row.operator("keyops.submenu_add", text="Add Group", icon='MESH_PLANE').group = True


class KEYOPS_OT_submenu_add(Operator):
    bl_idname = "keyops.submenu_add"
    bl_label = "Add Submenu"
    bl_description = ("Make a submenu that belongs to this menu, and a button that opens it. In a pie menu "
                      "it's another pie (a sub-pie). It's edited from here and isn't a separate entry in the list")
    bl_options = {'INTERNAL'}

    group: BoolProperty(name="Group", default=False, options={'SKIP_SAVE'},
                        description="A group of buttons drawn in place (in a pie: several buttons in one direction) "
                                    "instead of a button that opens a menu") # type: ignore

    @classmethod
    def description(cls, context, props):
        if props.group:
            return ("Put a group of buttons here: in a pie, a column of buttons in one direction. Its buttons are "
                    "a small menu that belongs to this one; fill it after adding")
        return cls.bl_description

    def execute(self, context):
        prefs = get_keyops_prefs()
        parent = _active_pie(prefs)
        if parent is None:
            return {'CANCELLED'}
        n = len(submenus_of(prefs, parent.uid)) + 1
        # a pie opens another pie (a sub-pie, also in the Maya-style marking menu); other menus a popup menu.
        # A group is a popup menu drawn in place.
        kind = "PIE" if parent.menu_type == "PIE" and not self.group else "MENU"
        what = "Group" if self.group else ("Sub-pie" if kind == "PIE" else "Submenu")
        parent_uid = parent.uid
        sub = _new_pie(prefs)
        # adding to the list can move every menu in memory: find the parent again (the old reference can crash)
        parent = next(p for p in prefs.pies if p.uid == parent_uid)
        sub["enabled"], sub["menu_type"] = False, next(t[4] for t in MENU_TYPES if t[0] == kind)
        sub.name, sub.key, sub.editor, sub.owner = f"{parent.name}: {what} {n}", "NONE", parent.editor, parent.uid
        sub.items.clear()
        if kind == "PIE":
            for _i in range(ITEM_MIN["PIE"]):  # its 8 directions, empty, ready to fill
                sub.items.add().kind = N
        # the button in the parent: in a free pie slot, else at the end
        free = next((it for it in parent.items if _is_empty(it) and it.kind == N), None) if parent.menu_type == "PIE" else None
        if free is None and len(parent.items) < ITEM_LIMIT.get(parent.menu_type, 64):
            free = parent.items.add()
        if free is not None:
            free.kind, free.idname, free.label = SUB, sub.uid, f"{what} {n}"
            if self.group:
                free.sub_style, free.group_type, free.align, free.label = "INLINE", "COLUMN", True, ""
        prefs.active_pie = len(prefs.pies) - 1  # go into it, to fill it; the path above leads back
        _changed()
        sync_keymaps()
        return {'FINISHED'}


def draw_pies_tab(prefs, context, layout):
    if not prefs.pies:
        layout.label(text="No menus.")
        layout.operator("keyops.pie_preset_popup", text="Add Preset", icon='PRESET')
        return
    active = max(0, min(prefs.active_pie, len(prefs.pies) - 1))
    # fit the window: Blender's default Preferences window is small (about 520 px for this area)
    width = (context.region.width if context.region else 1600) / max(0.5, context.preferences.system.ui_scale)
    narrow, wide = width < 820, width >= 1350

    # the menu list: on the left, or on top in a narrow window
    if narrow:
        outer = layout.column()
        side = outer.column()
    else:
        outer = layout.split(factor=0.22 if wide else 0.3)
        side = outer.column()
    wm = context.window_manager
    srow = side.row(align=True)
    srow.prop(wm, "keyops_menu_filter", text="", icon='VIEWZOOM')
    srow.operator("keyops.pie_filter_popup", text="", icon='FILTER', depress=_filter_active(wm))
    lrow = side.row(align=False)
    # Blender's own list: click a row to edit that menu, double-click its name to rename, scroll, resize
    lrow.template_list("KEYOPS_UL_menus", "", prefs, "pies", prefs, "active_pie", rows=5 if narrow else 12)
    # beside the list, like Blender's own lists: add, remove, more, then move
    tools = lrow.column(align=True)
    tools.operator("keyops.pie_new_popup", text="", icon='ADD')
    tools.operator("keyops.pie_remove", text="", icon='REMOVE')
    tools.separator()
    tools.menu("KEYOPS_MT_menu_list_specials", text="", icon='DOWNARROW_HLT')
    tools.separator()
    tools.operator("keyops.pie_move", text="", icon='TRIA_UP').direction = -1
    tools.operator("keyops.pie_move", text="", icon='TRIA_DOWN').direction = 1
    if not any(listed(p) and _menu_matches(wm, p) for p in prefs.pies):
        empty = side.row()
        empty.active = False
        empty.label(text="No menus match")
    if not narrow:
        draw_pie_feel(prefs, side, prefs.pies[active])
        draw_values(context, side)
    layout = outer.column()

    pie = prefs.pies[active]
    draw_menu_path(prefs, layout, pie)
    box = layout.box()
    # header: where it works and Try It (its name and key are in the list on the left)
    box.separator(factor=0.3)
    head = box.row()
    names = editor_names(pie)
    where = head.row(align=True)
    where.alignment = 'LEFT'  # small, like Try It
    # one bar: every field has its name in front, the same width and look (icon, then the one picked or how many)
    _bar_label(where, "Works In")
    ed = where.row(align=True)
    ed.ui_units_x = BAR_FIELD_UNITS
    ed.prop_menu_enum(pie, "editor_set", text=_summary([_EDITOR_LABELS[n] for n in names], "Editors", "Nowhere"),
                      icon=_EDITOR_ICONS[names[0]] if len(names) == 1 else 'WORKSPACE')
    _bar_label(where, "Only In")  # ...and in which mode of it
    mode = where.row(align=True)
    mode.ui_units_x = BAR_FIELD_UNITS
    mode.prop_menu_enum(pie, "only_mode_set", text=only_mode_text(pie), icon=only_mode_icon(pie))
    _bar_label(where, "Preview")
    pv = where.row(align=True)
    pv.ui_units_x = BAR_FIELD_UNITS
    wm = context.window_manager
    pmode = next(m for m in PREVIEW_MODES if m[0] == wm.keyops_preview_mode)
    pv.popover("KEYOPS_PT_menu_preview_mode", text=pmode[1], icon=pmode[3])
    if pie.menu_type == "PANEL":
        _bar_label(where, "Tab")
        tab = where.row(align=True)
        tab.ui_units_x = BAR_FIELD_UNITS
        tab.prop(pie, "tab", text="", icon='MENU_PANEL')
        draw_panel_options(box, pie, prefs)

    box.separator(factor=0.8)
    # the preview, and the selected item's settings beside it (a wide window) or under it
    if wide:
        split = box.split(factor=0.62)
        left, right = split.column(), split.column()
    else:
        left = right = box.column()
    if menu_canvas.supported(pie):  # drawn as the real menu looks, with drag and drop (ui/menu_canvas.py)
        draw_canvas_overview(left, context, pie, prefs)
        tip = left.row()
        tip.alignment = 'CENTER'
        tip.active = False
        # what a click does where the mouse is (the icon spot, the label), else how the preview works
        tip.label(text=menu_canvas.hover_hint(context.region)
                  or "Click to edit, again for its operator. Drag to move. Right-click for more.")
    else:
        draw_pie_overview(left, pie, prefs)
    card_w = width * (0.78 if not narrow else 1.0) * (0.38 if wide else 1.0)
    draw_item_card(prefs, context, right, pie, compact=card_w < 430)
    draw_menu_settings(prefs, right, pie)
    if narrow:  # the pie settings and your values, under everything
        draw_pie_feel(prefs, layout, pie)
        draw_values(context, layout)



KIND_NAMES = {O: "Button", M: "Menu", P: "Setting", SUB: "Opens a Menu", SCRIPT: "Python", MACRO: "Macro",
              PANEL_ITEM: "Blender Panel", LABEL: "Label", BREAK: "Next Column", BOX: "Group", BOX_END: "End Group"}
KIND_ICONS = {O: 'RADIOBUT_OFF', M: 'MENU_PANEL', P: 'PROPERTIES', SUB: 'COLLAPSEMENU', SCRIPT: 'SCRIPT',
              MACRO: 'SEQUENCE', PANEL_ITEM: 'MENU_PANEL', LABEL: 'FONT_DATA', BREAK: 'CENTER_ONLY',
              BOX: 'META_PLANE', BOX_END: 'REMOVE'}


def item_title(pie, item):
    if item.kind == BOX:
        return GROUP_NAMES.get(item.group_type, "Group") + (f": {item.label}" if item.label.strip() else "")
    if _is_empty(item):
        return "Separator" if pie.menu_type != "PIE" else "Empty slot"
    if item.kind in (BREAK, BOX_END):
        return KIND_NAMES[item.kind]
    return item.label or action_name(item) or KIND_NAMES.get(item.kind, "Item")


def card_kind(pie, item):
    """The item card's heading: the kind of item (its name shows in the fields under it)."""
    if item.kind == BOX:
        return GROUP_NAMES.get(item.group_type, "Group")
    if _is_empty(item):
        return "Separator" if pie.menu_type != "PIE" else "Empty Slot"
    return KIND_NAMES.get(item.kind, "Item")


def look_options(pie, item):
    """The look settings Blender can apply to this item, so only those are offered."""
    k = item.kind
    if k in (BREAK, BOX_END) or (_is_empty(item) and k == N):
        return set()
    if k == BOX:
        return {"width", "height", "emboss", "alert", "active", "enabled"}
    if k == LABEL:
        return {"width", "height", "alert", "active", "enabled"}
    opts = {"width", "height", "emboss", "alert", "active", "enabled"}
    if k in (O, M, SUB, SCRIPT, MACRO):
        opts.add("depress")
    if k == P:
        opts.add("decorate")
        found = setting_rna(item)
        if found is not None and found[0].type == 'BOOLEAN' and item.setting_style in ("AUTO", "CHECKBOX"):
            opts.add("invert")
    if items_can_share_row(pie, list(pie.items).index(item)):
        opts.add("same_row")
    return opts


def _foldout(layout, data, prop, text):
    row = layout.row()
    row.alignment = 'LEFT'
    on = getattr(data, prop)
    row.prop(data, prop, text=text, icon='DOWNARROW_HLT' if on else 'RIGHTARROW', emboss=False)
    return on


def draw_item_card(prefs, context, layout, pie, compact=False):
    """The selected item: the things you change most, then Advanced for the rest.
    compact: little room (a small Preferences window): icons and dropdowns instead of rows of buttons."""
    if not len(pie.items):
        _note(layout.box(), "Empty: use Add under the preview to put in a button, label or group")
        return
    slot = max(0, min(prefs.pie_slot, len(pie.items) - 1))
    item = pie.items[slot]
    is_menu = pie.menu_type != "PIE"
    box = layout.box()
    col = box.column()
    # moving, copying and removing the item are in its right-click menu in the preview
    k = item.kind
    if k == BREAK:
        _note(col, "The items after this go in the next column")
    elif k == BOX_END:
        _note(col, "Ends the group above: the items after this are outside it")
    elif k == BOX:
        if compact:
            col.prop(item, "group_type", text="")
        else:
            col.row(align=True).prop(item, "group_type", expand=True)
        r = col.row(align=True)
        r.prop(item, "label", text="", icon='FONT_DATA', placeholder="Heading") if bpy.app.version >= (4, 1, 0) \
            else r.prop(item, "label", text="Heading")
        r = col.row(align=True)
        r.prop(item, "align", toggle=True, icon='SNAP_EDGE')
        if item.group_type == "SPLIT":
            r.prop(item, "factor", slider=True)
        elif item.group_type == "GRID":
            r.prop(item, "grid_columns")
        elif item.group_type == "PANEL":
            r.prop(item, "closed", toggle=True)
        if compact:
            col.prop(item, "alignment", text="")
        else:
            col.row(align=True).prop(item, "alignment", expand=True)
    elif _is_empty(item) and k == N and is_menu:
        r = col.row(align=True)
        r.prop(item, "sep_type", expand=True)
        r.prop(item, "sep_factor")
        op = col.operator("keyops.pie_slot_search", text="Operator", icon='VIEWZOOM')
        op.slot, op.scope = slot, "ALL"
    elif k == LABEL:
        r = col.row(align=True)
        r.prop(item, "label", text="")
        r.operator("keyops.pie_icon_picker", text="", **icon_kw(item.icon or 'IMAGE_DATA')).slot = slot
    else:
        if k == MACRO:
            r = col.row(align=True)
            r.scale_y = 1.2
            r.label(text=item.label or "Macro", icon='SEQUENCE')
        # what it runs is picked with the type buttons above and the search beside the Operator field
        # a setting drawn as a checkbox shows no icon in Blender: no icon button then
        icon_ok = not (k == P and item.setting_style == "CHECKBOX")
        if not _is_empty(item) and icon_ok:
            # its label, then its icon (click to change it): names on the left, both lined up like the
            # Operator and Poll rows below
            # its icon (a button showing it, + when it has none: click to change it) joined to its label
            r = _field(col, "Label")
            r.operator("keyops.pie_icon_picker", text="", **icon_kw(item.icon or 'ADD')).slot = slot
            _prop_hint(r, item, "label", "", "", "No label: icon only")
        if k == MACRO:  # its steps, stacked in the order they run
            draw_macro_steps(col, item, slot, pie)

    looks = look_options(pie, item)
    toggles = [(n, i) for n, i in (("emboss", 'MESH_PLANE'), ("alert", 'ERROR'), ("active", 'HIDE_OFF'),
                                   ("enabled", 'RESTRICT_SELECT_OFF'), ("depress", 'CHECKBOX_HLT'),
                                   ("same_row", 'SNAP_EDGE'), ("invert", 'ARROW_LEFTRIGHT'),
                                   ("decorate", 'DECORATE_KEYFRAME')) if n in looks]
    if k not in (BREAK, BOX_END):
        col.separator(factor=0.6)
        adv = col.column()  # what it is and runs: always shown, it's what the item does
        draw_item_advanced(context, adv, pie, item, slot, looks)
        if item.kind == O:
            _field(adv, "Run As").prop(item, "call_mode", text="")
            if item.idname.strip() == "keyops.toggle_ui_element":
                adv.operator("keyops.pick_ui_element", text="Pick Blender UI to Hide", icon='HIDE_ON').slot = slot
        inline = item.kind == O and item.idname.strip() != "keyops.toggle_ui_element" \
            and bool(item.idname.strip()) and _op_rna(item.idname) is not None
        if inline or has_operator_settings(item):
            col.separator(factor=0.6)
            if _foldout(col, prefs, "pie_show_op_params", "Operator Parameters"):
                # one panel: the operator's own options, then the settings Key Ops keeps for it (if any)
                pbox = col.box().column()
                extra = (lambda lay: draw_operator_settings(prefs, lay, item)) if has_operator_settings(item) else None
                if inline:
                    draw_inline_params(pbox, pie, slot, -1, item, extra)
                elif extra is not None:
                    extra(pbox)
    # how it's drawn: last, right above the menu's own settings
    draws_as = not _is_empty(item) and k in (P, M, SUB, O)
    if toggles or "width" in looks or draws_as:
        col.separator(factor=0.6)
        if _foldout(col, prefs, "pie_show_drawing", "Drawing"):
            dbox = col.box()
            if draws_as:
                draw_item_draw_as(dbox.column(), item, compact)
            line = dbox.row()  # the look toggles, then the size, on one row
            if toggles:
                r = line.row(align=True)
                for name, icon in toggles:
                    if compact:  # just the icons (each has its name as a tooltip)
                        r.prop(item, name, toggle=True, icon=icon, text="")
                    else:
                        r.prop(item, name, toggle=True, icon=icon)
            if "width" in looks:
                r = line.row(align=True)
                r.prop(item, "width", text="X")
                r.prop(item, "height", text="Y")


def draw_item_draw_as(col, item, compact=False):
    """Draw As: how a setting, menu, submenu or operator item is drawn (a button, a dropdown, a group...),
    with the extra field some styles need. Part of the item card's Drawing section."""
    k = item.kind
    if k == P:
        col.prop(item, "setting_style", text="Draw As")
        if item.setting_style in SETTING_SOURCE:
            name, hint = SETTING_SOURCE[item.setting_style]
            _prop_hint(_field(col, name), item, "source", "", "", hint)
    elif k == M:
        col.prop(item, "menu_style", text="Draw As")
    elif k == SUB:
        if compact:
            col.prop(item, "sub_style", text="Draw As")
        else:
            col.row(align=True).prop(item, "sub_style", expand=True)
        if item.sub_style == "INLINE":
            r = col.row(align=True)
            r.prop(item, "group_type", text="")
            r.prop(item, "align", toggle=True, icon='SNAP_EDGE')
    elif k == O:
        col.prop(item, "op_style", text="Draw As")
        if item.op_style != "BUTTON":
            _prop_hint(_field(col, "Option"), item, "enum_prop", "", "", "The operator's choice option, e.g. type")


def has_operator_settings(item):
    """True when Key Ops keeps settings for this item's operator (see draw_operator_settings)."""
    return item.kind == O and item.idname.strip() in ("keyops.add_mesh",)


def draw_operator_settings(prefs, layout, item):
    """Settings Key Ops keeps for one of its own operators, shown only with that operator."""
    if item.idname.strip() == "keyops.add_mesh":
        col = layout.column()
        col.prop(prefs, "add_object_pie_use_relative")
        sub = col.column()
        sub.active = prefs.add_object_pie_use_relative
        sub.prop(prefs, "add_object_pie_relative_scale")
        col.prop(prefs, "add_object_pie_default_scale")


def draw_panel_options(layout, pie, prefs):
    """A sidebar panel's header: its icon, hidden or closed at first, its order, and the panel it sits in."""
    row = layout.row(align=True)
    row.alignment = 'LEFT'
    ic = row.row(align=True)
    ic.alignment = 'LEFT'  # label and button at their own width, not stretched across the row
    ic.ui_units_x = 3
    ic.label(text="Icon:")
    ic.operator("keyops.panel_icon_picker", text="", emboss=False, **icon_kw(pie.panel_icon.strip() or 'IMAGE_DATA'))
    row.prop(pie, "panel_hide_header", toggle=True)
    row.prop(pie, "panel_closed", toggle=True)
    order = row.row(align=True)
    order.ui_units_x = 5
    order.prop(pie, "panel_order")
    inside = row.row(align=True)
    inside.ui_units_x = 8
    parent = find_pie(pie.panel_parent.strip())
    inside.operator_menu_enum("keyops.panel_parent_pick", "target", icon='MENU_PANEL',
                              text=f"Inside {parent.name}" if parent else "Own Panel")


def _parent_choices(self, context):
    prefs = get_keyops_prefs()
    me = _active_pie(prefs)
    out = [("NONE", "Own Panel", "A panel of its own, not inside another", 'BLANK1', 0)]
    for n, p in enumerate(prefs.pies):
        if p.menu_type == "PANEL" and (me is None or p.uid != me.uid):
            out.append((p.uid, p.name or "Panel", f"Show inside \"{p.name}\" as a sub-panel", 'MENU_PANEL', n + 1))
    return out


class KEYOPS_OT_panel_parent_pick(Operator):
    bl_idname = "keyops.panel_parent_pick"
    bl_label = "Inside"
    bl_description = "Show this sidebar panel as a sub-panel inside another of your sidebar panels"
    bl_options = {'INTERNAL'}
    target: EnumProperty(name="Inside", items=_parent_choices) # type: ignore

    def execute(self, context):
        pie = _active_pie(get_keyops_prefs())
        if pie is None:
            return {'CANCELLED'}
        pie.panel_parent = "" if self.target == "NONE" else self.target
        return {'FINISHED'}


def _note(layout, text):
    r = layout.row()
    r.active = False
    r.label(text=text)


def draw_item_advanced(context, col, pie, item, slot, looks):
    """Less used: what kind of item it is, its command, Python and macros, when it shows."""
    k = item.kind
    if k == BOX:
        col.prop(item, "prop_split")
        return
    _field(col, "Type").prop(item, "item_type", text="")
    if k in (SCRIPT, DRAW):
        if k == DRAW:
            _note(col, "Runs on every redraw. Names: layout, context (C), bpy, D, icon(\"keyops:name\")")
        lines = item.script.rstrip("\n").split("\n")
        if len(lines) > 1:  # longer scripts: a read-only preview, edited in the Text Editor
            pre = col.box().column(align=True)
            pre.scale_y = 0.8
            for line in lines[:8]:
                pre.label(text=line.replace("\t", "    ") or " ")
            if len(lines) > 8:
                _note(pre, f"... {len(lines) - 8} more lines")
        else:
            col.prop(item, "script", text="", icon='SCRIPT')
        r = col.row(align=True)
        r.operator("keyops.script_edit", text="Edit in Text Editor", icon='TEXT')
        r.operator("keyops.script_save", text="Save to Item", icon='FILE_TICK')
    elif k == O:
        # One line: operator and options, e.g. bpy.ops.mesh.primitive_cube_add(size=2). Takes pasted Info commands too.
        row = _field(col, "Operator")
        _prop_hint(row, item, "command", "", "",
                   "Paste from the Info editor or Python Console, e.g. bpy.ops.mesh.primitive_cube_add(size=2)")
        op = row.operator("keyops.pie_slot_search", text="", icon='VIEWZOOM')  # or pick it from every operator
        op.slot, op.scope = slot, "OPERATORS"
    elif k in (M, PANEL_ITEM):
        row = _field(col, "Menu" if k == M else "Panel")
        _prop_hint(row, item, "idname", "", "",
                   "e.g. VIEW3D_MT_add" if k == M else "e.g. VIEW3D_PT_overlay")
        op = row.operator("keyops.pie_slot_search", text="", icon='VIEWZOOM')
        op.slot, op.scope = slot, "ALL" if k == M else "PANELS"
    elif k == SUB:
        target = find_pie(item.idname)
        op = _field(col, "Opens").operator("keyops.pie_slot_search", text=target.name if target else "Pick a menu",
                                           icon='VIEWZOOM')
        op.slot, op.scope = slot, "KEYOPS"
    elif k != LABEL:
        if k == P:
            _field(col, "Setting").prop(item, "idname", text="")
            found = setting_rna(item, context)
            if found is not None and getattr(found[0], "array_length", 0):  # location, color, a layer mask
                _field(col, "Index").prop(item, "index", text="Index" if item.index >= 0 else "All Values")
            _prop_hint(_field(col, "Options"), item, "props", "", "",
                       "rows=6 for a List, scale=3.5 for an Icon Picker")
        if k in (MACRO, N):  # a pasted command adds a macro step, or turns an empty slot into it
            _prop_hint(col, context_wm(), "keyops_paste_command", "", 'PASTEDOWN',
                       "Paste a command from Blender's Info editor")
    if pie.menu_type == "PANEL" and k not in LAYOUT_KINDS:
        col.prop(item, "in_header")
    r = _field(col, "Poll")
    _prop_hint(r, item, "show_if", "", 'HIDE_OFF', "Show only when true, e.g. mode == 'EDIT_MESH'")
    from .features import DOCS_URL
    r.operator("wm.url_open", text="", icon='QUESTION').url = DOCS_URL + "pie-menus.html#poll"


FIELD_SPLIT = 0.25  # the item settings' name column, shared by every row so they line up


def _field(layout, text):
    """A settings row: 'text:' in the name column, returns the row on the right for its widgets."""
    sp = layout.split(factor=FIELD_SPLIT)
    sp.label(text=f"{text}:")
    return sp.row(align=True)


def _icon_button(layout, item, slot):
    """One entry, 'Icon' with the item's current icon: click it to pick another. A single button, since a row
    (label and button) splits Blender's popup menus into columns."""
    layout.operator("keyops.pie_icon_picker", text="Icon", **icon_kw(item.icon or 'IMAGE_DATA')).slot = slot


def _prop_hint(layout, owner, prop, text, icon, hint):
    """A text setting with a grey hint inside it while empty (Blender 4.1+)."""
    if bpy.app.version >= (4, 1, 0):
        layout.prop(owner, prop, text=text, icon=icon or 'NONE', placeholder=hint)
    else:
        layout.prop(owner, prop, text=text, icon=icon or 'NONE')


def _prop_with_help(layout, owner, prop, text, icon, docs_page, hint=""):
    """A setting with a ? button after it that opens its page in the docs."""
    from .features import DOCS_URL
    row = layout.row(align=True)
    _prop_hint(row, owner, prop, text, icon, hint)
    row.operator("wm.url_open", text="", icon='QUESTION').url = DOCS_URL + docs_page


def draw_menu_settings(prefs, layout, pie):
    """The menu's own settings, folded away."""
    pbox = layout.box()
    if not _foldout(pbox, prefs, "pie_show_settings", "Menu Settings"):
        return
    c = pbox.column()
    c.use_property_split = True
    c.use_property_decorate = False
    c.separator(factor=0.3)
    _prop_with_help(c, pie, "condition", "Show When", 'SCRIPT', "pie-menus.html#poll",
                    "Open only when true, e.g. obj and obj.type == 'MESH'")
    if pie.menu_type not in {"PANEL", "STICKY", "MODAL"}:
        c.prop(pie, "key_event", text="Opens On")
    if pie.menu_type != "PANEL":
        c.prop(pie, "key_mod", text="While Holding")
    if pie.menu_type in {"DIALOG", "PANEL"}:
        c.prop(pie, "columns")
    if pie.menu_type == "DIALOG":
        c.row().prop(pie, "dialog_mode", expand=True)
    if pie.menu_type == "STACK":
        c.prop(pie, "stack_reset")
    if pie.menu_type in ("PIE", "MENU", "DIALOG"):  # these can sit in Blender's own menus, headers and panels
        c.prop(pie, "append_to", text="Add To", icon='ADD')
    if pie.menu_type in ("PIE", "MENU", "DIALOG") and pie.append_to.strip():
        c.row().prop(pie, "append_as", expand=True)
        if not hasattr(bpy.types, pie.append_to.strip()):
            warn = c.row()
            warn.alert = True
            warn.label(text="Blender has no menu, header or panel with that name", icon='ERROR')
    if pie.menu_type == "PIE" and prefs.pie_style == "MARKING":  # Blender's pies take these from its preferences
        feel = c.column(align=True)
        feel.prop(pie, "radius", text="Size")
        feel.prop(pie, "threshold", text="Flick Distance")
    if pie.preset in PRESET_BY_ID:
        c.separator(factor=0.5)
        c.operator("keyops.pie_reset", text="Reset to Preset", icon='LOOP_BACK')


def draw_values(context, layout):
    """My Properties: numbers, toggles, text and choices of your own that items, tests and scripts can use."""
    prefs = get_keyops_prefs()
    box = layout.box()
    row = box.row()
    row.alignment = 'LEFT'
    row.prop(prefs, "pie_show_values", text="My Properties", emboss=False,
             icon='DOWNARROW_HLT' if prefs.pie_show_values else 'RIGHTARROW')
    if not prefs.pie_show_values:
        return
    vals = context.window_manager.keyops_values
    for i, v in enumerate(vals):
        col = box.column(align=True)
        r = col.row(align=True)
        r.prop(v, "vtype", text="", icon_only=True)
        r.prop(v, "owner", text="", icon_only=True)
        r.prop(v, "name", text="")
        r.prop(v, v.field, text="")
        r.operator("keyops.value_remove", text="", icon='X').index = i
        if v.vtype == "ENUM":
            col.prop(v, "choices", text="", icon='PRESET')
        note = col.row()
        note.active = False
        note.scale_y = 0.8
        note.label(text=v.path if v.owner == "ADDON" else f"{v.path}  (value above: its default)")
    box.operator("keyops.value_add", text="Add Property", icon='ADD')
    if vals:
        note = box.column(align=True)
        note.active = False
        note.label(text="Use the path in a Setting item. Tests and Draw Code: values[\"Name\"]")


PIE_TIMEOUT_DEFAULT = 6  # Blender's default pie animation timeout


def _get_no_lag(self):
    return bpy.context.preferences.view.pie_animation_timeout == 0


def _set_no_lag(self, value):
    bpy.context.preferences.view.pie_animation_timeout = 0 if value else PIE_TIMEOUT_DEFAULT


def draw_pie_feel(prefs, layout, pie=None):
    """The no-lag option. It's Blender's own pie animation setting, shown here so it's easy to find:
    the person changes it, Key Ops never writes Blender's preferences itself.
    Only shown while the selected menu is a pie menu."""
    if pie is not None and pie.menu_type != "PIE":
        return
    box = layout.box()
    box.label(text="Pie Menu Settings")
    box.prop(bpy.context.window_manager, "keyops_no_lag_pies")
    row = box.row(align=True)
    row.label(text="Style")
    row.prop(prefs, "pie_style", expand=True)
    if prefs.pie_style == "MARKING":
        look = box.row()
        look.alignment = 'LEFT'
        look.prop(prefs, "pie_show_marking", emboss=False,
                  icon='DOWNARROW_HLT' if prefs.pie_show_marking else 'RIGHTARROW')
        if prefs.pie_show_marking:
            from . import marking_menu
            marking_menu.draw_look_settings(prefs, box.column())


def context_wm():
    return bpy.context.window_manager


def draw_macro_steps(layout, item, slot, pie=None):
    box = layout.box()
    head = box.row()
    head.label(text="Steps")
    note = head.row()
    note.alignment = 'RIGHT'
    note.active = False
    note.label(text="Run top to bottom, one undo step")
    for n, step in enumerate(item.steps):
        r = box.row(align=True)
        num = r.row()
        num.ui_units_x = 1.2
        num.label(text=f"{n + 1}")
        op = r.operator("keyops.pie_slot_search", text=step_name(step) or "Pick an operator", icon='VIEWZOOM')
        op.slot, op.scope, op.step = slot, "ALL", n
        r.prop(step, "props", text="", placeholder="Options") if bpy.app.version >= (4, 1, 0) else r.prop(step, "props", text="")
        shown = _open_step["slot"] == slot and _open_step["step"] == n and pie is not None
        prm = r.operator("keyops.macro_step_params", text="", icon='DOWNARROW_HLT' if shown else 'PREFERENCES',
                         depress=shown)
        prm.slot, prm.step = slot, n
        r.prop(step, "interactive", text="", icon='RESTRICT_SELECT_OFF', toggle=True)
        for icon, d in (('TRIA_UP', -1), ('TRIA_DOWN', 1)):
            mv = r.operator("keyops.macro_step_move", text="", icon=icon)
            mv.step, mv.direction = n, d
        r.operator("keyops.macro_step_remove", text="", icon='X').step = n
        if shown and _op_rna(step.idname or "") is not None:
            draw_inline_params(box.box(), pie, slot, n, step)
    box.operator("keyops.macro_step_add", text="Add Step", icon='ADD')


property_classes = (KeyOpsValue, KeyOpsMacroStep, KeyOpsPieItem, KeyOpsPie, KeyOpsExportChoice)
classes = (KEYOPS_OT_panel_parent_pick, KEYOPS_MT_pie_submenu, KEYOPS_OT_submenu_add, WM_OT_keyops_run_script, KEYOPS_OT_script_edit, KEYOPS_OT_script_save, KEYOPS_OT_slot_set_kind,
           KEYOPS_OT_pie_duplicate, KEYOPS_OT_value_add, KEYOPS_OT_value_remove,
           WM_OT_keyops_call_pie, WM_OT_keyops_run_macro, KEYOPS_OT_menu_item_add, KEYOPS_OT_menu_item_remove,
           KEYOPS_OT_menu_item_insert, KEYOPS_MT_item_insert, KEYOPS_OT_item_options, KEYOPS_OT_item_wrap, KEYOPS_MT_item_add,
           KEYOPS_OT_add_button_to_menu, KEYOPS_MT_add_to_menu, KEYOPS_MT_add_to_where, KEYOPS_OT_menu_append_here,
           KEYOPS_OT_panel_to_menu, KEYOPS_MT_extend_here, *_here_menu_classes,
           KEYOPS_OT_item_ungroup, KEYOPS_MT_item_wrap,
           KEYOPS_OT_menu_item_move, KEYOPS_OT_slot_make_macro, KEYOPS_OT_macro_step_add, KEYOPS_OT_macro_step_remove,
           KEYOPS_OT_macro_step_move, KEYOPS_OT_operator_params, KEYOPS_PT_menu_preview_mode, KEYOPS_OT_operator_params_reset, KEYOPS_OT_macro_step_params, KEYOPS_OT_pie_new_popup, KEYOPS_OT_pie_move, KEYOPS_OT_component_mode, KEYOPS_OT_slot_swap, KEYOPS_OT_slot_copy, KEYOPS_OT_slot_paste, KEYOPS_OT_pie_filter_popup, KEYOPS_OT_pie_filter_clear, KEYOPS_OT_pie_select, KEYOPS_OT_pie_add, KEYOPS_OT_pie_remove,
           KEYOPS_OT_pie_reset, KEYOPS_OT_pie_set_key, KEYOPS_OT_pie_preset_popup, KEYOPS_OT_pie_slot_search,
           KEYOPS_OT_pie_slot_select, KEYOPS_PT_icon_palette, KeyOpsIconRow, KEYOPS_UL_icon_rows, KEYOPS_UL_menus, KEYOPS_MT_menu_list_specials, KEYOPS_OT_pie_icon_picker, KEYOPS_OT_panel_icon_picker, KEYOPS_OT_pie_set_icon, KEYOPS_OT_pie_icon_search,
           KEYOPS_OT_settings_export, KEYOPS_OT_settings_import)


def register_properties():
    for cls in property_classes:
        bpy.utils.register_class(cls)


def unregister_properties():
    for cls in reversed(property_classes):
        bpy.utils.unregister_class(cls)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    from . import marking_menu
    marking_menu.register()
    menu_canvas.register()
    menu = _button_context_menu()
    if menu is not None:
        menu.append(_button_context_draw)
    bpy.types.WindowManager.keyops_export_menus = CollectionProperty(type=KeyOpsExportChoice)
    bpy.types.WindowManager.keyops_values = CollectionProperty(type=KeyOpsValue)
    bpy.types.WindowManager.keyops_preview_mode = EnumProperty(
        name="Preview In", items=PREVIEW_MODES, default='EDITING', options={'SKIP_SAVE'},
        description="Show the preview as the menu looks in this mode: items whose Poll is false there are hidden",
        update=_redraw_all_areas)
    bpy.types.WindowManager.keyops_menu_filter = StringProperty(
        name="Find Menu", description="Search menus by name or key", options={'TEXTEDIT_UPDATE'})
    bpy.types.WindowManager.keyops_menu_filter_types = EnumProperty(
        name="Type", options={'ENUM_FLAG'}, description="Show only these menu types. None picked shows all",
        items=_menu_type_filter_items)
    bpy.types.WindowManager.keyops_menu_filter_state = EnumProperty(name="Show", items=[
        ("ALL", "All", "Enabled and disabled menus"),
        ("ON", "Enabled", "Only menus whose checkbox in the list is ticked"),
        ("OFF", "Disabled", "Only menus whose checkbox in the list is not ticked")])
    bpy.types.WindowManager.keyops_menu_filter_tag = StringProperty(
        name="Tag", description="Show only menus with this tag",
        search=lambda self, context, text: [t for t in all_tags() if text.strip().lower() in t])
    bpy.types.WindowManager.keyops_menu_filter_editor = EnumProperty(
        name="Works In", items=[("ANY", "Anywhere", "Menus for any editor", 'WORLD', 0)] + [(e[0], e[1], e[2], e[3], i + 1) for i, e in enumerate(EDITORS)])
    bpy.types.WindowManager.keyops_script_text = StringProperty()
    bpy.types.WindowManager.keyops_no_lag_pies = BoolProperty(
        name="No Lag Pies", get=_get_no_lag, set=_set_no_lag,
        description="Open pie menus instantly, with no opening animation. Changes Blender's Pie Menu Animation Timeout")
    bpy.types.WindowManager.keyops_paste_command = StringProperty(
        name="Paste Command", description="Paste a bpy.ops command copied from Blender's Info editor", update=_paste_command)
    bpy.types.WindowManager.keyops_icon_filter = StringProperty(
        name="Search Icons", description="Type part of an icon's name, e.g. cube or snap", options={'TEXTEDIT_UPDATE'},
        update=_icon_rows_update)
    bpy.types.WindowManager.keyops_icon_rows = CollectionProperty(type=KeyOpsIconRow)
    bpy.types.WindowManager.keyops_icon_row_index = IntProperty(default=-1, update=_icon_row_index_update)
    bpy.types.WindowManager.keyops_icon_category = EnumProperty(
        name="Category", items=[(c[0], c[1], f"{c[1]} icons") for c in ICON_CATEGORIES] + [("OTHER", "Other", "Everything else")],
        update=_icon_rows_update)
    sync_keymaps()


def unregister():
    remove_user_panels()
    if bpy.app.timers.is_registered(_inline_sync):
        bpy.app.timers.unregister(_inline_sync)
    _inline["pending"] = False
    _inline_close()
    menu = _button_context_menu()
    if menu is not None:
        try:
            menu.remove(_button_context_draw)
        except (ValueError, RuntimeError):
            pass
    _remove_appends()
    from . import settings_store
    settings_store.flush_now()  # don't lose a change made just before disabling
    _remove_pie_keymaps()
    del bpy.types.WindowManager.keyops_icon_category
    del bpy.types.WindowManager.keyops_icon_filter
    del bpy.types.WindowManager.keyops_icon_rows
    del bpy.types.WindowManager.keyops_icon_row_index
    del bpy.types.WindowManager.keyops_paste_command
    del bpy.types.WindowManager.keyops_export_menus
    remove_custom_props()
    del bpy.types.WindowManager.keyops_values
    del bpy.types.WindowManager.keyops_preview_mode
    del bpy.types.WindowManager.keyops_menu_filter
    del bpy.types.WindowManager.keyops_menu_filter_types
    del bpy.types.WindowManager.keyops_menu_filter_state
    del bpy.types.WindowManager.keyops_menu_filter_editor
    del bpy.types.WindowManager.keyops_menu_filter_tag
    del bpy.types.WindowManager.keyops_script_text
    del bpy.types.WindowManager.keyops_no_lag_pies
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    menu_canvas.unregister()
    from . import marking_menu
    marking_menu.unregister()


def values_to_data(prefs):
    out = []
    for v in bpy.context.window_manager.keyops_values:
        out.append({"name": v.name, "type": v.vtype, "value": getattr(v, v.field), "owner": v.owner,
                    "choices": v.choices})
    return {"values": out}


def values_from_data(prefs, data, merge):
    global _loading
    _loading = True
    try:
        vals = bpy.context.window_manager.keyops_values
        if not merge:
            vals.clear()
        for entry in data.get("values", []):
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            v = vals.get(entry["name"]) or vals.add()
            v.name = entry["name"]
            try:
                v.vtype = entry.get("type", "FLOAT")
                v.owner = entry.get("owner", "ADDON")
                v.choices = entry.get("choices", v.choices)
                if v.vtype == "ENUM":
                    v.string_value = str(entry.get("value") or "")
                else:
                    setattr(v, v.field, entry.get("value"))
            except (TypeError, ValueError):
                pass
    finally:
        _loading = False
    schedule_custom_props_sync()


def _register_section():
    from . import settings_store
    settings_store.register_section("pie_menus", pies_to_data, pies_from_data, own_file=True,
                                    schema=PIE_SCHEMA, migrations=PIE_MIGRATIONS)
    settings_store.register_section("values", values_to_data, values_from_data, own_file=True, schema=1)


_register_section()
