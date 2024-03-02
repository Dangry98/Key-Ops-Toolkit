import bpy.types
from ..utils.pref_utils import get_keyops_prefs

"""
TODO:
Clean up AddModCylinder and AddQuadSphere
"""

def calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=1.0):
    prefs = get_keyops_prefs()
    if use_relative_scale:
        cursor_location = bpy.context.scene.cursor.location
        camera_pivot_center = context.region_data.view_location
        camera_view_distance = context.area.spaces.active.region_3d.view_distance

        #Need to calculate the distance from the camera pivot center to the cursor in order to compensate for the camera pivot offset from the cursor, otherwise the scale will be off
        distance_to_cursor = (cursor_location - camera_pivot_center).length
        camera_view_distance = (camera_view_distance - distance_to_cursor)

        scale = camera_view_distance / scale_relative_float * custom_scale_factor
        if scale >= 10.0:
            scale = round(scale / 5) * 5  #Round to nearest multiple of 5
        elif scale >= 1.0:
            scale = round(scale * 2) / 2  #Round to nearest 0.5
        else:                                                   
            scale = scale * 1.75  #Add an 75% extra scale to make it easier to see
            scale_levels = [1.0, 0.75, 0.5, 0.25, 0.1, 0.05, 0.025, 0.01, 0.005, 0.0025, 0.001]
            for level in scale_levels:
                if scale >= level:
                    scale = level
                    break
            #Make sure the scale is never 0
            min_scale = prefs.add_object_pie_min_scale
            if scale < min_scale:
                scale = min_scale
    else:
        scale = scale_property
    return scale

def draw_scale_prop(self, layout):
        prop_name = "scale_relative_float" if self.use_relative_scale else "scale_property"
        layout.prop(self, prop_name)
        layout.prop(self, "use_relative_scale")    

def AddModCylinder(context, segment_amount, scale, use_relative_scale, scale_relative_float, scale_property):
    if bpy.context.mode == 'EDIT_MESH':
        bpy.ops.object.editmode_toggle()

    bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=True, align='WORLD',  scale=(1, 1, 1))
    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
    bpy.ops.mesh.edge_collapse()
    bpy.ops.mesh.extrude_region_move(MESH_OT_extrude_region={"use_normal_flip":False, "use_dissolve_ortho_edges":False, "mirror":False}, TRANSFORM_OT_translate={"value":(1, 0, 0),  "orient_type":'GLOBAL', "orient_matrix":((1, 0, 0), (0, 1, 0), (0, 0, 1)), "orient_matrix_type":'GLOBAL', "constraint_axis":(True, False, False), "mirror":False, "use_proportional_edit":False, "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "use_proportional_connected":False, "use_proportional_projected":False, "snap":False, "snap_elements":{'VERTEX'}, "use_snap_project":False, "snap_target":'CLOSEST', "use_snap_self":True, "use_snap_edit":True, "use_snap_nonedit":True, "use_snap_selectable":False, "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0),})
    bpy.ops.mesh.extrude_region_move(MESH_OT_extrude_region={"use_normal_flip":False, "use_dissolve_ortho_edges":False, "mirror":False}, TRANSFORM_OT_translate={"value":(0, 0, 2),  "orient_type":'GLOBAL', "orient_matrix":((1, 0, 0), (0, 1, 0), (0, 0, 1)), "orient_matrix_type":'GLOBAL', "constraint_axis":(False, False, True), "mirror":False, "use_proportional_edit":False, "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "use_proportional_connected":False, "use_proportional_projected":False, "snap":False, "snap_elements":{'VERTEX'}, "use_snap_project":False, "snap_target":'CLOSEST', "use_snap_self":True, "use_snap_edit":True, "use_snap_nonedit":True, "use_snap_selectable":False, "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0),})
    bpy.ops.mesh.extrude_region_move(MESH_OT_extrude_region={"use_normal_flip":False, "use_dissolve_ortho_edges":False, "mirror":False}, TRANSFORM_OT_translate={"value":(-1, -0, -0),  "orient_type":'GLOBAL', "orient_matrix":((1, 0, 0), (0, 1, 0), (0, 0, 1)), "orient_matrix_type":'GLOBAL', "constraint_axis":(True, False, False), "mirror":False, "use_proportional_edit":False, "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "use_proportional_connected":False, "use_proportional_projected":False, "snap":False, "snap_elements":{'VERTEX'}, "use_snap_project":False, "snap_target":'CLOSEST', "use_snap_self":True, "use_snap_edit":True, "use_snap_nonedit":True, "use_snap_selectable":False, "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0),})
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.transform.translate(value=(-0, -0, -1), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', constraint_axis=(False, False, True), mirror=True, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False, snap_elements={'VERTEX'}, use_snap_project=False, snap_target='CLOSEST', use_snap_self=True, use_snap_edit=True, use_snap_nonedit=True, use_snap_selectable=False)
    bpy.ops.object.editmode_toggle()

    bpy.ops.object.modifier_add(type='SCREW')
    bpy.context.object.modifiers["Screw"].name = "Cylinder"
    bpy.ops.object.shade_smooth(use_auto_smooth=True, auto_smooth_angle=1.0472)
    bpy.context.object.modifiers["Cylinder"].use_smooth_shade = True
    bpy.context.object.modifiers["Cylinder"].steps = segment_amount
    bpy.context.object.modifiers["Cylinder"].use_normal_calculate = True
    bpy.context.object.modifiers["Cylinder"].use_normal_flip = True

    scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=0.5)
    if use_relative_scale==False:
            scale = scale*0.5
    obj = bpy.context.active_object
    obj.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.object.modifiers["Cylinder"].use_merge_vertices = True
    bpy.context.object.modifiers["Cylinder"].merge_threshold = scale * 0.1
   
