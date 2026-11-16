# Key Ops: Toolkit 1.0 — "Quiet by default" redesign

Status: proposal · Scope: preferences window, shortcuts, pie menus, Rebind, N-panel, first-run experience, and the registration code behind them. Feature set stays the same.

Interactive mockups: [`mockup.html`](./mockup.html) (open in a browser).

---

## 1. Why

The most common complaint is that the add-on does too much the moment it is installed: it turns on a lot of features and takes over keys people already use. The code backs that up:

| Finding | Where |
|---|---|
| **26 of 31** `enable_*` features are on at first install | `addon_preferences.py:554-585` |
| About **100 keymap entries** go live on install, across 20 features | `operators/*`, `tools/*`, `menu/pies.py` |
| Many of them replace Blender defaults: `1` (vertex select mode), `Delete` (delete menu), `D` (annotate), `Shift+S` (snap pie), `Ctrl+E` (edge menu in Edit Mode, via *3D View Generic*), `Alt+C` (convert), `Alt+M` (split), `Alt+V` (rip fill), `Alt+LMB` (loop select), outliner click and right-click, right-click in the UV editor | see the keymap inventory in §4 |
| The Rebind tab edits `keyconfigs.user` directly and writes `preferences.view.pie_animation_timeout` | `operators/rebind.py`, `addon_preferences.py:412-488` |
| Maya Pivot disables a Grease Pencil item in the user keymap, and Retopology rewrites the 3D View theme | `operators/maya_pivot.py:168-172`, `operators/toggle_retopology.py:51-271` |
| The tabs rename and reorder themselves at 705 px of window width, using module-level `do_once` globals | `addon_preferences.py:14-97` |
| The Keymaps tab sorts entries into "Operations" and "Pie Menus" by looking for `"PIE"` in a variable name, plus a hand-kept ignore list | `addon_preferences.py:491-526` |
| Adding a feature means touching 4 places: a `BoolProperty`, a draw tuple, a 250-line `if/elif` in `__init__.py`, and the keymap source list in `pref_utils.py` | `__init__.py:28-250`, `utils/pref_utils.py:86-130` |
| No first-run guidance. A new user lands in a list of 31 toggles with unexplained badges | — |
| Typos in the UI: *Seperate, Atributes, Matieral, Primitivs, Modifers, Defualt, Cusomize* | various |

There is also a hard constraint. The extensions.blender.org moderation rules this repo follows (`.claude/skills/extension-review/references/rules.md` §6) say:

- Add-ons may only create their own items in `keyconfigs.addon` in `register()` and remove them in `unregister()`.
- They may not edit, disable or rebind items in `keyconfigs.user/default/active`, ship conflict finders or resolvers, or include operators that change shortcuts.
- They may not write `context.preferences.*` or themes.
- They should not overwrite common default keys or force keys onto niche operators.

Rebind, the Maya Pivot Grease Pencil tweak, the pie timeout button and the retopology theme swap all break these rules and can get the add-on delisted. The redesign has to fix that, not only tidy it.

## 2. Principles

