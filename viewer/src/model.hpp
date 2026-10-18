#pragma once

#include <cstdint>
#include <string>
#include <vector>

// one interleaved vertex: position, normal, uv
struct Vertex {
    float px, py, pz;
    float nx, ny, nz;
    float u, v;
    float part; // rig part index, as a float for the vertex attribute
};

struct Image {
    int w = 0;
    int h = 0;
    std::vector<uint8_t> rgba;
};

struct Model {
    std::vector<Vertex> verts;
    std::vector<uint32_t> indices;
    std::vector<std::string> groups; // obj "g" names, one per rig part
    std::vector<int> vertex_group;   // per vertex, index into groups
    Image texture;
    bool nearest = false; // chunky texels: "# genmodel filter nearest" in the .mtl
    float center[3] = {0, 0, 0};
    float radius = 1.0f;
};

// loads an .obj (v/vt/vn triangles) and the texture named by its .mtl map_Kd
bool load_model(const std::string& obj_path, Model& out);

// newest modification time of the obj and its texture, for hot reload
int64_t model_stamp(const std::string& obj_path);
