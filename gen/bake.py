"""UV atlas and texture baking. Every texel is shaded from the full-detail SDF: material,
curvature (edge wear and grime), ambient occlusion and projected decals."""

import multiprocessing as mp
import os

import numpy as np
import xatlas
from scipy import ndimage

from noise import fbm, hash3

F = np.float32


def make_atlas(verts, normals, faces, size):
    atlas = xatlas.Atlas()
    atlas.add_mesh(verts, faces, normals)
    chart = xatlas.ChartOptions()
    chart.max_iterations = 2
    chart.max_cost = 6.0
    pack = xatlas.PackOptions()
    pack.resolution = size
    pack.padding = max(2, size // 340)
    pack.bilinear = True
    pack.rotate_charts_to_axis = True
    atlas.generate(chart, pack)
    vmap, ifaces, uvs = atlas[0]
    print(f"  atlas: {atlas.chart_count} charts, {atlas.utilization * 100:.0f}% used, {len(vmap)} verts")
    return verts[vmap], normals[vmap], ifaces.astype(np.int32), uvs.astype(F)


def rasterize(uvs, faces, size):
    """Which triangle covers each texel, and its barycentrics."""
    tri = np.full((size, size), -1, np.int32)
    bary = np.zeros((size, size, 3), F)
    pix = uvs * size - 0.5
    for f, (a, b, c) in enumerate(faces):
        pa, pb, pc = pix[a], pix[b], pix[c]
        x0 = max(int(np.floor(min(pa[0], pb[0], pc[0]))), 0)
        x1 = min(int(np.ceil(max(pa[0], pb[0], pc[0]))), size - 1)
        y0 = max(int(np.floor(min(pa[1], pb[1], pc[1]))), 0)
        y1 = min(int(np.ceil(max(pa[1], pb[1], pc[1]))), size - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1, dtype=F), np.arange(y0, y1 + 1, dtype=F))
        v0, v1 = pb - pa, pc - pa
        den = v0[0] * v1[1] - v1[0] * v0[1]
        if abs(den) < 1e-12:
            continue
        wx, wy = xs - pa[0], ys - pa[1]
        l1 = (wx * v1[1] - v1[0] * wy) / den
        l2 = (v0[0] * wy - wx * v0[1]) / den
        l0 = 1 - l1 - l2
        eps = -0.02
        inside = (l0 >= eps) & (l1 >= eps) & (l2 >= eps)
        if not inside.any():
            continue
        iy = ys[inside].astype(int)
        ix = xs[inside].astype(int)
        tri[iy, ix] = f
        bary[iy, ix] = np.stack([l0[inside], l1[inside], l2[inside]], 1)
    return tri, bary


def laplacian(eval_d, p, e):
    total = np.zeros(len(p), F)
    for ax in range(3):
        o = np.zeros(3, F)
        o[ax] = e
        total += eval_d(p + o) + eval_d(p - o)
    return (total - 6 * eval_d(p)) / (e * e)


def ambient_occlusion(eval_d, p, n, reach, steps=6):
    occ = np.zeros(len(p), F)
    w = 1.0
    for i in range(1, steps + 1):
        h = reach * i / steps
        d = eval_d(p + n * h)
        occ += w * np.maximum(h - d, 0) / h
        w *= 0.7
    return np.clip(1 - occ * 0.55, 0, 1)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def to_lin(c):
    return (np.asarray(c, F) / 255.0) ** 2.2


def per_texel(texel, salt):
    """A random number in [0, 1) for each texel, stable across bakes."""
    ids = np.stack([texel, np.full(len(texel), salt), np.zeros(len(texel), np.int64)], 1).astype(np.int64)
    return hash3(ids, 0)


def style_pass(st, col, spec, n, texel, edge, crease, paint, glow):
    """The crunch look on top of the shading: per-texel grain, rust specks, white chips on
    edges and a cool sheen on upward bevels. Everything is per texel, so it reads as the
    chunky pixels it is."""
    r = [per_texel(texel, k) for k in range(6)]
    grain = st.get("grain", 0)
    col = col * (1 + grain * (r[0] * 2 - 1))[:, None]
    tint = st.get("grain-tint", 0)
    col = col * (1 + tint * np.stack([r[1] - 0.5, r[1] * 0.4 - 0.2, 0.5 - r[1]], 1))
    cool = st.get("cool-edges", 0) * edge * smoothstep(0.2, 0.8, n[:, 1])
    col = col * (1 - cool[:, None]) + to_lin((178, 192, 214)) * cool[:, None]
    chips = (r[2] < st.get("chips", 0) * edge * 0.8) & ~glow
    col = np.where(chips[:, None], to_lin((206, 206, 200)) * (0.85 + 0.3 * r[3][:, None]), col)
    specks = (r[4] < st.get("rust-specks", 0) * (0.4 + 2.5 * edge + 2.0 * crease)) & ~glow
    rust = to_lin((196, 98, 38)) * (0.6 + 0.6 * r[5][:, None])
    col = np.where(specks[:, None], rust, col)
    spec = np.where(chips, spec + 0.3, np.where(specks, spec * 0.3, spec))
    return col, spec


