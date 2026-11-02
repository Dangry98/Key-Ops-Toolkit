import bpy.types
import bmesh
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
from ..utils import mesh_utils as MeshUtils
from ..utils.pref_utils import get_keyops_prefs
from ..utils.pref_utils import clear_registered_keymaps
from ..utils.utilities import select_loop, select_ring
from .fast_knife import FastKnife

has_clicked_once = None
registered_fast_merge_keymaps = []

def register_fast_merge_keymaps():
    global registered_fast_merge_keymaps
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='Mesh', space_type='EMPTY')

    kmi = km.keymap_items.new('keyops.fast_merge', 'ONE', 'PRESS', repeat=True)
    registered_fast_merge_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('mesh.merge', 'ONE', 'PRESS', alt=True)
    kmi.properties.type = 'CENTER'
    registered_fast_merge_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('mesh.fast_connect', 'ONE', 'PRESS', shift=True)
    registered_fast_merge_keymaps.append((km, kmi))

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


def should_merge_to_nearest(prefs, selected_verts, active_vert):
    """Return True when fast merge should pick the nearest visible target."""
    return (
        (len(selected_verts) == 1 and prefs.fast_merge_merge_options == "only merge if active or only 1 verts is selected")
        or prefs.fast_merge_merge_options == "always merge to nearest vert"
        or (prefs.fast_merge_merge_options == "merge to nerest vert if no active" and active_vert is None)
        or len(selected_verts) == 1
    )


def get_merge_candidates(selected_verts):
    """Collect selected vertices and their neighbors once."""
    vertices = []
    for vert in selected_verts:
        vertices.extend(edge.other_vert(vert) for edge in vert.link_edges)

    vertices += selected_verts
    return list(set(vertices))


def get_selected_verts_and_active(bm):
    """Return the current selected verts and a valid active vert if one exists."""
    selected_verts = [vert for vert in bm.verts if vert.select]
    active_vert = bm.select_history.active
    if active_vert is None or not getattr(active_vert, "is_valid", False):
        active_vert = None
    return selected_verts, active_vert


def merge_selected_to_target(context, bm, selected_verts, target_vert, preserve_uvs):
    """Merge selected vertices into the target using the chosen UV behavior."""
    if preserve_uvs:
        MeshUtils.merge_vertices_preserve_uvs(context, selected_verts, target_vert, bm=bm, me=context.active_object.data)
    else:
        bmesh.ops.pointmerge(bm, verts=selected_verts, merge_co=target_vert.co)
        bmesh.update_edit_mesh(context.active_object.data)


def set_active_merged_vertex(context, target_index):
    """Restore the merged vertex as active from the refreshed edit mesh."""
    bm = bmesh.from_edit_mesh(context.active_object.data)
    bm.verts.ensure_lookup_table()
    active_vert = bm.verts[target_index] if target_index is not None and target_index < len(bm.verts) else None

    if active_vert is None or not active_vert.is_valid or not active_vert.select:
        active_vert = next((vert for vert in bm.verts if vert.select), None)
        if active_vert is None:
            return

    active_vert.select = True
    bm.select_history.clear()
    bm.select_history.add(active_vert)
    bmesh.update_edit_mesh(context.active_object.data)


