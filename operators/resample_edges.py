"""Resample Edges: change how many points a selected edge chain or loop has, and respace them along its shape.

Works on open chains (ends stay put) and closed loops, several at once, on wire edges or edges inside faces.
Adding points splits the chain's edges, removing points merges them into their neighbours, so the edges
that run across the chain are kept. The new points follow a curve through the old ones (or the straight
segments), with even or original spacing and optional smoothing that doesn't shrink the loop.
Shape math runs in numpy, so long loops stay fast.
"""

import bmesh
import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, IntProperty


# ---------------------------------------------------------------- chains

def find_chains(bm):
    """Selected edges grouped into ordered chains: (verts, closed). Branching selections are skipped."""
    selected = [e for e in bm.edges if e.select]
    if not selected:
        return [], 0
    adj = {}
    for e in selected:
        for v in e.verts:
            adj.setdefault(v, []).append(e)
    seen, chains, skipped = set(), [], 0
    for e0 in selected:
        if e0 in seen:
            continue
        comp, stack = set(), [e0]  # edges connected to e0
        while stack:
            e = stack.pop()
            if e in comp:
                continue
            comp.add(e)
            for v in e.verts:
                stack.extend(x for x in adj[v] if x not in comp)
        seen |= comp
        verts = {v for e in comp for v in e.verts}
        degree = {v: sum(1 for x in adj[v] if x in comp) for v in verts}
        if any(d > 2 for d in degree.values()):
            skipped += 1
            continue
        ends = [v for v in verts if degree[v] == 1]
        closed = not ends
        start = ends[0] if ends else min(verts, key=lambda v: v.index)
        chains.append((walk(start, comp), closed))
    return chains, skipped


def walk(start, edges):
    """Ordered verts from start, following the given edges (for a loop the start isn't repeated)."""
    order, prev, v = [start], None, start
    while True:
        nxt = next((e for e in v.link_edges if e in edges and e is not prev), None)
        if nxt is None:
            break
        v = nxt.other_vert(v)
        if v is start:
            break
        order.append(v)
        prev = nxt
    return order


def walk_selected(start):
    """Re-walk a chain after its topology changed, through selected edges."""
    order, prev, v = [start], None, start
    while True:
        nxt = next((e for e in v.link_edges if e.select and e is not prev), None)
        if nxt is None:
            break
        v = nxt.other_vert(v)
        if v is start:
            break
        order.append(v)
        prev = nxt
    return order


# ---------------------------------------------------------------- shape

def _catmull_rom(points, closed, per_segment=12):
    """Dense points on a centripetal Catmull-Rom curve through the given points."""
    p = np.asarray(points, dtype=np.float64)
    n = len(p)
    if n < 3:
        return p
    if closed:
        ext = np.vstack([p[-1], p, p[0], p[1]])
    else:  # mirror the ends so the curve reaches them with natural tangents
        ext = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    segs = n if closed else n - 1
    p0, p1, p2, p3 = ext[:segs], ext[1:segs + 1], ext[2:segs + 2], ext[3:segs + 3]

    def knot(a, b):
        return np.maximum(np.linalg.norm(b - a, axis=1) ** 0.5, 1e-9)[:, None]

    t1 = knot(p0, p1)
    t2 = t1 + knot(p1, p2)
    t3 = t2 + knot(p2, p3)
    u = np.linspace(0.0, 1.0, per_segment, endpoint=False)[None, :, None]
    t = t1[:, None] + u * (t2 - t1)[:, None]          # (segs, k, 1)
    t1b, t2b, t3b = t1[:, None], t2[:, None], t3[:, None]
    P0, P1, P2, P3 = p0[:, None], p1[:, None], p2[:, None], p3[:, None]
    a1 = (t1b - t) / t1b * P0 + t / t1b * P1
    a2 = (t2b - t) / (t2b - t1b) * P1 + (t - t1b) / (t2b - t1b) * P2
    a3 = (t3b - t) / (t3b - t2b) * P2 + (t - t2b) / (t3b - t2b) * P3
    b1 = (t2b - t) / t2b * a1 + t / t2b * a2
    b2 = (t3b - t) / (t3b - t1b) * a2 + (t - t1b) / (t3b - t1b) * a3
    c = (t2b - t) / (t2b - t1b) * b1 + (t - t1b) / (t2b - t1b) * b2
    dense = c.reshape(-1, 3)
    return np.vstack([dense, p[0] if closed else p[-1]])


