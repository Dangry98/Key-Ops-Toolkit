"""User-editable pie menus.

Every Key Ops pie is now a preset stored in the add-on preferences: users can
change any slot, change its key, and add pies of their own. One operator
(wm.keyops_call_pie) opens any of them, and each enabled pie gets one Key Ops
keymap item in keyconfigs.addon. The user's keymap is never edited.
"""

import ast
import json
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

O, M, P, N, MACRO = "OPERATOR", "MENU", "PROPERTY", "NONE", "MACRO"
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
# The presets that existed before files recorded which presets they had seen
FIRST_PRESETS = ("add_objects", "add_modifier", "flatten", "cursor", "workspace", "utility", "uv_space", "uv_islands")

_ICONS = set(bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys())
_KEY_NAMES = {i.identifier: i.name for i in bpy.types.KeyMapItem.bl_rna.properties["type"].enum_items}
_MODIFIER_KEYS = {"LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_ALT", "RIGHT_ALT", "OSKEY"}


_loading = False  # True while pies are read from disk, so reading doesn't trigger a save
loaded_from_disk = False


def _changed(self=None, context=None):
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
        for kind, label, icon, idname, props in preset["items"]:
            if kind == N or (kind, idname, props) in seen:
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


class KeyOpsMacroStep(PropertyGroup):
    idname: StringProperty(name="Operator", description="Operator to run in this step, e.g. mesh.select_all", update=_changed) # type: ignore
    props: StringProperty(name="Options", description="Options for this step, e.g. action='SELECT'", update=_changed) # type: ignore
    interactive: BoolProperty(name="Interactive", update=_changed,
                              description="Run this step like a key press, so tools that follow the mouse can be used. Later steps don't wait for it") # type: ignore


class KeyOpsPieItem(PropertyGroup):
    kind: EnumProperty(name="Type", items=(
        (N, "Empty", "Leave this slot empty (a separator in popup menus)"),
        (O, "Operator", "Run an operator, e.g. mesh.primitive_cube_add"),
        (M, "Menu", "Open a menu, e.g. VIEW3D_MT_add"),
        (P, "Toggle", "Toggle a setting, e.g. scene.tool_settings.use_snap"),
        (MACRO, "Macro", "Run several operators one after another")), update=_changed) # type: ignore
    steps: CollectionProperty(type=KeyOpsMacroStep) # type: ignore
    extra: StringProperty(options={'HIDDEN'}) # type: ignore  # fields from newer versions, kept as JSON
    label: StringProperty(name="Label", update=_changed) # type: ignore
    icon: StringProperty(name="Icon", description="Blender icon name, e.g. MESH_CUBE. Leave empty for no icon", update=_changed) # type: ignore
    idname: StringProperty(name="Command", description="Operator id, menu id or setting path", update=_changed) # type: ignore
    props: StringProperty(name="Options", description="Operator options, e.g. type='WELD', segments=4", update=_changed) # type: ignore
    choice: EnumProperty(name="Action", description="What this slot does. Pick any Key Ops action",
                         items=_choice_items, get=_choice_get, set=_choice_set) # type: ignore


class KeyOpsPie(PropertyGroup):
    uid: StringProperty() # type: ignore
    menu_type: EnumProperty(name="Menu Type", items=(
        ("PIE", "Pie Menu", "Up to 8 actions around the mouse"),
        ("MENU", "Popup Menu", "A list of actions under the mouse, as long as you like")), update=_changed) # type: ignore
    extra: StringProperty(options={'HIDDEN'}) # type: ignore
    name: StringProperty(name="Name", default="New Pie", update=_changed) # type: ignore
    preset: StringProperty(description="Preset this pie was made from") # type: ignore
    enabled: BoolProperty(name="Enabled", default=True, update=_sync_update) # type: ignore
    editor: EnumProperty(name="Works In", items=EDITORS, update=_sync_update) # type: ignore
    key: StringProperty(name="Key", default="NONE", update=_changed) # type: ignore
    ctrl: BoolProperty(name="Ctrl", update=_changed) # type: ignore
    shift: BoolProperty(name="Shift", update=_changed) # type: ignore
    alt: BoolProperty(name="Alt", update=_changed) # type: ignore
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


