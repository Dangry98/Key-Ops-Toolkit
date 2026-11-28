"""Draws the Edit Toolkit's icons for Key Ops' own operators into icons/ (64 px PNGs, light grey line art with an
orange accent, like the other Key Ops icons). Run with any Python that has Pillow:

    python3 scripts/make_toolkit_icons.py
"""
import math
import os

from PIL import Image, ImageDraw

SIZE, SS = 64, 4                     # final size, supersampling
GREY = (214, 214, 214, 255)
DIM = (150, 150, 150, 255)
ORANGE = (255, 160, 40, 255)
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")


class Pen:
    def __init__(self):
        self.img = Image.new("RGBA", (SIZE * SS, SIZE * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    @staticmethod
    def p(x, y):
        return (x * SS, y * SS)

    def line(self, pts, col=GREY, w=3.0, closed=False):
        pts = [self.p(*q) for q in pts] + ([self.p(*pts[0])] if closed else [])
        self.d.line(pts, fill=col, width=int(w * SS), joint="curve")
        for q in pts:  # round ends
            r = w * SS / 2
            self.d.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), fill=col)

    def poly(self, pts, col):
        self.d.polygon([self.p(*q) for q in pts], fill=col)

    def dot(self, x, y, r=3.5, col=ORANGE):
        self.d.ellipse((self.p(x - r, y - r)) + self.p(x + r, y + r), fill=col)

    def arrow(self, a, b, col=ORANGE, w=3.0, head=7.0):
        self.line([a, b], col, w)
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        for s in (2.5, -2.5):
            self.line([b, (b[0] - head * math.cos(ang + s / 3), b[1] - head * math.sin(ang + s / 3))], col, w)

    def save(self, name):
        self.img.resize((SIZE, SIZE), Image.LANCZOS).save(os.path.join(OUT, name + ".png"))


def ngon(cx, cy, r, n, start=-90):
    return [(cx + r * math.cos(math.radians(start + 360 * i / n)), cy + r * math.sin(math.radians(start + 360 * i / n)))
            for i in range(n)]


