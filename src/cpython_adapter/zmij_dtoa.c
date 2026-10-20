/* zmij_dtoa.c - _Py_dg_dtoa drop-in backed by the Żmij C library.
 *
 * This is the backend floatium proposes for CPython itself, so it is
 * written as plain C11 against the exact _Py_dg_dtoa contract and uses
 * nothing from CPython beyond PyMem_Malloc / PyMem_Free. Moving it into
 * Python/ next to pystrtod.c should be a copy, not a port.
 *
 *   char *_Py_zmij_dtoa(double d, int mode, int ndigits,
 *                       int *decpt, int *sign, char **rve);
 *
 *   mode 0  - shortest round-trip digits            (repr / str)
 *   mode 2  - max(1, ndigits) significant digits    (%e / %g)
 *   mode 3  - ndigits digits past the decimal point (%f); ndigits may be
 *             negative (float.__round__ with a negative argument), in which
 *             case the value is rounded to a multiple of 10**-ndigits with
 *             ties to even against the exact binary value.
 *
 * Output contract (David Gay's):
 *   - returns a PyMem_Malloc'd NUL-terminated string of decimal digits only:
 *     no sign, no decimal point, no exponent, no leading zeros, and no
 *     trailing zeros; value ~= 0.<digits> * 10**(*decpt).
 *   - a result that rounds to zero in mode 3 is the empty string with
 *     *decpt == -ndigits (Gay's "no digits" convention).
 *   - *sign is 1 for negative input (including -0.0), else 0.
 *   - +-inf / nan return "Infinity" / "NaN" with *decpt == 9999;
 *     format_float_short recognises them by the first character.
 *   - *rve points at the terminating NUL. NULL means allocation failure.
 *
 * Żmij writes printf-style text, so the adapter re-reads the few
 * characters it produced into the digits/decpt shape. A to-decimal
 * entry point in Żmij's C API (significand + exponent, the shape its
 * internal to_decimal already has) would remove that step; see
 * README.vendor for the upstream request.
 */

#include <Python.h>

#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "zmij-c.h"

/* Worst-case widths of the Żmij text we re-read:
 *   fixed      : 309 integer digits + '.' + precision          (no sign)
 *   scientific : 1 + '.' + precision + "e+308"                 (no sign)
 * The public zmij_write_* wrappers truncate to the buffer size we pass,
 * so these bounds are also what makes the re-read safe. */
#define ZMIJ_DTOA_FIXED_EXTRA 311
#define ZMIJ_DTOA_SCI_EXTRA 8

static char *
dup_digits(const char *src, size_t n, char **rve)
{
    char *out = (char *)PyMem_Malloc(n + 1);
    if (out == NULL) {
        return NULL;
    }
    memcpy(out, src, n);
    out[n] = '\0';
    if (rve) {
        *rve = out + n;
    }
    return out;
}

/* Re-read Żmij's "[d...][.d...][e[+-]dd]" text (no sign) into Gay's
 * digits/decpt shape: strips the decimal point, leading zeros and trailing
 * zeros, and folds the exponent into *decpt. Handles the fixed shape
 * ("123.45", "0.00123", "1500"), the scientific shape ("1.5e+20",
 * "5e-324") and the all-zero shape ("0.000" -> "" with decpt
 * -len(fraction)). Returns a PyMem_Malloc'd digit string or NULL. */
static char *
from_text(const char *s, size_t len, int *decpt, char **rve)
{
    const char *e = (const char *)memchr(s, 'e', len);
    size_t mant_len = e ? (size_t)(e - s) : len;

    int exp10 = 0;
    if (e != NULL) {
        const char *p = e + 1;
        const char *end = s + len;
        int neg = 0;
        if (p < end && (*p == '+' || *p == '-')) {
            neg = (*p == '-');
            p++;
        }
        while (p < end) {
            exp10 = exp10 * 10 + (*p - '0');
            p++;
        }
        if (neg) {
            exp10 = -exp10;
        }
    }

    const char *dot = (const char *)memchr(s, '.', mant_len);
    int int_len = dot ? (int)(dot - s) : (int)mant_len;

    char *out = (char *)PyMem_Malloc(mant_len + 1);
    if (out == NULL) {
        return NULL;
    }
    size_t n = 0;
    for (size_t i = 0; i < mant_len; i++) {
        if (s[i] != '.') {
            out[n++] = s[i];
        }
    }
    size_t lead = 0;
    while (lead < n && out[lead] == '0') {
        lead++;
    }
    n -= lead;
    memmove(out, out + lead, n);
    while (n > 0 && out[n - 1] == '0') {
        n--;
    }
    out[n] = '\0';

    /* int_len counts the digits before the point including stripped
     * leading zeros, so int_len - lead is where the point sits relative
     * to the first significant digit. For the all-zero case (n == 0)
     * this yields -(fraction length) == -ndigits, Gay's convention. */
    *decpt = int_len - (int)lead + exp10;
    if (rve) {
        *rve = out + n;
    }
    return out;
}

