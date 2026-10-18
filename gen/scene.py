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


def instanced(name, element, placements, h, tris):
    """A piece made of copies of one element; the body (for baking) is their union."""
    body = sdf.Union(*[sdf.Xform(element, R, t) for R, t in placements])
    return Piece(name, body, h=h, tris=tris, element=element, placements=placements)


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

    def bake_nodes(self):
        out = []
        for pc in self.pieces:
            n = pc.bake_node()
            lo, hi = n.bounds()
            out.append((n, lo, hi))
        return out
