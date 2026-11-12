import os

import bpy
import bmesh
import gpu
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d,
    region_2d_to_origin_3d,
    region_2d_to_vector_3d,
)
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_point_line

from ..utils import draw_utils as DrawUtils

# Fast Loop Cut: hover over an edge to preview the loop exactly where the cursor is,
# click to cut it. No slide step afterwards like the built-in Loop Cut.

ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")
OP_IDNAME = "keyops.fast_loop_cut"
ADJUST_IDNAME = "keyops.fast_loop_cut_adjust"
MODIFIERS_IDNAME = "keyops.fast_loop_cut_modifiers"
TOOL_IDNAME = "edit_mesh.fast_loop_cut_workspace_tool"

COLOR_PREVIEW = (0.9608, 0.9451, 0.3020, 1.0)
COLOR_POINT = (1.0, 1.0, 1.0, 1.0)
FACTOR_EPSILON = 1e-4

# Per-object BVH cache, cleared whenever the depsgraph updates (mesh edited/moved).
_bvh_cache = {}
# Preview geometry in world space, written by the gizmo hover test and read by its draw.
_preview = {"loops": [], "point": None}


@persistent
def _clear_cache_handler(scene, depsgraph):
    _bvh_cache.clear()


EDGE_FLOW_OP_TYPE = "MESH_OT_set_mesh_edge_flow"


def edge_flow_available():
    """True when the Set Edge Flow operator (mesh.set_mesh_edge_flow) is registered."""
    return hasattr(bpy.types, EDGE_FLOW_OP_TYPE)


def get_tool_props(context):
    """Operator properties stored on the active Fast Loop Cut tool, or None."""
    workspace = getattr(context, "workspace", None)
    if workspace is None:
        return None
    try:
        tool = workspace.tools.from_space_view3d_mode('EDIT_MESH', create=False)
        if tool is not None and tool.idname == TOOL_IDNAME:
            return tool.operator_properties(OP_IDNAME)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    return None


# Modifier keys held right now. Holding one flips its setting for as long as it's held:
# Shift = Center, Alt = Even, Ctrl = Edge Flow.
_held = {"shift": False, "alt": False, "ctrl": False}
MODIFIER_KEYS = {
    'LEFT_SHIFT': "shift", 'RIGHT_SHIFT': "shift",
    'LEFT_ALT': "alt", 'RIGHT_ALT': "alt",
    'LEFT_CTRL': "ctrl", 'RIGHT_CTRL': "ctrl",
}


def sync_held(event):
    """Update _held from an event. Returns True when the held state changed."""
    new = {"shift": event.shift, "alt": event.alt, "ctrl": event.ctrl}
    key = MODIFIER_KEYS.get(event.type)
    if key is not None and event.value in {'PRESS', 'RELEASE'}:
        new[key] = event.value == 'PRESS'
    changed = new != _held
    _held.update(new)
    return changed


def effective_settings(even, snap_center, use_edge_flow):
    """Apply held modifiers on top of the toggled settings. A held key wins over a toggle."""
    if _held["alt"]:
        even = not even
    if _held["shift"]:
        snap_center = not snap_center
    if _held["ctrl"]:
        use_edge_flow = not use_edge_flow
    # Even and Center are exclusive; the one that's being held takes priority.
    if even and snap_center:
        if _held["alt"] and not _held["shift"]:
            snap_center = False
        else:
            even = False
    return even, snap_center, use_edge_flow


def get_tool_settings(context):
    """Number of cuts / even / center for the preview: tool settings plus held modifiers."""
    props = get_tool_props(context)
    if props is None:
        even, center, _flow = effective_settings(False, False, False)
        return 1, even, center
    even, center, _flow = effective_settings(props.even, props.snap_center, props.use_edge_flow)
    return props.number_cuts, even, center


