"""floatium — drop-in replacement for CPython float formatting/parsing.

Backs float repr/str/__format__/__new__ with the {fmt} and fast_float C++
libraries to demonstrate the performance and correctness case for a
forthcoming CPython PEP.

Basic usage:

    import floatium
    floatium.install()          # patch PyFloat_Type slots
    repr(0.1)                   # -> '0.1', same as stock
    floatium.uninstall()        # restore

    with floatium.patched():
        ...                     # patched inside the block

Autopatch on interpreter startup: set FLOATIUM_AUTOPATCH=1. See README.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from floatium import _ext

__all__ = [
    "install",
    "uninstall",
    "is_patched",
    "info",
    "patched",
    "__version__",
]

__version__ = "0.1.0.dev0"


def install(
    format_backend: str | None = None,
    parse_backend: str | None = None,
) -> None:
    """Install floatium's replacement slots on PyFloat_Type.

    ``format_backend`` and ``parse_backend`` select which compiled-in
    implementation to use. Pass None to use the build-time defaults
    (typically ``"fmt"`` and ``"fast_float"``). See ``info()`` for
    which backends are available in this wheel.

    Idempotent: calling install() twice is a no-op on the second call.
    """
    kwargs = {}
    if format_backend is not None:
        kwargs["format_backend"] = format_backend
    if parse_backend is not None:
        kwargs["parse_backend"] = parse_backend
    _ext.install(**kwargs)


def uninstall() -> None:
    """Restore the original PyFloat_Type slots."""
    _ext.uninstall()


def is_patched() -> bool:
    """Return True if floatium is currently installed."""
    return bool(_ext.is_patched())


def info() -> dict:
    """Return a dict describing the current state and available backends."""
    return _ext.info()


@contextmanager
def patched(
    format_backend: str | None = None,
    parse_backend: str | None = None,
) -> Iterator[None]:
    """Context manager that installs on entry and restores on exit.

    Useful for A/B benchmarking or scoped testing::

        with floatium.patched():
            assert repr(0.1) == '0.1'
    """
    was_patched = is_patched()
    if not was_patched:
        install(format_backend=format_backend, parse_backend=parse_backend)
    try:
        yield
    finally:
        if not was_patched:
            uninstall()
