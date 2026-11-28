"""Re-Align Rotation: give an object back a rotation that matches its shape.

When an object's rotation has been applied (frozen), its mesh sits turned inside an unrotated object: the
bounding box is loose and rotating it along its own axes is awkward. This finds the orientation the shape
really has and turns the object to it, while the mesh is turned back the other way, so nothing moves in the
scene: only the object's axes (and its rotation values) change.

The orientation comes from the selected faces (their normal is up, their longest edge is X), or, without a
selection, from the tightest box around the mesh, snapped to its largest flat area. The axis that was closest
to up stays up, so objects never end up upside down.
"""

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty
from mathutils import Matrix, Vector

from ..utils.geometry_math_utils import min_oriented_box


def _flat_area_normal(me):
    """The normal of the mesh's largest flat area (faces pointing the same way, by total area), or None."""
    groups = []
    for p in me.polygons:
        n = p.normal
        for g in groups:
            if g[0].dot(n) > 0.999:
                g[1] += p.area
                break
        else:
            groups.append([n.copy(), p.area])
    if not groups:
        return None
    n, area = max(groups, key=lambda g: g[1])
    total = sum(g[1] for g in groups)
    return n if total > 0 and area / total > 0.05 else None


def _orthonormal(z, x_hint):
    z = z.normalized()
    x = x_hint - z * x_hint.dot(z)
    if x.length < 1e-6:
        x = z.orthogonal()
    x.normalize()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def _from_selection(me):
    """Rotation (local space) from the selected faces: average normal up, longest selected edge along X."""
    faces = [p for p in me.polygons if p.select]
    if not faces:
        return None
    n = sum((p.normal * p.area for p in faces), Vector())
    area = sum(p.area for p in faces)
    if n.length < 0.1 * area or n.length < 1e-9:  # faces facing every way (a whole closed part): no up
        return None
    best, best_len = None, -1.0
    for p in faces:
        vs = [me.vertices[i].co for i in p.vertices]
        for i in range(len(vs)):
            d = vs[(i + 1) % len(vs)] - vs[i]
            if d.length > best_len:
                best, best_len = d, d.length
    return _orthonormal(n, best if best is not None else Vector((1, 0, 0)))


def _auto(me):
    """Rotation (local space) of the tightest box, with one axis snapped to the largest flat area."""
    pts = [v.co for v in me.vertices]
    if len(pts) < 2:
        return None
    _c, rot, _s = min_oriented_box(pts)
    axes = [rot.col[i].to_3d() for i in range(3)]
    flat = _flat_area_normal(me)
    if flat is not None:
        k = max(range(3), key=lambda i: abs(axes[i].dot(flat)))
        if abs(axes[k].dot(flat)) > math.cos(math.radians(10)):  # close: lock that axis exactly to the face
            sign = 1.0 if axes[k].dot(flat) > 0 else -1.0
            other = axes[(k + 1) % 3]
            r = _orthonormal(flat * sign, other)
            # put the snapped axis back in slot k
            cols = [r.col[0].to_3d(), r.col[1].to_3d(), r.col[2].to_3d()]
            order = {2: (0, 1, 2), 0: (2, 0, 1), 1: (1, 2, 0)}[k]
            axes = [cols[order[0]], cols[order[1]], cols[order[2]]]
    return Matrix(axes).transposed()


def _keep_upright(rot, current_world_rot):
    """Reorder / flip the box axes so the one closest to the object's current up (world Z) is Z and the one
    closest to its current X is X: the object turns as little as possible and never goes upside down."""
    axes = [rot.col[i].to_3d() for i in range(3)]
    world = [current_world_rot @ a for a in axes]
    up = Vector((0, 0, 1))
    z = max(range(3), key=lambda i: abs(world[i].dot(up)))
    zs = 1.0 if world[z].dot(up) >= 0 else -1.0
    cur_x = current_world_rot @ Vector((1, 0, 0))
    rest = [i for i in range(3) if i != z]
    x = max(rest, key=lambda i: abs(world[i].dot(cur_x)))
    xs = 1.0 if world[x].dot(cur_x) >= 0 else -1.0
    ax_z, ax_x = axes[z] * zs, axes[x] * xs
    return Matrix((ax_x, ax_z.cross(ax_x), ax_z)).transposed()


