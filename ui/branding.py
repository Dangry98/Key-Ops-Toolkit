"""Key Ops branding: logo images, version and links shown in the preferences header."""

import os
import tomllib

import bpy
import bpy.utils.previews

BRAND_DIR = os.path.join(os.path.dirname(__file__), "..", "icons", "brand")
DOCS_URL = "https://dangry98.github.io/Key-Ops-Toolkit/"
ISSUES_URL = "https://github.com/Dangry98/Key-Ops-Toolkit/issues"
EXTENSION_URL = "https://extensions.blender.org/add-ons/key-ops-toolkit/"

_previews = None


def version_text():
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "blender_manifest.toml"), "rb") as f:
            return tomllib.load(f).get("version", "")
    except OSError:
        return ""


def _icons():
    global _previews
    if _previews is None:
        _previews = bpy.utils.previews.new()
        for i in range(2):
            _previews.load(f"logo_{i}", os.path.join(BRAND_DIR, f"logo_tile_{i}.png"), 'IMAGE')
    return _previews


def draw_logo(layout, scale=4.0):
    """The wide logo, drawn as two square tiles that meet in the gap between "Key" and "Ops"."""
    row = layout.row(align=True)
    row.alignment = 'LEFT'
    icons = _icons()
    for i in range(2):
        col = row.column(align=True)
        col.template_icon(icon_value=icons[f"logo_{i}"].icon_id, scale=scale)


def _links(row):
    row.operator("wm.url_open", text="Documentation", icon='HELP', emboss=False).url = DOCS_URL
    row.operator("wm.url_open", text="Report a Problem", icon='URL', emboss=False).url = ISSUES_URL


def draw_header(layout):
    """Logo left, name and version beside it, links as quiet text links under the version."""
    box = layout.box()
    split = box.split(factor=0.36)
    draw_logo(split.column(), scale=6.0)
    right = split.column(align=True)
    right.separator(factor=2.2)
    right.label(text="Modeling tools, pie menus and shortcuts for Blender")
    sub = right.row()
    sub.active = False
    sub.label(text=f"Version {version_text()}  ·  by Dan-Gry")
    right.separator(factor=0.6)
    row = right.row(align=False)
    row.alignment = 'LEFT'
    _links(row)


def unregister():
    global _previews
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews = None
