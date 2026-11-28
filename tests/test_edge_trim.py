"""Make Edge Trim (and the live trim) on the saved cases in tests/data/trim_cases.blend.

    blender -b --factory-startup --python tests/test_edge_trim.py   (with the add-on installed as an extension)

Regenerate the cases with tests/data/make_trim_cases.py. Exits non-zero on failure.
"""
import os
import sys
import traceback

import addon_utils
import bpy
from mathutils.bvhtree import BVHTree

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "trim_cases.blend")
LIVE_ALL = True  # the live trim lays its flanges on the faces at any angle: every case
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def world_bvh(obj, depsgraph=None):
    me = obj.evaluated_get(depsgraph).to_mesh() if depsgraph else obj.data
    mw = obj.matrix_world
    tree = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]) \
        if len(me.polygons) else None
    if depsgraph:
        obj.evaluated_get(depsgraph).to_mesh_clear()
    return tree


def select_case_edges(obj):
    me = obj.data
    flags = [False] * len(me.edges)
    me.attributes["trim_edges"].data.foreach_get("value", flags)
    for p in me.polygons:
        p.select = False
    for v in me.vertices:
        v.select = False
    for e, f in zip(me.edges, flags):
        e.select = f
        if f:
            for i in e.vertices:
                me.vertices[i].select = True


def stats(trim, src_tree, depsgraph=None):
    me = trim.evaluated_get(depsgraph).to_mesh() if depsgraph else trim.data
    mw = trim.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    dists = [src_tree.find_nearest(v)[3] for v in verts] if src_tree else []
    areas, facing = [], []
    for p in me.polygons:
        pts = [verts[i] for i in p.vertices]
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        for i in range(3, len(pts)):
            n += (pts[i - 1] - pts[0]).cross(pts[i] - pts[0])
        areas.append(n.length / 2)
        if src_tree:
            c = sum(pts, pts[0] * 0) / len(pts)
            hit = src_tree.find_nearest(c)
            if hit[0] is not None and hit[3] < 1e-3 and n.length > 1e-12:
                facing.append(n.normalized().dot(hit[1]))
    zs = [v.z for v in verts]
    out = dict(n_faces=len(me.polygons), max_off=max(dists) if dists else 0.0,
               on_frac=(sum(d < 1e-4 for d in dists) / len(dists)) if dists else 0.0,
               min_area=min(areas) if areas else 0.0, facing=min(facing) if facing else None,
               z_span=(max(zs) - min(zs)) if zs else 0.0, sharp=[e for e in me.edges if e.use_edge_sharp])
    if depsgraph:
        trim.evaluated_get(depsgraph).to_mesh_clear()
    return out


