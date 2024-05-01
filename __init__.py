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
    "author": "Dan Gry, MACHIN3",
    "version": (0, 1, 83),
    "blender": (4, 0, 0),
    "description": "Adds new tools, shortcuts and operations to Blender",
    "category": "3D View"
}

#The following code is based on the MACHIN3 addon: MACHIN3tools
#Check out there awesome addons here: https://machin3.io/

#reload modules if the addon is updated, does not work for some reason :(
# def reload_modules(name):
#     import bpy
#     import os
#     import importlib
#     from . import classes_keymap_items
#     global default_classes

#     print("reloading", "default_classes")
#     for cls in default_classes:
#         bpy.utils.register_class(cls)

#     utils_modules = sorted([name[:-3] for name in os.listdir(os.path.join(__path__[0], "utils")) if name.endswith('.py')])

#     for module in utils_modules:
#         impline = "from . utils import %s" % (module)

#         print("reloading %s" % (".".join([name] + ['utils'] + [module])))

#         exec(impline)
#         importlib.reload(eval(module))

#     for module in [classes_keymap_items]:
#         print("reloading", module.__name__)
#         importlib.reload(module)


#     modules = []

#     for label in classes_keymap_items.classes:
#         entries = classes_keymap_items.classes[label]
#         for entry in entries:
#             path = entry[0].split('.')
#             module = path.pop(-1)

#             if (path, module) not in modules:
#                 modules.append((path, module))

#     for path, module in modules:
#         if path:
#             impline = "from . %s import %s" % (".".join(path), module)
#         else:
#             impline = "from . import %s" % (module)

#         print("reloading %s" % (".".join([name] + path + [module])))

#         exec(impline)
#         importlib.reload(eval(module))

from .addon_preferences import KeyOpsPreferences
from .operators.rebind import Rebind
from .operators.auto_smooth import AutoSmooth
#from .operators.extrude_edge_along_normals import ExtrudeEdgeAlongNormals

# if 'bpy' in locals():
#     reload_modules(bl_info['name'])

import bpy
from .utils.register_extensions import get_extension, register_classes, unregister_classes, register_keymaps, unregister_keymaps
import time 

default_classes = [
    KeyOpsPreferences,
    Rebind,
]
if bpy.app.version >= (4, 1, 0):
    default_classes.append(AutoSmooth)

def register():
    debug = False
    global classes, keymaps
    global default_classes

    if debug:
        addon_start_time = time.time()

    # Register default classes
    if debug:            
        default_classes_start_time = time.time()
    for cls in default_classes:
        bpy.utils.register_class(cls)
    if debug:
        print(f"registering default classes took {time.time() - default_classes_start_time:.4f} seconds")

    # Get extension classes and keymaps
    if debug:
        get_extension_time = time.time()
    extension_classlists, extension_keylists = get_extension()
    if debug:
        print(f"get_extension() took {time.time() - get_extension_time:.4f} seconds")

    # Register extension classes
    if debug:
        register_classes_time = time.time()
    classes = register_classes(extension_classlists)
    if debug:
        print(f"register_classes() took {time.time() - register_classes_time:.4f} seconds")

    # Register extension keymaps
    if debug:
        register_keymaps_time = time.time()
    keymaps = register_keymaps(extension_keylists)
    if debug:
        print(f"register_keymaps() took {time.time() - register_keymaps_time:.4f} seconds")
        print(f"{bl_info['name']} addon registered in {time.time() - addon_start_time:.4f} seconds")

def unregister():
    for cls in default_classes:
        bpy.utils.unregister_class(cls)
 
    global classes, keymaps
    unregister_keymaps(keymaps)
    unregister_classes(classes)

    classes, keymaps = None, None
