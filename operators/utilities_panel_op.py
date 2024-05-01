import bpy
from ..utils.pref_utils import get_keyops_prefs
import tempfile
import bmesh
from bpy.props import IntProperty, FloatProperty, BoolProperty


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
    triangulate: bpy.props.BoolProperty(name="Triangulate", default=False) # type: ignore
    rename_uv_layer: bpy.props.BoolProperty(name="Rename UV Layer 0 To UVMap", default=True) # type: ignore
    join_children: bpy.props.BoolProperty(name="Join Children", default=True) # type: ignore
    scale_triplanar: bpy.props.FloatProperty(name="Scale", default=0.5) # type: ignore
    rotation_triplanar: bpy.props.FloatProperty(name="Rotation", default=0.0) # type: ignore
    axis_x: bpy.props.FloatProperty(name="X", default=0.5) # type: ignore
    axis_y: bpy.props.FloatProperty(name="Y", default=0.5 ) # type: ignore
    appy_triplanar: bpy.props.BoolProperty(name="Apply Triplanar", default=False) # type: ignore
    recalculate_normals: bpy.props.BoolProperty(name="Recalculate Normals", default=False) # type: ignore

    def draw(self, context):
        layout = self.layout
        if self.type == "offset_uv":
            if context.mode == 'EDIT_MESH':
                layout.prop(self, "true_false")
        if self.type == "Triplanar_UV_Mapping":
            layout.prop(self, "axis_x")
            layout.prop(self, "axis_y")
            layout.prop(self, "scale_triplanar")
            layout.prop(self, "rotation_triplanar")
            layout.prop(self, "appy_triplanar")
            
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
            layout.prop(self, "recalculate_normals")
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
        if bpy.app.version >= (4, 1, 0): 
            prefs = get_keyops_prefs()
            if self.type == "Triplanar_UV_Mapping":
                active_object = bpy.context.active_object
                if bpy.data.node_groups.get("Triplanar UV Mapping") is None:
                    triplanar_uv_mapping_node_group()
                for obj in bpy.context.selected_objects:
                    if obj.type == 'MESH':         
                        bpy.context.view_layer.objects.active = obj

                        if bpy.context.object.modifiers.get("Triplanar UV Mapping") is None:
                            bpy.context.object.modifiers.new('Triplanar UV Mapping', 'NODES')
                            bpy.context.object.modifiers['Triplanar UV Mapping'].node_group = bpy.data.node_groups['Triplanar UV Mapping']
                    
                        if obj.data.uv_layers.active is not None:
                            active_uv_layer_name = bpy.context.object.data.uv_layers.active.name

                        if context.mode == 'EDIT_MESH':
                            bpy.ops.object.geometry_nodes_input_attribute_toggle(input_name="Socket_2", modifier_name="Triplanar UV Mapping")
                            bpy.context.object.modifiers["Triplanar UV Mapping"]["Socket_2_attribute_name"] = "Triplanar_UV_Mapping"
                            named_attributes = bpy.context.object.data.attributes
                            attribute_name = "Triplanar_UV_Mapping"
                            set_act = named_attributes.get(attribute_name)
                            if set_act is not None:
                                select_atribute(attribute_name)
                            else:
                                mesh = bpy.context.object.data
                                mesh.attributes.new(name="Triplanar_UV_Mapping", domain='FACE', type='BOOLEAN')
                                select_atribute(attribute_name)
                        else:
                            context.object.modifiers["Triplanar UV Mapping"]["Socket_2"] = True

                        context.object.modifiers["Triplanar UV Mapping"]["Socket_3"] = active_uv_layer_name
                        context.object.modifiers["Triplanar UV Mapping"]["Socket_4"] = self.axis_x
                        context.object.modifiers["Triplanar UV Mapping"]["Socket_5"] = self.axis_y
                        context.object.modifiers["Triplanar UV Mapping"]["Socket_6"] = self.scale_triplanar
                        context.object.modifiers["Triplanar UV Mapping"]["Socket_7"] = self.rotation_triplanar
                        bpy.context.object.data.update()
                    
                        bpy.context.object.modifiers["Triplanar UV Mapping"].show_group_selector = False

                        if context.mode == 'EDIT_MESH':
                            bpy.ops.mesh.attribute_set(value_bool=True)

                if self.appy_triplanar == True:
                    for obj in bpy.context.selected_objects:
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.object.modifier_apply(modifier="Triplanar UV Mapping")

                bpy.context.view_layer.objects.active = active_object
        else:
            self.report({'ERROR'}, "This operator only works on Blender 4.1 and above, due to a bug in geometry nodes")

        if self.type == "Remove_Triplanar_UV_Mapping":
            active_object = bpy.context.active_object

            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    if bpy.context.object.modifiers.get("Triplanar UV Mapping") is not None:
                        bpy.context.object.modifiers.remove(bpy.context.object.modifiers['Triplanar UV Mapping'])
            bpy.context.view_layer.objects.active = active_object

        def add_UV_offset_modifier():
            bpy.context.view_layer.objects.active = obj
            
            if bpy.context.object.modifiers.get("Offset UV") is None:
                bpy.context.object.modifiers.new('Offset UV', 'NODES')
                bpy.context.object.modifiers['Offset UV'].node_group = bpy.data.node_groups['Offset UV']
                if bpy.context.mode == 'OBJECT':
                    bpy.context.object.modifiers["Offset UV"]["Socket_2"] = True

                if bpy.context.mode == 'EDIT_MESH': 
                    bpy.ops.object.geometry_nodes_input_attribute_toggle(input_name="Socket_2", modifier_name="Offset UV")
                    bpy.context.object.modifiers["Offset UV"]["Socket_2_attribute_name"] = "Offset_UV"

        if self.type == "offset_uv":
            if bpy.app.version >= (4, 1, 0): 
                active_object = bpy.context.active_object
                if bpy.data.node_groups.get("Offset UV") is None:
                    offset_uv()
                for obj in bpy.context.selected_objects:
                    if obj.type == 'MESH':
                        if bpy.context.mode == 'OBJECT':
                            add_UV_offset_modifier()
                        if bpy.context.mode == 'EDIT_MESH':
                            if obj.data.total_vert_sel > 0:
                                add_UV_offset_modifier()

                            if bpy.context.mode == 'EDIT_MESH':
                                if obj.data.total_vert_sel > 0:
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
                                    
                        bpy.context.object.modifiers["Offset UV"].show_group_selector = False
                bpy.context.view_layer.objects.active = active_object
            else:
                self.report({'ERROR'}, "This operator only works on Blender 4.1 and above, due to a bug in geometry nodes")

        if self.type == "Remove_Offset_UV":
            active_object = bpy.context.active_object

            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    if bpy.context.object.modifiers.get("Offset UV") is not None:
                        bpy.context.object.modifiers.remove(bpy.context.object.modifiers['Offset UV'])
            bpy.context.view_layer.objects.active = active_object

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
                if bpy.app.version >= (4, 1, 0):
                        pass
                else:
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
            bpy.ops.mesh.duplicate_move(MESH_OT_duplicate={"mode":1}, TRANSFORM_OT_translate={"value":(0, 0, 0), "orient_type":'GLOBAL', "orient_matrix":((0, 0, 0), (0, 0, 0), (0, 0, 0)), "orient_matrix_type":'GLOBAL', "constraint_axis":(False, False, False), "mirror":False, "use_proportional_edit":False, "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "use_proportional_connected":False, "use_proportional_projected":False, "snap":False, "snap_elements":{'INCREMENT'}, "use_snap_project":False, "snap_target":'CLOSEST', "use_snap_self":True, "use_snap_edit":True, "use_snap_nonedit":True, "use_snap_selectable":False, "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0), "gpencil_strokes":False, "cursor_transform":False, "texture_space":False, "remove_on_cancel":False, "use_duplicated_keyframes":False, "view2d_edge_pan":False, "release_confirm":False, "use_accurate":False, "use_automerge_and_split":False})
            bpy.ops.mesh.separate(type='SELECTED')
            duplicated_object = bpy.context.selected_objects[1]
            duplicated_object.modifiers.clear()
            current_name = duplicated_object.name
            duplicated_object.name = current_name + "_normal_transfer"

            bpy.ops.object.editmode_toggle()

            bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
            if bpy.app.version >= (4, 1, 0):
                pass
            else:
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
                    elif bpy.context.scene.bevel_segments_type == 'BY_OFFSET':
                        if bpy.context.scene.compensate_for_scale == True:
                            bevel_offset = bpy.context.scene.bevel_offset / get_scale(selected_obj)
                        else:
                            bevel_offset = bpy.context.scene.bevel_offset
                        for modifier in selected_obj.modifiers:  
                            if modifier.type == 'BEVEL':
                                if modifier.width < bevel_offset:
                                    modifier.segments = bpy.context.scene.bevel_segment_amount

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
                    if bpy.context.scene.bevel_segments_type == 'BY_OFFSET':
                        if bpy.context.scene.compensate_for_scale == True:
                            bevel_offset = bpy.context.scene.bevel_offset / get_scale(selected_obj)
                        else:
                            bevel_offset = bpy.context.scene.bevel_offset
                        for modifier in selected_obj.modifiers:  
                            if modifier.type == 'BEVEL':
                                if modifier.width < bevel_offset:
                                    segment_amount = modifier.segments + (modifier.segments * bpy.context.scene.bevel_segment_by_percent / 100)
                                    modifier.segments = int(segment_amount)
                                                            
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
                            if bpy.context.scene.bevel_segments_type == 'BY_OFFSET':
                                if modifier.width < bevel_offset:
                                    modifier.show_viewport = False
                                                                             
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
            if len(selected_objects) == 0:
                self.report({'WARNING'}, "No Objects Selected")
                return {'CANCELLED'}
        
            selected_objects = [obj for obj in selected_objects if (obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'INSTANCE') and obj.display_type != 'WIRE']
            if bpy.context.mode == 'EDIT_MESH':                                                             
                bpy.ops.object.mode_set(mode='OBJECT')
            
            cursor_loc = context.scene.cursor.location
            pos2 = (cursor_loc[0], cursor_loc[1], cursor_loc[2])
            bpy.ops.view3d.snap_cursor_to_active()

            if self.apply_instances == True:
                bpy.ops.object.duplicates_make_real()


            bpy.ops.object.select_all(action='DESELECT')

            for selected_obj in selected_objects:
                selected_obj.select_set(True)

            bpy.context.view_layer.objects.active = selected_objects[0]

            bpy.ops.object.make_single_user(object=True, obdata=True, material=False, animation=False, obdata_animation=False)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            bpy.ops.object.convert(target='MESH')

            if self.rename_uv_layer == True:
                for selected_obj in selected_objects:
                    if selected_obj.data.uv_layers.active is not None:
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

            if self.recalculate_normals == True:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.normals_make_consistent(inside=False)
                bpy.ops.object.mode_set(mode='OBJECT')

            #perf_time = time.time() - perf_time
            #print(f"Total Selection Time: {perf_time:.4f} seconds")
            #can crash sometimes, dont know why, debug
            #needs a way to make sure to presver normals, maybe add custom split normals data if it does not have it?, no does not work

        if self.type == "Quick_Apply_All_Modifiers":
            #nice when modifiers are very slow to apply, but the final result is not that high-poly - test decmiation modifier 32 seconds to 1.5 seconds
            selected_objects = bpy.context.selected_objects
            if len(selected_objects) == 0:
                self.report({'WARNING'}, "No Objects Selected")
                return {'CANCELLED'}
        
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

        if self.type == "un_subdivide_cylinder":
            for obj in bpy.context.selected_objects:
                if obj.data.total_vert_sel > 0:
                    context.view_layer.objects.active = obj
                    obj.data.attributes.new(name='Edge_Un_Subdivied_Cylinder', type='BOOLEAN', domain='EDGE')
                    obj.data.attributes.active = obj.data.attributes.get('Edge_Un_Subdivied_Cylinder')
                    obj.data.update()
                    bpy.ops.mesh.attribute_set(value_bool=True)

            for obj in bpy.context.selected_objects:
                if obj.data.total_vert_sel > 0:    
                    bpy.ops.mesh.loop_multi_select('EXEC_DEFAULT', True, ring=True)
                    bpy.ops.mesh.select_nth('EXEC_DEFAULT', True, skip=1, nth=1, offset=0)
                    bpy.ops.mesh.loop_multi_select('EXEC_DEFAULT', True, ring=False)
                    bpy.ops.mesh.dissolve_mode('EXEC_DEFAULT', True, use_verts=True)

            for obj in bpy.context.selected_objects:
                if obj.data.attributes.get('Edge_Un_Subdivied_Cylinder') is not None:
                    context.view_layer.objects.active = obj
                    bpy.ops.mesh.select_by_attribute()
                    obj.data.attributes.remove(obj.data.attributes.get('Edge_Un_Subdivied_Cylinder'))
                    
        if self.type == "subdivide_cylinder":
            bpy.ops.mesh.loop_multi_select(ring=False)
            bpy.ops.mesh.loop_multi_select(ring=True)
            for obj in bpy.context.selected_objects:
                if obj.data.total_vert_sel > 0:
                    context.view_layer.objects.active = obj
                    obj.data.attributes.new(name='Edge_Subdivied_Cylinder', type='BOOLEAN', domain='EDGE')
                    obj.data.attributes.active = obj.data.attributes.get('Edge_Subdivied_Cylinder')
                    obj.data.update()
                    bpy.ops.mesh.attribute_set(value_bool=True)
            bpy.ops.mesh.bevel(offset_type='PERCENT', offset=0.282053, offset_pct=25, affect='EDGES')
            bpy.ops.mesh.select_all(action='DESELECT')

            for obj in bpy.context.selected_objects:
                if obj.data.attributes.get('Edge_Subdivied_Cylinder') is not None:
                    context.view_layer.objects.active = obj
                    bpy.ops.mesh.select_by_attribute()
                    obj.data.attributes.remove(obj.data.attributes.get('Edge_Subdivied_Cylinder'))

        if self.type == "change_cylinder_segments_modifier":
            bpy.ops.mesh.select_all(action='INVERT')
            bpy.ops.mesh.delete(type='EDGE')
            obj = bpy.context.active_object
            obj.modifiers.new(type='SCREW', name='Screw')
            bpy.context.object.modifiers["Screw"].use_normal_calculate = True
            bpy.context.object.modifiers["Screw"].use_merge_vertices = True
        
        if self.type == "clear_custom_normals":
            selection = bpy.context.selected_objects

            for obj in selection:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.mesh.customdata_custom_splitnormals_clear()

        return {'FINISHED'}
    
    
    def register():
        bpy.utils.register_class(ObjectModePanel)
        bpy.utils.register_class(UtilitiesPanel)
        bpy.utils.register_class(EditModePanel)
        bpy.utils.register_class(SmartExtrude)
        bpy.utils.register_class(ExtrudeEdgeByNormal)
    def unregister():
        bpy.utils.unregister_class(ObjectModePanel)
        bpy.utils.unregister_class(UtilitiesPanel)
        bpy.utils.unregister_class(EditModePanel)
        bpy.utils.unregister_class(SmartExtrude)
        bpy.utils.unregister_class(ExtrudeEdgeByNormal)

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
        bpy.types.VIEW3D_MT_edit_mesh_extrude.prepend(menu_extrude)
    def unregister():
        bpy.types.VIEW3D_MT_edit_mesh_extrude.remove(menu_extrude)
