from typing import Set
import bpy.types
from bpy.types import Context, Operator
from ..utils.pref_utils import get_is_addon_enabled
from ..utils.mesh_utils import modifier_toggle_visability_based
import time

modifier_list = None

def sync_bpy_object_props(source, dest):
    for p in source.bl_rna.properties:
        if not p.is_readonly:
            setattr(dest, p.identifier, getattr(source, p.identifier))

def get_editable_bpy_object_props(bpy_object, props_to_ignore={}):
    props = [getattr(bpy_object, p.identifier) for p in bpy_object.bl_rna.properties
            if not p.is_readonly and p.identifier not in props_to_ignore]
    return [p[:] if type(p).__name__ == "bpy_prop_array" else p for p in props]


class ModiKey(Operator):
    bl_idname = "keyops.modi_key"
    bl_label = "KeyOps: Modi Key"
    bl_description = ""
    bl_options = {'INTERNAL', 'UNDO'}

    type: bpy.props.StringProperty(name="type") #type:ignore

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        global modifier_list

        if bpy.context.space_data.context == 'MODIFIER':
            if modifier_list is None:
                modifier_list = get_is_addon_enabled('Modifier_List_Fork')  
            
            obj = bpy.context.active_object
            has_Linked_modifiers = False

            if modifier_list: 
                obj = bpy.context.active_object
                if obj.modifiers:
                    mod = obj.modifiers[0]
                    if len(obj.modifiers) == 1:
                        if mod.name == "Duplicate Linked Modifiers":
                            for item in mod.node_group.interface.items_tree:
                                if item.in_out == "INPUT" and item.identifier == 'Socket_2': 
                                    if mod[item.identifier]:
                                        object_name = mod[item.identifier].name
                                        obj = bpy.data.objects[object_name]
                                        has_Linked_modifiers = True
           
            active_modifier = obj.modifiers.active

            if active_modifier:
                active_index = obj.modifiers.find(active_modifier.name)

                if self.type == 'move_up' and active_index > 0:
                        obj.modifiers.move(active_index, active_index - 1)
                elif self.type == 'move_top':
                        obj.modifiers.move(active_index, 0)
                elif self.type == 'move_down' and active_index < len(obj.modifiers) - 1:
                        obj.modifiers.move(active_index, active_index + 1)
                elif self.type == 'move_bottom':
                        obj.modifiers.move(active_index, len(obj.modifiers) - 1)
                elif self.type == 'select_up' and active_index > 0:
                    obj.modifiers.active = obj.modifiers[active_index - 1]
                elif self.type == 'select_down' and active_index < len(obj.modifiers) - 1:
                    obj.modifiers.active = obj.modifiers[active_index + 1]
                elif self.type == 'select_top':
                    obj.modifiers.active = obj.modifiers[0]
                elif self.type == 'select_bottom':
                    obj.modifiers.active = obj.modifiers[-1]

                elif self.type == 'delete':
                    if modifier_list and not has_Linked_modifiers:
                        bpy.ops.object.ml_modifier_remove("INVOKE_DEFAULT")
                    else:
                        if bpy.context.object.mode == "OBJECT":
                            obj.modifiers.remove(active_modifier)
                        else:
                            current_mode = bpy.context.object.mode
                            bpy.ops.object.mode_set(mode='OBJECT')
                            bpy.ops.ed.undo_push()
                                
                            obj.modifiers.remove(active_modifier)

                            bpy.ops.object.mode_set(mode=current_mode)

                elif self.type == 'delete_named_modi_on_all_selected':
                    delete_modi_name = active_modifier.name

                    for obj in bpy.context.selected_objects:
                        if obj.type == 'MESH':
                            for mod in obj.modifiers:
                                if mod.name == delete_modi_name:
                                    obj.modifiers.remove(mod)

                elif self.type == "Copy_Modifier_to_Selected":
                    if len(bpy.context.selected_objects) > 1:                       
                        bpy.ops.object.modifier_copy_to_selected(modifier = active_modifier.name)
                
                    return {'FINISHED'}  

                elif self.type == 'Apply':
                    name = active_modifier.name
                    apply_time = time.time()    

                    visibility_modifier_dict_list = {}

                    def modifier_toggle_visability_based2(): 
                        active_object_name = bpy.context.view_layer.objects.active.name
 
                        if active_object_name not in visibility_modifier_dict_list:
                            visibility_modifier_dict_list[active_object_name] = []

                        visibility_modifier_list = visibility_modifier_dict_list[active_object_name]

                        if len(visibility_modifier_list) <= 0:
                            ml_act_ob = bpy.context.view_layer.objects.active
                            for mod in ml_act_ob.modifiers:
                                if mod.show_viewport:
                                    visibility_modifier_list.append(mod)
                                    mod.show_viewport = False
                        else:
                            ml_act_ob = bpy.context.view_layer.objects.active
                            hidden_modifiers = []
                            for mod in ml_act_ob.modifiers:
                                if mod in visibility_modifier_list:
                                    mod.show_viewport = True
                                    hidden_modifiers.append(mod)
                            visibility_modifier_list = [mod for mod in visibility_modifier_list if mod not in hidden_modifiers]
                            visibility_modifier_dict_list[active_object_name] = visibility_modifier_list

                    if modifier_list:     
                        if bpy.context.mode == 'OBJECT':   
                            bpy.ops.object.ml_modifier_apply("INVOKE_DEFAULT")
                                                        
                            # does not work with modifers that are not visible in edit mode, make exception for them?
                            #hide all modifiers except the active one
                            #name = active_modifier.name
                            # active_modifier = bpy.context.view_layer.objects.active.modifiers.active
                            # #get a list with all modifers that are visiable or not execpt the active one
                            # vis_list = [mod.show_viewport for mod in bpy.context.view_layer.objects.active.modifiers if mod != active_modifier]
                    
                            # if not active_modifier.show_in_editmode:
                            #     active_modifier.show_in_editmode = True
                            # for mod in bpy.context.view_layer.objects.active.modifiers:
                            #     if mod != active_modifier:
                            #         mod.show_viewport = False
                            # #update object data
                            # bpy.context.view_layer.objects.active.data.update()
                            # bpy.ops.keyops.utilities_panel_op(type="Instant_Apply_Modifiers", remove_modifiers=False)
                            # #remove the active modifier from the object
                            # obj.modifiers.remove(active_modifier)

                            # #restore the visibility of the other modifiers
                            # for i, mod in enumerate(bpy.context.view_layer.objects.active.modifiers):
                            #     mod.show_viewport = vis_list[i]
                                 
                        else:
                            if bpy.context.mode == 'EDIT_MESH':
                                modifier_toggle_visability_based2()        
                            bpy.ops.object.ml_modifier_apply("INVOKE_DEFAULT")
                            if bpy.context.mode == 'EDIT_MESH':
                                modifier_toggle_visability_based2()   
                    else:
                        if bpy.context.mode == 'OBJECT':
                            instances = [o for o in bpy.data.objects if o.data == obj.data]

                            if instances and len(instances) > 1:
                                bpy.ops.object.modifier_apply("INVOKE_DEFAULT", modifier=active_modifier.name)

                                self.report({'WARNING'}, f"Object has many users, can't apply modifier, consider making it single user")
                                return {'FINISHED'}
                            else:
                                bpy.ops.object.modifier_apply(modifier=active_modifier.name)
                          
                        else:
                            modifier_toggle_visability_based2()        
                            bpy.ops.object.mode_set(mode='OBJECT')
                            bpy.ops.ed.undo_push()
                            bpy.ops.object.modifier_apply(modifier=active_modifier.name)
                            bpy.ops.object.mode_set(mode='EDIT')
                            modifier_toggle_visability_based2()        

                    apply_time = time.time() - apply_time
                    if apply_time > 1:
                        self.report({'INFO'}, f"Applied {name} in {apply_time:.2f} seconds")
                    else:
                        self.report({'INFO'}, f"Applied {name} in {apply_time * 1000:.2f} ms") 
                    return {'FINISHED'}

                elif self.type == 'Apply_All':
                    bpy.ops.object.convert(target='MESH')
                elif self.type == 'HideAll':
                    for modifier in obj.modifiers:
                        modifier.show_viewport = False
                elif self.type == 'ShowAll':
                    for modifier in obj.modifiers:
                        modifier.show_viewport = True

                elif self.type == 'Render_Toggle':
                    active_modifier.show_render = not active_modifier.show_render
                elif self.type == 'Viewport_Toggle':
                    active_modifier.show_viewport = not active_modifier.show_viewport
                elif self.type == 'Viewport_Toggle_all_selected':
                    selection = set(bpy.context.selected_objects)
                    selection.add(bpy.context.active_object)
                    current_status = active_modifier.show_viewport 
                    mod_name = active_modifier.name
                    for obj in selection:
                        for mod in obj.modifiers:
                            if mod.name == mod_name:
                                mod.show_viewport = not current_status
                            
                elif self.type == 'Edit_Toggle':
                    active_modifier.show_in_editmode = not active_modifier.show_in_editmode
                elif self.type == 'Cage_Toggle':
                    active_modifier.show_on_cage = not active_modifier.show_on_cage
                elif self.type == 'Duplicate':
                    bpy.ops.object.modifier_copy(modifier=active_modifier.name)

        
        if bpy.context.space_data.context == 'MATERIAL':
            obj = bpy.context.active_object
            active_material = obj.active_material
 
            if active_material:
                active_index = obj.material_slots.find(active_material.name)
            else:
                current_active_slot = obj.active_material_index
                active_index = current_active_slot
            
            if self.type == 'delete':
                if bpy.context.mode == 'EDIT_MESH':
                    bpy.ops.object.editmode_toggle()
                    bpy.ops.object.material_slot_remove()
                    bpy.ops.object.editmode_toggle()
                else:
                    bpy.ops.object.material_slot_remove()
                
            elif self.type == 'move_top':
                bpy.ops.object.material_slot_move(direction='UP')
            elif self.type == 'move_bottom':
                bpy.ops.object.material_slot_move(direction='DOWN')
            elif self.type == 'Duplicate':
                bpy.ops.object.material_slot_add()

            elif self.type == 'select_up' and active_index > 0:
                obj.active_material_index = active_index - 1
            elif self.type == 'select_down' and active_index < len(obj.material_slots) - 1:
                obj.active_material_index = active_index + 1
            elif self.type == 'select_top':
                obj.active_material_index = 0
            elif self.type == 'select_bottom':
                obj.active_material_index = len(obj.material_slots) - 1
            elif self.type == 'move_up' and active_index > 0:
                bpy.ops.object.material_slot_move(direction='UP')
                # #move the material and slot one step up, do it wihoute bpy.ops.object.material_slot_move(direction='UP') operations since its slow
                # get_all_materials = [mat for mat in bpy.data.materials if mat.use_nodes]
                # get_active_slot = obj.material_slots[active_index]
                # #move the material one step up
                # previus_index = active_index 
                # active_index = active_index - 1

                # obj.material_slots[active_index].material = get_active_slot.material 
                # obj.material_slots[previus_index].material = get_all_materials[active_index]
                # obj.active_material_index = active_index
            elif self.type == 'move_down' and active_index < len(obj.material_slots) - 1:
                bpy.ops.object.material_slot_move(direction='DOWN')
                # get_all_materials = [mat for mat in bpy.data.materials]
                # get_active_slot = obj.material_slots[active_index]
                # #move the material one step down
                # previus_index = active_index
                # active_index = active_index + 1

                # obj.material_slots[active_index].material = get_active_slot.material
                # obj.material_slots[previus_index].material = get_all_materials[previus_index]
                # obj.active_material_index = active_index
                # #remap the index for faces so that the material index is correct
                # for face in obj.data.polygons:
                #     if face.material_index == active_index:
                #         face.material_index = previus_index
                #     elif face.material_index == previus_index:
                #         face.material_index = active_index
            elif self.type == 'Apply':
                if bpy.context.mode == 'EDIT_MESH':
                    bpy.ops.object.material_slot_assign()
                else:
                    bpy.ops.object.material_slot_copy()
            elif self.type == 'select':
                pass
        return {'FINISHED'}
    def register():
        bpy.utils.register_class(ModiKeyNoUndo)
    def unregister():
        bpy.utils.unregister_class(ModiKeyNoUndo)


