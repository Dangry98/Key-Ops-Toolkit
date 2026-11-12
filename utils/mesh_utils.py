
import math
from collections import deque

import bpy
import bmesh
from mathutils import Vector


def get_center(elements):
    """Calculate center point of vertices, edges, or vectors."""
    coords = []

    if isinstance(elements, bmesh.types.BMEdge):
        coords = [v.co for v in elements.verts]
    elif isinstance(elements, (list, tuple)):
        if not elements:
            return Vector()
        first = elements[0]
        if isinstance(first, bmesh.types.BMVert):
            coords = [v.co for v in elements]
        elif isinstance(first, Vector):
            coords = list(elements)

    if not coords:
        return Vector()

    return sum(coords, Vector()) / len(coords)


def get_unique_valid_vertices(vertices):
    """Return valid vertices once, preserving order."""
    unique_vertices = []
    seen_indices = set()

    for vert in vertices:
        if vert is None or not vert.is_valid or vert.index in seen_indices:
            continue
        unique_vertices.append(vert)
        seen_indices.add(vert.index)

    return unique_vertices


def refresh_bmesh_verts(operator):
    """Refresh the edit bmesh and ensure vertex lookup is available."""
    operator.bm = bmesh.from_edit_mesh(operator.me)
    operator.bm.verts.ensure_lookup_table()
    return operator.bm


def merge_uv_points(operator, vertices, target):
    """Merge UV face data for vertices."""
    if bpy.app.version >= (5, 2, 0):
        bmesh.ops.pointmerge_facedata(operator.bm, verts=vertices, vert_target=target)
    else:
        bmesh.ops.pointmerge_facedata(operator.bm, verts=vertices, vert_snap=target)


def move_vertices_with_face_attributes(operator, destinations_by_index):
    """Move verts with Blender's face-attribute correction so UVs follow the motion."""
    if not destinations_by_index:
        return

    tool_settings = bpy.context.scene.tool_settings
    prev_correct = tool_settings.use_transform_correct_face_attributes
    prev_keep_connected = tool_settings.use_transform_correct_keep_connected

    override_context = {
        'window': operator.window,
        'area': operator.area,
        'region': operator.region,
        'active_object': bpy.context.object,
        'object': bpy.context.object,
        'edit_object': bpy.context.edit_object,
    }

    try:
        tool_settings.use_transform_correct_face_attributes = True
        tool_settings.use_transform_correct_keep_connected = True

        for vert_index, destination in destinations_by_index.items():
            refresh_bmesh_verts(operator)
            vert = operator.bm.verts[vert_index]
            offset = destination - vert.co
            if offset.length <= 1e-8:
                continue

            bpy.ops.mesh.select_all(action='DESELECT')
            vert.select = True
            operator.bm.select_history.clear()
            operator.bm.select_history.add(vert)
            operator.bm.select_flush_mode()
            bmesh.update_edit_mesh(operator.me)

            with bpy.context.temp_override(**override_context):
                bpy.ops.transform.translate(
                    value=offset,
                    orient_type='LOCAL',
                    orient_matrix_type='LOCAL',
                    constraint_axis=(False, False, False),
                    mirror=False,
                    use_proportional_edit=False,
                    proportional_edit_falloff='SMOOTH',
                    proportional_size=1.0,
                    use_proportional_connected=False,
                    use_proportional_projected=False,
                    snap=False,
                    release_confirm=False,
                    use_accurate=False,
                    use_automerge_and_split=False,
                )

        refresh_bmesh_verts(operator)
    finally:
        tool_settings.use_transform_correct_face_attributes = prev_correct
        tool_settings.use_transform_correct_keep_connected = prev_keep_connected


def has_uv_border(operator, vertex, epsilon=1e-6):
    """Return True if a vertex has multiple distinct UVs across linked loops."""
    uv_layer = operator.bm.loops.layers.uv.active
    if uv_layer is None:
        return False

    uv_coords = []
    for loop in vertex.link_loops:
        uv = loop[uv_layer].uv
        if not any((uv - other).length <= epsilon for other in uv_coords):
            uv_coords.append(uv.copy())
            if len(uv_coords) > 1:
                return True

    return False


