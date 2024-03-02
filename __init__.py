# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ***** END GPL LICENSE BLOCK *****

bl_info = {
    "name": "Key Ops: Toolkit",
    "author": "DanGry, MACHIN3",
    "version": (0, 1, 70),
    "blender": (4, 0, 0),
    "description": "Adds new tools, shortcuts and operations to Blender",
    "category": "3D View"
}

#The following code is based on the MACHIN3 addon: MACHIN3tools
#Check out there awesome addons here: https://machin3.io/
from .utils.register_extensions import get_extension, register_classes, unregister_classes, register_keymaps, unregister_keymaps
import time 
from .addon_preferences import KeyOpsPreferences
from .operators.rebind import Rebind
from .operators.auto_smooth import AutoSmooth
import bpy

def register():
    debug = True
    global classes, keymaps

    if debug:
        addon_start_time = time.time()

    #default classes
    default_classes_start_time = time.time()
    if bpy.app.version <= (4, 1, 0):
        bpy.utils.register_class(KeyOpsPreferences)
    bpy.utils.register_class(Rebind)
    bpy.utils.register_class(AutoSmooth)
    if debug:
        print(f"registering default classes took {time.time() - default_classes_start_time:.4f} seconds")

    get_extension_time = time.time()
    extension_classlists, extension_keylists = get_extension()
    if debug:
        print(f"get_extension() took {time.time() - get_extension_time:.4f} seconds")

    register_classes_time = time.time()
    classes = register_classes(extension_classlists)
    if debug:
        print(f"register_classes() took {time.time() - register_classes_time:.4f} seconds")

    register_keymaps_time = time.time()
    keymaps = register_keymaps(extension_keylists)
    if debug:
        print(f"register_keymaps() took {time.time() - register_keymaps_time:.4f} seconds")
        print(f"{bl_info['name']} addon registered in {time.time() - addon_start_time:.4f} seconds")

def unregister():
    bpy.utils.unregister_class(KeyOpsPreferences)
    bpy.utils.unregister_class(Rebind)
    bpy.utils.unregister_class(AutoSmooth)

    global classes, keymaps
    unregister_keymaps(keymaps)
    unregister_classes(classes)
