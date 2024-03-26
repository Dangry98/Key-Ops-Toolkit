import bpy

class ExtrudeEdgeAlongNormals(bpy.types.Operator):
    """Extrude selected edges along their normals"""
    bl_idname = "keyops.extrude_edge_along_normals"
    bl_label = "Extrude Edge Along Normals"
    bl_options = {'REGISTER', 'UNDO'}

    amount: bpy.props.FloatProperty(
        name="Amount",
        description="Amount",
        default=0.1,
        min=-100,
        max=100,
        subtype="DISTANCE",
    ) #type: ignore

    def execute(self, context):
        bpy.ops.mesh.offset_edge_loops_slide(MESH_OT_offset_edge_loops={"use_cap_endpoint":False}, TRANSFORM_OT_edge_slide={"value":0.00001, "single_side":True, "use_even":False, "flipped":False, "use_clamp":True, "mirror":True, "snap":False, "snap_elements":{'INCREMENT', 'VERTEX'}, "use_snap_project":False, "snap_target":'CLOSEST', "use_snap_self":True, "use_snap_edit":True, "use_snap_nonedit":True, "use_snap_selectable":False, "snap_point":(0, 0, 0), "correct_uv":True, "release_confirm":False, "use_accurate":False, "alt_navigation":False})
        bpy.ops.mesh.loop_to_region()
        bpy.ops.mesh.loop_multi_select(ring=False)
        bpy.ops.mesh.select_all(action='INVERT')
        bpy.ops.transform.shrink_fatten(value=self.amount, use_even_offset=False, mirror=True, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False)

        return {'FINISHED'}
    
    def register():
        bpy.types.VIEW3D_MT_edit_mesh_extrude.prepend(draw_menu)
    def unregister():
        bpy.types.VIEW3D_MT_edit_mesh_extrude.remove(draw_menu)

def draw_menu(self, context):
    self.layout.operator("keyops.extrude_edge_along_normals")