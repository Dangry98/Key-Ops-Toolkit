import bmesh
import bpy
from ..utils.pref_utils import get_keyops_prefs, get_is_addon_enabled
from ..utils.utilities import BLENDER_VERSION

#Based on the code from the excellent addon UV Toolkit by Alex Dev that is sadly no longer available, please come back Alex! :( 
#Only an very old version is still available, but I doubt it still works in new version of Blender  https://alexbel.gumroad.com/l/NbMya
#The Toggle UV sync was an serverly underrated operation that basically fixes the uv editor in Blender, and I wanted to highlight its importance and keep it alive since its no longer officaly available anywhere. 
#Its the only way to get the UV editor in Blender to not be a horrible slow mess to work in and its a must have for anyone who works with UVs.

class SmartUVSync(bpy.types.Operator):
    bl_idname = "keyops.smart_uv_sync"
    bl_label = "KeyOps: Smart UV Sync"
    bl_description = "Toggle Sync Mode and UV Selection while preserving selection and selection mode"
    bl_options = {'REGISTER'}

    fast_sync: bpy.props.BoolProperty(name="Fast Mode", default=False, description="Fast Mode, Right Click to Toggle Sync Mode and UV Selection, can be slow on very large meshes") # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'
    
    def fast_sync(self, context):
        if bpy.context.scene.tool_settings.use_uv_select_sync:
            bpy.context.scene.tool_settings.use_uv_select_sync = True
        else:
            bpy.context.scene.tool_settings.use_uv_select_sync = False
            bpy.ops.mesh.select_all(action='SELECT')

    def sync_uv_selction_mode(self, context, uv_sync_enable):
        scene = context.scene

        vertex = True, False, False
        edge = False, True, False
        face = False, False, True

        if uv_sync_enable:
            uv_select_mode = scene.tool_settings.uv_select_mode
            tool_settings = context.tool_settings

            if uv_select_mode == 'VERTEX':
                tool_settings.mesh_select_mode = vertex
            if uv_select_mode == 'EDGE':
                tool_settings.mesh_select_mode = edge
            if uv_select_mode == 'FACE':
                tool_settings.mesh_select_mode = face

        else:
            mesh_select_mode = context.tool_settings.mesh_select_mode[:]
            tool_settings = scene.tool_settings

            if mesh_select_mode == vertex:
                tool_settings.uv_select_mode = 'VERTEX'
            if mesh_select_mode == edge:
                tool_settings.uv_select_mode = 'EDGE'
            if mesh_select_mode == face:
                tool_settings.uv_select_mode = 'FACE'

    def sync_selected_elements(self, context, uv_sync_enable):
        objects_in_mode_unique_data = context.objects_in_mode_unique_data
        if self.fast_sync:
            for ob in objects_in_mode_unique_data:
                objects_in_mode_unique_data = [ob for ob in objects_in_mode_unique_data if ob.data.total_vert_sel > 0]
        for ob in objects_in_mode_unique_data:
                me = ob.data
                bm = bmesh.from_edit_mesh(me)

                uv_layer = bm.loops.layers.uv.verify()

                if uv_sync_enable:
                    for face in bm.faces:
                        for loop in face.loops:
                            loop_uv = loop[uv_layer]
                            if not loop_uv.select:
                                face.select = False

                    for face in bm.faces:
                        for loop in face.loops:
                            loop_uv = loop[uv_layer]
                            if loop_uv.select:
                                loop.vert.select = True

                    for edge in bm.edges:
                        vert_count = 0
                        for vert in edge.verts:
                            if vert.select:
                                vert_count += 1
                        if vert_count == 2:
                            edge.select = True

                else:
                    for face in bm.faces:
                        for loop in face.loops:
                            loop_uv = loop[uv_layer]
                            loop_uv.select = False

                    mesh_select_mode = context.tool_settings.mesh_select_mode[:]

                    if mesh_select_mode[2]:  # face
                        for face in bm.faces:
                            if face.select:
                                for loop in face.loops:
                                    loop_uv = loop[uv_layer]
                                    if loop.vert.select:
                                        loop_uv.select = True
                    # if mesh_select_mode[1]:  # edge
                    #     bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
                    #     print ("edge")

                    
                    else: #vertex
                        for face in bm.faces:
                            for loop in face.loops:
                                loop_uv = loop[uv_layer]
                                if loop.vert.select:
                                    loop_uv.select = True

                    for face in bm.faces:
                        face.select = True
            
                bmesh.update_edit_mesh(me)


    def execute(self, context):
        tool_settings = context.tool_settings
        uv_sync_enable = not tool_settings.use_uv_select_sync
        tool_settings.use_uv_select_sync = uv_sync_enable

        if context.scene.smart_uv_sync_enable:
            self.sync_uv_selction_mode(context, uv_sync_enable)
            if BLENDER_VERSION < (5,0,0):
                self.sync_selected_elements(context, uv_sync_enable)
        else:
            self.fast_sync(context)

        return {'FINISHED'}

    def register():
        # bpy.utils.register_class(UVEDITORSMARTUVSYNC_PT_Panel)
        bpy.types.Scene.smart_uv_sync_enable = bpy.props.BoolProperty(name="Enable", default=True, description="Right Click to Toggle Sync Mode and UV Selection, can be slow on very large meshes")
        bpy.utils.register_class(UVCut)
        bpy.utils.register_class(SharpFromUVIslands)
        bpy.utils.register_class(UnwrapInPlace)
        bpy.utils.register_class(AutoSeam)
        bpy.utils.register_class(ToggleSmoothSharp)
        bpy.utils.register_class(OrientIslandToEdge)
        bpy.utils.register_class(UnwrapSelected)
        bpy.utils.register_class(QuickPack)
        bpy.utils.register_class(IsolateUVIsland)
        bpy.utils.register_class(RemoveSeam)
        # bpy.utils.register_class(SelectSimilarUVIsland)
        bpy.utils.register_class(RemoveAllPins)

    def unregister():
        # bpy.utils.unregister_class(UVEDITORSMARTUVSYNC_PT_Panel)
        del bpy.types.Scene.smart_uv_sync_enable
        bpy.utils.unregister_class(UVCut)
        bpy.utils.unregister_class(SharpFromUVIslands)
        bpy.utils.unregister_class(UnwrapInPlace)
        bpy.utils.unregister_class(AutoSeam)
        bpy.utils.unregister_class(ToggleSmoothSharp)
        bpy.utils.unregister_class(OrientIslandToEdge)
        bpy.utils.unregister_class(UnwrapSelected)
        bpy.utils.unregister_class(QuickPack)
        bpy.utils.unregister_class(IsolateUVIsland)
        bpy.utils.unregister_class(RemoveSeam)
        # bpy.utils.unregister_class(SelectSimilarUVIsland)
        bpy.utils.unregister_class(RemoveAllPins)


