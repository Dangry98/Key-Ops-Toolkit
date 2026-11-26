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
from mathutils import Vector

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
    """Per vertex: where it starts, and its best rail edge for moving outward and for moving inward."""

    def __init__(self, obj, pivot_world, axis):
        self.obj = obj
        self.bm = bmesh.from_edit_mesh(obj.data)
        mw = obj.matrix_world
        imw = mw.inverted_safe()
        self.pivot = imw @ pivot_world
        # the axis constraint and radial directions are measured in world space, moves happen in local space
        self.items = []
        for v in self.bm.verts:
            if not v.select:
                continue
            co = v.co.copy()
            r = mw @ co - pivot_world
            if axis is not None:
                r = axis * r.dot(axis)
            r_len = r.length
            rails = []
            for e in v.link_edges:
                o = e.other_vert(v)
                if o.select:
                    continue
                d_world = mw.to_3x3() @ (o.co - co)
                if d_world.length < 1e-12:
                    continue
                rails.append((o.co - co, d_world))
            out_rail = in_rail = None
            if r_len > 1e-9:
                rn = r / r_len
                best_out = max(rails, key=lambda rl: rl[1].normalized().dot(rn), default=None)
                best_in = max(rails, key=lambda rl: -rl[1].normalized().dot(rn), default=None)
                if best_out is not None and best_out[1].normalized().dot(rn) > 0.2:
                    out_rail = best_out
                if best_in is not None and -best_in[1].normalized().dot(rn) > 0.2:
                    in_rail = best_in
            free = imw.to_3x3() @ r  # plain scaling direction, local
            self.items.append((v, co, r_len, out_rail, in_rail, free))

    def apply(self, factor, clamp, slide_only):
        for v, co, r_len, out_rail, in_rail, free in self.items:
            delta = (factor - 1.0) * r_len  # how far plain scaling moves it along its radial direction (world)
            rail = out_rail if delta > 0 else in_rail
            if rail is not None and r_len > 1e-9:
                d_local, d_world = rail
                rn = (self.obj.matrix_world.to_3x3() @ free).normalized() if free.length > 1e-12 else d_world.normalized()
                along = d_world.normalized().dot(rn) * (1 if delta > 0 else -1)
                dist = abs(delta) / max(along, 1e-6)  # world distance along the rail
                frac = dist / d_world.length
                if clamp:
                    frac = min(frac, 1.0)
                v.co = co + d_local * frac
            elif slide_only:
                v.co = co
            else:
                v.co = co + free * (factor - 1.0)
        self.bm.normal_update()
        bmesh.update_edit_mesh(self.obj.data, loop_triangles=True, destructive=False)

    def restore(self):
        for v, co, *_rest in self.items:
            v.co = co
        bmesh.update_edit_mesh(self.obj.data, loop_triangles=True, destructive=False)


class KEYOPS_OT_slide_scale(bpy.types.Operator):
    """Scale the selection with every vertex sliding along its edges, so the surface around it keeps its shape.
    Move the mouse to scale, X / Y / Z to scale along one axis, type a number, click to confirm"""
    bl_idname = "keyops.slide_scale"
    bl_label = "Slide Scale"
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    factor: FloatProperty(name="Scale", default=1.0, soft_min=0.0, soft_max=4.0) # type: ignore
    axis: EnumProperty(name="Axis", default='NONE', items=(
        ('NONE', "Free", "Scale in every direction"), ('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", ""))) # type: ignore
    clamp: BoolProperty(name="Clamp", default=True,
                        description="Never slide past the end of an edge (the next vertex)") # type: ignore
    slide_only: BoolProperty(name="Slide Only", default=False,
                             description="Vertices without an edge to slide along stay put instead of scaling") # type: ignore

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
        axis = AXES.get(self.axis)
        return pivot, [_Rails(o, pivot, axis) for o in objs]

    def execute(self, context):
        setup = self._setup(context)
        if setup is None:
            self.report({'WARNING'}, "Select something to scale")
            return {'CANCELLED'}
        _pivot_world, rails = setup
        for r in rails:
            r.apply(self.factor, self.clamp, self.slide_only)
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
        self.axis = 'NONE'
        region, rv3d = context.region, context.region_data
        p = view3d_utils.location_3d_to_region_2d(region, rv3d, self.pivot_world)
        self.pivot_2d = p if p is not None else Vector((region.width / 2, region.height / 2))
        mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        self.start_dist = max((mouse - self.pivot_2d).length, 10.0)
        self.precise_base = None
        context.window_manager.modal_handler_add(self)
        self._status(context)
        return {'RUNNING_MODAL'}

    def _status(self, context):
        text = f"Slide Scale: {self.typed or f'{self.factor:.3f}'}"
        if self.axis != 'NONE':
            text += f"  along {self.axis}"
        context.area.header_text_set(text + "    LMB Confirm   RMB Cancel   X/Y/Z Axis   Ctrl Snap   Shift Precise"
                                     f"   C Clamp {'on' if self.clamp else 'off'}")

    def _rebuild(self, context):
        for r in self.rails:
            r.restore()
        axis = AXES.get(self.axis)
        objs = self._objs(context)
        self.rails = [_Rails(o, self.pivot_world, axis) for o in objs]

    def _update(self, context):
        for r in self.rails:
            r.apply(self.factor, self.clamp, self.slide_only)
        self._status(context)

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}
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
                    self.factor = float(self.typed)
                except ValueError:
                    pass
            self._update(context)
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(KEYOPS_OT_slide_scale)


def unregister():
    bpy.utils.unregister_class(KEYOPS_OT_slide_scale)
