"""Headless checks for the backlog fixes and features (one section per card).

Run with the add-on installed as an extension in the user_default repository:
    blender -b --factory-startup --python tests/test_backlog.py
Exits non-zero on failure.
"""

import importlib
import os
import sys
import traceback

import addon_utils
import bmesh
import bpy
from mathutils import Matrix, Vector

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def sub(name):
    return importlib.import_module(f"{MOD}.{name}")


def clear_scene():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def mesh_object(name, verts, edges=(), faces=()):
    me = bpy.data.meshes.new(name)
    me.from_pydata([Vector(v) for v in verts], list(edges), list(faces))
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


def edit_select_all(obj, mode='EDGE'):
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type=mode)
    bpy.ops.mesh.select_all(action='SELECT')


# ---------------------------------------------------------------- Phase 1

def test_revolve_axis():
    tp = sub("operators.toolkit_panel")
    line_z = [Vector((1, 0, z)) for z in (-1, 0, 1)]
    check("revolve axis: a vertical line beside the origin turns around Z", tp.revolve_axis(line_z) == 'Z')
    line_x = [Vector((x, 0, 1)) for x in (-1, 0, 1)]
    check("revolve axis: a line along X above the origin turns around X", tp.revolve_axis(line_x) == 'X')
    line_y = [Vector((0.5, y, 0)) for y in (0, 2)]
    check("revolve axis: a line along Y beside the origin turns around Y", tp.revolve_axis(line_y) == 'Y')
    disc = [Vector((x, 0, 0)) for x in (0, 0.5, 1)]
    check("revolve axis: a flat profile through the origin (a disc) turns around Z", tp.revolve_axis(disc) == 'Z')
    cup = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((1, 0, 2))]
    check("revolve axis: a cup profile (bottom + wall) turns around Z", tp.revolve_axis(cup) == 'Z')

    clear_scene()
    obj = mesh_object("Profile", [(0, 1, -1), (0, 1, 1)], [(0, 1)])  # a wall along Z beside the origin on Y
    edit_select_all(obj)
    bpy.ops.keyops.toolkit_panel(type="change_cylinder_segments_modifier")
    mod = obj.modifiers.get("Screw")
    check("Revolve Edges: Screw modifier added around the picked axis", mod is not None and mod.axis == 'Z',
          mod and mod.axis)
    bpy.ops.object.mode_set(mode='OBJECT')
    clear_scene()
    obj = mesh_object("Profile", [(-1, 0, 1), (1, 0, 1)], [(0, 1)])  # a line along X above the origin
    edit_select_all(obj)
    bpy.ops.keyops.toolkit_panel(type="change_cylinder_segments_modifier")
    mod = obj.modifiers.get("Screw")
    check("Revolve Edges: a profile along X revolves around X", mod is not None and mod.axis == 'X', mod and mod.axis)
    bpy.ops.object.mode_set(mode='OBJECT')
    clear_scene()
    obj = mesh_object("Profile", [(-1, 0, 1), (1, 0, 1)], [(0, 1)])
    edit_select_all(obj)
    bpy.ops.keyops.toolkit_panel(type="change_cylinder_segments_modifier", screw_axis='Y', screw_steps=12)
    mod = obj.modifiers.get("Screw")
    check("Revolve Edges: the axis and steps can be set by hand", mod and mod.axis == 'Y' and mod.steps == 12)
    bpy.ops.object.mode_set(mode='OBJECT')


def test_curve_tools():
    clear_scene()
    obj = mesh_object("Wire", [(0, 0, 0), (1, 0, 0), (1, 1, 0), (5, 5, 5)], [(0, 1), (1, 2)])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bm = bmesh.from_edit_mesh(obj.data)
    for e in bm.edges:
        e.select = True
    bmesh.update_edit_mesh(obj.data)
    res = bpy.ops.keyops.edges_to_curve(depth=0.1)
    curves = [o for o in bpy.data.objects if o.type == 'CURVE']
    check("Edges to Curve: makes a curve from the selected edges", res == {'FINISHED'} and len(curves) == 1, res)
    if curves:
        c = curves[0]
        pts = sum(len(s.points) for s in c.data.splines)
        check("Edges to Curve: curve has the selected edges' points, the bevel depth, and the mesh stays",
              pts == 3 and abs(c.data.bevel_depth - 0.1) < 1e-6 and len(obj.data.vertices) == 4, f"{pts} pts")
        check("Edges to Curve: the new curve is active in Object Mode", bpy.context.mode == 'OBJECT'
              and bpy.context.view_layer.objects.active == c)
        res = bpy.ops.keyops.curve_radius(depth=0.25)
        check("Curve Radius: sets the bevel depth", res == {'FINISHED'} and abs(c.data.bevel_depth - 0.25) < 1e-6)


def test_q_menu_migration():
    pm = sub("pie_menus")
    data = {"pies": [
        {"uid": "q1", "preset": "q_menu", "editor": "Object Mode, Mesh", "items": []},
        {"uid": "q2", "preset": "q_active_modifier", "owner": "q1", "editor": "Object Mode, Mesh", "items": []},
        {"uid": "q3", "preset": "q_display", "owner": "q1", "editor": "Object Mode, Mesh", "items": []},
        {"uid": "uv", "preset": "uv_islands", "editor": "UV Editor, 3D View Generic", "items": []},
        {"uid": "add", "preset": "add_objects", "editor": "3D View Generic", "items": [
            {"kind": "OPERATOR", "idname": "keyops.add_mesh", "props": "mesh_type='CYLINDER'"},
            {"kind": "OPERATOR", "idname": "keyops.add_mesh", "props": "mesh_type='MODCYLINDER'"}]},
    ]}
    out = pm._migrate_pies_13_to_14(data)
    presets = {p["preset"]: p for p in out["pies"]}
    check("migration 14: the Active Modifier submenu is dropped", "q_active_modifier" not in presets)
    check("migration 14: the Q Menu and its submenus also work in curve Edit Mode",
          presets["q_menu"]["editor"] == "Object Mode, Mesh, Curve" and presets["q_display"]["editor"] == "Object Mode, Mesh, Curve")
    check("migration 14: the Q Menu is rebuilt from its preset", "q1" in pm._refill_uids)
    check("migration 14: the UV Islands pie works only in the UV Editor", presets["uv_islands"]["editor"] == "UV Editor")
    items = presets["add_objects"]["items"]
    check("migration 14: Add Objects' Cylinder is Blender's own cylinder, Mod Cylinder stays",
          items[0]["idname"] == "mesh.primitive_cylinder_add" and items[1]["props"] == "mesh_type='MODCYLINDER'")
    pm._refill_uids.clear()
    q = pm.PRESET_BY_ID["q_display"]
    styles = [it[6] if len(it) > 6 else "AUTO" for it in q["items"]]
    check("Q Menu Display: display types are one button each (no third menu level)", styles.count("VALUE") == 4)


def test_whats_new_not_automatic():
    w = sub("ui.welcome")
    scheduled = []
    real = bpy.app.timers.register
    try:
        bpy.app.timers.register = lambda fn, **kw: scheduled.append(fn)
        real_bg = bpy.app.background
        w.schedule_welcome()  # in background mode nothing is scheduled at all; check the code path directly
        p = sub("utils.pref_utils").get_keyops_prefs()
        kind = w.first_screen(p)
    finally:
        bpy.app.timers.register = real
    import inspect
    src = inspect.getsource(w.schedule_welcome)
    check("What's New never opens by itself (only the first-install welcome may)",
          "register(_show_whats_new" not in src and "WELCOME" in src and real_bg)
    check("What's New can be opened from Preferences", "show_whats_new" in dir(bpy.ops.keyops))


def test_header_element_button():
    sm = sub("operators.subobject_modes")
    H = bpy.types.VIEW3D_HT_header
    check("header: Vertex / Edge / Face / Element drawn by Key Ops as one joined group in mesh Edit Mode",
          sm._header_draw in getattr(H.draw, "_draw_funcs", ()))
    # other add-ons' header items: added before or after Key Ops, they draw and can be removed again
    def other_item(self, context):
        pass
    H.append(other_item)
    sm._unpatch_header()
    restored = sm._header_draw not in H.draw._draw_funcs and other_item in H.draw._draw_funcs
    sm._patch_header()
    H.remove(other_item)
    check("header: other add-ons' items survive Key Ops patching / unpatching and can be removed",
          restored and other_item not in H.draw._draw_funcs and sm._header_draw in H.draw._draw_funcs)
    check("Element mode keeps its original icon", sm.ELEMENT_ICON == 'SNAP_VOLUME')
    log = []

    class Rec:
        def __getattr__(self, name):
            def call(*a, **k):
                log.append((name, k.get("icon"), k.get("depress")))
                return self if name in ("row", "column") else type("Op", (), {})()
            return call
    proxy = sm._LayoutProxy(Rec(), bpy.context)
    real_mode = bpy.context.mode
    if real_mode != 'EDIT_MESH':
        clear_scene()
        bpy.ops.mesh.primitive_cube_add()
        bpy.ops.object.mode_set(mode='EDIT')
    proxy._context = bpy.context
    proxy.template_header_3D_mode()
    icons = [i for n, i, _d in log if n == "operator"]
    check("header group: the four modes in one row", icons == ['VERTEXSEL', 'EDGESEL', 'FACESEL', 'SNAP_VOLUME']
          and log[0][0] == "row", str(log[:5]))
    bpy.ops.object.mode_set(mode='OBJECT')


def test_duplicate_linked_in_object_menu():
    tp = sub("operators.toolkit_panel")
    fns = getattr(bpy.types.VIEW3D_MT_object, "_dyn_ui_initialize", lambda: [])()
    check("Object menu has Duplicate Linked Modifiers (same command as Alt+Shift+D)", tp.object_menu_duplicate in fns)
    km = bpy.context.window_manager.keyconfigs.addon.keymaps.get("Object Mode")
    bound = km is not None and any(k.idname == "object.duplicate_linked_modifiers" and k.type == 'D' and k.shift and k.alt
                                   for k in km.keymap_items)
    check("Duplicate Linked Modifiers is its own object.* operator on Shift Alt D (the shortcut shows on hover)", bound)
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    before = len(bpy.data.objects)
    res = bpy.ops.object.duplicate_linked_modifiers('EXEC_DEFAULT')
    check("Duplicate Linked Modifiers duplicates the selection", res == {'FINISHED'} and len(bpy.data.objects) == before + 1,
          f"{res} {len(bpy.data.objects)}")


# ---------------------------------------------------------------- Phase 2

