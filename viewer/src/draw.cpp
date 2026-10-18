#include "draw.hpp"

#include <GL/glcorearb.h>

#include <algorithm>
#include <vector>
#include <cmath>
#include <cstdio>
#include <cstring>

namespace {

const char* model_vs = R"(#version 330 core
layout(location = 0) in vec3 a_pos;
layout(location = 1) in vec3 a_nrm;
layout(location = 2) in vec2 a_uv;
layout(location = 3) in float a_part;
layout(location = 4) in float a_layer;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform mat4 u_bones[128];
uniform vec3 u_glow[128];
uniform vec2 u_uvoff[128];
out vec3 v_nrm;
out vec3 v_view_pos;
out vec2 v_uv;
out vec3 v_glow;
out vec3 v_world;
flat out float v_layer;
void main() {
    int part = int(a_part + 0.5);
    mat4 bone = u_bones[part];
    vec4 wp = bone * vec4(a_pos, 1.0);
    v_world = wp.xyz;
    vec4 vp = u_view * wp;
    v_view_pos = vp.xyz;
    v_nrm = mat3(u_view) * (mat3(bone) * a_nrm);
    v_layer = a_layer;
    v_uv = a_layer > 0.5 ? a_uv + u_uvoff[part] : a_uv;
    v_glow = u_glow[part];
    gl_Position = u_proj * vp;
}
)";

// lights live in view space, so orbiting turns the model under a fixed studio rig
const char* model_fs = R"(#version 330 core
in vec3 v_nrm;
in vec3 v_view_pos;
in vec2 v_uv;
in vec3 v_glow;
in vec3 v_world;
flat in float v_layer;
uniform mat4 u_view;
uniform mat4 u_light_vp;
uniform sampler2D u_shadow;
uniform int u_moody;
uniform vec3 u_key_world;

