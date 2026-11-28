"""Single source of truth for every Key Ops feature.

Each Feature declares what it is (name, category, description, docs) and the
shortcuts it adds, with what each one replaces in Blender's default keymap.
Preferences, the welcome screen and the cheat sheet read from FEATURES.

Every feature's classes and shortcuts are registered once, in __init__.py. The
switches in the preferences don't register anything: they turn the feature's
own shortcuts on or off (``kmi.active``), panels and menus check the switch
when they draw, and the few features that change something in Blender itself
(a toolbar tool, a handler) do that in their module's set_enabled().
"""

from contextlib import contextmanager
from dataclasses import dataclass

import bpy

from .operators import (
    auto_delete, double_click_select_island, fast_merge, legacy_shortcuts, material_index, maya_navigation,
    maya_pivot, modi_key, optional_keys, outliner_options, poly_count_list, quick_export, smart_extrude, snap_to_floor,
    toggle_retopology, toolkit_panel, uv_tools, viewport_menu,
)
from .tools import cutter_tool, fast_loop_cut, merge_tool

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
            "modeling-tools.html#merge-tool"),
    Feature("fast_loop_cut", "Fast Loop Cut", "TOOLS",
            "Previews the loop under the cursor and cuts on click, with no slide step.",
            "modeling-tools.html#fast-loop-cut",
            keys=(_k("Alt R", "Mesh", "Fast Loop Cut tool"),), plus=True),
    Feature("cutter_tool", "Cutter Tool", "TOOLS",
            "Draw a box, circle or ngon to boolean-cut objects. Toolbar tool.",
            "modeling-tools.html#cutter"),
    Feature("push_pull", "Push / Pull", "TOOLS",
            "Drag faces out or in: square walls stretch, otherwise it extrudes and merges or cuts. Toolbar tool.",
            "modeling-tools.html#push-pull"),
    Feature("fast_merge", "Merge / Connect", "MODELING",
            "Merge to nearest or active vertex, and connect, with one key.",
            "extras.html#fast-merge",
            keys=(_k("1", "Mesh", "Fast merge", "Vertex select mode"),
                  _k("Shift 1", "Mesh", "Fast connect", "Extend vertex select"),
                  _k("Alt 1", "Mesh", "Merge menu")), keys_only=True),
    Feature("auto_delete", "Auto Delete", "INDUSTRY",
            "Delete in Edit Mode removes what you selected, with no menu.",
            "industry-standard.html#auto-delete",
            keys=(_k("Delete", "Mesh", "Context-aware delete", "Delete menu"),
                  _k("X", "Object Mode", "Delete, confirm optional", "Delete with confirm")), keys_only=True),
    Feature("atri_op", "Attribute Operations", "MODELING",
            "Select and assign face, edge and vertex attributes in Edit Mode.",
            "extras.html#attribute-operations"),
    Feature("looptools_menu", "LoopTools Menu", "MODELING",
            "Adds LoopTools to the Edit Mode context menu.",
            "https://docs.blender.org/manual/en/latest/addons/mesh/looptools.html", min_version=(5, 3, 0)),

    # ---------------- Object & Modifiers
    Feature("toolkit_panel", "Object Toolkit", "OBJECT",
            "N-panel tools: combine, separate, apply, mirror, booleans and edit-mode operations.",
            "toolkit.html#toolkit-panel",
            keys=(_k("Alt C", "Object Mode", "Smart combine", "Convert menu"),
                  _k("Alt X", "Object Mode", "Fast mirror"),
                  _k("Ctrl Numpad - + * /", "Object Mode", "Boolean difference / union / intersect / slice"),
                  _k("Alt 3", "Object Mode", "Snap to floor"),
                  _k("Alt C", "Mesh", "Clean up"),
                  _k("D", "Mesh", "Mirror options", "Annotate"),
                  _k("Alt M", "Object Mode", "Material menu"))),
    Feature("modi_key", "Modifier Keys", "OBJECT",
            "Reorder, toggle, apply and delete modifiers with keys while hovering the Properties editor.",
            "extras.html#modifier-key",
            keys=(_k("Q / E", "Properties", "Move modifier up / down"),
                  _k("W / S", "Properties", "Select modifier up / down"),
                  _k("1 2 3 4", "Properties", "Toggle render / viewport / edit / cage"),
                  _k("A / X / D", "Properties", "Apply / delete / duplicate modifier")), keys_only=True, plus=True),
    Feature("material_index", "Material Utils", "OBJECT",
            "Material list with preview icons and quick assign.",
            "toolkit.html#material-utils",
            keys=(_k("Alt M", "Mesh", "Material menu", "Split menu"),)),

    # ---------------- Industry standard
    Feature("maya_navigation", "Alt Navigation", "INDUSTRY",
            "Alt + left, middle and right mouse to orbit, pan and zoom.",
            "industry-standard.html#alt-navigation",
            keys=(_k("Alt LMB drag", "3D View", "Orbit", "Loop select (Edit Mode)"),
                  _k("Alt MMB drag", "3D View / 2D editors", "Pan"),
                  _k("Alt RMB drag", "3D View / 2D editors", "Zoom")), keys_only=True),
    Feature("maya_pivot", "Maya Pivot", "INDUSTRY",
            "Hold or tap D to edit the pivot in Object and Edit Mode.",
            "industry-standard.html#maya-pivot",
            keys=(_k("D", "Object / Mesh", "Edit pivot", "Annotate"),), keys_only=True),
    Feature("double_click_select_island", "Select Island", "INDUSTRY",
            "Double-click to select a linked island in mesh, UV and curves.",
            "industry-standard.html#select-island",
            keys=(_k("Double-click", "Mesh / UV / Curve", "Select island"),), keys_only=True),
    Feature("toggle_retopology", "Retopology Toggle", "INDUSTRY",
            "Switches overlay, snapping and tool to a retopology setup and back.",
            "industry-standard.html#toggle-retopology",
            keys=(_k("5", "Mesh", "Toggle retopology"),), plus=True),

    # ---------------- UV (Modeling)
    Feature("uv_tools", "UV Tools", "MODELING",
            "Smart UV Sync, UV Cut, unwrap in place, pack helpers and a UV editor panel.",
            "uv.html#uv-tools",
            keys=(_k("RMB", "UV Editor", "Smart UV sync", "Context menu"),
                  _k("X / Shift X", "UV Editor", "UV cut"),
                  _k("Alt 2", "Mesh", "Remove seam"))),

    # ---------------- Game art
    Feature("quick_export", "Quick Export", "GAME_ART",
            "Exports the selection; low/high collections go to a bake folder.",
            "toolkit.html#quick-export",
            keys=(_k("Ctrl E", "3D View", "Quick export", "Edge menu (Edit Mode)"),), keys_only=True),
    Feature("quick_bake_name", "Quick Bake Name", "GAME_ART",
            "Names high and low poly pairs for baking.",
            "toolkit.html#quick-bake-name"),
    Feature("auto_lod", "Auto LOD", "GAME_ART",
            "Generates decimated LOD chains from selected meshes.",
            "toolkit.html#auto-lod"),
    Feature("cad_decimate", "CAD Decimate", "GAME_ART",
            "Decimates meshes with millions of triangles.",
            "toolkit.html#cad-decimate"),
    Feature("polycount_list", "Polycount List", "GAME_ART",
            "Every object with its poly count and modifier evaluation time.",
            "toolkit.html#polycount-list"),

    # ---------------- Interface
    Feature("viewport_menu", "Viewport Menu", "INTERFACE",
            "Overlay menu with quick toggles and silhouette mode.",
            "extras.html#viewport-menu",
            keys=(_k("Alt V", "3D View", "Viewport menu", "Rip fill (Edit Mode)"),), keys_only=True),
    Feature("outliner_options", "Outliner Options", "INTERFACE",
            "Auto-focus and extra click behaviour in the Outliner.",
            "extras.html#outliner-options",
            keys=(_k("LMB / RMB click", "Outliner", "Outliner click", "Outliner select"),
                  _k("A / Alt A", "Outliner", "Select all / none")), keys_only=True),
    Feature("w_context_menu", "W Context Menu", "INTERFACE",
            "Opens the right-click context menu on W, as in Blender 2.7x.",
            "extras.html#legacy-shortcuts",
            keys=(_k("W", "Object / Mesh / Curve", "Context menu", "Select tool cycle"),), keys_only=True, optional=True),
    Feature("legacy_shortcuts", "Legacy Shortcuts", "INTERFACE",
            "Shortcuts from Blender 2.7x: Alt P poke, < > grow and shrink, UV Ctrl A/P/C/V.",
            "extras.html#legacy-shortcuts",
            keys=(_k("Alt P", "Mesh", "Poke faces"),
                  _k("< / Shift <", "Mesh / UV", "Select more / less"),
                  _k("Ctrl A / P / C / V", "UV Editor", "Average scale / pack / copy / paste UVs")), keys_only=True),
)