def _arc_params(points):
    d = np.linalg.norm(np.diff(points, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(d)])
    return s / s[-1] if s[-1] > 0 else np.linspace(0, 1, len(points))


def _taubin(points, closed, iterations, lam=0.5, mu=-0.53):
    """Smoothing that doesn't shrink the shape (Taubin). Ends of open chains stay put."""
    p = points.copy()
    for _ in range(iterations):
        for f in (lam, mu):
            if closed:
                avg = (np.roll(p, 1, axis=0) + np.roll(p, -1, axis=0)) * 0.5
                p = p + f * (avg - p)
            else:
                avg = (p[:-2] + p[2:]) * 0.5
                p[1:-1] = p[1:-1] + f * (avg - p[1:-1])
    return p


def resample_positions(coords, closed, segments, curve=True, even=True, smooth=0.0):
    """New point positions for a chain with this many segments."""
    p = np.asarray(coords, dtype=np.float64)
    old_segments = len(p) if closed else len(p) - 1
    ring = np.vstack([p, p[:1]]) if closed else p          # closed: walk back to the start
    shape = _catmull_rom(p, closed) if curve and len(p) >= 3 else ring
    shape_s = _arc_params(shape)
    if even:
        targets = np.linspace(0.0, 1.0, segments + 1)
    else:  # keep the old spacing: point i sits where fraction i/segments of the old points was
        old_s = _arc_params(ring)
        targets = np.interp(np.linspace(0, old_segments, segments + 1), np.arange(old_segments + 1), old_s)
    new = np.column_stack([np.interp(targets, shape_s, shape[:, k]) for k in range(3)])
    if closed:
        new = new[:-1]
    if smooth > 0:
        before = new
        new = _taubin(new, closed, max(1, int(round(smooth * 30))))
        if closed:  # keep the loop's size: scale back to its average distance from the centre
            c0, c1 = before.mean(axis=0), new.mean(axis=0)
            r0 = np.linalg.norm(before - c0, axis=1).mean()
            r1 = np.linalg.norm(new - c1, axis=1).mean()
            if r1 > 1e-12:
                new = c0 + (new - c1) * (r0 / r1)
    return new


# ---------------------------------------------------------------- topology

def _split_counts(lengths, total):
    """Segments per edge adding up to total, at least 1 each, proportional to length."""
    lengths = np.maximum(np.asarray(lengths, dtype=np.float64), 1e-12)
    extra = total - len(lengths)
    share = lengths / lengths.sum() * extra
    counts = np.floor(share).astype(int)
    for i in np.argsort(-(share - counts))[:extra - counts.sum()]:
        counts[i] += 1
    return counts + 1


def change_count(bm, verts, closed, segments):
    """Give the chain this many segments by splitting or merging its edges. Returns its new start vertex."""
    start = verts[0]
    old = len(verts) if closed else len(verts) - 1
    edges = [bm.edges.get((verts[i], verts[(i + 1) % len(verts)])) for i in range(old)]
    if segments > old:
        # split edges along the chain only: faces beside it just gain points, no new edges across them
        counts = _split_counts([e.calc_length() for e in edges], segments)
        for i, (e, c) in enumerate(zip(edges, counts)):
            v, far = verts[i], verts[(i + 1) % len(verts)]
            for k in range(int(c) - 1, 0, -1):  # cut off 1/(k+1) of what's left each time
                e_new, v_new = bmesh.utils.edge_split(e, v, 1.0 / (k + 1))
                v_new.select = True
                for piece in v_new.link_edges:
                    piece.select = True
                v = v_new
                e = bm.edges.get((v_new, far))  # the part still to split
    elif segments < old:
        # interior points to remove, spread evenly; each merges into the next point that stays
        movable = list(range(1, len(verts))) if closed else list(range(1, len(verts) - 1))
        remove = old - segments
        picks = sorted({movable[int((k + 0.5) * len(movable) / remove)] for k in range(remove)})
        keep = set(range(len(verts))) - set(picks)
        target = {}
        for i in picks:
            j = i
            while j not in keep:
                j = (j + 1) % len(verts) if closed else j + 1
            target[verts[i]] = verts[j]
        bmesh.ops.weld_verts(bm, targetmap=target)
    return start


