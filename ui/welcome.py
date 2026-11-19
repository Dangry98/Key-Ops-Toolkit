"""First-run welcome, cheat sheet and small helper operators for the 1.0 UI."""

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty

from .. import features as F
from ..utils.pref_utils import get_addon_name, get_keyops_prefs
from .splash import KEYOPS_OT_welcome, mark_seen, read_seen
from . import branding

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


def _invoke_welcome(whats_new=False):
    window, area, region = _find_view3d(bpy.context)
    if window is None:
        return None
    try:
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.keyops.welcome('INVOKE_DEFAULT', whats_new=whats_new)
    except (AttributeError, RuntimeError):
        pass  # the add-on was switched off before the screen came up
    return None


def _invoke_whats_new():
    return _invoke_welcome(True)


def first_screen(p):
    """'WELCOME' for a new install, 'WHATS_NEW' once after each update, otherwise None."""
    from .branding import version_text
    seen = read_seen()
    welcome_version = max(p.welcome_version, int(seen.get("welcome_version", 0) or 0))
    last_seen = seen.get("last_seen_version") or p.last_seen_version
    if last_seen == version_text():
        return None  # this version's screen was shown already: once ever per update
    if welcome_version < F.WELCOME_VERSION and not p.show_whats_new:
        return 'WELCOME'
    if p.show_whats_new or last_seen != version_text():
        return 'WHATS_NEW'
    return None


def schedule_welcome():
    if bpy.app.background:
        return
    kind = first_screen(get_keyops_prefs())
    if kind == 'WELCOME':
        bpy.app.timers.register(_invoke_welcome, first_interval=1.0)
    elif kind == 'WHATS_NEW':
        bpy.app.timers.register(_invoke_whats_new, first_interval=1.0)


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


def _key_group(context, items):
    """The user keymap items a Shortcuts row stands for ("keymap|id;keymap|id")."""
    kc = context.window_manager.keyconfigs.user
    out = []
    for part in items.split(";"):
        name, _sep, kid = part.rpartition("|")
        km = kc.keymaps.get(name)
        kmi = km.keymap_items.from_id(int(kid)) if km and kid.isdigit() else None
        if kmi is not None:
            out.append((km, kmi))
    return out


def _redraw_all(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


class KEYOPS_OT_shortcut_group_toggle(bpy.types.Operator):
    bl_idname = "keyops.shortcut_group_toggle"
    bl_label = "Use Shortcut"
    bl_description = "Turn this shortcut on or off"
    bl_options = {'INTERNAL'}
    items: StringProperty() # type: ignore

    def execute(self, context):
        group = _key_group(context, self.items)
        on = not any(kmi.active for _km, kmi in group)
        for _km, kmi in group:
            kmi.active = on
        return {'FINISHED'}


class KEYOPS_OT_shortcut_group_restore(bpy.types.Operator):
    bl_idname = "keyops.shortcut_group_restore"
    bl_label = "Restore"
    bl_description = "Put this shortcut back to the key Key Ops gave it"
    bl_options = {'INTERNAL'}
    items: StringProperty() # type: ignore

    def execute(self, context):
        for km, kmi in _key_group(context, self.items):
            if kmi.is_user_modified:
                km.restore_item_to_default(kmi)
        return {'FINISHED'}


_SKIP_KEYS = {"LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_ALT", "RIGHT_ALT", "OSKEY",
              "MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "TRACKPADPAN", "TRACKPADZOOM", "WINDOW_DEACTIVATE"}


class KEYOPS_OT_shortcut_group_set_key(bpy.types.Operator):
    bl_idname = "keyops.shortcut_group_set_key"
    bl_label = "Set Key"
    bl_description = ("Click, then press the new key (with Ctrl/Shift/Alt). Mouse buttons work too. "
                      "Esc cancels")
    bl_options = {'INTERNAL'}
    items: StringProperty() # type: ignore

    def invoke(self, context, event):
        from ..addon_preferences import key_capture
        key_capture["items"] = self.items
        context.window_manager.modal_handler_add(self)
        _redraw_all(context)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        from ..addon_preferences import key_capture
        if event.value != 'PRESS' or event.type in _SKIP_KEYS or event.type.startswith(("TIMER", "NDOF", "EVT_")):
            return {'RUNNING_MODAL'}
        if event.type != 'ESC':
            for _km, kmi in _key_group(context, self.items):  # every keymap item of the row gets the key
                kmi.type = event.type
                kmi.ctrl, kmi.shift, kmi.alt, kmi.oskey = event.ctrl, event.shift, event.alt, event.oskey
            context.window_manager.keyconfigs.update()  # so Blender sees the items as changed (restorable)
        key_capture["items"] = ""
        _redraw_all(context)
        return {'FINISHED'}


class KEYOPS_OT_dismiss_whats_new(bpy.types.Operator):
    bl_idname = "keyops.dismiss_whats_new"
    bl_label = "What's New"
    bl_options = {'INTERNAL'}


    def execute(self, context):
        mark_seen(get_keyops_prefs())
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
                from ..addon_preferences import shortcut_name
                sp2.label(text=shortcut_name(kmi))
                sub = sp2.row()
                sub.active = False
                sub.label(text=f.name)
                n += 1
        from .. import pie_menus
        for pie in p.pies:
            if pie.enabled and pie.key not in ("", "NONE") and not p.pause_shortcuts and set(pie_menus.editor_names(pie)) & set(_MODE_KEYMAPS[mode]):
                sp = col.split(factor=0.3)
                sp.label(text=pie_menus.key_text(pie))
                sp2 = sp.split(factor=0.62)
                sp2.label(text=f"{pie.name} pie")
                sub = sp2.row()
                sub.active = False
                sub.label(text="Custom Menus")
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
    KEYOPS_OT_shortcut_group_toggle,
    KEYOPS_OT_shortcut_group_restore,
    KEYOPS_OT_shortcut_group_set_key,
    KEYOPS_OT_dismiss_whats_new,
    KEYOPS_OT_shortcut_cheatsheet,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.keyops_open_feature = StringProperty()


def unregister():
    from .splash import close_overlays
    close_overlays()
    for fn in (_invoke_welcome, _invoke_whats_new):  # switched off before the screen came up
        if bpy.app.timers.is_registered(fn):
            bpy.app.timers.unregister(fn)
    branding.unregister()
    del bpy.types.WindowManager.keyops_open_feature
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
