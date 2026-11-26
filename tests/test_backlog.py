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


def run():
    addon_utils.enable(MOD, default_set=True)
    for t in (test_revolve_axis, test_curve_tools, test_q_menu_migration, test_whats_new_not_automatic,
              test_header_element_button, test_duplicate_linked_in_object_menu):
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
