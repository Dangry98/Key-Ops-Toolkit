import bpy
from ..utils.utilities import BLENDER_VERSION

def offset_uv_node_group():
	offset_uv = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Offset UV")

	offset_uv.color_tag = 'NONE'
	offset_uv.description = ""

	offset_uv.is_modifier = True
	
	#offset_uv interface
	#Socket Geometry
	geometry_socket = offset_uv.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
	geometry_socket.attribute_domain = 'POINT'
	
	#Socket Geometry
	geometry_socket_1 = offset_uv.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
	geometry_socket_1.attribute_domain = 'POINT'
	
	#Socket Selection
	selection_socket = offset_uv.interface.new_socket(name = "Selection", in_out='INPUT', socket_type = 'NodeSocketBool')
	selection_socket.default_value = False
	selection_socket.attribute_domain = 'POINT'
	selection_socket.hide_value = True
	
	#Socket Offset UV X
	offset_uv_x_socket = offset_uv.interface.new_socket(name = "Offset UV X", in_out='INPUT', socket_type = 'NodeSocketFloat')
	offset_uv_x_socket.default_value = 1.0
	offset_uv_x_socket.min_value = -10000.0
	offset_uv_x_socket.max_value = 10000.0
	offset_uv_x_socket.subtype = 'NONE'
	offset_uv_x_socket.attribute_domain = 'POINT'
	
	#Socket Offset UV Y
	offset_uv_y_socket = offset_uv.interface.new_socket(name = "Offset UV Y", in_out='INPUT', socket_type = 'NodeSocketFloat')
	offset_uv_y_socket.default_value = 0.0
	offset_uv_y_socket.min_value = -10000.0
	offset_uv_y_socket.max_value = 10000.0
	offset_uv_y_socket.subtype = 'NONE'
	offset_uv_y_socket.attribute_domain = 'POINT'
	
	#Socket UV Name
	uv_name_socket = offset_uv.interface.new_socket(name = "UV Name", in_out='INPUT', socket_type = 'NodeSocketString')
	uv_name_socket.default_value = "UVMap"
	uv_name_socket.attribute_domain = 'POINT'
	
	
	#initialize offset_uv nodes
	#node Named Attribute
	named_attribute = offset_uv.nodes.new("GeometryNodeInputNamedAttribute")
	named_attribute.name = "Named Attribute"
	named_attribute.data_type = 'FLOAT_VECTOR'
	
	#node Vector Math
	vector_math = offset_uv.nodes.new("ShaderNodeVectorMath")
	vector_math.name = "Vector Math"
	vector_math.operation = 'ADD'
	
	#node Combine XYZ
	combine_xyz = offset_uv.nodes.new("ShaderNodeCombineXYZ")
	combine_xyz.name = "Combine XYZ"
	#Z
	combine_xyz.inputs[2].default_value = 0.0
	
	#node Store Named Attribute
	store_named_attribute = offset_uv.nodes.new("GeometryNodeStoreNamedAttribute")
	store_named_attribute.name = "Store Named Attribute"
	store_named_attribute.data_type = 'FLOAT2'
	store_named_attribute.domain = 'CORNER'
	
	#node Group Output
	group_output = offset_uv.nodes.new("NodeGroupOutput")
	group_output.name = "Group Output"
	group_output.is_active_output = True
	
	#node Group Input
	group_input = offset_uv.nodes.new("NodeGroupInput")
	group_input.name = "Group Input"
	
	
	
	
	#Set locations
	named_attribute.location = (-200.4461669921875, -366.95660400390625)
	vector_math.location = (10.429038047790527, -312.1781005859375)
	combine_xyz.location = (-190.34738159179688, -165.83035278320312)
	store_named_attribute.location = (228.44163513183594, -150.38143920898438)
	group_output.location = (419.38494873046875, -153.27713012695312)
	group_input.location = (-503.3841552734375, -143.69046020507812)
	
	#Set dimensions
	named_attribute.width, named_attribute.height = 140.0, 100.0
	vector_math.width, vector_math.height = 140.0, 100.0
	combine_xyz.width, combine_xyz.height = 140.0, 100.0
	store_named_attribute.width, store_named_attribute.height = 140.0, 100.0
	group_output.width, group_output.height = 140.0, 100.0
	group_input.width, group_input.height = 140.0, 100.0
	
	#initialize offset_uv links
	#store_named_attribute.Geometry -> group_output.Geometry
	offset_uv.links.new(store_named_attribute.outputs[0], group_output.inputs[0])
	#group_input.Geometry -> store_named_attribute.Geometry
	offset_uv.links.new(group_input.outputs[0], store_named_attribute.inputs[0])
	#named_attribute.Attribute -> vector_math.Vector
	offset_uv.links.new(named_attribute.outputs[0], vector_math.inputs[0])
	#vector_math.Vector -> store_named_attribute.Value
	offset_uv.links.new(vector_math.outputs[0], store_named_attribute.inputs[3])
	#group_input.Selection -> store_named_attribute.Selection
	offset_uv.links.new(group_input.outputs[1], store_named_attribute.inputs[1])
	#combine_xyz.Vector -> vector_math.Vector
	offset_uv.links.new(combine_xyz.outputs[0], vector_math.inputs[1])
	#group_input.Offset UV X -> combine_xyz.X
	offset_uv.links.new(group_input.outputs[2], combine_xyz.inputs[0])
	#group_input.Offset UV Y -> combine_xyz.Y
	offset_uv.links.new(group_input.outputs[3], combine_xyz.inputs[1])
	#group_input.UV Name -> named_attribute.Name
	offset_uv.links.new(group_input.outputs[4], named_attribute.inputs[0])
	#group_input.UV Name -> store_named_attribute.Name
	offset_uv.links.new(group_input.outputs[4], store_named_attribute.inputs[2])
	return offset_uv

