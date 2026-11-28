import bpy
import bpy.types
import bmesh
from ..utils.pref_utils import clear_registered_keymaps
from ..utils.utilities import BLENDER_VERSION

first_invoked = True
registered_double_click_select_island_keymaps = []

def register_double_click_select_island_keymaps():
    global registered_double_click_select_island_keymaps
    wm = bpy.context.window_manager

    km = wm.keyconfigs.addon.keymaps.new(name='Mesh', space_type='EMPTY')
    kmi = km.keymap_items.new('keyops.double_click_select_island', 'LEFTMOUSE', 'DOUBLE_CLICK')
    registered_double_click_select_island_keymaps.append((km, kmi))
    kmi = km.keymap_items.new('keyops.double_click_select_island', 'LEFTMOUSE', 'DOUBLE_CLICK', shift=True)
    kmi.properties.deselect = False
    registered_double_click_select_island_keymaps.append((km, kmi))
    kmi = km.keymap_items.new('keyops.double_click_select_island', 'LEFTMOUSE', 'DOUBLE_CLICK', ctrl=True)
    kmi.properties.deselect = True
    registered_double_click_select_island_keymaps.append((km, kmi))
    kmi = km.keymap_items.new('keyops.select_edge_loop', 'LEFTMOUSE', 'DOUBLE_CLICK')
    registered_double_click_select_island_keymaps.append((km, kmi))
    kmi = km.keymap_items.new('keyops.select_edge_loop', 'LEFTMOUSE', 'DOUBLE_CLICK', shift=True)
    registered_double_click_select_island_keymaps.append((km, kmi))

    km = wm.keyconfigs.addon.keymaps.new(name='UV Editor', space_type='EMPTY')
    kmi = km.keymap_items.new('keyops.double_click_select_island', 'LEFTMOUSE', 'DOUBLE_CLICK')
    registered_double_click_select_island_keymaps.append((km, kmi))
    kmi = km.keymap_items.new('keyops.double_click_select_island', 'LEFTMOUSE', 'DOUBLE_CLICK', shift=True)
    kmi.properties.extend = True
    registered_double_click_select_island_keymaps.append((km, kmi))
    kmi = km.keymap_items.new('keyops.double_click_select_island', 'LEFTMOUSE', 'DOUBLE_CLICK', ctrl=True)
    kmi.properties.deselect = True
    registered_double_click_select_island_keymaps.append((km, kmi))

    km = wm.keyconfigs.addon.keymaps.new(name='Curve', space_type='EMPTY')
    kmi = km.keymap_items.new('keyops.double_click_select_island', 'LEFTMOUSE', 'DOUBLE_CLICK')
    registered_double_click_select_island_keymaps.append((km, kmi))
    kmi = km.keymap_items.new('curve.select_linked', 'LEFTMOUSE', 'DOUBLE_CLICK', shift=True)
    registered_double_click_select_island_keymaps.append((km, kmi))
    kmi = km.keymap_items.new('curve.select_linked_pick', 'LEFTMOUSE', 'DOUBLE_CLICK', ctrl=True)
    kmi.properties.deselect = True
    registered_double_click_select_island_keymaps.append((km, kmi))

    km = wm.keyconfigs.addon.keymaps.new(name='Curves', space_type='EMPTY')
    kmi = km.keymap_items.new('curves.select_linked', 'LEFTMOUSE', 'DOUBLE_CLICK')
    registered_double_click_select_island_keymaps.append((km, kmi))

