#include "asset.hpp"

#include <filesystem>

namespace fs = std::filesystem;

static std::string rig_path_for(const std::string& obj_path) {
    fs::path p(obj_path);
    return (p.parent_path() / (p.stem().string() + ".rig.sexp")).string();
}

bool load_asset(const std::string& obj_path, const std::string& anim_path, Asset& out) {
    Asset a;
    a.obj_path = obj_path;
    a.anim_path = anim_path;
    if (!load_model(obj_path, a.model)) {
        return false;
    }
    if (!load_rig(rig_path_for(obj_path), a.rig)) {
        a.rig = root_only_rig();
    }
    if (!anim_path.empty()) {
        a.animated = load_anim(anim_path, a.rig, a.anim);
    }
    out = std::move(a);
    return true;
}

void asset_pose(const Asset& a, float t, Pose& out) {
    if (a.animated) {
        evaluate(a.anim, a.rig, t, out);
    } else {
        rest_pose(a.rig, out);
    }
}

static int64_t stamp_of(const std::string& path) {
    std::error_code ec;
    auto t = fs::last_write_time(path, ec);
    return ec ? 0 : (int64_t)t.time_since_epoch().count();
}

int64_t asset_stamp(const Asset& a) {
    int64_t s = model_stamp(a.obj_path);
    s = std::max(s, stamp_of(rig_path_for(a.obj_path)));
    if (!a.anim_path.empty()) {
        s = std::max(s, stamp_of(a.anim_path));
    }
    return s;
}
