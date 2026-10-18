"""Liedersanger, low fidelity: the same gun rebuilt from scratch for the lofi style.

Same layout, rig part names and muzzle/port positions as liedersanger.py, so its animation,
smoke and sound drive this one unchanged. Every part is sized to read at a few thousand
triangles and a 256 px texture: thick barrels, a handful of fat coil rings, big brakes,
chunky links and teeth, and nothing hairline (no knurling, ribs, hoses or gas tubes).
"""

import math

import numpy as np
from PIL import Image, ImageDraw

import sdf
from models import liedersanger as hi
from models.liedersanger import (BLACK, BRASS, DRUM_C, DRUM_LEN, DRUM_R, DRUM_TILT, GEAR, GUNMETAL, LENS,
                                 LOWER_Y, LOWER_Z, MATERIALS, N_CASES, PORT, RED, RUBBER, STEEL, TEAL,
                                 UPPER_Y, UPPER_Z, WHITE, drum_point, muzzle_flash, tube)
from scene import Decal, Piece, Scene, instanced
from sdf import Box, Cylinder, Prism, Torus, Union, compose, segment, translate, turn

UNIT = 0.12
FIN_PITCH = 0.16  # coil spacing along the sleeve, one tile repeat per fin
STYLE = "lofi"
BELT_PITCH = 0.3
BELT_START = 0.15


def rounds_tile():
    """One belt link seen from outside: a brass round pointing at the muzzle (left, -x)
    held by a steel clip on the right. Pixel art; alpha is the specular mask."""
    img = Image.new("RGBA", (64, 16), (58, 56, 54, 90))
    d = ImageDraw.Draw(img)
    d.polygon([(0, 8), (8, 4), (8, 12)], fill=(176, 140, 70, 200))        # tip
    d.rectangle((8, 4, 41, 12), fill=(166, 128, 60, 200))                  # case
    d.rectangle((8, 4, 41, 5), fill=(220, 186, 110, 230))                  # highlight
    d.rectangle((8, 11, 41, 12), fill=(110, 82, 38, 160))                  # shade
    d.rectangle((42, 3, 44, 13), fill=(140, 110, 52, 200))                 # rim
    d.rectangle((46, 1, 60, 15), fill=(150, 150, 152, 180))                # clip
    d.rectangle((46, 1, 60, 2), fill=(196, 198, 202, 220))
    d.rectangle((52, 6, 54, 10), fill=(70, 70, 72, 120))                   # clip slot
    d.rectangle((0, 0, 63, 0), fill=(36, 34, 32, 60))                      # gaps between links
    d.rectangle((0, 15, 63, 15), fill=(36, 34, 32, 60))
    return img


def fins_tile():
    """One coil turn along the sleeve: a bright ridge, its shadow, a dark groove."""
    rows = [(86, 86, 90), (150, 150, 156), (190, 192, 198), (150, 150, 156), (112, 112, 116),
            (86, 86, 90), (62, 62, 66), (40, 40, 44)]
    img = Image.new("RGBA", (4, len(rows)))
    for y, c in enumerate(rows):
        for x in range(4):
            img.putpixel((x, y), (*c, 170))
    return img


def fins_uv(axis_x0):
    """Bands along the barrel axis; u is constant, so there's no seam round the sleeve."""
    return lambda v: np.stack([np.full(len(v), 0.5, np.float32), (v[:, 0] - axis_x0) / FIN_PITCH], 1).astype(np.float32)


def rounds_uv(v):
    """Planar across the link: u along the round (-x tip to +x clip), v across the link."""
    return np.stack([(v[:, 0] + 1.38) / 2.2, (v[:, 1] + 0.13) / 0.26], 1).astype(np.float32)


