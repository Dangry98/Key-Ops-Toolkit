#The following code is based on the MACHIN3 addon: MACHIN3tools
#Check out there awesome addons here: https://machin3.io/   

def unregister_keymaps(keymaps):
    global unregister_idnames
    for km, kmi in keymaps:
        try:
            km.keymap_items.remove(kmi)
        except:
            pass

def clear_registered_keymaps(registered_keymaps):
    unregister_keymaps(registered_keymaps)
    registered_keymaps.clear()