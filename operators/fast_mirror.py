import bpy
import bmesh
import gpu
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils
from mathutils import Vector, Matrix
from ..utils.utilities import get_blender_key_icon

MIRROR_MODIFIER_NAME = "KeyOps Mirror"
AXES = "XYZ"
AXIS_COLORS = {
    'X': (1.0, 0.21, 0.33),
    'Y': (0.54, 0.86, 0.0),
    'Z': (0.17, 0.56, 1.0),
}

DEFAULT_MODE = 'MODIFIER_NO_BISECT'

MODE_ITEMS = [
    ('MODIFIER_NO_BISECT', "Mirror", "Add or update the KeyOps Mirror modifier with clipping, without bisect", 'MOD_MIRROR', 0),
    ('NEW_MODIFIER', "New Mirror", "Always add a new Mirror modifier with bisect and clipping", 'ADD', 1),
    ('BISECT_ONLY', "Bisect", "Cut the mesh in half on the axis plane (applied, no modifier)", 'SNAP_FACE_CENTER', 2),
    ('BISECT', "Bisect + Mirror", "Cut the mesh in half on the axis plane, then add a Mirror modifier with clipping", 'MESH_PLANE', 3),
    ('SYMMETRIZE', "Symmetrize", "Symmetrize the mesh geometry (applied, no modifier)", 'ARROW_LEFTRIGHT', 4),
    ('FLIP', "Flip", "Flip the mesh across the axis plane. Face winding, custom normals and shape keys are kept correct", 'UV_SYNC_SELECT', 5),
]

# kind: what is done, bisect/clip: Mirror modifier settings, modifier: add a Mirror modifier after bisecting
MODE_PRESETS = {
    'BISECT': {'kind': 'BISECT', 'modifier': True, 'clip': True},
    'BISECT_ONLY': {'kind': 'BISECT', 'modifier': False, 'clip': False},
    'MODIFIER_NO_BISECT': {'kind': 'MODIFIER', 'new': False, 'bisect': False, 'clip': True},
    'NEW_MODIFIER': {'kind': 'MODIFIER', 'new': True, 'bisect': True, 'clip': True},
    'SYMMETRIZE': {'kind': 'SYMMETRIZE'},
    'FLIP': {'kind': 'FLIP'},
}

RED = (0.9, 0.3, 0.3)
GREY = (0.5, 0.5, 0.5)

# Preview plane color per mode: red = destructive cut, green = adds, blue = modifier, orange = symmetrize, purple = flip
MODE_COLORS = {
    'BISECT': RED,
    'BISECT_ONLY': RED,
    'MODIFIER_NO_BISECT': (0.3, 0.6, 0.95),
    'NEW_MODIFIER': (0.35, 0.8, 0.4),
    'SYMMETRIZE': (0.95, 0.65, 0.25),
    'FLIP': (0.7, 0.45, 0.9),
}

# Hover preview: only actual bisect cuts warn in red. Modifier-based mirrors stay neutral grey,
# since they do not cut the mesh immediately.
CUTTING_MODES = {'BISECT', 'BISECT_ONLY'}

# Preview block behavior per mode.
# side: draw only the affected side of the mesh bounds
# full: draw the whole mesh bounds
BOX_PREVIEW_KIND = {
    'BISECT': 'side',
    'BISECT_ONLY': 'side',
    'MODIFIER_NO_BISECT': 'side',
    'NEW_MODIFIER': 'side',
    'SYMMETRIZE': 'side',
    'FLIP': 'side',
}

# Modes reachable with modifier keys on a block click, whatever mode is selected: ((ctrl, shift, alt), label, mode)
MODIFIER_MODES = [
    ((True, False, False), "Ctrl", 'BISECT'),
    ((False, True, False), "Shift", 'NEW_MODIFIER'),
    ((False, False, True), "Alt", 'SYMMETRIZE'),
    ((True, True, False), "Ctrl+Shift", 'FLIP'),
]

MODIFIER_EVENT_MAP = {
    'LEFT_CTRL': 'ctrl',
    'RIGHT_CTRL': 'ctrl',
    'LEFT_SHIFT': 'shift',
    'RIGHT_SHIFT': 'shift',
    'LEFT_ALT': 'alt',
    'RIGHT_ALT': 'alt',
}


def get_modifier_mode(ctrl, shift, alt, fallback_mode):
    for (modifier_ctrl, modifier_shift, modifier_alt), _label, mode in MODIFIER_MODES:
        if (ctrl, shift, alt) == (modifier_ctrl, modifier_shift, modifier_alt):
            return mode
    return fallback_mode


def get_preview_mode(wm, ctrl=False, shift=False, alt=False):
    return get_modifier_mode(ctrl, shift, alt, wm.keyops_fast_mirror_mode)


def get_preview_mode_from_wm_state(wm):
    return get_preview_mode(
        wm,
        getattr(wm, "keyops_fast_mirror_ctrl", False),
        getattr(wm, "keyops_fast_mirror_shift", False),
        getattr(wm, "keyops_fast_mirror_alt", False),
    )


def set_watcher_modifier_state(wm, ctrl=False, shift=False, alt=False):
    wm.keyops_fast_mirror_ctrl = bool(ctrl)
    wm.keyops_fast_mirror_shift = bool(shift)
    wm.keyops_fast_mirror_alt = bool(alt)


