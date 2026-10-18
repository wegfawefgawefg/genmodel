"""Signed distance nodes, evaluated on (N, 3) numpy point arrays.

Every node answers eval(p) -> (dist, mat) and bounds() -> (lo, hi) in its parent's space.
Leaves carry a material id; unions keep the material of whichever child is nearest.
"""

import math

import numpy as np

F = np.float32


def length(v, axis=-1):
    return np.sqrt(np.sum(v * v, axis=axis))


class Node:
    def eval(self, p):
        raise NotImplementedError

    def dist(self, p):
        return self.eval(p)[0]

    def bounds(self):
        raise NotImplementedError

    # chaining helpers so models read top to bottom
    def at(self, x, y, z):
        return Xform(self, np.eye(3, dtype=F), np.array([x, y, z], F))

    def rot(self, axis, deg):
        return Xform(self, rotation(axis, deg), np.zeros(3, F))

    def round(self, r):
        return Round(self, r)


def rotation(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], F)
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], F)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], F)


def axis_frame(p, axis):
    """Split p into (along, radial-2d) for an axis-aligned primitive."""
    if axis == "x":
        return p[:, 0], p[:, 1:3]
    if axis == "y":
        return p[:, 1], p[:, [0, 2]]
    return p[:, 2], p[:, 0:2]


def axis_half(axis, along, across):
    h = np.array([across, across, across], F)
    h["xyz".index(axis)] = along
    return h


class Leaf(Node):
    mat = 0

    def eval(self, p):
        d = self.sd(p)
        return d, np.full(len(p), self.mat, np.int16)


class Box(Leaf):
    """Box with half extents, optional rounded (r) or chamfered (ch) edges."""

    def __init__(self, hx, hy, hz, mat, r=0.0, ch=0.0):
        self.h = np.array([hx, hy, hz], F)
        self.mat, self.r, self.ch = mat, r, ch

    def sd(self, p):
        q = np.abs(p) - (self.h - self.r)
        out = length(np.maximum(q, 0)) + np.minimum(q.max(axis=1), 0) - self.r
        if self.ch > 0:
            a = np.abs(p)
            h = self.h
            k = 1.0 / math.sqrt(2.0)
            for i, j in ((0, 1), (1, 2), (0, 2)):
                out = np.maximum(out, (a[:, i] + a[:, j] - (h[i] + h[j] - self.ch)) * k)
        return out

    def bounds(self):
        return -self.h, self.h.copy()


class Sphere(Leaf):
    def __init__(self, r, mat):
        self.r, self.mat = r, mat

    def sd(self, p):
        return length(p) - self.r

    def bounds(self):
        h = np.full(3, self.r, F)
        return -h, h


class Cylinder(Leaf):
    """Capped cylinder along an axis, radius r, half length h, rounded rim r_edge."""

    def __init__(self, r, h, mat, axis="x", r_edge=0.0, ch=0.0):
        self.r, self.h, self.mat, self.axis, self.re, self.ch = r, h, mat, axis, r_edge, ch

    def sd(self, p):
        along, rad = axis_frame(p, self.axis)
        dx = length(rad) - self.r + self.re
        dy = np.abs(along) - self.h + self.re
        out = np.minimum(np.maximum(dx, dy), 0) + length(np.stack([np.maximum(dx, 0), np.maximum(dy, 0)], 1)) - self.re
        if self.ch > 0:
            out = np.maximum(out, (length(rad) + np.abs(along) - (self.r + self.h - self.ch)) / math.sqrt(2.0))
        return out

    def bounds(self):
        h = axis_half(self.axis, self.h, self.r)
        return -h, h


