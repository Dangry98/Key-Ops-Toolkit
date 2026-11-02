from collections import defaultdict, namedtuple
from dataclasses import dataclass

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty


# ----------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------

_EPS = 1e-7

# Covered by their own comparisons, so they are not treated as "attributes".
_SKIPPED_ATTRIBUTES = {"position", "material_index"}

# attribute data_type -> (property on each element, numpy dtype, components)
_ATTRIBUTE_READERS = {
    "FLOAT": ("value", np.float32, 1),
    "INT": ("value", np.int32, 1),
    "BOOLEAN": ("value", np.bool_, 1),
    "FLOAT_VECTOR": ("vector", np.float32, 3),
    "FLOAT2": ("vector", np.float32, 2),
    "FLOAT_COLOR": ("color", np.float32, 4),
    "BYTE_COLOR": ("color", np.float32, 4),
}


@dataclass(frozen=True)
class Options:
    """Snapshot of the operator properties, so the helpers don't depend on bpy."""
    tolerance: float
    neighbor_levels: int
    positions: str            # 'NONE' | 'SHAPE' | 'EXACT'
    counts: bool
    materials: bool
    shading: bool
    attributes: bool
    attribute_values: bool
    vertex_groups: bool
    shape_keys: bool
    modifiers: bool
    dimensions: bool
    evaluated: bool


def _close(a, b, tol):
    """Relative comparison of two numbers."""
    return abs(a - b) <= tol * max(abs(a), abs(b)) + _EPS


def _all_close(a, b, tol):
    """Relative comparison of two equally long number sequences."""
    return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))


def _arrays_close(x, y, atol, rtol=0.0):
    return x.shape == y.shape and bool(np.allclose(x, y, rtol=rtol, atol=atol))


def _read(collection, prop, dtype, width=1):
    """foreach_get() into a fresh numpy array (safe for empty collections)."""
    out = np.empty(len(collection) * width, dtype=dtype)
    if out.size:
        collection.foreach_get(prop, out)
    return out


def _material_names(obj):
    return [slot.material.name_full if slot.material else "" for slot in obj.material_slots]


def _visible_attributes(mesh):
    for attr in getattr(mesh, "attributes", ()):
        if (attr.name.startswith(".")
                or attr.name in _SKIPPED_ATTRIBUTES
                or getattr(attr, "is_internal", False)):
            continue
        yield attr


def _attribute_list(mesh):
    return tuple(sorted((a.name, a.domain, a.data_type) for a in _visible_attributes(mesh)))


def _attribute_values(mesh):
    values = {}
    for attr in _visible_attributes(mesh):
        reader = _ATTRIBUTE_READERS.get(attr.data_type)
        if reader is None:
            continue
        prop, dtype, width = reader
        try:
            values[attr.name] = _read(attr.data, prop, dtype, width).astype(np.float64)
        except (RuntimeError, TypeError, ValueError, AttributeError):
            continue
    return values


# ----------------------------------------------------------------------------
# Object Mode: compare whole meshes
# ----------------------------------------------------------------------------

class MeshData:
    """Everything derived from a mesh datablock (shared by all its users)."""
    __slots__ = (
        "counts", "extent",
        "radial", "edge_lengths", "areas",                  # SHAPE fingerprint
        "co", "edges", "loop_verts", "loop_sizes",          # EXACT data
        "attr_list", "uv_names", "attr_values",
        "mat_index", "smooth",
    )

    def __init__(self):
        for name in self.__slots__:
            setattr(self, name, None)


class ObjectData:
    """MeshData plus the properties that live on the object itself."""
    __slots__ = ("mesh", "mat_usage", "mat_ids", "groups", "shape_keys", "modifiers", "dims")

    def __init__(self):
        for name in self.__slots__:
            setattr(self, name, None)