/* Mode 3 with ndigits = -k (k >= 1): round |d| to a multiple of 10**k,
 * ties to even against the exact value. Every finite double of magnitude
 * >= 2**52 is an integer, so floor() is exact and the exact decimal digits
 * of the integer part come from a precision-0 fixed conversion; the only
 * other information needed is whether a fractional part exists at all. */
static char *
mode3_negative(double abs_d, int k, int *decpt, char **rve)
{
    double ix = floor(abs_d);
    int frac_nonzero = (abs_d != ix);

    char intbuf[zmij_double_fixed_buffer_size];
    char *end = zmij_write_fixed(intbuf, sizeof intbuf, ix, 0);
    int intlen = (int)(end - intbuf);

    /* Fewer than k integer digits: |d| < 10**(k-1) < 10**k / 2 -> 0. */
    if (intlen < k) {
        *decpt = k;
        return dup_digits("", 0, rve);
    }

    int q_len = intlen - k;             /* digits of the quotient Q    */
    const char *r = intbuf + q_len;     /* the low k digits, remainder */

    int cmp;                            /* R <=> 10**k / 2             */
    if (r[0] < '5') {
        cmp = -1;
    }
    else if (r[0] > '5') {
        cmp = 1;
    }
    else {
        cmp = 0;
        for (int i = 1; i < k; i++) {
            if (r[i] != '0') {
                cmp = 1;
                break;
            }
        }
    }

    int round_up;
    if (cmp != 0) {
        round_up = cmp > 0;
    }
    else if (frac_nonzero) {
        round_up = 1;
    }
    else {
        char q_last = q_len > 0 ? intbuf[q_len - 1] : '0';
        round_up = ((q_last - '0') & 1) != 0;
    }

    /* Q (+1), with room for a carry-out digit. */
    char *q = (char *)PyMem_Malloc((size_t)q_len + 2);
    if (q == NULL) {
        return NULL;
    }
    memcpy(q, intbuf, (size_t)q_len);
    int qlen = q_len;
    if (round_up) {
        int i = qlen - 1;
        while (i >= 0 && q[i] == '9') {
            q[i--] = '0';
        }
        if (i >= 0) {
            q[i]++;
        }
        else {
            memmove(q + 1, q, (size_t)qlen);
            q[0] = '1';
            qlen++;
        }
    }
    if (qlen == 0) {                    /* Q == 0 and no round-up      */
        PyMem_Free(q);
        *decpt = k;
        return dup_digits("", 0, rve);
    }

    *decpt = k + qlen;                  /* value == Q * 10**k          */
    while (qlen > 0 && q[qlen - 1] == '0') {
        qlen--;
    }
    q[qlen] = '\0';
    if (rve) {
        *rve = q + qlen;
    }
    return q;
}

char *
_Py_zmij_dtoa(double d, int mode, int ndigits, int *decpt, int *sign,
              char **rve)
{
    *sign = signbit(d) ? 1 : 0;
    double abs_d = fabs(d);

    if (isinf(abs_d)) {
        *decpt = 9999;
        return dup_digits("Infinity", 8, rve);
    }
    if (isnan(abs_d)) {
        *decpt = 9999;
        return dup_digits("NaN", 3, rve);
    }
    if (abs_d == 0.0) {
        *decpt = 1;
        return dup_digits("0", 1, rve);
    }

    switch (mode) {
    case 0: {
        char buf[zmij_double_buffer_size];
        char *end = zmij_write(buf, sizeof buf, abs_d);
        return from_text(buf, (size_t)(end - buf), decpt, rve);
    }
    case 2: {
        int precision = (ndigits < 1 ? 1 : ndigits) - 1;  /* digits after '.' */
        char stack[zmij_double_scientific_buffer_size];
        char *buf = stack;
        size_t n = sizeof stack;
        if (precision >= 18) {
            n = (size_t)precision + ZMIJ_DTOA_SCI_EXTRA;
            buf = (char *)PyMem_Malloc(n);
            if (buf == NULL) {
                return NULL;
            }
        }
        char *end = zmij_write_scientific(buf, n, abs_d, precision);
        char *out = from_text(buf, (size_t)(end - buf), decpt, rve);
        if (buf != stack) {
            PyMem_Free(buf);
        }
        return out;
    }
    default: {                          /* mode 3, like Gay's fallthrough */
        if (ndigits < 0) {
            return mode3_negative(abs_d, -ndigits, decpt, rve);
        }
        char stack[zmij_double_fixed_buffer_size];
        char *buf = stack;
        size_t n = sizeof stack;
        if (ndigits > 18) {
            n = (size_t)ndigits + ZMIJ_DTOA_FIXED_EXTRA;
            buf = (char *)PyMem_Malloc(n);
            if (buf == NULL) {
                return NULL;
            }
        }
        char *end = zmij_write_fixed(buf, n, abs_d, ndigits);
        char *out = from_text(buf, (size_t)(end - buf), decpt, rve);
        if (buf != stack) {
            PyMem_Free(buf);
        }
        return out;
    }
    }
}

void
_Py_zmij_dtoa_free(char *s)
{
    PyMem_Free(s);
}