// how lit by the key light: 1 in the open, 0 in shadow (3x3 filtered)
float key_visible(vec3 n_world) {
    vec4 lp = u_light_vp * vec4(v_world, 1.0);
    vec3 p = lp.xyz / lp.w * 0.5 + 0.5;
    if (p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0) return 1.0;
    float bias = 0.002 + 0.004 * (1.0 - abs(dot(n_world, u_key_world)));
    vec2 texel = 1.0 / vec2(textureSize(u_shadow, 0));
    float lit = 0.0;
    for (int y = -1; y <= 1; y++)
        for (int x = -1; x <= 1; x++)
            lit += (p.z - bias <= texture(u_shadow, p.xy + vec2(x, y) * texel * 1.5).r) ? 1.0 : 0.0;
    return lit / 9.0;
}
uniform sampler2D u_tex;
uniform sampler2D u_tile0, u_tile1, u_tile2;
uniform sampler2D u_env;
uniform float u_reflect;
uniform int u_mode; // 0 textured, 1 clay, 2 uv checker, 3 wire, 4 additive glow
out vec4 o_color;
void main() {
    if (u_mode == 3) {
        o_color = vec4(0.05, 0.9, 1.0, 1.0);
        return;
    }
    vec4 t = v_layer < 0.5 ? texture(u_tex, v_uv)
           : v_layer < 1.5 ? texture(u_tile0, v_uv)
           : v_layer < 2.5 ? texture(u_tile1, v_uv) : texture(u_tile2, v_uv);
    if (u_mode == 4) {
        // flashes: the texture is the flame colour, the view angle thins the edges
        // white-hot where it faces you, deep orange at the grazing edges
        float facing = abs(dot(normalize(v_nrm), normalize(-v_view_pos)));
        vec3 edge = vec3(1.0, 0.22, 0.02);
        vec3 flame = mix(edge, t.rgb * vec3(1.0, 0.95, 0.85), facing * facing);
        o_color = vec4(flame * (0.45 + 1.6 * facing) + v_glow, 1.0);
        return;
    }
    vec3 albedo = pow(t.rgb, vec3(2.2));
    float shine = t.a;
    if (u_mode == 1) {
        albedo = vec3(0.45);
        shine = 0.3;
    } else if (u_mode == 2) {
        vec2 c = floor(v_uv * 32.0);
        float k = mod(c.x + c.y, 2.0);
        albedo = mix(vec3(0.1), vec3(0.8), k) * vec3(v_uv, 0.6);
        shine = 0.0;
    }
    vec3 n = normalize(v_nrm);
    if (!gl_FrontFacing) {
        n = -n;
    }
    vec3 eye = normalize(-v_view_pos);

    vec3 key_dir = normalize(vec3(-0.5, 0.75, 0.6));
    vec3 fill_dir = normalize(vec3(0.8, 0.1, 0.3));
    vec3 rim_dir = normalize(vec3(0.2, 0.4, -1.0));
    vec3 key_col = vec3(1.0, 0.96, 0.9) * 2.4;
    vec3 fill_col = vec3(0.35, 0.5, 0.7) * 0.7;
    vec3 rim_col = vec3(0.6, 0.9, 1.0) * 1.1;
    float shade_key = 1.0;
    if (u_moody == 1) {
        // one hard warm key from high above, fixed in the world; a faint cool bounce from
        // below-behind; a thin rim; almost no ambient
        mat3 to_view = mat3(u_view);
        key_dir = normalize(to_view * u_key_world);
        fill_dir = normalize(to_view * normalize(vec3(-0.5, -0.35, -0.6)));
        key_col = vec3(1.0, 0.92, 0.8) * 4.6;
        fill_col = vec3(0.3, 0.42, 0.6) * 0.1;
        rim_col = vec3(0.6, 0.8, 1.0) * 0.55;
        shade_key = key_visible(normalize(transpose(to_view) * n));
    }

    // hemisphere ambient, sky above and dark floor below
    float up = n.y * 0.5 + 0.5;
    vec3 ambient = mix(vec3(0.05, 0.05, 0.06), vec3(0.22, 0.25, 0.3), up);
    if (u_moody == 1) ambient = mix(vec3(0.003, 0.003, 0.004), vec3(0.022, 0.025, 0.03), up);

    float nk = max(dot(n, key_dir), 0.0) * shade_key;
    float nf = max(dot(n, fill_dir), 0.0);
    vec3 diffuse = albedo * (ambient + key_col * nk + fill_col * nf);

    // shiny bits get a tight highlight, matte bits a broad soft one
    float power = mix(12.0, 90.0, shine);
    vec3 h = normalize(key_dir + eye);
    float spec = pow(max(dot(n, h), 0.0), power) * (0.04 + 0.9 * shine) * (power + 8.0) / 25.0;
    float rim = pow(1.0 - max(dot(n, eye), 0.0), 3.0) * max(dot(n, rim_dir) + 0.4, 0.0);

    vec3 col = diffuse + key_col * spec * nk + rim_col * rim * (0.15 + 0.35 * shine);
    // the old trick for chrome and gloss: a sphere-mapped picture of a world, looked up by
    // the view-space reflection, masked by how shiny the texel is, stronger at grazing angles
    vec3 r = reflect(-eye, n);
    float m = 2.0 * sqrt(r.x * r.x + r.y * r.y + (r.z + 1.0) * (r.z + 1.0));
    vec3 env = pow(texture(u_env, r.xy / m + 0.5).rgb, vec3(2.2));
    if (u_moody == 1) env *= 0.25 + 0.75 * shade_key; // reflections dim in shadow too
    float grazing = pow(1.0 - max(dot(n, eye), 0.0), 2.0);
    col = col * (1.0 - 0.25 * u_reflect * shine) + env * u_reflect * (0.08 + 1.4 * pow(shine, 1.5)) * (0.5 + 0.5 * grazing) * mix(vec3(1.0), albedo * 2.5 + 0.2, 0.3);
    // heat and lamps: emissive on top of the lighting; dark metal shows heat most,
    // and a hot part's own lighting fades under the glow
    float dark = 1.0 - clamp(dot(albedo, vec3(0.33)) * 3.0, 0.0, 1.0);
    vec3 emit = v_glow * (0.12 + 0.88 * dark * dark);
    col = col * (1.0 - clamp(dot(emit, vec3(0.6)), 0.0, 0.85)) + emit;
    if (u_moody == 1) {
        // gentler highlight roll-off, then an S-curve: lit tops stay bright, shadows go deep
        col = col / (1.0 + col * 0.12);
        vec3 g = clamp(pow(col, vec3(1.0 / 2.2)), 0.0, 1.0);
        g = mix(g, g * g * (3.0 - 2.0 * g), 0.55);
        o_color = vec4(g, 1.0);
        return;
    }
    col = col / (1.0 + col * 0.25);
    o_color = vec4(pow(col, vec3(1.0 / 2.2)), 1.0);
}
)";

