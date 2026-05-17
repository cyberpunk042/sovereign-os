"""L1 lint — `tools/claude/rearm-goal-from-mandate.sh` must emit a
goal-text within the harness char limit + cite the active mandate
file. Anti-recurrence guard for the discovery in
docs/standing-directives/goal-rearming.md.
"""

from __future__ import annotations

import pathlib
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HARNESS_CHAR_LIMIT = 4000


def _run_script() -> str:
    script = REPO_ROOT / "tools" / "claude" / "rearm-goal-from-mandate.sh"
    assert script.is_file() and script.stat().st_mode & 0o111, (
        f"{script} must exist + be executable"
    )
    r = subprocess.run([str(script)], capture_output=True, text=True, check=False)
    assert r.returncode == 0, (
        f"rearm script exited rc={r.returncode}; stderr={r.stderr}"
    )
    return r.stdout


def test_rearm_goal_script_is_under_harness_char_limit():
    """The whole point of the script: stay under 4000 chars so the
    harness `/goal` command accepts it."""
    output = _run_script()
    assert 0 < len(output) <= HARNESS_CHAR_LIMIT, (
        f"goal-text must be 1..{HARNESS_CHAR_LIMIT} chars; got {len(output)}"
    )


def test_rearm_goal_script_pointers_at_mandate_file():
    """The compact goal-text must link to the durable mandate file
    rather than inlining the verbatim text (the original failure was
    the verbatim text exceeding the char limit)."""
    output = _run_script()
    assert "docs/standing-directives/" in output, (
        "goal-text must pointer at the mandate file path"
    )
    assert ".md" in output


def test_rearm_goal_script_carries_continue_signal():
    """When the harness re-fires this as a Stop-hook condition, the
    condition evaluator must NOT auto-clear on routine progress —
    the language must be open-ended."""
    output = _run_script().lower()
    # At least one of these long-running signal phrases must appear.
    signals = ("never stop", "continue endlessly", "open-ended",
               "next todo module", "ship one round per turn")
    assert any(s in output for s in signals), (
        f"goal-text must carry an open-ended signal; got: {output[:200]!r}"
    )


def test_rearm_goal_script_lists_epics():
    """Active Epics must surface in the goal-text so condition
    evaluators see the structural decomposition."""
    output = _run_script()
    # At least E1..E9 should appear (the operator-mandate Epics).
    epic_ids = [f"E{i}" for i in range(1, 10)]
    assert any(eid in output for eid in epic_ids), (
        "goal-text must enumerate active Epic IDs"
    )


def test_goal_rearming_doc_exists():
    """The root-cause analysis + paste-ready snippet doc must ship
    with the script."""
    doc = REPO_ROOT / "docs" / "standing-directives" / "goal-rearming.md"
    assert doc.is_file(), f"{doc} missing"
    body = doc.read_text()
    # Cite the actual harness limit so future maintainers don't have
    # to re-discover the number.
    assert "4000" in body, "doc must cite the 4000-char harness limit"
    # Cite the three-layer fix so operators see all the options.
    for layer in ("Layer A", "Layer B", "Layer C"):
        assert layer in body, f"doc must enumerate {layer}"
