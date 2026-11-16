import bpy
import rna_keymap_ui
from bpy.props import IntProperty, BoolProperty, FloatProperty, FloatVectorProperty, StringProperty, EnumProperty
from .utils.pref_utils import get_addon_name, _keymap_item_to_display_item
from .utils.utilities import is_addon_enabled
from .operators.maya_navigation import update_tablet_navigation as _update_tablet_navigation
from .operators.maya_navigation import update_sculpt_navigation as _update_sculpt_navigation
from .operators.auto_delete import update_auto_delete_confirm_delete
from . import features as F
from .ui.feature_settings import draw_settings, SETTINGS

DOCS_URL = F.DOCS_URL


# ---------------------------------------------------------------- update callbacks

def update_tablet_navigation(self, context):
    with F.capture("maya_navigation"):
        _update_tablet_navigation(self, context)


def update_sculpt_navigation(self, context):
    with F.capture("maya_navigation"):
        _update_sculpt_navigation(self, context)


def update_legacy_collection_shortcuts(self, context):
    if F.is_suspended():
        return
    if bpy.app.version < (5, 0, 0) or not self.enable_legacy_shortcuts:
        if self.enable_legacy_collection_shortcuts:
            self.enable_legacy_collection_shortcuts = False
        return
    from .operators.legacy_shortcuts import register_legacy_collection_shortcuts, unregister_legacy_collection_shortcuts
    if self.enable_legacy_collection_shortcuts:
        with F.capture("legacy_shortcuts"):
            register_legacy_collection_shortcuts()
    else:
        unregister_legacy_collection_shortcuts()


def _enable_update(feature_id):
    def update(self, context):
        F.on_enable_changed(feature_id)
    return update


def _keys_update(feature_id):
    def update(self, context):
        F.on_keys_changed(feature_id)
    return update


def _style_update(self, context):
    if F.is_suspended():
        return
    if self.shortcut_style != "CUSTOM":
        F.apply_style(self.shortcut_style)


def _pause_update(self, context):
    F.apply_all_key_states()


_category_cache = {}  # Blender keeps pointers to enum strings, so every list we hand out must stay alive


def _category_enum_items(self, context):
    """Category list with live 'on/total' counts."""
    try:
        visible = F.visible_features(self)
    except Exception:
        visible = F.FEATURES
    counts = []
    for cid, _name, _desc, _icon in F.CATEGORIES:
        feats = [f for f in visible if f.category == cid]
        counts.append((sum(1 for f in feats if getattr(self, f"enable_{f.id}", False)), len(feats)))
    key = tuple(counts)
    if key not in _category_cache:
        _category_cache[key] = [(cid, f"{name}   {on}/{total}", desc, icon, i)
                                for i, ((cid, name, desc, icon), (on, total)) in enumerate(zip(F.CATEGORIES, counts))]
    return _category_cache[key]


def _impact(f):
    if not f.keys:
        return "No shortcuts", 'CHECKMARK'
    if f.replaced:
        extra = f" +{len(f.replaced) - 1}" if len(f.replaced) > 1 else ""
        return f"Replaces {f.replaced[0].replaces}{extra}", 'ERROR'
    n = len(f.keys)
    return f"{n} free shortcut{'s' if n > 1 else ''}", 'EVENT_K'


def _docs(f):
    return f.docs if f.docs.startswith("http") else DOCS_URL + f.docs


def _wrap(text, width):
    words, lines, line = text.split(), [], ""
    for w in words:
        if len(line) + len(w) + 1 > width and line:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        lines.append(line)
    return lines


