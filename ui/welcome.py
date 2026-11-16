"""First-run welcome, cheat sheet and small helper operators for the 1.0 UI."""

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty

from .. import features as F
from ..utils.pref_utils import get_addon_name, get_keyops_prefs

NPANEL_TAB = "Key Ops"

# Keymaps that matter per mode, for the cheat sheet
_MODE_KEYMAPS = {
    'OBJECT': {"Object Mode", "Object Non-modal", "3D View", "3D View Generic", "Window", "Screen", "Property Editor", "Outliner"},
    'EDIT_MESH': {"Mesh", "3D View", "3D View Generic", "Window", "Screen", "Property Editor", "Outliner"},
}


def _find_view3d(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                return window, area, region
    return None, None, None


def _invoke_welcome(step=0):
    window, area, region = _find_view3d(bpy.context)
    if window is None:
        return None
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.keyops.welcome('INVOKE_DEFAULT', step=step)
    return None


def schedule_welcome():
    """Show the welcome dialog once, after the UI has loaded."""
    if bpy.app.background:
        return
    p = get_keyops_prefs()
    if p.welcome_version >= F.WELCOME_VERSION or p.show_whats_new:
        return
    bpy.app.timers.register(_invoke_welcome, first_interval=1.0)


class KEYOPS_OT_welcome(bpy.types.Operator):
    bl_idname = "keyops.welcome"
    bl_label = "Welcome to Key Ops"
    bl_description = "Choose how Key Ops uses your keyboard and see where everything is"
    bl_options = {'INTERNAL'}

    step: IntProperty(default=0, min=0, max=2, options={'SKIP_SAVE'}) # type: ignore

    def invoke(self, context, event):
        p = get_keyops_prefs()
        p.welcome_version = F.WELCOME_VERSION  # shown once, even if dismissed
        confirm = {0: "Next", 1: "Next", 2: "Open N-panel"}[self.step]
        return context.window_manager.invoke_props_dialog(
            self, width=560, title=f"Welcome to Key Ops  ·  Step {self.step + 1} of 3", confirm_text=confirm)

    def draw(self, context):
        p = get_keyops_prefs()
        layout = self.layout
        if self.step == 0:
            self._draw_style(p, layout)
        elif self.step == 1:
            self._draw_review(p, layout)
        else:
            self._draw_where(layout)

    def _draw_style(self, p, layout):
        col = layout.column(align=True)
        col.label(text="Key Ops adds modeling tools, pie menus and panels.")
        col.label(text="Nothing changes your shortcuts until you choose.", icon='CHECKMARK')
        layout.separator()
        layout.label(text="How should Key Ops use your keyboard?")
        for sid, name, desc, icon, _i in F.STYLES:
            row = layout.row(align=True)
            b = row.row(align=True)
            b.scale_y = 1.6
            b.ui_units_x = 7
            b.prop_enum(p, "shortcut_style", sid, text=name, icon=icon)
            d = row.column(align=True)
            d.scale_y = 0.8
            lines = [desc] if len(desc) < 52 else [desc[:desc.rfind(' ', 0, 52)], desc[desc.rfind(' ', 0, 52) + 1:]]
            for i, line in enumerate(lines):
                sub = d.row()
                sub.active = sid == p.shortcut_style
                sub.label(text=line + ("   (recommended)" if sid == "ESSENTIALS" and i == len(lines) - 1 else ""))

    def _draw_review(self, p, layout):
        feats, keys, repl = F.stats(p)
        name = dict((s[0], s[1]) for s in F.STYLES)[p.shortcut_style]
        col = layout.column(align=True)
        if keys:
            col.label(text=f"{name} adds {keys} shortcuts. {repl} of them replace Blender keys.",
                      icon='ERROR' if repl else 'CHECKMARK')
            sub = col.row()
            sub.active = False
            sub.label(text="Untick anything you don't want. Features stay on without their keys.")
        else:
            col.label(text=f"{name} adds no shortcuts.", icon='CHECKMARK')
            sub = col.row()
            sub.active = False
            sub.label(text="Tick a feature below to add its shortcuts, or go Back and pick another style.")
        box = layout.box()
        grid = box.column(align=True)
        for f in F.visible_features(p):
            if not f.keys or f.optional:
                continue
            if not (getattr(p, f"enable_{f.id}") or (f.keys_only and f.default_on)):
                continue
            row = grid.row(align=True)
            row.prop(p, f"keys_{f.id}", text="")
            sp = row.split(factor=0.36)
            sp.label(text=f.name)
            sp2 = sp.split(factor=0.42)
            sp2.label(text=", ".join(k.key for k in f.keys)[:28], icon='EVENT_K')
            r = sp2.row()
            r.active = bool(getattr(p, f"keys_{f.id}"))
            if f.replaced:
                r.alert = bool(getattr(p, f"keys_{f.id}"))
                r.label(text="Replaces " + f.replaced[0].replaces, icon='ERROR')
            else:
                r.label(text="Free key" + ("s" if len(f.keys) > 1 else ""), icon='CHECKMARK')
        row = layout.row()
        row.operator("keyops.welcome_step", text="Back", icon='BACK').step = 0

    def _draw_where(self, layout):
        layout.label(text="You're set. Here's where things are:")
        rows = (
            ("N", "Key Ops tab in the 3D View sidebar: object, mesh, modifier and pipeline tools."),
            ("F3", "Search \"Key Ops\" to run any tool without a shortcut."),
            ("?", "The ? button in the Key Ops panel header lists the shortcuts active in your mode."),
            ("PREFERENCES", "Edit > Preferences > Add-ons > Key Ops changes style, features and keys."),
        )
        box = layout.box()
        for key, text in rows:
            sp = box.split(factor=0.14)
            if key == "PREFERENCES":
                sp.label(text="", icon='PREFERENCES')
            else:
                sp.label(text=key)
            sp.label(text=text)

    def execute(self, context):
        if self.step < 2:
            nxt = self.step + 1
            bpy.app.timers.register(lambda: _invoke_welcome(nxt), first_interval=0.05)
        else:
            bpy.ops.keyops.open_npanel()
        return {'FINISHED'}


class KEYOPS_OT_welcome_step(bpy.types.Operator):
    bl_idname = "keyops.welcome_step"
    bl_label = "Go to Step"
    bl_options = {'INTERNAL'}
    step: IntProperty(options={'SKIP_SAVE'}) # type: ignore

    def execute(self, context):
        s = self.step
        bpy.app.timers.register(lambda: _invoke_welcome(s), first_interval=0.05)
        return {'FINISHED'}


class KEYOPS_OT_open_npanel(bpy.types.Operator):
    bl_idname = "keyops.open_npanel"
    bl_label = "Open Key Ops Panel"
    bl_description = "Show the 3D View sidebar on the Key Ops tab"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        _w, area, _r = _find_view3d(context)
        if area is None:
            return {'CANCELLED'}
        area.spaces.active.show_region_ui = True
        area.tag_redraw()

        def select_tab(tries=[0]):
            # The sidebar only knows its tabs after it has been drawn once
            for region in area.regions:
                if region.type == 'UI':
                    try:
                        region.active_panel_category = NPANEL_TAB
                        region.tag_redraw()
                        return None
                    except (AttributeError, TypeError, ValueError, ReferenceError):
                        pass
            tries[0] += 1
            return 0.1 if tries[0] < 20 else None
        bpy.app.timers.register(select_tab, first_interval=0.1)
        return {'FINISHED'}


class KEYOPS_OT_toggle_feature_card(bpy.types.Operator):
    bl_idname = "keyops.toggle_feature_card"
    bl_label = "Show Details"
    bl_description = "Show this feature's shortcuts and settings"
    bl_options = {'INTERNAL'}
    feature_id: StringProperty() # type: ignore

    def execute(self, context):
        wm = context.window_manager
        wm.keyops_open_feature = "" if wm.keyops_open_feature == self.feature_id else self.feature_id
        return {'FINISHED'}


class KEYOPS_OT_dismiss_whats_new(bpy.types.Operator):
    bl_idname = "keyops.dismiss_whats_new"
    bl_label = "What's New"
    bl_options = {'INTERNAL'}
    switch: BoolProperty(options={'SKIP_SAVE'}) # type: ignore

    @classmethod
    def description(cls, context, properties):
        return "Switch to tools and panels without shortcuts" if properties.switch else "Keep features and shortcuts as they were"

    def execute(self, context):
        p = get_keyops_prefs()
        p.show_whats_new = False
        p.welcome_version = F.WELCOME_VERSION
        if self.switch:
            p.shortcut_style = "ESSENTIALS"
        return {'FINISHED'}


class KEYOPS_OT_shortcut_cheatsheet(bpy.types.Operator):
    bl_idname = "keyops.shortcut_cheatsheet"
    bl_label = "Key Ops Shortcuts"
    bl_description = "List the Key Ops shortcuts active in the current mode"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=420)

    def draw(self, context):
        p = get_keyops_prefs()
        layout = self.layout
        mode = context.mode if context.mode in _MODE_KEYMAPS else 'OBJECT'
        title = "Object Mode" if mode == 'OBJECT' else "Edit Mode"
        layout.label(text=f"Key Ops shortcuts  ·  {title}", icon='KEYINGSET')
        if p.pause_shortcuts:
            layout.label(text="All Key Ops shortcuts are paused.", icon='PAUSE')
        col = layout.column(align=True)
        n = 0
        for f in F.FEATURES:
            if not getattr(p, f"enable_{f.id}", False) or not F.keys_active(f.id, p):
                continue
            seen = set()
            for km, kmi in F.tracked_items(f.id):
                if km.name not in _MODE_KEYMAPS[mode] or kmi.value == 'RELEASE':
                    continue
                key = kmi.to_string()
                if (key, km.name) in seen:
                    continue
                seen.add((key, km.name))
                sp = col.split(factor=0.3)
                sp.label(text=key)
                sp2 = sp.split(factor=0.62)
                sp2.label(text=kmi.name or kmi.idname)
                sub = sp2.row()
                sub.active = False
                sub.label(text=f.name)
                n += 1
        if not n:
            sub = layout.column()
            sub.active = False
            sub.label(text="No Key Ops shortcuts are active in this mode.")
            sub.label(text="Pick Blender+ or Industry in Preferences to add some.")
        layout.operator("preferences.addon_show", text="Change in Preferences", icon='PREFERENCES').module = get_addon_name()

    def execute(self, context):
        return {'FINISHED'}


class KEYOPS_MT_panel_menu(bpy.types.Menu):
    bl_idname = "KEYOPS_MT_panel_menu"
    bl_label = "Key Ops"

    def draw(self, context):
        p = get_keyops_prefs()
        layout = self.layout
        layout.prop(p, "pause_shortcuts", text="Pause All Key Ops Shortcuts")
        layout.operator("keyops.shortcut_cheatsheet", text="Active Shortcuts", icon='KEYINGSET')
        layout.separator()
        layout.operator("preferences.addon_show", text="Preferences", icon='PREFERENCES').module = get_addon_name()
        layout.operator("keyops.welcome", text="Show Welcome", icon='HEART')
        layout.operator("wm.url_open", text="Documentation", icon='HELP').url = F.DOCS_URL


classes = (
    KEYOPS_OT_welcome,
    KEYOPS_OT_welcome_step,
    KEYOPS_OT_open_npanel,
    KEYOPS_OT_toggle_feature_card,
    KEYOPS_OT_dismiss_whats_new,
    KEYOPS_OT_shortcut_cheatsheet,
    KEYOPS_MT_panel_menu,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.keyops_open_feature = StringProperty()


def unregister():
    del bpy.types.WindowManager.keyops_open_feature
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
