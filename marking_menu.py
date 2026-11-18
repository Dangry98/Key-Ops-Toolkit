"""Marking menus for Key Ops pie menus (Pie Style: Marking).

Press the key and flick: the direction picks the item, not the button under the mouse, and releasing
the key runs it, even before the menu has appeared. Hold still and the menu shows. Items that open
another pie menu open it right where the mouse is once you move past them, so you can keep flicking
A quick tap leaves the menu open to click; releasing in the middle cancels.
Drawn in dark charcoal items with Blender's selection blue as the highlight; every colour and size can be changed.
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


# Key Ops look: compact charcoal items, rounded a little, highlighted in Blender's selection blue
MARK_ITEM = (0.17, 0.17, 0.18, 0.96)
MARK_BORDER = (0.09, 0.09, 0.10, 1.0)
MARK_TEXT = (0.90, 0.90, 0.91, 1.0)
MARK_HIGHLIGHT = (0.278, 0.447, 0.702, 1.0)   # Blender's default selection blue (#4772B3)
MARK_TEXT_HIGHLIGHT = (1.0, 1.0, 1.0, 1.0)
MARK_LINE = (0.278, 0.447, 0.702, 0.85)       # the mark line, in the highlight colour
MARK_RING = (0.90, 0.90, 0.91, 0.9)
# Sizes follow Blender's own pie menu at its default Pie Menu Radius (100 px)
MARK_LINE_WIDTH = 0.0  # Blender's pie has no trail; the centre ring points at the item instead
MARK_BOX_H = 28      # box height (Blender's pie buttons are 1.4 widget units)
MARK_PAD = 10        # space each side of the label
MARK_FONT = 11       # label size (Blender's widget text)
MARK_CORNER = 4      # corner rounding
MARK_SIDE = 105      # left/right boxes: inner edge this far beside the centre
MARK_DIAG_X = 75     # corner boxes: inner edge this far beside the centre ...
MARK_DIAG_Y = 74     # ... and their middle this far above or below it
MARK_TOP = 120       # top/bottom boxes: middle this far above or below the centre
# Blender's pie number keys: the numpad layout (8 is up, 4 left, 6 right, 2 down, corners in between)
DIRECTION_NUMBERS = {"SW": 1, "S": 2, "SE": 3, "W": 4, "E": 6, "NW": 7, "N": 8, "NE": 9}
NUMBER_KEYS = {**{k: n for n, k in enumerate(("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"), 1)},
               **{f"NUMPAD_{n}": n for n in range(1, 10)}}
MARK_LAYOUT = {      # direction: (horizontal side, inner edge offset, vertical offset of the box middle)
    "E": (1, MARK_SIDE, 0), "W": (-1, MARK_SIDE, 0),
    "NE": (1, MARK_DIAG_X, MARK_DIAG_Y), "NW": (-1, MARK_DIAG_X, MARK_DIAG_Y),
    "SE": (1, MARK_DIAG_X, -MARK_DIAG_Y), "SW": (-1, MARK_DIAG_X, -MARK_DIAG_Y),
    "N": (0, 0, MARK_TOP), "S": (0, 0, -MARK_TOP)}


def _look():
    """The marking menu look from the preferences (Key Ops defaults if they can't be read)."""
    from .utils.pref_utils import get_keyops_prefs
    p = get_keyops_prefs()
    if not hasattr(p, "marking_item_color"):
        class Defaults:
            marking_item_color, marking_border_color, marking_text_color = MARK_ITEM, MARK_BORDER, MARK_TEXT
            marking_highlight_color, marking_highlight_text_color = MARK_HIGHLIGHT, MARK_TEXT_HIGHLIGHT
            marking_line_color, marking_center_color, marking_center, marking_text_align = MARK_LINE, MARK_RING, "PIE", "LEFT"
            marking_show_title, marking_show_numbers = True, True
            marking_line_width, marking_box_height, marking_padding, marking_font_size = MARK_LINE_WIDTH, MARK_BOX_H, MARK_PAD, MARK_FONT
            marking_corner, marking_side, marking_diag_x, marking_diag_y, marking_top = MARK_CORNER, MARK_SIDE, MARK_DIAG_X, MARK_DIAG_Y, MARK_TOP
            marking_delay = SHOW_DELAY
            marking_use_theme, marking_antialias, marking_shadow = True, True, False
        return Defaults
    return p


def _pm():
    from . import pie_menus
    return pie_menus


def _shader():
    return gpu.shader.from_builtin('UNIFORM_COLOR')


_smooth = True  # anti-aliased edges and lines for the menu being drawn (set per draw from the look)


def _poly(points, color, width=1.0, closed=False):
    """A line through the points: smooth (anti-aliased) or crisp."""
    pts = list(points) + ([points[0]] if closed else [])
    if len(pts) < 2:
        return
    if _smooth:
        region = bpy.context.region
        sh = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        batch = batch_for_shader(sh, 'LINE_STRIP', {"pos": pts})
        sh.bind()
        sh.uniform_float("viewportSize", (region.width, region.height))
        sh.uniform_float("lineWidth", width)
        sh.uniform_float("color", color)
        try:
            sh.uniform_bool("lineSmooth", True)
        except (ValueError, AttributeError):
            pass  # smooth is the default where the setting doesn't exist
        batch.draw(sh)
        return
    sh = _shader()
    batch = batch_for_shader(sh, 'LINE_STRIP', {"pos": pts})
    gpu.state.line_width_set(width)
    sh.bind()
    sh.uniform_float("color", color)
    batch.draw(sh)
    gpu.state.line_width_set(1.0)


def _fill(verts, indices, color):
    sh = _shader()
    batch = batch_for_shader(sh, 'TRIS', {"pos": verts}, indices=indices)
    sh.bind()
    sh.uniform_float("color", color)
    batch.draw(sh)


def _tri(points, color):
    _fill(points, [(0, 1, 2)], color)
    if _smooth:
        _poly(points, color, 1.0, closed=True)


def _rounded_outline(x, y, w, h, r, segments=10):
    r = max(0.0, min(r, w / 2, h / 2))
    if r <= 0:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    pts = []
    for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
        for k in range(segments + 1):
            a = math.radians(a0 + 90 * k / segments)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _rounded(x, y, w, h, r, color, edge=None):
    """A filled box with rounded corners; smooth edges in the edge colour (or its own) when anti-aliasing."""
    pts = _rounded_outline(x, y, w, h, r)
    verts = [(x + w / 2, y + h / 2)] + pts
    _fill(verts, [(0, i, i % len(pts) + 1) for i in range(1, len(pts) + 1)], color)
    if _smooth:
        _poly(pts, edge or color, 1.0, closed=True)


def _shadow(x, y, w, h, r, strength=0.22, size=5.0):
    """A soft drop shadow under a box, like Blender's menus."""
    steps = 5
    for i in range(steps, 0, -1):
        grow = size * i / steps
        a = strength * (1 - (i - 1) / steps) / steps * 2
        _rounded(x - grow, y - grow - 1.5, w + 2 * grow, h + 2 * grow, r + grow, (0, 0, 0, a))


def _circle_points(cx, cy, r, segments=32):
    return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in (i * 2 * math.pi / segments for i in range(segments))]


