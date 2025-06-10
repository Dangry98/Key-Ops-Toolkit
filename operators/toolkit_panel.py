import bpy
from ..utils.pref_utils import get_keyops_prefs, get_is_addon_enabled
import bmesh
import math
from mathutils import Vector
from ..utils.pref_utils import get_icon
from .add_modifier import AddModifier
from .smart_apply_scale import SmartApplyScale
from .none_live_booleans import ENTERING_TRANSFORM_OT_None_Live_Booleans
from .add_modifier import BooleanScroll, AddBooleanModifier

# fix attribute toggle in edit mode/objet mode

def offset_uv():
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
    world_scale_socket.default_value = True
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

def make_duplicate_linked(self, context):
    if not bpy.data.node_groups.get("Duplicate Linked Modifiers"):
        duplicate_linked_modifiers_node_group()

    supported_objects = ['MESH', 'CURVE', 'TEXT', 'SURFACE']

    og_selected_objects = bpy.context.selected_objects
    og_selected_meshes = [obj for obj in og_selected_objects if obj.type in supported_objects]
    
    names = []
    for obj in og_selected_meshes:
        name = obj.name
        if obj.modifiers:
            mod = obj.modifiers[0]
            if len(obj.modifiers) == 1:
                if mod.name == "Duplicate Linked Modifiers":
                    for item in mod.node_group.interface.items_tree:
                        if item.in_out == "INPUT" and item.identifier == 'Socket_2': 
                            if mod[item.identifier]:
                                name = mod[item.identifier].name
        names.append(name)
        
    bpy.ops.object.duplicate(linked=True)

    new_selected_objects = bpy.context.selected_objects
    new_selected_meshes = [obj for obj in new_selected_objects if obj.type in supported_objects]
    
    iteration = -1
    for obj in new_selected_meshes:
        iteration += 1

        for modifier in obj.modifiers:
            obj.modifiers.remove(modifier) 

        if obj.modifiers.get("Duplicate Linked Modifiers") is None:
            mod = obj.modifiers.new('Duplicate Linked Modifiers', 'NODES')
            mod.node_group = bpy.data.node_groups['Duplicate Linked Modifiers']
            if not self.instance:
                mod.show_in_editmode = False    

        #add option to only duplate the shoruce object so the modifers is not wrong! Go after socket name? Works, but not when adding a modifier :(
        obj.modifiers["Duplicate Linked Modifiers"]["Socket_2"] = bpy.data.objects[names[iteration]]
        obj.modifiers["Duplicate Linked Modifiers"]["Socket_3"] = self.instance
        name = obj.name.split("_Link_Mod")[0]
        obj.name = names[iteration] + "_Link_Mod"
        #obj.modifiers["Duplicate Linked Modifiers"].show_in_editmode = False
    
    # bpy.ops.transform.translate('INVOKE_DEFAULT')
    if self.instance:
        self.report({'INFO'}, "Created Linked Modifier Instance")
        # self.report({'WARNING'}, "Created Linked Modifier Instance; New Modifiers might not work with Instances!")
    else:
        self.report({'INFO'}, "Created Linked Modifier Object")

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

def get_description(type: str) -> str:
    if type == "offset_uv":
        return "Offset UV"
    elif type == "Triplanar_UV_Mapping":
        return "Triplanar UV Mapping"
    elif type == "snap_to_floor":
        return "Snap To Grid Floor"
    elif type == "Instant_Apply_Modifiers":
        return "Apply All Modifiers on currently Selected Objects (very fast, since it only returns whats on screen)"
    elif type == "clear_custom_normals":
        return "Clear all Custom Normals on currently Selected Objects"
    elif type == "Smart_Join_Objects":
        return "Join/Combine selected objects"
    elif type == "seprate_objects_by":
        return "Separate Selected Objects by"

