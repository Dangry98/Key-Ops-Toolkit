import bpy.types
from bpy.types import Context, Menu
from ..utils.pref_utils import get_is_addon_enabled
from ..utils.pref_utils import get_keyops_prefs
import bmesh
import mathutils

hardops = None
uvpackmaster = None
uvtoolkit = None
zenuv = None
polyquilt = None

class AddObjectsPie(Menu):
    bl_idname = "KEYOPS_MT_add_objects_pie"
    bl_label = "Add Mesh Pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        prefs = get_keyops_prefs()


        pie.operator("keyops.add_mesh", text="UV Sphere", icon="SHADING_WIRE").mesh_type = "UVSPHERE" #LEFT

        pie.operator("keyops.add_mesh", text="Cube", icon="MESH_CUBE").mesh_type = "CUBE" #RIGHT

        pie.operator("keyops.add_mesh", text="Cylinder", icon="MESH_CYLINDER").mesh_type = "CYLINDER" #BOTTOM

        pie.operator("keyops.add_mesh", text="Plane", icon="MESH_PLANE").mesh_type = "PLANE" #TOP

        pie.operator("keyops.add_mesh", text="Mod Cylinder", icon="MOD_SCREW").mesh_type = "MODCYLINDER" #LEFT TOP
        if prefs.add_object_pie_empty:
            pie.operator("keyops.add_mesh", text="Empty", icon="EMPTY_ARROWS").mesh_type = "EMPTY" #RIGHT TOP
        else:
            pie.operator("keyops.add_mesh", text="Monkey", icon="MESH_MONKEY").mesh_type = "MONKEY" #RIGHT TOP

        pie.operator("keyops.add_mesh", text="Quad Sphere", icon="MESH_UVSPHERE").mesh_type = "QUADSPHERE" #LEFT BOTTOM

        pie.operator("keyops.add_mesh", text="Circle", icon="MESH_CIRCLE").mesh_type = "CIRCLE" #RIGHT BOTTOM  

class ViewCameraPie(Menu):
    bl_idname = "KEYOPS_MT_view_camera_pie"
    bl_label = "View Camera Pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        pie.operator("view3d.view_axis", text="Left", icon="MESH_MONKEY").type = 'LEFT'   #LEFT
        pie.operator("view3d.view_axis", text="Right", icon="MESH_MONKEY").type = 'RIGHT' #RIGHT
        pie.operator("view3d.view_axis", text="Bottom", icon="MESH_MONKEY").type = 'BOTTOM' #BOTTOM
        pie.operator("view3d.view_axis", text="Top", icon="MESH_MONKEY").type = 'TOP' #TOP

class AddModifierPie(Menu):
    bl_idname = "KEYOPS_MT_add_modifier_pie"
    bl_label = "Add Modifier Pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        
        global hardops

        if hardops is None:
            hardops = get_is_addon_enabled("HOps")

        if hardops:
            pie.operator("hops.st3_array", text="Array", icon="MOD_ARRAY")# LEFT
        else:
            pie.operator("object.modifier_add", text="Array", icon="MOD_ARRAY").type = "ARRAY" # LEFT

        if hardops:
            pie.operator("hops.adjust_tthick", text="Solidify", icon="MOD_SOLIDIFY") #RIGHT
        else:
            pie.operator("object.modifier_add", text="Solidify", icon="MOD_SOLIDIFY").type = "SOLIDIFY" #RIGHT

        if hardops:
            pie.operator("hops.adjust_bevel", text="Bevel", icon="MOD_BEVEL") #BOTTOM
        else:
            pie.operator("object.modifier_add", text="Bevel", icon="MOD_BEVEL").type = "BEVEL" #BOTTOM

        pie.operator("keyops.add_modifier", text="Weighted Normal", icon="MOD_NORMALEDIT"). type = "WEIGHTED_NORMAL" #TOP
      
        pie.operator("keyops.add_modifier", text="Lattice", icon="MOD_LATTICE").type = "LATTICE" #LEFT TOP

        pie.operator("keyops.add_modifier", text="Weld", icon="AUTOMERGE_OFF").type = "WELD" #RIGHT TOP

        pie.operator("keyops.add_modifier", text="Triangulate", icon="MOD_TRIANGULATE").type = "TRIANGULATE" #LEFT BOTTOM

        if hardops:
            pie.operator("hops.mod_shrinkwrap", text="Shrinkwrap", icon="MOD_SHRINKWRAP") #RIGHT BOTTOM
        else:
            pie.operator("object.modifier_add", text="Shrinkwrap", icon="MOD_SHRINKWRAP").type = "SHRINKWRAP" #RIGHT BOTTOM

