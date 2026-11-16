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


def _invoke_welcome():
    window, area, region = _find_view3d(bpy.context)
    if window is None:
        return None
    with bpy.context.temp_override(window=window, area=area, region=region):
        bpy.ops.keyops.welcome('INVOKE_DEFAULT')
    return None


def schedule_welcome():
    """Show the welcome screen once, after the UI has loaded."""
    if bpy.app.background:
        return
    p = get_keyops_prefs()
    if p.welcome_version >= F.WELCOME_VERSION or p.show_whats_new:
        return
    bpy.app.timers.register(_invoke_welcome, first_interval=1.0)


def _open_preferences():
    try:
        bpy.ops.preferences.addon_show(module=get_addon_name())
    except RuntimeError:
        pass
    return None


class KEYOPS_OT_welcome(bpy.types.Operator):
    bl_idname = "keyops.welcome"
    bl_label = "Welcome to Key Ops"
    bl_description = "Pick which shortcuts Key Ops starts with"
    bl_options = {'INTERNAL'}

    preset: bpy.props.EnumProperty(name="Keyboard", items=list(F.STYLES), default="ESSENTIALS") # type: ignore

    def invoke(self, context, event):
        get_keyops_prefs().welcome_version = F.WELCOME_VERSION  # shown once, even if dismissed
        return context.window_manager.invoke_props_dialog(self, width=580, title="Welcome to Key Ops", confirm_text="Get Started")

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Key Ops adds modeling tools, pie menus and an N-panel toolkit.")
        col.label(text="Pick which shortcuts to start with. You can turn any of them on or off later.")
        layout.separator()
        col = layout.column(align=True)
        for sid, name, desc, _icon, _i in F.STYLES:
            row = col.row(align=True)
            b = row.row(align=True)
            b.scale_y = 1.5
            b.ui_units_x = 6
            b.prop_enum(self, "preset", sid, text=name)
            d = row.row()
            d.active = sid == self.preset
            d.label(text=desc + ("  (recommended)" if sid == "ESSENTIALS" else ""))
        layout.separator()
        sub = layout.row()
        sub.active = False
        sub.label(text="Preferences open next so you can fine-tune features, shortcuts and pie menus.")

    def execute(self, context):
        p = get_keyops_prefs()
        p.shortcut_style = self.preset
        F.apply_style(self.preset)
        bpy.app.timers.register(_open_preferences, first_interval=0.1)
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


    def execute(self, context):
        p = get_keyops_prefs()
        p.show_whats_new = False
        p.welcome_version = F.WELCOME_VERSION
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
        from .. import pie_menus
        for pie in p.pies:
            if pie.enabled and pie.key not in ("", "NONE") and not p.pause_shortcuts and pie.editor in _MODE_KEYMAPS[mode]:
                sp = col.split(factor=0.3)
                sp.label(text=pie_menus.key_text(pie))
                sp2 = sp.split(factor=0.62)
                sp2.label(text=f"{pie.name} pie")
                sub = sp2.row()
                sub.active = False
                sub.label(text="Pie Menus")
                n += 1
        if not n:
            sub = layout.column()
            sub.active = False
            sub.label(text="No Key Ops shortcuts are active in this mode.")
            sub.label(text="Turn shortcuts on per feature in Preferences.")
        layout.operator("preferences.addon_show", text="Change in Preferences", icon='PREFERENCES').module = get_addon_name()

    def execute(self, context):
        return {'FINISHED'}


classes = (
    KEYOPS_OT_welcome,
    KEYOPS_OT_toggle_feature_card,
    KEYOPS_OT_dismiss_whats_new,
    KEYOPS_OT_shortcut_cheatsheet,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.keyops_open_feature = StringProperty()


def unregister():
    del bpy.types.WindowManager.keyops_open_feature
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
