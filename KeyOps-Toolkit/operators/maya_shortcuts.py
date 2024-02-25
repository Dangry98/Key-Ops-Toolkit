import bpy.types

class MayaShortcuts(bpy.types.Operator):
    bl_idname = "keyops.maya_shortcuts"
    bl_label = "KeyOps: Maya Shortcuts"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return {'FINISHED'}