def update_watcher_modifier_state_from_event(wm, event):
    key = MODIFIER_EVENT_MAP.get(event.type)
    if key is not None and event.value in {'PRESS', 'RELEASE'}:
        setattr(wm, f"keyops_fast_mirror_{key}", event.value == 'PRESS')
        return

    # Keep state robust when Blender forwards non-modifier events with updated flags.
    wm.keyops_fast_mirror_ctrl = bool(event.ctrl)
    wm.keyops_fast_mirror_shift = bool(event.shift)
    wm.keyops_fast_mirror_alt = bool(event.alt)


def set_preview_mode(context, mode, redraw=True):
    if context is None:
        return

    wm = context.window_manager
    if wm.keyops_fast_mirror_preview_mode == mode:
        return

    wm.keyops_fast_mirror_preview_mode = mode
    if redraw:
        redraw_view3d_areas(context)


def apply_temporary_mode_override(context):
    """Temporarily switch the active mode while modifier keys are held, then restore it."""
    if context is None:
        return

    wm = context.window_manager
    has_modifier = (
        getattr(wm, "keyops_fast_mirror_ctrl", False)
        or getattr(wm, "keyops_fast_mirror_shift", False)
        or getattr(wm, "keyops_fast_mirror_alt", False)
    )

    override_active = getattr(wm, "keyops_fast_mirror_mode_override_active", False)
    base_mode = getattr(wm, "keyops_fast_mirror_mode_before_override", wm.keyops_fast_mirror_mode)

    if not has_modifier:
        if override_active:
            wm.keyops_fast_mirror_mode = base_mode
            wm.keyops_fast_mirror_mode_override_active = False
        return

    target_mode = get_modifier_mode(
        wm.keyops_fast_mirror_ctrl,
        wm.keyops_fast_mirror_shift,
        wm.keyops_fast_mirror_alt,
        base_mode if override_active else wm.keyops_fast_mirror_mode,
    )

    if not override_active:
        if target_mode != wm.keyops_fast_mirror_mode:
            wm.keyops_fast_mirror_mode_before_override = wm.keyops_fast_mirror_mode
            wm.keyops_fast_mirror_mode_override_active = True
            wm.keyops_fast_mirror_mode = target_mode
        return

    if target_mode == base_mode:
        wm.keyops_fast_mirror_mode = base_mode
        wm.keyops_fast_mirror_mode_override_active = False
        return

    if wm.keyops_fast_mirror_mode != target_mode:
        wm.keyops_fast_mirror_mode = target_mode


def build_fast_mirror_status_text(wm):
    base_mode = get_mode_label(wm.keyops_fast_mirror_mode)
    shortcuts = [f"Click: {base_mode}"]
    shortcuts += [f"{label}: {get_mode_label(mode)}" for _keys, label, mode in MODIFIER_MODES]
    shortcuts += ["D: Options", "Alt X: Toggle Gizmo"]
    return "Fast Mirror | " + " | ".join(shortcuts)


def update_fast_mirror_status_text(context):
    if context is None or context.workspace is None:
        return

    wm = context.window_manager
    if getattr(wm, "keyops_fast_mirror_gizmo", False):
        context.workspace.status_text_set(build_fast_mirror_status_text(wm))
    else:
        context.workspace.status_text_set(None)


def redraw_view3d_areas(context):
    if context is None or context.screen is None:
        return
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def find_view3d_override(context):
    """Return an override dict targeting a VIEW_3D WINDOW region, or None."""
    if context is None:
        return None

    wm = context.window_manager
    windows = []
    if context.window is not None:
        windows.append(context.window)
    windows.extend(window for window in wm.windows if window not in windows)

    for window in windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            region = next((region for region in area.regions if region.type == 'WINDOW'), None)
            if region is None:
                continue
            return {
                "window": window,
                "screen": screen,
                "area": area,
                "region": region,
            }
    return None


def invoke_fast_mirror_preview_watcher(context):
    """Start the watcher from a guaranteed VIEW_3D context."""
    if context is None:
        return False

    wm = context.window_manager
    # A stale flag can survive if Blender interrupts modal flow; allow restart.
    wm.keyops_fast_mirror_modal_running = False

    override = find_view3d_override(context)
    if override is None:
        return False

    try:
        with context.temp_override(**override):
            result = bpy.ops.keyops.fast_mirror_preview_watcher('INVOKE_DEFAULT')
    except RuntimeError:
        return False

    return 'RUNNING_MODAL' in result or 'FINISHED' in result


def on_fast_mirror_mode_changed(_self, context):
    if context is not None:
        wm = context.window_manager
        set_preview_mode(context, wm.keyops_fast_mirror_mode, redraw=False)
    update_fast_mirror_status_text(context)
    redraw_view3d_areas(context)


# (gizmo, axis_index, keep_negative) of the current gizmo group, read by the draw handlers
active_arrows = []
last_hovered_arrow = None
last_modal_hovered_arrow = None

# Handler handles live in driver_namespace so they survive module reloads and stale handlers can be removed
HANDLERS_KEY = "keyops_fast_mirror_handlers"

registered_fast_mirror_classes = []


def get_mode_label(mode):
    for identifier, name, *_ in MODE_ITEMS:
        if identifier == mode:
            return name
    return mode


def get_target_objects(context):
    if context.mode == 'EDIT_MESH':
        return [obj for obj in context.objects_in_mode_unique_data if obj.type == 'MESH']

    objs = [obj for obj in context.selected_objects if obj.type == 'MESH']
    active = context.active_object
    if active is not None and active.type == 'MESH' and active not in objs:
        objs.append(active)
    return objs


def move_before_weighted_normal(obj, mod):
    modifiers = obj.modifiers
    names = [m.name for m in modifiers]
    mod_index = names.index(mod.name)
    for index, other in enumerate(modifiers):
        if other.type == 'WEIGHTED_NORMAL' and index < mod_index:
            modifiers.move(mod_index, index)
            return


