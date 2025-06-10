import bpy
from bpy.app.handlers import persistent

is_transforming = False
was_transforming = False
booleon_cutter_info_dict = {}
temp_cutter_clones = []
obj_to_delete = []

def reset_globals():
    global is_transforming, was_transforming, booleon_cutter_info_dict, temp_cutter_clones
    is_transforming = False
    was_transforming = False
    booleon_cutter_info_dict = {}
    temp_cutter_clones = []

def create_copy_of_cutter_object(cutting_object):
    c = bpy.context
    # depsgraph = c.evaluated_depsgraph_get()
    # cutting_object_eval = cutting_object.evaluated_get(depsgraph)
    # new_cutter = cutting_object_eval.copy()
    # new_cutter.data = cutting_object_eval.data.copy()
    new_cutter = cutting_object.copy()
    new_cutter.data = cutting_object.data.copy()
    c.collection.objects.link(new_cutter)
    
    new_cutter.name = "temp_boolean_cutter_" + cutting_object.name

    # hide all modifiers
    # for mod in new_cutter.modifiers:
    #     mod.show_viewport = False
    #     mod.show_render = False
    return new_cutter

def find_boolean_relationships():
    c = bpy.context
    selected_objects = set(c.selected_objects)  # Use a set for O(1) lookups, also de-duplicates duplicates (not that it matters in this case, but I want to remember to it for the future)
    if not selected_objects:
        return

    boolean_links = {}

    objects_with_modifiers = [obj for obj in c.scene.objects if obj.modifiers]

    for obj in objects_with_modifiers:
        for mod in obj.modifiers:
            # Check if the modifier is a Boolean modifier and references a selected object
            if mod.type == 'BOOLEAN' and mod.object in selected_objects:
                cutting_object = mod.object
                boolean_links.setdefault(cutting_object, []).append({
                    'target_object': obj,
                    'modifier': mod
                })

    return boolean_links

    # Print results
    # for cutting_object, links in boolean_links.items():
    #     print(f"Boolean Object: {cutting_object.name}")
    #     for link in links:
    #         print(f"  Cuts Into: {link['target_object']}, Modifier: {link['modifier']}")


def faster_objs_delete(objs): # deleting objects in Blender is crazy slow by deafult, this is a faster way to do it
    for obj in objs:
        for collection in obj.users_collection:
            collection.objects.unlink(obj)

def is_current_running_modal_transform_none_live_booleans(dummy1, dummy2):
    global is_transforming, was_transforming, booleon_cutter_info_dict, temp_cutter_clones, obj_to_delete
    c = bpy.context
    is_transforming = False

    if c.mode == 'OBJECT':
        selected = c.selected_objects
        if selected:
            wm = c.window_manager

            for window in wm.windows:
                for op in window.modal_operators:
                    op_prefix = op.bl_idname.split("_OT_")
            
                    if "TRANSFORM" in op_prefix:
                        if hasattr(op, 'cursor_transform') and op.cursor_transform:
                            continue
                        is_transforming = True
                        break

            if is_transforming: 
                if not booleon_cutter_info_dict: # gizmo only
                    booleon_cutter_info_dict = find_boolean_relationships()
                
                    for cutting_object, links in booleon_cutter_info_dict.items():
                        for link in links:
                            if link['modifier'].object:
                                link['modifier'].object = None

                # selected_objects_names = [obj.name for obj in selected]
                # print("Transforming: " + str(selected_objects_names))
            elif was_transforming and not is_transforming:
                # print("Stopped transforming")
                if not temp_cutter_clones: # gizmo only
                    for cutting_object, links in booleon_cutter_info_dict.items():
                        for link in links:
                            if link['modifier'].object != cutting_object:
                                link['modifier'].object = cutting_object
                else:
                    iteration = -1
                    for cutting_object, links in booleon_cutter_info_dict.items():
                        iteration += 1
                        for link in links:
                            cutting_object.hide_set(False)
                            cutting_object.select_set(True)

                            # copy the location, rotation and scale of the cutter object to the boolean object
                            cutting_object.location = temp_cutter_clones[iteration].location
                            cutting_object.rotation_euler = temp_cutter_clones[iteration].rotation_euler
                            cutting_object.scale = temp_cutter_clones[iteration].scale
                    # remove the temp cutter clones, too slow in bigger scenes, just let Blender handle the unused data instead
                    # for new_cutter in temp_cutter_clones:
                        # get new_cutter mesh data from the object
                        # new_cutter_mesh = new_cutter.data
                        # bpy.data.objects.remove(new_cutter)
                        # bpy.data.meshes.remove(new_cutter_mesh)

                    for new_cutter in temp_cutter_clones:
                        obj_to_delete.append(new_cutter.name)

                    faster_objs_delete(temp_cutter_clones)

                booleon_cutter_info_dict = {}
                temp_cutter_clones = []

            was_transforming = is_transforming

