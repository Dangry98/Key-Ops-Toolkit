"""Headless checks for Set Cylinder Sides (keyops.set_cylinder_sides).

Run with the add-on installed as an extension in the user_default repository:
    blender -b --factory-startup --python tests/test_cylinder_sides.py
Exits non-zero on failure.
"""

import sys
import traceback

import addon_utils
import bmesh
import bpy

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def fresh(add):
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    add()
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for elems in (bm.verts, bm.edges, bm.faces):
        for e in elems:
            e.select = False
    return obj, bm


def select_edges(obj, bm, test):
    for e in bm.edges:
        if test(*e.verts):
            e.select = True
            for v in e.verts:
                v.select = True
    bm.select_flush_mode()
    bmesh.update_edit_mesh(obj.data)


def bottom_ring(a, b):
    return all(abs(v.co.z + 1) < 1e-4 and abs(v.co.xy.length - 1) < 1e-3 for v in (a, b))


def radii(bm):
    r = [v.co.xy.length for v in bm.verts if v.co.xy.length > 0.01]
    return min(r), max(r)


def sound(bm):
    return all(e.is_manifold or e.is_boundary for e in bm.edges) and all(len(f.verts) >= 3 for f in bm.faces)


def run():
    addon_utils.enable(MOD, default_set=True)
    check("operator registered", "set_cylinder_sides" in dir(bpy.ops.keyops))

    # Cylinder with n-gon caps: 16 -> 24 sides, outline stays on the unit circle, UVs survive
    obj, bm = fresh(lambda: bpy.ops.mesh.primitive_cylinder_add(vertices=16, depth=2, end_fill_type='NGON'))
    select_edges(obj, bm, bottom_ring)
    res = bpy.ops.keyops.set_cylinder_sides(mode='EXACT', sides=24)
    bm = bmesh.from_edit_mesh(obj.data)
    lo, hi = radii(bm)
    check("ngon cylinder 16 -> 24", res == {'FINISHED'} and len(bm.verts) == 48 and len(bm.faces) == 26,
          f"{res} verts={len(bm.verts)} faces={len(bm.faces)}")
    check("ngon cylinder keeps radius", abs(lo - 1) < 1e-4 and abs(hi - 1) < 1e-4, f"{lo:.5f}..{hi:.5f}")
    check("ngon cylinder is sound", sound(bm))
    check("UV layer kept", len(obj.data.uv_layers) == 1)
    check("new loop selected", sum(1 for e in bm.edges if e.select) == 24)

    # Fewer sides
    res = bpy.ops.keyops.set_cylinder_sides(mode='CHANGE', change=-18)
    bm = bmesh.from_edit_mesh(obj.data)
    check("ngon cylinder 24 -> 6", res == {'FINISHED'} and len(bm.verts) == 12, f"{res} verts={len(bm.verts)}")

    # Triangle-fan caps
    obj, bm = fresh(lambda: bpy.ops.mesh.primitive_cylinder_add(vertices=12, depth=2, end_fill_type='TRIFAN'))
    select_edges(obj, bm, bottom_ring)
    res = bpy.ops.keyops.set_cylinder_sides(mode='EXACT', sides=20)
    bm = bmesh.from_edit_mesh(obj.data)
    check("fan cylinder 12 -> 20", res == {'FINISHED'} and len(bm.verts) == 42 and len(bm.faces) == 60 and sound(bm),
          f"{res} verts={len(bm.verts)} faces={len(bm.faces)}")

    # Open tube, chosen by selecting its side faces
    obj, bm = fresh(lambda: bpy.ops.mesh.primitive_cylinder_add(vertices=8, depth=2, end_fill_type='NOTHING'))
    for f in bm.faces:
        f.select = True
    bmesh.update_edit_mesh(obj.data)
    res = bpy.ops.keyops.set_cylinder_sides(mode='EXACT', sides=5)
    bm = bmesh.from_edit_mesh(obj.data)
    check("open tube from faces 8 -> 5", res == {'FINISHED'} and len(bm.verts) == 10 and len(bm.faces) == 5,
          f"{res} verts={len(bm.verts)} faces={len(bm.faces)}")

    # Torus: change the minor rings, the walk wraps all the way round
    obj, bm = fresh(lambda: bpy.ops.mesh.primitive_torus_add(major_segments=24, minor_segments=12))
    select_edges(obj, bm, lambda a, b: abs(a.co.y) < 1e-4 and abs(b.co.y) < 1e-4 and a.co.x > 0 and b.co.x > 0)
    res = bpy.ops.keyops.set_cylinder_sides(mode='CHANGE', change=4)
    bm = bmesh.from_edit_mesh(obj.data)
    check("torus minor 12 -> 16", res == {'FINISHED'} and len(bm.verts) == 24 * 16 and
          all(e.is_manifold for e in bm.edges), f"{res} verts={len(bm.verts)}")

    # Shape joined to other geometry: refused, nothing changes
    obj, bm = fresh(lambda: bpy.ops.mesh.primitive_cylinder_add(vertices=8, depth=2, end_fill_type='NGON'))
    side = next(f for f in bm.faces if len(f.verts) == 4)
    side.select = True
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": tuple(side.normal)})  # a bump on the side
    bm = bmesh.from_edit_mesh(obj.data)
    for elems in (bm.verts, bm.edges, bm.faces):
        for e in elems:
            e.select = False
    select_edges(obj, bm, bottom_ring)
    before = len(bm.verts)
    res = bpy.ops.keyops.set_cylinder_sides(mode='EXACT', sides=16)
    bm = bmesh.from_edit_mesh(obj.data)
    check("joined shape refused, mesh unchanged", res == {'CANCELLED'} and len(bm.verts) == before,
          f"{res} verts {before} -> {len(bm.verts)}")

    # Nothing selected
    for e in bm.edges:
        e.select = False
    for v in bm.verts:
        v.select = False
    for f in bm.faces:
        f.select = False
    bmesh.update_edit_mesh(obj.data)
    check("nothing selected cancels", bpy.ops.keyops.set_cylinder_sides(mode='EXACT', sides=16) == {'CANCELLED'})
    bpy.ops.object.mode_set(mode='OBJECT')


try:
    run()
except Exception:
    traceback.print_exc()
    results.append(("no exception", False, ""))

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
