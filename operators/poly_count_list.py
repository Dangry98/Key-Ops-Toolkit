# Based on the excellent Polycount Addon by Vinc3r
# https://github.com/Vinc3r/Polycount
# I used this addon a lot and really liked it, but I feelt it could be improved in terms of performance, ui and usability when working in big production scenes.
# Its now about 1000-5000x times faster than the original addon, it has a realtime mode by defualt and more streamlined ui along with some new features.

import bpy, time
from bpy.types import PropertyGroup
from bpy.props import (EnumProperty, BoolProperty, StringProperty, PointerProperty, IntProperty)
from ..utils.pref_utils import get_icon, clear_registered_keymaps
from ..utils.pref_utils import feature_on
from bpy.app.handlers import persistent
from ..utils.pref_utils import get_keyops_prefs

# Todo: Add icon in panel and add ms and tris count to panel header

polycount = []  
polycount_sorting_ascending = True
polycount_sorting = 'TRIS'
ev = []
total_tris = 0
latest_updateded_objects_in_depsgrapth = []
list_cache = {}
obj_lookup_cache = {}

def _get_modifier_times(ob_eval, mod): # we should not call it per modifier, but only once per object
    ms_times = ob_eval.modifiers[mod.name].execution_time
    return ms_times

def time_to_string(t, compact):
    if compact:
        if t == 0.0015:
            return f'0.0 ms'
        units = {3600.: 'h', 60.: 'min', 1.: 'sec', .001: 'ms'}
        for factor in units.keys():
            if t >= factor:
                value = f'{t/factor:.3g}'
                if len(value) > 4:  
                    value = f'{t/factor:.2g}'
                return f'{value} {units[factor]}'

        if t >= 1e-4:
            return f'{t/factor:.2g} {units[factor]}'
        else:
            return f'<0.1 ms'
    else:
        if t == 0.0015:
            return f'0.0s'
        if t < 60:
            if t < 0.1:
                if t < 0.01:
                    return f'<0.0s'
                else:
                    return str(round(t, 2)) + "s"
    
            elif t < 10:
                return str(round(t, 1)) + "s"
            else:
                return str(round(t, 1)) + "s"
        elif t < 3600:
            return str(round(t/60, 0)) + "min"
        else:
            return str(round(t/3600, 0)) + "h"

def get_obj_lookup_cache(scene, depsgraph):
    global obj_lookup_cache
    obj_lookup_cache = {obj.name: obj for obj in bpy.data.objects}

def deselect_all(context):
    for obj in context.selected_objects:
        obj.select_set(False)

def get_all_child_collections(coll):
    yield coll
    for child in coll.children:
        yield from get_all_child_collections(child)

def sortList(item):
    if polycount_sorting == 'NAME':
        return item[0].casefold()
    elif polycount_sorting == 'TRIS':
        return item[1]
    elif polycount_sorting == 'VERTS':
        return item[2]
    elif polycount_sorting == 'EDGES':
        return item[3]
    elif polycount_sorting == 'FACES':
        return item[4]
    elif polycount_sorting == 'MS':
        return item[5]
    else:
        return item[1]

