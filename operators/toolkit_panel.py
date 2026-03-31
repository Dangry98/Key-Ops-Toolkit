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
from ..resources.geometry_nodes_scripits import offset_uv_node_group, triplanar_uv_mapping_node_group, duplicate_linked_modifiers_node_group, get_all_bouding_box_node_group

BLENDER_VERSION = bpy.app.version

# fix attribute toggle in edit mode/objet mode

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
    bl_label = ""
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
    addon_id: bpy.props.StringProperty(default="", options={'SKIP_SAVE', 'HIDDEN'}) # type: ignore
    def invoke(self, context, event):
        global ev 
        ev = []
        if event.ctrl:
            ev.append("Ctrl")
        if event.shift:
            ev.append("Shift")
        if event.alt:
            ev.append("Alt")

        if self.type == "operation_missing":
            return context.window_manager.invoke_props_dialog(self, confirm_text="Install", width=275)
        else:
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

        elif self.type == "operation_missing":
            layout = self.layout
            row = layout.row()
            row.label(text=f"{self.addon_id} is missing!", icon="INFO")
            row = layout.row()
            row.label(text=f"Please install if you want to use this operation.")

    def execute(self, context):
        prefs = get_keyops_prefs()

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
            if bpy.data.node_groups.get("Offset UV") is None:
                offset_uv_node_group()

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

        elif self.type == "set_normal_from_selection":
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
            
        elif self.type == "set_bevel_segment_amount":
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

        elif self.type == "operation_missing":
            bpy.ops.extensions.package_install(repo_index=0, pkg_id=self.addon_id)

        elif self.type == "bevel_segment_amount_by_%":
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
                                                            
        elif self.type == "hide_bevels_by_offset":
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

        elif self.type == "seprate_objects_by":
            if bpy.context.mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='OBJECT')
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
            bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name=self.default_name)

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
                    bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name="high")
            else:
                get_index_of_high = bpy.context.scene.collection.children.find("high") + 1
                bpy.ops.object.move_to_collection(collection_index=get_index_of_high)

        elif self.type == "low":
            if bpy.context.scene.collection.children.get("low") is None:
                if len(bpy.context.scene.collection.children) == 1 and not bpy.context.scene.collection.children[0].name == "high":
                    bpy.context.scene.collection.children[0].name = "low"
                else:
                    bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name="low")
            else:
                get_index_of_low = bpy.context.scene.collection.children.find("low") + 1
                bpy.ops.object.move_to_collection(collection_index=get_index_of_low)

        elif self.type == "un_subdivide_cylinder":
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
                    
        elif self.type == "subdivide_cylinder":
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
                bpy.ops.keyops.toolkit_panel("INVOKE_DEFAULT", type="operation_missing", addon_id="EdgeFlow")
                self.report({'WARNING'}, "EdgeFlow addon not installed, please install it to use this operator")

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
       
        elif self.type == "duplicate_linked_modifiers":
            make_duplicate_linked(self, context)
            return {'FINISHED'}
        elif self.type == "duplicate_linked_modifiers_and_move":
            make_duplicate_linked(self, context)
            bpy.ops.transform.translate('INVOKE_DEFAULT')
            
            return {'FINISHED'}

        elif self.type == "snap_to_floor":
            # import time
            # exec_time = time.time()
            global ev
            if "Alt" in ev:
                self.individual = True

            ev = []

            if not bpy.context.selected_objects:
                self.report({'WARNING'}, "No Objects Selected")
                return {'CANCELLED'}

            #bpy.context.evaluated_depsgraph_get()
            depsgraph = bpy.context.evaluated_depsgraph_get()

            if not self.individual:
                all_bounds = []
                new_selected_objects = [o for o in context.selected_objects if o.type in ['MESH', 'CURVE', 'TEXT', 'SURFACE']]

                active = context.active_object
                empty = [o for o in context.selected_objects if o.type in ['EMPTY', 'LATTICE']]
                from ..utils.utilities import get_AABB_bounding_box_coords
                all_bounds = get_AABB_bounding_box_coords(new_selected_objects)


                for obj in empty:
                    all_bounds.append(obj.location)
                
                if not all_bounds: return {"CANCELLED"}

                z_min = min(v[2] for v in all_bounds)
                
                for obj in context.selected_objects:
                    obj.matrix_world.translation -= Vector((0, 0, z_min))

                # bpy.ops.transform.translate(value=(0, 0, -z_min), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', constraint_axis=(False, False, True), mirror=False, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False)

            else:
                selection = bpy.context.selected_objects

                def move_individual_to_floor(selection):
                    for obj in selection:
                        if obj.type in ['MESH', 'CURVE', 'TEXT', 'SURFACE', 'FONT', 'META']:
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
        col = box.column(align=False) 

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
            row.scale_x = 0.4
            row.operator("keyops.toolkit_panel", text="Hide by Offset", icon= "MOD_BEVEL").type = "hide_bevels_by_offset"
            sub = row.row()
            sub.prop(context.scene, "compensate_for_scale", text="")
            subrow = sub.row(align=False)
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

def draw_edge_flow(row):
    if get_is_addon_enabled("EdgeFlow"):
        row.operator("mesh.set_edge_flow", text="Set Flow")
    else:
        op = row.operator("keyops.toolkit_panel", text="Set Flow")
        op.type = "operation_missing"
        op.addon_id = "EdgeFlow"

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

        if BLENDER_VERSION < (4, 5, 0):
            row.operator("mesh.loop_multi_select", text="Loop").ring=False
            row.operator("mesh.loop_multi_select", text="Ring").ring=True
        else:
            row.operator("mesh.select_edge_loop_multi", text="Loop")
            row.operator("mesh.select_edge_ring_multi", text="Ring")

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
            draw_edge_flow(row)
           
              
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
            draw_edge_flow(row)
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
            draw_edge_flow(row)
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
        if get_is_addon_enabled("looptools"):
            row.operator("mesh.looptools_flatten", text="Make Planar")
            row.operator("mesh.looptools_circle", text="Circle")
            row = box.row(align=False)
            row.alignment = 'CENTER'
            row.operator("mesh.looptools_relax", text="Relax")
        else:
            def looptools_missing_op(row, text):
                op = row.operator("keyops.toolkit_panel", text=text)
                op.type = "operation_missing"
                op.addon_id = "looptools"
                
            looptools_missing_op(row, "Make Planar")
            looptools_missing_op(row, "Circle")
            row = box.row(align=False)
            row.alignment = 'CENTER'
            looptools_missing_op(row, "Relax")

        row = box.row(align=False)
        row.operator("mesh.hide", text="Hide Selected")
        row.operator("mesh.reveal", text="Unhide All")
        row = box.row(align=False)
        row.alignment = 'CENTER'
        row.operator("mesh.hide", text="Hide Unselected").unselected = True

        # Cylinder
        row = box.row(align=False)
        row.label(text="Cylinder", icon="MESH_CYLINDER")
        row.operator("keyops.toolkit_panel", text="from Edge", icon="MOD_SCREW").type = "change_cylinder_segments_modifier"
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
        