def update_preview(context, mouse):
    """Recompute the hover preview at mouse (region coords) and redraw if it changed."""
    number_cuts, even, snap_center = get_tool_settings(context)
    loops, points = [], None
    try:
        hover = find_hover(context, mouse)
        if hover is not None:
            loops, points = preview_loops(hover, number_cuts, even, snap_center)
    except (ReferenceError, ValueError, IndexError):
        pass

    if loops != _preview["loops"]:
        _preview["loops"] = loops
        _preview["point"] = points
        if context.region is not None:
            context.region.tag_redraw()


def get_bvh(obj, bm):
    """BVH of the visible faces of an edit mesh, plus a map BVH index -> face index."""
    key = (len(bm.verts), len(bm.edges), len(bm.faces))
    cached = _bvh_cache.get(obj.name)
    if cached is not None and cached[0] == key:
        return cached[1], cached[2]

    bm.verts.index_update()
    bm.faces.index_update()
    coords = [v.co.copy() for v in bm.verts]
    polys = []
    face_map = []
    for f in bm.faces:
        if f.hide:
            continue
        polys.append([v.index for v in f.verts])
        face_map.append(f.index)

    bvh = BVHTree.FromPolygons(coords, polys, all_triangles=False) if polys else None
    _bvh_cache[obj.name] = (key, bvh, face_map)
    return bvh, face_map


FAN_MIN_TRIANGLES = 3


def _triangle_count(vert):
    return sum(1 for f in vert.link_faces if len(f.verts) == 3 and not f.hide)


def _fan_pole(edge):
    """The vertex of edge that is the centre of a triangle fan, or None.

    The pole must touch at least FAN_MIN_TRIANGLES triangles and strictly more than the
    other vertex, so a ring only passes through triangles that actually fan around a point
    (cylinder caps, poles) and stops at stray triangles like the built-in loop cut.
    """
    a, b = edge.verts
    count_a, count_b = _triangle_count(a), _triangle_count(b)
    if max(count_a, count_b) < FAN_MIN_TRIANGLES or count_a == count_b:
        return None
    return a if count_a > count_b else b


def _next_ring_loop(loop):
    """Loop on the edge the ring continues through after crossing loop.face, or None.

    Quads continue through the opposite edge. Triangles in a fan continue through the
    other edge touching the fan pole, so the cut circles around the pole.
    """
    face = loop.face
    if face is None or face.hide:
        return None
    side_count = len(face.verts)
    if side_count == 4:
        return loop.link_loop_next.link_loop_next
    if side_count == 3:
        pole = _fan_pole(loop.edge)
        if pole is None:
            return None
        return loop.link_loop_prev if pole == loop.vert else loop.link_loop_next
    return None


def _walk(loop, start_vert, start_edge, visited):
    """Walk an edge ring from start_edge through loop.face.

    Returns (edges, faces, closed); edges are (edge, start_vert) pairs where every
    start_vert sits on the same side of the ring as the original start_vert.
    """
    edges, faces = [], []
    l, s = loop, start_vert
    while True:
        face = l.face
        opp = _next_ring_loop(l)
        if opp is None:
            return edges, faces, False

        # Works for quads and fan triangles: opp.link_loop_next.vert is the vert of the
        # next edge that sits beside l.vert (for triangles it is the pole when l.vert is).
        s_next = opp.link_loop_next.vert if l.vert == s else opp.vert
        e_next = opp.edge

        if e_next == start_edge:
            faces.append(face)
            return edges, faces, True
        if e_next in visited or e_next.hide:
            return edges, faces, False

        visited.add(e_next)
        faces.append(face)
        edges.append((e_next, s_next))

        nxt = opp.link_loop_radial_next
        if nxt == opp or nxt.link_loop_radial_next != opp:  # boundary or non-manifold
            return edges, faces, False
        l, s = nxt, s_next


