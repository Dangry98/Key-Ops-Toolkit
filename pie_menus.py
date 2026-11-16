"""User-editable pie menus.

Every Key Ops pie is now a preset stored in the add-on preferences: users can
change any slot, change its key, and add pies of their own. One operator
(wm.keyops_call_pie) opens any of them, and each enabled pie gets one Key Ops
keymap item in keyconfigs.addon. The user's keymap is never edited.
"""

import ast
import uuid

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator, PropertyGroup

from .utils.pref_utils import get_keyops_prefs

# Blender's pie order: the 8 slots are filled in this sequence
ORDER = ("W", "E", "S", "N", "NW", "NE", "SW", "SE")
POSITION_NAMES = {"W": "Left", "E": "Right", "S": "Bottom", "N": "Top",
                  "NW": "Top Left", "NE": "Top Right", "SW": "Bottom Left", "SE": "Bottom Right"}
GRID = ("NW", "N", "NE", "W", None, "E", "SW", "S", "SE")

EDITORS = (
    ("3D View Generic", "3D Viewport", "Any mode in the 3D Viewport"),
    ("Object Mode", "Object Mode", "Only in Object Mode"),
    ("Mesh", "Edit Mesh", "Only in mesh Edit Mode"),
    ("UV Editor", "UV Editor", "Only in the UV Editor"),
    ("Window", "Everywhere", "In every editor"),
)

O, M, P, N = "OPERATOR", "MENU", "PROPERTY", "NONE"
_ = (N, "", "", "", "")


def _op(label, icon, idname, props=""):
    return (O, label, icon, idname, props)


