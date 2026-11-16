"""Single source of truth for every Key Ops feature.

Each Feature declares what it is (name, category, description, docs), how to
register it (module + function names) and the shortcuts it adds, with what each
one replaces in Blender's default keymap. Preferences, the welcome screen, the
cheat sheet and the registration code all read from FEATURES.

Shortcut handling only ever touches Key Ops' own items in
``keyconfigs.addon``: they are created by each feature's register function,
tracked here, and switched on/off with ``kmi.active``. The user's keymap is
never edited.
"""

import importlib
from contextlib import contextmanager
from dataclasses import dataclass, field

import bpy

DOCS_URL = "https://dangry98.github.io/Key-Ops-Toolkit/"
PREFS_VERSION = 2
WELCOME_VERSION = 1

CATEGORIES = (
    ("MODELING", "Modeling", "Modeling tools and mesh editing", "EDITMODE_HLT"),
    ("OBJECT", "Object & Modifiers", "Object operations, modifiers and materials", "OBJECT_DATAMODE"),
    ("PIES", "Pie Menus", "Pie menus", "MESH_CIRCLE"),
    ("NAV", "Navigation & Selection", "Viewport navigation, pivot and selection", "ORIENTATION_GIMBAL"),
    ("UV", "UV", "UV editing", "UV"),
    ("PIPELINE", "Pipeline", "Export, baking, LODs and poly counts", "EXPORT"),
    ("INTERFACE", "Interface", "Menus, outliner and legacy shortcuts", "WINDOW"),
)

STYLES = (
    ("ESSENTIALS", "Essentials", "Tools, panels and menus. No shortcuts", "CHECKMARK", 0),
    ("BLENDER_PLUS", "Blender+", "Adds shortcuts only on keys Blender leaves free", "BLENDER", 1),
    ("INDUSTRY", "Industry", "Maya-style: Alt navigation, D pivot, Delete, 1 merge. Same as Key Ops 0.2", "VIEW3D", 2),
    ("CUSTOM", "Custom", "Choose each feature and its shortcuts yourself", "PREFERENCES", 3),
)


@dataclass(frozen=True)
class Key:
    key: str            # as shown to people, e.g. "Shift Alt A"
    editor: str         # "Mesh", "3D View", ...
    action: str
    replaces: str = ""  # Blender default it takes over; "" means the key is free


@dataclass(frozen=True)
class Feature:
    id: str             # matches prefs.enable_<id> and prefs.keys_<id>
    name: str
    category: str
    description: str
    docs: str
    module: str = ""
    register: str = ""
    unregister: str = ""
    keys: tuple = ()
    default_on: bool = True     # on in the presets (Essentials/Blender+/Industry)
    keys_only: bool = False     # does nothing useful without its shortcuts
    plus: bool = False          # keys are all free -> on in Blender+
    optional: bool = False      # opt-in extra, never switched on by a preset
    experimental: bool = False
    requires: str = ""          # another feature id that must be enabled
    min_version: tuple = (4, 2, 0)

    @property
    def replaced(self):
        return [k for k in self.keys if k.replaces]

    def available(self):
        return bpy.app.version >= self.min_version


def _k(*a):
    return Key(*a)


