"""Writes .obj + .mtl + .png."""

import os

from PIL import Image


def write_obj(out_dir, name, verts, normals, uvs, faces, texture):
    os.makedirs(out_dir, exist_ok=True)
    Image.fromarray(texture, "RGBA").save(os.path.join(out_dir, name + ".png"))
    with open(os.path.join(out_dir, name + ".mtl"), "w") as f:
        f.write(f"newmtl {name}\nKd 1 1 1\nKs 0 0 0\nmap_Kd {name}.png\n")
    lines = [f"mtllib {name}.mtl\n", f"o {name}\n"]
    lines += [f"v {x:.5f} {y:.5f} {z:.5f}\n" for x, y, z in verts]
    # obj puts v = 0 at the bottom of the image, the atlas at the top
    lines += [f"vt {u:.6f} {1 - v:.6f}\n" for u, v in uvs]
    lines += [f"vn {x:.4f} {y:.4f} {z:.4f}\n" for x, y, z in normals]
    lines.append(f"usemtl {name}\n")
    fi = faces + 1
    lines += [f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n" for a, b, c in fi]
    tmp = os.path.join(out_dir, name + ".obj.tmp")
    with open(tmp, "w") as f:
        f.writelines(lines)
    os.replace(tmp, os.path.join(out_dir, name + ".obj"))