PRESETS = (
    dict(id="add_objects", name="Add Objects", editor="3D View Generic", key="A", shift=True, alt=True,
         styles={"BLENDER_PLUS", "INDUSTRY"}, items=(
             _op("UV Sphere", "SHADING_WIRE", "keyops.add_mesh", "mesh_type='UVSPHERE'"),
             _op("Cube", "MESH_CUBE", "keyops.add_mesh", "mesh_type='CUBE'"),
             _op("Cylinder", "MESH_CYLINDER", "keyops.add_mesh", "mesh_type='CYLINDER'"),
             _op("Plane", "MESH_PLANE", "keyops.add_mesh", "mesh_type='PLANE'"),
             _op("Mod Cylinder", "MOD_SCREW", "keyops.add_mesh", "mesh_type='MODCYLINDER'"),
             (M, "Other", "ADD", "VIEW3D_MT_add", ""),
             _op("Quad Sphere", "MESH_UVSPHERE", "keyops.add_mesh", "mesh_type='QUADSPHERE'"),
             _op("Circle", "MESH_CIRCLE", "keyops.add_mesh", "mesh_type='CIRCLE'"))),
    dict(id="add_modifier", name="Add Modifier", editor="Window", key="Q", shift=True,
         styles={"BLENDER_PLUS", "INDUSTRY"}, items=(
             _op("Array", "MOD_ARRAY", "keyops.fast_array"),
             _op("Solidify", "MOD_SOLIDIFY", "keyops.fast_solidify"),
             _op("Bevel", "MOD_BEVEL", "keyops.fast_bevel"),
             _op("Weighted Normal", "MOD_NORMALEDIT", "keyops.add_modifier", "type='WEIGHTED_NORMAL'"),
             _op("Lattice", "MOD_LATTICE", "keyops.add_modifier", "type='LATTICE'"),
             _op("Weld", "AUTOMERGE_OFF", "keyops.add_modifier", "type='WELD'"),
             _op("Triangulate", "MOD_TRIANGULATE", "keyops.add_modifier", "type='TRIANGULATE'"),
             _op("Shrinkwrap", "MOD_SHRINKWRAP", "keyops.add_modifier", "type='SHRINKWRAP'"))),
    dict(id="flatten", name="Flatten", editor="Mesh", key="THREE", alt=True,
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
    dict(id="workspace", name="Workspaces", editor="Window", key="BACK_SLASH", shift=True, styles=set(), items=tuple(
        _op(label, icon, "keyops.switch_workspace", f"workspace_name='{ws}'") for label, icon, ws in (
            ("Layout", "GRID", "Layout"), ("Modeling", "EDITMODE_HLT", "Modeling"), ("Shading", "MATERIAL", "Shading"),
            ("UV Editor", "UV", "UV Editing"), ("Scripting", "SCRIPT", "Scripting"),
            ("Texture Paint", "BRUSHES_ALL", "Texture Paint"), ("Geometry Nodes", "GEOMETRY_NODES", "Geometry Nodes"),
            ("Sculpting", "SCULPTMODE_HLT", "Sculpting")))),
    dict(id="utility", name="Utility", editor="3D View Generic", key="U", styles=set(), items=(
        (P, "Live Unwrap", "", "scene.tool_settings.use_edge_path_live_unwrap", ""),
        (M, "UV Mapping", "", "VIEW3D_MT_uv_map", ""),
        _op("Seam by Angle", "MOD_EDGESPLIT", "keyops.seam_by_angle"),
        _op("Unfold and Pack", "UV_FACESEL", "uv.unwrap"),
        (P, "Correct Face Attributes", "", "scene.tool_settings.use_transform_correct_face_attributes", ""),
        _op("Make Single User", "", "keyops.make_single_user"),
        (P, "Auto Merge", "", "scene.tool_settings.use_mesh_automerge", ""), _)),
    dict(id="uv_space", name="UV Unwrap", editor="UV Editor", key="SPACE", styles=set(), items=(
        _op("Straighten Quads", "UV_ISLANDSEL", "keyops.streighten_selection"),
        _op("Isolate Island", "", "keyops.isolate_uv_island"),
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
        _op("Sharp Edges from Islands", "MOD_EDGESPLIT", "keyops.sharp_from_uv_islands"),
        _op("Seams from Islands", "", "uv.seams_from_islands"),
        _op("Mirror Selected Seams", "MOD_MIRROR", "keyops.mirror_seams"),
        _op("Select Similar Islands", "", "keyops.select_similar_islands"), _)),
)
PRESET_BY_ID = {p["id"]: p for p in PRESETS}

_ICONS = set(bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys())
_KEY_NAMES = {i.identifier: i.name for i in bpy.types.KeyMapItem.bl_rna.properties["type"].enum_items}
_MODIFIER_KEYS = {"LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_ALT", "RIGHT_ALT", "OSKEY"}


def _sync_update(self, context):
    sync_keymaps()


# ---------------------------------------------------------------- data

class KeyOpsPieItem(PropertyGroup):
    kind: EnumProperty(name="Type", items=(
        (N, "Empty", "Leave this slot empty"),
        (O, "Operator", "Run an operator, e.g. mesh.primitive_cube_add"),
        (M, "Menu", "Open a menu, e.g. VIEW3D_MT_add"),
        (P, "Toggle", "Toggle a setting, e.g. scene.tool_settings.use_snap"))) # type: ignore
    label: StringProperty(name="Label") # type: ignore
    icon: StringProperty(name="Icon", description="Blender icon name, e.g. MESH_CUBE. Leave empty for no icon") # type: ignore
    idname: StringProperty(name="Command", description="Operator id, menu id or setting path") # type: ignore
    props: StringProperty(name="Options", description="Operator options, e.g. type='WELD', segments=4") # type: ignore


class KeyOpsPie(PropertyGroup):
    uid: StringProperty() # type: ignore
    name: StringProperty(name="Name", default="New Pie") # type: ignore
    preset: StringProperty(description="Preset this pie was made from") # type: ignore
    enabled: BoolProperty(name="Enabled", default=True, update=_sync_update) # type: ignore
    editor: EnumProperty(name="Works In", items=EDITORS, update=_sync_update) # type: ignore
    key: StringProperty(name="Key", default="NONE") # type: ignore
    ctrl: BoolProperty(name="Ctrl") # type: ignore
    shift: BoolProperty(name="Shift") # type: ignore
    alt: BoolProperty(name="Alt") # type: ignore
    items: CollectionProperty(type=KeyOpsPieItem) # type: ignore


def key_text(pie):
    if pie.key in ("", "NONE"):
        return "No key"
    mods = [m for m, on in (("Ctrl", pie.ctrl), ("Shift", pie.shift), ("Alt", pie.alt)) if on]
    return " ".join(mods + [_KEY_NAMES.get(pie.key, pie.key)])


def _fill(pie, preset):
    pie.name = preset["name"]
    pie.preset = preset["id"]
    pie.editor = preset["editor"]
    pie.key = preset["key"]
    pie.ctrl = preset.get("ctrl", False)
    pie.shift = preset.get("shift", False)
    pie.alt = preset.get("alt", False)
    pie.items.clear()
    for kind, label, icon, idname, props in preset["items"]:
        it = pie.items.add()
        it.kind, it.label, it.icon, it.idname, it.props = kind, label, icon, idname, props


def _new_pie(prefs):
    pie = prefs.pies.add()
    pie.uid = uuid.uuid4().hex[:12]
    return pie


def install_presets(prefs, style):
    """Fill the pie list from the presets, enabling the ones the chosen keyboard style includes."""
    prefs.pies.clear()
    for preset in PRESETS:
        pie = _new_pie(prefs)
        _fill(pie, preset)
        pie["enabled"] = style in preset["styles"]  # no update callback while filling
    prefs.pies_installed = True
    sync_keymaps()


def find_pie(uid):
    for pie in get_keyops_prefs().pies:
        if pie.uid == uid:
            return pie
    return None


# ---------------------------------------------------------------- keymaps

_pie_keymaps = []
_VIEWPORT_KEYMAPS = ("Object Mode", "Mesh", "Curve", "3D View Generic")


def sync_keymaps():
    for km, kmi in _pie_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _pie_keymaps.clear()
    kc = bpy.context.window_manager.keyconfigs.addon
    prefs = get_keyops_prefs()
    if kc is None or not getattr(prefs, "pies_installed", False) or prefs.pause_shortcuts:
        return
    for pie in prefs.pies:
        if not pie.enabled or pie.key in ("", "NONE"):
            continue
        # Mode keymaps (Object Mode, Mesh) are checked before "3D View Generic", so a
        # viewport-wide pie also goes into them, or Blender's own Shift A / Ctrl J would win.
        names = _VIEWPORT_KEYMAPS if pie.editor == "3D View Generic" else (pie.editor,)
        for name in names:
            km = kc.keymaps.new(name=name, space_type='EMPTY')
            kmi = km.keymap_items.new("wm.keyops_call_pie", pie.key, 'PRESS', ctrl=pie.ctrl, shift=pie.shift, alt=pie.alt)
            kmi.properties.pie = pie.uid
            _pie_keymaps.append((km, kmi))


def live_count():
    """Number of pies that have an active key."""
    return len({kmi.properties.pie for _km, kmi in _pie_keymaps})


# ---------------------------------------------------------------- drawing a pie

def _parse_props(text):
    if not text.strip():
        return {}
    call = ast.parse(f"f({text})", mode="eval").body
    return {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords}


def _icon(name):
    return name if name in _ICONS else 'NONE'


def draw_item(layout, context, item):
    if item.kind == N or not item.idname.strip():
        layout.separator()
        return
    label = item.label or item.idname
    try:
        if item.kind == M:
            layout.operator("wm.call_menu", text=label, icon=_icon(item.icon)).name = item.idname
        elif item.kind == P:
            *path, prop = item.idname.strip().split(".")
            data = context
            for part in path:
                data = getattr(data, part)
            layout.prop(data, prop, text=label, toggle=True, icon=_icon(item.icon))
        else:
            op = layout.operator(item.idname.strip(), text=label, icon=_icon(item.icon))
            for name, value in _parse_props(item.props).items():
                setattr(op, name, value)
    except Exception:
        layout.label(text=f"{label} (check command)", icon='ERROR')


class WM_OT_keyops_call_pie(Operator):
    bl_idname = "wm.keyops_call_pie"
    bl_label = "Key Ops Pie Menu"
    bl_description = "Open a Key Ops pie menu"
    bl_options = {'INTERNAL'}

    pie: StringProperty() # type: ignore

    def invoke(self, context, event):
        pie = find_pie(self.pie)
        if pie is None:
            return {'CANCELLED'}
        items = list(pie.items)

        def draw(menu, ctx):
            layout = menu.layout.menu_pie()
            for item in items[:8]:
                draw_item(layout, ctx, item)

        context.window_manager.popup_menu_pie(event, draw, title=pie.name)
        return {'FINISHED'}


# ---------------------------------------------------------------- editing operators

class KEYOPS_OT_pie_select(Operator):
    bl_idname = "keyops.pie_select"
    bl_label = "Edit Pie"
    bl_description = "Edit this pie menu"
    bl_options = {'INTERNAL'}
    index: IntProperty() # type: ignore

    def execute(self, context):
        get_keyops_prefs().active_pie = self.index
        return {'FINISHED'}


class KEYOPS_OT_pie_add(Operator):
    bl_idname = "keyops.pie_add"
    bl_label = "New Pie"
    bl_description = "Make a new empty pie menu"
    bl_options = {'INTERNAL'}
    preset: StringProperty(options={'SKIP_SAVE'}) # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _new_pie(prefs)
        if self.preset in PRESET_BY_ID:
            _fill(pie, PRESET_BY_ID[self.preset])
        else:
            pie.name = "My Pie"
            pie["enabled"] = False  # enable once it has a key and items
            for _i in ORDER:
                pie.items.add()
        prefs.active_pie = len(prefs.pies) - 1
        sync_keymaps()
        return {'FINISHED'}


class KEYOPS_OT_pie_remove(Operator):
    bl_idname = "keyops.pie_remove"
    bl_label = "Delete Pie"
    bl_description = "Delete this pie menu. Presets can be added back from Add Preset"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        if 0 <= prefs.active_pie < len(prefs.pies):
            prefs.pies.remove(prefs.active_pie)
            prefs.active_pie = max(0, prefs.active_pie - 1)
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
    bl_description = "Click, then press the key (with Ctrl/Shift/Alt) that should open this pie. Esc cancels, Backspace clears"
    bl_options = {'INTERNAL'}

    capturing = -1

    def invoke(self, context, event):
        KEYOPS_OT_pie_set_key.capturing = get_keyops_prefs().active_pie
        context.window_manager.modal_handler_add(self)
        self._redraw(context)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.value != 'PRESS' or event.type in _MODIFIER_KEYS or "MOUSEMOVE" in event.type or event.type.startswith("TIMER"):
            return {'RUNNING_MODAL'}
        prefs = get_keyops_prefs()
        pie = prefs.pies[KEYOPS_OT_pie_set_key.capturing]
        if event.type in {'ESC', 'LEFTMOUSE', 'RIGHTMOUSE'}:
            pass
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


class KEYOPS_MT_pie_presets(bpy.types.Menu):
    bl_idname = "KEYOPS_MT_pie_presets"
    bl_label = "Add Preset"

    def draw(self, context):
        for preset in PRESETS:
            self.layout.operator("keyops.pie_add", text=preset["name"]).preset = preset["id"]


# ---------------------------------------------------------------- preferences tab

def draw_pies_tab(prefs, context, layout):
    split = layout.split(factor=0.28)
    left = split.column()
    box = left.box()
    col = box.column(align=True)
    for i, pie in enumerate(prefs.pies):
        row = col.row(align=True)
        row.prop(pie, "enabled", text="")
        sub = row.row(align=True)
        sub.active = pie.enabled
        sub.operator("keyops.pie_select", text=pie.name, depress=(i == prefs.active_pie)).index = i
        k = row.row(align=True)
        k.active = False
        k.ui_units_x = 4.5
        k.alignment = 'RIGHT'
        k.label(text=key_text(pie))
    if not prefs.pies:
        col.label(text="No pie menus. Add one below.")
    row = left.row(align=True)
    row.operator("keyops.pie_add", text="New Pie")
    row.menu("KEYOPS_MT_pie_presets", text="Add Preset")

    right = split.column()
    if not (0 <= prefs.active_pie < len(prefs.pies)):
        right.label(text="Pick a pie on the left to edit it.")
        return
    pie = prefs.pies[prefs.active_pie]
    box = right.box()
    row = box.row(align=True)
    row.prop(pie, "enabled", text="")
    row.prop(pie, "name", text="")
    row.separator()
    capturing = KEYOPS_OT_pie_set_key.capturing == prefs.active_pie
    sub = row.row(align=True)
    sub.alert = capturing
    sub.operator("keyops.pie_set_key", text="Press a key..." if capturing else key_text(pie), depress=capturing)
    row.prop(pie, "editor", text="")
    row = box.row(align=True)
    row.operator("wm.keyops_call_pie", text="Try It").pie = pie.uid
    if pie.preset in PRESET_BY_ID:
        row.operator("keyops.pie_reset", text="Reset to Preset")
    row.operator("keyops.pie_remove", text="Delete")

    grid = right.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=False, align=False)
    for pos in GRID:
        cell = grid.box().column(align=True)
        if pos is None:
            cell.label(text=pie.name)
            sub = cell.column(align=True)
            sub.active = False
            sub.label(text=key_text(pie))
            sub.label(text=dict((e[0], e[1]) for e in EDITORS)[pie.editor])
            continue
        index = ORDER.index(pos)
        if index >= len(pie.items):
            continue
        item = pie.items[index]
        head = cell.row()
        head.active = False
        head.label(text=POSITION_NAMES[pos])
        cell.prop(item, "kind", text="")
        if item.kind != N:
            cell.prop(item, "label", text="", placeholder="Label") if bpy.app.version >= (4, 1, 0) else cell.prop(item, "label", text="")
            hint = {O: "mesh.primitive_cube_add", M: "VIEW3D_MT_add", P: "scene.tool_settings.use_snap"}[item.kind]
            cell.prop(item, "idname", text="", placeholder=hint) if bpy.app.version >= (4, 1, 0) else cell.prop(item, "idname", text="")
            if item.kind == O:
                cell.prop(item, "props", text="", placeholder="Options, e.g. type='WELD'") if bpy.app.version >= (4, 1, 0) else cell.prop(item, "props", text="")
            r = cell.row(align=True)
            r.prop(item, "icon", text="", placeholder="Icon, e.g. MESH_CUBE") if bpy.app.version >= (4, 1, 0) else r.prop(item, "icon", text="")
            if item.icon:
                r.label(text="", icon=_icon(item.icon))

    tip = right.column(align=True)
    tip.active = False
    tip.label(text="Tip: turn on Python Tooltips (Preferences > Interface) and hover any button to see its command.")

    if any(it.idname == "keyops.add_mesh" for it in pie.items):
        box = right.box()
        box.label(text="Add Objects size")
        r = box.row()
        r.prop(prefs, "add_object_pie_use_relative")
        s = r.row()
        s.active = prefs.add_object_pie_use_relative
        s.prop(prefs, "add_object_pie_relative_scale")
        r = box.row()
        r.prop(prefs, "add_object_pie_min_scale")
        r.prop(prefs, "add_object_pie_default_scale")


