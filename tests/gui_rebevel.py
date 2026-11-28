"""GUI test: Re-Bevel as a modal in a real window (wheel = segments, W = width with the mouse, click back out,
Enter confirms, Esc cancels). Run by scripts/test.sh --gui."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "demo"))

import addon_utils  # noqa: E402
import bmesh  # noqa: E402
import bpy  # noqa: E402
import harness as H  # noqa: E402

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
addon_utils.enable(MOD, default_set=True)
_w = sys.modules[MOD + ".ui.welcome"]
if bpy.app.timers.is_registered(_w._show_welcome):
    bpy.app.timers.unregister(_w._show_welcome)


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def scene(context):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=2)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bm = bmesh.from_edit_mesh(context.edit_object.data)
    for e in bm.edges:
        a, b = e.verts
        e.select = a.co.z > 0.9 and b.co.z > 0.9 and a.co.y < -0.9 and b.co.y < -0.9
    bm.select_flush(True)
    bmesh.update_edit_mesh(context.edit_object.data)
    bpy.ops.mesh.bevel(offset=0.2, segments=3, affect='EDGES')
    bpy.ops.mesh.select_mode(type='FACE')


def selected_faces():
    return sum(f.select for f in bmesh.from_edit_mesh(bpy.context.edit_object.data).faces)


def width():
    bm = bmesh.from_edit_mesh(bpy.context.edit_object.data)
    zs = [v.co.z for v in bm.verts if abs(v.co.y + 1) < 1e-4 and v.co.z < 0.999]
    return 1.0 - max(zs) if zs else 0.0


def expect(name, fn):
    def call(context):
        ok, detail = fn()
        check("Re-Bevel modal: " + name, ok, detail)
    return call


start = {}


def remember(context):
    start["w"] = width()


steps = [("wait", 1.0), ("key", 'ESC'), ("wait", 0.5), ("move", 0.5, 0.9, 0.1), ("click", 'LEFTMOUSE'), ("wait", 0.3),
         ("call", scene), ("wait", 0.3), ("move", 0.5, 0.5, 0.1),
         ("call", lambda c: bpy.ops.keyops.rebevel('INVOKE_DEFAULT')), ("wait", 0.3),
         ("call", expect("starts from the bevel as it is (3 segments)", lambda: (selected_faces() == 3, selected_faces()))),
         ("key", 'WHEELUPMOUSE'), ("key", 'WHEELUPMOUSE'), ("wait", 0.2),
         ("call", expect("the wheel adds segments (5)", lambda: (selected_faces() == 5, selected_faces()))),
         ("call", remember), ("key", 'W'), ("move", 0.7, 0.5, 0.3), ("wait", 0.2),
         ("call", expect("W: the mouse changes the width", lambda: (width() > start["w"] + 0.01, f"{start['w']:.3f} -> {width():.3f}"))),
         ("click", 'LEFTMOUSE'), ("wait", 0.2), ("call", remember), ("move", 0.4, 0.5, 0.3), ("wait", 0.2),
         ("call", expect("a click goes back to segments: the mouse leaves the width alone",
                         lambda: (abs(width() - start["w"]) < 1e-6, f"{start['w']:.3f} -> {width():.3f}"))),
         ("key", 'WHEELDOWNMOUSE'), ("key", 'WHEELDOWNMOUSE'), ("key", 'WHEELDOWNMOUSE'), ("key", 'WHEELDOWNMOUSE'),
         ("key", 'WHEELDOWNMOUSE'), ("wait", 0.2),
         ("call", expect("0 segments removes the bevel", lambda: (len(bmesh.from_edit_mesh(bpy.context.edit_object.data).verts) == 8,
                                                                    len(bmesh.from_edit_mesh(bpy.context.edit_object.data).verts)))),
         ("key", 'WHEELUPMOUSE'), ("key", 'WHEELUPMOUSE'), ("key", 'RET'), ("wait", 0.3),
         ("call", expect("Enter confirms (2 segments)", lambda: (selected_faces() == 2, selected_faces()))),
         ("call", lambda c: bpy.ops.keyops.rebevel('INVOKE_DEFAULT')), ("wait", 0.3),
         ("key", 'WHEELUPMOUSE'), ("key", 'WHEELUPMOUSE'), ("wait", 0.2), ("key", 'ESC'), ("wait", 0.3),
         ("call", expect("Esc cancels (back to 2 segments)", lambda: (selected_faces() == 2, selected_faces()))),
         ("call", lambda c: print("ALLDONE", flush=True))]
H.run(steps)
