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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000


def parse_sexp(text):
    """Nested lists of strings; ; starts a comment, "quoted" strings keep their spaces."""
    tokens, i = [], 0
    while i < len(text):
        c = text[i]
        if c == ";":
            while i < len(text) and text[i] != "\n":
                i += 1
        elif c in "()":
            tokens.append(c)
            i += 1
        elif c == '"':
            j = text.index('"', i + 1)
            tokens.append(text[i + 1 : j])
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < len(text) and not text[j].isspace() and text[j] not in '();"':
                j += 1
            tokens.append(text[i:j])
            i = j
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t)
    return stack[0]


def field(form, head, default=None):
    for f in form:
        if isinstance(f, list) and f and f[0] == head:
            return f[1:]
    return default


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
        # a motor's buzz (harmonics of 110 Hz) chopped by gear teeth at 24 Hz, with
        # bearing rumble; whole cycles in the clip so it loops cleanly
        tone = sum(np.sin(2 * np.pi * 110 * h * t + h) / h ** 1.3 for h in range(1, 14))
        teeth = 0.65 + 0.35 * np.sin(2 * np.pi * 24 * t) ** 8
        rumble = signal.lfilter(*signal.butter(2, 400 / (SR / 2)), rng.standard_normal(len(t)))
        whine = 0.25 * np.sin(2 * np.pi * 880 * t) * (0.8 + 0.2 * np.sin(2 * np.pi * 3 * t))
        return tone * teeth + rumble * 3 + whine
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
    if field(form, "room"):
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
