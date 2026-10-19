"""Exports a built model as a binary glTF (.glb) for game engines (Godot, Blender, ...).

    python tools/export_gltf.py out/name/name.obj out/name/name.glb

Every rig part becomes a node placed at its joint (pivot), parented like the rig, with its
mesh in the node's own space, so an engine can rotate and slide parts about their joints.
Materials keep their textures with nearest-neighbour filtering (the chunky look). Effect
parts (muzzle flashes, spent cases) are kept but scaled to nothing at rest, and flashes
use an unlit emissive material.
"""

import json
import os
import re
import struct
import sys

import numpy as np


def read_obj(path):
    v, vt, vn = [], [], []
    faces = []  # (material, group, [(vi, ti, ni) x3])
    mat, grp = "", "root"
    for line in open(path):
        if line.startswith("v "):
            v.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vt "):
            vt.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("vn "):
            vn.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("usemtl "):
            mat = line.split()[1]
        elif line.startswith("g "):
            grp = line[2:].strip()
        elif line.startswith("f "):
            corners = [tuple(int(i) - 1 for i in tok.split("/")) for tok in line.split()[1:4]]
            faces.append((mat, grp, corners))
    return np.array(v, np.float32), np.array(vt, np.float32), np.array(vn, np.float32), faces


def read_mtl(path):
    maps, cur = {}, None
    for line in open(path):
        f = line.split()
        if f and f[0] == "newmtl":
            cur = f[1]
        elif f and f[0] == "map_Kd" and cur:
            maps[cur] = f[1]
    return maps


def read_rig(path):
    parts = {}
    for line in open(path):
        m = re.match(r"\s*\(part (\S+) \(pivot ([-\d.e]+) ([-\d.e]+) ([-\d.e]+)\)(?: \(parent ([^)\s]+)\))?", line)
        if m:
            parts[m.group(1)] = (np.array([float(m.group(i)) for i in (2, 3, 4)], np.float32), m.group(5) or "")
    return parts


def is_fx(name):
    return name.endswith("_flash") or name.startswith("case.")


def main():
    obj_path, out_path = sys.argv[1], sys.argv[2]
    base = os.path.dirname(obj_path)
    stem = os.path.splitext(os.path.basename(obj_path))[0]
    v, vt, vn, faces = read_obj(obj_path)
    maps = read_mtl(os.path.join(base, stem + ".mtl"))
    rig = read_rig(os.path.join(base, stem + ".rig.sexp"))
    groups = sorted({g for _, g, _ in faces})
    for g in groups:
        rig.setdefault(g, (np.zeros(3, np.float32), "root" if g != "root" else ""))
    rig.setdefault("root", (np.zeros(3, np.float32), ""))

    blob = bytearray()

    def add_view(data, target=None):
        while len(blob) % 4:
            blob.append(0)
        off = len(blob)
        blob.extend(data)
        view = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target:
            view["target"] = target
        gl["bufferViews"].append(view)
        return len(gl["bufferViews"]) - 1

    gl = {"asset": {"version": "2.0", "generator": "genmodel export_gltf.py"}, "scene": 0, "scenes": [{"nodes": []}],
          "nodes": [], "meshes": [], "materials": [], "textures": [], "images": [], "samplers": [], "accessors": [],
          "bufferViews": [], "buffers": [], "extensionsUsed": ["KHR_materials_unlit"]}
    # nearest filtering, repeating (tiles wrap)
    gl["samplers"].append({"magFilter": 9728, "minFilter": 9728, "wrapS": 10497, "wrapT": 10497})

    mat_index = {}
    for name, img in maps.items():
        data = open(os.path.join(base, img), "rb").read()
        gl["images"].append({"bufferView": add_view(data), "mimeType": "image/png", "name": img})
        gl["textures"].append({"sampler": 0, "source": len(gl["images"]) - 1})
        mat = {"name": name, "pbrMetallicRoughness": {"baseColorTexture": {"index": len(gl["textures"]) - 1},
                                                      "metallicFactor": 0.0, "roughnessFactor": 0.85}}
        mat_index[name] = len(gl["materials"])
        gl["materials"].append(mat)
    # flashes: the same atlas, unlit and emissive
    atlas = mat_index.get(stem, 0)
    gl["materials"].append({"name": stem + "_flash", "pbrMetallicRoughness": {"baseColorTexture": {"index": atlas},
                                                                               "metallicFactor": 0.0},
                            "emissiveTexture": {"index": atlas}, "emissiveFactor": [1, 1, 1],
                            "extensions": {"KHR_materials_unlit": {}}})
    flash_mat = len(gl["materials"]) - 1

    def accessor(arr, kind, comp, target=None, minmax=False):
        a = {"bufferView": add_view(arr.tobytes(), target), "componentType": comp, "count": len(arr), "type": kind}
        if minmax:
            a["min"] = arr.min(0).tolist()
            a["max"] = arr.max(0).tolist()
        gl["accessors"].append(a)
        return len(gl["accessors"]) - 1

    # one mesh per part, one primitive per material, positions relative to the part's pivot
    node_of = {}
    for part in ["root"] + [g for g in rig if g != "root"]:
        pivot, parent = rig[part]
        node = {"name": part}
        ppivot = rig[parent][0] if parent else np.zeros(3, np.float32)
        node["translation"] = (pivot - ppivot).tolist()
        if is_fx(part):
            node["scale"] = [1e-4, 1e-4, 1e-4]
        prims = []
        for m in sorted({mt for mt, g, _ in faces if g == part}):
            corners = [c for mt, g, cs in faces if g == part and mt == m for c in cs]
            pos = np.array([v[c[0]] for c in corners], np.float32) - pivot
            nrm = np.array([vn[c[2]] for c in corners], np.float32)
            uv = np.array([vt[c[1]] for c in corners], np.float32)
            uv[:, 1] = 1 - uv[:, 1]  # glTF puts v = 0 at the top of the image
            idx = np.arange(len(corners), dtype=np.uint32)
            prims.append({"attributes": {"POSITION": accessor(pos, "VEC3", 5126, 34962, True),
                                         "NORMAL": accessor(nrm, "VEC3", 5126, 34962),
                                         "TEXCOORD_0": accessor(uv, "VEC2", 5126, 34962)},
                          "indices": accessor(idx, "SCALAR", 5125, 34963),
                          "material": flash_mat if part.endswith("_flash") else mat_index.get(m, 0)})
        if prims:
            gl["meshes"].append({"name": part, "primitives": prims})
            node["mesh"] = len(gl["meshes"]) - 1
        node_of[part] = len(gl["nodes"])
        gl["nodes"].append(node)
    for part, (pivot, parent) in rig.items():
        if part == "root":
            continue
        p = node_of[parent] if parent in node_of else node_of["root"]
        gl["nodes"][p].setdefault("children", []).append(node_of[part])
    gl["scenes"][0]["nodes"] = [node_of["root"]]

    while len(blob) % 4:
        blob.append(0)
    gl["buffers"].append({"byteLength": len(blob)})
    js = json.dumps(gl, separators=(",", ":")).encode()
    while len(js) % 4:
        js += b" "
    with open(out_path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))
    print(f"wrote {out_path}: {len(gl['nodes'])} nodes, {len(gl['meshes'])} meshes, {len(faces)} triangles")


if __name__ == "__main__":
    main()
