#!/usr/bin/env bash
# opens the viewer on your screen: scripts/run.sh [model-name]   (default: liedersanger)
# drag: orbit, right drag: pan, wheel: zoom, W wire, C clay, U uvs, space spin, R reset, Esc quit
# P pause, , . step a frame, [ ] slower/faster; edit gen/models/<name>.anim.sexp live
# the window reloads by itself whenever the generator rewrites the model
set -e
cd "$(dirname "$0")/.."
name="${1:-liedersanger}"
[ -f "out/$name/$name.obj" ] || name=test
cmake -S viewer -B build -G Ninja -DCMAKE_BUILD_TYPE=Release >/dev/null
ninja -C build >/dev/null
anim=()
[ -f "gen/models/$name.anim.sexp" ] && anim=(--anim "gen/models/$name.anim.sexp")
GENMODEL_ON_SCREEN=1 ./build/viewer "out/$name/$name.obj" "${anim[@]}" --yaw -30 --pitch 10 &
pid=$!

# i3 tiles new windows; float it at 1280x720 centred on the left monitor
if command -v i3-msg >/dev/null; then
    geom=$(i3-msg -t get_outputs | python3 -c '
import json, sys
outs = [o for o in json.load(sys.stdin) if o["active"]]
r = min(outs, key=lambda o: o["rect"]["x"])["rect"]
print(r["x"] + (r["width"] - 1280) // 2, r["y"] + (r["height"] - 720) // 2)')
    for _ in $(seq 50); do
        con=$(i3-msg -t get_tree | python3 -c '
import json, sys
def walk(n):
    if (n.get("window_properties") or {}).get("title", "").startswith("genmodel"):
        print(n["id"]); sys.exit()
    for c in n.get("nodes", []) + n.get("floating_nodes", []):
        walk(c)
walk(json.load(sys.stdin))')
        if [ -n "$con" ]; then
            i3-msg "[con_id=$con] floating enable, resize set 1280 720, move absolute position ${geom% *} ${geom#* }" >/dev/null
            break
        fi
        sleep 0.1
    done
fi
wait $pid
