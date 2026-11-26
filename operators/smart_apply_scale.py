# Based on Scale with modifiers by Artem_Poletsky https://blenderartists.org/t/scale-with-modifiers-free-addon-for-blender-2-8/1212309
# It has been modified to work with 4.+ and Geomtry Nodes Modifiers as well as some other minor changes

import bpy
from mathutils import Vector
from ..utils.pref_utils import get_keyops_prefs
from ..utils.pref_utils import feature_on
BLENDER_VERSION = bpy.app.version

MODS = {
    'ARRAY': 'function',
    'BOOLEAN': {'double_threshold'},
    'BEVEL': 'function',
    'SCREW': {'screw_offset', 'merge_threshold'},
    'MIRROR': {'merge_threshold'},
    'SOLIDIFY': {'thickness'},
    'WIREFRAME': {'thickness'},
    'DISPLACE':  'function',
    'SHRINKWRAP': {'offset'},
    'WELD': {'merge_threshold'},
    'SKIN': 'function',
    'REMESH': {'voxel_size'},
}

def objectsSelectSet(objects, value):
    for o in objects:
        o.select_set(value)

def funcBEVEL(mod, scale, object, operator):
    if mod.offset_type != 'PERCENT':
        mod.width *= scale
    return False

def funcBEVELget(mod):
    return mod.width

def funcBEVELset(mod, size):
    mod.width = size

def funcARRAY(mod, scale, object, operator):
    mod.constant_offset_displace[0] *= scale
    mod.constant_offset_displace[1] *= scale
    mod.constant_offset_displace[2] *= scale
    mod.merge_threshold *= scale
    return False

def funcARRAYget(mod):
    return Vector((mod.constant_offset_displace[0], mod.constant_offset_displace[1], mod.constant_offset_displace[2], mod.merge_threshold))

def funcARRAYset(mod, size):
    mod.constant_offset_displace[0] = size[0]
    mod.constant_offset_displace[1] = size[1]
    mod.constant_offset_displace[2] = size[2]
    mod.merge_threshold = size[3]

def funcDISPLACE(mod, scale, object, operator):
    mod.strength *= scale
    if (bool(mod.texture)
        & ((mod.texture_coords == "LOCAL") | (mod.texture_coords == "OBJECT"))
        & operator.scaleTextures):
        if hasattr(mod.texture, 'noise_scale'):
            mod.texture.noise_scale *= scale
        return "objects have displace texture applied."
    else:
        return False

def funcDISPLACEget(mod):
    return mod.strength

def funcDISPLACEset(mod, size):
    mod.strength = size

def funcSKIN(mod, scale, object, operator):
    verts = object.data.skin_vertices[0].data
    for v in verts:
        v.radius[0] *= scale
        v.radius[1] *= scale

def funcSKINget(mod):
    # unsupported
    return 1

def funcSKINset(mod, size):
    # unsupported
    return

def func_geom_nodes(scale, object):
    if object.modifiers:
        for mod in object.modifiers:
            if mod.type == 'NODES':
                if mod.node_group:
                    node_group = mod.node_group
                    input_node = next((node for node in node_group.nodes if node.type == 'GROUP_INPUT'),None)

                    for node_input in input_node.outputs[:-1]:
                        if not node_input.type == 'GEOMETRY':
                            socket_id = node_input.identifier
                            socket_type = node_input.type
                            if socket_type == 'VALUE':
                                if'NodeSocketFloatDistance' in str(node_input):
                                    mod[socket_id] = scale * mod[socket_id]

                            elif socket_type == 'VECTOR':
                                if'NodeSocketVectorTranslation' in str(node_input):
                                    mod[socket_id] = Vector(mod[socket_id]) * scale
        return 

def getModifierSize(mod, scale):
    attr = MODS[mod.type]
    if attr == 'function':
        return globals()["func" + mod.type + "get"](mod) * scale
    tupl = ()
    for key in attr:
        if not hasattr(mod, key):
            continue
        tupl += (getattr(mod, key), )
    if len(tupl) == 0:
        return 1
    if len(tupl) == 1:
        return tupl[0] * scale
    return Vector(tupl) * scale

