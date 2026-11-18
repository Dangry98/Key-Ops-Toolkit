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

from . import features, pie_menus
from .addon_preferences import KeyOpsPreferences
from .properties import register_properties, unregister_properties
from .operators.xray_select import register_xray_select, unregister_xray_select
from .ui.toolkit_paneL_ui import NewToolkitPanel
from .ui import welcome

debug = True


def register():
    if debug:
        import time
        start = time.time()

    # Scene properties must exist before anything that reads them is registered
    register_properties()
    pie_menus.register_properties()  # pie data lives in the preferences
    bpy.utils.register_class(KeyOpsPreferences)
    welcome.register()
    bpy.utils.register_class(NewToolkitPanel)
    register_xray_select()

    pie_menus.register()
    if _prefs_ready():
        _finish_register()
    else:
        # Enabled from the command line: preferences don't exist until Blender finishes starting
        bpy.app.timers.register(_finish_register_when_ready, first_interval=0.1)

    if debug:
        print(f"{__package__} registered in {time.time() - start:.4f}s, "
              f"{features.live_shortcut_count() + pie_menus.live_count()} shortcuts active")


def _prefs_ready():
    from .utils.pref_utils import KeyOpsPrefsMock, get_keyops_prefs
    return not isinstance(get_keyops_prefs(), KeyOpsPrefsMock)


def _finish_register():
    # Pie menus live in pie_menus.json in the add-on's user folder; read them first
    pie_menus.load_from_disk()
    # Fresh install -> quiet (no shortcuts) until the welcome screen. Upgrade from 0.2 -> keep everything.
    features.migrate()
    # Register every enabled feature from the registry (replaces the old if/elif dispatcher)
    features.sync_all()
    pie_menus.sync_keymaps()
    welcome.schedule_welcome()


def _finish_register_when_ready(tries=[0]):
    tries[0] += 1
    if _prefs_ready():
        _finish_register()
        return None
    return 0.2 if tries[0] < 100 else None


def unregister():
    from .operators.toggle_retopology import reset_retopo_themes_on_unregister_addon
    from .utils.pref_utils import unregister_icons
    reset_retopo_themes_on_unregister_addon()

    pie_menus.unregister()
    features.unregister_all()
    unregister_icons()
    unregister_xray_select()

    bpy.utils.unregister_class(NewToolkitPanel)
    welcome.unregister()
    bpy.utils.unregister_class(KeyOpsPreferences)
    pie_menus.unregister_properties()
    unregister_properties()
