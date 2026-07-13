"""SDD INDEX status/provenance hygiene lint (F-2026-031 / SDD-961).

`docs/sdd/INDEX.md` had collapsed hygiene: 71 rows carried a stale ephemeral
feature-branch reference (``SDD-NNN on branch `claude/recover-projects-b0oT6` ``)
for a session whose work had long since merged, and the Status column had drifted
into an undocumented, inconsistent vocabulary.

A durable catalog must not reference ephemeral branches (a merged branch name is
stale the moment it merges), and its status words must come from a defined set.
This lint pins both:

  1. no INDEX row references a `claude/<slug>` feature branch;
  2. every data row's Status column base word is in the documented vocabulary
     (see the INDEX header legend).

The mass status-reconciliation the finding also mentions (flipping merged SDDs
from `draft` to `accepted`/`complete`) is a per-SDD judgement left to the
authoring session / operator — this lint enforces only the objective floor.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX = REPO_ROOT / "docs" / "sdd" / "INDEX.md"

# The documented Status vocabulary (INDEX header legend). Base word only; an
# optional parenthetical qualifier (e.g. "draft (decision pending)") is allowed.
_ALLOWED_STATUS = {"draft", "review", "scoping", "accepted", "active", "complete"}

# A data row: | NNN | Title | Status | PR | Notes ... |
_ROW = re.compile(r"^\|\s*(\d{3})\s*\|[^|]*\|\s*([^|]+?)\s*\|", re.M)


def _body() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_no_feature_branch_references():
    hits = sorted(set(re.findall(r"claude/[a-z0-9]+(?:-[a-z0-9]+)*-[A-Za-z0-9]{5,}", _body())))
    assert not hits, (
        f"docs/sdd/INDEX.md references ephemeral feature branches {hits} — a "
        f"merged branch is stale in a durable catalog. Name the authoring session "
        f"instead (e.g. '(recover-projects session)')."
    )


def test_no_on_branch_phrase():
    assert "on branch `claude/" not in _body(), (
        "docs/sdd/INDEX.md still has an 'on branch `claude/...`' provenance — drop "
        "the ephemeral branch, keep the session name."
    )


def test_status_column_uses_the_documented_vocabulary():
    bad = []
    for num, status in _ROW.findall(_body()):
        base = status.split("(")[0].strip().lower()
        if base not in _ALLOWED_STATUS:
            bad.append(f"SDD-{num}: {status!r}")
    assert not bad, (
        f"docs/sdd/INDEX.md Status column has words outside the documented "
        f"vocabulary {sorted(_ALLOWED_STATUS)}: {bad}. Update the row or extend "
        f"the legend + this lint."
    )


def test_legend_documents_the_vocabulary():
    body = _body().lower()
    assert "status vocabulary" in body, "INDEX header missing the Status vocabulary legend"
    for word in _ALLOWED_STATUS:
        assert f"`{word}`" in body, f"INDEX legend does not document status {word!r}"
