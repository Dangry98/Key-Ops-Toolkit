import math
import os

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
from ..operators.add_modifier import (
    BOOLEAN_OPERATION_ITEMS,
    add_boolean_modifiers,
    get_cutter_collection,
    move_to_cutter_collection,
    resolve_boolean_solver,
)

# Cutter: draw a box / circle / ngon on a surface (or the view plane) and boolean it
# into the targets. The preview is a cheap GPU overlay; nothing is evaluated until
# the cut is confirmed, unless "Live" is enabled on the tool.
#
# The boolean setup itself (modifiers, solver, Cutters collection, slice) lives in
# operators/add_modifier.py and is shared with the Add Boolean operator.

ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")
OP_IDNAME = "keyops.cutter"
TOOL_IDNAME = "object.keyops_cutter_tool"

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
OPERATION_KEYS = {'ONE': 'DIFFERENCE', 'TWO': 'UNION', 'THREE': 'INTERSECT', 'FOUR': 'SLICE', 'FIVE': 'ADD'}
ADD_OBJECT_NAMES = {'BOX': "Box", 'CIRCLE': "Cylinder", 'NGON': "Prism"}
SHAPE_KEYS = {'B': 'BOX', 'C': 'CIRCLE', 'N': 'NGON'}
# Operator settings mirrored from the tool, so the D popup and shortcuts edit one place
SETTINGS = ("operation", "shape", "align", "solver", "segments", "snap_increment", "live", "apply")