def icons():
    # Select Similar: a selected face, and two of the same shape picked with it
    p = Pen()
    for x, y, col in ((8, 10, ORANGE), (36, 10, ORANGE), (22, 36, GREY)):
        p.line([(x, y), (x + 20, y), (x + 20, y + 18), (x, y + 18)], col, 3, closed=True)
    p.poly([(10, 12), (26, 12), (26, 26), (10, 26)], (255, 160, 40, 90))
    p.save("ops_select_similar")

    # Thin Triangles: a sliver triangle in a quad
    p = Pen()
    p.line([(8, 12), (56, 12), (56, 52), (8, 52)], GREY, 3, closed=True)
    p.poly([(8, 52), (56, 12), (56, 22)], (255, 160, 40, 120))
    p.line([(8, 52), (56, 12), (56, 22)], ORANGE, 3, closed=True)
    p.save("ops_thin_triangles")

    # Connect: an edge made between two vertices across a face
    p = Pen()
    p.line([(8, 10), (56, 10), (56, 54), (8, 54)], GREY, 3, closed=True)
    p.line([(32, 10), (32, 54)], ORANGE, 3.5)
    p.dot(32, 10, 5)
    p.dot(32, 54, 5)
    p.save("ops_connect")

    # Set Flow: the middle loop eased into a curve between two loops
    p = Pen()
    p.line([(6, 14), (58, 14)], DIM, 3)
    p.line([(6, 50), (58, 50)], DIM, 3)
    p.line([(6 + i * 52 / 12, 32 - 9 * math.sin(math.pi * i / 12)) for i in range(13)], ORANGE, 3.5)
    for x in (6, 32, 58):
        p.line([(x, 14), (x, 50)], DIM, 2)
    p.save("ops_set_flow")

    # Resample Edges: a curve with evenly spaced points
    p = Pen()
    pts = [(6 + i * 52 / 24, 46 - 26 * math.sin(math.pi * i / 24)) for i in range(25)]
    p.line(pts, GREY, 3)
    for i in range(0, 25, 4):
        p.dot(*pts[i], 4.5)
    p.save("ops_resample_edges")

    # Make Edge Trim: a strip along the top edge of a box
    p = Pen()
    p.line([(8, 26), (30, 14), (56, 26), (34, 38), (8, 26)], GREY, 3)
    p.line([(8, 26), (8, 50), (34, 62 - 0), (34, 38)], GREY, 3)
    p.line([(34, 62), (56, 50), (56, 26)], GREY, 3)
    p.poly([(34, 38), (56, 26), (56, 32), (34, 44)], ORANGE)
    p.poly([(34, 38), (56, 26), (50, 23), (29, 35)], (255, 190, 110, 255))
    p.save("ops_edge_trim")

    # Clean Up: a face with loose vertices swept away
    p = Pen()
    p.line([(8, 22), (40, 22), (40, 54), (8, 54)], GREY, 3, closed=True)
    for x, y in ((50, 10), (56, 22), (46, 30)):
        p.line([(x - 4, y - 4), (x + 4, y + 4)], ORANGE, 3)
        p.line([(x - 4, y + 4), (x + 4, y - 4)], ORANGE, 3)
    p.save("ops_cleanup")

    # Extract: a face lifted out of a grid
    p = Pen()
    for i in range(3):
        p.line([(6, 30 + i * 12), (58, 30 + i * 12)], DIM, 2)
    for x in (6, 23, 41, 58):
        p.line([(x, 30), (x, 54)], DIM, 2)
    p.line([(23, 30), (41, 30), (41, 42), (23, 42)], DIM, 2, closed=True)
    p.poly([(23, 8), (41, 8), (41, 20), (23, 20)], (255, 160, 40, 110))
    p.line([(23, 8), (41, 8), (41, 20), (23, 20)], ORANGE, 3, closed=True)
    p.arrow((32, 30), (32, 23), ORANGE, 2.5, 5)
    p.save("ops_extract")

    # Seam by Angle: seams on the sharp edges of a box
    p = Pen()
    top = [(8, 24), (30, 12), (56, 24), (34, 36)]
    p.line(top, GREY, 3, closed=True)
    p.line([(8, 24), (8, 48), (34, 60), (56, 48), (56, 24)], GREY, 3)
    p.line([(34, 36), (34, 60)], ORANGE, 3.5)
    p.line([(8, 24), (34, 36), (56, 24)], ORANGE, 3.5)
    p.save("ops_seam_by_angle")

    # Set Color: a face with a color on each corner
    p = Pen()
    tri = [(32, 8), (58, 54), (6, 54)]
    p.line(tri, GREY, 3, closed=True)
    for (x, y), col in zip(tri, ((235, 70, 70, 255), (80, 200, 90, 255), (70, 130, 240, 255))):
        p.dot(x, y, 6.5, col)
    p.save("ops_vertex_color")

    # Change Number of Sides: a ring with its vertices
    p = Pen()
    ring = ngon(32, 32, 24, 8)
    p.line(ring, GREY, 3, closed=True)
    for q in ring:
        p.dot(*q, 4.5)
    p.save("ops_cylinder_sides")

    # Halve Sides: eight sides become four
    p = Pen()
    p.line(ngon(32, 32, 25, 8), DIM, 2, closed=True)
    sq = ngon(32, 32, 25, 4)
    p.line(sq, ORANGE, 3.5, closed=True)
    p.save("ops_halve_sides")

    # Double Sides: four sides become eight
    p = Pen()
    p.line(ngon(32, 32, 25, 4), DIM, 2, closed=True)
    oc = ngon(32, 32, 25, 8)
    p.line(oc, ORANGE, 3.5, closed=True)
    p.save("ops_double_sides")

    # Revolve Edges: a profile spun around an axis
    p = Pen()
    p.line([(32, 6), (32, 58)], DIM, 2)
    p.line([(40, 12), (48, 24), (46, 40), (52, 52)], ORANGE, 3.5)
    arc = [(32 + 20 * math.cos(math.radians(a)), 32 + 7 * math.sin(math.radians(a))) for a in range(200, 341, 10)]
    p.line(arc, GREY, 3)
    p.arrow(arc[-2], arc[-1], GREY, 3, 6)
    p.save("ops_revolve")

    # Re-Bevel: a rounded corner whose segments change
    p = Pen()
    p.line([(8, 56), (8, 28)], GREY, 3)
    p.line([(36, 8), (56, 8)], GREY, 3)
    arc = [(36 - 28 * math.cos(math.radians(a)), 36 - 28 * math.sin(math.radians(a))) for a in range(0, 91, 18)]
    arc = [(8 + (x - 8), y) for x, y in arc]
    p.line(arc, ORANGE, 3.5)
    for q in arc:
        p.dot(*q, 3.5)
    p.save("ops_rebevel")

    # Slide Scale: vertices slide out along their edges
    p = Pen()
    p.line([(4, 32), (60, 32)], DIM, 2)
    p.line([(32, 4), (32, 60)], DIM, 2)
    p.line([(14, 14), (50, 50)], DIM, 2)
    p.line([(14, 50), (50, 14)], DIM, 2)
    for a, b in (((24, 32), (12, 32)), ((40, 32), (52, 32)), ((32, 24), (32, 12)), ((32, 40), (32, 52))):
        p.arrow(a, b, ORANGE, 3, 6)
    p.dot(32, 32, 4, GREY)
    p.save("ops_slide_scale")

    # Slide Rotate: vertices turn around, each staying on its edges
    p = Pen()
    p.line(ngon(32, 32, 24, 6), DIM, 2, closed=True)
    arc = [(32 + 15 * math.cos(math.radians(a)), 32 + 15 * math.sin(math.radians(a))) for a in range(200, 431, 10)]
    p.line(arc, ORANGE, 3.5)
    p.arrow(arc[-2], arc[-1], ORANGE, 3.5, 7)
    p.save("ops_slide_rotate")


if __name__ == "__main__":
    icons()
    print("icons written to", OUT)
