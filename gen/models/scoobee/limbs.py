"""Scoobee limbs, authored for the right side (+x); left ones are mirrored copies.
Long and lean: legs hang down -y from their plug; the elbow socket turns the forearm
forward. Rest angles come from the assembly's turns, so joints read at natural angles."""

import sdf
from mech import MechPart, housing, knuckle, socket
from models.scoobee import (ANKLE, BALL, CHROME, DARK, ELBOW, FLAP, GLASS, GRIP, HIP, KNEE, OLIVE, ORANGE, RUBBER, RUST,
                            SHOULDER, SPUR, TAN, WRIST)
from models.scoobee.kit import bolt_ring, bolts, hose, piston
from scene import Piece
from sdf import Box, Cylinder, Loft, Prism, Union, segment

THIGH_LEN = 0.95
SHIN_LEN = 2.05


def thigh():
    """A long sleek blade of a thigh: a tapered armour plate over a strut and a big ram."""
    k = (0.0, -THIGH_LEN, 0.0)
    plate = Box(0.11, THIGH_LEN * 0.42, 0.17, TAN, ch=0.07).rot("x", -4).at(0.06, -THIGH_LEN * 0.45, 0.08)
    plate = sdf.Paint(plate, Box(1.0, 0.05, 1.0, ORANGE).at(0, -THIGH_LEN * 0.62, 0), ORANGE)
    strut = Union(
        segment((0, -0.1, -0.04), (0, -THIGH_LEN + 0.12, -0.04), 0.07, DARK),
        Box(0.09, 0.08, 0.1, DARK, ch=0.03).at(0, -THIGH_LEN + 0.14, -0.02),
    )
    # the knee ram's top pin on the outer side (the ram is an assembly part, so it slides)
    lug = Union(Box(0.1, 0.06, 0.05, DARK, ch=0.02).at(0.16, -0.24, 0.12), Box(0.03, 0.07, 0.07, DARK, ch=0.015).at(0.27, -0.24, 0.16))
    body = Union(knuckle(HIP, DARK), strut, lug, housing(KNEE, DARK, CHROME).at(*k),
                 bolts([(0.18, -0.25, 0.12), (0.18, -0.6, 0.14)], 0.016, axis="x"))
    pieces = [Piece("plate", plate, h=0.025, tris=120), Piece("frame", body, h=0.02, tris=500)]
    pieces[0].cut(Box(0.12, 0.006, 0.18, TAN).at(0.06, -0.3, 0.08))
    return MechPart("thigh", pieces, {"knee": socket("knee", KNEE, *k)})


def shin():
    """The tall tapered shin pod: slim under the knee, swelling low, a rust hem at its foot,
    an orange band, a knee horn in front and a gusset behind carrying the calf ram's pin."""
    # panelled and tapered, deeper front to back than wide, swept slightly forward low down;
    # it starts below the knee knuckle so it never sweeps through the thigh as the knee bends
    stations = [(-0.14, 0.12, 0.13, 0.0), (-0.26, 0.15, 0.18, 0.0), (-0.6, 0.21, 0.27, 0.03), (-1.3, 0.28, 0.35, 0.07),
                (-1.68, 0.28, 0.33, 0.06), (-1.94, 0.19, 0.22, 0.03)]
    shell = Loft(stations, TAN).at(0, 0, 0.02)
    shell = sdf.Paint(shell, Box(2.0, 0.09, 2.0, ORANGE).at(0, -1.12, 0), ORANGE)
    shell = sdf.Paint(shell, Box(2.0, 0.07, 2.0, RUST).at(0, -1.9, 0), RUST)
    ankle_at = (0.0, -SHIN_LEN, 0.0)
    spine = Union(
        # the knee horn: a lever ahead of the knee axis for the extensor ram to drive
        segment((0.1, -0.16, 0.08), (0.27, -0.2, 0.27), 0.05, DARK),
        Box(0.03, 0.06, 0.06, DARK, ch=0.02).at(0.29, -0.2, 0.27),
        # a triangular gusset off the upper back of the shin out to the calf ram's pin
        Prism([(-0.36, -0.12), (-0.98, -0.2), (-0.6, -0.5)], 0.035, DARK, r=0.01, plane="yz"),
        Cylinder(0.045, 0.06, DARK, axis="x", ch=0.01).at(0, -0.6, -0.47),
        bolts([(0.04, -0.5, -0.22), (0.04, -0.75, -0.24)], 0.014, axis="x"),
    )
    joints = Union(knuckle(KNEE, DARK, CHROME), housing(ANKLE, DARK).at(*ankle_at),
                   segment((0, -1.9, 0), ankle_at, 0.08, DARK))
    pieces = [Piece("shell", shell, h=0.03, tris=340), Piece("gear", Union(spine, joints), h=0.02, tris=600)]
    pieces[0].cut(Box(1.0, 0.007, 1.0, TAN).at(0, -1.45, 0))
    pieces[0].cut(Box(0.007, 0.7, 1.0, TAN).at(0, -0.85, 0.3))
    return MechPart("shin", pieces, {"ankle": socket("ankle", ANKLE, *ankle_at),
                                     "flap": socket("flap", FLAP, 0.24, -0.78, 0.18)})


