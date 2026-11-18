import bpy.types
import math
from ..utils.pref_utils import get_keyops_prefs, get_icon

prefs = get_keyops_prefs()

# to do:
# add X symmetrize option for decimate modifier - DONE
# orginize menu panel better
# replace delete small face with delete by mesh island
# use split edge node instead of modifer
# place the lods in the current collection?
# add auto smooth angle
# add data transfere for normals - DONE
# Convert Deletesmall Faces/DeleteLooseEdges to function instead
#option for planar decimation

def delete_small_faces_node_group():
    """Geometry Nodes group that deletes faces smaller than 'Max Face Size' (by area)."""
    tree = bpy.data.node_groups.new(type='GeometryNodeTree', name="Delete Small Faces")
    tree.is_modifier = True
    tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    size = tree.interface.new_socket(name="Max Face Size", in_out='INPUT', socket_type='NodeSocketFloat')
    size.default_value = 0.0001
    size.min_value = 0.0
    nodes, links = tree.nodes, tree.links
    group_in = nodes.new("NodeGroupInput")
    group_out = nodes.new("NodeGroupOutput")
    group_out.is_active_output = True
    area = nodes.new("GeometryNodeInputMeshFaceArea")
    compare = nodes.new("FunctionNodeCompare")
    compare.data_type = 'FLOAT'
    compare.operation = 'LESS_THAN'
    delete = nodes.new("GeometryNodeDeleteGeometry")
    delete.domain = 'FACE'
    delete.mode = 'ALL'
    links.new(area.outputs["Area"], compare.inputs[0])
    links.new(group_in.outputs["Max Face Size"], compare.inputs[1])
    links.new(group_in.outputs["Geometry"], delete.inputs["Geometry"])
    links.new(compare.outputs["Result"], delete.inputs["Selection"])
    links.new(delete.outputs["Geometry"], group_out.inputs["Geometry"])
    return tree


def _max_face_size_id(tree):
    return next(item.identifier for item in tree.interface.items_tree
                if getattr(item, "in_out", "") == 'INPUT' and item.name == "Max Face Size")


def delete_loose_edge_node_group():
    delete_loose_edge = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Delete Loose Edge")

    delete_loose_edge.is_modifier = True
    
    #initialize delete_loose_edge nodes
    #delete_loose_edge interface
    #Socket Geometry
    geometry_socket = delete_loose_edge.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'
    
    #Socket Geometry
    geometry_socket_1 = delete_loose_edge.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket_1.attribute_domain = 'POINT'
    
    
    #node Group Input
    group_input = delete_loose_edge.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"
    
    #node Boolean Math
    boolean_math = delete_loose_edge.nodes.new("FunctionNodeBooleanMath")
    boolean_math.name = "Boolean Math"
    boolean_math.operation = 'NOT'
    #Boolean_001 (Blender 5.3+ has no second input for NOT)
    if len(boolean_math.inputs) > 1:
        boolean_math.inputs[1].default_value = False
    
    #node Delete Geometry
    delete_geometry = delete_loose_edge.nodes.new("GeometryNodeDeleteGeometry")
    delete_geometry.name = "Delete Geometry"
    delete_geometry.domain = 'EDGE'
    delete_geometry.mode = 'ALL'
    
    #node Edge Neighbors
    edge_neighbors = delete_loose_edge.nodes.new("GeometryNodeInputMeshEdgeNeighbors")
    edge_neighbors.name = "Edge Neighbors"
    
    #node Group Output
    group_output = delete_loose_edge.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True
    
    
    
    
    #Set locations
    group_input.location = (-340.0, 0.0)
    boolean_math.location = (-203.79037475585938, -102.6886215209961)
    delete_geometry.location = (-35.70556640625, 64.91195678710938)
    edge_neighbors.location = (-388.9553527832031, -148.6557159423828)
    group_output.location = (166.10665893554688, 65.12358093261719)
    
    #Set dimensions
    group_input.width, group_input.height = 140.0, 100.0
    boolean_math.width, boolean_math.height = 140.0, 100.0
    delete_geometry.width, delete_geometry.height = 140.0, 100.0
    edge_neighbors.width, edge_neighbors.height = 140.0, 100.0
    group_output.width, group_output.height = 140.0, 100.0
    
    #initialize delete_loose_edge links
    #group_input.Geometry -> delete_geometry.Geometry
    delete_loose_edge.links.new(group_input.outputs[0], delete_geometry.inputs[0])
    #delete_geometry.Geometry -> group_output.Geometry
    delete_loose_edge.links.new(delete_geometry.outputs[0], group_output.inputs[0])
    #boolean_math.Boolean -> delete_geometry.Selection
    delete_loose_edge.links.new(boolean_math.outputs[0], delete_geometry.inputs[1])
    #edge_neighbors.Face Count -> boolean_math.Boolean
    delete_loose_edge.links.new(edge_neighbors.outputs[0], boolean_math.inputs[0])
    return delete_loose_edge


