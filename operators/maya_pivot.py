import bpy.types, math, ctypes, mathutils, os
from mathutils import Matrix
from ..utils.pref_utils import get_keyops_prefs
from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
from bpy.types import (GizmoGroup)
from bpy_extras.view3d_utils import location_3d_to_region_2d
    
current_active_tool = None
gizmo_location = None
previuse_gizmo_visibility_states = None
previuse_ortiation_and_pivot_point = None
previuse_gizmo_translate_state = None
OS = os.name
        
def toggle_oriantation_and_pivot_point(context, set=False):
    global previuse_ortiation_and_pivot_point
    tool_settings = context.scene.tool_settings

    if set:
        if not context.scene.transform_orientation_slots[0].type == 'CURSOR' and not tool_settings.transform_pivot_point == 'CURSOR':
            previuse_ortiation_and_pivot_point = (context.scene.transform_orientation_slots[0].type, tool_settings.transform_pivot_point)
            context.scene.transform_orientation_slots[0].type == 'CURSOR'
            tool_settings.transform_pivot_point = 'CURSOR'
    else:
        if previuse_ortiation_and_pivot_point:
            context.scene.transform_orientation_slots[0].type, tool_settings.transform_pivot_point = previuse_ortiation_and_pivot_point

def reset_pivot(context):
    global current_active_tool
    
    if current_active_tool:
        bpy.ops.wm.tool_set_by_id(name=current_active_tool)
    context.window_manager.show_3d_gizmo = False

def reset_grease_pencil_keymap(context):
    wm = context.window_manager
    km = wm.keyconfigs.user.keymaps["Grease Pencil"]
    kmi = km.keymap_items.get("gpencil.annotate")
    if kmi:
        kmi.active = True

def toggle_deafult_gizmos(context, hide=False):
    global previuse_gizmo_visibility_states
    
    gizmo_attrs = [
        'show_gizmo_tool',
        'show_gizmo_object_translate',
        'show_gizmo_object_rotate', 
        'show_gizmo_object_scale']

    if hide:  # Hide all gizmos and save current states
        if any(getattr(context.space_data, attr) for attr in gizmo_attrs):
            previuse_gizmo_visibility_states = [getattr(context.space_data, attr) for attr in gizmo_attrs]
        for attr in gizmo_attrs:  # Hide all gizmos
            setattr(context.space_data, attr, False)
    else:  # Restore previous states
        if previuse_gizmo_visibility_states:
            for attr, state in zip(gizmo_attrs, previuse_gizmo_visibility_states):
                setattr(context.space_data, attr, state)

def should_show_pivot_gizmo(context):
    prefs = get_keyops_prefs()
    show_gizmo = prefs.maya_pivot_show_gizmo
    wm = context.window_manager
    if prefs.maya_pivot_experimental:
        return (
            (context.mode in {'OBJECT'} and show_gizmo and context.scene.tool_settings.use_transform_data_origin) or
            (context.mode in {'EDIT_MESH'} and wm.show_3d_gizmo and prefs.maya_pivot_in_edit_mode)
        )
    else:
        return False
    
class ResetButton(GizmoGroup):
    bl_idname = "view3d.reset_pivot_button_gizmo"
    bl_label = "Reset Pivot Button Gizmo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}
    
    @classmethod
    def poll(cls, context):
        return should_show_pivot_gizmo(context)
        
    def draw_prepare(self, context):
        global gizmo_location
        region = context.region
        rv3d = context.space_data.region_3d

        if gizmo_location:
            cursor_location = gizmo_location.translation
            cursor_2d = location_3d_to_region_2d(region, rv3d, cursor_location)
            
            if cursor_2d:
                self.foo_gizmo.matrix_basis[0][3] = cursor_2d.x
                self.foo_gizmo.matrix_basis[1][3] = cursor_2d.y + -70
                self.foo_gizmo.matrix_basis[2][3] = 0.0

    def setup(self, context):
        mpr = self.gizmos.new("GIZMO_GT_button_2d")
        op = mpr.target_set_operator("keyops.pivot_press")
        op.type = "reset_pivot"
        mpr.icon = 'CANCEL'
        mpr.draw_options = {'BACKDROP', 'OUTLINE'}
        mpr.alpha = 0.05
        mpr.color_highlight = 0.8, 0.8, 0.8
        mpr.alpha_highlight = 0.2
        mpr.scale_basis = (80 * 0.35) / 2
        self.foo_gizmo = mpr
        
