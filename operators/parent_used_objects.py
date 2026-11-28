import bpy


GN_OBJECT_SOCKETS = {'NodeSocketObject'}
GN_COLLECTION_SOCKETS = {'NodeSocketCollection'}


def _add_collection_objects(collection, out):
    if collection is None:
        return
    for obj in collection.all_objects:
        out.append(obj)


def _geometry_nodes_dependencies(mod, out):
    node_group = getattr(mod, "node_group", None)
    if node_group is None or not hasattr(node_group, "interface"):
        return
    keys = set(mod.keys())
    for item in node_group.interface.items_tree:
        if getattr(item, "item_type", None) != 'SOCKET' or getattr(item, "in_out", None) != 'INPUT':
            continue
        if item.identifier not in keys:
            continue
        value = mod.get(item.identifier)
        if value is None:
            continue
        if item.socket_type in GN_OBJECT_SOCKETS and isinstance(value, bpy.types.Object):
            out.append(value)
        elif item.socket_type in GN_COLLECTION_SOCKETS and isinstance(value, bpy.types.Collection):
            _add_collection_objects(value, out)


def _generic_modifier_dependencies(mod, out):
    for prop in mod.bl_rna.properties:
        if prop.type != 'POINTER' or prop.fixed_type is None:
            continue
        type_name = prop.fixed_type.identifier
        if type_name == 'Object':
            value = getattr(mod, prop.identifier, None)
            if value is not None:
                out.append(value)
        elif type_name == 'Collection':
            _add_collection_objects(getattr(mod, prop.identifier, None), out)


def get_modifier_dependencies(obj, booleans_only=False):
    """Return objects referenced by obj's modifiers, in modifier order, without duplicates."""
    found = []
    for mod in obj.modifiers:
        if mod.type == 'BOOLEAN':
            if getattr(mod, "operand_type", 'OBJECT') == 'COLLECTION':
                _add_collection_objects(mod.collection, found)
            elif mod.object is not None:
                found.append(mod.object)
        elif booleans_only:
            continue
        elif mod.type == 'NODES':
            _geometry_nodes_dependencies(mod, found)
        else:
            _generic_modifier_dependencies(mod, found)

    unique = []
    seen = set()
    for dep in found:
        if dep is obj or dep.name_full in seen:
            continue
        seen.add(dep.name_full)
        unique.append(dep)
    return unique


def _object_users(booleans_only):
    """For every object a modifier points at (directly, not through a collection): the objects whose
    modifiers point at it."""
    users = {}
    for obj in bpy.data.objects:
        for dep in _direct_dependencies(obj, booleans_only):
            users.setdefault(dep.name_full, set()).add(obj.name_full)
    return users


def _direct_dependencies(obj, booleans_only):
    """Objects obj's modifiers point at directly (a pointer or a Geometry Nodes Object input)."""
    out = []
    for mod in obj.modifiers:
        if mod.type == 'BOOLEAN':
            if getattr(mod, "operand_type", 'OBJECT') != 'COLLECTION' and mod.object is not None:
                out.append(mod.object)
            continue
        if booleans_only:
            continue
        if mod.type == 'NODES':
            node_group = getattr(mod, "node_group", None)
            if node_group is None or not hasattr(node_group, "interface"):
                continue
            for item in node_group.interface.items_tree:
                if getattr(item, "item_type", None) == 'SOCKET' and getattr(item, "in_out", None) == 'INPUT' \
                        and item.socket_type in GN_OBJECT_SOCKETS:
                    value = mod.get(item.identifier)
                    if isinstance(value, bpy.types.Object):
                        out.append(value)
        else:
            for prop in mod.bl_rna.properties:
                if prop.type == 'POINTER' and prop.fixed_type is not None and prop.fixed_type.identifier == 'Object':
                    value = getattr(mod, prop.identifier, None)
                    if value is not None:
                        out.append(value)
    return [d for d in out if d is not obj]


def _repoint(owner, old, new):
    """Point owner's modifiers at new wherever they pointed at old. Returns how many were changed."""
    changed = 0
    for mod in owner.modifiers:
        if mod.type == 'NODES' and getattr(mod, "node_group", None) is not None:
            for item in mod.node_group.interface.items_tree:
                if getattr(item, "item_type", None) == 'SOCKET' and getattr(item, "in_out", None) == 'INPUT' \
                        and item.socket_type in GN_OBJECT_SOCKETS and mod.get(item.identifier) == old:
                    mod[item.identifier] = new
                    changed += 1
            continue
        for prop in mod.bl_rna.properties:
            if prop.type == 'POINTER' and prop.fixed_type is not None and prop.fixed_type.identifier == 'Object' \
                    and not prop.is_readonly and getattr(mod, prop.identifier, None) == old:
                setattr(mod, prop.identifier, new)
                changed += 1
    if changed:
        owner.update_tag()
    return changed


def _data_collection(data):
    """The bpy.data collection name an object's data block lives in (meshes, curves, ...)."""
    for name in ("meshes", "curves", "lights", "cameras", "lattices", "metaballs", "grease_pencils", "armatures",
                 "volumes", "pointclouds", "hair_curves", "speakers", "lightprobes", "texts"):
        coll = getattr(bpy.data, name, None)
        if coll is not None and data.name in coll and coll[data.name] == data:
            return name
    return "meshes"


