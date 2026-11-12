"""Check that the docs site is in sync with the add-on.

Run from the repo root:  python docs/check_docs.py
Exits with code 1 if anything is out of sync.

Checks:
  * every `enable_*` preference is listed in the preferences UI with a DOCS_URL link
  * every DOCS_URL link (preferences) points to a page + anchor that exists
  * every local link / image in the docs resolves (page, anchor, file)
  * every sidebar entry in assets/site.js points to an existing anchor
  * the version shown in the docs matches blender_manifest.toml
  * media in assets/ that no page uses (warning only)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

errors, warnings = [], []

pages = {p.name: p.read_text(encoding="utf-8") for p in DOCS.glob("*.html")}
ids = {name: set(re.findall(r'\bid="([^"]+)"', text)) for name, text in pages.items()}


def anchor_ok(page, anchor):
    return page in ids and (not anchor or anchor in ids[page])


# --- preferences -> docs ----------------------------------------------------
prefs = (ROOT / "addon_preferences.py").read_text(encoding="utf-8")
declared = set(re.findall(r"^\s*(enable_\w+)\s*:\s*BoolProperty", prefs, re.M))
# rows drawn in draw_extensions: ("label", "enable_x", toggle, link, experimental)
rows = dict(re.findall(r'\(\s*"[^"]*",\s*"(enable_\w+)",\s*(?:True|False),\s*([^,]+),\s*[01]\)', prefs))
not_listed = {"enable_legacy_collection_shortcuts"}  # drawn as a sub-setting, not a row

for name in sorted(declared - set(rows) - not_listed):
    errors.append(f"preference {name} is not shown in the Extensions tab list")
for name, link in sorted(rows.items()):
    link = link.strip()
    m = re.match(r'DOCS_URL \+ "([^"#]+)#?([^"]*)"', link)
    if m:
        page, anchor = m.groups()
        if not anchor_ok(page, anchor):
            errors.append(f"preference {name} links to missing docs anchor {page}#{anchor}")
    elif link in ("False", '""', "''"):
        errors.append(f"preference {name} has no docs link")
    elif "notion" in link:
        errors.append(f"preference {name} still links to Notion")

# --- links and images inside the docs ---------------------------------------
for name, text in pages.items():
    for ref in re.findall(r'(?:href|src)="([^"]+)"', text):
        if ref.startswith(("http:", "https:", "mailto:")):
            continue
        target, _, anchor = ref.partition("#")
        if not target:
            if anchor not in ids[name]:
                errors.append(f"{name}: broken in-page link #{anchor}")
            continue
        if not (DOCS / target).exists():
            errors.append(f"{name}: missing file {target}")
        elif target.endswith(".html") and anchor and anchor not in ids.get(target, ()):
            errors.append(f"{name}: broken link {ref}")

# --- sidebar / search index -------------------------------------------------
site_js = (DOCS / "assets" / "site.js").read_text(encoding="utf-8")
for page, block in re.findall(r'page: "([^"]+)", title: "[^"]+", items: \[(.*?)\]\s*\}', site_js, re.S):
    if page not in pages:
        errors.append(f"site.js NAV: page {page} does not exist")
        continue
    for anchor in re.findall(r'\["([^"]+)",', block):
        if anchor not in ids[page]:
            errors.append(f"site.js NAV: {page}#{anchor} does not exist")
    documented = {i for i in ids[page] if re.search(rf'class="feature"[^>]*id="{re.escape(i)}"', pages[page])}
    for anchor in sorted(documented - set(re.findall(r'\["([^"]+)",', block))):
        warnings.append(f"{page}#{anchor} is not in the sidebar (site.js NAV)")

# --- version ----------------------------------------------------------------
manifest = (ROOT / "blender_manifest.toml").read_text(encoding="utf-8")
version = re.search(r'^version\s*=\s*"([^"]+)"', manifest, re.M).group(1)
js_version = re.search(r'const VERSION = "([^"]+)"', site_js).group(1)
if js_version != version:
    errors.append(f"site.js VERSION is {js_version}, manifest is {version}")

# --- unused media -----------------------------------------------------------
used = " ".join(pages.values()) + site_js
for f in (DOCS / "assets").rglob("*"):
    if f.is_file() and f.suffix.lower() in {".png", ".gif", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".svg"}:
        rel = f.relative_to(DOCS).as_posix()
        if rel not in used and rel not in {"assets/icon.svg", "assets/logo.svg"}:  # brand assets kept for reuse
            warnings.append(f"unused media: {rel}")

for w in warnings:
    print("warning:", w)
for e in errors:
    print("ERROR:", e)
print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
sys.exit(1 if errors else 0)
