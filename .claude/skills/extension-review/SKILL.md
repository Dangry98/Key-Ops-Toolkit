---
name: extension-review
description: Pre-upload compliance review of any Blender add-on against the extensions.blender.org Terms of Service, add-on guidelines and the unwritten rules moderators enforce. Use before submitting or updating an add-on on extensions.blender.org, when asked whether an add-on is "still compatible", "follows the rules", "safe to upload" or "ready for the extensions platform", when converting a legacy add-on to an extension, or after changes touching keymaps, preferences, networking, dependencies, packaging, threading, handlers or UI links. Violations get extensions declined or delisted.
---

# Extension platform review

Goal: decide whether an add-on can be submitted or updated on extensions.blender.org without being
sent back or **delisted**, and list exactly what must change. Works for any add-on, new or already
published. Treat every DELIST item as release blocking.

Before judging anything read `references/rules.md` (full rule set with severities and sources) and
`references/moderation-evidence.md` (how moderators apply the rules in practice). Do not soften a
rule because the add-on "was approved before": approved add-ons are re-reviewed and delisted for
things earlier reviews missed, and previously delisted add-ons get closer scrutiny.

Paths below are relative to this skill's folder (`<skill>`), wherever it is installed.

## Workflow

### 1. Locate and scope
- Find the add-on root: the folder containing `blender_manifest.toml` (it may be a sub-folder of
  the repository, and a repository may hold several add-ons - review each separately).
- No manifest, only `bl_info`? It is a legacy add-on: the review must start with conversion
  (manifest, `__package__` instead of module names, relative imports, wheels) - see
  rules.md section 11 and the manual's "Converting a Legacy Add-on into an Extension".
- Read the manifest: id, version, permissions, tags, `[build]` paths/excludes, wheels, platforms.
- New submission: review everything; also check the scope policies (rules.md section 13) - small,
  duplicated or saturated-category add-ons are declined regardless of code quality.
- Update to a published add-on: get its slug (from the manifest `website`, the platform URL, or
  ask), then:
  - read its review page `https://extensions.blender.org/approval-queue/<slug>/` for past
    moderator requests - reintroducing one is the fastest route to delisting;
  - find the last published version at `https://extensions.blender.org/add-ons/<slug>/versions/`
    and diff the source since then (`git log`/`git diff` from the matching commit or tag, if the
    project uses git). Review the whole add-on, but read every changed line: delistings usually
    come from something new in the latest version.
- `version` must be bumped versus the published one and follow semver.

### 2. Static scan
```
python3 <skill>/scripts/scan.py <addon_root>        # or a built .zip
python3 <skill>/scripts/scan.py <addon_root> --json # machine-readable
```
Standard library only (Python 3.11+ for manifest parsing). It scans only files that will ship
(honours `[build] paths` / `paths_exclude_pattern`) and reports BLOCKER / REQUIRED / WARN / INFO
with file:line. It is a net, not a verdict:
- Open every BLOCKER and REQUIRED hit and confirm or dismiss it by reading the code. Example:
  `keymap_items.remove()` is fine when it removes the add-on's own items from `keyconfigs.addon`
  in `unregister()`, and a violation when the keymap came from `keyconfigs.user/default/active`.
- Skim WARN hits; fix cheap ones, note the rest.
- The scan cannot judge images/description, runtime behaviour, scope creep or value. Steps 3-5 do.

### 3. Build, validate and run it in Blender
Use whatever Blender is available locally (any OS). Test the oldest supported version
(`blender_version_min`) and the newest release when possible. If none is installed, download an
official build from https://download.blender.org/release/ and verify it against the published
`.sha256` file. Use an isolated profile so no real user configuration is touched:
```
cd <addon_root>
blender --command extension validate                  # manifest + tags
mkdir -p <tmp>/ext-build                              # build fails if the dir doesn't exist
blender --command extension build --output-dir <tmp>/ext-build   # add --split-platforms if platforms/wheels require it
unzip -l <tmp>/ext-build/<zip>                        # inspect EVERY shipped file
export BLENDER_USER_RESOURCES=<tmp>/ext-profile       # isolated profile (set it the same way on Windows)
blender -b --factory-startup --command extension install-file -r user_default -e <tmp>/ext-build/<zip>
blender -b --python-expr "import bpy; m='bl_ext.user_default.<id>'; bpy.ops.preferences.addon_enable(module=m); bpy.ops.preferences.addon_disable(module=m); bpy.ops.preferences.addon_enable(module=m)"
```
- Any "Error" line or traceback during enable/disable is a finding (catches `keyconfigs.addon`
  being None in background mode, register-time errors, unregister leaks).
