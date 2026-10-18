#pragma once

#include "vec.hpp"

#include <gsexp/sexp.hpp>

#include <string>

// helpers for reading our .sexp data files
bool read_text(const std::string& path, std::string& out);
float num(gsexp::Node n, float fallback = 0.0f);
// three numbers starting at child `first` of a form
Vec3 vec_at(gsexp::Node form, size_t first);
// the form's head symbol, or "" for atoms
std::string head_of(gsexp::Node n);
void print_diagnostics(const std::string& path, const gsexp::ParseResult& r);
