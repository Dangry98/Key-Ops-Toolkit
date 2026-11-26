"""Attribute operations in the mesh Attributes panel (Edit Mode): assign, remove, select and deselect by the
active attribute, and new vertex / edge / face groups.

Assign, Remove and Select on booleans use Blender's own attribute operators: they are written in C and were
measured about 4x faster than a Python bmesh loop on a million faces (36 ms against 137 ms). Deselect and
selecting by value (which Blender has no operator for) work on the edit mesh directly (bmesh layers), as do
types an older Blender's operator can't set. Works on every mesh in Edit Mode that has the attribute, for
boolean, integer, float, vector, 2D vector and both color types, on points, edges, faces and face corners.
"""

import bmesh
import bpy.types

from ..utils.pref_utils import feature_on

# attribute data type -> (bmesh layer collection name, kind of value)
LAYERS = {
    'BOOLEAN': ("bool", "BOOL"),
    'INT': ("int", "INT"),
    'FLOAT': ("float", "FLOAT"),
    'FLOAT_VECTOR': ("float_vector", "VECTOR"),
    'FLOAT_COLOR': ("float_color", "COLOR"),
    'BYTE_COLOR': ("color", "COLOR"),
    'FLOAT2': ("float_vector", "VECTOR2"),  # not exposed by every Blender's bmesh: then reported as unsupported
}
DOMAINS = {'POINT': "verts", 'EDGE': "edges", 'FACE': "faces", 'CORNER': "loops"}
SELECT_MODES = {'POINT': (True, False, False), 'EDGE': (False, True, False), 'FACE': (False, False, True)}


def _edit_objects(context):
    """Meshes in Edit Mode, one per mesh (also right after a mode switch, when the context list is stale)."""
    objs = [o for o in (context.objects_in_mode_unique_data or ()) if o.type == 'MESH']
    if not objs:
        seen = set()
        for o in context.view_layer.objects:
            if o.type == 'MESH' and o.mode == 'EDIT' and o.data not in seen:
                seen.add(o.data)
                objs.append(o)
    return objs


def _active_attribute(context):
    obj = context.active_object
    return obj.data.attributes.active if obj and obj.type == 'MESH' else None


def _layer(bm, attr):
    """The bmesh layer for a mesh attribute, or None when this Blender's bmesh doesn't expose it."""
    kind = LAYERS.get(attr.data_type)
    domain = DOMAINS.get(attr.domain)
    if kind is None or domain is None:
        return None, None
    seq = bm.loops if domain == "loops" else getattr(bm, domain)
    layers = getattr(seq.layers, kind[0], None)
    if attr.data_type == 'FLOAT2' and domain == "loops":
        layers = getattr(seq.layers, "uv", layers)
    layer = layers.get(attr.name) if layers is not None else None
    return layer, kind[1]


def _elements(bm, attr, selected):
    """Elements of the attribute's domain: the selected ones (corners of selected faces), or all."""
    domain = DOMAINS[attr.domain]
    if domain == "loops":
        return [l for f in bm.faces if (f.select or not selected) for l in f.loops]
    seq = getattr(bm, domain)
    return [e for e in seq if e.select] if selected else list(seq)


def _value(context, kind, assign):
    wm = context.window_manager
    if kind == "BOOL":
        return assign
    if kind == "INT":
        return wm.integer_value if assign else 0
    if kind == "FLOAT":
        return wm.float_value if assign else 0.0
    if kind == "COLOR":
        return tuple(wm.float_color_value) if assign else (0.0, 0.0, 0.0, 0.0)
    if kind == "VECTOR":
        return tuple(wm.keyops_vector_value) if assign else (0.0, 0.0, 0.0)
    if kind == "VECTOR2":
        return tuple(wm.keyops_vector_value)[:2] if assign else (0.0, 0.0)
    return None


def _matches(stored, value, kind):
    if kind in ("BOOL", "INT"):
        return stored == value
    if kind == "FLOAT":
        return abs(stored - value) < 1e-5
    if kind == "VECTOR2" and hasattr(stored, "uv"):
        stored = stored.uv
    return all(abs(a - b) < 1e-5 for a, b in zip(stored, value))


def _set(elem, layer, value, kind):
    if kind == "VECTOR2" and hasattr(elem[layer], "uv"):
        elem[layer].uv = value
    else:
        elem[layer] = value


# kind of value -> the attribute_set operator's argument for it
OP_ARGS = {"BOOL": "value_bool", "INT": "value_int", "FLOAT": "value_float", "VECTOR": "value_float_vector_3d",
           "VECTOR2": "value_float_vector_2d"}


