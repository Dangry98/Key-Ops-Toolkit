"""Re-Bevel: change or remove a bevel that is already in the mesh.

Select the faces of a bevel (the strip of faces that rounds an edge, e.g. with Select Loop or Select Linked
Flat Faces) or just one edge ring across it. The strip's two borders are its rails. For each cross-section of
the strip the operator finds the sharp corner it was made from (where the two faces beside the rails meet),
folds the cross-section back into that corner, and bevels the corner again with the new segment count, width
and profile. With Remove, the corner simply stays sharp.
"""

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty
from mathutils import Vector
from mathutils.geometry import intersect_plane_plane


def _strip_faces(bm):
    faces = {f for f in bm.faces if f.select}
    if not faces:
        # an edge ring across the bevel: the faces along its edges
        edges = [e for e in bm.edges if e.select]
        faces = {f for e in edges for f in e.link_faces}
    return {f for f in faces if len(f.verts) == 4}  # a bevel strip is quads (caps and junctions aren't)


def _border_chains(faces):
    """The strip's border, split into chains at its corners (where the border turns round one face)."""
    border = {e for f in faces for e in f.edges if sum(1 for lf in e.link_faces if lf in faces) == 1}
    at = {}
    for e in border:
        for v in e.verts:
            at.setdefault(v, []).append(e)

    def is_corner(v):
        es = at.get(v, [])
        if len(es) != 2:
            return len(es) > 2
        shared = set(es[0].link_faces) & set(es[1].link_faces) & faces
        return bool(shared)

    chains, left = [], set(border)
    while left:
        e0 = left.pop()
        chain = [e0]
        for end in e0.verts:  # grow both ways until a corner (or back round)
            v, prev = end, e0
            while not is_corner(v):
                nxt = [x for x in at.get(v, []) if x is not prev and x in left]
                if not nxt:
                    break
                prev = nxt[0]
                left.discard(prev)
                chain.append(prev)
                v = prev.other_vert(v)
        chains.append(set(chain))
    return chains


def _bend(chain, faces):
    """How sharply the faces outside the strip meet it along this chain (average angle, radians)."""
    total, n = 0.0, 0
    for e in chain:
        inside = [f for f in e.link_faces if f in faces]
        outside = [f for f in e.link_faces if f not in faces]
        if inside and outside:
            total += inside[0].normal.angle(outside[0].normal, 0.0)
            n += 1
    return total / n if n else 10.0


def _rails(faces):
    """The bevel's two rails: closed borders as they are; on an open strip the two border chains that meet
    their neighbours most smoothly (the ends meet the side faces at a hard angle)."""
    chains = _border_chains(faces)
    if len(chains) > 2:
        chains = sorted(chains, key=lambda c: _bend(c, faces))[:2]
    return chains


def _cross_sections(faces, rail_a, rail_b):
    """For each vertex on rail A: the path across the strip to rail B, through the strip's inner edges."""
    verts_a = {v for e in rail_a for v in e.verts}
    verts_b = {v for e in rail_b for v in e.verts}
    rails = rail_a | rail_b
    inner = {e for f in faces for e in f.edges if e not in rails}  # the strip's ends are cross-sections too
    sections = []
    for va in verts_a:
        starts = [e for e in va.link_edges if e in inner]
        if len(starts) != 1:
            continue  # a corner of the strip (where it ends): no single way across
        path, prev, cur = [va], starts[0], starts[0].other_vert(va)
        ok = True
        while cur not in verts_b:
            path.append(cur)
            nxt = [e for e in cur.link_edges if e in inner and e is not prev
                   and not set(e.link_faces) & set(prev.link_faces) & faces]
            if len(nxt) != 1 or len(path) > 512:
                ok = False
                break
            prev, cur = nxt[0], nxt[0].other_vert(cur)
        if ok:
            path.append(cur)
            sections.append(path)
    return sections


def _outside_normal(v, faces, rails):
    """The face beside the rail at this vertex (only faces along the rail: at the strip's ends the side
    faces touch the vertex too)."""
    ns = [f.normal for e in v.link_edges if e in rails for f in e.link_faces if f not in faces]
    if not ns:
        ns = [f.normal for f in v.link_faces if f not in faces]
    if not ns:
        return None
    n = sum(ns, Vector())
    return n.normalized() if n.length > 1e-9 else None


