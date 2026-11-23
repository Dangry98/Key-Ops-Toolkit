import bpy
from . import marking_menu as MM
from bpy.props import CollectionProperty, IntProperty, BoolProperty, FloatProperty, FloatVectorProperty, StringProperty, EnumProperty
from .utils.pref_utils import get_addon_name, _keymap_item_to_display_item, get_icon
from .operators import maya_navigation
from .operators.auto_delete import update_auto_delete_confirm_delete
from . import features as F
from . import pie_menus
from .ui.feature_settings import draw_settings, SETTINGS

DOCS_URL = F.DOCS_URL


# ---------------------------------------------------------------- update callbacks

def update_maya_navigation_extras(self, context):
    """Tablet and sculpt navigation keys, while Alt Navigation is on."""
    maya_navigation.set_enabled(F.is_enabled("maya_navigation", self))


def update_legacy_collection_shortcuts(self, context):
    if F.is_suspended():
        return
    if bpy.app.version < (5, 0, 0):
        if self.enable_legacy_collection_shortcuts:
            self.enable_legacy_collection_shortcuts = False
        return
    from .operators import legacy_shortcuts
    legacy_shortcuts.set_enabled(F.is_enabled("legacy_shortcuts", self))
    F.apply_key_state("legacy_shortcuts", self)


def _enable_update(feature_id):
    def update(self, context):
        F.on_enable_changed(feature_id)
    return update


def _keys_update(feature_id):
    def update(self, context):
        F.on_keys_changed(feature_id)
    return update


def _pause_update(self, context):
    F.apply_all_key_states()
    pie_menus.sync_keymaps()


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
        _category_cache[key] = [(cid, f"{name}   {on}/{total}", desc + "\nShift-click to show several categories", 1 << i)
                                for i, ((cid, name, desc, icon), (on, total)) in enumerate(zip(F.CATEGORIES, counts))]
    return _category_cache[key]


_view_cache = {}


def _category_view_items(self, context):
    """The category list as drawn: All first, then each category. All is its own bit after the categories."""
    cats = _category_enum_items(self, context)
    try:
        visible = F.visible_features(self)
    except Exception:
        visible = F.FEATURES
    on = sum(1 for f in visible if getattr(self, f"enable_{f.id}", False))
    key = (on, len(visible), id(cats))
    if key not in _view_cache:
        _view_cache[key] = [("ALL", f"All   {on}/{len(visible)}", "Show every feature", 1 << len(F.CATEGORIES))] + list(cats)
    return _view_cache[key]


def _category_view_get(self):
    picked = set(self.ui_category)
    if not picked:
        return 1 << len(F.CATEGORIES)
    return sum(1 << i for i, c in enumerate(F.CATEGORIES) if c[0] in picked)


