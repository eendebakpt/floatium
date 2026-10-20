"""Per-backend ns/op matrix — the tables in BENCHMARKS.md.

Same kernels, corpora and timing method as bench_ns_per_op.py, but every
compiled-in format backend (repr / f"{x:.4f}") and parse backend
(float(s)) is measured in turn against the unpatched interpreter.
Needs a build with all backends compiled in:

    pip install . -C cmake.define.FLOATIUM_FORMAT_BACKEND=all \\
                  -C cmake.define.FLOATIUM_PARSE_BACKEND=all
    FLOATIUM_AUTOPATCH=0 python -m bench.bench_backend_matrix
"""

from __future__ import annotations

import argparse

import floatium
from bench import corpora
from bench.bench_ns_per_op import FORMAT_OPERATIONS, PARSE_OPERATIONS, _time_ns_per_op


def _table(rows: dict, names: list[str]) -> None:
    print("| Corpus | Operation | Stock (ns) | " + " | ".join(names) + " | "
          + " | ".join(f"{n} speedup" for n in names) + " |")
    print("|---|---|---:|" + "---:|" * (2 * len(names)))
    for (corpus, op), r in rows.items():
        stock = r["Stock"]
        print(f"| {corpus} | `{op}` | {stock:,.1f} | "
              + " | ".join(f"{r[n]:,.1f}" for n in names) + " | "
              + " | ".join(f"{stock / r[n]:.2f}x" for n in names) + " |")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus-size", type=int, default=2000)
    p.add_argument("--inner-loops", type=int, default=5)
    p.add_argument("--outer-runs", type=int, default=9)
    args = p.parse_args()

    def measure(kernel, values):
        kernel(values)  # warmup
        return _time_ns_per_op(kernel, values, args.inner_loops, args.outer_runs)

    data = corpora.all_corpora(n=args.corpus_size)
    floatium.uninstall()
    str_data = {name: [repr(x) for x in values] for name, values in data.items()}
    info = floatium.info()
    format_backends = info["available_format_backends"].split(",")
    parse_backends = info["available_parse_backends"].split(",")

    fmt_rows: dict = {}
    parse_rows: dict = {}
    for corpus, values in data.items():
        for op, kernel in FORMAT_OPERATIONS.items():
            fmt_rows[(corpus, op)] = {"Stock": measure(kernel, values)}
        for op, kernel in PARSE_OPERATIONS.items():
            parse_rows[(corpus, op)] = {"Stock": measure(kernel, str_data[corpus])}
    for backend in format_backends:
        floatium.uninstall()
        floatium.install(format_backend=backend)
        for corpus, values in data.items():
            for op, kernel in FORMAT_OPERATIONS.items():
                fmt_rows[(corpus, op)][backend] = measure(kernel, values)
    for backend in parse_backends:
        floatium.uninstall()
        floatium.install(parse_backend=backend)
        for corpus, _values in data.items():
            for op, kernel in PARSE_OPERATIONS.items():
                parse_rows[(corpus, op)][backend] = measure(kernel, str_data[corpus])
    floatium.uninstall()

    print("## Format backends\n")
    _table(fmt_rows, format_backends)
    print("\n## Parse backend\n")
    _table(parse_rows, parse_backends)


if __name__ == "__main__":
    main()
