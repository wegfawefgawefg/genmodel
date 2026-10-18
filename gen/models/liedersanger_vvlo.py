"""Liedersanger, very very low: the silhouette in a few hundred triangles. Square-section
barrels and rods, merged blocks, a belt of double-length links (two rounds each), six spent
cases, and every remaining detail in the baked texture. Same rig part names, so the same
animation, smoke and sound drive it."""

import math

import numpy as np

import sdf
from models import liedersanger as hi
from models import liedersanger_lo as lo
from models.liedersanger import (BLACK, BRASS, DRUM_C, DRUM_LEN, DRUM_R, DRUM_TILT, FLASH, FLASH_TIP, GEAR, GUNMETAL,
                                 LENS, LOWER_Y, LOWER_Z, MATERIALS, PORT, RED, RUBBER, STEEL, TEAL, UPPER_Y, UPPER_Z,
                                 WHITE)
from models.liedersanger_vlo import rod
from scene import Part, Piece, Scene, instanced
from sdf import Box, Cylinder, Prism, Torus, Union, translate

UNIT = 0.12
STYLE = "vvlo"
BELT_PITCH = 0.6
BELT_START = 0.3
N_CASES = 6


def disc(x, y, z, r, mat):
    """A round paint region through z (a capsule, so it stays round whatever the facets)."""
    return sdf.Capsule((x, y, z - 2.0), (x, y, z + 2.0), r, mat)


def hex_prism(r, half, mat, plane):
    """A hexagonal prism (keeps six sides when the style squares off cylinders)."""
    return Prism(sdf.hexagon(r / math.cos(math.pi / 6)), half, mat, plane=plane)


def flash(name, muzzle_x, y, z):
    """A forward spike and a jet out of each port."""
    tip = muzzle_x - 0.05
    port = muzzle_x + hi.PORT_FROM_MUZZLE
    cones = [sdf.Cone(0.0, 0.3, 1.5, FLASH).at(tip - 1.5, 0, 0)]
    for side in (1, -1):
        out = np.array([0.35, 0, side], np.float32) / np.linalg.norm([0.35, 0, 1])
        cones.append(sdf.Xform(sdf.Cone(0.0, 0.24, 0.6, FLASH), sdf.frame_from_x(-out),
                               np.array([port, 0, side * 0.36], np.float32) + out * 0.6))
    body = sdf.Paint(Union(*cones), sdf.Cut(sdf.Sphere(4.0, 0).at(port, 0, 0), sdf.Sphere(0.5, 0).at(tip - 0.15, 0, 0)), FLASH_TIP)
    return Piece(name, body.at(0, y, z), h=0.02, tris=20, part=name, free=True)


def barrel(name, y, z, muzzle_x, spring_x0):
    rear = -1.0
    tube = Cylinder(0.28, (rear - muzzle_x - 1.0) * 0.5, GUNMETAL).at((rear + muzzle_x + 1.0) * 0.5, 0, 0)
    nut = Cylinder(0.5, 0.25, STEEL).at(rear - 0.15, 0, 0)
    brake = Box(0.6, 0.48, 0.46, GUNMETAL).at(muzzle_x + 0.55, 0, 0)
    pc = Piece(name, Union(tube, nut, brake).at(0, y, z), h=0.03, tris=36, part=name)
    port = muzzle_x + hi.PORT_FROM_MUZZLE
    pc.paint(Box(0.13, 1.0, 1.0, BRASS).at(muzzle_x + 2.0, y, z), BRASS)
    pc.paint(Box(0.7, 1.0, 1.0, GUNMETAL).at(spring_x0 - 1.2, y, z), STEEL)  # the jacket, painted
    pc.cut(Box(0.16, 0.28, 0.7, GUNMETAL).at(port, y, z), GUNMETAL)
    pc.cut(Cylinder(0.2, 0.2, RUBBER).at(muzzle_x, y, z), RUBBER)
    half = (rear - 0.3 - spring_x0) * 0.5
    sleeve = Cylinder(0.42, half, GUNMETAL).at(spring_x0 + 0.05 + half, y, z)
    sleeve_pc = Piece(name + "_sleeve", sleeve, h=0.03, tris=12, part=name + "_sleeve", tile="fins",
                      tile_uv=lo.fins_uv(spring_x0))
    return [pc, sleeve_pc, flash(name + "_flash", muzzle_x, y, z)]


