"""Liedersanger: over-under heavy machine gun with a hanging drum (ref/target.png).

Units are roughly the reference's pixels / 100, level gun, muzzles toward -x, up +y,
the visible (left) side toward +z.
"""

import math

from PIL import Image, ImageDraw, ImageFont

import sdf
from scene import Decal, Material, Piece, Scene, instanced
from sdf import Box, Cut, Cylinder, Prism, Repeat, Torus, Union, compose, segment, translate, turn

UNIT = 0.08

TEAL, WHITE, RED, GUNMETAL, BRASS, BLACK, STEEL, LENS, RUBBER = range(9)

MATERIALS = [
    Material("teal", (100, 200, 188), 0.35, "paint", (196, 206, 196)),
    Material("white", (226, 229, 226), 0.35, "paint", (140, 142, 140)),
    Material("red", (204, 42, 36), 0.35, "paint", (190, 180, 170)),
    Material("gunmetal", (52, 46, 38), 0.65, "metal"),
    Material("brass", (156, 124, 62), 0.75, "metal"),
    Material("black", (30, 30, 33), 0.3, "paint", (96, 96, 96)),
    Material("steel", (104, 98, 88), 0.7, "metal"),
    Material("lens", (255, 40, 30), 0.9, "glow"),
    Material("rubber", (22, 22, 24), 0.1, "rubber"),
]

UPPER_Y, UPPER_Z = 1.15, -0.1
LOWER_Y, LOWER_Z = -0.6, 0.3

DRUM_C = (4.55, -3.0, -0.55)
DRUM_TILT = 30.0
DRUM_LEN = 2.65  # half length
DRUM_R = 1.95


def barrel(name, y, z, muzzle_x, spring_x0):
    """Barrel along -x from the housing: nut, recoil spring, jacket, bands, muzzle brake."""
    rear = -1.0
    tube = Cylinder(0.2, (rear - spring_x0 + 0.1) * 0.5, GUNMETAL, r_edge=0.02).at((rear + spring_x0) * 0.5, 0, 0)
    thin_len = spring_x0 - muzzle_x - 1.0
    thin = Cylinder(0.17, thin_len * 0.5, GUNMETAL).at(muzzle_x + 1.0 + thin_len * 0.5, 0, 0)
    jacket = Cylinder(0.25, 0.9, GUNMETAL, r_edge=0.04).at(spring_x0 - 1.1, 0, 0)
    nut = Cylinder(0.42, 0.22, STEEL, r_edge=0.05, ch=0.04).at(rear - 0.15, 0, 0)
    collar = Cylinder(0.36, 0.16, GUNMETAL, r_edge=0.03).at(spring_x0 - 0.1, 0, 0)
    n_rings = int((rear - 0.35 - spring_x0) / 0.16)
    rings = [translate(spring_x0 + 0.15 + 0.16 * i, y, z) for i in range(n_rings)]
    spring = instanced(name + "_spring", Torus(0.35, 0.085, GUNMETAL), rings, h=0.012, tris=40)
    coil_core = Cylinder(0.27, (rear - spring_x0) * 0.5, GUNMETAL).at((rear + spring_x0) * 0.5, 0, 0)
    band_x = muzzle_x + 2.3
    bands = Union(
        Cylinder(0.24, 0.07, BRASS, r_edge=0.02).at(band_x, 0, 0),
        Cylinder(0.24, 0.07, BRASS, r_edge=0.02).at(band_x + 0.35, 0, 0),
        Cylinder(0.27, 0.09, BRASS, r_edge=0.02).at(spring_x0 - 0.38, 0, 0),
    )
    # muzzle brake: a block with a bore and side ports
    brake = Box(0.55, 0.42, 0.4, GUNMETAL, r=0.12).at(muzzle_x + 0.55, 0, 0)
    brake = Cut(brake, Cylinder(0.2, 0.7, GUNMETAL).at(muzzle_x + 0.3, 0, 0), ch=0.05)
    brake = Cut(brake, Box(0.13, 0.25, 0.6, GUNMETAL).at(muzzle_x + 0.78, 0, 0), ch=0.03)
    brake = Union(brake, Torus(0.22, 0.05, STEEL).at(muzzle_x - 0.02, 0, 0))
    neck = Cylinder(0.22, 0.25, GUNMETAL, r_edge=0.03).at(muzzle_x + 1.25, 0, 0)
    # gas tube under the barrel
    gas = segment((spring_x0 - 1.7, -0.34, 0.08), (rear, -0.34, 0.08), 0.075, GUNMETAL, 0.02)
    gas_block = Union(
        Cylinder(0.27, 0.07, STEEL, r_edge=0.02).at(spring_x0 - 1.75, 0, 0),
        Box(0.07, 0.2, 0.1, STEEL, r=0.03).at(spring_x0 - 1.75, -0.24, 0.06),
    )

    body = Union(tube, thin, jacket, nut, collar, coil_core, bands, brake, neck, gas, gas_block).at(0, y, z)
    pc = Piece(name, body, h=0.024, tris=1300)
    # knurled grip band on the gas tube
    knurl = Repeat(Box(0.012, 0.2, 0.2, GUNMETAL).at(0, -0.36, 0.05), (0.05, 0, 0), 16).at(spring_x0 - 0.6, y, z)
    pc.cut(knurl)
    return [pc, spring]