def get_or_create_mirror_modifier(obj, new_modifier, mirror_object):
    if not new_modifier:
        for mod in obj.modifiers:
            if mod.type == 'MIRROR' and mod.name == MIRROR_MODIFIER_NAME and mod.mirror_object == mirror_object:
                return mod

    mod = obj.modifiers.new("Mirror" if new_modifier else MIRROR_MODIFIER_NAME, 'MIRROR')
    for i in range(3):
        mod.use_axis[i] = False
    mod.use_clip = True
    mod.mirror_object = mirror_object
    mod.show_on_cage = False
    move_before_weighted_normal(obj, mod)
    return mod


def set_modifier_axis(mod, axis_index, keep_negative, use_bisect, toggle=True):
    """Enable the axis on the modifier. Clicking the same state again turns the axis off."""
    already_set = (
        mod.use_axis[axis_index]
        and mod.use_bisect_axis[axis_index] == use_bisect
        and mod.use_bisect_flip_axis[axis_index] == (keep_negative and use_bisect)
    )
    if toggle and already_set:
        mod.use_axis[axis_index] = False
        mod.use_bisect_axis[axis_index] = False
        mod.use_bisect_flip_axis[axis_index] = False
        return

    mod.use_axis[axis_index] = True
    mod.use_bisect_axis[axis_index] = use_bisect
    mod.use_bisect_flip_axis[axis_index] = keep_negative and use_bisect


def edit_mesh_geometry(obj, is_edit_mode, operation):
    """Run operation(bm) on the mesh of obj and write the result back."""
    me = obj.data
    if is_edit_mode:
        bm = bmesh.from_edit_mesh(me)
    else:
        bm = bmesh.new()
        bm.from_mesh(me)

    operation(bm)

    if is_edit_mode:
        bmesh.update_edit_mesh(me, destructive=True)
    else:
        bm.to_mesh(me)
        bm.free()
        me.update()


def bisect_mesh(obj, axis_index, keep_negative, is_edit_mode):
    plane_no = Vector((0.0, 0.0, 0.0))
    plane_no[axis_index] = 1.0

    def operation(bm):
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(
            bm,
            geom=geom,
            dist=0.00001,
            plane_co=(0.0, 0.0, 0.0),
            plane_no=plane_no,
            clear_inner=not keep_negative,
            clear_outer=keep_negative,
        )

    edit_mesh_geometry(obj, is_edit_mode, operation)


def symmetrize_mesh(obj, axis_index, keep_negative, is_edit_mode):
    direction = ("-" if keep_negative else "") + AXES[axis_index]

    def operation(bm):
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.symmetrize(bm, input=geom, direction=direction, dist=0.00001)

    edit_mesh_geometry(obj, is_edit_mode, operation)


def flip_objects(objs, axis_index, is_edit_mode):
    """Flip the geometry across the local axis plane.

    The mesh is transformed with a reflection and the face winding is reversed afterwards, so
    face normals, custom normals, UVs and shape keys all stay consistent.
    """
    scale = Vector((1.0, 1.0, 1.0, 1.0))
    scale[axis_index] = -1.0
    matrix = Matrix.Diagonal(scale)

    if is_edit_mode:
        bpy.ops.object.mode_set(mode='OBJECT')
    try:
        processed = set()
        for obj in objs:
            me = obj.data
            pointer = me.as_pointer()
            if pointer in processed:
                continue
            processed.add(pointer)

            me.transform(matrix, shape_keys=True)
            me.flip_normals()
            me.update()
    finally:
        if is_edit_mode:
            bpy.ops.object.mode_set(mode='EDIT')


# ---------------------------------------------------------------------------
# Hover preview
# ---------------------------------------------------------------------------

LINE_WIDTH = 1.5


def _draw_batches(shader, line_shader, color, fill_batch, line_batch, fill_alpha, line_alpha):
    shader.bind()
    shader.uniform_float("color", (color[0], color[1], color[2], fill_alpha))
    fill_batch.draw(shader)
    if line_batch is not None:
        # Polyline shader gives smooth (anti-aliased) edges
        region = bpy.context.region
        line_shader.bind()
        line_shader.uniform_float("viewportSize", (region.width, region.height))
        line_shader.uniform_float("lineWidth", LINE_WIDTH)
        line_shader.uniform_float("color", (color[0], color[1], color[2], line_alpha))
        line_batch.draw(line_shader)


def draw_box(shader, line_shader, lo, hi, color, fill_alpha=0.03, line_alpha=0.12):
    verts = [
        Vector((hi[0] if i & 1 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 4 else lo[2]))
        for i in range(8)
    ]
    tris = []
    for axis in range(3):
        for side in (0, 1):
            i0, i1, i2, i3 = [i for i in range(8) if ((i >> axis) & 1) == side]
            tris += [(i0, i1, i3), (i0, i3, i2)]
    edges = [(a, b) for a in range(8) for b in range(a + 1, 8) if bin(a ^ b).count("1") == 1]
    fill = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=tris)
    lines = batch_for_shader(line_shader, 'LINES', {"pos": verts}, indices=edges)
    _draw_batches(shader, line_shader, color, fill, lines, fill_alpha, line_alpha)


def get_hovered_gizmo():
    """Return (gizmo, axis_index, keep_negative) of the highlighted gizmo, or None."""
    for gizmo, axis_index, keep_negative in active_arrows:
        try:
            if gizmo.is_highlight:
                return gizmo, axis_index, keep_negative
        except ReferenceError:
            active_arrows.clear()
            return None
    return None