def shin_flap():
    """A smaller cup flap over the shin's intake, opening with speed like the body's."""
    from models.scoobee.kit import cup_flap
    cup = cup_flap(0.13, 0.55, TAN, 0.02)
    hinge = Cylinder(0.022, 0.08, DARK, axis="y", ch=0.008)
    return MechPart("shin_flap", [Piece("cup", cup, h=0.014, tris=160, mesher="contour"), Piece("hinge", hinge, h=0.015, tris=24)], {})


FOOT_SCALE = 1.5
BALL_AT = (0.0, -0.24 * FOOT_SCALE, 0.32 * FOOT_SCALE)
SPUR_AT = (0.0, -0.3, -0.13)


def foot():
    """Ankle block, a sloped instep and a heel spur; the toes are their own part on the ball
    joint, so the heel can roll up off planted toes."""
    k = FOOT_SCALE
    block = Box(0.11, 0.08, 0.13, DARK, ch=0.03).at(0, -0.1, 0)
    instep = Box(0.13, 0.06, 0.2, TAN, ch=0.05).rot("x", 16).at(0, -0.17, 0.16)
    instep = sdf.Paint(instep, Box(1.0, 1.0, 0.04, ORANGE).at(0, 0, 0.24), ORANGE)
    # a solid triangular heel plate from the ankle block back to the calf ram's pin
    lug = Union(Prism([(-0.02, -0.05), (-0.2, -0.1), (-0.12, -0.22)], 0.025, DARK, r=0.006, plane="yz"),
                Cylinder(0.025, 0.035, DARK, axis="x", ch=0.006).at(0, -0.12, -0.22))
    # authored small, then scaled up round the ankle (the knuckle stays the joint's size)
    big = sdf.Scale(Union(block, instep, lug), k)
    body = Union(knuckle(ANKLE, DARK), big, housing(BALL, DARK).at(*BALL_AT), housing(SPUR, DARK).at(*SPUR_AT))
    return MechPart("foot", [Piece("foot", body, h=0.015, tris=400)],
                    {"ball": socket("ball", BALL, *BALL_AT), "spur": socket("spur", SPUR, *SPUR_AT)})


def spur():
    """The back toe: a sprung blade behind the heel that folds up under load (the gait works it)."""
    blade = Union(segment((0, 0, 0), (0, -0.1, -0.3), 0.04, DARK), knuckle(SPUR, DARK),
                  Box(0.05, 0.03, 0.07, RUST, ch=0.015).rot("x", -15).at(0, -0.11, -0.33),
                  Box(0.055, 0.012, 0.06, RUBBER, ch=0.005).at(0, -0.14, -0.33))
    return MechPart("spur", [Piece("spur", blade, h=0.012, tris=120)], {})


