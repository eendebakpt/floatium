"""Edge cases that commonly break hand-rolled dtoa replacements.

These are curated from bugs in real projects: off-by-one exponent
normalization, negative-zero in %g, integer boundary at 2^53,
tiny-number exponent widths, alternate format flag.
"""

from __future__ import annotations

import math

import pytest

import floatium

pytestmark = pytest.mark.usefixtures("patched")


def test_negative_zero_preserved():
    assert repr(-0.0) == "-0.0"
    assert str(-0.0) == "-0.0"


def test_negative_zero_suppressed_for_g():
    # Python's g-formatting does *not* suppress -0.0 by default; but the
    # formatter used by repr does add a sign. Document the actual behavior.
    assert format(-0.0, "g") == "-0"
    assert format(-0.0, ".2f") == "-0.00"


def test_two_power_53_boundary():
    assert repr(float(2**53 - 1)) == "9007199254740991.0"
    assert repr(float(2**53)) == "9007199254740992.0"
    # 2^53 + 1 rounds to 2^53 in double; the repr reflects the stored value.
    assert repr(float(2**53 + 1)) == "9007199254740992.0"
    assert repr(float(2**53 + 2)) == "9007199254740994.0"


def test_smallest_subnormal():
    x = 5e-324
    assert repr(x) == "5e-324"


def test_largest_finite():
    x = 1.7976931348623157e308
    assert repr(x) == "1.7976931348623157e+308"


def test_exponent_padding_is_two_digits_minimum():
    # CPython pads the exponent to at least 2 digits: "1e+05", not "1e+5".
    assert repr(1e5) == "100000.0"  # not exponential for repr
    assert format(1e5, "e") == "1.000000e+05"
    assert format(1e-5, "e") == "1.000000e-05"
    assert format(1e100, "e") == "1.000000e+100"


def test_alternate_format_flag():
    # '#' forces trailing decimal point on 'g'.
    assert format(1.0, "#g") == "1.00000"
    assert format(1.0, "g") == "1"


def test_g_switchover_to_exponential():
    # Python uses exponential for g when exp < -4 or >= precision.
    assert format(0.0001, "g") == "0.0001"
    assert format(0.00001, "g") == "1e-05"  # boundary
    assert format(1e6, "g") == "1e+06"     # boundary for precision=6 default


@pytest.mark.parametrize("x,expected", [
    (0.1,                "0.1"),
    (0.2,                "0.2"),
    (0.1 + 0.2,          "0.30000000000000004"),
    (1/3,                "0.3333333333333333"),
    (math.pi,            "3.141592653589793"),
    (math.e,             "2.718281828459045"),
])
def test_famous_values(x, expected):
    assert repr(x) == expected


def test_large_integer_valued_float():
    # Values that are integers but far beyond 2^53 lose precision; the
    # shortest repr reflects the stored value.
    x = 1e20
    s = repr(x)
    assert float(s) == x
    assert "e" in s or s.endswith(".0") or "." in s


def test_round_trip_known_problem_values():
    # A pile of values that have historically caused trouble in dtoa
    # implementations. The goal here is just "round-trips"; we don't
    # pin the exact string (that's in test_parity.py).
    tough = [
        1e23, 9e15, 8e15, 4e18, 9.999999999999999e22,
        2.2250738585072011e-308,  # smallest normal - 1 ulp
        2.2250738585072014e-308,  # smallest normal
        math.nextafter(1.0, 2.0),
        math.nextafter(1.0, 0.0),
    ]
    for x in tough:
        assert float(repr(x)) == x, repr(x)
