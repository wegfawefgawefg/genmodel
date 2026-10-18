"""Clean low-poly meshes straight from SDF primitives, for the old-fashioned look.

polygonize(node) walks a piece's SDF tree and emits each primitive as the polygon model
an artist would make: chamfered boxes, n-sided prisms with bevelled ends, extruded and
bevelled profiles, low tori, tubes lofted along curves. Unions just overlap (no booleans),
so there are no needles or slivers from decimating a dense surface. A tree with a cut,
intersection or shell returns None and the caller falls back to contouring.
"""

import math

import numpy as np
from scipy.spatial import ConvexHull

import sdf

F = np.float32


def sides():
    return sdf.FACETS if sdf.FACETS > 0 else 8


def fan_polygons(verts, polys):
    tris = []
    for loop in polys:
        for i in range(1, len(loop) - 1):
            tris.append((loop[0], loop[i], loop[i + 1]))
    return verts.astype(F), np.array(tris, np.int32).reshape(-1, 3)


def hull(points):
    """Convex hull with coplanar triangles merged back into polygons, each fanned from one
    corner, so a box face is two triangles and an octagon cap a tidy fan."""
    pts = np.asarray(points, np.float64)
    h = ConvexHull(pts)
    groups = {}
    for simplex, eq in zip(h.simplices, h.equations):
        key = tuple(np.round(eq, 4))
        groups.setdefault(key, []).append(simplex)
    polys = []
    for key, tris in groups.items():
        normal = np.array(key[:3])
        # boundary edges: those used once inside the group
        count = {}
        for t in tris:
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                e = (min(a, b), max(a, b))
                count[e] = count.get(e, 0) + 1
        edges = [e for e, c in count.items() if c == 1]
        nxt = {}
        for a, b in edges:
            nxt.setdefault(a, []).append(b)
            nxt.setdefault(b, []).append(a)
        start = edges[0][0]
        loop, prev, cur = [start], None, start
        while True:
            cand = [x for x in nxt[cur] if x != prev]
            if not cand or cand[0] == start:
                break
            prev, cur = cur, cand[0]
            loop.append(cur)
        # wind counter-clockwise seen from outside
        p = pts[loop]
        area = np.cross(p[1] - p[0], p[2] - p[0])
        for i in range(2, len(p) - 1):
            area = area + np.cross(p[i] - p[0], p[i + 1] - p[0])
        if area @ normal < 0:
            loop.reverse()
        polys.append(loop)
    return fan_polygons(pts, polys)


def ring(radius, n, angle0, along, axis, frame_axes=None):
    """n points of a polygon whose flat sides face angle 0 (matching sdf.radial)."""
    i = "xyz".index(axis)
    a_idx, b_idx = [(1, 2), (0, 2), (0, 1)][i]
    out = []
    for k in range(n):
        ang = angle0 + 2 * math.pi * k / n
        p = [0.0, 0.0, 0.0]
        p[i] = along
        p[a_idx] = radius * math.cos(ang)
        p[b_idx] = radius * math.sin(ang)
        out.append(p)
    return out


def prism_rings(r, h, bevel, axis, n):
    """A polygonal cylinder: apothem r, half length h, ends bevelled by `bevel`."""
    circ = r / math.cos(math.pi / n)
    a0 = math.pi / n
    pts = []
    if bevel > 0:
        inner = (r - bevel) / math.cos(math.pi / n)
        for s in (-1, 1):
            pts += ring(circ, n, a0, s * (h - bevel), axis)
            pts += ring(inner, n, a0, s * h, axis)
    else:
        for s in (-1, 1):
            pts += ring(circ, n, a0, s * h, axis)
    return pts


def box_points(hx, hy, hz, b):
    pts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                if b <= 0:
                    pts.append((sx * hx, sy * hy, sz * hz))
                    continue
                pts.append((sx * (hx - b), sy * (hy - b), sz * hz))
                pts.append((sx * hx, sy * (hy - b), sz * (hz - b)))
                pts.append((sx * (hx - b), sy * hy, sz * (hz - b)))
    return pts


def ear_clip(poly):
    """Triangulates a simple counter-clockwise 2d polygon; returns index triples."""
    idx = list(range(len(poly)))
    tris = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        n = len(idx)
        for k in range(n):
            i0, i1, i2 = idx[(k - 1) % n], idx[k], idx[(k + 1) % n]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if cross(a, b, c) <= 1e-12:
                continue
            inside = False
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p = poly[j]
                if cross(a, b, p) >= 0 and cross(b, c, p) >= 0 and cross(c, a, p) >= 0:
                    inside = True
                    break
            if not inside:
                tris.append((i0, i1, i2))
                idx.pop(k)
                break
        else:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


def ccw(poly):
    p = np.asarray(poly, np.float64)
    area = 0.5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])
    return p if area > 0 else p[::-1]


