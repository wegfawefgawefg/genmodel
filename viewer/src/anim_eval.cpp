// turns an Anim and a time into one matrix per rig part
#include "anim.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace {

const float deg = 3.14159265f / 180.0f;

float clamp01(float t) { return std::clamp(t, 0.0f, 1.0f); }

float ease_one(Ease e, float t) {
    t = clamp01(t);
    switch (e) {
    case Ease::linear:
        return t;
    case Ease::smooth:
        return t * t * (3 - 2 * t);
    case Ease::expo_in:
        return (std::exp2(10 * t) - 1) / 1023.0f;
    case Ease::expo_out:
        return (1 - std::exp2(-10 * t)) / (1 - 1.0f / 1024.0f);
    case Ease::expo_inout:
        return t < 0.5f ? (std::exp2(20 * t - 10) - 1.0f / 1024.0f) * 0.5f
                        : 1 - (std::exp2(-20 * t + 10) - 1.0f / 1024.0f) * 0.5f;
    case Ease::superexp: {
        // double exponential: idles near zero, then runs away
        const float a = 2.2f;
        return (std::exp(std::exp(a * t) - 1) - 1) / (std::exp(std::exp(a) - 1) - 1);
    }
    case Ease::back: {
        const float c = 2.2f;
        float u = t - 1;
        return 1 + (c + 1) * u * u * u + c * u * u;
    }
    case Ease::spring:
        return 1 - std::exp(-6 * t) * std::cos(15 * t);
    }
    return t;
}

// integer hash -> [0, 1)
float hash01(uint32_t a, uint32_t b) {
    uint32_t h = a * 0x9E3779B1u ^ (b + 0x7F4A7C15u) * 0x85EBCA77u;
    h ^= h >> 15;
    h *= 0x2C1B3C6Du;
    h ^= h >> 12;
    h *= 0x297A2D39u;
    h ^= h >> 15;
    return (float)(h & 0xFFFFFF) / (float)0x1000000;
}

// smooth 1d value noise in [-1, 1]
float noise1(float x, uint32_t seed) {
    float i = std::floor(x);
    float f = x - i;
    float u = f * f * (3 - 2 * f);
    float a = hash01((uint32_t)(int32_t)i, seed) * 2 - 1;
    float b = hash01((uint32_t)(int32_t)i + 1, seed) * 2 - 1;
    return a + (b - a) * u;
}

float table_at(const std::vector<float>& tab, float dt, float t) {
    if (tab.empty()) {
        return 0;
    }
    float x = t / dt;
    int i = std::clamp((int)x, 0, (int)tab.size() - 2);
    float f = clamp01(x - i);
    return tab[i] * (1 - f) + tab[i + 1] * f;
}

float drive(const Anim& a, const Drive& d, float t) {
    float v = 1;
    if (d.driver == Driver::rate) v = table_at(a.rate_table, a.table_dt, t);
    if (d.driver == Driver::heat) v = table_at(a.heat_table, a.table_dt, t);
    if (d.driver == Driver::idle) v = table_at(a.idle_table, a.table_dt, t);
    v *= d.k;
    return d.eased ? ease(d.ease, clamp01(v)) : v;
}

struct Acc {
    Vec3 move, rot, glow;
    float scale = 1;
};

float weight(const Track& t, size_t k) {
    float f = t.parts.size() > 1 ? (float)k / (float)(t.parts.size() - 1) : 0;
    return t.spread0 + (t.spread1 - t.spread0) * f;
}

bool passes(const Track& t, int shot) { return shot % t.every == t.offset % t.every; }

// filtered shots with index <= last
int filtered_count(const Track& t, int last) {
    int off = t.offset % t.every;
    return last < off ? 0 : (last - off) / t.every + 1;
}

// first shot at or after time t0
int first_shot(const Anim& a, float t0) {
    return (int)(std::lower_bound(a.shots.begin(), a.shots.end(), t0) - a.shots.begin());
}

int last_shot(const Anim& a, float t) {
    return (int)(std::upper_bound(a.shots.begin(), a.shots.end(), t) - a.shots.begin()) - 1;
}

void add(Acc& acc, const Motion& m, float k) {
    acc.move = acc.move + m.move * k;
    acc.rot = acc.rot + m.rot_axis * (m.rot_deg * deg * k);
    acc.scale += m.scale * k;
    acc.glow = acc.glow + m.glow * k;
}

