"""Demo videos of Key Ops features, recorded in a real Blender window (see scripts/REMOTE_BLENDER.md).

    BLENDER_USER_RESOURCES=<profile> scripts/demo/record.sh <blender> scripts/demo/demos.py out.mp4 -- <demo name>

One demo per name in DEMOS. Each sets up a small scene, drives the feature with simulated input and shows a
caption, then quits.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
import harness as H  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

P = H.world_to_px


def view(rot=(1.1, 0, 0.7), loc=(0, 0, 0.5), dist=9.0, ortho=False):
    def fn(context):
        a = H.area()
        sp = a.spaces.active
        sp.overlay.show_stats = False
        sp.show_region_ui = False
        r3d = sp.region_3d
        r3d.view_perspective = 'ORTHO' if ortho else 'PERSP'
        r3d.view_rotation = Euler(rot).to_quaternion()
        r3d.view_location = loc
        r3d.view_distance = dist
    return fn


def clear(context):
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def prefs(**kw):
    def fn(context):
        p = H.prefs()
        for k, v in kw.items():
            setattr(p, k, v)
    return fn


def op(name, *args, **kw):
    def fn(context):
        mod, _dot, attr = name.partition(".")
        getattr(getattr(bpy.ops, mod), attr)(*args, **kw)
    return fn


def select_faces(test):
    def fn(context):
        bm = bmesh.from_edit_mesh(context.edit_object.data)
        for f in bm.faces:
            f.select_set(bool(test(f)))
        bmesh.update_edit_mesh(context.edit_object.data)
    return fn


def select_edges(test):
    def fn(context):
        bm = bmesh.from_edit_mesh(context.edit_object.data)
        for v in bm.verts:
            v.select = False
        for e in bm.edges:
            e.select_set(False)
        for e in bm.edges:
            if test(e):
                e.select_set(True)
        bmesh.update_edit_mesh(context.edit_object.data)
    return fn


# ---------------------------------------------------------------- the demos

def push_pull():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cube_add(size=2)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.subdivide(number_cuts=2)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.wm.tool_set_by_id(name="mesh.keyops_push_pull_tool")

    def one_face(x, y):
        return select_faces(lambda f: f.normal.z > 0.9 and (f.calc_center_median().xy - Vector((x, y))).length < 0.2)
    return [("call", prefs(enable_push_pull=True)), ("call", scene), ("call", view(rot=(1.15, 0, 0.55))), ("wait", 0.8),
            ("text", "Push / Pull tool: square walls just stretch"),
            ("drag", P((0.0, -1.0, 0.0)), P((0.0, -1.9, 0.0)), 1.2), ("wait", 0.8),
            ("text", "Smart Extrude pushed into a surface cuts a pocket"),
            ("call", one_face(0.0, 0.0)), ("move", P((0.0, 0.0, 1.0)), 0.3),
            ("call", op("keyops.smart_extrude", 'INVOKE_DEFAULT')), ("move", P((0.0, 0.0, 0.35)), 1.2),
            ("click", 'LEFTMOUSE'), ("wait", 0.8),
            ("text", "Pulled out it adds a block, no faces left inside"),
            ("call", one_face(0.67, 0.67)), ("move", P((0.67, 0.67, 1.0)), 0.3),
            ("call", op("keyops.smart_extrude", 'INVOKE_DEFAULT')), ("move", P((0.67, 0.67, 1.7)), 1.2),
            ("click", 'LEFTMOUSE'), ("wait", 1.5)]


def fast_bevel_keys():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cube_add(size=2)
    return [("call", scene), ("call", view(dist=7)), ("move", 0.6, 0.5, 0.2), ("wait", 0.5),
            ("text", "Fast Bevel: 1 hard normals (1 segment)"),
            ("call", op("keyops.fast_bevel", 'INVOKE_DEFAULT')), ("move", 0.66, 0.5, 0.6), ("wait", 0.4),
            ("key", 'ONE'), ("wait", 1.4),
            ("text", "3: conversion bevel"), ("key", 'THREE'), ("wait", 1.2),
            ("click", 'LEFTMOUSE'), ("wait", 1.0)]


def fast_array_end_to_end():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cube_add(size=1)
    return [("call", scene), ("call", view(loc=(1.5, 0, 0), dist=9)), ("move", 0.5, 0.5, 0.2), ("wait", 0.5),
            ("text", "Fast Array: drag, then 1 lines the copies up end to end"),
            ("call", op("keyops.fast_array", 'INVOKE_DEFAULT')), ("move", 0.7, 0.5, 0.8), ("key", 'C'),
            ("move", 0.62, 0.5, 0.6), ("wait", 0.6), ("key", 'ONE'), ("wait", 1.0),
            ("key", 'WHEELUPMOUSE'), ("key", 'WHEELUPMOUSE'), ("wait", 0.8),
            ("text", "Shift 2: a second array"), ("key", 'TWO', {"shift": True}), ("move", 0.6, 0.62, 0.6),
            ("wait", 0.8), ("click", 'LEFTMOUSE'), ("wait", 1.0)]


def cutter():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
        context.object.name = "Box"
        bpy.ops.mesh.primitive_cube_add(size=1, location=(3, 0, 0.5))
        for o in context.selected_objects:
            o.select_set(False)
        bpy.data.objects["Box"].select_set(True)
        context.view_layer.objects.active = bpy.data.objects["Box"]
        ct = sys.modules["bl_ext.user_default.Key_Ops_Toolkit.tools.cutter_tool"]
        bpy.ops.wm.tool_set_by_id(name=ct.TOOL_IDNAME)
        props = ct._tool_props(context)
        props.shape, props.operation, props.mirror_x = 'BOX', 'DIFFERENCE', True
    return [("call", prefs(enable_cutter_tool=True)), ("call", scene), ("call", view(rot=(0.6, 0, 0.4), loc=(1.4, 0, 0.6))),
            ("wait", 0.8), ("text", "Cutter: a click selects, a drag draws"),
            ("move", P((3, 0, 1)), 0.4), ("click", 'LEFTMOUSE'), ("wait", 0.8),
            ("move", P((0, 0, 2)), 0.4), ("click", 'LEFTMOUSE'), ("wait", 0.6),
            ("text", "Mirror X bisects at the mirror plane: one clean cut"),
            ("drag", P((-0.3, -0.5, 2)), P((0.8, 0.5, 2)), 1.0), ("move", P((0.3, 0, 1.2)), 0.8)] + \
        ([("shot", os.environ["DEMO_SHOT"])] if os.environ.get("DEMO_SHOT") else []) + \
        [("click", 'LEFTMOUSE'), ("wait", 1.6)]


def edge_trim():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, depth=2, end_fill_type='NGON')
        for v in context.object.data.vertices:
            if v.co.z > 0:
                v.co.z += 0.5 * v.co.x
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='EDGE')
    return [("call", scene), ("call", view(dist=7)), ("wait", 0.6),
            ("call", select_edges(lambda e: all(v.co.z > 0.3 for v in e.verts))), ("wait", 0.6),
            ("text", "Make Edge Trim (Mixed): the flanges follow the sloped faces"),
            ("call", op("keyops.edge_trim", width_a=0.12)), ("wait", 1.5),
            ("call", lambda c: bpy.ops.object.mode_set(mode='OBJECT')), ("wait", 1.0)]


def live_edge_trim():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cube_add(size=2)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='EDGE')

    def move_top(context):
        bm = bmesh.from_edit_mesh(context.edit_object.data)
        for v in bm.verts:
            v.select = v.co.z > 0.9 and v.co.x > 0.9
        bm.select_flush(True)
        bmesh.update_edit_mesh(context.edit_object.data)
    steps = [("call", scene), ("call", view(dist=8)), ("wait", 0.5),
             ("call", select_edges(lambda e: all(v.co.z > 0.99 for v in e.verts))), ("wait", 0.4),
             ("text", "Live Edge Trim: a Geometry Nodes trim that follows the mesh"),
             ("call", op("keyops.edge_trim_live", width=0.15)), ("wait", 0.8), ("call", move_top)]
    for i in range(12):
        steps += [("call", op("transform.translate", value=(0, 0, 0.06))), ("wait", 0.08)]
    return steps + [("wait", 1.5)]


def live_trim_gizmos():
    """Blender 4.3+: the live trim's Width / Second Width / Offset arrows in the viewport."""
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cube_add(size=2)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='EDGE')

    def to_trim(context):
        bpy.ops.object.mode_set(mode='OBJECT')
        trim = next(o for o in bpy.data.objects if o.name.endswith("_Trim"))
        for o in context.view_layer.objects:
            o.select_set(False)
        context.view_layer.objects.active = trim
        trim.select_set(True)

    widths = iter([0.18, 0.21, 0.24, 0.27, 0.3, 0.33])

    def widen(context):
        trim = context.view_layer.objects.active
        H.addon().operators.toolkit_panel.set_gn_input(trim.modifiers[0], "Width", next(widths))
        trim.update_tag()
    steps = [("call", scene), ("call", view(dist=7)), ("wait", 0.5),
             ("call", select_edges(lambda e: all(v.co.z > 0.99 for v in e.verts))), ("wait", 0.3),
             ("call", op("keyops.edge_trim_live", width=0.15)), ("wait", 0.5), ("call", to_trim), ("wait", 0.8),
             ("text", "Live Edge Trim (Blender 4.3+): drag the arrows for width and offset"), ("wait", 0.6)]
    shot = os.environ.get("DEMO_SHOT")
    if shot:
        steps.append(("shot", shot))
    for _i in range(6):
        steps += [("call", widen), ("wait", 0.25)]
    return steps + [("wait", 1.0)]


