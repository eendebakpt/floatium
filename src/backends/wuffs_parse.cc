// Wuffs-backed parse backend. Forwards to _Py_wuffs_strtod in
// src/cpython_adapter/wuffs_strtod.cc, which wraps the Wuffs
// parse_number_f64 entry point. Pure-C alternative to fast_float
// for callers who want zero C++ on the parse side.
#include "common/backend.h"

#include <Python.h>

extern "C" {
double _Py_wuffs_strtod(const char *nptr, char **endptr);
}

namespace {

struct Register {
    Register() {
        static const FloatiumParseBackend b = {
            /*name=*/"wuffs",
            /*strtod=*/&_Py_wuffs_strtod,
        };
        floatium::register_parse_backend(b);
    }
};
Register _reg;

}  // namespace
