"""Scoobee core parts: torso (the root: a machinery spine under a long cabin capsule),
head (a binocular sensor pod forward on a neck), pelvis (hip gear)."""

import sdf
from mech import MechPart, housing, knuckle, socket
from models.scoobee import CHROME, DARK, FLAP, GLASS, HIP, LAMP, NECK, PYLON, OLIVE, ORANGE, RUBBER, RUST, SHOULDER, TAN, WAIST
from models.scoobee.kit import (antenna, bolt_ring, bolts, drum_stack, grille, handle, hose, pipe, piston, teardrop,
                                teardrop_profile)
from scene import Piece
from sdf import Box, Cylinder, Loft, Prism, Torus, Union, segment

NECK_AT = (0.0, -0.24, 0.98)
SH_X, SH_Y, SH_Z = 0.84, -0.12, 0.3
WAIST_AT = (0.0, -0.6, -0.1)


def sensor_pod(x, y, z, r=0.25):
    """A big round sensor on the chassis flank, one form: a teardrop whose round face looks
    forward with a rounded recess sunk into it (the hull, contoured), and in the recess a dark
    lens with grille bars spanning it wall to wall and a bright centre (crisp parts)."""
    face_z = z + r * 0.92
    body = sdf.Cut(teardrop(r, 1.1, TAN).at(x, y, z), Cylinder(r * 0.74, 0.12, TAN, axis="z").at(x, y, face_z + 0.02), k=0.03)
    lens = Cylinder(r * 0.76, 0.02, GLASS, axis="z").at(x, y, face_z - 0.09)
    bars = Union(*[Box(r * 0.74 * max(1 - ((k - 2.5) / 3.0) ** 2, 0.05) ** 0.5, 0.012, 0.05, DARK, ch=0.004)
                   .at(x, y - r * 0.6 + k * r * 0.24, face_z - 0.05) for k in range(6)])
    centre = Cylinder(r * 0.2, 0.05, CHROME, axis="z", ch=0.012).at(x, y, face_z - 0.05)
    return body, Union(lens, bars, centre)


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


def spine_shell():
    """A smooth teardrop belly under the cabin that the sensor pods melt into."""
    belly = teardrop(0.36, 1.45, TAN).at(0, 0.0, 0.55)
    return sdf.Union(belly, Box(0.4, 0.12, 0.5, TAN, ch=0.1).at(0, 0.14, 0.1), k=0.15)


def back_gear():
    """The engine's outlets and the rest of the dress on the back: two bent exhaust stacks,
    round tail lamps in chrome bezels, flank vents, and long swept antennas (asymmetric)."""
    # short straight stacks standing up out of the back, raked a little rearward, on a manifold
    stacks = Union(
        segment((0.2, 0.5, -1.25), (0.24, 0.98, -1.42), 0.06, DARK),
        segment((-0.2, 0.5, -1.25), (-0.24, 0.9, -1.4), 0.06, DARK),
        Cylinder(0.075, 0.05, RUST, axis="y", ch=0.015).rot("x", -20).at(0.24, 0.98, -1.42),
        Cylinder(0.075, 0.05, RUST, axis="y", ch=0.015).rot("x", -20).at(-0.24, 0.9, -1.4),
        Box(0.3, 0.06, 0.12, DARK, ch=0.025).at(0, 0.5, -1.25),
    )
    lamps = Union(
        Cylinder(0.055, 0.03, LAMP, axis="z").at(0.18, 0.44, -1.64),
        Cylinder(0.055, 0.03, LAMP, axis="z").at(-0.18, 0.44, -1.64),
        sdf.Torus(0.06, 0.016, CHROME, axis="z").at(0.18, 0.44, -1.63),
        sdf.Torus(0.06, 0.016, CHROME, axis="z").at(-0.18, 0.44, -1.63),
    )
    # hinge brackets for the flank flaps: lugs off the body either end of each pin
    flap_mounts = Union(*[Box(0.06, 0.025, 0.035, DARK, ch=0.01).at(sx * 0.53, y, -0.05) for sx in (1, -1) for y in (0.12, -0.12)],
                        Cylinder(0.022, 0.13, CHROME, axis="y", ch=0.006).at(0.58, 0, -0.05),
                        Cylinder(0.022, 0.13, CHROME, axis="y", ch=0.006).at(-0.58, 0, -0.05))
    vents = Union(
        Box(0.03, 0.12, 0.3, DARK, ch=0.01).at(0.63, 0.42, -0.75),
        Box(0.03, 0.12, 0.3, DARK, ch=0.01).at(-0.63, 0.42, -0.75),
        grille((0.655, 0.42, -0.75), 0.56, 0.22, 5, axis="x"),
        grille((-0.655, 0.42, -0.75), 0.56, 0.22, 5, axis="x"),
        Box(0.2, 0.05, 0.18, DARK, ch=0.015).at(0, 0.78, -0.95),
        grille((0, 0.81, -0.95), 0.36, 0.3, 6, axis="z"),
    )
    whips = Union(
        antenna((0.36, 0.76, -0.95), (0.62, 2.2, -2.9), 0.008),
        antenna((0.24, 0.78, -1.1), (0.34, 1.55, -2.35), 0.006),
        antenna((-0.32, 0.76, -1.15), (-0.5, 1.85, -2.6), 0.007),
    )
    return Union(stacks, lamps, vents, whips, flap_mounts)