class Cone(Leaf):
    """Capped cone along an axis: radius r0 at -h, r1 at +h."""

    def __init__(self, r0, r1, h, mat, axis="x"):
        self.r0, self.r1, self.h, self.mat, self.axis = r0, r1, h, mat, axis

    def sd(self, p):
        along, rad = axis_frame(p, self.axis)
        q = np.stack([length(rad), along], 1)
        h, r1, r2 = self.h, self.r0, self.r1
        k1 = np.array([r2, h], F)
        k2 = np.array([r2 - r1, 2 * h], F)
        ca = np.stack([q[:, 0] - np.minimum(q[:, 0], np.where(q[:, 1] < 0, r1, r2)), np.abs(q[:, 1]) - h], 1)
        t = np.clip(((k1 - q) @ k2) / (k2 @ k2), 0, 1)
        cb = q - k1 + k2 * t[:, None]
        s = np.where((cb[:, 0] < 0) & (ca[:, 1] < 0), -1.0, 1.0)
        return s * np.sqrt(np.minimum(np.sum(ca * ca, 1), np.sum(cb * cb, 1)))

    def bounds(self):
        h = axis_half(self.axis, self.h, max(self.r0, self.r1))
        return -h, h


class Torus(Leaf):
    """Ring around an axis: major radius R, tube radius r."""

    def __init__(self, R, r, mat, axis="x"):
        self.R, self.r, self.mat, self.axis = R, r, mat, axis

    def sd(self, p):
        along, rad = axis_frame(p, self.axis)
        q = np.stack([length(rad) - self.R, along], 1)
        return length(q) - self.r

    def bounds(self):
        h = axis_half(self.axis, self.r, self.R + self.r)
        return -h, h


class Capsule(Leaf):
    def __init__(self, a, b, r, mat):
        self.a, self.b, self.r, self.mat = np.array(a, F), np.array(b, F), r, mat

    def sd(self, p):
        pa = p - self.a
        ba = self.b - self.a
        t = np.clip(pa @ ba / (ba @ ba), 0, 1)
        return length(pa - t[:, None] * ba) - self.r

    def bounds(self):
        return np.minimum(self.a, self.b) - self.r, np.maximum(self.a, self.b) + self.r


def sd_polygon(q, verts):
    """Signed distance to a closed 2d polygon (Inigo Quilez), q is (N, 2)."""
    v = np.asarray(verts, F)
    d = np.sum((q - v[0]) ** 2, 1)
    s = np.ones(len(q), F)
    n = len(v)
    for i in range(n):
        j = (i - 1) % n
        e = v[j] - v[i]
        w = q - v[i]
        b = w - e * np.clip((w @ e) / (e @ e), 0, 1)[:, None]
        d = np.minimum(d, np.sum(b * b, 1))
        c1 = q[:, 1] >= v[i][1]
        c2 = q[:, 1] < v[j][1]
        c3 = e[0] * w[:, 1] > e[1] * w[:, 0]
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return s * np.sqrt(d)


class Prism(Leaf):
    """A 2d profile in the xy plane extruded along z (half depth hz), edges rounded by r.

    plane="xz" extrudes along y instead, plane="yz" along x.
    """

    def __init__(self, verts, hz, mat, r=0.0, plane="xy"):
        self.v = np.asarray(verts, F)
        self.hz, self.mat, self.r, self.plane = hz, mat, r, plane

    def split(self, p):
        if self.plane == "xy":
            return p[:, 0:2], p[:, 2]
        if self.plane == "xz":
            return p[:, [0, 2]], p[:, 1]
        return p[:, 1:3], p[:, 0]

    def sd(self, p):
        q, z = self.split(p)
        d2 = sd_polygon(q, self.v) + self.r
        dz = np.abs(z) - self.hz + self.r
        return np.minimum(np.maximum(d2, dz), 0) + length(np.stack([np.maximum(d2, 0), np.maximum(dz, 0)], 1)) - self.r

    def bounds(self):
        lo2, hi2 = self.v.min(0), self.v.max(0)
        if self.plane == "xy":
            return np.array([lo2[0], lo2[1], -self.hz], F), np.array([hi2[0], hi2[1], self.hz], F)
        if self.plane == "xz":
            return np.array([lo2[0], -self.hz, lo2[1]], F), np.array([hi2[0], self.hz, hi2[1]], F)
        return np.array([-self.hz, lo2[0], lo2[1]], F), np.array([self.hz, hi2[0], hi2[1]], F)


