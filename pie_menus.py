"""User-editable pie menus.

Every Key Ops pie is now a preset stored in the add-on preferences: users can
change any slot, change its key, and add pies of their own. One operator
(wm.keyops_call_pie) opens any of them, and each enabled pie gets one Key Ops
keymap item in keyconfigs.addon. The user's keymap is never edited.
"""

import ast
import json
import time
import uuid

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
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
    ("Sculpt", "Sculpt Mode", "Only in Sculpt Mode"),
    ("Weight Paint", "Weight Paint", "Only in Weight Paint Mode"),
    ("UV Editor", "UV Editor", "Only in the UV Editor"),
    ("Image", "Image Editor", "In the Image Editor"),
    ("Node Editor", "Node Editors", "Shader, Geometry and other node editors"),
    ("Graph Editor", "Graph Editor", "In the Graph Editor"),
    ("Dopesheet", "Dope Sheet", "In the Dope Sheet"),
    ("Outliner", "Outliner", "In the Outliner"),
    ("Property Editor", "Properties", "In the Properties editor"),
    ("Sequencer", "Video Sequencer", "In the Video Sequencer"),
    ("Text", "Text Editor", "In the Text Editor"),
    ("Window", "Everywhere", "In every editor"),
)

MENU_TYPES = (
    ("PIE", "Pie Menu", "Up to 8 actions around the mouse", 'MESH_CIRCLE', 0),
    ("MENU", "Popup Menu", "A list of actions under the mouse, as long as you like", 'COLLAPSEMENU', 1),
    ("DIALOG", "Dialog", "Buttons and settings in a small window, in columns", 'WINDOW', 2),
    ("PANEL", "Sidebar Panel", "Your buttons and settings as a panel in the editor's sidebar (N)", 'MENU_PANEL', 3),
    ("STACK", "Stack Key", "Each press runs the next item, then starts over", 'SORTSIZE', 4),
    ("STICKY", "Sticky Key", "One action while the key is held, another when it's released", 'PINNED', 5),
    ("MODAL", "Modal Value", "Move the mouse or scroll to change a setting, click to confirm", 'MOUSE_MOVE', 6),
)
TYPE_ICON = {t[0]: t[3] for t in MENU_TYPES}
ITEM_LIMIT = {"PIE": 8, "STICKY": 2, "MODAL": 1}  # others: up to 64
ITEM_MIN = {"PIE": 8, "STICKY": 2, "MODAL": 1}

ONLY_MODES = (
    ("ANY", "Any Mode", "Works in every mode of that editor"),
    ("OBJECT", "Object Mode", ""), ("EDIT_MESH", "Edit Mesh", ""), ("EDIT_CURVE", "Edit Curve", ""),
    ("SCULPT", "Sculpt", ""), ("PAINT_WEIGHT", "Weight Paint", ""), ("PAINT_VERTEX", "Vertex Paint", ""),
    ("PAINT_TEXTURE", "Texture Paint", ""), ("POSE", "Pose", ""), ("EDIT_ARMATURE", "Edit Armature", ""),
)
KEY_EVENTS = (
    ("PRESS", "Press", "Opens as soon as the key goes down"),
    ("CLICK", "Click", "Opens on a quick press and release, so holding the key can do something else"),
    ("DOUBLE_CLICK", "Double Click", "Opens on a double press"),
    ("CLICK_DRAG", "Press and Drag", "Opens when you press the key and move the mouse"),
)

O, M, P, N, MACRO, SUB = "OPERATOR", "MENU", "PROPERTY", "NONE", "MACRO", "SUBMENU"
SCRIPT, PANEL_ITEM, LABEL = "SCRIPT", "POPOVER", "LABEL"
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
_KEY_NAMES.update({f"BUTTON{n}MOUSE": f"Mouse {n}" for n in range(4, 8)})
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


class KeyOpsValue(PropertyGroup):
    """A value of your own (number, toggle or text), saved by Key Ops and usable in menus and scripts."""
    vtype: EnumProperty(name="Type", items=(("FLOAT", "Number", "A number like 0.25", 'DRIVER_DISTANCE', 0),
                                            ("INT", "Whole Number", "A whole number like 3", 'LINENUMBERS_ON', 1),
                                            ("BOOL", "Toggle", "On or off", 'CHECKBOX_HLT', 2),
                                            ("STRING", "Text", "Some text", 'SYNTAX_OFF', 3)), update=lambda s, c: _values_changed()) # type: ignore
    float_value: FloatProperty(name="Value", update=lambda s, c: _values_changed()) # type: ignore
    int_value: IntProperty(name="Value", update=lambda s, c: _values_changed()) # type: ignore
    bool_value: BoolProperty(name="Value", update=lambda s, c: _values_changed()) # type: ignore
    string_value: StringProperty(name="Value", update=lambda s, c: _values_changed()) # type: ignore

    @property
    def field(self):
        return {"FLOAT": "float_value", "INT": "int_value", "BOOL": "bool_value", "STRING": "string_value"}[self.vtype]