class SwitchWorkspace(bpy.types.Operator):
    bl_idname = "keyops.switch_workspace"
    bl_label = "Switch Workspace"

    workspace_name: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        bpy.context.window.workspace = bpy.data.workspaces[self.workspace_name]
        return {'FINISHED'}

class WorkspacePie(Menu):
    bl_idname = "KEYOPS_MT_workspace_pie"
    bl_label = "Workspace Pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        pie.operator("keyops.switch_workspace", text="Layout", icon="GRID").workspace_name = "Layout" #LEFT

        pie.operator("keyops.switch_workspace", text="Modeling", icon="EDITMODE_HLT").workspace_name = "Modeling" #RIGHT

        pie.operator("keyops.switch_workspace", text="Shading", icon="MATERIAL").workspace_name = "Shading" #BOTTOM

        pie.operator("keyops.switch_workspace", text="UV Editor", icon="UV").workspace_name = "UV Editing" #TOP

        pie.operator("keyops.switch_workspace", text="Scripting", icon="SCRIPT").workspace_name = "Scripting" #LEFT TOP

        pie.operator("keyops.switch_workspace", text="Texture Paint", icon="BRUSHES_ALL").workspace_name = "Texture Paint" #RIGHT TOP

        pie.operator("keyops.switch_workspace", text="Geometry Nodes", icon="GEOMETRY_NODES").workspace_name = "Geometry Nodes" #LEFT BOTTOM

        pie.operator("keyops.switch_workspace", text="Sculpting", icon="SCULPTMODE_HLT").workspace_name = "Sculpting" #RIGHT BOTTOM

    def register():
        bpy.utils.register_class(SwitchWorkspace)

    def unregister():
        bpy.utils.unregister_class(SwitchWorkspace)

class CursorPie(Menu):
    bl_idname = "KEYOPS_MT_cursor_pie"
    bl_label = "Cursor Pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        pie.operator("keyops.origin_to_selection", text="Origin to 3D Cursor", icon="LAYER_USED").type= "origin_to_3d_cursor" #LEFT

        pie.operator("keyops.origin_to_selection", text="Origin to Selection", icon="LAYER_USED").type= "origin_to_geometry" #RIGHT

        pie.operator("view3d.snap_cursor_to_selected", text="Cursor to Selection", icon="CURSOR") #BOTTOM

        pie.operator("view3d.snap_selected_to_cursor", text="Selection to Cursor", icon="RESTRICT_SELECT_OFF") #TOP

        pie.operator("view3d.snap_selected_to_grid", text="Selection to Grid", icon="SNAP_GRID") #LEFT TOP
        
        pie.operator('view3d.snap_cursor_to_grid', text="Cursor to Grid", icon="SNAP_GRID") #RIGHT TOP

        pie.operator("view3d.snap_cursor_to_center", text="Cursor to World Origin", icon="PIVOT_CURSOR") #LEFT BOTTOM
        
        pie.operator('view3d.snap_cursor_to_active', text="Cursor to Active", icon="CURSOR") #RIGHT BOTTOM

