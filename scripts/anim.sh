#!/usr/bin/env bash
# animated turntable video, headless: scripts/anim.sh [name] [seconds] [seconds per orbit] [pitch]
# plays gen/models/<name>.anim.sexp; writes out/<name>/<name>-anim.mp4 (1280x720, 60 fps),
# with sound from gen/models/<name>.sound.sexp when ref/sounds has the samples
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
# the soundtrack: clips prepared from the bank, mixed by the viewer on the shot times
audio=()
if [ -f "gen/models/$name.sound.sexp" ] && [ -d ref/sounds ]; then
    .venv/bin/python tools/sounds.py "$name" >/dev/null
    ./build/viewer "out/$name/$name.obj" --anim "gen/models/$name.anim.sexp" --audio "$tmp/sound.wav" \
        --audio-secs "$secs" | grep -v "^loaded\|^rig\|^anim\|^sound"
    audio=(-i "$tmp/sound.wav" -c:a aac -b:a 192k)
fi
ffmpeg -loglevel error -y -framerate 60 -i "$tmp/f_%04d.png" "${audio[@]}" -c:v libx264 -pix_fmt yuv420p -crf 16 \
    -preset slow -shortest "out/$name/$name-anim.mp4"
rm -rf "$tmp"
echo "wrote out/$name/$name-anim.mp4"
