// Packaging a double-to-digits result into the final printable string.
//
// This is a port of CPython's Python/pystrtod.c:format_float_short and
// PyOS_double_to_string. The porting exists for one reason: we want to
// call a pluggable backend (fmt today, maybe Dragonbox or Ryu tomorrow)
// instead of _Py_dg_dtoa, and format_float_short is static. By vendoring
// it we keep the output byte-identical to stock CPython for every input
// where the backend's digit output matches _Py_dg_dtoa.
//
// Upstream license: PSF. Compatible with MIT/BSD distribution.

#include "common/format_short.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Lookup tables for case-sensitive infinity/nan/exponent strings, mirroring
// CPython's lc_float_strings / uc_float_strings.
#define OFS_INF 0
#define OFS_NAN 1
#define OFS_E   2

static const char *const lc_float_strings[] = {"inf", "nan", "e"};
static const char *const uc_float_strings[] = {"INF", "NAN", "E"};

static int is_digit_ascii(char c) {
    return c >= '0' && c <= '9';
}

static char *format_float_short(
    const FloatiumFormatBackend *backend,
    double d, char format_code, int mode, int precision,
    int always_add_sign, int add_dot_0_if_integer,
    int use_alt_formatting, int no_negative_zero,
    const char *const *float_strings, int *type)
{
    char *buf = NULL;
    char *p = NULL;
    Py_ssize_t bufsize = 0;
    char *digits = NULL;
    char *digits_end = NULL;
    int decpt_as_int = 0, sign = 0, exp_len = 0, exp = 0, use_exp = 0;
    Py_ssize_t decpt, digits_len, vdigits_start, vdigits_end;

    digits = backend->dtoa(d, mode, precision, &decpt_as_int, &sign, &digits_end);
    if (digits == NULL) {
        // Backend set a Python error (e.g. NoMemory) or the "stock" placeholder
        // backend refused. Either way, surface it.
        if (!PyErr_Occurred()) PyErr_NoMemory();
        goto exit;
    }
    decpt = (Py_ssize_t)decpt_as_int;
    assert(digits_end != NULL && digits_end >= digits);
    digits_len = digits_end - digits;

    if (no_negative_zero && sign == 1 &&
        (digits_len == 0 || (digits_len == 1 && digits[0] == '0'))) {
        sign = 0;
    }

    if (digits_len && !is_digit_ascii(digits[0])) {
        // Infinity / NaN: the backend returned "Infinity" or "NaN" (see
        // fmt_dtoa.cc). Convert to cpython's output convention and return.
        if (digits[0] == 'n' || digits[0] == 'N') sign = 0;  // ignore nan sign

        bufsize = 5;  // "+inf\0"
        buf = (char *)PyMem_Malloc(bufsize);
        if (!buf) { PyErr_NoMemory(); goto exit; }
        p = buf;

        if (sign == 1) *p++ = '-';
        else if (always_add_sign) *p++ = '+';

        if (digits[0] == 'i' || digits[0] == 'I') {
            memcpy(p, float_strings[OFS_INF], 3); p += 3;
            if (type) *type = FLOATIUM_DTST_INFINITE;
        } else if (digits[0] == 'n' || digits[0] == 'N') {
            memcpy(p, float_strings[OFS_NAN], 3); p += 3;
            if (type) *type = FLOATIUM_DTST_NAN;
        } else {
            // unreachable
            PyMem_Free(buf); buf = NULL;
            PyErr_BadInternalCall();
            goto exit;
        }
        goto exit;
    }

    if (type) *type = FLOATIUM_DTST_FINITE;

    // Compute where the decimal point lands and whether to use exponent form.
    vdigits_end = digits_len;
    switch (format_code) {
    case 'e':
        use_exp = 1;
        vdigits_end = precision;
        break;
    case 'f':
        vdigits_end = decpt + precision;
        break;
    case 'g':
        if (decpt <= -4 || decpt >
            (add_dot_0_if_integer ? precision - 1 : precision))
            use_exp = 1;
        if (use_alt_formatting) vdigits_end = precision;
        break;
    case 'r':
        if (decpt <= -4 || decpt > 16) use_exp = 1;
        break;
    default:
        PyErr_BadInternalCall();
        goto exit;
    }

    if (use_exp) {
        exp = (int)decpt - 1;
        decpt = 1;
    }
    vdigits_start = decpt <= 0 ? decpt - 1 : 0;
    if (!use_exp && add_dot_0_if_integer)
        vdigits_end = vdigits_end > decpt ? vdigits_end : decpt + 1;
    else
        vdigits_end = vdigits_end > decpt ? vdigits_end : decpt;

    assert(vdigits_start <= 0 && 0 <= digits_len && digits_len <= vdigits_end);
    assert(vdigits_start < decpt && decpt <= vdigits_end);

    bufsize = 3 + (vdigits_end - vdigits_start) + (use_exp ? 5 : 0);
    buf = (char *)PyMem_Malloc(bufsize);
    if (!buf) { PyErr_NoMemory(); goto exit; }
    p = buf;

    if (sign == 1) *p++ = '-';
    else if (always_add_sign) *p++ = '+';

    // Leading zero-padding.
    if (decpt <= 0) {
        memset(p, '0', decpt - vdigits_start); p += decpt - vdigits_start;
        *p++ = '.';
        memset(p, '0', -decpt); p += -decpt;
    } else {
        memset(p, '0', -vdigits_start); p += -vdigits_start;
    }

    // Digits and included decimal point.
    if (0 < decpt && decpt <= digits_len) {
        memcpy(p, digits, decpt); p += decpt;
        *p++ = '.';
        memcpy(p, digits + decpt, digits_len - decpt); p += digits_len - decpt;
    } else {
        memcpy(p, digits, digits_len); p += digits_len;
    }

    // Trailing zeros.
    if (digits_len < decpt) {
        memset(p, '0', decpt - digits_len); p += decpt - digits_len;
        *p++ = '.';
        memset(p, '0', vdigits_end - decpt); p += vdigits_end - decpt;
    } else {
        memset(p, '0', vdigits_end - digits_len); p += vdigits_end - digits_len;
    }

    // Drop trailing '.' unless alt formatting.
    if (p - buf > 0 && p[-1] == '.' && !use_alt_formatting) p--;

    if (use_exp) {
        *p++ = float_strings[OFS_E][0];
        exp_len = snprintf(p, (size_t)(bufsize - (p - buf)), "%+.02d", exp);
        p += exp_len;
    }

exit:
    if (buf) {
        *p = '\0';
        assert(p - buf < bufsize);
    }
    if (digits) backend->dtoa_free(digits);
    return buf;
}

