import bpy
import gpu
import bmesh
import os
import math
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_location_3d
from gpu_extras.batch import batch_for_shader
from bpy.props import BoolProperty

ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")
CURSOR_ICON = 'PAINT_CROSS'

COLOR_START = (1.0, 1.0, 1.0, 1.0)
COLOR_END = (0.6392,0.2078, 0.2078,1 )
COLOR_LINE = (0.9608, 0.9451, 0.3020, 1)

# COLOR_END = bpy.context.preferences.themes[0].user_interface.gizmo_b
# COLOR_LINE = bpy.context.preferences.themes[0].user_interface.gizmo_primary
# print(COLOR_END)
POINT_SMALL = 4
MAX_PREVIEW_COMPONENTS = 24

VERT_MODE = 'VERT'
EDGE_MODE = 'EDGE'
FACE_MODE = 'FACE'


def get_builtin_shader(shader_name, fallbacks=()):
    """Return a supported built-in shader, trying fallbacks for older Blender versions."""
    try:
        return gpu.shader.from_builtin(shader_name)
    except (ValueError, TypeError):
        for fallback in fallbacks:
            try:
                return gpu.shader.from_builtin(fallback)
            except (ValueError, TypeError):
                continue
    return None


def get_preview_selection(selection, max_count=MAX_PREVIEW_COMPONENTS):
    """Limit preview-only draws to avoid freezing on very large selections."""
    if selection is None:
        return []
    if len(selection) <= max_count:
        return list(selection)
    return list(selection[:max_count])


def get_center(elements):
    """Calculate center point of vertices, edges, or vectors."""
    coords = []
    
    if isinstance(elements, bmesh.types.BMEdge):
        coords = [v.co for v in elements.verts]
    elif isinstance(elements, (list, tuple)):
        if not elements:
            return Vector()
        first = elements[0]
        if isinstance(first, bmesh.types.BMVert):
            coords = [v.co for v in elements]
        elif isinstance(first, Vector):
            coords = list(elements)
    
    if not coords:
        return Vector()
    
    center = sum(coords, Vector()) / len(coords)
    return center


def draw_points(shader, coords, color, point_size=6.0):
    """Draw points using GPU with custom size."""
    if not coords:
        return
    coords = coords if isinstance(coords, list) else [coords]

    shader = get_builtin_shader('POINT_UNIFORM_COLOR', ('UNIFORM_COLOR',))
    if shader is None:
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


def draw_line_strip(coords, color, line_width=2.0):
    """Draw a continuous polyline using GPU."""
    if not coords or len(coords) < 2:
        return

    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    shader.bind()

    region = bpy.context.region
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("color", color)
    shader.uniform_float("lineWidth", line_width)

    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": coords})
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


def draw_circle_marker(point, context, color, radius_px=7.0, line_width=2.0, segments=96):
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
    # Convert pixel widths into world-space radii so ring thickness remains screen-consistent.
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

    # Outer feather, solid core, inner feather.
    append_band(aa_outer, core_outer, 0.0, alpha)
    append_band(core_outer, core_inner, alpha, alpha)
    append_band(core_inner, aa_inner, alpha, 0.0)

    shader = gpu.shader.from_builtin('SMOOTH_COLOR')
    shader.bind()

    gpu.state.blend_set("ALPHA")
    batch = batch_for_shader(shader, 'TRIS', {"pos": positions, "color": colors})
    batch.draw(shader)

