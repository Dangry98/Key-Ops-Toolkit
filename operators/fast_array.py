import bpy
from mathutils import Vector

ARRAY_SLOTS = ("Array", "Array.001", "Array.002")
AXIS_NAMES = ("X", "Y", "Z")
EPS = 1e-6

_running_op = None  # the FastArray instance whose keymap is drawn in the status bar


def _valid_icon(name):
    try:
        items = bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items
        return name if name in items else 'NONE'
    except Exception:
        return 'NONE'


def _draw_status(header, context):
    layout = header.layout
    op = _running_op
    if op is None:
        return

    row = layout.row(align=True)

    def item(icons, text):
        for icon in icons:
            row.label(text="", icon=_valid_icon(icon))
        row.label(text=text)
        row.separator(factor=2.0)

    item(('MOUSE_LMB',), "Confirm")
    item(('MOUSE_RMB',), "Cancel")
    item(('MOUSE_MOVE',), "Offset")
    item(('EVENT_SHIFT',), "Precise")
    item(('EVENT_CTRL',), "Snap")
    item(('MOUSE_MMB_SCROLL',), f"Count ({op.current_count()})")
    item(('EVENT_SHIFT', 'MOUSE_MMB_SCROLL'), "Move Modifier")
    item(('EVENT_X', 'EVENT_Y', 'EVENT_Z'), "Axis")
    item(('EVENT_SHIFT', 'EVENT_X'), "Toggle Axis")
    item(('EVENT_R',), "Relative" + (" ✓" if op.relative else ""))
    item(('EVENT_C',), "Constant" + ("" if op.relative else " ✓"))
    row.label(text="1 / 2 / 3")
    row.label(text=f"Array Slot ({op.active_name})")
    row.separator(factor=2.0)
    item(('EVENT_Q', 'EVENT_W'), "Modifier Up / Down")
    if context.mode == 'OBJECT':
        item(('EVENT_S',), "Apply Scale")