def _disc(cx, cy, r, fill, outline, segments=32):
    pts = _circle_points(cx, cy, r, segments)
    _fill([(cx, cy)] + pts, [(0, i, i % segments + 1) for i in range(1, segments + 1)], fill)
    _poly(pts, outline, 1.0, closed=True)


def _circle(cx, cy, r, color, width=1.5, segments=32):
    _poly(_circle_points(cx, cy, r, segments), color, width, closed=True)


def _pie_centre(cx, cy, s, ring, edge, lit, angle):
    """Blender's pie centre: a thick dark ring; a lit arc on it points at the item under the mouse."""
    r, t = 15 * s, 7 * s
    _poly(_circle_points(cx, cy, r + t / 2 + 0.5 * s, 48), edge, 1.0 * s, closed=True)
    _poly(_circle_points(cx, cy, r, 48), ring, t, closed=True)
    if angle is not None:
        arc = [(cx + r * math.cos(angle + a), cy + r * math.sin(angle + a))
               for a in (math.radians(d) for d in range(-35, 36, 5))]
        _poly(arc, lit, t)


class Level:
    """One open marking menu: which pie and where its centre is (window coordinates)."""

    def __init__(self, pie, x, y):
        self.uid = pie.uid
        self.x, self.y = x, y


class MenuState:
    """Everything an open marking menu needs, kept in plain Python, not on the operator.

    The draw callback only ever sees this object, never the operator or a stored Blender region: when Blender
    ends the operator from outside (loading a file, closing the window, disabling the add-on) those are freed,
    and touching them from a draw callback can crash Blender. The region is remembered by its address only."""

    def __init__(self, pie, event, key, region):
        self.mx, self.my = event.mouse_x, event.mouse_y
        self.levels = [Level(pie, self.mx, self.my)]
        self.start = time.time()
        self.moved = False
        self.click_mode = False
        self.key = key
        self.region_ptr = region.as_pointer()
        self.handle = None
        self.space = None
        self.timer = None

    # ---- geometry
    def _scale(self):
        return bpy.context.preferences.system.ui_scale

    def _radius(self, pie):
        """How far out the items are (for opening submenus); Pie Size scales the layout."""
        return (pie.radius or max(_look().marking_top, 1)) * self._scale()

    def _layout_scale(self, pie):
        return self._scale() * ((pie.radius / max(_look().marking_top, 1)) if pie.radius else 1.0)

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
        if index is not None and (index >= len(pie.items) or _pm()._is_empty(pie.items[index])):
            index = None
        return pie, index, dist

    # ---- drawing (called by Blender's draw callback, with only this object)
    def _colours(self, look):
        """(item, highlight, text, highlight text, border, line, centre): the theme's pie menu colours, or the look's own."""
        if look.marking_use_theme:
            w = bpy.context.preferences.themes[0].user_interface.wcol_pie_menu
            rgba = lambda c: tuple(c) if len(c) == 4 else tuple(c) + (1.0,)
            sel = rgba(w.inner_sel)
            return (rgba(w.inner), sel, rgba(w.text), rgba(w.text_sel), rgba(w.outline), sel[:3] + (0.9,), rgba(w.text))
        return tuple(tuple(getattr(look, f"marking_{n}_color")) for n in
                     ("item", "highlight", "text", "highlight_text", "border", "line", "center"))

    def _draw(self):
        global _smooth
        context = bpy.context
        region = context.region
        if region is None or region.as_pointer() != self.region_ptr:
            return
        look = _look()
        _smooth = look.marking_antialias
        item_c, high_c, text_c, high_text_c, border, line_c, centre_c = self._colours(look)
        rx, ry = region.x, region.y
        s = self._scale()
        shown = self.click_mode or time.time() - self.start >= look.marking_delay
        gpu.state.blend_set('ALPHA')

        # the mark: a line from the first press through every opened submenu to the mouse
        if look.marking_line_width > 0:
            trail = [(lv.x - rx, lv.y - ry) for lv in self.levels] + [(self.mx - rx, self.my - ry)]
            _poly(trail, line_c, look.marking_line_width * s)
        level = self.levels[-1]
        pie, active, dist_now = self._active(context)
        for i, lv in enumerate(self.levels):  # a ring or a dot at every centre
            if look.marking_center == "DOT":
                _disc(lv.x - rx, lv.y - ry, 6 * s, centre_c, border)
            elif look.marking_center == "PIE":  # Blender's pie centre: a thick ring, lit toward the mouse
                top = i == len(self.levels) - 1
                ang = math.atan2(self.my - lv.y, self.mx - lv.x)
                lit = top and pie is not None and dist_now >= self._threshold(pie)
                _pie_centre(lv.x - rx, lv.y - ry, s, item_c, border, high_c, ang if lit else None)
            else:
                _circle(lv.x - rx, lv.y - ry, 5 * s, centre_c, 1.5 * s)
        if not shown or pie is None:
            gpu.state.blend_set('NONE')
            return

        PM = _pm()
        cx, cy = level.x - rx, level.y - ry
        k = self._layout_scale(pie)
        size = look.marking_font_size * s
        blf.size(0, size)
        bh = look.marking_box_height * s
        pad = look.marking_padding * s
        r = (bpy.context.preferences.themes[0].user_interface.wcol_pie_menu.roundness * bh / 2
             if look.marking_use_theme else look.marking_corner * s)
        layout = {"E": (1, look.marking_side, 0), "W": (-1, look.marking_side, 0),
                  "NE": (1, look.marking_diag_x, look.marking_diag_y), "NW": (-1, look.marking_diag_x, look.marking_diag_y),
                  "SE": (1, look.marking_diag_x, -look.marking_diag_y), "SW": (-1, look.marking_diag_x, -look.marking_diag_y),
                  "N": (0, 0, look.marking_top), "S": (0, 0, -look.marking_top)}
        if look.marking_show_title:  # the menu's name above the centre, dim, like Blender's pie
            blf.size(0, size)
            tw = blf.dimensions(0, pie.name)[0]
            blf.color(0, *text_c[:3], 0.6)
            blf.position(0, cx - tw / 2, cy + 28 * s * k, 0)
            blf.draw(0, pie.name)
        numbers = look.marking_show_numbers
        num_w = blf.dimensions(0, "8")[0] + 10 * s if numbers else 0
        boxes = []
        for direction, index in self._slots(context, pie).items():
            item = pie.items[index]
            if PM._is_empty(item):
                continue
            label = item.label or item.idname
            sub = item.kind == PM.SUB
            w, _h = blf.dimensions(0, label)
            arrow = 12 * s if sub else 0
            bw = w + 2 * pad + arrow + num_w
            if numbers:  # Blender's pie buttons keep room for an icon: never narrower than this
                bw = max(bw, 3.4 * bh)
            side, inner, mid = layout[direction]
            bx = cx + inner * k if side > 0 else (cx - inner * k - bw if side < 0 else cx - bw / 2)
            by = cy + mid * k - bh / 2
            boxes.append((bx, by, bw, w, arrow, label, sub, index == active, DIRECTION_NUMBERS.get(direction)))
        if look.marking_shadow:  # shadows first, so no box's shadow falls on another box
            for bx, by, bw, *_rest in boxes:
                _shadow(bx, by, bw, bh, r, size=5 * s)
        for bx, by, bw, w, arrow, label, sub, selected, number in boxes:
            if _smooth:  # fill, then the border as one smooth line along the same edge
                _rounded(bx, by, bw, bh, r, high_c if selected else item_c, edge=border)
            else:  # crisp: a border box behind the item, pixel exact
                _rounded(bx - 1, by - 1, bw + 2, bh + 2, r + 1 if r else 0, border)
                _rounded(bx, by, bw, bh, r, high_c if selected else item_c)
            colour = high_text_c if selected else text_c
            blf.color(0, *colour)
            tx = bx + (bw - arrow - num_w - w) / 2 if look.marking_text_align == "CENTER" else bx + pad
            ty = by + (bh - size * 0.72) / 2
            blf.position(0, tx, ty, 0)
            blf.draw(0, label)
            if numbers and number:  # the number key that picks it, dim on the right
                blf.color(0, *colour[:3], colour[3] * 0.5)
                blf.position(0, bx + bw - pad - arrow - blf.dimensions(0, str(number))[0], ty, 0)
                blf.draw(0, str(number))
            if sub:  # a small triangle for items that open another marking menu
                ax, ay, t = bx + bw - 10 * s, by + bh / 2, 3.5 * s
                _tri(((ax - t * 0.7, ay - t), (ax - t * 0.7, ay + t), (ax + t * 0.7, ay)), colour)
        gpu.state.blend_set('NONE')




