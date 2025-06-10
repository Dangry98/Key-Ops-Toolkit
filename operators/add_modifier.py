import bpy.types
from ..utils.pref_utils import get_is_addon_enabled
from mathutils import Vector, Matrix
from bpy.types import Menu
from ..utils.utilities import force_show_obj

hardops = None
modifier_list = None
started_in_edit_mode = False

class Dummy_AddModifier(bpy.types.Operator):
    bl_description = "Add a modifier"
    bl_idname = "keyops.dummy_add_modifier"
    bl_label = "Add Modifier"
    bl_options = {'INTERNAL'}

    def register():
        bpy.utils.register_class(AddModifierPie)
        bpy.utils.register_class(AddModifierModal)
    def unregister():
        bpy.utils.unregister_class(AddModifierPie)
        bpy.utils.unregister_class(AddModifierModal)

boolean_objects = set()
start_active_obj_booleon_scroll = None
boolean_index = 0
previus_bool_visibility = {}

def toggle_visibility(context, new_index, start=False):
    global boolean_objects, boolean_index, start_active_obj_booleon_scroll
 
    boolean_index = new_index

    for i, obj in enumerate(boolean_objects):
        if obj:
            if (i != new_index):
                obj.hide_set(True)
                if obj.select_get():
                    obj.select_set(False)
            else:
                force_show_obj(context, obj, select=True)

    # set active modifier to the new index
    if start_active_obj_booleon_scroll:
        for mod in start_active_obj_booleon_scroll.modifiers:
            if mod.type == 'BOOLEAN' and mod.object == boolean_objects[boolean_index]:
                start_active_obj_booleon_scroll.modifiers.active = mod
                break

def properties_panel_pin(context, obj, pin=True):
    """ Pin/unpin the properties panel to the active object """
    for area in context.screen.areas:
        if area.type == 'PROPERTIES':
            space_data = area.spaces.active
            obj = context.active_object

            if pin:
                space_data.pin_id = obj
            else:
                space_data.pin_id = None
            break

def boolean_scroll_done(context):
    context.workspace.status_text_set(None) # Clear status bar
    properties_panel_pin(context, start_active_obj_booleon_scroll, pin=False)

def toggle_wire_solid_display(context, obj, value=None):
    """ Toggle or set wire/solid display mode for the given object """
    if obj:
        if value is None:
            value = 'SOLID' if obj.display_type == 'WIRE' else 'WIRE'
        obj.display_type = value
        is_solid = value == 'SOLID'
        obj.visible_camera = is_solid
        obj.visible_shadow = is_solid

