import bpy
import bmesh
from bpy.types import Menu, Operator
from bpy.props import EnumProperty, BoolProperty, FloatVectorProperty
from mathutils import Vector
from ..utils.pref_utils import clear_registered_keymaps


registered_flatten_pie_keymaps = []

DIRECTIONS = [
    ("LEFT", "Left", "Flatten onto the left most point of the selection"),
    ("RIGHT", "Right", "Flatten onto the right most point of the selection"),
    ("TOP", "Top", "Flatten onto the top most point of the selection"),
    ("BOTTOM", "Bottom", "Flatten onto the bottom most point of the selection"),
]


def _snap_to_world_axis(vec):
    """Return the world axis (signed) closest to vec."""
    i = max(range(3), key=lambda n: abs(vec[n]))
    axis = Vector((0.0, 0.0, 0.0))
    axis[i] = 1.0 if vec[i] >= 0 else -1.0
    return axis


class KEYOPS_OT_flatten(Operator):
    bl_idname = "keyops.flatten"
    bl_label = "Flatten"
    bl_description = "Flatten the selection along the view direction, onto the outer most selected point in that direction"
    bl_options = {'UNDO'}

    direction: EnumProperty(name="Direction", items=DIRECTIONS, default="RIGHT") # type: ignore
    snap_to_world_axis: BoolProperty(name="Snap to World Axis", description="Use the world axis closest to the view direction instead of the exact view direction", default=True) # type: ignore
    view_right: FloatVectorProperty(options={'HIDDEN', 'SKIP_SAVE'}, size=3) # type: ignore
    view_up: FloatVectorProperty(options={'HIDDEN', 'SKIP_SAVE'}, size=3) # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        rv3d = context.region_data
        if rv3d is None:
            self.report({'WARNING'}, "Flatten needs a 3D Viewport")
            return {'CANCELLED'}
        rot = rv3d.view_rotation
        self.view_right = rot @ Vector((1.0, 0.0, 0.0))
        self.view_up = rot @ Vector((0.0, 1.0, 0.0))
        return self.execute(context)

    def get_axis(self):
        right = Vector(self.view_right)
        up = Vector(self.view_up)
        if right.length == 0 or up.length == 0:
            return None
        axis_map = {
            "LEFT": -right,
            "RIGHT": right,
            "TOP": up,
            "BOTTOM": -up,
        }
        axis = axis_map[self.direction]
        return _snap_to_world_axis(axis) if self.snap_to_world_axis else axis.normalized()

    def execute(self, context):
        axis = self.get_axis()
        if axis is None:
            # Ran without invoke (e.g. from script), fall back to the current view
            rv3d = context.region_data
            if rv3d is None:
                self.report({'WARNING'}, "Flatten needs a 3D Viewport")
                return {'CANCELLED'}
            rot = rv3d.view_rotation
            self.view_right = rot @ Vector((1.0, 0.0, 0.0))
            self.view_up = rot @ Vector((0.0, 1.0, 0.0))
            axis = self.get_axis()

        objects = [o for o in context.objects_in_mode_unique_data if o.type == 'MESH']

        data = []
        values = []
        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            verts = [v for v in bm.verts if v.select and not v.hide]
            if not verts:
                continue
            mw = obj.matrix_world
            for v in verts:
                values.append((mw @ v.co).dot(axis))
            data.append((obj, bm, verts))

        if not values:
            self.report({'INFO'}, "Nothing selected")
            return {'CANCELLED'}

        target = max(values)

        for obj, bm, verts in data:
            mw = obj.matrix_world
            mw_inv = mw.inverted_safe()
            for v in verts:
                world_co = mw @ v.co
                world_co += axis * (target - world_co.dot(axis))
                v.co = mw_inv @ world_co
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


class KEYOPS_MT_flatten_pie(Menu):
    bl_idname = "KEYOPS_MT_flatten_pie"
    bl_label = "Flatten"

    def draw(self, context):
        pie = self.layout.menu_pie()

        pie.operator("keyops.flatten", text="Left", icon="TRIA_LEFT").direction = "LEFT" #LEFT
        pie.operator("keyops.flatten", text="Right", icon="TRIA_RIGHT").direction = "RIGHT" #RIGHT
        pie.operator("keyops.flatten", text="Bottom", icon="TRIA_DOWN").direction = "BOTTOM" #BOTTOM
        pie.operator("keyops.flatten", text="Top", icon="TRIA_UP").direction = "TOP" #TOP


def register_flatten_pie_keymaps():
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='Mesh', space_type='EMPTY')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'THREE', 'PRESS', alt=True)
    kmi.properties.name = 'KEYOPS_MT_flatten_pie'
    registered_flatten_pie_keymaps.append((km, kmi))


def register_flatten_pie():
    bpy.utils.register_class(KEYOPS_OT_flatten)
    bpy.utils.register_class(KEYOPS_MT_flatten_pie)
    register_flatten_pie_keymaps()


def unregister_flatten_pie():
    clear_registered_keymaps(registered_flatten_pie_keymaps)
    bpy.utils.unregister_class(KEYOPS_MT_flatten_pie)
    bpy.utils.unregister_class(KEYOPS_OT_flatten)
