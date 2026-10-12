import bpy
import gpu
import math
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_location_3d
from gpu_extras.batch import batch_for_shader


def draw_points(coords, color, point_size=6.0, shader=None):
    """Draw points using GPU with custom size."""
    if not coords:
        return
    coords = coords if isinstance(coords, list) else [coords]

    if shader is None:
        try:
            shader = gpu.shader.from_builtin('POINT_UNIFORM_COLOR')
        except (ValueError, TypeError):
            try:
                shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            except (ValueError, TypeError):
                return
    batch = batch_for_shader(shader, 'POINTS', {"pos": coords})
    shader.uniform_float("color", color)
    gpu.state.point_size_set(point_size)
    batch.draw(shader)


def draw_lines(coords, color, line_width=2.0):
    """Draw lines using GPU."""
    if not coords or len(coords) < 2:
        return

    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    shader.bind()

    region = bpy.context.region
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("color", color)
    shader.uniform_float("lineWidth", line_width)

    batch = batch_for_shader(shader, 'LINES', {"pos": coords})
    gpu.state.blend_set("ALPHA")
    batch.draw(shader)


def _project_point(region, region_data, point):
    """Project a world-space point to region space."""
    return location_3d_to_region_2d(region, region_data, point)


def _point_at_screen_distance(start, end, region, region_data, target_distance, start_2d, end_2d):
    """Find a world-space point whose projected distance matches a screen-space offset."""
    if target_distance <= 0:
        return start

    total_distance = (end_2d - start_2d).length
    if total_distance <= 0:
        return start

    target_distance = min(target_distance, total_distance)
    direction = end - start
    low = 0.0
    high = 1.0

    for _ in range(16):
        mid = (low + high) * 0.5
        world_point = start + direction * mid
        projected_point = _project_point(region, region_data, world_point)
        if projected_point is None:
            return start + direction * (target_distance / total_distance)

        screen_distance = (projected_point - start_2d).length
        if screen_distance < target_distance:
            low = mid
        else:
            high = mid

    return start + direction * ((low + high) * 0.5)


def draw_dashed_lines(start, end, context, color, dash_size=8.0, gap_size=8.0, line_width=1.0, alpha=1.0):
    """Draw dashed line from start to end point with screen-space dash/gap size."""
    if start is None or end is None:
        return

    region = context.region
    region_data = context.space_data.region_3d
    start_2d = _project_point(region, region_data, start)
    end_2d = _project_point(region, region_data, end)

    if start_2d is None or end_2d is None:
        return

    dashed_color = (color[0], color[1], color[2], color[3] * alpha)
    distance = (end_2d - start_2d).length

    if distance == 0:
        return

    coords = []
    current_distance = 0.0
    is_dash = True

    while current_distance < distance:
        segment_size = dash_size if is_dash else gap_size
        next_distance = min(current_distance + segment_size, distance)

        if is_dash:
            current_pos = _point_at_screen_distance(start, end, region, region_data, current_distance, start_2d, end_2d)
            next_pos = _point_at_screen_distance(start, end, region, region_data, next_distance, start_2d, end_2d)
            coords.extend([current_pos, next_pos])

        current_distance = next_distance
        is_dash = not is_dash

    if coords:
        draw_lines(coords, dashed_color, line_width)


def draw_circle(point, context, color, radius_px=7.0, line_width=2.0, segments=96):
    """Draw an anti-aliased round screen-space ring around a world-space point."""
    region = context.region
    region_data = context.space_data.region_3d

    center_2d = _project_point(region, region_data, point)
    if center_2d is None:
        return

    right_2d = center_2d + Vector((radius_px, 0.0))
    world_offset = region_2d_to_location_3d(region, region_data, right_2d, point)
    world_radius = (world_offset - point).length
    if world_radius <= 0:
        return

    view_rot = region_data.view_rotation
    right = view_rot @ Vector((1.0, 0.0, 0.0))
    up = view_rot @ Vector((0.0, 1.0, 0.0))

    tau = 6.283185307179586
    alpha = color[3] if len(color) > 3 else 1.0
    px_to_world = world_radius / max(radius_px, 1e-6)
    core_outer = world_radius
    core_inner = max(core_outer - (line_width * px_to_world), core_outer * 0.45)
    feather = 1.25 * px_to_world
    aa_outer = core_outer + feather
    aa_inner = max(core_inner - feather, core_inner * 0.25)

    positions = []
    colors = []

    def append_band(radius_outer, radius_inner, alpha_outer, alpha_inner):
        co_outer = (color[0], color[1], color[2], alpha_outer)
        co_inner = (color[0], color[1], color[2], alpha_inner)
        for i in range(segments):
            j = (i + 1) % segments
            a0 = tau * (i / segments)
            a1 = tau * (j / segments)

            c0, s0 = math.cos(a0), math.sin(a0)
            c1, s1 = math.cos(a1), math.sin(a1)

            o0 = point + (right * (radius_outer * c0)) + (up * (radius_outer * s0))
            o1 = point + (right * (radius_outer * c1)) + (up * (radius_outer * s1))
            i0 = point + (right * (radius_inner * c0)) + (up * (radius_inner * s0))
            i1 = point + (right * (radius_inner * c1)) + (up * (radius_inner * s1))

            positions.extend([o0, o1, i0, o1, i1, i0])
            colors.extend([co_outer, co_outer, co_inner, co_outer, co_inner, co_inner])

    append_band(aa_outer, core_outer, 0.0, alpha)
    append_band(core_outer, core_inner, alpha, alpha)
    append_band(core_inner, aa_inner, alpha, 0.0)

    shader = gpu.shader.from_builtin('SMOOTH_COLOR')
    shader.bind()

    gpu.state.blend_set("ALPHA")
    batch = batch_for_shader(shader, 'TRIS', {"pos": positions, "color": colors})
    batch.draw(shader)
