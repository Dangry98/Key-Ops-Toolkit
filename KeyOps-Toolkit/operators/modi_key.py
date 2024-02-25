from typing import Set
import bpy.types
from bpy.types import Context, Operator
from ..utils.pref_utils import get_is_addon_enabled

modifier_list = None

class ModiKey(Operator):
    bl_idname = "keyops.modi_key"
    bl_label = "KeyOps: Modi Key"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.StringProperty(name="type") #type:ignore

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        global modifier_list

        if bpy.context.space_data.context == 'MODIFIER':
            if modifier_list is None:
                modifier_list = get_is_addon_enabled('modifier_list' or 'modifier_list-master')  

            obj = bpy.context.active_object
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
                    if modifier_list:
                        bpy.ops.object.ml_modifier_remove("INVOKE_DEFAULT")
                    else:
                        current_mode = bpy.context.object.mode
                        bpy.ops.object.mode_set(mode='OBJECT')
                        bpy.ops.ed.undo_push()
                        obj.modifiers.remove(active_modifier)
                        bpy.ops.object.mode_set(mode=current_mode)
                elif self.type == 'Apply':
                    if modifier_list:
                        bpy.ops.object.ml_modifier_apply("INVOKE_DEFAULT")
                    else:
                        if bpy.context.mode == 'OBJECT':
                            bpy.ops.object.modifier_apply(modifier=active_modifier.name)
                        else:
                            current_mode = bpy.context.object.mode
                            bpy.ops.object.mode_set(mode='OBJECT')
                            bpy.ops.ed.undo_push()
                            bpy.ops.object.modifier_apply(modifier=active_modifier.name)
                            bpy.ops.object.mode_set(mode=current_mode)

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
                elif self.type == 'Edit_Toggle':
                    active_modifier.show_in_editmode = not active_modifier.show_in_editmode
                elif self.type == 'Cage_Toggle':
                    active_modifier.show_on_cage = not active_modifier.show_on_cage
                elif self.type == 'Duplicate':
                    modifier_list.duplicate_modifier = active_modifier.name

        
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
                bpy.ops.object.material_slot_assign()
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
    bl_options = {'REGISTER'}

    type: bpy.props.StringProperty(name="type") #type:ignore

    def execute(self, context):

        if self.type == 'Toggle_Space':
            active_object = bpy.context.active_object
            current_context = bpy.context.space_data.context

            if active_object is not None:
                if current_context == 'DATA':
                    bpy.context.space_data.context = 'MODIFIER'
                elif current_context == 'MODIFIER':
                    bpy.context.space_data.context = 'DATA'
                else:
                    bpy.context.space_data.context = 'MODIFIER'
    
        return {'FINISHED'}
    