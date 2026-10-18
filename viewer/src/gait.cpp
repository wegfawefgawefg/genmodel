#include "gait.hpp"

#include "anim.hpp"
#include "rig.hpp"

#include <algorithm>
#include <cmath>

namespace {

const float pi = 3.14159265f;
const float deg = pi / 180.0f;

float smooth(float a, float b, float x) {
    float t = std::clamp((x - a) / (b - a), 0.0f, 1.0f);
    return t * t * (3 - 2 * t);
}

// minimum-jerk position profile: zero speed and acceleration at both ends
float min_jerk(float s) {
    s = std::clamp(s, 0.0f, 1.0f);
    return s * s * s * (10 - 15 * s + 6 * s * s);
}

float lerp(float a, float b, float t) { return a + (b - a) * t; }

// critically damped response to a kick at tau = 0: rises, peaks at 1 when tau = 1 / w, settles
float impulse(float tau, float w) {
    if (tau < 0) return 0;
    float x = w * tau;
    return x * std::exp(1 - x);
}

GaitStyle mix(const GaitStyle& a, const GaitStyle& b, float t) {
    GaitStyle o;
    const float* pa = &a.speed;
    const float* pb = &b.speed;
    float* po = &o.speed;
    // every field is a float, in order
    for (size_t i = 0; i < sizeof(GaitStyle) / sizeof(float); i++) po[i] = lerp(pa[i], pb[i], t);
    return o;
}

// the style for a speed: between the two nearest styles
GaitStyle style_at(const Gait& g, float v) {
    const std::vector<GaitStyle>& s = g.styles;
    if (v <= s.front().speed) return s.front();
    for (size_t i = 0; i + 1 < s.size(); i++) {
        if (v <= s[i + 1].speed) return mix(s[i], s[i + 1], smooth(s[i].speed, s[i + 1].speed, v));
    }
    return s.back();
}

float speed_at(const Gait& g, float t) {
    for (const Gait::Seg& s : g.speed) {
        if (t >= s.t0 && t < s.t1) {
            float u = (t - s.t0) / std::max(s.t1 - s.t0, 1e-6f);
            u = u * u * (3 - 2 * u);
            return lerp(s.v0, s.v1, u);
        }
    }
    return 0;
}

// rigid motion of a foot: lifted by (0, y, z) and pitched (toes up positive) about point p
void foot_motion(Vec3 p, float y, float z, float pitch_deg, float* out) {
    float a = -pitch_deg * deg; // rotating about +x by a positive angle drops the toes
    float c = std::cos(a), s = std::sin(a);
    Vec3 rp = {p.x, c * p.y - s * p.z, s * p.y + c * p.z};
    out[0] = p.x - rp.x;
    out[1] = y + p.y - rp.y;
    out[2] = z + p.z - rp.z;
    out[3] = pitch_deg;
}

struct FootState {
    bool stance = true;
    float z = 0, swing_from = 0, swing_to = 0, rel_at_lift = 0;
    float touchdown = -100; // time of the last footfall
    float impact = 0;       // how hard it was
};

GaitSample sample_at(const Gait& g, float t) {
    float x = t / g.dt;
    int i = std::clamp((int)x, 0, (int)g.table.size() - 2);
    float f = std::clamp(x - i, 0.0f, 1.0f);
    const GaitSample& a = g.table[i];
    const GaitSample& b = g.table[i + 1];
    GaitSample o = a;
    for (int k = 0; k < body_channels; k++) o.body[k] = lerp(a.body[k], b.body[k], f);
    o.speed = lerp(a.speed, b.speed, f);
    o.ground = lerp(a.ground, b.ground, f);
    float dp = b.arm_phase - a.arm_phase; // phases wrap: interpolate the short way
    dp -= std::round(dp);
    o.arm_phase = a.arm_phase + dp * f;
    for (size_t k = 0; k < a.foot.size(); k++) o.foot[k] = lerp(a.foot[k], b.foot[k], f);
    return o;
}

Mat4 basis(Vec3 d, Vec3 n) { return frame(d, n, cross(d, n), {0, 0, 0}); }

// a second-order low-pass over one body channel: lag and a little settle, like mass on springs
void spring_filter(std::vector<GaitSample>& tab, int ch, float dt, float hz, float damp) {
    float w = 2 * pi * hz, x = 0, v = 0;
    for (int pass = 0; pass < 2; pass++) { // the second pass starts from the loop's end state
        for (GaitSample& s : tab) {
            float target = s.body[ch];
            float acc = w * w * (target - x) - 2 * damp * w * v;
            v += acc * dt;
            x += v * dt;
            if (pass == 1) s.body[ch] = x;
        }
    }
}

} // namespace

