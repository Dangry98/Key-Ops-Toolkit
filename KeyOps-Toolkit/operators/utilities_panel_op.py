import bpy
from ..utils.pref_utils import get_keyops_prefs

#fix attribute toggle in edit mode/objet mode

def offset_uv():
    offset_uv = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Offset UV")

    offset_uv.is_modifier = True

    named_attribute = offset_uv.nodes.new("GeometryNodeInputNamedAttribute")
    named_attribute.name = "Named Attribute"
    named_attribute.data_type = 'FLOAT_VECTOR'
    named_attribute.inputs[0].default_value = "UVMap"

    vector_math = offset_uv.nodes.new("ShaderNodeVectorMath")
    vector_math.name = "Vector Math"
    vector_math.operation = 'ADD'
    vector_math.inputs[2].default_value = (0.0, 0.0, 0.0)
    vector_math.inputs[3].default_value = 1.0

    combine_xyz = offset_uv.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz.name = "Combine XYZ"
    combine_xyz.inputs[2].default_value = 0.0

    store_named_attribute = offset_uv.nodes.new("GeometryNodeStoreNamedAttribute")
    store_named_attribute.name = "Store Named Attribute"
    store_named_attribute.data_type = 'FLOAT2'
    store_named_attribute.domain = 'CORNER'
    store_named_attribute.inputs[2].default_value = "UVMap"
    store_named_attribute.inputs[4].default_value = 0.0
    store_named_attribute.inputs[5].default_value = (0.0, 0.0, 0.0, 0.0)
    store_named_attribute.inputs[6].default_value = False
    store_named_attribute.inputs[7].default_value = 0
    store_named_attribute.inputs[8].default_value = (0.0, 0.0, 0.0)

    group_output = offset_uv.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True
    geometry_socket = offset_uv.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'



    group_input = offset_uv.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"
    geometry_socket = offset_uv.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'

    selection_socket = offset_uv.interface.new_socket(name = "Selection", in_out='INPUT', socket_type = 'NodeSocketBool')
    selection_socket.attribute_domain = 'POINT'
    selection_socket.hide_value = True
    selection_socket.default_value = True   

    offset_uv_x_socket = offset_uv.interface.new_socket(name = "Offset UV X", in_out='INPUT', socket_type = 'NodeSocketFloat')
    offset_uv_x_socket.subtype = 'NONE'
    offset_uv_x_socket.default_value = 1.0
    offset_uv_x_socket.min_value = -10000.0
    offset_uv_x_socket.max_value = 10000.0
    offset_uv_x_socket.attribute_domain = 'POINT'

    offset_uv_y_socket = offset_uv.interface.new_socket(name = "Offset UV Y", in_out='INPUT', socket_type = 'NodeSocketFloat')
    offset_uv_y_socket.subtype = 'NONE'
    offset_uv_y_socket.default_value = 0.0
    offset_uv_y_socket.min_value = -10000.0
    offset_uv_y_socket.max_value = 10000.0
    offset_uv_y_socket.attribute_domain = 'POINT'

    named_attribute.location = (-427.7541809082031, -191.61178588867188)
    vector_math.location = (-249.5355224609375, -130.76705932617188)
    combine_xyz.location = (-421.7253112792969, -51.163997650146484)
    store_named_attribute.location = (-71.33470153808594, 71.70158386230469)
    group_output.location = (121.15008544921875, 72.86686706542969)
    group_input.location = (-622.7821655273438, 11.500011444091797)

    named_attribute.width, named_attribute.height = 140.0, 100.0
    vector_math.width, vector_math.height = 140.0, 100.0
    combine_xyz.width, combine_xyz.height = 140.0, 100.0
    store_named_attribute.width, store_named_attribute.height = 140.0, 100.0
    group_output.width, group_output.height = 140.0, 100.0
    group_input.width, group_input.height = 140.0, 100.0

    offset_uv.links.new(store_named_attribute.outputs[0], group_output.inputs[0])
    offset_uv.links.new(group_input.outputs[0], store_named_attribute.inputs[0])
    offset_uv.links.new(named_attribute.outputs[0], vector_math.inputs[0])
    offset_uv.links.new(vector_math.outputs[0], store_named_attribute.inputs[3])
    offset_uv.links.new(group_input.outputs[1], store_named_attribute.inputs[1])
    offset_uv.links.new(combine_xyz.outputs[0], vector_math.inputs[1])
    offset_uv.links.new(group_input.outputs[2], combine_xyz.inputs[0])
    offset_uv.links.new(group_input.outputs[3], combine_xyz.inputs[1])
    return offset_uv

