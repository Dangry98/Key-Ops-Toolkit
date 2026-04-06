import bpy, bmesh
import numpy as np # type: ignore
from mathutils import Matrix, Vector
from .pref_utils import get_is_addon_enabled

BLENDER_VERSION = bpy.app.version

def get_obj_evaluated_data(obj, depsgraph=None): 
    if not depsgraph:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    eval_obj = obj.evaluated_get(depsgraph)
    m = eval_obj.to_mesh()
    return m

def force_show_obj(context, obj, select=True):
    obj_collection = obj.users_collection[0]

    if obj_collection.hide_viewport == True or context.view_layer.layer_collection.children[obj_collection.name].hide_viewport == True:
        obj_collection.hide_viewport = False
        context.view_layer.layer_collection.children[obj_collection.name].hide_viewport = False
        for obj in obj_collection.objects:
            if not obj.hide_get():
                obj.hide_set(True)
    
    if obj.hide_set:
        obj.hide_set(False)
    if obj.hide_viewport:
        obj.hide_viewport = False
    if select:
        obj.select_set(True)
        context.view_layer.objects.active = obj

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

MESH_OBJECT_TYPES = ["MESH", "CURVE", "FONT"]

def is_object_mesh(obj):
    return obj.type in MESH_OBJECT_TYPES


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

def is_set_edge_flow_installed():
    if get_is_addon_enabled("EdgeFlow-blender_28") or get_is_addon_enabled("EdgeFlow"):
        return True
    else:
        bpy.ops.keyops.toolkit_panel("INVOKE_DEFAULT", type="operation_missing", addon_id="EdgeFlow")
        return False

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