void gait_prepare(Anim& a, const Rig& rig) {
    Gait& g = a.gait;
    if (!g.on) return;
    g.body = find_part(rig, g.body_name);
    g.hips = g.hips_name.empty() ? -1 : find_part(rig, g.hips_name);
    g.head = g.head_name.empty() ? -1 : find_part(rig, g.head_name);
    for (GaitLeg& l : g.legs)
        for (int k = 0; k < 5; k++) l.part[k] = l.names[k].empty() ? -1 : find_part(rig, l.names[k]);
    for (GaitArm& m : g.arms)
        for (int k = 0; k < 2; k++) m.part[k] = find_part(rig, m.names[k]);
    for (const GaitLeg& l : g.legs) {
        if (l.part[0] < 0 || l.part[1] < 0 || l.part[2] < 0 || g.body < 0) {
            g.on = false;
            return;
        }
    }

    int n = (int)std::ceil(a.length / g.dt) + 2;
    g.table.assign(n, {});
    std::vector<FootState> feet(g.legs.size());
    float phase = 0, ground = 0;
    // the body as a mass moved by the legs' ground forces (per unit mass, metres and seconds)
    const float grav = 9.8f;
    float body_y = 0, body_vy = 0, body_z = 0, body_vz = 0;
    float force_avg = grav; // the legs' force averaged over a second or so (what holds it up)
    for (int i = 0; i < n; i++) {
        float t = i * g.dt;
        float v = speed_at(g, t);
        GaitStyle st = style_at(g, v);
        // cadence fades in with the first bit of speed, so the first steps are short shuffles
        float f = st.cadence * smooth(0.0f, 0.35f, v);
        float stride = f > 1e-4f ? std::min(v * st.duty / f, 2.6f) : 0.0f;
        float moving = smooth(0.0f, 0.7f, v);
        phase += f * g.dt;
        ground += v * g.dt;

        GaitSample s;
        s.speed = v;
        s.ground = ground;
        s.arm_phase = phase;
        float sink = 0;           // footfalls pressing the body down
        float force_y = 0, force_z = 0; // ground reaction on the body from the stance feet
        for (size_t k = 0; k < g.legs.size(); k++) {
            const GaitLeg& leg = g.legs[k];
            FootState& fs = feet[k];
            float psi = phase + leg.phase;
            psi -= std::floor(psi);
            bool stance = psi < st.duty;
            if (stance && !fs.stance) {
                fs.z = fs.swing_to;
                fs.touchdown = t;
                fs.impact = moving * (0.4f + 0.6f * smooth(0.0f, 6.0f, v)); // harder the faster
            }
            Vec3 ankle = rig.parts[leg.part[2]].pivot;
            Vec3 toe = leg.part[3] >= 0 ? rig.parts[leg.part[3]].pivot : Vec3{ankle.x, 0, ankle.z + leg.toe};
            toe.y = 0; // roll about the sole under the ball, so nothing dips into the ground
            Vec3 heel = {ankle.x, 0, ankle.z - leg.heel};
            float* out = nullptr;
            s.foot.resize(s.foot.size() + foot_channels);
            out = &s.foot[s.foot.size() - foot_channels];
            float since = t - fs.touchdown;
            float kick = impulse(since, 9.0f) * fs.impact; // the damper's stroke after a footfall
            sink += kick * st.impact;
            if (!stance && fs.stance) {
                fs.swing_from = fs.z;
                fs.swing_to = stride * 0.5f;
                fs.rel_at_lift = 0;
            }
            fs.stance = stance;
            if (stance && moving > 0.01f) {
                // vertical: a run pushes in one hump (peak mid-stance), a walk in two (load,
                // vault, push); scaled so the stance feet carry the body's weight on average
                float u = psi / std::max(st.duty, 1e-3f);
                float runish = smooth(0.58f, 0.45f, st.duty);
                float hump = std::sin(pi * u);
                float two = std::sin(pi * u) + 0.6f * std::sin(3 * pi * u);
                float shape = lerp(two / 1.4f, hump, runish); // both average about 2/pi
                float legs = (float)g.legs.size();
                force_y += grav * (pi / 2) / (legs * st.duty) * shape;
                // horizontal: braking while the foot is ahead, then the shove behind
                force_z += -st.shove * std::sin(2 * pi * u) * smooth(0.0f, 4.0f, v);
            }
            if (stance) {
                fs.z -= v * g.dt; // planted: the ground carries it back
                {
                    float side = ankle.x >= 0 ? 1.0f : -1.0f;
                    float u0 = psi / std::max(st.duty, 1e-3f);
                    out[5] = -side * st.invert * moving * (1 - smooth(0.0f, 0.2f, u0));
                }
                float u = psi / std::max(st.duty, 1e-3f);
                out[6] = st.give * moving * (0.55f * std::sin(pi * std::min(u * 1.4f, 1.0f)) + 0.8f * kick) +
                         st.strike * moving * (1 - smooth(0, 0.15f, u)) * 1.3f;
                if (u < 0.15f) {
                    // heel strike: the foot slaps down flat about its heel
                    foot_motion(heel, 0, fs.z, st.strike * moving * (1 - smooth(0, 0.15f, u)), out);
                    out[4] = st.flex * kick;
                } else {
                    // toe-off: the heel rolls up about the ball while the toes stay flat
                    float up = smooth(0.55f, 1.0f, u);
                    float pitch = -st.toe_off * moving * up * up;
                    foot_motion(toe, 0, fs.z, pitch, out);
                    out[4] = (leg.part[3] >= 0 ? -pitch : 0) + st.flex * kick;
                    fs.rel_at_lift = out[4];
                }
            } else {
                float sw = (psi - st.duty) / std::max(1 - st.duty, 1e-3f);
                // thrown out ahead of the landing spot, then pulled back to strike the ground
                float throw_out = std::pow(std::sin(pi * std::pow(sw, 1.6f)), 2.0f);
                fs.z = lerp(fs.swing_from, fs.swing_to, min_jerk(sw)) + st.reach * moving * throw_out;
                float lift = st.lift * moving * std::pow(std::sin(pi * std::pow(sw, 0.75f)), 1.2f);
                float pitch = lerp(-st.toe_off, st.strike, smooth(0.0f, 0.9f, sw)) * moving;
                // the pivot travels ball -> ankle -> heel so the foot pose stays continuous
                Vec3 p = sw < 0.5f ? toe + (ankle - toe) * (sw / 0.5f) : ankle + (heel - ankle) * ((sw - 0.5f) / 0.5f);
                p.y = sw < 0.5f ? lerp(toe.y, ankle.y, sw / 0.5f) : lerp(ankle.y, 0.0f, (sw - 0.5f) / 0.5f);
                foot_motion(p, lift, fs.z, pitch, out);
                // the toes' angle in the world: flat as they leave, pointing a little down only
                // once the foot is up, then up for the next footfall; relative to the foot
                float toes_world = moving * (-10.0f * smooth(0.2f, 0.45f, sw) * (1 - smooth(0.6f, 0.85f, sw)) +
                                             6.0f * smooth(0.65f, 1.0f, sw));
                out[4] = toes_world - pitch;
                // the spur springs open off the ground, then reaches down for the landing
                // the spur springs open off the ground, reaches a little for the landing, and folds
                // up by the foot's toes-up pitch so its tip stays clear of the ground
                out[6] = st.give * moving * (0.5f * (1 - smooth(0.0f, 0.3f, sw)) - 0.2f * smooth(0.55f, 0.9f, sw)) +
                         std::max(pitch, 0.0f) * 1.3f;
                // rolled in to meet the ground, flattening as it lands
                float side = ankle.x >= 0 ? 1.0f : -1.0f;
                out[5] = -side * st.invert * moving * smooth(0.45f, 0.85f, sw);
            }
        }

        // integrate the body: legs push, gravity pulls, posture control holds it near rest.
        // standing still the feet simply carry the weight.
        force_y = force_y * moving + grav * (1 - moving);
        // only the force's swing about its average moves the body (no slow sag or climb)
        force_avg += (force_y - force_avg) * std::min(g.dt / 1.2f, 1.0f);
        body_vy += (force_y - force_avg - 6.0f * body_y - 2.5f * body_vy) * g.dt;
        body_y += body_vy * g.dt;
        body_vz += (force_z - 3.0f * body_z - 2.0f * body_vz) * g.dt;
        body_z += body_vz * g.dt;
        float mid = phase + (g.legs.empty() ? 0 : g.legs[0].phase) - st.duty * 0.5f;
        float bob = st.bob * moving * std::cos(4 * pi * mid) + body_y;
        Vec3 hip0 = rig.parts[g.legs[0].part[0]].pivot;
        float side = hip0.x >= 0 ? 1.0f : -1.0f;
        float sway = st.sway * moving * std::cos(2 * pi * mid) * side;
        float swing_mid = st.duty + (1 - st.duty) * 0.5f;
        float twist = st.twist * moving * std::cos(2 * pi * (phase + g.legs[0].phase - swing_mid));
        s.body[0] = sway;
        s.body[1] = bob - st.crouch * moving - sink;
        s.body[2] = body_z;
        // pitching into the shove: forward as the feet push, back as they brake
        s.body[3] = st.lean * moving + 1.2f * moving * std::cos(4 * pi * mid) + 40.0f * sink + 0.9f * force_z;
        s.body[4] = -sway * 14.0f;
        s.body[5] = twist * 0.45f;     // the torso turns back against the hips
        s.body[6] = -twist * 1.45f;    // the hips relative to the torso
        // the hips drop toward the swinging leg's side (the stance hip carries the weight)
        s.body[7] = -st.twist * 0.5f * moving * std::cos(2 * pi * mid) * side;
        g.table[i] = s;
    }

    // the body lags its targets through a spring: weight, not keyframes
    for (int ch = 0; ch < body_channels; ch++) {
        if (ch != 1 && ch != 2) spring_filter(g.table, ch, g.dt, g.spring_hz, g.spring_damp);
    }

    // ease everything back to rest over the last stretch, so the loop seam is clean
    float fade0 = a.length - 0.9f, fade1 = a.length - 0.15f;
    for (int i = 0; i < n; i++) {
        float w = 1 - smooth(fade0, fade1, i * g.dt);
        GaitSample& s = g.table[i];
        for (float& x : s.body) x *= w;
        for (float& x : s.foot) x *= w;
    }
    // the speed as a driver for other tracks (flaps opening, antennas streaming...)
    a.speed_table.assign(a.rate_table.size(), 0.0f);
    for (size_t i = 0; i < a.speed_table.size(); i++) {
        float tt = i * a.table_dt;
        a.speed_table[i] = g.table[std::min((size_t)(tt / g.dt), g.table.size() - 1)].speed;
    }
    float total = g.table.back().ground;
    g.ground_period = total > 0.5f ? total / std::max(1.0f, std::round(total / 1.5f)) : 1.5f;
}

