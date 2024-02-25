import bpy

#todo:
#autofind booleons
#new cutter collection?
#custom name
#auto remove remesh and smooth?
#Auto remove small bevelse?

class UniqueCollectionDuplicate(bpy.types.Operator):
    bl_label = "Unique Collection Duplicate"
    bl_idname = "keyops.unique_collection_duplicate"
    bl_description = "Make a copy of the current collection and makes all the booleons unqiue if the booleons are selected"
    bl_options = {'REGISTER', 'UNDO'}

    default_name = ""

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            return [obj for obj in context.selected_objects]
            
    def execute(self, context):

        if bpy.data.collections.get("high"):
            self.default_name = "low"
        else:
            self.default_name = "high"
    
        bpy.ops.object.duplicate()
        bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name=self.default_name)

        objects_to_duplicate = [obj for obj in context.selected_objects if obj.data and obj.data.users > 1]

        for obj in objects_to_duplicate:

            obj.data = obj.data.copy()

            booleans = [mod for mod in obj.modifiers if mod.type == 'BOOLEAN' and mod.object and mod.object.data.users > 1]

            for mod in booleans:
                mod.object.data = mod.object.data.copy()

        return {'FINISHED'}