def get_hovered_arrow():
    """Return (axis_index, keep_negative) of the highlighted gizmo, or None."""
    hovered = get_hovered_gizmo()
    return None if hovered is None else hovered[1:]


def is_preview_modifier_active(wm):
    return (
        getattr(wm, "keyops_fast_mirror_ctrl", False)
        or getattr(wm, "keyops_fast_mirror_shift", False)
        or getattr(wm, "keyops_fast_mirror_alt", False)
    )


def update_watcher_mouse_state(wm, event):
    mouse_x = getattr(event, "mouse_region_x", -1)
    mouse_y = getattr(event, "mouse_region_y", -1)
    wm.keyops_fast_mirror_mouse_x = int(mouse_x)
    wm.keyops_fast_mirror_mouse_y = int(mouse_y)


def get_hovered_arrow_from_mouse(context, wm, max_distance_px=64.0):
    region = context.region
    rv3d = context.region_data
    if region is None or rv3d is None:
        return None

    mouse = Vector((
        float(getattr(wm, "keyops_fast_mirror_mouse_x", -1)),
        float(getattr(wm, "keyops_fast_mirror_mouse_y", -1)),
    ))
    if mouse.x < 0.0 or mouse.y < 0.0:
        return None

    best = None
    best_distance = max_distance_px
    for gizmo, axis_index, keep_negative in active_arrows:
        try:
            world_pos = gizmo.matrix_basis.translation
        except ReferenceError:
            continue

        screen_pos = view3d_utils.location_3d_to_region_2d(region, rv3d, world_pos)
        if screen_pos is None:
            continue

        distance = (screen_pos - mouse).length
        if distance <= best_distance:
            best_distance = distance
            best = (axis_index, keep_negative)
    return best


def get_hovered_arrow_from_mouse_coords(region, rv3d, mouse_x, mouse_y, max_distance_px=64.0):
    if region is None or rv3d is None:
        return None
    if mouse_x < 0 or mouse_y < 0:
        return None

    mouse = Vector((float(mouse_x), float(mouse_y)))
    best = None
    best_distance = max_distance_px
    for gizmo, axis_index, keep_negative in active_arrows:
        try:
            world_pos = gizmo.matrix_basis.translation
        except ReferenceError:
            continue

        screen_pos = view3d_utils.location_3d_to_region_2d(region, rv3d, world_pos)
        if screen_pos is None:
            continue

        distance = (screen_pos - mouse).length
        if distance <= best_distance:
            best_distance = distance
            best = (axis_index, keep_negative)
    return best


def draw_plane(shader, line_shader, axis_index, lo, hi, color, fill_alpha=0.2, line_alpha=0.8):
    b, c = [i for i in range(3) if i != axis_index]
    margin = [(hi[i] - lo[i]) * 0.1 for i in range(3)]
    corners = (
        (lo[b] - margin[b], lo[c] - margin[c]),
        (hi[b] + margin[b], lo[c] - margin[c]),
        (hi[b] + margin[b], hi[c] + margin[c]),
        (lo[b] - margin[b], hi[c] + margin[c]),
    )
    verts = []
    for vb, vc in corners:
        v = Vector((0.0, 0.0, 0.0))
        v[b], v[c] = vb, vc
        verts.append(v)
    fill = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=[(0, 1, 2), (0, 2, 3)])
    lines = batch_for_shader(line_shader, 'LINES', {"pos": verts}, indices=[(0, 1), (1, 2), (2, 3), (3, 0)])
    _draw_batches(shader, line_shader, color, fill, lines, fill_alpha, line_alpha)


def _box_with_axis_range(bb_min, bb_max, axis_index, a, b):
    lo, hi = bb_min.copy(), bb_max.copy()
    lo[axis_index], hi[axis_index] = min(a, b), max(a, b)
    return lo, hi


def get_view_facing_tint(obj, axis_index, keep_negative, rv3d):
    """Return a 0..1 factor based on whether the selected side faces the current view."""
    center = Vector((sum(corner[i] for corner in obj.bound_box) / 8.0 for i in range(3)))
    normal = Vector((0.0, 0.0, 0.0))
    normal[axis_index] = 1.0 if keep_negative else -1.0
    normal = obj.matrix_world.to_3x3() @ normal

    view_matrix = rv3d.view_matrix.inverted()
    camera_loc = view_matrix.translation
    view_dir = (center - camera_loc)
    if view_dir.length_squared > 0.0:
        view_dir.normalize()
    else:
        view_dir = Vector((0.0, 0.0, 1.0))

    facing = normal.dot(view_dir)
    facing = max(0.0, min(1.0, (facing * 0.5 + 0.5)))
    return 1.0 - (0.0 + facing * 0.9)


