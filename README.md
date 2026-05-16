# floatium

[![PyPI](https://img.shields.io/pypi/v/floatium.svg)](https://pypi.org/project/floatium/)
[![Python versions](https://img.shields.io/pypi/pyversions/floatium.svg)](https://pypi.org/project/floatium/)
[![License](https://img.shields.io/pypi/l/floatium.svg)](https://github.com/eendebakpt/floatium/blob/main/LICENSE)

Experimental drop-in replacement for CPython's float formatting and parsing,
backed by the [{fmt}](https://github.com/fmtlib/fmt) and
[fast_float](https://github.com/fastfloat/fast_float) C++ libraries.

After `pip install floatium`, every subsequent Python process uses
`{fmt}`'s Dragonbox for `repr(float)` / `str(float)` /
`float.__format__` and `fast_float` for `float("...")`. Existing code,
existing tests, existing output — just faster. Works with an unmodified
stock CPython; no interpreter rebuild required.

## Installation

```bash
pip install floatium
```

Source builds require a C++17 compiler (GCC 9+, Clang 12+, or MSVC
2019+) and CMake ≥ 3.20:

```bash
git clone https://github.com/eendebakpt/floatium
cd floatium
pip install -e '.[test]'
```

No system libraries are required; `{fmt}`, `fast_float`, Ryu, and
Wuffs are all vendored. See [INTERNALS.md](INTERNALS.md) for the build
options and backend matrix.

## Why this package exists

CPython's float formatting has gone through
[`Python/dtoa.c`](https://github.com/python/cpython/blob/main/Python/dtoa.c)
— David Gay's 1991 reference implementation — for three decades. The
code is ~2,800 lines of hand-tuned C and slower than modern alternatives.
Its parsing counterpart (`_Py_dg_strtod` in the same file) has similar
constraints.

Floatium demonstrates what replacing both sides looks like, as a pip
package against stock CPython. Output is **bit-identical** to stock on
every input we've tested (see [PARITY.md](PARITY.md) — currently zero
divergences against CPython 3.15's stdlib test suite).

## Benchmarks

Numbers below are from a release CPython 3.14.3 build
(`python -m bench.bench_ns_per_op`, median of fastest third of samples,
lower is better) using floatium's default `fmt_opt` format backend +
`fast_float` parse backend:

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

The table above is the default configuration. For the full
per-backend matrix — `fmt_opt` / `fmt` / `ryu_opt` formatting and
`fast_float` / `wuffs` / `stock` parsing — see
[BENCHMARKS.md](BENCHMARKS.md).

Run locally with:

```bash
python -m bench.bench_ns_per_op --markdown        # quick ns/op table
bench/run_all.sh                                  # full pyperf sweep
```

## Usage

### Autopatch (default)

Once `floatium` is installed, every Python process automatically uses
the replacement at startup — no env var, no import needed in your code:

```bash
python -c "import json; print(json.dumps([0.1, 0.2, 1e100]))"
# [0.1, 0.2, 1e+100]
```

The mechanism is a `.pth` file placed in `site-packages/` at install
time. `site.py` executes it during interpreter startup, before user
code, and the hook calls `install()` unless you've opted out.

**Disable autopatch** in this environment with the CLI:

```bash
python -m floatium disable    # writes a marker file in site-packages
python -m floatium enable     # remove the marker (the default state)
python -m floatium status     # show whether autopatch is on
```

For temporary or per-process opt-out, set `FLOATIUM_AUTOPATCH=0` in the
environment. It wins over the marker file and is the right knob for
CI, tooling, and ad-hoc subprocesses.

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

with floatium.enabled():            # ensure patched in the block
    do_something_float_heavy()

with floatium.enabled(False):       # ensure UN-patched in the block
    stock_value = float(s)          # measured against stock CPython
```

`enabled(True)` (the default) installs floatium for the block and
restores the entry state on exit. `enabled(False)` is the inverse: it
unpatches for the block, useful when autopatch is on globally but you
want to hand a single hot section to stock CPython.

## What it patches

| Surface                             | How                                           |
|-------------------------------------|-----------------------------------------------|
| `repr(x)`, `str(x)`, `f"{x}"`       | `PyFloat_Type.tp_repr` pointer swap            |
| `f"{x:.2f}"`, `format(x, spec)`     | `__format__` entry in `PyFloat_Type.tp_dict`   |
| `"{}".format(x)`                    | via `__format__`                              |
| `float("1.5")`                      | `PyFloat_Type.tp_new` + `tp_vectorcall` swap   |
| `json.dumps([x])`                   | via `__repr__`                                |

`"%g" % x` is **not** patched — see [PARITY.md](PARITY.md).

For the full backend matrix (which format backend / parse backend
combinations are available and how to A/B them), see
[INTERNALS.md](INTERNALS.md).

## Running CPython's test suite against floatium

`tools/run_stdlib_tests.py` runs a curated set of CPython's own stdlib
regression tests with floatium autopatched. Zero divergences on the
default set as of the last update; see [PARITY.md](PARITY.md) for the
current status.

```bash
python tools/run_stdlib_tests.py
# ==> running: python -m test test_float test_strtod test_fstring ...
# == Tests result: SUCCESS ==
# All 12 tests OK.
```

## Limitations

See [PARITY.md](PARITY.md) for the full list. Summary:

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
- Ryu (vendored in `third_party/ryu/`): **Apache-2.0 OR Boost-1.0**.
- Wuffs (vendored in `third_party/wuffs/`): **Apache-2.0 OR MIT**.
- `src/format_short.cc` is a port of code from CPython `Python/pystrtod.c`,
  which is under the **PSF License**. The port preserves the original
  attribution and is compatible with downstream MIT redistribution under
  the PSF license's permissive terms.
- Name and vectorcall patching inspired by [copium](https://github.com/percolab/copium) (MIT).

See `LICENSE` and the per-directory `LICENSE*` files.
