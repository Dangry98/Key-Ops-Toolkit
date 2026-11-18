"""Extract Geometry: copy a mesh, or the selected part of it, into a new object and start editing that.

Object Mode: the selected meshes are copied. Edit Mode: what's selected is copied (whole faces, edges and
vertices; the original is left as it was), or the whole mesh when nothing is selected. The copies keep the
original's materials, UVs, attributes and place in the scene, start without modifiers (optional), and open
in Edit Mode with everything selected, so you can carry on working on just that piece.
"""

import bmesh
import bpy
from bpy.props import BoolProperty


def _extract(obj, selected_only, clear_modifiers):
    """A new object holding a copy of obj's mesh (or only its selected part). Returns it."""
    mesh = obj.data.copy()  # materials, UV maps and attributes come along
    if selected_only:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        if any(v.select for v in bm.verts):
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.select], context='VERTS')
        bm.to_mesh(mesh)
        bm.free()
    new = obj.copy()  # transform, vertex groups and parenting like the original
    new.data = mesh
    new.name = f"{obj.name}_Extract"
    mesh.name = new.name
    if clear_modifiers:
        new.modifiers.clear()
    for coll in obj.users_collection:
        coll.objects.link(new)
    return new


class KEYOPS_OT_extract_geometry(bpy.types.Operator):
    bl_idname = "keyops.extract_geometry"
    bl_label = "Extract Geometry"
    bl_description = ("Copy the selected geometry (or the whole mesh) into a new object, without modifiers, "
                      "and start editing it")
    bl_options = {'REGISTER', 'UNDO'}

    remove_modifiers: BoolProperty(name="Remove Modifiers", default=True,
                                   description="The new object starts without the original's modifiers") # type: ignore

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            return True
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        in_edit = context.mode == 'EDIT_MESH'
        if in_edit:
            sources = [o for o in (context.objects_in_mode_unique_data or [context.edit_object]) if o and o.type == 'MESH']
            for o in sources:
                o.update_from_editmode()  # the mesh data sees the current edit-mode selection
        else:
            sources = [o for o in context.selected_objects if o.type == 'MESH']
        if not sources:
            self.report({'WARNING'}, "Select a mesh")
            return {'CANCELLED'}
        if in_edit:
            bpy.ops.object.mode_set(mode='OBJECT')
        new = [_extract(o, in_edit, self.remove_modifiers) for o in sources]
        for o in context.view_layer.objects:
            o.select_set(False)
        for o in new:
            o.select_set(True)
        context.view_layer.objects.active = new[0]
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        self.report({'INFO'}, f"Extracted {len(new)} object{'s' if len(new) > 1 else ''}: now editing {new[0].name}")
        return {'FINISHED'}


def register_extract_geometry():
    bpy.utils.register_class(KEYOPS_OT_extract_geometry)


def unregister_extract_geometry():
    bpy.utils.unregister_class(KEYOPS_OT_extract_geometry)
