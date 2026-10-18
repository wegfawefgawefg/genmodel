"""Liedersanger, very low: the lo gun on a strict triangle budget (about a thousand, fewer
visible at rest). Same layout, rig part names and muzzle/port positions, so the same
animation, smoke and sound drive it.

Every round part is a plain hexagonal prism with no chamfers; every block a plain box.
Detail that the lo gun built as geometry is carved or painted into the texture instead
(the bake reads the full SDF): gear teeth, cover ribs, drum bolts and rings, the coil, the
belt's rounds, panel seams.
"""

import math

import numpy as np

import sdf
from models import liedersanger as hi
from models import liedersanger_lo as lo
from models.liedersanger import (BLACK, BRASS, DRUM_C, DRUM_LEN, DRUM_R, DRUM_TILT, FLASH, FLASH_TIP, GEAR, GUNMETAL,
                                 LENS, LOWER_Y, LOWER_Z, MATERIALS, PORT, RED, RUBBER, STEEL, TEAL, UPPER_Y, UPPER_Z,
                                 WHITE)
from scene import Decal, Part, Piece, Scene, instanced
from sdf import Box, Cylinder, Prism, Torus, Union, compose, translate, turn

UNIT = 0.12
STYLE = "vlo"
BELT_PITCH = 0.3
BELT_START = 0.15
N_CASES = 10


def rod(a, b, r, mat):
    """A hexagonal rod from a to b (a plain cylinder placed along the segment)."""
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    half = float(np.linalg.norm(b - a)) * 0.5
    return sdf.Xform(Cylinder(r, half, mat, axis="x"), sdf.frame_from_x(b - a), (a + b) * 0.5)


def flash(name, muzzle_x, y, z):
    """A few hexagonal cones: a forward spike, a four-point star, a jet out of each port."""
    tip = muzzle_x - 0.05
    port = muzzle_x + hi.PORT_FROM_MUZZLE
    cones = [sdf.Cone(0.0, 0.24, 1.5, FLASH).at(tip - 1.5, 0, 0)]
    for a in np.radians([0, 90, 180, 270]):
        out = np.array([-0.6, 0.8 * math.cos(a), 0.8 * math.sin(a)], np.float32)
        cones.append(sdf.Xform(sdf.Cone(0.0, 0.15, 0.6, FLASH), sdf.frame_from_x(-out), np.array([tip - 0.15, 0, 0], np.float32) + out * 0.6))
    for side in (1, -1):
        out = np.array([0.35, 0, side], np.float32) / np.linalg.norm([0.35, 0, 1])
        cones.append(sdf.Xform(sdf.Cone(0.0, 0.2, 0.55, FLASH), sdf.frame_from_x(-out),
                               np.array([port, 0, side * 0.36], np.float32) + out * 0.55))
    body = sdf.Paint(Union(*cones), sdf.Cut(sdf.Sphere(4.0, 0).at(port, 0, 0), sdf.Sphere(0.5, 0).at(tip - 0.15, 0, 0)), FLASH_TIP)
    return Piece(name, body.at(0, y, z), h=0.02, tris=60, part=name, free=True)


def barrel(name, y, z, muzzle_x, spring_x0):
    """Tube, nut, jacket and a single brake block; the coil sleeve is a textured hex prism."""
    rear = -1.0
    tube = Cylinder(0.26, (rear - muzzle_x - 1.0) * 0.5, GUNMETAL).at((rear + muzzle_x + 1.0) * 0.5, 0, 0)
    nut = Cylinder(0.5, 0.25, STEEL).at(rear - 0.15, 0, 0)
    jacket = Cylinder(0.34, 0.7, GUNMETAL).at(spring_x0 - 1.2, 0, 0)
    brake = Box(0.6, 0.48, 0.46, GUNMETAL).at(muzzle_x + 0.55, 0, 0)
    body = Union(tube, nut, jacket, brake).at(0, y, z)
    pc = Piece(name, body, h=0.03, tris=80, part=name)
    # painted, not built: the brass band, the brake's side port, the bore, the gas tube
    port = muzzle_x + hi.PORT_FROM_MUZZLE
    pc.paint(Box(0.13, 1.0, 1.0, BRASS).at(muzzle_x + 2.0, y, z), BRASS)
    pc.cut(Box(0.16, 0.28, 0.7, GUNMETAL).at(port, y, z), GUNMETAL)
    pc.cut(Cylinder(0.2, 0.2, RUBBER).at(muzzle_x, y, z), RUBBER)
    half = (rear - 0.3 - spring_x0) * 0.5
    sleeve = Cylinder(0.4, half, GUNMETAL).at(spring_x0 + 0.05 + half, y, z)
    sleeve_pc = Piece(name + "_sleeve", sleeve, h=0.03, tris=20, part=name + "_sleeve", tile="fins",
                      tile_uv=lo.fins_uv(spring_x0))
    return [pc, sleeve_pc, flash(name + "_flash", muzzle_x, y, z)]