class AutoLOD(bpy.types.Operator):
    bl_idname = "keyops.auto_lod"
    bl_label = "Auto LOD"
    bl_description = "Auto LOD"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.keyops.auto_lod_props
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        suffix = props.suffix
        parent_object = props.lod_parent_object
        apply_decimate_modifier = props.apply_decimate_modifier
        amount_of_lods = props.amount_of_lods
        lod_difference = props.lod_difference / 100.0
        edge_split = props.edge_split
        max_face_size = props.max_face_size
        remove_non_manifold_faces = props.remove_non_manifold_faces
        multipler = props.multipler
        transfere_normals = props.transfere_normals
        transfere_edge_normals = props.transfere_edge_normals
        create_collection = props.create_collection
        add_weighted_normals = props.add_weighted_normals

        total_steps = len(selected_objects) * amount_of_lods
        current_step = 0

        # Begin progress bar
        wm = bpy.context.window_manager
        wm.progress_begin(0, total_steps)

        orginal_objects = selected_objects.copy()

        # if props.iterativ_lod_suffix:
        #     for obj in orginal_objects:
        #         if "_LOD_" in obj.name:
        #             obj.name = obj.name[:-13]
        #         obj["LOD"] = str(0)
 

        if props.delete_loose_edges:
            if bpy.data.node_groups.get("Delete Loose Edge") is None:
                delete_loose_edge_node_group()

        for obj in selected_objects:
            for i in range(amount_of_lods):
                # Update progress cursor
                wm.progress_update(current_step)

                new_object = obj.copy()
                new_object.data = obj.data.copy()

                # if not props.iterativ_lod_suffix:
                lod_name = f"{obj.name}{suffix}{(i + 1)}"
                # else:
                #     start_prefix = "_LOD_"

                #     lod_name = f"{obj.name}{start_prefix}" + f"{(i + 1)}"
                #     new_object["LOD"] = str(i + 1)

                new_object.name = lod_name

                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    bpy.context.collection.objects.link(new_object)

                    if edge_split:
                        split_edge_modifier = new_object.modifiers.new(name="EDGE_SPLIT", type="EDGE_SPLIT")
                        split_edge_modifier.show_in_editmode = False
                        split_angle_degrees = props.edge_split_angle
                        split_angle_radians = math.radians(split_angle_degrees)
                        split_edge_modifier.split_angle = split_angle_radians

                    decimate_modifier = new_object.modifiers.new(name="Decimate", type='DECIMATE')
                    decimate_modifier.ratio = (1 - lod_difference) ** (i + 1)
                    if props.keep_symmetry_X:
                        decimate_modifier.use_symmetry = True

                    if props.unlock_normals_on_all_lods:
                        bpy.ops.mesh.customdata_custom_splitnormals_clear()

                    if apply_decimate_modifier:
                        bpy.ops.object.modifier_apply(modifier="EDGE_SPLIT")
                        bpy.ops.object.modifier_apply(modifier="Decimate")

                    if parent_object:
                        new_object.parent = obj
                        new_object.matrix_parent_inverse = obj.matrix_world.inverted()

                    bpy.context.view_layer.objects.active = new_object

                    if props.delete_loose_edges:
                        if bpy.context.object.modifiers.get("Delete Loose Edge") is None:
                            bpy.context.object.modifiers.new('Delete Loose Edge', 'NODES')
                            bpy.context.object.modifiers['Delete Loose Edge'].node_group = bpy.data.node_groups['Delete Loose Edge']

                    if remove_non_manifold_faces:
                        tree = bpy.data.node_groups.get("Delete Small Faces") or delete_small_faces_node_group()
                        modifier = new_object.modifiers.get("Delete Small Faces")
                        if modifier is None:
                            modifier = new_object.modifiers.new("Delete Small Faces", 'NODES')
                        modifier.node_group = tree
                        modifier[_max_face_size_id(tree)] = max_face_size * (multipler ** i)

                    if transfere_normals or transfere_edge_normals:
                        mod = new_object.modifiers.new(type='DATA_TRANSFER', name='Transfere_Normals')
                        mod.object = obj
                        mod.use_object_transform = False

                    if transfere_edge_normals:
                        mod.data_types_edges = {'SHARP_EDGE'}

                    if transfere_normals:
                        mod.data_types_loops = {'CUSTOM_NORMAL'}

                    if add_weighted_normals:
                        mod = new_object.modifiers.new(type='WEIGHTED_NORMAL', name='Weighted Normals')
                        mod.keep_sharp = True

                    current_step += 1

        if apply_decimate_modifier:
            bpy.ops.object.modifier_apply(modifier="Decimate")
            bpy.ops.object.modifier_apply(modifier="EDGE_SPLIT")

        # End progress bar

        # Rename the original objects with the suffix
        for obj in orginal_objects:
            if obj.type == 'MESH':
                # if props.iterativ_lod_suffix:
                #     obj.name = obj.name + "_LOD_0_______"
                # else:
                    obj.name = f"{obj.name}{suffix}0"

        # create collections for each orginal object and name them the same name as the orginal object - suffix
        if create_collection:
            for obj in orginal_objects:
                # remove the suffix from the name to get the collection name without suffix
                collection_name = obj.name[:-len(suffix)]
                collection = bpy.data.collections.new(collection_name)
                bpy.context.scene.collection.children.link(collection)
        wm.progress_end()

        return {'FINISHED'}