float envelope(const Track& t, float tau) {
    if (tau < 0) {
        return 0;
    }
    if (tau < t.attack) {
        return ease(t.attack_ease, tau / t.attack);
    }
    float r = tau - t.attack;
    if (r >= t.release) {
        return 0;
    }
    if (t.release_ease.a == Ease::spring) {
        float w = 2 * 3.14159265f * t.spring_hz;
        float z = std::min(t.spring_damp, 0.99f);
        float wd = w * std::sqrt(1 - z * z);
        float tail = 1 - ease_one(Ease::smooth, (r / t.release - 0.7f) / 0.3f);
        return std::exp(-z * w * r) * std::cos(wd * r) * tail;
    }
    return 1 - ease(t.release_ease, r / t.release);
}

void run_kick(const Anim& a, const Track& t, float now, std::vector<Acc>& acc) {
    if (t.at >= 0) {
        float strength = envelope(t, now - t.at);
        for (size_t k = 0; k < t.parts.size(); k++) {
            add(acc[t.parts[k]], t.motion, strength * weight(t, k));
        }
        return;
    }
    int last = last_shot(a, now);
    int latest = -1;
    for (int i = first_shot(a, now - t.attack - t.release); i <= last; i++) {
        if (!passes(t, i)) continue;
        float strength = envelope(t, now - a.shots[i]) * (1 + t.vary * (hash01(i, 77) * 2 - 1));
        for (size_t k = 0; k < t.parts.size(); k++) {
            add(acc[t.parts[k]], t.motion, strength * weight(t, k));
        }
        latest = i;
    }
    // a random turn per shot, held while that shot is live (flash orientation)
    if (latest >= 0 && t.roll_deg != 0) {
        float ang = (hash01(latest, 91) * 2 - 1) * t.roll_deg * deg;
        for (int p : t.parts) {
            acc[p].rot = acc[p].rot + t.roll_axis * ang;
        }
    }
}

// whole steps done so far plus the easing of steps still in progress
float step_progress(const Anim& a, const Track& t, float now) {
    int done_last = last_shot(a, now - t.over);
    float total = (float)filtered_count(t, done_last);
    int last = last_shot(a, now);
    for (int i = done_last + 1; i <= last; i++) {
        if (passes(t, i)) total += ease(t.over_ease, (now - a.shots[i]) / t.over);
    }
    return total;
}

void run_throw(const Anim& a, const Track& t, float now, std::vector<Acc>& acc) {
    size_t n = t.parts.size();
    if (n == 0) return;
    std::vector<bool> taken(n, false);
    int last = last_shot(a, now);
    for (int i = last; i >= 0 && now - a.shots[i] < t.life; i--) {
        if (!passes(t, i)) continue;
        int ordinal = (i - t.offset % t.every) / t.every;
        size_t j = (size_t)ordinal % n;
        if (taken[j]) continue;
        taken[j] = true;
        float tau = now - a.shots[i];
        Vec3 r = {hash01(i, 1) * 2 - 1, hash01(i, 2) * 2 - 1, hash01(i, 3) * 2 - 1};
        Vec3 v = t.vel + Vec3{t.jitter.x * r.x, t.jitter.y * r.y, t.jitter.z * r.z};
        Acc& c = acc[t.parts[j]];
        c.move = c.move + v * tau + Vec3{0, 0.5f * t.gravity * tau * tau, 0};
        Vec3 axis = norm(Vec3{hash01(i, 4) - 0.5f, hash01(i, 5) - 0.5f, hash01(i, 6) - 0.5f + 0.8f});
        c.rot = c.rot + axis * (t.spin * deg * tau * (0.6f + 0.8f * hash01(i, 7)));
        // pop out of the port, shrink away at the end of life
        float in = ease_one(Ease::expo_out, tau / 0.03f);
        float out = 1 - ease_one(Ease::smooth, (tau / t.life - 0.8f) / 0.2f);
        c.scale += in * out;
    }
}

void run_continuous(const Anim& a, const Track& t, float now, std::vector<Acc>& acc) {
    float amp = drive(a, t.by, now);
    for (size_t k = 0; k < t.parts.size(); k++) {
        int p = t.parts[k];
        float w = amp * weight(t, k);
        if (t.kind == TrackKind::glow) {
            acc[p].glow = acc[p].glow + t.motion.glow * w;
            continue;
        }
        if (t.kind == TrackKind::lean) {
            add(acc[p], t.motion, w);
            continue;
        }
        if (t.kind == TrackKind::wave) {
            float s = std::sin(2 * 3.14159265f * t.freq * now + p * 1.7f);
            add(acc[p], t.motion, s * w);
            continue;
        }
        // shake: independent smooth noise per axis
        float x = now * t.freq;
        uint32_t seed = (uint32_t)p * 16 + (uint32_t)(&t - &a.tracks[0]) * 512;
        Vec3 n = {noise1(x, seed + 1), noise1(x, seed + 2), noise1(x, seed + 3)};
        Motion m = t.motion;
        acc[p].move = acc[p].move + Vec3{m.move.x * n.x, m.move.y * n.y, m.move.z * n.z} * w;
        acc[p].rot = acc[p].rot + m.rot_axis * (m.rot_deg * deg * noise1(x, seed + 4) * w);
    }
}