def upper_housing():
    profile = [(-1.3, 0.95), (-1.3, 2.4), (-1.15, 2.78), (-0.8, 2.98), (3.3, 3.05), (3.8, 3.35), (6.1, 3.4), (6.1, 2.35),
               (2.15, 2.35), (2.0, 1.25), (1.85, 0.75), (0.85, 0.62), (0.55, 0.92)]
    shell = Prism(profile, 0.75, WHITE, r=0.22).at(0, 0, UPPER_Z)
    # round boss over the barrel-return cap on the side
    boss = Cylinder(0.52, 0.8, TEAL, axis="z", r_edge=0.12).at(1.35, 1.1, UPPER_Z)
    cap = Union(
        Cylinder(0.38, 0.1, GUNMETAL, axis="z", r_edge=0.04).at(1.35, 1.1, UPPER_Z + 0.82),
        Cylinder(0.16, 0.06, STEEL, axis="z", r_edge=0.03).at(1.35, 1.1, UPPER_Z + 0.92),
    )
    lens = Cylinder(0.13, 0.08, LENS, r_edge=0.04).at(-1.33, 2.62, UPPER_Z)
    lens_ring = Torus(0.14, 0.035, STEEL).at(-1.32, 2.62, UPPER_Z)
    latch = Box(0.22, 0.2, 0.08, WHITE, r=0.05).at(-0.45, 2.3, UPPER_Z + 0.75)
    top_knob = Cylinder(0.12, 0.07, STEEL, axis="y", r_edge=0.03).at(5.1, 3.45, UPPER_Z + 0.4)
    front_plug = Union(
        Cylinder(0.12, 0.08, STEEL, r_edge=0.03).at(-1.36, 1.55, UPPER_Z + 0.35),
        Cylinder(0.1, 0.08, STEEL, r_edge=0.03).at(-1.36, 1.3, UPPER_Z - 0.3),
    )
    body = Union(Union(shell, boss, k=0.12), cap, lens, lens_ring, latch, top_knob, front_plug)

    # teal sweeps up from the boss toward the back; a red band over the top
    sweep = [(0.45, 0.3), (0.62, 0.9), (1.3, 1.62), (2.5, 2.12), (3.15, 2.6), (3.4, 3.7), (7.0, 3.7), (7.0, 0.3)]
    teal = Prism(sweep, 2.0, TEAL)
    stripe = Box(0.3, 0.75, 1.2, RED).rot("z", -6).at(3.0, 3.1, UPPER_Z)
    body = sdf.Paint(sdf.Paint(body, teal, TEAL), stripe, RED)
    pc = Piece("upper_housing", body, h=0.035, tris=1800)
    # panel seams and screws, baked into the texture only
    pc.cut(Box(0.02, 1.4, 1.0, WHITE).at(-0.2, 1.9, UPPER_Z))
    pc.cut(Box(2.5, 0.02, 1.0, WHITE).at(3.6, 2.55, UPPER_Z))
    for x, yy in ((-0.9, 1.15), (0.3, 2.6), (2.3, 2.5), (3.9, 2.5), (5.6, 2.55), (-0.9, 2.65)):
        pc.cut(Torus(0.05, 0.015, STEEL, axis="z").at(x, yy, UPPER_Z + 0.75))
    return pc