def test_cylinder_sides_partial():
    """A cylinder joined to geometry it can't walk through: the touching ring stays, the rest changes."""
    clear_scene()
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, depth=2, end_fill_type='NOTHING')
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bottom = [e for e in bm.edges if all(abs(v.co.z + 1) < 1e-4 for v in e.verts)]
    # a flange of quads outward from the bottom ring, then one flange quad becomes a 5-gon (not a clean ring)
    ret = bmesh.ops.extrude_edge_only(bm, edges=bottom)
    new_verts = [v for v in ret["geom"] if isinstance(v, bmesh.types.BMVert)]
    for v in new_verts:
        v.co.x *= 2.0
        v.co.y *= 2.0
    outer = [e for e in ret["geom"] if isinstance(e, bmesh.types.BMEdge)
             and all(v in new_verts for v in e.verts)]
    bmesh.ops.subdivide_edges(bm, edges=outer[:1], cuts=1)
    for elems in (bm.verts, bm.edges, bm.faces):
        for e in elems:
            e.select = False
    top = [e for e in bm.edges if all(abs(v.co.z - 1) < 1e-4 for v in e.verts)]
    for e in top:
        e.select = True
    bmesh.update_edit_mesh(obj.data)
    res = bpy.ops.keyops.set_cylinder_sides(mode='EXACT', sides=24)
    bm = bmesh.from_edit_mesh(obj.data)
    top_n = len([v for v in bm.verts if abs(v.co.z - 1) < 1e-4])
    bottom_n = len([v for v in bm.verts if abs(v.co.z + 1) < 1e-4 and v.co.xy.length < 1.5])
    sound = all(e.is_manifold or e.is_boundary for e in bm.edges)
    check("Set Cylinder Sides: rebuilds up to geometry it can't walk through, the touching ring stays",
          res == {'FINISHED'} and top_n == 24 and bottom_n == 16 and sound, f"{res} top {top_n} bottom {bottom_n} sound {sound}")
    bpy.ops.object.mode_set(mode='OBJECT')


def test_none_live_booleans_undo():
    nlb = sub("operators.none_live_booleans")
    clear_scene()
    objs = {}
    for name, x in (("A", 0), ("CutA", 0), ("B", 5), ("CutB", 5)):
        bpy.ops.mesh.primitive_cube_add(location=(x, 0, 0))
        objs[name] = bpy.context.object
        objs[name].name = name
    for target, cutter in (("A", "CutA"), ("B", "CutB")):
        m = objs[target].modifiers.new("Boolean", 'BOOLEAN')
        m.object = objs[cutter]
    # an old transform's copy of CutB: no longer in the scene (unlinked)
    old = objs["CutB"].copy()
    old.name = "temp_boolean_cutter_CutB"
    # the current undo step still has CutA's copy in the scene, selected, with CutA hidden
    cur = objs["CutA"].copy()
    bpy.context.collection.objects.link(cur)
    cur.name = "temp_boolean_cutter_CutA"
    for o in bpy.context.selected_objects:
        o.select_set(False)
    objs["CutA"].hide_set(True)
    cur.select_set(True)
    nlb.obj_to_delete = [old.name, cur.name]
    nlb.delete_temp_objs_on_redo_undo(None, None)
    check("non-live booleans undo: the copy in the scene goes, its cutter shows and is selected",
          not cur.users_collection and not objs["CutA"].hide_get() and objs["CutA"].select_get())
    check("non-live booleans undo: other booleans' cutters are not selected",
          not objs["CutB"].select_get() and not objs["A"].select_get() and not objs["B"].select_get())


def test_smart_apply_scale():
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    a = bpy.context.object
    b = a.copy()
    bpy.context.collection.objects.link(b)  # shares a's mesh
    b.location.x = 4
    for o in (a, b):
        o.scale = (2, 2, 2)
    bev = a.modifiers.new("Bevel", 'BEVEL')
    bev.width = 0.1
    bpy.ops.mesh.primitive_cube_add(location=(0, 6, 0))
    c = bpy.context.object
    d = c.copy()
    bpy.context.collection.objects.link(d)
    c.scale = (3, 3, 3)
    d.scale = (1.5, 1.5, 1.5)  # same mesh, other scale
    child = bpy.data.objects.new("Child", None)
    bpy.context.collection.objects.link(child)
    child.parent = a
    child.location = (1, 0, 0)
    bpy.context.view_layer.update()
    child_world = child.matrix_world.translation.copy()
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in (a, b, c, d):
        o.select_set(True)
    bpy.context.view_layer.objects.active = a
    res = bpy.ops.object.smart_apply_scale()
    bpy.context.view_layer.update()
    xs = [v.co.x for v in a.data.vertices]
    check("Smart Apply Scale: objects sharing a mesh with the same scale keep sharing it",
          res == {'FINISHED'} and a.data == b.data and tuple(a.scale) == (1, 1, 1) and abs(max(xs) - 2) < 1e-5,
          f"{res} {tuple(a.scale)} {max(xs):.3f}")
    check("Smart Apply Scale: modifiers are scaled to keep their look", abs(bev.width - 0.2) < 1e-6, bev.width)
    check("Smart Apply Scale: children stay where they were",
          (child.matrix_world.translation - child_world).length < 1e-5)
    check("Smart Apply Scale: shared meshes with other scales get their own copy, and all are applied",
          c.data != d.data and tuple(c.scale) == (1, 1, 1) and tuple(d.scale) == (1, 1, 1)
          and abs(max(v.co.x for v in c.data.vertices) - 3) < 1e-5 and abs(max(v.co.x for v in d.data.vertices) - 1.5) < 1e-5)


def test_rebevel():
    def bevelled_cube(segs):
        clear_scene()
        bpy.ops.mesh.primitive_cube_add(size=2)
        obj = bpy.context.object
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(obj.data)
        for elems in (bm.verts, bm.edges, bm.faces):
            for e in elems:
                e.select = False
        # the top front edge: y = -1, z = 1
        e = next(e for e in bm.edges if all(abs(v.co.y + 1) < 1e-4 and abs(v.co.z - 1) < 1e-4 for v in e.verts))
        e.select = True
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.select_mode(type='EDGE')
        bpy.ops.mesh.bevel(offset=0.2, segments=segs, affect='EDGES')
        bpy.ops.mesh.select_mode(type='FACE')  # the bevel's faces stay selected
        return obj

    obj = bevelled_cube(3)
    res = bpy.ops.keyops.rebevel(segments=0)
    bm = bmesh.from_edit_mesh(obj.data)
    corners = sorted(tuple(round(c, 4) for c in v.co) for v in bm.verts)
    check("Re-Bevel: Remove folds a bevel back into the sharp cube corner",
          res == {'FINISHED'} and len(bm.verts) == 8 and (0.0, 0.0, 0.0) not in corners
          and all(abs(abs(c) - 1) < 1e-4 for p in corners for c in p), f"{res} {len(bm.verts)}")
    obj = bevelled_cube(3)
    res = bpy.ops.keyops.rebevel(segments=5)
    bm = bmesh.from_edit_mesh(obj.data)
    sel = [f for f in bm.faces if f.select]
    check("Re-Bevel: same bevel with 5 segments (same width)", res == {'FINISHED'} and len(sel) == 5
          and len(bm.verts) == 8 - 2 + 2 * 6, f"{res} faces {len(sel)} verts {len(bm.verts)}")
    xs = sorted({round(v.co.z, 3) for v in bm.verts if abs(v.co.x - 1) < 1e-4 and v.co.y < -0.5})
    check("Re-Bevel: keeps the bevel's width", any(abs(z - 0.8) < 1e-3 for z in xs), str(xs))
    bpy.ops.object.mode_set(mode='OBJECT')

    # a bevel around a cylinder cap: two closed rails
    clear_scene()
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, depth=2, end_fill_type='NGON')
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for elems in (bm.verts, bm.edges, bm.faces):
        for e in elems:
            e.select = False
    for e in bm.edges:
        if all(abs(v.co.z - 1) < 1e-4 for v in e.verts):
            e.select = True
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.mesh.select_mode(type='EDGE')
    bpy.ops.mesh.bevel(offset=0.1, segments=2, affect='EDGES')
    bpy.ops.mesh.select_mode(type='FACE')
    res = bpy.ops.keyops.rebevel(segments=4)
    bm = bmesh.from_edit_mesh(obj.data)
    check("Re-Bevel: a bevel around a cylinder cap goes from 2 to 4 segments",
          res == {'FINISHED'} and len([f for f in bm.faces if f.select and len(f.verts) == 4]) == 24 * 4,
          f"{res} {len([f for f in bm.faces if f.select and len(f.verts) == 4])}")
    bpy.ops.object.mode_set(mode='OBJECT')


def test_alt_c_screw_and_instances():
    clear_scene()
    # a profile of edges with a Screw modifier whose surface faces inward
    obj = mesh_object("Profile", [(1, 0, -1), (1, 0, 0), (1, 0, 1)], [(0, 1), (1, 2)])
    scr = obj.modifiers.new("Screw", 'SCREW')
    scr.use_normal_flip = False
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    mc = sub("operators.mesh_cleanup")
    inward = mc._points_inward(obj, dg)
    scr.use_normal_flip = not inward  # start from the wrong way round (facing inward)
    edit_select_all(obj)
    res = bpy.ops.keyops.mesh_cleanup()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    check("Alt C on a Screw profile keeps the profile edges", len(obj.data.edges) == 2, len(obj.data.edges))
    check("Alt C on a Screw profile flips the modifier's normals instead",
          scr.use_normal_flip == inward and not mc._points_inward(obj, bpy.context.evaluated_depsgraph_get()))

    clear_scene()
    coll = bpy.data.collections.new("Asset")
    bpy.context.scene.collection.children.link(coll)
    me = bpy.data.meshes.new("AssetMesh")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    part = bpy.data.objects.new("Part", me)
    coll.objects.link(part)
    part.modifiers.new("Solidify", 'SOLIDIFY')
    inst = bpy.data.objects.new("Instance", None)
    inst.instance_type = 'COLLECTION'
    inst.instance_collection = coll
    inst.location = (5, 0, 0)
    bpy.context.collection.objects.link(inst)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    inst.select_set(True)
    bpy.context.view_layer.objects.active = inst
    bpy.ops.keyops.toolkit_panel(type="Instant_Apply_Modifiers")
    real = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    check("Alt C on a collection instance: makes its objects real and applies their modifiers",
          len(real) == 1 and not real[0].modifiers and len(real[0].data.polygons) > 1
          and abs(real[0].matrix_world.translation.x - 5) < 1e-5 and "Instance" not in bpy.data.objects,
          f"{[(o.name, len(o.modifiers)) for o in real]}")
    check("Alt C on a collection instance: the collection itself is untouched",
          len(part.modifiers) == 1 and len(me.polygons) == 1)


