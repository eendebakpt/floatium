"""Microbenchmark: format(float, spec).

Format specs chosen to cover the hot paths in format_float_short:
  - ``.2f`` : fixed path, short precision, common in finance / logging.
  - ``.6e`` : exponential path, default for ``%e``.
  - ``g``   : general path with mode-2 / auto-switch.
  - ``.10g``: general path, longer precision.
"""

from __future__ import annotations

import pyperf

import floatium
from bench import corpora

_SPECS = [".2f", ".6e", "g", ".10g"]


def main() -> None:
    runner = pyperf.Runner()
    runner.metadata["description"] = "format(float, spec) A/B"

    data = corpora.all_corpora(n=5_000)

    for tag, ctx in [("stock", _ctx_uninstall), ("floatium", _ctx_install)]:
        with ctx():
            for corpus_name, values in data.items():
                for spec in _SPECS:
                    name = f"format/{corpus_name}/{spec}/{tag}"
                    _format = format
                    runner.bench_func(
                        name,
                        lambda vs=values, s=spec: [_format(x, s) for x in vs],
                    )


# Simple context managers so we don't need two separate functions.
class _ctx_install:
    def __enter__(self): floatium.install()
    def __exit__(self, *a): floatium.uninstall()


class _ctx_uninstall:
    def __enter__(self): floatium.uninstall()
    def __exit__(self, *a): pass


if __name__ == "__main__":
    main()
