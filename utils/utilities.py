import bpy, bmesh
import numpy as np # type: ignore
from mathutils import Matrix, Vector

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