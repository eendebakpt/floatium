// fast_float-backed parse backend. Forwards to _Py_fast_float_strtod in
// src/cpython_adapter/fast_float_strtod.cc (verbatim from CPython branch).
#include "common/backend.h"

#include <Python.h>

extern "C" {
double _Py_fast_float_strtod(const char *nptr, char **endptr);
}

namespace {

struct Register {
    Register() {
        static const FloatiumParseBackend b = {
            /*name=*/"fast_float",
            /*strtod=*/&_Py_fast_float_strtod,
        };
        floatium::register_parse_backend(b);
    }
};
Register _reg;

}  // namespace