class DoubleClickSelectIsland(bpy.types.Operator):
    bl_idname = "keyops.double_click_select_island"
    bl_label = "Select Linked"
    bl_description = "KeyOps: Select Linked (Double Click)"
    bl_options = {'REGISTER', 'UNDO'}

    extend: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"}) # type: ignore
    deselect: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"}) # type: ignore

    delimit: bpy.props.EnumProperty(
        name="Delimit",
        description="Limits selection by chosen criteria",
        items=[
            ("NORMAL", "Normal", ""),
            ("ANGLE", "Angle", ""),
            ("MATERIAL", "Material", ""),
            ("SEAM", "Seam", ""),
            ("SHARP", "Sharp", ""),
            ("UV", "UV", ""),
        ],
        default={'NORMAL'},
        options={'ENUM_FLAG'}  # <-- allow multiple selections
    ) # type: ignore

    index: bpy.props.IntProperty(default=0, options={"SKIP_SAVE"}) # type: ignore
    object_index: bpy.props.IntProperty(default=0, options={"SKIP_SAVE"}) # type: ignore

    angle: bpy.props.FloatProperty(
        name="Angle",
        subtype="ANGLE",
        min=0,
        max=3.14159,
        default=0.0174533
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        # Only bound in the Mesh, UV Editor, Curve and Curves keymaps, all edit-mode
        if context.object is None or context.area is None or context.mode not in {'EDIT_MESH', 'EDIT_CURVE', 'EDIT_CURVES'}:
            return False
        # in the 3D View in edge-only select mode a double click selects a full edge loop instead (SelectEdgeLoop)
        if context.mode == 'EDIT_MESH' and context.area.type == 'VIEW_3D' \
                and tuple(context.tool_settings.mesh_select_mode) == (False, True, False):
            return False
        return True

    def invoke(self, context, event):
        global first_invoked

        if event.shift:
            self.extend = True
        if event.ctrl:
            self.deselect = True

        obj = context.object

        if context.area.type != 'IMAGE_EDITOR' and obj.type == "MESH":
            first_invoked = True

            delimit_set = set(self.delimit)
            if "ANGLE" not in delimit_set:
                bpy.ops.mesh.select_linked_pick(
                    'INVOKE_DEFAULT',
                    deselect=self.deselect,
                    delimit=delimit_set
                )
            else:
                # Handle ANGLE specially
                ob = context.edit_object
                me = ob.data
                bm = bmesh.from_edit_mesh(me)
                original_selection = {f.index for f in bm.faces if f.select}

                bpy.ops.mesh.select_linked_pick(
                    'INVOKE_DEFAULT',
                    deselect=self.deselect,
                    delimit={"NORMAL"}
                )

                # Reset to original selection
                bm = bmesh.from_edit_mesh(me)
                for f in bm.faces:
                    f.select = f.index in original_selection
                bmesh.update_edit_mesh(me)

            # Capture Blender reports for index tracking
            message = ""
            if BLENDER_VERSION >= (5, 2, 0):
                if bpy.context.window_manager.reports:
                    r = bpy.context.window_manager.reports[-1]
                    message = r.message
            else:
                def get_latest_reports():
                    original_area = bpy.context.area.type
                    bpy.context.area.type = 'INFO'
                    bpy.ops.info.select_all(action='SELECT')
                    bpy.ops.info.report_copy()
                    bpy.context.area.type = original_area
                    return bpy.context.window_manager.clipboard

                message = ""
                messages = get_latest_reports()
                if messages:
                    message = messages.splitlines()[-1]

            if message:
                for m in message.split(","):
                    if "object_index" in m:
                        self.object_index = int(m.split("=")[-1].replace(")", ""))
                    if "index" in m:
                        self.index = int(m.split("=")[-1].replace(")", ""))

        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        if context.object.type == 'MESH' and context.edit_object:
            if "ANGLE" in self.delimit:
                if not context.tool_settings.mesh_select_mode[2]:
                    layout.label(text="Only works in Face Mode", icon="ERROR")
                else:
                    layout.prop(self, "deselect")
                    layout.prop(self, "angle")
            else:
                layout.prop(self, "deselect")

            layout.prop(self, "delimit", expand=True)

    def execute(self, context):
        global first_invoked
        obj = context.active_object

        if obj and obj.type == 'MESH':
            if context.area.type == 'IMAGE_EDITOR':
                bpy.ops.uv.select_linked_pick(
                    'INVOKE_DEFAULT',
                    deselect=self.deselect,
                    extend=self.extend
                )
                return {'FINISHED'}

            delimit_set = set(self.delimit)
            if "ANGLE" not in delimit_set:
                if not first_invoked:
                    bpy.ops.mesh.select_linked_pick(
                        'INVOKE_DEFAULT',
                        deselect=self.deselect,
                        delimit=delimit_set,
                        index=self.index,
                        object_index=self.object_index
                    )
            else:
                if self.deselect or self.extend:
                    ob = context.edit_object
                    me = ob.data
                    bm = bmesh.from_edit_mesh(me)

                    original_selection = {f.index for f in bm.faces if f.select}
                    active_face = next(
                        (f for f in reversed(bm.select_history) if isinstance(f, bmesh.types.BMFace)),
                        None
                    )

                    if not active_face:
                        return {'FINISHED'}

                    for f in bm.faces:
                        f.select = False
                    active_face.select = True

                bpy.ops.mesh.faces_select_linked_flat(sharpness=self.angle)

                if self.deselect or self.extend:
                    bm = bmesh.from_edit_mesh(context.edit_object.data)
                    new_selection = {f.index for f in bm.faces if f.select}

                    if self.deselect:
                        final_selection = original_selection - new_selection
                    elif self.extend:
                        final_selection = original_selection | new_selection
                    else:
                        final_selection = new_selection

                    for f in bm.faces:
                        f.select = f.index in final_selection

            first_invoked = False

        elif obj and obj.type == 'CURVE' and bpy.ops.curve.select_linked_pick.poll():
            bpy.ops.curve.select_linked_pick('INVOKE_DEFAULT')
        elif obj and obj.type == 'CURVES' and "select_linked_pick" in dir(bpy.ops.curves) and bpy.ops.curves.select_linked_pick.poll():
            bpy.ops.curves.select_linked_pick('INVOKE_DEFAULT')

        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(DoubleClickSelectIsland)
    bpy.utils.register_class(SelectEdgeLoop)
    register_double_click_select_island_keymaps()
def unregister():
    clear_registered_keymaps(registered_double_click_select_island_keymaps)
    bpy.utils.unregister_class(DoubleClickSelectIsland)
    bpy.utils.unregister_class(SelectEdgeLoop)
def _straightest(v, e, faces_ok=True):
    """The edge that carries a loop on from edge e through vertex v: on a plain grid vertex (four edges, all
    quads) the opposite edge; at poles, triangles and n-gons the straightest one (within 50 degrees)."""
    others = [x for x in v.link_edges if x is not e]
    if not others:
        return None
    if len(v.link_edges) == 4 and all(len(f.verts) == 4 for f in v.link_faces) and len(v.link_faces) == 4:
        opposite = [x for x in others if not set(x.link_faces) & set(e.link_faces)]
        if len(opposite) == 1:
            return opposite[0]
    if e.is_boundary:  # a border: follow the border
        border = [x for x in others if x.is_boundary]
        if len(border) == 1:
            return border[0]
    d_in = (v.co - e.other_vert(v).co)
    if d_in.length < 1e-12:
        return None
    d_in.normalize()
    best, best_dot = None, 0.64  # cos(50 degrees)
    for x in others:
        if x.is_boundary != e.is_boundary and e.is_boundary:
            continue
        d = x.other_vert(v).co - v.co
        if d.length < 1e-12:
            continue
        dot = d_in.dot(d.normalized())
        if dot > best_dot:
            best, best_dot = x, dot
    return best


def full_loop(start):
    """Every edge of the loop through `start`, walking both ways until it closes or nothing carries on."""
    loop = [start]
    seen = {start}
    for v0 in start.verts:
        e, v = start, v0
        while True:
            nxt = _straightest(v, e)
            if nxt is None or nxt in seen:
                break
            seen.add(nxt)
            loop.append(nxt)
            e, v = nxt, nxt.other_vert(v)
    return loop


class SelectEdgeLoop(bpy.types.Operator):
    """Double click an edge (edge select mode): select its whole loop, carrying on through poles, triangles and
    n-gons where Blender's loop select stops"""
    bl_idname = "keyops.select_edge_loop"
    bl_label = "KeyOps: Select Edge Loop"
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.active_object and
            context.active_object.type == 'MESH' and
            context.mode == 'EDIT_MESH' and
            context.scene.tool_settings.mesh_select_mode[1] and
            context.area is not None
        )

    def execute(self, context):
        done = False
        for obj in [o for o in context.objects_in_mode_unique_data if o.type == 'MESH']:
            bm = bmesh.from_edit_mesh(obj.data)
            act = bm.select_history.active
            if not isinstance(act, bmesh.types.BMEdge) or obj != context.edit_object:
                continue
            for e in full_loop(act):
                e.select_set(True)
            bm.select_history.add(act)
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            done = True
        if not done:  # nothing picked by the first click: Blender's own loop select
            bpy.ops.mesh.loop_select("INVOKE_DEFAULT", extend=True)
        return {'FINISHED'}
