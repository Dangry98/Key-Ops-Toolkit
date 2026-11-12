import math

import bmesh
import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

ZERO_VEC = Vector((0.0, 0.0, 0.0))
Z_UP = Vector((0.0, 0.0, 1.0))


class OffsetExtrudeEdge(bpy.types.Operator):
    """Offset extrude selected edges in edge-normal direction"""

    bl_idname = "mesh.offset_extrude_edge"
    bl_label = "Offset Extrude Edge"
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}

    width: bpy.props.FloatProperty(name="Distance", default=0.0, subtype="DISTANCE", options={'SKIP_SAVE'})  # type: ignore
    angle: bpy.props.FloatProperty(name="Angle", subtype="ANGLE", default=0.0, step=5   )  # type: ignore
    threshold: bpy.props.FloatProperty(
        name="Flat Face Threshold",
        subtype="ANGLE",
        default=math.radians(0.05),
        min=0.0,
        max=math.radians(45.0),
    )  # type: ignore

    _bm_backup = None
    _mouse_start = None
    _mouse_prev = None
    _factor = 0.001
    _base_width = 0.0
    _base_angle = 0.0

    @staticmethod
    def _get_edit_mesh_object(context):
        obj = context.edit_object
        if obj is None:
            obj = context.active_object
        if obj is None:
            return None
        if obj.type != "MESH":
            return None
        if obj.mode != "EDIT":
            return None
        return obj

    @classmethod
    def poll(cls, context):
        return cls._get_edit_mesh_object(context) is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "width")
        layout.prop(self, "angle")
        layout.prop(self, "threshold")

    def _apply_offset_extrude(self, context):
        obj = self._get_edit_mesh_object(context)
        if obj is None:
            self.report({"WARNING"}, "No active edit mesh object.")
            return False

        me = obj.data
        bpy.ops.object.mode_set(mode="OBJECT")
        bm = bmesh.new()
        bm.from_mesh(me)

        set_edges_orig = gather_offset_candidate_edges(bm)
        if set_edges_orig is None:
            bm.free()
            bpy.ops.object.mode_set(mode="EDIT")
            self.report({"WARNING"}, "No valid edges are selected.")
            return False

        loops = build_edge_loops(set_edges_orig)
        if loops is None:
            bm.free()
            bpy.ops.object.mode_set(mode="EDIT")
            self.report({"WARNING"}, "Overlapping edge loops detected. Select discrete loops.")
            return False

        vec_upward = Vector((1.0, 1.0, 1.0)).normalized()
        offset_infos = []
        for loop_data in loops:
            verts, directions = compute_offset_directions(
                loop_data,
                vec_upward,
                Z_UP,
                None,
                follow_face=False,
                edge_rail=False,
                edge_rail_only_end=False,
                threshold=self.threshold,
            )
            if verts:
                offset_infos.append((verts, directions))

        width = self.width * math.cos(self.angle)
        depth = self.width * math.sin(self.angle)

        geom_ex = extrude_selected_edges(bm, list(set_edges_orig))
        for verts, directions in offset_infos:
            apply_offset_to_vertices(width, depth, verts, directions, geom_ex)

        cleanup_selection_after_extrude(bm, "extrude", list(set_edges_orig), geom_ex)
        bm.to_mesh(me)
        bm.free()
        bpy.ops.object.mode_set(mode="EDIT")
        return True

    def _restore_backup_mesh(self, context):
        if self._bm_backup is None:
            return False

        obj = self._get_edit_mesh_object(context)
        if obj is None:
            return False

        me = obj.data
        bpy.ops.object.mode_set(mode="OBJECT")
        self._bm_backup.to_mesh(me)
        bpy.ops.object.mode_set(mode="EDIT")
        bmesh.update_edit_mesh(me, destructive=True)
        return True

    def _rebuild_preview(self, context):
        if self._bm_backup is not None:
            if not self._restore_backup_mesh(context):
                return
        self._apply_offset_extrude(context)

    def execute(self, context):
        if not self._apply_offset_extrude(context):
            return {"CANCELLED"}
        return {"FINISHED"}

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Run this operator from the 3D View.")
            return {"CANCELLED"}

        obj = self._get_edit_mesh_object(context)
        if obj is None:
            self.report({"WARNING"}, "Switch to Mesh Edit Mode first.")
            return {"CANCELLED"}

        bpy.ops.object.mode_set(mode="OBJECT")
        self._bm_backup = bmesh.new()
        self._bm_backup.from_mesh(obj.data)
        bpy.ops.object.mode_set(mode="EDIT")

        self._mouse_start = Vector((event.mouse_x, event.mouse_y))
        self._mouse_prev = self._mouse_start.copy()
        self._base_width = self.width
        self._base_angle = self.angle
        self._factor = self._compute_mouse_distance_scale(context)

        context.window_manager.modal_handler_add(self)
        context.area.header_text_set(self._header_text())
        self._rebuild_preview(context)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if context.area is None:
            self._restore_backup(context)
            return {"CANCELLED"}

        if event.type in {"RIGHTMOUSE", "ESC"}:
            self._restore_backup(context)
            context.area.header_text_set(text=None)
            return {"CANCELLED"}

        if event.type == "LEFTMOUSE":
            context.area.header_text_set(text=None)
            self._cleanup_backup()
            return {"FINISHED"}

        if event.type == "R" and event.value == "PRESS":
            self.angle = 0.0
            self._base_angle = 0.0
            self._mouse_start = Vector((event.mouse_x, event.mouse_y))
            self._mouse_prev = self._mouse_start.copy()
            self._rebuild_preview(context)
            context.area.header_text_set(self._header_text())
            return {"RUNNING_MODAL"}

        if event.type == "MOUSEMOVE":
            mouse_now = Vector((event.mouse_x, event.mouse_y))
            delta = mouse_now - self._mouse_prev
            precision = 0.2 if event.shift else 1.0

            if event.alt:
                self.angle += delta.y * 0.01 * precision
                if event.ctrl:
                    snap_scene = bpy.data.scenes.get("Scene")
                    if snap_scene is not None:
                        snap_step = snap_scene.tool_settings.snap_angle_increment_3d
                        if snap_step > 0.0:
                            self.angle = round(self.angle / snap_step) * snap_step
            else:
                self.width += delta.x * self._factor * precision

            self._mouse_prev = mouse_now

            self._rebuild_preview(context)
            context.area.header_text_set(self._header_text())
            return {"RUNNING_MODAL"}

        return {"RUNNING_MODAL"}

    def _header_text(self):
        angle_deg = math.degrees(self.angle)
        return (
            f"Distance: {self.width:.4f}  Angle: {angle_deg:.2f}  "
            "LMB Confirm  RMB/ESC Cancel  Alt Angle  Ctrl Snap Angle  R Reset Angle"
        )

    def _restore_backup(self, context):
        if self._bm_backup is None:
            return

        obj = self._get_edit_mesh_object(context)
        if obj is None:
            self._cleanup_backup()
            return

        me = obj.data
        bpy.ops.object.mode_set(mode="OBJECT")
        self._bm_backup.to_mesh(me)
        bpy.ops.object.mode_set(mode="EDIT")
        bmesh.update_edit_mesh(me, destructive=True)
        self._cleanup_backup()

    def _cleanup_backup(self):
        if self._bm_backup is not None:
            self._bm_backup.free()
            self._bm_backup = None

    def _compute_mouse_distance_scale(self, context):
        obj = self._get_edit_mesh_object(context)
        if obj is None:
            return 0.001

        reg = context.region
        reg3d = context.space_data.region_3d
        if reg is None or reg3d is None or reg.width <= 0:
            return 0.001

        bm = bmesh.from_edit_mesh(obj.data)
        selected_verts = [vert for vert in bm.verts if vert.select]
        if not selected_verts:
            return 0.001

        co_center = Vector((0.0, 0.0, 0.0))
        for vert in selected_verts:
            co_center += vert.co
        co_center /= float(len(selected_verts))

        world_loc = obj.matrix_world @ co_center
        left = view3d_utils.region_2d_to_location_3d(reg, reg3d, Vector((0.0, 0.0)), world_loc)
        right = view3d_utils.region_2d_to_location_3d(reg, reg3d, Vector((float(reg.width), 0.0)), world_loc)

        local_vec = obj.matrix_world.inverted_safe() @ (right - left)
        return local_vec.length / float(reg.width)




