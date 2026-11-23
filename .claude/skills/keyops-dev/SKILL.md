---
name: keyops-dev
description: Token-saving playbook for developing the Key-Ops-Toolkit Blender add-on in this repo. Use at the start of any Key-Ops code task (new feature, bug fix, shortcut, preference, pie menu, panel, operator, tool, docs sync, test run) to find the right file fast, read only what is needed, delegate searches cheaply, and finish with the required reload/docs/test steps without re-discovering them.
---

# Key-Ops development, lean

Goal: do Key-Ops work with the fewest tokens. Know where things live, read narrow
ranges, delegate wide searches, and run the fixed finish steps without rediscovering them.

## 1. Repo map (don't `ls` or Explore to rediscover this)

| Need | Go to |
|---|---|
| Feature list, categories, shortcuts, `DOCS_URL`, `PREFS_VERSION` | `features.py` (`FEATURES` tuple ~line 79, `Feature`/key dataclasses above it) |
| Registration order, deferred `finish_register` | `__init__.py` (`register()` ~line 91) |
| Preferences UI, `enable_<id>` / `keys_<id>` props, docs links | `addon_preferences.py` (`KeyOpsPreferences` ~line 121) |
| Custom pie menus data model, presets, catalog | `pie_menus.py` (3.5k lines: grep, never read whole) |
| Built-in pie menu classes | `menu/pies.py` |
| One operator per file | `operators/<name>.py` |
| Toolbar/active tools | `tools/cutter_tool.py`, `tools/fast_loop_cut.py`, `tools/merge_tool.py` |
| N-panel / Toolkit panel | `operators/toolkit_panel.py`, `ui/toolkit_paneL_ui.py` (note capital L) |
| Welcome, splash, branding, per-feature settings UI | `ui/` |
| Pref access helpers, icons | `utils/pref_utils.py` (`get_keyops_prefs`) |
| Geometry Nodes groups | `resources/node_groups.blend` via `utils/node_groups.get_node_group(name)` |
| Saved settings across reinstalls | `settings_store.py` |
| Docs site | `docs/*.html`, nav + `VERSION` in `docs/assets/site.js`, checker `docs/check_docs.py` |
| Tests | `tests/test_registration.py`, `tests/test_redesign.py` (headless) |
| Dev scripts (excluded from the build) | `scripts/reload.ps1`, `scripts/test.ps1` |

Large files (read by range only): `pie_menus.py` 3549, `tools/cutter_tool.py` 1565,
`operators/toolkit_panel.py` 1429, `operators/fast_mirror.py` 1429, `operators/uv_tools.py` 1050.

Feature model (from `features.py` docstring): every class and shortcut registers once in
`__init__.py`. Pref switches only toggle `kmi.active`; panels check the switch when drawing;
modules that change Blender itself do it in their own `set_enabled()`. A new feature therefore
needs: a `Feature(...)` entry, its module registered in `__init__.py`, prefs row + docs link,
docs section.

## 2. Reading rules

- Grep for the symbol first (`Grep` with `-n`, `output_mode: content`, small `-C`), then
  `Read` with `offset`/`limit` around the hit. Never read a file over ~300 lines whole.
- Exact file or symbol known: work inline. No subagent.
- Wide "where is X / what calls Y / all uses of Z": `caveman:cavecrew-investigator`.
- Diff or file review: `caveman:cavecrew-reviewer`.
- Bounded 1–2 file mechanical edit: `caveman:cavecrew-builder`.
- Don't re-read a file after editing it. Don't open `__pycache__`, `wheels/`, `icons/`,
  `docs/redesign/`, or `.blend` files.
- Prefer `git diff -- <path>` / `git diff --stat` over reading files to see what changed;
  main usually carries lots of uncommitted WIP, so never revert or commit unrelated files.

## 3. Finish steps (every code change)

1. **Live reload**: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/reload.ps1`
   (add `-Script <abs .py>` to also run a check script in Blender). It finds every
   VS Code-launched Blender, pings it and reloads; one line per Blender. Exit 1 means none
   reloaded, usually because Blender was started outside VS Code: tell the user, change nothing.
   Blender runs under a debugger that pauses on any raised exception, so check scripts
   must not raise (guard with checks, not try/except) and should write results to a file.
2. **Docs sync** when a feature, shortcut, preference or panel changed: edit its
   `<section class="feature" id="...">`, `shortcuts.html` if keys changed, NAV in
   `site.js` for new features, then
   `C:/Users/Daniel/AppData/Local/Programs/Python/Python310/python.exe docs/check_docs.py`.
   Docs text stays minimal: title, shortcut badge, one line, visual; rest in "More info".
3. **Headless test** only when registration, prefs or keymaps changed (about a minute):
   `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test.ps1` (default Blender 5.4;
   `-Version 4.2.3` for the minimum, `-Tests tests/test_registration.py` for one file, `-Full`
   for whole logs). It builds the working tree, installs it in a scratch profile (the user's
   config is never touched) and prints only failures plus `OK/FAIL <test> pass=N fail=N exit=N`.
   Full logs path is printed last; grep them, don't cat them. Many ops fail in `-b` only for
   lack of a 3D View; that's expected. The `ValueError: boom` traceback in `test_redesign.py`
   is an expected check. Blender 5.4 rejects raw ID-property access on add-on prefs
   (`p["x"]`, `p.get`): gate it by `bpy.app.version`, never try/except.

Never `taskkill /IM blender.exe` (user has their own sessions); kill by PID.

## 4. Compatibility guardrails (cheap to remember, expensive to debug)

- Min Blender is 4.2 (`blender_manifest.toml`); `Feature.min_version` gates newer features.
- Edit `node_groups.blend` only in the oldest installed Blender; keep group names and
  `Socket_N` identifiers.
- Check C operators with `name in dir(bpy.ops.<mod>)`, not `hasattr`.
- `POINT_UNIFORM_COLOR` / `POINT_FLAT_COLOR` builtin shaders only exist from 4.5: use
  `utils/draw_utils.point_shader()`. `tests/test_ui_draw.py` draws every panel/menu against the
  running Blender's API; run the suite with `-Version 4.2.3` as well as 5.4. Draw callbacks, modal
  handlers and status bars never run in `-b`: add `-Gui` (tests/gui_modal_smoke.py, real window,
  simulated events, fails on any traceback). `MOUSE_MMB_SCROLL` icon arrived in 4.3: pass icons
  that may be missing through `utils.utilities.safe_icon()` (it maps known stand-ins).
- Changes touching keymaps, prefs, handlers, networking, packaging: run the
  `extension-review` skill before release.

## 5. Never mention other add-ons

Never name any third-party add-on anywhere: code, comments, docstrings, UI text, `docs/`,
README, manifest, commit messages, PR titles or descriptions, issues. No comparisons ("like
<other add-on>"), no integrations, no links. Describe what Key Ops does on its own terms instead.
Only name one when the user has approved that exact mention. Approved so far: PolyQuilt in
`docs/industry-standard.html`, and the existing "based on" credit comments for borrowed code
(GPL). If a commit message would need a name, write "WIP" instead. Before every commit, check
the diff and the message for add-on names.

## 6. Output

Report results in a few lines: what changed (paths), reload/docs/test status, anything not
verified. No file dumps, no recap of the plan.