def _values_changed():
    if not _loading:
        from . import settings_store
        settings_store.save_soon("values")


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
        (LABEL, "Label", "A heading (popup menus, dialogs and panels)")), update=_changed) # type: ignore
    script: StringProperty(name="Python", description="Python to run. Use the Text Editor button for longer scripts",
                           update=_changed) # type: ignore
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
    menu_type: EnumProperty(name="Menu Type", items=MENU_TYPES, update=_sync_update) # type: ignore
    only_mode: EnumProperty(name="Only In", items=ONLY_MODES, update=_changed,
                            description="Only open in this mode; anywhere else the key does what Blender does") # type: ignore
    key_event: EnumProperty(name="Key Event", items=KEY_EVENTS, update=_sync_update) # type: ignore
    key_mod: EnumProperty(name="While Holding", update=_sync_update,
                          description="Optional: a second key that must be held, for two-key shortcuts",
                          items=[(i.identifier, "Nothing" if i.identifier == "NONE" else _KEY_NAMES.get(i.identifier, i.name), "")
                                 for i in bpy.types.KeyMapItem.bl_rna.properties["key_modifier"].enum_items]) # type: ignore
    columns: IntProperty(name="Columns", default=2, min=1, max=6, update=_changed) # type: ignore
    dialog_mode: EnumProperty(name="Behaviour", items=(
        ("POPUP", "Popup", "Closes when the mouse moves away"),
        ("DIALOG", "Dialog", "Stays open until you close it")), update=_changed) # type: ignore
    stack_reset: FloatProperty(name="Start Over After", default=2.0, min=0.0, max=30.0, subtype='TIME_ABSOLUTE', unit='TIME_ABSOLUTE',
                               description="Seconds without a press before the stack starts at the first item again (0 = never)",
                               update=_changed) # type: ignore
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

PIE_FIELDS = ("uid", "name", "preset", "enabled", "menu_type", "editor", "key", "ctrl", "shift", "alt",
              "key_event", "only_mode", "columns", "dialog_mode", "stack_reset", "key_mod")
ITEM_FIELDS = ("kind", "label", "icon", "idname", "props", "script")
STEP_FIELDS = ("idname", "props", "interactive")
PIE_SCHEMA = 4  # bump when the saved layout changes, and add a migration below


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
            limit = ITEM_LIMIT.get(pie.menu_type, 64)
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
            while len(pie.items) < ITEM_MIN.get(pie.menu_type, 0):
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


def _migrate_pies_2_to_3(data):
    """Schema 3 added more menu types and per-menu options; older menus keep the defaults."""
    for p in data.get("pies", []):
        p.setdefault("key_event", "PRESS")
        p.setdefault("only_mode", "ANY")
    return data


def _migrate_pies_3_to_4(data):
    """Schema 4 added Python, panel and label items, and two-key shortcuts. Nothing to convert."""
    return data


PIE_MIGRATIONS = {1: _migrate_pies_1_to_2, 2: _migrate_pies_2_to_3, 3: _migrate_pies_3_to_4}


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


def sync_keymaps():
    _remove_pie_keymaps()
    kc = bpy.context.window_manager.keyconfigs.addon
    prefs = get_keyops_prefs()
    if kc is None or not getattr(prefs, "pies_installed", False) or prefs.pause_shortcuts:
        return
    for pie in prefs.pies:
        if not pie.enabled or pie.key in ("", "NONE") or pie.menu_type == "PANEL":
            continue
        # Mode keymaps (Object Mode, Mesh) are checked before "3D View Generic", so a
        # viewport-wide pie also goes into them, or Blender's own Shift A / Ctrl J would win.
        names = _VIEWPORT_KEYMAPS if pie.editor == "3D View Generic" else (pie.editor,)
        for name in names:
            km = kc.keymaps.new(name=name, space_type='EMPTY')
            value = 'PRESS' if pie.menu_type in {"STICKY", "MODAL"} else pie.key_event
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


def _icon(name):
    return name if name in _ICONS else 'NONE'


