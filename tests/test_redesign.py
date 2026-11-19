"""Headless checks for the 1.0 preferences/shortcut redesign.

Run with the add-on installed as an extension in the user_default repository:
    blender -b --factory-startup --python tests/test_redesign.py
Exits non-zero on failure.
"""

import sys
import traceback

import addon_utils
import bpy

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def user_keymap_snapshot():
    """Blender's own (non add-on) user keymap items, to prove we never edit them."""
    wm = bpy.context.window_manager
    snap = []
    for km in wm.keyconfigs.user.keymaps:
        for kmi in km.keymap_items:
            if kmi.idname.startswith("keyops.") or getattr(kmi.properties, "name", "").startswith("KEYOPS_"):
                continue
            snap.append((km.name, kmi.idname, kmi.type, kmi.value, kmi.ctrl, kmi.shift, kmi.alt, kmi.active))
    return sorted(snap, key=repr)


def call_menu(uid):
    """Open a Key Ops menu like a key press would (invoke needs a window, even in background mode)."""
    win = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=win, screen=win.screen):
        return bpy.ops.wm.keyops_call_pie('INVOKE_DEFAULT', pie=uid)


def addon_items():
    kc = bpy.context.window_manager.keyconfigs.addon
    return [(km.name, kmi) for km in kc.keymaps for kmi in km.keymap_items]


def active_addon_items():
    return [x for x in addon_items() if x[1].active]


