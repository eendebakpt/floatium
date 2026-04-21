"""Shared pytest fixtures for floatium's own test suite.

The ``patched`` fixture installs floatium for the duration of a test and
uninstalls it afterwards. Tests that want to compare against stock CPython
output run a subprocess without FLOATIUM_AUTOPATCH set to capture a
baseline.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

import floatium


@pytest.fixture
def patched():
    """Install floatium for the duration of one test."""
    floatium.install()
    try:
        yield
    finally:
        floatium.uninstall()


@pytest.fixture(scope="session")
def stock_repr_tool(tmp_path_factory):
    """Return a function that reports stock-CPython repr of a float.

    Runs a subprocess without FLOATIUM_AUTOPATCH so we can compare to what
    the interpreter produces natively.
    """
    def _stock_repr(expr: str) -> str:
        env = os.environ.copy()
        env.pop("FLOATIUM_AUTOPATCH", None)
        # Disable .pth execution via -S is too aggressive (breaks site); instead
        # we rely on FLOATIUM_AUTOPATCH being unset.
        proc = subprocess.run(
            [sys.executable, "-c", f"import sys; sys.stdout.write(repr({expr}))"],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout

    return _stock_repr
