import bpy.types, bmesh
from ..utils.pref_utils import get_keyops_prefs
from ..utils.pref_utils import clear_registered_keymaps
from bpy.types import Menu

"""
TODO:
Add Support for Custom Meshes from .blend, fbx and bpy.ops
"""

registered_add_objects_pie_keymaps = []

def register_add_objects_pie_keymaps():
    global registered_add_objects_pie_keymaps
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='3D View Generic', space_type='VIEW_3D')
    kmi = km.keymap_items.new('wm.call_menu_pie', 'A', 'PRESS', shift=True, alt=True)
    kmi.properties.name = 'KEYOPS_MT_add_objects_pie_menu'
    registered_add_objects_pie_keymaps.append((km, kmi))

def calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=1.0):
    prefs = get_keyops_prefs()
    if use_relative_scale:
        view_loc = context.space_data.region_3d.view_matrix.inverted().translation
        cursor_location = context.scene.cursor.location
        distance = (view_loc - cursor_location).length

        #Need to calculate the distance from the camera pivot center to the cursor in order to compensate for the camera pivot offset from the cursor, otherwise the scale will be off

        scale = distance / scale_relative_float * custom_scale_factor
        
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
        row = layout.row()
        row.prop(self, prop_name)
        row.prop(self, "use_relative_scale")    

def is_orthographic_view(context):
    space_data = context.space_data
    region_3d = getattr(space_data, "region_3d", None)
    return region_3d is not None and region_3d.view_perspective == 'ORTHO'

def get_cylinder_dimensions(context, radius, height, use_relative_scale, scale_relative_float, scale_property):
    if use_relative_scale:
        relative_scale = calculate_scale(
            context,
            scale_property,
            use_relative_scale,
            scale_relative_float,
            custom_scale_factor=1.0,
        )
        return max(radius * relative_scale, 0.0001), max(height * relative_scale, 0.0001)
    return max(radius, 0.0001), max(height, 0.0001)


def format_length_value(context, value):
    unit_settings = context.scene.unit_settings
    return bpy.utils.units.to_string(
        unit_settings.system,
        'LENGTH',
        value,
        precision=4,
        split_unit=False,
        compatible_unit=False,
    )


def AddModCylinder(context, segment_amount, radius, height, align_to_view=False):
    if bpy.context.mode == 'EDIT_MESH':
        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.select_all(action='DESELECT')

    radius = max(radius, 0.0001)
    height = max(height, 0.0001)
    half_height = height * 0.5

    bm = bmesh.new()

    v1 = bm.verts.new((0, 0, -half_height))
    v2 = bm.verts.new((radius, 0, -half_height))
    v3 = bm.verts.new((radius, 0, half_height))
    v4 = bm.verts.new((0, 0, half_height))

    # Create edges
    bm.edges.new((v1, v2))
    bm.edges.new((v4, v3))
    bm.edges.new((v2, v3))

    mesh = bpy.data.meshes.new("ModifierCylinder")
    bm.to_mesh(mesh)
    bm.free()

    # link it to the scene
    obj = bpy.data.objects.new("ModifierCylinder", mesh)
    bpy.context.collection.objects.link(obj)

    obj.location = bpy.context.scene.cursor.location

    if align_to_view:
        space_data = context.space_data
        region_3d = getattr(space_data, "region_3d", None)
        if region_3d is not None and region_3d.view_perspective == 'ORTHO':
            obj.rotation_euler = region_3d.view_rotation.to_euler()

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # add screw modifier
    screw_modifier = obj.modifiers.new(name="Cylinder", type='SCREW')
    screw_modifier.use_smooth_shade = True
    screw_modifier.steps = segment_amount
    screw_modifier.use_normal_calculate = True
    screw_modifier.use_normal_flip = True
    screw_modifier.use_merge_vertices = True
    screw_modifier.merge_threshold = min(radius, height) * 0.1


