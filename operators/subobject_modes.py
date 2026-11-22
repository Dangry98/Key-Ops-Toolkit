"""Border and Element modes for the Edit Toolkit, next to Vertex, Edge and Face.

They work as selection modes rather than one-off commands: while Border is on, picking an edge on an open
border picks the whole border; while Element is on, picking any part of a mesh island picks the whole island
(and deselecting a part, or Ctrl+clicking it, deselects the island). Turning a mode on also converts what is selected already.
The mode ends when you pick Vertex, Edge or Face, change the select mode another way, or leave Edit Mode.
"""

import bmesh
import bpy
from bpy.props import EnumProperty

MODES = ("VERT", "EDGE", "FACE")

# module state: the active extra mode ("NONE", "BORDER" or "ELEMENT") and whether its watcher runs
state = {"mode": "NONE", "running": False}


def active_mode():
    return state["mode"] if state["running"] else "NONE"


def _edit_meshes(context):
    objs = context.objects_in_mode_unique_data or ([context.edit_object] if context.edit_object else [])
    return [o for o in objs if o and o.type == 'MESH']


# ---------------------------------------------------------------- selection growing
def _border_loop(edge):
    """All edges of the open border `edge` lies on (walks from boundary edge to boundary edge)."""
    loop, todo = {edge}, [edge]
    while todo:
        e = todo.pop()
        for v in e.verts:
            for nxt in v.link_edges:
                if nxt not in loop and nxt.is_boundary:
                    loop.add(nxt)
                    todo.append(nxt)
    return loop


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


def snapshot(bm, mode):
    """What a mode compares against: selected edges for Border, selected vertices for Element, plus counts so
    edits that add or remove geometry (extrude, delete...) are not taken for a selection change."""
    elems = bm.edges if mode == "BORDER" else bm.verts
    return (len(bm.verts), len(bm.edges), len(bm.faces)), {e.index for e in elems if e.select}


def grow(bm, mode, before):
    """Grow what was newly picked to a whole border/island, and shrink what was unpicked the same way.
    Returns the new snapshot and whether anything changed."""
    counts, old = before
    now = snapshot(bm, mode)
    if now[0] != counts:  # the geometry changed: nothing to grow, start over from here
        return now, False
    added, removed = now[1] - old, old - now[1]
    if not added and not removed:
        return now, False
    if mode == "BORDER":
        for f in bm.faces:  # first: deselecting a face also deselects its edges
            if f.select:
                f.select = False
        bm.edges.ensure_lookup_table()
        for i in removed:
            e = bm.edges[i]
            if e.is_boundary:
                for le in _border_loop(e):
                    le.select = False
        for i in added:
            e = bm.edges[i]
            if e.is_boundary and e.select:
                for le in _border_loop(e):
                    le.select = True
        for v in bm.verts:  # vertices follow their edges (setting False would deselect edges, so only when bare)
            if v.select != any(e.select for e in v.link_edges):
                v.select = not v.select
    else:
        bm.verts.ensure_lookup_table()
        done = set()
        for i in removed:
            v = bm.verts[i]
            if v not in done:
                isl = _island(v)
                done |= isl
                _set_verts(bm, isl, False)
        for i in added:
            v = bm.verts[i]
            if v not in done and v.select:
                isl = _island(v)
                done |= isl
                _set_verts(bm, isl, True)
    return snapshot(bm, mode), True


