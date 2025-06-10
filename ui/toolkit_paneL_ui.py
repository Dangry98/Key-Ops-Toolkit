import bpy
from ..utils.pref_utils import get_icon, get_addon_name
from ..operators.poly_count_list import draw_polycount_list_ui
from ..operators.auto_lod import draw_lod_panel
from ..operators.quick_bake_name import draw_quick_bake_name
from ..operators.toggle_retopology import draw_retopology_panel
from ..operators.cad_decimate import draw_cad_decimate_panel
from ..operators.toolkit_panel import draw_edit_mode_panel, draw_modifier_panel
import functools

show_object_panel = False

def object_panel(self, context):
    layout = self.layout
    wm = context.window_manager
    
    box = layout.box()
    box.label(text="Object Operations", icon_value=get_icon("mesh_cube"))
    col = box.column(align=False) 

    # row = col.row(align=True)
    # # add vert, edge, face, click on the menters edit mode
    # row.scale_y = 2
    # row.scale_x = 2
    # row.operator("keyops.toolkit_panel", text="", icon = "VERTEXSEL")
    # row.operator("keyops.toolkit_panel", text="", icon = "EDGESEL")
    # row.operator("keyops.toolkit_panel", text="", icon = "FACESEL")

    row = col.row(align=True)
    row.scale_y = 1.4
    row.operator("keyops.toolkit_panel", text="Combine", icon_value=get_icon("union")).type = "Smart_Join_Objects"
    row.operator("keyops.toolkit_panel", text="Seperate", icon_value=get_icon("slice")).type = "seprate_objects_by"


    row = col.row(align=True)
    row.scale_y = 1.4
    row.operator("keyops.toolkit_panel", text="Apply Modifiers",  icon_value=get_icon("mesh")).type = "Instant_Apply_Modifiers"
    row.operator("object.smart_apply_scale", text="Freeze Scale", icon = "FREEZE")
    row = col.row(align=True)
    row.scale_y = 1.4
    row.operator("keyops.toolkit_panel", text="Snap to Floor", icon = "VIEW_PERSPECTIVE").type = "snap_to_floor"
    row.operator("keyops.toolkit_panel", text="Clear Normals", icon="X").type = "clear_custom_normals"

    row = col.row(align=True)
    row.label(text="Duplicate Linked")
    row = col.row(align=True)
    row.scale_y = 1.4
    row.operator("object.duplicate_move_linked", text="Mesh", icon = "LINKED")
    row.operator("keyops.toolkit_panel", text="Modifiers", icon = "LINKED").type = "duplicate_linked_modifiers"
    
    
    if context.mode == 'OBJECT':
        # box.label(text="Booleans")
        row = box.row(align=True)
        row = box.row(align=True)
        row.label(text="Booleans")
        # row = box.row(align=True)
        row.scale_y = 1.5
        row.scale_x = 4
        row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("diffrance")).type = "DIFFERENCE"
        row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("union")).type = "UNION"
        row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("intersection")).type = "INTERSECT"
        row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("slice")).type = "SLICE"
        # row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("hole")).type = "SLICE"

        row = box.row()

        # row = box.row()
        row.scale_y = 1.1
        row.scale_x = 1
        row.alignment = 'LEFT'
        row.prop(wm, "live_booleans", text="Realtime")
        row.operator("object.boolean_scroll", text="Boolean Scroll", icon="MOUSE_MMB_SCROLL")

    # box = layout.box()
    # box.label(text="High/Low Collections")
    # col = box.column(align=True)
    # row = col.row(align=True)
    # row.operator("keyops.toolkit_panel", text="Unique Collection Copy", icon="COLLECTION_COLOR_02").type = "unique_collection_duplicat"
    # row = col.row(align=True)
    # row.operator("keyops.toolkit_panel", text="Toggle").type = "toggle_high_low"
    # row.operator("keyops.toolkit_panel", text="high").type = "high"
    # row.operator("keyops.toolkit_panel", text="low").type = "low"



