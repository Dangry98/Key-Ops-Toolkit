import bpy.types
from bpy.types import Menu
from ..utils.pref_utils import get_is_addon_enabled
from ..utils.pref_utils import get_keyops_prefs


hardops = None
uvpackmaster = None
uvtoolkit = None
zenuv = None
polyquilt = None

class SwitchWorkspace(bpy.types.Operator):
    bl_idname = "keyops.switch_workspace"
    bl_label = "Switch Workspace"
    bl_options = {'INTERNAL'}

    workspace_name: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        if self.workspace_name in bpy.data.workspaces:
            bpy.context.window.workspace = bpy.data.workspaces[self.workspace_name]
        else:
            bpy.ops.workspace.append_activate(idname=self.workspace_name, filepath= bpy.utils.user_resource('CONFIG', path='startup.blend'))
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
        pie.operator("uv.keyops_quick_pack", text="Quick Pack", icon="CON_SAMEVOL") #BOTTOM

        pie.operator("uv.keyops_unwrap_in_place", text="Unwrap Inplace", icon="STICKY_UVS_VERT") #TOP

        pie.operator("uv.unwrap", text="Unwrap and Pack", icon="UV_FACESEL") #LEFT TOP

        pie.operator("keyops.unwrap_selected", text="Unwrap Selected", icon="UV_VERTEXSEL") #RIGHT TOP

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
        bpy.utils.register_class(StreightenSelection)
        bpy.utils.register_class(StreightenAfterEdge)
        bpy.utils.register_class(UVQPie)

    def unregister():
        bpy.utils.unregister_class(StreightenSelection)
        bpy.utils.unregister_class(StreightenAfterEdge)
        bpy.utils.unregister_class(UVQPie)

class UtilityPie(Menu):
    bl_idname = "KEYOPS_MT_utility_pie"
    bl_label = "Utility Pie"

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
            polyquilt = get_is_addon_enabled("PolyQuilt_Fork")

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
        
        pie.prop(context.scene.tool_settings, "use_mesh_automerge", text="Auto Merge", toggle=True) #RIGHT BOTTOM
      
        
    def register():

        bpy.utils.register_class(MakeSingleUser)
        #bpy.utils.register_class(UVMappingMenu)
        bpy.utils.register_class(UnwrapingOp)
    def unregister():
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
        polyquilt = get_is_addon_enabled("PolyQuilt_Fork")


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
            pie.operator("keyops.sharp_from_uv_islands" , text="Sharp Edges from UV Islands", icon="MOD_EDGESPLIT")
        
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
        bpy.utils.register_class(StackSimilarIslands)
        bpy.utils.register_class(MirrorSeams)
        bpy.utils.register_class(SelectSimilarIslands)
    def unregister():   
        bpy.utils.unregister_class(StackSimilarIslands)
        bpy.utils.unregister_class(MirrorSeams)
        bpy.utils.unregister_class(SelectSimilarIslands)

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