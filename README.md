# floatium

Experimental drop-in replacement for CPython's float formatting and parsing,
backed by the [{fmt}](https://github.com/fmtlib/fmt) and
[fast_float](https://github.com/fastfloat/fast_float) C++ libraries.

`pip install floatium`, set `FLOATIUM_AUTOPATCH=1`, and every subsequent
Python process uses `{fmt}`'s Dragonbox for `repr(float)` / `str(float)` /
`float.__format__` and `fast_float` for `float("...")`. Existing code,
existing tests, existing output — just faster.

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
pip install -e .
```

No system libraries are required; `{fmt}` and `fast_float` are vendored.

## Why this package exists

CPython's float formatting has gone through
[`Python/dtoa.c`](https://github.com/python/cpython/blob/main/Python/dtoa.c)
— David Gay's 1991 reference implementation — for three decades. The
code is ~2,800 lines of hand-tuned C and slower than modern alternatives.
Its parsing counterpart (`_Py_dg_strtod` in the same file) has similar
constraints.

Floatium demonstrates what replacing both sides looks like:

- **Format** (double → string) via `{fmt}`'s Dragonbox algorithm — the
  same algorithm that backs C++20's `std::format`.
- **Parse** (string → double) via `fast_float`'s Eisel–Lemire + bignum
  path — the same algorithm Rust's `std`, Apache Arrow, and DuckDB use.

Both produce output **bit-identical** to stock CPython on every input
we've tested (see [DIFFERENCES.md](DIFFERENCES.md) — currently zero
divergences against CPython 3.15's stdlib test suite).

## Why `{fmt}`

- **Modern, actively maintained, permissive license** (MIT). Upstream
  releases every few months; C++20 `std::format` is a direct descendant.
- **Dragonbox shortest round-trip**, proven correct across IEEE 754
  doubles, typically faster than Ryu on common inputs.
- **Single source of grammar + formatters + fallbacks**, minimizing the
  surface area an upstream audit would need to cover.
- **Header-only mode** vendored trivially (4 headers, ~9,400 LOC).

**Other libraries could work equally well** — Ryu, Schubfach, Grisu3,
double-conversion. `{fmt}` is floatium's default because swapping it out
is a single edit (see the `FLOATIUM_FORMAT_BACKEND` CMake option and
`src/backend.h`) and because bundling the whole formatter+grammar in one
upstream means downstream doesn't need to wire three separate vendored
components.

## Why `fast_float`

- **Header-only, C++11, trivially vendorable** (9 headers, ~4,000 LOC).
  Smaller than double-conversion (~10k LOC).
- **Battle-tested** in Chromium, Apache Arrow, ClickHouse, folly, DuckDB.
- **Triple license** (Apache-2.0 OR MIT OR Boost-1.0), maximally
  compatible with CPython's PSF license.
- **Exhaustively validated** against strtod reference on every IEEE 754
  halfway case.

**Other parsers could work** — double-conversion from Google,
`absl::from_chars`, or rolling the minimum Eisel–Lemire ourselves.
`fast_float` was chosen for the smallest vendoring footprint and the
cleanest license for redistribution.

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

### Introspection

```python
>>> floatium.info()
{'patched': True,
 'format_backend': 'fmt',
 'parse_backend': 'fast_float',
 'available_format_backends': 'fmt,stock',
 'available_parse_backends': 'fast_float,stock',
 'default_format_backend': 'fmt',
 'default_parse_backend': 'fast_float'}
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

Indicative numbers on Python 3.15 free-threaded debug build
(`python -m bench.bench_ns_per_op`, median of fastest third of samples,
lower is better):

| Corpus          | Operation       | Stock (ns/op) | floatium (ns/op) | Speedup |
|-----------------|-----------------|--------------:|-----------------:|--------:|
| random_uniform  | `repr(x)`       |         2,997 |              473 |   6.33× |
| random_uniform  | `f"{x:.4f}"`    |           716 |              556 |   1.29× |
| random_bits     | `repr(x)`       |         3,962 |              540 |   7.34× |
| random_bits     | `f"{x:.4f}"`    |         3,712 |            6,052 |   0.61× |
| financial       | `repr(x)`       |         1,919 |              457 |   4.20× |
| financial       | `f"{x:.4f}"`    |           738 |              554 |   1.33× |
| scientific      | `repr(x)`       |         3,731 |              535 |   6.97× |
| scientific      | `f"{x:.4f}"`    |         2,498 |            3,477 |   0.72× |
| integer_valued  | `repr(x)`       |           632 |              475 |   1.33× |
| integer_valued  | `f"{x:.4f}"`    |           777 |              564 |   1.38× |
| famous          | `repr(x)`       |         2,547 |              485 |   5.25× |
| famous          | `f"{x:.4f}"`    |         1,652 |            2,160 |   0.76× |

Debug builds inflate absolute numbers; the A/B ratio is stable across
release builds.

**Known regression on the `f`/`F` path for huge-magnitude values.**
`fmt::detail::format_float` in fixed mode is ~2× slower than stock
dtoa.c when asked to emit 300+ digits (e.g. `f"{1.7e308:.4f}"`).
Crossover at roughly |d| ≥ 1e50. The regression shows up on the
`random_bits`, `scientific`, and `famous` corpora because they include
such values. **We deliberately do not work around this by delegating
back to stock dtoa** — the end goal is to retire dtoa, and any demo
that keeps it on a code path would be arguing against that. The real
fix lives in `fmt` itself (fixed-mode bignum generation) and is the
same fix the in-tree CPython change would need.

## Backend abstraction

The vendored libraries sit behind a narrow C interface
([`src/common/backend.h`](src/common/backend.h)):

```c
struct FloatiumFormatBackend { const char *name; floatium_dtoa_fn dtoa; ... };
struct FloatiumParseBackend  { const char *name; floatium_strtod_fn strtod; };
```

Swapping `{fmt}` for Dragonbox, Ryu, or Schubfach is a single file in
`src/backends/`. Swapping `fast_float` for double-conversion is another.
Both are CMake-selectable at build time
(`-DFLOATIUM_FORMAT_BACKEND=...`); when built with `-DFLOATIUM_FORMAT_BACKEND=all`
the backend is chosen by the `FLOATIUM_FORMAT_BACKEND` env var at
interpreter startup.

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
- `src/format_short.cc` is a port of code from CPython `Python/pystrtod.c`,
  which is under the **PSF License**. The port preserves the original
  attribution and is compatible with downstream MIT redistribution under
  the PSF license's permissive terms.

See `LICENSE` and the per-directory `LICENSE*` files.

## Status

Pre-alpha. v0.1.x — the API will stay small (the four functions in
`floatium/__init__.py`) but the internals will change.