def select_atribute(attribute_name):
    C = bpy.context
    ip_name = attribute_name
    named_attributes = C.object.data.attributes

    set_act = named_attributes.get(ip_name)
    C.object.data.attributes.active = set_act
    set_act_index = C.object.data.attributes.find(ip_name)
    C.object.data.attributes.active_index = set_act_index

def get_scale(obj):
    s = obj.scale
    return (s[0] + s[1] + s[2]) / 3

class UtilitiesPanelOP(bpy.types.Operator):
    bl_description = "Utilities Panel Operator"
    bl_idname = "keyops.utilities_panel_op"
    bl_label = "Utilities Operator"
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.StringProperty() # type: ignore
    
    true_false: bpy.props.BoolProperty(name="True", default=True) # type: ignore
    select_children: bpy.props.BoolProperty(name="Select Children", default=True) # type: ignore    
    select_parent: bpy.props.BoolProperty(name="Select Parent", default=True) # type: ignore
    select_top_parent: bpy.props.BoolProperty(name="Select Top Parent", default=True) # type: ignore
    set_material_index: bpy.props.BoolProperty(name="Set Material Index", default=False) # type: ignore
    join_objects: bpy.props.BoolProperty(name="Join Objects", default=True) # type: ignore
    apply_instances: bpy.props.BoolProperty(name="Apply Instances", default=True) # type: ignore
    scale: bpy.props.FloatProperty(name="Scale", default=5.0) # type: ignore
    mix_factor: bpy.props.FloatProperty(name="Mix Factor", default=1.0, min=0.0, max=1.0) # type: ignore
    set_orgin_to_geometry: bpy.props.BoolProperty(name="Set Origin to Geometry", default=True) # type: ignore
    subdivide: bpy.props.IntProperty(name="Subdivide", default=6, min=0, max=10) # type: ignore

    def draw(self, context):
        layout = self.layout
        if self.type == "offset_uv":
            if context.mode == 'EDIT_MESH':
                layout.prop(self, "true_false")
        if self.type == "Select_Changed":
            layout.prop(self, "select_parent")
            if self.select_parent == True:
                layout.prop(self, "select_top_parent")
                layout.prop(self, "select_children")
        if self.type == "Apply_and_Join":
            layout.prop(self, "set_material_index")   
            layout.prop(self, "join_objects")     
            layout.prop(self, "apply_instances") 
            layout.prop(self, "export_normals")
        if self.type == "set_sphere_normal":
            layout.prop(self, "mix_factor")
            layout.prop(self, "scale")
            layout.prop(self, "subdivide")
            layout.prop(self, "set_orgin_to_geometry")
        if self.type == "set_normal_from_selection":
            layout.prop(self, "mix_factor")
            

    def execute(self, context):
        prefs = get_keyops_prefs()
        if self.type == "offset_uv":
            if bpy.data.node_groups.get("Offset UV") is None:
                offset_uv()
            if bpy.context.object.modifiers.get("Offset UV") is None:
                bpy.context.object.modifiers.new('Offset UV', 'NODES')
                bpy.context.object.modifiers['Offset UV'].node_group = bpy.data.node_groups['Offset UV']
                if bpy.context.mode == 'EDIT_MESH': 
                    bpy.ops.object.geometry_nodes_input_attribute_toggle(input_name="Socket_2", modifier_name="Offset UV")
                    bpy.context.object.modifiers["Offset UV"]["Socket_2_attribute_name"] = "Offset_UV"

            if bpy.context.mode == 'EDIT_MESH':
                named_attributes = bpy.context.object.data.attributes
                attribute_name = "Offset_UV"
                set_act = named_attributes.get(attribute_name)
                if set_act is not None:
                    select_atribute(attribute_name)
                else:
                    mesh = bpy.context.object.data
                    mesh.attributes.new(name="Offset_UV", domain='FACE', type='BOOLEAN')
                    select_atribute(attribute_name)

                bpy.ops.mesh.attribute_set(value_bool=self.true_false)
        if self.type == "set_sphere_normal":
            current_selectded_objects = bpy.context.selected_objects
            if bpy.context.mode == 'EDIT_MESH':
                bpy.ops.object.editmode_toggle()

            if self.set_orgin_to_geometry == True:
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

            for obj in current_selectded_objects:
                bpy.context.view_layer.objects.active = obj
                bpy.ops.view3d.snap_cursor_to_active()
                bpy.ops.keyops.add_mesh(mesh_type='QUADSPHERE', scale_property=self.scale, use_relative_scale=False, sub_amount=self.subdivide)

                bpy.ops.object.shade_smooth()
                bpy.context.object.display_type = 'WIRE'
                sphere_object = bpy.context.active_object

                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.shade_smooth(use_auto_smooth=True)
                bpy.ops.object.modifier_add(type='DATA_TRANSFER')
                data_transfer_modifier = bpy.context.object.modifiers[-1]
                data_transfer_modifier.use_loop_data = True
                data_transfer_modifier.data_types_loops = {'CUSTOM_NORMAL'}
                data_transfer_modifier.mix_factor = self.mix_factor
                data_transfer_modifier.object = sphere_object

        if self.type == "set_normal_from_selection":
            if bpy.context.mode == 'OBJECT':
                bpy.ops.object.editmode_toggle()
            bpy.ops.mesh.duplicate_move(MESH_OT_duplicate={"mode":1}, TRANSFORM_OT_translate={"value":(0, 0, 0), "orient_type":'GLOBAL', "orient_matrix":((0, 0, 0), (0, 0, 0), (0, 0, 0)), "orient_matrix_type":'GLOBAL', "constraint_axis":(False, False, False), "mirror":False, "use_proportional_edit":False, "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "use_proportional_connected":False, "use_proportional_projected":False, "snap":False, "snap_elements":{'INCREMENT'}, "use_snap_project":False, "snap_target":'CLOSEST', "use_snap_self":True, "use_snap_edit":True, "use_snap_nonedit":True, "use_snap_selectable":False, "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0), "gpencil_strokes":False, "cursor_transform":False, "texture_space":False, "remove_on_cancel":False, "use_duplicated_keyframes":False, "view2d_edge_pan":False, "release_confirm":False, "use_accurate":False, "alt_navigation":False, "use_automerge_and_split":False})
            bpy.ops.mesh.separate(type='SELECTED')
            duplicated_object = bpy.context.selected_objects[1]
            duplicated_object.modifiers.clear()
            current_name = duplicated_object.name
            duplicated_object.name = current_name + "_normal_transfer"

            bpy.ops.object.editmode_toggle()

            bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
            bpy.ops.object.shade_smooth(use_auto_smooth=True)
            bpy.ops.object.modifier_add(type='DATA_TRANSFER')
            data_transfer_modifier = bpy.context.object.modifiers[-1]
            data_transfer_modifier.use_loop_data = True
            data_transfer_modifier.data_types_loops = {'CUSTOM_NORMAL'}
            data_transfer_modifier.mix_factor = self.mix_factor
            data_transfer_modifier.object = duplicated_object
            

        if self.type == "set_bevel_segment_amount":
            selected_objects = bpy.context.selected_objects
            for selected_obj in selected_objects:
                if selected_obj.type == 'MESH':
                    modifiers = selected_obj.modifiers
                    num_modifiers = len(modifiers)

                    if bpy.context.scene.bevel_segments_type == 'ALL':
                        for modifier in modifiers: 
                            if modifier.type == 'BEVEL':
                                modifier.segments = bpy.context.scene.bevel_segment_amount

                    elif bpy.context.scene.bevel_segments_type == 'TOP':
                        if num_modifiers > 0 and modifiers[0].type == 'BEVEL':
                            modifiers[0].segments = bpy.context.scene.bevel_segment_amount

                    elif bpy.context.scene.bevel_segments_type == 'BOTTOM':
                        if num_modifiers > 0 and modifiers[-1].type == 'BEVEL':
                            modifiers[-1].segments = bpy.context.scene.bevel_segment_amount

        if self.type == "bevel_segment_amount_by_%":
            selected_objects = bpy.context.selected_objects

            for selected_obj in selected_objects:
                if selected_obj.type == 'MESH':
                    modifiers = selected_obj.modifiers
                    num_modifiers = len(modifiers)

                    if bpy.context.scene.bevel_segments_type == 'ALL':
                        for modifier in selected_obj.modifiers:  
                            if modifier.type == 'BEVEL':
                                segment_amount = modifier.segments + (modifier.segments * bpy.context.scene.bevel_segment_by_percent / 100)
                                modifier.segments = int(segment_amount)
                    if bpy.context.scene.bevel_segments_type == 'TOP':
                        if num_modifiers > 0 and modifiers[0].type == 'BEVEL':
                            segment_amount = modifiers[0].segments + (modifiers[0].segments * bpy.context.scene.bevel_segment_by_percent / 100)
                            modifiers[0].segments = int(segment_amount)
                    if bpy.context.scene.bevel_segments_type == 'BOTTOM':
                        if num_modifiers > 0 and modifiers[-1].type == 'BEVEL':
                            segment_amount = modifiers[-1].segments + (modifiers[-1].segments * bpy.context.scene.bevel_segment_by_percent / 100)
                            modifiers[-1].segments = int(segment_amount)
        if self.type == "hide_bevels_by_offset":
            selected_objects = bpy.context.selected_objects

            for selected_obj in selected_objects:
                if selected_obj.type == 'MESH':
                    modifiers = selected_obj.modifiers
                    num_modifiers = len(modifiers)

                    for modifier in selected_obj.modifiers:
                        if modifier.type == 'BEVEL':
                            if bpy.context.scene.compensate_for_scale == True:
                                bevel_offset = bpy.context.scene.bevel_offset / get_scale(selected_obj)
                            else:
                                bevel_offset = bpy.context.scene.bevel_offset
                            if bpy.context.scene.bevel_segments_type == 'ALL':
                                if modifier.width < bevel_offset:
                                    modifier.show_viewport = False
                            if bpy.context.scene.bevel_segments_type == 'TOP':
                                if num_modifiers > 0 and modifiers[0].type == 'BEVEL':
                                    if modifiers[0].width < bevel_offset:
                                        modifiers[0].show_viewport = False
                            if bpy.context.scene.bevel_segments_type == 'BOTTOM':
                                if num_modifiers > 0 and modifiers[-1].type == 'BEVEL':
                                    if modifiers[-1].width < bevel_offset:
                                        modifiers[-1].show_viewport = False
                                                                             
        if self.type == "Marke_Changed":
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    bpy.context.object.color = (1, 0, 0, 1)
                    self.report({'INFO'}, "Marked Changed")
                else:
                    self.report({'WARNING'}, "Only Works on Meshes")
        
        #Make a list with all emptyes that has changde? Tag and untag button? Select button?
        #auto tag with handlers?
            
        if self.type == "Clear_Changed":
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    bpy.context.object.color = (1, 1, 1, 1)
            
        if self.type == "Clear_All":
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    bpy.context.object.color = (1, 1, 1, 1)
            self.report({'WARNING'}, "Cleared All")

        if self.type == "Preview_Change_Objects":
            bpy.context.space_data.shading.type = 'SOLID'
            if bpy.context.space_data.shading.color_type == 'OBJECT':
                bpy.context.space_data.shading.color_type = 'MATERIAL'
            else:
                bpy.context.space_data.shading.color_type = 'OBJECT'
            pass

        if self.type == "Select_Changed":
            #import time

            #perf_time = time.time()
            if bpy.context.mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='OBJECT')
            selected_objects = []

            bpy.ops.object.select_all(action='DESELECT')

            selected_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.color[:4] == (1, 0, 0, 1)]

            if self.select_parent == True:
            
                for obj in selected_objects:
                    bpy.context.view_layer.objects.active = obj
                    if self.select_children == True:
                        bpy.ops.object.select_grouped(extend=True, type='PARENT')
                        bpy.ops.object.select_grouped(extend=True, type='CHILDREN_RECURSIVE')
                    else:
                        bpy.ops.object.select_grouped(extend=True, type='PARENT')
                        obj.select_set(False)
                    if self.select_top_parent == True:
                        top_parent = obj
                        while top_parent.parent:
                            top_parent.parent.select_set(False)
                            top_parent = top_parent.parent

                        if self.select_children == True:
                            bpy.context.view_layer.objects.active = top_parent
                            top_parent.select_set(True)
                            bpy.ops.object.select_grouped(extend=True, type='CHILDREN_RECURSIVE')
                        else:
                            top_parent.select_set(True)
            else:
                for obj in selected_objects:
                    obj.select_set(True)
        if self.type == "Apply_and_Join":
            import time
            operation_time = time.time()

            if self.apply_instances == True:
                bpy.ops.object.duplicates_make_real()
            
            selected_objects = bpy.context.selected_objects
            selected_objects = [obj for obj in selected_objects if (obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'INSTANCE') and obj.display_type != 'WIRE']
            if bpy.context.mode == 'EDIT_MESH':                                                             
                bpy.ops.object.mode_set(mode='OBJECT')

            bpy.ops.object.select_all(action='DESELECT')

            for selected_obj in selected_objects:
                selected_obj.select_set(True)

            bpy.context.view_layer.objects.active = selected_objects[0]

            bpy.ops.object.make_single_user(object=True, obdata=True, material=False, animation=False, obdata_animation=False)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            bpy.ops.object.convert(target='MESH')

            for selected_obj in selected_objects:
                selected_obj.select_set(True)
                bpy.context.view_layer.objects.active = selected_obj
                bpy.ops.mesh.customdata_custom_splitnormals_add()

            if self.join_objects == True:
                bpy.ops.object.join()
                bpy.ops.object.modifier_add(type='TRIANGULATE')
                bpy.context.object.modifiers["Triangulate"].keep_custom_normals = True
            else:
                for selected_obj in selected_objects:
                    bpy.context.view_layer.objects.active = selected_obj
                    bpy.ops.object.modifier_add(type='TRIANGULATE')
                    bpy.context.object.modifiers["Triangulate"].keep_custom_normals = True
            
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            bpy.context.object.data.use_auto_smooth = True

            if self.set_material_index == True and prefs.enable_material_index:
                bpy.ops.keyops.material_index(type="Make_Material_Index")

            operation_time = time.time() - operation_time
            print(f"Total Operation Time: {operation_time:.4f} seconds")
     
            #perf_time = time.time() - perf_time
            #print(f"Total Selection Time: {perf_time:.4f} seconds")
            #can crash sometimes, dont know why, debug
            #needs a way to make sure to presver normals, maybe add custom split normals data if it does not have it?, no does not work
        return {'FINISHED'}
    
    def register():
        bpy.utils.register_class(UtilitiesPanel)
    def unregister():
        bpy.utils.unregister_class(UtilitiesPanel)