def hexagon(r):
    return [(r * math.cos(math.radians(30 + 60 * i)), r * math.sin(math.radians(30 + 60 * i))) for i in range(6)]


def bolt(r, h, mat, axis="z"):
    """Hex bolt head sticking out along +axis from the origin."""
    plane = {"z": "xy", "y": "xz", "x": "yz"}[axis]
    head = Prism(hexagon(r), h * 0.5, mat, r=min(r, h) * 0.15, plane=plane)
    off = [0.0, 0.0, 0.0]
    off["xyz".index(axis)] = h * 0.5
    return head.at(*off)


class Xform(Node):
    """Places a child: world = R @ local + t."""

    def __init__(self, child, R, t):
        self.child, self.R, self.t = child, R, t

    def at(self, x, y, z):
        return Xform(self.child, self.R, self.t + np.array([x, y, z], F))

    def rot(self, axis, deg):
        R = rotation(axis, deg)
        return Xform(self.child, R @ self.R, R @ self.t)

    def eval(self, p):
        return self.child.eval((p - self.t) @ self.R)

    def bounds(self):
        lo, hi = self.child.bounds()
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], F)
        w = corners @ self.R.T + self.t
        return w.min(0), w.max(0)


def nearest(a, b):
    """Union of two (dist, mat) pairs."""
    pick = b[0] < a[0]
    return np.where(pick, b[0], a[0]), np.where(pick, b[1], a[1])


class Union(Node):
    def __init__(self, *children, k=0.0):
        self.children = [c for c in children if c is not None]
        self.k = k

    def eval(self, p):
        d, m = self.children[0].eval(p)
        for c in self.children[1:]:
            d2, m2 = c.eval(p)
            if self.k > 0:
                h = np.clip(0.5 + 0.5 * (d2 - d) / self.k, 0, 1)
                m = np.where(d2 < d, m2, m)
                d = d2 * (1 - h) + d * h - self.k * h * (1 - h)
            else:
                m = np.where(d2 < d, m2, m)
                d = np.minimum(d, d2)
        return d, m

    def bounds(self):
        bs = [c.bounds() for c in self.children]
        return np.min([b[0] for b in bs], 0) - self.k, np.max([b[1] for b in bs], 0) + self.k


class Cut(Node):
    """a minus b; k > 0 rounds the cut edge, ch > 0 chamfers it. The cut wall takes
    b's material when cut_mat is True, otherwise keeps a's."""

    def __init__(self, a, b, k=0.0, ch=0.0, cut_mat=False):
        self.a, self.b, self.k, self.ch, self.cut_mat = a, b, k, ch, cut_mat

    def eval(self, p):
        da, ma = self.a.eval(p)
        db, mb = self.b.eval(p)
        nb = -db
        if self.k > 0:
            h = np.clip(0.5 - 0.5 * (nb - da) / self.k, 0, 1)
            d = nb * (1 - h) + da * h + self.k * h * (1 - h)
        else:
            d = np.maximum(da, nb)
        if self.ch > 0:
            d = np.maximum(d, (da + nb + self.ch) / math.sqrt(2.0))
        m = np.where((nb > da) & self.cut_mat, mb, ma)
        return d, m

    def bounds(self):
        return self.a.bounds()