extern "C"
char *floatium_double_to_string(
    const FloatiumFormatBackend *backend,
    double val, char format_code, int precision, int flags, int *type)
{
    const char *const *float_strings = lc_float_strings;
    int mode;

    switch (format_code) {
    case 'E':
        float_strings = uc_float_strings;
        format_code = 'e';
        // fallthrough
    case 'e':
        mode = 2;
        precision++;
        break;
    case 'F':
        float_strings = uc_float_strings;
        format_code = 'f';
        // fallthrough
    case 'f':
        mode = 3;
        break;
    case 'G':
        float_strings = uc_float_strings;
        format_code = 'g';
        // fallthrough
    case 'g':
        mode = 2;
        if (precision == 0) precision = 1;
        break;
    case 'r':
        mode = 0;
        if (precision != 0) { PyErr_BadInternalCall(); return NULL; }
        break;
    default:
        PyErr_BadInternalCall();
        return NULL;
    }

    return format_float_short(
        backend, val, format_code, mode, precision,
        /*always_add_sign=*/(flags & FLOATIUM_SIGN) != 0,
        /*add_dot_0_if_integer=*/(flags & FLOATIUM_ADD_DOT_0) != 0,
        /*use_alt_formatting=*/(flags & FLOATIUM_ALT) != 0,
        /*no_negative_zero=*/(flags & FLOATIUM_NO_NEG_0) != 0,
        float_strings, type);
}
