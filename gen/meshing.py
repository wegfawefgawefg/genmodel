"""SDF -> triangles: narrow-band sampling, marching cubes, quadric decimation, crease normals."""

import math

import numpy as np
import pyfqmr
from scipy import ndimage
from skimage import measure

F = np.float32


def eval_chunked(fn, pts, chunk=400_000):
    out = np.empty(len(pts), F)
    for i in range(0, len(pts), chunk):
        out[i : i + chunk] = fn(pts[i : i + chunk])
    return out


def grid_points(lo, h, dims):
    axes = [lo[i] + h * np.arange(dims[i], dtype=F) for i in range(3)]
    g = np.stack(np.meshgrid(*axes, indexing="ij"), -1)
    return g.reshape(-1, 3)


def sample_volume(dist, lo, hi, h, coarse=4):
    """Distance volume at spacing h. Far from the surface values are trilinear from a
    coarse pass; only cells near the surface are evaluated exactly."""
    n_coarse = np.ceil((hi - lo) / (h * coarse)).astype(int) + 1
    dims = (n_coarse - 1) * coarse + 1
    cvol = eval_chunked(dist, grid_points(lo, h * coarse, n_coarse)).reshape(n_coarse)

    # coarse cells that might hold surface, grown by one so fine boundaries are safe
    near = np.abs(cvol) < h * coarse * 1.8
    near = ndimage.binary_dilation(near, iterations=1)

    idx = np.indices(dims, dtype=np.float32).reshape(3, -1) / coarse
    vol = ndimage.map_coordinates(cvol, idx, order=1).reshape(dims).astype(F)
    fine_near = near
    for ax in range(3):
        fine_near = np.repeat(fine_near, coarse, axis=ax)
    fine_near = fine_near[: dims[0], : dims[1], : dims[2]]
    ids = np.nonzero(fine_near.reshape(-1))[0]
    ii = np.stack(np.unravel_index(ids, dims), 1).astype(F)
    vol.reshape(-1)[ids] = eval_chunked(dist, lo + ii * h)
    return vol


def mesh_sdf(dist, lo, hi, h):
    lo = np.asarray(lo, F) - 3 * h
    hi = np.asarray(hi, F) + 3 * h
    vol = sample_volume(dist, lo, hi, h)
    if vol.min() >= 0 or vol.max() <= 0:
        return np.zeros((0, 3), F), np.zeros((0, 3), np.int32)
    verts, faces, _, _ = measure.marching_cubes(vol, 0.0, spacing=(h, h, h))
    verts = verts.astype(F) + lo
    # skimage's winding already faces outward (counter-clockwise) for an sdf
    faces = faces.astype(np.int32)
    return verts, faces


def project_to_surface(dist, verts, h, steps=2):
    """Newton steps along the field gradient; pulls decimated vertices back onto the surface."""
    e = h * 0.25
    for _ in range(steps):
        d = eval_chunked(dist, verts)
        g = np.zeros_like(verts)
        for ax in range(3):
            o = np.zeros(3, F)
            o[ax] = e
            g[:, ax] = (eval_chunked(dist, verts + o) - eval_chunked(dist, verts - o)) / (2 * e)
        gl = np.maximum(np.linalg.norm(g, axis=1), 1e-6)
        step = np.clip(d, -h, h)
        verts = verts - (step / gl / gl)[:, None] * g
    return verts


def decimate(verts, faces, target, aggressiveness=6):
    """Quadric decimation to about `target` triangles. One pyfqmr run can stall well above
    a small target (it runs out of iterations), so run again while it still makes progress."""
    v, f = verts.astype(np.float64), faces.astype(np.int32)
    for _ in range(4):
        s = pyfqmr.Simplify()
        s.setMesh(v, f)
        s.simplify_mesh(target_count=int(target), aggressiveness=aggressiveness, preserve_border=True, verbose=False)
        v2, f2, _ = s.getMesh()
        progress = len(f2) < len(f) * 0.98
        v, f = v2, f2
        if len(f) <= target * 1.05 or not progress:
            break
    return v.astype(F), f.astype(np.int32)


def face_normals(verts, faces):
    a = verts[faces[:, 0]]
    b = verts[faces[:, 1]]
    c = verts[faces[:, 2]]
    n = np.cross(b - a, c - a)
    area = np.linalg.norm(n, axis=1)
    return n / np.maximum(area, 1e-12)[:, None], area * 0.5