def build_ring(edge, start_vert):
    """Edge ring through edge. ring[i] and ring[i+1] share faces[i] (faces[-1] wraps when closed)."""
    link_loops = list(edge.link_loops)
    if not link_loops or len(link_loops) > 2:
        return None

    visited = {edge}
    fw_edges, fw_faces, closed = _walk(link_loops[0], start_vert, edge, visited)
    bw_edges, bw_faces = [], []
    if not closed and len(link_loops) == 2:
        bw_edges, bw_faces, _closed = _walk(link_loops[1], start_vert, edge, visited)

    ring = list(reversed(bw_edges)) + [(edge, start_vert)] + fw_edges
    faces = list(reversed(bw_faces)) + fw_faces
    if not faces:
        return None
    return ring, faces, closed, len(bw_edges)


def compute_factors(ring, hover_index, t, number_cuts, even, snap_center):
    """Per ring edge, the ascending list of cut factors measured from that edge's start vert."""
    if number_cuts > 1:
        step = 1.0 / (number_cuts + 1)
        factors = [step * (i + 1) for i in range(number_cuts)]
        return [factors for _ in ring]

    if snap_center:
        return [[0.5] for _ in ring]

    t = min(max(t, FACTOR_EPSILON), 1.0 - FACTOR_EPSILON)
    if not even:
        return [[t] for _ in ring]

    # Even: keep the same distance to the edge loop the cursor is closest to.
    hover_edge = ring[hover_index][0]
    from_start = t <= 0.5
    distance = hover_edge.calc_length() * (t if from_start else 1.0 - t)

    result = []
    for e, _s in ring:
        length = e.calc_length()
        f = distance / length if length > 0 else 0.5
        f = min(max(f, FACTOR_EPSILON), 1.0 - FACTOR_EPSILON)
        result.append([f if from_start else 1.0 - f])
    return result


def _dist_to_segment_2d(p, a, b):
    ab = b - a
    denom = ab.length_squared
    if denom == 0.0:
        return (p - a).length
    t = min(max((p - a).dot(ab) / denom, 0.0), 1.0)
    return (p - (a + ab * t)).length


def find_hover(context, mouse):
    """Find the edge (and position along it) under the mouse. Returns a dict or None."""
    region = context.region
    rv3d = context.region_data
    if region is None or rv3d is None:
        return None

    mouse = Vector(mouse)
    origin = region_2d_to_origin_3d(region, rv3d, mouse)
    direction = region_2d_to_vector_3d(region, rv3d, mouse)

    objects = [o for o in getattr(context, "objects_in_mode", []) if o.type == 'MESH']
    if not objects and context.edit_object and context.edit_object.type == 'MESH':
        objects = [context.edit_object]

    best = None
    for obj in objects:
        bm = bmesh.from_edit_mesh(obj.data)
        bvh, face_map = get_bvh(obj, bm)
        if bvh is None:
            continue
        mat_inv = obj.matrix_world.inverted_safe()
        o_local = mat_inv @ origin
        d_local = (mat_inv.to_3x3() @ direction).normalized()
        loc, _normal, index, _dist = bvh.ray_cast(o_local, d_local)
        if loc is None:
            continue
        dist_world = (obj.matrix_world @ loc - origin).length
        if best is None or dist_world < best[0]:
            best = (dist_world, obj, bm, loc, face_map[index])

    if best is None:
        return None

    _dist, obj, bm, loc, face_index = best
    bm.faces.ensure_lookup_table()
    face = bm.faces[face_index]
    mat = obj.matrix_world

    # Nearest edge of the face under the cursor, in screen space.
    best_edge, best_dist = None, None
    for e in face.edges:
        a = location_3d_to_region_2d(region, rv3d, mat @ e.verts[0].co)
        b = location_3d_to_region_2d(region, rv3d, mat @ e.verts[1].co)
        if a is None or b is None:
            continue
        d = _dist_to_segment_2d(mouse, a, b)
        if best_dist is None or d < best_dist:
            best_edge, best_dist = e, d
    if best_edge is None:
        return None

    start = best_edge.verts[0]
    _point, t = intersect_point_line(loc, start.co, best_edge.verts[1].co)
    t = min(max(t, 0.0), 1.0)

    ring_data = build_ring(best_edge, start)
    if ring_data is None:
        return None
    ring, faces, closed, hover_index = ring_data
    return {
        "obj": obj,
        "bm": bm,
        "edge": best_edge,
        "start": start,
        "t": t,
        "ring": ring,
        "faces": faces,
        "closed": closed,
        "hover_index": hover_index,
    }


