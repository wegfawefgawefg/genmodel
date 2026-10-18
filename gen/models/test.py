"""Smoke test: a chamfered block with a bored cylinder and a bolt."""

from scene import Material, Piece, Scene
import sdf

UNIT = 0.08


def build():
    mats = [Material("teal", (90, 200, 190), 0.35, "paint", (200, 210, 205)),
            Material("steel", (70, 68, 64), 0.7, "metal")]
    block = sdf.Cut(sdf.Box(1.0, 0.6, 0.5, 0, ch=0.08), sdf.Cylinder(0.3, 1.0, 1, axis="z").at(0.4, 0, 0), cut_mat=True)
    rod = sdf.Cylinder(0.15, 1.2, 1, axis="x", r_edge=0.03).at(-1.4, 0, 0)
    pc = Piece("block", sdf.Union(block, sdf.bolt(0.12, 0.08, 1).at(-0.5, 0.2, 0.5)), h=0.03)
    pc.cut(sdf.Box(0.01, 0.4, 0.6, 0).at(-0.2, 0, 0))
    return Scene("test", mats, [pc, Piece("rod", rod, h=0.03)], texture_size=1024)
