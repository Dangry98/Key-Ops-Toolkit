"""Headless checks that custom menus draw solidly, and that the editor's preview matches the real menu.

Every menu is drawn through a stand-in layout that records each call and checks it against Blender's real
UILayout API: the function exists, its keyword arguments exist, icons are real icons, menus, panels,
operators and settings exist, and operator options are real options with valid values. Hundreds of
generated menus (every item kind, broken items, Show If tests, columns, boxes, submenus) are drawn as
popup menus, panels, dialogs and pies; the preview (ui/menu_canvas.py) is built for each, and for popup
menus the preview's rows are compared with what the real menu drew, one for one.

Run with the add-on installed as an extension in the user_default repository:
    blender -b --factory-startup --python tests/test_menu_drawing.py
Exits non-zero on failure.
"""

import random
import sys
import traceback

import addon_utils
import bpy

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


# ---------------------------------------------------------------- a layout that records and checks every call

_UI = bpy.types.UILayout.bl_rna
FUNCS = {f.identifier: [p.identifier for p in f.parameters] for f in _UI.functions}
PROPS = {p.identifier for p in _UI.properties}
ICONS = set(_UI.functions["prop"].parameters["icon"].enum_items.keys())
SUBLAYOUTS = {"row", "column", "split", "box", "grid_flow", "column_flow", "menu_pie"}


class LayoutError(Exception):
    pass


class Op:
    """What layout.operator returns: only the operator's real options can be set, with valid values."""

    def __init__(self, idname):
        mod, _, name = idname.partition(".")
        if not mod or not name or not hasattr(bpy.ops, mod) or name not in dir(getattr(bpy.ops, mod)):
            raise LayoutError(f"no operator {idname}")
        object.__setattr__(self, "_idname", idname)
        object.__setattr__(self, "_rna", getattr(getattr(bpy.ops, mod), name).get_rna_type())

    def __setattr__(self, key, value):
        props = self._rna.properties
        if key not in props or key == "rna_type":
            raise LayoutError(f"{self._idname} has no option {key}")
        prop = props[key]
        if prop.type == 'ENUM':
            ids = {e.identifier for e in prop.enum_items}
            values = value if isinstance(value, set) else {value}
            if ids and not values <= ids:  # dynamic enums list no items here
                raise LayoutError(f"{self._idname}.{key}: {value!r} is not one of {sorted(ids)[:6]}")


class Rec:
    """A stand-in for bpy.types.UILayout. Records (function, text, details) in a shared log."""

    def __init__(self, log, ctx="EXEC_REGION_WIN"):  # Blender's popup menus execute by default
        object.__setattr__(self, "_log", log)
        object.__setattr__(self, "_ctx", ctx)

    def __setattr__(self, key, value):
        if key not in PROPS:
            raise LayoutError(f"UILayout has no property {key}")
        if key == "operator_context":
            object.__setattr__(self, "_ctx", value)

    def __getattr__(self, name):
        if name == "operator_context":
            return self._ctx
        if name in PROPS:  # reading a layout property: its default is fine here
            return None
        if name not in FUNCS:
            raise LayoutError(f"UILayout has no function {name}")
        params = FUNCS[name]

        def call(*args, **kw):
            bad = set(kw) - set(params)
            if bad:
                raise LayoutError(f"{name}() has no argument {sorted(bad)}")
            if len(args) > len(params):
                raise LayoutError(f"{name}() takes {len(params)} arguments, got {len(args)}")
            kw = dict(zip(params, args), **kw)
            icon = kw.get("icon")
            if icon is not None and icon not in ICONS:
                raise LayoutError(f"{name}(icon={icon!r}) is not a Blender icon")
            if "icon_value" in kw and not isinstance(kw["icon_value"], int):
                raise LayoutError(f"{name}(icon_value={kw['icon_value']!r}) is not a number")
            entry = {"fn": name, "kw": kw, "text": kw.get("text"), "ctx": self._ctx}
            if name in ("prop", "prop_menu_enum", "props_enum", "template_icon_view", "prop_enum"):
                data, prop = kw.get("data"), kw.get("property")
                rna = getattr(data, "bl_rna", None)
                if rna is None or prop not in rna.properties:
                    raise LayoutError(f"{name}(): no setting {prop!r} on {data!r}")
                entry["rna"] = rna.properties[prop]
                if name == "prop_menu_enum" and entry["rna"].type != 'ENUM':
                    raise LayoutError(f"prop_menu_enum() on a {entry['rna'].type} setting")
                if entry["text"] is None:
                    entry["text"] = entry["rna"].name
            if name == "menu" and not hasattr(bpy.types, kw.get("menu", "")):
                raise LayoutError(f"no menu {kw.get('menu')}")
            if name == "popover" and not hasattr(bpy.types, kw.get("panel", "")):
                raise LayoutError(f"no panel {kw.get('panel')}")
            self._log.append(entry)
            if name in SUBLAYOUTS:  # a sub-layout starts with its parent's operator context
                return Rec(self._log, self._ctx)
            if name == "panel":
                return Rec(self._log, self._ctx), Rec(self._log, self._ctx)
            if name == "operator":
                return Op(kw.get("operator", ""))
            return None
        return call


