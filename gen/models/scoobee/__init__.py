"""Scoobee: a Phantom Crash style walker (ref/scoobee_*.png), built from separate parts.

Parts live in body.py and limbs.py, each in its own frame with its plug joint at the
origin; assembly.sexp plugs them together. Metres, y up, the mech faces +z, its right
side is +x (left parts are mirrored copies).

    python gen/build.py scoobee              the assembled mech
    python gen/build.py scoobee --part shin_r  one part alone, for review
"""

import os

from mech import Joint, assemble, mirrored
from scene import Material, Scene

UNIT = 0.05
STYLE = "lofi"
TEXTURE = 1024  # a whole mech needs more texels than a gun

TAN, OLIVE, ORANGE, DARK, CHROME, RUST, GLASS, RUBBER = range(8)

MATERIALS = [
    Material("tan", (196, 184, 150), 0.3, "paint", (150, 146, 132), rust=0.5),
    Material("olive", (112, 114, 76), 0.25, "paint", (138, 136, 112), rust=0.4),
    Material("orange", (212, 112, 44), 0.3, "paint", (180, 160, 140), rust=0.3),
    Material("dark", (62, 60, 56), 0.6, "metal", rust=0.7),
    Material("chrome", (164, 164, 160), 0.85, "metal", rust=0.3),
    Material("rust", (124, 76, 48), 0.25, "paint", (90, 80, 70), rust=0.8),
    Material("glass", (30, 38, 42), 0.95, "metal"),
    Material("rubber", (34, 33, 32), 0.1, "rubber"),
]

# every joint once: both sides of it are shaped from these
NECK = Joint("neck", "ball", 0.17)
WAIST = Joint("waist", "ball", 0.22)
HIP = Joint("hip", "ball", 0.19)
KNEE = Joint("knee", "hinge", 0.17, 0.15)
ANKLE = Joint("ankle", "hinge", 0.11, 0.1)
SHOULDER = Joint("shoulder", "ball", 0.17)
ELBOW = Joint("elbow", "hinge", 0.12, 0.1)
WRIST = Joint("wrist", "hinge", 0.085, 0.07)
GRIP = Joint("grip", "hinge", 0.05, 0.05)
BALL = Joint("ball", "hinge", 0.07, 0.1)  # the foot's toe joint

HERE = os.path.dirname(__file__)


def make_part(model, side):
    from models.scoobee import body, limbs

    builders = {
        "torso": body.torso, "head": body.head, "pelvis": body.pelvis,
        "thigh": limbs.thigh, "shin": limbs.shin, "foot": limbs.foot, "toes": limbs.toes,
        "upper_arm": limbs.upper_arm, "forearm": limbs.forearm, "claw": limbs.claw, "rifle": limbs.rifle,
    }
    part = builders[model]()
    return mirrored(part) if side < 0 else part


def build(part=None):
    pieces, parts, aims = assemble(os.path.join(HERE, "assembly.sexp"), make_part, only=part, ram_mats=(DARK, CHROME))
    return Scene("scoobee" + ("_" + part if part else ""), MATERIALS, pieces, [], texture_size=TEXTURE, scale=1.0,
                 parts=parts, rust=0.6, aims=aims)
