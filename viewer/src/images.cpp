#include "images.hpp"

#define STB_IMAGE_IMPLEMENTATION
#include <stb_image.h>
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <stb_image_write.h>

#include <cstdio>
#include <cstring>

bool load_png(const std::string& path, Image& out) {
    // obj uvs put v = 0 at the bottom of the image
    stbi_set_flip_vertically_on_load(1);
    int w, h, n;
    uint8_t* data = stbi_load(path.c_str(), &w, &h, &n, 4);
    if (!data) {
        fprintf(stderr, "cannot load %s\n", path.c_str());
        return false;
    }
    out.w = w;
    out.h = h;
    out.rgba.assign(data, data + (size_t)w * h * 4);
    stbi_image_free(data);
    return true;
}

bool save_png(const std::string& path, const Image& img) {
    return stbi_write_png(path.c_str(), img.w, img.h, 4, img.rgba.data(), img.w * 4) != 0;
}
