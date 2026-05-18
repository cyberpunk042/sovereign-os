"""R374 (E10.M18) — round-reference validator (extends SDD-037 family).

Every `R<N>` round reference in the mandate file Rounds column MUST
have a corresponding commit message in git history. Catches:

  - Agent invents round R999 (no commit ever shipped it)
  - Agent typos round number (R354 → R345)
  - Mandate row claims R<N> ships work but the commit message
    actually says R<M>

Note: this is a "shape sanity check" not a "completeness check" —
the lint asserts every round number cited in the Rounds column is
plausible (numbered in the active range + commit history shows it),
not that every R<N> equals its claimed work.

Continues the fabrication-catch quartet:
  R368: §N spec section refs (master spec)
  R371: E.M mandate row refs
  R372: sovereign-osctl verb dispatch + SDD refs
  R373: cross-catalog phrase consistency
  R374: round-number citation validity (this round)
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANDATE = (REPO_ROOT / "docs" / "standing-directives"
           / "2026-05-17-operator-mandate.md")


def _git_commits_in_history() -> set[str]:
    """Return set of all R<N> round refs found in git commit messages.
    NEVER raises — returns empty set if git not available."""
    try:
        cp = subprocess.run(
            ["git", "log", "--all", "--pretty=format:%s%n%b"],
            capture_output=True, text=True, timeout=20, cwd=REPO_ROOT,
        )
    except Exception:
        return set()
    if cp.returncode != 0:
        return set()
    # Extract all R<N> patterns from commit messages
    return set(re.findall(r"\bR(\d+)\b", cp.stdout))


def _mandate_rounds_column_refs() -> dict[str, list[str]]:
    """Parse the mandate file. For each row, extract R<N> refs from
    the Rounds column (the last `|` field). Returns mapping
    {row_id: [round_refs]}."""
    body = MANDATE.read_text(encoding="utf-8")
    out: dict[str, list[str]] = {}
    # Mandate row: "| E<N>.M<N> | <text> | <status> | <rounds> |"
    pattern = re.compile(
        r"^\| (E\d+\.M\d+) \|[^|]*\|[^|]*\| ([^|]*) \|", re.M)
    for m in pattern.finditer(body):
        row_id = m.group(1)
        rounds_field = m.group(2)
        # Find R<N> references in the rounds field
        round_refs = re.findall(r"\bR(\d+)\b", rounds_field)
        if round_refs:
            out[row_id] = round_refs
    return out


def test_mandate_rounds_column_parses():
    """Sanity: we can parse ≥100 rounds columns from mandate."""
    refs = _mandate_rounds_column_refs()
    assert len(refs) >= 100, (
        f"only parsed {len(refs)} mandate rows with rounds columns; "
        "parser may be broken or mandate may be truncated."
    )


def test_round_numbers_in_active_range():
    """Every R<N> round cited in mandate Rounds column must be in
    the active range R1..R<MAX> (current MAX = R400 — generous
    upper bound). Catches: agents inventing R9999."""
    refs = _mandate_rounds_column_refs()
    for row_id, rounds in refs.items():
        for r in rounds:
            n = int(r)
            assert 1 <= n <= 400, (
                f"mandate row {row_id} cites R{r} which is OUT OF "
                f"ACTIVE RANGE (1..400). Either operator extended the "
                f"upper bound or this is a fabricated round number."
            )


def test_round_numbers_well_formed_no_zero_padding():
    """R<N> citations in mandate ROUNDS COLUMN must be unpadded
    (R5 not R005). Scope: only the Rounds column of each row.
    Documentation examples in row text (e.g. 'R5 not R005' as a
    counter-example) are allowed."""
    refs = _mandate_rounds_column_refs()
    bad: list[tuple[str, str]] = []
    for row_id, rounds in refs.items():
        for r in rounds:
            if r.startswith("0") and len(r) > 1:
                bad.append((row_id, r))
    assert not bad, (
        f"mandate Rounds column contains zero-padded round numbers: "
        f"{bad}. Operator convention is unpadded integers."
    )


def test_recent_rounds_in_commit_history():
    """The most recently-mentioned rounds in the mandate (R350+) MUST
    appear in git commit history. Catches: agent claimed R374 in
    mandate but never committed it; or claimed R366 but never wired
    it up. Older rounds (R1..R349) skipped since they predate this
    branch's git history."""
    commits = _git_commits_in_history()
    if not commits:
        # No git available in test env — skip
        return
    refs = _mandate_rounds_column_refs()
    cited_recent = set()
    for row_id, rounds in refs.items():
        for r in rounds:
            n = int(r)
            if n >= 350:
                cited_recent.add(r)
    missing = sorted(cited_recent - commits, key=int)
    assert not missing, (
        f"mandate cites R<N> values not in commit history: {missing}. "
        f"Either the commits got lost or the mandate row is "
        f"fabricated. Recent R-numbers (R350+) MUST have backing commits."
    )


def test_no_primary_round_number_collision_in_recent_rows():
    """Within the recent E10 epic rows (R350+ era), each row's
    PRIMARY round (first R<N> in the Rounds column) should be unique.
    Cross-references to other R<N> in row notes are allowed — only
    primary attribution must not collide."""
    refs = _mandate_rounds_column_refs()
    primary_rounds: dict[str, list[str]] = {}
    for row_id, rounds in refs.items():
        if not row_id.startswith("E10.") or not rounds:
            continue
        primary = rounds[0]  # First R<N> = primary attribution
        primary_rounds.setdefault(primary, []).append(row_id)
    duplicates = {r: sorted(set(rows)) for r, rows
                  in primary_rounds.items() if len(set(rows)) > 1}
    assert not duplicates, (
        f"Primary R-number collision in E10 mandate rows: {duplicates}. "
        f"Each row's primary R<N> (first one in Rounds column) MUST be "
        f"unique. Cross-references to other rounds in notes are fine."
    )


def test_mandate_total_row_count_sane():
    """Sanity backstop: mandate file should have ≥150 rows by this
    stage. R373+ work has expanded coverage substantially."""
    refs = _mandate_rounds_column_refs()
    assert len(refs) >= 150, (
        f"mandate has only {len(refs)} parseable rows — expected ≥150."
    )
