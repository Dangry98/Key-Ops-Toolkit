# Evidence from the approval queue (snapshot 2026-11-15)

Source: every add-on review page at https://extensions.blender.org/approval-queue/ (2,083 add-ons:
1,202 approved, 445 declined, 412 awaiting changes, 24 awaiting review), 4,388 moderator comments.
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

## Why approved add-ons get delisted

73 moderator comments announce a delisting/unlisting. A large sweep happened in late June 2026,
re-reviewing the latest version of popular add-ons; several maintainers lost multiple add-ons the
same day. Reasons seen, roughly by frequency:

- threading/queue modules (also `queue` alone - "it uses threading under the hood")
- eval/exec
- Updaters, update checks, alternative installers, uninstall operators
- sys.modules / sys.path manipulation, custom module auto-registration
- Ads, social media, funding links, Pro upsell or in-UI notifications
- Depending on, importing from, or querying other add-ons
- Third-party software, even optional or disabled by default (registry lookups, browsers, Git)
- Keymap tampering (rewriting or failing to restore users' keymaps - "considered a security issue")
- OS manipulation (killing processes, OS-level mouse/keyboard events, toggling the system console)
- Pre-compiled C/C++ libraries
- pip install instructions, wheels already bundled with Blender, wheels for unused Python versions
- Heavy work in register(), asset libraries added on every register, leaking draw handlers
- Development files in the package (CLAUDE.md, tests, pytest/ruff configs, release scripts, source art)
- Connecting to services that are not completely free / API keys
- Scope creep: features unrelated to the approved title added in an update
- Copyright concerns or uncredited copying (one permanent delisting)
- Excessive uploads (warning after 57 versions in 2 months)
- Invalid extension ID (starting with a digit) - had to resubmit as a new extension

Moderator quotes that set expectations:
- "In the future add-ons will be delisted for this violation." (keymap overwrites)
- "In future something like this will result in permanent removal." (heavy registration)
- "If any future versions introduce significant issues add-on will be delisted permanently
  without a second chance." (AI-maintained add-on)
- "It seems this add-on was approved without deep enough review." (approved status is no guarantee)

## Typical change list on a delisted add-on

A representative delisting comment from the 2026 sweep asked, in one go, to:
- remove a custom module-registration system ("Import and register modules normally, and manually")
- remove every dependency on other add-ons, including panels showing their properties and
  instructions to install them
- remove operators that duplicate existing Blender operators ("Just access those operators")
- remove a depsgraph_update_post handler used to track UI selection
- stop defining register/unregister inside operators
- exclude a release/zip script from the package
- remove all exec/eval
and noted general code-quality concerns (suspected AI-generated code). The add-on was approved
again after all items were fixed.

Consequence: once an add-on has been delisted, every later upload is likely to get a secondary
review. Anything from that change list reappearing, or anything in the DELIST column of
rules.md, risks another delisting - possibly permanent.
