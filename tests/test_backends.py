"""Every compiled-in backend must match stock CPython, not just the default.

The wheels ship fmt_opt + fast_float, but the CMake "all" build (used by
the test-all-backends CI job) also compiles fmt, ryu_opt, wuffs and
stock. Before this file only one test ever exercised a non-default
backend. Comparisons are done in-process: stock output is collected with
floatium uninstalled, then each backend is installed in turn.
"""

from __future__ import annotations

import math
import random
import struct

import pytest

import floatium

_INFO = floatium.info()
FORMAT_BACKENDS = _INFO["available_format_backends"].split(",")
PARSE_BACKENDS = _INFO["available_parse_backends"].split(",")


def _bits(b: int) -> float:
    return struct.unpack("<d", b.to_bytes(8, "little"))[0]


def _outcome(fn, *args):
    """Run fn(*args); return ("ok", value) or (exception name, message)."""
    try:
        return ("ok", fn(*args))
    except Exception as e:
        return (type(e).__name__, str(e))


_rng = random.Random(0xB4C7E)
VALUES: list[float] = [
    0.0, -0.0, 1.0, -1.0, 0.1, 0.5, 1.5, 2.5, 0.125, 0.375, 2.675, 1.005,
    1e16, 1e17, 1e22, 1e23, 1e100, 1e-100, 1e300, 5e-324,
    1.7976931348623157e308, 2.2250738585072014e-308, 9.5, 0.05, 0.005,
    999999.5, 9.5e-7, float(2**53), math.pi, math.inf, -math.inf, math.nan,
]
VALUES += [_bits(_rng.getrandbits(64)) for _ in range(2000)]
VALUES += [_rng.uniform(-1e6, 1e6) for _ in range(500)]
VALUES += [round(_rng.uniform(-1000, 1000), _rng.randint(0, 6)) for _ in range(500)]
VALUES += [_bits(_rng.getrandbits(52) | (_rng.getrandbits(1) << 63)) for _ in range(300)]

SPECS = ["", ".0f", ".1f", ".2f", ".6f", ".17f", ".30f", ".100f", ".0e", ".1e", ".5e",
         ".17e", ".60e", "g", ".1g", ".5g", ".12g", ".17g", ".30g", "G", "E", "F",
         "f", "e", ".0g", "#g", "#.3g", "#.0f", "#.0e", "+.2f", "r", "n"]

PARSE_STRINGS: list[str] = [
    "1e400", "-1e400", "1e-400", "0x10", "1_0", "nan(1)", "infinity", "INF", "nan",
    "  1.5\t", "1.5e", "+.5", "5.", ".", "+", "", "1,5", "1\x002", "\x1c1.5\x1f",
    "1e-324", "2.4703282292062327e-324", "2.4703282292062328e-324",
    "9007199254740993", "1.7976931348623158e308", "1.7976931348623159e308",
    "0" * 400 + ".5", "1" + "0" * 400, "0." + "0" * 400 + "1",
    # Integer part longer than Wuffs' 800-digit HPD cap (upstream bug,
    # fixed locally — see third_party/wuffs/README.vendor item 7).
    "1" + "9" * 800 + "e-800", "1" + "0" * 800 + "e-800", "1" + "2" * 805 + "e-805",
    "9" * 801 + ".5e-800", "1" + "9" * 799 + "e-800",
]
for _x in VALUES[:800]:
    PARSE_STRINGS += [repr(_x), format(_x, ".25e"), format(_x, ".30g"), format(_x, "f")]
for _ in range(1000):
    _n = _rng.randint(1, 60)
    PARSE_STRINGS.append(
        "".join(_rng.choice("0123456789") for _ in range(_n))
        + "." + "".join(_rng.choice("0123456789") for _ in range(_rng.randint(0, 40)))
        + _rng.choice(["", "e" + str(_rng.randint(-330, 330))])
    )
for _ in range(200):
    PARSE_STRINGS.append(
        "0." + "".join(_rng.choice("0123456789") for _ in range(_rng.randint(100, 1200)))
    )
    PARSE_STRINGS.append(
        "".join(_rng.choice("0123456789") for _ in range(_rng.randint(100, 900)))
        + "e" + str(_rng.randint(-1100, 400))
    )


def _parse_outcome(s: str):
    r = _outcome(float, s)
    if r[0] == "ok":
        return ("ok", struct.pack("<d", r[1]))  # compare bits, so nan == nan
    return r


def _format_table() -> dict:
    """{(index, spec): outcome} for every value/spec; "repr" is a pseudo-spec.

    Keys use the *index* into VALUES, not the value: 0.0 and -0.0 compare
    equal and would otherwise collapse into one dict slot.
    """
    out = {}
    for i, x in enumerate(VALUES):
        out[(i, "repr")] = _outcome(repr, x)
        for spec in SPECS:
            out[(i, spec)] = _outcome(format, x, spec)
    return out


@pytest.fixture(scope="module")
def stock_format():
    floatium.uninstall()
    return _format_table()


@pytest.fixture(scope="module")
def stock_parse():
    floatium.uninstall()
    return {s: _parse_outcome(s) for s in PARSE_STRINGS}


@pytest.mark.parametrize("backend", FORMAT_BACKENDS)
def test_format_backend_matches_stock(backend, stock_format):
    floatium.uninstall()
    floatium.install(format_backend=backend)
    try:
        assert floatium.info()["format_backend"] == backend
        ours = _format_table()
        bad = [((VALUES[i], spec), expected, ours[(i, spec)])
               for (i, spec), expected in stock_format.items()
               if ours[(i, spec)] != expected]
        assert not bad, f"{len(bad)} divergences, first: {bad[:5]}"
    finally:
        floatium.uninstall()
        floatium.install()


@pytest.mark.parametrize("backend", PARSE_BACKENDS)
def test_parse_backend_matches_stock(backend, stock_parse):
    floatium.uninstall()
    floatium.install(parse_backend=backend)
    try:
        assert floatium.info()["parse_backend"] == backend
        bad = [(s[:60], exp, _parse_outcome(s)) for s, exp in stock_parse.items()
               if _parse_outcome(s) != exp]
        assert not bad, f"{len(bad)} divergences, first: {bad[:5]}"
    finally:
        floatium.uninstall()
        floatium.install()
