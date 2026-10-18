#pragma once

#include "draw.hpp"
#include "asset.hpp"

#include <string>
#include <vector>

struct Shot {
    Camera cam;
    DrawOptions opt;
    float time = 0; // animation time
};

// renders shots on the GPU with no window (EGL surfaceless) and tiles them into one png,
// `columns` shots per row, each `width` x `height`
bool capture(Asset& asset, const std::vector<Shot>& shots, int columns, int width,
             int height, const std::string& out_path);