def barrel(name, y, z, muzzle_x, spring_x0):
    """A fat barrel sliding into a plain sleeve (its coil is a texture, see TILES), a big nut,
    one band and a muzzle brake built as a cage of blocks round a real side port."""
    rear = -1.0
    tube_ = Cylinder(0.26, (rear - muzzle_x - 1.0) * 0.5, GUNMETAL, ch=0.03).at((rear + muzzle_x + 1.0) * 0.5, 0, 0)
    nut = Cylinder(0.5, 0.25, STEEL, ch=0.08).at(rear - 0.15, 0, 0)
    collar = Cylinder(0.44, 0.16, GUNMETAL, ch=0.05).at(spring_x0 - 0.1, 0, 0)
    jacket = Cylinder(0.34, 0.7, GUNMETAL, ch=0.06).at(spring_x0 - 1.2, 0, 0)
    band = Cylinder(0.36, 0.12, BRASS, ch=0.04).at(muzzle_x + 2.0, 0, 0)
    port = muzzle_x + hi.PORT_FROM_MUZZLE
    brake = Union(
        Box((port - 0.16 - muzzle_x) * 0.5, 0.48, 0.46, GUNMETAL, ch=0.08).at((muzzle_x + port - 0.16) * 0.5, 0, 0),
        Box((muzzle_x + 1.1 - port - 0.16) * 0.5, 0.48, 0.46, GUNMETAL, ch=0.08).at((port + 0.16 + muzzle_x + 1.1) * 0.5, 0, 0),
        Box(0.17, 0.1, 0.46, GUNMETAL, ch=0.03).at(port, 0.38, 0),
        Box(0.17, 0.1, 0.46, GUNMETAL, ch=0.03).at(port, -0.38, 0),
        Cylinder(0.2, 0.03, RUBBER).at(muzzle_x - 0.02, 0, 0),
    )
    neck = Cylinder(0.3, 0.22, GUNMETAL, ch=0.05).at(muzzle_x + 1.3, 0, 0)
    gas = Box(1.2, 0.1, 0.1, GUNMETAL, ch=0.03).at(spring_x0 - 1.3, -0.42, 0.08)
    body = Union(tube_, nut, collar, jacket, band, brake, neck, gas).at(0, y, z)

    half = (rear - 0.3 - spring_x0) * 0.5
    sleeve = Cylinder(0.4, half, GUNMETAL, ch=0.05).at(spring_x0 + 0.05 + half, y, z)
    flash = muzzle_flash(name + "_flash", muzzle_x, y, z)
    flash.tris = 200
    sleeve_pc = Piece(name + "_sleeve", sleeve, h=0.03, tris=40, part=name + "_sleeve", tile="fins",
                      tile_uv=fins_uv(spring_x0))
    return [Piece(name, body, h=0.03, tris=420, part=name), sleeve_pc, flash]


def upper_housing():
    profile = [(-1.3, 0.95), (-1.3, 2.45), (-1.0, 2.98), (3.3, 3.05), (3.8, 3.35), (6.1, 3.4), (6.1, 2.35),
               (2.15, 2.35), (2.0, 1.25), (1.85, 0.75), (0.85, 0.62), (0.55, 0.92)]
    shell = Prism(profile, 0.75, WHITE, r=0.12).at(0, 0, UPPER_Z)
    boss = Cylinder(0.56, 0.82, TEAL, axis="z", ch=0.12).at(1.35, 1.1, UPPER_Z)
    cap = Cylinder(0.4, 0.12, GUNMETAL, axis="z", ch=0.05).at(1.35, 1.1, UPPER_Z + 0.85)
    latch = Box(0.3, 0.24, 0.12, WHITE, ch=0.05).at(-0.4, 2.25, UPPER_Z + 0.75)
    body = Union(Union(shell, boss, k=0.15), cap, latch)
    sweep = [(0.45, 0.3), (0.62, 0.9), (1.3, 1.62), (2.5, 2.12), (3.15, 2.6), (3.4, 3.7), (7.0, 3.7), (7.0, 0.3)]
    body = sdf.Paint(body, Prism(sweep, 2.0, TEAL), TEAL)
    body = sdf.Paint(body, Box(0.36, 0.8, 1.2, RED).rot("z", -6).at(3.0, 3.1, UPPER_Z), RED)
    pc = Piece("upper_housing", body, h=0.04, tris=520)
    pc.cut(Box(0.03, 1.4, 1.0, WHITE).at(-0.2, 1.9, UPPER_Z))
    # a big square lamp reads at this size where a small round lens would not
    lens = Box(0.1, 0.2, 0.2, LENS, ch=0.04).at(-1.38, 2.55, UPPER_Z)
    return [pc, Piece("lens", lens, h=0.02, tris=24, part="lens")]


def lower_housing():
    profile = [(-1.85, -0.25), (-1.85, 0.1), (-1.55, 0.38), (2.3, 0.38), (2.3, -1.0), (1.4, -1.5),
               (-0.2, -1.52), (-1.0, -1.35)]
    shell = Prism(profile, 0.78, TEAL, r=0.14).at(0, 0, LOWER_Z)
    boss = Cylinder(0.54, 0.84, TEAL, axis="z", ch=0.12).at(-0.65, -0.85, LOWER_Z)
    cap = Cylinder(0.38, 0.12, GUNMETAL, axis="z", ch=0.05).at(-0.65, -0.85, LOWER_Z + 0.87)
    plate = Box(0.8, 0.65, 0.07, TEAL, ch=0.04).at(1.2, -0.45, LOWER_Z + 0.8)
    body = Union(Union(shell, boss, k=0.15), cap, plate)
    return Piece("lower_housing", body, h=0.04, tris=360)


