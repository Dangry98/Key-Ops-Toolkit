import bpy.types
from bpy.props import StringProperty, PointerProperty, CollectionProperty
from bpy_extras import view3d_utils

class MaterialItem(bpy.types.PropertyGroup):
    name: StringProperty() # type: ignore

# Custom property to store the materials thar are linked wuth name and everything and add them to the list
class MaterialListProperty(bpy.types.PropertyGroup):
    items: CollectionProperty(type=MaterialItem) # type: ignore

material_list = []
material_list_index = 0
material_list_item_name = []
active_index = 0
assign_index = 0

class MaterialIndex(bpy.types.Operator):
    bl_idname = "keyops.material_index"
    bl_label = "KeyOps: Material Index"
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.StringProperty() # type: ignore
    material_name: bpy.props.StringProperty(name="Material Name", default="") # type: ignore

    def execute(self, context):
        global active_index
      
        #if screw modifier or curv object is present, set material with modifier instead of material index, same with boolean? Or make so that booleon get the same material as the object it cuts
        if self.type == "Make_Material_Index":
            import time
            start_time = time.time()
            if bpy.context.mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='OBJECT')

            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH' or obj.type == 'CURVE' and not obj.display_type == 'WIRE':
                    bpy.context.view_layer.objects.active = obj

                    current_active_object_existing_materials_names = [material.name for material in obj.material_slots]

                    # Add materials from the material list to the object
                    for material_item in context.scene.material_list_property.items:
                        material_name = material_item.name
                        material = bpy.data.materials.get(material_name)

                        if material_name not in current_active_object_existing_materials_names:
                            obj.data.materials.append(bpy.data.materials.get(material_name))
                        
                    #if thers a material i current_active_object_existing_materials_names that is not in the material list remove it
                    for material_name in current_active_object_existing_materials_names:
                        if material_name not in [material_item.name for material_item in context.scene.material_list_property.items]:
                            obj.active_material_index = len(obj.material_slots)-1
                            #if its not the same index as the material list
                            while obj.active_material.name != material_name:
                                obj.active_material_index -=1
                            # Remove materials that do not have the same name as in the material list for each object
                            obj.data.materials.pop(index=obj.active_material_index)


                    material_names_in_order = [material_item.name for material_item in context.scene.material_list_property.items]

                    material_index_dict = {name: index for index, name in enumerate(material_names_in_order)}

                    # Sort the material slots based on the order in the material list, current bottleneck is bpy.ops.object.material_slot_move, should be replaced with a none bpy.ops solution
                    for index, slot in enumerate(obj.material_slots):
                        for material_name in current_active_object_existing_materials_names:
                            if material_name in material_names_in_order:
                                obj.active_material_index = len(obj.material_slots)-1
                                #if its not the same index as the material list
                                while obj.active_material.name != material_name:
                                    obj.active_material_index -=1
                                while obj.active_material_index > material_index_dict[material_name]:
                                    bpy.ops.object.material_slot_move(direction='UP')
                                #repete if its still does not match
                                while obj.active_material_index < material_index_dict[material_name]:
                                    bpy.ops.object.material_slot_move(direction='DOWN')
            
            print ("%s seconds" % (time.time() - start_time))
            #Benchmarks, before, before, after optimization:
            #61.839571475982666 seconds, 7.817131280899048 seconds, 6.89214015007019 seconds
                    
        elif self.type == "Clear_Unused_Materials":
            # import time
            # start_time = time.time()

            if bpy.context.mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='OBJECT')

            for obj in bpy.context.selected_objects:
                has_screw_modifier = any(modifier.type == "SCREW" for modifier in obj.modifiers)

                if has_screw_modifier:
                    #remove all but the top material slot
                    if obj.material_slots:
                        for i in range(len(obj.material_slots) - 1, 0, -1):
                            obj.data.materials.pop(index=i)
                else:
                    material_indices = set()
                    
                    if not obj.material_slots or not obj.type == "MESH":
                        continue
                    for f in obj.data.polygons:
                        material_indices.add(f.material_index)
                    for i in range(len(obj.material_slots) - 1, -1, -1):
                        if i not in material_indices:
                            if i < len(obj.data.materials):
                                obj.data.materials.pop(index=i)
            # print ("%s seconds" % (time.time() - start_time))
            #from 28 seconds to 0.02 seconds when not using bpy.ops.object.material_slot_remove_unused() lol :) 

                #     self.report({'INFO'}, "Cleared Unused Materials")
                # else:
                #     self.report({'WARNING'}, "Only Works on Meshes")


        elif self.type == "Add_Iteam_To_Material_Index":
            #get active object
            obj = bpy.context.active_object
            if obj.type == 'MESH':
                active_material = obj.active_material

                #add material to list
                material_list_item_name.append(active_material.name)
                material_list.append(active_material)
                #add material to list property
                item = context.scene.material_list_property.items.add()
                item.name = active_material.name
                print([item.name for item in context.scene.material_list_property.items])
                self.report({'INFO'}, "Added Material to Index")
                #update ui
                context.area.tag_redraw()
                
            else:
                self.report({'WARNING'}, "Only Works on Meshes")

        elif self.type == "Remove_Iteam_From_Material_Index":
            if active_index is not None and active_index < len(context.scene.material_list_property.items):
                context.scene.material_list_property.items.remove(active_index)
                print([item.name for item in context.scene.material_list_property.items])
                #update index if its the last
                if active_index == len(context.scene.material_list_property.items):
                    active_index = active_index - 1
                self.report({'INFO'}, "Removed Material from Index")

        elif self.type == "Move_Material_Index_Up":
            if active_index is not None and active_index < len(context.scene.material_list_property.items):
                context.scene.material_list_property.items.move(active_index, active_index - 1)
                #update index
                if active_index > 0:
                    active_index = active_index - 1
                    self.report({'INFO'}, "Moved Material Index Up")
        elif self.type == "Move_Material_Index_Down":
            if active_index is not None and active_index < len(context.scene.material_list_property.items):
                context.scene.material_list_property.items.move(active_index, active_index + 1)
                #update index
                if active_index < len(context.scene.material_list_property.items):
                    active_index = active_index + 1
                    self.report({'INFO'}, "Moved Material Index Down")
        elif self.type == "Refresh_Material_Name":
            #get active object
            obj = bpy.context.active_object
            if obj.type == 'MESH':
                active_material = obj.active_material
                #update material name in list from active material slot name
                if active_index is not None and active_index < len(context.scene.material_list_property.items):
                    context.scene.material_list_property.items[active_index].name = active_material.name
                    self.report({'INFO'}, "Refreshed Material Name")

            elif bpy.context.mode == 'OBJECT':
                #get the index row and assing that material to the active slot in the active material and all other select objects
                for obj in bpy.context.selected_objects:
                    if obj.type == 'MESH':
                        obj.active_material_index = active_index
                        bpy.ops.object.material_slot_assign()
                        self.report({'INFO'}, "Assigned Material")           

        return {'FINISHED'}
    
    def register():
        bpy.utils.register_class(MaterialIndexPanel)
        bpy.utils.register_class(MATERIALINDEX_OT_refresh)
        bpy.utils.register_class(MaterialAssign)
        bpy.utils.register_class(MaterialItem)
        bpy.utils.register_class(MaterialListProperty)
        #bpy.utils.register_class(MaterialPicker)
        bpy.types.Scene.material_list_property = PointerProperty(type=MaterialListProperty)

    def unregister():
        bpy.utils.unregister_class(MaterialIndexPanel)
        bpy.utils.unregister_class(MATERIALINDEX_OT_refresh)
        bpy.utils.unregister_class(MaterialAssign)
        bpy.utils.unregister_class(MaterialItem)
        bpy.utils.unregister_class(MaterialListProperty)
        #bpy.utils.unregister_class(MaterialPicker)
        del bpy.types.Scene.material_list_property

    
