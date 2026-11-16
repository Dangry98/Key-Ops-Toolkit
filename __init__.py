# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ***** END GPL LICENSE BLOCK *****

import bpy

from . import features
from .addon_preferences import KeyOpsPreferences
from .operators.xray_select import register_xray_select, unregister_xray_select
from .ui.toolkit_paneL_ui import panel_classes
from .ui import welcome

debug = True


def register():
    if debug:
        import time
        start = time.time()

    bpy.utils.register_class(KeyOpsPreferences)
    welcome.register()
    for cls in panel_classes:
        bpy.utils.register_class(cls)
    register_xray_select()

    # Fresh install -> Essentials (no shortcuts). Upgrade from 0.2 -> keep everything.
    features.migrate()
    # Register every enabled feature from the registry (replaces the old if/elif dispatcher)
    features.sync_all()
    welcome.schedule_welcome()

    if debug:
        print(f"{__package__} registered in {time.time() - start:.4f}s, "
              f"{features.live_shortcut_count()} shortcuts active")


def unregister():
    from .operators.toggle_retopology import reset_retopo_themes_on_unregister_addon
    from .utils.pref_utils import unregister_icons
    reset_retopo_themes_on_unregister_addon()

    features.unregister_all()
    unregister_icons()
    unregister_xray_select()

    for cls in reversed(panel_classes):
        bpy.utils.unregister_class(cls)
    welcome.unregister()
    bpy.utils.unregister_class(KeyOpsPreferences)
