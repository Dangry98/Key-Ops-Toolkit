"""Smart Extrude and Push / Pull for Edit Mode: two tools on one engine.

- Push / Pull (keyops.push_pull, a toolbar tool): CAD style, below.
- Smart Extrude (keyops.smart_extrude, in the Extrude menu): always extrudes, then merges or cuts.

Drag selected faces along their normal:
- Push / Pull: when the faces around the selection stand square to it (a box side, a slot), the faces just
  slide: the walls stretch, no new geometry, like push/pull in CAD.
- Otherwise (or with Push / Pull off) it extrudes, and the extrusion merges with the mesh: pulled out it is
  united with it, pushed in it cuts through it, and no faces are left inside.

How it's built: each update starts from the original mesh. When the extrusion hits nothing else in the mesh
it is a plain extrude (no boolean). Otherwise utils/safe_boolean.py adds or cuts a prism built over the faces:
only the islands it can reach take part, holes get temporary caps so the mesh is closed, the solver is
Manifold (4.5+) or Fast with Exact as the fallback, and every result is checked before it is used. Nothing is
left behind (no modifier, no cutter object), so a finished extrude costs nothing afterwards. (Blender's Python
entry for node tools, geometry.execute_node_group, is gone after 5.0, so a node tool can't be driven from
here on current versions.)

In the toolbar, the Push / Pull tool picks the flat face area under the mouse and you drag it.
"""

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from bpy_extras import view3d_utils
from mathutils import Vector
from mathutils.geometry import intersect_line_line

from ..utils import safe_boolean

TOOL_IDNAME = "mesh.keyops_push_pull_tool"
SQUARE = 0.02  # side faces this close to square (|cos|) count as walls that can stretch


def _region(bm):
    """Selected faces, their area-weighted normal and centre (local space)."""
    faces = [f for f in bm.faces if f.select]
    if not faces:
        return None
    n = sum((f.normal * f.calc_area() for f in faces), Vector())
    if n.length < 1e-12:
        return None
    area = sum(f.calc_area() for f in faces)
    c = sum((f.calc_center_median() * f.calc_area() for f in faces), Vector()) / max(area, 1e-12)
    return faces, n.normalized(), c


def _walls(faces, n):
    """The unselected faces around the selection, and whether they all stand square to it (can stretch)."""
    sel = set(faces)
    border = {e for f in faces for e in f.edges if sum(1 for lf in e.link_faces if lf in sel) == 1}
    walls = {lf for e in border for lf in e.link_faces if lf not in sel}
    square = bool(walls) and all(abs(w.normal.dot(n)) < SQUARE for w in walls)
    return border, walls, square


def _push_limit(faces, n):
    """How far the faces can be pushed in before a wall would turn inside out."""
    sel_verts = {v for f in faces for v in f.verts}
    limit = float("inf")
    for v in sel_verts:
        for e in v.link_edges:
            o = e.other_vert(v)
            if o in sel_verts:
                continue
            depth = (v.co - o.co).dot(n)
            if depth > 1e-9:
                limit = min(limit, depth)
    return limit


def _border(faces):
    """(vert a, vert b) of each border edge of the selection, in the winding of the selected face beside it."""
    sel = set(faces)
    out = []
    for f in faces:
        for loop in f.loops:
            if sum(1 for lf in loop.edge.link_faces if lf in sel) == 1:
                out.append((loop.vert, loop.link_loop_next.vert))
    return out


def _prism_eps(d):
    return max(1e-4, abs(d) * 1e-3)


def _build_prism(faces, n, d):
    """A closed prism over the selected faces: from just behind the surface to d along n (local space). Its far
    cap is tagged so it ends up selected after the boolean."""
    eps = _prism_eps(d)
    sign = 1.0 if d > 0 else -1.0
    pm = bmesh.new()
    tag = pm.faces.layers.int.new(safe_boolean.CAP)
    base, top = {}, {}
    for f in faces:
        for v in f.verts:
            if v not in base:
                base[v] = pm.verts.new(v.co - n * (sign * eps))
                top[v] = pm.verts.new(v.co + n * d)
    for f in faces:
        pm.faces.new([base[v] for v in reversed(f.verts)])
        pm.faces.new([top[v] for v in f.verts])[tag] = 2
    for a, b in _border(faces):
        pm.faces.new([base[a], base[b], top[b], top[a]])[tag] = 3
    bmesh.ops.recalc_face_normals(pm, faces=pm.faces)
    return pm