def triplanar_uv_mapping_node_group():
    triplanar_uv_mapping = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Triplanar UV Mapping")

    triplanar_uv_mapping.color_tag = 'NONE'
    triplanar_uv_mapping.description = ""

    triplanar_uv_mapping.is_modifier = True

    #triplanar_uv_mapping interface
    #Socket Geometry
    geometry_socket = triplanar_uv_mapping.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'

    #Socket Geometry
    geometry_socket_1 = triplanar_uv_mapping.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket_1.attribute_domain = 'POINT'

    #Socket Selection
    selection_socket = triplanar_uv_mapping.interface.new_socket(name = "Selection", in_out='INPUT', socket_type = 'NodeSocketBool')
    selection_socket.default_value = False
    selection_socket.attribute_domain = 'POINT'
    selection_socket.hide_value = True

    #Socket Name
    name_socket = triplanar_uv_mapping.interface.new_socket(name = "Name", in_out='INPUT', socket_type = 'NodeSocketString')
    name_socket.default_value = ""
    # name_socket.subtype = 'NONE'
    name_socket.attribute_domain = 'POINT'

    #Panel Offset
    offset_panel = triplanar_uv_mapping.interface.new_panel("Offset")
    #Socket World Offset
    world_offset_socket = triplanar_uv_mapping.interface.new_socket(name = "World Offset", in_out='INPUT', socket_type = 'NodeSocketBool', parent = offset_panel)
    world_offset_socket.default_value = False
    world_offset_socket.attribute_domain = 'POINT'

    #Socket Offset Y
    offset_y_socket = triplanar_uv_mapping.interface.new_socket(name = "Offset Y", in_out='INPUT', socket_type = 'NodeSocketFloat', parent = offset_panel)
    offset_y_socket.default_value = 0.5
    offset_y_socket.min_value = -10000.0
    offset_y_socket.max_value = 10000.0
    # offset_y_socket.subtype = 'NONE'
    offset_y_socket.attribute_domain = 'POINT'

    #Socket Offset X
    offset_x_socket = triplanar_uv_mapping.interface.new_socket(name = "Offset X", in_out='INPUT', socket_type = 'NodeSocketFloat', parent = offset_panel)
    offset_x_socket.default_value = 0.5
    offset_x_socket.min_value = -10000.0
    offset_x_socket.max_value = 10000.0
    # offset_x_socket.subtype = 'NONE'
    offset_x_socket.attribute_domain = 'POINT'


    #Panel Scale
    scale_panel = triplanar_uv_mapping.interface.new_panel("Scale")
    #Socket World Scale
    world_scale_socket = triplanar_uv_mapping.interface.new_socket(name = "World Scale", in_out='INPUT', socket_type = 'NodeSocketBool', parent = scale_panel)
    world_scale_socket.default_value = False
    world_scale_socket.attribute_domain = 'POINT'

    #Socket Scale
    scale_socket = triplanar_uv_mapping.interface.new_socket(name = "Scale", in_out='INPUT', socket_type = 'NodeSocketFloat', parent = scale_panel)
    scale_socket.default_value = 0.5
    scale_socket.min_value = 0.0
    scale_socket.max_value = 10000.0
    scale_socket.subtype = 'DISTANCE'
    scale_socket.attribute_domain = 'POINT'


    #Panel Rotation
    rotation_panel = triplanar_uv_mapping.interface.new_panel("Rotation")
    #Socket World Rotation
    world_rotation_socket = triplanar_uv_mapping.interface.new_socket(name = "World Rotation", in_out='INPUT', socket_type = 'NodeSocketBool', parent = rotation_panel)
    world_rotation_socket.default_value = False
    world_rotation_socket.attribute_domain = 'POINT'
    world_rotation_socket.hide_in_modifier = True

    #Socket Angle
    angle_socket = triplanar_uv_mapping.interface.new_socket(name = "Angle", in_out='INPUT', socket_type = 'NodeSocketFloat', parent = rotation_panel)
    angle_socket.default_value = 0.0
    angle_socket.min_value = -360.0
    angle_socket.max_value = 360.0
    angle_socket.subtype = 'ANGLE'
    angle_socket.attribute_domain = 'POINT'



    #initialize triplanar_uv_mapping nodes
    #node Group Input
    group_input = triplanar_uv_mapping.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"
    group_input.outputs[3].hide = True
    group_input.outputs[6].hide = True
    group_input.outputs[7].hide = True
    group_input.outputs[8].hide = True
    group_input.outputs[9].hide = True
    group_input.outputs[10].hide = True

    #node Group Output
    group_output = triplanar_uv_mapping.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True
    group_output.inputs[1].hide = True

    #node Store Named Attribute
    store_named_attribute = triplanar_uv_mapping.nodes.new("GeometryNodeStoreNamedAttribute")
    store_named_attribute.name = "Store Named Attribute"
    store_named_attribute.data_type = 'FLOAT2'
    store_named_attribute.domain = 'CORNER'

    #node Combine XYZ
    combine_xyz = triplanar_uv_mapping.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz.name = "Combine XYZ"
    combine_xyz.inputs[2].hide = True
    #Z
    combine_xyz.inputs[2].default_value = 0.0

    #node Vector Rotate.001
    vector_rotate_001 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorRotate")
    vector_rotate_001.name = "Vector Rotate.001"
    vector_rotate_001.invert = False
    vector_rotate_001.rotation_type = 'AXIS_ANGLE'
    vector_rotate_001.inputs[2].hide = True
    vector_rotate_001.inputs[4].hide = True
    #Axis
    vector_rotate_001.inputs[2].default_value = (0.0, 0.0, 1.0)

    #node Separate XYZ.001
    separate_xyz_001 = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz_001.name = "Separate XYZ.001"

    #node Compare.002
    compare_002 = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
    compare_002.name = "Compare.002"
    compare_002.data_type = 'FLOAT'
    compare_002.mode = 'ELEMENT'
    compare_002.operation = 'GREATER_THAN'

    #node Compare.003
    compare_003 = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
    compare_003.name = "Compare.003"
    compare_003.data_type = 'FLOAT'
    compare_003.mode = 'ELEMENT'
    compare_003.operation = 'GREATER_THAN'

    #node Position
    position = triplanar_uv_mapping.nodes.new("GeometryNodeInputPosition")
    position.name = "Position"

    #node Vector Math
    vector_math = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math.name = "Vector Math"
    vector_math.operation = 'MULTIPLY'

    #node Switch
    switch = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch.name = "Switch"
    switch.input_type = 'VECTOR'
    #True
    switch.inputs[2].default_value = (1.0, 0.0, 1.0)

    #node Switch.001
    switch_001 = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch_001.name = "Switch.001"
    switch_001.input_type = 'VECTOR'
    #False
    switch_001.inputs[1].default_value = (1.0, 1.0, 0.0)
    #True
    switch_001.inputs[2].default_value = (0.0, 1.0, 1.0)

    #node Switch.003
    switch_003 = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch_003.name = "Switch.003"
    switch_003.input_type = 'VECTOR'
    #False
    switch_003.inputs[1].default_value = (0.0, 0.0, 0.0)
    #True
    switch_003.inputs[2].default_value = (0.0, -1.5707999467849731, 0.0)

    #node Switch.002
    switch_002 = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch_002.name = "Switch.002"
    switch_002.input_type = 'VECTOR'
    #True
    switch_002.inputs[2].default_value = (-1.5707999467849731, 0.0, 0.0)

    #node Normal
    normal = triplanar_uv_mapping.nodes.new("GeometryNodeInputNormal")
    normal.name = "Normal"

    #node Vector Math.001
    vector_math_001 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_001.name = "Vector Math.001"
    vector_math_001.operation = 'ABSOLUTE'

    #node Separate XYZ
    separate_xyz = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz.name = "Separate XYZ"

    #node Compare
    compare = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
    compare.name = "Compare"
    compare.data_type = 'FLOAT'
    compare.mode = 'ELEMENT'
    compare.operation = 'GREATER_THAN'

    #node Compare.001
    compare_001 = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
    compare_001.name = "Compare.001"
    compare_001.data_type = 'FLOAT'
    compare_001.mode = 'ELEMENT'
    compare_001.operation = 'GREATER_THAN'

    #node Boolean Math
    boolean_math = triplanar_uv_mapping.nodes.new("FunctionNodeBooleanMath")
    boolean_math.name = "Boolean Math"
    boolean_math.operation = 'AND'

    #node Boolean Math.001
    boolean_math_001 = triplanar_uv_mapping.nodes.new("FunctionNodeBooleanMath")
    boolean_math_001.name = "Boolean Math.001"
    boolean_math_001.operation = 'AND'

    #node Vector Rotate
    vector_rotate = triplanar_uv_mapping.nodes.new("ShaderNodeVectorRotate")
    vector_rotate.name = "Vector Rotate"
    vector_rotate.invert = False
    vector_rotate.rotation_type = 'EULER_XYZ'
    #Center
    vector_rotate.inputs[1].default_value = (0.0, 0.0, 0.0)

    #node Vector Math.004
    vector_math_004 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_004.name = "Vector Math.004"
    vector_math_004.operation = 'MULTIPLY'

    #node Object Info.001
    object_info_001 = triplanar_uv_mapping.nodes.new("GeometryNodeObjectInfo")
    object_info_001.name = "Object Info.001"
    object_info_001.transform_space = 'ORIGINAL'
    #As Instance
    object_info_001.inputs[1].default_value = False

    #node Self Object.001
    self_object_001 = triplanar_uv_mapping.nodes.new("GeometryNodeSelfObject")
    self_object_001.name = "Self Object.001"

    #node Group Input.002
    group_input_002 = triplanar_uv_mapping.nodes.new("NodeGroupInput")
    group_input_002.name = "Group Input.002"
    group_input_002.outputs[0].hide = True
    group_input_002.outputs[1].hide = True
    group_input_002.outputs[2].hide = True
    group_input_002.outputs[3].hide = True
    group_input_002.outputs[4].hide = True
    group_input_002.outputs[5].hide = True
    group_input_002.outputs[7].hide = True
    group_input_002.outputs[8].hide = True
    group_input_002.outputs[9].hide = True
    group_input_002.outputs[10].hide = True

    #node Switch.004
    switch_004 = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch_004.name = "Switch.004"
    switch_004.input_type = 'VECTOR'

    #node Vector Math.006
    vector_math_006 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_006.name = "Vector Math.006"
    vector_math_006.operation = 'SCALE'
    vector_math_006.inputs[1].hide = True
    vector_math_006.inputs[2].hide = True
    vector_math_006.outputs[1].hide = True

    #node Group Input.004
    group_input_004 = triplanar_uv_mapping.nodes.new("NodeGroupInput")
    group_input_004.name = "Group Input.004"
    group_input_004.outputs[0].hide = True
    group_input_004.outputs[1].hide = True
    group_input_004.outputs[2].hide = True
    group_input_004.outputs[3].hide = True
    group_input_004.outputs[4].hide = True
    group_input_004.outputs[5].hide = True
    group_input_004.outputs[6].hide = True
    group_input_004.outputs[8].hide = True
    group_input_004.outputs[10].hide = True

    #node Vector Math.007
    vector_math_007 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_007.name = "Vector Math.007"
    vector_math_007.operation = 'ADD'
    vector_math_007.inputs[2].hide = True
    vector_math_007.inputs[3].hide = True
    vector_math_007.outputs[1].hide = True

    #node Object Info.003
    object_info_003 = triplanar_uv_mapping.nodes.new("GeometryNodeObjectInfo")
    object_info_003.name = "Object Info.003"
    object_info_003.mute = True
    object_info_003.transform_space = 'ORIGINAL'
    #As Instance
    object_info_003.inputs[1].default_value = False

    #node Self Object.003
    self_object_003 = triplanar_uv_mapping.nodes.new("GeometryNodeSelfObject")
    self_object_003.name = "Self Object.003"
    self_object_003.mute = True

    #node Group Input.003
    group_input_003 = triplanar_uv_mapping.nodes.new("NodeGroupInput")
    group_input_003.name = "Group Input.003"
    group_input_003.outputs[0].hide = True
    group_input_003.outputs[1].hide = True
    group_input_003.outputs[2].hide = True
    group_input_003.outputs[3].hide = True
    group_input_003.outputs[4].hide = True
    group_input_003.outputs[5].hide = True
    group_input_003.outputs[6].hide = True
    group_input_003.outputs[7].hide = True
    group_input_003.outputs[8].hide = True
    group_input_003.outputs[10].hide = True

    #node Boolean Math.003
    boolean_math_003 = triplanar_uv_mapping.nodes.new("FunctionNodeBooleanMath")
    boolean_math_003.name = "Boolean Math.003"
    boolean_math_003.operation = 'NOT'

    #node Math
    math = triplanar_uv_mapping.nodes.new("ShaderNodeMath")
    math.name = "Math"
    math.operation = 'ADD'
    math.use_clamp = False

    #node Separate XYZ.002
    separate_xyz_002 = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz_002.name = "Separate XYZ.002"

    #node Combine XYZ.001
    combine_xyz_001 = triplanar_uv_mapping.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz_001.name = "Combine XYZ.001"
    #X
    combine_xyz_001.inputs[0].default_value = 0.0
    #Y
    combine_xyz_001.inputs[1].default_value = -1.5707999467849731

    #node Separate XYZ.003
    separate_xyz_003 = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz_003.name = "Separate XYZ.003"

    #node Combine XYZ.002
    combine_xyz_002 = triplanar_uv_mapping.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz_002.name = "Combine XYZ.002"
    #X
    combine_xyz_002.inputs[0].default_value = -1.5707999467849731
    #Y
    combine_xyz_002.inputs[1].default_value = 0.0

    #node Math.001
    math_001 = triplanar_uv_mapping.nodes.new("ShaderNodeMath")
    math_001.name = "Math.001"
    math_001.operation = 'MULTIPLY'
    math_001.use_clamp = False
    #Value_001
    math_001.inputs[1].default_value = -1.0

    #node Vector Math.010
    vector_math_010 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_010.name = "Vector Math.010"
    vector_math_010.operation = 'ADD'
    vector_math_010.inputs[2].hide = True
    vector_math_010.inputs[3].hide = True
    vector_math_010.outputs[1].hide = True

    #node Position.002
    position_002 = triplanar_uv_mapping.nodes.new("GeometryNodeInputPosition")
    position_002.name = "Position.002"

    #node Separate XYZ.004
    separate_xyz_004 = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz_004.name = "Separate XYZ.004"

    #node Combine XYZ.003
    combine_xyz_003 = triplanar_uv_mapping.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz_003.name = "Combine XYZ.003"
    #X
    combine_xyz_003.inputs[0].default_value = 0.0
    #Y
    combine_xyz_003.inputs[1].default_value = 0.0

    #node Object Info.004
    object_info_004 = triplanar_uv_mapping.nodes.new("GeometryNodeObjectInfo")
    object_info_004.name = "Object Info.004"
    object_info_004.transform_space = 'ORIGINAL'
    #As Instance
    object_info_004.inputs[1].default_value = False

    #node Self Object.004
    self_object_004 = triplanar_uv_mapping.nodes.new("GeometryNodeSelfObject")
    self_object_004.name = "Self Object.004"

    #node Vector Math.009
    vector_math_009 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_009.name = "Vector Math.009"
    vector_math_009.operation = 'ADD'
    vector_math_009.inputs[2].hide = True
    vector_math_009.inputs[3].hide = True
    vector_math_009.outputs[1].hide = True

    #node Group Input.005
    group_input_005 = triplanar_uv_mapping.nodes.new("NodeGroupInput")
    group_input_005.name = "Group Input.005"
    group_input_005.outputs[0].hide = True
    group_input_005.outputs[1].hide = True
    group_input_005.outputs[2].hide = True
    group_input_005.outputs[4].hide = True
    group_input_005.outputs[5].hide = True
    group_input_005.outputs[6].hide = True
    group_input_005.outputs[7].hide = True
    group_input_005.outputs[8].hide = True
    group_input_005.outputs[9].hide = True
    group_input_005.outputs[10].hide = True

    #node Switch.005
    switch_005 = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch_005.name = "Switch.005"
    switch_005.input_type = 'VECTOR'





    #Set locations
    group_input.location = (1618.71875, -177.65013122558594)
    group_output.location = (3218.12109375, -119.95706176757812)
    store_named_attribute.location = (3024.74951171875, -120.89886474609375)
    combine_xyz.location = (2440.536865234375, -269.6875)
    vector_rotate_001.location = (2607.607421875, -369.5301208496094)
    separate_xyz_001.location = (-850.6109619140625, -997.3045043945312)
    compare_002.location = (-585.7400512695312, -844.56103515625)
    compare_003.location = (-585.2684936523438, -1009.624267578125)
    position.location = (-46.76734924316406, -392.42816162109375)
    vector_math.location = (806.116455078125, -627.3997192382812)
    switch.location = (412.1543884277344, -818.9706420898438)
    switch_001.location = (151.3099365234375, -899.8958129882812)
    switch_003.location = (842.8276977539062, -849.111083984375)
    switch_002.location = (1219.5185546875, -736.88232421875)
    normal.location = (-1246.9434814453125, -1070.3668212890625)
    vector_math_001.location = (-1053.5908203125, -1015.7783813476562)
    separate_xyz.location = (-538.8992919921875, -1285.957763671875)
    compare.location = (-322.9216003417969, -1095.156982421875)
    compare_001.location = (-294.9595642089844, -1298.4024658203125)
    boolean_math.location = (-104.07305908203125, -1270.914794921875)
    boolean_math_001.location = (-143.67474365234375, -724.1923828125)
    vector_rotate.location = (1799.5244140625, -642.817138671875)
    vector_math_004.location = (239.3844757080078, -417.611572265625)
    object_info_001.location = (-48.02244186401367, -450.4876403808594)
    self_object_001.location = (-233.47183227539062, -499.84259033203125)
    group_input_002.location = (74.32839965820312, -233.9241943359375)
    switch_004.location = (454.7678527832031, -385.1258544921875)
    vector_math_006.location = (2319.488037109375, -365.44622802734375)
    group_input_004.location = (2072.93798828125, -502.40576171875)
    vector_math_007.location = (2850.14794921875, -323.29901123046875)
    object_info_003.location = (327.0261535644531, -1213.8956298828125)
    self_object_003.location = (177.04380798339844, -1415.77587890625)
    group_input_003.location = (2417.1044921875, -656.2293701171875)
    boolean_math_003.location = (1442.992431640625, -1154.0697021484375)
    math.location = (1195.0794677734375, -1200.3321533203125)
    separate_xyz_002.location = (797.0464477539062, -1394.712890625)
    combine_xyz_001.location = (980.4664916992188, -1386.6495361328125)
    separate_xyz_003.location = (755.58447265625, -1579.6807861328125)
    combine_xyz_002.location = (1147.4310302734375, -1500.011474609375)
    math_001.location = (956.2252807617188, -1576.642822265625)
    vector_math_010.location = (478.9027404785156, -1590.67919921875)
    position_002.location = (245.85205078125, -1612.192626953125)
    separate_xyz_004.location = (629.2012939453125, -1178.031494140625)
    combine_xyz_003.location = (1055.3148193359375, -1041.5009765625)
    object_info_004.location = (495.8307189941406, -56.04844665527344)
    self_object_004.location = (293.0511779785156, -194.81289672851562)
    vector_math_009.location = (1090.20458984375, -269.9072265625)
    group_input_005.location = (1182.134033203125, -545.7793579101562)
    switch_005.location = (1422.7188720703125, -503.6679992675781)

    #Set dimensions
    group_input.width, group_input.height = 140.0, 100.0
    group_output.width, group_output.height = 140.0, 100.0
    store_named_attribute.width, store_named_attribute.height = 140.0, 100.0
    combine_xyz.width, combine_xyz.height = 140.0, 100.0
    vector_rotate_001.width, vector_rotate_001.height = 140.0, 100.0
    separate_xyz_001.width, separate_xyz_001.height = 140.0, 100.0
    compare_002.width, compare_002.height = 140.0, 100.0
    compare_003.width, compare_003.height = 140.0, 100.0
    position.width, position.height = 140.0, 100.0
    vector_math.width, vector_math.height = 140.0, 100.0
    switch.width, switch.height = 140.0, 100.0
    switch_001.width, switch_001.height = 140.0, 100.0
    switch_003.width, switch_003.height = 140.0, 100.0
    switch_002.width, switch_002.height = 140.0, 100.0
    normal.width, normal.height = 140.0, 100.0
    vector_math_001.width, vector_math_001.height = 140.0, 100.0
    separate_xyz.width, separate_xyz.height = 140.0, 100.0
    compare.width, compare.height = 140.0, 100.0
    compare_001.width, compare_001.height = 140.0, 100.0
    boolean_math.width, boolean_math.height = 140.0, 100.0
    boolean_math_001.width, boolean_math_001.height = 140.0, 100.0
    vector_rotate.width, vector_rotate.height = 140.0, 100.0
    vector_math_004.width, vector_math_004.height = 140.0, 100.0
    object_info_001.width, object_info_001.height = 140.0, 100.0
    self_object_001.width, self_object_001.height = 140.0, 100.0
    group_input_002.width, group_input_002.height = 140.0, 100.0
    switch_004.width, switch_004.height = 140.0, 100.0
    vector_math_006.width, vector_math_006.height = 140.0, 100.0
    group_input_004.width, group_input_004.height = 140.0, 100.0
    vector_math_007.width, vector_math_007.height = 140.0, 100.0
    object_info_003.width, object_info_003.height = 140.0, 100.0
    self_object_003.width, self_object_003.height = 140.0, 100.0
    group_input_003.width, group_input_003.height = 140.0, 100.0
    boolean_math_003.width, boolean_math_003.height = 140.0, 100.0
    math.width, math.height = 140.0, 100.0
    separate_xyz_002.width, separate_xyz_002.height = 140.0, 100.0
    combine_xyz_001.width, combine_xyz_001.height = 140.0, 100.0
    separate_xyz_003.width, separate_xyz_003.height = 140.0, 100.0
    combine_xyz_002.width, combine_xyz_002.height = 140.0, 100.0
    math_001.width, math_001.height = 140.0, 100.0
    vector_math_010.width, vector_math_010.height = 132.3218994140625, 100.0
    position_002.width, position_002.height = 140.0, 100.0
    separate_xyz_004.width, separate_xyz_004.height = 140.0, 100.0
    combine_xyz_003.width, combine_xyz_003.height = 140.0, 100.0
    object_info_004.width, object_info_004.height = 140.0, 100.0
    self_object_004.width, self_object_004.height = 140.0, 100.0
    vector_math_009.width, vector_math_009.height = 140.0, 100.0
    group_input_005.width, group_input_005.height = 140.0, 100.0
    switch_005.width, switch_005.height = 140.0, 100.0

    #initialize triplanar_uv_mapping links
    #store_named_attribute.Geometry -> group_output.Geometry
    triplanar_uv_mapping.links.new(store_named_attribute.outputs[0], group_output.inputs[0])
    #group_input.Geometry -> store_named_attribute.Geometry
    triplanar_uv_mapping.links.new(group_input.outputs[0], store_named_attribute.inputs[0])
    #group_input.Selection -> store_named_attribute.Selection
    triplanar_uv_mapping.links.new(group_input.outputs[1], store_named_attribute.inputs[1])
    #group_input.Name -> store_named_attribute.Name
    triplanar_uv_mapping.links.new(group_input.outputs[2], store_named_attribute.inputs[2])
    #normal.Normal -> vector_math_001.Vector
    triplanar_uv_mapping.links.new(normal.outputs[0], vector_math_001.inputs[0])
    #vector_math_001.Vector -> separate_xyz.Vector
    triplanar_uv_mapping.links.new(vector_math_001.outputs[0], separate_xyz.inputs[0])
    #separate_xyz.X -> compare.A
    triplanar_uv_mapping.links.new(separate_xyz.outputs[0], compare.inputs[0])
    #separate_xyz.Y -> compare.B
    triplanar_uv_mapping.links.new(separate_xyz.outputs[1], compare.inputs[1])
    #separate_xyz.X -> compare_001.A
    triplanar_uv_mapping.links.new(separate_xyz.outputs[0], compare_001.inputs[0])
    #separate_xyz.Z -> compare_001.B
    triplanar_uv_mapping.links.new(separate_xyz.outputs[2], compare_001.inputs[1])
    #compare.Result -> boolean_math.Boolean
    triplanar_uv_mapping.links.new(compare.outputs[0], boolean_math.inputs[0])
    #compare_001.Result -> boolean_math.Boolean
    triplanar_uv_mapping.links.new(compare_001.outputs[0], boolean_math.inputs[1])
    #vector_math_001.Vector -> separate_xyz_001.Vector
    triplanar_uv_mapping.links.new(vector_math_001.outputs[0], separate_xyz_001.inputs[0])
    #separate_xyz_001.Z -> compare_003.B
    triplanar_uv_mapping.links.new(separate_xyz_001.outputs[2], compare_003.inputs[1])
    #compare_002.Result -> boolean_math_001.Boolean
    triplanar_uv_mapping.links.new(compare_002.outputs[0], boolean_math_001.inputs[0])
    #compare_003.Result -> boolean_math_001.Boolean
    triplanar_uv_mapping.links.new(compare_003.outputs[0], boolean_math_001.inputs[1])
    #separate_xyz_001.Y -> compare_002.A
    triplanar_uv_mapping.links.new(separate_xyz_001.outputs[1], compare_002.inputs[0])
    #separate_xyz_001.X -> compare_002.B
    triplanar_uv_mapping.links.new(separate_xyz_001.outputs[0], compare_002.inputs[1])
    #separate_xyz_001.Y -> compare_003.A
    triplanar_uv_mapping.links.new(separate_xyz_001.outputs[1], compare_003.inputs[0])
    #switch.Output -> vector_math.Vector
    triplanar_uv_mapping.links.new(switch.outputs[0], vector_math.inputs[1])
    #switch_001.Output -> switch.False
    triplanar_uv_mapping.links.new(switch_001.outputs[0], switch.inputs[1])
    #boolean_math.Boolean -> switch_001.Switch
    triplanar_uv_mapping.links.new(boolean_math.outputs[0], switch_001.inputs[0])
    #boolean_math_001.Boolean -> switch.Switch
    triplanar_uv_mapping.links.new(boolean_math_001.outputs[0], switch.inputs[0])
    #switch_003.Output -> switch_002.False
    triplanar_uv_mapping.links.new(switch_003.outputs[0], switch_002.inputs[1])
    #boolean_math.Boolean -> switch_003.Switch
    triplanar_uv_mapping.links.new(boolean_math.outputs[0], switch_003.inputs[0])
    #boolean_math_001.Boolean -> switch_002.Switch
    triplanar_uv_mapping.links.new(boolean_math_001.outputs[0], switch_002.inputs[0])
    #group_input.Offset X -> combine_xyz.X
    triplanar_uv_mapping.links.new(group_input.outputs[5], combine_xyz.inputs[0])
    #group_input.Offset Y -> combine_xyz.Y
    triplanar_uv_mapping.links.new(group_input.outputs[4], combine_xyz.inputs[1])
    #position.Position -> vector_math_004.Vector
    triplanar_uv_mapping.links.new(position.outputs[0], vector_math_004.inputs[0])
    #self_object_001.Self Object -> object_info_001.Object
    triplanar_uv_mapping.links.new(self_object_001.outputs[0], object_info_001.inputs[0])
    #object_info_001.Scale -> vector_math_004.Vector
    triplanar_uv_mapping.links.new(object_info_001.outputs[3], vector_math_004.inputs[1])
    #group_input_002.World Scale -> switch_004.Switch
    triplanar_uv_mapping.links.new(group_input_002.outputs[6], switch_004.inputs[0])
    #vector_math_004.Vector -> switch_004.True
    triplanar_uv_mapping.links.new(vector_math_004.outputs[0], switch_004.inputs[2])
    #position.Position -> switch_004.False
    triplanar_uv_mapping.links.new(position.outputs[0], switch_004.inputs[1])
    #switch_004.Output -> vector_math.Vector
    triplanar_uv_mapping.links.new(switch_004.outputs[0], vector_math.inputs[0])
    #group_input_004.Scale -> vector_math_006.Scale
    triplanar_uv_mapping.links.new(group_input_004.outputs[7], vector_math_006.inputs[3])
    #vector_rotate.Vector -> vector_math_006.Vector
    triplanar_uv_mapping.links.new(vector_rotate.outputs[0], vector_math_006.inputs[0])
    #combine_xyz.Vector -> vector_math_007.Vector
    triplanar_uv_mapping.links.new(combine_xyz.outputs[0], vector_math_007.inputs[1])
    #vector_rotate_001.Vector -> vector_math_007.Vector
    triplanar_uv_mapping.links.new(vector_rotate_001.outputs[0], vector_math_007.inputs[0])
    #vector_math_007.Vector -> store_named_attribute.Value
    triplanar_uv_mapping.links.new(vector_math_007.outputs[0], store_named_attribute.inputs[3])
    #self_object_003.Self Object -> object_info_003.Object
    triplanar_uv_mapping.links.new(self_object_003.outputs[0], object_info_003.inputs[0])
    #math.Value -> boolean_math_003.Boolean
    triplanar_uv_mapping.links.new(math.outputs[0], boolean_math_003.inputs[0])
    #boolean_math_001.Boolean -> math.Value
    triplanar_uv_mapping.links.new(boolean_math_001.outputs[0], math.inputs[0])
    #boolean_math.Boolean -> math.Value
    triplanar_uv_mapping.links.new(boolean_math.outputs[0], math.inputs[1])
    #object_info_003.Rotation -> separate_xyz_002.Vector
    triplanar_uv_mapping.links.new(object_info_003.outputs[2], separate_xyz_002.inputs[0])
    #object_info_003.Rotation -> separate_xyz_003.Vector
    triplanar_uv_mapping.links.new(object_info_003.outputs[2], separate_xyz_003.inputs[0])
    #separate_xyz_003.Y -> math_001.Value
    triplanar_uv_mapping.links.new(separate_xyz_003.outputs[1], math_001.inputs[0])
    #math_001.Value -> combine_xyz_002.Z
    triplanar_uv_mapping.links.new(math_001.outputs[0], combine_xyz_002.inputs[2])
    #position_002.Position -> vector_math_010.Vector
    triplanar_uv_mapping.links.new(position_002.outputs[0], vector_math_010.inputs[1])
    #object_info_003.Location -> vector_math_010.Vector
    triplanar_uv_mapping.links.new(object_info_003.outputs[1], vector_math_010.inputs[0])
    #separate_xyz_002.X -> combine_xyz_001.Z
    triplanar_uv_mapping.links.new(separate_xyz_002.outputs[0], combine_xyz_001.inputs[2])
    #object_info_003.Rotation -> separate_xyz_004.Vector
    triplanar_uv_mapping.links.new(object_info_003.outputs[2], separate_xyz_004.inputs[0])
    #separate_xyz_004.Z -> combine_xyz_003.Z
    triplanar_uv_mapping.links.new(separate_xyz_004.outputs[2], combine_xyz_003.inputs[2])
    #self_object_004.Self Object -> object_info_004.Object
    triplanar_uv_mapping.links.new(self_object_004.outputs[0], object_info_004.inputs[0])
    #vector_math.Vector -> vector_math_009.Vector
    triplanar_uv_mapping.links.new(vector_math.outputs[0], vector_math_009.inputs[1])
    #object_info_004.Location -> vector_math_009.Vector
    triplanar_uv_mapping.links.new(object_info_004.outputs[1], vector_math_009.inputs[0])
    #vector_math_006.Vector -> vector_rotate_001.Vector
    triplanar_uv_mapping.links.new(vector_math_006.outputs[0], vector_rotate_001.inputs[0])
    #group_input_003.Angle -> vector_rotate_001.Angle
    triplanar_uv_mapping.links.new(group_input_003.outputs[9], vector_rotate_001.inputs[3])
    #switch_002.Output -> vector_rotate.Rotation
    triplanar_uv_mapping.links.new(switch_002.outputs[0], vector_rotate.inputs[4])
    #vector_math.Vector -> switch_005.False
    triplanar_uv_mapping.links.new(vector_math.outputs[0], switch_005.inputs[1])
    #vector_math_009.Vector -> switch_005.True
    triplanar_uv_mapping.links.new(vector_math_009.outputs[0], switch_005.inputs[2])
    #switch_005.Output -> vector_rotate.Vector
    triplanar_uv_mapping.links.new(switch_005.outputs[0], vector_rotate.inputs[0])
    #group_input_005.World Offset -> switch_005.Switch
    triplanar_uv_mapping.links.new(group_input_005.outputs[3], switch_005.inputs[0])
    #combine_xyz.Vector -> vector_rotate_001.Center
    triplanar_uv_mapping.links.new(combine_xyz.outputs[0], vector_rotate_001.inputs[1])
    return triplanar_uv_mapping

