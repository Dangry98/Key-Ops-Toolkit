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
def _island(vert):
    """All vertices connected to `vert` by edges."""
    seen, todo = {vert}, [vert]
    while todo:
        v = todo.pop()
        for e in v.link_edges:
            o = e.other_vert(v)
            if o not in seen:
                seen.add(o)
                todo.append(o)
    return seen


def _set_verts(bm, verts, value):
    for v in verts:
        v.select = value
        for e in v.link_edges:
            if e.other_vert(v) in verts:
                e.select = value
        for f in v.link_faces:
            if all(fv in verts for fv in f.verts):
                f.select = value


_KINDS = ((bmesh.types.BMVert, "v"), (bmesh.types.BMEdge, "e"), (bmesh.types.BMFace, "f"))


def _key(elem):
    for cls, kind in _KINDS:
        if isinstance(elem, cls):
            return (kind, elem.index)
    return None


def _vert_of(bm, key):
    kind, i = key
    if kind == "v":
        return bm.verts[i]
    return (bm.edges if kind == "e" else bm.faces)[i].verts[0]


def snapshot(bm):
    """What the mode compares against: selected vertices, edges and faces (in Face mode, deselecting one face can
    leave all its vertices selected), the active element, plus counts so edits that add or remove geometry
    (extrude, delete...) are not taken for a selection change."""
    counts = (len(bm.verts), len(bm.edges), len(bm.faces))
    active = _key(bm.select_history.active) if bm.select_history.active else None
    sel = {("v", e.index) for e in bm.verts if e.select}
    sel |= {("e", e.index) for e in bm.edges if e.select}
    sel |= {("f", e.index) for e in bm.faces if e.select}
    return counts, sel, active


def grow(bm, before, click=False, deselect_only=False):
    """Grow what was newly picked to a whole island, and shrink what was unpicked the same way.
    `click`: a mouse pick happened, so the active element counts as picked even if it was selected already.
    `deselect_only`: a Ctrl+click deselect, so only shrink.
    Picks win over removals, so clicking part of an already selected island keeps the whole of it.
    Returns the new snapshot and whether anything changed."""
    counts, old, _old_active = before
    now = snapshot(bm)
    if now[0] != counts:  # the geometry changed: nothing to grow, start over from here
        return now, False
    sel, active = now[1], now[2]
    added, removed = sel - old, old - sel
    if not added and not removed:
        return now, False
    picked = set() if deselect_only else set(added)
    if click and not deselect_only and active in sel:
        picked.add(active)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    on = set()
    for key in picked:
        v = _vert_of(bm, key)
        if v not in on:
            on |= _island(v)
    off = set()
    for key in removed:
        v = _vert_of(bm, key)
        if v not in on and v not in off:
            off |= _island(v)
    _set_verts(bm, off, False)
    _set_verts(bm, on, True)
    return snapshot(bm), True


def convert(bm):
    """Turn the current selection into whole islands when the mode is switched on."""
    picked = [v for v in bm.verts if v.select]
    done = set()
    for v in picked:
        if v not in done:
            isl = _island(v)
            done |= isl
            _set_verts(bm, isl, True)


