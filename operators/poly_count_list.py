# Based on the excellent Polycount Addon by Vinc3r
# https://github.com/Vinc3r/Polycount
# I used this addon a lot and really liked it, but I feelt it could be improved in terms of performance, ui and usability when working in big production scenes.
""""
TODO:
auto refresh option - DONE
fix category can't be set as defaults - DONE
dont refresh when just selecting an object in name mode - DONE
total poly count - DONE
Does not work correclty in edit modes, skips counting object if in edit mode - DONE
Cant select objects from list in edit mode - DONE

Show both selected objects and active object in list -  
Option to show by Collection in List Category -
Option to Limit to a Collection or Collections -

"""

import bpy
from bpy.types import Scene
from bpy.props import (EnumProperty,BoolProperty,StringProperty)
# import time

polycount = []
polycount_sorting_ascending = True
polycount_sorting = 'TRIS'
ev = []
total_tris = 0

# Thanks Michelanders for this very helpful blog post:
#https://blog.michelanders.nl/2021/07/generate-list-of-blender-object-information.html
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
        # default
        return item[1]

def get_poly_count(context):
    selection = None
    global total_tris

    # bm = bmesh.new()
    # depsgraph = context.view_layer.depsgraph
    
    if context.scene.polycount_use_selection_only:
        selection = [obj for obj in context.selected_objects if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']
    else:
        selection = [obj for obj in context.scene.objects if obj.type == 'MESH' or obj.type == 'CURVE' or obj.type == 'FONT' or obj.type == 'SURFACE' or obj.type == 'META']

    for obj in selection:
        m = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()

        tris = len(m.loop_triangles)
        verts = len(m.vertices)
        edges = len(m.edges)
        faces = len(m.polygons)
        total_tris = total_tris + tris

        yield obj.name, tris, verts, edges, faces, 
        

    # for ob in selection:
    #     tris, faces, edges, verts = 0,0,0,0
    #     if ob.type == 'MESH':
    #         bm.from_object(ob, depsgraph, face_normals=False)
    #         tris = len(bm.calc_loop_triangles())

    #         verts = len(bm.verts)

    #         edges = len(bm.edges)

    #         faces = len(bm.faces)

    #         bm.clear()

    #         yield ob.name, tris, verts, edges, faces, 

    # bm.free()

    if polycount_sorting == 'NAME':
        name_ascending = not polycount_sorting_ascending
        polycount.sort(
            key=sortList, reverse=name_ascending)
    else:
        polycount.sort(
            key=sortList, reverse=polycount_sorting_ascending)
        
    total_tris = 0
    for obj in polycount:
        total_tris = total_tris + obj[1]

    return {'FINISHED'}


class PolyCountList(bpy.types.Operator):
    bl_idname = "keyops.poly_count_list"
    bl_label = "Poly Count List"
    bl_description = "Refresh the polycount list, only needed if auto update is off"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        #refresh_time = time.time()

        global polycount
        polycount.clear()
        for ob in get_poly_count(context):
            polycount.append(ob)
                
        #refresh_time = time.time() - refresh_time
        #print("Refresh time: {:.2f} seconds".format(refresh_time))
        return {'FINISHED'}
    
    def register():
        bpy.utils.register_class(KEYOPS_PT_poly_count_list_panel)
        bpy.utils.register_class(POLYCOUNT_OT_refresh)
        bpy.utils.register_class(POLYCOUNTILST_PT_Settings)

        Scene.polycount_use_selection_only = BoolProperty(name="Use selected only",description="Compute stats only for selected objects",default=False)
        Scene.auto_update_polycount = BoolProperty(name="Auto Update",description="Auto update the list, might be slow in big scenes",default=True)
        Scene.polycount_show_tris = BoolProperty(name="Show Tris",description="Show Tris in the list",default=True)
        Scene.polycount_show_verts = BoolProperty(name="Show Verts",description="Show Verts in the list",default=True)
        Scene.polycount_show_edges = BoolProperty(name="Show Edges",description="Show Edges in the list",default=True)
        Scene.polycount_show_faces = BoolProperty(name="Show Faces",description="Show Faces in the list",default=True)
        Scene.show_total_tris = BoolProperty(name="Show Total Tris",description="Show Total Tris in the list",default=True)
        Scene.show_selected_in_edit = BoolProperty(name="Show Selected in Edit",description="Show Selected in Edit mode",default=False)

    def unregister():
        bpy.utils.unregister_class(KEYOPS_PT_poly_count_list_panel)
        bpy.utils.unregister_class(POLYCOUNT_OT_refresh)
        bpy.utils.unregister_class(POLYCOUNTILST_PT_Settings)
        del Scene.polycount_use_selection_only
        del Scene.auto_update_polycount
        del Scene.polycount_show_tris
        del Scene.polycount_show_verts
        del Scene.polycount_show_edges
        del Scene.polycount_show_faces
        del Scene.show_total_tris
        del Scene.show_selected_in_edit
    
def trim_numbers(number):
    numberAsString = "{}".format(number)
    if number < 1000:
        return numberAsString
    else:
        numberAsString = "{:,.2f}k".format(round(number/1000, 2)).replace(",", " ")
    return numberAsString


class KEYOPS_PT_poly_count_list_panel(bpy.types.Panel):
    bl_label = "Polycount List"
    bl_idname = "KEYOPS_PT_poly_count_list_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        global polycount_sorting_ascending
        global polycount_sorting
        global polycount
        global total_tris 
        global polycount

        if context.scene.auto_update_polycount:
            polycount.clear()
            for ob in get_poly_count(context):
                polycount.append(ob)

        if context.scene.show_total_tris:
            row = layout.row(align=True)
            row.label(text="Total Tris: {}".format(trim_numbers(total_tris)))

        if context.scene.show_selected_in_edit and context.mode == 'EDIT_MESH':
            row = layout.row(align=True)
            total_selected_verts = 0
            total_verts = 0

            total_selected_edges = 0
            total_edges = 0

            total_selected_faces = 0
            total_faces = 0


            for ob in context.selected_objects:
                if ob.type == 'MESH':

                    verts = len(ob.data.vertices)
                    edges = len(ob.data.edges)
                    faces = len(ob.data.polygons)

                    total_selected_verts += ob.data.total_vert_sel 
                    total_verts += verts

                    total_selected_edges += ob.data.total_edge_sel
                    total_edges += edges

                    total_selected_faces += ob.data.total_face_sel
                    total_faces += faces

            row = layout.row(align=True)
            row.label(text="Verts: " + str(total_selected_verts) + "/" + str(total_verts))
            row.label(text="Edges: " + str(total_selected_edges) + "/" + str(total_edges))
            row.label(text="Faces: " + str(total_selected_faces) + "/" + str(total_faces))

        row = layout.row(align=True)
        row.prop(context.scene, "auto_update_polycount", text="Auto", icon="FILE_REFRESH", toggle=False)
        row.operator("keyops.poly_count_list", text="Refresh", icon="FILE_REFRESH")
        
        row.prop(context.scene, "polycount_use_selection_only", text="Only selected", icon="RESTRICT_SELECT_OFF", toggle=False)
        
        row.popover(panel="POLYCOUNTILST_PT_Settings", icon="FILTER", text="")
        
        col_flow = layout.column_flow(
            columns=0, align=True)
        row = col_flow.row(align=True)

        row = col_flow.row(align=True)

        if polycount_sorting == 'NAME':
            if polycount_sorting_ascending:
                row.operator("keyops.polycount_user_interaction",
                             text="Object", icon="TRIA_DOWN").poly_sort = 'NAME'
            else:
                row.operator("keyops.polycount_user_interaction",
                             text="Object", icon="TRIA_UP").poly_sort = 'NAME'
        else:
            row.operator("keyops.polycount_user_interaction",
                         text="Object").poly_sort = 'NAME'
            
        if context.scene.polycount_show_tris:
            if polycount_sorting == 'TRIS':
                if polycount_sorting_ascending:
                    row.operator("keyops.polycount_user_interaction",
                                    text="Tris", icon="TRIA_DOWN").poly_sort = 'TRIS'
                else:
                    row.operator("keyops.polycount_user_interaction",
                                    text="Tris", icon="TRIA_UP").poly_sort = 'TRIS'
            else:
                row.operator("keyops.polycount_user_interaction",
                                text="Tris").poly_sort = 'TRIS'
        if context.scene.polycount_show_verts:
            if polycount_sorting == 'VERTS':
                if polycount_sorting_ascending:
                    row.operator("keyops.polycount_user_interaction",
                                    text="Verts", icon="TRIA_DOWN").poly_sort = 'VERTS'
                else:
                    row.operator("keyops.polycount_user_interaction",
                                    text="Verts", icon="TRIA_UP").poly_sort = 'VERTS'
            else:
                row.operator("keyops.polycount_user_interaction",
                                text="Verts").poly_sort = 'VERTS'
        if context.scene.polycount_show_edges:
            if polycount_sorting == 'EDGES':
                if polycount_sorting_ascending:
                    row.operator("keyops.polycount_user_interaction",
                                    text="Edges", icon="TRIA_DOWN").poly_sort = 'EDGES'
                else:
                    row.operator("keyops.polycount_user_interaction",
                                    text="Edges", icon="TRIA_UP").poly_sort = 'EDGES'
            else:
                row.operator("keyops.polycount_user_interaction",
                                text="Edges").poly_sort = 'EDGES'
        if context.scene.polycount_show_faces:
            if polycount_sorting == 'FACE':
                if polycount_sorting_ascending:
                    row.operator("keyops.polycount_user_interaction",
                                    text="Face", icon="TRIA_DOWN").poly_sort = 'FACE'
                else:
                    row.operator("keyops.polycount_user_interaction",
                                    text="Face", icon="TRIA_UP").poly_sort = 'FACE'
            else:
                row.operator("keyops.polycount_user_interaction",
                                text="Face").poly_sort = 'FACE'

        # objects stats layout

        if len(polycount) > 0:
            for obj in polycount:
                row = col_flow.row(align=True)
                # show if active
                if context.view_layer.objects.active and context.view_layer.objects.active.name == str(obj[0]):
                    row.operator("keyops.polycount_user_interaction",
                                 text=str(obj[0]), depress=True).make_active = obj[0]
                else:
                    row.operator("keyops.polycount_user_interaction",
                                 text=str(obj[0]), depress=False).make_active = obj[0]
                if context.scene.polycount_show_tris:
                    tris_number = trim_numbers(obj[1])
                    row.label(text=tris_number)
                if context.scene.polycount_show_verts:
                    verts_number = trim_numbers(obj[2])
                    row.label(text=verts_number)
                if context.scene.polycount_show_edges:
                    edge_number = trim_numbers(obj[3])
                    row.label(text=edge_number)
                if context.scene.polycount_show_faces:
                    faces_number = trim_numbers(obj[4])
                    row.label(text=faces_number)
        

class POLYCOUNTILST_PT_Settings(bpy.types.Panel):
    bl_label = "Polycount Settings"
    bl_idname = "POLYCOUNTILST_PT_Settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.label(text="Filter by:")
        row = layout.row(align=True)

        row.prop(context.scene, "polycount_show_tris", text="Tri", icon="MESH_DATA")
        row.prop(context.scene, "polycount_show_verts", text="Vert", icon="VERTEXSEL")
        row.prop(context.scene, "polycount_show_edges", text="Edge", icon="EDGESEL")
        row.prop(context.scene, "polycount_show_faces", text="Face", icon="FACESEL")

        row = layout.row()
        row.prop(context.scene, "show_total_tris", text="Show Total Tris")
        #row = layout.row()
        #row.prop(context.scene, "show_selected_in_edit", text="Show Selected in Edit Mode")
    

class POLYCOUNT_OT_refresh(bpy.types.Operator):
    bl_idname = "keyops.polycount_user_interaction"
    bl_label = "Show polycount in Scene properties panel"
    bl_description = "Object Name"
    make_active: StringProperty(default="") # type: ignore
    poly_sort: EnumProperty(items=[ 
        ('NAME', "Name", ""),
        ('VERTS', "Verts", ""),
        ('EDGES', "Edges", ""),
        ('FACE', "Faces", ""),
        ('TRIS', "Tris", ""),
    ], default='TRIS') # type: ignore
    refresh: BoolProperty(default=False) # type: ignore

    @classmethod
    def poll(cls, context):
        return len(context.view_layer.objects) > 0
    
    def invoke(self, context, event):
        global ev 
        ev = []
        if event.shift:
            ev.append("Shift")
        ev.append("Click")
    
        return self.execute(context)
        

    def execute(self, context):
        global polycount_sorting_ascending
        global polycount_sorting

        if self.refresh:
            self.refresh = False
            pass
        else:
            if (self.make_active != "" and bpy.data.objects.get(str(self.make_active)) != None):
                if context.mode == 'OBJECT':
                    if ev != ["Shift", "Click"]:
                        bpy.ops.object.select_all(action='DESELECT')
                context.view_layer.objects.active = bpy.data.objects[str(self.make_active)]
                context.view_layer.objects.active.select_set(True)
                
            else:
                if self.poly_sort == polycount_sorting:
                    # if we want to toogle sorting type
                    polycount_sorting_ascending = not polycount_sorting_ascending
                else:
                    # if we change sort
                    polycount_sorting = self.poly_sort
            # resetting the active param
            self.make_active = ""

        if polycount_sorting == 'NAME':
            name_ascending = not polycount_sorting_ascending
            polycount.sort(
                key=sortList, reverse=name_ascending)
        else:
            polycount.sort(
            key=sortList, reverse=polycount_sorting_ascending)

        return {'FINISHED'}
