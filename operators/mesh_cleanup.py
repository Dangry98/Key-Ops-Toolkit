"""Clean Up: fix the usual mesh problems in one go and report what was fixed.

Merges doubles, removes degenerate and loose geometry, dissolves redundant edges on flat areas and
redundant vertices on straight edges, makes normals consistent, then optionally selects what still
needs a look (non-manifold edges, non-planar faces, n-gons or triangles) and warns when the mesh is
still non-manifold. Works on the whole mesh (or only the selection) in Edit Mode, and on every
selected mesh object in Object Mode.

Step order and the near-zero default angle: flat edges are
dissolved before straight vertices, so the vertices those dissolves leave behind are cleaned too,
and only geometry that adds no shape at all is dissolved.
"""

import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty


def _straight(v, angle):
    """A vertex with two edges that make a (nearly) straight line."""
    if len(v.link_edges) != 2:
        return False
    a, b = (e.other_vert(v).co - v.co for e in v.link_edges)
    if a.length < 1e-12 or b.length < 1e-12:
        return True
    return math.pi - a.angle(b) <= angle


def _non_planar(face, tolerance):
    if len(face.verts) < 4:
        return False
    n, c = face.normal, face.calc_center_median()
    return any(abs((v.co - c).dot(n)) > tolerance for v in face.verts)


def _problem_edge(e, boundary):
    """Edges that make a mesh non-manifold: more than two faces, wire edges, and optionally open borders."""
    return len(e.link_faces) > 2 or e.is_wire or (boundary and e.is_boundary)


def _counts(bm):
    return len(bm.verts), len(bm.edges), len(bm.faces)


def clean(bm, scope, opts, select=True):
    """Run the chosen steps on one bmesh; returns (step counts, removed (v, e, f), problem edge count, found)."""
    report = {}
    before = _counts(bm)
    bm.normal_update()
    if scope == "SELECTED" and not any(v.select for v in bm.verts):
        scope = "ALL"  # nothing selected: clean the whole mesh

    def in_scope(elems):
        return [e for e in elems if e.is_valid and (scope == "ALL" or e.select)]

    if opts.doubles:
        n = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=in_scope(bm.verts), dist=opts.distance)
        report["doubles merged"] = n - len(bm.verts)

    if opts.degenerate:
        n = len(bm.edges) + len(bm.faces)
        bmesh.ops.dissolve_degenerate(bm, edges=in_scope(bm.edges), dist=opts.distance)
        report["degenerate removed"] = n - len(bm.edges) - len(bm.faces)

    if opts.loose:
        n = sum(_counts(bm))
        if opts.loose_faces:
            # faces not joined to anything by a manifold edge
            faces = [f for f in in_scope(bm.faces) if not any(e.is_manifold for e in f.edges)]
            if faces:
                bmesh.ops.delete(bm, geom=faces, context='FACES_ONLY')
        if opts.loose_edges:
            edges = [e for e in in_scope(bm.edges) if not e.link_faces]
            if edges:
                bmesh.ops.delete(bm, geom=edges, context='EDGES')  # also removes the verts left alone
        if opts.loose_verts:
            verts = [v for v in in_scope(bm.verts) if not v.link_edges]
            if verts:
                bmesh.ops.delete(bm, geom=verts, context='VERTS')
        report["loose removed"] = n - sum(_counts(bm))

    if opts.redundant_edges:
        bm.normal_update()
        edges = [e for e in in_scope(bm.edges) if e.is_manifold and not e.seam
                 and not (opts.keep_sharp and not e.smooth) and e.calc_face_angle(math.pi) <= opts.angle]
        if edges:
            n = len(bm.edges)
            ends = {v for e in edges for v in e.verts}
            bmesh.ops.dissolve_edges(bm, edges=edges, use_verts=False, use_face_split=False)
            # vertices left in the middle of a straight face side add nothing; corners stay
            left = [v for v in ends if v.is_valid and _straight(v, opts.angle)]
            if left:
                bmesh.ops.dissolve_verts(bm, verts=left, use_face_split=False, use_boundary_tear=False)
            report["flat edges dissolved"] = n - len(bm.edges)

    if opts.redundant_verts:
        verts = [v for v in in_scope(bm.verts) if _straight(v, opts.angle) and
                 (v.link_faces or not opts.keep_wire_ends)]
        if verts:
            n = len(bm.verts)
            bmesh.ops.dissolve_verts(bm, verts=verts, use_face_split=False, use_boundary_tear=False)
            report["straight vertices dissolved"] = n - len(bm.verts)

    bm.normal_update()
    if opts.normals:
        faces = in_scope(bm.faces)
        old = {f: f.normal.copy() for f in faces}
        bmesh.ops.recalc_face_normals(bm, faces=faces)
        bm.normal_update()
        report["normals flipped"] = sum(1 for f, n in old.items() if f.is_valid and f.normal.dot(n) < 0)

    problems = sum(1 for e in bm.edges if _problem_edge(e, opts.boundary))

    found = 0
    if select and opts.select != "NONE":
        for elems in (bm.faces, bm.edges, bm.verts):
            for e in elems:
                e.select = False
        if opts.select == "NON_MANIFOLD":
            hits = [e for e in bm.edges if _problem_edge(e, opts.boundary)]
        elif opts.select == "NON_PLANAR":
            hits = [f for f in bm.faces if _non_planar(f, opts.planar_tolerance)]
        elif opts.select == "NGONS":
            hits = [f for f in bm.faces if len(f.verts) > 4]
        else:
            hits = [f for f in bm.faces if len(f.verts) == 3]
        # select_set also selects the verts: Blender syncs edit-mode selection from them,
        # so setting only the edge/face flag gets lost
        bm.select_mode = {'EDGE'} if opts.select == "NON_MANIFOLD" else {'FACE'}
        for e in hits:
            e.select_set(True)
        bm.select_flush_mode()
        found = len(hits)

    after = _counts(bm)
    removed = tuple(b - a for b, a in zip(before, after))
    return report, removed, problems, found


