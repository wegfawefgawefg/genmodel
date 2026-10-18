"""Scoobee limbs, authored for the right side (+x); left ones are mirrored copies.
Legs hang down -y from their plug; the elbow socket turns the forearm to point forward."""

import sdf
from mech import MechPart, housing, knuckle, socket
from models.scoobee import (ANKLE, CHROME, DARK, ELBOW, GRIP, HIP, KNEE, OLIVE, ORANGE, RUBBER, RUST, TAN,
                            WRIST)
from scene import Piece
from sdf import Box, Cylinder, Lathe, Union, segment

KNEE_AT = (0.22, -0.24, 0.04)
SHIN_LEN = 1.78


def thigh():
    """Short and stout: from the hip ball out and down to the knee fork, a strut pair and a
    piston between them."""
    kx, ky, kz = KNEE_AT
    struts = Union(
        segment((0, 0, 0.09), (kx, ky + 0.08, kz + 0.09), 0.07, DARK),
        segment((0, 0, -0.09), (kx, ky + 0.08, kz - 0.09), 0.07, DARK),
        segment((0.02, -0.05, 0), (kx - 0.02, ky + 0.12, kz), 0.05, CHROME),
        Box(0.13, 0.05, 0.13, DARK, ch=0.03).at(kx * 0.6, ky * 0.6, kz),
    )
    body = Union(knuckle(HIP, DARK), struts, housing(KNEE, DARK, CHROME).at(*KNEE_AT))
    return MechPart("thigh", [Piece("thigh", body, h=0.025, tris=300)], {"knee": socket("knee", KNEE, *KNEE_AT)})


def shin():
    """The big bowling-pin shell hanging from the knee knuckle, an orange band round its belly,
    the ankle fork under its hem."""
    # the shell rises past the knee so the joint sits inside its neck, like the reference
    profile = [(0.16, 0.2), (0.23, 0.05), (0.3, -0.2), (0.4, -0.55), (0.47, -0.95), (0.49, -1.2),
               (0.46, -1.45), (0.38, -1.63), (0.24, -1.74)]
    shell = Lathe(profile, TAN)
    shell = sdf.Paint(shell, Box(2.0, 0.1, 2.0, ORANGE).at(0, -1.02, 0), ORANGE)
    hem = Cylinder(0.24, 0.03, RUST, axis="y", ch=0.01).at(0, -1.75, 0)
    body = Union(shell, hem)
    ankle_at = (0.0, -SHIN_LEN, 0.02)
    joints = Union(knuckle(KNEE, DARK, CHROME), housing(ANKLE, DARK).at(*ankle_at))
    pieces = [Piece("shell", body, h=0.03, tris=300), Piece("joints", joints, h=0.025, tris=200)]
    pieces[0].cut(sdf.Torus(0.48, 0.01, TAN).at(0, -1.3, 0))  # a seam under the band
    return MechPart("shin", pieces, {"ankle": socket("ankle", ANKLE, *ankle_at)})


def foot():
    """Three splayed claw toes forward and a spur behind, on a small ankle block."""
    block = Box(0.12, 0.07, 0.13, DARK, ch=0.03).at(0, -0.12, 0)
    toes = []
    for ang in (-28, 0, 28):
        toes.append(Box(0.05, 0.04, 0.17, DARK, ch=0.02).rot("x", 12).rot("y", ang).at(0, -0.2, 0.14))
    spur = Box(0.05, 0.04, 0.12, DARK, ch=0.02).rot("x", -10).at(0, -0.2, -0.13)
    pads = Box(0.13, 0.025, 0.2, RUBBER, ch=0.01).at(0, -0.25, 0.08)
    body = Union(knuckle(ANKLE, DARK), block, *toes, spur, pads)
    return MechPart("foot", [Piece("foot", body, h=0.02, tris=200)], {})