def convert(bm, mode):
    """Turn the current selection into whole borders / islands when a mode is switched on."""
    if mode == "BORDER":
        edges = {e for e in bm.edges if e.select}
        faces = [f for f in bm.faces if f.select]
        if faces:  # a selected region: its outline, like Select Boundary Loop
            outline = {e for f in faces for e in f.edges if sum(1 for lf in e.link_faces if lf.select) == 1}
            edges = outline
        keep = set()
        for e in edges:
            keep |= _border_loop(e) if e.is_boundary else {e}
        for f in bm.faces:
            f.select = False
        for v in bm.verts:
            v.select = False
        for e in keep:
            e.select = True  # selects its two vertices too
    else:
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
        ("BORDER", "Border", "Border mode: picking an edge on an open border picks the whole border.\n"
                             "Click again to turn it off"),
        ("ELEMENT", "Element", "Element mode: picking any part of a mesh island picks the whole island.\n"
                               "Click again to turn it off"))) # type: ignore

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
        if self.mode == "BORDER":
            bpy.ops.mesh.select_mode(type='EDGE')
        for obj in _edit_meshes(context):
            bm = bmesh.from_edit_mesh(obj.data)
            convert(bm, self.mode)
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        state["mode"] = self.mode
        if not state["running"] and context.window and not bpy.app.background:
            bpy.ops.keyops.sub_object_watch('INVOKE_DEFAULT')
        return {'FINISHED'}


class KEYOPS_OT_sub_object_watch(bpy.types.Operator):
    """Keeps Border/Element mode working: grows each new pick to its whole border or island."""
    bl_idname = "keyops.sub_object_watch"
    bl_label = "Border/Element Mode"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        self.select_mode = tuple(context.tool_settings.mesh_select_mode)
        self.mode = state["mode"]
        self.snaps = self._snapshots(context)
        self.pending = False
        self.timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        state["running"] = True
        return {'RUNNING_MODAL'}

    def _snapshots(self, context):
        return {o.name: snapshot(bmesh.from_edit_mesh(o.data), self.mode) for o in _edit_meshes(context)}

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
        sel = tuple(context.tool_settings.mesh_select_mode)
        if state["mode"] != self.mode:  # switched straight from Border to Element or back
            self.mode, self.select_mode = state["mode"], sel
            self.snaps = self._snapshots(context)
            return False
        return sel != self.select_mode

    def update(self, context):
        changed = False
        for obj in _edit_meshes(context):
            bm = bmesh.from_edit_mesh(obj.data)
            before = self.snaps.get(obj.name)
            if before is None:
                self.snaps[obj.name] = snapshot(bm, self.mode)
                continue
            self.snaps[obj.name], did = grow(bm, self.mode, before)
            if did:
                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
                changed = True
        if changed:
            bpy.ops.ed.undo_push(message="Select " + self.mode.title())

    def _ctrl_deselect(self, context, event):
        """Ctrl+click deselects what's under the mouse (Blender's own Ctrl+click picks a shortest path, which
        would add to the selection); the mode then deselects its whole island or border."""
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
            self.pending = True
            return {'RUNNING_MODAL'}
        if event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}:  # a pick happens on this event: look on the next one
            self.pending = True
            return {'PASS_THROUGH'}
        if self.pending and event.type in {'TIMER', 'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            self.pending = False
            self.update(context)
        return {'PASS_THROUGH'}


def draw_mode_row(layout, context):
    """Vertex, Edge, Face, Border, Element as one row of mode buttons."""
    sel = context.tool_settings.mesh_select_mode
    extra = active_mode()
    row = layout.row(align=True)
    for mode, on, icon in (("VERT", sel[0], 'VERTEXSEL'), ("EDGE", sel[1], 'EDGESEL'), ("FACE", sel[2], 'FACESEL')):
        row.operator("keyops.sub_object_mode", text="", icon=icon, depress=bool(on) and extra == "NONE").mode = mode
    row.operator("keyops.sub_object_mode", text="", icon='MESH_CAPSULE', depress=extra == "BORDER").mode = "BORDER"
    row.operator("keyops.sub_object_mode", text="", icon='SNAP_VOLUME', depress=extra == "ELEMENT").mode = "ELEMENT"
    return row


classes = (KEYOPS_OT_sub_object_mode, KEYOPS_OT_sub_object_watch)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    state["mode"] = "NONE"
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
