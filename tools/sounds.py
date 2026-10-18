"""Prepares a model's sound clips from its bank: python tools/sounds.py liedersanger

Reads gen/models/<name>.sound.sexp, and for every (sample ...) cuts, filters, fades and
roughens the source once, writing out/<name>/sounds/<sample>.wav (48 kHz mono float).
The viewer plays these clips; cues and triggers are read by the viewer itself.
"""

import os
import subprocess
import sys
import wave
import zlib

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gen"))
from sexp import field, parse_sexp  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000


def decode(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def room(x, amount):
    """A few reflections and a short diffuse tail, baked in so playback stays stateless."""
    tail = int(0.35 * SR)
    y = np.concatenate([x, np.zeros(tail)])
    out = y.copy()
    for delay, gain in ((0.017, 0.5), (0.029, 0.4), (0.043, 0.3), (0.061, 0.2)):
        d = int(delay * SR)
        out[d:] += y[:-d] * gain * amount
    b, a = signal.butter(1, 3500 / (SR / 2))
    soft = signal.lfilter(b, a, y) * amount * 0.5
    for delay, fb in ((0.0297, 0.6), (0.0371, 0.57), (0.0411, 0.54)):
        d = int(delay * SR)
        den = np.zeros(d + 1)
        den[0], den[d] = 1, -fb
        out += signal.lfilter([1.0], den, soft)
    # trim the silent end
    keep = np.flatnonzero(np.abs(out) > 1e-4)
    return out[: keep[-1] + 1] if len(keep) else out


def seamless(x, fade):
    """Crossfades the end into the start so the clip loops without a click."""
    n = int(fade * SR)
    head, tail = x[:n].copy(), x[-n:]
    ramp = np.linspace(0, 1, n)
    x = x[: len(x) - n].copy()
    x[:n] = head * ramp + tail * (1 - ramp)
    return x


def synth(kind, length, rng):
    """Made-up sounds: a geared motor whirr, smoke sizzle, a pneumatic hiss."""
    t = np.arange(int(length * SR)) / SR
    if kind == "whirr":
        # a heavy gear train: big teeth meshing ring low and long (with a fixed pattern of
        # uneven teeth, like worn gears), a growling motor underneath and some grind. At
        # low playback speed the teeth clunk apart; at speed they run into a deep churn.
        mesh = 40.0  # teeth per second at full speed; whole teeth per clip so it loops
        n = len(t)
        ping_t = np.arange(int(0.04 * SR)) / SR
        ping = sum(a * np.sin(2 * np.pi * f * ping_t) for a, f in ((1.0, 520), (0.6, 830), (0.35, 1400), (0.5, 260)))
        ping *= np.exp(-ping_t / 0.012)
        clicks = np.zeros(n)
        uneven = rng.uniform(0.55, 1.0, 24)  # a 24-tooth gear's wear, repeating
        for k in range(int(length * mesh)):
            i = int(k / mesh * SR)
            if i < n:
                clicks[i] += uneven[k % 24]
        out = signal.fftconvolve(clicks, ping)[:n]
        # motor: a buzzy low drone (harmonics of 55 Hz), rounded off above 600 Hz
        motor = sum(np.sin(2 * np.pi * 55 * h * t + 0.7 * h) / h for h in range(1, 12))
        motor = signal.lfilter(*signal.butter(2, 600 / (SR / 2)), motor)
        # grind: low noise pulsing with the teeth
        grind = signal.lfilter(*signal.butter(2, [120 / (SR / 2), 700 / (SR / 2)], "band"), rng.standard_normal(n))
        grind *= 0.5 + 0.5 * np.sin(2 * np.pi * mesh * t) ** 2
        return out + 0.55 * motor + 1.2 * grind + 0.2 * np.sin(2 * np.pi * mesh * 2 * t)
    noise = rng.standard_normal(len(t))
    if kind == "sizzle":
        # bright hiss that flutters, with sparse crackle pops
        hiss = signal.lfilter(*signal.butter(2, [2500 / (SR / 2), 9000 / (SR / 2)], "band"), noise)
        flutter = 0.6 + 0.4 * signal.lfilter(*signal.butter(1, 6 / (SR / 2)), rng.standard_normal(len(t))) * 20
        pops = (rng.random(len(t)) < 40 / SR) * rng.uniform(0.5, 1.5, len(t))
        crackle = signal.lfilter(*signal.butter(2, 1800 / (SR / 2), "high"), pops)
        crackle = signal.lfilter([1.0], [1, -0.93], crackle)
        return hiss * np.clip(flutter, 0.1, 1.5) + crackle * 1.5
    if kind == "hiss":
        # a vent letting go: loud at once, thinning as it dies
        band = signal.lfilter(*signal.butter(2, [900 / (SR / 2), 7000 / (SR / 2)], "band"), noise)
        return band * np.exp(-t * 2.2) * (1 - np.exp(-t * 200))
    raise ValueError("unknown synth " + kind)


def prepare(form, src_dir):
    name = form[1]
    rng = np.random.default_rng(zlib.crc32(name.encode()))
    if field(form, "synth"):
        length = float(field(form, "length", ["2"])[0])
        x = synth(field(form, "synth")[0], length + (0.1 if field(form, "loop") is not None else 0), rng)
        if field(form, "loop") is not None:
            x = seamless(x, 0.1)
    else:
        x = decode(os.path.join(src_dir, field(form, "file")[0]))
        cut = field(form, "cut", [])
        start = float(cut[0]) if cut else 0.0
        end = float(cut[1]) if len(cut) > 1 else None
        x = x[int(start * SR) : int(end * SR) if end else None].copy()
        if field(form, "loop") is not None:
            x = seamless(x, 0.15)
    if field(form, "highpass"):
        b, a = signal.butter(2, float(field(form, "highpass")[0]) / (SR / 2), "high")
        x = signal.lfilter(b, a, x)
    if field(form, "lowpass"):
        b, a = signal.butter(2, float(field(form, "lowpass")[0]) / (SR / 2))
        x = signal.lfilter(b, a, x)
    fade = field(form, "fade", [])
    if fade:
        n_in, n_out = int(float(fade[0]) * SR), int(float(fade[1]) * SR)
        if n_in:
            x[:n_in] *= np.linspace(0, 1, n_in)
        if n_out and n_out < len(x):
            x[-n_out:] *= np.linspace(1, 0, n_out) ** 2
    x /= max(np.abs(x).max(), 1e-9)
    # a tail would break a loop's seam
    if field(form, "room") and field(form, "loop") is None:
        x = room(x, float(field(form, "room")[0]))
        x /= max(np.abs(x).max(), 1e-9)
    x *= float(field(form, "gain", ["1"])[0])
    return name, x.astype(np.float32)


def write_wav(path, x):
    # 32-bit float wav (format 3); wave can't write that header, so build it here
    data = x.astype("<f4").tobytes()
    header = b"RIFF" + (36 + len(data)).to_bytes(4, "little") + b"WAVE"
    header += b"fmt " + (16).to_bytes(4, "little") + (3).to_bytes(2, "little") + (1).to_bytes(2, "little")
    header += SR.to_bytes(4, "little") + (SR * 4).to_bytes(4, "little") + (4).to_bytes(2, "little") + (32).to_bytes(2, "little")
    header += b"data" + len(data).to_bytes(4, "little")
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(header + data)
    os.replace(tmp, path)


def main():
    name = sys.argv[1]
    bank = parse_sexp(open(os.path.join(ROOT, "gen", "models", name + ".sound.sexp")).read())[0]
    src_dir = os.path.join(ROOT, field(bank, "dir", ["ref/sounds"])[0])
    out_dir = os.path.join(ROOT, "out", name, "sounds")
    os.makedirs(out_dir, exist_ok=True)
    for form in bank:
        if isinstance(form, list) and form and form[0] == "sample":
            sample, x = prepare(form, src_dir)
            write_wav(os.path.join(out_dir, sample + ".wav"), x)
            print(f"  {sample}: {len(x) / SR:.2f}s")
    print(f"wrote out/{name}/sounds")


if __name__ == "__main__":
    main()
