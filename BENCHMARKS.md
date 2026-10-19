# floatium benchmarks

Nanoseconds per operation for `repr(float)`, fixed-precision f-string
formatting, and `float(str)`, comparing stock CPython against every
floatium format backend (`fmt_opt`, `fmt`, `ryu_opt`) and every parse
backend (`fast_float`, `wuffs`, `stock`).

## Methodology

- **floatium:** 0.14.5 + branch `py315-fixes-revendor` (fmt 12.2.0,
  fast_float v8.3.2), release build, all backends compiled in.
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
values above 1.00x are faster than stock.

| Corpus | Operation | Stock (ns) | fmt_opt | fmt | ryu_opt | fmt_opt speedup | fmt speedup | ryu_opt speedup |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| random_uniform | `repr(x)` | 284.7 | 92.2 | 91.6 | 95.4 | 3.09x | 3.11x | 2.98x |
| random_uniform | `f"{x:.4f}"` | 119.9 | 99.9 | 100.7 | 105.6 | 1.20x | 1.19x | 1.14x |
| random_bits | `repr(x)` | 821.6 | 130.1 | 129.9 | 142.4 | 6.31x | 6.32x | 5.77x |
| random_bits | `f"{x:.4f}"` | 1,933.9 | 196.8 | 5,532.8 | 215.1 | 9.83x | 0.35x | 8.99x |
| financial | `repr(x)` | 171.0 | 75.0 | 73.8 | 101.2 | 2.28x | 2.32x | 1.69x |
| financial | `f"{x:.4f}"` | 144.7 | 96.5 | 98.1 | 114.4 | 1.50x | 1.47x | 1.27x |
| scientific | `repr(x)` | 638.4 | 127.2 | 127.3 | 138.5 | 5.02x | 5.02x | 4.61x |
| scientific | `f"{x:.4f}"` | 1,078.7 | 161.4 | 2,969.0 | 173.4 | 6.68x | 0.36x | 6.22x |
| integer_valued | `repr(x)` | 142.8 | 84.1 | 83.3 | 78.8 | 1.70x | 1.71x | 1.81x |
| integer_valued | `f"{x:.4f}"` | 167.9 | 102.2 | 101.7 | 107.4 | 1.64x | 1.65x | 1.56x |

## Parse backend

`float(s)` over each corpus, `s` being a stock CPython repr. Speedup is
`stock / backend`.

| Corpus | Operation | Stock (ns) | fast_float | wuffs | stock | fast_float speedup | wuffs speedup | stock speedup |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| random_uniform | `float(s)` | 125.6 | 46.0 | 57.0 | 108.5 | 2.73x | 2.20x | 1.16x |
| random_bits | `float(s)` | 276.3 | 66.8 | 300.9 | 210.8 | 4.14x | 0.92x | 1.31x |
| financial | `float(s)` | 36.8 | 37.6 | 41.9 | 78.5 | 0.98x | 0.88x | 0.47x |
| scientific | `float(s)` | 213.6 | 63.8 | 74.1 | 185.4 | 3.35x | 2.88x | 1.15x |
| integer_valued | `float(s)` | 43.2 | 44.0 | 47.5 | 69.1 | 0.98x | 0.91x | 0.63x |
