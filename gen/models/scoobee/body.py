"""Scoobee core parts: torso (the root: a machinery spine under a long cabin capsule),
head (a binocular sensor pod forward on a neck), pelvis (hip gear)."""

import sdf
from mech import MechPart, housing, knuckle, socket
from models.scoobee import CHROME, DARK, GLASS, HIP, NECK, OLIVE, ORANGE, RUST, SHOULDER, TAN, WAIST
from models.scoobee.kit import bolt_ring, bolts, drum_stack, grille, handle, hose, piston
from scene import Piece
from sdf import Box, Cylinder, Loft, Torus, Union, segment

NECK_AT = (0.0, -0.02, 0.86)
SH_X, SH_Y, SH_Z = 0.72, -0.12, 0.3
WAIST_AT = (0.0, -0.46, -0.1)


def headlight(x, y, z):
    """A big round sensor can on the chassis flank: tan body, chrome rim, grille lens."""
    return Union(
        Cylinder(0.24, 0.2, TAN, axis="z", ch=0.05).at(x, y, z),
        Torus(0.2, 0.032, CHROME, axis="z").at(x, y, z + 0.2),
        Cylinder(0.19, 0.025, GLASS, axis="z").at(x, y, z + 0.18),
        grille((x, y, z + 0.2), 0.3, 0.28, 5),
        Cylinder(0.06, 0.03, CHROME, axis="z").at(x, y, z + 0.22),
    )


def cabin():
    """The long armoured capsule riding on top, nose up front. Olive cap, seams, a hatch,
    a handrail and a pair of exhaust stubs at the back."""
    # a long low wedge, wider than tall, raked down to the nose: stations run tail to nose
    # along the loft's y, which the turn maps onto -z (and its depth onto up)
    stations = [(1.45, 0.3, 0.16, 0.06), (1.1, 0.52, 0.3, 0.03), (0.4, 0.64, 0.37, 0.0), (-0.3, 0.64, 0.36, -0.01),
                (-0.8, 0.54, 0.27, -0.07), (-1.12, 0.32, 0.13, -0.12)]
    shell = Loft(stations, TAN).rot("x", -90).at(0, 0.42, -0.2)
    shell = sdf.Paint(shell, Box(3.0, 0.2, 3.0, OLIVE).at(0, 0.92, 0), OLIVE)
    shell = sdf.Paint(shell, Box(0.12, 0.045, 3.0, ORANGE).at(0.62, 0.48, -0.2), ORANGE)
    shell = sdf.Paint(shell, Box(0.12, 0.045, 3.0, ORANGE).at(-0.62, 0.48, -0.2), ORANGE)
    rail = handle((0.24, 0.79, 0.1), (0.24, 0.77, -0.9), (0, 0.06, 0))
    rail2 = handle((-0.24, 0.79, 0.1), (-0.24, 0.77, -0.9), (0, 0.06, 0))
    exhaust = Union(
        Cylinder(0.055, 0.1, DARK, axis="z", ch=0.01).at(0.2, 0.48, -1.68),
        Cylinder(0.055, 0.1, DARK, axis="z", ch=0.01).at(-0.2, 0.48, -1.68),
    )
    lip = Box(0.42, 0.03, 0.06, DARK, ch=0.012).at(0, 0.24, 0.86)
    return Union(shell, rail, rail2, exhaust, lip)


def spine():
    """The exposed machinery under the cabin: a frame, rusty tanks, drum stacks, rams, hoses."""
    frame = Union(
        Box(0.34, 0.2, 0.75, DARK, ch=0.05).at(0, -0.12, 0.05),
        Box(0.5, 0.06, 0.6, DARK, ch=0.02).at(0, 0.06, 0.0),
        Box(0.2, 0.18, 0.2, DARK, ch=0.04).at(0, -0.06, 0.72),
    )
    tanks = Union(
        Cylinder(0.11, 0.38, RUST, axis="z", ch=0.03).at(0.38, -0.12, -0.25),
        Cylinder(0.11, 0.38, RUST, axis="z", ch=0.03).at(-0.38, -0.12, -0.25),
        Torus(0.11, 0.02, DARK, axis="z").at(0.38, -0.12, -0.05),
        Torus(0.11, 0.02, DARK, axis="z").at(-0.38, -0.12, -0.05),
    )
    drums = Union(drum_stack((0, -0.3, -0.2), 0.16, 5, 0.1), drum_stack((0, -0.24, 0.38), 0.12, 4, 0.09))
    rams = Union(
        piston((0.2, 0.0, 0.62), (0.32, 0.3, 0.12), 0.035),
        piston((-0.2, 0.0, 0.62), (-0.32, 0.3, 0.12), 0.035),
    )
    lines = Union(
        hose((0.3, 0.32, -0.6), (0.4, -0.02, -0.1), 0.12, 0.025, (0.5, -0.8, 0)),
        hose((-0.3, 0.32, -0.6), (-0.4, -0.02, -0.1), 0.12, 0.025, (-0.5, -0.8, 0)),
        hose((0.12, -0.04, 0.6), (0.5, -0.1, 0.3), 0.08, 0.02),
    )
    return Union(frame, tanks, drums, rams, lines)