def AddQuadSphere(context, scale, use_relative_scale, scale_relative_float, scale_property, sub_amount, use_modifiers):
    if bpy.app.version >= (5, 3, 0):
        if bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.select_all(action='DESELECT')
        scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=1.0) *0.5
        bpy.ops.mesh.primitive_quad_sphere_add(radius=scale, align='WORLD', location=context.scene.cursor.location, segments=sub_amount)
        return

    if bpy.context.mode == 'EDIT_MESH':
        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.select_all(action='DESELECT')

    scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=1.0)
    scale = scale * 1.168 # round it to full Meters
    
    mesh = bpy.data.meshes.new("QuadSphere")
    obj = bpy.data.objects.new("QuadSphere", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=scale)

    for poly in bm.faces:
        poly.smooth = True

    bm.to_mesh(mesh)
    bm.free()

    obj.location = bpy.context.scene.cursor.location

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    subdive_modifier = obj.modifiers.new(name="Subdivision", type='SUBSURF')
    subdive_modifier.levels = sub_amount
    subdive_modifier.show_only_control_edges = False
    cast_modifier = obj.modifiers.new(name="Cast", type='CAST')
    cast_modifier.factor = 1.0

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

def AddCylinder(context, segment_amount, radius, height):
        radius = max(radius, 0.0001)
        height = max(height, 0.0001)
        bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=height, vertices=segment_amount)

def AddEmpty(context, scale, use_relative_scale, scale_relative_float, scale_property):
    scale = calculate_scale(context, scale_property, use_relative_scale, scale_relative_float, custom_scale_factor=1.0)
    bpy.ops.object.empty_add(type='ARROWS', radius=scale)