def get_poly_count(context, force_update_all=False):
    global total_tris, latest_updateded_objects_in_depsgrapth, obj_lookup_cache, list_cache
    
    obj_lookup_cache = {obj.name: obj for obj in bpy.data.objects}
    
    c = context
    props = c.scene.keyops.polycount_props
    filter_list_show = props.filter_list_show
    show_ms = 'MS' in filter_list_show

    if props.filter_by == 'ALL':
        if props.show_only_enabled_collections:
            filter_type = c.view_layer.objects
        else:
            filter_type = c.scene.objects

    elif props.filter_by == 'VISIBLE':
        filter_type = c.visible_objects

    elif props.filter_by == 'COLLECTION':
        if props.my_collection is None:
            collection = c.collection
            filter_type = c.collection.objects
        else:
            collection = bpy.data.collections[props.my_collection.name]

        if props.child_collection:
            collections = set()
            for coll in get_all_child_collections(collection):
                collections.add(coll)
                
            filter_type = set()
            for col in collections:
                for obj in col.objects:
                    filter_type.add(obj)
        else:
            filter_type = collection.objects

    if props.polycount_use_selection_only:
        filter_type = c.selected_objects

    # import time
    # start_time = time.time()

    depsgraph = context.evaluated_depsgraph_get()
    show_collection_instances = props.show_collection_instances
    # replace mesh cache with just global polycount cache
    total_tris = 0

    filter_type = [obj for obj in filter_type if obj.type in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'META'}]
    
    for obj in filter_type:
        tris = 0
        verts = 0
        edges = 0
        faces = 0
        if obj.name in latest_updateded_objects_in_depsgrapth or obj not in list_cache:
            ms = 0
            if obj.type in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'META'}:
                eval_obj = obj.evaluated_get(depsgraph)
                mesh = eval_obj.to_mesh()
                if mesh is not None:
                    tris = len(mesh.loop_triangles)
                    verts = len(mesh.vertices)
                    edges = len(mesh.edges)
                    faces = len(mesh.polygons)

                    if show_ms:
                        for mod in obj.modifiers:
                            ms += _get_modifier_times(eval_obj, mod)
                        if not ms >= 1e-4:
                            if obj in list_cache:
                                tris2, verts2, edges2, faces2, ms = list_cache[obj]
                                
                        list_cache[obj] = (tris, verts, edges, faces, ms)
                        eval_obj.to_mesh_clear()
        else:
            tris, verts, edges, faces, ms = list_cache[obj]

        total_tris += tris
        polycount.append((obj.name, tris, verts, edges, faces, ms))  # Store directly in polycount list, we should not receate it each time, instead the list_cache should be used everwhere!
    # print("Time taken to get polycount: {:.4f} ms".format((time.time() - start_time) * 1000))

    latest_updateded_objects_in_depsgrapth = []

    if show_collection_instances:
        for obj in c.scene.objects:
            if obj.instance_type == 'COLLECTION' and obj.instance_collection:
                collection_instance_name = obj.name
                collection_tris, collection_verts, collection_edges, collection_faces = 0, 0, 0, 0

                for ob_col in obj.instance_collection.objects:
                    if ob_col.type in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'META'}:
                        eval_obj = ob_col.evaluated_get(depsgraph)
                        if ob_col.name not in list_cache:
                            m = eval_obj.to_mesh()
                            if m is not None:
                                list_cache[ob_col.name] = (len(m.loop_triangles), len(m.vertices), len(m.edges), len(m.polygons))
                                eval_obj.to_mesh_clear()
                        if ob_col.name in list_cache:
                            tris, verts, edges, faces = list_cache[ob_col.name]
                            collection_tris += tris
                            collection_verts += verts
                            collection_edges += edges
                            collection_faces += faces

                polycount.append((collection_instance_name, collection_tris, collection_verts, collection_edges, collection_faces))

    if polycount_sorting == 'NAME':
        name_ascending = not polycount_sorting_ascending
        polycount.sort(key=sortList, reverse=name_ascending)
    else:
        polycount.sort(key=sortList, reverse=polycount_sorting_ascending)

@persistent
def get_latest_updated_objects_in_depsgraph_poly_count_list(scene, depsgraph):
    global latest_updateded_objects_in_depsgrapth, list_cache
    scene_tab_is_open = False
    
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.spaces[0].type == 'PROPERTIES' and area.spaces[0].context == 'SCENE':
                latest_updateded_objects_in_depsgrapth = [update.id.name for update in depsgraph.updates if isinstance(update.id, bpy.types.Object)]
                scene_tab_is_open = True
                break
            
    if 'POLYCOUNT_LIST' in bpy.context.window_manager.toolkit_panel_mode:
        latest_updateded_objects_in_depsgrapth = [update.id.name for update in depsgraph.updates if isinstance(update.id, bpy.types.Object)]
        scene_tab_is_open = True

    if not scene_tab_is_open:
        # reset list_cache, since it will need to be recomputed once the scene tab is opened again
        if list_cache:
            list_cache.clear()