def get_uv_border_indices(operator, vertices):
    """Return UV-border vertex indices for the provided vertices."""
    uv_layer = operator.bm.loops.layers.uv.active
    if uv_layer is None:
        return set()

    return {vert.index for vert in vertices if has_uv_border(operator, vert)}


def merge_vertex_pair(operator, source, target, merge_center=False, center=None, preserve_uvs=True):
    """Merge a single source/target vertex pair while preserving UV behavior."""
    if not preserve_uvs:
        if merge_center:
            center = center or get_center([source, target])
            source.co = center
            target.co = center
        else:
            source.co = target.co
        return

    vertices = [source, target]
    border_indices = get_uv_border_indices(operator, vertices)

    if merge_center:
        center = center or get_center(vertices)
        if border_indices:
            move_vertices_with_face_attributes(operator, {source.index: center.copy(), target.index: center.copy()})
        else:
            target.co = center
            bmesh.ops.average_vert_facedata(operator.bm, verts=vertices)
        return

    if border_indices:
        move_vertices_with_face_attributes(operator, {source.index: target.co.copy()})
    else:
        source.co = target.co
        merge_uv_points(operator, vertices, target)


def merge_vertices_preserve_uvs(source, vertices, target, merge_center=False, bm=None, me=None):
    """Merge vertices using seam-aware UV handling without scanning unrelated mesh data."""
    if hasattr(source, "me"):
        operator = source
    else:
        obj = source.edit_object or source.object
        if obj is None or obj.type != 'MESH':
            return False
        operator = type("MergeState", (), {})()
        operator.me = me or obj.data
        operator.bm = bm or bmesh.from_edit_mesh(operator.me)
        operator.window = source.window
        operator.area = source.area
        operator.region = source.region

    unique_vertices = get_unique_valid_vertices(vertices)

    if target is None or not target.is_valid:
        return False

    if all(vert.index != target.index for vert in unique_vertices):
        unique_vertices.append(target)

    if len(unique_vertices) < 2:
        return False

    target = next((vert for vert in unique_vertices if vert.index == target.index), target)
    merge_map = {vert: target for vert in unique_vertices if vert.index != target.index}
    border_indices = get_uv_border_indices(operator, unique_vertices)

    if merge_center:
        center = get_center(unique_vertices)
        if not border_indices:
            target.co = center
            bmesh.ops.average_vert_facedata(operator.bm, verts=unique_vertices)
        else:
            move_vertices_with_face_attributes(operator, {vert.index: center.copy() for vert in unique_vertices})
    else:
        if not border_indices:
            for vert in merge_map:
                vert.co = target.co
            merge_uv_points(operator, unique_vertices, target)
        else:
            if target.index in border_indices:
                move_vertices_with_face_attributes(operator, {vert.index: target.co.copy() for vert in merge_map})
            else:
                for vert in merge_map:
                    if vert.index in border_indices:
                        continue
                    vert.co = target.co
                    merge_uv_points(operator, [vert, target], target)

                move_vertices_with_face_attributes(
                    operator,
                    {vert.index: target.co.copy() for vert in merge_map if vert.index in border_indices}
                )

    merge_indices = {source.index: target.index for source, target in merge_map.items()}
    refresh_bmesh_verts(operator)
    merge_map = {
        operator.bm.verts[source_index]: operator.bm.verts[target_index]
        for source_index, target_index in merge_indices.items()
    }
    bmesh.ops.weld_verts(operator.bm, targetmap=merge_map)
    operator.bm.select_flush_mode()
    bmesh.update_edit_mesh(operator.me, destructive=True)
    return True


def merge_vertices_basic(source, vertices, target, merge_center=False, bm=None, me=None):
    """Merge vertices without UV preservation logic for faster results on dense meshes."""
    if hasattr(source, "me"):
        operator = source
    else:
        obj = source.edit_object or source.object
        if obj is None or obj.type != 'MESH':
            return False
        operator = type("MergeState", (), {})()
        operator.me = me or obj.data
        operator.bm = bm or bmesh.from_edit_mesh(operator.me)

    unique_vertices = get_unique_valid_vertices(vertices)

    if target is None or not target.is_valid:
        return False

    if all(vert.index != target.index for vert in unique_vertices):
        unique_vertices.append(target)

    if len(unique_vertices) < 2:
        return False

    merge_co = get_center(unique_vertices) if merge_center else target.co.copy()
    bmesh.ops.pointmerge(operator.bm, verts=unique_vertices, merge_co=merge_co)
    operator.bm.select_flush_mode()
    bmesh.update_edit_mesh(operator.me, destructive=True)
    return True


