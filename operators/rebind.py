import bpy

#combine to one class

class ContextMenuRebindW(bpy.types.Operator):
    bl_idname = "keyops.rebind_w"
    bl_label = "Context Menu W"

    def execute(self, context):
        for km in bpy.context.window_manager.keyconfigs.user.keymaps:
            for kmi in km.keymap_items:
                if kmi.type == "RIGHTMOUSE":
                    
                    if "Object" in kmi.name and "Context Menu" in kmi.name:
                        km.keymap_items.new("wm.call_menu", "W", "PRESS", shift=False, ctrl=False, alt=False).properties.name = kmi.properties.name
                        km.keymap_items.remove(kmi)
                    elif "Vertex Paint" in kmi.name and "Context Menu" in kmi.name:
                        km.keymap_items.new("wm.call_menu", "W", "PRESS", shift=False, ctrl=False, alt=False).properties.name = kmi.properties.name
                        km.keymap_items.remove(kmi)
                    # elif "Node" in kmi.name and "Context Menu" in kmi.name:
                    #     km.keymap_items.new("wm.call_menu", "W", "PRESS", shift=False, ctrl=False, alt=False).properties.name = kmi.properties.name
                    #     km.keymap_items.remove(kmi)
                    elif "Curve" in kmi.name and "Context Menu" in kmi.name:
                        km.keymap_items.new("wm.call_menu", "W", "PRESS", shift=False, ctrl=False, alt=False).properties.name = kmi.properties.name
                        km.keymap_items.remove(kmi)
                    elif "Lattice" in kmi.name and "Context Menu" in kmi.name:
                        km.keymap_items.new("wm.call_menu", "W", "PRESS", shift=False, ctrl=False, alt=False).properties.name = kmi.properties.name
                        km.keymap_items.remove(kmi)
                    elif kmi.name == "Call Menu" and kmi.properties.name == "VIEW3D_MT_edit_mesh_context_menu":
                        km.keymap_items.new("wm.call_menu", "W", "PRESS", shift=False, ctrl=False, alt=False).properties.name = kmi.properties.name
                        km.keymap_items.remove(kmi)
                    # elif kmi.name == "Outliner Context Menu" and kmi.properties.name == "OUTLINER_MT_context_menu":
                    #     km.keymap_items.new("wm.call_menu", "W", "PRESS", shift=False, ctrl=False, alt=False).properties.name = kmi.properties.name
                    #     km.keymap_items.remove(kmi)
                    # elif kmi.name == "Outliner" and "Context Menu" in kmi.name:
                    #     km.keymap_items.new("wm.call_menu", "W", "PRESS", shift=False, ctrl=False, alt=False).properties.name = kmi.properties.name
                    #     km.keymap_items.remove(kmi)

        return {'FINISHED'}

class ContextMenuRebindRightClick(bpy.types.Operator):
    bl_idname = "keyops.rebind_rightclick"
    bl_label = "Context Menu Rightclick"

    def execute(self, context):
        for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
            for keymap_item in keymap.keymap_items:
                if keymap_item.name == "Call Menu" and keymap_item.properties.name == "VIEW3D_MT_edit_mesh_context_menu":
                    keymap_item.type = "RIGHTMOUSE"
                elif "Context Menu" in keymap_item.name:
                    if "Object" in keymap_item.name and keymap_item.type == "W":
                        keymap_item.type = "RIGHTMOUSE"
                    elif "Vertex Paint" in keymap_item.name and keymap_item.type == "W":
                        keymap_item.type = "RIGHTMOUSE"
                    #need to rebind switch tool as well! 
                    # elif "Node" in keymap_item.name and keymap_item.type == "W":
                    #     keymap_item.type = "RIGHTMOUSE"
                    elif "Curve" in keymap_item.name and keymap_item.type == "W":
                        keymap_item.type = "RIGHTMOUSE"
                    elif "Lattice" in keymap_item.name and keymap_item.type == "W":
                        keymap_item.type = "RIGHTMOUSE"
                    # elif "Outliner Context Menu" in keymap_item.name and keymap_item.type == "W":
                    #     keymap_item.type = "RIGHTMOUSE"
        
        return {'FINISHED'}