def menu_extrude(self, context):
    layout = self.layout
    layout.operator(SmartExtrude.bl_idname, text="Smart Extrude (Slow, Outdated)")



class ExtrudeEdgeByNormal(bpy.types.Operator):
    bl_idname = "mesh.extrude_edge_by_normal"
    bl_label = "Extrude Edge by Normal"
    bl_options = {'REGISTER', 'UNDO'}

    offset: bpy.props.FloatProperty(name="Offset", default=1) # type: ignore

    def execute(self, context):
        if bpy.app.version <= (4, 0, 2):
            self.report({'WARNING'}, "This operator is not supported in Blender 4.0.2 or lower due to a bug in the Geometry Nodes")
            return {'CANCELLED'}
        else:
            def extrude_edge_by_normal_node_group():
                extrude_edge_by_normal = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Extrude Edge By Normal")

                extrude_edge_by_normal.is_tool = True
                extrude_edge_by_normal.is_mode_edit = True
                extrude_edge_by_normal.is_mode_sculpt = False
                extrude_edge_by_normal.is_type_curve = False
                extrude_edge_by_normal.is_type_mesh = True
                extrude_edge_by_normal.is_type_point_cloud = False
                
                #initialize extrude_edge_by_normal nodes
                #extrude_edge_by_normal interface
                #Socket Geometry
                geometry_socket = extrude_edge_by_normal.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
                geometry_socket.attribute_domain = 'POINT'
                
                #Socket Geometry
                geometry_socket_1 = extrude_edge_by_normal.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
                geometry_socket_1.attribute_domain = 'POINT'
                
                
                #node Group Input
                group_input = extrude_edge_by_normal.nodes.new("NodeGroupInput")
                group_input.name = "Group Input"
                
                #node Group Output
                group_output = extrude_edge_by_normal.nodes.new("NodeGroupOutput")
                group_output.name = "Group Output"
                group_output.is_active_output = True
                
                #node Extrude Mesh
                extrude_mesh = extrude_edge_by_normal.nodes.new("GeometryNodeExtrudeMesh")
                extrude_mesh.name = "Extrude Mesh"
                extrude_mesh.mode = 'EDGES'
                #Offset Scale
                extrude_mesh.inputs[3].default_value = 1.0
                #Individual
                extrude_mesh.inputs[4].default_value = True
                
                #node Normal
                normal = extrude_edge_by_normal.nodes.new("GeometryNodeInputNormal")
                normal.name = "Normal"
                
                #node Selection
                selection = extrude_edge_by_normal.nodes.new("GeometryNodeToolSelection")
                selection.name = "Selection"
                
                #node Set Selection
                set_selection = extrude_edge_by_normal.nodes.new("GeometryNodeToolSetSelection")
                set_selection.name = "Set Selection"
                
                #Set locations
                group_input.location = (-956.7882690429688, -106.79387664794922)
                group_output.location = (32.99273681640625, -42.937740325927734)
                extrude_mesh.location = (-449.79449462890625, -33.02903366088867)
                normal.location = (-743.4354248046875, -157.43838500976562)
                selection.location = (-722.5401000976562, -86.97645568847656)
                set_selection.location = (-233.14840698242188, -84.7745132446289)
                
                #initialize extrude_edge_by_normal links
                #group_input.Geometry -> extrude_mesh.Mesh
                extrude_edge_by_normal.links.new(group_input.outputs[0], extrude_mesh.inputs[0])
                #normal.Normal -> extrude_mesh.Offset
                extrude_edge_by_normal.links.new(normal.outputs[0], extrude_mesh.inputs[2])
                #selection.Selection -> extrude_mesh.Selection
                extrude_edge_by_normal.links.new(selection.outputs[0], extrude_mesh.inputs[1])
                #extrude_mesh.Mesh -> set_selection.Geometry
                extrude_edge_by_normal.links.new(extrude_mesh.outputs[0], set_selection.inputs[0])
                #extrude_mesh.Top -> set_selection.Selection
                extrude_edge_by_normal.links.new(extrude_mesh.outputs[1], set_selection.inputs[1])
                #set_selection.Geometry -> group_output.Geometry
                extrude_edge_by_normal.links.new(set_selection.outputs[0], group_output.inputs[0])
                return extrude_edge_by_normal

            if "Extrude Edge By Normal" not in bpy.data.node_groups:
                extrude_edge_by_normal_node_group()

            bpy.data.node_groups["Extrude Edge By Normal"].is_mode_edit = True
            bpy.data.node_groups["Extrude Edge By Normal"].nodes["Extrude Mesh"].inputs[3].default_value = self.offset
            bpy.ops.geometry.execute_node_group(name="Extrude Edge By Normal")
            bpy.data.node_groups["Extrude Edge By Normal"].is_mode_edit = False

        return {'FINISHED'}
    