def _trim_case(name, build, select, **props):
    """Build a mesh, select edges, run Make Edge Trim (Mixed, separate) and measure the trim against the source."""
    from mathutils.bvhtree import BVHTree
    clear_scene()
    obj = build()
    bpy.ops.object.mode_set(mode='OBJECT')
    src = BVHTree.FromPolygons([v.co.copy() for v in obj.data.vertices], [tuple(p.vertices) for p in obj.data.polygons])
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for elems in (bm.verts, bm.edges, bm.faces):
        for e in elems:
            e.select = False
    for e in bm.edges:
        if select(e):
            e.select = True
    bmesh.update_edit_mesh(obj.data)
    res = bpy.ops.keyops.edge_trim(**props)
    bpy.ops.object.mode_set(mode='OBJECT')
    trims = [o for o in bpy.data.objects if o is not obj and o.type == 'MESH']
    if res != {'FINISHED'} or len(trims) != 1:
        return None, obj, res
    return trims[0], obj, src


def _trim_stats(trim, src):
    me = trim.data
    off = max((src.find_nearest(v.co)[3] for v in me.vertices), default=0.0) if src is not None else 0.0
    min_area = min((p.area for p in me.polygons), default=0.0)
    facing = []
    if src is not None:
        for p in me.polygons:
            hit = src.find_nearest(p.center)
            if hit[0] is not None and hit[3] < 1e-4:
                facing.append(p.normal.dot(hit[1]))
    return off, min_area, facing


def test_edge_trim():
    def cube():
        bpy.ops.mesh.primitive_cube_add(size=2)
        bpy.ops.object.mode_set(mode='EDIT')
        return bpy.context.object

    def sloped_cylinder():
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, depth=2, end_fill_type='NGON')
        obj = bpy.context.object
        for v in obj.data.vertices:
            if v.co.z > 0:
                v.co.z += 0.6 * v.co.x  # the top cap slopes down
        bpy.ops.object.mode_set(mode='EDIT')
        return obj

    def floor_wall():
        obj = mesh_object("Corner", [(-1, 0, 0), (1, 0, 0), (1, 2, 0), (-1, 2, 0), (1, 0, 2), (-1, 0, 2)], [],
                          [(0, 1, 2, 3), (1, 0, 5, 4)])
        bpy.ops.object.mode_set(mode='EDIT')
        return obj

    def ngon():
        import math
        obj = mesh_object("Ngon", [(math.cos(i / 8 * 6.2832), math.sin(i / 8 * 6.2832), 0) for i in range(8)], [],
                          [tuple(range(8))])
        bpy.ops.object.mode_set(mode='EDIT')
        return obj

    top = lambda e: all(v.co.z > 0.99 for v in e.verts)
    # (name, build, select, how far off the surface a point may be: the sloped cylinder's side quads aren't
    # flat any more, so a flat flange can only follow them to a fraction of a millimetre; None: a border edge's
    # second flange stands up by design)
    cases = [
        ("cube top loop", cube, top, 1e-4),
        ("sloped n-gon cylinder top", sloped_cylinder, lambda e: all(v.co.z > 0.3 for v in e.verts), 1e-3),
        ("inside corner (floor meets wall)", floor_wall,
         lambda e: all(abs(v.co.y) < 1e-4 and abs(v.co.z) < 1e-4 for v in e.verts), 1e-4),
        ("n-gon border", ngon, lambda e: True, None),
    ]
    for name, build, select, tol in cases:
        trim, obj, src = _trim_case(name, build, select)
        if trim is None:
            check(f"Edge Trim ({name}): makes a trim", False, str(src))
            continue
        off, min_area, facing = _trim_stats(trim, src)
        if tol is not None:
            check(f"Edge Trim ({name}): every trim point lies on the surface (no clipping)", off < tol, f"{off:.5f}")
        else:
            on = sum(1 for v in trim.data.vertices if src.find_nearest(v.co)[3] < 1e-4)
            check(f"Edge Trim ({name}): one flange on the face, one standing up", on * 3 >= len(trim.data.vertices) * 2 - 1,
                  f"{on}/{len(trim.data.vertices)}")
        check(f"Edge Trim ({name}): no collapsed faces", min_area > 1e-6, f"{min_area:.2e}")
        check(f"Edge Trim ({name}): trim faces point the same way as the faces under them",
              facing and min(facing) > 0.99, f"{min(facing) if facing else None}")
        sharp = [e for e in trim.data.edges if e.use_edge_sharp]
        check(f"Edge Trim ({name}): smooth, no sharp edges", not sharp and all(p.use_smooth for p in trim.data.polygons))

    # loose wire chain: still a trim
    trim, obj, src = _trim_case("wire", lambda: mesh_object("Wire", [(0, 0, 0), (1, 0, 0), (1, 1, 0)], [(0, 1), (1, 2)]),
                                lambda e: True)
    check("Edge Trim (loose edges): makes a trim", trim is not None and len(trim.data.polygons) == 4)

    # UVs keep their aspect: U per metre along the trim matches V per metre across it
    trim, obj, src = _trim_case("uv", cube, top, width_a=0.1, v_min=0.0, v_max=0.2)
    uv = trim.data.uv_layers.active.data
    p = max(trim.data.polygons, key=lambda p: p.area)
    loops = list(p.loop_indices)
    pts = [trim.data.vertices[trim.data.loops[i].vertex_index].co for i in loops]
    uvs = [uv[i].uv for i in loops]
    ratios = []
    for a in range(4):
        b = (a + 1) % 4
        d3 = (pts[b] - pts[a]).length
        d2 = (uvs[b] - uvs[a]).length
        if d3 > 1e-6:
            ratios.append(d2 / d3)
    check("Edge Trim: UVs are not stretched along the trim (Keep Aspect)", max(ratios) - min(ratios) < 1e-3,
          str([round(r, 4) for r in ratios]))


# ---------------------------------------------------------------- Phase 3

def test_attribute_ops():
    clear_scene()
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=10, y_subdivisions=10)
    obj = bpy.context.object
    me = obj.data
    me.attributes.new("Weight", 'FLOAT', 'POINT')
    me.attributes.new("Tag", 'BOOLEAN', 'FACE')
    me.attributes.new("Dir", 'FLOAT_VECTOR', 'EDGE')
    me.attributes.new("Paint", 'BYTE_COLOR', 'CORNER')
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(me)
    for f in bm.faces:
        f.select_set(f.index < 10)
    bmesh.update_edit_mesh(me)
    wm = bpy.context.window_manager

    def run_on(name, action):
        me.attributes.active = me.attributes[name]
        return bpy.ops.keyops.atri_op(type=action)

    r = run_on("Tag", "Assign")
    bpy.ops.mesh.select_all(action='DESELECT')
    r2 = run_on("Tag", "Select")
    bm = bmesh.from_edit_mesh(me)
    check("Attributes: boolean Assign then Select picks the same faces",
          r == r2 == {'FINISHED'} and sum(f.select for f in bm.faces) == 10)
    r3 = run_on("Tag", "Deselect")
    bm = bmesh.from_edit_mesh(me)
    check("Attributes: Deselect", r3 == {'FINISHED'} and sum(f.select for f in bm.faces) == 0)
    for f in bm.faces:
        f.select_set(f.index < 3)
    bm.select_flush(True)
    bmesh.update_edit_mesh(me)
    want_v = sum(v.select for v in bm.verts)
    want_e = sum(e.select for e in bm.edges)
    wm.float_value = 0.5  # the live update assigns it
    me.attributes.active = me.attributes["Weight"]
    run_on("Weight", "Assign")
    wm.keyops_vector_value = (1, 2, 3)
    r_v = run_on("Dir", "Assign")
    wm.float_color_value = (1, 0, 0, 1)
    r_c = run_on("Paint", "Assign")
    bpy.ops.object.mode_set(mode='OBJECT')
    w = [d.value for d in me.attributes["Weight"].data]
    dirs = [tuple(d.vector) for d in me.attributes["Dir"].data]
    cols = [tuple(round(c, 2) for c in d.color) for d in me.attributes["Paint"].data]
    check("Attributes: float value on the selected vertices", w.count(0.5) == want_v, f"{w.count(0.5)} of {want_v}")
    check("Attributes: vector on the selected edges", r_v == {'FINISHED'} and dirs.count((1.0, 2.0, 3.0)) == want_e,
          f"{dirs.count((1.0, 2.0, 3.0))} of {want_e}")
    check("Attributes: byte color on the selected faces' corners",
          r_c == {'FINISHED'} and sum(1 for c in cols if c[0] > 0.99 and c[1] < 0.01) == 12, str(cols[:2]))
    bpy.ops.object.mode_set(mode='EDIT')
    r_g = bpy.ops.keyops.atri_op(type="Face")
    bpy.ops.object.mode_set(mode='OBJECT')
    g = me.attributes.get("Face_Group")
    check("Attributes: Face Group makes a boolean face attribute set on the selection",
          r_g == {"FINISHED"} and g is not None and sum(d.value for d in g.data) == 3, f"{r_g} {g and sum(d.value for d in g.data)}")


def test_menu_preview_mode():
    pm = sub("pie_menus")
    prefs = sub("utils.pref_utils").get_keyops_prefs()
    pie = pm._new_pie(prefs)
    pie.name, pie.menu_type = "Preview Test", "MENU"
    a = pie.items.add()
    a.kind, a.idname, a.label, a.show_if = pm.O, "mesh.subdivide", "Edit Only", "mode == 'EDIT_MESH'"
    b = pie.items.add()
    b.kind, b.idname, b.label = pm.O, "object.join", "Always"
    wm = bpy.context.window_manager
    wm.keyops_preview_mode = 'EDITING'
    every = not pm.preview_hidden(a) and not pm.preview_hidden(b)
    wm.keyops_preview_mode = 'OBJECT'
    obj_mode = pm.preview_hidden(a) and not pm.preview_hidden(b)
    wm.keyops_preview_mode = 'EDIT_MESH'
    edit_mode = not pm.preview_hidden(a)
    sc = sub("ui.menu_canvas").build_menu(pie)
    wm.keyops_preview_mode = 'OBJECT'
    sc2 = sub("ui.menu_canvas").build_menu(pie)
    wm.keyops_preview_mode = 'EDITING'
    check("Custom Menus Preview In: items whose Poll is false in that mode are hidden, Every Item shows all",
          every and obj_mode and edit_mode and len(sc2.els) < len(sc.els), f"{every} {obj_mode} {edit_mode} {len(sc.els)} {len(sc2.els)}")
    prefs.pies.remove(list(prefs.pies).index(pie))


