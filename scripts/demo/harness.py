"""Drive a real Blender window from a script, for GUI checks and demo videos.

A demo script imports this, builds a list of steps and calls run(steps). Each step is one of:
    ("wait", seconds)
    ("call", fn)                       fn(ctx) runs with the 3D View (or chosen area) as context
    ("key", type, {"shift": True})     press + release a key at the mouse position
    ("press", type) / ("release", type)
    ("move", x, y, seconds)            glide the mouse to (x, y) in area-relative pixels
    ("click", button)                  LEFTMOUSE / RIGHTMOUSE press + release
    ("drag", (x0, y0), (x1, y1), seconds, button, {"shift": True})
    ("shot", path)                     save a screenshot of the window
    ("area", type)                     later steps act in the largest area of this type
    ("text", "Some caption")           show a caption at the bottom of the viewport (for videos)
Run Blender with --enable-event-simulate. The script quits Blender when the steps are done.
"""
import math
import sys

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

state = {"area": 'VIEW_3D', "mouse": None, "caption": "", "handlers": [], "log": []}


def log(*args):
    msg = " ".join(str(a) for a in args)
    state["log"].append(msg)
    print("DEMO", msg, flush=True)


def window():
    return bpy.context.window_manager.windows[0]


def area(kind=None):
    kind = kind or state["area"]
    found = [a for a in window().screen.areas if a.type == kind]
    return max(found, key=lambda a: a.width * a.height) if found else None


def region(a, kind='WINDOW'):
    return next((r for r in a.regions if r.type == kind), None) if a else None


def ctx():
    a = area()
    return dict(window=window(), area=a, region=region(a), screen=window().screen)


def to_window(x, y=None):
    """Area-relative fractions (0..1) or region pixels to window pixels. x may be a function returning (x, y),
    worked out when the step runs (e.g. a 3D point projected to the screen)."""
    if callable(x):
        x, y = x()
    a = area()
    r = region(a) or a
    px = r.x + (x * r.width if isinstance(x, float) and x <= 1.0 else x)
    py = r.y + (y * r.height if isinstance(y, float) and y <= 1.0 else y)
    return int(px), int(py)


def ev(etype, value='NOTHING', **kw):
    x, y = state["mouse"] or to_window(0.5, 0.5)
    window().event_simulate(etype, value, x=x, y=y, **kw)


_MOD_KEYS = {"shift": 'LEFT_SHIFT', "ctrl": 'LEFT_CTRL', "alt": 'LEFT_ALT'}


def mod_keys(mods, value):
    """Press / release the modifier keys themselves: drags and clicks read the window's modifier state, which
    only real modifier key events change (the event's own shift/ctrl flags are not enough)."""
    held = {}
    for name, key in _MOD_KEYS.items():
        if mods.get(name):
            held[name] = True
            ev(key, value, **(held if value == 'PRESS' else {}))


# ---------------------------------------------------------------- caption overlay for videos
def _draw_caption():
    text = state["caption"]
    if not text:
        return
    r = bpy.context.region
    blf.size(0, 22)
    w, h = blf.dimensions(0, text)
    x, y = (r.width - w) / 2, 40
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    pad = 12
    verts = ((x - pad, y - pad), (x + w + pad, y - pad), (x + w + pad, y + h + pad), (x - pad, y + h + pad))
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": verts})
    gpu.state.blend_set('ALPHA')
    shader.uniform_float("color", (0.05, 0.05, 0.05, 0.75))
    batch.draw(shader)
    blf.color(0, 1, 1, 1, 1)
    blf.position(0, x, y, 0)
    blf.draw(0, text)
    gpu.state.blend_set('NONE')


def _redraw():
    for a in window().screen.areas:
        a.tag_redraw()