class PolyCountList(bpy.types.Operator):
    bl_idname = "keyops.poly_count_list"
    bl_label = "Poly Count List"
    bl_description = "Refresh the polycount list, only needed if auto update is off"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global polycount, list_cache
        list_cache.clear()
        polycount.clear()
        get_poly_count(context)
        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(PolyCountList)

    bpy.utils.register_class(KEYOPS_PT_poly_count_list_scene_panel)
    bpy.utils.register_class(POLYCOUNT_OT_refresh)
    bpy.utils.register_class(POLYCOUNTILST_PT_Settings)
    bpy.utils.register_class(POLYCOUNT_OT_walk)
    register_polycount_keymaps()


def unregister():
    bpy.utils.unregister_class(PolyCountList)

    bpy.utils.unregister_class(KEYOPS_PT_poly_count_list_scene_panel)
    bpy.utils.unregister_class(POLYCOUNT_OT_refresh)
    bpy.utils.unregister_class(POLYCOUNTILST_PT_Settings)
    clear_registered_keymaps(registered_polycount_keymaps)
    bpy.utils.unregister_class(POLYCOUNT_OT_walk)


def set_enabled(on):
    """The list keeps up with edits through a depsgraph handler, only while the feature is on."""
    handlers = bpy.app.handlers.depsgraph_update_post
    handler = get_latest_updated_objects_in_depsgraph_poly_count_list
    if on and handler not in handlers:
        handlers.append(handler)
    elif not on and handler in handlers:
        handlers.remove(handler)

ui_updates = 0
last_draw_time = 0
ms = ""

