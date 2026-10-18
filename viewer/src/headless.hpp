#pragma once

#include "draw.hpp"
#include "model.hpp"

#include <string>
#include <vector>

struct Shot {
    Camera cam;
    DrawOptions opt;
};

// renders shots on the GPU with no window (EGL surfaceless) and tiles them into one png,
// `columns` shots per row, each `width` x `height`
bool capture(const Model& model, const std::vector<Shot>& shots, int columns, int width,
             int height, const std::string& out_path);
