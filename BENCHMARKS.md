# floatium benchmarks

Nanoseconds per operation for `repr(float)`, fixed-precision f-string
formatting, and `float(str)`, comparing stock CPython against every
floatium format backend (`fmt_opt`, `fmt`, `ryu_opt`) and every parse
backend (`fast_float`, `wuffs`, `stock`).

## Methodology

- **floatium:** 0.14.2, release build, all backends compiled in.
- **CPython:** 3.14.3.
- **Machine:** 13th Gen Intel Core i7-13650HX, Linux.
- **Date:** 2026-05-16.
- **Corpora:** the five canonical corpora from `bench/corpora.py` —
  `random_uniform`, `random_bits`, `financial`, `scientific`,
  `integer_valued`; 2000 values each.
- **Timing:** mirrors `bench/bench_ns_per_op.py` — 9 outer samples per
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
| random_uniform | `repr(x)` | 285.3 | 97.9 | 98.3 | 96.4 | 2.92x | 2.90x | 2.96x |
| random_uniform | `f"{x:.4f}"` | 119.2 | 103.4 | 103.5 | 104.8 | 1.15x | 1.15x | 1.14x |
| random_bits | `repr(x)` | 819.6 | 135.5 | 135.2 | 146.1 | 6.05x | 6.06x | 5.61x |
| random_bits | `f"{x:.4f}"` | 1,956.3 | 193.9 | 5,549.3 | 212.2 | 10.09x | 0.35x | 9.22x |
| financial | `repr(x)` | 172.0 | 80.7 | 79.6 | 101.6 | 2.13x | 2.16x | 1.69x |
| financial | `f"{x:.4f}"` | 144.5 | 100.5 | 100.1 | 115.1 | 1.44x | 1.44x | 1.25x |
| scientific | `repr(x)` | 639.8 | 133.6 | 132.7 | 141.0 | 4.79x | 4.82x | 4.54x |
| scientific | `f"{x:.4f}"` | 1,078.6 | 158.1 | 2,972.4 | 170.7 | 6.82x | 0.36x | 6.32x |
| integer_valued | `repr(x)` | 143.1 | 88.7 | 88.2 | 80.7 | 1.61x | 1.62x | 1.77x |
| integer_valued | `f"{x:.4f}"` | 168.0 | 104.8 | 104.5 | 107.6 | 1.60x | 1.61x | 1.56x |

## Parse backend

`float(s)` over each corpus, `s` being a stock CPython repr. Speedup is
`stock / backend`.

| Corpus | Operation | Stock (ns) | fast_float | wuffs | stock | fast_float speedup | wuffs speedup | stock speedup |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| random_uniform | `float(s)` | 121.4 | 43.9 | 55.6 | 106.3 | 2.76x | 2.18x | 1.14x |
| random_bits | `float(s)` | 277.6 | 59.1 | 293.4 | 208.7 | 4.70x | 0.95x | 1.33x |
| financial | `float(s)` | 36.8 | 37.0 | 39.8 | 78.0 | 0.99x | 0.92x | 0.47x |
| scientific | `float(s)` | 213.7 | 57.4 | 66.5 | 183.3 | 3.72x | 3.21x | 1.17x |
| integer_valued | `float(s)` | 42.8 | 42.0 | 46.6 | 64.1 | 1.02x | 0.92x | 0.67x |
