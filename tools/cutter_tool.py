import itertools
import math
import os

import bmesh
import bpy
import gpu
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d,
    region_2d_to_origin_3d,
    region_2d_to_vector_3d,
)
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector
from mathutils.geometry import (
    intersect_line_line,
    intersect_line_plane,
    intersect_point_line,
    tessellate_polygon,
)

from ..utils.pref_utils import get_icon
from ..utils.utilities import safe_icon
from ..operators.add_modifier import (
    BOOLEAN_OPERATION_ITEMS,
    add_boolean_modifiers,
    get_cutter_collection,
    move_to_cutter_collection,
    resolve_boolean_solver,
)

# Cutter: draw a box / circle / ngon on a surface (or the grid floor) and boolean it
# into the targets. The preview is a GPU overlay; with "Live" on (the default) the
# boolean is also shown while drawing. In Edit Mode the cut is applied to the mesh.
#
# The boolean setup itself (modifiers, solver, Cutters collection, slice) lives in
# operators/add_modifier.py and is shared with the Add Boolean operator.

ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")
OP_IDNAME = "keyops.cutter"
TOOL_IDNAME = "object.keyops_cutter_tool"
EDIT_TOOL_IDNAME = "mesh.keyops_cutter_tool"

OPERATION_COLORS = {
    'DIFFERENCE': (1.0, 0.32, 0.30),
    'UNION': (0.35, 0.90, 0.45),
    'INTERSECT': (0.35, 0.65, 1.0),
    'SLICE': (1.0, 0.85, 0.30),
    'ADD': (0.72, 0.72, 0.72),
}
# The booleans plus Add, which makes a new object from the shape instead of cutting
OPERATION_ITEMS = BOOLEAN_OPERATION_ITEMS + (('ADD', 'Add', 'Add a new mesh object from the shape, no boolean'),)
OPERATION_NAMES = {i[0]: i[1] for i in OPERATION_ITEMS}
OPERATION_ORDER = [i[0] for i in OPERATION_ITEMS]  # X cycles through these
ADD_OBJECT_NAMES = {'BOX': "Box", 'CIRCLE': "Cylinder", 'NGON': "Prism"}
SHAPE_KEYS = {'B': 'BOX', 'C': 'CIRCLE', 'N': 'NGON'}  # B on a box toggles the bevel instead
MIRROR_KEYS = {'ONE': "mirror_x", 'TWO': "mirror_y", 'THREE': "mirror_z"}
PLUS_KEYS = {'WHEELUPMOUSE', 'NUMPAD_PLUS', 'PLUS', 'EQUAL'}
MINUS_KEYS = {'WHEELDOWNMOUSE', 'NUMPAD_MINUS', 'MINUS'}
# Operator settings mirrored from the tool, so the D popup and shortcuts edit one place
SETTINGS = ("operation", "shape", "align", "solver", "segments", "snap_increment", "live", "apply",
            "bevel", "bevel_width", "bevel_segments", "bevel_profile", "mirror_x", "mirror_y", "mirror_z")

SHAPE_ITEMS = (
    ('BOX', "Box", "Drag a rectangle", 'MESH_PLANE', 0),
    ('CIRCLE', "Circle", "Drag an ellipse", 'MESH_CIRCLE', 1),
    ('NGON', "Ngon", "Click points, Enter / Space or click the first point to close", 'MESH_DATA', 2),
)
ALIGN_ITEMS = (
    ('VIEW', "View", "Align the shape to the view"),
    ('EDGE', "Edge", "Align the shape to the closest edge of the face under the cursor"),
)
# Settings the mouse drags with B (bevel width) and P (bevel profile): (min, max)
MOUSE_ADJUST_RANGES = {"bevel_width": (0.01, 0.5), "bevel_profile": (0.0, 1.0)}
MOUSE_ADJUST_PIXELS = 600.0  # mouse pixels for a change of 1.0
SOLVER_ITEMS = (
    ('FAST', "Fast", ""),
    ('EXACT', "Exact", ""),
    ('MANIFOLD', "Manifold", ""),
)

MIN_DEPTH = 1e-4  # smallest depth into the surface, depth can't go toward the camera
TARGET_SEPARATOR = "\x1f"  # between object names in the stored target list
CLICK_DRAG_THRESHOLD = 4.0  # px, below this a press + release is treated as a select click
NGON_CLOSE_RADIUS = 12.0  # px, clicking this close to the first point closes the ngon


# --- Small helpers ----------------------------------------------------------

def _tool_props(context):
    """Settings of the active Cutter tool (Object Mode and Edit Mode each have their own)."""
    mode = 'EDIT_MESH' if context.mode == 'EDIT_MESH' else 'OBJECT'
    try:
        tool = context.workspace.tools.from_space_view3d_mode(mode, create=False)
        if tool is not None and tool.idname in {TOOL_IDNAME, EDIT_TOOL_IDNAME}:
            return tool.operator_properties(OP_IDNAME)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    return None


def operation_icon(operation):
    """Toolkit icon id for an operation (the boolean icons, a cube for Add)."""
    return get_icon("mesh_cube" if operation == 'ADD' else operation.lower())


def _is_cut_target(obj, cutter_collection):
    return (
        obj is not None
        and obj.type == 'MESH'
        and obj.display_type not in {'WIRE', 'BOUNDS'}
        and (cutter_collection is None or cutter_collection not in obj.users_collection)
    )


def box_points(center, hx, hy, bevel=0.0, segments=1, profile=0.5):
    """CCW rectangle around center. With a bevel (a share of the shorter side, up to 0.5 for
    fully round ends) each corner is replaced by segments + 1 points.

    profile works like the Bevel modifier's Shape: 0.5 is round, 0.25 a straight chamfer,
    lower curves inward, higher bulges out toward the corner."""
    radius = bevel * 2.0 * min(hx, hy)
    exponent = 2.0 / (2.0 ** ((profile - 0.25) / 0.25))  # superellipse: 2 / 1 / 0.5 for round / flat / concave
    points = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        corner = center + Vector((sx * hx, sy * hy))
        if radius < 1e-9:
            points.append(corner)
            continue
        # Quarter superellipse around the pivot, from the edge coming in to the edge going out
        pivot = corner - Vector((sx, sy)) * radius
        for i in range(segments + 1):
            t = i / segments * math.pi / 2
            if sx * sy < 0:
                t = math.pi / 2 - t  # these corners are reached along the horizontal edge first
            offset = Vector((sx * math.cos(t) ** exponent, sy * math.sin(t) ** exponent)) * radius
            points.append(pivot + offset)
    # A full bevel makes neighbouring arcs meet, drop the doubled points
    cleaned = [p for i, p in enumerate(points) if (p - points[i - 1]).length > 1e-9]
    return cleaned or points


def _world_bounds(points):
    """(min, max) corners of the axis aligned box around world points."""
    lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return lo, hi


def _bounds_overlap(a, b):
    return all(a[0][i] <= b[1][i] and b[0][i] <= a[1][i] for i in range(3))


def _object_bounds(obj):
    return _world_bounds([obj.matrix_world @ Vector(corner) for corner in obj.bound_box])


def _signed_area(points):
    area = 0.0
    for a, b in zip(points, points[1:] + points[:1]):
        area += a.x * b.y - b.x * a.y
    return area * 0.5


def _plane_matrix(origin, normal, x_axis, fallback_x):
    z = normal.normalized()
    x = x_axis - z * x_axis.dot(z)
    if x.length_squared < 1e-12:
        x = fallback_x - z * fallback_x.dot(z)
    if x.length_squared < 1e-12:
        x = z.orthogonal()
    x.normalize()
    y = z.cross(x)
    mat = Matrix((x, y, z)).transposed().to_4x4()
    mat.translation = origin
    return mat


def _ray_cast(context, depsgraph, origin, direction, cutter_collection):
    """First hit on a cuttable mesh, skipping wire cutters. Returns (location, normal, index, obj, matrix) or None."""
    scene = context.scene
    for _ in range(16):
        hit, loc, normal, index, obj, matrix = scene.ray_cast(depsgraph, origin, direction)
        if not hit:
            return None
        original = getattr(obj, "original", obj)
        if _is_cut_target(original, cutter_collection):
            return loc, normal, index, original, matrix
        origin = loc + direction * 1e-4
    return None


