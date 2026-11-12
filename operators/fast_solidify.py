import bpy

MOD_TYPE = 'SOLIDIFY'
SNAPSHOT_PROPS = (
    "thickness", "offset", "use_rim_only", "use_even_offset", "use_quality_normals",
    "show_on_cage", "show_in_editmode", "show_viewport", "solidify_mode",
)
MODE_LABELS = {'EXTRUDE': "Simple", 'NON_MANIFOLD': "Complex"}
WARP_MARGIN = 40


def _solidify_mods(obj):
    return [m for m in obj.modifiers if m.type == MOD_TYPE]


def _keep_weighted_normal_last(obj):
    for mod in [m for m in obj.modifiers if m.type == 'WEIGHTED_NORMAL']:
        idx = obj.modifiers.find(mod.name)
        if idx != len(obj.modifiers) - 1:
            obj.modifiers.move(idx, len(obj.modifiers) - 1)


def _draw_status_bar(self, context):
    layout = self.layout
    op = KEYOPS_OT_fast_solidify.operator
    if op is None:
        return

    def item(text, *icons):
        row = layout.row(align=True)
        for icon in icons:
            row.label(text="", icon=icon)
        row.label(text=text)
        layout.separator(factor=1.5)

    item("Confirm", 'MOUSE_LMB')
    item("Cancel", 'MOUSE_RMB')
    item("Snap 0.1 / 0.01", 'EVENT_CTRL')
    item("Precise", 'EVENT_SHIFT')
    item("Offset -1 / 0 / 1   (1 2 3)")
    item("Rim", 'EVENT_R')
    item("Simple / Complex   (4)")
    item("Add / Remove", 'EVENT_SHIFT', 'EVENT_A')
    item("Move Up / Down", 'EVENT_Q', 'EVENT_E')
    item("Cycle Solidify", 'EVENT_CTRL', 'MOUSE_MMB')
    item("Pause", 'EVENT_X')
    item("Options", 'EVENT_TAB')


