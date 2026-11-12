import bpy
from bpy.types import Menu

class VIEW3D_MT_edit_mesh_looptools_menu(Menu):
    bl_label = "LoopTools"

    def draw(self, context):
        layout = self.layout
        layout.operator("mesh.circularize", text="Circle")
        layout.operator("mesh.curve_edge_loops_between_selected", text="Curve")
        layout.operator("mesh.flatten", text="Flatten")
        layout.operator("mesh.fit_edge_loops_to_annotation", text="Gstretch")
        layout.operator("mesh.relax_edge_loops", text="Relax")
        layout.operator("mesh.space_edge_loops_evenly", text="Space")

def menu_func(self, context):
    self.layout.menu("VIEW3D_MT_edit_mesh_looptools_menu")
    self.layout.separator()

def register_looptools_menu():
    bpy.utils.register_class(VIEW3D_MT_edit_mesh_looptools_menu)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.prepend(menu_func)

def unregister_looptools_menu():
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(menu_func)
    bpy.utils.unregister_class(VIEW3D_MT_edit_mesh_looptools_menu)