def inset(poly, d):
    """Moves each edge of a ccw polygon inward by d (mitred corners)."""
    p = np.asarray(poly, np.float64)
    n = len(p)
    out = []
    for i in range(n):
        a, b, c = p[i - 1], p[i], p[(i + 1) % n]
        e1, e2 = b - a, c - b
        n1 = np.array([-e1[1], e1[0]]) / np.linalg.norm(e1)
        n2 = np.array([-e2[1], e2[0]]) / np.linalg.norm(e2)
        bis = n1 + n2
        bis /= max(np.linalg.norm(bis), 1e-9)
        out.append(b + bis * d / max(bis @ n1, 0.3))
    return np.array(out)


def extrude(poly2d, hz, bevel, to3d):
    """A bevelled slab from a 2d profile: walls, bevel bands and ear-clipped caps.
    to3d(u, v, w) maps profile coordinates and depth to model space."""
    outer = ccw(poly2d)
    n = len(outer)
    rings = []
    if bevel > 0:
        cap = inset(outer, bevel)
        rings = [(cap, -hz), (outer, -(hz - bevel)), (outer, hz - bevel), (cap, hz)]
    else:
        rings = [(outer, -hz), (outer, hz)]
    verts = []
    for loop, w in rings:
        verts += [to3d(u, v, w) for u, v in loop]
    tris = []
    for r in range(len(rings) - 1):
        a0, b0 = r * n, (r + 1) * n
        for i in range(n):
            j = (i + 1) % n
            tris += [(a0 + i, a0 + j, b0 + j), (a0 + i, b0 + j, b0 + i)]
    caps = ear_clip(rings[0][0])
    last = (len(rings) - 1) * n
    tris += [(c, b, a) for a, b, c in caps]
    tris += [(last + a, last + b, last + c) for a, b, c in caps]
    v = np.array(verts, F)
    t = np.array(tris, np.int32)
    return orient_outward(v, t)


def orient_outward(v, t):
    """Flips the whole mesh if it came out inside-out (signed volume negative)."""
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    vol = np.sum(np.einsum("ij,ij->i", a, np.cross(b, c)))
    return (v, t) if vol >= 0 else (v, t[:, ::-1].copy())


def plane_map(plane):
    if plane == "xy":
        return lambda u, v, w: (u, v, w)
    if plane == "xz":
        return lambda u, v, w: (u, w, v)
    return lambda u, v, w: (w, u, v)


def torus_mesh(R, r, axis, n_major, n_minor):
    i = "xyz".index(axis)
    a_idx, b_idx = [(1, 2), (0, 2), (0, 1)][i]
    verts = []
    for j in range(n_major):
        th = 2 * math.pi * j / n_major
        for k in range(n_minor):
            ph = 2 * math.pi * k / n_minor
            rad = R + r * math.cos(ph)
            p = [0.0, 0.0, 0.0]
            p[a_idx], p[b_idx], p[i] = rad * math.cos(th), rad * math.sin(th), r * math.sin(ph)
            verts.append(p)
    tris = []
    for j in range(n_major):
        for k in range(n_minor):
            a = j * n_minor + k
            b = ((j + 1) % n_major) * n_minor + k
            c = ((j + 1) % n_major) * n_minor + (k + 1) % n_minor
            d = j * n_minor + (k + 1) % n_minor
            tris += [(a, b, c), (a, c, d)]
    return orient_outward(np.array(verts, F), np.array(tris, np.int32))


def loft(curve, profile, s0, s1, across, segments=None):
    """Sweeps a closed 2d profile (u across, v out) along the curve from s0 to s1, capped."""
    prof = ccw(profile)
    n = len(prof)
    seg = segments or max(2, int((s1 - s0) / 0.2))
    verts = []
    for k in range(seg + 1):
        s = s0 + (s1 - s0) * k / seg
        R, p = curve.frame_at(s, across)
        x_axis, z_axis = R[:, 0], R[:, 2]
        verts += [p + x_axis * u + z_axis * v for u, v in prof]
    tris = []
    for k in range(seg):
        a0, b0 = k * n, (k + 1) * n
        for i in range(n):
            j = (i + 1) % n
            tris += [(a0 + i, a0 + j, b0 + j), (a0 + i, b0 + j, b0 + i)]
    caps = ear_clip(prof)
    last = seg * n
    tris += [(c, b, a) for a, b, c in caps]
    tris += [(last + a, last + b, last + c) for a, b, c in caps]
    return orient_outward(np.array(verts, F), np.array(tris, np.int32))


def circle_profile(r, n):
    circ = r / math.cos(math.pi / n)
    return [(circ * math.cos(math.pi / n + 2 * math.pi * k / n), circ * math.sin(math.pi / n + 2 * math.pi * k / n))
            for k in range(n)]