def cylinder_sides():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, depth=1.6, end_fill_type='NOTHING', location=(0, 0, 0.8))
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(context.edit_object.data)
        bottom = [e for e in bm.edges if all(abs(v.co.z + 0.8) < 1e-4 for v in e.verts)]
        ret = bmesh.ops.extrude_edge_only(bm, edges=bottom)
        nv = [v for v in ret["geom"] if isinstance(v, bmesh.types.BMVert)]
        for v in nv:
            v.co.x *= 2.2
            v.co.y *= 2.2
        outer = [e for e in ret["geom"] if isinstance(e, bmesh.types.BMEdge) and all(v in nv for v in e.verts)]
        bmesh.ops.subdivide_edges(bm, edges=outer[:2], cuts=1)
        bmesh.update_edit_mesh(context.edit_object.data)
        bpy.ops.mesh.select_mode(type='EDGE')
    return [("call", scene), ("call", view(dist=8, loc=(0, 0, 0.6))), ("wait", 0.5),
            ("call", select_edges(lambda e: all(abs(v.co.z - 0.8) < 1e-3 for v in e.verts))),
            ("text", "Set Cylinder Sides: joined to other geometry, the touching ring stays"),
            ("move", 0.5, 0.5, 0.2), ("call", op("keyops.set_cylinder_sides", 'INVOKE_DEFAULT')), ("wait", 0.4)] + \
        [("key", 'WHEELUPMOUSE') for _ in range(8)] + [("wait", 1.0), ("click", 'LEFTMOUSE'), ("wait", 1.2)]


