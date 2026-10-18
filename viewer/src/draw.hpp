#pragma once

#include "anim.hpp"
#include "model.hpp"
#include "rig.hpp"

#include <cstdint>

// orbit camera around the model's center
struct Camera {
    float yaw = -0.6f;   // radians around +Y
    float pitch = 0.25f; // radians above the horizon
    float zoom = 1.0f;   // distance multiplier over the fit distance
    float pan_x = 0.0f;  // screen-space offsets in model radii
    float pan_y = 0.0f;
};

struct Gpu {
    uint32_t program = 0;
    uint32_t back_program = 0;
    uint32_t vao = 0;
    uint32_t vbo = 0;
    uint32_t ibo = 0;
    uint32_t texture = 0;
    uint32_t empty_vao = 0;
    int index_count = 0;
    int additive_first = 0; // triangles of additive parts sit at the end of the index buffer
    uint32_t fx_program = 0, fx_vao = 0, fx_vbo = 0, fx_atlas = 0;
    float center[3] = {0, 0, 0};
    float radius = 1.0f;
};

struct DrawOptions {
    bool wire = false;    // wireframe over the shaded model
    bool flat = false;    // ignore the texture, show grey clay
    bool show_uv = false; // show the uv layout as a checker
};

const int max_parts = 128;

bool gpu_init(Gpu& gpu);
bool fx_init(Gpu& gpu);
// smoke and sparks over the drawn model (view/proj column-major, eye in model space)
void fx_draw(const Gpu& gpu, const Pose& pose, const float* view, const float* proj, Vec3 eye);
// binds each vertex to its rig part by obj group name
void gpu_upload(Gpu& gpu, Model& model, const Rig& rig);
void gpu_draw(const Gpu& gpu, const Camera& cam, const DrawOptions& opt, const Pose& pose, int width, int height);
