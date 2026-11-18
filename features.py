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

from contextlib import contextmanager
from dataclasses import dataclass, field

import bpy

DOCS_URL = "https://dangry98.github.io/Key-Ops-Toolkit/"
PREFS_VERSION = 2
WELCOME_VERSION = 1

CATEGORIES = (
    ("MODELING", "Modeling", "Modeling tools, mesh editing and UVs", "EDITMODE_HLT"),
    ("TOOLS", "Active Tools", "Tools that sit in the toolbar and work as the active tool", "TOOL_SETTINGS"),
    ("OBJECT", "Object & Modifiers", "Object operations, modifiers and materials", "OBJECT_DATAMODE"),
    ("INDUSTRY", "Industry Standard", "Navigation, pivot, selection and delete the way other 3D apps do them",
     "ORIENTATION_GIMBAL"),
    ("GAME_ART", "Game Art", "Export, baking, LODs and poly counts", "EXPORT"),
    ("INTERFACE", "Interface", "Menus, outliner and legacy shortcuts", "WINDOW"),
)

STYLES = (
    ("ESSENTIALS", "Essentials", "Tools, panels and menus. No shortcuts", "NONE", 0),
    ("BLENDER_PLUS", "Blender+", "Shortcuts and pies only on keys Blender leaves free", "NONE", 1),
    ("INDUSTRY", "Industry", "Maya-style keys: Alt navigation, D pivot, Delete", "NONE", 2),
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
    Feature("merge_tool", "Merge Tool", "TOOLS",
            "Maya-style target weld for vertices and edges, in the toolbar.",
            "modeling-tools.html#merge-tool", "tools.merge_tool", "register_merge_tool", "unregister_merge_tool"),
    Feature("fast_loop_cut", "Fast Loop Cut", "TOOLS",
            "Previews the loop under the cursor and cuts on click, with no slide step.",
            "modeling-tools.html#fast-loop-cut", "tools.fast_loop_cut", "register_fast_loop_cut", "unregister_fast_loop_cut",
            keys=(_k("Alt R", "Mesh", "Fast Loop Cut tool"),), plus=True),
    Feature("cutter_tool", "Cutter Tool", "TOOLS",
            "Draw a box, circle or ngon to boolean-cut objects. Toolbar tool.",
            "modeling-tools.html#cutter", "tools.cutter_tool", "register_cutter_tool", "unregister_cutter_tool"),
    Feature("fast_merge", "Merge / Connect", "MODELING",
            "Merge to nearest or active vertex, and connect, with one key.",
            "extras.html#fast-merge", "operators.fast_merge", "register_fast_merge", "unregister_fast_merge",
            keys=(_k("1", "Mesh", "Fast merge", "Vertex select mode"),
                  _k("Shift 1", "Mesh", "Fast connect", "Extend vertex select"),
                  _k("Alt 1", "Mesh", "Merge menu")), keys_only=True),
    Feature("auto_delete", "Auto Delete", "INDUSTRY",
            "Delete in Edit Mode removes what you selected, with no menu.",
            "industry-standard.html#auto-delete", "operators.auto_delete", "register_auto_delete", "unregister_auto_delete",
            keys=(_k("Delete", "Mesh", "Context-aware delete", "Delete menu"),), keys_only=True),
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

    # ---------------- Industry standard
    Feature("maya_navigation", "Alt Navigation", "INDUSTRY",
            "Alt + left, middle and right mouse to orbit, pan and zoom.",
            "industry-standard.html#alt-navigation", "operators.maya_navigation", "register_maya_navigation", "unregister_maya_navigation",
            keys=(_k("Alt LMB drag", "3D View", "Orbit", "Loop select (Edit Mode)"),
                  _k("Alt MMB drag", "3D View / 2D editors", "Pan"),
                  _k("Alt RMB drag", "3D View / 2D editors", "Zoom")), keys_only=True),
    Feature("maya_pivot", "Maya Pivot", "INDUSTRY",
            "Hold or tap D to edit the pivot in Object and Edit Mode.",
            "industry-standard.html#maya-pivot", "operators.maya_pivot", "register_maya_pivot", "unregister_maya_pivot",
            keys=(_k("D", "Object / Mesh", "Edit pivot", "Annotate"),), keys_only=True),
    Feature("double_click_select_island", "Select Island", "INDUSTRY",
            "Double-click to select a linked island in mesh, UV and curves.",
            "industry-standard.html#select-island", "operators.double_click_select_island",
            "register_double_click_select_island", "unregister_double_click_select_island",
            keys=(_k("Double-click", "Mesh / UV / Curve", "Select island"),), keys_only=True),
    Feature("toggle_retopology", "Retopology Toggle", "INDUSTRY",
            "Switches overlay, snapping and tool to a retopology setup and back.",
            "industry-standard.html#toggle-retopology", "operators.toggle_retopology", "register_toggle_retopology", "unregister_toggle_retopology",
            keys=(_k("5", "Mesh", "Toggle retopology"),), plus=True),

    # ---------------- UV (Modeling)
    Feature("uv_tools", "UV Tools", "MODELING",
            "Smart UV Sync, UV Cut, unwrap in place, pack helpers and a UV editor panel.",
            "uv.html#uv-tools", "operators.uv_tools", "register_uv_tools", "unregister_uv_tools",
            keys=(_k("RMB", "UV Editor", "Smart UV sync", "Context menu"),
                  _k("X / Shift X", "UV Editor", "UV cut"),
                  _k("Alt 2", "Mesh", "Remove seam"))),

    # ---------------- Game art
    Feature("quick_export", "Quick Export", "GAME_ART",
            "Exports the selection; low/high collections go to a bake folder.",
            "toolkit.html#quick-export", "operators.quick_export", "register_quick_export", "unregister_quick_export",
            keys=(_k("Ctrl E", "3D View", "Quick export", "Edge menu (Edit Mode)"),), keys_only=True),
    Feature("quick_bake_name", "Quick Bake Name", "GAME_ART",
            "Names high and low poly pairs for baking.",
            "toolkit.html#quick-bake-name", "operators.quick_bake_name", "register_quick_bake_name", "unregister_quick_bake_name"),
    Feature("auto_lod", "Auto LOD", "GAME_ART",
            "Generates decimated LOD chains from selected meshes.",
            "toolkit.html#auto-lod", "operators.auto_lod", "register_auto_lod", "unregister_auto_lod"),
    Feature("cad_decimate", "CAD Decimate", "GAME_ART",
            "Decimates meshes with millions of triangles.",
            "toolkit.html#cad-decimate", "operators.cad_decimate", "register_cad_decimate", "unregister_cad_decimate"),
    Feature("polycount_list", "Polycount List", "GAME_ART",
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


def _module(path):
    """Import a feature module by its dotted path, with plain explicit imports (no dynamic loading)."""
    if path == "operators.atri_op":
        from .operators import atri_op as mod
    elif path == "operators.auto_delete":
        from .operators import auto_delete as mod
    elif path == "operators.auto_lod":
        from .operators import auto_lod as mod
    elif path == "operators.cad_decimate":
        from .operators import cad_decimate as mod
    elif path == "operators.double_click_select_island":
        from .operators import double_click_select_island as mod
    elif path == "operators.fast_merge":
        from .operators import fast_merge as mod
    elif path == "operators.looptools_menu":
        from .operators import looptools_menu as mod
    elif path == "operators.material_index":
        from .operators import material_index as mod
    elif path == "operators.maya_navigation":
        from .operators import maya_navigation as mod
    elif path == "operators.maya_pivot":
        from .operators import maya_pivot as mod
    elif path == "operators.modi_key":
        from .operators import modi_key as mod
    elif path == "operators.optional_keys":
        from .operators import optional_keys as mod
    elif path == "operators.outliner_options":
        from .operators import outliner_options as mod
    elif path == "operators.poly_count_list":
        from .operators import poly_count_list as mod
    elif path == "operators.quick_bake_name":
        from .operators import quick_bake_name as mod
    elif path == "operators.quick_export":
        from .operators import quick_export as mod
    elif path == "operators.toggle_retopology":
        from .operators import toggle_retopology as mod
    elif path == "operators.toolkit_panel":
        from .operators import toolkit_panel as mod
    elif path == "operators.uv_tools":
        from .operators import uv_tools as mod
    elif path == "operators.viewport_menu":
        from .operators import viewport_menu as mod
    elif path == "tools.cutter_tool":
        from .tools import cutter_tool as mod
    elif path == "tools.fast_loop_cut":
        from .tools import fast_loop_cut as mod
    elif path == "tools.merge_tool":
        from .tools import merge_tool as mod
    elif path == "operators.add_mesh":
        from .operators import add_mesh as mod
    elif path == "operators.add_modifier":
        from .operators import add_modifier as mod
    elif path == "operators.origin_to_selection":
        from .operators import origin_to_selection as mod
    elif path == "operators.flatten":
        from .operators import flatten as mod
    elif path == "menu.pies":
        from .menu import pies as mod
    else:
        raise KeyError(path)
    return mod


def _call(f, which):
    if f.id == "legacy_shortcuts":
        return (_legacy_register if which == "register" else _legacy_unregister)()
    getattr(_module(f.module), getattr(f, which))()


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
    """(enabled, keys) a welcome-screen preset gives one feature."""
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
    sync_all()
    from . import pie_menus
    if not pie_menus.loaded_from_disk:  # pies saved by the user (pie_menus.json) are never overwritten
        pie_menus.install_presets(p, style)


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
    (register_feature if on else unregister_feature)(f)
    apply_key_state(feature_id)


def on_keys_changed(feature_id):
    if is_suspended():
        return
    p = prefs()
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
        "enable_add_objects_pie", "enable_cursor_pie", "enable_workspace_pie",
        "auto_delete_dissolv_edge", "maya_pivot_behavior", "fast_merge_merge_options",
        "add_object_pie_use_relative", "material_list_type", "experimental"]
    changed_settings = any((p.is_property_set(n) if hasattr(p, n) else p.get(n) is not None) for n in legacy_names)
    # A 0.2 user who never changed a setting leaves nothing saved. But Blender re-enables an installed
    # add-on at startup without marking the preferences as changed, while enabling it in Preferences
    # (a new install) marks them changed first. So "enabled at startup" means it was installed before.
    enabled_at_startup = not bpy.app.background and not bpy.context.preferences.is_dirty
    upgrading = changed_settings or enabled_at_startup
    with suspended():
        if upgrading:
            # Keep every feature and shortcut exactly as it was in 0.2.x
            for f in FEATURES:
                if f.keys:
                    setattr(p, f"keys_{f.id}", not f.optional)
            p.shortcut_style = "INDUSTRY"
            p.show_whats_new = True
            p.welcome_version = WELCOME_VERSION
        p.prefs_version = PREFS_VERSION
    if upgrading:
        from . import pie_menus
        if pie_menus.loaded_from_disk:
            return  # pies already saved in pie_menus.json
        pie_menus.install_presets(p, "INDUSTRY")  # the pies 0.2 had on by default
        # 0.2 stored one switch per pie; carry over any the user changed
        old_switches = {"add_objects": "enable_add_objects_pie", "add_modifier": "enable_add_modifier_pie",
                        "flatten": "enable_flatten_pie", "cursor": "enable_cursor_pie",
                        "workspace": "enable_workspace_pie", "utility": "enable_utility_pie",
                        "uv_space": "enable_uv_pies", "uv_islands": "enable_uv_pies"}
        for pie in p.pies:
            saved = p.get(old_switches.get(pie.preset, ""))
            if saved is not None:
                pie["enabled"] = bool(saved)
        pie_menus.sync_keymaps()
    if not upgrading:
        # Quiet until the welcome screen's choice: no shortcuts, no pies
        apply_style("ESSENTIALS")