# ---------------------------------------------------------------- the runner
def _steps_gen(steps):
    for step in steps:
        kind = step[0]
        if kind == "wait":
            t = step[1]
            while t > 0:
                yield 0.05
                t -= 0.05
        elif kind == "area":
            state["area"] = step[1]
            state["mouse"] = to_window(0.5, 0.5)
        elif kind == "call":
            with bpy.context.temp_override(**ctx()):
                step[1](bpy.context)
            yield 0.1
        elif kind == "text":
            state["caption"] = step[1]
            _redraw()
            yield 0.05
        elif kind == "move":
            if callable(step[1]):
                x1, y1 = to_window(step[1])
                secs = step[2] if len(step) > 2 else 0.5
            else:
                x1, y1 = to_window(step[1], step[2])
                secs = step[3] if len(step) > 3 else 0.5
            x0, y0 = state["mouse"] or (x1, y1)
            n = max(1, int(secs / 0.02))
            for i in range(1, n + 1):
                t = i / n
                t = t * t * (3 - 2 * t)
                state["mouse"] = (int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t))
                ev('MOUSEMOVE')
                yield 0.02
        elif kind == "key":
            mods = step[2] if len(step) > 2 else {}
            ev(step[1], 'PRESS', **mods)
            yield 0.05
            ev(step[1], 'RELEASE', **mods)
            yield 0.15
        elif kind in ("press", "release"):
            mods = step[2] if len(step) > 2 else {}
            ev(step[1], kind.upper(), **mods)
            yield 0.05
        elif kind == "click":
            button = step[1] if len(step) > 1 else 'LEFTMOUSE'
            mods = step[2] if len(step) > 2 else {}
            mod_keys(mods, 'PRESS')
            ev(button, 'PRESS', **mods)
            yield 0.05
            ev(button, 'RELEASE', **mods)
            mod_keys(mods, 'RELEASE')
            yield 0.15
        elif kind == "drag":
            a_pt = step[1]() if callable(step[1]) else step[1]
            b_pt = step[2]() if callable(step[2]) else step[2]
            (xa, ya), (xb, yb) = a_pt, b_pt
            secs = step[3] if len(step) > 3 else 0.6
            button = step[4] if len(step) > 4 else 'LEFTMOUSE'
            mods = step[5] if len(step) > 5 else {}
            state["mouse"] = to_window(xa, ya)
            mod_keys(mods, 'PRESS')
            ev('MOUSEMOVE', **mods)
            yield 0.05
            ev(button, 'PRESS', **mods)
            yield 0.05
            x0, y0 = state["mouse"]
            x1, y1 = to_window(xb, yb)
            n = max(1, int(secs / 0.02))
            for i in range(1, n + 1):
                t = i / n
                state["mouse"] = (int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t))
                ev('MOUSEMOVE', **mods)
                yield 0.02
            ev(button, 'RELEASE', **mods)
            mod_keys(mods, 'RELEASE')
            yield 0.15
        elif kind == "shot":
            _redraw()
            yield 0.3
            # grab the X display (Blender's own screenshot reads back black on software OpenGL)
            import os
            import subprocess
            w, h = window().width, window().height
            r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab", "-video_size", f"{w}x{h}",
                                "-i", os.environ.get("DISPLAY", ":0"), "-frames:v", "1", step[1]])
            log("shot" if r.returncode == 0 else "shot failed", step[1])
            yield 0.1


def run(steps, first_delay=2.0, quit_after=True):
    def start():
        a = area()
        if a is None:
            log("no area")
            return None
        state["mouse"] = to_window(0.5, 0.5)
        h = bpy.types.SpaceView3D.draw_handler_add(_draw_caption, (), 'WINDOW', 'POST_PIXEL')
        state["handlers"].append(h)
        gen = _steps_gen(steps)

        def tick():
            try:
                return next(gen)
            except StopIteration:
                log("ALLDONE")
                if quit_after:
                    bpy.app.timers.register(lambda: bpy.ops.wm.quit_blender() and None, first_interval=0.5)
                return None
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                log("STEP ERROR", e)
                if quit_after:
                    bpy.ops.wm.quit_blender()
                return None
        bpy.app.timers.register(tick, first_interval=0.1, persistent=True)
        return None
    bpy.app.timers.register(start, first_interval=first_delay, persistent=True)


def world_to_px(co):
    """A function giving the region pixel position of a 3D point in the current 3D View (for move/drag steps)."""
    def fn():
        from bpy_extras.view3d_utils import location_3d_to_region_2d
        a = area()
        p = location_3d_to_region_2d(region(a), a.spaces.active.region_3d, co)
        return (int(p.x), int(p.y)) if p is not None else (0, 0)
    return fn


def scene_cube(edit=False, select_mode='FACE'):
    """A fresh scene with a cube, optionally in Edit Mode."""
    def fn(context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        bpy.ops.mesh.primitive_cube_add(size=2)
        if edit:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type=select_mode)
    return fn


def prefs():
    from bl_ext.user_default.Key_Ops_Toolkit.utils.pref_utils import get_keyops_prefs
    return get_keyops_prefs()


def addon():
    return sys.modules.get("bl_ext.user_default.Key_Ops_Toolkit")