class UtilitiesPanel(bpy.types.Panel):
    bl_description = "Utilities Panel"
    bl_label = "Utilities"
    bl_idname = "KEYOPS_PT_utilities_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ToolKit'

    @classmethod
    def poll(cls, context):
        return get_keyops_prefs().enable_utilities_panel_op
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("keyops.unique_collection_duplicate", text="Unique Collection Duplicate")
        row = layout.row()
        row.operator("keyops.utilities_panel_op", text="Join and Preserve Normals").type = "Apply_and_Join"

        layout.separator()

        row = layout.row()
        if bpy.context.mode == 'EDIT_MESH':
            row.operator("keyops.utilities_panel_op", text="Offset Selected UV", icon= "MOD_UVPROJECT").type = "offset_uv"   
        else:   
            row.operator("keyops.utilities_panel_op", text="Offset Object UV", icon= "MOD_UVPROJECT").type = "offset_uv"
        
        row = layout.row()
        row.label(text="Set Normals:")
        row = layout.row(align=True)
        row.operator("keyops.utilities_panel_op", text="Sphere", icon= "META_BALL").type = "set_sphere_normal"
        row.operator("keyops.utilities_panel_op", text="Selection", icon= "UV_FACESEL").type = "set_normal_from_selection"

        layout.separator()
        row = layout.row()
        row.prop(context.scene, "bevel_segments_type", text="Set")
        row = layout.row()
        row.operator("keyops.utilities_panel_op", text="Set Value", icon= "MOD_BEVEL").type = "set_bevel_segment_amount" 
        row.operator("keyops.utilities_panel_op", text="Set by %", icon= "MOD_BEVEL").type = "bevel_segment_amount_by_%"
        row = layout.row()
        row.prop(context.scene, "bevel_segment_amount", text="")
        row.prop(context.scene, "bevel_segment_by_percent", text="")

        row = layout.row()
        row.operator("keyops.utilities_panel_op", text="Hide by Offset", icon= "MOD_BEVEL").type = "hide_bevels_by_offset"
        row = layout.row()
        row.prop(context.scene, "compensate_for_scale", text="Scale")
        row.prop(context.scene, "bevel_offset", text="")

        layout.separator()
        row = layout.row()
        row.label(text="Changde Meshes:")
        row = layout.row(align=True)
        row.operator("keyops.utilities_panel_op", text="Marke", icon="SEQUENCE_COLOR_01").type = "Marke_Changed"
        row.operator("keyops.utilities_panel_op", text="Clear", icon="SEQUENCE_COLOR_04").type = "Clear_Changed"
        row = layout.row(align=True)
        row.operator("keyops.utilities_panel_op", text="Preview", icon="HIDE_OFF").type = "Preview_Change_Objects"
        row.operator("keyops.utilities_panel_op", text="Clear All", icon="X" ).type = "Clear_All"
        row = layout.row()
        row.operator("keyops.utilities_panel_op", text="Select All Changed", icon="RESTRICT_SELECT_OFF").type = "Select_Changed"

    def register():
        bpy.types.Scene.bevel_segment_amount = bpy.props.IntProperty(name="Bevel Segment Amount", default=2, min=1, max=128)
        bpy.types.Scene.bevel_segment_by_percent = bpy.props.IntProperty(name="Bevel Segment By %", default=-50, min=-100, max=100, subtype='FACTOR')
        bpy.types.Scene.bevel_offset = bpy.props.FloatProperty(name="Bevel Offset", default=0.1, min=-0.0, max=10.0)
        bpy.types.Scene.compensate_for_scale = bpy.props.BoolProperty(name="Compensate for Scale", default=True, description="Compensate for Scale")
        bpy.types.Scene.bevel_segments_type = bpy.props.EnumProperty(name="bevel_segments_type", items=[('ALL', 'All Bevelse', 'All Bevelse'), ('TOP', 'First Bevel', 'First Bevel'), ('BOTTOM', 'Last Bevel', 'Last Bevel')], default='ALL', description="Bevel Segments Type")
    def unregister():
        del bpy.types.Scene.bevel_segment_amount
        del bpy.types.Scene.bevel_segment_by_percent
        del bpy.types.Scene.bevel_offset
        del bpy.types.Scene.compensate_for_scale
        del bpy.types.Scene.bevel_segments_type
