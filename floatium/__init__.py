"""floatium — drop-in replacement for CPython float formatting/parsing.

Backs float repr/str/__format__/__new__ with the {fmt} and fast_float C++
libraries (or a pure-C combination of Ryu + Wuffs) to demonstrate the
performance and correctness case for a forthcoming CPython PEP.

Basic usage:

    import floatium
    floatium.install()          # patch PyFloat_Type slots
    repr(0.1)                   # -> '0.1', same as stock
    floatium.uninstall()        # restore

    with floatium.enabled():            # scoped patching
        ...                             # patched inside the block
    with floatium.enabled(False):       # scoped UN-patching
        ...                             # patched on exit, unpatched here

Autopatch runs at interpreter startup by default. Opt out per-environment
with ``python -m floatium disable`` (writes a marker file in
site-packages), or temporarily with ``FLOATIUM_AUTOPATCH=0``. See
``python -m floatium status`` for the current state.
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
    "enabled",
    "patched",  # deprecated alias for enabled(True)
    "__version__",
]

__version__ = "0.14.0"


def install(
    format_backend: str | None = None,
    parse_backend: str | None = None,
) -> None:
    """Install floatium's replacement slots on PyFloat_Type.

    ``format_backend`` and ``parse_backend`` select which compiled-in
    implementation to use. Pass None to use the build-time defaults.
    Available backends are listed in ``info()``.

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
def enabled(
    active: bool = True,
    format_backend: str | None = None,
    parse_backend: str | None = None,
) -> Iterator[None]:
    """Scoped patching/unpatching, restoring the entry state on exit.

    ``enabled(True)`` (the default) ensures floatium is installed within
    the block and restores the prior state afterward — useful for
    benchmarks or for opting a single hot section into floatium without
    touching global state::

        with floatium.enabled():
            assert repr(0.1) == '0.1'

    ``enabled(False)`` is the inverse: it ensures floatium is NOT
    installed within the block, then restores. Useful for measuring
    stock behavior from a process that has autopatch on, or for handing
    a single hot section to stock CPython::

        with floatium.enabled(False):
            stock_value = float(s)   # stock parser, even with floatium on

    ``format_backend`` / ``parse_backend`` are forwarded to ``install``
    when ``active=True`` and floatium isn't already installed.
    """
    was_patched = is_patched()

    if active and not was_patched:
        install(format_backend=format_backend, parse_backend=parse_backend)
    elif not active and was_patched:
        uninstall()

    try:
        yield
    finally:
        if was_patched and not is_patched():
            install(format_backend=format_backend, parse_backend=parse_backend)
        elif not was_patched and is_patched():
            uninstall()


@contextmanager
def patched(
    format_backend: str | None = None,
    parse_backend: str | None = None,
) -> Iterator[None]:
    """Deprecated alias for ``enabled(True, ...)``. Use ``enabled`` instead."""
    import warnings

    warnings.warn(
        "floatium.patched() is deprecated since v0.13.0; use floatium.enabled() instead.",
        DeprecationWarning,
        stacklevel=3,
    )
    with enabled(True, format_backend=format_backend, parse_backend=parse_backend):
        yield
