import bpy.types, bmesh
from bpy.props import StringProperty, PointerProperty, CollectionProperty
from bpy_extras import view3d_utils
from ..utils.pref_utils import get_keyops_prefs

def clear_unused_materials(obj):
    material_indices = set()
    
    if obj.material_slots and obj.type == "MESH":
        for f in obj.data.polygons:
            material_indices.add(f.material_index)
        for i in range(len(obj.material_slots) - 1, -1, -1):
            if i not in material_indices:
                if i < len(obj.data.materials):
                    obj.data.materials.pop(index=i)

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
            # import time
            # start_time = time.time()
            if bpy.context.mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='OBJECT')

            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH' or obj.type == 'CURVE' and not obj.display_type == 'WIRE':
                    m = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()

                    #need to cheack for empty mesh since it can soft lock blender
                    if m is not None:
                        faces = len(m.polygons)
                        if faces >= 1:
                            clear_unused_materials(obj)
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
        
            # print ("%s seconds" % (time.time() - start_time))
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
                    clear_unused_materials(obj)
              
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
        bpy.utils.register_class(MaterialItem)
        bpy.utils.register_class(MaterialListProperty)
        bpy.utils.register_class(MaterialListMenu)
        bpy.utils.register_class(MaterialSelectByActive)
        bpy.utils.register_class(AssignMaterial)
        #bpy.utils.register_class(MaterialPicker)
        bpy.types.Scene.material_list_property = PointerProperty(type=MaterialListProperty)

    def unregister():
        bpy.utils.unregister_class(MaterialIndexPanel)
        bpy.utils.unregister_class(MATERIALINDEX_OT_refresh)
        bpy.utils.unregister_class(MaterialItem)
        bpy.utils.unregister_class(MaterialListProperty)
        bpy.utils.unregister_class(MaterialListMenu)
        bpy.utils.unregister_class(MaterialSelectByActive)
        bpy.utils.unregister_class(AssignMaterial)
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
    bl_order = 10

    @classmethod
    def poll(cls, context):
        prefs = get_keyops_prefs()
        return prefs.material_utilities_panel

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon='PRESET')

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
            row.operator("object.assign_materials_by_name", text="", icon_value=material_icon).mat_name = str(material_item.name)
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
    
class MaterialSelectByActive(bpy.types.Operator):
    bl_idname = "object.select_material_by_active"
    bl_label = "Select Objects with Material"
    bl_options = {'INTERNAL', 'UNDO'}

    deselect: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'}) # type: ignore

    def execute(self, context):
        active_material = context.active_object.active_material

        for obj in context.scene.objects:
            if obj.material_slots:
                for slot in obj.material_slots:
                    if slot.material == active_material:
                        if self.deselect:
                            obj.select_set(False)
                        else:
                            obj.select_set(True)
                        break
        return {'FINISHED'}


def check_if_material_exists_in_object(obj, mat):
    for i, slot in enumerate(obj.material_slots):
        if slot.material == mat:
            obj.active_material_index = i
            return True
        
