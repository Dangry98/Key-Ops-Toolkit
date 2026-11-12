import bpy.types, bmesh
from ..utils.pref_utils import get_keyops_prefs
from ..utils.pref_utils import clear_registered_keymaps

active_index = 0
registered_material_index_keymaps = []

def register_material_index_keymaps():
    global registered_material_index_keymaps
    wm = bpy.context.window_manager

    km = wm.keyconfigs.addon.keymaps.new(name='3D View Generic', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu', 'M', 'PRESS', alt=True)
    kmi.properties.name = 'MATERIAL_MT_material_list'
    registered_material_index_keymaps.append((km, kmi))

    km = wm.keyconfigs.addon.keymaps.new(name='Mesh', space_type='EMPTY')
    kmi = km.keymap_items.new('wm.call_menu', 'M', 'PRESS', alt=True)
    kmi.properties.name = 'MATERIAL_MT_material_list'
    registered_material_index_keymaps.append((km, kmi))

class MaterialSelectByActive(bpy.types.Operator):
    bl_idname = "object.select_material_by_active"
    bl_label = "Select Objects with Material"
    bl_options = {'INTERNAL', 'UNDO'}

    deselect: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'}) # type: ignore

    def execute(self, context):
        active_material = context.active_object.active_material
        obj_view_layer = set(context.view_layer.objects)

        for obj in context.scene.objects:
            if obj.material_slots:
                for slot in obj.material_slots:
                    if slot.material == active_material:
                        if self.deselect:
                            if obj in obj_view_layer:
                                obj.select_set(False)
                        else:
                            if obj in obj_view_layer:
                                obj.select_set(True)
                        break
        return {'FINISHED'}
    
class ClearUnusedMaterials(bpy.types.Operator):
    bl_idname = "object.clear_unused_materials"
    bl_label = "Clear Unused Materials"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = """Clears all unused materials from the active object or all selected objects.

Alt - Clear from all selected objects"""

    all_selected_objects: bpy.props.BoolProperty(
        name="All Selected Objects",
        description="""Clears all unused materials from all selected objects. Else clears from the active object only.""",
        default=False
    ) # type: ignore

    def invoke(self, context, event):
        if event.alt:
            self.all_selected_objects = True
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "all_selected_objects")

    def execute(self, context):
        selected = [context.view_layer.objects.active]
        if self.all_selected_objects:
            selected.extend(context.selected_objects)

        for obj in selected:
            material_indices = set()
            
            if obj.material_slots and obj.type == "MESH":
                for f in obj.data.polygons:
                    material_indices.add(f.material_index)
                for i in range(len(obj.material_slots) - 1, -1, -1):
                    if i not in material_indices:
                        if i < len(obj.data.materials):
                            obj.data.materials.pop(index=i)

        return {'FINISHED'}


class RemoveAllObjectMaterials(bpy.types.Operator):
    bl_idname = "object.remove_all_object_materials"
    bl_label = "Remove All Object Materials"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = """Removes all materials from object
        
Alt - Hold to remove from all selected objects"""

    all_selected_objects: bpy.props.BoolProperty(
        name="All Selected Objects",
        description="""Removes all materials from all selected objects. Else removes all materials from the active object only.""",
        default=False
    ) # type: ignore

    def invoke(self, context, event):
        if event.alt:
            self.all_selected_objects = True
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "all_selected_objects")

    def execute(self, context):
        objects = [context.view_layer.objects.active]
        if self.all_selected_objects:
            objects.extend(context.selected_objects)

        for obj in objects:
            if obj.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
                obj.data.materials.clear()

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
    if bpy.context.mode == 'OBJECT':
        layout = self.layout
        row = layout.row(align=True)
        #row.operator("view3d.material_picker", icon = "EYEDROPPER")
        if bpy.context.active_object.data.materials:
            if bpy.context.active_object.active_material:
                row.operator("object.assign_materials_by_name", text="Assign").mat_name = bpy.context.active_object.active_material.name
                row.operator("object.select_material_by_active", text="Select")
                row.operator("object.select_material_by_active", text="Deselect").deselect = True
                row.operator("object.clear_unused_materials", text="Clear Unused").all_selected_objects = True

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

classes = (
    MaterialListMenu,
    MaterialSelectByActive,
    AssignMaterial,
    RemoveAllObjectMaterials,
    ClearUnusedMaterials,
)

def draw_remove_all_materials(self, context):
    layout = self.layout
    layout.separator()
    op = layout.operator(RemoveAllObjectMaterials.bl_idname, text="Remove All Materials", icon='X')
    op.all_selected_objects = False

def draw_remove_all_materials_from_selected(self, context):
    layout = self.layout
    layout.separator()
    op = layout.operator(RemoveAllObjectMaterials.bl_idname, text="Remove All Materials from Selected", icon='X')
    op.all_selected_objects = True

def register_material_index():
    for cls in classes:
        bpy.utils.register_class(cls)
    register_material_index_keymaps()

    bpy.types.MATERIAL_MT_context_menu.append(draw_remove_all_materials)
    bpy.types.VIEW3D_MT_object_cleanup.append(draw_remove_all_materials_from_selected)

def unregister_material_index():
    clear_registered_keymaps(registered_material_index_keymaps)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.types.MATERIAL_MT_context_menu.remove(draw_remove_all_materials)
    bpy.types.VIEW3D_MT_object_cleanup.remove(draw_remove_all_materials_from_selected)