def drop_degenerate(verts, faces):
    _, area = face_normals(verts, faces)
    ok = (area > 1e-10) & (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    return faces[ok]


def surface_normals(dist, verts, faces, h, merge_deg=40.0):
    """Normals from the field itself. Each face corner samples the gradient a little way
    into its own face, so a corner on a real crease sees its own side; corners that agree
    are welded and averaged. Returns new (verts, normals, faces), split only at creases."""
    fn, _ = face_normals(verts, faces)
    cen = verts[faces].mean(1)
    q = verts[faces] * 0.85 + cen[:, None, :] * 0.15
    g_side = field_gradient(dist, q.reshape(-1, 3), h * 0.1).reshape(-1, 3, 3)
    g_vert = field_gradient(dist, verts, h * 0.05)[faces]
    # smooth surface: the exact normal at the vertex fits every face around it
    smooth = np.sum(g_vert * fn[:, None, :], 2) > math.cos(math.radians(50))
    side_ok = np.sum(g_side * fn[:, None, :], 2) > 0.5
    corner_n = np.where(smooth[:, :, None], g_vert, np.where(side_ok[:, :, None], g_side, fn[:, None, :]))
    corner_n = corner_n.reshape(-1, 3)

    return weld_corners(verts, faces, corner_n, merge_deg)


def crease_split(verts, faces, crease_deg=20.0):
    """Flat-shaded look: each face keeps its own normal, but neighbours within crease_deg
    share an averaged one, so flat panels stay one smooth piece and facets stay sharp."""
    fn, _ = face_normals(verts, faces)
    return weld_corners(verts, faces, np.repeat(fn, 3, axis=0), crease_deg)


def weld_corners(verts, faces, corner_n, merge_deg):
    """Per vertex, greedily cluster its face corners by normal and average each cluster;
    returns (verts, normals, faces) with a vertex per cluster."""
    cos_t = math.cos(math.radians(merge_deg))
    corner_v = faces.reshape(-1)
    order = np.argsort(corner_v, kind="stable")
    sv = corner_v[order]
    starts = np.flatnonzero(np.r_[True, sv[1:] != sv[:-1]])
    ends = np.r_[starts[1:], len(sv)]
    # greedy clusters per vertex: a corner joins the first cluster whose seed it agrees with
    out_n = corner_n.copy()
    cluster = np.zeros(len(corner_v), np.int64)
    for s, e in zip(starts, ends):
        cs = order[s:e]
        n = corner_n[cs]
        ids = np.full(len(cs), -1)
        seeds = []
        for i in range(len(cs)):
            for c, seed in enumerate(seeds):
                if n[i] @ n[seed] > cos_t:
                    ids[i] = c
                    break
            if ids[i] < 0:
                ids[i] = len(seeds)
                seeds.append(i)
        for c in range(len(seeds)):
            members = ids == c
            avg = n[members].sum(0)
            out_n[cs[members]] = avg / max(np.linalg.norm(avg), 1e-12)
        cluster[cs] = ids

    key = corner_v.astype(np.int64) * 64 + cluster
    _, first, inverse = np.unique(key, return_index=True, return_inverse=True)
    return verts[corner_v[first]], out_n[first], inverse.reshape(-1, 3).astype(np.int32)


def field_gradient(dist, p, e):
    g = np.zeros_like(p)
    for ax in range(3):
        o = np.zeros(3, F)
        o[ax] = e
        g[:, ax] = eval_chunked(dist, p + o) - eval_chunked(dist, p - o)
    return g / np.maximum(np.linalg.norm(g, axis=1), 1e-9)[:, None]


# for an edge along axis a, the two other axes in right-handed order
OTHER = {0: (1, 2), 1: (2, 0), 2: (0, 1)}


def dual_contour(dist, lo, hi, h):
    """Dual contouring: one vertex per surface cell placed by a QEF of the edge
    crossings, so flat panels stay flat and creases stay sharp."""
    lo = np.asarray(lo, F) - 3 * h
    hi = np.asarray(hi, F) + 3 * h
    vol = sample_volume(dist, lo, hi, h)
    dims = np.array(vol.shape)
    inside = vol < 0
    cdims = dims - 1
    n_cells = int(np.prod(cdims))

    pts, nrm, cells4, flip = [], [], [], []
    for a in range(3):
        # sign-changing edges along axis a
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[a] = slice(0, -1)
        sl1[a] = slice(1, None)
        change = inside[tuple(sl0)] != inside[tuple(sl1)]
        ijk = np.argwhere(change)
        if len(ijk) == 0:
            continue
        v0 = vol[tuple(sl0)][change]
        v1 = vol[tuple(sl1)][change]
        t = np.clip(v0 / (v0 - v1), 0, 1)
        p = lo + ijk.astype(F) * h
        p[:, a] += t * h
        # one secant step against the true field
        d = eval_chunked(dist, p)
        p[:, a] -= np.clip(d * np.sign(v1 - v0), -h, h)
        p[:, a] = np.clip(p[:, a], lo[a] + ijk[:, a] * h, lo[a] + (ijk[:, a] + 1) * h)
        n = field_gradient(dist, p, h * 0.1)

        # the four cells around the edge, counter-clockwise seen from +a
        b, c = OTHER[a]
        quad = []
        valid = np.ones(len(ijk), bool)
        for db, dc in ((1, 1), (0, 1), (0, 0), (1, 0)):
            cell = ijk.copy()
            cell[:, b] -= db
            cell[:, c] -= dc
            valid &= np.all((cell >= 0) & (cell < cdims), axis=1)
            quad.append(np.ravel_multi_index(np.clip(cell, 0, cdims - 1).T, cdims))
        quad = np.stack(quad, 1)
        pts.append(p[valid])
        nrm.append(n[valid])
        cells4.append(quad[valid])
        flip.append(~inside[tuple(ijk[valid].T)])
    pts = np.concatenate(pts)
    nrm = np.concatenate(nrm)
    cells4 = np.concatenate(cells4)
    flip = np.concatenate(flip)

    # accumulate the quadric of every crossing into its four cells
    cell_ids = cells4.reshape(-1)
    rep = np.repeat(np.arange(len(pts)), 4)
    P, N = pts[rep], nrm[rep]
    nb = np.sum(N * P, 1)
    used, inv = np.unique(cell_ids, return_inverse=True)
    m = len(used)
    ata = np.zeros((m, 3, 3), np.float64)
    atb = np.zeros((m, 3), np.float64)
    for r in range(3):
        atb[:, r] = np.bincount(inv, N[:, r] * nb, m)
        for s in range(3):
            ata[:, r, s] = np.bincount(inv, N[:, r] * N[:, s], m)
    count = np.bincount(inv, None, m)
    mass = np.stack([np.bincount(inv, P[:, r], m) for r in range(3)], 1) / count[:, None]

    # solve around the mass point, dropping weak directions
    rhs = atb - np.einsum("mij,mj->mi", ata, mass)
    U, S, Vt = np.linalg.svd(ata)
    Sinv = np.where(S > 0.1 * S[:, :1], 1.0 / np.maximum(S, 1e-12), 0.0)
    x = mass + np.einsum("mji,mj,mkj,mk->mi", Vt, Sinv, U, rhs)
    corner = lo + np.stack(np.unravel_index(used, cdims), 1) * h
    x = np.clip(x, corner - 0.1 * h, corner + 1.1 * h).astype(F)

    # quads to triangles, split on the shorter diagonal
    q = inv.reshape(-1, 4)
    q = np.where(flip[:, None], q[:, ::-1], q)
    d02 = np.sum((x[q[:, 0]] - x[q[:, 2]]) ** 2, 1)
    d13 = np.sum((x[q[:, 1]] - x[q[:, 3]]) ** 2, 1)
    use02 = d02 <= d13
    t1 = np.where(use02[:, None], q[:, [0, 1, 2]], q[:, [0, 1, 3]])
    t2 = np.where(use02[:, None], q[:, [0, 2, 3]], q[:, [1, 2, 3]])
    faces = np.concatenate([t1, t2]).astype(np.int32)
    return weld(x, faces, h * 1e-3)


def weld(verts, faces, eps):
    """Merges vertices closer than eps and drops faces that collapse. Unlike dropping
    every zero-area face, this never opens holes (which stall decimation at their rims)."""
    key = np.round(verts / eps).astype(np.int64)
    _, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inverse = inverse.reshape(-1)
    f = inverse[faces]
    ok = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    return verts[first], f[ok].astype(np.int32)
