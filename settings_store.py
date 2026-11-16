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
import shutil
import time

import bpy

from .utils.pref_utils import get_addon_name, get_keyops_prefs

FORMAT = "keyops-settings"
FORMAT_VERSION = 2  # layout of the file wrapper itself (sections carry their own schema numbers)

# name -> {"save", "load", "file", "schema", "migrations"}
_sections = {}
_pending = set()
_read_only = {}  # name -> reason; set when a file came from a newer Key Ops, so it is never overwritten
_notices = []    # short messages for the preferences (backups made, files set aside)


def register_section(name, save, load, own_file=True, schema=1, migrations=None):
    """Register a settings section.

    save(prefs) -> dict and load(prefs, data, merge) turn the settings into plain data and back.
    schema is the current version of this section's data. migrations maps an old schema number
    to a function that upgrades data from that version to the next one, so files from any older
    version are brought up to date step by step.
    own_file: keep the section in <name>.json and save it whenever it changes."""
    _sections[name] = {"save": save, "load": load, "file": own_file, "schema": schema,
                       "migrations": dict(migrations or {})}


def sections():
    return list(_sections)


def notices():
    return list(_notices)


def read_only(name):
    return _read_only.get(name)


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
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)  # atomic: the old file stays intact until the new one is complete


def _addon_version():
    try:
        from .ui.branding import version_text
        return version_text()
    except Exception:
        return ""


def _wrap(name, data):
    sec = _sections[name]
    return {"format": FORMAT, "version": FORMAT_VERSION, "section": name, "schema": sec["schema"],
            "written_by": _addon_version(), "data": data}


def _set_aside(path, why):
    """Keep a file we can't use under a new name instead of deleting or overwriting it."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base, ext = os.path.splitext(path)
    dest = f"{base}.{why}-{stamp}{ext}"
    try:
        shutil.copy2(path, dest)
        _notices.append(f"{os.path.basename(path)}: kept a copy as {os.path.basename(dest)}")
    except OSError:
        pass
    return dest


def migrate(name, data, schema):
    """Upgrade data of a section from schema to the current schema."""
    sec = _sections[name]
    while schema < sec["schema"]:
        step = sec["migrations"].get(schema)
        if step is not None:
            data = step(data)
        schema += 1
    return data


def save_section(name):
    sec = _sections.get(name)
    prefs = get_keyops_prefs()
    if sec is None or not sec["file"] or not hasattr(prefs, "bl_rna") or name in _read_only:
        return False
    _write_json(section_path(name), _wrap(name, sec["save"](prefs)))
    return True


def load_section(name):
    """Load <name>.json into the preferences. Returns False when there is no usable file.

    - unreadable JSON: the file is set aside and defaults are used
    - older schema: a backup is kept, the data is migrated, then saved in the new schema
    - newer schema (from a newer Key Ops): loaded as far as understood, never overwritten"""
    sec = _sections.get(name)
    if sec is None or not has_file(name):
        return False
    path = section_path(name)
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict) or payload.get("format") != FORMAT:
            raise ValueError("not a Key Ops settings file")
    except (OSError, ValueError) as e:
        print(f"Key Ops: {name}.json could not be read ({e}); using defaults")
        _set_aside(path, "unreadable")
        return False

    schema = int(payload.get("schema", 1))
    data = payload.get("data", {})
    if schema > sec["schema"]:
        _read_only[name] = f"{name}.json was saved by a newer Key Ops ({payload.get('written_by', '?')}). " \
                           "Changes won't be saved to it until you update."
    elif schema < sec["schema"]:
        _set_aside(path, f"backup-schema{schema}")
        data = migrate(name, data, schema)
    try:
        sec["load"](get_keyops_prefs(), data, False)
    except Exception as e:  # never let a bad file stop the add-on from starting
        print(f"Key Ops: {name}.json has unexpected content ({e}); using defaults")
        _set_aside(path, "unreadable")
        return False
    if schema < sec["schema"]:
        save_section(name)
    return True


def save_soon(name):
    """Save a section a moment after the last change, so dragging a value doesn't write every frame."""
    if name not in _sections:
        return
    if bpy.app.background:
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

def export_file(path, names=None, options=None):
    """Write the chosen sections to one file. options[name] is passed to the section's save
    as prefs-independent filters (e.g. which pies to include)."""
    prefs = get_keyops_prefs()
    names = names or sections()
    bundle = {"format": FORMAT, "version": FORMAT_VERSION, "written_by": _addon_version(), "sections": {}}
    for name in names:
        sec = _sections[name]
        data = sec["save"](prefs)
        flt = (options or {}).get(name)
        if flt is not None:
            data = flt(data)
        bundle["sections"][name] = {"schema": sec["schema"], "data": data}
    _write_json(path, bundle)
    return names


def import_file(path, merge=False, names=None):
    """Apply the sections found in an exported file (any older format). Returns the imported names."""
    with open(path, encoding="utf-8") as f:
        bundle = json.load(f)
    if not isinstance(bundle, dict) or bundle.get("format") != FORMAT:
        raise ValueError("This is not a Key Ops settings file")
    if bundle.get("version", 1) > FORMAT_VERSION:
        raise ValueError("This file was made by a newer Key Ops. Update Key Ops to import it")
    prefs = get_keyops_prefs()
    done = []
    for name, entry in bundle.get("sections", {}).items():
        if name not in _sections or (names is not None and name not in names):
            continue
        sec = _sections[name]
        if bundle.get("version", 1) < 2:  # version 1 files stored the data directly
            entry = {"schema": 1, "data": entry}
        schema = int(entry.get("schema", 1))
        if schema > sec["schema"]:
            raise ValueError(f"The {name.replace('_', ' ')} in this file need a newer Key Ops")
        data = migrate(name, entry.get("data", {}), schema)
        sec["load"](prefs, data, merge)
        if sec["file"]:
            save_section(name)
        done.append(name)
    return done


# ---------------------------------------------------------------- the "preferences" section
# Every simple add-on preference, found automatically, so new features need no extra code.

_SKIP_PREFIXES = ("ui_", "pie_show", "pie_customize", "pie_slot", "active_pie")  # UI state, not settings
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
