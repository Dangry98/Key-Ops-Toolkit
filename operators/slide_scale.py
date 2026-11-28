"""Slide Scale: scale the selection while every vertex slides along one of its edges, like scaling with the
edges as rails. The surface around the selection keeps its shape: a ring of vertices on a curved surface
scales along the surface instead of floating off it.

Each selected vertex picks, once, the edge to an unselected neighbour that points most along the way it would
move (toward or away from the pivot), and moves along that edge as far as plain scaling would move it in that
direction. Vertices with no such edge (inside the selection) scale as usual.
"""

import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector

AXES = {'X': Vector((1, 0, 0)), 'Y': Vector((0, 1, 0)), 'Z': Vector((0, 0, 1))}


def _pivot(context, objs):
    pp = context.tool_settings.transform_pivot_point
    if pp == 'CURSOR':
        return context.scene.cursor.location.copy()
    pts = []
    active = None
    for obj in objs:
        bm = bmesh.from_edit_mesh(obj.data)
        mw = obj.matrix_world
        sel = [mw @ v.co for v in bm.verts if v.select]
        pts += sel
        act = bm.select_history.active
        if pp == 'ACTIVE_ELEMENT' and act is not None and obj == context.edit_object:
            if isinstance(act, bmesh.types.BMVert):
                active = mw @ act.co
            elif isinstance(act, bmesh.types.BMFace):
                active = mw @ act.calc_center_median()
            else:
                active = mw @ ((act.verts[0].co + act.verts[1].co) / 2)
    if not pts:
        return None
    if active is not None:
        return active
    if pp == 'BOUNDING_BOX_CENTER':
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        return (lo + hi) / 2
    return sum(pts, Vector()) / len(pts)


class _Rails:
    """Per selected vertex: where it starts (local and world) and the edges it may slide along.

    A vertex with unselected neighbours (on the border of the selection, or on a selected line) may slide along
    any of its edges, its own selected ones too: a vertex on a selected line keeps to the line (also a diagonal
    line across a cylinder), and a ring on a sphere picks the edges across it. A vertex inside a selected area
    moves freely (its neighbours move too)."""

    def __init__(self, obj):
        self.obj = obj
        self.bm = bmesh.from_edit_mesh(obj.data)
        mw = obj.matrix_world
        self.m3 = mw.to_3x3()
        self.im3 = self.m3.inverted_safe()
        self.items = []
        for v in self.bm.verts:
            if not v.select:
                continue
            co = v.co.copy()
            edges = []
            border = False
            for e in v.link_edges:
                o = e.other_vert(v)
                if not o.select:
                    border = True
                d_world = self.m3 @ (o.co - co)
                if d_world.length > 1e-12:
                    edges.append((o.co - co, d_world))
            self.items.append((v, co, mw @ co, edges if border else []))

    def apply(self, move_of, clamp, slide_only):
        """move_of(world position) -> where plain transforming would put that point (world)."""
        for v, co, w, edges in self.items:
            disp = move_of(w) - w
            dist = disp.length
            if dist < 1e-12:
                v.co = co
                continue
            dn = disp / dist
            best = max(edges, key=lambda e: e[1].normalized().dot(dn), default=None)
            along = best[1].normalized().dot(dn) if best is not None else 0.0
            if best is not None and along > 0.2:
                d_local, d_world = best
                frac = (dist / along) / d_world.length  # as far along the edge as the plain move goes that way
                if clamp:
                    frac = min(frac, 1.0)
                v.co = co + d_local * frac
            elif edges or slide_only:
                v.co = co  # no edge goes that way: moving freely would leave the surface, so it stays
            else:
                v.co = co + self.im3 @ disp  # inside a selected area: its neighbours move too
        self.bm.normal_update()
        bmesh.update_edit_mesh(self.obj.data, loop_triangles=True, destructive=False)

    def restore(self):
        for v, co, *_rest in self.items:
            v.co = co
        bmesh.update_edit_mesh(self.obj.data, loop_triangles=True, destructive=False)