def rebevel():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cube_add(size=2)
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(context.edit_object.data)
        for e in bm.edges:
            e.select_set(all(v.co.z > 0.99 for v in e.verts) and all(v.co.y < -0.99 for v in e.verts))
        bmesh.update_edit_mesh(context.edit_object.data)
        bpy.ops.mesh.select_mode(type='EDGE')
        bpy.ops.mesh.bevel(offset=0.4, segments=2, affect='EDGES')
        bpy.ops.mesh.select_mode(type='FACE')
    return [("call", scene), ("call", view(rot=(1.2, 0, 0.5), dist=7)), ("wait", 0.8),
            ("text", "Re-Bevel: 2 segments -> 8, same width"), ("call", op("keyops.rebevel", segments=8)),
            ("wait", 1.4), ("text", "Remove Bevel: back to the sharp corner"),
            ("call", op("keyops.rebevel", segments=0)), ("wait", 1.5)]


def slide_scale():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.5)
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(context.edit_object.data)
        zs = sorted({round(v.co.z, 4) for v in bm.verts})
        ring = [z for z in zs if 0.4 < z < 0.8][0]
        for v in bm.verts:
            v.select = abs(v.co.z - ring) < 1e-4
        bm.select_flush(True)
        bmesh.update_edit_mesh(context.edit_object.data)
    return [("call", scene), ("call", view(rot=(1.3, 0, 0.3), dist=7, loc=(0, 0, 0.3))), ("wait", 0.6),
            ("text", "Slide Scale: the ring slides along the sphere's own edges"),
            ("move", P((1.6, 0, 0.6)), 0.3), ("call", op("keyops.slide_scale", 'INVOKE_DEFAULT')),
            ("move", P((0.5, 0, 0.6)), 1.6), ("move", P((1.9, 0, 0.6)), 1.6), ("wait", 0.4),
            ("click", 'LEFTMOUSE'), ("wait", 1.2)]


