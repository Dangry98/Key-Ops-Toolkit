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

def draw_object_panel(self, context):
    layout = self.layout
    wm = context.window_manager
    
    box = layout.box()
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




# ---------------------------------------------------------------- 1.0 N-panel
# One "Key Ops" tab with native subpanels: Blender handles collapse, reordering
# and pinning. Sections follow the mode, and pipeline tools sit in one closed group.

TAB = "Key Ops"


def _modeling_mode(context):
    return context.mode in {'OBJECT', 'EDIT_MESH'}


class KEYOPS_PT_main(bpy.types.Panel):
    bl_label = "Key Ops"
    bl_idname = "KEYOPS_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = TAB
    bl_order = 0

    def draw_header(self, context):
        row = self.layout.row(align=True)
        row.scale_x = 0.94
        for name in ("K", "ey", "Op", "s"):
            row.label(text="", icon_value=get_icon(name))

    def draw_header_preset(self, context):
        row = self.layout.row(align=True)
        row.operator("keyops.shortcut_cheatsheet", text="", icon='QUESTION', emboss=False)
        row.menu("KEYOPS_MT_panel_menu", text="", icon='COLLAPSEMENU')

    def draw(self, context):
        prefs = get_keyops_prefs()
        layout = self.layout
        row = layout.row(align=True)
        mode = {'OBJECT': "Object Mode", 'EDIT_MESH': "Edit Mode"}.get(context.mode, context.mode.replace("_", " ").title())
        row.label(text=mode, icon='OBJECT_DATAMODE' if context.mode == 'OBJECT' else 'EDITMODE_HLT')
        if prefs.pause_shortcuts:
            sub = layout.row(align=True)
            sub.alert = True
            sub.prop(prefs, "pause_shortcuts", text="Shortcuts Paused - Resume", icon='PLAY', toggle=True)
        if not _modeling_mode(context):
            sub = layout.column()
            sub.active = False
            sub.label(text="Key Ops tools show in Object and Edit Mode.")


class _KeyOpsSubPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = TAB
    bl_parent_id = "KEYOPS_PT_main"


class KEYOPS_PT_object(_KeyOpsSubPanel, bpy.types.Panel):
    bl_label = "Object"
    bl_idname = "KEYOPS_PT_object"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and get_keyops_prefs().enable_toolkit_panel

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon("mesh_cube"))

    def draw(self, context):
        draw_object_panel(self, context)


class KEYOPS_PT_edit_mesh(_KeyOpsSubPanel, bpy.types.Panel):
    bl_label = "Mesh"
    bl_idname = "KEYOPS_PT_edit_mesh"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and get_keyops_prefs().enable_toolkit_panel

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon("editmode"))

    def draw_header_preset(self, context):
        self.layout.popover(panel="EDIT_PT_Settings", text="", icon='PREFERENCES')

    def draw(self, context):
        draw_edit_mode_panel(self, context, draw_header=False)


class KEYOPS_PT_modifiers(_KeyOpsSubPanel, bpy.types.Panel):
    bl_label = "Modifiers"
    bl_idname = "KEYOPS_PT_modifiers"
    bl_order = 2

    @classmethod
    def poll(cls, context):
        return _modeling_mode(context) and get_keyops_prefs().enable_toolkit_panel

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon("modifier"))

    def draw(self, context):
        draw_modifier_panel(self, context, draw_header=False)


class KEYOPS_PT_retopology(_KeyOpsSubPanel, bpy.types.Panel):
    bl_label = "Retopology"
    bl_idname = "KEYOPS_PT_retopology"
    bl_order = 3

    @classmethod
    def poll(cls, context):
        return _modeling_mode(context) and get_keyops_prefs().enable_toggle_retopology

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon("retopo"))

    def draw(self, context):
        draw_retopology_panel(self, context, draw_header=False)


_PIPELINE = ("quick_bake_name", "auto_lod", "cad_decimate", "polycount_list")


class KEYOPS_PT_pipeline(_KeyOpsSubPanel, bpy.types.Panel):
    bl_label = "Pipeline"
    bl_idname = "KEYOPS_PT_pipeline"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 4

    @classmethod
    def poll(cls, context):
        prefs = get_keyops_prefs()
        return context.mode == 'OBJECT' and any(getattr(prefs, "enable_" + f) for f in _PIPELINE)

    def draw_header(self, context):
        self.layout.label(text="", icon='EXPORT')

    def draw(self, context):
        sub = self.layout.row()
        sub.active = False
        sub.label(text="Bake names, LODs, decimation, poly counts")


class _PipelineChild(_KeyOpsSubPanel):
    bl_parent_id = "KEYOPS_PT_pipeline"
    bl_options = {'DEFAULT_CLOSED'}
    feature = ""

    @classmethod
    def poll(cls, context):
        return getattr(get_keyops_prefs(), "enable_" + cls.feature)


class KEYOPS_PT_bake_names(_PipelineChild, bpy.types.Panel):
    bl_label = "Bake Names"
    bl_idname = "KEYOPS_PT_bake_names"
    feature = "quick_bake_name"

    def draw(self, context):
        draw_quick_bake_name(self, context, draw_header=False)


class KEYOPS_PT_lod(_PipelineChild, bpy.types.Panel):
    bl_label = "Auto LOD"
    bl_idname = "KEYOPS_PT_lod"
    feature = "auto_lod"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon("mesh_icosphere2"))

    def draw(self, context):
        draw_lod_panel(self, context, draw_header=False)


class KEYOPS_PT_cad_decimate(_PipelineChild, bpy.types.Panel):
    bl_label = "CAD Decimate"
    bl_idname = "KEYOPS_PT_cad_decimate"
    feature = "cad_decimate"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon("mod_decim"))

    def draw(self, context):
        draw_cad_decimate_panel(self, context, draw_header=False)


class KEYOPS_PT_polycount(_PipelineChild, bpy.types.Panel):
    bl_label = "Polycount"
    bl_idname = "KEYOPS_PT_polycount"
    feature = "polycount_list"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon("polycount"))

    def draw(self, context):
        from ..operators import poly_count_list
        import time
        poly_count_list.npanel_last_draw = time.time()
        draw_polycount_list_ui(self, context)


def _register_panel_props():
    bpy.types.WindowManager.toolkit_panel_mode = bpy.props.EnumProperty(
        name="Toolkit Panel Mode", items=get_toolkit_panel_items, options={'ENUM_FLAG'})
    from ..operators.select_similar import register_select_similar
    register_select_similar()


def _unregister_panel_props():
    del bpy.types.WindowManager.toolkit_panel_mode
    from ..operators.select_similar import unregister_select_similar
    unregister_select_similar()


KEYOPS_PT_main.register = staticmethod(_register_panel_props)
KEYOPS_PT_main.unregister = staticmethod(_unregister_panel_props)

panel_classes = (
    KEYOPS_PT_main,
    KEYOPS_PT_object,
    KEYOPS_PT_edit_mesh,
    KEYOPS_PT_modifiers,
    KEYOPS_PT_retopology,
    KEYOPS_PT_pipeline,
    KEYOPS_PT_bake_names,
    KEYOPS_PT_lod,
    KEYOPS_PT_cad_decimate,
    KEYOPS_PT_polycount,
)
