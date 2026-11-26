"""Set Cylinder Sides: change how many sides a cylinder, tube, pipe, torus or other round shape has, in Edit Mode.

Select one edge loop that goes around the shape (or its faces). From that loop the operator walks across the
quad strips on both sides to find every parallel ring of the shape, until it reaches an end: an open border,
an n-gon cap or a triangle-fan cap. A torus closes back on itself. Every ring is then rebuilt with the new
number of sides. New points are placed on each ring's own outline (radius and height interpolated around its
centre), so a circle stays a circle, ovals stay close to their shape, and bent pipes follow their bend.
Faces copy materials and smoothing, UVs and other corner data are interpolated from the old faces, and
seams, sharp edges and creases are kept where an old edge lines up with a new one.

Where the walk meets geometry it can't follow (a boss joined to a plate, a fillet, an uneven ring) it stops
there: that ring keeps its sides, and a strip of quads and triangles joins it to the rebuilt rings, so the rest
of the shape still changes and the mesh never tears.
"""

import math
from bisect import bisect_right

import bmesh
import bpy
from bpy.props import EnumProperty, IntProperty
from mathutils import Vector

from ..utils.utilities import safe_icon

FULL = 2.0 * math.pi
EPS = 1e-6
MAX_RINGS = 100000


def _mesh_objects(context):
    return [o for o in context.objects_in_mode_unique_data if o.type == 'MESH']


# ---------------------------------------------------------------- selection

def _ordered_cycles(edges):
    """Closed, non-branching cycles in the given edges, each as an ordered vertex list."""
    adj = {}
    for e in edges:
        for v in e.verts:
            adj.setdefault(v, []).append(e)
    seen, cycles = set(), []
    for e0 in edges:
        if e0 in seen:
            continue
        comp, stack = set(), [e0]
        while stack:
            e = stack.pop()
            if e in comp:
                continue
            comp.add(e)
            for v in e.verts:
                stack.extend(x for x in adj[v] if x not in comp)
        seen |= comp
        verts = {v for e in comp for v in e.verts}
        if len(verts) < 3 or any(len(adj[v]) != 2 for v in verts):
            continue
        start = e0.verts[0]
        order, prev, cur = [start], e0, e0.other_vert(start)
        while cur is not start and len(order) <= len(verts):
            order.append(cur)
            a, b = adj[cur]
            prev = b if a is prev else a
            cur = prev.other_vert(cur)
        if cur is start and len(order) == len(verts):
            cycles.append(order)
    return cycles


def selected_loops(bm):
    """Loops the user picked: selected edge loops, or the border loops of the selected faces."""
    sel_faces = [f for f in bm.faces if f.select]
    if sel_faces:
        border = [e for e in bm.edges if sum(1 for f in e.link_faces if f.select) == 1]
        loops = _ordered_cycles(border)
        if not loops:  # a whole closed shape is selected: start from its n-gon caps
            loops = [list(f.verts) for f in sel_faces if len(f.verts) > 4]
        return loops
    return _ordered_cycles([e for e in bm.edges if e.select])


# ---------------------------------------------------------------- topology walk

def _edge_between(a, b):
    for e in a.link_edges:
        if e.other_vert(a) is b:
            return e
    return None


def _loop_edges(verts):
    n = len(verts)
    return [_edge_between(verts[i], verts[(i + 1) % n]) for i in range(n)]


