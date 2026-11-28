"""Booleans on edit meshes that come back right on as many meshes as possible.

Used by Smart Extrude / Push / Pull. The rules, in order:

1. No boolean when none is needed: if a plain extrude hits nothing else in the mesh, it is done with
   bmesh.ops (exact, keeps the topology). See `extrude_hits`.
2. Only the islands the cutter can reach go into the boolean; every other part of the mesh is left exactly as
   it was and merged back afterwards.
3. Open islands are made closed first: every hole gets a temporary cap face, tagged with a face attribute. The
   boolean runs on the closed mesh and the tagged faces are deleted afterwards, so the mesh comes back open
   exactly where it was open, changed only where the cutter went.
4. Solver: Manifold (Blender 4.5+) when the capped mesh is manifold; otherwise Fast, unless a face of the cutter
   lies on a face of the mesh (Fast can't handle that); Exact as the last resort.
5. Every result is checked (no new holes or non-manifold edges, volume changed the right way and by no more
   than the cutter's volume); a result that fails goes to the next solver.
"""

import os

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

DEBUG = bool(os.environ.get("KEYOPS_BOOL_DEBUG"))
last_path = None  # what the last extrude did ('NONE' = no boolean, else the solver): for tests and the status bar
CAP = "keyops_cap"  # temporary face tag: 1 = cap face (deleted afterwards), 2 = cutter face to select afterwards,
#                    3 = cutter face selected when no 2 is left (a cut right through)


# ---------------------------------------------------------------- small mesh helpers

def solver_items():
    return [i.identifier for i in bpy.types.BooleanModifier.bl_rna.properties["solver"].enum_items]


def fast_name():
    return 'FAST' if 'FAST' in solver_items() else 'FLOAT'


def islands(faces):
    """Face islands (connected through edges) of an iterable of faces, as lists. Islands that touch only at a
    vertex stay apart (Exact mishandles solids touching at a point); boolean() welds such vertices back."""
    left = set(faces)
    out = []
    while left:
        seed = left.pop()
        isl = [seed]
        stack = [seed]
        while stack:
            f = stack.pop()
            for e in f.edges:
                for lf in e.link_faces:
                    if lf in left:
                        left.discard(lf)
                        isl.append(lf)
                        stack.append(lf)
        out.append(isl)
    return out


def _bbox(points):
    xs, ys, zs = zip(*points)
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def _bbox_overlap(a, b, tol):
    return all(a[0][i] - tol <= b[1][i] and b[0][i] - tol <= a[1][i] for i in range(3))


def signed_volume(bm):
    vol = 0.0
    for tri in bm.calc_loop_triangles():
        a, b, c = (lp.vert.co for lp in tri)
        vol += a.dot(b.cross(c))
    return vol / 6.0


def stats(bm):
    boundary = nonmanifold = 0
    for e in bm.edges:
        k = len(e.link_faces)
        if k == 1:
            boundary += 1
        elif k > 2:
            nonmanifold += 1
    return boundary, nonmanifold


def mesh_stats(bm, scratch):
    """(open edges, non-manifold edges, signed volume) of a bmesh, computed in C / numpy through the Mesh
    `scratch` (fast on big meshes, where Python loops over every face would take seconds)."""
    import numpy as np
    scratch.clear_geometry()
    bm.to_mesh(scratch)
    nl, ne = len(scratch.loops), len(scratch.edges)
    if not nl:
        return 0, 0, 0.0
    edge_idx = np.empty(nl, dtype=np.int32)
    scratch.loops.foreach_get("edge_index", edge_idx)
    per_edge = np.bincount(edge_idx, minlength=ne)
    boundary = int(np.count_nonzero(per_edge == 1))
    nonmanifold = int(np.count_nonzero(per_edge > 2))
    scratch.calc_loop_triangles()
    nt = len(scratch.loop_triangles)
    co = np.empty(len(scratch.vertices) * 3, dtype=np.float64)
    scratch.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    tri = np.empty(nt * 3, dtype=np.int32)
    scratch.loop_triangles.foreach_get("vertices", tri)
    tri = tri.reshape(-1, 3)
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    vol = float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)
    return boundary, nonmanifold, vol