SHAPE_ITEMS = (
    ('BOX', "Box", "Drag a rectangle", 'MESH_PLANE', 0),
    ('CIRCLE', "Circle", "Drag an ellipse", 'MESH_CIRCLE', 1),
    ('NGON', "Ngon", "Click points, Enter / Space or click the first point to close", 'MESH_DATA', 2),
)
ALIGN_ITEMS = (
    ('EDGE', "Edge", "Align the shape to the closest edge of the face under the cursor"),
    ('VIEW', "View", "Align the shape to the view"),
)
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
    try:
        tool = context.workspace.tools.from_space_view3d_mode('OBJECT', create=False)
        if tool is not None and tool.idname == TOOL_IDNAME:
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
    align: EnumProperty(name="Align", items=ALIGN_ITEMS, default='EDGE')  # type: ignore
    solver: EnumProperty(name="Solver", items=SOLVER_ITEMS, default='FAST')  # type: ignore
    segments: IntProperty(name="Segments", description="Circle segments", default=32, min=3, max=256)  # type: ignore
    snap_increment: FloatProperty(name="Snap", description="Grid increment used while holding Ctrl", default=0.1, min=0.0001, soft_max=10.0, subtype='DISTANCE')  # type: ignore
    live: BoolProperty(name="Live", description="Create the cutter and boolean while drawing. Slower on heavy meshes, off by default", default=False)  # type: ignore
    apply: BoolProperty(name="Apply", description="Apply the boolean and delete the cutter when done", default=False)  # type: ignore
    parent: BoolProperty(name="Parent Boolean", description="Parent the cutter to the object it cuts", default=False, options={'SKIP_SAVE'})  # type: ignore
    depth_amount: FloatProperty(name="Depth", description="How far the cutter goes in, away from the view. In Add mode, how far the new object comes out of the surface", default=0.5, min=MIN_DEPTH, soft_max=100.0, subtype='DISTANCE', options={'SKIP_SAVE'})  # type: ignore

    # The finished cut, stored so the redo panel can rebuild it in execute()
    plane_matrix: FloatVectorProperty(size=16, options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore
    outline: StringProperty(options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore
    target_names: StringProperty(options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.area is not None and context.area.type == 'VIEW_3D'

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
            layout.prop(self, "parent")
        layout.separator()
        layout.prop(self, "depth_amount")
        if self.shape == 'CIRCLE':
            layout.prop(self, "segments")
        if not is_add:
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
        self.depth = self.depth_amount if is_add else -self.depth_amount
        self.cutter = None
        self.created = []

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
            return [center + Vector(o) for o in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
        seg = self.segments
        return [center + Vector((hx * math.cos(i * math.tau / seg), hy * math.sin(i * math.tau / seg)))
                for i in range(seg)]

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

        selected = [o for o in context.selected_objects if _is_cut_target(o, cutter_collection)]
        self.targets = selected or ([hit[3]] if hit else [])
        if not self.targets and self.operation != 'ADD':
            return self._click_select(context, event)

        view_rot = self.rv3d.view_rotation
        view_right = view_rot @ Vector((1.0, 0.0, 0.0))
        view_up = view_rot @ Vector((0.0, 1.0, 0.0))

        if hit:
            loc, normal, index, obj, matrix = hit
            if normal.dot(direction) > 0.0:
                normal = -normal
            x_axis = view_right
            if self.align == 'EDGE':
                edge_dir = _closest_edge_direction(obj, depsgraph, matrix, index, loc)
                if edge_dir is not None:
                    x_axis = edge_dir
            self.plane = _plane_matrix(loc, normal, x_axis, view_up)
        elif self.operation == 'ADD':
            # Nothing under the cursor: draw on the floor through the 3D cursor, like Add Object.
            # Looking along the floor, a view aligned plane through the 3D cursor instead.
            cursor = context.scene.cursor.location
            floor = Vector((0.0, 0.0, 1.0)) if direction.z < 0.0 else Vector((0.0, 0.0, -1.0))
            point = intersect_line_plane(origin, origin + direction, cursor, floor) if abs(direction.z) > 0.1 else None
            if point is not None and (point - origin).dot(direction) > 0.0:
                self.plane = _plane_matrix(point, floor, Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)))
            else:
                closest = intersect_line_plane(origin, origin + direction, cursor, -direction) or cursor
                self.plane = _plane_matrix(closest, -direction, view_right, view_up)
        else:
            # Nothing under the cursor: view aligned plane through the targets
            center = sum((o.matrix_world.translation for o in self.targets), Vector()) / len(self.targets)
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

        # The handle lives in the closure too: if the operator is freed without _cleanup
        # (file load, Blender ending the modal) the callback removes itself instead of
        # raising ReferenceError on every redraw. Addon reloads are covered by
        # unregister_cutter_tool(), which removes every handle in _draw_handles.
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
        self._update_status(context)
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
            if self.alt:
                center, hx, hy = self.start, abs(d.x), abs(d.y)
            else:
                center, hx, hy = self.start + d * 0.5, abs(d.x) * 0.5, abs(d.y) * 0.5
            if self.shape == 'BOX':
                pts = [center + Vector(o) for o in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
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
            return tuple(sorted((0.0, self.depth)))  # sits on the surface and comes out of it
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

        if self.shape == 'CIRCLE' and self.operation != 'ADD':
            # Non destructive: a side profile spun by a Screw modifier, so segments stay editable.
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

    def _create_cutter(self, context):
        if self.operation == 'ADD':
            # A plain new object in the active collection, real geometry (no Screw) like Add Object
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
        if not self.live:
            return
        profile = self.profile()
        z = self.z_range(profile) if profile else None
        if z is None or (not self.targets and self.operation != 'ADD'):
            return
        if self.cutter is None:
            self._create_cutter(context)
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
        if not self.targets and self.operation != 'ADD':
            return {'CANCELLED'}  # switched from Add to a boolean with nothing to cut
        self.depth_amount = max(abs(self.depth), MIN_DEPTH)
        self.target_names = TARGET_SEPARATOR.join(o.name for o in self.targets)
        return self.execute(context)

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
            # Add comes out of the surface, cuts go in: mirror the depth so the mouse keeps working
            self.depth_ref += 2.0 * self.depth
            self.depth = -self.depth
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
        self._setup_depth_input()
        mouse_depth = self._mouse_depth(mouse)
        self.depth_ref = (mouse_depth - self.depth) if mouse_depth is not None else -self.depth
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

    def _modal(self, context, event):
        mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        changed = self._sync_from_tool(context)

        if event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_ALT', 'RIGHT_ALT', 'LEFT_CTRL', 'RIGHT_CTRL'} \
                or event.type == 'MOUSEMOVE':
            if self.phase == 'DRAW' and (self.shift, self.alt) != (event.shift, event.alt):
                self.shift, self.alt = event.shift, event.alt
                changed = True

        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            return self._cancel(context)

        if event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'NDOF_MOTION'}:
            return {'PASS_THROUGH'}

        key_press = event.value == 'PRESS' and not (event.ctrl or event.alt or event.oskey)

        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'NUMPAD_PLUS', 'NUMPAD_MINUS'}:
            if self.shape != 'CIRCLE':
                return {'PASS_THROUGH'}
            if event.value == 'PRESS':  # wheel events also arrive as PRESS
                step = 1 if event.type in {'WHEELUPMOUSE', 'NUMPAD_PLUS'} else -1
                segments = max(3, min(256, self.segments + step * (4 if event.ctrl else 1)))
                changed |= self._set_setting(context, "segments", segments)

        elif event.type in OPERATION_KEYS and key_press:
            changed |= self._set_setting(context, "operation", OPERATION_KEYS[event.type])

        elif event.type in SHAPE_KEYS and key_press:
            changed |= self._set_setting(context, "shape", SHAPE_KEYS[event.type])

        elif event.type == 'L' and key_press:
            changed |= self._set_setting(context, "live", not self.live)

        elif event.type == 'A' and key_press and self.operation != 'ADD':
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
                d = self._mouse_depth(mouse)
                if d is not None:
                    depth = d - self.depth_ref
                    if event.ctrl:
                        depth = self._snap(depth)
                    if self.operation == 'ADD':
                        depth = max(depth, MIN_DEPTH)  # Add only comes out of the surface
                    else:
                        depth = min(depth, -MIN_DEPTH)  # only ever away from the camera, never toward it
                    if depth != self.depth:
                        self.depth = depth
                        changed = True

        elif event.type == 'LEFTMOUSE':
            if event.alt and event.value == 'PRESS' and (self.shape == 'NGON' or self.phase == 'EXTRUDE'):
                return {'PASS_THROUGH'}  # Alt + LMB navigation
            if self.phase == 'DRAW' and self.shape != 'NGON' and event.value == 'RELEASE':
                if not self.has_dragged:
                    self._cancel(context)
                    return self._click_select(context, event)
                return self._end_draw(context, mouse)
            if self.phase == 'DRAW' and self.shape == 'NGON' and event.value == 'PRESS':
                first = location_3d_to_region_2d(self.region, self.rv3d, self.plane @ self.points[0].to_3d())
                if len(self.points) >= 3 and first is not None and (mouse - first).length < NGON_CLOSE_RADIUS:
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

    def _status_items(self):
        """(icons, text) pairs for the status bar, Blender style: key icons followed by a label."""
        items = []
        if self.phase == 'DRAW':
            if self.shape == 'NGON':
                items += [(('MOUSE_LMB',), "Add Point"), (('EVENT_BACKSPACE',), "Remove Point"),
                          (('EVENT_RETURN',), "Close")]
            else:
                items += [(('MOUSE_LMB_DRAG',), "Draw"),
                          (('EVENT_SHIFT',), "Ellipse" if self.shape == 'CIRCLE' else "Square"),
                          (('EVENT_ALT',), "From Center")]
        else:
            items += [(('MOUSE_LMB',), "Confirm"), (('MOUSE_MOVE',), "Depth")]
        items.append((('EVENT_CTRL',), "Snap"))
        if self.shape == 'CIRCLE':
            items.append((('MOUSE_MMB_SCROLL',), f"Segments: {self.segments}"))
        items += [
            (('EVENT_ONEKEY', 'EVENT_FIVEKEY'), OPERATION_NAMES[self.operation]),
            (('EVENT_B', 'EVENT_C', 'EVENT_N'), self.shape.title()),
            (('EVENT_L',), f"Live: {'On' if self.live else 'Off'}"),
        ]
        if self.operation != 'ADD':
            items.append((('EVENT_A',), f"Apply: {'On' if self.apply else 'Off'}"))
        items += [
            (('EVENT_D',), "Options"),
            (('MOUSE_RMB',), "Cancel"),
        ]
        return items

    def _update_status(self, context):
        op = self.operation.title()
        items = self._status_items()

        def draw_status(header, _context):
            row = header.layout.row(align=True)
            for icons, text in items:
                for icon in icons[:-1]:
                    row.label(text="", icon=icon)
                row.label(text=text, icon=icons[-1])
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
        if self.live:
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
            fill = batch_for_shader(fill_shader, 'TRIS', {"pos": ring}, indices=tris)
        else:
            bottom = [plane @ Vector((p.x, p.y, z[0])) for p in profile]
            top = [plane @ Vector((p.x, p.y, z[1])) for p in profile]
            cap = tessellate_polygon([top])
            coords = top + bottom
            tris = list(cap) + [(a + n, b + n, c + n) for a, b, c in cap]
            lines = []
            for i in range(n):
                j = (i + 1) % n
                tris += [(i, j, n + j), (i, n + j, n + i)]
                lines += (top[i], top[j], bottom[i], bottom[j])
                if self.shape != 'CIRCLE' or i % max(1, n // 8) == 0:
                    lines += (top[i], bottom[i])
            fill = batch_for_shader(fill_shader, 'TRIS', {"pos": coords}, indices=tris)

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
            for depth_test, fill_alpha, line_alpha, width in (('NONE', 0.06, 0.35, 1.5), ('LESS_EQUAL', 0.18, 0.95, 2.0)):
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
        keys = {v: k for k, v in OPERATION_KEYS.items()}
        number = {'ONE': "1", 'TWO': "2", 'THREE': "3", 'FOUR': "4", 'FIVE': "5"}
        name = OPERATION_NAMES[properties.operation]
        if properties.operation == 'ADD':
            name = "Add a new object instead of cutting"
        return f"{name}  ({number[keys[properties.operation]]} while cutting)"

    def execute(self, context):
        props = _tool_props(context)
        if props is None:
            return {'CANCELLED'}
        props.operation = self.operation
        return {'FINISHED'}


def draw_cutter_options(layout, props):
    """Tool settings with their modal shortcuts, used by the D popup."""
    col = layout.column(align=True)
    col.label(text="Operation    1 - 5")
    draw_operation_buttons(col, props, scale=1.4)

    col = layout.column(align=True)
    col.label(text="Shape    B / C / N")
    row = col.row(align=True)
    row.scale_x = row.scale_y = 1.4
    for identifier, _name, _desc, icon, _num in SHAPE_ITEMS:
        row.prop_enum(props, "shape", identifier, text="", icon=icon)
    if props.shape == 'CIRCLE':
        col.prop(props, "segments", text="Segments    Wheel")

    is_add = props.operation == 'ADD'
    col = layout.column(align=True)
    if not is_add:
        col.prop(props, "solver", text="Solver")
    col.prop(props, "align", text="Align")
    col.prop(props, "snap_increment", text="Snap  Ctrl")

    row = layout.row()
    row.prop(props, "live", text="Live  L")
    if not is_add:
        row.prop(props, "apply", text="Apply  A")


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
        draw_cutter_options(self.layout, props)

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
        "Add mode (5) makes a new object from the shape instead"
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
        is_add = props.operation == 'ADD'
        layout.prop(props, "align", text="")
        if not is_add:
            layout.prop(props, "solver", text="")
        layout.prop(props, "snap_increment")
        layout.prop(props, "live")
        if not is_add:
            layout.prop(props, "apply")


classes = (Cutter, CutterSetOperation, KEYOPS_MT_cutter_operation, CutterToolOptions)

# Draw handles of running Cutter operators, so a reload mid-cut can't leave one behind
_draw_handles = set()


def register_cutter_tool():
    from .merge_tool import remove_stale_tool

    for cls in classes:
        bpy.utils.register_class(cls)

    try:
        if not hasattr(WorkSpaceCutter, "_bl_tool"):
            remove_stale_tool(WorkSpaceCutter)
            bpy.utils.register_tool(WorkSpaceCutter, after={"builtin.measure"}, separator=True, group=False)
    except Exception as e:
        print(f"Failed to register WorkSpaceCutter: {e}")


def unregister_cutter_tool():
    for h in list(_draw_handles):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
        except ValueError:
            pass
    _draw_handles.clear()

    try:
        if hasattr(WorkSpaceCutter, "_bl_tool"):
            bpy.utils.unregister_tool(WorkSpaceCutter)
    except Exception as e:
        print(f"Failed to unregister WorkSpaceCutter: {e}")

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
