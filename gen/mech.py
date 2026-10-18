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
              tris=piece.tris, part=rename_part, free=piece.free, tile=piece.tile, tile_uv=piece.tile_uv)
    p.details = [(op, wrap(node), mat) for op, node, mat in piece.details]
    if piece.element is not None:
        p.element = piece.element
        p.placements = [sdf.compose((R, t), pl) for pl in piece.placements]
    return p


MIRROR_X = np.diag([-1.0, 1.0, 1.0]).astype(F)


def assemble(assembly_path, make_part, only=None):
    """Reads an assembly sexp and places its parts. make_part(model, side) builds a
    MechPart (side is 1, or -1 for a mirrored copy). Returns (pieces, rig parts). With
    only = a part name, that part alone in its own frame (for reviewing one part)."""
    form = parse_sexp(open(assembly_path).read())[0]
    entries = [f for f in form if isinstance(f, list) and f and f[0] == "part"]
    placed = {}
    pieces, parts = [], []
    for e in entries:
        name = e[1]
        opts = {f[0]: f[1:] for f in e[2:] if isinstance(f, list)}
        model = opts.get("model", [name])[0]
        side = -1 if "mirror" in opts else 1
        mp = make_part(model, side)
        if only is not None:
            if name == only:
                return [place(pc, np.eye(3, dtype=F), np.zeros(3, F), name) for pc in mp.pieces], [Part(name, "", (0, 0, 0))]
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
    return pieces, parts


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
