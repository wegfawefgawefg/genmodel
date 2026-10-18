#pragma once

// Legged locomotion: a speed curve drives a gait that blends from a walk (double support,
// body high at mid-stance) to a jog (flight phase, body dipping at mid-stance). Feet in
// stance are locked to the ground, which slides back under the mech at its speed; swing
// feet travel on a minimum-jerk arc with toe-off and heel strike. Legs reach their feet by
// two-bone IK. The whole thing is simulated once at load into tables, so it is a pure
// function of time like the rest of the animation.

#include "vec.hpp"

#include <string>
#include <vector>

struct GaitStyle {
    float speed = 1.8f;   // ground speed, m/s
    float cadence = 0.56f; // full cycles (two steps) per second
    float duty = 0.62f;   // share of a cycle each foot spends on the ground
    float lift = 0.28f;   // swing foot height
    float bob = 0.05f;    // body rise and fall
    float sway = 0.06f;   // body shift toward the stance foot
    float lean = 3.0f;    // forward pitch, degrees
    float crouch = 0.0f;  // body drop
    float arms = 8.0f;    // shoulder swing, degrees
    float elbows = 0.0f;  // extra elbow bend, degrees
    float toe_off = 25.0f; // heel lift at the end of stance, degrees
    float strike = 10.0f; // toes up at heel strike, degrees
    float twist = 4.0f;   // hips turn with the swinging leg, degrees (the torso turns back)
    float impact = 0.05f; // how far the body sinks into each footfall, m
    float flex = 12.0f;   // toes spring up off each footfall, degrees
    float shove = 2.0f;   // horizontal ground force: braking early in stance, shoving late (m/s2)
    float reach = 0.1f;   // the swing foot overshoots this far forward, then pulls back to land
    float invert = 3.0f;  // the swing foot rolls in this much before landing, degrees
    float give = 14.0f;   // the heel spur folds up under load like a sprung damper, degrees
};

struct GaitLeg {
    std::string names[5]; // thigh, shin, foot, toes and heel spur (both optional)
    int part[5] = {-1, -1, -1, -1, -1};
    float phase = 0;
    float toe = 0.6f, heel = 0.3f; // toe tip and heel, ahead of / behind the ankle on the ground
};

struct GaitArm {
    std::string names[2]; // upper arm, forearm
    int part[2] = {-1, -1};
    float phase = 0;
};

const int body_channels = 8;
const int foot_channels = 7;

struct GaitSample {
    float body[body_channels]; // dx, dy, dz, pitch, roll, yaw (deg) of the body; yaw, roll of the hips
    float arm_phase;       // cycle phase for the arms
    float speed;
    float ground;          // ground distance travelled
    std::vector<float> foot; // per leg: tx, ty, tz, pitch (deg) of the foot; toes' pitch; foot roll; spur (deg)
};

struct Gait {
    bool on = false;
    std::string body_name, hips_name, head_name;
    int body = -1, hips = -1, head = -1;
    float spring_hz = 1.6f, spring_damp = 0.5f; // the body follows its targets through a spring
    std::vector<GaitLeg> legs;
    std::vector<GaitArm> arms;
    struct Seg {
        float t0, t1, v0, v1;
    };
    std::vector<Seg> speed;
    std::vector<GaitStyle> styles; // by speed: walk, jog, sprint... blended between neighbours
    float dt = 1.0f / 240.0f;
    std::vector<GaitSample> table;
    float ground_period = 1.0f; // grid spacing that loops cleanly
};

struct Rig;
struct Anim;
struct Pose;

void gait_prepare(Anim& anim, const Rig& rig);
// adds body and arm motion before the hierarchy is resolved (rot in radians)
void gait_body(const Anim& anim, float t, std::vector<Vec3>& move, std::vector<Vec3>& rot);
// solves the legs after it, overwriting their bones; sets the ground scroll
void gait_legs(const Anim& anim, const Rig& rig, float t, Pose& pose);
