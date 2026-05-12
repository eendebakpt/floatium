# Internals

Notes on how floatium is wired internally. Not needed for ordinary use;
see the [README](README.md) first.

## Introspection

```python
>>> import floatium
>>> floatium.info()
{'patched': True,
 'format_backend': 'fmt_opt',
 'parse_backend': 'fast_float',
 'available_format_backends': 'fmt,fmt_opt,ryu_opt',
 'available_parse_backends': 'fast_float,wuffs,stock',
 'default_format_backend': 'fmt_opt',
 'default_parse_backend': 'fast_float'}
```

Fields:

- `patched` — whether `install()` is currently active.
- `format_backend` / `parse_backend` — which backend is active now.
- `available_*` — what was compiled into this wheel.
- `default_*` — what `install()` picks if no backend is requested.

`python -m floatium info` prints the same as a quick CLI view, plus
the package version.

## Backend matrix

All format backends produce bit-identical output. Pick one at build
time, or build all of them and switch at install time:

| Format backend       | Algorithm                                                  | C++? |
|----------------------|------------------------------------------------------------|------|
| `fmt_opt` (default)  | `{fmt}` Dragonbox (modes 0/2) + Ryu `d2fixed` (mode 3)     | yes  |
| `fmt`                | `{fmt}` Dragonbox + `fmt::detail::format_float`            | yes  |
| `ryu_opt`            | Ryu `d2s` (mode 0) + `d2exp` (mode 2) + `d2fixed` (mode 3) | **no** |

| Parse backend        | Algorithm                                                  | C++? |
|----------------------|------------------------------------------------------------|------|
| `fast_float` (default) | Eisel–Lemire 64-bit + bignum fallback                    | yes  |
| `wuffs`              | Wuffs `parse_number_f64` — Eisel–Lemire + HPD              | **no** |
| `stock`              | libc `strtod` via floatium's wrapper                       | no   |

For a true stock-CPython baseline on the format side, call
`floatium.uninstall()` — there is no `stock` format backend, because
backends speak the dtoa digit-string contract and stock CPython's
formatter produces a packaged string directly. The parse side does
have a `stock` backend (libc `strtod`) because libc happens to
match the contract.

`ryu_opt` paired with `wuffs` gives fully pure-C operation — zero C++
on either the format or parse path:

```python
import floatium
floatium.install(format_backend="ryu_opt", parse_backend="wuffs")
```