def _unique_copy(dep):
    """A copy of dep with its own data, in the same collections."""
    new = dep.copy()
    if dep.data is not None:
        new.data = dep.data.copy()
    for coll in dep.users_collection:
        coll.objects.link(new)
    return new


def _is_self_or_ancestor(candidate, obj):
    """True if candidate is obj or one of obj's parents (parenting would create a cycle)."""
    current = obj
    while current is not None:
        if current == candidate:
            return True
        current = current.parent
    return False


def _parent_keep_transform(child, parent, worlds=None):
    """Parent child to parent without moving it. worlds: world matrices read before anything changed (copies
    and objects re-parented earlier in the same run have no up-to-date matrix_world until the scene updates)."""
    world = (worlds or {}).get(child.name_full) or child.matrix_world.copy()
    parent_world = (worlds or {}).get(parent.name_full) or parent.matrix_world.copy()
    child.parent = parent
    child.parent_type = 'OBJECT'
    child.matrix_parent_inverse = parent_world.inverted_safe()
    child.matrix_basis = world


class ParentUsedObjects(bpy.types.Operator):
    bl_idname = "keyops.parent_used_objects"
    bl_label = "KeyOps: Parent Used Objects"
    bl_description = (
        "Parent all objects used by the selected objects' modifiers (boolean cutters, mirror/array "
        "objects, Geometry Nodes inputs, etc.) so they move with it. Ctrl+click: shared ones are made unique first"
    )
    bl_options = {'REGISTER', 'UNDO'}

    filter: bpy.props.EnumProperty(
        name="Dependencies",
        items=[
            ('ALL', "All Modifiers", "Parent objects referenced by any modifier"),
            ('BOOLEANS', "Booleans Only", "Only parent boolean cutters"),
        ],
        default='ALL',
    )  # type: ignore

    make_unique: bpy.props.BoolProperty(
        name="Make Unique",
        description="Objects that other (unselected) objects' modifiers also use, like a cutter shared by two "
                    "meshes, are copied for the selected object first, so parenting them never moves the others "
                    "(Ctrl+click)",
        default=False,
    )  # type: ignore

    recursive: bpy.props.BoolProperty(
        name="Recursive",
        description="Also parent the dependencies of the dependencies (e.g. cutters on a cutter) to their own owner",
        default=True,
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(context.selected_objects)

    def invoke(self, context, event):
        self.make_unique = event.ctrl
        return self.execute(context)

    def execute(self, context):
        booleans_only = self.filter == 'BOOLEANS'

        roots = list(context.selected_objects)
        active = context.active_object
        if active in roots:
            roots.remove(active)
            roots.insert(0, active)

        assigned = set()   # objects that were parented during this run
        processed = set()  # objects whose dependencies were already handled
        parented_count = 0
        skipped_count = 0
        copied_count = 0
        users = _object_users(booleans_only) if self.make_unique else {}
        root_names = {r.name_full for r in roots}
        # every world matrix as it is now, from the evaluated scene, before anything changes
        dg = context.evaluated_depsgraph_get()
        worlds = {o.name_full: o.evaluated_get(dg).matrix_world.copy() for o in context.scene.objects}

        def process(owner):
            nonlocal parented_count, skipped_count, copied_count
            if owner.name_full in processed:
                return
            processed.add(owner.name_full)

            for dep in get_modifier_dependencies(owner, booleans_only):
                if dep.name_full in assigned:
                    continue
                if dep.library is not None or _is_self_or_ancestor(dep, owner):
                    skipped_count += 1
                    continue
                if self.make_unique:
                    others = users.get(dep.name_full, set()) - {owner.name_full} - root_names
                    if others:  # used by objects that aren't being parented to: give this owner its own copy
                        new = _unique_copy(dep)
                        worlds[new.name_full] = worlds.get(dep.name_full, dep.matrix_world).copy()
                        if _repoint(owner, dep, new):
                            users.setdefault(new.name_full, set()).add(owner.name_full)
                            users[dep.name_full].discard(owner.name_full)
                            if dep.parent == owner:
                                # parented to this owner before (an earlier run), but now only the others use
                                # it: let it go, in place, so it no longer moves with this owner
                                w = worlds.get(dep.name_full, dep.matrix_world).copy()
                                dep.parent = None
                                dep.matrix_basis = w
                            dep = new
                            copied_count += 1
                        else:  # only reachable through a collection: can't repoint it, so leave it shared
                            data = new.data if new.data is not dep.data else None
                            bpy.data.objects.remove(new)
                            if data is not None and data.users == 0:
                                getattr(bpy.data, _data_collection(data)).remove(data)
                            skipped_count += 1
                            continue
                if dep.parent != owner:
                    _parent_keep_transform(dep, owner, worlds)
                    parented_count += 1
                assigned.add(dep.name_full)
                if self.recursive:
                    process(dep)

        for root in roots:
            process(root)

        if parented_count == 0:
            self.report({'INFO'}, "No new dependencies to parent")
        else:
            msg = f"Parented {parented_count} object{'s' if parented_count != 1 else ''}"
            if copied_count:
                msg += f", {copied_count} made unique"
            if skipped_count:
                msg += f" (skipped {skipped_count})"
            self.report({'INFO'}, msg)
        return {'FINISHED'}


def register():
    bpy.utils.register_class(ParentUsedObjects)


def unregister():
    bpy.utils.unregister_class(ParentUsedObjects)
