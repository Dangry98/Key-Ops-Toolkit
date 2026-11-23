"""Headless checks that every built-in Key Ops panel and menu draws in this Blender version.

Each registered Panel and Menu class from the add-on is drawn through the recording layout from
test_menu_drawing.py, which checks every call against this Blender's real UILayout API: functions,
keyword arguments, icons, menus, panels, operators and settings must exist. Panels and menus are drawn
in Object Mode and Edit Mode with a 3D View context. It also checks that every gpu module function the
add-on calls exists here, since draw callbacks never run in background mode.

The point is catching API that only exists in newer Blender (an icon, a shader, a keyword) when run in
the minimum supported version, so run it in both:
    blender -b --factory-startup --python tests/test_ui_draw.py
Exits non-zero on failure.
"""

import os
import re
import sys
import traceback

import addon_utils
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = sys.argv[:1]  # test_menu_drawing runs its own checks on import only when executed as a script

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def load_recorder():
    """Takes Rec and LayoutError from test_menu_drawing.py without running that file's tests."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_menu_drawing.py")
    src = open(path, encoding="utf-8").read()
    src = src.split("\ndef run():", 1)[0]  # only the layout recorder part
    ns = {"__name__": "menu_drawing_recorder"}
    exec(compile(src, path, "exec"), ns)
    return ns["Rec"], ns["LayoutError"]


class FakeSelf:
    """Stands in for a Panel or Menu instance: a recording layout plus the class's own attributes."""

    def __init__(self, layout):
        object.__setattr__(self, "layout", layout)

    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)


def fake_self(cls, layout):
    """A FakeSelf whose type carries the class's bl_* attributes and methods, so type(self).bl_idname works."""
    attrs = {}
    for k in dir(cls):
        if k.startswith("__") or k in ("layout", "bl_rna", "rna_type"):
            continue
        try:
            attrs[k] = getattr(cls, k)
        except AttributeError:
            continue
    for klass in reversed(cls.__mro__):  # plain functions keep binding to the fake instance
        for k, v in klass.__dict__.items():
            if not k.startswith("__") and k in attrs:
                attrs[k] = v
    return type("Fake_" + cls.__name__, (FakeSelf,), attrs)(layout)


def view3d_override():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                return dict(window=win, area=area, region=region, space_data=area.spaces.active)
    return {}


def addon_classes():
    out = []
    for base in (bpy.types.Panel, bpy.types.Menu):
        stack = list(base.__subclasses__())
        while stack:
            cls = stack.pop()
            stack.extend(cls.__subclasses__())
            if cls.__module__.startswith(MOD) and getattr(cls, "is_registered", False) and "draw" in dir(cls):
                out.append(cls)
    return sorted(set(out), key=lambda c: c.__name__)


def run():
    addon_utils.enable(MOD, default_set=True)
    Rec, LayoutError = load_recorder()

    class Recorder(Rec):
        """layout.icon(data) returns an icon number in Blender; the recorder returns None."""

        def __getattr__(self, name):
            if name == "icon":
                return lambda *a, **k: 0
            fn = Rec.__getattr__(self, name)
            if name in ("row", "column", "split", "box", "grid_flow", "column_flow", "menu_pie"):
                return lambda *a, **k: (fn(*a, **k), Recorder(self._log, self._ctx))[1]
            if name == "panel":
                return lambda *a, **k: (fn(*a, **k), (Recorder(self._log, self._ctx), Recorder(self._log, self._ctx)))[1]
            return fn

    # gpu functions the add-on calls exist in this version (draw callbacks can't run in -b)
    import gpu
    root = os.path.dirname(sys.modules[MOD].__file__)
    used = set()
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("__pycache__", "wheels")]
        for f in fn:
            if f.endswith(".py"):
                text = open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
                used |= set(re.findall(r"gpu\.(state|shader|types|matrix|texture)\.([A-Za-z_]+)", text))
    missing = sorted(f"gpu.{m}.{n}" for m, n in used if not hasattr(getattr(gpu, m), n))
    check(f"every gpu function the add-on calls exists ({len(used)} used)", not missing, ", ".join(missing))

    # POINT_* builtin shaders only exist from 4.5: they may only be named in draw_utils.point_shader()
    stray = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("__pycache__", "wheels")]
        for f in fn:
            if f.endswith(".py") and f != "draw_utils.py":
                text = open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
                if re.search(r"from_builtin\(\s*['\"]POINT_", text):
                    stray.append(f)
    check("POINT_* shaders are only used through draw_utils.point_shader() (4.2 lacks them)", not stray,
          ", ".join(stray))

    # every panel and menu draws
    bpy.ops.object.select_all(action='DESELECT') if bpy.context.view_layer.objects.active else None
    mesh = bpy.data.meshes.new("KO_Test")
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new("KO_Test", mesh)
    bpy.context.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)

    override = view3d_override()
    classes = addon_classes()
    check(f"found the add-on's panels and menus ({len(classes)})", len(classes) > 10)

    for mode in ('OBJECT', 'EDIT'):
        with bpy.context.temp_override(**override):
            if mode == 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            api_errors, other = [], []
            for cls in classes:
                ctx = bpy.context
                poll = getattr(cls, "poll", None)
                if poll is not None:
                    try:
                        if not poll(ctx):
                            continue
                    except Exception as e:  # noqa: BLE001
                        other.append(f"{cls.__name__}.poll: {type(e).__name__}: {e}")
                        continue
                for fn_name in ("draw_header", "draw"):
                    if fn_name not in cls.__dict__:
                        continue
                    me = fake_self(cls, Recorder([]))
                    try:
                        getattr(cls, fn_name)(me, ctx)
                    except LayoutError as e:
                        api_errors.append(f"{cls.__name__}.{fn_name}: {e}")
                    except Exception as e:  # noqa: BLE001
                        tb = traceback.extract_tb(e.__traceback__)[-1]
                        other.append(f"{cls.__name__}.{fn_name}: {type(e).__name__}: {e} "
                                     f"({os.path.basename(tb.filename)}:{tb.lineno})")
            if mode == 'EDIT':
                bpy.ops.object.mode_set(mode='OBJECT')
        check(f"{mode}: every panel and menu uses only UI API this Blender has", not api_errors,
              " | ".join(api_errors))
        check(f"{mode}: every panel and menu draws without an error", not other, " | ".join(other))


try:
    run()
except Exception:
    traceback.print_exc()
    results.append(("no exception", False, ""))

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