def restore_boolean_modifiers():
    """Restore Boolean modifier object references after undo/redo."""
    global booleon_cutter_info_dict
    for cutting_object, links in booleon_cutter_info_dict.items():
        for link in links:
            if link['modifier'].object is None:
                link['modifier'].object = cutting_object

def delete_temp_objs_on_redo_undo(dummy1, dummy2): # need to do this since the bpy.opps.transform.translate() creates a undo step where the temp objects still exist
    import time
    exec_time = time.time()
    global obj_to_delete
    all_objects = bpy.data.objects

    objects_to_delete = [all_objects[obj_name] for obj_name in obj_to_delete if obj_name in all_objects]

    faster_objs_delete(objects_to_delete)

    for obj in objects_to_delete:
        cutter_name = obj.name.replace("temp_boolean_cutter_", "")
        if cutter_name in all_objects:
            cutter = bpy.data.objects[cutter_name]
            if cutter.name in bpy.context.view_layer.objects:
                cutter.hide_set(False)
                cutter.select_set(True)
   
    # refresh viewport the object someitmes does not translate to the correct location at first undo/redo due to it being in the last captured undo step in that lcoation before the temp objects took over
    # bpy.ops.transform.translate(value=(0, 0, 0), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', mirror=False, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False, snap_elements={'GRID', 'VERTEX', 'FACE'}, use_snap_project=False, snap_target='CLOSEST', use_snap_self=True, use_snap_edit=True, use_snap_nonedit=True, use_snap_selectable=False)
    # print("Deleted temp objects in: " + str(time.time() - exec_time) + " seconds")

# We need to detect if the user presses G, R, S, to invoke a transform operator, to skip any initial lag spikes due to recalculations of the modifiers.
# Seems like the only way to get over the first lag spike when transforming. RIP Gizmo users, I guess.
class ENTERING_TRANSFORM_OT_None_Live_Booleans(bpy.types.Operator):
    bl_idname = "transform.entering_transform_none_live_booleans"
    bl_label = "Entering Transform"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        # bpy.ops.ed.undo_push()
        # print("Entering Transform")
        if bpy.context.selected_objects:
            global booleon_cutter_info_dict, temp_cutter_clones
            booleon_cutter_info_dict = find_boolean_relationships()
            
            for cutting_object, links in booleon_cutter_info_dict.items():
                for link in links:
                    # hide the cutter object
                    cutting_object.hide_set(True)
                    cutting_object.select_set(False)
                    
                    # create a copy of the cutter object
                    new_cutter = create_copy_of_cutter_object(cutting_object)
                    new_cutter.select_set(True)
                    temp_cutter_clones.append(new_cutter)
        return {'PASS_THROUGH'}

    def register():
        # add the keymap
        wm = bpy.context.window_manager
        km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type='EMPTY')
        kmi = km.keymap_items.new(ENTERING_TRANSFORM_OT_None_Live_Booleans.bl_idname, type='G', value='PRESS', shift=False, ctrl=False, alt=False, oskey=False)
        kmi = km.keymap_items.new(ENTERING_TRANSFORM_OT_None_Live_Booleans.bl_idname, type='R', value='PRESS', shift=False, ctrl=False, alt=False, oskey=False)
        kmi = km.keymap_items.new(ENTERING_TRANSFORM_OT_None_Live_Booleans.bl_idname, type='S', value='PRESS', shift=False, ctrl=False, alt=False, oskey=False)

        handlers = [
            (bpy.app.handlers.depsgraph_update_pre, is_current_running_modal_transform_none_live_booleans),
            (bpy.app.handlers.load_post, unregister_none_live_booleans),
            (bpy.app.handlers.undo_post, delete_temp_objs_on_redo_undo),
            (bpy.app.handlers.redo_post, delete_temp_objs_on_redo_undo)]

        for handler_list, handler in handlers:
            if handler not in handler_list:
                handler_list.append(handler)

    def unregister():
        handlers = [
            (bpy.app.handlers.depsgraph_update_pre, is_current_running_modal_transform_none_live_booleans),
            (bpy.app.handlers.load_post, unregister_none_live_booleans),
            (bpy.app.handlers.undo_post, delete_temp_objs_on_redo_undo),
            (bpy.app.handlers.redo_post, delete_temp_objs_on_redo_undo)]
        
        for handler_list, handler in handlers:
            if handler in handler_list:
                handler_list.remove(handler)

        # remove the keymap
        wm = bpy.context.window_manager
        km = wm.keyconfigs.addon.keymaps['Object Mode']

        for kmi in km.keymap_items:
            if kmi.idname == ENTERING_TRANSFORM_OT_None_Live_Booleans.bl_idname:
                km.keymap_items.remove(kmi)

        reset_globals()
    

@persistent
def unregister_none_live_booleans(dummy, dummy2):
    try:
        bpy.utils.unregister_class(ENTERING_TRANSFORM_OT_None_Live_Booleans)
    except:
        pass