def test_menu_preview_submenu_edit():
    pm = sub("pie_menus")
    mc = sub("ui.menu_canvas")
    prefs = sub("utils.pref_utils").get_keyops_prefs()
    parent = pm._new_pie(prefs)
    parent.name, parent.menu_type = "Parent", "MENU"
    child = pm._new_pie(prefs)
    child.name, child.menu_type = "Child", "MENU"
    parent = pm.find_pie(parent.uid)
    a = parent.items.add()
    a.kind, a.idname, a.label = pm.O, "object.join", "Join"
    s_ = parent.items.add()
    s_.kind, s_.idname, s_.label = pm.SUB, child.uid, "More"
    c = child.items.add()
    c.kind, c.idname, c.label = pm.O, "object.delete", "Delete"
    prefs.active_pie = list(prefs.pies).index(parent)
    prefs.pie_slot = 1  # the submenu item: the preview opens its submenu beside it
    pies = mc.menu_chain(parent, prefs)
    opened = [p.uid for p in pies] == [parent.uid, child.uid]
    switched = mc.edit_chain_menu(2 * mc.SUB_STRIDE + 0)  # click Delete in the submenu
    edits_child = pm._active_pie(prefs).uid == child.uid and prefs.pie_slot == 0
    still = [p.uid for p in mc.menu_chain(pm._active_pie(prefs), prefs)] == [parent.uid, child.uid]
    check("Custom Menus preview: clicking an item of a submenu edits that submenu, the menu above stays open",
          opened and switched and edits_child and still, f"{opened} {switched} {edits_child} {still}")
    moved = mc.move_item_to_menu(child, 0, parent, 0)  # drag Delete up into the parent menu
    check("Custom Menus preview: an item dragged into the menu beside it moves there",
          moved and len(child.items) == 0 and parent.items[0].idname == "object.delete" and len(parent.items) == 3,
          f"{moved} {[i.idname for i in parent.items]}")
    loop = mc.move_item_to_menu(parent, 2, child, 0)  # the submenu item into its own submenu: refused
    check("Custom Menus preview: a submenu can't be dropped into itself", not loop and len(child.items) == 0)
    for p in (child, parent):
        prefs.pies.remove(list(prefs.pies).index(pm.find_pie(p.uid)))


def test_attribute_view():
    """The Attributes panel's reading side: active value, mixed values, Geometry Nodes limits."""
    V = sub("operators.atri_view")
    A = sub("operators.atri_op")
    clear_scene()
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=4, y_subdivisions=4)
    obj = bpy.context.object
    me = obj.data
    w = me.attributes.new("Width", 'FLOAT', 'POINT')
    for i, d in enumerate(w.data):
        d.value = 0.1 * (i % 3)
    me.attributes.active = me.attributes["Width"]
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(me)
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        v.select_set(v.index in (0, 3))   # values 0.0 and 0.0
    bm.select_history.clear()
    bm.select_history.add(bm.verts[1])
    bm.verts[1].select_set(True)          # value 0.1, active
    bmesh.update_edit_mesh(me)
    data = V.take_snapshot(obj)
    active, text = V.summary(data)
    check("Attributes: the active vertex's value is shown", active is not None and abs(float(active) - 0.1) < 1e-4, str(active))
    check("Attributes: a selection holding different values says so", text.startswith("Mixed (2 values)"), text)
    for v in bm.verts:
        v.select_set(v.index in (0, 3))
    bm.select_history.clear()
    bmesh.update_edit_mesh(me)
    data = V.take_snapshot(obj)
    active, text = V.summary(data)
    check("Attributes: one shared value is shown as such", active is None and text == "All 2 selected: 0", f"{active} {text}")
    # a Geometry Nodes input that reads the attribute gives the value field its limits and units
    ng = bpy.data.node_groups.new("AttrLimits", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    sock = ng.interface.new_socket("Trim Width", in_out="INPUT", socket_type="NodeSocketFloat")
    sock.subtype, sock.min_value, sock.max_value = 'DISTANCE', 0.0, 0.5
    mod = obj.modifiers.new("Limits", 'NODES')
    mod.node_group = ng
    sub("operators.toolkit_panel").set_gn_attribute_input(obj, mod, "Trim Width", "Width")
    m2, found = V.linked_socket(obj, "Width")
    spec = V.socket_spec(found)
    check("Attributes: finds the Geometry Nodes input reading the attribute", m2 == mod and spec["unit"] == 'LENGTH'
          and spec["max"] == 0.5, str(spec))
    A._apply_spec(spec)
    wm = bpy.context.window_manager
    rna = wm.bl_rna.properties["float_value"]
    A._quiet["on"] = True
    wm.float_value = 3.0
    A._quiet["on"] = False
    check("Attributes: the value field takes the input's min, max and units", rna.hard_max == 0.5 and rna.subtype == 'DISTANCE'
          and abs(wm.float_value - 0.5) < 1e-6, f"{rna.hard_max} {rna.subtype} {wm.float_value}")
    A._apply_spec(None)
    check("Attributes: without such an input the field is plain again", wm.bl_rna.properties["float_value"].subtype == 'NONE')
    # Use Active Value
    for v in bm.verts:
        v.select_set(v.index == 2)
    bm.select_history.clear()
    bm.select_history.add(bm.verts[2])
    bmesh.update_edit_mesh(me)
    A._quiet["on"] = True
    wm.float_value = 0.9
    A._quiet["on"] = False
    data = V.take_snapshot(obj, positions=False)
    A._set_field("FLOAT", V.active_value(data))
    bpy.ops.object.mode_set(mode='OBJECT')
    vals = [round(d.value, 4) for d in me.attributes["Width"].data]
    bpy.ops.object.mode_set(mode='EDIT')
    check("Attributes: the Value field shows the active element's value, without assigning it",
          abs(wm.float_value - 0.2) < 1e-5 and vals[2] == 0.2 and vals.count(0.2) == sum(1 for i in range(len(vals)) if i % 3 == 2),
          f"{wm.float_value} {vals[:6]}")
    # a color attribute shows with Blender's own Solid shading (no overlay of Key Ops' own)
    me.color_attributes.new("Paint", 'BYTE_COLOR', 'CORNER')
    me.attributes.active = me.attributes["Paint"]
    check("Attributes: no viewport overlay of its own (only Blender's shading)", not hasattr(V, "_draw_view")
          and not hasattr(bpy.types.WindowManager, "keyops_attr_show_numbers"))
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.node_groups.remove(ng)


def test_parent_used_objects_unique():
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
    a = bpy.context.object
    a.name = "A"
    bpy.ops.mesh.primitive_cube_add(location=(5, 0, 0))
    b = bpy.context.object
    b.name = "B"
    bpy.ops.mesh.primitive_cylinder_add(location=(2.5, 0, 0))
    cut = bpy.context.object
    cut.name = "SharedCutter"
    for o in (a, b):
        m = o.modifiers.new("Boolean", 'BOOLEAN')
        m.object = cut
    for o in bpy.context.selected_objects:
        o.select_set(False)
    a.select_set(True)
    bpy.context.view_layer.objects.active = a
    res = bpy.ops.keyops.parent_used_objects(make_unique=True)
    new = a.modifiers["Boolean"].object
    check("Parent Used Objects (Make Unique): the selected object gets its own copy of a shared cutter",
          res == {'FINISHED'} and new is not cut and new.parent == a and new.data is not cut.data)
    check("Parent Used Objects (Make Unique): the other object keeps the original, unparented",
          b.modifiers["Boolean"].object is cut and cut.parent is None)
    check("Parent Used Objects (Make Unique): the copy stays where the cutter was",
          (new.matrix_world.translation - cut.matrix_world.translation).length < 1e-6)


def test_lattice_min_box():
    import math
    from mathutils import Matrix
    gmu = sub("utils.geometry_math_utils")
    # a box turned 30 degrees around Z and 20 around X: the minimum box finds its real size
    rot = Matrix.Rotation(math.radians(30), 3, 'Z') @ Matrix.Rotation(math.radians(20), 3, 'X')
    corners = [rot @ Vector((x * 2, y * 1, z * 0.5)) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    centre, r, size = gmu.min_oriented_box(corners)
    check("minimum box: a turned box is fitted at its own size (not the world-aligned box)",
          abs(size.x - 4) < 1e-3 and abs(size.y - 2) < 1e-3 and abs(size.z - 1) < 1e-3 and centre.length < 1e-4,
          str([round(v, 3) for v in size]))
    flat = [rot @ Vector((x, y, 0)) for x, y in ((0, 0), (3, 0), (3, 1), (0, 1), (1.5, 0.5))]
    centre, r, size = gmu.min_oriented_box(flat)
    check("minimum box: flat points are flat along the box's Z", size.z < 1e-4 and abs(size.x - 3) < 1e-3,
          str([round(v, 3) for v in size]))

    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)
    a = bpy.context.object
    a.rotation_euler = (0.3, 0.2, 0.5)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(4, 0, 0))
    b = bpy.context.object
    for o in (a, b):
        o.select_set(True)
    bpy.context.view_layer.objects.active = a
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    res = bpy.ops.keyops.add_modifier(type='LATTICE', min_box=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    lat = [o for o in bpy.data.objects if o.type == 'LATTICE']
    mods = [m for o in (a, b) for m in o.modifiers if m.type == 'LATTICE']
    check("Lattice (Edit Mode): every object with selected vertices gets the modifier, on its own group",
          res == {'FINISHED'} and len(lat) == 1 and len(mods) == 2
          and all(m.vertex_group in o.vertex_groups for o in (a, b) for m in o.modifiers if m.type == 'LATTICE'),
          f"{res} lattices {len(lat)} mods {len(mods)}")


def test_modifier_order():
    mo = sub("utils.modifier_order")
    clear_scene()
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    obj.modifiers.new("Weighted Normal", 'WEIGHTED_NORMAL')
    obj.modifiers.new("Triangulate", 'TRIANGULATE')
    pin = obj.modifiers.new("Pinned", 'DISPLACE')
    if hasattr(pin, "use_pin_to_last"):
        pin.use_pin_to_last = True
    bev = obj.modifiers.new("Bevel", 'BEVEL')
    mo.place_shape_modifier(obj, bev)
    mo.sort_shading_last(obj)
    names = [m.name for m in obj.modifiers]
    want = ["Bevel", "Triangulate", "Weighted Normal", "Pinned"] if hasattr(pin, "use_pin_to_last") else None
    check("modifier order: new shape modifier above shading, Triangulate before Weighted Normal, pinned last",
          want is None or names == want, str(names))
    check("modifier order: never moves a modifier into the pinned ones",
          not hasattr(pin, "use_pin_to_last") or not mo.can_move(obj, obj.modifiers["Weighted Normal"], 3))


def test_realign_rotation():
    import math
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)
    obj = bpy.context.object
    obj.scale = (1.0, 2.0, 0.5)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler = (math.radians(20), 0, math.radians(35))
    obj.location = (1, 2, 3)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)  # rotation frozen
    bpy.context.view_layer.update()
    before = sorted(tuple(round(c, 4) for c in obj.matrix_world @ v.co) for v in obj.data.vertices)
    res = bpy.ops.keyops.realign_rotation()
    bpy.context.view_layer.update()
    after = sorted(tuple(round(c, 4) for c in obj.matrix_world @ v.co) for v in obj.data.vertices)
    dims = sorted(round(d, 3) for d in obj.dimensions)
    check("Re-Align Rotation: nothing moves in the scene", res == {'FINISHED'} and before == after)
    check("Re-Align Rotation: the object gets back a rotation that matches the shape (tight box)",
          dims == [1.0, 2.0, 4.0] and abs(obj.rotation_euler.z) > 0.1, f"{dims} {tuple(round(r, 3) for r in obj.rotation_euler)}")
    check("Re-Align Rotation: stays upright (the axis closest to up is still up)",
          (obj.matrix_world.to_3x3() @ Vector((0, 0, 1))).z > 0.9)


