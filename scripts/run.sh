#!/usr/bin/env bash
# opens the viewer on your screen: scripts/run.sh [model-name]   (default: liedersanger)
# drag: orbit, right drag: pan, wheel: zoom, W wire, C clay, U uvs, space spin, R reset, Esc quit
# P pause, , . step a frame, [ ] slower/faster, M mute; edit gen/models/<name>.anim.sexp and
# <name>.sound.sexp live
# the window reloads by itself whenever the generator rewrites the model
set -e
cd "$(dirname "$0")/.."
name="${1:-liedersanger}"
base="${name%%[-_]*}"  # liedersanger-crunch and liedersanger_lo play liedersanger's anim and sounds
[ -f "out/$name/$name.obj" ] || name=test
cmake -S viewer -B build -G Ninja -DCMAKE_BUILD_TYPE=Release >/dev/null
ninja -C build >/dev/null
anim=()
[ -f "gen/models/$base.anim.sexp" ] && anim=(--anim "gen/models/$base.anim.sexp")
# sound clips from the bank (rerun tools/sounds.py after editing samples; cues reload live)
if [ -f "gen/models/$base.sound.sexp" ] && [ -d ref/sounds ]; then
    .venv/bin/python tools/sounds.py "$base" >/dev/null
fi
GENMODEL_ON_SCREEN=1 ./build/viewer "out/$name/$name.obj" "${anim[@]}" --yaw -30 --pitch 10 &
pid=$!

# i3 tiles new windows; float it at 1280x720 centred on the left monitor
if command -v i3-msg >/dev/null; then
    geom=$(i3-msg -t get_outputs | python3 -c '
import json, sys
outs = [o for o in json.load(sys.stdin) if o["active"]]
r = min(outs, key=lambda o: o["rect"]["x"])["rect"]
print(r["x"] + (r["width"] - 1280) // 2, r["y"] + (r["height"] - 720) // 2)')
    # find the viewer by its own process id, never by title (other windows share the name)
    for _ in $(seq 50); do
        wid=$(xdotool search --pid "$pid" 2>/dev/null | head -1)
        if [ -n "$wid" ] && i3-msg -t get_tree | grep -q "\"window\":$wid,"; then
            i3-msg "[id=$wid] floating enable, resize set 1280 720, move absolute position ${geom% *} ${geom#* }" >/dev/null
            break
        fi
        sleep 0.1
    done
fi
wait $pid
