import bpy
import bmesh
from mathutils import Vector
from bpy_extras import view3d_utils


def get_edge_normal(edge):
    """Average normal of an edge's linked faces (this is what 'edge normal'
    means for a manifold/boundary edge). Falls back to a direction
    perpendicular to the edge itself for wire edges with no faces."""
    linked_faces = edge.link_faces
    if linked_faces:
        n = Vector((0.0, 0.0, 0.0))
        for f in linked_faces:
            n += f.normal
        if n.length > 1e-8:
            return n.normalized()
    edge_dir = edge.verts[1].co - edge.verts[0].co
    if edge_dir.length < 1e-8:
        return Vector((0.0, 0.0, 1.0))
    edge_dir.normalize()
    up = Vector((0.0, 0.0, 1.0))
    if abs(edge_dir.dot(up)) > 0.99:
        up = Vector((1.0, 0.0, 0.0))
    return edge_dir.cross(up).normalized()


class MESH_OT_extrude_edge_along_normals(bpy.types.Operator):
    """Extrude selected edges and slide the new geometry along edge normal(s)"""
    bl_idname = "mesh.extrude_edge_along_normals"
    bl_label = "Extrude Edge Along Normals"
    bl_options = {'REGISTER', 'UNDO'}

    individual: bool = bpy.props.BoolProperty(
        name="Individual Normals",
        description="Slide each new vertex along its own local normal "
                    "(Maya/Max style - preserves curvature) instead of one "
                    "averaged direction for the whole selection",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'EDIT_MESH'
                and context.active_object is not None
                and context.active_object.type == 'MESH')

    def invoke(self, context, event):
        if context.region_data is None:
            self.report({'WARNING'}, "Run this from a 3D Viewport")
            return {'CANCELLED'}

        self.obj = context.edit_object
        self.mesh = self.obj.data
        self.bm = bmesh.from_edit_mesh(self.mesh)

        sel_edges = [e for e in self.bm.edges if e.select]
        if not sel_edges:
            self.report({'WARNING'}, "No edges selected")
            return {'CANCELLED'}

        # Normal per original vertex, averaged over every selected edge
        # touching it. Computed BEFORE extruding - link_faces changes as
        # soon as the new geometry exists.
        vert_normals = {}
        for e in sel_edges:
            n = get_edge_normal(e)
            vert_normals.setdefault(e.verts[0], []).append(n)
            vert_normals.setdefault(e.verts[1], []).append(n)
        for v, normals in vert_normals.items():
            total = sum(normals, Vector())
            vert_normals[v] = total.normalized() if total.length > 1e-8 else Vector((0.0, 0.0, 1.0))

        avg_normal = sum(vert_normals.values(), Vector())
        avg_normal = avg_normal.normalized() if avg_normal.length > 1e-8 else Vector((0.0, 0.0, 1.0))

        ret = bmesh.ops.extrude_edge_only(self.bm, edges=sel_edges)
        geom = ret['geom']
        new_verts = set(g for g in geom if isinstance(g, bmesh.types.BMVert))
        new_edges = [g for g in geom if isinstance(g, bmesh.types.BMEdge)]

        # "Rail" edges connect an original vertex to its new duplicate -
        # exactly one endpoint is new. That gives a reliable old -> new
        # vertex mapping without relying on list order or coordinates.
        new_to_old = {}
        for e in new_edges:
            v1, v2 = e.verts
            if (v1 in new_verts) != (v2 in new_verts):
                old_v, new_v = (v2, v1) if v1 in new_verts else (v1, v2)
                new_to_old[new_v] = old_v

        self.vert_data = []
        for nv in new_verts:
            old_v = new_to_old.get(nv)
            n = vert_normals.get(old_v, avg_normal) if self.individual else avg_normal
            self.vert_data.append([nv, nv.co.copy(), n])

        if not self.vert_data:
            bmesh.update_edit_mesh(self.mesh)
            return {'CANCELLED'}

        for v in self.bm.verts:
            v.select = False
        for e in self.bm.edges:
            e.select = False
        for f in self.bm.faces:
            f.select = False
        for nv, _, _ in self.vert_data:
            nv.select = True
        self.bm.select_flush(True)

        self.offset = 0.0
        self.start_mouse = Vector((event.mouse_x, event.mouse_y))
        self.region = context.region
        self.rv3d = context.region_data

        center_local = sum((co for _, co, _ in self.vert_data), Vector()) / len(self.vert_data)
        self.origin = self.obj.matrix_world @ center_local
        self.world_normal = (self.obj.matrix_world.to_3x3() @ avg_normal).normalized()

        bmesh.update_edit_mesh(self.mesh)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}  # let the user orbit/zoom mid-extrude

        if event.type == 'MOUSEMOVE':
            self.offset = self.get_offset(event)
            for v, orig_co, n in self.vert_data:
                v.co = orig_co + n * self.offset
            bmesh.update_edit_mesh(self.mesh)
            context.area.header_text_set(f"Extrude Edge Along Normals: {self.offset:.4f}")
            return {'RUNNING_MODAL'}

        if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            context.area.header_text_set(None)
            bmesh.update_edit_mesh(self.mesh)
            return {'FINISHED'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            for v, orig_co, _ in self.vert_data:
                v.co = orig_co
            context.area.header_text_set(None)
            bmesh.update_edit_mesh(self.mesh)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def get_offset(self, event):
        """Project mouse movement onto the on-screen direction of the
        extrude normal. This is the same trick Blender's own axis-
        constrained translate uses to turn free 2D mouse motion into 1D
        motion along an arbitrary 3D axis: project the axis endpoints to
        screen space, then dot the mouse delta against that 2D direction."""
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
    for c in classes:
            bpy.utils.register_class(c)

    bpy.types.VIEW3D_MT_edit_mesh_extrude.prepend(menu_func)
  


def unregister_extrude_edge_along_normals():
    bpy.types.VIEW3D_MT_edit_mesh_extrude.remove(menu_func)


    for c in reversed(classes):
        bpy.utils.unregister_class(c)
  

def register():
    register_extrude_edge_along_normals()


def unregister():
    unregister_extrude_edge_along_normals()


if __name__ == "__main__":
    register()