class ToolkitPanel(bpy.types.Operator):
    bl_description = "Object Panel Operator"
    bl_idname = "keyops.toolkit_panel"
    bl_label = "Object Operator"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return get_description(properties.type)

    type: bpy.props.StringProperty() # type: ignore
    select_children: bpy.props.BoolProperty(name="Select Children", default=True) # type: ignore    
    select_parent: bpy.props.BoolProperty(name="Select Parent", default=True) # type: ignore
    select_top_parent: bpy.props.BoolProperty(name="Select Top Parent", default=True) # type: ignore
    # set_material_index: bpy.props.BoolProperty(name="Set Material Index", default=False) # type: ignore
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
    world_offset: bpy.props.BoolProperty(name="World Offset", default=False) # type: ignore
    world_scale: bpy.props.BoolProperty(name="World Scale", default=True) # type: ignore
    scale_triplanar: bpy.props.FloatProperty(name="Scale", default=0.5) # type: ignore
    rotation_triplanar: bpy.props.FloatProperty(name="Rotation", default=0.0) # type: ignore
    axis_x: bpy.props.FloatProperty(name="X", default=0.5) # type: ignore
    axis_y: bpy.props.FloatProperty(name="Y", default=0.5 ) # type: ignore
    appy_triplanar: bpy.props.BoolProperty(name="Apply Triplanar", default=False) # type: ignore
    recalculate_normals: bpy.props.BoolProperty(name="Recalculate Normals", default=False) # type: ignore
    triangulate_end: bpy.props.BoolProperty(name="Triangulate End", default=True) # type: ignore
    angle_to_skip: bpy.props.FloatProperty(name="Angle to Skip", subtype='ANGLE', default=1.5708, min=0.0, max=1.5708) # type: ignore
    full_edge_loops: bpy.props.BoolProperty(name="Full Edge Loops", default=True) # type: ignore
    angle_to_add: bpy.props.FloatProperty(name="Angle to Add", subtype='ANGLE', default=1.5708, min=0.0, max=1.5708) # type: ignore
    use_full_edge_loops: bpy.props.BoolProperty(name="Full Edge Loops", default=True) # type: ignore
    convert_to_options: bpy.props.EnumProperty(name="Convert To", 
                                               items=[("Insta_Apply_Modifiers", "Apply Viewport Modifiers", "Apply Modifiers", "MODIFIER_ON", 0),
                                                      ("Mesh", "Mesh", "Mesh", "OUTLINER_OB_MESH", 1),
                                                      ("Curve", "Curve", "Curve", "OUTLINER_OB_CURVE", 2),
                                                      ("Curves", "Curves", "Curves", "OUTLINER_OB_CURVES", 3),
                                                      ("Grease_Pencil", "Grease Pencil", "Grease Pencil", "OUTLINER_OB_GREASEPENCIL", 4)],
                                                      default="Insta_Apply_Modifiers") # type: ignore
    remove_modifiers: bpy.props.BoolProperty(name="Remove Modifiers", default=True) # type: ignore
    ovveride_color: bpy.props.BoolProperty(name="Override Color", default=False) # type: ignore
    ovveride_color_vec: bpy.props.FloatVectorProperty(name="Color", default=(0.0, 0.0, 0.0, 1.0), subtype='COLOR', size=4) # type: ignore
    individual: bpy.props.BoolProperty(name="Individual", description="Snap each object to the floor individually (hold Alt when clicking button)", default=False, options={'SKIP_SAVE'}) # type: ignore
    exact: bpy.props.BoolProperty(name="Exact", description="Exact snap to floor, but slower (hold Ctrl when clicking button)", default=True, options={'SKIP_SAVE'}) # type: ignore
    instance: bpy.props.BoolProperty(name="Instanced", description="Might provde better viewport performance, but some modifiers and exporters will not work", default=False) # type: ignore
    seprate_by: bpy.props.EnumProperty(name="Separate By",
                                       items=[("MATERIAL", "Material", "Separate by Material", "MATERIAL", 0),
                                              ("LOOSE", "By Loose Parts", "Separate by Loose Islands", "LOOSE", 1)],
                                        default="LOOSE") # type: ignore
    def invoke(self, context, event):
        global ev 
        ev = []
        if event.ctrl:
            ev.append("Ctrl")
        if event.shift:
            ev.append("Shift")
        if event.alt:
            ev.append("Alt")
        return self.execute(context)
    
    @classmethod
    def description(cls, context, properties):
        return get_description(properties.type)
    
    def draw(self, context):
        #add operation text + icon label for all!
        layout = self.layout
        # if self.type == "offset_uv":
        #     layout.label(text="Offset UV", icon="AREA_JOIN")
        #     if context.mode == 'EDIT_MESH':
        #         layout.prop(self, "true_false")
        if self.type == "Triplanar_UV_Mapping":
            layout.label(text="Triplanar UV", icon="AXIS_SIDE")
            layout.prop(self, "world_offset")
            layout.prop(self, "axis_x")
            layout.prop(self, "axis_y")
            layout.prop(self, "world_scale")
            layout.prop(self, "scale_triplanar")
            layout.prop(self, "rotation_triplanar")
            layout.prop(self, "appy_triplanar")
        if self.type == "Smart_Join_Objects":
            layout.label(text="Quick Join Objects", icon="EVENT_J")
            # layout.prop(self, "set_material_index")   
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
        if self.type == "subdivide_cylinder":
            layout.prop(self, "triangulate_end")
            layout.prop(self, "angle_to_add")
            layout.prop(self, "use_full_edge_loops")
        if self.type == "un_subdivide_cylinder":
            layout.prop(self, "angle_to_skip")
            layout.prop(self, "full_edge_loops")
        if self.type == "Instant_Apply_Modifiers":
            layout.label(text="Instant Apply All Modifiers", icon="OUTLINER_OB_MESH")
            layout.prop(self, "convert_to_options", text="Convert To")
        if self.type == "snap_to_floor":
            layout.label(text="Snap to Grid Floor", icon="VIEW_PERSPECTIVE")
            layout.prop(self, "individual")
            layout.prop(self, "exact", text="Exact")
        if self.type == "duplicate_linked_modifiers":
            layout.label(text="Duplicate Linked Modifiers", icon="LINKED")
            layout.prop(self, "instance")
        if self.type == "change_hard_bevel_width":
            layout.prop(self, "scale")
        if self.type == "seprate_objects_by":
            layout.scale_x = 1.2
            layout.prop(self, "seprate_by")


    def execute(self, context):
        prefs = get_keyops_prefs()
        
        if self.type == "Triplanar_UV_Mapping":
            active_object = bpy.context.active_object
            if bpy.data.node_groups.get("Triplanar UV Mapping") is None:
                triplanar_uv_mapping_node_group()
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':         
                    bpy.context.view_layer.objects.active = obj

                    if obj.data.uv_layers.active is None:
                        bpy.ops.mesh.uv_texture_add()       

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
                    context.object.modifiers["Triplanar UV Mapping"]["Socket_5"] = self.world_offset
                    context.object.modifiers["Triplanar UV Mapping"]["Socket_6"] = self.axis_x
                    context.object.modifiers["Triplanar UV Mapping"]["Socket_7"] = self.axis_y
                    context.object.modifiers["Triplanar UV Mapping"]["Socket_9"] = self.world_scale
                    context.object.modifiers["Triplanar UV Mapping"]["Socket_10"] = self.scale_triplanar
                    context.object.modifiers["Triplanar UV Mapping"]["Socket_13"] = self.rotation_triplanar
                    bpy.context.object.data.update()
                
                    bpy.context.object.modifiers["Triplanar UV Mapping"].show_group_selector = False

                    if context.mode == 'EDIT_MESH':
                        bpy.ops.mesh.attribute_set(value_bool=True)

            if self.appy_triplanar == True:
                for obj in bpy.context.selected_objects:
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_apply(modifier="Triplanar UV Mapping")

            bpy.context.view_layer.objects.active = active_object

        if self.type == "Remove_Triplanar_UV_Mapping":
            active_object = bpy.context.active_object

            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    if bpy.context.object.modifiers.get("Triplanar UV Mapping") is not None:
                        bpy.context.object.modifiers.remove(bpy.context.object.modifiers['Triplanar UV Mapping'])
            bpy.context.view_layer.objects.active = active_object

        def add_UV_offset_modifier(obj):
            if obj.modifiers.get("Offset UV") is None:
                obj.modifiers.new('Offset UV', 'NODES')
                obj.modifiers['Offset UV'].node_group = bpy.data.node_groups['Offset UV']
                if bpy.context.mode == 'OBJECT':
                    obj.modifiers["Offset UV"]["Socket_2"] = True

                if bpy.context.mode == 'EDIT_MESH': 
                    mod = obj.modifiers["Offset UV"]
                    mod["Socket_2_use_attribute"] = True
                    mod["Socket_2_attribute_name"] = "Offset_UV"

        def set_offset_uv_true_false(obj, true_false=True):
            if obj.data.total_vert_sel > 0:
                named_attributes = obj.data.attributes
                attribute_name = "Offset_UV"
                set_act = named_attributes.get(attribute_name)
                if set_act is not None:
                    select_atribute(attribute_name)
                else:
                    obj.data.attributes.new(name="Offset_UV", domain='FACE', type='BOOLEAN')
                    select_atribute(attribute_name)

                bpy.context.view_layer.objects.active = obj
                bpy.ops.mesh.attribute_set(value_bool=true_false)

        if self.type == "offset_uv":
            active_object = bpy.context.active_object
            if bpy.data.node_groups.get("Offset UV") is None:
                offset_uv()

            for area in bpy.context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    with context.temp_override(area=area):
                        if not area.spaces.active.uv_editor.show_modified_edges:
                            area.spaces.active.uv_editor.show_modified_edges = True

            for obj in bpy.context.selected_objects:
                #add option to ctrl click for forcing adding a new modifier
                if obj.type == 'MESH':
                    if bpy.context.mode == 'OBJECT':
                        add_UV_offset_modifier(obj)
                    if bpy.context.mode == 'EDIT_MESH':
                        if obj.data.total_vert_sel > 0:
                            add_UV_offset_modifier(obj)
                            set_offset_uv_true_false(obj, True)

                    for mod in obj.modifiers:
                        if mod.name == "Offset UV":
                            active_uv_name = obj.data.uv_layers.active.name
                            if obj.modifiers["Offset UV"]["Socket_5"] == "UVMap" and active_uv_name != "UVMap":
                                obj.modifiers["Offset UV"]["Socket_5"] = active_uv_name
                                obj.modifiers["Offset UV"].show_group_selector = False
                                break

                bpy.context.view_layer.objects.active = active_object

        if self.type == "Remove_Offset_UV":
            if context.mode != 'EDIT_MESH':
                active_object = bpy.context.active_object

                for obj in bpy.context.selected_objects:
                    if obj.type == 'MESH':
                        bpy.context.view_layer.objects.active = obj
                        if bpy.context.object.modifiers.get("Offset UV") is not None:
                            bpy.context.object.modifiers.remove(bpy.context.object.modifiers['Offset UV'])
                bpy.context.view_layer.objects.active = active_object
            else:
                for obj in bpy.context.selected_objects:
                    if obj.type == 'MESH':
                        set_offset_uv_true_false(obj, False)


        if self.type == "change_hard_bevel_width":
            context = bpy.context
            ob = context.edit_object
            me = ob.data
            bm = bmesh.from_edit_mesh(me)
            selection = [f for f in bm.faces if f.select]

            bpy.ops.transform.shrink_fatten(value=self.scale, use_even_offset=False, mirror=True, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False)
            bpy.ops.mesh.select_linked(delimit={'NORMAL'})
            
            for f in selection:
                f.select = False

            bpy.ops.transform.shrink_fatten(value=-self.scale, use_even_offset=True, mirror=True, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False)
            bpy.ops.mesh.select_all(action='DESELECT')

            for f in selection:
                f.select = True

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
            bpy.ops.mesh.duplicate_move(MESH_OT_duplicate={"mode":1}, TRANSFORM_OT_translate={"value":(0, 0, 0), "orient_type":'GLOBAL', "orient_matrix":((0, 0, 0), (0, 0, 0), (0, 0, 0)), "orient_matrix_type":'GLOBAL', "constraint_axis":(False, False, False), "mirror":False, "snap":False, "snap_elements":{'INCREMENT'}, "use_snap_project":False, "snap_target":'CLOSEST', "use_snap_self":True, "use_snap_edit":True, "use_snap_nonedit":True, "use_snap_selectable":False, "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0), "gpencil_strokes":False, "cursor_transform":False, "texture_space":False, "remove_on_cancel":False, "use_duplicated_keyframes":False, "view2d_edge_pan":False, "release_confirm":False, "use_accurate":False, "use_automerge_and_split":False})
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
            new_selected_meshes = bpy.context.selected_objects
            for selected_obj in new_selected_meshes:
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
            new_selected_meshes = bpy.context.selected_objects

            for selected_obj in new_selected_meshes:
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
            new_selected_meshes = bpy.context.selected_objects

            for selected_obj in new_selected_meshes:
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

        if self.type == "seprate_objects_by":
            if bpy.context.mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='OBJECT')
            if self.seprate_by == "MATERIAL":
                bpy.ops.mesh.separate(type='MATERIAL')
            elif self.seprate_by == "LOOSE":
                bpy.ops.mesh.separate(type='LOOSE')


        if self.type == "unique_collection_duplicat":
            if bpy.data.collections.get("high"):
                self.default_name = "low"
            else:
                self.default_name = "high"
        
            bpy.ops.object.duplicate()
            bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name=self.default_name)

            objects_to_duplicate = [obj for obj in context.selected_objects if obj.data and obj.data.users > 1]

            for obj in objects_to_duplicate:

                obj.data = obj.data.copy()
                #should auto get all booleons, so they do not need to be selected
                booleans = [mod for mod in obj.modifiers if mod.type == 'BOOLEAN' and mod.object and mod.object.data.users > 1]

                for mod in booleans:
                    mod.object.data = mod.object.data.copy()

        if self.type == "Smart_Join_Objects":
            #import time
            #exec_time = time.time()
            if bpy.context.mode == 'EDIT_MESH':                                                             
                bpy.ops.object.mode_set(mode='OBJECT')
            
            new_selected_meshes = bpy.context.selected_objects
            new_selected_meshes = [obj for obj in new_selected_meshes if (obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'INSTANCE') and obj.display_type != 'WIRE']

            if len(new_selected_meshes) == 0:
                self.report({'WARNING'}, "No Objects Selected")
                return {'CANCELLED'}
            
            elif bpy.context.active_object is None:
                bpy.context.view_layer.objects.active = new_selected_meshes[0]

            if self.join_children:
                bpy.ops.object.select_grouped(extend=True, type='CHILDREN_RECURSIVE')
            
            cursor_loc = context.scene.cursor.location
            pos2 = (cursor_loc[0], cursor_loc[1], cursor_loc[2])
            bpy.ops.view3d.snap_cursor_to_active()

            if self.apply_instances == True:
                bpy.ops.object.duplicates_make_real()

            bpy.ops.object.select_all(action='DESELECT')

            for selected_obj in new_selected_meshes:
                selected_obj.select_set(True)

            bpy.context.view_layer.objects.active = new_selected_meshes[0]

            bpy.ops.object.make_single_user(object=True, obdata=True, material=False, animation=False, obdata_animation=False)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            #bpy.ops.object.convert(target='MESH')
            bpy.ops.keyops.toolkit_panel(type="Instant_Apply_Modifiers")

            new_selected_meshes = bpy.context.selected_objects
        
            if self.rename_uv_layer == True:
                for obj in new_selected_meshes:
                    if obj.type == 'MESH':
                        if obj.data.uv_layers.active is not None:
                            #if it already has a "UVMap", it needs to rename it to old
                            if obj.data.uv_layers[0].name != "UVMap":
                                obj.data.uv_layers[0].name = "UVMap"

            for selected_obj in new_selected_meshes:
                selected_obj.select_set(True)
                bpy.context.view_layer.objects.active = selected_obj
                bpy.ops.mesh.customdata_custom_splitnormals_add()

            if self.join_objects == True:
                bpy.ops.object.join()
                if self.triangulate == True:
                    bpy.ops.object.modifier_add(type='TRIANGULATE')
            else:
                if self.triangulate == True:
                    for selected_obj in new_selected_meshes:
                        bpy.context.view_layer.objects.active = selected_obj
                        bpy.ops.object.modifier_add(type='TRIANGULATE')
            
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            if bpy.app.version <= (4, 0, 0):
                bpy.context.object.data.use_auto_smooth = True

            # if self.set_material_index == True and prefs.enable_material_index:
            #     bpy.ops.keyops.material_index(type="Make_Material_Index")
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
            #print(f"Total Time: {time.time() - exec_time:.4f} seconds")
        if self.type == "Instant_Apply_Modifiers":
            import time
            perf_time = time.time()

            if self.convert_to_options == "Insta_Apply_Modifiers":
                new_selected_objects = bpy.context.selected_objects
                new_selected_meshes = [obj for obj in new_selected_objects if obj.type == 'MESH']
                selected_curves = [obj for obj in new_selected_objects if obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']
                active_object = bpy.context.active_object

                if new_selected_objects:
                    depsgraph = bpy.context.evaluated_depsgraph_get()
                    for obj in new_selected_meshes:
                        object_eval = obj.evaluated_get(depsgraph)
                        mesh_from_eval = bpy.data.meshes.new_from_object(object_eval, depsgraph=depsgraph)

                        if obj.mode == 'OBJECT':
                            obj.data = mesh_from_eval
                        else:
                            bm = bmesh.from_edit_mesh(obj.data)
                            bm.clear()
                            bm.from_mesh(mesh_from_eval)
                            bmesh.update_edit_mesh(obj.data)
                            
                        if self.remove_modifiers:
                            for modifier in obj.modifiers:
                                obj.modifiers.remove(modifier) 

                    for obj in selected_curves:
                        name = obj.name
                 
                        object_collection = obj.users_collection[0]

                        object_eval = obj.evaluated_get(depsgraph)
                        mesh_from_eval = bpy.data.meshes.new_from_object(object_eval, depsgraph=depsgraph)

                        new_obj = bpy.data.objects.new("temp_mesh", mesh_from_eval)
                        object_collection.objects.link(new_obj)

                        new_obj.matrix_world = obj.matrix_world
                        new_obj.select_set(True)
                        bpy.data.objects.remove(obj)

                        # restore the original name
                        new_obj.name = name

                        #set the new object as active if the old object was active
                        if obj == active_object:
                            active_object = new_obj
               
                    #clear the evaluated mesh
                    object_eval.to_mesh_clear()
                    bpy.context.view_layer.objects.active = active_object
                   
                else:
                    self.report({'WARNING'}, "No Objects are Selected")
                print(f"Total Time: {time.time() - perf_time:.4f} seconds")

            elif self.convert_to_options == "Mesh":
                bpy.ops.object.convert(target='MESH')
            elif self.convert_to_options == "Curve":
                bpy.ops.object.convert(target='CURVE')
            elif self.convert_to_options == "Curves":
                bpy.ops.object.convert(target='CURVES')
            elif self.convert_to_options == "Grease_Pencil":
                bpy.ops.object.convert(target='GPENCIL')
            return {'FINISHED'}

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
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')

            for obj in bpy.context.selected_objects:
                if obj.data.total_vert_sel > 0:
                    context.view_layer.objects.active = obj
                    if obj.data.attributes.get('Edge_Un_Subdivied_Cylinder') is None:
                        obj.data.attributes.new(name='Edge_Un_Subdivied_Cylinder', type='BOOLEAN', domain='EDGE')
                    obj.data.attributes.active = obj.data.attributes.get('Edge_Un_Subdivied_Cylinder')
                    obj.data.update()
                    bpy.ops.mesh.attribute_set(value_bool=True)

            for obj in bpy.context.selected_objects:
                if obj.data.total_vert_sel > 0:    
                    mesh = obj.data
                    bm = bmesh.from_edit_mesh(mesh)
                    current_selection = [e for e in bm.edges if e.select]

                    if len(current_selection) == 0:
                        self.report({'INFO'}, "No edges selected")
                        obj.data.attributes.remove(obj.data.attributes.get('Edge_Un_Subdivied_Cylinder'))
                        return {'CANCELLED'}
                    
                    bpy.ops.mesh.select_all(action='DESELECT')
                    current_selection[0].select = True

                    bpy.ops.mesh.loop_multi_select('EXEC_DEFAULT', True, ring=True)
                    bpy.ops.mesh.select_nth('EXEC_DEFAULT', True, skip=1, nth=1, offset=0)

                    #compare if current_selection does not match any in the new_selection, if then increase the offset with +1
                    new_selection = [e for e in bm.edges if e.select]
                    if any(e in current_selection for e in new_selection):
                        bpy.ops.mesh.loop_multi_select('EXEC_DEFAULT', True, ring=True)
                        bpy.ops.mesh.select_nth('EXEC_DEFAULT', True, skip=1, nth=1, offset=1)

                    bpy.ops.mesh.loop_multi_select('EXEC_DEFAULT', True, ring=False)

                    if self.angle_to_skip <= 1.570:
                        bpy.ops.mesh.select_all(action='INVERT')
                        bpy.ops.mesh.edges_select_sharp(sharpness=self.angle_to_skip)
                        bpy.ops.mesh.select_all(action='INVERT')
                        if self.full_edge_loops == True:
                            bpy.ops.mesh.loop_multi_select(ring=False)

                    bpy.ops.mesh.dissolve_mode('EXEC_DEFAULT', True, use_verts=True)
                    bpy.ops.mesh.select_by_attribute()

                    bmesh.update_edit_mesh(mesh)
                    bm.free()

            for obj in bpy.context.selected_objects:
                if obj.data.attributes.get('Edge_Un_Subdivied_Cylinder') is not None:
                    context.view_layer.objects.active = obj
                    bpy.ops.mesh.select_by_attribute()
                    obj.data.attributes.remove(obj.data.attributes.get('Edge_Un_Subdivied_Cylinder'))
                    
        if self.type == "subdivide_cylinder":
            if get_is_addon_enabled("EdgeFlow-blender_28") or get_is_addon_enabled("EdgeFlow"):
                mesh_obj = bpy.context.active_object

                bm = bmesh.from_edit_mesh(mesh_obj.data)

                active_edge = bm.select_history.active
                selected_edges = [e for e in bm.edges if e.select]

                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')

                if len(selected_edges) == 0:
                    self.report({'WARNING'}, "No edges selected")
                    return {'CANCELLED'}

                if active_edge is None or not isinstance(active_edge, bmesh.types.BMEdge):
                    loop = selected_edges[0].link_loops[0]
                else:
                    loop = active_edge.link_loops[0]

                next_loop = loop.link_loop_next

                for edge in bm.edges:
                    edge.select = False
                next_loop.edge.select = True

                bpy.ops.mesh.loop_multi_select(ring=True)
                bpy.ops.mesh.loop_multi_select(ring=False)

                if self.angle_to_add <= 1.570:
                    bm = bmesh.from_edit_mesh(mesh_obj.data)
                    # Define the angle threshold for edge deletion
                    angle_threshold = math.radians(self.angle_to_skip)

                    # Loop through all edges in the mesh
                    for edge in bm.edges:
                        # Check if the edge has exactly 2 faces
                        if len(edge.link_faces) == 2:
                            # Calculate the angle between the connected faces
                            angle = edge.calc_face_angle()

                            # Check if the angle is below the threshold
                            if angle < angle_threshold:
                                # Mark the edge to be deselected
                                edge.select = False
                        else:
                            # Handle the case where the edge doesn't have 2 faces
                            self.report({'WARNING'}, "Edge doesn't use 2 faces")

                    # Update the mesh
                    bmesh.update_edit_mesh(mesh_obj.data)

                if self.use_full_edge_loops == True:
                    bpy.ops.mesh.loop_multi_select(ring=False)


                bpy.ops.mesh.connect2()
                bpy.ops.mesh.set_edge_flow(tension=180, iterations=3)

                if self.triangulate_end == True:
                    bm = bmesh.from_edit_mesh(mesh_obj.data)

                    new_selected_edges = [e for e in bm.edges if e.select]
                    
                    bpy.ops.mesh.loop_multi_select(ring=True)
                    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
                    bpy.ops.mesh.region_to_loop()
                    bpy.ops.mesh.loop_to_region()
                    bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')

                    for edge in bm.edges:
                        edge.select = False

                    for edge in new_selected_edges:
                        edge.select = True

                    bmesh.update_edit_mesh(mesh_obj.data)
                    bm.free()

                    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')

            else:
                self.report({'WARNING'}, "EdgeFlow addon not installed, please install it to use this operator")

        if self.type == "change_cylinder_segments_modifier":
            bpy.ops.mesh.select_all(action='INVERT')
            bpy.ops.mesh.delete(type='EDGE')

            obj = bpy.context.active_object

            mod = obj.modifiers.new(type='SCREW', name='Screw')
            mod.use_normal_calculate = True
            mod.use_merge_vertices = True
            mod.steps = 32
            bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)

        if self.type == "clear_custom_normals":
            selection = bpy.context.selected_objects

            for obj in selection:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.mesh.customdata_custom_splitnormals_clear()

        if self.type == "cleanup":
            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)

        if self.type == "set_vertex_color":
            if bpy.context.space_data.shading.color_type != 'VERTEX':
                bpy.context.space_data.shading.color_type = 'VERTEX'

            selection = set(bpy.context.selected_objects)
            active = set([context.active_object])
            selection = set(selection).union(set(active))

            for obj in selection:
                if obj.data.total_vert_sel > 0: 
                    if obj.data.attributes.active_color is None:
                        context.view_layer.objects.active = obj
                        obj.data.color_attributes.new(name="Vertex_Color", type="BYTE_COLOR", domain="POINT")
                        
                    active_attribute = obj.data.attributes.active_color.name

                    set_act_index = obj.data.attributes.find(active_attribute)
                    obj.data.attributes.active_index = set_act_index

            if self.ovveride_color != True:
                color = bpy.context.scene.vertex_color
            else:
                color = self.ovveride_color_vec
            bpy.ops.mesh.attribute_set(value_color=(color[0], color[1], color[2], color[3]))
       
        if self.type == "duplicate_linked_modifiers":
            make_duplicate_linked(self, context)
            return {'FINISHED'}
        if self.type == "duplicate_linked_modifiers_and_move":
            make_duplicate_linked(self, context)
            bpy.ops.transform.translate('INVOKE_DEFAULT')
            
            return {'FINISHED'}

        if self.type == "snap_to_floor":
            global ev
            if "Alt" in ev:
                self.individual = True
            if "Ctrl" in ev:
                self.exact = False
            ev = []

            if not bpy.context.selected_objects:
                self.report({'WARNING'}, "No Objects Selected")
                return {'CANCELLED'}

            #bpy.context.evaluated_depsgraph_get()
            depsgraph = bpy.context.evaluated_depsgraph_get()

            if not self.individual:
                all_bounds = []

                if self.exact:
                    active = context.active_object
                    new_selected_objects = [o for o in context.selected_objects if o.type in ['MESH', 'CURVE', 'TEXT', 'SURFACE']]
                    empty = [o for o in context.selected_objects if o.type in ['EMPTY', 'LATTICE']]
                    obj_names = []
                    for obj in new_selected_objects:
                        name = obj.name
                        obj_names.append(name)

                    bpy.ops.mesh.primitive_plane_add(enter_editmode=False, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))

                    if bpy.data.node_groups.get("Get All Bouding Box"):
                        n = bpy.data.node_groups["Get All Bouding Box"]
                        bpy.data.node_groups.remove(n)

                    get_all_bouding_box_node_group(obj_names)
        
                    if bpy.context.object.modifiers.get("Get All Bouding Box") is None:
                        bpy.context.object.modifiers.new('Get All Bouding Box', 'NODES')
                        bpy.context.object.modifiers['Get All Bouding Box'].node_group = bpy.data.node_groups['Get All Bouding Box']
                    
                    bounding_box = [o for o in context.selected_objects if o.type in ['MESH']]
                    
                    #need to update in order for the new bouding box created in geomtry nodes to be evaluated
                    context.view_layer.update()

                if self.exact:
                    for obj in bounding_box:
                        eval = obj.evaluated_get(depsgraph)
                        me = eval.to_mesh()
                        all_bounds += [obj.matrix_world @ v.co for v in me.vertices]   
                        eval.to_mesh_clear()
                else:
                    for obj in [o for o in context.selected_objects if o.type in ['MESH', 'CURVE', 'TEXT', 'SURFACE']]:
                        obj_bounds = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
                        all_bounds += obj_bounds

                if not self.exact:
                    for obj in [o for o in context.selected_objects if o.type == 'EMPTY']:
                        all_bounds.append(obj.location)
                else:
                    for obj in empty:
                        all_bounds.append(obj.location)
                
                if not all_bounds: return {"CANCELLED"}

                if not self.exact:
                    z_min = min(c[2] for c in all_bounds)
                else:
                    z_min = min(v.z for v in all_bounds)

                if self.exact:
                    objs = bpy.data.objects
                    objs.remove(objs[str(bounding_box[0].name)], do_unlink=True)

                    for obj in new_selected_objects + empty:
                        obj.select_set(True)
                 
                    bpy.context.view_layer.objects.active = active
                    
                bpy.ops.transform.translate(value=(0, 0, -z_min), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', constraint_axis=(False, False, True), mirror=False, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False)
            else:
                # import time
                # exec_time = time.time()
                selection = bpy.context.selected_objects

                def move_individual_to_floor(selection):
                    for obj in selection:
                        if obj.type in ['MESH', 'CURVE', 'TEXT', 'SURFACE', 'FONT', 'META']:
                            #if roation is 0,0,0, then we should be able to use the bound box to get accurate z value
                            # otherwise we need to calculate the min z value in world coordinates directly
                            roation = obj.rotation_euler
                            if roation.x == 0 and roation.y == 0 and obj.type != 'SURFACE' or not self.exact:
                                if obj.bound_box:
                                    minz = min((obj.matrix_world @ Vector(corner)).z for corner in obj.bound_box)
                                    obj.matrix_world.translation.z -= minz
                            else:
                                eval = obj.evaluated_get(depsgraph)
                                me = eval.to_mesh()
                                
                                if me.vertices:
                                    # Calculate the minimum Z value in world coordinates directly
                                    minz = float('inf')
                                    for v in me.vertices:
                                        z = (obj.matrix_world @ v.co).z
                                        if z < minz:
                                            minz = z
                                    
                                    obj.matrix_world.translation.z -= minz
                                eval.to_mesh_clear()
                        
                        elif obj.type == 'EMPTY':
                            obj.matrix_world.translation.z -= obj.location.z
                            
                move_individual_to_floor(selection)
                #if any objects has a child,do opertion again to fix offset
                selection = [child for obj in selection for child in obj.children]
                #remove anytihng thats not in selection
                if selection:
                    selection = [obj for obj in selection if obj in bpy.context.selected_objects]
                    move_individual_to_floor(selection)
                # print(f"Total Time: {time.time() - exec_time:.4f} seconds")
        return {'FINISHED'}
    
    def register():
        # bpy.utils.register_class(NewToolkitPanel)
        bpy.utils.register_class(ObjectModePanel)
        bpy.utils.register_class(ModifierPanel)
        bpy.utils.register_class(EditModePanel)
        #bpy.utils.register_class(SmartExtrude)
        bpy.utils.register_class(ExtrudeEdgeByNormal)
        bpy.utils.register_class(EDIT_PT_Settings)
        bpy.utils.register_class(AddModifier)
        bpy.utils.register_class(SmartApplyScale)
        bpy.utils.register_class(AddBooleanModifier)
        bpy.utils.register_class(BooleanScroll)
        bpy.types.Scene.vertex_color = bpy.props.FloatVectorProperty(name="Vertex Color", subtype='COLOR', size=4, min=0.0, max=1.0, update=update_vertex_color, default=(1.0, 1.0, 1.0, 0.3))
        bpy.types.Scene.RGB_Enum = bpy.props.EnumProperty(items=[('R', 'Red', 'Red', 'EVENT_R', 0), ('G', 'Green', 'Green', 'EVENT_G', 1), ('B', 'Blue', 'Blue', 'EVENT_B', 2)], name="RGB", default='R', update=click_rgb_enum)
        bpy.types.WindowManager.live_booleans = bpy.props.BoolProperty(name="Realtime Booleans", default=True, update=toggle_realtime_booleans)
        bpy.context.window_manager.live_booleans = True
    def unregister():
        bpy.utils.unregister_class(ObjectModePanel)
        bpy.utils.unregister_class(ModifierPanel)
        bpy.utils.unregister_class(EditModePanel)
        #bpy.utils.unregister_class(SmartExtrude)
        bpy.utils.unregister_class(ExtrudeEdgeByNormal)
        bpy.utils.unregister_class(EDIT_PT_Settings)
        bpy.utils.unregister_class(AddModifier)
        bpy.utils.unregister_class(SmartApplyScale)
        bpy.utils.unregister_class(AddBooleanModifier)
        bpy.utils.unregister_class(BooleanScroll)
        # bpy.utils.unregister_class(NewToolkitPanel)
        del bpy.types.Scene.vertex_color
        del bpy.types.Scene.RGB_Enum
        del bpy.types.WindowManager.live_booleans
        try:
            bpy.utils.unregister_class(ENTERING_TRANSFORM_OT_None_Live_Booleans)
        except:
            pass

def toggle_realtime_booleans(self, context):
    if not bpy.context.window_manager.live_booleans:
        bpy.utils.register_class(ENTERING_TRANSFORM_OT_None_Live_Booleans)
    else:
        try:
            bpy.utils.unregister_class(ENTERING_TRANSFORM_OT_None_Live_Booleans)
        except:
            pass
        
def update_vertex_color(self, context):
    bpy.ops.keyops.toolkit_panel(type="set_vertex_color")  
    #bpy.ops.mesh.attribute_set(value_color=(bpy.context.scene.vertex_color[0], bpy.context.scene.vertex_color[1], bpy.context.scene.vertex_color[2], bpy.context.scene.vertex_color[3]))

def click_rgb_enum(self, context):
    if bpy.context.scene.RGB_Enum == 'R':
        bpy.ops.keyops.toolkit_panel(type="set_vertex_color", ovveride_color=True, ovveride_color_vec=(1.0, 0.0, 0.0, 1.0))
    elif bpy.context.scene.RGB_Enum == 'G':
        bpy.ops.keyops.toolkit_panel(type="set_vertex_color", ovveride_color=True, ovveride_color_vec=(0.0, 1.0, 0.0, 1.0))
    elif bpy.context.scene.RGB_Enum == 'B':
        bpy.ops.keyops.toolkit_panel(type="set_vertex_color", ovveride_color=True, ovveride_color_vec=(0.0, 0.0, 1.0, 1.0))

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
        #import time 
        #perf_time = time.time()
        if "Extrude Edge By Normal" not in bpy.data.node_groups:
            extrude_edge_by_normal_node_group()

        bpy.data.node_groups["Extrude Edge By Normal"].is_mode_edit = True
        bpy.data.node_groups["Extrude Edge By Normal"].nodes["Extrude Mesh"].inputs[3].default_value = self.offset
        bpy.ops.geometry.execute_node_group(name="Extrude Edge By Normal")
        bpy.data.node_groups["Extrude Edge By Normal"].is_mode_edit = False
        #print(f"Total Time: {time.time() - perf_time:.4f} seconds")

        return {'FINISHED'}
    
def register():
    bpy.types.VIEW3D_MT_edit_mesh_extrude_pre.prepend(menu_extrude)
def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_extrude_pre.remove(menu_extrude)

def menu_extrude(self, context):
    if bpy.context.mode == 'EDIT_MESH' and not bpy.context.tool_settings.mesh_select_mode[2] == True:
        self.layout.operator(ExtrudeEdgeByNormal.bl_idname, text="Extrude Edge by Normal")
def draw_modifier_panel(self, context, draw_header=False):
        layout = self.layout
        prefs = get_keyops_prefs()
        wm = bpy.context.window_manager
        
        box = layout.box()
        col = box.column(align=True)
        if draw_header:
            col.label(text="Modifiers", icon_value=get_icon("modifier"))
        row = col.row(align=True)
        row.label(text="UV Tools")
        row = col.row(align=True)
        column = row.column(align=True) 
        row = column.split(factor=0.57, align=True)
        row.scale_y = 1.15

        if bpy.context.mode == 'EDIT_MESH':
            row.operator("keyops.toolkit_panel", text="Offset UV", icon="AREA_JOIN").type = "offset_uv"   
            row.operator("keyops.toolkit_panel", text="Remove").type = "Remove_Offset_UV"
        else:   
            row.operator("keyops.toolkit_panel", text="Offset UV", icon="AREA_JOIN").type = "offset_uv"
            row.operator("keyops.toolkit_panel", text="Remove").type = "Remove_Offset_UV"
        row = column.split(factor=0.57, align=True)
        row.operator("keyops.toolkit_panel", text="Triplanar UV", icon="AXIS_SIDE").type = "Triplanar_UV_Mapping"
        row.operator("keyops.toolkit_panel", text="Remove").type = "Remove_Triplanar_UV_Mapping"

        if prefs.enable_uv_tools:
            row = column.split(align=True)
            row.operator("keyops.sharp_from_uv_islands", text="Sharp from UV Islands", icon="MOD_EDGESPLIT")

        row = layout.row(align=True)
        box = row.box()

        row = box.row(align=True)
        row.label(text="Create")
        row = box.row(align=True)
        row.operator("keyops.add_modifier", text="Lattice", icon="MOD_LATTICE").type = "LATTICE"
        operation_FFD2X = row.operator("keyops.add_modifier", text="FFD 3x")
        operation_FFD2X.subdivisions = 3
        operation_FFD2X.type = "LATTICE"

        operation_FFD2X = row.operator("keyops.add_modifier", text="FFD 4x")
        operation_FFD2X.subdivisions = 4
        operation_FFD2X.type = "LATTICE"


        if context.mode == 'OBJECT':
            # header, panel_changde_meshes = box.panel(idname="Set Bevel",  default_closed=False)
            # header.label(text="Set Bevel", icon = "MOD_BEVEL")
            # if panel_changde_meshes:
            box = layout.box()

            layout = box
            col = layout.column(align=False)
            row = col.row(align=False)
            row.label(text="Set Bevel", icon = "MOD_BEVEL")
            row = col.row(align=True)

            row.prop(context.scene, "bevel_segments_type", text="Set")
            row = col.row(align=False)
            col = layout.column(align=True)

            row = col.row(align=True)
            row.operator("keyops.toolkit_panel", text="Set Value", icon= "MOD_BEVEL").type = "set_bevel_segment_amount" 
            row.operator("keyops.toolkit_panel", text="Set by %", icon= "MOD_BEVEL").type = "bevel_segment_amount_by_%"
            row = col.row(align=True)
            row.prop(context.scene, "bevel_segment_amount", text="")
            row.prop(context.scene, "bevel_segment_by_percent", text="")

            row = layout.row()
            row.scale_x = 0.35
            row.operator("keyops.toolkit_panel", text="Hide by Offset", icon= "MOD_BEVEL").type = "hide_bevels_by_offset"
            row.prop(context.scene, "compensate_for_scale", text="")
            subrow = row.row(align=False)
            subrow.scale_x = 0.4
            subrow.prop(context.scene, "bevel_offset", text="")
class ModifierPanel(bpy.types.Panel):
    bl_description = "Modifier Operations"
    bl_label = "Modifiers"
    bl_idname = "KEYOPS_PT_modifier_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'
    # bl_parent_id = "KEYOPS_PT_toolkit_panel"

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon_value=get_icon("modifier"))

    @classmethod
    def poll(cls, context):
        return get_keyops_prefs().enable_toolkit_panel
    
    def draw(self, context):
       draw_modifier_panel(self, context, draw_header=False)

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

