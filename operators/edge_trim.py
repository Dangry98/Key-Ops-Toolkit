"""Make Trim: turn selected edge chains into L-shaped trim strips (two flanges at 90 degrees) with UVs laid
out for a trim sheet.

Select edges, run it, get a trim: each chain gets an L profile swept along it, mitred at the turns so the
flanges keep their width. Its UVs are one piece: U runs along the length (fitted to the sheet, or tiled per
metre), V spans the chosen strip of the trim sheet across the L, split at the corner by flange width, so a
trim texture lines up without any UV editing. Works on open chains and closed loops, on wire edges or edges
on a surface. Which side the L goes on is guessed from the geometry; Flip Side puts it on the other side.
"""

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from mathutils import Vector
from mathutils.geometry import intersect_line_line

from itertools import combinations

Z_UP = Vector((0.0, 0.0, 1.0))


def _chain_plane_normal(verts, closed):
    """The normal of the plane a (loose) chain lies in, pointing up-ish; world up for a straight chain."""
    co = [v.co for v in verts]
    normal = Vector()
    for i in range(len(co) - (0 if closed else 2)):
        a, b, c = co[i], co[(i + 1) % len(co)], co[(i + 2) % len(co)]
        normal += (b - a).cross(c - b)
    if normal.length < 1e-9:
        return Z_UP.copy()
    normal.normalize()
    return -normal if normal.dot(Z_UP) < 0 else normal


def _base_face(edge):
    """The face an upright trim stands on: the one facing most upward (a floor or a top), else any."""
    faces = list(edge.link_faces) if edge else []
    return max(faces, key=lambda f: f.normal.dot(Z_UP)) if faces else None


def _segment_frames(verts, closed, profile):
    """Per edge of the chain: (tangent, up, side, inward). Up comes from the edge's faces: a wrap trim bisects
    them, an upright trim stands on the most upward one. Loose edges use the plane the chain lies in, or world
    up. Inward points from the edge toward its face, or toward the middle of a loose loop: the side the L
    most likely belongs on (used to guess the side)."""
    n = len(verts)
    frames = []
    plane_up = _chain_plane_normal(verts, closed)
    centre = sum((v.co for v in verts), Vector()) / n
    for i in range(n if closed else n - 1):
        v0, v1 = verts[i], verts[(i + 1) % n]
        t = v1.co - v0.co
        t = t.normalized() if t.length > 1e-9 else Vector((1.0, 0.0, 0.0))
        edge = next((e for e in v0.link_edges if e.other_vert(v0) is v1), None)
        mid = (v0.co + v1.co) / 2
        base = _base_face(edge)
        if base is not None and profile == "UPRIGHT":
            up = base.normal.copy()
        else:
            up = Vector()
            for f in (edge.link_faces if edge else ()):
                up += f.normal
        if up.length < 1e-6:  # no faces (loose vertex normals are meaningless): the chain's plane
            up = plane_up.copy()
        up = up - up.project(t)
        if up.length < 1e-6:
            up = Z_UP - Z_UP.project(t)
            if up.length < 1e-6:
                up = Vector((0.0, 1.0, 0.0))
        up.normalize()
        if base is not None:
            inward = base.calc_center_median() - mid
        elif closed:
            inward = centre - mid
        else:
            inward = Vector()
        frames.append((t, up, t.cross(up).normalized(), inward))
    return frames


def guess_side(frames):
    """+1 or -1: the side most of the chain's edges point inward on (toward their face or the loop's middle)."""
    score = sum(side.dot(inward) for _t, _up, side, inward in frames)
    return -1.0 if score < 0 else 1.0


def _pair_score(v, a, b):
    """How well two edges at v continue each other: straight on scores highest; level pairs (a loop around a
    box top) win over vertical ones when the angles tie."""
    da = (a.other_vert(v).co - v.co).normalized()
    db = (b.other_vert(v).co - v.co).normalized()
    level = abs(da.cross(db).normalized().dot(Z_UP)) if da.cross(db).length > 1e-6 else 1.0
    return -da.dot(db) + 0.5 * level