FEATURES = (
    # ---------------- Modeling
    Feature("merge_tool", "Merge Tool", "MODELING",
            "Maya-style target weld for vertices and edges, in the toolbar.",
            "modeling-tools.html#merge-tool", "tools.merge_tool", "register_merge_tool", "unregister_merge_tool"),
    Feature("fast_loop_cut", "Fast Loop Cut", "MODELING",
            "Previews the loop under the cursor and cuts on click, with no slide step.",
            "modeling-tools.html#fast-loop-cut", "tools.fast_loop_cut", "register_fast_loop_cut", "unregister_fast_loop_cut",
            keys=(_k("Alt R", "Mesh", "Fast Loop Cut tool"),), plus=True),
    Feature("cutter_tool", "Cutter Tool", "MODELING",
            "Draw a box, circle or ngon to boolean-cut objects. Toolbar tool.",
            "modeling-tools.html#cutter", "tools.cutter_tool", "register_cutter_tool", "unregister_cutter_tool"),
    Feature("fast_merge", "Merge / Connect", "MODELING",
            "Merge to nearest or active vertex, and connect, with one key.",
            "extras.html#fast-merge", "operators.fast_merge", "register_fast_merge", "unregister_fast_merge",
            keys=(_k("1", "Mesh", "Fast merge", "Vertex select mode"),
                  _k("Shift 1", "Mesh", "Fast connect", "Extend vertex select"),
                  _k("Alt 1", "Mesh", "Merge menu")), keys_only=True),
    Feature("auto_delete", "Auto Delete", "MODELING",
            "Delete in Edit Mode removes what you selected, with no menu.",
            "industry-standard.html#auto-delete", "operators.auto_delete", "register_auto_delete", "unregister_auto_delete",
            keys=(_k("Delete", "Mesh", "Context-aware delete", "Delete menu"),), keys_only=True),
    Feature("flatten_pie", "Flatten Pie", "MODELING",
            "Flattens the selection left, right, top or bottom from the current view.",
            "pie-menus.html#flatten-pie", "operators.flatten", "register_flatten_pie", "unregister_flatten_pie",
            keys=(_k("Alt 3", "Mesh", "Flatten pie"),), keys_only=True, plus=True),
    Feature("atri_op", "Attribute Operations", "MODELING",
            "Select and assign face, edge and vertex attributes in Edit Mode.",
            "extras.html#attribute-operations", "operators.atri_op", "register_atri_op", "unregister_atri_op"),
    Feature("looptools_menu", "LoopTools Menu", "MODELING",
            "Adds LoopTools to the Edit Mode context menu.",
            "https://docs.blender.org/manual/en/latest/addons/mesh/looptools.html",
            "operators.looptools_menu", "register_looptools_menu", "unregister_looptools_menu", min_version=(5, 3, 0)),

    # ---------------- Object & Modifiers
    Feature("toolkit_panel", "Object Toolkit", "OBJECT",
            "N-panel tools: combine, separate, apply, mirror, booleans and edit-mode operations.",
            "toolkit.html#toolkit-panel", "operators.toolkit_panel", "register_toolkit_panel", "unregister_toolkit_panel",
            keys=(_k("Alt C", "Object Mode", "Smart combine", "Convert menu"),
                  _k("Alt X", "Object Mode", "Fast mirror"),
                  _k("Ctrl Numpad - + * /", "Object Mode", "Boolean difference / union / intersect / slice"),
                  _k("Alt 3", "Object Mode", "Snap to floor"),
                  _k("D", "Mesh", "Mirror options", "Annotate"),
                  _k("Alt M", "Object Mode", "Material menu"))),
    Feature("modi_key", "Modifier Keys", "OBJECT",
            "Reorder, toggle, apply and delete modifiers with keys while hovering the Properties editor.",
            "extras.html#modifier-key", "operators.modi_key", "register_modi_key", "unregister_modi_key",
            keys=(_k("Q / E", "Properties", "Move modifier up / down"),
                  _k("W / S", "Properties", "Select modifier up / down"),
                  _k("1 2 3 4", "Properties", "Toggle render / viewport / edit / cage"),
                  _k("A / X / D", "Properties", "Apply / delete / duplicate modifier")), keys_only=True, plus=True),
    Feature("material_index", "Material Utils", "OBJECT",
            "Material list with preview icons and quick assign.",
            "toolkit.html#material-utils", "operators.material_index", "register_material_index", "unregister_material_index",
            keys=(_k("Alt M", "Mesh", "Material menu", "Split menu"),)),

    # ---------------- Pie menus
    Feature("add_objects_pie", "Add Objects Pie", "PIES",
            "Add primitives at a size relative to the view, so they are never too big or too small.",
            "pie-menus.html#add-objects-pie", "operators.add_mesh", "register_add_objects_pie", "unregister_add_objects_pie",
            keys=(_k("Shift Alt A", "3D View", "Add Objects pie"),), keys_only=True, plus=True),
    Feature("add_menu_shift_a", "Add Objects Pie on Shift A", "PIES",
            "Also opens the Add Objects pie on Shift A, in place of Blender's Add menu.",
            "pie-menus.html#add-objects-pie", "operators.optional_keys", "register_add_menu_shift_a", "unregister_add_menu_shift_a",
            keys=(_k("Shift A", "Object / Mesh", "Add Objects pie", "Add menu"),), keys_only=True, optional=True,
            requires="add_objects_pie"),
    Feature("add_modifier_pie", "Add Modifier Pie", "PIES",
            "The modifiers you use most, one flick away.",
            "pie-menus.html#add-modifier-pie", "operators.add_modifier", "register_add_modifier_pie", "unregister_add_modifier_pie",
            keys=(_k("Shift Q", "Window", "Add Modifier pie"),), keys_only=True, plus=True),
    Feature("cursor_pie", "Cursor & Origin Pie", "PIES",
            "A fuller cursor and origin snapping pie.",
            "pie-menus.html#cursor-pie", "operators.origin_to_selection", "register_cursor_pie", "unregister_cursor_pie",
            keys=(_k("Shift S", "3D View", "Cursor & Origin pie", "Snap pie"),), keys_only=True),
    Feature("view_pie_space", "View Pie on Space", "PIES",
            "Opens Blender's View pie on Space in the 3D View. Play stays on Space everywhere else.",
            "pie-menus.html", "operators.optional_keys", "register_view_pie_space", "unregister_view_pie_space",
            keys=(_k("Space", "3D View", "View pie", "Play animation"),), keys_only=True, optional=True),
    Feature("workspace_pie", "Workspace Pie", "PIES",
            "Switch workspaces from anywhere.",
            "pie-menus.html#workspace-pie", "menu.pies", "register_workspace_pie", "unregister_workspace_pie",
            keys=(_k("Shift \\", "Window", "Workspace pie"),), keys_only=True, default_on=False),
    Feature("utility_pie", "Utility Pie", "PIES",
            "Common mesh and UV actions in Object and Edit Mode.",
            "pie-menus.html#utility-pie", "menu.pies", "register_utility_pie", "unregister_utility_pie",
            keys=(_k("U", "Object / Mesh", "Utility pie", "UV unwrap menu"),), keys_only=True, default_on=False,
            experimental=True),
    Feature("uv_pies", "UV Pies", "PIES",
            "Unwrap and island actions in the UV editor.",
            "pie-menus.html#uv-pies", "menu.pies", "register_uv_pies", "unregister_uv_pies",
            keys=(_k("Q", "UV Editor", "UV pie"), _k("Space", "UV Editor", "UV pie", "Play animation")),
            keys_only=True, default_on=False, experimental=True),

    # ---------------- Navigation & selection
    Feature("maya_navigation", "Alt Navigation", "NAV",
            "Alt + left, middle and right mouse to orbit, pan and zoom.",
            "industry-standard.html#alt-navigation", "operators.maya_navigation", "register_maya_navigation", "unregister_maya_navigation",
            keys=(_k("Alt LMB drag", "3D View", "Orbit", "Loop select (Edit Mode)"),
                  _k("Alt MMB drag", "3D View / 2D editors", "Pan"),
                  _k("Alt RMB drag", "3D View / 2D editors", "Zoom")), keys_only=True),
    Feature("maya_pivot", "Maya Pivot", "NAV",
            "Hold or tap D to edit the pivot in Object and Edit Mode.",
            "industry-standard.html#maya-pivot", "operators.maya_pivot", "register_maya_pivot", "unregister_maya_pivot",
            keys=(_k("D", "Object / Mesh", "Edit pivot", "Annotate"),), keys_only=True),
    Feature("double_click_select_island", "Select Island", "NAV",
            "Double-click to select a linked island in mesh, UV and curves.",
            "industry-standard.html#select-island", "operators.double_click_select_island",
            "register_double_click_select_island", "unregister_double_click_select_island",
            keys=(_k("Double-click", "Mesh / UV / Curve", "Select island"),), keys_only=True),
    Feature("toggle_retopology", "Retopology Toggle", "NAV",
            "Switches overlay, snapping and tool to a retopology setup and back.",
            "industry-standard.html#toggle-retopology", "operators.toggle_retopology", "register_toggle_retopology", "unregister_toggle_retopology",
            keys=(_k("5", "Mesh", "Toggle retopology"),), plus=True),

    # ---------------- UV
    Feature("uv_tools", "UV Tools", "UV",
            "Smart UV Sync, UV Cut, unwrap in place, pack helpers and a UV editor panel.",
            "uv.html#uv-tools", "operators.uv_tools", "register_uv_tools", "unregister_uv_tools",
            keys=(_k("RMB", "UV Editor", "Smart UV sync", "Context menu"),
                  _k("X / Shift X", "UV Editor", "UV cut"),
                  _k("Alt 2", "Mesh", "Remove seam"))),

    # ---------------- Pipeline
    Feature("quick_export", "Quick Export", "PIPELINE",
            "Exports the selection; low/high collections go to a bake folder.",
            "toolkit.html#quick-export", "operators.quick_export", "register_quick_export", "unregister_quick_export",
            keys=(_k("Ctrl E", "3D View", "Quick export", "Edge menu (Edit Mode)"),), keys_only=True),
    Feature("quick_bake_name", "Quick Bake Name", "PIPELINE",
            "Names high and low poly pairs for baking.",
            "toolkit.html#quick-bake-name", "operators.quick_bake_name", "register_quick_bake_name", "unregister_quick_bake_name"),
    Feature("auto_lod", "Auto LOD", "PIPELINE",
            "Generates decimated LOD chains from selected meshes.",
            "toolkit.html#auto-lod", "operators.auto_lod", "register_auto_lod", "unregister_auto_lod"),
    Feature("cad_decimate", "CAD Decimate", "PIPELINE",
            "Decimates meshes with millions of triangles.",
            "toolkit.html#cad-decimate", "operators.cad_decimate", "register_cad_decimate", "unregister_cad_decimate"),
    Feature("polycount_list", "Polycount List", "PIPELINE",
            "Every object with its poly count and modifier evaluation time.",
            "toolkit.html#polycount-list", "operators.poly_count_list", "register_polycount_list", "unregister_polycount_list"),

    # ---------------- Interface
    Feature("viewport_menu", "Viewport Menu", "INTERFACE",
            "Overlay menu with quick toggles and silhouette mode.",
            "extras.html#viewport-menu", "operators.viewport_menu", "register_viewport_menu", "unregister_viewport_menu",
            keys=(_k("Alt V", "3D View", "Viewport menu", "Rip fill (Edit Mode)"),), keys_only=True),
    Feature("outliner_options", "Outliner Options", "INTERFACE",
            "Auto-focus and extra click behaviour in the Outliner.",
            "extras.html#outliner-options", "operators.outliner_options", "register_outliner_options", "unregister_outliner_options",
            keys=(_k("LMB / RMB click", "Outliner", "Outliner click", "Outliner select"),
                  _k("A / Alt A", "Outliner", "Select all / none")), keys_only=True),
    Feature("w_context_menu", "W Context Menu", "INTERFACE",
            "Opens the right-click context menu on W, as in Blender 2.7x.",
            "extras.html#legacy-shortcuts", "operators.optional_keys", "register_w_context_menu", "unregister_w_context_menu",
            keys=(_k("W", "Object / Mesh / Curve", "Context menu", "Select tool cycle"),), keys_only=True, optional=True),
    Feature("legacy_shortcuts", "Legacy Shortcuts", "INTERFACE",
            "Shortcuts from Blender 2.7x: Alt P poke, < > grow and shrink, UV Ctrl A/P/C/V.",
            "extras.html#legacy-shortcuts", "", "", "",
            keys=(_k("Alt P", "Mesh", "Poke faces"),
                  _k("< / Shift <", "Mesh / UV", "Select more / less"),
                  _k("Ctrl A / P / C / V", "UV Editor", "Average scale / pack / copy / paste UVs")), keys_only=True),
)