def core():
    """Receiver block, chute down to the drum, the rear rail; chunky gear and feed cover."""
    block = Box(2.0, 1.85, 0.62, GUNMETAL, ch=0.12).at(4.05, 0.55, 0)
    chute = Box(1.0, 0.75, 0.55, GUNMETAL, ch=0.12).rot("z", -12).at(4.6, -1.35, 0.1)
    rear_rail = Box(1.6, 0.4, 0.5, GUNMETAL, ch=0.1).at(7.0, 2.55, -0.05)
    fitting = Box(0.35, 0.3, 0.2, TEAL, ch=0.08).at(2.6, -0.8, 0.75)
    pc = Piece("core", Union(block, chute, rear_rail, fitting), h=0.04, tris=300)
    pc.cut(Box(1.5, 0.03, 1.0, GUNMETAL).at(4.6, 1.05, 0))

    gx, gy, gz = GEAR
    gear = Union(
        Cylinder(0.66, 0.13, GUNMETAL, axis="z", ch=0.05).at(gx, gy, gz),
        Cylinder(0.32, 0.12, STEEL, axis="z", ch=0.05).at(gx, gy, gz + 0.18),
        Box(0.08, 0.5, 0.06, STEEL, ch=0.02).at(gx, gy, gz + 0.3),
    )
    spots = [compose(translate(*GEAR), compose(turn("z", 40 * i), translate(0.74, 0, 0))) for i in range(9)]
    teeth = instanced("gear_teeth", Box(0.14, 0.12, 0.13, GUNMETAL, ch=0.03), spots, h=0.02, tris=12, part="gear")
    cover = Box(1.15, 0.55, 0.72, GUNMETAL, ch=0.14).at(3.95, 1.85, 0.05)
    ribs = instanced("cover_ribs", Box(0.1, 0.1, 0.7, STEEL, ch=0.04),
                     [translate(3.2 + 0.5 * i, 2.44, 0.05) for i in range(4)], h=0.02, tris=12, part="cover")
    return [pc, Piece("gear", gear, h=0.025, tris=90, part="gear"), teeth,
            Piece("cover", cover, h=0.04, tris=40, part="cover"), ribs]


def belt():
    """Fat links on the same hanging curve, with a chute carrying the top stretch."""
    curve = sdf.Curve(hi.belt_curve())
    # a flat link panel; the rounds and links are its texture (TILES["rounds"])
    link = Box(1.1, 0.13, 0.16, STEEL, ch=0.04).at(-0.28, 0, 0)
    n = int(curve.length / BELT_PITCH)
    spots = [curve.frame_at(BELT_START + i * BELT_PITCH) for i in range(n)]
    links = instanced("belt", link, spots, h=0.02, tris=40, part="belt", part_each=True, tile="rounds",
                      tile_uv=rounds_uv)
    s0 = curve.length * 0.7
    run = curve.length - s0 + 0.05
    chute = Prism(sdf.channel(2.6, 0.46, 0.1), run * 0.5, GUNMETAL, plane="yz").at(s0 + run * 0.5, 0, 0)
    chute = sdf.Bend(chute.at(0, -0.28, 0.2), curve, across=(1, 0, 0))
    guide = Box(0.75, 0.3, 0.45, GUNMETAL, ch=0.08).at(3.75, 1.5, 0.85)
    return [links, Piece("belt_guide", Union(guide, chute), h=0.035, tris=140)]


def casings():
    case = Cylinder(0.1, 0.26, BRASS, ch=0.03)
    return instanced("casings", case, [translate(*PORT) for _ in range(N_CASES)], h=0.02, tris=16,
                     part="case", part_each=True, free=True)