def vertex_merge(operator):
    """Generic vertex merge logic for edit-mesh operators."""
    try:
        vertices = []

        if operator.multi_merge and operator.start_sel:
            vertices.extend(v for v in operator.start_sel if v.is_valid)
        elif operator.start_comp.is_valid:
            vertices.append(operator.start_comp)

        if operator.end_comp.is_valid and operator.end_comp not in vertices:
            vertices.append(operator.end_comp)

        if operator.preserve_uvs:
            return merge_vertices_preserve_uvs(
                operator,
                vertices,
                operator.end_comp,
                merge_center=operator.merge_center,
            )

        return merge_vertices_basic(
            operator,
            vertices,
            operator.end_comp,
            merge_center=operator.merge_center,
        )
    except Exception as e:
        print(f"Vertex merge failed: {e}")
        return False


def _hermite_1d(y0, y1, y2, y3, mu, tension, bias):
    mu2 = mu * mu
    mu3 = mu2 * mu
    m0 = (y1 - y0) * (1 + bias) * (1 - tension) / 2
    m0 += (y2 - y1) * (1 - bias) * (1 - tension) / 2
    m1 = (y2 - y1) * (1 + bias) * (1 - tension) / 2
    m1 += (y3 - y2) * (1 - bias) * (1 - tension) / 2
    a0 = 2 * mu3 - 3 * mu2 + 1
    a1 = mu3 - 2 * mu2 + mu
    a2 = mu3 - mu2
    a3 = -2 * mu3 + 3 * mu2
    return a0 * y1 + a1 * m0 + a2 * m1 + a3 * y2


def _hermite_3d(p1, p2, p3, p4, mu, tension, bias):
    return [
        _hermite_1d(p1[0], p2[0], p3[0], p4[0], mu, tension, bias),
        _hermite_1d(p1[1], p2[1], p3[1], p4[1], mu, tension, bias),
        _hermite_1d(p1[2], p2[2], p3[2], p4[2], mu, tension, bias),
    ]


class _Loop:
    def __init__(self, bm, edges):
        self.bm = bm
        self.edges = edges
        self.verts = []

        if len(self.edges) > 1:
            last_vert = None
            for p in self.edges[0].verts:
                if p not in self.edges[1].verts:
                    last_vert = p

            self.verts.append(last_vert)
            for edge in self.edges:
                vert = edge.other_vert(last_vert)
                self.verts.append(vert)
                last_vert = vert
        else:
            self.verts = [self.edges[0].verts[0], self.edges[0].verts[1]]

        if self.verts[0].co.x + self.verts[0].co.y + self.verts[0].co.z < self.verts[-1].co.x + self.verts[-1].co.y + self.verts[-1].co.z:
            self.verts.reverse()
            self.edges.reverse()

        self.initial_vert_positions = [v.co.copy() for v in self.verts]
        self.is_cyclic = self.verts[0] == self.verts[-1]
        self.valences = []
        self.ring = {edge: [] for edge in self.edges}
        self.edge_rings = {}
        self.ends = {}

    def set_ring(self, edge, ring_edge):
        if edge in self.ring and len(self.ring[edge]) <= 2:
            self.ring[edge].append(ring_edge)

    def get_ring(self, edge):
        if edge in self.ring:
            return self.ring[edge]
        raise Exception("edge not in Edgeloop!")

    def set_flow(self, tension, min_angle):
        for edge in self.edges:
            target = {}
            if edge.is_boundary:
                continue

            for loop in edge.link_loops:
                ring1 = loop.link_loop_next.link_loop_next
                ring2 = loop.link_loop_radial_prev.link_loop_prev.link_loop_prev
                center = edge.other_vert(loop.vert)

                p2 = ring1.vert
                p3 = ring2.link_loop_radial_next.vert

                if not ring1.edge.is_boundary:
                    final = ring1.link_loop_radial_next.link_loop_next
                    a, b = final.edge.verts
                    p1 = b.co if p2 == a else a.co

                    va = (p1 - p2.co).normalized()
                    vb = (center.co - p2.co).normalized()
                    dot = min(1.0, max(-1.0, va.dot(vb)))
                    angle = math.acos(dot)
                    if angle < min_angle:
                        p1 = p2.co - (p3.co - p2.co) * 0.5
                else:
                    p1 = p2.co - (p3.co - p2.co)

                if not ring2.edge.is_boundary:
                    final = ring2.link_loop_radial_prev.link_loop_prev
                    a, b = final.edge.verts
                    p4 = b.co if p3 == a else a.co

                    va = (p4 - p3.co).normalized()
                    vb = (center.co - p3.co).normalized()
                    dot = min(1.0, max(-1.0, va.dot(vb)))
                    angle = math.acos(dot)
                    if angle < min_angle:
                        p4 = p3.co - (p2.co - p3.co) * 0.5
                else:
                    p3 = ring2.edge.other_vert(p3)
                    p4 = p3.co - (p2.co - p3.co)

                target[center] = [p1, p2.co, p3.co, p4]

            for vert, points in target.items():
                p1, p2, p3, p4 = points
                if p1 == p2 or p3 == p4:
                    continue

                d = (p2 - p3).length * 0.5
                p1 = p2 + (d * (p1 - p2).normalized())
                p4 = p3 + (d * (p4 - p3).normalized())

                result = _hermite_3d(p1, p2, p3, p4, 0.5, -tension, 0)
                vert.co = Vector(result)