def draw_item(layout, context, item, pie_uid="", index=-1, slider=False):
    if item.kind == SUB:
        target = find_pie(item.idname)
        if target is None:
            layout.separator()
            return
        layout.operator("wm.keyops_call_pie", text=item.label or target.name,
                        icon=_icon(item.icon) if item.icon else TYPE_ICON.get(target.menu_type, 'NONE')).pie = target.uid
        return
    if item.kind == LABEL:
        layout.label(text=item.label, icon=_icon(item.icon) if item.icon else 'NONE')
        return
    if item.kind == SCRIPT:
        if not item.script.strip():
            layout.separator()
            return
        op = layout.operator("wm.keyops_run_script", text=item.label or "Python", icon=_icon(item.icon) if item.icon else 'SCRIPT')
        op.pie, op.slot = pie_uid, index
        return
    if item.kind == PANEL_ITEM:
        if not item.idname.strip() or not hasattr(bpy.types, item.idname.strip()):
            layout.label(text=f"{item.label or item.idname} (panel not found)", icon='ERROR')
            return
        layout.popover(panel=item.idname.strip(), text=item.label or item.idname, icon=_icon(item.icon) if item.icon else 'NONE')
        return
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
            data, prop = _resolve(context, item.idname)
            if slider:  # dialogs and panels show settings as real fields and sliders
                layout.prop(data, prop, text=label, icon=_icon(item.icon) if item.icon else 'NONE')
            else:
                layout.prop(data, prop, text=label, toggle=True, icon=_icon(item.icon))
        else:
            op = layout.operator(item.idname.strip(), text=label, icon=_icon(item.icon))
            for name, value in _parse_props(item.props).items():
                setattr(op, name, value)
    except Exception:
        layout.label(text=f"{label} (check command)", icon='ERROR')


_stack_state = {}  # menu id -> (next index, time of last press)


def _resolve(context, path):
    path = path.strip()
    if path.startswith("values:"):  # one of your own values: values:Size
        v = context.window_manager.keyops_values.get(path[len("values:"):].strip())
        if v is None:
            raise KeyError(path)
        return v, v.field
    *parts, prop = path.split(".")
    data = context
    for part in parts:
        data = getattr(data, part)
    return data, prop


def run_item(context, pie, index):
    """Do what an item does, outside of a menu (stack, sticky and modal keys)."""
    item = pie.items[index]
    if _is_empty(item):
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
        bpy.ops.wm.call_menu(name=item.idname)
    elif item.kind == P:
        data, prop = _resolve(context, item.idname)
        if isinstance(getattr(data, prop), bool):
            setattr(data, prop, not getattr(data, prop))
    else:
        _run_step(item.idname, item.props, True)


class WM_OT_keyops_call_pie(Operator):
    bl_idname = "wm.keyops_call_pie"
    bl_label = "Key Ops Menu"
    bl_description = "Open a Key Ops menu"
    bl_options = {'INTERNAL'}

    pie: StringProperty() # type: ignore

    def invoke(self, context, event):
        pie = find_pie(self.pie)
        if pie is None:
            return {'CANCELLED'}
        if pie.only_mode != "ANY" and context.mode != pie.only_mode:
            return {'PASS_THROUGH'}  # let Blender's own key do its thing here
        items = list(pie.items)
        uid = pie.uid
        kind = pie.menu_type
        self._uid = uid

        if kind == "MENU":
            def draw_menu(menu, ctx):
                col = menu.layout.column()
                for i, item in enumerate(items):
                    draw_item(col, ctx, item, uid, i)
            context.window_manager.popup_menu(draw_menu, title=pie.name)
            return {'FINISHED'}

        if kind in {"DIALOG", "PANEL"}:
            width = 180 * max(1, pie.columns)
            if pie.dialog_mode == "DIALOG" and kind == "DIALOG":
                return context.window_manager.invoke_props_dialog(self, width=width, title=pie.name, confirm_text="Close")
            return context.window_manager.invoke_popup(self, width=width)

        if kind == "STACK":
            return self._run_stack(context, pie)

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

        def draw(menu, ctx):
            layout = menu.layout.menu_pie()
            for i, item in enumerate(items[:8]):
                draw_item(layout, ctx, item, uid, i)

        context.window_manager.popup_menu_pie(event, draw, title=pie.name)
        return {'FINISHED'}

    # ---- dialog / popup panel
    def draw(self, context):
        pie = find_pie(self.pie)
        if pie is None:
            return
        layout = self.layout
        if pie.menu_type == "DIALOG" and pie.dialog_mode == "POPUP":
            layout.label(text=pie.name)
        draw_grid(layout, context, pie)

    def execute(self, context):
        # Called from a script (no key press): stack keys still step, other menus need invoke.
        pie = find_pie(self.pie)
        if pie is None:
            return {'CANCELLED'}
        if pie.only_mode != "ANY" and context.mode != pie.only_mode:
            return {'PASS_THROUGH'}
        if pie.menu_type == "STACK":
            return self._run_stack(context, pie)
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
                        row.label(text="", icon=icon)
                    row.label(text=label, icon=icons[-1])
                    row.separator(factor=1.5)
            context.workspace.status_text_set(status)

    @staticmethod
    def _clear(context):
        if context.area:
            context.area.header_text_set(None)
        if context.workspace:
            context.workspace.status_text_set(None)

    def modal(self, context, event):
        pie = find_pie(self.pie)
        if pie is None:
            return {'CANCELLED'}
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


