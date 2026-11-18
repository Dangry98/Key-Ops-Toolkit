"""Clean Up: fix the usual mesh problems in one go and report what was fixed.

Merges doubles, removes degenerate and loose geometry, dissolves redundant vertices on straight edges
and redundant edges on flat areas, makes normals consistent, then optionally selects what still needs
a look (non-manifold edges, non-planar faces, n-gons or triangles). Works on the selection or the
whole mesh in Edit Mode, and on every selected mesh object in Object Mode.
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


def clean(bm, scope, opts, select=True):
    """Run the chosen steps on one bmesh; returns a dict of counts."""
    report = {}
    if scope == "SELECTED" and not any(v.select for v in bm.verts):
        scope = "ALL"  # nothing selected: clean the whole mesh

    def in_scope(elems):
        return [e for e in elems if e.is_valid and (scope == "ALL" or e.select)]

    if opts.doubles:
        verts = in_scope(bm.verts)
        before = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=verts, dist=opts.distance)
        report["doubles merged"] = before - len(bm.verts)

    if opts.degenerate:
        edges = in_scope(bm.edges)
        before = len(bm.edges) + len(bm.faces)
        bmesh.ops.dissolve_degenerate(bm, edges=edges, dist=opts.distance)
        report["degenerate removed"] = before - len(bm.edges) - len(bm.faces)

    if opts.loose:
        loose_edges = [e for e in in_scope(bm.edges) if not e.link_faces]
        loose_verts = [v for v in in_scope(bm.verts) if not v.link_faces and
                       all(e in loose_edges for e in v.link_edges)]
        n = len(loose_edges) + len(loose_verts)
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
        loose_verts = [v for v in loose_verts if v.is_valid]
        if loose_verts:
            bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')
        report["loose removed"] = n

    if opts.redundant_verts:
        verts = [v for v in in_scope(bm.verts) if _straight(v, opts.angle) and
                 (v.link_faces or not opts.keep_wire_ends)]
        if verts:
            bmesh.ops.dissolve_verts(bm, verts=verts, use_face_split=False, use_boundary_tear=False)
        report["straight vertices dissolved"] = len(verts)

    if opts.redundant_edges:
        edges = [e for e in in_scope(bm.edges) if e.is_manifold and not e.seam and not (opts.keep_sharp and not e.smooth)]
        flat = [e for e in edges if e.calc_face_angle(math.pi) <= opts.angle]
        before = len(bm.edges)
        if flat:
            bmesh.ops.dissolve_edges(bm, edges=flat, use_verts=True, use_face_split=False)
        report["flat edges dissolved"] = before - len(bm.edges)

    if opts.normals:
        faces = in_scope(bm.faces)
        flipped_before = {f: f.normal.copy() for f in faces}
        bmesh.ops.recalc_face_normals(bm, faces=faces)
        report["normals flipped"] = sum(1 for f, n in flipped_before.items() if f.is_valid and f.normal.dot(n) < 0)

    # select what still needs a look
    if select and opts.select != "NONE":
        for f in bm.faces:
            f.select = False
        for e in bm.edges:
            e.select = False
        for v in bm.verts:
            v.select = False
        if opts.select == "NON_MANIFOLD":
            found = [e for e in bm.edges if not e.is_manifold and not e.is_boundary or e.is_wire]
            for e in found:
                e.select = True
        elif opts.select == "NON_PLANAR":
            found = [f for f in bm.faces if _non_planar(f, opts.planar_tolerance)]
            for f in found:
                f.select = True
        elif opts.select == "NGONS":
            found = [f for f in bm.faces if len(f.verts) > 4]
            for f in found:
                f.select = True
        else:
            found = [f for f in bm.faces if len(f.verts) == 3]
            for f in found:
                f.select = True
        bm.select_flush(True)
        report["selected for a look"] = len(found)
    return report


class KEYOPS_OT_mesh_cleanup(bpy.types.Operator):
    bl_idname = "keyops.mesh_cleanup"
    bl_label = "Clean Up"
    bl_description = ("Merge doubles, remove degenerate and loose geometry, dissolve redundant vertices and edges, "
                      "fix normals, then select what still needs a look")
    bl_options = {'REGISTER', 'UNDO'}

    scope: EnumProperty(name="Clean", items=(
        ("SELECTED", "Selected", "Only the selected part of the mesh (Edit Mode). With nothing selected, the whole mesh"),
        ("ALL", "Whole Mesh", "The whole mesh"))) # type: ignore
    doubles: BoolProperty(name="Merge Doubles", default=True) # type: ignore
    degenerate: BoolProperty(name="Degenerate", default=True,
                             description="Remove zero-length edges and zero-area faces") # type: ignore
    loose: BoolProperty(name="Loose", default=True, description="Delete vertices and edges that aren't part of a face") # type: ignore
    redundant_verts: BoolProperty(name="Straight Vertices", default=True,
                                  description="Dissolve vertices that sit on a straight edge and add no shape") # type: ignore
    keep_wire_ends: BoolProperty(name="Keep Wire Points", default=True,
                                 description="Keep straight vertices on loose wire edges (curves made of edges)") # type: ignore
    redundant_edges: BoolProperty(name="Flat Edges", default=False,
                                  description="Dissolve edges between faces that lie flat, merging them into n-gons") # type: ignore
    keep_sharp: BoolProperty(name="Keep Sharp Edges", default=True,
                             description="Don't dissolve edges marked sharp, even on flat areas") # type: ignore
    normals: BoolProperty(name="Fix Normals", default=True, description="Make face normals point outside, consistently") # type: ignore
    distance: FloatProperty(name="Merge Distance", default=0.0001, min=0.0, soft_max=0.01, subtype='DISTANCE', precision=5) # type: ignore
    angle: FloatProperty(name="Angle", default=math.radians(1.0), min=0.0, max=math.radians(30), subtype='ANGLE',
                         description="How far from straight or flat still counts as redundant") # type: ignore
    select: EnumProperty(name="Then Select", default="NON_MANIFOLD", items=(
        ("NONE", "Nothing", "Keep the selection"),
        ("NON_MANIFOLD", "Non-Manifold", "Edges with more than two faces, and loose edges"),
        ("NON_PLANAR", "Non-Planar", "Faces whose corners don't lie in one plane"),
        ("NGONS", "N-gons", "Faces with more than four corners"),
        ("TRIS", "Triangles", "Faces with three corners"))) # type: ignore
    planar_tolerance: FloatProperty(name="Planar Tolerance", default=0.001, min=0.0, soft_max=0.1, subtype='DISTANCE',
                                    precision=4) # type: ignore

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in (context.selected_objects or [context.active_object]) if o)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        if context.mode == 'EDIT_MESH':
            layout.row().prop(self, "scope", expand=True)
        col = layout.column(heading="Fix")
        col.prop(self, "doubles")
        col.prop(self, "degenerate")
        col.prop(self, "loose")
        col.prop(self, "redundant_verts")
        sub = col.row()
        sub.active = self.redundant_verts
        sub.prop(self, "keep_wire_ends")
        col.prop(self, "redundant_edges")
        sub = col.row()
        sub.active = self.redundant_edges
        sub.prop(self, "keep_sharp")
        col.prop(self, "normals")
        col = layout.column()
        col.prop(self, "distance")
        col.prop(self, "angle")
        layout.prop(self, "select")
        if self.select == "NON_PLANAR":
            layout.prop(self, "planar_tolerance")

    def execute(self, context):
        totals = {}
        if context.mode == 'EDIT_MESH':
            objs = [o for o in (context.objects_in_mode_unique_data or [context.edit_object]) if o.type == 'MESH']
            for obj in objs:
                bm = bmesh.from_edit_mesh(obj.data)
                for k, v in clean(bm, self.scope, self).items():
                    totals[k] = totals.get(k, 0) + v
                bm.normal_update()
                bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
        else:
            objs = {o.data: o for o in context.selected_objects if o.type == 'MESH'}.values()
            for obj in objs:
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                for k, v in clean(bm, "ALL", self, select=False).items():
                    totals[k] = totals.get(k, 0) + v
                bm.to_mesh(obj.data)
                bm.free()
                obj.data.update()
        fixed = [f"{v} {k}" for k, v in totals.items() if v]
        self.report({'INFO'}, "Clean Up: " + (", ".join(fixed) if fixed else "nothing to fix"))
        return {'FINISHED'}


def register_mesh_cleanup():
    bpy.utils.register_class(KEYOPS_OT_mesh_cleanup)


def unregister_mesh_cleanup():
    bpy.utils.unregister_class(KEYOPS_OT_mesh_cleanup)