class KEYOPS_OT_realign_rotation(bpy.types.Operator):
    """Turn the object's axes to match its shape (after its rotation was applied), without moving the mesh.
    Uses the selected faces when there are any, else the tightest box and largest flat area"""
    bl_idname = "keyops.realign_rotation"
    bl_label = "Re-Align Rotation"
    bl_options = {'REGISTER', 'UNDO'}

    source: EnumProperty(name="From", default='AUTO', items=(
        ('AUTO', "Auto", "In Edit Mode the selected faces, if some are; otherwise the shape (tightest box, largest "
                         "flat area)"),
        ('SHAPE', "Shape", "The tightest box around the mesh, snapped to its largest flat area"),
        ('SELECTION', "Selected Faces", "Up is the selected faces' normal, X their longest edge (also from Object "
                                        "Mode: the faces last selected in Edit Mode)"))) # type: ignore
    turn: IntProperty(name="Turn", default=0, min=-3, max=3,
                      description="Turn the new axes around their up axis in 90 degree steps") # type: ignore
    flip: BoolProperty(name="Flip Up", default=False, description="Turn the new axes upside down") # type: ignore
    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT', 'EDIT_MESH'} and any(o.type == 'MESH' for o in context.selected_objects)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "source")
        layout.prop(self, "turn")
        layout.prop(self, "flip")

    def execute(self, context):
        was_edit = context.mode == 'EDIT_MESH'
        if was_edit:
            bpy.ops.object.mode_set(mode='OBJECT')  # the selection and mesh are up to date in Object Mode
        done, skipped = 0, 0
        seen = set()
        for obj in [o for o in context.selected_objects if o.type == 'MESH']:
            me = obj.data
            if me in seen or obj.library or me.library:
                skipped += 1 if (obj.library or me.library) else 0
                continue
            seen.add(me)
            rot = None
            # Auto reads the face selection only in Edit Mode, where you can see it, and only when it is part of
            # the mesh (a fresh primitive has every face selected); Selected Faces reads it in any mode
            selected = sum(1 for p in me.polygons if p.select)
            if self.source == 'SELECTION' or (self.source == 'AUTO' and was_edit and 0 < selected < len(me.polygons)):
                rot = _from_selection(me)
            if rot is None and self.source in {'AUTO', 'SHAPE'}:
                rot = _auto(me)
            if rot is None:
                skipped += 1
                continue
            mw = obj.matrix_world
            loc, wrot, scale = mw.decompose()
            rot = _keep_upright(rot, wrot.to_matrix())
            if self.flip:
                rot = rot @ Matrix.Rotation(math.pi, 3, 'X')
            if self.turn:
                rot = rot @ Matrix.Rotation(math.radians(90 * self.turn), 3, 'Z')
            self._apply(context, obj, rot)
            if obj.data is not me:  # it got its own mesh: the others still sharing the old one get their turn
                seen.discard(me)
            done += 1
        if was_edit:
            bpy.ops.object.mode_set(mode='EDIT')
        if not done:
            self.report({'WARNING'}, "Nothing to re-align (select mesh objects)")
            return {'CANCELLED'}
        msg = f"Re-aligned {done} object{'s' if done != 1 else ''}"
        self.report({'INFO'}, msg + (f", skipped {skipped}" if skipped else ""))
        return {'FINISHED'}

    def _apply(self, context, obj, rot):
        """Turn obj (and every object sharing its mesh) by rot in its own space; the mesh turns back."""
        me = obj.data
        users = [o for o in bpy.data.objects if o.data == me]
        sx, sy, sz = obj.scale
        uniform = abs(sx - sy) < 1e-6 and abs(sy - sz) < 1e-6
        r4 = rot.to_4x4()
        if not uniform:
            # a turn inside an unevenly scaled object would shear it: bake the scale into the mesh first. Objects
            # sharing the mesh with a different scale can't share the baked mesh: this one gets its own copy
            if any((Vector(o.scale) - Vector(obj.scale)).length > 1e-6 for o in users):
                obj.data = me = me.copy()
                users = [obj]
            s4 = Matrix.Diagonal((*obj.scale, 1.0))
            me.transform(s4)
            for o in users:
                for child in o.children:
                    child.matrix_parent_inverse = s4 @ child.matrix_parent_inverse
                o.scale = (1.0, 1.0, 1.0)
            context.view_layer.update()
        me.transform(r4.inverted())
        me.update()
        for o in users:
            o.matrix_world = o.matrix_world @ r4
            for child in o.children:
                child.matrix_parent_inverse = r4.inverted() @ child.matrix_parent_inverse


def register():
    bpy.utils.register_class(KEYOPS_OT_realign_rotation)


def unregister():
    bpy.utils.unregister_class(KEYOPS_OT_realign_rotation)
