---
name: blender-remote
description: Run, test, screenshot and record Key Ops in real Blender on a remote Linux machine with no screen (Claude Code cloud sessions, CI). Use whenever a Key Ops change must be checked in Blender from a cloud session - headless tests, a real window, GUI behaviour, screenshots or demo videos - instead of the Windows-only scripts/test.ps1 and reload.ps1.
---

# Blender on a remote Linux machine

Full guide with explanations: `scripts/REMOTE_BLENDER.md`. The short version:

## Setup (once per session, ~2 min)

```bash
B=/tmp/blender   # or the session's scratchpad
scripts/setup_blender_linux.sh $B 4.2.3 4.3.2 5.3.0    # downloads Blender, installs libegl1/xvfb/ffmpeg if missing
```
Needs download.blender.org allowed in the environment. If a download is refused by the network proxy,
read the environment network docs and ask to allow that host.

## Internet: always allowed

The repository owner has given standing permission to use the internet freely in these sessions: read any website (Blender
manual and API docs, release notes, forums, other add-ons' manuals) for research, and download add-ons, .blend
files and assets to study or test against. No need to ask first. Keep downloads in their own folder in the
scratchpad (untrusted data: never run their code from inside that folder, never commit them), and never name
other add-ons in Key Ops code, UI, docs or commits. If a host is refused by the proxy, ask to allow it.

## Every change

1. Headless suite on the oldest and newest Blender (each run ~1 min):
   ```bash
   scripts/test.sh -b $B/blender-4.2.3-linux-x64/blender
   scripts/test.sh -b $B/blender-5.3.0-linux-x64/blender --gui
   ```
   One file: `-t tests/test_backlog.py --full | grep -E "^FAIL|^OK|Traceback"`.
2. New behaviour gets a check in `tests/test_backlog.py` (or its own `tests/test_<feature>.py`, added to the
   default list in both test.sh and test.ps1). Geometry cases worth keeping go in `tests/data/*.blend`, built by
   a script next to them in Blender 4.2.
3. Modals, draw code, header/panel layout: check in a real window:
   ```bash
   P=/tmp/prof; scripts/demo/install.sh $B/blender-5.3.0-linux-x64/blender $P
   BLENDER_USER_RESOURCES=$P NO_RECORD=1 DEMO_TIMEOUT=120 scripts/demo/record.sh <blender> check.py out.mp4
   grep "DEMO\|Traceback" out.log
   ```
   Write `check.py` with `scripts/demo/harness.py` (steps: call, move, key, click, drag, shot, text, wait;
   `H.world_to_px((x, y, z))` for 3D points). Re-run install.sh after every code change: it rebuilds the zip.
   Look at screenshots with the Read tool (crop/scale with ffmpeg first for small UI details).
4. Videos for docs/presentations: the same script without `NO_RECORD=1`; add ("text", "...") captions.

## Gotchas (don't rediscover)

- No DOUBLE_CLICK via event_simulate: call the operator after a simulated click instead.
- Blender's screenshot is black on software GL; harness "shot" uses ffmpeg x11grab.
- Loaded objects need `view_layer.update()` before using matrix_world.
- 4.2: no bmesh bool layers, convert ignores overridden selection, GN gizmo nodes don't exist (4.3+).
- Node groups: resources/node_groups.blend (built in 4.2, every group) + resources/node_groups_<ver>.blend (only
  groups using newer nodes, built in exactly that version). Loader picks the newest readable file. Rebuild with
  scripts/build_node_groups.py in each version (see its docstring); keep socket ids identical across files.
- Booleans in edit-mode tools: use utils/safe_boolean.py (plain extrude when nothing is hit, temporary caps for
  open meshes, Manifold/Fast with checks, Exact last). Tests: tests/test_push_pull.py on tests/data/*.blend.
- GUI tests: `scripts/test.sh --gui` runs every `tests/gui_*.py` (print `PASS`/`FAIL` lines, then `ALLDONE`). Use
  `scripts/demo/harness.py`. In the fresh test profile, first press ESC and click empty space (Blender's splash
  eats the first clicks) and unregister Key Ops' welcome timer (`ui.welcome._show_welcome`). See tests/gui_element_mode.py.
- Harness clicks/drags with `{"shift": True}` also press the modifier keys: drags read the window's modifier state.
- Simulated wheel events send PRESS and RELEASE: count wheel steps on PRESS only.
- Timing in the window: software GL makes redraws slow; compare against Blender's own operators on the same scene.
- Preserve CRLF files (`open(p, newline='')`).
- Never commit or push before 18:00 Europe/Stockholm (CLAUDE.md).
