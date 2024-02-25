import bpy.types

class LegacyShortcuts(bpy.types.Operator):
    bl_idname = "keyops.legacy_shortcuts"
    bl_label = "KeyOps: Legacy Shortcuts"
    bl_description = "Adds Legacy Shortcuts From Blender 2.79x"
    bl_options = {"REGISTER", "UNDO"}
    
