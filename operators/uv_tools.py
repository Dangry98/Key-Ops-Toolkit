import bmesh
import bpy
from ..utils.pref_utils import get_keyops_prefs, get_is_addon_enabled
from ..utils.mesh_utils import modifier_toggle_visability_based

#Based on the code from the excellent addon UV Toolkit by Alex Dev that is sadly no longer available, please come back Alex! :( 
#Only an very old version is still available, but I doubt it still works in new version of Blender  https://alexbel.gumroad.com/l/NbMya
#The Toggle UV sync was an serverly underrated operation that basically fixes the uv editor in Blender, and I wanted to highlight its importance and keep it alive since its no longer officaly available anywhere. 
#Its the only way to get the UV editor in Blender to not be a horrible slow mess to work in and its a must have for anyone who works with UVs.

class SmartUVSync(bpy.types.Operator):
    bl_idname = "uv.keyops_smart_uv_sync"
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

    def register():
        bpy.utils.register_class(UVEDITORSMARTUVSYNC_PT_Panel)
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


    def unregister():
        bpy.utils.unregister_class(UVEDITORSMARTUVSYNC_PT_Panel)
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


    def execute(self, context):
        tool_settings = context.tool_settings
        uv_sync_enable = not tool_settings.use_uv_select_sync
        tool_settings.use_uv_select_sync = uv_sync_enable

        if context.scene.smart_uv_sync_enable:
            self.sync_uv_selction_mode(context, uv_sync_enable)
            self.sync_selected_elements(context, uv_sync_enable)

        else:
            self.fast_sync(context)

        return {'FINISHED'}

