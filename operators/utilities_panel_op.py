import bpy
from ..utils.pref_utils import get_keyops_prefs
import tempfile

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
    try_deduplicate_materials: bpy.props.BoolProperty(name="Try Deduplicate Materials", default=True) # type: ignore
    triangulate: bpy.props.BoolProperty(name="Triangulate", default=True) # type: ignore
    rename_uv_layer: bpy.props.BoolProperty(name="Rename UV Layer 0 To UVMap", default=True) # type: ignore
    join_children: bpy.props.BoolProperty(name="Join Children", default=True) # type: ignore

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
            layout.prop(self, "join_children")   
            layout.prop(self, "apply_instances") 
            layout.prop(self, "rename_uv_layer")
            layout.prop(self, "export_normals")
            layout.prop(self, "triangulate")
        if self.type == "set_sphere_normal":
            layout.prop(self, "mix_factor")
            layout.prop(self, "scale")
            layout.prop(self, "subdivide")
            layout.prop(self, "set_orgin_to_geometry")
        if self.type == "set_normal_from_selection":
            layout.prop(self, "mix_factor")
        if self.type == "Quick_Apply_All_Modifiers":
            layout.label(text="Can have unexpected results, save backup!", icon='ERROR')
            layout.prop(self, "try_deduplicate_materials")
            

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
            if self.join_children:
                bpy.ops.object.select_grouped(extend=True, type='CHILDREN_RECURSIVE')

            selected_objects = bpy.context.selected_objects

            cursor_loc = context.scene.cursor.location
            pos2 = (cursor_loc[0], cursor_loc[1], cursor_loc[2])
            bpy.ops.view3d.snap_cursor_to_active()

            if self.apply_instances == True:
                bpy.ops.object.duplicates_make_real()

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

            if self.rename_uv_layer == True:
                for selected_obj in selected_objects:
                    selected_obj.data.uv_layers[0].name = "UVMap"

            for selected_obj in selected_objects:
                selected_obj.select_set(True)
                bpy.context.view_layer.objects.active = selected_obj
                bpy.ops.mesh.customdata_custom_splitnormals_add()

            if self.join_objects == True:
                bpy.ops.object.join()
                if self.triangulate == True:
                    bpy.ops.object.modifier_add(type='TRIANGULATE')
                    bpy.context.object.modifiers["Triangulate"].keep_custom_normals = True
            else:
                if self.triangulate == True:
                    for selected_obj in selected_objects:
                        bpy.context.view_layer.objects.active = selected_obj
                        bpy.ops.object.modifier_add(type='TRIANGULATE')
                        bpy.context.object.modifiers["Triangulate"].keep_custom_normals = True
            
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            if bpy.app.version <= (4, 0, 0):
                bpy.context.object.data.use_auto_smooth = True

            if self.set_material_index == True and prefs.enable_material_index:
                bpy.ops.keyops.material_index(type="Make_Material_Index")
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
            context.scene.cursor.location = (pos2[0], pos2[1], pos2[2])

            #perf_time = time.time() - perf_time
            #print(f"Total Selection Time: {perf_time:.4f} seconds")
            #can crash sometimes, dont know why, debug
            #needs a way to make sure to presver normals, maybe add custom split normals data if it does not have it?, no does not work

        if self.type == "Quick_Apply_All_Modifiers":
            #nice when modifiers are very slow to apply, but the final result is not that high-poly - test decmiation modifier 32 seconds to 1.5 seconds
            selected_objects = bpy.context.selected_objects
        
            was_edit_mode = False
            if bpy.context.mode == 'EDIT_MESH':
                was_edit_mode = True
                bpy.ops.object.mode_set(mode='OBJECT')

            temp_file_path = tempfile.gettempdir()
            file_name = "temp_file.obj"
            temp_file_path = temp_file_path + "\\" + file_name
            bpy.ops.wm.obj_export(filepath=temp_file_path, export_selected_objects=True, export_uv=True, export_materials=True)
            bpy.ops.object.delete(use_global=False, confirm=False)  

            #import back the objects with obj importer
            output_directory = temp_file_path
            bpy.ops.wm.obj_import(filepath=temp_file_path, directory=output_directory)
            #obj 12.5 seconds - should be the fastest, except for .ply perhaps, but that one is unreliable in my experience
            if was_edit_mode:
                bpy.ops.object.mode_set(mode='EDIT')

            #move this later to a utility function, also should only operate on the selected objects
            #from https://blender.stackexchange.com/questions/75790/how-to-merge-around-300-duplicate-materials/195474#195474
            def replace_material(bad_mat, good_mat):
                bad_mat.user_remap(good_mat)
                bpy.data.materials.remove(bad_mat)              
                
            def get_duplicate_materials(og_material):
                get_selected_objects = None
                for obj in bpy.context.selected_objects:
                    if obj.type == 'MESH':
                        get_selected_objects = bpy.context.selected_objects
                        break
                get_all_selected_materials = [material for obj in get_selected_objects for material in obj.data.materials]

                common_name = og_material.name
                
                if common_name[-3:].isnumeric():
                    common_name = common_name[:-4]
                
                duplicate_materials = []
                
                for material in get_all_selected_materials:
                    if material is not og_material:
                        name = material.name
                        if name[-3:].isnumeric() and name[-4] == ".":
                            name = name[:-4]
                        
                        if name == common_name:
                            duplicate_materials.append(material)
                
                text = "{} duplicate materials found"
                print(text.format(len(duplicate_materials)))
                
                return duplicate_materials

            def remove_all_duplicate_materials():
                i = 0
                while i < len(bpy.data.materials):
                    
                    og_material = bpy.data.materials[i]
                    
                    print("og material: " + og_material.name)
                    
                    # get duplicate materials
                    duplicate_materials = get_duplicate_materials(og_material)
                    
                    # replace all duplicates
                    for duplicate_material in duplicate_materials:
                        replace_material(duplicate_material, og_material)
                    
                    # adjust name to no trailing numbers
                    if og_material.name[-3:].isnumeric() and og_material.name[-4] == ".":
                        og_material.name = og_material.name[:-4]
                        
                    i = i+1
            if self.try_deduplicate_materials:
                remove_all_duplicate_materials()  
            self.report({'WARNING'}, "This operation can cause unexpected results, please save backup before using")


        if self.type == "toggle_high_low":
            if bpy.context.scene.collection.children.get("high") is not None and bpy.context.scene.collection.children.get("low") is not None:
                high_index = bpy.context.scene.collection.children.find("high") + 1
                low_index = bpy.context.scene.collection.children.find("low") + 1
                active_index = bpy.context.scene.collection.children.find(bpy.context.view_layer.active_layer_collection.name) + 1
                if active_index == high_index:
                    bpy.ops.object.hide_collection(collection_index=low_index, extend=False)
                else:
                    bpy.ops.object.hide_collection(collection_index=high_index, extend=False)
            else:
                self.report({'WARNING'}, "high or low collections not found")
        if self.type == "high":
            if bpy.context.scene.collection.children.get("high") is None:
                if len(bpy.context.scene.collection.children) == 1 and not bpy.context.scene.collection.children[0].name == "low":
                    bpy.context.scene.collection.children[0].name = "high"
                else:
                    bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name="high")
            else:
                get_index_of_high = bpy.context.scene.collection.children.find("high") + 1
                bpy.ops.object.move_to_collection(collection_index=get_index_of_high)
        if self.type == "low":
            if bpy.context.scene.collection.children.get("low") is None:
                if len(bpy.context.scene.collection.children) == 1 and not bpy.context.scene.collection.children[0].name == "high":
                    bpy.context.scene.collection.children[0].name = "low"
                else:
                    bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name="low")
            else:
                get_index_of_low = bpy.context.scene.collection.children.find("low") + 1
                bpy.ops.object.move_to_collection(collection_index=get_index_of_low)

        return {'FINISHED'}
    
    
    def register():
        bpy.utils.register_class(UtilitiesPanel)
        bpy.utils.register_class(SmartExtrude)
    def unregister():
        bpy.utils.unregister_class(UtilitiesPanel)
        bpy.utils.unregister_class(SmartExtrude)

