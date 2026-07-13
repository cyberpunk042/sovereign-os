"""Deferred-work register source-resolution contract (F-2026-037 / SDD-971).

`docs/review/phase-1/deferred-work-register.md` consolidates the ~10 deferred-work
items the docs already promise, each pointing at its authoritative source (an SDD, a
decisions/context doc). This lint keeps those pointers honest: every SDD number and
every doc path cited in the register must resolve to a file that exists — so the
register can't rot into dangling references as SDDs are renumbered or docs move.

It deliberately does NOT assert an item is still open — status reconciliation is
per-item operator / authoring-session work against the cited source (the register is
a pointer index, not a live status board).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = REPO_ROOT / "docs" / "review" / "phase-1" / "deferred-work-register.md"
SDD_DIR = REPO_ROOT / "docs" / "sdd"

# SDD-NNN references, and repo-relative doc paths in backticks (e.g. `docs/decisions.md`).
_SDD_RE = re.compile(r"\bSDD-(\d{3})\b")
_PATH_RE = re.compile(r"`((?:docs|context|scripts|tests|crates|config)[\w./-]*\.md)`|`(context\.md)`")


def test_register_exists():
    assert REGISTER.is_file(), f"missing deferred-work register {REGISTER} (SDD-971)"


def test_every_cited_sdd_resolves():
    body = REGISTER.read_text(encoding="utf-8")
    missing: list[str] = []
    for num in sorted(set(_SDD_RE.findall(body))):
        if not list(SDD_DIR.glob(f"{num}-*.md")):
            missing.append(f"SDD-{num}")
    assert not missing, (
        f"the register cites SDDs that don't exist under docs/sdd/: {missing} "
        "(fix the reference or the register is dangling)"
    )


def test_every_cited_doc_path_resolves():
    body = REGISTER.read_text(encoding="utf-8")
    missing: list[str] = []
    for m in _PATH_RE.finditer(body):
        rel = m.group(1) or m.group(2)
        # only check in-repo doc paths (skip this register's own name)
        if rel and rel != "docs/review/phase-1/deferred-work-register.md":
            if not (REPO_ROOT / rel).is_file():
                missing.append(rel)
    assert not missing, (
        f"the register cites doc paths that don't exist: {sorted(set(missing))}"
    )
