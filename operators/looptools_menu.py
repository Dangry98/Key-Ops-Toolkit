import bpy
from bpy.types import Menu
from ..utils.utilities import operator_exists

# Native LoopTools replacements land one by one during the 5.3/5.4 alphas
# (e.g. 5.3 alpha has no Curve or Gstretch yet), so only draw the ones this build has.
LOOPTOOLS_OPERATORS = (
    ("mesh.circularize", "Circle"),
    ("mesh.curve_edge_loops_between_selected", "Curve"),
    ("mesh.flatten", "Flatten"),
    ("mesh.fit_edge_loops_to_annotation", "Gstretch"),
    ("mesh.relax_edge_loops", "Relax"),
    ("mesh.space_edge_loops_evenly", "Space"),
)

class VIEW3D_MT_edit_mesh_looptools_menu(Menu):
    bl_label = "LoopTools"

    def draw(self, context):
        layout = self.layout
        for idname, text in LOOPTOOLS_OPERATORS:
            if operator_exists(idname):
                layout.operator(idname, text=text)

def menu_func(self, context):
    self.layout.menu("VIEW3D_MT_edit_mesh_looptools_menu")
    self.layout.separator()

def register_looptools_menu():
    bpy.utils.register_class(VIEW3D_MT_edit_mesh_looptools_menu)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.prepend(menu_func)

def unregister_looptools_menu():
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(menu_func)
    bpy.utils.unregister_class(VIEW3D_MT_edit_mesh_looptools_menu)
