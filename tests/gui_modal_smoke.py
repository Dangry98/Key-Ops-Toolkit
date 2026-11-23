"""GUI smoke test: drive every Key Ops modal tool, pie and menu in a real window with simulated events.

Background mode never runs draw callbacks, modal handlers or status bar drawing, so this runs in a normal
Blender window started with --enable-event-simulate (real mouse and keyboard input is ignored while it runs).
Each step sets up a cube, opens a tool or menu, moves and drags the mouse, then cancels. Errors inside draw
callbacks are printed by Blender, not raised, so scripts/test.ps1 -Gui also fails the run on any "Traceback"
in the log. Run it in the minimum supported Blender (4.2) as well as the newest one:
    powershell -ExecutionPolicy Bypass -File scripts/test.ps1 -Gui -Version 4.2.3
The window opens and closes by itself in about a minute.
"""
import bpy, sys, addon_utils, traceback, bmesh
MOD = "bl_ext.user_default.Key_Ops_Toolkit"
addon_utils.enable(MOD, default_set=True)
PM = sys.modules[MOD + ".pie_menus"]
p = bpy.context.preferences.addons[MOD].preferences
if not p.pies_installed:
    PM.install_presets(p, "BLENDER_PLUS")
win = bpy.context.window_manager.windows[0]

def v3d():
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'), key=lambda a: a.width * a.height)
    region = next(r for r in area.regions if r.type == 'WINDOW')
    return area, region

def ov():
    area, region = v3d()
    return dict(window=win, screen=win.screen, area=area, region=region)

def center():
    area, region = v3d()
    return region.x + region.width // 2, region.y + region.height // 2

def ev(t, v='NOTHING', dx=0, dy=0, **kw):
    cx, cy = center()
    win.event_simulate(type=t, value=v, x=cx + dx, y=cy + dy, **kw)

def key(t, **kw):
    ev(t, 'PRESS', **kw); ev(t, 'RELEASE', **kw)

def reset_scene(mode='OBJECT', boolean=False):
    with bpy.context.temp_override(**ov()):
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        if boolean:
            bpy.ops.mesh.primitive_cylinder_add(location=(0.5, 0, 0), radius=0.3)
            cut = bpy.context.active_object
            m = cube.modifiers.new("B", 'BOOLEAN'); m.object = cut
            cut.select_set(False); cube.select_set(True)
            bpy.context.view_layer.objects.active = cube
        if mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='EDGE')
            bpy.ops.mesh.select_all(action='DESELECT')
            bm = bmesh.from_edit_mesh(cube.data)
            bm.edges.ensure_lookup_table()
            for e in bm.edges[:4]: e.select = True
            bmesh.update_edit_mesh(cube.data)

def first_uid(kind):
    for pie in p.pies:
        if (kind == "MARKING" and "marking" in pie.uid) or (kind != "MARKING" and pie.menu_type == kind and "marking" not in pie.uid):
            return pie.uid
    return ""

def wiggle():
    for i in range(6):
        ev('MOUSEMOVE', dx=10 * i, dy=6 * i)
        yield

def drag():
    ev('LEFTMOUSE', 'PRESS', dx=-60, dy=-40); yield
    for i in range(5):
        ev('MOUSEMOVE', dx=-60 + 25 * i, dy=-40 + 18 * i); yield
    ev('LEFTMOUSE', 'RELEASE', dx=60, dy=40); yield

def cancel():
    for t in ('ESC', 'ESC', 'RIGHTMOUSE', 'ESC'):
        key(t); yield

def invoke(idname, **props):
    mod, name = idname.split('.')
    if name not in dir(getattr(bpy.ops, mod)):
        print(f"SKIP {idname}: not registered in this Blender", flush=True)
        return False
    op = getattr(getattr(bpy.ops, mod), name)
    with bpy.context.temp_override(**ov()):
        if not op.poll():
            print(f"SKIP {idname}: poll False", flush=True)
            return False
        op('INVOKE_DEFAULT', **props)
    return True

STEPS = [
    ("keyops.cutter", 'OBJECT', {}, "drag"),
    ("keyops.cutter", 'EDIT', {}, "drag"),
    ("keyops.cutter_snap_preview", 'OBJECT', {}, "wiggle"),
    ("keyops.fast_array", 'OBJECT', {}, "wiggle"),
    ("keyops.fast_bevel", 'OBJECT', {}, "wiggle"),
    ("keyops.fast_bevel", 'EDIT', {}, "wiggle"),
    ("keyops.fast_solidify", 'OBJECT', {}, "wiggle"),
    ("keyops.fast_mirror", 'OBJECT', {}, "wiggle"),
    ("object.boolean_scroll", 'BOOL', {}, "wiggle"),
    ("mesh.extrude_edge_along_normals", 'EDIT', {}, "wiggle"),
    ("mesh.offset_extrude_edge", 'EDIT', {}, "wiggle"),
    ("keyops.resample_edges", 'EDIT', {}, "wiggle"),
    ("keyops.merge_tool", 'EDIT', {}, "drag"),
    ("keyops.fast_loop_cut_adjust", 'EDIT', {}, "looptool"),
    ("keyops.welcome", 'OBJECT', {}, "wiggle"),
    ("wm.keyops_call_pie", 'OBJECT', {"pie": "PIE", "direct": True}, "wiggle"),
    ("wm.keyops_call_pie", 'OBJECT', {"pie": "MENU", "direct": True}, "wiggle"),
    ("wm.keyops_call_pie", 'EDIT', {"pie": "PIE", "direct": True}, "wiggle"),
    ("wm.keyops_call_pie", 'EDIT', {"pie": "MENU", "direct": True}, "wiggle"),
    ("wm.keyops_call_pie", 'OBJECT', {"pie": "PIE", "direct": True}, "marking"),
    ("wm.keyops_call_pie", 'EDIT', {"pie": "PIE", "direct": True}, "marking"),
]
FLC = sys.modules[MOD + ".tools.fast_loop_cut"]

def run():
    yield
    for idname, mode, props, motion in STEPS:
        props = dict(props)
        if "pie" in props and props["pie"] in ("PIE", "MENU"):
            props["pie"] = first_uid(props["pie"])
            if not props["pie"]:
                print(f"SKIP {idname}: no menu", flush=True); continue
        print(f"STEP {idname} {mode} {props}", flush=True)
        try:
            reset_scene('OBJECT' if mode == 'BOOL' else mode, boolean=(mode == 'BOOL'))
            yield
            ev('MOUSEMOVE'); yield
            p.pie_style = "MARKING" if motion == "marking" else "BLENDER"
            if motion == "looptool":
                with bpy.context.temp_override(**ov()):
                    bpy.ops.wm.tool_set_by_id(name=FLC.TOOL_IDNAME)
                for i in range(4):
                    ev('MOUSEMOVE', dx=5 * i); yield
            if not invoke(idname, **props):
                continue
            yield
            yield from (drag() if motion == "drag" else wiggle())
            if motion == "looptool":
                with bpy.context.temp_override(**ov()):
                    bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
            yield from cancel()
        except Exception:
            print("STEPERROR " + idname + "\n" + traceback.format_exc(), flush=True)
        print(f"PASS {idname} {mode} {motion}", flush=True)
    print("ALLDONE", flush=True)
    bpy.ops.wm.quit_blender()

gen = run()
def tick():
    try:
        next(gen)
    except StopIteration:
        return None
    return 0.15
bpy.app.timers.register(tick, first_interval=2.0)
