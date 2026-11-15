# extensions.blender.org rules for add-ons

Compiled 2026-11-15 from the official pages (Terms of Service last updated 10 Aug 2026) and from
4,388 moderator comments on 2,083 add-on review pages in the approval queue. Rules marked
**[unwritten]** are not in any official document but are enforced consistently by moderators;
they are as binding in practice as the Terms of Service.

Severity used throughout:
- **DELIST**: moderators decline new submissions and unlist approved add-ons for this.
- **CHANGES**: version goes back to "Awaiting Changes" until fixed.
- **ADVICE**: commonly raised; reduces friction, sometimes becomes CHANGES.

Official sources (re-read when in doubt, they change):
- Terms of Service: https://extensions.blender.org/terms-of-service/
- Add-on guidelines: https://developer.blender.org/docs/handbook/extensions/addon_guidelines/
- Moderator review guidelines: https://developer.blender.org/docs/features/extensions/moderation/guidelines/
- Moderator canned responses: https://developer.blender.org/docs/features/extensions/moderation/canned_responses/
- Manifest schema: https://developer.blender.org/docs/features/extensions/schema/1.0.0/
- Manual, creating extensions: https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html
- Manual, add-ons (online access, __package__, local storage): https://docs.blender.org/manual/en/latest/advanced/extensions/addons.html
- Manual, Python wheels: https://docs.blender.org/manual/en/latest/advanced/extensions/python_wheels.html
- Manual, licenses / tags: .../advanced/extensions/licenses.html, .../tags.html
- CLI build/validate: https://docs.blender.org/manual/en/latest/advanced/command_line/extension_arguments.html

---

## 1. License & copyright (ToS 1)

| Rule | Sev |
|---|---|
| Add-on code must be wholly GPL compliant and declared `SPDX:GPL-3.0-or-later` (1.1). Since 2025 every add-on update must use GPL-3.0-or-later, even if code was GPL-2/MIT/ZLIB before (moderators posted this notice on 144 add-ons). | DELIST |
| Bundled images, SVGs, fonts, other assets must be CC0 / public domain (1.2). | CHANGES |
| Bundled third-party copyrighted code: credit all holders in manifest `copyright` ("Year Name" / "Year-Year Name") (1.3). | CHANGES |
| Copying code from another add-on without credit, or a "rewrite" with identical functions, gets the add-on removed **[observed: one add-on unlisted, another delisted permanently over copyright concerns]**. | DELIST |
| Add-on must not impose a license on what users create with it. **[unwritten]** | CHANGES |

## 2. Branding (ToS 2)

| Rule | Sev |
|---|---|
| The word "Blender" must not be in the extension name (2.1). | CHANGES |
| No Blender logo in thumbnails, icons, preview/featured images (2.2) - the most frequent branding request (≈25 add-ons told "Blender logo is trademarked..."). Using Blender's built-in UI icons inside the add-on UI is fine. | CHANGES, DELIST if ignored |
| No implied endorsement/affiliation with Blender (2.3). | CHANGES |
| Third-party logos only with documented permission (2.4). | CHANGES |

## 3. Content of the extension (ToS 3)

| Rule | Sev |
|---|---|
| **No surprises** (3.1): description lists everything the add-on does. Adding features unrelated to the approved scope is treated as a violation (add-ons have been unlisted for adding unrelated tools, or for bundling a different, unreviewed tool). | DELIST |
| Fully functional, documented, actively maintained (3.3). Broken registration, syntax errors, missing imports, tracebacks on enable = "Broken Add-on". | CHANGES |
| Not for internal/private/closed groups (3.4). Personal workflow toolkits without a clear theme are declined **[unwritten]**. | DECLINE |
| **No obfuscated code or byte code** (3.5): no `__pycache__`, `.pyc`, minified/renamed identifiers. | DELIST |
| **Source fully Python** (3.6): no pre-compiled C/C++ libraries, DLLs, `.so`, `.pyd`, executables (add-ons delisted for bundling C libraries). Exception granted only for hardware "driver" software. Binary wheels from PyPI are allowed (see 5). | DELIST |
| Must not hurt performance or stability (3.7). See section 8. | DELIST |
| Forks: clearly different name, significant difference, credit original authors (3.8). | CHANGES |
| **Must not tamper with the OS, third-party software, other extensions, Blender internals, or sensitive user data** (3.9). Keymaps and preferences count as sensitive user data - see section 6. | DELIST |
| No additional requirements blocking functionality: purchases, registration, payments, keys (3.10). Arbitrary limits ("1 mesh only", "max N shortcuts") count. | DELIST |

## 4. Internet (ToS 4)

| Rule | Sev |
|---|---|
| Request `network` permission with a reason (4.1). | CHANGES |
| Check `bpy.app.online_access` before every connection; do nothing online when it is False (4.2). | DELIST |
| Only connect to services that are **completely free and open to all**; free tiers of paid services, API keys for commercial services, logins to mixed offerings are rejected (4.3) ("free plans are not enough"). | DELIST |
| Buttons that only open a browser (manual, bug report) need no permission if clearly labelled (4.4). | - |
| Never send data anywhere without explicit user action (4.5). | DELIST |
| AI: extensions that use or connect to AI models/services are currently not hosted **[unwritten, stated repeatedly in 2026]**. | DECLINE |

