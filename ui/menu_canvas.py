"""The Custom Menus preview in the preferences, drawn with the GPU.

Blender's layouts can't draw a pie the way a pie looks, and can't drag things around. So the preview
reserves an empty area in the layout, framed by two thin colour swatches in colours nothing else uses
(the markers). A draw callback on the Preferences editor finds the markers in what was just drawn (a few
pixels read back), paints over the area and draws the menu there:

- Blender pies: sizes, positions, centre ring, number hints and underlined keys worked out the way
  Blender's own pie code does it (interface_layout.cc, interface_widgets.cc), in your theme's colours.
- Marking menus: drawn by the same code the real marking menu uses (marking_menu.py).
- Popup menus, dialogs and panels: Blender's menu, popup and panel look.

Blender's icons can't be drawn from Python, so the layout also draws the icons the menu needs in a row
inside the area; the callback picks them up from the screen before painting over them.

A modal operator runs while the preview is on screen, passing every event through except clicks and
drags on the preview's items: click an item to change it, drag it to move it.
"""

import math
import time

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

MARK_TOP = (1.0, 0.0, 1.0)      # top marker swatch
MARK_BOTTOM = (0.0, 1.0, 1.0)   # bottom marker swatch
MARK_SCALE = 0.3                # marker rows are this many rows tall
ICONS_PER_ROW = 16
DRAG_START = 5                  # pixels the mouse moves with the button down before it's a drag
FONT_POINTS = 11.0              # Blender's widget text size


def _pm():
    from .. import pie_menus
    return pie_menus


def _mm():
    from .. import marking_menu
    return marking_menu


def _prefs():
    from ..utils.pref_utils import get_keyops_prefs
    return get_keyops_prefs()


# ---------------------------------------------------------------- sizes and theme

def ui_scale():
    return bpy.context.preferences.system.ui_scale


def pixel():
    return bpy.context.preferences.system.pixel_size


def unit():
    """Blender's U.widget_unit: the height of a button."""
    return int(round(18.0 * ui_scale())) + 2 * int(pixel())


def _rgba(c, alpha=None):
    c = tuple(c)
    if len(c) == 3:
        c = c + (1.0,)
    return c if alpha is None else c[:3] + (c[3] * alpha,)


def _theme():
    return bpy.context.preferences.themes[0].user_interface


_font_px = FONT_POINTS


def _font(points=FONT_POINTS):
    global _font_px
    _font_px = points * ui_scale()
    blf.size(0, _font_px)


def _text_w(text):
    return blf.dimensions(0, text)[0] if text else 0.0


def _text_h():
    """Ascender + descender of the UI font at its current size (BLF_ascender + BLF_descender, which
    Python can't ask for): for Blender's Inter font that's 0.727 of the size, its cap height."""
    return 0.727 * _font_px + 2 * pixel()  # +2: measured against Blender's own pie items


# ---------------------------------------------------------------- drawing primitives

def _shader():
    return gpu.shader.from_builtin('UNIFORM_COLOR')


def _fill(verts, indices, color):
    gpu.state.blend_set('ALPHA')  # blf.draw turns blending off when it's done
    sh = _shader()
    batch = batch_for_shader(sh, 'TRIS', {"pos": verts}, indices=indices)
    sh.bind()
    sh.uniform_float("color", color)
    batch.draw(sh)


def _rect(x, y, w, h, color):
    _fill([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], [(0, 1, 2), (0, 2, 3)], color)


def _corner_radii(r, join):
    """(bottom right, top right, top left, bottom left) radii: square where the side is joined to a neighbour."""
    return (0 if {"R", "B"} & join else r, 0 if {"R", "T"} & join else r,
            0 if {"L", "T"} & join else r, 0 if {"L", "B"} & join else r)


def _outline_pts(x, y, w, h, r, seg=8):
    if isinstance(r, tuple):
        lim = min(w / 2, h / 2)
        pts = []
        for (cx, cy, a0), rr in zip(((x + w, y, -90), (x + w, y + h, 0), (x, y + h, 90), (x, y, 180)), r):
            rr = max(0.0, min(rr, lim))
            ox = -rr if cx > x else rr
            oy = rr if cy == y else -rr
            if rr <= 0.01:
                pts.append((cx, cy))
                continue
            for k in range(seg + 1):
                a = math.radians(a0 + 90 * k / seg)
                pts.append((cx + ox + rr * math.cos(a), cy + oy + rr * math.sin(a)))
        return pts
    r = max(0.0, min(r, w / 2, h / 2))
    if r <= 0.01:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    pts = []
    for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _line(pts, color, width=1.0, closed=False):
    pts = list(pts) + ([pts[0]] if closed else [])
    if len(pts) < 2:
        return
    region = bpy.context.region
    gpu.state.blend_set('ALPHA')
    sh = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(sh, 'LINE_STRIP', {"pos": pts})
    sh.bind()
    sh.uniform_float("viewportSize", (region.width, region.height))
    sh.uniform_float("lineWidth", width)
    sh.uniform_float("color", color)
    batch.draw(sh)


def _round_fill(x, y, w, h, r, color):
    pts = _outline_pts(x, y, w, h, r)
    _fill([(x + w / 2, y + h / 2)] + pts, [(0, i, i % len(pts) + 1) for i in range(1, len(pts) + 1)], color)


def _round_fill_grad(x, y, w, h, r, top, bottom):
    """A rounded box filled with a top-to-bottom gradient (Blender's shaded widgets)."""
    pts = _outline_pts(x, y, w, h, r)
    mix = lambda f: tuple(bottom[k] + (top[k] - bottom[k]) * f for k in range(4))
    verts = [(x + w / 2, y + h / 2)] + pts
    cols = [mix(0.5)] + [mix(min(1.0, max(0.0, (py - y) / max(h, 1)))) for _px, py in pts]
    gpu.state.blend_set('ALPHA')
    sh = gpu.shader.from_builtin('SMOOTH_COLOR')
    batch = batch_for_shader(sh, 'TRIS', {"pos": verts, "color": cols},
                             indices=[(0, i, i % len(pts) + 1) for i in range(1, len(pts) + 1)])
    sh.bind()
    batch.draw(sh)


def _shade(c, amount):
    """Blender's shadecolors4: a theme shade offset (-100..100, in 0..255 steps) added to a colour."""
    return tuple(min(1.0, max(0.0, c[k] + amount / 255.0)) for k in range(3)) + (c[3],)


def widget_box(x, y, w, h, r, inner, outline=None, join=(), wcol=None, emboss=False):
    """A Blender widget backdrop: the fill inside a one pixel outline, with smooth corners (square where it
    joins a neighbour in an aligned row or column). With the theme's widget colours (wcol): its shading
    gradient when the theme has Shaded on; emboss: the theme's emboss line under the widget."""
    if join:
        r = _corner_radii(r, set(join))
    shrink = (lambda rr, d: tuple(max(0.0, v - d) for v in rr)) if isinstance(r, tuple) else (lambda rr, d: max(0.0, rr - d))
    if emboss and h > 4:
        try:
            emb = _rgba(_theme().widget_emboss)
        except AttributeError:
            emb = (1, 1, 1, 0.05)
        if emb[3] > 0 and "B" not in set(join):
            pts = [p for p in _outline_pts(x + 0.5, y - 0.5, w - 1, h - 1, shrink(r, 0.5)) if p[1] < y + h * 0.35]
            if len(pts) > 1:
                pts.sort(key=lambda p: p[0])
                _line(pts, emb, 1.0)
    shaded = wcol is not None and getattr(wcol, "show_shaded", False)
    if outline is not None and outline[3] > 0:
        _round_fill(x, y, w, h, r, outline)
        px = pixel()
        if shaded:
            _round_fill_grad(x + px, y + px, w - 2 * px, h - 2 * px, shrink(r, px),
                             _shade(inner, wcol.shadetop), _shade(inner, wcol.shadedown))
        else:
            _round_fill(x + px, y + px, w - 2 * px, h - 2 * px, shrink(r, px), inner)
        _line(_outline_pts(x + 0.5, y + 0.5, w - 1, h - 1, shrink(r, 0.5)), outline, 1.0, closed=True)
    else:
        _round_fill(x, y, w, h, r, inner)
        if inner[3] > 0:
            _line(_outline_pts(x + 0.5, y + 0.5, w - 1, h - 1, shrink(r, 0.5)), inner, 1.0, closed=True)


def _shadow(x, y, w, h, r, size, strength=0.35):
    steps = 6
    for i in range(steps, 0, -1):
        grow = size * i / steps
        a = strength * (1 - (i - 1) / steps) / steps * 1.6
        _round_fill(x - grow, y - grow - size * 0.35, w + 2 * grow, h + 2 * grow, r + grow, (0, 0, 0, a))


def _disk(cx, cy, r0, r1, a0, arc, color, seg=40):
    n = max(2, int(seg * arc / (2 * math.pi)))
    verts, idx = [], []
    for k in range(n + 1):
        a = a0 + arc * k / n
        c, s = math.cos(a), math.sin(a)
        verts += [(cx + c * r0, cy + s * r0), (cx + c * r1, cy + s * r1)]
    for k in range(n):
        i = 2 * k
        idx += [(i, i + 1, i + 3), (i, i + 3, i + 2)]
    _fill(verts, idx, color)


def _circle(cx, cy, r, color, seg=40):
    _line([(cx + r * math.cos(2 * math.pi * k / seg), cy + r * math.sin(2 * math.pi * k / seg)) for k in range(seg)],
          color, 1.0, closed=True)


def _text(x, y, text, color):
    blf.color(0, *color)
    blf.position(0, round(x), round(y), 0)
    blf.draw(0, text)


def _text_in(x, y, w, h, text, color, align="LEFT"):
    """Text placed in a rectangle the way UI_fontstyle_draw does: vertically centred on the font height."""
    yofs = math.ceil(0.5 * (h - _text_h()))
    tw = _text_w(text)
    xofs = 0 if align == "LEFT" else (math.floor(0.5 * (w - tw)) if align == "CENTER" else w - tw)
    _text(x + max(0, xofs), y + max(0, yofs), text, color)
    return x + max(0, xofs), y + max(0, yofs)


def _underline(tx, ty, text, key, color):
    """The underline under an item's accelerator key, as Blender draws it (with a "_" glyph)."""
    i = text.find(key.upper())
    if i < 0:
        i = text.find(key)
    if i < 0:
        return
    x0 = _text_w(text[:i])
    cw = _text_w(text[:i + 1]) - x0
    uw = _text_w("_")
    _text(tx + x0 + (cw - uw) / 2, ty - pixel(), "_", color)


def _tria_right(x, y, size, color):
    _fill([(x - size * 0.35, y - size * 0.5), (x - size * 0.35, y + size * 0.5), (x + size * 0.45, y)], [(0, 1, 2)], color)


# ---------------------------------------------------------------- icons picked up from the screen

class IconCache:
    """Icon name -> (texture, size, mono). Mono icons are drawn tinted with the text colour, like Blender does."""

    def __init__(self):
        self.tex = {}
        self.atlases = []
        self.key = None  # (ui scale, background) the icons were picked up at

    def get(self, name):
        return self.tex.get(name)


_icons = IconCache()