def get_all_bouding_box_node_group(obj_name):
    get_all_bouding_box = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Get All Bouding Box")

    get_all_bouding_box.color_tag = 'NONE'
    get_all_bouding_box.description = ""

    get_all_bouding_box.is_modifier = True
	
    #get_all_bouding_box interface
    #Socket Geometry
    geometry_socket = get_all_bouding_box.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'

    #Socket Geometry
    geometry_socket_1 = get_all_bouding_box.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket_1.attribute_domain = 'POINT'


    #initialize get_all_bouding_box nodes
    #node Group Input
    group_input = get_all_bouding_box.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    #node Group Output
    group_output = get_all_bouding_box.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    #node Bounding Box
    bounding_box = get_all_bouding_box.nodes.new("GeometryNodeBoundBox")
    bounding_box.name = "Bounding Box"

    #node Realize Instances
    realize_instances = get_all_bouding_box.nodes.new("GeometryNodeRealizeInstances")
    realize_instances.name = "Realize Instances"
    #Selection
    realize_instances.inputs[1].default_value = True
    #Realize All
    realize_instances.inputs[2].default_value = True
    #Depth
    realize_instances.inputs[3].default_value = 0

    #node Join Geometry
    join_geometry = get_all_bouding_box.nodes.new("GeometryNodeJoinGeometry")
    join_geometry.name = "Join Geometry"

    iteration = -1
    for i in obj_name:
        iteration += 1
        object_info = "object_info" + str((iteration))

        object_info = get_all_bouding_box.nodes.new("GeometryNodeObjectInfo")
        object_info.name = "Object Info." + str((iteration))
        object_info.hide = True
        object_info.transform_space = 'RELATIVE'

        #As Instance
        object_info.inputs[1].default_value = True
        object_info.location = (-389.14093017578125, -171.42857360839844*iteration/3)

        get_all_bouding_box.links.new(object_info.outputs[4], join_geometry.inputs[0])

        if str(obj_name[iteration]) in bpy.data.objects:
            object_info.inputs[0].default_value = bpy.data.objects[str(obj_name[iteration])]


    #Set locations
    group_input.location = (-340.0, 0.0)
    group_output.location = (556.55908203125, -48.850746154785156)
    bounding_box.location = (17.911235809326172, -45.44710159301758)
    realize_instances.location = (198.05038452148438, -57.47685241699219)
    join_geometry.location = (-169.419677734375, -114.13054656982422)

    #initialize get_all_bouding_box links
    #object_info_0.Geometry -> join_geometry.Geometry
    get_all_bouding_box.links.new(bounding_box.outputs[0], group_output.inputs[0])
    #join_geometry.Geometry -> realize_instances.Geometry
    get_all_bouding_box.links.new(join_geometry.outputs[0], realize_instances.inputs[0])
    #realize_instances.Geometry -> bounding_box_001.Geometry
    get_all_bouding_box.links.new(realize_instances.outputs[0], bounding_box.inputs[0])

    #object_info.Geometry -> join_geometry.Geometry
    get_all_bouding_box.links.new(object_info.outputs[4], join_geometry.inputs[0])
    return get_all_bouding_box

