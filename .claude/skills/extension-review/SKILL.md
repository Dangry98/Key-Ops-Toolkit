---
name: extension-review
description: Pre-upload compliance review of a Blender add-on against the extensions.blender.org Terms of Service, add-on guidelines and the unwritten rules moderators enforce. Use before uploading any new version to extensions.blender.org, when asked whether the add-on is "still compatible", "follows the rules", "safe to upload", or after changes touching keymaps, preferences, networking, dependencies, packaging, threading, handlers or UI links. Violations get extensions delisted.
---

# Extension platform review

Goal: decide whether the current code can be uploaded to extensions.blender.org without being
sent back or **delisted**, and list exactly what must change. This add-on (Key Ops: Toolkit) was
delisted once already (June 2026) and is under closer watch; treat every DELIST item as release
blocking.

Read `references/rules.md` (the full rule set with severities) before judging anything, and
`references/moderation-evidence.md` for how moderators actually apply it and this add-on's own
review history. Do not soften a rule because "it was approved before": approved add-ons are
re-reviewed and delisted for things earlier reviews missed.

## Workflow

### 1. Scope the release
- Read `blender_manifest.toml` (version, permissions, tags, `[build]` excludes, wheels, platforms).
- Find what changed since the last uploaded version: the last version listed on
  https://extensions.blender.org/add-ons/key-ops-toolkit/versions/ (or ask the user), then
  `git log`/`git diff` from the matching commit or tag. Review the whole add-on, but read every
  changed line carefully: delistings usually come from something new in the latest version.
- Check `version` was bumped and follows semver.

### 2. Run the static scan
```
python3 .claude/skills/extension-review/scripts/scan.py <addon_dir>
```
It respects the manifest's build excludes (only files that will ship are scanned) and reports
BLOCKER / REQUIRED / WARN / INFO with file:line. It is a net, not a verdict:
- Open every BLOCKER and REQUIRED hit and confirm or dismiss it by reading the code. Example:
  `keymap_items.remove()` is fine when it removes this add-on's own items from
  `keyconfigs.addon` in `unregister()`, and a violation when the keymap came from
  `keyconfigs.user/default/active`.
- Skim WARN hits; fix cheap ones, note the rest.
- Things the scan cannot see: images/description, behaviour at runtime, scope creep,
  value judgements. Those are in steps 4-5.

### 3. Build, validate and run it in Blender
Use the oldest supported Blender (`blender_version_min`) and the newest release. If Blender
is not installed in this environment, download the official Linux build from
download.blender.org and verify its sha256 (see how it was done earlier in this repo's
history if needed).
```
blender --command extension validate            # manifest + tags
mkdir -p /tmp/kot-build                         # build fails if the dir doesn't exist
blender --command extension build --output-dir /tmp/kot-build
unzip -l /tmp/kot-build/*.zip                   # inspect EVERY shipped file
# isolated profile so the user's real config is never touched:
export BLENDER_USER_RESOURCES=/tmp/kot-profile
blender -b --factory-startup --command extension install-file -r user_default -e /tmp/kot-build/<zip>
blender -b --python-expr "import bpy; m='bl_ext.user_default.<id>'; bpy.ops.preferences.addon_enable(module=m); bpy.ops.preferences.addon_disable(module=m); bpy.ops.preferences.addon_enable(module=m)"
```
Any line printed with "Error" or a traceback during enable/disable is a finding.
- The zip must contain only runtime files: no `__pycache__`, `.pyc`, dev scripts
  (`zip_release.py`, icon generators), docs not loaded at runtime, `.gitignore`, tests,
  `CLAUDE.md`, `.claude/`, source art. Fix via `[build] paths_exclude_pattern`.
- Enable/disable/re-enable must produce no tracebacks in background mode (catches
  `keyconfigs.addon` being None, register-time errors, unregister leaks).
- Compare the user keymap before enable and after disable (export with
  `bpy.ops.preferences.keyconfig_export` in a scratch profile, or diff
  `[(km.name, kmi.idname, kmi.type, kmi.active) for km in wm.keyconfigs.user.keymaps for kmi in km.keymap_items]`).
  Any difference after disable means the add-on leaks or tampers with keymaps: DELIST.
- Do the same for `bpy.context.preferences` values the add-on touches.
- With a GUI available (Xvfb works), click through the main features once.

### 4. Manual checklist (confirm each; details in rules.md)
- License `SPDX:GPL-3.0-or-later`; bundled assets CC0; third-party code credited in `copyright`.
- No threading/queue/concurrent.futures; no eval/exec; no updater or update check.
- No sys.path/sys.modules/importlib loading tricks; plain relative imports; register/unregister
  modules explicitly; no class registration inside operators.
- No dependency on other add-ons (no addon_utils queries, no their operators/props/panels, no
  "install X" instructions) and no third-party programs, even optional.
- Keymaps: only own items in `keyconfigs.addon`, added in register, removed in unregister,
  guarded for None. No edits to user/default keymap items (confirm flags, active flags,
  removals, rebinding tabs). Exposing own items in preferences is fine.
- No writes to `context.preferences.*` or theme files; no saving prefs.
- No ads/social/donation/shop links or Pro/Lite mentions anywhere in Blender UI; only docs and
  bug-tracker links.
- No OS interaction (ctypes/winreg/simulated key presses/process control/console toggling).
- Network (if any): `network` permission, `bpy.app.online_access` checked before every request,
  only completely free services, no data sent without explicit user action, no AI services.
- Files written only via `bpy.utils.extension_path_user(__package__, create=True)` or user-chosen
  paths; `files` permission declared; `clipboard` permission if the clipboard is used.
- Handlers/timers/msgbus: none unless essential, all removed in unregister; nothing heavy in
  register.
- Preferences via `__package__`/`base_package`, never `__name__` or literals.
- Every feature fits the approved scope and is described on the listing (no surprises).

### 5. Listing check
- Support/Report Issues URL is a public bug tracker (GitHub issues). Manifest `support` or the
  website field.
- Tags: only directly relevant ones (moderators strike "3D View" and padding tags).
- Description: English, every feature and where to find it, no installation guide, no features
  that aren't in this version, working links.
- Images: no Blender logo, real UI screenshots, first preview a still image, no huge GIFs.
- Upload cadence: batch fixes; dozens of versions in weeks has drawn a delisting warning.

### 6. Report
Write the result for the user in this order:
1. Verdict: **Ready to upload** / **Fix before upload** / **Will be delisted** (one line why).
2. Blocking issues (DELIST-level), each with file:line, the rule (ToS number or
   "unwritten - moderator policy"), and the concrete fix.
3. Required changes (CHANGES-level).
4. Advice (worth doing, not blocking).
5. What was verified and how (scan, build contents, enable/disable test, Blender versions), and
   what was not checked.

Do not change code during the review unless asked; offer to fix the blocking items next.

## Keeping this skill current
The rules move (ToS updated Aug 2026; AI policy, threading and keymap rules tightened in 2026).
When reviewing, re-read the Terms of Service page and skim the newest moderator comments in
the approval queue (`?filter_by=awaiting-changes`); update `references/rules.md` and the scanner
when a new pattern shows up. `scripts/crawl_queue.py OUT_DIR --recent 200` fetches the most
recently active reviews (needs network access to extensions.blender.org); without `--recent` it
re-crawls everything for a full refresh of `references/moderation-evidence.md`.
