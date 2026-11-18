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
    ("INDUSTRY", "Industry", "Maya-style keys: Alt navigation,", "D pivot, Delete. Like Key Ops 0.2.", ""),
)
# Shown once after each update. Keep it to a handful of short, user-facing highlights.
WHATS_NEW = (
    ("Quiet by default", "Turn each feature and its shortcuts on or off. Nothing takes over your keys unless you choose."),
    ("Editable pie menus", "Every pie is a preset you can change: search actions, pick icons, set keys, or make your own."),
    ("Cleaner preferences", "Features, Pie Menus and Shortcuts tabs, with a Docs link on every feature."),
    ("Shortcut cheat sheet", "The ? button in the Toolkit panel lists the Key Ops shortcuts active in your mode."),
    ("Rebind is now opt-in", "The old Rebind options are Key Ops shortcuts that never edit your own keymap."),
)

HIGHLIGHTS = (
    ("Modeling tools", "Merge, fast loop cut, cutter,", "bevel, mirror and more."),
    ("Pie menus", "Add objects, modifiers, cursor.", "Every pie is editable."),
    ("N-panel toolkit", "Object, mesh and pipeline", "tools in one place."),
)

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


def _text(x, y, text, size, color, center=False):
    blf.size(0, size)
    if center:
        x -= blf.dimensions(0, text)[0] / 2
    blf.position(0, x, y, 0)
    blf.color(0, *color)
    blf.draw(0, text)


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
        p.welcome_version = F.WELCOME_VERSION  # shown once
        p.last_seen_version = version_text()   # the What's New for this version is seen too
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
        self.handle = bpy.types.SpaceView3D.draw_handler_add(self.draw_overlay, (), 'WINDOW', 'POST_PIXEL')
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
        bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
        if self.image is not None:
            bpy.data.images.remove(self.image)
        self.area.tag_redraw()
        p = get_keyops_prefs()
        if self.whats_new:
            p.show_whats_new = False
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
        _rounded(0, 0, rw, rh, 0, (0.0, 0.0, 0.0, 0.55))

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
        _text(cx, y, "Modeling tools, pie menus and shortcuts for Blender", 15 * s, DIM, center=True)

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
        _text(cx, y, "Every shortcut and pie menu can be turned on or off later in Preferences.", 12 * s, DIM, center=True)

        # Get Started
        bw, bh = 220 * s, 44 * s
        bx, by = cx - bw / 2, y0 + 30 * s
        _rounded(bx, by, bw, bh, r_tile, BUTTON_HOVER if self.hover == "START" else BUTTON)
        _text(cx, by + bh / 2 - 6 * s, "Get Started", 16 * s, (1, 1, 1, 1), center=True)
        self.hit["START"] = (bx, by, bw, bh)

        _text(x0 + 18 * s, y0 + 12 * s, f"v{version_text()}", 11 * s, DIM)
        gpu.state.blend_set('NONE')

    def draw_whats_new(self):
        s = bpy.context.preferences.system.ui_scale
        ui = bpy.context.preferences.themes[0].user_interface
        unit = 20 * s
        r_card = ui.wcol_menu_back.roundness * unit
        r_tile = ui.wcol_regular.roundness * unit * 0.75
        rw, rh = self.region.width, self.region.height
        gpu.state.blend_set('ALPHA')
        _rounded(0, 0, rw, rh, 0, (0.0, 0.0, 0.0, 0.55))

        row_h = 50 * s
        w, h = 640 * s, (250 + 0) * s + row_h * len(WHATS_NEW)
        x0, y0 = (rw - w) / 2, (rh - h) / 2
        _rounded(x0 - 1, y0 - 1, w + 2, h + 2, r_card + 1, CARD_EDGE)
        _rounded(x0, y0, w, h, r_card, CARD)
        cx, top = x0 + w / 2, y0 + h

        lw, lh = 240 * s, 80 * s
        ly = top - 28 * s - lh
        if self.texture is not None:
            sh = gpu.shader.from_builtin('IMAGE')
            batch = batch_for_shader(sh, 'TRI_FAN', {
                "pos": ((cx - lw / 2, ly), (cx + lw / 2, ly), (cx + lw / 2, ly + lh), (cx - lw / 2, ly + lh)),
                "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1))})
            sh.bind()
            sh.uniform_sampler("image", self.texture)
            batch.draw(sh)
        y = ly - 30 * s
        _text(cx, y, f"What's new in Key Ops {version_text()}", 16 * s, TEXT, center=True)

        y -= 26 * s
        for title, desc in WHATS_NEW:
            y -= row_h
            _rounded(x0 + 44 * s, y + 31 * s, 6 * s, 6 * s, 3 * s, ACCENT)
            _text(x0 + 60 * s, y + 28 * s, title, 14 * s, TEXT)
            _text(x0 + 60 * s, y + 9 * s, desc, 12 * s, DIM)

        bw, bh = 180 * s, 40 * s
        bx, by = cx - bw / 2, y0 + 26 * s
        _rounded(bx, by, bw, bh, r_tile, BUTTON_HOVER if self.hover == "START" else BUTTON)
        _text(cx, by + bh / 2 - 6 * s, "Got It", 15 * s, (1, 1, 1, 1), center=True)
        self.hit = {"START": (bx, by, bw, bh)}
        gpu.state.blend_set('NONE')