def _category_view_set(self, value):
    all_bit = 1 << len(F.CATEGORIES)
    was_all = not self.ui_category
    if value & all_bit and not was_all or value == all_bit or not value:
        self.ui_category = set()  # All clicked: show everything
        return
    self.ui_category = {c[0] for i, c in enumerate(F.CATEGORIES) if value & (1 << i)}


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

    # The LoopTools menu only exists from Blender 5.3, where these tools are built in
    looptools_menu_default = bpy.app.version >= (5, 3, 0)
    default_retopology_custom_tool = "builtin.select_box"

    # ---------------- 1.0 state
    ui_tab: EnumProperty(name="Tab", items=[
        ("FEATURES", "Features", "Turn features on and off, and change their settings"),
        ("PIES", "Custom Menus", "Pie menus, popup menus, dialogs, panels and special keys: see what each does, change it or make your own"),
        ("SHORTCUTS", "Shortcuts", "Every Key Ops shortcut, grouped by feature")]) # type: ignore
    ui_category: EnumProperty(name="Category", items=_category_enum_items, options={'ENUM_FLAG'}) # type: ignore
    ui_category_view: EnumProperty(name="Category", items=_category_view_items, options={'ENUM_FLAG'},
                                   get=_category_view_get, set=_category_view_set,
                                   description="Click a category to show it, shift-click to show several") # type: ignore
    ui_search: StringProperty(name="Search", description="Search features by name or description", options={'TEXTEDIT_UPDATE'}) # type: ignore
    ui_filter: EnumProperty(name="Show", items=[
        ("ALL", "All", "Show all features"),
        ("ON", "On", "Only features that are on"),
        ("OFF", "Off", "Only features that are off"),
        ("KEYS", "Uses Keys", "Only features that add shortcuts"),
        ("REPLACES", "Replaces Keys", "Only features that replace a Blender shortcut")]) # type: ignore
    shortcut_style: EnumProperty(name="Keyboard Preset", items=[s for s in F.STYLES], default="ESSENTIALS",
                                 description="Which shortcuts to start with. Applied once from the welcome screen") # type: ignore
    pies: CollectionProperty(type=pie_menus.KeyOpsPie) # type: ignore
    active_pie: IntProperty(default=0) # type: ignore
    pies_installed: BoolProperty(default=False) # type: ignore
    pie_slot: IntProperty(default=0) # type: ignore
    pie_show_more: BoolProperty(name="More Options", default=False) # type: ignore
    pie_show_settings: BoolProperty(name="Pie Settings", default=False) # type: ignore
    pie_show_values: BoolProperty(name="My Properties", default=False) # type: ignore
    pie_style: EnumProperty(name="Pie Style", default="BLENDER", items=(
        ("BLENDER", "Blender", "Blender's own pie menus: point at a button, release or click to pick it"),
        ("MARKING", "Marking", "Marking menus: flick in a direction and release, even before the menu shows. "
                               "Items that open another menu open it right there, so you can keep flicking"))) # type: ignore
    # ---- marking menu look (Pie Style: Marking). Defaults are the Key Ops look; every part can be changed.
    marking_item_color: FloatVectorProperty(name="Item", subtype='COLOR_GAMMA', size=4, min=0.0, max=1.0,
                                            default=MM.MARK_ITEM) # type: ignore
    marking_border_color: FloatVectorProperty(name="Border", subtype='COLOR_GAMMA', size=4, min=0.0, max=1.0,
                                              default=MM.MARK_BORDER) # type: ignore
    marking_text_color: FloatVectorProperty(name="Text", subtype='COLOR_GAMMA', size=4, min=0.0, max=1.0,
                                            default=MM.MARK_TEXT) # type: ignore
    marking_highlight_color: FloatVectorProperty(name="Highlight", subtype='COLOR_GAMMA', size=4, min=0.0, max=1.0,
                                                 default=MM.MARK_HIGHLIGHT) # type: ignore
    marking_highlight_text_color: FloatVectorProperty(name="Highlight Text", subtype='COLOR_GAMMA', size=4, min=0.0, max=1.0,
                                                      default=MM.MARK_TEXT_HIGHLIGHT) # type: ignore
    marking_line_color: FloatVectorProperty(name="Line", subtype='COLOR_GAMMA', size=4, min=0.0, max=1.0,
                                            default=MM.MARK_LINE) # type: ignore
    marking_center_color: FloatVectorProperty(name="Centre", subtype='COLOR_GAMMA', size=4, min=0.0, max=1.0,
                                              default=MM.MARK_RING) # type: ignore
    marking_use_theme: BoolProperty(name="Use Blender Theme Colors", default=True,
                                    description="Take colours and corner rounding from your Blender theme's pie menus") # type: ignore
    marking_antialias: BoolProperty(name="Anti-aliasing", default=True,
                                    description="Smooth lines and box edges. Off draws them crisp, pixel by pixel") # type: ignore
    marking_shadow: BoolProperty(name="Shadows", default=True, description="Soft shadows under the items, like Blender's menus") # type: ignore
    marking_center: EnumProperty(name="Centre", default="RING", items=(
        ("RING", "Ring", "A hollow ring where the key was pressed"),
        ("DOT", "Dot", "A filled dot with the border colour around it"))) # type: ignore
    marking_text_align: EnumProperty(name="Text", default="LEFT", items=(
        ("LEFT", "Left", "Labels start at the left of their box"),
        ("CENTER", "Centre", "Labels are centred in their box"))) # type: ignore
    marking_line_width: FloatProperty(name="Line Width", default=MM.MARK_LINE_WIDTH, min=0.0, max=10.0, subtype='PIXEL',
                                      description="Width of the line from the centre to the mouse. 0 hides it") # type: ignore
    marking_box_height: IntProperty(name="Box Height", default=MM.MARK_BOX_H, min=10, max=80, subtype='PIXEL') # type: ignore
    marking_padding: IntProperty(name="Padding", default=MM.MARK_PAD, min=0, max=80, subtype='PIXEL',
                                 description="Space each side of a label") # type: ignore
    marking_font_size: FloatProperty(name="Font Size", default=MM.MARK_FONT, min=6.0, max=40.0, step=50) # type: ignore
    marking_corner: IntProperty(name="Corners", default=MM.MARK_CORNER, min=0, max=30, subtype='PIXEL',
                                description="How round the corners are. 0 is square") # type: ignore
    marking_side: IntProperty(name="Sides", default=MM.MARK_SIDE, min=0, max=500, subtype='PIXEL',
                              description="Left and right items: distance from the centre to their inner edge") # type: ignore
    marking_diag_x: IntProperty(name="Corners Out", default=MM.MARK_DIAG_X, min=0, max=500, subtype='PIXEL',
                                description="Corner items: distance from the centre to their inner edge") # type: ignore
    marking_diag_y: IntProperty(name="Corners Up", default=MM.MARK_DIAG_Y, min=0, max=500, subtype='PIXEL',
                                description="Corner items: how far above or below the centre they sit") # type: ignore
    marking_top: IntProperty(name="Top & Bottom", default=MM.MARK_TOP, min=0, max=500, subtype='PIXEL',
                             description="Top and bottom items: how far above or below the centre they sit") # type: ignore
    marking_delay: FloatProperty(name="Show After", default=MM.SHOW_DELAY, min=0.0, max=1.0, subtype='TIME_ABSOLUTE',
                                 unit='TIME_ABSOLUTE', description="How long to hold still before the menu shows. "
                                 "A faster flick picks without showing it") # type: ignore
    pie_show_marking: BoolProperty(name="Marking Menu Look", default=False) # type: ignore
    pie_customize: BoolProperty(name="Type", default=True,
                                description="What the selected item is and runs: its type, command, Python, macro steps and when it shows") # type: ignore
    pie_show_op_params: BoolProperty(name="Operator Parameters", default=True,
                                     description="Settings Key Ops keeps for the selected item's operator") # type: ignore
    pie_show_drawing: BoolProperty(name="Drawing", default=False,
                                   description="How the selected item is drawn: emboss, alert, active, depress and its size") # type: ignore
    pause_shortcuts: BoolProperty(name="Pause All Key Ops Shortcuts", default=False, update=_pause_update,
                                  description="Switch every Key Ops shortcut off. Features keep working from menus, panels and F3") # type: ignore
    prefs_version: IntProperty(default=0) # type: ignore
    welcome_version: IntProperty(default=0) # type: ignore
    show_whats_new: BoolProperty(default=False) # type: ignore
    last_seen_version: StringProperty(default="") # type: ignore

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
    maya_navigation_tablet_navigation: BoolProperty(name="Tablet", description="Makes it easier to use tablet by adding zoom and pan to ctrl alt lmb and shift alt lmb", default=False, update=update_maya_navigation_extras) # type: ignore 
    maya_navigation_sculpt_navigation: BoolProperty(name="Sculpt", description="Use both Mask and Alt navigation in Sculpt mode, mask is used if mouse is over model, otherwise alt navigation is used.", default=True, update=update_maya_navigation_extras) # type: ignore 
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
    maya_pivot_experimental: BoolProperty(name="Edit Mode Pivot", default=False, description="Also edit the pivot with D in Edit Mode") # type: ignore
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
    edit_toolkit_show_blender_ops: BoolProperty(
        name="Include Blender Operators",
        default=True,
        description=("Edit Toolkit: also show Blender's built-in mesh operators (Loop, Ring, Bevel, Bridge, Extrude, Weld, "
                     "Subdivide and more) next to the Key Ops tools, for an all-in-one, 3ds Max-style panel. "
                     "Turn off to only show Key Ops operators")) # type: ignore
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
        from .ui import branding
        branding.draw_header(layout)
        if self.show_whats_new:
            box = layout.box()
            row = box.row()
            col = row.column(align=True)
            col.label(text="Key Ops 1.0: every feature and its shortcuts can now be turned on and off separately.")
            sub = col.row()
            sub.active = False
            sub.label(text="Your setup from 0.2 is kept. Menus are now editable in the Custom Menus tab.")
            row.operator("keyops.dismiss_whats_new", text="Got It")

        row = layout.row()
        row.scale_y = 1.3
        row.prop(self, "ui_tab", expand=True)
        body = layout.column()
        {"FEATURES": self.draw_features, "SHORTCUTS": self.draw_shortcuts,
         "PIES": self.draw_pies}[self.ui_tab](context, body)

    # ---------------------------------------------------------------- Features
    def _categories(self):
        """The categories picked on the left (shift-click picks several); all of them when none is."""
        picked = set(self.ui_category)
        return picked or {c[0] for c in F.CATEGORIES}

    def _feature_matches(self, f, every_category=False):
        q = self.ui_search.strip().lower()
        if q and q not in f"{f.name} {f.description}".lower():
            return False
        if not q and not every_category and f.category not in self._categories():
            return False
        return True

    def draw_features(self, context, layout):
        # a small Preferences window: no category list beside the features (it would cut their
        # descriptions short), every feature under its category heading instead
        width = (context.region.width if context.region else 1600) / max(0.5, context.preferences.system.ui_scale)
        narrow = width < 820
        if narrow:
            right = layout.column()
        else:
            split = layout.split(factor=0.22)
            left = split.column()
            col = left.column(align=True)
            col.scale_y = 1.35
            col.prop(self, "ui_category_view", expand=True)  # All and the categories, text on the left
            right = split.column()
        row = right.row(align=True)
        if bpy.app.version >= (4, 1, 0):
            row.prop(self, "ui_search", text="", icon='VIEWZOOM', placeholder="Search all features")
        else:
            row.prop(self, "ui_search", text="", icon='VIEWZOOM')
        right.separator(factor=0.5)

        order = {c[0]: i for i, c in enumerate(F.CATEGORIES)}
        shown = sorted((f for f in F.visible_features(self) if self._feature_matches(f, narrow)),
                       key=lambda f: order.get(f.category, 99))  # stable: keeps the order within a category
        if not shown:
            right.box().label(text="No features match your search.")
        headings = len({f.category for f in shown}) > 1  # several categories: a heading above each
        names = {c[0]: c[1] for c in F.CATEGORIES}
        last = None
        for f in shown:
            if headings and f.category != last:
                if last is not None:
                    right.separator()
                h = right.row()
                h.active = False
                h.label(text=names.get(f.category, f.category))
                last = f.category
            self.draw_card(context, right, f)

    def draw_card(self, context, layout, f):
        wm = context.window_manager
        enabled = getattr(self, f"enable_{f.id}")
        is_open = getattr(wm, "keyops_open_feature", "") == f.id
        keys_on = bool(getattr(self, f"keys_{f.id}", False))

        box = layout.box()
        col = box.column(align=True)
        row = col.row(align=True)
        row.operator("keyops.toggle_feature_card", text="", icon='DOWNARROW_HLT' if is_open else 'RIGHTARROW',
                     emboss=False).feature_id = f.id
        row.prop(self, f"enable_{f.id}", text="")
        sp = row.split(factor=0.45)
        name = sp.row()
        name.active = enabled
        label = f.name + ("   (experimental)" if f.experimental else "")
        if f.category == "TOOLS":
            # the toolbar icon, so people know what to look for in the toolbar
            name.label(text=label, icon_value=get_icon(f"tool_{f.id}"))
        else:
            name.label(text=label)
        right = sp.row(align=True)
        right.alignment = 'RIGHT'
        # kept clean at first glance: shortcuts are shown and switched when the card is opened
        right.operator("wm.url_open", text="", icon='HELP', emboss=False).url = _docs(f)

        d = col.row(align=True)
        d.separator(factor=3.6)  # under the name, past the arrow and checkbox
        link = d.row(align=True)
        link.alignment = 'LEFT'
        link.active = False
        link.operator("wm.url_open", text=f.description, emboss=False).url = _docs(f)  # click to read the docs
        if f.requires and not getattr(self, f"enable_{f.requires}"):
            r = col.row()
            r.separator(factor=4.2)
            r.label(text=f"Needs {F.FEATURE_BY_ID[f.requires].name} to be on.")

        if not is_open:
            return
        inner = box.column()
        inner.separator()
        if f.keys:
            head = inner.row()
            head.active = enabled
            head.prop(self, f"keys_{f.id}", text="Use Shortcuts")
            keys_col = inner.column(align=True)
            keys_col.active = keys_on and enabled
            for k in f.keys:
                ks = keys_col.split(factor=0.25)
                ks.label(text=k.key)
                ks2 = ks.split(factor=0.6)
                ks2.label(text=f"{k.action}  ·  {k.editor}")
                ks2.label(text=f"Replaces {k.replaces}" if k.replaces else "Free key")
            sub = inner.row()
            sub.active = False
            sub.label(text="Rebind them in the Shortcuts tab.")
        if f.id in SETTINGS:
            inner.separator()
            inner.label(text="Settings")
            draw_settings(f.id, self, inner.box().column())
        elif not f.keys:
            sub = inner.row()
            sub.active = False
            sub.label(text="This feature adds tools, panels or menu entries. It has no settings.")

    # ---------------------------------------------------------------- Shortcuts
    def draw_shortcuts(self, context, layout):
        box = layout.box()
        row = box.row()
        sub = row.column(align=True)
        sub.active = False
        sub.label(text="Key Ops adds shortcuts on top of yours. Turning one off gives Blender's back.")
        sub.label(text="Click a key to rebind it. Menu keys are set in the Custom Menus tab.")
        row.prop(self, "pause_shortcuts", text="Pause All Shortcuts", toggle=True, icon='PAUSE')
        layout.prop(self, "ui_search", text="", icon='VIEWZOOM')

        kc = context.window_manager.keyconfigs.user
        q = self.ui_search.strip().lower()
        groups = []
        for f in F.visible_features(self):
            if not f.keys or not getattr(self, f"enable_{f.id}") or f.id in NOT_IN_SHORTCUTS:
                continue
            # A search that matches the feature name shows all its keys; otherwise only the matching keys.
            whole = not q or q in f.name.lower()
            rows = []
            for km, kmi in F.tracked_items(f.id):
                ukm = kc.keymaps.get(km.name)
                ukmi = _find_user_item(ukm, kmi) if ukm else None
                if not ukmi:
                    continue
                if not whole and q not in shortcut_name(ukmi).lower() and q not in ukmi.type.lower():
                    continue
                rows.append((ukm, ukmi))
            if not whole and not rows:
                continue
            groups.append((f, rows))
        if not groups:
            layout.label(text="No shortcuts match your search." if q else
                         "No features with shortcuts are on. Turn some on in the Features tab.")
            return

        # two columns, filled top to bottom: the left one first, about half the rows in each
        total = sum(1 + len(r) for _f, r in groups)
        split = layout.split(factor=0.5)
        cols = (split.column(), split.column())
        filled = 0
        for f, rows in groups:
            col = cols[0] if filled < total / 2 else cols[1]
            filled += 1 + len(rows)
            box = col.box()
            head = box.row()
            head.prop(self, f"keys_{f.id}", text="")  # on/off first, before the name
            head.label(text=f.name)
            body = box.column(align=True)
            body.active = F.keys_active(f.id, self)
            for group in group_key_rows(rows):
                _draw_key_row(body, group)

    # ---------------------------------------------------------------- Pies
    def draw_pies(self, context, layout):
        pie_menus.draw_pies_tab(self, context, layout)