class BooleanScroll(bpy.types.Operator):
    bl_description = "Scroll through boolean modifiers"
    bl_idname = "object.boolean_scroll"
    bl_label = "Boolean Scroll"
    bl_options = {'INTERNAL'}

    @classmethod 
    def poll(cls, context):
        active = context.active_object
        if not active or active.type != 'MESH':
            return False
        return any(mod.type == 'BOOLEAN' for mod in context.active_object.modifiers)

    def modal(self, context, event):
        global start_active_obj_booleon_scroll, boolean_objects, boolean_index, previus_bool_visibility

        # Draw shortcuts in status bar
        context.workspace.status_text_set(
            "Scroll up/down : Next/Previous | "
            "Left Mouse : Confirm " + chr(0x2714) + " | "
            "Right Mouse : Cancel " + chr(0x2716) + " | "
            "Alt H : Show All | "
            "Q/E : Move up/down"
        )

        if (event.type == 'WHEELDOWNMOUSE' or event.type == 'PAGE_DOWN' or event.type == 'NUMPAD_PLUS' or event.type == 'S') and event.value == 'PRESS':
            next_index = (boolean_index + 1) % len(boolean_objects)
            toggle_visibility(context, next_index)
            return {'RUNNING_MODAL'}
            
        elif (event.type == 'WHEELUPMOUSE' or event.type == 'PAGE_UP' or event.type == 'NUMPAD_MINUS' or event.type == 'W') and event.value == 'PRESS':
            prev_index = (boolean_index - 1) % len(boolean_objects)
            toggle_visibility(context, prev_index)
            return {'RUNNING_MODAL'}
        
        elif event.type == 'LEFTMOUSE' or event.type == 'SPACE' or event.type == 'NUMPAD_ENTER' or event.type == 'ENTER':
            boolean_scroll_done(context)
            return {'FINISHED'}
        
        elif event.type == 'RIGHTMOUSE' or event.type == 'ESC':
            for obj in context.selected_objects:
                if obj:
                    obj.select_set(False)
                    obj.hide_set(False)
            # restore the visibility of the boolean objects
            for obj, visibility in previus_bool_visibility.items():
                if obj:
                    obj.hide_set(visibility)
                    # obj.select_set(False)
         
            if start_active_obj_booleon_scroll:
                context.view_layer.objects.active = start_active_obj_booleon_scroll
                start_active_obj_booleon_scroll.select_set(True)
            boolean_scroll_done(context)
            return {'CANCELLED'}
        
        elif event.type == 'H' and event.value == 'PRESS' and event.alt:
            for obj in boolean_objects:
                if obj:
                    force_show_obj(context, obj, select=True)
            boolean_scroll_done(context)
            return {'FINISHED'}
        
        elif event.type in {'Q', 'E'} and event.value == 'PRESS':
            active_modifier = start_active_obj_booleon_scroll.modifiers.active
            active_index = start_active_obj_booleon_scroll.modifiers.find(active_modifier.name)
            offset = -1 if event.type == 'Q' else 1
            target_index = active_index + offset
            
            if 0 <= target_index < len(start_active_obj_booleon_scroll.modifiers):
                start_active_obj_booleon_scroll.modifiers.move(active_index, target_index)
            return {'RUNNING_MODAL'}
   
        return {'PASS_THROUGH'}

    def invoke(self, context, _event):
        global boolean_objects, boolean_index, start_active_obj_booleon_scroll, previus_bool_visibility
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                area.spaces.active.context = 'MODIFIER'
        
        boolean_index = 0
        start_active_obj_booleon_scroll = context.active_object
        boolean_objects = [mod.object for mod in context.active_object.modifiers if mod.type == 'BOOLEAN' and mod.object]
        # save the current state of the boolean objects
        previus_bool_visibility = {obj: obj.hide_get() for obj in boolean_objects}
        
        cutters_collection = bpy.data.collections.get("Cutters")
        if cutters_collection:
            for obj in cutters_collection.objects:
                obj.hide_set(True)
                obj.select_set(False)

        properties_panel_pin(context, start_active_obj_booleon_scroll, pin=True)

        for obj in context.selected_objects:
            obj.select_set(False)
            
        if boolean_objects:
            toggle_visibility(context, 0, start=True)
            # force_show_obj(context, boolean_objects[0], select=True)
            context.window_manager.modal_handler_add(self)

            return {'RUNNING_MODAL'}
        return {'CANCELLED'}

