"""Per-operation nanosecond benchmark.

Reports one number per (corpus, operation, variant): the median time per
single repr() / f-string interpolation / float(s) parse, in nanoseconds.
Runs many repetitions, picks the median of the fastest third of runs to
reduce noise from jitter.

Operations measured:
    repr(x)
    f"{x:.4f}"
    float(s)    (s = repr of the original value, taken with stock Python
                 so parse timings aren't contaminated by floatium's
                 formatter)

Variants:
    stock       — floatium uninstalled (interpreter's native formatter)
    floatium    — floatium.install() active

Output is tab-separated so it pastes into README tables or spreadsheets.
"""

from __future__ import annotations

import argparse
import statistics
import time
from typing import Callable

import floatium
from bench import corpora


def _time_ns_per_op(fn: Callable[[], None], values: list[float],
                    inner_loops: int, outer_runs: int) -> float:
    """Median ns/op over outer_runs runs, each running the inner kernel
    inner_loops times over the whole corpus."""
    n = len(values)
    samples: list[float] = []
    for _ in range(outer_runs):
        t0 = time.perf_counter_ns()
        for _loop in range(inner_loops):
            fn(values)
        dt = time.perf_counter_ns() - t0
        samples.append(dt / (inner_loops * n))
    # Median of fastest third — robust to background noise without being
    # so aggressive it reports the cold cache outlier.
    samples.sort()
    trimmed = samples[: max(1, outer_runs // 3)]
    return statistics.median(trimmed)


def _repr_kernel(values: list[float]) -> None:
    _repr = repr
    for x in values:
        _repr(x)


def _fmt_4f_kernel(values: list[float]) -> None:
    for x in values:
        f"{x:.4f}"


def _parse_kernel(strings: list[str]) -> None:
    _float = float
    for s in strings:
        _float(s)


FORMAT_OPERATIONS = {
    "repr(x)":        _repr_kernel,
    'f"{x:.4f}"':     _fmt_4f_kernel,
}

PARSE_OPERATIONS = {
    "float(s)":       _parse_kernel,
}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus-size", type=int, default=2000,
                   help="values per corpus (default: 2000)")
    p.add_argument("--inner-loops", type=int, default=5,
                   help="inner kernel loops per sample (default: 5)")
    p.add_argument("--outer-runs", type=int, default=9,
                   help="outer timing samples per cell (default: 9)")
    p.add_argument("--markdown", action="store_true",
                   help="emit a markdown table instead of TSV")
    args = p.parse_args()

    data = corpora.all_corpora(n=args.corpus_size)

    # Stringify with stock Python so parse timings aren't contaminated by
    # floatium's formatter.
    floatium.uninstall()
    str_data = {name: [repr(x) for x in values]
                for name, values in data.items()}

    # Collect numbers: result[corpus][op][variant] = ns/op
    result: dict[str, dict[str, dict[str, float]]] = {}

    for variant, setup in [("stock", floatium.uninstall),
                           ("floatium", floatium.install)]:
        setup()
        for corpus_name, values in data.items():
            for op_name, kernel in FORMAT_OPERATIONS.items():
                kernel(values)  # warmup
                ns = _time_ns_per_op(kernel, values,
                                     args.inner_loops, args.outer_runs)
                result.setdefault(corpus_name, {}) \
                    .setdefault(op_name, {})[variant] = ns
            for op_name, kernel in PARSE_OPERATIONS.items():
                strings = str_data[corpus_name]
                kernel(strings)  # warmup
                ns = _time_ns_per_op(kernel, strings,
                                     args.inner_loops, args.outer_runs)
                result.setdefault(corpus_name, {}) \
                    .setdefault(op_name, {})[variant] = ns

    floatium.uninstall()

    # Emit.
    if args.markdown:
        _emit_markdown(result)
    else:
        _emit_tsv(result)


def _emit_tsv(result: dict) -> None:
    print("corpus\toperation\tstock_ns\tfloatium_ns\tspeedup")
    for corpus, ops in result.items():
        for op, variants in ops.items():
            s, f = variants["stock"], variants["floatium"]
            print(f"{corpus}\t{op}\t{s:.0f}\t{f:.0f}\t{s/f:.2f}x")


def _emit_markdown(result: dict) -> None:
    print("| Corpus | Operation | Stock (ns/op) | floatium (ns/op) | Speedup |")
    print("|---|---|---:|---:|---:|")
    for corpus, ops in result.items():
        for op, variants in ops.items():
            s, f = variants["stock"], variants["floatium"]
            print(f"| {corpus} | `{op}` | {s:,.0f} | {f:,.0f} | "
                  f"{s/f:.2f}× |")


if __name__ == "__main__":
    main()