def lower_housing():
    profile = [(-1.85, -0.25), (-1.85, 0.1), (-1.55, 0.38), (2.3, 0.38), (2.3, -1.0), (1.4, -1.5),
               (-0.2, -1.52), (-1.0, -1.35)]
    shell = Prism(profile, 0.78, TEAL, r=0.18).at(0, 0, LOWER_Z)
    boss = Cylinder(0.5, 0.82, TEAL, axis="z", r_edge=0.14).at(-0.65, -0.85, LOWER_Z)
    cap = Union(
        Cylinder(0.36, 0.1, GUNMETAL, axis="z", r_edge=0.04).at(-0.65, -0.85, LOWER_Z + 0.85),
        Cylinder(0.14, 0.06, STEEL, axis="z", r_edge=0.03).at(-0.65, -0.85, LOWER_Z + 0.95),
    )
    plate = Box(0.75, 0.6, 0.05, TEAL, r=0.04).at(1.2, -0.45, LOWER_Z + 0.8)
    clamp = Box(0.18, 0.12, 0.25, GUNMETAL, ch=0.04).at(-1.25, 0.48, LOWER_Z + 0.45)
    body = Union(Union(shell, boss, k=0.15), cap, plate, clamp)
    pc = Piece("lower_housing", body, h=0.035, tris=1100)
    for x, yy in ((0.5, 0.05), (1.9, 0.05), (1.9, -0.95), (0.5, -0.95)):
        pc.cut(Torus(0.05, 0.015, STEEL, axis="z").at(x, yy, LOWER_Z + 0.85))
    return pc


def core():
    """The dark receiver between the housings: feed cover, gear, chute down to the drum."""
    block = Box(2.0, 1.85, 0.62, GUNMETAL, ch=0.08).at(4.05, 0.55, 0)
    cover = Box(1.15, 0.55, 0.72, GUNMETAL, ch=0.1).at(3.95, 1.85, 0.05)
    gear = Union(
        Cylinder(0.7, 0.12, GUNMETAL, axis="z", r_edge=0.04).at(2.75, 0.45, 0.68),
        Cylinder(0.45, 0.1, STEEL, axis="z", r_edge=0.03).at(2.75, 0.45, 0.82),
        Cylinder(0.15, 0.08, GUNMETAL, axis="z", r_edge=0.03).at(2.75, 0.45, 0.94),
    )
    chute = Box(1.0, 0.75, 0.55, GUNMETAL, ch=0.08).rot("z", -12).at(4.6, -1.35, 0.1)
    rear_rail = Box(1.6, 0.4, 0.5, GUNMETAL, ch=0.06).at(7.0, 2.55, -0.05)
    hose = sdf.Capsule((5.3, 1.9, 0.55), (6.6, 1.95, 0.6), 0.09, RUBBER)
    red_clip = Box(0.18, 0.1, 0.1, RED, r=0.03).at(7.6, 2.3, 0.55)
    fittings = Union(
        sdf.Capsule((2.4, -0.9, 0.8), (2.9, -0.5, 0.85), 0.12, TEAL),
        sdf.Capsule((2.9, -0.5, 0.85), (3.4, -0.6, 0.75), 0.12, TEAL),
        Cylinder(0.17, 0.08, TEAL, axis="z", r_edge=0.04).at(2.4, -0.9, 0.86),
        sdf.bolt(0.1, 0.1, STEEL).at(2.4, -0.9, 0.93),
    )
    body = Union(block, cover, gear, chute, rear_rail, hose, red_clip, fittings)
    pc = Piece("core", body, h=0.03, tris=2200)
    pc.cut(Box(1.5, 0.02, 1.0, GUNMETAL).at(4.6, 1.05, 0))
    pc.cut(Torus(0.3, 0.02, GUNMETAL, axis="z").at(2.75, 0.45, 0.92))
    at_gear = translate(2.75, 0.45, 0.68)
    spots = [compose(at_gear, compose(turn("z", 20 * i), translate(0.72, 0, 0))) for i in range(18)]
    teeth = instanced("gear_teeth", Box(0.08, 0.06, 0.1, GUNMETAL, ch=0.02), spots, h=0.01, tris=12)
    ribs = instanced("cover_ribs", Box(0.05, 0.08, 0.68, STEEL, r=0.025),
                     [translate(3.05 + 0.22 * i, 2.42, 0.05) for i in range(8)], h=0.012, tris=24)
    return [pc, teeth, ribs]


def belt():
    """Cartridge belt from the feed down into the drum."""
    top = (4.2, 1.15)
    bottom = (5.1, -3.55)
    n = 25
    step = ((bottom[0] - top[0]) / (n - 1), (bottom[1] - top[1]) / (n - 1), 0)
    link = Union(
        Box(0.72, 0.07, 0.24, STEEL, ch=0.03),
        Box(0.09, 0.09, 0.3, STEEL, ch=0.02).at(-0.45, 0, 0),
        Box(0.09, 0.09, 0.3, STEEL, ch=0.02).at(0.35, 0, 0),
        Cylinder(0.075, 0.25, BRASS, r_edge=0.03).at(0.95, 0.03, 0),
        sdf.Cone(0.075, 0.025, 0.1, BRASS).at(1.28, 0.03, 0),
    )
    spots = [translate(top[0] + step[0] * i, top[1] + step[1] * i, 1.12) for i in range(n)]
    # stop where the belt meets the drum
    can = Cylinder(DRUM_R + 0.2, DRUM_LEN, BLACK).rot("z", DRUM_TILT).at(*DRUM_C)
    spots = [sp for sp in spots if can.dist(sp[1][None, :])[0] > 0.05]
    links = instanced("belt", link, spots, h=0.012, tris=90)
    # guide that carries the belt off the feed
    guide = Box(0.75, 0.3, 0.45, GUNMETAL, ch=0.06).at(top[0] + 0.1, top[1] + 0.25, 0.85)
    return [links, Piece("belt_guide", guide, h=0.03, tris=60)]


