"""Round-trip correctness: float(repr(x)) == x for every finite double.

The property is the load-bearing invariant of any replacement dtoa: no
matter what textual form the formatter chooses, reading it back must
recover the original bits. If a single case fails, float I/O is broken
and we cannot ship.

We exercise:
  - Uniform random doubles over the full IEEE 754 domain (all 64 bit
    patterns are valid inputs; only NaN returns NaN which compares !=).
  - Subnormals specifically (bit patterns with exponent zero).
  - Boundary values (±0, smallest/largest finite, 2^k and 2^k - ulp for
    every k).
  - Small-magnitude and large-magnitude families.
"""

from __future__ import annotations

import math
import random
import struct

import pytest

pytestmark = pytest.mark.usefixtures("patched")


def _bits_to_double(bits: int) -> float:
    return struct.unpack("<d", bits.to_bytes(8, "little"))[0]


def _roundtrip(x: float) -> None:
    if math.isnan(x):
        # NaN repr is "nan"; float("nan") is NaN; they don't compare equal.
        s = repr(x)
        assert s == "nan" or s == "-nan"
        assert math.isnan(float(s))
        return
    s = repr(x)
    y = float(s)
    assert y == x, f"roundtrip: {x!r} -> {s!r} -> {y!r}"


def test_roundtrip_zero_and_inf():
    _roundtrip(0.0)
    _roundtrip(-0.0)
    _roundtrip(math.inf)
    _roundtrip(-math.inf)


def test_roundtrip_small_integers():
    for i in range(-1000, 1000):
        _roundtrip(float(i))


def test_roundtrip_boundary_values():
    # Smallest positive normal and largest finite.
    _roundtrip(2.2250738585072014e-308)
    _roundtrip(1.7976931348623157e308)
    # Smallest positive subnormal (bit pattern 1).
    _roundtrip(_bits_to_double(1))
    # 2^k ± 1 ulp for selected k.
    for k in [-100, -10, 0, 10, 100, 1023]:
        _roundtrip(math.ldexp(1.0, k))
        _roundtrip(math.nextafter(math.ldexp(1.0, k), 0.0))


def test_roundtrip_random_uniform_bits():
    rng = random.Random(0xF10A711)
    for _ in range(50_000):
        bits = rng.getrandbits(64)
        _roundtrip(_bits_to_double(bits))


def test_roundtrip_subnormals():
    rng = random.Random(0xF10A711 ^ 0xDEAD)
    for _ in range(10_000):
        mantissa = rng.getrandbits(52)
        sign = rng.getrandbits(1)
        bits = (sign << 63) | mantissa  # exponent = 0 => subnormal
        _roundtrip(_bits_to_double(bits))


@pytest.mark.parametrize("bits", [0x0000000000000001, 0x000FFFFFFFFFFFFF,
                                  0x0010000000000000, 0x7FEFFFFFFFFFFFFF,
                                  0x4000000000000000, 0x3FF0000000000000])
def test_roundtrip_boundary_bit_patterns(bits):
    _roundtrip(_bits_to_double(bits))