FEATURE_BY_ID = {f.id: f for f in FEATURES}

# Settings that look like features (enable_*) but belong to another feature
SUB_SETTINGS = {"legacy_collection_shortcuts"}

# Features that change something in Blender itself while they are on. Each function takes on=True/False.
SET_ENABLED = {
    "auto_delete": auto_delete.set_enabled,              # applies the Object Mode X confirm setting
    "maya_navigation": maya_navigation.set_enabled,      # optional tablet and sculpt keys
    "legacy_shortcuts": legacy_shortcuts.set_enabled,    # optional collection number keys
    "outliner_options": outliner_options.set_enabled,    # selection timer
    "polycount_list": poly_count_list.set_enabled,       # depsgraph handler that keeps the list current
    "uv_tools": uv_tools.set_enabled,                    # Seam by Angle in the UV Unwrap menu
    "merge_tool": merge_tool.set_enabled,                # toolbar tools
    "cutter_tool": cutter_tool.set_enabled,
    "fast_loop_cut": fast_loop_cut.set_enabled,
    "push_pull": smart_extrude.set_enabled,
}

# The shortcuts each feature adds: the lists its module keeps of the keymap items it registered
FEATURE_KEYMAPS = {
    "fast_loop_cut": (fast_loop_cut.registered_fast_loop_cut_keymaps,),
    "fast_merge": (fast_merge.registered_fast_merge_keymaps,),
    "auto_delete": (auto_delete.registered_auto_delete_keymaps,),
    "toolkit_panel": (toolkit_panel.registered_toolkit_panel_keymaps, snap_to_floor.registered_snap_to_floor_keymaps),
    "modi_key": (modi_key.registered_modi_key_keymaps,),
    "material_index": (material_index.registered_material_index_keymaps,),
    "maya_navigation": (maya_navigation.registered_maya_navigation_keymaps,),
    "maya_pivot": (maya_pivot.registered_maya_pivot_keymaps,),
    "double_click_select_island": (double_click_select_island.registered_double_click_select_island_keymaps,),
    "toggle_retopology": (toggle_retopology.registered_toggle_retopology_keymaps,),
    "uv_tools": (uv_tools.registered_uv_tools_keymaps,),
    "quick_export": (quick_export.registered_quick_export_keymaps,),
    "viewport_menu": (viewport_menu.registered_viewport_menu_keymaps,),
    "w_context_menu": (optional_keys.registered_w_context_menu_keymaps,),
    "legacy_shortcuts": (legacy_shortcuts.registered_legacy_shortcuts_keymaps,
                         legacy_shortcuts.registered_legacy_collection_shortcuts_keymaps),
}