def preview_loops(hover, number_cuts, even, snap_center):
    """World space line segments (pairs) for every loop that would be cut."""
    ring = hover["ring"]
    mat = hover["obj"].matrix_world
    factors = compute_factors(ring, hover["hover_index"], hover["t"], number_cuts, even, snap_center)

    loops = []
    for k in range(len(factors[0])):
        points = []
        for (e, s), fl in zip(ring, factors):
            points.append(mat @ s.co.lerp(e.other_vert(s).co, fl[k]))
        if hover["closed"]:
            points.append(points[0])
        segments = []
        for a, b in zip(points, points[1:]):
            segments.extend((a, b))
        loops.append(segments)

    hover_points = [mat @ ring[hover["hover_index"]][1].co.lerp(
        ring[hover["hover_index"]][0].other_vert(ring[hover["hover_index"]][1]).co, f)
        for f in factors[hover["hover_index"]]]
    return loops, hover_points


def cut_ring(bm, ring, faces, closed, factors):
    """Split every ring edge at its factors and connect the new verts across the ring faces."""
    new_verts = []
    for (e, s), fl in zip(ring, factors):
        other = e.other_vert(s)
        s_co, o_co = s.co.copy(), other.co.copy()
        cur_edge, cur_start, prev = e, s, 0.0
        verts = []
        for f in fl:
            local = (f - prev) / (1.0 - prev)
            new_edge, new_vert = bmesh.utils.edge_split(cur_edge, cur_start, local)
            new_vert.co = s_co.lerp(o_co, f)
            if other in new_edge.verts:
                cur_edge = new_edge
            cur_start, prev = new_vert, f
            verts.append(new_vert)
        new_verts.append(verts)

    new_edges = []
    count = len(ring)
    for i in range(len(faces)):
        verts_a = new_verts[i]
        verts_b = new_verts[(i + 1) % count]
        for va, vb in zip(verts_a, verts_b):
            if any(vb in e.verts for e in va.link_edges):
                continue
            face = next((f for f in va.link_faces if vb in f.verts), None)
            if face is None:
                continue
            _new_face, new_loop = bmesh.utils.face_split(face, va, vb)
            new_edges.append(new_loop.edge)
    return new_verts, new_edges


def draw_edge_flow_settings(layout, props, show_options=True):
    """Edge Flow toggle (and tension/iterations when show_options), only when Set Edge Flow exists."""
    if not edge_flow_available():
        return
    layout.prop(props, "use_edge_flow")
    if show_options and props.use_edge_flow:
        col = layout.column(align=True)
        col.prop(props, "flow_tension")
        col.prop(props, "flow_iterations")