def draw_polycount_list_ui(self, context, properteries_panel=False):
    draw_time = time.time()
    name_offset_row = 0.725

    layout = self.layout
    global polycount_sorting_ascending, polycount_sorting, polycount, total_tris, ui_updates, last_draw_time, obj_lookup_cache, polycount, ms

    props = context.scene.keyops.polycount_props
    filter_list_show = props.filter_list_show

    show_tris = 'TRIS' in filter_list_show
    show_verts = 'VERT' in filter_list_show
    show_edges = 'EDGE' in filter_list_show
    show_faces = 'FACE' in filter_list_show
    show_ms = 'MS' in filter_list_show

    ui_updates += 1
    
    if props.auto_update_polycount:
        if ui_updates >= props.update_rate:
            polycount.clear()
            get_poly_count(context)
            ui_updates = 0

    if not properteries_panel:
        row = layout.row(align=True)
        text = ""
        if not props.show_total_tris:
            text = "Polycount List"
        row.label(text=text, icon_value=get_icon("polycount"))
        if props.show_total_tris:
            if props.round_numbers:
                row.label(text="Triangles: {}".format(trim_numbers(total_tris)))
            else:
                row.label(text="Triangles: " + "{:,}".format(total_tris))
            
            # objects = f"Objects {len(context.selected_objects)}/ {len(polycount)}"
            # row.label(text=objects)
            
            # sub.enabled = False
        if props.show_draw_time:  
            sub = row.row(align=True)
            sub.alignment = 'LEFT'
            if last_draw_time * 1000 > 30:
                sub.alert = True
            ms = "{:.1f} ms".format(last_draw_time * 1000)
            if not properteries_panel:
                sub.label(text=ms)
        

    if len(polycount) > 2500 and props.auto_update_polycount:
        row = layout.row(align=True)
    #     row.label(text="Warning: > 500 objects, auto update might be slow", icon="ERROR")
    #     # update_rate = props.update_rate
    #     row.scale_x = 0.4
    #     row.prop(props, "update_rate", text="Update Rate")

    # if redraw time is over 0.05s, show that update rate can be changed
        row.label(text="Auto Update might be slow", icon="INFO")
        # update_rate = props.update_rate
        row.scale_x = 0.45
        row.prop(props, "update_rate", text="Update Rate")

    row = layout.row(align=True)
    row.prop(props, "auto_update_polycount", text="Auto", icon="FILE_REFRESH", toggle=False)
    # row.popover(panel="POLYCOUNT_PT_AutoUpdate_Settings", icon="PREFERENCES", text="")
    row.operator("keyops.poly_count_list", text="Refresh", icon="FILE_REFRESH")
    row.prop(props, "polycount_use_selection_only", text="Selected", icon="RESTRICT_SELECT_OFF", toggle=False)
    row.popover(panel="POLYCOUNTILST_PT_Settings", icon="FILTER", text="")

    col_flow = layout.column_flow(columns=0, align=True)
    row = col_flow.row(align=True)

    if polycount_sorting == 'NAME':
        if polycount_sorting_ascending:
            row.operator("keyops.polycount_user_interaction", text="Object Name", icon="TRIA_DOWN").poly_sort = 'NAME'
        else:
            row.operator("keyops.polycount_user_interaction", text="Object Name", icon="TRIA_UP").poly_sort = 'NAME'
    else:
        row.operator("keyops.polycount_user_interaction", text="Object Name").poly_sort = 'NAME'

    row = row.row(align=True)
    row.scale_x = name_offset_row

    if show_tris:
        if polycount_sorting == 'TRIS':
            if polycount_sorting_ascending:
                row.operator("keyops.polycount_user_interaction", text="Tris", icon="TRIA_DOWN").poly_sort = 'TRIS'
            else:
                row.operator("keyops.polycount_user_interaction", text="Tris", icon="TRIA_UP").poly_sort = 'TRIS'
        else:
            row.operator("keyops.polycount_user_interaction", text="Tris").poly_sort = 'TRIS'

    if show_verts:
        if polycount_sorting == 'VERTS':
            if polycount_sorting_ascending:
                row.operator("keyops.polycount_user_interaction", text="Verts", icon="TRIA_DOWN").poly_sort = 'VERTS'
            else:
                row.operator("keyops.polycount_user_interaction", text="Verts", icon="TRIA_UP").poly_sort = 'VERTS'
        else:
            row.operator("keyops.polycount_user_interaction", text="Verts").poly_sort = 'VERTS'

    if show_edges:
        if polycount_sorting == 'EDGES':
            if polycount_sorting_ascending:
                row.operator("keyops.polycount_user_interaction", text="Edges", icon="TRIA_DOWN").poly_sort = 'EDGES'
            else:
                row.operator("keyops.polycount_user_interaction", text="Edges", icon="TRIA_UP").poly_sort = 'EDGES'
        else:
            row.operator("keyops.polycount_user_interaction", text="Edges").poly_sort = 'EDGES'

    if show_faces:
        if polycount_sorting == 'FACE':
            if polycount_sorting_ascending:
                row.operator("keyops.polycount_user_interaction", text="Face", icon="TRIA_DOWN").poly_sort = 'FACE'
            else:
                row.operator("keyops.polycount_user_interaction", text="Face", icon="TRIA_UP").poly_sort = 'FACE'
        else:
            row.operator("keyops.polycount_user_interaction", text="Face").poly_sort = 'FACE'
    
    if show_ms:
        if polycount_sorting == 'MS':
            if polycount_sorting_ascending:
                row.operator("keyops.polycount_user_interaction", text="Time", icon="TRIA_DOWN").poly_sort = 'MS'
            else:
                row.operator("keyops.polycount_user_interaction", text="Time", icon="TRIA_UP").poly_sort = 'MS'
        else:
            row.operator("keyops.polycount_user_interaction", text="Time").poly_sort = 'MS'

    # import time
    # start = time.time()
    box = col_flow.box()
    col_flow = box.column_flow(columns=0, align=True)
    if len(polycount) > 0:
        round_numbers = props.round_numbers
        show_collection_instances = props.show_collection_instances
        show_obj_type = props.show_obj_type
        max_list_length = props.max_list_length
        selecteion = context.selected_objects

        mesh_icon = get_icon("mesh")   
        curve_icon = get_icon("curve")
        
        found_active = False

        for i, obj in enumerate(polycount):
            if i >= max_list_length:
                break
            
            # data
            obj_name = str(obj[0])
            object = obj_lookup_cache.get(obj_name)
            # if object == None or str(object) == "<bpy_struct, Object invalid>": # object was deleted most likely
            if object == None: # object was deleted most likely
                continue

            row = col_flow.row(align=True)
            selected = object in selecteion

            if show_obj_type:
                object_type = object.type
                
                if object_type in {'MESH', 'CURVE'}:
                    if object_type == 'MESH':
                        icon_value = mesh_icon
                    elif object_type == 'CURVE':
                        icon_value = curve_icon

                    display_name = obj_name
                    if not found_active:
                        if object == context.active_object:
                            found_active = True
                            display_name = "*" + obj_name  
                            
                    row.operator("keyops.polycount_user_interaction", text=str(display_name), icon_value=icon_value, depress=selected, emboss=selected).make_active = obj_name
                else:
                    # Check if the object is an instanced collection
                    if show_collection_instances and object.instance_type == 'COLLECTION':
                        icon = 'OUTLINER_OB_GROUP_INSTANCE'
                    else:
                        icon = 'OUTLINER_OB_' + object_type if object_type in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'META', 'ARMATURE', 'CAMERA', 'LIGHT', 'LATTICE', 'EMPTY', 'SPEAKER', 'LIGHT_PROBE'} else 'OBJECT_DATAMODE'

                    row.operator("keyops.polycount_user_interaction", text=str(obj_name), icon=icon, depress=selected, emboss=selected).make_active = obj_name
            else:
                row.operator("keyops.polycount_user_interaction", text=str(obj_name), depress=selected, emboss=selected).make_active = obj_name

            row = row.row(align=True)
            row.scale_x = name_offset_row
        
            if show_tris: 
                text = trim_numbers(obj[1]) if round_numbers else "{:,.0f}".format(obj[1])
                row.operator("keyops.polycount_user_interaction", text=str(text), depress=selected, emboss=selected).make_active = obj_name
            if show_verts:
                text = trim_numbers(obj[2]) if round_numbers else "{:,.0f}".format(obj[2])
                row.operator("keyops.polycount_user_interaction", text=str(text), depress=selected, emboss=selected).make_active = obj_name
            if show_edges:
                text = trim_numbers(obj[3]) if round_numbers else "{:,.0f}".format(obj[3])
                row.operator("keyops.polycount_user_interaction", text=str(text), depress=selected, emboss=selected).make_active = obj_name
            if show_faces:
                text = trim_numbers(obj[4]) if round_numbers else "{:,.0f}".format(obj[4])
                row.operator("keyops.polycount_user_interaction", text=str(text), depress=selected, emboss=selected).make_active = obj_name
            if show_ms:
                text = time_to_string(obj[5], compact=properteries_panel)
                row.operator("keyops.polycount_user_interaction", text=str(text), depress=selected, emboss=selected).make_active = obj_name
            
            #add reached max list length warning
            if i == max_list_length - 1:
                row = col_flow.row(align=True)
                row.alignment = 'LEFT'
                row.scale_x = 2
                row.label(text="Max List Length Reached", icon="QUESTION")
                row.prop(props, "max_list_length", text="Current:")
        # print(time.time() - start)

    last_draw_time = time.time() - draw_time
