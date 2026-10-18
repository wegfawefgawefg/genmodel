// genmodel viewer: shows a generated .obj with its texture, rig and animation.
//   viewer out/m/m.obj [--anim gen/models/m.anim.sexp]   window, mouse drag to orbit
//   viewer out/m/m.obj --capture a.png                    headless render on the GPU, no window
#include "asset.hpp"
#include "draw.hpp"
#include "headless.hpp"

#include <GL/glcorearb.h>
#include <SDL3/SDL.h>

#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

struct Args {
    std::string obj;
    std::string anim;
    std::string capture;
    bool sheet = false;     // four standard views in a 2x2 grid
    bool print_shots = false; // print the animation's shot times and fire rate, then exit
    int dump_bones = 0;     // print every part's matrix at this many times over the loop, then exit
    std::string audio;      // write the soundtrack (from --time, --audio-secs long) to a wav
    float audio_secs = 10;
    int turntable = 0;      // frames to write to a %d pattern, orbiting and animating
    float spin_secs = 0;    // seconds per orbit in a turntable (0: one orbit over all frames)
    float time = 0;         // animation time of a still, or of a turntable's first frame
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
        } else if (s == "--anim" && has_next) {
            a.anim = argv[++i];
        } else if (s == "--turntable" && has_next) {
            a.turntable = atoi(argv[++i]);
        } else if (s == "--spin-secs" && has_next) {
            a.spin_secs = (float)atof(argv[++i]);
        } else if (s == "--time" && has_next) {
            a.time = (float)atof(argv[++i]);
        } else if (s == "--audio" && has_next) {
            a.audio = argv[++i];
        } else if (s == "--audio-secs" && has_next) {
            a.audio_secs = (float)atof(argv[++i]);
        } else if (s == "--dump-bones" && has_next) {
            a.dump_bones = atoi(argv[++i]);
        } else if (s == "--print-shots") {
            a.print_shots = true;
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
        } else if (s == "--reflect" && has_next) {
            a.opt.reflect = (float)atof(argv[++i]);
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
        Shot s = {a.cam, a.opt, a.time};
        s.cam.yaw = v[0] * deg;
        s.cam.pitch = v[1] * deg;
        shots.push_back(s);
    }
    return shots;
}

// 60 fps frames: time runs on from --time while the camera orbits
static std::vector<Shot> turntable_shots(const Args& a) {
    float spin = a.spin_secs > 0 ? a.spin_secs : a.turntable / 60.0f;
    std::vector<Shot> shots;
    for (int i = 0; i < a.turntable; i++) {
        float t = i / 60.0f;
        Shot s = {a.cam, a.opt, a.time + t};
        s.cam.yaw += 2.0f * (float)M_PI * t / spin;
        shots.push_back(s);
    }
    return shots;
}

// live sound: the device pulls blocks rendered from the shared, stateless mixer; while it
// plays, its clock is the animation's clock
struct AudioOut {
    SDL_AudioStream* stream = nullptr;
    Asset* asset = nullptr;
    std::atomic<double> time{0};
    std::atomic<bool> playing{false};
    std::vector<float> block;
};

static void SDLCALL pull_audio(void* user, SDL_AudioStream* stream, int additional, int /*total*/) {
    AudioOut* ao = (AudioOut*)user;
    int frames = additional / (int)(2 * sizeof(float));
    if (frames <= 0) {
        return;
    }
    ao->block.assign((size_t)frames * 2, 0.0f);
    if (ao->playing && ao->asset->animated) {
        double t = ao->time;
        sound_render(ao->asset->sound, ao->asset->anim, t, frames, ao->block.data());
        ao->time = t + (double)frames / sound_rate;
    }
    SDL_PutAudioStreamData(stream, ao->block.data(), frames * (int)(2 * sizeof(float)));
}

