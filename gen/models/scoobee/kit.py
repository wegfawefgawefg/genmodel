"""Mechanical detail for the scoobee: the small stuff that tells you how big it is."""

import numpy as np

import sdf
from models.scoobee import CHROME, DARK, RUBBER, RUST
from sdf import Box, Cylinder, Union, segment


def bolts(points, r=0.022, axis="z", mat=DARK):
    """Hex bolt heads at each point, standing out along +axis."""
    return Union(*[sdf.bolt(r, r * 0.7, mat, axis=axis).at(*p) for p in points])


def bolt_ring(center, radius, n, axis="y", r=0.02, mat=DARK):
    """A ring of bolt heads round an axis (heads facing outward along the ring's axis)."""
    cx, cy, cz = center
    pts = []
    for k in range(n):
        a = 2 * np.pi * k / n
        if axis == "y":
            pts.append((cx + radius * np.cos(a), cy, cz + radius * np.sin(a)))
        elif axis == "z":
            pts.append((cx + radius * np.cos(a), cy + radius * np.sin(a), cz))
        else:
            pts.append((cx, cy + radius * np.cos(a), cz + radius * np.sin(a)))
    return bolts(pts, r, axis, mat)


def piston(a, b, r=0.045, split=0.55):
    """A hydraulic ram from a to b: dark cylinder body, chrome rod, eye ends."""
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    m = a + (b - a) * split
    return Union(
        segment(a, m, r, DARK),
        segment(m - (b - a) * 0.05, b, r * 0.5, CHROME),
        sdf.Sphere(r * 1.1, DARK).at(*a),
        sdf.Sphere(r * 0.8, DARK).at(*b),
    )


def drum_stack(center, radius, n, pitch, axis="x", mats=(DARK, RUST)):
    """Ribbed actuator drums side by side along an axis, alternating sizes and colours."""
    cx, cy, cz = center
    out = []
    for k in range(n):
        off = (k - (n - 1) / 2) * pitch
        p = [cx, cy, cz]
        p["xyz".index(axis)] += off
        r = radius * (1.0 if k % 2 == 0 else 0.84)
        out.append(Cylinder(r, pitch * 0.38, mats[k % 2] if k % 3 == 1 else mats[0], axis=axis, ch=0.015).at(*p))
    return Union(*out)


def hose(a, b, sag, r=0.03, down=(0, -1, 0)):
    """A rubber hose slung from a to b."""
    return sdf.Sweep(sdf.Curve(sdf.hang(a, b, sag, down)), r, RUBBER)


def handle(a, b, lift, r=0.018, mat=CHROME):
    """A grab handle: a bar standing off the surface by `lift` along +normal (given in b - a's
    perpendicular plane by the caller via the points)."""
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    up = np.asarray(lift, np.float32)
    return Union(segment(a, a + up, r, mat), segment(a + up, b + up, r, mat), segment(b, b + up, r, mat))


def grille(center, w, h, n, axis="z", mat=DARK):
    """Vent slats: n bars across a w x h opening, facing along axis."""
    cx, cy, cz = center
    slats = []
    for k in range(n):
        y = cy - h / 2 + h * (k + 0.5) / n
        if axis == "z":
            slats.append(Box(w / 2, h / (2.6 * n), 0.02, mat, ch=0.005).at(cx, y, cz))
        else:
            slats.append(Box(0.02, h / (2.6 * n), w / 2, mat, ch=0.005).at(cx, y, cz))
    return Union(*slats)


def teardrop_profile(r, length, n=7):
    """Lathe profile of a teardrop: a round nose (top, +y) tapering to a fine tail at -length."""
    nose = [(r * np.sin(a), r * np.cos(a)) for a in np.radians(np.linspace(12, 90, n))]
    tail = [(r * 0.86, -length * 0.3), (r * 0.6, -length * 0.62), (r * 0.3, -length * 0.88), (r * 0.08, -length)]
    return [(max(x, 0.01), y) for x, y in nose] + tail


def teardrop(r, length, mat):
    """A teardrop with its round nose facing +z and its tail running back along -z."""
    return sdf.Lathe(teardrop_profile(r, length), mat).rot("x", 90)


def cup_flap(r, length, mat, thick=0.025):
    """A half teardrop shell, the outer (+x) half of one, hinged at its nose (the origin) and
    running back along -z; its open side faces the body. Opens by swinging its tail out."""
    shell = sdf.Shell(teardrop(r, length, mat).at(0, 0, -r), thick)
    return sdf.Intersect(shell, Box(r * 1.2, r * 1.2, length * 0.7, mat).at(r * 1.2, 0, -length * 0.55 - r * 0.2))


def pipe(points, r, mat=DARK):
    """A round pipe bent along a bezier (p0 h1 h2 p3)."""
    c = sdf.Curve(points)
    return sdf.Bend(Cylinder(r, c.length * 0.5, mat, axis="x").at(c.length * 0.5, 0, 0), c, across=(1, 0, 0))


def antenna(base, tip, r=0.008, mat=CHROME):
    """A long thin whip swept back from a base boss."""
    base, tip = np.asarray(base, np.float32), np.asarray(tip, np.float32)
    return Union(Cylinder(r * 4, 0.025, DARK, axis="y", ch=0.008).at(*base), segment(base, tip, r, mat),
                 segment(base, base + (tip - base) * 0.15, r * 2, DARK))
