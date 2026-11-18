import bpy
from ..utils.pref_utils import get_keyops_prefs
from ..utils.pref_utils import clear_registered_keymaps
import bmesh
import math
from ..utils.utilities import BLENDER_VERSION_MAJOR_POINT_MINOR, select_loop, select_ring, operator_exists, safe_icon
from ..utils.pref_utils import get_icon
from .add_modifier import AddModifier
from .smart_apply_scale import SmartApplyScale
from .none_live_booleans import ENTERING_TRANSFORM_OT_None_Live_Booleans
from .add_modifier import BooleanScroll, AddBooleanModifier
from .extrude_edge_along_normals import register_extrude_edge_along_normals, unregister_extrude_edge_along_normals
from .offset_extrude_edge import register_offset_extrude_edge, unregister_offset_extrude_edge
from .set_flow import register_set_flow, unregister_set_flow
from .fast_mirror import register_fast_mirror, unregister_fast_mirror
from ..utils.node_groups import get_node_group

from .subobject_modes import draw_mode_row

BLENDER_VERSION = bpy.app.version

EDIT_MESH_TYPES = {"change_hard_bevel_width", "un_subdivide_cylinder", "subdivide_cylinder", "change_cylinder_segments_modifier", "set_vertex_color"}
OBJECT_MODE_TYPES = {"unique_collection_duplicat", "high", "low", "cleanup", "duplicate_linked_modifiers", "duplicate_linked_modifiers_and_move"}
SWITCH_TO_OBJECT_MODE_TYPES = {"Smart_Join_Objects", "set_sphere_normal", "seprate_objects_by"}


def move_selected_to_collection(context, collection):
    for obj in context.selected_objects:
        if collection not in obj.users_collection:
            collection.objects.link(obj)
        for coll in list(obj.users_collection):
            if coll != collection:
                coll.objects.unlink(obj)


def move_selected_to_new_collection(context, name):
    collection = bpy.data.collections.new(name)
    context.scene.collection.children.link(collection)
    move_selected_to_collection(context, collection)


registered_toolkit_panel_keymaps = []

def register_toolkit_panel_keymaps():
    global registered_toolkit_panel_keymaps
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type='EMPTY')

    kmi = km.keymap_items.new('keyops.toolkit_panel', 'C', 'PRESS', alt=True)
    kmi.properties.type = 'Instant_Apply_Modifiers'
    registered_toolkit_panel_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('keyops.snap_to_floor', 'THREE', 'PRESS', alt=True)
    registered_toolkit_panel_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('keyops.toolkit_panel', 'D', 'PRESS', alt=True, shift=True)
    kmi.properties.type = 'duplicate_linked_modifiers_and_move'
    registered_toolkit_panel_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('object.add_boolean_modifier_operator', 'NUMPAD_MINUS', 'PRESS', ctrl=True)
    kmi.properties.type = 'DIFFERENCE'
    registered_toolkit_panel_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('object.add_boolean_modifier_operator', 'NUMPAD_PLUS', 'PRESS', ctrl=True)
    kmi.properties.type = 'UNION'
    registered_toolkit_panel_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('object.add_boolean_modifier_operator', 'NUMPAD_ASTERIX', 'PRESS', ctrl=True)
    kmi.properties.type = 'INTERSECT'
    registered_toolkit_panel_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('object.add_boolean_modifier_operator', 'NUMPAD_SLASH', 'PRESS', ctrl=True)
    kmi.properties.type = 'SLICE'
    registered_toolkit_panel_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('keyops.fast_mirror', 'X', 'PRESS', alt=True)
    registered_toolkit_panel_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('keyops.fast_mirror_options', 'D', 'PRESS')
    registered_toolkit_panel_keymaps.append((km, kmi))

    km = wm.keyconfigs.addon.keymaps.new(name='Mesh', space_type='EMPTY')
    kmi = km.keymap_items.new('wm.call_menu', 'M', 'PRESS', alt=True)
    kmi.properties.name = 'MATERIAL_MT_material_list'
    registered_toolkit_panel_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('keyops.fast_mirror', 'X', 'PRESS', alt=True)
    registered_toolkit_panel_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('keyops.fast_mirror_options', 'D', 'PRESS')
    registered_toolkit_panel_keymaps.append((km, kmi))

# fix attribute toggle in edit mode/objet mode

def make_duplicate_linked(self, context):
    node_group = get_node_group("Duplicate Linked Modifiers")

    supported_objects = ['MESH', 'CURVE', 'FONT']  # Geometry Nodes modifiers are not supported on surfaces

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
            if mod is None:
                continue
            mod.node_group = node_group
            if not self.instance:
                mod.show_in_editmode = False    

        #add option to only duplate the shoruce object so the modifers is not wrong! Go after socket name? Works, but not when adding a modifier :(
        if BLENDER_VERSION >= (5,2,0):
            obj.modifiers["Duplicate Linked Modifiers"].properties.inputs.Socket_2.value = bpy.data.objects[names[iteration]]
            obj.modifiers["Duplicate Linked Modifiers"].properties.inputs.Socket_3.value = self.instance
        else:
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