# ---------------------------------------------------------------- operators
class KEYOPS_OT_sub_object_mode(bpy.types.Operator):
    bl_idname = "keyops.sub_object_mode"
    bl_label = "Selection Mode"
    bl_description = "Pick what you select"
    bl_options = {'REGISTER', 'UNDO'}

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
        for obj in _edit_meshes(context):
            bm = bmesh.from_edit_mesh(obj.data)
            convert(bm)
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
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
        self.snaps = self._snapshots(context)
        self.quick = self._quick(context)
        self.pending = self.click = self.deselect = False
        self.fast = None  # a short timer, only while a pick waits to be grown
        self.timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        state["running"] = True
        return {'RUNNING_MODAL'}

    def _snapshots(self, context):
        return {o.name: snapshot(bmesh.from_edit_mesh(o.data)) for o in _edit_meshes(context)}

    @staticmethod
    def _quick(context):
        """Cheap per-mesh state: selection totals (kept by Blender) and the active element. When these haven't
        changed, the selection hasn't either, so the full comparison is skipped."""
        out = {}
        for o in _edit_meshes(context):
            me = o.data
            bm = bmesh.from_edit_mesh(me)
            act = bm.select_history.active
            out[o.name] = (me.total_vert_sel, me.total_edge_sel, me.total_face_sel, len(bm.verts),
                           _key(act) if act else None)
        return out

    def _stop_fast(self, context):
        if self.fast is not None:
            context.window_manager.event_timer_remove(self.fast)
            self.fast = None

    def _finish(self, context):
        state["running"] = False
        state["mode"] = "NONE"
        self._stop_fast(context)
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
        changed = False
        quick = self._quick(context)
        for obj in _edit_meshes(context):
            if not self.click and quick.get(obj.name) == self.quick.get(obj.name) and obj.name in self.snaps:
                continue  # nothing changed in this mesh: skip the full comparison
            bm = bmesh.from_edit_mesh(obj.data)
            before = self.snaps.get(obj.name)
            if before is None:
                self.snaps[obj.name] = snapshot(bm)
                continue
            self.snaps[obj.name], did = grow(bm, before, self.click, self.deselect)
            if did:
                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
                changed = True
        self.quick = self._quick(context) if changed else quick
        if changed:
            bpy.ops.ed.undo_push(message="Select Element")

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
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and event.ctrl \
                and not (event.shift or event.alt or event.oskey) and self._ctrl_deselect(context, event):
            self.pending, self.deselect = True, True
            return {'RUNNING_MODAL'}
        if event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}:  # a pick happens on this event: look right after it
            self.pending = True
            # Blender's click-select picks on release (press when select-on-press): both count as a pick
            if event.value in {'PRESS', 'RELEASE'} and event.type == 'LEFTMOUSE' and not self.deselect:
                self.click = True
            if self.fast is None:  # Blender picks after this event: grow it on the very next tick (~10 ms)
                self.fast = context.window_manager.event_timer_add(0.01, window=context.window)
            return {'PASS_THROUGH'}
        if self.pending and event.type in {'TIMER', 'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            self.update(context)
            self.pending = self.click = self.deselect = False
            self._stop_fast(context)
        return {'PASS_THROUGH'}


def draw_mode_row(layout, context):
    """Vertex, Edge, Face, Element as one centered row of mode buttons."""
    sel = context.tool_settings.mesh_select_mode
    extra = active_mode()
    row = layout.row(align=True)
    row.alignment = 'CENTER'
    for mode, on, icon in (("VERT", sel[0], 'VERTEXSEL'), ("EDGE", sel[1], 'EDGESEL'), ("FACE", sel[2], 'FACESEL')):
        row.operator("keyops.sub_object_mode", text="", icon=icon, depress=bool(on) and extra == "NONE").mode = mode
    row.operator("keyops.sub_object_mode", text="", icon=ELEMENT_ICON, depress=extra == "ELEMENT").mode = "ELEMENT"
    return row


ELEMENT_ICON = 'LINKED'  # Element mode picks whole linked parts, like Select Linked


# ---------------------------------------------------------------- the header button
# Blender draws its Vertex / Edge / Face buttons with a C template (template_header_3D_mode) and then, in
# mesh Edit Mode, its editor menus. Drawing the Element button at the start of the editor menus puts it
# right after the three mode buttons, like a fourth mode.

def _draw_editor_menus(cls, context, layout):
    if context.mode == 'EDIT_MESH' and _header_on():
        row = layout.row(align=True)
        row.operator("keyops.sub_object_mode", text="", icon=ELEMENT_ICON,
                     depress=active_mode() == "ELEMENT").mode = "ELEMENT"
    _original_collapsible.__func__(cls, context, layout)


def _header_on():
    from ..utils.pref_utils import feature_on
    try:
        return feature_on("toolkit_panel")
    except Exception:  # noqa: BLE001  prefs not ready (e.g. while registering)
        return False


_original_collapsible = None


def _patch_header():
    global _original_collapsible
    menus = getattr(bpy.types, "VIEW3D_MT_editor_menus", None)
    if menus is None or "draw_collapsible" in menus.__dict__:
        return
    _original_collapsible = bpy.types.Menu.draw_collapsible
    menus.draw_collapsible = classmethod(_draw_editor_menus)


def _unpatch_header():
    menus = getattr(bpy.types, "VIEW3D_MT_editor_menus", None)
    if menus is not None and menus.__dict__.get("draw_collapsible") is not None \
            and getattr(menus.__dict__["draw_collapsible"], "__func__", None) is _draw_editor_menus:
        del menus.draw_collapsible


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
