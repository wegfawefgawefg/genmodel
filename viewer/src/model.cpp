#include "model.hpp"

#include "images.hpp"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <unordered_map>

namespace fs = std::filesystem;

namespace {

struct Corner {
    int v, t, n;
    bool operator==(const Corner& o) const { return v == o.v && t == o.t && n == o.n; }
};

struct CornerHash {
    size_t operator()(const Corner& c) const {
        return (size_t)c.v * 73856093u ^ (size_t)c.t * 19349663u ^ (size_t)c.n * 83492791u;
    }
};

// "12/7/3" -> zero-based indices, missing parts become -1
Corner parse_corner(const char* s) {
    Corner c = {-1, -1, -1};
    int parts[3] = {0, 0, 0};
    int which = 0;
    const char* p = s;
    while (*p && which < 3) {
        if (*p == '/') {
            which++;
            p++;
            continue;
        }
        parts[which] = (int)strtol(p, (char**)&p, 10);
    }
    c.v = parts[0] - 1;
    c.t = parts[1] - 1;
    c.n = parts[2] - 1;
    return c;
}

std::string texture_from_mtl(const fs::path& mtl_path) {
    std::ifstream f(mtl_path);
    std::string line;
    while (std::getline(f, line)) {
        std::istringstream ss(line);
        std::string key;
        ss >> key;
        if (key == "map_Kd") {
            std::string name;
            ss >> name;
            return (mtl_path.parent_path() / name).string();
        }
    }
    return "";
}

std::string texture_path_for(const std::string& obj_path) {
    std::ifstream f(obj_path);
    std::string line;
    while (std::getline(f, line)) {
        if (line.rfind("mtllib ", 0) == 0) {
            return texture_from_mtl(fs::path(obj_path).parent_path() / line.substr(7));
        }
    }
    return "";
}

void fit_bounds(Model& m) {
    float lo[3] = {1e30f, 1e30f, 1e30f};
    float hi[3] = {-1e30f, -1e30f, -1e30f};
    for (const Vertex& v : m.verts) {
        float p[3] = {v.px, v.py, v.pz};
        for (int i = 0; i < 3; i++) {
            lo[i] = std::fmin(lo[i], p[i]);
            hi[i] = std::fmax(hi[i], p[i]);
        }
    }
    float r2 = 0;
    for (int i = 0; i < 3; i++) {
        m.center[i] = 0.5f * (lo[i] + hi[i]);
        float half = 0.5f * (hi[i] - lo[i]);
        r2 += half * half;
    }
    m.radius = std::sqrt(r2);
}

} // namespace

bool load_model(const std::string& obj_path, Model& out) {
    std::ifstream f(obj_path);
    if (!f) {
        fprintf(stderr, "cannot open %s\n", obj_path.c_str());
        return false;
    }
    std::vector<float> pos, uv, nrm;
    std::unordered_map<Corner, uint32_t, CornerHash> seen;
    Model m;

    // read lines, dedupe corners into vertices
    std::string line;
    while (std::getline(f, line)) {
        const char* s = line.c_str();
        if (s[0] == 'v' && s[1] == ' ') {
            float x, y, z;
            sscanf(s + 2, "%f %f %f", &x, &y, &z);
            pos.insert(pos.end(), {x, y, z});
        } else if (s[0] == 'v' && s[1] == 't') {
            float a, b;
            sscanf(s + 3, "%f %f", &a, &b);
            uv.insert(uv.end(), {a, b});
        } else if (s[0] == 'v' && s[1] == 'n') {
            float x, y, z;
            sscanf(s + 3, "%f %f %f", &x, &y, &z);
            nrm.insert(nrm.end(), {x, y, z});
        } else if (s[0] == 'f' && s[1] == ' ') {
            std::istringstream ss(line.substr(2));
            std::string tok;
            std::vector<uint32_t> face;
            while (ss >> tok) {
                Corner c = parse_corner(tok.c_str());
                auto it = seen.find(c);
                if (it != seen.end()) {
                    face.push_back(it->second);
                    continue;
                }
                Vertex v = {};
                v.px = pos[c.v * 3 + 0];
                v.py = pos[c.v * 3 + 1];
                v.pz = pos[c.v * 3 + 2];
                if (c.n >= 0) {
                    v.nx = nrm[c.n * 3 + 0];
                    v.ny = nrm[c.n * 3 + 1];
                    v.nz = nrm[c.n * 3 + 2];
                }
                if (c.t >= 0) {
                    v.u = uv[c.t * 2 + 0];
                    v.v = uv[c.t * 2 + 1];
                }
                uint32_t id = (uint32_t)m.verts.size();
                m.verts.push_back(v);
                seen[c] = id;
                face.push_back(id);
            }
            // fan any polygon into triangles
            for (size_t i = 2; i < face.size(); i++) {
                m.indices.insert(m.indices.end(), {face[0], face[i - 1], face[i]});
            }
        }
    }
    if (m.indices.empty()) {
        fprintf(stderr, "no faces in %s\n", obj_path.c_str());
        return false;
    }

    // texture, or a flat grey stand-in
    std::string tex = texture_path_for(obj_path);
    if (tex.empty() || !load_png(tex, m.texture)) {
        m.texture.w = m.texture.h = 1;
        m.texture.rgba = {180, 180, 180, 64};
    }
    fit_bounds(m);
    out = std::move(m);
    printf("loaded %s: %zu verts, %zu tris, texture %dx%d\n", obj_path.c_str(), out.verts.size(),
           out.indices.size() / 3, out.texture.w, out.texture.h);
    return true;
}

int64_t model_stamp(const std::string& obj_path) {
    std::error_code ec;
    int64_t stamp = 0;
    auto t = fs::last_write_time(obj_path, ec);
    if (!ec) {
        stamp = t.time_since_epoch().count();
    }
    std::string tex = texture_path_for(obj_path);
    if (!tex.empty()) {
        auto tt = fs::last_write_time(tex, ec);
        if (!ec && tt.time_since_epoch().count() > stamp) {
            stamp = tt.time_since_epoch().count();
        }
    }
    return stamp;
}