class _ExtrudeBase:
    """Shared by Smart Extrude and Push / Pull (they differ in the Push / Pull default and where they live)."""
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    distance: FloatProperty(name="Distance", default=0.0, subtype='DISTANCE') # type: ignore
    push_pull: BoolProperty(name="Push / Pull", default=True,
                            description="Where the walls around the faces stand square, just slide the faces "
                                        "(the walls stretch, no new geometry)") # type: ignore
    solver: EnumProperty(name="Solver", default='AUTO', items=(
        ('AUTO', "Auto", "No boolean when the extrude hits nothing; otherwise Manifold (Blender 4.5+) or Fast, "
                         "checked, with Exact as the fallback"),
        ('FAST', "Fast", "Fast boolean, checked, with Exact as the fallback"),
        ('EXACT', "Exact", "Always the Exact boolean: slowest, for difficult meshes"))) # type: ignore
    pick: BoolProperty(options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    pick_flat: BoolProperty(options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.edit_object is not None and context.edit_object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "distance")
        layout.prop(self, "push_pull")
        layout.prop(self, "solver")

    # ------------------------------------------------------------ the result
    def apply(self, context, d):
        """From the original mesh in the edit bmesh: slide or extrude the selection by d. Returns a message."""
        obj = context.edit_object
        bm = bmesh.from_edit_mesh(obj.data)
        reg = _region(bm)
        if reg is None:
            return "Select the faces to extrude"
        faces, n, _c = reg
        if abs(d) < 1e-7:
            return None
        _border_edges, _walls_, square = _walls(faces, n)
        cache = getattr(self, "_cache", None)
        border = _border(faces)
        # square walls: the faces just slide (push / pull), unless that would pass through another part of the
        # mesh (pulled into something, or pushed into something behind the faces): then add / cut instead
        dd = max(d, -_push_limit(faces, n) + 1e-5) if d < 0 else d
        if self.push_pull and square and not safe_boolean.extrude_hits(bm, faces, border, n, dd, cache,
                                                                       sliding_walls=d < 0):
            for v in {v for f in faces for v in f.verts}:
                v.co += n * dd
            bm.normal_update()
            bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=False)
            return None
        if not safe_boolean.extrude_hits(bm, faces, border, n, d, cache):
            safe_boolean.extrude(bm, faces, n, d)  # nothing in the way: a plain extrude, no boolean
            self.used = 'NONE'
            bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
            return None
        prism = _build_prism(faces, n, d)
        rig = getattr(self, "_rig", None)
        own = rig is None
        if own:
            rig = safe_boolean.Rig(context)
        try:
            area = sum(f.calc_area() for f in faces)
            min_change = 0.5 * area * min(_prism_eps(d), abs(d))
            used, err = safe_boolean.boolean(rig, bm, prism, 'UNION' if d > 0 else 'DIFFERENCE', self.solver,
                                             min_change, cache)
        finally:
            prism.free()
            if own:
                rig.remove()
        if err == safe_boolean.SHEET:  # a flat open sheet has no inside: extrude it plainly
            safe_boolean.extrude(bm, faces, n, d)
            used, err = 'NONE', None
        self.used = used
        bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
        return err

    def execute(self, context):
        msg = self.apply(context, self.distance)
        if msg:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}

    # ------------------------------------------------------------ interactive
    def invoke(self, context, event):
        obj = context.edit_object
        if self.pick and not self._pick(context, event):
            return {'PASS_THROUGH'}
        bm = bmesh.from_edit_mesh(obj.data)
        reg = _region(bm)
        if reg is None:
            self.report({'WARNING'}, "Select the faces to extrude")
            return {'CANCELLED'}
        if context.area is None or context.area.type != 'VIEW_3D':
            return self.execute(context)
        faces, n, c = reg
        mw = obj.matrix_world
        self.origin = mw @ c
        self.axis = (mw.to_3x3() @ n).normalized()
        self.n_local = n
        self.scale = (mw.to_3x3() @ n).length  # local units -> world along the normal
        self.backup = bpy.data.meshes.new(".keyops_extrude_backup")
        bm.to_mesh(self.backup)
        self.sel = [f.index for f in bm.faces if f.select]
        # heights of every vertex along the axis: Ctrl snaps to them
        self.heights = sorted({round((mw @ v.co - self.origin).dot(self.axis), 6) for v in bm.verts})
        self.start = self._axis_value(context, event)
        self.typed = ""
        self.d = 0.0
        self.dirty = False
        self.release_confirms = self.pick
        self._rig = safe_boolean.Rig(context)  # reused by every update of the drag
        self._cache = {}
        self.timer = context.window_manager.event_timer_add(0.03, window=context.window)
        context.window_manager.modal_handler_add(self)
        self._status(context)
        return {'RUNNING_MODAL'}

    def _pick(self, context, event):
        """Toolbar tool: the face under the mouse; if it is part of the current selection, the whole selection
        (nothing else gets selected for you). Shift: the whole flat area around the face."""
        mouse = (event.mouse_region_x, event.mouse_region_y)
        ts = context.tool_settings
        mode = tuple(ts.mesh_select_mode)
        bm = bmesh.from_edit_mesh(context.edit_object.data)
        saved = ([v.index for v in bm.verts if v.select], [e.index for e in bm.edges if e.select],
                 [f.index for f in bm.faces if f.select])
        ts.mesh_select_mode = (False, False, True)
        try:
            bpy.ops.view3d.select(location=mouse, deselect_all=True)
        except RuntimeError:
            pass
        bm = bmesh.from_edit_mesh(context.edit_object.data)
        if not any(f.select for f in bm.faces):
            # clicked beside the mesh: put the select mode and selection back as they were
            ts.mesh_select_mode = mode
            bm = bmesh.from_edit_mesh(context.edit_object.data)
            for seq, idx in zip((bm.verts, bm.edges, bm.faces), saved):
                seq.ensure_lookup_table()
                for i in idx:
                    if i < len(seq):
                        seq[i].select = True
            bmesh.update_edit_mesh(context.edit_object.data, loop_triangles=False, destructive=False)
            return False
        hit = [f.index for f in bm.faces if f.select]
        if hit and hit[0] in set(saved[2]) and not self.pick_flat:
            # clicked on the selection: push / pull all of it, as it was selected
            ts.mesh_select_mode = mode
            bm = bmesh.from_edit_mesh(context.edit_object.data)
            for seq, idx in zip((bm.verts, bm.edges, bm.faces), saved):
                seq.ensure_lookup_table()
                for i in idx:
                    if i < len(seq):
                        seq[i].select = True
            bmesh.update_edit_mesh(context.edit_object.data, loop_triangles=False, destructive=False)
        elif self.pick_flat:  # Shift: the whole flat area around the face, like a face in CAD
            bpy.ops.mesh.faces_select_linked_flat(sharpness=0.0175)
        return True

    def _axis_value(self, context, event):
        """Where the mouse ray passes closest to the extrude axis, as a distance along it (world)."""
        region, rv3d = context.region, context.region_data
        mouse = (event.mouse_region_x, event.mouse_region_y)
        o = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
        v = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
        hit = intersect_line_line(self.origin, self.origin + self.axis, o, o + v)
        if hit is None:
            return 0.0
        return (hit[0] - self.origin).dot(self.axis)

    def _restore(self, context):
        obj = context.edit_object
        bm = bmesh.from_edit_mesh(obj.data)
        bm.clear()
        bm.from_mesh(self.backup)
        bm.faces.ensure_lookup_table()
        for i in self.sel:
            bm.faces[i].select_set(True)
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=True)

    def _update(self, context):
        self._restore(context)
        self.distance = self.d / max(self.scale, 1e-12)  # stored in the object's units, for redo
        self.msg = self.apply(context, self.distance)
        self._status(context)

    def _status(self, context):
        text = f"Extrude: {self.typed or f'{self.d:.4f}'} m"
        context.area.header_text_set(text + "    LMB Confirm   RMB Cancel   Ctrl Snap to Vertices   Shift Precise   "
                                            f"P Push/Pull {'on' if self.push_pull else 'off'}")

    def _finish(self, context, cancel=False):
        context.window_manager.event_timer_remove(self.timer)
        self._rig.remove()
        self._rig = None
        if cancel:
            self._restore(context)
        bpy.data.meshes.remove(self.backup)
        context.area.header_text_set(None)
        msg = getattr(self, "msg", None)
        if msg and not cancel:  # the last update failed: say so, and leave the mesh as it was
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        return {'CANCELLED'} if cancel else {'FINISHED'}

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}
        if event.type == 'MOUSEMOVE' and not self.typed:
            d = self._axis_value(context, event) - self.start
            if event.shift:
                d *= 0.1
            if event.ctrl and self.heights:
                d = min(self.heights, key=lambda h: abs(h - d))
            self.d = d
            self.dirty = True
            self._status(context)
        elif event.type == 'TIMER':
            if self.dirty:
                self.dirty = False
                self._update(context)
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self.release_confirms:
            if self.dirty:
                self._update(context)
            return self._finish(context)
        elif event.value == 'PRESS':
            t = event.type
            digits = {'ZERO': "0", 'ONE': "1", 'TWO': "2", 'THREE': "3", 'FOUR': "4", 'FIVE': "5", 'SIX': "6",
                      'SEVEN': "7", 'EIGHT': "8", 'NINE': "9"}
            key = t[7:] if t.startswith('NUMPAD_') else t
            if key in digits or t in {'PERIOD', 'NUMPAD_PERIOD'}:
                self.typed += digits.get(key, ".")
            elif t in {'MINUS', 'NUMPAD_MINUS'}:
                self.typed = self.typed[1:] if self.typed.startswith("-") else "-" + self.typed
            elif t == 'BACK_SPACE' and self.typed:
                self.typed = self.typed[:-1]
            elif t == 'P':
                self.push_pull = not self.push_pull
            elif t in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE'}:
                if self.dirty or self.typed:
                    self._update(context)
                return self._finish(context)
            elif t in {'RIGHTMOUSE', 'ESC'}:
                return self._finish(context, cancel=True)
            else:
                return {'RUNNING_MODAL'}
            if self.typed:
                try:
                    self.d = float(self.typed)
                except ValueError:
                    pass
            self.dirty = True
            self._status(context)
        return {'RUNNING_MODAL'}


