"""Cross-repo SDD reference integrity — info-hub runbooks reference
selfdef SDDs by number; those SDDs must exist on selfdef side.

The info-hub wiki/runbooks/*.md files cite specific selfdef SDD
numbers (SDD-018 / SDD-026 / SDD-027 / SDD-028 / SDD-029 / SDD-030
/ SDD-031 / SDD-061 / SDD-062 / SDD-063 as of this audit) for
operator context. A silent rename or deletion of any selfdef SDD
breaks the operator's deep-link from the runbook with no detection
until the operator clicks through.

This sister-gate to test_cross_repo_selfdef_doc_references.py
covers the OTHER direction: that gate ensures sovereign-os docs
referencing selfdef files resolve; this one ensures info-hub
runbooks referencing selfdef SDD numbers resolve.

Selfdef ↔ info-hub adjacency required: SKIPs cleanly when info-hub
not adjacent (env var SOVEREIGN_OS_INFOHUB_REPO overrides default).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

SELFDEF_REPO_DEFAULT = REPO_ROOT.parent / "selfdef"
SELFDEF_REPO = Path(os.environ.get("SOVEREIGN_OS_SELFDEF_REPO", str(SELFDEF_REPO_DEFAULT)))

INFOHUB_REPO_DEFAULT = REPO_ROOT.parent / "devops-solutions-information-hub"
INFOHUB_REPO = Path(os.environ.get("SOVEREIGN_OS_INFOHUB_REPO", str(INFOHUB_REPO_DEFAULT)))

RUNBOOKS_DIR = INFOHUB_REPO / "wiki" / "runbooks"
SELFDEF_SDD_DIR = SELFDEF_REPO / "docs" / "sdd"

SDD_RE = re.compile(r"\bSDD-(\d{3})\b")


def _infohub_sdd_refs() -> dict[str, set[str]]:
    """For each runbook .md, the set of SDD-NNN numbers it cites."""
    out: dict[str, set[str]] = {}
    if not RUNBOOKS_DIR.is_dir():
        return out
    for md in sorted(RUNBOOKS_DIR.glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        refs = {m.group(0) for m in SDD_RE.finditer(text)}
        if refs:
            out[md.name] = refs
    return out


def _selfdef_sdd_numbers() -> set[str]:
    """Every SDD-NNN that has a docs/sdd/NNN-*.md file on selfdef side."""
    if not SELFDEF_SDD_DIR.is_dir():
        return set()
    out: set[str] = set()
    for md in SELFDEF_SDD_DIR.glob("*.md"):
        name = md.name
        if len(name) >= 3 and name[:3].isdigit():
            out.add(f"SDD-{name[:3]}")
    return out


@pytest.mark.skipif(
    not RUNBOOKS_DIR.is_dir() or not SELFDEF_SDD_DIR.is_dir(),
    reason=f"info-hub ({INFOHUB_REPO}) or selfdef SDD dir not adjacent",
)
def test_at_least_some_sdd_refs_present():
    """Sanity check the regex catches some references."""
    refs = _infohub_sdd_refs()
    assert refs, f"no SDD-NNN refs found under {RUNBOOKS_DIR}"


@pytest.mark.skipif(
    not RUNBOOKS_DIR.is_dir() or not SELFDEF_SDD_DIR.is_dir(),
    reason=f"info-hub ({INFOHUB_REPO}) or selfdef SDD dir not adjacent",
)
def test_every_infohub_sdd_ref_resolves_on_selfdef_side():
    """Every SDD-NNN cited from any info-hub runbook must have a real
    docs/sdd/NNN-*.md file on selfdef side. A silent rename / deletion
    on selfdef breaks the operator's runbook deep-link."""
    runbook_refs = _infohub_sdd_refs()
    selfdef_sdds = _selfdef_sdd_numbers()
    broken: list[tuple[str, str]] = []
    for runbook, refs in runbook_refs.items():
        for ref in sorted(refs):
            if ref not in selfdef_sdds:
                broken.append((runbook, ref))
    assert not broken, (
        f"info-hub runbooks reference selfdef SDDs that do not exist on "
        f"selfdef side (broken cross-repo deep-links): {broken}"
    )


@pytest.mark.skipif(
    not SELFDEF_SDD_DIR.is_dir(),
    reason=f"selfdef SDD dir not adjacent at {SELFDEF_SDD_DIR}",
)
def test_selfdef_has_at_least_one_sdd():
    """Sanity check that we can actually enumerate selfdef SDDs."""
    sdds = _selfdef_sdd_numbers()
    assert len(sdds) > 0, (
        f"no docs/sdd/NNN-*.md files found at {SELFDEF_SDD_DIR}"
    )
