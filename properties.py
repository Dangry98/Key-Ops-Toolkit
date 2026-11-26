"""All Scene properties used by the addon, collected in one PropertyGroup.

Access them through ``context.scene.keyops``, e.g. ``context.scene.keyops.fast_mode``.

Update callbacks live in the modules that own the feature. They are wrapped here with
lazy imports so this file does not pull in every operator module at register time.
Inside a callback, ``self`` is the KeyOpsSceneProperties instance (not the Scene).
"""

import os
import tempfile

import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)


# ---------------------------------------------------------------------------
# Update callbacks (lazy wrappers)
# ---------------------------------------------------------------------------

def _update_toolkit_ui(self, context):
    from .ui.toolkit_paneL_ui import update_ui
    update_ui(self, context)


def _update_outliner_selection_options(self, context):
    from .operators.outliner_options import enabled_selection_options
    enabled_selection_options(self, context)


def _update_vertex_color(self, context):
    from .operators.toolkit_panel import update_vertex_color
    update_vertex_color(self, context)


# ---------------------------------------------------------------------------
# Nested property groups
# ---------------------------------------------------------------------------

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
            ('TRIS', "", "Tris", 'MESH_DATA', 1),
            ('VERT', "", "Vert", 'VERTEXSEL', 2),
            ('EDGE', "", "Edge", 'EDGESEL', 4),
            ('FACE', "", "Face", 'FACESEL', 8),
            ('MS', "", "Show Object Modifier Execution Time", 'MODIFIER', 16)
        ],
        options={'ENUM_FLAG'},
        default={'TRIS', 'VERT', 'MS'}
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
    child_collection: BoolProperty(name="Child", default=False, description="Show all objects in collections that are children of the current selected collection")  # type: ignore
    show_collection_instances: BoolProperty(  # type: ignore
        name="Collection Instances",
        description="Show collection instances",
        default=False
    )
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
    search: StringProperty(  # type: ignore
        name="Search",
        description="Only list objects whose name contains this (not case sensitive)",
        default="", options={'TEXTEDIT_UPDATE'}
    )
    type_filter: EnumProperty(  # type: ignore
        name="Object Types",
        description="Which kinds of objects the list shows",
        items=[
            ('MESH', "Mesh", "Meshes", 'OUTLINER_OB_MESH', 1),
            ('CURVE', "Curve", "Curves and surfaces", 'OUTLINER_OB_CURVE', 2),
            ('FONT', "Text", "Text objects", 'OUTLINER_OB_FONT', 4),
            ('META', "Metaball", "Metaballs", 'OUTLINER_OB_META', 8),
        ],
        options={'ENUM_FLAG'},
        default={'MESH', 'CURVE', 'FONT', 'META'}
    )
    show_hidden: BoolProperty(  # type: ignore
        name="Show Hidden",
        description="List hidden objects too, greyed out, with an eye button to show them again",
        default=True
    )
    keyboard_navigation: BoolProperty(  # type: ignore
        name="Keyboard Navigation",
        description="Up/Down Arrow or W/S moves the active object through the list while hovering it (in the Toolkit N-panel or Scene Properties). Hold Shift to extend the selection",
        default=True
    )


class AutoLODProperties(bpy.types.PropertyGroup):
    suffix: StringProperty(default="_LOD")  # type: ignore
    iterativ_lod_suffix: BoolProperty(default=True)  # type: ignore
    lod_parent_object: BoolProperty(default=False)  # type: ignore
    apply_decimate_modifier: BoolProperty(default=False)  # type: ignore
    amount_of_lods: IntProperty(default=3, min=1)  # type: ignore
    lod_difference: FloatProperty(default=45.0, min=0.0, max=100.0)  # type: ignore
    unlock_normals_on_all_lods: BoolProperty(default=False)  # type: ignore
    edge_split: BoolProperty(default=False)  # type: ignore
    edge_split_angle: FloatProperty(default=60.0)  # type: ignore
    max_face_size: FloatProperty(default=0.0005)  # type: ignore
    remove_non_manifold_faces: BoolProperty(default=False)  # type: ignore
    multipler: FloatProperty(default=2.0)  # type: ignore
    delete_loose_edges: BoolProperty(default=True)  # type: ignore
    keep_symmetry_X: BoolProperty(default=False)  # type: ignore
    transfere_normals: BoolProperty(default=True)  # type: ignore
    transfere_edge_normals: BoolProperty(default=True)  # type: ignore
    create_collection: BoolProperty(default=False)  # type: ignore
    add_weighted_normals: BoolProperty(default=True)  # type: ignore


