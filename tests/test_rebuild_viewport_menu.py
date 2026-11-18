"""Rebuild the Viewport Menu (Alt V) with only the menu editor's features and check it draws exactly like
the original, in every shading state. Needs a window (run under a display, e.g. xvfb-run):

    blender -p 0 0 1920 1080 --python tests/test_rebuild_viewport_menu.py

Prints PASS/FAIL lines and quits. Exits non-zero on failure.
"""

import sys

import addon_utils
import bpy

MOD = "bl_ext.user_default.Key_Ops_Toolkit"


class Rec:
    """Stands in for a UILayout and writes down what is drawn into it."""

    def __init__(self, out):
        self.out = out

    def _child(self, *a, **k):
        sub = []
        self.out.append(("group", sub))
        return Rec(sub)

    split = column = grid_flow = row = box = _child

    def prop(self, data, prop, text=None, icon='NONE', **k):
        name = text if text is not None else data.bl_rna.properties[prop].name
        self.out.append(("prop", f"{type(data).__name__}.{prop}", name, icon if icon != 'NONE' else ''))

    def operator(self, idname, text=None, icon='NONE', **k):
        self.out.append(("op", idname, text, icon))
        return type("O", (), {"__setattr__": lambda s, kk, v: None})()

    def template_icon_view(self, data, prop, show_labels=False, scale=1.0, scale_popup=5.0):
        self.out.append(("icon_view", f"{type(data).__name__}.{prop}", show_labels, scale, scale_popup))

    def label(self, text="", icon='NONE', **k):
        self.out.append(("label", text))

    def separator(self, **k):
        self.out.append(("sep",))


def build(prefs, PM):
    bpy.ops.keyops.pie_add(menu_type="MENU")
    m = prefs.pies[-1]
    m.name = "Viewport Overlays"
    while len(m.items):
        m.items.remove(0)

    def add(kind, idname="", label="", icon="", props="", show_if=""):
        it = m.items.add()
        it.kind, it.idname, it.label, it.icon, it.props, it.show_if = kind, idname, label, icon, props, show_if

    add(PM.P, "space_data.overlay.show_wireframes")
    add(PM.P, "space_data.overlay.show_face_orientation")
    add(PM.P, "space_data.shading.show_object_outline", show_if="space.shading.type == 'SOLID'")
    add(PM.P, "space_data.overlay.show_overlays", label="Overlays")
    add(PM.BREAK, label="Next Column")
    silhouette = ("keyops.viewport_menu", "Toggle Silhouette")
    add(PM.O, *silhouette, "SHADING_SOLID", "type='toggle_silhouettes'", show_if="space.shading.light != 'FLAT'")
    add(PM.O, *silhouette, "SHADING_RENDERED", "type='toggle_silhouettes'", show_if="space.shading.light == 'FLAT'")
    add(PM.P, "space_data.shading.studio_light", props="view='ICONS', scale=3.5, scale_popup=4, show_labels=True",
        show_if="space.shading.type != 'WIREFRAME'")
    return m


def run():
    results = []
    try:
        addon_utils.enable(MOD, default_set=True)
        prefs = bpy.context.preferences.addons[MOD].preferences
        prefs.enable_viewport_menu = True
        PM = sys.modules[MOD].pie_menus
        m = build(prefs, PM)
        win = bpy.context.window_manager.windows[0]
        area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
        region = next(r for r in area.regions if r.type == 'WINDOW')
        shading = area.spaces[0].shading
        with bpy.context.temp_override(window=win, area=area, region=region):
            for stype, light in (("SOLID", "STUDIO"), ("SOLID", "FLAT"), ("WIREFRAME", "STUDIO"), ("MATERIAL", "STUDIO")):
                shading.type, shading.light = stype, light
                a, b = [], []
                bpy.types.VIEW3D_MT_viewport_menu.draw(type("M", (), {"layout": Rec(a)})(), bpy.context)
                PM.draw_columns(Rec(b), bpy.context, list(m.items), m.uid)
                ok = a == b
                results.append(ok)
                print(("PASS " if ok else "FAIL ") + f"{stype} shading, {light} light: draws like the original")
                if not ok:
                    print("   original:", a)
                    print("   rebuilt: ", b)
    except Exception:
        import traceback
        traceback.print_exc()
        results.append(False)
    print(f"{sum(results)}/{len(results)} checks passed")
    sys.stdout.flush()
    bpy.ops.wm.quit_blender()
    if not all(results):
        sys.exit(1)


bpy.app.timers.register(run, first_interval=2.0)