def trim_chains(bm):
    """The selected edges as ordered chains (verts, closed), also when the selection branches: where three or
    more edges meet, the two that continue each other best carry on as one chain and the others end there.
    A box outline (top loop and its upright edges) gives the top loop plus one chain per upright edge."""
    selected = [e for e in bm.edges if e.select]
    at = {}
    for e in selected:
        for v in e.verts:
            at.setdefault(v, []).append(e)
    partner = {}  # (vertex, edge) -> the edge the chain continues on at that vertex
    for v, edges in at.items():
        free = list(edges)
        if len(free) == 2:
            pairs = [tuple(free)]
        else:
            pairs = []
            for a, b in sorted(combinations(free, 2), key=lambda p: -_pair_score(v, *p)):
                if a in free and b in free and _pair_score(v, a, b) > -0.5:
                    pairs.append((a, b))
                    free.remove(a)
                    free.remove(b)
        for a, b in pairs:
            partner[(v, a)], partner[(v, b)] = b, a

    def walk(v, e):
        verts, edges = [v], [e]
        while True:
            v = e.other_vert(v)
            nxt = partner.get((v, e))
            if nxt is None or nxt in edges:
                closed = nxt is not None and nxt is edges[0]
                if not closed:
                    verts.append(v)
                return verts, edges, closed
            verts.append(v)
            edges.append(nxt)
            e = nxt

    used, chains = set(), []
    for e in selected:  # open chains first: start at an end (a vertex where the edge doesn't carry on)
        for v in e.verts:
            if e not in used and (v, e) not in partner:
                verts, edges, _closed = walk(v, e)
                used.update(edges)
                chains.append((verts, False))
    for e in selected:  # what's left are loops
        if e not in used:
            verts, edges, closed = walk(e.verts[0], e)
            used.update(edges)
            chains.append((verts, closed))
    return chains, 0


def _profile(up, side, opts, a, b):
    """The L's three points (flange A end, corner, flange B end) as offsets from the edge, in one frame."""
    corner = up * opts.offset
    if opts.profile == "WRAP":  # fold around the edge: both flanges lie back along the surface, 90 degrees apart
        d1, d2 = (-up + side).normalized(), (-up - side).normalized()
    else:  # stand up: one flange along the normal, one lying on the surface
        d1, d2 = up, side
    return (corner + d1 * a, corner, corner + d2 * b)


def _mitre(p, off_prev, t_prev, off_next, t_next, limit):
    """Where the profile line of the previous edge meets the one of the next edge at point p."""
    a0, b0 = p + off_prev, p + off_next
    if t_prev.cross(t_next).length < 1e-4:  # straight on: no mitre needed
        return (a0 + b0) / 2
    hit = intersect_line_line(a0, a0 + t_prev, b0, b0 + t_next)
    if hit is None:
        return (a0 + b0) / 2
    m = (hit[0] + hit[1]) / 2
    if (m - p).length > limit:  # a very sharp turn: don't shoot off into the distance
        m = p + (m - p).normalized() * limit
    return m