def redraw_ui(self, context):
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'UI' and area.ui_type == 'New Toolkit':
                    area.tag_redraw()
                    break

def update_ui(self, context):
    global show_object_panel
    show_object_panel = self.show_object_panel
    # update the UI when properties change
    # This function can be used to refresh the UI or perform other actions
    bpy.app.timers.register(redraw_ui, persistent=True, first_interval=0.01)
    print("UI updated with new properties")


    # Add a Blender timer to periodically refresh the UI

ev = []

class ToggleToolkitPanelEnum(bpy.types.Operator):
    bl_idname = "keyops.toggle_toolkit_panel_enum"
    bl_label = "Toggle Toolkit Panel Enum"
    bl_description = "Toggle the visibility of the toolkit panel enum"

    type: bpy.props.StringProperty(
        name="ID",
        description="ID of the panel to toggle",
        default="toolkit_panel_mode"
    )

    def invoke(self, context, event):
        if event.shift:
            ev.append("shift")
        return self.execute(context)

    def execute(self, context):
        scene = context.scene
        global ev
        if "shift" in ev:
            scene.toolkit_panel_mode ^= {self.type}
        else:
            scene.toolkit_panel_mode = {self.type}

        ev = []
        return {'FINISHED'}


class NewToolkitPanel(bpy.types.Panel):
    bl_description = "KeyOps Toolkit Panel"
    bl_label = "Toolkit"
    bl_idname = "KEYOPS_PT_new_toolkit_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'New Toolkit'

    # @classmethod
    # def poll(cls, context):
    #     return context.active_object is not None and context.active_object.mode == 'EDIT'

    def draw_header(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.scale_x = 0.94
        row.label(text="", icon_value=get_icon("K"))
        row.label(text="", icon_value=get_icon("ey"))
        row.label(text="", icon_value=get_icon("Op"))
        row.label(text="", icon_value=get_icon("s"))

    def draw_header_preset(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("preferences.addon_show", text="", icon='PREFERENCES', emboss=False).module = get_addon_name()
     

    def draw(self, context):
        global show_object_panel
        scene = context.scene
        layout = self.layout
        # layout.prop_tabs_enum(scene, "toolkit_panel_mode", icon_only=False)
        row = layout.row(align=True)
        layout = self.layout
        row = layout.row(align=True)
        row.scale_x = 12
        row.scale_y = 1.4
        row.alignment = 'EXPAND'
        row.prop(context.scene, "toolkit_panel_mode", emboss=True)
        row = layout.row(align=True)
        row.scale_x = 12
        row.scale_y = 1.25

        object = 'OBJECT' in scene.toolkit_panel_mode
        modifiers = 'MODIFIERS' in scene.toolkit_panel_mode
        lod = 'LOD' in scene.toolkit_panel_mode
        cad_decimate = 'CAD_DECIMATE' in scene.toolkit_panel_mode
        polycount_list = 'POLYCOUNT_LIST' in scene.toolkit_panel_mode

        # row.operator("keyops.toggle_toolkit_panel_enum", text="", icon_value=get_icon("mesh_cube"), depress=object, emboss=object).type = "OBJECT"
        # row.operator("keyops.toggle_toolkit_panel_enum", text="", icon_value=get_icon("modifier"), depress=modifiers, emboss=modifiers).type = "MODIFIERS"
        # row.operator("keyops.toggle_toolkit_panel_enum", text="", icon_value=get_icon("mesh_icosphere2"), depress=lod, emboss=lod).type = "LOD"
        # row.operator("keyops.toggle_toolkit_panel_enum", text="", icon_value=get_icon("mod_decim"), depress=cad_decimate, emboss=cad_decimate).type = "CAD_DECIMATE"
        # row.operator("keyops.toggle_toolkit_panel_enum", text="", icon="SORTSIZE", depress=polycount_list, emboss=polycount_list).type = "POLYCOUNT_LIST"
        
        if object:
            draw_retopology_panel(self, context, draw_header=True)
            if context.mode == 'OBJECT':
                object_panel(self, context)
                draw_quick_bake_name(self, context, draw_header=True)
            elif context.mode == 'EDIT_MESH':
                draw_edit_mode_panel(self, context, draw_header=True)
        if modifiers:
            draw_modifier_panel(self, context, draw_header=True)
        if lod:
            draw_lod_panel(self, context, draw_header=True)
        if cad_decimate:
            draw_cad_decimate_panel(self, context, draw_header=True)
        if polycount_list:
            draw_polycount_list_ui(self, context)
    
        # row = layout.row(align=True)
        # row.scale_x = 12
        # row.scale_y = 1.25
        # object_emboss = show_object_panel
        # icoon = get_icon("mesh_cube_selected")
        # if not object_emboss:
        #     icoon = get_icon("mesh_cube")
        # print(object_emboss)
 
        # row.prop(context.scene, "show_object_panel", text="", icon_value=icoon, emboss= object_emboss)
        # row.prop(context.scene, "show_modifiers_panel", text="", icon_value=get_icon("modifier"), emboss=scene.show_modifiers_panel)
        # row.prop(context.scene, "show_lod_panel", text="", icon_value=get_icon("mesh_icosphere2"), emboss=scene.show_lod_panel)
        # row.prop(context.scene, "show_cad_decimate_panel", text="", icon_value=get_icon("mod_decim"), emboss=scene.show_cad_decimate_panel)

    def register():

        # You can add a toggle to demonstrate dynamic change
        bpy.types.Scene.some_toggle = bpy.props.BoolProperty(
            name="Toggle Icon Change",
            description="Change enum icon dynamically",
            default=False
        )
        bpy.types.Scene.toolkit_panel_mode = bpy.props.EnumProperty(
            name="Toolkit Panel Mode",
            description="Manage which panels should show",
            items=[
                ('OBJECT', "", "Show Object panel", get_icon("mesh_cube"), 1),
                ('MODIFIERS', "", "Show Modifiers panel", get_icon("modifier"), 2),
                ('LOD', "", "Show LOD panel", get_icon("mesh_icosphere2"), 4),
                ('CAD_DECIMATE', "", "Show CAD Decimate panel", get_icon("mod_decim"), 8),
                ("POLYCOUNT_LIST", "", "Show Polycount List panel", get_icon("polycount"), 16),
            ],
            options={'ENUM_FLAG'},
            default={'OBJECT', 'MODIFIERS'},
        )

        bpy.types.Scene.show_object_panel = bpy.props.BoolProperty(
            name="Show Object Panel",
            description="Toggle visibility of the Object panel",
            default=True,
            update=update_ui
        )
        bpy.types.Scene.show_modifiers_panel = bpy.props.BoolProperty(
            name="Show Modifiers Panel",
            description="Toggle visibility of the Modifiers panel",
            default=True,
            update=update_ui
        )
        bpy.types.Scene.show_lod_panel = bpy.props.BoolProperty(
            name="Show LOD Panel",
            description="Toggle visibility of the LOD panel",
            default=True,
            update=update_ui
        )
        bpy.types.Scene.show_cad_decimate_panel = bpy.props.BoolProperty(
            name="Show CAD Decimate Panel",
            description="Toggle visibility of the CAD Decimate panel",
            default=True,
            update=update_ui
        )
        
        bpy.utils.register_class(ToggleToolkitPanelEnum)
        
    def unregister():
        del bpy.types.Scene.some_toggle
        del bpy.types.Scene.toolkit_panel_mode
        del bpy.types.Scene.show_object_panel
        del bpy.types.Scene.show_modifiers_panel
        del bpy.types.Scene.show_lod_panel
        del bpy.types.Scene.show_cad_decimate_panel

        bpy.utils.unregister_class(ToggleToolkitPanelEnum)

