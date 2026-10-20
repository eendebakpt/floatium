// ffc: pure-C parse backend backed by ffc.h, the C99 port of fast_float
// (Clinger + Eisel-Lemire + bigint digit comparison). Same algorithm and
// grammar as the fast_float backend, but with no C++ anywhere — paired
// with the zmij format backend this is the configuration floatium
// proposes for CPython.
#include "common/backend.h"

#include <Python.h>

extern "C" {
// Provided by src/cpython_adapter/ffc_strtod.c (compiled as C).
double _Py_ffc_strtod(const char *nptr, char **endptr);
}

namespace {

struct Register {
    Register() {
        static const FloatiumParseBackend b = {
            /*name=*/"ffc",
            /*strtod=*/&_Py_ffc_strtod,
        };
        floatium::register_parse_backend(b);
    }
};
Register _reg;

}  // namespace
