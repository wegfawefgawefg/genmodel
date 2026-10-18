"""Mixes a soundtrack for an animation from its shot times and the samples in ref/sounds.

    python tools/soundtrack.py liedersanger 18 out.wav

Every shot layers a boom, a crack, a low thump and the feed's clank, panned by barrel and
varied a little in pitch; spent cases tinkle down a moment later; a motor whine follows
the fire rate through the spin-up; the settle at the end gets a heavy impact.
"""

import os
import subprocess
import sys
import wave

import numpy as np
from scipy import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
SOUNDS = os.path.join(ROOT, "ref", "sounds")


def load(name, start=0.0, end=None, fade=0.05):
    """A mono sample cut from start to end seconds, faded out at its end."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", os.path.join(SOUNDS, name + ".mp3"),
                          "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).astype(np.float64)
    x = x[int(start * SR): int(end * SR) if end else None].copy()
    n = int(fade * SR)
    if n and len(x) > n:
        x[-n:] *= np.linspace(1, 0, n) ** 2
    return x / max(np.abs(x).max(), 1e-9)


def lowpass(x, hz):
    b, a = signal.butter(2, hz / (SR / 2))
    return signal.lfilter(b, a, x)


def pitched(x, speed):
    """Plays x at `speed` (1.2 = higher and shorter)."""
    t = np.arange(0, len(x) - 1, speed)
    return np.interp(t, np.arange(len(x)), x)


def place(mix, x, at, gain, pan):
    """Adds mono x into the stereo mix at `at` seconds, equal-power panned (-1 left, 1 right)."""
    i = int(at * SR)
    if i >= len(mix) or i + len(x) <= 0:
        return
    if i < 0:
        x, i = x[-i:], 0
    x = x[: len(mix) - i]
    ang = (pan + 1) * np.pi / 4
    mix[i: i + len(x), 0] += x * gain * np.cos(ang)
    mix[i: i + len(x), 1] += x * gain * np.sin(ang)


def anim_info(name):
    out = subprocess.run([os.path.join(ROOT, "build", "viewer"), f"out/{name}/{name}.obj", "--anim",
                          f"gen/models/{name}.anim.sexp", "--print-shots"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout
    length, shots, rate = 0.0, [], []
    for line in out.splitlines():
        f = line.split()
        if f[0] == "length":
            length = float(f[1])
        elif f[0] == "shot":
            shots.append((float(f[1]), int(f[2])))
        elif f[0] == "rate":
            rate.append((float(f[1]), float(f[2])))
    return length, shots, np.array(rate)


def room(mix):
    """A few early reflections and a short diffuse tail, so it isn't bone dry."""
    out = mix.copy()
    for delay, gain, ch in ((0.019, 0.22, 0), (0.027, 0.2, 1), (0.041, 0.14, 0), (0.053, 0.12, 1)):
        d = int(delay * SR)
        out[d:, ch] += mix[:-d, 1 - ch] * gain
    for delay, fb in ((0.0297, 0.62), (0.0371, 0.58), (0.0411, 0.55)):
        d = int(delay * SR)
        for ch in range(2):
            y = lowpass(mix[:, ch], 3500) * 0.08
            b = np.zeros(d + 1)
            b[0] = 1
            a = np.zeros(d + 1)
            a[0], a[d] = 1, -fb
            out[:, ch] += signal.lfilter(b, a, y)
    return out


def main():
    name, seconds, out_path = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    length, shots, rate = anim_info(name)
    rng = np.random.default_rng(7)

    boom = load("shot_50bmg", 0.2, 1.15, 0.45)
    crack = load("heavy_mg_50cal", 0.0, 0.11, 0.03)
    thump = lowpass(load("thump_cannon", 0.0, 1.1, 0.4), 160)
    thump /= np.abs(thump).max()
    clank = load("clank1", 0.09, None, 0.05)
    cycle = load("mechanical1", 0.33, None, 0.05)
    cases = [load("casing_5", 0.66, None, 0.1), load("casing_7", 0.0, None, 0.2)]
    settle = load("impact_heavy_4", 0.0, 1.6, 0.4)
    whine = load("gear_spin_loop", 0.0, None, 0.0)

    mix = np.zeros((int(seconds * SR), 2))
    loops = int(np.ceil(seconds / length))
    for k in range(loops):
        base = k * length
        for t, i in shots:
            at = base + t
            pan = -0.3 if i % 2 == 0 else 0.3  # top barrel left, bottom right
            sp = 1 + rng.uniform(-0.04, 0.04)
            place(mix, pitched(boom, sp), at, 0.3, pan)
            place(mix, pitched(crack, sp * 0.9), at, 0.3, pan)
            place(mix, thump, at, 0.45, 0)
            place(mix, pitched(clank, rng.uniform(0.92, 1.08)), at + 0.045, 0.28, 0.1)
            place(mix, pitched(cycle, rng.uniform(0.95, 1.1)), at + 0.07, 0.12, 0.1)
            # the case lands a beat later off to the side
            case = cases[rng.integers(len(cases))]
            place(mix, pitched(case, rng.uniform(0.85, 1.2)), at + rng.uniform(0.7, 1.05), rng.uniform(0.1, 0.2), 0.6)
        # the settle kick in the animation
        place(mix, settle, base + 7.0, 0.5, 0)

    # motor whine riding the fire rate, pitch and level up as it spins up
    tt = np.arange(len(mix)) / SR
    r = np.interp(tt % length, rate[:, 0], rate[:, 1])
    level = np.clip(r / 8, 0, 1)
    speed = 0.55 + 0.75 * level
    phase = np.cumsum(speed) % (len(whine) - 1)
    w = np.interp(phase, np.arange(len(whine)), whine) * (level ** 0.7) * 0.12
    mix[:, 0] += w
    mix[:, 1] += w

    mix = room(mix)
    mix = np.tanh(mix * 0.8) / np.tanh(0.8)
    mix *= 0.89 / max(np.abs(mix).max(), 1e-9)
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())
    print(f"wrote {out_path}: {seconds:.1f}s, {len(shots)} shots a loop")


if __name__ == "__main__":
    main()
