# Based on the excellent Baking-Namepair-Creator Addon by PLyczkowski
#https://github.com/PLyczkowski/Baking-Namepair-Creator
#Now it also works when more than 2 objects are selected, the active object will be the low poly and the rest will be high poly with a suffix of .001, .002 etc
#In Marmoset Toolbag and Substance Painter, the suffix will make the high poly objects with the same name bake together as one high poly object.

"""
TODO:
- add a reverse function when many objects are selected, so the active object is the high poly and the rest are low poly with a suffix of .001, .002 etc.
- add new operation that do it based on bounding box size or pivot point distance
"""

import bpy 
import random
import string
import bmesh
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
    rename_datablock : bpy.props.BoolProperty(name="Rename Datablock", description="Rename Datablock", default=True) # type: ignore
    hide : bpy.props.BoolProperty(name="Hide Renamed", description="Hide", default=False) # type: ignore
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "hide")
        row = layout.row()
        row.prop(self, "random_name")
        row = layout.row()
        row.prop(self, "rename_datablock")
        row = layout.row()

    def execute(self, context):
        selected = bpy.context.selected_objects

        in_high_collection = False
        in_low_collection = False

        if len(selected) == 1:
            self.report({'WARNING'}, "Please select at least two objects")

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
                depsgraph = bpy.context.evaluated_depsgraph_get()

                highest_poly_count_object = None
                highest_poly_count = 0

                for obj in selected:
                    bm = bmesh.new()
                    bm.from_object(obj, depsgraph)
                    poly_count = len(bm.verts)
                    bm.free()

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
    
class QuickBakeNamePanel(bpy.types.Panel):
    bl_description = "Quick Bake Name Panel"
    bl_label = "Quick Bake Name"
    bl_idname = "KEYOPS_PT_quick_bake_name_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ToolKit'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return get_keyops_prefs().enable_quick_bake_name
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("keyops.quick_bake_name", text="Quick Bake Name")
        row.scale_y = 1.25
        
        self._draw_toggle_viewport(context, 'HIGH', layout)
        self._draw_toggle_viewport(context, 'LOW', layout)
        self._draw_toggle_viewport(context, 'ALL', layout)
    
    def _draw_toggle_viewport(self, context, group, layout):
        row = layout.row()
        row.label(text=group.lower())
        op = row.operator("keyops.hide_show_low_high", text="SHOW")
        op.group = group
        op.action = 'SHOW'
        op = row.operator("keyops.hide_show_low_high", text="HIDE")
        op.group = group
        op.action = 'HIDE'
       