def delete_loose(bm):
    loose_e = [e for e in bm.edges if not e.link_faces]
    if loose_e:
        bmesh.ops.delete(bm, geom=loose_e, context='EDGES')
    loose_v = [v for v in bm.verts if not v.link_faces]
    if loose_v:
        bmesh.ops.delete(bm, geom=loose_v, context='VERTS')


def _shrunk(co_list, k=1e-3):
    c = sum(co_list, Vector()) / len(co_list)
    return [p + (c - p) * k for p in co_list]


def _poly_bvh(polys):
    """BVH from a list of coordinate lists (one per polygon)."""
    verts, idx = [], []
    for poly in polys:
        start = len(verts)
        verts.extend(poly)
        idx.append(tuple(range(start, start + len(poly))))
    return BVHTree.FromPolygons(verts, idx, all_triangles=False) if idx else None


def _lies_on(bvh, normal_of, polys, poly_normals, tol, skip=frozenset()):
    """True when a polygon in `polys` lies on (coplanar with, and over) a polygon of `bvh` (not one whose index
    is in `skip`). Samples the centre and points just inside each corner: Blender's BVH overlap test ignores
    coplanar triangles. normal_of(index) gives a bvh polygon's normal."""
    if bvh is None:
        return False
    for poly, pn in zip(polys, poly_normals):
        if pn.length < 1e-12:
            continue
        for p in [sum(poly, Vector()) / len(poly)] + _shrunk(poly, 0.05):
            hit = bvh.find_nearest(p, tol)
            if hit[0] is not None and hit[2] not in skip and abs(normal_of(hit[2]).dot(pn)) > 1.0 - 1e-5:
                return True
    return False


# ---------------------------------------------------------------- 1. extrude without a boolean

def extrude_hits(bm, faces, border, n, d, cache=None, sliding_walls=False):
    """Would a plain extrude of `faces` by d along n reach any other part of the mesh? Conservative: touching
    counts as reaching (the boolean then handles it). `border`: (vert a, vert b) of each border edge, in the
    winding of the selected face beside it.

    Blender's BVH overlap test misses triangles that only meet along an edge or lie in one plane, which is
    common on grid-like meshes, so besides it the swept volume is tested directly: other vertices inside it,
    the paths of the moving vertices through other faces, and other edges through the new faces.
    sliding_walls: the faces slide along the walls beside them (push / pull going in), so new walls lying on
    those walls are expected, not a hit."""
    tol = max(1e-6, abs(d) * 1e-5)
    region_verts = {v for f in faces for v in f.verts}
    key = (len(bm.verts), len(bm.faces))
    slot = cache.get("rest") if cache is not None else None
    bvh = slot[1] if slot is not None and slot[0] == key else None
    if bvh is None:
        bm.faces.index_update()
        bm.faces.ensure_lookup_table()
        bvh = BVHTree.FromBMesh(bm)  # the whole mesh, built in C; hits on the selected faces are skipped
        if cache is not None:
            cache["rest"] = (key, bvh)
    bm.faces.ensure_lookup_table()
    bm.verts.index_update()
    sel_idx = frozenset(f.index for f in faces)
    bm_faces = bm.faces

    def normal_of(i):
        return bm_faces[i].normal

    off = n * d
    walls = [[a.co, b.co, b.co + off, a.co + off] for a, b in border]
    caps = [[v.co + off for v in f.verts] for f in faces]
    new = walls + caps

    # 1. crossing faces (the generic case)
    if any(i not in sel_idx for i, _j in bvh.overlap(_poly_bvh([_shrunk(p) for p in new]))):
        return True
    # 2. new faces lying on existing ones
    wall_n = [(p[1] - p[0]).cross(p[3] - p[0]).normalized() for p in walls]
    if sliding_walls:
        if _lies_on(bvh, normal_of, caps, [f.normal for f in faces], tol, sel_idx):
            return True
    elif _lies_on(bvh, normal_of, new, wall_n + [f.normal for f in faces], tol, sel_idx):
        return True

    # the swept volume's box, to skip far geometry quickly
    pts = [v.co for v in region_verts] + [v.co + off for v in region_verts]
    lo, hi = _bbox(pts)
    lo -= Vector((tol, tol, tol))
    hi += Vector((tol, tol, tol))

    def near(p):
        return lo.x <= p.x <= hi.x and lo.y <= p.y <= hi.y and lo.z <= p.z <= hi.z

    # 3. other vertices inside the swept volume: straight back along the extrude direction they land on the
    #    selected faces within the distance
    region_bvh = _poly_bvh([[v.co for v in f.verts] for f in faces])
    back = -off.normalized()
    dist = abs(d)
    for v in bm.verts:
        if v in region_verts:
            continue
        co = v.co
        if not near(co):
            continue
        hit = region_bvh.ray_cast(co - back * tol, back, dist + 2 * tol)
        if hit[0] is not None and hit[3] > tol:
            return True

    # 4. the moving vertices' paths and the new cap's edges through other faces (not faces at that vertex)
    region_idx = {v.index for v in region_verts}
    segs = [(v.co, v.co + off, v) for v in region_verts]
    segs += [(a.co + off, b.co + off, None) for a, b in border]
    for p, q, vert in segs:
        dvec = q - p
        length = dvec.length
        if length < tol:
            continue
        dvec /= length
        start = p + dvec * tol
        reach = length - tol
        while reach > 0:
            hit = bvh.ray_cast(start, dvec, reach)
            if hit[0] is None:
                break
            hf = bm_faces[hit[2]]
            if hit[2] not in sel_idx and (vert is None or vert not in hf.verts):
                return True
            step = hit[3] + tol
            start = start + dvec * step
            reach -= step

    # 5. other edges through the new walls and cap (edges at the selection's border slide along them)
    new_bvh = _poly_bvh(new)
    for e in bm.edges:
        v0, v1 = e.verts
        if v0.index in region_idx or v1.index in region_idx:
            continue
        a, b = v0.co, v1.co
        if any(max(a[k], b[k]) < lo[k] or min(a[k], b[k]) > hi[k] for k in range(3)):
            continue
        dvec = b - a
        length = dvec.length
        if length < tol:
            continue
        hit = new_bvh.ray_cast(a, dvec / length, length)
        if hit[0] is not None:
            return True
    return False