static void open_audio(AudioOut& ao, Asset& asset) {
    ao.asset = &asset;
    if (!SDL_InitSubSystem(SDL_INIT_AUDIO)) {
        fprintf(stderr, "no audio: %s\n", SDL_GetError());
        return;
    }
    SDL_AudioSpec spec = {SDL_AUDIO_F32, 2, sound_rate};
    ao.stream = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, pull_audio, &ao);
    if (!ao.stream) {
        fprintf(stderr, "no audio device: %s\n", SDL_GetError());
        return;
    }
    SDL_ResumeAudioStreamDevice(ao.stream);
}

static int run_window(const Args& a, Asset& asset) {
    SDL_SetHint(SDL_HINT_APP_ID, "genmodel-viewer");
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
    SDL_Window* window = SDL_CreateWindow("genmodel viewer", a.width, a.height,
                                          SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE);
    if (!window) {
        // no multisampled visual on this display: go without
        SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 0);
        SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 0);
        window = SDL_CreateWindow("genmodel viewer", a.width, a.height, SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE);
    }
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
    gpu_upload(gpu, asset.model, asset.rig);
    AudioOut audio;
    open_audio(audio, asset);
    bool muted = false;
    printf("drag: orbit   right drag: pan   wheel: zoom   W: wire   C: clay   U: uvs\n"
           "space: spin   R: reset view   P: pause   , .: step   [ ]: slower/faster   M: mute\n"
           "E: fake reflections on/off\n"
           "Esc: quit\n"
           "(reloads when the model or animation files change)\n");

    Camera cam = a.cam;
    DrawOptions opt = a.opt;
    Pose pose;
    bool spin = false;
    bool paused = false;
    float speed = 1.0f;
    float anim_time = a.time;
    int64_t stamp = asset_stamp(asset);
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
                } else if (k == SDLK_P) {
                    paused = !paused;
                } else if (k == SDLK_COMMA) {
                    anim_time -= 1.0f / 60.0f;
                } else if (k == SDLK_PERIOD) {
                    anim_time += 1.0f / 60.0f;
                } else if (k == SDLK_LEFTBRACKET) {
                    speed = std::fmax(speed * 0.5f, 1.0f / 64.0f);
                } else if (k == SDLK_RIGHTBRACKET) {
                    speed = std::fmin(speed * 2.0f, 4.0f);
                } else if (k == SDLK_M) {
                    muted = !muted;
                } else if (k == SDLK_E) {
                    opt.reflect = opt.reflect > 0 ? 0.0f : 0.8f;
                }
            }
        }

        // hot reload when the generator or the animation file changes
        uint64_t now = SDL_GetTicks();
        if (now - last_check > 500) {
            last_check = now;
            int64_t s = asset_stamp(asset);
            if (s != stamp) {
                stamp = s;
                printf("model changed, reloading\n");
                SDL_Delay(200); // let the writer finish
                Asset fresh;
                if (load_asset(asset.obj_path, asset.anim_path, fresh)) {
                    // the audio thread reads the asset; swap it under the stream's lock
                    if (audio.stream) SDL_LockAudioStream(audio.stream);
                    asset = std::move(fresh);
                    if (audio.stream) SDL_UnlockAudioStream(audio.stream);
                    gpu_upload(gpu, asset.model, asset.rig);
                }
            }
        }
        float dt = (now - last_frame) / 1000.0f;
        last_frame = now;
        if (spin) {
            cam.yaw += dt * 0.5f;
        }
        // sound plays only at normal speed; then its clock leads (minus what's still queued)
        bool want_sound = audio.stream && !muted && !paused && speed == 1.0f && asset.animated;
        if (want_sound && !audio.playing) {
            audio.time = (double)anim_time;
            audio.playing = true;
        } else if (!want_sound && audio.playing) {
            audio.playing = false;
        }
        if (audio.playing) {
            // run on wall time but lean toward the audio clock, which moves in device blocks
            double queued = SDL_GetAudioStreamQueued(audio.stream) / (double)(2 * sizeof(float) * sound_rate);
            float heard = (float)(audio.time - queued);
            anim_time += dt;
            anim_time += (heard - anim_time) * 0.1f;
            if (std::fabs(heard - anim_time) > 0.1f) {
                anim_time = heard;
            }
        } else if (!paused) {
            anim_time += dt * speed;
        }

        // draw frame
        int w, h;
        SDL_GetWindowSizeInPixels(window, &w, &h);
        asset_pose(asset, anim_time, pose);
        gpu_draw(gpu, cam, opt, pose, w, h);
        SDL_GL_SwapWindow(window);
    }
    if (audio.stream) {
        SDL_DestroyAudioStream(audio.stream);
    }
    SDL_GL_DestroyContext(ctx);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}