# Features whose keys are part of how they work (not shortcuts to rebind): switched on and off in Features only
NOT_IN_SHORTCUTS = {"double_click_select_island", "maya_navigation", "auto_delete"}

key_capture = {"items": ""}  # the shortcut row waiting for a key press


def shortcut_name(kmi):
    """A shortcut's name as a person reads it: the operator's name without the "KeyOps:" prefix, plus
    what this key does when one operator does several things ("Modi Key · Apply")."""
    name = (kmi.name or kmi.idname).strip()
    for prefix in ("KeyOps: ", "KeyOps:", "Key Ops: "):
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
    props = kmi.properties
    kind = getattr(props, "type", None) if props is not None else None
    if isinstance(kind, str) and kind and kind.upper() != kind.lower():
        name += "  \u00b7  " + kind.replace("_", " ").strip().title()
    return name


def _key_signature(kmi):
    # by name, not operator: "Pan View" is view3d.move in the 3D View and view2d.pan in 2D editors
    return (kmi.name or kmi.idname, kmi.type, kmi.ctrl, kmi.shift, kmi.alt, kmi.oskey, kmi.any, kmi.key_modifier)


def group_key_rows(rows):
    """Shortcuts that do the same thing on the same key are one row, even when they sit in several keymaps
    or fire on both press and release (Maya Pivot is four keymap items: D in Object and Edit Mode, press and
    release). [(km, kmi), ...] -> [[(km, kmi), ...], ...] in first-seen order."""
    groups = {}
    for km, kmi in rows:
        groups.setdefault(_key_signature(kmi), []).append((km, kmi))
    return list(groups.values())


