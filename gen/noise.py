"""Cheap 3d value noise for texture variation."""

import numpy as np

F = np.float32


def hash3(i, seed):
    # integer lattice -> [0, 1)
    h = (i[:, 0] * 73856093) ^ (i[:, 1] * 19349663) ^ (i[:, 2] * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(F) / F(0xFFFFFF)


def value_noise(p, seed=0):
    p = p.astype(F)
    i = np.floor(p).astype(np.int64)
    f = p - i
    u = f * f * (3 - 2 * f)
    out = np.zeros(len(p), F)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (u[:, 0] if dx else 1 - u[:, 0]) * (u[:, 1] if dy else 1 - u[:, 1]) * (u[:, 2] if dz else 1 - u[:, 2])
                out += w * hash3(i + np.array([dx, dy, dz]), seed)
    return out


def fbm(p, octaves=4, seed=0, lacunarity=2.03, gain=0.5):
    total = np.zeros(len(p), F)
    amp, norm = 1.0, 0.0
    q = p.astype(F)
    for o in range(octaves):
        total += amp * value_noise(q, seed + o * 17)
        norm += amp
        amp *= gain
        q = q * lacunarity
    return total / norm
