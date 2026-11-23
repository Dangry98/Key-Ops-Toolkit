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

    to_surface: bpy.props.BoolProperty(
        name="Snap to Surface",
        description="Drop onto the nearest mesh face below instead of the grid floor. "
                    "Falls back to the grid floor when nothing is below",
        default=False,
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

    def draw(self, context):
        layout = self.layout
        if self.to_surface:
            layout.label(text="Snap to Surface", icon="SNAP_FACE")
        else:
            layout.label(text="Snap to Grid Floor", icon="VIEW_PERSPECTIVE")
        layout.prop(self, "to_surface")
        layout.prop(self, "individual")

    def execute(self, context):
        if not bpy.context.selected_objects:
            self.report({'WARNING'}, "No Objects Selected")
            return {'CANCELLED'}

        if self.to_surface:
            return self.snap_to_surface(context)

        depsgraph = bpy.context.evaluated_depsgraph_get()

        if not self.individual:
            all_bounds = []
            new_selected_objects = [o for o in context.selected_objects if o.type in ['MESH', 'CURVE', 'FONT', 'SURFACE', 'META']]

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
                    if obj.type in ['MESH', 'CURVE', 'SURFACE', 'FONT', 'META']:
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

    def snap_to_surface(self, context):
        """Drop the selection straight down onto the closest face of an unselected mesh."""
        from mathutils.bvhtree import BVHTree
        from ..utils.utilities import get_obj_coords

        context.view_layer.update()
        depsgraph = context.evaluated_depsgraph_get()
        selected = list(context.selected_objects)
        selected_set = set(selected)
        geo_types = {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}

        def world_points(objs):
            points = []
            for obj in objs:
                if obj.type in geo_types:
                    coords = get_obj_coords(obj, depsgraph=depsgraph)
                    if coords is not None and coords.size:
                        points.extend(Vector(c) for c in coords)
                elif obj.type in {'EMPTY', 'LATTICE'}:
                    points.append(obj.matrix_world.translation.copy())
            return points

        # World-space BVH trees for every visible, unselected mesh-like object
        trees = []
        for obj in context.visible_objects:
            if obj in selected_set or obj.type not in geo_types:
                continue
            ob_eval = obj.evaluated_get(depsgraph)
            mesh = ob_eval.to_mesh()
            if mesh.polygons:
                mw = obj.matrix_world
                verts = [mw @ v.co for v in mesh.vertices]
                polys = [tuple(p.vertices) for p in mesh.polygons]
                xs = [v.x for v in verts]
                ys = [v.y for v in verts]
                trees.append((BVHTree.FromPolygons(verts, polys),
                              min(xs), max(xs), min(ys), max(ys)))
            ob_eval.to_mesh_clear()

        down = Vector((0, 0, -1))
        eps = 1e-4

        def drop_distance(points):
            """Shortest downward distance from the points to a surface, or None."""
            if not points:
                return None
            min_x = min(p.x for p in points)
            max_x = max(p.x for p in points)
            min_y = min(p.y for p in points)
            max_y = max(p.y for p in points)
            near = [t[0] for t in trees
                    if t[1] <= max_x and t[2] >= min_x and t[3] <= max_y and t[4] >= min_y]
            best = None
            for tree in near:
                for p in points:
                    hit, _normal, _index, dist = tree.ray_cast(p + Vector((0, 0, eps)), down)
                    if hit is not None and (best is None or dist < best):
                        best = dist
            return None if best is None else best - eps

        missed = 0

        def move(objs, offset):
            for obj in objs:
                obj.matrix_world.translation.z -= offset

        if not self.individual:
            points = world_points(selected)
            if not points:
                return {'CANCELLED'}
            dist = drop_distance(points)
            if dist is None:
                missed += 1
                dist = min(p.z for p in points)
            move([o for o in selected if o.parent not in selected_set], dist)
        else:
            def drop_each(objs):
                nonlocal missed
                for obj in objs:
                    points = world_points([obj])
                    if not points:
                        continue
                    dist = drop_distance(points)
                    if dist is None:
                        missed += 1
                        dist = min(p.z for p in points)
                    move([obj], dist)
                    context.view_layer.update()

            drop_each(selected)
            children = [c for obj in selected for c in obj.children if c in selected_set]
            if children:
                drop_each(children)

        if missed:
            self.report({'INFO'}, "No surface below: snapped to the grid floor")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(SnapToFloor)
    register_snap_to_floor_keymaps()


def unregister():
    clear_registered_keymaps(registered_snap_to_floor_keymaps)
    bpy.utils.unregister_class(SnapToFloor)