def Add_Blend(context, scale, use_relative_scale, scale_relative_float, scale_property):
    prefs = get_keyops_prefs()
    
    blendpath = prefs.add_object_pie_blend_file_path
    namelist = prefs.add_object_pie_blend_object_name
    #add a , after each name to import many objects at once!
    namelist = namelist.split(",")

    with bpy.data.libraries.load(blendpath, link=False) as (data_from, data_to):
        data_to.objects = [name for name in data_from.objects if name in namelist]

    bpy.ops.object.select_all(action='DESELECT')

    for obj in data_to.objects:
        bpy.context.scene.collection.objects.link(obj)
        obj.select_set(True)
        context.view_layer.objects.active = obj

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
            ("EMPTY", "Empty", "Add an empty"),
            ("BLEND", ".blend", "Add a object from a .blend file"),
            ("CUSTOM", "Custom", "Add a object with bpy.ops")],
        name="Mesh Type", default="CUBE") #type:ignore
    scale_property: bpy.props.FloatProperty(name="Size", default=prefs.add_object_pie_default_scale, min=0.1, max=10.0,description="Absolute scale of the mesh", unit='LENGTH') #type:ignore
    use_relative_scale: bpy.props.BoolProperty(name="Relative Scale", default=prefs.add_object_pie_use_relative) #type:ignore
    scale_relative_float: bpy.props.FloatProperty(name="Scale", default=prefs.add_object_pie_relative_scale, min=1.0, max=25.0, description="Relative scale of the mesh") #type:ignore
    cylinder_radius: bpy.props.FloatProperty(name="Radius", default=0.5, min=0.0001, max=1000.0, description="Radius of the cylinder", unit='LENGTH') #type:ignore
    cylinder_height: bpy.props.FloatProperty(name="Height", default=1.0, min=0.0001, max=1000.0, description="Height of the cylinder", unit='LENGTH') #type:ignore
    segment_amount: bpy.props.IntProperty(name="Segments", default=32, min=3, max=256, description="Amount of segments the cylinder has") #type:ignore
    if bpy.app.version >= (5, 3, 0):
        sub_amount: bpy.props.IntProperty(name="Subdive Amount", default=4, min=2, max=200) #type:ignore
    else:
        sub_amount: bpy.props.IntProperty(name="Subdive Amount", default=4, min=1, max=6) #type:ignore
    use_modifiers: bpy.props.BoolProperty(name="Use Modifiers", default=True) #type:ignore
    Vertices: bpy.props.IntProperty(name="Vertices",default=32,min=3,max=256, description="Amount of vertices the circle has") #type:ignore
    rings_count: bpy.props.IntProperty(name="Rings", default=16, min=3, max=256, description="Amount of rings the sphere has")  #type:ignore
    align_to_view: bpy.props.BoolProperty(name="Align to View", default=True, description="Align Modifier Cylinder to viewport when in orthographic view") #type:ignore

    def draw(self, context):
        layout = self.layout
        if self.mesh_type == "MODCYLINDER":
            layout.label(text="Modifier Cylinder", icon="MOD_SCREW")
            layout.prop(self, "segment_amount")
            layout.prop(self, "cylinder_radius")
            layout.prop(self, "cylinder_height")
            layout.prop(self, "use_relative_scale")
            if self.use_relative_scale:
                layout.prop(self, "scale_relative_float")
                radius, height = get_cylinder_dimensions(
                    context,
                    self.cylinder_radius,
                    self.cylinder_height,
                    self.use_relative_scale,
                    self.scale_relative_float,
                    self.scale_property,
                )
                layout.label(text=f"Final Radius: {format_length_value(context, radius)}")
                layout.label(text=f"Final Height: {format_length_value(context, height)}")

        elif self.mesh_type == "QUADSPHERE":
            quad_icon = "MESH_QUADSPHERE" if bpy.app.version >= (5, 3, 0) else "MESH_UVSPHERE"
            layout.label(text="Quad Sphere", icon=quad_icon)
            if bpy.app.version < (5, 3, 0):
                layout.prop(self, "use_modifiers")
            layout.prop(self, "sub_amount")
        elif self.mesh_type == "CUBE":
            layout.label(text="Cube", icon="MESH_CUBE")
        elif self.mesh_type == "PLANE":
            layout.label(text="Plane", icon="MESH_PLANE")
        elif self.mesh_type == "UVSPHERE":
            layout.label(text="UV Sphere", icon="SHADING_WIRE")
            layout.prop(self, "segment_amount")
            layout.prop(self, "rings_count")
        elif self.mesh_type == "CIRCLE":
            layout.label(text="Circle", icon="MESH_CIRCLE")
            layout.prop(self, "Vertices")
        elif self.mesh_type == "MONKEY":
            layout.label(text="Monkey", icon="MESH_MONKEY")
        elif self.mesh_type == "CYLINDER":
            layout.label(text="Cylinder", icon="MESH_CYLINDER")
            layout.prop(self, "segment_amount")
            layout.prop(self, "cylinder_radius")
            layout.prop(self, "cylinder_height")
            layout.prop(self, "use_relative_scale")
            if self.use_relative_scale:
                layout.prop(self, "scale_relative_float")
                radius, height = get_cylinder_dimensions(
                    context,
                    self.cylinder_radius,
                    self.cylinder_height,
                    self.use_relative_scale,
                    self.scale_relative_float,
                    self.scale_property,
                )
                layout.label(text=f"Final Radius: {format_length_value(context, radius)}")
                layout.label(text=f"Final Height: {format_length_value(context, height)}")
        elif self.mesh_type == "EMPTY":
            layout.label(text="EMPTY", icon="EMPTY_ARROWS")
        elif self.mesh_type == "BLEND":
            layout.label(text=".blend", icon="BLENDER")
        elif self.mesh_type == "CUSTOM":
            layout.label(text="Custom", icon="FILE_SCRIPT")
        if self.mesh_type not in {"BLEND", "MODCYLINDER", "CYLINDER"}:
            draw_scale_prop(self, layout)

        if is_orthographic_view(context) and self.mesh_type == "MODCYLINDER":
            layout.prop(self, "align_to_view")

    def execute(self, context):
        radius = None
        height = None

        if self.mesh_type in {"MODCYLINDER", "CYLINDER"}:
            radius, height = get_cylinder_dimensions(context, self.cylinder_radius, self.cylinder_height, self.use_relative_scale, self.scale_relative_float, self.scale_property)
      
        if self.mesh_type == "MODCYLINDER":
            align_to_view = self.align_to_view and is_orthographic_view(context)
            AddModCylinder(context, self.segment_amount, radius, height, align_to_view)
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
            AddCylinder(context, self.segment_amount, radius, height)
        elif self.mesh_type == "EMPTY":
            if context.mode == 'EDIT_MESH':
                bpy.ops.object.editmode_toggle()
            AddEmpty(context, self.scale_property, self.use_relative_scale, self.scale_relative_float, self.scale_property)
        elif self.mesh_type == "BLEND":
            Add_Blend(context, self.scale_property, self.use_relative_scale, self.scale_relative_float, self.scale_property)
        return {'FINISHED'}
    
