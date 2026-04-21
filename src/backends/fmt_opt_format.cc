// fmt_opt: "optimized fmt" format backend. Identical to the "fmt" backend
// for modes 0 (shortest) and 2 (scientific), but routes mode 3 (fixed
// precision) through Ryu's d2fixed algorithm to sidestep the Dragon4 +
// bigint slow path inside fmt::detail::format_float that is ~2-6× slower
// than stock dtoa on huge-magnitude doubles.
//
// See reference_fmt_format_float_perf.md in the zmij memory for the
// analysis of why fmt::detail::format_float has this cliff.
#include "common/backend.h"

#include <Python.h>

extern "C" {
// Provided by src/cpython_adapter/fmt_opt_dtoa.cc.
char *_Py_fmt_opt_dtoa(double d, int mode, int ndigits,
                       int *decpt, int *sign, char **rve);
void _Py_fmt_opt_dtoa_free(char *s);
}

namespace {

struct Register {
    Register() {
        static const FloatiumFormatBackend b = {
            /*name=*/"fmt_opt",
            /*dtoa=*/&_Py_fmt_opt_dtoa,
            /*dtoa_free=*/&_Py_fmt_opt_dtoa_free,
        };
        floatium::register_format_backend(b);
    }
};
Register _reg;

}  // namespace
