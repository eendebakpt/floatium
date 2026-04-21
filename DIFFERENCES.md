# Behavioral differences vs. stock CPython

The primary success metric for floatium is that CPython's own regression
tests pass unchanged when run against a patched interpreter (Track A in
the test strategy). This file records every observed divergence so the
PEP discussion has them on the table up front.

## Last verified

- Interpreter: Python 3.15.0a3 (free-threaded debug build)
- floatium commit: initial (v0.1.0.dev0)
- Upstream CPython commit (fmt-fastfloat branch): `46e18aa3d5b`

## Summary: zero divergences

```
$ python tools/run_stdlib_tests.py
== Tests result: SUCCESS ==
All 12 tests OK.
Total tests: run=1,616 skipped=210
```

Default test set:
`test_float`, `test_strtod`, `test_fstring`, `test_format`, `test_complex`,
`test_json`, `test_struct`, `test_string`, `test_decimal`, `test_math`,
`test_cmath`, `test_statistics`.

In addition, the 499-entry byte-identical parity matrix in
`tests/test_parity.py` (repr, str, format across ~50 format specs × 23
curated values) passes 100%.

## Known limitations (not divergences)

These are cases where floatium is **intentionally unable** to intercept
behavior, not cases where it produces different output. Documented here
so they're visible when the PEP case is made.

### 1. `"%g" % x` is not patched

The `%` operator for strings (`printf`-style formatting) calls
`PyOS_double_to_string` directly from `Python/unicodeobject.c:formatfloat`.
That symbol lives inside `libpython` and is not reachable from a
pip-installed extension without `LD_PRELOAD` / symbol interposition.

Impact: `"%g" % 0.1` uses the stock dtoa in a floatium-patched process.
This is a consequence of floatium being a **demo**; the actual PEP would
modify `pystrtod.c` / `PyOS_double_to_string` directly and cover this
path. See the companion CPython `fmt-fastfloat` branch for the in-tree
implementation that covers it.

### 2. `float("1_000.5")` falls through to the original `tp_new`

`fast_float::from_chars` does not handle PEP 515 underscore separators,
so `floatium_float_new` checks for `_` in the input and delegates to the
saved `float_new` when present. Output is bit-identical to stock (we
literally invoke the original), but this path does not benefit from
fast_float's speed. The in-tree CPython implementation strips
underscores before calling fast_float and therefore does benefit.

### 3. `float("inf")`, `float("nan")` fall through

The `fast_float_strtod` wrapper sets `no_infnan` so these literals are
rejected by the parse backend and the original `tp_new` handles them.
This preserves CPython's exact casing rules (`Infinity`, `INF`, `nan`,
etc.) at the cost of a small fast-path miss on these strings. Parity is
identical.

### 4. `float.__format__` with complex specs falls through

`floatium_float_format` handles the common path inline
(`[.precision]{g,G,e,E,f,F}`) and delegates to the original descriptor
for anything with fill/align/width/`#`/`,`/`_`/etc. Output is
bit-identical because the fallback invokes the saved bound method.
Complex specs therefore run at stock speed.

## When you find a new divergence

1. Add a minimal reproducer to `tests/test_parity.py` marked `xfail` with
   the reason.
2. Add an entry to this file's "Known divergences" section (below —
   currently empty).
3. Open an issue against CPython's `fmt-fastfloat` branch if the
   divergence also exists there, or against floatium if it's specific to
   this package's wrappers.

## Known divergences

None as of the last-verified date above.