# ---------------------------------------------------------------- operators the presets use

_SUPPORT = (
    ("operators.add_mesh", "register_add_objects_pie", "unregister_add_objects_pie"),
    ("operators.add_modifier", "register_add_modifier_pie", "unregister_add_modifier_pie"),
    ("operators.origin_to_selection", "register_cursor_pie", "unregister_cursor_pie"),
    ("operators.flatten", "register_flatten_pie", "unregister_flatten_pie"),
    ("menu.pies", "register_workspace_pie", "unregister_workspace_pie"),
    ("menu.pies", "register_utility_pie", "unregister_utility_pie"),
    ("menu.pies", "register_uv_pies", "unregister_uv_pies"),
)


def _register_support():
    """Register the operators the preset pies call. The old modules also add their
    fixed keys; those are removed again, since keys now come from the pie list."""
    import importlib
    kc = bpy.context.window_manager.keyconfigs.addon

    def items():
        if kc is None:
            return {}
        return {kmi.as_pointer(): (km, kmi) for km in kc.keymaps for kmi in km.keymap_items}

    for module, reg, _unreg in _SUPPORT:
        before = set(items())
        getattr(importlib.import_module("." + module, __package__), reg)()
        for ptr, (km, kmi) in items().items():
            if ptr not in before and " Tool: " not in km.name:
                km.keymap_items.remove(kmi)


def _unregister_support():
    import importlib
    for module, _reg, unreg in reversed(_SUPPORT):
        try:
            getattr(importlib.import_module("." + module, __package__), unreg)()
        except Exception:
            pass


property_classes = (KeyOpsPieItem, KeyOpsPie)
classes = (WM_OT_keyops_call_pie, KEYOPS_OT_pie_select, KEYOPS_OT_pie_add, KEYOPS_OT_pie_remove,
           KEYOPS_OT_pie_reset, KEYOPS_OT_pie_set_key, KEYOPS_MT_pie_presets)


def register_properties():
    for cls in property_classes:
        bpy.utils.register_class(cls)


def unregister_properties():
    for cls in reversed(property_classes):
        bpy.utils.unregister_class(cls)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    _register_support()
    sync_keymaps()


def unregister():
    for km, kmi in _pie_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _pie_keymaps.clear()
    _unregister_support()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
