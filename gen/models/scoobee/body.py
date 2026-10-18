"""Scoobee core parts: torso (the root), head pod, pelvis."""

import sdf
from mech import MechPart, housing, knuckle, socket
from models.scoobee import (CHROME, DARK, GLASS, HIP, NECK, OLIVE, RUST, SHOULDER, TAN, WAIST)
from scene import Piece
from sdf import Box, Cylinder, Lathe, Torus, Union


def headlight(x, y, z):
    """One of the big round sensor pods on the shoulders: a tan can facing forward, a chrome
    rim, a dark grille lens with a bright centre."""
    return Union(
        Cylinder(0.27, 0.24, TAN, axis="z", ch=0.06).at(x, y, z),
        Torus(0.22, 0.035, CHROME, axis="z").at(x, y, z + 0.24),
        Cylinder(0.21, 0.03, GLASS, axis="z").at(x, y, z + 0.22),
        Cylinder(0.075, 0.03, CHROME, axis="z").at(x, y, z + 0.25),
    )


def torso():
    """A compact egg of a core with the big headlight cans on its shoulders, a rust jaw pad
    under the front and a pack on the back. Sockets: neck on top, shoulders under the
    cans, waist underneath."""
    egg = [(0.26, 0.6), (0.42, 0.48), (0.52, 0.24), (0.55, 0.0), (0.52, -0.26), (0.42, -0.48), (0.24, -0.6)]
    core = Lathe(egg, TAN).rot("x", 90)
    yoke = Box(0.6, 0.16, 0.28, TAN, ch=0.1).at(0, 0.22, 0.1)
    chest = Box(0.2, 0.18, 0.08, TAN, ch=0.04).at(0, -0.02, 0.52)
    jaw = Box(0.3, 0.12, 0.2, RUST, ch=0.06).rot("x", 20).at(0, -0.42, 0.34)
    pack = Box(0.36, 0.26, 0.16, OLIVE, ch=0.08).at(0, 0.06, -0.62)
    vents = Box(0.26, 0.04, 0.12, DARK, ch=0.02).at(0, 0.34, -0.28)
    body = Union(core, yoke, chest, jaw, pack, vents, headlight(0.66, 0.24, 0.12), headlight(-0.66, 0.24, 0.12))
    # sockets' housings belong to the torso
    neck_at = (0.0, 0.46, 0.26)
    sh_x = 0.7
    sh_y = -0.1
    joints = Union(
        housing(NECK, DARK).at(*neck_at),
        housing(SHOULDER, DARK).rot("z", 90).at(sh_x, sh_y, -0.02),
        housing(SHOULDER, DARK).rot("z", 90).at(-sh_x, sh_y, -0.02),
        housing(WAIST, DARK).at(0, -0.5, 0),
        # shoulder actuators: ribbed drums round the joints
        *[Cylinder(0.17, 0.025, DARK, axis="x", ch=0.01).at(s * (sh_x - 0.12 - 0.06 * i), sh_y, -0.02)
          for s in (1, -1) for i in range(3)],
    )
    pieces = [Piece("shell", body, h=0.04, tris=900), Piece("joints", joints, h=0.03, tris=400)]
    pieces[0].cut(Box(0.6, 0.012, 0.6, TAN).at(0, 0.1, 0))  # panel seam
    sockets = {
        "neck": socket("neck", NECK, *neck_at),
        "shoulder_r": socket("shoulder_r", SHOULDER, sh_x, sh_y, -0.02),
        "shoulder_l": socket("shoulder_l", SHOULDER, -sh_x, sh_y, -0.02),
        "waist": socket("waist", WAIST, 0, -0.5, 0),
    }
    return MechPart("torso", pieces, sockets)


def head():
    """The head pod riding on the neck: a big bean of a hood (a lathe along z), olive on top,
    overhanging a binocular sensor face."""
    # a wide capsule lying side to side (a lathe turned from y onto x), sitting forward
    capsule = [(0.16, 0.56), (0.3, 0.5), (0.37, 0.36), (0.39, 0.0), (0.37, -0.36), (0.3, -0.5), (0.16, -0.56)]
    hood = Lathe(capsule, TAN).rot("z", 90).at(0, 0.42, 0.12)
    hood = sdf.Paint(hood, Box(2.0, 0.16, 2.0, OLIVE).at(0, 0.8, 0), OLIVE)
    # the sensor face tucked under the hood's front
    face = Box(0.3, 0.13, 0.12, DARK, ch=0.03).at(0, 0.22, 0.42)
    lenses = Union(
        Cylinder(0.09, 0.07, CHROME, axis="z", ch=0.02).at(0.13, 0.24, 0.52),
        Cylinder(0.09, 0.07, CHROME, axis="z", ch=0.02).at(-0.13, 0.24, 0.52),
        Cylinder(0.065, 0.02, GLASS, axis="z").at(0.13, 0.24, 0.59),
        Cylinder(0.065, 0.02, GLASS, axis="z").at(-0.13, 0.24, 0.59),
    )
    grille = Box(0.16, 0.03, 0.05, CHROME, ch=0.01).at(0, 0.1, 0.44)
    stalk = Cylinder(0.11, 0.12, DARK, axis="y", ch=0.02).at(0, 0.1, 0)
    pieces = [
        Piece("hood", hood, h=0.03, tris=300),
        Piece("face", Union(face, lenses, grille, stalk, knuckle(NECK, DARK)), h=0.02, tris=400),
    ]
    return MechPart("head", pieces, {})


def pelvis():
    """Hangs from the waist: a block with ribbed hip actuators and a rusty armour plate in
    front. Sockets: the hips."""
    block = Box(0.34, 0.16, 0.28, TAN, ch=0.08).at(0, -0.24, 0)
    plate = Box(0.26, 0.15, 0.06, RUST, ch=0.04).rot("x", -15).at(0, -0.36, 0.3)
    hip_x = 0.58
    drums = Union(*[Cylinder(0.14 - 0.015 * (i % 2), 0.025, DARK, axis="x", ch=0.01).at(s * (0.37 + 0.06 * i), -0.26, 0)
                    for s in (1, -1) for i in range(3)])
    joints = Union(
        knuckle(WAIST, DARK),
        housing(HIP, DARK).rot("z", 90).at(hip_x, -0.26, 0),
        housing(HIP, DARK).rot("z", 90).at(-hip_x, -0.26, 0),
    )
    pieces = [Piece("block", Union(block, plate), h=0.03, tris=200), Piece("joints", Union(joints, drums), h=0.03, tris=500)]
    sockets = {
        "hip_r": socket("hip_r", HIP, hip_x, -0.26, 0),
        "hip_l": socket("hip_l", HIP, -hip_x, -0.26, 0),
    }
    return MechPart("pelvis", pieces, sockets)