const char* depth_fs = R"(#version 330 core
void main() {}
)";

// full-screen gradient behind the model
const char* back_vs = R"(#version 330 core
out vec2 v_p;
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    v_p = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.999, 1.0);
}
)";

const char* back_fs = R"(#version 330 core
in vec2 v_p;
out vec4 o_color;
void main() {
    float d = length((v_p - vec2(0.5, 0.55)) * vec2(1.6, 1.0));
    vec3 c = mix(vec3(0.075, 0.08, 0.09), vec3(0.012, 0.012, 0.016), clamp(d * 1.3, 0.0, 1.0));
    o_color = vec4(c, 1.0);
}
)";

// the ground for walking models: a big quad at y = 0 with a concrete-ish grid that scrolls
const char* ground_vs = R"(#version 330 core
uniform mat4 u_view;
uniform mat4 u_proj;
uniform float u_size;
out vec3 v_world;
void main() {
    // two triangles: (-1,-1) (1,-1) (-1,1) and (1,-1) (1,1) (-1,1)
    vec2 c = vec2((gl_VertexID == 1 || gl_VertexID == 3 || gl_VertexID == 4) ? 1.0 : -1.0,
                  (gl_VertexID == 2 || gl_VertexID == 4 || gl_VertexID == 5) ? 1.0 : -1.0);
    v_world = vec3(c.x * u_size, 0.0, c.y * u_size);
    gl_Position = u_proj * u_view * vec4(v_world, 1.0);
}
)";

const char* ground_fs = R"(#version 330 core
in vec3 v_world;
uniform float u_scroll;
uniform float u_period;
uniform float u_size;
uniform vec3 u_center;
uniform mat4 u_light_vp;
uniform sampler2D u_shadow;
uniform int u_moody;
out vec4 o_color;
float line(float x, float w) {
    float f = abs(fract(x) - 0.5);
    return smoothstep(0.5 - w, 0.5, f);
}
void main() {
    vec2 p = vec2(v_world.x, v_world.z + u_scroll) / u_period;
    float g = max(line(p.x, 0.02), line(p.y, 0.02));
    float fine = max(line(p.x * 4.0, 0.03), line(p.y * 4.0, 0.03)) * 0.35;
    float d = length(v_world.xz - u_center.xz) / u_size;
    float fade = 1.0 - smoothstep(0.25, 0.95, d);
    vec3 c = vec3(0.16, 0.16, 0.15) + vec3(0.12) * max(g, fine);
    if (u_moody == 1) {
        vec4 lp = u_light_vp * vec4(v_world, 1.0);
        vec3 sp = lp.xyz / lp.w * 0.5 + 0.5;
        float lit = 1.0;
        if (sp.x > 0.0 && sp.x < 1.0 && sp.y > 0.0 && sp.y < 1.0) {
            vec2 texel = 1.0 / vec2(textureSize(u_shadow, 0));
            lit = 0.0;
            for (int y = -1; y <= 1; y++)
                for (int x = -1; x <= 1; x++)
                    lit += (sp.z - 0.003 <= texture(u_shadow, sp.xy + vec2(x, y) * texel * 2.0).r) ? 1.0 : 0.0;
            lit /= 9.0;
        }
        c *= (0.25 + 0.75 * lit) * 0.75;
    }
    o_color = vec4(mix(vec3(0.03, 0.032, 0.036), pow(c, vec3(1.0 / 2.2)), fade), 1.0);
}
)";

