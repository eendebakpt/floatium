# floatium

Experimental drop-in replacement for CPython's float formatting and parsing,
backed by the [{fmt}](https://github.com/fmtlib/fmt) and
[fast_float](https://github.com/fastfloat/fast_float) C++ libraries.

`pip install floatium`, set `FLOATIUM_AUTOPATCH=1`, and every subsequent
Python process uses `{fmt}`'s Dragonbox for `repr(float)` / `str(float)` /
`float.__format__` and `fast_float` for `float("...")`. Existing code,
existing tests, existing output — just faster. Works with an unmodified
stock CPython; no interpreter rebuild required.

## Installation

```bash
pip install floatium
```

### From source

Source builds require a C++17 compiler (GCC 9+, Clang 12+, or MSVC
2019+) and CMake ≥ 3.20.

```bash
git clone https://github.com/eendebakpt/floatium
cd floatium
pip install -e '.[test]'
```

Tests and benchmarks target **CPython 3.14**. No system libraries are
required; `{fmt}` and `fast_float` are vendored.

## Why this package exists

CPython's float formatting has gone through
[`Python/dtoa.c`](https://github.com/python/cpython/blob/main/Python/dtoa.c)
— David Gay's 1991 reference implementation — for three decades. The
code is ~2,800 lines of hand-tuned C and slower than modern alternatives.
Its parsing counterpart (`_Py_dg_strtod` in the same file) has similar
constraints.

Floatium demonstrates what replacing both sides looks like, as a pip
package against stock CPython:

- **Format** (double → string) via `{fmt}`'s Dragonbox algorithm — the
  same algorithm that backs C++20's `std::format`. Fixed-precision
  formatting for huge-magnitude values is routed through Ryu's
  `d2fixed` to sidestep fmt's Dragon4 + bigint slow path.
- **Parse** (string → double) via `fast_float`'s Eisel–Lemire + bignum
  path — the same algorithm Rust's `std`, Apache Arrow, and DuckDB use.

Both produce output **bit-identical** to stock CPython on every input
we've tested (see [DIFFERENCES.md](DIFFERENCES.md) — currently zero
divergences against CPython 3.15's stdlib test suite).

Library choices: `{fmt}` is MIT, header-only, and ships Dragonbox
+ grammar + fallbacks from a single upstream (~9.4k LOC vendored).
`fast_float` is Apache-2.0 / MIT / Boost-1.0 triple-licensed, header-only,
C++11, and used in Chromium, Apache Arrow, ClickHouse, folly, and DuckDB.
Ryu is Apache-2.0 / Boost-1.0 dual-licensed and only its `d2fixed` entry
point is vendored (~100 KB of pow10 tables). Slots are backend-swappable
— see [INTERNALS.md](INTERNALS.md).

## Usage

### Autopatch (recommended)

Once `floatium` is installed, setting `FLOATIUM_AUTOPATCH=1` before any
Python process starts installs the replacement for the life of that
process:

```bash
export FLOATIUM_AUTOPATCH=1
python -c "import json; print(json.dumps([0.1, 0.2, 1e100]))"
# [0.1, 0.2, 1e+100]
```

The mechanism is a `.pth` file placed in `site-packages/` at install
time — `site.py` executes it during interpreter startup, before user
code, and the hook calls `install()` if the env var is set.

### Explicit

```python
import floatium

floatium.install()          # patch PyFloat_Type slots
assert repr(0.1) == "0.1"
floatium.uninstall()        # restore
```

### Scoped

```python
import floatium

with floatium.patched():
    do_something_float_heavy()
```

## What it patches

| Surface                             | How                                           |
|-------------------------------------|-----------------------------------------------|
| `repr(x)`, `str(x)`, `f"{x}"`       | `PyFloat_Type.tp_repr` pointer swap            |
| `f"{x:.2f}"`, `format(x, spec)`     | `__format__` entry in `PyFloat_Type.tp_dict`   |
| `"{}".format(x)`                    | via `__format__`                              |
| `float("1.5")`                      | `PyFloat_Type.tp_new` pointer swap             |
| `json.dumps([x])`                   | via `__repr__`                                |

`"%g" % x` is **not** patched — see [DIFFERENCES.md](DIFFERENCES.md).

## Benchmarks

Run locally with:

```bash
python -m bench.bench_ns_per_op --markdown        # quick ns/op table
bench/run_all.sh                                  # full pyperf sweep
```

Numbers below are from a release CPython 3.14.3 build
(`python -m bench.bench_ns_per_op`, median of fastest third of samples,
lower is better). The default backend is `fmt_opt`; see
[INTERNALS.md](INTERNALS.md) for the routing. The `fmt` column is the
plain-fmt backend, included for A/B transparency:

| Corpus          | Operation       | Stock (ns) | fmt (ns) | fmt_opt (ns) | fmt vs stock | fmt_opt vs stock |
|-----------------|-----------------|-----------:|---------:|-------------:|-------------:|-----------------:|
| random_uniform  | `repr(x)`       |        289 |       97 |           97 |        2.99× |            2.98× |
| random_uniform  | `f"{x:.4f}"`    |        119 |      104 |          104 |        1.14× |            1.15× |
| random_uniform  | `float(s)`      |        121 |      121 |          121 |        1.00× |            1.00× |
| random_bits     | `repr(x)`       |        820 |      136 |          137 |        6.03× |            5.99× |
| random_bits     | `f"{x:.4f}"`    |      1,940 |    5,530 |          193 |        0.35× |           10.04× |
| random_bits     | `float(s)`      |        277 |      279 |          278 |        0.99× |            1.00× |
| financial       | `repr(x)`       |        173 |       80 |           80 |        2.16× |            2.15× |
| financial       | `f"{x:.4f}"`    |        146 |       99 |          101 |        1.46× |            1.44× |
| financial       | `float(s)`      |         37 |       37 |           37 |        1.00× |            1.00× |
| scientific      | `repr(x)`       |        637 |      133 |          133 |        4.79× |            4.78× |
| scientific      | `f"{x:.4f}"`    |      1,081 |    2,961 |          158 |        0.36× |            6.84× |
| scientific      | `float(s)`      |        213 |      213 |          212 |        1.00× |            1.00× |
| integer_valued  | `repr(x)`       |        143 |       88 |           88 |        1.63× |            1.64× |
| integer_valued  | `f"{x:.4f}"`    |        167 |      105 |          106 |        1.59× |            1.58× |
| integer_valued  | `float(s)`      |         43 |       43 |           43 |        1.00× |            1.00× |

**fmt_opt eliminates the fixed-mode regression.** Plain `fmt` regresses
by 2-3× on `random_bits` and `scientific` `f"{x:.4f}"` because
`fmt::detail::format_float` falls into a Dragon4 + bigint classical loop
when the value's decade + requested precision exceeds the 19-digit
Dragonbox first segment. `fmt_opt` detects that cliff from the binary
exponent and routes only those cases through Ryu's `d2fixed` — which is
block-based and always fast — while keeping fmt's fast subsegment path
for ordinary magnitudes. Output is bit-identical on both paths.

**Parse is flat at this layer.** `fast_float` beats `_Py_dg_strtod` on
raw `from_chars`, but the wrapper's per-call overhead (UTF-8 extraction,
whitespace strip, null-termination copy, `PyFloat_FromDouble`) cancels
the gain on these corpora. The speedup is recoverable either by lifting
the hook closer to `PyFloat_FromString` (requires an in-tree CPython
change, out of scope for a pip package) or by batching string-heavy
workloads where the per-call overhead amortizes — JSON and CSV parsers
are the obvious candidates.

## Running CPython's test suite against floatium

`tools/run_stdlib_tests.py` runs a curated set of CPython's own stdlib
regression tests with floatium autopatched. Zero divergences on the
default set as of the last update; see [DIFFERENCES.md](DIFFERENCES.md)
for the current status.

```bash
python tools/run_stdlib_tests.py
# ==> running: python -m test test_float test_strtod test_fstring ...
# == Tests result: SUCCESS ==
# All 12 tests OK.
# Total tests: run=1,616 skipped=210
```

## Limitations

See [DIFFERENCES.md](DIFFERENCES.md) for the full list. Summary:

- **`"%g" % x` is not patched.** The `%` operator calls
  `PyOS_double_to_string` directly from `libpython`; no pip package can
  intercept that without `LD_PRELOAD`.
- **Patching is process-global.** One `install()` per process; affects
  all threads, all modules.
- **`Py_TPFLAGS_IMMUTABLETYPE` bypass.** We write directly to
  `PyFloat_Type` slots, bypassing the public type-attribute API that
  honors the flag. This is a known-stable internal technique (CPython
  itself does it during bootstrap) but explicitly not part of the stable
  ABI.
- **Free-threaded builds.** Supported; patching must happen at import
  time (the only safe window). Method-cache invalidation uses
  `PyType_Modified()` except on 3.15 debug builds (where that call
  asserts on static types), in which case the wrapper falls back to
  writing `tp_version_tag = 0` directly.
- **`float("1_000.5")` and `float("inf")` take the fallback path.** Both
  parse correctly (output is bit-identical to stock) but don't benefit
  from `fast_float`'s speed.

## License

- floatium wrapper code: **MIT**.
- `{fmt}` (vendored in `third_party/fmt/`): **MIT**.
- `fast_float` (vendored in `third_party/fast_float/`): **Apache-2.0 OR
  MIT OR Boost-1.0**.
- Ryu `d2fixed` (vendored in `third_party/ryu/`): **Apache-2.0 OR
  Boost-1.0**.
- `src/format_short.cc` is a port of code from CPython `Python/pystrtod.c`,
  which is under the **PSF License**. The port preserves the original
  attribution and is compatible with downstream MIT redistribution under
  the PSF license's permissive terms.

See `LICENSE` and the per-directory `LICENSE*` files.

## Status

Pre-alpha. v0.1.x — the API will stay small (the four functions in
`floatium/__init__.py`) but the internals will change.
