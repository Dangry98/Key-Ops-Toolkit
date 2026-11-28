"""Push / Pull (and so Smart Extrude, the same engine) on the saved meshes in tests/data/push_pull_cases.blend, with every solver mode.

    blender -b --factory-startup --python tests/test_push_pull.py   (with the add-on installed as an extension)

Regenerate the cases with tests/data/make_push_pull_cases.py (in Blender 4.2). Exits non-zero on failure.
Checks for every case: the operator finishes, no new non-manifold edges (and no new open edges unless the
case allows them), the volume changes by the expected amount on closed meshes, islands the extrusion can't
reach are untouched, the new faces are selected and no helper data is left behind.
"""
import math
import os
import sys
import time
import traceback

import addon_utils
import bmesh
import bpy

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "push_pull_cases.blend")
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def mesh_stats(bm):
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    vol = 0.0
    for tri in bm.calc_loop_triangles():
        a, b, c = (lp.vert.co for lp in tri)
        vol += a.dot(b.cross(c))
    return boundary, nonman, vol / 6.0


def island_keys(bm):
    """Each face island as a sorted tuple of rounded vertex positions."""
    sb = sys.modules[MOD + ".utils.safe_boolean"]
    out = []
    for isl in sb.islands(bm.faces):
        out.append(tuple(sorted({tuple(round(c, 5) for c in v.co) for f in isl for v in f.verts})))
    return out


def run_case(src, mode):
    sb = sys.modules[MOD + ".utils.safe_boolean"]
    name = f"{src.name} [{mode}]"
    obj = src.copy()
    obj.data = src.data.copy()
    bpy.context.collection.objects.link(obj)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    me = obj.data
    flags = [False] * len(me.polygons)
    me.attributes["pp_select"].data.foreach_get("value", flags)
    for p, f in zip(me.polygons, flags):
        p.select = f
    for e in me.edges:
        e.select = False
    for v in me.vertices:
        v.select = False
    sel_verts = {i for p, f in zip(me.polygons, flags) if f for i in p.vertices}
    for i in sel_verts:
        me.vertices[i].select = True
    bm0 = bmesh.new()
    bm0.from_mesh(me)
    src["_shortest"] = min((e.calc_length() for e in bm0.edges), default=1.0)
    seen0 = {}
    for v in bm0.verts:
        k = tuple(round(c, 5) for c in v.co)
        seen0[k] = seen0.get(k, 0) + 1
    src["_doubles"] = sum(c - 1 for c in seen0.values())
    before = mesh_stats(bm0)
    islands0 = island_keys(bm0)
    bm0.free()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    d = src["pp_distance"]
    t0 = time.perf_counter()
    res = bpy.ops.keyops.push_pull(distance=d, solver=mode)
    dt = time.perf_counter() - t0
    bm = bmesh.from_edit_mesh(obj.data)
    after = mesh_stats(bm)
    islands1 = set(island_keys(bm))
    selected = sum(1 for f in bm.faces if f.select)
    seen = {}
    for v in bm.verts:
        k = tuple(round(c, 5) for c in v.co)
        seen[k] = seen.get(k, 0) + 1
    doubles = sum(c - 1 for c in seen.values())
    doubles0 = src.get("_doubles", 0)
    doubles = max(0, doubles - doubles0)
    shortest = min((e.calc_length() for e in bm.edges), default=1.0)
    shortest0 = src.get("_shortest")
    bpy.ops.object.mode_set(mode='OBJECT')
    path = sb.last_path
    check(f"{name}: finished ({path}, {dt:.2f} s)", res == {'FINISHED'}, str(res))
    check(f"{name}: no new non-manifold edges", after[1] <= before[1], f"{before[1]} -> {after[1]}")
    if not src["pp_new_boundary"]:
        check(f"{name}: no new open edges", after[0] <= before[0], f"{before[0]} -> {after[0]}")
    dv = src["pp_dv"]
    if not math.isnan(dv):
        got = after[2] - before[2]
        check(f"{name}: volume change {got:.4f} (expected {dv:.4f})", abs(got - dv) < 2e-3 * max(1.0, abs(dv)))
    # islands with no vertex near the extrusion must come back exactly as they were
    far = [k for k in islands0 if not any(abs(c[2]) <= 1.0 + abs(d) + 1e-3 and abs(c[0]) < 1.5 and abs(c[1]) < 1.5
                                          for c in k)]
    check(f"{name}: unreachable islands untouched", all(k in islands1 for k in far), f"{len(far)} far islands")
    check(f"{name}: new faces selected", selected > 0)
    check(f"{name}: no doubled vertices", doubles == 0, str(doubles))
    check(f"{name}: no hair-thin slivers (shortest edge {shortest:.2e})", shortest > 1e-4 or
          (shortest0 is not None and shortest >= shortest0 * 0.999))
    check(f"{name}: nothing left behind",
          not obj.modifiers and not any(o.name.startswith(".keyops_bool") for o in bpy.data.objects)
          and not any(s.name.startswith(".keyops_bool") for s in bpy.data.scenes)
          and not any(m.name.startswith(".keyops_bool") for m in bpy.data.meshes))
    if "MANIFOLD" in sb.solver_items() and mode == 'AUTO' and path not in ('NONE', 'MANIFOLD', None):
        print(f"NOTE {name}: Manifold not used ({path})")
    bpy.data.objects.remove(obj)
    return path


def run():
    addon_utils.enable(MOD, default_set=True)
    with bpy.data.libraries.load(CASES, link=False) as (data_from, data_to):
        data_to.objects = list(data_from.objects)
    for o in list(bpy.data.objects):
        if o not in data_to.objects:
            bpy.data.objects.remove(o)
    check("cases loaded", len(data_to.objects) >= 27, str(len(data_to.objects)))
    for o in sorted(data_to.objects, key=lambda o: o.name):
        for mode in ('AUTO', 'FAST', 'EXACT'):
            try:
                run_case(o, mode)
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                check(f"{o.name} [{mode}]: ran without errors", False, repr(e))
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