def draw_menu(self, context):
    if context.mode == "EDIT_MESH":
        self.layout.operator_context = "INVOKE_DEFAULT"
        self.layout.operator(OffsetExtrudeEdge.bl_idname, text="Offset Extrude Edge")


def register_offset_extrude_edge():
    bpy.utils.register_class(OffsetExtrudeEdge)
    bpy.types.VIEW3D_MT_edit_mesh_extrude.prepend(draw_menu)


def unregister_offset_extrude_edge():
    bpy.types.VIEW3D_MT_edit_mesh_extrude.remove(draw_menu)
    bpy.utils.unregister_class(OffsetExtrudeEdge)




# Legacy helper math kept for modal solver parity.
def calculate_loop_normal(verts, fallback=Z_UP):
    normal = ZERO_VEC.copy()

    if verts[0] is verts[-1]:
        range_verts = range(1, len(verts))
    else:
        range_verts = range(0, len(verts))

    for i in range_verts:
        v1co, v2co = verts[i - 1].co, verts[i].co
        normal.x += (v1co.y - v2co.y) * (v1co.z + v2co.z)
        normal.y += (v1co.z - v2co.z) * (v1co.x + v2co.x)
        normal.z += (v1co.x - v2co.x) * (v1co.y + v2co.y)

    if normal != ZERO_VEC:
        normal.normalize()
    else:
        normal = fallback

    return normal


