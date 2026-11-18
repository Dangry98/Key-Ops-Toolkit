"""Maya-style marking menus for Key Ops pie menus (Pie Style: Maya).

Press the key and flick: the direction picks the item, not the button under the mouse, and releasing
the key runs it, even before the menu has appeared. Hold still and the menu shows. Items that open
another pie menu open it right where the mouse is once you move past them, so you can keep flicking
(Maya's sub-marking menus). A quick tap leaves the menu open to click; releasing in the middle cancels.
"""

import math
import time

import blf
import bpy
import gpu
from bpy.props import StringProperty
from gpu_extras.batch import batch_for_shader

SHOW_DELAY = 0.12  # seconds before the menu is drawn; a faster flick picks without showing it
TAP_TIME = 0.25    # a press shorter than this, without moving, leaves the menu open to click
# compass direction of each 45 degree sector, counter-clockwise from the right
SECTORS = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")
DIR_VECTORS = {d: (math.cos(i * math.pi / 4), math.sin(i * math.pi / 4)) for i, d in enumerate(SECTORS)}


def _pm():
    from . import pie_menus
    return pie_menus


def _shader():
    return gpu.shader.from_builtin('UNIFORM_COLOR')


def _rect(x, y, w, h, color):
    sh = _shader()
    batch = batch_for_shader(sh, 'TRIS', {"pos": ((x, y), (x + w, y), (x + w, y + h), (x, y + h))},
                             indices=((0, 1, 2), (0, 2, 3)))
    sh.bind()
    sh.uniform_float("color", color)
    batch.draw(sh)


def _lines(points, color, width=1.0, loop=False):
    sh = _shader()
    batch = batch_for_shader(sh, 'LINE_LOOP' if loop else 'LINE_STRIP', {"pos": points})
    gpu.state.line_width_set(width)
    sh.bind()
    sh.uniform_float("color", color)
    batch.draw(sh)
    gpu.state.line_width_set(1.0)


def _circle(cx, cy, r, color, width=1.5, segments=32):
    pts = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in (i * 2 * math.pi / segments for i in range(segments))]
    _lines(pts, color, width, loop=True)


class Level:
    """One open marking menu: which pie and where its centre is (window coordinates)."""

    def __init__(self, pie, x, y):
        self.uid = pie.uid
        self.x, self.y = x, y