def draw_callback_3d(self, context):
    """Main drawing callback for visualization."""
    try:
        if not self.started or self.start_comp is None:
            return
    except ReferenceError:
        # Operator RNA can be destroyed before delayed draw callbacks stop firing.
        return
    
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    
    if self.sel_mode == EDGE_MODE:
        edge_verts = [self.world_matrix @ v.co for v in self.start_comp.verts]
        draw_lines(edge_verts, COLOR_START)
    
    draw_points(shader, self.start_comp_transformed, COLOR_START, POINT_SMALL)
    
    if self.end_comp and self.end_comp != self.start_comp:
        vert_coords = []
        line_coords = []
        
        if self.multi_merge:
            preview_sel = get_preview_selection(self.start_sel)
            vert_list = [v.co for v in preview_sel]
            if self.end_comp not in preview_sel:
                vert_list.append(self.end_comp.co)
            
            if self.merge_center:
                center = self.world_matrix @ get_center(vert_list)
                
                if len(preview_sel) > 1:
                    for v in preview_sel:
                        if v != self.start_comp:
                            v_world = self.world_matrix @ v.co
                            draw_dashed_lines(v_world, center, context, COLOR_LINE, line_width=1.0)
                            vert_coords.append(v_world)
                    line_coords = [self.start_comp_transformed, center]
                else:
                    line_coords = [self.start_comp_transformed, center]
                
                line_coords.extend([center, self.end_comp_transformed])
            else:
                if len(preview_sel) > 1:
                    for v in preview_sel:
                        if v != self.start_comp:
                            v_world = self.world_matrix @ v.co
                            draw_dashed_lines(v_world, self.end_comp_transformed, context, COLOR_LINE, line_width=1.0)
                            vert_coords.append(v_world)
                    line_coords = [self.start_comp_transformed, self.end_comp_transformed]
                else:
                    line_coords = [self.start_comp_transformed, self.end_comp_transformed]
        else:
            line_coords = [self.start_comp_transformed, self.end_comp_transformed]
        
        draw_lines(line_coords, COLOR_LINE)
        
        if self.sel_mode == EDGE_MODE:
            edge_verts = [self.world_matrix @ v.co for v in self.end_comp.verts]
            draw_lines(edge_verts, COLOR_END)

        draw_circle_marker(self.end_comp_transformed, context, COLOR_LINE, radius_px=7.5, line_width=1)
        
        if self.multi_merge and vert_coords:
            draw_points(shader, vert_coords, COLOR_START, point_size=POINT_SMALL)
        
        if self.merge_center and self.multi_merge:
            preview_sel = get_preview_selection(self.start_sel)
            vert_list = [v.co for v in preview_sel]
            if self.end_comp not in preview_sel:
                vert_list.append(self.end_comp.co)
            center_point = self.world_matrix @ get_center(vert_list)
            draw_points(shader, center_point, COLOR_END)
        elif self.merge_center and self.sel_mode == VERT_MODE:
            center_point = self.world_matrix @ get_center([self.start_comp, self.end_comp])
            draw_points(shader, center_point, COLOR_END)
        elif self.merge_center and self.sel_mode == EDGE_MODE:
            center_point = self.world_matrix @ get_center([get_center(self.start_comp), get_center(self.end_comp)])
            draw_points(shader, center_point, COLOR_END)


def set_component(operator, mode):
    """Set start or end component from selection."""
    selected = operator.bm.select_history.active
    if not selected:
        return False
    
    transform_func = (lambda x: operator.world_matrix @ x.co if operator.sel_mode == VERT_MODE 
                     else operator.world_matrix @ get_center(x))
    
    if mode == 'START':
        operator.start_comp = selected
        operator.start_comp_transformed = transform_func(selected)
    elif mode == 'END':
        operator.end_comp = selected
        operator.end_comp_transformed = transform_func(selected)
    
    return True


def get_mesh_selection(operator):
    """Get currently selected components."""
    if operator.sel_mode == VERT_MODE:
        return [v for v in operator.bm.verts if v.select]
    elif operator.sel_mode == EDGE_MODE:
        return [e for e in operator.bm.edges if e.select]
    return []


def select_at_location(operator, context, event, extend=False):
    """Perform selection at mouse location."""
    location = (event.mouse_region_x, event.mouse_region_y)
    result = bpy.ops.view3d.select(extend=extend, location=location)
    
    if result == {'PASS_THROUGH'}:
        bpy.ops.mesh.select_all(action='DESELECT')
    
    return result


def execute_vertex_merge(operator):
    """Merge selected vertices."""
    try:
        bpy.ops.mesh.select_all(action='DESELECT')
        operator.bm.select_history.clear()
        
        # Only carry the original multi-selection when merge was started from it.
        if operator.multi_merge and operator.start_sel:
            for v in operator.start_sel:
                v.select = True
        
        operator.start_comp.select = True
        operator.end_comp.select = True
        operator.bm.select_history.add(operator.start_comp)
        operator.bm.select_history.add(operator.end_comp)
        
        merge_type = "CENTER" if operator.merge_center else "LAST"
        bpy.ops.mesh.merge(type=merge_type, uvs=True)
        bpy.ops.mesh.select_all(action='DESELECT')
        return True
    except Exception as e:
        print(f"Vertex merge failed: {e}")
        return False