class UVCut(bpy.types.Operator):
    bl_idname = "uv.keyops_uv_cut"
    bl_label = "KeyOps: UV Cut"
    bl_description = "Maya like Cut UVs"
    bl_options = {'REGISTER', 'UNDO'}

    quick: bpy.props.BoolProperty(name="Quick", default=False, description="Quick Cut", options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        if context.tool_settings.use_uv_select_sync:
            bpy.ops.keyops.smart_uv_sync()
            self.report({'WARNING'}, "UV Sync needs to be disabled for this operation")
            bpy.ops.uv.select_mode(type='EDGE')
            return {'CANCELLED'}

        bpy.ops.uv.mark_seam('EXEC_DEFAULT', True)
        bpy.ops.uv.rip_move('EXEC_DEFAULT', True, TRANSFORM_OT_translate={'value': (0.00025, 0.00025, 0.0)}, UV_OT_rip={'location': (100.0, 100.0)})

        if self.quick:
            bpy.ops.uv.select_linked_pick('INVOKE_DEFAULT')
            bpy.ops.transform.transform('INVOKE_DEFAULT')
        return {'FINISHED'}


class SharpFromUVIslands(bpy.types.Operator):
    bl_idname = "keyops.sharp_from_uv_islands"
    bl_label = "KeyOps: Sharp From UV Islands"
    bl_description = "Mark Sharp Edges from UV Islands"
    bl_options = {'REGISTER', 'UNDO'}

    only_uv_island_borders: bpy.props.BoolProperty(name="Only UV Island Borders", default=True, description="Only UV Island Borders") # type: ignore
    apply_modifier: bpy.props.BoolProperty(name="Apply Modifier", default=False, description="Apply Modifier") # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' or context.mode == 'OBJECT'

    def execute(self, context):
        

        if "SharpFromUVIslands" not in bpy.data.node_groups:
            from ..resources.geometry_nodes_scripits import sharpfromuvislands_node_group
            sharpfromuvislands_node_group()
            
        if bpy.app.version <= (4, 0, 2):
            self.report({'WARNING'}, "This operator is not supported in Blender 4.0.2 or lower due to a bug in the Geometry Nodes")
        else:
            active_object = bpy.context.active_object

            has_toggled = False
            if self.apply_modifier:
                if context.mode == 'EDIT_MESH':
                    bpy.ops.object.mode_set(mode='OBJECT')
                    has_toggled = True

            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    if "SharpFromUVIslands" not in obj.modifiers:
                        obj.modifiers.new(name = "SharpFromUVIslands", type = 'NODES')
                        obj.modifiers["SharpFromUVIslands"].node_group = bpy.data.node_groups["SharpFromUVIslands"]
                        obj.modifiers["SharpFromUVIslands"].show_viewport = False
                        
                    context.view_layer.objects.active = obj
                    get_active_uv_layer = obj.data.uv_layers.active

                    if get_active_uv_layer:
                        context.object.modifiers["SharpFromUVIslands"]["Socket_1_attribute_name"] = get_active_uv_layer.name
                        context.object.modifiers["SharpFromUVIslands"]["Socket_2"] = self.only_uv_island_borders

                        if self.apply_modifier:
                            instances = [o for o in bpy.data.objects if o.data == obj.data]
                            if len(instances) == 1:
                                bpy.ops.object.modifier_apply(modifier="SharpFromUVIslands")
                            else:
                                self.report({'WARNING'}, "The modifier can't be applied to some linked objects, make it single user or apply manually")
                        else:
                            obj.modifiers["SharpFromUVIslands"].show_viewport = True
                    else:
                        self.report({'WARNING'}, "One or more Objects did not have a UV map!")


            if has_toggled:
                bpy.ops.object.mode_set(mode='EDIT')  

            context.view_layer.objects.active = active_object
        return {'FINISHED'}


class UnwrapInPlace(bpy.types.Operator):
    bl_idname = "uv.keyops_unwrap_in_place"
    bl_label = "KeyOps: Unwrap in Place"
    bl_description = "Unwrap in Place"
    bl_options = {'REGISTER', 'UNDO'}

    selected_only: bpy.props.BoolProperty(name="Selected Only", default=False, description="Selected Only") # type: ignore
    ignore_pin: bpy.props.BoolProperty(name="Ignore Pin", default=True, description="Ignore Pin") # type: ignore
    select_islands: bpy.props.BoolProperty(name="Select Islands (Slow)", default=False, description="Select Islands") # type: ignore
    uv_unwrap_method: bpy.props.EnumProperty(name="Method", items=(('ANGLE_BASED', "Angle Based", "Angle Based"), ('CONFORMAL', "Conformal", "Conformal")), default='CONFORMAL', description="UV Unwrap Method") # type: ignore
    pack_uv_islands: bpy.props.BoolProperty(name="Pack UV Islands", default=True, description="Pack UV Islands") # type: ignore
    margin: bpy.props.FloatProperty(name="Margin", default=0.001, description="Margin") # type: ignore
    rotate: bpy.props.BoolProperty(name="Rotate", default=True, description="Rotate") # type: ignore
    rotation_method: bpy.props.EnumProperty(name="Rotation Method", items=(('ANY', "Any", "Any"), ('CARDINAL', "Cardinal", "Cardinal"), ('AXIS_ALIGNED', "Axis Aligned", "Axis Aligned")), default='CARDINAL', description="Rotation Method") # type: ignore
    #apply_modifier: bpy.props.BoolProperty(name="(Debug) No Apply", default=True, description="Apply Modifier") # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'
    
    def draw (self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "selected_only")
        layout.prop(self, "ignore_pin")
        layout.prop(self, "uv_unwrap_method")
        layout.label(text="Pack Islands:")
        layout.prop(self, "pack_uv_islands")
        if self.pack_uv_islands:
            layout.prop(self, "margin")
            layout.prop(self, "rotate")
            layout.prop(self, "rotation_method")
            #layout.prop(self, "apply_modifier")

    def execute(self, context):
        visibility_modifier_dict_list = {}

        def modifier_toggle_visability_based2(): 
            active_object_name = bpy.context.view_layer.objects.active.name

            if active_object_name not in visibility_modifier_dict_list:
                visibility_modifier_dict_list[active_object_name] = []

            visibility_modifier_list = visibility_modifier_dict_list[active_object_name]

            if len(visibility_modifier_list) <= 0:
                ml_act_ob = bpy.context.view_layer.objects.active
                for mod in ml_act_ob.modifiers:
                    if mod.show_viewport:
                        visibility_modifier_list.append(mod)
                        mod.show_viewport = False
            else:
                ml_act_ob = bpy.context.view_layer.objects.active
                hidden_modifiers = []
                for mod in ml_act_ob.modifiers:
                    if mod in visibility_modifier_list:
                        mod.show_viewport = True
                        hidden_modifiers.append(mod)
                visibility_modifier_list = [mod for mod in visibility_modifier_list if mod not in hidden_modifiers]
                visibility_modifier_dict_list[active_object_name] = visibility_modifier_list

        #import time
        #total_time = time.time()
        
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                if obj.data.total_vert_sel > 0:
                    bpy.context.view_layer.objects.active = obj
                    modifier_toggle_visability_based2()

        #create_unwrap_in_place_node_group_time = time.time()
        if "Unwrap In Place Tool" not in bpy.data.node_groups:
            from ..resources.geometry_nodes_scripits import unwrap_in_place_tool_node_group
            unwrap_in_place_tool_node_group()
        #print("Create Unwrap In Place Node Group Time: ", time.time() - create_unwrap_in_place_node_group_time)

        #start_op_time = time.time()
    
        if len([obj for obj in bpy.context.selected_objects if obj.type == 'MESH' and obj.data.total_vert_sel > 0]) == 0:
            self.report({'WARNING'}, "Nothing is selected")
            return {'FINISHED'}
        
        #print("Start Operator Time: ", time.time() - start_op_time)
        #cheack_time = time.time()
        has_synced = False
        angle_based = False

        if self.uv_unwrap_method == 'ANGLE_BASED':
            angle_based = True
        #print("Check Time: ", time.time() - cheack_time)
        
        bpy.data.node_groups["Unwrap In Place Tool"].is_mode_edit = True

        selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH' and obj.data.total_vert_sel > 0]
        
        #pre_prep_selection_time = time.time()

        if not self.selected_only:
            #replace with geomtry nodes, way faster! can save at least 10% of the time
            if self.select_islands:
                bpy.ops.mesh.select_linked()
        else:
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
            if context.tool_settings.use_uv_select_sync == False:
                bpy.ops.uv.select_split()
            bpy.ops.transform.translate(value=(0.00311425, -0.00103808, 0), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', mirror=False, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False, snap_elements={'INCREMENT'}, use_snap_project=False, snap_target='CLOSEST', use_snap_self=True, use_snap_edit=True, use_snap_nonedit=True, use_snap_selectable=False)
            bpy.ops.uv.seams_from_islands()
        
        if context.tool_settings.use_uv_select_sync == False:
            for obj in selected_objects:
                if obj.data.total_vert_sel > 0:
                    context.view_layer.objects.active = obj
                    obj.data.attributes.new(name='Currently_Visiable_Faces', type='BOOLEAN', domain='FACE')
                    obj.data.attributes.active = obj.data.attributes.get('Currently_Visiable_Faces')
                    obj.data.update()
                    bpy.ops.mesh.attribute_set(value_bool=True)
            
            has_synced = True
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
            bpy.ops.uv.hide(unselected=True)

        #print("Prep Selection Time: ", time.time() - pre_prep_selection_time)
        
        #set_seam_atri = time.time()
    
        for obj in selected_objects:
            if obj.data.total_vert_sel > 0:
                me = obj.data
                bm = bmesh.from_edit_mesh(me)

                intial_selection = [face for face in bm.faces if face.select]
                intial_selection_edges = [edge for edge in bm.edges if edge.select]

                for edge in intial_selection_edges:
                    edge.select = False
                    if edge.seam:
                        edge.select = True
        if obj.data.total_vert_sel > 0:
            bmesh.update_edit_mesh(me)

        for obj in selected_objects:
            if obj.data.total_vert_sel > 0:

                context.view_layer.objects.active = obj

                obj.data.attributes.new(name='seam_Unwrap_In_Place', type='BOOLEAN', domain='EDGE')
                obj.data.attributes.active = obj.data.attributes.get('seam_Unwrap_In_Place')
                obj.data.update()
                bpy.ops.mesh.attribute_set(value_bool=True)

        if obj.data.total_vert_sel > 0:
            for face in intial_selection:
                face.select = True
        if obj.data.total_vert_sel > 0:
            bmesh.update_edit_mesh(me)
                
        #print("Set Seam Atri ", time.time() - set_seam_atri)
        
        #get_uvmap_name_time = time.time()
        uv_name_list_and_object = []
        for obj in selected_objects:
            if len(obj.data.uv_layers) == 0:
                obj.data.uv_layers.new(name='UVMap')
            if obj.data.uv_layers.active.name != 'UVMap':
                if len(obj.data.uv_layers) > 0:
                    uv_name_list_and_object.append([obj.data.uv_layers.active.name, obj])
                    obj.data.uv_layers.active.name = 'UVMap'
        #print("Get UVMap Name Time: ", time.time() - get_uvmap_name_time)

        #add_modifier_time = time.time()

        if angle_based:
            bpy.data.node_groups["Unwrap In Place Tool"].nodes["Switch"].inputs[0].default_value = True
        else:
            bpy.data.node_groups["Unwrap In Place Tool"].nodes["Switch"].inputs[0].default_value = False

        if self.ignore_pin == False:
            for obj in selected_objects:
                if obj.data.total_vert_sel > 0:
                    me = obj.data
                    bm = bmesh.from_edit_mesh(me)
                    uv = bm.loops.layers.uv.verify()

                    for f in bm.faces:
                        for l in f.loops:
                            if l[uv].pin_uv:
                                f.select = False 
                    bmesh.update_edit_mesh(me)
       
        context_override = context.copy()
        context_override["area"].type = 'VIEW_3D'
        bpy.ops.geometry.execute_node_group(name="Unwrap In Place Tool")
        bpy.context.area.ui_type = 'UV'
        #("Unwrap Time ", time.time() - add_modifier_time)

        #restore_uvmap_name_time = time.time()
        for uv_name in uv_name_list_and_object:
            uv_name[1].data.uv_layers.active.name = uv_name[0]
        #print("Restore UVMap Name Time: ", time.time() - restore_uvmap_name_time)

        #edit_mode_time = time.time()
        bpy.ops.uv.average_islands_scale(scale_uv=True, shear=False)
        if self.pack_uv_islands:
            bpy.ops.uv.pack_islands(udim_source='ORIGINAL_AABB', margin=self.margin, shape_method='AABB', rotate_method= self.rotation_method, rotate=self.rotate)
        if has_synced:
            bpy.context.scene.tool_settings.use_uv_select_sync = False
        #print("Edit Mode Time: ", time.time() - edit_mode_time)

        #restore_selection_time = time.time()
        if has_synced:
            for obj in selected_objects:
                if obj.data.attributes.get('Currently_Visiable_Faces'):
                    context.view_layer.objects.active = obj
                    obj.data.attributes.active = obj.data.attributes.get('Currently_Visiable_Faces')
                    bpy.ops.mesh.select_by_attribute()
                    obj.data.attributes.remove(obj.data.attributes.get('Currently_Visiable_Faces'))
            #print("Restore Selection Time: ", time.time() - restore_selection_time)
        
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                if obj.data.total_vert_sel > 0:
                    bpy.context.view_layer.objects.active = obj
                    modifier_toggle_visability_based2()

        bpy.data.node_groups["Unwrap In Place Tool"].is_mode_edit = False
        #("Total Time: ", time.time() - total_time)
        return {'FINISHED'}


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
          
def disable_auto_smooth(obj):
    for m in obj.modifiers:
        if "Auto Smooth" in m.name or "Smooth by Angle" in m.name or "!!Auto Smooth" in m.name:
            if m.show_viewport:
                obj.modifiers[m.name].show_viewport = False

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
                me, bm = obj.data, bmesh.from_edit_mesh(obj.data)
                for face in bm.faces:
                    if not face.smooth:
                        face.smooth = True

                bmesh.update_edit_mesh(me, loop_triangles=False)
                if bpy.app.version < (4, 1, 0):
                    obj.data.auto_smooth_angle = 3.141590118408203
                    obj.data.use_auto_smooth = True
                else:
                    disable_auto_smooth(obj)
                                    
        elif bpy.context.mode == 'OBJECT':
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    if bpy.app.version > (4, 1, 0):
                        bpy.ops.object.shade_smooth(use_auto_smooth=True, auto_smooth_angle=3.14159, ignore_sharp=False)
                    else:
                        disable_auto_smooth(obj)
        return {'FINISHED'}

class OrientIslandToEdge(bpy.types.Operator):
    bl_description = "Orient Island to Edge"
    bl_idname = "keyops.orient_island_to_edge"
    bl_label = "Orient Island to Edge"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if bpy.context.scene.tool_settings.use_uv_select_sync:
            edge_mode = False
            if bpy.context.tool_settings.mesh_select_mode[1]:
                edge_mode = True
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
            bpy.ops.keyops.smart_uv_sync()
            bpy.ops.uv.select_more()
            bpy.ops.uv.select_less()
            bpy.ops.uv.align_rotation(method='EDGE')
            bpy.ops.keyops.smart_uv_sync()
            if edge_mode:
                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')
        else:
            bpy.ops.uv.align_rotation(method='EDGE')
        return {'FINISHED'}
    
class RemoveSeam(bpy.types.Operator):
    bl_idname = "keyops.remove_seam"
    bl_label = "KeyOps: Remove Seam"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'
    
    def execute(self, context):
        bpy.ops.mesh.mark_seam(clear=True)
        bpy.ops.mesh.mark_sharp(clear=True)
        return {'FINISHED'}
    
class RemoveAllPins(bpy.types.Operator):
    bl_idname = "uv.remove_all_pins"
    bl_label = "KeyOps: Clear All Pins"
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'
    
    def execute(self, context):
        for ob in context.objects_in_mode_unique_data:
            me = ob.data
            bm = bmesh.from_edit_mesh(me)
            uv = bm.loops.layers.uv.verify()

            for f in bm.faces:
                for l in f.loops:
                    l[uv].pin_uv = False
            bmesh.update_edit_mesh(me)
        return {'FINISHED'}
    
class UnwrapSelected(bpy.types.Operator):
    bl_description = "Unwrap Selected"
    bl_idname = "keyops.unwrap_selected"
    bl_label = "Unwrap Selected"
    bl_options = {'REGISTER', 'UNDO'}

    method : bpy.props.EnumProperty(
        items = [
            ('ANGLE_BASED', "Angle Based", "Angle Based"),
            ('CONFORMAL', "Conformal", "Conformal"),], 
        default = 'ANGLE_BASED',
    )# type: ignore
    fill_holes : bpy.props.BoolProperty(name="Fill Holes", default=True) # type: ignore
    corret_aspect : bpy.props.BoolProperty(name="Correct Aspect", default=True) # type: ignore
    use_subsurf_data : bpy.props.BoolProperty(name="Use Subdivision Surface", default=False) # type: ignore

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'
    
    reset_uv_sync = False

    def execute(self, context):
        if context.tool_settings.use_uv_select_sync:
            if bpy.context.scene.smart_uv_sync_enable == False:
                bpy.context.scene.smart_uv_sync_enable = True
                self.reset_uv_sync = True
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
            bpy.ops.keyops.smart_uv_sync()
            bpy.ops.uv.unwrap(method=self.method, margin=0.001, correct_aspect=self.corret_aspect, use_subsurf_data=self.use_subsurf_data, fill_holes=self.fill_holes)
            bpy.ops.keyops.smart_uv_sync()
            if self.reset_uv_sync:
                bpy.context.scene.smart_uv_sync_enable = False
        else:
            bpy.ops.uv.unwrap()

        return {'FINISHED'}
    
class QuickPack(bpy.types.Operator):
    bl_description = "Quick Pack"
    bl_idname = "uv.keyops_quick_pack"
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
    udim_source: bpy.props.EnumProperty(
        items=[
            ("CLOSEST_UDIM", "Closest UDIM", "Closest UDIM"),
            ("ACTIVE_UDIM", "Active UDIM", "Active UDIM"),
            ("ORIGINAL_AABB", "Original AABB", "Original AABB")],#type: ignore
        name="Pack to",description="UDIM Source",default="CLOSEST_UDIM")

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'
    
    
    def execute(self, context):
        bpy.ops.uv.pack_islands(rotate_method=self.rotate_method, margin=self.margin, shape_method='AABB', rotate=self.rotate, scale=self.scale, merge_overlap=self.merge_overlapping, udim_source=self.udim_source)
        return {'FINISHED'}
    
class IsolateUVIsland(bpy.types.Operator):
    bl_description = "Isolate UV Island"
    bl_idname = "uv.keyops_isolate_uv_island"
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
            bpy.ops.uv.select_linked()
            bpy.ops.keyops.smart_uv_sync()
            bpy.context.scene.tool_settings.use_uv_select_sync = False

        return {'FINISHED'}

class SelectSimilarUVIsland(bpy.types.Operator):
    bl_description = "Select Similar UV Island"
    bl_idname = "uv.keyops_select_similar_uv_island"
    bl_label = "Select Similar UV Island"
    bl_options = {'REGISTER', 'UNDO'}

    treshold: bpy.props.FloatProperty(name="Treshold",description="Treshold",default=0.001, min=0.0, max=1.0, precision=3) # type: ignore

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH' and not context.tool_settings.use_uv_select_sync
    
    def execute(self, context):
        has_synced = False
        # if context.tool_settings.use_uv_select_sync:
        #     bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')

        #     bpy.context.scene.tool_settings.use_uv_select_sync = False
        #     bpy.ops.uv.select_all(action='SELECT')

        #     bpy.ops.mesh.select_all(action='SELECT')
        #     bpy.ops.uv.select_mode(type='ISLAND')
        #     has_synced = True


        bpy.ops.uv.select_mode(type='FACE')
        bpy.ops.uv.select_mode(type='ISLAND')
        bpy.ops.uv.select_similar(type='AREA_3D', threshold=self.treshold)

        if has_synced:
            bpy.ops.keyops.smart_uv_sync()

        return {'FINISHED'}

class UVEDITORSMARTUVSYNC_PT_Panel(bpy.types.Panel):
    prefs = get_keyops_prefs()
    category_name = prefs.uv_tools_panel_name
    bl_label = "Key Ops: Toolkit - UV Tools"
    bl_idname = "UVEDITORSMARTUVSYNC_PT_Panel"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = category_name

    @classmethod
    def poll(cls, context):
        return False
        # return context.mode == 'EDIT_MESH' or context.mode == 'OBJECT'
    
    def draw(self, context):
        layout = self.layout
        row = layout.split(factor=0.65, align=True)

        row.scale_y = 1.5
        row.operator("keyops.smart_uv_sync", text="Smart UV Sync", icon='UV_SYNC_SELECT')
        row.prop(context.scene, "smart_uv_sync_enable", toggle=True, text="Enable")

        #uv islands  
        row = layout.row()
        row.label(text="UV Islands")
        row = layout.row(align=True)
        row.operator("uv.keyops_isolate_uv_island", text="Isolate UV")
        row.operator("uv.reveal", text="Unhide UV")
        row = layout.row()
        row.operator("keyops.sharp_from_uv_islands", text="Sharp from UV Islands", icon="MOD_EDGESPLIT")
        row = layout.row()
        row.operator("uv.seams_from_islands", text="Seams from UV Islands")
        row = layout.row()
        row.operator("uv.average_islands_scale", text="Average Island Scale")

        #unwrap
        def draw_unwrap(self, context):
            row = layout.separator()
            row = layout.row()
            row.label(text="Enable Live")
            row = layout.row(align=True)
            row.prop(context.scene.tool_settings, "use_edge_path_live_unwrap", text="Unwrap")
            row.prop(context.space_data.uv_editor, "use_live_unwrap", text="Live Pin")
            row = layout.row()
            row.label(text="Unwrap")
            row = layout.row(align=True)
            row.operator("uv.unwrap", icon='UV_FACESEL', text="and Pack")
            row.operator("keyops.unwrap_selected", icon='UV_VERTEXSEL', text="Selected")
            row = layout.row()
            row.operator("uv.keyops_unwrap_in_place", text="Unwrap Island in Place", icon='STICKY_UVS_VERT')
        draw_unwrap(self, context)

        #seams
        row = layout.separator()
        row = layout.row()
        row.label(text="Seams")
        row = layout.row(align=True)
        row.operator("uv.mark_seam", icon='EDGESEL', text="Mark").clear = False
        row.operator("uv.mark_seam", icon='X', text="Clear").clear = True
        row = layout.row(align=True)
        if bpy.app.version >= (4, 1, 0):
            icon_uv_cut = 'AREA_SWAP'
            icon_stitch = 'AREA_JOIN'
        else:
            icon_uv_cut = 'UV_EDGESEL'
            icon_stitch = 'UV_FACESEL'
        row.operator("uv.keyops_uv_cut", icon=icon_uv_cut, text="UV Cut")
        row.operator_context = 'EXEC_DEFAULT'
        row.operator("uv.stitch", icon=icon_stitch, text="UV Stitch")
        row = layout.row()
        row.operator_context = 'INVOKE_DEFAULT'
        row.operator("keyops.seam_by_angle", icon='MOD_EDGESPLIT', text="Seam by Angle")

        #pack
        row = layout.separator()
        row = layout.row()
        row.label(text="Pack UV Islands")
        row = layout.row(align=True)
        row.operator("uv.keyops_quick_pack", text="Quick Pack", icon='CON_SAMEVOL')
        row.operator("uv.pack_islands",  text="Exact Pack", icon='MOD_BUILD')

        #set
        row = layout.separator()
        row = layout.row()
        row.label(text="Set")
        row = layout.row(align=True)
        row.operator("uv.pin", icon='PINNED', text="Pin").clear = False
        row.operator("uv.pin", icon='UNPINNED', text="Unpin").clear = True
        row = layout.row(align=True)
        if bpy.app.version >= (4, 0, 0):
            row.operator("uv.pin", text="Invert Pin").invert = True
        row.operator("uv.remove_all_pins", text="Clear All Pins")
        row = layout.row(align=True)
        
        #align
        row = layout.separator()
        row = layout.row()
        row.label(text="Align")
        row = layout.row(align=True)
        row.operator("keyops.orient_island_to_edge", text="Orient to Edge")
        row.operator("uv.align_rotation", text="Align Islands"). method='AUTO'

        #select
        row = layout.separator()
        row = layout.row()
        row.label(text="Select")
        row = layout.row(align=True)
        row.operator("uv.select_more", text="More", icon='ADD')
        row.operator("uv.select_less", text="Less", icon='REMOVE')
        row = layout.row(align=True)
        row.operator("uv.keyops_select_similar_uv_island", text="Similar")
        row.operator("uv.select_overlap", text="Overlap")
        row = layout.row(align=True)
        row.operator("uv.select_linked", text="Island")
        row.operator("uv.select_pinned", text="Pinned")

        #transform
        row = layout.separator()
        row = layout.row()
        row.label(text="Transform")
        row = layout.row(align=True)
        row.operator_context = 'EXEC_DEFAULT'
        row.operator("transform.mirror", text="Flip X").constraint_axis = (True, False, False)
        row.operator("transform.mirror", text="Flip Y").constraint_axis = (False, True, False)

        #copy paste
        row = layout.separator()
        row = layout.row()
        row.label(text="Copy/Paste UVs")
        row = layout.row(align=True)
        row.operator("uv.copy", text="Copy")
        row.operator("uv.paste", text="Paste")