def draw_grid(layout, context, pie):
    """Dialogs and sidebar panels: items in columns, settings as real fields."""
    grid = layout.grid_flow(row_major=True, columns=max(1, pie.columns), even_columns=True, align=False)
    for i, item in enumerate(pie.items):
        draw_item(grid, context, item, pie.uid, i, slider=True)


def _panel_poll(editors):
    def poll(cls, context):
        prefs = get_keyops_prefs()
        return any(p.menu_type == "PANEL" and p.enabled and p.editor in editors for p in getattr(prefs, "pies", ()))
    return classmethod(poll)


def _panel_draw(editors):
    def draw(self, context):
        prefs = get_keyops_prefs()
        for p in prefs.pies:
            if p.menu_type == "PANEL" and p.enabled and p.editor in editors:
                if p.only_mode != "ANY" and context.mode != p.only_mode:
                    continue
                box = self.layout.box()
                box.label(text=p.name, icon=TYPE_ICON["PANEL"])
                draw_grid(box, context, p)
    return draw


_VIEW3D_EDITORS = {"3D View Generic", "Object Mode", "Mesh", "Sculpt", "Weight Paint", "Window"}
KEYOPS_PT_user_panels_3d = type("KEYOPS_PT_user_panels_3d", (bpy.types.Panel,), {
    "bl_label": "My Panels", "bl_idname": "KEYOPS_PT_user_panels_3d", "bl_space_type": 'VIEW_3D',
    "bl_region_type": 'UI', "bl_category": "Toolkit",
    "poll": _panel_poll(_VIEW3D_EDITORS), "draw": _panel_draw(_VIEW3D_EDITORS)})
KEYOPS_PT_user_panels_image = type("KEYOPS_PT_user_panels_image", (bpy.types.Panel,), {
    "bl_label": "My Panels", "bl_idname": "KEYOPS_PT_user_panels_image", "bl_space_type": 'IMAGE_EDITOR',
    "bl_region_type": 'UI', "bl_category": "Toolkit",
    "poll": _panel_poll({"UV Editor", "Image", "Window"}), "draw": _panel_draw({"UV Editor", "Image", "Window"})})
KEYOPS_PT_user_panels_node = type("KEYOPS_PT_user_panels_node", (bpy.types.Panel,), {
    "bl_label": "My Panels", "bl_idname": "KEYOPS_PT_user_panels_node", "bl_space_type": 'NODE_EDITOR',
    "bl_region_type": 'UI', "bl_category": "Toolkit",
    "poll": _panel_poll({"Node Editor", "Window"}), "draw": _panel_draw({"Node Editor", "Window"})})


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
        bpy.ops.wm.window_new()
        win = context.window_manager.windows[-1]
        area = win.screen.areas[0]
        area.type = 'TEXT_EDITOR'
        area.spaces.active.text = text
        context.window_manager.keyops_script_text = name
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
        elif self.menu_type != "PIE":
            names = {"MENU": "My Menu", "DIALOG": "My Dialog", "PANEL": "My Panel", "STACK": "My Stack Key",
                     "STICKY": "My Sticky Key", "MODAL": "My Modal Value"}
            pie.name = names.get(self.menu_type, "My Menu")
            pie.menu_type = self.menu_type
            pie["enabled"] = self.menu_type == "PANEL"  # panels need no key
            for _i in range({"DIALOG": 4, "PANEL": 4, "STACK": 2, "STICKY": 2}.get(self.menu_type, 1)):
                it = pie.items.add()
                if self.menu_type == "MODAL":
                    it.kind = P
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
        if pie is None or pie.menu_type == "PIE" or len(pie.items) >= ITEM_LIMIT.get(pie.menu_type, 64):
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


