import bpy.types
import math
from ..utils.pref_utils import get_keyops_prefs

prefs = get_keyops_prefs()

#to do:
#add X symmetrize option for decimate modifier - DONE
#orginize menu panel better
#replace delete small face with delete by mesh island
#use split edge node instead of modifer
#place the lods in the current collection?
#add auto smooth angle
#add data transfere for normals
#fix node group for delete small faces error and update to last version

class AutoLOD(bpy.types.Operator):
    bl_idname = "keyops.auto_lod"
    bl_label = "Auto LOD"
    bl_description = "Auto LOD"
    bl_options = {'REGISTER', 'UNDO'}
 
    def register():
        bpy.utils.register_class(DeleteSmallFaces)
        bpy.utils.register_class(DeleteLooseEdges)
        bpy.utils.register_class(GenerateLODOperator)
        bpy.utils.register_class(PreserveSmallerShapesOperator)
        bpy.utils.register_class(CopyAttributestoSelection)
        bpy.utils.register_class(RemovePreserveThinShapesOperator)
        bpy.utils.register_class(GenerateLODPanel)

    def unregister():
        bpy.utils.unregister_class(DeleteSmallFaces)
        bpy.utils.unregister_class(DeleteLooseEdges)
        bpy.utils.unregister_class(GenerateLODOperator)
        bpy.utils.unregister_class(PreserveSmallerShapesOperator)
        bpy.utils.unregister_class(CopyAttributestoSelection)
        bpy.utils.unregister_class(RemovePreserveThinShapesOperator)
        bpy.utils.unregister_class(GenerateLODPanel)

