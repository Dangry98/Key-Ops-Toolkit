import bpy.types
from ..classes_keymap_items import classes as classesdict
from ..classes_keymap_items import keymap_items as keysdict
from bpy.utils import register_class, unregister_class
from ..utils.pref_utils import get_keyops_prefs
import importlib

#The following code is based on the MACHIN3 addon: MACHIN3tools
#Check out there awesome addons here: https://machin3.io/   

def register_classes(classlists):
    classes = [getattr(importlib.import_module("..{}".format(fr), package=__package__), imp[0]) for classlist in classlists for fr, imps in classlist for imp in imps]

    for cls in classes:
        register_class(cls)
    return classes

def unregister_classes(classes):
    for cls in classes:
        unregister_class(cls)

def get_classes(classlist):
    classes = []

    for fr, imps in classlist:
        type = "OT" if "operators" in fr else "MT"
        classes.extend(getattr(bpy.types, f"KEYOPS_{type}_{imp[1]}", False) for imp in imps)
    return classes

def register_keymaps(keylists):
    keymaps = []

    for keylist in keylists:
        for item in keylist:
            keymap = item.get("keymap")
            space_type = item.get("space_type", "EMPTY")

            if keymap and (km := bpy.context.window_manager.keyconfigs.addon.keymaps.new(name=keymap, space_type=space_type)):
                idname = item.get("idname")
                type = item.get("type")
                value = item.get("value")
                repeat = item.get("repeat", False)
                ctrl = item.get("ctrl", False)
                shift = item.get("shift", False)
                alt = item.get("alt", False)

                if (kmi := km.keymap_items.new(idname, type, value, repeat=repeat, shift=shift, ctrl=ctrl, alt=alt)):
                    properties = item.get("properties")

                    if properties:
                        for name, value in properties:
                            setattr(kmi.properties, name, value)
                    keymaps.append((km, kmi))
    return keymaps

def unregister_keymaps(keymaps):
    for km, kmi in keymaps:
        km.keymap_items.remove(kmi)

def get_keymaps(keylist):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    keymaps = []

    for item in keylist:
        keymap = item.get("keymap")

        if keymap:
            km = kc.keymaps.get(keymap)

            if km:
                idname = item.get("idname")

                for kmi in km.keymap_items:
                    if kmi.idname == idname:
                        properties = item.get("properties")

                        if properties:
                            if all([getattr(kmi.properties, name, None) == value for name, value in properties]):
                                keymaps.append((km, kmi))

                        else:
                            keymaps.append((km, kmi))
    return keymaps

def enable_extension(self, register, extension):
    name = extension.replace("_", " ").title()
    debug = False

    if register:
        classlist, keylist = eval("get_%s()" % extension)
        classes = register_classes(classlist)

        from .. import classes as default_classes

        for c in classes:
            if c not in default_classes:
                default_classes.append(c)

        keymaps = register_keymaps(keylist)

        from .. import keymaps as default_keymaps
        for k in keymaps:
            if k not in default_keymaps:
                default_keymaps.append(k)

        if debug:
            if classes:
                print("Registered KEYOPStools' %s" % (name))

        classlist.clear()
        keylist.clear()

    else:
        keylist = keysdict.get(extension.upper())

        if keylist:
            keymaps = get_keymaps(keylist)

            from .. import keymaps as default_keymaps
            for k in keymaps:
                if k in default_keymaps:
                    default_keymaps.remove(k)

            unregister_keymaps(keymaps)

        classlist = classesdict[extension.upper()]
        classes = get_classes(classlist)

        from .. import classes as default_classes

        for c in classes:
            if c in default_classes:
                default_classes.remove(c)


        unregister_classes(classes)

        if debug:
            if classes:
                print("Unregistered KEYOPStools' %s" % (name))

def operator(operator_name):
    def decorator(func):
        def wrapper(classlists=[], keylists=[]):
            if getattr(get_keyops_prefs(), f"enable_{operator_name.lower().replace(' ', '_')}"):
                operator_class = classesdict[operator_name.upper().replace(' ', '_')]
                operator_key = keysdict.get(operator_name.upper().replace(' ', '_'), None)
                classlists.append(operator_class)
                if operator_key:
                    keylists.append(operator_key)
            return classlists, keylists
        return wrapper
    return decorator

def get_extension():
    functions = [
                 get_auto_delete,
                 get_toggle_retopology,
                 get_maya_pivot,
                 get_maya_navigation,
                 get_maya_shortcuts,
                 get_double_click_select_island,
                 get_smart_seam,
                 get_uv_tools,
                 get_add_objects_pie,
                 get_view_camera_pie,
                 get_add_modifier_pie,
                 get_workspace_pie,
                 get_cursor_pie,
                 get_legacy_shortcuts,
                 get_fast_merge,
                 get_modi_key,
                 get_uv_pies,
                 get_utility_pie,
                 get_cad_decimate,
                 get_auto_lod,
                 get_polycount_list,
                 get_utilities_panel_op,
                 get_quick_bake_name,
                 get_quick_export,
                 get_atri_op,
                 get_material_index,
]
    classlists, keylists = [], []
    for func in functions:
        classlists, keylists = func(classlists, keylists)
    return classlists, keylists


@operator("Auto Delete")
def get_auto_delete(): pass

@operator("Toggle Retopology")
def get_toggle_retopology(): pass

@operator("Maya Pivot")
def get_maya_pivot(): pass

@operator("Maya Navigation")
def get_maya_navigation(): pass

@operator("Maya Shortcuts")
def get_maya_shortcuts(): pass

@operator("Double Click Select Island")
def get_double_click_select_island(): pass

@operator("Smart Seam")
def get_smart_seam(): pass

@operator("UV Tools")
def get_uv_tools(): pass

@operator("Add Objects Pie")
def get_add_objects_pie(): pass

@operator("View Camera Pie")
def get_view_camera_pie(): pass

@operator("Add Modifier Pie")
def get_add_modifier_pie(): pass

@operator("Workspace Pie")
def get_workspace_pie(): pass

@operator("Legacy Shortcuts")
def get_legacy_shortcuts(): pass

@operator("Cursor Pie")
def get_cursor_pie(): pass

@operator("Fast Merge")
def get_fast_merge(): pass

@operator("Modi Key")
def get_modi_key(): pass

@operator("UV Pies")
def get_uv_pies(): pass

@operator("Utility Pie")
def get_utility_pie(): pass

@operator("CAD Decimate")
def get_cad_decimate(): pass

@operator("Auto LOD")
def get_auto_lod(): pass

@operator("Polycount List")
def get_polycount_list(): pass

@operator("Utilities Panel OP")
def get_utilities_panel_op(): pass

@operator("Quick Bake Name")
def get_quick_bake_name(): pass

@operator("Quick Export")
def get_quick_export(): pass

@operator("Atri OP")
def get_atri_op(): pass

@operator("Material Index")
def get_material_index(): pass