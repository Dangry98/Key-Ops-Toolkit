import bpy.types

class MayaNavigation(bpy.types.Operator):
    bl_idname = "keyops.maya_navigation"
    bl_label = "KeyOps: Maya Navigation"
    bl_options = {'REGISTER', 'UNDO'}