def draw_fast_mirror_visuals():
    global last_hovered_arrow, last_modal_hovered_arrow

    context = bpy.context
    wm = context.window_manager
    if not wm.keyops_fast_mirror_gizmo:
        last_hovered_arrow = None
        return

    hovered = get_hovered_arrow()
    if hovered is not None:
        last_hovered_arrow = hovered
    elif is_preview_modifier_active(wm):
        hovered = last_modal_hovered_arrow or last_hovered_arrow
        if hovered is None:
            hovered = get_hovered_arrow_from_mouse(context, wm)
            if hovered is not None:
                last_hovered_arrow = hovered

    obj = context.active_object
    if hovered is None or obj is None or obj.type != 'MESH':
        return

    preview_mode = getattr(wm, "keyops_fast_mirror_preview_mode", wm.keyops_fast_mirror_mode)
    axis_index, keep_negative = hovered
    corners = [Vector(corner) for corner in obj.bound_box]
    bb_min = Vector((min(c[i] for c in corners) for i in range(3)))
    bb_max = Vector((max(c[i] for c in corners) for i in range(3)))
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    line_shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    rv3d = context.region_data

    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('NONE')
    gpu.state.face_culling_set('NONE')
    gpu.matrix.push()
    gpu.matrix.multiply_matrix(obj.matrix_world)

    # Keep block/cube preview neutral: red only when the active preview mode performs a cut.
    preview_box_color = RED if preview_mode in CUTTING_MODES else GREY
    box_kind = BOX_PREVIEW_KIND.get(preview_mode, 'side')
    if preview_mode in CUTTING_MODES:
        box_fill_alpha, box_line_alpha = 0.05, 0.2
    else:
        box_fill_alpha, box_line_alpha = 0.035, 0.12

    if box_kind == 'full':
        draw_box(shader, line_shader, bb_min, bb_max, preview_box_color, fill_alpha=box_fill_alpha, line_alpha=box_line_alpha)
    else:
        if keep_negative and bb_max[axis_index] > 0.0:
            lo, hi = _box_with_axis_range(bb_min, bb_max, axis_index, 0.0, bb_max[axis_index])
            draw_box(shader, line_shader, lo, hi, preview_box_color, fill_alpha=box_fill_alpha, line_alpha=box_line_alpha)
        elif not keep_negative and bb_min[axis_index] < 0.0:
            lo, hi = _box_with_axis_range(bb_min, bb_max, axis_index, bb_min[axis_index], 0.0)
            draw_box(shader, line_shader, lo, hi, preview_box_color, fill_alpha=box_fill_alpha, line_alpha=box_line_alpha)

    color = MODE_COLORS.get(preview_mode, AXIS_COLORS[AXES[axis_index]])
    if rv3d is not None:
        center = Vector((sum(corner[i] for corner in obj.bound_box) / 8.0 for i in range(3)))
        normal = Vector((0.0, 0.0, 0.0))
        normal[axis_index] = 1.0 if keep_negative else -1.0
        normal = obj.matrix_world.to_3x3() @ normal

        view_matrix = rv3d.view_matrix.inverted()
        camera_loc = view_matrix.translation
        view_dir = (center - camera_loc)
        if view_dir.length_squared > 0.0:
            view_dir.normalize()
        else:
            view_dir = Vector((0.0, 0.0, 1.0))

        facing = normal.dot(view_dir)
        color = tuple(channel * (0.55 + 0.45 * max(0.0, min(1.0, (facing * 0.5 + 0.5)))) for channel in color)
        if facing <= 0.0:
            fill_alpha, line_alpha = 0.08, 0.22
        else:
            fill_alpha, line_alpha = 0.18, 0.7
    else:
        fill_alpha, line_alpha = 0.18, 0.7

    draw_plane(shader, line_shader, axis_index, bb_min, bb_max, color, fill_alpha=fill_alpha, line_alpha=line_alpha)

    gpu.matrix.pop()
    gpu.state.blend_set('NONE')


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class FastMirrorApply(bpy.types.Operator):
    bl_idname = "keyops.fast_mirror_apply"
    bl_label = "Fast Mirror"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        side = "-" if properties.keep_negative else "+"
        axis = properties.axis
        lines = [f"Mirror on {axis}, keeping the {side}{axis} side"]
        lines.append(f"Click: {get_mode_label(context.window_manager.keyops_fast_mirror_mode)}")
        lines += [f"{label}: {get_mode_label(mode)}" for _keys, label, mode in MODIFIER_MODES]
        return "\n".join(lines)

    axis: bpy.props.EnumProperty(name="Axis", items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")], default='X') # type: ignore
    keep_negative: bpy.props.BoolProperty(name="Keep Negative Side", description="Keep the negative side and mirror it onto the positive side", default=False) # type: ignore
    mode: bpy.props.EnumProperty(name="Mode", items=MODE_ITEMS, default=DEFAULT_MODE) # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT', 'EDIT_MESH'} and bool(get_target_objects(context))

    def invoke(self, context, event):
        wm = context.window_manager
        self.mode = getattr(wm, "keyops_fast_mirror_mode_before_override", wm.keyops_fast_mirror_mode) if getattr(wm, "keyops_fast_mirror_mode_override_active", False) else wm.keyops_fast_mirror_mode

        # Modifier keys override the mode, whatever mode is currently selected.
        self.mode = get_modifier_mode(event.ctrl, event.shift, event.alt, self.mode)
        wm.keyops_fast_mirror_preview_mode = self.mode

        result = self.execute(context)

        # Hide the gizmo after use, Alt X brings it back
        wm.keyops_fast_mirror_gizmo = False
        update_fast_mirror_status_text(context)
        redraw_view3d_areas(context)
        return result

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "axis")
        layout.prop(self, "keep_negative")
        layout.prop(self, "mode")

    def execute(self, context):
        objs = get_target_objects(context)
        if not objs:
            self.report({'WARNING'}, "No mesh object to mirror")
            return {'CANCELLED'}

        is_edit_mode = context.mode == 'EDIT_MESH'
        axis_index = AXES.index(self.axis)
        active = context.active_object
        preset = MODE_PRESETS[self.mode]

        if preset['kind'] == 'MODIFIER':
            new_modifier = preset['new']
            mirror_object = None
            targets = objs

            # Multiple selected objects: mirror them across the active object
            if not is_edit_mode and len(objs) > 1 and active in objs:
                mirror_object = active
                targets = [obj for obj in objs if obj != active]

            for obj in targets:
                mod = get_or_create_mirror_modifier(obj, new_modifier, mirror_object)
                set_modifier_axis(mod, axis_index, self.keep_negative, preset['bisect'], toggle=not new_modifier)
            return {'FINISHED'}

        if preset['kind'] == 'FLIP':
            flip_objects(objs, axis_index, is_edit_mode)
            return {'FINISHED'}

        processed = set()
        for obj in objs:
            pointer = obj.data.as_pointer()
            if pointer in processed:
                continue
            processed.add(pointer)

            if preset['kind'] == 'BISECT':
                bisect_mesh(obj, axis_index, self.keep_negative, is_edit_mode)
                if preset['modifier']:
                    mod = get_or_create_mirror_modifier(obj, False, None)
                    set_modifier_axis(mod, axis_index, False, False, toggle=False)
            elif preset['kind'] == 'SYMMETRIZE':
                symmetrize_mesh(obj, axis_index, self.keep_negative, is_edit_mode)

        return {'FINISHED'}