def register():
    bpy.types.VIEW3D_MT_edit_mesh_extrude_pre.prepend(menu_extrude)
def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_extrude_pre.remove(menu_extrude)

def menu_extrude(self, context):
    if bpy.context.mode == 'EDIT_MESH' and not bpy.context.tool_settings.mesh_select_mode[2] == True:
        self.layout.operator(ExtrudeEdgeByNormal.bl_idname, text="Extrude Edge by Normal")

class UtilitiesPanel(bpy.types.Panel):
    bl_description = "Utilities Panel"
    bl_label = "Modifiers"
    bl_idname = "KEYOPS_PT_utilities_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'

    @classmethod
    def poll(cls, context):
        return get_keyops_prefs().enable_utilities_panel_op
    
    def draw(self, context):
        layout = self.layout

        def draw_modifiers_operations():
            col = layout.column(align=True)
            row = col.row(align=True)
            if bpy.context.mode == 'EDIT_MESH':
                row.operator("keyops.utilities_panel_op", text="Offset UV").type = "offset_uv"   
                row.operator("keyops.utilities_panel_op", text="Remove").type = "Remove_Offset_UV"
            else:   
                row.operator("keyops.utilities_panel_op", text="Offset UV").type = "offset_uv"
                row.operator("keyops.utilities_panel_op", text="Remove").type = "Remove_Offset_UV"
            row = col.row(align=True)
            row.operator("keyops.utilities_panel_op", text="Triplanar UV").type = "Triplanar_UV_Mapping"
            row.operator("keyops.utilities_panel_op", text="Remove").type = "Remove_Triplanar_UV_Mapping"
        
        if get_keyops_prefs().enable_uv_tools:
            draw_modifiers_operations()
        
        row = layout.row()
        row.label(text="Set Normals")
        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator("keyops.utilities_panel_op", text="Sphere", icon= "META_BALL").type = "set_sphere_normal"
        row.operator("keyops.utilities_panel_op", text="Selection", icon= "UV_FACESEL").type = "set_normal_from_selection"
        row = col.row(align=True)
        row.operator("keyops.utilities_panel_op", text="Clear Custom Normals").type = "clear_custom_normals"
        
        if context.mode == 'OBJECT':
            layout.separator()
            layout = self.layout
            col = layout.column(align=False)
            row = col.row(align=False)

            row.prop(context.scene, "bevel_segments_type", text="Set")
            row = col.row(align=False)
            col = layout.column(align=True)

            row = col.row(align=True)
            row.operator("keyops.utilities_panel_op", text="Set Value", icon= "MOD_BEVEL").type = "set_bevel_segment_amount" 
            row.operator("keyops.utilities_panel_op", text="Set by %", icon= "MOD_BEVEL").type = "bevel_segment_amount_by_%"
            row = col.row(align=True)
            row.prop(context.scene, "bevel_segment_amount", text="")
            row.prop(context.scene, "bevel_segment_by_percent", text="")

            row = layout.row()
            row.operator("keyops.utilities_panel_op", text="Hide by Offset", icon= "MOD_BEVEL").type = "hide_bevels_by_offset"
            row = layout.row()
            row.prop(context.scene, "compensate_for_scale", text="Scale")
            row.prop(context.scene, "bevel_offset", text="")

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
            pass
            # header, panel_changde_meshes = layout.panel(idname="Mark Changde Objects",  default_closed=True)
            # header.label(text="Mark Changde Objects")
            # if panel_changde_meshes:
            #     change_meshes_draw()
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
        bpy.types.Scene.bevel_segments_type = bpy.props.EnumProperty(name="bevel_segments_type", items=[('ALL', 'All Bevelse', 'All Bevelse'), ('TOP', 'First Bevel', 'First Bevel'), ('BOTTOM', 'Last Bevel', 'Last Bevel'), ('BY_OFFSET', 'By Bevel Offset', 'By Bevel Offset')], default='ALL', description="Set based on bevel settings")
    def unregister():
        del bpy.types.Scene.bevel_segment_amount
        del bpy.types.Scene.bevel_segment_by_percent
        del bpy.types.Scene.bevel_offset
        del bpy.types.Scene.compensate_for_scale
        del bpy.types.Scene.bevel_segments_type