def read_mesh(mesh, opt):
    """Collect the requested properties of a mesh into a MeshData."""
    d = MeshData()
    nv, ne = len(mesh.vertices), len(mesh.edges)
    shape = opt.positions == "SHAPE"
    exact = opt.positions == "EXACT"

    sizes = None
    if opt.counts or exact:
        sizes = _read(mesh.polygons, "loop_total", np.int32)

    if opt.counts:
        mesh.calc_loop_triangles()
        d.counts = (
            nv, ne, len(mesh.polygons), len(mesh.loops), len(mesh.loop_triangles),
            int(np.count_nonzero(sizes == 3)),      # tris
            int(np.count_nonzero(sizes == 4)),      # quads
            int(np.count_nonzero(sizes > 4)),       # n-gons
        )

    if shape or exact:
        co = _read(mesh.vertices, "co", np.float32, 3).reshape(-1, 3).astype(np.float64)
        edges = _read(mesh.edges, "vertices", np.int32, 2).reshape(-1, 2)
        d.extent = float(np.ptp(co, axis=0).max()) if nv else 0.0
        if shape:
            # Rotation / translation / vertex-order independent fingerprint.
            d.radial = (np.sort(np.linalg.norm(co - co.mean(axis=0), axis=1))
                        if nv else np.empty(0))
            d.edge_lengths = np.sort(np.linalg.norm(co[edges[:, 0]] - co[edges[:, 1]], axis=1))
            d.areas = np.sort(_read(mesh.polygons, "area", np.float32))
        else:
            d.co = co
            d.edges = edges
            d.loop_verts = _read(mesh.loops, "vertex_index", np.int32)
            d.loop_sizes = sizes

    if opt.materials:
        d.mat_index = _read(mesh.polygons, "material_index", np.int32)
    if opt.shading:
        d.smooth = _read(mesh.polygons, "use_smooth", np.bool_)
    if opt.attributes:
        d.attr_list = _attribute_list(mesh)
        d.uv_names = tuple(sorted(uv.name for uv in mesh.uv_layers))
    if opt.attribute_values:
        d.attr_values = _attribute_values(mesh)
    return d


class ObjectScanner:
    """Builds ObjectData for objects, reusing work for shared mesh datablocks."""

    def __init__(self, opt, depsgraph=None):
        self.opt = opt
        self.depsgraph = depsgraph
        self._meshes = {}                 # datablock pointer -> MeshData
        self._material_ids = {"": 0}      # material name -> small int, shared by all objects

    def _material_id(self, name):
        return self._material_ids.setdefault(name, len(self._material_ids))

    def _mesh_data(self, obj):
        if self.opt.evaluated:
            evaluated = obj.evaluated_get(self.depsgraph)
            mesh = evaluated.to_mesh()
            try:
                return read_mesh(mesh, self.opt)
            finally:
                evaluated.to_mesh_clear()
        key = obj.data.as_pointer()
        data = self._meshes.get(key)
        if data is None:
            data = self._meshes[key] = read_mesh(obj.data, self.opt)
        return data

    def scan(self, obj):
        opt = self.opt
        o = ObjectData()
        o.mesh = self._mesh_data(obj)

        if opt.materials:
            slots = _material_names(obj)
            idx = o.mesh.mat_index
            if slots:
                lookup = np.array([self._material_id(n) for n in slots], dtype=np.int32)
                o.mat_ids = lookup[np.clip(idx, 0, len(slots) - 1)]
            else:
                o.mat_ids = np.zeros(len(idx), dtype=np.int32)
            ids, counts = np.unique(o.mat_ids, return_counts=True)
            o.mat_usage = tuple(zip(ids.tolist(), counts.tolist()))

        if opt.vertex_groups:
            o.groups = tuple(sorted(g.name for g in obj.vertex_groups))
        if opt.shape_keys:
            keys = obj.data.shape_keys
            o.shape_keys = tuple(sorted(k.name for k in keys.key_blocks)) if keys else ()
        if opt.modifiers:
            o.modifiers = tuple(m.type for m in obj.modifiers)
        if opt.dimensions:
            o.dims = tuple(sorted(obj.dimensions))
        return o


def _positions_match(a, b, opt):
    scale = max(a.extent, b.extent, _EPS)
    atol = opt.tolerance * scale
    if opt.positions == "SHAPE":
        return (_arrays_close(a.radial, b.radial, atol)
                and _arrays_close(a.edge_lengths, b.edge_lengths, atol)
                and _arrays_close(a.areas, b.areas, opt.tolerance * scale * scale))
    return (np.array_equal(a.edges, b.edges)
            and np.array_equal(a.loop_sizes, b.loop_sizes)
            and np.array_equal(a.loop_verts, b.loop_verts)
            and _arrays_close(a.co, b.co, atol))


def _values_match(a, b, tol):
    return a.keys() == b.keys() and all(
        _arrays_close(a[k], b[k], atol=1e-6, rtol=tol) for k in a)


def _mesh_numeric_match(a, b, opt):
    if opt.positions != "NONE" and not _positions_match(a, b, opt):
        return False
    if opt.shading:
        if opt.positions == "EXACT":
            if not np.array_equal(a.smooth, b.smooth):
                return False
        elif np.count_nonzero(a.smooth) != np.count_nonzero(b.smooth):
            return False
    if opt.attribute_values and not _values_match(a.attr_values, b.attr_values, opt.tolerance):
        return False
    return True


