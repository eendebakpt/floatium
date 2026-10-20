# floatium benchmarks

Nanoseconds per operation for `repr(float)`, fixed-precision f-string
formatting, and `float(str)`, comparing stock CPython against every
floatium format backend (`fmt_opt`, `fmt`, `ryu_opt`, `zmij`) and every parse
backend (`fast_float`, `wuffs`, `ffc`, `stock`).

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
| random_uniform | `repr(x)` | 284.6 | 91.0 | 90.6 | 93.8 | 100.7 | 3.13x | 3.14x | 3.03x | 2.83x |
| random_uniform | `f"{x:.4f}"` | 119.2 | 97.9 | 97.6 | 102.9 | 109.8 | 1.22x | 1.22x | 1.16x | 1.09x |
| random_bits | `repr(x)` | 821.9 | 130.9 | 129.0 | 146.1 | 153.3 | 6.28x | 6.37x | 5.62x | 5.36x |
| random_bits | `f"{x:.4f}"` | 1,936.1 | 193.6 | 5,550.4 | 213.6 | 452.8 | 10.00x | 0.35x | 9.07x | 4.28x |
| financial | `repr(x)` | 169.5 | 73.5 | 73.5 | 99.2 | 89.3 | 2.30x | 2.31x | 1.71x | 1.90x |
| financial | `f"{x:.4f}"` | 143.5 | 95.2 | 96.0 | 114.1 | 114.0 | 1.51x | 1.49x | 1.26x | 1.26x |
| scientific | `repr(x)` | 633.8 | 127.6 | 126.9 | 142.1 | 149.7 | 4.97x | 5.00x | 4.46x | 4.23x |
| scientific | `f"{x:.4f}"` | 1,079.2 | 159.3 | 2,973.1 | 172.2 | 279.4 | 6.77x | 0.36x | 6.27x | 3.86x |
| integer_valued | `repr(x)` | 141.8 | 81.8 | 82.0 | 78.0 | 92.4 | 1.73x | 1.73x | 1.82x | 1.54x |
| integer_valued | `f"{x:.4f}"` | 167.6 | 98.2 | 99.0 | 107.2 | 109.3 | 1.71x | 1.69x | 1.56x | 1.53x |

## Parse backend

`float(s)` over each corpus, `s` being a stock CPython repr. Speedup is
`stock / backend`. `ffc` (ffc.h, the C99 port of fast_float) is the
pure-C parse backend proposed for CPython; it tracks `fast_float`
within noise, while `wuffs` loses on 17-digit inputs (`random_bits`)
where its high-precision-decimal fallback runs.

| Corpus | Operation | Stock (ns) | fast_float | wuffs | ffc | stock | fast_float speedup | wuffs speedup | ffc speedup | stock speedup |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| random_uniform | `float(s)` | 120.8 | 45.6 | 56.2 | 44.2 | 109.3 | 2.65x | 2.15x | 2.73x | 1.11x |
| random_bits | `float(s)` | 276.5 | 58.8 | 293.4 | 59.5 | 212.1 | 4.70x | 0.94x | 4.65x | 1.30x |
| financial | `float(s)` | 36.6 | 37.6 | 39.9 | 37.3 | 79.9 | 0.98x | 0.92x | 0.98x | 0.46x |
| scientific | `float(s)` | 214.3 | 57.1 | 67.3 | 56.9 | 187.7 | 3.75x | 3.18x | 3.77x | 1.14x |
| integer_valued | `float(s)` | 43.0 | 43.4 | 47.9 | 44.1 | 66.4 | 0.99x | 0.90x | 0.98x | 0.65x |
