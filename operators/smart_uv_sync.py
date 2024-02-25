import bmesh
import bpy
from ..utils.pref_utils import get_keyops_prefs

#Based on the code from the excellent addon UV Toolkit by Alex Dev that is sadly no longer available, please come back Alex! :( 
#Only an very old version is still available, but I doubt it still works in new version of Blender  https://alexbel.gumroad.com/l/NbMya
#The Toggle UV sync was an serverly underrated operation that basically fixes the uv editor in Blender, and I wanted to highlight its importance and keep it alive since its no longer officaly available anywhere. 
#Its the only way to get the UV editor in Blender to not be a horrible slow mess to work in and its a must have for anyone who works with UVs.

class SmartUVSync(bpy.types.Operator):
    bl_idname = "keyops.smart_uv_sync"
    bl_label = "KeyOps: Smart UV Sync"
    bl_description = "Right Click to Toggle Sync Mode and UV Selection"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'
    
    def fast_sync(self, context):
        if bpy.context.scene.tool_settings.use_uv_select_sync:
            bpy.context.scene.tool_settings.use_uv_select_sync = True
        else:
            bpy.context.scene.tool_settings.use_uv_select_sync = False
            bpy.ops.mesh.select_all(action='SELECT')

    def sync_uv_selction_mode(self, context, uv_sync_enable):
        scene = context.scene

        vertex = True, False, False
        edge = False, True, False
        face = False, False, True

        if uv_sync_enable:
            uv_select_mode = scene.tool_settings.uv_select_mode
            tool_settings = context.tool_settings

            if uv_select_mode == 'VERTEX':
                tool_settings.mesh_select_mode = vertex
            if uv_select_mode == 'EDGE':
                tool_settings.mesh_select_mode = edge
            if uv_select_mode == 'FACE':
                tool_settings.mesh_select_mode = face

        else:
            mesh_select_mode = context.tool_settings.mesh_select_mode[:]
            tool_settings = scene.tool_settings

            if mesh_select_mode == vertex:
                tool_settings.uv_select_mode = 'VERTEX'
            if mesh_select_mode == edge:
                tool_settings.uv_select_mode = 'EDGE'
            if mesh_select_mode == face:
                tool_settings.uv_select_mode = 'FACE'

    def sync_selected_elements(self, context, uv_sync_enable):
        for ob in context.objects_in_mode_unique_data:
            me = ob.data
            bm = bmesh.from_edit_mesh(me)

            uv_layer = bm.loops.layers.uv.verify()

            if uv_sync_enable:
                for face in bm.faces:
                    for loop in face.loops:
                        loop_uv = loop[uv_layer]
                        if not loop_uv.select:
                            face.select = False

                for face in bm.faces:
                    for loop in face.loops:
                        loop_uv = loop[uv_layer]
                        if loop_uv.select:
                            loop.vert.select = True

                for edge in bm.edges:
                    vert_count = 0
                    for vert in edge.verts:
                        if vert.select:
                            vert_count += 1
                    if vert_count == 2:
                        edge.select = True

            else:
                for face in bm.faces:
                    for loop in face.loops:
                        loop_uv = loop[uv_layer]
                        loop_uv.select = False

                mesh_select_mode = context.tool_settings.mesh_select_mode[:]

                if mesh_select_mode[2]:  # face
                    for face in bm.faces:
                        if face.select:
                            for loop in face.loops:
                                loop_uv = loop[uv_layer]
                                if loop.vert.select:
                                    loop_uv.select = True
                # if mesh_select_mode[1]:  # edge
                #     bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
                #     print ("edge")

                
                else: #vertex
                    for face in bm.faces:
                        for loop in face.loops:
                            loop_uv = loop[uv_layer]
                            if loop.vert.select:
                                loop_uv.select = True

                for face in bm.faces:
                    face.select = True
        
            bmesh.update_edit_mesh(me)

    def register():
        bpy.utils.register_class(UVEDITORSMARTUVSYNC_PT_Panel)
        bpy.types.Scene.smart_uv_sync_enable = bpy.props.BoolProperty(name="Smart UV Sync (Slower)", default=True, description="Right Click to Toggle Sync Mode and UV Selection")
    

    def unregister():
        bpy.utils.unregister_class(UVEDITORSMARTUVSYNC_PT_Panel)
        del bpy.types.Scene.smart_uv_sync_enable


    def execute(self, context):
        tool_settings = context.tool_settings
        uv_sync_enable = not tool_settings.use_uv_select_sync
        tool_settings.use_uv_select_sync = uv_sync_enable

        if context.scene.smart_uv_sync_enable:
            self.sync_uv_selction_mode(context, uv_sync_enable)
            self.sync_selected_elements(context, uv_sync_enable)

        else:
            self.fast_sync(context)

        return {'FINISHED'}

class UVEDITORSMARTUVSYNC_PT_Panel(bpy.types.Panel):
    prefs = get_keyops_prefs()
    category_name = prefs.smart_uv_sync_panel_name
    bl_label = "KeyOps UV"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = category_name

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.scale_y = 1.5
        row.prop(context.scene, "smart_uv_sync_enable", toggle=True, icon='UV_SYNC_SELECT')