# ---------------------------------------------------------------- saving to pie_menus.json

PIE_FIELDS = ("uid", "name", "preset", "enabled", "menu_type", "editor", "key", "ctrl", "shift", "alt")
ITEM_FIELDS = ("kind", "label", "icon", "idname", "props")
STEP_FIELDS = ("idname", "props", "interactive")
PIE_SCHEMA = 2  # bump when the saved layout changes, and add a migration below


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
            limit = 8 if pie.menu_type == "PIE" else 64
            for it_data in entry.get("items", [])[:limit]:
                it = pie.items.add()
                if isinstance(it_data, dict):
                    _apply(it, ITEM_FIELDS, it_data)
                    for st_data in it_data.get("steps", []):
                        if isinstance(st_data, dict):
                            st = it.steps.add()
                            for f in STEP_FIELDS:
                                if f in st_data:
                                    try:
                                        setattr(st, f, st_data[f])
                                    except (TypeError, ValueError):
                                        pass
            while pie.menu_type == "PIE" and len(pie.items) < 8:
                pie.items.add()
        if not merge:
            # Presets added in a newer Key Ops show up once, switched off; your own pies are untouched
            seen = set(data.get("presets_seen", FIRST_PRESETS)) | {p.preset for p in prefs.pies}
            for preset in PRESETS:
                if preset["id"] not in seen:
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


PIE_MIGRATIONS = {1: _migrate_pies_1_to_2}


def load_from_disk():
    """Read pie_menus.json if it exists. Returns True when pies came from the file."""
    global loaded_from_disk
    from . import settings_store
    loaded_from_disk = settings_store.load_section("pie_menus")
    return loaded_from_disk


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


def _icon(name):
    return name if name in _ICONS else 'NONE'


def draw_item(layout, context, item, pie_uid="", index=-1):
    if item.kind == MACRO:
        if not item.steps:
            layout.separator()
            return
        op = layout.operator("wm.keyops_run_macro", text=item.label or "Macro", icon=_icon(item.icon))
        op.pie, op.slot = pie_uid, index
        return
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
        uid = pie.uid

        if pie.menu_type == "MENU":
            def draw_menu(menu, ctx):
                col = menu.layout.column()
                for i, item in enumerate(items):
                    draw_item(col, ctx, item, uid, i)
            context.window_manager.popup_menu(draw_menu, title=pie.name)
            return {'FINISHED'}

        def draw(menu, ctx):
            layout = menu.layout.menu_pie()
            for i, item in enumerate(items[:8]):
                draw_item(layout, ctx, item, uid, i)

        context.window_manager.popup_menu_pie(event, draw, title=pie.name)
        return {'FINISHED'}


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
    menu_type: StringProperty(default="PIE", options={'SKIP_SAVE'}) # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _new_pie(prefs)
        if self.preset in PRESET_BY_ID:
            _fill(pie, PRESET_BY_ID[self.preset])
        elif self.menu_type == "MENU":
            pie.name = "My Menu"
            pie.menu_type = "MENU"
            pie["enabled"] = False
            pie.items.add()
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
    bl_description = "Add an item to this popup menu"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _active_pie(prefs)
        if pie is None or pie.menu_type != "MENU" or len(pie.items) >= 64:
            return {'CANCELLED'}
        pie.items.add()
        prefs.pie_slot = len(pie.items) - 1
        prefs.pie_customize = True
        _changed()
        return {'FINISHED'}


class KEYOPS_OT_menu_item_remove(Operator):
    bl_idname = "keyops.menu_item_remove"
    bl_label = "Remove Item"
    bl_description = "Remove this item from the popup menu"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        pie = _active_pie(prefs)
        if pie is None or not (0 <= prefs.pie_slot < len(pie.items)):
            return {'CANCELLED'}
        pie.items.remove(prefs.pie_slot)
        prefs.pie_slot = max(0, prefs.pie_slot - 1)
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


from bpy_extras.io_utils import ExportHelper, ImportHelper  # noqa: E402


class KeyOpsExportChoice(PropertyGroup):
    uid: StringProperty() # type: ignore
    use: BoolProperty(default=True) # type: ignore