def edit_mode_pivot_release(context, skip_set_tool=False):
    wm = bpy.context.window_manager
    if current_active_tool and not skip_set_tool:
        bpy.ops.wm.tool_set_by_id(name=current_active_tool)
    wm.show_3d_gizmo = False
    # context.area.tag_redraw()
    toggle_deafult_gizmos(context, hide=False)
    reset_grease_pencil_keymap(context)

class PivotPress(bpy.types.Operator):
    bl_idname = "keyops.pivot_press"
    bl_label = "KeyOps: Pivot Press"
    bl_description = "Move Pivot Key Press"
    bl_options = {'REGISTER'}

    type: bpy.props.StringProperty(default="") # type: ignore

    @classmethod
    def poll(cls, context):
        prefs = get_keyops_prefs()
        return context.active_object is not None and context.object in context.selected_objects and context.active_object.mode == 'OBJECT' or context.mode == 'EDIT_MESH' and prefs.maya_pivot_experimental
    
    def invoke(self, context, event):
        # if context.mode == 'EDIT_MESH':
        prefs = get_keyops_prefs()
        pivot_behavior = prefs.maya_pivot_behavior
        if pivot_behavior != 'TOGGLE':          
            wm = context.window_manager
            km = wm.keyconfigs.user.keymaps.get("Grease Pencil")
            if km:
                kmi = km.keymap_items.get("gpencil.annotate")
                if kmi:
                    kmi.active = False
        return self.execute(context)
             
    def execute(self, context):
        prefs =  get_keyops_prefs()
        pivot_behavior = prefs.maya_pivot_behavior
        show_gizmo = prefs.maya_pivot_show_gizmo

        tool_settings = context.scene.tool_settings
        wm = context.window_manager

        if not prefs.maya_pivot_experimental:
            global previuse_gizmo_translate_state

            if context.mode == 'OBJECT':
                if self.type == 'PivotPress':
                    if not context.scene.tool_settings.use_transform_data_origin:
                        previuse_gizmo_translate_state = bpy.context.space_data.show_gizmo_object_translate

                    if pivot_behavior == 'TOGGLE':
                        if context.scene.tool_settings.use_transform_data_origin:
                            if previuse_gizmo_translate_state != None:
                                bpy.context.space_data.show_gizmo_object_translate = previuse_gizmo_translate_state

                        context.scene.tool_settings.use_transform_data_origin = not context.scene.tool_settings.use_transform_data_origin
                    
                        if show_gizmo and context.scene.tool_settings.use_transform_data_origin:
                            bpy.context.space_data.show_gizmo_context = True
                            bpy.context.space_data.show_gizmo_object_translate = True
                        else:
                            if previuse_gizmo_translate_state  != None:
                                bpy.context.space_data.show_gizmo_object_translate = previuse_gizmo_translate_state
                            reset_grease_pencil_keymap(context)

                    else:
                        context.scene.tool_settings.use_transform_data_origin = True
                        if show_gizmo and bpy.context.space_data.show_gizmo_object_translate == False:
                            bpy.context.space_data.show_gizmo_context = True
                            bpy.context.space_data.show_gizmo_object_translate = True
                        
                elif self.type == 'PivotRelease':
                    if pivot_behavior == 'HOLD':
                        context.scene.tool_settings.use_transform_data_origin = False
                        if show_gizmo:
                            if previuse_gizmo_translate_state != None:
                                bpy.context.space_data.show_gizmo_object_translate = previuse_gizmo_translate_state 
                            reset_grease_pencil_keymap(context)
                            
        else:
            if self.type == "reset_pivot":
                if context.mode == 'EDIT_MESH':
                    tool_settings.transform_pivot_point = 'MEDIAN_POINT'
                    context.scene.transform_orientation_slots[0].type = 'GLOBAL'

                    bpy.ops.view3d.snap_cursor_to_selected()
                    wm.show_3d_gizmo = False
                    # reset 3d cursor rotation, since it hard to reset it with the gizmo
                    context.scene.cursor.rotation_euler = mathutils.Euler((0, 0, 0), 'XYZ')
                    reset_grease_pencil_keymap(context)
                    toggle_oriantation_and_pivot_point(context, set=False)

                else:
                    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
                    tool_settings.use_transform_data_origin = False
                    wm.show_3d_gizmo = False
                    toggle_oriantation_and_pivot_point(context, set=False)

                return {'FINISHED'}
            
            if context.mode == 'OBJECT':
                if self.type == 'PivotPress':
                    toggle_deafult_gizmos(context, hide=True)
                    wm.show_3d_gizmo = True

                    if pivot_behavior == 'TOGGLE':
                        tool_settings.use_transform_data_origin = not tool_settings.use_transform_data_origin
                        tool_settings.use_transform_skip_children = not tool_settings.use_transform_skip_children
                    else:
                        tool_settings.use_transform_data_origin = True
                        tool_settings.use_transform_skip_children = True

                elif self.type == 'PivotRelease':
                    if pivot_behavior == 'HOLD':
                        tool_settings.use_transform_data_origin = False
                        tool_settings.use_transform_skip_children = False
                
                    toggle_deafult_gizmos(context, hide=False)

            elif context.mode == 'EDIT_MESH':
                if prefs.maya_pivot_in_edit_mode:
                    global current_active_tool

                    if self.type == 'PivotPress':
                        toggle_deafult_gizmos(context, hide=True)

                        if not tool_settings.transform_pivot_point == 'CURSOR':
                            if tool_settings.transform_pivot_point == 'ACTIVE_ELEMENT':
                                bpy.ops.view3d.snap_cursor_to_active()
                            else:
                                bpy.ops.view3d.snap_cursor_to_selected()

                        tools = bpy.context.workspace.tools
                        current_tool = tools.from_space_view3d_mode(bpy.context.mode).idname
                        if current_tool != 'builtin.cursor':
                            current_active_tool = current_tool

                        bpy.ops.wm.tool_set_by_id(name='builtin.cursor')
                        tool = ToolSelectPanelHelper.tool_active_from_context(context)
                        # Set the properties
                        props = tool.operator_properties('view3d.cursor3d')
                        props.use_depth = True
                        props.orientation = 'GEOM'

                        context.area.tag_redraw()
                        wm.show_3d_gizmo = True
                        toggle_oriantation_and_pivot_point(context, set=True)

                        context.scene.transform_orientation_slots[0].type = 'CURSOR'

                    elif self.type == 'PivotRelease':
                        edit_mode_pivot_release(context)
                else:
                    return {'PASS_THROUGH'}
        return {'FINISHED'}

    def register():
        bpy.utils.register_class(MayaPivotGizmoGroup)
        bpy.utils.register_class(ResetButton)
        bpy.utils.register_class(GizmoMayaPivotTransform)
        bpy.types.WindowManager.show_3d_gizmo = bpy.props.BoolProperty(
            name="Pivot Gizmo",
            description="Show 3D Cursor Gizmo",
            default=False)

    def unregister():
        bpy.utils.unregister_class(MayaPivotGizmoGroup)
        bpy.utils.unregister_class(ResetButton)
        bpy.utils.unregister_class(GizmoMayaPivotTransform)
        del bpy.types.WindowManager.show_3d_gizmo