def run_case(src):
    name = src.name
    tol = src.get("on_surface", 1e-4)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    src.select_set(True)
    bpy.context.view_layer.objects.active = src
    select_case_edges(src)
    tree = world_bvh(src)
    before = set(bpy.data.objects)
    bpy.ops.object.mode_set(mode='EDIT')
    res = bpy.ops.keyops.edge_trim()
    bpy.ops.object.mode_set(mode='OBJECT')
    trims = [o for o in set(bpy.data.objects) - before if o.type == 'MESH']
    check(f"{name}: Make Edge Trim makes a trim object", res == {'FINISHED'} and len(trims) == 1, str(res))
    if len(trims) != 1:
        return
    st = stats(trims[0], tree)
    if tol >= 0:
        check(f"{name}: every trim point on the surface (within {tol})", st["max_off"] <= tol, f"{st['max_off']:.5f}")
    elif tree is not None:
        check(f"{name}: one flange on the face, one standing up", st["on_frac"] >= 0.6, f"{st['on_frac']:.2f}")
    check(f"{name}: no collapsed faces", st["min_area"] > 1e-7, f"{st['min_area']:.2e}")
    if st["facing"] is not None:
        check(f"{name}: trim faces face the same way as the faces under them", st["facing"] > 0.99, f"{st['facing']:.4f}")
    check(f"{name}: smooth, no sharp edges", not st["sharp"])
    if name == "Scaled Box":
        # the box is squashed to half height at object level: the side flange must still be 5 cm in the scene
        check("Scaled Box: widths are metres in the scene (object scale compensated)", abs(st["z_span"] - 0.05) < 1e-3,
              f"{st['z_span']:.4f}")
    bpy.data.objects.remove(trims[0])

    if LIVE_ALL:
        for o in bpy.context.selected_objects:
            o.select_set(False)
        src.select_set(True)
        bpy.context.view_layer.objects.active = src
        select_case_edges(src)
        before = set(bpy.data.objects)
        bpy.ops.object.mode_set(mode='EDIT')
        res = bpy.ops.keyops.edge_trim_live(width=0.05, offset=0.0)
        bpy.ops.object.mode_set(mode='OBJECT')
        live = [o for o in set(bpy.data.objects) - before]
        dg = bpy.context.evaluated_depsgraph_get()
        if res != {'FINISHED'} or len(live) != 1:
            check(f"{name}: Live Edge Trim made", False, str(res))
            return
        st = stats(live[0], tree, dg)
        if tol >= 0:
            check(f"{name}: Live Edge Trim lies on the surface (within {max(tol, 1e-4)})",
                  st["n_faces"] > 0 and st["max_off"] <= max(tol, 1e-4), f"faces {st['n_faces']} off {st['max_off']:.5f}")
        elif tree is not None:
            check(f"{name}: Live Edge Trim: one flange on the face, one standing up", st["n_faces"] > 0
                  and st["on_frac"] >= 0.6, f"faces {st['n_faces']} on {st['on_frac']:.2f}")
        else:
            check(f"{name}: Live Edge Trim made faces", st["n_faces"] > 0, f"faces {st['n_faces']}")
        check(f"{name}: Live Edge Trim has no collapsed faces", st["min_area"] > 1e-7, f"{st['min_area']:.2e}")
        if st["facing"] is not None:
            check(f"{name}: Live Edge Trim faces face the same way as the faces under them", st["facing"] > 0.99,
                  f"{st['facing']:.4f}")
        me = live[0].evaluated_get(dg).to_mesh()
        mats = [m.name for m in me.materials if m]
        live[0].evaluated_get(dg).to_mesh_clear()
        if src.active_material is not None:
            check(f"{name}: Live Edge Trim gets the source's material", src.active_material.name in mats, str(mats))
        if name == "Scaled Box":
            check("Scaled Box: live trim widths are metres in the scene", abs(st["z_span"] - 0.05) < 1e-3, f"{st['z_span']:.4f}")
        if name == "Cube Top Loop":
            mod = live[0].modifiers[0]
            tp = sys.modules[MOD + ".operators.toolkit_panel"]
            tp.set_gn_input(mod, "Second Width", 0.2)  # ignored while Separate Widths is off
            live[0].update_tag()
            dg = bpy.context.evaluated_depsgraph_get()
            st1 = stats(live[0], tree, dg)
            check("Cube Top Loop: Separate Widths off: one width for both flanges", abs(st1["z_span"] - 0.05) < 1e-3,
                  f"{st1['z_span']:.4f}")
            tp.set_gn_input(mod, "Separate Widths", True)
            live[0].update_tag()
            dg = bpy.context.evaluated_depsgraph_get()
            st2 = stats(live[0], tree, dg)
            check("Cube Top Loop: Separate Widths on: the second flange takes its own width",
                  abs(st2["z_span"] - 0.05) > 1e-3 or st2["max_off"] > 1e-4, f"{st2['z_span']:.4f}")
            tp.set_gn_input(mod, "Wrap", False)
            tp.set_gn_input(mod, "Separate Widths", False)
            live[0].update_tag()
            dg = bpy.context.evaluated_depsgraph_get()
            st3 = stats(live[0], tree, dg)
            if st3["facing"] is not None:
                check("Cube Top Loop: Upright live trim faces face out too", st3["facing"] > 0.99, f"{st3['facing']:.4f}")
        bpy.data.objects.remove(live[0])


def run():
    addon_utils.enable(MOD, default_set=True)
    with bpy.data.libraries.load(CASES, link=False) as (data_from, data_to):
        data_to.objects = list(data_from.objects)
    for o in list(bpy.data.objects):
        if o not in data_to.objects:
            bpy.data.objects.remove(o)
    for o in data_to.objects:
        bpy.context.collection.objects.link(o)
    bpy.context.view_layer.update()  # world matrices of the loaded objects
    check("cases loaded", len(data_to.objects) >= 13, str(len(data_to.objects)))
    for o in sorted(data_to.objects, key=lambda o: o.name):
        try:
            run_case(o)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            check(f"{o.name}: ran without errors", False, repr(e))
            if bpy.context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')


try:
    run()
except Exception:
    traceback.print_exc()
    results.append(("no exception", False, ""))

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