def extrude(bm, faces, n, d):
    """Plain extrude of `faces` by d along n; the new cap faces end up selected."""
    global last_path
    last_path = 'NONE'
    ret = bmesh.ops.extrude_face_region(bm, geom=list(faces), use_keep_orig=False)
    new_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    new_faces = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMFace)]
    bmesh.ops.translate(bm, vec=n * d, verts=new_verts)
    bmesh.ops.delete(bm, geom=list(faces), context='FACES')
    for f in new_faces:
        f.select_set(True)
    bm.normal_update()
    return new_faces


# ---------------------------------------------------------------- 2-5. the boolean

class Rig:
    """Two hidden helper objects in a private scene, made once per drag: a mesh with a Boolean modifier and the
    cutter. Each run only swaps their mesh data and evaluates once. Nothing in the user's scene changes and no
    objects are added or removed during a drag (that would rebuild the dependency graph of the whole scene)."""

    def __init__(self, context):
        self.context = context
        self.scene = bpy.data.scenes.new(".keyops_bool_eval")
        coll = self.scene.collection
        self.base_me = bpy.data.meshes.new(".keyops_bool_base")
        self.base = bpy.data.objects.new(".keyops_bool_base", self.base_me)
        self.cut_me = bpy.data.meshes.new(".keyops_bool_cutter")
        self.cutter = bpy.data.objects.new(".keyops_bool_cutter", self.cut_me)
        for o in (self.base, self.cutter):
            coll.objects.link(o)
        self.cutter.display_type = 'WIRE'
        self.cutter.hide_render = True
        self.mod = self.base.modifiers.new("Boolean", 'BOOLEAN')
        self.mod.object = self.cutter
        if hasattr(self.mod, "use_self"):
            self.mod.use_self = False

    def run(self, bm, cutter_bm, op, solver):
        """bm with cutter_bm added / cut away, as a new bmesh (caller frees it)."""
        self.base_me.clear_geometry()
        bm.to_mesh(self.base_me)
        self.cut_me.clear_geometry()
        cutter_bm.to_mesh(self.cut_me)
        self.base_me.update()
        self.cut_me.update()
        if self.mod.operation != op:
            self.mod.operation = op
        if self.mod.solver != solver:
            self.mod.solver = solver
        with self.context.temp_override(scene=self.scene, view_layer=self.scene.view_layers[0]):
            dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        me = bpy.data.meshes.new_from_object(self.base.evaluated_get(dg), depsgraph=dg)
        out = bmesh.new()
        out.from_mesh(me)
        bpy.data.meshes.remove(me)
        return out

    def remove(self):
        for o in (getattr(self, "base", None), getattr(self, "cutter", None)):
            if o is not None:
                bpy.data.objects.remove(o)
        for m in (getattr(self, "base_me", None), getattr(self, "cut_me", None)):
            if m is not None:
                bpy.data.meshes.remove(m)
        self.base = self.cutter = self.base_me = self.cut_me = None
        if getattr(self, "scene", None) is not None:
            bpy.data.scenes.remove(self.scene)
            self.scene = None


