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


HEADER_STYLE = "A"  # "A", "B" or "C": three proposals for where the links go


def _links(row, emboss=True, icons=True):
    row.operator("wm.url_open", text="Documentation", icon='HELP' if icons else 'NONE', emboss=emboss).url = DOCS_URL
    row.operator("wm.url_open", text="Report a Problem", icon='URL' if icons else 'NONE', emboss=emboss).url = ISSUES_URL


def draw_header(layout):
    {"A": _header_a, "B": _header_b, "C": _header_c}.get(HEADER_STYLE, _header_a)(layout)


def _header_a(layout):
    """A: logo left, name and version beside it, links as quiet text links under the version."""
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
    _links(row, emboss=False)


def _header_b(layout):
    """B: logo left, links as small buttons pinned to the top right corner."""
    box = layout.box()
    row = box.row()
    draw_logo(row.column(), scale=5.0)
    right = row.column(align=True)
    links = right.row(align=True)
    links.alignment = 'RIGHT'
    _links(links)
    right.separator(factor=3.0)
    info = right.row()
    info.alignment = 'RIGHT'
    info.active = False
    info.label(text=f"Modeling tools, pie menus and shortcuts  ·  v{version_text()}")


def _header_c(layout):
    """C: centered logo with a centered row of links underneath, like an about page."""
    box = layout.box()
    row = box.row()
    row.alignment = 'CENTER'
    draw_logo(row, scale=5.0)
    t = box.row()
    t.alignment = 'CENTER'
    t.active = False
    t.label(text=f"Modeling tools, pie menus and shortcuts for Blender  ·  v{version_text()}")
    links = box.row()
    links.alignment = 'CENTER'
    _links(links)


def unregister():
    global _previews
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews = None
