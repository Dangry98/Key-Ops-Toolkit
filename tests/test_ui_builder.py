"""Checks that every kind of Blender UI the Custom Menus builder offers can be built, drawn and previewed.

Needs a window (the real layouts are drawn in a sidebar panel), so run it without -b:
    blender --factory-startup --python tests/test_ui_builder.py
with the add-on installed as an extension in the user_default repository. Exits non-zero on failure.
"""

import sys
import traceback
from types import SimpleNamespace

import bpy

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def add(pie, **kw):
    it = pie.items.add()
    for k, v in kw.items():
        setattr(it, k, v)
    return it


def every_kind(PM, pie):
    """One of everything: buttons with every look, settings in every style, labels, separators,
    menus, panels, sub-menus, Python, a macro, and every group type, nested."""
    pie.items.clear()
    add(pie, kind=PM.LABEL, label="Heading", icon="INFO")
    add(pie, kind=PM.O, idname="mesh.primitive_cube_add", label="Cube", icon="MESH_CUBE", props="size=2.0")
    add(pie, kind=PM.O, idname="object.delete", label="", icon="TRASH", alert=True)          # icon only, alert
    add(pie, kind=PM.O, idname="object.shade_smooth", label="Smooth", emboss=False, depress=True)
    add(pie, kind=PM.O, idname="object.shade_flat", label="Flat", active=False, width=1.5, height=1.3)
    for style in ("AUTO", "CHECKBOX", "BUTTON", "SLIDER", "EXPAND"):
        add(pie, kind=PM.P, idname="scene.render.resolution_percentage" if style == "SLIDER" else
            ("scene.tool_settings.transform_pivot_point" if style == "EXPAND" else "scene.tool_settings.use_snap"),
            label=style.title(), setting_style=style)
    for sep in ("AUTO", "LINE", "SPACE"):
        add(pie, kind=PM.N, sep_type=sep, sep_factor=1.5)
    add(pie, kind=PM.M, idname="VIEW3D_MT_add", label="Add Menu")
    add(pie, kind=PM.PANEL_ITEM, idname="VIEW3D_PT_shading", label="Shading Panel")
    add(pie, kind=PM.SCRIPT, script="import bpy\n", label="Python")
    mac = add(pie, kind=PM.MACRO, label="Macro")
    st = mac.steps.add()
    st.idname = "object.select_all"
    for g, extra in (("BOX", {}), ("ROW", {"align": True}), ("COLUMN", {"alignment": "CENTER"}),
                     ("SPLIT", {"factor": 0.3}), ("GRID", {"grid_columns": 2}), ("PANEL", {"closed": False}),
                     ("PANEL", {"closed": True})):
        add(pie, kind=PM.BOX, group_type=g, label=f"{g.title()} Group", prop_split=g == "COLUMN", **extra)
        add(pie, kind=PM.O, idname="object.select_all", label="All")
        add(pie, kind=PM.O, idname="object.select_all", label="None", same_row=g == "BOX")
        if g == "BOX":  # a row inside the box: groups nest
            add(pie, kind=PM.BOX, group_type="ROW", align=True)
            add(pie, kind=PM.O, idname="object.hide_view_set", label="Hide")
            add(pie, kind=PM.O, idname="object.hide_view_clear", label="Show")
            add(pie, kind=PM.BOX_END)
        add(pie, kind=PM.BOX_END)
    add(pie, kind=PM.BREAK)
    add(pie, kind=PM.O, idname="object.duplicate_move", label="Second Column")


drawn = {}