def _corner(section, faces, rails):
    """Where the faces beside the two rails meet, in this cross-section's plane."""
    va, vb = section[0], section[-1]
    na, nb = _outside_normal(va, faces, rails), _outside_normal(vb, faces, rails)
    mid = sum((v.co for v in section), Vector()) / len(section)
    if na is None or nb is None or abs(na.dot(nb)) > 0.9999:
        return mid
    line = intersect_plane_plane(va.co, na, vb.co, nb)
    if line[0] is None:
        return mid
    p, d = line
    d = d.normalized()
    # the point on the meeting line closest to the cross-section
    return p + d * (mid - p).dot(d)


class KEYOPS_OT_rebevel(bpy.types.Operator):
    """Change the segments, width or profile of a bevel already in the mesh, or remove it. Select the bevel's
    faces (or an edge ring across it)"""
    bl_idname = "keyops.rebevel"
    bl_label = "Re-Bevel"
    bl_options = {'REGISTER', 'UNDO'}

    remove: BoolProperty(name="Remove Bevel", default=False,
                         description="Fold the bevel back into a sharp corner and leave it there") # type: ignore
    segments: IntProperty(name="Segments", default=0, min=0, max=128,
                          description="Segments of the new bevel (0: the same as before)") # type: ignore
    width: FloatProperty(name="Width", default=0.0, min=0.0, soft_max=10.0, subtype='DISTANCE',
                         description="Width of the new bevel (0: the same as before)") # type: ignore
    profile: FloatProperty(name="Profile", default=0.5, min=0.0, max=1.0, subtype='FACTOR') # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "remove")
        col = layout.column()
        col.active = not self.remove
        col.prop(self, "segments")
        col.prop(self, "width")
        col.prop(self, "profile")

    def execute(self, context):
        done, skipped, widths, segs = 0, 0, [], []
        objs = [o for o in context.objects_in_mode_unique_data if o.type == 'MESH']
        corner_edges_by_obj = {}
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            faces = _strip_faces(bm)
            if not faces:
                continue
            rails = _rails(faces)
            if len(rails) != 2:
                skipped += 1
                continue
            sections = _cross_sections(faces, rails[0], rails[1])
            if len(sections) < 2:
                skipped += 1
                continue
            segs.append(len(sections[0]) - 1)
            targets = []
            for sec in sections:
                c = _corner(sec, faces, rails[0] | rails[1])
                widths.append(((sec[0].co - c).length + (sec[-1].co - c).length) * 0.5)
                targets.append((sec, c))
            merged = []
            for sec, c in targets:
                sec = [v for v in sec if v.is_valid]
                if not sec:
                    continue
                bmesh.ops.pointmerge(bm, verts=sec, merge_co=c)
                merged.append(sec[0] if sec[0].is_valid else next((v for v in sec if v.is_valid), None))
            merged = [v for v in merged if v is not None and v.is_valid]
            ms = set(merged)
            corner = [e for v in merged for e in v.link_edges if e.other_vert(v) in ms]
            bmesh.ops.remove_doubles(bm, verts=merged, dist=1e-6)
            for elems in (bm.verts, bm.edges, bm.faces):
                for e in elems:
                    e.select = False
            corner = [e for e in set(corner) if e.is_valid]
            for e in corner:
                e.select = True
                e.smooth = False
            corner_edges_by_obj[obj.name] = len(corner)
            bm.select_flush_mode()
            bm.normal_update()
            bmesh.update_edit_mesh(obj.data, destructive=True)
            done += 1
        if not done:
            self.report({'WARNING'}, "Select the faces of one bevel (a strip with two borders), or an edge ring across it")
            return {'CANCELLED'}
        # objects without a bevel to redo keep nothing selected, so the new bevel touches only the corners
        for obj in objs:
            if obj.name not in corner_edges_by_obj:
                bm = bmesh.from_edit_mesh(obj.data)
                for elems in (bm.verts, bm.edges, bm.faces):
                    for e in elems:
                        e.select = False
                bmesh.update_edit_mesh(obj.data)
        if not self.remove:
            width = self.width or (sum(widths) / len(widths) if widths else 0.1)
            segments = self.segments or (max(segs) if segs else 2)
            bpy.ops.mesh.select_mode(type='EDGE')
            bpy.ops.mesh.bevel(offset=width, offset_type='OFFSET', segments=segments, profile=self.profile,
                               affect='EDGES', clamp_overlap=True)
        msg = "Removed the bevel" if self.remove else "Re-bevelled"
        self.report({'INFO'}, msg + (f" (skipped {skipped} object(s))" if skipped else ""))
        return {'FINISHED'}


def register():
    bpy.utils.register_class(KEYOPS_OT_rebevel)


def unregister():
    bpy.utils.unregister_class(KEYOPS_OT_rebevel)
