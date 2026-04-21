"""Autopatch hook.

This module is imported by the site-packages/floatium.pth file at
interpreter startup. It inspects FLOATIUM_AUTOPATCH and installs the
replacement slots if set.

Rationale for gating on an env var rather than patching unconditionally:
the .pth file mechanism affects *every* Python invocation that shares
this site-packages directory, including tools that should not be
affected (the build system, linters, etc.). Opt-in is safer for
a process-global mutation.

Values that trigger install:
    FLOATIUM_AUTOPATCH=1
    FLOATIUM_AUTOPATCH=true
    FLOATIUM_AUTOPATCH=yes

You can also specify backends:
    FLOATIUM_FORMAT_BACKEND=fmt
    FLOATIUM_PARSE_BACKEND=fast_float
"""

from __future__ import annotations

import os


def _truthy(v: str | None) -> bool:
    if v is None:
        return False
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _run() -> None:
    if not _truthy(os.environ.get("FLOATIUM_AUTOPATCH")):
        return

    # Import lazily so that merely having the .pth on disk doesn't drag the
    # C extension into every Python process — only into ones that opt in.
    try:
        from floatium import install
    except ImportError:
        return

    fmt_backend = os.environ.get("FLOATIUM_FORMAT_BACKEND") or None
    parse_backend = os.environ.get("FLOATIUM_PARSE_BACKEND") or None

    try:
        install(format_backend=fmt_backend, parse_backend=parse_backend)
    except Exception:  # noqa: BLE001 — never break interpreter startup
        if _truthy(os.environ.get("FLOATIUM_AUTOPATCH_DEBUG")):
            import traceback

            traceback.print_exc()


_run()
