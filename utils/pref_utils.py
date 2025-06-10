import bpy
import rna_keymap_ui
import os
from bpy.utils import previews
from .. import __package__ as base_package

def get_is_addon_enabled(addon_name):
    list_of_addons = bpy.context.preferences.addons.keys()
    list_of_addons = [addon.split(".")[-1] for addon in list_of_addons]
    return addon_name in list_of_addons

def get_addon_name():
    return base_package

def get_keyops_prefs():
    addon_prefs = bpy.context.preferences.addons[base_package]
    return addon_prefs.preferences

def get_addon_path(addon_name):
    for addon in bpy.context.preferences.addons:
        if str(addon_name) in addon.module:
            return addon.module
        
def get_addon_preferences(addon_name):
    name = get_addon_path(addon_name)
    return bpy.context.preferences.addons[str(name)]

#The following code is based on the MACHIN3 addon: MACHIN3tools
#Check out there awesome addons here: https://machin3.io/
def draw_keymap(key_config, name, key_list, layout):
    drawn = []
    index = 0

    for item in key_list:
        is_drawn = False

        if item.get("keymap"):
            key_map = key_config.keymaps.get(item.get("keymap"))

            key_map_item = None
            if key_map:
                id_name = item.get("idname")
                for km_item in key_map.keymap_items:
                    if km_item.idname == id_name:
                        properties = item.get("properties")
                        if properties:
                            if all([getattr(km_item.properties, name, None) == value for name, value in properties]):
                                key_map_item = km_item
                                break
                        else:
                            key_map_item = km_item
                            break
            if key_map_item:
                if index == 0:
                    box = layout.box()

                if len(key_list) == 1:
                    label = name.title().replace("_", " ")
                else:
                    if index == 0:
                        box.label(text=name.title().replace("_", " "))

                    label = item.get("label")

                row = box.split(factor=0.15)
                row.label(text=label)

                rna_keymap_ui.draw_kmi(["ADDON", "USER", "DEFAULT"], key_config, key_map, key_map_item, row, 0)

                is_drawn = True
                index += 1

        drawn.append(is_drawn)
    return drawn

def register_icons():
    path = os.path.join(os.path.dirname(__file__), "..", "icons")
    icons = previews.new()
    for i in sorted(os.listdir(path)):
        if i.endswith(".png"):
            iconname = i[:-4]
            filepath = os.path.join(path, i)
            icons.load(iconname, filepath, 'IMAGE')
    return icons

def unregister_icons(icons):
    previews.remove(icons)

icons = None

def get_icon(name):
    global icons

    if not icons:
        from .. import icons
    
    return icons[name].icon_id