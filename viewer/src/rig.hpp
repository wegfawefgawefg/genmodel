#pragma once

#include "vec.hpp"

#include <string>
#include <vector>

// a rigid chunk of the model; rest transforms are identity, motion pivots about `pivot`
struct RigPart {
    std::string name;
    int parent = -1;
    Vec3 pivot;
    bool additive = false;
};

// a bezier that animation can bend; its links ride it by arc length
struct RigPath {
    std::string name;
    int parent = -1;
    int anchor = -1; // part carrying the start point (the drum the belt leaves)
    Vec3 points[4];
    int handle[2] = {-1, -1}; // parts whose motion offsets the two inner points
    std::vector<int> links;
    float pitch = 0.1f;
    float start = 0;  // arc length of the first link at rest
    Vec3 across = {1, 0, 0};
};

// a hydraulic ram across a joint: the cylinder rides one part, the rod the other, and both
// turn to face each other every frame, so the rod slides in and out as the joint moves
struct RigAim {
    int cylinder = -1, rod = -1;
};

struct Rig {
    std::vector<RigPart> parts;
    std::vector<RigPath> paths;
    std::vector<RigAim> aims;
};

// a rig with just a root, for models without a .rig.sexp
Rig root_only_rig();
bool load_rig(const std::string& path, Rig& out);
int find_part(const Rig& rig, const std::string& name);

// sampled bezier with an arc-length table
struct Curve {
    Vec3 pts[65];
    float arc[65];
    float length = 0;
};

Curve make_curve(const Vec3 p[4]);
// point and unit tangent at arc length s (clamped)
void curve_at(const Curve& c, float s, Vec3& point, Vec3& tangent);
// frame whose y runs along the curve and x leans toward `across`
Mat4 curve_frame(const Curve& c, float s, Vec3 across);
