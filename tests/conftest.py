"""Shared pytest fixtures for floatium's own test suite.

The ``patched`` fixture installs floatium for the duration of a test and
uninstalls it afterwards. Tests that want to compare against stock CPython
output run a subprocess with FLOATIUM_AUTOPATCH=0 to suppress the
default-on autopatch in the child.
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

    Runs a subprocess with FLOATIUM_AUTOPATCH=0 so the child interpreter
    does NOT autopatch (autopatch defaults to ON since v0.13.0).
    """
    def _stock_repr(expr: str) -> str:
        env = os.environ.copy()
        env["FLOATIUM_AUTOPATCH"] = "0"
        proc = subprocess.run(
            [sys.executable, "-c", f"import sys; sys.stdout.write(repr({expr}))"],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout

    return _stock_repr