class DeleteSmallFaces(bpy.types.Operator):
    bl_idname = "object.delete_small_faces"
    bl_label = "Delete Small Faces"

    def execute(self, context):
        if bpy.data.node_groups.get("Delete Small Faces") is None:
            delete_small_faces = bpy.data.node_groups.new(type="GeometryNodeTree", name="Delete Small Faces")

            # Initialize delete_small_faces nodes
            # delete_small_faces outputs
            # output Geometry
            delete_small_faces.outputs.new('NodeSocketGeometry', "Geometry")
            delete_small_faces.outputs[0].attribute_domain = 'POINT'

            # node Group Output
            group_output = delete_small_faces.nodes.new("NodeGroupOutput")

            # node Face Area
            face_area = delete_small_faces.nodes.new("GeometryNodeInputMeshFaceArea")

            # node Compare.001
            compare_001 = delete_small_faces.nodes.new("FunctionNodeCompare")
            compare_001.data_type = 'INT'
            compare_001.operation = 'EQUAL'
            compare_001.mode = 'ELEMENT'
            # A
            compare_001.inputs[0].default_value = 0.0
            # B
            compare_001.inputs[1].default_value = 0.0
            # B_INT
            compare_001.inputs[3].default_value = 1
            # A_VEC3
            compare_001.inputs[4].default_value = (0.0, 0.0, 0.0)
            # B_VEC3
            compare_001.inputs[5].default_value = (0.0, 0.0, 0.0)
            # A_COL
            compare_001.inputs[6].default_value = (0.0, 0.0, 0.0, 0.0)
            # B_COL
            compare_001.inputs[7].default_value = (0.0, 0.0, 0.0, 0.0)
            # A_STR
            compare_001.inputs[8].default_value = ""
            # B_STR
            compare_001.inputs[9].default_value = ""
            # C
            compare_001.inputs[10].default_value = 0.8999999761581421
            # Angle
            compare_001.inputs[11].default_value = 0.08726649731397629
            # Epsilon
            compare_001.inputs[12].default_value = 0.0010000000474974513

            # node Edge Neighbors
            edge_neighbors = delete_small_faces.nodes.new("GeometryNodeInputMeshEdgeNeighbors")

            # delete_small_faces inputs
            # input Geometry
            delete_small_faces.inputs.new('NodeSocketGeometry', "Geometry")
            delete_small_faces.inputs[0].attribute_domain = 'POINT'

            # input Threshold
            delete_small_faces.inputs.new('NodeSocketFloat', "Threshold")
            delete_small_faces.inputs[1].default_value = 0.15000000596046448
            delete_small_faces.inputs[1].min_value = -10000.0
            delete_small_faces.inputs[1].max_value = 10000.0
            delete_small_faces.inputs[1].attribute_domain = 'POINT'

            # node Group Input
            group_input = delete_small_faces.nodes.new("NodeGroupInput")

            # node Compare
            compare = delete_small_faces.nodes.new("FunctionNodeCompare")
            compare.data_type = 'FLOAT'
            compare.operation = 'LESS_THAN'
            compare.mode = 'ELEMENT'
            # A_INT
            compare.inputs[2].default_value = 0
            # B_INT
            compare.inputs[3].default_value = 0
            # A_VEC3
            compare.inputs[4].default_value = (0.0, 0.0, 0.0)
            # B_VEC3
            compare.inputs[5].default_value = (0.0, 0.0, 0.0)
            # A_COL
            compare.inputs[6].default_value = (0.0, 0.0, 0.0, 0.0)
            # B_COL
            compare.inputs[7].default_value = (0.0, 0.0, 0.0, 0.0)
            # A_STR
            compare.inputs[8].default_value = ""
            # B_STR
            compare.inputs[9].default_value = ""
            # C
            compare.inputs[10].default_value = 0.8999999761581421
            # Angle
            compare.inputs[11].default_value = 0.08726649731397629
            # Epsilon
            compare.inputs[12].default_value = 0.0010000000474974513

            # node Delete Geometry
            delete_geometry = delete_small_faces.nodes.new("GeometryNodeDeleteGeometry")
            delete_geometry.domain = 'FACE'
            delete_geometry.mode = 'ALL'

            # node Boolean Math
            boolean_math = delete_small_faces.nodes.new("FunctionNodeBooleanMath")
            boolean_math.operation = 'AND'

            #Set locations
            group_output.location = (200.0, 0.0)
            face_area.location = (-495.7608947753906, -327.19476318359375)
            compare_001.location = (-485.3419494628906, -115.89753723144531)
            edge_neighbors.location = (-669.9352416992188, -188.025146484375)
            group_input.location = (-796.7938842773438, -25.583044052124023)
            compare.location = (-307.2937316894531, -262.437744140625)
            delete_geometry.location = (-20.000003814697266, 62.11039352416992)
            boolean_math.location = (-183.51220703125, -117.73372650146484)


            # initialize delete_small_faces links
            # delete_geometry.Geometry -> group_output.Geometry
            delete_small_faces.links.new(delete_geometry.outputs[0], group_output.inputs[0])
            # group_input.Geometry -> delete_geometry.Geometry
            delete_small_faces.links.new(group_input.outputs[0], delete_geometry.inputs[0])
            # face_area.Area -> compare.A
            delete_small_faces.links.new(face_area.outputs[0], compare.inputs[0])
            # compare.Result -> boolean_math.Boolean
            delete_small_faces.links.new(compare.outputs[0], boolean_math.inputs[1])
            # edge_neighbors.Face Count -> compare_001.A
            delete_small_faces.links.new(edge_neighbors.outputs[0], compare_001.inputs[2])
            # compare_001.Result -> boolean_math.Boolean
            delete_small_faces.links.new(compare_001.outputs[0], boolean_math.inputs[0])
            # group_input.Threshold -> compare.B
            delete_small_faces.links.new(group_input.outputs[1], compare.inputs[1])
            # boolean_math.Boolean -> delete_geometry.Selection
            delete_small_faces.links.new(boolean_math.outputs[0], delete_geometry.inputs[1])
            return {'FINISHED'}

        if bpy.context.object.modifiers.get("Delete Small Faces") is None:
            bpy.context.object.modifiers.new('Delete Small Faces', 'NODES')
            bpy.context.object.modifiers['Delete Small Faces'].node_group = bpy.data.node_groups['Delete Small Faces']

        return {'FINISHED'}

