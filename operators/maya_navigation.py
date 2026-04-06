import bpy.types
from ..utils.pref_utils import get_keyops_prefs
from ..utils.utilities import add_shortcuts, set_shortcuts_active, remove_shortcuts

sculpt_mask = [
    ('Sculpt', 'sculpt.brush_stroke', 'LEFTMOUSE', 'PRESS', {'alt': True}),
    ('Sculpt', 'sculpt.brush_stroke', 'LEFTMOUSE', 'PRESS',{'ctrl': True, 'alt': True}),]

sculpt_navigation = [
    ('Sculpt', 'keyops.maya_navigation', 'LEFTMOUSE', 'CLICK_DRAG', {'alt': True}),
    ('Sculpt', 'keyops.maya_navigation', 'LEFTMOUSE', 'CLICK_DRAG',{'ctrl': True, 'alt': True}),]

tablet_keymap_config = [
    ('3D View', 'view3d.zoom', 'LEFTMOUSE', 'CLICK_DRAG', {'ctrl': True, 'alt': True}),
    ('3D View', 'view3d.move', 'LEFTMOUSE', 'CLICK_DRAG', {'alt': True, 'shift': True}),
    ('View2D', 'view2d.pan', 'LEFTMOUSE', 'CLICK_DRAG', {'alt': True}),
    ('View2D', 'view2d.zoom', 'LEFTMOUSE', 'CLICK_DRAG', {'ctrl': True, 'alt': True}),
    ('View2D', 'view2d.pan', 'LEFTMOUSE', 'PRESS', {'alt': True, 'shift': True}),
    ('View2D Buttons List', 'view2d.pan', 'LEFTMOUSE', 'PRESS', {'alt': True}),
    ('Image', 'image.view_zoom', 'LEFTMOUSE', 'PRESS', {'ctrl': True, 'alt': True}),
    ('Image', 'image.view_pan', 'LEFTMOUSE', 'PRESS', {'alt': True, 'shift': True}),
    ('Image', 'image.view_pan', 'LEFTMOUSE', 'PRESS', {'alt': True}),
]

def add_sculpt_shortcuts():
        add_shortcuts(sculpt_navigation)
        add_shortcuts(sculpt_navigation)
        set_shortcuts_active(sculpt_mask, set=False)


def update_tablet_navigation(self, context):
    if self.maya_navigation_tablet_navigation:
        add_shortcuts(tablet_keymap_config)
    else:
        remove_shortcuts(tablet_keymap_config)

def update_sculpt_navigation(self, context):
    if self.maya_navigation_sculpt_navigation:
        add_sculpt_shortcuts()
    else:
        remove_shortcuts(sculpt_navigation)
        set_shortcuts_active(sculpt_mask, set=True)

mask_keymap = None

class MayaNavigation(bpy.types.Operator):
    bl_idname = "keyops.maya_navigation"
    bl_label = "KeyOps: Maya Navigation Sculpt"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        prefs = get_keyops_prefs()
        return bpy.app.version >= (5, 1, 0) and context.mode == "SCULPT" and prefs.maya_navigation_sculpt_navigation

    def invoke(self, context, event):
        for km in bpy.context.window_manager.keyconfigs.user.keymaps:
            for kmi in km.keymap_items:
                if kmi.name == "Sculpt":
                    if kmi.idname == "sculpt.brush_stroke" and kmi.alt == True and kmi.ctrl == False:
                        mask_keymap = kmi
                        break

        if mask_keymap:
            from bpy_extras import view3d_utils 
            scene = context.scene
            region = context.region
            rv3d = context.region_data
            coord = event.mouse_region_x, event.mouse_region_y
            viewlayer = context.view_layer.depsgraph
            # get the ray from the viewport and mouse
            view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
            ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)

            hit, location, normal, index, object, matrix = scene.ray_cast(viewlayer, ray_origin, view_vector)

            if hit and object and object == context.object:
                if not event.ctrl:
                    result = bpy.ops.sculpt.brush_stroke('INVOKE_DEFAULT', brush_toggle="MASK")
                else:
                    result = bpy.ops.sculpt.brush_stroke('INVOKE_DEFAULT', mode="INVERT", brush_toggle="MASK")
                if result == {'RUNNING_MODAL'}:
                    return {'RUNNING_MODAL'}
                return {'FINISHED'}
            else:
                if not event.ctrl:
                    result = bpy.ops.view3d.rotate('INVOKE_DEFAULT')
                else:
                    result = bpy.ops.view3d.zoom('INVOKE_DEFAULT')
                if result == {'RUNNING_MODAL'}:
                    return {'RUNNING_MODAL'}
                return {'FINISHED'}
        return self.execute(context)
    
    def execute(self, context):
        pass
        return {"PASS_THROUGH"}

    def register():
        prefs = get_keyops_prefs()
        if prefs.maya_navigation_tablet_navigation:
            add_shortcuts(tablet_keymap_config)

        if prefs.maya_navigation_sculpt_navigation:
            bpy.app.timers.register(add_sculpt_shortcuts, first_interval=0.1)
        
    def unregister():
        remove_shortcuts(tablet_keymap_config)
        remove_shortcuts(sculpt_navigation)
        set_shortcuts_active(sculpt_mask, set=True)

        