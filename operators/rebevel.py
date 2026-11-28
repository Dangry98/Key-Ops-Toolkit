"""Re-Bevel: change or remove a bevel that is already in the mesh.

Select the faces of a bevel (the strip of faces that rounds an edge) or just one edge ring across it; Follow
Loops takes the whole bevel along its length. The strip's two borders are its rails. For each cross-section the
operator finds the sharp corner the bevel was made from: the point where the flat faces beside the strip meet
(intersecting their planes, so a bevel around a cylinder cap comes back to exactly its old corner, and running
it again and again moves nothing). It folds the cross-section back into that corner and bevels the corner again.
0 segments or 0 width leaves the corner sharp (removes the bevel).

It runs as a modal: it starts from the bevel's own segments and width, the wheel changes the segments, W and P
jump into changing the width / profile with the mouse and back out.
"""

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector
from mathutils.geometry import intersect_plane_plane


def _strip_faces(bm):
    faces = {f for f in bm.faces if f.select}
    if not faces:
        # an edge ring across the bevel: the faces along its edges
        edges = [e for e in bm.edges if e.select]
        faces = {f for e in edges for f in e.link_faces}
    return {f for f in faces if len(f.verts) == 4}  # a bevel strip is quads (caps and junctions aren't)


def _border_chains(faces):
    """The strip's border, split into chains at its corners (where the border turns round one face)."""
    border = {e for f in faces for e in f.edges if sum(1 for lf in e.link_faces if lf in faces) == 1}
    at = {}
    for e in border:
        for v in e.verts:
            at.setdefault(v, []).append(e)

    def is_corner(v):
        es = at.get(v, [])
        if len(es) != 2:
            return len(es) > 2
        shared = set(es[0].link_faces) & set(es[1].link_faces) & faces
        return bool(shared)

    chains, left = [], set(border)
    while left:
        e0 = left.pop()
        chain = [e0]
        for end in e0.verts:  # grow both ways until a corner (or back round)
            v, prev = end, e0
            while not is_corner(v):
                nxt = [x for x in at.get(v, []) if x is not prev and x in left]
                if not nxt:
                    break
                prev = nxt[0]
                left.discard(prev)
                chain.append(prev)
                v = prev.other_vert(v)
        chains.append(set(chain))
    return chains


def _bend(chain, faces):
    """How sharply the faces outside the strip meet it along this chain (average angle, radians)."""
    total, n = 0.0, 0
    for e in chain:
        inside = [f for f in e.link_faces if f in faces]
        outside = [f for f in e.link_faces if f not in faces]
        if inside and outside:
            total += inside[0].normal.angle(outside[0].normal, 0.0)
            n += 1
    return total / n if n else 10.0


def _rails(faces):
    """The bevel's two rails: closed borders as they are; on an open strip the two border chains that meet
    their neighbours most smoothly (the ends meet the side faces at a hard angle)."""
    chains = _border_chains(faces)
    if len(chains) > 2:
        chains = sorted(chains, key=lambda c: _bend(c, faces))[:2]
    return chains


def _cross_sections(faces, rail_a, rail_b):
    """For each vertex on rail A: the path across the strip to rail B, through the strip's inner edges."""
    verts_a = {v for e in rail_a for v in e.verts}
    verts_b = {v for e in rail_b for v in e.verts}
    rails = rail_a | rail_b
    inner = {e for f in faces for e in f.edges if e not in rails}  # the strip's ends are cross-sections too
    sections = []
    for va in verts_a:
        starts = [e for e in va.link_edges if e in inner]
        if len(starts) != 1:
            continue  # a corner of the strip (where it ends): no single way across
        path, prev, cur = [va], starts[0], starts[0].other_vert(va)
        ok = True
        while cur not in verts_b:
            path.append(cur)
            nxt = [e for e in cur.link_edges if e in inner and e is not prev
                   and not set(e.link_faces) & set(prev.link_faces) & faces]
            if len(nxt) != 1 or len(path) > 512:
                ok = False
                break
            prev, cur = nxt[0], nxt[0].other_vert(cur)
        if ok:
            path.append(cur)
            sections.append(path)
    return sections


def _outside_planes(v, faces, rails):
    """Planes (point, normal) of the flat faces beside the strip at this vertex: those along the rail, plus at
    the strip's ends the side faces there (they hold the old corner too)."""
    out = []
    for f in v.link_faces:
        if f in faces or f.normal.length < 1e-9:
            continue
        n = f.normal.normalized()
        if not any(abs(n.dot(m)) > 1.0 - 1e-6 and abs(n.dot(f.verts[0].co - p)) < 1e-6 for p, m in out):
            out.append((f.verts[0].co.copy(), n))
    return out


