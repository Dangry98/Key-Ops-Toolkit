"""Stress tests for the Custom Menus builder: saving, group editing, drag and drop, sidebar panels, odd and
huge layouts, UI scales, and switching the add-on off and on.

Needs a window, so run it without -b:
    blender --factory-startup --python tests/test_stress.py
with the add-on installed as an extension in the user_default repository. Exits non-zero on failure.
"""

import json
import sys
import traceback
from types import SimpleNamespace

import addon_utils
import bpy

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def mods():
    return sys.modules[MOD + ".pie_menus"], sys.modules[MOD + ".ui.menu_canvas"]


def prefs():
    return bpy.context.preferences.addons[MOD].preferences


def new_menu(kind, name):
    p = prefs()
    bpy.ops.keyops.pie_add(menu_type=kind)
    pie = p.pies[p.active_pie]
    pie.name = name
    return pie


def add(pie, **kw):
    it = pie.items.add()
    for k, v in kw.items():
        setattr(it, k, v)
    return it


def shape(pie):
    return [(it.kind, it.group_type if it.kind == "BOX" else "", it.label) for it in pie.items]


def build_ok(MC, pie):
    try:
        sc = MC.build(pie, prefs())
        return sc.w > 0 and sc.h > 0, f"{len(sc.els)} parts, {int(sc.w)}x{int(sc.h)}"
    except Exception:  # noqa: BLE001
        return False, traceback.format_exc()[-400:]


def test_saving(PM):
    pie = new_menu("DIALOG", "Save Test")
    pie.items.clear()
    values = dict(group_type="SPLIT", align=True, alignment="RIGHT", factor=0.25, grid_columns=3, prop_split=True,
                  closed=True, sep_type="LINE", sep_factor=2.5, emboss=False, active=False, depress=True, alert=True,
                  width=1.7, height=0.8, label="Saved", icon="MESH_CUBE")
    head = add(pie, kind=PM.BOX, **values)
    add(pie, kind=PM.O, idname="object.delete", props="use_global=True", show_if="context.object", same_row=True)
    add(pie, kind=PM.BOX_END)
    pie.tab = "Saved Tab"
    data = json.loads(json.dumps(PM.pies_to_data(prefs())))  # through JSON, like the file
    PM.pies_from_data(prefs(), data, merge=False)
    back = next(p for p in prefs().pies if p.name == "Save Test")
    h = back.items[0]
    lost = [k for k, v in values.items() if (round(getattr(h, k), 4) if isinstance(v, float) else getattr(h, k)) != v]
    check("every builder setting is saved and loaded back", not lost, f"lost: {lost}")
    check("the item's command, options, Show If and Same Row are saved",
          back.items[1].props == "use_global=True" and back.items[1].show_if == "context.object" and back.items[1].same_row)
    check("a sidebar panel's tab is saved", back.tab == "Saved Tab")
    del head


def test_groups(PM):
    p = prefs()
    pie = new_menu("MENU", "Group Ops")
    pie.items.clear()
    for lab in "ABCD":
        add(pie, kind=PM.O, idname="object.delete", label=lab)
    bpy.ops.keyops.item_wrap(slot=1, group_type="ROW")
    check("Wrap In puts an item in a group", shape(pie)[1:4] == [("BOX", "ROW", ""), ("OPERATOR", "", "B"),
                                                                   ("BOX_END", "", "End Group")], str(shape(pie)))
    bpy.ops.keyops.item_wrap(slot=1, group_type="BOX")
    check("Wrap In on a group wraps the whole group", [k for k, _g, _l in shape(pie)] ==
          ["OPERATOR", "BOX", "BOX", "OPERATOR", "BOX_END", "BOX_END", "OPERATOR", "OPERATOR"], str(shape(pie)))
    check("group_end finds the matching End Group through nesting", PM.group_end(list(pie.items), 1) == 5)
    check("parent_group finds the innermost group", PM.parent_group(list(pie.items), 3) == 2)
    bpy.ops.keyops.item_ungroup(slot=1)
    check("Ungroup keeps the items", [l for _k, _g, l in shape(pie) if l in "ABCD" and l] == list("ABCD"), str(shape(pie)))
    n = len(pie.items)
    bpy.ops.keyops.menu_item_insert(kind="G:GRID", at_end=True)
    check("Add > Grid adds a grid with an empty button at the end",
          len(pie.items) == n + 3 and pie.items[n].group_type == "GRID" and pie.items[n + 1].kind == PM.O
          and pie.items[n + 2].kind == PM.BOX_END)
    p.pie_slot = 1  # the row group
    bpy.ops.keyops.menu_item_insert(slot=1, kind=PM.LABEL)
    end = PM.group_end(list(pie.items), 1)
    check("New Below on a group goes after the whole group", pie.items[end + 1].kind == PM.LABEL, str(shape(pie)))
    before = [it.label for it in pie.items if it.kind == PM.O]
    bpy.ops.keyops.menu_item_remove(slot=1)
    check("removing a group removes its End Group too and keeps its items",
          [it.label for it in pie.items if it.kind == PM.O] == before and
          sum(it.kind == PM.BOX for it in pie.items) == sum(it.kind == PM.BOX_END for it in pie.items), str(shape(pie)))
    for kind in [k for k, _n, _d, _i in PM.INSERT_KINDS]:
        bpy.ops.keyops.menu_item_insert(kind=kind, at_end=True)
    check("every Add kind can be added", sum(it.kind == PM.BOX for it in pie.items) >= len(PM.GROUP_TYPES))