def _closest_axis(matrix, normal, direction):
    """The object axis (from matrix) lying in the plane of normal that best matches direction.
    Falls back to direction when every axis points along the normal."""
    flat_direction = direction - normal * direction.dot(normal)
    best, best_dot = direction, 0.0
    for i in range(3):
        axis = matrix.col[i].to_3d()
        axis -= normal * axis.dot(normal)
        if axis.length < 1e-6:
            continue
        axis.normalize()
        for candidate in (axis, -axis):
            dot = candidate.dot(flat_direction)
            if dot > best_dot:
                best, best_dot = candidate, dot
    return best


def _closest_edge_direction(obj, depsgraph, matrix, index, location):
    """World direction of the edge of the hit face closest to location, or None."""
    try:
        mesh = obj.evaluated_get(depsgraph).data
        poly = mesh.polygons[index]
    except (IndexError, AttributeError, ReferenceError):
        return None
    best, best_dist = None, None
    verts = mesh.vertices
    for a, b in poly.edge_keys:
        pa = matrix @ verts[a].co
        pb = matrix @ verts[b].co
        _p, t = intersect_point_line(location, pa, pb)
        t = min(max(t, 0.0), 1.0)
        d = (location - pa.lerp(pb, t)).length
        if best_dist is None or d < best_dist:
            best, best_dist = pb - pa, d
    return best


def ensure_screw_modifier(obj, segments):
    """Screw modifier that spins a side profile into a closed cylinder around local Z."""
    mod = next((m for m in obj.modifiers if m.type == 'SCREW'), None)
    if mod is None:
        mod = obj.modifiers.new(name="Screw", type='SCREW')
        mod.axis = 'Z'
        mod.angle = math.tau
        mod.screw_offset = 0.0
        mod.iterations = 1
        mod.use_merge_vertices = True
        mod.merge_threshold = 1e-5
        mod.use_normal_calculate = True
        mod.use_normal_flip = True  # the profile spins inside out otherwise, booleans need outward normals
        mod.use_smooth_shade = False
    mod.steps = segments
    mod.render_steps = segments
    # The spun caps are triangle fans, Planar Decimate turns each into one ngon. The angle stays
    # below the step between the sides (1.4 degrees at 256 segments), so the sides are kept.
    if not any(m.type == 'DECIMATE' for m in obj.modifiers):
        decimate = obj.modifiers.new(name="Decimate", type='DECIMATE')
        decimate.decimate_type = 'DISSOLVE'
        decimate.angle_limit = math.radians(0.5)
    return mod


def build_prism(points, z0, z1):
    """Verts and faces of a closed prism from a CCW 2D profile."""
    n = len(points)
    verts = [(p.x, p.y, z0) for p in points] + [(p.x, p.y, z1) for p in points]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return verts, faces


# --- Operator ---------------------------------------------------------------