def _step(verts, edges, forward):
    """Look at the faces on one side of a ring.

    The side is picked by face direction: 'forward' faces run verts[i] -> verts[i+1] along the ring edge.
    Returns ('STRIP', (next_ring, faces)), ('OPEN', None), ('NGON', face), ('FAN', (faces, apex)) or ('BAD', None).
    """
    n = len(verts)
    loops = []
    for i in range(n):
        hits = [l for l in edges[i].link_loops if (l.vert is verts[i]) == forward]
        if len(hits) > 1:
            return 'BAD', None
        loops.append(hits[0] if hits else None)
    faces = [l.face if l else None for l in loops]
    if all(f is None for f in faces):
        return 'OPEN', None
    if any(f is None for f in faces):
        return 'BAD', None

    if len(set(faces)) == n and all(len(f.verts) == 4 for f in faces):
        nxt = [None] * n
        for i, l in enumerate(loops):
            if forward:
                here, there = l.link_loop_prev.vert, l.link_loop_next.link_loop_next.vert
            else:
                here, there = l.link_loop_next.link_loop_next.vert, l.link_loop_prev.vert
            for idx, v in ((i, here), ((i + 1) % n, there)):
                if nxt[idx] is None:
                    nxt[idx] = v
                elif nxt[idx] is not v:
                    return 'BAD', None
        if len(set(nxt)) != n or set(nxt) & set(verts):
            return 'BAD', None
        return 'STRIP', (nxt, faces)

    if len(set(faces)) == 1 and len(faces[0].verts) == n:
        return 'NGON', faces[0]
    if len(set(faces)) == n and all(len(f.verts) == 3 for f in faces):
        apex = {v for f in faces for v in f.verts} - set(verts)
        if len(apex) == 1:
            c = apex.pop()
            if len(c.link_faces) == n and len(c.link_edges) == n:
                return 'FAN', (faces, c)
    return 'BAD', None


class Chain:
    """All rings of one round shape, the strips of quads between them and the caps at its ends."""

    def __init__(self):
        self.rings = []    # ordered vertex lists, all aligned (index i lines up along the shape)
        self.strips = []   # (ring_p, ring_q, faces along ring_p's edges, forward)
        self.caps = []     # (ring, kind, data, forward)
        self.fixed = set() # rings that touch other geometry: they keep their vertices


def find_chain(start):
    """Walk out from one ring. Returns (Chain, None) or (None, reason)."""
    if None in _loop_edges(start):
        return None, "The selected loop is not a closed edge loop"
    sides = {}
    visited = set(start)
    closed = False
    stopped = {}  # side -> True when the walk stopped at geometry it can't follow
    for forward in (True, False):
        seq, strips, cap = [], [], None
        cur = start
        while True:
            kind, data = _step(cur, _loop_edges(cur), forward)
            if kind == 'STRIP':
                nxt, faces = data
                strips.append(faces)
                if set(nxt) == set(start):
                    if any(a is not b for a, b in zip(nxt, start)):
                        return None, "Twisted ring shapes are not supported"
                    closed = True
                    break
                if set(nxt) & visited or len(seq) > MAX_RINGS:
                    return None, "The shape runs into itself"
                visited |= set(nxt)
                seq.append(nxt)
                cur = nxt
            elif kind == 'BAD':
                stopped[forward] = True  # this ring touches other geometry: keep it, rebuild up to it
                break
            else:
                cap = (kind, data)
                break
        sides[forward] = (seq, strips, cap)
        if closed:
            break

    chain = Chain()
    seq_a, strips_a, cap_a = sides[True]
    seq_b, strips_b, cap_b = sides.get(False, ([], [], None))
    chain.rings = list(reversed(seq_b)) + [start] + seq_a
    i0 = len(seq_b)
    for j, faces in enumerate(strips_a):
        q = i0 + j + 1 if not (closed and j == len(strips_a) - 1) else i0
        chain.strips.append((i0 + j, q, faces, True))
    for j, faces in enumerate(strips_b):
        chain.strips.append((i0 - j, i0 - j - 1, faces, False))
    if cap_a and cap_a[0] != 'OPEN':
        chain.caps.append((i0 + len(seq_a), cap_a[0], cap_a[1], True))
    if cap_b and cap_b[0] != 'OPEN':
        chain.caps.append((i0 - len(seq_b), cap_b[0], cap_b[1], False))
    if stopped.get(True):
        chain.fixed.add(i0 + len(seq_a))
    if stopped.get(False):
        chain.fixed.add(i0 - len(seq_b))
    if len(chain.fixed) >= len(chain.rings):
        return None, "The shape is joined to other geometry right at the selected loop"

    # Nothing else may hang on the rings that get rebuilt, or rebuilding them would tear the mesh
    allowed = {f for _, _, faces, _ in chain.strips for f in faces}
    for _, kind, data, _ in chain.caps:
        allowed |= {data} if kind == 'NGON' else set(data[0])
    for x, ring in enumerate(chain.rings):
        if x in chain.fixed:
            continue
        for v in ring:
            if any(f not in allowed for f in v.link_faces) or any(not e.link_faces for e in v.link_edges):
                return None, "The shape is joined to other geometry"
    return chain, None