def duplicate_linked_modifiers_node_group():
	duplicate_linked_modifiers = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Duplicate Linked Modifiers")

	duplicate_linked_modifiers.color_tag = 'NONE'
	duplicate_linked_modifiers.description = ""

	duplicate_linked_modifiers.is_modifier = True
	
	#duplicate_linked_modifiers interface
	#Socket Geometry
	geometry_socket = duplicate_linked_modifiers.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
	geometry_socket.attribute_domain = 'POINT'
	
	#Socket Geometry
	geometry_socket_1 = duplicate_linked_modifiers.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
	geometry_socket_1.attribute_domain = 'POINT'
	
	#Socket Object
	object_socket = duplicate_linked_modifiers.interface.new_socket(name = "Object", in_out='INPUT', socket_type = 'NodeSocketObject')
	object_socket.attribute_domain = 'POINT'
	
	#Socket As Instance
	as_instance_socket = duplicate_linked_modifiers.interface.new_socket(name = "As Instance", in_out='INPUT', socket_type = 'NodeSocketBool')
	as_instance_socket.default_value = True
	as_instance_socket.attribute_domain = 'POINT'
	
	
	#initialize duplicate_linked_modifiers nodes
	#node Group Input
	group_input = duplicate_linked_modifiers.nodes.new("NodeGroupInput")
	group_input.name = "Group Input"
	
	#node Group Output
	group_output = duplicate_linked_modifiers.nodes.new("NodeGroupOutput")
	group_output.name = "Group Output"
	group_output.is_active_output = True
	
	#node Object Info
	object_info = duplicate_linked_modifiers.nodes.new("GeometryNodeObjectInfo")
	object_info.name = "Object Info"
	object_info.transform_space = 'ORIGINAL'
	
	#Set locations
	group_input.location = (-251.35650634765625, -25.58302116394043)
	group_output.location = (200.0, 0.0)
	object_info.location = (-25.55487823486328, 89.14085388183594)
	
	#initialize duplicate_linked_modifiers links
	#object_info.Geometry -> group_output.Geometry
	duplicate_linked_modifiers.links.new(object_info.outputs[4], group_output.inputs[0])
	#group_input.Object -> object_info.Object
	duplicate_linked_modifiers.links.new(group_input.outputs[1], object_info.inputs[0])
	#group_input.As Instance -> object_info.As Instance
	duplicate_linked_modifiers.links.new(group_input.outputs[2], object_info.inputs[1])
	return duplicate_linked_modifiers

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
	reroute.width, reroute.height = 140.0, 100.0
	separate_xyz.width, separate_xyz.height = 140.0, 100.0
	compare.width, compare.height = 140.0, 100.0
	math_004.width, math_004.height = 140.0, 100.0
	reroute_001.width, reroute_001.height = 140.0, 100.0
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

