"""Microbenchmark: repr(float).

We run each corpus twice — once with floatium installed, once without —
so a single invocation produces an A/B table. pyperf handles the
outer rigging (warmup, loops, variance, JSON output).
"""

from __future__ import annotations

import pyperf

import floatium
from bench import corpora


def bench_repr(runner: pyperf.Runner, corpus_name: str, values: list[float],
               patched_suffix: str) -> None:
    name = f"repr/{corpus_name}/{patched_suffix}"
    # Bind locals to avoid attribute lookup noise in the timed loop.
    _repr = repr
    runner.bench_func(name, lambda vs=values: [_repr(x) for x in vs])


def main() -> None:
    runner = pyperf.Runner()
    runner.metadata["description"] = "repr(float) A/B"

    data = corpora.all_corpora(n=5_000)

    # Stock first, then patched, to surface the A/B impact cleanly.
    floatium.uninstall()
    for name, values in data.items():
        bench_repr(runner, name, values, "stock")

    floatium.install()
    for name, values in data.items():
        bench_repr(runner, name, values, "floatium")
    floatium.uninstall()


if __name__ == "__main__":
    main()