class AssignMaterial(bpy.types.Operator):
    bl_idname = "object.assign_materials_by_name"
    bl_label = "Assign Material"
    bl_options = {'REGISTER', 'UNDO'}

    mat_name: bpy.props.StringProperty(name="Material Name", options={'SKIP_SAVE'}) # type: ignore
    add_by: bpy.props.EnumProperty(
        items=[
            ("INDEX", "Active Index", "Assign by material index"),
            ("INDEX_ID", "Index ID", "Assign by index ID"),
        ],
        name="Add By",
        default="INDEX_ID"
    ) # type: ignore

    id: bpy.props.IntProperty(name="Index ID", default=0, min=0, max=64) # type: ignore

    def draw(self, context):
        if context.mode != 'EDIT_MESH':
            layout = self.layout
            row = layout.row()
            row.prop(self, "add_by", text="By")
            if self.add_by == "INDEX_ID":
                row.prop(self, "id")

    def execute(self, context):
        mat = bpy.data.materials.get(self.mat_name)
        selection = set(context.selected_objects)
        active_object = bpy.context.object
        selection.add(active_object)

        if not self.mat_name:
            self.mat_name = active_object.active_material.name

        if active_object:
            active_obj_index = active_object.active_material_index
            
            for obj in selection:
                if obj.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
                    if context.mode != 'EDIT_MESH':
                        if self.add_by == "INDEX":
                            if obj.active_material:
                                obj.active_material_index = active_obj_index
                                obj.active_material = mat
                            else:
                                obj.data.materials.append(mat)
                        elif self.add_by == "INDEX_ID":
                            if obj.active_material:
                                obj.active_material_index = self.id
                                obj.active_material = mat
                            else:
                                obj.data.materials.append(mat)
                    else:
                        mat_found = check_if_material_exists_in_object(obj, mat)
                                
                        if not mat_found:
                            obj.data.materials.append(mat)
                            obj.active_material_index = len(obj.material_slots) - 1

                        if obj.type == 'MESH':
                            bm = bmesh.from_edit_mesh(obj.data)
                            mat_idx = obj.active_material_index
                            for face in bm.faces:
                                if face.select:
                                    face.material_index = mat_idx
                            obj.data.update()

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
            if bpy.context.active_object.active_material:
                row.operator("object.assign_materials_by_name", text="Assign").mat_name = bpy.context.active_object.active_material.name
                row.operator("object.select_material_by_active", text="Select")
                row.operator("object.select_material_by_active", text="Deselect").deselect = True
                row.operator("keyops.material_index", text="Clear Unused").type="Clear_Unused_Materials"

class MaterialListMenu(bpy.types.Menu):
    bl_idname = "MATERIAL_MT_material_list"
    bl_label = "Material List"

    def draw(self, context):
        prefs = get_keyops_prefs()
        layout = self.layout
        col = layout.column()
        
        # Get non-grease pencil materials
        materials = [m for m in bpy.data.materials if not m.is_grease_pencil]
        
        if prefs.material_list_type == "PREVIEW_ICONS":
            # Icon grid view
            max_materials_per_row = 12
            num_columns = max(4, (len(materials) + 7) // max_materials_per_row)
            grid = col.grid_flow(row_major=False, columns=num_columns, 
                               even_columns=True, even_rows=True, align=True)
            
            for mat in materials:
                cell = grid.column()
                icon = layout.icon(mat)
                cell.template_icon(icon_value=icon, scale=prefs.material_list_icon_scale)
                # Truncate long names
                text = mat.name
                max_len = 8
                if len(text) > max_len:
                    text = text[:max_len + 2] if len(text) - max_len <= 2 else f"{text[:max_len].rstrip()}.."

                op = cell.operator("object.assign_materials_by_name", text=text, emboss=True)
                op.mat_name = mat.name
        else:
            # Compact list view
            max_items_per_column = 24
            num_columns = (len(materials) + max_items_per_column - 1) // max_items_per_column
            max_text_length = 24 

            if num_columns > 1:
                grid = col.grid_flow(columns=num_columns, align=True)
                sub_col = grid.column()
            else:
                sub_col = col

            for i, mat in enumerate(materials):
                if num_columns > 1 and i % max_items_per_column == 0 and i > 0:
                    sub_col = grid.column()

                display_name = mat.name
                if len(display_name) > max_text_length:
                    display_name = display_name[:max_text_length + 2] if len(display_name) - max_text_length <= 2 else f"{display_name[:max_text_length].rstrip()}.."

                kwargs = {
                    "text": display_name,
                    "emboss": True
                }
                if prefs.material_list_show_icons:
                    kwargs["icon_value"] = layout.icon(mat)
                    
                op = sub_col.operator("object.assign_materials_by_name", **kwargs)
                op.mat_name = mat.name
