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
import polys
import sdf
from sexp import field, parse_sexp

F = np.float32
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mesh_element(node, pc, coarse, poly):
    """(verts, faces) for one node: clean polygons when asked and possible, else contoured
    and decimated to the piece's budget."""
    if poly and pc.mesher != "contour":
        m = polys.polygonize(node)
        if m is not None:
            return m
        print(f"  {pc.name}: no polygon form (a cut?), contouring instead")
    lo, hi = node.bounds()
    v, f = meshing.dual_contour(node.dist, lo, hi, pc.h * coarse)
    return meshing.decimate(v, f, pc.tris)


def mesh_piece(pc, coarse, poly=False):
    """One piece's (verts, faces, tile uv or None); instanced pieces mesh their element once
    and copy it, mapping the tile in the element's own coordinates."""
    if pc.element is None:
        v, f = mesh_element(pc.body, pc, coarse, poly)
        uv = pc.tile_uv(v) if pc.tile else None
        return v, f, uv
    v, f = mesh_element(pc.element, pc, coarse, poly)
    uv = pc.tile_uv(v) if pc.tile else None
    vs = [v @ R.T + t for R, t in pc.placements]
    # mirrored copies come out inside out: rewind them
    fs = [(f if np.linalg.det(R) > 0 else f[:, ::-1]) + i * len(v) for i, (R, t) in enumerate(pc.placements)]
    uvs = np.tile(uv, (len(pc.placements), 1)) if uv is not None else None
    return np.concatenate(vs).astype(F), np.concatenate(fs), uvs