def drum():
    """The hanging drum: black canister, teal front housing with a ringed face, rails."""
    L, R = DRUM_LEN, DRUM_R
    can = Cylinder(R, L, BLACK, r_edge=0.12)
    front = Cylinder(R + 0.16, 0.9, TEAL, r_edge=0.14).at(-L + 0.85, 0, 0)
    front = Cut(front, Cylinder(R - 0.3, 0.3, GUNMETAL).at(-L - 0.12, 0, 0), k=0.04, cut_mat=True)
    face = Union(
        Cylinder(R - 0.35, 0.06, GUNMETAL, r_edge=0.02).at(-L + 0.12, 0, 0),
        Torus(R - 0.65, 0.05, GUNMETAL).at(-L + 0.08, 0, 0),
        Torus(R - 0.95, 0.05, GUNMETAL).at(-L + 0.05, 0, 0),
        Torus(R - 1.2, 0.05, GUNMETAL).at(-L + 0.02, 0, 0),
        Cylinder(0.25, 0.06, STEEL, r_edge=0.03).at(-L - 0.02, 0, 0),
    )
    trim = Torus(R + 0.17, 0.045, RED).at(-L + 1.55, 0, 0)
    back = Cylinder(R + 0.08, 0.14, TEAL, r_edge=0.06).at(L - 0.1, 0, 0)
    rails = Union(
        segment((-L + 1.6, -1.45, 1.52), (L + 0.6, -1.45, 1.52), 0.1, TEAL, 0.03),
        segment((-L + 1.6, 0.7, 1.98), (L + 0.2, 0.7, 1.98), 0.09, TEAL, 0.03),
        segment((L + 0.6, -1.45, 1.52), (L + 0.6, 1.0, 1.2), 0.1, TEAL, 0.03),
    )
    body = Union(can, front, face, trim, back, rails)
    body = body.rot("z", DRUM_TILT).at(*DRUM_C)
    place = compose(translate(*DRUM_C), turn("z", DRUM_TILT))
    spots = [compose(place, compose(translate(-L + 0.7, 0, 0), compose(turn("x", 15 + 60 * i), translate(0, R + 0.13, 0))))
             for i in range(6)]
    bolts = instanced("drum_bolts", sdf.bolt(0.12, 0.14, STEEL, axis="y"), spots, h=0.01, tris=40)
    return [Piece("drum", body, h=0.035, tris=2400), bolts]


