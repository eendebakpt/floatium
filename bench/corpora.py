"""Canonical benchmark corpora.

Each corpus represents a distinct profile of float values we've seen
stress different parts of dtoa implementations:

- ``random_uniform``: uniform on [0, 1). Generic case.
- ``random_bits``: every 64-bit pattern is an input. Exercises the full
  exponent range, subnormals, extreme values.
- ``financial``: two-decimal values like prices. Shortest path tends to
  emit 2-4 chars; the format code exercises the <= 16-digit path.
- ``scientific``: uniform log-distributed over [1e-200, 1e200]. The
  exponent path dominates.
- ``integer_valued``: values like 1.0, 42.0, 1e6. Exercises the
  "add ``.0``" integer-handling branch of repr.

Corpora are seeded so benchmark runs are reproducible.
"""

from __future__ import annotations

import math
import random
import struct


def random_uniform(n: int = 10_000, seed: int = 1) -> list[float]:
    rng = random.Random(seed)
    return [rng.random() for _ in range(n)]


def random_bits(n: int = 10_000, seed: int = 2) -> list[float]:
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        bits = rng.getrandbits(64)
        x = struct.unpack("<d", bits.to_bytes(8, "little"))[0]
        if math.isfinite(x):
            out.append(x)
    return out


def financial(n: int = 10_000, seed: int = 3) -> list[float]:
    rng = random.Random(seed)
    return [round(rng.uniform(0.01, 99999.99), 2) for _ in range(n)]


def scientific(n: int = 10_000, seed: int = 4) -> list[float]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        exp = rng.uniform(-200, 200)
        mantissa = rng.uniform(1.0, 9.9999)
        out.append(mantissa * (10.0 ** exp))
    return out


def integer_valued(n: int = 10_000, seed: int = 5) -> list[float]:
    rng = random.Random(seed)
    return [float(rng.randint(-(10**9), 10**9)) for _ in range(n)]


ALL = {
    "random_uniform": random_uniform,
    "random_bits":    random_bits,
    "financial":      financial,
    "scientific":     scientific,
    "integer_valued": integer_valued,
}


def get(name: str, n: int = 10_000) -> list[float]:
    if name not in ALL:
        raise KeyError(f"unknown corpus: {name} (available: {sorted(ALL)})")
    return ALL[name](n)


def all_corpora(n: int = 10_000) -> dict[str, list[float]]:
    return {name: fn(n) for name, fn in ALL.items()}