def get_description(type: str) -> str:
    if type == "offset_uv":
        return "Offset UV"
    elif type == "Remove_Offset_UV":
        return "Remove the Offset UV modifier"
    elif type == "Triplanar_UV_Mapping":
        return "Triplanar UV Mapping"
    elif type == "Remove_Triplanar_UV_Mapping":
        return "Remove the Triplanar UV Mapping modifier"
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
    instance: bpy.props.BoolProperty(name="Instanced", description="Might provde better viewport performance, but some modifiers and exporters will not work", default=False) # type: ignore
    seprate_by: bpy.props.EnumProperty(name="Separate By",
                                       items=[("MATERIAL", "Material", "Separate by Material", "MATERIAL", 0),
                                              ("LOOSE", "Loose Parts", "Separate by Loose Islands", "LOOSE", 1)],
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
        elif self.type == "Smart_Join_Objects":
            layout.label(text="Quick Join Objects", icon_value=get_icon("union"))
            # layout.prop(self, "set_material_index")   
            layout.prop(self, "join_objects")  
            layout.prop(self, "join_children")   
            layout.prop(self, "apply_instances") 
            layout.prop(self, "rename_uv_layer")
            layout.prop(self, "recalculate_normals")
            layout.prop(self, "triangulate")
        elif self.type == "set_sphere_normal":
            layout.prop(self, "mix_factor")
            layout.prop(self, "scale")
            layout.prop(self, "subdivide")
            layout.prop(self, "set_orgin_to_geometry")
        elif self.type == "set_normal_from_selection":
            layout.prop(self, "mix_factor")
        elif self.type == "subdivide_cylinder":
            layout.prop(self, "triangulate_end")
            layout.prop(self, "angle_to_add")
            layout.prop(self, "use_full_edge_loops")
        elif self.type == "un_subdivide_cylinder":
            layout.prop(self, "angle_to_skip")
            layout.prop(self, "full_edge_loops")
        elif self.type == "Instant_Apply_Modifiers":
            layout.label(text="Apply All Modifiers", icon_value=get_icon("mesh"))
            layout.prop(self, "convert_to_options", text="Convert To")
        elif self.type == "snap_to_floor":
            layout.label(text="Snap to Grid Floor", icon="VIEW_PERSPECTIVE")
            layout.prop(self, "individual")
        elif self.type == "duplicate_linked_modifiers":
            layout.label(text="Duplicate Linked Modifiers", icon="LINKED")
            layout.prop(self, "instance")
        elif self.type == "change_hard_bevel_width":
            layout.prop(self, "scale")
        elif self.type == "seprate_objects_by":
            layout.label(text="Seperate", icon_value=get_icon("slice"))
            layout.scale_x = 1.2
            layout.prop(self, "seprate_by", text="by")
        elif self.type == "clear_custom_normals":
            layout.label(text="Clear Normals", icon="X")

    def execute(self, context):
        if self.type in EDIT_MESH_TYPES and context.mode != 'EDIT_MESH':
            self.report({'WARNING'}, "Only works in mesh Edit Mode")
            return {'CANCELLED'}

        if self.type in OBJECT_MODE_TYPES and context.mode != 'OBJECT':
            self.report({'WARNING'}, "Only works in Object Mode")
            return {'CANCELLED'}

        # These switch to Object Mode themselves
        if self.type in SWITCH_TO_OBJECT_MODE_TYPES or (self.type == "Instant_Apply_Modifiers" and (self.convert_to_options != "Insta_Apply_Modifiers" or context.mode != 'EDIT_MESH')):
            if context.mode != 'OBJECT' and context.active_object is not None:
                bpy.ops.object.mode_set(mode='OBJECT')

        def add_UV_offset_modifier(obj):
            if obj.modifiers.get("Offset UV") is None:
                obj.modifiers.new('Offset UV', 'NODES')
                obj.modifiers['Offset UV'].node_group = bpy.data.node_groups['Offset UV']
                if bpy.context.mode == 'OBJECT':
                    if  BLENDER_VERSION_MAJOR_POINT_MINOR >= 5.2:
                        obj.modifiers["Offset UV"].properties.inputs.Socket_2.value = True
                    else:
                        obj.modifiers["Offset UV"]["Socket_2"] = True

                if bpy.context.mode == 'EDIT_MESH': 
                    mod = obj.modifiers["Offset UV"]
                    if BLENDER_VERSION_MAJOR_POINT_MINOR >= 5.2:
                        mod.properties.inputs.Socket_2.attribute_name = "Offset_UV"
                        mod.properties.inputs.Socket_2.type = "ATTRIBUTE"
                    else:
                        mod["Socket_2_use_attribute"] = True
                        mod["Socket_2_attribute_name"] = "Offset_UV"

        def set_offset_uv_true_false(obj, true_false=True):
            if obj.data.total_vert_sel > 0:
                bpy.context.view_layer.objects.active = obj  # select_atribute works on the active object
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

        
        if self.type == "Triplanar_UV_Mapping":
            active_object = bpy.context.active_object
            get_node_group("Triplanar UV Mapping")
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
                        if BLENDER_VERSION_MAJOR_POINT_MINOR >= 5.2:
                            triplanar_mod = bpy.context.object.modifiers["Triplanar UV Mapping"]
                            triplanar_mod.properties.inputs.Socket_2.attribute_name = "Triplanar_UV_Mapping"
                            triplanar_mod.properties.inputs.Socket_2.type = "ATTRIBUTE"
                        else:
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
                        if BLENDER_VERSION_MAJOR_POINT_MINOR >= 5.2:
                            context.object.modifiers["Triplanar UV Mapping"].properties.inputs.Socket_2.value = True
                        else:
                            context.object.modifiers["Triplanar UV Mapping"]["Socket_2"] = True
                    mod = context.object.modifiers["Triplanar UV Mapping"]

                    if BLENDER_VERSION_MAJOR_POINT_MINOR >= 5.2:
                        mod.properties.inputs.Socket_3.value = active_uv_layer_name
                        mod.properties.inputs.Socket_5.value = self.world_offset
                        mod.properties.inputs.Socket_6.value = self.axis_x
                        mod.properties.inputs.Socket_7.value = self.axis_y
                        mod.properties.inputs.Socket_9.value = self.world_scale
                        mod.properties.inputs.Socket_10.value = self.scale_triplanar
                        mod.properties.inputs.Socket_13.value = self.rotation_triplanar
                    else:
                        mod["Socket_3"] = active_uv_layer_name
                        mod["Socket_5"] = self.world_offset
                        mod["Socket_6"] = self.axis_x
                        mod["Socket_7"] = self.axis_y
                        mod["Socket_9"] = self.world_scale
                        mod["Socket_10"] = self.scale_triplanar
                        mod["Socket_13"] = self.rotation_triplanar
                    bpy.context.object.data.update()
                
                    mod.show_group_selector = False

                    if context.mode == 'EDIT_MESH':
                        bpy.ops.mesh.attribute_set(value_bool=True)

            if self.appy_triplanar == True:
                for obj in bpy.context.selected_objects:
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_apply(modifier="Triplanar UV Mapping")

            bpy.context.view_layer.objects.active = active_object

        elif self.type == "Remove_Triplanar_UV_Mapping":
            active_object = bpy.context.active_object

            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    if bpy.context.object.modifiers.get("Triplanar UV Mapping") is not None:
                        bpy.context.object.modifiers.remove(bpy.context.object.modifiers['Triplanar UV Mapping'])
            bpy.context.view_layer.objects.active = active_object

        elif self.type == "offset_uv":
            active_object = bpy.context.active_object
            get_node_group("Offset UV")

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
                            if BLENDER_VERSION_MAJOR_POINT_MINOR >= 5.2:
                                uv_name_input = mod.properties.inputs.Socket_5
                                current_uv_name = uv_name_input.value
                            else:
                                current_uv_name = mod["Socket_5"]
                            if current_uv_name == "UVMap" and active_uv_name != "UVMap":
                                if BLENDER_VERSION_MAJOR_POINT_MINOR >= 5.2:
                                    uv_name_input.value = active_uv_name
                                else:
                                    mod["Socket_5"] = active_uv_name
                                obj.modifiers["Offset UV"].show_group_selector = False
                                break

                bpy.context.view_layer.objects.active = active_object

        elif self.type == "Remove_Offset_UV":
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

        elif self.type == "change_hard_bevel_width":
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

        elif self.type == "set_sphere_normal":
            current_selectded_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
            if not current_selectded_objects:
                self.report({'WARNING'}, "No mesh objects selected")
                return {'CANCELLED'}

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

        elif self.type == "set_normal_from_selection":
            if context.active_object is None or context.active_object.type != 'MESH':
                self.report({'WARNING'}, "Needs an active mesh object")
                return {'CANCELLED'}
            if bpy.context.mode != 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='EDIT')
            if context.active_object.data.total_vert_sel == 0:
                self.report({'WARNING'}, "Nothing selected")
                return {'CANCELLED'}
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
            
        elif self.type == "seprate_objects_by":
            if self.seprate_by == "MATERIAL":
                bpy.ops.mesh.separate(type='MATERIAL')
            elif self.seprate_by == "LOOSE":
                bpy.ops.mesh.separate(type='LOOSE')

        elif self.type == "unique_collection_duplicat":
            if bpy.data.collections.get("high"):
                self.default_name = "low"
            else:
                self.default_name = "high"
        
            bpy.ops.object.duplicate()
            move_selected_to_new_collection(context, self.default_name)

            objects_to_duplicate = [obj for obj in context.selected_objects if obj.data and obj.data.users > 1]

            for obj in objects_to_duplicate:

                obj.data = obj.data.copy()
                #should auto get all booleons, so they do not need to be selected
                booleans = [mod for mod in obj.modifiers if mod.type == 'BOOLEAN' and mod.object and mod.object.data.users > 1]

                for mod in booleans:
                    mod.object.data = mod.object.data.copy()

        elif self.type == "Smart_Join_Objects":
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
        elif self.type == "Instant_Apply_Modifiers":
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

                        if obj.mode != 'EDIT':
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
                bpy.ops.object.convert(target='GREASEPENCIL' if BLENDER_VERSION >= (4, 3, 0) else 'GPENCIL')
            return {'FINISHED'}

        elif self.type == "toggle_high_low":
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
    
        elif self.type == "high":
            if bpy.context.scene.collection.children.get("high") is None:
                if len(bpy.context.scene.collection.children) == 1 and not bpy.context.scene.collection.children[0].name == "low":
                    bpy.context.scene.collection.children[0].name = "high"
                else:
                    move_selected_to_new_collection(context, "high")
            else:
                move_selected_to_collection(context, bpy.context.scene.collection.children["high"])

        elif self.type == "low":
            if bpy.context.scene.collection.children.get("low") is None:
                if len(bpy.context.scene.collection.children) == 1 and not bpy.context.scene.collection.children[0].name == "high":
                    bpy.context.scene.collection.children[0].name = "low"
                else:
                    move_selected_to_new_collection(context, "low")
            else:
                move_selected_to_collection(context, bpy.context.scene.collection.children["low"])

        elif self.type == "un_subdivide_cylinder":
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')

            for obj in [o for o in context.objects_in_mode if o.type == 'MESH']:
                if obj.data.total_vert_sel > 0:
                    context.view_layer.objects.active = obj
                    if obj.data.attributes.get('Edge_Un_Subdivied_Cylinder') is None:
                        obj.data.attributes.new(name='Edge_Un_Subdivied_Cylinder', type='BOOLEAN', domain='EDGE')
                    obj.data.attributes.active = obj.data.attributes.get('Edge_Un_Subdivied_Cylinder')
                    obj.data.update()
                    bpy.ops.mesh.attribute_set(value_bool=True)

            for obj in [o for o in context.objects_in_mode if o.type == 'MESH']:
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

                    select_ring()
                    bpy.ops.mesh.select_nth('EXEC_DEFAULT', True, skip=1, nth=1, offset=0)

                    #compare if current_selection does not match any in the new_selection, if then increase the offset with +1
                    new_selection = [e for e in bm.edges if e.select]
                    if any(e in current_selection for e in new_selection):
                        select_ring()
                        bpy.ops.mesh.select_nth('EXEC_DEFAULT', True, skip=1, nth=1, offset=1)

                    select_loop()

                    if self.angle_to_skip <= 1.570:
                        bpy.ops.mesh.select_all(action='INVERT')
                        bpy.ops.mesh.edges_select_sharp(sharpness=self.angle_to_skip)
                        bpy.ops.mesh.select_all(action='INVERT')
                        if self.full_edge_loops == True:
                            select_loop()

                    bpy.ops.mesh.dissolve_mode('EXEC_DEFAULT', True, use_verts=True)
                    bpy.ops.mesh.select_by_attribute()

                    bmesh.update_edit_mesh(mesh)
                    bm.free()

            for obj in [o for o in context.objects_in_mode if o.type == 'MESH']:
                if obj.data.attributes.get('Edge_Un_Subdivied_Cylinder') is not None:
                    context.view_layer.objects.active = obj
                    bpy.ops.mesh.select_by_attribute()
                    obj.data.attributes.remove(obj.data.attributes.get('Edge_Un_Subdivied_Cylinder'))
                    
        elif self.type == "subdivide_cylinder":
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

            select_ring()
            select_loop()

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
                select_loop()


            bpy.ops.mesh.connect2()
            bpy.ops.mesh.set_mesh_edge_flow(tension=180, iterations=3)

            if self.triangulate_end == True:
                bm = bmesh.from_edit_mesh(mesh_obj.data)

                new_selected_edges = [e for e in bm.edges if e.select]
                
                select_ring()
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

        elif self.type == "change_cylinder_segments_modifier":
            bpy.ops.mesh.select_all(action='INVERT')
            bpy.ops.mesh.delete(type='EDGE')

            obj = bpy.context.active_object

            mod = obj.modifiers.new(type='SCREW', name='Screw')
            mod.use_normal_calculate = True
            mod.use_merge_vertices = True
            mod.steps = 32
            bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)

        elif self.type == "clear_custom_normals":
            selection = bpy.context.selected_objects
            old_version = BLENDER_VERSION < (4, 5)

            if old_version:
                for obj in selection:
                    if obj.type == 'MESH':
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.mesh.customdata_custom_splitnormals_clear()
            else:
                for obj in selection:
                    if obj.type == 'MESH':
                        for atri in obj.data.attributes:
                            if atri.name == "custom_normal":
                                obj.data.attributes.remove(atri)

        elif self.type == "cleanup":
            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)

        elif self.type == "set_vertex_color":
            space = context.space_data
            if space is not None and space.type == 'VIEW_3D' and space.shading.color_type != 'VERTEX':
                space.shading.color_type = 'VERTEX'

            selection = [o for o in context.objects_in_mode if o.type == 'MESH']

            for obj in selection:
                if obj.data.total_vert_sel > 0: 
                    if obj.data.attributes.active_color is None:
                        context.view_layer.objects.active = obj
                        obj.data.color_attributes.new(name="Vertex_Color", type="BYTE_COLOR", domain="POINT")
                        
                    active_attribute = obj.data.attributes.active_color.name

                    set_act_index = obj.data.attributes.find(active_attribute)
                    obj.data.attributes.active_index = set_act_index

            if not any(obj.data.total_vert_sel > 0 for obj in selection):
                self.report({'WARNING'}, "Nothing selected")
                return {'CANCELLED'}

            if self.ovveride_color != True:
                color = bpy.context.scene.keyops.vertex_color
            else:
                color = self.ovveride_color_vec
            bpy.ops.mesh.attribute_set(value_color=(color[0], color[1], color[2], color[3]))
       
        elif self.type == "duplicate_linked_modifiers":
            make_duplicate_linked(self, context)

        elif self.type == "duplicate_linked_modifiers_and_move":
            make_duplicate_linked(self, context)
            bpy.ops.transform.translate('INVOKE_DEFAULT')

        return {'FINISHED'}

