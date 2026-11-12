import bpy
from mathutils import Vector
from ..utils.pref_utils import clear_registered_keymaps

registered_snap_to_floor_keymaps = []


def register_snap_to_floor_keymaps():
    global registered_snap_to_floor_keymaps
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='Object Mode', space_type='EMPTY')
    kmi = km.keymap_items.new('keyops.snap_to_floor', 'THREE', 'PRESS', alt=True)
    registered_snap_to_floor_keymaps.append((km, kmi))


class SnapToFloor(bpy.types.Operator):
    bl_idname = "keyops.snap_to_floor"
    bl_label = "KeyOps: Snap To Floor"
    bl_description = "Snap the selected objects to the floor"
    bl_options = {'REGISTER', 'UNDO'}

    individual: bpy.props.BoolProperty(
        name="Individual",
        description="Snap each object to the floor individually (hold Alt when clicking button)",
        default=False,
        options={'SKIP_SAVE'}
    )  # type: ignore

    def invoke(self, context, event):
        global ev
        ev = []
        if event.ctrl:
            ev.append("Ctrl")
        if event.shift:
            ev.append("Shift")
        if event.alt:
            ev.append("Alt")

        if "Alt" in ev:
            self.individual = True
        else:
            self.individual = False

        return self.execute(context)

    def execute(self, context):
        if not bpy.context.selected_objects:
            self.report({'WARNING'}, "No Objects Selected")
            return {'CANCELLED'}

        depsgraph = bpy.context.evaluated_depsgraph_get()

        if not self.individual:
            all_bounds = []
            new_selected_objects = [o for o in context.selected_objects if o.type in ['MESH', 'CURVE', 'TEXT', 'SURFACE']]

            empty = [o for o in context.selected_objects if o.type in ['EMPTY', 'LATTICE']]
            from ..utils.utilities import get_AABB_bounding_box_coords
            all_bounds = get_AABB_bounding_box_coords(new_selected_objects)

            for obj in empty:
                all_bounds.append(obj.location)

            if not all_bounds:
                return {'CANCELLED'}

            z_min = min(v[2] for v in all_bounds)

            roots = [o for o in context.selected_objects if o.parent is None]
            for obj in roots:
                obj.matrix_world.translation -= Vector((0, 0, z_min))
        else:
            selection = bpy.context.selected_objects

            def move_individual_to_floor(selection):
                for obj in selection:
                    if obj.type in ['MESH', 'CURVE', 'TEXT', 'SURFACE', 'FONT', 'META']:
                        m = obj.evaluated_get(depsgraph)
                        me = m.to_mesh()

                        if me.vertices:
                            minz = float('inf')
                            for v in me.vertices:
                                z = (obj.matrix_world @ v.co).z
                                if z < minz:
                                    minz = z

                            obj.matrix_world.translation.z -= minz
                        m.to_mesh_clear()

                    elif obj.type == 'EMPTY':
                        obj.matrix_world.translation.z -= obj.location.z

            move_individual_to_floor(selection)
            selection = [child for obj in selection for child in obj.children]
            if selection:
                selection = [obj for obj in selection if obj in bpy.context.selected_objects]
                move_individual_to_floor(selection)

        return {'FINISHED'}


def register_snap_to_floor():
    bpy.utils.register_class(SnapToFloor)
    register_snap_to_floor_keymaps()


def unregister_snap_to_floor():
    clear_registered_keymaps(registered_snap_to_floor_keymaps)
    bpy.utils.unregister_class(SnapToFloor)