class KEYOPS_OT_smart_extrude(_ExtrudeBase, bpy.types.Operator):
    """Extrude the selected faces along their normal by dragging: pulled out the extrusion is united with the
    mesh, pushed in it cuts into it, with no faces left inside"""
    bl_idname = "keyops.smart_extrude"
    bl_label = "Smart Extrude"

    push_pull: BoolProperty(name="Push / Pull", default=False,
                            description="Where the walls around the faces stand square, just slide the faces "
                                        "(the walls stretch, no new geometry)") # type: ignore


class KEYOPS_OT_push_pull(_ExtrudeBase, bpy.types.Operator):
    """Push / Pull like in CAD: drag a face. Walls that stand square to it stretch with it; otherwise it extrudes
    and adds to the mesh going out, cuts into it going in"""
    bl_idname = "keyops.push_pull"
    bl_label = "Push / Pull"


class WorkSpacePushPullTool(bpy.types.WorkSpaceTool):
    """Push / Pull: drag a flat face area out or in"""
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'EDIT_MESH'
    bl_idname = TOOL_IDNAME
    bl_label = "Push / Pull"
    bl_description = ("Drag the face under the mouse (or the selection, when you click on it); Shift: the whole flat "
                      "area. Walls that stand square just stretch, otherwise it extrudes and merges with the mesh "
                      "(out: adds, in: cuts)")
    bl_icon = "ops.mesh.extrude_manifold"
    bl_widget = None
    bl_keymap = (
        ("keyops.push_pull", {"type": 'LEFTMOUSE', "value": 'PRESS'}, {"properties": [("pick", True)]}),
        ("keyops.push_pull", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True},
         {"properties": [("pick", True), ("pick_flat", True)]}),
    )

    def draw_settings(context, layout, tool):
        props = tool.operator_properties("keyops.push_pull")
        layout.prop(props, "push_pull")
        layout.prop(props, "solver")


