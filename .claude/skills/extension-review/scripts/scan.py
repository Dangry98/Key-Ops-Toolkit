#!/usr/bin/env python3
"""Static pre-upload scan of a Blender add-on extension against extensions.blender.org rules.

Usage:
    python3 scan.py [ADDON_DIR | PACKAGE.zip] [--json] [--include-excluded]

ADDON_DIR is the folder holding blender_manifest.toml (default: current directory; if the
manifest is not there, the first sub-folder that has one is used). A built extension .zip
can be passed instead and is scanned exactly as it would ship.
In a source folder, files outside the manifest's [build] paths / paths_exclude_pattern (or
the defaults) are skipped because they will not ship; use --include-excluded to scan them.
Works for any add-on; needs only the Python standard library (3.11+ for manifest checks).

Findings are heuristics. Every hit must be confirmed by reading the code: the scan
exists to make sure nothing is overlooked, not to replace review.

Severity levels:
    BLOCKER  - moderators delist / decline for this (ToS or hard platform rule)
    REQUIRED - moderators send the version back ("Awaiting Changes") for this
    WARN     - frequently flagged in review; fix or be ready to justify
    INFO     - worth a look
"""
from __future__ import annotations

import ast
import fnmatch
import json
import os
import re
import sys

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

SEVERITIES = ("BLOCKER", "REQUIRED", "WARN", "INFO")

VALID_ADDON_TAGS = {
    "3D View", "Add Curve", "Add Mesh", "Animation", "Bake", "Camera", "Compositing",
    "Development", "Game Engine", "Geometry Nodes", "Grease Pencil", "Import-Export",
    "Lighting", "Material", "Modeling", "Mesh", "Node", "Object", "Paint", "Pipeline",
    "Physics", "Render", "Rigging", "Scene", "Sculpt", "Sequencer", "System",
    "Text Editor", "Tracking", "User Interface", "UV",
}
VALID_PERMISSIONS = {"files", "network", "clipboard", "camera", "microphone"}
VALID_PLATFORMS = {"windows-x64", "windows-arm64", "macos-x64", "macos-arm64", "linux-x64"}
DEFAULT_EXCLUDES = ["__pycache__/", ".git", "*.zip"]

BINARY_EXT = {".dll", ".so", ".pyd", ".dylib", ".exe", ".bin", ".lib", ".a", ".o", ".jar"}
BYTECODE_EXT = {".pyc", ".pyo"}
DEV_FILE_PATTERNS = [
    "CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", "*.code-workspace", ".gitignore",
    ".gitattributes", "pyproject.toml", "setup.py", "setup.cfg", "requirements*.txt",
    "poetry.lock", "uv.lock", "Pipfile*", "ruff.toml", ".ruff.toml", "pytest.ini", "tox.ini",
    ".flake8", ".pylintrc", ".editorconfig", ".pre-commit-config.yaml", "Makefile",
    "*.psd", "*.ai", "*.blend1", "*.kra", "*.xcf", "zip_release*.py", "build*.py",
    "release*.py", "devtools*.py", "*.log",
]
DEV_DIR_NAMES = {"tests", "test", ".github", ".vscode", ".idea", ".claude", "docs", "dev",
                 ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}

AD_DOMAINS = r"patreon\.com|gumroad\.com|ko-fi\.com|buymeacoffee|paypal\.(com|me)|superhivemarket|" \
             r"blendermarket\.com|artstation\.com/marketplace|youtube\.com|youtu\.be|discord\.(gg|com)|" \
             r"twitter\.com|x\.com/|instagram\.com|facebook\.com|tiktok\.com|linkedin\.com|" \
             r"bit\.ly|tinyurl|linktr\.ee|github\.com/sponsors|opencollective"


AGGREGATE = {"bpy-ops", "bpy-data", "stray-props", "addon-dir-write"}