_open = []  # the open marking menu's state (at most one), so it can be cleaned up from anywhere


def close_all():
    """Remove what an open marking menu added (draw callback, timer). Safe to call any time."""
    while _open:
        st = _open.pop()
        if st.handle is not None:
            try:
                st.space.draw_handler_remove(st.handle, 'WINDOW')
            except (ValueError, ReferenceError):
                pass
            st.handle = None
        if st.timer is not None:
            try:
                bpy.context.window_manager.event_timer_remove(st.timer)
            except (ValueError, ReferenceError, AttributeError):
                pass
            st.timer = None
    for window in getattr(bpy.context.window_manager, "windows", ()):
        for area in window.screen.areas:
            area.tag_redraw()


def _draw_callback(st):
    if st not in _open:  # ended without cleaning up: never draw a stale menu
        return
    try:
        st._draw()
    except ReferenceError:  # the pie or its data went away while the menu was open
        pass


@bpy.app.handlers.persistent
def _on_load(_dummy=None):
    close_all()  # loading a file ends a running menu without telling it


class WM_OT_keyops_marking_menu(bpy.types.Operator):
    bl_idname = "wm.keyops_marking_menu"
    bl_label = "Key Ops Marking Menu"
    bl_description = "Open a Key Ops pie as a marking menu"
    bl_options = {'INTERNAL'}

    pie: StringProperty() # type: ignore
    key: StringProperty() # type: ignore  # releasing this key picks

    # ---- running
    def invoke(self, context, event):
        pie = _pm().find_pie(self.pie)
        if pie is None or context.area is None:
            return {'CANCELLED'}
        close_all()  # only one at a time
        region = next((r for r in context.area.regions if r.type == 'WINDOW'), context.region)
        st = MenuState(pie, event, self.key or event.type, region)
        st.space = type(context.space_data)
        st.handle = st.space.draw_handler_add(_draw_callback, (st,), 'WINDOW', 'POST_PIXEL')
        st.timer = context.window_manager.event_timer_add(0.03, window=context.window)
        _open.append(st)
        self.st = st
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        close_all()  # Blender ended the menu (another file, window closed)

    def _finish(self, context):
        close_all()

    def _pick(self, context, chosen=None):
        pie, index = chosen if chosen else self.st._active(context)[:2]
        self._finish(context)
        if pie is not None and index is not None:
            try:
                _pm().run_item(context, pie, index)
            except Exception as e:  # noqa: BLE001  report like a failed menu item would
                self.report({'WARNING'}, f"{pie.items[index].label or pie.items[index].idname}: {e}")
        return {'FINISHED'}

    def modal(self, context, event):
        st = self.st
        if st not in _open:  # cleaned up from elsewhere
            return {'CANCELLED'}
        if context.area:
            context.area.tag_redraw()
        if event.type == 'MOUSEMOVE':
            st.mx, st.my = event.mouse_x, event.mouse_y
            pie, index, dist = st._active(context)
            if pie is None:
                self._finish(context)
                return {'CANCELLED'}
            if dist > 3 * st._scale():
                st.moved = True
            # moving past an item that opens another pie: open it here and keep going
            if index is not None and dist > st._radius(pie):
                item = pie.items[index]
                target = _pm().find_pie(item.idname) if item.kind == _pm().SUB else None
                if target is not None and target.menu_type == "PIE" and len(st.levels) < 8:
                    st.levels.append(Level(target, st.mx, st.my))
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._finish(context)
            return {'CANCELLED'}
        if event.type in NUMBER_KEYS and event.value == 'PRESS':  # 1 to 9 pick like in Blender's pie
            pie = _pm().find_pie(st.levels[-1].uid)
            direction = next((d for d, n in DIRECTION_NUMBERS.items() if n == NUMBER_KEYS[event.type]), None)
            index = st._slots(context, pie).get(direction) if pie is not None and direction else None
            if index is not None and not _pm()._is_empty(pie.items[index]):
                return self._pick(context, (pie, index))
            return {'RUNNING_MODAL'}
        if event.type == st.key and event.value == 'RELEASE' and not st.click_mode:
            _pie, index, _dist = st._active(context)
            if index is not None:
                return self._pick(context)
            if not st.moved and time.time() - st.start < TAP_TIME:
                st.click_mode = True  # a quick tap: stay open, click to pick
                return {'RUNNING_MODAL'}
            self._finish(context)
            return {'CANCELLED'}
        if st.click_mode and event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            _pie, index, _dist = st._active(context)
            if index is None:
                self._finish(context)
                return {'CANCELLED'}
            return self._pick(context)
        return {'RUNNING_MODAL'}  # a marking menu takes every key while it's open, like a pie


