"""Finds pieces that float: bits of a part that touch nothing else in it.

    python tools/floating.py scoobee [gap_cm]

Each rig part's mesh (an .obj group) is split into its connected pieces; every piece's
surface is sampled densely and checked against the samples of all the part's other pieces.
A piece further than the gap from all of them is reported with where it sits.
"""

import os
import sys

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def groups(obj_path):
    verts, faces, cur = [], {}, "root"
    for line in open(obj_path):
        if line.startswith("v "):
            verts.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("g "):
            cur = line[2:].strip()
        elif line.startswith("f "):
            faces.setdefault(cur, []).append([int(t.split("/")[0]) - 1 for t in line.split()[1:4]])
    return np.array(verts, np.float32), {g: np.array(f) for g, f in faces.items()}


def sample(v, f, spacing):
    """Points over the triangles, about `spacing` apart."""
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    n = np.maximum(1, (area / (spacing * spacing)).astype(int))
    rng = np.random.default_rng(3)
    idx = np.repeat(np.arange(len(f)), n)
    r1, r2 = rng.random(len(idx)), rng.random(len(idx))
    flip = r1 + r2 > 1
    r1[flip], r2[flip] = 1 - r1[flip], 1 - r2[flip]
    pts = a[idx] + (b[idx] - a[idx]) * r1[:, None] + (c[idx] - a[idx]) * r2[:, None]
    return np.concatenate([pts, v[np.unique(f)]])


def main():
    name = sys.argv[1]
    gap = (float(sys.argv[2]) if len(sys.argv) > 2 else 2.0) / 100
    verts, parts = groups(os.path.join(ROOT, "out", name, name + ".obj"))
    found = 0
    for part, f in sorted(parts.items()):
        # pieces: faces linked by shared (or coincident) vertices
        key = np.round(verts / 1e-4).astype(np.int64)
        _, vid = np.unique(key, axis=0, return_inverse=True)
        ff = vid.reshape(-1)[f]
        e = np.concatenate([ff[:, [0, 1]], ff[:, [1, 2]]])
        n = vid.max() + 1
        k, lab = connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)), directed=False)
        face_lab = lab[ff[:, 0]]
        pieces = np.unique(face_lab)
        if len(pieces) < 2:
            continue
        samples = {p: sample(verts, f[face_lab == p], 0.012) for p in pieces}
        for p in pieces:
            others = np.concatenate([samples[q] for q in pieces if q != p])
            d, _ = cKDTree(others).query(samples[p], k=1)
            if d.min() > gap:
                c = samples[p].mean(0)
                found += 1
                print(f"  {part:16} piece of {int((face_lab == p).sum()):4d} tris at ({c[0]:+.2f} {c[1]:+.2f} {c[2]:+.2f}) "
                      f"floats {d.min() * 100:.1f} cm off")
    # every part must touch the part it hangs from (rig parents), or it floats as a whole
    parent = {}
    for line in open(os.path.join(ROOT, "out", name, name + ".rig.sexp")):
        f = line.replace("(", " ").replace(")", " ").split()
        if f and f[0] == "part" and "parent" in f:
            parent[f[1]] = f[f.index("parent") + 1]
    cloud = {p: sample(verts, fp, 0.012) for p, fp in parts.items()}
    for child, par in sorted(parent.items()):
        if child not in cloud or par not in cloud:
            continue
        d, _ = cKDTree(cloud[par]).query(cloud[child], k=1)
        if d.min() > gap:
            found += 1
            c = cloud[child].mean(0)
            print(f"  {child:16} hangs {d.min() * 100:.1f} cm off its parent {par} (at {c[0]:+.2f} {c[1]:+.2f} {c[2]:+.2f})")
    print(f"{found} floating pieces")


if __name__ == "__main__":
    main()
