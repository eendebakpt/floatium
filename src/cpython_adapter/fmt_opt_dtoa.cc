// fmt_opt: fmt for modes 0/2, Ryu d2fixed for mode 3.
//
// Rationale (see memory reference_fmt_format_float_perf.md): fmt's
// fixed-precision path falls into a Dragon4 + bigint classical loop
// when the value's decade + requested fractional precision exceeds
// ~19, which fires for huge-magnitude doubles and is ~2-6× slower
// than stock dtoa. Ryu d2fixed is block-based (9 digits per
// mulShift_mod1e9 step) and always fast, trading ~100 KB of pow10
// tables for a stable perf profile.
//
// The public shape of this TU matches src/cpython_adapter/fmt_dtoa.cc
// (_Py_fmt_opt_dtoa / _Py_fmt_opt_dtoa_free) so the backend registry
// can swap them without touching src/slots.cc.

#define FMT_HEADER_ONLY 1
#define FMT_OPTIMIZE_SIZE 2

#include "format.h"
#include "format-inl.h"

#include <Python.h>

#include <cmath>
#include <cstdint>
#include <cstring>

// Ryu d2fixed_buffered_n. The TU is compiled as C (see CMakeLists.txt).
extern "C" {
int d2fixed_buffered_n(double d, uint32_t precision, char *result);
}

