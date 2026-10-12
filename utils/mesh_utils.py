
import bpy
import bmesh
from mathutils import Vector

def modifier_toggle_visability_based(visibility_modifier_dict_list={}):
    active_object_name = bpy.context.view_layer.objects.active.name

    if active_object_name not in visibility_modifier_dict_list:
        visibility_modifier_dict_list[active_object_name] = []

    visibility_modifier_list = visibility_modifier_dict_list[active_object_name]

    if len(visibility_modifier_list) <= 0:
        ml_act_ob = bpy.context.view_layer.objects.active
        for mod in ml_act_ob.modifiers:
            if mod.show_viewport:
                visibility_modifier_list.append(mod)
                mod.show_viewport = False
    else:
        ml_act_ob = bpy.context.view_layer.objects.active
        hidden_modifiers = []
        for mod in ml_act_ob.modifiers:
            if mod in visibility_modifier_list:
                mod.show_viewport = True
                hidden_modifiers.append(mod)
        visibility_modifier_list = [mod for mod in visibility_modifier_list if mod not in hidden_modifiers]
        visibility_modifier_dict_list[active_object_name] = visibility_modifier_list

def set_attribute_value_on_selection(obj=None, attr_name="", value=True, domain='POINT', data_type='BOOLEAN'):
    mesh = obj.data
    
    if attr_name and obj:
        attribute = mesh.attributes.get(attr_name)
        if attribute is None:
            attribute = mesh.attributes.new(name=attr_name, domain=domain, type=data_type)
        if obj.mode == 'EDIT':
            mesh = bpy.context.active_object.data
            attribute = mesh.attributes.new(name="new attribute", type="BOOLEAN", domain="POINT")
            attribute_values = [i for i in range(len(mesh.vertices))]

            bm = bmesh.from_edit_mesh(mesh)
            layer = bm.verts.layers.int.get(attr_name)

            for vert in bm.verts:
                print(f"Previous value for {vert} : {vert[layer]}")
                vert[layer] = attribute_values[vert.index]
                print(f"New value for {vert} : {vert[layer]}")

            bmesh.update_edit_mesh(mesh)


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
        tool_settings.use_transform_correct_keep_connected = False

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