def register_toolkit_panel():
    from .snap_to_floor import register_snap_to_floor
    from .parent_used_objects import register_parent_used_objects
    from .resample_edges import register_resample_edges
    from .mesh_cleanup import register_mesh_cleanup
    from .extract_geometry import register_extract_geometry
    register_extract_geometry()
    from .edge_trim import register_edge_trim
    from .subobject_modes import register_sub_object_modes
    register_sub_object_modes()
    register_edge_trim()
    register_resample_edges()
    register_mesh_cleanup()
    register_set_flow()
    register_fast_mirror()
    register_snap_to_floor()
    register_parent_used_objects()
    bpy.utils.register_class(ToolkitPanel)
    # bpy.utils.register_class(NewToolkitPanel)
    # bpy.utils.register_class(ObjectModePanel)
    # bpy.utils.register_class(ModifierPanel)
    # bpy.utils.register_class(EditModePanel)
    #bpy.utils.register_class(SmartExtrude)
    register_extrude_edge_along_normals()
    register_offset_extrude_edge()
    bpy.utils.register_class(EDIT_PT_Settings)
    bpy.utils.register_class(AddModifier)
    bpy.utils.register_class(SmartApplyScale)
    bpy.utils.register_class(AddBooleanModifier)
    bpy.utils.register_class(BooleanScroll)
    register_toolkit_panel_keymaps()
    # bpy.types.Scene.RGB_Enum = bpy.props.EnumProperty(items=[('R', 'Red', 'Red', 'EVENT_R', 0), ('G', 'Green', 'Green', 'EVENT_G', 1), ('B', 'Blue', 'Blue', 'EVENT_B', 2)], name="RGB", default='R', update=click_rgb_enum)
    bpy.types.WindowManager.live_booleans = bpy.props.BoolProperty(name="Realtime Booleans", default=True, description="Wether to calculate Booleons in real time or not, if turned off, it will only calculate once you stoped moving the object, making interaction way smoother", update=toggle_realtime_booleans)
    bpy.context.window_manager.live_booleans = True

