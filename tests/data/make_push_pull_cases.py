"""Build tests/data/push_pull_cases.blend: meshes for Smart Extrude / Push / Pull (tests/test_push_pull.py).

    blender -b --factory-startup --python tests/data/make_push_pull_cases.py

Run in the oldest supported Blender (4.2) so every version can open the file. Each object has:
- a boolean face attribute "pp_select": the faces to extrude,
- "pp_distance": the distance along their normal (object units),
- "pp_dv": the expected change of volume (nan: not checked, e.g. open meshes),
- "pp_new_boundary": 1 when the result may have new open edges (an open shell cut as if solid).
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "push_pull_cases.blend")
NAN = float("nan")
X = 0.0


def new_obj(name, bm, select, distance, dv=NAN, new_boundary=0, loc=None):
    global X
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    flags = [bool(select(f)) for f in bm.faces]
    bm.to_mesh(me)
    bm.free()
    attr = me.attributes.new("pp_select", 'BOOLEAN', 'FACE')
    attr.data.foreach_set("value", flags)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc if loc is not None else (X, 0, 0)
    X += 8.0
    o["pp_distance"] = distance
    o["pp_dv"] = dv
    o["pp_new_boundary"] = new_boundary
    assert any(flags), name
    return o


def cube(size=2.0, cuts=2, center=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size, matrix=Matrix.Translation(center))
    if cuts:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    return bm


def top_mid(f):
    c = f.calc_center_median()
    return f.normal.z > 0.9 and abs(c.x) < 0.4 and abs(c.y) < 0.4 and c.z < 1.2


MID_AREA = (2.0 / 3.0) ** 2

for name, d, dv in (("Pocket", -0.5, -MID_AREA * 0.5), ("Boss", 0.5, MID_AREA * 0.5),
                    ("Through Hole", -2.5, -MID_AREA * 2.0), ("Exactly Through", -2.0, -MID_AREA * 2.0)):
    new_obj(name, cube(), top_mid, d, dv)

for name, d, nb in (("Open Box Pocket", -0.5, 0), ("Open Box Through", -2.5, 1)):
    bm = cube()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < -0.9], context='FACES')
    new_obj(name, bm, top_mid, d, NAN, nb)

bm = cube()
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < -0.9], context='FACES')
new_obj("Open Box Side Through", bm, lambda f: f.normal.x > 0.9 and abs(f.calc_center_median().y) < 0.4
        and abs(f.calc_center_median().z) < 0.4, -2.5, NAN)

bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=4, y_segments=4, size=1.0)
new_obj("Grid Push", bm, lambda f: abs(f.calc_center_median().x) < 0.5 and abs(f.calc_center_median().y) < 0.5, -0.3)

bm = cube()
far = cube(size=1.0, cuts=0, center=(4, 0, 0))
tmp = bpy.data.meshes.new("tmp")
far.to_mesh(tmp)
far.free()
bm.from_mesh(tmp)
new_obj("Two Islands", bm, top_mid, -0.5, -MID_AREA * 0.5)

bm2 = cube(size=1.0, cuts=0, center=(0, 0, 2.0))
bm2.to_mesh(tmp)
bm2.free()
bm = cube()
bm.from_mesh(tmp)
new_obj("Pull Into Neighbour", bm, top_mid, 1.0, MID_AREA * 1.0 - MID_AREA * 0.5)
bpy.data.meshes.remove(tmp)

bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=1.0, radius2=1.0, depth=2.0)
chord = 2 * math.sin(math.pi / 16)
new_obj("Cylinder Side Pocket", bm,
        lambda f: len(f.verts) == 4 and f.normal.x > 0.97 and f.normal.y > 0, -0.2, -chord * 2.0 * 0.2)

bm = bmesh.new()
bmesh.ops.create_monkey(bm)
best = max((f for f in bm.faces if f.normal.z > 0.6 and abs(f.calc_center_median().x) < 0.15),
           key=lambda f: f.calc_center_median().z)
best_c = best.calc_center_median().copy()
new_obj("Suzanne Forehead", bm, lambda f: (f.calc_center_median() - best_c).length < 1e-6, -0.05)

bm = cube()
bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
new_obj("Flipped Cube", bm, lambda f: f.normal.z < -0.9 and abs(f.calc_center_median().x) < 0.4
        and abs(f.calc_center_median().y) < 0.4 and f.calc_center_median().z > 0.9, 0.5)

bm = cube()
e = max((e for e in bm.edges if all(v.co.z > 0.99 for v in e.verts) and all(abs(v.co.y + 1) < 1e-6 for v in e.verts)),
        key=lambda e: -abs(e.verts[0].co.x + e.verts[1].co.x))
a, b = e.verts
fa, fb = bm.verts.new(a.co + Vector((0, 0, 0.6))), bm.verts.new(b.co + Vector((0, 0, 0.6)))
bm.faces.new((a, b, fb, fa))
bm2 = bm.copy()
new_obj("Non-manifold Fin", bm, top_mid, -0.5, NAN)
new_obj("Non-manifold Fin Through", bm2, top_mid, -2.5, NAN)

for name, d, dv in (("Bevelled Top Pocket", -0.3, -1.6 * 1.6 * 0.3), ("Bevelled Through", -3.0, -1.6 * 1.6 * 2.0)):
    bm = cube(cuts=0)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=0.2, segments=2, affect='EDGES', profile=0.5)
    new_obj(name, bm, lambda f: f.normal.z > 0.999 and f.calc_center_median().z > 0.99, d, dv)

bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=1.5)
new_obj("Dense Sphere", bm, lambda f: f.calc_center_median().z > 1.42, -0.3, NAN)

o = new_obj("Scaled Rotated", cube(), top_mid, -0.5, -MID_AREA * 0.5)
o.scale = (2, 1, 0.5)
o.rotation_euler = (0.3, 0.2, 0.1)

bm = cube()
bmesh.ops.triangulate(bm, faces=bm.faces[:])
new_obj("Triangulated Through", bm, lambda f: f.normal.z > 0.9 and abs(f.calc_center_median().x) < 1 / 3
        and abs(f.calc_center_median().y) < 1 / 3, -2.5, -MID_AREA * 2.0)

bm = cube()
corner = cube(size=1.0, cuts=0, center=(1.5, 1.5, 1.5))  # touches the big cube at one vertex only
tmp = bpy.data.meshes.new("tmp")
corner.to_mesh(tmp)
corner.free()
bm.from_mesh(tmp)
bpy.data.meshes.remove(tmp)
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
new_obj("Corner Touch Through", bm, top_mid, -2.5, -MID_AREA * 2.0)

bm = cube()
pocket = [f for f in bm.faces if top_mid(f)]
ret = bmesh.ops.extrude_face_region(bm, geom=pocket)
bmesh.ops.translate(bm, vec=Vector((0, 0, -0.2)), verts=[g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)])
bmesh.ops.delete(bm, geom=pocket, context='FACES')
new_obj("Slot Floor Pull", bm, lambda f: f.normal.z > 0.9 and abs(f.calc_center_median().z - 0.8) < 1e-4,
        0.5, MID_AREA * 0.5)

bm = cube(cuts=0)
inner = cube(size=1.6, cuts=0)
bmesh.ops.reverse_faces(inner, faces=inner.faces[:])
tmp = bpy.data.meshes.new("tmp")
inner.to_mesh(tmp)
inner.free()
bm.from_mesh(tmp)
bpy.data.meshes.remove(tmp)
new_obj("Push Into Inner Shell", bm, lambda f: f.normal.z > 0.9 and f.calc_center_median().z > 0.9, -0.5,
        -(2 * 2 * 0.5 - 1.6 * 1.6 * 0.3))

bm = cube()
inner = cube(size=1.6, cuts=0)
bmesh.ops.reverse_faces(inner, faces=inner.faces[:])
tmp = bpy.data.meshes.new("tmp")
inner.to_mesh(tmp)
inner.free()
bm.from_mesh(tmp)
bpy.data.meshes.remove(tmp)
new_obj("Hollow Box Breakthrough", bm, lambda f: top_mid(f) and f.calc_center_median().z > 0.9, -0.3, -MID_AREA * 0.2)

bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
for v in bm.verts:
    v.co.x *= 3.0
    v.co.z = (v.co.z + 0.5) * 0.5
bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.x - e.verts[1].co.x) > 1e-6], cuts=5,
                          use_grid_fill=True)
posts = [f for f in bm.faces if f.normal.z > 0.9 and abs(f.calc_center_median().x) > 1.0]
ret = bmesh.ops.extrude_face_region(bm, geom=posts)
bmesh.ops.translate(bm, vec=Vector((0, 0, 1.5)), verts=[g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)])
bmesh.ops.delete(bm, geom=posts, context='FACES')
new_obj("U Self Collide", bm, lambda f: f.normal.x > 0.9 and abs(f.calc_center_median().x + 1.0) < 1e-4
        and f.calc_center_median().z > 0.5, 2.2, 1.5 * 2.2 - 0.2 * 1.5)

tiny = cube(size=0.02)
new_obj("Tiny Pocket", tiny, lambda f: f.normal.z > 0.9 and abs(f.calc_center_median().x) < 0.004
        and abs(f.calc_center_median().y) < 0.004, -0.005, -(0.02 / 3) ** 2 * 0.005)

bm = bmesh.new()
tmp = bpy.data.meshes.new("tmp")
for i in range(10):
    for j in range(10):
        c = cube(size=0.5, center=(i - 4.5, j - 4.5, 0))
        c.to_mesh(tmp)
        c.free()
        bm.from_mesh(tmp)
bpy.data.meshes.remove(tmp)
new_obj("Many Islands", bm, lambda f: f.normal.z > 0.9 and abs(f.calc_center_median().x - 0.5) < 0.05
        and abs(f.calc_center_median().y - 0.5) < 0.05, -0.1, -(0.5 / 3) ** 2 * 0.1)

for ob in list(bpy.data.objects):
    if "pp_distance" not in ob:
        bpy.data.objects.remove(ob)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print("SAVED", OUT, len(bpy.data.objects))
