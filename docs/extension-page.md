Industry standard tools and shortcuts for Blender: Maya-style navigation and selection, fast interactive modeling tools, pie menus and a game-art toolkit.

**Every feature can be turned on or off** in *Edit > Preferences > Add-ons > Key Ops: Toolkit*. No restart needed.

[Documentation](https://dangry98.github.io/Key-Ops-Toolkit/) · [Shortcut Cheat Sheet](https://dangry98.github.io/Key-Ops-Toolkit/shortcuts.html) · [Source on GitHub](https://github.com/Dangry98/Key-Ops-Toolkit)

---

## Industry Standard

Navigation and selection that work like Maya and 3ds Max.

- **Alt Navigation** (`Alt` + mouse): orbit, pan and zoom like Maya in the 3D Viewport, UV, Image and 2D editors. Optional tablet mode.
- **Double-Click Select** (double-click): select an island or edge loop. `Shift` adds, `Ctrl` deselects. Works on meshes, UVs and curves.
- **Auto Delete** (`Delete`): delete the selection without the menu, with optional dissolve in edge mode.
- **Maya Pivot** (`D`): move and rotate the pivot in place. Hold or toggle.
- **Toggle Retopology** (`5`): one key for a full retopology setup (tool, theme, snapping). Press again to go back.

![Double-click to select an island](https://dangry98.github.io/Key-Ops-Toolkit/assets/notion/select-island.gif)

![Maya-style pivot on D](https://dangry98.github.io/Key-Ops-Toolkit/assets/notion/maya-pivot.gif)

[More on Industry Standard](https://dangry98.github.io/Key-Ops-Toolkit/industry-standard.html)

---

## Modeling Tools

Fast, interactive tools. While a tool runs, its keys are listed in the status bar.

![Merge Tool](https://dangry98.github.io/Key-Ops-Toolkit/assets/gifs/merge-tool.gif)

- **Merge Tool**: drag a vertex or edge onto another to merge them. Supports multi-merge and merge to center, and keeps UVs intact.
- **Fast Loop Cut** (`Alt R`): hover to preview, click to cut. No slide step. Even, center and edge-flow modes.
- **Cutter**: draw a box, circle or ngon to cut (difference, union, intersect, slice) or add geometry. The boolean is only added on release, so drawing stays fast on heavy meshes.
- **Fast Mirror** (`Alt X`): click a block to mirror on that axis. Hold a modifier key to bisect, symmetrize or flip instead.
- **Fast Bevel, Array and Solidify**: drag and scroll to set up modifiers interactively from the Add Modifier pie.
- **Booleans** (`Ctrl Numpad - + * /`): difference, union, intersect and slice on the selection.
- **Snap to Floor** (`Alt 3`), **Select Similar** and **X-Ray Select**.

![Snap to Floor](https://dangry98.github.io/Key-Ops-Toolkit/assets/gifs/snap-to-floor.gif)

[More on Modeling Tools, with videos](https://dangry98.github.io/Key-Ops-Toolkit/modeling-tools.html)

---

## Toolkit Panel

Everything lives in the **Toolkit** tab of the 3D Viewport sidebar (`N`).

![Object Toolkit](https://dangry98.github.io/Key-Ops-Toolkit/assets/shots/toolkit-object.png)

- **Object Toolkit**: combine and separate while keeping normals and UVs, fast apply modifiers (`Alt C`), parent used objects.
- **Freeze Scale**: apply object scale without breaking modifiers. Modifier values are adjusted so the shape stays the same, including Geometry Nodes inputs.
- **Duplicate Linked Modifiers**: duplicates share one modifier stack. Add modifiers on top to override single objects.
- **Live Booleans**: pause boolean evaluation while you move objects and resume when you confirm. Keeps heavy boolean stacks responsive.
- **Edit Toolkit**: subdivide and un-subdivide cylinders, set flow, offset extrude edge, LoopTools integration.

![Freeze Scale keeps modifiers intact](https://dangry98.github.io/Key-Ops-Toolkit/assets/gifs/smart-apply-scale.gif)

![Live Booleans](https://dangry98.github.io/Key-Ops-Toolkit/assets/gifs/live-booleans.gif)

[More on the Toolkit Panel](https://dangry98.github.io/Key-Ops-Toolkit/toolkit.html)

---

## Game Art Toolkit

- **CAD Decimate**: decimate huge CAD scenes without crashing (tested on 330 million triangles).
- **Auto LOD**: generate LODs in one click, with normal transfer and weighted normals.
- **Polycount List**: live triangle count and modifier evaluation time per object, filtered by visibility or collection.
- **Quick Bake Name**: name `_high` and `_low` pairs for baking.
- **Quick Export** (`Ctrl E`): export the selection in one key, straight into a Bake folder.

![Polycount List](https://dangry98.github.io/Key-Ops-Toolkit/assets/shots/toolkit-polycount-list.png)

---

## Pie Menus

![Add Objects Pie](https://dangry98.github.io/Key-Ops-Toolkit/assets/shots/pie-add-objects.png)

- **Add Objects** (`Shift Alt A`): primitives sized to your view, so they are never too big or too small.
- **Add Modifier** (`Shift Q`, off by default).
- **Cursor** (`Shift S`): snapping plus set origin.
- **Flatten** (`Alt 3` in Edit Mode): flatten the selection from the view.
- **Workspace** (`Shift \`, off by default).
- **View Camera** (`Space`, via the Rebind tab).
- **Utility and UV pies** (`U`, `Space`, `Q`, experimental).

[More on Pie Menus](https://dangry98.github.io/Key-Ops-Toolkit/pie-menus.html)

---

## UV

- **Smart UV Sync** (`RMB`): right-click toggles UV Sync while keeping the selection.
- **UV Cut** (`X` / `Shift X`): Maya-style cut and move island, or just cut.
- **Remove Seam** (`Alt 2`): clear seams and sharp edges.
- **Sharp Edges from UV Islands**: mark sharp edges on UV island borders, skipping internal seams such as on a cylinder.
- **Triplanar UV modifier**: box-projection UVs as a modifier, like Box Projection UVW in 3ds Max.

![Smart UV Sync](https://dangry98.github.io/Key-Ops-Toolkit/assets/notion/uv-sync-on.gif)

[More on UV](https://dangry98.github.io/Key-Ops-Toolkit/uv.html)

---

## Extras

- **Fast Merge and Connect** (`1`, `Alt 1`, `Shift 1`): merge to nearest or active, merge at center, connect, join or knife.
- **Material Utilities** (`Alt M`): assign, select and remove materials, even in Object Mode.
- **Modifier Key**: keyboard control of the modifier stack in the Properties Editor.
- **Attribute Operations**, **Viewport Menu** (`Alt V`, with silhouette toggle), **Outliner Options** and **LoopTools Menu**.
- **Legacy Shortcuts**: handy shortcuts from Blender 2.79 (poke, grow and shrink, UV copy and paste).

![Fast Merge](https://dangry98.github.io/Key-Ops-Toolkit/assets/notion/fast-merge.gif)

[More on Extras](https://dangry98.github.io/Key-Ops-Toolkit/extras.html)

---

## Rebind

One-click changes to Blender's own keymap: context menu on right-click, Add Objects Pie on `Shift A`, View pie on `Space`, and no-lag pie menus. Each has a reset button.

---

[Documentation](https://dangry98.github.io/Key-Ops-Toolkit/) · [Report an issue](https://github.com/Dangry98/Key-Ops-Toolkit/issues)