def _walk_boundary(start_edge, limit_to_edges=None):
    edge_loop = {start_edge}
    visited = set()
    candidates = [start_edge]

    while True:
        for candidate in candidates:
            for vert in candidate.verts:
                if len(vert.link_edges) > 2:
                    for edge in vert.link_edges:
                        if edge.is_boundary and edge not in edge_loop:
                            if limit_to_edges is not None:
                                if edge in limit_to_edges:
                                    edge_loop.add(edge)
                            else:
                                edge_loop.add(edge)
            visited.add(candidate)

        candidates = edge_loop - visited
        if len(visited) == len(edge_loop):
            break

    raw_edge_loop = list(edge_loop)
    start_edge = raw_edge_loop[0]
    raw_edge_loop.remove(start_edge)

    sorted_edge_loop = deque([start_edge])
    add = sorted_edge_loop.append

    for p in start_edge.verts:
        while True:
            edge = None
            for test_edge in raw_edge_loop:
                if p in test_edge.verts:
                    edge = test_edge

            if edge is not None:
                add(edge)
                p = edge.other_vert(p)
                raw_edge_loop.remove(edge)
            else:
                break

        add = sorted_edge_loop.appendleft

    return list(sorted_edge_loop)


def _walk_ngon(start_edge, limit_to_edges=None):
    edge_loop = deque([start_edge])
    start_loops = []
    face_valence = []

    for linked_loop in start_edge.link_loops:
        vert_count = len(linked_loop.face.verts)
        if vert_count > 4:
            start_loops.append(linked_loop)
            face_valence.append(vert_count)

    start_loop = start_loops[face_valence.index(max(face_valence))]

    loop = start_loop.link_loop_next
    while len(loop.vert.link_edges) < 4 and loop.edge not in edge_loop:
        if limit_to_edges is not None and loop.edge not in limit_to_edges:
            break
        edge_loop.append(loop.edge)
        loop = loop.link_loop_next

    loop = start_loop.link_loop_prev
    while len(loop.edge.other_vert(loop.vert).link_edges) < 4 and loop.edge not in edge_loop:
        if limit_to_edges is not None and loop.edge not in limit_to_edges:
            break
        edge_loop.appendleft(loop.edge)
        loop = loop.link_loop_prev

    return list(edge_loop)


def _walk_edge_loop(start_edge, limit_to_edges=None):
    edge_loop = deque([start_edge])
    add = edge_loop.append

    for loop in start_edge.link_loops:
        start_valence = len(loop.vert.link_edges)
        if start_valence <= 4:
            while True:
                valence = len(loop.vert.link_edges)
                if valence == 4 and start_valence == valence:
                    loop = loop.link_loop_prev.link_loop_radial_prev.link_loop_prev
                    if loop.edge in edge_loop:
                        break

                    if limit_to_edges is not None:
                        if loop.edge in limit_to_edges:
                            add(loop.edge)
                        else:
                            break
                    else:
                        add(loop.edge)
                else:
                    break

        add = edge_loop.appendleft

    return list(edge_loop)