def rear_frame():
    """Open bracket at the back: top bar, back post, lower boss; the receiver shows through."""
    top_bar = Prism([(5.9, 2.95), (6.15, 3.45), (8.75, 3.45), (8.75, 2.95)], 0.78, TEAL, r=0.12).at(0, 0, -0.05)
    post = Prism([(7.95, 3.2), (8.75, 3.2), (8.75, 0.2), (8.35, -0.3), (7.95, 0.2)], 0.8, TEAL, r=0.15).at(0, 0, -0.05)
    boss = Prism([(6.5, 0.0), (6.6, 1.55), (8.2, 1.65), (8.3, 0.1), (7.6, -0.35)], 0.72, TEAL, r=0.2).at(0, 0, -0.05)
    frame = Union(top_bar, post, boss, k=0.12)
    mech = Union(
        Box(0.9, 0.45, 0.55, GUNMETAL, ch=0.06).at(7.0, 2.0, -0.1),
        Cylinder(0.12, 0.9, STEEL, r_edge=0.03).at(7.0, 2.55, 0.5),
    )
    cap = Union(
        Cylinder(0.42, 0.85, TEAL, axis="z", r_edge=0.12).at(8.2, 0.95, -0.05),
        Cylinder(0.3, 0.08, BLACK, axis="z", r_edge=0.04).at(8.2, 0.95, 0.83),
    )
    sight = Union(
        Box(1.0, 0.18, 0.35, BLACK, ch=0.04).at(7.15, 3.62, -0.05),
        Cylinder(0.14, 0.45, BLACK, r_edge=0.03).at(6.75, 3.88, 0.15),
        Cylinder(0.14, 0.45, BLACK, r_edge=0.03).at(7.55, 3.88, -0.2),
        Cylinder(0.1, 0.04, STEEL, r_edge=0.02).at(8.02, 3.88, -0.2),
    )
    handle = Union(
        segment((8.0, 0.1, 0.85), (8.55, -0.45, 1.0), 0.09, TEAL, 0.03),
        segment((8.55, -0.45, 1.0), (8.3, -1.25, 1.05), 0.09, TEAL, 0.03),
        segment((8.3, -1.25, 1.05), (7.7, -1.1, 1.05), 0.09, TEAL, 0.03),
    )
    strut = Union(
        segment((6.3, 1.5, 0.7), (5.4, -0.2, 0.95), 0.1, TEAL, 0.03),
        segment((6.7, 1.3, 0.7), (6.2, -0.9, 0.95), 0.08, TEAL, 0.03),
        Box(0.35, 0.5, 0.05, TEAL, r=0.03).rot("z", 25).at(6.15, 0.35, 0.85),
    )
    body = Union(frame, mech, cap, sight, handle, strut)
    pc = Piece("rear_frame", body, h=0.03, tris=1600)
    for x, yy in ((6.85, 0.2), (8.5, 3.15), (6.4, 3.15), (8.5, 0.35)):
        pc.cut(Torus(0.05, 0.015, STEEL, axis="z").at(x, yy, 0.73))
    return pc


def text_image(text, size, color, font="DejaVuSans-Bold.ttf", w=1024, h=256, stretch=1.0):
    path = "/usr/share/fonts/truetype/dejavu/" + font
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(path, size)
    box = d.textbbox((0, 0), text, font=f)
    d.text(((w - (box[2] - box[0])) / 2 - box[0], (h - (box[3] - box[1])) / 2 - box[1]), text, font=f, fill=color)
    return img


def number_plate():
    """The stencilled 33 with its red corner tick."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf", 470)
    d.text((30, -20), "33", font=f, fill=(92, 62, 40, 235))
    # stencil bridges
    for x in (150, 380):
        d.rectangle((x - 7, 40, x + 7, 500), fill=(0, 0, 0, 0))
    d.rectangle((6, 30, 90, 54), fill=(204, 42, 36, 255))
    d.rectangle((6, 30, 30, 120), fill=(204, 42, 36, 255))
    return img


def decals():
    side_up = (0, 1, 0)
    a = math.radians(DRUM_TILT)
    axis = (math.cos(a), math.sin(a), 0)
    across = (-math.sin(a), math.cos(a), 0)
    cx, cy, cz = DRUM_C
    drum_text = Image.new("RGBA", (1024, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(drum_text)
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 76)
    d.text((40, 30), "GEWICHT DER TROMMEL", font=f, fill=(225, 225, 220, 240))
    d.text((40, 130), "73 KG", font=f, fill=(225, 225, 220, 240))
    return [
        Decal(text_image("Liedersänger", 118, (40, 40, 44, 255)), (2.3, 2.72, UPPER_Z + 0.75), (1, 0, 0), side_up, (1.6, 0.4)),
        Decal(number_plate(), (1.2, -0.45, LOWER_Z + 0.85), (1, 0, 0), side_up, (1.2, 1.2)),
        Decal(text_image("R", 200, (30, 34, 34, 255), w=256, h=256), (7.3, 1.05, 0.67), (1, 0, 0), side_up, (0.5, 0.5)),
        Decal(drum_text, (cx + 0.5 * axis[0] - 0.2 * across[0], cy + 0.5 * axis[1] - 0.2 * across[1], cz + 1.6),
              axis, across, (2.6, 0.65), depth=0.5),
        Decal(text_image("NICHT TRETEN", 110, (204, 42, 36, 230)),
              (cx - 1.8 * axis[0] + 1.3 * across[0], cy - 1.8 * axis[1] + 1.3 * across[1], cz + 1.0),
              axis, across, (1.1, 0.25), depth=0.8),
    ]


def build():
    pieces = [
        *barrel("upper_barrel", UPPER_Y, UPPER_Z, -7.9, -3.9),
        *barrel("lower_barrel", LOWER_Y, LOWER_Z, -8.9, -4.3),
        upper_housing(),
        lower_housing(),
        *core(),
        *belt(),
        *drum(),
        rear_frame(),
    ]
    return Scene("liedersanger", MATERIALS, pieces, decals(), texture_size=2048, scale=0.25)