- The zip must contain only runtime files: no `__pycache__`/`.pyc`, dev or release scripts,
  generators, tests, lint/CI/packaging configs, AI-assistant files (e.g. `CLAUDE.md`, `.claude/`),
  `.gitignore`, docs not loaded at runtime, source art. Fix via `[build] paths_exclude_pattern`.
- If the add-on registers keymaps or touches preferences: run Blender with a window (a virtual
  display such as Xvfb works on Linux), snapshot
  `[(km.name, kmi.idname, kmi.type, kmi.value, kmi.active) for km in wm.keyconfigs.user.keymaps for kmi in km.keymap_items]`
  and the `context.preferences` sections it touches, enable the add-on (also with its optional
  keymap features switched on), disable it, and snapshot again. Any change to Blender's own items
  or preferences after disable is keymap/preference tampering: DELIST. The add-on's own entries
  left behind after disable are leaks: CHANGES.
- With a GUI available, click through the main features once.

### 4. Manual checklist (confirm each; details in rules.md)
- License `SPDX:GPL-3.0-or-later`; bundled assets CC0; third-party code credited in `copyright`.
- No threading/queue/concurrent.futures; no eval/exec; no updater or update check.
- No sys.path/sys.modules/importlib loading tricks; plain relative imports; register/unregister
  modules explicitly; no class registration inside operators.
- No dependency on other add-ons (no addon_utils queries, no their operators/props/panels, no
  "install X" instructions) and no third-party programs, even optional.
- Keymaps: only own items in `keyconfigs.addon`, added in register, removed in unregister,
  guarded for None. No edits to Blender's keymap items (confirm flags, active flags, removals,
  "rebind" features). Exposing own items in preferences is fine.
- No writes to `context.preferences.*` or theme files; no saving preferences.
- No ads/social/donation/shop links or Pro/Lite mentions anywhere in Blender's UI; only
  documentation and bug-tracker links.
- No OS interaction (ctypes/winreg/simulated key presses/process control/console toggling).
- Network (if any): `network` permission, `bpy.app.online_access` checked before every request,
  only completely free services, no data sent without explicit user action, no AI services.
- Files written only via `bpy.utils.extension_path_user(__package__, create=True)` or paths the
  user picks; `files` permission declared; `clipboard` permission if the clipboard is used.
- Wheels (if any): unmodified PyPI wheels under `./wheels/`, all dependencies, all supported
  platforms and Python versions, nothing Blender already bundles; `platforms` set only when needed.
- Handlers/timers/msgbus: none unless essential, all removed in unregister; nothing heavy in
  register.
- Preferences via `__package__`/`base_package`, never `__name__` or literals.
- Every feature fits the add-on's stated scope and is described on the listing (no surprises).

### 5. Listing check
- Support / Report Issues URL is a public bug tracker (manifest `support` or the website field).
- Tags: only directly relevant ones (moderators strike "3D View" and padding tags).
- Name/tagline: no "Blender" in the name; tagline ≤64 chars, no end punctuation.
- Description: English, every feature and where to find it, no installation guide, nothing that
  isn't in this version, working links.
- Images: no Blender logo, real UI screenshots, first preview a still image, no huge GIFs.
- Upload cadence: batch fixes; dozens of versions in a few weeks has drawn a delisting warning.

### 6. Report
Write the result in this order:
1. Verdict: **Ready to upload** / **Fix before upload** / **Will be declined or delisted**
   (one line why).
2. Blocking issues (DELIST-level), each with file:line, the rule (ToS number or
   "unwritten - moderator policy"), and the concrete fix.
3. Required changes (CHANGES-level).
4. Advice (worth doing, not blocking).
5. What was verified and how (scan, build contents, enable/disable and keymap test, Blender
   versions), and what was not checked.

Do not change code during the review unless asked; offer to fix the blocking items next.

## Reusing and maintaining this skill
- It is self-contained: copy the `extension-review` folder into another project's
  `.claude/skills/`, or into `~/.claude/skills/` to have it in every project. If it lives inside
  an add-on's repository, keep `.claude/` excluded from that add-on's build.
- The rules move (ToS updated Aug 2026; AI, threading and keymap policies tightened in 2026).
  When reviewing, re-read the Terms of Service and skim the newest moderator comments in the
  approval queue (`?filter_by=awaiting-changes`); update `references/rules.md` and the scanner when
  a new pattern shows up. `python3 <skill>/scripts/crawl_queue.py <out_dir> --recent 200` fetches
  the most recently active reviews (needs network access to extensions.blender.org); without
  `--recent` it re-crawls everything for a full refresh of `references/moderation-evidence.md`.