def make_trims(bm, opts):
    """Build an L trim along every selected chain; returns (chains done, branching selections skipped, new faces)."""
    chains, skipped = trim_chains(bm)
    uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
    new_faces = []
    for f in bm.faces:
        f.select = False
    for e in bm.edges:
        e.select = False
    for v in bm.verts:
        v.select = False

    a, b = opts.width_a, (opts.width_b if opts.separate_widths else opts.width_a)
    total = a + b
    v_corner = opts.v_min + (opts.v_max - opts.v_min) * (a / total if total > 0 else 0.5)
    limit = 4.0 * (opts.offset + max(a, b))
    corner_edges = []

    def chain_length(verts, closed):
        n = len(verts)
        return sum((verts[(i + 1) % n].co - verts[i].co).length for i in range(n if closed else n - 1))
    spans = [chain_length(v, c) for v, c in chains]
    all_length = sum(spans) or 1.0
    u_start = 0.0  # Fit to Sheet: the chains share U 0 to 1, end to end, so none overlap and density matches
    for (verts, closed), span in zip(chains, spans):
        n = len(verts)
        frames = _segment_frames(verts, closed, opts.profile)
        sign = guess_side(frames) * (-1.0 if opts.flip_side else 1.0)  # best guess, or the other side
        segs = [(t, up, side * sign) for t, up, side, _inward in frames]
        profiles = [_profile(up, side, opts, a, b) for _t, up, side in segs]
        rows = []  # per point: (flange A end, corner, flange B end)
        for i, v in enumerate(verts):
            prev_s = (i - 1) % len(segs) if (closed or i > 0) else None
            next_s = i if (closed or i < n - 1) else None
            pts = []
            for k in range(3):
                if prev_s is None:
                    pts.append(v.co + profiles[next_s][k])
                elif next_s is None:
                    pts.append(v.co + profiles[prev_s][k])
                else:
                    pts.append(_mitre(v.co, profiles[prev_s][k], segs[prev_s][0], profiles[next_s][k], segs[next_s][0], limit))
            rows.append(tuple(bm.verts.new(p) for p in pts))

        # U along the length, measured on the corner line so both flanges share it: one piece in UV
        lengths = [0.0]
        for i in range(1, n + (1 if closed else 0)):
            lengths.append(lengths[-1] + (rows[i % n][1].co - rows[i - 1][1].co).length)
        total_len = lengths[-1] or 1.0
        if opts.u_mode == "FIT":  # this chain's share of the strip, in proportion to its length
            u_per_metre = (span / all_length) / total_len
            u_base = u_start
            u_start += span / all_length
        else:
            u_per_metre, u_base = opts.u_scale, 0.0
        for i in range(len(lengths) - 1):
            j = (i + 1) % n
            _t, up_s, side_s = segs[i]
            # wrap: faces point away from the edge they cover; upright: into the L, the side you see
            facing = up_s if opts.profile == "WRAP" else up_s + side_s
            u0 = u_base + lengths[i] * u_per_metre + opts.u_offset
            u1 = u_base + lengths[i + 1] * u_per_metre + opts.u_offset
            for k0, k1, v0, v1 in ((0, 1, opts.v_max, v_corner), (1, 2, v_corner, opts.v_min)):
                quad = [rows[i][k0], rows[j][k0], rows[j][k1], rows[i][k1]]
                uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
                face = bm.faces.new(quad)
                face.normal_update()
                if (face.normal.dot(facing) < 0) != opts.flip_normals:
                    face.normal_flip()
                uv_by_vert = {quad[q]: uvs[q] for q in range(4)}  # by vertex, so flipping keeps them in place
                for loop in face.loops:
                    loop[uv].uv = uv_by_vert[loop.vert]
                face.select = True
                face.smooth = opts.smooth
                new_faces.append(face)
            corner = next((e for e in rows[i][1].link_edges if e.other_vert(rows[i][1]) is rows[j][1]), None)
            if corner is not None:
                corner_edges.append(corner)
    for e in corner_edges:  # the L's 90 degree corner stays crisp when shaded smooth
        e.smooth = False
    bm.select_flush(True)
    return len(chains), skipped, new_faces