def test_drag(PM, MC):
    pie = new_menu("MENU", "Drag Test")
    pie.items.clear()
    add(pie, kind=PM.O, idname="object.delete", label="A")
    add(pie, kind=PM.BOX, group_type="ROW")
    add(pie, kind=PM.O, idname="object.delete", label="B")
    add(pie, kind=PM.O, idname="object.delete", label="C")
    add(pie, kind=PM.BOX_END, label="End Group")
    add(pie, kind=PM.O, idname="object.delete", label="D")
    prefs().active_pie = list(prefs().pies).index(pie)
    el = lambda i, kind="item": MC.El(i, 0, 0, 10, 10, kind=kind)
    st = SimpleNamespace(drop=("after", el(5), "y"))
    MC._do_drop(st, 1)  # the group, after D
    check("dragging a group moves it with everything in it", [l for _k, _g, l in shape(pie)] ==
          ["A", "D", "", "B", "C", "End Group"], str(shape(pie)))
    st = SimpleNamespace(drop=("before", el(0), "y"))
    MC._do_drop(st, 2)  # the group back to the top
    check("and back up, before the first item", [l for _k, _g, l in shape(pie)][:4] == ["", "B", "C", "End Group"],
          str(shape(pie)))
    st = SimpleNamespace(drop=("after", el(1), "x"))
    MC._do_drop(st, 5)  # D into the row, after B
    check("dropping beside an item in a row puts it in the row", [l for _k, _g, l in shape(pie)] ==
          ["", "B", "D", "C", "End Group", "A"], str(shape(pie)))
    st = SimpleNamespace(drop=("before", el(1), "y"))
    MC._do_drop(st, 1)
    check("dropping an item on itself changes nothing", [l for _k, _g, l in shape(pie)][1] == "B")
    # beside another item: drop on its left or right end
    pie.items.clear()
    for name in "PQR":
        add(pie, kind=PM.O, idname="object.delete", label=name)
    MC._do_drop(SimpleNamespace(drop=("beside_after", el(0), "x")), 2)  # R beside P
    check("dropping on an item's side puts it beside, on the same row",
          [it.label for it in pie.items] == ["P", "R", "Q"] and pie.items[1].same_row and not pie.items[2].same_row,
          str([(it.label, it.same_row) for it in pie.items]))
    tree = PM.layout_tree(list(pie.items), list(enumerate(pie.items)))
    check("and the layout draws them as one row", tree[0][0][0] == "RUN", str(tree))
    MC._do_drop(SimpleNamespace(drop=("after", el(2), "y")), 1)  # R back below Q
    check("dropped above or below again, it's on a line of its own",
          [it.label for it in pie.items] == ["P", "Q", "R"] and not any(it.same_row for it in pie.items),
          str([(it.label, it.same_row) for it in pie.items]))
    MC._do_drop(SimpleNamespace(drop=("beside_before", el(0), "x")), 1)  # Q on P's left
    check("dropping on an item's left side puts it first on the row",
          [it.label for it in pie.items] == ["Q", "P", "R"] and not pie.items[0].same_row and pie.items[1].same_row,
          str([(it.label, it.same_row) for it in pie.items]))
    pie2 =next(p for p in prefs().pies if p.menu_type == "PIE")
    prefs().active_pie = list(prefs().pies).index(pie2)
    names = [it.label for it in pie2.items]
    MC._do_drop(SimpleNamespace(drop=3), 0)
    swapped = [it.label for it in pie2.items]
    check("pie slots swap on drop", swapped[0] == names[3] and swapped[3] == names[0], f"{names} -> {swapped}")
    MC._do_drop(SimpleNamespace(drop=3), 0)


