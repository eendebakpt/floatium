// Backend abstractions. Keeping fmt and fast_float behind these interfaces
// means other libraries (Ryu, Schubfach, double-conversion, absl::from_chars)
// can be swapped in without touching the slot-patching layer.
//
// The format backend produces a PyMem_Malloc'd digit string with the exact
// contract of _Py_dg_dtoa: digits (no dot, no sign, no exponent), decpt such
// that value ~= 0.digits * 10^decpt, *sign set from signbit, *rve pointing at
// the NUL terminator. This is the "raw" output that format_float_short
// packages into the final string.
//
// The parse backend produces a double from a C string, with the _Py_dg_strtod
// contract: no leading whitespace skipping, no infinity/nan handling (that's
// the caller's fallback), *endptr points past consumed chars, errno=ERANGE on
// over/underflow. pystrtod.c's path from the CPython fmt-fastfloat branch
// relies on these invariants.
#ifndef FLOATIUM_BACKEND_H
#define FLOATIUM_BACKEND_H

#ifdef __cplusplus
extern "C" {
#endif

// Format: double -> digit-string + decpt + sign (mimics _Py_dg_dtoa).
//
// mode: 0 = shortest round-trip
//       2 = max(1, ndigits) significant digits
//       3 = ndigits digits past the decimal point (ndigits may be negative)
//
// Returns a PyMem_Malloc'd buffer, or NULL on allocation failure. Caller
// must free with the matching *_free function (all backends use PyMem_Free).
typedef char *(*floatium_dtoa_fn)(double d, int mode, int ndigits,
                                  int *decpt, int *sign, char **rve);
typedef void  (*floatium_dtoa_free_fn)(char *s);

// Parse: C string -> double (mimics _Py_dg_strtod).
typedef double (*floatium_strtod_fn)(const char *nptr, char **endptr);

struct FloatiumFormatBackend {
    const char *name;               // "fmt", "stock", ...
    floatium_dtoa_fn dtoa;
    floatium_dtoa_free_fn dtoa_free;
};

struct FloatiumParseBackend {
    const char *name;
    floatium_strtod_fn strtod;
};

// Registry lookup. Returns NULL if the backend wasn't compiled in.
const struct FloatiumFormatBackend *floatium_format_backend(const char *name);
const struct FloatiumParseBackend  *floatium_parse_backend(const char *name);

// Default backends (from CMake-configured FLOATIUM_DEFAULT_*). These are
// what install() uses unless the env vars FLOATIUM_FORMAT_BACKEND /
// FLOATIUM_PARSE_BACKEND override them.
const struct FloatiumFormatBackend *floatium_default_format_backend(void);
const struct FloatiumParseBackend  *floatium_default_parse_backend(void);

// Names, for introspection.
const char *floatium_format_backend_names(void);  // comma-separated
const char *floatium_parse_backend_names(void);

#ifdef __cplusplus
}  // extern "C"

// C++-only registration helpers for the individual backends.
namespace floatium {

// Each backend .cc registers itself at static-init time via these:
void register_format_backend(const FloatiumFormatBackend &b);
void register_parse_backend(const FloatiumParseBackend &b);

}  // namespace floatium
#endif

#endif  // FLOATIUM_BACKEND_H