_switched_on = set() # features whose set_enabled(True) has run
_suspend = 0         # >0 while presets/migration write props, so update callbacks stay quiet


def prefs():
    from .utils.pref_utils import get_keyops_prefs
    return get_keyops_prefs()


def visible_features(p=None):
    p = p or prefs()
    return [f for f in FEATURES if f.available() and not f.experimental]


# ---------------------------------------------------------------- shortcuts

def tracked_items(feature_id):
    """(KeyMap, KeyMapItem) pairs of the shortcuts a feature registered."""
    return [pair for keymaps in FEATURE_KEYMAPS.get(feature_id, ()) for pair in keymaps]


def is_enabled(feature_id, p=None):
    """Whether a feature is on. Before the preferences exist, it's on if the Essentials
    preset has it (tools, panels and menus), so those never wait for the preferences."""
    f = FEATURE_BY_ID[feature_id]
    p = p or prefs()
    if p is None:
        return style_values("ESSENTIALS", f)[0] and f.available()
    return getattr(p, f"enable_{feature_id}") and f.available()


def keys_active(feature_id, p=None):
    """Whether a feature's shortcuts are on. Never before the preferences exist."""
    p = p or prefs()
    if p is None:
        return False
    return is_enabled(feature_id, p) and getattr(p, f"keys_{feature_id}", False) and not p.pause_shortcuts