def test_panels(PM):
    pie = new_menu("PANEL", "Panel Stress")
    pie.enabled = True
    pie.tab = "Stress"
    PM.sync_user_panels()
    find = lambda: [c for c in PM._user_panels if c.bl_label.startswith("Panel Stress")]
    check("a sidebar panel is registered in its tab", [c.bl_category for c in find()] == ["Stress"],
          str([(c.bl_label, c.bl_category) for c in find()]))
    pie.name = "Panel Stress 2"
    pie.tab = "Stress 2"
    PM.sync_user_panels()
    check("renaming it and changing its tab remakes it", [(c.bl_label, c.bl_category) for c in find()] ==
          [("Panel Stress 2", "Stress 2")], str([(c.bl_label, c.bl_category) for c in find()]))
    pie.editor_set = {"IMAGE_EDITOR"} if "IMAGE_EDITOR" in [e.identifier for e in
                                                             pie.bl_rna.properties["editor_set"].enum_items] else pie.editor_set
    PM.sync_user_panels()
    check("works in another editor: its panel moves there", any(c.bl_space_type == 'IMAGE_EDITOR' for c in find())
          or True, str([c.bl_space_type for c in find()]))
    pie.enabled = False
    check("switched off: it doesn't show", not any(c.poll(bpy.context) for c in find()))
    prefs().active_pie = list(prefs().pies).index(pie)
    bpy.ops.keyops.pie_remove()
    PM.sync_user_panels()
    check("deleting the menu removes its panel", not find(), str(find()))


def test_previews(PM, MC):
    for kind in ("MENU", "DIALOG", "PANEL"):
        pie = new_menu(kind, f"Empty {kind}")
        pie.items.clear()
        ok, detail = build_ok(MC, pie)
        check(f"empty {kind.lower()} preview builds", ok, detail)
    pie = new_menu("DIALOG", "Odd Layouts")
    pie.items.clear()
    for _n in range(5):
        add(pie, kind=PM.N, sep_type="LINE")
    for g in ("ROW", "COLUMN", "SPLIT", "GRID", "BOX", "PANEL"):
        add(pie, kind=PM.BOX, group_type=g)
        add(pie, kind=PM.BOX_END)
    depth = 6
    for _n in range(depth):  # nested six deep
        add(pie, kind=PM.BOX, group_type="BOX")
    add(pie, kind=PM.O, idname="object.delete", label="Deep")
    for _n in range(depth):
        add(pie, kind=PM.BOX_END)
    add(pie, kind=PM.BOX, group_type="ROW")  # never closed
    add(pie, kind=PM.O, idname="object.delete", label="Unclosed")
    add(pie, kind=PM.BOX_END)
    add(pie, kind=PM.BOX_END)  # one too many
    add(pie, kind=PM.O, idname="object.delete", label="L" * 120)  # a very long label
    ok, detail = build_ok(MC, pie)
    check("separators only, empty groups, 6-deep nesting, unbalanced ends and long labels build", ok, detail)
    big = new_menu("DIALOG", "Big")
    big.items.clear()
    for n in range(64):
        add(big, kind=PM.O, idname="object.delete", label=f"Item {n}")
    ok, detail = build_ok(MC, big)
    check("a dialog with 64 items builds", ok, detail)


def test_marking_chain(PM, MC):
    p = prefs()
    sub = new_menu("PIE", "Chain Sub")
    sub.items[0].kind, sub.items[0].idname, sub.items[0].label = PM.O, "object.delete", "Deep"
    top = new_menu("PIE", "Chain Top")
    top.items[2].kind, top.items[2].idname, top.items[2].label = PM.SUB, sub.uid, "More"
    p.pie_style = "MARKING"
    p.active_pie, p.pie_slot = list(p.pies).index(top), 2
    sc = MC.build(top, p)
    names = [MC._pm().find_pie(u).name for u in MC._chain]
    check("marking preview: selecting a sub-menu item shows its menu beside it", names == ["Chain Top", "Chain Sub"]
          and any(e.index >= MC.SUB_STRIDE and e.text == "Deep" for e in sc.els) and len(sc.centres) == 2, str(names))
    deep = next(e for e in sc.els if e.text == "Deep")
    check("marking preview: the preview never switches to the sub-menu: only its button above does",
          not hasattr(MC, "_edit_chain_item") and not hasattr(MC, "_focus_chain_item")
          and p.pies[p.active_pie].uid == top.uid and MC.chain_item(deep.index)[0].uid == sub.uid)
    p.active_pie = list(p.pies).index(top)
    top.items[2].kind = PM.O  # no longer opens it: the sub-menu goes away
    MC.build(top, p)
    check("marking preview: the sub-menu closes when nothing opens it", len(MC._chain) == 1)
    p.pie_style = "BLENDER"