def unwrap_in_place_tool_node_group():
	unwrap_in_place_tool = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Unwrap In Place Tool")

	unwrap_in_place_tool.is_tool = True
	unwrap_in_place_tool.is_mode_object = False
	unwrap_in_place_tool.is_mode_edit = False
	unwrap_in_place_tool.is_mode_sculpt = False
	unwrap_in_place_tool.is_type_curve = False
	unwrap_in_place_tool.is_type_mesh = True
	unwrap_in_place_tool.is_type_point_cloud = False
	
	#initialize unwrap_in_place_tool nodes
	#unwrap_in_place_tool interface
	#Socket Geometry
	geometry_socket_1 = unwrap_in_place_tool.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
	geometry_socket_1.attribute_domain = 'POINT'
	
	#Socket Geometry
	geometry_socket_2 = unwrap_in_place_tool.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
	geometry_socket_2.attribute_domain = 'POINT'
	
	
	#node Group Input.001
	group_input_001 = unwrap_in_place_tool.nodes.new("NodeGroupInput")
	group_input_001.name = "Group Input.001"
	group_input_001.outputs[1].hide = True
	
	#node Group Output.001
	group_output_001 = unwrap_in_place_tool.nodes.new("NodeGroupOutput")
	group_output_001.name = "Group Output.001"
	group_output_001.is_active_output = True
	
	#node Set Position
	set_position = unwrap_in_place_tool.nodes.new("GeometryNodeSetPosition")
	set_position.name = "Set Position"
	#Offset
	set_position.inputs[3].default_value = (0.0, 0.0, 0.0)
	
	#node Named Attribute
	named_attribute = unwrap_in_place_tool.nodes.new("GeometryNodeInputNamedAttribute")
	named_attribute.name = "Named Attribute"
	named_attribute.data_type = 'FLOAT_VECTOR'
	
	#node Position
	position_1 = unwrap_in_place_tool.nodes.new("GeometryNodeInputPosition")
	position_1.name = "Position"
	
	#node Split Edges
	split_edges = unwrap_in_place_tool.nodes.new("GeometryNodeSplitEdges")
	split_edges.name = "Split Edges"
	
	#node Store Named Attribute.003
	store_named_attribute_003 = unwrap_in_place_tool.nodes.new("GeometryNodeStoreNamedAttribute")
	store_named_attribute_003.name = "Store Named Attribute.003"
	store_named_attribute_003.data_type = 'FLOAT2'
	store_named_attribute_003.domain = 'CORNER'
	
	#node UV Unwrap.001
	uv_unwrap_001 = unwrap_in_place_tool.nodes.new("GeometryNodeUVUnwrap")
	uv_unwrap_001.name = "UV Unwrap.001"
	uv_unwrap_001.method = 'ANGLE_BASED'
	
	#node Store Named Attribute.004
	store_named_attribute_004 = unwrap_in_place_tool.nodes.new("GeometryNodeStoreNamedAttribute")
	store_named_attribute_004.name = "Store Named Attribute.004"
	store_named_attribute_004.data_type = 'FLOAT2'
	store_named_attribute_004.domain = 'CORNER'
	#Selection
	store_named_attribute_004.inputs[1].default_value = True
	
	#node Set Position.003
	set_position_003 = unwrap_in_place_tool.nodes.new("GeometryNodeSetPosition")
	set_position_003.name = "Set Position.003"
	#Offset
	set_position_003.inputs[3].default_value = (0.0, 0.0, 0.0)
	
	#node Set Position.001
	set_position_001 = unwrap_in_place_tool.nodes.new("GeometryNodeSetPosition")
	set_position_001.name = "Set Position.001"
	set_position_001.inputs[3].hide = True
	#Offset
	set_position_001.inputs[3].default_value = (0.0, 0.0, 0.0)
	
	#node Group.001
	group_001 = unwrap_in_place_tool.nodes.new("GeometryNodeGroup")
	group_001.label = "Match Bounding Box"
	group_001.name = "Group.001"
	group_001.node_tree = match_bounding_box_node_group()
	
	#node Group Input.006
	group_input_006 = unwrap_in_place_tool.nodes.new("NodeGroupInput")
	group_input_006.name = "Group Input.006"
	group_input_006.outputs[1].hide = True
	
	#node Store Named Attribute.006
	store_named_attribute_006 = unwrap_in_place_tool.nodes.new("GeometryNodeStoreNamedAttribute")
	store_named_attribute_006.name = "Store Named Attribute.006"
	store_named_attribute_006.data_type = 'FLOAT2'
	store_named_attribute_006.domain = 'CORNER'
	
	#node Named Attribute.001
	named_attribute_001 = unwrap_in_place_tool.nodes.new("GeometryNodeInputNamedAttribute")
	named_attribute_001.name = "Named Attribute.001"
	named_attribute_001.data_type = 'FLOAT_VECTOR'
	
	#node Sample Index.001
	sample_index_001_1 = unwrap_in_place_tool.nodes.new("GeometryNodeSampleIndex")
	sample_index_001_1.name = "Sample Index.001"
	sample_index_001_1.clamp = False
	sample_index_001_1.data_type = 'FLOAT_VECTOR'
	sample_index_001_1.domain = 'CORNER'
	
	#node Index
	index_1 = unwrap_in_place_tool.nodes.new("GeometryNodeInputIndex")
	index_1.name = "Index"
	
	#node Duplicate Elements
	duplicate_elements = unwrap_in_place_tool.nodes.new("GeometryNodeDuplicateElements")
	duplicate_elements.name = "Duplicate Elements"
	duplicate_elements.domain = 'FACE'
	#Amount
	duplicate_elements.inputs[2].default_value = 1
	
	#node Switch
	switch = unwrap_in_place_tool.nodes.new("GeometryNodeSwitch")
	switch.name = "Switch"
	switch.input_type = 'VECTOR'
	#Switch
	switch.inputs[0].default_value = False
	
	#node UV Unwrap.002
	uv_unwrap_002 = unwrap_in_place_tool.nodes.new("GeometryNodeUVUnwrap")
	uv_unwrap_002.name = "UV Unwrap.002"
	uv_unwrap_002.method = 'CONFORMAL'
	
	#node Selection
	selection = unwrap_in_place_tool.nodes.new("GeometryNodeToolSelection")
	selection.name = "Selection"
	
	#node Evaluate on Domain
	evaluate_on_domain = unwrap_in_place_tool.nodes.new("GeometryNodeFieldOnDomain")
	evaluate_on_domain.name = "Evaluate on Domain"
	evaluate_on_domain.data_type = 'BOOLEAN'
	evaluate_on_domain.domain = 'FACE'
	
	#node Named Attribute.002
	named_attribute_002 = unwrap_in_place_tool.nodes.new("GeometryNodeInputNamedAttribute")
	named_attribute_002.name = "Named Attribute.002"
	named_attribute_002.data_type = 'BOOLEAN'
	
	#node Named Attribute.003
	named_attribute_003 = unwrap_in_place_tool.nodes.new("GeometryNodeInputNamedAttribute")
	named_attribute_003.name = "Named Attribute.003"
	named_attribute_003.data_type = 'BOOLEAN'
	
	#node Remove Named Attribute
	remove_named_attribute = unwrap_in_place_tool.nodes.new("GeometryNodeRemoveAttribute")
	remove_named_attribute.name = "Remove Named Attribute"
	remove_named_attribute.pattern_mode = 'EXACT'
	#Name
	remove_named_attribute.inputs[1].default_value = "seam_Unwrap_In_Place"
	
	#node String
	string = unwrap_in_place_tool.nodes.new("FunctionNodeInputString")
	string.name = "String"
	string.string = "UVMap"
	
	#node Value
	value = unwrap_in_place_tool.nodes.new("ShaderNodeValue")
	value.name = "Value"
	
	value.outputs[0].default_value = 0.0010000000474974513
	#node Boolean
	boolean = unwrap_in_place_tool.nodes.new("FunctionNodeInputBool")
	boolean.name = "Boolean"
	boolean.boolean = True
	
	#node String.001
	string_001 = unwrap_in_place_tool.nodes.new("FunctionNodeInputString")
	string_001.name = "String.001"
	string_001.string = "seam_Unwrap_In_Place"
	
	#node Bounding Box
	bounding_box_1 = unwrap_in_place_tool.nodes.new("GeometryNodeBoundBox")
	bounding_box_1.name = "Bounding Box"
	
	#node Vector Math
	vector_math_1 = unwrap_in_place_tool.nodes.new("ShaderNodeVectorMath")
	vector_math_1.name = "Vector Math"
	vector_math_1.operation = 'SUBTRACT'
	#Vector_002
	vector_math_1.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Scale
	vector_math_1.inputs[3].default_value = 1.0
	
	#node Grid
	grid = unwrap_in_place_tool.nodes.new("GeometryNodeMeshGrid")
	grid.name = "Grid"
	grid.inputs[2].hide = True
	grid.inputs[3].hide = True
	grid.outputs[1].hide = True
	#Vertices X
	grid.inputs[2].default_value = 2
	#Vertices Y
	grid.inputs[3].default_value = 2
	
	#node Transform Geometry
	transform_geometry = unwrap_in_place_tool.nodes.new("GeometryNodeTransform")
	transform_geometry.name = "Transform Geometry"
	transform_geometry.mode = 'COMPONENTS'
	#Rotation
	transform_geometry.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Scale
	transform_geometry.inputs[3].default_value = (1.0, 1.0, 1.0)
	
	#node Switch.003
	switch_003 = unwrap_in_place_tool.nodes.new("GeometryNodeSwitch")
	switch_003.name = "Switch.003"
	switch_003.input_type = 'GEOMETRY'
	
	#node Vector Math.001
	vector_math_001_1 = unwrap_in_place_tool.nodes.new("ShaderNodeVectorMath")
	vector_math_001_1.name = "Vector Math.001"
	vector_math_001_1.operation = 'ADD'
	#Vector_002
	vector_math_001_1.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Scale
	vector_math_001_1.inputs[3].default_value = 1.0
	
	#node Vector Math.002
	vector_math_002 = unwrap_in_place_tool.nodes.new("ShaderNodeVectorMath")
	vector_math_002.name = "Vector Math.002"
	vector_math_002.operation = 'SCALE'
	#Vector_001
	vector_math_002.inputs[1].default_value = (0.0, 0.0, 0.0)
	#Vector_002
	vector_math_002.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Scale
	vector_math_002.inputs[3].default_value = 0.5
	
	#node Compare.002
	compare_002 = unwrap_in_place_tool.nodes.new("FunctionNodeCompare")
	compare_002.name = "Compare.002"
	compare_002.data_type = 'FLOAT'
	compare_002.mode = 'ELEMENT'
	compare_002.operation = 'LESS_EQUAL'
	#B
	compare_002.inputs[1].default_value = 2.0
	#A_INT
	compare_002.inputs[2].default_value = 0
	#B_INT
	compare_002.inputs[3].default_value = 0
	#A_VEC3
	compare_002.inputs[4].default_value = (0.0, 0.0, 0.0)
	#B_VEC3
	compare_002.inputs[5].default_value = (0.0, 0.0, 0.0)
	#A_COL
	compare_002.inputs[6].default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
	#B_COL
	compare_002.inputs[7].default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
	#A_STR
	compare_002.inputs[8].default_value = ""
	#B_STR
	compare_002.inputs[9].default_value = ""
	#C
	compare_002.inputs[10].default_value = 0.8999999761581421
	#Angle
	compare_002.inputs[11].default_value = 0.08726649731397629
	#Epsilon
	compare_002.inputs[12].default_value = 0.0010000000474974513
	
	#node Vector Math.003
	vector_math_003 = unwrap_in_place_tool.nodes.new("ShaderNodeVectorMath")
	vector_math_003.name = "Vector Math.003"
	vector_math_003.operation = 'LENGTH'
	#Vector_001
	vector_math_003.inputs[1].default_value = (0.0, 0.0, 0.0)
	#Vector_002
	vector_math_003.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Scale
	vector_math_003.inputs[3].default_value = 1.0
	
	#node Domain Size
	domain_size = unwrap_in_place_tool.nodes.new("GeometryNodeAttributeDomainSize")
	domain_size.name = "Domain Size"
	domain_size.component = 'MESH'
	domain_size.outputs[1].hide = True
	domain_size.outputs[2].hide = True
	domain_size.outputs[3].hide = True
	domain_size.outputs[4].hide = True
	domain_size.outputs[5].hide = True
	domain_size.outputs[6].hide = True
	
	#node Merge by Distance.002
	merge_by_distance_002 = unwrap_in_place_tool.nodes.new("GeometryNodeMergeByDistance")
	merge_by_distance_002.name = "Merge by Distance.002"
	merge_by_distance_002.mode = 'CONNECTED'
	#Selection
	merge_by_distance_002.inputs[1].default_value = True
	#Distance
	merge_by_distance_002.inputs[2].default_value = 9.999999747378752e-05
	
	#node Named Attribute.004
	named_attribute_004 = unwrap_in_place_tool.nodes.new("GeometryNodeInputNamedAttribute")
	named_attribute_004.name = "Named Attribute.004"
	named_attribute_004.data_type = 'FLOAT_VECTOR'
	
	#node Duplicate Elements.002
	duplicate_elements_002 = unwrap_in_place_tool.nodes.new("GeometryNodeDuplicateElements")
	duplicate_elements_002.name = "Duplicate Elements.002"
	duplicate_elements_002.domain = 'FACE'
	#Selection
	duplicate_elements_002.inputs[1].default_value = True
	#Amount
	duplicate_elements_002.inputs[2].default_value = 1
	
	#node Set Position.002
	set_position_002 = unwrap_in_place_tool.nodes.new("GeometryNodeSetPosition")
	set_position_002.name = "Set Position.002"
	#Selection
	set_position_002.inputs[1].default_value = True
	#Offset
	set_position_002.inputs[3].default_value = (0.0, 0.0, 0.0)
	
	#node Duplicate Elements.003
	duplicate_elements_003 = unwrap_in_place_tool.nodes.new("GeometryNodeDuplicateElements")
	duplicate_elements_003.name = "Duplicate Elements.003"
	duplicate_elements_003.domain = 'POINT'
	#Amount
	duplicate_elements_003.inputs[2].default_value = 1
	
	#node Switch.004
	switch_004 = unwrap_in_place_tool.nodes.new("GeometryNodeSwitch")
	switch_004.name = "Switch.004"
	switch_004.input_type = 'GEOMETRY'
	
	#node Grid.001
	grid_001 = unwrap_in_place_tool.nodes.new("GeometryNodeMeshGrid")
	grid_001.name = "Grid.001"
	#Size X
	grid_001.inputs[0].default_value = 0.5
	#Size Y
	grid_001.inputs[1].default_value = 0.5
	#Vertices X
	grid_001.inputs[2].default_value = 2
	#Vertices Y
	grid_001.inputs[3].default_value = 2
	
	#node Transform Geometry.001
	transform_geometry_001 = unwrap_in_place_tool.nodes.new("GeometryNodeTransform")
	transform_geometry_001.name = "Transform Geometry.001"
	transform_geometry_001.mode = 'COMPONENTS'
	#Translation
	transform_geometry_001.inputs[1].default_value = (0.5, 0.5, 0.0)
	#Rotation
	transform_geometry_001.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Scale
	transform_geometry_001.inputs[3].default_value = (1.0, 1.0, 1.0)
	
	#node Compare.003
	compare_003 = unwrap_in_place_tool.nodes.new("FunctionNodeCompare")
	compare_003.name = "Compare.003"
	compare_003.data_type = 'FLOAT'
	compare_003.mode = 'ELEMENT'
	compare_003.operation = 'LESS_EQUAL'
	#B
	compare_003.inputs[1].default_value = 2.0
	#A_INT
	compare_003.inputs[2].default_value = 0
	#B_INT
	compare_003.inputs[3].default_value = 0
	#A_VEC3
	compare_003.inputs[4].default_value = (0.0, 0.0, 0.0)
	#B_VEC3
	compare_003.inputs[5].default_value = (0.0, 0.0, 0.0)
	#A_COL
	compare_003.inputs[6].default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
	#B_COL
	compare_003.inputs[7].default_value = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)
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
	
	#node Store Named Attribute
	store_named_attribute = unwrap_in_place_tool.nodes.new("GeometryNodeStoreNamedAttribute")
	store_named_attribute.name = "Store Named Attribute"
	store_named_attribute.data_type = 'FLOAT_VECTOR'
	store_named_attribute.domain = 'POINT'
	#Name
	store_named_attribute.inputs[2].default_value = "pos"
	
	#node Named Attribute.005
	named_attribute_005 = unwrap_in_place_tool.nodes.new("GeometryNodeInputNamedAttribute")
	named_attribute_005.name = "Named Attribute.005"
	named_attribute_005.data_type = 'FLOAT_VECTOR'
	#Name
	named_attribute_005.inputs[0].default_value = "pos"
	
	
	
	
	#Set locations
	group_input_001.location = (-709.258056640625, -436.9896545410156)
	group_output_001.location = (3731.859130859375, 158.48330688476562)
	set_position.location = (318.9644775390625, -283.7413330078125)
	named_attribute.location = (80.46863555908203, -529.8975219726562)
	position_1.location = (-643.6294555664062, -561.041015625)
	split_edges.location = (-120.47317504882812, -364.7484130859375)
	store_named_attribute_003.location = (1425.8426513671875, -320.0542907714844)
	uv_unwrap_001.location = (527.5487670898438, -552.85888671875)
	store_named_attribute_004.location = (2704.843505859375, -123.15985870361328)
	set_position_003.location = (1095.3909912109375, -380.85748291015625)
	set_position_001.location = (1895.7034912109375, -326.86370849609375)
	group_001.location = (2464.648681640625, -262.9260559082031)
	group_input_006.location = (2762.777587890625, 57.02855682373047)
	store_named_attribute_006.location = (3302.553955078125, 132.36138916015625)
	named_attribute_001.location = (2545.10546875, -31.51673126220703)
	sample_index_001_1.location = (3076.62158203125, -17.763328552246094)
	index_1.location = (2562.821533203125, -172.6898193359375)
	duplicate_elements.location = (528.2855224609375, -266.8842468261719)
	switch.location = (792.8668212890625, -605.5924072265625)
	uv_unwrap_002.location = (536.3257446289062, -727.11669921875)
	selection.location = (-229.96835327148438, -541.886474609375)
	evaluate_on_domain.location = (79.89872741699219, -380.45855712890625)
	named_attribute_002.location = (-63.35287857055664, -780.0927734375)
	named_attribute_003.location = (241.72677612304688, -737.4782104492188)
	remove_named_attribute.location = (3498.46875, 160.91714477539062)
	string.location = (-354.9782409667969, -717.7208862304688)
	value.location = (9.28640365600586, -693.0759887695312)
	boolean.location = (246.69219970703125, -943.7881469726562)
	string_001.location = (-314.5406188964844, -848.703857421875)
	bounding_box_1.location = (967.7250366210938, -92.2804946899414)
	vector_math_1.location = (1259.5888671875, 26.084964752197266)
	grid.location = (1657.582763671875, 73.90567016601562)
	transform_geometry.location = (2003.52880859375, -109.94488525390625)
	switch_003.location = (2236.65283203125, -38.558162689208984)
	vector_math_001_1.location = (1624.822509765625, -196.11776733398438)
	vector_math_002.location = (1750.199462890625, -194.54443359375)
	compare_002.location = (1649.615234375, -30.162660598754883)
	vector_math_003.location = (1419.9462890625, 72.43637084960938)
	domain_size.location = (1467.27392578125, -97.00637817382812)
	merge_by_distance_002.location = (1302.48974609375, -80.48823547363281)
	named_attribute_004.location = (1445.475341796875, -579.6399536132812)
	duplicate_elements_002.location = (1675.232421875, -348.19586181640625)
	set_position_002.location = (747.9999389648438, -118.56639099121094)
	duplicate_elements_003.location = (2244.999755859375, -351.35821533203125)
	switch_004.location = (2420.06201171875, 109.07523345947266)
	grid_001.location = (1965.2052001953125, 161.468994140625)
	transform_geometry_001.location = (2141.143310546875, 236.33486938476562)
	compare_003.location = (1833.024658203125, -36.365753173828125)
	store_named_attribute.location = (-432.9498291015625, -363.1137390136719)
	named_attribute_005.location = (873.2334594726562, -448.8204650878906)
	
	#Set dimensions
	group_input_001.width, group_input_001.height = 140.0, 100.0
	group_output_001.width, group_output_001.height = 140.0, 100.0
	set_position.width, set_position.height = 140.0, 100.0
	named_attribute.width, named_attribute.height = 140.0, 100.0
	position_1.width, position_1.height = 140.0, 100.0
	split_edges.width, split_edges.height = 140.0, 100.0
	store_named_attribute_003.width, store_named_attribute_003.height = 140.0, 100.0
	uv_unwrap_001.width, uv_unwrap_001.height = 140.0, 100.0
	store_named_attribute_004.width, store_named_attribute_004.height = 140.0, 100.0
	set_position_003.width, set_position_003.height = 140.0, 100.0
	set_position_001.width, set_position_001.height = 140.0, 100.0
	group_001.width, group_001.height = 140.0, 100.0
	group_input_006.width, group_input_006.height = 140.0, 100.0
	store_named_attribute_006.width, store_named_attribute_006.height = 140.0, 100.0
	named_attribute_001.width, named_attribute_001.height = 140.0, 100.0
	sample_index_001_1.width, sample_index_001_1.height = 140.0, 100.0
	index_1.width, index_1.height = 140.0, 100.0
	duplicate_elements.width, duplicate_elements.height = 140.0, 100.0
	switch.width, switch.height = 140.0, 100.0
	uv_unwrap_002.width, uv_unwrap_002.height = 140.0, 100.0
	selection.width, selection.height = 140.0, 100.0
	evaluate_on_domain.width, evaluate_on_domain.height = 140.0, 100.0
	named_attribute_002.width, named_attribute_002.height = 140.0, 100.0
	named_attribute_003.width, named_attribute_003.height = 140.0, 100.0
	remove_named_attribute.width, remove_named_attribute.height = 170.0, 100.0
	string.width, string.height = 140.0, 100.0
	value.width, value.height = 140.0, 100.0
	boolean.width, boolean.height = 140.0, 100.0
	string_001.width, string_001.height = 140.0, 100.0
	bounding_box_1.width, bounding_box_1.height = 140.0, 100.0
	vector_math_1.width, vector_math_1.height = 140.0, 100.0
	grid.width, grid.height = 140.0, 100.0
	transform_geometry.width, transform_geometry.height = 140.0, 100.0
	switch_003.width, switch_003.height = 140.0, 100.0
	vector_math_001_1.width, vector_math_001_1.height = 140.0, 100.0
	vector_math_002.width, vector_math_002.height = 140.0, 100.0
	compare_002.width, compare_002.height = 140.0, 100.0
	vector_math_003.width, vector_math_003.height = 140.0, 100.0
	domain_size.width, domain_size.height = 140.0, 100.0
	merge_by_distance_002.width, merge_by_distance_002.height = 140.0, 100.0
	named_attribute_004.width, named_attribute_004.height = 140.0, 100.0
	duplicate_elements_002.width, duplicate_elements_002.height = 140.0, 100.0
	set_position_002.width, set_position_002.height = 140.0, 100.0
	duplicate_elements_003.width, duplicate_elements_003.height = 140.0, 100.0
	switch_004.width, switch_004.height = 140.0, 100.0
	grid_001.width, grid_001.height = 140.0, 100.0
	transform_geometry_001.width, transform_geometry_001.height = 140.0, 100.0
	compare_003.width, compare_003.height = 140.0, 100.0
	store_named_attribute.width, store_named_attribute.height = 140.0, 100.0
	named_attribute_005.width, named_attribute_005.height = 140.0, 100.0
	
	#initialize unwrap_in_place_tool links
	#named_attribute.Attribute -> set_position.Position
	unwrap_in_place_tool.links.new(named_attribute.outputs[0], set_position.inputs[2])
	#split_edges.Mesh -> set_position.Geometry
	unwrap_in_place_tool.links.new(split_edges.outputs[0], set_position.inputs[0])
	#set_position.Geometry -> set_position_003.Geometry
	unwrap_in_place_tool.links.new(set_position.outputs[0], set_position_003.inputs[0])
	#set_position_003.Geometry -> store_named_attribute_003.Geometry
	unwrap_in_place_tool.links.new(set_position_003.outputs[0], store_named_attribute_003.inputs[0])
	#duplicate_elements_002.Geometry -> set_position_001.Geometry
	unwrap_in_place_tool.links.new(duplicate_elements_002.outputs[0], set_position_001.inputs[0])
	#set_position_001.Geometry -> store_named_attribute_004.Geometry
	unwrap_in_place_tool.links.new(set_position_001.outputs[0], store_named_attribute_004.inputs[0])
	#named_attribute_001.Attribute -> sample_index_001_1.Value
	unwrap_in_place_tool.links.new(named_attribute_001.outputs[0], sample_index_001_1.inputs[1])
	#sample_index_001_1.Value -> store_named_attribute_006.Value
	unwrap_in_place_tool.links.new(sample_index_001_1.outputs[0], store_named_attribute_006.inputs[3])
	#store_named_attribute_004.Geometry -> sample_index_001_1.Geometry
	unwrap_in_place_tool.links.new(store_named_attribute_004.outputs[0], sample_index_001_1.inputs[0])
	#index_1.Index -> sample_index_001_1.Index
	unwrap_in_place_tool.links.new(index_1.outputs[0], sample_index_001_1.inputs[2])
	#set_position.Geometry -> duplicate_elements.Geometry
	unwrap_in_place_tool.links.new(set_position.outputs[0], duplicate_elements.inputs[0])
	#group_001.Vector -> store_named_attribute_004.Value
	unwrap_in_place_tool.links.new(group_001.outputs[0], store_named_attribute_004.inputs[3])
	#duplicate_elements_003.Geometry -> group_001.Target
	unwrap_in_place_tool.links.new(duplicate_elements_003.outputs[0], group_001.inputs[1])
	#uv_unwrap_001.UV -> switch.True
	unwrap_in_place_tool.links.new(uv_unwrap_001.outputs[0], switch.inputs[2])
	#uv_unwrap_002.UV -> switch.False
	unwrap_in_place_tool.links.new(uv_unwrap_002.outputs[0], switch.inputs[1])
	#switch.Output -> store_named_attribute_003.Value
	unwrap_in_place_tool.links.new(switch.outputs[0], store_named_attribute_003.inputs[3])
	#group_input_006.Geometry -> store_named_attribute_006.Geometry
	unwrap_in_place_tool.links.new(group_input_006.outputs[0], store_named_attribute_006.inputs[0])
	#remove_named_attribute.Geometry -> group_output_001.Geometry
	unwrap_in_place_tool.links.new(remove_named_attribute.outputs[0], group_output_001.inputs[0])
	#selection.Selection -> evaluate_on_domain.Value
	unwrap_in_place_tool.links.new(selection.outputs[0], evaluate_on_domain.inputs[0])
	#evaluate_on_domain.Value -> set_position.Selection
	unwrap_in_place_tool.links.new(evaluate_on_domain.outputs[0], set_position.inputs[1])
	#evaluate_on_domain.Value -> duplicate_elements.Selection
	unwrap_in_place_tool.links.new(evaluate_on_domain.outputs[0], duplicate_elements.inputs[1])
	#named_attribute_002.Attribute -> split_edges.Selection
	unwrap_in_place_tool.links.new(named_attribute_002.outputs[0], split_edges.inputs[1])
	#named_attribute_003.Attribute -> uv_unwrap_001.Seam
	unwrap_in_place_tool.links.new(named_attribute_003.outputs[0], uv_unwrap_001.inputs[1])
	#named_attribute_003.Attribute -> uv_unwrap_002.Seam
	unwrap_in_place_tool.links.new(named_attribute_003.outputs[0], uv_unwrap_002.inputs[1])
	#store_named_attribute_006.Geometry -> remove_named_attribute.Geometry
	unwrap_in_place_tool.links.new(store_named_attribute_006.outputs[0], remove_named_attribute.inputs[0])
	#evaluate_on_domain.Value -> uv_unwrap_001.Selection
	unwrap_in_place_tool.links.new(evaluate_on_domain.outputs[0], uv_unwrap_001.inputs[0])
	#evaluate_on_domain.Value -> uv_unwrap_002.Selection
	unwrap_in_place_tool.links.new(evaluate_on_domain.outputs[0], uv_unwrap_002.inputs[0])
	#evaluate_on_domain.Value -> set_position_003.Selection
	unwrap_in_place_tool.links.new(evaluate_on_domain.outputs[0], set_position_003.inputs[1])
	#evaluate_on_domain.Value -> set_position_001.Selection
	unwrap_in_place_tool.links.new(evaluate_on_domain.outputs[0], set_position_001.inputs[1])
	#evaluate_on_domain.Value -> store_named_attribute_003.Selection
	unwrap_in_place_tool.links.new(evaluate_on_domain.outputs[0], store_named_attribute_003.inputs[1])
	#evaluate_on_domain.Value -> store_named_attribute_006.Selection
	unwrap_in_place_tool.links.new(evaluate_on_domain.outputs[0], store_named_attribute_006.inputs[1])
	#string.String -> named_attribute.Name
	unwrap_in_place_tool.links.new(string.outputs[0], named_attribute.inputs[0])
	#string.String -> store_named_attribute_003.Name
	unwrap_in_place_tool.links.new(string.outputs[0], store_named_attribute_003.inputs[2])
	#string.String -> store_named_attribute_004.Name
	unwrap_in_place_tool.links.new(string.outputs[0], store_named_attribute_004.inputs[2])
	#string.String -> store_named_attribute_006.Name
	unwrap_in_place_tool.links.new(string.outputs[0], store_named_attribute_006.inputs[2])
	#string.String -> named_attribute_001.Name
	unwrap_in_place_tool.links.new(string.outputs[0], named_attribute_001.inputs[0])
	#value.Value -> uv_unwrap_001.Margin
	unwrap_in_place_tool.links.new(value.outputs[0], uv_unwrap_001.inputs[2])
	#value.Value -> uv_unwrap_002.Margin
	unwrap_in_place_tool.links.new(value.outputs[0], uv_unwrap_002.inputs[2])
	#boolean.Boolean -> uv_unwrap_002.Fill Holes
	unwrap_in_place_tool.links.new(boolean.outputs[0], uv_unwrap_002.inputs[3])
	#boolean.Boolean -> uv_unwrap_001.Fill Holes
	unwrap_in_place_tool.links.new(boolean.outputs[0], uv_unwrap_001.inputs[3])
	#string_001.String -> named_attribute_002.Name
	unwrap_in_place_tool.links.new(string_001.outputs[0], named_attribute_002.inputs[0])
	#string_001.String -> named_attribute_003.Name
	unwrap_in_place_tool.links.new(string_001.outputs[0], named_attribute_003.inputs[0])
	#bounding_box_1.Min -> vector_math_1.Vector
	unwrap_in_place_tool.links.new(bounding_box_1.outputs[1], vector_math_1.inputs[0])
	#bounding_box_1.Max -> vector_math_1.Vector
	unwrap_in_place_tool.links.new(bounding_box_1.outputs[2], vector_math_1.inputs[1])
	#grid.Mesh -> transform_geometry.Geometry
	unwrap_in_place_tool.links.new(grid.outputs[0], transform_geometry.inputs[0])
	#transform_geometry.Geometry -> switch_003.True
	unwrap_in_place_tool.links.new(transform_geometry.outputs[0], switch_003.inputs[2])
	#vector_math_001_1.Vector -> vector_math_002.Vector
	unwrap_in_place_tool.links.new(vector_math_001_1.outputs[0], vector_math_002.inputs[0])
	#bounding_box_1.Min -> vector_math_001_1.Vector
	unwrap_in_place_tool.links.new(bounding_box_1.outputs[1], vector_math_001_1.inputs[0])
	#bounding_box_1.Max -> vector_math_001_1.Vector
	unwrap_in_place_tool.links.new(bounding_box_1.outputs[2], vector_math_001_1.inputs[1])
	#vector_math_002.Vector -> transform_geometry.Translation
	unwrap_in_place_tool.links.new(vector_math_002.outputs[0], transform_geometry.inputs[1])
	#vector_math_1.Vector -> vector_math_003.Vector
	unwrap_in_place_tool.links.new(vector_math_1.outputs[0], vector_math_003.inputs[0])
	#vector_math_003.Value -> grid.Size X
	unwrap_in_place_tool.links.new(vector_math_003.outputs[1], grid.inputs[0])
	#vector_math_003.Value -> grid.Size Y
	unwrap_in_place_tool.links.new(vector_math_003.outputs[1], grid.inputs[1])
	#domain_size.Point Count -> compare_002.A
	unwrap_in_place_tool.links.new(domain_size.outputs[0], compare_002.inputs[0])
	#merge_by_distance_002.Geometry -> switch_003.False
	unwrap_in_place_tool.links.new(merge_by_distance_002.outputs[0], switch_003.inputs[1])
	#compare_002.Result -> switch_003.Switch
	unwrap_in_place_tool.links.new(compare_002.outputs[0], switch_003.inputs[0])
	#bounding_box_1.Bounding Box -> merge_by_distance_002.Geometry
	unwrap_in_place_tool.links.new(bounding_box_1.outputs[0], merge_by_distance_002.inputs[0])
	#merge_by_distance_002.Geometry -> domain_size.Geometry
	unwrap_in_place_tool.links.new(merge_by_distance_002.outputs[0], domain_size.inputs[0])
	#set_position_002.Geometry -> bounding_box_1.Geometry
	unwrap_in_place_tool.links.new(set_position_002.outputs[0], bounding_box_1.inputs[0])
	#string.String -> named_attribute_004.Name
	unwrap_in_place_tool.links.new(string.outputs[0], named_attribute_004.inputs[0])
	#named_attribute_004.Attribute -> set_position_001.Position
	unwrap_in_place_tool.links.new(named_attribute_004.outputs[0], set_position_001.inputs[2])
	#store_named_attribute_003.Geometry -> duplicate_elements_002.Geometry
	unwrap_in_place_tool.links.new(store_named_attribute_003.outputs[0], duplicate_elements_002.inputs[0])
	#duplicate_elements.Geometry -> set_position_002.Geometry
	unwrap_in_place_tool.links.new(duplicate_elements.outputs[0], set_position_002.inputs[0])
	#named_attribute.Attribute -> set_position_002.Position
	unwrap_in_place_tool.links.new(named_attribute.outputs[0], set_position_002.inputs[2])
	#set_position_001.Geometry -> duplicate_elements_003.Geometry
	unwrap_in_place_tool.links.new(set_position_001.outputs[0], duplicate_elements_003.inputs[0])
	#evaluate_on_domain.Value -> duplicate_elements_003.Selection
	unwrap_in_place_tool.links.new(evaluate_on_domain.outputs[0], duplicate_elements_003.inputs[1])
	#switch_003.Output -> switch_004.False
	unwrap_in_place_tool.links.new(switch_003.outputs[0], switch_004.inputs[1])
	#switch_004.Output -> group_001.Geometry
	unwrap_in_place_tool.links.new(switch_004.outputs[0], group_001.inputs[0])
	#grid_001.Mesh -> transform_geometry_001.Geometry
	unwrap_in_place_tool.links.new(grid_001.outputs[0], transform_geometry_001.inputs[0])
	#transform_geometry_001.Geometry -> switch_004.True
	unwrap_in_place_tool.links.new(transform_geometry_001.outputs[0], switch_004.inputs[2])
	#domain_size.Point Count -> compare_003.A
	unwrap_in_place_tool.links.new(domain_size.outputs[0], compare_003.inputs[0])
	#compare_003.Result -> switch_004.Switch
	unwrap_in_place_tool.links.new(compare_003.outputs[0], switch_004.inputs[0])
	#position_1.Position -> store_named_attribute.Value
	unwrap_in_place_tool.links.new(position_1.outputs[0], store_named_attribute.inputs[3])
	#group_input_001.Geometry -> store_named_attribute.Geometry
	unwrap_in_place_tool.links.new(group_input_001.outputs[0], store_named_attribute.inputs[0])
	#store_named_attribute.Geometry -> split_edges.Mesh
	unwrap_in_place_tool.links.new(store_named_attribute.outputs[0], split_edges.inputs[0])
	#named_attribute_005.Attribute -> set_position_003.Position
	unwrap_in_place_tool.links.new(named_attribute_005.outputs[0], set_position_003.inputs[2])
	#evaluate_on_domain.Value -> store_named_attribute.Selection
	unwrap_in_place_tool.links.new(evaluate_on_domain.outputs[0], store_named_attribute.inputs[1])
	return unwrap_in_place_tool

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


	if BLENDER_VERSION <= (4,4,10):
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
	else:
		set_shade_smooth_001 = sharpfromuvislands.nodes.new("GeometryNodeSetMeshNormal")

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
		uv_islands_boundaries.links.new(corners_of_edge_002.outputs[0], evaluate_at_index_003.inputs["Index"])
		#offset_corner_in_face.Corner Index -> evaluate_at_index_001.Index
		uv_islands_boundaries.links.new(offset_corner_in_face.outputs[0], evaluate_at_index_001.inputs["Index"])
		#edge_neighbors_001.Face Count -> compare_003.A
		uv_islands_boundaries.links.new(edge_neighbors_001.outputs[0], compare_003.inputs[2])
		#compare_002.Result -> boolean_math_001.Boolean
		uv_islands_boundaries.links.new(compare_002.outputs[0], boolean_math_001.inputs[1])
		#evaluate_at_index_002.Value -> compare_002.A
		uv_islands_boundaries.links.new(evaluate_at_index_002.outputs[0], compare_002.inputs[4])
		#offset_corner_in_face_001.Corner Index -> evaluate_at_index_002.Index
		uv_islands_boundaries.links.new(offset_corner_in_face_001.outputs[0], evaluate_at_index_002.inputs["Index"])
		#corners_of_edge.Corner Index -> evaluate_at_index.Index
		uv_islands_boundaries.links.new(corners_of_edge.outputs[0], evaluate_at_index.inputs["Index"])
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
		uv_islands_boundaries.links.new(group_input_1.outputs[1], evaluate_at_index_001.inputs["Value"])
		#group_input_1.UV -> evaluate_at_index.Value
		uv_islands_boundaries.links.new(group_input_1.outputs[1], evaluate_at_index.inputs["Value"])
		#group_input_1.UV -> evaluate_at_index_002.Value
		uv_islands_boundaries.links.new(group_input_1.outputs[1], evaluate_at_index_002.inputs["Value"])
		#group_input_1.UV -> evaluate_at_index_003.Value
		uv_islands_boundaries.links.new(group_input_1.outputs[1], evaluate_at_index_003.inputs["Value"])
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

	if BLENDER_VERSION <= (4,4,10):
		set_shade_smooth_002.location = (1176.4324951171875, 133.21624755859375)
		set_shade_smooth_003.location = (1180.4324951171875, 140.21624755859375)
	group.location = (667.629150390625, 119.90283203125)
	face_group_boundaries.location = (1063.4482421875, -47.62242889404297)
	edges_to_face_groups.location = (898.8531494140625, -48.52994155883789)
	switch.location = (1245.561767578125, -37.500709533691406)

	#initialize sharpfromuvislands links
	#set_shade_smooth_001.Geometry -> set_shade_smooth_002.Geometry
	if BLENDER_VERSION <= (4,4,10):
		sharpfromuvislands.links.new(set_shade_smooth_001.outputs[0], set_shade_smooth_002.inputs[0])
		#set_shade_smooth_002.Geometry -> set_shade_smooth_003.Geometry
		sharpfromuvislands.links.new(set_shade_smooth_002.outputs[0], set_shade_smooth_003.inputs[0])
		#set_shade_smooth_003.Geometry -> group_output.Geometry
		sharpfromuvislands.links.new(set_shade_smooth_003.outputs[0], group_output.inputs[0])
		#group.Geometry -> set_shade_smooth_001.Geometry
		sharpfromuvislands.links.new(group.outputs[0], set_shade_smooth_001.inputs[0])
		#switch.Output -> set_shade_smooth_003.Selection
		sharpfromuvislands.links.new(switch.outputs[0], set_shade_smooth_003.inputs[1])
	else:
		sharpfromuvislands.links.new(set_shade_smooth_001.outputs[0], group_output.inputs[0])
		sharpfromuvislands.links.new(group.outputs[0], set_shade_smooth_001.inputs[0])
		sharpfromuvislands.links.new(switch.outputs[0], set_shade_smooth_001.inputs[2])

	#group_input.Geometry -> group.Geometry
	sharpfromuvislands.links.new(group_input.outputs[0], group.inputs[0])
	#group_input.UV -> group.UV
	sharpfromuvislands.links.new(group_input.outputs[1], group.inputs[1])

	#edges_to_face_groups.Face Group ID -> face_group_boundaries.Face Group ID
	sharpfromuvislands.links.new(edges_to_face_groups.outputs[0], face_group_boundaries.inputs[0])
	#group.UV Borders -> edges_to_face_groups.Boundary Edges
	sharpfromuvislands.links.new(group.outputs[1], edges_to_face_groups.inputs[0])
	#group.UV Borders -> switch.False
	sharpfromuvislands.links.new(group.outputs[1], switch.inputs[1])
	#face_group_boundaries.Boundary Edges -> switch.True
	sharpfromuvislands.links.new(face_group_boundaries.outputs[0], switch.inputs[2])
	#group_input.Only UV Island Borders -> switch.Switch
	sharpfromuvislands.links.new(group_input.outputs[2], switch.inputs[0])
	return sharpfromuvislands