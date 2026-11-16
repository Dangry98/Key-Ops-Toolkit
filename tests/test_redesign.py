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


def addon_items():
    kc = bpy.context.window_manager.keyconfigs.addon
    return [(km.name, kmi) for km in kc.keymaps for kmi in km.keymap_items]


def active_addon_items():
    return [x for x in addon_items() if x[1].active]


def run():
    before = user_keymap_snapshot()
    addon_utils.enable(MOD, default_set=True)
    pkg = sys.modules[MOD]
    F = pkg.features
    PM = pkg.pie_menus
    p = bpy.context.preferences.addons[MOD].preferences

    # ---- fresh install (before the welcome screen)
    check("fresh install binds zero shortcuts", F.live_shortcut_count() == 0, str(F.live_shortcut_count()))
    check("fresh install: pies listed but none active", len(p.pies) == 8 and PM.live_count() == 0,
          f"{len(p.pies)} pies, {PM.live_count()} keys")
    feats, keys, repl = F.stats(p)
    check("fresh install still turns UI features on", feats >= 10, f"{feats} features")
    check("toolkit N-panel registered (original design)", hasattr(bpy.types, "KEYOPS_PT_new_toolkit_panel"))
    tabs = [i.identifier for i in p.bl_rna.properties["ui_tab"].enum_items]
    check("tabs: Features, Pie Menus, Shortcuts last", tabs == ["FEATURES", "PIES", "SHORTCUTS"], str(tabs))
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
    bpy.ops.keyops.icon_palette_tab(category="MODIFIERS")
    check("clicking a tab switches the palette category", bpy.context.window_manager.keyops_icon_category == "MODIFIERS")
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