void gait_body(const Anim& a, float t, std::vector<Vec3>& move, std::vector<Vec3>& rot) {
    const Gait& g = a.gait;
    if (!g.on || g.table.empty()) return;
    GaitSample s = sample_at(g, t);
    move[g.body] = move[g.body] + Vec3{s.body[0], s.body[1], s.body[2]};
    rot[g.body] = rot[g.body] + Vec3{s.body[3] * deg, s.body[5] * deg, s.body[4] * deg};
    if (g.hips >= 0) rot[g.hips] = rot[g.hips] + Vec3{0, s.body[6] * deg, s.body[7] * deg};
    // the head holds its gaze steady against the body's pitch, roll and turn
    if (g.head >= 0) rot[g.head] = rot[g.head] + Vec3{-0.7f * s.body[3] * deg, -0.8f * s.body[5] * deg, -0.7f * s.body[4] * deg};
    GaitStyle st = style_at(g, s.speed);
    float moving = smooth(0.0f, 0.7f, s.speed);
    float swing_mid = st.duty + (1 - st.duty) * 0.5f;
    for (const GaitArm& m : g.arms) {
        if (m.part[0] < 0) continue;
        float c = std::cos(2 * pi * (s.arm_phase + m.phase - swing_mid));
        rot[m.part[0]] = rot[m.part[0]] + Vec3{-st.arms * moving * c * deg, 0, 0};
        if (m.part[1] >= 0) rot[m.part[1]] = rot[m.part[1]] + Vec3{st.elbows * moving * deg, 0, 0};
    }
}

