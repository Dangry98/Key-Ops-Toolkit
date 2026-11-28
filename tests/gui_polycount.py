"""GUI test: the Polycount List's keyboard and list operators, run from the 3D View sidebar (where the keys work).
Run by scripts/test.sh --gui."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "demo"))

import addon_utils  # noqa: E402
import bpy  # noqa: E402
import harness as H  # noqa: E402

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
addon_utils.enable(MOD, default_set=True)
_w = sys.modules[MOD + ".ui.welcome"]
if bpy.app.timers.is_registered(_w._show_welcome):
    bpy.app.timers.unregister(_w._show_welcome)
pcl = sys.modules[MOD + ".operators.poly_count_list"]


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def sidebar():
    a = H.area()
    a.spaces.active.show_region_ui = True
    r = next(r for r in a.regions if r.type == 'UI')
    return a, r


def scene(context):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for i in range(5):
        bpy.ops.mesh.primitive_cube_add(size=0.5, location=(i, 0, 0))
        context.object.name = f"Box{i}"
    context.window_manager.toolkit_panel_mode = {'POLYCOUNT_LIST'}
    pcl.polycount.clear()
    pcl.get_poly_count(context)


def run_ops(context):
    a, r = sidebar()
    names = [o.name for o in pcl.get_list_objects(context)]
    with context.temp_override(area=a, region=r):
        check("Polycount List keys work in the sidebar (poll)", pcl.POLYCOUNT_OT_walk.poll(bpy.context),
              f"category {getattr(r, 'active_panel_category', None)} mode {bpy.context.mode}")
        vl = bpy.context.view_layer
        vl.objects.active = bpy.data.objects[names[0]]
        bpy.ops.keyops.polycount_walk(direction='DOWN')
        check("Down / S moves to the next object in the list", vl.objects.active.name == names[1],
              f"{vl.objects.active.name} want {names[1]}")
        bpy.ops.keyops.polycount_walk(direction='DOWN', extend=True)
        sel = sorted(o.name for o in bpy.context.selected_objects)
        check("Shift+Down extends the selection", sel == sorted(names[1:3]), str(sel))
        bpy.ops.keyops.polycount_select_all(action='SELECT')
        check("A selects every object in the list", len(bpy.context.selected_objects) == 5)
        bpy.ops.keyops.polycount_select_all(action='DESELECT')
        check("Alt A deselects them", len(bpy.context.selected_objects) == 0)
        bpy.data.objects[names[0]].hide_set(True)
        bpy.ops.keyops.polycount_show_all()
        check("Alt H shows hidden objects again", not bpy.data.objects[names[0]].hide_get())
        bpy.ops.keyops.polycount_item_action(name=names[2], action='ISOLATE')
        hidden = [n for n in names if bpy.data.objects[n].hide_get()]
        check("Right-click Isolate hides the others", hidden == [n for n in names if n != names[2]], str(hidden))


state = {}
H.run([("wait", 1.0), ("key", 'ESC'), ("wait", 0.5), ("call", scene), ("wait", 0.5), ("call", run_ops),

       ("call", lambda c: print("ALLDONE", flush=True))])