class Intersect(Node):
    def __init__(self, a, b, k=0.0):
        self.a, self.b, self.k = a, b, k

    def eval(self, p):
        da, ma = self.a.eval(p)
        db, _ = self.b.eval(p)
        if self.k > 0:
            h = np.clip(0.5 - 0.5 * (db - da) / self.k, 0, 1)
            return db * (1 - h) + da * h + self.k * h * (1 - h), ma
        return np.maximum(da, db), ma

    def bounds(self):
        la, ha = self.a.bounds()
        lb, hb = self.b.bounds()
        return np.maximum(la, lb), np.minimum(ha, hb)


class Round(Node):
    def __init__(self, child, r):
        self.child, self.r = child, r

    def eval(self, p):
        d, m = self.child.eval(p)
        return d - self.r, m

    def bounds(self):
        lo, hi = self.child.bounds()
        return lo - self.r, hi + self.r


class Shell(Node):
    def __init__(self, child, t):
        self.child, self.t = child, t

    def eval(self, p):
        d, m = self.child.eval(p)
        return np.abs(d) - self.t, m

    def bounds(self):
        lo, hi = self.child.bounds()
        return lo - self.t, hi + self.t


class Repeat(Node):
    """count copies of child, each shifted by step. Copies must not overlap much
    along step, since only the nearest two are evaluated."""

    def __init__(self, child, step, count):
        self.child, self.step, self.count = child, np.array(step, F), count

    def eval(self, p):
        s2 = self.step @ self.step
        t = (p @ self.step) / s2
        i0 = np.clip(np.floor(t), 0, self.count - 1)
        i1 = np.clip(i0 + 1, 0, self.count - 1)
        a = self.child.eval(p - i0[:, None] * self.step)
        b = self.child.eval(p - i1[:, None] * self.step)
        return nearest(a, b)

    def bounds(self):
        lo, hi = self.child.bounds()
        end = self.step * (self.count - 1)
        return np.minimum(lo, lo + end), np.maximum(hi, hi + end)


class Radial(Node):
    """count copies of child spun around an axis through the origin."""

    def __init__(self, child, count, axis="x", phase=0.0):
        self.child, self.count, self.axis, self.phase = child, count, axis, phase

    def eval(self, p):
        i = "xyz".index(self.axis)
        a_idx, b_idx = [(1, 2), (2, 0), (0, 1)][i]
        ang = np.arctan2(p[:, b_idx], p[:, a_idx]) - math.radians(self.phase)
        sector = 2 * math.pi / self.count
        k = np.round(ang / sector)
        back = -(k * sector + math.radians(self.phase))
        c, s = np.cos(back), np.sin(back)
        q = p.copy()
        q[:, a_idx] = c * p[:, a_idx] - s * p[:, b_idx]
        q[:, b_idx] = s * p[:, a_idx] + c * p[:, b_idx]
        return self.child.eval(q)

    def bounds(self):
        lo, hi = self.child.bounds()
        r = float(np.max(np.abs(np.concatenate([lo, hi]))))
        i = "xyz".index(self.axis)
        lo2, hi2 = np.full(3, -r, F), np.full(3, r, F)
        lo2[i], hi2[i] = lo[i], hi[i]
        return lo2, hi2


class Paint(Node):
    """Surface of `base`, but wherever the point lies inside `region` the material
    becomes `mat`. Geometry is untouched."""

    def __init__(self, base, region, mat):
        self.base, self.region, self.mat = base, region, mat

    def eval(self, p):
        d, m = self.base.eval(p)
        inside = self.region.dist(p) < 0
        return d, np.where(inside, np.int16(self.mat), m)

    def bounds(self):
        return self.base.bounds()


def bounds_of(nodes):
    bs = [n.bounds() for n in nodes]
    return np.min([b[0] for b in bs], 0), np.max([b[1] for b in bs], 0)


def frame_from_x(d):
    """Rotation taking +x to the unit direction d."""
    d = np.asarray(d, F) / np.linalg.norm(d)
    helper = np.array([0, 1, 0], F) if abs(d[1]) < 0.9 else np.array([1, 0, 0], F)
    y = helper - d * (helper @ d)
    y /= np.linalg.norm(y)
    z = np.cross(d, y)
    return np.stack([d, y, z], 1).astype(F)