def torso():
    joints = Union(
        housing(NECK, DARK).rot("x", 90).at(*NECK_AT),
        housing(SHOULDER, DARK).rot("z", 90).at(SH_X, SH_Y, SH_Z),
        housing(SHOULDER, DARK).rot("z", 90).at(-SH_X, SH_Y, SH_Z),
        housing(WAIST, DARK).at(*WAIST_AT),
        # the waist column comes down onto a flange that carries the collar
        Cylinder(0.13, 0.14, DARK, axis="y", ch=0.03).at(0, WAIST_AT[1] + 0.2, WAIST_AT[2]),
        Torus(0.13, 0.03, CHROME).at(0, WAIST_AT[1] + 0.2, WAIST_AT[2]),
        Cylinder(0.25, 0.03, DARK, axis="y", ch=0.012).at(0, WAIST_AT[1] + 0.07, WAIST_AT[2]),
        drum_stack((SH_X - 0.2, SH_Y, SH_Z), 0.18, 3, 0.07),
        drum_stack((-SH_X + 0.2, SH_Y, SH_Z), 0.18, 3, 0.07),
        # a through-shaft carries both shoulder collars, with hubs where it meets them
        segment((SH_X, SH_Y, SH_Z), (-SH_X, SH_Y, SH_Z), 0.07, DARK),
        Cylinder(0.12, 0.05, DARK, axis="x", ch=0.02).at(SH_X - 0.04, SH_Y, SH_Z),
        Cylinder(0.12, 0.05, DARK, axis="x", ch=0.02).at(-SH_X + 0.04, SH_Y, SH_Z),
    )
    # sensor pods blended into the chassis (smooth hull, contoured), their faces crisp
    pod_r, face_r = sensor_pod(0.5, 0.1, 0.5)
    pod_l, face_l = sensor_pod(-0.5, 0.1, 0.5)
    hull = Union(spine_shell(), pod_r, pod_l, k=0.12)
    lights = Union(face_r, face_l)
    bolt_rows = Union(
        bolts([(x, 0.24, 0.92) for x in (-0.3, -0.1, 0.1, 0.3)], 0.016),
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
    pieces = [shell, Piece("spine", spine(), h=0.03, tris=1400), Piece("lights", lights, h=0.02, tris=500),
              Piece("hull", hull, h=0.03, tris=1400, mesher="contour"), Piece("joints", joints, h=0.03, tris=700),
              Piece("back", back_gear(), h=0.02, tris=900)]
    sockets = {
        "neck": socket("neck", NECK, *NECK_AT),
        "shoulder_r": socket("shoulder_r", SHOULDER, SH_X, SH_Y, SH_Z),
        "shoulder_l": socket("shoulder_l", SHOULDER, -SH_X, SH_Y, SH_Z),
        "waist": socket("waist", WAIST, *WAIST_AT),
        # cup flaps on the flanks behind the sensor pods, hinged at their noses
        "flap_r": socket("flap_r", FLAP, 0.58, 0.0, -0.05),
        "flap_l": socket("flap_l", FLAP, -0.58, 0.0, -0.05),
        # the missile pod rides out off the left side on an outrigger (an asymmetric load-out)
        "launcher": socket("launcher", PYLON, -0.62, 0.55, -0.35),
    }
    return MechPart("torso", pieces, sockets)


def head():
    """A swept helmet on a short neck reaching forward: a teardrop dome with an olive crest
    and brow, cheek intakes cut into it, and the old twin binocular lenses set into a sensor
    housing under the brow, with a small red eye beside them. Everything grows out of the
    helmet or sits in a recess in it."""
    neck = Union(segment((0, 0, 0), (0, -0.02, 0.3), 0.08, DARK), knuckle(NECK, DARK),
                 Cylinder(0.11, 0.04, DARK, axis="z", ch=0.012).at(0, -0.02, 0.3))
    dome = teardrop(0.26, 0.62, TAN).at(0, 0.08, 0.62)
    brow = Box(0.29, 0.06, 0.16, OLIVE, ch=0.05).rot("x", -8).at(0, 0.24, 0.64)
    crest = Prism([(0.32, 0.64), (0.43, 0.32), (0.38, 0.08), (0.26, 0.2)], 0.04, OLIVE, r=0.015, plane="yz")
    housing_ = Box(0.22, 0.1, 0.12, TAN, ch=0.06).at(0, 0.05, 0.8)
    chin = Box(0.14, 0.05, 0.12, RUST, ch=0.035).rot("x", 18).at(0, -0.1, 0.74)
    helmet = sdf.Union(dome, brow, crest, housing_, chin, k=0.06)
    # cheek intakes and the lens sockets are cut into the helmet itself
    for x in (0.2, -0.2):
        helmet = sdf.Cut(helmet, Box(0.04, 0.05, 0.14, TAN).at(x, -0.03, 0.72), k=0.015)
    for x in (0.11, -0.11):
        helmet = sdf.Cut(helmet, Cylinder(0.085, 0.1, TAN, axis="z").at(x, 0.06, 0.93), k=0.012)
    helmet = sdf.Paint(helmet, Box(1.0, 0.12, 1.0, OLIVE).at(0, 0.42, 0), OLIVE)
    lenses = Union(*[Union(
        Cylinder(0.08, 0.1, DARK, axis="z", ch=0.012).at(x, 0.06, 0.88),
        Cylinder(0.072, 0.02, CHROME, axis="z", ch=0.006).at(x, 0.06, 0.97),
        Cylinder(0.055, 0.015, GLASS, axis="z").at(x, 0.06, 0.985),
    ) for x in (0.11, -0.11)])
    eye = Union(Cylinder(0.026, 0.03, DARK, axis="z", ch=0.008).at(0.0, -0.03, 0.9), Cylinder(0.018, 0.01, LAMP, axis="z").at(0.0, -0.03, 0.93))
    slats = Union(grille((0.2, -0.03, 0.72), 0.1, 0.08, 3, axis="x"), grille((-0.2, -0.03, 0.72), 0.1, 0.08, 3, axis="x"))
    whips = Union(antenna((0.12, 0.31, 0.42), (0.24, 1.25, 0.02), 0.006), antenna((-0.1, 0.3, 0.4), (-0.17, 0.95, 0.12), 0.005))
    pieces = [Piece("helmet", helmet, h=0.016, tris=900, mesher="contour"),
              Piece("sensors", Union(neck, lenses, eye, slats, whips), h=0.012, tris=700)]
    pieces[0].cut(Box(0.3, 0.006, 0.6, TAN).at(0, 0.02, 0.4))
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


def flap(r=0.15, length=0.6):
    """A half-teardrop cup over the flank intake, hinged at its nose: it swings open with speed."""
    from models.scoobee.kit import cup_flap
    cup = cup_flap(r, length, TAN, 0.025)
    cup = sdf.Paint(cup, Box(1.0, 1.0, 0.04, ORANGE).at(0, 0, -0.32), ORANGE)
    hinge = Cylinder(0.025, 0.09, DARK, axis="y", ch=0.01)
    return MechPart("flap", [Piece("cup", cup, h=0.018, tris=260, mesher="contour"), Piece("hinge", hinge, h=0.02, tris=30)], {})


def launcher():
    """A missile pod off the shoulder on an outrigger pylon: six launch tubes in a bundle,
    two bands round them, warheads showing in the top row, a rear blast plate."""
    arm = Union(knuckle(PYLON, DARK), Box(0.22, 0.06, 0.09, DARK, ch=0.03).at(-0.2, 0.0, 0),
                Box(0.06, 0.12, 0.08, DARK, ch=0.02).at(-0.38, 0.1, 0))
    tubes, heads = [], []
    for i, (tx, ty) in enumerate([(-0.48, 0.22), (-0.32, 0.22), (-0.48, 0.36), (-0.32, 0.36), (-0.4, 0.5), (-0.24, 0.29)][:6]):
        tubes.append(Cylinder(0.075, 0.42, OLIVE, axis="z", ch=0.015).at(tx, ty, 0.05))
        tubes.append(Cylinder(0.055, 0.02, DARK, axis="z").at(tx, ty, 0.475))
        if ty > 0.3:
            heads.append(sdf.Cone(0.0, 0.05, 0.06, RUST, axis="z").at(tx, ty, 0.47))
    bands = Union(Box(0.2, 0.2, 0.03, DARK, ch=0.02).at(-0.38, 0.36, 0.3), Box(0.2, 0.2, 0.03, DARK, ch=0.02).at(-0.38, 0.36, -0.2))
    plate = Box(0.2, 0.2, 0.025, DARK, ch=0.015).at(-0.38, 0.36, -0.39)
    pieces = [Piece("tubes", Union(*tubes), h=0.02, tris=500), Piece("frame", Union(arm, bands, plate, *heads), h=0.015, tris=400)]
    return MechPart("launcher", pieces, {})
