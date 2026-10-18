#pragma once

// Event-driven rigid animation, read from an .anim.sexp file.
//
// A fire-rate curve decides when shots happen; tracks react to shots (kick, step, feed,
// throw) or follow a driver continuously (shake, wave, glow). Contributions are summed
// per part, then turned into one matrix per part for the vertex shader.

#include "gait.hpp"
#include "rig.hpp"
#include "vec.hpp"

#include <string>
#include <vector>

enum class Ease { linear, smooth, expo_in, expo_out, expo_inout, superexp, back, spring, critical };

// an ease, optionally blended with a second one: (mix expo-out back 0.3)
struct EaseSpec {
    Ease a = Ease::linear;
    Ease b = Ease::linear;
    float w = 0.0f;
};

// smoulder = heat * idle: hot but no longer firing; curve = a named (curve ...) of the anim
enum class Driver { one, rate, heat, idle, smoulder, curve, speed, throttle };

struct Drive {
    Driver driver = Driver::one;
    int curve = -1;
    float k = 1.0f;
    bool eased = false;
    EaseSpec ease;
};

// what a track does to a part at full strength
struct Motion {
    Vec3 move;
    Vec3 rot_axis = {0, 0, 1};
    float rot_deg = 0;
    float scale = 0;
    bool has_scale = false;
    Vec3 glow;
    Vec3 uv; // slides the part's tile texture (x = u, y = v)
};

enum class TrackKind { rest, kick, step, feed, throw_, shake, wave, glow, lean, wisp, puff, spark, sound, hum, lamp };

struct Track {
    TrackKind kind = TrackKind::kick;
    std::vector<int> parts;
    float spread0 = 1, spread1 = 1; // weight across the part list, first to last
    Motion motion;
    // shot filter: shots whose index % every == offset
    int every = 1, offset = 0;
    float at = -1; // a kick at this time instead of on shots
    // kick envelope
    float attack = 0.01f, release = 0.2f;
    EaseSpec attack_ease = {Ease::expo_out}, release_ease = {Ease::expo_out};
    float spring_hz = 10, spring_damp = 0.3f;
    float vary = 0;                 // per-shot strength jitter, 0..1
    Vec3 roll_axis;                 // per-shot random spin (degrees in roll_deg)
    float roll_deg = 0;
    // step / feed
    float over = 0.05f;
    EaseSpec over_ease = {Ease::expo_out};
    int path = -1;
    // throw
    Vec3 vel, jitter;
    float gravity = -4, spin = 720, life = 1;
    // continuous
    Drive by;
    float freq = 1;
    // effects (wisp, puff, spark): emitted from `from` (model space at rest) carried by parts[0]
    Vec3 from;
    Vec3 color = {0.7f, 0.72f, 0.75f};
    float alpha = 0.5f;
    float rise = 0.3f, accel = 0;     // upward speed and its growth
    float curl = 0.05f, curl_hz = 0.7f; // sideways meander of a wisp
    Vec3 wind;
    float size0 = 0.05f, size1 = 0.3f, grow = 0.4f; // sprite or ribbon width over life
    int count = 6, points = 48;
    float fwd = 1, spread = 0.3f, up = 0; // puff/spark launch: along dir, random, upward
    Vec3 dir = {-1, 0, 0};                 // launch direction in the part's frame (default: out the muzzle)
    float drag = 3;
    float warm = 0.06f;                    // seconds a fresh puff stays lit by the flash
    // sound (on shots or at a time) and hum (a loop following `by`): the cue to play
    std::string cue;
    float gain = 1, pan = 0, pitch_lo = 1, pitch_hi = 1;
    // where the emitter was, sampled at load: a table over the loop, and at each shot
    std::vector<Vec3> path_pos, path_fwd, shot_pos, shot_fwd;
};

struct Anim {
    float length = 4;
    std::vector<Track> tracks;
    // fire rate segments (t0 t1 v0 v1 ease)
    struct Seg {
        float t0, t1, v0, v1;
        EaseSpec ease;
    };
    std::vector<Seg> rate;
    // named curves any track can be driven by: (curve spin (seg t0 t1 from to ease)...)
    struct NamedCurve {
        std::string name;
        std::vector<Seg> segs;
        std::vector<float> table;
    };
    std::vector<NamedCurve> curves;
    float heat_gain = 0.04f, heat_cool = 1.5f;
    // tables built at load
    std::vector<float> shots; // times in one loop
    float table_dt = 1.0f / 480.0f;
    std::vector<float> rate_table, heat_table, idle_table;
    std::vector<float> speed_table; // the gait's ground speed (m/s), for (by speed k)
    std::vector<float> throttle_table; // 0..1: opens as it gets moving, closes as it slows
    std::vector<float> ground_table;   // ground travelled since the loop began (m); empty if standing
    float ground_total = 0;            // ground travelled over one loop
    Gait gait; // (gait ...): legged locomotion with IK
};

bool load_anim(const std::string& path, const Rig& rig, Anim& out);

// smoke and sparks for one frame, in model space
struct FxSprite {
    Vec3 pos;
    float size, angle;
    Vec3 color; // linear
    float alpha; // 0 makes it purely additive (sparks)
    int tile;
};

struct FxRibbon {
    std::vector<Vec3> pts;
    std::vector<float> width, alpha;
    Vec3 color;
};

// per-part matrices for time t (seconds, wrapped into the loop)
struct Pose {
    std::vector<Mat4> bones;
    std::vector<Vec3> glow;
    std::vector<Vec3> uv; // tile texture offsets per part
    bool ground_on = false; // a gait is running: draw the ground, scrolled by `ground`
    float ground = 0;
    float ground_period = 1.5f;
    std::vector<FxSprite> sprites;
    std::vector<FxRibbon> ribbons;
};

void evaluate(const Anim& anim, const Rig& rig, float t, Pose& out);
// the rest pose, for models without animation
void rest_pose(const Rig& rig, Pose& out);
// samples effect emitters over the loop (needs the finished anim); and the effects at t
void fx_prepare(Anim& anim, const Rig& rig);
void fx_evaluate(const Anim& anim, float t, Pose& out);
float ease(const EaseSpec& e, float t);
