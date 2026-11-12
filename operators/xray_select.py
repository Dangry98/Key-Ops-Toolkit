"""X-Ray Select: always select through geometry with the box/circle/lasso select tools.

Adds an "X-Ray Select" checkbox to the tool header of the select tools, right after the Mode enum. While it's enabled, a lightweight timer watches for a running
box/circle/lasso select gesture in Edit Mesh mode and turns on an opaque X-ray
(faces stay solid, hidden wireframe shows through) for its duration, so the selection
goes through the geometry. The previous shading is restored as soon as the gesture
finishes.

Always registered (not tied to an addon preference).
"""

import bpy

SELECT_TOOLS = {"builtin.select_box", "builtin.select_circle", "builtin.select_lasso"}
SELECT_GESTURE_OPS = {"VIEW3D_OT_select_box", "VIEW3D_OT_select_circle", "VIEW3D_OT_select_lasso"}

IDLE_INTERVAL = 0.1     # seconds between checks while no gesture is running
ACTIVE_INTERVAL = 0.02  # seconds between checks while a gesture is running

# (window pointer) -> list of (View3DShading, {attribute: original value}) we changed
_forced_xray = {}


def _xray_attrs(shading):
    """Attributes to switch for an X-ray that keeps surfaces looking solid.

    Like space_view3d_xray_selection_tools' "hidden X-ray": X-ray is enabled so the
    selection goes through, but alpha 1.0 keeps faces opaque. The back-wire overlay is
    left as is, so hidden edges/verts still show through like regular X-ray.
    """
    if shading.type == 'WIREFRAME':
        return "show_xray_wireframe", {"show_xray_wireframe": True}
    return "show_xray", {"show_xray": True, "xray_alpha": 1.0}


def _window_in_edit_mesh(window):
    obj = window.view_layer.objects.active if window.view_layer else None
    return obj is not None and obj.type == 'MESH' and obj.mode == 'EDIT'


def _gesture_running(window):
    # modal_operators can contain None entries (handlers without a Python-visible operator)
    return any(op is not None and op.bl_idname in SELECT_GESTURE_OPS for op in window.modal_operators)


def _force_xray(window):
    forced = []
    for area in window.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        shading = area.spaces.active.shading
        toggle_attr, values = _xray_attrs(shading)
        if getattr(shading, toggle_attr):
            continue  # X-ray already on: leave the user's setup alone
        original = {name: getattr(shading, name) for name in values}
        for name, value in values.items():
            setattr(shading, name, value)
        forced.append((shading, original))
        area.tag_redraw()
    _forced_xray[window.as_pointer()] = forced


def _restore_xray(key):
    for shading, original in _forced_xray.pop(key, ()):
        try:
            for name, value in original.items():
                setattr(shading, name, value)
        except ReferenceError:  # area/space was closed meanwhile
            pass


def _restore_all():
    for key in list(_forced_xray):
        _restore_xray(key)


def _xray_select_watcher():
    wm = bpy.context.window_manager
    if wm is None:
        return IDLE_INTERVAL

    open_windows = set()
    for window in wm.windows:
        key = window.as_pointer()
        open_windows.add(key)
        running = _gesture_running(window)

        if key in _forced_xray:
            if not running:
                _restore_xray(key)
        elif running and window.scene.keyops_xray_select and _window_in_edit_mesh(window):
            _force_xray(window)

    for key in list(_forced_xray):  # windows closed mid-gesture
        if key not in open_windows:
            _forced_xray.pop(key, None)

    return ACTIVE_INTERVAL if _forced_xray or any(_gesture_running(w) for w in wm.windows) else IDLE_INTERVAL


class XraySelectToggleOperator(bpy.types.Operator):
    bl_idname = "keyops.xray_select_toggle"
    bl_label = "KeyOps: Toggle X-Ray Select"
    bl_description = "Toggle always selecting through geometry with the box, circle and lasso select tools"
    bl_options = {'REGISTER'}

    def execute(self, context):
        context.scene.keyops_xray_select = not context.scene.keyops_xray_select
        return {'FINISHED'}


def _draw_select_through(context, layout):
    if context.mode != 'EDIT_MESH' or getattr(context.space_data, "type", None) != 'VIEW_3D':
        return
    tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
    if tool is None or tool.idname not in SELECT_TOOLS:
        return
    layout.prop(context.scene, "keyops_xray_select", text="X-Ray Select")


# The select tools' Mode enum is drawn by the tool's own draw_settings, called from
# ToolSelectPanelHelper.draw_active_tool_header, which draws nothing after it for these
# tools. Wrapping that function lets the checkbox sit right after the Mode enum.
def _unwrapped_draw_active_tool_header():
    from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
    fn = ToolSelectPanelHelper.draw_active_tool_header
    while getattr(fn, "_keyops_select_through_orig", None) is not None:  # strip stale wrappers from earlier loads
        fn = fn._keyops_select_through_orig
    return fn


def _install_header_wrapper():
    from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
    orig = _unwrapped_draw_active_tool_header()

    def draw_active_tool_header(context, layout, **kwargs):
        result = orig(context, layout, **kwargs)
        if result is not None:
            try:
                _draw_select_through(context, layout)
            except Exception as e:
                print(f"Key Ops Toolkit: X-Ray Select draw failed: {e}")
        return result

    draw_active_tool_header._keyops_select_through_orig = orig
    ToolSelectPanelHelper.draw_active_tool_header = staticmethod(draw_active_tool_header)


def _remove_header_wrapper():
    from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
    ToolSelectPanelHelper.draw_active_tool_header = staticmethod(_unwrapped_draw_active_tool_header())


classes = (XraySelectToggleOperator,)


def register_xray_select():
    bpy.types.Scene.keyops_xray_select = bpy.props.BoolProperty(
        name="X-Ray Select",
        description="Always select through geometry when using the box, circle or lasso select tools",
        default=False,
    )

    for cls in classes:
        bpy.utils.register_class(cls)

    _install_header_wrapper()

    if not bpy.app.timers.is_registered(_xray_select_watcher):
        bpy.app.timers.register(_xray_select_watcher, first_interval=IDLE_INTERVAL, persistent=True)


def unregister_xray_select():
    if bpy.app.timers.is_registered(_xray_select_watcher):
        bpy.app.timers.unregister(_xray_select_watcher)
    _restore_all()

    _remove_header_wrapper()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    if hasattr(bpy.types.Scene, "keyops_xray_select"):
        del bpy.types.Scene.keyops_xray_select
