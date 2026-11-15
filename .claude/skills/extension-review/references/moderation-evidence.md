# Evidence from the approval queue (snapshot 2026-11-15)

Source: every add-on review page at https://extensions.blender.org/approval-queue/ (2,083 add-ons:
1,202 approved, 445 declined, 412 awaiting changes, 24 awaiting review), 4,388 moderator comments.
Most reviews are by nickberckley; others by campbell (Campbell Barton), dfelinto, Victor-09.
Re-crawl if this file is more than a few months old - policies tightened noticeably in 2026.

## How often each issue is raised (add-ons with at least one moderator comment matching)

Keyword-matched, so counts are approximate; the ranking is what matters.

| Add-ons | Issue |
|---:|---|
| 350 | Support / Report Issues link missing or not a public bug tracker |
| 278 | Description problems: installation guide, unclear features, missing UI screenshots |
| 197 | Irrelevant tags ("Remove 3D View tag") |
| 196 | depsgraph/app handlers (performance) |
| 196 | License (GPL-3.0-or-later notice, CC0 assets) |
| 165 | Development/unused files in the package; build with the CLI |
| 160 | Too small / duplicates a Blender feature / saturated category |
| 157 | Wheels, pip, split-platforms |
| 149 | threading / queue |
| 136 | Depends on or modifies other add-ons |
| 128 | Third-party software / not self-contained |
| 111 | AI models or AI-written code concerns |
| 98 | Ads, social, funding links in UI |
| 96 | sys.path / sys.modules / custom module loaders |
| 93 | `__name__` instead of `__package__` for preferences |
| 93 | bpy.ops overuse |
| 90 | "Blender" in name / Blender logo in images |
| 89 | Stray properties on Scene (use a PropertyGroup) |
| 82 | Pro/Lite versions, paid services, API keys |
| 74 | eval / exec |
| 63 | Custom operator category prefixes ("unkeymappable") |
| 51 | Writing into the add-on directory |
| 49 | OS manipulation |
| 27 | Updaters |
| 22 | Keymap manipulation beyond register/unregister |
| 22 | Missing online_access check |
| 17 | sys.executable without bpy.app.python_args |

## Why add-ons get delisted (approved add-ons pulled from the platform)

73 moderator comments announce a delisting/unlisting. A large sweep happened 18-29 June 2026,
re-reviewing the latest version of popular add-ons. Reasons, with examples:

- threading/queue: only-blends-gamepad, uvo-overlays, caustics-baking-addon, paint-system,
  open-stage-blender-dmx, shapekey-axis-control, threemf-io, univ, faster-fbx-exporter (queue counts too)
- eval/exec: math-formula, nodepie, k-tools-render-preset-manager, linkforge, thomas-rig-legacy,
  universal-multi-importer, faster-fbx-exporter
- Updaters / update checks: polyquilt-fork, povable, siemen-lens-blender-autotrack, nd, secret-paint
- sys.modules / sys.path / custom registration loaders: modifier-list-fork, chunk-render, refboard,
  open-stage-blender-dmx, key-ops-toolkit ("Import and register modules normally, and manually")
- Ads, social, funding links, Pro upsell in UI: textify, rotor, wiggle-2, nd, hyperfy-tools,
  smart-apply-scale, autocam, paint-system
- Dependencies on other add-ons: key-ops-toolkit (Set Flow, PolyQuilt_Fork, LoopTools),
  universal-multi-importer, nfc-card-keychain-generator, sidebar-tab-search
- Third-party software, even optional: arma3objectbuilder (winreg), vectart-import, threemf-io
  (Chromium), paint-system
- Keymap tampering: blenderdefender-gizmodalops ("considered a security issue"), armature-pie;
  bbrush warned that future violations mean delisting
- OS manipulation: modifier-list-fork (mouse hover via OS), threemf-io (killing processes)
- Pre-compiled C/C++ libraries: texel-density-checker, gzm-mod
- pip / wheels: references-overlays (pip instructions), only-blends-mixer (bundled `packaging`),
  linkforge (Python 3.12 wheels)
- Performance: node-runner (work in register), bioxelnodes (asset library on every register),
  blockout (draw handler leaks)
- Dev files: easymesh-batch-exporter (pytest, ruff, CLAUDE.md, tests), quick-rigid, mc-animaker
- Paid services/API keys: ftl-exporter; pexels-image-search warned
- Scope creep / no surprises: toggle-language, shapekey-axis-control
- Copyright / uncredited copying: allset (permanent), remove-loops
- Too many uploads: gp-select warned at 57 versions in 2 months
- Broken ID: 3d-cursor-snap (ID starting with a digit)

Moderator quotes that set expectations:
- "In the future add-ons will be delisted for this violation." (keymap overwrites)
- "In future something like this will result in permanent removal." (heavy registration)
- "If any future versions introduce significant issues add-on will be delisted permanently
  without a second chance." (AI-maintained add-on)
- "It seems this add-on was approved without deep enough review." (approved status is no guarantee)

## Key Ops: Toolkit history on the platform

- Jul 2024: first review required removing the "About" tab (advertising in UI). Approved.
- Jul 2024 - Apr 2026: ~40 versions uploaded without review comments.
- 26 Jun 2026: **delisted** by nickberckley with required changes: remove custom module
  registration ("Import and register modules normally, and manually"); remove dependencies on
  Set Flow, PolyQuilt_Fork and LoopTools and any panels/instructions for them; remove operators that
  duplicate Blender operators (extrude_edge_along_normals, remove_seam); remove the
  depsgraph_update_post handler tracking Outliner selection; no register/unregister inside
  operators; remove zip_release.py from the package; remove all exec/eval; general code-quality
  concerns (suspected AI code). The same day Modifier List (fork), PolyQuilt (fork) and Faster FBX
  Exporter from the same maintainer were delisted too (sys.modules + OS hover, updater,
  eval/exec + queue).
- 19 Oct 2026: resubmitted; kept extrude_edge_along_normals only below Blender 5.4.
- 21 Oct 2026: approved again. v0.2.6 uploaded 8 Nov 2026.

Consequence: this add-on is on the moderators' radar. Every upload is likely to get a secondary
review; anything from the June list reappearing, or anything in the DELIST column of rules.md,
risks another delisting - possibly permanent.