def run():
    import os, shutil
    # start like a fresh install: no settings files from an earlier run
    user_dir = bpy.utils.extension_path_user(MOD)
    if os.path.isdir(user_dir):
        shutil.rmtree(user_dir)
    before = user_keymap_snapshot()
    addon_utils.enable(MOD, default_set=True)
    pkg = sys.modules[MOD]
    F = pkg.features
    PM = pkg.pie_menus
    p = bpy.context.preferences.addons[MOD].preferences

    # ---- fresh install (before the welcome screen)
    check("fresh install binds zero shortcuts", F.live_shortcut_count() == 0, str(F.live_shortcut_count()))
    check("fresh install: pies listed but none active", len(p.pies) == 9 and PM.live_count() == 0,
          f"{len(p.pies)} pies, {PM.live_count()} keys")
    feats, keys, repl = F.stats(p)
    check("fresh install still turns UI features on", feats >= 10, f"{feats} features")
    check("toolkit N-panel registered (original design)", hasattr(bpy.types, "KEYOPS_PT_new_toolkit_panel"))
    tabs = [i.identifier for i in p.bl_rna.properties["ui_tab"].enum_items]
    check("tabs: Features, Pie Menus, Shortcuts last", tabs == ["FEATURES", "PIES", "SHORTCUTS"], str(tabs))
    W = sys.modules[MOD + ".ui.welcome"]
    BR = sys.modules[MOD + ".ui.branding"]
    SP = sys.modules[MOD + ".ui.splash"]
    if os.path.isfile(SP._seen_path()):
        os.remove(SP._seen_path())  # a fresh install has no record of screens shown
    check("new install shows the welcome screen", W.first_screen(p) == 'WELCOME')
    p.welcome_version = F.WELCOME_VERSION
    p.last_seen_version = BR.version_text()
    check("nothing shows again for the same version", W.first_screen(p) is None)
    p.last_seen_version = "0.0.1"
    check("an update shows What's New once", W.first_screen(p) == 'WHATS_NEW')
    SP.mark_seen(p)
    p.last_seen_version = "0.0.1"   # Blender didn't save its preferences...
    p.show_whats_new = True         # ...and the 0.2 upgrade asked for What's New again
    check("What's New never shows twice for one version, even if preferences weren't saved",
          W.first_screen(p) is None)
    os.remove(SP._seen_path())
    p.show_whats_new = False
    p.last_seen_version = ""
    p.welcome_version = 0
    check("pies not in Features", not any(f.category == "PIES" or "pie" in f.id for f in F.FEATURES))

    # ---- welcome preset: Blender+
    p.shortcut_style = "BLENDER_PLUS"; F.apply_style("BLENDER_PLUS")
    feats, keys, repl = F.stats(p)
    check("Blender+ adds only free keys", keys > 0 and repl == 0, f"{keys} keys, {repl} replacing")
    pie_keys = {(km.name, kmi.type, kmi.shift, kmi.alt) for km, kmi in PM._pie_keymaps}
    check("Blender+ enables Add Objects pie on Shift Alt A", ("3D View Generic", "A", True, True) in pie_keys, str(pie_keys))
    check("viewport pies also win in Object Mode", ("Object Mode", "A", True, True) in pie_keys)
    check("Blender+ does not take Shift S", not any(k[1] == "S" and k[2] for k in pie_keys))
    names = {(km, kmi.type) for km, kmi in active_addon_items()}
    check("Blender+ does NOT take Delete", ("Mesh", "DEL") not in names)

    # ---- welcome preset: Industry (0.2 parity)
    F.apply_style("INDUSTRY")
    feats, keys, repl = F.stats(p)
    names = {(km, kmi.type) for km, kmi in active_addon_items()}
    check("Industry replaces Blender keys", repl > 0, f"{keys} keys, {repl} replacing")
    check("Industry has Delete auto delete", ("Mesh", "DEL") in names)
    check("Industry enables Cursor pie on Shift S", any(kmi.type == "S" and kmi.shift for _km, kmi in PM._pie_keymaps))
    industry_live = F.live_shortcut_count()

    # ---- per-feature shortcut switch
    p.keys_auto_delete = False
    check("keys off -> auto delete operator still registered", hasattr(bpy.ops.keyops, "auto_delete"))
    check("keys off -> Delete inactive", not any(kmi.type == "DEL" and kmi.active for _k, kmi in addon_items()))
    p.keys_auto_delete = True

    # ---- pause all (features + pies)
    p.pause_shortcuts = True
    check("pause -> zero live shortcuts and pie keys", F.live_shortcut_count() == 0 and PM.live_count() == 0)
    p.pause_shortcuts = False
    check("resume -> shortcuts back", F.live_shortcut_count() == industry_live and PM.live_count() > 0)

    # ---- feature off/on
    p.enable_maya_pivot = False
    check("feature off removes its keymap items", not any(kmi.idname == "keyops.pivot_press" for _k, kmi in addon_items()))
    p.enable_maya_pivot = True
    check("feature on restores its keymap items", any(kmi.idname == "keyops.pivot_press" for _k, kmi in addon_items()))

    # ---- pies are editable
    pie = next(x for x in p.pies if x.preset == "add_objects")
    pie.key, pie.shift, pie.alt = "A", True, False
    PM.sync_keymaps()
    check("pie key can be changed (Add Objects on Shift A)",
          any(kmi.type == "A" and kmi.shift and not kmi.alt and kmi.properties.pie == pie.uid for _km, kmi in PM._pie_keymaps))
    pie.items[1].label = "Big Cube"
    check("pie slots are editable", pie.items[1].label == "Big Cube")
    check("renamed slot shows as 'your own' in the dropdown", pie.items[1].choice == "CUSTOM")
    pie.items[1].choice = "EMPTY"
    check("dropdown can empty a slot", pie.items[1].kind == "NONE")
    weld = next(f"C{i}" for i, c in enumerate(PM._CATALOG) if c[2] == "Weld")
    pie.items[1].choice = weld
    check("dropdown fills a slot from any preset (Weld into Add Objects)",
          pie.items[1].idname == "keyops.add_modifier" and pie.items[1].props == "type='WELD'" and pie.items[1].choice == weld)
    p.active_pie = list(p.pies).index(pie)
    bpy.ops.keyops.pie_reset()
    check("reset to preset restores slots and key", pie.items[1].label == "Cube" and pie.alt)

    # ---- searchable pickers and icon palette
    it = pie.items[0]
    PM.apply_action(it, "O:mesh.primitive_monkey_add")
    check("search: any Blender operator fills a slot", it.idname == "mesh.primitive_monkey_add" and it.label == "Add Monkey" and it.icon == "")
    p.pie_slot = 0
    bpy.ops.keyops.pie_set_icon(icon="MONKEY", slot=0)
    check("icon palette sets the slot icon", it.icon == "MONKEY")
    cats = {c for c in PM._ICON_CAT.values()}
    check("icon palette has category tabs", {"OBJECTS", "MODIFIERS", "EDITING", "VIEW", "ARROWS", "KEYS"} <= cats, str(sorted(cats)))
    check("Modifier icons land in the Modifiers tab", PM._ICON_CAT.get("MOD_ARRAY") == "MODIFIERS" and PM._ICON_CAT.get("MESH_CUBE") == "OBJECTS")
    bpy.context.window_manager.keyops_icon_category = "MODIFIERS"
    check("the category tabs switch the palette category", bpy.context.window_manager.keyops_icon_category == "MODIFIERS")
    check("operator search list includes Blender operators", any(i[0] == "O:mesh.primitive_monkey_add" for i in PM._all_operator_items()))
    PM.apply_action(it, "EMPTY")
    check("search: Empty clears a slot", it.kind == "NONE" and it.idname == "")

    # ---- users can add their own pie
    n = len(p.pies)
    bpy.ops.keyops.pie_add()
    mine = p.pies[-1]
    mine.name = "My Pie"
    mine.items[0].kind, mine.items[0].label, mine.items[0].idname = "OPERATOR", "Cube", "mesh.primitive_cube_add"
    mine.items[1].kind, mine.items[1].idname = "PROPERTY", "scene.tool_settings.use_snap"
    mine.key, mine.ctrl = "J", True
    mine.enabled = True
    check("user can add a pie", len(p.pies) == n + 1)
    check("user pie gets its key", any(kmi.properties.pie == mine.uid and kmi.type == "J" and kmi.ctrl
                                        for _km, kmi in PM._pie_keymaps))
    check("pie option parsing", PM._parse_props("type='WELD', segments=4") == {"type": "WELD", "segments": 4})
    check("pie command operator registered", hasattr(bpy.ops.wm, "keyops_call_pie"))
    check("preset operators registered (add_mesh, fast_array, flatten)",
          all(hasattr(bpy.ops.keyops, o) for o in ("add_mesh", "fast_array", "flatten", "switch_workspace")))
    check("old fixed pie keys not registered", not any(kmi.idname == "wm.call_menu_pie" and
          getattr(kmi.properties, "name", "").startswith("KEYOPS_MT_") for _k, kmi in addon_items()))
    bpy.ops.keyops.pie_remove()
    check("user can delete a pie", len(p.pies) == n)

    # ---- settings files in the add-on's user folder, export / import
    import json, os, tempfile
    S = sys.modules[MOD + ".settings_store"]
    S.flush_now()
    pie_file = S.section_path("pie_menus")
    user_dir = bpy.utils.extension_path_user(MOD)
    check("pie menus are saved as JSON in the add-on's user folder",
          os.path.isfile(pie_file) and os.path.dirname(pie_file) == os.path.normpath(user_dir), pie_file)
    p.pies[0].name = "Renamed Pie"
    S.flush_now()
    saved = json.load(open(pie_file))
    check("a change is written to pie_menus.json", saved["data"]["pies"][0]["name"] == "Renamed Pie")
    p.pies.clear()
    PM.load_from_disk()
    check("pies come back from the file (e.g. after reinstalling)", len(p.pies) >= 9 and p.pies[0].name == "Renamed Pie")
    tmp = os.path.join(tempfile.mkdtemp(), "keyops.json")
    bpy.ops.keyops.settings_export(filepath=tmp, scope="ALL")
    bundle = json.load(open(tmp))
    check("export writes every section", {"preferences", "pie_menus"} <= set(bundle["sections"]), str(list(bundle["sections"])))
    check("export includes feature switches automatically", "enable_auto_delete" in bundle["sections"]["preferences"]["data"])
    cad_before = p.enable_cad_decimate
    p.enable_cad_decimate = not cad_before
    p.pies[0].name = "Changed"
    bpy.ops.keyops.settings_import(filepath=tmp, scope="ALL", mode="REPLACE")
    check("import restores feature settings", p.enable_cad_decimate == cad_before)
    check("import restores pie menus", p.pies[0].name == "Renamed Pie")
    n_pies = len(p.pies)
    bundle["sections"]["pie_menus"]["data"]["pies"][0]["uid"] = "imported01"
    bundle["sections"]["pie_menus"]["data"]["pies"][0]["name"] = "Shared Pie"
    json.dump(bundle, open(tmp, "w"))
    bpy.ops.keyops.settings_import(filepath=tmp, scope="PIES", mode="ADD")
    check("import with Add keeps your pies and adds new ones", len(p.pies) == n_pies + 1 and p.pies[-1].name == "Shared Pie")
    bad = os.path.join(os.path.dirname(tmp), "bad.json")
    json.dump({"hello": 1}, open(bad, "w"))
    try:
        res = bpy.ops.keyops.settings_import(filepath=bad, scope="ALL")
    except RuntimeError as e:
        res = str(e)
    check("importing a wrong file is refused with a clear message", "not a Key Ops settings file" in str(res), str(res))

    # ---- file versioning: old files migrate (with a backup), newer files are never overwritten
    import glob
    v1 = {"format": "keyops-settings", "version": 1, "section": "pie_menus",
          "data": {"pies": [{"uid": "old1", "name": "Old Pie", "enabled": True, "editor": "3D View Generic",
                             "key": "J", "ctrl": True, "future_field": "keep me",
                             "items": [{"kind": "OPERATOR", "label": "Cube", "idname": "mesh.primitive_cube_add",
                                        "props": "", "icon": "MESH_CUBE"}]}]}}
    json.dump(v1, open(pie_file, "w"))
    for f in glob.glob(os.path.join(user_dir, "pie_menus.backup-*")):
        os.remove(f)
    PM.load_from_disk()
    names = [x.name for x in p.pies]
    check("an old (schema 1) file loads and migrates", "Old Pie" in names and p.pies[0].menu_type == "PIE", str(names))
    check("a backup is kept before migrating", len(glob.glob(os.path.join(user_dir, "pie_menus.backup-schema1-*"))) == 1)
    check("presets added since that file appear once, switched off",
          any(x.preset == "view" and not x.enabled for x in p.pies) and sum(x.preset == "view" for x in p.pies) == 1)
    resaved = json.load(open(pie_file))
    check("the file is rewritten in the current schema", resaved["schema"] == PM.PIE_SCHEMA)
    check("unknown fields from other versions are kept", resaved["data"]["pies"][0].get("future_field") == "keep me")

    # button looks and layout items survive saving, and shape the layout
    m = PM._new_pie(p)
    m.name, m.menu_type = "Look Test", "MENU"
    for kind, kw in ((PM.BOX, {"label": "Add"}),
                     (PM.O, {"idname": "mesh.primitive_cube_add", "icon": "MESH_CUBE", "label": ""}),
                     (PM.O, {"idname": "mesh.primitive_uv_sphere_add", "icon": "MESH_UVSPHERE", "label": "",
                             "same_row": True}),
                     (PM.BOX_END, {}),
                     (PM.BREAK, {}),
                     (PM.O, {"idname": "object.delete", "alert": True, "emboss": False, "height": 1.5}),
                     (PM.P, {"idname": "scene.tool_settings.use_snap", "setting_style": "CHECKBOX"})):
        it = m.items.add()
        it.kind = kind
        for k, v in kw.items():
            setattr(it, k, v)
    saved = PM.pies_to_data(p)
    entry = next(e for e in saved["pies"] if e["name"] == "Look Test")
    PM.pies_from_data(p, saved, merge=False)
    m = next(x for x in p.pies if x.name == "Look Test")
    check("button looks are saved and loaded", [PM.item_text(it, "x") for it in m.items][1:3] == ["", ""]
          and m.items[2].same_row and m.items[5].alert and not m.items[5].emboss and m.items[5].height == 1.5
          and m.items[6].setting_style == "CHECKBOX", str(entry["items"][5]))
    old = {"pies": [{"items": [{"kind": PM.O, "label": "Cube", "icon": "MESH_CUBE", "display": "ICON"},
                               {"kind": PM.O, "label": "Sphere", "icon": "MESH_UVSPHERE", "display": "TEXT"},
                               {"kind": PM.O, "label": "Cone", "icon": "MESH_CONE", "display": "AUTO"}]}]}
    new = PM._migrate_pies_6_to_7(old)["pies"][0]["items"]
    check("old Icon Only / Text Only items keep their look without the Show setting",
          new[0]["label"] == "" and new[0]["icon"] == "MESH_CUBE" and new[1]["icon"] == "" and new[1]["label"] == "Sphere"
          and new[2]["label"] == "Cone" and new[2]["icon"] == "MESH_CONE" and all("display" not in d for d in new), str(new))
    old = {"pies": [{"items": [{"kind": PM.BOX, "label": "A"}, {"kind": PM.O}, {"kind": PM.BOX, "label": "B"},
                               {"kind": PM.O}, {"kind": PM.BREAK}, {"kind": PM.O}]}]}
    kinds = [d["kind"] for d in PM._migrate_pies_6_to_7(old)["pies"][0]["items"]]
    check("old boxes are closed where they used to end (next box, next column)",
          kinds == [PM.BOX, PM.O, PM.BOX_END, PM.BOX, PM.O, PM.BOX_END, PM.BREAK, PM.O], str(kinds))
    g = PM._new_pie(p)
    g.name, g.menu_type = "Group Test", "DIALOG"
    for kind, kw in ((PM.BOX, {"group_type": "BOX"}), (PM.BOX, {"group_type": "ROW", "align": True}),
                     (PM.O, {"idname": "object.delete"}), (PM.O, {"idname": "object.delete"}), (PM.BOX_END, {}),
                     (PM.O, {"idname": "object.delete"}), (PM.BOX_END, {})):
        it = g.items.add()
        it.kind = kind
        for k, v in kw.items():
            setattr(it, k, v)
    tree = PM.layout_tree(list(g.items), list(enumerate(g.items)))
    check("groups nest: a box holding an aligned row of two and one more item",
          tree == [[["GROUP", 0, [["GROUP", 1, [["ITEM", 2], ["ITEM", 3]], 4], ["ITEM", 5]], 6]]], str(tree))
    p.pies.remove(len(p.pies) - 1)
    cols = PM.layout_groups(list(enumerate(m.items)))
    check("layout: two columns, a box holding one row of two buttons",
          len(cols) == 2 and cols[0][0][0] == "BOX" and len(cols[0][0][2]) == 1 and len(cols[0][0][2][0][1]) == 2
          and [b[0] for b in cols[1]] == ["RUN", "RUN"], str(cols))
    check("a menu with rows or boxes opens as a popup panel", PM.needs_panel_popup(m.items)
          and not PM.needs_panel_popup([x for x in m.items if x.kind == PM.O and not x.same_row and x.height == 1.0]))
    p.pies.remove(list(p.pies).index(m))
    newer = dict(resaved, schema=99)
    json.dump(newer, open(pie_file, "w"))
    PM.load_from_disk()
    p.pies[0].name = "Should not be saved"
    S.flush_now()
    check("a file from a newer Key Ops is never overwritten", json.load(open(pie_file))["schema"] == 99 and S.read_only("pie_menus"))
    S._read_only.clear()
    open(pie_file, "w").write("{ not json")
    ok = PM.load_from_disk()
    check("a broken file is set aside, not deleted", not ok and glob.glob(os.path.join(user_dir, "pie_menus.unreadable-*")))
    p.pies.clear()
    PM.install_presets(p, "BLENDER_PLUS")
    S.flush_now()

    # ---- popup menus and macros
    view = next(x for x in p.pies if x.preset == "view")
    blender_view = ["view3d.view_axis"] * 6 + ["view3d.view_camera", "view3d.view_selected"]
    check("View pie matches Blender's View pie slot for slot", [i.idname for i in view.items] == blender_view and view.key == "SPACE")
    bpy.ops.keyops.pie_add(menu_type="MENU")
    menu = p.pies[-1]
    p.active_pie = len(p.pies) - 1
    bpy.ops.keyops.menu_item_add()
    bpy.ops.keyops.menu_item_add()
    PM.apply_action(menu.items[0], "O:mesh.primitive_cube_add")
    PM.apply_action(menu.items[2], "O:mesh.primitive_uv_sphere_add")
    p.pie_slot = 2
    bpy.ops.keyops.menu_item_move(direction=-1)
    check("popup menus hold any number of items and can be reordered",
          menu.menu_type == "MENU" and len(menu.items) == 3 and menu.items[1].idname == "mesh.primitive_uv_sphere_add")
    p.pie_slot = 0
    bpy.ops.keyops.slot_make_macro()
    it = menu.items[0]
    bpy.ops.keyops.macro_step_add()
    it.steps[1].idname, it.steps[1].props = "transform.translate", "value=(3, 0, 0)"
    check("an item becomes a macro, keeping its operator as step 1", it.kind == "MACRO" and it.steps[0].idname == "mesh.primitive_cube_add")
    n_obj = len(bpy.data.objects)
    bpy.ops.wm.keyops_run_macro(pie=menu.uid, slot=0)
    newest = bpy.context.object
    check("running a macro runs every step", len(bpy.data.objects) == n_obj + 1 and abs(newest.location.x - 3) < 1e-4,
          f"{len(bpy.data.objects) - n_obj} new, x={newest.location.x:.2f}")
    check("commands from the Info editor are understood",
          PM.parse_command("bpy.ops.mesh.primitive_monkey_add(size=2, location=(0, 0, 1))")
          == ("mesh.primitive_monkey_add", "size=2, location=(0, 0, 1)"))
    bpy.context.window_manager.keyops_paste_command = "bpy.ops.object.shade_smooth()"
    check("pasting a command adds it to the macro", it.steps[-1].idname == "object.shade_smooth")
    S.flush_now()
    saved = json.load(open(pie_file))["data"]["pies"][-1]
    check("popup menus and macro steps are saved", saved["menu_type"] == "MENU" and len(saved["items"][0]["steps"]) == 3)
    tmp2 = os.path.join(tempfile.mkdtemp(), "one.json")
    S.export_file(tmp2, ["pie_menus"], {"pie_menus": lambda d: dict(d, pies=[x for x in d["pies"] if x["uid"] == menu.uid])})
    check("export can include just the menus you pick", [x["name"] for x in json.load(open(tmp2))["sections"]["pie_menus"]["data"]["pies"]] == ["My Menu"])

    old_export = {"format": "keyops-settings", "version": 1,
                  "sections": {"pie_menus": {"pies": [{"uid": "fromold", "name": "From Old Export", "key": "K",
                                                       "items": []}]}}}
    tmp3 = os.path.join(tempfile.mkdtemp(), "old.json")
    json.dump(old_export, open(tmp3, "w"))
    bpy.ops.keyops.settings_import(filepath=tmp3, scope="PIES", mode="ADD")
    check("files exported by an earlier Key Ops still import", any(x.name == "From Old Export" and x.menu_type == "PIE"
                                                               and len(x.items) == 8 for x in p.pies))

    # ---- more menu types
    ts = bpy.context.scene.tool_settings
    ts.use_snap, ts.use_mesh_automerge = False, False
    bpy.ops.keyops.pie_add(menu_type="STACK")
    stack = p.pies[-1]
    p.active_pie = len(p.pies) - 1
    PM.apply_action(stack.items[0], "C0")
    stack.items[0].kind, stack.items[0].idname = "PROPERTY", "scene.tool_settings.use_snap"
    stack.items[1].kind, stack.items[1].idname = "PROPERTY", "scene.tool_settings.use_mesh_automerge"
    stack.stack_reset = 0
    call_menu(stack.uid)
    first = (ts.use_snap, ts.use_mesh_automerge)
    call_menu(stack.uid)
    second = (ts.use_snap, ts.use_mesh_automerge)
    call_menu(stack.uid)
    check("stack key runs the next item on each press, then starts over",
          first == (True, False) and second == (True, True) and ts.use_snap is False, f"{first} {second}")
    stack.only_mode = "EDIT_MESH"
    res = call_menu(stack.uid)
    check("'Only in' lets Blender's own key through in other modes", res == {'PASS_THROUGH'}, str(res))
    bpy.ops.keyops.pie_add(menu_type="PANEL")
    panel = p.pies[-1]
    panel.items[0].kind, panel.items[0].idname = "PROPERTY", "scene.render.resolution_percentage"
    check("sidebar panels appear in the 3D View sidebar", bpy.types.KEYOPS_PT_user_panels_3d.poll(bpy.context))
    bpy.ops.keyops.pie_add(menu_type="DIALOG")
    dialog = p.pies[-1]
    PM.apply_action(dialog.items[0], "O:mesh.primitive_cube_add")
    res = bpy.ops.wm.keyops_call_pie('INVOKE_DEFAULT', pie=dialog.uid)
    check("dialogs open", res in ({'RUNNING_MODAL'}, {'FINISHED'}), str(res))
    PM.apply_action(dialog.items[1], f"K:{stack.uid}")
    check("an item can open another Key Ops menu", dialog.items[1].kind == "SUBMENU" and dialog.items[1].idname == stack.uid)
    bpy.ops.keyops.pie_add(menu_type="STICKY")
    check("sticky keys have a press and a release item", len(p.pies[-1].items) == 2)
    bpy.ops.keyops.pie_add(menu_type="MODAL")
    check("modal values hold one setting", len(p.pies[-1].items) == 1 and p.pies[-1].items[0].kind == "PROPERTY")
    S.flush_now()
    saved_types = {x["menu_type"] for x in json.load(open(pie_file))["data"]["pies"]}
    check("every menu type is saved", {"PIE", "STACK", "PANEL", "DIALOG", "STICKY", "MODAL"} <= saved_types, str(saved_types))
    v2 = json.load(open(pie_file))
    v2["schema"] = 2
    for x in v2["data"]["pies"]:
        x.pop("key_event", None); x.pop("only_mode", None)
    json.dump(v2, open(pie_file, "w"))
    PM.load_from_disk()
    check("schema 2 files upgrade to the current schema", json.load(open(pie_file))["schema"] == PM.PIE_SCHEMA
          and all(x.key_event == "PRESS" and x.only_mode == "ANY" for x in p.pies))

    # ---- Python, Blender panel and label items, your own values, duplicate, two-key shortcuts
    bpy.ops.keyops.pie_add(menu_type="MENU")
    m = p.pies[-1]
    p.active_pie = len(p.pies) - 1
    while len(m.items) < 3:
        bpy.ops.keyops.menu_item_add()
    p.pie_slot = 0
    bpy.ops.keyops.slot_set_kind(kind="SCRIPT")
    check("an item can be made a Python script", m.items[0].kind == "SCRIPT" and m.items[0].script.startswith("import bpy"))
    m.items[0].script = "import bpy\nbpy.context.scene.frame_end = 77\n"
    texts_before = len(bpy.data.texts)
    res = bpy.ops.wm.keyops_run_script(pie=m.uid, slot=0)
    check("Python items run through the Text Editor", res == {'FINISHED'} and bpy.context.scene.frame_end == 77, str(res))
    check("the temporary text is removed after running", len(bpy.data.texts) == texts_before)
    m.items[0].script = "raise ValueError('boom')"
    res = bpy.ops.wm.keyops_run_script(pie=m.uid, slot=0)
    check("a failing script is reported instead of breaking the menu", res == {'CANCELLED'} and len(bpy.data.texts) == texts_before)
    PM.apply_action(m.items[1], "P:VIEW3D_PT_overlay")
    check("an item can open one of Blender's panels", m.items[1].kind == "POPOVER" and m.items[1].idname == "VIEW3D_PT_overlay")
    check("Blender's panels can be searched", any(i[0] == "P:VIEW3D_PT_overlay" for i in PM._blender_panel_items()))
    p.pie_slot = 2
    bpy.ops.keyops.slot_set_kind(kind="LABEL")
    check("an item can be a label", m.items[2].kind == "LABEL" and m.items[2].label)
    bpy.ops.keyops.value_add()
    vals = bpy.context.window_manager.keyops_values
    v = vals[-1]
    v.name, v.vtype = "Size", "FLOAT"
    v.float_value = 2.5
    data, prop = PM._resolve(bpy.context, "values:Size")
    check("your own values can be used as values:Name", getattr(data, prop) == 2.5)
    S.flush_now()
    vfile = S.section_path("values")
    check("your own values are saved to values.json",
          os.path.isfile(vfile) and json.load(open(vfile))["data"]["values"][0]["value"] == 2.5)
    vals.clear()
    S.load_section("values")
    check("your own values load back", vals.get("Size") is not None and vals["Size"].float_value == 2.5)
    n = len(p.pies)
    bpy.ops.keyops.pie_duplicate()
    dup = p.pies[-1]
    check("menus can be duplicated", len(p.pies) == n + 1 and dup.name == m.name + " Copy" and dup.uid != m.uid
          and [i.kind for i in dup.items] == [i.kind for i in m.items] and not dup.enabled)
    m.key, m.key_mod, m.enabled = "F", "BUTTON4MOUSE", True
    PM.sync_keymaps()
    kmis = [kmi for _k, kmi in addon_items() if kmi.idname == "wm.keyops_call_pie" and kmi.properties.pie == m.uid]
    check("a menu can need a second held key", kmis and all(k.key_modifier == "BUTTON4MOUSE" for k in kmis))
    check("the held key is shown", PM.key_text(m).endswith("+ F"), PM.key_text(m))
    m.key, m.key_mod = "BUTTON5MOUSE", "NONE"
    PM.sync_keymaps()
    check("side mouse buttons can open menus",
          any(kmi.type == "BUTTON5MOUSE" for _k, kmi in addon_items() if kmi.idname == "wm.keyops_call_pie"))
    m.enabled = False
    S.flush_now()
    saved = next(x for x in json.load(open(pie_file))["data"]["pies"] if x["uid"] == m.uid)
    check("new item fields are saved", saved["items"][0]["script"] and saved["items"][1]["kind"] == "POPOVER"
          and "key_mod" in saved)
    v3 = json.load(open(pie_file))
    v3["schema"] = 3
    for x in v3["data"]["pies"]:
        x.pop("key_mod", None)
        for it in x["items"]:
            it.pop("script", None)
    json.dump(v3, open(pie_file, "w"))
    PM.load_from_disk()
    check("schema 3 files upgrade to the current schema", json.load(open(pie_file))["schema"] == PM.PIE_SCHEMA
          and all(x.key_mod == "NONE" for x in p.pies))
    bpy.context.window_manager.keyops_menu_filter = "zzz-no-match"
    bpy.context.window_manager.keyops_menu_filter = ""

    # ---- disable: Blender's own keymap untouched, our items gone
    addon_utils.disable(MOD, default_set=True)
    after = user_keymap_snapshot()
    check("Blender's own keymap unchanged after enable/disable", before == after,
          f"{len(before)} vs {len(after)} items")
    check("no Key Ops items left in add-on keyconfig",
          not any(kmi.idname.startswith("keyops.") for _k, kmi in addon_items()))

    # ---- upgrade path: saved 0.2 prefs keep their shortcuts
    addon_utils.enable(MOD, default_set=True)
    F = sys.modules[MOD].features
    p = bpy.context.preferences.addons[MOD].preferences
    p.prefs_version = 0
    # a real 0.2 user has no pie_menus.json yet
    S2 = sys.modules[MOD + ".settings_store"]
    if os.path.isfile(S2.section_path("pie_menus")):
        os.remove(S2.section_path("pie_menus"))
    PM.loaded_from_disk = False
    with F.suspended():
        p.enable_auto_delete = True   # an explicitly saved 0.2 setting
    p["enable_cursor_pie"] = 0        # a 0.2 user who had switched the Cursor pie off
    p["enable_workspace_pie"] = 1     # ...and the Workspace pie on
    F.migrate()
    F.sync_all()
    PM = sys.modules[MOD].pie_menus
    check("upgrade keeps 0.2 pies on", PM.live_count() >= 3, str(PM.live_count()))
    states = {x.preset: x.enabled for x in p.pies}
    check("upgrade keeps a pie the user switched off in 0.2 (Cursor)", states["cursor"] is False, str(states))
    check("upgrade keeps a pie the user switched on in 0.2 (Workspace)", states["workspace"] is True)
    check("upgrade keeps 0.2 shortcuts on", any(kmi.type == "DEL" and kmi.active for _k, kmi in addon_items()))
    check("upgrade shows What's new", p.show_whats_new)
    addon_utils.disable(MOD, default_set=True)


try:
    run()
except Exception:
    traceback.print_exc()
    results.append(("no exceptions", False, "see traceback"))

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
