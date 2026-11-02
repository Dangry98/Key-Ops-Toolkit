import bpy
import rna_keymap_ui
import os
from bpy.utils import previews
from .. import __package__ as base_package

# Runtime keymap display registry built from extension registration globals.
registered_keymap_display_items = {}

def get_is_addon_enabled(addon_name):
    list_of_addons = bpy.context.preferences.addons.keys()
    list_of_addons = [addon.split(".")[-1] for addon in list_of_addons]
    return addon_name in list_of_addons

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

def get_addon_path(addon_name):
    for addon in bpy.context.preferences.addons:
        if str(addon_name) in addon.module:
            return addon.module
        
def get_addon_preferences(addon_name):
    name = get_addon_path(addon_name)
    if not name:
        return KeyOpsPrefsMock()
    return bpy.context.preferences.addons.get(str(name), KeyOpsPrefsMock())


def unregister_keymaps(keymaps):
    for km, kmi in keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass


def clear_registered_keymaps(registered_keymaps):
    unregister_keymaps(registered_keymaps)
    registered_keymaps.clear()


def _normalize_keymap_group_name(variable_name):
    name = variable_name
    if name.startswith("registered_"):
        name = name[len("registered_"):]
    if name.endswith("_keymaps"):
        name = name[:-len("_keymaps")]
    return name.upper()


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


def _iter_registered_keymap_sources():
    from ..menu import pies as pies_module
    from ..operators import add_mesh as add_mesh_module
    from ..operators import add_modifier as add_modifier_module
    from ..operators import auto_delete as auto_delete_module
    from ..operators import double_click_select_island as double_click_select_island_module
    from ..operators import fast_merge as fast_merge_module
    from ..operators import legacy_shortcuts as legacy_shortcuts_module
    from ..operators import material_index as material_index_module
    from ..operators import maya_navigation as maya_navigation_module
    from ..operators import maya_pivot as maya_pivot_module
    from ..operators import modi_key as modi_key_module
    from ..operators import origin_to_selection as origin_to_selection_module
    from ..operators import quick_export as quick_export_module
    from ..operators import toggle_retopology as toggle_retopology_module
    from ..operators import toolkit_panel as toolkit_panel_module
    from ..operators import uv_tools as uv_tools_module
    from ..operators import viewport_menu as viewport_menu_module

    sources = [
        (pies_module, (
            "registered_workspace_pie_keymaps",
            "registered_uv_pies_keymaps",
            "registered_utility_pie_keymaps",
        )),
        (add_mesh_module, ("registered_add_objects_pie_keymaps",)),
        (add_modifier_module, ("registered_add_modifier_pie_keymaps",)),
        (auto_delete_module, ("registered_auto_delete_keymaps",)),
        (double_click_select_island_module, ("registered_double_click_select_island_keymaps",)),
        (fast_merge_module, ("registered_fast_merge_keymaps",)),
        (legacy_shortcuts_module, ("registered_legacy_shortcuts_keymaps",)),
        (material_index_module, ("registered_material_index_keymaps",)),
        (maya_navigation_module, ("registered_maya_navigation_keymaps",)),
        (maya_pivot_module, ("registered_maya_pivot_keymaps",)),
        (modi_key_module, ("registered_modi_key_keymaps",)),
        (origin_to_selection_module, ("registered_cursor_pie_keymaps",)),
        (quick_export_module, ("registered_quick_export_keymaps",)),
        (toggle_retopology_module, ("registered_toggle_retopology_keymaps",)),
        (toolkit_panel_module, ("registered_toolkit_panel_keymaps",)),
        (uv_tools_module, ("registered_uv_tools_keymaps",)),
        (viewport_menu_module, ("registered_viewport_menu_keymaps",)),
    ]

    return [
        (name, getattr(module, name, []))
        for module, names in sources
        for name in names
    ]


def rebuild_registered_keymap_display_items():
    global registered_keymap_display_items
    registered_keymap_display_items = {}

    for var_name, value in _iter_registered_keymap_sources():
        if not isinstance(value, list) or not value:
            continue

        group_name = _normalize_keymap_group_name(var_name)
        display_items = registered_keymap_display_items.setdefault(group_name, [])

        for pair in value:
            if not isinstance(pair, tuple) or len(pair) != 2:
                continue
            km, kmi = pair
            if km is None or kmi is None:
                continue
            display_items.append(_keymap_item_to_display_item(km, kmi))

    return registered_keymap_display_items


def get_registered_keymap_display_items():
    return rebuild_registered_keymap_display_items()


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

    if name == "K":
        hacky_icon_fix = str(icon.icon_pixels) # reliable hack to fix diseparing icons bug, weird this works?? Must be reloading them in some way? Please do not change!

    return icon

