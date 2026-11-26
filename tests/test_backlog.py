"""Headless checks for the backlog fixes and features (one section per card).

Run with the add-on installed as an extension in the user_default repository:
    blender -b --factory-startup --python tests/test_backlog.py
Exits non-zero on failure.
"""

import importlib
import sys
import traceback

import addon_utils
import bmesh
import bpy
from mathutils import Vector

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
    menus = bpy.types.VIEW3D_MT_editor_menus
    sm = sub("operators.subobject_modes")
    patched = "draw_collapsible" in menus.__dict__
    check("header: Element mode button drawn after Vertex/Edge/Face (editor menus patched)", patched)
    check("Element mode uses the linked icon", sm.ELEMENT_ICON == 'LINKED')


def test_duplicate_linked_in_object_menu():
    tp = sub("operators.toolkit_panel")
    fns = getattr(bpy.types.VIEW3D_MT_object, "_dyn_ui_initialize", lambda: [])()
    check("Object menu has Duplicate Linked Modifiers (same command as Alt+Shift+D)", tp.object_menu_duplicate in fns)


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
    res = bpy.ops.keyops.rebevel(remove=True)
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


def run():
    addon_utils.enable(MOD, default_set=True)
    for t in (test_revolve_axis, test_curve_tools, test_q_menu_migration, test_whats_new_not_automatic,
              test_header_element_button, test_duplicate_linked_in_object_menu,
              test_cylinder_sides_partial, test_none_live_booleans_undo, test_smart_apply_scale, test_rebevel,
              test_alt_c_screw_and_instances, test_edge_trim):
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