uint32_t compile(GLenum kind, const char* src) {
    uint32_t s = glCreateShader(kind);
    glShaderSource(s, 1, &src, nullptr);
    glCompileShader(s);
    int ok = 0;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[2048];
        glGetShaderInfoLog(s, sizeof(log), nullptr, log);
        fprintf(stderr, "shader error: %s\n", log);
    }
    return s;
}

uint32_t link(const char* vs, const char* fs) {
    uint32_t p = glCreateProgram();
    uint32_t a = compile(GL_VERTEX_SHADER, vs);
    uint32_t b = compile(GL_FRAGMENT_SHADER, fs);
    glAttachShader(p, a);
    glAttachShader(p, b);
    glLinkProgram(p);
    glDeleteShader(a);
    glDeleteShader(b);
    int ok = 0;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[2048];
        glGetProgramInfoLog(p, sizeof(log), nullptr, log);
        fprintf(stderr, "link error: %s\n", log);
        return 0;
    }
    return p;
}

// column-major 4x4
void mat_identity(float* m) {
    memset(m, 0, 16 * sizeof(float));
    m[0] = m[5] = m[10] = m[15] = 1.0f;
}

void mat_perspective(float* m, float fovy, float aspect, float near_z, float far_z) {
    float f = 1.0f / std::tan(fovy * 0.5f);
    memset(m, 0, 16 * sizeof(float));
    m[0] = f / aspect;
    m[5] = f;
    m[10] = (far_z + near_z) / (near_z - far_z);
    m[11] = -1.0f;
    m[14] = 2.0f * far_z * near_z / (near_z - far_z);
}

void mat_ortho(float* m, float r, float near_z, float far_z) {
    memset(m, 0, 16 * sizeof(float));
    m[0] = 1.0f / r;
    m[5] = 1.0f / r;
    m[10] = -2.0f / (far_z - near_z);
    m[14] = -(far_z + near_z) / (far_z - near_z);
    m[15] = 1.0f;
}

void mat_mul(float* out, const float* a, const float* b) {
    float r[16];
    for (int c = 0; c < 4; c++)
        for (int row = 0; row < 4; row++) {
            float s = 0;
            for (int k = 0; k < 4; k++) s += a[k * 4 + row] * b[c * 4 + k];
            r[c * 4 + row] = s;
        }
    memcpy(out, r, sizeof(r));
}

// view matrix looking from eye at target with +Y up
void mat_look_at(float* m, const float* eye, const float* target) {
    float f[3] = {target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]};
    float fl = std::sqrt(f[0] * f[0] + f[1] * f[1] + f[2] * f[2]);
    for (float& x : f) {
        x /= fl;
    }
    float up[3] = {0, 1, 0};
    float s[3] = {f[1] * up[2] - f[2] * up[1], f[2] * up[0] - f[0] * up[2],
                  f[0] * up[1] - f[1] * up[0]};
    float sl = std::sqrt(s[0] * s[0] + s[1] * s[1] + s[2] * s[2]);
    for (float& x : s) {
        x /= sl;
    }
    float u[3] = {s[1] * f[2] - s[2] * f[1], s[2] * f[0] - s[0] * f[2], s[0] * f[1] - s[1] * f[0]};
    mat_identity(m);
    m[0] = s[0];
    m[4] = s[1];
    m[8] = s[2];
    m[1] = u[0];
    m[5] = u[1];
    m[9] = u[2];
    m[2] = -f[0];
    m[6] = -f[1];
    m[10] = -f[2];
    m[12] = -(s[0] * eye[0] + s[1] * eye[1] + s[2] * eye[2]);
    m[13] = -(u[0] * eye[0] + u[1] * eye[1] + u[2] * eye[2]);
    m[14] = f[0] * eye[0] + f[1] * eye[1] + f[2] * eye[2];
}

} // namespace