class KEYOPS_OT_slot_set_kind(Operator):
    bl_idname = "keyops.slot_set_kind"
    bl_label = "Item Type"
    bl_description = "Make this item a Python script or a label"
    bl_options = {'INTERNAL'}
    kind: StringProperty() # type: ignore

    def execute(self, context):
        prefs = get_keyops_prefs()
        item = _active_item(prefs, prefs.pie_slot)
        if item is None:
            return {'CANCELLED'}
        item.kind = self.kind
        if self.kind == SCRIPT and not item.script:
            item.script = "import bpy\n"
            item.label = item.label or "Python"
        if self.kind == LABEL:
            item.label = item.label or "Heading"
        _changed()
        return {'FINISHED'}


class KEYOPS_OT_pie_duplicate(Operator):
    bl_idname = "keyops.pie_duplicate"
    bl_label = "Duplicate"
    bl_description = "Make a copy of this menu"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_keyops_prefs()
        src = _active_pie(prefs)
        if src is None:
            return {'CANCELLED'}
        data = pies_to_data(prefs)["pies"][prefs.active_pie]
        data["uid"] = uuid.uuid4().hex[:12]
        data["name"] = src.name + " Copy"
        data["enabled"] = False
        data["preset"] = ""
        pies_from_data(prefs, {"pies": [data]}, True)
        prefs.active_pie = len(prefs.pies) - 1
        return {'FINISHED'}


class KEYOPS_OT_value_add(Operator):
    bl_idname = "keyops.value_add"
    bl_label = "Add Value"
    bl_description = "Add a value of your own. Use it in a Toggle/Setting item as values:Name"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        vals = context.window_manager.keyops_values
        v = vals.add()
        n = 1
        while f"Value {n}" in vals:
            n += 1
        v.name = f"Value {n}"
        _values_changed()
        return {'FINISHED'}


class KEYOPS_OT_value_remove(Operator):
    bl_idname = "keyops.value_remove"
    bl_label = "Remove Value"
    bl_options = {'INTERNAL'}
    index: IntProperty() # type: ignore

    def execute(self, context):
        vals = context.window_manager.keyops_values
        if 0 <= self.index < len(vals):
            vals.remove(self.index)
            _values_changed()
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
            pass  # middle and side mouse buttons can be used as keys
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

    @classmethod
    def description(cls, context, props):
        if props.scope == "PIES":
            return "Export pie menus to a .json file, to back them up or use them on another computer"
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
            return "Import pie menus from a .json file made with Export"
        return cls.bl_description
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


class KEYOPS_OT_pie_new_popup(Operator):
    bl_idname = "keyops.pie_new_popup"
    bl_label = "New"
    bl_description = "Make a new pie menu, popup menu, dialog, panel or special key"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=200)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        col = self.layout.column(align=True)
        for tid, name, _desc, icon, _n in MENU_TYPES:
            col.operator("keyops.pie_add", text=name, icon=icon).menu_type = tid


def _preset_key_text(preset):
    mods = [m for m, k in (("Ctrl", "ctrl"), ("Shift", "shift"), ("Alt", "alt")) if preset.get(k)]
    return " ".join(mods + [_KEY_NAMES.get(preset["key"], preset["key"])])


def _preset_summary(preset, limit=3):
    labels = [label for _kind, label, _icon, _idname, _props in preset["items"] if label]
    return ", ".join(labels[:limit]) + (", ..." if len(labels) > limit else "")


class KEYOPS_OT_pie_preset_popup(Operator):
    bl_idname = "keyops.pie_preset_popup"
    bl_label = "Add Preset"
    bl_description = "Add one of the ready-made pie menus"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=220)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        have = {p.preset for p in get_keyops_prefs().pies}
        col = self.layout.column(align=True)
        for preset in PRESETS:
            row = col.row(align=True)
            row.operator("keyops.pie_add", text=preset["name"], icon='MESH_CIRCLE').preset = preset["id"]
            mark = row.row(align=True)
            mark.active = False
            mark.label(text="", icon='CHECKMARK' if preset["id"] in have else 'BLANK1')


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