def execute_edge_merge(operator):
    """Merge selected edges."""
    try:
        bpy.ops.mesh.select_all(action='DESELECT')
        operator.bm.select_history.clear()
        
        edge1, edge2 = operator.start_comp, operator.end_comp
        shared_verts = [v for v in edge1.verts if v in edge2.verts]
        
        if not shared_verts:
            bridge_result = bmesh.ops.bridge_loops(operator.bm, edges=(edge1, edge2))
            new_e0, new_e1 = bridge_result['edges'][0], bridge_result['edges'][1]
            
            sv0 = [v for v in new_e0.verts if v in edge1.verts][0]
            sv1 = [v for v in new_e1.verts if v in edge1.verts][0]
            ev0 = new_e0.other_vert(sv0)
            ev1 = new_e1.other_vert(sv1)
            
            merge_map = {sv0: ev0, sv1: ev1}
            
            if operator.merge_center:
                ev0.co = get_center(new_e0)
                ev1.co = get_center(new_e1)
            else:
                sv0.co = ev0.co
                sv1.co = ev1.co
        else:
            shared = shared_verts[0]
            sv = [v for v in edge1.verts if v != shared][0]
            ev = [v for v in edge2.verts if v != shared][0]
            
            merge_map = {sv: ev}
            
            if operator.merge_center:
                ev.co = get_center([sv, ev])
            else:
                sv.co = ev.co
        
        bmesh.ops.weld_verts(operator.bm, targetmap=merge_map)
        bmesh.update_edit_mesh(operator.me)
        return True
    except Exception as e:
        print(f"Edge merge failed: {e}")
        return False


class MergeTool(bpy.types.Operator):
    """Interactive merge tool for vertices and edges."""
    bl_idname = "keyops.merge_tool"
    bl_label = "Merge Tool"
    bl_options = {'REGISTER', 'UNDO'}

    merge_center: BoolProperty(
        name="Merge Center",
        description="Merge to center or last selected",
        default=False
    )

    wait_for_input: BoolProperty(
        name="Wait for Input",
        description="Wait for input or start immediately",
        default=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.window = None
        self.sel_mode = None
        self.start_sel = None
        self.start_comp = None
        self.start_comp_transformed = None
        self.end_comp = None
        self.end_comp_transformed = None
        self.started = False
        self.multi_merge = False
        self.me = None
        self.bm = None
        self.world_matrix = None
        self._draw_handle = None

    def _reset_state(self):
        """Reset operator state to defaults."""
        self.start_sel = None
        self.start_comp = None
        self.start_comp_transformed = None
        self.end_comp = None
        self.end_comp_transformed = None
        self.started = False
        self.multi_merge = False

    def _restore_selection(self):
        """Restore previously selected components."""
        if not self.start_sel:
            return
        
        bpy.ops.mesh.select_all(action='DESELECT')
        for component in self.start_sel:
            component.select = True
        self.bm.select_flush_mode()
        bmesh.update_edit_mesh(self.me)

    def _add_draw_handler(self, context):
        """Add 3D viewport draw handler."""
        if not self._draw_handle:
            self._draw_handle = bpy.types.SpaceView3D.draw_handler_add(
                draw_callback_3d, (self, context), 'WINDOW', 'POST_VIEW'
            )

    def _remove_draw_handler(self, context):
        """Remove 3D viewport draw handler."""
        if self._draw_handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle, 'WINDOW')
            self._draw_handle = None

    def _cleanup(self, context):
        """Clean up operator resources."""
        self._remove_draw_handler(context)
        context.workspace.status_text_set(None)
        if self.window:
            self.window.cursor_modal_restore()
        self._reset_state()

    def _init_mesh_data(self, context):
        """Initialize mesh data from context."""
        self.me = context.object.data
        self.world_matrix = context.object.matrix_world
        self.bm = bmesh.from_edit_mesh(self.me)
        self.window = context.window_manager.windows[0]

    def _check_selection_mode(self, context):
        """Determine and validate selection mode."""
        modes = context.tool_settings.mesh_select_mode
        
        if modes[0] and not modes[1]:
            self.sel_mode = VERT_MODE
        elif modes[1] and not modes[0]:
            self.sel_mode = EDGE_MODE
        elif modes[2]:
            self.sel_mode = FACE_MODE
        
        if self.sel_mode == FACE_MODE:
            self.report({'WARNING'}, "Merge Tool does not work with Face selection mode")
            return False
        
        if modes[0] and modes[1]:
            self.report({'WARNING'}, "Selection Mode must be Vertex OR Edge, not both")
            return False
        
        return True

    def _get_selected_count(self, context):
        """Get count of selected elements."""
        if self.sel_mode == VERT_MODE:
            return context.object.data.total_vert_sel
        elif self.sel_mode == EDGE_MODE:
            return context.object.data.total_edge_sel
        return 0

    def _attempt_merge(self, context):
        """Attempt to merge selected components."""
        if self.start_comp is None or self.end_comp is None:
            return False
        
        if self.start_comp is self.end_comp:
            return False
        
        success = False
        if self.sel_mode == VERT_MODE:
            success = execute_vertex_merge(self)
        elif self.sel_mode == EDGE_MODE:
            success = execute_edge_merge(self)
        
        bpy.ops.mesh.select_all(action='DESELECT')
        return success

    def modal(self, context, event):
        """Handle modal input."""
        context.area.tag_redraw()
        
        if event.alt or event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
        
        if event.type == 'C' and event.value == 'PRESS':
            self.merge_center = not self.merge_center
        
        elif event.type == 'MOUSEMOVE':
            if self.started:
                select_at_location(self, context, event, extend=False)
                set_component(self, 'END')
        
        elif event.type == 'LEFTMOUSE':
            select_at_location(self, context, event, extend=self.started)
            
            if not self.started:
                if self._get_selected_count(context) == 1:
                    if set_component(self, 'START'):
                        self.started = True
                        if self.sel_mode == VERT_MODE and self.start_sel:
                            self.multi_merge = self.start_comp in self.start_sel
                        self._add_draw_handler(context)
                else:
                    self._cleanup(context)
                    return {'CANCELLED'}
            else:
                if self._attempt_merge(context):
                    self._cleanup(context)
                    return {'FINISHED'}
                else:
                    self._cleanup(context)
                    return {'CANCELLED'}
        
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self._restore_selection()
            self._cleanup(context)
            return {'CANCELLED'}
        
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        """Start the merge tool operator."""
        if context.space_data.type != 'VIEW_3D':
            self.report({'WARNING'}, "Active space must be a View3D")
            return {'CANCELLED'}
        
        self._init_mesh_data(context)
        
        if not self._check_selection_mode(context):
            return {'CANCELLED'}
        
        if self._get_selected_count(context) > 1:
            self.start_sel = get_mesh_selection(self)
        
        context.workspace.status_text_set(
            "LMB: Select start/end | Move: Reselect end | C: Toggle Center | ESC/RMB: Cancel"
        )
        
        if self.wait_for_input:
            context.window_manager.modal_handler_add(self)
            self.window.cursor_modal_set(CURSOR_ICON)
            return {'RUNNING_MODAL'}
        
        select_at_location(self, context, event, extend=False)
        
        if self._get_selected_count(context) == 0:
            self._cleanup(context)
            return {'CANCELLED'}
        
        if self._get_selected_count(context) == 1:
            if set_component(self, 'START'):
                self.started = True
                if self.sel_mode == VERT_MODE and self.start_sel:
                    self.multi_merge = self.start_comp in self.start_sel
                self._add_draw_handler(context)
        else:
            self._cleanup(context)
            return {'CANCELLED'}
        
        context.window_manager.modal_handler_add(self)
        self.window.cursor_modal_set(CURSOR_ICON)
        return {'RUNNING_MODAL'}

