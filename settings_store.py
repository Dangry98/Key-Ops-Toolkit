"""Key Ops settings files.

Settings that don't fit Blender's add-on preferences (like the pie menus) are kept as
JSON in the add-on's own user folder, ``bpy.utils.extension_path_user(__package__)``,
which is the only place the extensions platform allows an add-on to write.

Each feature registers a *section*: a name plus two functions that turn its settings
into plain data and back. The store handles files, versioning, delayed saving, and
exporting/importing every section as one file. Adding a new feature's settings is one
``register_section`` call.
"""

import json
import os

import bpy

from .utils.pref_utils import get_addon_name, get_keyops_prefs

FORMAT = "keyops-settings"
FORMAT_VERSION = 1

# name -> {"save": prefs -> dict, "load": (prefs, dict, merge) -> None, "file": bool}
_sections = {}
_pending = set()


def register_section(name, save, load, own_file=True):
    """own_file: keep this section in <name>.json and save it whenever it changes.
    Sections without their own file still take part in export/import."""
    _sections[name] = {"save": save, "load": load, "file": own_file}


def sections():
    return list(_sections)


# ---------------------------------------------------------------- files

def user_dir():
    return bpy.utils.extension_path_user(get_addon_name(), create=True)


def section_path(name):
    return os.path.join(user_dir(), f"{name}.json")


def has_file(name):
    try:
        return os.path.isfile(section_path(name))
    except Exception:
        return False


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)  # never leaves a half-written file


def _wrap(name, data):
    return {"format": FORMAT, "version": FORMAT_VERSION, "section": name, "data": data}


def save_section(name):
    sec = _sections.get(name)
    prefs = get_keyops_prefs()
    if sec is None or not sec["file"] or not hasattr(prefs, "bl_rna"):
        return False
    _write_json(section_path(name), _wrap(name, sec["save"](prefs)))
    return True


def load_section(name):
    """Load <name>.json into the preferences. Returns False when there is no usable file."""
    sec = _sections.get(name)
    if sec is None or not has_file(name):
        return False
    try:
        with open(section_path(name), encoding="utf-8") as f:
            payload = json.load(f)
        if payload.get("format") != FORMAT:
            return False
        sec["load"](get_keyops_prefs(), payload.get("data", {}), False)
        return True
    except (OSError, ValueError) as e:
        print(f"Key Ops: could not read {name}.json: {e}")
        return False


def save_soon(name):
    """Save a section a moment after the last change, so dragging a value doesn't write every frame."""
    if name not in _sections or bpy.app.background:
        if name in _sections and bpy.app.background:
            save_section(name)
        return
    if not _pending:
        bpy.app.timers.register(_flush, first_interval=0.5)
    _pending.add(name)


def _flush():
    for name in list(_pending):
        try:
            save_section(name)
        except OSError as e:
            print(f"Key Ops: could not save {name}.json: {e}")
    _pending.clear()
    return None


def flush_now():
    if bpy.app.timers.is_registered(_flush):
        bpy.app.timers.unregister(_flush)
    _flush()


# ---------------------------------------------------------------- export / import

def export_file(path, names=None):
    prefs = get_keyops_prefs()
    names = names or sections()
    bundle = {"format": FORMAT, "version": FORMAT_VERSION, "sections": {}}
    for name in names:
        bundle["sections"][name] = _sections[name]["save"](prefs)
    _write_json(path, bundle)
    return names


def import_file(path, merge=False, names=None):
    """Apply the sections found in an exported file. Returns the names that were imported."""
    with open(path, encoding="utf-8") as f:
        bundle = json.load(f)
    if bundle.get("format") != FORMAT:
        raise ValueError("This is not a Key Ops settings file")
    if bundle.get("version", 0) > FORMAT_VERSION:
        raise ValueError("This file was made by a newer Key Ops. Update Key Ops to import it")
    prefs = get_keyops_prefs()
    done = []
    for name, data in bundle.get("sections", {}).items():
        if name in _sections and (names is None or name in names):
            _sections[name]["load"](prefs, data, merge)
            if _sections[name]["file"]:
                save_section(name)
            done.append(name)
    return done


# ---------------------------------------------------------------- the "preferences" section
# Every simple add-on preference, found automatically, so new features need no extra code.

_SKIP_PREFIXES = ("ui_", "pie_show", "pie_customize", "pie_slot", "active_pie")
_SKIP = {"rna_type", "bl_idname", "prefs_version", "welcome_version", "last_seen_version",
         "show_whats_new", "pies", "pies_installed", "style_modified"}


def _simple_props(prefs):
    for name, prop in prefs.bl_rna.properties.items():
        if name in _SKIP or name.startswith(_SKIP_PREFIXES):
            continue
        if prop.type in {'BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM'} and not prop.is_readonly:
            yield name, prop


def _save_preferences(prefs):
    out = {}
    for name, prop in _simple_props(prefs):
        value = getattr(prefs, name)
        if prop.type == 'ENUM' and prop.is_enum_flag:
            value = sorted(value)
        elif hasattr(value, "__len__") and not isinstance(value, str):
            value = list(value)
        out[name] = value
    return out


def _load_preferences(prefs, data, merge):
    from . import features
    known = dict(_simple_props(prefs))
    with features.suspended():
        for name, value in data.items():
            prop = known.get(name)
            if prop is None:
                continue  # setting from another version: ignore
            try:
                if prop.type == 'ENUM' and prop.is_enum_flag:
                    value = set(value)
                setattr(prefs, name, value)
            except (TypeError, ValueError, AttributeError):
                pass
    features.sync_all()


register_section("preferences", _save_preferences, _load_preferences, own_file=False)
