#include "sexp_read.hpp"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>

bool read_text(const std::string& path, std::string& out) {
    std::ifstream f(path);
    if (!f) {
        return false;
    }
    std::stringstream ss;
    ss << f.rdbuf();
    out = ss.str();
    return true;
}

float num(gsexp::Node n, float fallback) {
    if (!n.valid() || n.is_list()) {
        return fallback;
    }
    std::string s(n.text());
    char* end = nullptr;
    float v = strtof(s.c_str(), &end);
    return end == s.c_str() ? fallback : v;
}

Vec3 vec_at(gsexp::Node form, size_t first) {
    return {num(form.child_at(first)), num(form.child_at(first + 1)), num(form.child_at(first + 2))};
}

std::string head_of(gsexp::Node n) {
    if (!n.valid() || !n.is_list() || n.child_count() == 0) {
        return "";
    }
    return std::string(n.head().text());
}

void print_diagnostics(const std::string& path, const gsexp::ParseResult& r) {
    for (const gsexp::Diagnostic& d : r.diagnostics) {
        fprintf(stderr, "%s:%d:%d: %s\n", path.c_str(), (int)d.line, (int)d.column, d.message.c_str());
    }
}