Mat4 part_local(const RigPart& part, const Acc& a) {
    return translate(part.pivot + a.move) * rotate(a.rot) * scale(std::max(a.scale, 0.0f)) *
           translate(part.pivot * -1.0f);
}

// links ride the bent path: placed by arc length, fading in and out at the ends
void place_links(const Rig& rig, const RigPath& ph, float feed, std::vector<Mat4>& world) {
    Mat4 parent = ph.parent >= 0 ? world[ph.parent] : Mat4{};
    Mat4 anchor = ph.anchor >= 0 ? world[ph.anchor] : parent;
    Vec3 bent[4] = {apply_point(anchor, ph.points[0]), ph.points[1], ph.points[2], apply_point(parent, ph.points[3])};
    for (int h = 0; h < 2; h++) {
        bent[h + 1] = ph.handle[h] >= 0 ? apply_point(world[ph.handle[h]], ph.points[h + 1])
                                        : apply_point(parent, ph.points[h + 1]);
    }
    Curve rest = make_curve(ph.points);
    Curve now = make_curve(bent);
    Vec3 across = apply_dir(parent, ph.across);
    float span = ph.pitch * (float)ph.links.size();
    for (size_t i = 0; i < ph.links.size(); i++) {
        if (ph.links[i] < 0) continue;
        float rel = std::fmod(i * ph.pitch + feed * ph.pitch, span);
        if (rel < 0) rel += span;
        float k = ease_one(Ease::smooth, std::min(rel, span - rel) / ph.pitch);
        Mat4 from = curve_frame(rest, ph.start + i * ph.pitch, ph.across);
        Mat4 to = curve_frame(now, ph.start + rel, across);
        world[ph.links[i]] = to * scale(k) * inverse_rigid(from);
    }
    (void)rig;
}

} // namespace

float ease(const EaseSpec& e, float t) {
    float a = ease_one(e.a, t);
    return e.w > 0 ? a + (ease_one(e.b, t) - a) * e.w : a;
}

void rest_pose(const Rig& rig, Pose& out) {
    out.bones.assign(rig.parts.size(), Mat4{});
    out.glow.assign(rig.parts.size(), Vec3{});
}

void evaluate(const Anim& a, const Rig& rig, float t, Pose& out) {
    t = std::fmod(t, a.length);
    if (t < 0) t += a.length;
    std::vector<Acc> acc(rig.parts.size());
    std::vector<float> feed(rig.paths.size(), 0);

    // rest values first, then everything that adds on top
    for (const Track& tr : a.tracks) {
        if (tr.kind != TrackKind::rest) continue;
        for (int p : tr.parts) {
            if (tr.motion.has_scale) acc[p].scale = tr.motion.scale;
            acc[p].move = acc[p].move + tr.motion.move;
            acc[p].glow = acc[p].glow + tr.motion.glow;
        }
    }
    for (const Track& tr : a.tracks) {
        switch (tr.kind) {
        case TrackKind::rest:
            break;
        case TrackKind::kick:
            run_kick(a, tr, t, acc);
            break;
        case TrackKind::step: {
            float s = step_progress(a, tr, t);
            for (size_t k = 0; k < tr.parts.size(); k++) {
                add(acc[tr.parts[k]], tr.motion, s * weight(tr, k));
            }
            break;
        }
        case TrackKind::feed:
            if (tr.path >= 0) feed[tr.path] += step_progress(a, tr, t);
            break;
        case TrackKind::throw_:
            run_throw(a, tr, t, acc);
            break;
        default:
            run_continuous(a, tr, t, acc);
        }
    }

    // parents come before children in the rig file
    out.bones.resize(rig.parts.size());
    out.glow.resize(rig.parts.size());
    for (size_t i = 0; i < rig.parts.size(); i++) {
        Mat4 local = part_local(rig.parts[i], acc[i]);
        int p = rig.parts[i].parent;
        out.bones[i] = p >= 0 && p < (int)i ? out.bones[p] * local : local;
        out.glow[i] = acc[i].glow;
    }
    for (size_t i = 0; i < rig.paths.size(); i++) {
        place_links(rig, rig.paths[i], feed[i], out.bones);
    }
}