class MaterialIndexPanel(bpy.types.Panel):
    bl_description = "Material Index Panel"
    bl_label = "Material Index"
    bl_idname = "KEYOPS_PT_material_index"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context): 
        global active_index
        global material_list
        global material_list_item_name
        global assign_index

        layout = self.layout
        row = layout.row(align=True)
        row.operator("keyops.material_index", text="Set Index", icon='MATERIAL').type = "Make_Material_Index"
        row.operator("keyops.material_index", text="Clear", icon='PANEL_CLOSE').type = "Clear_Unused_Materials"
        row = layout.row(align=True)
        row.operator("keyops.material_index", text="Up", icon='TRIA_UP').type = "Move_Material_Index_Up"
        row.operator("keyops.material_index", text="Down", icon='TRIA_DOWN').type = "Move_Material_Index_Down"
        row = layout.row()
        row.label(text="Index List", icon='MATERIAL')
        row.operator("keyops.material_index", text="", icon='FILE_REFRESH').type = "Refresh_Material_Name"
        row.operator("keyops.material_index", text="", icon='ADD').type = "Add_Iteam_To_Material_Index"
        row.operator("keyops.material_index", text="", icon='REMOVE').type = "Remove_Iteam_From_Material_Index"

        col_flow = layout.column_flow(columns=0, align=True)

        for index, material_item in enumerate(context.scene.material_list_property.items):
            row = col_flow.row(align=True)
            row.alignment = 'LEFT'

            materials = [mat for mat in bpy.data.materials if material_item.name == mat.name]

            if materials:
                mat = materials[0]
                material_icon = layout.icon(mat)
      
            else:
                material_icon = 1
                print("Material not found")                

            icon = 'RESTRICT_SELECT_OFF' if index == active_index else 'RESTRICT_SELECT_ON'
            row.operator("keyops.material_index_assign", text="", icon_value=material_icon).assign_material = str(index)
            row.label(text=f"ID: {index+1} ")

            text = f"{material_item.name}"
            row.label(text=text)
            row.operator("keyops.material_index_user_interaction", text="", icon=icon).make_active = str(index)

