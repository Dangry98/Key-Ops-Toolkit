import bpy
import bmesh
from mathutils import Vector
from bpy_extras import view3d_utils


def update_edit_mesh(bm, mesh, destructive=False):
    bm.normal_update()
    bmesh.update_edit_mesh(mesh, loop_triangles=True, destructive=destructive)


def get_edge_normal(edge):
    linked_faces = edge.link_faces
    if linked_faces:
        normal = Vector((0.0, 0.0, 0.0))
        for face in linked_faces:
            normal += face.normal
        if normal.length > 1e-8:
            return normal.normalized()

    edge_dir = edge.verts[1].co - edge.verts[0].co
    if edge_dir.length < 1e-8:
        return Vector((0.0, 0.0, 1.0))

    edge_dir.normalize()
    up = Vector((0.0, 0.0, 1.0))
    if abs(edge_dir.dot(up)) > 0.99:
        up = Vector((1.0, 0.0, 0.0))
    return edge_dir.cross(up).normalized()


def find_original_vert(new_vert, new_verts):
    for edge in new_vert.link_edges:
        other = edge.other_vert(new_vert)
        if other not in new_verts:
            return other
    return None


def average_vectors(vectors):
    total = sum(vectors, Vector())
    return total.normalized() if total.length > 1e-8 else Vector((0.0, 0.0, 1.0))


class MESH_OT_extrude_edge_along_normals(bpy.types.Operator):
    """Extrude selected edges and slide the new geometry along edge normal(s)"""
    bl_idname = "mesh.extrude_edge_along_normals"
    bl_label = "Extrude Edge Along Normals"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    def _apply_distance(self, context, value=None):
        if not hasattr(self, 'vert_data') or not hasattr(self, 'bm'):
            return

        value = float(self.distance if value is None else value)
        self.offset = value
        for v, orig_co, n in self.vert_data:
            v.co = orig_co + n * value
        update_edit_mesh(self.bm, self.mesh)
        if context.area:
            context.area.header_text_set(f"Extrude Edge Along Normals: {value:.4f}")

    def _distance_updated(self, context):
        if getattr(self, '_updating_distance', False):
            return
        if not hasattr(self, 'vert_data') or not hasattr(self, 'bm'):
            return
        if not getattr(self, '_modal_running', False):
            return

        self._updating_distance = True
        try:
            self._apply_distance(context, self.distance)
        finally:
            self._updating_distance = False

    def _select_new_geometry(self):
        if not hasattr(self, 'bm') or not hasattr(self, 'vert_data'):
            return

        for v in self.bm.verts:
            v.select = False
        for e in self.bm.edges:
            e.select = False
        for f in self.bm.faces:
            f.select = False
        for nv, _, _ in self.vert_data:
            nv.select = True
        self.bm.select_flush(True)

    def _prepare_extrusion(self, context):
        self.obj = context.edit_object
        self.mesh = self.obj.data
        self.bm = bmesh.from_edit_mesh(self.mesh)

        selected_edges = [e for e in self.bm.edges if e.select]
        if not selected_edges:
            self.report({'WARNING'}, "No edges selected")
            return False

        vert_normals = {}
        for edge in selected_edges:
            normal = get_edge_normal(edge)
            vert_normals.setdefault(edge.verts[0], []).append(normal)
            vert_normals.setdefault(edge.verts[1], []).append(normal)

        for v, normals in vert_normals.items():
            vert_normals[v] = average_vectors(normals)

        self.avg_normal = average_vectors(list(vert_normals.values()))

        result = bmesh.ops.extrude_edge_only(self.bm, edges=selected_edges)
        new_verts = {g for g in result['geom'] if isinstance(g, bmesh.types.BMVert)}

        self.vert_data = []
        for new_vert in new_verts:
            old_vert = find_original_vert(new_vert, new_verts)
            normal = vert_normals.get(old_vert, self.avg_normal) if self.individual else self.avg_normal
            self.vert_data.append([new_vert, new_vert.co.copy(), normal])

        if not self.vert_data:
            update_edit_mesh(self.bm, self.mesh, destructive=True)
            return False

        self._select_new_geometry()
        self.offset = float(getattr(self, 'distance', 0.0))
        self.distance = self.offset
        return True

    def _setup_modal_state(self, context, event):
        self._modal_running = True
        self.start_mouse = Vector((event.mouse_x, event.mouse_y))
        self.region = context.region
        self.rv3d = context.region_data

        center_local = sum((co for _, co, _ in self.vert_data), Vector()) / len(self.vert_data)
        self.origin = self.obj.matrix_world @ center_local
        self.world_normal = (self.obj.matrix_world.to_3x3() @ self.avg_normal).normalized()

        update_edit_mesh(self.bm, self.mesh, destructive=True)
        context.window_manager.modal_handler_add(self)

    distance: bpy.props.FloatProperty(
        name="Distance",
        default=0.0,
        subtype='DISTANCE',
        update=_distance_updated,
    )  # type: ignore
    individual: bpy.props.BoolProperty(
        name="Individual Normals",
        description="Slide each new vertex along its own local normal "
                    "(Maya/Max style - preserves curvature) instead of one "
                    "averaged direction for the whole selection",
        default=True,
    )  # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "distance")
        layout.prop(self, "individual")

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH'
                and context.active_object is not None
                and context.active_object.type == 'MESH')

    def invoke(self, context, event):
        if context.region_data is None:
            self.report({'WARNING'}, "Run this from a 3D Viewport")
            return {'CANCELLED'}

        if not self._prepare_extrusion(context):
            return {'CANCELLED'}

        self._setup_modal_state(context, event)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if context.mode != 'EDIT_MESH':
            return {'CANCELLED'}

        obj = context.edit_object
        if obj is None or obj.type != 'MESH':
            return {'CANCELLED'}

        if not self._prepare_extrusion(context):
            return {'CANCELLED'}

        self._apply_distance(context, self.offset)
        return {'FINISHED'}

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}  # let the user orbit/zoom mid-extrude

        if event.type == 'MOUSEMOVE':
            self.offset = self.get_offset(event)
            self._updating_distance = True
            try:
                self.distance = self.offset
            finally:
                self._updating_distance = False
            self._apply_distance(context, self.offset)
            return {'RUNNING_MODAL'}

        if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            self._modal_running = False
            context.area.header_text_set(None)
            update_edit_mesh(self.bm, self.mesh)
            return {'FINISHED'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self._modal_running = False
            for v, orig_co, _ in self.vert_data:
                v.co = orig_co
            context.area.header_text_set(None)
            update_edit_mesh(self.bm, self.mesh)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def get_offset(self, event):
        mouse_now = Vector((event.mouse_x, event.mouse_y))
        p0 = view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, self.origin)
        p1 = view3d_utils.location_3d_to_region_2d(self.region, self.rv3d, self.origin + self.world_normal)

        if p0 is None or p1 is None or (p1 - p0).length < 1e-6:
            # Normal is edge-on to the view (or behind the camera) - fall
            # back to vertical mouse movement so the tool still responds.
            return (mouse_now - self.start_mouse).y * 0.01

        screen_dir = (p1 - p0).normalized()
        delta = mouse_now - self.start_mouse
        return delta.dot(screen_dir) * 0.01


