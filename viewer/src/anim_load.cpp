// reads .anim.sexp files and precomputes the fire-rate tables
#include "anim.hpp"
#include "sexp_read.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>

namespace {

Ease ease_named(const std::string& s) {
    if (s == "smooth") return Ease::smooth;
    if (s == "expo-in") return Ease::expo_in;
    if (s == "expo-out") return Ease::expo_out;
    if (s == "expo-inout") return Ease::expo_inout;
    if (s == "superexp") return Ease::superexp;
    if (s == "back") return Ease::back;
    if (s == "spring") return Ease::spring;
    return Ease::linear;
}

// an atom like expo-out, or (mix a b w)
EaseSpec read_ease(gsexp::Node n) {
    EaseSpec e;
    if (head_of(n) == "mix") {
        e.a = ease_named(std::string(n.child_at(1).text()));
        e.b = ease_named(std::string(n.child_at(2).text()));
        e.w = num(n.child_at(3), 0.5f);
        return e;
    }
    e.a = ease_named(std::string(n.text()));
    return e;
}

Driver driver_named(const std::string& s) {
    if (s == "rate") return Driver::rate;
    if (s == "heat") return Driver::heat;
    if (s == "idle") return Driver::idle;
    if (s == "smoulder") return Driver::smoulder;
    return Driver::one;
}

// part names, with "prefix.*" matching every numbered copy in order
void add_targets(const Rig& rig, const std::string& name, std::vector<int>& out) {
    if (name.size() > 2 && name.compare(name.size() - 2, 2, ".*") == 0) {
        std::string prefix = name.substr(0, name.size() - 1);
        for (int i = 0;; i++) {
            int p = find_part(rig, prefix + std::to_string(i));
            if (p < 0) {
                break;
            }
            out.push_back(p);
        }
        return;
    }
    int p = find_part(rig, name);
    if (p < 0) {
        fprintf(stderr, "anim: no part named %s\n", name.c_str());
        return;
    }
    out.push_back(p);
}

// (rot ax ay az deg)
void read_motion_field(gsexp::Node c, const std::string& h, Motion& m) {
    if (h == "move") {
        m.move = vec_at(c, 1);
    } else if (h == "rot") {
        m.rot_axis = norm(vec_at(c, 1));
        m.rot_deg = num(c.child_at(4));
    } else if (h == "scale") {
        m.scale = num(c.child_at(1));
        m.has_scale = true;
    } else if (h == "glow") {
        m.glow = vec_at(c, 1);
    }
}

TrackKind kind_named(const std::string& s, bool& ok) {
    ok = true;
    if (s == "rest") return TrackKind::rest;
    if (s == "kick") return TrackKind::kick;
    if (s == "step") return TrackKind::step;
    if (s == "feed") return TrackKind::feed;
    if (s == "throw") return TrackKind::throw_;
    if (s == "shake") return TrackKind::shake;
    if (s == "wave") return TrackKind::wave;
    if (s == "glow") return TrackKind::glow;
    if (s == "lean") return TrackKind::lean;
    if (s == "wisp") return TrackKind::wisp;
    if (s == "puff") return TrackKind::puff;
    if (s == "spark") return TrackKind::spark;
    if (s == "sound") return TrackKind::sound;
    if (s == "hum") return TrackKind::hum;
    ok = false;
    return TrackKind::kick;
}

// (kick part... (field ...)...): bare atoms after the head are targets
bool read_track(gsexp::Node form, const Rig& rig, int every, int offset, Track& t) {
    bool ok;
    t.kind = kind_named(head_of(form), ok);
    if (!ok) {
        return false;
    }
    t.every = every;
    t.offset = offset;
    for (size_t i = 1; i < form.child_count(); i++) {
        gsexp::Node c = form.child_at(i);
        if (!c.is_list()) {
            std::string name(c.text());
            if (t.kind == TrackKind::sound || t.kind == TrackKind::hum) {
                t.cue = name;
            } else if (t.kind == TrackKind::feed) {
                for (size_t p = 0; p < rig.paths.size(); p++) {
                    if (rig.paths[p].name == name) {
                        t.path = (int)p;
                    }
                }
            } else {
                add_targets(rig, name, t.parts);
            }
            continue;
        }
        std::string h = head_of(c);
        read_motion_field(c, h, t.motion);
        if (h == "spread") {
            t.spread0 = num(c.child_at(1), 1);
            t.spread1 = num(c.child_at(2), 1);
        } else if (h == "attack") {
            t.attack = num(c.child_at(1), 0.01f);
            if (c.child_count() > 2) t.attack_ease = read_ease(c.child_at(2));
        } else if (h == "release") {
            // (release secs ease) or (release secs spring hz damping)
            t.release = num(c.child_at(1), 0.2f);
            if (c.child_count() > 2) t.release_ease = read_ease(c.child_at(2));
            if (t.release_ease.a == Ease::spring) {
                t.spring_hz = num(c.child_at(3), 10);
                t.spring_damp = num(c.child_at(4), 0.3f);
            }
        } else if (h == "over") {
            t.over = num(c.child_at(1), 0.05f);
            if (c.child_count() > 2) t.over_ease = read_ease(c.child_at(2));
        } else if (h == "at") {
            t.at = num(c.child_at(1), -1);
        } else if (h == "vary") {
            t.vary = num(c.child_at(1));
        } else if (h == "roll") {
            t.roll_axis = norm(vec_at(c, 1));
            t.roll_deg = num(c.child_at(4));
        } else if (h == "vel") {
            t.vel = vec_at(c, 1);
        } else if (h == "jitter") {
            t.jitter = vec_at(c, 1);
        } else if (h == "gravity") {
            t.gravity = num(c.child_at(1));
        } else if (h == "spin") {
            t.spin = num(c.child_at(1));
        } else if (h == "life") {
            t.life = num(c.child_at(1), 1);
        } else if (h == "from") {
            t.from = vec_at(c, 1);
        } else if (h == "color") {
            t.color = vec_at(c, 1);
            t.alpha = num(c.child_at(4), t.alpha);
        } else if (h == "rise") {
            t.rise = num(c.child_at(1));
            t.accel = num(c.child_at(2), 0);
        } else if (h == "curl") {
            t.curl = num(c.child_at(1));
            t.curl_hz = num(c.child_at(2), t.curl_hz);
        } else if (h == "wind") {
            t.wind = vec_at(c, 1);
        } else if (h == "size") {
            t.size0 = num(c.child_at(1));
            t.size1 = num(c.child_at(2), t.size0);
            t.grow = num(c.child_at(3), t.grow);
        } else if (h == "count") {
            t.count = (int)num(c.child_at(1), 6);
        } else if (h == "points") {
            t.points = (int)num(c.child_at(1), 48);
        } else if (h == "launch") {
            t.fwd = num(c.child_at(1));
            t.spread = num(c.child_at(2));
            t.up = num(c.child_at(3));
        } else if (h == "gain") {
            t.gain = num(c.child_at(1), 1);
        } else if (h == "pan") {
            t.pan = num(c.child_at(1), 0);
        } else if (h == "pitch") {
            t.pitch_lo = num(c.child_at(1), 1);
            t.pitch_hi = num(c.child_at(2), t.pitch_lo);
        } else if (h == "dir") {
            t.dir = norm(vec_at(c, 1));
        } else if (h == "drag") {
            t.drag = num(c.child_at(1), 3);
        } else if (h == "warm") {
            t.warm = num(c.child_at(1));
        } else if (h == "freq") {
            t.freq = num(c.child_at(1), 1);
        } else if (h == "by") {
            // (by driver k [ease])
            t.by.driver = driver_named(std::string(c.child_at(1).text()));
            t.by.k = num(c.child_at(2), 1);
            if (c.child_count() > 3) {
                t.by.eased = true;
                t.by.ease = read_ease(c.child_at(3));
            }
        }
    }
    return true;
}

float rate_at(const Anim& a, float t) {
    for (const Anim::Seg& s : a.rate) {
        if (t >= s.t0 && t < s.t1) {
            float u = (t - s.t0) / std::max(s.t1 - s.t0, 1e-6f);
            return s.v0 + (s.v1 - s.v0) * ease(s.ease, u);
        }
    }
    return 0;
}

// shot times from the integrated rate, plus heat and idle tables
void build_tables(Anim& a) {
    int n = (int)std::ceil(a.length / a.table_dt) + 1;
    a.rate_table.assign(n, 0);
    a.heat_table.assign(n, 0);
    a.idle_table.assign(n, 1);
    a.shots.clear();
    float phase = 0, heat = 0, idle = 1;
    // two passes so heat and idle carry over the loop seam
    for (int pass = 0; pass < 2; pass++) {
        for (int i = 0; i < n; i++) {
            float t = i * a.table_dt;
            float r = rate_at(a, t);
            heat += (a.heat_gain * r - heat / a.heat_cool) * a.table_dt;
            float want_idle = 1.0f - std::min(r / 4.0f, 1.0f);
            idle += (want_idle - idle) * std::min(a.table_dt / 0.6f, 1.0f);
            if (pass == 1) {
                a.rate_table[i] = r;
                a.heat_table[i] = heat;
                a.idle_table[i] = idle;
                float next = phase + r * a.table_dt;
                if (std::floor(next) > std::floor(phase)) {
                    float frac = (std::floor(next) - phase) / std::max(next - phase, 1e-9f);
                    a.shots.push_back(t + frac * a.table_dt);
                }
                phase = next;
            }
        }
    }
}

} // namespace

