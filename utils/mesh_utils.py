
import bpy


def modifier_toggle_visability_based(visibility_modifier_dict_list={}):
    active_object_name = bpy.context.view_layer.objects.active.name

    if active_object_name not in visibility_modifier_dict_list:
        visibility_modifier_dict_list[active_object_name] = []

    visibility_modifier_list = visibility_modifier_dict_list[active_object_name]

    if len(visibility_modifier_list) <= 0:
        ml_act_ob = bpy.context.view_layer.objects.active
        for mod in ml_act_ob.modifiers:
            if mod.show_viewport:
                visibility_modifier_list.append(mod)
                mod.show_viewport = False
    else:
        ml_act_ob = bpy.context.view_layer.objects.active
        hidden_modifiers = []
        for mod in ml_act_ob.modifiers:
            if mod in visibility_modifier_list:
                mod.show_viewport = True
                hidden_modifiers.append(mod)
        visibility_modifier_list = [mod for mod in visibility_modifier_list if mod not in hidden_modifiers]
        visibility_modifier_dict_list[active_object_name] = visibility_modifier_list
