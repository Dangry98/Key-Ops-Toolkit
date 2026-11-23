import bpy
from bpy.types import Menu
from ..utils.utilities import operator_exists
from ..utils.pref_utils import get_keyops_prefs
from ..utils.pref_utils import feature_on

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
    if not feature_on("looptools_menu"):
        return
    self.layout.menu("VIEW3D_MT_edit_mesh_looptools_menu")
    self.layout.separator()

def register():
    if bpy.app.version < (5, 3, 0):  # the LoopTools operators are in Blender from 5.3
        return
    bpy.utils.register_class(VIEW3D_MT_edit_mesh_looptools_menu)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.prepend(menu_func)

def unregister():
    if bpy.app.version < (5, 3, 0):
        return
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(menu_func)
    bpy.utils.unregister_class(VIEW3D_MT_edit_mesh_looptools_menu)