def drawn_rows(log):
    """What a popup menu shows, row by row: (look, text), the way pie_menus.popup_menu_look names it."""
    rows = []
    for e in log:
        fn = e["fn"]
        if fn in ("menu", "prop_menu_enum"):
            rows.append(("SUBMENU", e["text"] or ""))
        elif fn == "prop":
            rna = e["rna"]
            look = "CHECKBOX" if rna.type == 'BOOLEAN' and not getattr(rna, "array_length", 0) else "FIELD"
            rows.append((look, e["text"] or ""))
        elif fn in ("operator", "popover"):
            rows.append(("BUTTON", e["text"] or ""))
        elif fn == "prop_enum":  # one option of a choice, as a button
            rows.append(("BUTTON", e["text"] or ""))
        elif fn == "label":
            rows.append(("LABEL", e["text"] or ""))
        elif fn == "separator":
            rows.append(("SEP", ""))
        elif fn == "template_icon_view":
            rows.append(("ICONS", "*"))  # a big icon picker: its text isn't compared
    return rows


def preview_rows(sc):
    """The preview's rows of a popup menu, in the order they're drawn (column by column, top to bottom)."""
    # the edited menu's own rows (a submenu open beside it has indices from SUB_STRIDE on)
    els = [el for el in sc.els if el.kind in ("item", "label", "sep", "empty") and el.index < 1000]
    els.sort(key=lambda el: (el.col, -el.y, el.x))
    rows = []
    for el in els:
        if el.kind in ("sep", "empty"):
            rows.append(("SEP", ""))
        elif el.kind == "label":
            rows.append(("LABEL", el.text))
        else:
            text = el.text
            if el.look == "FIELD":  # the preview adds the value, as Blender's field shows it
                text = "" if ": " not in text else text.rsplit(": ", 1)[0]
            elif el.look == "ICONS":
                text = "*"
            rows.append((el.look, text))
    return rows


# ---------------------------------------------------------------- generated menus

