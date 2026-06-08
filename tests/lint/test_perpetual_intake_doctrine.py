"""R326 (E9.M10) — SDD-033 perpetual-intake-doctrine L1 lint.

Pins the required sections of SDD-033 so a future edit that strips
a section fails at push-time. R320 (E9.M4) already pins the
cross-link preamble; this lint adds the per-section structure.

The doctrine itself is REVIEWABLE not RIGID — operator can edit
text inside any section. Only the section HEADERS are pinned.

If the operator deliberately renames or removes a section, they
update this lint in the same commit (forces conscious doctrine
evolution rather than silent drift).
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_PATH = REPO_ROOT / "docs" / "sdd" / "033-perpetual-intake-doctrine.md"

# Section headers that must appear in the doctrine, in order.
REQUIRED_SECTIONS = [
    "## Mission",
    "## The doctrine — five-step round template",
    "## Acceptance criteria for a round to count",
    "## Composition patterns shipped via this doctrine",
    "## Round-template scaffold for future authors",
    "## L1 lint enforcement",
    "## What this SDD does NOT do",
    "## Future-quarter SDD evolution",
]


def test_sdd_033_exists():
    """SDD-033 doctrine file must be present."""
    assert SDD_PATH.is_file(), f"missing {SDD_PATH}"


def test_sdd_033_has_required_sections():
    """All required sections must appear."""
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SECTIONS if s not in body]
    assert not missing, (
        f"SDD-033 missing required sections: {missing}.\n"
        "If you deliberately renamed or removed a section, update "
        "REQUIRED_SECTIONS in tests/lint/test_perpetual_intake_doctrine.py"
        " in the same commit."
    )


def test_sdd_033_sections_in_order():
    """Required sections must appear in declaration order."""
    body = SDD_PATH.read_text(encoding="utf-8")
    positions = []
    for s in REQUIRED_SECTIONS:
        if s in body:
            positions.append((s, body.index(s)))
    sorted_by_pos = sorted(positions, key=lambda x: x[1])
    actual_order = [s for s, _ in sorted_by_pos]
    assert actual_order == REQUIRED_SECTIONS, (
        f"sections out of order:\n  expected: {REQUIRED_SECTIONS}\n  "
        f"actual:   {actual_order}"
    )


def test_sdd_033_carries_cross_link_preamble():
    """R320 cross-link preamble (E<n>.M<n> in title OR Closes
    findings: line)."""
    body = SDD_PATH.read_text(encoding="utf-8")
    first_30 = "\n".join(body.splitlines()[:30])
    assert "E9.M10" in first_30 or "Closes findings:" in first_30, (
        "SDD-033 must carry E9.M10 cross-link in title OR a "
        "'Closes findings:' preamble per R320 (E9.M4) doctrine"
    )


def test_sdd_033_documents_triple_gate():
    """Apply-side doctrine: triple-gate pattern (R318) must be
    documented since it's required for any round that mutates."""
    body = SDD_PATH.read_text(encoding="utf-8")
    assert "Triple-gate" in body or "triple-gate" in body, (
        "SDD-033 must document the R318 triple-gate apply pattern"
    )
    assert "SOVEREIGN_OS_CONFIRM_DESTROY=YES" in body, (
        "SDD-033 must cite the env-var gate name explicitly"
    )


def test_sdd_033_documents_overlay_doctrine():
    """Overlay doctrine (R283 / SDD-030) cross-ref must be present."""
    body = SDD_PATH.read_text(encoding="utf-8")
    assert "R283" in body or "SDD-030" in body, (
        "SDD-033 must cross-ref R283 / SDD-030 operator-overlay-doctrine"
    )


def test_sdd_033_documents_composition_pattern():
    """The probe → advisor → rollup → meta composition chain must
    be illustrated so future authors see the shape."""
    body = SDD_PATH.read_text(encoding="utf-8")
    # Spot-check that at least one example chain is present.
    assert "R252" in body, "expected composition example with R252 power-status"
    assert "R322" in body, "expected composition example with R322 state-snapshot"


def test_sdd_033_documents_acceptance_criteria_checklist():
    """The acceptance-criteria checklist must use markdown checkbox
    syntax so it's operator-readable + linkable from PR bodies."""
    body = SDD_PATH.read_text(encoding="utf-8")
    assert "- [x]" in body, (
        "acceptance criteria must use [x] checkbox markdown"
    )
    # Mandatory items.
    for required in (
        "Verbatim §1b phrase",
        "Mandate row added",
        "Operator-runnable script",
        "L3 test",
        "Mandate row flipped",
    ):
        assert required in body, f"acceptance criteria missing: {required}"


# Five numbered subsections under "## The doctrine — five-step round template".
# Pinning these in declaration order guarantees a future edit that drops or
# reorders a step fails L1 lint (the doctrine names exactly five steps —
# dropping one silently is a regression).
REQUIRED_FIVE_STEPS = [
    "### 1. Locate the §1b verbatim phrase",
    "### 2. File a TODO mandate row",
    "### 3. Ship an operator-runnable verb",
    "### 4. Author an L3 test",
    "### 5. Flip the mandate row + commit",
]


def test_sdd_033_has_five_step_subsections():
    """All 5 numbered step subheaders must appear (in order)."""
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_FIVE_STEPS if s not in body]
    assert not missing, (
        f"SDD-033 missing five-step subheaders: {missing}.\n"
        "The doctrine is by name a FIVE-step round template — silently "
        "dropping or renaming a step is a regression. If renaming "
        "deliberately, update REQUIRED_FIVE_STEPS in the same commit."
    )
    # Order check.
    positions = [(s, body.index(s)) for s in REQUIRED_FIVE_STEPS]
    assert positions == sorted(positions, key=lambda x: x[1]), (
        f"five-step subheaders out of order: "
        f"{[s for s, _ in sorted(positions, key=lambda x: x[1])]}"
    )
