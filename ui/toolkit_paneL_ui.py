import bpy
from ..utils.pref_utils import get_icon, get_addon_name
from ..operators.poly_count_list import draw_polycount_list_ui
from ..operators.auto_lod import draw_lod_panel
from ..operators.quick_bake_name import draw_quick_bake_name
from ..operators.toggle_retopology import draw_retopology_panel
from ..operators.cad_decimate import draw_cad_decimate_panel
from ..operators.toolkit_panel import draw_edit_mode_panel, draw_modifier_panel
from ..utils.pref_utils import get_keyops_prefs
BLENDER_VERSION = bpy.app.version

show_object_panel = False
startup = True

def set_default_panels():
    prefs = get_keyops_prefs()
    wm = bpy.context.window_manager
    if prefs.enable_toolkit_panel or prefs.enable_quick_bake_name or prefs.enable_toggle_retopology:
        wm.toolkit_panel_mode |= {'OBJECT'}

    if prefs.enable_toolkit_panel:
        wm.toolkit_panel_mode |= {'MODIFIERS'}

        
def get_toolkit_panel_items(scene, context):
    global startup
    prefs = get_keyops_prefs()
    
    items = []
    if prefs.enable_toolkit_panel or prefs.enable_quick_bake_name or prefs.enable_toggle_retopology:
        items.append(('OBJECT', "", "Show Object panel", get_icon("mesh_cube"), 1))
    if prefs.enable_toolkit_panel:
        items.append(('MODIFIERS', "", "Show Modifiers panel", get_icon("modifier"), 2))
    if prefs.enable_auto_lod:
        items.append(('LOD', "", "Show LOD panel", get_icon("mesh_icosphere2"), 4))
    if prefs.enable_cad_decimate:
        items.append(('CAD_DECIMATE', "", "Show CAD Decimate panel", get_icon("mod_decim"), 8))
    if prefs.enable_polycount_list:
        items.append(("POLYCOUNT_LIST", "", "Show Polycount List panel", get_icon("polycount"), 16))

    # should deafult to object and modifiers if both are available, otherwise just show the one that is available
    if startup:
        startup = False        
        set_default_panels()

    return items

NPANEL_PROPOSAL = False  # True: the cleaner layout proposal (same buttons, same operators)


def _subheading(col, text):
    col.separator(factor=0.8)
    r = col.row()
    r.active = False
    r.label(text=text)


def draw_object_panel_clean(self, context):
    """Proposal: same sections and operators, one button height, quiet sub-headings."""
    layout = self.layout
    wm = context.window_manager
    box = layout.box()
    box.label(text="Object Toolkit", icon_value=get_icon("mesh_cube"))
    col = box.column(align=True)
    col.scale_y = 1.25
    pairs = (
        (("keyops.toolkit_panel", "Combine", get_icon("union"), None, "Smart_Join_Objects"),
         ("keyops.toolkit_panel", "Separate", get_icon("slice"), None, "seprate_objects_by")),
        (("keyops.toolkit_panel", "Apply Modifiers", get_icon("mesh"), None, "Instant_Apply_Modifiers"),
         ("object.smart_apply_scale", "Freeze Scale", 0, "FREEZE", None)),
        (("keyops.snap_to_floor", "Snap to Floor", 0, "VIEW_PERSPECTIVE", None),
         ("keyops.toolkit_panel", "Clear Normals", 0, "X", "clear_custom_normals")),
        (("keyops.fast_mirror", "Fast Mirror", 0, "MOD_MIRROR", None),
         ("keyops.select_similar", "Select Similar", 0, "POINTCLOUD_POINT", None)),
    )
    for pair in pairs:
        row = col.row(align=True)
        for idname, text, icon_value, icon, type_ in pair:
            if icon_value:
                op = row.operator(idname, text=text, icon_value=icon_value)
            else:
                op = row.operator(idname, text=text, icon=icon)
            if type_:
                op.type = type_
    col.operator("keyops.parent_used_objects", text="Parent Used Objects", icon="CON_CHILDOF")

    _subheading(col, "Duplicate Linked")
    row = col.row(align=True)
    row.operator("object.duplicate_move_linked", text="Mesh", icon="LINKED")
    row.operator("keyops.toolkit_panel", text="Modifiers", icon="LINKED").type = "duplicate_linked_modifiers"

    if context and context.mode == 'OBJECT':
        _subheading(col, "Boolean")
        grid = col.grid_flow(row_major=True, columns=4, even_columns=True, align=True)
        for kind, icon in (("DIFFERENCE", "difference"), ("UNION", "union"), ("INTERSECT", "intersect"), ("SLICE", "slice")):
            grid.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon(icon)).type = kind
        col.separator(factor=0.4)
        row = col.row(align=False)
        row.prop(wm, "live_booleans", text="Realtime")
        scroll_icon = "EVENT_CAPSLOCK" if BLENDER_VERSION <= (4, 2, 99) else "MOUSE_MMB_SCROLL"
        row.operator("object.boolean_scroll", text="Boolean Scroll", icon=scroll_icon)


