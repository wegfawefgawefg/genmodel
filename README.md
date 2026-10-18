# genmodel

Experiment: textured, PS2-era-but-good 3D models for a mech game, built from a reference image.
Not an exact copy; the goal is the general structure of the reference with a clean y2k look.

## How it works

1. A model is written by hand (`gen/models/<name>.py`) as SDF pieces: boxes, cylinders, tori,
   extruded 2d profiles, smooth unions, cuts. The reference is read in pixel units, roughly.
2. Each piece is dual-contoured (sharp creases, flat panels), then decimated to its own triangle budget.
   Repeated parts (spring coils, belt links, bolts, teeth) are meshed once and instanced.
3. Normals come from the SDF gradient, so curves stay round and only real creases split.
4. xatlas unwraps; every texel is shaded from the full-detail SDF: material, edge wear and grime
   from curvature, ambient occlusion, texture-only details (seams, screws) and projected decals.
5. Output: `out/<name>/<name>.obj` + `.mtl` + `.png` (RGB albedo, alpha = specular).

## Use

    python3 -m venv .venv && .venv/bin/pip install numpy scipy scikit-image xatlas pyfqmr pillow
    .venv/bin/python gen/build.py liedersanger          # full build, about 20 s
    .venv/bin/python gen/build.py liedersanger --fast   # coarse voxels, 1024 texture
    scripts/run.sh                                       # viewer window (floats on i3, left monitor)
    scripts/shot.sh liedersanger out.png --sheet         # headless GPU render, no window

Viewer: drag to orbit, right drag to pan, wheel to zoom, W wireframe, C clay, U uv checker,
space to spin, R to reset. It reloads whenever the model files change.

The viewer refuses to open a window when run by an agent (CLAUDECODE set); agents use `--capture`.
