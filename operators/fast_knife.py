import bpy
from mathutils.bvhtree import BVHTree
import bmesh
from ..utils.geometry_math_utils import GeometryMath


class FastKnifeStaticPrefs:
    snap_vertex_distance = 20
    snap_edge_distance = 15



FAST_KNIFE_PREFS = FastKnifeStaticPrefs()


def calc_edge_center(edge):
    return (edge.verts[0].co + edge.verts[1].co) / 2

def dissolve_redundant_edges(bm, vert, excluded_verts = []):
    dissolved_edges = []
    l = len(vert.link_edges)
    for e in vert.link_edges:
        if not e.other_vert(vert) in excluded_verts and l > 2:
            dissolved_edges.append(e)
            l -= 1
    # dissolved_edges = vert.link_edges[slice(len(vert.link_edges) - 2)]
    bmesh.ops.dissolve_edges(bm, edges = dissolved_edges, use_verts = False, use_face_split = False)

class FastKnife(bpy.types.Operator):
    bl_idname = "mesh.fast_knife"
    bl_label = "Fast Knife"
    bl_description = "Instant knife cut without preview drawing"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'VIEW_3D'
            and context.object
            and context.object.mode == 'EDIT')


    def addVertOnFace(self, co, face):
        vert = bmesh.ops.poke(self.bmesh, faces=[face])['verts'][0]
        vert.co = co
        dissolve_redundant_edges(self.bmesh, vert)
        return vert;
        
    def __calc_split_fac( self , edge , co ) :
        fac = 0.5
        d0 = (edge.verts[0].co - co ).length
        d1 = (edge.verts[1].co - co ).length
        fac = d0 / (d0 + d1)
        return fac

    def addVertOnEdge(self, co, edge):
        #split_ratio = self.util.get_split_ratio(co, edge)
        fac = self.__calc_split_fac( edge , co )

        edge, vert = bmesh.utils.edge_split(edge, edge.verts[0], fac)
        return vert;

    def addVert(self, context, event):
        self.calc_hit(context, event)
        if self.snap_mode == 'VOID':
            co = self.util.get_viewport_point_object_space(event.mouse_region_x, event.mouse_region_y)
            vert = self.bmesh.verts.new()
            vert.co = co
            self.virtual_start = vert
            return vert, co
        elif self.snap_mode == 'VERT':
            vert, center = self.vert, self.vert.co
        elif self.snap_mode == 'FACE':
            center = self.face.calc_center_median()
            vert = self.addVertOnFace(self.snapped_hit, self.face)
            self.face = vert.link_faces[0]
        elif self.snap_mode == 'EDGE':
            center = calc_edge_center(self.edge)
            vert = self.addVertOnEdge(self.snapped_hit, self.edge)

        vert.select_set(True)
        self.bmesh.select_history.add(vert)
        self.update_geom()
        return vert, center

    def update_geom(self):
        bmesh.update_edit_mesh(self.object.data, loop_triangles = True, destructive = True)
        self.tree = BVHTree.FromBMesh(self.bmesh)
        self.bmesh.faces.ensure_lookup_table()

    def snap_void_preivew(self, hit):
        self.snap_mode = 'VOID'
        self.snapped_hit = hit

    def snap_vert_preivew(self, vert):
        self.snap_mode = 'VERT'
        self.snapped_hit = vert.co
        self.snapped_vert = vert

    def snap_face_preivew(self, hit, face):
        self.snap_mode = 'FACE'
        self.snapped_hit = hit

    def snap_edge_preivew(self, hit, edge, projected):
        self.snap_mode = 'EDGE'
        self.snapped_hit = projected


    def get_cut_point(self, coord):
        screen_position_px = self.util.location_3d_to_region_2d_object_space(coord)
        view_origin, view_vector = self.util.get_view_world_space(screen_position_px.x, screen_position_px.y)
        pos = view_origin + view_vector;
        return pos, screen_position_px

    def create_cut_obj(self):
        # Make a new BMesh
        bm = bmesh.new()
        new_vertex_co = self.snapped_hit

        v0co, _ = self.get_cut_point(new_vertex_co)
        v0 = bm.verts.new(v0co)
        for v in self.initial_vertices:
            v1co, _ = self.get_cut_point(v.co)
            v1 = bm.verts.new(v1co)
            bm.edges.new((v0, v1))

        me = bpy.data.meshes.new("Mesh")
        bm.to_mesh(me)
        bm.free()


        # Add the mesh to the scene
        obj = bpy.data.objects.new("Cut object", me)
        bpy.context.collection.objects.link(obj)

        # bpy.context.view_layer.objects.active = obj
        #obj.select_set(True)
        self.cut_obj = obj


    def delete_vitrual_vertex(self):
        if self.virtual_start:
            bmesh.ops.delete(self.bmesh, geom = [self.virtual_start], context = 'VERTS')
            self.update_geom()

    def fix_lonely_vert(self, start_co):
        bm = self.bmesh = bmesh.from_edit_mesh(self.object.data)

        start = None
        lonely_vert = None
        for v in bm.verts:
            if v.co == start_co:
                start = v
            if v.select:
                lonely_vert = v
        if not lonely_vert:
            return
        if len(lonely_vert.link_faces) != 0:
            return
        end = lonely_vert.co
        bm.verts.remove(lonely_vert)
        self.update_geom()
        hit, face = self.util.ray_cast_point(self.tree, bm, self.snapped_hit)
        vert = bmesh.ops.poke(bm, faces=[face])['verts'][0]
        vert.co = self.snapped_hit
        dissolve_redundant_edges(bm, vert, excluded_verts = [start])
        vert.select_set(True)
        self.bmesh.select_history.add(vert)
        self.update_geom()

    def run_cut(self):
        is_multiple_verts = len(self.initial_vertices) > 1
        if self.snap_mode == 'EDGE':
            self.addVertOnEdge(self.snapped_hit, self.edge)
            self.update_geom()

        self.create_cut_obj()

        if not self.initial_vertices:
            return
        risk_of_lonely_vert = False


        if not is_multiple_verts:
            start = self.initial_vertices[0]
            end = self.snapped_hit
            if start.co == end:
                self.delete_vitrual_vertex()
                bpy.data.objects.remove(self.cut_obj, do_unlink=True)
                return
            if self.snap_mode == 'FACE' and self.face in start.link_faces:
                risk_of_lonely_vert = True
                start_co = start.co

        self.delete_vitrual_vertex()

        self.cut_obj.select_set(True)
        bpy.ops.mesh.knife_project(cut_through = False)

        bpy.ops.mesh.select_mode(use_extend = False, use_expand = False, type = 'VERT')
        bpy.data.objects.remove(self.cut_obj, do_unlink=True)

        self.update_geom()

        select_location = self.util.location_3d_to_region_2d_object_space(self.snapped_hit)
        if select_location:
            bpy.ops.view3d.select(location = (int(select_location.x), int(select_location.y)))
            # Blender 2.91 hack bugfix
            #bpy.ops.object.mode_set(mode = 'OBJECT')
            #bpy.ops.object.mode_set(mode = 'EDIT')

        if risk_of_lonely_vert:
            self.fix_lonely_vert(start_co)

    def calc_hit(self, context, event):
        hit, face = self.util.ray_cast_BVH(self.tree, self.bmesh, event.mouse_region_x, event.mouse_region_y)
        if hit:
            vert, edge, vertex_pixel_distance, edge_pixel_distance, projected = self.util.find_closest(hit, face, True)
            self.vert = vert
            self.edge = edge
            self.face = face
            if vertex_pixel_distance < self.prefs.snap_vertex_distance:
                self.snap_vert_preivew(vert)
            elif edge_pixel_distance < self.prefs.snap_edge_distance:
                self.snap_edge_preivew(hit, edge, projected)
            else:
                self.snap_face_preivew(hit, face)
        else:
            hit = self.util.get_viewport_point_object_space(event.mouse_region_x, event.mouse_region_y)
            self.snap_void_preivew(hit)

    def invoke(self, context, event):
        self.object = context.edit_object
        self.prefs = FAST_KNIFE_PREFS

        self.bmesh = bmesh.from_edit_mesh(self.object.data)

        self.initial_vertices = [v for v in self.bmesh.verts if v.select]
        vert_len = len(self.initial_vertices)
        if vert_len > 10:
            self.report({'ERROR'}, 'Too many vertices selected! Canceling.')
            return {'CANCELLED'}

        self.tree = BVHTree.FromBMesh(self.bmesh)
        self.util = GeometryMath(context, self.object)

        self.virtual_start = None
        if vert_len == 0:
            vert, _ = self.addVert(context, event)

            if not vert:
                return {'FINISHED'}

            if not self.virtual_start:
                return {'FINISHED'}

            self.initial_vertices = [vert]

        if self.virtual_start:
            self.delete_vitrual_vertex()
            return {'CANCELLED'}

        self.calc_hit(context, event)
        self.run_cut()
        return {'FINISHED'}

