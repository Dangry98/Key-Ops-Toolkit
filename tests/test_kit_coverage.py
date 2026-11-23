"""Headless checks that Custom Menus can rebuild Blender's own menus, panels and headers 1:1.

Each check builds a Key Ops menu from items the way a person would in the editor, copying a piece of
Blender's UI (the Add menu, the material slots panel, the vertex groups panel, a header row, the
snapping and pivot settings, the color and curve editors), draws it through the recording layout from
test_menu_drawing.py (every call checked against this Blender's real UILayout API), and checks that the
same Blender calls come out that Blender's own draw code makes. Also checks that the new item fields
survive saving and loading, and that the editor preview builds for every rebuilt menu.

Run in both the minimum and the newest Blender:
    blender -b --factory-startup --python tests/test_kit_coverage.py
Exits non-zero on failure.
"""

import os
import sys
import traceback

import addon_utils
import bpy

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def load_recorder():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_menu_drawing.py")
    src = open(path, encoding="utf-8").read().split("\ndef run():", 1)[0]
    ns = {"__name__": "menu_drawing_recorder"}
    exec(compile(src, path, "exec"), ns)
    return ns["Rec"]


def run():
    addon_utils.enable(MOD, default_set=True)
    pkg = sys.modules[MOD]
    PM, MC = pkg.pie_menus, pkg.ui.menu_canvas
    p = bpy.context.preferences.addons[MOD].preferences
    C = bpy.context
    Rec = load_recorder()
    type_value = {t[0]: t[4] for t in PM.MENU_TYPES}

    # a scene to draw against: an active mesh with a material and a vertex group
    cube = bpy.data.objects.get("Cube")
    if cube is None:
        bpy.ops.mesh.primitive_cube_add()
        cube = C.active_object
    C.view_layer.objects.active = cube
    cube.select_set(True)
    if not cube.material_slots:
        cube.data.materials.append(bpy.data.materials.new("Mat"))
    if not cube.vertex_groups:
        cube.vertex_groups.new(name="Group")
    tex = bpy.data.textures.new("Ramp", type='BLEND')
    tex.use_color_ramp = True
    if C.scene.world is None:
        C.scene.world = bpy.data.worlds.new("World")

    def new_menu(menu_type, name):
        pie = PM._new_pie(p)
        pie["enabled"], pie["menu_type"] = False, type_value[menu_type]
        pie.name, pie.key = name, "NONE"
        pie.items.clear()
        return pie

    def add(pie, kind, idname="", label="", **fields):
        it = pie.items.add()
        it.kind, it.idname, it.label = kind, idname, label
        for k, v in fields.items():
            setattr(it, k, v)
        return it

    def draw(pie):
        log = []
        root = Rec(log)
        try:
            items = list(pie.items)
            if pie.menu_type == "MENU" and not PM.needs_panel_popup(items):
                PM.draw_popup_menu(root, C, items, pie.uid)
            elif pie.menu_type == "MENU":
                PM.draw_columns(root, C, items, pie.uid)
            elif pie.menu_type == "PIE":
                PM.draw_pie_items(root.menu_pie(), C, items, pie.uid)
            else:
                PM.draw_grid(root, C, pie)
            return log, None
        except Exception as e:  # noqa: BLE001
            return log, f"{type(e).__name__}: {e}"

    def fns(log):
        return [e["fn"] for e in log]

    def errors(log):
        return [e["text"] for e in log if e["fn"] == "label" and e.get("kw", {}).get("icon") == 'ERROR']

    def preview_ok(pie):
        try:
            MC.build(pie, p)
            return True, ""
        except Exception as e:  # noqa: BLE001
            return False, f"{type(e).__name__}: {e}"

    made = []

    # ---- Blender's Add menu (VIEW3D_MT_add): submenus open on hover, Empty and Light are enum dropdowns
    m = new_menu("MENU", "Add (rebuilt)")
    add(m, PM.M, "VIEW3D_MT_mesh_add", "Mesh", icon="OUTLINER_OB_MESH")
    add(m, PM.M, "VIEW3D_MT_curve_add", "Curve", icon="OUTLINER_OB_CURVE")
    add(m, PM.N)
    add(m, PM.O, "object.text_add", "Text", icon="OUTLINER_OB_FONT")
    add(m, PM.O, "object.empty_add", "Empty", icon="OUTLINER_OB_EMPTY", op_style="MENU", enum_prop="type")
    add(m, PM.O, "object.light_add", "Light", icon="OUTLINER_OB_LIGHT", op_style="MENU", enum_prop="type")
    log, err = draw(m)
    made.append(m.name)
    f = fns(log)
    check("Add menu: draws with only real Blender calls", err is None, err or "")
    check("Add menu: menu items open as hover submenus (layout.menu), like Blender's own",
          f.count("menu") == 2 and not any(e["fn"] == "operator" and e["kw"].get("operator") == "wm.call_menu"
                                           for e in log), str(f))
    check("Add menu: Empty and Light are operator enum dropdowns (operator_menu_enum)",
          f.count("operator_menu_enum") == 2, str(f))

    # ---- menu styles: button, dropdown, inline contents
    m = new_menu("DIALOG", "Menu styles")
    add(m, PM.M, "VIEW3D_MT_transform", "Button", menu_style="BUTTON")
    add(m, PM.M, "VIEW3D_MT_transform", "Dropdown", menu_style="SUBMENU")
    add(m, PM.M, "VIEW3D_MT_transform", "Inline", menu_style="INLINE")
    log, err = draw(m)
    made.append(m.name)
    f = fns(log)
    inline = "menu_contents" in f if "menu_contents" in bpy.types.UILayout.bl_rna.functions else f.count("operator") == 2
    check("Menu styles: button, dropdown and inline draw", err is None and "menu" in f and inline, err or str(f))

    # ---- mesh select mode buttons (operator_enum)
    m = new_menu("DIALOG", "Select mode")
    add(m, PM.O, "mesh.select_mode", op_style="EXPAND", enum_prop="type")
    log, err = draw(m)
    made.append(m.name)
    check("Select mode: one button per value (operator_enum)", err is None and "operator_enum" in fns(log),
          err or str(fns(log)))

    # ---- material slots panel (EEVEE_MATERIAL_PT_context_material): list + data-block selector
    m = new_menu("PANEL", "Material (rebuilt)")
    add(m, PM.P, "object.material_slots", setting_style="LIST")
    add(m, PM.P, "object.active_material", setting_style="ID", source="material.new")
    log, err = draw(m)
    made.append(m.name)
    f = fns(log)
    tl = next((e for e in log if e["fn"] == "template_list"), None)
    check("Material panel: slot list and data-block selector draw", err is None and tl is not None
          and "template_ID" in f, err or str(f))
    check("Material panel: the list's active index is found by itself (active_material_index)",
          tl is not None and tl["kw"].get("active_propname") == "active_material_index",
          str(tl and tl["kw"].get("active_propname")))
    tid = next((e for e in log if e["fn"] == "template_ID"), None)
    check("Material panel: New button runs material.new", tid is not None and tid["kw"].get("new") == "material.new")

    # ---- vertex groups (DATA_PT_vertex_groups): the list's index lives on the collection itself
    m = new_menu("PANEL", "Vertex Groups (rebuilt)")
    add(m, PM.P, "object.vertex_groups", setting_style="LIST", props="rows=3")
    log, err = draw(m)
    made.append(m.name)
    tl = next((e for e in log if e["fn"] == "template_list"), None)
    check("Vertex groups: list with vertex_groups.active_index, rows from Options",
          err is None and tl is not None and tl["kw"].get("active_propname") == "active_index"
          and tl["kw"].get("rows") == 3, err or str(tl and tl["kw"]))

    # ---- object parent search field (OBJECT_PT_relations) with bpy.data paths
    m = new_menu("DIALOG", "Relations (rebuilt)")
    add(m, PM.P, "object.parent", "Parent", setting_style="SEARCH", source="bpy.data.objects")
    add(m, PM.P, "object.data.uv_layers", setting_style="LIST")
    add(m, PM.P, "object.parent", "No source", setting_style="SEARCH")
    log, err = draw(m)
    made.append(m.name)
    ps = next((e for e in log if e["fn"] == "prop_search"), None)
    check("Relations: search field searches bpy.data.objects (prop_search)",
          err is None and ps is not None and ps["kw"].get("search_property") == "objects", err or str(fns(log)))
    check("Relations: a search without Search In says so instead of failing",
          any("Search In" in (t or "") for t in errors(log)), str(errors(log)))

    # ---- pivot point buttons and header row (VIEW3D_HT_header): one option, tabs, spacer
    m = new_menu("PANEL", "Header (rebuilt)")
    add(m, PM.BOX, group_type="ROW", align=True)
    add(m, PM.P, "scene.tool_settings.transform_pivot_point", setting_style="VALUE", source="MEDIAN_POINT",
        icon="PIVOT_MEDIAN", label="")
    add(m, PM.P, "scene.tool_settings.transform_pivot_point", setting_style="VALUE", source="CURSOR",
        icon="PIVOT_CURSOR", label="")
    add(m, PM.N, sep_type="SPACER")
    add(m, PM.P, "scene.render.engine", setting_style="MENU")
    add(m, PM.BOX_END)
    add(m, PM.P, "space_data.shading.type", setting_style="TABS")
    add(m, PM.P, "scene.tool_settings.use_snap", setting_style="POPOVER", source="VIEW3D_PT_snapping", label="")
    log, err = draw(m)
    made.append(m.name)
    f = fns(log)
    check("Header: one-option buttons, spacer, dropdown and tabs",
          err is None and f.count("prop_enum") == 2 and "separator_spacer" in f and "prop_menu_enum" in f,
          err or str(f))
    check("Header: snapping toggle with its popover (prop_with_popover)", "prop_with_popover" in f, str(f))

    # ---- transform panel details: one value of an array, inverted checkbox, keyframe dot, enabled
    m = new_menu("PANEL", "Transform (rebuilt)")
    add(m, PM.BOX, group_type="COLUMN", prop_split=True, decorate=True)
    add(m, PM.P, "object.location", "X", index=0)
    add(m, PM.P, "object.hide_render", "Show in Renders", invert=True)
    add(m, PM.P, "object.rotation_mode", decorate=True)
    add(m, PM.O, "object.transform_apply", "Apply", enabled=False)
    add(m, PM.BOX_END)
    add(m, PM.P, "scene.transform_orientation_slots[0].type", "Orientation")
    add(m, PM.P, "D.objects", setting_style="LIST")
    log, err = draw(m)
    made.append(m.name)
    props = [e for e in log if e["fn"] == "prop"]
    check("Transform: X alone (index=0) and an inverted checkbox",
          err is None and any(e["kw"].get("index") == 0 for e in props)
          and any(e["kw"].get("invert_checkbox") for e in props), err or str([e["kw"] for e in props]))
    check("Transform: indexed setting paths work (transform_orientation_slots[0].type)",
          any(e["kw"].get("property") == "type" for e in props)
          and not any("check command" in (t or "") for t in errors(log)), str(errors(log)))
    check("Transform: D. paths resolve (D.objects), a list without an index says so",
          any("Active Index" in (t or "") for t in errors(log)), str(errors(log)))

    # ---- editors: color wheel, ramp, curve
    m = new_menu("PANEL", "Editors (rebuilt)")
    add(m, PM.P, "scene.world.color", "World Color", setting_style="COLOR")
    add(m, PM.P, "D.textures['Ramp'].color_ramp", setting_style="RAMP")
    add(m, PM.P, "scene.view_settings.curve_mapping", setting_style="CURVE")
    log, err = draw(m)
    made.append(m.name)
    f = fns(log)
    check("Editors: color wheel, color ramp and curve mapping",
          err is None and {"template_color_picker", "template_color_ramp", "template_curve_mapping"} <= set(f),
          err or str(f))

    # ---- a popup menu with a list opens as a panel (a menu row can't hold it)
    m = new_menu("MENU", "Menu with list")
    add(m, PM.P, "object.material_slots", setting_style="LIST")
    check("Popup menu with a list opens as a popup panel", PM.needs_panel_popup(list(m.items)))

    # ---- a pie with several buttons in one direction (viewport_pie_menus' shading pie, Blender's snap pie)
    new_menu("PIE", "Pie with group (rebuilt)")
    new_menu("MENU", "Pie group")
    pie = next(x for x in p.pies if x.name == "Pie with group (rebuilt)")  # fetched after both are added
    grp = next(x for x in p.pies if x.name == "Pie group")
    for _n in range(8):
        add(pie, PM.N)
    grp.owner = pie.uid
    for op, lbl in (("object.shade_smooth", "Smooth"), ("object.shade_flat", "Flat"),
                    ("object.shade_auto_smooth", "Auto Smooth")):
        add(grp, PM.O, op, lbl)
    slot = pie.items[0]  # West
    slot.kind, slot.idname, slot.sub_style, slot.group_type, slot.align = PM.SUB, grp.uid, "INLINE", "BOX", True
    slot.label = "Shading"
    pie.items[1].kind, pie.items[1].idname, pie.items[1].label = PM.O, "object.select_all", "All"
    log, err = draw(pie)
    made.append(pie.name)
    f = fns(log)
    ops = [e["kw"].get("operator") for e in log if e["fn"] == "operator"]
    check("Pie group: three buttons in one direction, in a box with a heading",
          err is None and ops[:3] == ["object.shade_smooth", "object.shade_flat", "object.shade_auto_smooth"]
          and "box" in f and any(e["fn"] == "label" and e["text"] == "Shading" for e in log), err or str(f))
    check("Pie group: the next direction still gets its own item", ops[3:] == ["object.select_all"], str(ops))
    try:
        sc = MC.build(pie, p)
        n_els = len([e for e in sc.els if e.index == 0 and e.kind == "item"])
        check("Pie group: the preview shows the group's three buttons in that direction", n_els == 3, str(n_els))
    except Exception as e:  # noqa: BLE001
        check("Pie group: the preview shows the group's three buttons in that direction", False, repr(e))
    loop = new_menu("MENU", "Loop group")
    add(loop, PM.SUB, loop.uid, sub_style="INLINE", group_type="COLUMN")
    log, err = draw(loop)
    check("Pie group: a group inside itself says so instead of looping",
          err is None and any("contains itself" in (t or "") for t in errors(log)), err or str(errors(log)))
    # ---- the preview builds for every rebuilt menu
    bad = []
    for pie in [x for x in p.pies if x.name in made]:  # by name: references go stale as menus are added
        ok, msg = preview_ok(pie)
        if not ok:
            bad.append(f"{pie.name}: {msg}")
    check("Preview builds for every rebuilt menu", not bad, "; ".join(bad[:3]))

    # ---- the new fields survive saving and loading
    data = PM.pies_to_data(p)
    saved = [d for d in data["pies"] if d.get("name") in set(made)]
    flat = [it for d in saved for it in d["items"]]
    check("Saving keeps the new item fields",
          any(it.get("op_style") == "MENU" for it in flat) and any(it.get("source") == "material.new" for it in flat)
          and any(it.get("index") == 0 for it in flat) and any(it.get("sep_type") == "SPACER" for it in flat))
    names = list(made)
    PM.pies_from_data(p, data, False)
    back = [x for x in p.pies if x.name in names]
    flat = [it for x in back for it in x.items]
    check("Loading brings them back",
          any(it.op_style == "MENU" and it.enum_prop == "type" for it in flat)
          and any(it.setting_style == "ID" and it.source == "material.new" for it in flat)
          and any(it.invert for it in flat) and any(not it.enabled for it in flat))

    # the editor's Add Group button: a group menu owned by the pie, drawn in a free direction
    pie = next(x for x in p.pies if x.name == "Pie with group (rebuilt)")  # earlier references are stale now
    p.active_pie = list(p.pies).index(pie)
    before = len(p.pies)
    r = bpy.ops.keyops.submenu_add(group=True)
    new = p.pies[-1] if len(p.pies) > before else None
    slot2 = next((it for it in pie.items if it.kind == PM.SUB and new is not None and it.idname == new.uid), None)
    check("Add Group: makes a group menu and puts it in a free pie direction",
          r == {'FINISHED'} and new is not None and new.menu_type == "MENU" and new.owner == pie.uid
          and slot2 is not None and slot2.sub_style == "INLINE" and list(pie.items).index(slot2) == 2,
          str((r, new and new.menu_type, slot2 and slot2.sub_style)))

try:
    run()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    results.append(("run", False, "exception"))

failed = [r for r in results if not r[1]]
print(f"\nkit coverage: {len(results) - len(failed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
