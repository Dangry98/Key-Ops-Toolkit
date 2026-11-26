"""Build Key Ops' Geometry Nodes groups into resources/node_groups.blend.

Run in the OLDEST Blender the add-on supports (see blender_manifest.toml), so every newer Blender can read it:
    blender -b resources/node_groups.blend --python scripts/build_node_groups.py
Each group is rebuilt from scratch (replacing an older copy of itself), given a fake user, and the file is
saved in place. Groups that aren't built here are left exactly as they are.
"""

import math

import bpy

TRIPLANAR = "Triplanar UV"


class G:
    """A tiny helper for wiring node groups from Python."""

    def __init__(self, tree):
        self.t = tree
        self.x = 0

    def node(self, kind, x=None, y=0, **props):
        n = self.t.nodes.new(kind)
        n.location = (x if x is not None else self.x, y)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, out, inp):
        self.t.links.new(out, inp)

    def math(self, op, a=None, b=None, x=0, y=0):
        n = self.node("ShaderNodeMath", x, y, operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                self.link(v, n.inputs[i])
        return n.outputs[0]

    def vmath(self, op, a=None, b=None, x=0, y=0):
        n = self.node("ShaderNodeVectorMath", x, y, operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (tuple, list)):
                n.inputs[i].default_value = v
            else:
                self.link(v, n.inputs[i])
        return n.outputs[0] if op not in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs[1]

    def switch(self, kind, cond, false, true, x=0, y=0):
        n = self.node("GeometryNodeSwitch", x, y, input_type=kind)
        self.link(cond, n.inputs[0])
        for sock, v in ((n.inputs[1], false), (n.inputs[2], true)):
            if hasattr(v, "is_output"):
                self.link(v, sock)
            else:
                sock.default_value = v
        return n.outputs[0]

    def compare(self, op, a, b, x=0, y=0):
        n = self.node("FunctionNodeCompare", x, y, data_type='FLOAT', operation=op)
        self.link(a, n.inputs[0])
        if isinstance(b, (int, float)):
            n.inputs[1].default_value = b
        else:
            self.link(b, n.inputs[1])
        return n.outputs[0]

    def boolean(self, op, a, b=None, x=0, y=0):
        n = self.node("FunctionNodeBooleanMath", x, y, operation=op)
        self.link(a, n.inputs[0])
        if b is not None:
            self.link(b, n.inputs[1])
        return n.outputs[0]

    def sep(self, v, x=0, y=0):
        n = self.node("ShaderNodeSeparateXYZ", x, y)
        self.link(v, n.inputs[0])
        return n.outputs

    def comb(self, a, b, c=0.0, x=0, y=0):
        n = self.node("ShaderNodeCombineXYZ", x, y)
        for i, v in enumerate((a, b, c)):
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                self.link(v, n.inputs[i])
        return n.outputs[0]


def socket(tree, name, kind, default=None, panel=None, desc="", minv=None, maxv=None, subtype=None, out=False):
    s = tree.interface.new_socket(name=name, in_out='OUTPUT' if out else 'INPUT', socket_type=kind, parent=panel)
    s.description = desc
    if default is not None:
        s.default_value = default
    if minv is not None:
        s.min_value = minv
    if maxv is not None:
        s.max_value = maxv
    if subtype is not None and hasattr(s, "subtype"):
        try:
            s.subtype = subtype
        except (TypeError, AttributeError):
            pass
    return s


def build_triplanar():
    old = bpy.data.node_groups.get(TRIPLANAR)
    if old is not None:
        bpy.data.node_groups.remove(old)
    t = bpy.data.node_groups.new(TRIPLANAR, 'GeometryNodeTree')
    t.use_fake_user = True
    t.description = ("Box / triplanar UVs: each face gets the UVs of the axis it faces most, upright and never "
                     "mirrored on any side")
    if hasattr(t, "is_modifier"):
        t.is_modifier = True

    socket(t, "Geometry", 'NodeSocketGeometry', out=True)
    socket(t, "Geometry", 'NodeSocketGeometry')
    socket(t, "Selection", 'NodeSocketBool', True, desc="Faces that get the new UVs")
    socket(t, "UV Map", 'NodeSocketString', "UVMap", desc="The UV map to write")
    socket(t, "Texture Size", 'NodeSocketFloat', 1.0, desc="How many metres one UV tile covers", minv=0.0001,
           subtype='DISTANCE')
    socket(t, "Rotation", 'NodeSocketFloat', 0.0, desc="Turn the UVs on every side", subtype='ANGLE')
    p_space = t.interface.new_panel("Space", default_closed=False)
    socket(t, "World Scale", 'NodeSocketBool', True, p_space,
           "The texture keeps its size when the object is scaled (same texel density on every object)")
    socket(t, "World Rotation", 'NodeSocketBool', False, p_space,
           "Project along the world axes instead of the object's own (the texture stays put when the object turns)")
    socket(t, "World Offset", 'NodeSocketBool', False, p_space,
           "The texture stays put when the object moves, instead of moving with it")
    p_off = t.interface.new_panel("Offset", default_closed=True)
    socket(t, "Offset X", 'NodeSocketFloat', 0.0, p_off, "Slide the UVs along U")
    socket(t, "Offset Y", 'NodeSocketFloat', 0.0, p_off, "Slide the UVs along V")
    p_adv = t.interface.new_panel("Per Axis", default_closed=True)
    socket(t, "Axis Scale", 'NodeSocketVector', (1.0, 1.0, 1.0), p_adv,
           "Stretch the texture along the X, Y and Z axes separately")
    socket(t, "Rotation X", 'NodeSocketFloat', 0.0, p_adv, "Extra turn on the faces facing X", subtype='ANGLE')
    socket(t, "Rotation Y", 'NodeSocketFloat', 0.0, p_adv, "Extra turn on the faces facing Y", subtype='ANGLE')
    socket(t, "Rotation Z", 'NodeSocketFloat', 0.0, p_adv, "Extra turn on the faces facing Z (tops and bottoms)",
           subtype='ANGLE')

    g = G(t)
    gi = g.node("NodeGroupInput", -1400, 0)
    go = g.node("NodeGroupOutput", 1600, 0)
    I = {s.name: gi.outputs[s.identifier] for s in t.interface.items_tree
         if s.item_type == 'SOCKET' and s.in_out == 'INPUT'}

    selfobj = g.node("GeometryNodeSelfObject", -1400, -600)
    info = g.node("GeometryNodeObjectInfo", -1200, -600, transform_space='ORIGINAL')
    g.link(selfobj.outputs[0], info.inputs[0])
    loc, rot, scl = info.outputs["Location"], info.outputs["Rotation"], info.outputs["Scale"]

    pos = g.node("GeometryNodeInputPosition", -1200, 200).outputs[0]
    nrm_node = g.node("GeometryNodeInputNormal", -1200, -200)
    face_n = g.node("GeometryNodeFieldOnDomain", -1000, -200, domain='FACE', data_type='FLOAT_VECTOR')
    g.link(nrm_node.outputs[0], face_n.inputs[0])
    nrm = face_n.outputs[0]

    # positions in the chosen space
    p_scaled = g.switch('VECTOR', I["World Scale"], pos, g.vmath('MULTIPLY', pos, scl, -900, 300), -750, 300)
    rot_p = g.node("ShaderNodeVectorRotate", -600, 300, rotation_type='EULER_XYZ')
    g.link(p_scaled, rot_p.inputs["Vector"])
    g.link(rot, rot_p.inputs["Rotation"])
    p_rot = g.switch('VECTOR', I["World Rotation"], p_scaled, rot_p.outputs[0], -450, 300)
    p_world = g.switch('VECTOR', I["World Offset"], p_rot, g.vmath('ADD', p_rot, loc, -350, 400), -250, 300)
    # texture size and per-axis scale
    size_v = g.vmath('MULTIPLY', I["Axis Scale"], g.comb(I["Texture Size"], I["Texture Size"], I["Texture Size"], -400, 100), -250, 100)
    p = g.vmath('DIVIDE', p_world, size_v, -100, 300)

    # normals in the same space (non-uniform scale bends normals the inverse way)
    n_scaled = g.switch('VECTOR', I["World Scale"], nrm, g.vmath('NORMALIZE', g.vmath('DIVIDE', nrm, scl, -900, -300), None, -800, -300), -650, -300)
    rot_n = g.node("ShaderNodeVectorRotate", -500, -300, rotation_type='EULER_XYZ')
    g.link(n_scaled, rot_n.inputs["Vector"])
    g.link(rot, rot_n.inputs["Rotation"])
    n = g.switch('VECTOR', I["World Rotation"], n_scaled, rot_n.outputs[0], -350, -300)

    nx, ny, nz = g.sep(n, -200, -300)
    ax, ay, az = (g.math('ABSOLUTE', c, None, -50, -250 - 60 * i) for i, c in enumerate((nx, ny, nz)))
    is_x = g.boolean('AND', g.compare('GREATER_EQUAL', ax, ay, 100, -200), g.compare('GREATER_EQUAL', ax, az, 100, -260), 250, -220)
    is_y = g.boolean('AND', g.boolean('NOT', is_x, None, 250, -300), g.compare('GREATER_EQUAL', ay, az, 100, -340), 400, -300)
    sx = g.math('SIGN', nx, None, 100, -420)
    sy = g.math('SIGN', ny, None, 100, -480)
    sz = g.math('SIGN', nz, None, 100, -540)
    # a face exactly sideways along an axis has sign 0 in the others: count it as positive
    sx = g.switch('FLOAT', g.compare('EQUAL', sx, 0.0, 250, -420), sx, 1.0, 400, -420)
    sy = g.switch('FLOAT', g.compare('EQUAL', sy, 0.0, 250, -480), sy, 1.0, 400, -480)
    sz = g.switch('FLOAT', g.compare('EQUAL', sz, 0.0, 250, -540), sz, 1.0, 400, -540)

    px, py, pz = g.sep(p, 100, 300)
    # upright on every side, never mirrored: +X (y, z) -X (-y, z) +Y (-x, z) -Y (x, z) +Z (x, y) -Z (x, -y)
    uv_x = g.comb(g.math('MULTIPLY', py, sx, 300, 450), pz, 0.0, 500, 450)
    uv_y = g.comb(g.math('MULTIPLY', g.math('MULTIPLY', px, sy, 300, 350), -1.0, 400, 350), pz, 0.0, 500, 350)
    uv_z = g.comb(px, g.math('MULTIPLY', py, sz, 300, 250), 0.0, 500, 250)
    uv = g.switch('VECTOR', is_x, g.switch('VECTOR', is_y, uv_z, uv_y, 650, 330), uv_x, 800, 380)

    # rotation: the global angle plus the face's axis
    ang_axis = g.switch('FLOAT', is_x, g.switch('FLOAT', is_y, I["Rotation Z"], I["Rotation Y"], 650, 100), I["Rotation X"], 800, 100)
    ang = g.math('ADD', I["Rotation"], ang_axis, 950, 100)
    u, v, _w = g.sep(uv, 950, 380)
    c = g.math('COSINE', ang, None, 1100, 150)
    s_ = g.math('SINE', ang, None, 1100, 90)
    ru = g.math('SUBTRACT', g.math('MULTIPLY', u, c, 1200, 450), g.math('MULTIPLY', v, s_, 1200, 400), 1300, 430)
    rv = g.math('ADD', g.math('MULTIPLY', u, s_, 1200, 340), g.math('MULTIPLY', v, c, 1200, 290), 1300, 320)
    final = g.comb(g.math('ADD', ru, I["Offset X"], 1400, 430), g.math('ADD', rv, I["Offset Y"], 1400, 330), 0.0, 1500, 380)

    store = g.node("GeometryNodeStoreNamedAttribute", 1450, 0, data_type='FLOAT2', domain='CORNER')
    g.link(I["Geometry"], store.inputs["Geometry"])
    g.link(I["Selection"], store.inputs["Selection"])
    g.link(I["UV Map"], store.inputs["Name"])
    g.link(final, store.inputs["Value"])
    g.link(store.outputs[0], go.inputs[0])
    return t


if __name__ == "__main__":
    build_triplanar()
    bpy.context.preferences.filepaths.save_version = 0  # no .blend1 backup next to it
    bpy.ops.wm.save_mainfile(compress=True)
    print("BUILT", TRIPLANAR)
