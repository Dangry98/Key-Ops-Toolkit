"""Element mode for the Edit Toolkit, next to Vertex, Edge and Face.

It works as a selection mode rather than a one-off command: while Element is on, picking any part of a mesh
island picks the whole island (and deselecting a part, or Ctrl+clicking it, deselects the island). Turning the
mode on also converts what is selected already.
The mode ends when you pick Vertex, Edge or Face, change the select mode another way, or leave Edit Mode.
"""

import bmesh
import bpy
from bpy.props import EnumProperty

MODES = ("VERT", "EDGE", "FACE")

# module state: the active extra mode ("NONE" or "ELEMENT") and whether its watcher runs
state = {"mode": "NONE", "running": False}


def active_mode():
    return state["mode"] if state["running"] else "NONE"


def _edit_meshes(context):
    objs = context.objects_in_mode_unique_data or ([context.edit_object] if context.edit_object else [])
    return [o for o in objs if o and o.type == 'MESH']


# ---------------------------------------------------------------- selection growing
# The mode keeps one rule: what is selected is whole islands. After any change of the selection (a click, box,
# lasso or circle select, select all, Ctrl+click...) it compares what is selected now with before:
# - something new was picked: grow it to whole islands (Blender's own Select Linked, in C);
# - only something was unpicked: unpick the rest of those islands (Select Linked on the inverted selection).
# Selection counts kept by Blender make the "did anything change?" check free, so the watcher can look often.

_KINDS = ((bmesh.types.BMVert, "v"), (bmesh.types.BMEdge, "e"), (bmesh.types.BMFace, "f"))


def _key(elem):
    for cls, kind in _KINDS:
        if isinstance(elem, cls):
            return (kind, elem.index)
    return None


def snapshot(bm):
    """(geometry counts, selected vertex indices, selected face indices, active element)."""
    act = bm.select_history.active
    return ((len(bm.verts), len(bm.edges), len(bm.faces)), {v.index for v in bm.verts if v.select},
            {f.index for f in bm.faces if f.select}, (_key(act) if act else None))


def _quick(me, bm):
    """Free to compute: Blender keeps the selection totals; plus counts and the active element."""
    act = bm.select_history.active
    return (me.total_vert_sel, me.total_edge_sel, me.total_face_sel, len(bm.verts), len(bm.faces),
            _key(act) if act else None)


def _linked():
    bpy.ops.mesh.select_linked('EXEC_DEFAULT', False, delimit=set())


def _invert():
    bpy.ops.mesh.select_all('EXEC_DEFAULT', False, action='INVERT')


def sync(objs, before, click=False, hint=None):
    """Make the selection of the meshes in `objs` whole islands again after a change. `before`: their snapshots
    by name. `click`: a mouse pick happened, so the active element counts as picked even if it was selected
    already (clicking part of a selected island keeps it). `hint`: the modifier keys of the mouse press that
    started it: 'pick' (none), 'toggle' (Shift) or 'remove' (Ctrl). A plain box select over part of a selected
    island picks it again, it doesn't unpick the rest. Returns the new snapshots and whether it changed
    anything."""
    added = removed = False
    after = {}
    for obj in objs:
        snap = snapshot(bmesh.from_edit_mesh(obj.data))
        old = before.get(obj.name)
        after[obj.name] = snap
        if old is None or old[0] != snap[0]:
            continue  # new to the mode, or the geometry changed (extrude, delete...): nothing to grow
        verts, faces = snap[1], snap[2]
        if (verts - old[1]) or (faces - old[2]):
            added = True
        elif click and snap[3] is not None and snap[3] != old[3]:
            added = True
        if (old[1] - verts) or (old[2] - faces):
            removed = True
    if removed and not added and hint == 'pick' and any(o.data.total_vert_sel for o in objs):
        added = True  # replaced by a plain pick inside selected islands: those islands stay picked
    if added:
        _linked()
    elif removed:
        _invert()
        _linked()
        _invert()
    else:
        return after, False
    return {o.name: snapshot(bmesh.from_edit_mesh(o.data)) for o in objs}, True


def convert(context):
    """Turn the current selection into whole islands when the mode is switched on."""
    if any(o.data.total_vert_sel for o in _edit_meshes(context)):
        _linked()