def _get_edgeloop(bm, start_edge, limit_to_edges=None):
    start_loops = start_edge.link_loops
    is_ngon = any(len(loop.face.verts) > 4 for loop in start_loops)

    quad_flow = len(start_edge.verts[0].link_edges) == 4 and len(start_edge.verts[1].link_edges) == 4
    loop_end = (
        (len(start_edge.verts[0].link_edges) > 4 and len(start_edge.verts[1].link_edges) == 4)
        or (len(start_edge.verts[0].link_edges) == 4 and len(start_edge.verts[1].link_edges) > 4)
    )

    if is_ngon and not quad_flow and not loop_end:
        return _Loop(bm, _walk_ngon(start_edge, limit_to_edges))
    if start_edge.is_boundary:
        return _Loop(bm, _walk_boundary(start_edge, limit_to_edges))
    return _Loop(bm, _walk_edge_loop(start_edge, limit_to_edges))


def _find_edge_ring_neighbours(edgeloops, edge_to_loop):
    for edgeloop in edgeloops:
        for edge in edgeloop.edges:
            if len(edgeloop.get_ring(edge)) == 2:
                continue
            for link_loop in edge.link_loops:
                if len(link_loop.face.verts) != 4:
                    continue
                next_edge = link_loop.link_loop_next.link_loop_next.edge
                if next_edge not in edgeloop.get_ring(edge) and next_edge in edge_to_loop:
                    edgeloop.set_ring(edge, next_edge)
                    edge_to_loop[next_edge].set_ring(next_edge, edge)


def _find_control_edgeloop(edgeloops, edge_to_loop):
    for edgeloop in edgeloops:
        for edge in edgeloop.edges:
            if edge in edgeloop.edge_rings:
                continue

            edge_ring = deque([edge.link_loops[0]])
            ends = []
            append_func = edge_ring.append

            for index, loop in enumerate(edge.link_loops):
                next_loop = loop
                visited = set()
                while True:
                    ring = next_loop.link_loop_prev.link_loop_prev
                    if ring in visited:
                        break
                    visited.add(ring)

                    if ring.edge not in edge_to_loop:
                        ends.append(ring)
                        break

                    append_func(ring)
                    next_loop = ring.link_loop_radial_prev
                    if ring.edge.is_boundary:
                        ends.append(ring)
                        break

                if index == 0:
                    append_func = edge_ring.appendleft

            for ring in edge_ring:
                edge_to_loop[ring.edge].edge_rings[ring.edge] = edge_ring
                edge_to_loop[ring.edge].ends[ring.edge] = ends


def _compute_edge_ring_valences(edgeloops, edge_to_loop):
    for edgeloop in edgeloops:
        max_valence = -1
        for edge in edgeloop.edges:
            valence = 0
            visited = set()
            search = {edge}
            while search:
                current = search.pop()
                visited.add(current)
                ring_edges = edge_to_loop[current].get_ring(current)

                add_to_valence = True
                for ring in ring_edges:
                    if ring not in visited:
                        search.add(ring)
                        if add_to_valence:
                            valence += 1
                            add_to_valence = False

            edgeloop.valences.append(valence)
            max_valence = max(max_valence, valence)
        edgeloop.max_valence = max_valence


def _compute_edgeloop_data(edgeloops):
    edge_to_loop = {}
    for edgeloop in edgeloops:
        for edge in edgeloop.edges:
            edge_to_loop[edge] = edgeloop

    _find_edge_ring_neighbours(edgeloops, edge_to_loop)
    _compute_edge_ring_valences(edgeloops, edge_to_loop)
    _find_control_edgeloop(edgeloops, edge_to_loop)

    result = sorted(edgeloops, key=lambda edgeloop: edgeloop.max_valence)
    result.reverse()
    return result


def _get_edgeloops(bm, edges):
    not_visited = set(edges)
    edge_loops = []

    while not_visited:
        next_edge = not_visited.pop()
        edge_loop = _get_edgeloop(bm, next_edge, not_visited)
        edge_loops.append(edge_loop)
        for edge in edge_loop.edges:
            if edge in not_visited:
                not_visited.remove(edge)

    return _compute_edgeloop_data(edge_loops)