def register_auto_lod():
    bpy.utils.register_class(AutoLOD)
    # bpy.utils.register_class(GenerateLODPanel)

def unregister_auto_lod():
    bpy.utils.unregister_class(AutoLOD)
    # bpy.utils.unregister_class(GenerateLODPanel)

def draw_lod_panel(self, context, draw_header=False):
    layout = self.layout    
    box = layout.box()
    props = context.scene.keyops.auto_lod_props

    if draw_header:
        row = box.row()
        row.label(text="Generate LOD", icon_value=get_icon("mesh_icosphere2"))
    row = box.row()

    # if not props.iterativ_lod_suffix:
    #     row.prop(props, "iterativ_lod_suffix", text="Auto")
    # else:
    row.alignment = 'LEFT'
    row.prop(props, "suffix")
    # row.prop(props, "iterativ_lod_suffix", text="Auto")
    row = box.row(align=True)
    row.prop(props, "lod_parent_object", text="Parent")

    row.prop(props, "keep_symmetry_X", text="Symmetry")

    row = box.row()
    row.label(text="Transfere Normals:")
    row = box.row(align=True)
    row.prop(props, "transfere_normals", text="Face Normals", toggle=True)
    row.prop(props, "transfere_edge_normals", text="Edge Normals", toggle=True)

    row = box.row()
    row.prop(props, "add_weighted_normals", text="Weighted Normals")

    row = box.row()
    row.prop(props, "unlock_normals_on_all_lods", text="Unlock Normals")

    row = box.row()
    row.prop(props, "amount_of_lods", text="Amount of LODs")

    row = box.row()
    row.prop(props, "lod_difference", text="LOD Difference %")

    row = box.row()
    row.scale_y = 1.4
    row.operator("keyops.auto_lod", text="Generate LODs", icon='MESH_ICOSPHERE')

class GenerateLODPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_generate_lod"
    bl_label = "Generate LOD"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'
    bl_options = {'DEFAULT_CLOSED'}
    # bl_parent_id = "KEYOPS_PT_toolkit_panel"

    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT":
            return True

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon_value=get_icon("mesh_icosphere"))

    def draw(self, context):
        draw_lod_panel(self, context)