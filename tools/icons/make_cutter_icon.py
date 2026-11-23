"""Generates ops.object.cutter_tool.dat, the Cutter Tool toolbar icon.

Blender toolbar icons are triangle meshes in a 256x256 space (uint8 coords, y up) with
per-vertex RGBA colors: b"VCO" + version + width, height, x, y, then all coords, then all colors.

Design: two overlapping squares, readable at toolbar size. A white outlined square for the
object, and a solid mint square for the cutter overlapping its top-right corner.

Run with: blender -b --factory-startup --python make_cutter_icon.py
"""
import os
import struct

WHITE = (229, 229, 229, 255)  # same as Blender's tool icons
MINT = (117, 255, 175, 255)

# Object: outlined square, drawn as four bars of this thickness
OBJECT = (44, 44, 164, 164)
STROKE = 14

# Cutter: solid square overlapping the object's top-right corner, drawn on top
CUTTER = (104, 104, 212, 212)


def fill_rect(x0, y0, x1, y1):
    """Two triangles covering an axis-aligned rectangle."""
    return [((x0, y0), (x1, y0), (x1, y1)), ((x0, y0), (x1, y1), (x0, y1))]


def outline_rect(x0, y0, x1, y1, width):
    """Four non-overlapping bars forming a square frame, edges centered on the rectangle."""
    h = width * 0.5
    return (fill_rect(x0 - h, y0 - h, x1 + h, y0 + h) + fill_rect(x0 - h, y1 - h, x1 + h, y1 + h)
            + fill_rect(x0 - h, y0 + h, x0 + h, y1 - h) + fill_rect(x1 - h, y0 + h, x1 + h, y1 - h))


def build():
    tris = [(t, WHITE) for t in outline_rect(*OBJECT, STROKE)]
    tris += [(t, MINT) for t in fill_rect(*CUTTER)]
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