// a sphere map of a made-up place: bright sky above, a hot horizon, blue-grey building
// silhouettes, a sun glint, dark ground below. Indexed by view-space reflection direction.
static void make_env(Gpu& gpu) {
    const int n = 256;
    std::vector<unsigned char> px(n * n * 4);
    for (int y = 0; y < n; y++) {
        for (int x = 0; x < n; x++) {
            float u = (x + 0.5f) / n * 2 - 1, v = 1 - (y + 0.5f) / n * 2;
            float rr = u * u + v * v;
            float rgb[3] = {0, 0, 0};
            if (rr <= 1) {
                // the reflected direction this texel stands for
                float z = 1 - 2 * rr;
                float s = std::sqrt(std::max(0.0f, 1 - z * z)) / std::max(std::sqrt(rr), 1e-6f);
                float dx = u * s, dy = v * s;
                float h = dy; // up component
                float sky = std::clamp(h * 1.6f, 0.0f, 1.0f);
                float horizon = std::exp(-h * h * 60.0f);
                for (int c = 0; c < 3; c++) {
                    float top[3] = {0.55f, 0.66f, 0.8f}, low[3] = {0.95f, 0.9f, 0.82f}, ground[3] = {0.16f, 0.14f, 0.12f};
                    rgb[c] = h > 0 ? low[c] + (top[c] - low[c]) * sky : ground[c] * (1 + h);
                    rgb[c] += horizon * 0.25f;
                }
                // building silhouettes along the horizon
                float az = std::atan2(dx, z);
                float bld = 0.12f + 0.1f * std::fabs(std::sin(az * 7.3f)) + 0.08f * std::fabs(std::sin(az * 17.0f + 1.0f));
                if (h > 0 && h < bld) {
                    for (int c = 0; c < 3; c++) rgb[c] = rgb[c] * 0.45f + 0.08f * (c == 2 ? 1.3f : 1.0f);
                }
                // a sun glint high on one side
                float sx = dx - 0.45f, sy = dy - 0.62f;
                float sun = std::exp(-(sx * sx + sy * sy) * 120.0f);
                for (int c = 0; c < 3; c++) rgb[c] += sun * 1.2f;
            }
            for (int c = 0; c < 3; c++) px[(y * n + x) * 4 + c] = (unsigned char)(std::clamp(std::pow(rgb[c], 1 / 2.2f), 0.0f, 1.0f) * 255);
            px[(y * n + x) * 4 + 3] = 255;
        }
    }
    glGenTextures(1, &gpu.env);
    glBindTexture(GL_TEXTURE_2D, gpu.env);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, n, n, 0, GL_RGBA, GL_UNSIGNED_BYTE, px.data());
    glGenerateMipmap(GL_TEXTURE_2D);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
}

bool gpu_init(Gpu& gpu) {
    gpu.program = link(model_vs, model_fs);
    gpu.back_program = link(back_vs, back_fs);
    if (!gpu.program || !gpu.back_program) {
        return false;
    }
    glGenVertexArrays(1, &gpu.vao);
    glGenVertexArrays(1, &gpu.empty_vao);
    glGenBuffers(1, &gpu.vbo);
    glGenBuffers(1, &gpu.ibo);
    glGenTextures(1, &gpu.texture);
    gpu.ground_program = link(ground_vs, ground_fs);
    gpu.shadow_program = link(model_vs, depth_fs);
    const int shadow_size = 2048;
    glGenTextures(1, &gpu.shadow_tex);
    glBindTexture(GL_TEXTURE_2D, gpu.shadow_tex);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT24, shadow_size, shadow_size, 0, GL_DEPTH_COMPONENT, GL_FLOAT, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glGenFramebuffers(1, &gpu.shadow_fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, gpu.shadow_fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, gpu.shadow_tex, 0);
    glDrawBuffer(GL_NONE);
    glReadBuffer(GL_NONE);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    make_env(gpu);
    return fx_init(gpu);
}

