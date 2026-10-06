import bpy.types
from ..utils.pref_utils import clear_registered_keymaps

registered_legacy_shortcuts_keymaps = []

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

def register_legacy_shortcuts():
    register_legacy_shortcuts_keymaps()

def unregister_legacy_shortcuts():
    clear_registered_keymaps(registered_legacy_shortcuts_keymaps)

    