class KEYOPS_PT_poly_count_list_scene_panel(bpy.types.Panel):
    bl_label = "Polycount List"
    bl_idname = "KEYOPS_PT_poly_count_list_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    @classmethod
    def poll(cls, context):
        return feature_on("polycount_list")

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon_value=get_icon("polycount"))
        return 
    
    def draw_header_preset(self, context):
        global ms 
        layout = self.layout
        row = layout.row()
        props = context.scene.keyops.polycount_props

        if props.show_total_tris:
            row.scale_x = 1.5
            if props.round_numbers:
                row.label(text="Triangles: {}".format(trim_numbers(total_tris)))
            else:
                row.label(text="Triangles: " + "{:,}".format(total_tris))

        if props.show_draw_time:  
            sub = row.row()
            sub.label(text=ms)
        return 

    def draw(self, context):
        draw_polycount_list_ui(self, context, properteries_panel=True)
class POLYCOUNTILST_PT_Settings(bpy.types.Panel):
    bl_label = "Polycount Settings"
    bl_idname = "POLYCOUNTILST_PT_Settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}
    # bl_ui_units_x = 11

    def draw(self, context):
        layout = self.layout
        props = context.scene.keyops.polycount_props

        row = layout.row()
        row.label(text="Performance:")
        
        row = layout.row()
        row.label(text="Length:")
        row.prop(props, "max_list_length", text="")

        if props.auto_update_polycount:
            row.label(text="Redraw")
            row.prop(props, "update_rate", text="")

        row = layout.row()
        row = layout.row()

        row.label(text="Show:")
        row = layout.row()
        row.alignment = 'LEFT'
        row.prop(props, "show_total_tris", text="Total")
        row.prop(props, "round_numbers", text="Round Numbers")
        row = layout.row()
        row.alignment = 'LEFT'
        row.prop(props, "show_obj_type", text="Object Type")
        row.prop(props, "show_draw_time", text="Draw Time")
        row = layout.row()
        row.alignment = 'LEFT'
        row.prop(props, "keyboard_navigation", text="Keyboard Navigation (Up/Down, W/S)")

        row = layout.row(align=True)
        row = layout.row(align=True)
        # row.label(text="Show")
        # row.alignment = "EXPAND"
        row.scale_x = 2.1
        row.prop(props, "filter_list_show")

        row = layout.row()
        row.label(text="Filter Objects by:")
        row = layout.row()
        row.prop(props, "filter_by", text="Object Visible", expand=True)

        if props.filter_by == 'ALL':
            row = layout.row()
            row.prop(props, "show_only_enabled_collections", text="Show Only Enabled Collections")

        if props.filter_by == 'VISIBLE':
            row = layout.row()
            row.label(text="Only Visible Objects are Shown")
            row = layout.row()
            row.label(text="N-Panel will show local view visibility")

        if props.filter_by == 'COLLECTION':
            row = layout.row()
            row.prop(props, "my_collection", text="Custom")
            row = layout.row(align=True)
            row.alignment = "LEFT"
            row.label(text="Show:")
            row.prop(props, "show_collection_instances", text="Instances")
            row.prop(props, "child_collection", text="Recursively")