class UVSpacePie(Menu):
    bl_idname = "KEYOPS_MT_uv_space_pie"
    bl_label = "UV Space Pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        global uvtoolkit
        global uvpackmaster
        global zenuv

        if uvtoolkit is None:
            uvtoolkit = get_is_addon_enabled("UVToolkit-main" or "UVToolkit")
        if uvpackmaster is None:
            uvpackmaster = get_is_addon_enabled("uvpackmaster3" or "uvpackmaster2" or "uvpackmaster")
        if zenuv is None:
            zenuv = get_is_addon_enabled("ZenUV")
       
        if uvtoolkit:
            pie.operator("keyops.streighten_selection", text="Straighten Quads", icon="UV_ISLANDSEL") #LEFT
        elif zenuv:
            pie.operator("uv.zenuv_quadrify", text="Straighten Quads", icon="UV_ISLANDSEL") #LEFT
        if zenuv:
             pie.operator("uv.zenuv_isolate_island", text="Isolate Island (Toggle)") #RIGHT
        else:
            pie.operator("keyops.isolate_uv_island", text="Isolate Island (Toggle)") #RIGHT
        # if uvpackmaster and zenuv:
        #     pie.operator("uv.zenuv_pack", text="Pack Master", icon="MOD_MULTIRES") #BOTTOM
        # else:
        pie.operator("keyops.quick_pack", text="Quick Pack", icon="MOD_MULTIRES") #BOTTOM

        pie.operator("uv.unwrap", text="Unfold and Pack", icon="UV_FACESEL") #TOP

        pie.operator("keyops.unfold_selected", text="Unfold Selected", icon="UV_VERTEXSEL") #LEFT TOP

        if zenuv:
            pie.operator("uv.zenuv_unwrap_inplace", text="Unfold Inplace", icon="STICKY_UVS_VERT") #RIGHT TOP
        else:
            pie.operator("keyops.unfold_inplace", text="Unfold Inplace", icon="STICKY_UVS_VERT") #RIGHT TOP

        if uvtoolkit and zenuv:
            if bpy.context.tool_settings.use_uv_select_sync:
                pie.operator("uv.zenuv_reshape_island", text="Straighten after Edge", icon="UV_EDGESEL") #LEFT BOTTOM
            else:    
                pie.operator("uv.toolkit_straighten_island", text="Straighten after Edge", icon="UV_EDGESEL")
        elif uvtoolkit:
            pie.operator("keyops.streighten_after_edge", text="Straighten after Edge", icon="UV_EDGESEL")
        elif zenuv:
            pie.operator("uv.zenuv_reshape_island", text="Straighten after Edge", icon="UV_EDGESEL") #LEFT BOTTOM

        pie.operator("image.view_selected", text="View Selected", icon="ZOOM_SELECTED") #RIGHT BOTTOM

    def register():
        bpy.utils.register_class(IsolateUVIsland)
        bpy.utils.register_class(QuickPack)
        bpy.utils.register_class(UnfoldSelected)
        bpy.utils.register_class(StreightenSelection)
        bpy.utils.register_class(StreightenAfterEdge)
        bpy.utils.register_class(UnfoldInplace)

    def unregister():
        bpy.utils.unregister_class(IsolateUVIsland)
        bpy.utils.unregister_class(QuickPack)
        bpy.utils.unregister_class(UnfoldSelected)
        bpy.utils.unregister_class(StreightenSelection)
        bpy.utils.unregister_class(StreightenAfterEdge)
        bpy.utils.unregister_class(UnfoldInplace)

class UVUPie(Menu):
    bl_idname = "KEYOPS_MT_uv_u_pie"
    bl_label = "UV U Pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        uvpackmaster = None
        uvtoolkit = None
        zenuv = None
        polyquilt = None

        if zenuv is None:
            zenuv = get_is_addon_enabled("ZenUV")
        if uvtoolkit is None:
            uvtoolkit = get_is_addon_enabled("UVToolkit-main" or "UVToolkit")
        if uvpackmaster is None:
            uvpackmaster = get_is_addon_enabled("uvpackmaster3" or "uvpackmaster2" or "uvpackmaster")
        if polyquilt is None:
            polyquilt = get_is_addon_enabled("PolyQuilt")

        pie.prop(context.scene.tool_settings, "use_edge_path_live_unwrap", text="Live Unwrap", toggle=True) #LEFT

        pie.operator("wm.call_menu", text="UV Mapping Menu").name = "VIEW3D_MT_uv_map" #RIGHT     
  
        pie.operator("keyops.seam_by_angle", text="Seam by Angle", icon="MOD_EDGESPLIT") #BOTTOM
      
        pie.operator("uv.unwrap", text="Unfold and Pack", icon= "UV_FACESEL") #TOP

        if polyquilt:
            pie.operator("wm.tool_set_by_id", text="Seam Tool", icon="MOD_LINEART").name = "mesh_tool.poly_quilt_seam" #LEFT TOP 

        pie.prop(context.scene.tool_settings, "use_transform_correct_face_attributes", text="Correct Face Attributesg", toggle=True) #RIGHT TOP
        
        if zenuv and bpy.context.mode == 'EDIT_MESH':
            pie.operator("uv.zenuv_quadrify", text="Quadrify Island after edge", icon="UV_ISLANDSEL") #LEFT BOTTOM
        elif bpy.context.mode == "OBJECT":
            pie.operator("keyops.make_single_user" , text="Make Single User") #LEFT BOTTOM

        pie.operator("keyops.smooth_by_sharp", text="Smooth by Sharp Edge") #RIGHT BOTTOM
    def register():
        bpy.utils.register_class(AutoSeam)
        bpy.utils.register_class(ToggleSmoothSharp)
        bpy.utils.register_class(MakeSingleUser)
        #bpy.utils.register_class(UVMappingMenu)
        bpy.utils.register_class(UnwrapingOp)
    def unregister():
        bpy.utils.unregister_class(AutoSeam)
        bpy.utils.unregister_class(ToggleSmoothSharp)
        bpy.utils.unregister_class(MakeSingleUser)
        #bpy.utils.unregister_class(UVMappingMenu)
        bpy.utils.unregister_class(UnwrapingOp)

