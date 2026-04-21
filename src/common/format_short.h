// Packaging layer on top of the format backend.
//
// format_float_short takes a double and produces the final textual form
// (with sign, decimal point, exponent, padding) that float_repr,
// PyOS_double_to_string, and the %g/%e/%f formatters would produce. The
// logic is a 1:1 port of CPython's Python/pystrtod.c:format_float_short,
// which is what ensures output is bit-identical to stock CPython.
//
// The only change from upstream is the dtoa call: it goes through the
// currently-active FloatiumFormatBackend instead of _Py_dg_dtoa directly.
#ifndef FLOATIUM_FORMAT_SHORT_H
#define FLOATIUM_FORMAT_SHORT_H

#ifdef __cplusplus
extern "C" {
#endif

#include <Python.h>

#include "backend.h"

// Bits for the 'flags' argument, matching CPython's Py_DTSF_* constants.
// Repeated here so floatium doesn't depend on internal CPython headers.
#define FLOATIUM_SIGN        0x1   // always add a sign
#define FLOATIUM_ADD_DOT_0   0x2   // add ".0" to integers
#define FLOATIUM_ALT         0x4   // alternate form (like printf %#g)
#define FLOATIUM_NO_NEG_0    0x8   // don't emit -0.0

// Type classification, matching Py_DTST_*.
#define FLOATIUM_DTST_FINITE    0
#define FLOATIUM_DTST_INFINITE  1
#define FLOATIUM_DTST_NAN       2

// Produces a PyMem_Malloc'd null-terminated string. Caller must free with
// PyMem_Free.
//
// format_code: 'e', 'E', 'f', 'F', 'g', 'G', 'r'
// precision:   as for printf (ignored for 'r')
// flags:       OR of FLOATIUM_SIGN / FLOATIUM_ADD_DOT_0 / FLOATIUM_ALT /
//              FLOATIUM_NO_NEG_0
// type_out:    if non-NULL, set to FLOATIUM_DTST_*.
char *floatium_double_to_string(
    const FloatiumFormatBackend *backend,
    double val, char format_code, int precision, int flags, int *type_out);

#ifdef __cplusplus
}  // extern "C"
#endif

#endif  // FLOATIUM_FORMAT_SHORT_H