class POLYCOUNT_PT_AutoUpdate_Settings(bpy.types.Panel):
    bl_label = "Auto Update Settings"
    bl_idname = "POLYCOUNT_PT_AutoUpdate_Settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.keyops.polycount_props

        row = layout.row()
        row.label(text="Auto Update Settings:")
        row = layout.row()
        row.prop(props, "auto_update_polycount", text="Auto Update")

class POLYCOUNT_OT_refresh(bpy.types.Operator):
    bl_idname = "keyops.polycount_user_interaction"
    bl_label = "Show polycount in Scene properties panel"
    bl_description = "Header: sort the list.\nRow: Click to select, Ctrl to toggle, Shift to select the range from the active object, Shift on the active object to select its children"
    make_active: StringProperty(default="") # type: ignore
    poly_sort: EnumProperty(
        items=[
            ('NAME', "Name", ""),
            ('VERTS', "Verts", ""),
            ('EDGES', "Edges", ""),
            ('FACE', "Faces", ""),
            ('TRIS', "Tris", ""),
            ('MS', "ms", "")
        ], default='TRIS'
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        return len(context.view_layer.objects) > 0
    def invoke(self, context, event):
        global ev
        ev = []
        if event.shift:
            ev.append("Shift")
        if event.ctrl:
            ev.append("Ctrl")
        ev.append("Click")
        return self.execute(context)

    def execute(self, context):
        global polycount_sorting_ascending
        global polycount_sorting

        obj = bpy.data.objects.get(str(self.make_active))
        if obj is not None:
            if context.mode != 'OBJECT':
                self.report({'WARNING'}, "Selecting from the list only works in Object Mode")
            elif obj.name not in context.view_layer.objects:
                self.report({'WARNING'}, "Object not in an enabled collection or view layer")
            else:
                click_select(context, obj, shift="Shift" in ev, ctrl="Ctrl" in ev)
        else:
            if self.poly_sort == polycount_sorting:
                polycount_sorting_ascending = not polycount_sorting_ascending
            else:
                polycount_sorting = self.poly_sort
        self.make_active = ""
        ev.clear()

        if polycount_sorting == 'NAME':
            name_ascending = not polycount_sorting_ascending
            polycount.sort(key=sortList, reverse=name_ascending)
        else:
            polycount.sort(key=sortList, reverse=polycount_sorting_ascending)

        return {'FINISHED'}

def get_list_objects(context):
    """Objects in the order the list shows them (only those that can be selected)."""
    props = context.scene.keyops.polycount_props
    view_layer_objects = context.view_layer.objects
    objects = []
    for item in polycount[:props.max_list_length]:
        obj = view_layer_objects.get(item[0])
        if obj is not None and obj not in objects:
            objects.append(obj)
    return objects

def click_select(context, obj, shift=False, ctrl=False):
    """Outliner-style click: plain = select only, Ctrl = toggle,
    Shift = range from the active object, Shift on the active object = its children."""
    view_layer = context.view_layer
    active = view_layer.objects.active

    if shift:
        if active is not None and obj == active:
            # Select the active object's whole hierarchy
            if not ctrl:
                deselect_all(context)
            active.select_set(True)
            for child in active.children_recursive:
                if child.name in view_layer.objects:
                    child.select_set(True)
            return

        objects = get_list_objects(context)
        if active in objects and obj in objects:
            a, b = objects.index(active), objects.index(obj)
            if not ctrl:
                deselect_all(context)
            for o in objects[min(a, b):max(a, b) + 1]:
                o.select_set(True)
            return
        # No anchor in the list: fall back to extending the selection
        obj.select_set(True)
        view_layer.objects.active = obj
        return

    if ctrl:
        if obj.select_get():
            obj.select_set(False)
        else:
            obj.select_set(True)
            view_layer.objects.active = obj
        return

    deselect_all(context)
    obj.select_set(True)
    view_layer.objects.active = obj

class POLYCOUNT_OT_walk(bpy.types.Operator):
    bl_idname = "keyops.polycount_walk"
    bl_label = "Polycount List Walk"
    bl_description = "Move the active object up or down in the Polycount List"
    bl_options = {'INTERNAL', 'UNDO'}

    direction: EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")], default='DOWN') # type: ignore
    extend: BoolProperty(name="Extend", default=False, description="Extend the selection instead of replacing it") # type: ignore

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if context.mode != 'OBJECT' or scene is None or not hasattr(scene, "polycount_props"):
            return False
        if not scene.keyops.polycount_props.keyboard_navigation or not polycount:
            return False
        space, region = context.space_data, context.region
        if space is None or region is None:
            return False
        if space.type == 'PROPERTIES':
            return space.context == 'SCENE'
        if space.type == 'VIEW_3D':
            if region.type != 'UI' or 'POLYCOUNT_LIST' not in getattr(context.window_manager, "toolkit_panel_mode", set()):
                return False
            category = getattr(region, "active_panel_category", None)
            return category in {None, 'Toolkit'}
        return False

    def execute(self, context):
        objects = get_list_objects(context)
        if not objects:
            return {'CANCELLED'}

        view_layer = context.view_layer
        active = view_layer.objects.active
        step = -1 if self.direction == 'UP' else 1

        if active not in objects:
            target = objects[0] if step == 1 else objects[-1]
        else:
            index = objects.index(active) + step
            if index < 0 or index >= len(objects):
                return {'CANCELLED'}
            target = objects[index]

        if self.extend and active in objects:
            # Like the outliner: walking back onto a selected item shrinks the selection
            if target.select_get():
                active.select_set(False)
            target.select_set(True)
        else:
            deselect_all(context)
            target.select_set(True)
        view_layer.objects.active = target

        if context.screen is not None:
            for area in context.screen.areas:
                if area.type in {'PROPERTIES', 'VIEW_3D'}:
                    area.tag_redraw()
        return {'FINISHED'}

registered_polycount_keymaps = []

def register_polycount_keymaps():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return
    for km_name, space_type in (('3D View Generic', 'VIEW_3D'), ('Property Editor', 'PROPERTIES')):
        km = kc.keymaps.new(name=km_name, space_type=space_type)
        for key, direction in (('UP_ARROW', 'UP'), ('W', 'UP'), ('DOWN_ARROW', 'DOWN'), ('S', 'DOWN')):
            for shift in (False, True):
                kmi = km.keymap_items.new(POLYCOUNT_OT_walk.bl_idname, key, 'PRESS', shift=shift, repeat=True)
                kmi.properties.direction = direction
                kmi.properties.extend = shift
                registered_polycount_keymaps.append((km, kmi))

def trim_numbers(number):
    if number < 1000:
        return str(number)
    elif number < 1000000:
        return "{:.1f}k".format(number / 1000)
    else:
        return "{:.1f}m".format(number / 1000000)