class KEYOPS_OT_extrude_edge_along_normals_menu(bpy.types.Operator):
    """Menu-safe forwarder for Alt+E invocation."""
    bl_idname = "keyops.extrude_edge_along_normals_menu"
    bl_label = "Extrude Edge Along Normals"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH'
                and context.active_object is not None
                and context.active_object.type == 'MESH')

    def execute(self, context):
        return bpy.ops.mesh.extrude_edge_along_normals('INVOKE_DEFAULT')


def menu_func(self, context):
    self.layout.operator(KEYOPS_OT_extrude_edge_along_normals_menu.bl_idname,
                         text="Extrude Edge Along Normals")


classes = (MESH_OT_extrude_edge_along_normals, KEYOPS_OT_extrude_edge_along_normals_menu)


def register_extrude_edge_along_normals():
    if bpy.app.version >= (5, 4, 0):  # included by default in Blender 5.4
        return

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.VIEW3D_MT_edit_mesh_extrude.prepend(menu_func)


def unregister_extrude_edge_along_normals():
    if bpy.app.version >= (5, 4, 0):
        return

    if hasattr(bpy.types, "VIEW3D_MT_edit_mesh_extrude"):
        try:
            bpy.types.VIEW3D_MT_edit_mesh_extrude.remove(menu_func)
        except ValueError:
            pass

    for cls in reversed(classes):
        if cls.is_registered:
            bpy.utils.unregister_class(cls)


def register():
    if bpy.app.version < (5, 4, 0):
        register_extrude_edge_along_normals()


def unregister():
    if bpy.app.version < (5, 4, 0):
        unregister_extrude_edge_along_normals()