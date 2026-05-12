"""CLI for floatium.

  python -m floatium enable    Enable autopatch in this environment (default).
  python -m floatium disable   Disable autopatch in this environment.
  python -m floatium status    Report the current autopatch state.
  python -m floatium info      Show backend / version info.

The enable/disable commands toggle a marker file next to floatium.pth in
site-packages. With no marker and no env-var override, autopatch is ON
(the default since v0.13.0). Set FLOATIUM_AUTOPATCH=0 or run
``python -m floatium disable`` to opt out.
"""

from __future__ import annotations

import argparse
import os
import site
import sys
from pathlib import Path

MARKER_NAME = "floatium-autopatch.disabled"


def _find_pth_dir() -> Path:
    """Return the site-packages directory that contains floatium.pth."""
    # Primary: the parent of the floatium package directory is typically
    # site-packages, and floatium.pth lives there.
    import floatium

    pkg_dir = Path(floatium.__file__).resolve().parent
    candidate = pkg_dir.parent
    if (candidate / "floatium.pth").is_file():
        return candidate

    # Fallback: scan known site-packages locations.
    candidates: list[str] = []
    try:
        candidates.extend(site.getsitepackages())
    except Exception:  # noqa: BLE001
        pass
    try:
        candidates.append(site.getusersitepackages())
    except Exception:  # noqa: BLE001
        pass
    for p in candidates:
        if p and (Path(p) / "floatium.pth").is_file():
            return Path(p)

    # Last resort: the package's parent, even if no .pth was found.
    return candidate


def _marker_path() -> Path:
    return _find_pth_dir() / MARKER_NAME


def _env_override() -> bool | None:
    """Return True/False if FLOATIUM_AUTOPATCH is explicitly set, else None."""
    v = os.environ.get("FLOATIUM_AUTOPATCH")
    if v is None:
        return None
    s = v.strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return None


def cmd_enable(_args: argparse.Namespace) -> int:
    m = _marker_path()
    if m.exists():
        try:
            m.unlink()
        except OSError as e:
            print(
                f"floatium: failed to remove marker at {m}: {e}",
                file=sys.stderr,
            )
            return 1
        print(f"floatium autopatch: enabled (removed {m})")
    else:
        print(f"floatium autopatch: already enabled (no marker at {m})")
    return 0


def cmd_disable(_args: argparse.Namespace) -> int:
    m = _marker_path()
    if m.exists():
        print(f"floatium autopatch: already disabled (marker at {m})")
        return 0
    try:
        m.write_text(
            "# Presence of this file disables floatium autopatch in this\n"
            "# site-packages directory. Created by: python -m floatium disable\n"
            "# Remove via:                          python -m floatium enable\n"
        )
    except OSError as e:
        print(
            f"floatium: failed to write marker at {m}: {e}\n"
            "  (site-packages may be read-only; try a venv or "
            "set FLOATIUM_AUTOPATCH=0 instead)",
            file=sys.stderr,
        )
        return 1
    print(f"floatium autopatch: disabled (created {m})")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    m = _marker_path()
    env = _env_override()
    if env is True:
        active = True
        reason = "FLOATIUM_AUTOPATCH set to truthy value"
    elif env is False:
        active = False
        reason = "FLOATIUM_AUTOPATCH set to falsey value"
    elif m.exists():
        active = False
        reason = f"marker present at {m}"
    else:
        active = True
        reason = "default (no marker, no env-var override)"
    print(
        f"floatium autopatch: {'ENABLED' if active else 'DISABLED'}\n"
        f"  reason:        {reason}\n"
        f"  marker path:   {m}\n"
        f"  marker exists: {m.exists()}\n"
        f"  env override:  {os.environ.get('FLOATIUM_AUTOPATCH', '(unset)')}"
    )
    return 0


def cmd_info(_args: argparse.Namespace) -> int:
    import floatium

    info = floatium.info()
    print(f"floatium version: {floatium.__version__}")
    for k, v in info.items():
        print(f"  {k}: {v}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m floatium",
        description=(
            "Manage floatium autopatch state. With no marker and no env-var "
            "override, autopatch is ENABLED by default."
        ),
    )
    sub = p.add_subparsers(dest="cmd", metavar="{enable,disable,status,info}")
    sub.add_parser("enable", help="Enable autopatch in this environment.").set_defaults(fn=cmd_enable)
    sub.add_parser("disable", help="Disable autopatch in this environment.").set_defaults(fn=cmd_disable)
    sub.add_parser("status", help="Report the current autopatch state.").set_defaults(fn=cmd_status)
    sub.add_parser("info", help="Show backend / version info.").set_defaults(fn=cmd_info)

    args = p.parse_args(argv)
    if not hasattr(args, "fn"):
        p.print_help()
        return 0
    return args.fn(args)
