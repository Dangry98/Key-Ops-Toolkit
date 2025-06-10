import bpy

def force_show_obj(context, obj, select=True):
    """
    Force show the object in the viewport, even if the collection is hidden.
    """
    obj_collection = obj.users_collection[0]

    if obj_collection.hide_viewport == True or context.view_layer.layer_collection.children[obj_collection.name].hide_viewport == True:
        obj_collection.hide_viewport = False
        context.view_layer.layer_collection.children[obj_collection.name].hide_viewport = False
        for obj in obj_collection.objects:
            if not obj.hide_get():
                obj.hide_set(True)

    obj.hide_set(False)
    obj.hide_viewport = False
    if select:
        obj.select_set(True)
        context.view_layer.objects.active = obj