FEATURE_BY_ID = {f.id: f for f in FEATURES}

# Settings that look like features (enable_*) but belong to another feature
SUB_SETTINGS = {"legacy_collection_shortcuts"}

_tracked = {}        # feature id -> [(KeyMap, KeyMapItem)] in keyconfigs.addon
_registered = set()  # feature ids currently registered
_suspend = 0         # >0 while presets/migration write props, so update callbacks stay quiet


def prefs():
    from .utils.pref_utils import get_keyops_prefs
    return get_keyops_prefs()


def visible_features(p=None):
    p = p or prefs()
    return [f for f in FEATURES if f.available() and (not f.experimental or p.experimental)]


# ---------------------------------------------------------------- key tracking

def _addon_items():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return {}
    return {kmi.as_pointer(): (km, kmi) for km in kc.keymaps for kmi in km.keymap_items}


def _is_shortcut_keymap(km):
    # Toolbar tools keep their own internal keymaps ("3D View Tool: ..."). Those are
    # how the tool works, not shortcuts, so they are never switched off.
    return " Tool: " not in km.name and not km.is_modal


@contextmanager
def capture(feature_id):
    """Track keymap items created inside the block as belonging to feature_id."""
    before = set(_addon_items())
    try:
        yield
    finally:
        new = [(ptr, km, kmi) for ptr, (km, kmi) in _addon_items().items()
               if ptr not in before and _is_shortcut_keymap(km)]
        if new:
            _tracked.setdefault(feature_id, []).extend(new)
            apply_key_state(feature_id)


