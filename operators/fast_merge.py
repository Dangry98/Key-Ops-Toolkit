import bpy.types
import bmesh
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
from ..utils.pref_utils import get_keyops_prefs
from ..utils.pref_utils import get_is_addon_enabled

has_clicked_once = None
half_knife = None

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
    
    preserve_uvs: bpy.props.BoolProperty(name="Preserve UVs", description="Try Preserve UVs (Slower and does not always work)", default=False) # type: ignore
    prefs = get_keyops_prefs()
    mouse_position = Vector((0, 0))
    draw_preserve_uvs = False

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.scene.tool_settings.mesh_select_mode[0]

    def invoke(self, context, event):
        self.mouse_position[0] = event.mouse_region_x
        self.mouse_position[1] = event.mouse_region_y
        return self.execute(context)

    def draw(self, context):
        self.layout.prop(self, "preserve_uvs")

    def execute(self, context):
        bm = bmesh.from_edit_mesh(context.active_object.data)
        selected_verts = [vert for vert in bm.verts if vert.select]
        global has_clicked_once 
        active_vert = bm.select_history.active
    
        def merge(self, context, bm=bm, selected_verts=selected_verts):
            active_vert = bm.select_history.active
            if not selected_verts == None:
                if len(selected_verts) == 0:
                    self.report({'WARNING'}, "No vertices selected")
                    return {'FINISHED'}
            if len(selected_verts) == 1 and self.prefs.fast_merge_merge_options == "only merge if active or only 1 verts is selected" or self.prefs.fast_merge_merge_options == "always merge to nearest vert" or self.prefs.fast_merge_merge_options == "merge to nerest vert if no active" and active_vert == None or len(selected_verts) == 1:
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
                        if uv_layer and nearest_vertex.link_loops:
                            for vert in selected_verts:
                                for loop in vert.link_loops:
                                    if loop[uv_layer] and nearest_vertex.link_loops[0][uv_layer]:
                                        loop[uv_layer].uv = nearest_vertex.link_loops[0][uv_layer].uv
                                    
                        bmesh.ops.pointmerge(bm, verts=selected_verts, merge_co=nearest_vertex.co)
                        bmesh.update_edit_mesh(obj.data)
                    else:
                        bmesh.ops.pointmerge(bm, verts=selected_verts, merge_co=nearest_vertex.co)
                        bmesh.update_edit_mesh(obj.data)
                        
                    self.report({'INFO'}, "Merged %d vertices" % (len(selected_verts) - 1))
                return {'FINISHED'}
            
            else:
                selected_history = bm.select_history.active
                active_vert = selected_history if selected_history in selected_verts else []

                if active_vert:
                    if self.preserve_uvs:
                        amount_of_verts_merged = len(selected_verts)
                        bpy.ops.mesh.merge(uvs=True, type='LAST')
                    else:
                        amount_of_verts_merged = len(selected_verts)
                        bmesh.ops.pointmerge(bm, verts=selected_verts, merge_co=active_vert.co)
                        bmesh.update_edit_mesh(context.active_object.data)
                        
                    self.report({'INFO'}, "Merged %d vertices" % (amount_of_verts_merged - 1))

                else:
                    self.report({'WARNING'}, "No Active Vertex to Merge to")

        if self.prefs.fast_merge_soft_limit == "no_limit":  
            merge(self, context, bm, selected_verts)

        elif self.prefs.fast_merge_soft_limit == "max_polycount":
            if self.prefs.fast_merge_polycount >= len(selected_verts):
                merge(self, context, bm, selected_verts)
            else:
                self.report({'WARNING'}, "Limit - Too many vertices selected")
        elif self.prefs.fast_merge_soft_limit == "all_selected":
            if len(selected_verts) == len(bm.verts):
                self.report({'WARNING'}, "Limit - All vertices are selected")
            else:
                merge(self, context, bm, selected_verts)

        elif self.prefs.fast_merge_soft_limit == "max_limit_&_all_selected":
            if len(selected_verts) == len(bm.verts) and self.prefs.fast_merge_polycount < len(selected_verts):
                self.report({'WARNING'}, "Limit - All vertices are selected and too many vertices selected")
            elif self.prefs.fast_merge_polycount >= len(selected_verts):
                merge(self, context, bm, selected_verts)
            else:
                self.report({'WARNING'}, "Limit - Too many vertices selected")

        elif self.prefs.fast_merge_soft_limit == "ask_if_no_active_vert":
            if active_vert == None:
                if has_clicked_once == None:
                    has_clicked_once = True
                    if not self.prefs.fast_merge_merge_options == "only merge if active or only 1 verts is selected":
                        self.report({'WARNING'}, "Limit - Press again to merge to nearest vertex")
                    return {'FINISHED'}
                else:
                    has_clicked_once = None
                    merge(self, context, bm, selected_verts)
                    current_selected_verts = [vert for vert in bm.verts if vert.select]
                    if len(current_selected_verts) > 0:
                        bm.select_history.add(current_selected_verts[0])
            else:
                merge(self, context, bm, selected_verts)
            
        has_clicked_once = None
            
        return {'FINISHED'}
    def register():
        bpy.utils.register_class(FastConnect)
        bpy.utils.register_class(Connect)
        #bpy.utils.register_class(FastKnife)

    def unregister():
        bpy.utils.unregister_class(FastConnect)
        bpy.utils.unregister_class(Connect)
        #bpy.utils.unregister_class(FastKnife)

