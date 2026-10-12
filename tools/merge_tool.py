import bpy
import bmesh
import os
from bpy.props import BoolProperty

from ..utils import draw_utils as DrawUtils
from ..utils import mesh_utils as MeshUtils

# Based on the really handy https://github.com/Stromberg90/Scripts
# Tried to make it a bit more minimalist and more maya like for my usecases 

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


def get_preview_selection(selection, max_count=MAX_PREVIEW_COMPONENTS):
    """Limit preview-only draws to avoid freezing on very large selections."""
    if selection is None:
        return []
    if len(selection) <= max_count:
        return list(selection)
    return list(selection[:max_count])


def draw_callback_3d(self, context):
    """Main drawing callback for visualization."""
    try:
        if not self.started or self.start_comp is None:
            return
    except ReferenceError:
        # Operator RNA can be destroyed before delayed draw callbacks stop firing.
        return
    
    if self.sel_mode == EDGE_MODE:
        edge_verts = [self.world_matrix @ v.co for v in self.start_comp.verts]
        DrawUtils.draw_lines(edge_verts, COLOR_START)

    DrawUtils.draw_points(self.start_comp_transformed, COLOR_START, POINT_SMALL)
    
    if self.end_comp and self.end_comp != self.start_comp:
        vert_coords = []
        line_coords = []
        
        if self.multi_merge:
            preview_sel = get_preview_selection(self.start_sel)
            vert_list = [v.co for v in preview_sel]
            if self.end_comp not in preview_sel:
                vert_list.append(self.end_comp.co)
            
            if self.merge_center:
                center = self.world_matrix @ MeshUtils.get_center(vert_list)
                
                if len(preview_sel) > 1:
                    for v in preview_sel:
                        if v != self.start_comp:
                            v_world = self.world_matrix @ v.co
                            DrawUtils.draw_dashed_lines(v_world, center, context, COLOR_LINE, line_width=1.0)
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
                            DrawUtils.draw_dashed_lines(v_world, self.end_comp_transformed, context, COLOR_LINE, line_width=1.0)
                            vert_coords.append(v_world)
                    line_coords = [self.start_comp_transformed, self.end_comp_transformed]
                else:
                    line_coords = [self.start_comp_transformed, self.end_comp_transformed]
        else:
            line_coords = [self.start_comp_transformed, self.end_comp_transformed]
        
        DrawUtils.draw_lines(line_coords, COLOR_LINE)

        if self.sel_mode == EDGE_MODE:
            edge_verts = [self.world_matrix @ v.co for v in self.end_comp.verts]
            DrawUtils.draw_lines(edge_verts, COLOR_END)

        DrawUtils.draw_circle(self.end_comp_transformed, context, COLOR_LINE, radius_px=7.5, line_width=1)

        if self.multi_merge and vert_coords:
            DrawUtils.draw_points(vert_coords, COLOR_START, POINT_SMALL)

        if self.merge_center and self.multi_merge:
            preview_sel = get_preview_selection(self.start_sel)
            vert_list = [v.co for v in preview_sel]
            if self.end_comp not in preview_sel:
                vert_list.append(self.end_comp.co)
            center_point = self.world_matrix @ MeshUtils.get_center(vert_list)
            DrawUtils.draw_points(center_point, COLOR_END)
        elif self.merge_center and self.sel_mode == VERT_MODE:
            center_point = self.world_matrix @ MeshUtils.get_center([self.start_comp, self.end_comp])
            DrawUtils.draw_points(center_point, COLOR_END)
        elif self.merge_center and self.sel_mode == EDGE_MODE:
            center_point = self.world_matrix @ MeshUtils.get_center([
                MeshUtils.get_center(self.start_comp),
                MeshUtils.get_center(self.end_comp),
            ])
            DrawUtils.draw_points(center_point, COLOR_END)


def set_component(operator, mode):
    """Set start or end component from selection."""
    selected = operator.bm.select_history.active
    if not selected:
        return False
    
    transform_func = (lambda x: operator.world_matrix @ x.co if operator.sel_mode == VERT_MODE 
                     else operator.world_matrix @ MeshUtils.get_center(x))
    
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


def edge_merge(operator):
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
            MeshUtils.merge_vertex_pair(
                operator,
                sv0,
                ev0,
                merge_center=operator.merge_center,
                center=MeshUtils.get_center(new_e0),
                preserve_uvs=operator.preserve_uvs,
            )
            MeshUtils.merge_vertex_pair(
                operator,
                sv1,
                ev1,
                merge_center=operator.merge_center,
                center=MeshUtils.get_center(new_e1),
                preserve_uvs=operator.preserve_uvs,
            )
        else:
            shared = shared_verts[0]
            sv = [v for v in edge1.verts if v != shared][0]
            ev = [v for v in edge2.verts if v != shared][0]
            
            merge_map = {sv: ev}
            MeshUtils.merge_vertex_pair(operator, sv, ev, merge_center=operator.merge_center, preserve_uvs=operator.preserve_uvs)
        
        merge_indices = {source.index: target.index for source, target in merge_map.items()}
        operator.bm = bmesh.from_edit_mesh(operator.me)
        operator.bm.verts.ensure_lookup_table()
        merge_map = {
            operator.bm.verts[source_index]: operator.bm.verts[target_index]
            for source_index, target_index in merge_indices.items()
        }
        bmesh.ops.weld_verts(operator.bm, targetmap=merge_map)
        bmesh.update_edit_mesh(operator.me, destructive=True)
        return True
    except Exception as e:
        print(f"Edge merge failed: {e}")
        return False


class MergeTool(bpy.types.Operator):
    """Interactive merge tool for vertices and edges."""
    bl_idname = "keyops.merge_tool"
    bl_label = "Merge Tool"
    bl_options = {'REGISTER', 'UNDO'}

    merge_center: BoolProperty(  # type: ignore
        name="Merge Center",
        description="Merge to center or last selected",
        default=False
    )

    preserve_uvs: BoolProperty(  # type: ignore
        name="Preserve UVs",
        description="Preserve UVs while merging. This can be performance heavy on high-poly meshes",
        default=True
    )

    wait_for_input: BoolProperty(  # type: ignore
        name="Wait for Input",
        description="Wait for input or start immediately",
        default=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.window = None
        self.area = None
        self.region = None
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
        self.area = context.area
        self.region = context.region

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
            self.report({'WARNING'}, "Merge Tool: Does not support Face Selection Mode")
            return False
        
        if modes[0] and modes[1]:
            self.report({'WARNING'}, "Merge Tool: Selection Mode cannot be both Edge & Vertex")
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
            success = MeshUtils.vertex_merge(self)
        elif self.sel_mode == EDGE_MODE:
            success = edge_merge(self)
        
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
        row = layout.row()
        row.prop(tool_props, "preserve_uvs")

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