def upper_housing():
    profile = [(-1.3, 0.95), (-1.3, 2.45), (-1.0, 2.98), (3.3, 3.05), (3.8, 3.35), (6.1, 3.4), (6.1, 2.35),
               (2.15, 2.35), (2.0, 1.25), (1.85, 0.75), (0.85, 0.62), (0.55, 0.92)]
    shell = Prism(profile, 0.75, WHITE).at(0, 0, UPPER_Z)
    boss = Cylinder(0.56, 0.82, TEAL, axis="z").at(1.35, 1.1, UPPER_Z)
    body = Union(shell, boss)
    sweep = [(0.45, 0.3), (0.62, 0.9), (1.3, 1.62), (2.5, 2.12), (3.15, 2.6), (3.4, 3.7), (7.0, 3.7), (7.0, 0.3)]
    body = sdf.Paint(body, Prism(sweep, 2.0, TEAL), TEAL)
    body = sdf.Paint(body, Box(0.36, 0.8, 1.2, RED).rot("z", -6).at(3.0, 3.1, UPPER_Z), RED)
    pc = Piece("upper_housing", body, h=0.04, tris=80)
    pc.cut(Box(0.03, 1.4, 1.0, WHITE).at(-0.2, 1.9, UPPER_Z))
    pc.paint(Cylinder(0.4, 0.12, GUNMETAL, axis="z").at(1.35, 1.1, UPPER_Z + 0.85), GUNMETAL)  # the cap, painted in
    lens = Box(0.1, 0.2, 0.2, LENS).at(-1.38, 2.55, UPPER_Z)
    return [pc, Piece("lens", lens, h=0.02, tris=12, part="lens")]


def lower_housing():
    profile = [(-1.85, -0.25), (-1.85, 0.1), (-1.55, 0.38), (2.3, 0.38), (2.3, -1.0), (1.4, -1.5),
               (-0.2, -1.52), (-1.0, -1.35)]
    shell = Prism(profile, 0.78, TEAL).at(0, 0, LOWER_Z)
    boss = Cylinder(0.54, 0.84, TEAL, axis="z").at(-0.65, -0.85, LOWER_Z)
    pc = Piece("lower_housing", Union(shell, boss), h=0.04, tris=60)
    pc.paint(Cylinder(0.38, 0.12, GUNMETAL, axis="z").at(-0.65, -0.85, LOWER_Z + 0.87), GUNMETAL)
    return pc


def core():
    block = Box(2.0, 1.85, 0.62, GUNMETAL).at(4.05, 0.55, 0)
    chute = Box(1.0, 0.75, 0.55, GUNMETAL).rot("z", -12).at(4.6, -1.35, 0.1)
    rail = Box(1.6, 0.4, 0.5, GUNMETAL).at(7.0, 2.55, -0.05)
    pc = Piece("core", Union(block, chute, rail), h=0.04, tris=40)
    pc.cut(Box(1.5, 0.03, 1.0, GUNMETAL).at(4.6, 1.05, 0))
    gx, gy, gz = GEAR
    gear = Cylinder(0.78, 0.13, GUNMETAL, axis="z").at(gx, gy, gz)
    gear_pc = Piece("gear", gear, h=0.025, tris=20, part="gear")
    # the teeth are notches carved into the texture round the rim
    for i in range(9):
        a = math.radians(40 * i)
        gear_pc.cut(Box(0.06, 0.06, 0.3, GUNMETAL).rot("z", 40 * i).at(gx + 0.74 * math.cos(a), gy + 0.74 * math.sin(a), gz), GUNMETAL)
    gear_pc.paint(Cylinder(0.32, 0.2, STEEL, axis="z").at(gx, gy, gz + 0.12), STEEL)
    cover = Box(1.15, 0.6, 0.72, GUNMETAL).at(3.95, 1.85, 0.05)
    cover_pc = Piece("cover", cover, h=0.04, tris=12, part="cover")
    for i in range(4):
        cover_pc.cut(Box(0.05, 0.1, 0.8, STEEL).at(3.2 + 0.5 * i, 2.45, 0.05), STEEL)
    return [pc, gear_pc, cover_pc]


def belt():
    """Flat link boxes on the hanging curve, the rounds painted on as a tile."""
    curve = sdf.Curve(hi.belt_curve())
    link = Box(1.1, 0.13, 0.16, STEEL).at(-0.28, 0, 0)
    n = int(curve.length / BELT_PITCH)
    spots = [curve.frame_at(BELT_START + i * BELT_PITCH) for i in range(n)]
    links = instanced("belt", link, spots, h=0.02, tris=12, part="belt", part_each=True, tile="rounds", tile_uv=lo.rounds_uv)
    guide = Box(0.75, 0.3, 0.45, GUNMETAL).at(3.75, 1.5, 0.85)
    return [links, Piece("belt_guide", guide, h=0.03, tris=12)]


