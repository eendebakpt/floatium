/* ffc_strtod.c - _Py_dg_strtod drop-in backed by ffc.h (C99 fast_float port).
 *
 * This is the parse half of the pair floatium proposes for CPython (the
 * format half is zmij_dtoa.c), so it is plain C11 against the exact
 * _Py_dg_strtod contract and uses nothing from CPython:
 *
 *   double _Py_ffc_strtod(const char *nptr, char **endptr);
 *
 *   - no leading-whitespace skipping (PyOS_string_to_double relies on it);
 *   - optional sign, decimal mantissa with optional '.', optional exponent;
 *   - "inf" / "nan" are NOT accepted: pystrtod.c's _Py_parse_inf_or_nan
 *     owns those so CPython's exact spellings and casing rules stay put;
 *   - *endptr points past the consumed characters, or at nptr when no
 *     number was found (return value 0.0);
 *   - overflow returns +-HUGE_VAL, underflow the nearest value (possibly
 *     0 or subnormal); both set errno = ERANGE like strtod.
 *
 * ffc.h is the same pipeline as fast_float: Clinger fast path, then
 * Eisel-Lemire, then an exact big-integer digit comparison for the rare
 * hard cases. Every result is correctly rounded (ties to even) and no
 * floating-point arithmetic is done on the way, so the result does not
 * depend on the x87 precision mode that dtoa.c needs to control.
 */

#define FFC_IMPL
#include "ffc.h"

#include <errno.h>
#include <string.h>

double
_Py_ffc_strtod(const char *nptr, char **endptr)
{
    const char *last = nptr + strlen(nptr);
    double value = 0.0;

    ffc_parse_options options = ffc_parse_options_default();
    options.format = FFC_PRESET_GENERAL
                     | FFC_FORMAT_FLAG_ALLOW_LEADING_PLUS
                     | FFC_FORMAT_FLAG_NO_INFNAN;
    ffc_result result = ffc_from_chars_double_options(nptr, last, &value, options);

    if (result.outcome == FFC_OUTCOME_INVALID_INPUT) {
        if (endptr) {
            *endptr = (char *)nptr;
        }
        return 0.0;
    }
    if (endptr) {
        *endptr = (char *)result.ptr;
    }
    if (result.outcome == FFC_OUTCOME_OUT_OF_RANGE) {
        errno = ERANGE;
    }
    return value;
}
