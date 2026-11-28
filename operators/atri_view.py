"""Reading the active attribute for the Attributes panel: the active element's value (and whether the selection
holds different values), the value field following a Geometry Nodes input that reads the attribute (its min,
max and units), and showing a color attribute with Blender's own Solid shading.

Everything is read from one snapshot of the mesh, made with numpy from the mesh data (the edit mesh is written
to it first), never per element in Python, so a million-face mesh stays usable. The snapshot is made in a timer,
not in a draw, and again a moment after the mesh changes (a depsgraph update), not on every redraw.
"""

import time

import bmesh
import bpy
import numpy as np

# attribute data type -> (foreach_get name, values per element)
READ = {'BOOLEAN': ("value", 1), 'INT': ("value", 1), 'INT8': ("value", 1), 'FLOAT': ("value", 1),
        'FLOAT_VECTOR': ("vector", 3), 'FLOAT2': ("vector", 2), 'INT32_2D': ("value", 2),
        'FLOAT_COLOR': ("color", 4), 'BYTE_COLOR': ("color", 4)}
MIXED_TOLERANCE = 1e-5

_snap = {"key": None, "data": None, "dirty": True, "pending": False}


# ---------------------------------------------------------------- the snapshot

def _settings_key(obj):
    attr = obj.data.attributes.active if obj and obj.type == 'MESH' else None
    return (obj.name, obj.data.name, attr.name if attr else "", attr.domain if attr else "",
            attr.data_type if attr else "") if obj and obj.type == 'MESH' else None


def _read(mesh, attr):
    name, size = READ[attr.data_type]
    n = len(attr.data)
    if attr.data_type == 'BOOLEAN':
        buf = np.zeros(n, dtype=bool)
    elif attr.data_type in ('INT', 'INT8', 'INT32_2D'):
        buf = np.zeros(n * size, dtype=np.int32)
    else:
        buf = np.zeros(n * size, dtype=np.float32)
    attr.data.foreach_get(name, buf)
    return buf.reshape(n, size) if size > 1 else buf


def _flags(seq, prop, n):
    buf = np.zeros(n, dtype=bool)
    if n:
        seq.foreach_get(prop, buf)
    return buf


def _active_index(obj, domain):
    """The active vertex / edge / face of the edit mesh (select history), or -1."""
    if obj.mode != 'EDIT' or domain not in ('POINT', 'EDGE', 'FACE'):
        return -1
    try:
        act = bmesh.from_edit_mesh(obj.data).select_history.active
    except (ReferenceError, ValueError):
        return -1
    want = {'POINT': bmesh.types.BMVert, 'EDGE': bmesh.types.BMEdge, 'FACE': bmesh.types.BMFace}[domain]
    return act.index if isinstance(act, want) else -1


def take_snapshot(obj, positions=True):
    """Values, selection and (for the viewport) element positions of the active attribute."""
    attr = obj.data.attributes.active
    if attr is None or attr.data_type not in READ or attr.domain not in ('POINT', 'EDGE', 'FACE', 'CORNER'):
        return None
    if obj.mode != 'EDIT':
        return _snapshot_of(obj, obj.data, attr.name, positions)
    # in Edit Mode the attributes live in the edit mesh, out of reach of fast reads: write it to the mesh and
    # read a temporary copy (no modifiers), about 0.15 s for a million vertices
    obj.update_from_editmode()
    _snap["own_update"] = time.monotonic()  # it sends a depsgraph update of its own: not a change to read again
    try:
        me = obj.to_mesh(preserve_all_data_layers=True)
    except RuntimeError:
        return None
    try:
        return _snapshot_of(obj, me, attr.name, positions)
    finally:
        obj.to_mesh_clear()


