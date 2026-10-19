# floatium benchmarks

Nanoseconds per operation for `repr(float)`, fixed-precision f-string
formatting, and `float(str)`, comparing stock CPython against every
floatium format backend (`fmt_opt`, `fmt`, `ryu_opt`, `zmij`) and every parse
backend (`fast_float`, `wuffs`, `stock`).

## Methodology

- **floatium:** 0.15.0 (fmt 12.2.0, fast_float v8.3.2), release build,
  all backends compiled in.
- **CPython:** 3.14.3.
- **Date:** 2026-10-19.
- **Script:** `FLOATIUM_AUTOPATCH=0 python -m bench.bench_backend_matrix`.
- **Corpora:** the five canonical corpora from `bench/corpora.py` —
  `random_uniform`, `random_bits`, `financial`, `scientific`,
  `integer_valued`; 2000 values each.
- **Timing:** same as `bench/bench_ns_per_op.py` — 9 outer samples per
  cell, each timing 5 inner loops over the whole corpus; the reported
  figure is the median of the fastest third (3 of 9), robust to
  background jitter without picking the cold-cache outlier.
- **Variants:** `Stock` is the unpatched interpreter. The format-backend
  columns measure `repr` / `f"{x:.4f}"` with each format backend
  installed; the parse-backend columns measure `float(s)` with each
  parse backend installed, over input strings built from stock reprs.
  (In the parse table, the `stock` *column* is floatium's libc-`strtod`
  backend — a real backend — and is distinct from the unpatched `Stock`
  baseline.)

## Format backends

`repr(x)` and `f"{x:.4f}"` over each corpus. Speedup is `stock / backend`;
values above 1.00x are faster than stock. `zmij` is the pure-C
single-library backend proposed for CPython; its `repr` carries a text
re-read of ~10 ns that a to-decimal entry point in Żmij's C API would
remove, and its fixed-precision path on huge magnitudes (`random_bits`)
is bigint-based and ~2x slower than Ryu's `d2fixed`, while still 4x
faster than stock.

| Corpus | Operation | Stock (ns) | fmt_opt | fmt | ryu_opt | zmij | fmt_opt speedup | fmt speedup | ryu_opt speedup | zmij speedup |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random_uniform | `repr(x)` | 284.0 | 90.8 | 89.5 | 91.5 | 102.9 | 3.13x | 3.17x | 3.10x | 2.76x |
| random_uniform | `f"{x:.4f}"` | 119.2 | 100.0 | 100.2 | 104.4 | 109.4 | 1.19x | 1.19x | 1.14x | 1.09x |
| random_bits | `repr(x)` | 819.9 | 131.2 | 128.5 | 143.0 | 154.3 | 6.25x | 6.38x | 5.73x | 5.31x |
| random_bits | `f"{x:.4f}"` | 1,933.7 | 193.2 | 5,539.0 | 211.5 | 452.3 | 10.01x | 0.35x | 9.14x | 4.28x |
| financial | `repr(x)` | 172.5 | 72.4 | 71.9 | 96.6 | 90.6 | 2.38x | 2.40x | 1.78x | 1.90x |
| financial | `f"{x:.4f}"` | 144.6 | 97.1 | 96.0 | 115.9 | 113.8 | 1.49x | 1.51x | 1.25x | 1.27x |
| scientific | `repr(x)` | 635.2 | 127.5 | 127.1 | 139.5 | 150.6 | 4.98x | 5.00x | 4.55x | 4.22x |
| scientific | `f"{x:.4f}"` | 1,078.2 | 158.7 | 2,969.7 | 170.2 | 279.4 | 6.79x | 0.36x | 6.33x | 3.86x |
| integer_valued | `repr(x)` | 142.1 | 83.4 | 81.2 | 78.2 | 94.0 | 1.70x | 1.75x | 1.82x | 1.51x |
| integer_valued | `f"{x:.4f}"` | 167.3 | 99.2 | 101.5 | 108.1 | 108.1 | 1.69x | 1.65x | 1.55x | 1.55x |

## Parse backend

`float(s)` over each corpus, `s` being a stock CPython repr. Speedup is
`stock / backend`.

| Corpus | Operation | Stock (ns) | fast_float | wuffs | stock | fast_float speedup | wuffs speedup | stock speedup |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| random_uniform | `float(s)` | 121.0 | 46.6 | 56.9 | 109.1 | 2.60x | 2.13x | 1.11x |
| random_bits | `float(s)` | 278.5 | 62.7 | 297.5 | 210.4 | 4.44x | 0.94x | 1.32x |
| financial | `float(s)` | 36.7 | 36.6 | 41.6 | 78.5 | 1.00x | 0.88x | 0.47x |
| scientific | `float(s)` | 212.5 | 57.1 | 68.0 | 186.2 | 3.72x | 3.13x | 1.14x |
| integer_valued | `float(s)` | 43.0 | 42.8 | 47.6 | 68.0 | 1.01x | 0.90x | 0.63x |