class UVCut(bpy.types.Operator):
    bl_idname = "uv.keyops_uv_cut"
    bl_label = "KeyOps: UV Cut"
    bl_description = "Maya like Cut UVs"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        if context.tool_settings.use_uv_select_sync:
            bpy.ops.uv.keyops_smart_uv_sync()
            self.report({'WARNING'}, "UV Sync needs to be disabled for this operation")
            bpy.ops.uv.select_mode(type='EDGE')

        bpy.ops.uv.mark_seam('EXEC_DEFAULT', True)
        bpy.ops.uv.rip_move('EXEC_DEFAULT', True, TRANSFORM_OT_translate={'value': (0.00025, 0.00025, 0.0)}, UV_OT_rip={'location': (100.0, 100.0)})
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
        def sharpfromuvislands_node_group():
            sharpfromuvislands = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "SharpFromUVIslands")

            sharpfromuvislands.is_modifier = True

            #initialize sharpfromuvislands nodes
            #node Group Input
            group_input = sharpfromuvislands.nodes.new("NodeGroupInput")
            group_input.name = "Group Input"
            #sharpfromuvislands inputs
            #input Geometry
            geometry_socket = sharpfromuvislands.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
            geometry_socket.attribute_domain = 'POINT'

            #input UV
            uv_socket = sharpfromuvislands.interface.new_socket(name = "UV", in_out='INPUT', socket_type = 'NodeSocketVector')
            uv_socket.subtype = 'NONE'
            uv_socket.min_value = -3.4028234663852886e+38
            uv_socket.max_value = 3.4028234663852886e+38
            uv_socket.default_attribute_name = "UVMap"
            uv_socket.attribute_domain = 'POINT'

            #input Only UV Island Borders
            only_uv_island_borders_socket = sharpfromuvislands.interface.new_socket(name = "Only UV Island Borders", in_out='INPUT', socket_type = 'NodeSocketBool')
            only_uv_island_borders_socket.attribute_domain = 'POINT'
            only_uv_island_borders_socket.force_non_field = True

            #node Group Output
            group_output = sharpfromuvislands.nodes.new("NodeGroupOutput")
            group_output.name = "Group Output"
            group_output.is_active_output = True
            #sharpfromuvislands outputs
            #output Geometry
            geometry_socket = sharpfromuvislands.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
            geometry_socket.attribute_domain = 'POINT'



            #node Set Shade Smooth.001
            set_shade_smooth_001 = sharpfromuvislands.nodes.new("GeometryNodeSetShadeSmooth")
            set_shade_smooth_001.name = "Set Shade Smooth.001"
            set_shade_smooth_001.domain = 'FACE'
            #Selection
            set_shade_smooth_001.inputs[1].default_value = True
            #Shade Smooth
            set_shade_smooth_001.inputs[2].default_value = True

            
            #node Set Shade Smooth.002
            set_shade_smooth_002 = sharpfromuvislands.nodes.new("GeometryNodeSetShadeSmooth")
            set_shade_smooth_002.name = "Set Shade Smooth.002"
            set_shade_smooth_002.domain = 'EDGE'
            #Shade Smooth
            set_shade_smooth_002.inputs[2].default_value = True

            #node Set Shade Smooth.003
            set_shade_smooth_003 = sharpfromuvislands.nodes.new("GeometryNodeSetShadeSmooth")
            set_shade_smooth_003.name = "Set Shade Smooth.002"
            set_shade_smooth_003.domain = 'EDGE'
            #Shade Smooth
            set_shade_smooth_003.inputs[2].default_value = False

            #node Group
            group = sharpfromuvislands.nodes.new("GeometryNodeGroup")
            group.name = "Group"
            #initialize uv_islands_boundaries node group
            def uv_islands_boundaries_node_group():
                uv_islands_boundaries = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "UV Islands Boundaries")


                #initialize uv_islands_boundaries nodes
                #node Group Output
                group_output_1 = uv_islands_boundaries.nodes.new("NodeGroupOutput")
                group_output_1.name = "Group Output"
                group_output_1.is_active_output = True
                #uv_islands_boundaries outputs
                #output Geometry
                geometry_socket = uv_islands_boundaries.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
                geometry_socket.attribute_domain = 'POINT'

                #output UV Borders
                uv_borders_socket = uv_islands_boundaries.interface.new_socket(name = "UV Borders", in_out='OUTPUT', socket_type = 'NodeSocketBool')
                uv_borders_socket.attribute_domain = 'POINT'



                #node Group Input
                group_input_1 = uv_islands_boundaries.nodes.new("NodeGroupInput")
                group_input_1.name = "Group Input"
                #uv_islands_boundaries inputs
                #input Geometry
                geometry_socket = uv_islands_boundaries.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
                geometry_socket.attribute_domain = 'POINT'

                #input UV
                uv_socket = uv_islands_boundaries.interface.new_socket(name = "UV", in_out='INPUT', socket_type = 'NodeSocketVector')
                uv_socket.subtype = 'NONE'
                uv_socket.min_value = -3.4028234663852886e+38
                uv_socket.max_value = 3.4028234663852886e+38
                uv_socket.attribute_domain = 'POINT'
                uv_socket.hide_value = True


                group_input_1.outputs[0].hide = True
                group_input_1.outputs[2].hide = True

                #node Boolean Math.002
                boolean_math_002 = uv_islands_boundaries.nodes.new("FunctionNodeBooleanMath")
                boolean_math_002.name = "Boolean Math.002"
                boolean_math_002.operation = 'OR'

                #node Boolean Math.001
                boolean_math_001 = uv_islands_boundaries.nodes.new("FunctionNodeBooleanMath")
                boolean_math_001.name = "Boolean Math.001"
                boolean_math_001.operation = 'NAND'

                #node Edge Neighbors.001
                edge_neighbors_001 = uv_islands_boundaries.nodes.new("GeometryNodeInputMeshEdgeNeighbors")
                edge_neighbors_001.name = "Edge Neighbors.001"

                #node Evaluate at Index.001
                evaluate_at_index_001 = uv_islands_boundaries.nodes.new("GeometryNodeFieldAtIndex")
                evaluate_at_index_001.name = "Evaluate at Index.001"
                evaluate_at_index_001.data_type = 'FLOAT_VECTOR'
                evaluate_at_index_001.domain = 'CORNER'

                #node Offset Corner in Face
                offset_corner_in_face = uv_islands_boundaries.nodes.new("GeometryNodeOffsetCornerInFace")
                offset_corner_in_face.name = "Offset Corner in Face"
                #Offset
                offset_corner_in_face.inputs[1].default_value = 1

                #node Corners of Edge
                corners_of_edge = uv_islands_boundaries.nodes.new("GeometryNodeCornersOfEdge")
                corners_of_edge.name = "Corners of Edge"
                corners_of_edge.inputs[0].hide = True
                corners_of_edge.inputs[1].hide = True
                corners_of_edge.outputs[1].hide = True
                #Edge Index
                corners_of_edge.inputs[0].default_value = 0
                #Weights
                corners_of_edge.inputs[1].default_value = 0.0
                #Sort Index
                corners_of_edge.inputs[2].default_value = 0

                #node Corners of Edge.001
                corners_of_edge_001 = uv_islands_boundaries.nodes.new("GeometryNodeCornersOfEdge")
                corners_of_edge_001.name = "Corners of Edge.001"
                corners_of_edge_001.inputs[0].hide = True
                corners_of_edge_001.inputs[1].hide = True
                corners_of_edge_001.outputs[1].hide = True
                #Edge Index
                corners_of_edge_001.inputs[0].default_value = 0
                #Weights
                corners_of_edge_001.inputs[1].default_value = 0.0
                #Sort Index
                corners_of_edge_001.inputs[2].default_value = 1

                #node Evaluate at Index
                evaluate_at_index = uv_islands_boundaries.nodes.new("GeometryNodeFieldAtIndex")
                evaluate_at_index.name = "Evaluate at Index"
                evaluate_at_index.data_type = 'FLOAT_VECTOR'
                evaluate_at_index.domain = 'CORNER'

                #node Evaluate at Index.002
                evaluate_at_index_002 = uv_islands_boundaries.nodes.new("GeometryNodeFieldAtIndex")
                evaluate_at_index_002.name = "Evaluate at Index.002"
                evaluate_at_index_002.data_type = 'FLOAT_VECTOR'
                evaluate_at_index_002.domain = 'CORNER'

                #node Offset Corner in Face.001
                offset_corner_in_face_001 = uv_islands_boundaries.nodes.new("GeometryNodeOffsetCornerInFace")
                offset_corner_in_face_001.name = "Offset Corner in Face.001"
                #Offset
                offset_corner_in_face_001.inputs[1].default_value = 1

                #node Corners of Edge.002
                corners_of_edge_002 = uv_islands_boundaries.nodes.new("GeometryNodeCornersOfEdge")
                corners_of_edge_002.name = "Corners of Edge.002"
                corners_of_edge_002.inputs[0].hide = True
                corners_of_edge_002.inputs[1].hide = True
                corners_of_edge_002.outputs[1].hide = True
                #Edge Index
                corners_of_edge_002.inputs[0].default_value = 0
                #Weights
                corners_of_edge_002.inputs[1].default_value = 0.0
                #Sort Index
                corners_of_edge_002.inputs[2].default_value = 1

                #node Corners of Edge.003
                corners_of_edge_003 = uv_islands_boundaries.nodes.new("GeometryNodeCornersOfEdge")
                corners_of_edge_003.name = "Corners of Edge.003"
                corners_of_edge_003.inputs[0].hide = True
                corners_of_edge_003.inputs[1].hide = True
                corners_of_edge_003.outputs[1].hide = True
                #Edge Index
                corners_of_edge_003.inputs[0].default_value = 0
                #Weights
                corners_of_edge_003.inputs[1].default_value = 0.0
                #Sort Index
                corners_of_edge_003.inputs[2].default_value = 0

                #node Evaluate at Index.003
                evaluate_at_index_003 = uv_islands_boundaries.nodes.new("GeometryNodeFieldAtIndex")
                evaluate_at_index_003.name = "Evaluate at Index.003"
                evaluate_at_index_003.data_type = 'FLOAT_VECTOR'
                evaluate_at_index_003.domain = 'CORNER'

                #node Compare
                compare = uv_islands_boundaries.nodes.new("FunctionNodeCompare")
                compare.name = "Compare"
                compare.data_type = 'VECTOR'
                compare.mode = 'ELEMENT'
                compare.operation = 'EQUAL'
                #A
                compare.inputs[0].default_value = 0.0
                #B
                compare.inputs[1].default_value = 0.0
                #A_INT
                compare.inputs[2].default_value = 0
                #B_INT
                compare.inputs[3].default_value = 0
                #A_COL
                compare.inputs[6].default_value = (0.0, 0.0, 0.0, 0.0)
                #B_COL
                compare.inputs[7].default_value = (0.0, 0.0, 0.0, 0.0)
                #A_STR
                compare.inputs[8].default_value = ""
                #B_STR
                compare.inputs[9].default_value = ""
                #C
                compare.inputs[10].default_value = 0.8999999761581421
                #Angle
                compare.inputs[11].default_value = 0.08726649731397629
                #Epsilon
                compare.inputs[12].default_value = 0.0

                #node Compare.002
                compare_002 = uv_islands_boundaries.nodes.new("FunctionNodeCompare")
                compare_002.name = "Compare.002"
                compare_002.data_type = 'VECTOR'
                compare_002.mode = 'ELEMENT'
                compare_002.operation = 'EQUAL'
                #A
                compare_002.inputs[0].default_value = 0.0
                #B
                compare_002.inputs[1].default_value = 0.0
                #A_INT
                compare_002.inputs[2].default_value = 0
                #B_INT
                compare_002.inputs[3].default_value = 0
                #A_COL
                compare_002.inputs[6].default_value = (0.0, 0.0, 0.0, 0.0)
                #B_COL
                compare_002.inputs[7].default_value = (0.0, 0.0, 0.0, 0.0)
                #A_STR
                compare_002.inputs[8].default_value = ""
                #B_STR
                compare_002.inputs[9].default_value = ""
                #C
                compare_002.inputs[10].default_value = 0.8999999761581421
                #Angle
                compare_002.inputs[11].default_value = 0.08726649731397629
                #Epsilon
                compare_002.inputs[12].default_value = 0.0

                #node Compare.003
                compare_003 = uv_islands_boundaries.nodes.new("FunctionNodeCompare")
                compare_003.name = "Compare.003"
                compare_003.data_type = 'INT'
                compare_003.mode = 'ELEMENT'
                compare_003.operation = 'EQUAL'
                #A
                compare_003.inputs[0].default_value = 0.0
                #B
                compare_003.inputs[1].default_value = 0.0
                #B_INT
                compare_003.inputs[3].default_value = 1
                #A_VEC3
                compare_003.inputs[4].default_value = (0.0, 0.0, 0.0)
                #B_VEC3
                compare_003.inputs[5].default_value = (0.0, 0.0, 0.0)
                #A_COL
                compare_003.inputs[6].default_value = (0.0, 0.0, 0.0, 0.0)
                #B_COL
                compare_003.inputs[7].default_value = (0.0, 0.0, 0.0, 0.0)
                #A_STR
                compare_003.inputs[8].default_value = ""
                #B_STR
                compare_003.inputs[9].default_value = ""
                #C
                compare_003.inputs[10].default_value = 0.8999999761581421
                #Angle
                compare_003.inputs[11].default_value = 0.08726649731397629
                #Epsilon
                compare_003.inputs[12].default_value = 0.0010000000474974513

                #node Group Input.001
                group_input_001 = uv_islands_boundaries.nodes.new("NodeGroupInput")
                group_input_001.name = "Group Input.001"
                group_input_001.outputs[1].hide = True
                group_input_001.outputs[2].hide = True




                #Set locations
                group_output_1.location = (561.7774658203125, -117.97454833984375)
                group_input_1.location = (-668.76904296875, -47.189823150634766)
                boolean_math_002.location = (350.0039978027344, -0.04056549072265625)
                boolean_math_001.location = (209.17730712890625, -71.60853576660156)
                edge_neighbors_001.location = (51.36872100830078, 66.03910064697266)
                evaluate_at_index_001.location = (-128.41116333007812, 63.79388427734375)
                offset_corner_in_face.location = (-308.1910400390625, 61.548667907714844)
                corners_of_edge.location = (-327.8054504394531, -149.02264404296875)
                corners_of_edge_001.location = (-467.9953918457031, 59.55291748046875)
                evaluate_at_index.location = (-130.40692138671875, -75.84950256347656)
                evaluate_at_index_002.location = (-130.0, -260.0)
                offset_corner_in_face_001.location = (-318.07373046875, -270.2109069824219)
                corners_of_edge_002.location = (-302.39044189453125, -470.37615966796875)
                corners_of_edge_003.location = (-469.0550231933594, -258.80487060546875)
                evaluate_at_index_003.location = (-130.0, -420.0)
                compare.location = (50.62031555175781, 13.672832489013672)
                compare_002.location = (50.0, -260.0)
                compare_003.location = (211.17306518554688, 68.03484344482422)
                group_input_001.location = (383.9731140136719, -124.26652526855469)

                #initialize uv_islands_boundaries links
                #corners_of_edge_002.Corner Index -> evaluate_at_index_003.Index
                uv_islands_boundaries.links.new(corners_of_edge_002.outputs[0], evaluate_at_index_003.inputs[0])
                #offset_corner_in_face.Corner Index -> evaluate_at_index_001.Index
                uv_islands_boundaries.links.new(offset_corner_in_face.outputs[0], evaluate_at_index_001.inputs[0])
                #edge_neighbors_001.Face Count -> compare_003.A
                uv_islands_boundaries.links.new(edge_neighbors_001.outputs[0], compare_003.inputs[2])
                #compare_002.Result -> boolean_math_001.Boolean
                uv_islands_boundaries.links.new(compare_002.outputs[0], boolean_math_001.inputs[1])
                #evaluate_at_index_002.Value -> compare_002.A
                uv_islands_boundaries.links.new(evaluate_at_index_002.outputs[0], compare_002.inputs[4])
                #offset_corner_in_face_001.Corner Index -> evaluate_at_index_002.Index
                uv_islands_boundaries.links.new(offset_corner_in_face_001.outputs[0], evaluate_at_index_002.inputs[0])
                #corners_of_edge.Corner Index -> evaluate_at_index.Index
                uv_islands_boundaries.links.new(corners_of_edge.outputs[0], evaluate_at_index.inputs[0])
                #boolean_math_001.Boolean -> boolean_math_002.Boolean
                uv_islands_boundaries.links.new(boolean_math_001.outputs[0], boolean_math_002.inputs[1])
                #compare.Result -> boolean_math_001.Boolean
                uv_islands_boundaries.links.new(compare.outputs[0], boolean_math_001.inputs[0])
                #evaluate_at_index_001.Value -> compare.A
                uv_islands_boundaries.links.new(evaluate_at_index_001.outputs[0], compare.inputs[4])
                #evaluate_at_index.Value -> compare.B
                uv_islands_boundaries.links.new(evaluate_at_index.outputs[0], compare.inputs[5])
                #compare_003.Result -> boolean_math_002.Boolean
                uv_islands_boundaries.links.new(compare_003.outputs[0], boolean_math_002.inputs[0])
                #corners_of_edge_003.Corner Index -> offset_corner_in_face_001.Corner Index
                uv_islands_boundaries.links.new(corners_of_edge_003.outputs[0], offset_corner_in_face_001.inputs[0])
                #evaluate_at_index_003.Value -> compare_002.B
                uv_islands_boundaries.links.new(evaluate_at_index_003.outputs[0], compare_002.inputs[5])
                #corners_of_edge_001.Corner Index -> offset_corner_in_face.Corner Index
                uv_islands_boundaries.links.new(corners_of_edge_001.outputs[0], offset_corner_in_face.inputs[0])
                #group_input_1.UV -> evaluate_at_index_001.Value
                uv_islands_boundaries.links.new(group_input_1.outputs[1], evaluate_at_index_001.inputs[1])
                #group_input_1.UV -> evaluate_at_index.Value
                uv_islands_boundaries.links.new(group_input_1.outputs[1], evaluate_at_index.inputs[1])
                #group_input_1.UV -> evaluate_at_index_002.Value
                uv_islands_boundaries.links.new(group_input_1.outputs[1], evaluate_at_index_002.inputs[1])
                #group_input_1.UV -> evaluate_at_index_003.Value
                uv_islands_boundaries.links.new(group_input_1.outputs[1], evaluate_at_index_003.inputs[1])
                #boolean_math_002.Boolean -> group_output_1.UV Borders
                uv_islands_boundaries.links.new(boolean_math_002.outputs[0], group_output_1.inputs[1])
                #group_input_001.Geometry -> group_output_1.Geometry
                uv_islands_boundaries.links.new(group_input_001.outputs[0], group_output_1.inputs[0])
                return uv_islands_boundaries

            uv_islands_boundaries = uv_islands_boundaries_node_group()

            group.node_tree = bpy.data.node_groups["UV Islands Boundaries"]

            #node Face Group Boundaries
            face_group_boundaries = sharpfromuvislands.nodes.new("GeometryNodeMeshFaceSetBoundaries")
            face_group_boundaries.name = "Face Group Boundaries"

            #node Edges to Face Groups
            edges_to_face_groups = sharpfromuvislands.nodes.new("GeometryNodeEdgesToFaceGroups")
            edges_to_face_groups.name = "Edges to Face Groups"

            #node Switch
            switch = sharpfromuvislands.nodes.new("GeometryNodeSwitch")
            switch.name = "Switch"
            switch.input_type = 'BOOLEAN'

            #Set locations
            group_input.location = (431.7928161621094, 51.20960998535156)
            group_output.location = (1382.4488525390625, 137.2201690673828)
            set_shade_smooth_001.location = (972.25634765625, 132.051025390625)
            set_shade_smooth_002.location = (1176.4324951171875, 133.21624755859375)
            set_shade_smooth_003.location = (1180.4324951171875, 140.21624755859375)
            group.location = (667.629150390625, 119.90283203125)
            face_group_boundaries.location = (1063.4482421875, -47.62242889404297)
            edges_to_face_groups.location = (898.8531494140625, -48.52994155883789)
            switch.location = (1245.561767578125, -37.500709533691406)

            #initialize sharpfromuvislands links
            #set_shade_smooth_001.Geometry -> set_shade_smooth_002.Geometry
            sharpfromuvislands.links.new(set_shade_smooth_001.outputs[0], set_shade_smooth_002.inputs[0])
            #set_shade_smooth_002.Geometry -> set_shade_smooth_003.Geometry
            sharpfromuvislands.links.new(set_shade_smooth_002.outputs[0], set_shade_smooth_003.inputs[0])
            #set_shade_smooth_003.Geometry -> group_output.Geometry
            sharpfromuvislands.links.new(set_shade_smooth_003.outputs[0], group_output.inputs[0])
            #group_input.Geometry -> group.Geometry
            sharpfromuvislands.links.new(group_input.outputs[0], group.inputs[0])
            #group_input.UV -> group.UV
            sharpfromuvislands.links.new(group_input.outputs[1], group.inputs[1])
            #group.Geometry -> set_shade_smooth_001.Geometry
            sharpfromuvislands.links.new(group.outputs[0], set_shade_smooth_001.inputs[0])
            #edges_to_face_groups.Face Group ID -> face_group_boundaries.Face Group ID
            sharpfromuvislands.links.new(edges_to_face_groups.outputs[0], face_group_boundaries.inputs[0])
            #group.UV Borders -> edges_to_face_groups.Boundary Edges
            sharpfromuvislands.links.new(group.outputs[1], edges_to_face_groups.inputs[0])
            #group.UV Borders -> switch.False
            sharpfromuvislands.links.new(group.outputs[1], switch.inputs[1])
            #face_group_boundaries.Boundary Edges -> switch.True
            sharpfromuvislands.links.new(face_group_boundaries.outputs[0], switch.inputs[2])
            #switch.Output -> set_shade_smooth_003.Selection
            sharpfromuvislands.links.new(switch.outputs[0], set_shade_smooth_003.inputs[1])
            #group_input.Only UV Island Borders -> switch.Switch
            sharpfromuvislands.links.new(group_input.outputs[2], switch.inputs[0])
            return sharpfromuvislands

        if "SharpFromUVIslands" not in bpy.data.node_groups:
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
    select_islands: bpy.props.BoolProperty(name="Select Islands (Slow)", default=True, description="Select Islands") # type: ignore
    uv_unwrap_method: bpy.props.EnumProperty(name="Method", items=(('ANGLE_BASED', "Angle Based", "Angle Based"), ('CONFORMAL', "Conformal", "Conformal")), default='CONFORMAL', description="UV Unwrap Method") # type: ignore
    fill_holes: bpy.props.BoolProperty(name="Fill Holes", default=True, description="Fill Holes") # type: ignore
    pack_uv_islands: bpy.props.BoolProperty(name="Pack UV Islands", default=True, description="Pack UV Islands") # type: ignore
    margin: bpy.props.FloatProperty(name="Margin", default=0.01, min=0.0, max=1.0, description="Margin") # type: ignore
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
        layout.prop(self, "select_islands")
        layout.prop(self, "uv_unwrap_method")
        layout.prop(self, "fill_holes")
        layout.label(text="Pack Islands:")
        layout.prop(self, "pack_uv_islands")
        if self.pack_uv_islands:
            layout.prop(self, "margin")
            layout.prop(self, "rotate")
            layout.prop(self, "rotation_method")
            #layout.prop(self, "apply_modifier")

    def execute(self, context):
        def match_bounding_box_node_group():
            match_bounding_box = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Match Bounding Box")

            match_bounding_box.is_modifier = True
            
            #initialize match_bounding_box nodes
            #match_bounding_box interface
            #Socket Vector
            vector_socket = match_bounding_box.interface.new_socket(name = "Vector", in_out='OUTPUT', socket_type = 'NodeSocketVector')
            vector_socket.subtype = 'NONE'
            vector_socket.default_value = (0.0, 0.0, 0.0)
            vector_socket.min_value = -3.4028234663852886e+38
            vector_socket.max_value = 3.4028234663852886e+38
            vector_socket.attribute_domain = 'POINT'
            
            #Socket Geometry
            geometry_socket = match_bounding_box.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
            geometry_socket.attribute_domain = 'POINT'
            
            #Socket Target
            target_socket = match_bounding_box.interface.new_socket(name = "Target", in_out='INPUT', socket_type = 'NodeSocketGeometry')
            target_socket.attribute_domain = 'POINT'
            
            
            #node Vector Math.001
            vector_math_001 = match_bounding_box.nodes.new("ShaderNodeVectorMath")
            vector_math_001.name = "Vector Math.001"
            vector_math_001.operation = 'SUBTRACT'
            #Vector_002
            vector_math_001.inputs[2].default_value = (0.0, 0.0, 0.0)
            #Scale
            vector_math_001.inputs[3].default_value = 1.0
            
            #node Vector Math
            vector_math = match_bounding_box.nodes.new("ShaderNodeVectorMath")
            vector_math.name = "Vector Math"
            vector_math.operation = 'DIVIDE'
            #Vector_002
            vector_math.inputs[2].default_value = (0.0, 0.0, 0.0)
            #Scale
            vector_math.inputs[3].default_value = 1.0
            
            #node Math
            math = match_bounding_box.nodes.new("ShaderNodeMath")
            math.name = "Math"
            math.operation = 'ADD'
            math.use_clamp = False
            #Value
            math.inputs[0].default_value = 2.0
            #Value_001
            math.inputs[1].default_value = 1.0
            #Value_002
            math.inputs[2].default_value = 0.5
            
            #node Math.001
            math_001 = match_bounding_box.nodes.new("ShaderNodeMath")
            math_001.name = "Math.001"
            math_001.operation = 'MODULO'
            math_001.use_clamp = False
            #Value_001
            math_001.inputs[1].default_value = 3.0
            #Value_002
            math_001.inputs[2].default_value = 0.5
            
            #node Math.002
            math_002 = match_bounding_box.nodes.new("ShaderNodeMath")
            math_002.name = "Math.002"
            math_002.operation = 'ADD'
            math_002.use_clamp = False
            #Value
            math_002.inputs[0].default_value = 2.0
            #Value_001
            math_002.inputs[1].default_value = 2.0
            #Value_002
            math_002.inputs[2].default_value = 0.5
            
            #node Math.003
            math_003 = match_bounding_box.nodes.new("ShaderNodeMath")
            math_003.name = "Math.003"
            math_003.operation = 'MODULO'
            math_003.use_clamp = False
            #Value_001
            math_003.inputs[1].default_value = 3.0
            #Value_002
            math_003.inputs[2].default_value = 0.5
            
            #node Position
            position = match_bounding_box.nodes.new("GeometryNodeInputPosition")
            position.name = "Position"
            
            #node Group Output
            group_output = match_bounding_box.nodes.new("NodeGroupOutput")
            group_output.name = "Group Output"
            group_output.is_active_output = True
            
            #node Group Input
            group_input = match_bounding_box.nodes.new("NodeGroupInput")
            group_input.name = "Group Input"
            
            #node Mix
            mix = match_bounding_box.nodes.new("ShaderNodeMix")
            mix.name = "Mix"
            mix.blend_type = 'MIX'
            mix.clamp_factor = True
            mix.clamp_result = False
            mix.data_type = 'VECTOR'
            mix.factor_mode = 'UNIFORM'
            #Factor_Vector
            mix.inputs[1].default_value = (0.5, 0.5, 0.5)
            #A_Float
            mix.inputs[2].default_value = 0.0
            #B_Float
            mix.inputs[3].default_value = 0.0
            #A_Color
            mix.inputs[6].default_value = (0.5, 0.5, 0.5, 1.0)
            #B_Color
            mix.inputs[7].default_value = (0.5, 0.5, 0.5, 1.0)
            #A_Rotation
            mix.inputs[8].default_value = (0.0, 0.0, 0.0)
            #B_Rotation
            mix.inputs[9].default_value = (0.0, 0.0, 0.0)
            
            #node Mix.001
            mix_001 = match_bounding_box.nodes.new("ShaderNodeMix")
            mix_001.name = "Mix.001"
            mix_001.blend_type = 'MIX'
            mix_001.clamp_factor = True
            mix_001.clamp_result = False
            mix_001.data_type = 'VECTOR'
            mix_001.factor_mode = 'UNIFORM'
            #Factor_Vector
            mix_001.inputs[1].default_value = (0.5, 0.5, 0.5)
            #A_Float
            mix_001.inputs[2].default_value = 0.0
            #B_Float
            mix_001.inputs[3].default_value = 0.0
            #A_Color
            mix_001.inputs[6].default_value = (0.5, 0.5, 0.5, 1.0)
            #B_Color
            mix_001.inputs[7].default_value = (0.5, 0.5, 0.5, 1.0)
            #A_Rotation
            mix_001.inputs[8].default_value = (0.0, 0.0, 0.0)
            #B_Rotation
            mix_001.inputs[9].default_value = (0.0, 0.0, 0.0)
            
            #node Mix.002
            mix_002 = match_bounding_box.nodes.new("ShaderNodeMix")
            mix_002.name = "Mix.002"
            mix_002.blend_type = 'MIX'
            mix_002.clamp_factor = True
            mix_002.clamp_result = False
            mix_002.data_type = 'VECTOR'
            mix_002.factor_mode = 'UNIFORM'
            #Factor_Vector
            mix_002.inputs[1].default_value = (0.5, 0.5, 0.5)
            #A_Float
            mix_002.inputs[2].default_value = 0.0
            #B_Float
            mix_002.inputs[3].default_value = 0.0
            #A_Color
            mix_002.inputs[6].default_value = (0.5, 0.5, 0.5, 1.0)
            #B_Color
            mix_002.inputs[7].default_value = (0.5, 0.5, 0.5, 1.0)
            #A_Rotation
            mix_002.inputs[8].default_value = (0.0, 0.0, 0.0)
            #B_Rotation
            mix_002.inputs[9].default_value = (0.0, 0.0, 0.0)
            
            #node Bounding Box
            bounding_box = match_bounding_box.nodes.new("GeometryNodeBoundBox")
            bounding_box.name = "Bounding Box"
            
            #node Vector Math.004
            vector_math_004 = match_bounding_box.nodes.new("ShaderNodeVectorMath")
            vector_math_004.name = "Vector Math.004"
            vector_math_004.operation = 'SUBTRACT'
            #Vector_002
            vector_math_004.inputs[2].default_value = (0.0, 0.0, 0.0)
            #Scale
            vector_math_004.inputs[3].default_value = 1.0
            
            #node Reroute
            reroute = match_bounding_box.nodes.new("NodeReroute")
            reroute.name = "Reroute"
            #node Separate XYZ
            separate_xyz = match_bounding_box.nodes.new("ShaderNodeSeparateXYZ")
            separate_xyz.name = "Separate XYZ"
            
            #node Compare
            compare = match_bounding_box.nodes.new("FunctionNodeCompare")
            compare.name = "Compare"
            compare.data_type = 'INT'
            compare.mode = 'ELEMENT'
            compare.operation = 'EQUAL'
            #A
            compare.inputs[0].default_value = 0.0
            #B
            compare.inputs[1].default_value = 0.0
            #B_INT
            compare.inputs[3].default_value = 0
            #A_VEC3
            compare.inputs[4].default_value = (0.0, 0.0, 0.0)
            #B_VEC3
            compare.inputs[5].default_value = (0.0, 0.0, 0.0)
            #A_COL
            compare.inputs[6].default_value = (0.0, 0.0, 0.0, 0.0)
            #B_COL
            compare.inputs[7].default_value = (0.0, 0.0, 0.0, 0.0)
            #A_STR
            compare.inputs[8].default_value = ""
            #B_STR
            compare.inputs[9].default_value = ""
            #C
            compare.inputs[10].default_value = 0.8999999761581421
            #Angle
            compare.inputs[11].default_value = 0.08726649731397629
            #Epsilon
            compare.inputs[12].default_value = 0.0010000000474974513
            
            #node Math.004
            math_004 = match_bounding_box.nodes.new("ShaderNodeMath")
            math_004.name = "Math.004"
            math_004.operation = 'MULTIPLY'
            math_004.use_clamp = False
            #Value_002
            math_004.inputs[2].default_value = 0.5
            
            #node Reroute.001
            reroute_001 = match_bounding_box.nodes.new("NodeReroute")
            reroute_001.name = "Reroute.001"
            #node Separate XYZ.001
            separate_xyz_001 = match_bounding_box.nodes.new("ShaderNodeSeparateXYZ")
            separate_xyz_001.name = "Separate XYZ.001"
            
            #node Compare.001
            compare_001 = match_bounding_box.nodes.new("FunctionNodeCompare")
            compare_001.name = "Compare.001"
            compare_001.data_type = 'INT'
            compare_001.mode = 'ELEMENT'
            compare_001.operation = 'EQUAL'
            #A
            compare_001.inputs[0].default_value = 0.0
            #B
            compare_001.inputs[1].default_value = 0.0
            #B_INT
            compare_001.inputs[3].default_value = 0
            #A_VEC3
            compare_001.inputs[4].default_value = (0.0, 0.0, 0.0)
            #B_VEC3
            compare_001.inputs[5].default_value = (0.0, 0.0, 0.0)
            #A_COL
            compare_001.inputs[6].default_value = (0.0, 0.0, 0.0, 0.0)
            #B_COL
            compare_001.inputs[7].default_value = (0.0, 0.0, 0.0, 0.0)
            #A_STR
            compare_001.inputs[8].default_value = ""
            #B_STR
            compare_001.inputs[9].default_value = ""
            #C
            compare_001.inputs[10].default_value = 0.8999999761581421
            #Angle
            compare_001.inputs[11].default_value = 0.08726649731397629
            #Epsilon
            compare_001.inputs[12].default_value = 0.0010000000474974513
            
            #node Math.007
            math_007 = match_bounding_box.nodes.new("ShaderNodeMath")
            math_007.name = "Math.007"
            math_007.operation = 'MULTIPLY'
            math_007.use_clamp = False
            #Value_002
            math_007.inputs[2].default_value = 0.5
            
            #node Math.008
            math_008 = match_bounding_box.nodes.new("ShaderNodeMath")
            math_008.name = "Math.008"
            math_008.operation = 'MULTIPLY'
            math_008.use_clamp = False
            #Value_002
            math_008.inputs[2].default_value = 0.5
            
            #node Math.009
            math_009 = match_bounding_box.nodes.new("ShaderNodeMath")
            math_009.name = "Math.009"
            math_009.operation = 'ADD'
            math_009.use_clamp = False
            #Value_002
            math_009.inputs[2].default_value = 0.5
            
            #node Position.001
            position_001 = match_bounding_box.nodes.new("GeometryNodeInputPosition")
            position_001.name = "Position.001"
            
            #node Vertex of Corner
            vertex_of_corner = match_bounding_box.nodes.new("GeometryNodeVertexOfCorner")
            vertex_of_corner.name = "Vertex of Corner"
            
            #node Vertex of Corner.001
            vertex_of_corner_001 = match_bounding_box.nodes.new("GeometryNodeVertexOfCorner")
            vertex_of_corner_001.name = "Vertex of Corner.001"
            
            #node Corners of Face.001
            corners_of_face_001 = match_bounding_box.nodes.new("GeometryNodeCornersOfFace")
            corners_of_face_001.name = "Corners of Face.001"
            #Weights
            corners_of_face_001.inputs[1].default_value = 0.0
            #Sort Index
            corners_of_face_001.inputs[2].default_value = 1
            
            #node Vertex of Corner.002
            vertex_of_corner_002 = match_bounding_box.nodes.new("GeometryNodeVertexOfCorner")
            vertex_of_corner_002.name = "Vertex of Corner.002"
            
            #node Corners of Face.002
            corners_of_face_002 = match_bounding_box.nodes.new("GeometryNodeCornersOfFace")
            corners_of_face_002.name = "Corners of Face.002"
            #Weights
            corners_of_face_002.inputs[1].default_value = 0.0
            #Sort Index
            corners_of_face_002.inputs[2].default_value = 2
            
            #node Vertex of Corner.003
            vertex_of_corner_003 = match_bounding_box.nodes.new("GeometryNodeVertexOfCorner")
            vertex_of_corner_003.name = "Vertex of Corner.003"
            
            #node Sample Index.002
            sample_index_002 = match_bounding_box.nodes.new("GeometryNodeSampleIndex")
            sample_index_002.name = "Sample Index.002"
            sample_index_002.clamp = False
            sample_index_002.data_type = 'FLOAT_VECTOR'
            sample_index_002.domain = 'POINT'
            
            #node Sample Index.005
            sample_index_005 = match_bounding_box.nodes.new("GeometryNodeSampleIndex")
            sample_index_005.name = "Sample Index.005"
            sample_index_005.clamp = False
            sample_index_005.data_type = 'FLOAT_VECTOR'
            sample_index_005.domain = 'POINT'
            
            #node Sample Index.004
            sample_index_004 = match_bounding_box.nodes.new("GeometryNodeSampleIndex")
            sample_index_004.name = "Sample Index.004"
            sample_index_004.clamp = False
            sample_index_004.data_type = 'FLOAT_VECTOR'
            sample_index_004.domain = 'POINT'
            
            #node Sample Index.007
            sample_index_007 = match_bounding_box.nodes.new("GeometryNodeSampleIndex")
            sample_index_007.name = "Sample Index.007"
            sample_index_007.clamp = False
            sample_index_007.data_type = 'FLOAT_VECTOR'
            sample_index_007.domain = 'POINT'
            
            #node Sample Index.001
            sample_index_001 = match_bounding_box.nodes.new("GeometryNodeSampleIndex")
            sample_index_001.name = "Sample Index.001"
            sample_index_001.clamp = False
            sample_index_001.data_type = 'FLOAT_VECTOR'
            sample_index_001.domain = 'FACE'
            #Index
            sample_index_001.inputs[2].default_value = 0
            
            #node Sample Index.003
            sample_index_003 = match_bounding_box.nodes.new("GeometryNodeSampleIndex")
            sample_index_003.name = "Sample Index.003"
            sample_index_003.clamp = False
            sample_index_003.data_type = 'FLOAT_VECTOR'
            sample_index_003.domain = 'FACE'
            #Index
            sample_index_003.inputs[2].default_value = 0
            
            #node Sample Index.008
            sample_index_008 = match_bounding_box.nodes.new("GeometryNodeSampleIndex")
            sample_index_008.name = "Sample Index.008"
            sample_index_008.clamp = False
            sample_index_008.data_type = 'FLOAT_VECTOR'
            sample_index_008.domain = 'FACE'
            #Index
            sample_index_008.inputs[2].default_value = 0
            
            #node Sample Index.006
            sample_index_006 = match_bounding_box.nodes.new("GeometryNodeSampleIndex")
            sample_index_006.name = "Sample Index.006"
            sample_index_006.clamp = False
            sample_index_006.data_type = 'FLOAT_VECTOR'
            sample_index_006.domain = 'FACE'
            #Index
            sample_index_006.inputs[2].default_value = 0
            
            #node Corners of Face.003
            corners_of_face_003 = match_bounding_box.nodes.new("GeometryNodeCornersOfFace")
            corners_of_face_003.name = "Corners of Face.003"
            #Weights
            corners_of_face_003.inputs[1].default_value = 0.0
            #Sort Index
            corners_of_face_003.inputs[2].default_value = 3
            
            #node Corners of Face
            corners_of_face = match_bounding_box.nodes.new("GeometryNodeCornersOfFace")
            corners_of_face.name = "Corners of Face"
            #Weights
            corners_of_face.inputs[1].default_value = 0.0
            #Sort Index
            corners_of_face.inputs[2].default_value = 0
            
            #node Index
            index = match_bounding_box.nodes.new("GeometryNodeInputIndex")
            index.name = "Index"
            
            
            
            
            #Set locations
            vector_math_001.location = (671.8292846679688, -3.393566131591797)
            vector_math.location = (905.0932006835938, 144.4541015625)
            math.location = (565.4978637695312, -232.2760772705078)
            math_001.location = (881.5574340820312, -204.1563720703125)
            math_002.location = (590.8495483398438, -395.4056396484375)
            math_003.location = (884.0984497070312, -376.4026184082031)
            position.location = (393.37603759765625, -64.50838470458984)
            group_output.location = (1984.5904541015625, 958.5203857421875)
            group_input.location = (-385.03082275390625, 340.2637939453125)
            mix.location = (1455.6461181640625, 951.1998291015625)
            mix_001.location = (1458.203857421875, 762.4796142578125)
            mix_002.location = (1741.3050537109375, 888.8538818359375)
            bounding_box.location = (9.702392578125, 74.94915771484375)
            vector_math_004.location = (424.3367919921875, 105.096923828125)
            reroute.location = (816.8677978515625, -114.7408676147461)
            separate_xyz.location = (987.7881469726562, 44.316226959228516)
            compare.location = (882.8019409179688, -80.56271362304688)
            math_004.location = (1067.386962890625, -60.907283782958984)
            reroute_001.location = (1015.1231079101562, -369.200927734375)
            separate_xyz_001.location = (1128.98388671875, -163.91058349609375)
            compare_001.location = (1129.827880859375, -309.7416687011719)
            math_007.location = (1451.3521728515625, 267.85394287109375)
            math_008.location = (1450.5181884765625, 218.8677978515625)
            math_009.location = (1588.9984130859375, 460.2774353027344)
            position_001.location = (330.43988037109375, 1052.831298828125)
            vertex_of_corner.location = (336.75323486328125, 979.8141479492188)
            vertex_of_corner_001.location = (316.51531982421875, 770.7216186523438)
            corners_of_face_001.location = (37.93927001953125, 766.745849609375)
            vertex_of_corner_002.location = (296.0479736328125, 562.2384643554688)
            corners_of_face_002.location = (17.47186279296875, 558.2626953125)
            vertex_of_corner_003.location = (274.91302490234375, 347.5218505859375)
            sample_index_002.location = (618.0657958984375, 1046.685546875)
            sample_index_005.location = (577.3604736328125, 629.1099243164062)
            sample_index_004.location = (597.827880859375, 837.5931396484375)
            sample_index_007.location = (556.2257080078125, 414.3934326171875)
            sample_index_001.location = (935.4558715820312, 1079.818603515625)
            sample_index_003.location = (911.6384887695312, 866.556396484375)
            sample_index_008.location = (864.8963012695312, 393.2352294921875)
            sample_index_006.location = (889.1013793945312, 656.0769653320312)
            corners_of_face_003.location = (-4.5345458984375, 349.69403076171875)
            corners_of_face.location = (58.17718505859375, 975.83837890625)
            index.location = (-164.66323852539062, 893.779296875)
            
            #Set dimensions
            vector_math_001.width, vector_math_001.height = 140.0, 100.0
            vector_math.width, vector_math.height = 140.0, 100.0
            math.width, math.height = 140.0, 100.0
            math_001.width, math_001.height = 140.0, 100.0
            math_002.width, math_002.height = 140.0, 100.0
            math_003.width, math_003.height = 140.0, 100.0
            position.width, position.height = 140.0, 100.0
            group_output.width, group_output.height = 140.0, 100.0
            group_input.width, group_input.height = 140.0, 100.0
            mix.width, mix.height = 140.0, 100.0
            mix_001.width, mix_001.height = 140.0, 100.0
            mix_002.width, mix_002.height = 140.0, 100.0
            bounding_box.width, bounding_box.height = 140.0, 100.0
            vector_math_004.width, vector_math_004.height = 140.0, 100.0
            reroute.width, reroute.height = 100.0, 100.0
            separate_xyz.width, separate_xyz.height = 140.0, 100.0
            compare.width, compare.height = 140.0, 100.0
            math_004.width, math_004.height = 140.0, 100.0
            reroute_001.width, reroute_001.height = 100.0, 100.0
            separate_xyz_001.width, separate_xyz_001.height = 140.0, 100.0
            compare_001.width, compare_001.height = 140.0, 100.0
            math_007.width, math_007.height = 140.0, 100.0
            math_008.width, math_008.height = 140.0, 100.0
            math_009.width, math_009.height = 140.0, 100.0
            position_001.width, position_001.height = 140.0, 100.0
            vertex_of_corner.width, vertex_of_corner.height = 140.0, 100.0
            vertex_of_corner_001.width, vertex_of_corner_001.height = 140.0, 100.0
            corners_of_face_001.width, corners_of_face_001.height = 140.0, 100.0
            vertex_of_corner_002.width, vertex_of_corner_002.height = 140.0, 100.0
            corners_of_face_002.width, corners_of_face_002.height = 140.0, 100.0
            vertex_of_corner_003.width, vertex_of_corner_003.height = 140.0, 100.0
            sample_index_002.width, sample_index_002.height = 140.0, 100.0
            sample_index_005.width, sample_index_005.height = 140.0, 100.0
            sample_index_004.width, sample_index_004.height = 140.0, 100.0
            sample_index_007.width, sample_index_007.height = 140.0, 100.0
            sample_index_001.width, sample_index_001.height = 140.0, 100.0
            sample_index_003.width, sample_index_003.height = 140.0, 100.0
            sample_index_008.width, sample_index_008.height = 140.0, 100.0
            sample_index_006.width, sample_index_006.height = 140.0, 100.0
            corners_of_face_003.width, corners_of_face_003.height = 140.0, 100.0
            corners_of_face.width, corners_of_face.height = 140.0, 100.0
            index.width, index.height = 140.0, 100.0
            
            #initialize match_bounding_box links
            #mix.Result -> mix_002.A
            match_bounding_box.links.new(mix.outputs[1], mix_002.inputs[4])
            #mix_001.Result -> mix_002.B
            match_bounding_box.links.new(mix_001.outputs[1], mix_002.inputs[5])
            #position.Position -> vector_math_001.Vector
            match_bounding_box.links.new(position.outputs[0], vector_math_001.inputs[0])
            #vector_math_001.Vector -> vector_math.Vector
            match_bounding_box.links.new(vector_math_001.outputs[0], vector_math.inputs[0])
            #math.Value -> math_001.Value
            match_bounding_box.links.new(math.outputs[0], math_001.inputs[0])
            #math_002.Value -> math_003.Value
            match_bounding_box.links.new(math_002.outputs[0], math_003.inputs[0])
            #mix_002.Result -> group_output.Vector
            match_bounding_box.links.new(mix_002.outputs[1], group_output.inputs[0])
            #bounding_box.Max -> vector_math_004.Vector
            match_bounding_box.links.new(bounding_box.outputs[2], vector_math_004.inputs[0])
            #bounding_box.Min -> vector_math_004.Vector
            match_bounding_box.links.new(bounding_box.outputs[1], vector_math_004.inputs[1])
            #bounding_box.Min -> vector_math_001.Vector
            match_bounding_box.links.new(bounding_box.outputs[1], vector_math_001.inputs[1])
            #vector_math_004.Vector -> vector_math.Vector
            match_bounding_box.links.new(vector_math_004.outputs[0], vector_math.inputs[1])
            #group_input.Target -> bounding_box.Geometry
            match_bounding_box.links.new(group_input.outputs[1], bounding_box.inputs[0])
            #reroute.Output -> compare.A
            match_bounding_box.links.new(reroute.outputs[0], compare.inputs[2])
            #separate_xyz.X -> math_004.Value
            match_bounding_box.links.new(separate_xyz.outputs[0], math_004.inputs[0])
            #compare.Result -> math_004.Value
            match_bounding_box.links.new(compare.outputs[0], math_004.inputs[1])
            #math_001.Value -> reroute.Input
            match_bounding_box.links.new(math_001.outputs[0], reroute.inputs[0])
            #vector_math.Vector -> separate_xyz.Vector
            match_bounding_box.links.new(vector_math.outputs[0], separate_xyz.inputs[0])
            #math_004.Value -> mix.Factor
            match_bounding_box.links.new(math_004.outputs[0], mix.inputs[0])
            #math_004.Value -> mix_001.Factor
            match_bounding_box.links.new(math_004.outputs[0], mix_001.inputs[0])
            #reroute_001.Output -> compare_001.A
            match_bounding_box.links.new(reroute_001.outputs[0], compare_001.inputs[2])
            #reroute_001.Output -> math_008.Value
            match_bounding_box.links.new(reroute_001.outputs[0], math_008.inputs[1])
            #separate_xyz_001.X -> math_007.Value
            match_bounding_box.links.new(separate_xyz_001.outputs[0], math_007.inputs[0])
            #compare_001.Result -> math_007.Value
            match_bounding_box.links.new(compare_001.outputs[0], math_007.inputs[1])
            #separate_xyz_001.Y -> math_008.Value
            match_bounding_box.links.new(separate_xyz_001.outputs[1], math_008.inputs[0])
            #math_007.Value -> math_009.Value
            match_bounding_box.links.new(math_007.outputs[0], math_009.inputs[0])
            #math_008.Value -> math_009.Value
            match_bounding_box.links.new(math_008.outputs[0], math_009.inputs[1])
            #math_003.Value -> reroute_001.Input
            match_bounding_box.links.new(math_003.outputs[0], reroute_001.inputs[0])
            #vector_math.Vector -> separate_xyz_001.Vector
            match_bounding_box.links.new(vector_math.outputs[0], separate_xyz_001.inputs[0])
            #math_009.Value -> mix_002.Factor
            match_bounding_box.links.new(math_009.outputs[0], mix_002.inputs[0])
            #vertex_of_corner_002.Vertex Index -> sample_index_005.Index
            match_bounding_box.links.new(vertex_of_corner_002.outputs[0], sample_index_005.inputs[2])
            #index.Index -> corners_of_face_002.Face Index
            match_bounding_box.links.new(index.outputs[0], corners_of_face_002.inputs[0])
            #vertex_of_corner_001.Vertex Index -> sample_index_004.Index
            match_bounding_box.links.new(vertex_of_corner_001.outputs[0], sample_index_004.inputs[2])
            #sample_index_007.Value -> sample_index_008.Value
            match_bounding_box.links.new(sample_index_007.outputs[0], sample_index_008.inputs[1])
            #vertex_of_corner.Vertex Index -> sample_index_002.Index
            match_bounding_box.links.new(vertex_of_corner.outputs[0], sample_index_002.inputs[2])
            #sample_index_004.Value -> sample_index_003.Value
            match_bounding_box.links.new(sample_index_004.outputs[0], sample_index_003.inputs[1])
            #corners_of_face_003.Corner Index -> vertex_of_corner_003.Corner Index
            match_bounding_box.links.new(corners_of_face_003.outputs[0], vertex_of_corner_003.inputs[0])
            #position_001.Position -> sample_index_005.Value
            match_bounding_box.links.new(position_001.outputs[0], sample_index_005.inputs[1])
            #corners_of_face_001.Corner Index -> vertex_of_corner_001.Corner Index
            match_bounding_box.links.new(corners_of_face_001.outputs[0], vertex_of_corner_001.inputs[0])
            #position_001.Position -> sample_index_002.Value
            match_bounding_box.links.new(position_001.outputs[0], sample_index_002.inputs[1])
            #position_001.Position -> sample_index_004.Value
            match_bounding_box.links.new(position_001.outputs[0], sample_index_004.inputs[1])
            #index.Index -> corners_of_face_003.Face Index
            match_bounding_box.links.new(index.outputs[0], corners_of_face_003.inputs[0])
            #index.Index -> corners_of_face_001.Face Index
            match_bounding_box.links.new(index.outputs[0], corners_of_face_001.inputs[0])
            #vertex_of_corner_003.Vertex Index -> sample_index_007.Index
            match_bounding_box.links.new(vertex_of_corner_003.outputs[0], sample_index_007.inputs[2])
            #sample_index_005.Value -> sample_index_006.Value
            match_bounding_box.links.new(sample_index_005.outputs[0], sample_index_006.inputs[1])
            #corners_of_face_002.Corner Index -> vertex_of_corner_002.Corner Index
            match_bounding_box.links.new(corners_of_face_002.outputs[0], vertex_of_corner_002.inputs[0])
            #index.Index -> corners_of_face.Face Index
            match_bounding_box.links.new(index.outputs[0], corners_of_face.inputs[0])
            #position_001.Position -> sample_index_007.Value
            match_bounding_box.links.new(position_001.outputs[0], sample_index_007.inputs[1])
            #corners_of_face.Corner Index -> vertex_of_corner.Corner Index
            match_bounding_box.links.new(corners_of_face.outputs[0], vertex_of_corner.inputs[0])
            #sample_index_002.Value -> sample_index_001.Value
            match_bounding_box.links.new(sample_index_002.outputs[0], sample_index_001.inputs[1])
            #group_input.Geometry -> sample_index_006.Geometry
            match_bounding_box.links.new(group_input.outputs[0], sample_index_006.inputs[0])
            #group_input.Geometry -> sample_index_002.Geometry
            match_bounding_box.links.new(group_input.outputs[0], sample_index_002.inputs[0])
            #group_input.Geometry -> sample_index_005.Geometry
            match_bounding_box.links.new(group_input.outputs[0], sample_index_005.inputs[0])
            #group_input.Geometry -> sample_index_001.Geometry
            match_bounding_box.links.new(group_input.outputs[0], sample_index_001.inputs[0])
            #group_input.Geometry -> sample_index_007.Geometry
            match_bounding_box.links.new(group_input.outputs[0], sample_index_007.inputs[0])
            #group_input.Geometry -> sample_index_003.Geometry
            match_bounding_box.links.new(group_input.outputs[0], sample_index_003.inputs[0])
            #group_input.Geometry -> sample_index_004.Geometry
            match_bounding_box.links.new(group_input.outputs[0], sample_index_004.inputs[0])
            #group_input.Geometry -> sample_index_008.Geometry
            match_bounding_box.links.new(group_input.outputs[0], sample_index_008.inputs[0])
            #sample_index_001.Value -> mix.A
            match_bounding_box.links.new(sample_index_001.outputs[0], mix.inputs[4])
            #sample_index_003.Value -> mix.B
            match_bounding_box.links.new(sample_index_003.outputs[0], mix.inputs[5])
            #sample_index_008.Value -> mix_001.A
            match_bounding_box.links.new(sample_index_008.outputs[0], mix_001.inputs[4])
            #sample_index_006.Value -> mix_001.B
            match_bounding_box.links.new(sample_index_006.outputs[0], mix_001.inputs[5])
            return match_bounding_box

        def unwrap_in_place_node_group():
            unwrap_in_place = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Unwrap In Place")

            unwrap_in_place.is_modifier = True
            
            #initialize unwrap_in_place nodes
            #unwrap_in_place interface
            #Socket Geometry
            geometry_socket_1 = unwrap_in_place.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
            geometry_socket_1.attribute_domain = 'POINT'
            
            #Socket Geometry
            geometry_socket_2 = unwrap_in_place.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
            geometry_socket_2.attribute_domain = 'POINT'
            
            #Socket UV
            uv_socket = unwrap_in_place.interface.new_socket(name = "UV", in_out='INPUT', socket_type = 'NodeSocketString')
            uv_socket.attribute_domain = 'POINT'
            
            #Socket Seam
            seam_socket = unwrap_in_place.interface.new_socket(name = "Seam", in_out='INPUT', socket_type = 'NodeSocketBool')
            seam_socket.default_attribute_name = "seam_Unwrap_In_Place"
            seam_socket.attribute_domain = 'POINT'
            seam_socket.hide_value = True
            
            #Socket Selection
            selection_socket = unwrap_in_place.interface.new_socket(name = "Selection", in_out='INPUT', socket_type = 'NodeSocketBool')
            selection_socket.default_attribute_name = "UV_Selection_Unwrap_In_Place"
            selection_socket.attribute_domain = 'POINT'
            selection_socket.hide_value = True
            
            #Socket Margin
            margin_socket = unwrap_in_place.interface.new_socket(name = "Margin", in_out='INPUT', socket_type = 'NodeSocketFloat')
            margin_socket.subtype = 'NONE'
            margin_socket.default_value = 0.0010000000474974513
            margin_socket.min_value = 0.0
            margin_socket.max_value = 1.0
            margin_socket.attribute_domain = 'POINT'
            
            #Socket Fill Holes
            fill_holes_socket = unwrap_in_place.interface.new_socket(name = "Fill Holes", in_out='INPUT', socket_type = 'NodeSocketBool')
            fill_holes_socket.attribute_domain = 'POINT'
            
            #Socket Angle Based
            angle_based_socket = unwrap_in_place.interface.new_socket(name = "Angle Based", in_out='INPUT', socket_type = 'NodeSocketBool')
            angle_based_socket.attribute_domain = 'POINT'
            
            
            #node Group Input
            group_input_1 = unwrap_in_place.nodes.new("NodeGroupInput")
            group_input_1.name = "Group Input"
            group_input_1.outputs[3].hide = True
            group_input_1.outputs[4].hide = True
            group_input_1.outputs[5].hide = True
            group_input_1.outputs[6].hide = True
            group_input_1.outputs[7].hide = True
            
            #node Group Output
            group_output_1 = unwrap_in_place.nodes.new("NodeGroupOutput")
            group_output_1.name = "Group Output"
            group_output_1.is_active_output = True
            
            #node Set Position
            set_position = unwrap_in_place.nodes.new("GeometryNodeSetPosition")
            set_position.name = "Set Position"
            #Offset
            set_position.inputs[3].default_value = (0.0, 0.0, 0.0)
            
            #node Named Attribute
            named_attribute = unwrap_in_place.nodes.new("GeometryNodeInputNamedAttribute")
            named_attribute.name = "Named Attribute"
            named_attribute.data_type = 'FLOAT_VECTOR'
            
            #node Position
            position_1 = unwrap_in_place.nodes.new("GeometryNodeInputPosition")
            position_1.name = "Position"
            
            #node Split Edges
            split_edges = unwrap_in_place.nodes.new("GeometryNodeSplitEdges")
            split_edges.name = "Split Edges"
            
            #node Group Input.001
            group_input_001 = unwrap_in_place.nodes.new("NodeGroupInput")
            group_input_001.name = "Group Input.001"
            group_input_001.outputs[0].hide = True
            group_input_001.outputs[1].hide = True
            group_input_001.outputs[2].hide = True
            group_input_001.outputs[4].hide = True
            group_input_001.outputs[5].hide = True
            group_input_001.outputs[6].hide = True
            group_input_001.outputs[7].hide = True
            
            #node Bounding Box
            bounding_box_1 = unwrap_in_place.nodes.new("GeometryNodeBoundBox")
            bounding_box_1.name = "Bounding Box"
            
            #node Store Named Attribute.003
            store_named_attribute_003 = unwrap_in_place.nodes.new("GeometryNodeStoreNamedAttribute")
            store_named_attribute_003.name = "Store Named Attribute.003"
            store_named_attribute_003.data_type = 'FLOAT2'
            store_named_attribute_003.domain = 'CORNER'
            
            #node UV Unwrap.001
            uv_unwrap_001 = unwrap_in_place.nodes.new("GeometryNodeUVUnwrap")
            uv_unwrap_001.name = "UV Unwrap.001"
            uv_unwrap_001.method = 'ANGLE_BASED'
            
            #node Store Named Attribute.004
            store_named_attribute_004 = unwrap_in_place.nodes.new("GeometryNodeStoreNamedAttribute")
            store_named_attribute_004.name = "Store Named Attribute.004"
            store_named_attribute_004.data_type = 'FLOAT2'
            store_named_attribute_004.domain = 'CORNER'
            
            #node Set Position.003
            set_position_003 = unwrap_in_place.nodes.new("GeometryNodeSetPosition")
            set_position_003.name = "Set Position.003"
            #Offset
            set_position_003.inputs[3].default_value = (0.0, 0.0, 0.0)
            
            #node Set Position.001
            set_position_001 = unwrap_in_place.nodes.new("GeometryNodeSetPosition")
            set_position_001.name = "Set Position.001"
            #Offset
            set_position_001.inputs[3].default_value = (0.0, 0.0, 0.0)
            
            #node Named Attribute.005
            named_attribute_005 = unwrap_in_place.nodes.new("GeometryNodeInputNamedAttribute")
            named_attribute_005.name = "Named Attribute.005"
            named_attribute_005.data_type = 'FLOAT_VECTOR'
            
            #node Group Input.002
            group_input_002 = unwrap_in_place.nodes.new("NodeGroupInput")
            group_input_002.name = "Group Input.002"
            group_input_002.outputs[0].hide = True
            group_input_002.outputs[7].hide = True
            
            #node Group.001
            group_001 = unwrap_in_place.nodes.new("GeometryNodeGroup")
            group_001.label = "Match Bounding Box"
            group_001.name = "Group.001"
            group_001.node_tree = match_bounding_box_node_group()

            
            #node Group Input.003
            group_input_003 = unwrap_in_place.nodes.new("NodeGroupInput")
            group_input_003.name = "Group Input.003"
            group_input_003.outputs[0].hide = True
            group_input_003.outputs[1].hide = True
            group_input_003.outputs[2].hide = True
            group_input_003.outputs[4].hide = True
            group_input_003.outputs[5].hide = True
            group_input_003.outputs[6].hide = True
            group_input_003.outputs[7].hide = True
            
            #node Group Input.004
            group_input_004 = unwrap_in_place.nodes.new("NodeGroupInput")
            group_input_004.name = "Group Input.004"
            group_input_004.outputs[0].hide = True
            group_input_004.outputs[2].hide = True
            group_input_004.outputs[4].hide = True
            group_input_004.outputs[5].hide = True
            group_input_004.outputs[6].hide = True
            group_input_004.outputs[7].hide = True
            
            #node Group Input.005
            group_input_005 = unwrap_in_place.nodes.new("NodeGroupInput")
            group_input_005.name = "Group Input.005"
            group_input_005.outputs[2].hide = True
            group_input_005.outputs[4].hide = True
            group_input_005.outputs[5].hide = True
            group_input_005.outputs[6].hide = True
            group_input_005.outputs[7].hide = True
            
            #node Store Named Attribute.006
            store_named_attribute_006 = unwrap_in_place.nodes.new("GeometryNodeStoreNamedAttribute")
            store_named_attribute_006.name = "Store Named Attribute.006"
            store_named_attribute_006.data_type = 'FLOAT2'
            store_named_attribute_006.domain = 'CORNER'
            
            #node Named Attribute.001
            named_attribute_001 = unwrap_in_place.nodes.new("GeometryNodeInputNamedAttribute")
            named_attribute_001.name = "Named Attribute.001"
            named_attribute_001.data_type = 'FLOAT_VECTOR'
            
            #node Sample Index.001
            sample_index_001_1 = unwrap_in_place.nodes.new("GeometryNodeSampleIndex")
            sample_index_001_1.name = "Sample Index.001"
            sample_index_001_1.clamp = False
            sample_index_001_1.data_type = 'FLOAT_VECTOR'
            sample_index_001_1.domain = 'CORNER'
            
            #node Index
            index_1 = unwrap_in_place.nodes.new("GeometryNodeInputIndex")
            index_1.name = "Index"
            
            #node Duplicate Elements
            duplicate_elements = unwrap_in_place.nodes.new("GeometryNodeDuplicateElements")
            duplicate_elements.name = "Duplicate Elements"
            duplicate_elements.domain = 'POINT'
            #Amount
            duplicate_elements.inputs[2].default_value = 1
            
            #node Duplicate Elements.001
            duplicate_elements_001 = unwrap_in_place.nodes.new("GeometryNodeDuplicateElements")
            duplicate_elements_001.name = "Duplicate Elements.001"
            duplicate_elements_001.domain = 'POINT'
            #Amount
            duplicate_elements_001.inputs[2].default_value = 1
            
            #node Capture Attribute
            capture_attribute = unwrap_in_place.nodes.new("GeometryNodeCaptureAttribute")
            capture_attribute.name = "Capture Attribute"
            capture_attribute.data_type = 'FLOAT_VECTOR'
            capture_attribute.domain = 'POINT'
            
            #node Group Input.006
            group_input_006 = unwrap_in_place.nodes.new("NodeGroupInput")
            group_input_006.name = "Group Input.006"
            group_input_006.outputs[0].hide = True
            group_input_006.outputs[2].hide = True
            group_input_006.outputs[3].hide = True
            group_input_006.outputs[4].hide = True
            group_input_006.outputs[5].hide = True
            group_input_006.outputs[6].hide = True
            group_input_006.outputs[7].hide = True
            
            #node Switch
            switch = unwrap_in_place.nodes.new("GeometryNodeSwitch")
            switch.name = "Switch"
            switch.input_type = 'VECTOR'
            
            #node UV Unwrap.002
            uv_unwrap_002 = unwrap_in_place.nodes.new("GeometryNodeUVUnwrap")
            uv_unwrap_002.name = "UV Unwrap.002"
            uv_unwrap_002.method = 'CONFORMAL'
            
            #node Group Input.007
            group_input_007 = unwrap_in_place.nodes.new("NodeGroupInput")
            group_input_007.name = "Group Input.007"
            group_input_007.outputs[0].hide = True
            group_input_007.outputs[2].hide = True
            group_input_007.outputs[3].hide = True
            group_input_007.outputs[4].hide = True
            group_input_007.outputs[5].hide = True
            group_input_007.outputs[6].hide = True
            group_input_007.outputs[7].hide = True
            
            #node Remove Named Attribute
            remove_named_attribute = unwrap_in_place.nodes.new("GeometryNodeRemoveAttribute")
            remove_named_attribute.name = "Remove Named Attribute"
            #Name
            remove_named_attribute.inputs[1].default_value = "UV_Selection_Unwrap_In_Place"
            
            #node Remove Named Attribute.001
            remove_named_attribute_001 = unwrap_in_place.nodes.new("GeometryNodeRemoveAttribute")
            remove_named_attribute_001.name = "Remove Named Attribute.001"
            #Name
            remove_named_attribute_001.inputs[1].default_value = "seam_Unwrap_In_Place"
            
            
            
            
            #Set locations
            group_input_1.location = (-800.7864379882812, 35.97612380981445)
            group_output_1.location = (4099.57080078125, 477.5541076660156)
            set_position.location = (214.8248291015625, 100.59524536132812)
            named_attribute.location = (-501.1990051269531, -48.008819580078125)
            position_1.location = (-502.5131530761719, 18.43531036376953)
            split_edges.location = (-96.95872497558594, 102.62326049804688)
            group_input_001.location = (1665.4072265625, -97.56024169921875)
            bounding_box_1.location = (650.4869995117188, 218.11727905273438)
            store_named_attribute_003.location = (1321.702880859375, 64.28227996826172)
            uv_unwrap_001.location = (687.408935546875, -168.5223388671875)
            store_named_attribute_004.location = (2545.86767578125, 203.36032104492188)
            set_position_003.location = (991.2513427734375, 3.479095458984375)
            set_position_001.location = (1640.371337890625, 197.32843017578125)
            named_attribute_005.location = (1165.9384765625, 229.28451538085938)
            group_input_002.location = (457.1207275390625, -139.79605102539062)
            group_001.location = (2039.508544921875, 121.41050720214844)
            group_input_003.location = (44.42805480957031, -118.64273834228516)
            group_input_004.location = (2284.73046875, 75.13125610351562)
            group_input_005.location = (3044.12744140625, 401.8300476074219)
            store_named_attribute_006.location = (3362.724853515625, 451.0467224121094)
            named_attribute_001.location = (2945.66357421875, 292.0354309082031)
            sample_index_001_1.location = (3136.79248046875, 300.9219970703125)
            index_1.location = (2951.22607421875, 152.07904052734375)
            duplicate_elements.location = (424.14581298828125, 157.6721649169922)
            duplicate_elements_001.location = (1877.373291015625, -8.011474609375)
            capture_attribute.location = (-329.465576171875, 159.68740844726562)
            group_input_006.location = (988.124267578125, 157.46710205078125)
            switch.location = (952.72705078125, -221.255859375)
            uv_unwrap_002.location = (696.1859130859375, -342.7801208496094)
            group_input_007.location = (2735.8798828125, 252.25604248046875)
            remove_named_attribute.location = (3599.944091796875, 464.0772705078125)
            remove_named_attribute_001.location = (3849.999755859375, 470.94342041015625)
            
            #Set dimensions
            group_input_1.width, group_input_1.height = 140.0, 100.0
            group_output_1.width, group_output_1.height = 140.0, 100.0
            set_position.width, set_position.height = 140.0, 100.0
            named_attribute.width, named_attribute.height = 140.0, 100.0
            position_1.width, position_1.height = 140.0, 100.0
            split_edges.width, split_edges.height = 140.0, 100.0
            group_input_001.width, group_input_001.height = 140.0, 100.0
            bounding_box_1.width, bounding_box_1.height = 140.0, 100.0
            store_named_attribute_003.width, store_named_attribute_003.height = 140.0, 100.0
            uv_unwrap_001.width, uv_unwrap_001.height = 140.0, 100.0
            store_named_attribute_004.width, store_named_attribute_004.height = 140.0, 100.0
            set_position_003.width, set_position_003.height = 140.0, 100.0
            set_position_001.width, set_position_001.height = 140.0, 100.0
            named_attribute_005.width, named_attribute_005.height = 140.0, 100.0
            group_input_002.width, group_input_002.height = 140.0, 100.0
            group_001.width, group_001.height = 189.59912109375, 100.0
            group_input_003.width, group_input_003.height = 140.0, 100.0
            group_input_004.width, group_input_004.height = 140.0, 100.0
            group_input_005.width, group_input_005.height = 140.0, 100.0
            store_named_attribute_006.width, store_named_attribute_006.height = 140.0, 100.0
            named_attribute_001.width, named_attribute_001.height = 140.0, 100.0
            sample_index_001_1.width, sample_index_001_1.height = 140.0, 100.0
            index_1.width, index_1.height = 140.0, 100.0
            duplicate_elements.width, duplicate_elements.height = 140.0, 100.0
            duplicate_elements_001.width, duplicate_elements_001.height = 140.0, 100.0
            capture_attribute.width, capture_attribute.height = 140.0, 100.0
            group_input_006.width, group_input_006.height = 140.0, 100.0
            switch.width, switch.height = 140.0, 100.0
            uv_unwrap_002.width, uv_unwrap_002.height = 140.0, 100.0
            group_input_007.width, group_input_007.height = 140.0, 100.0
            remove_named_attribute.width, remove_named_attribute.height = 170.0, 100.0
            remove_named_attribute_001.width, remove_named_attribute_001.height = 170.0, 100.0
            
            #initialize unwrap_in_place links
            #named_attribute.Attribute -> set_position.Position
            unwrap_in_place.links.new(named_attribute.outputs[0], set_position.inputs[2])
            #group_input_1.UV -> named_attribute.Name
            unwrap_in_place.links.new(group_input_1.outputs[1], named_attribute.inputs[0])
            #group_input_1.Seam -> split_edges.Selection
            unwrap_in_place.links.new(group_input_1.outputs[2], split_edges.inputs[1])
            #split_edges.Mesh -> set_position.Geometry
            unwrap_in_place.links.new(split_edges.outputs[0], set_position.inputs[0])
            #set_position.Geometry -> set_position_003.Geometry
            unwrap_in_place.links.new(set_position.outputs[0], set_position_003.inputs[0])
            #set_position_003.Geometry -> store_named_attribute_003.Geometry
            unwrap_in_place.links.new(set_position_003.outputs[0], store_named_attribute_003.inputs[0])
            #store_named_attribute_003.Geometry -> set_position_001.Geometry
            unwrap_in_place.links.new(store_named_attribute_003.outputs[0], set_position_001.inputs[0])
            #named_attribute_005.Attribute -> set_position_001.Position
            unwrap_in_place.links.new(named_attribute_005.outputs[0], set_position_001.inputs[2])
            #group_input_002.Selection -> store_named_attribute_003.Selection
            unwrap_in_place.links.new(group_input_002.outputs[3], store_named_attribute_003.inputs[1])
            #group_input_002.Selection -> set_position_003.Selection
            unwrap_in_place.links.new(group_input_002.outputs[3], set_position_003.inputs[1])
            #group_input_002.Selection -> set_position_001.Selection
            unwrap_in_place.links.new(group_input_002.outputs[3], set_position_001.inputs[1])
            #bounding_box_1.Bounding Box -> group_001.Geometry
            unwrap_in_place.links.new(bounding_box_1.outputs[0], group_001.inputs[0])
            #group_input_003.Selection -> set_position.Selection
            unwrap_in_place.links.new(group_input_003.outputs[3], set_position.inputs[1])
            #group_input_004.Selection -> store_named_attribute_004.Selection
            unwrap_in_place.links.new(group_input_004.outputs[3], store_named_attribute_004.inputs[1])
            #set_position_001.Geometry -> store_named_attribute_004.Geometry
            unwrap_in_place.links.new(set_position_001.outputs[0], store_named_attribute_004.inputs[0])
            #group_input_002.Selection -> uv_unwrap_001.Selection
            unwrap_in_place.links.new(group_input_002.outputs[3], uv_unwrap_001.inputs[0])
            #group_input_002.Seam -> uv_unwrap_001.Seam
            unwrap_in_place.links.new(group_input_002.outputs[2], uv_unwrap_001.inputs[1])
            #remove_named_attribute_001.Geometry -> group_output_1.Geometry
            unwrap_in_place.links.new(remove_named_attribute_001.outputs[0], group_output_1.inputs[0])
            #named_attribute_001.Attribute -> sample_index_001_1.Value
            unwrap_in_place.links.new(named_attribute_001.outputs[0], sample_index_001_1.inputs[1])
            #capture_attribute.Geometry -> split_edges.Mesh
            unwrap_in_place.links.new(capture_attribute.outputs[0], split_edges.inputs[0])
            #sample_index_001_1.Value -> store_named_attribute_006.Value
            unwrap_in_place.links.new(sample_index_001_1.outputs[0], store_named_attribute_006.inputs[3])
            #store_named_attribute_004.Geometry -> sample_index_001_1.Geometry
            unwrap_in_place.links.new(store_named_attribute_004.outputs[0], sample_index_001_1.inputs[0])
            #group_input_005.Geometry -> store_named_attribute_006.Geometry
            unwrap_in_place.links.new(group_input_005.outputs[0], store_named_attribute_006.inputs[0])
            #index_1.Index -> sample_index_001_1.Index
            unwrap_in_place.links.new(index_1.outputs[0], sample_index_001_1.inputs[2])
            #set_position.Geometry -> duplicate_elements.Geometry
            unwrap_in_place.links.new(set_position.outputs[0], duplicate_elements.inputs[0])
            #group_input_003.Selection -> duplicate_elements.Selection
            unwrap_in_place.links.new(group_input_003.outputs[3], duplicate_elements.inputs[1])
            #duplicate_elements.Geometry -> bounding_box_1.Geometry
            unwrap_in_place.links.new(duplicate_elements.outputs[0], bounding_box_1.inputs[0])
            #group_001.Vector -> store_named_attribute_004.Value
            unwrap_in_place.links.new(group_001.outputs[0], store_named_attribute_004.inputs[3])
            #set_position_001.Geometry -> duplicate_elements_001.Geometry
            unwrap_in_place.links.new(set_position_001.outputs[0], duplicate_elements_001.inputs[0])
            #group_input_001.Selection -> duplicate_elements_001.Selection
            unwrap_in_place.links.new(group_input_001.outputs[3], duplicate_elements_001.inputs[1])
            #duplicate_elements_001.Geometry -> group_001.Target
            unwrap_in_place.links.new(duplicate_elements_001.outputs[0], group_001.inputs[1])
            #group_input_005.Selection -> store_named_attribute_006.Selection
            unwrap_in_place.links.new(group_input_005.outputs[3], store_named_attribute_006.inputs[1])
            #group_input_1.Geometry -> capture_attribute.Geometry
            unwrap_in_place.links.new(group_input_1.outputs[0], capture_attribute.inputs[0])
            #position_1.Position -> capture_attribute.Value
            unwrap_in_place.links.new(position_1.outputs[0], capture_attribute.inputs[1])
            #capture_attribute.Attribute -> set_position_003.Position
            unwrap_in_place.links.new(capture_attribute.outputs[1], set_position_003.inputs[2])
            #group_input_002.Margin -> uv_unwrap_001.Margin
            unwrap_in_place.links.new(group_input_002.outputs[4], uv_unwrap_001.inputs[2])
            #group_input_002.Fill Holes -> uv_unwrap_001.Fill Holes
            unwrap_in_place.links.new(group_input_002.outputs[5], uv_unwrap_001.inputs[3])
            #group_input_006.UV -> named_attribute_005.Name
            unwrap_in_place.links.new(group_input_006.outputs[1], named_attribute_005.inputs[0])
            #uv_unwrap_001.UV -> switch.True
            unwrap_in_place.links.new(uv_unwrap_001.outputs[0], switch.inputs[2])
            #group_input_002.Selection -> uv_unwrap_002.Selection
            unwrap_in_place.links.new(group_input_002.outputs[3], uv_unwrap_002.inputs[0])
            #group_input_002.Seam -> uv_unwrap_002.Seam
            unwrap_in_place.links.new(group_input_002.outputs[2], uv_unwrap_002.inputs[1])
            #group_input_002.Margin -> uv_unwrap_002.Margin
            unwrap_in_place.links.new(group_input_002.outputs[4], uv_unwrap_002.inputs[2])
            #group_input_002.Fill Holes -> uv_unwrap_002.Fill Holes
            unwrap_in_place.links.new(group_input_002.outputs[5], uv_unwrap_002.inputs[3])
            #uv_unwrap_002.UV -> switch.False
            unwrap_in_place.links.new(uv_unwrap_002.outputs[0], switch.inputs[1])
            #group_input_002.Angle Based -> switch.Switch
            unwrap_in_place.links.new(group_input_002.outputs[6], switch.inputs[0])
            #switch.Output -> store_named_attribute_003.Value
            unwrap_in_place.links.new(switch.outputs[0], store_named_attribute_003.inputs[3])
            #group_input_004.UV -> store_named_attribute_004.Name
            unwrap_in_place.links.new(group_input_004.outputs[1], store_named_attribute_004.inputs[2])
            #group_input_002.UV -> store_named_attribute_003.Name
            unwrap_in_place.links.new(group_input_002.outputs[1], store_named_attribute_003.inputs[2])
            #group_input_007.UV -> named_attribute_001.Name
            unwrap_in_place.links.new(group_input_007.outputs[1], named_attribute_001.inputs[0])
            #group_input_005.UV -> store_named_attribute_006.Name
            unwrap_in_place.links.new(group_input_005.outputs[1], store_named_attribute_006.inputs[2])
            #store_named_attribute_006.Geometry -> remove_named_attribute.Geometry
            unwrap_in_place.links.new(store_named_attribute_006.outputs[0], remove_named_attribute.inputs[0])
            #remove_named_attribute.Geometry -> remove_named_attribute_001.Geometry
            unwrap_in_place.links.new(remove_named_attribute.outputs[0], remove_named_attribute_001.inputs[0])
            return unwrap_in_place
    
        import time
        total_time = time.time()
        create_unwrap_in_place_node_group_time = time.time()
        if "Unwrap In Place" not in bpy.data.node_groups:
            unwrap_in_place_node_group()
        print("Create Unwrap In Place Node Group Time: ", time.time() - create_unwrap_in_place_node_group_time)

        start_op_time = time.time()

        active_object = bpy.context.active_object
        if active_object.modifiers.active is not None:
            active_modifer_index = active_object.modifiers.find(context.object.modifiers.active.name)

        if bpy.app.version <= (4, 0, 2):
            self.report({'WARNING'}, "This operator is not supported in Blender 4.0.2 or lower due to a bug in the Geometry Nodes")
        else:
            print("Start Operator Time: ", time.time() - start_op_time)
            cheack_time = time.time()
            has_toggled = False
            has_synced = False
            angle_based = False

            if self.uv_unwrap_method == 'ANGLE_BASED':
                angle_based = True
            print("Check Time: ", time.time() - cheack_time)

            pre_prep_selection_time = time.time()
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
                for obj in bpy.context.selected_objects:
                    if obj.type == 'MESH':
                        context.view_layer.objects.active = obj
                        obj.data.attributes.new(name='Currently_Visiable_Faces', type='BOOLEAN', domain='FACE')
                        obj.data.attributes.active = obj.data.attributes.get('Currently_Visiable_Faces')
                        obj.data.update()
                        bpy.ops.mesh.attribute_set(value_bool=True)
                
                has_synced = True
                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
                bpy.ops.uv.hide(unselected=True)

            print("Prep Selection Time: ", time.time() - pre_prep_selection_time)
            
            add_modifier_time = time.time()
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    context.view_layer.objects.active = obj
                    modifier_toggle_visability_based()        

                    if obj.data.total_vert_sel > 0:
                        if "Unwrap In Place" not in obj.modifiers:
                            obj.modifiers.new(name = "Unwrap In Place", type = 'NODES')
                            obj.modifiers["Unwrap In Place"].node_group = bpy.data.node_groups["Unwrap In Place"]
                            obj.modifiers["Unwrap In Place"].show_viewport = False
                                            
                            get_active_uv_layer = obj.data.uv_layers.active         

                            context.object.modifiers["Unwrap In Place"]["Socket_2"] = get_active_uv_layer.name

                            context.object.modifiers["Unwrap In Place"]["Socket_5"] = self.margin
                            context.object.modifiers["Unwrap In Place"]["Socket_6"] = self.fill_holes
                            context.object.modifiers["Unwrap In Place"]["Socket_7"] = angle_based

                            context.object.modifiers["Unwrap In Place"]["Socket_4_attribute_name"] = "UV_Selection_Unwrap_In_Place"
            print("Add Modifier Time: ", time.time() - add_modifier_time)

            switch_to_object_mode_time = time.time()
            if context.mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='OBJECT')

                for obj in bpy.context.selected_objects:
                    if "Unwrap In Place" in obj.modifiers:
                        obj.data.attributes.new(name='seam_Unwrap_In_Place', type='BOOLEAN', domain='EDGE')
                        seam = obj.data.attributes.get('seam_Unwrap_In_Place')
                        seam.data.foreach_set('value', [e.use_seam for e in obj.data.edges])
             
                        obj.data.attributes.new(name='UV_Selection_Unwrap_In_Place', type='BOOLEAN', domain='FACE')
                        selection = obj.data.attributes.get('UV_Selection_Unwrap_In_Place')
                        selection.data.foreach_set('value', [f.select for f in obj.data.polygons])
                        obj.data.update()
                    
                has_toggled = True
                #if self.apply_modifier:
                for obj in bpy.context.selected_objects:
                    if "Unwrap In Place" in obj.modifiers:
                        context.view_layer.objects.active = obj 
                        bpy.ops.object.modifier_apply(modifier="Unwrap In Place")
            print("Switch To Object Mode Time: ", time.time() - switch_to_object_mode_time)


            edit_mode_time = time.time()
            if has_toggled:
                bpy.ops.object.mode_set(mode='EDIT')  
                bpy.ops.uv.average_islands_scale(scale_uv=True, shear=False)
                if self.pack_uv_islands:
                    bpy.ops.uv.pack_islands(udim_source='ORIGINAL_AABB', margin=self.margin, shape_method='AABB', rotate_method= self.rotation_method, rotate=self.rotate)
            if has_synced:
                bpy.context.scene.tool_settings.use_uv_select_sync = False
            print("Edit Mode Time: ", time.time() - edit_mode_time)

            retsore_modifier_visibility_time = time.time()
            #restore modifier visibility from current modifier visibility list depending on the object name and the modifier name
            for obj in bpy.context.selected_objects:
                context.view_layer.objects.active = obj
                modifier_toggle_visability_based()         
            print("Restore Modifier Visibility Time: ", time.time() - retsore_modifier_visibility_time)

            restore_selection_time = time.time()
            if has_synced:
                for obj in bpy.context.selected_objects:
                    if obj.type == 'MESH':
                        context.view_layer.objects.active = obj
                        obj.data.attributes.active = obj.data.attributes.get('Currently_Visiable_Faces')
                        bpy.ops.mesh.select_by_attribute()
                        obj.data.attributes.remove(obj.data.attributes.get('Currently_Visiable_Faces'))
                print("Restore Selection Time: ", time.time() - restore_selection_time)

        #restore active modifier
        if active_object is not None and 'active_modifer_index' in locals():
            active_object.modifiers.active = active_object.modifiers[active_modifer_index]

        print("Total Time: ", time.time() - total_time)
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
                    if bpy.app.version > (4, 1, 0):
                        obj.data.auto_smooth_angle = 3.141590118408203
                        obj.data.use_auto_smooth = True
                    else:
                        for m in obj.modifiers:
                            if "Auto Smooth" in m.name and m.show_viewport:
                                context.object.modifiers[m.name].show_viewport = False
                            if "Smooth by Angle" in [m.name for m in obj.modifiers]:
                                context.object.modifiers[m.name].show_viewport = False
                                    
        elif bpy.context.mode == 'OBJECT':
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    if bpy.app.version > (4, 1, 0):
                        bpy.ops.object.shade_smooth(use_auto_smooth=True, auto_smooth_angle=3.14159, ignore_sharp=False)
                    else:
                        for m in obj.modifiers:
                            if "Auto Smooth" in m.name and m.show_viewport:
                                context.object.modifiers[m.name].show_viewport = False
                            if "Smooth by Angle" in [m.name for m in obj.modifiers]:
                                context.object.modifiers[m.name].show_viewport = False
        return {'FINISHED'}

