import bpy, bmesh
import inspect
import numpy as np # type: ignore
from mathutils import Vector
from bl_ui.space_toolsystem_common import ToolSelectPanelHelper

BLENDER_VERSION = bpy.app.version
BLENDER_VERSION_MAJOR_POINT_MINOR = float(bpy.app.version_string[0:4].strip("."))


def _addon_name_matches(module_name, addon_names):
    if not module_name or not addon_names:
        return False

    module_name = str(module_name).strip().lower()
    if not module_name:
        return False

    module_tail = module_name.split(".")[-1]
    module_short = module_tail.split("_")[-1]

    for addon_name in addon_names:
        name = str(addon_name).strip().lower()
        if not name:
            continue

        name_tail = name.split(".")[-1]
        if (
            module_name == name
            or module_name.endswith(f".{name}")
            or module_tail == name
            or module_tail == name_tail
            or module_short == name
            or module_short == name_tail
        ):
            return True

    return False


def is_addon_enabled(*addon_names):
    addons = getattr(getattr(bpy.context, "preferences", None), "addons", None)
    if addons is None:
        return False

    return any(_addon_name_matches(module_name, addon_names) for module_name in addons.keys())


def get_blender_key_icon(key_name):
    mapping = {
        'Ctrl': 'EVENT_CTRL',
        'Control': 'EVENT_CTRL',
        'Shift': 'EVENT_SHIFT',
        'Alt': 'EVENT_ALT',
        'D': 'EVENT_D',
        'X': 'EVENT_X',
        'Q': 'EVENT_Q',
        'E': 'EVENT_E',
        'H': 'EVENT_H',
        'M': 'EVENT_M',
        'C': 'EVENT_C',
        'W': 'EVENT_W',
        'S': 'EVENT_S',
        'Z': 'EVENT_Z',
        'SPACE': 'EVENT_SPACEKEY',
        'Esc': 'ESC',
        'ESC': 'ESC',
        'LMB': 'MOUSE_LMB',
        'RMB': 'MOUSE_RMB',
        'MMB': 'MOUSE_MMB',
    }
    return mapping.get(key_name, '')


def get_edit_mesh_tool_defs(context):
    tool_defs = []

    try:
        tools_class = ToolSelectPanelHelper._tool_class_from_space_type('VIEW_3D')
        if not tools_class or context is None:
            return tool_defs

        sig = inspect.signature(tools_class.tools_from_context)
        supports_mode_arg = "mode" in sig.parameters

        def collect_tools_from_context(ctx):
            if supports_mode_arg:
                toolbar_tools = tools_class.tools_from_context(ctx, mode='EDIT_MESH')
            else:
                toolbar_tools = tools_class.tools_from_context(ctx)

            for tool_def in ToolSelectPanelHelper._tools_flatten(toolbar_tools):
                tool_defs.append(tool_def)

        collect_tools_from_context(context)

        # If the current context is not suitable (e.g. preferences), try a VIEW_3D override.
        if not tool_defs:
            wm = context.window_manager
            for window in wm.windows:
                screen = window.screen
                if not screen:
                    continue

                for area in screen.areas:
                    if area.type != 'VIEW_3D':
                        continue

                    window_region = None
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            window_region = region
                            break

                    if window_region is None:
                        continue

                    with context.temp_override(window=window, area=area, region=window_region):
                        collect_tools_from_context(bpy.context)

                    if tool_defs:
                        break

                if tool_defs:
                    break
    except Exception:
        pass

    return tool_defs

def get_tool_icon_value(tool_id, context):
    if not tool_id:
        return 0

    for tool_def in get_edit_mesh_tool_defs(context):
        if getattr(tool_def, "idname", "") != tool_id:
            continue

        icon_handle = getattr(tool_def, "icon", None)
        if not icon_handle:
            return 0

        try:
            return ToolSelectPanelHelper._icon_value_from_icon_handle(icon_handle)
        except Exception:
            return 0

    return 0

def get_tool_display_name(tool_id, context):
    if not tool_id:
        return ""

    for tool_def in get_edit_mesh_tool_defs(context):
        if getattr(tool_def, "idname", "") != tool_id:
            continue

        label = getattr(tool_def, "label", "")
        if callable(label):
            try:
                label = label()
            except Exception:
                label = ""

        if label:
            return str(label)

    for tool_class in bpy.types.WorkSpaceTool.__subclasses__():
        if getattr(tool_class, "bl_idname", "") != tool_id:
            continue

        class_label = getattr(tool_class, "bl_label", "")
        if class_label:
            return str(class_label)

    readable_tail = tool_id.split(".")[-1]
    return readable_tail.replace("_", " ").title()

def get_obj_evaluated_data(obj, depsgraph=None): 
    if not depsgraph:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    eval_obj = obj.evaluated_get(depsgraph)
    m = eval_obj.to_mesh()
    return m


def get_layer_collection_by_name(name, _layer_collection=None): # function from https://b3d.interplanety.org/en/enabling-and-disabling-collections-by-object/
    if _layer_collection is None:
        _layer_collection = bpy.context.view_layer.layer_collection
    if _layer_collection.name == name:
        return _layer_collection
    else:
        for l_col in _layer_collection.children:
            if rez := get_layer_collection_by_name(name=name, _layer_collection=l_col):
                return rez