class WM_OT_keyops_marking_menu(bpy.types.Operator):
    bl_idname = "wm.keyops_marking_menu"
    bl_label = "Key Ops Marking Menu"
    bl_description = "Open a Key Ops pie as a Maya-style marking menu"
    bl_options = {'INTERNAL'}

    pie: StringProperty() # type: ignore
    key: StringProperty() # type: ignore  # releasing this key picks

    # ---- geometry
    def _scale(self):
        return bpy.context.preferences.system.ui_scale

    def _radius(self, pie):
        view = bpy.context.preferences.view
        return (pie.radius or view.pie_menu_radius) * self._scale()

    def _threshold(self, pie):
        view = bpy.context.preferences.view
        return max(4.0, (pie.threshold or view.pie_menu_threshold) * self._scale())

    def _slots(self, context, pie):
        return dict(_pm().pie_slots(context, list(pie.items)))

    def _active(self, context):
        """(pie, item index, distance) under the current direction of the top level, item None at the centre."""
        level = self.levels[-1]
        pie = _pm().find_pie(level.uid)
        dx, dy = self.mx - level.x, self.my - level.y
        dist = math.hypot(dx, dy)
        if pie is None or dist < self._threshold(pie):
            return pie, None, dist
        sector = SECTORS[int(round(math.atan2(dy, dx) / (math.pi / 4))) % 8]
        index = self._slots(context, pie).get(sector)
        if index is not None and _pm()._is_empty(pie.items[index]):
            index = None
        return pie, index, dist

    # ---- running
    def invoke(self, context, event):
        PM = _pm()
        pie = PM.find_pie(self.pie)
        if pie is None or context.area is None:
            return {'CANCELLED'}
        self.region = next((r for r in context.area.regions if r.type == 'WINDOW'), context.region)
        self.mx, self.my = event.mouse_x, event.mouse_y
        self.levels = [Level(pie, self.mx, self.my)]
        self.start = time.time()
        self.moved = False
        self.click_mode = False
        self.key = self.key or event.type
        space = type(context.space_data)
        self._space = space
        self._handle = space.draw_handler_add(self._draw, (), 'WINDOW', 'POST_PIXEL')
        self._timer = context.window_manager.event_timer_add(0.03, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        try:
            self._space.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, ReferenceError):
            pass
        context.window_manager.event_timer_remove(self._timer)
        if context.area:
            context.area.tag_redraw()

    def _pick(self, context):
        pie, index, _dist = self._active(context)
        self._finish(context)
        if pie is not None and index is not None:
            try:
                _pm().run_item(context, pie, index)
            except Exception as e:  # noqa: BLE001  report like a failed menu item would
                self.report({'WARNING'}, f"{pie.items[index].label or pie.items[index].idname}: {e}")
        return {'FINISHED'}

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()
        if event.type == 'MOUSEMOVE':
            self.mx, self.my = event.mouse_x, event.mouse_y
            pie, index, dist = self._active(context)
            if dist > 3 * self._scale():
                self.moved = True
            # moving past an item that opens another pie: open it here and keep going
            if index is not None and dist > self._radius(pie):
                item = pie.items[index]
                target = _pm().find_pie(item.idname) if item.kind == _pm().SUB else None
                if target is not None and target.menu_type == "PIE" and len(self.levels) < 8:
                    self.levels.append(Level(target, self.mx, self.my))
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._finish(context)
            return {'CANCELLED'}
        if event.type == self.key and event.value == 'RELEASE' and not self.click_mode:
            _pie, index, _dist = self._active(context)
            if index is not None:
                return self._pick(context)
            if not self.moved and time.time() - self.start < TAP_TIME:
                self.click_mode = True  # a quick tap: stay open, click to pick
                return {'RUNNING_MODAL'}
            self._finish(context)
            return {'CANCELLED'}
        if self.click_mode and event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            _pie, index, _dist = self._active(context)
            if index is None:
                self._finish(context)
                return {'CANCELLED'}
            return self._pick(context)
        if event.type.startswith("TIMER") or event.type in {self.key, 'LEFTMOUSE'}:
            return {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'}  # a marking menu takes every key while it's open, like a pie

    # ---- drawing
    def _draw(self):
        context = bpy.context
        if context.region is None or context.region.as_pointer() != self.region.as_pointer():
            return
        rx, ry = self.region.x, self.region.y
        theme = context.preferences.themes[0].user_interface.wcol_pie_menu
        inner, inner_sel = tuple(theme.inner), tuple(theme.inner_sel)
        text, text_sel = tuple(theme.text) + (1.0,), tuple(theme.text_sel) + (1.0,)
        outline = tuple(theme.outline) + (1.0,) if len(theme.outline) == 3 else tuple(theme.outline)
        s = self._scale()
        shown = self.click_mode or time.time() - self.start >= SHOW_DELAY
        gpu.state.blend_set('ALPHA')

        # the mark: from the first centre through every opened submenu to the mouse
        trail = [(lv.x - rx, lv.y - ry) for lv in self.levels] + [(self.mx - rx, self.my - ry)]
        _lines(trail, inner_sel[:3] + (0.9,), 2.0 * s)
        for lv in self.levels[:-1]:
            _circle(lv.x - rx, lv.y - ry, 4 * s, text[:3] + (0.5,), 1.0)

        level = self.levels[-1]
        pie, active, _dist = self._active(context)
        cx, cy = level.x - rx, level.y - ry
        _circle(cx, cy, self._threshold(pie) if pie else 8 * s, text[:3] + (0.8,), 1.5 * s)
        if not shown or pie is None:
            gpu.state.blend_set('NONE')
            return

        PM = _pm()
        size = int(12 * s)
        blf.size(0, size)
        r = self._radius(pie)
        pad_x, pad_y = 10 * s, 6 * s
        for direction, index in self._slots(context, pie).items():
            item = pie.items[index]
            if PM._is_empty(item):
                continue
            label = item.label or item.idname
            if item.kind == PM.SUB:
                label += "  ▸"  # opens another menu
            w, h = blf.dimensions(0, label)
            dx, dy = DIR_VECTORS[direction]
            # place boxes around the circle like Blender's pie: beside it on the sides, centred above and below
            bw, bh = w + 2 * pad_x, size + 2 * pad_y
            px, py = cx + dx * r, cy + dy * r
            bx = px if dx > 0.3 else (px - bw if dx < -0.3 else px - bw / 2)
            by = py if dy > 0.9 else (py - bh if dy < -0.9 else py - bh / 2)
            selected = index == active
            _rect(bx, by, bw, bh, inner_sel if selected else inner)
            _lines(((bx, by), (bx + bw, by), (bx + bw, by + bh), (bx, by + bh)), outline, 1.0, loop=True)
            blf.color(0, *(text_sel if selected else text))
            blf.position(0, bx + pad_x, by + pad_y + 1 * s, 0)
            blf.draw(0, label)
        # menu name under the centre
        blf.size(0, int(11 * s))
        tw, _th = blf.dimensions(0, pie.name)
        blf.color(0, *text[:3], 0.8)
        blf.position(0, cx - tw / 2, cy - self._threshold(pie) - 16 * s, 0)
        blf.draw(0, pie.name)
        gpu.state.blend_set('NONE')


def register():
    bpy.utils.register_class(WM_OT_keyops_marking_menu)


def unregister():
    bpy.utils.unregister_class(WM_OT_keyops_marking_menu)
