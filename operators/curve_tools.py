"""Curve helpers for the Q Menu: drag a curve's radius, and turn selected mesh edges into a curve."""
import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty


def _status(context, text):
    if context.workspace:
        context.workspace.status_text_set(text)


class KEYOPS_OT_curve_radius(bpy.types.Operator):
    """Drag to change the curve's thickness: in Object Mode its Bevel Depth, in Edit Mode the radius of the
    selected points"""
    bl_idname = "keyops.curve_radius"
    bl_label = "Curve Radius"
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}

    depth: FloatProperty(name="Depth", min=0.0, soft_max=10.0, subtype='DISTANCE', precision=4)  # type: ignore

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'CURVE' and context.mode in ('OBJECT', 'EDIT_CURVE')

    def execute(self, context):
        for obj in self._curves(context):
            obj.data.bevel_depth = self.depth
        return {'FINISHED'}

    def _curves(self, context):
        sel = [o for o in context.selected_objects if o.type == 'CURVE']
        return sel or [context.active_object]

    def invoke(self, context, event):
        if context.mode == 'EDIT_CURVE':
            # Blender's own radius tool already works on the selected points (Alt S)
            return bpy.ops.transform.transform('INVOKE_DEFAULT', mode='CURVE_SHRINKFATTEN')
        self.start = {o.name: o.data.bevel_depth for o in self._curves(context)}
        self.base = context.active_object.data.bevel_depth
        self.x0 = event.mouse_x
        # pixels to metres: about a tenth of the object's size per 100 px, at least a millimetre
        size = max(max(context.active_object.dimensions), 0.01)
        self.per_px = size / 1000.0
        self.depth = self.base
        context.window_manager.modal_handler_add(self)
        self._update(context, event)
        return {'RUNNING_MODAL'}

    def _update(self, context, event):
        step = self.per_px * (0.1 if event.shift else 1.0)
        depth = max(0.0, self.base + (event.mouse_x - self.x0) * step)
        if event.ctrl:
            snap = 10 ** round(__import__("math").log10(max(depth, 1e-4))) / 10.0
            depth = round(depth / snap) * snap
        self.depth = depth
        self.execute(context)
        _status(context, f"Radius {depth:.4f}    LMB Confirm   RMB/Esc Cancel   Shift Precise   Ctrl Snap")

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            self._update(context, event)
        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
            _status(context, None)
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            for obj in self._curves(context):
                if obj.name in self.start:
                    obj.data.bevel_depth = self.start[obj.name]
            _status(context, None)
            return {'CANCELLED'}
        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


class KEYOPS_OT_edges_to_curve(bpy.types.Operator):
    """Copy the selected edges into a new curve object (the mesh stays as it is), then drag its thickness"""
    bl_idname = "keyops.edges_to_curve"
    bl_label = "Edges to Curve"
    bl_options = {'REGISTER', 'UNDO'}

    stay_in_edit: BoolProperty(name="Stay in Edit Mode", default=False,
                               description="Keep editing the mesh instead of switching to the new curve")  # type: ignore
    depth: FloatProperty(name="Bevel Depth", default=0.0, min=0.0, soft_max=1.0, subtype='DISTANCE',
                         description="Give the new curve a round profile of this radius")  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        sources = [o for o in context.objects_in_mode_unique_data if o.type == 'MESH']
        made = []
        for src in sources:
            bm = bmesh.from_edit_mesh(src.data)
            edges = [e for e in bm.edges if e.select]
            if not edges:
                continue
            index = {}
            verts = []
            for e in edges:
                for v in e.verts:
                    if v.index not in index:
                        index[v.index] = len(verts)
                        verts.append(v.co.copy())
            me = bpy.data.meshes.new(src.name + "_curve")
            me.from_pydata(verts, [(index[e.verts[0].index], index[e.verts[1].index]) for e in edges], [])
            obj = bpy.data.objects.new(src.name + "_Curve", me)
            obj.matrix_world = src.matrix_world.copy()
            for coll in src.users_collection:
                coll.objects.link(obj)
            made.append(obj)
        if not made:
            self.report({'WARNING'}, "Select some edges first")
            return {'CANCELLED'}

        active = context.view_layer.objects.active
        was_selected = [o for o in context.selected_objects]
        bpy.ops.object.mode_set(mode='OBJECT')
        # convert works on the real selection (Blender 4.2 ignores an overridden one)
        for o in context.selected_objects:
            o.select_set(False)
        for obj in made:
            obj.select_set(True)
        context.view_layer.objects.active = made[0]
        bpy.ops.object.convert(target='CURVE')
        for obj in made:
            if obj.type == 'CURVE':
                obj.data.bevel_depth = self.depth
                obj.data.dimensions = '3D'
        if self.stay_in_edit:
            for obj in made:
                obj.select_set(False)
            for o in was_selected:
                o.select_set(True)
            context.view_layer.objects.active = active
            bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'}, f"Made {len(made)} curve{'s' if len(made) > 1 else ''}")
        return {'FINISHED'}

    def invoke(self, context, event):
        """Make the curve, then drag its thickness right away (like Radius)."""
        result = self.execute(context)
        if result == {'FINISHED'} and not self.stay_in_edit and context.area and context.area.type == 'VIEW_3D':
            bpy.ops.keyops.curve_radius('INVOKE_DEFAULT')
        return result


classes = (KEYOPS_OT_curve_radius, KEYOPS_OT_edges_to_curve)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
