"""First-run welcome screen, drawn over the 3D Viewport like an app splash.

Blender's own dialogs always add a Cancel button and plain popups close when
the mouse leaves them, so the welcome screen is a small modal operator that
draws its own card: logo, what Key Ops does, three keyboard presets and one
Get Started button.
"""

import os

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from .. import features as F
from ..utils.pref_utils import get_addon_name, get_keyops_prefs
from .branding import BRAND_DIR, version_text

ACCENT = (0.949, 0.294, 0.376, 1.0)       # logo pink
ACCENT_SOFT = (0.949, 0.294, 0.376, 0.16)
CARD = (0.107, 0.107, 0.107, 1.0)       # matches the dark boxes in Preferences
CARD_EDGE = (0.22, 0.22, 0.22, 1.0)
TILE = (0.155, 0.155, 0.155, 1.0)
TILE_HOVER = (0.195, 0.195, 0.195, 1.0)
TEXT = (0.92, 0.92, 0.93, 1.0)
BUTTON = (0.70, 0.31, 0.42, 1.0)          # calmer brand rose (logo gradient, toned down)
BUTTON_HOVER = (0.78, 0.36, 0.48, 1.0)
DIM = (0.62, 0.62, 0.65, 1.0)

PRESETS = (
    ("ESSENTIALS", "Essentials", "Tools, panels and menus.", "No shortcuts.", "Recommended"),
    ("BLENDER_PLUS", "Blender+", "Shortcuts and pies only on", "keys Blender leaves free.", ""),
    ("INDUSTRY", "Industry", "Maya-style keys: Alt navigation,", "D pivot and Delete.", ""),
)
# Shown once after each update: four highlights with a picture each, and one line for the rest.
# Pictures are 512 x 256 PNGs in icons/whats_new.
WHATS_NEW = (
    ("Build your own menus", "Pies, popup menus, panels and macros, with icons, rows and boxes.", "menus.png"),
    ("Marking menus", "Flick through pie menus without waiting, in their own clean look.", "marking.png"),
    ("Border and Element modes", "Pick whole borders or mesh islands, next to Vertex, Edge and Face.", "modes.png"),
    ("Make Trim", "Turn edges into L-shaped trims with trim-sheet UVs, in one click.", "trim.png"),
)
WHATS_NEW_HEADLINE = "A completely new design: Features, Custom Menus and Shortcuts, rebuilt from the ground up."
WHATS_NEW_MORE = "Also new: Resample Edges, Clean Up, and every feature quiet until you turn it on."
WHATS_NEW_DIR = os.path.join(os.path.dirname(__file__), "..", "icons", "whats_new")

HIGHLIGHTS = (
    ("Modeling tools", "Merge, fast loop cut, cutter,", "bevel, mirror and more."),
    ("Custom menus", "Pies, popups, panels, macros.", "Every one is editable."),
    ("N-panel toolkit", "Object, mesh and pipeline", "tools in one place."),
)

_SEEN_FILE = "seen.json"


def _seen_path():
    from ..settings_store import user_dir
    return os.path.join(user_dir(), _SEEN_FILE)


def read_seen():
    """Which welcome and What's New screens were shown. Kept in the add-on's own user folder, so it holds
    even when Blender's preferences aren't saved."""
    import json
    path = _seen_path()
    if not os.path.isfile(path):  # first run; checked up front so a debugger doesn't stop on the error
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def mark_seen(p):
    """The welcome screen and this version's What's New are shown: never again for this version."""
    import json
    p.welcome_version = max(p.welcome_version, F.WELCOME_VERSION)
    p.last_seen_version = version_text()
    p.show_whats_new = False
    try:
        with open(_seen_path(), "w", encoding="utf-8") as fh:
            json.dump({"welcome_version": p.welcome_version, "last_seen_version": p.last_seen_version}, fh)
    except OSError:
        pass


_shader = None


def _rect_shader():
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader


def _outline(x, y, w, h, r, color, width=2.0, segments=10):
    import math
    r = min(r, w / 2, h / 2)
    pts = []
    for cx, cy, start in ((x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180), (x + w - r, y + r, 270)):
        for i in range(segments + 1):
            a = math.radians(start + 90 * i / segments)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    sh = _rect_shader()
    batch = batch_for_shader(sh, 'LINE_LOOP', {"pos": pts})
    gpu.state.line_width_set(width)
    sh.bind()
    sh.uniform_float("color", color)
    batch.draw(sh)
    gpu.state.line_width_set(1.0)