def unregister_toolkit_panel():
    from .snap_to_floor import unregister_snap_to_floor
    from .parent_used_objects import unregister_parent_used_objects
    from .resample_edges import unregister_resample_edges
    from .mesh_cleanup import unregister_mesh_cleanup
    from .extract_geometry import unregister_extract_geometry
    unregister_extract_geometry()
    from .edge_trim import unregister_edge_trim
    from .subobject_modes import unregister_sub_object_modes
    unregister_sub_object_modes()
    unregister_edge_trim()
    unregister_resample_edges()
    unregister_mesh_cleanup()
    clear_registered_keymaps(registered_toolkit_panel_keymaps)
    unregister_fast_mirror()
    unregister_set_flow()
    unregister_snap_to_floor()
    unregister_parent_used_objects()
    bpy.utils.unregister_class(ToolkitPanel)
    # bpy.utils.unregister_class(ObjectModePanel)
    # bpy.utils.unregister_class(ModifierPanel)
    # bpy.utils.unregister_class(EditModePanel)
    #bpy.utils.unregister_class(SmartExtrude)
    unregister_extrude_edge_along_normals()
    unregister_offset_extrude_edge()
    bpy.utils.unregister_class(EDIT_PT_Settings)
    bpy.utils.unregister_class(AddModifier)
    bpy.utils.unregister_class(SmartApplyScale)
    bpy.utils.unregister_class(AddBooleanModifier)
    bpy.utils.unregister_class(BooleanScroll)
    # bpy.utils.unregister_class(NewToolkitPanel)
    # del bpy.types.Scene.RGB_Enum
    del bpy.types.WindowManager.live_booleans
    if ENTERING_TRANSFORM_OT_None_Live_Booleans.is_registered:
        bpy.utils.unregister_class(ENTERING_TRANSFORM_OT_None_Live_Booleans)