class MATERIALINDEX_OT_refresh(bpy.types.Operator):
    bl_idname = "keyops.material_index_user_interaction"
    bl_label = "Show polycount in Scene properties panel"
    bl_description = "Show polycount in Scene properties panel"
    make_active: StringProperty(default="") # type: ignore

    def execute(self, context):
        global active_index
        if (self.make_active != ""):
            material_list_index = int(self.make_active)
            active_index = []  
            active_index = (material_list_index)

        return {'FINISHED'}
    
class MaterialAssign(bpy.types.Operator):
    bl_idname = "keyops.material_index_assign"
    bl_label = "KeyOps: Material Index Assign"
    bl_options = {'INTERNAL', 'UNDO'}
    assign_material: StringProperty(default="") # type: ignore

    def execute(self, context):
        global assign_index

        if (self.assign_material != ""):
            material_list_index = int(self.assign_material)
            assign_index = []  
            assign_index = (material_list_index)
            # for material_item in context.scene.material_list_property.items:
            #     material_name = material_item.name

            # if bpy.context.mode == 'EDIT_MESH':
            #     for obj in bpy.context.selected_objects:
            #         if obj.type == 'MESH':

            #             #if the materail does not already exist add it. else just assign it
            #             current_active_object_existing_materials_names = [material.name for material in obj.material_slots]

            #                                 #if thers a material i current_active_object_existing_materials_names that is not in the material list remove it
            #             for material_name in current_active_object_existing_materials_names:
            #                 if material_name not in [material_item.name for material_item in context.scene.material_list_property.items]:
            #                     obj.active_material_index = len(obj.material_slots)-1
            #                     #if its not the same index as the material list
            #                     while obj.active_material.name != material_name:
            #                         obj.active_material_index -=1
            #                     # Remove materials that do not have the same name as in the material list for each object
            #                     obj.data.materials.pop(index=obj.active_material_index)
            #             #else add new material that in material list active
            #             if context.scene.material_list_property.items[assign_index].name not in current_active_object_existing_materials_names:
            #                 obj.data.materials.append(bpy.data.materials.get(context.scene.material_list_property.items[assign_index].name))
 
            #             #add the material to the slot if it does not exist
            #             obj.material_slots[len(obj.material_slots) - 1].material = bpy.data.materials.get(context.scene.material_list_property.items[assign_index].name)
            #             #assign after active material list index name
            #             obj.active_material_index = len(obj.material_slots) - 1
            #             bpy.ops.object.material_slot_assign()
            #             self.report({'INFO'}, "Assigned Material")
            # elif bpy.context.mode == 'OBJECT':

            #can be optimzed a lot if needed by not using bpy.ops.object.material_slot_assign(), almost there, but not quite yet
            mat = context.scene.material_list_property.items[assign_index].name
            op = bpy.ops.object.apply_material
            op(mat_to_assign = mat)
              
                #get the index row and assign that material to the active slot in the active material and all other select objects
                # for obj in bpy.context.selected_objects:
                #     if obj.type == 'MESH':
                #         if obj.active_material_index < len(obj.material_slots):
                #             obj.data.materials.pop(index=obj.active_material_index)
                #         obj.data.materials.append(bpy.data.materials.get(context.scene.material_list_property.items[assign_index].name))
        return {'FINISHED'}
    
    def register():
        bpy.types.EEVEE_MATERIAL_PT_context_material.append(menu_material)
        if hasattr(bpy.types, 'CYCLES_PT_context_material'):
            bpy.types.CYCLES_PT_context_material.append(menu_material)
    def unregister():
        if hasattr(bpy.types, 'EEVEE_MATERIAL_PT_context_material'):
            bpy.types.EEVEE_MATERIAL_PT_context_material.remove(menu_material)
        if hasattr(bpy.types, 'CYCLES_PT_context_material'):
            bpy.types.CYCLES_PT_context_material.remove(menu_material)
    
