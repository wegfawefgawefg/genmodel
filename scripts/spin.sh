#!/usr/bin/env bash
# turntable video, headless: scripts/spin.sh [name] [seconds per turn] [turns]
# writes out/<name>/<name>-spin.mp4 (1280x720, 60 fps)
set -e
cd "$(dirname "$0")/.."
name="${1:-liedersanger}"
secs="${2:-2}"
turns="${3:-3}"
frames=$((secs * 60))
tmp=$(mktemp -d)
ninja -C build >/dev/null
./build/viewer "out/$name/$name.obj" --capture "$tmp/f_%04d.png" --turntable $frames \
    --size 1280 720 --yaw -30 --pitch 16 --zoom 0.85 | grep -v "^loaded\|^headless"
ffmpeg -loglevel error -y -stream_loop $((turns - 1)) -framerate 60 -i "$tmp/f_%04d.png" \
    -c:v libx264 -pix_fmt yuv420p -crf 16 -preset slow "out/$name/$name-spin.mp4"
rm -rf "$tmp"
echo "wrote out/$name/$name-spin.mp4"