def _op_assign(context, attr, kind, action):
    """Blender's attribute_set (C, fast) when it can set this type; False when it can't."""
    arg = OP_ARGS.get(kind)
    if kind == "COLOR":
        arg = "value_byte_color" if attr.data_type == 'BYTE_COLOR' else "value_color"
    props = bpy.ops.mesh.attribute_set.get_rna_type().properties
    if arg is None or arg not in props:
        return False
    try:
        bpy.ops.mesh.attribute_set(**{arg: _value(context, kind, action == "ASSIGN")})
    except (RuntimeError, TypeError):
        return False
    return True


def run(context, action, name=None):
    """Assign / Remove / Select / Deselect on every mesh in Edit Mode with the active attribute's name (or the
    given one). Returns (meshes done, elements touched, error or None)."""
    attr = _active_attribute(context)
    if name is not None:
        obj = context.active_object
        attr = obj.data.attributes.get(name) if obj is not None else None
    if attr is None:
        return 0, 0, "No active attribute"
    name, data_type, domain = attr.name, attr.data_type, attr.domain
    if data_type not in LAYERS:
        return 0, 0, f"{data_type.replace('_', ' ').title()} attributes aren't supported"
    if action in ("SELECT", "DESELECT") and domain == 'CORNER':
        return 0, 0, "Face corner attributes can't be selected by"
    kind = LAYERS[data_type][1]
    if action in ("ASSIGN", "REMOVE") and attr == _active_attribute(context) and _op_assign(context, attr, kind, action):
        return len(_edit_objects(context)), 0, None
    if action == "SELECT" and kind == "BOOL" and domain in SELECT_MODES and attr == _active_attribute(context):
        context.tool_settings.mesh_select_mode = SELECT_MODES[domain]
        bpy.ops.mesh.select_by_attribute()
        return len(_edit_objects(context)), 0, None
    done = touched = 0
    for obj in _edit_objects(context):
        a = obj.data.attributes.get(name)
        if a is None or a.data_type != data_type or a.domain != domain:
            continue
        bm = bmesh.from_edit_mesh(obj.data)
        layer, kind = _layer(bm, a)
        if layer is None and data_type == 'BOOLEAN':
            # Blender 4.2's bmesh has no boolean layers: Blender's own attribute operators do it there
            return _run_boolean_fallback(context, action, domain)
        if layer is None:
            return done, touched, f"This Blender can't edit {data_type.replace('_', ' ').lower()} attributes directly"
        if action in ("ASSIGN", "REMOVE"):
            value = _value(context, kind, action == "ASSIGN")
            for e in _elements(bm, a, selected=True):
                _set(e, layer, value, kind)
                touched += 1
        else:  # select / deselect what is set (booleans) or holds the current value
            value = True if kind == "BOOL" else _value(context, kind, True)
            on = action == "SELECT"
            for e in _elements(bm, a, selected=False):
                if _matches(e[layer], value, kind):
                    e.select_set(on)
                    touched += 1
            bm.select_flush_mode()
        done += 1
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    if action in ("SELECT", "DESELECT") and domain in SELECT_MODES:
        # show what was picked in the attribute's own select mode
        mode = SELECT_MODES[domain]
        if action == "SELECT" and tuple(context.tool_settings.mesh_select_mode) != mode:
            context.tool_settings.mesh_select_mode = mode
    return done, touched, None


def _selected_keys(context):
    keys = {}
    for obj in _edit_objects(context):
        bm = bmesh.from_edit_mesh(obj.data)
        keys[obj.name] = ({v.index for v in bm.verts if v.select}, {e.index for e in bm.edges if e.select},
                          {f.index for f in bm.faces if f.select})
    return keys


def _run_boolean_fallback(context, action, domain):
    """Boolean attributes where bmesh can't reach them (Blender 4.2): Blender's attribute operators, on the
    meshes in Edit Mode. Deselect is select-by-attribute, then the rest of the old selection is put back."""
    if action in ("ASSIGN", "REMOVE"):
        bpy.ops.mesh.attribute_set(value_bool=(action == "ASSIGN"))
        return 1, 0, None
    old_mode = tuple(context.tool_settings.mesh_select_mode)
    if domain in SELECT_MODES:
        context.tool_settings.mesh_select_mode = SELECT_MODES[domain]
    before = _selected_keys(context)
    if action == "DESELECT":
        bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_by_attribute()
    if action == "DESELECT":
        hit = _selected_keys(context)
        for obj in _edit_objects(context):
            bm = bmesh.from_edit_mesh(obj.data)
            old, new = before.get(obj.name), hit.get(obj.name)
            if old is None:
                continue
            for seq, keep in ((bm.verts, old[0] - new[0]), (bm.edges, old[1] - new[1]), (bm.faces, old[2] - new[2])):
                for e in seq:
                    e.select = e.index in keep
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        context.tool_settings.mesh_select_mode = old_mode
    return 1, 0, None


