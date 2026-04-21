"""Run CPython's own stdlib regression tests against a floatium-patched
interpreter (Track A of the CPython test strategy).

Mechanism:
  * floatium's .pth file is installed at site-packages root.
  * Setting FLOATIUM_AUTOPATCH=1 causes _autopatch.py to call install()
    before the first user line of code runs (site.py processes .pth files
    early in startup).
  * `python -m test <test_name>` then runs the unmodified regrtest harness
    against PyFloat_Type with our replacement slots in place.

If a test fails, that is a real divergence from stock CPython behavior.
We capture failures here rather than papering over them — they go into
DIFFERENCES.md so the PEP discussion has them up front.

Default test set: everything with meaningful float I/O in its name.

Usage:
  python tools/run_stdlib_tests.py                 # default test set
  python tools/run_stdlib_tests.py test_float      # single test
  python tools/run_stdlib_tests.py --list          # show default set
  python tools/run_stdlib_tests.py -v              # pass -v to regrtest
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

# Tests whose names indicate float formatting/parsing involvement. We
# deliberately include tests beyond test_float because %g happens in many
# stdlib modules (json, decimal, unittest, ...).
DEFAULT_TESTS = [
    "test_float",
    "test_strtod",
    "test_fstring",
    "test_format",
    "test_complex",
    "test_json",
    "test_struct",
    "test_string",
    "test_decimal",
    "test_math",
    "test_cmath",
    "test_statistics",
]


def run(tests: list[str], verbose: bool, extra_args: list[str]) -> int:
    env = os.environ.copy()
    env["FLOATIUM_AUTOPATCH"] = "1"
    # Guardrail: make install failures noisy in case the .pth hook itself
    # has a problem. Without this the startup hook silently swallows errors
    # so the interpreter still comes up.
    env["FLOATIUM_AUTOPATCH_DEBUG"] = "1"

    argv = [sys.executable, "-m", "test"]
    if verbose:
        argv.append("-v")
    argv.extend(extra_args)
    argv.extend(tests)

    print(f"==> running: {' '.join(argv)}")
    print(f"==> FLOATIUM_AUTOPATCH=1")
    proc = subprocess.run(argv, env=env)
    return proc.returncode


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tests", nargs="*",
                   help="regrtest test names (default: DEFAULT_TESTS)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="pass -v to regrtest")
    p.add_argument("--list", action="store_true",
                   help="print DEFAULT_TESTS and exit")
    p.add_argument("--extra-args", nargs=argparse.REMAINDER, default=[],
                   help="additional arguments to pass after the test names")
    args = p.parse_args()

    if args.list:
        for t in DEFAULT_TESTS:
            print(t)
        return 0

    tests = args.tests or DEFAULT_TESTS

    # Verify floatium is importable first; a clean import failure here is
    # much more informative than a silent autopatch miss.
    try:
        import floatium  # noqa: F401
    except ImportError as e:
        print(f"error: import floatium failed: {e}", file=sys.stderr)
        print("hint: pip install -e . from the repo root first", file=sys.stderr)
        return 2

    return run(tests, args.verbose, args.extra_args)


if __name__ == "__main__":
    raise SystemExit(main())