class FastMirror(bpy.types.Operator):
    bl_idname = "keyops.fast_mirror"
    bl_label = "Fast Mirror"
    bl_description = "Toggle the Mirror gizmo. Click a block to mirror on that axis and keep the side it is on. Click = selected mode, Ctrl = Bisect, Shift = New Modifier, Alt = Symmetrize, Ctrl+Shift = Flip. D opens the options"
    bl_options = {'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        enabling = not wm.keyops_fast_mirror_gizmo
        wm.keyops_fast_mirror_gizmo = enabling

        if enabling:
            wm.keyops_fast_mirror_mode_before_override = wm.keyops_fast_mirror_mode
            wm.keyops_fast_mirror_mode_override_active = False
            set_watcher_modifier_state(wm, ctrl=False, shift=False, alt=False)

        set_preview_mode(context, wm.keyops_fast_mirror_mode, redraw=False)
        update_fast_mirror_status_text(context)

        if enabling:
            if not invoke_fast_mirror_preview_watcher(context):
                self.report({'WARNING'}, "Fast Mirror preview watcher could not start (no 3D view context)")
        else:
            wm.keyops_fast_mirror_modal_running = False
            wm.keyops_fast_mirror_mode = wm.keyops_fast_mirror_mode_before_override
            wm.keyops_fast_mirror_mode_override_active = False

        redraw_view3d_areas(context)
        return {'FINISHED'}


class FastMirrorPreviewWatcher(bpy.types.Operator):
    bl_idname = "keyops.fast_mirror_preview_watcher"
    bl_label = "Fast Mirror Event Watcher"
    bl_description = "Handle Fast Mirror temporary preview mode from modifier keys"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def _stop(self, context):
        global last_hovered_arrow, last_modal_hovered_arrow

        wm = context.window_manager
        wm.keyops_fast_mirror_modal_running = False
        set_watcher_modifier_state(wm, ctrl=False, shift=False, alt=False)
        apply_temporary_mode_override(context)
        wm.keyops_fast_mirror_mouse_x = -1
        wm.keyops_fast_mirror_mouse_y = -1
        last_hovered_arrow = None
        last_modal_hovered_arrow = None
        set_preview_mode(context, wm.keyops_fast_mirror_mode, redraw=True)

    def modal(self, context, event):
        wm = context.window_manager
        if not wm.keyops_fast_mirror_gizmo or context.mode not in {'OBJECT', 'EDIT_MESH'}:
            self._stop(context)
            return {'CANCELLED'}

        if event.type == 'WINDOW_DEACTIVATE':
            set_watcher_modifier_state(wm, ctrl=False, shift=False, alt=False)
            apply_temporary_mode_override(context)
            set_preview_mode(context, wm.keyops_fast_mirror_mode, redraw=True)
            return {'PASS_THROUGH'}

        update_watcher_mouse_state(wm, event)
        update_watcher_modifier_state_from_event(wm, event)
        apply_temporary_mode_override(context)

        modal_hovered = get_hovered_arrow_from_mouse_coords(
            context.region,
            context.region_data,
            wm.keyops_fast_mirror_mouse_x,
            wm.keyops_fast_mirror_mouse_y,
        )
        if modal_hovered is not None:
            global last_modal_hovered_arrow
            last_modal_hovered_arrow = modal_hovered

        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            wm.keyops_fast_mirror_gizmo = False
            set_preview_mode(context, wm.keyops_fast_mirror_mode, redraw=False)
            update_fast_mirror_status_text(context)
            redraw_view3d_areas(context)
            self._stop(context)
            return {'FINISHED'}

        if event.type == 'D' and event.value == 'PRESS':
            bpy.ops.keyops.fast_mirror_options('INVOKE_DEFAULT')
            return {'RUNNING_MODAL'}

        set_preview_mode(context, get_preview_mode_from_wm_state(wm), redraw=True)
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        wm = context.window_manager
        if wm.keyops_fast_mirror_modal_running:
            return {'CANCELLED'}

        wm.keyops_fast_mirror_modal_running = True
        update_watcher_mouse_state(wm, event)
        set_watcher_modifier_state(wm, ctrl=event.ctrl, shift=event.shift, alt=event.alt)
        set_preview_mode(context, get_preview_mode_from_wm_state(wm), redraw=True)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class FastMirrorCancel(bpy.types.Operator):
    bl_idname = "keyops.fast_mirror_cancel"
    bl_label = "Cancel Fast Mirror"
    bl_description = "Close the Fast Mirror gizmo"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.window_manager.keyops_fast_mirror_gizmo

    def execute(self, context):
        wm = context.window_manager
        wm.keyops_fast_mirror_gizmo = False
        set_preview_mode(context, wm.keyops_fast_mirror_mode, redraw=False)
        update_fast_mirror_status_text(context)
        redraw_view3d_areas(context)
        return {'FINISHED'}


class FastMirrorOptions(bpy.types.Operator):
    bl_idname = "keyops.fast_mirror_options"
    bl_label = "Fast Mirror Options"
    bl_description = "Show all Fast Mirror options (only while the Mirror gizmo is active)"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.window_manager.keyops_fast_mirror_gizmo

    def invoke(self, context, event):
        bpy.ops.wm.call_panel('INVOKE_DEFAULT', name=FastMirrorOptionsPanel.bl_idname, keep_open=True)
        return {'FINISHED'}


def draw_fast_mirror_options(layout, wm, compact=False):
    """Draw every option at once, independent of the selected mode."""
    if compact:
        row = layout.row(align=True)
        row.prop(wm, "keyops_fast_mirror_mode", text="")
        return

    col = layout.column(align=True)
    col.label(text="Mode")
    col.prop(wm, "keyops_fast_mirror_mode", expand=True)

    col = layout.column(align=True)
    for _keys, label, mode in MODIFIER_MODES:
        row = col.row(align=True)
        for key_name in label.split('+'):
            icon_name = get_blender_key_icon(key_name.strip())
            if icon_name:
                row.label(icon=icon_name)
            else:
                row.label(text=key_name.strip())
        row.label(text=f"  {get_mode_label(mode)}")

    row = col.row(align=True)
    row.label(icon='EVENT_D', text="Options")
    row.label(icon='EVENT_ALT', text="")
    row.label(icon='EVENT_X', text="Toggle Gizmo")


def draw_fast_mirror_panel(layout, context):
    wm = context.window_manager
    box = layout.box()
    box.label(text="Mirror", icon='MOD_MIRROR')
    row = box.row(align=True)
    row.scale_y = 1.3
    row.operator("keyops.fast_mirror", text="Mirror Gizmo (Alt X)", icon='MOD_MIRROR', depress=wm.keyops_fast_mirror_gizmo)
    draw_fast_mirror_options(box.column(), wm)


def draw_fast_mirror_tool_header(layout, wm):
    """Mirror options for the active tool settings header (top left of the viewport)."""
    row = layout.row(align=True)
    row.label(text="Mirror", icon='MOD_MIRROR')
    row.prop(wm, "keyops_fast_mirror_mode", expand=True)


_original_tool_settings_draw = None


def _tool_settings_draw_with_mirror(self, context):
    wm = context.window_manager
    if getattr(wm, "keyops_fast_mirror_gizmo", False):
        draw_fast_mirror_tool_header(self.layout, wm)
        return
    _original_tool_settings_draw(self, context)


def patch_toolbar():
    """Replace the active tool settings in the tool header with the mirror options while the gizmo is active."""
    global _original_tool_settings_draw
    header = bpy.types.VIEW3D_HT_tool_header
    if _original_tool_settings_draw is None:
        _original_tool_settings_draw = header.draw_tool_settings
    header.draw_tool_settings = _tool_settings_draw_with_mirror


def unpatch_toolbar():
    global _original_tool_settings_draw
    if _original_tool_settings_draw is not None:
        bpy.types.VIEW3D_HT_tool_header.draw_tool_settings = _original_tool_settings_draw
        _original_tool_settings_draw = None


class FastMirrorOptionsPanel(bpy.types.Panel):
    bl_idname = "KEYOPS_PT_fast_mirror_options"
    bl_label = "Fast Mirror"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'

    def draw(self, context):
        layout = self.layout
        layout.ui_units_x = 8
        draw_fast_mirror_options(layout, context.window_manager)


def _block_shapes_data(length=0.1, half=0.05):
    """Triangles, outline lines and stem of the block gizmo, pointing along +Z."""
    corners = [
        (half if i & 1 else -half, half if i & 2 else -half, length + (half if i & 4 else -half))
        for i in range(8)
    ]
    tris = []
    for axis in range(3):
        for side in (0, 1):
            i0, i1, i2, i3 = [i for i in range(8) if ((i >> axis) & 1) == side]
            tris += [corners[i0], corners[i1], corners[i3], corners[i0], corners[i3], corners[i2]]

    edges = [(a, b) for a in range(8) for b in range(a + 1, 8) if bin(a ^ b).count("1") == 1]
    lines = [corners[i] for edge in edges for i in edge]
    lines += [(0.0, 0.0, 0.0), (0.0, 0.0, length - half)]
    return tris, lines


class FastMirrorBlockGizmo(bpy.types.Gizmo):
    """Block on a stem. The outline is drawn as smooth lines so the edges are anti-aliased."""
    bl_idname = "KEYOPS_GT_fast_mirror_block"

    def setup(self):
        tris, lines = _block_shapes_data()
        self.fill_shape = self.new_custom_shape('TRIS', tris)
        self.line_shape = self.new_custom_shape('LINES', lines)

    def draw(self, context):
        self.draw_custom_shape(self.fill_shape)
        self.draw_custom_shape(self.line_shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.fill_shape, select_id=select_id)


class FastMirrorGizmoGroup(bpy.types.GizmoGroup):
    bl_idname = "KEYOPS_GGT_fast_mirror"
    bl_label = "Fast Mirror Gizmo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            context.window_manager.keyops_fast_mirror_gizmo
            and obj is not None
            and obj.type == 'MESH'
            and context.mode in {'OBJECT', 'EDIT_MESH'}
        )

    @staticmethod
    def _apply_axis_color(gizmo, axis, keep_negative):
        color = AXIS_COLORS[axis]
        factor = 0.55 if keep_negative else 1.0
        gizmo.color = (color[0] * factor, color[1] * factor, color[2] * factor)
        gizmo.alpha = 0.9

    def setup(self, context):
        self.arrows = []
        for axis_index, axis in enumerate(AXES):
            for keep_negative in (False, True):
                gizmo = self.gizmos.new(FastMirrorBlockGizmo.bl_idname)
                gizmo.use_draw_modal = False
                gizmo.use_draw_scale = True
                gizmo.scale_basis = 2.0
                gizmo.line_width = 3.0
                gizmo.color_highlight = (1.0, 1.0, 1.0)
                gizmo.alpha_highlight = 1.0

                self._apply_axis_color(gizmo, axis, keep_negative)

                props = gizmo.target_set_operator("keyops.fast_mirror_apply")
                props.axis = axis
                props.keep_negative = keep_negative

                self.arrows.append((gizmo, axis_index, keep_negative))

    def draw_prepare(self, context):
        obj = context.active_object
        if obj is None:
            return

        corners = [Vector(corner) for corner in obj.bound_box]
        bb_min = Vector((min(c[i] for c in corners) for i in range(3)))
        bb_max = Vector((max(c[i] for c in corners) for i in range(3)))
        center = (bb_min + bb_max) * 0.5
        min_offset = max((bb_max - bb_min).length * 0.1, 0.05)

        matrix_world = obj.matrix_world
        rotation = matrix_world.to_quaternion()
        active_arrows.clear()
        active_arrows.extend(self.arrows)

        for gizmo, axis_index, keep_negative in self.arrows:
            self._apply_axis_color(gizmo, AXES[axis_index], keep_negative)

            local_pos = center.copy()
            if keep_negative:
                local_pos[axis_index] = min(bb_min[axis_index], -min_offset)
            else:
                local_pos[axis_index] = max(bb_max[axis_index], min_offset)

            direction = Vector((0.0, 0.0, 0.0))
            direction[axis_index] = -1.0 if keep_negative else 1.0
            direction = rotation @ direction

            position = matrix_world @ local_pos
            gizmo.matrix_basis = Matrix.Translation(position) @ direction.to_track_quat('Z', 'Y').to_matrix().to_4x4()