def shade(scene, p, n, unit, piece, texel):
    """Albedo (linear) and spec for texel points p with normals n, each on scene.pieces[piece].
    unit is a typical detail size in model units, used for wear widths and noise scale."""
    solid = scene.bake_nodes(include_free=False)
    # material comes from the texel's own piece, so overlapping pieces can't steal it
    mat = np.zeros(len(p), np.int16)
    for k in np.unique(piece):
        idx = np.nonzero(piece == k)[0]
        _, mat[idx] = scene.pieces[k].bake_node().eval(p[idx] - n[idx] * unit * 0.05)
    mats = scene.materials
    base = np.array([to_lin(m.color) for m in mats], F)[mat]
    wear_col = np.array([to_lin(m.wear) for m in mats], F)[mat]
    spec = np.array([m.spec for m in mats], F)[mat]
    kind = np.array([m.kind for m in mats])[mat]
    paint = kind == "paint"
    metal = kind == "metal"
    glow = kind == "glow"

    def dist(q):
        return scene.union_eval(q, solid, pad=unit * 8)[0]

    # curvature: positive on convex edges, negative in creases and grooves
    curv = laplacian(dist, p, unit * 0.6) * unit * 0.6
    ao_near = ambient_occlusion(dist, p + n * unit * 0.05, n, unit * 1.5)
    ao_far = ambient_occlusion(dist, p + n * unit * 0.05, n, unit * 7.0)
    ao = ao_near * (0.35 + 0.65 * ao_far)
    st = scene.style
    if st:
        ao = 1 - (1 - ao) * st.get("grime", 1.0)

    # breakup noise at a few scales
    big = fbm(p / (unit * 25), 3, seed=1)
    mid = fbm(p / (unit * 4), 4, seed=7)
    fine = fbm(p / (unit * 0.6), 3, seed=13)

    col = base * (0.9 + 0.2 * mid[:, None])[:, :]

    # worn edges: paint chips show what is underneath, bare metal gets polished
    edge = smoothstep(0.25, 1.1, curv + (fine - 0.5) * 0.8)
    chip = edge * smoothstep(0.35, 0.65, mid + 0.25 * fine)
    col = np.where(paint[:, None], col * (1 - chip[:, None]) + wear_col * chip[:, None], col)
    spec = np.where(paint, spec + chip * 0.35, spec)
    shine = metal * edge * 0.6
    col = col * (1 + shine[:, None] * 1.4)
    spec = spec + shine * 0.3

    # grime collects in creases, under overhangs and on lower faces
    crease = smoothstep(0.1, 1.2, -curv)
    low = smoothstep(0.2, -0.9, n[:, 1]) * 0.25
    grime = np.clip(crease * 0.9 + (1 - ao_near) * 1.1 + low, 0, 1) * (0.55 + 0.8 * big)
    blotch = smoothstep(0.55, 0.8, fbm(p / (unit * 9), 4, seed=31)) * 0.35
    grime = np.clip(grime + blotch, 0, 1)
    dirt_col = to_lin((58, 44, 30))
    col = col * (1 - 0.7 * grime[:, None]) + dirt_col * 0.7 * grime[:, None] * 0.5
    speck = (fine > 0.78) & paint
    col = np.where(speck[:, None], col * 0.75 + dirt_col * 0.1, col)
    spec = spec * (1 - 0.6 * grime)

    # rust: patchy, worse in creases, under overhangs and where paint has chipped,
    # bleeding down in streaks; how much varies from region to region
    if scene.rust > 0:
        rust_mat = np.array([m.rust for m in mats], F)[mat]
        region = fbm(p / (unit * 30), 2, seed=61)
        patch = fbm(p / (unit * 5), 4, seed=53)
        streak = fbm(p * np.array([1, 0.08, 1], F) / (unit * 1.5), 3, seed=57)
        drip = smoothstep(0.1, -0.6, n[:, 1]) * 0.25 + (1 - ao_near) * 0.5
        want = patch + 0.55 * crease + drip + 0.45 * streak * smoothstep(0.3, 0.7, region) + 0.6 * chip
        amount = smoothstep(0.95, 1.35, want + region * 0.5) * rust_mat * scene.rust * (st.get("rust", 0.12) if st else 1.0)
        rust_col = to_lin((66, 32, 16)) * (1 - fine[:, None]) + to_lin((150, 72, 30)) * fine[:, None]
        col = col * (1 - amount[:, None]) + rust_col * amount[:, None]
        spec = spec * (1 - 0.8 * amount)

    # light streaky scratches on paint
    streak = fbm(p * np.array([1, 12, 1], F) / (unit * 3), 2, seed=21)
    col = np.where(paint[:, None], col * (0.96 + 0.08 * streak[:, None]), col)

    col = col * ao[:, None]
    if st:
        col, spec = style_pass(st, col, spec, n, texel, edge, crease, paint, glow)
    col = np.where(glow[:, None], base * (1.2 + 0.3 * fine[:, None]), col)

    col, spec = apply_decals(scene, p, n, col, spec)
    return col, np.clip(spec, 0, 1)