# ---------------------------------------------------------------- operator

def _mesh_objects(context):
    return [o for o in (context.objects_in_mode_unique_data or [context.edit_object]) if o and o.type == 'MESH']


class KEYOPS_OT_resample_edges(bpy.types.Operator):
    bl_idname = "keyops.resample_edges"
    bl_label = "Resample Edges"
    bl_description = ("Change how many points the selected edge chains or loops have and space them along their shape.\n"
                      "Wheel: points. Shift Wheel: smoothing. Ctrl: even or original spacing. C: curve or straight")
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(name="Points", items=(
        ("CHANGE", "Add / Remove", "Add or remove points on every chain, keeping their own counts otherwise"),
        ("EXACT", "Exact Count", "Give every chain the same number of segments"))) # type: ignore
    change: IntProperty(name="Change", default=0, soft_min=-50, soft_max=50,
                        description="Points to add on every chain (or remove, below 0). Stops where a chain "
                                    "can't get any shorter") # type: ignore
    count: IntProperty(name="Segments", description="Segments every chain gets (a loop needs at least 3)",
                       default=8, min=1, soft_max=200, max=100000) # type: ignore
    spacing: EnumProperty(name="Spacing", items=(
        ("EVEN", "Even", "Same distance between all points"),
        ("KEEP", "Original", "Keep the chain's original spacing, denser where it was denser"))) # type: ignore
    shape: EnumProperty(name="Shape", items=(
        ("CURVE", "Curve", "Follow a smooth curve through the old points"),
        ("LINEAR", "Straight", "Follow the old straight segments exactly"))) # type: ignore
    smooth: FloatProperty(name="Smoothing", description="Smooth the chain without shrinking it", default=0.0,
                          min=0.0, max=1.0, subtype='FACTOR') # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.row().prop(self, "mode", expand=True)
        layout.prop(self, "change" if self.mode == "CHANGE" else "count")
        layout.row().prop(self, "spacing", expand=True)
        layout.row().prop(self, "shape", expand=True)
        layout.prop(self, "smooth", slider=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def resample(self, context):
        done, skipped = 0, 0
        for obj in _mesh_objects(context):
            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            chains, bad = find_chains(bm)
            skipped += bad
            if self.mode == "CHANGE" and chains:  # never below what the shortest chain can lose
                lowest = min((len(v) - 3) if c else (len(v) - 2) for v, c in chains)
                if self.change < -lowest:
                    self.change = -lowest
            for verts, closed in chains:
                old = len(verts) if closed else len(verts) - 1
                segments = self.count if self.mode == "EXACT" else old + self.change
                segments = max(segments, 3 if closed else 1)
                coords = [v.co.copy() for v in verts]
                new = resample_positions(coords, closed, segments, self.shape == "CURVE", self.spacing == "EVEN", self.smooth)
                start = change_count(bm, verts, closed, segments)
                order = walk_selected(start)
                if len(order) != len(new):  # topology didn't come out as planned (e.g. merged faces)
                    continue
                if closed:  # walk the way round that matches the new points, or the loop would twist
                    rev = [order[0]] + order[:0:-1]
                    fwd = np.array([v.co for v in order])
                    if np.linalg.norm(fwd[[0] + list(range(len(fwd) - 1, 0, -1))] - new, axis=1).sum() \
                            < np.linalg.norm(fwd - new, axis=1).sum():
                        order = rev
                for v, co in zip(order, new):
                    v.co = co
                done += 1
            bm.normal_update()
            bmesh.update_edit_mesh(me, loop_triangles=True, destructive=True)
        return done, skipped

    def execute(self, context):
        done, skipped = self.resample(context)
        if not done:
            self.report({'WARNING'}, "Select one or more edge chains or loops (no branches)")
            return {'CANCELLED'}
        if skipped:
            self.report({'INFO'}, f"Skipped {skipped} selection(s) that branch")
        return {'FINISHED'}

    # ---- interactive: wheel to change, like the original add-on
    def invoke(self, context, event):
        objs = _mesh_objects(context)
        counts, spare = [], []
        for obj in objs:
            obj.update_from_editmode()
            chains, _ = find_chains(bmesh.from_edit_mesh(obj.data))
            counts += [len(v) if c else len(v) - 1 for v, c in chains]
            spare += [(len(v) - 3) if c else (len(v) - 2) for v, c in chains]  # points each chain can lose
        if not counts:
            self.report({'WARNING'}, "Select one or more edge chains or loops (no branches)")
            return {'CANCELLED'}
        self._single = counts[0] if len(counts) == 1 else 0
        self._min_change = -min(spare)
        self._backup, self._selection = {}, {}
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            tmp = bpy.data.meshes.new(".keyops_resample_backup")
            bm.to_mesh(tmp)
            self._backup[obj.name] = tmp
            self._selection[obj.name] = ([v.index for v in bm.verts if v.select], [e.index for e in bm.edges if e.select])
        self.mode, self.change = "CHANGE", 0
        context.window_manager.modal_handler_add(self)
        self._update(context)
        return {'RUNNING_MODAL'}

    def _restore(self, context):
        for obj in _mesh_objects(context):
            tmp = self._backup.get(obj.name)
            if tmp is not None:
                bm = bmesh.from_edit_mesh(obj.data)
                bm.clear()
                bm.from_mesh(tmp)
                # the copy doesn't keep the selection: put it back (same element order as when it was made)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                verts, edges = self._selection.get(obj.name, ((), ()))
                for i in verts:
                    bm.verts[i].select = True
                for i in edges:
                    bm.edges[i].select = True
                bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)

    def _cleanup(self, context):
        for tmp in self._backup.values():
            bpy.data.meshes.remove(tmp)
        self._backup = {}
        context.area.header_text_set(None)
        context.workspace.status_text_set(None)

    def _update(self, context):
        self._restore(context)
        self.resample(context)
        pts = f"{self._single + self.change}" if self._single else f"{self.change:+d}"
        context.area.header_text_set(
            f"Segments: {pts}    Smoothing: {int(self.smooth * 100)}%    "
            f"Spacing: {'Even' if self.spacing == 'EVEN' else 'Original'}    Shape: {self.shape.title()}")

        def status(header, ctx):
            row = header.layout.row()
            for icon, text in (('MOUSE_MMB_SCROLL', "Segments"), ('EVENT_SHIFT', "+ Wheel: Smoothing"),
                               ('EVENT_CTRL', "Spacing"), ('EVENT_C', "Curve/Straight"),
                               ('MOUSE_LMB', "Confirm"), ('MOUSE_RMB', "Cancel")):
                row.label(text=text, icon=icon)
        context.workspace.status_text_set(status)

    def modal(self, context, event):
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'NUMPAD_PLUS', 'NUMPAD_MINUS'} and event.value == 'PRESS':
            step = 1 if event.type in {'WHEELUPMOUSE', 'NUMPAD_PLUS'} else -1
            if event.shift:
                self.smooth = min(1.0, max(0.0, self.smooth + 0.05 * step))
            else:
                self.change = max(self._min_change, self.change + step)
            self._update(context)
        elif event.type in {'LEFT_CTRL', 'RIGHT_CTRL'} and event.value == 'PRESS':
            self.spacing = "KEEP" if self.spacing == "EVEN" else "EVEN"
            self._update(context)
        elif event.type == 'C' and event.value == 'PRESS':
            self.shape = "LINEAR" if self.shape == "CURVE" else "CURVE"
            self._update(context)
        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._restore(context)
            self._cleanup(context)
            return {'CANCELLED'}
        elif event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}  # let the view be moved while adjusting
        return {'RUNNING_MODAL'}


def register_resample_edges():
    bpy.utils.register_class(KEYOPS_OT_resample_edges)


def unregister_resample_edges():
    bpy.utils.unregister_class(KEYOPS_OT_resample_edges)