def menu_material(self, context):
    layout = self.layout
    row = layout.row(align=True)
    if bpy.context.mode == 'OBJECT':
        #row.operator("view3d.material_picker", icon = "EYEDROPPER")
        if bpy.context.active_object.data.materials:
            row.operator("object.material_slot_copy", text="Assign")
            row.operator("keyops.material_index", text="Clear Unused").type="Clear_Unused_Materials"



def main(context, event):
    # get the context arguments
    scene = context.scene
    region = context.region
    rv3d = context.region_data
    coord = event.mouse_region_x, event.mouse_region_y
#    scene = bpy.context.scene 
#    viewlayer = bpy.context.view_layer
    viewlayer = context.view_layer

    # get the ray from the viewport and mouse
    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
#    ray_target = ray_origin + (view_vector *-10)
#    ray_goal = ray_origin + (view_vector *1000)
    

#    result, location, normal, index, object, matrix = scene.ray_cast(viewlayer, ray_target, ray_goal)
    result, location, normal, index, object, matrix = scene.ray_cast(bpy.context.evaluated_depsgraph_get(), ray_origin, view_vector)

    # get and select object
#    obj = object  
#    bpy.ops.object.select_all(action='DESELECT')
#    context.view_layer.objects.active = obj

    if result:
        for o in context.selected_objects:
            o.select_set(False)
        dg = context.depsgraph
#        eval_obj = dg.id_eval_get(obj)
        eval_obj = dg.id_eval_get(object)
        viewlayer.objects.active = object.original
    
#    if obj:
        # select material slot
        MatInd = eval_obj.data.polygons[index].material_index
        
        print (MatInd)
        object.original.active_material_index = MatInd

#    else:
#        return {'CANCELLED'}
    return {'FINISHED'}


class MaterialPicker(bpy.types.Operator):
    bl_idname = "view3d.material_picker"
    bl_label = ""

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 
'WHEELDOWNMOUSE'}:
            # allow navigation
            return {'PASS_THROUGH'}
#        elif event.type == 'LEFTMOUSE':
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            main(context, event)
            return {'RUNNING_MODAL'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.space_data.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}