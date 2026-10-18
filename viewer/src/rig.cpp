#include "rig.hpp"

#include "sexp_read.hpp"

#include <algorithm>
#include <cstdio>

Rig root_only_rig() {
    Rig r;
    r.parts.push_back({"root", -1, {0, 0, 0}, false});
    return r;
}

int find_part(const Rig& rig, const std::string& name) {
    for (size_t i = 0; i < rig.parts.size(); i++) {
        if (rig.parts[i].name == name) {
            return (int)i;
        }
    }
    return -1;
}

static void read_part(gsexp::Node form, Rig& rig, std::vector<std::string>& parent_names) {
    RigPart p;
    p.name = std::string(form.child_at(1).text());
    std::string parent;
    for (size_t i = 2; i < form.child_count(); i++) {
        gsexp::Node c = form.child_at(i);
        std::string h = head_of(c);
        if (h == "pivot") {
            p.pivot = vec_at(c, 1);
        } else if (h == "parent") {
            parent = std::string(c.child_at(1).text());
        } else if (h == "additive") {
            p.additive = true;
        }
    }
    rig.parts.push_back(p);
    parent_names.push_back(parent);
}

// paths name their handles by convention: <path>_h1 and <path>_h2
static void read_path(gsexp::Node form, Rig& rig, std::string& parent_name) {
    RigPath ph;
    ph.name = std::string(form.child_at(1).text());
    for (size_t i = 2; i < form.child_count(); i++) {
        gsexp::Node c = form.child_at(i);
        std::string h = head_of(c);
        if (h == "parent") {
            parent_name = std::string(c.child_at(1).text());
        } else if (h == "points") {
            for (size_t k = 0; k < 4 && k + 1 < c.child_count(); k++) {
                ph.points[k] = vec_at(c.child_at(k + 1), 0);
            }
        } else if (h == "anchor") {
            ph.anchor = find_part(rig, std::string(c.child_at(1).text()));
        } else if (h == "start") {
            ph.start = num(c.child_at(1));
        } else if (h == "pitch") {
            ph.pitch = num(c.child_at(1), 0.1f);
        } else if (h == "across") {
            ph.across = vec_at(c, 1);
        } else if (h == "links") {
            for (size_t k = 1; k < c.child_count(); k++) {
                ph.links.push_back(find_part(rig, std::string(c.child_at(k).text())));
            }
        }
    }
    ph.handle[0] = find_part(rig, ph.name + "_h1");
    ph.handle[1] = find_part(rig, ph.name + "_h2");
    rig.paths.push_back(ph);
}

bool load_rig(const std::string& path, Rig& out) {
    std::string text;
    if (!read_text(path, text)) {
        return false;
    }
    gsexp::ParseResult r = gsexp::parse(text);
    if (!r.ok || r.root_count() == 0) {
        print_diagnostics(path, r);
        return false;
    }
    Rig rig;
    std::vector<std::string> parent_names;
    std::vector<std::string> path_parents;
    gsexp::Node top = r.root(0);
    // parts first so paths can name their links
    for (gsexp::Node c : top.children()) {
        if (head_of(c) == "part") {
            read_part(c, rig, parent_names);
        }
    }
    for (gsexp::Node c : top.children()) {
        if (head_of(c) == "path") {
            path_parents.emplace_back();
            read_path(c, rig, path_parents.back());
        }
    }
    // a rig without a root gets one first, before any parent indices are resolved
    if (find_part(rig, "root") < 0) {
        rig.parts.insert(rig.parts.begin(), {"root", -1, {0, 0, 0}, false});
        parent_names.insert(parent_names.begin(), "");
    }
    for (size_t i = 0; i < rig.parts.size(); i++) {
        rig.parts[i].parent = parent_names[i].empty() ? -1 : find_part(rig, parent_names[i]);
    }
    for (size_t i = 0; i < rig.paths.size(); i++) {
        rig.paths[i].parent = find_part(rig, path_parents[i]);
    }
    for (gsexp::Node c : top.children()) {
        if (head_of(c) == "aim") {
            RigAim a = {find_part(rig, std::string(c.child_at(1).text())), find_part(rig, std::string(c.child_at(2).text()))};
            if (a.cylinder >= 0 && a.rod >= 0) rig.aims.push_back(a);
        }
    }
    printf("rig %s: %zu parts, %zu paths\n", path.c_str(), rig.parts.size(), rig.paths.size());
    out = std::move(rig);
    return true;
}

Curve make_curve(const Vec3 p[4]) {
    Curve c;
    for (int i = 0; i <= 64; i++) {
        float u = (float)i / 64.0f, v = 1 - u;
        c.pts[i] = p[0] * (v * v * v) + p[1] * (3 * v * v * u) + p[2] * (3 * v * u * u) + p[3] * (u * u * u);
        c.arc[i] = i == 0 ? 0 : c.arc[i - 1] + len(c.pts[i] - c.pts[i - 1]);
    }
    c.length = c.arc[64];
    return c;
}

void curve_at(const Curve& c, float s, Vec3& point, Vec3& tangent) {
    s = std::clamp(s, 0.0f, c.length);
    int k = (int)(std::upper_bound(c.arc, c.arc + 65, s) - c.arc) - 1;
    k = std::clamp(k, 0, 63);
    float span = std::max(c.arc[k + 1] - c.arc[k], 1e-9f);
    float f = (s - c.arc[k]) / span;
    point = c.pts[k] * (1 - f) + c.pts[k + 1] * f;
    tangent = norm(c.pts[k + 1] - c.pts[k]);
}

Mat4 curve_frame(const Curve& c, float s, Vec3 across) {
    Vec3 p, t;
    curve_at(c, s, p, t);
    Vec3 x = norm(across - t * dot(across, t));
    Vec3 z = cross(x, t);
    return frame(x, t, z, p);
}