class EditModePanel(bpy.types.Panel):
    bl_description = "Modeling Panel"
    bl_label = "Edit Mode"
    bl_idname = "KEYOPS_PT_modeling_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            return True
    
    def draw(self, context):
        sel_mode = bpy.context.tool_settings.mesh_select_mode[:]

        layout = self.layout
        col = layout.column(align=True)

        #uv
        row = col.row(align=True)
        row.operator("keyops.seam_by_angle", text="Seam by Angle", icon= "MOD_EDGESPLIT")
        row = col.row(align=True)

        #edit mesh
        row.label(text="Edit Mesh")
        row = col.row(align=True)
        row.operator("mesh.extrude_edge_by_normal", text="Extrude Edge by Normal")
        row = col.row(align=True)
        row.operator("mesh.flip_normals", text="Flip")
        row.operator("mesh.normals_make_consistent", text="Recalculate")
        row = col.row(align=True)
        row.operator("mesh.remove_doubles", text="Weld")
        row.operator("mesh.bridge_edge_loops", text="Bridge")
        row = col.row(align=True)
        row.operator("mesh.connect2", text="Connect")
        row.operator("mesh.subdivide", text="Subdivide")
        row = col.row(align=True)
        row.operator("mesh.set_edge_flow", text="Set Flow")
        row.operator("mesh.edge_face_add", text="Fill")

        row = col.row(align=True)
        row.operator("mesh.dissolve_limited", text="Limited Dissolve")
        row = col.row(align=True)
        if sel_mode[0] or sel_mode[1]:
            row.operator("mesh.rip_move", text="Rip")
        else:
            row.operator("mesh.split", text="Split")
        row.operator("mesh.separate", text="Separate")

        #select 
        row = col.row(align=True)
        row.label(text="Select")
        row = col.row(align=True)
        row.operator("mesh.select_more", text="More", icon= "ADD")
        row.operator("mesh.select_less", text="Less", icon= "REMOVE")
        row = col.row(align=True)
        row.operator("mesh.loop_multi_select", text="Loop").ring=False
        row.operator("mesh.loop_multi_select", text="Ring").ring=True
        row = col.row(align=True)
        row.operator("mesh.select_non_manifold", text="Non Manifold")
        row.operator("mesh.region_to_loop", text="Boundary")
        row = col.row(align=True)
        row.operator("mesh.select_similar", text="Similar")
        if sel_mode[2]:
            row.operator("mesh.faces_select_linked_flat", text="By Angle")
        else:
            row.operator("mesh.edges_select_sharp", text="Edge Angle")

        #cylinder
        row = col.row(align=True)
        row.label(text="Cylinder")
        row = col.row(align=True)
        row.operator("keyops.utilities_panel_op", text="Un-Subdivide").type = "un_subdivide_cylinder"
        row.operator("keyops.utilities_panel_op", text="Subdivide").type = "subdivide_cylinder"
        row = col.row(align=True) 
        row.operator("keyops.utilities_panel_op", text="Cylinder From Edge Modifier").type = "change_cylinder_segments_modifier"

class ObjectModePanel(bpy.types.Panel):
    bl_description = "Object Mode Panel"
    bl_label = "Object Mode"
    bl_idname = "KEYOPS_PT_object_mode_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'
    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)

        row.operator("keyops.utilities_panel_op", text="Join Objects & Keep Normals").type = "Apply_and_Join"
        row = col.row(align=True)
        row.operator("keyops.utilities_panel_op", text="Quick Apply All Modifiers").type = "Quick_Apply_All_Modifiers"

        row = col.row(align=True)

        row.label(text="Collections:")
        row = col.row(align=True)
        row.operator("keyops.unique_collection_duplicate", text="Unique Collection Duplicate")
        row = col.row(align=True)
        row.operator("keyops.utilities_panel_op", text="Toggle").type = "toggle_high_low"
        row.operator("keyops.utilities_panel_op", text="high").type = "high"
        row.operator("keyops.utilities_panel_op", text="low").type = "low"