def gather_offset_candidate_edges(bm):
    set_edges_orig = set()
    for e in bm.edges:
        if e.select:
            co_faces_selected = 0
            for f in e.link_faces:
                if f.select:
                    co_faces_selected += 1
                    if co_faces_selected == 2:
                        break
            else:
                set_edges_orig.add(e)

    if not set_edges_orig:
        return None

    return set_edges_orig


def build_edge_loops(set_edges_orig):
    set_edges_copy = set_edges_orig.copy()

    loops = []
    while set_edges_copy:
        edge_start = set_edges_copy.pop()
        v_left, v_right = edge_start.verts
        lp = [v_left, edge_start, v_right]
        reverse = False
        while True:
            edge = None
            for e in v_right.link_edges:
                if e in set_edges_copy:
                    if edge:
                        return None
                    edge = e
                    set_edges_copy.remove(e)
            if edge:
                v_right = edge.other_vert(v_right)
                lp.extend((edge, v_right))
                continue
            if v_right is v_left:
                loops.append(lp)
                break
            if reverse is False:
                lp.reverse()
                v_right, v_left = v_left, v_right
                reverse = True
                continue
            loops.append(lp)
            break
    return loops


def get_adjacent_faces(edges):
    adj_faces = []
    for e in edges:
        adj_f = None
        co_adj = 0
        for f in e.link_faces:
            if not f.hide and f.normal != ZERO_VEC:
                adj_f = f
                co_adj += 1
                if f.select:
                    adj_faces.append(adj_f)
                    break
        else:
            if co_adj == 1:
                adj_faces.append(adj_f)
            else:
                adj_faces.append(None)
    return adj_faces


def get_edge_rail_direction(vert, set_edges_orig):
    co_edges = co_edges_selected = 0
    vec_inner = None
    for e in vert.link_edges:
        if (e not in set_edges_orig and
           (e.select or (co_edges_selected == 0 and not e.hide))):
            v_other = e.other_vert(vert)
            vec = v_other.co - vert.co
            if vec != ZERO_VEC:
                vec_inner = vec
                if e.select:
                    co_edges_selected += 1
                    if co_edges_selected == 2:
                        return None
                else:
                    co_edges += 1
    if co_edges_selected == 1:
        vec_inner.normalize()
        return vec_inner
    if co_edges == 1:
        vec_inner.normalize()
        return vec_inner
    return None


def get_cross_rail_direction(vec_tan, vec_edge_r, vec_edge_l, normal_r, normal_l):
    vec_cross = normal_r.cross(normal_l)
    if vec_cross.dot(vec_tan) < .0:
        vec_cross *= -1
    cos_min = min(vec_tan.dot(vec_edge_r), vec_tan.dot(-vec_edge_l))
    cos = vec_tan.dot(vec_cross)
    if cos >= cos_min:
        vec_cross.normalize()
        return vec_cross
    return None


def get_mirror_rail_direction(mirror_plane, vec_up):
    p_norm = mirror_plane[1]
    mirror_rail = vec_up.cross(p_norm)
    if mirror_rail != ZERO_VEC:
        mirror_rail.normalize()
        vec_up = vec_up - vec_up.project(p_norm)
        vec_up.normalize()
        return mirror_rail, vec_up
    return None, vec_up


def align_loop_winding(verts, edges, lp_normal, adj_faces):
    for i, adj_f in enumerate(adj_faces):
        if adj_f is None:
            continue
        v1, v2 = verts[i], verts[i + 1]
        fv = tuple(adj_f.verts)
        if fv[fv.index(v1) - 1] is v2:
            verts.reverse()
            edges.reverse()
            adj_faces.reverse()
        if lp_normal.dot(adj_f.normal) < .0:
            lp_normal *= -1
        break
    else:
        for v in verts:
            if v.normal != ZERO_VEC:
                if lp_normal.dot(v.normal) < .0:
                    verts.reverse()
                    edges.reverse()
                    lp_normal *= -1
                break

    return verts, edges, lp_normal, adj_faces


