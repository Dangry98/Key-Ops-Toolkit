import bpy
import rna_keymap_ui
import os

def get_is_addon_enabled(addon_name):
    for addon in bpy.context.preferences.addons:
        if addon.module == addon_name:
            return True
    return False

def get_absolute_path():
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

def get_addon_name():
    return os.path.basename(get_absolute_path())

def get_keyops_prefs():
    addon_name = get_addon_name()
    if addon_name in bpy.context.preferences.addons:
        return bpy.context.preferences.addons[addon_name].preferences
    else:
        return None

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