def _corner(section, faces, rails):
    """The old sharp corner for this cross-section: the point closest to all the planes of the flat faces
    beside it (their meeting point when there are three, as at a cylinder cap's rim; with two, the point of
    their meeting line nearest the cross-section)."""
    va, vb = section[0], section[-1]
    planes = _outside_planes(va, faces, rails) + _outside_planes(vb, faces, rails)
    mid = sum((v.co for v in section), Vector()) / len(section)
    if len(planes) < 2:
        return mid
    # least squares with a tiny pull to the cross-section's middle (it settles a line of solutions)
    lam = 1e-6
    a = Matrix(((lam, 0.0, 0.0), (0.0, lam, 0.0), (0.0, 0.0, lam)))
    b = mid * lam
    for p, n in planes:
        a += Matrix(((n.x * n.x, n.x * n.y, n.x * n.z), (n.y * n.x, n.y * n.y, n.y * n.z),
                     (n.z * n.x, n.z * n.y, n.z * n.z)))
        b += n * n.dot(p)
    try:
        c = a.inverted() @ b
    except ValueError:
        return mid
    if (c - mid).length > 10.0 * max((v.co - mid).length for v in section) + 1e-6:
        return mid  # nearly parallel faces: no sensible corner
    return c


TURN_LIMIT = 1.31  # 75 degrees: a mitred corner of a bevel turns less, a bevel's end against a side face more


def _ring_faces(faces):
    """Follow Loops: the whole bevel along its length. From each face, walk across its 'cross' edges (the pair
    of opposite edges the strip continues through) from quad to quad until the strip ends."""
    faces = set(faces)
    out = set(faces)
    for f in faces:
        if len(f.edges) != 4:
            continue
        loops = list(f.loops)
        pairs = ((loops[0].edge, loops[2].edge), (loops[1].edge, loops[3].edge))

        def smooth(edge):
            o = [g for g in edge.link_faces if g is not f]
            if not o or any(len(g.verts) != 4 for g in o):
                return 0.0  # the strip ends here (at an n-gon or an open edge): this is its length direction
            return min(f.normal.angle(g.normal, 3.0) for g in o)
        # the strip runs through the pair whose neighbours continue most smoothly; on a tie (a curved bevel
        # can turn as much along its length as between its segments) the shorter pair: the bevel's own width
        cross = min(pairs, key=lambda pr: (round(max(smooth(pr[0]), smooth(pr[1])), 3),
                                           pr[0].calc_length() + pr[1].calc_length()))
        for e in cross:
            cur_f, cur_e = f, e
            for _step in range(100000):
                nxt = [g for g in cur_e.link_faces if g is not cur_f]
                if len(nxt) != 1 or len(nxt[0].edges) != 4 or nxt[0] in out:
                    break
                if cur_f.normal.angle(nxt[0].normal, 3.0) > TURN_LIMIT:
                    break  # the end of the bevel: it meets a side face, not more of itself
                g = nxt[0]
                out.add(g)
                gl = next(lp for lp in g.loops if lp.edge is cur_e)
                cur_f, cur_e = g, gl.link_loop_next.link_loop_next.edge
    return out


