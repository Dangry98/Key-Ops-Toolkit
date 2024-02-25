import bpy.types
from ..utils.pref_utils import get_is_addon_enabled
from mathutils import Vector, Matrix

hardops = None

class AddModifier(bpy.types.Operator):
    bl_description = "Add a modifier"
    bl_idname = "keyops.add_modifier"
    bl_label = "Add Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.EnumProperty(name="Modifier Type", description="", items=(
            ('TRIANGULATE', 'Triangulate', ''),
            ('WEIGHTED_NORMAL', 'Weighted Normal', ''),
            ('WELD', 'Weld', ''),
            ('LATTICE', 'Lattice', ''))) #type:ignore
    keep_custom_normals: bpy.props.BoolProperty(name="Keep Normals",description="", default=True) #type:ignore
    keep_sharp: bpy.props.BoolProperty(name="Keep Sharp",description="", default=False) #type:ignore
    merge_threshold: bpy.props.FloatProperty(name="Merge Threshold",description="", default=0.0001,) #type:ignore
    merge_mode: bpy.props.EnumProperty(name="Mode", description="", items=(
            ('CONNECTED', 'Connected', ''),
            ('ALL', 'All', ''))) #type:ignore
    modified: bpy.props.BoolProperty(name="Modified", description="Use final geometry. Edit mode only", default = False) #type:ignore
    individual: bpy.props.BoolProperty(name="Individual", description="Assign individual lattice per object", default = False) #type:ignore
    mode: bpy.props.EnumProperty(name="Lattice Style",default='KEY_BSPLINE',items=
            (("KEY_LINEAR", "Linear", ""), ("KEY_BSPLINE", "Bspline", ""))) #type:ignore
    lattice_subdivisions: bpy.props.IntProperty(name="Subdivisions", description="Subdivisions", default=1, min=1, max=10) #type:ignore

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)
    
    def invoke(self, context, event):
        global ev 
        ev = []
        if event.ctrl:
            ev.append("Ctrl")
        if event.shift:
            ev.append("Shift")
        if event.alt:
            ev.append("Alt")
        return self.execute(context)
    
    def draw(self, context):
        if self.type == 'TRIANGULATE':
            self.layout.prop(self, "keep_custom_normals")
        if self.type == 'WEIGHTED_NORMAL':
            self.layout.prop(self, "keep_sharp")
        if self.type == 'WELD':
            self.layout.prop(self, "merge_mode")
            self.layout.prop(self, "merge_threshold")
        if self.type == 'LATTICE':
            self.layout.prop(self, "mode")
            if context.mode == 'EDIT_MESH':
                self.layout.prop(self, "modified")
            self.layout.prop(self, "individual")

    def execute(self, context):
        if self.type == 'TRIANGULATE':
            #sort triabgelate before mirror modifier? For better baking?
            for obj in [o for o in context.selected_objects if o.type == 'MESH']:
                mod = obj.modifiers.new(type='TRIANGULATE', name='Triangulate')
                mod.keep_custom_normals = self.keep_custom_normals
                mod.show_in_editmode = False

        if self.type == 'WEIGHTED_NORMAL':
            for obj in [o for o in context.selected_objects if o.type == 'MESH']:
                obj.data.use_auto_smooth = True
                for f in obj.data.polygons:
                    f.use_smooth = True
                mod = obj.modifiers.new(type='WEIGHTED_NORMAL', name='Weighted Normal')
                mod.keep_sharp = self.keep_sharp

        if self.type == 'WELD':
            for obj in [o for o in context.selected_objects if o.type == 'MESH']:
                    weld_modifier = bpy.context.object.modifiers.new(name="Weld", type='WELD')
                    weld_modifier.mode = self.merge_mode
                    weld_modifier.merge_threshold = self.merge_threshold
        if self.type == 'LATTICE':
                bpy.ops.hops.mod_lattice("INVOKE_DEFAULT")
                bpy.ops.object.editmode_toggle()
        return {"FINISHED"}