## 5. Third-party code & software (ToS 5, add-on guidelines)

| Rule | Sev |
|---|---|
| Self-contained; never load remote code for execution (5.1). | DELIST |
| No external functional components to download, **even optional features** (5.2). This includes launching/checking for other programs (winreg lookups, Chromium, Git, slicers, "bridge" add-ons). | DELIST |
| **No dependency on other extensions, even optional** (5.3): no `addon_utils` queries, no `bpy.ops` from other add-ons, no panels showing other add-ons' properties, no "install add-on X for this feature" instructions. Add-ons have been delisted for depending on other add-ons this way. Bundling the other add-on inside yours (with credit) is the allowed alternative. | DELIST |
| Never install anything at runtime: no pip, ensurepip, downloads of modules. Python dependencies ship as wheels listed in the manifest (unmodified PyPI wheels, all dependencies included, under `./wheels/`). | DELIST |
| Platform-specific wheels: declare `platforms`, build with `--split-platforms`, upload one zip per platform. Do not declare `platforms` when nothing is platform-specific. | CHANGES |
| Do not ship wheels Blender already bundles (e.g. `packaging` - cited in a delisting), or for Python ABIs no supported Blender uses. | DELIST |
| Only load modules into the add-on's own namespace: no `sys.path`/`sys.modules`/`site` manipulation, no `importlib` loading from paths, no custom module "auto-registration" frameworks that touch `sys.modules` (several delistings). "Import and register modules normally, and manually." | DELIST |
| Sub-processes of Blender's Python must forward `*bpy.app.python_args` with `sys.executable`. | CHANGES |
| Add-ons produced by visual add-on generators are not accepted. **[unwritten]** | DECLINE |

## 6. Keymaps, preferences, other add-ons **[unwritten - strictly enforced]**

Quotes: "Modifying keymaps is not allowed. You can register and unregister them. No other
modification besides that will be allowed." / "keymaps are very sensitive data and we do not host
extensions [that] modify them" / "Do not temper with peoples keymap and preferences."

