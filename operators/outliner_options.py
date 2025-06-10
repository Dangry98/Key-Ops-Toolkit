import bpy
from bpy.app.handlers import persistent

previous_selected_objects = []
clicked_in_outliner = False

def register_outliner_click_keymap(register=True):
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='Outliner', space_type='OUTLINER')
    kmi = km.keymap_items.new('keyops.outliner_click', 'LEFTMOUSE', 'CLICK')
    kmi = km.keymap_items.new('keyops.outliner_click', 'RIGHTMOUSE', 'CLICK')
    kmi.active = True
    kmi = km.keymap_items.new('keyops.outliner_click', 'LEFTMOUSE', 'CLICK', shift=True)
    kmi = km.keymap_items.new('keyops.outliner_click', 'LEFTMOUSE', 'CLICK', ctrl=True)
    kmi = km.keymap_items.new('keyops.outliner_click', 'LEFTMOUSE', 'CLICK', ctrl=True, shift=True)
    kmi = km.keymap_items.new('keyops.outliner_click', 'A', 'PRESS', alt=True)
    kmi = km.keymap_items.new('keyops.outliner_click', 'A', 'PRESS')
    kmi.active = True

    if not register:
        wm.keyconfigs.addon.keymaps.remove(km)

    return km, kmi

def unregister_outliner_click_keymap():
    wm = bpy.context.window_manager
    for km in wm.keyconfigs.addon.keymaps:
        if km.name == 'Outliner':
            if 'keyops.outliner_click' in [k.idname for k in km.keymap_items]:
                wm.keyconfigs.addon.keymaps.remove(km)
                break

# Register the handler after the add-on has loaded if the option is enabled
@persistent
def register_handler(dummy=None, depsgraph=None):
    bpy.app.timers.register(lambda: enabled_selection_options(bpy.context.scene, bpy.context), first_interval=0.3)

def selection_option_handler(dummy, depsgraph):
    global previous_selected_objects
    global clicked_in_outliner
    current_selected_objects = bpy.context.selected_objects
    
    if previous_selected_objects != current_selected_objects:
        previous_selected_objects = current_selected_objects

        if bpy.context.scene.auto_focus_in_outliner or bpy.context.scene.collapse_unselected_collections:
            if not clicked_in_outliner:
                outliner_areas = [a for a in bpy.context.screen.areas if a.type == "OUTLINER"]
                if not outliner_areas:
                    return  # No outliner area found, exit the function
                largest_area = max(outliner_areas, key=lambda a: a.width * a.height)
                largest_region = next(r for r in largest_area.regions if r.type == "WINDOW")

                override_context = {
                    'area': largest_area,
                    'region': largest_region
                }

                with bpy.context.temp_override(**override_context):
                    if bpy.context.scene.collapse_unselected_collections:
                        bpy.ops.outliner.expanded_toggle()
                        bpy.ops.outliner.expanded_toggle()

                    bpy.ops.outliner.show_active()

        def walk_children(ob):
            yield ob
            for child in ob.children:
                yield from walk_children(child)

        if bpy.context.scene.select_children and clicked_in_outliner:
            for obj in current_selected_objects:
                for child in walk_children(obj):
                    child.select_set(True)

    clicked_in_outliner = False

def draw_options_in_outliner(self, context):
    layout = self.layout
    layout.label(text="Selection")
    row = layout.row()
    row.prop(context.scene, 'auto_focus_in_outliner')
    row = layout.row()
    row.prop(context.scene, 'collapse_unselected_collections')
    row = layout.row()
    row.prop(context.scene, 'select_children')

def enabled_selection_options(self, context):
    if self.auto_focus_in_outliner or self.select_children or self.collapse_unselected_collections:
        if selection_option_handler not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(selection_option_handler)
            if not any('keyops.outliner_click' in km.keymap_items for km in bpy.context.window_manager.keyconfigs.addon.keymaps):
                register_outliner_click_keymap()
    else:
        if selection_option_handler in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(selection_option_handler)
            unregister_outliner_click_keymap()

class OutlinerClick(bpy.types.Operator):
    bl_idname = "keyops.outliner_click"
    bl_label = "KeyOps: Outliner Click"
    bl_description = ""
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return (context.scene.auto_focus_in_outliner or 
                context.scene.select_children or 
                context.scene.collapse_unselected_collections)

    def invoke(self, context, event):
        global clicked_in_outliner
        clicked_in_outliner = True
        return {'PASS_THROUGH'}


class OutlinerOptions(bpy.types.Operator):
    bl_idname = "keyops.outliner_options"
    bl_label = "KeyOps: Outliner Options"
    bl_description = ""
    bl_options = {'INTERNAL'}

    def register():
        bpy.utils.register_class(OutlinerClick)
        bpy.types.Scene.auto_focus_in_outliner = bpy.props.BoolProperty(
            name="Auto Select in Outliner",
            description="Automatically focus on the selected objects in the outliner, can be slow with many objects",
            default=False,
            update=enabled_selection_options
        )
        bpy.types.Scene.select_children = bpy.props.BoolProperty(
            name="Select Children",
            description="Automatically select children of selected objects",
            default=False,
            update=enabled_selection_options
        )
        bpy.types.Scene.collapse_unselected_collections = bpy.props.BoolProperty(
            name="Collapse Unselected Collections",
            description="Automatically collapse collections that are not related to the selected objects",
            default=False,
            update=enabled_selection_options
        )
        bpy.types.OUTLINER_PT_filter.prepend(draw_options_in_outliner)
        
        bpy.app.timers.register(register_handler)
        bpy.app.handlers.load_post.append(register_handler)

    def unregister():
        bpy.utils.unregister_class(OutlinerClick)
        if selection_option_handler in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(selection_option_handler)
        
        handlers = [h.__name__ for h in bpy.app.handlers.load_post]
        if 'register_handler' in handlers:
            bpy.app.handlers.load_post.remove(register_handler)
        
        del bpy.types.Scene.auto_focus_in_outliner
        del bpy.types.Scene.select_children
        del bpy.types.Scene.collapse_unselected_collections

        if bpy.types.OUTLINER_PT_filter:
            bpy.types.OUTLINER_PT_filter.remove(draw_options_in_outliner)
        
        unregister_outliner_click_keymap()