class UVQPie(Menu):
    bl_description = "UV Q Pie"
    bl_idname = "KEYOPS_MT_uv_q_pie"
    bl_label = "UV Q Pie"

    uvpackmaster = None
    uvtoolkit = None
    zenuv = None
    polyquilt = None

    if zenuv is None:
        zenuv = get_is_addon_enabled("ZenUV")
    if uvtoolkit is None:
        uvtoolkit = get_is_addon_enabled("UVToolkit-main" or "UVToolkit")
    if uvpackmaster is None:
        uvpackmaster = get_is_addon_enabled("uvpackmaster3" or "uvpackmaster2" or "uvpackmaster")
    if polyquilt is None:
        polyquilt = get_is_addon_enabled("PolyQuilt")


    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        pie.operator("uv.select_overlap", text="Select Overlapping") #LEFT

        if zenuv:
            pie.operator("uv.zenuv_orient_island", text="Orient Island to Edge", icon="UV_EDGESEL").mode="BY_SELECTION" #RIGHT
        else:
            pie.operator("keyops.orient_island_to_edge", text="Orient Island to Edge") #RIGHT
          
        pie.operator("keyops.stack_similar_islands" , text="Stack Similar Islands", icon="CON_SIZELIKE") #BOTTOM

        if uvtoolkit:
            pie.operator("uv.toolkit_sharp_edges_from_uv_islands" , text="Sharp Edges from UV Islands", icon="MOD_EDGESPLIT") #TOP
        else:
            pie.operator("keyops.sharp_by_uv_borders" , text="Sharp Edges from UV Islands", icon="MOD_EDGESPLIT")
        
        pie.operator("uv.seams_from_islands", text="Seams from Islands") #LEFT TOP

        if zenuv:
            pie.operator("mesh.zenuv_mirror_seams", text="Mirror Seams", icon="MOD_MIRROR") #RIGHT TOP
        elif uvtoolkit:
            pie.operator("uv.toolkit_mirror_seam" , text="Mirror Seams", icon="MOD_MIRROR") #RIGHT TOP
        else:
            pie.operator("keyops.mirror_seams" , text="Mirror Selected Seams", icon="MOD_MIRROR")

        if uvpackmaster:
            pie.operator("uvpackmaster3.split_overlapping", text="Unstack Islands", icon="MOD_ARRAY") #LEFT BOTTOM
        elif zenuv:
            pie.operator("uv.zenuv_unstack", text="Unstack Islands", icon="MOD_ARRAY") #LEFT BOTTOM
        elif uvtoolkit:
            pie.operator("uv.toolkit_unstack_overlapped_uvs", text="Unstack Islands", icon="MOD_ARRAY") #LEFT BOTTOM
        
        if zenuv:
            pie.operator("uv.zenuv_select_similar", text="Select Similar Islands")
        else:
            pie.operator("keyops.select_similar_islands", text="Select Similar Islands")

        
    def register():
        bpy.utils.register_class(OrientIslandToEdge)
        bpy.utils.register_class(StackSimilarIslands)
        bpy.utils.register_class(SharpByUVBorders)
        bpy.utils.register_class(MirrorSeams)
        bpy.utils.register_class(SelectSimilarIslands)
    def unregister():   
        bpy.utils.unregister_class(OrientIslandToEdge)
        bpy.utils.unregister_class(StackSimilarIslands)
        bpy.utils.unregister_class(SharpByUVBorders)
        bpy.utils.unregister_class(MirrorSeams)
        bpy.utils.unregister_class(SelectSimilarIslands)

