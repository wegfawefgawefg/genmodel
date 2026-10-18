// smoke sprites and ribbons: camera-facing quads built on the CPU each frame, sorted far to
// near, blended premultiplied (smoke covers, sparks with alpha 0 just add light)
#include "draw.hpp"

#include <GL/glcorearb.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>

namespace {

const char* fx_vs = R"(#version 330 core
layout(location = 0) in vec3 a_pos;
layout(location = 1) in vec2 a_uv;
layout(location = 2) in vec4 a_color;
uniform mat4 u_view;
uniform mat4 u_proj;
out vec2 v_uv;
out vec4 v_color;
void main() {
    v_uv = a_uv;
    v_color = a_color;
    gl_Position = u_proj * u_view * vec4(a_pos, 1.0);
}
)";

const char* fx_fs = R"(#version 330 core
in vec2 v_uv;
in vec4 v_color;
uniform sampler2D u_atlas;
out vec4 o_color;
void main() {
    vec4 t = texture(u_atlas, v_uv);
    o_color = vec4(v_color.rgb * t.rgb * t.a, v_color.a * t.a);
}
)";

struct FxVert {
    float x, y, z, u, v, r, g, b, a;
};

struct Quad {
    FxVert v[4];
    float depth;
};

const int tile_px = 128;
const int atlas_w = 512, atlas_h = 256; // 4 x 2 tiles

float hash2(int x, int y, int seed) {
    unsigned h = (unsigned)x * 374761393u + (unsigned)y * 668265263u + (unsigned)seed * 2246822519u;
    h = (h ^ (h >> 13)) * 1274126177u;
    return (float)((h ^ (h >> 16)) & 0xFFFFFF) / (float)0xFFFFFF;
}

float vnoise(float x, float y, int seed) {
    int ix = (int)std::floor(x), iy = (int)std::floor(y);
    float fx = x - ix, fy = y - iy;
    fx = fx * fx * (3 - 2 * fx);
    fy = fy * fy * (3 - 2 * fy);
    float a = hash2(ix, iy, seed), b = hash2(ix + 1, iy, seed);
    float c = hash2(ix, iy + 1, seed), d = hash2(ix + 1, iy + 1, seed);
    return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy;
}

float fbm(float x, float y, int seed) {
    float s = 0, amp = 0.5f;
    for (int o = 0; o < 5; o++) {
        s += amp * vnoise(x, y, seed + o * 7);
        x *= 2.03f, y *= 2.03f, amp *= 0.5f;
    }
    return s / 0.97f;
}

// tiles 0-2: billowy puffs, 3: soft glow dot, 4: a wisp band (alpha across u, streaks along v)
std::vector<unsigned char> make_atlas() {
    std::vector<unsigned char> px(atlas_w * atlas_h * 4, 0);
    for (int tile = 0; tile < 5; tile++) {
        int ox = (tile % 4) * tile_px, oy = (tile / 4) * tile_px;
        for (int y = 0; y < tile_px; y++) {
            for (int x = 0; x < tile_px; x++) {
                float u = (x + 0.5f) / tile_px, v = (y + 0.5f) / tile_px;
                float cx = u * 2 - 1, cy = v * 2 - 1;
                float r = std::sqrt(cx * cx + cy * cy);
                float lum = 1, alpha = 0;
                if (tile < 3) {
                    float n = fbm(u * 3.2f + tile * 5.1f, v * 3.2f, 3 + tile);
                    float billow = fbm(u * 7.0f, v * 7.0f + tile, 17 + tile);
                    alpha = (1 - r * r) * 1.5f - (1 - n) * 1.05f - (1 - billow) * 0.25f;
                    alpha = std::pow(std::clamp(alpha, 0.0f, 1.0f), 1.25f) * std::clamp((1 - r) * 4, 0.0f, 1.0f);
                    lum = 0.72f + 0.38f * (n - 0.5f) + 0.15f * (billow - 0.5f) + 0.12f * cy;
                } else if (tile == 3) {
                    alpha = std::exp(-r * r * 7);
                } else {
                    float d = (u - 0.5f) / 0.24f;
                    float streak = fbm(u * 5.0f, v * 2.0f, 41);
                    alpha = std::exp(-d * d) * (0.55f + 0.45f * streak);
                    lum = 0.9f + 0.1f * streak;
                }
                unsigned char* p = &px[((oy + y) * atlas_w + ox + x) * 4];
                unsigned char l = (unsigned char)(std::clamp(lum, 0.0f, 1.0f) * 255);
                p[0] = p[1] = p[2] = l;
                p[3] = (unsigned char)(std::clamp(alpha, 0.0f, 1.0f) * 255);
            }
        }
    }
    return px;
}