def bend(node, depth_t=np.zeros(3, F)):
    """Bend of a straight child: a cylinder along x becomes a tube, a yz prism a loft."""
    child, t = node.child, np.zeros(3, F)
    if isinstance(child, sdf.Xform):
        t = child.t
        child = child.child
    lo, hi = child.bounds()
    s0, s1 = float(lo[0] + t[0]), float(hi[0] + t[0])
    if isinstance(child, sdf.Cylinder) and child.axis == "x":
        prof = [(u + t[1], v + t[2]) for u, v in circle_profile(child.r, sides())]
    elif isinstance(child, sdf.Prism) and child.plane == "yz":
        prof = [(u + t[1], v + t[2]) for u, v in child.v]
        s0, s1 = float(t[0] - child.hz), float(t[0] + child.hz)
    else:
        return None
    return loft(node.curve, prof, max(s0, 0.0), min(s1, node.curve.length), node.across)


def lathe_mesh(profile, n):
    """Rings of n sides at each profile point, joined by quads, capped where r > 0. Flat
    sides face angle 0 like sdf.radial (x then z)."""
    verts, rings = [], []
    for r, y in profile:
        circ = r / math.cos(math.pi / n)
        if r <= 1e-6:
            rings.append([len(verts)])
            verts.append((0.0, y, 0.0))
            continue
        idx = []
        for k in range(n):
            a = math.pi / n + 2 * math.pi * k / n
            idx.append(len(verts))
            verts.append((circ * math.cos(a), y, circ * math.sin(a)))
        rings.append(idx)
    tris = []
    for a, b in zip(rings[:-1], rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        for k in range(n):
            a0, a1 = a[k % len(a)], a[(k + 1) % len(a)]
            b0, b1 = b[k % len(b)], b[(k + 1) % len(b)]
            if len(a) == 1:
                tris.append((a0, b1, b0))
            elif len(b) == 1:
                tris.append((a0, a1, b0))
            else:
                tris += [(a0, a1, b1), (a0, b1, b0)]
    # rings run clockwise seen from +y, so the top cap fans backwards and the bottom forwards
    for ring, top in ((rings[0], True), (rings[-1], False)):
        if len(ring) > 1:
            for k in range(1, n - 1):
                tri = (ring[0], ring[k], ring[k + 1])
                tris.append(tri[::-1] if top else tri)
    return orient_outward(np.array(verts, F), np.array(tris, np.int32))


def polygonize(node):
    """(verts, faces) for a tree of supported nodes, or None."""
    n = sides()
    if isinstance(node, sdf.Box):
        return hull(box_points(*node.h, max(node.ch, node.r * 0.7)))
    if isinstance(node, sdf.Cylinder):
        return hull(prism_rings(node.r, node.h, max(node.ch, node.re * 0.7), node.axis, n))
    if isinstance(node, sdf.Cone):
        pts = []
        for r, w in ((node.r0, -node.h), (node.r1, node.h)):
            pts += [[0, 0, 0]] if r <= 1e-6 else []
            if r <= 1e-6:
                pts[-1]["xyz".index(node.axis)] = w
            else:
                pts += ring(r / math.cos(math.pi / n), n, math.pi / n, w, node.axis)
        return hull(pts)
    if isinstance(node, sdf.Sphere):
        pts = []
        for lat in np.linspace(-math.pi / 2, math.pi / 2, 5):
            for k in range(n if abs(lat) < 1.5 else 1):
                lon = 2 * math.pi * k / n
                pts.append((node.r * math.cos(lat) * math.cos(lon), node.r * math.sin(lat), node.r * math.cos(lat) * math.sin(lon)))
        return hull(pts)
    if isinstance(node, sdf.Lathe):
        return lathe_mesh(node.profile, node.sides or max(n, 12))
    if isinstance(node, sdf.Torus):
        return torus_mesh(node.R, node.r, node.axis, max(2 * n, 12), 6)
    if isinstance(node, sdf.Prism):
        return extrude(node.v, node.hz, node.r * 0.8, plane_map(node.plane))
    if isinstance(node, sdf.Sweep):
        prof = circle_profile(node.r0, n)
        return loft(node.curve, prof, 0.0, node.curve.length, (1, 0, 0))
    if isinstance(node, sdf.Bend):
        return bend(node)
    if isinstance(node, sdf.Xform):
        m = polygonize(node.child)
        if m is None:
            return None
        v, f = m
        # a reflection (mirrored left/right parts) turns faces inside out: rewind them
        if np.linalg.det(node.R) < 0:
            f = f[:, ::-1].copy()
        return (v @ node.R.T + node.t).astype(F), f
    if isinstance(node, (sdf.Paint, sdf.Round)):
        return polygonize(node.base if isinstance(node, sdf.Paint) else node.child)
    if isinstance(node, sdf.Union):
        return merge([polygonize(c) for c in node.children])
    if isinstance(node, sdf.Repeat):
        m = polygonize(node.child)
        if m is None:
            return None
        return merge([((m[0] + node.step * i).astype(F), m[1]) for i in range(node.count)])
    return None


def merge(meshes):
    if any(m is None for m in meshes) or not meshes:
        return None
    vs, fs, base = [], [], 0
    for v, f in meshes:
        vs.append(v)
        fs.append(f + base)
        base += len(v)
    return np.concatenate(vs).astype(F), np.concatenate(fs).astype(np.int32)