class DeleteLooseEdges(bpy.types.Operator):
    bl_idname = "object.delete_loose_edges"
    bl_label = "Delete Loose Edges"

    def execute(self, context):
        # Check if the geometry node group exists
        if bpy.data.node_groups.get("DeleteLooseEdges") is None:
            # Create a group
            delete_loose_edges = bpy.data.node_groups.new('DeleteLooseEdges', 'GeometryNodeTree')

            # Create group inputs
            group_inputs = delete_loose_edges.nodes.new('NodeGroupInput')
            group_inputs.location = (-350, 0)
            delete_loose_edges.inputs.new('NodeSocketGeometry', 'Geometry')

            # Create group outputs
            group_outputs = delete_loose_edges.nodes.new('NodeGroupOutput')
            group_outputs.location = (300, 0)
            delete_loose_edges.outputs.new('NodeSocketGeometry', 'Geometry')

            # Create nodes in the group
            node_delete_geometry = delete_loose_edges.nodes.new('GeometryNodeDeleteGeometry')
            node_delete_geometry.domain = 'EDGE'
            node_delete_geometry.mode = 'ALL'
            node_delete_geometry.location = (100, 0)

            node_edge_neighbors = delete_loose_edges.nodes.new('GeometryNodeInputMeshEdgeNeighbors')
            node_edge_neighbors.location = (-100, -100)

            node_compare = delete_loose_edges.nodes.new('FunctionNodeCompare')
            node_compare.operation = 'EQUAL'
            node_compare.label = 'Equal'
            node_compare.data_type = 'INT'
            node_compare.location = (-50, -100)

            # Link inputs
            delete_loose_edges.links.new(group_inputs.outputs['Geometry'], node_delete_geometry.inputs[0])

            # Link outputs
            delete_loose_edges.links.new(node_delete_geometry.outputs[0], group_outputs.inputs['Geometry'])

            # Link nodes together
            delete_loose_edges.links.new(node_edge_neighbors.outputs[0], node_compare.inputs[2])
            delete_loose_edges.links.new(node_compare.outputs[0], node_delete_geometry.inputs[1])

        if bpy.context.object.modifiers.get("DeleteLooseEdges") is None:
            bpy.context.object.modifiers.new('DeleteLooseEdges', 'NODES')
            bpy.context.object.modifiers['DeleteLooseEdges'].node_group = bpy.data.node_groups['DeleteLooseEdges']

        return {'FINISHED'}

class GenerateLODOperator(bpy.types.Operator):
    bl_idname = "object.generate_lod"
    bl_label = "Generate LODs"

    @classmethod
    def poll(cls, context):
        return context.active_object.type == 'MESH'

    def execute(self, context):
        selected_objects = bpy.context.selected_objects
        suffix = context.scene.suffix
        parent_object = context.scene.lod_parent_object
        apply_decimate_modifier = context.scene.apply_decimate_modifier
        amount_of_lods = context.scene.amount_of_lods
        lod_difference = context.scene.lod_difference / 100.0
        unlock_normals_on_all_lods = context.scene.unlock_normals_on_all_lods
        edge_split = context.scene.edge_split
        max_face_size = context.scene.max_face_size
        remove_non_manifold_faces = context.scene.remove_non_manifold_faces
        multipler = context.scene.multipler
        delete_loose_edges = context.scene.delete_loose_edges   

        total_steps = len(selected_objects) * amount_of_lods
        current_step = 0

        # Begin progress bar
        wm = bpy.context.window_manager
        wm.progress_begin(0, total_steps)

        for obj in selected_objects:
            for i in range(amount_of_lods):
                # Update progress cursor
                wm.progress_update(current_step)

                new_object = obj.copy()
                new_object.data = obj.data.copy()

                lod_name = f"{obj.name}{suffix}{i + 1}"
                new_object.name = lod_name

                if obj.type == 'MESH':
                    bpy.context.collection.objects.link(new_object)

                    if edge_split:
                        split_edge_modifier = new_object.modifiers.new(name="EDGE_SPLIT", type="EDGE_SPLIT")
                        split_edge_modifier.show_in_editmode = False
                        split_angle_degrees = context.scene.edge_split_angle
                        split_angle_radians = math.radians(split_angle_degrees)
                        split_edge_modifier.split_angle = split_angle_radians
                

                    decimate_modifier = new_object.modifiers.new(name="Decimate", type='DECIMATE')
                    decimate_modifier.ratio = (1 - lod_difference) ** (i + 1)
                    if context.scene.keep_symmetry_X:
                        decimate_modifier.use_symmetry = True

                    if unlock_normals_on_all_lods:
                        bpy.ops.mesh.customdata_custom_splitnormals_clear()

                    bpy.context.object.data.auto_smooth_angle = 1.0472

                    if apply_decimate_modifier:
                        bpy.ops.object.modifier_apply(modifier="EDGE_SPLIT")
                        bpy.ops.object.modifier_apply(modifier="Decimate")
                    
                    if parent_object:
                        new_object.parent = obj
                        new_object.matrix_parent_inverse = obj.matrix_world.inverted()
                        
                    bpy.context.view_layer.objects.active = new_object
                    if delete_loose_edges:
                        bpy.ops.object.delete_loose_edges()

                    if remove_non_manifold_faces:
                        bpy.ops.object.delete_small_faces()

                        modifier = bpy.context.object.modifiers.get("Delete Small Faces")
                        if modifier is not None:
                            modifier["Input_2"] = max_face_size * (multipler ** i)
                        else:
                            print("Warning: 'Delete Small Faces' modifier not found.")

                    print(f"{lod_name} DONE")

                    current_step += 1   
        if apply_decimate_modifier:
            bpy.ops.object.modifier_apply(modifier="Decimate")
            bpy.ops.object.modifier_apply(modifier="EDGE_SPLIT")
        # End progress bar
        wm.progress_end()

        bpy.ops.ed.undo_push(True)
        return {'FINISHED'}

