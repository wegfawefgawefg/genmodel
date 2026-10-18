#!/usr/bin/env bash
# rebuilds a model whenever its sources change: scripts/watch.sh [name] [build args...]
# pair it with scripts/run.sh <name>, which reloads the viewer when the build lands
set -e
cd "$(dirname "$0")/.."
name="${1:-scoobee}"
shift || true
echo "watching gen/ for $name (ctrl-c to stop)"
.venv/bin/python gen/build.py "$name" "$@" | tail -1
while true; do
    if command -v inotifywait >/dev/null; then
        inotifywait -qq -r -e close_write,moved_to,create gen
    else
        # no inotify-tools: poll the newest mtime under gen/
        last=$(find gen -type f -printf '%T@\n' | sort -n | tail -1)
        while [ "$(find gen -type f -printf '%T@\n' | sort -n | tail -1)" = "$last" ]; do sleep 0.5; done
    fi
    sleep 0.2
    .venv/bin/python gen/build.py "$name" "$@" 2>&1 | tail -1 || true
done
