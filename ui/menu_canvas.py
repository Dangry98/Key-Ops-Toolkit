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

# Shapes don't go to the GPU one by one: a run of fills (or of lines of one width) is gathered and drawn as
# one batch, which keeps a big menu cheap to redraw. The order on screen stays the same: anything else that
# draws (text, icons, another kind of shape) sends the gathered run first (_flush).
_queue = {"kind": None, "width": 1.0, "pos": [], "col": [], "idx": []}


def _flush():
    q = _queue
    if not q["pos"]:
        q["kind"] = None
        return
    gpu.state.blend_set('ALPHA')  # blf.draw turns blending off when it's done
    if q["kind"] == "fill":
        sh = gpu.shader.from_builtin('SMOOTH_COLOR')
        batch = batch_for_shader(sh, 'TRIS', {"pos": q["pos"], "color": q["col"]}, indices=q["idx"])
        sh.bind()
    else:
        region = bpy.context.region
        sh = gpu.shader.from_builtin('POLYLINE_FLAT_COLOR')
        batch = batch_for_shader(sh, 'LINES', {"pos": q["pos"], "color": q["col"]})
        sh.bind()
        sh.uniform_float("viewportSize", (region.width, region.height))
        sh.uniform_float("lineWidth", q["width"])
    batch.draw(sh)
    q["kind"] = None
    q["pos"], q["col"], q["idx"] = [], [], []


def _queue_for(kind, width=1.0):
    q = _queue
    if q["kind"] != kind or (kind == "line" and q["width"] != width):
        _flush()
        q["kind"], q["width"] = kind, width
    return q


def _fill(verts, indices, color, colors=None):
    q = _queue_for("fill")
    base = len(q["pos"])
    q["pos"].extend(verts)
    q["col"].extend(colors if colors is not None else [tuple(color)] * len(verts))
    q["idx"].extend((a + base, b + base, c + base) for a, b, c in indices)


def _rect(x, y, w, h, color):
    _fill([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], [(0, 1, 2), (0, 2, 3)], color)


def _corner_radii(r, join):
    """(bottom right, top right, top left, bottom left) radii: square where the side is joined to a neighbour."""
    return (0 if {"R", "B"} & join else r, 0 if {"R", "T"} & join else r,
            0 if {"L", "T"} & join else r, 0 if {"L", "B"} & join else r)


_arcs = {}  # (start angle, segments) -> the quarter circle's (cos, sin) steps, worked out once


def _arc(a0, seg):
    got = _arcs.get((a0, seg))
    if got is None:
        got = _arcs[(a0, seg)] = [(math.cos(math.radians(a0 + 90 * k / seg)), math.sin(math.radians(a0 + 90 * k / seg)))
                                  for k in range(seg + 1)]
    return got


def _outline_pts(x, y, w, h, r, seg=8):
    if isinstance(r, tuple):
        lim = min(w / 2, h / 2)
        pts = []
        for (cx, cy, a0), rr in zip(((x + w, y, -90), (x + w, y + h, 0), (x, y + h, 90), (x, y, 180)), r):
            rr = max(0.0, min(rr, lim))
            if rr <= 0.01:
                pts.append((cx, cy))
                continue
            ox = cx + (-rr if cx > x else rr)
            oy = cy + (rr if cy == y else -rr)
            pts.extend([(ox + rr * c, oy + rr * s) for c, s in _arc(a0, seg)])
        return pts
    r = max(0.0, min(r, w / 2, h / 2))
    if r <= 0.01:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    pts = []
    for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
        pts.extend([(cx + r * c, cy + r * s) for c, s in _arc(a0, seg)])
    return pts


_fans = {}  # point count -> the triangle fan indices around a centre vertex


def _fan(n):
    got = _fans.get(n)
    if got is None:
        got = _fans[n] = [(0, i, i % n + 1) for i in range(1, n + 1)]
    return got


def _line(pts, color, width=1.0, closed=False):
    pts = list(pts) + ([pts[0]] if closed else [])
    if len(pts) < 2:
        return
    q = _queue_for("line", width)
    col = tuple(color)
    pos = q["pos"]
    for k in range(len(pts) - 1):  # a strip as separate segments, so runs of lines share one batch
        pos.append(pts[k])
        pos.append(pts[k + 1])
    q["col"].extend([col] * (2 * (len(pts) - 1)))


def _round_fill(x, y, w, h, r, color):
    pts = _outline_pts(x, y, w, h, r)
    _fill([(x + w / 2, y + h / 2)] + pts, _fan(len(pts)), color)