def main():
    PM = sys.modules[MOD + ".pie_menus"]
    MC = sys.modules[MOD + ".ui.menu_canvas"]
    prefs = bpy.context.preferences.addons[MOD].preferences

    menus = {}
    for kind in ("MENU", "DIALOG", "PANEL"):
        bpy.ops.keyops.pie_add(menu_type=kind)
        pie = prefs.pies[prefs.active_pie]
        pie.name = f"Every {kind.title()}"
        every_kind(PM, pie)
        menus[kind] = pie
    groups = {it.group_type for it in menus["DIALOG"].items if it.kind == PM.BOX}
    check("every group type can be added", groups == {g[0] for g in PM.GROUP_TYPES}, str(groups))

    # the layout tree: one column per Next Column, groups nested
    tree = PM.layout_tree(list(menus["DIALOG"].items), list(enumerate(menus["DIALOG"].items)))
    check("layout: Next Column makes a second column", len(tree) == 2, str(len(tree)))
    box = next(n for n in tree[0] if n[0] == "GROUP" and menus["DIALOG"].items[n[1]].group_type == "BOX")
    check("layout: a row nests inside the box", any(c[0] == "GROUP" for c in box[2]), str(box))

    # the real layouts: drawn in a sidebar panel, every item and group
    class KEYOPS_PT_builder_test(bpy.types.Panel):
        bl_label = "Builder Test"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = "Item"  # the tab a fresh sidebar shows, so it gets drawn

        def draw(self, context):
            for kind, pie in menus.items():
                try:
                    PM.draw_columns(self.layout.column(), context, list(pie.items), pie.uid)
                    drawn[kind] = "ok"
                except Exception:  # noqa: BLE001
                    drawn[kind] = traceback.format_exc()

    bpy.utils.register_class(KEYOPS_PT_builder_test)
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    area.spaces.active.show_region_ui = True
    area.tag_redraw()
    yield 0.6
    for kind in menus:
        check(f"{kind.lower()}: every item and group draws in Blender", drawn.get(kind) == "ok",
              (drawn.get(kind) or "not drawn")[:300])
    bpy.utils.unregister_class(KEYOPS_PT_builder_test)

    # the previews: built for every kind of menu, every pie style
    for kind, pie in menus.items():
        try:
            sc = MC.build(pie, prefs)
            ok = bool(sc.els) and sc.w > 0 and sc.h > 0
            detail = f"{len(sc.els)} parts"
        except Exception:  # noqa: BLE001
            ok, detail = False, traceback.format_exc()[-300:]
        check(f"{kind.lower()}: the preview builds", ok, detail)
    pie = next(p for p in prefs.pies if p.menu_type == "PIE")
    for style in ("BLENDER", "MARKING"):
        prefs.pie_style = style
        try:
            sc = MC.build(pie, prefs)
            check(f"pie preview builds ({style.title()} style)", len(sc.els) == 8, str(len(sc.els)))
        except Exception:  # noqa: BLE001
            check(f"pie preview builds ({style.title()} style)", False, traceback.format_exc()[-300:])
    prefs.pie_style = "BLENDER"

    # the real menus open
    reg = next(r for r in area.regions if r.type == 'WINDOW')
    for kind in ("MENU", "DIALOG"):
        with bpy.context.temp_override(window=win, area=area, region=reg):
            res = bpy.ops.wm.keyops_call_pie('INVOKE_DEFAULT', pie=menus[kind].uid, direct=True)
        check(f"{kind.lower()}: opens", res in ({'RUNNING_MODAL'}, {'FINISHED'}), str(res))
        yield 0.5
        yield 0.3
    PM.sync_user_panels()
    check("sidebar panel: a panel of its own", any(c.bl_label == menus["PANEL"].name for c in PM._user_panels))

    # right-click any button: Add to Key Ops Menu
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name="Window", space_type='EMPTY')
    kmi = km.keymap_items.new("mesh.primitive_cube_add", 'NONE', 'PRESS')
    kmi.properties.size = 3.0
    ctx = SimpleNamespace(button_operator=kmi.properties, button_pointer=None, button_prop=None)
    info = PM.button_info(ctx)
    check("right-click an operator button: its operator and options",
          info is not None and info[1] == "mesh.primitive_cube_add" and "size=3.0" in info[2], str(info))
    km.keymap_items.remove(kmi)
    ts = bpy.context.scene.tool_settings
    ctx = SimpleNamespace(button_operator=None, button_pointer=ts, button_prop=ts.bl_rna.properties["use_snap"],
                          space_data=None, tool_settings=ts, scene=bpy.context.scene)
    info = PM.button_info(ctx)
    check("right-click a setting: its path from the context", info is not None and info[0] == PM.P
          and info[1] == "tool_settings.use_snap", str(info))
    PM._last_button = info
    before = len(prefs.pies)
    bpy.ops.keyops.add_button_to_menu(pie="")
    new = prefs.pies[-1]
    check("Add to Key Ops Menu > New Popup Menu: a new menu with the button in it",
          len(prefs.pies) == before + 1 and any(it.idname == "tool_settings.use_snap" for it in new.items),
          str([it.idname for it in new.items]))
    pie_items = [it.idname for it in pie.items]
    bpy.ops.keyops.add_button_to_menu(pie=pie.uid)
    check("Add to Key Ops Menu > a full pie says so instead of replacing a slot",
          [it.idname for it in pie.items] == pie_items)

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    sys.stdout.flush()
    bpy.app.timers.register(lambda: sys.exit(1 if failed else 0) or None, first_interval=0.1)


gen = None


def tick():
    global gen
    try:
        if gen is None:
            import addon_utils
            addon_utils.enable(MOD, default_set=True)
            gen = main()
        return next(gen)
    except StopIteration:
        return None
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)


bpy.app.timers.register(tick, first_interval=1.0)
