# Based on the excellent Polycount Addon by Vinc3r
# https://github.com/Vinc3r/Polycount
# I used this addon a lot and really liked it, but I feelt it could be improved in terms of performance, ui and usability when working in big production scenes.
# Its now about 1000-5000x times faster than the original addon, it has a realtime mode by defualt and more streamlined ui along with some new features.

# TODO: Make faster by having global var listcache isntead of yield in get_poly_count

import bpy, time
from bpy.types import PropertyGroup
from bpy.props import (EnumProperty, BoolProperty, StringProperty, PointerProperty, IntProperty)
from ..utils.pref_utils import get_keyops_prefs, get_icon

polycount = []
polycount_sorting_ascending = True
polycount_sorting = 'TRIS'
ev = []
total_tris = 0
latest_updated_objects_in_depsgrapth = []
list_cache = {}

class PolyCountProperties(PropertyGroup):
    polycount_use_selection_only: BoolProperty(  # type: ignore
        name="Use selected only",
        description="Compute stats only for selected objects",
        default=False
    )
    auto_update_polycount: BoolProperty(  # type: ignore
        name="Auto Update",
        description="Auto update the list, might be slow in big scenes",
        default=True
    )
    filter_list_show: EnumProperty(  # type: ignore
        name="List Show",
        description="Show",
        items=[
            ('TRIS', "Tris", "Tris", 'MESH_DATA', 1),
            ('VERT', "Vert", "Vert", 'VERTEXSEL', 2),
            ('EDGE', "Edge", "Edge", 'EDGESEL', 4),
            ('FACE', "Face", "Face", 'FACESEL', 8)
        ],
        options={'ENUM_FLAG'},
        default={'TRIS', 'VERT', 'FACE'}
    )
    show_total_tris: BoolProperty(  # type: ignore
        name="Show Total Tris",
        description="Show Total Tris in the list",
        default=True
    )
    filter_by: EnumProperty(  # type: ignore
        name="Filter",
        description="Filter",
        items=[
            ('ALL', "All", "", 'NONE', 0),
            ('VISIBLE', "Visible", "", 'HIDE_OFF', 1),
            ('COLLECTION', "Collection", "", '', 2)
        ],
        default='ALL'
    )
    my_collection: PointerProperty(name="Collection",type=bpy.types.Collection)  # type: ignore

    round_numbers: BoolProperty(  # type: ignore
        name="Round Numbers",
        description="Round the numbers, slower, but more readable",
        default=True
    )
    show_only_enabled_collections: BoolProperty(  # type: ignore
        name="Show Only Enabled Collections",
        description="Show only enabled collections",
        default=True
    )
    show_collection_instances: BoolProperty(  # type: ignore
        name="Show Collection Instances",
        description="Show collection instances",
        default=False
    )
    show_obj_type: BoolProperty(  # type: ignore
        name="Show Object Type",
        description="Warning: Slow in big scenes, shows the icon of the object type",
        default=True
    )
    max_list_length: IntProperty(  # type: ignore
        name="Max List Length",
        description="Maximum number of objects to show in the list",
        default=150,
        min=1
    )
    update_rate: IntProperty(  # type: ignore
        name="Update Rate",
        description="Update rate",
        default=1,
        min=1
    )
    show_draw_time: BoolProperty(  # type: ignore
        name="Show Draw Time",
        description="Show the time it took to draw the list",
        default=True
    )

def deselect_all(context):
    for obj in context.selected_objects:
            obj.select_set(False)
        
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
    else:
        return item[1]