def encode_key_group(group):
    return ";".join(f"{km.name}|{kmi.id}" for km, kmi in group)


def key_text(kmi):
    text = kmi.to_string()
    if kmi.value == 'CLICK_DRAG':
        mods = [m for m, on in (("Ctrl", kmi.ctrl), ("Shift", kmi.shift), ("Alt", kmi.alt), ("Cmd", kmi.oskey)) if on]
        name = kmi.bl_rna.properties["type"].enum_items[kmi.type].name
        text = " ".join(mods + [f"drag {name}"])
    return text


def _draw_key_row(layout, group):
    """One shortcut on one line: on/off, what it does, the key (click to rebind), restore if changed.
    A group of keymap items that share the key is drawn and changed as one."""
    km, kmi = group[0]
    ids = encode_key_group(group)
    on = any(k.active for _m, k in group)
    row = layout.row(align=True)
    row.operator("keyops.shortcut_group_toggle", text="", emboss=False,
                 icon='CHECKBOX_HLT' if on else 'CHECKBOX_DEHLT').items = ids
    name = row.row()
    name.active = on
    name.label(text=shortcut_name(kmi))
    key = row.row(align=True)
    key.ui_units_x = 7
    waiting = key_capture.get("items") == ids
    key.operator("keyops.shortcut_group_set_key", text="Press a key..." if waiting else key_text(kmi),
                 depress=waiting).items = ids
    if any(k.is_user_modified for _m, k in group):
        row.operator("keyops.shortcut_group_restore", text="", icon='BACK').items = ids


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