def realign_rotation():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cube_add(size=1)
        o = context.object
        o.scale = (2, 1, 0.5)
        bpy.ops.object.transform_apply(scale=True)
        o.rotation_euler = (0.3, 0.2, 0.7)
        bpy.ops.object.transform_apply(rotation=True)
        o.show_bounds = True
        o.show_axis = True
    return [("call", scene), ("call", view(dist=6)), ("wait", 0.8),
            ("text", "Rotation applied: loose box, axes don't match the shape"), ("wait", 1.4),
            ("call", op("keyops.realign_rotation")),
            ("text", "Re-Align Rotation: axes match the shape again, nothing moved"), ("wait", 2.0)]


def element_header():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cube_add(size=1.5, location=(-1.2, 0, 0))
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.8, location=(1.2, 0, 0))
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(type='FACE')
        bpy.ops.keyops.sub_object_mode(mode='ELEMENT')
    return [("call", scene), ("call", view(dist=7, loc=(0, 0, 0))), ("wait", 0.6),
            ("text", "Vertex | Edge | Face | Element: one group in the header"), ("wait", 1.2),
            ("move", P((-1.2, -0.75, 0.2)), 0.5), ("click", 'LEFTMOUSE'), ("wait", 0.8),
            ("move", P((1.2, -0.8, 0.0)), 0.5), ("click", 'LEFTMOUSE', {"shift": True}), ("wait", 1.5)]


def triplanar():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cube_add(size=2)
        o = context.object
        mat = bpy.data.materials.new("Checker")
        mat.use_nodes = True
        nt = mat.node_tree
        tex = nt.nodes.new("ShaderNodeTexChecker")
        tex.inputs["Scale"].default_value = 2.0
        nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
        o.data.materials.append(mat)
        o.scale = (1.5, 1, 1)
        context.space_data.shading.type = 'MATERIAL' if context.space_data else None
    def shading(context):
        H.area().spaces.active.shading.type = 'MATERIAL'
    return [("call", scene), ("call", shading), ("call", view(dist=8)), ("wait", 1.0),
            ("text", "Triplanar UV: upright on every side, World Scale"),
            ("call", op("keyops.toolkit_panel", type="Triplanar_UV_Mapping", tri_size=1.0)), ("wait", 2.5)]


def q_menu():
    def scene(context):
        clear(context)
        bpy.ops.mesh.primitive_cube_add()
        p = H.prefs()
        for pie in p.pies:
            if pie.preset == "q_menu":
                pie.enabled = True
        H.addon().pie_menus.sync_keymaps()
    return [("call", scene), ("call", view(dist=8)), ("move", 0.45, 0.5, 0.3), ("wait", 0.5),
            ("text", "Q Menu: Display types right in the menu, no third level"),
            ("key", 'Q'), ("wait", 0.8), ("move", 0.5, 0.36, 0.6), ("wait", 2.0), ("key", 'ESC'), ("wait", 0.8)]


DEMOS = {f.__name__: f for f in (push_pull, fast_bevel_keys, fast_array_end_to_end, cutter, edge_trim, live_edge_trim,
                                 cylinder_sides, rebevel, slide_scale, realign_rotation, element_header, triplanar,
                                 q_menu, live_trim_gizmos)}

name = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "push_pull"
H.run(DEMOS[name]() + [("text", ""), ("wait", 0.3)])
