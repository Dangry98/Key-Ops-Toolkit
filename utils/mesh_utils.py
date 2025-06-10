
import bpy
import bmesh

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

def set_attribute_value_on_selection(obj=None, attr_name="", value=True, domain='POINT', data_type='BOOLEAN'):
    mesh = obj.data
    
    if attr_name and obj:
        attribute = mesh.attributes.get(attr_name)
        if attribute is None:
            attribute = mesh.attributes.new(name=attr_name, domain=domain, type=data_type)
        if obj.mode == 'EDIT':
            mesh = bpy.context.active_object.data
            attribute = mesh.attributes.new(name="new attribute", type="BOOLEAN", domain="POINT")
            attribute_values = [i for i in range(len(mesh.vertices))]

            bm = bmesh.from_edit_mesh(mesh)
            layer = bm.verts.layers.int.get(attr_name)

            for vert in bm.verts:
                print(f"Previous value for {vert} : {vert[layer]}")
                vert[layer] = attribute_values[vert.index]
                print(f"New value for {vert} : {vert[layer]}")

            bmesh.update_edit_mesh(mesh)
                        
