"""Headless checks for Snap to Floor's Snap to Surface option.

Run: powershell -ExecutionPolicy Bypass -File scripts/test.ps1 -Tests tests/test_snap_surface.py
"""

import sys
import addon_utils
import bpy

MOD = "bl_ext.user_default.Key_Ops_Toolkit"
addon_utils.enable(MOD, default_set=True)
ok = True

def check(name, cond, detail=""):
    global ok
    ok = ok and cond
    print(("PASS " if cond else "FAIL ") + name + f"  [{detail}]")

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)

bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 2))
ground = bpy.context.active_object
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 8))
cube = bpy.context.active_object
bpy.ops.mesh.primitive_cube_add(size=2, location=(20, 0, 8))
far = bpy.context.active_object

def select(*objs):
    for o in bpy.data.objects:
        o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]

select(cube)
bpy.ops.keyops.snap_to_floor('EXEC_DEFAULT', to_surface=True)
check("cube lands on plane", abs(cube.location.z - 3.0) < 1e-3, cube.location.z)

select(far)
bpy.ops.keyops.snap_to_floor('EXEC_DEFAULT', to_surface=True)
check("no surface falls back to floor", abs(far.location.z - 1.0) < 1e-3, far.location.z)

cube.location.z = 8
far.location.z = 8
select(cube, far)
bpy.ops.keyops.snap_to_floor('EXEC_DEFAULT', to_surface=True, individual=True)
check("individual", abs(cube.location.z - 3.0) < 1e-3 and abs(far.location.z - 1.0) < 1e-3,
      (cube.location.z, far.location.z))

cube.location.z = 8
select(cube)
bpy.ops.keyops.snap_to_floor('EXEC_DEFAULT', to_surface=False)
check("default grid floor unchanged", abs(cube.location.z - 1.0) < 1e-3, cube.location.z)

sys.exit(0 if ok else 1)