def AddQuadSphere(context, scale, use_relative_scale, scale_relative_float, scale_property, sub_amount, use_modifiers):
    scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=1.0)
    if bpy.context.mode == 'EDIT_MESH':
        bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.primitive_cube_add(size=(scale), align='CURSOR')
    bpy.ops.object.subdivision_set(level=sub_amount)
    bpy.context.object.modifiers["Subdivision"].show_only_control_edges = False
    bpy.ops.object.modifier_add(type='CAST')
    bpy.context.object.modifiers["Cast"].factor = 1
    bpy.ops.object.shade_smooth()
    bpy.ops.transform.resize(value=(1.168, 1.168, 1.168), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', mirror=False, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False, snap_elements={'INCREMENT'}, use_snap_project=False, snap_target='CLOSEST', use_snap_self=True, use_snap_edit=True, use_snap_nonedit=True, use_snap_selectable=False, alt_navigation=True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    if not use_modifiers: 
        bpy.ops.object.convert(target='MESH')

def AddCube(context, scale, use_relative_scale, scale_relative_float, scale_property):
    scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=1.0)
    bpy.ops.mesh.primitive_cube_add(size=scale, enter_editmode=False, align='WORLD',  scale=(1, 1, 1))

def AddPlane(context, scale, use_relative_scale, scale_relative_float, scale_property):
        scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=1.0)
        bpy.ops.mesh.primitive_plane_add(size=scale)
    
def AddUVSphere(context, scale, use_relative_scale, scale_relative_float, scale_property, segment_amount, rings_count):
        scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=0.7)
        if use_relative_scale==False:
            scale = scale*0.5
        bpy.ops.mesh.primitive_uv_sphere_add(radius=scale, ring_count=rings_count, segments=segment_amount)
    
def AddCircle(context, scale, use_relative_scale, scale_relative_float, scale_property, Vertices):
        scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=1.0)
        bpy.ops.mesh.primitive_circle_add(radius=scale*0.5, vertices=Vertices)
    
def AddMonkey(context, scale, use_relative_scale, scale_relative_float, scale_property):
        scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=1.0)
        bpy.ops.mesh.primitive_monkey_add(size=scale)

def AddCylinder(context, segment_amount, scale, use_relative_scale, scale_relative_float, scale_property):
        scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=0.5)
        if use_relative_scale==False:
            scale = scale*0.5
        bpy.ops.mesh.primitive_cylinder_add(radius=scale, depth=scale*2, vertices=segment_amount)

def AddEmpty(context, scale, use_relative_scale, scale_relative_float, scale_property):
    scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=1.0)
    bpy.ops.object.empty_add(type='ARROWS', radius=scale)

