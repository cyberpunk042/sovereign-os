"""SDD INDEX status-completeness lint (F-2026-099 / SDD-996).

SDD-961 (F-2026-031) established INDEX status *hygiene* — a valid status
vocabulary + no stale feature-branch refs. But it left the **draft→complete**
transition unenforced: 126 of 178 rows sat `draft` even though 44 of them
declared, in their own Notes, that the work had **shipped on branch / this
session** (i.e. merged to `main` — the row is only on `main` because its PR
merged). A shipped SDD frozen at `draft` makes the index lie about what is done.

This lint closes that gap (operator directive 2026-07-14, "merged → complete").
The rule is evidence-based and mechanical: **a row whose Notes assert a clean
shipped-marker MUST NOT sit at `draft`.** The normal landing is `complete`, but
a deliberate later-lifecycle status the author chose (`active` for an anchor with
an ongoing arc, `review`/`accepted`/`scoping` for a decision still in motion) is
also fine — what a shipped row may never be is `draft`. Exempt: a *caveated*
shipped-marker (awaiting an operator decision, an in-progress `Stage N`, or
stacked on a still-open PR), and rows that make no shipped claim at all (older
foundation rows predating the convention).

So once an author writes "…shipped on branch." in a row and it lands on `main`,
CI requires the status cell to have advanced past `draft` — the index can no
longer freeze a merged SDD at draft.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX = REPO_ROOT / "docs" / "sdd" / "INDEX.md"

_ROW = re.compile(r"^\| (\d{3}) \|")
_SHIPPED = re.compile(r"shipped (on branch|this session)|✓ shipped")
# Caveats that mean "declared shipped, but genuinely not yet complete":
_CAVEAT = re.compile(r"awaiting|Stage \d|decision pending|open SDD-\d+ PR")


def _rows():
    for ln in INDEX.read_text(encoding="utf-8").splitlines():
        if not _ROW.match(ln):
            continue
        parts = ln.split("|")
        if len(parts) < 7:
            continue
        yield parts[1].strip(), parts[3].strip(), parts[5]  # num, status, notes


def test_shipped_rows_are_not_left_at_draft():
    offenders = []
    for num, status, notes in _rows():
        m = re.search(r"Status:\s*(.*)$", notes)
        clause = m.group(1).strip() if m else ""
        if _SHIPPED.search(clause) and not _CAVEAT.search(clause):
            if status == "draft":
                offenders.append((num, status, clause[:70]))
    assert not offenders, (
        "SDD INDEX rows that declare a clean shipped-marker but are still `draft` "
        "(a merged SDD must not sit stale as draft — flip the status cell to "
        "`complete`, or to a deliberate active/review/accepted if the arc is still "
        "in motion):\n"
        + "\n".join(f"  SDD-{n}: status={s!r} — {c}" for n, s, c in offenders)
    )


def test_status_vocabulary_is_valid():
    """Guard rail alongside SDD-961 hygiene — the status cell stays in the
    documented vocabulary (a typo'd status would slip a shipped row past the
    check above)."""
    allowed = {"draft", "review", "scoping", "accepted", "active", "complete",
               "draft (decision pending)"}
    bad = [(n, s) for n, s, _ in _rows() if s not in allowed]
    assert not bad, f"unknown SDD INDEX status words: {bad}"


def test_some_rows_are_complete():
    """A direct anti-freeze check: the audit found only 2/178 rows complete;
    after the merged→complete pass the index must reflect real completion."""
    n_complete = sum(1 for _, s, _ in _rows() if s == "complete")
    assert n_complete >= 40, (
        f"only {n_complete} INDEX rows are `complete` — the merged→complete "
        "hygiene pass (SDD-996) appears to have regressed"
    )