# click vert, edge andface again should go to object mode!        
def draw_edit_mode_panel(self, context, draw_header=False):
    sel_mode = bpy.context.tool_settings.mesh_select_mode[:]
    prefs = get_keyops_prefs()

    layout = self.layout
    box = layout.box()
    if draw_header:
        box.label(text="Edit Toolkit", icon_value=get_icon("editmode"))

    if not prefs.max_layout:
        row = box.row(align=True)
        row.scale_x = 2.15
        row.scale_y = 1.5
        row.alignment = 'CENTER'
        row.template_header_3D_mode()
        row.operator("mesh.region_to_loop", text="", icon="MESH_CAPSULE")
        row.operator("mesh.select_linked", text="", icon="SNAP_VOLUME")

        # Selection
        row = box.row(align=False)
        row.label(text="Selection")
        row = box.row(align=False)
        row.scale_x = 1.25
        row.scale_y = 1.5
        row.operator("mesh.select_more", text="", icon="ADD")
        row.operator("mesh.select_less", text="", icon="REMOVE")
        row.operator("mesh.loop_multi_select", text="Loop").ring=False
        row.operator("mesh.loop_multi_select", text="Ring").ring=True
        row = box.row(align=False)
        row.operator("mesh.region_to_loop", text="Boundary")
        row.operator("mesh.loop_to_region", text="Inner Region")
        row = box.row(align=False)

        if sel_mode[2]:
            row.operator("mesh.faces_select_linked_flat", text="By Angle")
        else:
            row.operator("mesh.edges_select_sharp", text="Edge Angle")
        row.operator("mesh.select_similar", text="Similar")
        # Checker deselect
        row = box.row(align=False)
        row.alignment = 'CENTER'
        row.operator("mesh.select_nth", text="Checker Deselect")
        if sel_mode[0] or sel_mode[1]:
            row = box.row(align=False)
            row.operator("mesh.select_non_manifold", text="Non Manifold")
        row.operator("mesh.select_face_by_sides", text="Ngons").type = 'GREATER'

        # Edit vertices
        row = box.row(align=False)
        row = box.row(align=False)
        row = box.row(align=False)

        if sel_mode[0]:
            row.label(text="Edit Vertices")
        if sel_mode[1]:
            row.label(text="Edit Edges")
        if sel_mode[2]:
            row.label(text="Edit Polygons")

        row = box.row(align=False)
        row.alignment = 'CENTER'
        if sel_mode[0]:
            row.operator("mesh.delete", text="Remove").type = 'VERT'
        if sel_mode[1]:
            row.operator("mesh.dissolve_mode", text="Remove")
            row.operator("mesh.rip", text="Split")
        if sel_mode[2]:
            row.operator("mesh.delete", text="Remove").type = 'FACE'

        row = box.row(align=False)
        row.operator("wm.call_menu", text="Extrude").name = "VIEW3D_MT_edit_mesh_extrude"
        row.operator("mesh.remove_doubles", text="Weld")
        row = box.row(align=False)
        row.operator("mesh.bevel", text="Chamfer")
        if not sel_mode[2]:
            if prefs.enable_fast_merge:
                row.operator("mesh.connect2", text="Connect")
        else:
            row.operator("mesh.inset", text="Inset")

        if sel_mode[0]:
            row = box.row(align=False)
            row.operator("mesh.edge_face_add", text="Fill")
            row.operator("mesh.set_edge_flow", text="Set Flow")
            row = box.row(align=False)
            row.alignment = 'CENTER'
            row.operator("mesh.dissolve_limited", text="Limited Dissolve")
        # Edit edges
        if sel_mode[1]:
            row = box.row(align=False)
            row.operator("mesh.bridge_edge_loops", text="Bridge")
            row.operator("mesh.edge_face_add", text="Fill")
            row = box.row(align=False)
            row.alignment = 'CENTER'
            row.operator("mesh.set_edge_flow", text="Set Flow")
            if sel_mode[0]:
                row = box.row(align=False)
                row.alignment = 'CENTER'
            row.operator("mesh.dissolve_limited", text="Limited Dissolve")
        # Edit polygons
        if sel_mode[2]:
            if prefs.enable_fast_merge:
                row = box.row(align=False)
                row.alignment = 'CENTER'
                row.operator("mesh.connect2", text="Connect")
            row = box.row(align=False)
            row.operator("mesh.bridge_edge_loops", text="Bridge")
            row.operator("mesh.flip_normals", text="Flip")

            row = box.row(align=False)
            row.operator("mesh.edge_face_add", text="Fill")
            row.operator("mesh.set_edge_flow", text="Set Flow")
            row = box.row(align=False)
            row.alignment = 'CENTER'
            row.operator("mesh.dissolve_limited", text="Limited Dissolve")

        # Vertex color
        row = box.row(align=True)
        row.label(text="Vertex Color")
        row = box.row(align=False)
        row.operator("keyops.toolkit_panel", text="Set Color").type = "set_vertex_color"
        row.prop(context.scene, "vertex_color", text="")
        row = box.row(align=False)
        row.prop(context.scene, "RGB_Enum", expand=True, emboss=False)

        # Edit geometry
        row = box.row(align=False)
        row = box.row(align=False)
        row = box.row(align=False)

        row.label(text="Edit Geometry")
        row = box.row(align=False)
        row.alignment = 'CENTER'
        # Repeat last operator
        row.operator("screen.repeat_last", text="Repeat Last")
        row = box.row(align=False)
        row.alignment = 'RIGHT'
        # Correct face attributes
        row.prop(context.scene.tool_settings, "use_transform_correct_face_attributes", text="Preserve UVs")
        popover_kw = {"space_type": 'VIEW_3D', "region_type": 'UI', "category": "Tool"}
        row.popover_group(context=".mesh_edit", **popover_kw)
        row = box.row(align=False)
        row.operator("mesh.merge", text="Merge Center").type = 'CENTER'
        row.operator("mesh.edge_collapse", text="Collapse")
        # Separate
        row = box.row(align=False)
        row.operator("mesh.separate", text="Separate")
        row.operator("mesh.rip_move", text="Rip")
        row = box.row(align=False)
        row.operator("mesh.bisect", text="Slice Plane")
        row.operator("mesh.knife_tool", text="Cut")
        row = box.row(align=False)
        row.operator("mesh.subdivide", text="Subdivide")
        row.operator("mesh.unsubdivide", text="Un-Subdivide")
        row = box.row(align=False)
        row.operator("mesh.looptools_flatten", text="Make Planar")
        row.operator("mesh.looptools_circle", text="Circle")
        row = box.row(align=False)
        row.alignment = 'CENTER'
        row.operator("mesh.looptools_relax", text="Relax")
        row = box.row(align=False)
        row.operator("mesh.hide", text="Hide Selected")
        row.operator("mesh.reveal", text="Unhide All")
        row = box.row(align=False)
        row.alignment = 'CENTER'
        row.operator("mesh.hide", text="Hide Unselected").unselected = True

        # Cylinder
        row = box.row(align=False)
        row.label(text="Cylinder")
        row = box.row(align=False)
        row.operator("keyops.toolkit_panel", text="Un-Subdivide").type = "un_subdivide_cylinder"
        row.operator("keyops.toolkit_panel", text="Subdivide").type = "subdivide_cylinder"
    else:
        # UV
        col = box.column(align=True)

        if prefs.enable_uv_tools:
            row = col.row(align=True)
            row.operator("keyops.seam_by_angle", text="Seam by Angle", icon="MOD_EDGESPLIT")
        row = col.row(align=True)

        # Edit mesh
        row = col.row(align=True)
        row.operator("mesh.extrude_edge_by_normal", text="Extrude Edge by Normal")
        row = col.row(align=True)
        row.operator("mesh.flip_normals", text="Flip")
        row.operator("mesh.normals_make_consistent", text="Recalculate")
        row = col.row(align=True)
        row.operator("mesh.remove_doubles", text="Weld")
        row.operator("mesh.bridge_edge_loops", text="Bridge")
        row = col.row(align=True)
        if prefs.enable_fast_merge:
            row.operator("mesh.connect2", text="Connect")
        row.operator("mesh.subdivide", text="Subdivide")
        row = col.row(align=True)
        row.operator("mesh.edge_face_add", text="Fill")

        row = col.row(align=True)
        row.operator("mesh.dissolve_limited", text="Limited Dissolve")
        row = col.row(align=True)
        if sel_mode[0] or sel_mode[1]:
            row.operator("mesh.rip_move", text="Rip")
        else:
            row.operator("mesh.split", text="Split")
        row.operator("mesh.separate", text="Separate")

        if prefs.experimental:
            row = box.row(align=False)
            row.operator("keyops.toolkit_panel", text="Change Hard Bevel Width", icon="MOD_BEVEL").type = "change_hard_bevel_width"

        # Vertex color
        col = box
        row = col.row(align=True)
        row.label(text="Vertex Color")
        row = col.row(align=False)
        row.operator("keyops.toolkit_panel", text="Set Color").type = "set_vertex_color"
        row.prop(context.scene, "vertex_color", text="")
        row = col.row(align=False)
        row.prop(context.scene, "RGB_Enum", expand=True, emboss=False)

        # Select
        col = box.column(align=True)
        row = col.row(align=True)
        row.label(text="Select")
        row = col.row(align=True)
        row.operator("mesh.select_more", text="More", icon="ADD")
        row.operator("mesh.select_less", text="Less", icon="REMOVE")
        row = col.row(align=True)
        row.operator("mesh.loop_multi_select", text="Loop").ring=False
        row.operator("mesh.loop_multi_select", text="Ring").ring=True
        row = col.row(align=True)
        row.operator("mesh.region_to_loop", text="Boundary")
        row.operator("mesh.loop_to_region", text="Inner Region")
        row = col.row(align=True)

        if sel_mode[2]:
            row.operator("mesh.faces_select_linked_flat", text="By Angle")
        else:
            row.operator("mesh.edges_select_sharp", text="Edge Angle")
        row.operator("mesh.select_similar", text="Similar")
        # Checker deselect
        row = col.row(align=True)
        row.operator("mesh.select_nth", text="Checker Deselect")
        row = col.row(align=True)
        row.operator("mesh.select_non_manifold", text="Non Manifold")
        row.operator("mesh.select_face_by_sides", text="Ngons").type = 'GREATER'

        # Cylinder
        col = box.column(align=True)
        row = col.row(align=True)
        row.label(text="Cylinder", icon="MESH_CYLINDER")
        row = col.row(align=True)
        row.operator("keyops.toolkit_panel", text="Un-Subdivide").type = "un_subdivide_cylinder"
        row.operator("keyops.toolkit_panel", text="Subdivide").type = "subdivide_cylinder"
        row = col.row(align=True)
        row.operator("keyops.toolkit_panel", text="Cylinder from Edge", icon="MOD_SCREW").type = "change_cylinder_segments_modifier"


