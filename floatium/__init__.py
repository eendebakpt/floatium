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

__version__ = "0.14.4"


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


class enabled:
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

    __slots__ = ("_active", "_format_backend", "_parse_backend", "_was_patched")

    def __init__(
        self,
        active: bool = True,
        format_backend: str | None = None,
        parse_backend: str | None = None,
    ) -> None:
        self._active = active
        self._format_backend = format_backend
        self._parse_backend = parse_backend
        self._was_patched = False

    def __enter__(self) -> None:
        self._was_patched = is_patched()
        if self._active and not self._was_patched:
            install(format_backend=self._format_backend, parse_backend=self._parse_backend)
        elif not self._active and self._was_patched:
            uninstall()
        return None

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._was_patched and not is_patched():
            install(format_backend=self._format_backend, parse_backend=self._parse_backend)
        elif not self._was_patched and is_patched():
            uninstall()
        return None


class patched(enabled):
    """Deprecated alias for ``enabled(True, ...)``. Use ``enabled`` instead."""

    def __init__(
        self,
        format_backend: str | None = None,
        parse_backend: str | None = None,
    ) -> None:
        import warnings

        warnings.warn(
            "floatium.patched() is deprecated since v0.13.0; use floatium.enabled() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(True, format_backend=format_backend, parse_backend=parse_backend)