def torso():
    joints = Union(
        housing(NECK, DARK).rot("x", 90).at(*NECK_AT),
        housing(SHOULDER, DARK).rot("z", 90).at(SH_X, SH_Y, SH_Z),
        housing(SHOULDER, DARK).rot("z", 90).at(-SH_X, SH_Y, SH_Z),
        housing(WAIST, DARK).at(*WAIST_AT),
        drum_stack((SH_X - 0.2, SH_Y, SH_Z), 0.18, 3, 0.07),
        drum_stack((-SH_X + 0.2, SH_Y, SH_Z), 0.18, 3, 0.07),
        segment((0.3, SH_Y, SH_Z), (-0.3, SH_Y, SH_Z), 0.06, DARK),
    )
    lights = Union(headlight(0.5, 0.12, 0.62), headlight(-0.5, 0.12, 0.62))
    bolt_rows = Union(
        bolts([(x, 0.37, 0.7) for x in (-0.42, -0.21, 0.0, 0.21, 0.42)], 0.02),
        bolts([(x, 0.78, -0.2) for x in (-0.4, 0.4)] + [(x, 0.78, -0.6) for x in (-0.4, 0.4)], 0.018, axis="y"),
    )
    shell = Piece("cabin", Union(cabin(), bolt_rows), h=0.04, tris=1200)
    # panel seams and a top hatch: texture only
    shell.cut(Box(1.0, 1.0, 0.007, TAN).at(0, 0.42, -0.5))
    shell.cut(Box(1.0, 1.0, 0.007, TAN).at(0, 0.42, 0.45))
    shell.cut(Box(0.22, 0.3, 0.007, TAN).at(0, 0.8, -0.3))
    shell.cut(Box(0.22, 0.3, 0.007, TAN).at(0, 0.8, -0.85))
    shell.cut(Box(0.007, 0.3, 0.28, TAN).at(0.22, 0.8, -0.575))
    shell.cut(Box(0.007, 0.3, 0.28, TAN).at(-0.22, 0.8, -0.575))
    pieces = [shell, Piece("spine", spine(), h=0.03, tris=1400), Piece("lights", lights, h=0.03, tris=600),
              Piece("joints", joints, h=0.03, tris=700)]
    sockets = {
        "neck": socket("neck", NECK, *NECK_AT),
        "shoulder_r": socket("shoulder_r", SHOULDER, SH_X, SH_Y, SH_Z),
        "shoulder_l": socket("shoulder_l", SHOULDER, -SH_X, SH_Y, SH_Z),
        "waist": socket("waist", WAIST, *WAIST_AT),
    }
    return MechPart("torso", pieces, sockets)


def head():
    """The sensor pod on a short neck reaching forward: a rounded box with an olive brow,
    two big lens barrels, cheek rams and a whip antenna."""
    neck = Union(segment((0, 0, 0), (0, -0.05, 0.22), 0.07, DARK), knuckle(NECK, DARK))
    pod = Box(0.3, 0.2, 0.28, TAN, ch=0.1).at(0, -0.02, 0.44)
    brow = Box(0.33, 0.06, 0.26, OLIVE, ch=0.05).at(0, 0.17, 0.44)
    lenses = Union(*[Union(
        Cylinder(0.09, 0.1, DARK, axis="z", ch=0.015).at(x, -0.03, 0.76),
        Cylinder(0.085, 0.03, CHROME, axis="z", ch=0.01).at(x, -0.03, 0.85),
        Cylinder(0.06, 0.02, GLASS, axis="z").at(x, -0.03, 0.875),
    ) for x in (0.13, -0.13)])
    cheeks = Union(piston((0.2, -0.08, 0.25), (0.16, -0.1, 0.55), 0.025),
                   piston((-0.2, -0.08, 0.25), (-0.16, -0.1, 0.55), 0.025))
    jaw = Box(0.14, 0.04, 0.12, RUST, ch=0.02).at(0, -0.18, 0.48)
    antenna = Union(Cylinder(0.02, 0.04, DARK, axis="y").at(0.18, 0.2, 0.3), segment((0.18, 0.2, 0.3), (0.2, 0.62, 0.22), 0.006, CHROME))
    pieces = [Piece("pod", Union(pod, brow, jaw), h=0.025, tris=300),
              Piece("sensors", Union(neck, lenses, cheeks, antenna, bolts([(0.12, 0.14, 0.58), (-0.12, 0.14, 0.58)], 0.016)),
                    h=0.015, tris=700)]
    pieces[0].cut(Box(0.25, 0.006, 0.23, TAN).at(0, 0.05, 0.4))
    return MechPart("head", pieces, {})


def pelvis():
    """Hip gear hanging from the waist: a block, big drum stacks over each hip, an armour skirt."""
    hip_x = 0.56
    block = Box(0.3, 0.16, 0.26, DARK, ch=0.06).at(0, -0.22, 0)
    skirt = Box(0.24, 0.13, 0.05, TAN, ch=0.04).rot("x", -12).at(0, -0.3, 0.3)
    skirt = sdf.Paint(skirt, Box(1.0, 0.03, 1.0, ORANGE).at(0, -0.34, 0), ORANGE)
    drums = Union(drum_stack((hip_x - 0.2, -0.26, 0), 0.19, 4, 0.08), drum_stack((-hip_x + 0.2, -0.26, 0), 0.19, 4, 0.08))
    joints = Union(
        knuckle(WAIST, DARK),
        housing(HIP, DARK).rot("z", 90).at(hip_x, -0.26, 0),
        housing(HIP, DARK).rot("z", 90).at(-hip_x, -0.26, 0),
        segment((0.3, -0.26, 0), (-0.3, -0.26, 0), 0.07, CHROME),
        bolt_ring((0, -0.06, 0), 0.2, 8, axis="y", r=0.018),
    )
    pieces = [Piece("block", Union(block, skirt), h=0.03, tris=200), Piece("joints", Union(joints, drums), h=0.03, tris=700)]
    sockets = {
        "hip_r": socket("hip_r", HIP, hip_x, -0.26, 0),
        "hip_l": socket("hip_l", HIP, -hip_x, -0.26, 0),
    }
    return MechPart("pelvis", pieces, sockets)