void tile_uv(int tile, float u, float v, float& tu, float& tv) {
    float pad = 1.5f / atlas_w;
    tu = ((tile % 4) + u) * tile_px / atlas_w;
    tv = ((tile / 4) + v) * tile_px / atlas_h;
    tu = std::clamp(tu, ((tile % 4) * tile_px) / (float)atlas_w + pad, ((tile % 4 + 1) * tile_px) / (float)atlas_w - pad);
}

Vec3 srgb(Vec3 c) {
    return {std::pow(std::max(c.x, 0.0f), 1 / 2.2f), std::pow(std::max(c.y, 0.0f), 1 / 2.2f),
            std::pow(std::max(c.z, 0.0f), 1 / 2.2f)};
}

FxVert vert(Vec3 p, int tile, float u, float v, Vec3 col, float alpha, float premul) {
    FxVert f;
    f.x = p.x, f.y = p.y, f.z = p.z;
    tile_uv(tile, u, v, f.u, f.v);
    f.r = col.x * premul, f.g = col.y * premul, f.b = col.z * premul, f.a = alpha;
    return f;
}

uint32_t compile_fx(GLenum kind, const char* src) {
    uint32_t s = glCreateShader(kind);
    glShaderSource(s, 1, &src, nullptr);
    glCompileShader(s);
    int ok = 0;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[2048];
        glGetShaderInfoLog(s, sizeof(log), nullptr, log);
        fprintf(stderr, "fx shader error: %s\n", log);
    }
    return s;
}

} // namespace

bool fx_init(Gpu& gpu) {
    uint32_t vs = compile_fx(GL_VERTEX_SHADER, fx_vs), fs = compile_fx(GL_FRAGMENT_SHADER, fx_fs);
    gpu.fx_program = glCreateProgram();
    glAttachShader(gpu.fx_program, vs);
    glAttachShader(gpu.fx_program, fs);
    glLinkProgram(gpu.fx_program);
    glDeleteShader(vs);
    glDeleteShader(fs);
    glGenVertexArrays(1, &gpu.fx_vao);
    glGenBuffers(1, &gpu.fx_vbo);
    glBindVertexArray(gpu.fx_vao);
    glBindBuffer(GL_ARRAY_BUFFER, gpu.fx_vbo);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(FxVert), (void*)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, sizeof(FxVert), (void*)(3 * sizeof(float)));
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, sizeof(FxVert), (void*)(5 * sizeof(float)));
    glBindVertexArray(0);

    std::vector<unsigned char> px = make_atlas();
    glGenTextures(1, &gpu.fx_atlas);
    glBindTexture(GL_TEXTURE_2D, gpu.fx_atlas);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, atlas_w, atlas_h, 0, GL_RGBA, GL_UNSIGNED_BYTE, px.data());
    glGenerateMipmap(GL_TEXTURE_2D);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    return true;
}

