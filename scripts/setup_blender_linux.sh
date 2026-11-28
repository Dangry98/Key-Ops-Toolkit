#!/usr/bin/env bash
# Get Blender ready for testing Key Ops on Linux (cloud sessions, CI): download the versions, install what a
# real (windowed) Blender needs on a headless machine, and print the paths.
#
#   scripts/setup_blender_linux.sh [dest_dir] [version ...]
#   scripts/setup_blender_linux.sh /tmp/blender 4.2.3 5.3.0
#
# Defaults: dest ~/.cache/keyops-blender, versions 4.2.3 (the minimum) and the newest release found.
# Needs download.blender.org reachable. Re-running skips what is already there.
set -u
dest="${1:-$HOME/.cache/keyops-blender}"
shift || true
versions=("$@")
mkdir -p "$dest"

if [ ${#versions[@]} -eq 0 ]; then
    newest_series=$(curl -s https://download.blender.org/release/ | grep -o 'Blender[0-9]\.[0-9]*' | sort -uV | tail -1 | sed 's/Blender//')
    newest=$(curl -s "https://download.blender.org/release/Blender$newest_series/" | grep -o "blender-$newest_series\.[0-9]*-linux-x64.tar.xz" | sort -uV | tail -1 | sed 's/blender-\(.*\)-linux-x64.tar.xz/\1/')
    versions=(4.2.3 "$newest")
fi

for v in "${versions[@]}"; do
    dir="$dest/blender-$v-linux-x64"
    if [ -x "$dir/blender" ]; then
        echo "have   $dir/blender"
        continue
    fi
    series="${v%.*}"
    url="https://download.blender.org/release/Blender$series/blender-$v-linux-x64.tar.xz"
    echo "get    $url"
    curl -sSfL "$url" -o "$dest/b.tar.xz" && tar xf "$dest/b.tar.xz" -C "$dest" && rm -f "$dest/b.tar.xz" \
        || { echo "FAIL   download $v"; continue; }
    echo "ready  $dir/blender"
done

# A windowed Blender under Xvfb needs EGL (4.x) and a virtual display; recording needs ffmpeg
missing=()
ldconfig -p | grep -q 'libEGL.so.1' || missing+=(libegl1)
command -v Xvfb >/dev/null || missing+=(xvfb)
command -v ffmpeg >/dev/null || missing+=(ffmpeg)
if [ ${#missing[@]} -gt 0 ]; then
    echo "apt    ${missing[*]}"
    (apt-get install -y "${missing[@]}" >/dev/null 2>&1 || { apt-get update -qq >/dev/null 2>&1 && apt-get install -y "${missing[@]}" >/dev/null 2>&1; }) \
        || echo "FAIL   apt-get install ${missing[*]} (install them by hand)"
fi
echo "done   blenders in $dest"