def test_slide_scale():
    clear_scene()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0)
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    zs = sorted({round(v.co.z, 4) for v in bm.verts})
    ring_z = [z for z in zs if 0.3 < z < 0.6][0]  # a ring above the equator
    for v in bm.verts:
        v.select = abs(v.co.z - ring_z) < 1e-4
    bm.select_flush(True)
    bmesh.update_edit_mesh(obj.data)
    bpy.context.scene.tool_settings.transform_pivot_point = 'MEDIAN_POINT'
    res = bpy.ops.keyops.slide_scale(factor=0.8)
    bm = bmesh.from_edit_mesh(obj.data)
    ring = [v for v in bm.verts if v.select]
    radii = [v.co.length for v in ring]
    up = min(v.co.z for v in ring)
    check("Slide Scale: the ring slides along the sphere's edges (stays on the surface, moves up)",
          res == {'FINISHED'} and min(radii) > 0.97 and up > ring_z + 1e-3,
          f"radius {min(radii):.3f}..{max(radii):.3f} z {ring_z:.3f}->{up:.3f}")
    bpy.ops.object.mode_set(mode='OBJECT')


def test_full_edge_loop():
    dc = sub("operators.double_click_select_island")
    clear_scene()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    # a meridian edge next to the equator: Blender's loop select stops at the poles (triangle fans)
    e = next(e for e in bm.edges if abs(e.verts[0].co.x * e.verts[1].co.y - e.verts[0].co.y * e.verts[1].co.x) < 1e-6
             and abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-3 and min(abs(v.co.z) for v in e.verts) < 0.21
             and e.verts[0].co.x > 0.1)
    loop = dc.full_loop(e)
    check("full edge loop: a meridian on a UV sphere runs through both poles (a whole great circle)",
          len(loop) == 32, f"{len(loop)} edges")
    bpy.ops.object.mode_set(mode='OBJECT')


def test_macro_operator_params():
    pm = sub("pie_menus")
    prefs = sub("utils.pref_utils").get_keyops_prefs()
    pie = pm._new_pie(prefs)
    pie.name, pie.menu_type = "Macro Test", "MENU"
    prefs.active_pie = len(prefs.pies) - 1
    item = pie.items.add()
    item.kind = pm.MACRO
    step = item.steps.add()
    step.idname = "object.modifier_add"
    names = pm._param_names(pm._op_rna("object.modifier_add"))
    check("Operator Parameters: lists the operator's options (Add Modifier's type)", "type" in names, str(names))
    bridge = pm._param_names(pm._op_rna("mesh.bridge_edge_loops"))
    check("Operator Parameters: lists Bridge Edge Loops' options", {"type", "use_merge", "number_cuts", "twist_offset"} <= set(bridge),
          str(bridge))
    wm = bpy.context.window_manager
    last = wm.operator_properties_last("object.modifier_add")
    before = last.type
    last.type = 'BEVEL'
    res = bpy.ops.keyops.operator_params('EXEC_DEFAULT', slot=0, step=0, op_idname="object.modifier_add")
    check("Operator Parameters: the chosen options are written into the step", res == {'FINISHED'}
          and pm._parse_props(step.props).get("type") == 'BEVEL', step.props)
    check("Operator Parameters: the operator's own last-used values are put back", last.type == before or not last.is_property_set("type"))
    # the inline dropdown: fields load from the step, an edited field is stored in the step, closing gives back
    slot = list(prefs.pies).index(pie)
    key = (pie.uid, 0, 0)
    pm._inline_request(key)
    pm._inline_sync()
    loaded = pm._inline["key"] == key and last.type == 'BEVEL'
    last.type = 'ARRAY'
    pm._inline_request(key)
    pm._inline_sync()
    stored = pm._parse_props(step.props).get("type") == 'ARRAY'
    step.props = "type='MIRROR'"  # typed in the text field: the fields follow
    pm._inline_request(key)
    pm._inline_sync()
    follows = last.type == 'MIRROR'
    pm._inline_close()
    check("Operator Parameters dropdown: loads the step's options, stores edited fields, follows typed text",
          loaded and stored and follows, f"{loaded} {stored} {follows} {step.props}")
    check("Operator Parameters dropdown: closing puts the operator's last-used values back",
          last.type == before or not last.is_property_set("type"), last.type)
    prefs.pies.remove(slot)


def test_hide_ui():
    hu = sub("ui.hide_ui")
    name = "VIEW3D_PT_view3d_properties"
    cls = getattr(bpy.types, name)
    had_poll = "poll" in cls.__dict__
    res = bpy.ops.keyops.toggle_ui_element(element=name)
    hidden = cls.poll(bpy.context) is False
    prefs = sub("utils.pref_utils").get_keyops_prefs()
    check("Hide Blender UI: hides a panel (its poll says no) and remembers it", res == {'FINISHED'} and hidden
          and name in prefs.hidden_ui)
    bpy.ops.keyops.toggle_ui_element(element=name)
    check("Hide Blender UI: pressing again shows it, Blender's own poll is back",
          not hu.is_hidden(name) and ("poll" in cls.__dict__) == had_poll and name not in prefs.hidden_ui)
    menu = "VIEW3D_MT_view"
    bpy.ops.keyops.toggle_ui_element(element=menu)
    m = getattr(bpy.types, menu)
    check("Hide Blender UI: hides a menu (draws nothing)", m.draw is hu._draw_nothing)
    hu.show_all()
    check("Hide Blender UI: everything comes back when switched off", m.draw is not hu._draw_nothing and not hu.hidden_names())
    items = hu.ui_element_items(None, bpy.context)
    check("Hide Blender UI: the picker lists Blender's panels, menus and headers",
          any(i[0] == "VIEW3D_PT_overlay" for i in items) and any(i[0] == "VIEW3D_HT_header" for i in items), len(items))


def test_triplanar():
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)
    obj = bpy.context.object
    obj.scale = (2.0, 2.0, 2.0)  # World Scale: the texture keeps its size anyway
    res = bpy.ops.keyops.toolkit_panel(type="Triplanar_UV_Mapping", tri_size=1.0, appy_triplanar=True)
    me = obj.data
    uv = me.uv_layers.active.data
    mirrored, upside_down, spans = 0, 0, []
    for p in me.polygons:
        pts = [me.vertices[me.loops[i].vertex_index].co for i in p.loop_indices]
        uvs = [uv[i].uv.copy() for i in p.loop_indices]
        area = sum(uvs[i].x * uvs[(i + 1) % 4].y - uvs[(i + 1) % 4].x * uvs[i].y for i in range(4)) / 2
        mirrored += area < 0
        spans.append(round(max(u.x for u in uvs) - min(u.x for u in uvs), 4))
        if abs(p.normal.z) < 0.5:  # a side: V goes up with Z
            hi = max(range(4), key=lambda i: pts[i].z)
            lo = min(range(4), key=lambda i: pts[i].z)
            upside_down += uvs[hi].y < uvs[lo].y
    check("Triplanar: no side is mirrored", res == {'FINISHED'} and mirrored == 0, f"{mirrored} mirrored")
    check("Triplanar: the sides are upright (V goes up)", upside_down == 0, f"{upside_down} upside down")
    check("Triplanar: World Scale keeps the texture size (a 4 m face spans 4 tiles at 1 m)", set(spans) == {4.0}, str(set(spans)))
    check("Triplanar: the old modifier name is gone, the new group is used",
          bpy.data.node_groups.get("Triplanar UV") is not None)

    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for f in bm.faces:
        f.select_set(f.normal.z > 0.5)
    bmesh.update_edit_mesh(obj.data)
    res = bpy.ops.keyops.toolkit_panel(type="Triplanar_UV_Mapping", tri_size=0.5)
    bpy.ops.object.mode_set(mode='OBJECT')
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg).to_mesh()
    uvd = ev.uv_layers.active.data
    top = next(p for p in ev.polygons if p.normal.z > 0.5)
    side = next(p for p in ev.polygons if abs(p.normal.x) > 0.5)
    top_span = max(uvd[i].uv.x for i in top.loop_indices) - min(uvd[i].uv.x for i in top.loop_indices)
    side_span = max(uvd[i].uv.x for i in side.loop_indices) - min(uvd[i].uv.x for i in side.loop_indices)
    check("Triplanar (Edit Mode): only the selected faces get the new UVs",
          res == {'FINISHED'} and abs(top_span - 4.0) < 1e-4 and abs(side_span - 4.0) > 1e-3, f"top {top_span:.3f} side {side_span:.3f}")
    obj.evaluated_get(dg).to_mesh_clear()


def test_edge_trim_live():
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for e in bm.edges:
        e.select_set(all(v.co.z > 0.99 for v in e.verts))
    bmesh.update_edit_mesh(obj.data)
    res = bpy.ops.keyops.edge_trim_live(width=0.1, offset=0.0)
    trim = next((o for o in bpy.data.objects if o.name.endswith("_Trim")), None)
    bpy.ops.object.mode_set(mode='OBJECT')
    dg = bpy.context.evaluated_depsgraph_get()
    ev = trim.evaluated_get(dg).to_mesh() if trim else None
    faces = len(ev.polygons) if ev else 0
    on_cube = ev is not None and all(max(abs(c) for c in v.co) > 0.999 for v in ev.vertices)
    uv_ok = ev is not None and ev.uv_layers.get("UVMap") is not None
    check("Live Edge Trim: a trim object with a modifier sweeping the marked edges (8 faces round the top)",
          res == {'FINISHED'} and faces == 8, f"{res} faces {faces}")
    check("Live Edge Trim: wraps the top edges, lying on the cube's faces, with UVs", on_cube and uv_ok)
    if trim:
        trim.evaluated_get(dg).to_mesh_clear()
    # live: move a top vertex of the source and the trim follows
    obj.data.vertices[next(i for i, v in enumerate(obj.data.vertices) if v.co.z > 0.99)].co.z += 0.5
    obj.data.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev2 = trim.evaluated_get(dg).to_mesh()
    top = max(v.co.z for v in ev2.vertices)
    check("Live Edge Trim: follows changes to the source mesh", top > 1.2, f"top {top:.3f}")
    trim.evaluated_get(dg).to_mesh_clear()