def apply_key_state(feature_id, p=None):
    on = keys_active(feature_id, p)
    for _km, kmi in tracked_items(feature_id):
        kmi.active = on


def apply_all_key_states():
    p = prefs()
    for fid in FEATURE_KEYMAPS:
        apply_key_state(fid, p)


# ---------------------------------------------------------------- switching features on and off

def switch(feature_id, on):
    """Turn a feature on or off: its shortcuts, plus its set_enabled() changes if it has any."""
    on = on and FEATURE_BY_ID[feature_id].available()
    set_enabled = SET_ENABLED.get(feature_id)
    if set_enabled is not None and on != (feature_id in _switched_on):
        set_enabled(on)
        if on:
            _switched_on.add(feature_id)
        else:
            _switched_on.discard(feature_id)
    apply_key_state(feature_id)


def apply_all():
    """Make every feature match its switch in the preferences."""
    p = prefs()
    for f in FEATURES:
        switch(f.id, is_enabled(f.id, p))


def switch_all_off():
    """Undo every set_enabled() change, when the add-on is disabled."""
    for feature_id in list(_switched_on):
        switch(feature_id, False)


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
    apply_all()
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
    switch(feature_id, on)


def on_keys_changed(feature_id):
    if is_suspended():
        return
    p = prefs()
    f = FEATURE_BY_ID[feature_id]
    if getattr(p, f"keys_{feature_id}") and f.keys_only and not getattr(p, f"enable_{feature_id}"):
        with suspended():
            setattr(p, f"enable_{feature_id}", True)  # ticking a keys-only feature's shortcuts turns it on
        switch(feature_id, True)
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
    return sum(1 for fid in FEATURE_KEYMAPS for _km, kmi in tracked_items(fid) if kmi.active)


# ---------------------------------------------------------------- first run / upgrade

def _saved_value(p, name):
    """A raw saved preference value, or None. Blender 5.4 dropped IDProperty access on add-on
    preferences (p.get raises TypeError), and there is nothing saved to carry over then.
    Checked by version first so a debugger that stops on caught exceptions doesn't pause here."""
    if bpy.app.version >= (5, 4, 0):
        return None
    try:
        return p.get(name)
    except TypeError:
        return None


def migrate():
    """Decide between a fresh install (Essentials, welcome) and an upgrade (keep everything)."""
    p = prefs()
    if p.prefs_version >= PREFS_VERSION:
        return
    legacy_names = [f"enable_{f.id}" for f in FEATURES] + [
        "enable_add_objects_pie", "enable_cursor_pie", "enable_workspace_pie",
        "auto_delete_dissolv_edge", "maya_pivot_behavior", "fast_merge_merge_options",
        "add_object_pie_use_relative", "material_list_type", "experimental"]
    changed_settings = any((p.is_property_set(n) if hasattr(p, n) else _saved_value(p, n) is not None) for n in legacy_names)
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
            saved = _saved_value(p, old_switches.get(pie.preset, ""))
            if saved is not None:
                pie["enabled"] = bool(saved)
        pie_menus.sync_keymaps()
    if not upgrading:
        # Quiet until the welcome screen's choice: no shortcuts, no pies
        apply_style("ESSENTIALS")