def toes():
    """Two long splayed front toes with rust tips and rubber pads, hinged at the ball."""
    k = FOOT_SCALE
    toes_, pads = [], []
    for ang, length in ((-14, 0.3), (14, 0.3)):
        toe = Union(Box(0.06, 0.04, length * 0.5, DARK, ch=0.022).at(0, 0, length * 0.5),
                    Box(0.04, 0.03, 0.05, RUST, ch=0.015).rot("x", 18).at(0, -0.01, length + 0.02))
        toes_.append(toe.rot("y", ang).at(0, 0, 0.02))
        pads.append(Box(0.065, 0.015, length * 0.4, RUBBER, ch=0.006).at(0, -0.045, length * 0.55).rot("y", ang).at(0, 0, 0.02))
    body = Union(knuckle(BALL, DARK), sdf.Scale(Union(*toes_, *pads), k))
    return MechPart("toes", [Piece("toes", body, h=0.012, tris=260)], {})


def upper_arm():
    """From the shoulder ball down to the elbow: an olive actuator can and two long rams."""
    elbow_at = (0.0, -0.78, 0.0)
    can = Cylinder(0.12, 0.13, OLIVE, axis="y", ch=0.04).at(0, -0.2, 0)
    struts = Union(
        Box(0.04, 0.05, 0.05, DARK, ch=0.015).at(0, -0.22, 0.14),   # bicep ram pin
        segment((0, -0.3, -0.07), (0, -0.7, -0.07), 0.05, DARK),
        bolt_ring((0, -0.07, 0), 0.12, 6, axis="y", r=0.015),
    )
    body = Union(knuckle(SHOULDER, DARK), can, struts, housing(ELBOW, DARK, CHROME).at(*elbow_at))
    return MechPart("upper_arm", [Piece("upper_arm", body, h=0.02, tris=400)],
                    {"elbow": socket("elbow", ELBOW, *elbow_at, rot=[("x", -90)])})


def forearm():
    """A long tapered gauntlet with an orange band, wrist fork at its end."""
    wrist_at = (0.0, -0.95, 0.0)
    stations = [(-0.06, 0.09, 0.1, 0.0), (-0.2, 0.14, 0.15, 0.0), (-0.55, 0.17, 0.19, 0.02), (-0.78, 0.15, 0.16, 0.01),
                (-0.88, 0.11, 0.12, 0.0)]
    shell = Loft(stations, TAN)
    shell = sdf.Paint(shell, Box(1.0, 0.06, 1.0, ORANGE).at(0, -0.56, 0), ORANGE)
    cuff = Cylinder(0.11, 0.035, RUST, axis="y", ch=0.015).at(0, -0.89, 0)
    body = Union(knuckle(ELBOW, DARK, CHROME), cuff, housing(WRIST, DARK).at(*wrist_at))
    pieces = [Piece("gauntlet", shell, h=0.025, tris=200), Piece("joints", body, h=0.02, tris=260)]
    pieces[0].cut(Box(1.0, 0.006, 1.0, TAN).at(0, -0.35, 0))
    return MechPart("forearm", pieces, {"wrist": socket("wrist", WRIST, *wrist_at)})


def finger(base, splay, curl, lengths, r):
    """A jointed finger from base: segments bending by `curl` degrees each about x (toward +z),
    splayed sideways by `splay`; knuckle balls join the segments so nothing floats."""
    import numpy as np
    p = np.asarray(base, np.float32)
    parts = [sdf.Sphere(r * 1.25, DARK).at(*p)]
    ang = 0.0
    for i, l in enumerate(lengths):
        ang += curl
        d = np.array([np.sin(np.radians(splay)), -np.cos(np.radians(ang)), np.sin(np.radians(ang))], np.float32)
        d /= np.linalg.norm(d)
        q = p + d * l
        parts.append(segment(p, q, r * (1 - 0.12 * i), CHROME if i else DARK))
        parts.append(sdf.Sphere(r * (1.15 - 0.12 * i), DARK).at(*q))
        p = q
    parts.append(Box(r * 0.9, r * 0.6, r * 0.9, RUST, ch=r * 0.3).at(*p))
    return Union(*parts)


