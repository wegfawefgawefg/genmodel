#include "asset.hpp"

#include <filesystem>

namespace fs = std::filesystem;

static std::string rig_path_for(const std::string& obj_path) {
    fs::path p(obj_path);
    return (p.parent_path() / (p.stem().string() + ".rig.sexp")).string();
}

// m.anim.sexp -> m.sound.sexp
static std::string bank_path_for(const std::string& anim_path) {
    const std::string tail = ".anim.sexp";
    if (anim_path.size() < tail.size() || anim_path.compare(anim_path.size() - tail.size(), tail.size(), tail) != 0) {
        return "";
    }
    return anim_path.substr(0, anim_path.size() - tail.size()) + ".sound.sexp";
}

// clips belong to the animation's model, so styled builds (out/m-crunch) share out/m/sounds
static std::string clip_dir_for(const std::string& anim_path) {
    std::string stem = fs::path(anim_path).filename().string();
    stem = stem.substr(0, stem.find('.'));
    return (fs::path(anim_path).parent_path().parent_path().parent_path() / "out" / stem / "sounds").string();
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
        if (a.animated) {
            gait_prepare(a.anim, a.rig);
            fx_prepare(a.anim, a.rig);
            std::string bank = bank_path_for(anim_path);
            if (!bank.empty() && fs::exists(bank) && load_sound_bank(bank, clip_dir_for(anim_path), a.sound)) {
                sound_prepare(a.sound, a.anim);
            }
        }
    }
    out = std::move(a);
    return true;
}

void asset_pose(const Asset& a, float t, Pose& out) {
    if (a.animated) {
        evaluate(a.anim, a.rig, t, out);
        fx_evaluate(a.anim, t, out);
    } else {
        rest_pose(a.rig, out);
    }
}

static int64_t stamp_of(const std::string& path) {
    std::error_code ec;
    auto t = fs::last_write_time(path, ec);
    return ec ? 0 : (int64_t)t.time_since_epoch().count();
}

// a sum of every file's modification time: any change changes it (file clock counts can
// be negative, and missing files count 0, so a max would miss changes)
int64_t asset_stamp(const Asset& a) {
    int64_t s = model_stamp(a.obj_path);
    s += stamp_of(rig_path_for(a.obj_path));
    if (!a.anim_path.empty()) {
        s += stamp_of(a.anim_path);
        s += stamp_of(bank_path_for(a.anim_path));
        std::error_code ec;
        for (const auto& e : fs::directory_iterator(clip_dir_for(a.anim_path), ec)) {
            s += stamp_of(e.path().string());
        }
    }
    return s;
}