def setModifierSize(mod, size):
    attr = MODS[mod.type]
    if attr == 'function':
        globals()["func" + mod.type + "set"](mod, size)
        return

    i = 0
    for key in attr:
        if not hasattr(mod, key):
            continue
        if type(size) == Vector:
            setattr(mod, key, size[i])
        else:
            setattr(mod, key, size)
        i+=1

def get_scale(obj):
    s = obj.scale
    return (s[0] + s[1] + s[2]) / 3

def equal_points_len(target, source):
    tl = len(target)
    sl = len(source)
    if tl == sl:
        return
    while tl > sl:
        target.remove(target[1])
        tl = len(target)
    while tl < sl:
        target.add(0, 0)
        tl = len(target)
    return
def copy_profile(target, source):
    copy_modifier(target, source)
    equal_points_len(target.points, source.points)
    # len = max(len(source.points), len(target.points))
    for i in range(0, len(source.points)):
        p1 = source.points[i]
        p2 = target.points[i]
        # new_point = target.points.add(p.location[0], p.location[1])
        p2.handle_type_1 = p1.handle_type_1
        p2.handle_type_2 = p1.handle_type_2
        p2.location = p1.location
        # copy_modifier(new_point, p)
    target.update()
    return

def copy_modifier(target, source, string=""):
    """Copy attributes from source to target that have string in them"""
    for attr in dir(source):
        if attr in {'custom_profile'}:
            copy_profile(getattr(target, attr), getattr(source, attr))
            continue
        if attr.find(string) > -1:
            try:
                setattr(target, attr, getattr(source, attr))
            except:
                pass
    return

# class UnifyModifiersSizeOperator(bpy.types.Operator):
#     """Unify modifiers"""
#     bl_idname = "object.unify_modifiers_operator"
#     bl_label = "Unify modifiers"
#     bl_options = {'REGISTER', 'UNDO'}

#     use_names: bpy.props.BoolProperty(name="Use names", default=False)
#     copy_all: bpy.props.BoolProperty(name="Copy all attributes", default=False)

#     @classmethod
#     def poll(cls, context):
#         return (context.space_data.type == 'VIEW_3D'
#             and len(context.selected_objects) > 0
#             and context.view_layer.objects.active
#             and context.object.mode == 'OBJECT')

#     def execute(self, context):
#         source  = context.view_layer.objects.active
#         targets = list(context.selected_objects)
#         targets.remove(source)
#         source_scale = abs(get_scale(source))
#         indices = {}
#         for mod in reversed(source.modifiers):
#             if not mod.type in MODS:
#                 continue
#             size = getModifierSize(mod, source_scale)
#             indices[mod.type] = indices[mod.type] + 1 if mod.type in indices else 0
#             if not mod.show_viewport:
#                 continue
#             source_index = indices[mod.type]
#             for t in targets:
#                 target_scale = abs(get_scale(t))
#                 target_index = 0
#                 for m in reversed(t.modifiers):
#                     # print(source_index, target_index, mod.type, m.type)
#                     if m.type == mod.type:
#                         do_set_size = self.use_names and m.name == mod.name
#                         # print(self.use_names, m.name, mod.name, do_set_size)
#                         if not do_set_size and not self.use_names:
#                             do_set_size = target_index == source_index
#                         if do_set_size and target_scale != 0:
#                             if self.copy_all:
#                                 copy_modifier(m, mod)
#                             setModifierSize(m, size / target_scale)
#                         target_index += 1
#         return {'FINISHED'}


def _scale_modifiers(obj, scale, operator):
    """Make the object's modifiers keep their look after its scale (average of X, Y, Z) is applied.
    Returns warnings, e.g. about displacement textures."""
    warnings = []
    for mod in obj.modifiers:
        if mod.type in MODS and mod.show_viewport:
            if MODS[mod.type] == 'function':
                result = globals()["func" + mod.type](mod, scale, obj, operator)
                if result:
                    warnings.append(result)
            else:
                for attrname in MODS[mod.type]:
                    if hasattr(mod, attrname):
                        setattr(mod, attrname, getattr(mod, attrname) * scale)
    if operator.geomtryNodes:
        func_geom_nodes(scale, obj)
    return warnings