def objects_match(a, b, opt):
    """True when two ObjectData agree on every enabled comparison (cheap checks first)."""
    ma, mb = a.mesh, b.mesh
    if opt.counts and ma.counts != mb.counts:
        return False
    if opt.attributes and (ma.attr_list != mb.attr_list or ma.uv_names != mb.uv_names):
        return False
    if opt.materials and a.mat_usage != b.mat_usage:
        return False
    if opt.vertex_groups and a.groups != b.groups:
        return False
    if opt.shape_keys and a.shape_keys != b.shape_keys:
        return False
    if opt.modifiers and a.modifiers != b.modifiers:
        return False
    if opt.dimensions and not _all_close(a.dims, b.dims, opt.tolerance):
        return False
    if ma is not mb and not _mesh_numeric_match(ma, mb, opt):
        return False
    if opt.materials and opt.positions == "EXACT" and not np.array_equal(a.mat_ids, b.mat_ids):
        return False
    return True


# ----------------------------------------------------------------------------
# Edit Mode: compare vertices / edges / faces
# ----------------------------------------------------------------------------

# ints   = values that must match exactly (side count, valence, material, flags)
# floats = values that must match within the tolerance (lengths, angles, area)
Desc = namedtuple("Desc", ("ints", "floats"))


def _rings_match(a, b, tol):
    return len(a) == len(b) and all(
        ra[0] == rb[0] and _close(ra[1], rb[1], tol) and _close(ra[2], rb[2], tol)
        for ra, rb in zip(a, b))


class EditScanner:
    """Describes the elements of one edit-mesh, caching every result."""

    def __init__(self, obj, kind, opt):
        self.obj = obj
        self.kind = kind                      # 'VERT' | 'EDGE' | 'FACE'
        self.opt = opt
        self.bm = bmesh.from_edit_mesh(obj.data)
        self.elements = {"VERT": self.bm.verts, "EDGE": self.bm.edges, "FACE": self.bm.faces}[kind]
        self._materials = _material_names(obj)
        self._face_cache = {}
        self._cache = {}
        self._rings = {}
        self.describe = {"VERT": self._vert_desc, "EDGE": self._edge_desc,
                         "FACE": self._face_desc}[kind]

    # -- selection ---------------------------------------------------------

    def selected(self):
        return [e for e in self.elements if e.select]

    def candidates(self):
        return [e for e in self.elements if not e.select and not e.hide]

    def commit(self):
        self.bm.select_flush_mode()
        bmesh.update_edit_mesh(self.obj.data, loop_triangles=False, destructive=False)

    # -- element descriptions ------------------------------------------------

    def _material_name(self, index):
        return self._materials[min(index, len(self._materials) - 1)] if self._materials else ""

    def _face_desc(self, f):
        d = self._face_cache.get(f)
        if d is None:
            loops = f.loops
            ints = [len(loops)]
            if self.opt.materials:
                ints.append(self._material_name(f.material_index))
            if self.opt.shading:
                ints.append(bool(f.smooth))
            lengths = sorted(loop.edge.calc_length() for loop in loops)
            angles = sorted(loop.calc_angle() for loop in loops)
            d = self._face_cache[f] = Desc(tuple(ints), (f.calc_area(), *lengths, *angles))
        return d

    def _vert_desc(self, v):
        d = self._cache.get(v)
        if d is None:
            lengths = sorted(e.calc_length() for e in v.link_edges)
            angles = sorted(loop.calc_angle() for loop in v.link_loops)
            ints = (len(lengths), len(v.link_faces), bool(v.is_boundary))
            d = self._cache[v] = Desc(ints, (*lengths, *angles))
        return d

    def _edge_desc(self, e):
        d = self._cache.get(e)
        if d is None:
            ints = [len(e.link_faces)]
            if self.opt.shading:
                ints += [bool(e.smooth), bool(e.seam)]
            d = self._cache[e] = Desc(tuple(ints), (e.calc_length(), e.calc_face_angle(0.0)))
        return d

    # -- neighbourhood rings -------------------------------------------------

    def _ring_signature(self, faces):
        descs = [self._face_desc(f) for f in faces]
        return (tuple(sorted(d.ints for d in descs)),
                sum(d.floats[0] for d in descs),                          # total area
                sum(sum(d.floats[1:1 + d.ints[0]]) for d in descs))       # total edge length

    def rings(self, elem):
        """Signature of the faces touching elem, then of each further ring of faces."""
        rings = self._rings.get(elem)
        if rings is None:
            frontier = [elem] if self.kind == "FACE" else list(elem.link_faces)
            seen = set(frontier)
            rings = [self._ring_signature(frontier)]
            for _ in range(self.opt.neighbor_levels):
                step = []
                for f in frontier:
                    for e in f.edges:
                        for other in e.link_faces:
                            if other not in seen:
                                seen.add(other)
                                step.append(other)
                frontier = step
                rings.append(self._ring_signature(frontier))
            self._rings[elem] = rings
        return rings


