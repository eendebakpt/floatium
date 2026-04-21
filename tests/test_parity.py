"""Byte-for-byte parity with stock CPython's float output.

The `fmt-fastfloat` CPython branch claims bit-identical output vs the
stock dtoa build. floatium vendors the same wrappers, so these tests
reconfirm that claim against the interpreter the wheel actually runs on.

Any failure here is either (a) a divergence we need to document in
DIFFERENCES.md, or (b) a bug in our packaging layer (format_float_short
port) that doesn't exist in the CPython branch. Report both upstream.
"""

from __future__ import annotations

import math
import subprocess
import sys

import pytest

import floatium

# Corpus of "interesting" values. Every entry must round-trip under any
# correct formatter; here we additionally require the *text* to match.
_CORPUS = [
    0.0, -0.0, 1.0, -1.0, 0.1, 0.2, 0.1 + 0.2,
    1e-1, 1e-2, 1e-3, 1e-4, 1e-5,
    1e16, 1e17, 1e100, 1e-100,
    1.7976931348623157e308, 2.2250738585072014e-308,
    5e-324,  # smallest subnormal
    3.141592653589793, 2.718281828459045,
    123456789.0, 0.0001, 1e-7,
    2**53 - 1, float(2**53), float(2**53 + 1),  # integer boundary
]

_FORMAT_SPECS = ["", ".2f", ".5f", ".0f", ".2e", ".5e", ".10e",
                 "g", "G", "e", "E", "f", "F",
                 ".3g", ".6g", ".10g", "r"]


def _stock(expr: str) -> str:
    import os
    env = os.environ.copy()
    env.pop("FLOATIUM_AUTOPATCH", None)
    proc = subprocess.run(
        [sys.executable, "-c", f"import sys; sys.stdout.write({expr})"],
        env=env, capture_output=True, text=True, check=True,
    )
    return proc.stdout


@pytest.mark.parametrize("x", _CORPUS)
def test_repr_parity(x):
    stock = _stock(f"repr({x!r})")
    with floatium.patched():
        ours = repr(x)
    assert ours == stock, f"repr({x!r}): ours={ours!r} stock={stock!r}"


@pytest.mark.parametrize("x", _CORPUS)
def test_str_parity(x):
    stock = _stock(f"str({x!r})")
    with floatium.patched():
        ours = str(x)
    assert ours == stock, f"str({x!r}): ours={ours!r} stock={stock!r}"


@pytest.mark.parametrize("x", _CORPUS)
@pytest.mark.parametrize("spec", _FORMAT_SPECS)
def test_format_parity(x, spec):
    # Skip 'r' for floats where the built-in behaves oddly; not a real spec.
    if spec == "r":
        pytest.skip("'r' is not a real format spec for __format__")
    stock = _stock(f"format({x!r}, {spec!r})")
    with floatium.patched():
        ours = format(x, spec)
    assert ours == stock, (
        f"format({x!r}, {spec!r}): ours={ours!r} stock={stock!r}"
    )


@pytest.mark.parametrize("s", [
    "0", "0.0", "1", "1.0", "-1", "3.14159", "1e10", "1e-10",
    "1.5e+5", "-2.5e-3", "1234567890", "0.00001",
])
def test_float_parse_parity(s):
    stock = _stock(f"repr(float({s!r}))")
    with floatium.patched():
        ours = repr(float(s))
    assert ours == stock, f"float({s!r}): ours={ours!r} stock={stock!r}"


def test_nan_inf_parity():
    for name in ["nan", "inf", "-inf", "+inf"]:
        stock = _stock(f"repr(float({name!r}))")
        with floatium.patched():
            ours = repr(float(name))
        # NaN is parsed via the fallback (fast_float rejects inf/nan literals
        # with our no_infnan setting), so this tests the fallback too.
        assert ours == stock, f"float({name!r}): ours={ours!r} stock={stock!r}"
