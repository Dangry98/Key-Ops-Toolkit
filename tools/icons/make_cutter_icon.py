"""Generates ops.object.cutter_tool.dat, the Cutter Tool toolbar icon.

Blender toolbar icons are triangle meshes in a 256x256 space (uint8 coords, y up) with
per-vertex RGBA colors: b"VCO" + version + width, height, x, y, then all coords, then all colors.

Design follows Blender's own tool icons: a thin white wire cube with the "action" in the mint
accent color, here a square cutter drawn on the front face.

Run with: blender -b --factory-startup --python make_cutter_icon.py
"""
import os
import struct

WHITE = (229, 229, 229, 255)  # same as Blender's tool icons
MINT = (117, 255, 175, 255)
STROKE = 5.5

# Wire cube: front face, and its back face offset up/right
FX0, FY0, FX1, FY1 = 48, 40, 168, 160
DX, DY = 44, 44
CUBE = [
    ((FX0, FY0), (FX1, FY0), (FX1, FY1), (FX0, FY1), (FX0, FY0)),
    ((FX0, FY1), (FX0 + DX, FY1 + DY), (FX1 + DX, FY1 + DY), (FX1, FY1)),
    ((FX1, FY0), (FX1 + DX, FY0 + DY), (FX1 + DX, FY1 + DY)),
]

# The cutter: a square drawn on the front face, nothing more so it stays readable at 32px
HX0, HY0, HX1, HY1 = 74, 66, 142, 134
HOLE = [
    ((HX0, HY0), (HX1, HY0), (HX1, HY1), (HX0, HY1), (HX0, HY0)),
]


def stroke_polyline(points, width):
    """Quads per segment with square caps, so corners overlap into clean joints."""
    tris = []
    h = width * 0.5
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        dx, dy = x1 - x0, y1 - y0
        length = (dx * dx + dy * dy) ** 0.5
        if length == 0:
            continue
        ux, uy = dx / length, dy / length
        nx, ny = -uy * h, ux * h
        ax, ay = x0 - ux * h, y0 - uy * h
        bx, by = x1 + ux * h, y1 + uy * h
        q = [(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]
        tris += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
    return tris


def build():
    tris = []
    for line in CUBE:
        tris += [(t, WHITE) for t in stroke_polyline(line, STROKE)]
    for line in HOLE:
        tris += [(t, MINT) for t in stroke_polyline(line, STROKE)]
    return tris


def write_dat(path, tris):
    clamp = lambda v: max(0, min(255, int(round(v))))
    coords = bytearray()
    colors = bytearray()
    for tri, color in tris:
        for x, y in tri:
            coords += bytes((clamp(x), clamp(y)))
            colors += bytes(color)
    with open(path, "wb") as f:
        f.write(b"VCO\x00" + struct.pack("4B", 255, 255, 0, 0) + coords + colors)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ops.object.cutter_tool.dat")
    write_dat(out, build())
    print("wrote", out)
