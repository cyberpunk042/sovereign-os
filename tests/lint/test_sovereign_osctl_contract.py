"""R413 (E10.M57) — sovereign-osctl operator-CLI contract lint.

Extends R387-R412 operational-artifact pinning to:
  scripts/sovereign-osctl  (operator-facing single-entry-point CLI)

R383 already covered the help-text r-arc-verb discoverability surface.
R413 covers the BROADER CLI dispatcher contract: every operator-named
subcommand has a matching cmd_<name> handler, the script can locate
its lib from multiple install paths, Q-019 verbatim framing preserved.

Q-019 verbatim (operator-named):
  > "even once installed and configured it will be possible to manage
  >  the OS like we need to even if we need to add such an additional
  >  tool and even service possibly or even multiple adapted if need be"

This is the operator's CLI-manageability mandate. sovereign-osctl is
the implementation. Drift to remove subcommands silently breaks the
operator-manageability contract.

If a future agent silently:
  - drops the Q-019 verbatim quote from header = sacrosanct framing erased
  - removes a cmd_<name> handler but keeps its dispatcher entry = silent
    'command not found' for operator-named subcommands
  - removes 'set -euo pipefail' = unset-var bugs creep in silently
  - drops a lib-search path = osctl breaks when operator installs to
    a non-default prefix
…operator's Q-019 manageability contract silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

# Operator-named commands that MUST exist in the dispatcher. Each MUST
# have a matching cmd_<name> handler function.
EXPECTED_COMMANDS = [
    "status", "assistant", "doctor",
    "profiles", "whitelabel", "perimeter",
    "models", "audit", "maintenance",
    "metrics", "journal", "history",
    "thermals", "alerts", "env",
    "init", "trinity", "wizard",
    "bootstrap", "secure-boot", "install",
    "hooks", "decommission", "inference",
    "overview",
]


def _read() -> str:
    assert OSCTL.is_file(), f"missing {OSCTL}"
    modules = REPO_ROOT / "scripts" / "osctl.d"
    return OSCTL.read_text(encoding="utf-8") + "\n" + "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(modules.glob("*.sh"))
    )


def test_osctl_exists():
    assert OSCTL.is_file(), f"missing {OSCTL}"


def test_osctl_is_executable():
    """The operator-facing CLI MUST be executable (else 'bash
    sovereign-osctl' workaround is needed)."""
    import os
    assert os.access(OSCTL, os.X_OK), (
        "scripts/sovereign-osctl missing executable bit "
        "(operator can't invoke as 'sovereign-osctl ...')"
    )


# --- Operator-named framing ---


def test_q_019_verbatim_quote_present():
    """Q-019 verbatim operator framing is SACROSANCT — header MUST
    quote the operator's exact wording. Drift = framing erased."""
    body = _read()
    assert "Q-019" in body, (
        "sovereign-osctl missing 'Q-019' reference "
        "(operator-named question-id binding)"
    )
    # Look for key phrases from the verbatim quote (may be wrapped
    # across shell-comment lines — match by individual phrase)
    has_verbatim = (
        "even once installed and configured" in body
        and "manage" in body
        and "the OS" in body
    )
    assert has_verbatim, (
        "sovereign-osctl missing Q-019 verbatim operator framing "
        "in header (sacrosanct — 'even once installed and configured "
        "it will be possible to manage the OS...')"
    )


def test_sacrosanct_marker_in_comments():
    """The verbatim quote MUST be marked sacrosanct (defense-in-depth
    against well-meaning reformatting that breaks operator-exact text)."""
    body = _read()
    assert "sacrosanct" in body.lower(), (
        "sovereign-osctl missing 'sacrosanct' marker on Q-019 verbatim "
        "(drift = future agent reformats operator-exact text)"
    )


def test_set_euo_pipefail():
    """Bash strict mode — sovereign-osctl handles operator install/
    decommission flows. Drift to weaker shell options = unset-var
    bugs slip through to operator's running system."""
    body = _read()
    assert "set -euo pipefail" in body, (
        "sovereign-osctl missing 'set -euo pipefail' bash strict mode "
        "(SDD-001 verbatim shell discipline)"
    )


# --- Dispatcher contract ---


def test_all_expected_commands_have_handler():
    """Every operator-named subcommand MUST have a cmd_<name>
    handler. Drift = silent 'command not found' for operator-named verbs."""
    body = _read()
    for cmd in EXPECTED_COMMANDS:
        # Bash function names use underscore, CLI uses dash
        handler = "cmd_" + cmd.replace("-", "_")
        pattern = re.compile(rf"^{re.escape(handler)}\(\)\s*\{{", re.M)
        assert pattern.search(body), (
            f"sovereign-osctl missing handler {handler}() for "
            f"operator-named subcommand {cmd!r}"
        )


def test_all_expected_commands_in_dispatcher():
    """Every cmd_<name> handler MUST be routed by the main case
    statement. Drift = handler exists but is silently unreachable."""
    body = _read()
    for cmd in EXPECTED_COMMANDS:
        handler = "cmd_" + cmd.replace("-", "_")
        # Two dispatch forms are valid (F-2026-025):
        #   resident: '  status)   cmd_status "$@" ;;'
        #   modular:  '  ms003)     _source_osctl_module ms003 && cmd_ms003 "$@" ;;'
        # (the extracted verbs source their osctl.d/<verb>.sh module first).
        pattern = re.compile(
            rf"^\s*{re.escape(cmd)}\)\s+"
            rf"(?:_source_osctl_module\s+{re.escape(cmd)}\s+&&\s+)?"
            rf"{re.escape(handler)}\b",
            re.M,
        )
        assert pattern.search(body), (
            f"sovereign-osctl dispatcher missing '{cmd}) {handler}' "
            f"route (handler exists but unreachable)"
        )


def test_help_command_handler_exists():
    """help command MUST have its own handler (operator-discovery
    surface — 'sovereign-osctl help' is the first thing a new operator
    types)."""
    body = _read()
    assert "cmd_help()" in body, (
        "sovereign-osctl missing cmd_help() handler "
        "(operator-discovery — primary help-text surface)"
    )


def test_version_command_handler_exists():
    """version command for operator-discoverable identity surface."""
    body = _read()
    assert "cmd_version" in body, (
        "sovereign-osctl missing cmd_version handler "
        "(operator-discovery — version identity surface)"
    )


# --- Library-locator contract ---


def test_multiple_lib_search_paths():
    """sovereign-osctl MUST search multiple lib paths so it works in
    both in-repo dev context and post-install (/usr/local/lib/sovereign-os,
    /usr/lib/sovereign-os, /opt/sovereign-os). Drift losing any silently
    breaks one install mode."""
    body = _read()
    expected_paths = [
        "/usr/local/lib/sovereign-os",
        "/usr/lib/sovereign-os",
        "/opt/sovereign-os",
    ]
    for path in expected_paths:
        assert path in body, (
            f"sovereign-osctl missing lib search path {path!r} "
            f"(drift breaks install with that PREFIX)"
        )


def test_sovereign_os_lib_env_override():
    """SOVEREIGN_OS_LIB env var MUST be honored as the first-priority
    override (operator can point to a custom lib location)."""
    body = _read()
    assert "SOVEREIGN_OS_LIB" in body, (
        "sovereign-osctl missing SOVEREIGN_OS_LIB env override "
        "(operator can't specify non-standard lib location)"
    )


def test_explicit_error_on_missing_lib():
    """If no lib found, sovereign-osctl MUST exit non-zero with a
    discoverable error. Drift to silent-skip = confusing 'command not
    found' for downstream invocations."""
    body = _read()
    has_explicit_error = (
        "can't locate its lib" in body
        and "exit 1" in body
    )
    assert has_explicit_error, (
        "sovereign-osctl missing explicit 'can't locate lib' error "
        "(drift = silent failure, confusing operator)"
    )


# --- Active-profile discovery ---


def test_active_profile_from_etc():
    """sovereign-osctl MUST read /etc/sovereign-os/active-profile to
    pick the operator's installed profile. Drift = always reverts to
    'sain-01' hardcoded default = wrong commands on other profiles."""
    body = _read()
    assert "/etc/sovereign-os/active-profile" in body, (
        "sovereign-osctl missing /etc/sovereign-os/active-profile read "
        "(operator's installed-profile selection)"
    )


def test_sain_01_fallback_default():
    """If active-profile isn't set, fall back to sain-01 (the operator-
    named primary profile). Drift to 'minimal' or empty = wrong
    profile-dependent commands."""
    body = _read()
    # Pattern: || echo sain-01
    assert "sain-01" in body, (
        "sovereign-osctl missing sain-01 default fallback "
        "(operator-named primary profile)"
    )


# --- R-arc operator-pull verb discoverability (R383 + extension) ---


def test_operator_pull_verbs_in_help():
    """R383: help text MUST surface the R-arc operator-pull verbs
    (architecture-qa / coverage / layers / etc.). Drift removes
    operator-discoverability of the new verbs."""
    body = _read()
    # Help text section should list at least these verbs
    expected_verbs = [
        "architecture-qa",
        "coverage",
        "layers",
        "search",
    ]
    for verb in expected_verbs:
        assert verb in body, (
            f"sovereign-osctl missing operator-pull verb {verb!r} "
            f"(R383 — R-arc discoverability surface)"
        )


# --- Cross-script contract: dispatcher count vs handler count ---


def test_dispatcher_to_handler_consistency():
    """Bidirectional consistency: every handler in the script MUST
    be reachable via the dispatcher. Drift = orphaned handlers
    (dead code) OR orphaned dispatcher entries (silent fail)."""
    body = _read()
    # Find all defined cmd_<name>() handlers
    handlers = set(re.findall(r"^cmd_([a-z_]+)\(\)", body, re.M))
    # Find all dispatched cmd_<name> calls (in the case statement)
    dispatched = set(re.findall(r"\bcmd_([a-z_]+)\s+\"\$@\"", body))

    # 'help' is dispatched via fall-through / default and may not
    # appear in the case explicitly — exempt
    handlers.discard("help")
    dispatched.discard("help")

    orphan_handlers = handlers - dispatched
    orphan_dispatched = dispatched - handlers

    # Allow some orphan handlers (helpers like cmd_show called from
    # cmd_profiles); just flag if the count is unexpectedly large
    assert len(orphan_handlers) <= 8, (
        f"too many orphan cmd_<name> handlers (not dispatched): "
        f"{sorted(orphan_handlers)} — cleanup or wire them in"
    )
    assert not orphan_dispatched, (
        f"sovereign-osctl dispatcher references nonexistent handlers: "
        f"{sorted(orphan_dispatched)} (silent 'command not found' "
        f"for operator-named verbs)"
    )


def test_active_profile_environment_export():
    """SOVEREIGN_OS_PROFILE MUST be set / exported (downstream scripts
    rely on this env var)."""
    body = _read()
    assert "SOVEREIGN_OS_PROFILE" in body, (
        "sovereign-osctl missing SOVEREIGN_OS_PROFILE env "
        "(operator's active-profile selector)"
    )