class CopyAttributestoSelection(bpy.types.Operator):
    bl_idname = "copy.attributes_to_selection"
    bl_label = "Copy Attributes to Selection"

    def execute(self, context):
        bpy.ops.object.vertex_group_copy_to_selected()
        active_object = bpy.context.object
        selected_objects = bpy.context.selected_objects.copy()
        selected_objects.remove(active_object)  # Remove the active object from the selected objects list
        modifier_name = "Weld"
        edge_split_index = 1 if any("EDGE_SPLIT" in obj.modifiers for obj in selected_objects) else 0

        active_modifiers = active_object.modifiers
        modifier = active_modifiers.get(modifier_name)

        if modifier:
            for obj in selected_objects:
                has_weld_modifier = any(mod.name == modifier_name for mod in obj.modifiers)
                has_preserve_group = "Preserve Group" in obj.vertex_groups

                if not has_weld_modifier:
                    new_modifier = obj.modifiers.new(name=modifier.name, type=modifier.type)
                    new_modifier.show_expanded = modifier.show_expanded
                    bpy.context.view_layer.objects.active = obj
                    bpy.context.object.vertex_groups.active.name = "Preserve Group"
                    new_modifier.vertex_group = "Preserve Group"
                    bpy.ops.object.modifier_move_to_index(modifier=modifier_name, index=edge_split_index)

        return {'FINISHED'}

class PreserveSmallerShapesOperator(bpy.types.Operator):
    bl_idname = "object.preserve_smaller_shapes"
    bl_label = "Preserve Smaller Shapes"

    def execute(self, context):
        vertex_group = context.object.vertex_groups.get("Preserve Group")
        weld_modifier = context.object.modifiers.get("Weld")
        edge_split_modifier = context.object.modifiers.get("EDGE_SPLIT")

        if weld_modifier is None:
            weld_modifier = context.object.modifiers.new(name="Weld", type='WELD')

            if vertex_group is None:
                bpy.ops.object.vertex_group_add()
                bpy.context.active_object.vertex_groups.active.name = "Preserve Group"
                bpy.context.object.modifiers["Weld"].vertex_group = "Preserve Group"
            else:
                bpy.context.active_object.vertex_groups.active.name = "Preserve Group"
                bpy.context.object.modifiers["Weld"].vertex_group = "Preserve Group"
            
        else:
            bpy.ops.object.vertex_group_assign()

        def check(obj, name):
            index = obj.modifiers.find(name)
            if index == -1:
                print(f"Couldn't find '{name}' modifier inside '{obj.name}' object")
            return index

        if edge_split_modifier is not None:
            bpy.ops.object.modifier_move_to_index(modifier="Weld", index=1)

        else:
            bpy.ops.object.modifier_move_to_index(modifier="Weld", index=0)


        return {'FINISHED'}

