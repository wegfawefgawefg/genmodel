"""Mechs built from separate parts that plug into each other at joints.

A Joint is defined once (kind, radius, width) and both sides are shaped from it: the
parent carries the housing at its socket, the child the knuckle at its origin. Rotating
the child about the joint centre keeps the knuckle inside the housing, so the parts stay
continuous at any angle.

A part is authored in its own frame with its plug (the joint it hangs from) at the
origin. Sockets give the frames where children attach, in the part's frame. An assembly
(sexp) says which part plugs into which socket; build() places everything and turns each
part into a rig part pivoting at its joint.
"""

import math
from dataclasses import dataclass, field

import numpy as np

import sdf
from scene import Part, Piece
from sexp import parse_sexp

F = np.float32


@dataclass
class Joint:
    name: str
    kind: str        # hinge (turns about the socket's x axis) or ball
    radius: float    # knuckle radius
    width: float = 0.0  # hinge: knuckle half width along x


@dataclass
class Socket:
    name: str
    joint: Joint
    R: np.ndarray    # socket frame in the parent's frame
    t: np.ndarray


@dataclass
class MechPart:
    name: str
    pieces: list
    sockets: dict = field(default_factory=dict)
    markers: dict = field(default_factory=dict)  # named points (exhaust tips, lamps) in the part's frame


def socket(name, joint, x, y, z, rot=None):
    """A socket at (x, y, z); rot is a list of (axis, degrees) turns applied in order."""
    R = np.eye(3, dtype=F)
    for axis, deg in rot or []:
        R = sdf.rotation(axis, deg) @ R
    return Socket(name, joint, R, np.array([x, y, z], F))


def knuckle(j, mat, inner_mat=None):
    """The child's side of a joint, at its origin."""
    if j.kind == "hinge":
        return sdf.Union(
            sdf.Cylinder(j.radius, j.width, mat, axis="x", ch=j.radius * 0.15),
            sdf.Cylinder(j.radius * 0.45, j.width + 0.03, inner_mat if inner_mat is not None else mat, axis="x"),
        )
    return sdf.Sphere(j.radius, mat)


def housing(j, mat, cap_mat=None):
    """The parent's side: cheek plates either side of a hinge knuckle with axle caps, or a
    collar ring round a ball. Built in the socket frame."""
    cap_mat = mat if cap_mat is None else cap_mat
    if j.kind == "hinge":
        gap = 0.02
        x = j.width + gap + 0.05
        out = []
        for s in (-1, 1):
            out.append(sdf.Cylinder(j.radius * 1.2, 0.05, mat, axis="x", ch=0.02).at(s * x, 0, 0))
            out.append(sdf.Cylinder(j.radius * 0.55, 0.04, cap_mat, axis="x", ch=0.015).at(s * (x + 0.07), 0, 0))
        return sdf.Union(*out)
    return sdf.Torus(j.radius * 0.95, j.radius * 0.28, mat, axis="y")


def place(piece, R, t, rename_part):
    """A copy of a piece moved into the assembly by (R, t), riding rig part `rename_part`."""
    def wrap(n):
        return sdf.Xform(n, R, t)

    p = Piece(piece.name if not rename_part else f"{rename_part}.{piece.name}", wrap(piece.body), h=piece.h,
              tris=piece.tris, part=rename_part, free=piece.free, tile=piece.tile, tile_uv=piece.tile_uv,
              mesher=piece.mesher)
    p.details = [(op, wrap(node), mat) for op, node, mat in piece.details]
    if piece.element is not None:
        p.element = piece.element
        p.placements = [sdf.compose((R, t), pl) for pl in piece.placements]
    return p


MIRROR_X = np.diag([-1.0, 1.0, 1.0]).astype(F)


def ram_pieces(name, a, b, r, cyl_mat, rod_mat, from_part, to_part):
    """A hydraulic ram between rest points a and b: a cylinder from a reaching most of the
    way, a thinner rod from b reaching back into it, eyes at both pins. Two rig parts."""
    a, b = np.asarray(a, F), np.asarray(b, F)
    d = np.linalg.norm(b - a)
    u = (b - a) / d
    cyl_end = a + u * d * 0.62
    rod_end = b - u * d * 0.66
    cylinder = sdf.Union(
        sdf.segment(a + u * r * 0.6, cyl_end, r, cyl_mat),
        sdf.segment(cyl_end - u * r * 0.4, cyl_end, r * 1.12, cyl_mat),
        sdf.segment(a - u * r * 0.2, a + u * r * 0.7, r * 0.75, cyl_mat),
    )
    rod = sdf.Union(
        sdf.segment(rod_end, b - u * r * 0.5, r * 0.5, rod_mat),
        sdf.segment(b - u * r * 0.7, b + u * r * 0.2, r * 0.7, cyl_mat),
    )
    pieces = [Piece(f"{name}.cyl", cylinder, h=0.012, tris=60, part=f"{name}.cyl"),
              Piece(f"{name}.rod", rod, h=0.01, tris=40, part=f"{name}.rod")]
    parts = [Part(f"{name}.cyl", from_part, tuple(float(x) for x in a)),
             Part(f"{name}.rod", to_part, tuple(float(x) for x in b))]
    return pieces, parts


