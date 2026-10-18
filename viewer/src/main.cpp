// genmodel viewer: shows a generated .obj with its texture.
//   viewer out/model.obj                 window, mouse drag to orbit
//   viewer out/model.obj --capture a.png headless render on the GPU, no window
#include "draw.hpp"
#include "headless.hpp"
#include "model.hpp"

#include <GL/glcorearb.h>
#include <SDL3/SDL.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

struct Args {
    std::string obj;
    std::string capture;
    bool sheet = false; // four standard views in a 2x2 grid
    int width = 1280;
    int height = 720;
    Camera cam;
    DrawOptions opt;
};

static bool parse_args(int argc, char** argv, Args& a) {
    for (int i = 1; i < argc; i++) {
        std::string s = argv[i];
        bool has_next = i + 1 < argc;
        if (s == "--capture" && has_next) {
            a.capture = argv[++i];
        } else if (s == "--sheet") {
            a.sheet = true;
        } else if (s == "--size" && i + 2 < argc) {
            a.width = atoi(argv[++i]);
            a.height = atoi(argv[++i]);
        } else if (s == "--yaw" && has_next) {
            a.cam.yaw = (float)atof(argv[++i]) * (float)M_PI / 180.0f;
        } else if (s == "--pitch" && has_next) {
            a.cam.pitch = (float)atof(argv[++i]) * (float)M_PI / 180.0f;
        } else if (s == "--zoom" && has_next) {
            a.cam.zoom = (float)atof(argv[++i]);
        } else if (s == "--wire") {
            a.opt.wire = true;
        } else if (s == "--clay") {
            a.opt.flat = true;
        } else if (s == "--uv") {
            a.opt.show_uv = true;
        } else if (s[0] != '-') {
            a.obj = s;
        } else {
            fprintf(stderr, "unknown argument %s\n", s.c_str());
            return false;
        }
    }
    return !a.obj.empty();
}

// the 2x2 sheet: the target's three-quarter view, side, top, and back three-quarter
static std::vector<Shot> sheet_shots(const Args& a) {
    float deg = (float)M_PI / 180.0f;
    float views[4][2] = {{a.cam.yaw / deg, a.cam.pitch / deg}, {0, 0}, {0, 89}, {200, 20}};
    std::vector<Shot> shots;
    for (auto& v : views) {
        Shot s;
        s.cam = a.cam;
        s.cam.yaw = v[0] * deg;
        s.cam.pitch = v[1] * deg;
        s.opt = a.opt;
        shots.push_back(s);
    }
    return shots;
}

static int run_window(const Args& a, Model& model) {
    if (!SDL_Init(SDL_INIT_VIDEO)) {
        fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
        return 1;
    }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 1);
    SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 8);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);
    SDL_Window* window = SDL_CreateWindow("genmodel", a.width, a.height,
                                          SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE);
    if (!window) {
        fprintf(stderr, "SDL_CreateWindow: %s\n", SDL_GetError());
        return 1;
    }
    SDL_SetWindowPosition(window, SDL_WINDOWPOS_CENTERED_DISPLAY(SDL_GetPrimaryDisplay()),
                          SDL_WINDOWPOS_CENTERED_DISPLAY(SDL_GetPrimaryDisplay()));
    SDL_GLContext ctx = SDL_GL_CreateContext(window);
    SDL_GL_SetSwapInterval(1);
    Gpu gpu;
    if (!ctx || !gpu_init(gpu)) {
        return 1;
    }
    gpu_upload(gpu, model);
    printf("drag: orbit   right drag: pan   wheel: zoom   W: wire   C: clay   U: uvs\n"
           "space: spin   R: reset view   Esc: quit   (reloads when the model file changes)\n");

    Camera cam = a.cam;
    DrawOptions opt = a.opt;
    bool spin = false;
    int64_t stamp = model_stamp(a.obj);
    uint64_t last_check = SDL_GetTicks();
    uint64_t last_frame = SDL_GetTicks();
    bool running = true;
    while (running) {
        // pump input
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_EVENT_QUIT) {
                running = false;
            } else if (e.type == SDL_EVENT_MOUSE_MOTION) {
                if (e.motion.state & SDL_BUTTON_LMASK) {
                    cam.yaw -= e.motion.xrel * 0.008f;
                    cam.pitch += e.motion.yrel * 0.008f;
                    cam.pitch = std::fmax(-1.55f, std::fmin(1.55f, cam.pitch));
                } else if (e.motion.state & (SDL_BUTTON_RMASK | SDL_BUTTON_MMASK)) {
                    cam.pan_x -= e.motion.xrel * 0.002f * cam.zoom;
                    cam.pan_y += e.motion.yrel * 0.002f * cam.zoom;
                }
            } else if (e.type == SDL_EVENT_MOUSE_WHEEL) {
                cam.zoom *= std::pow(0.9f, e.wheel.y);
                cam.zoom = std::fmax(0.1f, std::fmin(5.0f, cam.zoom));
            } else if (e.type == SDL_EVENT_KEY_DOWN) {
                SDL_Keycode k = e.key.key;
                if (k == SDLK_ESCAPE) {
                    running = false;
                } else if (k == SDLK_W) {
                    opt.wire = !opt.wire;
                } else if (k == SDLK_C) {
                    opt.flat = !opt.flat;
                } else if (k == SDLK_U) {
                    opt.show_uv = !opt.show_uv;
                } else if (k == SDLK_SPACE) {
                    spin = !spin;
                } else if (k == SDLK_R) {
                    cam = a.cam;
                }
            }
        }

        // hot reload when the generator rewrites the model
        uint64_t now = SDL_GetTicks();
        if (now - last_check > 500) {
            last_check = now;
            int64_t s = model_stamp(a.obj);
            if (s != stamp) {
                stamp = s;
                SDL_Delay(200); // let the writer finish
                if (load_model(a.obj, model)) {
                    gpu_upload(gpu, model);
                }
            }
        }
        if (spin) {
            cam.yaw += (now - last_frame) * 0.0005f;
        }
        last_frame = now;

        // draw frame
        int w, h;
        SDL_GetWindowSizeInPixels(window, &w, &h);
        gpu_draw(gpu, cam, opt, w, h);
        SDL_GL_SwapWindow(window);
    }
    SDL_GL_DestroyContext(ctx);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}

int main(int argc, char** argv) {
    Args a;
    if (!parse_args(argc, argv, a)) {
        fprintf(stderr, "usage: viewer model.obj [--capture out.png [--sheet]] [--size w h]\n"
                        "       [--yaw deg] [--pitch deg] [--zoom z] [--wire] [--clay] [--uv]\n");
        return 1;
    }
    Model model;
    if (!load_model(a.obj, model)) {
        return 1;
    }
    if (!a.capture.empty()) {
        std::vector<Shot> shots;
        if (a.sheet) {
            shots = sheet_shots(a);
        } else {
            shots.push_back({a.cam, a.opt});
        }
        int columns = a.sheet ? 2 : 1;
        return capture(model, shots, columns, a.width, a.height, a.capture) ? 0 : 1;
    }

    // agents must never put a window on the user's screen
    if (getenv("CLAUDECODE") && !getenv("GENMODEL_ON_SCREEN")) {
        fprintf(stderr, "refusing to open a window under an agent; use --capture\n");
        return 1;
    }
    return run_window(a, model);
}
