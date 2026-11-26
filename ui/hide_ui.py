"""Hide parts of Blender's own interface: panels, menus and headers, from a Custom Menus button.

A Custom Menus "Hide Blender UI" item is a button running keyops.toggle_ui_element with the element's class
name (e.g. VIEW3D_PT_overlay_bones). Pressing it hides that element, pressing again shows it. Panels are
hidden through their poll, menus and headers by drawing nothing; Blender's own class keeps working and gets
its poll / draw back the moment it's shown again, the feature is switched off or the add-on is disabled.
The hidden elements are remembered in Key Ops' settings and hidden again at the next start.
"""

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty

_patched = {}  # class name -> {"poll": (had, original), "draw": original}


def _cls(name):
    cls = getattr(bpy.types, name, None)
    if cls is None or not isinstance(cls, type):
        return None
    if not issubclass(cls, (bpy.types.Panel, bpy.types.Menu, bpy.types.Header)):
        return None
    return cls


def is_hidden(name):
    return name in _patched


def _never(cls, context):
    return False


def _draw_nothing(self, context):
    pass


def hide(name):
    cls = _cls(name)
    if cls is None or name in _patched:
        return False
    state = {}
    if issubclass(cls, bpy.types.Panel):
        had = "poll" in cls.__dict__
        state["poll"] = (had, cls.__dict__.get("poll"))
        cls.poll = classmethod(_never)
        if not had:
            # Blender only asks a panel's poll if it had one when it was registered: register it again
            _reregister(cls)
    else:
        state["draw"] = cls.__dict__.get("draw")
        cls.draw = _draw_nothing
    _patched[name] = state
    _redraw()
    return True


def show(name):
    cls = _cls(name)
    state = _patched.pop(name, None)
    if cls is None or state is None:
        return False
    if "poll" in state:
        had, original = state["poll"]
        if had:
            cls.poll = original
        else:
            if "poll" in cls.__dict__:
                del cls.poll
            _reregister(cls)
    if "draw" in state:
        if state["draw"] is not None:
            cls.draw = state["draw"]
        elif "draw" in cls.__dict__:
            del cls.draw
    _redraw()
    return True


def _reregister(cls):
    try:
        bpy.utils.unregister_class(cls)
        bpy.utils.register_class(cls)
    except (RuntimeError, ValueError):
        pass


def _redraw():
    wm = getattr(bpy.context, "window_manager", None)
    for window in (wm.windows if wm else ()):
        for area in window.screen.areas:
            area.tag_redraw()


def show_all():
    for name in list(_patched):
        show(name)


def hidden_names():
    return sorted(_patched)


def _save():
    from ..utils.pref_utils import get_keyops_prefs
    prefs = get_keyops_prefs()
    if prefs is not None and hasattr(prefs, "hidden_ui"):
        prefs.hidden_ui = ",".join(hidden_names())


def restore_saved():
    """Hide again what was hidden last time (called once the add-on is set up)."""
    from ..utils.pref_utils import get_keyops_prefs
    prefs = get_keyops_prefs()
    names = [n for n in getattr(prefs, "hidden_ui", "").split(",") if n] if prefs else []
    for n in names:
        hide(n)
    return None


# ---------------------------------------------------------------- the picker
_items_cache = []


def ui_element_items(self, context):
    """Every panel, menu and header Blender has, for the search."""
    global _items_cache
    out = []
    for base, kind in ((bpy.types.Panel, "Panel"), (bpy.types.Menu, "Menu"), (bpy.types.Header, "Header")):
        for cls in base.__subclasses__():
            name = getattr(cls, "bl_idname", "") or cls.__name__
            if not name or name.startswith("KEYOPS") or getattr(bpy.types, name, None) is not cls:
                continue
            label = getattr(cls, "bl_label", "") or name
            space = getattr(cls, "bl_space_type", "")
            out.append((name, f"{label}  ({kind}{', ' + space.replace('_', ' ').title() if space else ''})",
                        name))
    out.sort(key=lambda t: t[1].lower())
    _items_cache = out
    return _items_cache


class KEYOPS_OT_toggle_ui_element(bpy.types.Operator):
    """Hide this part of Blender's interface, or show it again"""
    bl_idname = "keyops.toggle_ui_element"
    bl_label = "Hide / Show Blender UI"

    element: StringProperty(name="Element", description="The panel, menu or header's class name, "
                                                        "e.g. VIEW3D_PT_overlay") # type: ignore

    @classmethod
    def description(cls, context, props):
        if props and props.element:
            state = "Show" if is_hidden(props.element) else "Hide"
            return f"{state} {props.element}"
        return cls.__doc__

    def execute(self, context):
        if not self.element:
            self.report({'WARNING'}, "Pick a panel, menu or header first")
            return {'CANCELLED'}
        if _cls(self.element) is None:
            self.report({'WARNING'}, f"{self.element} isn't a Blender panel, menu or header")
            return {'CANCELLED'}
        if is_hidden(self.element):
            show(self.element)
            self.report({'INFO'}, f"Showing {self.element}")
        else:
            hide(self.element)
            self.report({'INFO'}, f"Hid {self.element}")
        _save()
        return {'FINISHED'}


class KEYOPS_OT_pick_ui_element(bpy.types.Operator):
    """Pick the panel, menu or header this button hides"""
    bl_idname = "keyops.pick_ui_element"
    bl_label = "Pick Blender UI"
    bl_property = "element"
    bl_options = {'INTERNAL'}

    element: EnumProperty(items=ui_element_items) # type: ignore
    slot: IntProperty(default=-1, options={'SKIP_SAVE'}) # type: ignore

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .. import pie_menus as PM
        from ..utils.pref_utils import get_keyops_prefs
        prefs = get_keyops_prefs()
        item = PM._active_item(prefs, self.slot if self.slot >= 0 else prefs.pie_slot)
        if item is None:
            return {'CANCELLED'}
        cls = _cls(self.element)
        item.kind = PM.O
        item.idname = KEYOPS_OT_toggle_ui_element.bl_idname
        item.props = f"element={self.element!r}"
        item.label = f"Hide {getattr(cls, 'bl_label', '') or self.element}"
        if not item.icon:
            item.icon = 'HIDE_ON'
        PM._changed()
        PM._redraw_all(context)
        return {'FINISHED'}


classes = (KEYOPS_OT_toggle_ui_element, KEYOPS_OT_pick_ui_element)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    if not bpy.app.timers.is_registered(restore_saved):
        bpy.app.timers.register(restore_saved, first_interval=0.5)


def unregister():
    if bpy.app.timers.is_registered(restore_saved):
        bpy.app.timers.unregister(restore_saved)
    show_all()
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