def _round_fill_grad(x, y, w, h, r, top, bottom):
    """A rounded box filled with a top-to-bottom gradient (Blender's shaded widgets)."""
    pts = _outline_pts(x, y, w, h, r)
    mix = lambda f: tuple(bottom[k] + (top[k] - bottom[k]) * f for k in range(4))
    verts = [(x + w / 2, y + h / 2)] + pts
    cols = [mix(0.5)] + [mix(min(1.0, max(0.0, (py - y) / max(h, 1)))) for _px, py in pts]
    _fill(verts, _fan(len(pts)), None, colors=cols)


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
    _flush()
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
            o[..., :3] = np.clip(bgc + d / np.maximum(a, 1e-3)[..., None], 0.0, 1.0)
            # Blender draws a coloured icon in a label slightly see-through: picked up as is, it would show the
            # button under it and look washed out. Its most solid pixel is solid in a real button.
            peak = float(a.max())
            o[..., 3] = np.clip(a / peak, 0.0, 1.0) if peak > 0.05 else a
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
    # a crisp plus (rectangles on whole pixels, so it never looks blurry); hovered, the zone outline frames it
    s = ui_scale()
    size = round(14 * s)
    a = tint[3] * alpha
    x, y = round(cx - size / 2), round(cy - size / 2)
    t = max(1, round(1.4 * s))       # stroke
    arm = round(8 * s) // 2 * 2 + t  # odd/even matched to the stroke, so the plus sits centred
    mx, my = x + (size - t) // 2, y + (size - t) // 2
    col = (tint[0], tint[1], tint[2], a * 0.7)
    _rect(x + (size - arm) // 2, my, arm, t, col)
    _rect(mx, y + (size - arm) // 2, t, (arm - t) // 2, col)  # the vertical bar in two halves, not over the middle
    _rect(mx, my + t, t, (arm - t) // 2, col)


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
    _flush()
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
                 "emboss", "active", "depress", "dim", "join", "show", "segs", "value", "frac", "look")

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
        self.segs = kw.get("segs")  # an expanded setting: its choices [(text, icon, chosen)], drawn as one row
        self.value = kw.get("value", "")  # a setting's current value, as its field shows it
        self.frac = kw.get("frac", 0.5)   # how full a slider is
        self.look = kw.get("look", "BUTTON")  # popup menus: how the real menu draws it (pie_menus.popup_menu_look)

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
        self.centres = []    # marking chains: (x, y, is the edited menu) of every menu shown
        self.links = []      # marking chains: lines from a sub-menu item to its menu
        self.subs = []       # popup menus: each menu shown (the edited one, its open submenus), own frame each

    def hit(self, mx, my):
        for el in reversed(self.els):
            if el.kind in ("marker", "grouptag") and not (self.show_markers and el.show):
                continue
            if el.kind in ("item", "empty", "marker", "boxhead", "label", "sep", "group", "grouptag") and el.contains(mx, my):
                return el
        return None

    def offset(self, dx, dy, els=True):
        if els:
            for el in self.els:
                el.moved(dx, dy)
        for sub in self.subs:  # their items are in self.els (moved above); move their frames and titles
            sub.offset(dx, dy, els=False)
        self.cx += dx
        self.cy += dy
        self.centres = [(x + dx, y + dy, a) for x, y, a in self.centres]
        self.links = [((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)) for a, b in self.links]
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
    return dict(emboss=item.emboss, active=getattr(item, "active", True) and getattr(item, "enabled", True),
                depress=getattr(item, "depress", False))


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


def _setting(item):
    """(Blender's property, its current value) for a setting item, or None when it can't be found here."""
    PM = _pm()
    try:
        data, prop = PM._resolve(bpy.context, item.idname)
        rna = data.bl_rna.properties[prop]
        return rna, getattr(data, prop)
    except Exception:  # noqa: BLE001
        return None


def _value_text(rna, value):
    """A number setting's value the way its field shows it."""
    if rna.type == 'INT':
        return f"{value}%" if rna.subtype == 'PERCENTAGE' else str(value)
    if rna.type == 'FLOAT':
        if getattr(rna, "array_length", 0):
            return ""
        txt = f"{value:.{max(0, min(rna.precision, 5))}f}"
        if rna.subtype == 'PERCENTAGE':
            return txt + "%"
        if rna.subtype in ('DISTANCE', 'LENGTH'):
            return txt + " m"
        if rna.subtype == 'ANGLE':
            return f"{math.degrees(value):.0f}\u00b0"
        return txt
    return ""


def _slider_frac(rna, value):
    try:
        lo, hi = rna.soft_min, rna.soft_max
        return min(1.0, max(0.0, (value - lo) / (hi - lo))) if hi > lo else 0.5
    except Exception:  # noqa: BLE001
        return 0.5


def _field(item):
    """How a setting is drawn in a dialog or panel, from what kind of setting it is (style AUTO) or its
    style: (style, value text, slider fill)."""
    st = getattr(item, "setting_style", "AUTO")
    found = _setting(item)
    if found is None:
        return ({"SLIDER": "SLIDER", "BUTTON": "BUTTON", "EXPAND": "BUTTON"}.get(st, "CHECK"), "", 0.5)
    rna, value = found
    kind = rna.type
    if st in ("SEARCH", "ID"):  # a field showing the picked item's name
        return ("DROPDOWN", getattr(value, "name", "") if value is not None else "", 0.5)
    if st == "MENU" and kind == 'ENUM' and not rna.is_enum_flag:
        name = next((e.name for e in rna.enum_items if e.identifier == value), "")
        return ("DROPDOWN", name, 0.5)
    if st in ("LIST", "COLOR", "RAMP", "CURVE", "PALETTE", "ICONS", "VALUE", "TABS", "POPOVER"):
        return ("BUTTON", "", 0.5)  # the real one only exists in Blender: a placeholder button
    if kind in ('INT', 'FLOAT') and not getattr(rna, "array_length", 0):
        slider = st == "SLIDER" or rna.subtype in ('PERCENTAGE', 'FACTOR')
        return ("SLIDER" if slider else "NUMBER", _value_text(rna, value), _slider_frac(rna, value))
    if kind == 'BOOLEAN':
        if st == "BUTTON" or (st == "AUTO" and rna.icon != 'NONE'):  # a setting with an icon is a toggle button
            return ("BUTTON", "", 0.5)
        return ("CHECK", "", 0.5)
    if kind == 'ENUM' and st != "EXPAND" and not rna.is_enum_flag:
        name = next((e.name for e in rna.enum_items if e.identifier == value), "")
        return ("DROPDOWN", name, 0.5)
    if kind == 'STRING':
        return ("TEXT", str(value), 0.5)
    return ("BUTTON", "", 0.5)


def _clip(text, w):
    """Text cut to fit a width the way Blender does it: with "..." while there's room for it."""
    if _text_w(text) <= w:
        return text
    for n in range(len(text) - 1, 0, -1):
        if _text_w(text[:n] + "...") <= w:
            return text[:n] + "..."
    for n in range(len(text) - 1, 0, -1):
        if _text_w(text[:n]) <= w:
            return text[:n]
    return ""


def _segments(item):
    """An expanded choice setting's buttons: [(text, icon, chosen)], or None."""
    if getattr(item, "setting_style", "AUTO") not in ("EXPAND", "TABS"):
        return None
    found = _setting(item)
    if found is None or found[0].type != 'ENUM':
        return None
    rna, value = found
    chosen = value if isinstance(value, set) else {value}
    return [(e.name, "" if e.icon == 'NONE' else e.icon, e.identifier in chosen) for e in rna.enum_items]


def _segments_w(segs):
    u = unit()
    return sum(_text_w(t) + math.ceil(u * (1.5 + (0.25 if i else 0.0))) if t else u for t, i, _c in segs)


def _item_texts(item):
    """(text, icon name or '') the way the real menu button shows them."""
    PM = _pm()
    if item.kind == PM.SUB:
        target = PM.find_pie(item.idname)
        default = item.label or (target.name if target else item.idname)
        icon = PM.item_icon(item, PM.TYPE_ICON.get(target.menu_type, 'NONE') if target else 'NONE')
    elif item.kind == PM.SCRIPT:
        default, icon = item.label or "Python", PM.item_icon(item, 'SCRIPT')
    elif item.kind == PM.DRAW:  # its real look only exists when it runs: a placeholder in the preview
        default, icon = item.label or "Draw Code", PM.item_icon(item, 'CONSOLE')
    elif item.kind == PM.MACRO:
        default, icon = item.label or "Macro", PM.item_icon(item)
    elif item.kind == PM.P:
        found = _setting(item)
        default = item.label or (found[0].name if found else item.idname.strip().split(".")[-1].replace("_", " ").title())
        icon = PM.item_icon(item)
        if icon in ('NONE', '', None) and found and getattr(item, "setting_style", "AUTO") != "CHECKBOX":
            icon = found[0].icon  # Blender shows the setting's own icon
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
    """The item is drawn in a sub-layout of its own (pie_menus._styled), so the pie shows it as a plain button."""
    return not (item.height == 1.0 and item.width == 1.0 and item.emboss and not item.alert
                and getattr(item, "active", True)) or _segments(item) is not None


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
        group = PM.inline_target(item)
        if group is not None:  # several buttons in this direction (pie_menus._draw_inline_group)
            _pie_group(sc, i, item, group, vx, vy, fx, fy, R, u)
            aligned |= d in ("N", "S", "E", "W")
            diagonal |= d not in ("N", "S", "E", "W")
            continue
        empty = PM._is_empty(item)
        text, icon, default = texts[i]
        styled = not empty and item.kind != PM.LABEL and _styled(item)
        dim = False
        if empty:
            text, icon = "Empty", ""
        else:
            text, icon, dim = _hovered(text, icon, default, i == hover)
        tw = _text_w(text)
        segs = None if empty else _segments(item)
        label = not empty and item.kind == PM.LABEL
        if segs:
            w = _segments_w(segs)
        elif label:  # a heading, in a sub-layout of its own so it keeps its slot: just its text
            w = tw + (u if icon else 0) + math.ceil(0.4 * u)
        elif icon and not text:
            w = u
        elif text:
            w = tw + math.ceil(u * (1.5 + (0.25 if icon else 0.0)))
        else:
            w = u
        if label:
            h = u
        elif styled:  # a sub-layout: a plain button, not a pie item
            h = u * item.height
            sx = item.width
            # measured on Blender's pies: a wider row grows by more than its scale (1.5 u per unit of scale)
            w = w * sx + (1.5 * u * sx * (sx - 1) if sx != 1.0 else 0)
        else:
            w += 1.5 * u
            h = 1.5 * u
        w, h = int(w), int(h)
        x = int(vx * R + fx * w)
        y = int(vy * R + fy * h)
        if not empty:
            aligned |= d in ("N", "S", "E", "W")
            diagonal |= d not in ("N", "S", "E", "W")
        style = "LABEL" if label else ("BUTTON" if styled else "PIE")
        sc.els.append(El(i, x, y, w, h, kind="empty" if empty else "item", text=text, icon=icon,
                         num="" if label else NUMPAD[d], key="" if dim or label else keys[i], sub=item.kind == PM.SUB,
                         style=style + ("_ALERT" if not empty and item.alert else ""),
                         icon_rect=None, dim=dim, segs=segs, **({} if empty else _look(item))))
    _pie_extras(sc, pie, u, s, R)
    sc.dirmask = (aligned, diagonal)
    sc.title = pie.name
    tw = _text_w(pie.name)
    sc.title_rect = (-tw / 2, int(thr + 9 * s), tw, u)
    xs = [e.x for e in sc.els] + [e.x + e.w for e in sc.els] + [-tw / 2, tw / 2]
    ys = [e.y for e in sc.els] + [e.y + e.h for e in sc.els] + [thr + 9 * s + u] + [b[1] + b[3] for b in sc.boxes]
    ext_x = max(abs(v) for v in xs)
    ext_y = max(abs(v) for v in ys)
    sc.w, sc.h = 2 * ext_x, 2 * ext_y
    return sc


def _pie_group(sc, i, item, group, vx, vy, fx, fy, R, u):
    """A pie direction holding a group of buttons: a box (or a plain column or row) of the group menu's items,
    every one of them selecting the pie's item i when clicked (the group's own buttons are edited in it)."""
    PM = _pm()
    rows = []
    for it in group.items:
        if it.kind in PM.LAYOUT_KINDS:
            continue
        if PM._is_empty(it):
            rows.append(("", "", True))
            continue
        text, icon, _d = _item_texts(it)
        rows.append((text, icon, False))
    if not rows:
        rows.append(("Empty group", "", False))
    widths = [(_text_w(t) + math.ceil(u * (1.5 + (0.25 if ic else 0.0)))) if t else u for t, ic, _sep in rows]
    horizontal = item.group_type in ("ROW", "SPLIT")
    framed = item.group_type in ("BOX", "PANEL")
    pad = int(0.4 * u) if framed else 0
    head = u if item.label.strip() else 0
    if horizontal:
        inner_w, inner_h = sum(widths), u
    else:
        inner_w, inner_h = max(widths), sum(int(0.5 * u) if sep else u for _t, _ic, sep in rows)
    w, h = int(inner_w + 2 * pad), int(inner_h + 2 * pad + head)
    x = int(vx * R + fx * w)
    y = int(vy * R + fy * h)
    if framed:
        sc.boxes.append((x, y, w, h))
    if head:
        sc.els.append(El(i, x + pad, y + h - pad - u, w - 2 * pad, u, kind="label", text=item.label, style="LABEL",
                         icon=PM.item_icon(item, '') if item.icon else ""))
    cx, cy = x + pad, y + h - pad - head
    look = _look(item)
    for n, ((text, icon, sep), rw) in enumerate(zip(rows, widths)):
        if sep:
            cy -= int(0.5 * u)
            continue
        if horizontal:
            el = El(i, cx, cy - u, rw, u, kind="item", text=text, icon=icon, style="BUTTON", **look)
            cx += rw
        else:
            el = El(i, cx, cy - u, inner_w, u, kind="item", text=text, icon=icon, style="BUTTON", **look)
            cy -= u
        if item.align and n > 0:
            el.join.add("L" if horizontal else "T")
        if item.align and n < len(rows) - 1:
            el.join.add("R" if horizontal else "B")
        sc.els.append(el)


def _pie_extras(sc, pie, u, s, R):
    """A Blender pie's extra items (after its 8 directions): a box of buttons on top of its top item, which
    joins them in a column (pie_menus.draw_pie_items)."""
    PM = _pm()
    extras = list(range(PM.PIE_SLOTS, len(pie.items)))
    if not extras:
        return
    rows = []
    for i in extras:
        it = pie.items[i]
        empty = PM._is_empty(it)
        text, icon, _d = _item_texts(it) if not empty else ("Empty", "", "")
        w = _text_w(text) + math.ceil(u * (1.5 + (0.25 if icon else 0.0))) if text else u
        rows.append((i, text, icon, w, empty, it))
    top_i = PM.ORDER.index("N")
    top = next((e for e in sc.els if e.index == top_i), None)
    if top is not None and top_i < len(pie.items) and PM.inline_target(pie.items[top_i]) is not None:
        top = None  # a group up there: the extras go above it, it keeps its own look
        R = max([e.y + e.h for e in sc.els if e.index == top_i] + [R]) + int(0.2 * u)
    width = max([w for *_a, w, _e, _it in rows] + [top.w if top else 0])
    width = int(width + 0.8 * u)  # the box's padding
    y = R
    if top is not None:  # the top item becomes a plain button at the bottom of the column
        top.style = "BUTTON" + ("_ALERT" if top.style.endswith("_ALERT") else "")
        top.num, top.w, top.h = "", width, u
        top.x, top.y = -width // 2, R
        y = R + u + int(0.2 * u)
    pad = int(0.4 * u)
    bh = len(rows) * u + 2 * pad
    sc.boxes.append((-width // 2, y, width, bh))
    for n, (i, text, icon, _w, empty, it) in enumerate(rows):
        yy = y + bh - pad - (n + 1) * u
        el = El(i, -width // 2 + pad, yy, width - 2 * pad, u, kind="empty" if empty else "item", text=text,
                icon=icon, style="BUTTON" + ("_ALERT" if not empty and it.alert else ""), **({} if empty else _look(it)))
        if n > 0:  # an aligned column: joined to its neighbours
            el.join.add("T")
        if n < len(rows) - 1:
            el.join.add("B")
        sc.els.append(el)


def build_marking(pie):
    MM = _mm()
    PM = _pm()
    sc = Scene("MARKING")
    look = MM._look()
    s = ui_scale()
    k = s * ((pie.radius / max(look.marking_top, 1)) if pie.radius else 1.0)
    slots = [(PM.ORDER[i], i) for i in range(min(8, len(pie.items)))]
    boxes = MM.marking_boxes(pie, slots, 0.0, 0.0, look, s, k, None, show_empty=True)
    # the extra items after the 8 directions: Maya's list under the menu
    boxes += MM.marking_list_boxes(pie, list(range(PM.PIE_SLOTS, len(pie.items))), 0.0, 0.0, look, s, k, None,
                                   show_empty=True)
    bh = MM.marking_box_height(look, s)
    sc.marking = boxes
    for bx, by, bw, _w, _arrow, label, sub, _sel, index in boxes:
        empty = PM._is_empty(pie.items[index])
        sc.els.append(El(index, bx, by, bw, bh, kind="empty" if empty else "item", text=label, sub=sub, style="MARK"))
    xs = [abs(v) for b in boxes for v in (b[0], b[0] + b[2])] or [50]
    ys = [abs(v) for b in boxes for v in (b[1], b[1] + bh)] or [50]
    sc.w, sc.h = 2 * max(xs), 2 * max(ys)
    return sc


def _menu_value(rna, value):
    """A setting's value as a popup menu field shows it: numbers as their field does, choices by name."""
    if rna.type == 'ENUM':
        chosen = value if isinstance(value, set) else {value}
        return ", ".join(e.name for e in rna.enum_items if e.identifier in chosen)
    return _value_text(rna, value) or str(value)


def _menu_item_w(text, icon, u):
    return _text_w(text) + (u if icon else 0) + u * (0.2 + 0.4 + 0.6)


def build_menu(pie, hover=None, sub=False):
    """A popup menu (Blender's menu look), a popup panel, a dialog or a sidebar panel.
    sub: shown as a submenu (opened from another menu's item): no title, like Blender's submenus."""
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
    if pie.menu_type != "PANEL" and not sub:
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
                # what the real popup menu draws for it (pie_menus.popup_menu_look decides for both)
                look = PM.popup_menu_look(it) if kind == "item" else "BUTTON"
                if look == "SUBMENU" and it.kind == PM.P:
                    icon = "" if PM.item_icon(it) == 'NONE' else PM.item_icon(it)  # a choice: only its own icon
                elif look == "CHECKBOX":
                    icon = ""  # a checkbox instead of an icon
                elif look == "FIELD":  # a number, text or several-choice setting: "Label: value", like Blender
                    found = PM.setting_rna(it)
                    if found is not None:
                        value = _menu_value(*found)
                        text = f"{text}: {value}" if text else value
                        default = f"{default}: {value}" if default else value
                if kind == "empty":
                    text = "Empty"
                elif kind == "item":
                    text, icon, dim = _hovered(text, icon, default, i == hover)
                style = "MENU" if as_menu else _panel_style(it)
                el = El(i, int(xx), y - rh, int(w), rh, kind=kind, text=text, icon=icon, key="" if dim else keys[i],
                        sub=look == "SUBMENU", style=style + ("_ALERT" if it.alert else ""), col=c, dim=dim,
                        look=look, **_look(it))
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
            segs = None if PM._is_empty(it) else _segments(it)
            if segs:
                return _segments_w(segs) * it.width
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
        segs = _segments(it) if kind == "item" else None
        style = "MENU" if self.menu_look and it.kind != PM.LABEL else _panel_style(it)
        if segs:  # an expanded setting is a row of buttons, in a menu too
            style = "BUTTON"
        value, frac = "", 0.5
        if kind == "item" and it.kind == PM.P and not segs:
            _st, value, frac = _field(it)
        el = El(i, int(x), int(y - h), int(w), h, kind=kind, text=text, icon=icon, key="" if dim else self.keys[i],
                sub=it.kind == PM.SUB, style=style + ("_ALERT" if it.alert else ""), dim=dim, segs=segs,
                value=value, frac=frac, **_look(it))
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
        self.late.append(El(i, gx - int(2 * s), int(top - th / 2), int(tw), th, kind="grouptag", text=name,
                            col=end if end is not None else i))
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
    if pie.menu_type == "DIALOG" and not grid:  # the dialog is 180 px per Columns wide, whatever is in it
        total = 180 * s * max(1, pie.columns)
        colw = int((total - gap * (ncol - 1)) / max(1, ncol))
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
        return _field(item)[0]
    if item.kind == PM.PANEL_ITEM:  # a popover: a dropdown button
        return "DROPDOWN"
    if not item.emboss:
        return "FLAT"
    return "BUTTON"


def build(pie, prefs, hover=None):
    if pie.menu_type == "PIE":
        if getattr(prefs, "pie_style", "BLENDER") == "MARKING":
            return build_marking_chain(pie, prefs)
        return build_blender_pie(pie, hover)
    if pie.menu_type == "MENU":
        return build_menu_chain(pie, prefs, hover)
    return build_menu(pie, hover)


def _menu_sub_target(p, index):
    """The popup menu that item opens as a submenu, or None."""
    PM = _pm()
    if p is None or index is None or not 0 <= index < len(p.items):
        return None
    it = p.items[index]
    if it.kind != PM.SUB or PM.popup_menu_look(it) != "SUBMENU":
        return None
    return PM.find_pie(it.idname)


def menu_chain(pie, prefs, hover=None):
    """The popup menus the preview shows: the edited one, the menus above it it was opened from, and the
    submenu open beside it. A submenu opens when the mouse is on the item that opens it (or that item is
    selected), and stays open until the mouse is on another item that opens one: moving over empty space,
    clicking or dragging never swaps it back to the selected item's submenu."""
    global _chain, _chain_slot, _choice
    PM = _pm()
    if pie.uid not in _chain:
        _chain, _choice = [pie.uid], None
    pos = _chain.index(pie.uid)
    slot = (pie.uid, prefs.pie_slot)
    if hover is not None:
        opener = (pos, hover) if hover < SUB_STRIDE else (hover // SUB_STRIDE - 1, hover % SUB_STRIDE)
    elif slot != _chain_slot:  # the selection changed: open the submenu of the newly selected item
        opener = (pos, prefs.pie_slot)
    else:
        opener = None
    _chain_slot = slot
    if opener is not None and 0 <= opener[0] < len(_chain):
        op = PM.find_pie(_chain[opener[0]])
        t = _menu_sub_target(op, opener[1])
        if t is not None and t.uid not in _chain[:opener[0] + 1]:
            _chain, _choice = _chain[:opener[0] + 1] + [t.uid], None
        elif t is None and opener[0] >= pos and _choice_rna(op, opener[1]) is not None:
            # a several-choice setting: its choices open beside it, as Blender's menu shows them
            _chain, _choice = _chain[:opener[0] + 1], opener
    pies = []
    for n, uid in enumerate(_chain):  # each one must still be opened by an item of the one before
        p = PM.find_pie(uid)
        if p is None or (n and not any(getattr(_menu_sub_target(pies[-1], i), "uid", None) == uid
                                       for i in range(len(pies[-1].items)))):
            _chain = _chain[:n]
            break
        pies.append(p)
    if pie.uid not in _chain:
        _chain, pies, _choice = [pie.uid], [pie], None
    if _choice is not None and (_choice[0] != len(pies) - 1 or _choice_rna(pies[-1], _choice[1]) is None):
        _choice = None  # its menu closed, or the item is no longer a several-choice setting
    return pies


def close_submenus_after(pie):
    """A click on an item that opens no submenu closes the submenus open after its menu."""
    global _chain, _choice
    if pie is not None and pie.uid in _chain:
        n = _chain.index(pie.uid)
        _chain = _chain[:n + 1]
        if _choice is not None and _choice[0] >= n:
            _choice = None


def _choice_rna(p, index):
    """(rna, value) of a several-choice setting that opens its choices as a submenu, or None."""
    PM = _pm()
    if p is None or index is None or not 0 <= index < len(p.items):
        return None
    it = p.items[index]
    if it.kind != PM.P or PM.popup_menu_look(it) != "SUBMENU":
        return None
    found = PM.setting_rna(it)
    return found if found is not None and found[0].type == 'ENUM' and not found[0].is_enum_flag else None


def build_choices(rna, value, base, hover=None):
    """The choices of a several-choice setting, shown as a submenu like Blender's: the current one marked.
    Only shown: they are Blender's own, not items of the menu, so there is nothing to edit on them."""
    s, u = ui_scale(), unit()
    _font()
    sc = Scene("MENU")
    pad = int(0.25 * u)
    choices = [e for e in rna.enum_items]
    any_icon = any(e.icon != 'NONE' for e in choices)
    colw = int(max([9 * u] + [_menu_item_w(e.name, any_icon, u) for e in choices]))
    y = -pad
    for j, e in enumerate(choices):
        el = El(base + j, pad, y - u, colw, u, kind="item", text=e.name,
                icon="" if e.icon == 'NONE' else e.icon, style="MENU", look="BUTTON",
                depress=e.identifier == value)
        sc.els.append(el)
        y -= u
    h = -y + pad
    w = pad * 2 + colw
    sc.frame = (0, -h, w, h)
    sc.panel_header = (0, 0, w, 0)
    sc.w, sc.h = w, h
    sc.offset(-w / 2, h / 2)
    return sc


def build_menu_chain(pie, prefs, hover=None):
    """A popup menu with its open submenu beside it (and theirs), as Blender shows them. The edited menu's
    items keep their index; the other menus' items get (position in the chain + 1) * SUB_STRIDE + index."""
    pies = menu_chain(pie, prefs, hover)
    if len(pies) == 1 and _choice is None:
        return build_menu(pie, hover)
    u = unit()
    active = pies.index(pie)
    out = Scene("MENU")
    prev, prev_k = None, 0
    for k, p in enumerate(pies):
        base = 0 if k == active else (k + 1) * SUB_STRIDE
        h = hover - base if hover is not None and (hover < SUB_STRIDE) == (base == 0) and \
            (base == 0 or hover // SUB_STRIDE == k + 1) else None
        sc = build_menu(p, h, sub=k > 0)
        if prev is not None and prev.frame and sc.frame:
            # beside the item that opens it: its top row level with that item, its left edge on the menu's right
            pbase = 0 if prev_k == active else (prev_k + 1) * SUB_STRIDE
            opener = next((e for e in prev.els if e.kind == "item"
                           and getattr(_menu_sub_target(pies[prev_k], e.index - pbase), "uid", None) == p.uid), None)
            px, py, pw, ph = prev.frame
            fx, fy, fw, fh = sc.frame
            top = (opener.y + opener.h + int(0.25 * u)) if opener is not None else py + ph
            sc.offset(px + pw - int(0.1 * u) - fx, top - (fy + fh))
        for e in sc.els:
            e.index += base
        out.els.extend(sc.els)
        out.subs.append(sc)
        prev, prev_k = sc, k
    found = _choice_rna(pies[-1], _choice[1]) if _choice is not None else None
    if found is not None and prev is not None and prev.frame:
        # the choices of a setting in the last menu, beside it (their indices are past every menu's)
        pbase = 0 if prev_k == active else (prev_k + 1) * SUB_STRIDE
        sc = build_choices(found[0], found[1], (len(pies) + 1) * SUB_STRIDE)
        opener = next((e for e in prev.els if e.kind == "item" and e.index == pbase + _choice[1]), None)
        px, py, pw, ph = prev.frame
        fx, fy, fw, fh = sc.frame
        top = (opener.y + opener.h + int(0.25 * u)) if opener is not None else py + ph
        sc.offset(px + pw - int(0.1 * u) - fx, top - (fy + fh))
        out.els.extend(sc.els)
        out.subs.append(sc)
    first = out.subs[0]
    edited = out.subs[active]
    out.frame, out.title_rect = edited.frame, None  # the edited menu: where the layout markers show
    out.w, out.h, out.cx, out.cy = first.w, first.h, first.cx, first.cy
    return out


SUB_STRIDE = 1000  # items of the other menus shown beside the edited one: (position in the chain + 1) * this + index
_chain_slot = None  # (menu, selected item) menu_chain last saw: the selection opens a submenu only when it changes
_choice = None      # (position in the chain, item index): a several-choice setting showing its choices beside it
_chain = []        # the marking menu being edited and the sub-menus opened from it in the preview (uids)


def _sub_target(pie, index):
    PM = _pm()
    if not 0 <= index < len(pie.items) or pie.items[index].kind != PM.SUB:
        return None
    t = PM.find_pie(pie.items[index].idname)
    return t if t is not None and t.menu_type == "PIE" else None


def marking_chain(pie, prefs):
    """The menus the marking preview shows: the one picked in the list, then each sub-menu opened from it,
    like Maya shows a sub-menu beside the item that opens it. Selecting a sub-menu item opens its menu."""
    global _chain
    PM = _pm()
    if pie.uid not in _chain:
        _chain = [pie.uid]
    pos = _chain.index(pie.uid)
    t = _sub_target(pie, prefs.pie_slot)
    if t is not None and t.uid not in _chain[:pos + 1] and (len(_chain) <= pos + 1 or _chain[pos + 1] != t.uid):
        _chain = _chain[:pos + 1] + [t.uid]
    pies = []
    for n, uid in enumerate(_chain):  # each one must still be opened by an item of the one before
        p = PM.find_pie(uid)
        if p is None or (n and not any(getattr(_sub_target(pies[-1], i), "uid", None) == uid
                                       for i in range(len(pies[-1].items)))):
            _chain = _chain[:n]
            break
        pies.append(p)
    return pies


def chain_item(index):
    """(menu, item index) for an item index in the preview (see SUB_STRIDE)."""
    PM = _pm()
    if index is None or index < SUB_STRIDE:
        return None
    k, i = divmod(index, SUB_STRIDE)
    if k - 1 >= len(_chain):
        return None
    p = PM.find_pie(_chain[k - 1])
    return (p, i) if p is not None else None


def build_marking_chain(pie, prefs):
    pies = marking_chain(pie, prefs)
    if len(pies) == 1:
        return build_marking(pie)
    u = unit()
    active = pies.index(pie)
    out = Scene("MARKING")
    out.marking, out.centres, out.links = [], [], []
    prev = None
    for k, p in enumerate(pies):
        sc = build_marking(p)
        if prev is not None:  # beside the item that opens it, to the right of the menu before
            opener = next((e for e in prev.els
                           if getattr(_sub_target(pies[k - 1], e.index % SUB_STRIDE), "uid", None) == p.uid), None)
            ax = max(e.x + e.w for e in prev.els) if prev.els else prev.cx
            ay = opener.y + opener.h / 2 if opener is not None else prev.cy
            left = min((e.x for e in sc.els), default=0.0)
            sc.offset(ax + 2 * u - left, ay)
            if opener is not None:
                start = (opener.x + opener.w, opener.y + opener.h / 2)
                # up to the sub-menu's first item in the way (its left one), else its centre
                hits = [e.x for e in sc.els if e.y <= start[1] <= e.y + e.h and start[0] < e.x < sc.cx]
                out.links.append((start, (min(hits), start[1]) if hits else (sc.cx, sc.cy)))
        if k != active:  # the other menus' items get indices of their own
            base = (k + 1) * SUB_STRIDE
            for e in sc.els:
                e.index += base
            sc.marking = [tuple(b[:8]) + (b[8] + base,) for b in sc.marking]
        out.els.extend(sc.els)
        out.marking.extend(sc.marking)
        out.centres.append((sc.cx, sc.cy, k == active))
        prev = sc
    xs = [v for e in out.els for v in (e.x, e.x + e.w)] or [0.0]
    ys = [v for e in out.els for v in (e.y, e.y + e.h)] or [0.0]
    mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    for e in out.els:
        e.moved(-mx, -my)
    out.marking = [(b[0] - mx, b[1] - my) + tuple(b[2:]) for b in out.marking]
    out.centres = [(x - mx, y - my, a) for x, y, a in out.centres]
    out.links = [((a[0] - mx, a[1] - my), (b[0] - mx, b[1] - my)) for a, b in out.links]
    acx, acy, _a = out.centres[active]
    out.cx, out.cy = acx, acy
    out.w, out.h = max(xs) - min(xs) + 2 * u, max(ys) - min(ys) + 2 * u
    return out


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
        for name in [icon] + [i for _t, i, _c in (_segments(it) or [])]:
            if name and name not in names:
                names.append(name)
    return names


# ---------------------------------------------------------------- drawing a scene

def draw_scene(sc, st, prefs):
    th = _theme()
    s, u = ui_scale(), unit()
    hover = st.hover
    drag = st.drag if st.drag and st.drag.get("active") and not st.drag.get("pan") else None
    src = drag["src"] if drag else None
    selected = prefs.pie_slot
    accent = _rgba(th.wcol_menu_item.inner_sel)
    _font()
    if sc.kind == "BLENDER_PIE":
        _draw_blender_pie(sc, st, th, s, u, hover, src, selected, accent)
    elif sc.kind == "MARKING":
        _draw_marking(sc, st, hover, src, selected, accent, s)
    elif sc.subs:  # a popup menu with its submenus open beside it
        for sub in sc.subs:
            _draw_menu(sub, st, th, s, u, hover, src, selected, accent)
    else:
        _draw_menu(sc, st, th, s, u, hover, src, selected, accent)
    flush_icons()
    if not drag:
        _draw_hover_zone(sc, st, accent, s, u)
    if drag:
        _draw_drop(sc, st, accent, s, u)
        _draw_ghost(sc, st, th, s, u)
        flush_icons()
    _flush()


def _zone_rect(st, el, zone):
    """The part of an item a click there acts on: its icon spot, or the rest (its label). (x, y, w, h)"""
    u, s = unit(), ui_scale()
    if st.scene is not None and st.scene.kind == "BLENDER_PIE" and el.icon:
        icon = (el.x + 0.3 * u - 2 * s, el.y + 2 * s, 20 * s + 0.2 * u, el.h - 4 * s)
    elif el.icon_rect:
        icon = el.icon_rect
    else:
        icon = None
    if icon is not None:  # kept inside the button, so the outline never pokes out above or below it
        y0, y1 = max(icon[1], el.y + 2 * s), min(icon[1] + icon[3], el.y + el.h - 2 * s)
        x0, x1 = max(icon[0], el.x + 2 * s), min(icon[0] + icon[2], el.x + el.w - 2 * s)
        x0, y0, x1, y1 = math.ceil(x0), math.ceil(y0), math.floor(x1), math.floor(y1)  # whole pixels: an even outline
        icon = (x0, y0, x1 - x0, y1 - y0)
    if zone == "icon":
        return icon
    if icon is None:
        return (el.x, el.y, el.w, el.h)
    left = icon[0] + icon[2]
    return (left, el.y + 2 * s, el.x + el.w - left - 2 * s, el.h - 4 * s)


def _draw_hover_zone(sc, st, accent, s, u):
    """While the mouse is on an item: a soft outline around the part a click acts on, so it's clear the
    icon and the label can each be clicked (the hint under the preview says what a click does)."""
    if st.hover is None or not st.hover_zone:
        return
    el = next((e for e in sc.els if e.index == st.hover and e.kind == "item"), None)
    if el is None:
        return
    rect = _zone_rect(st, el, st.hover_zone)
    if rect is None or rect[2] <= 0 or rect[3] <= 0:
        return
    x, y, w, h = rect
    r = min(h / 2, 0.3 * u)
    _round_fill(x, y, w, h, r, accent[:3] + (0.12,))
    _line(_outline_pts(x + 0.5, y + 0.5, w - 1, h - 1, r), accent[:3] + (0.85,), 1.0 * s, closed=True)


def hover_hint(region):
    """What a click does where the mouse is in the preview, for the line under it ("" when it's elsewhere)."""
    st = _canvases.get(region.as_pointer()) if region is not None else None
    if st is None or st.hover is None or st.drag:
        return ""
    el = next((e for e in st.scene.els if e.index == st.hover), None) if st.scene else None
    if el is None:
        return ""
    if el.index >= SUB_STRIDE:
        if chain_item(el.index) is None:
            return "The setting's choices, as the menu shows them"
        sub = chain_item(el.index)[0]
        return f"Part of \"{sub.name}\": to edit it, click its button in the Submenus row above"
    if el.kind != "item":
        return "Click to select it. Drag to move it. Right-click for more"
    if st.hover_zone == "icon":
        return "Click: change the icon"
    if el.index == _prefs().pie_slot:
        return "Click: change what it does (its operator, menu or setting). Drag to move it. Right-click for more"
    return "Click: select it, its settings show beside. Click again: change what it does. Right-click for more"


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
    if el.style.startswith("LABEL"):  # a heading in its own sub-layout: plain text
        col = _tcol(el, _rgba(_theme().wcol_regular.text, alpha))
        _button_content(el, col, u, s, align="LEFT") if el.icon else _text_in(el.x + 0.2 * u, el.y, el.w, el.h, el.text,
                                                                              col, "LEFT")
        return
    if el.segs:
        _draw_segments(el, _theme(), u, s, hovered, alpha)
        return
    if el.style.startswith("BUTTON"):  # a sub-layout in the pie: drawn as a plain button
        tool = _theme().wcol_tool
        sel = hovered or el.depress
        tcol = _rgba(tool.text_sel if sel else tool.text, alpha)
        if el.emboss:
            inner = _rgba(tool.inner_sel if sel else tool.inner, alpha)
            if alert:
                inner = (0.47, 0.07, 0.07, alpha)
            widget_box(el.x, el.y, el.w, el.h, tool.roundness * u * 0.5, inner, _rgba(tool.outline, alpha), wcol=tool,
                       emboss=True, join=el.join)
        else:  # Emboss off: flat, only the icon and text
            if hovered:
                _round_fill(el.x, el.y, el.w, el.h, tool.roundness * u * 0.5, _rgba(tool.inner, 0.5 * alpha))
            if alert:
                tcol = (1.0, 0.35, 0.3, alpha)
        _button_content(el, _tcol(el, tcol), u, s, align="LEFT")  # a pie's buttons keep their text on the left
        return
    inner = _rgba(wcol.inner_sel if (el.depress or hovered) else wcol.inner, alpha)  # a pie's hovered item is active
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
        tx0 = rx + round(0.4 * u)  # Blender's pie items keep their text on the left
        tx, ty = _text_in(tx0, el.y, el.w - 2 * round(0.4 * u), el.h, el.text, tcol, "LEFT")
        if el.key:
            _underline(tx, ty, el.text, el.key, tcol)
    if el.num:
        clip = 0.25 * u
        ncol = tcol[:3] + (tcol[3] * 0.5,)
        _text_in(el.x, el.y, el.w - clip, el.h, el.num, ncol, "RIGHT")


def _name_value(el, tcol, u, arrows=False):
    """A number field's text: its name on the left, its value on the right (just the value with no name)."""
    pad = 0.4 * u + (0.4 * u if arrows else 0)
    if el.text and el.value:
        vw = _text_w(el.value)
        _text_in(el.x + el.w - pad - vw, el.y, vw, el.h, el.value, tcol, "LEFT")
        _text_in(el.x + pad, el.y, el.w, el.h, _clip(el.text, el.w - 2 * pad - vw - 0.4 * u), tcol, "LEFT")
    else:
        _text_in(el.x, el.y, el.w, el.h, el.value or el.text, tcol, "CENTER")


def _chevron(cx, cy, size, color, s):
    _line([(cx - size, cy + size * 0.5), (cx, cy - size * 0.5), (cx + size, cy + size * 0.5)], color, 1.4 * s)


def _draw_segments(el, th, u, s, hovered, alpha):
    """An expanded choice setting: one aligned row of buttons, the chosen one(s) pressed in."""
    radio = th.wcol_radio
    segs = el.segs
    nat = [max(1.0, _text_w(t) + math.ceil(u * (1.5 + (0.25 if i else 0.0))) if t else u) for t, i, _c in segs]
    if abs(sum(nat) - el.w) > 1.5:  # given a width of its own (a dialog, a panel): Blender splits it evenly
        nat = [1.0] * len(segs)
    scale = el.w / max(sum(nat), 1.0)
    x = el.x
    r = radio.roundness * u * 0.5
    for n, ((text, icon, chosen), nw) in enumerate(zip(segs, nat)):
        w = nw * scale if n < len(segs) - 1 else el.x + el.w - x
        join = set(el.join)
        if n > 0:
            join.add("L")
        if n < len(segs) - 1:
            join.add("R")
        inner = _rgba(radio.inner_sel if chosen else radio.inner, alpha)
        widget_box(x + (0 if "L" in join else 1), el.y + 1, w - (0 if "L" in join else 1) - (0 if "R" in join else 1),
                   el.h - 2, r, inner, _rgba(radio.outline, alpha), join=join, wcol=radio, emboss=True)
        tcol = _tcol(el, _rgba(radio.text_sel if chosen else radio.text, alpha))
        room = w - 0.4 * u - (16 * s + 0.2 * u if icon else 0)
        shown = _clip(text, room) if text else ""
        if icon and shown and _text_w(text) > room:  # squeezed: the icon, then what's left of the text after it
            draw_icon(icon, x + 0.2 * u + 8 * s, el.y + el.h / 2, tcol)
            _text_in(x + 0.4 * u + 16 * s, el.y, room, el.h, shown, tcol, "LEFT")
        else:
            _button_content(El(el.index, x, el.y, w, el.h, text=shown, icon=icon), tcol, u, s, align="CENTER")
        x += w


def _button_content(el, tcol, u, s, align="CENTER"):
    if el.icon and el.text:
        draw_icon(el.icon, el.x + 0.2 * u + 8 * s + 2 * s, el.y + el.h / 2, tcol)
        tx0 = el.x + 0.2 * u + 16 * s + 2 * s + 0.4 * u
        text = _clip(el.text, el.x + el.w - tx0 - 0.3 * u)  # Blender cuts text that doesn't fit with "..."
        if align == "CENTER":  # Blender centres a button's text on the button, the icon stays on the left
            tw = _text_w(text)
            tx0 = max(tx0, el.x + (el.w - tw) / 2)
        tx, ty = _text_in(tx0, el.y, el.x + el.w - tx0, el.h, text, tcol, "LEFT")
    elif el.icon:
        draw_icon(el.icon, el.x + el.w / 2, el.y + el.h / 2, tcol)
        return
    else:
        text = _clip(el.text, el.w - 0.8 * u)
        tx, ty = _text_in(el.x + 0.4 * u, el.y, el.w - 0.8 * u, el.h, text, tcol, align)
    if el.key and text == el.text:
        _underline(tx, ty, el.text, el.key, tcol)


def _ring(x, y, w, h, r, t, color, seg=8):
    """A rounded frame t pixels thick, drawn as filled triangles so its corners stay clean (a wide polyline
    leaves spikes where its short arc segments meet), with 1px smooth lines on both edges for anti-aliasing."""
    r = max(0.0, min(r, w / 2, h / 2))
    t = max(0.5, min(t, w / 2, h / 2))
    outer, inner = [], []
    for cx, cy, a0, sx, sy in ((x + w - r, y + r, -90, -1, 1), (x + w - r, y + h - r, 0, -1, -1),
                               (x + r, y + h - r, 90, 1, -1), (x + r, y + r, 180, 1, 1)):
        push = max(0.0, t - r)  # a corner tighter than the frame: the inner corner is square, moved inward
        icx, icy, ir = cx + sx * push, cy + sy * push, max(0.0, r - t)
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            c, sn = math.cos(a), math.sin(a)
            outer.append((cx + r * c, cy + r * sn))
            inner.append((icx + ir * c, icy + ir * sn))
    n = len(outer)
    verts = outer + inner
    idx = []
    for i in range(n):
        j = (i + 1) % n
        idx += [(i, j, n + j), (i, n + j, n + i)]
    _fill(verts, idx, color)
    soft = color[:3] + (color[3] * 0.6,)
    _line(outer, soft, 1.0, closed=True)
    _line(inner, soft, 1.0, closed=True)


def _selection(el, accent, s, u, r=None):
    px = 2 * s
    rr = (r if r is not None else 0.25 * u) + px
    _ring(el.x - 1.5 * px, el.y - 1.5 * px, el.w + 3 * px, el.h + 3 * px, rr + 0.5 * px, px, accent)


def _draw_blender_pie(sc, st, th, s, u, hover, src, selected, accent):
    wcol = th.wcol_pie_menu
    for bx, by, bw, bh in sc.boxes:  # the box of extra items on top
        widget_box(bx, by, bw, bh, th.wcol_box.roundness * u * 0.5, _rgba(th.wcol_box.inner), _rgba(th.wcol_box.outline))
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
    # no direction highlight in the ring: in the editor it only follows the mouse and distracts
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
    centres = sc.centres or [(sc.cx, sc.cy, True)]
    for a, b in sc.links:  # a sub-menu item and the menu it opens
        MM._poly([a, b], colours[5][:3] + (colours[5][3] * 0.6,), max(1.0, look.marking_line_width) * s)
    if st.mouse is not None and hover is not None and look.marking_line_width > 0 and src is None:
        k = hover // SUB_STRIDE  # from the centre of the menu the mouse is on (0: the edited one)
        hx, hy = centres[k - 1][:2] if 0 < k <= len(centres) else (sc.cx, sc.cy)
        MM._poly([(hx, hy), st.mouse], colours[5], look.marking_line_width * s)
    for x, y, _a in centres:
        MM.draw_marking_centre(x, y, look, s, colours)
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
        _draw_sidebar(sc, pie, th, s, u, x, y, w, h)
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
        elif (menu or el.style.startswith("MENU")) and not el.segs:
            _menu_item(el, item_col, th, u, s, hovered, alpha, any_icon)
        else:
            _panel_item(el, th, u, s, hovered, alpha)
        if selected is not None and el.index == selected:
            _selection(el, accent, s, u, 0.2 * u)
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
    tags = {el.index: el.show for el in sc.els if el.kind == "grouptag"}
    for i, x, y, w, h, _t in sc.groups:
        on = i == hover or i == selected
        if not (on or (sc.show_markers and tags.get(i))):
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


def _sidebar_colors():
    space = bpy.context.preferences.themes[0].view_3d.space
    get = lambda name, default: _rgba(getattr(space, name)) if hasattr(space, name) else default
    try:
        pc = space.panelcolors
        header, body = _rgba(pc.header), _rgba(pc.back)
    except AttributeError:
        header, body = (0.19, 0.19, 0.19, 1), (0.16, 0.16, 0.16, 1)
    return dict(region=get("button", (0.11, 0.11, 0.11, 1)), header=header, body=body,
                title=get("button_title", (0.9, 0.9, 0.9, 1)), tab_back=get("tab_back", (0.1, 0.1, 0.1, 1)),
                tab_active=get("tab_active", (0.27, 0.27, 0.27, 1)), tab_outline=get("tab_outline", (0.15, 0.15, 0.15, 1)))


def _draw_sidebar(sc, pie, th, s, u, x, y, w, h):
    """A Sidebar Panel as it looks in the editor's sidebar (N): the region, the panel in it and its tab."""
    c = _sidebar_colors()
    margin = int(0.4 * u)
    tab_w = int(1.1 * u)
    # the sidebar region, with the tab strip on its right
    _rect(x - margin, y - margin, w + 2 * margin + tab_w, h + 2 * margin, c["region"])
    tx = x + w + margin
    _rect(tx, y - margin, tab_w, h + 2 * margin, c["tab_back"])
    name = (pie.tab or "Toolkit").strip() or "Toolkit"
    _font(FONT_POINTS)
    name = _clip(name, h + 2 * margin - 1.2 * u)  # the tab can't be longer than the region
    tw = _text_w(name)
    th_ = tw + 0.8 * u
    ty = y + h - th_ - 0.2 * u + margin
    _round_fill(tx + 2 * s, ty, tab_w - 3 * s, th_, 3 * s, c["tab_active"])
    blf.enable(0, blf.ROTATION)
    blf.rotation(0, -math.pi / 2)  # sidebar tabs read top to bottom
    # turned a quarter clockwise the glyphs grow to the right of the baseline, so it sits left of the middle
    _text(tx + (tab_w - _text_h()) / 2 + pixel(), ty + th_ - 0.4 * u, name, c["title"])
    blf.rotation(0, 0)
    blf.disable(0, blf.ROTATION)
    # the panel: header with its arrow and name, then the body
    r = 4 * s
    _round_fill(x, y, w, h, r, c["body"])
    hx, hy, hw, hh = sc.panel_header
    # the header is the panel's own colour in Blender's sidebar, with the drag dots on its right
    for dx in range(4):
        for dy in range(2):
            _rect(hx + hw - 0.5 * u - dx * 3 * s, hy + hh / 2 - 2 * s + dy * 3 * s, 1.2 * s, 1.2 * s,
                  c["title"][:3] + (0.35,))
    cx, cy, k = hx + 0.55 * u, hy + hh / 2, 0.18 * u
    _line([(cx - k, cy + k * 0.5), (cx, cy - k * 0.5), (cx + k, cy + k * 0.5)], c["title"], 1.2 * s)
    _text_in(hx + 1.1 * u, hy, hw, hh, _clip(pie.name, hw - 2.2 * u), c["title"], "LEFT")


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
    if el.style.startswith("MENU") and el.kind == "item" and getattr(el, "look", "") == "CHECKBOX":
        # on/off settings show as checkboxes in menus, ticked when on
        bx, by = x + 2 * s, el.y + (el.h - 14 * s) / 2
        opt = th.wcol_option
        item = _item_of(el)
        found = _pm().setting_rna(item) if item is not None else None
        on = bool(found and found[1])
        widget_box(bx, by, 14 * s, 14 * s, opt.roundness * 14 * s, _rgba(opt.inner_sel if on else opt.inner, alpha),
                   _rgba(opt.outline, alpha))
        if on:
            _line([(bx + 3 * s, by + 7 * s), (bx + 6 * s, by + 4 * s), (bx + 11 * s, by + 10 * s)],
                  _rgba(opt.text_sel, alpha), 1.6 * s)
        tx0 = x + u + 0.2 * u
    else:
        if el.icon:
            draw_icon(el.icon, x + 8 * s + 2 * s, el.y + el.h / 2, tcol, 1.0)
        tx0 = x + ((u + 0.2 * u) if any_icon or el.icon else 0.2 * u)
    text = _clip(el.text, el.x + el.w - tx0 - (0.9 * u if el.sub else 0.3 * u))
    tx, ty = _text_in(tx0, el.y, el.w, el.h, text, tcol, "LEFT")
    if el.key and text == el.text:
        _underline(tx, ty, el.text, el.key, tcol)
    if el.sub:
        _tria_right(el.x + el.w - 0.6 * u, el.y + el.h / 2, 0.35 * u, tcol)


def _item_of(el):
    """The item an element shows: of the edited menu, or of a menu shown beside it (see SUB_STRIDE)."""
    if el.index >= SUB_STRIDE:
        found = chain_item(el.index)
        if found is None or not 0 <= found[1] < len(found[0].items):
            return None
        return found[0].items[found[1]]
    pie = _cur_pie()
    return pie.items[el.index] if pie is not None and 0 <= el.index < len(pie.items) else None


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
        if el.icon:
            _button_content(el, col, u, s, align="LEFT")
        else:
            _text_in(el.x + 0.2 * u, el.y, el.w, el.h, _clip(el.text, el.w - 0.4 * u), col, "LEFT")
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
        lx = bx + size + 0.3 * u
        _text_in(lx, el.y, el.w, el.h, _clip(el.text, el.x + el.w - lx - 0.2 * u), _tcol(el, _rgba(opt.text, alpha)), "LEFT")
        return
    if style == "SLIDER":
        ns = th.wcol_numslider
        widget_box(bx0, y, bw, h, ns.roundness * u * 0.5, _rgba(ns.inner, alpha), _rgba(ns.outline, alpha), join=j,
                   wcol=ns, emboss=True)
        fill_w = bw * el.frac
        if fill_w > 0.5:
            rr = _corner_radii(ns.roundness * u * 0.5, j | ({"R"} if el.frac < 0.999 else set()))
            _round_fill(bx0, y, fill_w, h, rr, _rgba(ns.item, alpha))
        tcol = _rgba(ns.text, alpha)
        _name_value(el, tcol, u)
        return
    if style == "NUMBER":
        num = th.wcol_num
        widget_box(bx0, y, bw, h, num.roundness * u * 0.5, _hover(_rgba(num.inner, alpha), hovered),
                   _rgba(num.outline, alpha), join=j, wcol=num, emboss=True)
        tcol = _rgba(num.text, alpha)
        _name_value(el, tcol, u, arrows=True)
        return
    if style in ("DROPDOWN", "TEXT"):
        wc = th.wcol_menu if style == "DROPDOWN" else th.wcol_text
        widget_box(bx0, y, bw, h, wc.roundness * u * 0.5, _rgba(wc.inner, alpha), _rgba(wc.outline, alpha), join=j,
                   wcol=wc, emboss=True)
        tcol = _tcol(el, _rgba(wc.text, alpha))
        shown = el.value if el.value else el.text  # a choice setting shows its current choice, a popover its name
        part = El(el.index, el.x, el.y, el.w - (0.8 * u if style == "DROPDOWN" else 0), el.h, text=shown,
                  icon=el.icon)
        if part.text:
            part.text = _clip(part.text, part.w - 0.8 * u - (u if part.icon else 0))
        _button_content(part, tcol, u, s, align="LEFT")
        if style == "DROPDOWN":
            _chevron(el.x + el.w - 0.55 * u, el.y + el.h / 2, 0.22 * u, tcol, s)
        return
    if el.segs:
        _draw_segments(el, th, u, s, hovered, alpha)
        return
    tool = th.wcol_tool
    if style == "FLAT":
        if hovered or el.depress:
            _round_fill(bx0, y, bw, h, tool.roundness * u * 0.5, _rgba(tool.inner_sel if el.depress else tool.inner,
                                                                           0.6 * alpha))
        tcol = _rgba(tool.text, alpha)
        if alert:
            tcol = (1.0, 0.35, 0.3, alpha)
    else:
        base = tool.inner_sel if el.depress else tool.inner
        inner = _rgba(base, alpha) if not alert else (0.47, 0.07, 0.07, alpha)
        widget_box(bx0, y, bw, h, tool.roundness * u * 0.5, _hover(inner, hovered and not el.depress),
                   _rgba(tool.outline, alpha), join=j, wcol=tool, emboss=True)
        tcol = _rgba(tool.text_sel if el.depress else tool.text, alpha)
    _button_content(el, _tcol(el, tcol), u, s, align="CENTER")


def _hover(rgba, on):
    """Blender's hover look: the widget's colour a little lighter (lightness x 1.15)."""
    if not on:
        return rgba
    import colorsys
    h, l, sat = colorsys.rgb_to_hls(*rgba[:3])
    r, g, b = colorsys.hls_to_rgb(h, min(1.0, l * 1.15 + 0.02), sat)
    return (r, g, b, rgba[3])


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
        x = el.x if kind.endswith("before") else el.x + el.w
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
        self.picked = None        # (menu, item) the last click in the preview was on
        self.last_w = None        # the area's width last time it was found
        self.k, self.kc = 1.0, (0, 0)  # the preview's scale (below 1 when it doesn't fit) and its centre
        self.base_w = None
        self.pan = (0.0, 0.0)     # how far the preview was dragged (empty space or middle mouse)
        self.pan_root = None      # the menu the pan belongs to: another one starts in the middle again
        self.can_pan = False      # the menu is bigger than the preview: only then can the view be dragged


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
    for uid in _chain:  # the submenus open beside it show their icons too
        other = _pm().find_pie(uid)
        if other is not None and other.uid != pie.uid:
            st.icons += [n for n in icons_needed(other) if n not in st.icons]
    u = unit()
    try:
        sc = build(pie, prefs)
        st.base_w = sc.w  # its width without hover effects: the scale follows this, so hovering never resizes it
        k = min(1.0, max(0.4, (st.last_w - u) / max(sc.w, 1.0))) if st.last_w else 1.0
        need = int(sc.h * k + 2.2 * u)
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
            row.label(text="", **_pm().icon_kw(name))
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
    _flush()  # drawn before the scissor and scale below
    prefs = _prefs()
    pie = _cur_pie()
    st.pie = pie
    if pie is None or not supported(pie):
        gpu.state.blend_set('NONE')
        return
    sc = build(pie, prefs, st.hover if not st.drag else None)
    root = _chain[0] if sc.kind in ("MARKING", "MENU") and _chain else pie.uid  # a submenu keeps its menu's view
    if st.pan_root != root:
        st.pan, st.pan_root = (0.0, 0.0), root
    # too wide for the area (a small Preferences window): drawn smaller, clicks are mapped back
    st.last_w = x1 - x0
    st.k = min(1.0, max(0.4, (x1 - x0 - unit()) / max(st.base_w or sc.w, 1.0)))
    # the view only moves when the menu doesn't fit, e.g. a big marking menu with many submenus open
    cx, cy = round((x0 + x1) / 2), round((y0 + y1) / 2)
    # the view stays where it was put while submenus open and close under the mouse (a jump would move the
    # items away from it); it only goes back to the middle for another menu or a double-click on empty space
    st.can_pan = st.pan != (0.0, 0.0) or _overflows(sc, st.k, x0, y0, x1, y1, cx, cy)
    sc.offset(cx + st.pan[0], cy + st.pan[1])
    st.kc = (cx, cy)
    if sc.frame and st.mouse is not None:
        fx, fy, fw, fh = sc.frame
        mpad = unit()
        sc.show_markers = fx - mpad <= st.mouse[0] <= fx + fw + mpad and fy - mpad <= st.mouse[1] <= fy + fh + mpad
    if st.drag and st.drag.get("active"):
        sc.show_markers = True
    # End Group markers only for the group the mouse is in (or the selected one), so they don't crowd the menu
    sel = prefs.pie_slot
    dragging = bool(st.drag and st.drag.get("active"))
    for el in sc.els:  # only the group the mouse is in (or the selected one) shows its tag and End Group
        if el.kind == "marker" and el.text == "End Group":
            lo, hi = el.col, el.index
        elif el.kind == "grouptag":
            lo, hi = el.index, el.col
        else:
            continue
        inside = lambda k: k is not None and lo <= k <= hi
        el.show = inside(st.hover) or inside(sel) or dragging
    st.scene = sc
    st.show_remove = pie.menu_type != "PIE" and len(pie.items) > _pm().ITEM_MIN.get(pie.menu_type, 0)
    gpu.state.scissor_test_set(True)
    gpu.state.scissor_set(int(vp[0] + x0), int(vp[1] + y0 - pad), int(x1 - x0), int(y1 - y0 + 2 * pad))
    gpu.matrix.push()
    if st.k < 1.0:
        gpu.matrix.translate((cx, cy))
        gpu.matrix.scale((st.k, st.k))
        gpu.matrix.translate((-cx, -cy))
    draw_scene(sc, st, prefs)
    gpu.matrix.pop()
    gpu.state.scissor_test_set(False)
    gpu.state.blend_set('NONE')
    # make sure the modal that handles clicks and drags is running for this window
    wp = st.window_ptr
    if wp and wp not in _running and time.time() - _last_exit.get(wp, 0.0) > 0.3 and not _stop:
        _running.add(wp)  # claimed now, so only one start is scheduled
        rp = region.as_pointer()
        bpy.app.timers.register(lambda: _start_modal(wp, rp), first_interval=0.01)


def _overflows(sc, k, x0, y0, x1, y1, cx, cy):
    """True when part of the drawn menu (every element, at scale k, centred on cx, cy) falls outside the
    preview area: it is too big, or an open submenu reaches past an edge."""
    rects = [(el.x, el.y, el.w, el.h) for el in sc.els]
    rects += [s.frame for s in sc.subs if s.frame]
    if sc.frame:
        rects.append(sc.frame)
    if not rects:
        return False
    left = min(x for x, _y, _w, _h in rects)
    right = max(x + w for x, _y, w, _h in rects)
    bottom = min(y for _x, y, _w, _h in rects)
    top = max(y + h for _x, y, _w, h in rects)
    return cx + left * k < x0 or cx + right * k > x1 or cy + bottom * k < y0 or cy + top * k > y1


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
        return el.index if el is not None and el.index != src and el.index < SUB_STRIDE else None
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
    # near the left or right end of a stacked item: put it beside that one, on the same row
    edge = min(best.w * 0.25, 3 * unit())
    if best.kind in ("item", "label") and _pm().items_can_share_row(_cur_pie(), best.index) \
            and _pm().pie_items_kind(_cur_pie(), src) not in ("BOX", "BOX_END", "BREAK"):
        if mx < best.x + edge:
            return ("beside_before", best, "x")
        if mx > best.x + best.w - edge:
            return ("beside_after", best, "x")
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
        kind, el, axis = st.drop
        items = list(pie.items)
        moved_row = items[src].same_row
        if src + 1 < len(items) and items[src + 1].same_row and not moved_row:
            items[src + 1].same_row = False  # the item after it starts the row it leaves
        if kind in ("before", "beside_before"):
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
        new = pie.items[prefs.pie_slot]
        if kind == "beside_after":  # on the row of the one before it
            new.same_row = True
        elif kind == "beside_before":  # it takes the row's start, the other one sits beside it
            other = pie.items[prefs.pie_slot + 1]
            new.same_row, other.same_row = other.same_row, True
        elif axis == "y" and n == 1:  # dropped above or below: on a line of its own
            new.same_row = False
    PM._changed()


def _click(context, st, el, zone, win, area, region):
    PM = _pm()
    prefs = _prefs()
    if st.pie is not None and st.pie.menu_type == "MENU" and _menu_sub_target(st.pie, el.index) is None \
            and _choice_rna(st.pie, el.index) is None:
        close_submenus_after(st.pie)
    with context.temp_override(window=win, area=area, region=region):
        # a second click on the same item (the first one only selects it) picks its action
        was_selected = prefs.pie_slot == el.index and st.picked == (st.pie.uid if st.pie else "", el.index)
        st.picked = (st.pie.uid if st.pie else "", el.index)
        if zone == "icon" and el.kind == "item":  # the icon spot: straight to the icons
            prefs.pie_slot = el.index
            bpy.ops.keyops.pie_icon_picker('INVOKE_DEFAULT', slot=el.index)
        elif not was_selected or el.kind in ("marker", "boxhead", "label", "group", "grouptag"):
            prefs.pie_slot = el.index  # first click: select it, its settings show below the preview
        else:  # a selected button clicked again: pick what it does
            bpy.ops.keyops.pie_slot_search('INVOKE_DEFAULT', slot=el.index, scope="ALL")
    PM._redraw_all(context)


def _zone(st, el, mx, my):
    u = unit()
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
        rmx, rmy = mx, my  # region pixels
        if st.k < 1.0:  # the preview is drawn smaller: the mouse in its own (unscaled) coordinates
            mx = st.kc[0] + (mx - st.kc[0]) / st.k
            my = st.kc[1] + (my - st.kc[1]) / st.k

        if st.drag is not None:
            return self._dragging(context, event, st, area, reg, mx, my)

        if event.type == 'MOUSEMOVE' or event.type == 'INBETWEEN_MOUSEMOVE':
            # over a marker row (hidden under the preview): keep the mouse from Blender, so its colour swatch
            # never shows a tooltip
            band = st.pad
            if x0 <= rmx <= x1 and (y0 - band <= rmy < y0 or y1 < rmy <= y1 + band):
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
        if st.can_pan and ((event.type == 'MIDDLEMOUSE' and event.value == 'PRESS') or
                           (event.type == 'LEFTMOUSE' and event.value == 'PRESS' and _item_under(st, mx, my) is None)):
            st.drag = {"pan": True, "start": (rmx, rmy), "from": st.pan, "active": True, "src": None}
            try:
                context.window.cursor_modal_set('SCROLL_XY')
            except (AttributeError, ReferenceError, TypeError):
                pass
            return {'RUNNING_MODAL'}
        if st.can_pan and event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN'}:
            # scroll the view: wheel up/down, Shift or Ctrl + wheel sideways, or a trackpad in any direction
            k = st.k or 1.0
            if event.type == 'TRACKPADPAN':
                dx, dy = event.mouse_x - event.mouse_prev_x, event.mouse_y - event.mouse_prev_y
            else:
                step = 2.5 * unit() * (1 if event.type == 'WHEELUPMOUSE' else -1)
                dx, dy = (step, 0.0) if (event.shift or event.ctrl) else (0.0, -step)
            st.pan = (st.pan[0] + dx / k, st.pan[1] + dy / k)
            reg.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'HOME' and event.value == 'PRESS':
            st.pan = (0.0, 0.0)  # Home: back to the middle (only on request, the view never moves by itself)
            reg.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value in {'PRESS', 'DOUBLE_CLICK'}:
            el = _item_under(st, mx, my)
            if el is None:
                return {'PASS_THROUGH'}
            if el.index >= SUB_STRIDE:  # a submenu shown beside it: only for looking, its button above edits it
                return {'RUNNING_MODAL'}
            zone = _zone(st, el, mx, my)
            st.drag = {"src": el.index, "start": (mx, my), "grab": (mx - el.x, my - el.y), "active": False,
                       "zone": zone, "el": el, "area": area.as_pointer()}
            return {'RUNNING_MODAL'}
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':  # everything about the item, in one menu
            el = _item_under(st, mx, my)
            if el is None:
                return {'PASS_THROUGH'}
            slot = el.index
            if slot >= SUB_STRIDE:  # a submenu shown beside it: never switch menus from the preview
                return {'RUNNING_MODAL'}
            with context.temp_override(window=context.window, area=area, region=reg):
                bpy.ops.keyops.item_options('INVOKE_DEFAULT', slot=slot)
            reg.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type in {'DEL', 'X'} and event.value == 'PRESS' and st.hover is not None and st.show_remove \
                and st.hover < SUB_STRIDE \
                and not (event.ctrl or event.alt or event.shift):
            with context.temp_override(window=context.window, area=area, region=reg):
                bpy.ops.keyops.menu_item_remove(slot=st.hover)
            st.hover = None
            reg.tag_redraw()
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}

    def _dragging(self, context, event, st, area, reg, mx, my):
        d = st.drag
        if d.get("pan"):  # moving the view of the preview
            if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
                rx, ry = event.mouse_region_x, event.mouse_region_y
                k = st.k or 1.0
                st.pan = (d["from"][0] + (rx - d["start"][0]) / k, d["from"][1] + (ry - d["start"][1]) / k)
                reg.tag_redraw()
            elif event.value == 'RELEASE' and event.type in {'LEFTMOUSE', 'MIDDLEMOUSE'}:
                st.drag = None
                try:
                    context.window.cursor_modal_restore()
                except (AttributeError, ReferenceError, TypeError):
                    pass
            return {'RUNNING_MODAL'}
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            st.mouse = (mx, my)
            if not d["active"] and math.hypot(mx - d["start"][0], my - d["start"][1]) > DRAG_START * ui_scale():
                if st.scene is not None:
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