class KEYOPS_OT_marking_look_reset(bpy.types.Operator):
    bl_idname = "keyops.marking_look_reset"
    bl_label = "Reset Look"
    bl_description = "Put every marking menu colour and size back to the Key Ops defaults"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from .utils.pref_utils import get_keyops_prefs
        p = get_keyops_prefs()
        for name in p.bl_rna.properties.keys():
            if name.startswith("marking_"):
                p.property_unset(name)
        return {'FINISHED'}


LOOKS = {
    # Blender: drawn like Blender's own pie menu, in your theme's pie colours: the menu name above a centre
    # ring that points at the item, roomy boxes spread around it, number keys shown on the right
    "BLENDER": dict(marking_use_theme=True, marking_antialias=True, marking_shadow=False, marking_center="PIE",
                    marking_show_title=True, marking_show_numbers=True,
                    marking_text_align="LEFT", marking_line_width=MARK_LINE_WIDTH, marking_box_height=MARK_BOX_H,
                    marking_padding=MARK_PAD, marking_font_size=MARK_FONT, marking_side=MARK_SIDE,
                    marking_diag_x=MARK_DIAG_X, marking_diag_y=MARK_DIAG_Y, marking_top=MARK_TOP),
    # classic: flat, square, crisp boxes in mid grey, packed close to the centre
    "CLASSIC": dict(marking_use_theme=False, marking_antialias=False, marking_shadow=False, marking_center="DOT",
                    marking_show_title=False, marking_show_numbers=False,
                    marking_text_align="CENTER", marking_item_color=(0.322, 0.322, 0.322, 1.0),
                    marking_border_color=(0.0, 0.0, 0.0, 1.0), marking_text_color=(0.933, 0.933, 0.933, 1.0),
                    marking_highlight_color=(0.322, 0.522, 0.651, 1.0), marking_highlight_text_color=(0.933, 0.933, 0.933, 1.0),
                    marking_line_color=(0.502, 0.502, 0.502, 1.0), marking_center_color=(0.502, 0.502, 0.502, 1.0),
                    marking_line_width=3.0, marking_box_height=18, marking_padding=26, marking_font_size=10.5,
                    marking_corner=0, marking_side=56, marking_diag_x=40, marking_diag_y=29, marking_top=55),
}


