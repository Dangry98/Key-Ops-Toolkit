import bpy

previes_shading_types_settings = []

class ViewportMenu(bpy.types.Operator):
    bl_idname = "keyops.viewport_menu"
    bl_label = "Viewport Overlays Menu"

    type: bpy.props.StringProperty(default='') # type: ignore

    def execute(self, context):
        global previes_shading_types_settings

        if self.type == 'toggle_silhouettes':
            view3d = context.space_data

            if not view3d.shading.light == 'FLAT':
                previes_shading_types_settings = [view3d.shading.show_object_outline, 
                                                  view3d.shading.show_xray, 
                                                  view3d.shading.show_backface_culling, 
                                                  view3d.shading.light, 
                                                  view3d.shading.background_type, 
                                                  view3d.overlay.show_overlays,
                                                  view3d.shading.type,
                                                  view3d.shading.background_color.copy(),
                                                  view3d.shading.show_cavity,
                                                  view3d.shading.show_shadows,
                                                  view3d.shading.show_xray,
                                                  view3d.shading.color_type,
                                                  view3d.shading.single_color]
                # silhouette settings
                view3d.shading.light = 'FLAT'
                view3d.shading.show_object_outline = False
                view3d.shading.background_type = 'VIEWPORT'
                view3d.overlay.show_overlays = False
                view3d.shading.type = 'SOLID'
                view3d.shading.background_color = (0, 0, 0)
                view3d.shading.show_cavity = False
                view3d.shading.show_shadows = False
                view3d.shading.show_xray = False
                view3d.shading.color_type = 'SINGLE'
                view3d.shading.single_color = (1, 1, 1)

            else:
                if previes_shading_types_settings:
                    # restore previous settings
                    view3d.shading.show_object_outline = previes_shading_types_settings[0]
                    view3d.shading.show_xray = previes_shading_types_settings[1]
                    view3d.shading.show_backface_culling = previes_shading_types_settings[2]
                    view3d.shading.light = previes_shading_types_settings[3]
                    view3d.shading.background_type = previes_shading_types_settings[4]
                    view3d.overlay.show_overlays = previes_shading_types_settings[5]
                    view3d.shading.type = previes_shading_types_settings[6]
                    view3d.shading.background_color = previes_shading_types_settings[7]
                    view3d.shading.show_cavity = previes_shading_types_settings[8]
                    view3d.shading.show_shadows = previes_shading_types_settings[9]
                    view3d.shading.show_xray = previes_shading_types_settings[10]
                    view3d.shading.color_type = previes_shading_types_settings[11]
                    view3d.shading.single_color = previes_shading_types_settings[12]
                    
                else:
                    # reset to default settings if no previous settings was found
                    view3d.shading.show_object_outline = True
                    view3d.shading.show_xray = False
                    view3d.shading.show_backface_culling = False
                    view3d.shading.light = 'STUDIO'
                    view3d.shading.background_type = 'THEME'
                    view3d.overlay.show_overlays = True
                    view3d.shading.type = 'SOLID'
                    view3d.shading.background_color = (0.05, 0.05, 0.05)
                  
                previes_shading_types_settings = []
        return {'FINISHED'}
        
    def register():
        bpy.utils.register_class(VIEW3D_MT_viewport_menu)
    def unregister():
        bpy.utils.unregister_class(VIEW3D_MT_viewport_menu)

class VIEW3D_MT_viewport_menu(bpy.types.Menu):
    bl_label = "Viewport Overlays"
    bl_idname = "VIEW3D_MT_viewport_menu"

    def draw(self, context):
        layout = self.layout
        view3d = context.space_data
        shading = view3d.shading
        
        split = layout.split(factor=0.5)
        
        # Left column
        col = split.column()
        col.prop(view3d.overlay, 'show_wireframes')
        col.prop(view3d.overlay, 'show_face_orientation')
        if view3d.shading.type == 'SOLID':
            col.prop(view3d.shading, 'show_object_outline')
        col.prop(view3d.overlay, "show_overlays", text = 'Overlays', emboss=True)
        
        # Right column
        col = split.column()
        icon = "SHADING_SOLID" if shading.light != 'FLAT' else "SHADING_RENDERED"
        col.operator('keyops.viewport_menu', text='Toggle Silhouette', icon=icon).type = 'toggle_silhouettes'

        if view3d.shading.type != 'WIREFRAME':
            col.template_icon_view(view3d.shading, "studio_light", show_labels=True, scale=3.5, scale_popup=4)
            # col.label(text='')

            # if view3d.shading.type == 'SOLID':
            #     col.prop(view3d.shading, "light", text="Test", expand=True)