def _capture_icons(fb, vp, names, x0, ytop, u, bg):
    """Read the icon row(s) the layout drew under the top marker (cells u wide from x0, top edge ytop) into one
    texture: mono icons as white with alpha (tinted when drawn), coloured ones in their own colours."""
    import numpy as np  # bundled with Blender
    rows = (len(names) + ICONS_PER_ROW - 1) // ICONS_PER_ROW
    if not rows:
        return
    w = min(len(names), ICONS_PER_ROW) * u
    h = rows * u
    buf = fb.read_color(vp[0] + int(x0), vp[1] + int(ytop - h), int(w), int(h), 4, 0, 'FLOAT')
    buf.dimensions = int(w) * int(h) * 4
    px = np.array(buf.to_list(), dtype=np.float32).reshape(int(h), int(w), 4)
    bgc = np.array(bg[:3], dtype=np.float32)
    out = np.zeros((int(h), int(w), 4), dtype=np.float32)
    found = {}
    for n, name in enumerate(names):
        r, c = divmod(n, ICONS_PER_ROW)
        y0 = int(h) - (r + 1) * u
        cell = px[y0:y0 + u, c * u:(c + 1) * u, :3]
        d = cell - bgc
        mag = np.abs(d).max(axis=2)
        if mag.max() < 0.02:
            _icons.tex[name] = None  # nothing drawn there (an unknown icon): don't look again
            continue
        sat = cell.max(axis=2) - cell.min(axis=2)
        lum = cell.mean(axis=2) - bgc.mean()
        strong = mag > 0.1
        mono = float(sat[strong].max()) < 0.12 if strong.any() else True
        o = out[y0:y0 + u, c * u:(c + 1) * u]
        if mono:
            peak = lum.flat[np.abs(lum).argmax()]
            o[..., :3] = 1.0
            o[..., 3] = np.clip(lum / (peak if abs(peak) > 0.05 else 1.0), 0.0, 1.0)
        else:
            room = np.where(d >= 0, 1.0 - bgc, bgc)
            a = np.clip((np.abs(d) / np.maximum(room, 1e-3)).max(axis=2), 0.0, 1.0)
            o[..., 3] = a
            o[..., :3] = np.clip(bgc + d / np.maximum(a, 1e-3)[..., None], 0.0, 1.0)
        found[name] = ((c * u) / w, y0 / h, ((c + 1) * u) / w, (y0 + u) / h, mono)
    data = gpu.types.Buffer('FLOAT', int(w) * int(h) * 4, out.ravel().tolist())
    tex = gpu.types.GPUTexture((int(w), int(h)), format='RGBA16F', data=data)
    _icons.atlases.append(tex)
    for name, (u0, v0, u1, v1, mono) in found.items():
        _icons.tex[name] = (tex, u, (u0, v0, u1, v1), mono)


_icon_queue = []  # icons wait here and are drawn together (see flush_icons)


def draw_icon(name, cx, cy, tint, alpha=1.0):
    """Queue a picked-up icon centred on (cx, cy), pixel aligned. Drawn by flush_icons."""
    if name == ADD_ICON:  # an item without an icon, hovered: a spot to click to pick one
        _add_icon(cx, cy, tint, alpha)
        return
    got = _icons.get(name)
    if got is None:
        return
    tex, size, uv, mono = got
    x, y = round(cx - size / 2), round(cy - size / 2)
    colour = (tint[0], tint[1], tint[2], tint[3] * alpha) if mono else (1, 1, 1, alpha)
    _icon_queue.append((tex, x, y, size, uv, colour))


def _add_icon(cx, cy, tint, alpha=1.0):
    s = ui_scale()
    size = 14 * s
    col = (tint[0], tint[1], tint[2], tint[3] * alpha * 0.55)
    x, y = round(cx - size / 2) + 0.5, round(cy - size / 2) + 0.5
    pts = _outline_pts(x, y, size, size, 3 * s)
    for k in range(0, len(pts), 2):  # dashed
        _line(pts[k:k + 2], col, 1.0)
    p = 3.5 * s
    _line([(cx - p, cy), (cx + p, cy)], col, 1.2 * s)
    _line([(cx, cy - p), (cx, cy + p)], col, 1.2 * s)


def _tcol(el, c):
    """Text and icon colour: faded for an inactive item (Active off), and for the action's name shown while hovered."""
    a = c[3]
    if not el.active:
        a *= 0.5
    if el.dim:
        a *= 0.5
    return c[:3] + (a,)


def flush_icons():
    """Draw the queued icons. Text drawn between texture draws can leave the wrong texture bound,
    so all icons are drawn here, one after another, after the shapes and text of a layer."""
    gpu.state.blend_set('ALPHA')
    sh = gpu.shader.from_builtin('IMAGE_COLOR')
    for tex, x, y, size, (u0, v0, u1, v1), colour in _icon_queue:
        batch = batch_for_shader(sh, 'TRI_FAN', {"pos": ((x, y), (x + size, y), (x + size, y + size), (x, y + size)),
                                                 "texCoord": ((u0, v0), (u1, v0), (u1, v1), (u0, v1))})
        sh.bind()
        sh.uniform_sampler("image", tex)
        sh.uniform_float("color", colour)
        batch.draw(sh)
    _icon_queue.clear()


# ---------------------------------------------------------------- scene: what is drawn where

class El:
    """One drawn thing: an item (index), its rectangle and how it's drawn."""
    __slots__ = ("index", "x", "y", "w", "h", "kind", "text", "icon", "num", "key", "sub", "style", "icon_rect", "col",
                 "emboss", "active", "depress", "dim", "join", "show")

    def __init__(self, index, x, y, w, h, kind="item", text="", icon="", **kw):
        self.index, self.x, self.y, self.w, self.h = index, x, y, w, h
        self.kind, self.text, self.icon = kind, text, icon
        self.num = kw.get("num", "")
        self.key = kw.get("key", "")
        self.sub = kw.get("sub", False)
        self.style = kw.get("style", "")
        self.icon_rect = kw.get("icon_rect")
        self.col = kw.get("col", 0)
        self.emboss = kw.get("emboss", True)
        self.active = kw.get("active", True)
        self.depress = kw.get("depress", False)
        self.dim = kw.get("dim", False)  # the text is the action's name, shown while hovered (an icon-only item)
        self.join = set()  # sides joined to a neighbour in an aligned row or column: "L", "R", "T", "B"
        self.show = True   # markers: drawn and clickable now

    def contains(self, mx, my, pad=0):
        return self.x - pad <= mx <= self.x + self.w + pad and self.y - pad <= my <= self.y + self.h + pad

    def moved(self, dx, dy):
        self.x += dx
        self.y += dy
        if self.icon_rect:
            ix, iy, iw, ih = self.icon_rect
            self.icon_rect = (ix + dx, iy + dy, iw, ih)


class Scene:
    def __init__(self, kind):
        self.kind = kind     # "BLENDER_PIE", "MARKING", "MENU", "PANEL"
        self.els = []
        self.w = self.h = 0  # content size
        self.cx = self.cy = 0.0
        self.frame = None    # (x, y, w, h) popup / panel backdrop
        self.title = ""
        self.title_rect = None
        self.radius = self.threshold = 0.0
        self.dirmask = (False, False)  # (has axis aligned, has diagonal) items
        self.marking = None  # marking menu boxes
        self.panel_header = None
        self.boxes = []      # (x, y, w, h) frames of box groups, drawn behind their items
        self.panels = []     # (x, y, w, h, closed) headers of panel groups
        self.groups = []     # (start index, x, y, w, h, layout) of every group
        self.show_markers = False  # group tags and End Group / Next Column markers: while the mouse is on the menu

    def hit(self, mx, my):
        for el in reversed(self.els):
            if el.kind in ("marker", "grouptag") and not (self.show_markers and el.show):
                continue
            if el.kind in ("item", "empty", "marker", "boxhead", "label", "sep", "group", "grouptag") and el.contains(mx, my):
                return el
        return None

    def offset(self, dx, dy):
        for el in self.els:
            el.moved(dx, dy)
        self.cx += dx
        self.cy += dy
        if self.frame:
            x, y, w, h = self.frame
            self.frame = (x + dx, y + dy, w, h)
        if self.title_rect:
            x, y, w, h = self.title_rect
            self.title_rect = (x + dx, y + dy, w, h)
        if self.panel_header:
            x, y, w, h = self.panel_header
            self.panel_header = (x + dx, y + dy, w, h)
        if self.marking:
            self.marking = [(bx + dx, by + dy) + tuple(rest) for bx, by, *rest in self.marking]
        self.boxes = [(x + dx, y + dy, w, h) for x, y, w, h in self.boxes]
        self.panels = [(x + dx, y + dy, w, h, c) for x, y, w, h, c in self.panels]
        self.groups = [(i, x + dx, y + dy, w, h, t) for i, x, y, w, h, t in self.groups]


ADD_ICON = "+ADD"  # the icon spot a hovered item shows when it has no icon yet: click it to pick one


def _look(item):
    return dict(emboss=item.emboss, active=getattr(item, "active", True), depress=getattr(item, "depress", False))


def _hovered(text, icon, default, hover):
    """While the mouse is on an item it shows both of its parts, so each can be clicked: the icon (a spot to
    add one if it has none) and the text (the action's name, dimmed, if it shows only its icon)."""
    dim = False
    if hover:
        if not icon:
            icon = ADD_ICON
        if not text:
            text, dim = default, True
    return text, icon, dim


NUMPAD = {"W": "4", "E": "6", "S": "2", "N": "8", "NW": "7", "NE": "9", "SW": "1", "SE": "3"}
DIR_VEC = {"E": (1, 0), "NE": (math.sqrt(0.5), math.sqrt(0.5)), "N": (0, 1), "NW": (-math.sqrt(0.5), math.sqrt(0.5)),
           "W": (-1, 0), "SW": (-math.sqrt(0.5), -math.sqrt(0.5)), "S": (0, -1), "SE": (math.sqrt(0.5), -math.sqrt(0.5))}


def _item_texts(item):
    """(text, icon name or '') the way the real menu button shows them."""
    PM = _pm()
    if item.kind == PM.SUB:
        target = PM.find_pie(item.idname)
        default = item.label or (target.name if target else item.idname)
        icon = PM.item_icon(item, PM.TYPE_ICON.get(target.menu_type, 'NONE') if target else 'NONE')
    elif item.kind == PM.SCRIPT:
        default, icon = item.label or "Python", PM.item_icon(item, 'SCRIPT')
    elif item.kind == PM.MACRO:
        default, icon = item.label or "Macro", PM.item_icon(item)
    elif item.kind == PM.P:
        default = item.label or item.idname.strip().split(".")[-1].replace("_", " ").title()
        icon = PM.item_icon(item)
    else:
        default, icon = item.label or PM.action_name(item), PM.item_icon(item)
    text = PM.item_text(item, default)
    return text, ("" if icon in ('NONE', '', None) else icon), default


def _accel_kinds():
    PM = _pm()
    return (PM.O, PM.M, PM.SUB, PM.SCRIPT, PM.MACRO)  # operator buttons; settings and popovers get no key


def accelerators(texts):
    """Blender's menu keys (ui_menu_block_set_keyaccels): first letters of words first, then any letter."""
    used, keys = set(), [""] * len(texts)
    for pass_ in (0, 1):
        for n, t in enumerate(texts):
            if keys[n] or not t:
                continue
            i = 0
            while i < len(t):
                ch = t[i].lower()
                if "a" <= ch <= "z" and ch not in used:
                    used.add(ch)
                    keys[n] = ch
                    break
                if pass_ == 0:
                    while i < len(t) and t[i].isalpha():
                        i += 1
                    i += 1
                else:
                    i += 1
    return keys


def _styled(item):
    return not (item.height == 1.0 and item.width == 1.0 and item.emboss and not item.alert)