def segment(a, b, r, mat, r_edge=0.0):
    """Flat-ended cylinder from point a to point b."""
    a, b = np.asarray(a, F), np.asarray(b, F)
    half = float(np.linalg.norm(b - a)) * 0.5
    return Xform(Cylinder(r, half, mat, axis="x", r_edge=r_edge), frame_from_x(b - a), (a + b) * 0.5)


def compose(outer, inner):
    """(R, t) of applying inner then outer."""
    Ro, to = outer
    Ri, ti = inner
    return (Ro @ Ri).astype(F), (Ro @ ti + to).astype(F)


def translate(x, y, z):
    return np.eye(3, dtype=F), np.array([x, y, z], F)


def turn(axis, deg):
    return rotation(axis, deg), np.zeros(3, F)


class Curve:
    """Cubic Bezier through control points p0 h1 h2 p3 (more points chain segments of 4,
    sharing ends: p0 h h p3 h h p6 ...). Sampled densely; lookups are by arc length."""

    def __init__(self, points, samples=96):
        self.points = np.asarray(points, F)
        n_seg = (len(self.points) - 1) // 3
        ts = np.linspace(0, n_seg, samples * n_seg + 1, dtype=F)
        self.pts = np.array([self._at(t) for t in ts], F)
        seg = np.linalg.norm(np.diff(self.pts, axis=0), axis=1)
        self.arc = np.concatenate([[0], np.cumsum(seg)]).astype(F)
        self.length = float(self.arc[-1])

    def _at(self, t):
        i = min(int(t), (len(self.points) - 1) // 3 - 1)
        u = t - i
        a, b, c, d = self.points[i * 3 : i * 3 + 4]
        return (1 - u) ** 3 * a + 3 * (1 - u) ** 2 * u * b + 3 * (1 - u) * u * u * c + u ** 3 * d

    def at_length(self, s):
        """Point and unit tangent at arc length s."""
        s = min(max(s, 0.0), self.length)
        k = int(np.clip(np.searchsorted(self.arc, s) - 1, 0, len(self.arc) - 2))
        f = (s - self.arc[k]) / max(self.arc[k + 1] - self.arc[k], 1e-9)
        p = self.pts[k] * (1 - f) + self.pts[k + 1] * f
        t = self.pts[k + 1] - self.pts[k]
        return p, t / np.linalg.norm(t)

    def frame_at(self, s, across=(1, 0, 0)):
        """(R, t) whose local y runs along the curve and local x leans toward `across`."""
        p, t = self.at_length(s)
        x = np.asarray(across, F)
        x = x - t * (x @ t)
        x /= np.linalg.norm(x)
        z = np.cross(x, t)
        return np.stack([x, t, z], 1).astype(F), p.astype(F)


class Sweep(Leaf):
    """A round tube along a curve; radius runs from r0 at the start to r1 at the end."""

    def __init__(self, curve, r0, mat, r1=None):
        self.curve, self.r0, self.mat = curve, r0, mat
        self.r1 = r0 if r1 is None else r1

    def sd(self, p):
        pts, arc = self.curve.pts, self.curve.arc
        best = np.full(len(p), 1e9, F)
        best_s = np.zeros(len(p), F)
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            ab = b - a
            t = np.clip((p - a) @ ab / (ab @ ab), 0, 1)
            d = length(p - a - t[:, None] * ab)
            closer = d < best
            best = np.where(closer, d, best)
            best_s = np.where(closer, arc[k] + t * (arc[k + 1] - arc[k]), best_s)
        f = best_s / self.curve.length
        return best - (self.r0 + (self.r1 - self.r0) * f)

    def bounds(self):
        r = max(self.r0, self.r1)
        return self.curve.pts.min(0) - r, self.curve.pts.max(0) + r