class ModiKeyNoUndo(Operator):
    bl_description = ""
    bl_idname = "keyops.modi_key_no_undo"
    bl_label = "KeyOps: Modi Key No Undo"
    bl_options = {'INTERNAL'}

    type: bpy.props.StringProperty(name="type") #type:ignore

    def execute(self, context):

        active_object = bpy.context.active_object
        current_context = bpy.context.space_data.context
        if self.type == 'Toggle_Space':
            if active_object is not None:
                if active_object.type == 'MESH' or active_object.type == 'CURVE' or active_object.type == 'SURFACE' or active_object.type == 'META' or active_object.type == 'FONT':
                    if current_context == 'DATA':
                        bpy.context.space_data.context = 'MODIFIER'
                    elif current_context == 'MODIFIER':
                        bpy.context.space_data.context = 'DATA'
                    else:
                        bpy.context.space_data.context = 'MODIFIER'

                elif active_object.type == 'LIGHT':
                    if current_context == 'OBJECT':
                        bpy.context.space_data.context = 'DATA'
                    elif current_context == 'DATA':
                        bpy.context.space_data.context = 'OBJECT'
                    else:
                        bpy.context.space_data.context = 'DATA'
        if self.type == "Material_Tab":
            if active_object.type == 'MESH' or active_object.type == 'CURVE' or active_object.type == 'SURFACE' or active_object.type == 'META' or active_object.type == 'FONT':
                bpy.context.space_data.context = 'MATERIAL'
    
        return {'FINISHED'}
    