def toggle_realtime_booleans(self, context):
    # Update callbacks fire on every assignment, not only when the value changes.
    is_registered = ENTERING_TRANSFORM_OT_None_Live_Booleans.is_registered
    if not bpy.context.window_manager.live_booleans:
        if not is_registered:
            bpy.utils.register_class(ENTERING_TRANSFORM_OT_None_Live_Booleans)
    elif is_registered:
        bpy.utils.unregister_class(ENTERING_TRANSFORM_OT_None_Live_Booleans)
        
def update_vertex_color(self, context):
    bpy.ops.keyops.toolkit_panel(type="set_vertex_color")  
    #bpy.ops.mesh.attribute_set(value_color=(bpy.context.scene.keyops.vertex_color[0], bpy.context.scene.keyops.vertex_color[1], bpy.context.scene.keyops.vertex_color[2], bpy.context.scene.keyops.vertex_color[3]))

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
        #import time 
        #perf_time = time.time()
        node_group = get_node_group("Extrude Edge By Normal")

        node_group.is_mode_edit = True
        node_group.nodes["Extrude Mesh"].inputs["Offset Scale"].default_value = self.offset
        bpy.ops.geometry.execute_node_group(name=node_group.name)
        node_group.is_mode_edit = False
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

        box = layout.box()
        col = box.column(align=True)
        if draw_header:
            col.label(text="Modifiers", icon_value=get_icon("modifier"))
        # Create: the Fast tools first, then lattices
        col = box.column(align=True)
        col.label(text="Create")
        grid = col.column(align=True)
        row = grid.row(align=True)
        row.operator("keyops.fast_bevel", text="Bevel", icon="MOD_BEVEL")
        row.operator("keyops.fast_array", text="Array", icon="MOD_ARRAY")
        row.operator("keyops.fast_solidify", text="Solidify", icon="MOD_SOLIDIFY")
        row = grid.row(align=True)
        row.operator("keyops.add_modifier", text="Lattice", icon="MOD_LATTICE").type = "LATTICE"
        for n in (3, 4):
            op = row.operator("keyops.add_modifier", text=f"FFD {n}x")
            op.subdivisions = n
            op.type = "LATTICE"

        # UV
        col = box.column(align=True)
        col.label(text="UV")
        column = col.column(align=True)
        row = column.split(factor=0.57, align=True)
        row.operator("keyops.toolkit_panel", text="Offset UV", icon="AREA_JOIN").type = "offset_uv"
        row.operator("keyops.toolkit_panel", text="Remove").type = "Remove_Offset_UV"
        row = column.split(factor=0.57, align=True)
        row.operator("keyops.toolkit_panel", text="Triplanar UV", icon="AXIS_SIDE").type = "Triplanar_UV_Mapping"
        row.operator("keyops.toolkit_panel", text="Remove").type = "Remove_Triplanar_UV_Mapping"
        if prefs.enable_uv_tools:
            column.operator("keyops.sharp_from_uv_islands", text="Sharp from UV Islands", icon="MOD_EDGESPLIT")

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


