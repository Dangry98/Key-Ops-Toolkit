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


def _invoke(operator, **props):
    window, area, region = _find_view3d(bpy.context)
    if window is None:
        return None
    try:
        with bpy.context.temp_override(window=window, area=area, region=region):
            operator('INVOKE_DEFAULT', **props)
    except (AttributeError, RuntimeError):
        pass  # the add-on was switched off before the screen came up
    return None


def _invoke_welcome(whats_new=False):
    _invoke(bpy.ops.keyops.welcome, whats_new=whats_new)
    return None


def _splash_is_open():
    """Blender shows its splash screen when it starts without a file. Python can't ask
    whether it is still open, so at startup we wait for the first click or key, which
    closes it."""
    starting_up = not bpy.context.preferences.is_dirty  # enabling in Preferences marks them changed
    return starting_up and bpy.context.preferences.view.show_splash and not bpy.data.filepath


def _show_first_screen(whats_new):
    if _splash_is_open():
        _invoke(bpy.ops.keyops.welcome_wait_for_splash, whats_new=whats_new)
    else:
        _invoke_welcome(whats_new)
    return None


def _show_welcome():
    return _show_first_screen(False)


def _show_whats_new():
    return _show_first_screen(True)


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
    """Only the first-install setup screen opens by itself. What's New never pops up on its own: the
    extensions platform treats update notifications inside Blender as advertising. It's one click away
    in the add-on's Preferences (KEYOPS_OT_show_whats_new)."""
    if bpy.app.background:
        return
    if first_screen(get_keyops_prefs()) == 'WELCOME':
        bpy.app.timers.register(_show_welcome, first_interval=1.0)


class KEYOPS_OT_show_whats_new(bpy.types.Operator):
    """Show what changed in this version of Key Ops"""
    bl_idname = "keyops.show_whats_new"
    bl_label = "What's New"

    def execute(self, context):
        _invoke_welcome(True)
        return {'FINISHED'}


class KEYOPS_OT_welcome_wait_for_splash(bpy.types.Operator):
    """Waits for Blender's splash screen to close, then opens the Key Ops welcome screen.
    Every event is passed on, so the splash screen works as usual."""
    bl_idname = "keyops.welcome_wait_for_splash"
    bl_label = "Wait for Splash Screen"
    bl_options = {'INTERNAL'}

    whats_new: BoolProperty(options={'SKIP_SAVE'}) # type: ignore

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        closes_splash = event.value == 'PRESS' and (
            event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE', 'ESC', 'RET', 'NUMPAD_ENTER'})
        if closes_splash:
            whats_new = self.whats_new
            bpy.app.timers.register(lambda: _invoke_welcome(whats_new), first_interval=0.3)
            return {'FINISHED', 'PASS_THROUGH'}
        return {'PASS_THROUGH'}


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


from ..utils.utilities import redraw_all_areas as _redraw_all


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
    KEYOPS_OT_welcome_wait_for_splash,
    KEYOPS_OT_toggle_feature_card,
    KEYOPS_OT_shortcut_group_toggle,
    KEYOPS_OT_shortcut_group_restore,
    KEYOPS_OT_shortcut_group_set_key,
    KEYOPS_OT_dismiss_whats_new,
    KEYOPS_OT_show_whats_new,
    KEYOPS_OT_shortcut_cheatsheet,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.keyops_open_feature = StringProperty()


def unregister():
    from .splash import close_overlays
    close_overlays()
    for fn in (_show_welcome, _show_whats_new):  # switched off before the screen came up
        if bpy.app.timers.is_registered(fn):
            bpy.app.timers.unregister(fn)
    branding.unregister()
    del bpy.types.WindowManager.keyops_open_feature
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