class KeyOpsPreferences(bpy.types.AddonPreferences):
    bl_idname = get_addon_name()

    # Disable LoopTools menu by default when LoopTools is enabled, to avoid duplicate menu entries.
    looptools_menu_default = not is_addon_enabled("looptools", "mesh_looptools", "bl_ext.blender_org.looptools")
    default_retopology_custom_tool = "builtin.select_box"

    # ---------------- 1.0 state
    ui_tab: EnumProperty(name="Tab", items=[
        ("HOME", "Home", "Shortcut style and status", 'HOME', 0),
        ("FEATURES", "Features", "Turn features on and off, and change their settings", 'PRESET', 1),
        ("SHORTCUTS", "Shortcuts", "Every Key Ops shortcut, grouped by feature", 'KEYINGSET', 2),
        ("PIES", "Pie Menus", "Pie menus and the keys that open them", 'MESH_CIRCLE', 3)]) # type: ignore
    ui_category: EnumProperty(name="Category", items=_category_enum_items) # type: ignore
    ui_search: StringProperty(name="Search", description="Search features by name or description", options={'TEXTEDIT_UPDATE'}) # type: ignore
    ui_filter: EnumProperty(name="Show", items=[
        ("ALL", "All", "Show all features"),
        ("ON", "On", "Only features that are on"),
        ("OFF", "Off", "Only features that are off"),
        ("KEYS", "Uses Keys", "Only features that add shortcuts"),
        ("REPLACES", "Replaces Keys", "Only features that replace a Blender shortcut")]) # type: ignore
    shortcut_style: EnumProperty(name="Shortcut Style", items=[s for s in F.STYLES], default="ESSENTIALS", update=_style_update) # type: ignore
    style_modified: BoolProperty(default=False) # type: ignore
    pause_shortcuts: BoolProperty(name="Pause All Key Ops Shortcuts", default=False, update=_pause_update,
                                  description="Switch every Key Ops shortcut off. Features keep working from menus, panels and F3") # type: ignore
    prefs_version: IntProperty(default=0) # type: ignore
    welcome_version: IntProperty(default=0) # type: ignore
    show_whats_new: BoolProperty(default=False) # type: ignore

    # ---------------- feature switches, generated from the registry
    for _f in F.FEATURES:
        _default = looptools_menu_default if _f.id == "looptools_menu" else (_f.default_on and not _f.optional)
        __annotations__[f"enable_{_f.id}"] = BoolProperty(
            name=_f.name, description=_f.description, default=_default, update=_enable_update(_f.id))
        if _f.keys:
            __annotations__[f"keys_{_f.id}"] = BoolProperty(
                name="Use Shortcuts", description=f"Turn {_f.name} shortcuts on or off", default=False,
                update=_keys_update(_f.id))
    del _f, _default

    enable_legacy_collection_shortcuts: BoolProperty(name="Collection Number Keys", description="Restore object-mode collection hide/unhide shortcuts on numbers 1-0, including Shift and Alt variants. Blender 5.0+ only.", default=False, update=update_legacy_collection_shortcuts) # type: ignore


    #prefs settings variables
    maya_navigation_tablet_navigation: BoolProperty(name="Tablet", description="Makes it easier to use tablet by adding zoom and pan to ctrl alt lmb and shift alt lmb", default=False, update= update_tablet_navigation) # type: ignore 
    maya_navigation_sculpt_navigation: BoolProperty(name="Sculpt", description="Use both Mask and Alt navigation in Sculpt mode, mask is used if mouse is over model, otherwise alt navigation is used.", default=True, update= update_sculpt_navigation) # type: ignore 
    auto_delete_dissolv_edge: BoolProperty(name="Dissolve Edge", default=False, description="Dissolve Edge in Edge Mode ") # type: ignore
    auto_delete_confirm_object_mode: BoolProperty(name="Confirm on X in Object Mode", description="Confirm Delete in Object Mode on the X key", default=False, update= update_auto_delete_confirm_delete) # type: ignore
    toggle_retopology_custom_tool: StringProperty(name="Tool", default=default_retopology_custom_tool) # type: ignore
    toggle_retopology_color_enum: EnumProperty(
        name="Theme",
        items=[
            ("blender_default", "Blender Default", "Choose this option for the blender default color"),
            ("maya", "Maya", "Choose this option for maya color"),
            ("custom_color", "Custom Color", "Choose this option for custom tool")],
        default="maya") # type: ignore
    toggle_retopology_custom_color: FloatVectorProperty(name="", subtype='COLOR', size=4, default=(0.313726, 0.784314, 1.0, 0.058824), min=0.0, max=1.0) # type: ignore
    toggle_retopology_face_alpha: FloatProperty(name="Face Alpha", default=0.301961, min=0.0, max=1.0) # type: ignore
    toggle_retopology_edge_width: IntProperty(name="", default=2, min=1, max=5, description="Edge Width") # type: ignore
    toggle_retopology_snapping_settings_save_string: StringProperty(name="Snap Settings", default="") # type: ignore
    toggle_retopology_snapping_settings_vert: BoolProperty(name="Vert", default=False) # type: ignore
    toggle_retopology_snapping_settings_face: BoolProperty(name="Face", default=True) # type: ignore
    toggle_retopology_snapping_settings_face_project: BoolProperty(name="Face Project", default=False) # type: ignore
    toggle_retopology_snapping_settings_face_nearest: BoolProperty(name="Face Nearest", default=False) # type: ignore

    savede_colors_theme_settings_string: StringProperty(name="Saved Colors", default="") # type: ignore
    savede_colors_theme_settings_string_backup2: StringProperty(name="Saved Colors Backup", default="") # type: ignore
    maya_pivot_behavior: EnumProperty(
        name="Behavior",
        items=[
            ("TOGGLE", "Toggle", "Toggle key to move Pivot"),
            ("HOLD", "Hold", "Hold key to move Pivot")],
        default="HOLD") # type: ignore
    maya_pivot_show_gizmo: BoolProperty(name="Show Gizmo", default=True) # type: ignore
    maya_pivot_in_edit_mode: BoolProperty(name="In Edit Mode", default=True) # type: ignore
    maya_pivot_experimental: BoolProperty(name="Experimental", default=False) # type: ignore
    fast_merge_merge_options: EnumProperty( 
        name="Options",
        items=[
            ("merge to nerest vert if no active", "Merge nearest if no Active and > 1 Vert Selected", "Merge to nearest vert if no active vert and over 1 vert is selected"),
            ("always merge to nearest vert", "Always merge to nearest vert", "Always merge to nearest vert"),
            ("only merge if active or only 1 verts is selected", "Merge nearest if 1 Vert is Selected, Otherwise Active", "(legacy) only merge if active vert or only 1 verts is selected")],
        default="merge to nerest vert if no active") # type: ignore
    fast_merge_soft_limit: EnumProperty(
        name="Limit",
        items=[
            ("max_polycount", "Max Polycount", "Limit the polycount of the mesh"),
            ("all_selected", "All Selected", "Do not merge if all verts are selected"),
            ("max_limit_&_all_selected", "Max Limit & All Selected", "Do not merge if all verts are selected and polycount is above limit"),
            ("ask_if_no_active_vert", "Confirm to Merge if No Active", "Ask if no active vert"),
            ("no_limit", "No Limit", "Merge all selected verts")],
        default="ask_if_no_active_vert") # type: ignore
    fast_merge_polycount: IntProperty(name="Verts", default=1000, min=1, max=1000000) # type: ignore
    add_object_pie_use_relative: BoolProperty(name="Relative Scale", default=True, description="Default Relative Scale Value") # type: ignore
    add_object_pie_relative_scale: FloatProperty(name="Screen Size", default=7.0, min=1.0, max=25.0, description="Default Relative Scale Value") # type: ignore
    add_object_pie_default_scale: FloatProperty(name="Size", default=2.0, min=0.1, max=10.0, unit='LENGTH', description="Default Regular Scale Size Value") # type: ignore
    add_object_pie_min_scale: FloatProperty(name="Min Size", default=0.01, min=0.0001, max=10.0, unit='LENGTH', description="Relative Scale Min Size Value") # type: ignore
    add_object_pie_Enum: EnumProperty(
        name="Top Right Option",
        items=[
            ("OTHER", "Other", "Deafult Add Menu", "ADD", 0),
            ("EMPTY", "Empty", "Empty", "EMPTY_ARROWS", 2),
            ("MONKEY", "Monkey", "Monkey", "MONKEY", 4),
            ("BLEND", ".blend", "Blender File", "BLENDER", 8)],
        default="OTHER") # type: ignore
            # ("CUSTOM", "Custom", "bpy.ops operation", "FILE_SCRIPT", 16)],
    add_object_pie_blend_file_path: StringProperty(name="Path", subtype='FILE_PATH') #type: ignore
    add_object_pie_blend_object_name: StringProperty(name="Object Name: add a , to add many objects; cube,cylinder,sphere etc") #type: ignore
    add_object_pie_bpy_ops: StringProperty(name="Operation") #type: ignore
    uv_tools_panel_name: StringProperty(name="", default="Toolkit") # type: ignore
    # max_layout: BoolProperty(name="Max Layout", default=False, description="Edit mode - Toolkit Panel") # type: ignore
    # material_utilities_panel: BoolProperty(name="Material Index Panel", default=True) # type: ignore
    material_list_icon_scale: FloatProperty(name="Icon Scale", default=2.0, min=0.1, max=10.0) # type: ignore
    material_list_type: EnumProperty(
        name="Type",
        items=[
            ("PREVIEW_ICONS", "Big Preview Icons", "Preview Icons", "IMAGE_DATA", 0),
            ("COMPACT_LIST", "Compact List", "Compact List", "ALIGN_LEFT", 1)],
        default="COMPACT_LIST") # type: ignore  
    material_list_show_icons: BoolProperty(name="Show Icons", default=True) # type: ignore
    experimental: BoolProperty(name="Experimental", default=False, description="Enable Experimental Features") # type: ignore

    # ================================================================ drawing

    def draw(self, context):
        layout = self.layout
        if self.show_whats_new:
            box = layout.box()
            col = box.column()
            col.label(text="Key Ops 1.0: features and shortcuts now have separate switches.", icon='INFO')
            sub = col.column()
            sub.active = False
            sub.label(text="Your setup from 0.2 is kept as it was. Switch to Essentials for tools and panels without shortcuts.")
            row = col.row()
            row.operator("keyops.dismiss_whats_new", text="Keep My Setup").switch = False
            row.operator("keyops.dismiss_whats_new", text="Switch to Essentials").switch = True

        row = layout.row()
        row.scale_y = 1.3
        row.prop(self, "ui_tab", expand=True)
        body = layout.column()
        {"HOME": self.draw_home, "FEATURES": self.draw_features,
         "SHORTCUTS": self.draw_shortcuts, "PIES": self.draw_pies}[self.ui_tab](context, body)

    # ---------------------------------------------------------------- Home
    def draw_home(self, context, layout):
        box = layout.box()
        box.label(text="Shortcut Style")
        grid = box.grid_flow(row_major=True, columns=4, even_columns=True, align=False)
        for sid, name, desc, icon, _i in F.STYLES:
            col = grid.column(align=True)
            r = col.row()
            r.scale_y = 2.0
            r.prop_enum(self, "shortcut_style", sid, text=name, icon=icon)
            d = col.column(align=True)
            d.active = False
            for line in _wrap(desc, 30):
                d.label(text=line)

        feats, keys, repl = F.stats(self)
        name = dict((s[0], s[1]) for s in F.STYLES)[self.shortcut_style]
        if self.shortcut_style != "CUSTOM" and not F.matches_style(self.shortcut_style, self):
            name += " (modified)"
        row = box.row()
        row.label(text=f"Current: {name}", icon='DOT')
        row.label(text=f"{feats} features on")
        row.label(text=f"{keys} shortcuts active")
        sub = row.row()
        sub.alert = repl > 0
        sub.label(text=f"{repl} replace Blender keys", icon='ERROR' if repl else 'CHECKMARK')

        box = layout.box()
        row = box.row()
        row.prop(self, "pause_shortcuts", text="Pause All Key Ops Shortcuts", icon='PAUSE' if not self.pause_shortcuts else 'PLAY', toggle=True)
        sub = row.row()
        sub.active = False
        sub.label(text="Features keep working. Try this first when a key stops doing what you expect.")

        box = layout.box()
        box.label(text="Get Started")
        row = box.row()
        row.operator("keyops.welcome", text="Show Welcome Again", icon='HEART')
        row.operator("wm.url_open", text="Documentation", icon='HELP').url = DOCS_URL
        row.operator("keyops.shortcut_cheatsheet", text="Active Shortcuts", icon='KEYINGSET')

        box = layout.box()
        box.label(text="Blender Settings We Recommend")
        col = box.column(align=True)
        col.active = False
        col.label(text="Pie menus open instantly with Interface > Editors > Pie Menus > Animation Timeout set to 0.")
        col.label(text="Key Ops never changes your Blender preferences or keymap for you.")

    # ---------------------------------------------------------------- Features
    def _feature_matches(self, f):
        q = self.ui_search.strip().lower()
        if q and q not in f"{f.name} {f.description}".lower():
            return False
        if not q and f.category != self.ui_category:
            return False
        on = getattr(self, f"enable_{f.id}")
        flt = self.ui_filter
        if flt == "ON" and not on:
            return False
        if flt == "OFF" and on:
            return False
        if flt == "KEYS" and not f.keys:
            return False
        if flt == "REPLACES" and not f.replaced:
            return False
        return True

    def draw_features(self, context, layout):
        split = layout.split(factor=0.24)
        left = split.column()
        col = left.column(align=True)
        col.scale_y = 1.35
        col.prop(self, "ui_category", expand=True)
        left.separator()
        left.prop(self, "experimental", text="Show Experimental", icon='EXPERIMENTAL', toggle=True)

        right = split.column()
        row = right.row(align=True)
        row.prop(self, "ui_search", text="", icon='VIEWZOOM', placeholder="Search all features") if bpy.app.version >= (4, 1, 0) else row.prop(self, "ui_search", text="", icon='VIEWZOOM')
        row = right.row(align=True)
        row.prop(self, "ui_filter", expand=True)
        right.separator(factor=0.5)

        shown = [f for f in F.visible_features(self) if self._feature_matches(f)]
        if not shown:
            box = right.box()
            box.label(text="No features match. Clear the search or the filter.", icon='INFO')
        for f in shown:
            self.draw_card(context, right, f)

    def draw_card(self, context, layout, f):
        wm = context.window_manager
        enabled = getattr(self, f"enable_{f.id}")
        is_open = getattr(wm, "keyops_open_feature", "") == f.id

        box = layout.box()
        col = box.column(align=True)
        row = col.row(align=True)
        row.prop(self, f"enable_{f.id}", text="")
        sp = row.split(factor=0.5)
        name = sp.row()
        name.active = enabled
        name.label(text=f.name + ("   (experimental)" if f.experimental else ""))
        right = sp.row(align=True)
        right.alignment = 'RIGHT'
        text, icon = _impact(f)
        badge = right.row()
        badge.active = enabled
        badge.alert = bool(f.replaced) and enabled and getattr(self, f"keys_{f.id}", False)
        badge.label(text=text, icon=icon)
        right.operator("wm.url_open", text="", icon='HELP', emboss=False).url = _docs(f)
        right.operator("keyops.toggle_feature_card", text="", icon='DOWNARROW_HLT' if is_open else 'RIGHTARROW',
                       emboss=False).feature_id = f.id

        d = col.row()
        d.active = False
        d.separator(factor=2.6)
        d.label(text=f.description)
        if f.requires and not getattr(self, f"enable_{f.requires}"):
            r = col.row()
            r.separator(factor=2.6)
            r.label(text=f"Needs {F.FEATURE_BY_ID[f.requires].name} to be on.", icon='LINKED')

        if not is_open:
            return
        inner = box.column()
        inner.separator(type='LINE') if bpy.app.version >= (4, 2, 0) else inner.separator()
        if f.keys:
            r = inner.row()
            r.prop(self, f"keys_{f.id}", text="Use Shortcuts")
            if not getattr(self, f"keys_{f.id}"):
                s = r.row()
                s.active = False
                s.label(text="Off. Run it from the N-panel, menus or F3 search.")
            keys_col = inner.column(align=True)
            keys_col.active = getattr(self, f"keys_{f.id}") and enabled
            for k in f.keys:
                ks = keys_col.split(factor=0.28)
                ks.label(text=k.key, icon='EVENT_K')
                ks2 = ks.split(factor=0.6)
                ks2.label(text=f"{k.action}  ·  {k.editor}")
                ks2.label(text=f"Replaces {k.replaces}" if k.replaces else "Free key",
                          icon='ERROR' if k.replaces else 'CHECKMARK')
            sub = inner.row()
            sub.active = False
            sub.label(text="Rebind these in the Shortcuts tab.")
        else:
            sub = inner.row()
            sub.active = False
            sub.label(text="This feature adds tools, panels or menu entries. It has no shortcuts.")
        sbox = inner.column()
        if f.id in SETTINGS:
            sbox.separator()
            sbox.label(text="Settings", icon='PREFERENCES')
            draw_settings(f.id, self, sbox.box().column())

    # ---------------------------------------------------------------- Shortcuts
    def draw_shortcuts(self, context, layout):
        box = layout.box()
        row = box.row()
        sub = row.column(align=True)
        sub.active = False
        sub.label(text="Key Ops adds shortcuts on top of yours. Turning one off gives Blender's back.")
        sub.label(text="Click a key to rebind it. Changes are saved in your keymap like any other shortcut.")
        row.prop(self, "pause_shortcuts", text="Pause All", icon='PAUSE', toggle=True)
        layout.prop(self, "ui_search", text="", icon='VIEWZOOM')

        kc = context.window_manager.keyconfigs.user
        q = self.ui_search.strip().lower()
        drawn = False
        for f in F.visible_features(self):
            if not f.keys or not getattr(self, f"enable_{f.id}"):
                continue
            items = F.tracked_items(f.id)
            if q and q not in f.name.lower() and not any(q in (kmi.name or "").lower() or q in kmi.type.lower() for _km, kmi in items):
                continue
            drawn = True
            box = layout.box()
            head = box.row()
            head.label(text=f.name, icon='ERROR' if f.replaced else 'EVENT_K')
            head.prop(self, f"keys_{f.id}", text="On")
            col = box.column()
            col.active = F.keys_active(f.id, self)
            for km, kmi in items:
                ukm = kc.keymaps.get(km.name)
                ukmi = _find_user_item(ukm, kmi) if ukm else None
                if ukmi:
                    rna_keymap_ui.draw_kmi(["ADDON", "USER", "DEFAULT"], kc, ukm, ukmi, col, 0)
            if not items:
                col.label(text="No shortcuts registered yet.")
        if not drawn:
            layout.label(text="No features with shortcuts are on. Turn some on in Features, or pick a style on Home.", icon='INFO')

    # ---------------------------------------------------------------- Pies
    def draw_pies(self, context, layout):
        box = layout.box()
        col = box.column(align=True)
        col.active = False
        col.label(text="Pie menus open with a key, so each one adds a shortcut. Options marked 'on Shift A' or 'on Space'")
        col.label(text="replace a Blender key with Key Ops' own shortcut. Your keymap itself is never edited.")
        for f in F.visible_features(self):
            if f.category == "PIES":
                self.draw_card(context, layout, f)


def _find_user_item(ukm, kmi):
    """The user-keymap copy of one of our addon items (what rna_keymap_ui edits)."""
    want = _keymap_item_to_display_item(None, kmi).get("properties", [])
    candidates = [item for item in ukm.keymap_items
                  if item.idname == kmi.idname and all(getattr(item.properties, n, None) == v for n, v in want)]
    sig = (kmi.type, kmi.value, kmi.ctrl, kmi.shift, kmi.alt)
    for item in candidates:
        if (item.type, item.value, item.ctrl, item.shift, item.alt) == sig:
            return item
    return candidates[0] if candidates else None
