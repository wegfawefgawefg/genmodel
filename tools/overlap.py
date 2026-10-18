"""Finds parts that pass through each other over an animation.

    python tools/overlap.py scoobee [samples]

The viewer dumps every part's matrix at sample times; each part's surface points (from the
built .obj, thinned) are moved into place and tested against every other part's SDF in that
pose. A part and its parent meet at a joint by design, so those pairs are skipped.
"""

import importlib
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "gen"))

import sdf  # noqa: E402

JOINT_BALL = 0.3  # around a joint, a part and its parent overlap on purpose (knuckle in housing)


def surface_points(obj_path, keep=260):
    """Per group (rig part): its vertices and face centres in rest model space, thinned."""
    verts, groups, cur = [], {}, "root"
    for line in open(obj_path):
        if line.startswith("v "):
            verts.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("g "):
            cur = line[2:].strip()
        elif line.startswith("f "):
            idx = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
            groups.setdefault(cur, []).append(idx)
    verts = np.array(verts, np.float32)
    rng = np.random.default_rng(1)
    out = {}
    for name, faces in groups.items():
        f = np.array(faces)
        p = np.concatenate([verts[np.unique(f)], verts[f].mean(1)]).astype(np.float32)
        if len(p) > keep:
            p = p[rng.choice(len(p), keep, replace=False)]
        out[name] = p
    return out


class Checker:
    def __init__(self, name):
        self.name = name
        sdf.FACETS = 8
        scene = importlib.import_module("models." + name).build()
        self.bodies = {}
        for pc in scene.pieces:
            if not pc.free:
                self.bodies.setdefault(pc.part, []).append(pc.body)
        self.raw_bodies = self.bodies
        self.pts = surface_points(os.path.join(ROOT, "out", name, name + ".obj"))
        self.grounded = getattr(importlib.import_module("models." + name), "GROUNDED", False)
        # rest joint positions (each part's pivot) from the rig
        self.pivot = {}
        dy = 0.0
        for line in open(os.path.join(ROOT, "out", name, name + ".rig.sexp")):
            if line.startswith("; ground_dy"):
                dy = float(line.split()[2])
            f = line.replace("(", " ").replace(")", " ").split()
            if len(f) >= 6 and f[0] == "part" and f[2] == "pivot":
                self.pivot[f[1]] = np.array([float(x) for x in f[3:6]], np.float32)
        # the build may have stood the model on the ground: move the SDFs the same way
        if dy:
            self.bodies = {p: [n.at(0, dy, 0) for n in ns] for p, ns in self.bodies.items()}
        # rest bounding spheres for a quick reject
        self.sphere = {}
        for part, nodes in self.bodies.items():
            lo = np.min([n.bounds()[0] for n in nodes], 0)
            hi = np.max([n.bounds()[1] for n in nodes], 0)
            self.sphere[part] = ((lo + hi) * 0.5, float(np.linalg.norm(hi - lo)) * 0.5)

    def poses(self, samples):
        res = subprocess.run([os.path.join(ROOT, "build", "viewer"), f"out/{self.name}/{self.name}.obj", "--anim",
                              f"gen/models/{self.name}.anim.sexp", "--dump-bones", str(samples)], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        out, cur, parent_idx, order = [], None, {}, []
        for line in res.splitlines():
            f = line.split()
            if f[0] == "pose":
                cur = (float(f[1]), {})
                out.append(cur)
            elif f[0] == "bone":
                if f[1] not in parent_idx:
                    order.append(f[1])
                parent_idx[f[1]] = int(f[2])
                cur[1][f[1]] = np.array([float(x) for x in f[3:19]], np.float32).reshape(4, 4).T
        parent = {n: (order[i] if i >= 0 else "") for n, i in parent_idx.items()}
        return out, parent

    def check(self, samples=52):
        """{(a, b): (deepest penetration in m, time)} and the summed depth over all samples."""
        frames, parent = self.poses(samples)
        worst, total = {}, 0.0
        for t, bones in frames:
            centres = {}
            for b, (c, r) in self.sphere.items():
                if b in bones:
                    centres[b] = (bones[b][:3, :3] @ c + bones[b][:3, 3], r)
            for a, pa in self.pts.items():
                if a not in bones or a not in centres:
                    continue
                wa = None
                if self.grounded:
                    wa = pa @ bones[a][:3, :3].T + bones[a][:3, 3]
                    depth = float(-wa[:, 1].min())
                    if depth > 0.01:
                        total += depth
                        key = (a, "ground")
                        if depth > worst.get(key, (0, 0))[0]:
                            worst[key] = (depth, t)
                for b, nodes in self.bodies.items():
                    if b == a or b not in centres:
                        continue
                    # a ram's rod lives inside its cylinder
                    if "." in a and a.split(".")[0] == b.split(".")[0]:
                        continue
                    if np.linalg.norm(centres[a][0] - centres[b][0]) > centres[a][1] + centres[b][1]:
                        continue
                    if wa is None:
                        wa = pa @ bones[a][:3, :3].T + bones[a][:3, 3]
                    pts_a = wa
                    # a part and its parent meet at their joint by design: ignore a ball there
                    child = a if parent.get(a) == b else (b if parent.get(b) == a else None)
                    if child is not None and child in self.pivot:
                        j = bones[child][:3, :3] @ self.pivot[child] + bones[child][:3, 3]
                        pts_a = wa[np.linalg.norm(wa - j, axis=1) > JOINT_BALL]
                        if len(pts_a) == 0:
                            continue
                    inv = np.linalg.inv(bones[b])
                    q = (pts_a @ inv[:3, :3].T + inv[:3, 3]).astype(np.float32)
                    d = np.min([n.dist(q) for n in nodes], axis=0)
                    depth = float(-d.min())
                    if depth > 0.01:
                        total += depth
                        key = tuple(sorted((a, b)))
                        if depth > worst.get(key, (0, 0))[0]:
                            worst[key] = (depth, t)
        return worst, total


def main():
    name = sys.argv[1]
    samples = int(sys.argv[2]) if len(sys.argv) > 2 else 104
    worst, total = Checker(name).check(samples)
    if not worst:
        print("no overlaps deeper than 1 cm")
    for (a, b), (depth, t) in sorted(worst.items(), key=lambda kv: -kv[1][0]):
        print(f"  {a:14} x {b:14} {depth * 100:5.1f} cm at t={t:.2f}")
    print(f"total {total:.3f}")


if __name__ == "__main__":
    main()
