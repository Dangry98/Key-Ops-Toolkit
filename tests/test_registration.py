"""Headless checks for plain registration: every module registers once, switches only toggle.

Run with the add-on installed as an extension in the user_default repository:
    blender -b --factory-startup --python tests/test_registration.py
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


def keyops_classes():
    names = set()
    for base in (bpy.types.Operator, bpy.types.Panel, bpy.types.Menu, bpy.types.GizmoGroup):
        for cls in base.__subclasses__():
            if cls.__module__.startswith(MOD) and getattr(cls, "is_registered", False):
                names.add(cls.__name__)
    return names


def keyops_handlers():
    found = []
    for name in ("depsgraph_update_post", "depsgraph_update_pre", "load_post", "undo_post", "redo_post"):
        for h in getattr(bpy.app.handlers, name):
            if getattr(h, "__module__", "").startswith(MOD):
                found.append(f"{name}:{h.__name__}")
    return found


def run():
    addon_utils.enable(MOD, default_set=True)
    check("enables", MOD in bpy.context.preferences.addons)
    pkg = sys.modules[MOD]
    F = pkg.features
    p = bpy.context.preferences.addons[MOD].preferences

    init_src = open(pkg.__file__, encoding="utf-8").read()
    check("__init__ has no string dispatch", "getattr(" not in init_src and "importlib" not in init_src)
    feat_src = open(F.__file__, encoding="utf-8").read()
    check("features.py has no module loading", "_module(" not in feat_src and "import_module" not in feat_src)

    n_classes = len(keyops_classes())
    check("classes registered at enable", n_classes > 50, str(n_classes))

    # Industry turns everything on: every feature's set_enabled ran
    F.apply_style("INDUSTRY")
    live_industry = F.live_shortcut_count()
    check("industry has live shortcuts", live_industry > 20, str(live_industry))
    switched = set(F._switched_on)
    expected = {fid for fid in F.SET_ENABLED if F.is_enabled(fid, p)}
    check("set_enabled ran for every enabled feature", switched == expected, f"{sorted(switched ^ expected)}")

    # Each switch off and on again: no errors, classes stay registered, shortcuts follow
    for f in F.FEATURES:
        if not f.available():
            continue
        name = f"enable_{f.id}"
        was = getattr(p, name)
        setattr(p, name, not was)
        setattr(p, name, was)
    check("toggling every feature keeps the classes", len(keyops_classes()) == n_classes)
    check("toggling every feature restores the shortcuts", F.live_shortcut_count() == live_industry,
          f"{F.live_shortcut_count()} vs {live_industry}")

    p.enable_fast_merge = False
    check("switching a feature off turns its keys off", not any(kmi.active for _km, kmi in F.tracked_items("fast_merge")))
    p.enable_fast_merge = True
    check("switching it back on turns them on", all(kmi.active for _km, kmi in F.tracked_items("fast_merge")))

    if hasattr(bpy.types, "WorkSpaceTool"):
        tool = sys.modules[MOD + ".tools.merge_tool"].WorkSpaceMergeTool
        p.enable_merge_tool = False
        check("merge tool leaves the toolbar when off", not hasattr(tool, "_bl_tool"))
        p.enable_merge_tool = True
        check("merge tool comes back when on", hasattr(tool, "_bl_tool"))

    p.enable_polycount_list = False
    check("polycount handler removed when off", not any("poly_count" in h for h in keyops_handlers()), str(keyops_handlers()))
    p.enable_polycount_list = True
    check("polycount handler back when on", any("poly_count" in h for h in keyops_handlers()), str(keyops_handlers()))

    # ---- Essentials: tools, panels and menus work, no shortcuts
    F.apply_style("ESSENTIALS")
    check("essentials: no live shortcuts", F.live_shortcut_count() == 0, str(F.live_shortcut_count()))
    tools = [sys.modules[MOD + ".tools." + m] for m in ("merge_tool", "cutter_tool", "fast_loop_cut")]
    tool_classes = [t.WorkSpaceMergeTool for t in tools[:1]] + [tools[1].WorkSpaceCutter, tools[2].WorkSpaceFastLoopCut]
    check("essentials: toolbar tools are in the toolbar", all(hasattr(c, "_bl_tool") for c in tool_classes))
    panel = getattr(bpy.types, "KEYOPS_PT_new_toolkit_panel", None)
    check("essentials: Toolkit panel registered", panel is not None)
    check("essentials: Toolkit panel shows", panel is not None and bool(panel.poll(bpy.context)))

    # ---- no preferences yet (enabled from the command line): Essentials still on, no shortcuts
    PU = sys.modules[MOD + ".utils.pref_utils"]
    real_get, real_prefs = PU.get_keyops_prefs, F.prefs
    PU.get_keyops_prefs = lambda: None
    F.prefs = lambda: None
    try:
        F.apply_all()
        check("no prefs: tools stay in the toolbar", all(hasattr(c, "_bl_tool") for c in tool_classes))
        check("no prefs: Toolkit panel shows", bool(panel.poll(bpy.context)))
        check("no prefs: feature_on treats switches as on", PU.feature_on("toolkit_panel") is True)
        check("no prefs: no shortcuts", F.live_shortcut_count() == 0, str(F.live_shortcut_count()))
    finally:
        PU.get_keyops_prefs, F.prefs = real_get, real_prefs
        F.apply_all()
    check("prefs back: switches read from preferences again", PU.feature_on("auto_delete") == p.enable_auto_delete)

    for attempt in (1, 2):
        addon_utils.disable(MOD, default_set=True)
        check(f"disable {attempt}: no classes left", not keyops_classes(), str(sorted(keyops_classes())[:5]))
        check(f"disable {attempt}: no handlers left", not keyops_handlers(), str(keyops_handlers()))
        addon_utils.enable(MOD, default_set=True)
        check(f"re-enable {attempt}", MOD in bpy.context.preferences.addons)


try:
    run()
except Exception:
    traceback.print_exc()
    results.append(("no exception", False, ""))

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
