#pragma once

#include "model.hpp"

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
    float center[3] = {0, 0, 0};
    float radius = 1.0f;
};

struct DrawOptions {
    bool wire = false;    // wireframe over the shaded model
    bool flat = false;    // ignore the texture, show grey clay
    bool show_uv = false; // show the uv layout as a checker
};

bool gpu_init(Gpu& gpu);
void gpu_upload(Gpu& gpu, const Model& model);
void gpu_draw(const Gpu& gpu, const Camera& cam, const DrawOptions& opt, int width, int height);
