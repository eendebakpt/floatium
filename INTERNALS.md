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
 'available_format_backends': 'fmt_opt',
 'available_parse_backends': 'fast_float',
 'default_format_backend': 'fmt_opt',
 'default_parse_backend': 'fast_float'}
```

Fields:

- `patched` — whether `install()` is currently active.
- `format_backend` / `parse_backend` — which backend is active now.
- `available_*` — what was compiled into this wheel.
- `default_*` — what `install()` picks if no backend is requested.

## Format backends

Registered format backends (all produce output bit-identical to stock
CPython):

| name       | Uses                                          | When |
|------------|-----------------------------------------------|------|
| `fmt_opt`  | fmt Dragonbox + fmt fast subsegment + Ryu d2fixed | default |
| `fmt`      | fmt Dragonbox + fmt `format_float` only       | A/B measurement |
| `stock`    | calls back into `PyOS_double_to_string`       | regression baseline |

`fmt_opt` is the floatium default. For each `_Py_dg_dtoa` call it picks
per mode:

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
2-6× slower than stock dtoa. log10(2) ≈ 0.30103 gives
exp2 ≈ 3.32 × decade, hence the integer inequality above.

## Parse backend

Only `fast_float` is registered on the parse side. `float(str)` is
intercepted by swapping `PyFloat_Type.tp_new`; the wrapper UTF-8
extracts, strips whitespace, rejects underscores / non-ASCII (those
fall through to the original `tp_new`), null-terminates, and calls the
backend's `strtod`.

## Backend abstraction

The vendored libraries sit behind a narrow C interface
([`src/common/backend.h`](src/common/backend.h)):

```c
struct FloatiumFormatBackend { const char *name; floatium_dtoa_fn dtoa; ... };
struct FloatiumParseBackend  { const char *name; floatium_strtod_fn strtod; };
```

Swapping fmt for Ryu shortest or Schubfach is a new file in
`src/backends/`. Swapping `fast_float` for double-conversion is another.
Backends are CMake-selectable at build time
(`-DFLOATIUM_FORMAT_BACKEND=...`, values `fmt_opt`, `fmt`, `stock`,
`all`); when built with `all` every backend is compiled in and the
active one is chosen via the `FLOATIUM_FORMAT_BACKEND` env var at
interpreter startup or the `format_backend=` kwarg to `install()`.