def get_is_in_local_view(): 
    local_view = False   
    active_view_3d = None
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            active_view_3d = area.spaces.active
            if active_view_3d.local_view:
                local_view = True
                break
    return local_view, active_view_3d

def force_show_obj(objs, select=True):
    for obj in objs:
        for col in obj.users_collection:
            l_col = get_layer_collection_by_name(col.name)
            if l_col.exclude == True or l_col.hide_viewport == True:
                l_col.exclude = False
                l_col.hide_viewport = False
                for obj in col.objects:
                    if obj.hide_get:
                        obj.hide_set(True)
                        
    is_isolate_mode, active_view_3d = get_is_in_local_view()
    
    selected_objs = []
    for obj in objs:
        if obj.hide_set:
            obj.hide_set(False)
        if obj.hide_viewport:
            obj.hide_viewport = False

        if select:
            obj.select_set(select)
            selected_objs.append(obj)

        if is_isolate_mode:
            if not obj.local_view_get(active_view_3d):
                (obj.local_view_set(active_view_3d, True))

    return selected_objs

def get_obj_coords(obj, depsgraph=None, worldspace=True):
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(obj.data)
        verts = [v for v in bm.verts if v.select] if obj.data.total_vert_sel else bm.verts
        if not verts:
            return None

        coords = np.empty((len(verts), 3), dtype=np.float64)
        for i, v in enumerate(verts):
            coords[i] = v.co
    else:
        mesh = get_obj_evaluated_data(obj, depsgraph=depsgraph)
        verts = mesh.vertices
        if not verts:
            return None

        coords = np.empty(len(verts) * 3, dtype=np.float64)
        verts.foreach_get("co", coords)
        coords = coords.reshape((-1, 3))

    if worldspace:
        mw = np.array(obj.matrix_world, dtype=np.float64)
        coords = coords @ mw[:3, :3].T + mw[:3, 3] # add matrix_world in bulk
    return coords

def np_get_bounds_from_coords(coords):
    min_corner = coords.min(axis=0)
    max_corner = coords.max(axis=0)
    return Vector(min_corner), Vector(max_corner)

def get_AABB_bounding_box_coords(objs):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    chunks = []  

    for obj in objs:
        verts = get_obj_coords(obj, depsgraph=depsgraph)  
        if verts is not None and verts.size:
            chunks.append(verts)

    if not chunks:
        return []

    world_coords = np.vstack(chunks)  
    objs = [objs[0]]

    for obj in objs:
        min_corner, max_corner = np_get_bounds_from_coords(world_coords)

        coords = [
            (min_corner.x, min_corner.y, min_corner.z),
            (min_corner.x, min_corner.y, max_corner.z),
            (min_corner.x, max_corner.y, min_corner.z),
            (min_corner.x, max_corner.y, max_corner.z),
            (max_corner.x, min_corner.y, min_corner.z),
            (max_corner.x, min_corner.y, max_corner.z),
            (max_corner.x, max_corner.y, min_corner.z),
            (max_corner.x, max_corner.y, max_corner.z),
        ]

    return coords

def select_loop():
    if BLENDER_VERSION >= (5, 1, 0):
        bpy.ops.mesh.select_edge_loop_multi()
    else:
        bpy.ops.mesh.loop_multi_select(ring=False)

def select_ring():
    if BLENDER_VERSION >= (5, 1, 0):
        bpy.ops.mesh.select_edge_ring_multi()
    else:
        bpy.ops.mesh.loop_multi_select(ring=True)

def add_shortcuts(list):
    wm = bpy.context.window_manager
    try:
        for keymap_name, idname, key, value, modifiers in list:
            km = wm.keyconfigs.active.keymaps[keymap_name]
            kmi = km.keymap_items.new(idname, key, value)
            
            if modifiers:
                for mod, enabled in modifiers.items():
                    setattr(kmi, mod, enabled)
    except KeyError as e:
        print(f"Error adding tablet navigation keymap: {e}")
        return

def remove_shortcuts(list):
    wm = bpy.context.window_manager

    try:
        for keymap_name, idname, key, value, modifiers in list:
            km = wm.keyconfigs.active.keymaps[keymap_name]
            items_to_remove = [
                kmi for kmi in km.keymap_items
                if kmi.idname == idname and kmi.type == key and kmi.value == value and all(
                    getattr(kmi, mod) == enabled for mod, enabled in modifiers.items()
                )
            ]
            for kmi in items_to_remove:
                km.keymap_items.remove(kmi)
    except KeyError as e:
        print(f"Error removing tablet navigation keymap: {e}")
        return
    
def set_shortcuts_active(list, set=False):
    wm = bpy.context.window_manager

    try:
        for keymap_name, idname, key, value, modifiers in list:
            km = wm.keyconfigs.active.keymaps[keymap_name]
            items_to_remove = [
                kmi for kmi in km.keymap_items
                if kmi.idname == idname and kmi.type == key and kmi.value == value and all(
                    getattr(kmi, mod) == enabled for mod, enabled in modifiers.items()
                )
            ]
            for kmi in items_to_remove:
                kmi.active = set
    except KeyError as e:
        print(f"Error disable tablet navigation keymap: {e}")
        return