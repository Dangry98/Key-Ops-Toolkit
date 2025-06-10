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

from .addon_preferences import KeyOpsPreferences
from .operators.rebind import Rebind
from .utils.register_extensions import get_extension, register_classes, unregister_classes, register_keymaps, unregister_keymaps
from .utils.pref_utils import register_icons, unregister_icons 
from .ui.toolkit_paneL_ui import NewToolkitPanel

default_classes = [KeyOpsPreferences,Rebind, NewToolkitPanel]
debug = False

if 'bpy' in locals():
    import os
    import importlib

    for cls in default_classes:
        importlib.reload(cls)
    
    from . import classes_keymap_items

    for module in [classes_keymap_items]:
        importlib.reload(module)

    utils_modules = sorted([name[:-3] for name in os.listdir(os.path.join(__path__[0], "utils")) if name.endswith('.py')])

    for module in utils_modules:
        impline = f"from . utils import {module}"

        if debug:
            print(f"reloading {__package__}.utils.{module}")

        exec(impline)
        importlib.reload(eval(module))

    modules = []

    for label in classes_keymap_items.classes:
        entries = classes_keymap_items.classes[label]
        for entry in entries:
            path = entry[0].split('.')
            module = path.pop(-1)

            if (path, module) not in modules:
                modules.append((path, module))

    for path, module in modules:
        if path:
            impline = f"from . {'.'.join(path)} import {module}"
        else:
            impline = f"from . import {module}"

        if debug:
            print(f"reloading {__package__}.{'.'.join(path)}.{module}")

        exec(impline)
        importlib.reload(eval(module))

import bpy

def register():
    global classes, keymaps, default_classes, icons

    if debug:
        import time 
        addon_start_time = time.time()

    icons = register_icons()
    
    # Register default classes
    for cls in default_classes:
        bpy.utils.register_class(cls)

    # Get extension classes and keymaps
    extension_classlists, extension_keylists = get_extension()

    # Register extension classes
    classes = register_classes(extension_classlists)

    # Register extension keymaps
    keymaps = register_keymaps(extension_keylists)
    if debug:
            print(f"{__package__} addon registered in {time.time() - addon_start_time:.4f} seconds")


    #print all addons names that are enabled
    # for addon in bpy.context.preferences.addons:
    #     print(addon.module)        

def unregister():
    for cls in default_classes:
        bpy.utils.unregister_class(cls)
 
    global classes, keymaps, icons
    unregister_keymaps(keymaps)
    unregister_classes(classes)

    classes, keymaps = None, None

    unregister_icons(icons)