class KEYOPS_OT_mesh_cleanup(bpy.types.Operator):
    bl_idname = "keyops.mesh_cleanup"
    bl_label = "Clean Up"
    bl_description = ("Merge doubles, remove degenerate and loose geometry, dissolve redundant edges and vertices, "
                      "fix normals, then select what still needs a look")
    bl_options = {'REGISTER', 'UNDO'}

    scope: EnumProperty(name="Clean", default="ALL", items=(
        ("ALL", "Whole Mesh", "The whole mesh"),
        ("SELECTED", "Selected", "Only the selected part of the mesh (Edit Mode). With nothing selected, the whole mesh"),
    )) # type: ignore
    doubles: BoolProperty(name="Merge Doubles", default=True) # type: ignore
    degenerate: BoolProperty(name="Degenerate", default=True,
                             description="Remove zero-length edges and zero-area faces") # type: ignore
    distance: FloatProperty(name="Merge Distance", default=0.0001, min=0.0, soft_max=0.01, subtype='DISTANCE', precision=5) # type: ignore
    loose: BoolProperty(name="Loose", default=True, description="Delete geometry that isn't part of the surface") # type: ignore
    loose_verts: BoolProperty(name="Verts", default=True, description="Delete vertices without edges") # type: ignore
    loose_edges: BoolProperty(name="Edges", default=True, description="Delete edges without faces") # type: ignore
    loose_faces: BoolProperty(name="Faces", default=False,
                              description="Delete faces that aren't joined to other faces by a manifold edge") # type: ignore
    redundant_edges: BoolProperty(name="Flat Edges", default=False,
                                  description="Dissolve edges between faces that lie flat, merging them into n-gons") # type: ignore
    keep_sharp: BoolProperty(name="Keep Sharp", default=True,
                             description="Don't dissolve edges marked sharp, even on flat areas. Seams are always kept") # type: ignore
    redundant_verts: BoolProperty(name="Straight Vertices", default=True,
                                  description="Dissolve vertices with two edges that sit on a straight line and add no shape") # type: ignore
    keep_wire_ends: BoolProperty(name="Keep Wire Points", default=True,
                                 description="Keep straight vertices on loose wire edges (curves made of edges)") # type: ignore
    angle: FloatProperty(name="Angle", default=math.radians(0.001), min=0.0, max=math.radians(30), subtype='ANGLE',
                         precision=3, step=1,
                         description="How far from straight or flat still counts as redundant. "
                                     "Keep it tiny, or dense curves and smooth surfaces get dissolved") # type: ignore
    normals: BoolProperty(name="Fix Normals", default=True, description="Make face normals point outside, consistently") # type: ignore
    select: EnumProperty(name="Select Issue", default="NON_MANIFOLD", items=(
        ("NONE", "Nothing", "Keep the selection"),
        ("NON_MANIFOLD", "Non-Manifold", "Edges with more than two faces, and loose edges"),
        ("NON_PLANAR", "Non-Planar", "Faces whose corners don't lie in one plane"),
        ("NGONS", "N-gons", "Faces with more than four corners"),
        ("TRIS", "Triangles", "Faces with three corners"))) # type: ignore
    boundary: BoolProperty(name="Include Open Borders", default=False,
                           description="Count boundary edges (holes, open borders) as non-manifold too") # type: ignore
    planar_tolerance: FloatProperty(name="Planar Tolerance", default=0.001, min=0.0, soft_max=0.1, subtype='DISTANCE',
                                    precision=4) # type: ignore

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in (context.selected_objects or [context.active_object]) if o)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        edit = context.mode == 'EDIT_MESH'
        if edit:
            layout.row().prop(self, "scope", expand=True)

        col = layout.column(heading="Fix")
        col.prop(self, "doubles")
        col.prop(self, "degenerate")
        sub = col.row()
        sub.active = self.doubles or self.degenerate
        sub.prop(self, "distance")

        col.prop(self, "loose")
        row = col.row(align=True)
        row.active = self.loose
        row.prop(self, "loose_verts", toggle=True)
        row.prop(self, "loose_edges", toggle=True)
        row.prop(self, "loose_faces", toggle=True)

        col.prop(self, "redundant_edges")
        sub = col.row()
        sub.active = self.redundant_edges
        sub.prop(self, "keep_sharp")
        col.prop(self, "redundant_verts")
        sub = col.row()
        sub.active = self.redundant_verts
        sub.prop(self, "keep_wire_ends")
        sub = col.row()
        sub.active = self.redundant_edges or self.redundant_verts
        sub.prop(self, "angle")

        col.prop(self, "normals")

        col = layout.column()
        col.prop(self, "boundary")
        if edit:
            col.prop(self, "select")
            sub = col.column()
            sub.active = self.select != "NONE"
            if self.select == "NON_PLANAR":
                sub.prop(self, "planar_tolerance")

    def execute(self, context):
        totals, removed, problems, found = {}, [0, 0, 0], 0, 0

        def add(result):
            nonlocal problems, found
            report, rem, prob, hit = result
            for k, v in report.items():
                totals[k] = totals.get(k, 0) + v
            for i, v in enumerate(rem):
                removed[i] += v
            problems += prob
            found += hit

        edit = context.mode == 'EDIT_MESH'
        if edit:
            objs = [o for o in (context.objects_in_mode_unique_data or [context.edit_object]) if o and o.type == 'MESH']
            if self.select == "NON_MANIFOLD":
                mode = (False, True, False)
            elif self.select == "NONE":
                mode = None
            else:
                mode = (False, False, True)
            if mode:
                # results only show in the matching select mode
                context.tool_settings.mesh_select_mode = mode
            for obj in objs:
                bm = bmesh.from_edit_mesh(obj.data)
                add(clean(bm, self.scope, self))
                bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
        else:
            objs = {o.data: o for o in context.selected_objects if o.type == 'MESH'}.values()
            for obj in objs:
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                add(clean(bm, "ALL", self, select=False))
                bm.to_mesh(obj.data)
                bm.free()
                obj.data.update()

        fixed = [f"{v} {k}" for k, v in totals.items() if v]
        v, e, f = removed
        net = ", ".join(f"{n} {label}" for n, label in ((v, "verts"), (e, "edges"), (f, "faces")) if n > 0)
        msg = "Clean Up: " + (", ".join(fixed) if fixed else "nothing to fix")
        if net:
            msg += f" (removed {net})"
        if edit and self.select not in ("NONE", "NON_MANIFOLD") and found:
            msg += f". Selected {found} faces"
        if problems:
            self.report({'WARNING'}, msg + f". {problems} non-manifold edges left")
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


def register():
    bpy.utils.register_class(KEYOPS_OT_mesh_cleanup)


def unregister():
    bpy.utils.unregister_class(KEYOPS_OT_mesh_cleanup)