def tracked_items(feature_id):
    """(KeyMap, KeyMapItem) pairs still alive in keyconfigs.addon, checked by pointer."""
    entries = _tracked.get(feature_id)
    if not entries:
        return []
    live = _addon_items()
    alive = [(ptr, km, kmi) for ptr, km, kmi in entries if ptr in live]
    _tracked[feature_id] = alive
    return [(km, kmi) for _ptr, km, kmi in alive]


def keys_active(feature_id, p=None):
    p = p or prefs()
    return bool(getattr(p, f"keys_{feature_id}", False)) and not p.pause_shortcuts


def apply_key_state(feature_id, p=None):
    on = keys_active(feature_id, p)
    for _km, kmi in tracked_items(feature_id):
        kmi.active = on


def apply_all_key_states():
    p = prefs()
    for fid in list(_registered):
        apply_key_state(fid, p)


# ---------------------------------------------------------------- lifecycle

def _legacy_register():
    from .operators.legacy_shortcuts import register_legacy_shortcuts_keymaps, register_legacy_collection_shortcuts
    register_legacy_shortcuts_keymaps()
    if bpy.app.version >= (5, 0, 0) and prefs().enable_legacy_collection_shortcuts:
        register_legacy_collection_shortcuts()


def _legacy_unregister():
    from .operators.legacy_shortcuts import unregister_legacy_shortcuts, unregister_legacy_collection_shortcuts
    unregister_legacy_shortcuts()
    if bpy.app.version >= (5, 0, 0):
        unregister_legacy_collection_shortcuts()