def test_smart_extrude():
    def cube_top(subdiv=0):
        clear_scene()
        bpy.ops.mesh.primitive_cube_add(size=2)
        obj = bpy.context.object
        bpy.ops.object.mode_set(mode='EDIT')
        if subdiv:
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.subdivide(number_cuts=subdiv)
        bm = bmesh.from_edit_mesh(obj.data)
        for f in bm.faces:
            c = f.calc_center_median()
            f.select_set(f.normal.z > 0.9 and (not subdiv or (abs(c.x) < 0.4 and abs(c.y) < 0.4)))
        bmesh.update_edit_mesh(obj.data)
        return obj

    obj = cube_top()
    res = bpy.ops.keyops.push_pull(distance=0.5)
    bm = bmesh.from_edit_mesh(obj.data)
    check("Smart Extrude: square walls just stretch (push/pull), no new geometry",
          res == {'FINISHED'} and len(bm.verts) == 8 and abs(max(v.co.z for v in bm.verts) - 1.5) < 1e-5,
          f"{len(bm.verts)} verts, top {max(v.co.z for v in bm.verts):.3f}")
    obj = cube_top()
    res = bpy.ops.keyops.push_pull(distance=-0.5)
    bm = bmesh.from_edit_mesh(obj.data)
    check("Smart Extrude: pushing square walls in shortens them", abs(max(v.co.z for v in bm.verts) - 0.5) < 1e-5)

    obj = cube_top(subdiv=2)  # the middle top face: its neighbours are flat, not walls
    res = bpy.ops.keyops.push_pull(distance=-0.5)
    bm = bmesh.from_edit_mesh(obj.data)
    zs = sorted({round(v.co.z, 3) for v in bm.verts})
    sound = all(e.is_manifold for e in bm.edges)
    check("Smart Extrude: pushed into the surface it cuts a pocket (boolean difference), still closed",
          res == {'FINISHED'} and 0.5 in zs and sound and max(zs) == 1.0, f"{zs} manifold {sound}")
    obj = cube_top(subdiv=2)
    res = bpy.ops.keyops.push_pull(distance=0.5)
    bm = bmesh.from_edit_mesh(obj.data)
    inner = [f for f in bm.faces if abs(f.calc_center_median().z - 1.0) < 1e-4 and abs(f.calc_center_median().x) < 0.3
             and abs(f.calc_center_median().y) < 0.3]
    check("Smart Extrude: pulled out it adds a block (union), no faces left inside",
          res == {'FINISHED'} and abs(max(v.co.z for v in bm.verts) - 1.5) < 1e-4 and not inner
          and all(e.is_manifold for e in bm.edges), f"top {max(v.co.z for v in bm.verts):.3f} inner {len(inner)}")
    obj = cube_top()
    res = bpy.ops.keyops.smart_extrude(distance=0.5)
    bm = bmesh.from_edit_mesh(obj.data)
    check("Smart Extrude (its own tool): always extrudes, even with square walls (new geometry, still closed)",
          res == {'FINISHED'} and len(bm.verts) > 8 and abs(max(v.co.z for v in bm.verts) - 1.5) < 1e-4
          and all(e.is_manifold for e in bm.edges), f"{len(bm.verts)} verts")
    check("Smart Extrude: nothing left behind (no modifier, no cutter object)",
          not obj.modifiers and not any(o.name.startswith(".keyops_extrude") for o in bpy.data.objects))
    bpy.ops.object.mode_set(mode='OBJECT')


def test_node_group_versions():
    ng = sys.modules[MOD + ".utils.node_groups"]
    files = [os.path.basename(f) for f in ng.candidate_files()]
    check("Node groups: base file always last, newer files only up to this Blender",
          files[-1] == "node_groups.blend" and all(
              tuple(int(x) for x in f[len("node_groups_"):-len(".blend")].split("_")) <= bpy.app.version[:2]
              for f in files[:-1]), str(files))
    for g in [g for g in bpy.data.node_groups if g.name == "Edge Trim Live"]:
        bpy.data.node_groups.remove(g)
    group = ng.get_node_group("Edge Trim Live")
    gizmos = sum(1 for n in group.nodes if n.bl_idname == "GeometryNodeGizmoLinear")
    want = 3 if bpy.app.version >= (4, 3) else 0
    check(f"Node groups: Live Edge Trim has {want} viewport gizmos in this version", gizmos == want, str(gizmos))
    names = ["Delete Loose Edge", "Duplicate Linked Modifiers", "Extrude Edge By Normal", "Offset UV",
             "SharpFromUVIslands", "Triplanar UV", "Unwrap In Place Tool"]
    missing = []
    for name in names:
        try:
            ng.get_node_group(name)
        except Exception:  # noqa: BLE001
            missing.append(name)
    check("Node groups: every group loads in this version", not missing, str(missing))


def test_cutter_mirror_preview_joined():
    from types import SimpleNamespace
    ct = sys.modules[MOD + ".tools.cutter_tool"]
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)
    pivot = bpy.context.object
    # a box from x -0.3 to 0.7: it crosses the X mirror plane, so it overlaps its mirrored copy
    top = [Vector(c) for c in ((-0.3, -0.4, 1.2), (0.7, -0.4, 1.2), (0.7, 0.4, 1.2), (-0.3, 0.4, 1.2))]
    coords = top + [Vector((c.x, c.y, 0.5)) for c in top]
    fake = SimpleNamespace(mirror_object=pivot, mirror_x=True, mirror_y=False, mirror_z=False)
    fake._mirror_matrices = lambda: ct.Cutter._mirror_matrices(fake)
    fake._mirror_sides = lambda c: ct.Cutter._mirror_sides(fake, c)
    positions, tris, lines, _thin = ct.Cutter._joined_mirror_preview(fake, coords, False, 4)
    xs = [p.x for p in positions]
    seam = [i for i in range(0, len(lines), 2) if abs(lines[i].x) < 1e-6 and abs(lines[i + 1].x) < 1e-6]
    check("Cutter: mirrored copies that overlap preview as one piece (-0.7..0.7, no seam lines)",
          abs(min(xs) + 0.7) < 1e-5 and abs(max(xs) - 0.7) < 1e-5 and not seam and tris,
          f"x {min(xs):.3f}..{max(xs):.3f}, seam lines {len(seam)}")
    # centred exactly on the mirror plane: both halves stay
    mid = [Vector((c.x - 0.2, c.y, c.z)) for c in coords]
    positions, tris, lines, _thin = ct.Cutter._joined_mirror_preview(fake, mid, False, 4)
    xs = [p.x for p in positions]
    check("Cutter: a shape centred on the mirror plane previews whole", abs(min(xs) + 0.5) < 1e-5
          and abs(max(xs) - 0.5) < 1e-5, f"x {min(xs):.3f}..{max(xs):.3f}")
    # apart from each other: still two pieces, each a full box
    far = [Vector((c.x + 1.0, c.y, c.z)) for c in coords]
    positions, tris, lines, _thin = ct.Cutter._joined_mirror_preview(fake, far, False, 4)
    check("Cutter: mirrored copies apart stay two boxes", len(positions) == 16 and len(lines) == 2 * 24,
          f"{len(positions)} points, {len(lines) // 2} lines")


def test_cutter_array():
    from types import SimpleNamespace
    ct = sys.modules[MOD + ".tools.cutter_tool"]
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)
    target = bpy.context.object
    plane = Matrix.Translation((0.0, 0.0, 1.0))
    box = [Vector((-0.2, -0.1)), Vector((0.2, -0.1)), Vector((0.2, 0.1)), Vector((-0.2, 0.1))]
    fake = SimpleNamespace(array_count=3, array_axis='X', array_gap=0.5, plane=plane, _fixed_profile=box,
                           mirror_object=target, mirror_x=False, mirror_y=False, mirror_z=False)
    fake.profile = lambda: box
    mats = ct.Cutter._array_matrices(fake, box)
    xs = [round(m.translation.x, 4) for m in mats]
    check("Cutter array: copies spaced by the shape's width plus the gap (0.4 x 1.5)", xs == [0.0, 0.6, 1.2], str(xs))
    fake.array_axis = 'Y'
    ys = [round(m.translation.y, 4) for m in ct.Cutter._array_matrices(fake, box)]
    check("Cutter array: along Y uses the shape's height", ys == [0.0, 0.3, 0.6], str(ys))
    fake.array_count = 1
    check("Cutter array: a count of 1 is no array", len(ct.Cutter._array_matrices(fake, box)) == 1)
    # the modifier: right before the Mirror modifier, relative offset matching the preview
    bpy.ops.mesh.primitive_cube_add(size=0.2)
    cutter = bpy.context.object
    cutter.modifiers.new("Mirror", 'MIRROR')
    fake.cutter, fake.array_count, fake.array_axis = cutter, 4, 'X'
    ct.Cutter._update_array_modifier(fake)
    mods = [m.type for m in cutter.modifiers]
    arr = cutter.modifiers.get("Array")
    check("Cutter array: an Array modifier before the Mirror modifier", mods == ['ARRAY', 'MIRROR'] and arr.count == 4
          and abs(arr.relative_offset_displace[0] - 1.5) < 1e-6, f"{mods} {arr and arr.count}")
    fake.array_count = 1
    ct.Cutter._update_array_modifier(fake)
    check("Cutter array: back to 1 removes the modifier", [m.type for m in cutter.modifiers] == ['MIRROR'])
    # Add in Edit Mode: three boxes go into the mesh
    bpy.context.view_layer.objects.active = target
    for o in bpy.context.selected_objects:
        o.select_set(o == target)
    bpy.ops.object.mode_set(mode='EDIT')
    before = len(target.data.vertices)
    bm = bmesh.from_edit_mesh(target.data)
    nverts = len(bm.verts)
    fake.array_count, fake.array_axis = 3, 'X'
    fake._profile_center = lambda: Vector((0.0, 0.0))
    fake._cutter_matrix = lambda c: ct.Cutter._cutter_matrix(fake, c)
    fake._mirror_matrices = lambda: ct.Cutter._mirror_matrices(fake)
    fake._mirror_sides = lambda c: ct.Cutter._mirror_sides(fake, c)
    fake._array_matrices = lambda prof=None: ct.Cutter._array_matrices(fake, prof)
    ct.Cutter._add_to_edit_mesh(fake, target, box, (0.0, 0.3))
    bm = bmesh.from_edit_mesh(target.data)
    new = [v for v in bm.verts if v.select]
    xs = sorted({round(v.co.x, 3) for v in new})
    check("Cutter array: Add in Edit Mode builds every copy", len(bm.verts) - nverts == 24 and xs[0] == -0.2 and xs[-1] == 1.4,
          f"{len(bm.verts) - nverts} new, x {xs}")
    bpy.ops.object.mode_set(mode='OBJECT')