1. **Quiet by default.** A fresh install adds tools, panels and menu entries. It binds no keys until the user picks a shortcut style.
2. **Features and shortcuts are separate switches.** A feature can be on while its keys are off. Everything is still reachable from the N-panel, the menus and F3.
3. **Every key states its impact.** Each shortcut is labelled *Free* (unused in Blender's default keymap) or *Replaces "X"*, and the label lives in the feature's declared data, not in a runtime conflict scanner, which the rules don't allow.
4. **One place to learn, one place to change.** The preferences window explains, the N-panel does, and a cheat sheet shows what is active right now.
5. **One source of truth in code.** A single feature registry drives registration, preferences, the Shortcuts tab, the welcome screen, the cheat sheet and the docs links.
6. **Never surprise existing users.** Upgrades keep the current setup exactly as it is.

## 3. Information architecture

### 3.1 Feature taxonomy

The current sections (Industry Standard, Toolkit, Tools, Pies, Extras, Legacy) mix *where a feature lives* with *where it came from*. The new groups follow where the user meets the feature:

| Category | Features |
|---|---|
| **Modeling** | Merge Tool, Fast Loop Cut, Cutter Tool, Merge / Connect, Auto Delete, Flatten Pie, Attribute Operations, LoopTools menu |
| **Object & Modifiers** | Object Toolkit (panel), Modifier Keys, Material Utils, Smart Apply Scale, Fast Mirror / Booleans |
| **Pie Menus** | Add Objects, Add Modifier, Cursor & Origin, Workspace, Utility, UV pies |
| **Navigation & Selection** | Alt Navigation, Maya Pivot, Select Island (double-click), Retopology toggle |
| **UV** | UV Tools, UV pies (also listed under Pie Menus) |
| **Pipeline** | Quick Export, Quick Bake Name, Auto LOD, CAD Decimate, Polycount List |
| **Interface** | Viewport Menu, Outliner Options, Legacy shortcuts, Legacy collection keys |

The word "Extensions" goes away inside the add-on, because Blender already uses it for packages. They become **Features**.

### 3.2 Impact levels

Each feature declares one impact level, shown as a badge:

| Level | Meaning | Badge |
|---|---|---|
| **UI only** | Panels, menu entries, toolbar tools, F3 operators. No keys. | grey "UI" |
| **Adds keys** | Binds only key combos that are free in Blender's default keymap. | blue "⌨ 3 keys" |
| **Replaces keys** | Rebinds at least one Blender default (always through `keyconfigs.addon`). | amber "Replaces Delete menu" |

### 3.3 Shortcut styles (profiles)

Picked on the welcome screen and changeable from the Home tab. A style is a preset that sets `enabled` and `keys_enabled` for every feature. After that the user can change any single feature, and the Home tab shows "Blender+ (modified)".

| Style | Features on | Keys on | For |
|---|---|---|---|
| **Essentials** *(default for new installs)* | All UI-only features, plus feature cores whose keys are switched off | none | "I just want the tools." |
| **Blender+** | Same as Essentials | Keys on free combos only: Add Objects pie `Shift+Alt+A`, Add Modifier pie `Shift+Q`, Flatten `Alt+3`, Modifier Keys in the Properties editor, Quick Export as an Object Mode-only key | Blender users who want speed without losing muscle memory |
| **Industry** | Everything | Everything, including replacements: Alt navigation, `D` pivot, `Delete`, double-click island, `1` merge, `Shift+S` pie | Maya / Max / Modo users. Matches what 0.2.x ships today. |
| **Custom** | You choose | You choose | Opens Features |

**Upgrade rule.** If saved preferences exist and `prefs_version < 2`, the style becomes **Custom (kept from 0.2.x)** and nothing changes. The "What's new" dialog explains the new tabs and offers Essentials for anyone who wants to trim down.

## 4. Preferences window

Four tabs instead of three shape-shifting ones: **Home · Features · Shortcuts · Pie Menus**. They no longer change with window width. Narrow windows stack columns using `context.region.width` instead of scanning every window.

### 4.1 Home
- Current shortcut style as four large toggle buttons, plus "modified" state.
- Status line: *14 features on · 9 shortcuts active · 2 replace Blender keys*.
- **Pause all Key Ops shortcuts**: one switch that unregisters every Key Ops keymap item and leaves the features running. This is the first thing to try when "my key stopped working". The same switch is in the N-panel ⋯ menu.
- Buttons: Show welcome again · Open docs · What's new · Report a problem.
- **Blender settings we recommend** (replaces the "pie timeout" button): text plus a docs link explaining where to set *Interface → Editors → Pie Menus → Animation Timeout*. Nothing is written for the user.

### 4.2 Features
- Left column: category list, drawn as a vertical `prop(..., expand=True)` of a category enum, which looks like a sidebar.
- Top row: search field, plus a filter for *All / On / Off / Uses keys / Replaces keys*.
- One card per feature:
  - Header: `[✓] Name   [impact badge]   [?]docs   [▸]settings`
  - One-line description in plain words. The current descriptions double as docs links. In the new cards they become a label, and the `?` button is the link.
  - Expanded: the feature's settings (today these only appear when enabled, scattered through the page), then its keys with their own "Use shortcuts" switch.
- Experimental and WIP features sit behind one "Show experimental" filter chip instead of the hidden `experimental` property.

### 4.3 Shortcuts
- Grouped **by feature**, then by editor. No more string-matching on `"PIE"`.
- Each row shows the key, action, editor, impact (*Free* / *Replaces "Delete menu"*) and an active toggle, drawn with `rna_keymap_ui.draw_kmi` so the user can still rebind every Key Ops item. The moderation rules explicitly allow exposing your own keymap items like this.
- Search by action name or key.
- Per feature: **Restore defaults** (Key Ops' own items only).
- A header note: "Key Ops only adds shortcuts on top of yours. Turning a shortcut off brings back Blender's."

### 4.4 Pie Menus
- One card per pie with a small 8-slot diagram of what is on it, its key, an enable switch and its settings (for example, the Add Objects pie's relative scale and custom .blend object).
- Optional "Also use on Blender's key" entries replace the old Rebind buttons. Example: *Add Objects pie on Shift+A (replaces the Add menu)*. This registers a **Key Ops** keymap item in `keyconfigs.addon` and never edits the user's keymap. It is off by default and disappears cleanly when turned off or uninstalled.

### 4.5 What happens to Rebind

| Today | New |
|---|---|
| Rebind right-click / W context menu (edits user keymap) | Optional Key Ops keymap item "W → context menu" in Shortcuts › Interface. Off by default. |
| Add menu ↔ Shift+Alt+A (edits user keymap) | Pie Menus › Add Objects › "Also on Shift+A" |
| Space → View Camera pie (edits user keymap) | Pie Menus › View Camera › "Also on Space" (Play stays on Shift+Space via the same addon item) |
| No-lag pie timeout (writes preferences) | Home › Recommended settings (text and docs link only) |

Two related changes:
- **Maya Pivot** no longer touches the Grease Pencil keymap. It registers its `D` item in the more specific keymaps where it needs to win.
- **Retopology** stops rewriting the theme. It uses overlay settings that live in the scene or space data, or draws its own wire color with a GPU draw handler.

## 5. Welcome screen

Shown once after the first install (`prefs.welcome_version < WELCOME_VERSION`), opened through `bpy.app.timers.register(..., first_interval=0.5)` so it appears after the UI has loaded. It is an `invoke_props_dialog(width=560)` operator with a `step` property. "Next" re-invokes it at the next step.

1. **Welcome.** One sentence: "Key Ops adds modeling tools, pie menus and panels. Nothing changes your shortcuts until you choose." Then the four style cards: *Essentials* (recommended), *Blender+*, *Industry* and *Custom*.
2. **Review.** Lists exactly which keys the chosen style adds and which Blender keys it replaces, each with a checkbox. This is the consent step the complaint calls for.
3. **Where to find things.** The N-panel **Key Ops** tab (`N` in the 3D View), F3 → "Key Ops", the cheat sheet (`?` in the N-panel header) and the Preferences location. Buttons: *Open N-panel* and *Done*.

On upgrade, a single-page **What's new** dialog replaces the full welcome. It has a *Keep my setup* button (default) and *Switch to Essentials*.

## 6. N-panel

- **One tab, "Key Ops"** (renamable, one setting for both 3D View and UV editor). Today the tab is "Toolkit", a generic name other add-ons also use, and the UV editor tab has its own separate setting.
- Native subpanels (`bl_parent_id`, `DEFAULT_CLOSED`) replace the custom icon-only enum toggle row (`toolkit_panel_mode`). Users get the collapse, drag-to-reorder and pin behaviour Blender already provides.
- **Mode-aware.** Object Mode shows *Object*, *Modifiers* and *Retopology*. Edit Mode shows *Mesh*, *Selection*, *UV* and *Attributes*. *Pipeline* (Bake Names, Export, LOD, CAD Decimate, Polycount) is one collapsed parent panel with child panels, so the long pipeline tools stop pushing modeling tools down.
- Header: mode label, a `?` button for the cheat sheet (a popup listing the active Key Ops shortcuts for the current mode) and a `⋯` menu (Pause shortcuts, Preferences, Docs).
- Buttons keep their current icons. The row sizing (`scale_y = 1.4`) moves into one helper so every section matches.

## 7. Code architecture

### 7.1 Feature registry

```python
# features/registry.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Key:
    keymap: str              # "Mesh", "3D View Generic", ...
    idname: str
    type: str
    value: str = "PRESS"
    ctrl: bool = False; shift: bool = False; alt: bool = False
    props: tuple = ()        # (("name", "KEYOPS_MT_add_pie"),)
    replaces: str = ""       # "Delete menu" -> amber badge; "" -> free
    space_type: str = "EMPTY"; region_type: str = "WINDOW"

@dataclass(frozen=True)
class Feature:
    id: str                  # "auto_delete" -> prefs.enable_auto_delete (kept for compat)
    name: str
    category: str            # "MODELING", "PIES", ...
    description: str
    docs: str
    module: str              # "operators.auto_delete"
    keys: tuple[Key, ...] = ()
    styles: frozenset = frozenset({"ESSENTIALS", "BLENDER_PLUS", "INDUSTRY"})
    key_styles: frozenset = frozenset({"INDUSTRY"})
    min_blender: tuple = (4, 2, 0)
    experimental: bool = False

FEATURES = (
    Feature("auto_delete", "Auto Delete", "MODELING",
            "Delete in Edit Mode removes what you selected, with no menu.",
            "industry-standard.html#auto-delete", "operators.auto_delete",
            keys=(Key("Mesh", "keyops.auto_delete", "DEL", replaces="Delete menu"),)),
    # ... one entry per feature
)
```

### 7.2 One generic lifecycle

```python
# features/lifecycle.py
import importlib
from .registry import FEATURES
_live_keys: dict[str, list] = {}

def enable(f):
    mod = importlib.import_module(f".{f.module}", __package__.rpartition(".")[0])
    mod.register()                      # classes, panels, menus, handlers: no keymaps
    if prefs().keys_enabled(f.id) and not prefs().pause_shortcuts:
        register_keys(f)

def register_keys(f):
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:                      # background mode
        return
    items = []
    for k in f.keys:
        km = kc.keymaps.new(k.keymap, space_type=k.space_type, region_type=k.region_type)
        kmi = km.keymap_items.new(k.idname, k.type, k.value, ctrl=k.ctrl, shift=k.shift, alt=k.alt)
        for name, val in k.props:
            setattr(kmi.properties, name, val)
        items.append((km, kmi))
    _live_keys[f.id] = items
```

`importlib.import_module` with a relative name inside the add-on's own package is ordinary importing. It does not load from paths or touch `sys.modules`, so it stays clear of the "auto-registration frameworks" rule. A plain explicit dict of `id → module` also works if moderators prefer it.

This removes:
- the 250-line `extension_register_unregister` `if/elif`,
- the `registered_*_keymaps` globals and the `_iter_registered_keymap_sources` reflection,
- the `"PIE"` string sorting and the ignore list,
- the hand-written `maya_data`, `pie_data`, `Extra_data` and similar draw tuples.

The preferences UI, the Shortcuts tab, the welcome "Review" step, the cheat sheet and the docs site's shortcut table all read `FEATURES`.

### 7.3 Preferences storage

- Keep `enable_<id>` `BoolProperty`s so existing saved preferences still load. Add `keys_<id>` `BoolProperty`s, generated in a loop into `__annotations__` before the class is registered.
- Per-feature settings move into `PointerProperty(type=<Feature>Settings)` groups over time. A `prefs_version` int drives a one-time copy from the old flat names.
- New: `shortcut_style` enum, `pause_shortcuts`, `welcome_version`, `ui_category`, `ui_search`, `ui_filter`.
- Each feature card's expanded state lives in a `WindowManager` collection, so opening a card never marks preferences as changed.

### 7.4 Layout

- Remove `get_window_with()` and the `do_once_over705` / `do_once_under705` globals. Use `context.region.width` once per draw to pick one or two columns. The tab list stays fixed.
- Put shared UI helpers in `ui/widgets.py`: `feature_card()`, `impact_badge()`, `key_row()`, `section()`.

### 7.5 Compliance fixes (blocking for 1.0)

1. Delete `operators/rebind.py`. Replace it with addon-keymap items as described in §4.5.
2. Remove the Grease Pencil `kmi.active = False` from Maya Pivot, and the user-keymap scans in `auto_delete.py` and `maya_navigation.py`.
3. Remove theme writes from Retopology.
4. Guard `keyconfigs.addon is None` everywhere. The registry does this in one place.
5. Over time, rename operators from `keyops.*` to built-in categories (`mesh.keyops_*`, `object.keyops_*`) so users can keymap them from the UI. The registry makes this a one-file change for keys.

## 8. Rollout

| Phase | Ship | Risk |
|---|---|---|
| 1 | Registry and generic lifecycle behind the current UI. No visible change. | Low. Verify with enable/disable snapshot tests. |
| 2 | Compliance fixes (§7.5) and the Pie Menus "Also on Blender's key" items | Medium. Changes Rebind users' workflow, so it's covered in What's new. |
| 3 | New preferences window (Home, Features, Shortcuts, Pie Menus) | Low |
| 4 | Welcome, What's new, shortcut styles; Essentials becomes the default for new installs | Low for upgraders, since they keep their setup |
| 5 | N-panel restructure and cheat sheet | Low |
| 6 | Docs site generated from `FEATURES` (shortcut tables stay in sync) | Low |

## 9. Open questions

1. Is **Blender+** worth keeping, or is Essentials / Industry / Custom enough?
2. Should the N-panel tab be named **Key Ops** or stay **Toolkit**?
3. Quick Export on `Ctrl+E`: limit it to Object Mode (free) in Blender+, and keep *3D View Generic* (replaces the Edge menu) only in Industry?
4. Outliner Options replaces left and right click in the Outliner. Should it move to Industry only?
