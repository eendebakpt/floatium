# Vendored CPython tests (Track B)

Selected tests copied from CPython's `Lib/test/` directory, adapted for
pytest and used as a fallback to the preferred Track A
(`tools/run_stdlib_tests.py`).

## When this directory gets populated

Today it's empty on purpose: **Track A passes every float-relevant
stdlib test in the current CPython source tree without modification**
(see `../../DIFFERENCES.md`). Vendoring test files ahead of a known
divergence is unneeded duplication.

When a future divergence is discovered:

1. Copy the failing test file from the CPython checkout, e.g.:

    cp ~/cpython/Lib/test/test_float.py \
       tests/cpython_suite/test_float_floatium.py

2. Rename classes/functions where pytest collection clashes with the
   unittest style.

3. Mark the specific divergent case with
   `@pytest.mark.xfail(reason=..., strict=True)` and add an entry to
   DIFFERENCES.md.

4. Update the provenance block at the top of the vendored file:

        # Vendored from CPython Lib/test/test_float.py @ <commit>
        # Upstream: https://github.com/python/cpython/blob/...
        # Adapted: <what you changed and why>

## Why not just always vendor?

Vendoring locks tests to a snapshot. When CPython adds new tests they
won't run against floatium. Track A picks those up automatically. The
only reason to vendor is to freeze a test at a version we've verified
against.
