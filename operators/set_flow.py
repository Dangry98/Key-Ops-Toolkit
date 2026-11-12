import bpy
import bmesh

from ..utils import mesh_utils as MeshUtils


class SetFlow(bpy.types.Operator):
    bl_idname = "mesh.set_mesh_edge_flow"
    bl_label = "Set Flow"
    bl_description = "Adjust curvature to match surface defined by edges crossing the edgeloop"
    bl_options = {'REGISTER', 'UNDO'}

    tension: bpy.props.IntProperty(name="Tension", default=180, min=-500, max=500)  # type: ignore
    iterations: bpy.props.IntProperty(name="Iterations", default=8, min=1, soft_max=32)  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.edit_object is not None and context.edit_object.type == 'MESH'

    def execute(self, context):
        objects = set(context.selected_editable_objects) if context.selected_editable_objects else {context.object}
        valid_objects = []

        for obj in objects:
            if obj.mode != 'EDIT' or obj.type != 'MESH':
                continue
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            edges = [edge for edge in bm.edges if edge.select]
            if not edges:
                continue
            valid_objects.append((obj, bm, MeshUtils._get_edgeloops(bm, edges)))

        if not valid_objects:
            self.report({'WARNING'}, "No edges selected")
            return {'CANCELLED'}

        for obj, bm, edgeloops in valid_objects:
            for _ in range(self.iterations):
                for edgeloop in edgeloops:
                    edgeloop.set_flow(tension=self.tension / 100.0, min_angle=0.0)

            bm.normal_update()
            bmesh.update_edit_mesh(obj.data)

        return {'FINISHED'}


def register_set_flow():
    bpy.utils.register_class(SetFlow)


def unregister_set_flow():
    bpy.utils.unregister_class(SetFlow)
