"""GUI test: Element mode with real (simulated) mouse input, in a real window.

Click, Shift+click, Ctrl+click, box select with the Select Box tool (plain, Shift, Ctrl drag) and B box select
must all pick or unpick whole islands, quickly (also on a heavy mesh). Run by scripts/test.sh --gui.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "demo"))

import addon_utils  # noqa: E402
import bmesh  # noqa: E402
import bpy  # noqa: E402
import harness as H  # noqa: E402
from mathutils import Euler  # noqa: E402

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
addon_utils.enable(MOD, default_set=True)
_w = sys.modules[MOD + ".ui.welcome"]
if bpy.app.timers.is_registered(_w._show_welcome):  # a fresh profile: the welcome screen would cover the view
    bpy.app.timers.unregister(_w._show_welcome)
P = H.world_to_px
results = {"t0": 0.0}


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def scene(context):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-1.5, 0, 0))
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.primitive_cube_add(size=1, location=(1.5, 0, 0))  # second island in the same mesh
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_mode(type='VERT')
    a = H.area()
    sp = a.spaces.active
    sp.region_3d.view_perspective = 'ORTHO'
    sp.region_3d.view_rotation = Euler((0, 0, 0)).to_quaternion()  # top view
    sp.region_3d.view_location = (0, 0, 0)
    sp.region_3d.view_distance = 6
    sp.show_region_ui = False
    bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
    bpy.ops.keyops.sub_object_mode('INVOKE_DEFAULT', mode='ELEMENT')


def counts():
    obj = bpy.context.edit_object
    mw = obj.matrix_world
    bm = bmesh.from_edit_mesh(obj.data)
    pts = [mw @ v.co for v in bm.verts if v.select]
    return sum(1 for p in pts if p.x < 0 and abs(p.y) < 0.6), sum(1 for p in pts if p.x > 0 and abs(p.y) < 0.6)


SHOTS = os.environ.get("ELEMENT_SHOTS")


def expect(name, left, right):
    def fn(context):
        if SHOTS:
            import subprocess
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab", "-video_size", "1600x1000", "-i",
                            os.environ["DISPLAY"], "-frames:v", "1", os.path.join(SHOTS, name[:20] + ".png")])
        got = counts()
        check(f"Element mode: {name}", got == (left, right), f"selected left/right {got}, want {(left, right)}")
    return fn


def heavy(context):
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, radius=0.6, location=(0, 1.6, 0))
    bpy.ops.mesh.subdivide(number_cuts=1)
    bpy.ops.mesh.select_all(action='DESELECT')
    n = len(bmesh.from_edit_mesh(context.edit_object.data).verts)
    check("Element mode: heavy island built", n > 90000, str(n))


def start_timer(context):
    results["t0"] = time.perf_counter()


def heavy_done(context):
    mw = context.edit_object.matrix_world
    bm = bmesh.from_edit_mesh(context.edit_object.data)
    sel = sum(1 for v in bm.verts if v.select and (mw @ v.co).y > 0.8)
    total = sum(1 for v in bm.verts if (mw @ v.co).y > 0.8)
    check("Element mode: a click on a 98k-vertex island selects all of it", sel == total, f"{sel}/{total}")


L, R = (-1.5, 0.0, 0.0), (1.5, 0.0, 0.0)
steps = [("wait", 1.0), ("key", 'ESC'), ("wait", 0.5), ("move", 0.5, 0.9, 0.1), ("click", 'LEFTMOUSE'),
         ("wait", 0.5),  # close Blender's splash screen (factory startup)
         ("call", scene), ("wait", 0.6),
         ("move", P((-1.95, -0.45, 0.5)), 0.2), ("click", 'LEFTMOUSE'), ("wait", 0.3),
         ("call", expect("click a corner picks its island", 8, 0)),
         ("move", P((1.95, 0.45, 0.5)), 0.2), ("click", 'LEFTMOUSE', {"shift": True}), ("wait", 0.3),
         ("call", expect("Shift+click adds the other island", 8, 8)),
         ("move", P((-1.95, -0.45, 0.5)), 0.2), ("click", 'LEFTMOUSE', {"ctrl": True}), ("wait", 0.3),
         ("call", expect("Ctrl+click unpicks an island", 0, 8)),
         ("move", P((1.05, 0.45, 0.5)), 0.2), ("click", 'LEFTMOUSE', {"shift": True}), ("wait", 0.3),
         ("call", expect("Shift+click on a selected island toggles it off", 0, 0)),
         # Select Box tool drags
         ("drag", P((-2.3, 0.2, 0.5)), P((-1.7, 0.7, 0.5)), 0.3), ("wait", 0.3),
         ("call", expect("box over part of an island picks all of it", 8, 0)),
         ("drag", P((1.3, -0.7, 0.5)), P((2.3, -0.2, 0.5)), 0.3, 'LEFTMOUSE', {"shift": True}), ("wait", 0.3),
         ("call", expect("Shift box adds an island", 8, 8)),
         ("drag", P((1.3, -0.7, 0.5)), P((2.3, -0.2, 0.5)), 0.3, 'LEFTMOUSE', {"ctrl": True}), ("wait", 0.3),
         ("call", expect("Ctrl box over part of an island unpicks it", 8, 0)),
         ("drag", P((-1.2, -0.7, 0.5)), P((-0.8, -0.2, 0.5)), 0.3), ("wait", 0.3),
         ("call", expect("plain box over part of the selected island keeps it", 8, 0)),
         ("drag", P((0.3, -0.3, 0.5)), P((0.6, 0.3, 0.5)), 0.3), ("wait", 0.3),
         ("call", expect("plain box on empty space clears the selection", 0, 0)),
         # B key box select
         ("move", P((0.0, -1.5, 0.5)), 0.1), ("key", 'B'), ("wait", 0.2),
         ("drag", P((1.3, 0.2, 0.5)), P((2.3, 0.7, 0.5)), 0.3), ("wait", 0.3),
         ("call", expect("B box select picks a whole island", 0, 8)),
         # speed on a heavy island
         ("call", heavy), ("wait", 0.5),
         ("move", P((0.0, 1.6, 0.6)), 0.2), ("call", start_timer), ("click", 'LEFTMOUSE'), ("wait", 0.6),
         ("call", heavy_done),
         ("call", lambda c: print("ALLDONE", flush=True))]
H.run(steps)
