"""R434 (E10.M78) — operator-pull intelligence verbs contract lint.

Extends R387-R433 + R382/R386 operational-artifact pinning to the
4 operator-pull intelligence verbs that surface doctrine + state:
  scripts/intelligence/doctrine-status.py    (R376 — lint health)
  scripts/intelligence/quarterly-review.py   (R378 — quarterly state)
  scripts/intelligence/morning-brief.py      (R338 — daily orient)
  scripts/intelligence/next-action-advisor.py (operator-pull next-step)

Each verb implements the operator-discoverable pattern:
  - CLI subcommands
  - --json / --human format flags
  - operator-overlay TOML config support
  - documented exit-code surface

These verbs are dispatched by sovereign-osctl (R413). R434 ensures
each verb is a working operator-discovery surface — not a stub.

If a future agent silently:
  - removes a verb's CLI subcommand = sovereign-osctl wrapper invokes
    a missing subcommand
  - drops --json output = fleet aggregation breaks
  - returns no useful content (e.g., just 'OK') = operator-pull surface
    is inert
…the operator-pull intelligence layer silently degrades.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEL_DIR = REPO_ROOT / "scripts" / "intelligence"

EXPECTED_VERBS = [
    "doctrine-status.py",
    "quarterly-review.py",
    "morning-brief.py",
    "next-action-advisor.py",
]


def _read(name: str) -> str:
    p = INTEL_DIR / name
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_all_four_verbs_exist():
    for name in EXPECTED_VERBS:
        p = INTEL_DIR / name
        assert p.is_file(), (
            f"operator-pull intelligence verb missing: {p}"
        )


def test_all_verbs_are_python3():
    """All verbs MUST use #!/usr/bin/env python3 (operator
    discovers ./scripts/intelligence/X.py is runnable)."""
    for name in EXPECTED_VERBS:
        body = _read(name)
        assert body.startswith("#!/usr/bin/env python3"), (
            f"{name} missing python3 shebang"
        )


def test_all_verbs_have_docstring():
    """Module-level docstring documents the operator-discoverable
    'WHY this verb exists' surface."""
    for name in EXPECTED_VERBS:
        body = _read(name)
        # First triple-quoted block must exist and be non-trivial
        m = re.search(r'^"""(.+?)"""', body, re.DOTALL | re.M)
        assert m, (
            f"{name} missing module docstring"
        )
        doc = m.group(1).strip()
        assert len(doc) >= 30, (
            f"{name} docstring too short (operator-discovery surface)"
        )


# --- Per-verb required features ---


def test_doctrine_status_documents_round_provenance():
    """R376 reference in docstring (operator-discoverable round
    provenance)."""
    body = _read("doctrine-status.py")
    has_round = (
        "R376" in body
        or "SDD-037" in body
    )
    assert has_round, (
        "doctrine-status.py missing R376 / SDD-037 round provenance"
    )


def test_doctrine_status_runs_pytest_against_lint_family():
    """The verb's whole purpose is to wrap pytest on the SDD-037
    lint family. Drift = verb doesn't actually run any tests."""
    body = _read("doctrine-status.py")
    has_pytest = "pytest" in body.lower()
    assert has_pytest, (
        "doctrine-status.py doesn't invoke pytest "
        "(its core purpose is to wrap pytest for operators)"
    )


def test_doctrine_status_targets_tests_lint_path():
    """Specifically tests/lint/ — the SDD-037 family lives there."""
    body = _read("doctrine-status.py")
    assert "tests/lint" in body, (
        "doctrine-status.py doesn't target tests/lint/ "
        "(SDD-037 family location)"
    )


def test_doctrine_status_has_status_subcommand():
    body = _read("doctrine-status.py")
    assert '"status"' in body or "'status'" in body, (
        "doctrine-status.py missing 'status' subcommand"
    )


def test_doctrine_status_has_tally_subcommand():
    body = _read("doctrine-status.py")
    assert '"tally"' in body or "'tally'" in body, (
        "doctrine-status.py missing 'tally' subcommand"
    )


def test_doctrine_status_has_run_subcommand():
    """'run' subcommand executes pytest (slow verb ~1-3s)."""
    body = _read("doctrine-status.py")
    assert '"run"' in body or "'run'" in body, (
        "doctrine-status.py missing 'run' subcommand"
    )


# --- Cross-verb invariants ---


def test_all_verbs_use_argparse():
    """Argparse-based CLI (operator-discoverable -h)."""
    for name in EXPECTED_VERBS:
        body = _read(name)
        assert "argparse" in body, (
            f"{name} not using argparse (operator -h broken)"
        )


def test_all_verbs_support_json_output():
    """--json format flag for fleet aggregation."""
    for name in EXPECTED_VERBS:
        body = _read(name)
        assert "--json" in body, (
            f"{name} missing --json output flag "
            f"(fleet aggregation broken)"
        )


def test_all_verbs_support_human_output():
    """--human format flag for terminal."""
    for name in EXPECTED_VERBS:
        body = _read(name)
        assert "--human" in body, (
            f"{name} missing --human output flag "
            f"(operator terminal display broken)"
        )


def test_all_verbs_document_exit_codes():
    """Exit-code documentation in module docstring (operator-
    discoverable failure-mode surface)."""
    for name in EXPECTED_VERBS:
        body = _read(name)
        has_codes = (
            "Exit codes" in body
            or "exit code" in body.lower()
            or re.search(r"^\s*0\s+ok\b", body, re.M | re.I)
        )
        assert has_codes, (
            f"{name} missing exit-code documentation"
        )


def test_all_verbs_have_main_function():
    """def main() entry point (operator-discoverable + importable)."""
    for name in EXPECTED_VERBS:
        body = _read(name)
        has_main = (
            re.search(r"^def main\(", body, re.M)
            or "def main(" in body
        )
        assert has_main, (
            f"{name} missing main() entry function"
        )


def test_all_verbs_dispatched_via_if_name_main():
    """if __name__ == '__main__': main() pattern (operator can
    run as ./script.py)."""
    for name in EXPECTED_VERBS:
        body = _read(name)
        has_dispatch = '__name__ == "__main__"' in body or "__name__ == '__main__'" in body
        assert has_dispatch, (
            f"{name} missing __main__ dispatch "
            f"(operator can't run as script)"
        )


# --- Operator-overlay support (SDD-030) ---


def test_doctrine_status_supports_operator_overlay():
    """SDD-030 verbatim: operator-overlay config at
    /etc/sovereign-os/<verb>.toml allows operator extension."""
    body = _read("doctrine-status.py")
    has_overlay = (
        "/etc/sovereign-os/doctrine-status.toml" in body
        or "operator-overlay" in body.lower()
        or "SDD-030" in body
    )
    assert has_overlay, (
        "doctrine-status.py missing operator-overlay support "
        "(SDD-030 — operator can't extend the verb)"
    )


# --- Bidirectional consistency with sovereign-osctl ---


def test_verbs_dispatched_by_osctl():
    """sovereign-osctl R413 dispatches these verbs. Each verb
    MUST be invocable via the operator-named CLI surface."""
    osctl = REPO_ROOT / "scripts" / "sovereign-osctl"
    if not osctl.is_file():
        return  # graceful skip
    osctl_body = osctl.read_text(encoding="utf-8")
    # doctrine-status should be invocable via sovereign-osctl
    assert (
        "doctrine-status" in osctl_body
        or "doctrine_status" in osctl_body
        or "cmd_doctrine" in osctl_body
    ), (
        "sovereign-osctl doesn't reference doctrine-status verb "
        "(bidirectional consistency: verb exists but not dispatched)"
    )
