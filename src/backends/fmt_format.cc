// fmt-backed format backend. Forwards to the CPython adapter
// _Py_fmt_dtoa (in src/cpython_adapter/fmt_dtoa.cc), which is copied
// verbatim from the CPython fmt-fastfloat branch so output is
// bit-identical to what the in-tree build would produce.
#include "common/backend.h"

#include <Python.h>

extern "C" {
// Provided by src/cpython_adapter/fmt_dtoa.cc.
char *_Py_fmt_dtoa(double d, int mode, int ndigits,
                   int *decpt, int *sign, char **rve);
void _Py_fmt_dtoa_free(char *s);
}

namespace {

struct Register {
    Register() {
        static const FloatiumFormatBackend b = {
            /*name=*/"fmt",
            /*dtoa=*/&_Py_fmt_dtoa,
            /*dtoa_free=*/&_Py_fmt_dtoa_free,
        };
        floatium::register_format_backend(b);
    }
};
Register _reg;

}  // namespace