void gait_legs(const Anim& a, const Rig& rig, float t, Pose& pose) {
    const Gait& g = a.gait;
    if (!g.on || g.table.empty()) return;
    GaitSample s = sample_at(g, t);
    pose.ground_on = true;
    pose.ground = std::fmod(s.ground, g.ground_period);
    pose.ground_period = g.ground_period;
    Vec3 pole = norm(apply_dir(pose.bones[g.body], {0, 0, 1}));
    for (size_t k = 0; k < g.legs.size(); k++) {
        const GaitLeg& leg = g.legs[k];
        const float* f = &s.foot[k * foot_channels];
        Vec3 h0 = rig.parts[leg.part[0]].pivot, k0 = rig.parts[leg.part[1]].pivot, a0 = rig.parts[leg.part[2]].pivot;
        // pitch about the table's pivot, then roll about the ankle
        Mat4 m = translate({f[0], f[1], f[2]}) * rotate({-f[3] * deg, 0, 0}) * translate(a0) *
                 rotate({0, 0, f[5] * deg}) * translate(a0 * -1.0f);
        int hip_parent = rig.parts[leg.part[0]].parent;
        Vec3 h = hip_parent >= 0 ? apply_point(pose.bones[hip_parent], h0) : h0;
        Vec3 target = apply_point(m, a0);
        float l1 = len(k0 - h0), l2 = len(a0 - k0);

        // two-bone IK: the knee on the circle of solutions, toward the pole
        Vec3 u = norm(target - h);
        float c = std::clamp(len(target - h), std::fabs(l1 - l2) + 1e-3f, l1 + l2 - 1e-3f);
        float along = (l1 * l1 - l2 * l2 + c * c) / (2 * c);
        float up = std::sqrt(std::max(l1 * l1 - along * along, 0.0f));
        Vec3 w = norm(pole - u * dot(pole, u));
        Vec3 knee = h + u * along + w * up;
        Vec3 ankle = h + u * c; // the reachable ankle (equals the target unless overstretched)

        // map the rest leg plane onto the new one, bone by bone
        Vec3 u0 = norm(a0 - h0);
        Vec3 w0 = norm((k0 - h0) - u0 * dot(k0 - h0, u0));
        Vec3 n0 = norm(cross(u0, w0)), n1 = norm(cross(u, w));
        Mat4 thigh = basis(norm(knee - h), n1) * inverse_rigid(basis(norm(k0 - h0), n0));
        Mat4 shin = basis(norm(ankle - knee), n1) * inverse_rigid(basis(norm(a0 - k0), n0));
        pose.bones[leg.part[0]] = translate(h) * thigh * translate(h0 * -1.0f);
        pose.bones[leg.part[1]] = translate(knee) * shin * translate(k0 * -1.0f);
        // the foot keeps its planted pose; if the leg fell short it hangs from the ankle
        Mat4 foot = translate(ankle - target) * m;
        pose.bones[leg.part[2]] = foot;
        if (leg.part[3] >= 0) {
            Vec3 ball = rig.parts[leg.part[3]].pivot;
            pose.bones[leg.part[3]] = foot * translate(ball) * rotate({-f[4] * deg, 0, 0}) * translate(ball * -1.0f);
        }
        if (leg.part[4] >= 0) {
            // the heel spur folds its tip up about its hinge
            Vec3 hinge = rig.parts[leg.part[4]].pivot;
            pose.bones[leg.part[4]] = foot * translate(hinge) * rotate({f[6] * deg, 0, 0}) * translate(hinge * -1.0f);
        }
    }
}