class Scanner:
    def __init__(self, root: str, include_excluded: bool = False):
        self.root = os.path.abspath(root)
        self.include_excluded = include_excluded
        self.findings: list[dict] = []
        self.manifest: dict = {}
        self.excludes: list[str] = list(DEFAULT_EXCLUDES)
        self.include_paths: list[str] | None = None
        self.shipped: list[str] = []
        self.py_files: list[str] = []
        self.texts: dict[str, str] = {}
        self.seen_prefixes: set[str] = set()

    # ------------------------------------------------------------------ util
    def add(self, sev, rule, msg, path=None, line=None, snippet=None):
        self.findings.append({"severity": sev, "rule": rule, "message": msg,
                              "path": path, "line": line,
                              "snippet": (snippet or "").strip()[:160] or None})

    def excluded(self, rel: str) -> bool:
        rel_posix = rel.replace(os.sep, "/")
        parts = rel_posix.split("/")
        for pat in self.excludes:
            p = pat.strip()
            if not p:
                continue
            anchored = p.startswith("/")
            p = p.lstrip("/")
            dir_only = p.endswith("/")
            p = p.rstrip("/")
            if anchored:
                if fnmatch.fnmatch(rel_posix, p) or fnmatch.fnmatch(rel_posix, p + "/*") \
                        or rel_posix.startswith(p + "/"):
                    return True
            else:
                candidates = parts[:-1] if dir_only else parts
                if any(fnmatch.fnmatch(c, p) for c in candidates):
                    return True
                if fnmatch.fnmatch(rel_posix, p):
                    return True
        return False

    # -------------------------------------------------------------- manifest
    def load_manifest(self):
        path = os.path.join(self.root, "blender_manifest.toml")
        if not os.path.exists(path):
            self.add("BLOCKER", "manifest", "blender_manifest.toml not found", "blender_manifest.toml")
            return
        raw = open(path, encoding="utf-8").read()
        if tomllib is None:
            self.add("INFO", "manifest", "tomllib unavailable (Python < 3.11); manifest checks skipped")
            return
        try:
            self.manifest = tomllib.loads(raw)
        except Exception as e:  # noqa: BLE001
            self.add("BLOCKER", "manifest", f"manifest is not valid TOML: {e}", "blender_manifest.toml")
            return
        build = self.manifest.get("build", {})
        if "paths_exclude_pattern" in build:
            self.excludes = list(build["paths_exclude_pattern"])
        if "paths" in build:
            self.include_paths = [p.replace("\\", "/").strip("/") for p in build["paths"]]
        if "generated" in build:
            self.add("REQUIRED", "manifest", "[build.generated] is reserved and must not be in the source manifest",
                     "blender_manifest.toml")

    def check_manifest(self):
        m = self.manifest
        if not m:
            return
        f = "blender_manifest.toml"
        for key in ("schema_version", "id", "version", "name", "tagline", "maintainer", "type",
                    "blender_version_min", "license"):
            if key not in m:
                self.add("BLOCKER", "manifest", f"required field '{key}' missing", f)
        for key, val in m.items():
            if val in ("", [], {}):
                self.add("REQUIRED", "manifest", f"field '{key}' is empty; omit optional fields instead", f)
        ext_id = str(m.get("id", ""))
        if ext_id and (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", ext_id)):
            self.add("BLOCKER", "manifest", f"id '{ext_id}' must be a valid Python identifier (no leading digit, no dashes)", f)
        ver = str(m.get("version", ""))
        if ver and not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?", ver):
            self.add("REQUIRED", "manifest", f"version '{ver}' is not semantic versioning (MAJOR.MINOR.PATCH)", f)
        name = str(m.get("name", ""))
        if re.search(r"\bblender\b", name, re.I):
            self.add("BLOCKER", "branding", "the word 'Blender' must not be in the extension name (ToS 2.1)", f)
        tagline = str(m.get("tagline", ""))
        if tagline:
            if len(tagline) > 64:
                self.add("REQUIRED", "manifest", f"tagline is {len(tagline)} chars; max 64", f)
            if re.search(r"[.!?,;:]$", tagline):
                self.add("REQUIRED", "manifest", "tagline must not end with punctuation", f)
            if re.search(r"\bblender\b", tagline, re.I):
                self.add("INFO", "branding", "tagline mentions 'Blender'; make sure it does not imply endorsement (ToS 2.3)", f)
        if m.get("type") not in (None, "add-on", "theme", "asset-library"):
            self.add("BLOCKER", "manifest", f"unknown type '{m.get('type')}'", f)
        bmin = str(m.get("blender_version_min", ""))
        if bmin and tuple(int(x) for x in re.findall(r"\d+", bmin)[:3]) < (4, 2, 0):
            self.add("REQUIRED", "manifest", "blender_version_min must be at least 4.2.0", f)
        lic = m.get("license", [])
        if m.get("type", "add-on") == "add-on" and "SPDX:GPL-3.0-or-later" not in lic:
            self.add("BLOCKER", "license", "add-ons must be licensed SPDX:GPL-3.0-or-later (ToS 1.1)", f)
        if lic and any(not str(x).startswith("SPDX:") for x in lic):
            self.add("REQUIRED", "license", "license entries must use the 'SPDX:' prefix", f)
        for c in m.get("copyright", []) or []:
            if not re.fullmatch(r"\d{4}(-\d{4})? .+", str(c)):
                self.add("REQUIRED", "manifest", f"copyright '{c}' must be 'Year Name' or 'Year-Year Name'", f)
        tags = m.get("tags", []) or []
        for t in tags:
            if t not in VALID_ADDON_TAGS and m.get("type", "add-on") == "add-on":
                self.add("REQUIRED", "tags", f"tag '{t}' is not a valid add-on tag", f)
        if len(tags) > 3:
            self.add("WARN", "tags", f"{len(tags)} tags; moderators routinely ask to drop tags that are not "
                                      f"directly relevant ('do not abuse our tags system for exposure')", f)
        if "3D View" in tags:
            self.add("WARN", "tags", "'3D View' is one of the tags moderators most often ask to remove; keep only "
                                     "if the add-on is about the viewport itself", f)
        perms = m.get("permissions", {}) or {}
        if isinstance(perms, list):
            self.add("REQUIRED", "permissions", "permissions must be a table with a reason per permission", f)
            perms = {}
        for k, reason in perms.items():
            if k not in VALID_PERMISSIONS:
                self.add("REQUIRED", "permissions", f"unknown permission '{k}'", f)
            r = str(reason)
            if len(r) > 64:
                self.add("REQUIRED", "permissions", f"reason for '{k}' is {len(r)} chars; max 64", f)
            if r.rstrip().endswith("."):
                self.add("REQUIRED", "permissions", f"reason for '{k}' must not end with a period", f)
        self.perms = perms
        plats = m.get("platforms")
        if plats:
            for p in plats:
                if p not in VALID_PLATFORMS:
                    self.add("REQUIRED", "manifest", f"unknown platform '{p}'", f)
        self.platforms = plats
        if "support" not in m:
            self.add("REQUIRED", "listing", "no 'support' URL in manifest. Moderators require a public bug tracker "
                                           "('Report Issues' link, e.g. the GitHub issues page) - set it here or on the "
                                           "website. Most common change request on the platform", f)
        elif re.search(r"mailto:|@", str(m.get("support"))) and "github" not in str(m.get("support")):
            self.add("REQUIRED", "listing", "support must be a public issue tracker, not an e-mail address", f)
        for w in m.get("wheels", []) or []:
            if "\\" in w:
                self.add("REQUIRED", "wheels", f"wheel path '{w}' must use forward slashes", f)
            if not os.path.exists(os.path.join(self.root, w)):
                self.add("BLOCKER", "wheels", f"wheel listed but missing: {w}", f)
            if re.search(r"cp3(?:1[012]|[0-9])-", os.path.basename(w)):
                self.add("REQUIRED", "wheels", f"{os.path.basename(w)} targets an old CPython ABI; ship wheels for the "
                                              f"Python version of every supported Blender", f)
            if re.search(r"^(packaging|numpy|requests|urllib3|idna|certifi|charset_normalizer|zstandard)-",
                         os.path.basename(w)):
                self.add("REQUIRED", "wheels", f"{os.path.basename(w)} is already bundled with Blender; do not ship it", f)

    # ----------------------------------------------------------------- files
    def walk(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            rel_dir = os.path.relpath(dirpath, self.root)
            if rel_dir == ".":
                rel_dir = ""
            if ".git" in dirpath.split(os.sep):
                continue
            for fn in filenames:
                rel = os.path.join(rel_dir, fn) if rel_dir else fn
                if not self.include_excluded:
                    rel_posix = rel.replace(os.sep, "/")
                    if self.include_paths is not None:
                        if rel_posix != "blender_manifest.toml" and not any(
                                rel_posix == p or rel_posix.startswith(p + "/") for p in self.include_paths):
                            continue
                    elif self.excluded(rel):
                        continue
                self.shipped.append(rel)
                if fn.endswith(".py"):
                    self.py_files.append(rel)

    def check_files(self):
        has_binary = False
        size = 0
        for rel in self.shipped:
            full = os.path.join(self.root, rel)
            try:
                size += os.path.getsize(full)
            except OSError:
                pass
            base = os.path.basename(rel)
            ext = os.path.splitext(base)[1].lower()
            parts = rel.replace(os.sep, "/").split("/")
            if ext in BYTECODE_EXT or "__pycache__" in parts:
                self.add("BLOCKER", "bytecode", "byte-code would ship; build with `blender -c extension build` "
                                                "(ToS 3.5 - no byte code)", rel)
            elif ext in BINARY_EXT:
                has_binary = True
                self.add("BLOCKER", "binaries", "pre-compiled binary would ship. Extensions must be pure Python; "
                                                "C/C++ libraries are delisted (ToS 3.6)", rel)
            elif ext == ".whl":
                if base not in {os.path.basename(w) for w in self.manifest.get("wheels", []) or []}:
                    self.add("REQUIRED", "wheels", "wheel file ships but is not listed in manifest 'wheels'", rel)
                if not re.search(r"none-any\.whl$", base):
                    has_binary = True
            if any(fnmatch.fnmatch(base, p) for p in DEV_FILE_PATTERNS) or \
                    any(p in DEV_DIR_NAMES for p in parts[:-1]):
                self.add("REQUIRED", "dev-files", "development/unused file would ship. Exclude it in [build] "
                                                  "paths_exclude_pattern; delistings have cited CLAUDE.md, tests, "
                                                  "ruff/pytest configs, zip_release.py, source art", rel)
            if ext == ".gif":
                try:
                    if os.path.getsize(full) > 2_000_000:
                        self.add("WARN", "files", "large GIF ships in the package", rel)
                except OSError:
                    pass
            if ext in {".zip", ".blend1", ".bak", ".orig"}:
                self.add("REQUIRED", "dev-files", "archive/backup file would ship", rel)
            if re.search(r"blender[-_ ]?(logo|icon)", base, re.I):
                self.add("WARN", "branding", "file name suggests a Blender logo; the logo may not be used in "
                                             "extension images or icons (ToS 2.2)", rel)
        if self.manifest:
            plats = self.manifest.get("platforms")
            if has_binary and not plats:
                self.add("REQUIRED", "manifest", "platform-specific files present but 'platforms' not declared "
                                                 "(build with --split-platforms and upload one zip per platform)")
            if plats and not has_binary:
                self.add("REQUIRED", "manifest", "'platforms' declared without platform-specific files; remove it "
                                                 "or the add-on is hidden from other platforms", "blender_manifest.toml")
        if size > 50_000_000:
            self.add("WARN", "files", f"package payload is {size / 1e6:.0f} MB")
        if "__init__.py" not in self.shipped:
            self.add("BLOCKER", "files", "no top-level __init__.py")
        if "LICENSE" not in self.shipped and "LICENSE.txt" not in self.shipped and "COPYING" not in self.shipped:
            self.add("INFO", "license", "no LICENSE file ships; not required, but include the GPL text if you "
                                        "bundle third-party code")

    # ------------------------------------------------------------------ code
    LINE_RULES = [
        # (severity, rule, regex, message)
        ("BLOCKER", "threading", r"^\s*(from\s+(threading|_thread|queue|concurrent\.futures)\b|import\s+([\w.]+(\s+as\s+\w+)?\s*,\s*)*(threading|_thread|queue|concurrent\.futures)\b)",
         "threading/queue are treated as Blender crashers and are delisted on sight; use subprocess, "
         "multiprocessing, timers or modal operators"),
        ("BLOCKER", "eval-exec", r"(?<![\w.])(eval|exec)\s*\(",
         "eval()/exec() are not accepted (security); use getattr/setattr, json, ast.literal_eval"),
        ("BLOCKER", "eval-exec", r"\bcompile\s*\([^)]*['\"]exec['\"]",
         "compile(..., 'exec') is code execution; not accepted"),
        ("BLOCKER", "sys-manipulation", r"\bsys\.(path|modules|meta_path|path_hooks)\s*(\[.*\])?\s*(=|\.(append|insert|extend|pop|remove|clear|update)|\bdel\b)",
         "modifying sys.path/sys.modules affects other add-ons; import sub-modules relatively and ship wheels"),
        ("BLOCKER", "sys-manipulation", r"^\s*del\s+sys\.modules",
         "deleting from sys.modules (custom reloaders) is not allowed; use the documented reload pattern"),
        ("BLOCKER", "sys-manipulation", r"\bsite\.addsitedir\b|\bimportlib\.util\.(spec_from_file_location|module_from_spec)\b",
         "manual module loading outside the package namespace is not allowed"),
        ("WARN", "module-loader", r"\bimportlib\.(import_module|reload)\b|\bpkgutil\.(iter_modules|walk_packages)\b|__import__\s*\(",
         "dynamic module loading/auto-registration. Moderators delisted add-ons for this "
         "('import and register modules normally, and manually'); confirm it only touches this package"),
        ("BLOCKER", "pip", r"\bensurepip\b|['\"]-m['\"]\s*,\s*['\"]pip['\"]|\bpip\s+install\b|pip\._internal",
         "installing packages at runtime is forbidden; bundle wheels"),
        ("BLOCKER", "updater", r"(?i)\b(addon_updater|auto_?updat|check_for_update|update_checker|updater_|download_update|latest_release|releases/latest)\b",
         "self-updaters and update checks are not allowed; updating is Blender's job"),
        ("BLOCKER", "other-addons", r"\baddon_utils\.(enable|disable|modules)\b|bpy\.ops\.preferences\.addon_(enable|disable|remove|install|refresh)|bpy\.ops\.extensions\.",
         "enabling/disabling/installing/querying other add-ons is forbidden (ToS 3.9, 5.3)"),
        ("REQUIRED", "other-addons", r"['\"](bl_ext\.|user_default|blender_org)",
         "hard-coded extension repository/module names; practically always means reaching into another "
         "extension or a broken import"),
        ("REQUIRED", "pkg-name", r"\.addons\s*\[\s*__name__\s*\]|bl_idname\s*=\s*__name__\b",
         "use __package__ (or `from .. import __package__ as base_package` in sub-modules) for add-on preferences"),
        ("REQUIRED", "addon-dir-write", r"__file__",
         "check this use of __file__: never write into the add-on directory (read-only 'System' installs) - "
         "use bpy.utils.extension_path_user(__package__, create=True); never build sys.path entries from it"),
        ("BLOCKER", "network", r"^\s*(from\s+(requests|urllib|http\.client|httpx|aiohttp|socket|ftplib|websocket|smtplib)\b|import\s+([\w.]+(\s+as\s+\w+)?\s*,\s*)*(requests|urllib|http\.client|httpx|aiohttp|socket|ftplib|websocket|smtplib)\b)",
         "network code found: needs the 'network' permission, a bpy.app.online_access check before every "
         "connection, explicit user action before sending data, and only completely free services (ToS 4.x)"),
        ("WARN", "network", r"['\"]https?://(?!docs\.blender\.org|developer\.blender\.org|projects\.blender\.org|extensions\.blender\.org|www\.blender\.org)[^'\"]+['\"]",
         "URL literal: if it is fetched, the network rules apply; if it is a UI link, it must be docs/bug "
         "tracker, never shop/social/donation (ToS 6.1)"),
        ("BLOCKER", "ads", r"(?i)(" + AD_DOMAINS + r")",
         "shop/funding/social link. Advertising, funding and social links inside Blender's UI are delisted "
         "on sight (ToS 6.1/6.3). Allowed: documentation and the public bug tracker"),
        ("BLOCKER", "ads", r"(?i)\b(pro version|upgrade to pro|buy (now|pro|full)|get (the )?pro|premium|unlock (all|full|pro)|donate|sponsor|support (me|the dev|development))\b",
         "upsell/donation text: nothing may be locked behind or advertise paid versions (ToS 3.10, 6.x)"),
        ("BLOCKER", "third-party-software", r"\bwinreg\b|\bsubprocess\.(Popen|run|call|check_call|check_output)\b|\bos\.(system|startfile|popen|exec[lv]p?e?|spawn\w*)\b",
         "external process: launching third-party software is not allowed even when optional (ToS 5.2). "
         "subprocess of Blender's own Python is fine but must forward bpy.app.python_args"),
        ("REQUIRED", "subprocess-python", r"sys\.executable(?![^\n]*python_args)",
         "sub-processes of sys.executable must pass *bpy.app.python_args (isolates from user's PYTHONPATH)"),
        ("BLOCKER", "os-tamper", r"\bos\.(kill|killpg|setpriority|chmod|chown)\b|\bctypes\.(windll|cdll|CDLL|WinDLL)\b|\bpsutil\b",
         "touching the operating system / other processes is not allowed (ToS 3.9)"),
        ("WARN", "os-tamper", r"\bos\.environ\s*\[[^\]]+\]\s*=|\bos\.(putenv|environ\.(update|setdefault|pop))\b",
         "changing environment variables changes Blender's process for everyone"),
        ("WARN", "keymap-access", r"keyconfigs\.(user|default|active)\b",
         "reads the user/default/active keyconfig. Reading it to draw the add-on's own items in preferences "
         "(rna_keymap_ui) is fine; any change to it is keymap tampering (see BLOCKER keymap-tamper hits)"),
        ("BLOCKER", "keymap-tamper", r"\bkeymap_items\.(remove|clear)\(|\b(kmi|km_item|keymap_item|keyitem|key_item|item)\.(active|type|value|ctrl|shift|alt|oskey|any|key_modifier|map_type|idname|repeat)\s*=(?!=)|\b(kmi|km_item|keymap_item|keyitem|key_item|item)\.properties\.\w+\s*=(?!=)",
         "keymap item mutation: allowed ONLY on items your add-on created in keyconfigs.addon; anything else "
         "is 'tampering with sensitive user data'"),
        ("REQUIRED", "keymap-tamper", r"\bkeyconfigs\.(import|export|new|remove)\b|bpy\.ops\.preferences\.keyconfig_|keymap_restore|keyitem_restore",
         "keyconfig import/export/restore manipulates the user's keymap"),
        ("BLOCKER", "prefs-tamper", r"\b(context|C|bpy\.context)\.preferences\.(view|inputs|edit|system|filepaths|themes|keymap|experimental|apps)\.\w+\s*=(?!=)",
         "writes Blender user preferences. Changing users' preferences is treated like keymap tampering - "
         "make it an explicit, reversible user action or remove it"),
        ("REQUIRED", "prefs-tamper", r"bpy\.ops\.wm\.save_userpref|bpy\.ops\.preferences\.(reset_default_theme|theme_install)|save_preferences",
         "saving/resetting preferences programmatically is not the add-on's call"),
        ("WARN", "handlers", r"\bbpy\.app\.handlers\.(depsgraph_update_(pre|post)|frame_change_(pre|post))\.append",
         "depsgraph/frame handlers fire constantly; moderators reject them unless essential (performance ToS 3.7). "
         "Also used to 'watch' UI state - not accepted"),
        ("INFO", "handlers", r"\bbpy\.app\.handlers\.\w+\.append",
         "app handler: make sure it is @persistent only if needed and removed in unregister"),
        ("WARN", "msgbus", r"\bbpy\.msgbus\.subscribe_rna\b", "msgbus subscription: clear it in unregister"),
        ("WARN", "stray-props", r"\bbpy\.types\.(Scene|Object|Mesh|Material|WindowManager|World|Collection)\.\w+\s*=\s*(bpy\.props\.)?\w*Property\s*\(",
         "property registered directly on an ID type. Moderators ask to collect them in one PropertyGroup "
         "(stray Scene props clutter the UI)"),
        ("WARN", "bpy-data", r"\bbpy\.data\.objects\b(?!\.new)",
         "bpy.data.objects spans all scenes/libraries; usually context.scene.objects is meant"),
        ("WARN", "bpy-data", r"\bbpy\.data\.\w+\s*\[\s*['\"][^'\"]+['\"]\s*\]",
         "hard-coded data-block name; it may not exist or may be a linked duplicate"),
        ("WARN", "paths", r"['\"][A-Za-z]:\\\\|['\"][^'\"\n]*\\\\(?![nrt'\"\\0xuU])[A-Za-z_][^'\"\n]*['\"]",
         "backslash/Windows path literal will break on Linux/macOS; use os.path.join or pathlib"),
        ("WARN", "strip", r"\.(l|r)?strip\(\s*['\"][^'\"]{2,}['\"]\s*\)",
         "str.strip with several characters strips them in any order; use removeprefix/removesuffix"),
        ("WARN", "quoting", r"['\"]\w*\[\\?['\"]\s*['\"]?\s*\+\s*\w+(\.name)?\s*\+|\[\"\{\}\"\]|\[\"\{[\w.]+\}\"\]",
         "name concatenated into a data-path/expression without escaping; use bpy.utils.escape_identifier/repr"),
        ("INFO", "bpy-ops", r"\bbpy\.ops\.(?!wm\.url_open|wm\.call_menu|wm\.call_panel|ed\.undo_push)\w+\.\w+\s*\(",
         "bpy.ops inside add-on logic is 'highly discouraged' in reviews (slow, context-dependent); "
         "prefer data API where practical"),
        ("WARN", "console", r"\b(subprocess|os)\b.*console_toggle|wm\.console_toggle",
         "toggling the system console was cited in a delisting (OS-specific, user's choice)"),
        ("INFO", "ai", r"(?i)\b(openai|anthropic|gemini|ollama|huggingface|transformers|onnxruntime|torch|tensorflow|mediapipe|stable.?diffusion)\b",
         "AI model/service code: the platform currently does not host extensions that use or connect to AI models"),
        ("WARN", "logging", r"logging\.basicConfig|\.setLevel\(\s*logging\.(DEBUG|INFO)",
         "initialising loggers by default clutters the user's console (cited in a delisting)"),
        ("INFO", "debug", r"^\s*if\s+__name__\s*==\s*['\"]__main__['\"]",
         "development entry point; moderators ask to remove debug/dev code"),
    ]

    def check_code(self):
        compiled = [(s, r, re.compile(p, re.M), msg) for s, r, p, msg in self.LINE_RULES]
        online_checked = False
        network_used = False
        keymap_none_checked = False
        keyconfigs_addon_used = False
        agg = {}
        for rel in self.py_files:
            full = os.path.join(self.root, rel)
            try:
                text = open(full, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            self.texts[rel] = text
            if "online_access" in text:
                online_checked = True
            if "keyconfigs.addon" in text:
                keyconfigs_addon_used = True
                if re.search(r"keyconfigs\.addon\s*(is\s+not\s+None|is\s+None|\)|:|\s+and|\s+or)|if\s+(not\s+)?kc\b|if\s+kc\s+is", text):
                    keymap_none_checked = True
            lines = text.splitlines()
            touches_user_kc = bool(re.search(r"keyconfigs\.(user|default|active)\b", text))
            in_doc = False
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    if not (len(stripped) > 3 and stripped.endswith(stripped[:3]) and len(stripped) >= 6):
                        in_doc = not in_doc
                    continue
                if in_doc or stripped.startswith("#"):
                    continue
                code = re.sub(r"(?<!['\"])#.*$", "", line)
                for sev, rule, rx, msg in compiled:
                    target = line if rule in ("ads", "network", "paths", "quoting") else code
                    if rx.search(target):
                        if rule == "network" and rx.pattern.startswith("^"):
                            network_used = True
                        if rule == "addon-dir-write" and not re.search(r"open\(|write|makedirs|mkdir|shutil|sys\.path|\.save|rename|remove|unlink|rmtree|copy", " ".join(lines[max(0, i - 4):i + 4])):
                            sev = "INFO"
                        if rule == "third-party-software" and "python_args" in line:
                            sev = "INFO"
                        if rule == "keymap-tamper" and sev == "BLOCKER" and not touches_user_kc:
                            # mutating items of the add-on's own keymap (keyconfigs.addon) is the normal unregister path
                            sev, msg_used = "INFO", "keymap item change in a file that only uses keyconfigs.addon - " \
                                                    "fine if these are the add-on's own items"
                            self.add(sev, rule, msg_used, rel, i, line)
                            continue
                        if rule in AGGREGATE:
                            agg.setdefault((rule, rel), [sev, msg, 0, i])[2] += 1
                            continue
                        self.add(sev, rule, msg, rel, i, line)
            self.check_ast(rel, text)
        for (rule, rel), (sev, msg, n, first) in agg.items():
            self.add(sev, rule, f"{msg} ({n} occurrence{'s' if n != 1 else ''} in this file)", rel, first)
        if network_used:
            if "network" not in (self.manifest.get("permissions") or {}):
                self.add("BLOCKER", "network", "network code present but no 'network' permission in the manifest (ToS 4.1)",
                         "blender_manifest.toml")
            if not online_checked:
                self.add("BLOCKER", "network", "network code present but bpy.app.online_access is never checked (ToS 4.2)")
        if keyconfigs_addon_used and not keymap_none_checked:
            self.add("REQUIRED", "keymaps", "wm.keyconfigs.addon is used without a None check; it is None in "
                                            "background mode (blender -b) and registration will fail")
        perms = self.manifest.get("permissions") or {}
        uses_files = any(re.search(r"\bopen\(|ExportHelper|ImportHelper|\bshutil\.|os\.makedirs|filepath", t)
                         for t in self.texts.values())
        if uses_files and "files" not in perms:
            self.add("REQUIRED", "permissions", "file-system access found but no 'files' permission",
                     "blender_manifest.toml")
        uses_clip = any("clipboard" in t for t in self.texts.values())
        if uses_clip and "clipboard" not in perms:
            self.add("WARN", "permissions", "'clipboard' used in code but no 'clipboard' permission",
                     "blender_manifest.toml")

    def check_ast(self, rel, text):
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            self.add("BLOCKER", "syntax", f"syntax error: {e.msg}", rel, e.lineno)
            return
        has_register = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in ("register", "unregister"):
                has_register = True
            # register()/unregister() defined or called inside an Operator's execute
            if isinstance(node, ast.ClassDef):
                bases = {getattr(b, "attr", getattr(b, "id", "")) for b in node.bases}
                if "Operator" in bases:
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and \
                                sub.func.attr in ("register_class", "unregister_class"):
                            self.add("REQUIRED", "registration", "register/unregister calls inside an operator "
                                     "('if users don't unregister manually everything will break')",
                                     rel, sub.lineno)
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for t in item.targets:
                                if getattr(t, "id", "") == "bl_idname" and isinstance(item.value, ast.Constant) \
                                        and isinstance(item.value.value, str):
                                    prefix = item.value.value.split(".")[0]
                                    if prefix in self.seen_prefixes:
                                        continue
                                    self.seen_prefixes.add(prefix)
                                    if prefix not in {"object", "mesh", "curve", "armature", "pose", "scene",
                                                      "view3d", "uv", "image", "node", "wm", "screen", "anim",
                                                      "graph", "action", "sequencer", "transform", "material",
                                                      "texture", "paint", "sculpt", "render", "file", "import_scene",
                                                      "export_scene", "import_mesh", "export_mesh", "gpencil",
                                                      "grease_pencil", "outliner", "clip", "text", "console",
                                                      "info", "preferences", "ui", "font", "lattice", "particle",
                                                      "rigidbody", "constraint", "collection", "geometry", "buttons",
                                                      "marker", "mball", "pointcloud", "curves", "camera", "world",
                                                      "brush", "palette", "cachefile", "boid", "cloth", "dpaint",
                                                      "fluid", "ptcache", "surface", "workspace", "view2d",
                                                      "spreadsheet", "asset", "image_paint", "uv_tools"}:
                                        self.add("INFO", "operator-prefix",
                                                 f"operator prefix '{prefix}.' is a custom category; moderators "
                                                 f"note these are 'unkeymappable from the UI' and recommend built-in "
                                                 f"prefixes (object, mesh, wm, ...)", rel, item.lineno)
        if rel == "__init__.py":
            if not has_register:
                self.add("BLOCKER", "registration", "top-level __init__.py defines no register()/unregister()", rel)
            if re.search(r"^bl_info\s*=", text, re.M):
                self.add("INFO", "manifest", "bl_info is ignored for extensions (fine to keep for legacy installs)", rel)

    # ------------------------------------------------------------------- run
    def run(self):
        self.load_manifest()
        self.walk()
        self.check_manifest()
        self.check_files()
        self.check_code()
        order = {s: i for i, s in enumerate(SEVERITIES)}
        self.findings.sort(key=lambda f: (order[f["severity"]], f["rule"], f["path"] or "", f["line"] or 0))
        return self.findings


def resolve_root(target):
    """Return (addon_dir, is_zip). Extracts a .zip to a temp dir; finds the manifest folder."""
    is_zip = target.lower().endswith(".zip") and os.path.isfile(target)
    if is_zip:
        import tempfile
        import zipfile
        tmp = tempfile.mkdtemp(prefix="ext-scan-")
        with zipfile.ZipFile(target) as z:
            z.extractall(tmp)
        target = tmp
    if not os.path.exists(os.path.join(target, "blender_manifest.toml")):
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
            if "blender_manifest.toml" in filenames:
                return dirpath, is_zip
    return target, is_zip


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    root, is_zip = resolve_root(args[0] if args else ".")
    sc = Scanner(root, include_excluded=is_zip or "--include-excluded" in argv)
    findings = sc.run()
    if "--json" in argv:
        print(json.dumps({"root": sc.root, "shipped_files": len(sc.shipped), "findings": findings}, indent=1))
        return
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    print(f"Scanned {sc.root}: {len(sc.shipped)} shipped files, {len(sc.py_files)} Python files")
    print("Summary: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    current = None
    for f in findings:
        if f["severity"] != current:
            current = f["severity"]
            print(f"\n=== {current} ===")
        loc = f["path"] or ""
        if f["line"]:
            loc += f":{f['line']}"
        print(f"[{f['rule']}] {loc}  {f['message']}")
        if f["snippet"]:
            print(f"      > {f['snippet']}")
    sys.exit(1 if counts["BLOCKER"] else 0)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except BrokenPipeError:  # output piped into head etc.
        sys.stderr.close()