# ----------------------------------------------------------------------------
# Operator
# ----------------------------------------------------------------------------

class KEYOPS_OT_select_similar(bpy.types.Operator):
    """Select similar meshes (Object Mode) or similar vertices, edges or faces (Edit Mode)"""
    bl_idname = "keyops.select_similar"
    bl_label = "Select Similar"
    bl_description = "Select similar meshes (Object Mode) or similar vertices, edges or faces (Edit Mode)"
    bl_options = {"REGISTER", "UNDO"}

    tolerance: FloatProperty(
        name="Tolerance",
        description="How far two values may differ and still count as similar, "
                    "relative to their size (0.01 = 1%)",
        default=0.001, min=0.0, soft_max=0.1, max=1.0, precision=4, step=1,
    )
    neighbor_levels: IntProperty(
        name="Neighbor Levels",
        description="Edit Mode: also compare this many rings of surrounding faces "
                    "(slow for high numbers)",
        default=0, min=0, max=5,
    )
    positions: EnumProperty(
        name="Positions",
        description="How vertex positions are compared (Object Mode)",
        items=[
            ("NONE", "Ignore", "Do not compare vertex positions"),
            ("SHAPE", "Shape", "Same shape regardless of rotation, mirroring or vertex order"),
            ("EXACT", "Exact", "Same vertices, in the same order, at the same local positions"),
        ],
        default="SHAPE",
    )
    compare_counts: BoolProperty(
        name="Verts Count", default=True,
        description="Vertex, edge, face, loop and triangle counts, plus tri/quad/n-gon split")
    compare_materials: BoolProperty(
        name="Materials", default=False,
        description="Materials and which faces use them")
    compare_shading: BoolProperty(
        name="Shading", default=False,
        description="Smooth/flat faces (Object Mode), plus sharp and seam edges (Edit Mode)")
    compare_attributes: BoolProperty(
        name="Attributes", default=False,
        description="Attribute names, domains and types, plus UV maps (Object Mode)")
    compare_attribute_values: BoolProperty(
        name="Attribute Values", default=False,
        description="Per-element attribute values; needs the same element order (Object Mode)")
    compare_vertex_groups: BoolProperty(
        name="Vertex Groups", default=False, description="Vertex group names")
    compare_shape_keys: BoolProperty(
        name="Shape Keys", default=False, description="Shape key names")
    compare_modifiers: BoolProperty(
        name="Modifiers", default=False, description="Modifier types and their order")
    compare_dimensions: BoolProperty(
        name="Dimensions", default=False,
        description="Object dimensions (mesh bounds x object scale), in any orientation")
    use_evaluated: BoolProperty(
        name="Evaluated Mesh", default=False,
        description="Compare the mesh after modifiers instead of the base mesh (slower)")

    # -- UI -----------------------------------------------------------------

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "tolerance")

        if context.mode == "EDIT_MESH":
            layout.prop(self, "neighbor_levels")
            col = layout.column(heading="Compare")
            col.prop(self, "compare_materials")
            col.prop(self, "compare_shading")
            return

        layout.prop(self, "positions")
        col = layout.column(heading="Compare")
        for name in ("compare_counts", "compare_materials", "compare_shading",
                     "compare_attributes", "compare_attribute_values",
                     "compare_vertex_groups", "compare_shape_keys",
                     "compare_modifiers", "compare_dimensions"):
            col.prop(self, name)
        layout.prop(self, "use_evaluated")

    # -- helpers --------------------------------------------------------------

    def _options(self):
        return Options(
            tolerance=self.tolerance,
            neighbor_levels=self.neighbor_levels,
            positions=self.positions,
            counts=self.compare_counts,
            materials=self.compare_materials,
            shading=self.compare_shading,
            attributes=self.compare_attributes,
            attribute_values=self.compare_attribute_values,
            vertex_groups=self.compare_vertex_groups,
            shape_keys=self.compare_shape_keys,
            modifiers=self.compare_modifiers,
            dimensions=self.compare_dimensions,
            evaluated=self.use_evaluated,
        )

    @staticmethod
    def _select_kind(context):
        _vert, edge, face = context.tool_settings.mesh_select_mode
        if face:
            return "FACE"
        return "EDGE" if edge else "VERT"

    # -- Object Mode ------------------------------------------------------------

    def _execute_object_mode(self, context):
        opt = self._options()
        if not (opt.positions != "NONE" or opt.counts or opt.materials or opt.shading
                or opt.attributes or opt.attribute_values or opt.vertex_groups
                or opt.shape_keys or opt.modifiers or opt.dimensions):
            self.report({"WARNING"}, "Enable at least one comparison")
            return {"FINISHED"}

        depsgraph = context.evaluated_depsgraph_get() if opt.evaluated else None
        scanner = ObjectScanner(opt, depsgraph)
        sources = [scanner.scan(o) for o in context.selected_objects if o.type == "MESH"]

        count = 0
        for obj in context.view_layer.objects:
            if (obj.type != "MESH" or obj.select_get()
                    or obj.hide_select or not obj.visible_get()):
                continue
            data = scanner.scan(obj)
            if any(objects_match(src, data, opt) for src in sources):
                obj.select_set(True)
                count += 1

        self.report({"INFO"}, f"Selected {count} similar object(s)")
        return {"FINISHED"}

    # -- Edit Mode ----------------------------------------------------------------

    def _execute_edit_mode(self, context):
        opt = self._options()
        kind = self._select_kind(context)
        use_rings = kind != "FACE" or opt.neighbor_levels > 0
        scanners = [EditScanner(o, kind, opt) for o in context.objects_in_mode_unique_data]

        # Reference elements, grouped by their exact (integer) description.
        references = defaultdict(list)
        for sc in scanners:
            for elem in sc.selected():
                desc = sc.describe(elem)
                references[desc.ints].append((sc, elem, desc.floats))
        if not references:
            self.report({"WARNING"}, "Nothing selected to compare against")
            return {"CANCELLED"}

        count = 0
        for sc in scanners:
            hits = []
            for elem in sc.candidates():
                desc = sc.describe(elem)
                for ref_sc, ref_elem, ref_floats in references.get(desc.ints, ()):
                    if not _all_close(desc.floats, ref_floats, opt.tolerance):
                        continue
                    if use_rings and not _rings_match(
                            sc.rings(elem), ref_sc.rings(ref_elem), opt.tolerance):
                        continue
                    hits.append(elem)
                    break
            for elem in hits:
                elem.select_set(True)
            if hits:
                sc.commit()
            count += len(hits)

        self.report({"INFO"}, f"Selected {count} similar element(s)")
        return {"FINISHED"}

    # -- Blender entry points --------------------------------------------------------

    def execute(self, context):
        if context.mode == "EDIT_MESH":
            return self._execute_edit_mode(context)
        return self._execute_object_mode(context)

    @classmethod
    def poll(cls, context):
        if context.mode == "EDIT_MESH":
            return context.edit_object is not None
        if context.mode == "OBJECT":
            return any(o.type == "MESH" for o in context.selected_objects)
        return False


