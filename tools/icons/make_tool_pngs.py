"""Renders the toolbar icons (ops.*.dat) to PNG files in icons/, named tool_<feature id>.png.

The preferences show these next to each Active Tools feature, so people can spot the tool
in the toolbar. Run again after changing a .dat icon. Pure Python, no Blender needed:

    python make_tool_pngs.py

.dat layout: b"VCO" + version byte, then width, height, x, y (one byte each), then all
triangle coords (two uint8 per vertex, y up), then all vertex colors (RGBA uint8).
"""
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "..", "icons")
SIZE = 64   # output pixels
SS = 4      # supersampling per axis, for smooth edges

ICONS = {
    "merge_tool": "ops.mesh.merge_tool.dat",
    "fast_loop_cut": "ops.mesh.fast_loop_cut.dat",
    "cutter_tool": "ops.object.cutter_tool.dat",
    "push_pull": "ops.mesh.push_pull.dat",  # Blender's Extrude Manifold icon, which the tool uses
}


def read_dat(path):
    with open(path, "rb") as f:
        data = f.read()
    assert data[:3] == b"VCO", path
    w, h = data[4], data[5]
    body = data[8:]
    n_verts = len(body) // 6  # 2 coord bytes + 4 color bytes per vertex
    coords = body[:n_verts * 2]
    colors = body[n_verts * 2:]
    tris = []
    for t in range(n_verts // 3):
        pts = [(coords[(t * 3 + i) * 2] / w, coords[(t * 3 + i) * 2 + 1] / h) for i in range(3)]
        c = colors[t * 12:t * 12 + 4]  # flat color: first vertex
        tris.append((pts, tuple(c)))
    return tris


def rasterize(tris):
    n = SIZE * SS
    acc = [[0.0, 0.0, 0.0, 0.0] for _ in range(SIZE * SIZE)]  # premultiplied RGBA sums
    for pts, (r, g, b, a) in tris:
        (x0, y0), (x1, y1), (x2, y2) = [(px * n, (1.0 - py) * n) for px, py in pts]  # flip y
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if area == 0:
            continue
        lo_x, hi_x = max(0, int(min(x0, x1, x2))), min(n - 1, int(max(x0, x1, x2)) + 1)
        lo_y, hi_y = max(0, int(min(y0, y1, y2))), min(n - 1, int(max(y0, y1, y2)) + 1)
        for sy in range(lo_y, hi_y + 1):
            py = sy + 0.5
            for sx in range(lo_x, hi_x + 1):
                px = sx + 0.5
                w0 = (x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)
                w1 = (x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)
                w2 = (x0 - px) * (y1 - py) - (x1 - px) * (y0 - py)
                if (w0 >= 0 and w1 >= 0 and w2 >= 0) or (w0 <= 0 and w1 <= 0 and w2 <= 0):
                    _samples[(sx, sy)] = (r, g, b, a)  # later triangles paint over earlier ones
    for (sx, sy), (r, g, b, a) in _samples.items():
        p = acc[(sy // SS) * SIZE + sx // SS]
        al = a / 255.0
        p[0] += r * al
        p[1] += g * al
        p[2] += b * al
        p[3] += al
    _samples.clear()
    out = bytearray()
    k = SS * SS
    for y in range(SIZE):
        out.append(0)  # PNG filter: none
        for x in range(SIZE):
            r, g, b, a = acc[y * SIZE + x]
            if a > 0:
                out += bytes((round(r / a), round(g / a), round(b / a), round(255 * a / k)))
            else:
                out += b"\0\0\0\0"
    return bytes(out)


_samples = {}


def write_png(path, raw):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    for fid, dat in ICONS.items():
        out = os.path.normpath(os.path.join(OUT_DIR, f"tool_{fid}.png"))
        write_png(out, rasterize(read_dat(os.path.join(HERE, dat))))
        print("wrote", out)
