// wuffs: pure-C string-to-double parser, vendored from Wuffs
// (https://github.com/google/wuffs). Eisel-Lemire fast path + HPD
// fallback; no bigint, no allocation, no platform strtod dependency.
//
// The actual parser lives in third_party/wuffs/floatconv_wuffs.h; the
// per-input wrapper that mimics _Py_dg_strtod is pystrtod_wuffs.h
// (ported nearly verbatim from cpython@dtoa_wuff). This TU is the
// single instantiation point that exposes the C-linkage entry point
// the registry calls into.
//
// Pair with format_backend="ryu_opt" for fully pure-C operation
// (zero C++ in the float-formatting / parsing paths).

#include "pystrtod_wuffs.h"

extern "C" {

double _Py_wuffs_strtod(const char *nptr, char **endptr) {
    return _Py_wuffs_strtod_impl(nptr, endptr);
}

}  // extern "C"