bool load_anim(const std::string& path, const Rig& rig, Anim& out) {
    std::string text;
    if (!read_text(path, text)) {
        return false;
    }
    gsexp::ParseResult r = gsexp::parse(text);
    if (!r.ok || r.root_count() == 0) {
        print_diagnostics(path, r);
        return false;
    }
    Anim a;
    for (gsexp::Node c : r.root(0).children()) {
        std::string h = head_of(c);
        if (h == "length") {
            a.length = num(c.child_at(1), 4);
        } else if (h == "rate") {
            for (gsexp::Node s : c.children()) {
                if (head_of(s) != "seg") continue;
                Anim::Seg seg = {num(s.child_at(1)), num(s.child_at(2)), num(s.child_at(3)), num(s.child_at(4)), {}};
                if (s.child_count() > 5) seg.ease = read_ease(s.child_at(5));
                a.rate.push_back(seg);
            }
        } else if (h == "heat") {
            gsexp::FormView f(c);
            a.heat_gain = f.get_float("gain").value_or(a.heat_gain);
            a.heat_cool = f.get_float("cool").value_or(a.heat_cool);
        } else if (h == "on-shot") {
            // (on-shot (every n k) track...)
            int every = 1, offset = 0;
            for (gsexp::Node s : c.children()) {
                if (head_of(s) == "every") {
                    every = std::max(1, (int)num(s.child_at(1), 1));
                    offset = (int)num(s.child_at(2), 0);
                }
            }
            for (gsexp::Node s : c.children()) {
                Track t;
                if (s.is_list() && head_of(s) != "every" && read_track(s, rig, every, offset, t)) {
                    a.tracks.push_back(t);
                }
            }
        } else if (c.is_list()) {
            Track t;
            if (read_track(c, rig, 1, 0, t)) {
                a.tracks.push_back(t);
            }
        }
    }
    build_tables(a);
    printf("anim %s: %zu tracks, %zu shots in %.2fs\n", path.c_str(), a.tracks.size(), a.shots.size(), a.length);
    out = std::move(a);
    return true;
}
