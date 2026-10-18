#!/usr/bin/env bash
# animated turntable video, headless: scripts/anim.sh [name] [seconds] [seconds per orbit] [pitch]
# plays gen/models/<name>.anim.sexp; writes out/<name>/<name>-anim.mp4 (1280x720, 60 fps),
# with a soundtrack mixed from the shot times (tools/soundtrack.py) when ref/sounds has the samples
set -e
cd "$(dirname "$0")/.."
name="${1:-liedersanger}"
secs="${2:-16}"
orbit="${3:-16}"
pitch="${4:-14}"
tmp=$(mktemp -d)
ninja -C build >/dev/null
./build/viewer "out/$name/$name.obj" --anim "gen/models/$name.anim.sexp" --capture "$tmp/f_%04d.png" \
    --turntable $((secs * 60)) --spin-secs "$orbit" --size 1280 720 --yaw -35 --pitch "$pitch" --zoom 0.85 |
    grep -v "^loaded\|^headless\|^rig\|^anim"
# a soundtrack from the shot times, when the reference sounds are here (ref/sounds)
audio=()
if [ -f ref/sounds/shot_50bmg.mp3 ]; then
    .venv/bin/python tools/soundtrack.py "$name" "$secs" "$tmp/sound.wav"
    audio=(-i "$tmp/sound.wav" -c:a aac -b:a 192k)
fi
ffmpeg -loglevel error -y -framerate 60 -i "$tmp/f_%04d.png" "${audio[@]}" -c:v libx264 -pix_fmt yuv420p -crf 16 \
    -preset slow -shortest "out/$name/$name-anim.mp4"
rm -rf "$tmp"
echo "wrote out/$name/$name-anim.mp4"
