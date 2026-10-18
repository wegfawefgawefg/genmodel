"""Hill-climbs pose knobs until parts stop passing through each other over the animation.

    python tools/declip.py scoobee [rounds]

Knobs come from gen/models/<name>.declip.sexp: rest rotations of parts, each within a range.
The cost is the summed penetration over the loop (tools/overlap.py) plus a penalty for
leaving the authored pose. Coordinate descent: each knob tries a step either way and keeps
whatever lowers the cost; steps shrink when nothing helps. The result lives in a marked
block of the anim file, so it can be read, edited or deleted by hand.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gen"))

from overlap import ROOT, Checker  # noqa: E402
from sexp import field, parse_sexp  # noqa: E402

BEGIN = "  ; declip: begin (written by tools/declip.py; rest rotations that stop clipping)"
END = "  ; declip: end"
AXES = {"x": "1 0 0", "y": "0 1 0", "z": "0 0 1"}


def read_block(anim):
    vals = {}
    m = re.search(re.escape(BEGIN) + r"(.*?)" + re.escape(END), anim, re.S)
    if m:
        for part, ax, deg in re.findall(r"\(rest (\S+) \(rot ([\d. -]+?) ([-\d.]+)\)\)", m.group(1)):
            axis = {v: k for k, v in AXES.items()}.get(ax.strip())
            if axis:
                vals[(part, axis)] = float(deg)
    return vals


def write_block(path, vals):
    anim = open(path).read()
    lines = [BEGIN] + [f"  (rest {p} (rot {AXES[a]} {v:.1f}))" for (p, a), v in sorted(vals.items()) if abs(v) > 0.05]
    lines.append(END)
    block = "\n".join(lines)
    if BEGIN in anim:
        anim = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: block, anim, flags=re.S)
    else:
        anim = anim.rstrip()
        assert anim.endswith(")")
        # the closing paren on its own line: the end marker is a comment
        anim = anim[:-1] + "\n\n" + block + "\n)\n"
    open(path, "w").write(anim)


def main():
    name = sys.argv[1]
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    spec = parse_sexp(open(os.path.join(ROOT, "gen", "models", name + ".declip.sexp")).read())[0]
    penalty = float(field(spec, "penalty", ["0.003"])[0])
    knobs = [(k[1], k[2], float(k[3]), float(k[4])) for k in spec if isinstance(k, list) and k[0] == "knob"]
    anim_path = os.path.join(ROOT, "gen", "models", name + ".anim.sexp")
    vals = read_block(open(anim_path).read())
    for p, a, lo, hi in knobs:
        vals.setdefault((p, a), 0.0)
    checker = Checker(name)

    def cost(v):
        write_block(anim_path, v)
        worst, total = checker.check(40)
        return total + penalty * sum(x * x for x in v.values()), worst

    best, worst = cost(vals)
    print(f"start {best:.3f}  ({len(worst)} clipping pairs)")
    step = 8.0
    for r in range(rounds):
        improved = False
        for p, a, lo, hi in knobs:
            for sign in (1, -1):
                trial = dict(vals)
                trial[(p, a)] = min(max(vals[(p, a)] + sign * step, lo), hi)
                if trial[(p, a)] == vals[(p, a)]:
                    continue
                c, w = cost(trial)
                if c < best - 1e-4:
                    best, vals, worst, improved = c, trial, w, True
                    print(f"  {p} {a} -> {vals[(p, a)]:+.1f}   cost {best:.3f}  ({len(w)} pairs)")
                    break
        if not improved:
            step *= 0.5
            print(f"round {r + 1}: no gain, step -> {step:.1f}")
        else:
            print(f"round {r + 1}: cost {best:.3f}")
    write_block(anim_path, vals)
    print("left:")
    for (a, b), (depth, t) in sorted(worst.items(), key=lambda kv: -kv[1][0]):
        print(f"  {a:14} x {b:14} {depth * 100:5.1f} cm at t={t:.2f}")


if __name__ == "__main__":
    main()
