"""Microbenchmark: float(str).

Parse corpora are derived from the formatted output of the numeric
corpora — this models the realistic "write-then-read" pipeline seen in
JSON, CSV, and config-file workflows.
"""

from __future__ import annotations

import pyperf

import floatium
from bench import corpora


def _stringify(values: list[float]) -> list[str]:
    # Deliberately use stock repr so parse benches aren't contaminated by
    # floatium's formatting perf — we want to measure parse alone.
    floatium.uninstall()
    return [repr(v) for v in values]


def main() -> None:
    runner = pyperf.Runner()
    runner.metadata["description"] = "float(str) A/B"

    data = corpora.all_corpora(n=5_000)
    str_data = {name: _stringify(values) for name, values in data.items()}

    _float = float
    for tag, ctx in [("stock", _ctx_uninstall), ("floatium", _ctx_install)]:
        with ctx():
            for corpus_name, strings in str_data.items():
                name = f"parse/{corpus_name}/{tag}"
                runner.bench_func(
                    name, lambda ss=strings: [_float(s) for s in ss])


class _ctx_install:
    def __enter__(self): floatium.install()
    def __exit__(self, *a): floatium.uninstall()


class _ctx_uninstall:
    def __enter__(self): floatium.uninstall()
    def __exit__(self, *a): pass


if __name__ == "__main__":
    main()
