#!/usr/bin/env bash
# Linux/macOS twin of scripts/test.ps1: build the working tree, install it into a throwaway Blender
# profile and run the headless tests. The user's own Blender config is never touched.
#
#   scripts/test.sh -b /path/to/blender [-t tests/x.py ...] [--gui] [--full]
#
# BLENDER env var works instead of -b. --gui also runs tests/gui_modal_smoke.py in a real window
# (under xvfb-run when no DISPLAY is set).
set -u
repo="$(cd "$(dirname "$0")/.." && pwd)"
blender="${BLENDER:-}"
tests=()
gui=0
full=0
while [ $# -gt 0 ]; do
    case "$1" in
        -b) blender="$2"; shift 2 ;;
        -t) tests+=("$2"); shift 2 ;;
        --gui) gui=1; shift ;;
        --full) full=1; shift ;;
        *) echo "unknown argument $1"; exit 2 ;;
    esac
done
[ -x "$blender" ] || { echo "FAIL no blender: pass -b <path> or set BLENDER"; exit 2; }
[ ${#tests[@]} -eq 0 ] && tests=(tests/test_registration.py tests/test_redesign.py tests/test_menu_drawing.py tests/test_ui_draw.py tests/test_kit_coverage.py)
echo "blender: $blender"

work="$(mktemp -d "${TMPDIR:-/tmp}/keyops-test-XXXXXX")"
export BLENDER_USER_RESOURCES="$work/user"
mkdir -p "$BLENDER_USER_RESOURCES" "$work/build"

"$blender" --command extension build --source-dir "$repo" --output-dir "$work/build" >"$work/build.log" 2>&1
zip="$(ls "$work"/build/*.zip 2>/dev/null | head -1)"
[ -n "$zip" ] || { echo "FAIL build"; tail -20 "$work/build.log"; exit 1; }
"$blender" --command extension install-file -r user_default -e "$zip" >"$work/install.log" 2>&1 \
    || { echo "FAIL install"; tail -20 "$work/install.log"; exit 1; }
echo "built + installed $(basename "$zip")"

failed=0
for t in "${tests[@]}"; do
    log="$work/$(basename "$t").log"
    "$blender" -b --factory-startup --python-exit-code 1 --python "$repo/$t" >"$log" 2>&1
    code=$?
    pass=$(grep -c '^PASS ' "$log")
    fail=$(grep -c '^FAIL ' "$log")
    if [ $full -eq 1 ]; then cat "$log"; else grep -E '^FAIL |Traceback|Error|Exception' "$log" | grep -v '^PASS ' | head -40; fi
    if [ $code -eq 0 ] && [ "$fail" -eq 0 ]; then s="OK  "; else s="FAIL"; failed=$((failed + 1)); fi
    echo "$s $t  pass=$pass fail=$fail exit=$code"
done

if [ $gui -eq 1 ]; then
    t=tests/gui_modal_smoke.py
    log="$work/gui_modal_smoke.py.log"
    run=("$blender" --factory-startup --enable-event-simulate --python "$repo/$t")
    if [ -z "${DISPLAY:-}" ]; then run=(xvfb-run -a -s "-screen 0 1600x1000x24" "${run[@]}"); fi
    "${run[@]}" >"$log" 2>&1
    code=$?
    pass=$(grep -c '^PASS ' "$log"); fail=$(grep -c '^FAIL ' "$log")
    tb=$(grep -c 'Traceback' "$log"); done_=$(grep -c '^ALLDONE' "$log")
    if [ $full -eq 1 ]; then cat "$log"; else grep -E '^FAIL |^SKIP |Traceback|Error|^  File ' "$log" | head -40; fi
    if [ $code -eq 0 ] && [ "$fail" -eq 0 ] && [ "$tb" -eq 0 ] && [ "$done_" -eq 1 ]; then s="OK  "; else s="FAIL"; failed=$((failed + 1)); fi
    echo "$s $t  pass=$pass fail=$fail tracebacks=$tb exit=$code"
fi

echo "logs: $work"
[ $failed -eq 0 ]
