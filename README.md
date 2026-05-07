# floatium

[![PyPI](https://img.shields.io/pypi/v/floatium.svg)](https://pypi.org/project/floatium/)
[![Python versions](https://img.shields.io/pypi/pyversions/floatium.svg)](https://pypi.org/project/floatium/)
[![License](https://img.shields.io/pypi/l/floatium.svg)](https://github.com/eendebakpt/floatium/blob/main/LICENSE)

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

A **pure-C** format backend (`ryu_opt`, using Ryu's `d2s` + `d2fixed` +
`d2exp`) is also available for callers who want zero C++ in the
float-formatting path. See [Backends](#backends) below.

All backends produce output **bit-identical** to stock CPython on every
input we've tested (see [DIFFERENCES.md](DIFFERENCES.md) — currently
zero divergences against CPython 3.15's stdlib test suite).

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

## Backends

Three format backends and two parse backends are available. All format
backends produce bit-identical output. Pick one at build time, or build
all of them and switch at install time.

| Format backend | Algorithm                                          | C++ used? |
|----------------|----------------------------------------------------|-----------|
| `fmt_opt` (default) | `{fmt}` Dragonbox (modes 0/2) + Ryu `d2fixed` (mode 3) | yes |
| `fmt`          | `{fmt}` Dragonbox + `fmt::detail::format_float`    | yes       |
| `ryu_opt`      | Ryu `d2s` (mode 0) + `d2exp` (mode 2) + `d2fixed` (mode 3) | **no** |
| `stock`        | marker — uninstalls and uses CPython's `dtoa.c`    | no        |

| Parse backend  | Algorithm                                  | C++ used? |
|----------------|--------------------------------------------|-----------|
| `fast_float` (default) | Eisel–Lemire + bignum fallback     | yes       |
| `stock`        | marker — uninstalls and uses CPython's `_Py_dg_strtod` | no |

`ryu_opt` paired with `parse_backend="stock"` gives a fully pure-C
operation (zero C++ on either side). To build only the pure-C path:

```bash
pip install -e . \
  -C cmake.define.FLOATIUM_FORMAT_BACKEND=ryu_opt \
  -C cmake.define.FLOATIUM_PARSE_BACKEND=stock
```

Or build every backend and pick at runtime:

```bash
pip install -e . \
  -C cmake.define.FLOATIUM_FORMAT_BACKEND=all \
  -C cmake.define.FLOATIUM_PARSE_BACKEND=all
```

```python
import floatium
floatium.install(format_backend="ryu_opt", parse_backend="stock")
```

The `ryu_opt` adapter (mode dispatch, FP fast path for `%e`/`%g`,
banker's rounding for `round(x, k)` with negative `k`) is ported from
the [`rye_float`](https://github.com/eendebakpt/cpython/tree/rye_float)
companion CPython branch — the in-tree pure-C demonstrator that drops
`Python/dtoa.c`.

### Vendored libraries

All three are vendored directly from upstream — pinned versions live in
each `third_party/<lib>/README.vendor`:

| Library | Upstream | Resync |
|---|---|---|
| [`{fmt}`](https://github.com/fmtlib/fmt) | `fmtlib/fmt` | `tools/sync_fmt.sh [/path/to/fmt]` |
| [`fast_float`](https://github.com/fastfloat/fast_float) | `fastfloat/fast_float` | `tools/sync_fast_float.sh [/path/to/fast_float]` |
| [`Ryu`](https://github.com/ulfjack/ryu) | `ulfjack/ryu` | `tools/sync_ryu.sh [/path/to/ryu]` |

Each script defaults to `~/<libname>` and copies a fixed file set into
`third_party/<lib>/`. None of the vendored files are locally modified
except for one trivial include rewrite in Ryu (`#include "ryu/X"` →
`#include "X"`); see each `README.vendor` for the file list.

The C++ adapter shims that bridge these libraries to CPython's
formatting/parsing contracts (`fmt_dtoa.cc`, `fmt_opt_dtoa.cc`,
`fast_float_strtod.cc`, `ryu_opt_dtoa.cc`) live in
`src/cpython_adapter/` as floatium-owned code.

## Benchmarks

Run locally with:

```bash
python -m bench.bench_ns_per_op --markdown        # quick ns/op table
bench/run_all.sh                                  # full pyperf sweep
```

Numbers below are from a release CPython 3.14.3 build
(`python -m bench.bench_ns_per_op`, median of fastest third of samples,
lower is better) using floatium's default `fmt_opt` format backend +
`fast_float` parse backend. See [INTERNALS.md](INTERNALS.md) for the
routing inside `fmt_opt`, and the [Backends](#backends) section above
for how to A/B against `fmt`, `ryu_opt`, or `stock`:

| Corpus          | Operation       | Stock (ns) | floatium (ns) | Speedup |
|-----------------|-----------------|-----------:|--------------:|--------:|
| random_uniform  | `repr(x)`       |        284 |            96 |   2.95× |
| random_uniform  | `f"{x:.4f}"`    |        119 |           103 |   1.16× |
| random_uniform  | `float(s)`      |        121 |            44 |   2.79× |
| random_bits     | `repr(x)`       |        820 |           134 |   6.11× |
| random_bits     | `f"{x:.4f}"`    |      1,933 |           196 |   9.86× |
| random_bits     | `float(s)`      |        275 |            61 |   4.52× |
| financial       | `repr(x)`       |        171 |            80 |   2.14× |
| financial       | `f"{x:.4f}"`    |        145 |           101 |   1.43× |
| financial       | `float(s)`      |         37 |            36 |   1.01× |
| scientific      | `repr(x)`       |        640 |           135 |   4.74× |
| scientific      | `f"{x:.4f}"`    |      1,081 |           161 |   6.71× |
| scientific      | `float(s)`      |        212 |            58 |   3.64× |
| integer_valued  | `repr(x)`       |        143 |            88 |   1.62× |
| integer_valued  | `f"{x:.4f}"`    |        169 |           106 |   1.60× |
| integer_valued  | `float(s)`      |         43 |            42 |   1.02× |

**Wins are largest on hard inputs.** `random_bits` and `scientific`
corpora — values whose decimal expansion stresses dtoa's big-integer
path — see 6–10× on `repr` / `f"{x:.4f}"` and 3.6–4.5× on `float(s)`.
On `financial` and `integer_valued`, parse stays near 1× because the
inputs are short, integer-valued strings where dtoa's fast path and
fast_float's Eisel–Lemire path both finish in tens of nanoseconds —
there's not enough work to amortize either parser's setup cost.

For the format side specifically, plain `fmt` regresses on fixed-mode
huge-magnitude inputs because `fmt::detail::format_float` falls into a
Dragon4 + bigint classical loop when the value's decade + requested
precision exceeds the 19-digit Dragonbox first segment; `fmt_opt`
detects that cliff from the binary exponent and routes those cases
through Ryu's `d2fixed`, which is block-based and always fast.

**Parse hooks both `tp_new` and `tp_vectorcall`.** CPython 3.13+'s
specializing interpreter quickens `float(s)` to `CALL_BUILTIN_CLASS`,
which dispatches through `tp_vectorcall` — bypassing `tp_new`. Patching
only `tp_new` would silently leave fast_float disconnected for the
common direct call (`type.__call__(float, s)` would still hit the
hook, but `float(s)` would not). Floatium patches both slots, so the
benchmark numbers above reflect fast_float actually running, not the
stock parser running twice.

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
- Ryu (`d2s` + `d2fixed`, vendored in `third_party/ryu/`): **Apache-2.0
  OR Boost-1.0**.
- `src/format_short.cc` is a port of code from CPython `Python/pystrtod.c`,
  which is under the **PSF License**. The port preserves the original
  attribution and is compatible with downstream MIT redistribution under
  the PSF license's permissive terms.

See `LICENSE` and the per-directory `LICENSE*` files.
