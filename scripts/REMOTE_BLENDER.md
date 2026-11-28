# Testing Key Ops in Blender on a remote Linux machine

How to run Key Ops in real Blender (headless tests, a real window, screenshots and videos) on a cloud session
or any Linux box without a screen. Everything here was used and checked in a Claude Code cloud session.

## 1. One-time setup (about 2 minutes)

```bash
scripts/setup_blender_linux.sh /tmp/blender 4.2.3 4.3.2 5.3.0   # 4.3.2 only to build resources/node_groups_4_3.blend
```

- Downloads Blender from download.blender.org (that host must be allowed in the environment's network
  settings) and unpacks it. 4.2.3 is the oldest version Key Ops supports; also test the newest release.
- Installs `libegl1` (Blender 4.x needs EGL to open a window), `xvfb` (a virtual screen) and `ffmpeg`
  (screenshots and recordings) with apt when missing.
- Re-running is safe: it skips what is already there.

## Internet use

Using the internet is always allowed in these sessions: read any site for research and download add-ons, .blend
files or assets to test against, without asking. Keep downloads in their own scratchpad folder, don't run their
code from inside it, never commit them, and never name other add-ons in Key Ops itself. A host the proxy refuses
can be added to the environment's allowed hosts (ask once).

## 2. Headless tests

```bash
scripts/test.sh -b /tmp/blender/blender-4.2.3-linux-x64/blender
scripts/test.sh -b /tmp/blender/blender-5.3.0-linux-x64/blender --gui      # also the real-window smoke test
scripts/test.sh -b <blender> -t tests/test_edge_trim.py --full             # one file, whole log
```

`test.sh` is the Linux twin of `test.ps1`: it builds the working tree into an extension zip, installs it into a
throwaway profile (`BLENDER_USER_RESOURCES`), runs each test with `-b --factory-startup` and prints only
failures plus `OK/FAIL <test> pass=N fail=N`. Expected noise: a `ValueError: boom` traceback in
test_redesign.py and "This is not a Key Ops settings file" (both are checks).

Test data lives in `tests/data/` (e.g. `trim_cases.blend`, rebuilt by `tests/data/make_trim_cases.py`).
Build such files in Blender 4.2 so every newer version can open them.

## 3. A real Blender window (GUI checks, screenshots, videos)

```bash
scripts/demo/install.sh <blender> /tmp/prof          # build + install Key Ops into a scratch profile,
                                                     # splash off, OpenGL backend, add-on enabled
BLENDER_USER_RESOURCES=/tmp/prof NO_RECORD=1 scripts/demo/record.sh <blender> my_check.py out.mp4
BLENDER_USER_RESOURCES=/tmp/prof scripts/demo/record.sh <blender> my_demo.py out.mp4   # records a video
```

`record.sh` starts Xvfb, runs Blender with `--enable-event-simulate` and the script, and (without
`NO_RECORD=1`) records the screen with ffmpeg until Blender quits. Blender's log goes to `out.log`.

A check or demo script drives Blender with `scripts/demo/harness.py`:

```python
import sys; sys.path.insert(0, "/path/to/Key-Ops-Toolkit/scripts/demo")
import bpy, harness as H

def report(context):
    H.log("modifiers", [m.type for m in context.object.modifiers])

H.run([
    ("call", H.scene_cube(edit=False)),           # a fresh scene
    ("move", 0.5, 0.5, 0.3),                      # mouse to the middle of the 3D View (fractions or pixels)
    ("call", lambda c: bpy.ops.keyops.fast_bevel('INVOKE_DEFAULT')),
    ("key", 'FOUR'),                              # press + release, mods as {"shift": True}
    ("drag", H.world_to_px((0, 0, 1)), H.world_to_px((1, 0, 1)), 0.5),   # 3D points projected each step
    ("click", 'LEFTMOUSE'),
    ("call", report),
    ("text", "A caption for the video"),
    ("shot", "/tmp/out.png"),                     # screenshot of the X display
])
```

Lines starting with `DEMO` in the log are the script's own output; `DEMO ALLDONE` means it finished.

## 4. Things that cost time to find out

- Node groups come in one file per Blender version: resources/node_groups.blend (built in 4.2, every group) and
  resources/node_groups_<major>_<minor>.blend (only groups that use nodes from that version, e.g. 4.3 gizmos,
  built in exactly that version). utils/node_groups.py loads the newest file the running Blender can read.
  Rebuild: `blender-4.2 -b resources/node_groups.blend --python scripts/build_node_groups.py` and
  `blender-4.3 -b --factory-startup --python scripts/build_node_groups.py`. Socket ids must match in every file.
- Edit-mode booleans: utils/safe_boolean.py; `KEYOPS_BOOL_DEBUG=1` prints every solver attempt and its checks.

- Blender's own `screen.screenshot` reads back black on software OpenGL: the harness grabs the X display with
  ffmpeg instead.
- Blender 4.x opens no window without `libEGL.so.1` (it aborts with "Couldn't open libEGL.so.1").
- `event_simulate` can't send DOUBLE_CLICK, and two quick simulated presses don't become one either: test
  what a double click runs by calling the operator after a simulated click.
- Opening a file removes non-persistent `bpy.app.timers`: the harness registers its timers persistent.
- Objects loaded with `bpy.data.libraries.load` have no world matrix until `view_layer.update()`.
- Blender 4.2's bmesh has no boolean layers (`bm.faces.layers.bool` arrived later): fall back to Blender's
  attribute operators there.
- `bpy.ops.object.convert` in 4.2 ignores an overridden selection: select the objects for real.
- Keep files' line endings: some sources use CRLF (e.g. utils/pref_utils.py). Edit with
  `open(path, newline='')` and write back the same endings, or the diff shows every line changed.
- A first run shows Blender's splash and, on software GL, a Vulkan warning: `install.sh` turns the splash off
  and sets the OpenGL backend in the scratch profile.
- `--factory-startup` ignores the scratch profile: don't pass it when the add-on should load from the profile
  (record.sh doesn't).
