"""Regression snapshot: run in the ORIGINAL add-on and in this version, then diff the two JSON files.

    blender --factory-startup --python tests/compare_with_original.py -- old|new out.json

Enables every feature (and in the new version every shortcut and pie), then records:
registered classes, operators, add-on keymap items, extra RNA properties, preference
properties with defaults, and the result of running every Key Ops operator on a test mesh.
"""

import json
import sys
import traceback

import addon_utils
import bpy

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
mode, out_path = sys.argv[sys.argv.index("--") + 1:][:2]


def ops_set():
    return {f"{m}.{o}" for m in dir(bpy.ops) for o in dir(getattr(bpy.ops, m))}


def props_of(t):
    return set(t.bl_rna.properties.keys())


def snapshot():
    before_types = set(dir(bpy.types))
    before_ops = ops_set()
    before_props = {t: props_of(getattr(bpy.types, t)) for t in ("Scene", "Object", "WindowManager", "Mesh", "Material")}

    addon_utils.enable(MOD, default_set=True)
    p = bpy.context.preferences.addons[MOD].preferences
    p.experimental = True
    if mode == "new":
        F = sys.modules[MOD].features
        PM = sys.modules[MOD].pie_menus
        F.apply_style("INDUSTRY")
        for f in F.FEATURES:
            if f.available():
                setattr(p, f"enable_{f.id}", True)
                if f.keys:
                    setattr(p, f"keys_{f.id}", True)
        for pie in p.pies:
            pie.enabled = True
        PM.sync_keymaps()
    else:
        for name in p.bl_rna.properties.keys():
            if name.startswith("enable_") and name != "enable_legacy_collection_shortcuts" and not getattr(p, name):
                try:
                    setattr(p, name, True)
                except Exception:
                    traceback.print_exc()

    kc = bpy.context.window_manager.keyconfigs.addon
    kmis = []
    for km in (kc.keymaps if kc else []):
        for kmi in km.keymap_items:
            if not kmi.active:
                continue
            props = {}
            for n in ("name", "type", "mesh_type", "pie"):
                if hasattr(kmi.properties, n):
                    try:
                        props[n] = str(getattr(kmi.properties, n))
                    except Exception:
                        pass
            kmis.append([km.name, kmi.idname, kmi.type, kmi.value, kmi.ctrl, kmi.shift, kmi.alt, props])

    prefs_props = {}
    for name, prop in p.bl_rna.properties.items():
        if name == "rna_type":
            continue
        d = getattr(prop, "default", None)
        if getattr(prop, "type", "") == "ENUM":
            d = prop.default
        prefs_props[name] = repr(d) if d is not None else None

    return {
        "types": sorted(set(dir(bpy.types)) - before_types),
        "ops": sorted(ops_set() - before_ops),
        "props": {t: sorted(props_of(getattr(bpy.types, t)) - before_props[t]) for t in before_props},
        "keymap": kmis,
        "prefs": prefs_props,
    }


SKIP = {  # open dialogs, start modal UI, touch files or block in background
    "keyops.quick_export", "keyops.cad_decimate", "keyops.export_cad_decimate", "keyops.import_cad_decimate",
    "keyops.import_all_cad_decimate", "keyops.welcome", "keyops.pie_set_key", "keyops.pie_icon_picker",
    "keyops.pie_slot_search", "keyops.shortcut_cheatsheet", "wm.keyops_call_pie", "keyops.auto_lod",
}


def run_ops(op_names):
    results = {}
    for name in sorted(op_names):
        if not name.startswith(("keyops.", "object.", "mesh.", "uv.")) or name in SKIP:
            continue
        for mode_name in ("OBJECT", "EDIT"):
            try:
                if bpy.context.object and bpy.context.object.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
                for ob in list(bpy.data.objects):
                    bpy.data.objects.remove(ob)
                bpy.ops.mesh.primitive_cube_add()
            except Exception as e:
                results[f"{name}@{mode_name}"] = "setup-failed"
                continue
            cube = bpy.context.object
            if mode_name == "EDIT":
                bpy.ops.object.mode_set(mode='EDIT')
            m, o = name.split(".", 1)
            op = getattr(getattr(bpy.ops, m), o)
            try:
                if not op.poll():
                    r = "poll-false"
                else:
                    r = ",".join(sorted(op('EXEC_DEFAULT')))
            except Exception as e:
                r = "error:" + type(e).__name__ + ":" + str(e).splitlines()[0][:80]
            results[f"{name}@{mode_name}"] = r
    return results


try:
    snap = snapshot()
    if bpy.app.background:  # operator runs are done headless so no modal tool can take over the window
        snap = {"runs": run_ops(snap["ops"]), "ops": snap["ops"]}
except Exception:
    traceback.print_exc()
    snap = {"error": traceback.format_exc()}
json.dump(snap, open(out_path, "w"), indent=1)
print("WROTE", out_path)
bpy.ops.wm.quit_blender()
