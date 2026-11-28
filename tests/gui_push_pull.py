"""GUI test: the Push / Pull tool picks only what you click (the face under the mouse, or your selection when you
click on it; Shift: the flat area), in a real window. Run by scripts/test.sh --gui."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "demo"))

import addon_utils  # noqa: E402
import bmesh  # noqa: E402
import bpy  # noqa: E402
import harness as H  # noqa: E402
from mathutils import Euler  # noqa: E402

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
addon_utils.enable(MOD, default_set=True)
_w = sys.modules[MOD + ".ui.welcome"]
if bpy.app.timers.is_registered(_w._show_welcome):
    bpy.app.timers.unregister(_w._show_welcome)
P = H.world_to_px
state = {}


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def scene(select=()):
    def fn(context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        H.prefs().enable_push_pull = True
        bpy.ops.mesh.primitive_cube_add(size=2)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.subdivide(number_cuts=2)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(type='FACE')
        bm = bmesh.from_edit_mesh(context.edit_object.data)
        for f in bm.faces:
            c = f.calc_center_median()
            f.select = any(f.normal.z > 0.9 and abs(c.x - x) < 0.2 and abs(c.y - y) < 0.2 for x, y in select)
        bm.select_flush_mode()
        bmesh.update_edit_mesh(context.edit_object.data)
        state["verts"] = len(bm.verts)
        bpy.ops.wm.tool_set_by_id(name="mesh.keyops_push_pull_tool")
        r = H.area().spaces.active.region_3d
        r.view_rotation = Euler((0.9, 0, 0.5)).to_quaternion()
        r.view_location = (0, 0, 0.5)
        r.view_distance = 7
    return fn


def expect(name, new_verts, selected):
    def fn(context):
        bm = bmesh.from_edit_mesh(context.edit_object.data)
        added = len(bm.verts) - state["verts"]
        sel = sum(f.select for f in bm.faces)
        check("Push / Pull tool: " + name, added == new_verts and (selected is None or sel == selected),
              f"new verts {added} (want {new_verts}), selected faces {sel} (want {selected})")
    return fn


steps = [("wait", 1.0), ("key", 'ESC'), ("wait", 0.5), ("move", 0.5, 0.9, 0.1), ("click", 'LEFTMOUSE'), ("wait", 0.5),
         # a click on one face of a flat side: only that face (it extrudes, nothing else gets selected)
         ("call", scene()), ("wait", 0.5),
         ("drag", P((0.0, 0.0, 1.0)), P((0.0, 0.0, 1.6)), 0.6), ("wait", 0.5),
         ("call", expect("a click takes only the face under the mouse", 4, 1)),
         # a click on one of two selected faces: both
         ("call", scene(select=((0.0, 0.0), (0.67, 0.0)))), ("wait", 0.5),
         ("drag", P((0.0, 0.0, 1.0)), P((0.0, 0.0, 1.6)), 0.6), ("wait", 0.5),
         ("call", expect("a click on the selection takes the whole selection", 6, 2)),
         # Shift: the whole flat top (its walls are square: it just stretches, no new vertices)
         ("call", scene()), ("wait", 0.5),
         ("drag", P((0.0, 0.0, 1.0)), P((0.0, 0.0, 1.6)), 0.6, 'LEFTMOUSE', {"shift": True}), ("wait", 0.5),
         ("call", expect("Shift takes the flat area (square walls: it stretches)", 0, 9)),
         ("call", lambda c: print("ALLDONE", flush=True))]
H.run(steps)
