"""How alike two builds look: renders both from the same cameras (untextured clay, so only
the shape counts) and reports silhouette change and shading difference.

    python tools/lookalike.py out/a/a.obj out/b/b.obj
"""

import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS = [(-30, 10), (60, 20), (180, 5), (0, 80), (120, -15), (90, 0)]


def render(obj, out, yaw, pitch):
    subprocess.run([os.path.join(ROOT, "build", "viewer"), obj, "--capture", out, "--size", "960", "540", "--yaw", str(yaw),
                    "--pitch", str(pitch), "--zoom", "0.8", "--clay", "--reflect", "0", "--studio"],
                   cwd=ROOT, capture_output=True, check=True)


def main():
    a_obj, b_obj = sys.argv[1], sys.argv[2]
    tmp = tempfile.mkdtemp()
    sil, diff, changed = [], [], []
    for yaw, pitch in VIEWS:
        pa, pb = os.path.join(tmp, "a.png"), os.path.join(tmp, "b.png")
        render(a_obj, pa, yaw, pitch)
        render(b_obj, pb, yaw, pitch)
        a = np.asarray(Image.open(pa).convert("L")).astype(float)
        b = np.asarray(Image.open(pb).convert("L")).astype(float)
        ma, mb = a > 30, b > 30
        sil.append((ma ^ mb).sum() / max(ma.sum(), 1) * 100)
        m = ma | mb
        d = np.abs(a - b)[m]
        diff.append(d.mean())
        changed.append((d > 24).mean() * 100)
    tris = [sum(1 for l in open(os.path.join(ROOT, p)) if l.startswith("f ")) for p in (a_obj, b_obj)]
    print(f"{tris[0]} -> {tris[1]} tris ({100 * (1 - tris[1] / tris[0]):.0f}% fewer)   silhouette change {np.mean(sil):.2f}%"
          f"   shading diff {np.mean(diff):.1f}/255   pixels visibly changed {np.mean(changed):.1f}%")


if __name__ == "__main__":
    main()