class FastLoopCut(bpy.types.Operator):
    """Cut a loop exactly where the cursor is hovering"""
    bl_idname = OP_IDNAME
    bl_label = "Fast Loop Cut"
    bl_options = {'REGISTER', 'UNDO'}

    number_cuts: IntProperty(name="Number of Cuts", description="Number of loops to cut. More than one spreads them evenly", default=1, min=1, soft_max=32, max=256)  # type: ignore
    even: BoolProperty(name="Even", description="Keep the same distance to the closest edge loop along the whole ring", default=False)  # type: ignore
    snap_center: BoolProperty(name="Center", description="Always cut in the middle of the edges", default=False)  # type: ignore
    use_edge_flow: BoolProperty(name="Edge Flow", description="Run Set Edge Flow on the new loops so they follow the surface curvature", default=False)  # type: ignore
    flow_tension: IntProperty(name="Tension", description="Set Edge Flow tension", default=180, min=-500, max=500)  # type: ignore
    flow_iterations: IntProperty(name="Iterations", description="Set Edge Flow iterations", default=8, min=1, soft_max=32)  # type: ignore
    factor: FloatProperty(name="Position", description="Position of the cut along the hovered edge", default=0.5, min=0.0, max=1.0, subtype='FACTOR', options={'SKIP_SAVE'})  # type: ignore
    object_name: StringProperty(options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore
    edge_index: IntProperty(default=-1, options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore
    start_index: IntProperty(default=-1, options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        sync_held(event)
        props = get_tool_props(context)
        if props is not None:
            # Read the tool's toggles directly and apply the held modifiers on top, so a
            # held key only affects this cut and never sticks to the tool settings.
            self.number_cuts = props.number_cuts
            self.flow_tension = props.flow_tension
            self.flow_iterations = props.flow_iterations
            self.even, self.snap_center, self.use_edge_flow = effective_settings(
                props.even, props.snap_center, props.use_edge_flow)

        hover = find_hover(context, (event.mouse_region_x, event.mouse_region_y))
        if hover is None:
            return {'PASS_THROUGH'}
        bm = hover["bm"]
        bm.verts.index_update()
        bm.edges.index_update()
        self.object_name = hover["obj"].name
        self.edge_index = hover["edge"].index
        self.start_index = hover["start"].index
        self.factor = hover["t"]
        return self.execute(context)

    def execute(self, context):
        obj = bpy.data.objects.get(self.object_name)
        if obj is None or obj.type != 'MESH' or obj.mode != 'EDIT':
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        if not (0 <= self.edge_index < len(bm.edges) and 0 <= self.start_index < len(bm.verts)):
            return {'CANCELLED'}
        edge = bm.edges[self.edge_index]
        start = bm.verts[self.start_index]
        if start not in edge.verts:
            return {'CANCELLED'}

        ring_data = build_ring(edge, start)
        if ring_data is None:
            return {'CANCELLED'}
        ring, faces, closed, hover_index = ring_data
        factors = compute_factors(ring, hover_index, self.factor, self.number_cuts, self.even, self.snap_center)

        for v in bm.verts:
            v.select = False
        for e in bm.edges:
            e.select = False
        for f in bm.faces:
            f.select = False

        new_verts, new_edges = cut_ring(bm, ring, faces, closed, factors)

        for e in new_edges:
            e.select_set(True)
        for verts in new_verts:
            for v in verts:
                v.select_set(True)
        bm.select_flush_mode()

        bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)

        if self.use_edge_flow and new_edges:
            self.apply_edge_flow(context, obj)

        _bvh_cache.pop(obj.name, None)
        _preview["loops"] = []
        _preview["point"] = None
        return {'FINISHED'}

    def apply_edge_flow(self, context, obj):
        """Run mesh.set_mesh_edge_flow on the freshly cut (selected) loops of obj only."""
        if not edge_flow_available():
            return
        with context.temp_override(
            object=obj,
            active_object=obj,
            edit_object=obj,
            selected_objects=[obj],
            selected_editable_objects=[obj],
        ):
            if bpy.ops.mesh.set_mesh_edge_flow.poll():
                bpy.ops.mesh.set_mesh_edge_flow(tension=self.flow_tension, iterations=self.flow_iterations)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "number_cuts")
        col = layout.column()
        col.active = self.number_cuts == 1
        col.prop(self, "even")
        col.prop(self, "snap_center")
        if not self.snap_center and self.number_cuts == 1:
            col.prop(self, "factor")
        draw_edge_flow_settings(layout, self)


class FastLoopCutAdjust(bpy.types.Operator):
    """Change the Fast Loop Cut tool settings while hovering"""
    bl_idname = "keyops.fast_loop_cut_adjust"
    bl_label = "Fast Loop Cut Adjust"
    bl_options = {'INTERNAL'}

    action: EnumProperty(
        name="Action",
        items=[
            ('INCREASE', "More Cuts", "Add one cut"),
            ('DECREASE', "Fewer Cuts", "Remove one cut"),
            ('TOGGLE_EVEN', "Toggle Even", "Toggle Even"),
            ('TOGGLE_CENTER', "Toggle Center", "Toggle Center"),
            ('TOGGLE_EDGE_FLOW', "Toggle Edge Flow", "Toggle Set Edge Flow after cutting"),
        ],
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and get_tool_props(context) is not None

    def invoke(self, context, event):
        props = get_tool_props(context)
        if props is None:
            return {'PASS_THROUGH'}

        if self.action == 'INCREASE':
            props.number_cuts = min(props.number_cuts + 1, 256)
            msg = f"Cuts: {props.number_cuts}"
        elif self.action == 'DECREASE':
            props.number_cuts = max(props.number_cuts - 1, 1)
            msg = f"Cuts: {props.number_cuts}"
        elif self.action == 'TOGGLE_EVEN':
            props.even = not props.even
            if props.even:
                props.snap_center = False
            msg = f"Even: {'On' if props.even else 'Off'}"
        elif self.action == 'TOGGLE_CENTER':
            props.snap_center = not props.snap_center
            if props.snap_center:
                props.even = False
            msg = f"Center: {'On' if props.snap_center else 'Off'}"
        else:
            if not edge_flow_available():
                return {'PASS_THROUGH'}
            props.use_edge_flow = not props.use_edge_flow
            msg = f"Edge Flow: {'On' if props.use_edge_flow else 'Off'}"

        # Force the preview to rebuild with the new settings at the current cursor.
        _preview["loops"] = None
        update_preview(context, (event.mouse_region_x, event.mouse_region_y))
        for area in context.screen.areas if context.screen else ():
            if area.type in {'VIEW_3D', 'STATUSBAR'}:
                area.tag_redraw()
        self.report({'INFO'}, msg)
        return {'FINISHED'}


_icon_names = None


def _icon(name):
    """name if Blender has that icon, else 'NONE' (event icons vary between versions)."""
    global _icon_names
    if _icon_names is None:
        _icon_names = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())
    return name if name in _icon_names else 'NONE'


# Modifier key icons are drawn wider than a normal square icon and clip without extra room.
WIDE_KEY_ICONS = {'EVENT_SHIFT', 'EVENT_CTRL', 'EVENT_ALT', 'EVENT_OS', 'EVENT_TAB', 'EVENT_SPACEKEY', 'EVENT_RETURN'}


def _status_item(layout, keys, text):
    """One hint: key icons (or key text when no icon exists) followed by a label."""
    row = layout.row(align=True)
    for key in keys:
        icon = _icon(key)
        if icon == 'NONE':
            row.label(text=key.removeprefix("EVENT_").title())
            continue
        cell = row.row(align=True)
        if icon in WIDE_KEY_ICONS:
            cell.ui_units_x = 1.4
        cell.label(text="", icon=icon)
    if text:
        row.label(text=text)
    layout.separator(factor=1.0)


def _on_off(value):
    return "On" if value else "Off"


def draw_status_bar(header, context):
    """Status bar hints for Fast Loop Cut, showing the live state of every setting."""
    props = get_tool_props(context) if context.mode == 'EDIT_MESH' else None
    if props is None:
        # Tool switched off or left edit mode: give Blender its status bar back.
        bpy.app.timers.register(clear_status_bar, first_interval=0.0)
        return

    number_cuts, even, center = get_tool_settings(context)
    flow = effective_settings(props.even, props.snap_center, props.use_edge_flow)[2]

    layout = header.layout
    _status_item(layout, ['MOUSE_LMB'], "Cut")
    _status_item(layout, ['MOUSE_MMB_SCROLL'], f"Cuts: {number_cuts}")
    _status_item(layout, ['EVENT_PLUS', 'EVENT_MINUS'], "")
    _status_item(layout, ['EVENT_E', 'EVENT_ALT'], f"Even: {_on_off(even)}")
    _status_item(layout, ['EVENT_C', 'EVENT_SHIFT'], f"Center: {_on_off(center)}")
    if edge_flow_available():
        _status_item(layout, ['EVENT_F', 'EVENT_CTRL'], f"Edge Flow: {_on_off(flow)}")
    layout.label(text="Tap to toggle, hold modifier to flip")


def ensure_status_bar(context):
    """Install the hints unless they're already the status bar's draw function."""
    from bl_ui.space_statusbar import STATUSBAR_HT_header
    if STATUSBAR_HT_header.draw is draw_status_bar or context.workspace is None:
        return
    context.workspace.status_text_set(draw_status_bar)
    redraw_status_bar(context)


def clear_status_bar():
    """Restore Blender's own status bar if Fast Loop Cut's hints are installed. Timer safe."""
    from bl_ui.space_statusbar import STATUSBAR_HT_header
    if STATUSBAR_HT_header.draw is not draw_status_bar:
        return None
    wm = bpy.context.window_manager
    for window in wm.windows if wm else ():
        window.workspace.status_text_set(None)
        for area in window.screen.areas:
            if area.type == 'STATUSBAR':
                area.tag_redraw()
        break  # status_text_set restores the shared draw function; once is enough
    return None


def redraw_status_bar(context):
    screen = getattr(context, "screen", None)
    for area in screen.areas if screen else ():
        if area.type == 'STATUSBAR':
            area.tag_redraw()


class FastLoopCutModifiers(bpy.types.Operator):
    """Track held Shift/Alt/Ctrl so the preview shows Center/Even while they're held"""
    bl_idname = MODIFIERS_IDNAME
    bl_label = "Fast Loop Cut Modifiers"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        if sync_held(event):
            _preview["loops"] = None  # force a rebuild with the new modifier state
            update_preview(context, (event.mouse_region_x, event.mouse_region_y))
            redraw_status_bar(context)
        return {'PASS_THROUGH'}


class FastLoopCutPreviewGizmo(bpy.types.Gizmo):
    """Invisible gizmo: uses hover testing to update and draw the loop preview."""
    bl_idname = "KEYOPS_GT_fast_loop_cut_preview"

    def test_select(self, context, location):
        update_preview(context, location)
        return -1

    def draw(self, context):
        # The gizmo only draws while the tool is active, so this is where the hints go up.
        ensure_status_bar(context)
        if not _preview["loops"]:
            return
        gpu.state.depth_test_set('NONE')
        # Match the built-in Loop Cut preview: 1px, scaled with the UI's pixel size.
        line_width = context.preferences.system.pixel_size
        for segments in _preview["loops"]:
            DrawUtils.draw_lines(segments, COLOR_PREVIEW, line_width=line_width)
        if _preview["point"]:
            DrawUtils.draw_points(_preview["point"], COLOR_POINT, point_size=6.0)
        gpu.state.blend_set('NONE')


class FastLoopCutGizmoGroup(bpy.types.GizmoGroup):
    bl_idname = "KEYOPS_GGT_fast_loop_cut"
    bl_label = "Fast Loop Cut Preview"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'EXCLUDE_MODAL'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'EDIT_MESH':
            return False
        tool = context.workspace.tools.from_space_view3d_mode('EDIT_MESH', create=False)
        return tool is not None and tool.idname == TOOL_IDNAME

    def setup(self, context):
        self.preview = self.gizmos.new(FastLoopCutPreviewGizmo.bl_idname)


class WorkSpaceFastLoopCut(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'EDIT_MESH'
    bl_idname = TOOL_IDNAME
    bl_label = "Fast Loop Cut"
    bl_description = (
        "Hover an edge to preview a loop at the cursor, click to cut it.\n"
        "+/- or Scroll: number of cuts.\n"
        "Toggle: E Even, C Center, F Edge Flow.\n"
        "Hold: Alt Even, Shift Center, Ctrl Edge Flow"
    )
    bl_icon = os.path.join(ICON_DIR, "ops.mesh.fast_loop_cut")
    bl_widget = FastLoopCutGizmoGroup.bl_idname
    bl_keymap = (
        (OP_IDNAME, {"type": 'LEFTMOUSE', "value": 'PRESS', "any": True}, None),
        (MODIFIERS_IDNAME, {"type": 'MOUSEMOVE', "value": 'ANY', "any": True}, None),
        *((MODIFIERS_IDNAME, {"type": key, "value": value, "any": True}, None)
          for key in MODIFIER_KEYS for value in ('PRESS', 'RELEASE')),
        (ADJUST_IDNAME, {"type": 'WHEELUPMOUSE', "value": 'PRESS'}, {"properties": [("action", 'INCREASE')]}),
        (ADJUST_IDNAME, {"type": 'WHEELDOWNMOUSE', "value": 'PRESS'}, {"properties": [("action", 'DECREASE')]}),
        (ADJUST_IDNAME, {"type": 'NUMPAD_PLUS', "value": 'PRESS'}, {"properties": [("action", 'INCREASE')]}),
        (ADJUST_IDNAME, {"type": 'NUMPAD_MINUS', "value": 'PRESS'}, {"properties": [("action", 'DECREASE')]}),
        (ADJUST_IDNAME, {"type": 'EQUAL', "value": 'PRESS'}, {"properties": [("action", 'INCREASE')]}),
        (ADJUST_IDNAME, {"type": 'MINUS', "value": 'PRESS'}, {"properties": [("action", 'DECREASE')]}),
        (ADJUST_IDNAME, {"type": 'E', "value": 'PRESS'}, {"properties": [("action", 'TOGGLE_EVEN')]}),
        (ADJUST_IDNAME, {"type": 'C', "value": 'PRESS'}, {"properties": [("action", 'TOGGLE_CENTER')]}),
        (ADJUST_IDNAME, {"type": 'F', "value": 'PRESS'}, {"properties": [("action", 'TOGGLE_EDGE_FLOW')]}),
    )

    def draw_settings(context, layout, tool):
        props = tool.operator_properties(OP_IDNAME)
        layout.prop(props, "number_cuts")
        row = layout.row()
        row.active = props.number_cuts == 1
        row.prop(props, "even")
        row.prop(props, "snap_center")
        draw_edge_flow_settings(layout, props, show_options=False)


classes = (FastLoopCut, FastLoopCutAdjust, FastLoopCutModifiers, FastLoopCutPreviewGizmo, FastLoopCutGizmoGroup)
registered_fast_loop_cut_keymaps = []


def register_fast_loop_cut_keymaps():
    wm = bpy.context.window_manager
    if wm.keyconfigs.addon is None:
        return
    km = wm.keyconfigs.addon.keymaps.new(name='Mesh', space_type='EMPTY')
    kmi = km.keymap_items.new('wm.tool_set_by_id', 'R', 'PRESS', alt=True)
    kmi.properties.name = TOOL_IDNAME
    registered_fast_loop_cut_keymaps.append((km, kmi))


def register_fast_loop_cut():
    from .merge_tool import remove_stale_tool

    for cls in classes:
        bpy.utils.register_class(cls)

    try:
        if not hasattr(WorkSpaceFastLoopCut, "_bl_tool"):
            remove_stale_tool(WorkSpaceFastLoopCut)
            bpy.utils.register_tool(WorkSpaceFastLoopCut, after={"builtin.bevel"}, separator=False, group=False)
    except Exception as e:
        print(f"Failed to register WorkSpaceFastLoopCut: {e}")

    if _clear_cache_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_clear_cache_handler)

    if not registered_fast_loop_cut_keymaps:
        register_fast_loop_cut_keymaps()


def unregister_fast_loop_cut():
    from ..utils.pref_utils import clear_registered_keymaps
    clear_registered_keymaps(registered_fast_loop_cut_keymaps)

    if _clear_cache_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_clear_cache_handler)
    _bvh_cache.clear()
    _preview["loops"] = []
    _preview["point"] = None
    clear_status_bar()

    try:
        if hasattr(WorkSpaceFastLoopCut, "_bl_tool"):
            bpy.utils.unregister_tool(WorkSpaceFastLoopCut)
    except Exception as e:
        print(f"Failed to unregister WorkSpaceFastLoopCut: {e}")

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