def apply_decals(scene, p, n, col, spec):
    for dc in scene.decals:
        img = np.asarray(dc.image.convert("RGBA"), F) / 255.0
        o = np.asarray(dc.origin, F)
        U = np.asarray(dc.u_axis, F)
        V = np.asarray(dc.v_axis, F)
        N = np.cross(U, V)
        rel = p - o
        u = rel @ U / dc.size[0] + 0.5
        v = rel @ V / dc.size[1] + 0.5
        w = rel @ N
        hit = (u >= 0) & (u < 1) & (v >= 0) & (v < 1) & (np.abs(w) < dc.depth) & (n @ N > 0.25)
        idx = np.nonzero(hit)[0]
        if len(idx) == 0:
            continue
        ih, iw = img.shape[:2]
        px = np.clip((u[idx] * iw).astype(int), 0, iw - 1)
        py = np.clip(((1 - v[idx]) * ih).astype(int), 0, ih - 1)
        s = img[py, px]
        a = s[:, 3:4]
        if dc.mode == "dirt":
            col[idx] = col[idx] * (1 - a * 0.6)
            continue
        lin = s[:, :3] ** 2.2
        # keep some of the underlying shading so decals sit in the grime
        lum = np.clip(col[idx].mean(1, keepdims=True) / np.maximum(lin.mean(1, keepdims=True), 0.05), 0.4, 1.0)
        col[idx] = col[idx] * (1 - a) + lin * lum * a
        spec[idx] = spec[idx] * (1 - a[:, 0]) + 0.35 * a[:, 0]
    return col, spec


_JOB = None


def _shade_chunk(span):
    scene, p, n, unit, piece, texel = _JOB
    a, b = span
    return shade(scene, p[a:b], n[a:b], unit, piece[a:b], texel[a:b])


def bake(scene, verts, normals, faces, uvs, size, unit, face_piece):
    tri, bary = rasterize(uvs, faces, size)
    covered = tri >= 0
    ys, xs = np.nonzero(covered)
    t = tri[ys, xs]
    b = bary[ys, xs]
    f = faces[t]
    p = (verts[f] * b[:, :, None]).sum(1)
    nn = (normals[f] * b[:, :, None]).sum(1)
    nn /= np.maximum(np.linalg.norm(nn, axis=1), 1e-9)[:, None]
    print(f"  baking {len(p)} texels")

    # shade in parallel; workers inherit the scene through fork
    global _JOB
    _JOB = (scene, p, nn, unit, face_piece[t], ys.astype(np.int64) * size + xs)
    chunk = 20_000
    starts = list(range(0, len(p), chunk))
    with mp.get_context("fork").Pool(os.cpu_count()) as pool:
        parts = pool.map(_shade_chunk, [(s, s + chunk) for s in starts])
    col = np.concatenate([c for c, _ in parts])
    spec = np.concatenate([s for _, s in parts])

    srgb = np.clip(col, 0, 1) ** (1 / 2.2)
    img = np.zeros((size, size, 4), F)
    img[ys, xs, :3] = srgb
    img[ys, xs, 3] = spec

    # bleed chart colours outward so mips and filtering never pull in the background
    _, (iy, ix) = ndimage.distance_transform_edt(~covered, return_indices=True)
    img = img[iy, ix]
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
