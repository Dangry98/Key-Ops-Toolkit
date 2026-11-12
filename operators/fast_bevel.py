import bpy
import bmesh
from math import radians, degrees
from mathutils import Vector
from bpy_extras import view3d_utils

# Newer Blender features are used when available:
#   - 4.3+: edit mode bevels are limited by a custom edge attribute
#     (BevelModifier.edge_weight / vertex_weight) instead of a vertex group,
#     so only the selected edges get beveled.
#   - Enum values (offset type, limit method, miter...) are read from RNA so
#     cycling works across versions.

EPS = 1e-6
NEW_WIDTH = 0.02           # world units, for freshly added bevels
SEGMENT_PIXELS = 12        # mouse pixels per segment step
PROFILE_PER_PIXEL = 0.004
ANGLE_PER_PIXEL = radians(0.25)
PERCENT_PER_PIXEL = 0.1
WEIGHT_ATTR = "KO_Bevel"   # base name for edit mode edge / vertex attributes

MOD_PROPS = (
    "width", "width_pct", "segments", "profile", "profile_type", "limit_method",
    "angle_limit", "affect", "offset_type", "use_clamp_overlap", "loop_slide",
    "harden_normals", "miter_outer", "miter_inner", "show_viewport",
    "vertex_group", "edge_weight", "vertex_weight",
)

MODE_LABELS = {
    'WIDTH': "Width",
    'SEGMENTS': "Segments",
    'PROFILE': "Profile",
    'ANGLE': "Angle",
}

_running_op = None  # the FastBevel instance whose keymap is drawn in the status bar


def _valid_icon(name):
    try:
        items = bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items
        return name if name in items else 'NONE'
    except Exception:
        return 'NONE'


def _enum_items(mod, prop):
    try:
        return [i.identifier for i in mod.bl_rna.properties[prop].enum_items]
    except Exception:
        return []


def _cycle_enum(mod, prop, step=1):
    items = _enum_items(mod, prop)
    if not items:
        return None
    current = getattr(mod, prop)
    idx = items.index(current) if current in items else -1
    value = items[(idx + step) % len(items)]
    setattr(mod, prop, value)
    return value


def _nice(identifier):
    return identifier.replace("MITER_", "").replace("_", " ").title()


def _has_weight_attributes():
    return "edge_weight" in bpy.types.BevelModifier.bl_rna.properties


