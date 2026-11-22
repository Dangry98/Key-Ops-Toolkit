import bpy
import rna_keymap_ui
import os
from bpy.utils import previews
from .. import __package__ as base_package

def get_addon_name():
    return base_package

class KeyOpsPrefsMock:
    def __getattr__(self, name):
        return False

def get_keyops_prefs():
    if not hasattr(bpy.context, "preferences"):
        return KeyOpsPrefsMock()

    addons = bpy.context.preferences.addons

    if base_package in addons:
        return addons[base_package].preferences

    addon_id = base_package.split(".")[-1]
    for name, addon in addons.items():
        if name == addon_id or name.endswith(f".{addon_id}"):
            return addon.preferences

    return KeyOpsPrefsMock()

def unregister_keymaps(keymaps):
    for km, kmi in keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass


def clear_registered_keymaps(registered_keymaps):
    unregister_keymaps(registered_keymaps)
    registered_keymaps.clear()


def _keymap_item_to_display_item(km, kmi):
    item = {
        "label": getattr(kmi, "name", ""),
        "keymap": getattr(km, "name", ""),
        "idname": getattr(kmi, "idname", ""),
        "type": getattr(kmi, "type", "NONE"),
        "value": getattr(kmi, "value", "PRESS"),
    }

    for attr in ("ctrl", "shift", "alt", "oskey", "repeat"):
        value = getattr(kmi, attr, False)
        if value:
            item[attr] = value

    properties = []
    props = getattr(kmi, "properties", None)
    if props and hasattr(props, "bl_rna") and hasattr(props, "is_property_set"):
        for prop in props.bl_rna.properties:
            identifier = getattr(prop, "identifier", None)
            if not identifier or identifier == "rna_type":
                continue
            if props.is_property_set(identifier):
                properties.append((identifier, getattr(props, identifier)))

    if properties:
        item["properties"] = properties

    return item


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

icons_collection = None
icons_directory = os.path.join(os.path.dirname(__file__), "..", "icons")


def register_icons():
    global icons_collection
    if icons_collection is None:
        icons_collection = bpy.utils.previews.new()  # hack needed for Blender 5.2 + for some reason we can not do it in register() anymore, gives errors
    return icons_collection


def unregister_icons(collection=None):
    global icons_collection
    if collection is None:
        collection = icons_collection

    if collection is None:
        return

    try:
        bpy.utils.previews.remove(collection)
    except KeyError:
        pass
    finally:
        if icons_collection is collection:
            icons_collection = None


def get_icon(name):
    return get_icon_data(name).icon_id


def get_icon_data(name):
    global icons_collection
    if icons_collection is None:
        register_icons()

    if name in icons_collection:
        return icons_collection[name]

    icon = icons_collection.load(name, os.path.join(icons_directory, name + ".png"), "IMAGE")
    load_icon_now(icon)
    return icon


def load_icon_now(icon):
    """Previews load their image later, the first time they are drawn. An icon first drawn while a
    file is loading can stay empty. Reading its pixels loads the image straight away, so it always shows."""
    icon.icon_pixels[0:1]