def build_blender_pie(pie, hover=None):
    """Blender's pie layout (ui_litem_layout_radial), centred on (0, 0)."""
    PM = _pm()
    sc = Scene("BLENDER_PIE")
    view = bpy.context.preferences.view
    s, u = ui_scale(), unit()
    R = int((pie.radius or view.pie_menu_radius) * s)
    thr = (pie.threshold or view.pie_menu_threshold) * s
    sc.radius, sc.threshold = R, thr
    _font()
    items = list(pie.items)[:8]
    texts = [_item_texts(it) if not PM._is_empty(it) else ("", "", "") for it in items]
    keys = accelerators([t if (not PM._is_empty(it) and it.kind in _accel_kinds()) else ""
                         for it, (t, _i, _d) in zip(items, texts)])
    aligned = diagonal = False
    for i, item in enumerate(items):
        d = PM.ORDER[i]
        vx, vy = DIR_VEC[d]
        fx = 0.0 if vx > 0.01 else (-1.0 if vx < -0.01 else -0.5)
        fy = 0.0 if vy > 0.99 else (-1.0 if vy < -0.99 else -0.5)
        empty = PM._is_empty(item)
        text, icon, default = texts[i]
        styled = not empty and _styled(item)
        dim = False
        if empty:
            text, icon = "Empty", ""
        else:
            text, icon, dim = _hovered(text, icon, default, i == hover)
        tw = _text_w(text)
        if icon and not text:
            w = u
        elif text:
            w = tw + math.ceil(u * (1.5 + (0.25 if icon else 0.0)))
        else:
            w = u
        if styled:  # a sub-layout: a plain button, not a pie item
            h = u * item.height
            w = w * item.width
        else:
            w += 1.5 * u
            h = 1.5 * u
        w, h = int(w), int(h)
        x = int(vx * R + fx * w)
        y = int(vy * R + fy * h)
        if not empty:
            aligned |= d in ("N", "S", "E", "W")
            diagonal |= d not in ("N", "S", "E", "W")
        sc.els.append(El(i, x, y, w, h, kind="empty" if empty else "item", text=text, icon=icon,
                         num=NUMPAD[d], key="" if dim else keys[i], sub=item.kind == PM.SUB,
                         style=("BUTTON" if styled else "PIE") + ("_ALERT" if not empty and item.alert else ""),
                         icon_rect=None, dim=dim, **({} if empty else _look(item))))
    sc.dirmask = (aligned, diagonal)
    sc.title = pie.name
    tw = _text_w(pie.name)
    sc.title_rect = (-tw / 2, int(thr + 9 * s), tw, u)
    xs = [e.x for e in sc.els] + [e.x + e.w for e in sc.els] + [-tw / 2, tw / 2]
    ys = [e.y for e in sc.els] + [e.y + e.h for e in sc.els] + [thr + 9 * s + u]
    ext_x = max(abs(v) for v in xs)
    ext_y = max(abs(v) for v in ys)
    sc.w, sc.h = 2 * ext_x, 2 * ext_y
    return sc


def build_marking(pie):
    MM = _mm()
    PM = _pm()
    sc = Scene("MARKING")
    look = MM._look()
    s = ui_scale()
    k = s * ((pie.radius / max(look.marking_top, 1)) if pie.radius else 1.0)
    slots = [(PM.ORDER[i], i) for i in range(min(8, len(pie.items)))]
    boxes = MM.marking_boxes(pie, slots, 0.0, 0.0, look, s, k, None, show_empty=True)
    bh = MM.marking_box_height(look, s)
    sc.marking = boxes
    for bx, by, bw, _w, _arrow, label, sub, _sel, index in boxes:
        empty = PM._is_empty(pie.items[index])
        sc.els.append(El(index, bx, by, bw, bh, kind="empty" if empty else "item", text=label, sub=sub, style="MARK"))
    xs = [abs(v) for b in boxes for v in (b[0], b[0] + b[2])] or [50]
    ys = [abs(v) for b in boxes for v in (b[1], b[1] + bh)] or [50]
    sc.w, sc.h = 2 * max(xs), 2 * max(ys)
    return sc


def _menu_item_w(text, icon, u):
    return _text_w(text) + (u if icon else 0) + u * (0.2 + 0.4 + 0.6)


def build_menu(pie, hover=None):
    """A popup menu (Blender's menu look), a popup panel, a dialog or a sidebar panel."""
    PM = _pm()
    s, u = ui_scale(), unit()
    items = list(pie.items)
    as_menu = pie.menu_type == "MENU" and not PM.needs_panel_popup(items)
    sc = Scene("MENU" if as_menu else "PANEL")
    _font()
    pad = int(0.25 * u) if as_menu else int(0.5 * u)
    space_y = int(2 * s) if not as_menu else 0
    any_icon = any(_item_texts(it)[1] for it in items if not PM._is_empty(it) and it.kind not in PM.LAYOUT_KINDS)
    texts = []
    for it in items:
        if it.kind in PM.LAYOUT_KINDS:
            texts.append(("", "", ""))
        elif PM._is_empty(it):
            texts.append(("", "", ""))
        else:
            texts.append(_item_texts(it))
    keys = accelerators([t if as_menu and not PM._is_empty(it) and it.kind in _accel_kinds() else ""
                         for it, (t, _i, _d) in zip(items, texts)])

    # columns of rows; a row is a list of item indices (Same Row joins the one before)
    columns = [[]]
    box_open = None
    for i, it in enumerate(items):
        if it.kind == PM.BREAK:
            columns[-1].append(("MARK", i, "Next Column"))
            columns.append([])
            box_open = None
            continue
        if it.kind == PM.BOX:
            box_open = i
            columns[-1].append(("BOX", i))
            continue
        if it.kind == PM.BOX_END:
            columns[-1].append(("MARK", i, "End Box"))
            box_open = None
            continue
        row = columns[-1][-1] if columns[-1] else None
        if it.same_row and row is not None and row[0] == "ROW":
            row[1].append(i)
        else:
            columns[-1].append(("ROW", [i], box_open))

    if as_menu:
        colw = max([9 * u] + [_menu_item_w(texts[i][0] or "Separator", any_icon, u)
                              for col in columns for r in col if r[0] == "ROW" for i in r[1]])
    elif pie.menu_type == "PANEL":
        colw = 12 * u
    elif pie.menu_type == "DIALOG":
        colw = 180 * s if not PM._has_layout(items) else 180 * s
    else:
        colw = 200 * s
    colw = int(colw)
    if not as_menu and pie.menu_type in ("DIALOG", "PANEL") and not PM._has_layout(items):
        # no layout items: they fill the Columns row by row, like grid_flow
        ncol = max(1, pie.columns)
        columns = [[] for _ in range(ncol)]
        for n, i in enumerate(range(len(items))):
            columns[n % ncol].append(("ROW", [i], None))
    ncols = len(columns)
    gap = 0 if as_menu else int(u * 0.4)

    title_h = 0
    if pie.menu_type != "PANEL":
        title_h = u + (int(0.3 * u) if as_menu else int(0.2 * u))
        sc.title = pie.name
    else:
        sc.panel_header = True
    header_h = int(u * 1.2) if pie.menu_type == "PANEL" else 0

    if not as_menu:
        return _finish_panel(sc, pie, items, texts, keys, hover, s, u, pad, colw, gap, title_h, header_h)

    heights = []
    for c, col in enumerate(columns):
        x0 = pad + c * (colw + gap)
        y = -(pad + title_h + header_h)
        box_start = None
        for entry in col:
            if entry[0] == "MARK":
                if entry[2] == "End Box":
                    y -= int(u * 0.35)  # below the box's frame
                h = int(u * 0.6)
                tw = _text_w(entry[2])
                sc.els.append(El(entry[1], x0 + (colw - tw) / 2 - 4 * s, y - h, tw + 8 * s, h, kind="marker",
                                 text=entry[2], col=c))
                y -= h + space_y
                if entry[2] == "End Box" and box_start is not None:
                    box_start = None
                continue
            if entry[0] == "BOX":
                i = entry[1]
                h = u
                text, icon = (texts[i][0], texts[i][1]) if items[i].label.strip() else ("Box", "")
                y -= int(u * 0.25)
                sc.els.append(El(i, x0, y - h - int(u * 0.25), colw, h + int(u * 0.25), kind="boxhead",
                                 text=items[i].label.strip() or "Box", icon=texts[i][1], col=c))
                y -= h + int(u * 0.25) + space_y
                continue
            idxs = entry[1]
            inbox = entry[2] is not None
            inset = int(u * 0.3) if inbox else 0
            rh = int(max(u * (items[i].height if not as_menu else 1.0) for i in idxs))
            row_items = []
            for i in idxs:
                it = items[i]
                empty = PM._is_empty(it)
                if as_menu and (empty or it.kind == PM.N):
                    row_items.append((i, "sep"))
                else:
                    row_items.append((i, "empty" if empty else ("label" if it.kind == PM.LABEL else "item")))
            if as_menu and len(row_items) == 1 and row_items[0][1] == "sep":
                sp = items[idxs[0]]
                h = max(int(4 * s), int(u * 0.5 * sp.sep_factor))
                sc.els.append(El(idxs[0], x0, y - h, colw, h, kind="sep", text="Separator", col=c,
                                 style="SEP_SPACE" if sp.sep_type == "SPACE" else "SEP_LINE"))
                y -= h
                continue
            total_w = sum(items[i].width for i in idxs) or 1
            xx = x0 + inset
            avail = colw - 2 * inset
            for i, kind in row_items:
                it = items[i]
                w = avail * it.width / total_w
                text, icon, default = texts[i]
                dim = False
                if kind == "empty":
                    text = "Empty"
                elif kind == "item":
                    text, icon, dim = _hovered(text, icon, default, i == hover)
                style = "MENU" if as_menu else _panel_style(it)
                el = El(i, int(xx), y - rh, int(w), rh, kind=kind, text=text, icon=icon, key="" if dim else keys[i],
                        sub=it.kind == PM.SUB, style=style + ("_ALERT" if it.alert else ""), col=c, dim=dim,
                        **_look(it))
                if icon and kind == "item":
                    el.icon_rect = (int(xx), y - rh, u + int(0.3 * u), rh)
                sc.els.append(el)
                xx += w
            y -= rh + space_y
        heights.append(-y)
    content_h = max(heights + [title_h + header_h + pad + u]) + pad
    w = pad * 2 + ncols * colw + (ncols - 1) * gap
    sc.frame = (0, -content_h, w, content_h)
    if sc.title:
        sc.title_rect = (pad, -(pad + u), w - 2 * pad, u)
    if sc.panel_header:
        sc.panel_header = (0, -header_h, w, header_h)
    # boxes: a frame from the box heading down to its last item
    sc.w, sc.h = w, content_h
    # centre on (0, 0) like the pies
    sc.offset(-w / 2, content_h / 2)
    return sc