def _snapshot_of(obj, me, name, positions):
    attr = me.attributes.get(name)
    if attr is None:
        return None
    values = _read(me, attr)
    nv, ne, nf, nl = len(me.vertices), len(me.edges), len(me.polygons), len(me.loops)
    domain = attr.domain
    if domain == 'POINT':
        sel = _flags(me.vertices, "select", nv)
    elif domain == 'EDGE':
        sel = _flags(me.edges, "select", ne)
    elif domain == 'FACE':
        sel = _flags(me.polygons, "select", nf)
    else:  # corners of selected faces
        fsel = _flags(me.polygons, "select", nf)
        totals = np.zeros(nf, dtype=np.int32)
        me.polygons.foreach_get("loop_total", totals)
        sel = np.repeat(fsel, totals)
    data = {"values": values, "sel": sel, "domain": domain, "type": attr.data_type, "name": attr.name,
            "active": _active_index(obj, domain), "pos": None, "tris": None, "edges": None}
    if positions:
        co = np.zeros(nv * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(nv, 3)
        if domain == 'POINT':
            data["pos"] = co
        elif domain == 'EDGE':
            ev = np.zeros(ne * 2, dtype=np.int32)
            me.edges.foreach_get("vertices", ev)
            ev = ev.reshape(ne, 2)
            data["edges"] = co[ev]                    # (ne, 2, 3)
            data["pos"] = data["edges"].mean(axis=1)
        else:
            centres = np.zeros(nf * 3, dtype=np.float32)
            me.polygons.foreach_get("center", centres)
            centres = centres.reshape(nf, 3)
            if domain == 'FACE':
                data["pos"] = centres
                me.calc_loop_triangles()
                nt = len(me.loop_triangles)
                tv = np.zeros(nt * 3, dtype=np.int32)
                tp = np.zeros(nt, dtype=np.int32)
                me.loop_triangles.foreach_get("vertices", tv)
                me.loop_triangles.foreach_get("polygon_index", tp)
                data["tris"] = (co[tv.reshape(nt, 3)], tp)
            else:  # a corner sits a quarter of the way from its vertex to its face's centre
                lv = np.zeros(nl, dtype=np.int32)
                me.loops.foreach_get("vertex_index", lv)
                totals = np.zeros(nf, dtype=np.int32)
                me.polygons.foreach_get("loop_total", totals)
                data["pos"] = co[lv] * 0.75 + np.repeat(centres, totals, axis=0) * 0.25
        data["matrix"] = np.array(obj.matrix_world, dtype=np.float32)
    return data


def snapshot(context, want_positions=False):
    """The cached snapshot for the active object, or None while a new one is being made."""
    obj = context.active_object
    key = _settings_key(obj)
    data = _snap["data"]
    stale = key != _snap["key"] or _snap["dirty"] or (want_positions and data is not None and data["pos"] is None)
    if stale:
        _request(want_positions)
    return data if key == _snap["key"] else None


def _request(positions=False):
    _snap["want_pos"] = _snap.get("want_pos", False) or positions
    if not _snap["pending"]:
        _snap["pending"] = True
        bpy.app.timers.register(_refresh, first_interval=0.1)


def _refresh():
    _snap["pending"] = False
    context = bpy.context
    obj = context.active_object
    key = _settings_key(obj)
    positions = _snap.pop("want_pos", False)
    try:
        _snap["data"] = take_snapshot(obj, positions) if key is not None else None
    except (ReferenceError, RuntimeError, AttributeError, ValueError):
        _snap["data"] = None
    _snap["key"], _snap["dirty"] = key, False
    for win in context.window_manager.windows:
        for area in win.screen.areas:
            if area.type in ('PROPERTIES', 'VIEW_3D'):
                area.tag_redraw()
    return None


@bpy.app.handlers.persistent
def _on_depsgraph(scene, depsgraph):
    """The mesh changed (values, selection, shape): read it again shortly, once the change settles."""
    obj = bpy.context.active_object
    if obj is None or obj.type != 'MESH' or _snap["key"] is None:
        return
    own = _snap.pop("own_update", None)
    if own is not None and time.monotonic() - own < 0.5:
        return
    for u in depsgraph.updates:
        if getattr(u.id, "original", None) in (obj, obj.data):
            _snap["dirty"] = True
            return


def mark_dirty():
    _snap["dirty"] = True


# ---------------------------------------------------------------- active value and mixed values

def _fmt(v, data_type, unit=None):
    if data_type == 'BOOLEAN':
        return "True" if v else "False"
    if np.ndim(v):
        return "(" + ", ".join(_fmt(x, 'INT' if data_type in ('INT32_2D',) else 'FLOAT', unit) for x in v) + ")"
    if data_type in ('INT', 'INT8', 'INT32_2D'):
        return str(int(v))
    if unit:
        try:
            us = bpy.context.scene.unit_settings
            return bpy.utils.units.to_string(us.system if us.system != 'NONE' else 'METRIC', unit, float(v), precision=4)
        except (ValueError, TypeError, AttributeError, RuntimeError):
            pass
    return f"{float(v):.4g}"


def summary(data, unit=None):
    """(active text or None, selection text): the active element's value, and whether the selected elements
    hold one value or several."""
    if data is None:
        return None, "Reading..."
    vals, sel, dt = data["values"], data["sel"], data["type"]
    active = None
    if 0 <= data["active"] < len(vals):
        active = _fmt(vals[data["active"]], dt, unit)
    picked = vals[sel]
    n = len(picked)
    if n == 0:
        return active, "Nothing selected"
    flat = picked.reshape(n, -1).astype(np.float64)
    lo, hi = flat.min(axis=0), flat.max(axis=0)
    if np.all(hi - lo <= MIXED_TOLERANCE):
        return active, f"All {n} selected: {_fmt(picked[0], dt, unit)}"
    if dt == 'BOOLEAN':
        on = int(picked.sum())
        return active, f"Mixed: {on} True, {n - on} False"
    uniq = len(np.unique(flat, axis=0)) if n <= 200000 else None
    many = f"Mixed ({uniq} values)" if uniq is not None else "Mixed (many values)"
    if flat.shape[1] == 1:
        return active, f"{many}: {_fmt(lo[0], dt, unit)} - {_fmt(hi[0], dt, unit)}"
    return active, many


def active_value(data):
    """The active element's value, else the value the selection shares; None when neither exists."""
    if data is None:
        return None
    vals, sel = data["values"], data["sel"]
    if 0 <= data["active"] < len(vals):
        return vals[data["active"]]
    picked = vals[sel]
    if len(picked):
        flat = picked.reshape(len(picked), -1)
        if np.all(flat.max(axis=0) - flat.min(axis=0) <= MIXED_TOLERANCE):
            return picked[0]
    return None


# ---------------------------------------------------------------- the Geometry Nodes input that reads the attribute

def _input_reads(mod, ident, name):
    """True when the modifier's input reads the named attribute instead of a value."""
    if hasattr(mod, "properties") and not hasattr(mod, "keys"):
        sock = getattr(mod.properties.inputs, ident, None)
        return sock is not None and getattr(sock, "type", "") == "ATTRIBUTE" and sock.attribute_name == name
    try:
        return bool(mod.get(ident + "_use_attribute")) and mod.get(ident + "_attribute_name") == name
    except (TypeError, AttributeError):
        sock = getattr(getattr(getattr(mod, "properties", None), "inputs", None), ident, None)
        return sock is not None and getattr(sock, "type", "") == "ATTRIBUTE" and sock.attribute_name == name


def linked_socket(obj, name):
    """(modifier, interface socket) of a Geometry Nodes input on obj that reads the attribute, or (None, None)."""
    for mod in obj.modifiers:
        group = getattr(mod, "node_group", None) if mod.type == 'NODES' else None
        if group is None:
            continue
        for it in group.interface.items_tree:
            if it.item_type == 'SOCKET' and it.in_out == 'INPUT' and hasattr(it, "min_value") \
                    and _input_reads(mod, it.identifier, name):
                return mod, it
    return None, None


FLOAT_UNITS = {'DISTANCE': 'LENGTH', 'ANGLE': 'ROTATION', 'TIME': 'TIME', 'TIME_ABSOLUTE': 'TIME',
               'WAVELENGTH': 'WAVELENGTH', 'TEMPERATURE': 'TEMPERATURE'}


def socket_spec(sock):
    """min, max, subtype and display unit for the value field, from a Geometry Nodes input."""
    if sock is None:
        return None
    sub = getattr(sock, "subtype", 'NONE') or 'NONE'
    lo, hi = getattr(sock, "min_value", None), getattr(sock, "max_value", None)
    return {"min": lo, "max": hi, "subtype": sub, "unit": FLOAT_UNITS.get(sub),
            "socket": sock.socket_type, "name": sock.name}


def kind_of(data_type):
    from .atri_op import LAYERS
    return LAYERS.get(data_type, (None, None))[1]


# ---------------------------------------------------------------- viewport preview

def show_in_viewport(context, attr):
    """Blender's own display of a color attribute: Solid shading colored by the active color attribute."""
    obj = context.active_object
    if obj is None or attr is None or attr.data_type not in ('FLOAT_COLOR', 'BYTE_COLOR') \
            or attr.domain not in ('POINT', 'CORNER'):
        return False
    me = obj.data
    idx = next((n for n, a in enumerate(me.color_attributes) if a.name == attr.name), None)
    if idx is None:
        return False
    me.color_attributes.active_color_index = idx
    for area in context.screen.areas if context.screen else ():
        if area.type == 'VIEW_3D':
            shading = area.spaces.active.shading
            if shading.type in ('WIREFRAME', 'SOLID'):
                shading.type = 'SOLID'
                shading.color_type = 'VERTEX'
            area.tag_redraw()
    return True


def register():
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)


def unregister():
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    if bpy.app.timers.is_registered(_refresh):
        bpy.app.timers.unregister(_refresh)
    _snap.update(key=None, data=None, dirty=True, pending=False)
