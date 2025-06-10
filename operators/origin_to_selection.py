import bpy.types
from bpy.types import Menu

class OriginToSelection(bpy.types.Operator):
    bl_description = "Set the origin of the selected object to the center of its geometry or selection"
    bl_idname = "keyops.origin_to_selection"
    bl_label = "Origin to Selection"
    bl_options = {'INTERNAL'}

    type: bpy.props.StringProperty(name='Type') # type:ignore
    
    def execute(self, context):
        if self.type == "origin_to_geometry":
            if context.mode == 'OBJECT':
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
                bpy.ops.ed.undo_push()
            elif context.mode == 'EDIT_MESH':
                cursor_loc = context.scene.cursor.location
                pos2 = (cursor_loc[0], cursor_loc[1], cursor_loc[2])

                bpy.ops.view3d.snap_cursor_to_selected()
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                bpy.ops.ed.undo_push() # this works out better before editmode_toggle, otherwise it jumps around a lot in edit mode
                bpy.ops.object.editmode_toggle()
                bpy.ops.ed.undo_push() # makes it so you return to edit mode after the operation on undo

                context.scene.cursor.location = (pos2[0], pos2[1], pos2[2])
        elif self.type == "origin_to_3d_cursor":
            if context.mode == 'OBJECT':
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                bpy.ops.ed.undo_push()
            elif context.mode == 'EDIT_MESH':
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                bpy.ops.ed.undo_push() # this works out better before editmode_toggle, otherwise it jumps around a lot in edit mode
                bpy.ops.object.editmode_toggle()
                bpy.ops.ed.undo_push() # makes it so you return to edit mode after the operation on undo
            
        return {'FINISHED'}
    def register():
        bpy.utils.register_class(CursorPie)
    def unregister():
        bpy.utils.unregister_class(CursorPie)

class CursorPie(Menu):
    bl_idname = "KEYOPS_MT_cursor_pie"
    bl_label = "Cursor Pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        pie.operator("keyops.origin_to_selection", text="Origin to 3D Cursor", icon="LAYER_USED").type= "origin_to_3d_cursor" #LEFT

        pie.operator("keyops.origin_to_selection", text="Origin to Selection", icon="LAYER_USED").type= "origin_to_geometry" #RIGHT

        pie.operator("view3d.snap_cursor_to_selected", text="Cursor to Selection", icon="CURSOR") #BOTTOM

        pie.operator("view3d.snap_selected_to_cursor", text="Selection to Cursor", icon="RESTRICT_SELECT_OFF") #TOP

        pie.operator("view3d.snap_selected_to_grid", text="Selection to Grid", icon="SNAP_GRID") #LEFT TOP
        
        pie.operator('view3d.snap_cursor_to_grid', text="Cursor to Grid", icon="SNAP_GRID") #RIGHT TOP

        pie.operator("view3d.snap_cursor_to_center", text="Cursor to World Origin", icon="PIVOT_CURSOR") #LEFT BOTTOM
        
        pie.operator('view3d.snap_cursor_to_active', text="Cursor to Active", icon="CURSOR") #RIGHT BOTTOM

