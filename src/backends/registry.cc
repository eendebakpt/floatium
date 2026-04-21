// Backend registry. Backends self-register from their own TU's static init.
// Lookups are by name; defaults come from the CMake-configured
// FLOATIUM_DEFAULT_{FORMAT,PARSE}_BACKEND macro.
//
// Note: We deliberately avoid std::mutex on the registration side — all
// registrations happen during static init, before install() can run, so
// there's no concurrent access. Lookups are read-only after that.
#include "common/backend.h"

#include <cstring>
#include <string>
#include <vector>

namespace {

std::vector<FloatiumFormatBackend> &format_vec() {
    static std::vector<FloatiumFormatBackend> v;
    return v;
}
std::vector<FloatiumParseBackend> &parse_vec() {
    static std::vector<FloatiumParseBackend> v;
    return v;
}

}  // namespace

namespace floatium {

void register_format_backend(const FloatiumFormatBackend &b) {
    format_vec().push_back(b);
}

void register_parse_backend(const FloatiumParseBackend &b) {
    parse_vec().push_back(b);
}

}  // namespace floatium

extern "C" {

const FloatiumFormatBackend *floatium_format_backend(const char *name) {
    if (!name) return nullptr;
    for (const auto &b : format_vec()) {
        if (std::strcmp(b.name, name) == 0) return &b;
    }
    return nullptr;
}

const FloatiumParseBackend *floatium_parse_backend(const char *name) {
    if (!name) return nullptr;
    for (const auto &b : parse_vec()) {
        if (std::strcmp(b.name, name) == 0) return &b;
    }
    return nullptr;
}

const FloatiumFormatBackend *floatium_default_format_backend(void) {
    return floatium_format_backend(FLOATIUM_DEFAULT_FORMAT_BACKEND);
}

const FloatiumParseBackend *floatium_default_parse_backend(void) {
    return floatium_parse_backend(FLOATIUM_DEFAULT_PARSE_BACKEND);
}

const char *floatium_format_backend_names(void) {
    static std::string s;
    if (s.empty()) {
        for (const auto &b : format_vec()) {
            if (!s.empty()) s += ",";
            s += b.name;
        }
    }
    return s.c_str();
}

const char *floatium_parse_backend_names(void) {
    static std::string s;
    if (s.empty()) {
        for (const auto &b : parse_vec()) {
            if (!s.empty()) s += ",";
            s += b.name;
        }
    }
    return s.c_str();
}

}  // extern "C"