def register_add_objects_pie():
    bpy.utils.register_class(AddMesh)
    bpy.utils.register_class(AddObjectsPie)
    register_add_objects_pie_keymaps()

def unregister_add_objects_pie():
    clear_registered_keymaps(registered_add_objects_pie_keymaps)
    bpy.utils.unregister_class(AddMesh)
    bpy.utils.unregister_class(AddObjectsPie)

class AddObjectsPie(Menu):
    bl_idname = "KEYOPS_MT_add_objects_pie_menu"
    bl_label = "Add Mesh Pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        prefs = get_keyops_prefs()

        pie.operator("keyops.add_mesh", text="UV Sphere", icon="SHADING_WIRE").mesh_type = "UVSPHERE"  # LEFT

        pie.operator("keyops.add_mesh", text="Cube", icon="MESH_CUBE").mesh_type = "CUBE"  # RIGHT

        pie.operator("keyops.add_mesh", text="Cylinder", icon="MESH_CYLINDER").mesh_type = "CYLINDER"  # BOTTOM

        pie.operator("keyops.add_mesh", text="Plane", icon="MESH_PLANE").mesh_type = "PLANE"  # TOP

        pie.operator("keyops.add_mesh", text="Mod Cylinder", icon="MOD_SCREW").mesh_type = "MODCYLINDER"  # LEFT TOP

        if prefs.add_object_pie_Enum == "EMPTY":
            pie.operator("keyops.add_mesh", text="Empty", icon="EMPTY_ARROWS").mesh_type = "EMPTY"  # RIGHT TOP
        if prefs.add_object_pie_Enum == "MONKEY":
            pie.operator("keyops.add_mesh", text="Monkey", icon="MESH_MONKEY").mesh_type = "MONKEY"  # RIGHT TOP
        if prefs.add_object_pie_Enum == "OTHER":
            if context.mode == 'EDIT_MESH':
                pie.operator("wm.call_menu", text="Other", icon="ADD").name = "VIEW3D_MT_mesh_add"  # RIGHT TOP
            else:
                pie.operator("wm.call_menu", text="Other", icon="ADD").name = "VIEW3D_MT_add"  # RIGHT TOP
        if prefs.add_object_pie_Enum == "BLEND":
            pie.operator("keyops.add_mesh", text=".blend", icon="BLENDER").mesh_type = "BLEND"  # RIGHT TOP
        if prefs.add_object_pie_Enum == "CUSTOM":
            pie.operator("keyops.add_mesh", text="Custom", icon="FILE_SCRIPT").mesh_type = "CUSTOM"  # RIGHT TOP
        
        if bpy.app.version >= (5, 3, 0):
            pie.operator("keyops.add_mesh", text="Quad Sphere", icon="MESH_QUADSPHERE").mesh_type = "QUADSPHERE"  # LEFT BOTTOM
        else:
            pie.operator("keyops.add_mesh", text="Quad Sphere", icon="MESH_UVSPHERE").mesh_type = "QUADSPHERE"  # LEFT BOTTOM
        pie.operator("keyops.add_mesh", text="Circle", icon="MESH_CIRCLE").mesh_type = "CIRCLE"  # RIGHT BOTTOM  
    