void fx_draw(const Gpu& gpu, const Pose& pose, const float* view, const float* proj, Vec3 eye) {
    if (pose.sprites.empty() && pose.ribbons.empty()) {
        return;
    }
    Vec3 right = {view[0], view[4], view[8]};
    Vec3 up = {view[1], view[5], view[9]};
    Vec3 back = {view[2], view[6], view[10]}; // toward the camera
    std::vector<Quad> quads;

    for (const FxSprite& s : pose.sprites) {
        float c = std::cos(s.angle), sn = std::sin(s.angle);
        Vec3 ax = (right * c + up * sn) * s.size;
        Vec3 ay = (up * c - right * sn) * s.size;
        Vec3 col = srgb(s.color);
        float premul = s.alpha > 0 ? s.alpha : 1.0f;
        Quad q;
        q.v[0] = vert(s.pos - ax - ay, s.tile, 0, 0, col, s.alpha, premul);
        q.v[1] = vert(s.pos + ax - ay, s.tile, 1, 0, col, s.alpha, premul);
        q.v[2] = vert(s.pos + ax + ay, s.tile, 1, 1, col, s.alpha, premul);
        q.v[3] = vert(s.pos - ax + ay, s.tile, 0, 1, col, s.alpha, premul);
        q.depth = dot(s.pos - eye, back);
        quads.push_back(q);
    }
    for (const FxRibbon& r : pose.ribbons) {
        Vec3 col = srgb(r.color);
        size_t n = r.pts.size();
        std::vector<Vec3> side(n);
        // a wide tangent window rides over small folds; the width never flips between
        // neighbours, which would twist a segment into a bow tie
        for (size_t i = 0; i < n; i++) {
            size_t lo = i >= 4 ? i - 4 : 0, hi = std::min(i + 4, n - 1);
            Vec3 t = r.pts[hi] - r.pts[lo];
            Vec3 sd = norm(cross(t, eye - r.pts[i]));
            if (i > 0 && dot(sd, side[i - 1]) < 0) {
                sd = sd * -1.0f;
            }
            side[i] = sd;
        }
        for (size_t i = 0; i < n; i++) {
            side[i] = side[i] * (r.width[i] * 0.5f);
        }
        for (size_t i = 0; i + 1 < n; i++) {
            if (r.alpha[i] < 0.002f && r.alpha[i + 1] < 0.002f) continue;
            float v0 = (float)i / (n - 1), v1 = (float)(i + 1) / (n - 1);
            Quad q;
            q.v[0] = vert(r.pts[i] - side[i], 4, 0, v0, col, r.alpha[i], r.alpha[i]);
            q.v[1] = vert(r.pts[i] + side[i], 4, 1, v0, col, r.alpha[i], r.alpha[i]);
            q.v[2] = vert(r.pts[i + 1] + side[i + 1], 4, 1, v1, col, r.alpha[i + 1], r.alpha[i + 1]);
            q.v[3] = vert(r.pts[i + 1] - side[i + 1], 4, 0, v1, col, r.alpha[i + 1], r.alpha[i + 1]);
            q.depth = dot((r.pts[i] + r.pts[i + 1]) * 0.5f - eye, back);
            quads.push_back(q);
        }
    }
    // far ones first
    std::sort(quads.begin(), quads.end(), [](const Quad& a, const Quad& b) { return a.depth < b.depth; });
    std::vector<FxVert> verts;
    verts.reserve(quads.size() * 6);
    for (const Quad& q : quads) {
        verts.insert(verts.end(), {q.v[0], q.v[1], q.v[2], q.v[0], q.v[2], q.v[3]});
    }

    glUseProgram(gpu.fx_program);
    glUniformMatrix4fv(glGetUniformLocation(gpu.fx_program, "u_view"), 1, GL_FALSE, view);
    glUniformMatrix4fv(glGetUniformLocation(gpu.fx_program, "u_proj"), 1, GL_FALSE, proj);
    glUniform1i(glGetUniformLocation(gpu.fx_program, "u_atlas"), 0);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, gpu.fx_atlas);
    glBindVertexArray(gpu.fx_vao);
    glBindBuffer(GL_ARRAY_BUFFER, gpu.fx_vbo);
    glBufferData(GL_ARRAY_BUFFER, verts.size() * sizeof(FxVert), verts.data(), GL_STREAM_DRAW);
    glEnable(GL_BLEND);
    glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
    glDepthMask(GL_FALSE);
    glDrawArrays(GL_TRIANGLES, 0, (int)verts.size());
    glDepthMask(GL_TRUE);
    glDisable(GL_BLEND);
    glBindVertexArray(0);
}
