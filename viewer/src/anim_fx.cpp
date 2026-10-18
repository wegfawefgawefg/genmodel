// smoke wisps, blast puffs, sparks and dust, evaluated from time alone (no simulation state),
// so scrubbing, looping and headless video all see the same smoke
#include "anim.hpp"
#include "anim_util.hpp"

#include <cmath>

namespace {

const float fx_dt = 1.0f / 120.0f;
const float tau = 6.2831853f;

bool is_fx(const Track& t) {
    return t.kind == TrackKind::wisp || t.kind == TrackKind::puff || t.kind == TrackKind::spark || t.kind == TrackKind::lamp;
}

bool follows_path(const Track& t) { return t.kind == TrackKind::wisp || t.kind == TrackKind::lamp; }

// emitter position and launch direction (the track's dir in the part's frame) under a pose
void emitter(const Track& t, const Pose& pose, Vec3& pos, Vec3& fwd) {
    int part = t.parts.empty() ? 0 : t.parts[0];
    pos = apply_point(pose.bones[part], t.from);
    fwd = norm(apply_dir(pose.bones[part], t.dir));
}

Vec3 lerp(Vec3 a, Vec3 b, float f) { return a + (b - a) * f; }

Vec3 sample(const std::vector<Vec3>& tab, float t) {
    float x = t / fx_dt;
    int i = std::clamp((int)x, 0, (int)tab.size() - 2);
    return lerp(tab[i], tab[i + 1], std::clamp(x - i, 0.0f, 1.0f));
}

float smooth01(float x) {
    x = std::clamp(x, 0.0f, 1.0f);
    return x * x * (3 - 2 * x);
}

// a rising ribbon: every parcel remembers when it left the muzzle, so the meander
// (a function of that time) travels up the stream like cigarette smoke
void run_wisp(const Anim& a, const Track& t, float now, Pose& out) {
    FxRibbon r;
    r.color = t.color;
    float any = 0;
    for (int k = 0; k < t.points; k++) {
        float age = t.life * (float)k / (float)(t.points - 1);
        float born = wrap_time(a, now - age);
        float strength = drive(a, t.by, born);
        Vec3 base = sample(t.path_pos, born);
        float amp = t.curl * age * (0.4f + age);
        float w = tau * t.curl_hz;
        float ox = std::sin(w * born + age * 1.7f) + 0.45f * std::sin(w * 2.3f * born + age * 3.1f + 1.0f);
        float oz = std::sin(w * 0.8f * born + 2.0f + age * 1.3f) + 0.35f * std::sin(w * 1.9f * born + age * 2.2f);
        // once out, the smoke is left on the ground, which slides back under a walking body
        float carried = ground_at(a, now) - ground_at(a, now - age);
        Vec3 p = base + Vec3{0, t.rise * age + 0.5f * t.accel * age * age, -carried} + t.wind * age + Vec3{ox, 0, oz} * amp;
        float alpha = t.alpha * strength * smooth01(age / 0.12f) * std::pow(1 - age / t.life, 1.6f);
        r.pts.push_back(p);
        r.width.push_back(t.size0 + (t.size1 - t.size0) * (1 - std::exp(-age / t.grow)));
        r.alpha.push_back(std::clamp(alpha, 0.0f, 1.0f));
        any += alpha;
    }
    // relax kinks left by sudden muzzle moves; the root stays on the muzzle
    for (int pass = 0; pass < 4; pass++) {
        std::vector<Vec3> p = r.pts;
        for (size_t i = 1; i + 1 < p.size(); i++) {
            r.pts[i] = p[i] * 0.5f + (p[i - 1] + p[i + 1]) * 0.25f;
        }
    }
    if (any > 0.01f) {
        out.ribbons.push_back(std::move(r));
    }
}

// a glowing lamp with a persistent afterglow: the light now, plus fading copies where it
// was over the last `life` seconds, so it streaks when the body moves
void run_lamp(const Anim& a, const Track& t, float now, Pose& out) {
    float level = drive(a, t.by, now);
    if (level <= 0.001f) return;
    int n = std::max(t.count, 1);
    for (int k = n - 1; k >= 0; k--) {
        float back = t.life * (float)k / (float)n;
        float fade = 1 - (float)k / (float)n;
        FxSprite s;
        s.pos = sample(t.path_pos, wrap_time(a, now - back)) - Vec3{0, 0, ground_at(a, now) - ground_at(a, now - back)};
        s.size = t.size0 * (k == 0 ? 1.0f : 0.8f);
        s.angle = 0;
        s.color = t.color * (level * fade * fade * (k == 0 ? 1.6f : 0.7f));
        s.alpha = 0;
        s.tile = 3;
        out.sprites.push_back(s);
    }
}

// shot-launched particles; spark = additive and falling, puff = smoke that drags to a stop
void run_burst(const Anim& a, const Track& t, float now, Pose& out) {
    bool spark = t.kind == TrackKind::spark;
    for (size_t i = 0; i < a.shots.size(); i++) {
        if ((int)i % t.every != t.offset % t.every) continue;
        float age = now - a.shots[i];
        if (age < 0) age += a.length; // late shots of the last loop still drifting
        if (age >= t.life) continue;
        Vec3 p0 = t.shot_pos[i], fwd = t.shot_fwd[i];
        for (int j = 0; j < t.count; j++) {
            uint32_t seed = (uint32_t)i * 977u + (uint32_t)j * 31u;
            float h[8];
            for (int k = 0; k < 8; k++) h[k] = hash01(seed, (uint32_t)k + 11u * (uint32_t)t.kind);
            Vec3 dir = norm(Vec3{h[0] * 2 - 1, h[1] * 2 - 1, h[2] * 2 - 1});
            Vec3 v0 = fwd * (t.fwd * (0.45f + 0.9f * h[3])) + dir * (t.spread * (0.3f + 0.7f * h[4])) + Vec3{0, t.up, 0};
            float slow = (1 - std::exp(-t.drag * age)) / t.drag;
            float fall = spark ? 0.5f * t.rise * age * age : t.rise * age;
            Vec3 p = p0 + v0 * slow + Vec3{0, fall, 0} + t.wind * age;
            float life_f = age / t.life;
            FxSprite s;
            s.pos = p;
            s.angle = h[5] * tau + (h[6] - 0.5f) * 1.6f * age;
            s.tile = spark ? 3 : (int)((i + j) % 3);
            float size = t.size0 + (t.size1 - t.size0) * (1 - std::exp(-age / t.grow));
            s.size = size * (0.7f + 0.6f * h[7]);
            if (spark) {
                float bright = (1 - life_f) * (1 - life_f);
                s.color = t.color * (bright * (0.6f + 0.8f * h[6]));
                s.alpha = 0;
            } else {
                // freshly blown smoke is lit by the flash, then settles to its own grey
                float lit = 1 - smooth01(age / t.warm);
                s.color = lerp(t.color, Vec3{1.6f, 0.75f, 0.3f}, lit);
                s.alpha = t.alpha * smooth01(age / 0.05f) * (1 - life_f) * (1 - life_f) * (0.6f + 0.4f * h[2]);
            }
            out.sprites.push_back(s);
        }
    }
}

} // namespace

