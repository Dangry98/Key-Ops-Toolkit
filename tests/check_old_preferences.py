"""Check that preferences saved by Key Ops 0.2 load correctly in this version.

1. With the 0.2 add-on installed, save preferences with these values (see EXPECTED).
2. Install this version in the same place and start Blender normally (not --factory-startup),
   with this script:  blender --python tests/check_old_preferences.py
"""

import sys

import bpy

MOD = "bl_ext.user_default.Key_Ops_Toolkit"

EXPECTED = dict(
    enable_auto_delete=False, enable_maya_navigation=False, enable_legacy_shortcuts=False,
    enable_polycount_list=False, maya_pivot_behavior='TOGGLE', add_object_pie_relative_scale=12.0,
    fast_merge_soft_limit='no_limit', material_list_type='PREVIEW_ICONS', toggle_retopology_edge_width=4,
    experimental=True, auto_delete_dissolv_edge=True,
)
PIES = {"cursor": False, "workspace": True, "add_objects": True, "add_modifier": True, "flatten": True}

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def run():
    if MOD not in bpy.context.preferences.addons:
        check("add-on enabled from the saved preferences", False)
        return finish()
    p = bpy.context.preferences.addons[MOD].preferences
    F = sys.modules[MOD + ".features"]
    PM = sys.modules[MOD + ".pie_menus"]
    W = sys.modules[MOD + ".ui.welcome"]
    for name, value in EXPECTED.items():
        got = getattr(p, name)
        ok = abs(got - value) < 1e-6 if isinstance(value, float) else got == value
        check(f"setting kept: {name}", ok, f"{got!r}")
    check("treated as an upgrade, not a fresh install", p.prefs_version == F.PREFS_VERSION and p.show_whats_new)
    check("What's New is shown instead of the welcome", W.first_screen(p) == 'WHATS_NEW')
    states = {x.preset: x.enabled for x in p.pies}
    for preset, on in PIES.items():
        check(f"pie kept {'on' if on else 'off'}: {preset}", states.get(preset) == on, str(states.get(preset)))
    on_with_keys = [f.id for f in F.FEATURES if getattr(p, f"enable_{f.id}") and f.keys]
    check("features that were on keep their shortcuts", all(getattr(p, f"keys_{fid}") for fid in on_with_keys))
    check("features that were off stay off", not p.enable_auto_delete and "auto_delete" not in F._registered)
    kc = bpy.context.window_manager.keyconfigs.addon
    check("Delete key not taken (Auto Delete was off)",
          not any(kmi.idname == "keyops.auto_delete" and kmi.active for km in kc.keymaps for kmi in km.keymap_items))
    check("D pivot shortcut still there (Maya Pivot was on)",
          any(kmi.idname == "keyops.pivot_press" and kmi.active for km in kc.keymaps for kmi in km.keymap_items))
    finish()


def finish():
    print(f"\n{sum(results)}/{len(results)} checks passed")
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(run, first_interval=2.0)