def _cap_holes(bm):
    """Close every hole with tagged cap faces. Returns the tag layer."""
    layer = bm.faces.layers.int.get(CAP) or bm.faces.layers.int.new(CAP)
    boundary = [e for e in bm.edges if e.is_boundary]
    if boundary:
        res = bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
        for f in res["faces"]:
            f[layer] = 1
    return layer


def _valid(before, after, op, cutter_vol, min_change=0.0):
    """Is a boolean result plausible? before/after: (boundary, nonmanifold, volume). min_change: the least the
    volume must change when the result is right (a silently failed boolean returns the mesh unchanged)."""
    b0, m0, v0 = before
    b1, m1, v1 = after
    if b1 > b0 or m1 > m0:
        return False  # new holes, or faces left inside
    if b0 == 0 and m0 == 0:
        s = 1.0 if v0 >= 0 else -1.0
        dv = (v1 - v0) * s
        tol = 1e-4 * (abs(v0) + cutter_vol) + 1e-9
        if op == 'UNION' and not (-tol <= dv <= cutter_vol + tol):
            return False
        if op == 'DIFFERENCE' and not (-cutter_vol - tol <= dv <= tol):
            return False
    if abs(v1 - v0) < min_change:  # unchanged: the solver gave up silently (open meshes too)
        return False
    return True


def _key(co, tol):
    """A position rounded to the tolerance: equal for points that are the same within it."""
    q = max(tol, 1e-9)
    return (round(co.x / q), round(co.y / q), round(co.z / q))


def _reweld(bm, single_keys, dist):
    """Merge result vertices sharing a position that held only one vertex in the input."""
    if not single_keys:
        return
    groups = {}
    tol = dist * 100.0
    for v in bm.verts:
        k = _key(v.co, tol)
        if k in single_keys:
            groups.setdefault(k, []).append(v)
    verts = [v for g in groups.values() if len(g) > 1 for v in g]
    if verts:
        bmesh.ops.remove_doubles(bm, verts=verts, dist=dist)


def _weld_slivers(bm, cutter_bvh, dist):
    """After a boolean with a widened cutter: merge the vertices on the cutter's surface that lie within `dist`
    of each other and drop the faces that collapse, so the hair-thin sliver it left disappears."""
    near = [v for v in bm.verts if cutter_bvh.find_nearest(v.co, dist)[0] is not None]
    if near:
        bmesh.ops.remove_doubles(bm, verts=near, dist=dist)
        bmesh.ops.dissolve_degenerate(bm, dist=dist, edges=bm.edges[:])
        delete_loose(bm)
    bm.normal_update()


def _widened(cutter, k):
    """A copy of the cutter inflated by k times its size (every vertex moved out along its normal): its walls no
    longer pass exactly through the mesh's own vertices and edges, the case that trips up the solvers.
    Returns (copy, distance moved)."""
    out = cutter.copy()
    out.normal_update()
    lo, hi = _bbox([v.co for v in out.verts])
    dist = (hi - lo).length * k
    for v in out.verts:
        v.co += v.normal * dist
    out.normal_update()
    return out, dist


SHEET = "sheet"  # boolean() error: the reachable part is a flat open sheet with no inside, no boolean applies


def boolean(rig, bm, cutter, op, mode='AUTO', min_change=0.0, cache=None):
    """Add (op 'UNION') or cut ('DIFFERENCE') the closed bmesh `cutter` into the edit bmesh `bm`, in place.
    min_change: the least the volume must change for a result to count as right.
    Returns (solver used, None) or (None, error message, or SHEET)."""
    global last_path
    used, err = _boolean(rig, bm, cutter, op, mode, min_change, cache)
    last_path = used
    return used, err