def drum():
    L, R = DRUM_LEN, DRUM_R
    can = Cylinder(R, L, BLACK, ch=0.15)
    front = Cylinder(R + 0.18, 0.9, TEAL, ch=0.15).at(-L + 0.85, 0, 0)
    # the face sits proud of the ring rather than recessed into it (no cut)
    face = Union(
        Cylinder(R - 0.3, 0.06, GUNMETAL, ch=0.03).at(-L - 0.1, 0, 0),
        Torus(R - 0.8, 0.1, GUNMETAL).at(-L - 0.16, 0, 0),
        Cylinder(0.35, 0.08, STEEL, ch=0.04).at(-L - 0.2, 0, 0),
        Box(0.05, 0.12, R - 0.6, STEEL, ch=0.03).at(-L - 0.2, 0, 0),
    )
    trim = Torus(R + 0.19, 0.08, RED).at(-L + 1.55, 0, 0)
    back = Cylinder(R + 0.1, 0.16, TEAL, ch=0.06).at(L - 0.1, 0, 0)
    rails = Union(
        segment((-L + 1.6, -1.5, 1.6), (L + 0.6, -1.5, 1.6), 0.14, TEAL),
        segment((L + 0.6, -1.5, 1.6), (L + 0.6, 1.0, 1.25), 0.14, TEAL),
    )
    body = Union(can, front, trim, back, rails).rot("z", DRUM_TILT).at(*DRUM_C)
    face = face.rot("z", DRUM_TILT).at(*DRUM_C)
    place = compose(translate(*DRUM_C), turn("z", DRUM_TILT))
    spots = [compose(place, compose(translate(-L + 0.7, 0, 0), compose(turn("x", 45 + 90 * i), translate(0, R + 0.15, 0))))
             for i in range(4)]
    bolts = instanced("drum_bolts", Box(0.14, 0.12, 0.14, STEEL, ch=0.04).at(0, 0.06, 0), spots, h=0.02, tris=12,
                      part="drum")
    return [Piece("drum", body, h=0.045, tris=560, part="drum"), Piece("drum_face", face, h=0.03, tris=150, part="drum_face"),
            bolts]


def rear_frame():
    top_bar = Prism([(5.9, 2.95), (6.15, 3.45), (8.75, 3.45), (8.75, 2.95)], 0.78, TEAL, r=0.1).at(0, 0, -0.05)
    post = Prism([(7.95, 3.2), (8.75, 3.2), (8.75, 0.2), (8.35, -0.3), (7.95, 0.2)], 0.8, TEAL, r=0.12).at(0, 0, -0.05)
    boss = Prism([(6.5, 0.0), (6.6, 1.55), (8.2, 1.65), (8.3, 0.1), (7.6, -0.35)], 0.72, TEAL, r=0.15).at(0, 0, -0.05)
    frame = Union(top_bar, post, boss, k=0.1)
    mech = Box(0.9, 0.45, 0.55, GUNMETAL, ch=0.1).at(7.0, 2.0, -0.1)
    cap = Union(
        Cylinder(0.46, 0.86, TEAL, axis="z", ch=0.12).at(8.2, 0.95, -0.05),
        Cylinder(0.32, 0.1, BLACK, axis="z", ch=0.05).at(8.2, 0.95, 0.85),
    )
    sight = Union(
        Box(1.0, 0.2, 0.36, RUBBER, ch=0.06).at(7.15, 3.64, -0.05),
        Cylinder(0.18, 0.45, RUBBER, ch=0.04).at(6.85, 3.95, 0.12),
        Cylinder(0.18, 0.45, RUBBER, ch=0.04).at(7.5, 3.95, -0.22),
    )
    handle = tube([(8.0, 0.1, 0.85), (9.0, -0.25, 1.0), (8.7, -1.35, 1.05), (7.7, -1.1, 1.05)], 0.14)
    strut = tube([(6.3, 1.5, 0.7), (6.0, 0.9, 0.85), (5.4, 0.3, 0.95), (5.4, -0.2, 0.95)], 0.14)
    return Piece("rear_frame", Union(frame, mech, cap, sight, handle, strut), h=0.04, tris=560)


def big_number():
    return hi.number_plate()


def decals():
    side_up = (0, 1, 0)
    return [
        Decal(big_number(), (1.2, -0.45, LOWER_Z + 0.88), (1, 0, 0), side_up, (1.3, 1.3)),
        Decal(hi.text_image("R", 220, (30, 34, 34, 255), w=256, h=256), (7.3, 1.05, 0.67), (1, 0, 0), side_up, (0.7, 0.7)),
    ]


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
    # the sleeves are their own parts, so recoil can slide their coil texture
    parts += [hi.Part("upper_barrel_sleeve", "root", (-2.5, UPPER_Y, UPPER_Z)),
              hi.Part("lower_barrel_sleeve", "root", (-2.7, LOWER_Y, LOWER_Z))]
    tiles = {"fins": fins_tile(), "rounds": rounds_tile()}
    return Scene("liedersanger_lo", MATERIALS, pieces, decals(), texture_size=256, scale=0.25, parts=parts,
                 paths=paths, rust=0.7, tiles=tiles)