class KEYOPS_OT_slide_scale(bpy.types.Operator):
    """Scale or rotate the selection with every vertex sliding along its edges, so the surface around it keeps
    its shape. Move the mouse, R switches scale / rotate, X / Y / Z for an axis, type a number, click to confirm"""
    bl_idname = "keyops.slide_scale"
    bl_label = "Slide Scale"
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    mode: EnumProperty(name="Mode", default='SCALE', items=(
        ('SCALE', "Scale", "Scale, sliding along the edges"),
        ('ROTATE', "Rotate", "Rotate, sliding along the edges (they follow the existing topology)"))) # type: ignore
    factor: FloatProperty(name="Scale", default=1.0, soft_min=0.0, soft_max=4.0) # type: ignore
    angle: FloatProperty(name="Angle", default=0.0, subtype='ANGLE') # type: ignore
    axis: EnumProperty(name="Axis", default='NONE', items=(
        ('NONE', "Free", "Scale in every direction; rotate around the view direction"), ('X', "X", ""),
        ('Y', "Y", ""), ('Z', "Z", ""))) # type: ignore
    clamp: BoolProperty(name="Clamp", default=True,
                        description="Never slide past the end of an edge (the next vertex)") # type: ignore
    slide_only: BoolProperty(name="Slide Only", default=False,
                             description="Vertices inside a selected area stay put instead of moving freely") # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def _objs(self, context):
        return [o for o in context.objects_in_mode_unique_data if o.type == 'MESH']

    def _setup(self, context):
        objs = self._objs(context)
        pivot = _pivot(context, objs)
        if pivot is None:
            return None
        return pivot, [_Rails(o) for o in objs]

    def _move_of(self, pivot):
        """The plain transform as a function of a world point (scale or rotation around the pivot)."""
        axis = AXES.get(self.axis)
        if self.mode == 'ROTATE':
            rot_axis = axis if axis is not None else getattr(self, "view_axis", Vector((0, 0, 1)))
            rot = Matrix.Rotation(self.angle, 3, rot_axis)
            return lambda w: pivot + rot @ (w - pivot)
        f = self.factor
        if axis is None:
            return lambda w: pivot + (w - pivot) * f
        return lambda w: w + axis * ((w - pivot).dot(axis) * (f - 1.0))

    def execute(self, context):
        setup = self._setup(context)
        if setup is None:
            self.report({'WARNING'}, "Select something to scale")
            return {'CANCELLED'}
        pivot, rails = setup
        for r in rails:
            r.apply(self._move_of(pivot), self.clamp, self.slide_only)
        return {'FINISHED'}

    # ---- interactive
    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return self.execute(context)
        setup = self._setup(context)
        if setup is None:
            self.report({'WARNING'}, "Select something to scale")
            return {'CANCELLED'}
        self.pivot_world, self.rails = setup
        self.typed = ""
        self.factor = 1.0
        self.angle = 0.0
        self.axis = 'NONE'
        region, rv3d = context.region, context.region_data
        self.view_axis = (rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))).normalized()
        p = view3d_utils.location_3d_to_region_2d(region, rv3d, self.pivot_world)
        self.pivot_2d = p if p is not None else Vector((region.width / 2, region.height / 2))
        mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        self.start_dist = max((mouse - self.pivot_2d).length, 10.0)
        self.start_vec = mouse - self.pivot_2d
        self.precise_base = None
        context.window_manager.modal_handler_add(self)
        self._status(context)
        return {'RUNNING_MODAL'}

    def _status(self, context):
        if self.mode == 'ROTATE':
            text = f"Slide Rotate: {self.typed or f'{math.degrees(self.angle):.1f}'}°"
        else:
            text = f"Slide Scale: {self.typed or f'{self.factor:.3f}'}"
        if self.axis != 'NONE':
            text += f"  along {self.axis}"
        context.area.header_text_set(text + "    LMB Confirm   RMB Cancel   R Scale/Rotate   X/Y/Z Axis   Ctrl Snap"
                                     f"   Shift Precise   C Clamp {'on' if self.clamp else 'off'}")

    def _rebuild(self, context):
        pass  # the rails don't depend on the axis any more: nothing to rebuild

    def _update(self, context):
        move_of = self._move_of(self.pivot_world)
        for r in self.rails:
            r.apply(move_of, self.clamp, self.slide_only)
        self._status(context)

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}
        if event.type == 'MOUSEMOVE' and not self.typed and self.mode == 'ROTATE':
            mouse = Vector((event.mouse_region_x, event.mouse_region_y))
            cur = mouse - self.pivot_2d
            if cur.length > 1e-6 and self.start_vec.length > 1e-6:
                a = math.atan2(self.start_vec.x * cur.y - self.start_vec.y * cur.x, self.start_vec.dot(cur))
                # counter-clockwise on screen turns the view-facing side counter-clockwise
                a = -a if self.axis == 'NONE' else a
                if event.ctrl:
                    a = math.radians(round(math.degrees(a) / 5.0) * 5.0)
                self.angle = a
                self._update(context)
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE' and not self.typed:
            mouse = Vector((event.mouse_region_x, event.mouse_region_y))
            f = (mouse - self.pivot_2d).length / self.start_dist
            if event.shift:
                if self.precise_base is None:
                    self.precise_base = (f, self.factor)
                f = self.precise_base[1] + (f - self.precise_base[0]) * 0.1
            else:
                self.precise_base = None
            if event.ctrl:
                f = round(f * 10.0) / 10.0
            self.factor = f
            self._update(context)
        elif event.value == 'PRESS':
            t = event.type
            digits = {'ZERO': "0", 'ONE': "1", 'TWO': "2", 'THREE': "3", 'FOUR': "4", 'FIVE': "5", 'SIX': "6",
                      'SEVEN': "7", 'EIGHT': "8", 'NINE': "9"}
            key = t[7:] if t.startswith('NUMPAD_') else t
            if key in digits or t in {'PERIOD', 'NUMPAD_PERIOD'}:
                self.typed += digits.get(key, ".")
            elif t == 'BACK_SPACE' and self.typed:
                self.typed = self.typed[:-1]
            elif t in {'MINUS', 'NUMPAD_MINUS'}:
                self.typed = self.typed[1:] if self.typed.startswith("-") else "-" + self.typed
            elif t in {'X', 'Y', 'Z'}:
                self.axis = 'NONE' if self.axis == t else t
                self._rebuild(context)
            elif t == 'C':
                self.clamp = not self.clamp
            elif t == 'R':
                self.mode = 'ROTATE' if self.mode == 'SCALE' else 'SCALE'
                self.typed = ""
                self.start_vec = Vector((event.mouse_region_x, event.mouse_region_y)) - self.pivot_2d
            elif t in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE'}:
                context.area.header_text_set(None)
                return {'FINISHED'}
            elif t in {'RIGHTMOUSE', 'ESC'}:
                for r in self.rails:
                    r.restore()
                context.area.header_text_set(None)
                return {'CANCELLED'}
            else:
                return {'RUNNING_MODAL'}
            if self.typed:
                try:
                    value = float(self.typed)
                    if self.mode == 'ROTATE':
                        self.angle = math.radians(value)
                    else:
                        self.factor = value
                except ValueError:
                    pass
            self._update(context)
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(KEYOPS_OT_slide_scale)


def unregister():
    bpy.utils.unregister_class(KEYOPS_OT_slide_scale)