int main(int argc, char** argv) {
    // line-buffered even when piped, so reload messages show up as they happen
    setvbuf(stdout, nullptr, _IOLBF, 0);
    Args a;
    if (!parse_args(argc, argv, a)) {
        fprintf(stderr, "usage: viewer model.obj [--anim file.anim.sexp] [--capture out.png [--sheet |\n"
                        "       --turntable frames [--spin-secs s]]] [--time t] [--size w h]\n"
                        "       [--yaw deg] [--pitch deg] [--zoom z] [--wire] [--clay] [--uv]\n"
                        "       [--audio out.wav [--audio-secs s]] [--print-shots]\n");
        return 1;
    }
    Asset asset;
    if (!load_asset(a.obj, a.anim, asset)) {
        return 1;
    }
    if (a.dump_bones > 0) {
        Pose pose;
        for (int i = 0; i < a.dump_bones; i++) {
            float t = asset.anim.length * (float)i / (float)a.dump_bones;
            asset_pose(asset, t, pose);
            printf("pose %.4f\n", t);
            for (size_t p = 0; p < asset.rig.parts.size() && p < pose.bones.size(); p++) {
                printf("bone %s %d", asset.rig.parts[p].name.c_str(), asset.rig.parts[p].parent);
                for (float m : pose.bones[p].m) printf(" %.5f", m);
                printf("\n");
            }
        }
        return 0;
    }
    if (a.print_shots) {
        printf("length %.4f\n", asset.anim.length);
        for (size_t i = 0; i < asset.anim.shots.size(); i++) {
            printf("shot %.5f %zu\n", asset.anim.shots[i], i);
        }
        for (size_t i = 0; i < asset.anim.rate_table.size(); i += 4) {
            printf("rate %.4f %.3f %.3f\n", i * asset.anim.table_dt, asset.anim.rate_table[i], asset.anim.heat_table[i]);
        }
        return 0;
    }
    if (!a.audio.empty()) {
        std::vector<float> pcm((size_t)(a.audio_secs * sound_rate) * 2);
        sound_render(asset.sound, asset.anim, a.time, (int)(pcm.size() / 2), pcm.data());
        bool ok = asset.sound.ok && write_wav16(a.audio, pcm);
        printf(ok ? "wrote %s\n" : "no sound for %s\n", a.audio.c_str());
        return ok ? 0 : 1;
    }
    if (!a.capture.empty()) {
        std::vector<Shot> shots;
        if (a.sheet) {
            shots = sheet_shots(a);
        } else if (a.turntable > 0) {
            shots = turntable_shots(a);
        } else {
            shots.push_back({a.cam, a.opt, a.time});
        }
        int columns = a.sheet ? 2 : 1;
        return capture(asset, shots, columns, a.width, a.height, a.capture) ? 0 : 1;
    }

    // agents must never put a window on the user's screen
    if (getenv("CLAUDECODE") && !getenv("GENMODEL_ON_SCREEN")) {
        fprintf(stderr, "refusing to open a window under an agent; use --capture\n");
        return 1;
    }
    return run_window(a, asset);
}