class KEYOPS_OT_fast_solidify(bpy.types.Operator):
    bl_idname = "keyops.fast_solidify"
    bl_label = "Fast Solidify"
    bl_description = "LMB: Adjust Solidify modifier\nCtrl + LMB: Add a new Solidify modifier\nTAB in modal for options"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    # Running instance, used by the popup and helper operators
    operator = None

    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT', 'EDIT_MESH'} and any(o.type == 'MESH' for o in context.selected_objects)

    # --- Modifier bookkeeping --- #

    def obj_mods(self, obj):
        return [m for m in _solidify_mods(obj) if (obj.name, m.name) not in self._pending_remove]

    def active_mods(self):
        result = []
        for obj in self._objects:
            mods = self.obj_mods(obj)
            if not mods:
                continue
            idx = max(0, min(self._active_index.get(obj.name, len(mods) - 1), len(mods) - 1))
            self._active_index[obj.name] = idx
            result.append((obj, mods[idx]))
        return result

    def display(self):
        """(obj, mod, index, total) shown in header/popup: prefer the active object."""
        active = self.active_mods()
        if not active:
            return None, None, 0, 0
        obj, mod = active[0]
        for o, m in active:
            if o == self._active_obj:
                obj, mod = o, m
                break
        return obj, mod, self._active_index[obj.name], len(self.obj_mods(obj))

    def create_new(self):
        for obj in self._objects:
            mod = obj.modifiers.new(name="Solidify", type=MOD_TYPE)
            mod.thickness = 0.0
            mod.use_even_offset = True
            mod.use_quality_normals = True
            mod.use_rim_only = False
            mod.show_on_cage = True
            self._created.append((obj, mod.name))
            _keep_weighted_normal_last(obj)
            self._active_index[obj.name] = len(self.obj_mods(obj)) - 1

    def remove_active(self):
        for obj, mod in self.active_mods():
            if (obj, mod.name) in self._created:
                self._created.remove((obj, mod.name))
                obj.modifiers.remove(mod)
            else:
                # Deferred so cancel can bring it back
                mod.show_viewport = False
                self._pending_remove.add((obj.name, mod.name))
            self._active_index[obj.name] = len(self.obj_mods(obj)) - 1

    def cycle(self, forward=True):
        for obj in self._objects:
            mods = self.obj_mods(obj)
            if mods:
                idx = self._active_index.get(obj.name, len(mods) - 1)
                self._active_index[obj.name] = (idx + (1 if forward else -1)) % len(mods)
        self._raw.clear()

    def set_active_by_name(self, name):
        for obj in self._objects:
            for i, m in enumerate(self.obj_mods(obj)):
                if m.name == name:
                    self._active_index[obj.name] = i
        self._raw.clear()

    def move_active(self, up=True):
        for obj, mod in self.active_mods():
            idx = obj.modifiers.find(mod.name)
            new_idx = idx - 1 if up else idx + 1
            if 0 <= new_idx < len(obj.modifiers):
                obj.modifiers.move(idx, new_idx)
            self._active_index[obj.name] = self.obj_mods(obj).index(mod)

    def set_attr(self, attr, value):
        for _obj, mod in self.active_mods():
            setattr(mod, attr, value)

    def toggle_attr(self, attr):
        for _obj, mod in self.active_mods():
            setattr(mod, attr, not getattr(mod, attr))

    def toggle_mode(self):
        for _obj, mod in self.active_mods():
            mod.solidify_mode = 'NON_MANIFOLD' if mod.solidify_mode == 'EXTRUDE' else 'EXTRUDE'

    def adjust_thickness(self, delta, ctrl, shift):
        for _obj, mod in self.active_mods():
            key = mod.as_pointer()
            raw = self._raw.get(key, mod.thickness) + delta
            self._raw[key] = raw
            if ctrl:
                mod.thickness = round(raw, 2 if shift else 1)
            else:
                mod.thickness = raw

    # --- Invoke / Modal --- #

    def invoke(self, context, event):
        area = context.area
        if area is None or area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Active space must be a 3D Viewport")
            return {'CANCELLED'}

        self._region = context.region if context.region and context.region.type == 'WINDOW' else \
            next((r for r in area.regions if r.type == 'WINDOW'), None)
        self._rv3d = area.spaces.active.region_3d
        if self._region is None or self._rv3d is None:
            return {'CANCELLED'}

        self._objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not self._objects:
            self.report({'WARNING'}, "Select at least one mesh object")
            return {'CANCELLED'}

        self._active_obj = context.active_object
        self._created = []
        self._pending_remove = set()
        self._active_index = {}
        self._raw = {}
        self._paused = False
        self._navigating = False
        self._exit_request = None
        self.popup = False

        # Snapshot for cancel
        self._snapshot = {}
        for obj in self._objects:
            self._snapshot[obj.name] = {
                "order": [m.name for m in obj.modifiers],
                "props": {m.name: {p: getattr(m, p) for p in SNAPSHOT_PROPS} for m in _solidify_mods(obj)},
            }

        if event.ctrl or not any(_solidify_mods(o) for o in self._objects):
            self.create_new()
        for obj in self._objects:
            if not self.obj_mods(obj):
                # Object without a solidify while others have one
                mod = obj.modifiers.new(name="Solidify", type=MOD_TYPE)
                mod.use_even_offset = True
                mod.use_quality_normals = True
                mod.show_on_cage = True
                self._created.append((obj, mod.name))
                _keep_weighted_normal_last(obj)

        for _obj, mod in self.active_mods():
            mod.use_even_offset = True
            mod.use_quality_normals = True
            mod.show_on_cage = True

        self._last_x = event.mouse_x
        self._last_y = event.mouse_y

        self.__class__.operator = self
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.05, window=context.window)
        context.window.cursor_modal_set('SCROLL_X')
        context.workspace.status_text_set(_draw_status_bar)
        self.update_header(context)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if self._exit_request == 'CONFIRM':
            self.finish(context)
            return {'FINISHED'}
        if self._exit_request == 'REMOVE':
            self.remove_active()
            self.finish(context)
            return {'FINISHED'}

        # Native popup is open: it handles its own events
        if self.popup:
            if event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'ESC', 'TAB', 'RET'} and event.value == 'PRESS':
                self.popup = False
            self._last_x, self._last_y = event.mouse_x, event.mouse_y
            self.update_header(context)
            return {'RUNNING_MODAL'}

        if event.type == 'TIMER':
            return {'RUNNING_MODAL'}

        # Navigation pass-through
        if event.type == 'MIDDLEMOUSE':
            self._navigating = event.value == 'PRESS'
            return {'PASS_THROUGH'}
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            if event.ctrl:
                self.cycle(forward=event.type == 'WHEELUPMOUSE')
                self.update_header(context)
                return {'RUNNING_MODAL'}
            if event.shift:
                self.move_active(up=event.type == 'WHEELUPMOUSE')
                self.update_header(context)
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}
        if event.type in {'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'MOUSESMARTZOOM'} or event.type.startswith('NDOF'):
            return {'PASS_THROUGH'}

        if event.type == 'MOUSEMOVE':
            if self._navigating or self._paused:
                self._last_x, self._last_y = event.mouse_x, event.mouse_y
            else:
                self.mouse_adjust(context, event)
            self.update_header(context)
            return {'RUNNING_MODAL'}

        if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
            self.finish(context)
            return {'FINISHED'}

        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self.cancel_restore(context)
            return {'CANCELLED'}

        if event.value == 'PRESS':
            handled = True
            if event.type == 'ONE':
                self.set_attr("offset", -1.0)
            elif event.type == 'TWO':
                self.set_attr("offset", 0.0)
            elif event.type == 'THREE':
                self.set_attr("offset", 1.0)
            elif event.type == 'FOUR':
                self.toggle_mode()
            elif event.type == 'R':
                self.toggle_attr("use_rim_only")
            elif event.type == 'A':
                if event.shift:
                    self.remove_active()
                else:
                    self.create_new()
                self._raw.clear()
            elif event.type == 'Q':
                self.move_active(up=True)
            elif event.type == 'E':
                self.move_active(up=False)
            elif event.type in {'NUMPAD_PLUS', 'EQUAL'}:
                self.cycle(forward=True)
            elif event.type in {'NUMPAD_MINUS', 'MINUS'}:
                self.cycle(forward=False)
            elif event.type == 'X':
                self._paused = not self._paused
                self._last_x, self._last_y = event.mouse_x, event.mouse_y
            elif event.type == 'TAB':
                self.popup = True
                bpy.ops.keyops.fast_solidify_popup('INVOKE_DEFAULT')
            else:
                handled = False
            if handled:
                self.update_header(context)
                return {'RUNNING_MODAL'}

        return {'RUNNING_MODAL'}

    def mouse_adjust(self, context, event):
        dx = event.mouse_x - self._last_x
        self._last_x, self._last_y = event.mouse_x, event.mouse_y

        region = self._region
        factor = self._rv3d.view_distance * 0.75 / max(region.width, 1)
        if event.shift:
            factor *= 0.1
        self.adjust_thickness(dx * factor, event.ctrl, event.shift)

        # Wrap cursor horizontally inside the viewport
        left, right = region.x + WARP_MARGIN, region.x + region.width - WARP_MARGIN
        if event.mouse_x < left or event.mouse_x > right:
            cx = region.x + region.width // 2
            context.window.cursor_warp(cx, event.mouse_y)
            self._last_x = cx

    # --- UI --- #

    def update_header(self, context):
        obj, mod, idx, total = self.display()
        if mod is None:
            text = "Solidify: None  |  A: Add new"
        else:
            text = (f"Solidify {idx + 1}/{total} ({mod.name})   "
                    f"Thickness: {mod.thickness:.3f}   "
                    f"Offset: {mod.offset:.2f}   "
                    f"Rim: {'On' if mod.use_rim_only else 'Off'}   "
                    f"Mode: {MODE_LABELS.get(mod.solidify_mode, mod.solidify_mode)}")
            if self._paused:
                text += "   [Paused]"
        if context.area:
            context.area.header_text_set(text)
            context.area.tag_redraw()

    # --- Exit --- #

    def _cleanup_ui(self, context):
        self.__class__.operator = None
        if getattr(self, "_timer", None):
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def finish(self, context):
        for obj_name, mod_name in self._pending_remove:
            obj = bpy.data.objects.get(obj_name)
            if obj and mod_name in obj.modifiers:
                obj.modifiers.remove(obj.modifiers[mod_name])
        self._pending_remove.clear()
        self._cleanup_ui(context)

    def cancel_restore(self, context):
        for obj, name in self._created:
            mod = obj.modifiers.get(name)
            if mod:
                obj.modifiers.remove(mod)
        for obj in self._objects:
            snap = self._snapshot.get(obj.name)
            if not snap:
                continue
            for mod_name, props in snap["props"].items():
                mod = obj.modifiers.get(mod_name)
                if mod:
                    for p, v in props.items():
                        try:
                            setattr(mod, p, v)
                        except (AttributeError, TypeError):
                            pass
            for i, name in enumerate(snap["order"]):
                idx = obj.modifiers.find(name)
                if idx >= 0 and idx != i:
                    obj.modifiers.move(idx, i)
        self._pending_remove.clear()
        self._cleanup_ui(context)

    def cancel(self, context):
        # Called by Blender if the modal is aborted (e.g. file load)
        if self.__class__.operator is self:
            self.cancel_restore(context)


class KEYOPS_OT_fast_solidify_popup(bpy.types.Operator):
    bl_idname = "keyops.fast_solidify_popup"
    bl_label = "Fast Solidify"
    bl_options = {'INTERNAL'}

    def __del__(self):
        op = KEYOPS_OT_fast_solidify.operator
        if op is not None:
            op.popup = False

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=240)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        op = KEYOPS_OT_fast_solidify.operator
        if op is None or op._exit_request:
            layout.label(text="Done - move the cursor away", icon='CHECKMARK')
            return

        obj, mod, idx, total = op.display()

        row = layout.row(align=True)
        row.label(text="Solidify", icon='MOD_SOLIDIFY')
        row.operator("keyops.fast_solidify_action", text="", icon='ADD').action = 'ADD'
        row.operator("keyops.fast_solidify_action", text="", icon='TRIA_UP').action = 'MOVE_UP'
        row.operator("keyops.fast_solidify_action", text="", icon='TRIA_DOWN').action = 'MOVE_DOWN'
        row.operator("keyops.fast_solidify_action", text="", icon='CHECKMARK').action = 'CONFIRM'

        if mod is None:
            layout.label(text="No Solidify modifier")
            return

        # Modifier selector
        col = layout.column(align=True)
        for i, m in enumerate(op.obj_mods(obj)):
            props = col.operator("keyops.fast_solidify_action", text=m.name, depress=(i == idx))
            props.action = 'SELECT'
            props.name = m.name

        layout.separator()
        col = layout.column(align=True)
        col.prop(mod, "thickness")
        col.prop(mod, "offset")

        row = layout.row(align=True)
        for value in (-1.0, 0.0, 1.0):
            props = row.operator("keyops.fast_solidify_action", text=f"{value:g}")
            props.action = 'OFFSET'
            props.value = value
        row.prop(mod, "use_rim_only", text="", icon='EVENT_R')

        layout.prop(mod, "solidify_mode", text="")

        col = layout.column(align=True)
        col.prop(mod, "use_even_offset")
        col.prop(mod, "use_quality_normals")
        col.prop(mod, "use_flip_normals")

        layout.separator()
        layout.operator("keyops.fast_solidify_action", text="Remove and Exit", icon='X').action = 'REMOVE_EXIT'


