"""Generates the menu type icons in icons/: menu_pie, menu_stack, menu_sticky, menu_modal, menu_macro.

These stand in for Blender icons that did not say much about the menu type (a plain circle for
a pie, a pin for a sticky key). They are flat, light grey line icons so they sit well next to
Blender's own icons in the same lists. Shapes are signed distance functions, supersampled for
smooth edges, written as 64x64 RGBA PNGs with only the standard library.

Run with any Python 3: python make_menu_type_icons.py
"""
import math
import os
import struct
import zlib

SIZE = 64
SAMPLES = 4  # per axis, per pixel
COLOR = (229, 229, 229)  # same as Blender's icons
DIM = 0.5  # opacity of the secondary parts of an icon
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "icons")


# ---- shapes: each returns a signed distance (negative inside) -------------------------------

def circle(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) - r


def ring(cx, cy, r, width):
    return lambda x, y: abs(math.hypot(x - cx, y - cy) - r) - width / 2


def segment(ax, ay, bx, by, width):
    """A line with round caps."""
    def d(x, y):
        px, py, vx, vy = x - ax, y - ay, bx - ax, by - ay
        t = max(0.0, min(1.0, (px * vx + py * vy) / (vx * vx + vy * vy)))
        return math.hypot(px - vx * t, py - vy * t) - width / 2
    return d


def round_rect(x0, y0, x1, y1, r):
    cx, cy, hx, hy = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 - r, (y1 - y0) / 2 - r
    def d(x, y):
        qx, qy = abs(x - cx) - hx, abs(y - cy) - hy
        return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r
    return d


def outline(shape, width):
    return lambda x, y: abs(shape(x, y) + width / 2) - width / 2


def polygon(*pts):
    """A convex polygon, points in either winding order."""
    edges = list(zip(pts, pts[1:] + pts[:1]))
    def d(x, y):
        dist = min(segment(ax, ay, bx, by, 0)(x, y) for (ax, ay), (bx, by) in edges)
        inside = all((bx - ax) * (y - ay) - (by - ay) * (x - ax) >= 0 for (ax, ay), (bx, by) in edges) or \
            all((bx - ax) * (y - ay) - (by - ay) * (x - ax) <= 0 for (ax, ay), (bx, by) in edges)
        return -dist if inside else dist
    return d


def cut(shape, *holes):
    return lambda x, y: max(shape(x, y), *(-h(x, y) for h in holes))


def arc(cx, cy, r, width, start, end):
    """Part of a ring from angle start to end (degrees, 0 = right, counterclockwise, y up)."""
    def d(x, y):
        a = math.degrees(math.atan2(cy - y, x - cx)) % 360
        if (a - start) % 360 <= (end - start) % 360:
            return abs(math.hypot(x - cx, y - cy) - r) - width / 2
        ends = [(cx + r * math.cos(math.radians(t)), cy - r * math.sin(math.radians(t))) for t in (start, end)]
        return min(math.hypot(x - ex, y - ey) for ex, ey in ends) - width / 2
    return d


# ---- the icons: lists of (shape, opacity) --------------------------------------------------

def pie():
    """Blender's own pie menu icon, redrawn smooth: eight short horizontal dashes in a ring.
    Sizes and positions are measured from Blender's 16px original (4 units per pixel)."""
    centres = [(0, -21.6), (-15.15, -12.8), (-20.75, 0)]  # top, top left, left: mirrored to all 8
    dashes = []
    for dx, dy in centres:
        for sx in ((1,) if dx == 0 else (1, -1)):
            for sy in ((1,) if dy == 0 else (1, -1)):
                cx, cy = 32 + sx * dx, 32 + sy * dy
                dashes.append((round_rect(cx - 6, cy - 2.4, cx + 6, cy + 2.4, 2.4), 1.0))
    return dashes


def stack():
    """Three stacked items with an arrow going from the last back to the first."""
    return [(round_rect(4, 7, 36, 17, 3), 1.0),
            (round_rect(4, 27, 36, 37, 3), DIM),
            (round_rect(4, 47, 36, 57, 3), DIM),
            (arc(44, 32, 17, 5, 270, 90), 1.0),
            (polygon((36, 15), (47, 6), (47, 24)), 1.0)]


def sticky():
    """A key with a down arrow (held) and an up arrow (released)."""
    return [(outline(round_rect(4, 4, 60, 60, 11), 5), 1.0),
            (segment(23, 16, 23, 36, 5), 1.0),
            (polygon((14, 33), (32, 33), (23, 46)), 1.0),
            (segment(41, 48, 41, 28, 5), DIM),
            (polygon((32, 31), (50, 31), (41, 18)), DIM)]


def modal():
    """A slider with arrows above it: move the mouse to change a value."""
    return [(segment(7, 46, 57, 46, 4), DIM),
            (segment(7, 46, 30, 46, 5), 1.0),
            (circle(30, 46, 8.5), 1.0),
            (segment(16, 17, 48, 17, 4), 1.0),
            (polygon((5, 17), (17, 8), (17, 26)), 1.0),
            (polygon((59, 17), (47, 8), (47, 26)), 1.0)]


def macro():
    """A list of steps with a play button: run them one after another."""
    return [(segment(7, 12, 46, 12, 6), 1.0),
            (segment(7, 27, 46, 27, 6), 1.0),
            (segment(7, 42, 26, 42, 6), 1.0),
            (polygon((34, 34), (34, 60), (58, 47)), 1.0)]


ICONS = {"menu_pie": pie, "menu_stack": stack, "menu_sticky": sticky, "menu_modal": modal, "menu_macro": macro}


# ---- rendering ------------------------------------------------------------------------------

def render(layers):
    rows = []
    for py in range(SIZE):
        row = bytearray([0])  # PNG filter: none
        for px in range(SIZE):
            total = 0.0
            for sy in range(SAMPLES):
                for sx in range(SAMPLES):
                    x, y = px + (sx + 0.5) / SAMPLES, py + (sy + 0.5) / SAMPLES
                    total += max((op for shape, op in layers if shape(x, y) <= 0), default=0.0)
            row += bytes(COLOR) + bytes([round(255 * total / SAMPLES ** 2)])
        rows.append(bytes(row))
    return b"".join(rows)


def write_png(path, pixels):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(pixels, 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


if __name__ == "__main__":
    for name, pixels in ((name, render(make())) for name, make in ICONS.items()):
        path = os.path.normpath(os.path.join(OUT, name + ".png"))
        write_png(path, pixels)
        print("wrote", path)
