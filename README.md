# genmodel

Experiment: textured, PS2-era-but-good 3D models for a mech game, built from a reference image.
Not an exact copy; the goal is the general structure of the reference with a clean y2k look.

**Start with [HOW_IT_WAS_MADE.md](HOW_IT_WAS_MADE.md)**: the story of the gun (down to 492
triangles) and the walking robot, step by step.

![the gun from 17k triangles down to 492](docs/img/lineup.jpg)

## How it works

1. A model is written by hand (`gen/models/<name>.py`) as SDF pieces: boxes, cylinders, tori,
   extruded 2d profiles, smooth unions, cuts. The reference is read in pixel units, roughly.
2. Each piece is dual-contoured (sharp creases, flat panels), then decimated to its own triangle budget.
   Repeated parts (spring coils, belt links, bolts, teeth) are meshed once and instanced.
3. Normals come from the SDF gradient, so curves stay round and only real creases split.
4. xatlas unwraps; every texel is shaded from the full-detail SDF: material, edge wear and grime
   from curvature, ambient occlusion, texture-only details (seams, screws) and projected decals.
5. Output: `out/<name>/<name>.obj` + `.mtl` + `.png` (RGB albedo, alpha = specular).

## Animation and sound

- `gen/models/<name>.anim.sexp`: a fire-rate curve decides when shots happen; tracks kick,
  step, feed, throw, shake, wave, lean and glow rig parts, and emit smoke (wisp, puff, spark).
- `gen/models/<name>.sound.sexp`: samples (cut, fades, filters, room, baked once by
  `tools/sounds.py` into `out/<name>/sounds/`) and cues (layers with gain/pitch/delay/pan ranges).
  The anim's `sound` and `hum` tracks trigger cues on the same events as the motion.
- Everything is a function of time: live playback, scrubbing and videos see and hear the same thing.
- Source sounds live in `ref/sounds/` (not in git; names, authors and links in
  [docs/sound-credits.md](docs/sound-credits.md)). Without them everything works, silently.

## Use

Needs Python 3, and for the viewer CMake, Ninja, a C++20 compiler, SDL3, OpenGL/EGL and stb
headers (`/usr/include/stb`). ffmpeg for videos and sound.

    python3 -m venv .venv && .venv/bin/pip install numpy scipy scikit-image xatlas pyfqmr pillow
    cmake -S viewer -B build -G Ninja && ninja -C build
    .venv/bin/python gen/build.py liedersanger          # full build, about 20 s
    .venv/bin/python gen/build.py liedersanger --fast   # coarse voxels, 1024 texture

Built models go to `out/` (not in git; everything there is rebuilt by these commands):

    .venv/bin/python gen/build.py liedersanger --style crunch
    .venv/bin/python gen/build.py liedersanger_lo
    .venv/bin/python gen/build.py liedersanger_lo --style lofigrey
    .venv/bin/python gen/build.py liedersanger_vlo
    .venv/bin/python gen/build.py liedersanger_vvlo
    .venv/bin/python gen/build.py liedersanger_vvlo --style bud
    .venv/bin/python gen/build.py scoobee
    .venv/bin/python tools/export_gltf.py out/X/X.obj out/X/X.glb   # glTF for game engines
    scripts/run.sh                                       # viewer window (floats on i3, left monitor)
    scripts/shot.sh liedersanger out.png --sheet         # headless GPU render, no window
    scripts/anim.sh liedersanger 18                      # animated video with sound

Viewer: drag to orbit, right drag to pan, wheel to zoom, W wireframe, C clay, U uv checker,
space to spin, R to reset, P pause, `,` `.` step, `[` `]` speed, M mute. It reloads whenever the
model, animation or sound files change.

The viewer refuses to open a window when run by an agent (CLAUDECODE set); agents use `--capture`.

## Credits and references

Reference pictures (`ref/`) are not included; the art belongs to its authors. Scoobee is a fan
model inspired by the mechs of Phantom Crash (Genki, 2002). Sound credits are in
[docs/sound-credits.md](docs/sound-credits.md).
