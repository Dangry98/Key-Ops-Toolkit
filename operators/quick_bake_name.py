# Based on the excellent Baking-Namepair-Creator Addon by PLyczkowski
# https://github.com/PLyczkowski/Baking-Namepair-Creator
# Now it also works when more than 2 objects are selected, the active object will be the low poly and the rest will be high poly with a suffix of .001, .002 etc
# In Marmoset Toolbag and Substance Painter, the suffix will make the high poly objects with the same name bake together as one high poly object.

"""
TODO:
- add a reverse function when many objects are selected, so the active object is the high poly and the rest are low poly with a suffix of .001, .002 etc.
- add new operation that do it based on bounding box size or pivot point distance
- make it fast - DONE, about 200-1000 faster now!
"""

import bpy 
import random
import string

from bpy.types import Context
from ..utils.pref_utils import get_keyops_prefs

prefs = get_keyops_prefs()
 
def random_name(size=5, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

class QuickBakeName(bpy.types.Operator):
    bl_description = "Quick Bake Name"
    bl_idname = "keyops.quick_bake_name"
    bl_label = "Quick Bake Name"
    bl_options = {'REGISTER', 'UNDO'}

    random_name : bpy.props.BoolProperty(name="Random Name", description="Random Name", default=True) # type: ignore
    rename_datablock : bpy.props.BoolProperty(name="Rename Datablock", description="Rename Datablock, slower but decreases risk of errors when baking", default=True) # type: ignore
    hide : bpy.props.BoolProperty(name="Hide Objects", description="Hide", default=False) # type: ignore
    type : bpy.props.StringProperty(name="Type", description="Type", default="", options={'SKIP_SAVE'}) # type: ignore
    new_name : bpy.props.StringProperty(
    name="New Name",
    description="Enter a new name for high and low poly objects, it will automatically find them based on the name",
    default="", options={'SKIP_SAVE'},
) # type: ignore
    def invoke(self, context, event):
        if self.type == "RENAME":
            active_object = bpy.context.object
            if not active_object:
                self.report({'WARNING'}, "Please select an active object")
                return {'CANCELLED'}    
            name = active_object.name
            self.new_name = name.split("_low")[0]
            self.new_name = self.new_name.split("_high")[0]
            return context.window_manager.invoke_props_dialog(self)
        else:
            return self.execute(context)
        
    # @classmethod
    # def poll(cls, context):
    #     if context.mode == "OBJECT" and len(context.selected_objects) >= 2:
    #         return True
    #     return False

    def draw(self, context):
        if self.type == "RENAME":
            self.layout.prop(self, "new_name")
        else:
            # if more than 2 objects are selected, show text that says the the active object will be the low poly and the rest will be high poly with a suffix of .001, .002 etc.
            selected = bpy.context.selected_objects
            if len(selected) > 2:
                self.layout.label(text=">2 objects, the active one is set as low-poly", icon="INFO")
            layout = self.layout
            row = layout.row()
            row.prop(self, "hide")
            row = layout.row()
            row.prop(self, "random_name")
            row = layout.row()
            row.prop(self, "rename_datablock")
            row = layout.row()

    def execute(self, context):
        if self.type == "RENAME": 
            new_name = self.new_name
            old_name = bpy.context.object.name.split("_low")[0]
            old_name = old_name.split("_high")[0]
            
            for obj in bpy.context.scene.objects:
                obj_name = obj.name
                if ("_low" in obj_name or "_high" in obj_name) and old_name in obj_name:
                    if "_low" in obj_name:
                        suffix = obj_name.split("_low")[1]
                        obj.name = new_name + "_low" + suffix
                    if "_high" in obj_name:
                        suffix = obj_name.split("_high")[1]
                        obj.name = new_name + "_high" + suffix

            return {'FINISHED'}
        
        if self.type in {"set_high_name", "set_low_name"}:
            suffix = "_high" if self.type == "set_high_name" else "_low"
            selected = bpy.context.selected_objects
            if selected:
                for obj in selected:
                    if "_low" in obj.name or "_high" in obj.name:
                        obj.name = obj.name.split("_low")[0].split("_high")[0] + suffix
                    else:
                        obj.name += suffix
            return {'FINISHED'}

        selected = bpy.context.selected_objects

        in_high_collection = False
        in_low_collection = False

        if len(selected) == 1:
            self.report({'WARNING'}, "Please select at least two objects")
            return {'CANCELLED'}

        if len(selected) == 2:
            for obj in selected:
                for coll in obj.users_collection:
                    if coll.name.lower() == "high":
                        in_high_collection = True
                        high_object = obj
                    elif coll.name.lower() == "low":
                        in_low_collection = True
                        low_object = obj

            if in_high_collection and in_low_collection:
                pass
            else:
                selected = bpy.context.selected_objects

                highest_poly_count_object = None
                highest_poly_count = 0

                for obj in selected:
                    m = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
                    poly_count = len(m.loop_triangles)

                    if poly_count > highest_poly_count:
                        highest_poly_count_object = obj
                        highest_poly_count = poly_count

                if highest_poly_count_object:
                    high_object = highest_poly_count_object
                    low_object = selected[0] if selected[1] == high_object else selected[1]

            if self.random_name:
                low_object.name = random_name() + "_low"
                high_object.name = low_object.name[:-4] + "_high"
                if self.rename_datablock:
                    low_object.data.name = low_object.name
                    high_object.data.name = high_object.name
            else:
                if low_object.name.endswith("_low"):
                    low_object.name = low_object.name[:-4]
                low_name = bpy.data.objects.get(low_object.name + "_low")
                high_name = bpy.data.objects.get(low_object.name + "_high")

                if low_name == None and high_name == None:
                    high_object.name = low_object.name + "_high"
                    low_object.name = low_object.name + "_low"
                    if self.rename_datablock:
                        low_object.data.name = low_object.name
                        high_object.data.name = high_object.name
                else:
                    self.report({'ERROR'}, "Name already exists, please rename the low poly object.")
            if self.hide:
                low_object.hide_set(True)
                high_object.hide_set(True)
            return {'FINISHED'}

        else:
            active_object = bpy.context.object
            high_exists = False
            rename_count = 0

            if self.random_name and active_object:
                active_object.name = random_name()
            
            for selected_object in bpy.context.selected_objects:
                if active_object != selected_object:
                    if high_exists:
                        rename_count += 1
                    elif active_object.name.endswith('_high'):
                        high_exists = True

                    if active_object.name.endswith('_low'):
                        selected_object.name = active_object.name[:-4] + f'_high.00{rename_count}'
                    else:
                        selected_object.name = active_object.name + f'_high.00{rename_count}'

            if not active_object.name.endswith('_low'):
                active_object.name += '_low'

            for obj in bpy.context.selected_objects:
                obj.name = obj.name.replace(".000", "")
            
            if self.hide:
                for obj in bpy.context.selected_objects:
                    obj.hide_set(True)
        return {'FINISHED'}
    
    def register():
        bpy.utils.register_class(QuickBakeNamePanel)
        bpy.utils.register_class(HideShowLowHigh)
    def unregister():
        bpy.utils.unregister_class(QuickBakeNamePanel)
        bpy.utils.unregister_class(HideShowLowHigh)
        
class HideShowLowHigh(bpy.types.Operator):
    bl_idname = "keyops.hide_show_low_high"
    bl_label = "Hide Show Low High"
    bl_description = "Hide Show Low High"
    bl_options = {'INTERNAL', 'UNDO'}

    group : bpy.props.EnumProperty(items = {
        ('HIGH', "High", "High"),
        ('LOW', "Low", "Low"),
        ('ALL', "All", "All"),
    }) # type: ignore
    action : bpy.props.EnumProperty(items = {
        ('SHOW', "Show", "Show"),
        ('HIDE', "Hide", "Hide")
    }) # type: ignore

    def execute(self, context):
        if self.group == 'HIGH':
            suffixes = ("_high",) + tuple("_high.{:03d}".format(i) for i in range(128))                                              
        elif self.group == 'LOW':
            suffixes = ("_low",) + tuple("_low.{:03d}".format(i) for i in range(128))
        else:
            suffixes = ("_low",) + tuple("_low.{:03d}".format(i) for i in range(128)) + ("_high",) + tuple("_high.{:03d}".format(i) for i in range(30))

        for obj in bpy.data.objects:
            if not obj.name.endswith(suffixes):
                continue
            if self.action == 'SHOW':
                obj.hide_set(False)
            else:
                obj.hide_set(True)
        return {'FINISHED'}
    

def draw_quick_bake_name(self, context, draw_header=False):       
    def draw_toggle_viewport(context, group, layout):
        row = layout.row()
        row.label(text=group.lower())
        op = row.operator("keyops.hide_show_low_high", text="SHOW")
        op.group = group
        op.action = 'SHOW'
        op = row.operator("keyops.hide_show_low_high", text="HIDE")
        op.group = group
        op.action = 'HIDE'

    layout = self.layout
    box = layout.box()
    row = box.row(align=True)
    if draw_header:
        row.label(text="Quick Bake Name", icon='MATSHADERBALL')
        row = box.row(align=True)
    row.operator("keyops.quick_bake_name", text="Quick Bake Name")
    row.scale_y = 1.3
    row.scale_x = 0.7
    row.operator("keyops.quick_bake_name", text="Rename").type = "RENAME"

    row = box.row(align=True)
    row.scale_y = 0.95
    row.operator("keyops.quick_bake_name", text="Add _high").type = "set_high_name"
    row.operator("keyops.quick_bake_name", text="Add _low").type = "set_low_name"
    
    draw_toggle_viewport(context, 'HIGH', box)
    draw_toggle_viewport(context, 'LOW', box)
    # draw_toggle_viewport(context, 'ALL', box)

class QuickBakeNamePanel(bpy.types.Panel):
    bl_description = "Quick Bake Name Panel"
    bl_label = "Quick Bake Name"
    bl_idname = "KEYOPS_PT_quick_bake_name_panel"
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
        layout.label(icon='MATSHADERBALL')
        
    def draw(self, context):
        draw_quick_bake_name(self, context)