def get_poly_count(context, force_update_all=False):
    global total_tris, latest_updated_objects_in_depsgrapth
    selection = None
    c = context
    props = c.scene.polycount_props

    if props.filter_by == 'ALL':
        if props.show_only_enabled_collections:
            filter_type = c.view_layer.objects
        else:
            filter_type = c.scene.objects

    elif props.filter_by == 'VISIBLE':
        filter_type = c.visible_objects

    elif props.filter_by == 'COLLECTION':
        if props.my_collection is None:
            filter_type = c.collection.objects
        else:
            filter_type = bpy.data.collections[props.my_collection.name].objects

    if props.polycount_use_selection_only:
        selection = c.selected_objects
        filter_type = [obj for obj in filter_type if obj in selection]

    selection = [obj for obj in filter_type if obj.type in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'META'}]

    depsgraph = context.evaluated_depsgraph_get()
    show_collection_instances = props.show_collection_instances
    # replace mesh cache with just global polycount cache
    # import time
    # start_time = time.time()
    for obj in selection:
        if obj.name in latest_updated_objects_in_depsgrapth or obj not in list_cache:
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
            if mesh is not None:
                tris = len(mesh.loop_triangles)
                verts = len(mesh.vertices)
                edges = len(mesh.edges)
                faces = len(mesh.polygons)
                list_cache[obj] = (tris, verts, edges, faces)
                eval_obj.to_mesh_clear()
        else:
            tris, verts, edges, faces = list_cache[obj]

        total_tris += tris
        polycount.append((obj.name, tris, verts, edges, faces))  # Store directly in polycount list

    latest_updated_objects_in_depsgrapth = []
    # print("Time taken to get polycount: ", time.time() - start_time)

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
    # print(time.time() - start)  

    if polycount_sorting == 'NAME':
        name_ascending = not polycount_sorting_ascending
        polycount.sort(key=sortList, reverse=name_ascending)
    else:
        polycount.sort(key=sortList, reverse=polycount_sorting_ascending)

    total_tris = 0
    for obj in polycount:
        total_tris += obj[1]

    return {'FINISHED'}

def get_latest_updated_objects_in_depsgraph_poly_count_list(scene, depsgraph):
    global latest_updated_objects_in_depsgrapth, list_cache
    scene_tab_is_open = False
    
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.spaces[0].type == 'PROPERTIES' and area.spaces[0].context == 'SCENE':
                latest_updated_objects_in_depsgrapth = [update.id.name for update in depsgraph.updates if isinstance(update.id, bpy.types.Object)]
                scene_tab_is_open = True
                break
    if scene.toolkit_panel_mode == 'POLYCOUNT_LIST':
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
        bpy.utils.register_class(PolyCountProperties)
        bpy.types.Scene.polycount_props = PointerProperty(type=PolyCountProperties)

        bpy.utils.register_class(KEYOPS_PT_poly_count_list_scene_panel)
        bpy.utils.register_class(POLYCOUNT_OT_refresh)
        bpy.utils.register_class(POLYCOUNTILST_PT_Settings)
        # bpy.utils.register_class(POLYCOUNT_PT_AutoUpdate_Settings)

        bpy.app.handlers.depsgraph_update_post.append(get_latest_updated_objects_in_depsgraph_poly_count_list)

    def unregister():
        bpy.utils.unregister_class(PolyCountProperties)
        del bpy.types.Scene.polycount_props

        bpy.utils.unregister_class(KEYOPS_PT_poly_count_list_scene_panel)
        bpy.utils.unregister_class(POLYCOUNT_OT_refresh)
        bpy.utils.unregister_class(POLYCOUNTILST_PT_Settings)
        # bpy.utils.unregister_class(POLYCOUNT_PT_AutoUpdate_Settings)

        if get_latest_updated_objects_in_depsgraph_poly_count_list in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(get_latest_updated_objects_in_depsgraph_poly_count_list)

ui_updates = 0
last_draw_time = 0

def draw_polycount_list_ui(self, context):
        draw_time = time.time()
        name_offset_row = 0.725

        layout = self.layout
        global polycount_sorting_ascending, polycount_sorting, polycount, total_tris, ui_updates, last_draw_time

        props = context.scene.polycount_props
        filter_list_show = props.filter_list_show

        show_tris = 'TRIS' in filter_list_show
        show_verts = 'VERT' in filter_list_show
        show_edges = 'EDGE' in filter_list_show
        show_faces = 'FACE' in filter_list_show

        ui_updates += 1
        
        if props.auto_update_polycount:
            if ui_updates >= props.update_rate:
                polycount.clear()
                get_poly_count(context)
                ui_updates = 0
        
        if props.show_total_tris:
            row = layout.row(align=True)
            if props.round_numbers:
                row.label(text="Total Tris: {}".format(trim_numbers(total_tris)))
            else:
                row.label(text="Total Tris: " + "{:,}".format(total_tris))
            sub = row.row(align=True)
            sub.alignment = 'LEFT'
            # sub.enabled = False
            if props.show_draw_time:  
                if last_draw_time * 1000 > 30:
                    sub.alert = True
                sub.label(text="{:.1f} ms".format(last_draw_time * 1000))

        row = layout.row(align=True)
        if len(polycount) > 2500 and props.auto_update_polycount:
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
        row.prop(props, "polycount_use_selection_only", text="Only selected", icon="RESTRICT_SELECT_OFF", toggle=False)
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
                object = bpy.data.objects.get(obj_name)
                if object is None: # object was deleted most likely
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

    def draw(self, context):
        draw_polycount_list_ui(self, context)
