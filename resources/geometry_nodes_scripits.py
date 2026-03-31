import bpy

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

	triplanar_uv_mapping.is_modifier = True
	
	#initialize triplanar_uv_mapping nodes
	#triplanar_uv_mapping interface
	#Socket Geometry
	geometry_socket = triplanar_uv_mapping.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
	geometry_socket.attribute_domain = 'POINT'
	
	#Socket Geometry
	geometry_socket_1 = triplanar_uv_mapping.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
	geometry_socket_1.attribute_domain = 'POINT'
	
	#Socket Selection
	selection_socket = triplanar_uv_mapping.interface.new_socket(name = "Selection", in_out='INPUT', socket_type = 'NodeSocketBool')
	selection_socket.attribute_domain = 'POINT'
	selection_socket.hide_value = True
	
	#Socket Name
	name_socket = triplanar_uv_mapping.interface.new_socket(name = "Name", in_out='INPUT', socket_type = 'NodeSocketString')
	name_socket.attribute_domain = 'POINT'
	
	#Socket X
	x_socket = triplanar_uv_mapping.interface.new_socket(name = "X", in_out='INPUT', socket_type = 'NodeSocketFloat')
	x_socket.subtype = 'NONE'
	x_socket.default_value = 0.5
	x_socket.min_value = -10000.0
	x_socket.max_value = 10000.0
	x_socket.attribute_domain = 'POINT'
	
	#Socket Y
	y_socket = triplanar_uv_mapping.interface.new_socket(name = "Y", in_out='INPUT', socket_type = 'NodeSocketFloat')
	y_socket.subtype = 'NONE'
	y_socket.default_value = 0.5
	y_socket.min_value = -10000.0
	y_socket.max_value = 10000.0
	y_socket.attribute_domain = 'POINT'
	
	#Socket Scale
	scale_socket = triplanar_uv_mapping.interface.new_socket(name = "Scale", in_out='INPUT', socket_type = 'NodeSocketFloat')
	scale_socket.subtype = 'NONE'
	scale_socket.default_value = 0.5
	scale_socket.min_value = -10000.0
	scale_socket.max_value = 10000.0
	scale_socket.attribute_domain = 'POINT'
	
	#Socket Angle
	angle_socket = triplanar_uv_mapping.interface.new_socket(name = "Angle", in_out='INPUT', socket_type = 'NodeSocketFloat')
	angle_socket.subtype = 'ANGLE'
	angle_socket.default_value = 0.0
	angle_socket.min_value = -360.0
	angle_socket.max_value = 360.0
	angle_socket.attribute_domain = 'POINT'
	
	
	#node Group Input
	group_input = triplanar_uv_mapping.nodes.new("NodeGroupInput")
	group_input.name = "Group Input"
	group_input.outputs[7].hide = True
	
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
	
	#node Vector Math.002
	vector_math_002 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
	vector_math_002.name = "Vector Math.002"
	vector_math_002.operation = 'SCALE'
	vector_math_002.inputs[1].hide = True
	vector_math_002.inputs[2].hide = True
	vector_math_002.outputs[1].hide = True
	#Vector_001
	vector_math_002.inputs[1].default_value = (0.0, 0.0, 0.0)
	#Vector_002
	vector_math_002.inputs[2].default_value = (0.0, 0.0, 0.0)
	
	#node Vector Math.003
	vector_math_003 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
	vector_math_003.name = "Vector Math.003"
	vector_math_003.operation = 'ADD'
	vector_math_003.inputs[2].hide = True
	vector_math_003.inputs[3].hide = True
	vector_math_003.outputs[1].hide = True
	#Vector_002
	vector_math_003.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Scale
	vector_math_003.inputs[3].default_value = 1.0
	
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
	#Rotation
	vector_rotate_001.inputs[4].default_value = (0.0, 0.0, 0.0)
	
	#node Separate XYZ.001
	separate_xyz_001 = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
	separate_xyz_001.name = "Separate XYZ.001"
	
	#node Compare.002
	compare_002 = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
	compare_002.name = "Compare.002"
	compare_002.data_type = 'FLOAT'
	compare_002.mode = 'ELEMENT'
	compare_002.operation = 'GREATER_THAN'
	#A_INT
	compare_002.inputs[2].default_value = 0
	#B_INT
	compare_002.inputs[3].default_value = 0
	#A_VEC3
	compare_002.inputs[4].default_value = (0.0, 0.0, 0.0)
	#B_VEC3
	compare_002.inputs[5].default_value = (0.0, 0.0, 0.0)
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
	compare_002.inputs[12].default_value = 0.0010000000474974513
	
	#node Compare.003
	compare_003 = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
	compare_003.name = "Compare.003"
	compare_003.data_type = 'FLOAT'
	compare_003.mode = 'ELEMENT'
	compare_003.operation = 'GREATER_THAN'
	#A_INT
	compare_003.inputs[2].default_value = 0
	#B_INT
	compare_003.inputs[3].default_value = 0
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
	
	#node Position
	position = triplanar_uv_mapping.nodes.new("GeometryNodeInputPosition")
	position.name = "Position"
	
	#node Vector Math
	vector_math = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
	vector_math.name = "Vector Math"
	vector_math.operation = 'MULTIPLY'
	#Vector_002
	vector_math.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Scale
	vector_math.inputs[3].default_value = 1.0
	
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
	switch_003.inputs[2].default_value = (0.0, -1.5707963705062866, 0.0)
	
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
	#Vector_001
	vector_math_001.inputs[1].default_value = (0.0, 0.0, 0.0)
	#Vector_002
	vector_math_001.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Scale
	vector_math_001.inputs[3].default_value = 1.0
	
	#node Separate XYZ
	separate_xyz = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
	separate_xyz.name = "Separate XYZ"
	
	#node Compare
	compare = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
	compare.name = "Compare"
	compare.data_type = 'FLOAT'
	compare.mode = 'ELEMENT'
	compare.operation = 'GREATER_THAN'
	#A_INT
	compare.inputs[2].default_value = 0
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
	
	#node Compare.001
	compare_001 = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
	compare_001.name = "Compare.001"
	compare_001.data_type = 'FLOAT'
	compare_001.mode = 'ELEMENT'
	compare_001.operation = 'GREATER_THAN'
	#A_INT
	compare_001.inputs[2].default_value = 0
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
	#Axis
	vector_rotate.inputs[2].default_value = (0.0, 0.0, 1.0)
	#Angle
	vector_rotate.inputs[3].default_value = 0.0
	
	#initialize triplanar_uv_mapping links
	#store_named_attribute.Geometry -> group_output.Geometry
	triplanar_uv_mapping.links.new(store_named_attribute.outputs[0], group_output.inputs[0])
	#group_input.Geometry -> store_named_attribute.Geometry
	triplanar_uv_mapping.links.new(group_input.outputs[0], store_named_attribute.inputs[0])
	#group_input.Selection -> store_named_attribute.Selection
	triplanar_uv_mapping.links.new(group_input.outputs[1], store_named_attribute.inputs[1])
	#group_input.Name -> store_named_attribute.Name
	triplanar_uv_mapping.links.new(group_input.outputs[2], store_named_attribute.inputs[2])
	#group_input.Scale -> vector_math_002.Scale
	triplanar_uv_mapping.links.new(group_input.outputs[5], vector_math_002.inputs[3])
	#vector_math_002.Vector -> vector_math_003.Vector
	triplanar_uv_mapping.links.new(vector_math_002.outputs[0], vector_math_003.inputs[0])
	#group_input.X -> combine_xyz.X
	triplanar_uv_mapping.links.new(group_input.outputs[3], combine_xyz.inputs[0])
	#group_input.Y -> combine_xyz.Y
	triplanar_uv_mapping.links.new(group_input.outputs[4], combine_xyz.inputs[1])
	#combine_xyz.Vector -> vector_math_003.Vector
	triplanar_uv_mapping.links.new(combine_xyz.outputs[0], vector_math_003.inputs[1])
	#vector_math_003.Vector -> vector_rotate_001.Vector
	triplanar_uv_mapping.links.new(vector_math_003.outputs[0], vector_rotate_001.inputs[0])
	#vector_rotate_001.Vector -> store_named_attribute.Value
	triplanar_uv_mapping.links.new(vector_rotate_001.outputs[0], store_named_attribute.inputs[3])
	#combine_xyz.Vector -> vector_rotate_001.Center
	triplanar_uv_mapping.links.new(combine_xyz.outputs[0], vector_rotate_001.inputs[1])
	#group_input.Angle -> vector_rotate_001.Angle
	triplanar_uv_mapping.links.new(group_input.outputs[6], vector_rotate_001.inputs[3])
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
	#position.Position -> vector_math.Vector
	triplanar_uv_mapping.links.new(position.outputs[0], vector_math.inputs[0])
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
	#vector_math.Vector -> vector_rotate.Vector
	triplanar_uv_mapping.links.new(vector_math.outputs[0], vector_rotate.inputs[0])
	#switch_002.Output -> vector_rotate.Rotation
	triplanar_uv_mapping.links.new(switch_002.outputs[0], vector_rotate.inputs[4])
	#vector_rotate.Vector -> vector_math_002.Vector
	triplanar_uv_mapping.links.new(vector_rotate.outputs[0], vector_math_002.inputs[0])
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