class WorkSpaceMergeTool(bpy.types.WorkSpaceTool):
    """Workspace tool definition for the Merge Tool."""
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'EDIT_MESH'
    bl_idname = "edit_mesh.merge_tool_workspace_tool"
    bl_label = "Merge Tool"
    bl_description = "Interactively merge vertices and edges"
    bl_icon = os.path.join(ICON_DIR, "ops.mesh.merge_tool")
    bl_cursor = CURSOR_ICON
    bl_widget = None
    bl_keymap = (
        ("keyops.merge_tool", {"type": 'LEFTMOUSE', "value": 'PRESS'},
         {"properties": [("wait_for_input", False)]}),
    )

    def draw_settings(context, layout, tool):
        """Draw tool settings in properties panel."""
        tool_props = tool.operator_properties("keyops.merge_tool")
        row = layout.row()
        row.prop(tool_props, "merge_center")

def register_merge_tool():
    try:
        bpy.utils.register_class(MergeTool)
    except (RuntimeError, ValueError):
        pass

    try:
        if not hasattr(WorkSpaceMergeTool, "_bl_tool"):
            bpy.utils.register_tool(WorkSpaceMergeTool, after={"builtin.spin"}, separator=False, group=False)
    except Exception as e:
        print(f"Failed to register WorkSpaceMergeTool: {e}")


def unregister_merge_tool():
    try:
        bpy.utils.unregister_class(MergeTool)
    except (RuntimeError, ValueError):
        pass

    try:
        if hasattr(WorkSpaceMergeTool, "_bl_tool"):
            bpy.utils.unregister_tool(WorkSpaceMergeTool)
    except Exception as e:
        print(f"Failed to unregister WorkSpaceMergeTool: {e}")