void fx_prepare(Anim& a, const Rig& rig) {
    bool any_wisp = false, any_burst = false;
    for (Track& t : a.tracks) {
        if (!is_fx(t)) continue;
        t.path_pos.clear(), t.path_fwd.clear(), t.shot_pos.clear(), t.shot_fwd.clear();
        any_wisp |= follows_path(t);
        any_burst |= !follows_path(t);
    }
    Pose pose;
    Vec3 p, f;
    // one pose per sample time feeds every emitter at once
    if (any_wisp) {
        int n = (int)std::ceil(a.length / fx_dt) + 2;
        for (int i = 0; i < n; i++) {
            evaluate(a, rig, i * fx_dt, pose);
            for (Track& t : a.tracks) {
                if (!follows_path(t)) continue;
                emitter(t, pose, p, f);
                t.path_pos.push_back(p);
                t.path_fwd.push_back(f);
            }
        }
    }
    // smoke doesn't jump with the recoil: low-pass each wisp's path around the loop
    for (Track& t : a.tracks) {
        if (t.kind != TrackKind::wisp || t.path_pos.empty()) continue;
        int n = (int)t.path_pos.size(), half = (int)(0.08f / fx_dt);
        std::vector<Vec3> smooth(n);
        for (int i = 0; i < n; i++) {
            Vec3 sum;
            for (int k = -half; k <= half; k++) {
                sum = sum + t.path_pos[((i + k) % n + n) % n];
            }
            smooth[i] = sum * (1.0f / (2 * half + 1));
        }
        t.path_pos = smooth;
    }
    if (any_burst) {
        for (float shot : a.shots) {
            evaluate(a, rig, shot, pose);
            for (Track& t : a.tracks) {
                if (t.kind != TrackKind::puff && t.kind != TrackKind::spark) continue;
                emitter(t, pose, p, f);
                t.shot_pos.push_back(p);
                t.shot_fwd.push_back(f);
            }
        }
    }
}

void fx_evaluate(const Anim& a, float t, Pose& out) {
    out.sprites.clear();
    out.ribbons.clear();
    t = wrap_time(a, t);
    for (const Track& tr : a.tracks) {
        if (tr.kind == TrackKind::lamp && tr.path_pos.size() > 1) {
            run_lamp(a, tr, t, out);
        } else if (tr.kind == TrackKind::wisp && tr.path_pos.size() > 1) {
            run_wisp(a, tr, t, out);
        } else if ((tr.kind == TrackKind::puff || tr.kind == TrackKind::spark) && tr.shot_pos.size() == a.shots.size()) {
            run_burst(a, tr, t, out);
        }
    }
}
