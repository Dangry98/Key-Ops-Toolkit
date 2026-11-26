#!/usr/bin/env bash
# Build the working tree and install it into a scratch Blender profile (for demos / GUI checks).
#   scripts/demo/install.sh <blender> <profile_dir>
# Then run Blender with BLENDER_USER_RESOURCES=<profile_dir> (no --factory-startup, so the add-on loads).
set -eu
blender="$1"; prof="$2"
repo="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$prof" "$prof/_build"
rm -f "$prof"/_build/*.zip
export BLENDER_USER_RESOURCES="$prof"
"$blender" --command extension build --source-dir "$repo" --output-dir "$prof/_build" >/dev/null
"$blender" --command extension install-file -r user_default -e "$prof"/_build/*.zip >/dev/null
# no splash, OpenGL backend (no Vulkan warning on software GL), the add-on enabled
"$blender" -b --python-expr "
import bpy, addon_utils
p = bpy.context.preferences
p.view.show_splash = False
try:
    p.system.gpu_backend = 'OPENGL'
except Exception:
    pass
addon_utils.enable('bl_ext.user_default.Key_Ops_Toolkit', default_set=True, persistent=True)
bpy.ops.wm.save_userpref()
" >/dev/null 2>&1
echo "installed into $prof"