def _rounded(x, y, w, h, r, color, segments=10):
    import math
    r = min(r, w / 2, h / 2)
    corners = ((x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180), (x + w - r, y + r, 270))
    pts = []
    for cx, cy, start in corners:
        for i in range(segments + 1):
            a = math.radians(start + 90 * i / segments)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    center = (x + w / 2, y + h / 2)
    verts = [center] + pts
    idx = [(0, i, i + 1) for i in range(1, len(pts))] + [(0, len(pts), 1)]
    sh = _rect_shader()
    batch = batch_for_shader(sh, 'TRIS', {"pos": verts}, indices=idx)
    sh.bind()
    sh.uniform_float("color", color)
    batch.draw(sh)


def _image(texture, x, y, w, h):
    sh = gpu.shader.from_builtin('IMAGE')
    batch = batch_for_shader(sh, 'TRI_FAN', {
        "pos": ((x, y), (x + w, y), (x + w, y + h), (x, y + h)),
        "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1))})
    sh.bind()
    sh.uniform_sampler("image", texture)
    batch.draw(sh)


def _wrap(text, size, width):
    """Lines of text that fit in width at this size."""
    blf.size(0, size)
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and blf.dimensions(0, trial)[0] > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def _text(x, y, text, size, color, center=False):
    blf.size(0, size)
    if center:
        x -= blf.dimensions(0, text)[0] / 2
    blf.position(0, x, y, 0)
    blf.color(0, *color)
    blf.draw(0, text)


_overlay = {"handle": None}  # the welcome screen's draw handler, while it is open


def remove_overlay():
    if _overlay["handle"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_overlay["handle"], 'WINDOW')
        _overlay["handle"] = None


class KEYOPS_OT_welcome(bpy.types.Operator):
    bl_idname = "keyops.welcome"
    bl_label = "Welcome to Key Ops"
    bl_description = "Welcome screen: pick which shortcuts Key Ops starts with"
    bl_options = {'INTERNAL'}

    whats_new: bpy.props.BoolProperty(options={'SKIP_SAVE'}) # type: ignore

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return {'CANCELLED'}
        p = get_keyops_prefs()
        mark_seen(p)  # shown once: as soon as it opens, even if Blender is closed before Got It
        self.area = context.area
        self.region = next(r for r in context.area.regions if r.type == 'WINDOW')
        self.choice = "ESSENTIALS"
        self.hover = None
        self.mouse = (0, 0)
        self.hit = {}
        self.image = None
        self.texture = None
        path = os.path.join(BRAND_DIR, "logo_wide.png")
        try:
            self.image = bpy.data.images.load(path, check_existing=False)
            self.image.name = ".Key Ops Welcome Logo"
            self.texture = gpu.texture.from_image(self.image)
        except Exception:
            self.texture = None
        self.pictures = {}  # What's New pictures: file -> (image, texture)
        if self.whats_new:
            for _title, _desc, name in WHATS_NEW:
                try:
                    img = bpy.data.images.load(os.path.join(WHATS_NEW_DIR, name), check_existing=False)
                    img.name = f".Key Ops What's New {name}"
                    self.pictures[name] = (img, gpu.texture.from_image(img))
                except Exception:
                    pass
        self.handle = bpy.types.SpaceView3D.draw_handler_add(self.draw_overlay, (), 'WINDOW', 'POST_PIXEL')
        _overlay["handle"] = self.handle
        context.window_manager.modal_handler_add(self)
        self.area.tag_redraw()
        return {'RUNNING_MODAL'}

    # ---------------------------------------------------------------- input
    def modal(self, context, event):
        x = event.mouse_x - self.region.x
        y = event.mouse_y - self.region.y
        self.mouse = (x, y)
        old = self.hover
        self.hover = next((k for k, (rx, ry, rw, rh) in self.hit.items() if rx <= x <= rx + rw and ry <= y <= ry + rh), None)
        if old != self.hover:
            self.area.tag_redraw()
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if self.hover == "START":
                return self.finish(context)
            if not self.whats_new and self.hover in {p[0] for p in PRESETS}:
                self.choice = self.hover
                self.area.tag_redraw()
        elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            return self.finish(context)
        return {'RUNNING_MODAL'}  # the welcome screen stays until Get Started

    def finish(self, context):
        remove_overlay()
        if self.image is not None:
            bpy.data.images.remove(self.image)
        for img, _tex in self.pictures.values():
            bpy.data.images.remove(img)
        self.pictures = {}
        self.area.tag_redraw()
        p = get_keyops_prefs()
        if self.whats_new:
            return {'FINISHED'}
        p.shortcut_style = self.choice
        F.apply_style(self.choice)

        def open_prefs():
            try:
                bpy.ops.preferences.addon_show(module=get_addon_name())
            except RuntimeError:
                pass
            return None
        bpy.app.timers.register(open_prefs, first_interval=0.1)
        return {'FINISHED'}

    # ---------------------------------------------------------------- drawing
    def draw_overlay(self):
        try:
            self.area
        except ReferenceError:  # a file was opened while the screen was up: Blender ended the operator
            remove_overlay()
            return
        if bpy.context.area != self.area:
            return
        if self.whats_new:
            return self.draw_whats_new()
        s = bpy.context.preferences.system.ui_scale
        # corner radius follows the user's theme, like Blender's own popups and buttons
        ui = bpy.context.preferences.themes[0].user_interface
        unit = 20 * s  # one widget unit
        r_card = ui.wcol_menu_back.roundness * unit
        r_tile = ui.wcol_regular.roundness * unit * 0.75
        rw, rh = self.region.width, self.region.height
        gpu.state.blend_set('ALPHA')

        w, h = 700 * s, 560 * s
        x0, y0 = (rw - w) / 2, (rh - h) / 2
        _rounded(x0 - 1, y0 - 1, w + 2, h + 2, r_card + 1, CARD_EDGE)
        _rounded(x0, y0, w, h, r_card, CARD)
        top = y0 + h
        cx = x0 + w / 2

        # logo
        lw, lh = 330 * s, 110 * s
        ly = top - 36 * s - lh
        if self.texture is not None:
            sh = gpu.shader.from_builtin('IMAGE')
            batch = batch_for_shader(sh, 'TRI_FAN', {
                "pos": ((cx - lw / 2, ly), (cx + lw / 2, ly), (cx + lw / 2, ly + lh), (cx - lw / 2, ly + lh)),
                "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1))})
            sh.bind()
            sh.uniform_sampler("image", self.texture)
            batch.draw(sh)
        else:
            _text(cx, ly + 40 * s, "Key Ops", 48 * s, TEXT, center=True)
        y = ly - 30 * s
        _text(cx, y, "Modeling tools, menus and shortcuts for Blender", 15 * s, DIM, center=True)

        # highlights
        y -= 52 * s
        col_w = (w - 80 * s) / 3
        for i, (title, l1, l2) in enumerate(HIGHLIGHTS):
            hx = x0 + 40 * s + col_w * i + col_w / 2
            _rounded(hx - 3 * s, y + 22 * s, 6 * s, 6 * s, 3 * s, ACCENT)
            _text(hx, y, title, 14 * s, TEXT, center=True)
            _text(hx, y - 20 * s, l1, 12 * s, DIM, center=True)
            _text(hx, y - 37 * s, l2, 12 * s, DIM, center=True)

        # presets
        y -= 84 * s
        _text(x0 + 40 * s, y, "How should Key Ops use your keyboard?", 14 * s, TEXT)
        y -= 16 * s
        tile_h = 96 * s
        gap = 12 * s
        tile_w = (w - 80 * s - 2 * gap) / 3
        self.hit = {}
        for i, (sid, name, d1, d2, badge) in enumerate(PRESETS):
            tx = x0 + 40 * s + i * (tile_w + gap)
            ty = y - tile_h
            selected = sid == self.choice
            fill = (0.25, 0.14, 0.165, 1.0) if selected else (TILE_HOVER if self.hover == sid else TILE)
            _rounded(tx, ty, tile_w, tile_h, r_tile, fill)
            if selected:
                _outline(tx, ty, tile_w, tile_h, r_tile, ACCENT, width=2.0 * s)
            _text(tx + 14 * s, ty + tile_h - 28 * s, name, 15 * s, TEXT)
            if badge:
                blf.size(0, 11 * s)
                _text(tx + tile_w - 14 * s - blf.dimensions(0, badge)[0], ty + tile_h - 27 * s, badge, 11 * s, ACCENT)
            _text(tx + 14 * s, ty + tile_h - 52 * s, d1, 12 * s, DIM)
            _text(tx + 14 * s, ty + tile_h - 69 * s, d2, 12 * s, DIM)
            self.hit[sid] = (tx, ty, tile_w, tile_h)

        y -= tile_h + 30 * s
        _text(cx, y, "Every shortcut and menu can be turned on or off later in Preferences.", 12 * s, DIM, center=True)

        # Get Started
        bw, bh = 220 * s, 44 * s
        bx, by = cx - bw / 2, y0 + 30 * s
        _rounded(bx, by, bw, bh, r_tile, BUTTON_HOVER if self.hover == "START" else BUTTON)
        _text(cx, by + bh / 2 - 6 * s, "Get Started", 16 * s, (1, 1, 1, 1), center=True)
        self.hit["START"] = (bx, by, bw, bh)

        _text(x0 + 18 * s, y0 + 12 * s, f"v{version_text()}", 11 * s, DIM)
        gpu.state.blend_set('NONE')

    def draw_whats_new(self):
        rw, rh = self.region.width, self.region.height
        s = bpy.context.preferences.system.ui_scale
        w, h = 820, 806  # at scale 1; shrink to fit small viewports
        s *= min(1.0, rw * 0.95 / (w * s), rh * 0.95 / (h * s))
        ui = bpy.context.preferences.themes[0].user_interface
        unit = 20 * s
        r_card = ui.wcol_menu_back.roundness * unit
        r_tile = ui.wcol_regular.roundness * unit * 0.75
        gpu.state.blend_set('ALPHA')

        w, h = w * s, h * s
        x0, y0 = (rw - w) / 2, (rh - h) / 2
        _rounded(x0 - 1, y0 - 1, w + 2, h + 2, r_card + 1, CARD_EDGE)
        _rounded(x0, y0, w, h, r_card, CARD)
        cx, top = x0 + w / 2, y0 + h

        lw, lh = 210 * s, 70 * s
        ly = top - 26 * s - lh
        if self.texture is not None:
            _image(self.texture, cx - lw / 2, ly, lw, lh)
        y = ly - 30 * s
        _text(cx, y, f"What's new in Key Ops {version_text()}", 17 * s, TEXT, center=True)
        y -= 26 * s
        _text(cx, y, WHATS_NEW_HEADLINE, 13 * s, ACCENT, center=True)

        # two by two: picture, title, a short line
        pad, gap = 40 * s, 24 * s
        tile_w = (w - 2 * pad - gap) / 2
        pic_h = tile_w / 2
        tile_h = pic_h + 66 * s
        y -= 26 * s
        for i, (title, desc, name) in enumerate(WHATS_NEW):
            col, row = i % 2, i // 2
            tx = x0 + pad + col * (tile_w + gap)
            ty = y - (row + 1) * tile_h - row * gap * 0.6
            pic = self.pictures.get(name)
            py = ty + tile_h - pic_h
            if pic is not None:
                _rounded(tx - 1, py - 1, tile_w + 2, pic_h + 2, r_tile, CARD_EDGE)
                _image(pic[1], tx, py, tile_w, pic_h)
            else:
                _rounded(tx, py, tile_w, pic_h, r_tile, TILE)
            _text(tx, py - 22 * s, title, 14 * s, TEXT)
            for k, line in enumerate(_wrap(desc, 12 * s, tile_w)[:2]):
                _text(tx, py - 41 * s - k * 16 * s, line, 12 * s, DIM)

        more_y = y - 2 * tile_h - gap * 0.6 - 30 * s
        _text(cx, more_y, WHATS_NEW_MORE, 12 * s, DIM, center=True)

        bw, bh = 180 * s, 40 * s
        bx, by = cx - bw / 2, y0 + 26 * s
        _rounded(bx, by, bw, bh, r_tile, BUTTON_HOVER if self.hover == "START" else BUTTON)
        _text(cx, by + bh / 2 - 6 * s, "Got It", 15 * s, (1, 1, 1, 1), center=True)
        self.hit = {"START": (bx, by, bw, bh)}
        gpu.state.blend_set('NONE')