The `ryu_opt` adapter (mode dispatch, FP fast path for `%e`/`%g`,
banker's rounding for `round(x, k)` with negative `k`) is ported from
the [`rye_float`](https://github.com/eendebakpt/cpython/tree/rye_float)
companion CPython branch — the in-tree pure-C demonstrator that drops
`Python/dtoa.c`. The Wuffs parser is ported from the `dtoa_wuff`
companion branch.

## Build options

Backends are CMake-selectable at build time. The defaults match what
the wheel ships (`fmt_opt` + `fast_float`); to build other
combinations:

```bash
# Build only the pure-C path (smaller wheel, no C++ in float I/O):
pip install -e . \
  -C cmake.define.FLOATIUM_FORMAT_BACKEND=ryu_opt \
  -C cmake.define.FLOATIUM_PARSE_BACKEND=wuffs

# Build every backend, switch at install time:
pip install -e . \
  -C cmake.define.FLOATIUM_FORMAT_BACKEND=all \
  -C cmake.define.FLOATIUM_PARSE_BACKEND=all
```

With `all`, every compiled-in backend can be selected at runtime via:

- `FLOATIUM_FORMAT_BACKEND` / `FLOATIUM_PARSE_BACKEND` env vars (read
  by the autopatch hook).
- `floatium.install(format_backend=..., parse_backend=...)` kwargs.

## Format backend routing inside `fmt_opt`

For each `_Py_dg_dtoa` call `fmt_opt` picks per mode:

- **Mode 0 (shortest, drives `repr`)** — fmt's Dragonbox via
  `fmt::detail::dragonbox::to_decimal`.
- **Mode 2 (significant digits, drives `%e`/`%g`)** — fmt's
  `format_float` with `presentation_type::exp`.
- **Mode 3 (digits past decimal, drives `%f`)** — hybrid:
  - If `3 × precision + max(exp2, 0) ≤ 60`, stay on fmt. This keeps
    easy cases (small magnitudes / small precision) on fmt's fast
    subsegment path, which is ~10 ns faster per call than d2fixed for
    those inputs.
  - Otherwise route through Ryu `d2fixed_buffered_n`, which is
    block-based (9 digits per `mulShift_mod1e9` step) and has no cliff.

The `exp2 ≤ 60` boundary mirrors fmt's internal cutoff: fmt falls into
Dragon4 + bigint once the value's decade plus requested precision
exceeds the 19-digit Dragonbox first segment, at which point it is
2–6× slower than stock dtoa. log10(2) ≈ 0.30103 gives
exp2 ≈ 3.32 × decade, hence the integer inequality above.

## Parse hook (dual-slot patching)

`float(s)` is intercepted by swapping **both** `PyFloat_Type.tp_new`
and `PyFloat_Type.tp_vectorcall`. The vectorcall slot is necessary
because CPython 3.13+'s specializing interpreter quickens `float(s)`
to the `CALL_BUILTIN_CLASS` opcode, which dispatches via
`tp_vectorcall` — bypassing `tp_new`. Patching only `tp_new` would
silently miss the common direct call shape; the wrapper handles both.

Both wrappers UTF-8-extract the input, strip ASCII whitespace, reject
underscores / non-ASCII (those fall through to the saved original),
null-terminate into a stack buffer when possible, and call the
backend's `strtod`. Subclasses of `str` and inputs that the backend
can't consume in full also fall through to the saved original tp_new,
which preserves CPython's exact semantics on the edges (`__float__`
dispatch, `inf`/`nan` literals, etc.).

## Vendored libraries

All four libraries are vendored directly from upstream — pinned
versions live in each `third_party/<lib>/README.vendor`:

| Library | Upstream | Resync |
|---|---|---|
| [`{fmt}`](https://github.com/fmtlib/fmt) | `fmtlib/fmt` | `tools/sync_fmt.sh [/path/to/fmt]` |
| [`fast_float`](https://github.com/fastfloat/fast_float) | `fastfloat/fast_float` | `tools/sync_fast_float.sh [/path/to/fast_float]` |
| [`Ryu`](https://github.com/ulfjack/ryu) | `ulfjack/ryu` | `tools/sync_ryu.sh [/path/to/ryu]` |
| [`Wuffs`](https://github.com/google/wuffs) | `google/wuffs` (via the `dtoa_wuff` extract on `eendebakpt/cpython`) | `tools/sync_wuffs.sh [/path/to/cpython0]` |

Each script defaults to `~/<libname>` (Wuffs defaults to `~/cpython0`)
and copies a fixed file set into `third_party/<lib>/`. None of the
vendored files have algorithmic local modifications. Trivial mods:

- Ryu: `#include "ryu/X"` → `#include "X"` (flattened directory).
- Wuffs: vendored as a single-header float-parsing subset of the
  upstream Wuffs release (`floatconv_wuffs.h`); the extraction details
  are in `third_party/wuffs/README.vendor`.

License filenames follow each upstream's convention rather than a
single house style (e.g. fast_float ships `LICENSE-APACHE` uppercase,
Ryu ships `LICENSE-Apache` mixed case). Keeping the upstream casing
makes the bytes copied here trivially comparable to what's on each
project's GitHub.

The C++ adapter shims that bridge these libraries to CPython's
formatting/parsing contracts (`fmt_dtoa.cc`, `fmt_opt_dtoa.cc`,
`fast_float_strtod.cc`, `ryu_opt_dtoa.cc`, `wuffs_strtod.cc`) live in
`src/cpython_adapter/` as floatium-owned code.

## Backend abstraction

The vendored libraries sit behind a narrow C interface
([`src/common/backend.h`](src/common/backend.h)):

```c
struct FloatiumFormatBackend { const char *name; floatium_dtoa_fn dtoa; ... };
struct FloatiumParseBackend  { const char *name; floatium_strtod_fn strtod; };
```

Swapping fmt for Schubfach or double-conversion is a new file in
`src/backends/` plus a corresponding adapter in `src/cpython_adapter/`.
The backend registry resolves names at install-time, so a wheel built
with `all` can switch backends at runtime without rebuilding.
