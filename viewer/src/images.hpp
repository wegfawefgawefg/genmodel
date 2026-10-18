#pragma once

#include "model.hpp"

#include <string>

bool load_png(const std::string& path, Image& out);
bool save_png(const std::string& path, const Image& img);
