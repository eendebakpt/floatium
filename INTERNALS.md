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

## Library provenance

- `{fmt}` (`third_party/fmt/`, ~9.4k LOC vendored) — MIT, header-only.
  Ships Dragonbox + the format grammar + fallbacks in one upstream.
- `fast_float` (`third_party/fast_float/`) — Apache-2.0 / MIT / Boost-1.0
  triple-licensed, header-only, C++11. Used in Chromium, Apache Arrow,
  ClickHouse, folly, DuckDB.
- Ryu `d2fixed` (`third_party/ryu/`) — Apache-2.0 / Boost-1.0
  dual-licensed. Only the `d2fixed` entry point is vendored
  (~100 KB of pow10 tables); the shortest-format code paths are
  redundant with fmt's Dragonbox.

All three are redistribution-compatible with floatium's MIT license.

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

Two parse backends are registered: `fast_float` (default) and `stock`
(libc `strtod`, mainly for A/B comparison). `float(str)` is intercepted
by swapping **both** `PyFloat_Type.tp_new` and
`PyFloat_Type.tp_vectorcall`. The vectorcall slot is necessary because
CPython 3.13+'s specializing interpreter quickens `float(s)` to the
`CALL_BUILTIN_CLASS` opcode, which dispatches via `tp_vectorcall` —
bypassing `tp_new`. Patching only `tp_new` would silently miss the
common direct call shape; the wrapper handles both. Both wrappers UTF-8
extract, strip whitespace, reject underscores / non-ASCII (those fall
through to the saved original), null-terminate, and call the backend's
`strtod`.

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
