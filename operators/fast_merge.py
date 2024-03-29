import bpy.types
import bmesh
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
from ..utils.pref_utils import get_keyops_prefs

def find_nearest_visible_vertex_to_mouse(context, mouse_position, vertices, matrix_world):
    def is_vertex_visible(vertex):
        world_position = matrix_world @ vertex.co
        screen_pos = location_3d_to_region_2d(context.region, context.space_data.region_3d, world_position)
        return screen_pos is not None

    def distance_to_mouse(vertex):
        world_position = matrix_world @ vertex.co
        screen_pos = location_3d_to_region_2d(context.region, context.space_data.region_3d, world_position)
        return (mouse_position - screen_pos).length if screen_pos else float('inf')

    return min(filter(is_vertex_visible, vertices), key=distance_to_mouse)


class FastMerge(bpy.types.Operator):
    bl_idname = "keyops.fast_merge"
    bl_label = "Fast Merge"
    bl_description = "Fast Merge"
    bl_options = {'REGISTER', 'UNDO'}
    
    preserve_uvs: bpy.props.BoolProperty(name="Preserve UVs", description="Try Preserve UVs (Slow)", default=False) # type: ignore
    prefs = get_keyops_prefs()
    mouse_position = Vector((0, 0))

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.scene.tool_settings.mesh_select_mode[0]

    def invoke(self, context, event):
        self.mouse_position[0] = event.mouse_region_x
        self.mouse_position[1] = event.mouse_region_y
        return self.execute(context)

    def draw(self, context):
        if len(self.selected_verts) != 1:
            self.layout.prop(self, "preserve_uvs")

    def execute(self, context):
        bm = bmesh.from_edit_mesh(context.active_object.data)
        selected_verts = [vert for vert in bm.verts if vert.select]
        def merge(self, context, bm=bm, selected_verts=selected_verts):
            if len(selected_verts) == 1 or self.prefs.fast_merge_last:
                obj = context.object
                matrix_world = obj.matrix_world.copy()
                bm = bmesh.from_edit_mesh(obj.data)
                vertices = []

                for vert in selected_verts:
                    vertices.extend(edge.other_vert(vert) for edge in vert.link_edges)

                vertices += selected_verts
                vertices = list(set(vertices))
                nearest_vertex = find_nearest_visible_vertex_to_mouse(context, self.mouse_position, vertices, matrix_world)

                if nearest_vertex:
                    if nearest_vertex not in selected_verts:
                        selected_verts.append(nearest_vertex)

                    if self.preserve_uvs:
                        uv_layer = bm.loops.layers.uv.active
                        #fixes error in some very rare cases, but might not be worth the potential performance hit
                        if nearest_vertex.link_loops:
                            for vert in selected_verts:
                                for loop in vert.link_loops:
                                    if loop[uv_layer] and nearest_vertex.link_loops[0][uv_layer]:
                                        loop[uv_layer].uv = nearest_vertex.link_loops[0][uv_layer].uv
                                    
                        bmesh.ops.pointmerge(bm, verts=selected_verts, merge_co=nearest_vertex.co)
                        bmesh.update_edit_mesh(obj.data)
                    else:
                        bmesh.ops.pointmerge(bm, verts=selected_verts, merge_co=nearest_vertex.co)
                        bmesh.update_edit_mesh(obj.data)

                return {'FINISHED'}
                
            else:
                selected_history = bm.select_history.active
                active_edge = selected_history if selected_history in selected_verts else []

                if active_edge:
                    if self.preserve_uvs:
                        bpy.ops.mesh.merge(uvs=True, type='LAST')
                    else:
                        bpy.ops.mesh.merge(type='LAST')
                else:
                    self.report({'WARNING'}, "No Active Vertex to Merge to")

        if self.prefs.fast_merge_soft_limit == "no_limit":  
            merge(self, context, bm, selected_verts)
        elif self.prefs.fast_merge_soft_limit == "max_polycount":
            if self.prefs.fast_merge_polycount >= len(selected_verts):
                merge(self, context, bm, selected_verts)
            else:
                self.report({'WARNING'}, "Too many vertices selected")
        elif self.prefs.fast_merge_soft_limit == "all_selected":
            if len(selected_verts) == len(bm.verts):
                self.report({'WARNING'}, "All vertices are selected")
            else:
                merge(self, context, bm, selected_verts)
        elif self.prefs.fast_merge_soft_limit == "max_limit_&_all_selected":
            if len(selected_verts) == len(bm.verts) and self.prefs.fast_merge_polycount < len(selected_verts):
                self.report({'WARNING'}, "All vertices are selected")
            elif self.prefs.fast_merge_polycount >= len(selected_verts):
                merge(self, context, bm, selected_verts)
            else:
                self.report({'WARNING'}, "Too many vertices selected")
            
        return {'FINISHED'}