def find_chains(bm):
    """Chains for every selected loop, one per shape. Returns (chains, reasons for skipped loops)."""
    chains, reasons, used = [], [], set()
    for loop in selected_loops(bm):
        if set(loop) & used:
            continue
        chain, why = find_chain(loop)
        if chain and chain.strips:  # line a UV seam up with the start, so it stays on an edge
            p, q, _, _ = chain.strips[0]
            seam = next((i for i in range(len(loop)) if (e := _edge_between(chain.rings[p][i], chain.rings[q][i]))
                         and e.seam), 0)
            if seam:
                chain, why = find_chain(loop[seam:] + loop[:seam])
        if chain is None:
            reasons.append(why)
            continue
        verts = {v for ring in chain.rings for v in ring}
        if verts & used:
            continue
        used |= verts
        chains.append(chain)
    return chains, reasons


# ---------------------------------------------------------------- rebuild

def _ring_shape(coords):
    """Centre, axis, in-plane basis and the polar outline (angle, radius, height) of one ring."""
    n = len(coords)
    c = sum(coords, Vector()) / n
    axis = Vector()
    for i in range(n):
        axis += (coords[i] - c).cross(coords[(i + 1) % n] - c)
    if axis.length < 1e-12:
        return None
    axis.normalize()
    d0 = coords[0] - c
    u = d0 - axis * d0.dot(axis)
    if u.length < 1e-12:
        return None
    u.normalize()
    w = axis.cross(u)
    ang, rad, hgt = [], [], []
    for p in coords:
        d = p - c
        x, y = d.dot(u), d.dot(w)
        ang.append(math.atan2(y, x) % FULL)
        rad.append(math.hypot(x, y))
        hgt.append(d.dot(axis))
    ang[0] = 0.0
    if any(ang[i + 1] <= ang[i] for i in range(n - 1)):
        return None  # points don't go round the centre in order: not a round shape
    return c, axis, u, w, ang, rad, hgt


def _segment(ang, t):
    """Index of the old ring edge that angle t falls on."""
    return max(0, min(len(ang) - 1, bisect_right(ang, t % FULL) - 1))


def _copy_edge(bm, old, new):
    """Copy seam, sharp and edge attributes (crease, bevel weight, ...) from an old edge to a new one."""
    new.seam = old.seam
    new.smooth = old.smooth
    for kind in ("float", "int", "bool", "float_vector", "float_color", "color"):
        layers = getattr(bm.edges.layers, kind, None)
        if layers is None:
            continue
        for layer in layers.values():
            new[layer] = old[layer]


def _interp_loops(face, sources):
    """Copy UVs and other corner data for each corner of a new face from the matching old face."""
    for l in face.loops:
        src = sources.get(l.vert)
        if src is not None and src.is_valid:
            l.copy_from_face_interp(src, False, True)  # (face, vert, multires): positional only


