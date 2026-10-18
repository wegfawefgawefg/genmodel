#include "headless.hpp"

#include "images.hpp"

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GL/glcorearb.h>

#include <cstdio>
#include <cstring>

namespace {

// a context on the real GPU with no surface and no display server
bool make_context(EGLDisplay& out_display) {
    auto get_display =
        (PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");
    EGLDisplay dpy = EGL_NO_DISPLAY;
    if (get_display) {
        dpy = get_display(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, nullptr);
    }
    if (dpy == EGL_NO_DISPLAY) {
        fprintf(stderr, "no surfaceless EGL display\n");
        return false;
    }
    if (!eglInitialize(dpy, nullptr, nullptr)) {
        fprintf(stderr, "eglInitialize failed\n");
        return false;
    }
    eglBindAPI(EGL_OPENGL_API);
    EGLint cfg_attr[] = {EGL_RENDERABLE_TYPE, EGL_OPENGL_BIT, EGL_NONE};
    EGLConfig cfg;
    EGLint n = 0;
    eglChooseConfig(dpy, cfg_attr, &cfg, 1, &n);
    EGLint ctx_attr[] = {EGL_CONTEXT_MAJOR_VERSION, 3, EGL_CONTEXT_MINOR_VERSION, 3,
                         EGL_CONTEXT_OPENGL_PROFILE_MASK, EGL_CONTEXT_OPENGL_CORE_PROFILE_BIT,
                         EGL_NONE};
    EGLContext ctx = eglCreateContext(dpy, n ? cfg : EGL_NO_CONFIG_KHR, EGL_NO_CONTEXT, ctx_attr);
    if (ctx == EGL_NO_CONTEXT || !eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, ctx)) {
        fprintf(stderr, "cannot create a surfaceless GL 3.3 context\n");
        return false;
    }
    out_display = dpy;
    return true;
}

} // namespace

bool capture(const Model& model, const std::vector<Shot>& shots, int columns, int width,
             int height, const std::string& out_path) {
    EGLDisplay dpy;
    if (!make_context(dpy)) {
        return false;
    }
    printf("headless GL: %s\n", (const char*)glGetString(GL_RENDERER));
    Gpu gpu;
    if (!gpu_init(gpu)) {
        return false;
    }
    gpu_upload(gpu, model);

    // multisampled target, resolved into a plain one for reading back
    uint32_t msaa_fbo, msaa_color, msaa_depth, fbo, color;
    glGenFramebuffers(1, &msaa_fbo);
    glGenRenderbuffers(1, &msaa_color);
    glGenRenderbuffers(1, &msaa_depth);
    glBindFramebuffer(GL_FRAMEBUFFER, msaa_fbo);
    glBindRenderbuffer(GL_RENDERBUFFER, msaa_color);
    glRenderbufferStorageMultisample(GL_RENDERBUFFER, 8, GL_RGBA8, width, height);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, msaa_color);
    glBindRenderbuffer(GL_RENDERBUFFER, msaa_depth);
    glRenderbufferStorageMultisample(GL_RENDERBUFFER, 8, GL_DEPTH_COMPONENT24, width, height);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, msaa_depth);
    glGenFramebuffers(1, &fbo);
    glGenRenderbuffers(1, &color);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glBindRenderbuffer(GL_RENDERBUFFER, color);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, width, height);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, color);

    int rows = ((int)shots.size() + columns - 1) / columns;
    Image sheet;
    sheet.w = width * columns;
    sheet.h = height * rows;
    sheet.rgba.assign((size_t)sheet.w * sheet.h * 4, 0);
    std::vector<uint8_t> pixels((size_t)width * height * 4);

    for (size_t i = 0; i < shots.size(); i++) {
        glBindFramebuffer(GL_FRAMEBUFFER, msaa_fbo);
        gpu_draw(gpu, shots[i].cam, shots[i].opt, width, height);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, msaa_fbo);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, fbo);
        glBlitFramebuffer(0, 0, width, height, 0, 0, width, height, GL_COLOR_BUFFER_BIT,
                          GL_NEAREST);
        glBindFramebuffer(GL_FRAMEBUFFER, fbo);
        glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());

        // a printf pattern like frame_%03d.png writes one file per shot
        if (out_path.find('%') != std::string::npos) {
            Image frame;
            frame.w = width;
            frame.h = height;
            frame.rgba.resize(pixels.size());
            for (int y = 0; y < height; y++) {
                memcpy(&frame.rgba[(size_t)y * width * 4], &pixels[(size_t)(height - 1 - y) * width * 4],
                       (size_t)width * 4);
            }
            for (size_t k = 3; k < frame.rgba.size(); k += 4) {
                frame.rgba[k] = 255;
            }
            char name[1024];
            snprintf(name, sizeof(name), out_path.c_str(), (int)i);
            save_png(name, frame);
            continue;
        }

        // flip rows into the tile
        int tx = (int)(i % columns) * width;
        int ty = (int)(i / columns) * height;
        for (int y = 0; y < height; y++) {
            const uint8_t* src = &pixels[(size_t)(height - 1 - y) * width * 4];
            uint8_t* dst = &sheet.rgba[((size_t)(ty + y) * sheet.w + tx) * 4];
            memcpy(dst, src, (size_t)width * 4);
        }
    }
    if (out_path.find('%') != std::string::npos) {
        printf("wrote %zu frames\n", shots.size());
        eglTerminate(dpy);
        return true;
    }
    for (size_t i = 3; i < sheet.rgba.size(); i += 4) {
        sheet.rgba[i] = 255;
    }
    if (!save_png(out_path, sheet)) {
        fprintf(stderr, "cannot write %s\n", out_path.c_str());
        return false;
    }
    printf("wrote %s\n", out_path.c_str());
    eglTerminate(dpy);
    return true;
}
