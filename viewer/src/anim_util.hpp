#pragma once

// small shared helpers for the animation evaluators
#include "anim.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

// integer hash -> [0, 1)
inline float hash01(uint32_t a, uint32_t b) {
    uint32_t h = a * 0x9E3779B1u ^ (b + 0x7F4A7C15u) * 0x85EBCA77u;
    h ^= h >> 15;
    h *= 0x2C1B3C6Du;
    h ^= h >> 12;
    h *= 0x297A2D39u;
    h ^= h >> 15;
    return (float)(h & 0xFFFFFF) / (float)0x1000000;
}

// smooth 1d value noise in [-1, 1]
inline float noise1(float x, uint32_t seed) {
    float i = std::floor(x);
    float f = x - i;
    float u = f * f * (3 - 2 * f);
    float a = hash01((uint32_t)(int32_t)i, seed) * 2 - 1;
    float b = hash01((uint32_t)(int32_t)i + 1, seed) * 2 - 1;
    return a + (b - a) * u;
}

inline float table_at(const std::vector<float>& tab, float dt, float t) {
    if (tab.empty()) {
        return 0;
    }
    float x = t / dt;
    int i = std::clamp((int)x, 0, (int)tab.size() - 2);
    float f = std::clamp(x - i, 0.0f, 1.0f);
    return tab[i] * (1 - f) + tab[i + 1] * f;
}

inline float drive(const Anim& a, const Drive& d, float t) {
    float v = 1;
    if (d.driver == Driver::rate) v = table_at(a.rate_table, a.table_dt, t);
    if (d.driver == Driver::heat) v = table_at(a.heat_table, a.table_dt, t);
    if (d.driver == Driver::idle) v = table_at(a.idle_table, a.table_dt, t);
    if (d.driver == Driver::curve && d.curve >= 0) v = table_at(a.curves[d.curve].table, a.table_dt, t);
    if (d.driver == Driver::smoulder) {
        float idle = table_at(a.idle_table, a.table_dt, t);
        v = table_at(a.heat_table, a.table_dt, t) * idle * idle;
    }
    v *= d.k;
    return d.eased ? ease(d.ease, std::clamp(v, 0.0f, 1.0f)) : v;
}

inline float wrap_time(const Anim& a, float t) {
    t = std::fmod(t, a.length);
    return t < 0 ? t + a.length : t;
}
