import bpy.types

class OriginToSelection(bpy.types.Operator):
    bl_description = "Set the origin of the selected object to the center of its geometry or selection"
    bl_idname = "keyops.origin_to_selection"
    bl_label = "Origin to Selection"
    bl_options = { 'UNDO', 'INTERNAL'}

    type: bpy.props.StringProperty(name='Type') # type:ignore
    
    def execute(self, context):
        if self.type == "origin_to_geometry":
            if context.mode == 'OBJECT':
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
                
            elif context.mode == 'EDIT_MESH':
                cursor_loc = context.scene.cursor.location
                pos2 = (cursor_loc[0], cursor_loc[1], cursor_loc[2])

                bpy.ops.view3d.snap_cursor_to_selected()
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                bpy.ops.object.editmode_toggle()

                context.scene.cursor.location = (pos2[0], pos2[1], pos2[2])
        elif self.type == "origin_to_3d_cursor":
            if context.mode == 'OBJECT':
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
            elif context.mode == 'EDIT_MESH':
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                bpy.ops.object.editmode_toggle()
            
        return {'FINISHED'}