def draw_object_panel(self, context):
    if NPANEL_PROPOSAL:
        return draw_object_panel_clean(self, context)
    layout = self.layout
    wm = context.window_manager
    
    box = layout.box()
    box.label(text="Object Toolkit", icon_value=get_icon("mesh_cube"))
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
    row.operator("keyops.toolkit_panel", text="Separate", icon_value=get_icon("slice")).type = "seprate_objects_by"

    row = col.row(align=True)
    row.scale_y = 1.4
    row.operator("keyops.toolkit_panel", text="Apply Modifiers",  icon_value=get_icon("mesh")).type = "Instant_Apply_Modifiers"
    row.operator("object.smart_apply_scale", text="Freeze Scale", icon = "FREEZE")
    row = col.row(align=True)
    row.scale_y = 1.4
    row.operator("keyops.snap_to_floor", text="Snap to Floor", icon = "VIEW_PERSPECTIVE")
    row.operator("keyops.toolkit_panel", text="Clear Normals", icon="X").type = "clear_custom_normals"

    row = col.row(align=True)
    row.scale_y = 1.4
    row.operator("keyops.fast_mirror", text="Fast Mirror", icon="MOD_MIRROR")
    row.operator("keyops.select_similar", text="Select Similar", icon="POINTCLOUD_POINT")

    row = col.row(align=True)
    row.scale_y = 1.4
    row.operator("keyops.parent_used_objects", text="Parent Used Objects", icon="CON_CHILDOF")

    row = col.row(align=True)
    row.label(text="Duplicate Linked")
    row = col.row(align=True)
    row.scale_y = 1.3
    row.operator("object.duplicate_move_linked", text="Mesh", icon = "LINKED")
    row.operator("keyops.toolkit_panel", text="Modifiers", icon = "LINKED").type = "duplicate_linked_modifiers"
    
    
    if context and context.mode == 'OBJECT':
        # box.label(text="Booleans")
        row = box.row(align=True)
        row = box.row(align=True)
        row.label(text="Boolean")
        # row = box.row(align=True)
        row.scale_y = 1.5
        row.scale_x = 4
        row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("difference")).type = "DIFFERENCE"
        row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("union")).type = "UNION"
        row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("intersect")).type = "INTERSECT"
        row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("slice")).type = "SLICE"
        # row.operator("object.add_boolean_modifier_operator", text="", icon_value=get_icon("hole")).type = "SLICE"

        row = box.row()

        # row = box.row()
        row.scale_y = 1.1
        row.scale_x = 1
        row.alignment = 'LEFT'
        row.prop(wm, "live_booleans", text="Realtime")
        old_version = BLENDER_VERSION <= (4, 2, 99)
        if old_version:
            row.operator("object.boolean_scroll", text="Boolean Scroll", icon="EVENT_CAPSLOCK")
        else:
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
                if region.type == 'UI' and area.ui_type == 'Toolkit':
                    area.tag_redraw()
                    break

def update_ui(self, context):
    global show_object_panel
    show_object_panel = self.show_object_panel
    # update the UI when properties change
    # This function can be used to refresh the UI or perform other actions
    bpy.app.timers.register(redraw_ui, persistent=True, first_interval=0.01)


    # Add a Blender timer to periodically refresh the UI

ev = []

class ToggleToolkitPanelEnum(bpy.types.Operator):
    bl_idname = "keyops.toggle_toolkit_panel_enum"
    bl_label = "Toggle Toolkit Panel Enum"
    bl_description = "Toggle the visibility of the toolkit panel enum"

    type: bpy.props.StringProperty(
        name="ID",
        description="ID of the panel to toggle",
        default="OBJECT"
    )

    def invoke(self, context, event):
        if event.shift:
            ev.append("shift")
        return self.execute(context)

    def execute(self, context):
        wm = context.window_manager
        global ev
        if self.type not in {item[0] for item in get_toolkit_panel_items(None, context)}:
            ev = []
            self.report({'WARNING'}, f"Unknown or disabled toolkit panel: {self.type}")
            return {'CANCELLED'}
        if "shift" in ev:
            wm.toolkit_panel_mode ^= {self.type}
        else:
            wm.toolkit_panel_mode = {self.type}

        ev = []
        return {'FINISHED'}