class Cutter(bpy.types.Operator):
    """Draw a shape and boolean it into the selected objects, or the object under the cursor.
Add mode makes a new object from the shape instead"""
    bl_idname = OP_IDNAME
    bl_label = "Cutter Tool"
    bl_options = {'REGISTER', 'UNDO'}

    operation: EnumProperty(name="Operation", items=OPERATION_ITEMS, default='DIFFERENCE')  # type: ignore
    shape: EnumProperty(name="Shape", items=SHAPE_ITEMS, default='BOX')  # type: ignore
    align: EnumProperty(name="Align", items=ALIGN_ITEMS, default='VIEW')  # type: ignore
    solver: EnumProperty(name="Solver", items=SOLVER_ITEMS, default='FAST')  # type: ignore
    segments: IntProperty(name="Segments", description="Circle segments", default=32, min=3, max=256)  # type: ignore
    snap_increment: FloatProperty(name="Snap", description="Grid increment used while holding Ctrl", default=0.1, min=0.0001, soft_max=10.0, subtype='DISTANCE')  # type: ignore
    live: BoolProperty(name="Live", description="Show the boolean while drawing. Turn off for heavy meshes. Object Mode only", default=True)  # type: ignore
    apply: BoolProperty(name="Apply", description="Apply the boolean and delete the cutter when done. Always on in Edit Mode", default=False)  # type: ignore
    bevel: BoolProperty(name="Bevel", description="Bevel the corners of the box", default=False)  # type: ignore
    bevel_width: FloatProperty(name="Bevel Width", description="Bevel size as a share of the shorter side of the box", default=0.15, min=0.01, max=0.5, subtype='FACTOR')  # type: ignore
    bevel_segments: IntProperty(name="Bevel Segments", description="Segments per bevelled corner", default=4, min=1, max=64)  # type: ignore
    bevel_profile: FloatProperty(name="Bevel Profile", description="Shape of the bevel: 0.5 is round, 0.25 a straight chamfer, lower curves inward", default=0.5, min=0.0, max=1.0, subtype='FACTOR')  # type: ignore
    mirror_x: BoolProperty(name="Mirror X", description="Mirror the cutter across the X axis of the object it starts on", default=False)  # type: ignore
    mirror_y: BoolProperty(name="Mirror Y", description="Mirror the cutter across the Y axis of the object it starts on", default=False)  # type: ignore
    mirror_z: BoolProperty(name="Mirror Z", description="Mirror the cutter across the Z axis of the object it starts on", default=False)  # type: ignore
    parent: BoolProperty(name="Parent Boolean", description="Parent the cutter to the object it cuts", default=False, options={'SKIP_SAVE'})  # type: ignore
    depth_amount: FloatProperty(name="Depth", description="How far the cutter goes in, away from the view. In Add mode, how far the new object comes out of the surface, negative goes into it", default=0.5, soft_min=-100.0, soft_max=100.0, subtype='DISTANCE', options={'SKIP_SAVE'})  # type: ignore

    # The finished cut, stored so the redo panel can rebuild it in execute()
    plane_matrix: FloatVectorProperty(size=16, options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore
    outline: StringProperty(options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore
    target_names: StringProperty(options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore
    mirror_pivot: StringProperty(options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT', 'EDIT_MESH'} and context.area is not None and context.area.type == 'VIEW_3D'

    def draw(self, context):
        """Redo panel, laid out like the Add Boolean operator's."""
        layout = self.layout
        row = layout.row()
        row.label(icon_value=operation_icon(self.operation))
        row.prop(self, "operation", text="")
        is_add = self.operation == 'ADD'
        if not is_add:
            layout.label(text="Boolean Solver")
            layout.row().prop(self, "solver", expand=True)
            if context.mode == 'OBJECT':
                layout.prop(self, "parent")
        layout.separator()
        layout.prop(self, "depth_amount")
        if self.shape == 'CIRCLE':
            layout.prop(self, "segments")
        if self.shape == 'BOX':
            draw_bevel_settings(layout, self)
        row = layout.row(align=True)
        row.label(text="Mirror")
        row.prop(self, "mirror_x", text="X", toggle=True)
        row.prop(self, "mirror_y", text="Y", toggle=True)
        row.prop(self, "mirror_z", text="Z", toggle=True)
        if not is_add and context.mode == 'OBJECT':
            layout.prop(self, "apply")

    def execute(self, context):
        """Build the cut from the stored outline. Runs when confirming the modal and on redo."""
        names = [n for n in self.target_names.split(TARGET_SEPARATOR) if n]
        self.targets = [o for o in (bpy.data.objects.get(n) for n in names) if o is not None and o.type == 'MESH']
        is_add = self.operation == 'ADD'
        if not self.outline or (not self.targets and not is_add):
            return {'CANCELLED'}

        v = list(self.plane_matrix)
        self.plane = Matrix((v[0:4], v[4:8], v[8:12], v[12:16]))
        self._fixed_profile = self._profile_from_outline()
        if not self._fixed_profile:
            return {'CANCELLED'}
        self.phase = 'EXTRUDE'
        depth = self.depth_amount
        if abs(depth) < MIN_DEPTH:
            depth = math.copysign(MIN_DEPTH, depth)
        self.depth = depth if is_add else -abs(depth)  # negative Add depth goes into the surface
        self.cutter = None
        self.created = []
        self.mirror_object = bpy.data.objects.get(self.mirror_pivot) if self.mirror_pivot else None

        if context.mode == 'EDIT_MESH':
            return self._execute_edit_mode(context)

        self._create_cutter(context)
        self._write_cutter_mesh(self._fixed_profile, self.z_range(self._fixed_profile))

        for obj in context.selected_objects:
            obj.select_set(False)
        if self.apply and not is_add:
            self._apply(context)
        if self.cutter is not None:
            self.cutter.select_set(True)
            context.view_layer.objects.active = self.cutter
        else:
            for target in self.targets:
                target.select_set(True)
            context.view_layer.objects.active = self.targets[0]
        return {'FINISHED'}

    def _execute_edit_mode(self, context):
        """Edit Mode cuts are destructive: Add puts the shape into the edit mesh, booleans are applied."""
        profile = self._fixed_profile
        z_range = self.z_range(profile)
        if self.operation == 'ADD':
            self._add_to_edit_mesh(context.edit_object, profile, z_range)
            return {'FINISHED'}

        # Booleans are applied as modifiers, which needs Object Mode for a moment
        edit_objects = [o for o in context.objects_in_mode if o.type == 'MESH']
        active = context.view_layer.objects.active
        bpy.ops.object.mode_set(mode='OBJECT')
        self._create_cutter(context)
        self._write_cutter_mesh(profile, z_range)
        self._apply(context)
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in edit_objects:
            obj.select_set(True)
        context.view_layer.objects.active = active
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}

    def _add_to_edit_mesh(self, obj, profile, z_range):
        """Add mode in Edit Mode: build the shape (and its mirrored copies) into the mesh, selected."""
        bm = bmesh.from_edit_mesh(obj.data)
        for elements in (bm.verts, bm.edges, bm.faces):
            for element in elements:
                element.select = False
        center = self._profile_center()
        verts, faces = build_prism([p - center for p in profile], z_range[0], z_range[1])
        to_local = obj.matrix_world.inverted_safe()
        for mirror in self._mirror_matrices():
            matrix = to_local @ mirror @ self._cutter_matrix(center)
            flipped = matrix.determinant() < 0.0  # a mirrored copy would be inside out
            new_verts = [bm.verts.new(matrix @ Vector(co)) for co in verts]
            for face in faces:
                indices = reversed(face) if flipped else face
                bm.faces.new([new_verts[i] for i in indices]).select_set(True)
        bmesh.update_edit_mesh(obj.data)

    def _mirror_matrices(self):
        """World matrices for the cutter and each mirrored copy. Mirroring happens in the space of
        the object the cut started on, like a Mirror modifier with that object as mirror object."""
        pivot = getattr(self, "mirror_object", None)
        axes = [i for i, on in enumerate((self.mirror_x, self.mirror_y, self.mirror_z)) if on]
        if pivot is None or not axes:
            return [Matrix.Identity(4)]
        to_pivot = pivot.matrix_world.inverted_safe()
        matrices = []
        for flips in itertools.product((False, True), repeat=len(axes)):
            scale = [1.0, 1.0, 1.0, 1.0]
            for axis, flip in zip(axes, flips):
                if flip:
                    scale[axis] = -1.0
            matrices.append(pivot.matrix_world @ Matrix.Diagonal(scale) @ to_pivot)
        return matrices

    def _update_mirror_modifier(self):
        """Mirror modifier on the cutter for the Mirror X / Y / Z settings."""
        axes = (self.mirror_x, self.mirror_y, self.mirror_z)
        pivot = getattr(self, "mirror_object", None)
        mod = next((m for m in self.cutter.modifiers if m.type == 'MIRROR'), None)
        if pivot is None or not any(axes):
            if mod is not None:
                self.cutter.modifiers.remove(mod)
            return
        if mod is None:
            mod = self.cutter.modifiers.new(name="Mirror", type='MIRROR')
        mod.use_axis = axes
        mod.mirror_object = pivot

    def _store_outline(self, profile):
        """Box and circle store their bounds (circle segments stay editable on redo), ngon its points."""
        if self.shape == 'NGON':
            pts = profile
        else:
            xs = [p.x for p in profile]
            ys = [p.y for p in profile]
            pts = [Vector((min(xs), min(ys))), Vector((max(xs), max(ys)))]
        self.outline = ";".join(f"{p.x!r},{p.y!r}" for p in pts)

    def _profile_from_outline(self):
        try:
            pts = [Vector(tuple(float(c) for c in item.split(","))) for item in self.outline.split(";") if item]
        except ValueError:
            return []
        if self.shape == 'NGON':
            return pts if len(pts) >= 3 else []
        if len(pts) != 2:
            return []
        lo, hi = pts
        center = (lo + hi) * 0.5
        hx, hy = (hi.x - lo.x) * 0.5, (hi.y - lo.y) * 0.5
        if self.shape == 'BOX':
            return self._box(center, hx, hy)
        seg = self.segments
        return [center + Vector((hx * math.cos(i * math.tau / seg), hy * math.sin(i * math.tau / seg)))
                for i in range(seg)]

    def _box(self, center, hx, hy):
        bevel = self.bevel_width if self.bevel else 0.0
        return box_points(center, hx, hy, bevel, self.bevel_segments, self.bevel_profile)

    # -- setup --

    def invoke(self, context, event):
        self.region = context.region
        self.rv3d = context.region_data
        if self.region is None or self.rv3d is None:
            return {'CANCELLED'}

        mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        self.press_mouse = mouse.copy()
        cutter_collection = bpy.data.collections.get("Cutters")
        depsgraph = context.evaluated_depsgraph_get()

        origin = region_2d_to_origin_3d(self.region, self.rv3d, mouse)
        direction = region_2d_to_vector_3d(self.region, self.rv3d, mouse)
        hit = _ray_cast(context, depsgraph, origin, direction, cutter_collection)

        if context.mode == 'EDIT_MESH':
            # Edit Mode cuts the meshes being edited, the active one first (it is the mirror object)
            edit_objects = [o for o in context.objects_in_mode if o.type == 'MESH']
            active = context.edit_object
            self.targets = [active] + [o for o in edit_objects if o != active]
        else:
            selected = [o for o in context.selected_objects if _is_cut_target(o, cutter_collection)]
            self.targets = selected or ([hit[3]] if hit else [])
        self.on_floor = False  # set below when nothing is under the cursor
        self.adjusting = None  # "bevel_width" (B) or "bevel_profile" (P) while the mouse sets it
        self.click_to_finish = False
        self.lmb_held = True  # the tool starts on a left mouse press
        self.mirror_object = hit[3] if hit and hit[3] in self.targets else (self.targets[0] if self.targets else None)
        self.mirror_pivot = self.mirror_object.name if self.mirror_object else ""

        view_rot = self.rv3d.view_rotation
        view_right = view_rot @ Vector((1.0, 0.0, 0.0))
        view_up = view_rot @ Vector((0.0, 1.0, 0.0))

        if hit:
            loc, normal, index, obj, matrix = hit
            if normal.dot(direction) > 0.0:
                normal = -normal
            # View: the object axis that looks most like screen right, so the box lines up with
            # the object instead of sitting skewed on the face
            x_axis = _closest_axis(obj.matrix_world, normal, view_right)
            if self.align == 'EDGE':
                edge_dir = _closest_edge_direction(obj, depsgraph, matrix, index, loc)
                if edge_dir is not None:
                    x_axis = edge_dir
            self.plane = _plane_matrix(loc, normal, x_axis, view_up)
        else:
            # Nothing under the cursor: always Add a new mesh, built up from the grid floor
            # (world Z = 0). The plane origin is the world origin so Ctrl snaps to the grid.
            self.on_floor = True
            self.operation = 'ADD'
            up = Vector((0.0, 0.0, 1.0))
            point = intersect_line_plane(origin, origin + direction, Vector(), up) if abs(direction.z) > 0.1 else None
            if point is not None and (point - origin).dot(direction) > 0.0:
                self.plane = _plane_matrix(Vector(), up, Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)))
            else:
                # Looking along the floor: a view aligned plane through the targets or the 3D cursor
                if self.targets:
                    center = sum((o.matrix_world.translation for o in self.targets), Vector()) / len(self.targets)
                else:
                    center = context.scene.cursor.location.copy()
                closest = intersect_line_plane(origin, origin + direction, center, -direction) or center
                self.plane = _plane_matrix(closest, -direction, view_right, view_up)

        self.plane_inv = self.plane.inverted_safe()
        self.normal = self.plane.col[2].to_3d().normalized()

        self.phase = 'DRAW'
        self.start = self._mouse_to_plane(mouse, event.ctrl) or Vector((0.0, 0.0))
        self.current = self.start.copy()
        self.points = [self.start.copy()] if self.shape == 'NGON' else []
        self.shift = event.shift
        self.alt = event.alt
        self.depth = 0.0
        self.depth_ref = 0.0
        self.depth_screen_scale = None  # world units per pixel when depth follows the mouse in screen space
        self.has_dragged = False

        self.cutter = None
        self.created = []
        self._batches = None
        self._dirty = True
        # Before any handler is added: if this fails, nothing is left running
        self._update_status(context)

        # The handle lives in the closure too: if the operator is freed without _cleanup
        # (file load, Blender ending the modal) the callback removes itself instead of
        # raising ReferenceError on every redraw. Addon reloads are covered by
        # unregister(), which removes every handle in _draw_handles.
        handle = []

        def remove():
            if handle:
                h = handle.pop()
                _draw_handles.discard(h)
                bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')

        def draw():
            # repr first: a freed struct reprs as "<bpy_struct, Cutter invalid>" without
            # raising, so the debugger isn't paused. The except is the fallback.
            if repr(self).endswith(" invalid>"):
                return remove()
            try:
                self._draw_callback()
            except ReferenceError:
                remove()

        handle.append(bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_VIEW'))
        self._handle = handle[0]
        _draw_handles.add(self._handle)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _click_select(self, context, event):
        try:
            bpy.ops.view3d.select(
                location=(event.mouse_region_x, event.mouse_region_y),
                extend=False, toggle=event.shift, deselect_all=not event.shift)
        except RuntimeError:
            pass
        return {'CANCELLED'}

    # -- geometry --

    def _mouse_ray(self, mouse):
        origin = region_2d_to_origin_3d(self.region, self.rv3d, mouse)
        direction = region_2d_to_vector_3d(self.region, self.rv3d, mouse)
        return origin, direction

    def _near_point(self, mouse, point):
        """True when the mouse is within NGON_CLOSE_RADIUS pixels of a plane point."""
        screen = location_3d_to_region_2d(self.region, self.rv3d, self.plane @ point.to_3d())
        return screen is not None and (mouse - screen).length < NGON_CLOSE_RADIUS

    def _snap(self, value):
        inc = self.snap_increment
        return round(value / inc) * inc

    def _mouse_to_plane(self, mouse, snap=False):
        origin, direction = self._mouse_ray(mouse)
        point = intersect_line_plane(origin, origin + direction, self.plane.translation, self.normal)
        if point is None:
            return None
        local = self.plane_inv @ point
        p = Vector((local.x, local.y))
        if snap:
            p = Vector((self._snap(p.x), self._snap(p.y)))
        return p

    def _setup_depth_input(self):
        """Pick how the mouse drives depth. Looking (almost) straight down the normal, e.g. an
        orthographic front view of the face, the mouse ray and the normal are parallel and can't be
        intersected, so depth follows vertical mouse movement in screen space instead."""
        center = self.plane @ self._profile_center().to_3d()
        _origin, view_dir = self._mouse_ray(location_3d_to_region_2d(self.region, self.rv3d, center) or Vector((0.0, 0.0)))
        self.depth_screen_scale = None
        if abs(view_dir.normalized().dot(self.normal)) > 0.98:
            a = location_3d_to_region_2d(self.region, self.rv3d, center)
            view_right = self.rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))
            b = location_3d_to_region_2d(self.region, self.rv3d, center + view_right)
            px_per_unit = (b - a).length if a is not None and b is not None else 0.0
            self.depth_screen_scale = 1.0 / px_per_unit if px_per_unit > 1e-6 else 0.01
        self._depth_view = self.rv3d.perspective_matrix.copy()

    def _anchor_depth(self, mouse):
        """(Re)start depth input from the current view, keeping the current depth. Called when
        extruding starts and whenever the view was rotated, panned or zoomed, so the mouse picks up
        from where the depth is instead of jumping or getting stuck at the surface."""
        self._setup_depth_input()
        mouse_depth = self._mouse_depth(mouse)
        self.depth_ref = (mouse_depth - self.depth) if mouse_depth is not None else -self.depth

    def _view_changed(self):
        old = getattr(self, "_depth_view", None)
        new = self.rv3d.perspective_matrix
        return old is None or any(abs(a - b) > 1e-6 for ra, rb in zip(old, new) for a, b in zip(ra, rb))

    def _mouse_depth(self, mouse):
        """Depth value under the mouse along the plane normal. Only differences are used (see depth_ref)."""
        if self.depth_screen_scale is not None:
            return mouse.y * self.depth_screen_scale  # mouse down pushes into the surface
        origin, direction = self._mouse_ray(mouse)
        center = self.plane @ self._profile_center().to_3d()
        result = intersect_line_line(center, center + self.normal, origin, origin + direction)
        if result is None:
            return None
        return (result[0] - center).dot(self.normal)

    def profile(self):
        """CCW 2D profile in plane space, or [] when the shape is degenerate."""
        fixed = getattr(self, "_fixed_profile", None)
        if fixed:
            return fixed  # rebuilt from the stored outline in execute()
        if self.shape == 'NGON':
            pts = list(self.points)
            if self.phase == 'DRAW':
                pts.append(self.current)
            cleaned = []
            for p in pts:
                if not cleaned or (p - cleaned[-1]).length > 1e-6:
                    cleaned.append(p)
            if len(cleaned) > 1 and (cleaned[0] - cleaned[-1]).length <= 1e-6:
                cleaned.pop()
            pts = cleaned
        else:
            d = self.current - self.start
            # Box: Shift makes it square. Circle: round by default, Shift frees it into an ellipse.
            if self.shift != (self.shape == 'CIRCLE'):
                m = max(abs(d.x), abs(d.y))
                d = Vector((math.copysign(m, d.x), math.copysign(m, d.y)))
            if self.alt or self.shape == 'CIRCLE':  # circles always grow from the center
                center, hx, hy = self.start, abs(d.x), abs(d.y)
            else:
                center, hx, hy = self.start + d * 0.5, abs(d.x) * 0.5, abs(d.y) * 0.5
            if self.shape == 'BOX':
                pts = self._box(center, hx, hy)
            else:
                seg = self.segments
                pts = [center + Vector((hx * math.cos(i * math.tau / seg), hy * math.sin(i * math.tau / seg)))
                       for i in range(seg)]

        if len(pts) < 3:
            return []
        area = _signed_area(pts)
        if abs(area) < 1e-10:
            return []
        if area < 0.0:
            pts.reverse()
        return pts

    def _profile_center(self):
        pts = self.profile() or [self.start]
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        return Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5))

    @staticmethod
    def _surface_margin(profile):
        xs = [p.x for p in profile]
        ys = [p.y for p in profile]
        size = max(max(xs) - min(xs), max(ys) - min(ys))
        return size * 0.01 + 1e-4

    def z_range(self, profile):
        """(z0, z1) of the cutter in plane space. None while drawing: the shape is a flat plane
        until it gets extruded. Negative depth is away from the camera (the plane normal faces it)."""
        if not profile or self.phase != 'EXTRUDE' or abs(self.depth) < 1e-6:
            return None
        if self.operation == 'ADD':
            return tuple(sorted((0.0, self.depth)))  # from the surface, out of it or into it
        # Push the surface side slightly out of the material to avoid coplanar faces
        surface = -math.copysign(self._surface_margin(profile), self.depth)
        return tuple(sorted((self.depth, surface)))

    # -- cutter object --

    def _cutter_matrix(self, center):
        return self.plane @ Matrix.Translation((center.x, center.y, 0.0))

    def _write_cutter_mesh(self, profile, z_range):
        center = self._profile_center()
        mesh = self.cutter.data
        mesh.clear_geometry()
        matrix = self._cutter_matrix(center)

        if self.shape == 'CIRCLE':
            # Non destructive, for cutters and Add: a side profile spun by a Screw modifier, so segments stay editable.
            # Ellipses use the object's Y scale.
            rx = max(abs(p.x - center.x) for p in profile)
            ry = max(abs(p.y - center.y) for p in profile)
            z0, z1 = z_range
            mesh.from_pydata([(0.0, 0.0, z0), (rx, 0.0, z0), (rx, 0.0, z1), (0.0, 0.0, z1)],
                             [(0, 1), (1, 2), (2, 3)], [])
            ensure_screw_modifier(self.cutter, self.segments)
            if rx > 1e-9:
                matrix = matrix @ Matrix.Diagonal((1.0, ry / rx, 1.0, 1.0))
        else:
            local = [p - center for p in profile]
            verts, faces = build_prism(local, z_range[0], z_range[1])
            mesh.from_pydata(verts, [], faces)

        mesh.update()
        self.cutter.matrix_world = matrix
        self._update_mirror_modifier()

    def _create_cutter(self, context):
        if self.operation == 'ADD':
            # A plain new object in the active collection, like Add Object
            name = ADD_OBJECT_NAMES[self.shape]
            self.cutter = bpy.data.objects.new(name, bpy.data.meshes.new(name))
            context.collection.objects.link(self.cutter)
            self.created = []
            return
        mesh = bpy.data.meshes.new("Cutter")
        self.cutter = bpy.data.objects.new("Cutter", mesh)
        get_cutter_collection(context).objects.link(self.cutter)

        solver, warning = resolve_boolean_solver(self.solver)
        if warning:
            self.report({'WARNING'}, warning)
        self.created = []
        for target in self.targets:
            self.created += add_boolean_modifiers(context, target, [self.cutter], self.operation, solver,
                                                  parent=self.parent)
        move_to_cutter_collection(context, [self.cutter])

    def _remove_cutter(self):
        if self.cutter is None:
            return
        for owner, mod in self.created:
            try:
                if owner in self.targets:
                    owner.modifiers.remove(mod)
                else:  # slice duplicate
                    data = owner.data
                    bpy.data.objects.remove(owner)
                    if data.users == 0:
                        bpy.data.meshes.remove(data)
            except (ReferenceError, RuntimeError):
                pass
        mesh = self.cutter.data
        bpy.data.objects.remove(self.cutter)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        self.cutter = None
        self.created = []

    def _update_live(self, context):
        if not self.live or context.mode != 'OBJECT':
            return  # Edit Mode cuts are applied on confirm, the overlay is the preview
        profile = self.profile()
        z = self.z_range(profile) if profile else None
        if z is None or (not self.targets and self.operation != 'ADD'):
            return
        if self.cutter is None:
            self._create_cutter(context)
            # Hidden while drawing so only the overlay shows, not its wire. Hidden objects still
            # cut. This preview cutter is removed on confirm, execute() builds the final one.
            if self.operation != 'ADD':  # Add's new object is the preview, keep it visible
                self.cutter.hide_set(True, view_layer=context.view_layer)
        self._write_cutter_mesh(profile, z)

    # -- finishing --

    def _finish(self, context):
        """Store the cut on the operator and build it through execute(), the same path redo uses."""
        profile = self.profile()
        z = self.z_range(profile) if profile else None
        self._cleanup(context)
        self._remove_cutter()  # live preview cutter, execute() builds the final one
        if z is None:
            return {'CANCELLED'}

        self.plane_matrix = [v for row in self.plane for v in row]
        self._store_outline(profile)
        if self.operation != 'ADD' and context.mode == 'EDIT_MESH':
            # Edit Mode: cut the edited meshes the cutter overlaps
            self.targets = self._overlapping_objects(context, profile, z)
        if not self.targets and self.operation != 'ADD':
            self.report({'INFO'}, "Nothing to cut")
            return {'CANCELLED'}
        self.depth_amount = self.depth if self.operation == 'ADD' else abs(self.depth)  # Add keeps its side
        self.target_names = TARGET_SEPARATOR.join(o.name for o in self.targets)
        return self.execute(context)

    def _overlapping_objects(self, context, profile, z_range):
        """Meshes whose bounding box overlaps the cutter's: the objects in Edit Mode there,
        otherwise every visible mesh that can be cut."""
        corners = [mirror @ self.plane @ Vector((p.x, p.y, z)) for mirror in self._mirror_matrices()
                   for p in profile for z in z_range]
        cutter_bounds = _world_bounds(corners)
        if context.mode == 'EDIT_MESH':
            candidates = self.targets
        else:
            cutter_collection = bpy.data.collections.get("Cutters")
            candidates = [o for o in context.visible_objects if _is_cut_target(o, cutter_collection)]
        return [o for o in candidates if _bounds_overlap(cutter_bounds, _object_bounds(o))]

    def _apply(self, context):
        for owner, mod in self.created:
            try:
                with context.temp_override(object=owner, active_object=owner, selected_objects=[owner]):
                    bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError as e:
                self.report({'WARNING'}, f"Could not apply boolean on {owner.name}: {e}")
                return  # keep the cutter so nothing is lost
        mesh = self.cutter.data
        bpy.data.objects.remove(self.cutter)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        self.cutter = None

    def _cancel(self, context):
        self._cleanup(context)
        self._remove_cutter()
        return {'CANCELLED'}

    def _cleanup(self, context):
        if getattr(self, "_handle", None) is not None:
            if self._handle in _draw_handles:
                _draw_handles.discard(self._handle)
                bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        self._batches = None
        context.workspace.status_text_set(None)
        if context.area:
            context.area.header_text_set(None)
        self.region.tag_redraw()

    # -- modal --

    def _apply_settings(self, context, values):
        """Apply changed settings to the running cut. Returns True when something changed."""
        values = {k: v for k, v in values.items() if getattr(self, k) != v}
        if self.on_floor:
            values.pop('operation', None)  # started on the floor: always Add, there is nothing to cut
        if 'shape' in values:
            new, old = values['shape'], self.shape
            if self.phase == 'EXTRUDE' and 'NGON' in (new, old):
                del values['shape']  # can't turn a finished outline into an ngon or back
                props = _tool_props(context)
                if props is not None:
                    props.shape = old
            elif new == 'NGON':
                self.points = [self.start.copy()]
            elif old == 'NGON' and self.points:
                self.start = self.points[0].copy()
        if not values:
            return False
        if 'operation' in values and self.phase == 'EXTRUDE' \
                and (values['operation'] == 'ADD') != (self.operation == 'ADD'):
            # Cuts only go in. Going to Add mirrors the depth so it comes out, going to a cut keeps
            # an Add that already goes in. depth_ref moves along so the mouse keeps working.
            new_depth = abs(self.depth) if values['operation'] == 'ADD' else -abs(self.depth)
            self.depth_ref += self.depth - new_depth
            self.depth = new_depth
        for name, value in values.items():
            setattr(self, name, value)
        if self.cutter is not None and values.keys() & {'operation', 'shape', 'solver'}:
            self._remove_cutter()  # live: rebuilt with the new settings by _update_live
        return True

    def _sync_from_tool(self, context):
        """Pick up changes made to the tool settings, e.g. from the D options popup."""
        props = _tool_props(context)
        if props is None:
            return False
        return self._apply_settings(context, {name: getattr(props, name) for name in SETTINGS})

    def _set_setting(self, context, name, value):
        """Change a setting from a shortcut, and keep it on the tool for the next cut."""
        props = _tool_props(context)
        if props is not None:
            setattr(props, name, value)
        return self._apply_settings(context, {name: value})

    def _end_draw(self, context, mouse):
        """The shape is drawn, move on to setting the depth with the mouse."""
        profile = self.profile()
        if not profile:
            return self._cancel(context)
        # Start flat, the mouse extrudes it from here (depth = mouse_depth - depth_ref)
        self.depth = MIN_DEPTH if self.operation == 'ADD' else -MIN_DEPTH
        self.phase = 'EXTRUDE'
        self._anchor_depth(mouse)
        self._dirty = True
        self._update_status(context)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        try:
            return self._modal(context, event)
        except Exception:
            # Blender ends the operator when modal raises; don't leave the overlay behind
            self._cancel(context)
            raise

    # -- mouse adjust: bevel width (B) and profile (P) --

    def _start_adjust(self, context, mouse, name):
        """Let horizontal mouse movement set a bevel setting until confirmed, then go back to
        drawing or setting the depth. Also turns the bevel on."""
        self.adjust_before = (self.bevel, getattr(self, name))
        self._set_setting(context, "bevel", True)
        self.adjusting = name
        self.adjust_mouse_start = mouse.x
        self.adjust_value_start = getattr(self, name)

    def _end_adjust(self, mouse):
        """Back to drawing or setting the depth, from where the mouse is now."""
        self.adjusting = None
        if self.phase == 'EXTRUDE':
            self._anchor_depth(mouse)  # keep the depth, don't jump to the moved mouse
        elif not self.lmb_held and self.shape != 'NGON':
            self.click_to_finish = True  # the drag was let go: a click finishes the shape

    def _adjust_event(self, context, event, mouse):
        """Events while adjusting with the mouse. None lets the normal handling run (wheel, view)."""
        name = self.adjusting
        if event.type == 'MOUSEMOVE':
            low, high = MOUSE_ADJUST_RANGES[name]
            value = self.adjust_value_start + (mouse.x - self.adjust_mouse_start) / MOUSE_ADJUST_PIXELS
            if event.ctrl:
                value = round(value * 20.0) / 20.0
            self._set_setting(context, name, max(low, min(high, value)))
        elif event.type == 'LEFTMOUSE' and event.value in {'PRESS', 'RELEASE'}:
            self._end_adjust(mouse)
        elif event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'}:
            if event.value == 'PRESS':
                self._end_adjust(mouse)
        elif event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            bevel, value = self.adjust_before
            self._set_setting(context, name, value)
            self._set_setting(context, "bevel", bevel)
            self._end_adjust(mouse)
        elif event.type == 'B' and event.value == 'PRESS':
            self._set_setting(context, "bevel", False)  # B again: no bevel
            self._end_adjust(mouse)
        elif event.type == 'P' and event.value == 'PRESS' and name != "bevel_profile":
            self._end_adjust(mouse)
            self._start_adjust(context, mouse, "bevel_profile")
        else:
            return None
        self._dirty = True
        self._update_live(context)
        self._update_status(context)
        self.region.tag_redraw()
        return {'RUNNING_MODAL'}

    def _modal(self, context, event):
        mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        changed = self._sync_from_tool(context)

        if event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_ALT', 'RIGHT_ALT', 'LEFT_CTRL', 'RIGHT_CTRL'} \
                or event.type == 'MOUSEMOVE':
            if self.phase == 'DRAW' and (self.shift, self.alt) != (event.shift, event.alt):
                self.shift, self.alt = event.shift, event.alt
                changed = True

        if event.type == 'LEFTMOUSE' and event.value in {'PRESS', 'RELEASE'}:
            self.lmb_held = event.value == 'PRESS'

        if self.adjusting:
            result = self._adjust_event(context, event, mouse)
            if result is not None:
                return result

        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            return self._cancel(context)

        if event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'NDOF_MOTION'}:
            return {'PASS_THROUGH'}

        key_press = event.value == 'PRESS' and not (event.ctrl or event.alt or event.oskey)

        if event.type in PLUS_KEYS | MINUS_KEYS:
            # Wheel and - / + change the circle segments, or the bevel segments of a bevelled box
            if self.shape == 'CIRCLE':
                name, low, high = "segments", 3, 256
            elif self.shape == 'BOX' and self.bevel:
                name, low, high = "bevel_segments", 1, 64
            elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'NUMPAD_PLUS', 'NUMPAD_MINUS'}:
                return {'PASS_THROUGH'}  # zoom the view
            else:
                return {'RUNNING_MODAL'}
            if event.value == 'PRESS':  # wheel events also arrive as PRESS
                step = 1 if event.type in PLUS_KEYS else -1
                value = max(low, min(high, getattr(self, name) + step * (4 if event.ctrl else 1)))
                changed |= self._set_setting(context, name, value)

        elif event.type in MIRROR_KEYS and key_press:
            name = MIRROR_KEYS[event.type]
            changed |= self._set_setting(context, name, not getattr(self, name))

        elif event.type == 'X' and key_press:
            index = OPERATION_ORDER.index(self.operation)
            step = -1 if event.shift else 1
            changed |= self._set_setting(context, "operation", OPERATION_ORDER[(index + step) % len(OPERATION_ORDER)])

        elif event.type == 'B' and key_press and self.shape == 'BOX':
            self._start_adjust(context, mouse, "bevel_width")
            changed = True

        elif event.type == 'P' and key_press and self.shape == 'BOX':
            self._start_adjust(context, mouse, "bevel_profile")
            changed = True

        elif event.type in SHAPE_KEYS and key_press:
            changed |= self._set_setting(context, "shape", SHAPE_KEYS[event.type])

        elif event.type == 'L' and key_press:
            changed |= self._set_setting(context, "live", not self.live)

        elif event.type == 'A' and key_press and self.operation != 'ADD' and context.mode == 'OBJECT':
            changed |= self._set_setting(context, "apply", not self.apply)

        elif event.type == 'D' and key_press:
            bpy.ops.keyops.cutter_tool_options('INVOKE_DEFAULT')
            return {'RUNNING_MODAL'}

        elif event.type == 'MOUSEMOVE':
            if self.phase == 'DRAW':
                p = self._mouse_to_plane(mouse, event.ctrl)
                if p is not None and p != self.current:
                    self.current = p
                    changed = True
                if (mouse - self.press_mouse).length >= CLICK_DRAG_THRESHOLD:
                    self.has_dragged = True
            else:
                if self._view_changed():
                    # The view moved since depth input was set up: the old reference no longer
                    # matches, so re-anchor from the current depth. The view never decides the
                    # direction, that comes from the surface normal and the clamp below.
                    self._anchor_depth(mouse)
                d = self._mouse_depth(mouse)
                if d is not None:
                    depth = d - self.depth_ref
                    if event.ctrl:
                        depth = self._snap(depth)
                    if self.operation == 'ADD':
                        # Add goes either way: out of the surface or into it, never flat
                        if abs(depth) < MIN_DEPTH:
                            depth = math.copysign(MIN_DEPTH, depth)
                    else:
                        depth = min(depth, -MIN_DEPTH)  # only ever away from the camera, never toward it
                    if depth != self.depth:
                        self.depth = depth
                        changed = True

        elif event.type == 'LEFTMOUSE':
            if event.alt and event.value == 'PRESS' and (self.shape == 'NGON' or self.phase == 'EXTRUDE'):
                return {'PASS_THROUGH'}  # Alt + LMB navigation
            if self.phase == 'DRAW' and self.shape != 'NGON' and self.click_to_finish:
                # The drag was let go while adjusting the bevel: a click finishes the shape
                if event.value == 'PRESS':
                    return self._end_draw(context, mouse)
            elif self.phase == 'DRAW' and self.shape != 'NGON' and event.value == 'RELEASE':
                if not self.has_dragged:
                    self._cancel(context)
                    return self._click_select(context, event)
                return self._end_draw(context, mouse)
            if self.phase == 'DRAW' and self.shape == 'NGON' and event.value in {'PRESS', 'DOUBLE_CLICK'}:
                # Close the ngon by clicking the first point, the last point again, or double clicking
                if len(self.points) >= 3 and (event.value == 'DOUBLE_CLICK'
                                              or self._near_point(mouse, self.points[0])
                                              or self._near_point(mouse, self.points[-1])):
                    self.current = self.points[-1]  # drop the floating cursor point
                    return self._end_draw(context, mouse)
                p = self._mouse_to_plane(mouse, event.ctrl)
                if p is not None and (p - self.points[-1]).length > 1e-6:
                    self.points.append(p)
                    changed = True
            elif self.phase == 'EXTRUDE' and event.value == 'PRESS':
                return self._finish(context)

        elif event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
            if self.phase == 'DRAW':
                if self.shape == 'NGON':
                    self.current = self.points[-1]  # drop the floating cursor point
                return self._end_draw(context, mouse)
            return self._finish(context)

        elif event.type == 'BACK_SPACE' and event.value == 'PRESS' and self.shape == 'NGON' and self.phase == 'DRAW':
            if len(self.points) > 1:
                self.points.pop()
                changed = True

        if changed:
            self._dirty = True
            self._update_live(context)
            self._update_status(context)
            self.region.tag_redraw()
        return {'RUNNING_MODAL'}

    # -- UI --

    def _mirror_text(self):
        axes = "".join(a for a, on in zip("XYZ", (self.mirror_x, self.mirror_y, self.mirror_z)) if on)
        if axes and getattr(self, "mirror_object", None) is None:
            return f"{axes} (needs an object)"
        return axes or "Off"

    def _status_items(self, context):
        """(icons, text) pairs for the status bar, Blender style: key icons followed by a label."""
        if self.adjusting:
            label = "Bevel Width" if self.adjusting == "bevel_width" else "Bevel Profile"
            value = getattr(self, self.adjusting)
            return [(('MOUSE_MOVE',), f"{label}: {value:.2f}"), (('EVENT_CTRL',), "Snap"),
                    (('MOUSE_MMB_SCROLL',), f"Bevel Segments: {self.bevel_segments}"),
                    (('MOUSE_LMB',), "Confirm"), (('EVENT_B',), "No Bevel"), (('MOUSE_RMB',), "Cancel")]
        items = []
        if self.phase == 'DRAW':
            if self.shape == 'NGON':
                items += [(('MOUSE_LMB',), "Add Point"), (('EVENT_BACKSPACE',), "Remove Point"),
                          (('EVENT_RETURN',), "Close")]
            else:
                items += [(('MOUSE_LMB_DRAG',), "Draw"),
                          (('EVENT_SHIFT',), "Ellipse" if self.shape == 'CIRCLE' else "Square")]
                if self.shape == 'BOX':
                    items.append((('EVENT_ALT',), "From Center"))
        else:
            items += [(('MOUSE_LMB',), "Confirm"), (('MOUSE_MOVE',), "Depth")]
        items.append((('EVENT_CTRL',), "Snap"))
        if self.shape == 'CIRCLE':
            items.append((('MOUSE_MMB_SCROLL',), f"Segments: {self.segments}"))
        items += [
            (('EVENT_X',), OPERATION_NAMES[self.operation]),
            (('EVENT_B', 'EVENT_C', 'EVENT_N'), self.shape.title()),
        ]
        if self.shape == 'BOX':
            items.append((('EVENT_B',), f"Bevel Width: {self.bevel_width:.2f}" if self.bevel else "Bevel"))
            if self.bevel:
                items += [(('MOUSE_MMB_SCROLL',), f"Bevel Segments: {self.bevel_segments}"),
                          (('EVENT_P',), f"Profile: {self.bevel_profile:.2f}")]
        items.append((('EVENT_ONEKEY', 'EVENT_TWOKEY', 'EVENT_THREEKEY'), f"Mirror: {self._mirror_text()}"))
        if context.mode == 'OBJECT':
            items.append((('EVENT_L',), f"Live: {'On' if self.live else 'Off'}"))
            if self.operation != 'ADD':
                items.append((('EVENT_A',), f"Apply: {'On' if self.apply else 'Off'}"))
        items += [
            (('EVENT_D',), "Options"),
            (('MOUSE_RMB',), "Cancel"),
        ]
        return items

    def _update_status(self, context):
        op = self.operation.title()
        items = self._status_items(context)

        def draw_status(header, _context):
            row = header.layout.row(align=True)
            for icons, text in items:
                for icon in icons[:-1]:
                    row.label(text="", icon=safe_icon(icon))
                row.label(text=text, icon=safe_icon(icons[-1]))
                row.separator(factor=2.0)

        context.workspace.status_text_set(draw_status)

        profile = self.profile()
        info = f"Cutter Tool: {op}  {self.shape.title()}"
        if profile:
            xs = [p.x for p in profile]
            ys = [p.y for p in profile]
            info += f"   {max(xs) - min(xs):.3f} x {max(ys) - min(ys):.3f}"
        if self.phase == 'EXTRUDE':
            info += f"   depth {abs(self.depth):.3f}"
        if self.shape == 'CIRCLE':
            info += f"   {self.segments} segments"
        if self.shape == 'BOX' and self.bevel:
            info += f"   bevel {self.bevel_width:.2f}  {self.bevel_segments} seg  profile {self.bevel_profile:.2f}"
        if any((self.mirror_x, self.mirror_y, self.mirror_z)):
            info += f"   mirror {self._mirror_text()}"
        if context.mode == 'EDIT_MESH':
            info += "   (Edit Mode, applied)"
        elif self.live:
            info += "   (Live)"
        if context.area:
            context.area.header_text_set(info)

    def _rebuild_batches(self):
        """Batches are only rebuilt when the shape changed, drawing itself just binds and draws."""
        self._dirty = False
        self._batches = None
        profile = self.profile()
        plane = self.plane

        point_coords = []
        if self.shape == 'NGON' and self.phase == 'DRAW':
            point_coords = [plane @ p.to_3d() for p in self.points]

        if not profile:
            self._batches = {"points": point_coords}
            if point_coords:
                self._build_point_batch()
            return

        z = self.z_range(profile)
        n = len(profile)
        line_shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        fill_shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        if z is None:
            # Flat plane, lifted a hair off the surface so the depth tested pass doesn't z-fight
            lift = self._surface_margin(profile)
            ring = [plane @ Vector((p.x, p.y, lift)) for p in profile]
            tris = tessellate_polygon([ring])
            lines = []
            for i in range(n):
                lines += (ring[i], ring[(i + 1) % n])
            coords = ring
        else:
            bottom = [plane @ Vector((p.x, p.y, z[0])) for p in profile]
            top = [plane @ Vector((p.x, p.y, z[1])) for p in profile]
            cap = tessellate_polygon([top])
            coords = top + bottom
            tris = list(cap) + [(a + n, b + n, c + n) for a, b, c in cap]
            lines = []
            rounded = self.shape == 'CIRCLE' or (self.shape == 'BOX' and self.bevel)
            for i in range(n):
                j = (i + 1) % n
                tris += [(i, j, n + j), (i, n + j, n + i)]
                lines += (top[i], top[j], bottom[i], bottom[j])
                if not rounded or i % max(1, n // 8) == 0:
                    lines += (top[i], bottom[i])

        # Mirrored copies (1 / 2 / 3) are drawn as more of the same shape
        mirrors = self._mirror_matrices()
        all_coords, all_tris = [], []
        for mirror in mirrors:
            offset = len(all_coords)
            all_coords += [mirror @ p for p in coords]
            all_tris += [(a + offset, b + offset, c + offset) for a, b, c in tris]
        lines = [mirror @ p for mirror in mirrors for p in lines]
        fill = batch_for_shader(fill_shader, 'TRIS', {"pos": all_coords}, indices=all_tris)

        self._batches = {
            "fill": fill,
            "lines": batch_for_shader(line_shader, 'LINES', {"pos": lines}),
            "fill_shader": fill_shader,
            "line_shader": line_shader,
            "points": point_coords,
        }
        if point_coords:
            self._build_point_batch()

    def _build_point_batch(self):
        try:
            shader = gpu.shader.from_builtin('POINT_UNIFORM_COLOR')
        except (ValueError, TypeError):
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        self._batches["point_shader"] = shader
        self._batches["point_batch"] = batch_for_shader(shader, 'POINTS', {"pos": self._batches["points"]})

    def _draw_callback(self):
        context = bpy.context
        region = context.region
        if region is None or region.as_pointer() != self.region.as_pointer():
            return
        try:
            if self._dirty or self._batches is None:
                self._rebuild_batches()
        except ReferenceError:
            return
        batches = self._batches
        if not batches:
            return

        color = OPERATION_COLORS.get(self.operation, (1.0, 1.0, 1.0))
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_mask_set(False)

        if "fill" in batches:
            fill_shader = batches["fill_shader"]
            line_shader = batches["line_shader"]
            # Two passes against the scene depth: the part inside the object draws faint (x-ray),
            # the part in front of it draws solid, so you can see the cutter going in.
            for depth_test, fill_alpha, line_alpha, width in (('NONE', 0.02, 0.35, 1.5), ('LESS_EQUAL', 0.06, 0.9, 2.0)):
                gpu.state.depth_test_set(depth_test)
                fill_shader.bind()
                fill_shader.uniform_float("color", (*color, fill_alpha))
                batches["fill"].draw(fill_shader)

                line_shader.bind()
                line_shader.uniform_float("viewportSize", (region.width, region.height))
                line_shader.uniform_float("lineWidth", width)
                line_shader.uniform_float("color", (*color, line_alpha))
                batches["lines"].draw(line_shader)

        gpu.state.depth_test_set('NONE')
        if "point_batch" in batches:
            shader = batches["point_shader"]
            shader.bind()
            shader.uniform_float("color", (1.0, 1.0, 1.0, 1.0))
            gpu.state.point_size_set(7.0)
            batches["point_batch"].draw(shader)

        gpu.state.blend_set('NONE')


# --- Options popup (D) ------------------------------------------------------

def draw_operation_buttons(layout, props, scale=1.0):
    """One row of boolean operation icons (the toolkit's own, same as the Toolkit panel)."""
    row = layout.row(align=True)
    row.scale_x = row.scale_y = scale
    for identifier, _name, _desc in OPERATION_ITEMS:
        if identifier == 'ADD':
            row.separator(factor=0.5)
        op = row.operator(CutterSetOperation.bl_idname, text="", icon_value=operation_icon(identifier),
                          depress=props.operation == identifier)
        op.operation = identifier
    return row


class KEYOPS_MT_cutter_operation(bpy.types.Menu):
    """Boolean operation (or Add) dropdown for the tool header, with the toolkit's boolean icons"""
    bl_label = "Operation"

    def draw(self, context):
        props = _tool_props(context)
        for identifier, name, _desc in OPERATION_ITEMS:
            if identifier == 'ADD':
                self.layout.separator()
            op = self.layout.operator(CutterSetOperation.bl_idname, text=name, icon_value=operation_icon(identifier),
                                      depress=props is not None and props.operation == identifier)
            op.operation = identifier


def draw_operation_dropdown(layout, props):
    """Looks like an enum field: current boolean's icon and name, opens the menu above."""
    row = layout.row()
    row.ui_units_x = 6.5  # fits "Difference" with its icon and the dropdown arrow, header buttons clip otherwise
    row.menu(KEYOPS_MT_cutter_operation.__name__, text=OPERATION_NAMES[props.operation],
             icon_value=operation_icon(props.operation))


class CutterSetOperation(bpy.types.Operator):
    """Set the boolean operation of the Cutter Tool"""
    bl_idname = "keyops.cutter_set_operation"
    bl_label = "Cutter Operation"
    bl_options = {'INTERNAL'}

    operation: EnumProperty(name="Operation", items=OPERATION_ITEMS)  # type: ignore

    @classmethod
    def description(cls, context, properties):
        name = OPERATION_NAMES[properties.operation]
        if properties.operation == 'ADD':
            name = "Add a new object instead of cutting"
        return f"{name}  (X cycles while cutting)"

    def execute(self, context):
        props = _tool_props(context)
        if props is None:
            return {'CANCELLED'}
        props.operation = self.operation
        return {'FINISHED'}


CIRCLE_SEGMENT_PRESETS = (8, 12, 16, 24, 32, 64)
BEVEL_SEGMENT_PRESETS = (1, 2, 3, 4, 6, 8)


class CutterSetSegments(bpy.types.Operator):
    """Set the segment count of the Cutter Tool"""
    bl_idname = "keyops.cutter_set_segments"
    bl_label = "Cutter Segments"
    bl_options = {'INTERNAL'}

    setting: StringProperty(options={'HIDDEN'})  # type: ignore
    value: IntProperty()  # type: ignore

    def execute(self, context):
        props = _tool_props(context)
        if props is None or self.setting not in {"segments", "bevel_segments"}:
            return {'CANCELLED'}
        setattr(props, self.setting, self.value)
        return {'FINISHED'}


def draw_segment_presets(layout, props, setting, presets):
    """A row of preset buttons for a segment count, the current one pressed."""
    row = layout.row(align=True)
    for value in presets:
        op = row.operator(CutterSetSegments.bl_idname, text=str(value), depress=getattr(props, setting) == value)
        op.setting = setting
        op.value = value


def draw_bevel_settings(layout, props, with_keys=False):
    """Box bevel settings, shared by the D popup and the redo panel."""
    col = layout.column(align=True)
    col.prop(props, "bevel", text="Bevel")
    if props.bevel:
        col.prop(props, "bevel_width", text="Width    B" if with_keys else "Width")
        col.prop(props, "bevel_segments", text="Segments    Wheel / - +" if with_keys else "Segments")
        if with_keys:
            draw_segment_presets(col, props, "bevel_segments", BEVEL_SEGMENT_PRESETS)
        col.prop(props, "bevel_profile", text="Profile    P" if with_keys else "Profile")


def draw_cutter_options(layout, props, context):
    """Tool settings with their modal shortcuts, used by the D popup."""
    col = layout.column(align=True)
    col.label(text="Operation    X")
    draw_operation_buttons(col, props, scale=1.4)

    col = layout.column(align=True)
    col.label(text="Shape    B / C / N")
    row = col.row(align=True)
    row.scale_x = row.scale_y = 1.4
    for identifier, _name, _desc, icon, _num in SHAPE_ITEMS:
        row.prop_enum(props, "shape", identifier, text="", icon=icon)
    if props.shape == 'CIRCLE':
        col.prop(props, "segments", text="Segments    Wheel / - +")
        draw_segment_presets(col, props, "segments", CIRCLE_SEGMENT_PRESETS)
    if props.shape == 'BOX':
        draw_bevel_settings(layout, props, with_keys=True)

    col = layout.column(align=True)
    col.label(text="Mirror    1 / 2 / 3")
    row = col.row(align=True)
    row.prop(props, "mirror_x", text="X", toggle=True)
    row.prop(props, "mirror_y", text="Y", toggle=True)
    row.prop(props, "mirror_z", text="Z", toggle=True)

    is_add = props.operation == 'ADD'
    col = layout.column(align=True)
    if not is_add:
        col.prop(props, "solver", text="Solver")
    col.prop(props, "align", text="Align")
    col.prop(props, "snap_increment", text="Snap  Ctrl")

    if context.mode == 'OBJECT':
        row = layout.row()
        row.prop(props, "live", text="Live  L")
        if not is_add:
            row.prop(props, "apply", text="Apply  A")
    else:
        layout.label(text="Edit Mode: cuts are applied to the mesh")


class CutterToolOptions(bpy.types.Operator):
    """Cutter Tool options"""
    bl_idname = "keyops.cutter_tool_options"
    bl_label = "Cutter Tool"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        if _tool_props(context) is None:
            return {'CANCELLED'}
        return context.window_manager.invoke_popup(self, width=240)

    def draw(self, context):
        props = _tool_props(context)
        if props is None:
            return
        self.layout.label(text="Cutter Tool", icon='MOD_BOOLEAN')
        draw_cutter_options(self.layout, props, context)

    def execute(self, context):
        return {'FINISHED'}


# --- Tool -------------------------------------------------------------------

class WorkSpaceCutter(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = TOOL_IDNAME
    bl_label = "Cutter Tool"
    bl_description = (
        "Draw a shape and boolean it into the selected objects, or the object under the cursor.\n"
        "Draw the shape, then set the depth with the mouse. Uses a light overlay, the boolean is only added when you confirm.\n"
        "Add mode (X cycles the operation) makes a new object from the shape instead"
    )
    bl_icon = os.path.join(ICON_DIR, "ops.object.cutter_tool") 
    bl_keymap = (
        (OP_IDNAME, {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),
        (OP_IDNAME, {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True}, None),
        (OP_IDNAME, {"type": 'LEFTMOUSE', "value": 'PRESS', "ctrl": True}, None),
        (CutterToolOptions.bl_idname, {"type": 'D', "value": 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        props = tool.operator_properties(OP_IDNAME)
        draw_operation_dropdown(layout, props)
        layout.prop(props, "shape", expand=True, icon_only=True)
        if props.shape == 'CIRCLE':
            layout.prop(props, "segments")
        if props.shape == 'BOX':
            layout.prop(props, "bevel")
            if props.bevel:
                layout.prop(props, "bevel_segments", text="Segments")
        row = layout.row(align=True)
        row.prop(props, "mirror_x", text="X", toggle=True)
        row.prop(props, "mirror_y", text="Y", toggle=True)
        row.prop(props, "mirror_z", text="Z", toggle=True)
        is_add = props.operation == 'ADD'
        layout.prop(props, "align", text="")
        if not is_add:
            layout.prop(props, "solver", text="")
        layout.prop(props, "snap_increment")
        if context.mode == 'OBJECT':
            layout.prop(props, "live")
            if not is_add:
                layout.prop(props, "apply")


class WorkSpaceCutterEdit(bpy.types.WorkSpaceTool):
    """The Cutter in Edit Mode: same tool, but the cut is applied to the mesh"""
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'EDIT_MESH'
    bl_idname = EDIT_TOOL_IDNAME
    bl_label = "Cutter Tool"
    bl_description = (
        "Draw a shape and cut it into the mesh being edited. The cut is applied right away.\n"
        "Add mode builds the shape into the mesh instead"
    )
    bl_icon = WorkSpaceCutter.bl_icon
    bl_keymap = WorkSpaceCutter.bl_keymap
    draw_settings = WorkSpaceCutter.draw_settings


classes = (Cutter, CutterSetOperation, CutterSetSegments, KEYOPS_MT_cutter_operation, CutterToolOptions)

# Draw handles of running Cutter operators, so a reload mid-cut can't leave one behind
_draw_handles = set()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def set_enabled(on):
    """The tool sits in the toolbar (Object and Edit Mode) only while the feature is on."""
    from .merge_tool import remove_stale_tool
    for tool in (WorkSpaceCutter, WorkSpaceCutterEdit):
        try:
            if on and not hasattr(tool, "_bl_tool"):
                remove_stale_tool(tool)
                bpy.utils.register_tool(tool, after={"builtin.measure"}, separator=True, group=False)
            elif not on and hasattr(tool, "_bl_tool"):
                bpy.utils.unregister_tool(tool)
        except Exception as e:
            print(f"Key Ops: could not update the Cutter tool in the toolbar: {e}")


def unregister():
    for h in list(_draw_handles):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
        except ValueError:
            pass
    _draw_handles.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