class FastArray(bpy.types.Operator):
    bl_idname = "keyops.fast_array"
    bl_label = "Fast Array"
    bl_description = ("Add or adjust an Array modifier interactively.\n"
                      "Drag to set the offset, scroll for count, X/Y/Z for axis, "
                      "R/C for relative/constant, 1/2/3 for up to three arrays")
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    # ------------------------------------------------------------------ setup

    def invoke(self, context, event):
        global _running_op

        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Active space must be a 3D Viewport")
            return {'CANCELLED'}

        self.objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not self.objects:
            self.report({'WARNING'}, "Select at least one mesh object")
            return {'CANCELLED'}

        active = context.active_object
        self.ref_obj = active if active in self.objects else self.objects[0]
        self.area = context.area
        self.region = context.region

        self.backup = {}       # (obj, mod name) -> original state, for cancel
        self.base = {}         # obj -> offset vector the current drag starts from
        self.drag = 0.0
        self.relative = True
        self.axes = [True, False, False]
        self.last_x = event.mouse_x
        self.skip_next_move = False

        self.activate_slot(0)

        context.window_manager.modal_handler_add(self)
        context.window.cursor_modal_set('SCROLL_X')
        _running_op = self
        try:
            context.workspace.status_text_set(_draw_status)
        except Exception:
            context.workspace.status_text_set(
                "LMB Confirm | RMB Cancel | Move Offset | Wheel Count | X/Y/Z Axis | R/C Relative/Constant | 1/2/3 Slot")
        self.update_header()
        return {'RUNNING_MODAL'}

    # ------------------------------------------------------------- modifiers

    def nonzero_axes(self, obj):
        axes = [i for i in range(3) if obj.dimensions[i] > EPS]
        return axes

    def default_axis(self, obj, slot):
        axes = self.nonzero_axes(obj)
        if not axes:
            return 0
        return axes[min(slot, len(axes) - 1)]

    def get_or_create(self, obj, name, slot):
        mod = obj.modifiers.get(name)
        created = False
        if mod is None or mod.type != 'ARRAY':
            if mod is not None:  # name taken by another modifier type
                name = name + "_Array"
                mod = obj.modifiers.get(name)
            if mod is None:
                mod = obj.modifiers.new(name=name, type='ARRAY')
                created = True
                self.setup_new_array(obj, mod, slot)

        key = (obj, mod.name)
        if key not in self.backup:
            self.backup[key] = {
                "created": created,
                "count": mod.count,
                "use_relative": mod.use_relative_offset,
                "use_constant": mod.use_constant_offset,
                "relative": Vector(mod.relative_offset_displace),
                "constant": Vector(mod.constant_offset_displace),
                "index": obj.modifiers.find(mod.name),
            }
        return mod

    def setup_new_array(self, obj, mod, slot):
        mod.count = 2
        axis = self.default_axis(obj, slot)
        mod.relative_offset_displace = (0.0, 0.0, 0.0)
        mod.constant_offset_displace = (0.0, 0.0, 0.0)
        if obj.dimensions[axis] > EPS:
            mod.use_relative_offset = True
            mod.use_constant_offset = False
            vec = [0.0, 0.0, 0.0]
            vec[axis] = 1.0
            mod.relative_offset_displace = vec
        else:  # flat / degenerate mesh: relative offset would do nothing
            mod.use_relative_offset = False
            mod.use_constant_offset = True

        # Keep Weighted Normal modifiers at the bottom of the stack
        idx = obj.modifiers.find(mod.name)
        for i, m in enumerate(obj.modifiers):
            if m.type == 'WEIGHTED_NORMAL' and i < idx:
                obj.modifiers.move(idx, i)
                break

    def active_mods(self):
        for obj in self.objects:
            mod = obj.modifiers.get(self.mod_names.get(obj, self.active_name))
            if mod is not None and mod.type == 'ARRAY':
                yield obj, mod

    def activate_slot(self, slot):
        self.slot = slot
        self.active_name = ARRAY_SLOTS[slot]
        self.mod_names = {}
        for obj in self.objects:
            mod = self.get_or_create(obj, self.active_name, slot)
            self.mod_names[obj] = mod.name
            obj.modifiers.active = mod
            mod.show_expanded = True

        # Read the mode/axes from the reference object's modifier
        mod = self.ref_obj.modifiers.get(self.mod_names[self.ref_obj])
        if mod.use_relative_offset or not mod.use_constant_offset:
            self.relative = True
        else:
            self.relative = False
        for obj, m in self.active_mods():
            m.use_relative_offset = self.relative
            m.use_constant_offset = not self.relative

        vec = mod.relative_offset_displace if self.relative else mod.constant_offset_displace
        self.axes = [abs(v) > EPS for v in vec]
        if not any(self.axes):
            self.axes = [False, False, False]
            self.axes[self.default_axis(self.ref_obj, slot)] = True
        self.capture_base()

    def capture_base(self):
        self.drag = 0.0
        self.base = {}
        for obj, mod in self.active_mods():
            vec = mod.relative_offset_displace if self.relative else mod.constant_offset_displace
            self.base[obj] = Vector(vec)

    def apply_offset(self, snap=False):
        for obj, mod in self.active_mods():
            base = self.base.get(obj, Vector((0.0, 0.0, 0.0)))
            vec = Vector(base)
            for i in range(3):
                if self.axes[i]:
                    v = base[i] + self.drag
                    vec[i] = round(v * 10.0) / 10.0 if snap else round(v, 4)
            if self.relative:
                mod.relative_offset_displace = vec
            else:
                mod.constant_offset_displace = vec

    def set_axis(self, axis, toggle):
        if toggle:
            self.axes[axis] = not self.axes[axis]
            if not any(self.axes):
                self.axes[axis] = True
        else:
            self.axes = [i == axis for i in range(3)]
            for obj, mod in self.active_mods():
                vec = [0.0, 0.0, 0.0]
                if self.relative:
                    vec[axis] = 1.0
                    mod.relative_offset_displace = vec
                else:
                    mod.constant_offset_displace = vec
        self.capture_base()

    def set_relative(self, relative):
        self.relative = relative
        axis = next((i for i in range(3) if self.axes[i]), 0)
        for obj, mod in self.active_mods():
            mod.use_relative_offset = relative
            mod.use_constant_offset = not relative
            vec = [0.0, 0.0, 0.0]
            if relative:
                for i in range(3):
                    if self.axes[i]:
                        vec[i] = 1.0
                mod.relative_offset_displace = vec
            else:
                mod.constant_offset_displace = vec
        if not any(self.axes):
            self.axes[axis] = True
        self.capture_base()
        self.report({'INFO'}, "Relative Offset" if relative else "Constant Offset")

    def change_count(self, step):
        for obj, mod in self.active_mods():
            mod.count = max(1, mod.count + step)

    def move_modifier(self, direction):
        for obj, mod in self.active_mods():
            idx = obj.modifiers.find(mod.name)
            new = idx + direction
            if 0 <= new < len(obj.modifiers):
                obj.modifiers.move(idx, new)

    def current_count(self):
        mod = self.ref_obj.modifiers.get(self.mod_names.get(self.ref_obj, self.active_name))
        return mod.count if mod is not None else 0

    # ---------------------------------------------------------------- modal

    def pixel_scale(self, context):
        if self.relative:
            return 0.01
        rv3d = context.region_data
        width = max(self.region.width, 1) if self.region else 1000
        dist = rv3d.view_distance if rv3d else 10.0
        return dist * 1.5 / width

    def wrap_cursor(self, context, event):
        region = self.region
        if region is None:
            return
        margin = 40
        if event.mouse_x < region.x + margin or event.mouse_x > region.x + region.width - margin:
            cx = region.x + region.width // 2
            context.window.cursor_warp(cx, event.mouse_y)
            self.last_x = cx

    def modal(self, context, event):
        # Let viewport navigation through
        if event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'} or event.type.startswith('NDOF'):
            self.skip_next_move = True
            return {'PASS_THROUGH'}
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and (event.ctrl or event.alt):
            return {'PASS_THROUGH'}

        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            if self.skip_next_move:
                self.skip_next_move = False
                self.last_x = event.mouse_x
                return {'RUNNING_MODAL'}
            delta = event.mouse_x - self.last_x
            self.last_x = event.mouse_x
            step = self.pixel_scale(context) * (0.1 if event.shift else 1.0)
            self.drag += delta * step
            self.apply_offset(snap=event.ctrl)
            self.wrap_cursor(context, event)
            self.update_header()
            return {'RUNNING_MODAL'}

        if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
            self.finish(context)
            return {'FINISHED'}

        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self.restore()
            self.finish(context)
            return {'CANCELLED'}

        if event.value != 'PRESS':
            return {'RUNNING_MODAL'}

        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'NUMPAD_PLUS', 'NUMPAD_MINUS', 'EQUAL', 'MINUS'}:
            step = 1 if event.type in {'WHEELUPMOUSE', 'NUMPAD_PLUS', 'EQUAL'} else -1
            if event.shift and event.type.startswith('WHEEL'):
                self.move_modifier(-step)
            else:
                self.change_count(step)

        elif event.type in {'X', 'Y', 'Z'}:
            self.set_axis(AXIS_NAMES.index(event.type), toggle=event.shift)

        elif event.type == 'R':
            self.set_relative(True)

        elif event.type == 'C':
            self.set_relative(False)

        elif event.type in {'ONE', 'TWO', 'THREE'}:
            self.activate_slot(('ONE', 'TWO', 'THREE').index(event.type))

        elif event.type == 'Q':
            self.move_modifier(-1)

        elif event.type == 'W':
            self.move_modifier(1)

        elif event.type == 'S' and context.mode == 'OBJECT':
            try:
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                self.report({'INFO'}, "Applied Scale")
            except RuntimeError as e:
                self.report({'WARNING'}, str(e).replace("Error: ", "").strip())
            self.capture_base()

        else:
            return {'RUNNING_MODAL'}

        self.update_header()
        return {'RUNNING_MODAL'}

    # ------------------------------------------------------------------ UI

    def update_header(self):
        mod = self.ref_obj.modifiers.get(self.mod_names.get(self.ref_obj, self.active_name))
        if mod is None or self.area is None:
            return
        vec = mod.relative_offset_displace if self.relative else mod.constant_offset_displace
        axes = "".join(a for a, on in zip(AXIS_NAMES, self.axes) if on)
        text = (f"{mod.name}    Count: {mod.count}    "
                f"{'Relative' if self.relative else 'Constant'}: "
                f"X {vec[0]:.3f}  Y {vec[1]:.3f}  Z {vec[2]:.3f}    Axis: {axes}")
        if len(self.objects) > 1:
            text += f"    ({len(self.objects)} objects)"
        self.area.header_text_set(text)
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {'STATUSBAR', 'PROPERTIES'}:
                    area.tag_redraw()

    def finish(self, context):
        global _running_op
        _running_op = None
        try:
            context.workspace.status_text_set(None)
        except Exception:
            pass
        if self.area is not None:
            self.area.header_text_set(None)
        context.window.cursor_modal_restore()

    def restore(self):
        # Remove arrays we created, then restore the rest
        for (obj, name), data in list(self.backup.items()):
            if data["created"]:
                mod = obj.modifiers.get(name)
                if mod is not None:
                    obj.modifiers.remove(mod)

        existing = [(k, d) for k, d in self.backup.items() if not d["created"]]
        existing.sort(key=lambda kd: kd[1]["index"])
        for (obj, name), data in existing:
            mod = obj.modifiers.get(name)
            if mod is None:
                continue
            mod.count = data["count"]
            mod.use_relative_offset = data["use_relative"]
            mod.use_constant_offset = data["use_constant"]
            mod.relative_offset_displace = data["relative"]
            mod.constant_offset_displace = data["constant"]
            idx = obj.modifiers.find(name)
            target = min(data["index"], len(obj.modifiers) - 1)
            if idx != target:
                obj.modifiers.move(idx, target)
