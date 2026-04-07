import bpy
import bpy.types
import bmesh
from ..utils.utilities import BLENDER_VERSION

first_invoked = True

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
        return context.object 
  
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

        elif obj and obj.type == 'CURVE':
            bpy.ops.curve.select_linked_pick('INVOKE_DEFAULT')
        elif obj and obj.type == 'CURVES':
            bpy.ops.curves.select_linked_pick('INVOKE_DEFAULT')

        return {'FINISHED'}
    
    def register():
        bpy.utils.register_class(SelectEdgeLoop)
    def unregister():
        bpy.utils.unregister_class(SelectEdgeLoop)
class SelectEdgeLoop(bpy.types.Operator):
    bl_idname = "keyops.select_edge_loop"
    bl_label = "KeyOps: Select Edge Loop"
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.active_object and
            context.active_object.type == 'MESH' and
            context.scene.tool_settings.mesh_select_mode[1]
        )

    def execute(self, context):
        bpy.ops.mesh.loop_select("INVOKE_DEFAULT", extend=True)
        return {'FINISHED'}