class SmartExtrude(bpy.types.Operator):
    bl_description = "Smart Extrude, this is a slow and outdated operator, a way faster and better version is in the works"
    bl_idname = "mesh.keyops_smart_extrude"
    bl_label = "Smart Extrude (Slow, Outdated)"
    bl_options = {'REGISTER', 'UNDO'}

    offset: bpy.props.FloatProperty(name="Offset", default=0.1, min=0.0) # type: ignore
    even_offset: bpy.props.BoolProperty(name="Even Offset", default=True) # type: ignore
    scale_offset: bpy.props.FloatProperty(name="Scale Offset", default=1.001, min=0.0, max=2.0) # type: ignore
    remove_doubles: bpy.props.FloatProperty(name="Remove Doubles", default=0.001, min=0.0, max=0.1) # type: ignore

    def execute(self, context):
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
        bpy.ops.mesh.duplicate_move(MESH_OT_duplicate={"mode":1}, TRANSFORM_OT_translate={"value":(0, 0, 0), "orient_type":'GLOBAL', "orient_matrix":((0, 0, 0), (0, 0, 0), (0, 0, 0)), "orient_matrix_type":'GLOBAL', "constraint_axis":(False, False, False), "mirror":False, "use_proportional_edit":False, "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "use_proportional_connected":False, "use_proportional_projected":False, "snap":False, "snap_elements":{'INCREMENT'}, "use_snap_project":False, "snap_target":'CLOSEST', "use_snap_self":True, "use_snap_edit":True, "use_snap_nonedit":True, "use_snap_selectable":False, "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0), "gpencil_strokes":False, "cursor_transform":False, "texture_space":False, "remove_on_cancel":False, "use_duplicated_keyframes":False, "view2d_edge_pan":False, "release_confirm":False, "use_accurate":False, "use_automerge_and_split":False})
        bpy.ops.mesh.flip_normals()
        bpy.ops.transform.shrink_fatten(value=-0.00318323, use_even_offset=self.even_offset, mirror=True, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False)
        bpy.ops.transform.resize(value=(self.scale_offset, self.scale_offset, self.scale_offset), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', mirror=True, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False, snap_elements={'INCREMENT'}, use_snap_project=False, snap_target='CLOSEST', use_snap_self=True, use_snap_edit=True, use_snap_nonedit=True, use_snap_selectable=False)
        bpy.ops.mesh.extrude_region_shrink_fatten(MESH_OT_extrude_region={"use_normal_flip":False, "use_dissolve_ortho_edges":False, "mirror":False}, TRANSFORM_OT_shrink_fatten={"value":self.offset, "use_even_offset":self.even_offset, "mirror":False, "use_proportional_edit":False, "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "use_proportional_connected":False, "use_proportional_projected":False, "snap":False, "release_confirm":False, "use_accurate":False})
        bpy.ops.mesh.select_linked(delimit={'NORMAL'})
        bpy.ops.mesh.intersect_boolean(operation='DIFFERENCE', use_swap=False, use_self=False, solver='FAST')
        bpy.ops.mesh.remove_doubles(threshold=self.remove_doubles, use_unselected=False)

        return {'FINISHED'}
    
    def register():
        bpy.types.VIEW3D_MT_edit_mesh_extrude.prepend(menu_func)
    def unregister():
        bpy.types.VIEW3D_MT_edit_mesh_extrude.remove(menu_func)
def menu_func(self, context):
    layout = self.layout
    layout.operator(SmartExtrude.bl_idname, text="Smart Extrude (Slow, Outdated)")



class UtilitiesPanel(bpy.types.Panel):
    bl_description = "Utilities Panel"
    bl_label = "Modifiers Utilities"
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
        if bpy.context.mode == 'OBJECT':
            row.operator("keyops.utilities_panel_op", text="Join Objects & Keep Normals").type = "Apply_and_Join"
            row = layout.row()
            row.operator("keyops.utilities_panel_op", text="Quick Apply All Modifiers").type = "Quick_Apply_All_Modifiers"
            layout.label(text="Collections:")
            row = layout.row(align=True)
            row.operator("keyops.unique_collection_duplicate", text="Unique Collection Duplicate")
            row = layout.row(align=True)
            row.operator("keyops.utilities_panel_op", text="Toggle").type = "toggle_high_low"
            row.operator("keyops.utilities_panel_op", text="high").type = "high"
            row.operator("keyops.utilities_panel_op", text="low").type = "low"

            layout.separator()

        def draw_uv_operations():
            row = layout.row()
            if bpy.context.mode == 'EDIT_MESH':
                row.operator("keyops.utilities_panel_op", text="Offset Selected UV", icon= "MOD_UVPROJECT").type = "offset_uv"   
            else:   
                row.operator("keyops.utilities_panel_op", text="Offset Object UV", icon= "MOD_UVPROJECT").type = "offset_uv"
            row = layout.row()
            row.operator("keyops.seam_by_angle", text="Seam by Angle", icon= "MOD_EDGESPLIT")
        
        if get_keyops_prefs().enable_uv_tools:
            draw_uv_operations()
        
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

        if context.mode == 'EDIT_MESH':
            row = layout.row()
            row.label(text="Meshe")
            row = layout.row()
            row.operator("mesh.keyops_smart_extrude", text="Smart Extrude (Outdated)")

        def change_meshes_draw():
            row = layout.row(align=True)
            row.operator("keyops.utilities_panel_op", text="Marke", icon="SEQUENCE_COLOR_01").type = "Marke_Changed"
            row.operator("keyops.utilities_panel_op", text="Clear", icon="SEQUENCE_COLOR_04").type = "Clear_Changed"
            row = layout.row(align=True)
            row.operator("keyops.utilities_panel_op", text="Preview", icon="HIDE_OFF").type = "Preview_Change_Objects"
            row.operator("keyops.utilities_panel_op", text="Clear All", icon="X" ).type = "Clear_All"
            row = layout.row()
            row.operator("keyops.utilities_panel_op", text="Select All Changed", icon="RESTRICT_SELECT_OFF").type = "Select_Changed"
        if bpy.app.version >= (4, 1, 0):
            header, panel_changde_meshes = layout.panel(idname="Mark Changde Objects",  default_closed=True)
            header.label(text="Mark Changde Objects")
            if panel_changde_meshes:
                change_meshes_draw()
        else:
            row = layout.row()
            row.label(text="Changde Meshes:")
            row = layout.row(align=True)
            change_meshes_draw()

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