# ---------------------------------------------------------------- operators
class KEYOPS_OT_sub_object_mode(bpy.types.Operator):
    bl_idname = "keyops.sub_object_mode"
    bl_label = "Selection Mode"
    bl_description = "Pick what you select"
    bl_options = {'UNDO'}  # no redo panel: there is nothing to adjust

    mode: EnumProperty(name="Mode", items=(
        ("VERT", "Vertex", "Select vertices.\nShift: add this mode. Ctrl: convert the selection"),
        ("EDGE", "Edge", "Select edges.\nShift: add this mode. Ctrl: convert the selection"),
        ("FACE", "Face", "Select faces.\nShift: add this mode. Ctrl: convert the selection"),
        ("ELEMENT", "Element", "Element mode: picking any part of a mesh island picks the whole island.\n"
                               "Ctrl+click deselects an island. Click again to turn it off"))) # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def description(cls, context, props):
        return cls.bl_rna.properties["mode"].enum_items[props.mode].description if props else cls.bl_description

    def invoke(self, context, event):
        self.extend, self.expand = event.shift, event.ctrl
        return self.execute(context)

    def execute(self, context):
        extend, expand = getattr(self, "extend", False), getattr(self, "expand", False)
        if self.mode in MODES:
            state["mode"] = "NONE"
            bpy.ops.mesh.select_mode(type=self.mode, use_extend=extend, use_expand=expand)
            return {'FINISHED'}
        if active_mode() == self.mode:  # clicking the lit button turns it off
            state["mode"] = "NONE"
            return {'FINISHED'}
        convert(context)
        state["mode"] = self.mode
        if not state["running"] and context.window and not bpy.app.background:
            bpy.ops.keyops.sub_object_watch('INVOKE_DEFAULT')
        return {'FINISHED'}


class KEYOPS_OT_sub_object_watch(bpy.types.Operator):
    """Keeps Element mode working: grows each new pick to its whole island."""
    bl_idname = "keyops.sub_object_watch"
    bl_label = "Element Mode"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        self.select_mode = tuple(context.tool_settings.mesh_select_mode)
        self.snaps = {o.name: snapshot(bmesh.from_edit_mesh(o.data)) for o in _edit_meshes(context)}
        self.quick = self._quicks(context)
        self.click = False
        self.hint = None
        # looks every 50 ms (free unless the selection changed): catches box / lasso / circle select, select
        # all and anything else that changes the selection, not only clicks
        self.timer = context.window_manager.event_timer_add(0.05, window=context.window)
        context.window_manager.modal_handler_add(self)
        state["running"] = True
        return {'RUNNING_MODAL'}

    @staticmethod
    def _quicks(context):
        return {o.name: _quick(o.data, bmesh.from_edit_mesh(o.data)) for o in _edit_meshes(context)}

    def _finish(self, context):
        state["running"] = False
        state["mode"] = "NONE"
        context.window_manager.event_timer_remove(self.timer)
        for area in context.screen.areas if context.screen else ():
            area.tag_redraw()
        return {'FINISHED'}

    def ended(self, context):
        """The mode is over: switched off, another mode was picked, or we left Edit Mode."""
        if state["mode"] == "NONE" or context.mode != 'EDIT_MESH':
            return True
        return tuple(context.tool_settings.mesh_select_mode) != self.select_mode

    def update(self, context):
        quick = self._quicks(context)
        if quick == self.quick and not self.click:
            return  # nothing changed: the usual case, and free
        self.snaps, changed = sync(_edit_meshes(context), self.snaps, self.click, self.hint)
        self.click = False
        if changed or quick != self.quick:
            self.hint = None
        self.quick = self._quicks(context) if changed else quick
        if changed:
            for area in context.screen.areas if context.screen else ():
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

    def _ctrl_deselect(self, context, event):
        """Ctrl+click deselects what's under the mouse (Blender's own Ctrl+click picks a shortest path, which
        would add to the selection); the mode then deselects its whole island."""
        for area in context.window.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for region in area.regions:
                if region.type != 'WINDOW':
                    continue
                x, y = event.mouse_x - region.x, event.mouse_y - region.y
                if 0 <= x < region.width and 0 <= y < region.height:
                    with context.temp_override(area=area, region=region):
                        bpy.ops.view3d.select(deselect=True, location=(x, y))
                    return True
        return False

    def modal(self, context, event):
        if self.ended(context):
            return self._finish(context)
        # Ctrl+click (a click, not a drag: Ctrl+drag stays Blender's box deselect)
        if event.type == 'LEFTMOUSE' and event.value == 'CLICK' and event.ctrl \
                and not (event.shift or event.alt or event.oskey) and self._ctrl_deselect(context, event):
            self.hint = 'remove'
            self.update(context)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.hint = 'remove' if event.ctrl else 'toggle' if event.shift else 'pick'
        if event.type == 'LEFTMOUSE' and event.value in {'PRESS', 'RELEASE', 'CLICK'}:
            # Blender picks on this event (press or release, by preference): the next event or tick looks
            self.click = True
            return {'PASS_THROUGH'}
        if event.type in {'TIMER', 'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'} or self.click:
            self.update(context)
        return {'PASS_THROUGH'}


