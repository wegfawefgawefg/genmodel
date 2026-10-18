#pragma once

#include <cmath>

// small 3d math for rigid parts; matrices are column-major like OpenGL
struct Vec3 {
    float x = 0, y = 0, z = 0;
};

inline Vec3 operator+(Vec3 a, Vec3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
inline Vec3 operator-(Vec3 a, Vec3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
inline Vec3 operator*(Vec3 a, float k) { return {a.x * k, a.y * k, a.z * k}; }
inline float dot(Vec3 a, Vec3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
inline Vec3 cross(Vec3 a, Vec3 b) {
    return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x};
}
inline float len(Vec3 a) { return std::sqrt(dot(a, a)); }
inline Vec3 norm(Vec3 a) {
    float l = len(a);
    return l > 1e-12f ? a * (1.0f / l) : Vec3{0, 0, 0};
}

struct Mat4 {
    float m[16] = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1};
};

inline Mat4 operator*(const Mat4& a, const Mat4& b) {
    Mat4 r;
    for (int c = 0; c < 4; c++) {
        for (int row = 0; row < 4; row++) {
            float s = 0;
            for (int k = 0; k < 4; k++) {
                s += a.m[k * 4 + row] * b.m[c * 4 + k];
            }
            r.m[c * 4 + row] = s;
        }
    }
    return r;
}

inline Mat4 translate(Vec3 t) {
    Mat4 r;
    r.m[12] = t.x;
    r.m[13] = t.y;
    r.m[14] = t.z;
    return r;
}

inline Mat4 scale(float k) {
    Mat4 r;
    r.m[0] = r.m[5] = r.m[10] = k;
    return r;
}

// rotation by a rotation vector: axis * radians
inline Mat4 rotate(Vec3 rv) {
    float a = len(rv);
    Mat4 r;
    if (a < 1e-9f) {
        return r;
    }
    Vec3 k = rv * (1.0f / a);
    float c = std::cos(a), s = std::sin(a), t = 1 - c;
    r.m[0] = c + k.x * k.x * t;
    r.m[1] = k.y * k.x * t + k.z * s;
    r.m[2] = k.z * k.x * t - k.y * s;
    r.m[4] = k.x * k.y * t - k.z * s;
    r.m[5] = c + k.y * k.y * t;
    r.m[6] = k.z * k.y * t + k.x * s;
    r.m[8] = k.x * k.z * t + k.y * s;
    r.m[9] = k.y * k.z * t - k.x * s;
    r.m[10] = c + k.z * k.z * t;
    return r;
}

// a frame from three axis columns and an origin
inline Mat4 frame(Vec3 x, Vec3 y, Vec3 z, Vec3 o) {
    Mat4 r;
    r.m[0] = x.x, r.m[1] = x.y, r.m[2] = x.z;
    r.m[4] = y.x, r.m[5] = y.y, r.m[6] = y.z;
    r.m[8] = z.x, r.m[9] = z.y, r.m[10] = z.z;
    r.m[12] = o.x, r.m[13] = o.y, r.m[14] = o.z;
    return r;
}

// inverse of rotation + translation (+ uniform scale ignored)
inline Mat4 inverse_rigid(const Mat4& a) {
    Mat4 r;
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            r.m[j * 4 + i] = a.m[i * 4 + j];
        }
    }
    Vec3 t = {a.m[12], a.m[13], a.m[14]};
    r.m[12] = -(r.m[0] * t.x + r.m[4] * t.y + r.m[8] * t.z);
    r.m[13] = -(r.m[1] * t.x + r.m[5] * t.y + r.m[9] * t.z);
    r.m[14] = -(r.m[2] * t.x + r.m[6] * t.y + r.m[10] * t.z);
    return r;
}

inline Vec3 apply_point(const Mat4& a, Vec3 p) {
    return {a.m[0] * p.x + a.m[4] * p.y + a.m[8] * p.z + a.m[12],
            a.m[1] * p.x + a.m[5] * p.y + a.m[9] * p.z + a.m[13],
            a.m[2] * p.x + a.m[6] * p.y + a.m[10] * p.z + a.m[14]};
}

inline Vec3 apply_dir(const Mat4& a, Vec3 d) {
    return {a.m[0] * d.x + a.m[4] * d.y + a.m[8] * d.z, a.m[1] * d.x + a.m[5] * d.y + a.m[9] * d.z,
            a.m[2] * d.x + a.m[6] * d.y + a.m[10] * d.z};
}
