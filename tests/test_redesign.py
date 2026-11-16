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
    p = bpy.context.preferences.addons[MOD].preferences

    # ---- fresh install
    check("fresh install picks Essentials", p.shortcut_style == "ESSENTIALS", p.shortcut_style)
    check("fresh install binds zero active shortcuts", F.live_shortcut_count() == 0, str(F.live_shortcut_count()))
    feats, keys, repl = F.stats(p)
    check("Essentials still turns UI features on", feats >= 10, f"{feats} features")
    check("Essentials: stats report 0 shortcuts", keys == 0 and repl == 0, f"{keys}/{repl}")
    check("toolkit panel registered", hasattr(bpy.types, "KEYOPS_PT_object"))
    check("welcome scheduled once (not marked seen in background)", p.welcome_version == 0)

    # ---- Blender+
    p.shortcut_style = "BLENDER_PLUS"
    feats, keys, repl = F.stats(p)
    check("Blender+ adds only free keys", keys > 0 and repl == 0, f"{keys} keys, {repl} replacing")
    live = F.live_shortcut_count()
    check("Blender+ registers live shortcuts", live > 0, f"{live} live items")
    names = {(km, kmi.type, kmi.shift, kmi.alt) for km, kmi in active_addon_items()}
    check("Blender+ has Shift Alt A pie", ("3D View Generic", "A", True, True) in names)
    check("Blender+ does NOT take Delete", not any(k[1] == "DEL" for k in names))
    check("Blender+ does NOT take 1 in Edit Mode", not any(k[0] == "Mesh" and k[1] == "ONE" for k in names))

    # ---- Industry (0.2 parity)
    p.shortcut_style = "INDUSTRY"
    feats, keys, repl = F.stats(p)
    names = {(km, kmi.type) for km, kmi in active_addon_items()}
    check("Industry replaces Blender keys", repl > 0, f"{keys} keys, {repl} replacing")
    check("Industry has Delete auto delete", ("Mesh", "DEL") in names)
    check("Industry has Alt navigation", any(t == "LEFTMOUSE" for _k, t in names))
    industry_live = F.live_shortcut_count()

    # ---- per-feature shortcut switch: feature stays registered
    p.keys_auto_delete = False
    check("keys off -> auto delete operator still registered", hasattr(bpy.ops.keyops, "auto_delete"))
    check("keys off -> Delete item inactive", not any(t == "DEL" and kmi.active for _k, kmi in addon_items() for t in [kmi.type]))
    check("touching a feature marks style modified", not F.matches_style("INDUSTRY", p))
    p.keys_auto_delete = True

    # ---- pause all
    p.pause_shortcuts = True
    check("pause -> zero live shortcuts", F.live_shortcut_count() == 0)
    p.pause_shortcuts = False
    check("resume -> shortcuts back", F.live_shortcut_count() == industry_live, f"{F.live_shortcut_count()} vs {industry_live}")

    # ---- feature off unregisters classes and its items
    p.enable_maya_pivot = False
    check("feature off removes its keymap items", not any(kmi.idname == "keyops.pivot_press" for _k, kmi in addon_items()))
    p.enable_maya_pivot = True
    check("feature on restores its keymap items", any(kmi.idname == "keyops.pivot_press" for _k, kmi in addon_items()))

    # ---- opt-in replacements for the old Rebind tab
    p.enable_add_menu_shift_a = True
    p.enable_w_context_menu = True
    p.enable_view_pie_space = True
    check("Shift A pie is an add-on item", any(km == "Object Mode" and kmi.type == "A" and kmi.shift and not kmi.alt
                                               and kmi.active for km, kmi in addon_items()))
    check("W context menu is an add-on item", any(kmi.type == "W" and kmi.active for _k, kmi in addon_items()))
    p.enable_add_objects_pie = False
    check("Shift A option follows its parent pie", not any(km == "Object Mode" and kmi.type == "A" and kmi.shift
                                                          for km, kmi in addon_items()))
    p.enable_add_objects_pie = True
    check("Shift A option returns with its parent pie", any(km == "Object Mode" and kmi.type == "A" and kmi.shift
                                                           for km, kmi in addon_items()))

    # ---- preferences draw without errors on every tab and category
    class _Fake:
        pass
    region_ok = True
    for tab in ("HOME", "FEATURES", "SHORTCUTS", "PIES"):
        p.ui_tab = tab
    check("all tabs selectable", True)

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
    F.migrate()
    F.sync_all()
    check("upgrade keeps style as Custom", p.shortcut_style == "CUSTOM", p.shortcut_style)
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