class KEYOPS_OT_edge_trim(bpy.types.Operator):
    bl_idname = "keyops.edge_trim"
    bl_label = "Make Trim"
    bl_description = ("Turn the selected edges into L-shaped trims (two flanges at 90 degrees) with UVs laid out "
                      "for a trim sheet")
    bl_options = {'REGISTER', 'UNDO'}

    profile: EnumProperty(name="Profile", default="UPRIGHT", items=(
        ("WRAP", "Wrap Edge", "Fold around the edge like a corner moulding: both flanges lie back along the surface"),
        ("UPRIGHT", "Upright", "Stand one flange up from the surface, the other lying on it"))) # type: ignore
    width_a: FloatProperty(name="Width", default=0.05, min=0.0001, soft_max=1.0, subtype='DISTANCE',
                           description="Width of the flanges") # type: ignore
    separate_widths: BoolProperty(name="Different Widths", default=False,
                                  description="Give the second flange its own width") # type: ignore
    width_b: FloatProperty(name="Second Width", default=0.05, min=0.0001, soft_max=1.0, subtype='DISTANCE') # type: ignore
    offset: FloatProperty(name="Offset", default=0.002, min=0.0, soft_max=0.1, subtype='DISTANCE',
                          description="Gap between the trim and the surface, so they don't overlap") # type: ignore
    flip_side: BoolProperty(name="Flip Side", default=False,
                            description="Put the L on the other side of the edges. Key Ops first guesses the side "
                                        "from the geometry: toward the face the edges border, or into a loop") # type: ignore
    flip_normals: BoolProperty(name="Flip Normals", default=False) # type: ignore
    smooth: BoolProperty(name="Smooth Shading", default=True,
                         description="Shade the trim smooth; the corner of the L stays sharp") # type: ignore
    v_min: FloatProperty(name="V Min", default=0.0, soft_min=0.0, soft_max=1.0,
                         description="Bottom of the trim's strip on the trim sheet") # type: ignore
    v_max: FloatProperty(name="V Max", default=0.125, soft_min=0.0, soft_max=1.0,
                         description="Top of the trim's strip on the trim sheet") # type: ignore
    u_mode: EnumProperty(name="Length", items=(
        ("FIT", "Fit to Sheet", "The whole trim spans the sheet once, from left to right (U 0 to 1)"),
        ("TILE", "Tile per Metre", "The texture repeats along the trim, a set number of times per metre"))) # type: ignore
    u_scale: FloatProperty(name="UV per Metre", default=1.0, min=0.0, soft_max=10.0,
                           description="How many times the trim texture repeats per metre of trim") # type: ignore
    u_offset: FloatProperty(name="U Offset", default=0.0, soft_min=-1.0, soft_max=1.0) # type: ignore
    separate: BoolProperty(name="Separate Object", default=True, description="Put the trims in their own object") # type: ignore
    clear_modifiers: BoolProperty(name="Remove Modifiers", default=True,
                                  description="The trim object starts without the modifiers of the mesh it came from") # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.row().prop(self, "profile", expand=True)
        col = layout.column(align=True)
        col.prop(self, "width_a")
        col.prop(self, "separate_widths")
        if self.separate_widths:
            col.prop(self, "width_b")
        layout.prop(self, "offset")
        col = layout.column(heading="Options")
        col.prop(self, "flip_side")
        col.prop(self, "flip_normals")
        col.prop(self, "smooth")
        col.prop(self, "separate")
        sub = col.row()
        sub.active = self.separate
        sub.prop(self, "clear_modifiers")
        layout.label(text="Trim Sheet UVs")
        col = layout.column(align=True)
        col.prop(self, "v_min")
        col.prop(self, "v_max")
        layout.row().prop(self, "u_mode", expand=True)
        col = layout.column(align=True)
        if self.u_mode == "TILE":
            col.prop(self, "u_scale")
        col.prop(self, "u_offset")

    def execute(self, context):
        done = skipped = 0
        objs = [o for o in (context.objects_in_mode_unique_data or [context.edit_object]) if o.type == 'MESH']
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            d, s, _faces = make_trims(bm, self)
            done, skipped = done + d, skipped + s
            bm.normal_update()
            bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
        if not done:
            self.report({'WARNING'}, "Select the edges (or faces) to put trims on")
            return {'CANCELLED'}
        if self.separate:
            before = set(bpy.data.objects)
            bpy.ops.mesh.separate(type='SELECTED')
            if self.clear_modifiers:
                for obj in set(bpy.data.objects) - before:  # the new trim objects
                    obj.modifiers.clear()
        if skipped:
            self.report({'INFO'}, f"Skipped {skipped} selection(s) that branch")
        return {'FINISHED'}


def register_edge_trim():
    bpy.utils.register_class(KEYOPS_OT_edge_trim)


def unregister_edge_trim():
    bpy.utils.unregister_class(KEYOPS_OT_edge_trim)