class KEYOPS_OT_marking_look(bpy.types.Operator):
    bl_idname = "keyops.marking_look"
    bl_label = "Marking Menu Look"
    bl_description = "Set every marking menu colour and size to one of the looks"
    bl_options = {'INTERNAL'}
    look: bpy.props.EnumProperty(items=(
        ("BLENDER", "Blender", "Like Blender's own pie menus: your theme's pie colours, the menu name above a centre "
                               "ring that points at the item, number keys on the right"),
        ("CLASSIC", "Classic", "Flat, square, crisp mid-grey boxes packed close to the centre, a filled centre dot"))) # type: ignore

    @classmethod
    def description(cls, context, props):
        return cls.bl_rna.properties["look"].enum_items[props.look].description

    def execute(self, context):
        from .utils.pref_utils import get_keyops_prefs
        p = get_keyops_prefs()
        for name, value in LOOKS[self.look].items():
            setattr(p, name, value)
        return {'FINISHED'}


def draw_look_settings(prefs, layout):
    """The marking menu look, under the Style option."""
    row = layout.row(align=True)
    row.operator("keyops.marking_look", text="Blender").look = "BLENDER"
    row.operator("keyops.marking_look", text="Classic").look = "CLASSIC"
    flags = layout.column(align=True)
    flags.prop(prefs, "marking_use_theme")
    flags.prop(prefs, "marking_antialias")
    flags.prop(prefs, "marking_shadow")
    flags.prop(prefs, "marking_show_title")
    flags.prop(prefs, "marking_show_numbers")
    col = layout.column(align=True)
    col.active = not prefs.marking_use_theme  # the theme decides these while it's used
    grid = col.grid_flow(columns=2, even_columns=True, align=True)
    for name in ("item", "highlight", "text", "highlight_text", "border", "line", "center"):
        grid.prop(prefs, f"marking_{name}_color")
    layout.separator(factor=0.5)
    col = layout.column(align=True)
    col.prop(prefs, "marking_font_size")
    col.prop(prefs, "marking_box_height")
    col.prop(prefs, "marking_padding")
    corner = col.row(align=True)
    corner.active = not prefs.marking_use_theme
    corner.prop(prefs, "marking_corner")
    col.prop(prefs, "marking_line_width")
    layout.separator(factor=0.5)
    col = layout.column(align=True)
    col.prop(prefs, "marking_side")
    col.prop(prefs, "marking_diag_x")
    col.prop(prefs, "marking_diag_y")
    col.prop(prefs, "marking_top")
    layout.separator(factor=0.5)
    for name, text in (("marking_center", "Centre"), ("marking_text_align", "Text")):
        row = layout.split(factor=0.3, align=True)
        row.label(text=text)
        row.row(align=True).prop(prefs, name, expand=True)
    layout.prop(prefs, "marking_delay")
    layout.operator("keyops.marking_look_reset", icon='LOOP_BACK')


def register():
    bpy.utils.register_class(WM_OT_keyops_marking_menu)
    if _on_load not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(_on_load)
    bpy.utils.register_class(KEYOPS_OT_marking_look_reset)
    bpy.utils.register_class(KEYOPS_OT_marking_look)


def unregister():
    close_all()  # a menu open while the add-on is turned off
    if _on_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_on_load)
    bpy.utils.unregister_class(KEYOPS_OT_marking_look)
    bpy.utils.unregister_class(KEYOPS_OT_marking_look_reset)
    bpy.utils.unregister_class(WM_OT_keyops_marking_menu)