class OrientIslandToEdge(bpy.types.Operator):
    bl_description = "Orient Island to Edge"
    bl_idname = "keyops.orient_island_to_edge"
    bl_label = "Orient Island to Edge"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if bpy.context.scene.tool_settings.use_uv_select_sync:
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
            bpy.ops.uv.keyops_smart_uv_sync()
            bpy.ops.uv.select_more()
            bpy.ops.uv.select_less()
            bpy.ops.uv.align_rotation(method='EDGE')
            bpy.ops.uv.keyops_smart_uv_sync()
        else:
            bpy.ops.uv.align_rotation(method='EDGE')
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
            bpy.ops.uv.keyops_smart_uv_sync()
            bpy.ops.uv.unwrap(method=self.method, margin=0.001, correct_aspect=self.corret_aspect, use_subsurf_data=self.use_subsurf_data, fill_holes=self.fill_holes)
            bpy.ops.uv.keyops_smart_uv_sync()
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
            bpy.ops.uv.keyops_smart_uv_sync()
            bpy.context.scene.tool_settings.use_uv_select_sync = False

        return {'FINISHED'}

class UVEDITORSMARTUVSYNC_PT_Panel(bpy.types.Panel):
    prefs = get_keyops_prefs()
    category_name = prefs.uv_tools_panel_name
    bl_label = "Key Ops: Toolkit - UV Tools"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = category_name

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' or context.mode == 'OBJECT'
    
    def draw(self, context):
        layout = self.layout
        row = layout.split(factor=0.65, align=True)

        row.scale_y = 1.5
        row.operator("uv.keyops_smart_uv_sync", text="Smart UV Sync", icon='UV_SYNC_SELECT')
        row.prop(context.scene, "smart_uv_sync_enable", toggle=True, text="Enable")

        #uv islands    
        row = layout.row()
        row.label(text="UV Islands")
        row = layout.row(align=True)
        row.operator("uv.keyops_isolate_uv_island", text="Isolate UV")
        row.operator("uv.reveal", text="Unhide UV")
        row = layout.row()
        row.operator("keyops.sharp_from_uv_islands", text="Sharp Edges From UV Islands")
        row = layout.row()
        row.operator("uv.seams_from_islands", text="Seams from UV Islands")

        #unwrap
        def draw_unwrap(self, context):
            row = layout.separator()
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
        row.operator("uv.mark_seam", icon='EDGESEL', text="Mark Seam").clear = False
        row.operator("uv.mark_seam", icon='X', text="Clear Seam").clear = True
        row = layout.row(align=True)
        if bpy.app.version >= (4, 1, 0):
            icon_uv_cut = 'AREA_SWAP'
            icon_stitch = 'AREA_JOIN'
        else:
            icon_uv_cut = 'UV_EDGESEL'
            icon_stitch = 'UV_FACESEL'
        row.operator("uv.keyops_uv_cut", icon=icon_uv_cut, text="UV Cut")
        row.operator("uv.stitch", icon=icon_stitch, text="UV Stitch")
        row = layout.row()
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

        #align
        row = layout.separator()
        row = layout.row()
        row.label(text="Align")
        row = layout.row(align=False)
        row.operator("keyops.orient_island_to_edge", text="Orient Island to Edge")