class AutoSeam(bpy.types.Operator):
    bl_idname = "keyops.seam_by_angle"
    bl_label = "Seam by Angle"
    bl_options = {'REGISTER', 'UNDO'}
    
    angle : bpy.props.FloatProperty(name="Angle", default=1.0472, min=0.0, max=180.0, description="Angle", subtype="ANGLE") # type: ignore
    selection : bpy.props.BoolProperty(name="On Selection Only", default=False, description="Selection") # type: ignore
    mark_seams : bpy.props.BoolProperty(name="Mark Seams", default=True, description="Mark Seams") # type: ignore
    mark_sharp : bpy.props.BoolProperty(name="Mark Sharp", default=True, description="Mark Sharp") # type: ignore
    keep_existing_seams : bpy.props.BoolProperty(name="Keep Existing Seams", default=False, description="Keep Existing Seams") # type: ignore
    shading_by_sharp_edge : bpy.props.BoolProperty(name="Smooth by Sharp Edge", default=True, description="Shading by Sharp Edge") # type: ignore
    select_seams : bpy.props.BoolProperty(name="Select New Seams", default=False, description="Select Seams") # type: ignore

    def auto_seam(self, context):
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')
            
        if self.selection:
            bpy.ops.mesh.select_all(action='INVERT')
            bpy.ops.mesh.hide(unselected=False)
            bpy.ops.mesh.select_all(action='INVERT')
            bpy.ops.mesh.select_all(action='DESELECT')

        if not self.keep_existing_seams:
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.mark_seam(clear=True)
            bpy.ops.mesh.mark_sharp(clear=True)

        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.edges_select_sharp(sharpness= self.angle)

        if self.mark_seams:
            bpy.ops.mesh.mark_seam(clear=False)
        if self.mark_sharp:
            bpy.ops.mesh.mark_sharp(clear=False)

        if not self.select_seams:
            bpy.ops.mesh.select_all(action='DESELECT')
        if self.selection:
            bpy.ops.mesh.reveal(select=False)
        if self.shading_by_sharp_edge:
            bpy.ops.keyops.smooth_by_sharp()
        return {'FINISHED'}

    def execute(self, context):
        if bpy.context.mode == 'EDIT_MESH':
            self.auto_seam(context)
        if bpy.context.mode == 'OBJECT':
            bpy.ops.object.mode_set(mode='EDIT')
            self.auto_seam(context)
            bpy.ops.object.mode_set(mode='OBJECT')
        
        return {'FINISHED'}
          
class ToggleSmoothSharp(bpy.types.Operator):
    bl_idname = "keyops.smooth_by_sharp"
    bl_label = "Toggle Smooth Sharp"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' 

    def execute(self, context):
        if bpy.context.mode == 'EDIT_MESH':
            for obj in context.objects_in_mode:
                
                for obj in context.objects_in_mode:
                    me, bm = obj.data, bmesh.from_edit_mesh(obj.data)
                    for face in bm.faces:
                        if not face.smooth:
                            face.smooth = True

                    bmesh.update_edit_mesh(me, loop_triangles=False)

                    obj.data.auto_smooth_angle = 3.141590118408203
                    obj.data.use_auto_smooth = True
            
        elif bpy.context.mode == 'OBJECT':
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                        bpy.ops.object.shade_smooth(use_auto_smooth=True, auto_smooth_angle=3.14159)

        return {'FINISHED'}

