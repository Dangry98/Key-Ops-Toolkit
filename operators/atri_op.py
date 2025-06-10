import bpy.types, bmesh

def update_float_value(self, context):
    wm = bpy.context.window_manager
    bpy.ops.mesh.attribute_set('EXEC_DEFAULT', True, value_float=wm.float_value)

def update_float_color_value(self, context):
    wm = bpy.context.window_manager
    bpy.ops.mesh.attribute_set('EXEC_DEFAULT', True, value_color=wm.float_color_value)
    
def update_integer_value(self, context):
    wm = bpy.context.window_manager
    bpy.ops.mesh.attribute_set('EXEC_DEFAULT', True, value_int=wm.integer_value)

def draw_custom_button(self, context):
    wm = bpy.context.window_manager

    if context.active_object.mode == 'EDIT':
        layout = self.layout
        row = layout.row(align=True)
        if bpy.context.object.data.attributes.active and bpy.context.object.data.attributes.active.data_type == "BOOLEAN":
            row.operator("keyops.atri_op", text="Assign").type = "Assign"
            row.operator("keyops.atri_op", text="Remove").type = "Remove"
            row.operator("keyops.atri_op", text="Select").type = "Select"
        if bpy.context.object.data.attributes.active and bpy.context.object.data.attributes.active.data_type == "FLOAT":
            row.prop(wm, "float_value", text="Float Value")
        if bpy.context.object.data.attributes.active and bpy.context.object.data.attributes.active.data_type == "FLOAT_COLOR":
            row.operator("keyops.atri_op", text="Assign").type = "Assign"
            row.operator("keyops.atri_op", text="Remove").type = "Remove"
            row.prop(wm, "float_color_value", text="")
        if bpy.context.object.data.attributes.active and bpy.context.object.data.attributes.active.data_type == "INT":
            # get active object and active face, get the integer value from the face
            # obj = bpy.context.active_object
            # bm = bmesh.from_edit_mesh(obj.data)
            # face = bm.select_history.active
            # if face:
            #     layer = bm.faces.layers.int.get(bpy.context.object.data.attributes.active.name)
            #     if layer:
            #         wm.integer_value = face[layer]
          
            row.prop(wm, "integer_value", text="Integer Value")
            
        layout = self.layout
        row = layout.row(align=True)
        row.operator("keyops.atri_op", text="Vertex Group", icon="VERTEXSEL").type = "Vertex"
        row.operator("keyops.atri_op", text="Edge Group", icon="EDGESEL").type = "Edge"
        row.operator("keyops.atri_op", text="Face Group", icon="FACESEL").type = "Face"


class AtriOP(bpy.types.Operator):
    bl_idname = "keyops.atri_op"
    bl_label = "KeyOps: Atri OP"
    bl_description = "Atributte Operations"
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.StringProperty(default="") # type:ignore

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.mode == 'EDIT'

    def execute(self, context):
        wm = bpy.context.window_manager
        sel_mode = context.tool_settings.mesh_select_mode[:]
        active_type = bpy.context.object.data.attributes.active
        if self.type == "Assign":
            if active_type and active_type.data_type == "BOOLEAN":
                bpy.ops.mesh.attribute_set('EXEC_DEFAULT', True, value_bool=True)
            if active_type and active_type.data_type == "FLOAT":
                bpy.ops.mesh.attribute_set('EXEC_DEFAULT', True, value_float=wm.float_value)
            if active_type and active_type.data_type == "FLOAT_COLOR":
                bpy.ops.mesh.attribute_set('EXEC_DEFAULT', True, value_color=wm.float_color_value)

        elif self.type == "Remove":
            if active_type and active_type.data_type == "BOOLEAN":
                bpy.ops.mesh.attribute_set('EXEC_DEFAULT', True, value_bool=False)
            if active_type and active_type.data_type == "FLOAT":
                bpy.ops.mesh.attribute_set('EXEC_DEFAULT', True, value_float=0.0)
            if active_type and active_type.data_type == "FLOAT_COLOR":
                bpy.ops.mesh.attribute_set('EXEC_DEFAULT', True, value_color=(0.0, 0.0, 0.0, 0.0))

        elif self.type == "Select":
            # need to change to the select mode first of the attribute, otherwise it will not work
            if active_type and active_type.domain == "POINT":
                context.tool_settings.mesh_select_mode = (True, False, False)
            elif active_type and active_type.domain == "EDGE":
                context.tool_settings.mesh_select_mode = (False, True, False)
            elif active_type and active_type.domain == "FACE":
                context.tool_settings.mesh_select_mode = (False, False, True)
            bpy.ops.mesh.select_by_attribute()

        elif self.type == "Vertex":
            context.tool_settings.mesh_select_mode = (True, False, False)
            bpy.ops.geometry.attribute_add(name="Vertex_Group", data_type='BOOLEAN', domain='POINT')
            bpy.ops.keyops.atri_op(type="Assign")
            context.tool_settings.mesh_select_mode = (sel_mode[0], sel_mode[1], sel_mode[2])
        elif self.type == "Edge":
            context.tool_settings.mesh_select_mode = (False, True, False)
            bpy.ops.geometry.attribute_add(name="Edge_Group", data_type='BOOLEAN', domain='EDGE')
            bpy.ops.keyops.atri_op(type="Assign")
            context.tool_settings.mesh_select_mode = (sel_mode[0], sel_mode[1], sel_mode[2])
        elif self.type == "Face":
            context.tool_settings.mesh_select_mode = (False, False, True)
            bpy.ops.geometry.attribute_add(name="Face_Group", data_type='BOOLEAN', domain='FACE')
            bpy.ops.keyops.atri_op(type="Assign")
            context.tool_settings.mesh_select_mode = (sel_mode[0], sel_mode[1], sel_mode[2])

        return {'FINISHED'}

    def register():
        bpy.types.DATA_PT_mesh_attributes.append(draw_custom_button)
        bpy.types.WindowManager.float_value = bpy.props.FloatProperty(name="Float Value", default=1.0, update=update_float_value)
        bpy.types.WindowManager.float_color_value = bpy.props.FloatVectorProperty(size=4, subtype="COLOR", name="Float Color Value", default=(1.0, 1.0, 1.0, 1.0), min=0.0, max=1.0, update=update_float_color_value)
        bpy.types.WindowManager.integer_value = bpy.props.IntProperty(name="Integer Value", default=0, update=update_integer_value)
    def unregister():
        bpy.types.DATA_PT_mesh_attributes.remove(draw_custom_button)
        del bpy.types.WindowManager.float_value
        del bpy.types.WindowManager.float_color_value
        del bpy.types.WindowManager.integer_value
