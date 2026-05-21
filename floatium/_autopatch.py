"""Autopatch hook.

This module is imported by the site-packages/floatium.pth file at
interpreter startup. Default behavior is to install floatium's
replacement slots; opt-out is via:

  * env var: ``FLOATIUM_AUTOPATCH=0`` (or false/no/off)
  * CLI:     ``python -m floatium disable``  (creates a marker file
             ``floatium-autopatch.disabled`` next to floatium.pth)

The env var (when explicitly set) wins over the marker file, so
ad-hoc opt-out works in CI even when the marker is absent. Set
``FLOATIUM_AUTOPATCH_DEBUG=1`` to see install failures during startup.

You can specify backends:

  * ``FLOATIUM_FORMAT_BACKEND=fmt``
  * ``FLOATIUM_PARSE_BACKEND=fast_float``

History: floatium <= 0.12.1 required an explicit ``FLOATIUM_AUTOPATCH=1``
to opt in. v0.13.0 flipped the default to opt-out.
"""

from __future__ import annotations

import os


_MARKER_NAME = "floatium-autopatch.disabled"


def _env_override() -> bool | None:
    """Parse FLOATIUM_AUTOPATCH; return True/False/None (unset or garbage)."""
    v = os.environ.get("FLOATIUM_AUTOPATCH")
    if v is None:
        return None
    s = v.strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return None


def _marker_present() -> bool:
    """True if the disable-marker exists in this install's site-packages."""
    # __file__ is .../site-packages/floatium/_autopatch.py
    # The marker sits next to floatium.pth, which is .../site-packages/
    try:
        sp = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        return os.path.isfile(os.path.join(sp, _MARKER_NAME))
    except Exception:  # noqa: BLE001 — never break startup
        return False


def _should_autopatch() -> bool:
    explicit = _env_override()
    if explicit is not None:
        return explicit
    return not _marker_present()


def _run() -> None:
    if not _should_autopatch():
        return

    # Import lazily so that merely having the .pth on disk doesn't drag the
    # C extension into every Python process — only into ones where autopatch
    # actually fires.
    try:
        from floatium import install
    except ImportError:
        return

    fmt_backend = os.environ.get("FLOATIUM_FORMAT_BACKEND") or None
    parse_backend = os.environ.get("FLOATIUM_PARSE_BACKEND") or None

    try:
        install(format_backend=fmt_backend, parse_backend=parse_backend)
    except Exception:  # noqa: BLE001 — never break interpreter startup
        if os.environ.get("FLOATIUM_AUTOPATCH_DEBUG", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            import traceback

            traceback.print_exc()


_run()