class GizmoMayaPivotTransform(bpy.types.Operator):
    bl_description = "Rotate Pivot"
    bl_idname = "keyops.gizmo_maya_pivot_transform"
    bl_label = "KeyOps: Rotate Pivot"
    bl_options = {'REGISTER'}

    constraint_axis: bpy.props.StringProperty(default="", options={'HIDDEN'}
    ) # type: ignore
    def execute(self, context):

        def press_r():
            axis = self.constraint_axis.upper()
            #press R key with ctypes
            ctypes.windll.user32.keybd_event(0x52, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x52, 0, 2, 0)

            # press axis key with ctypes
            if axis == 'X':
                ctypes.windll.user32.keybd_event(0x58, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x58, 0, 2, 0)
            elif axis == 'Y':
                ctypes.windll.user32.keybd_event(0x59, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x59, 0, 2, 0)
            elif axis == 'Z':
                ctypes.windll.user32.keybd_event(0x5A, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x5A, 0, 2, 0)
            else:
                return None
            
            return None  

        bpy.app.timers.register(press_r, first_interval=0.001)

        if context.mode == 'EDIT_MESH':
            bpy.ops.transform.translate('INVOKE_DEFAULT', cursor_transform=True, orient_type='CURSOR', orient_matrix_type='CURSOR', constraint_axis=(False, False, False))
        else:
            bpy.ops.transform.translate('INVOKE_DEFAULT', constraint_axis=(False, False, False), orient_type='LOCAL', orient_matrix_type='LOCAL')
        return {'FINISHED'}

