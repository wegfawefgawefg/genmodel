#include "draw.hpp"

#include <GL/glcorearb.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>

namespace {

const char* model_vs = R"(#version 330 core
layout(location = 0) in vec3 a_pos;
layout(location = 1) in vec3 a_nrm;
layout(location = 2) in vec2 a_uv;
layout(location = 3) in float a_part;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform mat4 u_bones[128];
uniform vec3 u_glow[128];
out vec3 v_nrm;
out vec3 v_view_pos;
out vec2 v_uv;
out vec3 v_glow;
void main() {
    int part = int(a_part + 0.5);
    mat4 bone = u_bones[part];
    vec4 vp = u_view * (bone * vec4(a_pos, 1.0));
    v_view_pos = vp.xyz;
    v_nrm = mat3(u_view) * (mat3(bone) * a_nrm);
    v_uv = a_uv;
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
uniform sampler2D u_tex;
uniform int u_mode; // 0 textured, 1 clay, 2 uv checker, 3 wire, 4 additive glow
out vec4 o_color;
void main() {
    if (u_mode == 3) {
        o_color = vec4(0.05, 0.9, 1.0, 1.0);
        return;
    }
    vec4 t = texture(u_tex, v_uv);
    if (u_mode == 4) {
        // flashes: the texture is the flame colour, the view angle thins the edges
        // white-hot where it faces you, deep orange at the grazing edges
        float facing = abs(dot(normalize(v_nrm), normalize(-v_view_pos)));
        vec3 edge = vec3(1.0, 0.22, 0.02);
        vec3 flame = mix(edge, t.rgb * vec3(1.0, 0.95, 0.85), facing * facing);
        o_color = vec4(flame * (0.25 + 1.1 * facing) + v_glow, 1.0);
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

    // hemisphere ambient, sky above and dark floor below
    float up = n.y * 0.5 + 0.5;
    vec3 ambient = mix(vec3(0.05, 0.05, 0.06), vec3(0.22, 0.25, 0.3), up);

    float nk = max(dot(n, key_dir), 0.0);
    float nf = max(dot(n, fill_dir), 0.0);
    vec3 diffuse = albedo * (ambient + key_col * nk + fill_col * nf);

    // shiny bits get a tight highlight, matte bits a broad soft one
    float power = mix(12.0, 90.0, shine);
    vec3 h = normalize(key_dir + eye);
    float spec = pow(max(dot(n, h), 0.0), power) * (0.04 + 0.9 * shine) * (power + 8.0) / 25.0;
    float rim = pow(1.0 - max(dot(n, eye), 0.0), 3.0) * max(dot(n, rim_dir) + 0.4, 0.0);

    vec3 col = diffuse + key_col * spec * nk + rim_col * rim * (0.15 + 0.35 * shine);
    // heat and lamps: emissive on top of the lighting; dark metal shows heat most,
    // and a hot part's own lighting fades under the glow
    float dark = 1.0 - clamp(dot(albedo, vec3(0.33)) * 3.0, 0.0, 1.0);
    vec3 emit = v_glow * (0.35 + 0.65 * dark);
    col = col * (1.0 - clamp(dot(emit, vec3(0.6)), 0.0, 0.85)) + emit;
    col = col / (1.0 + col * 0.25);
    o_color = vec4(pow(col, vec3(1.0 / 2.2)), 1.0);
}
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
    return true;
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
    glBindVertexArray(0);

    // texture with mips and anisotropy so panel lines hold up at a glance
    glBindTexture(GL_TEXTURE_2D, gpu.texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, model.texture.w, model.texture.h, 0, GL_RGBA,
                 GL_UNSIGNED_BYTE, model.texture.rgba.data());
    glGenerateMipmap(GL_TEXTURE_2D);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY, 8.0f);

    gpu.index_count = (int)model.indices.size();
    memcpy(gpu.center, model.center, sizeof(gpu.center));
    gpu.radius = model.radius;
}

void gpu_draw(const Gpu& gpu, const Camera& cam, const DrawOptions& opt, const Pose& pose, int width, int height) {
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
    int mode = opt.flat ? 1 : (opt.show_uv ? 2 : 0);
    glUniform1i(glGetUniformLocation(gpu.program, "u_mode"), mode);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, gpu.texture);
    glBindVertexArray(gpu.vao);

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

    if (opt.wire) {
        glUniform1i(glGetUniformLocation(gpu.program, "u_mode"), 3);
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE);
        glDrawElements(GL_TRIANGLES, gpu.index_count, GL_UNSIGNED_INT, nullptr);
        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL);
    }
    glBindVertexArray(0);
}
