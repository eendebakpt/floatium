"""Track B: copium-style vendored CPython test fixtures.

Track A (tools/run_stdlib_tests.py) is the preferred verification path —
it runs the actual unmodified stdlib tests against a patched interpreter.
Track B lives here as a fallback for two scenarios:

  1. A stdlib test drags in machinery that doesn't work under
     FLOATIUM_AUTOPATCH (e.g., something that re-imports float and expects
     the original slot pointers). A vendored copy can pin a known-good
     subset of the tests.

  2. floatium intentionally diverges from stock (none today; see
     DIFFERENCES.md). Vendored tests can encode the intentional
     divergence with explicit xfail markers.

This conftest installs floatium for every test in this directory.
"""

from __future__ import annotations

import pytest

import floatium


@pytest.fixture(autouse=True, scope="session")
def _floatium_installed_for_vendored_tests():
    floatium.install()
    yield
    floatium.uninstall()