def draw_mode_row(layout, context):
    """Vertex, Edge, Face, Element as one centered row of mode buttons."""
    sel = context.tool_settings.mesh_select_mode
    extra = active_mode()
    row = layout.row(align=True)
    for mode, on, icon in (("VERT", sel[0], 'VERTEXSEL'), ("EDGE", sel[1], 'EDGESEL'), ("FACE", sel[2], 'FACESEL')):
        row.operator("keyops.sub_object_mode", text="", icon=icon, depress=bool(on) and extra == "NONE").mode = mode
    row.operator("keyops.sub_object_mode", text="", icon=ELEMENT_ICON, depress=extra == "ELEMENT").mode = "ELEMENT"
    return row


ELEMENT_ICON = 'SNAP_VOLUME'


# ---------------------------------------------------------------- the header group
# Blender draws its Vertex / Edge / Face buttons with a C template (layout.template_header_3D_mode) inside
# VIEW3D_HT_header.draw, so nothing can be added to that group. In mesh Edit Mode Key Ops draws the group
# itself instead: the same three modes (Shift adds a mode, Ctrl converts, like Blender's) plus Element, as one
# joined row. Blender's header draw runs unchanged; only that one template call is answered by Key Ops.

class _LayoutProxy:
    def __init__(self, layout, context):
        self._layout = layout
        self._context = context

    def __getattr__(self, name):
        return getattr(self._layout, name)

    def template_header_3D_mode(self):
        if self._context.mode == 'EDIT_MESH' and _header_on():
            draw_mode_row(self._layout, self._context)
        else:
            self._layout.template_header_3D_mode()


class _HeaderProxy:
    def __init__(self, header, context):
        self._header = header
        self.layout = _LayoutProxy(header.layout, context)

    def __getattr__(self, name):
        return getattr(self._header, name)


def _header_draw(self, context):
    _original_header_draw(_HeaderProxy(self, context), context)


def _header_on():
    from ..utils.pref_utils import feature_on
    try:
        return feature_on("toolkit_panel")
    except Exception:  # noqa: BLE001  prefs not ready (e.g. while registering)
        return False


_original_header_draw = None


def _patch_header():
    """Swap Blender's own header draw function for _header_draw inside the header's list of draw functions
    (the one Header.append / prepend add to), so other add-ons' header items keep drawing and can still be
    removed, whenever they were added."""
    global _original_header_draw
    header = getattr(bpy.types, "VIEW3D_HT_header", None)
    if header is None:
        return
    funcs = header._dyn_ui_initialize()
    if _header_draw in funcs:
        return
    i = next((k for k, f in enumerate(funcs) if getattr(f, "__qualname__", "") == "VIEW3D_HT_header.draw"), 0)
    _original_header_draw = funcs[i]
    funcs[i] = _header_draw


def _unpatch_header():
    header = getattr(bpy.types, "VIEW3D_HT_header", None)
    funcs = getattr(getattr(header, "draw", None), "_draw_funcs", None)
    if funcs is not None and _header_draw in funcs and _original_header_draw is not None:
        funcs[funcs.index(_header_draw)] = _original_header_draw


classes = (KEYOPS_OT_sub_object_mode, KEYOPS_OT_sub_object_watch)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    _patch_header()


def unregister():
    _unpatch_header()
    state["mode"] = "NONE"
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
