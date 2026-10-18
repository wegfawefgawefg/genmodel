#!/usr/bin/env bash
# headless GPU render, never opens a window: scripts/shot.sh name out.png [viewer args...]
set -e
cd "$(dirname "$0")/.."
name="$1"; out="$2"; shift 2
ninja -C build >/dev/null
./build/viewer "out/$name/$name.obj" --capture "$out" --yaw -30 --pitch 10 "$@" | grep -v "^loaded\|^headless"
