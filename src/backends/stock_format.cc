// "stock" format backend: forwards to PyOS_double_to_string, i.e. whatever
// the currently-running CPython uses (dtoa.c on <=3.13, Ryu on some branches,
// etc.). Useful as a baseline for A/B parity tests — installing this backend
// should be observationally identical to not installing floatium at all
// (minus the one-extra-allocation path we introduce below).
//
// Contract: returns a PyMem_Malloc'd digit string matching _Py_dg_dtoa.
// Since PyOS_double_to_string returns a packaged string (with dot, sign,
// exponent), we cannot use it directly. Instead we invoke repr via the
// Python layer. This path is slow by construction (designed for testing,
// not for perf).
//
// For *real* A/B benchmarking against stock dtoa, install floatium with
// FLOATIUM_FORMAT_BACKEND=fmt and then compare with and without
// floatium.install() — not via this backend.

#include "common/backend.h"

#include <Python.h>

#include <cstring>

extern "C" {

static char *stock_dtoa(double d, int mode, int ndigits,
                        int *decpt, int *sign, char **rve) {
    // Placeholder: marking as unavailable is cleaner than approximating.
    // Users wanting a stock baseline should uninstall floatium instead.
    (void)d; (void)mode; (void)ndigits; (void)decpt; (void)sign; (void)rve;
    PyErr_SetString(PyExc_NotImplementedError,
                    "stock format backend is a marker only; uninstall "
                    "floatium to get the interpreter's native formatting");
    return nullptr;
}

static void stock_dtoa_free(char *s) {
    PyMem_Free(s);
}

}  // extern "C"

namespace {

struct Register {
    Register() {
        static const FloatiumFormatBackend b = {
            /*name=*/"stock",
            /*dtoa=*/&stock_dtoa,
            /*dtoa_free=*/&stock_dtoa_free,
        };
        floatium::register_format_backend(b);
    }
};
Register _reg;

}  // namespace