class _Panel:
    """Lays out popup panels, dialogs and sidebar panels the way Blender's layouts do: columns, rows, boxes,
    splits and grid flows, nested, with align, alignment and scale."""

    def __init__(self, sc, items, texts, keys, hover, s, u, menu_look=False):
        self.sc, self.items, self.texts, self.keys, self.hover = sc, items, texts, keys, hover
        self.menu_look = menu_look  # a popup menu: its buttons are drawn as menu items (the real one does too)
        self.s, self.u = s, u
        self.gap_y = int(2 * s)
        self.gap_x = int(4 * s)
        self.box_pad = int(6 * s)
        self.late = []  # group tags and markers: added last, so they're on top for clicks

    # ---- sizes
    def nat_w(self, node):
        PM, u = _pm(), self.u
        if node[0] == "ITEM":
            it = self.items[node[1]]
            text, icon, _d = self.texts[node[1]]
            if PM._is_empty(it):
                text = "Empty"
            base = _text_w(text) + (u if icon else 0) + u
            if _panel_style(it) in ("CHECK",):
                base += u * 0.8
            return base * it.width
        if node[0] == "RUN":
            return sum(self.nat_w(["ITEM", i]) for i in node[1])
        head = self.items[node[1]]
        kids = [self.nat_w(c) for c in node[2]] or [u]
        t = head.group_type
        if t in ("ROW", "SPLIT", "GRID"):
            w = sum(kids) + (0 if head.align else self.gap_x * (len(kids) - 1))
        else:
            w = max(kids)
        if t == "BOX":
            w += 2 * self.box_pad
        return w * head.width

    def weight(self, node):
        """How much of an expanding row an item takes: Blender gives each the same share, times its Scale X."""
        if node[0] == "ITEM":
            return self.items[node[1]].width
        if node[0] == "RUN":
            return sum(self.items[i].width for i in node[1])
        return self.items[node[1]].width

    def _join(self, start, sides):
        """Mark the buttons made since `start` as joined on these sides (aligned rows and columns)."""
        for el in self.sc.els[start:]:
            if el.kind in ("item", "empty", "label"):
                el.join |= sides

    # ---- placing (y is the top edge; coordinates go down into negative y)
    def item(self, i, x, y, w, sy):
        PM, u = _pm(), self.u
        it = self.items[i]
        empty = PM._is_empty(it)
        if empty and it.kind == PM.N:  # a separator (the real layout draws layout.separator() here)
            h = max(int(4 * self.s), int(u * 0.5 * it.sep_factor))
            line = it.sep_type == "LINE" or (it.sep_type == "AUTO" and self.menu_look)
            self.sc.els.append(El(i, int(x), int(y - h), int(w), h, kind="sep", text="Separator",
                                  style="SEP_LINE" if line else "SEP_SPACE"))
            return h
        h = int(round(u * it.height * sy))
        kind = "empty" if empty else ("label" if it.kind == PM.LABEL else "item")
        text, icon, default = self.texts[i]
        dim = False
        if kind == "empty":
            text = "Empty"
        elif kind == "item":
            text, icon, dim = _hovered(text, icon, default, i == self.hover)
        style = "MENU" if self.menu_look and it.kind != PM.LABEL else _panel_style(it)
        el = El(i, int(x), int(y - h), int(w), h, kind=kind, text=text, icon=icon, key="" if dim else self.keys[i],
                sub=it.kind == PM.SUB, style=style + ("_ALERT" if it.alert else ""), dim=dim, **_look(it))
        if icon and kind == "item":
            el.icon_rect = (int(x), int(y - h), u + int(0.3 * u), h)
        self.sc.els.append(el)
        return h

    def node(self, node, x, y, w, sy):
        if node[0] == "ITEM":
            return self.item(node[1], x, y, w, sy)
        if node[0] == "RUN":
            return self.row([["ITEM", i] for i in node[1]], x, y, w, sy, True, "EXPAND")
        return self.group(node, x, y, w, sy)

    def column(self, kids, x, y, w, sy, align, alignment):
        yy = y
        for n, c in enumerate(kids):
            cw = w if alignment == "EXPAND" else min(w, self.nat_w(c))
            cx = x if alignment in ("EXPAND", "LEFT") else (x + (w - cw) / 2 if alignment == "CENTER" else x + w - cw)
            start = len(self.sc.els)
            h = self.node(c, cx, yy, cw, sy)
            if align and len(kids) > 1:
                self._join(start, ({"B"} if n == 0 else {"T"} if n == len(kids) - 1 else {"T", "B"}))
            yy -= h + (0 if align or n == len(kids) - 1 else self.gap_y)
        return y - yy

    def row(self, kids, x, y, w, sy, align, alignment, widths=None):
        if not kids:
            return 0
        gap = 0 if align else self.gap_x
        if widths is None:
            avail = w - gap * (len(kids) - 1)
            nats = [max(1.0, self.nat_w(c)) for c in kids]
            if alignment == "EXPAND":
                weights = [max(0.05, self.weight(c)) for c in kids]
                widths = [avail * k / sum(weights) for k in weights]
            elif sum(nats) > avail:
                widths = [avail * n / sum(nats) for n in nats]
            else:
                widths = nats
        total = sum(widths) + gap * (len(kids) - 1)
        xx = x if alignment in ("EXPAND", "LEFT") else (x + (w - total) / 2 if alignment == "CENTER" else x + w - total)
        h = 0
        for n, (c, cw) in enumerate(zip(kids, widths)):
            start = len(self.sc.els)
            h = max(h, self.node(c, xx, y, cw, sy))
            if align and len(kids) > 1:
                self._join(start, ({"R"} if n == 0 else {"L"} if n == len(kids) - 1 else {"L", "R"}))
            xx += cw + gap
        return h

    def group(self, node, x, y, w, sy):
        PM, u, s = _pm(), self.u, self.s
        i, kids, end = node[1], node[2], node[3]
        head = self.items[i]
        t = head.group_type
        sy2 = sy * head.height
        pos = len(self.sc.els)  # the group's own (click) area goes under its items
        top = y
        label = head.label.strip()
        if t == "PANEL":  # a sub-panel: its header, then (when open) its items
            hh = int(u * 1.1)
            self.sc.els.append(El(i, int(x), int(y - hh), int(w), hh, kind="boxhead", text=label or "Panel",
                                  style="PANEL_CLOSED" if head.closed else "PANEL"))
            self.sc.panels.append((int(x), int(y - hh), int(w), hh, head.closed))
            y -= hh
            label = ""
            if head.closed:
                kids = []
        if t == "BOX":
            y -= self.box_pad
            x, w = x + self.box_pad, w - 2 * self.box_pad
        if label:
            lh = int(u * sy2)
            self.sc.els.append(El(i, int(x), int(y - lh), int(w), lh, kind="boxhead", text=label,
                                  icon=PM.item_icon(head) if PM.item_icon(head) != 'NONE' else ""))
            y -= lh + (0 if head.align else self.gap_y)
        if t == "PANEL" and head.closed:
            inner = 0
        elif not kids:  # an empty group: a dashed spot to drop items into
            h = int(u * sy2)
            inner = h
        elif t in ("BOX", "COLUMN", "PANEL"):
            inner = self.column(kids, x, y, w, sy2, head.align, head.alignment)
        elif t == "ROW":
            inner = self.row(kids, x, y, w, sy2, head.align, head.alignment)
        elif t == "SPLIT":
            n = len(kids)
            gap = 0 if head.align else self.gap_x
            avail = w - gap * (n - 1)
            if head.factor > 0 and n > 1:
                widths = [avail * head.factor] + [avail * (1 - head.factor) / (n - 1)] * (n - 1)
            else:
                widths = [avail / n] * n
            inner = self.row(kids, x, y, w, sy2, head.align, "EXPAND", widths)
        else:  # GRID
            cols = head.grid_columns or max(1, int(w // (5.5 * u)))
            cols = max(1, min(cols, len(kids)))
            gap = 0 if head.align else self.gap_x
            cw = (w - gap * (cols - 1)) / cols
            yy, inner = y, 0
            for r in range(0, len(kids), cols):
                h = self.row(kids[r:r + cols], x, yy, cw * len(kids[r:r + cols]) + gap * (len(kids[r:r + cols]) - 1),
                             sy2, head.align, "EXPAND", [cw] * len(kids[r:r + cols]))
                yy -= h + (0 if head.align else self.gap_y)
            inner = y - yy - (0 if head.align else self.gap_y)
        y -= inner
        if t == "BOX":
            y -= self.box_pad
            x, w = x - self.box_pad, w + 2 * self.box_pad
        h = top - y
        gx, gy = int(x), int(top - h)
        if t == "BOX":
            self.sc.boxes.append((gx, gy, int(w), int(h)))
        self.sc.groups.append((i, gx, gy, int(w), int(h), t))
        self.sc.els.insert(pos, El(i, gx, gy, int(w), int(h), kind="group", text=GROUP_LABEL.get(t, t)))
        # a small tag on the group's top left corner (while the mouse is on the menu): click or drag it
        name = GROUP_LABEL.get(t, t) + (f" · {label}" if label else "")
        _font(FONT_POINTS * 0.8)
        tw = _text_w(name) + 10 * s
        _font()
        th = int(0.62 * u)
        self.late.append(El(i, gx - int(2 * s), int(top - th / 2), int(tw), th, kind="grouptag", text=name))
        if end is not None:  # its End Group: a marker on the bottom edge
            _font(FONT_POINTS * 0.8)
            ew = _text_w("End Group") + 10 * s
            _font()
            self.late.append(El(end, int(gx + w / 2 - ew / 2), int(gy - th / 2), int(ew), th, kind="marker",
                                text="End Group", col=i))
        return h


GROUP_LABEL = {"BOX": "Box", "ROW": "Row", "COLUMN": "Column", "SPLIT": "Split", "GRID": "Grid", "PANEL": "Panel"}


def _finish_panel(sc, pie, items, texts, keys, hover, s, u, pad, colw, gap, title_h, header_h):
    PM = _pm()
    # a popup menu with rows, boxes or sizes opens as a popup panel: regular (grey) buttons, as drawn here
    lay = _Panel(sc, items, texts, keys, hover, s, u)
    shown = list(enumerate(items))
    if pie.menu_type in ("DIALOG", "PANEL") and not PM._has_layout(items):
        # no layout items: they fill the Columns row by row, like grid_flow
        ncol = max(1, pie.columns)
        columns = [[["ITEM", i] for i in range(len(items))]]
        grid = True
    else:
        columns = PM.layout_tree(items, shown)
        ncol, grid = len(columns), False
    breaks = [i for i, it in shown if it.kind == PM.BREAK]
    width = colw * (ncol if not grid else max(1, pie.columns)) + gap * ((ncol if not grid else 1) - 1)
    heights = []
    y0 = -(pad + title_h + header_h)
    if grid:
        nodes = columns[0]
        cw = (width - lay.gap_x * (ncol - 1)) / ncol
        yy = y0
        for r in range(0, len(nodes), ncol):
            chunk = nodes[r:r + ncol]
            h = lay.row(chunk, pad, yy, cw * len(chunk) + lay.gap_x * (len(chunk) - 1), 1.0, False, "EXPAND",
                        [cw] * len(chunk))
            yy -= h + lay.gap_y
        heights.append(-yy)
    else:
        for c, nodes in enumerate(columns):
            x0 = pad + c * (colw + gap)
            h = lay.column(nodes, x0, y0, colw, 1.0, False, "EXPAND") if nodes else u
            heights.append(-y0 + h)
            if c > 0 and c - 1 < len(breaks):  # Next Column: a marker on the column's top edge
                _font(FONT_POINTS * 0.8)
                bw = _text_w("Next Column") + 10 * s
                _font()
                th = int(0.62 * u)
                lay.late.append(El(breaks[c - 1], int(x0 + colw / 2 - bw / 2), int(y0 + th / 2), int(bw), th,
                                   kind="marker", text="Next Column"))
    sc.els.extend(lay.late)
    content_h = max(heights + [title_h + header_h + pad + u]) + pad
    w = pad * 2 + width
    sc.frame = (0, -content_h, w, content_h)
    if sc.title:
        sc.title_rect = (pad, -(pad + u), w - 2 * pad, u)
    if sc.panel_header:
        sc.panel_header = (0, -header_h, w, header_h)
    sc.w, sc.h = w, content_h
    sc.offset(-w / 2, content_h / 2)
    return sc


def _panel_style(item):
    PM = _pm()
    if item.kind == PM.LABEL:
        return "LABEL"
    if item.kind == PM.P:
        st = getattr(item, "setting_style", "AUTO")
        return {"SLIDER": "SLIDER", "BUTTON": "BUTTON", "EXPAND": "BUTTON"}.get(st, "CHECK")
    if not item.emboss:
        return "FLAT"
    return "BUTTON"


def build(pie, prefs, hover=None):
    if pie.menu_type == "PIE":
        return build_marking(pie) if getattr(prefs, "pie_style", "BLENDER") == "MARKING" else build_blender_pie(pie, hover)
    return build_menu(pie, hover)


def supported(pie):
    return pie.menu_type in ("PIE", "MENU", "DIALOG", "PANEL")


def icons_needed(pie):
    PM = _pm()
    names = []
    for it in pie.items:
        if PM._is_empty(it) or it.kind in PM.LAYOUT_KINDS and it.kind != PM.BOX:
            continue
        _t, icon, _d = _item_texts(it)
        if it.kind == PM.BOX:
            icon = PM.item_icon(it)
            icon = "" if icon == 'NONE' else icon
        if icon and icon not in names:
            names.append(icon)
    return names


# ---------------------------------------------------------------- drawing a scene

def _arc_dir(sc, mouse):
    if mouse is None:
        return None
    dx, dy = mouse[0] - sc.cx, mouse[1] - sc.cy
    if math.hypot(dx, dy) < sc.threshold:
        return None
    return math.atan2(dy, dx)


def draw_scene(sc, st, prefs):
    th = _theme()
    s, u = ui_scale(), unit()
    hover = st.hover
    drag = st.drag if st.drag and st.drag.get("active") else None
    src = drag["src"] if drag else None
    selected = prefs.pie_slot
    accent = _rgba(th.wcol_menu_item.inner_sel)
    _font()
    if sc.kind == "BLENDER_PIE":
        _draw_blender_pie(sc, st, th, s, u, hover, src, selected, accent)
    elif sc.kind == "MARKING":
        _draw_marking(sc, st, hover, src, selected, accent, s)
    else:
        _draw_menu(sc, st, th, s, u, hover, src, selected, accent)
    flush_icons()
    if drag:
        _draw_drop(sc, st, accent, s, u)
        _draw_ghost(sc, st, th, s, u)
        flush_icons()


def _pie_item(el, wcol, u, s, hovered, alpha=1.0, dashed=False):
    r = wcol.roundness * u
    if el.kind == "empty":
        pts = _outline_pts(el.x + 0.5, el.y + 0.5, el.w - 1, el.h - 1, r)
        _round_fill(el.x, el.y, el.w, el.h, r, _rgba(wcol.inner, 0.25 * alpha))
        _line(pts, _rgba(wcol.text, (0.35 if not hovered else 0.7) * alpha), 1.0, closed=True)
        tcol = _rgba(wcol.text, (0.35 if not hovered else 0.8) * alpha)
        _text_in(el.x, el.y, el.w, el.h, "Empty", tcol, align="CENTER")
        return
    alert = el.style.endswith("_ALERT")
    if el.style.startswith("BUTTON"):  # a sub-layout in the pie: drawn as a plain button
        tool = _theme().wcol_tool
        sel = hovered or el.depress
        tcol = _rgba(tool.text_sel if sel else tool.text, alpha)
        if el.emboss:
            inner = _rgba(tool.inner_sel if sel else tool.inner, alpha)
            if alert:
                inner = (0.47, 0.07, 0.07, alpha)
            widget_box(el.x, el.y, el.w, el.h, tool.roundness * u * 0.5, inner, _rgba(tool.outline, alpha), wcol=tool,
                       emboss=True)
        else:  # Emboss off: flat, only the icon and text
            if hovered:
                _round_fill(el.x, el.y, el.w, el.h, tool.roundness * u * 0.5, _rgba(tool.inner, 0.5 * alpha))
            if alert:
                tcol = (1.0, 0.35, 0.3, alpha)
        _button_content(el, _tcol(el, tcol), u, s, align="CENTER" if not el.icon else "LEFT")
        return
    inner = _rgba(wcol.inner_sel if el.depress else (wcol.item if hovered else wcol.inner), alpha)
    if alert:
        inner = (0.47, 0.07, 0.07, inner[3])
    widget_box(el.x, el.y, el.w, el.h, r, inner, _rgba(wcol.outline, alpha), wcol=wcol)
    tcol = _tcol(el, _rgba(wcol.text_sel if (hovered or el.depress) else wcol.text, alpha))
    rx = el.x
    if el.icon and not el.text:  # icon only: centred, like Blender's icon-only pie buttons
        draw_icon(el.icon, el.x + el.w / 2, el.y + el.h / 2, tcol)
    elif el.icon:
        ix = rx + 0.3 * u
        draw_icon(el.icon, ix + 4 * s + 8 * s, el.y + el.h / 2, tcol)
        tx0 = ix + round(16 * s + 2 * s) + round(0.4 * u)
        tx, ty = _text_in(tx0, el.y, el.x + el.w - tx0, el.h, el.text, tcol, "LEFT")
        if el.key:
            _underline(tx, ty, el.text, el.key, tcol)
    else:
        tx0 = rx + round(0.4 * u)
        tx, ty = _text_in(tx0, el.y, el.w - 2 * round(0.4 * u), el.h, el.text, tcol, "CENTER")
        if el.key:
            _underline(tx, ty, el.text, el.key, tcol)
    if el.num:
        clip = 0.25 * u
        ncol = tcol[:3] + (tcol[3] * 0.5,)
        _text_in(el.x, el.y, el.w - clip, el.h, el.num, ncol, "RIGHT")


def _button_content(el, tcol, u, s, align="CENTER"):
    if el.icon and el.text:
        draw_icon(el.icon, el.x + 0.2 * u + 8 * s + 2 * s, el.y + el.h / 2, tcol)
        tx0 = el.x + 0.2 * u + 16 * s + 2 * s + 0.4 * u
        if align == "CENTER":  # Blender centres a button's text on the button, the icon stays on the left
            tw = _text_w(el.text)
            tx0 = max(tx0, el.x + (el.w - tw) / 2)
        tx, ty = _text_in(tx0, el.y, el.x + el.w - tx0, el.h, el.text, tcol, "LEFT")
    elif el.icon:
        draw_icon(el.icon, el.x + el.w / 2, el.y + el.h / 2, tcol)
        return
    else:
        tx, ty = _text_in(el.x + 0.4 * u, el.y, el.w - 0.8 * u, el.h, el.text, tcol, align)
    if el.key:
        _underline(tx, ty, el.text, el.key, tcol)


def _selection(el, accent, s, u, r=None):
    px = 2 * s
    rr = (r if r is not None else 0.25 * u) + px
    _line(_outline_pts(el.x - px, el.y - px, el.w + 2 * px, el.h + 2 * px, rr), accent, 2.0 * s, closed=True)


def _draw_blender_pie(sc, st, th, s, u, hover, src, selected, accent):
    wcol = th.wcol_pie_menu
    for el in sc.els:
        alpha = 0.35 if el.index == src else 1.0
        _pie_item(el, wcol, u, s, el.index == hover and src is None, alpha)
        if selected is not None and el.index == selected:
            _selection(el, accent, s, u, wcol.roundness * u)
    # title: a label above the centre
    if sc.title_rect:
        x, y, w, h = sc.title_rect
        blf.enable(0, blf.SHADOW)  # the pie title is a label drawn with a soft shadow
        blf.shadow(0, 3, 0.0, 0.0, 0.0, 0.5)
        blf.shadow_offset(0, 1, -1)
        _text_in(x, y, w, h, sc.title, _rgba(th.wcol_menu_back.text), "CENTER")
        blf.disable(0, blf.SHADOW)
    # centre ring (ui_draw_pie_center)
    r0, r1 = sc.threshold, sc.threshold + 7 * s
    _disk(sc.cx, sc.cy, r0, r1, 0.0, 2 * math.pi, _rgba(wcol.inner))
    hover_el = next((e for e in sc.els if e.index == hover), None) if hover is not None else None
    angle = None
    if st.mouse is not None and (hover_el is not None or st.drag):
        angle = _arc_dir(sc, st.mouse)
    if angle is not None:
        rng = math.pi / 4 if all(sc.dirmask) else math.pi / 2
        _disk(sc.cx, sc.cy, r0, r1, angle - rng / 2, rng, _rgba(wcol.inner_sel))
    _circle(sc.cx, sc.cy, r0, _rgba(wcol.outline))
    _circle(sc.cx, sc.cy, r1, _rgba(wcol.outline))


def _draw_marking(sc, st, hover, src, selected, accent, s):
    MM = _mm()
    look = MM._look()
    colours = MM.marking_colours(look)
    MM._smooth = look.marking_antialias
    boxes = [tuple(b[:7]) + (b[8] == hover and src is None, b[8]) for b in sc.marking]
    empties = {el.index for el in sc.els if el.kind == "empty"}
    faded = empties | ({src} if src is not None else set())
    if st.mouse is not None and hover is not None and look.marking_line_width > 0 and src is None:
        MM._poly([(sc.cx, sc.cy), st.mouse], colours[5], look.marking_line_width * s)
    MM.draw_marking_centre(sc.cx, sc.cy, look, s, colours)
    MM.draw_marking_boxes(boxes, look, s, colours, dim=faded)
    if selected is not None:
        for el in sc.els:
            if el.index == selected:
                _selection(el, accent, s, unit(), MM.marking_corner(look, el.h, s))


def _draw_menu(sc, st, th, s, u, hover, src, selected, accent):
    pie = st.pie
    menu = sc.kind == "MENU"
    back = th.wcol_menu_back
    x, y, w, h = sc.frame
    if pie is not None and pie.menu_type == "PANEL":
        space = bpy.context.preferences.themes[0].view_3d.space
        try:
            pc = space.panelcolors
            header, body = _rgba(pc.header), _rgba(pc.back)
        except AttributeError:
            header, body = (0.18, 0.18, 0.18, 1), (0.16, 0.16, 0.16, 1)
        r = 0.2 * u
        _round_fill(x, y, w, h, r, body)
        hx, hy, hw, hh = sc.panel_header
        _round_fill(hx, hy, hw, hh, r, header)
        _rect(hx, hy, hw, hh / 2, header)
        _tria_down(hx + 0.6 * u, hy + hh / 2, 0.35 * u, _rgba(th.wcol_regular.text, 0.8))
        _text_in(hx + 1.2 * u, hy, hw, hh, pie.name, _rgba(th.wcol_regular.text), "LEFT")
    else:
        r = back.roundness * u * 0.5
        _shadow(x, y, w, h, r, 6 * s)
        widget_box(x, y, w, h, r, _rgba(back.inner), _rgba(back.outline))
        if sc.title_rect:
            tx, ty, tw, tht = sc.title_rect
            _text_in(tx + (0.2 * u if menu else 0), ty, tw, tht, sc.title, _rgba(back.text), "LEFT")
            if menu:
                ly = ty - 0.15 * u
                _rect(x + 0.25 * u, ly, w - 0.5 * u, 1 * pixel(), _rgba(back.text, 0.15))
    # boxes behind their items
    for bx, by, bw, bh in sc.boxes:
        widget_box(bx, by, bw, bh, th.wcol_box.roundness * u * 0.5, _rgba(th.wcol_box.inner), _rgba(th.wcol_box.outline))
    item_col = th.wcol_menu_item
    any_icon = any(el.icon and el.icon != ADD_ICON for el in sc.els if el.kind == "item")
    for el in sc.els:
        hovered = el.index == hover and src is None
        alpha = 0.35 if el.index == src else 1.0
        if el.kind in ("group", "grouptag", "marker"):
            continue  # drawn on top, below
        if el.kind == "sep":
            mid = el.y + el.h / 2
            if hovered:
                _round_fill(el.x + 0.15 * u, el.y + 1, el.w - 0.3 * u, el.h - 2, 0.15 * u, _rgba(item_col.inner_sel, 0.35))
            if hovered:  # an empty item: click to pick an action
                tw = _text_w("Empty")
                _text_in(el.x + (el.w - tw) / 2 - 0.3 * u, el.y, tw + 0.6 * u, el.h, "Empty", _rgba(back.text, 0.6), "CENTER")
                _rect(el.x + 0.25 * u, mid, (el.w - tw) / 2 - 0.6 * u, pixel(), _rgba(back.text, 0.4))
                _rect(el.x + (el.w + tw) / 2 + 0.35 * u, mid, (el.w - tw) / 2 - 0.6 * u, pixel(), _rgba(back.text, 0.4))
            elif el.style != "SEP_SPACE":
                _rect(el.x + 0.25 * u, mid, el.w - 0.5 * u, pixel(), _rgba(back.text, 0.15 * alpha))
        elif el.kind == "boxhead" and el.style.startswith("PANEL"):
            _panel_header(el, th, u, s, hovered, alpha)
        elif el.kind == "boxhead":
            col = _rgba(th.wcol_box.text, alpha)
            if hovered:
                _round_fill(el.x + 2, el.y + 2, el.w - 4, el.h - 4, 0.2 * u, _rgba(th.wcol_box.item, 0.6))
            if el.icon:
                draw_icon(el.icon, el.x + 0.4 * u + 8 * s, el.y + el.h / 2, col, alpha)
                _text_in(el.x + 0.4 * u + 16 * s + 0.4 * u, el.y, el.w, el.h, el.text, col, "LEFT")
            else:
                _text_in(el.x + 0.4 * u, el.y, el.w, el.h, el.text, col, "LEFT")
        elif menu or el.style.startswith("MENU"):
            _menu_item(el, item_col, th, u, s, hovered, alpha, any_icon)
        else:
            _panel_item(el, th, u, s, hovered, alpha)
        if selected is not None and el.index == selected:
            _selection(el, accent, s, u, 0.2 * u)
        if hovered and st.show_remove and el.kind in ("item", "empty", "sep", "label", "boxhead", "marker"):
            _draw_remove(el, th, u, s, st)
    if sc.show_markers or selected is not None:
        _draw_layout_marks(sc, th, s, u, hover, selected, accent)


def _panel_header(el, th, u, s, hovered, alpha):
    """A sub-panel's header (layout.panel): Blender's panel header colour, an open/closed triangle and its label."""
    # like Blender's layout.panel header in popups: a thin line above, a chevron, the label; no band
    _rect(el.x, el.y + el.h - pixel(), el.w, pixel(), _rgba(th.wcol_menu_back.text, 0.12 * alpha))
    if hovered:
        _round_fill(el.x, el.y, el.w, el.h, th.wcol_box.roundness * u * 0.5, (1, 1, 1, 0.04))
    col = _rgba(th.wcol_menu_back.text, alpha)
    cx, cy, c = el.x + 0.5 * u, el.y + el.h / 2, 0.18 * u
    if el.style == "PANEL_CLOSED":  # >
        _line([(cx - c * 0.5, cy + c), (cx + c * 0.5, cy), (cx - c * 0.5, cy - c)], col, 1.2 * s)
    else:  # v
        _line([(cx - c, cy + c * 0.5), (cx, cy - c * 0.5), (cx + c, cy + c * 0.5)], col, 1.2 * s)
    _text_in(el.x + 1.0 * u, el.y, el.w, el.h, el.text, col, "LEFT")


def _draw_layout_marks(sc, th, s, u, hover, selected, accent):
    """While the mouse is on the menu: each group's outline and tag, and the End Group / Next Column markers,
    so the layout items can be seen, clicked, dragged and right-clicked. (The real menu doesn't draw them.)"""
    text = th.wcol_menu_back.text
    for i, x, y, w, h, _t in sc.groups:
        on = i == hover or i == selected
        if not (sc.show_markers or on):
            continue
        col = accent[:3] + (0.9,) if on else _rgba(text, 0.22)
        pts = _outline_pts(x - 1.5 * s, y - 1.5 * s, w + 3 * s, h + 3 * s, 3 * s)
        for k in range(0, len(pts) - 1, 2):  # dashed
            _line(pts[k:k + 2], col, 1.0)
    if not sc.show_markers:
        return
    _font(FONT_POINTS * 0.8)
    for el in sc.els:
        if el.kind not in ("grouptag", "marker") or not el.show:
            continue
        on = el.index == hover or el.index == selected
        fill = accent[:3] + (0.95,) if on else (0.12, 0.12, 0.13, 0.92)
        _round_fill(el.x, el.y, el.w, el.h, el.h / 2, fill)
        _line(_outline_pts(el.x + 0.5, el.y + 0.5, el.w - 1, el.h - 1, el.h / 2 - 0.5), _rgba(text, 0.35), 1.0, closed=True)
        _text_in(el.x, el.y, el.w, el.h, el.text, (1, 1, 1, 0.95) if on else _rgba(text, 0.85), "CENTER")
    _font()


def _tria_down(x, y, size, color):
    _fill([(x - size * 0.5, y + size * 0.3), (x + size * 0.5, y + size * 0.3), (x, y - size * 0.4)], [(0, 1, 2)], color)


def _menu_item(el, wcol, th, u, s, hovered, alpha, any_icon):
    if el.kind == "label":
        col = _rgba(th.wcol_menu_back.text, 0.6 * alpha)
        _text_in(el.x + 0.2 * u + (u if any_icon else 0) + 0.4 * u - u * 0.4, el.y, el.w, el.h, el.text, col, "LEFT")
        return
    if hovered or el.depress:
        _round_fill(el.x + 0.15 * u, el.y, el.w - 0.3 * u, el.h, wcol.roundness * u * 0.5,
                    _rgba(wcol.inner_sel, alpha * (1.0 if hovered else 0.6)))
    tcol = _rgba(wcol.text_sel if (hovered or el.depress) else wcol.text, alpha)
    if el.style.endswith("_ALERT"):
        tcol = (1.0, 0.35, 0.3, alpha)
    if el.kind == "empty":
        tcol = _rgba(wcol.text, 0.35 * alpha)
    tcol = _tcol(el, tcol)
    x = el.x + 0.2 * u
    if el.style.startswith("MENU") and el.kind == "item" and _pm().P == _kind(el):
        # settings show as checkboxes in menus
        bx, by = x + 2 * s, el.y + (el.h - 14 * s) / 2
        opt = th.wcol_option
        widget_box(bx, by, 14 * s, 14 * s, opt.roundness * 14 * s, _rgba(opt.inner, alpha), _rgba(opt.outline, alpha))
        tx0 = x + u + 0.2 * u
    else:
        if el.icon:
            draw_icon(el.icon, x + 8 * s + 2 * s, el.y + el.h / 2, tcol, 1.0)
        tx0 = x + ((u + 0.2 * u) if any_icon or el.icon else 0.2 * u)
    tx, ty = _text_in(tx0, el.y, el.w, el.h, el.text, tcol, "LEFT")
    if el.key:
        _underline(tx, ty, el.text, el.key, tcol)
    if el.sub:
        _tria_right(el.x + el.w - 0.6 * u, el.y + el.h / 2, 0.35 * u, tcol)


def _kind(el):
    pie = _cur_pie()
    if pie is None or el.index >= len(pie.items):
        return ""
    return pie.items[el.index].kind


def _panel_item(el, th, u, s, hovered, alpha):
    style = el.style.replace("_ALERT", "")
    alert = el.style.endswith("_ALERT")
    if el.kind == "empty":
        r = 0.2 * u
        _line(_outline_pts(el.x + 0.5, el.y + 1.5, el.w - 1, el.h - 3, r), _rgba(th.wcol_regular.text, (0.6 if hovered else 0.3) * alpha), 1.0, closed=True)
        _text_in(el.x, el.y, el.w, el.h, "Empty", _rgba(th.wcol_regular.text, (0.7 if hovered else 0.35) * alpha), "CENTER")
        return
    if el.kind == "label" or style == "LABEL":
        col = _rgba(th.wcol_regular.text, alpha)
        _button_content(el, col, u, s, align="LEFT") if el.icon else _text_in(el.x + 0.2 * u, el.y, el.w, el.h, el.text, col, "LEFT")
        return
    j = el.join
    bx0 = el.x + (0 if "L" in j else 1)
    bw = el.x + el.w - (0 if "R" in j else 1) - bx0
    y = el.y + (0 if "B" in j else 1)
    h = el.y + el.h - (0 if "T" in j else 1) - y
    if style == "CHECK":
        opt = th.wcol_option
        size = 14 * s
        bx, by = el.x + 0.2 * u, el.y + (el.h - size) / 2
        widget_box(bx, by, size, size, opt.roundness * size * 0.5, _rgba(opt.inner_sel if el.depress else opt.inner, alpha),
                   _rgba(opt.outline, alpha), wcol=opt, emboss=True)
        _text_in(bx + size + 0.3 * u, el.y, el.w, el.h, el.text, _tcol(el, _rgba(opt.text, alpha)), "LEFT")
        return
    if style == "SLIDER":
        ns = th.wcol_numslider
        widget_box(bx0, y, bw, h, ns.roundness * u * 0.5, _rgba(ns.inner, alpha), _rgba(ns.outline, alpha), join=j,
                   wcol=ns, emboss=True)
        fill_w = bw * 0.5
        _round_fill(bx0, y, fill_w, h, _corner_radii(ns.roundness * u * 0.5, j | {"R"}), _rgba(ns.item, alpha))
        tcol = _rgba(ns.text_sel if hovered else ns.text, alpha)
        _text_in(el.x + 0.4 * u, el.y, el.w - 0.8 * u, el.h, el.text, tcol, "LEFT")
        return
    tool = th.wcol_tool
    if style == "FLAT":
        if hovered or el.depress:
            _round_fill(bx0, y, bw, h, tool.roundness * u * 0.5, _rgba(tool.inner_sel if el.depress else tool.inner,
                                                                           0.6 * alpha))
        tcol = _rgba(tool.text_sel if hovered else tool.text, alpha)
        if alert:
            tcol = (1.0, 0.35, 0.3, alpha)
    else:
        base = tool.inner_sel if el.depress else (tool.item if hovered else tool.inner)
        inner = _rgba(base, alpha) if not alert else (0.47, 0.07, 0.07, alpha)
        widget_box(bx0, y, bw, h, tool.roundness * u * 0.5, inner, _rgba(tool.outline, alpha), join=j, wcol=tool,
                   emboss=True)
        tcol = _rgba(tool.text_sel if (hovered or el.depress) else tool.text, alpha)
    _button_content(el, _tcol(el, tcol), u, s, align="CENTER")


def _remove_rect(el, u):
    size = 0.8 * u
    return (el.x + el.w - size - 0.1 * u, el.y + (el.h - size) / 2, size, size)


def _draw_remove(el, th, u, s, st):
    x, y, w, h = _remove_rect(el, u)
    over = st.mouse is not None and x <= st.mouse[0] <= x + w and y <= st.mouse[1] <= y + h
    if over:
        _round_fill(x, y, w, h, w / 2, (0.75, 0.2, 0.2, 0.9))
    col = (1, 1, 1, 0.95) if over else _rgba(th.wcol_menu_item.text, 0.6)
    c = w * 0.22
    mx, my = x + w / 2, y + h / 2
    _line([(mx - c, my - c), (mx + c, my + c)], col, 1.5 * s)
    _line([(mx - c, my + c), (mx + c, my - c)], col, 1.5 * s)


def _draw_drop(sc, st, accent, s, u):
    tgt = st.drop
    if tgt is None:
        return
    if sc.kind in ("BLENDER_PIE", "MARKING"):
        el = next((e for e in sc.els if e.index == tgt), None)
        if el is not None:
            _selection(el, accent, s, u, 0.3 * u)
        return
    kind, el, axis = tgt
    if el is None:
        return
    if axis == "x":  # a line on the item's left or right edge
        x = el.x if kind == "before" else el.x + el.w
        _rect(x - 1 * s, el.y, 2 * s, el.h, accent)
        _round_fill(x - 3 * s, el.y + el.h - 3 * s, 6 * s, 6 * s, 3 * s, accent)
        return
    y = el.y + el.h if kind == "before" else el.y
    _rect(el.x, y - 1 * s, el.w, 2 * s, accent)
    _round_fill(el.x - 3 * s, y - 3 * s, 6 * s, 6 * s, 3 * s, accent)


def _draw_ghost(sc, st, th, s, u):
    el = next((e for e in sc.els if e.index == st.drag["src"]), None)
    if el is None or st.mouse is None:
        return
    gx = st.mouse[0] - st.drag["grab"][0]
    gy = st.mouse[1] - st.drag["grab"][1]
    ghost = El(el.index, gx, gy, el.w, el.h, kind=el.kind, text=el.text, icon=el.icon, num=el.num, key=el.key,
               sub=el.sub, style=el.style)
    if el.icon_rect:
        ix, iy, iw, ih = el.icon_rect
        ghost.icon_rect = (ix - el.x + gx, iy - el.y + gy, iw, ih)
    if sc.kind == "BLENDER_PIE":
        _pie_item(ghost, th.wcol_pie_menu, u, s, True, 0.7)
    elif sc.kind == "MARKING":
        MM = _mm()
        look = MM._look()
        b = next(b for b in sc.marking if b[8] == el.index)
        MM.draw_marking_boxes([(gx, gy) + tuple(b[2:7]) + (True, b[8])], look, s, MM.marking_colours(look))
    else:
        r = 0.2 * u
        widget_box(gx, gy, el.w, el.h, r, _rgba(th.wcol_menu_back.inner, 0.6), _rgba(accent_of(th), 0.7))
        _button_content(ghost, _rgba(th.wcol_menu_back.text, 0.7), u, s, align="LEFT")


def accent_of(th):
    return th.wcol_menu_item.inner_sel


def _cur_pie():
    prefs = _prefs()
    pies = getattr(prefs, "pies", None)
    if not pies:
        return None
    return pies[max(0, min(prefs.active_pie, len(pies) - 1))]


# ---------------------------------------------------------------- per region state

class Canvas:
    def __init__(self):
        self.rect = None          # (x0, y0, x1, y1) in region pixels, from the last draw
        self.pad = 0              # how far the marker rows reach beyond the rect
        self.height = None        # pixels from the bottom of the top marker to the top of the bottom marker
        self.x_hint = None
        self.scene = None
        self.pie = None
        self.hover = None
        self.hover_zone = ""
        self.mouse = None         # region pixels
        self.drag = None          # {"src", "start", "grab", "active"}
        self.drop = None
        self.show_remove = False
        self.icons = []           # icon names the layout draws in the row under the top marker
        self.wanted = False       # the layout drew the markers since the last time they couldn't be found
        self.misses = 0
        self.window_ptr = 0
        self.press = None


_canvases = {}       # region pointer -> Canvas
_running = set()     # window pointers with a running canvas modal
_last_exit = {}      # window pointer -> time its modal ended
_handle = None
_stop = False
_debug_no_paint = False  # tests: show the raw layout under the preview


def _canvas(region):
    key = region.as_pointer()
    st = _canvases.get(key)
    if st is None:
        st = _canvases[key] = Canvas()
    return st


# ---------------------------------------------------------------- the layout side

def draw_layout(layout, context, pie, prefs):
    """Reserve the preview area in the preferences layout. The draw callback draws into it."""
    region = context.region
    if region is None:
        return
    st = _canvas(region)
    st.wanted = True
    st.misses = 0
    st.icons = icons_needed(pie)
    u = unit()
    try:
        sc = build(pie, prefs)
        need = int(sc.h + 2.2 * u)
    except Exception:  # noqa: BLE001  never break the preferences over the preview
        need = 12 * u
    wm = context.window_manager
    col = layout.column(align=True)
    top = col.row(align=True)
    top.scale_y = MARK_SCALE
    top.prop(wm, "keyops_canvas_mark_top", text="")
    rows = (len(st.icons) + ICONS_PER_ROW - 1) // ICONS_PER_ROW
    for r in range(rows):
        row = col.row(align=True)
        row.alignment = 'LEFT'
        for name in st.icons[r * ICONS_PER_ROW:(r + 1) * ICONS_PER_ROW]:
            row.label(text="", icon=name)
    rest = max(u, need - rows * u)
    # the area's height when only one marker is on screen (both seen: measured instead)
    st.height = int(rows * u + rest + pixel())
    body = col.row(align=True)
    body.scale_y = rest / u
    body.label(text="")
    bottom = col.row(align=True)
    bottom.scale_y = MARK_SCALE
    bottom.prop(wm, "keyops_canvas_mark_bottom", text="")


# ---------------------------------------------------------------- finding the area on screen

def _is(c, ref):
    return abs(c[0] - ref[0]) < 0.06 and abs(c[1] - ref[1]) < 0.06 and abs(c[2] - ref[2]) < 0.06


def _runs(col, ref):
    """(start, end) of the first run of pixels matching ref in a column/row of RGBA values."""
    start = None
    for i, c in enumerate(col):
        if _is(c, ref):
            if start is None:
                start = i
            end = i
        elif start is not None:
            return start, end
    return (start, end) if start is not None else None


def _read_col(fb, vp, x, h):
    buf = fb.read_color(vp[0] + x, vp[1], 1, h, 4, 0, 'FLOAT')
    return [buf[i][0] for i in range(h)]


def _read_row(fb, vp, y, w):
    buf = fb.read_color(vp[0], vp[1] + y, w, 1, 4, 0, 'FLOAT')
    return [buf[0][i] for i in range(w)]


def _locate(st, region):
    fb = gpu.state.active_framebuffer_get()
    vp = gpu.state.viewport_get()
    w, h = region.width, region.height
    xs = ([st.x_hint] if st.x_hint else []) + [int(w * k / 10) for k in range(1, 10)]
    top = bottom = None
    for x in xs:
        if not 0 <= x < w:
            continue
        col = _read_col(fb, vp, x, h)
        top = _runs(col, MARK_TOP)
        bottom = _runs(col, MARK_BOTTOM)
        if top or bottom:
            break
    if not (top or bottom):
        return None
    y_mid = (top[0] + top[1]) // 2 if top else (bottom[0] + bottom[1]) // 2
    row = _read_row(fb, vp, y_mid, w)
    xr = _runs(row, MARK_TOP if top else MARK_BOTTOM)
    if xr is None:
        return None
    x0, x1 = xr[0] - 1, xr[1] + 1
    st.x_hint = (x0 + x1) // 2
    if top and bottom:
        y1, y0 = top[0] - 1, bottom[1] + 1     # inside the canvas: below the top marker, above the bottom one
        st.height = y1 - y0
    elif top:
        if st.height is None:
            return None
        y1 = top[0] - 1
        y0 = y1 - st.height
    else:
        if st.height is None:
            return None
        y0 = bottom[1] + 1
        y1 = y0 + st.height
    # the marker rows themselves, painted over too
    mt = (top[1] - top[0] + 1) if top else 4
    return (x0, y0, x1, y1), (fb, vp, top, bottom, mt)


def _sample(fb, vp, x, y):
    buf = fb.read_color(vp[0] + int(x), vp[1] + int(y), 1, 1, 4, 0, 'FLOAT')
    return tuple(buf[0][0])


# ---------------------------------------------------------------- the draw callback

def _draw_callback():
    try:
        _draw()
    except ReferenceError:
        pass
    except Exception:  # noqa: BLE001  a broken preview must never spam or break the preferences
        import traceback
        traceback.print_exc()
        st = _canvases.get(bpy.context.region.as_pointer()) if bpy.context.region else None
        if st is not None:
            st.wanted = False


def _draw():
    context = bpy.context
    region = context.region
    if region is None:
        return
    st = _canvases.get(region.as_pointer())
    if st is None or not st.wanted:
        return
    found = _locate(st, region)
    if found is None:
        st.misses += 1
        st.rect = None
        if st.misses > 2:
            st.wanted = False  # not on screen: stop looking until the layout draws the preview again
        return
    st.misses = 0
    (x0, y0, x1, y1), (fb, vp, top, bottom, mt) = found
    if _debug_no_paint:
        return
    u = unit()
    # the background colour, from a corner of the area that's on screen (the right end: icons sit on the left)
    sy = y0 + 4 if y0 + 4 >= 0 else y1 - 4
    bg = _sample(fb, vp, x1 - 4, max(0, min(region.height - 1, sy)))
    # pick up the icons the layout drew under the top marker
    want = [n for n in st.icons if n not in _icons.tex]
    key = (ui_scale(), tuple(round(c, 3) for c in bg[:3]), bpy.context.preferences.themes[0].user_interface.wcol_regular.text[:])
    if _icons.key != key:
        _icons.tex.clear()
        _icons.atlases.clear()
        _icons.key = key
        want = list(st.icons)
    if want and top:
        _capture_icons(fb, vp, list(st.icons), x0, y1, u, bg)
    st.rect = (x0, y0, x1, y1)
    st.window_ptr = context.window.as_pointer() if context.window else 0
    # paint over the markers, the icon row and the area
    gpu.state.blend_set('ALPHA')
    pad = mt + 2
    st.pad = pad + 2
    _rect(x0 - 1, y0 - pad, x1 - x0 + 2, y1 - y0 + 2 * pad, (bg[0], bg[1], bg[2], 1.0))
    prefs = _prefs()
    pie = _cur_pie()
    st.pie = pie
    if pie is None or not supported(pie):
        gpu.state.blend_set('NONE')
        return
    sc = build(pie, prefs, st.hover if not st.drag else None)
    cx, cy = round((x0 + x1) / 2), round((y0 + y1) / 2)
    sc.offset(cx, cy)
    if sc.frame and st.mouse is not None:
        fx, fy, fw, fh = sc.frame
        pad = unit()
        sc.show_markers = fx - pad <= st.mouse[0] <= fx + fw + pad and fy - pad <= st.mouse[1] <= fy + fh + pad
    if st.drag and st.drag.get("active"):
        sc.show_markers = True
    # End Group markers only for the group the mouse is in (or the selected one), so they don't crowd the menu
    sel = prefs.pie_slot
    for el in sc.els:
        if el.kind == "marker" and el.text == "End Group":
            inside = lambda k: k is not None and el.col <= k <= el.index
            el.show = inside(st.hover) or inside(sel) or bool(st.drag and st.drag.get("active"))
    st.scene = sc
    st.show_remove = pie.menu_type != "PIE" and len(pie.items) > _pm().ITEM_MIN.get(pie.menu_type, 0)
    gpu.state.scissor_test_set(True)
    gpu.state.scissor_set(int(vp[0] + x0), int(vp[1] + y0 - pad), int(x1 - x0), int(y1 - y0 + 2 * pad))
    draw_scene(sc, st, prefs)
    # the key and what the menu does, small in the corner
    _font(FONT_POINTS * 0.9)
    th = _theme()
    from ..pie_menus import key_text
    info = "Sidebar" if pie.menu_type == "PANEL" else (key_text(pie) if pie.enabled else "Off")
    _text(x0 + 0.4 * u, y1 - 0.9 * u, info, _rgba(th.wcol_regular.text, 0.45))
    gpu.state.scissor_test_set(False)
    gpu.state.blend_set('NONE')
    # make sure the modal that handles clicks and drags is running for this window
    wp = st.window_ptr
    if wp and wp not in _running and time.time() - _last_exit.get(wp, 0.0) > 0.3 and not _stop:
        _running.add(wp)  # claimed now, so only one start is scheduled
        rp = region.as_pointer()
        bpy.app.timers.register(lambda: _start_modal(wp, rp), first_interval=0.01)


def _find(window_ptr, region_ptr):
    for win in bpy.context.window_manager.windows:
        if win.as_pointer() != window_ptr:
            continue
        for area in win.screen.areas:
            for reg in area.regions:
                if reg.as_pointer() == region_ptr:
                    return win, area, reg
    return None


def _start_modal(window_ptr, region_ptr):
    found = _find(window_ptr, region_ptr)
    if found is None or _stop:
        _running.discard(window_ptr)
        return None
    win, area, reg = found
    try:
        with bpy.context.temp_override(window=win, area=area, region=reg):
            bpy.ops.keyops.menu_canvas('INVOKE_DEFAULT')
    except Exception:  # noqa: BLE001
        _running.discard(window_ptr)
    return None


def _tag(region_ptr):
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            for reg in area.regions:
                if reg.as_pointer() == region_ptr:
                    reg.tag_redraw()
                    return


# ---------------------------------------------------------------- editing: clicks and drags

def _item_under(st, mx, my):
    sc = st.scene
    if sc is None:
        return None
    return sc.hit(mx, my)


def _drop_target(st, mx, my):
    sc = st.scene
    src = st.drag["src"]
    if sc.kind in ("BLENDER_PIE", "MARKING"):
        el = sc.hit(mx, my)
        if el is None:  # nearest slot, by direction from the centre
            best, bd = None, 1e9
            for e in sc.els:
                d = math.hypot(e.x + e.w / 2 - mx, e.y + e.h / 2 - my)
                if d < bd:
                    best, bd = e, d
            el = best if bd < 3 * unit() else None
        return el.index if el is not None and el.index != src else None
    # menus: the gap before or after the item nearest the mouse in the same column
    cands = [e for e in sc.els if e.kind in ("item", "empty", "sep", "label", "boxhead", "grouptag")
             and e.index != src]
    if not cands:
        return None
    best, bd = None, 1e9
    for e in cands:
        dx = 0 if e.x <= mx <= e.x + e.w else min(abs(mx - e.x), abs(mx - e.x - e.w))
        dy = 0 if e.y <= my <= e.y + e.h else min(abs(my - e.y), abs(my - e.y - e.h))
        d = dx * 3 + dy
        if d < bd:
            best, bd = e, d
    if best is None:
        return None
    # side by side (a row, split or grid): before or after by the mouse's x; stacked: by its y
    beside = any(e is not best and abs(e.y - best.y) < 2 and abs(e.h - best.h) < 2 and e.kind == best.kind
                 and (abs(e.x + e.w - best.x) < 8 or abs(best.x + best.w - e.x) < 8) for e in cands)
    if beside:
        return ("before" if mx < best.x + best.w / 2 else "after", best, "x")
    before = my > best.y + best.h / 2
    return ("before" if before else "after", best, "y")


def _do_drop(st, src):
    PM = _pm()
    prefs = _prefs()
    pie = _cur_pie()
    if pie is None or st.drop is None or not 0 <= src < len(pie.items):
        return
    if pie.menu_type == "PIE":
        dst = st.drop
        a, b = PM._item_to_data(pie.items[src]), PM._item_to_data(pie.items[dst])
        PM._item_from_data(pie.items[src], b)
        PM._item_from_data(pie.items[dst], a)
        prefs.pie_slot = dst
    else:
        kind, el, _axis = st.drop
        items = list(pie.items)
        if kind == "before":
            pos = el.index
        elif items[el.index].kind == PM.BOX and el.kind in ("grouptag", "boxhead"):
            pos = (PM.group_end(items, el.index) or el.index) + 1  # after the whole group
        else:
            pos = el.index + 1
        # a group moves with everything in it, up to its End Group
        end = PM.group_end(items, src) if items[src].kind == PM.BOX else src
        end = src if end is None else end
        n = end - src + 1
        if src <= pos <= end + 1:
            return  # dropped on itself
        if pos > end:
            for _k in range(n):
                pie.items.move(src, pos - 1)
            prefs.pie_slot = pos - n
        else:
            for k in range(n):
                pie.items.move(src + k, pos + k)
            prefs.pie_slot = pos
    PM._changed()


def _click(context, st, el, zone, win, area, region):
    PM = _pm()
    prefs = _prefs()
    with context.temp_override(window=win, area=area, region=region):
        was_selected = prefs.pie_slot == el.index
        if zone == "remove":
            bpy.ops.keyops.menu_item_remove(slot=el.index)
        elif zone == "icon" and el.kind == "item":  # the icon spot: straight to the icons
            prefs.pie_slot = el.index
            bpy.ops.keyops.pie_icon_picker('INVOKE_DEFAULT', slot=el.index)
        elif not was_selected or el.kind in ("marker", "boxhead", "label", "group", "grouptag"):
            prefs.pie_slot = el.index  # first click: select it, its settings show below the preview
        else:  # a selected button clicked again: pick what it does
            bpy.ops.keyops.pie_slot_search('INVOKE_DEFAULT', slot=el.index, scope="ALL")
    PM._redraw_all(context)


def _zone(st, el, mx, my):
    u = unit()
    if st.show_remove:
        x, y, w, h = _remove_rect(el, u)
        if x <= mx <= x + w and y <= my <= y + h:
            return "remove"
    if el.icon and el.kind == "item":
        if st.scene.kind == "BLENDER_PIE":
            ix = el.x + 0.3 * u
            if ix <= mx <= ix + 20 * ui_scale() + 0.2 * u:
                return "icon"
        elif el.icon_rect:
            x, y, w, h = el.icon_rect
            if x <= mx <= x + w and y <= my <= y + h:
                return "icon"
    return "item"


class KEYOPS_OT_menu_canvas(bpy.types.Operator):
    """Runs while the Custom Menus preview is on screen: hover, click and drag its items.
    Every other event goes on to Blender as usual."""
    bl_idname = "keyops.menu_canvas"
    bl_label = "Menu Preview"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        self.window_ptr = context.window.as_pointer()
        _running.add(self.window_ptr)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _end(self, context, st=None):
        _running.discard(self.window_ptr)
        _last_exit[self.window_ptr] = time.time()
        for c in _canvases.values():
            if c.window_ptr == self.window_ptr:
                if c.hover is not None or c.drag:
                    c.hover, c.drag, c.drop, c.mouse = None, None, None, None
        try:
            context.window.cursor_modal_restore()
        except (AttributeError, ReferenceError):
            pass
        _redraw_prefs(context)

    def cancel(self, context):
        _running.discard(getattr(self, "window_ptr", 0))

    def _canvas_at(self, context, event):
        """(canvas, area, region, mouse in region pixels) for the preview under the mouse."""
        win = context.window
        for area in win.screen.areas:
            if area.type != 'PREFERENCES':
                continue
            for reg in area.regions:
                if reg.type != 'WINDOW':
                    continue
                st = _canvases.get(reg.as_pointer())
                if st is None or st.rect is None:
                    continue
                mx, my = event.mouse_x - reg.x, event.mouse_y - reg.y
                if 0 <= mx < reg.width and 0 <= my < reg.height:
                    return st, area, reg, mx, my
        return None

    def modal(self, context, event):
        try:
            return self._modal(context, event)
        except Exception:  # noqa: BLE001  never leave a broken handler on the preferences
            import traceback
            traceback.print_exc()
            for c in _canvases.values():
                c.drag = c.drop = None
            self._end(context)
            return {'CANCELLED', 'PASS_THROUGH'}

    def _modal(self, context, event):
        if _stop or context.window is None:
            self._end(context)
            return {'CANCELLED', 'PASS_THROUGH'}
        if event.type == 'WINDOW_DEACTIVATE':
            self._end(context)
            return {'FINISHED', 'PASS_THROUGH'}
        # still on screen somewhere in this window?
        if not any(c.rect is not None and c.window_ptr == self.window_ptr for c in _canvases.values()):
            self._end(context)
            return {'FINISHED', 'PASS_THROUGH'}
        if event.type.startswith('TIMER') or event.type == 'NONE':
            return {'PASS_THROUGH'}
        at = self._canvas_at(context, event)
        if at is None:
            for c in _canvases.values():
                if c.window_ptr == self.window_ptr and (c.hover is not None or c.mouse is not None) and not c.drag:
                    c.hover, c.mouse = None, None
                    _redraw_prefs(context)
                    try:
                        context.window.cursor_modal_restore()
                    except (AttributeError, ReferenceError):
                        pass
            return {'PASS_THROUGH'}
        st, area, reg, mx, my = at
        x0, y0, x1, y1 = st.rect
        inside = x0 <= mx <= x1 and y0 <= my <= y1

        if st.drag is not None:
            return self._dragging(context, event, st, area, reg, mx, my)

        if event.type == 'MOUSEMOVE' or event.type == 'INBETWEEN_MOUSEMOVE':
            # over a marker row (hidden under the preview): keep the mouse from Blender, so its colour swatch
            # never shows a tooltip
            band = st.pad
            if x0 <= mx <= x1 and (y0 - band <= my < y0 or y1 < my <= y1 + band):
                return {'RUNNING_MODAL'}
            el = _item_under(st, mx, my) if inside else None
            new = el.index if el is not None else None
            zone = _zone(st, el, mx, my) if el is not None else ""
            mouse = (mx, my) if inside else None
            changed = (new != st.hover) or (zone != st.hover_zone) or (st.scene and st.scene.kind in ("BLENDER_PIE", "MARKING") and new is not None)
            if (st.mouse is None) != (mouse is None):
                changed = True
            st.hover, st.hover_zone, st.mouse = new, zone, mouse
            if st.scene is not None and st.scene.frame and mouse is not None:
                fx, fy, fw, fh = st.scene.frame
                pad = unit()
                on_menu = fx - pad <= mx <= fx + fw + pad and fy - pad <= my <= fy + fh + pad
                changed = changed or on_menu != st.scene.show_markers
            if changed:
                reg.tag_redraw()
                try:
                    if new is not None:
                        context.window.cursor_modal_set('HAND')
                    else:
                        context.window.cursor_modal_restore()
                except (AttributeError, ReferenceError, TypeError):
                    pass
            return {'PASS_THROUGH'}

        if not inside:
            return {'PASS_THROUGH'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            el = _item_under(st, mx, my)
            if el is None:
                return {'PASS_THROUGH'}
            zone = _zone(st, el, mx, my)
            st.drag = {"src": el.index, "start": (mx, my), "grab": (mx - el.x, my - el.y), "active": False,
                       "zone": zone, "el": el, "area": area.as_pointer()}
            return {'RUNNING_MODAL'}
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':  # everything about the item, in one menu
            el = _item_under(st, mx, my)
            if el is None:
                return {'PASS_THROUGH'}
            with context.temp_override(window=context.window, area=area, region=reg):
                bpy.ops.keyops.item_options('INVOKE_DEFAULT', slot=el.index)
            reg.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type in {'DEL', 'X'} and event.value == 'PRESS' and st.hover is not None and st.show_remove \
                and not (event.ctrl or event.alt or event.shift):
            with context.temp_override(window=context.window, area=area, region=reg):
                bpy.ops.keyops.menu_item_remove(slot=st.hover)
            st.hover = None
            reg.tag_redraw()
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}

    def _dragging(self, context, event, st, area, reg, mx, my):
        d = st.drag
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            st.mouse = (mx, my)
            if not d["active"] and math.hypot(mx - d["start"][0], my - d["start"][1]) > DRAG_START * ui_scale():
                if d["zone"] != "remove" and st.scene is not None:
                    d["active"] = True
                    try:
                        context.window.cursor_modal_set('SCROLL_XY')
                    except (AttributeError, ReferenceError, TypeError):
                        pass
            if d["active"]:
                st.drop = _drop_target(st, mx, my)
                reg.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            st.drag = None
            try:
                context.window.cursor_modal_set('HAND')
            except (AttributeError, ReferenceError, TypeError):
                pass
            if d["active"]:
                _do_drop(st, d["src"])
                st.drop = None
                _redraw_prefs(context)
            else:
                _click(context, st, d["el"], d["zone"], context.window, area, reg)
            reg.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            st.drag, st.drop = None, None
            reg.tag_redraw()
            return {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'}


def _redraw_prefs(context):
    for win in context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'PREFERENCES':
                area.tag_redraw()


# ---------------------------------------------------------------- registration

def register():
    global _handle, _stop
    _stop = False
    bpy.utils.register_class(KEYOPS_OT_menu_canvas)
    wm = bpy.types.WindowManager
    # fixed colours: a click on a marker can't change them (set does nothing)
    wm.keyops_canvas_mark_top = bpy.props.FloatVectorProperty(
        subtype='COLOR_GAMMA', size=3, get=lambda self: MARK_TOP, set=lambda self, value: None, options={'SKIP_SAVE'})
    wm.keyops_canvas_mark_bottom = bpy.props.FloatVectorProperty(
        subtype='COLOR_GAMMA', size=3, get=lambda self: MARK_BOTTOM, set=lambda self, value: None, options={'SKIP_SAVE'})
    _handle = bpy.types.SpacePreferences.draw_handler_add(_draw_callback, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _handle, _stop
    _stop = True
    if _handle is not None:
        try:
            bpy.types.SpacePreferences.draw_handler_remove(_handle, 'WINDOW')
        except (ValueError, ReferenceError):
            pass
        _handle = None
    _canvases.clear()
    _running.clear()
    _icons.tex.clear()
    _icons.key = None
    wm = bpy.types.WindowManager
    for name in ("keyops_canvas_mark_top", "keyops_canvas_mark_bottom"):
        if hasattr(wm, name):
            delattr(wm, name)
    bpy.utils.unregister_class(KEYOPS_OT_menu_canvas)