def casings():
    case = Box(0.26, 0.1, 0.1, BRASS)
    return instanced("casings", case, [translate(*PORT) for _ in range(N_CASES)], h=0.02, tris=12,
                     part="case", part_each=True, free=True)


def drum():
    L, R = DRUM_LEN, DRUM_R
    can = Cylinder(R, L, BLACK)
    front = Cylinder(R + 0.18, 0.9, TEAL).at(-L + 0.85, 0, 0)
    back = Cylinder(R + 0.1, 0.16, TEAL).at(L - 0.1, 0, 0)
    body = Union(can, front, back).rot("z", DRUM_TILT).at(*DRUM_C)
    pc = Piece("drum", body, h=0.045, tris=60, part="drum")
    place = lambda node: node.rot("z", DRUM_TILT).at(*DRUM_C)
    pc.paint(place(Box(0.08, 3.0, 3.0, RED).at(-L + 1.55, 0, 0)), RED)  # the red trim ring
    for i in range(4):  # bolt heads painted round the front ring
        a = math.radians(45 + 90 * i)
        pc.paint(place(Box(0.12, 0.12, 0.12, STEEL).at(-L + 0.7, (R + 0.18) * math.cos(a), (R + 0.18) * math.sin(a))), STEEL)
    face = Cylinder(R - 0.3, 0.06, GUNMETAL).at(-L - 0.1, 0, 0)
    face_pc = Piece("drum_face", place(face), h=0.03, tris=20, part="drum_face")
    face_pc.cut(place(Torus(R - 0.8, 0.07, GUNMETAL).at(-L - 0.16, 0, 0)), STEEL)
    face_pc.cut(place(Box(0.2, 0.1, R - 0.6, STEEL).at(-L - 0.16, 0, 0)), STEEL)
    rails = Union(rod((-L + 1.6, -1.5, 1.6), (L + 0.6, -1.5, 1.6), 0.14, TEAL),
                  rod((L + 0.6, -1.5, 1.6), (L + 0.6, 1.0, 1.25), 0.14, TEAL))
    return [pc, face_pc, Piece("drum_rails", place(rails), h=0.03, tris=40, part="drum")]


def rear_frame():
    top_bar = Prism([(5.9, 2.95), (6.15, 3.45), (8.75, 3.45), (8.75, 2.95)], 0.78, TEAL).at(0, 0, -0.05)
    post = Prism([(7.95, 3.2), (8.75, 3.2), (8.75, 0.2), (8.35, -0.3), (7.95, 0.2)], 0.8, TEAL).at(0, 0, -0.05)
    boss = Prism([(6.5, 0.0), (6.6, 1.55), (8.2, 1.65), (8.3, 0.1), (7.6, -0.35)], 0.72, TEAL).at(0, 0, -0.05)
    cap = Cylinder(0.46, 0.86, TEAL, axis="z").at(8.2, 0.95, -0.05)
    sight = Box(1.0, 0.2, 0.36, RUBBER).at(7.15, 3.64, -0.05)
    # the carry handle and strut as straight hex rods
    handle = Union(rod((8.0, 0.1, 0.85), (8.75, -0.35, 1.0), 0.14, TEAL), rod((8.75, -0.35, 1.0), (8.45, -1.3, 1.05), 0.14, TEAL),
                   rod((8.45, -1.3, 1.05), (7.7, -1.1, 1.05), 0.14, TEAL))
    strut = rod((6.3, 1.5, 0.7), (5.4, -0.2, 0.95), 0.14, TEAL)
    pc = Piece("rear_frame", Union(top_bar, post, boss, cap, sight, handle, strut), h=0.04, tris=150)
    pc.paint(Cylinder(0.32, 0.1, BLACK, axis="z").at(8.2, 0.95, 0.85), BLACK)
    pc.paint(Box(0.9, 0.45, 0.2, GUNMETAL).at(7.0, 2.0, 0.75), GUNMETAL)
    return pc


def build():
    pieces = [
        *barrel("upper_barrel", UPPER_Y, UPPER_Z, -7.9, -3.9),
        *barrel("lower_barrel", LOWER_Y, LOWER_Z, -8.9, -4.3),
        *upper_housing(),
        lower_housing(),
        *core(),
        *belt(),
        casings(),
        *drum(),
        rear_frame(),
    ]
    parts, paths = hi.rig(pieces, BELT_PITCH, BELT_START)
    parts += [Part("upper_barrel_sleeve", "root", (-2.5, UPPER_Y, UPPER_Z)),
              Part("lower_barrel_sleeve", "root", (-2.7, LOWER_Y, LOWER_Z))]
    tiles = {"fins": lo.fins_tile(), "rounds": lo.rounds_tile()}
    return Scene("liedersanger_vlo", MATERIALS, pieces, lo.decals(), texture_size=256, scale=0.25, parts=parts,
                 paths=paths, rust=0.7, tiles=tiles)