def mesh_pieces(scene, coarse, poly=False):
    """Mesh every piece, then drop faces buried inside other pieces of the same rigid part
    (a buried face on a moving part could come out into view)."""
    bodies = [(pc.body, *pc.body.bounds()) for pc in scene.pieces]
    vs, fs, parts, owners, tiles, tile_uv, base = [], [], [], [], [], [], 0
    for i, pc in enumerate(scene.pieces):
        v, f, uv = mesh_piece(pc, coarse, poly)
        f = meshing.drop_degenerate(v, f)
        others = [bodies[j] for j, o in enumerate(scene.pieces)
                  if j != i and not o.free and not pc.free and not pc.part_each and o.part == pc.part]
        if others and len(f):
            # drop a face only when it is buried entirely (all corners and its centre); big
            # low-poly faces often poke partly into a neighbour, and must stay
            pts = np.concatenate([v[f[:, 0]], v[f[:, 1]], v[f[:, 2]], v[f].mean(1)])
            d, _ = scene.union_eval(pts, others)
            d = d.reshape(4, -1)
            f = f[~np.all(d < -pc.h * 0.75, axis=0)]
        if pc.part_each:
            # copies were appended in order, so faces split evenly between them
            copy = np.minimum(f[:, 0] // (len(v) // len(pc.placements)), len(pc.placements) - 1)
            parts += [f"{pc.part}.{c}" for c in copy]
        else:
            parts += [pc.part] * len(f)
        owners += [i] * len(f)
        tiles += [pc.tile] * len(f)
        tile_uv.append(uv[f] if uv is not None else np.zeros((len(f), 3, 2), F))
        print(f"  {pc.name}: {len(f)} tris")
        vs.append(v)
        fs.append(f + base)
        base += len(v)
    v = np.concatenate(vs)
    f = np.concatenate(fs)
    used = np.unique(f)
    remap = np.full(len(v), -1, np.int32)
    remap[used] = np.arange(len(used))
    return v[used], remap[f], np.array(parts), np.array(owners), np.array(tiles), np.concatenate(tile_uv)


def load_style(name):
    """gen/styles/<name>.sexp as a flat dict of settings."""
    form = parse_sexp(open(os.path.join(ROOT, "gen", "styles", name + ".sexp")).read())[0]
    # (base other) starts from another style and overrides what this one says
    st = load_style(field(form, "base")[0]) if field(form, "base") else {}
    for key in ("facets", "texture"):
        if field(form, key):
            st[key] = int(field(form, key)[0])
    for key in ("tris", "voxel", "grain", "grain-tint", "rust-specks", "chips", "grime", "cool-edges", "rust"):
        if field(form, key):
            st[key] = float(field(form, key)[0])
    if field(form, "texture") and len(field(form, "texture")) > 1:
        st["filter"] = field(form, "texture")[1]
    if field(form, "mesher"):
        st["mesher"] = field(form, "mesher")[0]
    norm = field(form, "normals")
    if norm and norm[0] == "flat":
        st["flat"] = float(norm[1]) if len(norm) > 1 else 20.0
    if field(form, "palette"):
        st["palette"] = {p[0]: tuple(int(c) for c in p[1:4]) for p in field(form, "palette")}
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--tex", type=int, default=None)
    ap.add_argument("--fast", action="store_true", help="coarser voxels and a small texture")
    ap.add_argument("--style", default=None, help="a gen/styles/<name>.sexp to build in")
    ap.add_argument("--part", default=None, help="mechs: build one part alone, in its own frame")
    args = ap.parse_args()

    t0 = time.time()
    mod = importlib.import_module("models." + args.model)
    build_args = {"part": args.part} if args.part else {}
    # a model made for a style (STYLE = "lofi") builds in it unless told otherwise
    native = getattr(mod, "STYLE", None)
    style_name = args.style or native
    style = load_style(style_name) if style_name else {}
    # facets must be set before the model builds its primitives
    sdf.FACETS = style.get("facets", 0)
    scene = mod.build(**build_args)
    scene.style = style
    # a model can insist on its texture size (TEXTURE), e.g. a whole mech needs more texels
    size = args.tex or getattr(mod, "TEXTURE", None) or (1024 if args.fast else style.get("texture", scene.texture_size))
    coarse = (1.6 if args.fast else 1.0) * style.get("voxel", 1.0)
    for pc in scene.pieces:
        # small repeated parts (coil rings, links) fall apart below a few dozen triangles
        pc.tris = max(int(pc.tris * style.get("tris", 1.0)), min(pc.tris, 28))
    for m in scene.materials:
        if m.name in style.get("palette", {}):  # styles without a palette keep the model's
            m.color = style["palette"][m.name]
    out_name = args.model + ("-" + style_name if style_name and style_name != native else "")
    out_name += ("_" + args.part) if args.part else ""

    print("meshing")
    v, f, face_part, face_piece, face_tile, face_tile_uv = mesh_pieces(scene, coarse, style.get("mesher") == "poly")
    # standing models (GROUNDED = True) are dropped so their lowest point at rest is on y = 0
    if getattr(mod, "GROUNDED", False):
        dy = -float(v[:, 1].min())
        v = v + np.array([0, dy, 0], F)
        for pt in scene.parts:
            pt.pivot = (pt.pivot[0], pt.pivot[1] + dy, pt.pivot[2])
        for ph in scene.paths:
            ph.points = [(p[0], p[1] + dy, p[2]) for p in ph.points]
        scene.ground_dy = dy
        print(f"  grounded: moved {dy * 100:+.1f} cm")
    if "flat" in style:
        v, n, f = meshing.crease_split(v, f, crease_deg=style["flat"])
    else:
        bodies = [(pc.body, *pc.body.bounds()) for pc in scene.pieces]
        v, n, f = meshing.surface_normals(lambda q: scene.union_eval(q, bodies)[0], v, f, 0.03)
    print(f"  decimated: {len(f)} tris, {len(v)} verts  ({time.time() - t0:.1f}s)")

    print("texturing")
    n_faces = len(f)
    v, n, f, uv = bake.make_atlas(v, n, f, size)
    assert len(f) == n_faces, "atlas changed the face list"
    tex = bake.bake(scene, v, n, f, uv, size, getattr(mod, "UNIT", 0.08), face_piece)
    out_dir = os.path.join(ROOT, "out", out_name)
    export.write_obj(out_dir, out_name, v * scene.scale, n, uv, f, tex, face_part, style.get("filter", "linear"),
                     face_tile, face_tile_uv, scene.tiles)
    export.write_rig(out_dir, out_name, scene)
    print(f"wrote out/{out_name}/{out_name}.obj  {len(f)} tris, {size}px texture  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
