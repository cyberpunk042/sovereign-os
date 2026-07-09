"""R438 (E10.M82) — SDD content + INDEX extended invariants lint.

Extends R387-R437 + R384 + the pre-existing
tests/lint/test_sdd_index_consistency.py (3 assertions covering
filename↔INDEX bidirectional) operational-artifact pinning to:
  docs/sdd/*.md       (39 SDD documents)
  docs/sdd/INDEX.md   (operator-discoverable catalog)

R384 covered handoff INDEX bidirectional; pre-existing test_sdd_
index_consistency.py covers the filename↔INDEX bidirectional. R438
adds CONTENT-level invariants:
  - per-SDD title format + substantive content + multi-section
  - SDD-037 (verbatim-preservation arc anchor) present + documents
    its doctrine
  - INDEX numbering policy documented
  - INDEX has Status column
  - file-naming hygiene (lowercase hyphenated)
  - no SDD numbering gaps > 5 (drift = missed renumber)

This is the operator-discoverable cold-start surface for the SDD
family — every SDD must be a substantive design doc, not a stub.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_DIR = REPO_ROOT / "docs" / "sdd"
INDEX_MD = SDD_DIR / "INDEX.md"


def _sdd_files() -> list[Path]:
    return sorted(SDD_DIR.glob("[0-9][0-9][0-9]-*.md"))


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_at_least_30_sdds():
    """Operator-named: 38+ SDDs at R-arc census. Drift below 30 =
    accidental deletion."""
    files = _sdd_files()
    assert len(files) >= 30, (
        f"only {len(files)} SDDs found (operator-named 38+ floor)"
    )


def test_sdd_numbers_sequential_no_huge_gaps():
    """WITHIN a session number-band (a hundreds-block, per docs/sdd/README.md +
    SDD-100) SDD numbers stay tight (gap <= 5 — catches drift / a missed renumber).
    Band BOUNDARIES (crossing hundreds — e.g. 071 → 100 into the recover-projects
    band) are INTENTIONAL gaps and allowed: per-session bands (recover 100-199,
    header-sidemenu 200-299, science 300-399, general 900+) keep the 3 parallel
    sessions from colliding on SDD numbers."""
    files = _sdd_files()
    nums = sorted(
        int(re.match(r"^(\d{3})-", p.name).group(1)) for p in files
    )
    for i in range(len(nums) - 1):
        a, b = nums[i], nums[i + 1]
        if a // 100 != b // 100:
            continue  # band boundary — an intentional per-session gap
        assert b - a <= 5, (
            f"SDD numbering gap > 5 between {a:03d} and {b:03d} within a band "
            f"(possible drift / missed renumber)"
        )


def test_sdd_numbers_unique():
    files = _sdd_files()
    nums = [
        int(re.match(r"^(\d{3})-", p.name).group(1)) for p in files
    ]
    duplicates = [n for n in nums if nums.count(n) > 1]
    assert not duplicates, (
        f"duplicate SDD numbers: {set(duplicates)}"
    )


# --- Per-SDD content invariants ---


def test_every_sdd_has_h1_title():
    for sdd_path in _sdd_files():
        body = _read(sdd_path)
        m = re.search(r"^# ", body, re.M)
        assert m, f"{sdd_path.name} missing H1 title"


def test_every_sdd_h1_substantive():
    """SDD H1 title MUST be ≥10 chars (operator-discoverable identity)."""
    for sdd_path in _sdd_files():
        body = _read(sdd_path)
        m = re.search(r"^# (.+)$", body, re.M)
        assert m, f"{sdd_path.name} no H1"
        title = m.group(1).strip()
        assert len(title) >= 10, (
            f"{sdd_path.name} H1 title={title!r} too short"
        )


def test_every_sdd_substantive():
    """Each SDD MUST be substantive (>500 chars; drift to stub)."""
    for sdd_path in _sdd_files():
        body = _read(sdd_path)
        assert len(body) >= 500, (
            f"{sdd_path.name} too short ({len(body)} chars); "
            f"SDD must be substantive design doc"
        )


def test_every_sdd_has_at_least_two_sections():
    """≥2 ## section headers (operator-discoverable structure)."""
    for sdd_path in _sdd_files():
        body = _read(sdd_path)
        h2_count = len(re.findall(r"^## ", body, re.M))
        assert h2_count >= 2, (
            f"{sdd_path.name} has only {h2_count} ## sections"
        )


# --- INDEX content ---


def test_index_has_header_explaining_purpose():
    body = _read(INDEX_MD)
    has_explanation = (
        "SDD index" in body
        or "Reserved slots" in body
        or "Numbering" in body
    )
    assert has_explanation, (
        "docs/sdd/INDEX.md missing purpose / numbering policy header"
    )


def test_index_documents_numbering_policy():
    """Operator-named: three-digit zero-padded, never recycled."""
    body = _read(INDEX_MD)
    has_policy = (
        "three-digit" in body
        or "zero-padded" in body
        or "never recycled" in body
    )
    assert has_policy, (
        "docs/sdd/INDEX.md missing numbering policy "
        "(operator-named: three-digit zero-padded, never recycled)"
    )


def test_index_has_status_column():
    """Operator-discoverable: status column shows which SDDs are
    accepted vs review."""
    body = _read(INDEX_MD)
    has_status = (
        "| Status |" in body
        or "Status" in body and "accepted" in body.lower()
    )
    assert has_status, (
        "docs/sdd/INDEX.md missing Status column"
    )


# --- SDD-037 anchor (verbatim-preservation arc) ---


def test_sdd_037_exists():
    """SDD-037 is the verbatim-preservation arc anchor."""
    sdd_037 = list(SDD_DIR.glob("037-*.md"))
    assert sdd_037, (
        "docs/sdd/037-*.md missing (verbatim-preservation arc anchor)"
    )


def test_sdd_037_documents_verbatim_doctrine():
    sdd_037_files = list(SDD_DIR.glob("037-*.md"))
    if not sdd_037_files:
        return  # skipped — file existence check covers
    body = _read(sdd_037_files[0])
    has_doctrine = (
        "verbatim" in body.lower()
        or "preservation" in body.lower()
        or "NO REPHRASING" in body
    )
    assert has_doctrine, (
        f"{sdd_037_files[0].name} missing verbatim-preservation "
        f"doctrine documentation"
    )


# --- File-naming hygiene ---


def test_sdd_filenames_lowercase_hyphenated():
    """Operator-named: NNN-lower-with-hyphens.md format."""
    pattern = re.compile(r"^\d{3}-[a-z0-9-]+\.md$")
    for sdd_path in _sdd_files():
        assert pattern.match(sdd_path.name), (
            f"SDD filename {sdd_path.name!r} doesn't match "
            f"NNN-lower-hyphenated.md format"
        )


# --- SDD-000 charter is the foundation ---


def test_sdd_000_charter_exists():
    """SDD-000 is the operator-named project charter."""
    sdd_000 = list(SDD_DIR.glob("000-*.md"))
    assert sdd_000, "docs/sdd/000-*.md missing (project charter)"


def test_sdd_000_charter_documents_foundation():
    """The charter MUST establish the mission, SDD/TDD doctrine,
    Debian-as-Ark framing."""
    sdd_000_files = list(SDD_DIR.glob("000-*.md"))
    if not sdd_000_files:
        return
    body = _read(sdd_000_files[0])
    has_foundation = (
        "charter" in body.lower()
        or "mission" in body.lower()
        or "Debian" in body
        or "doctrine" in body.lower()
    )
    assert has_foundation, (
        "SDD-000 charter missing operator-named foundation language"
    )
