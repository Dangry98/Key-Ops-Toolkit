import bpy

class AutoSmooth(bpy.types.Operator):
    """Set auto smooth on selected objects"""
    bl_idname = "object.auto_smooth"
    bl_label = "Auto Smooth"
    bl_options = {'REGISTER', 'UNDO'}

    auto_smooth: bpy.props.BoolProperty(
        name="Auto Smooth",
        description="Auto Smooth",
        default=True
    ) #type: ignore

    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Angle",
        default=0.785398, #45 degrees
        min=0,
        max=3.14159,
        subtype="ANGLE",
    ) #type: ignore

    ignore_sharp: bpy.props.BoolProperty(
        name="Ignore Sharp",
        description="Ignore Sharp",
        default=True
    ) #type: ignore

    # remove_existing_sharp: bpy.props.BoolProperty(
    #     name="Remove Existing Sharp Edges",
    #     description="Delete Sharp",
    #     default=True
    # ) #type: ignore

    all_instances: bpy.props.BoolProperty(
        name="Apply on All Instances",
        description="Apply on All Instances",
        default=True
    ) #type: ignore

    move_to_bottom: bpy.props.BoolProperty(
        name="Move to Bottom",
        description="Move to Bottom",
        default=True
    ) #type: ignore

    def execute(self, context):
        active_object = context.active_object
        selected_objects = context.selected_objects

        if self.all_instances:
            for obj in context.selected_objects:
                instances = [o for o in bpy.data.objects if o.data == obj.data]
                for inst in instances:
                    if inst not in selected_objects:
                          selected_objects.extend([inst])
              
        if self.auto_smooth:
            #bpy.ops.object.shade_smooth(keep_sharp_edges=not self.ignore_sharp)
            
            def add_smooth_modifier(obj):
                if "Auto Smooth" in [m.name for m in obj.modifiers]:
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_remove(modifier="Auto Smooth")
                if "Smooth by Angle" not in [m.name for m in obj.modifiers]:
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_add_node_group(asset_library_type='ESSENTIALS', asset_library_identifier="", relative_asset_identifier="geometry_nodes\\smooth_by_angle.blend\\NodeTree\\Smooth by Angle")
                if "Smooth by Angle" in [m.name for m in obj.modifiers]:
                    bpy.context.view_layer.objects.active = obj
                    if self.move_to_bottom:
                        if obj.modifiers[-1].name != "Smooth by Angle":
                            bpy.ops.object.modifier_move_to_index(modifier="Smooth by Angle", index=len(obj.modifiers) - 1)
                    bpy.context.object.modifiers["Smooth by Angle"]["Input_1"] = self.angle
                    bpy.context.object.modifiers["Smooth by Angle"]["Socket_1"] = self.ignore_sharp
                    bpy.data.node_groups["Smooth by Angle"].interface.items_tree[2].subtype = 'ANGLE'

            for obj in selected_objects:
                add_smooth_modifier(obj)
                 
        else:
            def remove_smooth_modifier(obj):
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_remove(modifier="Smooth by Angle")
                    # ob = bpy.data.objects.get(obj.name)
                    # auto_smooth = [mod for mod in ob.modifiers if mod.name == "Smooth by Angle"]
                    # if auto_smooth:
                    #     ob.modifiers.remove(auto_smooth[-1])

            for obj in selected_objects:
                if "Smooth by Angle" in [m.name for m in obj.modifiers]:
                    remove_smooth_modifier(obj)                  

        bpy.context.view_layer.objects.active = active_object
        return {'FINISHED'}
    
    def register():
        bpy.types.VIEW3D_MT_object_context_menu.prepend(draw_menu)
    def unregister():
        bpy.types.VIEW3D_MT_object_context_menu.remove(draw_menu)

def draw_menu(self, context):
    layout = self.layout
    layout.operator(AutoSmooth.bl_idname, text="Auto Smooth")