# ----------------------------------------------------------------------------
# Registration
# ----------------------------------------------------------------------------

classes = (KEYOPS_OT_select_similar,)

_MENUS = ("VIEW3D_MT_edit_mesh_select_similar", "VIEW3D_MT_select_object", "HOPS_MT_SelectGrouped")


def menu_func(self, context):
    if context.mode == "EDIT_MESH":
        vert, edge, face = context.tool_settings.mesh_select_mode
        if face:
            self.layout.operator(KEYOPS_OT_select_similar.bl_idname, text="Faces")
        elif edge:
            self.layout.operator(KEYOPS_OT_select_similar.bl_idname, text="Edges")
        else:
            self.layout.operator(KEYOPS_OT_select_similar.bl_idname, text="Vertices")
        self.layout.separator()
    else:
        self.layout.operator(KEYOPS_OT_select_similar.bl_idname, text="Select Similar Objects")


def register_select_similar():
    for cls in classes:
        bpy.utils.register_class(cls)

    for name in _MENUS:
        try:
            if name == "VIEW3D_MT_edit_mesh_select_similar":
                getattr(bpy.types, name).prepend(menu_func)
            else:
                getattr(bpy.types, name).append(menu_func)
        except (AttributeError, ValueError):
            pass


def unregister_select_similar():
    for name in reversed(_MENUS):
        try:
            getattr(bpy.types, name).remove(menu_func)
        except (AttributeError, ValueError):
            pass
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