class NewToolkitPanel(bpy.types.Panel):
    bl_description = "KeyOps Toolkit Panel"
    bl_label = "Toolkit"
    bl_idname = "KEYOPS_PT_new_toolkit_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Toolkit'
    if BLENDER_VERSION >= (5,2,0):
        bl_icon_value = get_icon("K")

    @classmethod
    def poll(cls, context):
        return get_toolkit_panel_items(context.scene, context)

    def draw_header(self, context):
        if not context.window_manager.toolkit_panel_mode:
            set_default_panels()

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
        row.operator("keyops.shortcut_cheatsheet", text="", icon='QUESTION', emboss=False)
        row.operator("preferences.addon_show", text="Prefs", icon='PREFERENCES', emboss=True).module = get_addon_name()

    def draw(self, context):
        global show_object_panel
        wm = context.window_manager
        layout = self.layout
        # layout.prop_tabs_enum(scene, "toolkit_panel_mode", icon_only=False)
        row = layout.row(align=True)
        layout = self.layout
        row = layout.row(align=True)
        row.scale_x = 12
        row.scale_y = 1.4
        row.alignment = 'EXPAND'
        row.prop(wm, "toolkit_panel_mode", emboss=True)
        prefs = get_keyops_prefs()
        # row = layout.row(align=True)
        # row.scale_x = 12
        # row.scale_y = 1.25

        object = 'OBJECT' in wm.toolkit_panel_mode
        modifiers = 'MODIFIERS' in wm.toolkit_panel_mode
        lod = 'LOD' in wm.toolkit_panel_mode
        cad_decimate = 'CAD_DECIMATE' in wm.toolkit_panel_mode
        polycount_list = 'POLYCOUNT_LIST' in wm.toolkit_panel_mode

        # row.operator("keyops.toggle_toolkit_panel_enum", text="", icon_value=get_icon("mesh_cube"), depress=object, emboss=object).type = "OBJECT"
        # row.operator("keyops.toggle_toolkit_panel_enum", text="", icon_value=get_icon("modifier"), depress=modifiers, emboss=modifiers).type = "MODIFIERS"
        # row.operator("keyops.toggle_toolkit_panel_enum", text="", icon_value=get_icon("mesh_icosphere2"), depress=lod, emboss=lod).type = "LOD"
        # row.operator("keyops.toggle_toolkit_panel_enum", text="", icon_value=get_icon("mod_decim"), depress=cad_decimate, emboss=cad_decimate).type = "CAD_DECIMATE"
        # row.operator("keyops.toggle_toolkit_panel_enum", text="", icon="SORTSIZE", depress=polycount_list, emboss=polycount_list).type = "POLYCOUNT_LIST"
        
        if object:
            prefs = get_keyops_prefs()
            draw_retopology_panel(self, context, draw_header=True)
            if context.mode == 'OBJECT':
                if prefs.enable_toolkit_panel:
                    draw_object_panel(self, context)
                draw_quick_bake_name(self, context, draw_header=True)
            elif context.mode == 'EDIT_MESH':
                if prefs.enable_toolkit_panel:
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
 
        # row.prop(context.scene.keyops, "show_object_panel", text="", icon_value=icoon, emboss= object_emboss)
        # row.prop(context.scene.keyops, "show_modifiers_panel", text="", icon_value=get_icon("modifier"), emboss=scene.show_modifiers_panel)
        # row.prop(context.scene.keyops, "show_lod_panel", text="", icon_value=get_icon("mesh_icosphere2"), emboss=scene.show_lod_panel)
        # row.prop(context.scene.keyops, "show_cad_decimate_panel", text="", icon_value=get_icon("mod_decim"), emboss=scene.show_cad_decimate_panel)

    def register():

        bpy.types.WindowManager.toolkit_panel_mode = bpy.props.EnumProperty(
            name="Toolkit Panel Mode",
            description="Manage which panels should show",
            items=get_toolkit_panel_items,
            options={'ENUM_FLAG'},
        )

        
        bpy.utils.register_class(ToggleToolkitPanelEnum)
        from ..operators.select_similar import register_select_similar
        register_select_similar()
        
    def unregister():
        del bpy.types.WindowManager.toolkit_panel_mode

        bpy.utils.unregister_class(ToggleToolkitPanelEnum)
        from ..operators.select_similar import unregister_select_similar
        unregister_select_similar()

