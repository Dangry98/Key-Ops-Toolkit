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

class GeometryMath:

    def __init__(self, context, object):
        self.context = context
        self.region = context.region
        self.rv3d = context.region_data
        self.matrix = object.matrix_world
        self.matrix_inv = self.matrix.inverted()

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


# ---------------------------------------------------------------- minimum oriented bounding box

def _min_rect_2d(points2d):
    """Smallest-area rectangle around 2D points: (area, angle, (min_u, max_u, min_v, max_v)) with u, v the
    rectangle's axes rotated by angle. Rotating calipers over the convex hull's edges."""
    import math
    from mathutils import Vector
    from mathutils.geometry import convex_hull_2d
    if len(points2d) < 3:
        hull = list(points2d)
    else:
        hull = [points2d[i] for i in convex_hull_2d(points2d)]
    best = None
    n = len(hull)
    angles = set()
    for i in range(n):
        d = hull[(i + 1) % n] - hull[i]
        if d.length > 1e-12:
            angles.add(round(math.atan2(d.y, d.x) % (math.pi / 2), 9))
    if not angles:
        angles = {0.0}
    for a in angles:
        c, s = math.cos(a), math.sin(a)
        us = [p.x * c + p.y * s for p in hull]
        vs = [-p.x * s + p.y * c for p in hull]
        box = (min(us), max(us), min(vs), max(vs))
        area = (box[1] - box[0]) * (box[3] - box[2])
        if best is None or area < best[0] - 1e-12:
            best = (area, a, box)
    return best


def min_oriented_box(points):
    """The smallest box around 3D points, as (centre, rotation 3x3 with the box axes as columns, size).
    The box's axes are sorted so Z is the thinnest (a flat set of points is flat along Z).
    Tries the normals of the convex hull's faces as one axis and fits the smallest rectangle across them."""
    import bmesh
    from mathutils import Matrix, Vector
    pts = [Vector(p) for p in points]
    if not pts:
        return Vector(), Matrix.Identity(3), Vector()
    centre0 = sum(pts, Vector()) / len(pts)
    normals = []
    bm = bmesh.new()
    try:
        for p in pts:
            bm.verts.new(p)
        try:
            res = bmesh.ops.convex_hull(bm, input=list(bm.verts))
            faces = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
            for f in faces:
                f.normal_update()
                n = f.normal.copy()
                if n.length > 1e-9 and not any(abs(n.dot(m)) > 0.9999 for m in normals):
                    normals.append(n)
                if len(normals) > 400:
                    break
        except (ValueError, RuntimeError):
            pass
    finally:
        bm.free()
    if not normals:  # flat or a line: the plane's normal from the spread of the points
        normals = [_flat_normal(pts, centre0)]
    best = None
    for n in normals:
        n = n.normalized()
        u = n.orthogonal().normalized()
        w = n.cross(u)
        p2 = [Vector(((p - centre0).dot(u), (p - centre0).dot(w))) for p in pts]
        area, a, box = _min_rect_2d(p2)
        hs = [(p - centre0).dot(n) for p in pts]
        depth = max(hs) - min(hs)
        vol = area * depth if depth > 1e-9 else area * 1e-9
        if best is None or vol < best[0] - 1e-12:
            import math
            c, s = math.cos(a), math.sin(a)
            ax_u = (u * c + w * s).normalized()
            ax_v = n.cross(ax_u).normalized()
            centre = (centre0 + ax_u * (box[0] + box[1]) * 0.5 + ax_v * (box[2] + box[3]) * 0.5
                      + n * (min(hs) + max(hs)) * 0.5)
            best = (vol, centre, [(ax_u, box[1] - box[0]), (ax_v, box[3] - box[2]), (n, depth)])
    _vol, centre, axes = best
    axes.sort(key=lambda a: -a[1])  # longest first, thinnest last (Z)
    x, y = axes[0][0], axes[1][0]
    z = x.cross(y).normalized()  # right-handed
    rot = Matrix((x, y, z)).transposed()
    return centre, rot, Vector((axes[0][1], axes[1][1], axes[2][1]))


def _flat_normal(pts, centre):
    from mathutils import Matrix, Vector
    cov = Matrix(((0, 0, 0), (0, 0, 0), (0, 0, 0)))
    for p in pts:
        d = p - centre
        for i in range(3):
            for j in range(3):
                cov[i][j] += d[i] * d[j]
    try:
        import numpy as np
        vals, vecs = np.linalg.eigh(np.array([list(r) for r in cov]))
        n = Vector(vecs[:, 0])
    except Exception:  # noqa: BLE001
        n = Vector((0, 0, 1))
    return n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))