class POLYCOUNTILST_PT_Settings(bpy.types.Panel):
    bl_label = "Polycount Settings"
    bl_idname = "POLYCOUNTILST_PT_Settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.polycount_props

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
        row.prop(props, "show_total_tris", text="Total Tris")
        row.prop(props, "round_numbers", text="Round Numbers")
        row = layout.row()
        row.alignment = 'LEFT'
        row.prop(props, "show_obj_type", text="Object Type")
        row.prop(props, "show_draw_time", text="Draw Time")
        
        row = layout.row(align=True)
        row = layout.row(align=True)
        row.prop(props, "filter_list_show", text="Show")


        row = layout.row()
        row.label(text="Filter Objects by:")
        row = layout.row()
        row.prop(props, "filter_by", text="Object Visible", expand=True)

        if props.filter_by == 'ALL':
            row = layout.row()
            row.prop(props, "show_only_enabled_collections", text="Show Only Enabled Collections")

        if props.filter_by == 'VISIBLE':
            row = layout.row()
            row.label(text="Only Visible Objects are Now Shown")

        if props.filter_by == 'COLLECTION':
            row = layout.row()
            row.prop(props, "my_collection", text="Custom")
            row = layout.row()
            row.prop(props, "show_collection_instances", text="Include Collection Instances")

class POLYCOUNT_PT_AutoUpdate_Settings(bpy.types.Panel):
    bl_label = "Auto Update Settings"
    bl_idname = "POLYCOUNT_PT_AutoUpdate_Settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.polycount_props

        row = layout.row()
        row.label(text="Auto Update Settings:")
        row = layout.row()
        row.prop(props, "auto_update_polycount", text="Auto Update")

class POLYCOUNT_OT_refresh(bpy.types.Operator):
    bl_idname = "keyops.polycount_user_interaction"
    bl_label = "Show polycount in Scene properties panel"
    bl_description = "Object Name"
    make_active: StringProperty(default="") # type: ignore
    poly_sort: EnumProperty(
        items=[
            ('NAME', "Name", ""),
            ('VERTS', "Verts", ""),
            ('EDGES', "Edges", ""),
            ('FACE', "Faces", ""),
            ('TRIS', "Tris", "")
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

        def set_selected(ctrl=False):
            obj = bpy.data.objects.get(self.make_active)
            if not obj:
                return

            obj.select_set(not obj.select_get() if ctrl else True)
            context.view_layer.objects.active = obj if not ctrl else context.view_layer.objects.active

            # if context.scene.polycount_props.update_rate > 1: # update selection only if update rate is greater than 1
            #     for i, obj_data in enumerate(polycount):
            #         if obj_data[0] == self.make_active:
            #             polycount[i] = (*obj_data[:5], obj.select_get())
            #             break
            return

        if bpy.data.objects.get(str(self.make_active)) is not None:
            if context.mode == 'OBJECT':
                if ev == ["Shift", "Click"]:
                    set_selected()
                elif "Ctrl" in ev:
                    set_selected(ctrl=True)
                else:
                    deselect_all(context)
                    set_selected()
            else:
                self.report({'WARNING'}, "Object not in an enabled collection or view layer")
        else:
            if self.poly_sort == polycount_sorting:
                polycount_sorting_ascending = not polycount_sorting_ascending
            else:
                polycount_sorting = self.poly_sort
        self.make_active = ""

        if polycount_sorting == 'NAME':
            name_ascending = not polycount_sorting_ascending
            polycount.sort(key=sortList, reverse=name_ascending)
        else:
            polycount.sort(key=sortList, reverse=polycount_sorting_ascending)

        return {'FINISHED'}

def trim_numbers(number):
    if number < 1000:
        return str(number)
    elif number < 1000000:
        return "{:.1f}k".format(number / 1000)
    else:
        return "{:.1f}m".format(number / 1000000)

