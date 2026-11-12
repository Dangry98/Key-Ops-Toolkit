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


def _is_self_or_ancestor(candidate, obj):
    """True if candidate is obj or one of obj's parents (parenting would create a cycle)."""
    current = obj
    while current is not None:
        if current == candidate:
            return True
        current = current.parent
    return False


def _parent_keep_transform(child, parent):
    world = child.matrix_world.copy()
    child.parent = parent
    child.parent_type = 'OBJECT'
    child.matrix_parent_inverse = parent.matrix_world.inverted_safe()
    child.matrix_basis = world


class ParentUsedObjects(bpy.types.Operator):
    bl_idname = "keyops.parent_used_objects"
    bl_label = "KeyOps: Parent Used Objects"
    bl_description = (
        "Parent all objects used by the selected objects' modifiers (boolean cutters, mirror/array "
        "objects, Geometry Nodes inputs, etc.) so they move with it"
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

    recursive: bpy.props.BoolProperty(
        name="Recursive",
        description="Also parent the dependencies of the dependencies (e.g. cutters on a cutter) to their own owner",
        default=True,
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(context.selected_objects)

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

        def process(owner):
            nonlocal parented_count, skipped_count
            if owner.name_full in processed:
                return
            processed.add(owner.name_full)

            for dep in get_modifier_dependencies(owner, booleans_only):
                if dep.name_full in assigned:
                    continue
                if dep.library is not None or _is_self_or_ancestor(dep, owner):
                    skipped_count += 1
                    continue
                if dep.parent != owner:
                    _parent_keep_transform(dep, owner)
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
            if skipped_count:
                msg += f" (skipped {skipped_count})"
            self.report({'INFO'}, msg)
        return {'FINISHED'}


def register_parent_used_objects():
    bpy.utils.register_class(ParentUsedObjects)


def unregister_parent_used_objects():
    bpy.utils.unregister_class(ParentUsedObjects)