def claw():
    """A palm with three jointed fingers, splayed and curled round the grip, and an opposed
    thumb; a grip socket where the weapon sits in the curl."""
    palm = Union(Box(0.1, 0.09, 0.075, DARK, ch=0.03).at(0, -0.1, 0),
                 Box(0.085, 0.03, 0.06, OLIVE, ch=0.015).at(0, -0.06, 0.07))
    fingers = [finger((x, -0.18, 0.03), sp, 32, (0.1, 0.08, 0.06), 0.024) for x, sp in ((-0.07, -10), (0.0, 0), (0.07, 9))]
    thumb = finger((0.09, -0.11, -0.05), 35, -30, (0.08, 0.07), 0.026)
    body = Union(knuckle(WRIST, DARK), palm, *fingers, thumb)
    return MechPart("claw", [Piece("claw", body, h=0.01, tris=500)],
                    {"grip": socket("grip", GRIP, 0.0, -0.3, 0.12)})


def rifle():
    """A huge sniper rifle, barrel along -y from the grip: long barrel in a shroud, a big
    muzzle brake, a long scope on rings, a heavy magazine, a folded bipod and a skeleton stock."""
    receiver = Box(0.11, 0.55, 0.17, OLIVE, ch=0.05).at(0, -0.25, 0.14)
    shroud = Cylinder(0.11, 0.7, OLIVE, axis="y", ch=0.03).at(0, -1.45, 0.18)
    barrel = Cylinder(0.06, 1.0, DARK, axis="y", ch=0.01).at(0, -2.6, 0.18)
    brake = Union(Box(0.13, 0.22, 0.12, DARK, ch=0.04).at(0, -3.68, 0.18),
                  *[Box(0.15, 0.025, 0.06, RUBBER, ch=0.01).at(0, -3.6 - 0.07 * k, 0.18) for k in range(3)])
    scope = Union(Cylinder(0.075, 0.38, DARK, axis="y", ch=0.02).at(0, -0.5, 0.44),
                  Cylinder(0.09, 0.06, DARK, axis="y", ch=0.02).at(0, -0.9, 0.44),
                  Cylinder(0.07, 0.01, GLASS, axis="y").at(0, -0.97, 0.44),
                  Box(0.04, 0.03, 0.08, DARK, ch=0.01).at(0, -0.35, 0.33),
                  Box(0.04, 0.03, 0.08, DARK, ch=0.01).at(0, -0.7, 0.33))
    mag = Box(0.08, 0.14, 0.18, DARK, ch=0.03).rot("x", 8).at(0, -0.3, -0.12)
    bipod = Union(segment((0.05, -1.95, 0.08), (0.08, -1.3, -0.02), 0.022, DARK),
                  segment((-0.05, -1.95, 0.08), (-0.08, -1.3, -0.02), 0.022, DARK),
                  Box(0.08, 0.03, 0.04, DARK, ch=0.01).at(0, -1.97, 0.08))
    stock = Union(Box(0.07, 0.22, 0.05, RUST, ch=0.02).at(0, 0.42, 0.18),
                  Box(0.07, 0.05, 0.16, RUST, ch=0.02).at(0, 0.62, 0.08),
                  segment((0, 0.25, 0.05), (0, 0.6, -0.02), 0.03, DARK))
    grip = Union(Box(0.04, 0.05, 0.1, DARK, ch=0.015).at(0, 0, 0.02), knuckle(GRIP, DARK))
    pieces = [Piece("rifle", Union(receiver, shroud, scope, stock), h=0.02, tris=500),
              Piece("barrel", Union(barrel, brake, mag, bipod, grip), h=0.015, tris=500)]
    pieces[0].cut(Box(0.12, 0.006, 0.18, OLIVE).at(0, -0.6, 0.14))
    return MechPart("rifle", pieces, {})
