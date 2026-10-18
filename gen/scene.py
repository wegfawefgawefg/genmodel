"""A model is a list of pieces (each meshed on its own), materials and decals."""

from dataclasses import dataclass, field

import numpy as np

import sdf

F = np.float32


@dataclass
class Material:
    name: str
    color: tuple          # srgb 0-255
    spec: float = 0.3     # 0 matte .. 1 polished, goes to the texture's alpha
    kind: str = "paint"   # paint, metal, rubber, glow
    wear: tuple = (150, 150, 150)  # colour that shows through on worn edges


@dataclass
class Piece:
    name: str
    body: sdf.Node        # meshed geometry
    h: float = 0.04       # voxel size for meshing
    tris: int = 1000      # triangle budget (per instance for instanced pieces)
    details: list = field(default_factory=list)  # (op, node, mat) baked into the texture only
    element: object = None  # instanced pieces: one element meshed once...
    placements: list = field(default_factory=list)  # ...and copied to each (R, t)
    part: str = "root"    # rig part that carries it; instanced pieces may give one per copy
    part_each: bool = False  # instanced: copy i belongs to part "<part>.<i>"
    free: bool = False    # moves far from rest (casings, flashes): no culling, casts no AO

    def cut(self, node, mat=None):
        self.details.append(("cut", node, mat))
        return self

    def add(self, node):
        self.details.append(("add", node, None))
        return self

    def paint(self, region, mat):
        self.details.append(("paint", region, mat))
        return self

    def bake_node(self):
        """The body with the texture-only details applied."""
        n = self.body
        for op, d, mat in self.details:
            if op == "cut":
                n = sdf.Cut(n, d, cut_mat=mat is not None)
            elif op == "add":
                n = sdf.Union(n, d)
            else:
                n = sdf.Paint(n, d, mat)
        return n


def instanced(name, element, placements, h, tris, part="root", part_each=False, free=False):
    """A piece made of copies of one element; the body (for baking) is their union."""
    body = sdf.Union(*[sdf.Xform(element, R, t) for R, t in placements])
    return Piece(name, body, h=h, tris=tris, element=element, placements=placements, part=part,
                 part_each=part_each, free=free)


@dataclass
class Part:
    """A rigid chunk the animation moves: rotates about pivot, inherits its parent."""

    name: str
    parent: str = ""
    pivot: tuple = (0.0, 0.0, 0.0)
    additive: bool = False  # drawn glowing and blended (muzzle flashes)


@dataclass
class Path:
    """A bezier the animation can bend (its handles are parts) with links riding on it."""

    name: str
    parent: str
    points: list          # p0 h1 h2 p3
    links: list           # part names riding the path, in order from its start
    pitch: float          # arc length between links
    start: float = 0.0    # arc length of the first link
    anchor: str = ""      # part carrying the start point
    across: tuple = (1.0, 0.0, 0.0)


@dataclass
class Decal:
    """An rgba image projected along -normal onto a rectangle of the surface."""

    image: object         # PIL rgba image
    origin: tuple         # centre of the rectangle
    u_axis: tuple         # image right, unit
    v_axis: tuple         # image up, unit
    size: tuple           # (width, height) in model units
    depth: float = 0.3    # how far in front/behind the rectangle it still applies
    mode: str = "over"    # over: blend colour, dirt: darken only


@dataclass
class Scene:
    name: str
    materials: list
    pieces: list
    decals: list = field(default_factory=list)
    parts: list = field(default_factory=list)
    paths: list = field(default_factory=list)
    texture_size: int = 2048
    scale: float = 1.0    # applied at export

    def union_eval(self, p, nodes, pad=0.05):
        """Union of pieces, skipping pieces whose bounds are far from the points."""
        d = np.full(len(p), 1e9, F)
        m = np.zeros(len(p), np.int16)
        for node, lo, hi in nodes:
            inside = np.all((p >= lo - pad) & (p <= hi + pad), axis=1)
            idx = np.nonzero(inside)[0]
            if len(idx) == 0:
                continue
            dd, mm = node.eval(p[idx])
            closer = dd < d[idx]
            d[idx] = np.where(closer, dd, d[idx])
            m[idx] = np.where(closer, mm, m[idx])
        # far points: a lower bound is fine for ao and culling
        return d, m

    def bake_nodes(self, include_free=True):
        out = []
        for pc in self.pieces:
            if pc.free and not include_free:
                continue
            n = pc.bake_node()
            lo, hi = n.bounds()
            out.append((n, lo, hi))
        return out


def instance_parts(piece, parent):
    """One part per copy of a part_each piece, pivoting where the copy sits."""
    return [Part(f"{piece.part}.{i}", parent, tuple(float(x) for x in t)) for i, (_, t) in enumerate(piece.placements)]