def test_edge_trim_small_scale():
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)
    obj = bpy.context.object
    obj.scale = (0.1, 0.1, 0.1)
    bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for e in bm.edges:
        e.select_set(all(v.co.z > 0.99 for v in e.verts))
    bmesh.update_edit_mesh(obj.data)
    before = set(bpy.data.objects)
    bpy.ops.keyops.edge_trim(width_a=0.05, offset=0.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    new = [o.matrix_world @ v.co for o in set(bpy.data.objects) - before for v in o.data.vertices]
    zs = [p.z for p in new]
    span = max(zs) - min(zs) if zs else 0.0
    check("Edge Trim: corners keep their full width on an object at scale 0.1 (world z span 0.05)",
          abs(span - 0.05) < 2e-3, f"{span:.4f}")


def test_realign_linked_scales():
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=1)
    a = bpy.context.object
    a.rotation_euler = (0.3, 0.2, 0.7)
    bpy.ops.object.transform_apply(rotation=True)
    b = a.copy()  # a linked duplicate: same mesh, different scale
    bpy.context.collection.objects.link(b)
    a.scale = (1, 1, 2)
    b.scale = (1, 1, 3)
    b.location = (3, 0, 0)
    bpy.context.view_layer.update()

    def world_box(o):
        return sorted(tuple(round(c, 4) for c in (o.matrix_world @ v.co)) for v in o.data.vertices)
    before = (world_box(a), world_box(b))
    for o in bpy.context.selected_objects:
        o.select_set(False)
    a.select_set(True)
    b.select_set(True)
    bpy.context.view_layer.objects.active = a
    bpy.ops.keyops.realign_rotation(source='SHAPE')
    bpy.context.view_layer.update()
    check("Re-Align: linked duplicates with different scales keep their shape",
          (world_box(a), world_box(b)) == before, f"a {world_box(a)[:1]} b {world_box(b)[:1]}")


def test_fast_bevel_keys():
    fb = sub("operators.fast_bevel")
    check("Fast Bevel: number row 1 / 2 / 3 are the bevel types, no segment presets",
          fb.PRESET_KEYS == {'ONE': 1, 'TWO': 2, 'THREE': 3} and not hasattr(fb, "SEGMENT_KEYS"))
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)
    obj = bpy.context.object
    mod = obj.modifiers.new("Bevel", 'BEVEL')
    mod.segments = 4

    class Fake:
        def target_mods(self):
            return [(obj, mod)]

        def report(self, *a):
            pass

        def capture_base(self):
            pass
    fake = Fake()
    fake.unshade = lambda objs=None: fb.FastBevel.unshade(fake, objs)
    fb.FastBevel.preset(fake, 1)
    me = obj.data
    smooth = all(p.use_smooth for p in me.polygons)
    sharp = all(not e.use_edge_sharp for e in me.edges) is False
    check("Fast Bevel 1: one segment, Harden Normals, flat mesh shaded smooth with its corners kept hard",
          mod.segments == 1 and mod.harden_normals and mod.affect == 'EDGES' and smooth and sharp,
          f"seg {mod.segments} harden {mod.harden_normals} smooth {smooth} sharp {sharp}")
    fb.FastBevel.preset(fake, 3)
    flat = not any(p.use_smooth for p in me.polygons) and not any(e.use_edge_sharp for e in me.edges)
    check("Fast Bevel 3 after 1: the shading key 1 added is gone again (flat, no sharp marks)",
          flat and mod.segments == 2 and not mod.harden_normals)
    fb.FastBevel.preset(fake, 1)
    fake.unshade()  # what cancelling does
    check("Fast Bevel: cancelling puts the shading back", not any(p.use_smooth for p in me.polygons))


def test_realign_fresh_cube():
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)  # every face selected in the mesh data
    o = bpy.context.object
    o.rotation_euler = (0.3, 0.2, 0.7)
    bpy.ops.object.transform_apply(rotation=True)
    bpy.ops.keyops.realign_rotation()
    d = o.dimensions
    check("Re-Align: a cube whose rotation was applied gets its tight 2x2x2 box back (Object Mode)",
          all(abs(c - 2.0) < 1e-3 for c in d), f"{tuple(round(c, 3) for c in d)}")
    o.rotation_euler = (0.0, 0.0, 0.0)
    bpy.ops.object.transform_apply(rotation=True)
    for p in o.data.polygons:
        p.select = p.index == 0
    bpy.ops.keyops.realign_rotation(source='SELECTION')
    d = o.dimensions
    check("Re-Align: Selected Faces works from Object Mode too", all(abs(c - 2.0) < 1e-3 for c in d),
          f"{tuple(round(c, 3) for c in d)}")


def test_element_mode_sync():
    sm = sub("operators.subobject_modes")
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-2, 0, 0))
    a = bpy.context.object
    bpy.ops.mesh.primitive_cube_add(size=1, location=(2, 0, 0))
    b = bpy.context.object
    a.select_set(True)
    bpy.context.view_layer.objects.active = a
    bpy.ops.object.mode_set(mode='EDIT')
    # a second island in object a
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-2, 0, 3))
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_mode(type='VERT')
    objs = sm._edit_meshes(bpy.context)

    def bms():
        return [bmesh.from_edit_mesh(o.data) for o in objs]

    def snaps():
        return {o.name: sm.snapshot(bmesh.from_edit_mesh(o.data)) for o in objs}

    def sel_counts():
        return [sum(v.select for v in bm.verts) for bm in bms()]

    def set_verts(obj, test, value=True):
        bm = bmesh.from_edit_mesh(obj.data)
        for v in bm.verts:
            if test(v):
                v.select = value
        bm.select_flush(value)
        bmesh.update_edit_mesh(obj.data)

    lower_a = lambda v: v.co.z < 1.5
    snap = snaps()
    set_verts(a, lambda v: lower_a(v) and v.co.x < -0.4 and v.co.y < 0)  # one vertex of the lower island
    snap, changed = sm.sync(objs, snap, click=True, hint='pick')
    check("Element sync: a picked vertex selects its whole island, not the other island", changed and
          sel_counts()[objs.index(a)] == 8, str(sel_counts()))
    set_verts(a, lambda v: lower_a(v) and v.co.x < -0.4 and v.co.y < 0, False)
    snap, changed = sm.sync(objs, snap, click=True, hint='toggle')
    check("Element sync: unpicking part of an island unpicks all of it (Shift+click)", changed and
          sel_counts()[objs.index(a)] == 0, str(sel_counts()))
    set_verts(a, lower_a)
    snap, _c = sm.sync(objs, snap)
    # a plain box select inside the selected island: Blender keeps only the box contents
    set_verts(a, lambda v: lower_a(v) and v.co.x > -0.4, False)
    snap, changed = sm.sync(objs, snap, click=True, hint='pick')
    check("Element sync: a plain box select inside a selected island keeps the island", sel_counts()[objs.index(a)] == 8,
          str(sel_counts()))
    set_verts(a, lambda v: lower_a(v) and v.co.x > -0.4, False)
    snap, changed = sm.sync(objs, snap, click=False, hint='remove')
    check("Element sync: Ctrl box deselect over part of an island deselects it", sel_counts()[objs.index(a)] == 0,
          str(sel_counts()))
    # both objects at once (a box select across them)
    set_verts(a, lambda v: not lower_a(v) and v.co.x < -0.4)
    set_verts(b, lambda v: v.co.y < 0 and v.co.x > 0.4)
    snap, changed = sm.sync(objs, snap)
    check("Element sync: a box across two objects selects whole islands in both", sel_counts() == [8, 8]
          if objs.index(a) == 0 else sel_counts() == [8, 8], str(sel_counts()))
    # Face mode: deselecting one face of a selected island deselects the island
    bpy.ops.mesh.select_mode(type='FACE')
    bpy.ops.mesh.select_all(action='SELECT')
    snap = snaps()
    bm = bmesh.from_edit_mesh(a.data)
    f = next(f for f in bm.faces if f.calc_center_median().z > 1.5)
    f.select_set(False)
    bmesh.update_edit_mesh(a.data)
    snap, changed = sm.sync(objs, snap, click=True, hint='toggle')
    bm = bmesh.from_edit_mesh(a.data)
    upper = [f.select for f in bm.faces if f.calc_center_median().z > 1.5]
    lower = [f.select for f in bm.faces if f.calc_center_median().z < 1.5]
    check("Element sync: Face mode, unpicking one face unpicks its island only", not any(upper) and all(lower),
          f"upper {sum(upper)} lower {sum(lower)}")
    check("Element mode button has no redo panel", 'REGISTER' not in sm.KEYOPS_OT_sub_object_mode.bl_options)
    bpy.ops.object.mode_set(mode='OBJECT')