class FastMerge(bpy.types.Operator):
    bl_idname = "keyops.fast_merge"
    bl_label = "Fast Merge"
    bl_description = "Fast Merge"
    bl_options = {'REGISTER', 'UNDO'}
    
    preserve_uvs: bpy.props.BoolProperty(name="Preserve UVs", description="Try Preserve UVs (Slower and does not always work)", default=True) # type: ignore
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
        selected_verts, active_vert = get_selected_verts_and_active(bm)
        global has_clicked_once 
    
        def merge(self, context):
            bm = bmesh.from_edit_mesh(context.active_object.data)
            selected_verts, active_vert = get_selected_verts_and_active(bm)
            if len(selected_verts) == 0:
                self.report({'WARNING'}, "No vertices selected")
                return {'FINISHED'}

            if should_merge_to_nearest(self.prefs, selected_verts, active_vert):
                obj = context.object
                matrix_world = obj.matrix_world.copy()
                vertices = get_merge_candidates(selected_verts)
                nearest_vertex = find_nearest_visible_vertex_to_mouse(context, self.mouse_position, vertices, matrix_world)

                if nearest_vertex:
                    if nearest_vertex not in selected_verts:
                        selected_verts.append(nearest_vertex)

                    target_index = nearest_vertex.index
                    merge_selected_to_target(context, bm, selected_verts, nearest_vertex, self.preserve_uvs)
                    set_active_merged_vertex(context, target_index)
                    self.report({'INFO'}, "Merged %d vertices" % (len(selected_verts) - 1))
                return {'FINISHED'}

            if active_vert is not None and active_vert in selected_verts:
                amount_of_verts_merged = len(selected_verts)
                target_index = active_vert.index
                merge_selected_to_target(context, bm, selected_verts, active_vert, self.preserve_uvs)
                set_active_merged_vertex(context, target_index)
                self.report({'INFO'}, "Merged %d vertices" % (amount_of_verts_merged - 1))
            else:
                self.report({'WARNING'}, "No Active Vertex to Merge to")

        if self.prefs.fast_merge_soft_limit == "no_limit":  
            merge(self, context)

        elif self.prefs.fast_merge_soft_limit == "max_polycount":
            if self.prefs.fast_merge_polycount >= len(selected_verts):
                merge(self, context)
            else:
                self.report({'WARNING'}, "Limit - Too many vertices selected")
        elif self.prefs.fast_merge_soft_limit == "all_selected":
            if len(selected_verts) == len(bm.verts):
                self.report({'WARNING'}, "Limit - All vertices are selected")
            else:
                merge(self, context)

        elif self.prefs.fast_merge_soft_limit == "max_limit_&_all_selected":
            if len(selected_verts) == len(bm.verts) and self.prefs.fast_merge_polycount < len(selected_verts):
                self.report({'WARNING'}, "Limit - All vertices are selected and too many vertices selected")
            elif self.prefs.fast_merge_polycount >= len(selected_verts):
                merge(self, context)
            else:
                self.report({'WARNING'}, "Limit - Too many vertices selected")

        elif self.prefs.fast_merge_soft_limit == "ask_if_no_active_vert":
            if active_vert is None:
                if has_clicked_once == None:
                    has_clicked_once = True
                    if not self.prefs.fast_merge_merge_options == "only merge if active or only 1 verts is selected":
                        self.report({'WARNING'}, "Limit - Press again to merge to nearest vertex")
                    return {'FINISHED'}
                else:
                    has_clicked_once = None
                    merge(self, context)
            else:
                merge(self, context)
            
        has_clicked_once = None
            
        return {'FINISHED'}
def register_fast_merge():
    bpy.utils.register_class(FastMerge)
    bpy.utils.register_class(FastKnife)
    bpy.utils.register_class(FastConnect)
    bpy.utils.register_class(Connect)
    register_fast_merge_keymaps()

def unregister_fast_merge():
    clear_registered_keymaps(registered_fast_merge_keymaps)
    bpy.utils.unregister_class(FastMerge)
    bpy.utils.unregister_class(FastKnife)
    bpy.utils.unregister_class(FastConnect)
    bpy.utils.unregister_class(Connect)

class FastConnect(bpy.types.Operator):
    bl_idname = 'mesh.fast_connect'
    bl_label = 'FastConnect'
    bl_options = {'REGISTER', 'UNDO'}

    # edge_count: bpy.props.IntProperty(name="Cuts", default=1, min=1, max=128) # type: ignore
    # set_flow: bpy.props.BoolProperty(name="Set Flow", default=False) # type: ignore

    # def draw(self, context):
    #     layout = self.layout 
    #     layout.use_property_split = True
        
    #     layout.prop(self, "edge_count")
    #     layout.prop(self, "set_flow")

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.edit_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)

        sel_mode = bpy.context.tool_settings.mesh_select_mode[:]

        if sel_mode[0]:
            vert_sel = {v for v in bm.verts if v.select}

            if not vert_sel or len(vert_sel) == 1:
                bpy.ops.mesh.fast_knife('INVOKE_DEFAULT')
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
                # bpy.ops.mesh.connect2('INVOKE_DEFAULT', edge_count=self.edge_count, set_flow=self.set_flow)

            
        elif sel_mode[2]:
            face_sel = {f for f in bm.faces if f.select}

            if not face_sel:
                bpy.ops.mesh.knife_tool('INVOKE_DEFAULT')
                return {'FINISHED'}

            elif len(face_sel) > 1:
                bpy.ops.mesh.connect2('INVOKE_DEFAULT')
                # bpy.ops.mesh.connect2('INVOKE_DEFAULT', edge_count=self.edge_count, set_flow=self.set_flow)


        return {'FINISHED'}
    
class Connect(bpy.types.Operator):
    bl_idname = 'mesh.connect2'
    bl_label = 'Connect'
    bl_options = {'REGISTER', 'UNDO'}

    edge_count: bpy.props.IntProperty(name="Cuts", default=1, min=1, max=128) # type: ignore
    set_flow: bpy.props.BoolProperty(name="Set Flow", default=False) # type: ignore

    def draw(self, context):
        layout = self.layout 
        layout.use_property_split = True
        
        layout.prop(self, "edge_count")
        layout.prop(self, "set_flow")

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

                select_ring()
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
            bpy.ops.mesh.set_mesh_edge_flow('INVOKE_DEFAULT', tension=180, iterations=3)

        return {'FINISHED'}