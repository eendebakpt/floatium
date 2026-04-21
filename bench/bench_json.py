"""End-to-end benchmark: json.dumps of a list of floats.

Closer to real workload than per-call micros: exercises repr via the
json encoder's fast path for floats.
"""

from __future__ import annotations

import json

import pyperf

import floatium
from bench import corpora


def main() -> None:
    runner = pyperf.Runner()
    runner.metadata["description"] = "json.dumps([float, ...]) A/B"

    data = corpora.all_corpora(n=10_000)

    _dumps = json.dumps
    for tag, ctx in [("stock", _ctx_uninstall), ("floatium", _ctx_install)]:
        with ctx():
            for corpus_name, values in data.items():
                name = f"json/{corpus_name}/{tag}"
                runner.bench_func(
                    name, lambda vs=values: _dumps(vs))


class _ctx_install:
    def __enter__(self): floatium.install()
    def __exit__(self, *a): floatium.uninstall()


class _ctx_uninstall:
    def __enter__(self): floatium.uninstall()
    def __exit__(self, *a): pass


if __name__ == "__main__":
    main()