def _call(f, which):
    if f.id == "legacy_shortcuts":
        return (_legacy_register if which == "register" else _legacy_unregister)()
    mod = importlib.import_module("." + f.module, __package__)
    getattr(mod, getattr(f, which))()


def register_feature(f):
    if f.id in _registered or not f.available():
        return
    if f.requires and not getattr(prefs(), f"enable_{f.requires}", False):
        return
    with capture(f.id):
        _call(f, "register")
    _registered.add(f.id)
    # Optional extras that depend on this feature come back with it
    for dep in FEATURES:
        if dep.requires == f.id and getattr(prefs(), f"enable_{dep.id}", False):
            register_feature(dep)


def unregister_feature(f):
    if f.id not in _registered:
        return
    for dep in FEATURES:
        if dep.requires == f.id:
            unregister_feature(dep)
    try:
        _call(f, "unregister")
    finally:
        _registered.discard(f.id)
        # Anything the feature's own unregister left behind is ours to remove
        for km, kmi in tracked_items(f.id):
            km.keymap_items.remove(kmi)
        _tracked.pop(f.id, None)


def sync_all():
    """Make registered features match the enable_* preferences."""
    p = prefs()
    for f in FEATURES:
        want = bool(getattr(p, f"enable_{f.id}", False))
        if want and f.id not in _registered:
            register_feature(f)
        elif not want and f.id in _registered:
            unregister_feature(f)
    apply_all_key_states()