class RemovePreserveThinShapesOperator(bpy.types.Operator):
    bl_idname = "object.remove_preserve_thin_shapes"
    bl_label = "Remove Preserve Thin Shapes"

    def execute(self, context):
        bpy.ops.object.vertex_group_remove_from()
        return {'FINISHED'}


class GenerateLODPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_generate_lod"
    bl_label = "Generate LOD"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ToolKit'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return get_keyops_prefs().enable_auto_lod
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # layout.label(text="Normals:")

        # row = layout.row()
        # row.prop(scene, "edge_split", text="Edge Split")

        # row.prop(scene, "edge_split_angle", text="")

        # layout.label(text="LOD Settings:")

        row = layout.row()
        row.prop(scene, "suffix")
        row = layout.row()
        row.prop(scene, "lod_parent_object", text="Parent Object")

        # row = layout.row()
        # row.prop(scene, "apply_decimate_modifier", text="Apply Decimate Modifier")

        row = layout.row()
        row.prop(scene, "keep_symmetry_X", text="Symmetry X")

        row = layout.row()
        row.prop(scene, "delete_loose_edges", text="Delete Loose Edges")

        row = layout.row()
        row.prop(scene, "unlock_normals_on_all_lods", text="Unlock Normals")

        row = layout.row()
        row.prop(scene, "amount_of_lods", text="Amount of LODs")
        row = layout.row()
        row.prop(scene, "lod_difference", text="LOD Difference (%)")

        # row = layout.row()
        # row.prop(scene, "remove_non_manifold_faces", text="Remove non manifold faces")

        # row = layout.row()
        # row.prop(scene, "max_face_size", text="Max Face Size (%)")

        # row = layout.row()
        # row.prop(scene, "multipler", text="Multipler")

        row = layout.row()
        row.scale_y = 1.5
        row.operator("object.generate_lod", text="Generate LODs")

        layout.label(text="Add Preserve Shape to Selection:")
        
        if bpy.context.mode == 'EDIT_MESH':
            row = layout.row()
            row.operator("object.preserve_smaller_shapes", text="Add Preserve Thin Shapes")

        if bpy.context.mode == 'EDIT_MESH':
            row = layout.row()
            row.operator("object.remove_preserve_thin_shapes", text="Remove Preserve Thin Shapes")

        row = layout.row()
        row.enabled = bpy.context.mode == 'OBJECT'
        row.operator("copy.attributes_to_selection", text="Copy Attributes to Selection")

    def register():
        bpy.types.Scene.suffix = bpy.props.StringProperty(default="_LOD")
        bpy.types.Scene.lod_parent_object = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.apply_decimate_modifier = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.amount_of_lods = bpy.props.IntProperty(default=3, min=1)
        bpy.types.Scene.lod_difference = bpy.props.FloatProperty(default=50.0, min=0.0, max=100.0)
        bpy.types.Scene.unlock_normals_on_all_lods = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.edge_split = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.edge_split_angle = bpy.props.FloatProperty(default=60.0) 
        bpy.types.Scene.max_face_size = bpy.props.FloatProperty(default=0.0005)
        bpy.types.Scene.remove_non_manifold_faces = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.multipler = bpy.props.FloatProperty(default=2.0)
        bpy.types.Scene.delete_loose_edges = bpy.props.BoolProperty(default=False)
        bpy.types.Scene.keep_symmetry_X = bpy.props.BoolProperty(default=False)

    def unregister():
        del bpy.types.Scene.suffix
        del bpy.types.Scene.lod_parent_object
        del bpy.types.Scene.apply_decimate_modifier
        del bpy.types.Scene.amount_of_lods
        del bpy.types.Scene.lod_difference
        del bpy.types.Scene.unlock_normals_on_all_lods 
        del bpy.types.Scene.edge_split
        del bpy.types.Scene.edge_split_angle
        del bpy.types.Scene.max_face_size
        del bpy.types.Scene.remove_non_manifold_faces
        del bpy.types.Scene.multipler 
        del bpy.types.Scene.delete_loose_edges
        del bpy.types.Scene.keep_symmetry_X
