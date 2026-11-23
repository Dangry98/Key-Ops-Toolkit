"""Make the darker menu copies of Key Ops' coloured icons: icons/<name>_menu.png.

Custom menus (pies, popup menus, the preview in the preferences) draw a Key Ops icon "keyops:<name>" with
its _menu copy when there is one, so bright colours don't shout in a menu; the N panel keeps the originals.
Only coloured icons get a copy: grey ones look the same in both places.

Run it with Blender (any version), from the repo:
    blender -b --factory-startup --python scripts/make_menu_icons.py
Run it again after adding or changing an icon.
"""

import colorsys
import os

import bpy

ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "icons")
SUFFIX = "_menu"
SATURATION = 0.85   # how much of its saturation each colour keeps (the hue never changes)
BRIGHTNESS = 0.9    # and how much of its brightness
MIN_SATURATION = 0.2  # icons less colourful than this (on average) get no copy


def saturation(r, g, b):
    hi, lo = max(r, g, b), min(r, g, b)
    return 0.0 if hi <= 0.0 else (hi - lo) / hi


def make(path, out):
    img = bpy.data.images.load(path, check_existing=False)
    px = list(img.pixels)
    sats = [saturation(*px[i:i + 3]) for i in range(0, len(px), 4) if px[i + 3] > 0.5]
    if not sats or sum(sats) / len(sats) < MIN_SATURATION:
        bpy.data.images.remove(img)
        return False
    for i in range(0, len(px), 4):
        h, s, v = colorsys.rgb_to_hsv(*px[i:i + 3])
        px[i:i + 3] = colorsys.hsv_to_rgb(h, s * SATURATION, v * BRIGHTNESS)
    copy = bpy.data.images.new(os.path.basename(out), img.size[0], img.size[1], alpha=True)
    copy.pixels = px
    copy.filepath_raw = out
    copy.file_format = 'PNG'
    copy.save()
    bpy.data.images.remove(copy)
    bpy.data.images.remove(img)
    return True


made, skipped = [], []
for name in sorted(os.listdir(ICONS)):
    if not name.endswith(".png") or name[:-4].endswith(SUFFIX):
        continue
    out = os.path.join(ICONS, name[:-4] + SUFFIX + ".png")
    (made if make(os.path.join(ICONS, name), out) else skipped).append(name[:-4])
print("made menu copies:", ", ".join(made) or "none")
print("grey, no copy:", ", ".join(skipped) or "none")
