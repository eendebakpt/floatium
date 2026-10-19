// zmij: pure-C format backend backed by the Żmij C library (shortest via
// Żmij's Schubfach-family algorithm; %e / %f precision via its own
// correctly rounded fixed / scientific writers, bigint-backed above 18
// digits). This is the backend floatium proposes for CPython itself: one
// unmodified upstream C library plus the plain-C adapter in
// src/cpython_adapter/zmij_dtoa.c. Pair with parse_backend="wuffs" for a
// fully pure-C float path.
#include "common/backend.h"

#include <Python.h>

extern "C" {
// Provided by src/cpython_adapter/zmij_dtoa.c (compiled as C).
char *_Py_zmij_dtoa(double d, int mode, int ndigits,
                    int *decpt, int *sign, char **rve);
void _Py_zmij_dtoa_free(char *s);
}

namespace {

struct Register {
    Register() {
        static const FloatiumFormatBackend b = {
            /*name=*/"zmij",
            /*dtoa=*/&_Py_zmij_dtoa,
            /*dtoa_free=*/&_Py_zmij_dtoa_free,
        };
        floatium::register_format_backend(b);
    }
};
Register _reg;

}  // namespace
