# ##### BEGIN GPL LICENSE BLOCK #####
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####


from bpy_extras import view3d_utils
import numpy as np
import mathutils

class GeometryMath:

    def __init__(self, context, object):
        self.context = context
        self.region = context.region
        self.rv3d = context.region_data
        self.matrix = object.matrix_world
        self.matrix_inv = self.matrix.inverted()

    def get_view_plane(self):
        zero = self.get_viewport_point_object_space(0, 0)
        top_left = self.get_viewport_point_object_space(0, self.context.area.height)
        bottom_right = self.get_viewport_point_object_space(self.context.area.width, 0)

        normal = mathutils.geometry.normal(zero, top_left, bottom_right)
        return zero, normal

    def project_point_on_view(self, point):
        point2d = self.location_3d_to_region_2d_object_space(point)
        return self.get_viewport_point_object_space(point2d.x, point2d.y)

    def ray_cast_BVH(self, tree, bm, x, y):
        ray_origin_obj, ray_direction_obj = self.get_view_object_space(x, y)
        hit, normal, face_index, distance = tree.ray_cast(ray_origin_obj, ray_direction_obj)
        if not hit:
            return None, None
        return hit, bm.faces[face_index]

    def ray_cast_point(self, tree, bm, vec):
        v = self.location_3d_to_region_2d_object_space(vec)
        return self.ray_cast_BVH(tree, bm, v.x, v.y)

    def get_view_object_space(self, x, y):
        view_origin, view_vector = self.get_view_world_space(x, y)
        ray_target = view_origin + view_vector

        matrix_inv = self.matrix_inv
        ray_origin_obj = matrix_inv @ view_origin
        ray_target_obj = matrix_inv @ ray_target
        ray_direction_obj = ray_target_obj - ray_origin_obj

        return ray_origin_obj, ray_direction_obj

    def get_viewport_point_world_space(self, x, y):
        view_origin, view_vector = self.get_view_world_space(x, y)
        return view_origin + view_vector

    def get_viewport_point_object_space(self, x, y):
        view_origin, view_vector = self.get_view_object_space(x, y)
        return view_origin + view_vector

    def get_view_world_space(self, x, y):
        coord = x, y
        view_vector = view3d_utils.region_2d_to_vector_3d(self.region, self.rv3d, coord)
        view_origin = view3d_utils.region_2d_to_origin_3d(self.region, self.rv3d, coord)
        return view_origin, view_vector



    def location_3d_to_region_2d_object_space(self, v):
        return view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, self.matrix @ v)

    def distance_2d(self, v1, v2):
         pxv1 = self.location_3d_to_region_2d_object_space(v1)
         pxv2 = self.location_3d_to_region_2d_object_space(v2)
         if not pxv1 or not pxv2:
            return float("inf")

         return (pxv1 - pxv2).length

    def is_point_on_edge(self, point, v1, v2, dist):
        l1 = (point - v1).length
        if l1 == 0:
            return False;
        l2 = (point - v2).length
        if l2 == 0:
            return False;
        #print((v1 - v2).length - (l1 + l2))
        return abs((v1 - v2).length - (l1 + l2)) < dist

    def is_point_on_edge2(self, point, edge, dist):
        v1, v2 = [v.co for v in edge.verts]
        d1 = (point - v1).length
        d2 = (point - v2).length
        projected = self.vertex_project(point, v1, v2)
        h = (point - projected).length
        return h < dist

    def get_split_ratio(self, projected, edge):
        v1, v2 = [v.co for v in edge.verts]
        ab = v2 - v1
        d1 = (v1 - projected).length
        d2 = (v2 - projected).length
        a = ab.length
        if a == 0:
            return 0
        # projected = projected if abs(d1 + d2 - a) < 0.001 else edge.verts[0] if d1 < d2 else edge.verts[1]
        split_ratio = 0
        if (abs(d1 + d2 - a) < 0.001):
            split_ratio = d1 / a
        elif d1 > d2:
            split_ratio = 1
        return split_ratio

    def vertex_project(self, point, v1, v2):
        if v1 == v2:
            return v1
        ap = point - v1
        ab = v2 - v1
        temp = ab * (np.dot(ap,ab) / np.dot(ab,ab))
        projected = v1 + temp
        return projected

    def distance_to_edge(self, point, edge):
        v1, v2 = [v.co for v in edge.verts]
        d1 = (point - v1).length
        d2 = (point - v2).length
        projected = self.vertex_project(point, v1, v2)
        h = (point - projected).length

        # to solve concave ngons
        split_ratio = self.get_split_ratio(projected, edge)
        closest_point_on_edge = projected
        if split_ratio == 1:
            closest_point_on_edge = v2
        elif split_ratio == 0:
            closest_point_on_edge = v1
        edge_pixel_distance = self.distance_2d(point, closest_point_on_edge)

        vertex_distance, vertex_index, vertex_pixel_distance = (d1, 0, self.distance_2d(v1, point)) if d1 < d2 else (d2, 1, self.distance_2d(v2, point))
        edge_distance = min(h, d1, d2)

        return edge_distance, vertex_distance, vertex_index, edge_pixel_distance, vertex_pixel_distance, projected, split_ratio

    def find_closest(self, point, face, cull_zero_edges = True):
        if not point:
            return None, None, None, None

        edge_dist = float("inf")
        edge_pixel_distance = float("inf")
        vertex_pixel_distance = float("inf")
        edge = None
        vert = None
        projected = None
        for e in face.edges:
            try:
                dRes = self.distance_to_edge(point, e)
            except Exception as ex:
                e.select_set(True)
                raise ex

            if (cull_zero_edges):
                #projected_length = (dRes[5] - point).length
                split_ratio = dRes[6]
                #print(split_ratio)
                if split_ratio in [0, 1]:
                    continue

            if dRes[0] < edge_dist:
                edge_dist = dRes[0]
                edge = e
                vert = e.verts[dRes[2]]
                edge_pixel_distance = dRes[3]
                vertex_pixel_distance = dRes[4]
                projected = dRes[5]

        return vert, edge, vertex_pixel_distance, edge_pixel_distance, projected