def assemble(assembly_path, make_part, only=None, ram_mats=(0, 0)):
    """Reads an assembly sexp and places its parts. make_part(model, side) builds a
    MechPart (side is 1, or -1 for a mirrored copy). Returns (pieces, rig parts, aims). With
    only = a part name, that part alone in its own frame (for reviewing one part).
    (ram name (from part x y z) (to part x y z) (r radius)): points in each part's frame."""
    form = parse_sexp(open(assembly_path).read())[0]
    entries = [f for f in form if isinstance(f, list) and f and f[0] == "part"]
    placed = {}
    pieces, parts, markers = [], [], []
    assemble.markers = markers
    for e in entries:
        name = e[1]
        opts = {f[0]: f[1:] for f in e[2:] if isinstance(f, list)}
        model = opts.get("model", [name])[0]
        side = -1 if "mirror" in opts else 1
        mp = make_part(model, side)
        if only is not None:
            if name == only:
                return ([place(pc, np.eye(3, dtype=F), np.zeros(3, F), name) for pc in mp.pieces],
                        [Part(name, "", (0, 0, 0))], [])
            placed[name] = (np.eye(3, dtype=F), np.zeros(3, F), mp)
            continue
        if "on" in opts:
            parent, sock = opts["on"]
            PR, Pt, pmp = placed[parent]
            s = pmp.sockets[sock]
            R, t = sdf.compose((PR, Pt), (s.R, s.t))
        else:
            parent = ""
            R, t = np.eye(3, dtype=F), np.zeros(3, F)
            if "at" in opts:
                t = np.array([float(v) for v in opts["at"]], F)
        # the rest pose: (turn axis deg ...) turns the part about its own joint
        turn = opts.get("turn", [])
        for k in range(0, len(turn) - 1, 2):
            R = (R @ sdf.rotation(turn[k], float(turn[k + 1]))).astype(F)
        placed[name] = (R, t, mp)
        pieces += [place(pc, R, t, name) for pc in mp.pieces]
        parts.append(Part(name, parent, tuple(float(v) for v in t)))
        for mk, p in mp.markers.items():
            markers.append((mk, name, tuple(float(v) for v in R @ np.asarray(p, F) + t)))
    # rams last: their ends ride parts placed above
    aims = []
    for e in (f for f in form if isinstance(f, list) and f and f[0] == "ram"):
        if only is not None:
            break
        opts = {f[0]: f[1:] for f in e[2:] if isinstance(f, list)}
        ends = []
        for key in ("from", "to"):
            part, x, y, z = opts[key][0], *[float(v) for v in opts[key][1:4]]
            R, t, _ = placed[part]
            ends.append((part, R @ np.array([x, y, z], F) + t))
        r = float(opts.get("r", ["0.04"])[0])
        ps, pts = ram_pieces(e[1], ends[0][1], ends[1][1], r, ram_mats[0], ram_mats[1], ends[0][0], ends[1][0])
        pieces += ps
        parts += pts
        aims.append((pts[0].name, pts[1].name))
    return pieces, parts, aims


def mirrored(part):
    """The same part reflected across x (for left/right pairs): geometry, details and
    sockets. A reflected socket frame keeps x as the hinge axis, so joints still match."""
    out = MechPart(part.name, [], {})
    for pc in part.pieces:
        out.pieces.append(place(pc, MIRROR_X, np.zeros(3, F), ""))
        out.pieces[-1].name = pc.name
        out.pieces[-1].part = pc.part
    for k, s in part.sockets.items():
        out.sockets[k] = Socket(s.name, s.joint, MIRROR_X @ s.R @ MIRROR_X, MIRROR_X @ s.t)
    return out


def ring_band(r, h, y, mat):
    """A colour band painted round a body at height y (an infinite slab, so Paint only)."""
    return sdf.Box(4.0, h * 0.5, 4.0, mat).at(0, y, 0)


def radians(d):
    return d * math.pi / 180.0