class MakeSingleUser(bpy.types.Operator):
    bl_description = "Make Single User"
    bl_idname = "keyops.make_single_user"
    bl_label = "Make Single User"
    bl_options = {'REGISTER', 'UNDO'}

    object : bpy.props.BoolProperty(name="Object", default=True, description="Object") # type: ignore
    obdata : bpy.props.BoolProperty(name="Data", default=True, description="Data") # type: ignore
    materials : bpy.props.BoolProperty(name="Materials", default=False, description="Materials") # type: ignore
    object_animation : bpy.props.BoolProperty(name="Object Animation", default=False, description="Object Animation") # type: ignore
    object_animation_data : bpy.props.BoolProperty(name="Object Animation Data", default=False, description="Object Animation Data") # type: ignore

    def execute(self, context):
        bpy.ops.object.make_single_user(object=self.object, obdata=self.obdata, material=self.materials, animation=self.object_animation, obdata_animation=self.object_animation_data)
        return {'FINISHED'}

class UVMappingMenu(Menu):
    bl_description = "UV Mapping Menu"
    bl_idname = "VIEW3D_MT_uv_map_menu"
    bl_label = "UV Mapping"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("keyops.unwraping_op", text="Unwrap").unwrap_options = "unwrap"
        row = layout.row()
        row.operator("keyops.unwraping_op", text="Smart Project").unwrap_options = "smart_project"
        row = layout.row()
        row.operator("keyops.unwraping_op", text="Lightmap Pack").unwrap_options = "lightmap_pack"
        row = layout.row()
        row.operator("keyops.unwraping_op", text="Follow Active Quads").unwrap_options = "follow_active_quads"
        row = layout.row()
        row.operator("keyops.unwraping_op", text="Cube Project").unwrap_options = "cube_project"
        row = layout.row()
        row.operator("keyops.unwraping_op", text="Cylinder Project").unwrap_options = "cylinder_project"
        row = layout.row()
        row.operator("keyops.unwraping_op", text="Sphere Project").unwrap_options = "sphere_project"
        row = layout.row()
        row.operator("keyops.unwraping_op", text="Project From View").unwrap_options = "project_from_view"
        row = layout.row()
        row.operator("keyops.unwraping_op", text="Project From View Bounds").unwrap_options = "project_from_view_bounds"
        row = layout.row()
        row.operator("keyops.unwraping_op", text="Reset").unwrap_options = "reset"  

class UnwrapingOp(bpy.types.Operator):
    bl_description = "Unwraping Operator"
    bl_idname = "keyops.unwraping_op"
    bl_label = "Unwraping Operator"
    bl_options = {'REGISTER', 'UNDO'}

    unwrap_options: bpy.props.EnumProperty(
        items=[ 
            ("unwrap", "Unwrap", "Unwrap"),
            ("smart_project", "Smart Project", "Smart Project"),
            ("lightmap_pack", "Lightmap Pack", "Lightmap Pack"),
            ("follow_active_quads", "Follow Active Quads", "Follow Active Quads"),
            ("cube_project", "Cube Project", "Cube Project"),
            ("cylinder_project", "Cylinder Project", "Cylinder Project"),
            ("sphere_project", "Sphere Project", "Sphere Project"),
            ("project_from_view", "Project From View", "Project From View"),
            ("project_from_view_bounds", "Project From View Bounds", "Project From View Bounds"),
            ("reset", "Reset", "Reset")], #type: ignore
        name="Unwrap Types",
        description="Unwrap Options",
        default="unwrap"
    )

    pack_islands: bpy.props.BoolProperty(
        name="Pack Islands",
        description="Pack Islands",
        default=False) # type: ignore
        
    def execute(self, context):
        bpy.ops.uv
        if self.pack_islands:
            bpy.ops.uv.pack_islands()
        
class IsolateUVIsland(bpy.types.Operator):
    bl_description = "Isolate UV Island"
    bl_idname = "keyops.isolate_uv_island"
    bl_label = "Isolate UV Island"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'
    
    def execute(self, context):
        if context.tool_settings.use_uv_select_sync:
            bpy.ops.uv.select_linked()
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
            bpy.context.scene.tool_settings.use_uv_select_sync = False
        else:
            bpy.ops.keyops.smart_uv_sync()
            bpy.context.scene.tool_settings.use_uv_select_sync = False

        return {'FINISHED'}