class AddMesh(bpy.types.Operator):
    bl_description = "Add a mesh"
    bl_idname = "keyops.add_mesh"
    bl_label = "Add Mesh"
    bl_options = {"REGISTER", "UNDO"}
    prefs = get_keyops_prefs()

    mesh_type: bpy.props.EnumProperty(
        items=[
            ("MODCYLINDER", "Modifier Cylinder", "Add a cylinder with a screw modifier"),
            ("QUADSPHERE", "Quad Sphere", "Add a Quad Sphere"),
            ("CUBE", "Cube", "Add a cube"),
            ("PLANE", "Plane", "Add a plane"),
            ("UVSPHERE", "UV Sphere", "Add a UV sphere"),
            ("CIRCLE", "Circle", "Add a circle"),
            ("MONKEY", "Monkey", "Add a monkey"),
            ("CYLINDER", "Cylinder", "Add a cylinder"),
            ("EMPTY", "Empty", "Add an empty"),],
        name="Mesh Type", default="CUBE") #type:ignore
    scale_property: bpy.props.FloatProperty(name="Size", default=prefs.add_object_pie_default_scale, min=0.1, max=10.0,description="Absolute scale of the mesh", unit='LENGTH') #type:ignore
    use_relative_scale: bpy.props.BoolProperty(name="Use Relative Scale", default=prefs.add_object_pie_use_relative) #type:ignore
    scale_relative_float: bpy.props.FloatProperty(name="Scale Relative", default=prefs.add_object_pie_relative_scale, min=1.0, max=25.0, description="Relative scale of the mesh") #type:ignore
    segment_amount: bpy.props.IntProperty(name="Segments", default=32, min=3, max=256, description="Amount of segments the cylinder has") #type:ignore
    sub_amount: bpy.props.IntProperty(name="Subdive Amount", default=4, min=1, max=6) #type:ignore
    use_modifiers: bpy.props.BoolProperty(name="Use Modifiers", default=True) #type:ignore
    Vertices: bpy.props.IntProperty(name="Vertices",default=32,min=3,max=256, description="Amount of vertices the circle has") #type:ignore
    rings_count: bpy.props.IntProperty(name="Rings", default=16, min=3, max=256, description="Amount of rings the sphere has")  #type:ignore

    def draw(self, context):
        layout = self.layout
        if self.mesh_type == "MODCYLINDER":
            layout.prop(self, "segment_amount")
        elif self.mesh_type == "QUADSPHERE":
            layout.prop(self, "sub_amount")
            layout.prop(self, "use_modifiers")
        elif self.mesh_type == "CIRCLE":
            layout.prop(self, "Vertices")
        elif self.mesh_type == "CYLINDER":
            layout.prop(self, "segment_amount")
        elif self.mesh_type == "UVSPHERE":
            layout.prop(self, "segment_amount")
            layout.prop(self, "rings_count")
            
        draw_scale_prop(self, layout)

    def execute(self, context):
        if self.mesh_type == "MODCYLINDER":
            AddModCylinder(context, self.segment_amount, self.scale_property, self.use_relative_scale, self.scale_relative_float, self.scale_property)
        elif self.mesh_type == "QUADSPHERE":
            AddQuadSphere(context, self.scale_property, self.use_relative_scale, self.scale_relative_float, self.scale_property, self.sub_amount, self.use_modifiers)
        elif self.mesh_type == "CUBE":
            AddCube(context, self.scale_property, self.use_relative_scale, self.scale_relative_float, self.scale_property)
        elif self.mesh_type == "PLANE":
            AddPlane(context, self.scale_property, self.use_relative_scale, self.scale_relative_float, self.scale_property)
        elif self.mesh_type == "UVSPHERE":
            AddUVSphere(context, self.scale_property, self.use_relative_scale, self.scale_relative_float, self.scale_property, self.segment_amount, self.rings_count)
        elif self.mesh_type == "CIRCLE":
            AddCircle(context, self.scale_property, self.use_relative_scale, self.scale_relative_float, self.scale_property, self.Vertices)
        elif self.mesh_type == "MONKEY":
            AddMonkey(context, self.scale_property, self.use_relative_scale, self.scale_relative_float, self.scale_property)
        elif self.mesh_type == "CYLINDER":
            AddCylinder(context, self.segment_amount, self.scale_property, self.use_relative_scale, self.scale_relative_float, self.scale_property)
        elif self.mesh_type == "EMPTY":
            AddEmpty(context, self.scale_property, self.use_relative_scale, self.scale_relative_float, self.scale_property)
        return {'FINISHED'}