class MayaPivotGizmoGroup(bpy.types.GizmoGroup):
    bl_idname = "VIEW3D_GT_gizmo_3d_cursor_pivot"
    bl_label = "3D Cursor Gizmo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        return should_show_pivot_gizmo(context)

    def setup(self, context):
        gizmo_data = [
            ('x', 'GIZMO_GT_arrow_3d', (True, False, False)),
            ('y', 'GIZMO_GT_arrow_3d', (False, True, False)),
            ('z', 'GIZMO_GT_arrow_3d', (False, False, True)),
            ('dot', 'GIZMO_GT_move_3d', (False, False, False))
        ]

        self.r_gizmo = {}
        self.v_axes = {}

        for axis, gizmo_type, constraint_axis in gizmo_data:
            gizmo1 = self.gizmos.new(gizmo_type)
            gizmo1.use_tooltip = False
            gizmo1.use_draw_modal = False
            gizmo1.use_draw_hover = axis != 'dot'
            gizmo1.line_width = 2
            gizmo1.hide_select = False

            self.r_gizmo[f"{axis}_inv"] = gizmo1

            gizmo2 = self.gizmos.new(gizmo_type)
            gizmo2.use_tooltip = False
            gizmo2.color = (0, 0, 0)
            gizmo2.alpha = 1
            gizmo2.line_width = 2
            gizmo2.hide_select = True
            if axis != 'dot':
                gizmo2.length = 0.35
                gizmo2.use_draw_offset_scale = True
                gizmo2.matrix_offset = Matrix.Translation((0, 0, 0.65))

                gizmo1.length = 0.35
                gizmo1.use_draw_offset_scale = True
                gizmo1.matrix_offset = Matrix.Translation((0, 0, 0.65))

            self.v_axes[axis] = gizmo2

        self.r_gizmo['dot_inv'].draw_options = {'FILL_SELECT', 'ALIGN_VIEW'}
        self.v_axes['dot'].draw_options = {'FILL_SELECT', 'ALIGN_VIEW'}

        # Rotation Gizmos 
        if OS == 'nt':
            self.rot_gizmos = {}
            rotation_colors = {'x': (1.0, 0.0, 0.0), 'y': (0.0, 1.0, 0.0), 'z': (0.0, 0.0, 1.0)}

            for axis in ['x', 'y', 'z']:
                gizmo = self.gizmos.new('GIZMO_GT_dial_3d')
                gizmo.use_tooltip = False
                gizmo.line_width = 1.0  
                gizmo.scale_basis = 0.4
                gizmo.color = rotation_colors[axis]
                gizmo.alpha = 0.75
                gizmo.draw_options = {'CLIP'}  
                self.rot_gizmos[axis] = gizmo
                op = gizmo.target_set_operator('keyops.gizmo_maya_pivot_transform')
                op.constraint_axis = axis.upper()

    def refresh(self, context):
        global gizmo_location

        cursor = context.scene.cursor

        colors = {
            'x': (1.0, 0.211766, 0.325486),
            'y': (0.541176, 0.85883, 0.0),
            'z': (0.172551, 0.560786, 1.0),
            'dot': (1.0, 1.0, 1.0),
        }

        dot_scale = 0.2
        arrow_size = {'scale': 1.0, 'length': 0.8, 'line_width': 2.0}
        dot_size = {'line_width': 1.65}
        rot_size = {'scale': 0.65, 'line_width': 1.2}  # Rotation gizmo size
        
        for axis in ['x', 'y', 'z', 'dot']:
            if context.mode == 'EDIT_MESH':
                location = cursor.location.copy()
                rotation = cursor.rotation_euler.to_matrix().to_4x4()
            else:
                location = context.active_object.location.copy()
                rotation = context.active_object.rotation_euler.to_matrix().to_4x4()

            gizmo_location = Matrix.Translation(location) @ rotation
            if axis == 'x':
                rotation @= Matrix.Rotation(math.radians(90), 4, 'Y')
            elif axis == 'y':
                rotation @= Matrix.Rotation(math.radians(-90), 4, 'X')

            gizmo1 = self.r_gizmo[f"{axis}_inv"]
            gizmo2 = self.v_axes[axis]

            gizmo1.matrix_basis = Matrix.Translation(location) @ rotation
            gizmo1.color = (1.0, 1.0, 1.0) if axis == 'dot' and gizmo1.is_highlight else (0.7, 0.7, 0.7)
            gizmo1.alpha = 0.75
            gizmo1.scale_basis = dot_scale if axis == 'dot' else arrow_size['scale']
            gizmo1.line_width = dot_size['line_width'] if axis == 'dot' else arrow_size['line_width']

            gizmo2.matrix_basis = Matrix.Translation(location) @ rotation
            gizmo2.color = colors[axis]
            gizmo2.alpha = 1.0
            gizmo2.scale_basis = dot_scale if axis == 'dot' else arrow_size['scale']
            gizmo2.line_width = dot_size['line_width'] if axis == 'dot' else arrow_size['line_width']
        
        if OS == 'nt':
            # rotation gizmos
            for axis, gizmo in self.rot_gizmos.items():
                if context.mode == 'EDIT_MESH':
                    location = cursor.location.copy()
                    rotation = cursor.rotation_euler.to_matrix().to_4x4()
                else:
                    location = context.active_object.location.copy()
                    rotation = context.active_object.rotation_euler.to_matrix().to_4x4()

                if axis == 'x':
                    rotation @= Matrix.Rotation(math.radians(90), 4, 'Y')
                elif axis == 'y':
                    rotation @= Matrix.Rotation(math.radians(-90), 4, 'X')

                gizmo.matrix_basis = Matrix.Translation(location) @ rotation
                gizmo.scale_basis = rot_size['scale']
                gizmo.line_width = rot_size['line_width']

    def draw_prepare(self, context):
        for axis in ['x', 'y', 'z', 'dot']:
            gizmo1 = self.r_gizmo[f"{axis}_inv"]
            op = gizmo1.target_set_operator('transform.translate')
            op.constraint_axis = (axis == 'x', axis == 'y', axis == 'z')
            op.release_confirm = True

            if context.mode == 'EDIT_MESH':
                op.cursor_transform = True
                op.orient_type = 'CURSOR'
                # if active tool not view3d.cursor3d, reset it
                tool = ToolSelectPanelHelper.tool_active_from_context(context)
                if tool and tool.idname != 'builtin.cursor':
                    edit_mode_pivot_release(context, skip_set_tool=True)
            else:
                op.cursor_transform = False
                op.orient_type = 'LOCAL'

        self.refresh(context)