def test_rebevel_rework():
    def bevelled(kind, segs=3):
        clear_scene()
        if kind == "cylinder":
            bpy.ops.mesh.primitive_cylinder_add(vertices=24)
        else:
            bpy.ops.mesh.primitive_cube_add(size=2)
        obj = bpy.context.object
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='EDGE')
        bm = bmesh.from_edit_mesh(obj.data)
        for e in bm.edges:
            a, b = e.verts
            top = a.co.z > 0.9 and b.co.z > 0.9
            e.select = top and (kind != "edge" or (a.co.y > 0.9 and b.co.y > 0.9))
        bm.select_flush(True)
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.bevel(offset=0.2, segments=segs, affect='EDGES')
        bpy.ops.mesh.select_mode(type='FACE')
        return obj

    def key(obj):
        return sorted(tuple(round(c, 4) for c in v.co) for v in bmesh.from_edit_mesh(obj.data).verts)
    for kind in ("edge", "loop", "cylinder"):
        obj = bevelled(kind)
        k0 = key(obj)
        sel0 = {f.index for f in bmesh.from_edit_mesh(obj.data).faces if f.select}
        for _i in range(4):
            res = bpy.ops.keyops.rebevel(segments=3)
        k1 = key(obj)
        drift = max((abs(a - b) for p, q in zip(k0, k1) for a, b in zip(p, q)), default=0.0) if len(k0) == len(k1) else 9
        sel1 = sum(f.select for f in bmesh.from_edit_mesh(obj.data).faces)
        check(f"Re-Bevel ({kind}): four runs with the same settings move nothing", res == {'FINISHED'} and drift < 1e-4,
              f"{res} drift {drift}")
        bevel_faces = {"edge": 3, "loop": 12, "cylinder": 72}[kind]  # without a face the selection took along
        check(f"Re-Bevel ({kind}): only the bevel's faces stay selected", sel1 == bevel_faces, f"{len(sel0)} -> {sel1}")
        bpy.ops.object.mode_set(mode='OBJECT')
    obj = bevelled("edge")
    res = bpy.ops.keyops.rebevel(width=0.0)
    check("Re-Bevel: width 0 removes the bevel", len(bmesh.from_edit_mesh(obj.data).verts) == 8, str(res))
    bpy.ops.object.mode_set(mode='OBJECT')
    # Follow Loops: one face of a bevel around the cube top takes the whole bevel
    obj = bevelled("cylinder", segs=1)
    bm = bmesh.from_edit_mesh(obj.data)
    picked = next(f for f in bm.faces if f.select)
    for f in bm.faces:
        f.select = f is picked
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.keyops.rebevel(segments=2, follow_loops=True)
    sel = sum(f.select for f in bmesh.from_edit_mesh(obj.data).faces)
    check("Re-Bevel: Follow Loops re-bevels the whole bevel from one face", sel == 48, str(sel))
    bpy.ops.object.mode_set(mode='OBJECT')
    rb = sub("operators.rebevel").KEYOPS_OT_rebevel
    check("Re-Bevel: no Remove Bevel option any more", "remove" not in rb.__annotations__)


def test_lattice_best_fit_modes():
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)
    o = bpy.context.object
    o.rotation_euler = (0.3, 0.2, 0.7)
    bpy.ops.object.transform_apply(rotation=True)
    bpy.ops.keyops.add_modifier(type='LATTICE', min_box=True)
    lat = next(x for x in bpy.data.objects if x.type == 'LATTICE')
    check("Lattice Best Fit in Object Mode: tight box around the turned cube", all(abs(c - 2.02) < 0.01 for c in lat.scale),
          str(tuple(round(c, 3) for c in lat.scale)))
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2)
    o = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    o.select_set(False)  # in Edit Mode but not selected: still the object to work on
    poll = bpy.ops.keyops.add_modifier.poll()
    res = bpy.ops.keyops.add_modifier(type='LATTICE')
    check("Lattice in Edit Mode works on the objects being edited (selected or not)",
          poll and res == {'FINISHED'} and any(m.type == 'LATTICE' for m in o.modifiers), f"poll {poll} {res}")
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def test_realign_keeps_location():
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(3, 1, 2))
    o = bpy.context.object
    o.rotation_euler = (0.3, 0.2, 0.7)
    bpy.ops.object.transform_apply(rotation=True)
    bpy.ops.object.empty_add(location=(-1, 0, 0))
    parent = bpy.context.object
    parent.rotation_euler = (0, 0, 0.4)
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()
    loc_before = o.location.copy()
    world_before = o.matrix_world.translation.copy()
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    res = bpy.ops.keyops.realign_rotation()
    bpy.context.view_layer.update()
    check("Re-Align: one run does it, and only the rotation changes (location stays, also parented)",
          res == {'FINISHED'} and (o.location - loc_before).length < 1e-5
          and (o.matrix_world.translation - world_before).length < 1e-5 and all(abs(c - 2.0) < 1e-3 for c in o.dimensions),
          f"{res} loc {tuple(round(c, 4) for c in o.location)} dims {tuple(round(c, 3) for c in o.dimensions)}")


def test_parent_used_no_move():
    clear_scene()
    bpy.ops.object.empty_add(location=(5, 0, 0))
    root = bpy.context.object
    root.rotation_euler = (0, 0, 0.5)
    bpy.context.view_layer.update()
    objs = {}
    for name, loc in (("A", (0, 0, 0)), ("B", (3, 0, 0)), ("C", (0.4, 0, 0.4)), ("D", (0.5, 0.2, 0.6))):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        objs[name] = bpy.context.object
        objs[name].name = name
    for o in (objs["A"], objs["B"]):
        o.parent = root
        o.matrix_parent_inverse = root.matrix_world.inverted()
        o.modifiers.new("Bool", 'BOOLEAN').object = objs["C"]
    objs["C"].modifiers.new("Bool", 'BOOLEAN').object = objs["D"]
    bpy.context.view_layer.update()
    objs["C"].location = (0.6, 0.1, 0.4)  # moved just now: its matrix_world is out of date until the scene updates
    expect = {n: (o.parent.matrix_world if o.parent else Matrix()) @ o.matrix_parent_inverse @ o.matrix_basis
              for n, o in objs.items()}
    for o in bpy.context.selected_objects:
        o.select_set(False)
    objs["A"].select_set(True)
    bpy.context.view_layer.objects.active = objs["A"]
    bpy.ops.keyops.parent_used_objects(make_unique=True)
    bpy.context.view_layer.update()
    moved = [n for n, m in expect.items() if (objs[n].matrix_world.translation - m.translation).length > 1e-4]
    copies = [o for o in bpy.data.objects if o.name.startswith(("C.", "D."))]
    stray = [o.name for o in copies if min((o.matrix_world.translation - expect[o.name[0]].translation).length, 9) > 1e-4]
    check("Parent Used Objects (Make Unique): nothing moves, copies sit exactly on their originals",
          not moved and copies and not stray, f"moved {moved} stray {stray}")
    # C was parented to A by an earlier run and B uses it too: after Make Unique, B's cutter no longer follows A
    clear_scene()
    for name, loc in (("A", (0, 0, 0)), ("B", (3, 0, 0)), ("C", (0.4, 0, 0.4))):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        objs[name] = bpy.context.object
        objs[name].name = name
    for o in (objs["A"], objs["B"]):
        o.modifiers.new("Bool", 'BOOLEAN').object = objs["C"]
    for o in bpy.context.selected_objects:
        o.select_set(False)
    objs["A"].select_set(True)
    bpy.context.view_layer.objects.active = objs["A"]
    bpy.ops.keyops.parent_used_objects()
    c_world = objs["C"].matrix_world.copy()
    bpy.ops.keyops.parent_used_objects(make_unique=True)
    bpy.context.view_layer.update()
    check("Parent Used Objects (Make Unique): a cutter the selected object no longer uses lets go of it, in place",
          objs["C"].parent is None and (objs["C"].matrix_world.translation - c_world.translation).length < 1e-5,
          f"parent {objs['C'].parent}")


def test_slide_scale_lines_and_rotate():
    import math
    clear_scene()
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=1, depth=2)
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    side = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1.9]
    bmesh.ops.subdivide_edges(bm, edges=side, cuts=7, use_grid_fill=False)
    # a diagonal line across the side: one vertex per row, one column further each row, joined by cuts
    rows = sorted({round(v.co.z, 4) for v in bm.verts})
    diag = []
    for k, z in enumerate(rows):
        ang = math.radians(k * 360.0 / 32)
        diag.append(min((v for v in bm.verts if abs(v.co.z - z) < 1e-4),
                        key=lambda v: (v.co.x - math.cos(ang)) ** 2 + (v.co.y - math.sin(ang)) ** 2))
    for a, b in zip(diag, diag[1:]):
        bmesh.ops.connect_verts(bm, verts=[a, b])
    for v in bm.verts:
        v.select = False
    mid = diag[2:7]
    for v in mid:
        v.select = True
    bm.select_flush(True)
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.keyops.slide_scale(factor=1.6)
    bm = bmesh.from_edit_mesh(obj.data)
    radii = [math.hypot(v.co.x, v.co.y) for v in bm.verts if v.select]
    zs = sorted(v.co.z for v in bm.verts if v.select)
    check("Slide Scale: a diagonal line across a cylinder stays on the cylinder (and grows)",
          all(0.98 < r < 1.0001 for r in radii) and zs[-1] - zs[0] > 4 * (rows[1] - rows[0]) * 1.2,
          f"radius {min(radii):.4f}..{max(radii):.4f} span {zs[-1] - zs[0]:.3f}")
    bpy.ops.object.mode_set(mode='OBJECT')
    # Slide Rotate: a ring on a sphere turned around Z stays on the sphere
    clear_scene()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1)
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    zs = sorted({round(v.co.z, 4) for v in bm.verts})
    ring_z = [z for z in zs if 0.3 < z < 0.6][0]
    for v in bm.verts:
        v.select = abs(v.co.z - ring_z) < 1e-4
    bm.select_flush(True)
    bmesh.update_edit_mesh(obj.data)
    before = {v.index: v.co.copy() for v in bm.verts if v.select}
    bpy.ops.keyops.slide_scale(mode='ROTATE', angle=math.radians(5), axis='Z')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    moved = max((bm.verts[i].co - c).length for i, c in before.items())
    on = all(0.98 < bm.verts[i].co.length < 1.0001 for i in before)
    check("Slide Rotate: a ring on a sphere turns along the sphere's own edges, staying on it", moved > 0.01 and on,
          f"moved {moved:.3f}")
    bpy.ops.object.mode_set(mode='OBJECT')


def run():
    addon_utils.enable(MOD, default_set=True)
    for t in (test_revolve_axis, test_curve_tools, test_q_menu_migration, test_whats_new_not_automatic,
              test_header_element_button, test_duplicate_linked_in_object_menu,
              test_cylinder_sides_partial, test_none_live_booleans_undo, test_smart_apply_scale, test_rebevel,
              test_alt_c_screw_and_instances, test_edge_trim,
              test_attribute_ops, test_parent_used_objects_unique, test_lattice_min_box,
              test_modifier_order, test_realign_rotation, test_slide_scale,
              test_full_edge_loop, test_macro_operator_params, test_attribute_view, test_menu_preview_mode, test_menu_preview_submenu_edit, test_hide_ui,
              test_triplanar, test_edge_trim_live, test_smart_extrude, test_node_group_versions,
              test_cutter_mirror_preview_joined, test_cutter_array, test_edge_trim_small_scale,
              test_realign_linked_scales, test_fast_bevel_keys, test_realign_fresh_cube,
              test_element_mode_sync, test_rebevel_rework, test_lattice_best_fit_modes,
              test_realign_keeps_location, test_parent_used_no_move,
              test_slide_scale_lines_and_rotate):
        try:
            t()
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            check(f"{t.__name__} ran without errors", False, repr(e))


try:
    run()
except Exception:
    traceback.print_exc()
    results.append(("no exception", False, ""))

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