class EditModePanel(bpy.types.Panel):
    bl_description = "Modeling Panel"
    bl_label = ""
    bl_idname = "KEYOPS_PT_modeling_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'
    # bl_parent_id = "KEYOPS_PT_toolkit_panel"

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            return True
        
    def draw_header(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.label(text="Edit Mesh", icon_value=get_icon("editmode"))
        row.popover(panel="EDIT_PT_Settings", text="", icon='PREFERENCES')

    def draw(self, context):
        draw_edit_mode_panel(self, context, draw_header=False)

class ObjectModePanel(bpy.types.Panel):
    bl_description = "Object Mode Panel"
    bl_label = "Object"
    bl_idname = "KEYOPS_PT_object_mode_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'
    # bl_parent_id = "KEYOPS_PT_toolkit_panel"

    def draw_header(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.label(text="", icon_value=get_icon('mesh_cube'))

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'
    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Object Operations")
        col = box.column(align=False) 

        row = col.row(align=True)
        row.scale_y = 1.15
        row.operator("keyops.toolkit_panel", text="Quick Join Objects", icon = "EVENT_J").type = "Smart_Join_Objects"

        row = col.row(align=True)
        row.scale_y = 1.15
        row.operator("keyops.toolkit_panel", text="Duplicate Linked Modifiers", icon = "LINKED").type = "duplicate_linked_modifiers"
        row = col.row(align=False)
        row.scale_y = 1.15
        row.operator("keyops.toolkit_panel", text="Instant Apply All Modifiers",  icon_value=get_icon("mesh")).type = "Instant_Apply_Modifiers"
        row = col.row(align=True)
        row.scale_y = 1.15
        row.operator("keyops.toolkit_panel", text="Snap to Grid Floor", icon = "VIEW_PERSPECTIVE").type = "snap_to_floor"
        row = col.row(align=True)
        row.scale_y = 1.15
        row.operator("object.smart_apply_scale", text="Smart Apply Scale", icon = "FREEZE")
        row = col.row(align=True)
        row.operator("keyops.toolkit_panel", text="Clear Custom Normals", icon="X").type = "clear_custom_normals"


        box = layout.box()
        box.label(text="High/Low Collections")
        col = box.column(align=True)
        row = col.row(align=True)
        row.operator("keyops.toolkit_panel", text="Unique Collection Copy", icon="COLLECTION_COLOR_02").type = "unique_collection_duplicat"
        row = col.row(align=True)
        row.operator("keyops.toolkit_panel", text="Toggle").type = "toggle_high_low"
        row.operator("keyops.toolkit_panel", text="high").type = "high"
        row.operator("keyops.toolkit_panel", text="low").type = "low"

class EDIT_PT_Settings(bpy.types.Panel):
    bl_label = "Edit Panel Settings"
    bl_idname = "EDIT_PT_Settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        prefs = get_keyops_prefs()
        layout = self.layout
        col = layout.column(align=True)
        layout.label(text="Edit Mesh Panel Settings")
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(prefs, "max_layout", text="3ds Max Inspired Layout")
        

# class NewToolkitPanel(bpy.types.Panel):
#     bl_description = "Object Mode Panel"
#     bl_label = "Toolkit Panel"
#     bl_idname = "KEYOPS_PT_toolkit_panel"
#     bl_space_type = 'VIEW_3D'
#     bl_region_type = 'UI'
#     bl_category = 'Toolkit'
#     # bl_parent_id = "KEYOPS_PT_toolkit_panel"

#     def draw_header(self, context):
#         layout = self.layout
#         row = layout.row(align=True)
#         # row.label(text="", icon_value=get_icon('mesh_cube'))

#     def draw_header_preset(self, context):
#         layout = self.layout    
#         row = layout.row(align=True)
#         row.label(text="", icon="PREFERENCES")

#     def draw(self, context):
#         def modifiers():
#             layout = self.layout
#             prefs = get_keyops_prefs()
#             wm = bpy.context.window_manager
            
#             box = layout.box()
#             box.label(text="UV Tools")
#             col = box.column(align=True)
#             row = col.row(align=True)
#             column = row.column(align=True) 
#             row = column.split(factor=0.57, align=True)
#             row.scale_y = 1.15

#             if bpy.context.mode == 'EDIT_MESH':
#                 row.operator("keyops.toolkit_panel", text="Offset UV", icon="AREA_JOIN").type = "offset_uv"   
#                 row.operator("keyops.toolkit_panel", text="Remove").type = "Remove_Offset_UV"
#             else:   
#                 row.operator("keyops.toolkit_panel", text="Offset UV", icon="AREA_JOIN").type = "offset_uv"
#                 row.operator("keyops.toolkit_panel", text="Remove").type = "Remove_Offset_UV"
#             row = column.split(factor=0.57, align=True)
#             row.operator("keyops.toolkit_panel", text="Triplanar UV", icon="AXIS_SIDE").type = "Triplanar_UV_Mapping"
#             row.operator("keyops.toolkit_panel", text="Remove").type = "Remove_Triplanar_UV_Mapping"

#             if prefs.enable_uv_tools:
#                 row = column.split(align=True)
#                 row.operator("keyops.sharp_from_uv_islands", text="Sharp from UV Islands", icon="MOD_EDGESPLIT")
        
#             box = layout.box()
#             row = box.row()
#             row = row.split(factor=0.45, align=True)
#             row.operator("keyops.add_modifier", text="Lattice", icon="MOD_LATTICE").type = "LATTICE"
#             operation_FFD2X = row.operator("keyops.add_modifier", text="FFD 3x")
#             operation_FFD2X.subdivisions = 3
#             operation_FFD2X.type = "LATTICE"

#             operation_FFD2X = row.operator("keyops.add_modifier", text="FFD 4x")
#             operation_FFD2X.subdivisions = 4
#             operation_FFD2X.type = "LATTICE"

#             if context.mode == 'OBJECT':
#                 # box.label(text="Booleans")
#                 row = box.row(align=True)
#                 row.label(text="Booleans")
#                 row = box.row(align=True)
#                 row.scale_y = 1.5
#                 row.scale_x = 1.5
#                 row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("diffrance")).type = "DIFFERENCE"
#                 row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("union")).type = "UNION"
#                 row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("intersection")).type = "INTERSECT"
#                 row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("slice")).type = "SLICE"

#                 row = box.row()
#                 row.operator("object.boolean_scroll", text="Boolean Scroll", icon="MOD_BOOLEAN")

#                 row = box.row()
#                 row.scale_y = 1.05
#                 row.prop(wm, "live_booleans", text="Realtime Booleans")

#             row = box.row()
#             row.scale_y = 1.15
#             row.operator("keyops.toolkit_panel", text="Instant Apply Modifiers", icon="OUTLINER_OB_MESH").type = "Instant_Apply_Modifiers"

#             if context.mode == 'OBJECT':
#                 header, panel_changde_meshes = box.panel(idname="Set Bevel",  default_closed=True)
#                 header.label(text="Set Bevel", icon = "MOD_BEVEL")
#                 if panel_changde_meshes:
#                     layout = box
#                     col = layout.column(align=False)
#                     row = col.row(align=False)

#                     row.prop(context.scene, "bevel_segments_type", text="Set")
#                     row = col.row(align=False)
#                     col = layout.column(align=True)

#                     row = col.row(align=True)
#                     row.operator("keyops.toolkit_panel", text="Set Value", icon= "MOD_BEVEL").type = "set_bevel_segment_amount" 
#                     row.operator("keyops.toolkit_panel", text="Set by %", icon= "MOD_BEVEL").type = "bevel_segment_amount_by_%"
#                     row = col.row(align=True)
#                     row.prop(context.scene, "bevel_segment_amount", text="")
#                     row.prop(context.scene, "bevel_segment_by_percent", text="")

#                     row = layout.row()
#                     row.operator("keyops.toolkit_panel", text="Hide by Offset", icon= "MOD_BEVEL").type = "hide_bevels_by_offset"
#                     row = layout.row()
#                     row.prop(context.scene, "compensate_for_scale", text="Scale")
#                     row.prop(context.scene, "bevel_offset", text="")

#         def object():
#             layout = self.layout
#             prefs = get_keyops_prefs()
#             wm = bpy.context.window_manager
#             box = layout.box()
#             box.label(text="Object Operations")
#             col = box.column(align=False) 
#             row = col.row(align=False)
#             row.scale_y = 1.15
#             row.operator("keyops.toolkit_panel", text="Quick Join Objects", icon = "EVENT_J").type = "Smart_Join_Objects"

#             row = col.row(align=True)
#             row.scale_y = 1.15
#             row.operator("keyops.toolkit_panel", text="Duplicate Linked Modifiers", icon = "LINKED").type = "duplicate_linked_modifiers"
#             row = col.row(align=True)
#             row.scale_y = 1.15
#             row.operator("keyops.toolkit_panel", text="Snap to Grid Floor", icon = "VIEW_PERSPECTIVE").type = "snap_to_floor"
#             row = col.row(align=True)
#             row.scale_y = 1.15
#             row.operator("object.smart_apply_scale", text="Smart Apply Scale", icon = "FREEZE")
#             row = col.row(align=True)
#             row.operator("keyops.toolkit_panel", text="Clear Custom Normals", icon="X").type = "clear_custom_normals"


#             box = layout.box()
#             box.label(text="High/Low Collections")
#             col = box.column(align=True)
#             row = col.row(align=True)
#             row.operator("keyops.toolkit_panel", text="Unique Collection Copy", icon="COLLECTION_COLOR_02").type = "unique_collection_duplicat"
#             row = col.row(align=True)
#             row.operator("keyops.toolkit_panel", text="Toggle").type = "toggle_high_low"
#             row.operator("keyops.toolkit_panel", text="high").type = "high"
#             row.operator("keyops.toolkit_panel", text="low").type = "low"
        
    
        # modifiers()
        # object()
