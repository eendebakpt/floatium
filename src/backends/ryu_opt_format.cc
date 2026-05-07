// ryu_opt: pure-C format backend (Ryu d2s for shortest, Ryu d2exp for
// scientific, Ryu d2fixed for fixed-precision). The third backend
// alongside fmt and fmt_opt; useful for callers who want a zero-C++
// float-formatting path. Pair with parse_backend="stock" for a fully
// pure-C operation (a pure-C parse backend is future work — see README).
//
// Output is bit-identical to stock CPython's _Py_dg_dtoa for modes 0/2/3
// (verified by the test suite). Per the no-delegation-to-dtoa rule, this
// backend never falls through to the saved original __format__/tp_repr.
#include "common/backend.h"

#include <Python.h>

extern "C" {
// Provided by src/cpython_adapter/ryu_opt_dtoa.cc.
char *_Py_ryu_opt_dtoa(double d, int mode, int ndigits,
                       int *decpt, int *sign, char **rve);
void _Py_ryu_opt_dtoa_free(char *s);
}

namespace {

struct Register {
    Register() {
        static const FloatiumFormatBackend b = {
            /*name=*/"ryu_opt",
            /*dtoa=*/&_Py_ryu_opt_dtoa,
            /*dtoa_free=*/&_Py_ryu_opt_dtoa_free,
        };
        floatium::register_format_backend(b);
    }
};
Register _reg;

}  // namespace
