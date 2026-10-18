#pragma once

#include "anim.hpp"
#include "model.hpp"
#include "rig.hpp"

#include <cstdint>
#include <string>

// everything the viewer shows: mesh + texture, rig (from <obj>.rig.sexp), animation
struct Asset {
    std::string obj_path;
    std::string anim_path;
    Model model;
    Rig rig;
    Anim anim;
    bool animated = false;
};

bool load_asset(const std::string& obj_path, const std::string& anim_path, Asset& out);
void asset_pose(const Asset& a, float t, Pose& out);
// newest modification time of every file the asset was built from
int64_t asset_stamp(const Asset& a);