| Rule | Sev |
|---|---|
| Keymaps: only `keyconfigs.addon` items created in `register()` and removed in `unregister()`, exactly like the official tutorial. Nothing else: no editing, disabling, deleting or "rebinding" items in `keyconfigs.user/default/active`, no conflict finders/resolvers, no custom keymap import/export, no operators that change shortcuts, no restore logic (an add-on was unlisted for this; another was warned "add-ons will be delisted for this"). | DELIST |
| Exposing your own keymap items in the add-on preferences (rna_keymap_ui) is allowed and recommended for add-ons that assign many keys. | - |
| Do not assign default keys for niche operators ("does not need a forced keymap"); do not overwrite common default keys. | CHANGES |
| `wm.keyconfigs.addon` is None in background mode - guard it. | CHANGES |
| Operators with a custom `bl_idname` category (e.g. `myaddon.op`) are "unkeymappable from the UI"; moderators recommend built-in categories (`object.`, `mesh.`, `wm.` ...). Raised on ≈60 add-ons; advisory. | ADVICE |
| Do not write user preferences (`context.preferences.view/inputs/edit/... = ...`), save/load prefs, reset themes, or edit theme XML. | DELIST |
| Never enable/disable/install/uninstall/modify other add-ons or extensions, clear their handlers, or import their modules (plugin managers declined; an add-on was warned for clearing others' handlers). | DELIST |
| No "uninstall" or alternative installer operators - Blender manages add-ons. | DELIST |

## 7. Advertising (ToS 6)

| Rule | Sev |
|---|---|
| No ads, shop links, donation/funding buttons, Patreon/Gumroad/Ko-fi, social media (YouTube, Discord, X, Facebook) or "About/credits" upsell panels inside Blender's UI (6.1). Allowed: documentation and bug tracker links. Funding links may go in the platform description. An "About" tab with promotional links was required to be removed for this. | DELIST |
| No "Pro"/"Lite" split: no locked features, no detection of other editions, no mention of commercial versions in UI, description or images (6.2, 6.3) (add-ons unlisted for this). | DELIST |
| No in-UI update/promotion notifications (6.3) - "notifications will be considered advertisement". | DELIST |
| Description/images only show features of the hosted version (6.2). | CHANGES |

## 8. Stability & performance (ToS 3.7)

| Rule | Sev |
|---|---|
| **No `threading` or `queue`** (also `concurrent.futures`) - "known crashers"; >10 approved add-ons delisted for this in June 2026 alone. Use `subprocess`/`multiprocessing`, `bpy.app.timers`, modal operators. | DELIST |
| **No `eval()`/`exec()`** - security; delisted on sight in 2026. Use getattr/setattr, JSON, `ast.literal_eval`. | DELIST |
| No self-updaters, update checks, "check for updates" buttons, release polling. | DELIST |
| Avoid `depsgraph_update_*`/frame handlers unless essential; never use them to watch UI/outliner state. Remove every handler/timer/msgbus in `unregister()`. | CHANGES / DELIST |
| No heavy work in `register()` ("In future something like this will result in permanent removal"); no adding/removing asset libraries on every register. | DELIST |
| No register/unregister of classes inside operators or at runtime ("if users don't unregister manually everything will break"). | CHANGES |
| Don't register stray properties directly on `Scene`/`Object`/... - group them in one PropertyGroup. | CHANGES |
| Don't spam the console; no default logger setup, no system console toggling. | CHANGES |

## 9. Files & storage

| Rule | Sev |
|---|---|
| Never write into the add-on's own directory (read-only "System" repos, wiped on update). Use `bpy.utils.extension_path_user(__package__, create=True)`. | DELIST |
| Never build `sys.path` entries from `__file__`. | DELIST |
| No backslash path literals or absolute Windows paths (`C:\`). | CHANGES |
| `files` permission when reading/writing files outside Blender's own file browser flows (all I/O add-ons). `clipboard` permission when using `window_manager.clipboard`. | CHANGES |
| Package only what the add-on uses: build with `blender -c extension build`; exclude dev files (CLAUDE.md, tests, ruff/pytest/pyproject, `.gitignore`, `zip_release.py`, source art, docs not loaded at runtime, unused images). Raised on ≈165 add-ons; cited in several delistings. | CHANGES / DELIST |

## 10. Code correctness (moderator checklist)

| Rule | Sev |
|---|---|
| `__package__` (or `from .. import __package__ as base_package`) for preferences - never `__name__`, never a literal module name; never modify `__package__`. Raised on ≈93 add-ons. | CHANGES |
| Relative imports inside the package; no `bl_ext`, `user_default`, `blender_org` literals. | CHANGES |
| Escape names in data-paths (`bpy.utils.escape_identifier`) and expressions (`repr`/`!r`). | ADVICE |
| `str.strip(".json")` strips characters, not suffixes - use `removesuffix`. | ADVICE |
| Prefer `context.scene.objects` over `bpy.data.objects`; avoid hard-coded data-block names. | ADVICE |
| Prefer data API over `bpy.ops` in add-on logic; don't register operators that merely wrap an existing operator. | ADVICE / CHANGES |
| Must work on every supported Blender version (check API breaks for 4.x/5.x, e.g. removed `layout_type`); set `blender_version_max` when it doesn't. | CHANGES |
| Code generated by AI is scrutinised: unused imports, dead code, redundant try/except, "usual AI suspects" lead to CHANGES; moderators said AI-maintained add-ons that introduce issues may be delisted permanently. | CHANGES / DELIST |
| Run `ruff check --ignore=E402,E741,E731`; many unused imports/undefined names are a red flag. | ADVICE |

## 11. Manifest (schema 1.0.0) and legacy conversion

Legacy add-ons (with `bl_info`, no manifest) must be converted first: add `blender_manifest.toml`;
`bl_info` is ignored (may stay for legacy installs); replace every hard-coded module name with
`__package__` (sub-packages: `from .. import __package__ as base_package`); make all intra-package
imports relative; bundle third-party modules as wheels; install from disk and test.


Required: `schema_version="1.0.0"`, `id` (valid identifier, no leading digit - an add-on had to
resubmit under a new ID), `version` (semver), `name`, `tagline` (≤64 chars, no end punctuation), `maintainer`,
`type`, `blender_version_min` (≥4.2.0), `license`. Optional values must be omitted rather than
empty. `permissions` reasons: one sentence, ≤64 chars, no trailing period. `[build.generated]` is
reserved. Valid tags only - and only relevant ones ("Remove 3D View tag" is the single most common
tag note; "do not abuse our tags system for more exposure").

## 12. Store listing

| Rule | Sev |
|---|---|
| **Support / "Report Issues" link must point to a public bug tracker** (GitHub issues, forum thread). Not e-mail, not Twitter, not the docs site. The most common change request on the platform (≈350 add-ons). Set `support` in the manifest or the website field. | CHANGES |
| No installation guide in the description ("All extensions install the same way"). | CHANGES |
| Description in English, explains every feature and where it is in the UI; screenshots of the UI; first preview should be a still image, not a grey video frame; no heavy GIFs. | CHANGES |
| Website/documentation links must work (404s are flagged). | CHANGES |
| Don't spam updates: "You uploaded 57 versions in 2 months. If this goes on we will be delisting." | DELIST risk |

## 13. Scope policies for new submissions **[unwritten]**

Declined categories (relevant when splitting features into separate add-ons): very small add-ons
(one operator, saves one click, possible with keymap/quick favourites), features already in
Blender, saturated categories (bake helpers, mesh checkers/cleanup, origin tools, camera managers,
render queues, overscan), personal toolkits without a theme, things that only move UI elements,
assets that should be asset libraries, script executors (MCP etc.), AI tools, OS utilities.