def rebuild(bm, chain, sides):
    """Replace every ring of the chain with one that has the given number of sides. Returns an error or None."""
    shapes = [_ring_shape([v.co.copy() for v in ring]) for ring in chain.rings]
    if None in shapes:
        return "Some rings are not round enough to rebuild"
    n = len(chain.rings[0])
    ts = [FULL * k / sides for k in range(sides)]
    old_ring_edges = [_loop_edges(ring) for ring in chain.rings]

    new_rings = []
    for x, (ring, (c, axis, u, w, ang, rad, hgt)) in enumerate(zip(chain.rings, shapes)):
        if x in chain.fixed:
            new_rings.append(None)  # keeps its own vertices
            continue
        verts = []
        for t in ts:
            i = _segment(ang, t)
            j = (i + 1) % n
            span = (ang[j] if j else FULL) - ang[i]
            f = (t - ang[i]) / span if span > 0 else 0.0
            r = rad[i] + (rad[j] - rad[i]) * f
            h = hgt[i] + (hgt[j] - hgt[i]) * f
            co = c + axis * h + (u * math.cos(t) + w * math.sin(t)) * r
            verts.append(bm.verts.new(co, ring[i] if f < 0.5 else ring[j]))
        new_rings.append(verts)

    def spans(ang, k):
        """Old segments for the start, end and middle of new segment k."""
        a = ts[k]
        b = ts[k + 1] if k + 1 < sides else FULL
        return _segment(ang, a + EPS), _segment(ang, b - EPS), _segment(ang, (a + b) * 0.5)

    # Side faces
    for p, q, faces, forward in chain.strips:
        ang = shapes[p][4]
        P, Q = new_rings[p], new_rings[q]
        if P is None and Q is None:
            continue  # both rings stay: so does the strip between them
        if P is None or Q is None:
            _transition(bm, chain, shapes, new_rings, ts, p, q, faces, forward)
            continue
        for k in range(sides):
            k1 = (k + 1) % sides
            sa, sb, mid = spans(ang, k)
            vs = [P[k], P[k1], Q[k1], Q[k]] if forward else [P[k1], P[k], Q[k], Q[k1]]
            face = bm.faces.new(vs, faces[mid])
            face.select_set(faces[mid].select)
            _interp_loops(face, {P[k]: faces[sa], Q[k]: faces[sa], P[k1]: faces[sb], Q[k1]: faces[sb]})
        # rails that line up with an old one keep its seam / sharp / crease
        old_p, old_q = chain.rings[p], chain.rings[q]
        for k, t in enumerate(ts):
            i = _segment(ang, t + EPS)
            if abs(ang[i] - t) < 1e-5:
                old = _edge_between(old_p[i], old_q[i])
                new = _edge_between(P[k], Q[k])
                if old and new:
                    _copy_edge(bm, old, new)

    # Caps
    for r, kind, data, forward in chain.caps:
        ang = shapes[r][4]
        E = new_rings[r]
        if kind == 'NGON':
            vs = E if forward else list(reversed(E))
            face = bm.faces.new(vs, data)
            face.select_set(data.select)
            _interp_loops(face, {v: data for v in E})
        else:
            tris, apex = data
            for k in range(sides):
                k1 = (k + 1) % sides
                sa, sb, mid = spans(ang, k)
                vs = [E[k], E[k1], apex] if forward else [E[k1], E[k], apex]
                face = bm.faces.new(vs, tris[mid])
                face.select_set(tris[mid].select)
                _interp_loops(face, {E[k]: tris[sa], E[k1]: tris[sb], apex: tris[mid]})

    # Ring edges keep the flags (and selection) of the old ring edge they lie on
    for x, ring in enumerate(new_rings):
        if ring is None:
            continue
        ang = shapes[x][4]
        for k in range(sides):
            new = _edge_between(ring[k], ring[(k + 1) % sides])
            old = old_ring_edges[x][spans(ang, k)[2]]
            if new and old:
                _copy_edge(bm, old, new)
                new.select_set(old.select)

    bmesh.ops.delete(bm, geom=list({v for x, ring in enumerate(chain.rings) if x not in chain.fixed for v in ring}),
                     context='VERTS')
    return None