def run():
    addon_utils.enable(MOD, default_set=True)
    pkg = sys.modules[MOD]
    PM, MC = pkg.pie_menus, pkg.ui.menu_canvas
    p = bpy.context.preferences.addons[MOD].preferences
    if not p.pies_installed:
        PM.install_presets(p, "BLENDER_PLUS")
    C = bpy.context
    rng = random.Random(1234)

    type_value = {t[0]: t[4] for t in PM.MENU_TYPES}

    def new_menu(menu_type="MENU", name="Test"):
        """A menu that's switched off, made without saving or keymap updates for each change (fast)."""
        pie = PM._new_pie(p)
        pie["enabled"], pie["menu_type"] = False, type_value[menu_type]
        pie.name, pie.key = name, "NONE"
        pie.items.clear()
        return pie

    def draw_real(pie, context=C):
        """Draws the menu the way Blender opens it. Returns (log, error)."""
        log, root = [], Rec([])
        root = Rec(log)
        try:
            items = list(pie.items)
            if pie.menu_type == "MENU" and not PM.needs_panel_popup(items):
                PM.draw_popup_menu(root, context, items, pie.uid)
            elif pie.menu_type == "MENU":
                PM.draw_columns(root, context, items, pie.uid)
            elif pie.menu_type == "PIE":
                PM.draw_pie_items(root.menu_pie(), context, items, pie.uid)
            else:
                PM.draw_grid(root, context, pie)
            return log, None
        except Exception as e:  # noqa: BLE001
            return log, f"{type(e).__name__}: {e}"

    def broken(log):
        return [e["text"] for e in log if e["fn"] == "label" and e["text"] and "(check command)" in e["text"]]

    # a scene with a mesh selected and active, a boolean and a bevel on it
    cube = bpy.data.objects.get("Cube")
    if cube is None:
        bpy.ops.mesh.primitive_cube_add()
        cube = C.active_object
    C.view_layer.objects.active = cube
    cube.select_set(True)
    sub_menu = new_menu("MENU", "Sub")
    for label in ("One", "Two"):
        it = sub_menu.items.add()
        it.kind, it.label, it.idname = "OPERATOR", label, "mesh.primitive_cube_add"
    sub_pie = next(x for x in p.pies if x.preset == "add_objects")
    macro_host = None

    def item_spec(valid_only):
        """One random item: (fields, valid). Broken ones only when valid_only is False."""
        label = rng.choice(["", "Name", "A much longer label here"])
        icon = rng.choice(["", "MESH_CUBE", "keyops:union", "MODIFIER", "keyops:difference"]
                          + ([] if valid_only else ["NOT_AN_ICON", "keyops:nope"]))
        good = [
            ("OPERATOR", "mesh.primitive_cube_add", ""),
            ("OPERATOR", "object.add_boolean_modifier_operator", "type='UNION'"),
            ("OPERATOR", "keyops.active_modifier", "action='APPLY'"),
            ("MENU", "VIEW3D_MT_add", ""),
            ("PROPERTY", "scene.tool_settings.use_snap", ""),
            ("PROPERTY", "object.display_type", ""),
            ("PROPERTY", "object.show_wire", ""),
            ("PROPERTY", "scene.render.fps", ""),
            ("PROPERTY", "scene.tool_settings.snap_elements", ""),
            ("PROPERTY", "object.display_type", "view='ICONS'"),
            ("SUBMENU", sub_menu.uid, ""),
            ("SUBMENU", sub_pie.uid, ""),
            ("SCRIPT", "", ""),
            ("POPOVER", "VIEW3D_PT_overlay", ""),
            ("MACRO", "", ""),
            ("LABEL", "", ""),
            ("NONE", "", ""),
        ]
        bad = [
            ("OPERATOR", "not.an_operator", ""),
            ("OPERATOR", "mesh.primitive_cube_add", "no_such_option=3"),
            ("PROPERTY", "scene.no_such_setting", ""),
            ("PROPERTY", "space_data.shading.type", ""),  # no 3D View here
            ("SUBMENU", "missing-uid", ""),
            ("POPOVER", "NO_SUCH_PT_panel", ""),
        ]
        pool = good if valid_only else good + bad
        kind, idname, props = rng.choice(pool)
        return dict(kind=kind, idname=idname, props=props, label=label or ("Heading" if kind == "LABEL" else ""),
                    icon=icon, alert=rng.random() < 0.1, setting_style=rng.choice(["AUTO", "AUTO", "CHECKBOX", "EXPAND", "BUTTON"]),
                    script="print('hi')" if kind == "SCRIPT" else ""), (kind, idname, props) in good

    def fill(pie, specs):
        for spec in specs:
            it = pie.items.add()
            for k, v in spec.items():
                setattr(it, k, v)
            if it.kind == "MACRO":
                step = it.steps.add()
                step.idname = "mesh.primitive_cube_add"

    PM._loading = True  # no saving to disk for every generated item
    # ---- 1. popup menus of valid items: drawn without errors, and the preview shows the same rows
    mismatches, errors, bad_calls = [], [], []
    for n in range(150):
        pie = new_menu("MENU", f"Fuzz {n}")
        specs = [item_spec(True)[0] for _ in range(rng.randint(1, 14))]
        if rng.random() < 0.3:  # a few columns
            for _ in range(rng.randint(1, 2)):
                specs.insert(rng.randint(0, len(specs)), dict(kind="BREAK"))
        fill(pie, specs)
        log, err = draw_real(pie)
        if err:
            errors.append(f"{pie.name}: {err}")
        elif broken(log):
            bad_calls.append(f"{pie.name}: {broken(log)} {[(i.kind, i.idname, i.props) for i in pie.items]}")
        else:
            sc = MC.build(pie, p, None)
            real, shown = drawn_rows(log), preview_rows(sc)
            if real != shown:
                mismatches.append(f"{pie.name}: real {real} != preview {shown}")
        p.pies.remove(len(p.pies) - 1)
    check("popup menus: 150 generated menus draw with only real Blender calls", not errors, "; ".join(errors[:3]))
    check("popup menus: valid items never show (check command)", not bad_calls, "; ".join(bad_calls[:2]))
    check("popup menus: the preview shows the same rows as the real menu", not mismatches, "\n".join(mismatches[:3]))

    # ---- 2. every menu type with broken items, Show If tests, boxes, rows and sizes: never breaks
    errors, preview_errors = [], []
    tests = ["", "", "obj and obj.type == 'MESH'", "mode == 'EDIT_MESH'", "sel > 1", "'BOOLEAN' in mods",
             "len(mods) > 0", "obj.no_such_thing", "this is not python", "__import__('os')", "C.scene.render.fps > 1"]
    for n in range(250):
        menu_type = rng.choice(["MENU", "MENU", "DIALOG", "PANEL", "PIE"])
        pie = new_menu(menu_type, f"Mixed {n}")
        count = 8 if menu_type == "PIE" else rng.randint(0, 20)
        specs = []
        for _ in range(count):
            spec = item_spec(False)[0]
            spec["show_if"] = rng.choice(tests)
            if menu_type != "PIE":
                spec["same_row"] = rng.random() < 0.15
                spec["width"] = rng.choice([1.0, 1.0, 2.0, 0.5])
                spec["height"] = rng.choice([1.0, 1.0, 1.5])
            specs.append(spec)
        if menu_type != "PIE":
            for kind in rng.sample(["BOX", "BOX_END", "BREAK", "BOX", "BREAK"], rng.randint(0, 4)):
                specs.insert(rng.randint(0, len(specs)), dict(kind=kind, label=rng.choice(["", "Group"])))
        fill(pie, specs)
        log, err = draw_real(pie)
        if err:
            errors.append(f"{pie.name} ({menu_type}): {err}")
        try:
            MC.build(pie, p, None)
            MC.build(pie, p, rng.randrange(max(1, len(pie.items))))  # with an item hovered
        except Exception as e:  # noqa: BLE001
            preview_errors.append(f"{pie.name} ({menu_type}): {type(e).__name__}: {e}")
        p.pies.remove(len(p.pies) - 1)
    check("250 menus of every type, with broken items and tests, never raise", not errors, "; ".join(errors[:3]))
    check("the preview builds for all of them, hovered or not", not preview_errors, "; ".join(preview_errors[:3]))

    PM._loading = False
    # ---- 3. the Q Menu and its submenus in each situation: what shows, and the preview matches
    q = next(x for x in p.pies if x.preset == "q_menu")
    subs = {PM.find_pie(i.idname).preset: PM.find_pie(i.idname) for i in q.items if i.kind == "SUBMENU"}

    def q_rows(pie):
        log, err = draw_real(pie)
        return drawn_rows(log), err, broken(log)

    def labels(rows):
        return [t for look, t in rows if look != "SEP"]

    for ob in list(C.selected_objects):
        ob.select_set(False)
    cube.modifiers.clear()
    cube.select_set(True)
    C.view_layer.objects.active = cube
    rows, err, bad = q_rows(q)
    check("Q Menu, one mesh: the modifier modals at the top, then submenus, no booleans",
          not err and not bad and labels(rows)[:4] == ["Mirror", "Bevel", "Array", "Solidify"]
          and "Difference" not in labels(rows) and ("SUBMENU", "Modifiers") in rows
          and ("SUBMENU", "Active Modifier") not in rows, str(rows) + str(err or bad))
    other = bpy.data.objects.new("Other", cube.data)
    C.collection.objects.link(other)
    other.select_set(True)
    rows, err, bad = q_rows(q)
    check("Q Menu, two meshes: the booleans at the top", not err and labels(rows)[:4] == ["Difference", "Union", "Intersect", "Slice"]
          and "Mirror" not in labels(rows)[:6], str(rows))
    other.select_set(False)
    cube.modifiers.new("Bevel", 'BEVEL')
    cube.modifiers.active = cube.modifiers.new("Boolean", 'BOOLEAN')
    rows, err, bad = q_rows(q)
    check("Q Menu, an object with a boolean: Boolean Scroll, no Active Modifier submenu",
          not err and "Boolean Scroll" in labels(rows) and ("SUBMENU", "Active Modifier") not in rows, str(rows))
    rows, err, bad = q_rows(subs["q_display"])
    check("Display submenu: one button per display type, no Display As submenu (no third level)",
          not err and not bad and not any(look == "SUBMENU" for look, _t in rows)
          and all(t in labels(rows) for t in ("Bounds", "Wire", "Solid", "Textured")), str(rows))
    real_visible = PM.item_visible
    PM.item_visible = lambda *a, **k: True  # the editor's preview shows every item, whatever its Show If says
    for key, sub in subs.items():
        rows, err, bad = q_rows(sub)
        sc = MC.build(sub, p, None)
        check(f"{key}: preview matches the real menu", not err and not bad and preview_rows(sc) == rows,
              f"{rows} != {preview_rows(sc)} {err or bad}")
    PM.item_visible = real_visible
    # the Q Menu's own preview (every item shown, as the editor shows them) builds, and its icons resolve
    sc = MC.build(q, p, None)
    check("Q Menu: the preview builds, submenus with an arrow",
          any(el.sub and el.text == "Modifiers" for el in sc.els), str([(el.text, el.sub) for el in sc.els][-6:]))
    keyops_icons = [i.icon for m in [q, *subs.values()] for i in m.items if i.icon.startswith("keyops:")]
    check("Q Menu: uses Key Ops' own icons, and they all exist",
          keyops_icons and all(PM._icon(n) != 'NONE' for n in keyops_icons), str(keyops_icons))
    check("coloured Key Ops icons use their darker menu copy, grey ones the original",
          "union_menu" in PM.custom_icon_names() and "editmode_menu" not in PM.custom_icon_names()
          and PM.icon_kw("keyops:union")["icon_value"] == pkg.utils.pref_utils.get_icon("union_menu")
          and PM.icon_kw("keyops:editmode")["icon_value"] == pkg.utils.pref_utils.get_icon("editmode"))
    check("the icon palette offers Key Ops' own icons, not the menu copies",
          "union" in PM.palette_icon_names() and not any(n.endswith("_menu") for n in PM.palette_icon_names()))
    check("custom icons draw with icon_value", "icon_value" in PM.icon_kw("keyops:union")
          and PM.icon_kw("MESH_CUBE") == {"icon": "MESH_CUBE"} and PM.icon_kw("keyops:nope") == {"icon": "NONE"})

    # how the buttons run: popup menus invoke (Blender's popup menus would execute, so modal tools never
    # started), and an item's Run As wins
    log, err = draw_real(q)
    ops = [(e["text"], e["ctx"]) for e in log if e["fn"] == "operator"]
    check("Q Menu: every button invokes, so Boolean Scroll and the Fast modals start",
          ops and all(ctx == "INVOKE_REGION_WIN" for _t, ctx in ops), str(ops))
    run_as = new_menu("MENU", "Run As")
    for mode in ("DEFAULT", "EXEC_DEFAULT", "INVOKE_DEFAULT", "EXEC_REGION_WIN", "DEFAULT"):
        it = run_as.items.add()
        it.kind, it.idname, it.label, it.call_mode = "OPERATOR", "mesh.primitive_cube_add", mode, mode
    log, err = draw_real(run_as)
    ctxs = [e["ctx"] for e in log if e["fn"] == "operator"]
    check("Run As: each item is called the way it says, the next ones as the menu does",
          ctxs == ["INVOKE_REGION_WIN", "EXEC_DEFAULT", "INVOKE_DEFAULT", "EXEC_REGION_WIN", "INVOKE_REGION_WIN"], str(ctxs))
    check("Run As is saved with the item", "call_mode" in PM.ITEM_FIELDS)
    p.pies.remove(len(p.pies) - 1)

    # Edit Mode
    bpy.ops.object.mode_set(mode='EDIT')
    rows, err, bad = q_rows(q)
    check("Q Menu, Edit Mode: boolean on the selection, then Mesh and Modifiers submenus",
          not err and "Boolean Cut Selected" in labels(rows) and ("SUBMENU", "Mesh") in rows
          and ("SUBMENU", "Object") not in rows, str(rows))
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.objects.remove(other)

    # ---- 4. the preview: hovering a submenu item opens it beside the menu, where it can be edited
    q = next(x for x in p.pies if x.preset == "q_menu")
    p.active_pie = list(p.pies).index(q)
    p.pie_slot = 0
    MC._chain[:] = []
    mods_i = next(i for i, it in enumerate(q.items) if it.kind == "SUBMENU" and it.label == "Modifiers")
    mods = PM.find_pie(q.items[mods_i].idname)
    sc = MC.build(q, p, mods_i)
    beside = [el for el in sc.els if el.index >= MC.SUB_STRIDE and el.kind == "item"]
    opener = next(el for el in sc.els if el.index == mods_i)
    check("preview: hovering Modifiers opens its submenu beside the menu",
          len(sc.subs) == 2 and [el.text for el in beside][:2] == ["Mirror", "Bevel"]
          and sc.subs[1].frame[0] >= sc.subs[0].frame[0] + sc.subs[0].frame[2] - MC.unit()
          and not sc.subs[1].title, str([el.text for el in beside][:3]))
    check("preview: the submenu's first row is level with the item that opens it",
          abs((beside[0].y + beside[0].h) - (opener.y + opener.h)) <= 2, f"{beside[0].y} vs {opener.y}")
    sc = MC.build(q, p, None)
    check("preview: the submenu stays open while the mouse moves over to it", len(sc.subs) == 2)
    sc = MC.build(q, p, beside[0].index)
    check("preview: hovering an item in the submenu keeps it open", len(sc.subs) == 2)
    found = MC.chain_item(beside[1].index)
    check("preview: an item in the submenu maps to that menu and item", found is not None
          and found[0].uid == mods.uid and found[0].items[found[1]].label == "Bevel", str(found))
    p.active_pie = list(p.pies).index(mods)  # what the submenu's button in the row above the editor does
    p.pie_slot = found[1]
    check("preview: editing the submenu keeps the menu above on screen", len(MC.build(mods, p, None).subs) == 2)
    MC.close_submenus_after(q)
    p.active_pie = list(p.pies).index(q)
    p.pie_slot = 0
    sc = MC.build(q, p, None)
    check("preview: clicking an item that opens nothing closes the submenu", not sc.subs, str(len(sc.subs)))
    obj_i = next(i for i, it in enumerate(q.items) if it.kind == "SUBMENU" and it.label == "Object")
    sc = MC.build(q, p, obj_i)
    check("preview: hovering another submenu item opens that one instead", len(sc.subs) == 2
          and any(el.text == "Smart Apply Scale" for el in sc.els if el.index >= MC.SUB_STRIDE))
    check("preview: the open submenu's icons are captured too",
          all(n in MC.icons_needed(q) + [m for u in MC._chain for m in MC.icons_needed(PM.find_pie(u))]
              for n in MC.icons_needed(PM.find_pie(q.items[obj_i].idname))))
    MC._chain[:] = []

    # ---- 5. the icon palette: a grid of single icons (no row lights up on hover), Key Ops' icons in it
    wm = C.window_manager
    wm.keyops_icon_category = "KEYOPS"
    PM.rebuild_icon_rows(wm)
    grid = PM._grid_lists()  # Blender 5.4 has no grid lists: then each list row holds a row of icons
    own = [n for r in wm.keyops_icon_rows for n in r.names.split()]
    check("icon palette: the Key Ops tab lists the add-on's icons, one per cell",
          own and all(n.startswith("keyops:") and "," not in n for n in own) and "keyops:union" in own
          and (not grid or len(own) == len(wm.keyops_icon_rows)), str(own[:4]))
    wm.keyops_icon_category = "ALL"
    PM.rebuild_icon_rows(wm)
    log = []
    fake = type("Panel", (), {"layout": Rec(log)})()
    try:
        PM.KEYOPS_PT_icon_palette.draw(fake, C)
        err = None
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
    lists = [e["kw"] for e in log if e["fn"] == "template_list"]
    # icon buttons outside the list (the header's "No Icon" button doesn't count)
    icon_ops = [e for e in log if e["fn"] == "operator" and e.get("text") != "No Icon"]
    # always a list, so it keeps its scroll bar: a grid list, or (5.4+, no grid lists) a row list
    check("icon palette: drawn as a scrollable list with only real Blender calls",
          not err and lists and not icon_ops and lists[0].get("maxrows") == PM.ICON_ROWS
          and ((lists[0].get("type") == 'GRID' and lists[0].get("columns") == PM.ICON_COLUMNS)
               if grid else lists[0].get("type", 'DEFAULT') == 'DEFAULT'),
          str(err or lists or log[-3:]))
    log = []
    try:
        for n in (0, len(wm.keyops_icon_rows) - 1):
            PM.KEYOPS_UL_icon_rows.draw_item(None, C, Rec(log), wm, wm.keyops_icon_rows[n], 0, wm, "keyops_icon_row_index", n)
        err = None
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
    ops = [e for e in log if e["fn"] == "operator"]
    check("icon palette: each cell is one icon button, Key Ops' and Blender's alike",
          not err and (len(ops) == 2 if grid else
                       len(ops) == len(wm.keyops_icon_rows[0].names.split()) + len(wm.keyops_icon_rows[-1].names.split())),
          str(err or log[:4]))

    # ---- 6. hovering an item in the preview: the part a click acts on, and what the click does
    class FakeRegion:
        def as_pointer(self):
            return 987654321
    reg = FakeRegion()
    st = MC._canvas(reg)
    add = next(x for x in p.pies if x.preset == "add_objects")
    p.active_pie = list(p.pies).index(add)
    p.pie_slot = 5
    for hover, zone in ((0, "icon"), (0, "item")):
        st.scene, st.hover, st.hover_zone, st.drag = MC.build(add, p, hover), hover, zone, None
        el = next(e for e in st.scene.els if e.index == hover and e.kind == "item")
        rect = MC._zone_rect(st, el, zone)
        inside = rect and el.x - 1 <= rect[0] and rect[0] + rect[2] <= el.x + el.w + 1
        check(f"preview: hovering a pie item's {zone} outlines that part of it", inside, str((rect, el.x, el.w)))
    st.hover_zone = "icon"
    check("preview: the hint says a click on the icon changes it", MC.hover_hint(reg) == "Click: change the icon")
    st.hover_zone = "item"
    check("preview: on an item that isn't selected, a click selects it", "select it" in MC.hover_hint(reg))
    p.pie_slot = 0
    check("preview: on the selected item, a click changes what it does", "change what it does" in MC.hover_hint(reg))
    st.hover = None
    check("preview: away from the items, no hint (the usual line shows)", MC.hover_hint(reg) == "")
    MC._canvases.pop(reg.as_pointer(), None)

    # ---- 7. nested submenus and submenus that point at themselves never loop
    loop = new_menu("MENU", "Loop")
    it = loop.items.add()
    it.kind, it.idname, it.label = "SUBMENU", loop.uid, "Me again"
    log, err = draw_real(loop)
    check("a menu that opens itself as a submenu draws once (Blender opens it on hover)", not err
          and drawn_rows(log) == [("SUBMENU", "Me again")], str(drawn_rows(log)) + str(err))
    p.pies.remove(len(p.pies) - 1)

    # ---- 8. a hidden group hides everything in it, nested groups included
    panel = new_menu("PANEL", "Hidden Groups")
    for kind, label, show_if in (("BOX", "Outer", ""), ("BOX", "Hidden", "False"), ("LABEL", "inside hidden", ""),
                                 ("BOX", "Nested", ""), ("LABEL", "nested in hidden", ""), ("BOX_END", "", ""),
                                 ("BOX_END", "", ""), ("LABEL", "after hidden", ""), ("BOX_END", "", ""),
                                 ("BOX", "Open", "False"), ("LABEL", "unclosed hidden", ""),
                                 ("BREAK", "", ""), ("LABEL", "next column", "")):
        it = panel.items.add()
        it.kind, it.label, it.show_if = kind, label, show_if
    shown = [it.label for _i, it in PM.shown_items(C, list(panel.items), panel.uid) if it.kind == "LABEL"]
    check("a group hidden by Show If hides its items and nested groups, up to its End Group or the next column",
          shown == ["after hidden", "next column"], str(shown))
    tree = PM.layout_tree(list(panel.items), PM.shown_items(C, list(panel.items), panel.uid))
    check("the items after a hidden group stay in the group around it",
          tree[0][0][0] == "GROUP" and [n[0] for n in tree[0][0][2]] == ["ITEM"], str(tree))
    p.pies.remove(len(p.pies) - 1)

    # ---- 9. Only In: several modes, and the single mode older versions saved
    m = new_menu("MENU", "Modes")
    m.only_mode = "EDIT_MESH"
    check("an old single Only In mode still reads", PM.only_modes(m) == {"EDIT_MESH"})
    m.only_mode_set = {"OBJECT", "SCULPT"}
    check("Only In takes several modes", PM.only_modes(m) == {"OBJECT", "SCULPT"} and m.only_mode == "OBJECT, SCULPT",
          m.only_mode)
    check("the current mode passes when it's one of them", PM.mode_ok(C, m) == (C.mode in ("OBJECT", "SCULPT")))
    m.only_mode_set = set()
    check("no mode picked means any mode", m.only_mode == "ANY" and PM.mode_ok(C, m))
    p.pies.remove(len(p.pies) - 1)

    # ---- 10. Draw Code: draws into the layout, and a broken one shows its error instead of raising
    d = new_menu("PANEL", "Draw Code")
    good, bad = d.items.add(), d.items.add()
    good.kind, good.script = "DRAW", "layout.label(text='from code: ' + str(len(D.objects) >= 0))"
    bad.kind, bad.script, bad.label = "DRAW", "1 / 0", "Broken"
    log, err = draw_real(d)
    flat = str(log)
    check("Draw Code draws with layout, context and D", not err and "from code: True" in flat, flat[:300] + str(err))
    check("a failing Draw Code shows its error in place", "ZeroDivisionError" in flat, flat[:300])
    check("Draw Code is saved with the item", "script" in PM.ITEM_FIELDS)
    host = d.items.add()
    host.kind, host.script = "DRAW", (
        "class Other:\n"
        "    def helper(self):\n"
        "        return 'via helper'\n"
        "    def draw(self, context):\n"
        "        self.layout.prop(context.scene, 'frame_start', text=self.helper())\n"
        "draw_panel(Other)\n")
    hdr = d.items.add()
    hdr.kind, hdr.idname, hdr.label, hdr.in_header = "OPERATOR", "screen.region_toggle", "Only In Header", True
    log, err = draw_real(d)
    check("draw_panel draws another add-on's or Blender's panel into the layout", not err and any(
        e["fn"] == "prop" and e.get("text") == "via helper" for e in log), str(err))
    check("an In Header item isn't drawn in the panel's body", "Only In Header" not in str(log))
    p.pies.remove(len(p.pies) - 1)

    # ---- 11. My Properties: a choice, and real scene properties
    vals = bpy.context.window_manager.keyops_values
    v = vals.add()
    v.name, v.vtype, v.choices = "Test Detail", "ENUM", "Low, Medium, High"
    v.enum_value = "MEDIUM"
    check("a Choice property keeps its option", v.string_value == "MEDIUM" and v.enum_value == "MEDIUM", v.string_value)
    check("tests read My Properties by name", PM.safe_test("values['Test Detail'] == 'MEDIUM'", C))
    v.owner = "SCENE"
    PM.sync_custom_props()
    scene = bpy.context.scene
    check("a Scene property is a real property of every scene, its value the default",
          getattr(scene, "keyops_test_detail", None) == "MEDIUM", str(getattr(scene, "keyops_test_detail", None)))
    scene.keyops_test_detail = "HIGH"
    check("a Setting item reaches it by its path", PM._resolve(C, v.path)[1] == "keyops_test_detail"
          and PM.values_by_name(C)["Test Detail"] == "HIGH")
    vals.remove(len(vals) - 1)
    PM.sync_custom_props()
    check("removing it removes the real property", not hasattr(bpy.types.Scene, "keyops_test_detail"))

    # ---- 12. sidebar panel header: icon, header items, closed, order, sub-panel
    parent = new_menu("PANEL", "Header Parent")
    parent["enabled"] = True
    child = new_menu("PANEL", "Header Child")
    child["enabled"] = True
    child.panel_parent, child.panel_closed, child.panel_order = parent.uid, True, 5
    hb = parent.items.add()
    hb.kind, hb.idname, hb.label, hb.in_header = "OPERATOR", "screen.region_toggle", "Hdr", True
    PM.sync_user_panels()
    by_label = {c.bl_label: c for c in PM._user_panels if c.bl_space_type == 'VIEW_3D'}
    pc, cc = by_label.get("Header Parent"), by_label.get("Header Child")
    check("a sub-panel sits inside its parent panel", pc is not None and cc is not None
          and getattr(cc, "bl_parent_id", "") == pc.bl_idname, str(by_label))
    check("Start Closed and Order reach the panel", cc is not None and 'DEFAULT_CLOSED' in getattr(cc, "bl_options", set())
          and cc.bl_order == 5)
    child.panel_parent = child.uid
    parent.panel_parent = child.uid
    PM.sync_user_panels()
    check("panels inside each other in a loop still register, as panels of their own",
          {"Header Parent", "Header Child"} <= {c.bl_label for c in PM._user_panels})
    p.pies.remove(len(p.pies) - 1)
    p.pies.remove(len(p.pies) - 1)
    PM.sync_user_panels()


try:
    run()
except Exception:
    traceback.print_exc()
    results.append(("no exception", False, ""))

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