def _get_correct_uvs(self):
    return self.id_data.tool_settings.use_transform_correct_face_attributes


def _set_correct_uvs(self, value):
    # Turning Preserve UVs on also turns on Keep Connected, so UV islands don't tear apart
    tool_settings = self.id_data.tool_settings
    tool_settings.use_transform_correct_face_attributes = value
    if value:
        tool_settings.use_transform_correct_keep_connected = True


# ---------------------------------------------------------------------------
# Main property group
# ---------------------------------------------------------------------------

class KeyOpsSceneProperties(PropertyGroup):
    # Blender's "Correct Face Attributes" transform option, plus Keep Connected when turned on.
    # Not stored: get/set read and write the scene's tool settings directly.
    correct_uvs: BoolProperty(
        name="Preserve UVs",
        description="Keep UVs in place while moving geometry (Correct Face Attributes). "
                    "Turning it on also turns on Keep Connected",
        get=_get_correct_uvs, set=_set_correct_uvs)  # type: ignore

    # --- Nested groups ------------------------------------------------------
    polycount_props: PointerProperty(type=PolyCountProperties)  # type: ignore
    auto_lod_props: PointerProperty(type=AutoLODProperties)  # type: ignore

    # --- Toolkit panel UI (ui/toolkit_paneL_ui.py) ----------------------------
    some_toggle: BoolProperty(  # type: ignore
        name="Toggle Icon Change",
        description="Change enum icon dynamically",
        default=False
    )
    show_object_panel: BoolProperty(  # type: ignore
        name="Show Object Panel",
        description="Toggle visibility of the Object panel",
        default=True,
        update=_update_toolkit_ui
    )
    show_modifiers_panel: BoolProperty(  # type: ignore
        name="Show Modifiers Panel",
        description="Toggle visibility of the Modifiers panel",
        default=True,
        update=_update_toolkit_ui
    )
    show_lod_panel: BoolProperty(  # type: ignore
        name="Show LOD Panel",
        description="Toggle visibility of the LOD panel",
        default=True,
        update=_update_toolkit_ui
    )
    show_cad_decimate_panel: BoolProperty(  # type: ignore
        name="Show CAD Decimate Panel",
        description="Toggle visibility of the CAD Decimate panel",
        default=True,
        update=_update_toolkit_ui
    )

    # --- X-Ray select (operators/xray_select.py) -----------------------------
    # One setting per select tool, so each tool remembers its own (like its Mode)
    xray_select_box: BoolProperty(  # type: ignore
        name="X-Ray Select",
        description="Always select through geometry with the Select Box tool",
        default=False,
    )
    xray_select_circle: BoolProperty(  # type: ignore
        name="X-Ray Select",
        description="Always select through geometry with the Select Circle tool",
        default=False,
    )
    xray_select_lasso: BoolProperty(  # type: ignore
        name="X-Ray Select",
        description="Always select through geometry with the Select Lasso tool",
        default=False,
    )

    # --- UV tools (operators/uv_tools.py) ------------------------------------
    smart_uv_sync_enable: BoolProperty(name="Enable", default=True, description="Right Click to Toggle Sync Mode and UV Selection, can be slow on very large meshes")  # type: ignore

    # --- Outliner options (operators/outliner_options.py) --------------------
    select_children: BoolProperty(  # type: ignore
        name="Select Children",
        description="Automatically select children of selected objects",
        default=False,
        update=_update_outliner_selection_options
    )
    collapse_unselected_collections: BoolProperty(  # type: ignore
        name="Collapse Unselected Collections",
        description="Automatically collapse collections that are not related to the selected objects",
        default=False,
        update=_update_outliner_selection_options
    )
    auto_focus_in_outliner: BoolProperty(  # type: ignore
        name="Auto Select in Outliner",
        description="Automatically focus on the selected objects in the outliner, can be slow with many objects",
        default=False,
        update=_update_outliner_selection_options
    )

    # --- Toolkit panel (operators/toolkit_panel.py) --------------------------
    vertex_color: FloatVectorProperty(name="Vertex Color", subtype='COLOR', size=4, min=0.0, max=1.0, update=_update_vertex_color, default=(1.0, 1.0, 1.0, 0.3))  # type: ignore

    # --- CAD Decimate (operators/cad_decimate.py) ----------------------------
    auto_clear_garbage_data: BoolProperty(name="Auto Clear Garbage Data", default=True, description="Auto Clear Mesh Data Blocks (Saves a lot of Memory, but is slower)")  # type: ignore
    preserv_uvs: BoolProperty(name="Preserve UVs",default=True, description="Preserve UVs")  # type: ignore
    cad_decimate_export_path: StringProperty(name="Path",subtype='FILE_PATH',description="Path for exporting files",default=os.path.join(tempfile.gettempdir(),"CAD_Decimate"))  # type: ignore
    decimation_ratio: FloatProperty(name="Decimation Ratio",default=0.2, min=0.0,max=1.0,subtype='FACTOR',description="Decimation Ratio")  # type: ignore
    delete_files_after_import: BoolProperty(name="Delete Files After Import", default=True, description="Delete Files After Import")  # type: ignore
    export_selected_only: BoolProperty(name="Export Selected Only",default=True,description="Export Selected Only")  # type: ignore
    deceimate_type: EnumProperty(name="deceimate_type",  # type: ignore
        items=[('DECIMATE', 'High Quality (Slow)', 'Decimate modifier. Best result and keeps UVs, but slow on huge meshes'),
            ('WELD_DECIMATE', 'Medium Quality - Weld + Decimate', 'Weld (Connected) with an automatic, detail-safe distance does the cheap part of the reduction, then Decimate makes the final step to the target. Best for extremely dense meshes. Does not preserv UVs'),
            ('WELD', 'Low Quality (Fast)', 'Weld modifier only, does not preserv UVs'),
            ('CONNECT', 'Lowest Quality (Fastest)', 'Weld (Connected) only, very fast! But does not preserv UVs')],
        default='DECIMATE',description="Decimate Quality")
    merge_distance: FloatProperty(name="Merge Distance",default=0.02,min=0.001,max=1.0,subtype='FACTOR',description="Merge Distance (higher value = more decimation)")  # type: ignore
    format: EnumProperty(name="format",  # type: ignore
        items=[('OBJ', 'OBJ(Reliable, but slower)', 'OBJ'),
            ('PLY', 'PLY (Faster, but more error prone)', 'PLY'),
            ('COLLADA', 'COLLADA (Fastest, but always triangulated)', 'COLLADA')],
        default='COLLADA',description="Format")
    fast_mode: BoolProperty(default=True, description="Disabling 'Fast Mode' is Slower, but it can handle way more polygons without crashing Blender")  # type: ignore
    procent_or_amount: EnumProperty(name="Procent or Amount",  # type: ignore
        items=[('PROCENT', 'By Procent', 'By Procent'),
            ('AMOUNT', 'By Tris Count', 'By Tris Amount')],
        default='PROCENT',description="Procent or Amount")
    tris_count: IntProperty(name="Target Tris Count",default=10000,min=1,description="Target Tris Count")  # type: ignore


# Nested groups must be registered before the group that points to them.
classes = (
    PolyCountProperties,
    AutoLODProperties,
    KeyOpsSceneProperties,
)


def register_properties():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.keyops = PointerProperty(type=KeyOpsSceneProperties)


def unregister_properties():
    if hasattr(bpy.types.Scene, "keyops"):
        del bpy.types.Scene.keyops
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