booleon_descriptions = {
    'UNION': "Union",
    'DIFFERENCE': "Difference",
    'INTERSECT': "Intersect",
    'SLICE': "Slice"
}
class AddBooleanModifier(bpy.types.Operator):
    bl_description = "Add a boolean modifier"
    bl_idname = "object.add_boolean_modifier_operator"
    bl_label = ""
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.StringProperty(name="Type", description="", default="") #type:ignore
    solver: bpy.props.EnumProperty(name="Solver", description="", items=(
            ('EXACT', 'Exact', ''),
            ('FAST', 'Fast', '')),
            default='FAST') #type:ignore
    
    parant: bpy.props.BoolProperty(name="Parent", description="", default=False) #type:ignore
    apply: bpy.props.BoolProperty(name="Apply", description="", default=False) #type:ignore

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH' 

    @classmethod   
    def description(cls, context, operator):
        return booleon_descriptions[operator.type]
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="Boolean", icon="MOD_BOOLEAN")
        row = layout.row()
        row.prop(self, "solver", expand=True)
        row = layout.row()
        row.prop(self, "parant", expand=True)

    def execute(self, context):
        if len(context.selected_objects) < 2:
            self.report({'WARNING'}, "Select at least 2 objects")
            return {'CANCELLED'}
        
        cutters = set(bpy.context.selected_objects)
        active = bpy.context.active_object
        cutters.remove(active)

        def move_to_cutter_collection(objs):
            cutter_collection = bpy.data.collections.get("Cutters")
            if not cutter_collection:
                cutter_collection = bpy.data.collections.new("Cutters")
                cutter_collection.color_tag = "COLOR_01"
                bpy.context.scene.collection.children.link(cutter_collection)

            for obj in objs:
                for coll in obj.users_collection:
                    coll.objects.unlink(obj)
                    cutter_collection.objects.link(obj)
        
            if cutter_collection.hide_viewport == True or context.view_layer.layer_collection.children[cutter_collection.name].hide_viewport == True:
                cutter_collection.hide_viewport = False
                context.view_layer.layer_collection.children[cutter_collection.name].hide_viewport = False
                for obj in cutter_collection.objects:
                    obj.hide_set(True)

            for obj in objs:
                obj.hide_set(False)
                obj.select_set(True)

        operations = {
            'UNION': 'UNION',
            'DIFFERENCE': 'DIFFERENCE', 
            'INTERSECT': 'INTERSECT',
            'SLICE': 'SLICE'
        }
                    
        for obj in cutters:
            if self.parant:
                context.view_layer.update()
                obj.parent = active
                # matris inverse to get the correct location of the object
                obj.matrix_parent_inverse = active.matrix_world.inverted() 

            if self.type == 'SLICE':
                if obj != active:
                    mod = active.modifiers.new(type='BOOLEAN', name='Boolean')
                    mod.operation = "DIFFERENCE"
                    mod.solver = self.solver
                    mod.object = obj
                    toggle_wire_solid_display(context, obj, value='WIRE')
                else:
                    # duplicate the object and add a intesect boolean modifier to it
                    duplicate = obj.copy()
                    duplicate.data = obj.data.copy()
                    context.collection.objects.link(duplicate)
                    duplicate.select_set(True)
                    context.view_layer.objects.active = duplicate
                    mod = duplicate.modifiers.new(type='BOOLEAN', name='Boolean')
                    mod.operation = "INTERSECT"
                    mod.solver = self.solver
                    mod.object = active
                    toggle_wire_solid_display(context, obj, value='WIRE')

            else:
                if obj != active:
                    mod = active.modifiers.new(type='BOOLEAN', name='Boolean')
                    mod.operation = operations[self.type]
                    mod.solver = self.solver
                    mod.object = obj
                    toggle_wire_solid_display(context, obj, value='WIRE')
            
        active.select_set(False)

        move_to_cutter_collection(cutters)

        return {'FINISHED'}

        
