"""Builds a model: python gen/build.py liedersanger [--tex N] [--fast]"""

import argparse
import importlib
import os
import sys
import time

# workers do the parallelism, keep numpy itself single threaded
for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[var] = "1"

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

import bake
import export
import meshing

F = np.float32
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mesh_piece(pc, coarse):
    """Contour and decimate one piece to its own budget; instanced pieces mesh their
    element once and copy it."""
    if pc.element is None:
        lo, hi = pc.body.bounds()
        v, f = meshing.dual_contour(pc.body.dist, lo, hi, pc.h * coarse)
        return meshing.decimate(v, f, pc.tris)
    lo, hi = pc.element.bounds()
    v, f = meshing.dual_contour(pc.element.dist, lo, hi, pc.h * coarse)
    v, f = meshing.decimate(v, f, pc.tris)
    vs, fs = [], []
    for i, (R, t) in enumerate(pc.placements):
        vs.append(v @ R.T + t)
        fs.append(f + i * len(v))
    return np.concatenate(vs).astype(F), np.concatenate(fs)


def mesh_pieces(scene, coarse):
    """Mesh every piece, then drop faces buried inside other pieces."""
    bodies = [(pc.body, *pc.body.bounds()) for pc in scene.pieces]
    vs, fs, base = [], [], 0
    for i, pc in enumerate(scene.pieces):
        v, f = mesh_piece(pc, coarse)
        f = meshing.drop_degenerate(v, f)
        others = bodies[:i] + bodies[i + 1 :]
        if others and len(f):
            d, _ = scene.union_eval(v[f].mean(1), others)
            f = f[d > -pc.h * 0.75]
        print(f"  {pc.name}: {len(f)} tris")
        vs.append(v)
        fs.append(f + base)
        base += len(v)
    v = np.concatenate(vs)
    f = np.concatenate(fs)
    used = np.unique(f)
    remap = np.full(len(v), -1, np.int32)
    remap[used] = np.arange(len(used))
    return v[used], remap[f]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--tex", type=int, default=None)
    ap.add_argument("--fast", action="store_true", help="coarser voxels and a small texture")
    args = ap.parse_args()

    t0 = time.time()
    mod = importlib.import_module("models." + args.model)
    scene = mod.build()
    size = args.tex or (1024 if args.fast else scene.texture_size)
    coarse = 1.6 if args.fast else 1.0

    print("meshing")
    v, f = mesh_pieces(scene, coarse)
    bodies = [(pc.body, *pc.body.bounds()) for pc in scene.pieces]
    v, n, f = meshing.surface_normals(lambda q: scene.union_eval(q, bodies)[0], v, f, 0.03)
    print(f"  decimated: {len(f)} tris, {len(v)} verts  ({time.time() - t0:.1f}s)")

    print("texturing")
    v, n, f, uv = bake.make_atlas(v, n, f, size)
    tex = bake.bake(scene, v, n, f, uv, size, unit=getattr(mod, "UNIT", 0.08))
    out_dir = os.path.join(ROOT, "out", args.model)
    export.write_obj(out_dir, args.model, v * scene.scale, n, uv, f, tex)
    print(f"wrote out/{args.model}/{args.model}.obj  {len(f)} tris, {size}px texture  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