def _strip(faces):
    """(faces, rails, sections) when the faces form a bevel strip, else None. Faces much bigger than the strip's
    own (a face the selection took along, like the top of a box whose edges were bevelled) are left out."""
    for attempt in (faces, None):
        if attempt is None:
            areas = sorted(f.calc_area() for f in faces)
            med = areas[len(areas) // 2]
            attempt = {f for f in faces if f.calc_area() <= 3.0 * med}
            if len(attempt) == len(faces) or not attempt:
                return None
        rails = _rails(attempt)
        if len(rails) != 2:
            continue
        sections = _cross_sections(attempt, rails[0], rails[1])
        if len(sections) >= 2:
            return attempt, rails, sections
    return None


def _walk_from(strip, ends):
    """The strip plus the quads the bevel continues into through these end edges (stopping where it meets a side
    face or an n-gon)."""
    out = set(strip)
    for e in ends:
        cur_f = next(g for g in e.link_faces if g in strip)
        cur_e = e
        for _step in range(100000):
            nxt = [g for g in cur_e.link_faces if g is not cur_f]
            if len(nxt) != 1 or len(nxt[0].edges) != 4 or nxt[0] in out:
                break
            if cur_f.normal.angle(nxt[0].normal, 3.0) > TURN_LIMIT:
                break
            g = nxt[0]
            out.add(g)
            gl = next(lp for lp in g.loops if lp.edge is cur_e)
            cur_f, cur_e = g, gl.link_loop_next.link_loop_next.edge
    return out


def analyse(bm, follow=True):
    """The selected bevel: (faces, sections with their corners, measured width, segments) or None."""
    faces = _strip_faces(bm)
    if not faces:
        return None
    found = _strip(faces)
    if follow:
        if found is not None and len(found[2]) >= 3:
            # a strip longer than one face knows its rails: carry on only from its open ends
            strip, rails, _sections = found
            rail_set = rails[0] | rails[1]
            ends = [e for f in strip for e in f.edges
                    if e not in rail_set and sum(1 for g in e.link_faces if g in strip) == 1]
            grown = _walk_from(strip, ends) if ends else strip
        else:
            grown = _ring_faces(found[0] if found else faces)
        followed = _strip(grown) if grown is not (found[0] if found else None) else None
        if followed is not None and (found is None or len(followed[2]) >= len(found[2])):
            found = followed
    if found is None:
        return None
    faces, rails, sections = found
    rail_set = rails[0] | rails[1]
    targets = [(sec, _corner(sec, faces, rail_set)) for sec in sections]
    # the width: how far each rail lies from the corner line (measured square to it: on a polygonal cylinder the
    # rail's vertices sit on mitres, a little further from the corner point than the bevel's width)
    corner_at = {sec[0]: c for sec, c in targets}
    widths = []
    for sec, c in targets:
        # the old edges at this corner run to the neighbouring corners; Blender's width is the distance square to
        # each of them (at a mitre or on a polygonal cylinder the corner point itself is further away)
        nbs = [e.other_vert(sec[0]) for e in sec[0].link_edges if e in rail_set]
        dirs = [(corner_at[v] - c) for v in nbs if v in corner_at and (corner_at[v] - c).length > 1e-9]
        w = []
        for v in (sec[0], sec[-1]):
            off = v.co - c
            if not dirs:
                w.append(off.length)
                continue
            for d in dirs:
                dn = d.normalized()
                w.append((off - dn * off.dot(dn)).length)
        widths.append(min(w) if dirs else sum(w) / len(w))
    return faces, targets, sum(widths) / len(widths), max(len(sec) - 1 for sec, _c in targets)


def rebuild(bm, data, segments, width, profile):
    """Fold the bevel back into its corner and bevel that corner again (0 segments or width: leave it sharp).
    Only the new bevel's faces (or the sharp corner edges) end up selected."""
    _faces, targets, _w, _s = data
    merged = []
    for sec, c in targets:
        sec = [v for v in sec if v.is_valid]
        if not sec:
            continue
        bmesh.ops.pointmerge(bm, verts=sec, merge_co=c)
        merged.append(next((v for v in sec if v.is_valid), None))
    merged = [v for v in merged if v is not None and v.is_valid]
    ms = set(merged)
    corner = {e for v in merged for e in v.link_edges if e.other_vert(v) in ms}
    bmesh.ops.remove_doubles(bm, verts=merged, dist=1e-6)
    corner = [e for e in corner if e.is_valid]
    for elems in (bm.verts, bm.edges, bm.faces):
        for e in elems:
            e.select = False
    for e in corner:
        e.smooth = False
    if segments > 0 and width > 0 and corner:
        verts = list({v for e in corner for v in e.verts})
        res = bmesh.ops.bevel(bm, geom=corner + verts, offset=width, offset_type='OFFSET', segments=segments,
                              profile=profile, affect='EDGES', clamp_overlap=True)
        for f in res["faces"]:
            f.select_set(True)
    else:
        for e in corner:
            e.select_set(True)
    bm.normal_update()


DIGITS = {'ZERO': "0", 'ONE': "1", 'TWO': "2", 'THREE': "3", 'FOUR': "4", 'FIVE': "5", 'SIX': "6",
          'SEVEN': "7", 'EIGHT': "8", 'NINE': "9"}


class KEYOPS_OT_rebevel(bpy.types.Operator):
    """Change a bevel that's already in the mesh: wheel for segments, W for width, P for profile (0 segments or
    0 width removes it). Select the bevel's faces, or an edge ring across it"""
    bl_idname = "keyops.rebevel"
    bl_label = "Re-Bevel"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    segments: IntProperty(name="Segments", default=-1, min=-1, soft_min=0, max=128,
                          description="Segments of the new bevel (0: remove the bevel)") # type: ignore
    width: FloatProperty(name="Width", default=-1.0, min=-1.0, soft_min=0.0, soft_max=10.0, subtype='DISTANCE',
                         description="Width of the new bevel (0: remove the bevel)") # type: ignore
    profile: FloatProperty(name="Profile", default=0.5, min=0.0, max=1.0, subtype='FACTOR') # type: ignore
    follow_loops: BoolProperty(name="Follow Loops", default=True,
                               description="Take the whole bevel along its length; off: only the selected part"
                               ) # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "segments")
        layout.prop(self, "width")
        layout.prop(self, "profile")
        layout.prop(self, "follow_loops")

    # ------------------------------------------------------------ the work
    def _objects(self, context):
        return [o for o in context.objects_in_mode_unique_data if o.type == 'MESH']

    def apply(self, context):
        """Re-bevel every edited mesh with a bevel selected. Returns (done, measured width, measured segments)."""
        done, widths, segs = 0, [], []
        found = []
        for obj in self._objects(context):
            bm = bmesh.from_edit_mesh(obj.data)
            data = analyse(bm, self.follow_loops)
            if data is None:
                continue
            found.append((obj, bm, data))
            widths.append(data[2])
            segs.append(data[3])
        if not found:
            return 0, 0.0, 0
        width = self.width if self.width >= 0 else sum(widths) / len(widths)
        segments = self.segments if self.segments >= 0 else max(segs)
        for obj, bm, data in found:
            rebuild(bm, data, segments, width, self.profile)
            bmesh.update_edit_mesh(obj.data, destructive=True)
            done += 1
        return done, sum(widths) / len(widths), max(segs)

    def execute(self, context):
        done, _w, _s = self.apply(context)
        if not done:
            self.report({'WARNING'}, "Select the faces of one bevel (a strip with two borders), or an edge ring "
                                     "across it")
            return {'CANCELLED'}
        return {'FINISHED'}

    # ------------------------------------------------------------ modal
    def invoke(self, context, event):
        objs = self._objects(context)
        found = []
        for obj in objs:
            data = analyse(bmesh.from_edit_mesh(obj.data), self.follow_loops)
            if data is not None:
                found.append(data)
        if not found:
            self.report({'WARNING'}, "Select the faces of one bevel (a strip with two borders), or an edge ring "
                                     "across it")
            return {'CANCELLED'}
        # start from the bevel as it is: its own width and segments
        self.width = sum(d[2] for d in found) / len(found)
        self.segments = max(d[3] for d in found)
        if context.area is None or context.area.type != 'VIEW_3D':
            return self.execute(context)
        self.backups = {}
        for obj in objs:
            me = bpy.data.meshes.new(".keyops_rebevel_backup")
            bmesh.from_edit_mesh(obj.data).to_mesh(me)
            self.backups[obj.name] = me
        self.mode = 'SEGMENTS'
        self.typed = ""
        self.start_mouse = event.mouse_region_x
        self.start_value = 0.0
        self.pixel = self._pixel_size(context)
        self._update(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _pixel_size(self, context):
        """World size of a pixel at the bevel, so the mouse changes the width at a natural speed."""
        obj = context.edit_object
        region, rv3d = context.region, context.region_data
        if obj is None or region is None or rv3d is None:
            return 0.002
        bm = bmesh.from_edit_mesh(obj.data)
        sel = [v.co for v in bm.verts if v.select] or [v.co for v in bm.verts][:1]
        if not sel:
            return 0.002
        c = obj.matrix_world @ (sum(sel, Vector()) / len(sel))
        a = view3d_utils.region_2d_to_location_3d(region, rv3d, (region.width / 2, region.height / 2), c)
        b = view3d_utils.region_2d_to_location_3d(region, rv3d, (region.width / 2 + 100, region.height / 2), c)
        scale = obj.matrix_world.to_scale()
        return max((a - b).length / 100.0 / max(sum(scale) / 3.0, 1e-9), 1e-7)

    def _restore(self, context):
        for obj in self._objects(context):
            me = self.backups.get(obj.name)
            if me is None:
                continue
            bm = bmesh.from_edit_mesh(obj.data)
            bm.clear()
            bm.from_mesh(me)
            bmesh.update_edit_mesh(obj.data, destructive=True)

    def _update(self, context):
        self._restore(context)
        self.apply(context)
        self._status(context)

    def _status(self, context):
        if self.segments == 0 or self.width == 0:
            what = "Removed"
        else:
            what = f"Segments {self.segments}   Width {self.width:.4f}   Profile {self.profile:.2f}"
        mode = {'SEGMENTS': "", 'WIDTH': "   [Width: move the mouse, click to go back]",
                'PROFILE': "   [Profile: move the mouse, click to go back]"}[self.mode]
        typed = f"   typed: {self.typed}" if self.typed else ""
        context.area.header_text_set(
            f"Re-Bevel: {what}{mode}{typed}    Wheel Segments   W Width   P Profile   "
            f"F Follow Loops {'on' if self.follow_loops else 'off'}   LMB Confirm   RMB Cancel")

    def _finish(self, context, cancel):
        if cancel:
            self._restore(context)
        for me in self.backups.values():
            bpy.data.meshes.remove(me)
        self.backups = {}
        context.area.header_text_set(None)
        return {'CANCELLED'} if cancel else {'FINISHED'}

    def _enter(self, mode, event):
        self.mode = mode
        self.typed = ""
        self.start_mouse = event.mouse_region_x
        self.start_value = self.width if mode == 'WIDTH' else self.profile

    def _apply_typed(self):
        try:
            value = float(self.typed)
        except ValueError:
            return
        if self.mode == 'SEGMENTS':
            self.segments = max(0, min(128, int(value)))
        elif self.mode == 'WIDTH':
            self.width = max(0.0, value)
        else:
            self.profile = max(0.0, min(1.0, value))

    def modal(self, context, event):
        t, v = event.type, event.value
        if t in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'} or (t in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}
                                                                    and (event.ctrl or event.alt)):
            return {'PASS_THROUGH'}
        if t in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and v == 'RELEASE':
            return {'RUNNING_MODAL'}
        if t == 'MOUSEMOVE' and self.mode != 'SEGMENTS' and not self.typed:
            dx = (event.mouse_region_x - self.start_mouse) * (0.1 if event.shift else 1.0)
            if self.mode == 'WIDTH':
                self.width = max(0.0, self.start_value + dx * self.pixel)
            else:
                self.profile = max(0.0, min(1.0, self.start_value + dx / 300.0))
            self._update(context)
            return {'RUNNING_MODAL'}
        if (t in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and v != 'RELEASE') or (v == 'PRESS' and t in {'NUMPAD_PLUS',
                                                                                                   'NUMPAD_MINUS'}):
            step = 1 if t in {'WHEELUPMOUSE', 'NUMPAD_PLUS'} else -1
            self.segments = max(0, min(128, self.segments + step))
            self._update(context)
            return {'RUNNING_MODAL'}
        if v != 'PRESS':
            return {'RUNNING_MODAL'}
        key = t[7:] if t.startswith('NUMPAD_') else t
        if key in DIGITS or t in {'PERIOD', 'NUMPAD_PERIOD'}:
            self.typed += DIGITS.get(key, ".")
            self._apply_typed()
            self._update(context)
        elif t == 'BACK_SPACE' and self.typed:
            self.typed = self.typed[:-1]
            if self.typed:
                self._apply_typed()
            self._update(context)
        elif t == 'W':
            if self.mode == 'WIDTH':
                self.mode = 'SEGMENTS'
            else:
                self._enter('WIDTH', event)
            self._status(context)
        elif t == 'P':
            if self.mode == 'PROFILE':
                self.mode = 'SEGMENTS'
            else:
                self._enter('PROFILE', event)
            self._status(context)
        elif t == 'F':
            self.follow_loops = not self.follow_loops
            self._update(context)
        elif t in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE'}:
            if self.mode != 'SEGMENTS' and t == 'LEFTMOUSE':
                self.mode = 'SEGMENTS'  # out of width / profile, back to the main step
                self.typed = ""
                self._status(context)
                return {'RUNNING_MODAL'}
            return self._finish(context, cancel=False)
        elif t in {'RIGHTMOUSE', 'ESC'}:
            if self.mode != 'SEGMENTS':
                if self.mode == 'WIDTH':
                    self.width = self.start_value
                else:
                    self.profile = self.start_value
                self.mode = 'SEGMENTS'
                self.typed = ""
                self._update(context)
                return {'RUNNING_MODAL'}
            return self._finish(context, cancel=True)
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(KEYOPS_OT_rebevel)


def unregister():
    bpy.utils.unregister_class(KEYOPS_OT_rebevel)