def _user_menu_items():
    """Your own Key Ops menus, so an item can open another menu."""
    prefs = get_keyops_prefs()
    menus = tuple((p.uid, p.name, p.menu_type) for p in getattr(prefs, "pies", ()) if p.menu_type != "PANEL")
    if menus not in _menu_items_cache:  # Blender keeps pointers to these strings: keep every list alive
        _menu_items_cache[menus] = [(f"K:{uid}", f"{name}  ·  open this Key Ops menu", "", TYPE_ICON.get(t, 'NONE'), 10000 + i)
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


def _search_items(self, context):
    base = _KEYOPS_SEARCH + _user_menu_items()
    if self.scope == "PANELS":
        return _blender_panel_items()
    return base if self.scope == "KEYOPS" else base + _all_operator_items()


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
    scope: EnumProperty(items=(("KEYOPS", "Key Ops", ""), ("ALL", "All of Blender", ""), ("PANELS", "Blender Panels", ""))) # type: ignore
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
    if action.startswith("P:"):
        name = action[2:]
        cls = getattr(bpy.types, name, None)
        item.kind, item.idname, item.props = PANEL_ITEM, name, ""
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
    if item.kind == LABEL and not empty and not selected:  # a heading: plain text, still clickable
        r = cell.row(align=True)
        r.alignment = 'CENTER'
        if prefs.pie_customize:
            r.operator("keyops.pie_slot_select", text=text, emboss=False,
                       icon=_icon(item.icon) if item.icon else 'NONE').slot = index
        else:
            r.label(text=text, icon=_icon(item.icon) if item.icon else 'NONE')
        return
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
    if item.kind == SCRIPT:
        return not item.script.strip()
    if item.kind == LABEL:
        return not item.label.strip()
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


LIST_LABELS = {
    "STACK": lambda i: f"Press {i + 1}",
    "STICKY": lambda i: ("While Held", "On Release")[i] if i < 2 else "",
    "MODAL": lambda i: "Setting",
}
TYPE_HINT = {
    "DIALOG": "Opens a small window with these buttons and settings",
    "PANEL": "Shows in the editor's sidebar (N), in the Toolkit tab",
    "STACK": "Each press runs the next item",
    "STICKY": "A toggle setting here is only changed while the key is held",
    "MODAL": "Move the mouse or scroll to change it. Options like step=0.1, min=0, max=1",
}


def draw_list_overview(layout, pie, prefs):
    """Stack, sticky and modal keys, dialogs and panels: a labelled list of their items."""
    col = layout.column(align=False)
    head = col.row()
    head.alignment = 'CENTER'
    head.label(text=pie.name, icon=TYPE_ICON.get(pie.menu_type, 'NONE'))
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
    if (prefs.pie_customize or not pie.items) and len(pie.items) < ITEM_LIMIT.get(pie.menu_type, 64):
        row = col.row()
        row.alignment = 'CENTER'
        add = row.row()
        add.ui_units_x = 11.0
        add.operator("keyops.menu_item_add", text="Add Item", icon='ADD')


def draw_pie_overview(layout, pie, prefs):
    """The pie drawn as buttons, in roughly the proportions Blender draws it."""
    if pie.menu_type == "MENU":
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


def draw_pies_tab(prefs, context, layout):
    if not prefs.pies:
        layout.label(text="No pie menus.")
        layout.operator("keyops.pie_preset_popup", text="Add Preset", icon='PRESET')
        return
    active = max(0, min(prefs.active_pie, len(prefs.pies) - 1))

    # pie list on the side: on/off, name, key
    outer = layout.split(factor=0.22)
    side = outer.column()
    side.prop(context.window_manager, "keyops_menu_filter", text="", icon='VIEWZOOM')
    lbox = side.box()
    col = lbox.column(align=True)
    flt = context.window_manager.keyops_menu_filter.strip().lower()
    for i, p in enumerate(prefs.pies):
        if flt and flt not in p.name.lower():
            continue
        row = col.row(align=True)
        row.prop(p, "enabled", text="")
        name = row.row(align=True)
        name.active = p.enabled or i == active
        name.operator("keyops.pie_select", text=p.name, icon=TYPE_ICON.get(p.menu_type, 'NONE'),
                      depress=(i == active)).index = i
        k = row.row(align=True)
        k.ui_units_x = 4.2
        k.alignment = 'RIGHT'
        k.active = False
        k.label(text=key_text(p))
    r = side.row(align=True)
    r.operator("keyops.pie_new_popup", text="New", icon='ADD')
    r.operator("keyops.pie_preset_popup", text="Add Preset", icon='PRESET')
    r.operator("keyops.settings_import", text="", icon='IMPORT').scope = "PIES"
    r.operator("keyops.settings_export", text="", icon='EXPORT').scope = "PIES"
    draw_pie_feel(prefs, side)
    draw_values(context, side)
    layout = outer.column()

    pie = prefs.pies[active]
    box = layout.box()
    head = box.row(align=True)
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
    is_menu = pie.menu_type != "PIE"
    labels = LIST_LABELS.get(pie.menu_type)
    head.label(text=(labels(slot) if labels else f"Item {slot + 1}") if is_menu else f"{POSITION_NAMES[ORDER[slot]]} slot")
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
    if item.kind == SCRIPT:
        sbox = col.box()
        lines = item.script.rstrip("\n").split("\n")
        if len(lines) > 1:  # longer scripts: a read-only preview, edited in the Text Editor
            pre = sbox.column(align=True)
            pre.scale_y = 0.8
            for line in lines[:8]:
                pre.label(text=line.replace("\t", "    ") or " ")
            if len(lines) > 8:
                more = pre.row()
                more.active = False
                more.label(text=f"... {len(lines) - 8} more lines")
        else:
            sbox.prop(item, "script", text="", icon='SCRIPT')
        r = sbox.row(align=True)
        r.operator("keyops.script_edit", text="Edit in Text Editor", icon='TEXT')
        r.operator("keyops.script_save", text="Save to Item", icon='FILE_TICK')
        note = sbox.row()
        note.active = False
        note.label(text="Runs like Text Editor > Run Script")
    more_kinds = col.row(align=True)
    for kind, text, icon in ((SCRIPT, "Python", 'SCRIPT'), (PANEL_ITEM, "Blender Panel", 'MENU_PANEL'), (LABEL, "Label", 'SYNTAX_OFF')):
        if kind == PANEL_ITEM:
            op = more_kinds.operator("keyops.pie_slot_search", text=text, icon=icon, depress=item.kind == kind)
            op.slot, op.scope = slot, "PANELS"
        else:
            more_kinds.operator("keyops.slot_set_kind", text=text, icon=icon, depress=item.kind == kind).kind = kind
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
    prow.prop(prefs, "pie_show_settings", text="Menu Settings", icon='DOWNARROW_HLT' if prefs.pie_show_settings else 'RIGHTARROW',
              emboss=False)
    if prefs.pie_show_settings:
        c = pbox.column()
        c.prop(pie, "name", text="Name")
        c.prop(pie, "menu_type", text="Type")
        c.prop(pie, "editor", text="Works In")
        c.prop(pie, "only_mode", text="Only In")
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
        r = c.row(align=True)
        if pie.preset in PRESET_BY_ID:
            r.operator("keyops.pie_reset", text="Reset to Preset")
        r.operator("keyops.pie_duplicate", text="Duplicate")
        r.operator("keyops.pie_remove", text="Delete")


def draw_values(context, layout):
    """Your own values: numbers, toggles and text that items and scripts can use."""
    prefs = get_keyops_prefs()
    box = layout.box()
    row = box.row()
    row.alignment = 'LEFT'
    row.prop(prefs, "pie_show_values", text="My Values", emboss=False,
             icon='DOWNARROW_HLT' if prefs.pie_show_values else 'RIGHTARROW')
    if not prefs.pie_show_values:
        return
    vals = context.window_manager.keyops_values
    for i, v in enumerate(vals):
        r = box.row(align=True)
        r.prop(v, "vtype", text="", icon_only=True)
        r.prop(v, "name", text="")
        r.prop(v, v.field, text="")
        r.operator("keyops.value_remove", text="", icon='X').index = i
    box.operator("keyops.value_add", text="Add Value", icon='ADD')
    if vals:
        note = box.column(align=True)
        note.active = False
        note.label(text="Use in an item as  values:Name")
        note.label(text="Scripts: wm.keyops_values[\"Name\"]")


PIE_TIMEOUT_DEFAULT = 6  # Blender's default pie animation timeout


def _get_no_lag(self):
    return bpy.context.preferences.view.pie_animation_timeout == 0


def _set_no_lag(self, value):
    bpy.context.preferences.view.pie_animation_timeout = 0 if value else PIE_TIMEOUT_DEFAULT


def draw_pie_feel(prefs, layout):
    """The no-lag option. It's Blender's own pie animation setting, shown here so it's easy to find:
    the person changes it, Key Ops never writes Blender's preferences itself."""
    layout.box().prop(bpy.context.window_manager, "keyops_no_lag_pies")


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
        mod = _module(module)
        before = set(items())
        getattr(mod, reg)()
        removed = set()
        for ptr, (km, kmi) in items().items():
            if ptr not in before and " Tool: " not in km.name:
                km.keymap_items.remove(kmi)
                removed.add(ptr)
        _forget_removed(mod, removed)


def _forget_removed(mod, removed):
    """The old modules keep lists of the (keymap, item) pairs they added, to remove them on
    unregister. Drop the ones removed above, so nothing tries to remove them a second time."""
    if not removed:
        return
    for value in vars(mod).values():
        if isinstance(value, list) and value and all(isinstance(e, tuple) and len(e) == 2 for e in value):
            keep = []
            for km, kmi in value:
                try:
                    if kmi.as_pointer() in removed:
                        continue
                except (ReferenceError, AttributeError):
                    continue
                keep.append((km, kmi))
            value[:] = keep


def _unregister_support():
    from .features import _module
    for module, _reg, unreg in reversed(_SUPPORT):
        try:
            getattr(_module(module), unreg)()
        except Exception:
            pass


property_classes = (KeyOpsValue, KeyOpsMacroStep, KeyOpsPieItem, KeyOpsPie, KeyOpsExportChoice)
classes = (WM_OT_keyops_run_script, KEYOPS_OT_script_edit, KEYOPS_OT_script_save, KEYOPS_OT_slot_set_kind,
           KEYOPS_OT_pie_duplicate, KEYOPS_OT_value_add, KEYOPS_OT_value_remove, KEYOPS_PT_user_panels_3d, KEYOPS_PT_user_panels_image, KEYOPS_PT_user_panels_node,
           WM_OT_keyops_call_pie, WM_OT_keyops_run_macro, KEYOPS_OT_menu_item_add, KEYOPS_OT_menu_item_remove,
           KEYOPS_OT_menu_item_move, KEYOPS_OT_slot_make_macro, KEYOPS_OT_macro_step_add, KEYOPS_OT_macro_step_remove,
           KEYOPS_OT_macro_step_move, KEYOPS_OT_pie_new_popup, KEYOPS_OT_pie_select, KEYOPS_OT_pie_add, KEYOPS_OT_pie_remove,
           KEYOPS_OT_pie_reset, KEYOPS_OT_pie_set_key, KEYOPS_OT_pie_preset_popup, KEYOPS_OT_pie_slot_search,
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
    bpy.types.WindowManager.keyops_values = CollectionProperty(type=KeyOpsValue)
    bpy.types.WindowManager.keyops_menu_filter = StringProperty(name="Find Menu", options={'TEXTEDIT_UPDATE'})
    bpy.types.WindowManager.keyops_script_text = StringProperty()
    bpy.types.WindowManager.keyops_no_lag_pies = BoolProperty(
        name="No Lag Pies", get=_get_no_lag, set=_set_no_lag,
        description="Open pie menus instantly, with no opening animation. Changes Blender's Pie Menu Animation Timeout")
    bpy.types.WindowManager.keyops_paste_command = StringProperty(
        name="Paste Command", description="Paste a bpy.ops command copied from Blender's Info editor", update=_paste_command)
    bpy.types.WindowManager.keyops_icon_category = EnumProperty(
        name="Category", items=[(c[0], c[1], f"{c[1]} icons") for c in ICON_CATEGORIES] + [("OTHER", "Other", "Everything else")])
    _register_support()
    sync_keymaps()


def unregister():
    from . import settings_store
    settings_store.flush_now()  # don't lose a change made just before disabling
    _remove_pie_keymaps()
    _unregister_support()
    del bpy.types.WindowManager.keyops_icon_filter
    del bpy.types.WindowManager.keyops_icon_category
    del bpy.types.WindowManager.keyops_paste_command
    del bpy.types.WindowManager.keyops_export_menus
    del bpy.types.WindowManager.keyops_values
    del bpy.types.WindowManager.keyops_menu_filter
    del bpy.types.WindowManager.keyops_script_text
    del bpy.types.WindowManager.keyops_no_lag_pies
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


def values_to_data(prefs):
    out = []
    for v in bpy.context.window_manager.keyops_values:
        out.append({"name": v.name, "type": v.vtype, "value": getattr(v, v.field)})
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
                setattr(v, v.field, entry.get("value"))
            except (TypeError, ValueError):
                pass
    finally:
        _loading = False


def _register_section():
    from . import settings_store
    settings_store.register_section("pie_menus", pies_to_data, pies_from_data, own_file=True,
                                    schema=PIE_SCHEMA, migrations=PIE_MIGRATIONS)
    settings_store.register_section("values", values_to_data, values_from_data, own_file=True, schema=1)


_register_section()
