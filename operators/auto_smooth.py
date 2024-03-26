import bpy

class AutoSmooth(bpy.types.Operator):
    """Set auto smooth on selected objects"""
    bl_idname = "keyops.auto_smooth"
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

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        active_object = context.active_object
        selected_objects = context.selected_objects

        if "Smooth by Angle" not in bpy.data.node_groups:
            bpy.ops.object.modifier_add_node_group(asset_library_type='ESSENTIALS', asset_library_identifier="", relative_asset_identifier="geometry_nodes\\smooth_by_angle.blend\\NodeTree\\Smooth by Angle")
            active_object = context.active_object
            active_object.modifiers.remove(active_object.modifiers.get("Smooth by Angle"))

        if self.all_instances:
            for obj in context.selected_objects:
                instances = [o for o in bpy.data.objects if o.data == obj.data]
                for inst in instances:
                    if inst not in selected_objects:
                          selected_objects.extend([inst])
              
        if self.auto_smooth:
            def add_smooth_modifier(obj):
                for m in obj.modifiers:
                    if "Auto Smooth" in m.name:
                        if m == obj.modifiers.get("!!Auto Smooth"):
                            pass
                        else:
                            obj.modifiers.remove(m)
                
                if "!!Auto Smooth" in [m.name for m in obj.modifiers]:
                    context.view_layer.objects.active = obj
                    if self.move_to_bottom:
                        if obj.modifiers[-1].name != "!!Auto Smooth":
                            obj.modifiers.move(obj.modifiers.find("!!Auto Smooth"), len(obj.modifiers)-1)
                    context.object.modifiers["!!Auto Smooth"]["Socket_2"] = self.angle
                    context.object.modifiers["!!Auto Smooth"]["Socket_3"] = self.ignore_sharp

                    if "Smooth by Angle" in [m.name for m in obj.modifiers]:
                        obj.modifiers.remove(obj.modifiers.get("Smooth by Angle"))

                elif "Smooth by Angle" not in [m.name for m in obj.modifiers] and "!!Auto Smooth" not in [m.name for m in obj.modifiers]:
                    context.view_layer.objects.active = obj
                    obj.modifiers.new ("Smooth by Angle", 'NODES')
                    context.object.modifiers["Smooth by Angle"].node_group = bpy.data.node_groups["Smooth by Angle"]
                    
                    if self.move_to_bottom:
                        if obj.modifiers[-1].name != "Smooth by Angle":
                            obj.modifiers.move(obj.modifiers.find("Smooth by Angle"), len(obj.modifiers)-1)
                    context.object.modifiers["Smooth by Angle"]["Input_1"] = self.angle
                    context.object.modifiers["Smooth by Angle"]["Socket_1"] = self.ignore_sharp

            for obj in selected_objects:
                add_smooth_modifier(obj)
                 
        else:
            def remove_smooth_modifier(obj):
                context.view_layer.objects.active = obj
                if "!!Auto Smooth" in [m.name for m in obj.modifiers]:
                    obj.modifiers.remove(obj.modifiers.get("!!Auto Smooth"))
                if "Smooth by Angle" in [m.name for m in obj.modifiers]:
                    obj.modifiers.remove(obj.modifiers.get("Smooth by Angle"))
                if "Auto Smooth" in [m.name for m in obj.modifiers]:
                    obj.modifiers.remove(obj.modifiers.get("Auto Smooth"))

            for obj in selected_objects:
                remove_smooth_modifier(obj)       

        #refresh - profile to make sure it's not too slow in big scenes, ideally should be done only once at the first run
        if "Smooth by Angle" in bpy.data.node_groups:
            bpy.data.node_groups["Smooth by Angle"].interface.items_tree[2].subtype = 'ANGLE'
        if "Auto Smooth" in bpy.data.node_groups:
            bpy.data.node_groups["Auto Smooth"].interface.items_tree[2].subtype = 'ANGLE'

        context.view_layer.objects.active = active_object
        return {'FINISHED'}
    
    def register():
        bpy.types.VIEW3D_MT_object_context_menu.prepend(draw_menu)
    def unregister():
        bpy.types.VIEW3D_MT_object_context_menu.remove(draw_menu)

def draw_menu(self, context):
    if context.active_object is not None:
        layout = self.layout
        layout.operator(AutoSmooth.bl_idname, text="Auto Smooth")