_SCOPES = (("ALL", "All Settings", "Features, shortcuts, settings and pie menus"),
           ("PIES", "Pie Menus", "Only the pie menus"))


class KEYOPS_OT_settings_export(Operator, ExportHelper):
    bl_idname = "keyops.settings_export"
    bl_label = "Export Key Ops Settings"
    bl_description = "Save Key Ops settings to a .json file, to back them up or use them on another computer"
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
        settings_store.export_file(self.filepath, names, options)
        self.report({'INFO'}, f"Exported to {self.filepath}")
        return {'FINISHED'}


class KEYOPS_OT_settings_import(Operator, ImportHelper):
    bl_idname = "keyops.settings_import"
    bl_label = "Import Key Ops Settings"
    bl_description = "Load Key Ops settings from a .json file made with Export"
    bl_options = {'INTERNAL'}
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'}) # type: ignore
    scope: EnumProperty(name="Import", items=_SCOPES) # type: ignore
    mode: EnumProperty(name="Pie Menus", items=(
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


class KEYOPS_MT_pie_new(bpy.types.Menu):
    bl_idname = "KEYOPS_MT_pie_new"
    bl_label = "New"

    def draw(self, context):
        self.layout.operator("keyops.pie_add", text="Pie Menu", icon='MESH_CIRCLE').menu_type = "PIE"
        self.layout.operator("keyops.pie_add", text="Popup Menu", icon='COLLAPSEMENU').menu_type = "MENU"


class KEYOPS_MT_pie_presets(bpy.types.Menu):
    bl_idname = "KEYOPS_MT_pie_presets"
    bl_label = "Add Preset"

    def draw(self, context):
        for preset in PRESETS:
            self.layout.operator("keyops.pie_add", text=preset["name"]).preset = preset["id"]


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


def _search_items(self, context):
    return _KEYOPS_SEARCH if self.scope == "KEYOPS" else _KEYOPS_SEARCH + _all_operator_items()


def _active_item(prefs, slot):
    pie = prefs.pies[max(0, min(prefs.active_pie, len(prefs.pies) - 1))]
    return pie.items[slot] if 0 <= slot < len(pie.items) else None


class KEYOPS_OT_pie_slot_search(Operator):
    bl_idname = "keyops.pie_slot_search"
    bl_label = "Pick an Action"
    bl_description = "Search for what this slot should do"
    bl_options = {'INTERNAL'}
    bl_property = "action"

    slot: IntProperty() # type: ignore
    step: IntProperty(default=-1, options={'SKIP_SAVE'}) # type: ignore  # >= 0: a macro step
    scope: EnumProperty(items=(("KEYOPS", "Key Ops", ""), ("ALL", "All of Blender", ""))) # type: ignore
    action: EnumProperty(items=_search_items) # type: ignore

    def invoke(self, context, event):
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


def _redraw_all(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


class KEYOPS_OT_pie_slot_select(Operator):
    bl_idname = "keyops.pie_slot_select"
    bl_label = "Edit Slot"
    bl_description = "Edit this slot below"
    bl_options = {'INTERNAL'}
    slot: IntProperty() # type: ignore

    def execute(self, context):
        get_keyops_prefs().pie_slot = self.slot
        return {'FINISHED'}


class KEYOPS_PT_icon_palette(bpy.types.Panel):
    """Icon palette popup. Shown with wm.call_panel, so it closes when an icon is clicked."""
    bl_idname = "KEYOPS_PT_icon_palette"
    bl_label = "Pick an Icon"
    bl_space_type = 'TOPBAR'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 24

    def draw(self, context):
        wm = context.window_manager
        prefs = get_keyops_prefs()
        item = _active_item(prefs, prefs.pie_slot)
        current = item.icon if item is not None else ""
        layout = self.layout

        head = layout.row()
        head.label(text="Icons")
        right = head.row(align=True)
        right.alignment = 'RIGHT'
        if current:
            cur = right.row()
            cur.active = False
            cur.label(text=current.replace("_", " ").title(), icon=_icon(current))
        right.operator("keyops.pie_set_icon", text="No Icon", icon='X', emboss=False).icon = ""

        search = layout.row()
        search.scale_y = 1.2
        search.prop(wm, "keyops_icon_filter", text="", icon='VIEWZOOM', placeholder="Search icons and press Enter") \
            if bpy.app.version >= (4, 1, 0) else search.prop(wm, "keyops_icon_filter", text="", icon='VIEWZOOM')

        tabs = layout.row(align=True)
        tabs.scale_y = 1.1
        for cid, label in [(c[0], c[1]) for c in ICON_CATEGORIES] + [("OTHER", "Other")]:
            tabs.operator("keyops.icon_palette_tab", text=label, depress=(wm.keyops_icon_category == cid)).category = cid
        layout.separator(factor=0.6)

        q = wm.keyops_icon_filter.strip().upper().replace(" ", "_")
        cat = wm.keyops_icon_category
        matches = [n for n in _ICON_LIST if q in n and (cat == "ALL" or _ICON_CAT.get(n) == cat)]
        cols = 14
        names = matches[:cols * 10]  # keeps the popup on screen; search finds the rest
        grid = layout.grid_flow(row_major=True, columns=cols, even_columns=True, even_rows=True, align=False)
        grid.scale_x = 1.35
        grid.scale_y = 1.35
        for name in names:
            # icons sit on the dark popup without frames; the current one is highlighted
            is_current = name == current
            grid.operator("keyops.pie_set_icon", text="", icon=name, emboss=is_current, depress=is_current).icon = name
        for _ in range(max(0, cols - len(names))):
            grid.label(text="")  # keep icons the same size when only a few match

        foot = layout.row()
        foot.active = False
        if not names:
            foot.label(text="No icons match. Try another word or the All tab.")
        else:
            more = f"  ·  search to see the other {len(matches) - len(names)}" if len(matches) > len(names) else ""
            foot.label(text=f"{len(matches)} icons{more}")


def _open_palette():
    """Open the icon palette in the area under the mouse (used to reopen it after a tab click)."""
    ctx = bpy.context
    for window in ctx.window_manager.windows:
        for area in window.screen.areas:
            if area.type in {'PREFERENCES', 'VIEW_3D'}:
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                with ctx.temp_override(window=window, area=area, region=region):
                    bpy.ops.wm.call_panel(name="KEYOPS_PT_icon_palette", keep_open=False)
                return None
    return None


class KEYOPS_OT_icon_palette_tab(Operator):
    bl_idname = "keyops.icon_palette_tab"
    bl_label = "Icon Category"
    bl_options = {'INTERNAL'}
    category: StringProperty() # type: ignore

    @classmethod
    def description(cls, context, properties):
        return f"Show {properties.category.title()} icons"

    def execute(self, context):
        context.window_manager.keyops_icon_category = self.category
        # The palette closes on any click, so open it again on the new category
        bpy.app.timers.register(_open_palette, first_interval=0.05)
        return {'FINISHED'}


class KEYOPS_OT_pie_icon_picker(Operator):
    bl_idname = "keyops.pie_icon_picker"
    bl_label = "Pick an Icon"
    bl_description = "Choose this slot's icon from all of Blender's icons"
    bl_options = {'INTERNAL'}
    slot: IntProperty() # type: ignore

    def execute(self, context):
        item = _active_item(get_keyops_prefs(), self.slot)
        if item is None or _is_empty(item):
            self.report({'INFO'}, "Pick an action for this slot first")
            return {'CANCELLED'}
        get_keyops_prefs().pie_slot = self.slot
        bpy.ops.wm.call_panel(name="KEYOPS_PT_icon_palette", keep_open=False)
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
        prefs = get_keyops_prefs()
        item = _active_item(prefs, self.slot if self.slot >= 0 else prefs.pie_slot)
        if item is not None:
            item.icon = self.icon
        _redraw_all(context)
        return {'FINISHED'}


ICON_CATEGORIES = (
    ("ALL", "All", ()),
    ("OBJECTS", "Objects", ("MESH_", "OUTLINER_", "OBJECT", "CURVE", "SURFACE", "META", "EMPTY", "LIGHT", "CAMERA",
                            "ARMATURE", "LATTICE", "GREASEPENCIL", "FORCE_", "SPEAKER", "VOLUME", "POINTCLOUD", "MONKEY")),
    ("MODIFIERS", "Modifiers", ("MOD_", "CON_", "AUTOMERGE", "GEOMETRY_NODES", "NODETREE")),
    ("EDITING", "Editing", ("EDITMODE", "VERTEXSEL", "EDGESEL", "FACESEL", "SELECT", "SNAP", "PIVOT", "ORIENTATION",
                            "TRANSFORM", "TOOL", "SCULPT", "BRUSH", "MIRROR", "UV", "STICKY", "SEAM", "SHARP",
                            "NORMAL", "FREEZE", "CENTER", "CURSOR", "DECORATE", "PROP_", "AUTO")),
    ("VIEW", "View", ("VIEW", "HIDE", "RESTRICT", "ZOOM", "OVERLAY", "XRAY", "SHADING", "MATERIAL", "TEXTURE",
                      "IMAGE", "NODE", "WORLD", "RENDER", "SCENE", "WINDOW", "WORKSPACE", "AREA", "SPLIT",
                      "FULLSCREEN", "GRID", "AXIS")),
    ("ARROWS", "Arrows", ("TRIA_", "ARROW", "SORT", "BACK", "FORWARD", "LOOP_", "FRAME_", "PLAY", "REW", "FF",
                          "DISCLOSURE", "DOWNARROW", "RIGHTARROW", "UP", "DOWN", "LEFT", "RIGHT")),
    ("KEYS", "Keys", ("EVENT_", "MOUSE_")),
)


def _icon_category(name):
    for cid, _label, prefixes in ICON_CATEGORIES[1:]:
        if any(name.startswith(pre) or (len(pre) > 3 and pre in name) for pre in prefixes):
            return cid
    return "OTHER"


_ICON_LIST = sorted(n for n in _ICONS if n not in {"NONE", "BLANK1"} and not n.startswith(("BRUSH_", "MATPLANE", "COLORSET_")))
_ICON_CAT = {n: _icon_category(n) for n in _ICON_LIST}


# ---------------------------------------------------------------- pie overview

SLOT_W = 7.0  # units


def _slot_button(row, pie, index, prefs, width=SLOT_W):
    cell = row.row(align=True)
    cell.ui_units_x = width
    cell.scale_y = 1.25
    if index >= len(pie.items):
        cell.label(text="")
        return
    item = pie.items[index]
    empty = _is_empty(item)
    text = ("Separator" if pie.menu_type == "MENU" else "Empty") if empty else (item.label or item.idname or "Macro")
    selected = prefs.pie_customize and prefs.pie_slot == index
    # One rounded item, like an entry in a real pie: the icon and the label are two
    # frameless click zones inside it (icon opens the palette, label picks the action).
    item_box = cell.box() if not selected else cell.column()
    r = item_box.row(align=True)
    r.scale_y = 0.85 if not selected else 1.0
    emboss = selected
    r.operator("keyops.pie_icon_picker", text="", icon=_icon(item.icon) if item.icon else 'BLANK1',
               emboss=emboss, depress=selected).slot = index
    if prefs.pie_customize:
        op = r.operator("keyops.pie_slot_select", text=text, emboss=emboss, depress=selected)
        op.slot = index
    else:
        op = r.operator("keyops.pie_slot_search", text=text, emboss=emboss)
        op.slot = index
        op.scope = "KEYOPS"


def _is_empty(item):
    if item.kind == MACRO:
        return not len(item.steps)
    return item.kind == N or not item.idname.strip()


def draw_menu_overview(layout, pie, prefs):
    """A popup menu drawn as its list of items."""
    col = layout.column(align=False)
    head = col.row()
    head.alignment = 'CENTER'
    head.label(text=pie.name)
    k = col.row()
    k.alignment = 'CENTER'
    k.active = False
    k.label(text=key_text(pie) if pie.enabled else "Off")
    for i in range(len(pie.items)):
        row = col.row()
        row.alignment = 'CENTER'
        _slot_button(row, pie, i, prefs, width=11.0)
    if prefs.pie_customize or not pie.items:
        row = col.row()
        row.alignment = 'CENTER'
        add = row.row()
        add.ui_units_x = 11.0
        add.operator("keyops.menu_item_add", text="Add Item", icon='ADD')


def draw_pie_overview(layout, pie, prefs):
    """The pie drawn as buttons, in roughly the proportions Blender draws it."""
    if pie.menu_type == "MENU":
        return draw_menu_overview(layout, pie, prefs)
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


def draw_pies_tab(prefs, context, layout):
    if not prefs.pies:
        layout.label(text="No pie menus.")
        layout.menu("KEYOPS_MT_pie_presets", text="Add Preset")
        return
    active = max(0, min(prefs.active_pie, len(prefs.pies) - 1))

    # pie list on the side: on/off, name, key
    outer = layout.split(factor=0.22)
    side = outer.column()
    lbox = side.box()
    col = lbox.column(align=True)
    for i, p in enumerate(prefs.pies):
        row = col.row(align=True)
        row.prop(p, "enabled", text="")
        name = row.row(align=True)
        name.active = p.enabled or i == active
        name.operator("keyops.pie_select", text=p.name, depress=(i == active)).index = i
        k = row.row(align=True)
        k.ui_units_x = 4.2
        k.alignment = 'RIGHT'
        k.active = False
        k.label(text=key_text(p))
    r = side.row(align=True)
    r.menu("KEYOPS_MT_pie_new", text="New", icon='ADD')
    r.menu("KEYOPS_MT_pie_presets", text="Add Preset")
    r = side.row(align=True)
    r.operator("keyops.settings_import", text="Import", icon='IMPORT').scope = "PIES"
    r.operator("keyops.settings_export", text="Export", icon='EXPORT').scope = "PIES"
    draw_pie_feel(prefs, side)
    layout = outer.column()

    pie = prefs.pies[active]
    box = layout.box()
    head = box.row(align=True)
    head.prop(pie, "enabled", text="On")
    head.separator()
    capturing = KEYOPS_OT_pie_set_key.capturing == active
    keyb = head.row(align=True)
    keyb.alert = capturing
    keyb.operator("keyops.pie_set_key", text="Press a key..." if capturing else f"Key: {key_text(pie)}", depress=capturing)
    where = head.row()
    where.active = False
    where.label(text="in " + dict((e[0], e[1]) for e in EDITORS)[pie.editor])
    head.operator("wm.keyops_call_pie", text="Try It").pie = pie.uid
    head.separator()
    head.prop(prefs, "pie_customize", text="Customize", toggle=True)

    box.separator(factor=0.4)
    split = box.split(factor=0.58) if prefs.pie_customize else box.column()
    draw_pie_overview(split.column() if prefs.pie_customize else split, pie, prefs)
    if prefs.pie_customize:
        draw_slot_editor(prefs, split.column(), pie)
    else:
        tip = box.row()
        tip.alignment = 'CENTER'
        tip.active = False
        tip.label(text="Click a slot to search for a different action, or its icon to change the icon. Customize for more.")

    if any(it.idname == "keyops.add_mesh" for it in pie.items):
        sbox = layout.box()
        r = sbox.row()
        r.label(text="Add Objects size")
        r.prop(prefs, "add_object_pie_use_relative")
        sub = r.row()
        sub.active = prefs.add_object_pie_use_relative
        sub.prop(prefs, "add_object_pie_relative_scale")
        r.prop(prefs, "add_object_pie_default_scale")


def draw_slot_editor(prefs, layout, pie):
    """Customize: edit the selected slot. Advanced fields fold away."""
    if not len(pie.items):
        layout.box().label(text="Add an item to start.")
        return
    slot = max(0, min(prefs.pie_slot, len(pie.items) - 1))
    item = pie.items[slot]
    box = layout.box()
    head = box.row()
    is_menu = pie.menu_type == "MENU"
    head.label(text=f"Item {slot + 1}" if is_menu else f"{POSITION_NAMES[ORDER[slot]]} slot")
    if is_menu:
        tools = head.row(align=True)
        tools.alignment = 'RIGHT'
        tools.operator("keyops.menu_item_move", text="", icon='TRIA_UP').direction = -1
        tools.operator("keyops.menu_item_move", text="", icon='TRIA_DOWN').direction = 1
        tools.operator("keyops.menu_item_remove", text="", icon='X')
    else:
        sub = head.row()
        sub.alignment = 'RIGHT'
        sub.active = False
        sub.label(text="Click a slot on the left to edit it")

    col = box.column()
    empty = _is_empty(item)
    row = col.row(align=True)
    row.scale_y = 1.3
    if item.kind == MACRO:
        row.label(text=item.label or "Macro", icon='SEQUENCE')
    else:
        op = row.operator("keyops.pie_slot_search", text="Empty" if empty else (item.label or item.idname),
                          icon='VIEWZOOM')
        op.slot, op.scope = slot, "KEYOPS"
        op = row.operator("keyops.pie_slot_search", text="Any Operator")
        op.slot, op.scope = slot, "ALL"
    mk = row.row(align=True)
    mk.ui_units_x = 6
    mk.operator("keyops.slot_make_macro", text="Make Macro" if item.kind != MACRO else "Single Action",
                icon='SEQUENCE' if item.kind != MACRO else 'BACK', depress=False)
    if item.kind == MACRO:
        draw_macro_steps(col, item, slot)
    paste = col.row(align=True)
    paste.prop(context_wm(), "keyops_paste_command", text="", icon='PASTEDOWN',
               placeholder="Paste a command from Blender's Info editor") if bpy.app.version >= (4, 1, 0) else \
        paste.prop(context_wm(), "keyops_paste_command", text="", icon='PASTEDOWN')
    if not empty:
        row = col.row(align=True)
        row.prop(item, "label", text="Label")
        hint = col.row()
        hint.active = False
        hint.label(text="Click a slot's icon to change it")

        more = col.row()
        more.alignment = 'LEFT'
        more.prop(prefs, "pie_show_more", text="More Options", icon='DOWNARROW_HLT' if prefs.pie_show_more else 'RIGHTARROW',
                  emboss=False)
        if prefs.pie_show_more:
            adv = col.box().column()
            adv.row().prop(item, "kind", expand=True)
            adv.prop(item, "idname", text={O: "Operator", M: "Menu", P: "Setting"}.get(item.kind, "Command"))
            if item.kind == O:
                adv.prop(item, "props", text="Options")
            note = adv.row()
            note.active = False
            note.label(text="Options look like type='WELD', segments=4")

    pbox = layout.box()
    prow = pbox.row()
    prow.alignment = 'LEFT'
    prow.prop(prefs, "pie_show_settings", text="Pie Settings", icon='DOWNARROW_HLT' if prefs.pie_show_settings else 'RIGHTARROW',
              emboss=False)
    if prefs.pie_show_settings:
        c = pbox.column()
        c.prop(pie, "name", text="Name")
        c.prop(pie, "menu_type", text="Type")
        c.prop(pie, "editor", text="Works In")
        r = c.row(align=True)
        if pie.preset in PRESET_BY_ID:
            r.operator("keyops.pie_reset", text="Reset to Preset")
        r.operator("keyops.pie_remove", text="Delete Pie")


def draw_pie_feel(prefs, layout):
    """Blender's own pie menu settings, shown here so they're easy to find.
    Key Ops never changes them; the person does, as in Preferences > Interface."""
    box = layout.box()
    row = box.row()
    row.alignment = 'LEFT'
    row.prop(prefs, "pie_show_feel", text="How Pies Feel", emboss=False,
             icon='DOWNARROW_HLT' if prefs.pie_show_feel else 'RIGHTARROW')
    if not prefs.pie_show_feel:
        return
    view = bpy.context.preferences.view
    col = box.column()
    r = col.row(align=True)
    r.prop(view, "pie_animation_timeout", text="Animation")
    hint = col.row()
    hint.active = False
    hint.label(text="0 = opens instantly, no lag")
    col.prop(view, "pie_menu_radius", text="Radius")
    col.prop(view, "pie_menu_threshold", text="Threshold")
    col.prop(view, "pie_menu_confirm", text="Confirm")
    col.prop(view, "pie_tap_timeout", text="Tap Key Timeout")
    note = col.row()
    note.active = False
    note.label(text="Blender settings, also in Interface > Editors")


def context_wm():
    return bpy.context.window_manager


def draw_macro_steps(layout, item, slot):
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
        op = r.operator("keyops.pie_slot_search", text=step.idname or "Pick an operator", icon='VIEWZOOM')
        op.slot, op.scope, op.step = slot, "ALL", n
        r.prop(step, "props", text="", placeholder="Options") if bpy.app.version >= (4, 1, 0) else r.prop(step, "props", text="")
        r.prop(step, "interactive", text="", icon='RESTRICT_SELECT_OFF', toggle=True)
        for icon, d in (('TRIA_UP', -1), ('TRIA_DOWN', 1)):
            mv = r.operator("keyops.macro_step_move", text="", icon=icon)
            mv.step, mv.direction = n, d
        r.operator("keyops.macro_step_remove", text="", icon='X').step = n
    box.operator("keyops.macro_step_add", text="Add Step", icon='ADD')


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
    from .features import _module
    kc = bpy.context.window_manager.keyconfigs.addon

    def items():
        if kc is None:
            return {}
        return {kmi.as_pointer(): (km, kmi) for km in kc.keymaps for kmi in km.keymap_items}

    for module, reg, _unreg in _SUPPORT:
        before = set(items())
        getattr(_module(module), reg)()
        for ptr, (km, kmi) in items().items():
            if ptr not in before and " Tool: " not in km.name:
                km.keymap_items.remove(kmi)


def _unregister_support():
    from .features import _module
    for module, _reg, unreg in reversed(_SUPPORT):
        try:
            getattr(_module(module), unreg)()
        except Exception:
            pass


property_classes = (KeyOpsMacroStep, KeyOpsPieItem, KeyOpsPie, KeyOpsExportChoice)
classes = (WM_OT_keyops_call_pie, WM_OT_keyops_run_macro, KEYOPS_OT_menu_item_add, KEYOPS_OT_menu_item_remove,
           KEYOPS_OT_menu_item_move, KEYOPS_OT_slot_make_macro, KEYOPS_OT_macro_step_add, KEYOPS_OT_macro_step_remove,
           KEYOPS_OT_macro_step_move, KEYOPS_MT_pie_new, KEYOPS_OT_pie_select, KEYOPS_OT_pie_add, KEYOPS_OT_pie_remove,
           KEYOPS_OT_pie_reset, KEYOPS_OT_pie_set_key, KEYOPS_MT_pie_presets, KEYOPS_OT_pie_slot_search,
           KEYOPS_OT_pie_slot_select, KEYOPS_PT_icon_palette, KEYOPS_OT_icon_palette_tab, KEYOPS_OT_pie_icon_picker, KEYOPS_OT_pie_set_icon,
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
    bpy.types.WindowManager.keyops_icon_filter = StringProperty(
        name="Search Icons", description="Type part of an icon name and press Enter",
        update=lambda self, ctx: bpy.app.timers.register(_open_palette, first_interval=0.05))
    bpy.types.WindowManager.keyops_export_menus = CollectionProperty(type=KeyOpsExportChoice)
    bpy.types.WindowManager.keyops_paste_command = StringProperty(
        name="Paste Command", description="Paste a bpy.ops command copied from Blender's Info editor", update=_paste_command)
    bpy.types.WindowManager.keyops_icon_category = EnumProperty(
        name="Category", items=[(c[0], c[1], f"{c[1]} icons") for c in ICON_CATEGORIES] + [("OTHER", "Other", "Everything else")])
    _register_support()
    sync_keymaps()


def unregister():
    from . import settings_store
    settings_store.flush_now()  # don't lose a change made just before disabling
    for km, kmi in _pie_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _pie_keymaps.clear()
    _unregister_support()
    del bpy.types.WindowManager.keyops_icon_filter
    del bpy.types.WindowManager.keyops_icon_category
    del bpy.types.WindowManager.keyops_paste_command
    del bpy.types.WindowManager.keyops_export_menus
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


def _register_section():
    from . import settings_store
    settings_store.register_section("pie_menus", pies_to_data, pies_from_data, own_file=True,
                                    schema=PIE_SCHEMA, migrations=PIE_MIGRATIONS)


_register_section()