class QuickPack(bpy.types.Operator):
    bl_description = "Quick Pack"
    bl_idname = "keyops.quick_pack"
    bl_label = "Quick Pack"
    bl_options = {'REGISTER', 'UNDO'}

    #add advance settings cheackbox with all settings?

    margin: bpy.props.FloatProperty(name="Margin",description="Margin",default=0.001) # type: ignore
    scale: bpy.props.BoolProperty(name="Scale",description="Scale",default=True) # type: ignore
    
    rotate: bpy.props.BoolProperty(name="Rotate",description="Rotate",default=True) # type: ignore
    rotate_method: bpy.props.EnumProperty(
        items=[ 
            ("AXIS_ALIGNED", "Axis Aligned", "Axis Aligned"),
            ("CARDINAL", "Cardinal", "Cardinal"),
            ("ANY", "Any", "Any")],#type: ignore
        name="Rotate Method",description="Rotate Method",default="CARDINAL")

    merge_overlapping: bpy.props.BoolProperty(name="Merge Overlapping",description="Merge Overlapping",default=False) # type: ignore

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'
    
    
    def execute(self, context):
        bpy.ops.uv.pack_islands(rotate_method=self.rotate_method, margin=self.margin, shape_method='AABB', rotate=self.rotate, scale=self.scale, merge_overlap=self.merge_overlapping)
        return {'FINISHED'}

class UnfoldSelected(bpy.types.Operator):
    bl_description = "Unfold Selected"
    bl_idname = "keyops.unfold_selected"
    bl_label = "Unfold Selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'
    
    reset_uv_sync = False

    def execute(self, context):
        global zenuv

        if zenuv is None:
            zenuv = get_is_addon_enabled("ZenUV")
    
        if not zenuv:
            if context.tool_settings.use_uv_select_sync:
                if bpy.context.scene.smart_uv_sync_enable == False:
                    bpy.context.scene.smart_uv_sync_enable = True
                    self.reset_uv_sync = True
                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
                bpy.ops.keyops.smart_uv_sync()
                bpy.ops.uv.unwrap()
                bpy.ops.keyops.smart_uv_sync()
                if self.reset_uv_sync:
                    bpy.context.scene.smart_uv_sync_enable = False
            else:
                bpy.ops.uv.unwrap()
        else:
            if bpy.context.scene.tool_settings.use_uv_select_sync == True:
                bpy.ops.uv.zenuv_unwrap_constraint()

            else:
                bpy.ops.uv.unwrap()
        return {'FINISHED'}


class UnfoldInplace(bpy.types.Operator):
    bl_description = "Unfold Inplace"
    bl_idname = "keyops.unfold_inplace"
    bl_label = "Unfold Inplace"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        if not zenuv:
            if context.tool_settings.use_uv_select_sync:
                if bpy.context.scene.smart_uv_sync_enable == False:
                    bpy.context.scene.smart_uv_sync_enable = True
                    self.reset_uv_sync = True
                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
                bpy.ops.keyops.smart_uv_sync()
                bpy.ops.uv.unwrap()
                bpy.ops.keyops.smart_uv_sync()
                if self.reset_uv_sync:
                    bpy.context.scene.smart_uv_sync_enable = False
            else:
                bpy.ops.uv.unwrap()
        return {'FINISHED'}


class StreightenSelection(bpy.types.Operator):
    bl_description = "Streighten Selected"
    bl_idname = "keyops.streighten_selection"
    bl_label = "Streighten Selected"
    bl_options = {'REGISTER', 'UNDO'}

    pine_island : bpy.props.BoolProperty(
        name="Pin Island",
        description="Pin Island",
        default=True) # type: ignore

    global uvtoolkit
    global zenuv

    if uvtoolkit is None:
        uvtoolkit = get_is_addon_enabled("UVToolkit-main" or "UVToolkit")
    
    if zenuv is None:
        zenuv = get_is_addon_enabled("ZenUV")

    def execute(self, context):
            if bpy.context.scene.tool_settings.use_uv_select_sync == True:  
                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
                bpy.ops.keyops.smart_uv_sync()
                bpy.ops.uv.toolkit_straighten(gridify=False)
                bpy.ops.keyops.smart_uv_sync()

            else:
                bpy.ops.uv.toolkit_straighten(gridify=False)

            if self.pine_island:
                bpy.ops.uv.pin()   

            return {'FINISHED'}
    