def _real_users(data):
    return data.users - (1 if data.use_fake_user else 0)


def _is_linked(obj):
    return bool(obj.library or (obj.data is not None and getattr(obj.data, "library", None))
                or getattr(obj, "override_library", None))


def _keep_children_in_place(obj, scale_matrix):
    """The parent's scale goes to 1: fold it into each child's parent inverse so children don't move."""
    for child in obj.children:
        child.matrix_parent_inverse = scale_matrix @ child.matrix_parent_inverse


class SmartApplyScale(bpy.types.Operator):
    bl_idname = "object.smart_apply_scale"
    bl_label = "Smart Apply Scale"
    bl_description = ("Apply scale while compensating in the modifiers for the scale difference. Objects that "
                      "share their mesh keep sharing it when they have the same scale")
    bl_options = {'REGISTER', 'UNDO'}

    scaleTextures: bpy.props.BoolProperty(name="Scale displacement textures", default=False) # type: ignore
    makeClonesReal: bpy.props.BoolProperty(
        name="Make Single User When Needed", default=True,
        description="Objects that share a mesh with objects of another scale (or with unselected objects) get "
                    "their own copy of it, so their scale can be applied. Off: those are skipped") # type: ignore
    geomtryNodes: bpy.props.BoolProperty(name="Fix Geometry Nodes Modifiers", default=True, description="Only works if the input has Distance Subtype (m)") # type: ignore
    auto_fix_normals: bpy.props.BoolProperty(name="Auto Fix normals", default=True, description="Recalculate normals after applying scale if inverted scale") # type: ignore

    @classmethod
    def poll(cls, context):
        # object.transform_apply only works in Object Mode
        return context.mode == 'OBJECT' and len(context.selected_objects) > 0

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "makeClonesReal")
        layout.prop(self, "scaleTextures")
        layout.prop(self, "geomtryNodes")
        layout.prop(self, "auto_fix_normals")

    # ------------------------------------------------------------ applying
    def _apply_one_by_one(self, context, objs):
        """Blender's own apply, one object at a time (one failure doesn't stop the others).
        Returns (applied, failed[(obj, reason)])."""
        applied, failed = [], []
        if not objs:
            return applied, failed
        selected = list(context.selected_objects)
        active = context.view_layer.objects.active
        for o in selected:
            o.select_set(False)
        try:
            batch = [o for o in objs]
            # one call for all: fast; if Blender refuses, retry each on its own to find which can't
            for o in batch:
                o.select_set(True)
            context.view_layer.objects.active = batch[0]
            try:
                self._transform_apply(batch)
                applied = batch
            except RuntimeError:
                for o in batch:
                    o.select_set(False)
                for o in batch:
                    o.select_set(True)
                    context.view_layer.objects.active = o
                    try:
                        self._transform_apply([o])
                        applied.append(o)
                    except RuntimeError as e:
                        failed.append((o, str(e).strip().splitlines()[-1] if str(e).strip() else "Blender refused"))
                    o.select_set(False)
        finally:
            for o in context.selected_objects:
                o.select_set(False)
            for o in selected:
                if o.name in context.view_layer.objects:
                    o.select_set(True)
            context.view_layer.objects.active = active
        return applied, failed

    def _transform_apply(self, objs):
        if BLENDER_VERSION >= (5, 0, 0):
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True,
                                           corrective_flip_normals=self.auto_fix_normals)
            return
        flipped = []
        if self.auto_fix_normals:
            flipped = [o for o in objs if o.type == "MESH" and o.scale.x * o.scale.y * o.scale.z < 0]
            for o in flipped:
                o.data.flip_normals()
        try:
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        except RuntimeError:
            for o in flipped:  # nothing was applied: undo the flip
                o.data.flip_normals()
            raise

    def _apply_shared(self, users, data):
        """Objects that share one mesh/curve and have the same scale: scale the shared data once and set each
        object's scale to 1, so they keep sharing it."""
        from mathutils import Matrix
        sx, sy, sz = users[0].scale
        m = Matrix.Diagonal((sx, sy, sz, 1.0))
        data.transform(m)
        if self.auto_fix_normals and sx * sy * sz < 0 and hasattr(data, "flip_normals"):
            data.flip_normals()
        for o in users:
            _keep_children_in_place(o, m)
            o.scale = (1.0, 1.0, 1.0)

    def execute(self, context):
        objects = list(context.selected_objects)
        if not objects:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, "Smart Apply Scale only works in Object Mode")
            return {'CANCELLED'}

        skipped = []          # (obj, reason)
        to_apply = []         # Blender's apply, own data
        shared_groups = []    # (data, [objects]) applied to the shared data
        uneven = 0
        selected_set = set(objects)

        by_data = {}
        for obj in objects:
            if tuple(obj.scale) == (1.0, 1.0, 1.0):
                continue
            if _is_linked(obj):
                skipped.append((obj, "linked from a library"))
                continue
            if obj.data is not None and _real_users(obj.data) > 1:
                by_data.setdefault(obj.data, []).append(obj)
            else:
                to_apply.append(obj)

        single_user_made = 0
        for data, users in by_data.items():
            all_users = [o for o in bpy.data.objects if o.data == data]
            same_scale = all(tuple(o.scale) == tuple(users[0].scale) for o in users)
            if same_scale and set(all_users) <= selected_set and hasattr(data, "transform"):
                shared_groups.append((data, users))
            elif self.makeClonesReal:
                for o in users:
                    o.data = o.data.copy()
                    single_user_made += 1
                    to_apply.append(o)
            else:
                for o in users:
                    skipped.append((o, "shares its mesh with objects of another scale"))

        # remember each object's scale before applying, for its modifiers
        scales = {o: abs(sum(o.scale) / 3.0) for o in to_apply + [o for _d, us in shared_groups for o in us]}
        uneven = sum(1 for o in scales if not (o.scale[0] == o.scale[1] == o.scale[2]))

        applied, failed = self._apply_one_by_one(context, to_apply)
        skipped += failed
        for data, users in shared_groups:
            self._apply_shared(users, data)
            applied += users

        warnings = {}
        for o in applied:
            for w in _scale_modifiers(o, scales[o], self):
                warnings[w] = warnings.get(w, 0) + 1

        parts = [f"Applied scale to {len(applied)} object{'s' if len(applied) != 1 else ''}"]
        shared_n = sum(len(us) for _d, us in shared_groups)
        if shared_n:
            parts.append(f"{shared_n} still share their mesh")
        if single_user_made:
            parts.append(f"{single_user_made} got their own mesh")
        if uneven:
            parts.append(f"{uneven} had uneven scale (modifiers use the average)")
        for w, n in warnings.items():
            parts.append(f"{n} {w}")
        if skipped:
            reasons = {}
            for _o, r in skipped:
                reasons[r] = reasons.get(r, 0) + 1
            parts.append("skipped " + ", ".join(f"{n} ({r})" for r, n in reasons.items()))
        self.report({'WARNING'} if skipped or uneven else {'INFO'}, "; ".join(parts))
        return {'FINISHED'} if applied or not skipped else {'CANCELLED'}

def menu_apply(self, context):
    if not feature_on("toolkit_panel"):
        return
    layout = self.layout
    layout.separator()

    layout.operator_context = "INVOKE_DEFAULT"
    layout.operator(SmartApplyScale.bl_idname, text=SmartApplyScale.bl_label, icon='FREEZE')

# def menu_make_links(self, context):
#     layout = self.layout
#     layout.separator()

#     layout.operator_context = "INVOKE_DEFAULT"
#     # layout.operator(UnifyModifiersSizeOperator.bl_idname, text=UnifyModifiersSizeOperator.bl_label)


def register():
    bpy.utils.register_class(SmartApplyScale)
    bpy.types.VIEW3D_MT_object_apply.prepend(menu_apply)


def unregister():
    bpy.types.VIEW3D_MT_object_apply.remove(menu_apply)
    bpy.utils.unregister_class(SmartApplyScale)