def _boolean(rig, bm, cutter, op, mode, min_change, cache):
    ccos = [v.co for v in cutter.verts]
    cbox = _bbox(ccos)
    size = max((cbox[1] - cbox[0]).length, 1e-9)
    tol = size * 1e-4
    # face islands and their boxes, as face indices: the same for every update of a drag (the drag restores the
    # original mesh before each one), so they are worked out once
    bm.faces.index_update()
    bm.faces.ensure_lookup_table()
    key = (len(bm.verts), len(bm.faces))
    slot = cache.get("islands") if cache is not None else None
    if slot is None or slot[0] != key:
        isl_boxes = [([f.index for f in isl], _bbox([v.co for f in isl for v in f.verts])) for isl in islands(bm.faces)]
        if cache is not None:
            cache["islands"] = (key, isl_boxes)
    else:
        isl_boxes = slot[1]
    affected = [bm.faces[i] for idx, box in isl_boxes if _bbox_overlap(box, cbox, tol) for i in idx]
    if not affected:
        if op == 'UNION':  # nothing to merge with: the cutter becomes part of the mesh as it is
            layer = cutter.faces.layers.int.get(CAP)
            if layer is not None:
                for f in cutter.faces:
                    f.select_set(False)
                for f in cutter.faces:
                    if f[layer] == 2:
                        f.select_set(True)
                cutter.faces.layers.int.remove(layer)
            tmp = bpy.data.meshes.new(".keyops_bool_tmp")
            cutter.to_mesh(tmp)
            bm.from_mesh(tmp)
            bpy.data.meshes.remove(tmp)
            return 'NONE', None
        return 'NONE', None

    # the reachable islands, on their own and closed
    keep = {f.index for f in affected}
    work = bm.copy()
    work.faces.ensure_lookup_table()
    drop = [f for f in work.faces if f.index not in keep]
    if drop:
        bmesh.ops.delete(work, geom=drop, context='FACES')
    delete_loose(work)
    counts = {}
    for v in work.verts:
        k = _key(v.co, tol)
        counts[k] = counts.get(k, 0) + 1
    single_keys = {k for k, c in counts.items() if c == 1}
    _cap_holes(work)
    work.normal_update()
    scratch = bpy.data.meshes.new(".keyops_bool_stats")
    b0, m0, vol0 = mesh_stats(work, scratch)
    contiguous = all(e.is_contiguous for e in work.edges if len(e.link_faces) == 2)
    wlo, whi = _bbox([v.co for v in work.verts])
    ext = whi - wlo
    if b0 == 0 and m0 == 0 and abs(vol0) <= 1e-6 * max(ext.x * ext.y * ext.z, ext.length ** 3 * 1e-6) + 1e-12:
        work.free()
        bpy.data.meshes.remove(scratch)
        return None, SHEET
    # an inside-out mesh: turn it the right way for the boolean, and back again afterwards
    flipped = b0 == 0 and m0 == 0 and contiguous and vol0 < 0
    if flipped:
        bmesh.ops.reverse_faces(work, faces=work.faces[:])
        vol0 = -vol0
        op = {'UNION': 'DIFFERENCE', 'DIFFERENCE': 'UNION'}[op]
    before = (b0, m0, vol0)
    cutter_vol = abs(signed_volume(cutter))

    items = solver_items()
    fast = fast_name()
    exact_tail = [('EXACT', 0.0, False), ('EXACT', 0.0, True), ('EXACT', 4e-5, False)]
    if mode == 'EXACT':
        attempts = exact_tail
    elif mode == 'AUTO' and 'MANIFOLD' in items and b0 == 0 and m0 == 0 and contiguous:
        attempts = [('MANIFOLD', 0.0, False), ('MANIFOLD', 4e-5, False)] + exact_tail
    else:
        # Fast first (Blender 4.2, or a mesh Manifold can't take). Fast breaks where the cutter's faces lie on
        # the mesh's faces or its walls run exactly through the mesh's edges; then it runs on a cutter widened
        # by a hair and the hair-thin sliver is welded away again. Exact only when that fails too.
        work.faces.ensure_lookup_table()
        wfaces = work.faces
        cpolys = [[v.co for v in f.verts] for f in cutter.faces]
        coincident = _lies_on(BVHTree.FromBMesh(work), lambda i: wfaces[i].normal, cpolys,
                              [f.normal for f in cutter.faces], tol)
        attempts = ([] if coincident else [(fast, 0.0, False)])
        attempts += [(fast, 4e-5, False), (fast, 1e-4, False), (fast, 4e-4, False)]
        attempts += exact_tail

    # during a drag, start from what worked on the previous update (the mesh is the same, only the distance
    # changes), then try the rest in order
    if cache is not None and cache.get("attempt") in attempts:
        first = cache["attempt"]
        attempts = [first] + [a for a in attempts if a != first]

    cutter_bvh = _poly_bvh([[v.co for v in f.verts] for f in cutter.faces])
    result = used = None
    for attempt in attempts:
        solver, k, hole_tolerant = attempt
        if hole_tolerant and not hasattr(rig.mod, "use_hole_tolerant"):
            continue
        if hasattr(rig.mod, "use_hole_tolerant") and rig.mod.use_hole_tolerant != hole_tolerant:
            rig.mod.use_hole_tolerant = hole_tolerant
        if k:
            cut, slack = _widened(cutter, k)
        else:
            cut, slack = cutter, 0.0
        out = rig.run(work, cut, op, solver)
        if k:
            cut.free()
            _weld_slivers(out, cutter_bvh, slack * 3.0)
        else:  # zero-length edges and zero-area faces some solvers leave where the cut meets existing edges
            bmesh.ops.dissolve_degenerate(out, dist=tol * 0.01, edges=out.edges[:])
            delete_loose(out)
            out.normal_update()
        after = mesh_stats(out, scratch)
        ok = len(out.faces) and _valid(before, after, op, cutter_vol, min_change)
        if DEBUG:
            print("BOOLDBG", solver, op, f"widened {k}" if k else "", "tolerant" if hole_tolerant else "",
                  "before", before, "after", after, "cutter", cutter_vol, "ok", bool(ok))
        if ok:
            result, used = out, solver + ("+widened" if k else "") + ("+tolerant" if hole_tolerant else "")
            if cache is not None:
                cache["attempt"] = attempt
            break
        out.free()
    if hasattr(rig.mod, "use_hole_tolerant"):
        rig.mod.use_hole_tolerant = False
    bpy.data.meshes.remove(scratch)
    work.free()
    if result is None:
        return None, "The boolean failed on this mesh"

    layer = result.faces.layers.int.get(CAP)
    if DEBUG:
        from collections import Counter
        print("BOOLDBG tags", layer is not None and Counter(f[layer] for f in result.faces))
    if layer is not None:
        want = 2 if any(f[layer] == 2 for f in result.faces) else 3
        for f in result.faces:  # deselect everything first: deselecting a face also clears its edges
            f.select_set(False)
        for f in result.faces:
            if f[layer] == want:
                f.select_set(True)
        caps = [f for f in result.faces if f[layer] == 1]
        if caps:
            bmesh.ops.delete(result, geom=caps, context='FACES_ONLY')
        result.faces.layers.int.remove(layer)
    delete_loose(result)
    if flipped:
        bmesh.ops.reverse_faces(result, faces=result.faces[:])

    # vertices that were one vertex before and came back as several (Manifold splits a vertex where two parts
    # touch at a point): one again
    _reweld(result, single_keys, tol * 0.01)

    # merge back: the untouched part of the mesh stays exactly as it was; vertices it shares with the rebuilt
    # part (islands touching at a point) are welded again
    aff_set = set(affected)
    seam_keys = {_key(v.co, tol) for f in affected for v in f.verts if any(lf not in aff_set for lf in v.link_faces)}
    for f in bm.faces:
        f.select_set(False)
    bmesh.ops.delete(bm, geom=affected, context='FACES')
    tmp = bpy.data.meshes.new(".keyops_bool_tmp")
    result.to_mesh(tmp)
    result.free()
    bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)
    if seam_keys:
        seam = [v for v in bm.verts if _key(v.co, tol) in seam_keys]
        bmesh.ops.remove_doubles(bm, verts=seam, dist=tol * 0.01)
    return used, None
