import bpy.types
from ..utils.pref_utils import clear_registered_keymaps
# old useful leagacy shortcuts that are no longer in Blender but still useful to have. Optional enable in the addon preferences

registered_legacy_shortcuts_keymaps = []
registered_legacy_collection_shortcuts_keymaps = []

def register_legacy_shortcuts_keymaps():
    global registered_legacy_shortcuts_keymaps
    wm = bpy.context.window_manager

    km = wm.keyconfigs.addon.keymaps.new(name='Mesh', space_type='EMPTY')
    kmi = km.keymap_items.new('mesh.poke', 'P', 'PRESS', alt=True)
    registered_legacy_shortcuts_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('mesh.select_more', 'GRLESS', 'PRESS', repeat=True)
    registered_legacy_shortcuts_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('mesh.select_less', 'GRLESS', 'PRESS', shift=True, repeat=True)
    registered_legacy_shortcuts_keymaps.append((km, kmi))

    km = wm.keyconfigs.addon.keymaps.new(name='UV Editor', space_type='EMPTY')
    kmi = km.keymap_items.new('uv.average_islands_scale', 'A', 'PRESS', ctrl=True)
    registered_legacy_shortcuts_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('uv.pack_islands', 'P', 'PRESS', ctrl=True)
    registered_legacy_shortcuts_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('uv.copy', 'C', 'PRESS', ctrl=True)
    registered_legacy_shortcuts_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('uv.paste', 'V', 'PRESS', ctrl=True)
    registered_legacy_shortcuts_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('mesh.select_more', 'GRLESS', 'PRESS', repeat=True)
    registered_legacy_shortcuts_keymaps.append((km, kmi))

    kmi = km.keymap_items.new('mesh.select_less', 'GRLESS', 'PRESS', shift=True, repeat=True)
    registered_legacy_shortcuts_keymaps.append((km, kmi))

NUMBERS_1 = ('ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE', 'ZERO')


def register_legacy_collection_shortcuts():
    if bpy.app.version < (5, 0, 0):
        return
    add_legacy_collection_shortcuts()


def add_legacy_collection_shortcuts():
    global registered_legacy_collection_shortcuts_keymaps

    if bpy.app.version < (5, 0, 0):
        return

    clear_registered_keymaps(registered_legacy_collection_shortcuts_keymaps)

    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(
        name='Object Mode',
        space_type='EMPTY',
        region_type='WINDOW',
    )

    for item_name, item_data in _template_object_hide_collection_from_number_keys():
        item_kwargs = {
            key: value
            for key, value in item_data.items()
            if key not in {"type", "value", "properties"}
        }
        kmi = km.keymap_items.new(
            item_name,
            item_data["type"],
            item_data["value"],
            **item_kwargs,
        )

        for prop_name, prop_value in item_data.get("properties", {}).items():
            setattr(kmi.properties, prop_name, prop_value)

        registered_legacy_collection_shortcuts_keymaps.append((km, kmi))


def _template_object_hide_collection_from_number_keys():
    items = []
    for extend in (False, True):
        for add_10 in (False, True):
            for i in range(10):
                data = {
                    "type": NUMBERS_1[i],
                    "value": 'PRESS',
                    "properties": {
                        "collection_index": i + (11 if add_10 else 1),
                        "extend": extend,
                    },
                }
                if extend:
                    data["shift"] = True
                if add_10:
                    data["alt"] = True
                items.append(("object.hide_collection", data))
    return items


def unregister_legacy_shortcuts():
    clear_registered_keymaps(registered_legacy_shortcuts_keymaps)


def unregister_legacy_collection_shortcuts():
    clear_registered_keymaps(registered_legacy_collection_shortcuts_keymaps)

    