class AddModifier(bpy.types.Operator):
    bl_description = "Add a modifier"
    bl_idname = "keyops.add_modifier"
    bl_label = "Add Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.StringProperty(name="Type", description="", default="") #type:ignore
    quad_method: bpy.props.EnumProperty(name="Method", description="", items=(
            ('BEAUTY', 'Beauty', ''),
            ('FIXED', 'Fixed', ''),
            ('FIXED_ALTERNATE', 'Fixed Alternate', ''),
            ('SHORTEST_DIAGONAL', 'Shortest Diagonal', ''),
            ('LONGEST_DIAGONAL', 'Longest Diagonal', ''))) #type:ignore
    minimum_vertices: bpy.props.IntProperty(name="Min Vertices", description="", default=4) #type:ignore
    keep_custom_normals: bpy.props.BoolProperty(name="Keep Normals",description="", default=True) #type:ignore
    keep_sharp: bpy.props.BoolProperty(name="Keep Sharp",description="", default=True) #type:ignore
    merge_threshold: bpy.props.FloatProperty(name="Merge Threshold",description="", default=0.0001, min=0) #type:ignore
    merge_mode: bpy.props.EnumProperty(name="Mode", description="", items=(
            ('CONNECTED', 'Connected', ''),
            ('ALL', 'All', ''))) #type:ignore
    modified: bpy.props.BoolProperty(name="Modified", description="Use final geometry, Edit mode only", default = False) #type:ignore
    individual: bpy.props.BoolProperty(name="Individual", description="Assign individual lattice per object (hold Alt)", options={'SKIP_SAVE'}, default = False) #type:ignore
    mode: bpy.props.EnumProperty(name="Mode",default='KEY_BSPLINE',items=
            (("KEY_LINEAR", "Linear", ""), ("KEY_BSPLINE", "Bspline", ""))) #type:ignore
    lattice_subdivisions: bpy.props.IntProperty(name="Subdivisions", description="Subdivisions", default=1, min=1, max=10) #type:ignore
    cage : bpy.props.BoolProperty(name="Cage", description="Use cage", default=True) #type:ignore
    subdivisions: bpy.props.IntProperty(name="Subdivisions", description="Subdivisions", default=2, min=2, max=64) #type:ignore
    outside: bpy.props.BoolProperty(name="Outside", description="Use outside", default=True) #type:ignore
    shrink_mode: bpy.props.EnumProperty(name="Mode", description="", items=(
            ('NEAREST_SURFACEPOINT', 'Nearest Surface Point', ''),
            ('PROJECT', 'Project', ''),
            ('NEAREST_VERTEX', 'Nearest Vertex', ''),
            ('TARGET_PROJECT', 'Target Project', '')), default="NEAREST_SURFACEPOINT") #type:ignore
    
    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' or o.type == 'LATTICE' or o.type == 'CURVE' or o.type == 'SURFACE' or o.type == 'FONT' for o in context.selected_objects)
    
    def invoke(self, context, event):
        global ev 
        global started_in_edit_mode
        ev = []
        if event.ctrl:
            ev.append("Ctrl")
        if event.shift:
            ev.append("Shift")
        if event.alt:
            ev.append("Alt")
        if "Alt" in ev:
            self.individual = True
        if "Ctrl" in ev:
            self.modified = True

        started_in_edit_mode = context.mode == 'EDIT_MESH'
        return self.execute(context)
    
    def draw(self, context):
        global started_in_edit_mode

        if self.type == 'TRIANGULATE':
            row = self.layout.row()
            row.label(text="Triangulate", icon="MOD_TRIANGULATE")
            row = self.layout.row()
            row.prop(self, "quad_method")
            if bpy.app.version >= (4, 2, 1):
                row = self.layout.row()
                row.prop(self, "keep_custom_normals")
            row = self.layout.row()
            row.prop(self, "minimum_vertices")

        if self.type == 'WEIGHTED_NORMAL':
            row = self.layout.row()
            row.label(text="Weighted Normal", icon="MOD_NORMALEDIT")

            self.layout.prop(self, "keep_sharp")
        if self.type == 'WELD':
            row = self.layout.row()
            row.label(text="Weld", icon="AUTOMERGE_OFF")

            self.layout.prop(self, "merge_mode")
            self.layout.prop(self, "merge_threshold")
        
        if self.type == 'SHRINKWRAP':
            row = self.layout.row()
            row.label(text="Shrinkwrap", icon="MOD_SHRINKWRAP")

            self.layout.prop(self, "shrink_mode")
            self.layout.label(text="Active object is the target", icon='INFO')

        if self.type == 'LATTICE':
            row = self.layout.row()
            row.label(text="Lattice", icon="MOD_LATTICE")

            row = self.layout.row()
            row.label(text="Interpolation:")
            row.prop(self, "mode", expand=True)
            self.layout.prop(self, "individual")
            if started_in_edit_mode:
                self.layout.prop(self, "modified")
            self.layout.prop(self, "subdivisions")
            self.layout.prop(self, "outside")
            row = self.layout.row()
            row.alignment = 'LEFT'
            row.prop(self, "cage", icon='OUTLINER_DATA_MESH')
            if self.cage:
                row.label(text="Can cause preview issues", icon='ERROR')

    def execute(self, context):
        global hardops
        global modifier_list

        if hardops is None:
            hardops = get_is_addon_enabled("HOps")
            if hardops == False:
                hardops = get_is_addon_enabled("hardops")

        if modifier_list is None:
            modifier_list = get_is_addon_enabled("Modifier_List_Fork")

        if self.type == 'TRIANGULATE':
            #sort triabgelate before mirror modifier? For better baking?
            for obj in [o for o in context.selected_objects if o.type == 'MESH']:
                mod = obj.modifiers.new(type='TRIANGULATE', name='Triangulate')
                mod.quad_method = self.quad_method
                mod.min_vertices = self.minimum_vertices
                if bpy.app.version >= (4, 2, 1):
                    mod.keep_custom_normals = self.keep_custom_normals
                mod.show_in_editmode = False

        if self.type == 'WEIGHTED_NORMAL':
            for obj in [o for o in context.selected_objects if o.type == 'MESH']:
                mod = obj.modifiers.new(type='WEIGHTED_NORMAL', name='Weighted Normal')
                mod.keep_sharp = self.keep_sharp
                if obj.modifiers:
                    for modifier in obj.modifiers:
                        if "Smooth by Angle" in modifier.name or "Auto Smooth" in modifier.name:
                            mod.use_pin_to_last = True
                            #move it to the bottom of the stack
                            active_index = obj.modifiers.find(mod.name)
                            obj.modifiers.move(active_index, len(obj.modifiers) - 1)

        if self.type == 'WELD':
            for obj in [o for o in context.selected_objects if o.type == 'MESH']:
                    weld_modifier = obj.modifiers.new(name="Weld", type='WELD')
                    weld_modifier.mode = self.merge_mode
                    weld_modifier.merge_threshold = self.merge_threshold

        if self.type == 'SHRINKWRAP':
            #selected juts 1 mesh object
            selected = [o for o in context.selected_objects if o.type == 'MESH']
            if len(selected) == 1:
                bpy.ops.object.modifier_add(type='SHRINKWRAP')
            else:
                #add the shrinkwrap modifier to the none active object and choose the active object as target
                has_active_object = False
                if context.active_object.type == 'MESH':
                    has_active_object = True
                if has_active_object:
                    for obj in selected:
                        if obj != context.active_object:
                            mod = obj.modifiers.new(type='SHRINKWRAP', name='Shrinkwrap')
                            mod.target = context.active_object
                            mod.wrap_method = self.shrink_mode
                            mod.show_on_cage = True
                            mod.show_in_editmode = True
                else:       
                    self.report({'ERROR'}, "Needs to have one active mesh object (target) and one or more mesh objects selected")
                    return {'CANCELLED'}
                    
        if self.type == 'LATTICE':  
            context.evaluated_depsgraph_get()
            supported_objects = ["MESH", "CURVE", "SURFACE", "FONT"]
            
            for obj in context.selected_objects:
                if obj.type == 'LATTICE':
                    obj.select_set(False)

            if context.mode != 'EDIT_MESH':
                if self.individual:
                    for obj in [o for o in context.selected_objects if o.type in supported_objects]:
                        lattice_ob = create_lattice_object(self, context)

                        # Get object middle point to compensate for the object pivot offset
                        object_center = (Vector(obj.bound_box[0]) + Vector(obj.bound_box[6])) / 2

                        lattice_ob.location = obj.matrix_world @ object_center
                        lattice_ob.scale = obj.dimensions * 1.01
                        lattice_ob.rotation_euler = obj.rotation_euler

                        lattice_ob.select_set(True)
                        context.view_layer.objects.active = lattice_ob

                        add_lattice_modifier(self, obj, lattice_ob)

                    for obj in context.selected_objects:
                        if obj.type != 'LATTICE':
                            obj.select_set(False)
                            
                if not self.individual:
                    #get bounding box of all selected mesh objects and create a lattice object from it
                    all_bounds = []
                    for obj in [o for o in context.selected_objects if o.type in supported_objects]:
                        obj_bounds = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
                        all_bounds += obj_bounds
                    
                    if not all_bounds: return {"CANCELLED"}

                    x_min = min(c[0] for c in all_bounds)
                    x_max = max(c[0] for c in all_bounds)
                    y_min = min(c[1] for c in all_bounds)
                    y_max = max(c[1] for c in all_bounds)
                    z_min = min(c[2] for c in all_bounds)
                    z_max = max(c[2] for c in all_bounds)
           
                    lattice_ob = create_lattice_object(self, context)
                    
                    lattice_ob.location = (x_min + x_max) / 2, (y_min + y_max) / 2, (z_min + z_max) / 2
                    lattice_ob.scale = (x_max - x_min), (y_max - y_min), (z_max - z_min)
                    lattice_ob.scale = lattice_ob.scale * 1.01

                    for obj in [o for o in context.selected_objects if o.type in supported_objects]:
                        add_lattice_modifier(self, obj, lattice_ob)

                    for obj in context.selected_objects:
                        if obj.type != 'LATTICE':
                            obj.select_set(False)
                    lattice_ob.select_set(True)
                    context.view_layer.objects.active = lattice_ob
                
                bpy.ops.object.editmode_toggle()
                return {'FINISHED'} 
                    
            elif context.mode == 'EDIT_MESH':
                import time
                exec_time = time.time()
                import bmesh
                depsgraph = context.evaluated_depsgraph_get()

                for obj in [o for o in context.selected_objects if o.type in supported_objects]:
                    if obj.data.total_vert_sel > 0:
                        #add vertex group to selected vertices
                        lattice_verts = obj.vertex_groups.new(name='Lattice')
                        group = lattice_verts.index

                        bm = bmesh.from_edit_mesh(obj.data)
                        bm.verts.layers.deform.verify()

                        bm_deform = bm.verts.layers.deform.active
                        selected_vert = [v for v in bm.verts if v.select]

                        for v in selected_vert:
                            v[bm_deform][group] = 1
                        obj.update_from_editmode()

                context.view_layer.update()

                #if in edit mode, add lattice modifier to the current selection if the object has any selction
                if not self.individual:
                    verts = []
                    # Get bounding box of all selected mesh objects and create one big lattice object from it

                    for obj in [o for o in context.selected_objects if o.type in supported_objects]:
                        if obj.data.total_vert_sel > 0:
                            if self.modified:
                                group = len(obj.vertex_groups) - 1
                                eval = obj.evaluated_get(depsgraph)
                                me = eval.to_mesh()
                                #while using selection instead is way faster, it unforenly does not work in some cases when using modifers if the selction is not propugated
                                verts += [obj.matrix_world @ v.co for v in me.vertices if group in [ vg.group for vg in v.groups]]
                              
                                eval.to_mesh_clear()
                            else:
                                verts += [obj.matrix_world @ v.co for v in obj.data.vertices if v.select]   
                    if not verts: return {"CANCELLED"}

                    min_x, max_x, min_y, max_y, min_z, max_z = get_bounding_box(verts)
                    
                    lattice_ob = create_lattice_object(self, context)

                    lattice_ob.location = (min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2
                    lattice_ob.scale = (max_x - min_x), (max_y - min_y), (max_z - min_z)
                    lattice_ob.scale = lattice_ob.scale * 1.01


                    #if the lattice is completely flat, only have 1 subdivision on z axis
                    if lattice_ob.scale.z == 0:
                        lattice_ob.data.points_w = 1
                        lattice_ob.scale.z = 1.0     

                    #add lattice modifier to selected object and assign vertex group
                    mod = obj.modifiers.new(type='LATTICE', name='Lattice')
                    mod.object = lattice_ob
                    mod.show_in_editmode = self.modified
                    mod.vertex_group = lattice_verts.name
                    mod.show_on_cage = self.cage
                    if self.cage:
                        mod.show_in_editmode = True    

                            
                if self.individual:
                    for obj in [o for o in context.selected_objects if o.type in supported_objects]:
                        verts = []
                        
                        if obj.data.total_vert_sel > 0:
                            lattice_ob = create_lattice_object(self, context)
                            lattice_ob.select_set(True)
                        
                            # verts = [obj.data.vertices[i].co for i in range(len(obj.data.vertices)) if obj.data.vertices[i].select]
                            if self.modified:
                                group = len(obj.vertex_groups) - 1
                                eval = obj.evaluated_get(depsgraph)
                                me = eval.to_mesh()
                                #while using selection instead is way faster, it unforenly does not work in some cases when using modifers if the selction is not propugated
                                if obj.modifiers:
                                    verts += [Matrix() @ v.co for v in me.vertices if group in [ vg.group for vg in v.groups]]
                                else:
                                    verts = [v.co for v in me.vertices if v.select]
                                    
                                eval.to_mesh_clear()
                            else:
                                verts = [v.co for v in obj.data.vertices if v.select]
                            if not verts: return {"CANCELLED"}
                            min_x, max_x, min_y, max_y, min_z, max_z = get_bounding_box(verts)

                            lattice_ob.location = (min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2 
                            lattice_ob.scale = (max_x - min_x), (max_y - min_y), (max_z - min_z)

                            #transform the lattice object to fit the selected vertices
                            lattice_ob.rotation_euler = obj.rotation_euler
                            lattice_ob.location = obj.matrix_world @ lattice_ob.location

                            lattice_ob.scale = obj.scale * lattice_ob.scale * 1.01
                            #needs to get the world scale of objects since they can be paranted to another object with diffrent scale
                            obj_scale = obj.matrix_world.to_scale()
                            lattice_ob.scale *= obj_scale * 1.01
                                    
                            #if the lattice is completely flat, only have 1 subdivision on z axis
                            if lattice_ob.scale.z == 0:
                                lattice_ob.data.points_w = 1
                                lattice_ob.scale.z = 1.0        
                
                            #add lattice modifier to selected object and assign vertex group
                            mod = obj.modifiers.new(type='LATTICE', name='Lattice')
                            mod.object = lattice_ob
                            mod.show_in_editmode = self.modified
                            mod.vertex_group = lattice_verts.name
                            mod.show_on_cage = self.cage
                            if self.cage:
                                mod.show_in_editmode = True 

                bpy.ops.object.mode_set(mode='OBJECT')

                if lattice_ob != None:
                    lattice_ob.select_set(True)
                    context.view_layer.objects.active = lattice_ob

                bpy.ops.object.mode_set(mode='EDIT')
                for obj in context.selected_objects:
                    if obj != lattice_ob:
                        obj.select_set(False) 
            print("Execution time: ", time.time() - exec_time)
        return {'FINISHED'} 
    


def create_lattice_object(self, context):
    global modifier_list
    coll_name = "ML_Gizmo Objects" if modifier_list else "Lattice_Objects"

    lattice = bpy.data.lattices.new(name="Lattice_Gizmo")
    lattice_ob = bpy.data.objects.new("Lattice_Gizmo", lattice)

    if bpy.data.collections.get(coll_name):
        lattice_collection = bpy.data.collections[coll_name]
        bpy.data.collections[coll_name].objects.link(lattice_ob)
     
        if lattice_collection.hide_viewport == True or context.view_layer.layer_collection.children[lattice_collection.name].hide_viewport == True:
                lattice_collection.hide_viewport = False
                context.view_layer.layer_collection.children[lattice_collection.name].hide_viewport = False
                for obj in lattice_collection.objects:
                    obj.hide_set(True)
                lattice_ob.hide_set(False)
                lattice_ob.hide_viewport = False
                lattice_ob.select_set(True)
    
    else:
        ml_col = bpy.data.collections.new(coll_name)
        context.scene.collection.children.link(ml_col)
        bpy.data.collections[coll_name].objects.link(lattice_ob)

    lattice_ob.data.interpolation_type_u = self.mode
    lattice_ob.data.interpolation_type_v = self.mode
    lattice_ob.data.interpolation_type_w = self.mode
    lattice_ob.data.points_u = self.subdivisions
    lattice_ob.data.points_v = self.subdivisions
    lattice_ob.data.points_w = self.subdivisions
    lattice_ob.data.use_outside = self.outside

    return lattice_ob

def add_lattice_modifier(self, obj, lattice_ob):
    mod = obj.modifiers.new(type='LATTICE', name='Lattice')
    mod.object = lattice_ob
    mod.show_on_cage = self.cage
    if self.cage:
        mod.show_in_editmode = True

def get_bounding_box(verts):
    min_x = min([v.x for v in verts])
    max_x = max([v.x for v in verts])
    min_y = min([v.y for v in verts])
    max_y = max([v.y for v in verts])
    min_z = min([v.z for v in verts])
    max_z = max([v.z for v in verts])
    return min_x, max_x, min_y, max_y, min_z, max_z


class AddModifierModal(bpy.types.Operator):
    bl_idname = "keyops.add_modifier_modal"
    bl_label = "Add Modifier Modal"
    bl_options = {'REGISTER', 'UNDO', "BLOCKING"}

    type: bpy.props.StringProperty(name="Type", description="", default="")  # type:ignore
    thickness: bpy.props.FloatProperty(name="Thickness", description="", default=0.0)  # type:ignore

    def modal(self, context, event):
        amount_x = -0.005
        if event.shift:
            print("Shift")
            amount_x = -0.001
            
        if event.type == 'MOUSEMOVE':
            self.thickness = event.mouse_x * amount_x
            if self.type == 'SOLIDIFY':
                for obj in [o for o in context.selected_objects if o.type == 'MESH']:
                    mod = obj.modifiers.get('Solidify')
                    if mod:
                        mod.thickness = self.thickness
                    else:
                        mod = obj.modifiers.new(type='SOLIDIFY', name='Solidify')
                        mod.thickness = self.thickness
            #context.area.tag_redraw()

        elif event.type == 'LEFTMOUSE':
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # Cancel the operation and remove the modifier, but only if it did not have on from the start
            for obj in [o for o in context.selected_objects if o.type == 'MESH']:
                mod = obj.modifiers.get('Solidify')
                obj.modifiers.remove(mod)
          
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.space_data.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}


class AddModifierPie(Menu):
    bl_idname = "KEYOPS_MT_add_modifier_pie"
    bl_label = "Add Modifier Pie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()
        
        global hardops

        if hardops is None:
            hardops = get_is_addon_enabled("HOps")
           
            if hardops == False:
                hardops = get_is_addon_enabled("hardops")

        if hardops:
            pie.operator("hops.st3_array", text="Array", icon="MOD_ARRAY")# LEFT
        else:
            pie.operator("object.modifier_add", text="Array", icon="MOD_ARRAY").type = "ARRAY" # LEFT
            
        if hardops:
            pie.operator("hops.adjust_tthick", text="Solidify", icon="MOD_SOLIDIFY") #RIGHT
        else:
            pie.operator("keyops.add_modifier_modal", text="Solidify", icon="MOD_SOLIDIFY").type = "SOLIDIFY"

        if hardops:
            pie.operator("hops.adjust_bevel", text="Bevel", icon="MOD_BEVEL") #BOTTOM
        else:
            pie.operator("object.modifier_add", text="Bevel", icon="MOD_BEVEL").type = "BEVEL" #BOTTOM

        pie.operator("keyops.add_modifier", text="Weighted Normal", icon="MOD_NORMALEDIT"). type = "WEIGHTED_NORMAL" #TOP
      
        pie.operator("keyops.add_modifier", text="Lattice", icon="MOD_LATTICE").type = "LATTICE" #LEFT TOP

        pie.operator("keyops.add_modifier", text="Weld", icon="AUTOMERGE_OFF").type = "WELD" #RIGHT TOP

        pie.operator("keyops.add_modifier", text="Triangulate", icon="MOD_TRIANGULATE").type = "TRIANGULATE" #LEFT BOTTOM

        pie.operator("keyops.add_modifier", text="Shrinkwrap", icon="MOD_SHRINKWRAP").type = "SHRINKWRAP" #RIGHT BOTTOM
