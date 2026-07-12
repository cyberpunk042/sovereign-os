"""MASTER-PLAN count-consistency lint (F-2026-032 / SDD-959).

`docs/MASTER-PLAN.md` is the cross-repo milestone synthesis (selfdef +
sovereign-os). The audit found it self-contradictory — it stated both "128" and
"130" milestones, its sovereign-os count (82) trailed the file tree (84), and
two milestones (M085/M086) were missing from the enumeration.

This lint pins the **in-repo-verifiable** invariants so it can't silently drift
again:

  1. every `backlog/milestones/M*.md` (sovereign-os) is linked in the milestone
     enumeration — no silently-missing milestone;
  2. the top-line table's sovereign-os cell equals the actual M*.md file count;
  3. the combined total equals selfdef-cell + sovereign-os-cell;
  4. the three places that state the combined total (the intro line, the table,
     the "## The N milestones" header) all agree — the exact 128-vs-130
     contradiction the finding flagged.

The selfdef cell is **cross-repo** (`../../selfdef/backlog/milestones/MS*.md`,
not present in this checkout), so its value is checked only for internal
consistency, not against the selfdef tree — a documented limitation.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MASTER_PLAN = REPO_ROOT / "docs" / "MASTER-PLAN.md"
MILESTONES = REPO_ROOT / "backlog" / "milestones"


def _body() -> str:
    return MASTER_PLAN.read_text(encoding="utf-8")


def _milestone_files() -> set[str]:
    return {p.name for p in MILESTONES.glob("M[0-9][0-9][0-9]*.md")}


def _table_counts() -> tuple[int, int, int]:
    """(selfdef, sovereign_os, combined) from the top-line Milestones row."""
    m = re.search(
        r"\|\s*Milestones \(M\*\.md files\)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*\*\*(\d+)\*\*\s*\|",
        _body(),
    )
    assert m, "MASTER-PLAN top-line 'Milestones (M*.md files)' row not found/parseable"
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _enumerated_sovereign_milestones() -> set[str]:
    """Sovereign-os milestone files linked in the enumeration section."""
    body = _body()
    start = body.find("milestones (by repo, by ID)")
    section = body[start:] if start != -1 else body
    return set(re.findall(r"(M[0-9]{3}[a-z0-9-]*\.md)", section))


def test_master_plan_exists():
    assert MASTER_PLAN.is_file(), f"missing {MASTER_PLAN}"


def test_every_milestone_file_is_enumerated():
    missing = sorted(_milestone_files() - _enumerated_sovereign_milestones())
    assert not missing, (
        f"sovereign-os milestone files not linked in the MASTER-PLAN enumeration: "
        f"{missing}. Add them to '## The N milestones (by repo, by ID)' and bump "
        f"the counts."
    )


def test_no_stale_enumeration_entries():
    files = _milestone_files()
    stale = sorted(m for m in _enumerated_sovereign_milestones() if m not in files)
    assert not stale, (
        f"MASTER-PLAN enumerates milestone files that no longer exist: {stale}"
    )


def test_sovereign_os_count_matches_file_tree():
    _, sovereign, _ = _table_counts()
    actual = len(_milestone_files())
    assert sovereign == actual, (
        f"MASTER-PLAN top-line sovereign-os milestone count is {sovereign} but "
        f"backlog/milestones/ has {actual} M*.md files"
    )


def test_combined_total_is_internally_consistent():
    selfdef, sovereign, combined = _table_counts()
    assert combined == selfdef + sovereign, (
        f"MASTER-PLAN combined milestone total {combined} != selfdef {selfdef} + "
        f"sovereign-os {sovereign}"
    )


def test_all_stated_totals_agree():
    """The intro line, the table combined cell, and the '## The N milestones'
    header must all state the same total — the 128-vs-130 contradiction guard."""
    body = _body()
    _, _, combined = _table_counts()
    intro = re.search(r"synthesis of the existing (\d+) milestones", body)
    header = re.search(r"##\s*The (\d+) milestones", body)
    assert intro and int(intro.group(1)) == combined, (
        f"intro line total {intro.group(1) if intro else '?'} != table combined {combined}"
    )
    assert header and int(header.group(1)) == combined, (
        f"'## The N milestones' header {header.group(1) if header else '?'} != "
        f"table combined {combined}"
    )