class KEYOPS_OT_fast_solidify_action(bpy.types.Operator):
    bl_idname = "keyops.fast_solidify_action"
    bl_label = "Fast Solidify Action"
    bl_description = "Fast Solidify option"
    bl_options = {'INTERNAL'}

    action: bpy.props.EnumProperty(items=[
        ('ADD', "Add", "Add a new Solidify modifier"),
        ('MOVE_UP', "Move Up", "Move the Solidify modifier up"),
        ('MOVE_DOWN', "Move Down", "Move the Solidify modifier down"),
        ('SELECT', "Select", "Make this the Solidify modifier to adjust"),
        ('OFFSET', "Offset", "Set offset"),
        ('CONFIRM', "Confirm", "Confirm and exit"),
        ('REMOVE_EXIT', "Remove and Exit", "Remove the Solidify modifier and exit"),
    ])  # type: ignore
    name: bpy.props.StringProperty()  # type: ignore
    value: bpy.props.FloatProperty()  # type: ignore

    def execute(self, context):
        op = KEYOPS_OT_fast_solidify.operator
        if op is None:
            return {'CANCELLED'}
        if self.action == 'ADD':
            op.create_new()
        elif self.action == 'MOVE_UP':
            op.move_active(up=True)
        elif self.action == 'MOVE_DOWN':
            op.move_active(up=False)
        elif self.action == 'SELECT':
            op.set_active_by_name(self.name)
        elif self.action == 'OFFSET':
            op.set_attr("offset", self.value)
        elif self.action == 'CONFIRM':
            op._exit_request = 'CONFIRM'
        elif self.action == 'REMOVE_EXIT':
            op._exit_request = 'REMOVE'
        op.update_header(context)
        return {'FINISHED'}


classes = (
    KEYOPS_OT_fast_solidify,
    KEYOPS_OT_fast_solidify_popup,
    KEYOPS_OT_fast_solidify_action,
)


def register_fast_solidify():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister_fast_solidify():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