class FastKnife(bpy.types.Operator):
    bl_idname = 'mesh.fast_knife'
    bl_label = 'FastKnife'
    bl_options = {'REGISTER', 'UNDO'}
    
    mouse_position = Vector((0, 0))

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'
    
    def invoke(self, context, event):
        self.mouse_position[0] = event.mouse_region_x
        self.mouse_position[1] = event.mouse_region_y
        return self.execute(context)

    def execute(self, context):

            
        obj = context.edit_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)



        def dissolve_redundant_edges(bm, vert, excluded_verts = []):
            dissolved_edges = []
            l = len(vert.link_edges)
            for e in vert.link_edges:
                if not e.other_vert(vert) in excluded_verts and l > 2:
                    dissolved_edges.append(e)
                    l -= 1
            bmesh.ops.dissolve_edges(bm, edges = dissolved_edges, use_verts = False, use_face_split = False)


        def addVertOnFace(self, co, face):
            vert = bmesh.ops.poke(self.bmesh, faces=[face])['verts'][0]
            vert.co = co
            dissolve_redundant_edges(self.bmesh, vert)
            return vert

        def addVertOnEdge(self, co, edge):
            edge, vert = bmesh.utils.edge_split(edge, edge.verts[0], .5)
            vert.co = co
            return vert
        
        
        def find_closest_edge_or_face_or_vert_to_mouse(self, context, mouse_position, bm):
            obj = context.object
            matrix_world = obj.matrix_world.copy()
            vertices = [v for v in bm.verts if v.select]
            edges = [e for e in bm.edges if e.select]
            faces = [f for f in bm.faces if f.select]

            def distance_to_mouse(element):
                world_position = matrix_world @ element.calc_center_median()
                screen_pos = location_3d_to_region_2d(context.region, context.space_data.region_3d, world_position)
                return (mouse_position - screen_pos).length if screen_pos else float('inf')

            closest_element = min(vertices + edges + faces, key=distance_to_mouse)
            return closest_element
        
        #finds the closest edge or face or vert to the mouse and then decides if it should add a vert on edge ot add vert on face
        closest_element = find_closest_edge_or_face_or_vert_to_mouse(self, context, self.mouse_position, bm)
        
        if isinstance(closest_element, bmesh.types.BMVert):
            addVertOnEdge(self, closest_element.co, closest_element.link_edges[0])
        elif isinstance(closest_element, bmesh.types.BMEdge):
            addVertOnEdge(self, closest_element.verts[0].co.lerp(closest_element.verts[1].co, .5), closest_element)
        elif isinstance(closest_element, bmesh.types.BMFace):
            addVertOnFace(self, closest_element.calc_center_median(), closest_element)

        return {'FINISHED'}