def upper_arm():
    """From the shoulder ball down to the elbow: an actuator can and a strut with a piston."""
    elbow_at = (0.0, -0.62, 0.0)
    can = Cylinder(0.12, 0.14, OLIVE, axis="y", ch=0.04).at(0, -0.2, 0)
    struts = Union(
        segment((0, -0.3, 0.06), (0, -0.55, 0.06), 0.05, DARK),
        segment((0, -0.3, -0.06), (0, -0.55, -0.06), 0.05, CHROME),
    )
    body = Union(knuckle(sdf_ball(), DARK), can, struts, housing(ELBOW, DARK, CHROME).at(*elbow_at))
    # the forearm points forward at rest: turn the socket so the child's -y is +z
    return MechPart("upper_arm", [Piece("upper_arm", body, h=0.025, tris=260)],
                    {"elbow": socket("elbow", ELBOW, *elbow_at, rot=[("x", -90)])})


def sdf_ball():
    from models.scoobee import SHOULDER
    return SHOULDER


def forearm():
    """A tan shell with an orange band, wrist fork at its end."""
    wrist_at = (0.0, -0.72, 0.0)
    shell = Box(0.13, 0.3, 0.14, TAN, ch=0.07).at(0, -0.36, 0)
    shell = sdf.Paint(shell, Box(1.0, 0.06, 1.0, ORANGE).at(0, -0.42, 0), ORANGE)
    cuff = Cylinder(0.11, 0.05, RUST, axis="y", ch=0.02).at(0, -0.66, 0)
    body = Union(knuckle(ELBOW, DARK, CHROME), shell, cuff, housing(WRIST, DARK).at(*wrist_at))
    return MechPart("forearm", [Piece("forearm", body, h=0.025, tris=260)], {"wrist": socket("wrist", WRIST, *wrist_at)})


def claw():
    """A palm block with three chrome fingers and a thumb; a grip socket for a weapon."""
    palm = Box(0.09, 0.07, 0.07, DARK, ch=0.025).at(0, -0.1, 0)
    fingers = []
    for x in (-0.055, 0.0, 0.055):
        fingers.append(Box(0.02, 0.07, 0.022, CHROME, ch=0.008).at(x, -0.22, 0.03))
        fingers.append(Box(0.018, 0.05, 0.02, CHROME, ch=0.008).rot("x", 25).at(x, -0.31, 0.06))
    thumb = Box(0.02, 0.06, 0.02, CHROME, ch=0.008).rot("x", -35).at(0.0, -0.17, -0.08)
    body = Union(knuckle(WRIST, DARK), palm, *fingers, thumb)
    return MechPart("claw", [Piece("claw", body, h=0.015, tris=220)],
                    {"grip": socket("grip", GRIP, 0.0, -0.2, 0.0)})


def rifle():
    """A long rifle held at the grip, barrel along -y (out along the forearm)."""
    receiver = Box(0.07, 0.42, 0.11, OLIVE, ch=0.03).at(0, -0.15, 0.06)
    barrel = Cylinder(0.04, 0.55, DARK, axis="y", ch=0.01).at(0, -1.1, 0.08)
    shroud = Cylinder(0.065, 0.3, OLIVE, axis="y", ch=0.02).at(0, -0.7, 0.08)
    brake = Cylinder(0.06, 0.07, DARK, axis="y", ch=0.02).at(0, -1.64, 0.08)
    mag = Box(0.04, 0.09, 0.07, DARK, ch=0.015).rot("x", 10).at(0, -0.1, -0.08)
    scope = Cylinder(0.035, 0.12, DARK, axis="y", ch=0.01).at(0, -0.2, 0.2)
    stock = Box(0.05, 0.16, 0.08, RUST, ch=0.02).at(0, 0.33, 0.04)
    body = Union(receiver, barrel, shroud, brake, mag, scope, stock, knuckle(GRIP, DARK))
    return MechPart("rifle", [Piece("rifle", body, h=0.02, tris=300)], {})
