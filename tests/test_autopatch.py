"""Tests for the autopatch CLI and the env-var / marker precedence.

The CLI (`python -m floatium`) toggles a marker file in site-packages
and the autopatch hook honors a precedence order:
    FLOATIUM_AUTOPATCH env var > marker file > default ON.

These tests exercise the contract end-to-end by running a child
interpreter with controlled env / marker state and inspecting whether
floatium ends up installed.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

import floatium


def _run_cli(*args: str, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_overrides:
        for k, v in env_overrides.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    return subprocess.run(
        [sys.executable, "-m", "floatium", *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_child(code: str, env_overrides: dict[str, str] | None = None) -> str:
    """Run `python -c code` and return stdout; env_overrides modify os.environ."""
    env = os.environ.copy()
    if env_overrides:
        for k, v in env_overrides.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def _is_patched_in_child(env_overrides: dict[str, str] | None = None) -> bool:
    out = _run_child(
        "import floatium; print(floatium.is_patched())",
        env_overrides=env_overrides,
    )
    return out.strip() == "True"


def test_cli_status_runs():
    """`python -m floatium status` exits 0 and reports a state."""
    r = _run_cli("status", env_overrides={"FLOATIUM_AUTOPATCH": None})
    assert r.returncode == 0, r.stderr
    assert "floatium autopatch:" in r.stdout
    assert "ENABLED" in r.stdout or "DISABLED" in r.stdout


def test_cli_info_runs():
    """`python -m floatium info` exits 0 and shows the version + backends."""
    r = _run_cli("info")
    assert r.returncode == 0, r.stderr
    assert "floatium version:" in r.stdout
    assert "format_backend:" in r.stdout


def test_cli_status_reflects_env_var():
    """Env var should be reflected as the reason when set."""
    r_off = _run_cli("status", env_overrides={"FLOATIUM_AUTOPATCH": "0"})
    assert r_off.returncode == 0
    assert "DISABLED" in r_off.stdout
    assert "FLOATIUM_AUTOPATCH" in r_off.stdout

    r_on = _run_cli("status", env_overrides={"FLOATIUM_AUTOPATCH": "1"})
    assert r_on.returncode == 0
    assert "ENABLED" in r_on.stdout
    assert "FLOATIUM_AUTOPATCH" in r_on.stdout


def test_autopatch_default_is_on():
    """No env var, no marker → autopatch installs in the child."""
    assert _is_patched_in_child(env_overrides={"FLOATIUM_AUTOPATCH": None})


def test_env_var_zero_disables_autopatch():
    """FLOATIUM_AUTOPATCH=0 must suppress the default-on autopatch."""
    assert not _is_patched_in_child(
        env_overrides={"FLOATIUM_AUTOPATCH": "0"}
    )


def test_env_var_one_keeps_autopatch_on():
    """FLOATIUM_AUTOPATCH=1 (the legacy opt-in form) is honored."""
    assert _is_patched_in_child(
        env_overrides={"FLOATIUM_AUTOPATCH": "1"}
    )


def test_env_var_garbage_falls_back_to_default():
    """Unrecognized env-var values are treated as unset (default-on)."""
    assert _is_patched_in_child(
        env_overrides={"FLOATIUM_AUTOPATCH": "maybe"}
    )


def test_env_var_truthy_aliases():
    """true/yes/on (any case) also enable; false/no/off disable."""
    for v in ("true", "TRUE", "Yes", "on"):
        assert _is_patched_in_child(
            env_overrides={"FLOATIUM_AUTOPATCH": v}
        ), v
    for v in ("false", "FALSE", "No", "off"):
        assert not _is_patched_in_child(
            env_overrides={"FLOATIUM_AUTOPATCH": v}
        ), v


def test_cli_round_trip_disable_enable():
    """`disable` followed by `enable` returns to the default state.

    The marker file is per-environment (next to floatium.pth); we test
    in-process to avoid the side-effect of disabling autopatch system-wide
    while CI is running.
    """
    from floatium import _cli

    m = _cli._marker_path()
    initially_present = m.exists()

    try:
        # disable: marker should appear
        rc = _cli.cmd_disable(None)
        assert rc == 0
        assert m.exists()

        # enable: marker should be gone
        rc = _cli.cmd_enable(None)
        assert rc == 0
        assert not m.exists()
    finally:
        # Restore prior marker state regardless of outcome
        if initially_present and not m.exists():
            m.write_text("# restored by test\n")
        elif not initially_present and m.exists():
            m.unlink()


def test_env_var_wins_over_marker():
    """FLOATIUM_AUTOPATCH=1 should re-enable autopatch even with a marker.

    Creates a marker, then runs a child with FLOATIUM_AUTOPATCH=1 and
    confirms floatium IS installed (i.e., the env var won).
    """
    from floatium import _cli

    m = _cli._marker_path()
    initially_present = m.exists()

    try:
        if not initially_present:
            m.write_text("# created by test_env_var_wins_over_marker\n")
        # With marker present, default would be OFF — but env=1 must win.
        assert _is_patched_in_child(
            env_overrides={"FLOATIUM_AUTOPATCH": "1"}
        ), "FLOATIUM_AUTOPATCH=1 did not override the marker"
        # Conversely, marker alone (no env) should disable.
        assert not _is_patched_in_child(
            env_overrides={"FLOATIUM_AUTOPATCH": None}
        ), "marker file did not disable autopatch"
    finally:
        if not initially_present and m.exists():
            m.unlink()


def test_cli_disable_when_already_disabled_is_noop():
    """Running `disable` when the marker already exists exits 0 and says so."""
    from floatium import _cli

    m = _cli._marker_path()
    initially_present = m.exists()

    try:
        if not initially_present:
            m.write_text("# created by test\n")
        r = _run_cli("disable")
        assert r.returncode == 0
        assert "already disabled" in r.stdout
    finally:
        if not initially_present and m.exists():
            m.unlink()


def test_cli_enable_when_already_enabled_is_noop():
    """Running `enable` with no marker exits 0 and reports the no-op."""
    from floatium import _cli

    m = _cli._marker_path()
    if m.exists():
        pytest.skip("marker exists in this env; the no-op path can't be tested")
    r = _run_cli("enable")
    assert r.returncode == 0
    assert "already enabled" in r.stdout


def test_pth_hook_is_silent_in_subinterpreter():
    """The autopatch .pth hook must not print errors in a subinterpreter.

    floatium._ext is a process-global monkey-patch and deliberately does
    not support subinterpreters. CPython stdlib tests (e.g. test_struct)
    create subinterpreters, each of which runs site.py / the .pth hook;
    the hook must fail silently there rather than letting an ImportError
    escape to site.py (which would dump a traceback per subinterpreter).
    """
    try:
        import _interpreters  # noqa: F401
    except ImportError:
        pytest.skip("subinterpreters not available on this build")

    code = (
        "import _interpreters as I\n"
        "interp = I.create()\n"
        "I.run_string(interp, 'x = repr(0.1)')\n"
        "I.destroy(interp)\n"
        "print('OK')\n"
    )
    # Child runs with autopatch ON (default) so the .pth fires in the
    # subinterpreter. Any 'Error processing line' on stderr is a regression.
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == "OK"
    assert "Error processing line" not in proc.stderr, (
        f"autopatch .pth leaked an error in a subinterpreter:\n{proc.stderr}"
    )
    assert "does not support loading in subinterpreters" not in proc.stderr, (
        f"subinterpreter ImportError escaped the .pth hook:\n{proc.stderr}"
    )