def compute_offset_directions(lp, vec_upward, normal_fallback, vert_mirror_pairs, **options):
    opt_follow_face = options['follow_face']
    opt_edge_rail = options['edge_rail']
    opt_er_only_end = options['edge_rail_only_end']
    opt_threshold = options['threshold']

    verts, edges = lp[::2], lp[1::2]
    set_edges = set(edges)
    lp_normal = calculate_loop_normal(verts, fallback=normal_fallback)

    if lp_normal.dot(vec_upward) < .0:
        verts.reverse()
        edges.reverse()
        lp_normal *= -1

    if opt_follow_face:
        adj_faces = get_adjacent_faces(edges)
        verts, edges, lp_normal, adj_faces = align_loop_winding(verts, edges, lp_normal, adj_faces)
    else:
        adj_faces = (None,) * len(edges)

    vec_edges = tuple((e.other_vert(v).co - v.co).normalized() for v, e in zip(verts, edges))

    if verts[0] is verts[-1]:
        verts.pop()
        half_loop = False
    else:
        half_loop = True

    len_verts = len(verts)
    directions = []
    for i in range(len_verts):
        vert = verts[i]
        ix_right, ix_left = i, i - 1

        vert_end = False
        if half_loop:
            if i == 0:
                ix_left = ix_right
                vert_end = True
            elif i == len_verts - 1:
                ix_right = ix_left
                vert_end = True

        edge_right, edge_left = vec_edges[ix_right], vec_edges[ix_left]
        face_right, face_left = adj_faces[ix_right], adj_faces[ix_left]

        norm_right = face_right.normal if face_right else lp_normal
        norm_left = face_left.normal if face_left else lp_normal
        two_normals = norm_right.angle(norm_left) > opt_threshold

        tan_right = edge_right.cross(norm_right).normalized()
        tan_left = edge_left.cross(norm_left).normalized()
        tan_avr = (tan_right + tan_left).normalized()
        norm_avr = (norm_right + norm_left).normalized()

        rail = None
        if two_normals or opt_edge_rail:
            if two_normals or (not opt_er_only_end) or vert_end:
                rail = get_edge_rail_direction(vert, set_edges)
        if vert_mirror_pairs and vert_end:
            if vert in vert_mirror_pairs:
                rail, norm_avr = get_mirror_rail_direction(vert_mirror_pairs[vert], norm_avr)
        if (not rail) and two_normals:
            rail = get_cross_rail_direction(tan_avr, edge_right, edge_left, norm_right, norm_left)
        if rail:
            dot = tan_avr.dot(rail)
            if dot > .0:
                tan_avr = rail
            elif dot < .0:
                tan_avr = -rail

        vec_plane = norm_avr.cross(tan_avr)
        e_dot_p_r = edge_right.dot(vec_plane)
        e_dot_p_l = edge_left.dot(vec_plane)
        if e_dot_p_r or e_dot_p_l:
            if e_dot_p_r > e_dot_p_l:
                vec_edge, e_dot_p = edge_right, e_dot_p_r
            else:
                vec_edge, e_dot_p = edge_left, e_dot_p_l

            vec_tan = (tan_avr - tan_avr.project(vec_edge)).normalized()
            vec_up = vec_tan.cross(vec_edge)

            vec_width = vec_tan - (vec_tan.dot(vec_plane) / e_dot_p) * vec_edge
            vec_depth = vec_up - (vec_up.dot(vec_plane) / e_dot_p) * vec_edge
        else:
            vec_width = tan_avr
            vec_depth = norm_avr

        directions.append((vec_width, vec_depth))

    return verts, directions


def apply_offset_to_vertices(width, depth, verts, directions, geom_ex):
    if geom_ex:
        geom_s = geom_ex['side']
        verts_ex = []
        for v in verts:
            for e in v.link_edges:
                if e in geom_s:
                    verts_ex.append(e.other_vert(v))
                    break
        verts = verts_ex

    for v, (vec_width, vec_depth) in zip(verts, directions):
        v.co += width * vec_width + depth * vec_depth


def extrude_selected_edges(bm, edges_orig):
    extruded = bmesh.ops.extrude_edge_only(bm, edges=edges_orig)['geom']
    n_edges = n_faces = len(edges_orig)
    n_verts = len(extruded) - n_edges - n_faces

    geom = dict()
    geom['verts'] = verts = set(extruded[:n_verts])
    geom['edges'] = edges = set(extruded[n_verts:n_verts + n_edges])
    geom['faces'] = set(extruded[n_verts + n_edges:])
    geom['side'] = set(e for v in verts for e in v.link_edges if e not in edges)

    return geom


def cleanup_selection_after_extrude(bm, mode, edges_orig, geom_ex=None):
    for f in bm.faces:
        f.select = False
    if geom_ex:
        for e in geom_ex['edges']:
            e.select = True
        if mode == 'offset':
            lis_geom = list(geom_ex['side']) + list(geom_ex['faces'])
            bmesh.ops.delete(bm, geom=lis_geom, context='EDGES')
    else:
        for e in edges_orig:
            e.select = True