void gpu_upload(Gpu& gpu, Model& model, const Rig& rig) {
    // obj groups -> rig parts (unknown groups ride root)
    std::vector<int> group_part(model.groups.size(), 0);
    for (size_t g = 0; g < model.groups.size(); g++) {
        int p = find_part(rig, model.groups[g]);
        group_part[g] = p >= 0 && p < max_parts ? p : 0;
    }
    for (size_t i = 0; i < model.verts.size(); i++) {
        model.verts[i].part = (float)group_part[model.vertex_group[i]];
    }
    // opaque triangles first, additive ones after
    std::vector<uint32_t> opaque, additive;
    for (size_t i = 0; i + 2 < model.indices.size(); i += 3) {
        int p = (int)model.verts[model.indices[i]].part;
        std::vector<uint32_t>& dst = rig.parts[p].additive ? additive : opaque;
        dst.insert(dst.end(), {model.indices[i], model.indices[i + 1], model.indices[i + 2]});
    }
    gpu.additive_first = (int)opaque.size();
    opaque.insert(opaque.end(), additive.begin(), additive.end());

    glBindVertexArray(gpu.vao);
    glBindBuffer(GL_ARRAY_BUFFER, gpu.vbo);
    glBufferData(GL_ARRAY_BUFFER, model.verts.size() * sizeof(Vertex), model.verts.data(), GL_STATIC_DRAW);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, gpu.ibo);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, opaque.size() * sizeof(uint32_t), opaque.data(), GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(Vertex), (void*)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(Vertex), (void*)(3 * sizeof(float)));
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, sizeof(Vertex), (void*)(6 * sizeof(float)));
    glEnableVertexAttribArray(3);
    glVertexAttribPointer(3, 1, GL_FLOAT, GL_FALSE, sizeof(Vertex), (void*)(8 * sizeof(float)));
    glEnableVertexAttribArray(4);
    glVertexAttribPointer(4, 1, GL_FLOAT, GL_FALSE, sizeof(Vertex), (void*)(9 * sizeof(float)));
    glBindVertexArray(0);

    // texture with mips and anisotropy so panel lines hold up at a glance
    glBindTexture(GL_TEXTURE_2D, gpu.texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, model.texture.w, model.texture.h, 0, GL_RGBA,
                 GL_UNSIGNED_BYTE, model.texture.rgba.data());
    glGenerateMipmap(GL_TEXTURE_2D);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, model.nearest ? GL_NEAREST : GL_LINEAR);
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY, model.nearest ? 1.0f : 8.0f);

    // repeating tiles, wrapping so their uvs can slide forever
    for (int i = 0; i < 3; i++) {
        if (!gpu.tiles[i]) glGenTextures(1, &gpu.tiles[i]);
        const Image* img = i < (int)model.tiles.size() ? &model.tiles[i] : &model.texture;
        glBindTexture(GL_TEXTURE_2D, gpu.tiles[i]);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, img->w, img->h, 0, GL_RGBA, GL_UNSIGNED_BYTE, img->rgba.data());
        glGenerateMipmap(GL_TEXTURE_2D);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, model.nearest ? GL_NEAREST : GL_LINEAR);
    }

    gpu.index_count = (int)model.indices.size();
    memcpy(gpu.center, model.center, sizeof(gpu.center));
    gpu.radius = model.radius;
}

// the key light's depth map: the model seen from high above, so it can shade itself and the ground
static void shadow_pass(const Gpu& gpu, const Pose& pose, Vec3 key, float* light_vp) {
    GLint prev = 0;
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &prev);
    float r = gpu.radius * 1.6f;
    float target[3] = {gpu.center[0], gpu.center[1], gpu.center[2]};
    float eye[3] = {target[0] + key.x * gpu.radius * 3, target[1] + key.y * gpu.radius * 3, target[2] + key.z * gpu.radius * 3};
    float view[16], proj[16];
    mat_look_at(view, eye, target);
    mat_ortho(proj, r, 0.05f, gpu.radius * 7);
    mat_mul(light_vp, proj, view);
    glBindFramebuffer(GL_FRAMEBUFFER, gpu.shadow_fbo);
    glViewport(0, 0, 2048, 2048);
    glClear(GL_DEPTH_BUFFER_BIT);
    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LESS);
    glUseProgram(gpu.shadow_program);
    glUniformMatrix4fv(glGetUniformLocation(gpu.shadow_program, "u_view"), 1, GL_FALSE, view);
    glUniformMatrix4fv(glGetUniformLocation(gpu.shadow_program, "u_proj"), 1, GL_FALSE, proj);
    int n_bones = std::min((int)pose.bones.size(), max_parts);
    glUniformMatrix4fv(glGetUniformLocation(gpu.shadow_program, "u_bones"), n_bones, GL_FALSE, pose.bones[0].m);
    glBindVertexArray(gpu.vao);
    glEnable(GL_POLYGON_OFFSET_FILL);
    glPolygonOffset(2.0f, 4.0f);
    glDrawElements(GL_TRIANGLES, gpu.additive_first, GL_UNSIGNED_INT, nullptr);
    glDisable(GL_POLYGON_OFFSET_FILL);
    glBindVertexArray(0);
    glBindFramebuffer(GL_FRAMEBUFFER, prev);
}