extern "C" {

void _Py_fmt_opt_dtoa_free(char *s) {
    PyMem_Free(s);
}

static char *alloc_copy(const char *src, size_t n) {
    char *out = static_cast<char *>(PyMem_Malloc(n + 1));
    if (!out) return nullptr;
    std::memcpy(out, src, n);
    out[n] = '\0';
    return out;
}

static int u64_to_dec(uint64_t v, char *buf) {
    char tmp[20];
    int n = 0;
    do {
        tmp[n++] = static_cast<char>('0' + static_cast<int>(v % 10));
        v /= 10;
    } while (v);
    for (int i = 0; i < n; ++i) buf[i] = tmp[n - 1 - i];
    return n;
}

// ---- Mode 3 via Ryu d2fixed ------------------------------------------------
//
// Ryu writes "IIII.FFFF" (or "0.FFFF", or "IIII" when precision=0). The
// dtoa convention we're emulating returns digits-only and a decpt such
// that value ≈ 0.digits × 10^decpt. Conversion:
//
//   1. Locate the '.' (if precision > 0).
//   2. Concatenate integer + fractional parts.
//   3. Strip leading zeros: first_nz = index of first non-zero digit.
//      decpt = integer_len - first_nz.
//   4. Strip trailing zeros (keep at least one digit).
//   5. If everything rounded to zero, return "" with decpt = -ndigits.
static char *mode3_via_ryu(double abs_d, int ndigits, int *decpt,
                           char **rve) {
    const uint32_t precision = static_cast<uint32_t>(ndigits);

    // Worst case: sign + 310 integer digits + '.' + precision + NUL.
    // We never write a sign (abs_d is nonnegative).
    const size_t scratch_size = (size_t)precision + 325;
    char *scratch = static_cast<char *>(PyMem_Malloc(scratch_size));
    if (!scratch) return nullptr;

    int len = d2fixed_buffered_n(abs_d, precision, scratch);

    // Walk the output and compute integer_len, then the first non-zero.
    int integer_len;
    int raw_len;
    if (precision == 0) {
        // No dot in output.
        integer_len = len;
        raw_len = len;
    } else {
        // There is exactly one '.' between the integer and fractional parts.
        const char *dot = static_cast<const char *>(std::memchr(scratch, '.', len));
        integer_len = static_cast<int>(dot - scratch);
        // Collapse the dot in place: shift fractional back by one.
        std::memmove(scratch + integer_len, scratch + integer_len + 1,
                     len - integer_len - 1);
        raw_len = len - 1;
    }

    // Find first non-zero.
    int first_nz = 0;
    while (first_nz < raw_len && scratch[first_nz] == '0') ++first_nz;

    if (first_nz == raw_len) {
        // Rounded to zero. Empty digit string, decpt = -ndigits.
        PyMem_Free(scratch);
        char *out = static_cast<char *>(PyMem_Malloc(1));
        if (!out) return nullptr;
        out[0] = '\0';
        *decpt = -ndigits;
        if (rve) *rve = out;
        return out;
    }

    // Strip trailing zeros (keep at least one digit).
    int tail = raw_len;
    while (tail > first_nz + 1 && scratch[tail - 1] == '0') --tail;

    const int sig_len = tail - first_nz;
    // decpt uses pre-strip length by convention; but integer_len - first_nz
    // already gives the pre-strip decpt (trailing zeros in the raw string
    // don't shift the decimal point).
    *decpt = integer_len - first_nz;

    char *out = alloc_copy(scratch + first_nz, (size_t)sig_len);
    PyMem_Free(scratch);
    if (!out) return nullptr;
    if (rve) *rve = out + sig_len;
    return out;
}

// ---- Mode 3 via fmt (fallback for ndigits < 0) -----------------------------
static char *mode3_via_fmt(double abs_d, int ndigits, int *decpt,
                           char **rve) {
    fmt::format_specs specs;
    specs.set_type(fmt::presentation_type::fixed);
    fmt::memory_buffer buf;
    int exp = fmt::detail::format_float(abs_d, ndigits, specs,
                                        /*binary32=*/false, buf);
    const char *bd = buf.data();
    int n = static_cast<int>(buf.size());

    if (n == 1 && bd[0] == '0') {
        char *out = static_cast<char *>(PyMem_Malloc(1));
        if (!out) return nullptr;
        out[0] = '\0';
        *decpt = -ndigits;
        if (rve) *rve = out;
        return out;
    }
    if (n == 0) {
        char *out = static_cast<char *>(PyMem_Malloc(1));
        if (!out) return nullptr;
        out[0] = '\0';
        *decpt = -ndigits;
        if (rve) *rve = out;
        return out;
    }

    int nz = n;
    while (nz > 1 && bd[nz - 1] == '0') --nz;
    *decpt = exp + n;
    char *out = alloc_copy(bd, (size_t)nz);
    if (!out) return nullptr;
    if (rve) *rve = out + nz;
    return out;
}

char *_Py_fmt_opt_dtoa(double d, int mode, int ndigits,
                       int *decpt, int *sign, char **rve) {
    *sign = std::signbit(d) ? 1 : 0;
    double abs_d = *sign ? -d : d;

    if (std::isinf(abs_d)) {
        *decpt = 9999;
        char *out = alloc_copy("Infinity", 8);
        if (!out) return nullptr;
        if (rve) *rve = out + 8;
        return out;
    }
    if (std::isnan(abs_d)) {
        *decpt = 9999;
        char *out = alloc_copy("NaN", 3);
        if (!out) return nullptr;
        if (rve) *rve = out + 3;
        return out;
    }
    if (abs_d == 0.0) {
        *decpt = 1;
        char *out = alloc_copy("0", 1);
        if (!out) return nullptr;
        if (rve) *rve = out + 1;
        return out;
    }

    if (mode == 0) {
        auto r = fmt::detail::dragonbox::to_decimal(abs_d);
        char *out = static_cast<char *>(PyMem_Malloc(21));
        if (!out) return nullptr;
        int n = u64_to_dec(r.significand, out);
        int exp = r.exponent;
        while (n > 1 && out[n - 1] == '0') { --n; ++exp; }
        out[n] = '\0';
        *decpt = exp + n;
        if (rve) *rve = out + n;
        return out;
    }

    if (mode == 2) {
        fmt::format_specs specs;
        specs.set_type(fmt::presentation_type::exp);
        int precision = (ndigits < 1 ? 1 : ndigits);
        fmt::memory_buffer buf;
        int exp = fmt::detail::format_float(abs_d, precision, specs,
                                            /*binary32=*/false, buf);
        const char *bd = buf.data();
        int n = static_cast<int>(buf.size());
        int nz = n;
        while (nz > 1 && bd[nz - 1] == '0') --nz;
        *decpt = exp + n;
        char *out = alloc_copy(bd, (size_t)nz);
        if (!out) return nullptr;
        if (rve) *rve = out + nz;
        return out;
    }

    // Mode 3 (fixed precision). The two paths produce bit-identical output.
    //
    // fmt::detail::format_float has a fast subsegment path when the value's
    // decade + requested precision does not exceed the 19-digit Dragonbox
    // first segment; beyond that it falls into Dragon4 + bigint and becomes
    // 10-30× slower than Ryu d2fixed. Pick the path that keeps fmt on its
    // fast lane, and route everything else through d2fixed.
    //
    // Decade is estimated from the binary exponent: log10(2) ≈ 0.30103 so
    // decade × 3.32 ≈ exp2. We use the integer form 3 * precision + exp2 ≤ 60
    // (conservative vs the actual 19-digit cliff at exp2 ≈ 63 - 3.32 × prec).
    if (ndigits < 0) {
        return mode3_via_fmt(abs_d, ndigits, decpt, rve);
    }
    uint64_t bits;
    std::memcpy(&bits, &abs_d, sizeof(bits));
    int exp2 = static_cast<int>((bits >> 52) & 0x7ff) - 1023;
    if (exp2 < 0) exp2 = 0;  // small numbers always hit fmt's fast path
    if (3 * ndigits + exp2 <= 60) {
        return mode3_via_fmt(abs_d, ndigits, decpt, rve);
    }
    return mode3_via_ryu(abs_d, ndigits, decpt, rve);
}

}  // extern "C"
