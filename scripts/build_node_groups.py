"""Build Key Ops' Geometry Nodes groups into resources/node_groups.blend (and newer per-version files).

Run in the OLDEST Blender the add-on supports (see blender_manifest.toml), so every newer Blender can read it:
    blender -b resources/node_groups.blend --python scripts/build_node_groups.py
and for each newer file in VERSIONED (at the bottom), in exactly that Blender version:
    blender-4.3 -b --factory-startup --python scripts/build_node_groups.py   -> resources/node_groups_4_3.blend
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

    def scale(self, v, factor, x=0, y=0):
        """Vector times a number (a float, or a socket)."""
        n = self.node("ShaderNodeVectorMath", x, y, operation='SCALE')
        self.link(v, n.inputs[0])
        if isinstance(factor, (int, float)):
            n.inputs["Scale"].default_value = factor
        else:
            self.link(factor, n.inputs["Scale"])
        return n.outputs[0]

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


EDGE_TRIM = "Edge Trim Live"


def add_trim_gizmos(g, I, curve):
    """Blender 4.3+: arrows in the viewport for Width, Second Width and Offset, at the trim's first point, each
    pointing the way its flange (or the gap) grows."""
    def at_start(field, kind, x, y):
        smp = g.node("GeometryNodeSampleIndex", x, y, data_type=kind, domain='POINT')
        g.link(curve, smp.inputs[0])
        g.link(field, smp.inputs["Value"])
        smp.inputs["Index"].default_value = 0
        return smp.outputs[0]

    def named(name, kind, x, y):
        n = g.node("GeometryNodeInputNamedAttribute", x, y, data_type=kind)
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]
    x, y = 1400, -1800
    p0 = at_start(g.node("GeometryNodeInputPosition", x - 150, y).outputs[0], 'FLOAT_VECTOR', x, y)
    t0 = at_start(named("trim_tn", 'FLOAT_VECTOR', x - 150, y - 80), 'FLOAT_VECTOR', x, y - 80)
    n0 = at_start(named("trim_nn", 'FLOAT_VECTOR', x - 150, y - 160), 'FLOAT_VECTOR', x, y - 160)
    # the same frame as the profile (offset_for below)
    N = g.switch('VECTOR', I["Flip Up"], n0, g.scale(n0, -1.0, x + 150, y - 160), x + 250, y - 160)
    S0 = g.vmath('NORMALIZE', g.vmath('CROSS_PRODUCT', t0, N, x + 350, y - 100), None, x + 450, y - 100)
    S = g.switch('VECTOR', I["Flip Side"], S0, g.scale(S0, -1.0, x + 500, y - 140), x + 600, y - 100)
    a0 = at_start(named("trim_an", 'FLOAT_VECTOR', x - 150, y - 320), 'FLOAT_VECTOR', x, y - 320)
    b0 = at_start(named("trim_bn", 'FLOAT_VECTOR', x - 150, y - 380), 'FLOAT_VECTOR', x, y - 380)
    fa = g.switch('VECTOR', I["Flip Side"], a0, b0, x + 600, y - 200)
    fb = g.switch('VECTOR', I["Flip Side"], b0, a0, x + 600, y - 260)
    dA = g.switch('VECTOR', I["Wrap"], N, fa, x + 900, y - 180)
    dB = g.switch('VECTOR', I["Wrap"], S, fb, x + 900, y - 260)
    lifted = g.vmath('ADD', p0, g.scale(N, I["Offset"], x + 800, y - 340), x + 900, y - 340)
    for k, (value, direction, pos, style, color) in enumerate((
            (I["Width"], dA, lifted, 'ARROW', 'PRIMARY'),
            (I["Second Width"], dB, lifted, 'ARROW', 'PRIMARY'),
            (I["Offset"], N, p0, 'BOX', 'SECONDARY'))):
        gz = g.node("GeometryNodeGizmoLinear", x + 1100, y - 120 * k, draw_style=style, color_id=color)
        g.link(value, gz.inputs["Value"])
        g.link(pos, gz.inputs["Position"])
        g.link(direction, gz.inputs["Direction"])


def build_edge_trim(gizmos=False):
    """Live Make Edge Trim: reads the source object, takes the edges marked with a boolean edge attribute, and
    sweeps an L profile (two flanges) along them with trim-sheet UVs. Updates whenever the source changes.
    gizmos (Blender 4.3+): viewport arrows for Width, Second Width and Offset."""
    old = bpy.data.node_groups.get(EDGE_TRIM)
    if old is not None:
        bpy.data.node_groups.remove(old)
    t = bpy.data.node_groups.new(EDGE_TRIM, 'GeometryNodeTree')
    t.use_fake_user = True
    t.description = "An L-shaped trim along marked edges of another object, kept up to date as it changes"
    if hasattr(t, "is_modifier"):
        t.is_modifier = True
    socket(t, "Geometry", 'NodeSocketGeometry', out=True)
    socket(t, "Geometry", 'NodeSocketGeometry')
    socket(t, "Source", 'NodeSocketObject', desc="The object whose edges get the trim")
    socket(t, "Edge Attribute", 'NodeSocketString', "keyops_trim", desc="Boolean edge attribute marking the edges")
    socket(t, "Width", 'NodeSocketFloat', 0.05, desc="Width of the first flange", subtype='DISTANCE')
    socket(t, "Second Width", 'NodeSocketFloat', 0.05, desc="Width of the second flange", subtype='DISTANCE')
    socket(t, "Offset", 'NodeSocketFloat', 0.002, desc="Gap between the trim and the surface", subtype='DISTANCE')
    socket(t, "Wrap", 'NodeSocketBool', True, desc="On: fold around the edge (both flanges lie back along the "
                                                    "surface). Off: one flange stands up, one lies on the surface")
    socket(t, "Flip Side", 'NodeSocketBool', False, desc="Put the trim on the other side of the edges")
    socket(t, "Flip Up", 'NodeSocketBool', False, desc="Point the trim the other way along the surface normal")
    socket(t, "Flip Faces", 'NodeSocketBool', False, desc="Turn the trim's faces around")
    p_uv = t.interface.new_panel("Trim Sheet", default_closed=False)
    socket(t, "V Min", 'NodeSocketFloat', 0.0, p_uv, "Bottom of the trim's strip on the sheet")
    socket(t, "V Max", 'NodeSocketFloat', 0.125, p_uv, "Top of the trim's strip on the sheet")
    socket(t, "UV per Metre", 'NodeSocketFloat', 1.0, p_uv, "How often the texture repeats along the trim, per metre")
    socket(t, "UV Offset", 'NodeSocketFloat', 0.0, p_uv, "Slide the texture along the trim")
    socket(t, "UV Rotation", 'NodeSocketFloat', 0.0, p_uv, "Turn the UVs (90 degrees for a sheet with vertical "
                                                          "strips)", subtype='ANGLE')
    # added later: new sockets go last (existing ids stay), then move up in the list
    sep_w = socket(t, "Separate Widths", 'NodeSocketBool', False,
                   desc="Give the second flange its own width (off: both flanges use Width)")
    mat = socket(t, "Material", 'NodeSocketMaterial', desc="Material of the trim (the operator sets the source's)")
    items = [i for i in t.interface.items_tree if i.item_type == 'SOCKET' and i.in_out == 'INPUT']
    names = [i.name for i in items]
    t.interface.move(sep_w, items[names.index("Width")].position + 1)
    items = [i for i in t.interface.items_tree if i.item_type == 'SOCKET' and i.in_out == 'INPUT']
    names = [i.name for i in items]
    t.interface.move(mat, items[names.index("Offset")].position + 1)

    g = G(t)
    gi = g.node("NodeGroupInput", -1800, 0)
    go = g.node("NodeGroupOutput", 1900, 0)
    I = {s.name: gi.outputs[s.identifier] for s in t.interface.items_tree
         if s.item_type == 'SOCKET' and s.in_out == 'INPUT'}

    info = g.node("GeometryNodeObjectInfo", -1600, 200, transform_space='RELATIVE')
    g.link(I["Source"], info.inputs["Object"])
    src = info.outputs["Geometry"]
    # each edge's normal: the average of its faces' normals (Normal read on the edge domain)
    edge_n = g.node("GeometryNodeFieldOnDomain", -1500, -100, domain='EDGE', data_type='FLOAT_VECTOR')
    g.link(g.node("GeometryNodeInputNormal", -1650, -100).outputs[0], edge_n.inputs[0])
    st_n = g.node("GeometryNodeStoreNamedAttribute", -1350, 200, data_type='FLOAT_VECTOR', domain='EDGE')
    st_n.inputs["Name"].default_value = "trim_n"
    g.link(src, st_n.inputs["Geometry"])
    g.link(edge_n.outputs[0], st_n.inputs["Value"])
    marked = g.node("GeometryNodeInputNamedAttribute", -1350, -150, data_type='BOOLEAN')
    g.link(I["Edge Attribute"], marked.inputs["Name"])
    # each edge's two faces, exactly (from the topology, not by sampling the surface): their normals and centres,
    # and how many faces the edge has (2, 1 on a border, 0 for a wire edge)
    geo = st_n.outputs[0]
    face_count = g.node("GeometryNodeInputMeshEdgeNeighbors", -1500, -900).outputs["Face Count"]
    face_n = g.node("GeometryNodeInputNormal", -1500, -980).outputs[0]
    face_p = g.node("GeometryNodeInputPosition", -1500, -1040).outputs[0]
    per_face = {}
    for k in (0, 1):
        y0 = -1100 - 300 * k
        coe = g.node("GeometryNodeCornersOfEdge", -1450, y0)
        coe.inputs["Sort Index"].default_value = k
        foc = g.node("GeometryNodeFaceOfCorner", -1300, y0)
        g.link(coe.outputs["Corner Index"], foc.inputs["Corner Index"])
        smp = g.node("GeometryNodeSampleIndex", -1150, y0, data_type='FLOAT_VECTOR', domain='FACE')
        g.link(st_n.outputs[0], smp.inputs[0])
        g.link(face_n, smp.inputs["Value"])
        g.link(foc.outputs["Face Index"], smp.inputs["Index"])
        per_face["n" + str(k)] = smp.outputs[0]
        # into the face: the face's normal crossed with the edge as the face runs it (counter-clockwise), which
        # points inside the face even when the face is concave (its centre can lie outside it)
        ends = []
        for j, offset in enumerate((0, 1)):
            corner = coe.outputs["Corner Index"]
            if offset:
                oc = g.node("GeometryNodeOffsetCornerInFace", -1300, y0 - 120)
                g.link(corner, oc.inputs["Corner Index"])
                oc.inputs["Offset"].default_value = 1
                corner = oc.outputs["Corner Index"]
            voc = g.node("GeometryNodeVertexOfCorner", -1150, y0 - 60 - 60 * j)
            g.link(corner, voc.inputs["Corner Index"])
            sp = g.node("GeometryNodeSampleIndex", -1000, y0 - 60 - 60 * j, data_type='FLOAT_VECTOR', domain='POINT')
            g.link(st_n.outputs[0], sp.inputs[0])
            g.link(face_p, sp.inputs["Value"])
            g.link(voc.outputs["Vertex Index"], sp.inputs["Index"])
            ends.append(sp.outputs[0])
        run = g.vmath('SUBTRACT', ends[1], ends[0], -850, y0 - 90)
        per_face["i" + str(k)] = g.vmath('NORMALIZE', g.vmath('CROSS_PRODUCT', per_face["n" + str(k)], run, -750, y0),
                                         None, -650, y0)
    one = g.compare('LESS_THAN', face_count, 1.5, -1000, -1800)  # a border edge: its one face both times
    for name in ("n", "i"):
        per_face[name + "1"] = g.switch('VECTOR', one, per_face[name + "1"], per_face[name + "0"], -900, -1800)
    for name, value, kind in (("trim_n0", per_face["n0"], 'FLOAT_VECTOR'), ("trim_n1", per_face["n1"], 'FLOAT_VECTOR'),
                              ("trim_i0", per_face["i0"], 'FLOAT_VECTOR'), ("trim_i1", per_face["i1"], 'FLOAT_VECTOR'),
                              ("trim_fc", face_count, 'FLOAT')):
        st = g.node("GeometryNodeStoreNamedAttribute", -1250, 400, data_type=kind, domain='EDGE')
        st.inputs["Name"].default_value = name
        g.link(geo, st.inputs["Geometry"])
        g.link(value, st.inputs["Value"])
        geo = st.outputs[0]
    sep = g.node("GeometryNodeSeparateGeometry", -1150, 200, domain='EDGE')
    g.link(geo, sep.inputs["Geometry"])
    g.link(marked.outputs["Attribute"], sep.inputs["Selection"])
    m2c = g.node("GeometryNodeMeshToCurve", -950, 200)
    g.link(sep.outputs["Selection"], m2c.inputs["Mesh"])
    curve = m2c.outputs[0]

    # remember, per curve point, what the profile needs: position, normal, tangent, length along and total
    def store(geo, name, kind, value, x, y):
        n = g.node("GeometryNodeStoreNamedAttribute", x, y, data_type=kind, domain='POINT')
        n.inputs["Name"].default_value = name
        g.link(geo, n.inputs["Geometry"])
        g.link(value, n.inputs["Value"])
        return n.outputs[0]
    pos = g.node("GeometryNodeInputPosition", -900, -50).outputs[0]
    curve = store(curve, "trim_p", 'FLOAT_VECTOR', pos, -750, 200)
    spl = g.node("GeometryNodeSplineParameter", -600, -50)
    curve = store(curve, "trim_l", 'FLOAT', spl.outputs["Length"], -450, 200)
    slen = g.node("GeometryNodeSplineLength", -450, -50)
    curve = store(curve, "trim_len", 'FLOAT', slen.outputs["Length"], -300, 200)

    # neighbours along the curve: previous / next point (none at the ends of an open chain)
    def neighbour(offset, y):
        n = g.node("GeometryNodeOffsetPointInCurve", -300, y)
        n.inputs["Offset"].default_value = offset
        smp = g.node("GeometryNodeSampleIndex", -150, y, data_type='FLOAT_VECTOR', domain='POINT')
        g.link(curve, smp.inputs[0])
        g.link(g.node("GeometryNodeInputPosition", -300, y - 80).outputs[0], smp.inputs["Value"])
        g.link(n.outputs["Point Index"], smp.inputs["Index"])
        return smp.outputs[0], n.outputs["Is Valid Offset"]
    p_prev, has_prev = neighbour(-1, -150)
    p_next, has_next = neighbour(1, -300)
    here = g.node("GeometryNodeInputPosition", -150, -450).outputs[0]
    n_attr = g.node("GeometryNodeInputNamedAttribute", -150, -520, data_type='FLOAT_VECTOR')
    n_attr.inputs["Name"].default_value = "trim_n"
    n_avg = g.vmath('NORMALIZE', n_attr.outputs["Attribute"], None, 0, -520)

    face_normal = g.node("GeometryNodeFieldOnDomain", -150, -700, domain='FACE', data_type='FLOAT_VECTOR')
    g.link(g.node("GeometryNodeInputNormal", -300, -700).outputs[0], face_normal.inputs[0])

    edges_geo = sep.outputs["Selection"]  # the marked edges, with their face data

    def edge_value(name, kind, idx, x, y):
        attr = g.node("GeometryNodeInputNamedAttribute", x, y, data_type=kind)
        attr.inputs["Name"].default_value = name
        smp = g.node("GeometryNodeSampleIndex", x + 150, y, data_type=kind, domain='EDGE')
        g.link(edges_geo, smp.inputs[0])
        g.link(attr.outputs["Attribute"], smp.inputs["Value"])
        g.link(idx, smp.inputs["Index"])
        return smp.outputs[0]

    def seg_normal(a, b, y):
        """Segment a-b: its tangent, the edge normal, whether the edge is concave (fold +1) or convex (-1), and the
        directions lying in the two faces beside it, away from the edge (on the +side and on the -side). From the
        edge's own faces: exact, also next to narrow faces (a bevel)."""
        t = g.vmath('NORMALIZE', g.vmath('SUBTRACT', b, a, 0, y), None, 100, y)
        mid = g.scale(g.vmath('ADD', a, b, 200, y - 60), 0.5, 300, y - 60)
        near = g.node("GeometryNodeSampleNearest", 400, y - 60, domain='EDGE')
        g.link(edges_geo, near.inputs["Geometry"])
        g.link(mid, near.inputs["Sample Position"])
        idx = near.outputs["Index"]
        n0 = edge_value("trim_n0", 'FLOAT_VECTOR', idx, 550, y)
        n1 = edge_value("trim_n1", 'FLOAT_VECTOR', idx, 550, y - 60)
        i0 = edge_value("trim_i0", 'FLOAT_VECTOR', idx, 550, y - 120)
        i1 = edge_value("trim_i1", 'FLOAT_VECTOR', idx, 550, y - 180)
        fc = edge_value("trim_fc", 'FLOAT', idx, 550, y - 240)
        wire = g.compare('LESS_THAN', fc, 0.5, 800, y - 240)
        border = g.compare('LESS_THAN', fc, 1.5, 800, y - 280)
        navg0 = g.vmath('NORMALIZE', g.vmath('ADD', n0, n1, 800, y), None, 900, y)
        n = g.switch('VECTOR', wire, navg0, (0.0, 0.0, 1.0), 1000, y)
        side = g.vmath('NORMALIZE', g.vmath('CROSS_PRODUCT', t, n, 1000, y - 60), None, 1100, y - 60)
        # which face lies on the +side
        first_plus = g.compare('GREATER_THAN', g.vmath('DOT_PRODUCT', i0, side, 1200, y - 120), 0.0, 1300, y - 120)
        n_plus = g.switch('VECTOR', first_plus, n1, n0, 1400, y)
        d_plus = g.switch('VECTOR', first_plus, i1, i0, 1400, y - 80)
        d_minus = g.switch('VECTOR', first_plus, i0, i1, 1400, y - 120)
        # a border edge: the second flange stands up from its one face; a wire edge: upright
        d_minus = g.switch('VECTOR', border, d_minus, n, 2200, y - 160)
        d_plus = g.switch('VECTOR', wire, d_plus, side, 2200, y)
        concave = g.compare('LESS_THAN', g.vmath('DOT_PRODUCT', n_plus, side, 1500, y - 300), 0.0, 1600, y - 300)
        fold = g.switch('FLOAT', concave, -1.0, 1.0, 1700, y - 300)
        return t, n, fold, d_plus, d_minus

    t_prev, n_prev, f_prev, a_prev, b_prev = seg_normal(p_prev, here, -800)
    t_next, n_next, f_next, a_next, b_next = seg_normal(here, p_next, -1100)
    # an end of an open chain uses the one segment it has
    t_prev = g.switch('VECTOR', has_prev, t_next, t_prev, 1150, -800)
    n_prev = g.switch('VECTOR', has_prev, n_next, n_prev, 1150, -860)
    t_next = g.switch('VECTOR', has_next, t_prev, t_next, 1250, -1100)
    n_next = g.switch('VECTOR', has_next, n_prev, n_next, 1250, -1160)
    f_prev = g.switch('FLOAT', has_prev, f_next, f_prev, 1150, -920)
    f_next = g.switch('FLOAT', has_next, f_prev, f_next, 1250, -1220)
    a_prev = g.switch('VECTOR', has_prev, a_next, a_prev, 1150, -980)
    b_prev = g.switch('VECTOR', has_prev, b_next, b_prev, 1150, -1040)
    a_next = g.switch('VECTOR', has_next, a_prev, a_next, 1250, -1280)
    b_next = g.switch('VECTOR', has_next, b_prev, b_next, 1250, -1340)
    for name, val, y in (("trim_tp", t_prev, 150), ("trim_np", n_prev, 100), ("trim_tn", t_next, 50), ("trim_nn", n_next, 0)):
        curve = store(curve, name, 'FLOAT_VECTOR', val, 1350, y)
    for name, val, y in (("trim_fp", f_prev, -50), ("trim_fn", f_next, -100)):
        curve = store(curve, name, 'FLOAT', val, 1350, y)
    for name, val, y in (("trim_ap", a_prev, -150), ("trim_bp", b_prev, -200), ("trim_an", a_next, -250),
                         ("trim_bn", b_next, -300)):
        curve = store(curve, name, 'FLOAT_VECTOR', val, 1350, y)

    if gizmos:
        add_trim_gizmos(g, I, curve)

    # the profile: three points (flange end, corner, flange end), numbered 0, 1, 2
    line = g.node("GeometryNodeCurvePrimitiveLine", -600, -1400)
    res = g.node("GeometryNodeResampleCurve", -450, -1400)
    res.inputs["Count"].default_value = 3
    g.link(line.outputs[0], res.inputs["Curve"])
    prof = store(res.outputs[0], "trim_id", 'FLOAT', g.node("GeometryNodeInputIndex", -450, -1550).outputs[0], -300, -1400)

    c2m = g.node("GeometryNodeCurveToMesh", 1500, 200)
    g.link(curve, c2m.inputs["Curve"])
    g.link(prof, c2m.inputs["Profile Curve"])
    mesh = c2m.outputs[0]

    def attr(name, kind, x, y):
        n = g.node("GeometryNodeInputNamedAttribute", x, y, data_type=kind)
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]
    X0 = 1600
    P = attr("trim_p", 'FLOAT_VECTOR', X0, -200)
    pid = attr("trim_id", 'FLOAT', X0, -260)
    is0 = g.compare('LESS_THAN', pid, 0.5, X0 + 150, -260)
    is2 = g.compare('GREATER_THAN', pid, 1.5, X0 + 150, -320)

    def offset_for(T, N0, F, DA, DB, y):
        """This vertex's offset from the edge in one segment's frame (flange A end, corner or flange B end).
        Wrap: each flange lies on the face beside the edge, at whatever angle the faces meet (DA, DB: the
        directions in those faces). Off: flange A stands up along the normal, flange B lies along the side."""
        N = g.switch('VECTOR', I["Flip Up"], N0, g.scale(N0, -1.0, X0 + 100, y - 40), X0 + 200, y)
        S0 = g.vmath('NORMALIZE', g.vmath('CROSS_PRODUCT', T, N, X0 + 300, y), None, X0 + 400, y)
        S = g.switch('VECTOR', I["Flip Side"], S0, g.scale(S0, -1.0, X0 + 450, y - 40), X0 + 500, y)
        fa = g.switch('VECTOR', I["Flip Side"], DA, DB, X0 + 550, y - 80)
        fb = g.switch('VECTOR', I["Flip Side"], DB, DA, X0 + 550, y - 120)
        dA = g.switch('VECTOR', I["Wrap"], N, fa, X0 + 800, y)
        dB = g.switch('VECTOR', I["Wrap"], S, fb, X0 + 800, y - 60)
        lift = g.scale(N, I["Offset"], X0 + 800, y - 120)
        width_b = g.switch('FLOAT', I["Separate Widths"], I["Width"], I["Second Width"], X0 + 850, y - 100)
        a = g.scale(dA, I["Width"], X0 + 900, y)
        b = g.scale(dB, width_b, X0 + 900, y - 60)
        zero = g.scale(N, 0.0, X0 + 950, y - 120)  # the corner: no flange
        o = g.switch('VECTOR', is0, g.switch('VECTOR', is2, zero, b, X0 + 1000, y - 60), a, X0 + 1100, y)
        return g.vmath('ADD', o, lift, X0 + 1200, y)

    tp, np_ = attr("trim_tp", 'FLOAT_VECTOR', X0, -400), attr("trim_np", 'FLOAT_VECTOR', X0, -450)
    tn, nn = attr("trim_tn", 'FLOAT_VECTOR', X0, -700), attr("trim_nn", 'FLOAT_VECTOR', X0, -750)
    o_prev = offset_for(tp, np_, attr("trim_fp", 'FLOAT', X0, -500), attr("trim_ap", 'FLOAT_VECTOR', X0, -540),
                        attr("trim_bp", 'FLOAT_VECTOR', X0, -580), -400)
    o_next = offset_for(tn, nn, attr("trim_fn", 'FLOAT', X0, -800), attr("trim_an", 'FLOAT_VECTOR', X0, -840),
                        attr("trim_bn", 'FLOAT_VECTOR', X0, -880), -700)
    # mitre: where the previous segment's line through o_prev meets the next segment's line through o_next
    b_ = g.vmath('DOT_PRODUCT', tp, tn, X0 + 1300, -500)
    w0 = g.vmath('SUBTRACT', o_prev, o_next, X0 + 1300, -560)
    d_ = g.vmath('DOT_PRODUCT', tp, w0, X0 + 1400, -560)
    e_ = g.vmath('DOT_PRODUCT', tn, w0, X0 + 1400, -620)
    denom = g.math('SUBTRACT', 1.0, g.math('MULTIPLY', b_, b_, X0 + 1400, -500), X0 + 1500, -500)
    straight = g.compare('LESS_THAN', denom, 1e-4, X0 + 1600, -500)
    safe = g.math('MAXIMUM', denom, 1e-4, X0 + 1600, -440)
    tpar = g.math('DIVIDE', g.math('SUBTRACT', g.math('MULTIPLY', b_, e_, X0 + 1500, -620), d_, X0 + 1600, -620), safe, X0 + 1700, -600)
    spar = g.math('DIVIDE', g.math('SUBTRACT', e_, g.math('MULTIPLY', b_, d_, X0 + 1500, -700), X0 + 1600, -700), safe, X0 + 1700, -700)
    m1 = g.vmath('ADD', o_prev, g.scale(tp, tpar, X0 + 1800, -600), X0 + 1900, -600)
    m2 = g.vmath('ADD', o_next, g.scale(tn, spar, X0 + 1800, -700), X0 + 1900, -700)
    mitre = g.scale(g.vmath('ADD', m1, m2, X0 + 2000, -650), 0.5, X0 + 2100, -650)
    avg = g.scale(g.vmath('ADD', o_prev, o_next, X0 + 2000, -500), 0.5, X0 + 2100, -500)
    off = g.switch('VECTOR', straight, mitre, avg, X0 + 2200, -550)
    setp = g.node("GeometryNodeSetPosition", X0 + 2300, 200)
    g.link(mesh, setp.inputs["Geometry"])
    g.link(g.vmath('ADD', P, off, X0 + 2300, -300), setp.inputs["Position"])
    mesh = setp.outputs[0]

    # UVs: V by profile point (split at the corner by flange width), U by length along the trim; on a closed
    # loop, the face that wraps round gets the full length added on its start corners
    wa = g.math('ABSOLUTE', I["Width"], None, 300, -700)
    wb = g.math('ABSOLUTE', g.switch('FLOAT', I["Separate Widths"], I["Width"], I["Second Width"], 150, -750), None, 300, -750)
    frac = g.math('DIVIDE', wa, g.math('MAXIMUM', g.math('ADD', wa, wb, 450, -730), 1e-9, 550, -730), 650, -720)
    v_corner = g.math('ADD', I["V Min"], g.math('MULTIPLY', g.math('SUBTRACT', I["V Max"], I["V Min"], 650, -800), frac, 750, -780), 850, -760)
    v = g.switch('FLOAT', is0, g.switch('FLOAT', is2, v_corner, I["V Min"], 950, -700), I["V Max"], 1050, -700)
    L = attr("trim_l", 'FLOAT', 300, -900)
    Ltot = attr("trim_len", 'FLOAT', 300, -950)
    face_avg = g.node("GeometryNodeFieldOnDomain", 450, -1000, domain='FACE', data_type='FLOAT')
    g.link(L, face_avg.inputs[0])
    wraps = g.compare('LESS_THAN', g.math('ADD', L, g.math('MULTIPLY', Ltot, 0.5, 450, -950), 600, -930), face_avg.outputs[0], 750, -930)
    L2 = g.switch('FLOAT', wraps, L, g.math('ADD', L, Ltot, 750, -1000), 900, -930)
    u = g.math('ADD', g.math('MULTIPLY', L2, I["UV per Metre"], 1000, -930), I["UV Offset"], 1100, -930)
    c = g.math('COSINE', I["UV Rotation"], None, 1100, -1050)
    s_ = g.math('SINE', I["UV Rotation"], None, 1100, -1100)
    ru = g.math('SUBTRACT', g.math('MULTIPLY', u, c, 1250, -900), g.math('MULTIPLY', v, s_, 1250, -950), 1350, -920)
    rv = g.math('ADD', g.math('MULTIPLY', u, s_, 1250, -1000), g.math('MULTIPLY', v, c, 1250, -1050), 1350, -1020)
    uvs = g.node("GeometryNodeStoreNamedAttribute", 1450, 200, data_type='FLOAT2', domain='CORNER')
    uvs.inputs["Name"].default_value = "UVMap"
    g.link(mesh, uvs.inputs["Geometry"])
    g.link(g.comb(ru, rv, 0.0, 1450, -950), uvs.inputs["Value"])
    flip = g.node("GeometryNodeFlipFaces", 1600, 200)
    g.link(uvs.outputs[0], flip.inputs["Mesh"])
    # Wrap lays flange A on the +side face, which winds the profile the other way round than Upright
    g.link(g.boolean('XOR', I["Flip Faces"], I["Wrap"], 1500, 120), flip.inputs["Selection"])
    smooth = g.node("GeometryNodeSetShadeSmooth", 1750, 200)
    g.link(flip.outputs[0], smooth.inputs[0])
    setmat = g.node("GeometryNodeSetMaterial", 1800, 260)
    g.link(smooth.outputs[0], setmat.inputs["Geometry"])
    g.link(I["Material"], setmat.inputs["Material"])
    smooth = setmat
    # drop the helper attributes so the trim object stays clean
    rm = g.node("GeometryNodeRemoveAttribute", 1850, 350)
    g.link(smooth.outputs[0], rm.inputs[0])
    if "Pattern Mode" in [i.name for i in rm.inputs] or hasattr(rm, "pattern_mode"):
        pass
    rm.inputs["Name"].default_value = "trim_p"
    out = rm.outputs[0]
    for name in ("trim_tp", "trim_np", "trim_tn", "trim_nn", "trim_fp", "trim_fn", "trim_l", "trim_len", "trim_id", "trim_n",
                 "trim_ap", "trim_bp", "trim_an", "trim_bn", "trim_n0", "trim_n1", "trim_i0", "trim_i1", "trim_fc"):
        r = g.node("GeometryNodeRemoveAttribute", 1850, 350)
        g.link(out, r.inputs[0])
        r.inputs["Name"].default_value = name
        out = r.outputs[0]
    g.link(out, go.inputs[0])
    return t