def remove_draw_handlers():
    handlers = bpy.app.driver_namespace.pop(HANDLERS_KEY, ())
    for handler in handlers:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(handler, 'WINDOW')
        except ValueError:
            pass


def register_fast_mirror():
    wm_type = bpy.types.WindowManager
    wm_type.keyops_fast_mirror_gizmo = bpy.props.BoolProperty(name="Mirror Gizmo", description="Show the Fast Mirror gizmo", default=False) # type: ignore
    wm_type.keyops_fast_mirror_mode = bpy.props.EnumProperty(name="Mirror Mode", items=MODE_ITEMS, default=DEFAULT_MODE, update=on_fast_mirror_mode_changed) # type: ignore
    wm_type.keyops_fast_mirror_preview_mode = bpy.props.EnumProperty(name="Mirror Preview Mode", items=MODE_ITEMS, default=DEFAULT_MODE) # type: ignore
    wm_type.keyops_fast_mirror_modal_running = bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    wm_type.keyops_fast_mirror_ctrl = bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    wm_type.keyops_fast_mirror_shift = bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    wm_type.keyops_fast_mirror_alt = bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    wm_type.keyops_fast_mirror_mouse_x = bpy.props.IntProperty(default=-1, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    wm_type.keyops_fast_mirror_mouse_y = bpy.props.IntProperty(default=-1, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    wm_type.keyops_fast_mirror_mode_before_override = bpy.props.EnumProperty(name="Mirror Base Mode", items=MODE_ITEMS, default=DEFAULT_MODE, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    wm_type.keyops_fast_mirror_mode_override_active = bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore

    registered_fast_mirror_classes.clear()
    for cls in (FastMirrorApply, FastMirror, FastMirrorPreviewWatcher, FastMirrorCancel, FastMirrorOptionsPanel, FastMirrorOptions, FastMirrorBlockGizmo, FastMirrorGizmoGroup):
        bpy.utils.register_class(cls)
        registered_fast_mirror_classes.append(cls)

    patch_toolbar()

    remove_draw_handlers()
    handler = bpy.types.SpaceView3D.draw_handler_add(draw_fast_mirror_visuals, (), 'WINDOW', 'POST_VIEW')
    bpy.app.driver_namespace[HANDLERS_KEY] = (handler,)


def unregister_fast_mirror():
    global last_hovered_arrow, last_modal_hovered_arrow

    context = bpy.context
    if context is not None and context.workspace is not None:
        context.workspace.status_text_set(None)

    remove_draw_handlers()
    active_arrows.clear()
    last_hovered_arrow = None
    last_modal_hovered_arrow = None

    unpatch_toolbar()

    for cls in reversed(registered_fast_mirror_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    registered_fast_mirror_classes.clear()

    wm_type = bpy.types.WindowManager
    for name in (
        "keyops_fast_mirror_gizmo",
        "keyops_fast_mirror_mode",
        "keyops_fast_mirror_preview_mode",
        "keyops_fast_mirror_modal_running",
        "keyops_fast_mirror_ctrl",
        "keyops_fast_mirror_shift",
        "keyops_fast_mirror_alt",
        "keyops_fast_mirror_mouse_x",
        "keyops_fast_mirror_mouse_y",
        "keyops_fast_mirror_mode_before_override",
        "keyops_fast_mirror_mode_override_active",
    ):
        if hasattr(wm_type, name):
            delattr(wm_type, name)