def _transition(bm, chain, shapes, new_rings, ts, p, q, faces, forward):
    """Join a ring that keeps its vertices to a rebuilt one: walk round both by angle and make a quad where
    their points line up, a triangle where one has a point the other hasn't."""
    keep = p if new_rings[p] is None else q
    built = q if keep == p else p
    c, axis, u, w = shapes[built][:4]
    old_ang = shapes[p][4]
    kept = [(math.atan2((v.co - c).dot(w), (v.co - c).dot(u)) % FULL, v) for v in chain.rings[keep]]
    start = min(range(len(kept)), key=lambda i: kept[i][0])
    kept = kept[start:] + kept[:start]
    new = list(zip(ts, new_rings[built]))
    A, B = (kept, new) if keep == p else (new, kept)  # A runs along ring p, B along ring q
    na, nb = len(A), len(B)

    def angle(lst, i):
        return lst[i % len(lst)][0] + FULL * (i // len(lst))

    def src(t):
        return faces[_segment(old_ang, t)]

    i = j = 0
    while i < na or j < nb:
        a_next = angle(A, i + 1) if i < na else math.inf
        b_next = angle(B, j + 1) if j < nb else math.inf
        a0, b0 = A[i % na][1], B[j % nb][1]
        if abs(a_next - b_next) < 1e-4:
            vs = [a0, A[(i + 1) % na][1], B[(j + 1) % nb][1], b0]
            mid = (a_next + angle(A, i)) * 0.5
            i, j = i + 1, j + 1
        elif a_next < b_next:
            vs = [a0, A[(i + 1) % na][1], b0]
            mid = (a_next + angle(A, i)) * 0.5
            i += 1
        else:
            vs = [a0, B[(j + 1) % nb][1], b0]
            mid = (b_next + angle(B, j)) * 0.5
            j += 1
        if len(set(vs)) < 3:
            continue
        if not forward:
            vs.reverse()
        old = src(mid)
        try:
            face = bm.faces.new(vs, old)
        except ValueError:
            continue  # already exists
        face.select_set(old.select)
        _interp_loops(face, {v: old for v in vs})


# ---------------------------------------------------------------- operator

class KEYOPS_OT_set_cylinder_sides(bpy.types.Operator):
    bl_idname = "keyops.set_cylinder_sides"
    bl_label = "Set Cylinder Sides"
    bl_description = ("Change how many sides a cylinder, tube, pipe, torus or other round shape has, keeping its outline.\n"
                      "Select one edge loop that goes around it, or its faces. "
                      "Wheel: sides. Ctrl Wheel: double or halve")
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(name="Sides", items=(
        ("CHANGE", "Add / Remove", "Add or remove sides on every selected shape"),
        ("EXACT", "Exact Count", "Give every selected shape the same number of sides"))) # type: ignore
    change: IntProperty(name="Change", default=0, soft_min=-64, soft_max=64,
                        description="Sides to add to every shape (or remove, below 0). A shape keeps at least 3") # type: ignore
    sides: IntProperty(name="Sides", default=16, min=3, soft_max=256, max=4096,
                       description="Number of sides every selected shape gets") # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.row().prop(self, "mode", expand=True)
        layout.prop(self, "change" if self.mode == "CHANGE" else "sides")

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def apply(self, context):
        done, reasons = 0, []
        for obj in _mesh_objects(context):
            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            chains, why = find_chains(bm)
            reasons += why
            if not chains:
                continue
            for chain in chains:
                old = len(chain.rings[0])
                target = self.sides if self.mode == "EXACT" else old + self.change
                target = max(3, target)
                if target != old:
                    err = rebuild(bm, chain, target)
                    if err:
                        reasons.append(err)
                        continue
                done += 1
            bm.select_flush_mode()
            bm.normal_update()
            bmesh.update_edit_mesh(me, loop_triangles=True, destructive=True)
        return done, reasons

    def execute(self, context):
        done, reasons = self.apply(context)
        if not done:
            self.report({'WARNING'}, reasons[0] if reasons else
                        "Select an edge loop that goes around a round shape, or the shape's faces")
            return {'CANCELLED'}
        if reasons:
            self.report({'INFO'}, f"Skipped {len(reasons)} shape(s): {reasons[0]}")
        return {'FINISHED'}

    # ---- interactive: wheel changes the side count
    def invoke(self, context, event):
        objs = _mesh_objects(context)
        counts, reasons = [], []
        for obj in objs:
            obj.update_from_editmode()
            chains, why = find_chains(bmesh.from_edit_mesh(obj.data))
            counts += [len(c.rings[0]) for c in chains]
            reasons += why
        if not counts:
            self.report({'WARNING'}, reasons[0] if reasons else
                        "Select an edge loop that goes around a round shape, or the shape's faces")
            return {'CANCELLED'}
        self._base = counts[0]
        self._single = len(counts) == 1
        self._min_change = 3 - min(counts)
        self._backup, self._selection = {}, {}
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            tmp = bpy.data.meshes.new(".keyops_cylinder_sides_backup")
            bm.to_mesh(tmp)
            self._backup[obj.name] = tmp
            self._selection[obj.name] = ([v.index for v in bm.verts if v.select],
                                         [e.index for e in bm.edges if e.select],
                                         [f.index for f in bm.faces if f.select])
        self.mode, self.change = "CHANGE", 0
        self._dirty = False
        # wheel ticks only set the count; the mesh is rebuilt on the next timer tick, so fast scrolling on a
        # heavy mesh rebuilds once instead of once per tick
        self._timer = context.window_manager.event_timer_add(0.03, window=context.window)
        context.window_manager.modal_handler_add(self)
        self._update(context)
        return {'RUNNING_MODAL'}

    def _restore(self, context):
        for obj in _mesh_objects(context):
            tmp = self._backup.get(obj.name)
            if tmp is None:
                continue
            bm = bmesh.from_edit_mesh(obj.data)
            bm.clear()
            bm.from_mesh(tmp)
            # the copy doesn't keep the selection: put it back (same element order as when it was made)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            verts, edges, faces = self._selection.get(obj.name, ((), (), ()))
            for i in verts:
                bm.verts[i].select = True
            for i in edges:
                bm.edges[i].select = True
            for i in faces:
                bm.faces[i].select = True
            bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)

    def _cleanup(self, context):
        if getattr(self, "_timer", None) is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        for tmp in self._backup.values():
            bpy.data.meshes.remove(tmp)
        self._backup = {}
        context.area.header_text_set(None)
        context.workspace.status_text_set(None)

    def _update(self, context):
        self._restore(context)
        self.apply(context)
        text = f"{self._base + self.change}" if self._single else f"{self.change:+d}"
        context.area.header_text_set(f"Sides: {text}")

        def status(header, ctx):
            row = header.layout.row()
            for icon, label in (('MOUSE_MMB_SCROLL', "Sides"), ('EVENT_CTRL', "+ Wheel: Double / Halve"),
                                ('MOUSE_LMB', "Confirm"), ('MOUSE_RMB', "Cancel")):
                row.label(text=label, icon=safe_icon(icon))
        context.workspace.status_text_set(status)

    def modal(self, context, event):
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'NUMPAD_PLUS', 'NUMPAD_MINUS'} and event.value == 'PRESS':
            up = event.type in {'WHEELUPMOUSE', 'NUMPAD_PLUS'}
            if event.ctrl:
                current = self._base + self.change
                target = current * 2 if up else current // 2
                self.change = target - self._base
            else:
                self.change += 1 if up else -1
            self.change = max(self._min_change, self.change)
            self._dirty = True
            context.area.header_text_set(f"Sides: {self._base + self.change if self._single else f'{self.change:+d}'}")
        elif event.type == 'TIMER' and self._dirty:
            self._dirty = False
            self._update(context)
        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
            if self._dirty:
                self._update(context)
            self._cleanup(context)
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._restore(context)
            self._cleanup(context)
            return {'CANCELLED'}
        elif event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}  # let the view be moved while adjusting
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(KEYOPS_OT_set_cylinder_sides)


def unregister():
    bpy.utils.unregister_class(KEYOPS_OT_set_cylinder_sides)
