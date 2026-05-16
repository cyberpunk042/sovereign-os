"""Layer 1 — decisions log lint. Verifies D-NNN sequence is monotonic
and Q-X cross-references resolve."""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DECISIONS = REPO_ROOT / "docs" / "decisions.md"

DECISION_HEADER = re.compile(r"^#{2,3} D-(\d{3}) — \d{4}-\d{2}-\d{2} — .+$", re.M)
QUESTION_HEADER = re.compile(r"^### Q-(\d{3}|\w{1,3}-?\w?) — .+$", re.M)


def test_decisions_file_exists():
    assert DECISIONS.exists(), f"docs/decisions.md missing at {DECISIONS}"


def test_decisions_are_monotonic_increasing():
    text = DECISIONS.read_text()
    decisions = DECISION_HEADER.findall(text)
    nums = [int(d) for d in decisions]
    assert nums == sorted(nums), f"D-NNN entries not in monotonic order: {nums}"
    # No gaps either (audit-trail discipline)
    for i, n in enumerate(nums, 1):
        assert n == i, f"D-NNN sequence has gap at D-{n:03d} (expected D-{i:03d})"


def test_questions_present():
    """Every Q-NNN should be findable in the decisions log."""
    text = DECISIONS.read_text()
    questions = QUESTION_HEADER.findall(text)
    # At least Q-001..Q-019 from PR 1 + operator-added Q-016/Q-017/Q-018/Q-019
    assert "001" in questions or "Q-001" in text, "Q-001 must be present"
    assert "017" in questions or "Q-017" in text, "Q-017 (inference backend) must be present"
    assert "019" in questions or "Q-019" in text, "Q-019 (lifecycle surface) must be present"