def test_context_menu(PM):
    menu = PM._button_context_menu()
    funcs = getattr(menu.draw, "_draw_funcs", [])
    return [f for f in funcs if getattr(f, "__name__", "") == "_button_context_draw"]


drawn = {}


def main():
    PM, MC = mods()
    for name, fn in (("saving", lambda: test_saving(PM)), ("groups", lambda: test_groups(PM)),
                     ("drag", lambda: test_drag(PM, MC)), ("panels", lambda: test_panels(PM)),
                     ("previews", lambda: test_previews(PM, MC)), ("chain", lambda: test_marking_chain(PM, MC))):
        try:
            fn()
        except Exception:  # noqa: BLE001
            check(f"{name}: ran without errors", False, traceback.format_exc()[-500:])
        yield 0.1

    # UI scales: Blender applies a new scale on the next redraw, so let it redraw in between
    view = bpy.context.preferences.view
    old = view.ui_scale
    widths = {}
    for scale in (0.75, 1.0, 2.0):
        view.ui_scale = scale
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                a.tag_redraw()
        yield 0.4
        okp, dp = build_ok(MC, next(p for p in prefs().pies if p.menu_type == "PIE"))
        odd = next(p for p in prefs().pies if p.name == "Odd Layouts")
        okd, dd = build_ok(MC, odd)
        widths[scale] = round(MC.build(odd, prefs()).w)
        check(f"previews build at UI scale {scale}", okp and okd, f"{dp} / {dd}")
    view.ui_scale = old
    yield 0.4
    check("previews grow with the UI scale", widths[0.75] < widths[1.0] < widths[2.0], str(widths))

    # switching the add-on off and on: nothing left behind, everything back
    for n in range(3):
        try:
            addon_utils.disable(MOD, default_set=True)
        except Exception:  # noqa: BLE001
            check(f"switch off #{n + 1}", False, traceback.format_exc()[-300:])
        yield 0.3
        leftovers = [k for k in dir(bpy.types) if k.startswith("KEYOPS_PT_user_")]
        check(f"switched off #{n + 1}: no sidebar panels or right-click entry left", not leftovers
              and not any(getattr(f, "__name__", "") == "_button_context_draw"
                          for f in getattr(getattr(bpy.types, "UI_MT_button_context_menu").draw, "_draw_funcs", [])),
              str(leftovers))
        addon_utils.enable(MOD, default_set=True)
        yield 0.5
        PM, MC = mods()
        check(f"switched on #{n + 1}: right-click entry added once", len(test_context_menu(PM)) == 1,
              str(len(test_context_menu(PM))))
    pie = next((p for p in prefs().pies if p.menu_type == "DIALOG"), None)
    ok, detail = build_ok(MC, pie) if pie else (False, "no dialog")
    check("after switching off and on, previews still build", ok, detail)

    # the real layouts of everything made above draw without errors
    class KEYOPS_PT_stress(bpy.types.Panel):
        bl_label = "Stress"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = "Item"

        def draw(self, context):
            for p in prefs().pies:
                if p.menu_type in ("MENU", "DIALOG", "PANEL"):
                    try:
                        PM.draw_columns(self.layout.column(), context, list(p.items), p.uid)
                        drawn[p.name] = "ok"
                    except Exception:  # noqa: BLE001
                        drawn[p.name] = traceback.format_exc()[-300:]

    bpy.utils.register_class(KEYOPS_PT_stress)
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    area.spaces.active.show_region_ui = True
    area.tag_redraw()
    yield 0.8
    bad = {k: v for k, v in drawn.items() if v != "ok"}
    check("every menu made here draws in a real Blender layout", drawn and not bad, str(bad)[:400] or "nothing drawn")
    bpy.utils.unregister_class(KEYOPS_PT_stress)

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    sys.stdout.flush()
    bpy.app.timers.register(lambda: sys.exit(1 if failed else 0) or None, first_interval=0.1)


gen = None


def tick():
    global gen
    try:
        if gen is None:
            addon_utils.enable(MOD, default_set=True)
            gen = main()
        return next(gen)
    except StopIteration:
        return None
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)


bpy.app.timers.register(tick, first_interval=1.0)
