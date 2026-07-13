#!/usr/bin/env python3
"""
tests/lint/test_fmt_hook_contract.py — the local pre-push fmt gate mirrors CI
(F-2026-095 / SDD-987).

The July intelligence-layer arc landed 52 `cargo fmt` violations because it was
authored on a long-lived branch that never opened a PR, bypassing CI's fmt gate.
`scripts/git-hooks/pre-push` closes that hole by running the SAME check at push
time. This lint keeps the two in lockstep: if CI's fmt command changes, or the
hook drifts from it, this fails — so the local gate can never silently stop
matching the authoritative CI gate.

Stdlib + pytest only.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "scripts" / "git-hooks" / "pre-push"
CI = REPO / ".github" / "workflows" / "test.yml"

FMT_GATE = "cargo fmt --all --check"


def test_pre_push_hook_exists_and_is_executable():
    assert HOOK.is_file(), "scripts/git-hooks/pre-push missing (the local fmt gate, SDD-987)"
    assert HOOK.stat().st_mode & 0o111, "scripts/git-hooks/pre-push is not executable"


def test_pre_push_is_valid_bash():
    r = subprocess.run(["bash", "-n", str(HOOK)], capture_output=True, text=True)
    assert r.returncode == 0, f"pre-push has a bash syntax error:\n{r.stderr}"


def test_pre_push_runs_the_ci_fmt_gate():
    assert FMT_GATE in HOOK.read_text(encoding="utf-8"), (
        f"scripts/git-hooks/pre-push must run the CI-exact `{FMT_GATE}` so the "
        "local gate mirrors CI"
    )


def test_ci_still_runs_that_fmt_gate():
    """If CI's fmt command changes, this fails — a reminder to update the hook so
    the two never drift apart."""
    assert CI.is_file(), ".github/workflows/test.yml missing"
    assert FMT_GATE in CI.read_text(encoding="utf-8"), (
        f"CI no longer runs `{FMT_GATE}` — update both CI and "
        "scripts/git-hooks/pre-push together (they must mirror)."
    )