# Files per Blender version: resources/node_groups.blend is built in 4.2 and holds every group; a newer file
# holds only the groups that use features of that version (utils/node_groups.py loads the newest file the
# running Blender can read that has the group, so every version 4.2-5.x gets the best build it can open).
VERSIONED = (((4, 3), "node_groups_4_3.blend", (build_edge_trim,)),)  # 4.3: geometry nodes gizmos


if __name__ == "__main__":
    import os
    bpy.context.preferences.filepaths.save_version = 0  # no .blend1 backup next to it
    resources = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")
    newer = [v for v in VERSIONED if bpy.app.version >= v[0]]
    if not newer:
        build_triplanar()
        build_edge_trim()
        bpy.ops.wm.save_mainfile(compress=True)
        print("BUILT", TRIPLANAR, EDGE_TRIM)
    else:
        version, name, builders = newer[-1]
        if bpy.app.version[:2] != version:
            raise SystemExit(f"Build {name} in Blender {version[0]}.{version[1]} (the oldest that should read it)")
        for ng in list(bpy.data.node_groups):
            bpy.data.node_groups.remove(ng)
        for build in builders:
            build(gizmos=True) if build is build_edge_trim else build()
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(resources, name), compress=True)
        print("BUILT", name, [ng.name for ng in bpy.data.node_groups])
