// ryu_opt: pure-C float-formatting backend backed by Ryu (d2s + d2fixed +
// d2exp). Drop-in replacement for _Py_dg_dtoa for modes 0/2/3, with no
// dependency on {fmt} or any C++ library.
//
// The actual logic lives in pystrtod_ryu.h, ported nearly verbatim from
// the Ryu adapter on the ~/cpython@rye_float branch (the pure-C companion
// to floatium's fmt-based backends). This TU is the single instantiation
// point: it pulls the static-inline adapter routines into one object file
// and exposes the public symbols that backends/ryu_opt_format.cc registers.
//
// Per the project's no-delegation-to-dtoa rule, ryu_opt does not fall
// through to the original __format__ slot for any input; every mode
// 0/2/3 case is served by Ryu directly (mode 3 with negative ndigits is
// handled in-adapter via ryu_mode3_neg).

#include "pystrtod_ryu.h"

extern "C" {

char *_Py_ryu_opt_dtoa(double d, int mode, int ndigits,
                       int *decpt, int *sign, char **rve) {
    // Adapter's "digits_end" parameter has the same contract as dtoa's
    // *rve (pointer to the trailing NUL of the digit string).
    return _Py_ryu_opt_dtoa_impl(d, mode, ndigits, decpt, sign, rve);
}

void _Py_ryu_opt_dtoa_free(char *s) {
    PyMem_Free(s);
}

}  // extern "C"