def draw_edge_flow(row):
    row.operator("mesh.set_mesh_edge_flow", text="Set Flow")


# Edit Toolkit layout helpers: every section is a label plus an aligned column of buttons,
# two per row. A button wrapped in _wide() (or an odd one at the end) spans the whole row.
def _op(idname, text, **props):
    def draw(layout):
        op = layout.operator(idname, text=text)
        for name, value in props.items():
            setattr(op, name, value)
    return draw


def _menu_op(menu, text):
    def draw(layout):
        layout.operator("wm.call_menu", text=text).name = menu
    return draw


def _wide(draw):
    draw.wide = True
    return draw


def _section(box, label, items, first=False):
    items = [item for item in items if item is not None]
    if not items:
        return
    if label:
        if not first:
            box.separator(factor=0.5)
        box.label(text=label)
    col = box.column(align=True)
    row = None
    for item in items:
        if getattr(item, "wide", False):
            item(col.row(align=True))
            row = None
            continue
        if row is None:
            row = col.row(align=True)
            item(row)
        else:
            item(row)
            row = None


# click vert, edge andface again should go to object mode!
def draw_edit_mode_panel(self, context, draw_header=False):
    sel_mode = bpy.context.tool_settings.mesh_select_mode[:]
    prefs = get_keyops_prefs()

    # Off = only Key Ops operators, on = Key Ops + Blender built-in operators (3ds Max-style)
    show_blender_ops = prefs.edit_toolkit_show_blender_ops

    layout = self.layout
    box = layout.box()
    row = box.row(align=True)
    if draw_header:
        row.label(text="Edit Toolkit", icon_value=get_icon("editmode"))
    sub = row.row(align=True)
    sub.alignment = 'RIGHT'
    sub.popover(panel="EDIT_PT_Settings", text="", icon='PREFERENCES')

    if show_blender_ops:
        row = box.row(align=True)
        row.scale_x = 2.15
        row.scale_y = 1.5
        row.alignment = 'CENTER'
        # Vertex, Edge, Face plus the Border and Element modes, as one row of modes
        draw_mode_row(row, context)

    vert_mode, edge_mode, face_mode = sel_mode
    fast_merge = prefs.enable_fast_merge

    # Selection
    if show_blender_ops:
        loop_ring = ([_op("mesh.select_edge_loop_multi", "Loop"), _op("mesh.select_edge_ring_multi", "Ring")]
                     if BLENDER_VERSION >= (5, 1, 0) else
                     [_op("mesh.loop_multi_select", "Loop", ring=False), _op("mesh.loop_multi_select", "Ring", ring=True)])
        _section(box, "Selection", [
            _op("mesh.select_more", "More"), _op("mesh.select_less", "Less"),
            *loop_ring,
            _op("mesh.region_to_loop", "Boundary"), _op("mesh.loop_to_region", "Inner Region"),
            _op("mesh.faces_select_linked_flat", "By Angle") if face_mode else _op("mesh.edges_select_sharp", "Edge Angle"),
            _op("keyops.select_similar", "Similar"),
            _op("mesh.select_nth", "Checker Deselect"),
            _op("mesh.select_non_manifold", "Non Manifold") if (vert_mode or edge_mode) else None,
            _op("mesh.select_face_by_sides", "Ngons", type='GREATER'),
            _op("keyops.select_thin_triangles", "Thin Triangles"),
        ], first=True)
    else:
        _section(box, "Selection", [
            _op("keyops.select_similar", "Similar"),
            _op("keyops.select_thin_triangles", "Thin Triangles"),
        ], first=True)

    # Edit vertices / edges / polygons
    if show_blender_ops:
        title = ("Edit Mesh" if sum(sel_mode) > 1 else
                 "Edit Vertices" if vert_mode else "Edit Edges" if edge_mode else "Edit Polygons")
        items = {}
        if vert_mode:
            items["remove"] = _op("mesh.delete", "Remove", type='VERT')
        if edge_mode:
            items.setdefault("remove", _op("mesh.dissolve_mode", "Remove"))
            items["split"] = _op("mesh.rip", "Split")
        if face_mode:
            items.setdefault("remove", _op("mesh.delete", "Remove", type='FACE'))
        items["extrude"] = _menu_op("VIEW3D_MT_edit_mesh_extrude", "Extrude")
        items["weld"] = _op("mesh.remove_doubles", "Weld")
        items["bevel"] = (_op("mesh.bevel", "Chamfer", affect='VERTICES') if vert_mode and not (edge_mode or face_mode)
                          else _op("mesh.bevel", "Bevel", affect='EDGES'))
        if fast_merge:
            items["connect"] = _op("mesh.connect2", "Connect")
        if face_mode:
            items["inset"] = _op("mesh.inset", "Inset")
            items["flip"] = _op("mesh.flip_normals", "Flip")
        if edge_mode or face_mode:
            items["bridge"] = _op("mesh.bridge_edge_loops", "Bridge")
        items["fill"] = _op("mesh.edge_face_add", "Fill")
        items["flow"] = _op("mesh.set_mesh_edge_flow", "Set Flow")
        items["dissolve"] = _op("mesh.dissolve_limited", "Limited Dissolve")
        if vert_mode or edge_mode:
            items["resample"] = _op("keyops.resample_edges", "Resample Edges")
            items["trim"] = _op("keyops.edge_trim", "Make Trim")
        _section(box, title, list(items.values()))
    else:
        _section(box, "Edit Mesh", [
            _op("mesh.connect2", "Connect") if fast_merge else None,
            _op("mesh.set_mesh_edge_flow", "Set Flow"),
            _op("keyops.resample_edges", "Resample Edges"),
            _op("keyops.edge_trim", "Make Trim"),
        ])

    # UV
    _section(box, "UV", [
        _wide(lambda layout: layout.menu("VIEW3D_MT_uv_map", text="UV Unwrap")),
        _op("mesh.mark_seam", "Mark Seam", clear=False),
        _op("mesh.mark_seam", "Clear Seam", clear=True),
        _wide(_op("keyops.seam_by_angle", "Seam by Angle")) if prefs.enable_uv_tools else None,
    ])

    # Vertex color
    _section(box, "Vertex Color", [
        _op("keyops.toolkit_panel", "Set Color", type="set_vertex_color"),
        lambda layout: layout.prop(context.scene.keyops, "vertex_color", text=""),
    ])

    # Edit geometry
    if show_blender_ops:
        box.separator(factor=0.5)
        row = box.row(align=True)
        row.label(text="Edit Geometry")
        sub = row.row(align=True)
        sub.alignment = 'RIGHT'
        sub.prop(context.scene.tool_settings, "use_transform_correct_face_attributes", text="Preserve UVs")
        sub.popover_group(context=".mesh_edit", space_type='VIEW_3D', region_type='UI', category="Tool")

        loop_tools = []
        if BLENDER_VERSION >= (5, 3, 0):  # these LoopTools-style tools are built into Blender from 5.3
            if operator_exists("mesh.flatten"):
                loop_tools.append(_op("mesh.flatten", "Make Planar"))
            if operator_exists("mesh.circularize"):
                loop_tools.append(_op("mesh.circularize", "Circle"))
            if operator_exists("mesh.relax_edge_loops"):
                loop_tools.append(_op("mesh.relax_edge_loops", "Relax"))
        if len(loop_tools) % 2:
            loop_tools[-1] = _wide(loop_tools[-1])

        _section(box, None, [
            _op("mesh.merge", "Merge Center", type='CENTER'), _op("mesh.edge_collapse", "Collapse"),
            _op("mesh.separate", "Separate"), _op("mesh.rip_move", "Rip"),
            _op("mesh.bisect", "Slice Plane"), _op("mesh.knife_tool", "Cut"),
            _op("mesh.subdivide", "Subdivide"), _op("mesh.unsubdivide", "Un-Subdivide"),
            *loop_tools,
            _op("keyops.mesh_cleanup", "Clean Up"), _op("keyops.extract_geometry", "Extract"),
            _op("mesh.hide", "Hide Selected"), _op("mesh.reveal", "Unhide All"),
            _op("mesh.hide", "Hide Unselected", unselected=True),
        ])
    else:
        _section(box, "Edit Geometry", [
            _op("keyops.mesh_cleanup", "Clean Up"), _op("keyops.extract_geometry", "Extract"),
        ])

    # Cylinder
    _section(box, "Cylinder", [
        _wide(_op("keyops.toolkit_panel", "Cylinder from Edge", type="change_cylinder_segments_modifier")),
        _op("keyops.toolkit_panel", "Un-Subdivide", type="un_subdivide_cylinder"),
        _op("keyops.toolkit_panel", "Subdivide", type="subdivide_cylinder"),
    ])

    if prefs.experimental:
        _section(box, None, [
            _op("keyops.toolkit_panel", "Change Hard Bevel Width", type="change_hard_bevel_width"),
        ])


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
        row.operator("keyops.snap_to_floor", text="Snap to Grid Floor", icon = "VIEW_PERSPECTIVE")
        row = col.row(align=True)
        row.scale_y = 1.15
        row.operator("object.smart_apply_scale", text="Smart Apply Scale", icon = "FREEZE")
        row = col.row(align=True)
        row.scale_y = 1.15
        row.operator("keyops.mesh_cleanup", text="Clean Up", icon="BRUSH_DATA")
        row.operator("keyops.extract_geometry", text="Extract", icon="DUPLICATE")
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
    bl_label = "Edit Toolkit Settings"
    bl_description = "Choose which operators the Edit Toolkit shows"
    bl_idname = "EDIT_PT_Settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}
    bl_ui_units_x = 11  # just wide enough that the labels below don't clip

    def draw(self, context):
        prefs = get_keyops_prefs()
        layout = self.layout
        layout.label(text="Edit Toolkit Settings")
        layout.prop(prefs, "edit_toolkit_show_blender_ops")
        col = layout.column(align=True)
        col.scale_y = 0.8
        col.enabled = False
        if prefs.edit_toolkit_show_blender_ops:
            col.label(text="Key Ops + Blender operators", icon='INFO')
        else:
            col.label(text="Key Ops operators only", icon='INFO')
        