def _redraw_ui(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in {'STATUSBAR', 'PROPERTIES'}:
                area.tag_redraw()


def _draw_status(header, context):
    op = _running_op
    if op is None:
        return
    layout = header.layout
    row = layout.row(align=True)

    def item(icons, text):
        for icon in icons:
            row.label(text="", icon=_valid_icon(icon))
        row.label(text=text)
        row.separator(factor=2.0)

    def check(state):
        return " ✓" if state else ""

    mod = op.ref_mod()
    item(('MOUSE_LMB',), "Confirm")
    item(('MOUSE_RMB',), "Cancel")
    item(('MOUSE_MOVE',), MODE_LABELS[op.mode])
    item(('EVENT_SHIFT',), "Precise")
    item(('EVENT_CTRL',), "Snap")
    item(('MOUSE_MMB_SCROLL',), "Angle" if op.mode == 'ANGLE' else "Segments")
    item(('EVENT_S',), "Segments" + check(op.mode == 'SEGMENTS'))
    item(('EVENT_P',), "Profile" + check(op.mode == 'PROFILE'))
    item(('EVENT_A',), "Angle" + check(op.mode == 'ANGLE'))
    item(('EVENT_CTRL', 'EVENT_A'), "30° / 60°")
    item(('EVENT_Q', 'EVENT_E'), "Prev / Next Bevel")
    item(('EVENT_SHIFT', 'EVENT_Q'), "Move Up / Down")
    if mod is not None:
        item(('EVENT_L',), f"Limit ({_nice(mod.limit_method)})")
        item(('EVENT_W',), f"Offset ({_nice(mod.offset_type)})")
        item(('EVENT_C',), "Clamp" + check(mod.use_clamp_overlap))
        item(('EVENT_SHIFT', 'EVENT_C'), "Loop Slide" + check(mod.loop_slide))
        item(('EVENT_N',), "Harden Normals" + check(mod.harden_normals))
        item(('EVENT_M',), f"Miter ({_nice(mod.miter_outer)})")
    item(('EVENT_ONE', 'EVENT_TWO', 'EVENT_THREE'), "Edge / Vertex / Conversion")
    item(('EVENT_X',), "Half of Previous")
    item(('EVENT_V',), "Toggle Viewport")
    item(('EVENT_Z',), "Wireframe")
    item(('EVENT_TAB',), "Settings")
    item(('EVENT_SHIFT', 'EVENT_RETURN'), "Apply")


def _draw_popover(self, context):
    op = _running_op
    layout = self.layout
    if op is None:
        return
    mod = op.ref_mod()
    if mod is None:
        layout.label(text="No bevel modifier")
        return

    layout.label(text=f"{op.ref_obj.name}  ›  {mod.name}", icon='MOD_BEVEL')
    if len(op.objects) > 1:
        layout.label(text="Changes here only affect the active object", icon='INFO')

    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(mod, "affect", expand=True)
    col.separator()
    col.prop(mod, "offset_type")
    if mod.offset_type == 'PERCENT':
        col.prop(mod, "width_pct")
    else:
        col.prop(mod, "width")
    col.prop(mod, "segments")
    col.separator()
    col.prop(mod, "limit_method")
    if mod.limit_method == 'ANGLE':
        col.prop(mod, "angle_limit")
    elif mod.limit_method == 'VGROUP':
        col.prop_search(mod, "vertex_group", op.ref_obj, "vertex_groups", text="Vertex Group")
    elif mod.limit_method == 'WEIGHT' and hasattr(mod, "edge_weight"):
        if mod.affect == 'EDGES':
            col.prop(mod, "edge_weight", text="Edge Weight")
        else:
            col.prop(mod, "vertex_weight", text="Vertex Weight")
    col.separator()
    col.prop(mod, "profile_type")
    if mod.profile_type == 'SUPERELLIPSE':
        col.prop(mod, "profile", slider=True)
    col.separator()
    col.prop(mod, "miter_outer")
    col.prop(mod, "miter_inner")
    col.prop(mod, "use_clamp_overlap")
    col.prop(mod, "loop_slide")
    col.prop(mod, "harden_normals")


class FastBevel(bpy.types.Operator):
    bl_idname = "keyops.fast_bevel"
    bl_label = "Fast Bevel"
    bl_description = ("Add or adjust a Bevel modifier interactively.\n"
                      "Drag for width, scroll for segments, S/P/A for segment/profile/angle mode.\n"
                      "Ctrl: Add a new bevel (30°)  ·  Ctrl+Shift: Add a new bevel (60°)\n"
                      "In Edit Mode a new bevel is limited to the selected edges")
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

        self.edit_mode = context.mode == 'EDIT_MESH'
        if self.edit_mode:
            self.objects = [o for o in context.objects_in_mode if o.type == 'MESH']
        else:
            self.objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not self.objects:
            self.report({'WARNING'}, "Select at least one mesh object")
            return {'CANCELLED'}

        active = context.active_object
        self.ref_obj = active if active in self.objects else self.objects[0]
        self.area = context.area
        self.region = context.region
        self.rv3d = context.region_data or getattr(context.space_data, "region_3d", None)

        self.backup = {}          # (obj, mod name) -> original property values + index
        self.created = []         # (obj, mod name) we added
        self.created_attrs = []   # (obj, attr name, domain) added in edit mode
        self.created_vgroups = [] # (obj, vgroup name)
        self.wire_backup = {o: (o.show_wire, o.show_all_edges) for o in self.objects}
        self.targets = {}         # obj -> name of the bevel being adjusted
        self.mode = 'WIDTH'
        self.drag = 0.0
        self.base = {}
        self.typed = ""
        self.last_x = event.mouse_x
        self.skip_next_move = False

        force_new = event.ctrl
        angle = radians(60) if (event.ctrl and event.shift) else radians(30)
        new_count = 0
        for obj in self.objects:
            bevels = self.bevels(obj)
            want_selection = self.edit_mode and self.has_edge_selection(obj)
            if force_new or not bevels or want_selection:
                mod = self.add_bevel(obj, angle, limit_to_selection=want_selection)
                new_count += 1
            else:
                active_mod = obj.modifiers.active
                mod = active_mod if active_mod in bevels else bevels[-1]
                self.store(obj, mod)
            self.targets[obj] = mod.name
            obj.modifiers.active = mod
            mod.show_expanded = True

        self.capture_base()
        self.warn_scale()
        if new_count:
            self.report({'INFO'}, f"Bevel added ({new_count})")

        context.window_manager.modal_handler_add(self)
        context.window.cursor_modal_set('SCROLL_X')
        _running_op = self
        try:
            context.workspace.status_text_set(_draw_status)
        except Exception:
            context.workspace.status_text_set(
                "LMB Confirm | RMB Cancel | Move Width | Wheel Segments | S/P/A Mode | Q/E Bevel | Tab Settings")
        self.update_header(context)
        return {'RUNNING_MODAL'}

    # ------------------------------------------------------------- modifiers

    @staticmethod
    def bevels(obj):
        return [m for m in obj.modifiers if m.type == 'BEVEL']

    def target_mods(self):
        for obj in self.objects:
            mod = obj.modifiers.get(self.targets.get(obj, ""))
            if mod is not None and mod.type == 'BEVEL':
                yield obj, mod

    def ref_mod(self):
        mod = self.ref_obj.modifiers.get(self.targets.get(self.ref_obj, ""))
        return mod if mod is not None and mod.type == 'BEVEL' else None

    def store(self, obj, mod):
        key = (obj, mod.name)
        if key in self.backup:
            return
        data = {p: getattr(mod, p) for p in MOD_PROPS if hasattr(mod, p)}
        data["index"] = obj.modifiers.find(mod.name)
        self.backup[key] = data

    def add_bevel(self, obj, angle, limit_to_selection=False):
        mod = obj.modifiers.new(name="Bevel", type='BEVEL')
        self.created.append((obj, mod.name))

        scale = self.obj_scale(obj)
        dims = [d for d in obj.dimensions if d > EPS]
        width = NEW_WIDTH / scale
        if dims:
            width = min(width, min(dims) / scale * 0.1)

        mod.width = width
        mod.segments = 3
        mod.profile = 0.5
        mod.limit_method = 'ANGLE'
        mod.angle_limit = angle
        mod.miter_outer = 'MITER_ARC'
        mod.use_clamp_overlap = False
        mod.loop_slide = True
        mod.affect = 'EDGES'

        flat = any(d <= EPS for d in obj.dimensions)
        if flat:
            mod.affect = 'VERTICES'
            mod.segments = 6
            mod.use_clamp_overlap = True

        if limit_to_selection:
            self.limit_to_selection(obj, mod)

        self.sort_new(obj, mod)
        return mod

    def sort_new(self, obj, mod):
        """Keep normal / triangulate / pinned modifiers below the new bevel."""
        idx = obj.modifiers.find(mod.name)
        for i, m in enumerate(obj.modifiers):
            if i >= idx:
                break
            keep_below = m.type in {'WEIGHTED_NORMAL', 'TRIANGULATE'} or getattr(m, "use_pin_to_last", False)
            if m.type == 'NODES' and any(n in m.name for n in ("Smooth by Angle", "Auto Smooth")):
                keep_below = True
            if keep_below:
                obj.modifiers.move(idx, i)
                break

    # --- edit mode selection ---

    @staticmethod
    def has_edge_selection(obj):
        if obj.mode != 'EDIT':
            return False
        bm = bmesh.from_edit_mesh(obj.data)
        return any(e.select for e in bm.edges)

    def unique_attr_name(self, obj, bm):
        names = {a.name for a in obj.data.attributes}
        names |= {l.name for l in bm.edges.layers.float}
        names |= {l.name for l in bm.verts.layers.float}
        name, n = WEIGHT_ATTR, 1
        while name in names or name + "_v" in names:
            name = f"{WEIGHT_ATTR}.{n:03d}"
            n += 1
        return name

    def limit_to_selection(self, obj, mod):
        bm = bmesh.from_edit_mesh(obj.data)
        if _has_weight_attributes():
            name = self.unique_attr_name(obj, bm)
            layer = bm.edges.layers.float.new(name)
            for e in bm.edges:
                e[layer] = 1.0 if e.select else 0.0
            self.created_attrs.append((obj, name, 'EDGE'))
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            mod.limit_method = 'WEIGHT'
            mod.edge_weight = name
            mod.vertex_weight = name + "_v"
        else:
            # Pre 4.3: vertex group of the selected vertices
            vg = obj.vertex_groups.new(name="Bevel")
            self.created_vgroups.append((obj, vg.name))
            deform = bm.verts.layers.deform.verify()
            for v in bm.verts:
                if v.select:
                    v[deform][vg.index] = 1.0
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            mod.limit_method = 'VGROUP'
            mod.vertex_group = vg.name

    def ensure_vertex_weight(self, obj, mod):
        """Vertex bevel of an edit mode (edge attribute) bevel needs a vertex attribute."""
        if obj.mode != 'EDIT' or not hasattr(mod, "vertex_weight") or mod.limit_method != 'WEIGHT':
            return
        if (obj, mod.edge_weight, 'EDGE') not in self.created_attrs:
            return
        name = mod.vertex_weight
        bm = bmesh.from_edit_mesh(obj.data)
        if bm.verts.layers.float.get(name) is not None:
            return
        layer = bm.verts.layers.float.new(name)
        edge_layer = bm.edges.layers.float.get(mod.edge_weight)
        for v in bm.verts:
            on = v.select or (edge_layer is not None and any(e[edge_layer] > 0.0 for e in v.link_edges))
            v[layer] = 1.0 if on else 0.0
        self.created_attrs.append((obj, name, 'POINT'))
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

    # --- helpers ---

    @staticmethod
    def obj_scale(obj):
        s = obj.matrix_world.to_scale()
        return max((abs(s.x) + abs(s.y) + abs(s.z)) / 3.0, EPS)

    def warn_scale(self):
        for obj in self.objects:
            s = obj.matrix_world.to_scale()
            if max(abs(s.x - s.y), abs(s.y - s.z), abs(s.x - s.z)) > 1e-4:
                self.report({'WARNING'}, f"{obj.name} has non-uniform scale, bevel will be uneven (Alt+S applies scale)")
                return

    def world_per_pixel(self):
        region, rv3d = self.region, self.rv3d
        if region is None or rv3d is None:
            return 0.002
        loc = self.ref_obj.matrix_world @ (sum((Vector(c) for c in self.ref_obj.bound_box), Vector()) / 8.0)
        co = view3d_utils.location_3d_to_region_2d(region, rv3d, loc)
        if co is None:
            co = Vector((region.width / 2, region.height / 2))
        a = view3d_utils.region_2d_to_location_3d(region, rv3d, co, loc)
        b = view3d_utils.region_2d_to_location_3d(region, rv3d, co + Vector((1.0, 0.0)), loc)
        return max((b - a).length, 1e-7)

    def value_of(self, mod):
        if self.mode == 'WIDTH':
            return mod.width_pct if mod.offset_type == 'PERCENT' else mod.width
        if self.mode == 'SEGMENTS':
            return mod.segments
        if self.mode == 'PROFILE':
            return mod.profile
        return mod.angle_limit

    def capture_base(self):
        self.drag = 0.0
        self.base = {(obj, mod.name): self.value_of(mod) for obj, mod in self.target_mods()}

    def set_mode(self, mode):
        self.mode = 'WIDTH' if self.mode == mode else mode
        if self.mode == 'ANGLE':
            changed = False
            for obj, mod in self.target_mods():
                if mod.limit_method != 'ANGLE':
                    mod.limit_method = 'ANGLE'
                    changed = True
            if changed:
                self.report({'INFO'}, "Limit Method: Angle")
        self.typed = ""
        self.capture_base()

    # ---------------------------------------------------------------- apply

    def apply_drag(self, snap, fine):
        wpp = self.world_per_pixel()
        for obj, mod in self.target_mods():
            base = self.base.get((obj, mod.name), self.value_of(mod))
            if self.mode == 'WIDTH':
                if mod.offset_type == 'PERCENT':
                    v = max(0.0, base + self.drag * PERCENT_PER_PIXEL)
                    if snap:
                        v = round(v / (0.1 if fine else 1.0)) * (0.1 if fine else 1.0)
                    mod.width_pct = v
                else:
                    v = max(0.0, base + self.drag * wpp / self.obj_scale(obj))
                    if snap:
                        inc = 0.001 if fine else 0.01
                        v = round(v / inc) * inc
                    mod.width = v
            elif self.mode == 'SEGMENTS':
                mod.segments = max(1, int(base + self.drag / SEGMENT_PIXELS))
            elif self.mode == 'PROFILE':
                v = base + self.drag * PROFILE_PER_PIXEL
                if snap:
                    v = round(v / 0.05) * 0.05
                mod.profile = min(1.0, max(0.0, v))
            elif self.mode == 'ANGLE':
                v = base + self.drag * ANGLE_PER_PIXEL
                if snap:
                    inc = radians(1 if fine else 5)
                    v = round(v / inc) * inc
                mod.angle_limit = min(radians(180), max(0.0, v))

    def apply_typed(self):
        try:
            value = float(self.typed)
        except ValueError:
            return
        for obj, mod in self.target_mods():
            if self.mode == 'WIDTH':
                if mod.offset_type == 'PERCENT':
                    mod.width_pct = max(0.0, value)
                else:
                    mod.width = max(0.0, value)
            elif self.mode == 'SEGMENTS':
                mod.segments = max(1, int(value))
            elif self.mode == 'PROFILE':
                mod.profile = min(1.0, max(0.0, value))
            elif self.mode == 'ANGLE':
                mod.angle_limit = min(radians(180), max(0.0, radians(value)))

    def cycle_target(self, step):
        for obj in self.objects:
            bevels = self.bevels(obj)
            if not bevels:
                continue
            names = [m.name for m in bevels]
            current = self.targets.get(obj)
            idx = names.index(current) if current in names else len(names) - 1
            mod = bevels[(idx + step) % len(bevels)]
            self.store(obj, mod)
            self.targets[obj] = mod.name
            obj.modifiers.active = mod
            mod.show_expanded = True
        mod = self.ref_mod()
        if mod is not None:
            self.report({'INFO'}, f"Target Bevel: {mod.name}")
        self.capture_base()

    def move_modifier(self, direction):
        for obj, mod in self.target_mods():
            idx = obj.modifiers.find(mod.name)
            new = idx + direction
            if 0 <= new < len(obj.modifiers):
                obj.modifiers.move(idx, new)

    def toggle(self, prop, label):
        state = None
        for obj, mod in self.target_mods():
            if state is None:
                state = not getattr(mod, prop)
            setattr(mod, prop, state)
        if state is not None:
            self.report({'INFO'}, f"{label}: {'On' if state else 'Off'}")

    def cycle(self, prop, label, step=1):
        value = None
        for obj, mod in self.target_mods():
            if value is None:
                value = _cycle_enum(mod, prop, step)
            else:
                setattr(mod, prop, value)
        if value is not None:
            self.report({'INFO'}, f"{label}: {_nice(value)}")

    def cycle_angle(self):
        presets = (30, 60)
        value = None
        for obj, mod in self.target_mods():
            mod.limit_method = 'ANGLE'
            if value is None:
                current = round(degrees(mod.angle_limit))
                value = presets[(presets.index(current) + 1) % len(presets)] if current in presets else presets[0]
            mod.angle_limit = radians(value)
        if value is not None:
            self.report({'INFO'}, f"Bevel Angle: {value}°")

    def preset(self, number):
        for obj, mod in self.target_mods():
            if number == 1:
                mod.affect = 'EDGES'
                mod.harden_normals = False
                mod.profile_type = 'SUPERELLIPSE'
                mod.profile = 0.5
                if mod.segments <= 2:
                    mod.segments = 4
            elif number == 2:
                mod.affect = 'VERTICES'
                mod.profile_type = 'SUPERELLIPSE'
                mod.profile = 0.5
                self.ensure_vertex_weight(obj, mod)
            elif number == 3:
                mod.affect = 'EDGES'
                mod.harden_normals = False
                mod.profile_type = 'SUPERELLIPSE'
                mod.profile = 1.0
                mod.segments = 2
        self.report({'INFO'}, ("Edge Bevel", "Vertex Bevel", "Conversion Bevel")[number - 1])
        self.capture_base()

    def half_of_previous(self, double):
        for obj, mod in self.target_mods():
            bevels = self.bevels(obj)
            idx = bevels.index(mod)
            source = bevels[idx - 1] if idx > 0 else mod
            factor = 2.0 if double else 0.5
            if mod.offset_type == 'PERCENT':
                mod.width_pct = source.width_pct * factor
            else:
                mod.width = source.width * factor
        mod = self.ref_mod()
        if mod is not None:
            self.report({'INFO'}, f"Width set to {mod.width:.4f}")

    def toggle_wire(self):
        state = not self.ref_obj.show_wire
        for obj in self.objects:
            obj.show_wire = state
            obj.show_all_edges = state

    def apply_modifiers(self, context):
        targets = list(self.target_mods())
        if not targets:
            return
        was_edit = self.edit_mode
        if was_edit:
            bpy.ops.object.mode_set(mode='OBJECT')
        applied = 0
        for obj, mod in targets:
            try:
                with context.temp_override(object=obj, active_object=obj):
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                applied += 1
            except RuntimeError as e:
                self.report({'WARNING'}, str(e).replace("Error: ", "").strip())
        if was_edit:
            bpy.ops.object.mode_set(mode='EDIT')
        if applied:
            self.report({'INFO'}, f"Applied Bevel ({applied})")

    # ---------------------------------------------------------------- modal

    def wrap_cursor(self, context, event):
        region = self.region
        if region is None:
            return
        margin = 40
        if event.mouse_x < region.x + margin or event.mouse_x > region.x + region.width - margin:
            cx = region.x + region.width // 2
            context.window.cursor_warp(cx, event.mouse_y)
            self.last_x = cx

    def handle_typing(self, event):
        """Numeric input. Numpad keys / period start it, then the number row works too."""
        digits = {
            'ZERO': "0", 'ONE': "1", 'TWO': "2", 'THREE': "3", 'FOUR': "4",
            'FIVE': "5", 'SIX': "6", 'SEVEN': "7", 'EIGHT': "8", 'NINE': "9",
        }
        t = event.type
        char = None
        if t.startswith('NUMPAD_') and t[7:] in digits:
            char = digits[t[7:]]
        elif t in digits and self.typed:
            char = digits[t]
        elif t in {'PERIOD', 'NUMPAD_PERIOD'}:
            char = "" if "." in self.typed else "."
        elif t in {'MINUS', 'NUMPAD_MINUS'} and self.typed:
            self.typed = self.typed[1:] if self.typed.startswith("-") else "-" + self.typed
            return True
        elif t == 'BACK_SPACE' and self.typed:
            self.typed = self.typed[:-1]
            if not self.typed:
                self.restore_values_only()
            return True
        if char is None:
            return False
        self.typed += char
        return True

    def restore_values_only(self):
        """Back out of numeric input: return to the value before typing started."""
        for obj, mod in self.target_mods():
            base = self.base.get((obj, mod.name))
            if base is None:
                continue
            if self.mode == 'WIDTH':
                if mod.offset_type == 'PERCENT':
                    mod.width_pct = base
                else:
                    mod.width = base
            elif self.mode == 'SEGMENTS':
                mod.segments = base
            elif self.mode == 'PROFILE':
                mod.profile = base
            else:
                mod.angle_limit = base
        self.drag = 0.0

    def modal(self, context, event):
        # Let viewport navigation through
        if event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'} or event.type.startswith('NDOF'):
            self.skip_next_move = True
            return {'PASS_THROUGH'}

        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            if self.skip_next_move:
                self.skip_next_move = False
                self.last_x = event.mouse_x
                return {'RUNNING_MODAL'}
            if self.typed:  # numeric input wins over the mouse, like transform
                self.last_x = event.mouse_x
                return {'RUNNING_MODAL'}
            delta = event.mouse_x - self.last_x
            self.last_x = event.mouse_x
            self.drag += delta * (0.1 if event.shift else 1.0)
            self.apply_drag(snap=event.ctrl, fine=event.shift)
            self.wrap_cursor(context, event)
            self.update_header(context)
            return {'RUNNING_MODAL'}

        if event.value != 'PRESS':
            return {'RUNNING_MODAL'}

        if event.type in {'RET', 'NUMPAD_ENTER'} and event.shift:
            self.apply_modifiers(context)
            self.finish(context)
            return {'FINISHED'}

        if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE'}:
            self.finish(context)
            return {'FINISHED'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.restore()
            self.finish(context)
            return {'CANCELLED'}

        if self.handle_typing(event):
            if self.typed:
                self.apply_typed()
            self.update_header(context)
            return {'RUNNING_MODAL'}

        handled = True
        t = event.type
        if t in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'NUMPAD_PLUS', 'EQUAL'}:
            step = 1 if t in {'WHEELUPMOUSE', 'NUMPAD_PLUS', 'EQUAL'} else -1
            if event.shift and t.startswith('WHEEL'):
                self.move_modifier(-step)
            elif event.ctrl and t.startswith('WHEEL'):
                self.cycle_target(step)
            elif self.mode == 'ANGLE' or event.alt:
                for obj, mod in self.target_mods():
                    mod.angle_limit = min(radians(180), max(0.0, mod.angle_limit + radians(step)))
            else:
                for obj, mod in self.target_mods():
                    mod.segments = max(1, mod.segments + step)
            self.capture_base()

        elif t == 'S' and event.alt and not self.edit_mode:
            try:
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                self.report({'INFO'}, "Applied Scale")
            except RuntimeError as e:
                self.report({'WARNING'}, str(e).replace("Error: ", "").strip())
            self.capture_base()
        elif t == 'S':
            self.set_mode('SEGMENTS')
        elif t == 'P':
            self.set_mode('PROFILE')
        elif t == 'A' and event.ctrl:
            self.cycle_angle()
            self.capture_base()
        elif t == 'A':
            self.set_mode('ANGLE')

        elif t in {'Q', 'E'}:
            step = -1 if t == 'Q' else 1
            if event.shift:
                self.move_modifier(step)
            else:
                self.cycle_target(step)

        elif t == 'L':
            self.cycle("limit_method", "Limit Method")
        elif t == 'W':
            self.cycle("offset_type", "Width Type")
            self.capture_base()
        elif t == 'C':
            if event.shift:
                self.toggle("loop_slide", "Loop Slide")
            else:
                self.toggle("use_clamp_overlap", "Clamp Overlap")
        elif t == 'N':
            self.toggle("harden_normals", "Harden Normals")
        elif t == 'M':
            if event.shift:
                self.cycle("miter_inner", "Inner Miter")
            else:
                self.cycle("miter_outer", "Outer Miter")
        elif t == 'V':
            self.toggle("show_viewport", "Show in Viewport")
        elif t == 'Z':
            self.toggle_wire()

        elif t in {'ONE', 'TWO', 'THREE'}:
            self.preset(('ONE', 'TWO', 'THREE').index(t) + 1)

        elif t == 'X':
            self.half_of_previous(double=event.shift)
            self.finish(context)
            return {'FINISHED'}

        elif t == 'TAB':
            self.skip_next_move = True
            self.typed = ""
            context.window_manager.popover(_draw_popover, ui_units_x=14)
            # Values may be changed in the popover, start the next drag from them
            self.capture_base()

        else:
            handled = False

        if handled:
            self.update_header(context)
        return {'RUNNING_MODAL'}

    # ------------------------------------------------------------------ UI

    def update_header(self, context):
        mod = self.ref_mod()
        if mod is None or self.area is None:
            return
        bevels = self.bevels(self.ref_obj)
        pos = f"{bevels.index(mod) + 1}/{len(bevels)}" if mod in bevels else ""

        if mod.offset_type == 'PERCENT':
            width = f"Width: {mod.width_pct:.1f}%"
        else:
            width = f"Width: {mod.width:.4f}"
        parts = [f"{mod.name} ({pos})", width, f"Segments: {mod.segments}"]
        if mod.profile_type == 'SUPERELLIPSE':
            parts.append(f"Profile: {mod.profile:.2f}")
        else:
            parts.append("Profile: Custom")
        limit = _nice(mod.limit_method)
        if mod.limit_method == 'ANGLE':
            limit += f" {degrees(mod.angle_limit):.0f}°"
        parts.append(f"Limit: {limit}")
        if mod.affect == 'VERTICES':
            parts.append("Vertices")
        parts.append(f"Adjusting: {MODE_LABELS[self.mode]}")
        if self.typed:
            parts.append(f"Input: [{self.typed}|]")
        if len(self.objects) > 1:
            parts.append(f"({len(self.objects)} objects)")

        # Live values readable in the Properties editor too
        for obj, m in self.target_mods():
            obj.modifiers.active = m

        self.area.header_text_set("    ".join(parts))
        self.area.tag_redraw()
        _redraw_ui(context)

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
        _redraw_ui(context)

    def restore(self):
        # Remove bevels we created
        for obj, name in self.created:
            mod = obj.modifiers.get(name)
            if mod is not None:
                obj.modifiers.remove(mod)
            self.backup.pop((obj, name), None)

        # Remove edit mode attributes / vertex groups we created
        for obj, name, domain in self.created_attrs:
            if obj.mode == 'EDIT':
                bm = bmesh.from_edit_mesh(obj.data)
                layers = bm.edges.layers.float if domain == 'EDGE' else bm.verts.layers.float
                layer = layers.get(name)
                if layer is not None:
                    layers.remove(layer)
                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            else:
                attr = obj.data.attributes.get(name)
                if attr is not None:
                    obj.data.attributes.remove(attr)
        for obj, name in self.created_vgroups:
            vg = obj.vertex_groups.get(name)
            if vg is not None:
                obj.vertex_groups.remove(vg)

        # Restore existing bevels
        existing = sorted(self.backup.items(), key=lambda kd: kd[1]["index"])
        for (obj, name), data in existing:
            mod = obj.modifiers.get(name)
            if mod is None:
                continue
            for prop, value in data.items():
                if prop == "index":
                    continue
                try:
                    setattr(mod, prop, value)
                except (AttributeError, TypeError, ValueError):
                    pass
            idx = obj.modifiers.find(name)
            target = min(data["index"], len(obj.modifiers) - 1)
            if idx != target:
                obj.modifiers.move(idx, target)

        for obj, (wire, all_edges) in self.wire_backup.items():
            obj.show_wire = wire
            obj.show_all_edges = all_edges