def unregister_all():
    for f in reversed(FEATURES):
        unregister_feature(f)


# ---------------------------------------------------------------- presets

def style_values(style, f):
    """(enabled, keys) a preset gives one feature, or None for Custom."""
    if style == "CUSTOM":
        return None
    if f.optional or not f.default_on or f.experimental:
        return False, False
    if style == "ESSENTIALS":
        return (not f.keys_only), False
    if style == "BLENDER_PLUS":
        return (not f.keys_only or f.plus), (f.plus and bool(f.keys))
    return True, bool(f.keys)  # INDUSTRY


@contextmanager
def suspended():
    global _suspend
    _suspend += 1
    try:
        yield
    finally:
        _suspend -= 1


def is_suspended():
    return _suspend > 0


def apply_style(style):
    p = prefs()
    with suspended():
        for f in FEATURES:
            vals = style_values(style, f)
            if vals is None:
                continue
            setattr(p, f"enable_{f.id}", vals[0])
            if f.keys:
                setattr(p, f"keys_{f.id}", vals[1])
        p.style_modified = False
    sync_all()


def matches_style(style, p=None):
    p = p or prefs()
    for f in FEATURES:
        vals = style_values(style, f)
        if vals is None:
            return False
        if bool(getattr(p, f"enable_{f.id}")) != vals[0]:
            return False
        if f.keys and getattr(p, f"enable_{f.id}") and bool(getattr(p, f"keys_{f.id}")) != vals[1]:
            return False
    return True


# ---------------------------------------------------------------- update callbacks (used by preferences)

def on_enable_changed(feature_id):
    if is_suspended():
        return
    p = prefs()
    f = FEATURE_BY_ID[feature_id]
    on = getattr(p, f"enable_{feature_id}")
    if on and f.keys_only and f.keys and not getattr(p, f"keys_{feature_id}"):
        with suspended():
            setattr(p, f"keys_{feature_id}", True)  # a keys-only feature is useless without them
    p.style_modified = True
    (register_feature if on else unregister_feature)(f)
    apply_key_state(feature_id)


def on_keys_changed(feature_id):
    if is_suspended():
        return
    p = prefs()
    p.style_modified = True
    f = FEATURE_BY_ID[feature_id]
    if getattr(p, f"keys_{feature_id}") and f.keys_only and not getattr(p, f"enable_{feature_id}"):
        with suspended():
            setattr(p, f"enable_{feature_id}", True)  # ticking a keys-only feature's shortcuts turns it on
        register_feature(f)
    apply_key_state(feature_id)


# ---------------------------------------------------------------- stats

def stats(p=None):
    p = p or prefs()
    feats = keys = repl = 0
    for f in FEATURES:
        if not f.available() or not getattr(p, f"enable_{f.id}", False):
            continue
        feats += 1
        if f.keys and keys_active(f.id, p):
            keys += len(f.keys)
            repl += len(f.replaced)
    return feats, keys, repl


def live_shortcut_count():
    return sum(1 for fid in _registered for _km, kmi in tracked_items(fid) if kmi.active)


# ---------------------------------------------------------------- first run / upgrade

def migrate():
    """Decide between a fresh install (Essentials, welcome) and an upgrade (keep everything)."""
    p = prefs()
    if p.prefs_version >= PREFS_VERSION:
        return
    legacy_names = [f"enable_{f.id}" for f in FEATURES] + [
        "auto_delete_dissolv_edge", "maya_pivot_behavior", "fast_merge_merge_options",
        "add_object_pie_use_relative", "material_list_type", "experimental"]
    upgrading = any(p.is_property_set(n) for n in legacy_names if hasattr(p, n))
    with suspended():
        if upgrading:
            # Keep every feature and shortcut exactly as it was in 0.2.x
            for f in FEATURES:
                if f.keys:
                    setattr(p, f"keys_{f.id}", not f.optional)
            p.shortcut_style = "CUSTOM"
            p.style_modified = False
            p.show_whats_new = True
        p.prefs_version = PREFS_VERSION
    if not upgrading:
        apply_style("ESSENTIALS")
        with suspended():
            p.shortcut_style = "ESSENTIALS"
