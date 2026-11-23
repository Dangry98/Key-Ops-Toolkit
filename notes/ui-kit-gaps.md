# Custom Menus UI kit: gap report

Date: 2026-11-23. Method: counted every UILayout call in Blender 5.4's own UI
(`scripts/startup/bl_ui`) and in 25 UI-heavy add-ons from extensions.blender.org
(looptools, bool_tool, copy_attributes_menu, edit_mesh_tools, f2, viewport_pie_menus,
magic_uv, print3d_toolbox, amaranth, snap_utilities_line, quick_menu, NodePie,
pie_customizer, modifier_tools, tissue, measureit, screencast_keys, MustardUI, multirow,
toolhub, sun_position, extra_mesh_objects, simple_renaming_panel, quick_n_panel,
my_best_pie_menu_ever), then checked each against `pie_menus.py` `draw_item`.

Counts are "Blender UI uses / add-on uses".

## Already covered

operator (2905/779), prop (4264/1769) as button/checkbox/expand/slider/icon view,
menu as a button, popover, label, separator (line/space), row/column/box/split/grid_flow/panel
groups with align, alignment, scale, emboss, alert, active, use_property_split,
operator call context, poll conditions, Draw Code fallback, append into Blender menus,
headers and panels, sidebar panels.

## Items: missing, by how often they are used

| # | Missing | Uses | Why it matters |
|---|---|---|---|
| 1 | Menu item inside a popup menu opens as a hover submenu (`layout.menu`) | 471/40 | Today it is a `wm.call_menu` button: the popup closes and a new one opens. Every Blender menu (Add, Select, Mesh...) uses hover submenus, so 1:1 rebuilds look and behave wrong |
| 2 | Operator enum as dropdown (`operator_menu_enum`) / all values as buttons (`operator_enum`) | 149+32/9 | Add Modifier, Select Mode, Snap To, Delete menus |
| 3 | Search field (`prop_search`) | 70/62 | Material, object, vertex group, UV map pickers. Most used add-on gap |
| 4 | Data-block selector (`template_ID`) | 105/3 | Material / world / image / action pickers with New and Open |
| 5 | List (`template_list` + UIList) | 54/37 | Material slots, UV maps, vertex groups, shape keys. 4 of 25 add-ons register UILists |
| 6 | Flexible spacer (`separator_spacer`) | 42/14 | Pushes the rest of a header row to the right |
| 7 | One enum value as a button (`prop_enum`), tabs (`prop_tabs_enum`) | 18/7 | Pivot point, shading mode buttons |
| 8 | Setting options: array index, invert checkbox, icon only, keyframe decorator (`use_property_decorate`, `prop_decorator`) | 371+24 | Properties-editor look; X/Y/Z single toggles |
| 9 | Enabled (`layout.enabled`, cannot be clicked) next to Active (greyed but clickable) | 198 | Disabled-until-ready buttons |
| 10 | Inline menu contents (`menu_contents`) | 17 | Embed another menu's items directly |
| 11 | `context_pointer_set` | 13/16 | Buttons acting on a given object or modifier |
| 12 | Templates: curve mapping, color ramp, palette, color picker, preview, image, modifier/constraint stacks | 21+8+5+4+5+4+3 | Only through Draw Code today |
| 13 | Wrapped / multi-line labels (`label_multiline`, 5.x) | 7/7 | Help text in dialogs |
| 14 | `prop_with_popover`, `prop_with_menu`, `popover_group` | 14+4+15 | Header dropdowns (snapping, proportional) |

## Containers: missing

| # | Missing | Add-on use | Note |
|---|---|---|---|
| 15 | Sub-panels (`bl_parent_id`) | 10 of 25 add-ons, 73 panels | Nested collapsible panels in the sidebar |
| 16 | Panel header content (`draw_header`: checkbox or icon in the header) | 7 add-ons, 55 | Enable toggle in the panel title |
| 17 | Panel options: start closed, hide header, order (`DEFAULT_CLOSED`, `HIDE_HEADER`, `bl_order`) | 9 add-ons, 83 | Groups have "Start Closed", the panel itself does not |
| 18 | Panels in the Properties editor tabs (`bl_context`) | | Only sidebar regions today |
| 19 | Dialog width per menu, popover width | 7 add-ons, 57 | Width comes from a formula |

## Out of scope (not layout UI)

Viewport overlays drawn with gpu/blf (8 add-ons), gizmos, workspace tools, asset shelves.
These need code and cannot be described as menu data.

## Status after the claude/ui-kit-gaps branch

Done (tests/test_kit_coverage.py rebuilds each one and checks the calls, Blender 4.2.3 and 5.4):
1 hover submenus (Menu: Draw As Automatic/Dropdown, plus Inline = menu_contents and Button),
2 operator_menu_enum / operator_enum (Operator: Draw As Dropdown/Buttons + Option),
3 prop_search (Search + Search In), 4 template_ID (Data-Block + New), 5 template_list (List, active
index guessed, rows=N in Options), 6 separator_spacer (Separator: Spacer), 7 prop_enum / prop_tabs_enum
(One Option, Tabs), prop_menu_enum (Dropdown), 8 array Index, Invert, Keyframe Button (decorate),
9 Enabled, 10 menu_contents, 12 color wheel, color ramp, curve mapping, palette, icon picker as styles,
14 prop_with_popover (With Popover + Panel). Setting paths now take bpy.data. / D. / C. prefixes and
[0] / ["name"] indexes. 15-17 (sub-panels, header icon and items, start closed, hide header, order)
were already in the snapshot.

Groups inside a pie slot: done. A Key Ops Menu item drawn as Group puts its menu's items in one
direction as a box, column or row (pie Add Group makes one). Item index still equals pie slot, so
nothing else that counts slots changed.

Still missing:
- context_pointer_set (15 add-on uses), label_multiline (5.x only, 8), template_icon (6),
  panels in Properties editor tabs (bl_context), per-menu dialog width. Draw Code covers these today.