def _live_update(self, context):
    """Changing the value field applies it to the selection right away, like before."""
    if context.mode == 'EDIT_MESH' and _active_attribute(context) is not None:
        run(context, "ASSIGN")


def draw_custom_button(self, context):
    if not feature_on("atri_op"):
        return
    wm = context.window_manager
    obj = context.active_object
    if obj is None or obj.mode != 'EDIT':
        return
    layout = self.layout
    attr = obj.data.attributes.active
    if attr is not None and attr.data_type in LAYERS:
        kind = LAYERS[attr.data_type][1]
        row = layout.row(align=True)
        row.operator("keyops.atri_op", text="Assign").type = "Assign"
        row.operator("keyops.atri_op", text="Remove").type = "Remove"
        if attr.domain != 'CORNER':
            row.operator("keyops.atri_op", text="Select").type = "Select"
            row.operator("keyops.atri_op", text="Deselect").type = "Deselect"
        if kind != "BOOL":
            prop = {"INT": "integer_value", "FLOAT": "float_value", "COLOR": "float_color_value",
                    "VECTOR": "keyops_vector_value", "VECTOR2": "keyops_vector_value"}[kind]
            layout.row().prop(wm, prop, text="Value")

    row = layout.row(align=True)
    row.operator("keyops.atri_op", text="Vertex Group", icon="VERTEXSEL").type = "Vertex"
    row.operator("keyops.atri_op", text="Edge Group", icon="EDGESEL").type = "Edge"
    row.operator("keyops.atri_op", text="Face Group", icon="FACESEL").type = "Face"


class AtriOP(bpy.types.Operator):
    bl_idname = "keyops.atri_op"
    bl_label = "KeyOps: Atri OP"
    bl_description = "Attribute Operations"
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.StringProperty(default="") # type:ignore

    @classmethod
    def description(cls, context, props):
        return {
            "Assign": "Set the active attribute on the selection (booleans: on; others: the Value below)",
            "Remove": "Clear the active attribute on the selection (off, or zero)",
            "Select": "Select what has the active attribute set (booleans), or holds the Value below",
            "Deselect": "Deselect what has the active attribute set (booleans), or holds the Value below",
            "Vertex": "New boolean point attribute, set on the selected vertices",
            "Edge": "New boolean edge attribute, set on the selected edges",
            "Face": "New boolean face attribute, set on the selected faces",
        }.get(props.type, cls.bl_description) if props else cls.bl_description

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        if self.type in ("Vertex", "Edge", "Face"):
            domain = {"Vertex": 'POINT', "Edge": 'EDGE', "Face": 'FACE'}[self.type]
            name = f"{self.type}_Group"
            objs = _edit_objects(context)
            bpy.ops.object.mode_set(mode='OBJECT')  # adding an attribute needs the meshes out of Edit Mode
            for obj in objs:
                attr = obj.data.attributes.new(name=name, type='BOOLEAN', domain=domain)
                obj.data.attributes.active = attr
                name = attr.name  # the same name in every mesh
            bpy.ops.object.mode_set(mode='EDIT')
            for obj in objs:  # Edit Mode can reset the active attribute: make the new group active again
                attr = obj.data.attributes.get(name)
                if attr is not None:
                    obj.data.attributes.active = attr
            done, touched, err = run(context, "ASSIGN", name)
        else:
            action = self.type.upper()
            if action not in ("ASSIGN", "REMOVE", "SELECT", "DESELECT"):
                return {'CANCELLED'}
            done, touched, err = run(context, action)
        if err:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}
        if not done:
            self.report({'WARNING'}, "No mesh in Edit Mode has this attribute")
            return {'CANCELLED'}
        return {'FINISHED'}


def register():
    bpy.utils.register_class(AtriOP)
    bpy.types.DATA_PT_mesh_attributes.append(draw_custom_button)
    bpy.types.WindowManager.float_value = bpy.props.FloatProperty(name="Float Value", default=1.0, update=_live_update)
    bpy.types.WindowManager.float_color_value = bpy.props.FloatVectorProperty(size=4, subtype="COLOR", name="Float Color Value", default=(1.0, 1.0, 1.0, 1.0), min=0.0, max=1.0, update=_live_update)
    bpy.types.WindowManager.integer_value = bpy.props.IntProperty(name="Integer Value", default=0, update=_live_update)
    bpy.types.WindowManager.keyops_vector_value = bpy.props.FloatVectorProperty(size=3, name="Vector Value", default=(0.0, 0.0, 0.0), update=_live_update)


def unregister():
    bpy.utils.unregister_class(AtriOP)
    bpy.types.DATA_PT_mesh_attributes.remove(draw_custom_button)
    del bpy.types.WindowManager.float_value
    del bpy.types.WindowManager.float_color_value
    del bpy.types.WindowManager.integer_value
    del bpy.types.WindowManager.keyops_vector_value
