"""Build tests/data/trim_cases.blend: meshes for testing Make Edge Trim (and the live trim).

    blender -b --factory-startup --python tests/data/make_trim_cases.py

Each object stores the edges to trim in a boolean edge attribute "trim_edges" and, as custom properties,
what the test expects ("on_surface": the trim must lie on the faces within this distance, or -1 when a flange
stands up by design). Run it in the oldest supported Blender (4.2) so every version can open the file.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trim_cases.blend")


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def make(name, bm, test, location, on_surface=1e-4, matrix=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    attr = me.attributes.new("trim_edges", 'BOOLEAN', 'EDGE')
    flags = []
    for e in me.edges:
        a, b = (me.vertices[i].co for i in e.vertices)
        flags.append(bool(test(a, b)))
    attr.data.foreach_set("value", flags)
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    if matrix is not None:
        obj.matrix_world = Matrix.Translation(location) @ matrix
    obj["on_surface"] = on_surface
    obj["edge_count"] = sum(flags)
    return obj


def cube(size=2.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    return bm


def main():
    clear()
    top = lambda a, b: a.z > 0.99 and b.z > 0.99
    o = make("Cube Top Loop", cube(), top, (0, 0, 0))
    o.data.materials.append(bpy.data.materials.new("Trim Test Material"))  # the live trim must get it

    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=1, radius2=1, depth=2)
    for v in bm.verts:
        if v.co.z > 0:
            v.co.z += 0.6 * v.co.x
    make("Sloped Ngon Cylinder", bm, lambda a, b: a.z > 0.3 and b.z > 0.3, (4, 0, 0), on_surface=1e-3)

    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ((-1, 0, 0), (1, 0, 0), (1, 2, 0), (-1, 2, 0), (1, 0, 2), (-1, 0, 2))]
    bm.faces.new((vs[0], vs[1], vs[2], vs[3]))
    bm.faces.new((vs[1], vs[0], vs[5], vs[4]))
    make("Floor Meets Wall", bm, lambda a, b: abs(a.y) < 1e-4 and abs(a.z) < 1e-4 and abs(b.y) < 1e-4 and abs(b.z) < 1e-4,
         (8, 0, 0))

    bm = bmesh.new()
    vs = [bm.verts.new((math.cos(i / 8 * math.tau), math.sin(i / 8 * math.tau), 0)) for i in range(8)]
    bm.faces.new(vs)
    make("Ngon Border", bm, lambda a, b: True, (12, 0, 0), on_surface=-1)

    # an L-shaped block: its top outline has an inside (concave) corner
    bm = bmesh.new()
    outline = [(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)]
    vs = [bm.verts.new((x, y, 0)) for x, y in outline]
    f = bm.faces.new(vs)
    bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in bm.verts:
        if v.co.z == 0 and v not in vs:
            pass
    ext = [v for v in bm.verts if v not in vs]
    for v in ext:
        v.co.z = 1.0
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    make("L Block Top", bm, lambda a, b: a.z > 0.99 and b.z > 0.99, (0, 5, 0))

    # a box scaled unevenly at object level: widths must still be metres in the scene
    make("Scaled Box", cube(), top, (5, 5, 0), matrix=Matrix.Diagonal((2.0, 1.0, 0.5, 1.0)))

    # a bevelled box (rounded corners): many short edges and small turns
    bm = cube()
    vert_edges = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1.9]
    bmesh.ops.bevel(bm, geom=vert_edges, offset=0.3, segments=4, affect='EDGES', profile=0.5)
    make("Bevelled Box Top", bm, top, (9, 5, 0))

    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (2, 1, 0.5))]
    for a, b in zip(vs, vs[1:]):
        bm.edges.new((a, b))
    make("Wire Chain", bm, lambda a, b: True, (13, 5, 0), on_surface=-1)

    # a cube with one edge bevelled: the trim goes around the top, through the bevel's narrow faces
    bm = cube()
    edge = [e for e in bm.edges if all(v.co.z > 0.99 and v.co.y > 0.99 for v in e.verts)]
    bmesh.ops.bevel(bm, geom=edge + list(edge[0].verts), offset=0.2, segments=3, affect='EDGES', profile=0.5)
    make("Bevelled Edge Cube Top", bm, lambda a, b: a.z > 0.79 and b.z > 0.79 and not (a.z < 0.999 and b.z < 0.999
                                                                                        and abs(a.x - b.x) > 1.9),
         (0, 10, 0))
    # ... and along one rail of that bevel
    bm = cube()
    edge = [e for e in bm.edges if all(v.co.z > 0.99 and v.co.y > 0.99 for v in e.verts)]
    bmesh.ops.bevel(bm, geom=edge + list(edge[0].verts), offset=0.2, segments=3, affect='EDGES', profile=0.5)
    make("Bevel Rail Edge", bm, lambda a, b: abs(a.z - 1) < 1e-4 and abs(b.z - 1) < 1e-4 and abs(a.y - 0.8) < 1e-4
         and abs(b.y - 0.8) < 1e-4, (4, 10, 0))
    # a sloped roof ridge: two faces meeting at 120 degrees
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ((-1, -1, 0), (1, -1, 0), (1, 0, 0.58), (-1, 0, 0.58), (1, 1, 0), (-1, 1, 0))]
    bm.faces.new((vs[0], vs[1], vs[2], vs[3]))
    bm.faces.new((vs[3], vs[2], vs[4], vs[5]))
    make("Roof Ridge", bm, lambda a, b: a.z > 0.5 and b.z > 0.5, (8, 10, 0))

    # a line across a flat surface, and a loop around a cylinder's side: faces in one plane, the trim lies flat
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=6, y_segments=6, size=1.0)
    make("Flat Grid Line", bm, lambda a, b: abs(a.x) < 1e-4 and abs(b.x) < 1e-4, (12, 10, 0))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=1, radius2=1, depth=2)
    side = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1.9]
    bmesh.ops.subdivide_edges(bm, edges=side, cuts=1, use_grid_fill=False)
    make("Cylinder Side Loop", bm, lambda a, b: abs(a.z) < 1e-4 and abs(b.z) < 1e-4, (16, 10, 0))

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print("SAVED", OUT)


main()