def menu_extrude(self, context):
    if context.mode == 'EDIT_MESH' and context.tool_settings.mesh_select_mode[2]:
        col = self.layout.column()
        col.operator_context = 'INVOKE_DEFAULT'  # the Extrude menu runs operators directly; this one is a drag
        col.operator(KEYOPS_OT_smart_extrude.bl_idname, text="Smart Extrude", icon='MOD_SOLIDIFY')


def register():
    bpy.utils.register_class(KEYOPS_OT_smart_extrude)
    bpy.utils.register_class(KEYOPS_OT_push_pull)
    bpy.types.VIEW3D_MT_edit_mesh_extrude.prepend(menu_extrude)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_extrude.remove(menu_extrude)
    if hasattr(WorkSpacePushPullTool, "_bl_tool"):
        try:
            bpy.utils.unregister_tool(WorkSpacePushPullTool)
        except Exception:  # noqa: BLE001
            pass
    bpy.utils.unregister_class(KEYOPS_OT_push_pull)
    bpy.utils.unregister_class(KEYOPS_OT_smart_extrude)


def set_enabled(on):
    """The Push / Pull tool sits in the toolbar only while the feature is on."""
    from ..tools.merge_tool import remove_stale_tool
    try:
        if on and not hasattr(WorkSpacePushPullTool, "_bl_tool"):
            remove_stale_tool(WorkSpacePushPullTool)
            bpy.utils.register_tool(WorkSpacePushPullTool, after={"builtin.extrude_region"}, separator=False,
                                    group=False)
        elif not on and hasattr(WorkSpacePushPullTool, "_bl_tool"):
            bpy.utils.unregister_tool(WorkSpacePushPullTool)
    except Exception as e:  # noqa: BLE001
        print(f"Key Ops: could not update the Push / Pull tool in the toolbar: {e}")