def housings():
    upper = Prism([(-1.3, 0.95), (-1.3, 2.6), (-0.9, 3.0), (3.3, 3.05), (3.8, 3.38), (6.1, 3.4), (6.1, 2.35),
                   (2.1, 2.35), (1.9, 0.75), (0.6, 0.65)], 0.75, WHITE).at(0, 0, UPPER_Z)
    upper = sdf.Paint(upper, Prism([(0.45, 0.3), (0.62, 0.9), (1.3, 1.62), (2.5, 2.12), (3.15, 2.6), (3.4, 3.7),
                                    (7.0, 3.7), (7.0, 0.3)], 2.0, TEAL), TEAL)
    upper = sdf.Paint(upper, Box(0.36, 0.8, 1.2, RED).rot("z", -6).at(3.0, 3.1, UPPER_Z), RED)
    upper = sdf.Paint(upper, Box(0.12, 0.2, 0.2, LENS).at(-1.3, 2.55, UPPER_Z), LENS)
    up = Piece("upper_housing", upper, h=0.04, tris=40)
    up.paint(disc(1.35, 1.1, UPPER_Z, 0.56, TEAL), TEAL)          # the boss
    up.paint(disc(1.35, 1.1, UPPER_Z, 0.38, GUNMETAL), GUNMETAL)  # its cap
    up.cut(Box(0.03, 1.4, 1.0, WHITE).at(-0.2, 1.9, UPPER_Z))
    lower = Prism([(-1.85, -0.3), (-1.55, 0.38), (2.3, 0.38), (2.3, -1.0), (1.4, -1.5), (-1.0, -1.45)], 0.78, TEAL).at(0, 0, LOWER_Z)
    low = Piece("lower_housing", lower, h=0.04, tris=24)
    low.paint(disc(-0.65, -0.85, LOWER_Z, 0.38, GUNMETAL), GUNMETAL)
    return [up, low]


def core():
    block = Prism([(2.05, -1.3), (2.05, 2.4), (6.05, 2.4), (6.05, -0.6), (5.6, -2.1), (3.6, -2.1)], 0.6, GUNMETAL)
    rail = Box(1.6, 0.4, 0.5, GUNMETAL).at(7.0, 2.55, -0.05)
    pc = Piece("core", Union(block, rail), h=0.04, tris=36)
    gx, gy, gz = GEAR
    gear = Piece("gear", hex_prism(0.78, 0.13, GUNMETAL, "xy").at(gx, gy, gz), h=0.025, tris=20, part="gear")
    for i in range(9):
        a = math.radians(40 * i)
        gear.cut(Box(0.06, 0.06, 0.3, GUNMETAL).rot("z", 40 * i).at(gx + 0.74 * math.cos(a), gy + 0.74 * math.sin(a), gz), GUNMETAL)
    cover = Piece("cover", Box(1.15, 0.6, 0.72, GUNMETAL).at(3.95, 1.85, 0.05), h=0.04, tris=12, part="cover")
    for i in range(4):
        cover.cut(Box(0.05, 0.1, 0.8, STEEL).at(3.2 + 0.5 * i, 2.45, 0.05), STEEL)
    return [pc, gear, cover]


def belt():
    """Double-length links, two rounds painted on each (the tile repeats across the link)."""
    curve = sdf.Curve(hi.belt_curve())
    link = Box(1.1, 0.26, 0.16, STEEL).at(-0.28, 0, 0)
    n = int(curve.length / BELT_PITCH)
    spots = [curve.frame_at(BELT_START + i * BELT_PITCH) for i in range(n)]
    return instanced("belt", link, spots, h=0.02, tris=12, part="belt", part_each=True, tile="rounds", tile_uv=lo.rounds_uv)