class StreightenAfterEdge(bpy.types.Operator):
    bl_description = "Streighten After Edge"
    bl_idname = "keyops.streighten_after_edge"
    bl_label = "Streighten After Edge"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if bpy.context.scene.tool_settings.use_uv_select_sync == True:  
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
            bpy.ops.keyops.smart_uv_sync()
            bpy.ops.uv.toolkit_straighten_island()
            bpy.ops.keyops.smart_uv_sync()

        else:
            bpy.ops.uv.toolkit_straighten_island()

        return {'FINISHED'}

class OrientIslandToEdge(bpy.types.Operator):
    bl_description = "Orient Island to Edge"
    bl_idname = "keyops.orient_island_to_edge"
    bl_label = "Orient Island to Edge"
    bl_options = {'REGISTER', 'UNDO'}

    uvtoolkit = None

    if uvtoolkit is None:
        uvtoolkit = get_is_addon_enabled("UVToolkit-main" or "UVToolkit")

    def execute(self, context):
        if uvtoolkit:
            if bpy.context.scene.tool_settings.use_uv_select_sync:
                bpy.ops.keyops.smart_uv_sync()
                bpy.ops.uv.toolkit_orient_to_edge()
            else:
                bpy.ops.uv.toolkit_orient_to_edge()
            return {'FINISHED'}

        else:
            if bpy.context.scene.tool_settings.use_uv_select_sync:
                bpy.ops.keyops.smart_uv_sync()
                bpy.ops.uv.select_more()
                bpy.ops.uv.select_less()
                bpy.ops.uv.align_rotation(method='EDGE')
                bpy.ops.keyops.smart_uv_sync()
            else:
                bpy.ops.uv.align_rotation(method='EDGE')
            return {'FINISHED'}

class StackSimilarIslands(bpy.types.Operator):
    bl_description = "Stack Similar Islands"
    bl_idname = "keyops.stack_similar_islands"
    bl_label = "Stack Similar Islands"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global uvpackmaster

        if uvpackmaster is None:
            uvpackmaster = get_is_addon_enabled("uvpackmaster3" or "uvpackmaster2" or "uvpackmaster")

        if uvpackmaster:
            bpy.ops.uvpackmaster3.align_similar()
        else:
            bpy.ops.uv.copy()
            bpy.ops.uv.paste()
        return {'FINISHED'}

class SharpByUVBorders(bpy.types.Operator):
    bl_description = "Sharp By UV Borders"
    bl_idname = "keyops.sharp_by_uv_borders"
    bl_label = "Sharp By UV Borders"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None
    
    def execute(self, context):
        bpy.ops.keyops.smooth_by_sharp()
        bpy.ops.uv.seams_from_islands(mark_seams=False, mark_sharp=True)
        return {'FINISHED'}

class MirrorSeams(bpy.types.Operator):
    bl_description = "Mirror Seams"
    bl_idname = "keyops.mirror_seams"
    bl_label = "Mirror Seams"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None
    
    def execute(self, context):
        bpy.ops.mesh.select_mirror(extend=True)
        bpy.ops.mesh.mark_seam()
        return {'FINISHED'}
    
class SelectSimilarIslands(bpy.types.Operator):
    bl_description = "Select Similar Islands"
    bl_idname = "keyops.select_similar_islands"
    bl_label = "Select Similar Islands"
    bl_options = {'REGISTER', 'UNDO'}

    global uvtoolkit

    if uvtoolkit is None:
        uvtoolkit = get_is_addon_enabled("UVToolkit-main" or "UVToolkit")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None
    
    def execute(self, context):
        if uvtoolkit:
            bpy.ops.uv.select_similar()
        else:
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
            if bpy.context.tool_settings.use_uv_select_sync:
                bpy.ops.keyops.smart_uv_sync()

            bpy.ops.uv.select_mode(type='ISLAND')

            bpy.ops.uv.select_similar(type='FACE', threshold=0.01)

            return {'FINISHED'}