class AddObjectPieRebindShiftA(bpy.types.Operator):
    bl_idname = "keyops.add_object_pie_rebind"
    bl_label = "KeyOps: Add Object Pie Rebind Shift A"
    bl_description = "Rebind Add Object Pie to Shift A"

    type: bpy.props.StringProperty(default="") # type: ignore
    
    def execute(self, context):
        if self.type == "Add Object Pie Rebind Shift A":
            for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                for keymap_item in keymap.keymap_items:
                    if keymap_item.name == "Mesh" and keymap_item.type == "A" and keymap_item.shift:
                        keymap_item.alt = True
                    if keymap_item.name == "Add Mesh Pie" and keymap_item.type == "A" and keymap_item.shift and keymap_item.alt:
                        keymap_item.alt = False

                    if keymap.name == "Object Mode":
                            for keymap_item in keymap.keymap_items:
                                if keymap_item.name == "Add" and keymap_item.type == "A" and keymap_item.shift:
                                    keymap_item.alt = True

        elif self.type == "Add Object Pie Rebind Shift Alt A":
            for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                for keymap_item in keymap.keymap_items:
                    if keymap_item.name == "Mesh" and keymap_item.type == "A" and keymap_item.shift and keymap_item.alt:
                        keymap_item.alt = False
                    if keymap_item.name == "Add Mesh Pie" and keymap_item.type == "A" and keymap_item.shift:
                        keymap_item.alt = True

                    if keymap.name == "Object Mode":
                            for keymap_item in keymap.keymap_items:
                                if keymap_item.name == "Add" and keymap_item.type == "A" and keymap_item.shift and keymap_item.alt:
                                    keymap_item.alt = False
        return {'FINISHED'}
    
class SpaceToViewPieShift(bpy.types.Operator):
    bl_idname = "keyops.space_to_view_camera_pie"
    bl_label = "KeyOps: Space to View Camera Pie"
    bl_description = "Rebinds View Camera Pie to Space"

    type: bpy.props.StringProperty(default="") # type: ignore

    def execute(self, context):
        if self.type == "Space To View Camera Pie Shift":
            for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                for keymap_item in keymap.keymap_items:
                    if keymap_item.name == "Play Animation" and keymap_item.type == "SPACE" and keymap_item.shift==False:
                        keymap_item.shift = True   

            for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                for keymap_item in keymap.keymap_items:
                    if keymap_item.name == "View" and keymap_item.idname == "wm.call_menu_pie":
                        keymap_item.type = "SPACE"

        elif self.type == "Space To View Camera Pie":
            for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                for keymap_item in keymap.keymap_items:
                    if keymap_item.name == "Play Animation" and keymap_item.type == "SPACE" and keymap_item.shift:
                        keymap_item.shift = False  

            for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                for keymap_item in keymap.keymap_items:
                    if keymap_item.name == "View" and keymap_item.idname == "wm.call_menu_pie":
                        keymap_item.type = "ACCENT_GRAVE"
        return {'FINISHED'}


classes = [ContextMenuRebindW, 
        ContextMenuRebindRightClick, 
        AddObjectPieRebindShiftA, 
        SpaceToViewPieShift,
        ]

class Rebind(bpy.types.Operator):
    bl_idname = "keyops.rebind"
    bl_label = "KeyOps: Rebind"
    bl_description = "Move Pivot Key Press"
    bl_options = {'INTERNAL'}

    type: bpy.props.StringProperty(default="") # type: ignore

    def execute(self, context):
        if self.type == "Default_Pie":
            prefs = bpy.context.preferences.view
            prefs.pie_animation_timeout = 6
            prefs.pie_tap_timeout = 20
            prefs.pie_initial_timeout = 0
            prefs.pie_menu_radius = 100
            prefs.pie_menu_threshold = 12
            prefs.pie_menu_confirm = 0
        elif self.type == "No_Lag_Pie":
            prefs = bpy.context.preferences.view
            prefs.pie_animation_timeout = 0
            prefs.pie_tap_timeout = 0
            prefs.pie_initial_timeout = 0
            prefs.pie_menu_radius = 85
            prefs.pie_menu_threshold = 11
            prefs.pie_menu_confirm = 0
        elif self.type == "Remove Select Type Shortcuts":
            for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                for keymap_item in keymap.keymap_items:
                    if keymap_item.name == "Select Mode" and keymap_item.type in ('ONE', 'TWO', 'THREE') and not all([not keymap_item.ctrl, not keymap_item.alt, not keymap_item.shift]):
                        keymap_item.active = False
        elif self.type == "Add Select Type Shortcuts":
            for keymap in bpy.context.window_manager.keyconfigs.user.keymaps:
                for keymap_item in keymap.keymap_items:
                    if keymap_item.name == "Select Mode" and keymap_item.type in ('ONE', 'TWO', 'THREE') and not all([not keymap_item.ctrl, not keymap_item.alt, not keymap_item.shift]):
                        keymap_item.active = True
            
        return {'FINISHED'}
            
    
    def register():
        for cls in classes:
            bpy.utils.register_class(cls)

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