def casings():
    return instanced("casings", Box(0.26, 0.1, 0.1, BRASS), [translate(*PORT) for _ in range(N_CASES)], h=0.02, tris=12,
                     part="case", part_each=True, free=True)


def drum():
    L, R = DRUM_LEN, DRUM_R
    place = lambda node: node.rot("z", DRUM_TILT).at(*DRUM_C)
    can = hex_prism(R + 0.12, L, BLACK, "yz")
    pc = Piece("drum", place(can), h=0.045, tris=20, part="drum")
    pc.paint(place(Box(0.9, 4.0, 4.0, TEAL).at(-L + 0.85, 0, 0)), TEAL)
    pc.paint(place(Box(0.16, 4.0, 4.0, TEAL).at(L - 0.1, 0, 0)), TEAL)
    pc.paint(place(Box(0.08, 4.0, 4.0, RED).at(-L + 1.55, 0, 0)), RED)
    pc.paint(place(sdf.Capsule((-L - 0.3, 0, 0), (-L + 0.05, 0, 0), R - 0.3, GUNMETAL)), GUNMETAL)  # the face
    pc.cut(place(Torus(R - 0.8, 0.06, GUNMETAL).at(-L, 0, 0)), STEEL)
    rail = rod((-L + 1.6, -1.6, 1.62), (L + 0.6, -1.6, 1.62), 0.14, TEAL)
    face = Piece("drum_face", place(Box(0.03, 0.4, 0.4, GUNMETAL).at(-L - 0.12, 0, 0)), h=0.02, tris=12, part="drum_face")
    return [pc, face, Piece("drum_rail", place(rail), h=0.03, tris=12, part="drum")]


def rear_frame():
    frame = Prism([(5.9, 2.95), (6.15, 3.45), (8.75, 3.45), (8.75, 0.2), (8.35, -0.35), (6.6, -0.1), (6.6, 1.55),
                   (7.95, 1.6), (7.95, 2.95)], 0.78, TEAL).at(0, 0, -0.05)
    sight = Box(1.0, 0.2, 0.36, RUBBER).at(7.15, 3.64, -0.05)
    handle = rod((8.1, 0.0, 0.85), (8.4, -1.25, 1.0), 0.14, TEAL)
    pc = Piece("rear_frame", Union(frame, sight, handle), h=0.04, tris=60)
    pc.paint(disc(8.2, 0.95, 0, 0.46, TEAL), TEAL)
    pc.paint(disc(8.2, 0.95, 0, 0.32, BLACK), BLACK)
    pc.paint(Box(0.9, 0.45, 1.0, GUNMETAL).at(7.0, 2.0, 0), GUNMETAL)
    return pc


def build():
    pieces = [
        *barrel("upper_barrel", UPPER_Y, UPPER_Z, -7.9, -3.9),
        *barrel("lower_barrel", LOWER_Y, LOWER_Z, -8.9, -4.3),
        *housings(),
        *core(),
        belt(),
        casings(),
        *drum(),
        rear_frame(),
    ]
    parts, paths = hi.rig(pieces, BELT_PITCH, BELT_START)
    parts += [Part("upper_barrel_sleeve", "root", (-2.5, UPPER_Y, UPPER_Z)),
              Part("lower_barrel_sleeve", "root", (-2.7, LOWER_Y, LOWER_Z)),
              Part("lens", "root", (-1.33, 2.62, UPPER_Z))]
    tiles = {"fins": lo.fins_tile(), "rounds": lo.rounds_tile()}
    return Scene("liedersanger_vvlo", MATERIALS, pieces, lo.decals(), texture_size=256, scale=0.25, parts=parts,
                 paths=paths, rust=0.7, tiles=tiles)
