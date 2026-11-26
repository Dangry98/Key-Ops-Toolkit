#!/usr/bin/env bash
# Record a Blender demo: start a virtual display, run Blender with a demo script, capture with ffmpeg.
#   scripts/demo/record.sh <blender> <demo.py> <out.mp4> [extra blender args...]
# The demo script drives Blender with bpy.app.timers + window.event_simulate and quits when done.
# Needs Xvfb and ffmpeg. Install the add-on first (scripts/demo/install.sh) and export BLENDER_USER_RESOURCES.
# NO_RECORD=1 runs the script in the window without recording (GUI checks, screenshots).
set -u
blender="$1"; script="$2"; out="$3"; shift 3
W=${DEMO_W:-1600}; H=${DEMO_H:-900}
disp=":$((90 + RANDOM % 9))"
Xvfb "$disp" -screen 0 "${W}x${H}x24" -nolisten tcp >/dev/null 2>&1 &
xpid=$!
sleep 1
DISPLAY="$disp" "$blender" --enable-event-simulate --window-geometry 0 0 "$W" "$H" --no-window-focus --python "$script" "$@" >"${out%.mp4}.log" 2>&1 &
bpid=$!
# wait for the window to draw, then record until Blender exits
if [ "${NO_RECORD:-0}" = 1 ]; then wait $bpid; kill $xpid 2>/dev/null; echo "ran $script"; exit 0; fi
sleep "${DEMO_WARMUP:-4}"
ffmpeg -loglevel error -y -f x11grab -framerate 30 -video_size "${W}x${H}" -i "$disp" \
    -c:v libx264 -preset veryfast -pix_fmt yuv420p -crf 23 "$out" &
fpid=$!
wait $bpid
kill -INT $fpid 2>/dev/null; wait $fpid 2>/dev/null
kill $xpid 2>/dev/null
echo "recorded $out"