void gpu_draw(const Gpu& gpu, const Camera& cam, const DrawOptions& opt, const Pose& pose, int width, int height) {
    Vec3 key = norm(Vec3{0.38f, 1.0f, 0.28f});
    float light_vp[16];
    if (opt.moody) {
        shadow_pass(gpu, pose, key, light_vp);
    }
    glViewport(0, 0, width, height);
    glClearColor(0, 0, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

    // background
    glDisable(GL_DEPTH_TEST);
    glUseProgram(gpu.back_program);
    glBindVertexArray(gpu.empty_vao);
    glDrawArrays(GL_TRIANGLES, 0, 3);

    // camera on a sphere around the model
    float aspect = (float)width / (float)height;
    float fovy = 0.42f;
    float dist = gpu.radius / std::sin(fovy * 0.5f) * 0.72f * cam.zoom;
    float cp = std::cos(cam.pitch);
    float dir[3] = {cp * std::sin(cam.yaw), std::sin(cam.pitch), cp * std::cos(cam.yaw)};
    float right[3] = {std::cos(cam.yaw), 0, -std::sin(cam.yaw)};
    float up[3] = {-std::sin(cam.pitch) * std::sin(cam.yaw), cp,
                   -std::sin(cam.pitch) * std::cos(cam.yaw)};
    float target[3];
    float eye[3];
    for (int i = 0; i < 3; i++) {
        target[i] = gpu.center[i] + (cam.pan_x * right[i] + cam.pan_y * up[i]) * gpu.radius;
        eye[i] = target[i] + dir[i] * dist;
    }
    float view[16];
    float proj[16];
    mat_look_at(view, eye, target);
    mat_perspective(proj, fovy, aspect, dist * 0.05f, dist + gpu.radius * 4.0f);

    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LESS);
    glDisable(GL_CULL_FACE);
    glUseProgram(gpu.program);
    glUniformMatrix4fv(glGetUniformLocation(gpu.program, "u_view"), 1, GL_FALSE, view);
    glUniformMatrix4fv(glGetUniformLocation(gpu.program, "u_proj"), 1, GL_FALSE, proj);
    glUniform1i(glGetUniformLocation(gpu.program, "u_tex"), 0);
    int n_bones = std::min((int)pose.bones.size(), max_parts);
    glUniformMatrix4fv(glGetUniformLocation(gpu.program, "u_bones"), n_bones, GL_FALSE, pose.bones[0].m);
    glUniform3fv(glGetUniformLocation(gpu.program, "u_glow"), n_bones, &pose.glow[0].x);
    std::vector<float> uvoff((size_t)n_bones * 2, 0.0f);
    for (int i = 0; i < n_bones && i < (int)pose.uv.size(); i++) {
        uvoff[i * 2] = pose.uv[i].x;
        uvoff[i * 2 + 1] = pose.uv[i].y;
    }
    glUniform2fv(glGetUniformLocation(gpu.program, "u_uvoff"), n_bones, uvoff.data());
    glActiveTexture(GL_TEXTURE4);
    glBindTexture(GL_TEXTURE_2D, gpu.env);
    glUniform1i(glGetUniformLocation(gpu.program, "u_env"), 4);
    glUniform1f(glGetUniformLocation(gpu.program, "u_reflect"), opt.reflect);
    glUniform1i(glGetUniformLocation(gpu.program, "u_moody"), opt.moody ? 1 : 0);
    glUniform3f(glGetUniformLocation(gpu.program, "u_key_world"), key.x, key.y, key.z);
    if (opt.moody) {
        glUniformMatrix4fv(glGetUniformLocation(gpu.program, "u_light_vp"), 1, GL_FALSE, light_vp);
        glActiveTexture(GL_TEXTURE5);
        glBindTexture(GL_TEXTURE_2D, gpu.shadow_tex);
        glUniform1i(glGetUniformLocation(gpu.program, "u_shadow"), 5);
    }
    const char* tile_names[3] = {"u_tile0", "u_tile1", "u_tile2"};
    for (int i = 0; i < 3; i++) {
        glActiveTexture(GL_TEXTURE1 + i);
        glBindTexture(GL_TEXTURE_2D, gpu.tiles[i]);
        glUniform1i(glGetUniformLocation(gpu.program, tile_names[i]), 1 + i);
    }
    int mode = opt.flat ? 1 : (opt.show_uv ? 2 : 0);
    glUniform1i(glGetUniformLocation(gpu.program, "u_mode"), mode);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, gpu.texture);
    glBindVertexArray(gpu.vao);

    if (pose.ground_on && mode != 3) {
        glUseProgram(gpu.ground_program);
        glUniformMatrix4fv(glGetUniformLocation(gpu.ground_program, "u_view"), 1, GL_FALSE, view);
        glUniformMatrix4fv(glGetUniformLocation(gpu.ground_program, "u_proj"), 1, GL_FALSE, proj);
        glUniform1f(glGetUniformLocation(gpu.ground_program, "u_size"), gpu.radius * 3.6f);
        glUniform1f(glGetUniformLocation(gpu.ground_program, "u_scroll"), pose.ground);
        glUniform1f(glGetUniformLocation(gpu.ground_program, "u_period"), pose.ground_period);
        glUniform3f(glGetUniformLocation(gpu.ground_program, "u_center"), gpu.center[0], 0, gpu.center[2]);
        glUniform1i(glGetUniformLocation(gpu.ground_program, "u_moody"), opt.moody ? 1 : 0);
        if (opt.moody) {
            glUniformMatrix4fv(glGetUniformLocation(gpu.ground_program, "u_light_vp"), 1, GL_FALSE, light_vp);
            glActiveTexture(GL_TEXTURE5);
            glBindTexture(GL_TEXTURE_2D, gpu.shadow_tex);
            glUniform1i(glGetUniformLocation(gpu.ground_program, "u_shadow"), 5);
            glActiveTexture(GL_TEXTURE0);
        }
        glBindVertexArray(gpu.empty_vao);
        glDrawArrays(GL_TRIANGLES, 0, 6);
        glUseProgram(gpu.program);
        glBindVertexArray(gpu.vao);
    }

    glEnable(GL_POLYGON_OFFSET_FILL);
    glPolygonOffset(1.0f, 1.0f);
    glDrawElements(GL_TRIANGLES, gpu.additive_first, GL_UNSIGNED_INT, nullptr);
    glDisable(GL_POLYGON_OFFSET_FILL);

    // glowing parts: added on top, no depth writes
    int n_add = gpu.index_count - gpu.additive_first;
    if (n_add > 0 && mode == 0) {
        glUniform1i(glGetUniformLocation(gpu.program, "u_mode"), 4);
        glEnable(GL_BLEND);
        glBlendFunc(GL_ONE, GL_ONE);
        glDepthMask(GL_FALSE);
        glEnable(GL_CULL_FACE);
        glDrawElements(GL_TRIANGLES, n_add, GL_UNSIGNED_INT, (void*)(gpu.additive_first * sizeof(uint32_t)));
        glDisable(GL_CULL_FACE);
        glDepthMask(GL_TRUE);
        glDisable(GL_BLEND);
    }

    if (mode == 0) {
        fx_draw(gpu, pose, view, proj, Vec3{eye[0], eye[1], eye[2]});
        glUseProgram(gpu.program);
        glBindVertexArray(gpu.vao);
    }

    if (opt.wire) {
        glUniform1i(glGetUniformLocation(gpu.program, "u_mode"), 3);
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE);
        glDrawElements(GL_TRIANGLES, gpu.index_count, GL_UNSIGNED_INT, nullptr);
        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL);
    }
    glBindVertexArray(0);
}