class FastConnect(bpy.types.Operator):
    bl_idname = 'mesh.fast_connect'
    bl_label = 'FastConnect'
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        global half_knife

        if half_knife is None:
            half_knife = get_is_addon_enabled('Half_Knife')

        obj = context.edit_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)

        sel_mode = bpy.context.tool_settings.mesh_select_mode[:]

        if sel_mode[0]:
            vert_sel = {v for v in bm.verts if v.select}

            if not vert_sel or len(vert_sel) == 1:
                if half_knife:
                    bpy.ops.mesh.half_knife_operator('INVOKE_DEFAULT', auto_cut=True, cut_with_preview_from_void = False)
                else:
                    bpy.ops.mesh.knife_tool('INVOKE_DEFAULT')
                return {'FINISHED'}
            
            elif len(vert_sel) > 1:
                try:
                    bpy.ops.mesh.vert_connect_path('INVOKE_DEFAULT')
                except:
                    self.report({'WARNING'}, "Could not connect vertices")
                return {'FINISHED'}

        elif sel_mode[1]:
            edge_sel = {e for e in bm.edges if e.select}

            if not edge_sel:
                bpy.ops.mesh.knife_tool('INVOKE_DEFAULT')
                return {'FINISHED'}
            else:
                bpy.ops.mesh.connect2('INVOKE_DEFAULT')

            
        elif sel_mode[2]:
            face_sel = {f for f in bm.faces if f.select}

            if not face_sel:
                bpy.ops.mesh.knife_tool('INVOKE_DEFAULT')
                return {'FINISHED'}

            elif len(face_sel) > 1:
                bpy.ops.mesh.connect2('INVOKE_DEFAULT')

        return {'FINISHED'}
    
class Connect(bpy.types.Operator):
    bl_idname = 'mesh.connect2'
    bl_label = 'Connect'
    bl_options = {'REGISTER', 'UNDO'}

    edge_count: bpy.props.IntProperty(name="Cuts", default=1, min=1, max=128) # type: ignore
    set_flow: bpy.props.BoolProperty(name="Set Flow", default=False) # type: ignore

    def draw(self, context):
        self.layout.prop(self, "edge_count")
        self.layout.prop(self, "set_flow")

    def execute(self, context):
        sel_mode = bpy.context.tool_settings.mesh_select_mode[:]
        edit_mode_objects = [obj for obj in context.objects_in_mode if obj.type == 'MESH']

        if sel_mode[0] or sel_mode[2]:
            for obj in edit_mode_objects:
                if sel_mode[0]:
                    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')

                me = obj.data
                bm = bmesh.from_edit_mesh(me)

                edge_sel = {e for e in bm.edges if e.select}
                if not edge_sel:
                    continue

                #Based on Armored Wolf's answer on https://blender.stackexchange.com/questions/142197
                bpy.ops.mesh.region_to_loop()
                perimeter_edges = set(e for e in bm.edges if e.select)
                contained_edges = edge_sel - perimeter_edges
                
                bpy.ops.mesh.select_all(action='DESELECT')

                for e in contained_edges:
                    e.select = True

                bpy.ops.mesh.loop_multi_select(ring=True)
                ring_edges = set(e for e in bm.edges if e.select)

                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
                corner_edges = set(e for e in bm.edges if e.select).intersection(perimeter_edges)

                ring_edges -= corner_edges

                bpy.ops.mesh.select_all(action='DESELECT')
                    
                ring_sel = (perimeter_edges.intersection(ring_edges) - corner_edges).union(contained_edges)

                new_edges = bmesh.ops.subdivide_edges(bm, edges=list(ring_sel), cuts=self.edge_count, use_grid_fill=True)
                for e in new_edges['geom_inner']:
                    e.select = True
                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')
                bmesh.update_edit_mesh(me)
                bm.free()

        
        elif sel_mode[1]:
            for obj in edit_mode_objects:
                if obj.data.total_edge_sel > 0:
                    me = obj.data
                    bm = bmesh.from_edit_mesh(me)

                    edge_sel = set(e for e in bm.edges if e.select)

                    for e in bm.edges:
                        e.select = False

                    new_edges = bmesh.ops.subdivide_edges(bm, edges=list(edge_sel), cuts=self.edge_count, use_grid_fill=True)
                    remove_edges = set(e for e in new_edges['geom_split'] if isinstance(e, bmesh.types.BMEdge))  
                    
                    for e in new_edges['geom_inner']:
                        e.select = True
                    for e in remove_edges:
                        e.select = False
                    bmesh.update_edit_mesh(me)
                    bm.free()

        if self.set_flow:
            if get_is_addon_enabled('EdgeFlow-blender_28') or get_is_addon_enabled('EdgeFlow'):
                bpy.ops.mesh.set_edge_flow(tension=180, iterations=3)
            else:
                self.report({'WARNING'}, "EdgeFlow Add-on not Installed, search for it in Get Extensions")

        return {'FINISHED'}