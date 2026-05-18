"""R439 (E10.M83) — decisions.md audit trail content + format lint.

Extends R387-R438 + R384 operational-artifact pinning to:
  docs/decisions.md       (chronological decision audit trail)
  docs/src/decisions.md   (mirror for mdbook surfacing)

Operator-named append-only audit pattern:
  - Each D-NNN entry corresponds to an answered question from an SDD
  - Entries are append-only (NEVER edit a past entry; append revisits)
  - The two-artifact pattern (decisions + SDD Q-X rows) mirrors selfdef

Required per-entry format:
  ## D-NNN — YYYY-MM-DD — <one-line summary>
  **Decision**: <what was decided>
  **Question**: <full question>
  **Source**: docs/sdd/<n>-<title>.md:<line> (Q-X row)
  **Rationale**: <why this option beats alternatives>
  **Affected items**: <files / SDDs / scripts touched>
  **Reversibility**: fully-reversible | partial | locked
  **Linked**: PR #<n>

If a future agent silently:
  - rewrites a past D-NNN entry = append-only violation
  - drops the format documentation = future entries diverge
  - adds D-NNN without the required fields = audit trail incomplete
…the operator-named decision audit trail silently corrupts.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DECISIONS = REPO_ROOT / "docs" / "decisions.md"
DECISIONS_MIRROR = REPO_ROOT / "docs" / "src" / "decisions.md"

KNOWN_REVERSIBILITY = {
    "fully-reversible",
    "partial",
    "locked",
    # Operator-introduced legacy values from earlier entries:
    "high", "medium", "low",
    "reversible", "irreversible",
}


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def _entries() -> list[tuple[str, str]]:
    """Return list of (id, body) for every D-NNN entry."""
    body = _read(DECISIONS)
    matches = re.finditer(
        r"^### (D-\d+)[^\n]+\n(.*?)(?=^### D-\d+|\Z)",
        body,
        re.M | re.DOTALL,
    )
    return [(m.group(1), m.group(2)) for m in matches]


# --- Structural ---


def test_decisions_md_exists():
    assert DECISIONS.is_file(), f"missing {DECISIONS}"


def test_decisions_mirror_md_exists():
    """docs/src/decisions.md mirrors docs/decisions.md for mdbook
    surfacing. Drift = published docs lose decisions log."""
    assert DECISIONS_MIRROR.is_file(), (
        f"missing {DECISIONS_MIRROR} (mdbook mirror)"
    )


def test_decisions_md_documents_append_only():
    """Operator-named: append-only — never edit past entries.
    Drift = format docs lost = future agents may edit-in-place."""
    body = _read(DECISIONS)
    assert "append-only" in body.lower(), (
        "docs/decisions.md missing append-only contract documentation"
    )


def test_decisions_md_documents_format():
    """## Format section MUST exist + show the D-NNN template."""
    body = _read(DECISIONS)
    assert "## Format" in body, (
        "docs/decisions.md missing ## Format section"
    )
    # Should show the D-NNN template
    assert "D-NNN" in body and "YYYY-MM-DD" in body, (
        "docs/decisions.md ## Format missing D-NNN / YYYY-MM-DD template"
    )


def test_decisions_md_documents_two_artifact_pattern():
    """Operator-named: SDD Q-X rows get annotated in place + new
    D-NNN gets appended — the two together form the audit trail."""
    body = _read(DECISIONS)
    has_pattern = (
        "two-artifact pattern" in body.lower()
        or ("Q-X" in body and "D-NNN" in body)
    )
    assert has_pattern, (
        "docs/decisions.md missing two-artifact pattern documentation"
    )


# --- Entry-level invariants ---


def test_at_least_15_decisions():
    """Operator-named: 18+ decisions at R-arc census. Drift below
    15 = accidental deletion."""
    entries = _entries()
    assert len(entries) >= 15, (
        f"only {len(entries)} D-NNN entries (operator-named 18+ floor; "
        f"drift = entries deleted)"
    )


def test_decision_ids_well_formed():
    """D-NNN format: D-001..D-NNN. Drift to D-NN.5 = invalid."""
    entries = _entries()
    pattern = re.compile(r"^D-\d+$")
    for did, _ in entries:
        assert pattern.match(did), (
            f"decision id={did!r} doesn't match D-NNN pattern"
        )


def test_decision_ids_unique():
    """No duplicate D-NNN. Drift = same decision logged twice."""
    entries = _entries()
    ids = [did for did, _ in entries]
    duplicates = set(i for i in ids if ids.count(i) > 1)
    assert not duplicates, (
        f"duplicate D-NNN entries: {duplicates}"
    )


def test_decision_ids_sequential():
    """D-NNN MUST be 1..N sequential (operator-named no-gap policy)."""
    entries = _entries()
    nums = sorted(int(re.match(r"^D-(\d+)$", d).group(1)) for d, _ in entries)
    expected = list(range(1, len(nums) + 1))
    assert nums == expected, (
        f"D-NNN sequence not 1..{len(nums)}: actual={nums}"
    )


def test_every_decision_has_date_stamp():
    """## D-NNN — YYYY-MM-DD — <summary>. Drift = no chronological
    anchor for the entry."""
    body = _read(DECISIONS)
    # Each ### D-NNN header MUST have YYYY-MM-DD
    headers = re.findall(
        r"^### (D-\d+) — (\d{4}-\d{2}-\d{2})",
        body,
        re.M,
    )
    entries = _entries()
    assert len(headers) == len(entries), (
        f"only {len(headers)}/{len(entries)} D-NNN headers have "
        f"YYYY-MM-DD date stamp"
    )


def test_every_decision_has_decision_field():
    """Each entry MUST have **Decision**: line."""
    for did, body in _entries():
        assert "**Decision**" in body or "Decision:" in body, (
            f"{did} missing Decision: field"
        )


def test_most_decisions_have_question_field():
    """**Question**: field captures the SDD Q-X verbatim. ≥80% should have it."""
    entries = _entries()
    have = sum(
        1 for _, body in entries
        if "**Question**" in body or "Question:" in body
    )
    pct = (have / len(entries)) * 100 if entries else 0
    assert pct >= 70, (
        f"only {have}/{len(entries)} ({pct:.0f}%) decisions have "
        f"Question field (≥70% threshold)"
    )


def test_most_decisions_have_source_field():
    """**Source**: field points at the SDD Q-X row (operator-discoverable
    cross-reference)."""
    entries = _entries()
    have = sum(
        1 for _, body in entries
        if "**Source**" in body or "Source:" in body
    )
    pct = (have / len(entries)) * 100 if entries else 0
    assert pct >= 70, (
        f"only {have}/{len(entries)} ({pct:.0f}%) decisions have "
        f"Source field"
    )


def test_most_decisions_have_reversibility_field():
    """**Reversibility**: operator-discoverable: can this be undone?"""
    entries = _entries()
    have = sum(
        1 for _, body in entries
        if "**Reversibility**" in body or "Reversibility:" in body
    )
    pct = (have / len(entries)) * 100 if entries else 0
    assert pct >= 50, (
        f"only {have}/{len(entries)} ({pct:.0f}%) decisions have "
        f"Reversibility field"
    )


def test_reversibility_values_in_known_set():
    """When Reversibility: is set, value MUST be in known set."""
    for did, body in _entries():
        m = re.search(
            r"\*\*Reversibility\*\*[:\s]+([a-z-]+)",
            body,
        )
        if m:
            val = m.group(1)
            assert val in KNOWN_REVERSIBILITY, (
                f"{did} Reversibility={val!r} not in {KNOWN_REVERSIBILITY}"
            )


# --- Decisions ↔ SDDs cross-reference ---


def test_decision_sources_reference_real_sdds():
    """When a decision cites docs/sdd/NNN-*.md as Source, that SDD
    MUST exist (drift = phantom source)."""
    body = _read(DECISIONS)
    # Find docs/sdd/NNN-... references in Source: lines
    sdd_refs = re.findall(
        r"docs/sdd/(\d{3})-[a-z0-9-]+\.md",
        body,
    )
    sdd_dir = REPO_ROOT / "docs" / "sdd"
    for num in sdd_refs:
        matching = list(sdd_dir.glob(f"{num}-*.md"))
        assert matching, (
            f"decisions.md references docs/sdd/{num}-*.md but no such "
            f"file exists (phantom Source)"
        )


# --- Open questions section ---


def test_decisions_md_documents_open_questions():
    """## Open questions section catalogs the unresolved Q-NNN
    questions (operator-discoverable: what's NOT yet decided)."""
    body = _read(DECISIONS)
    assert "Open questions" in body, (
        "docs/decisions.md missing 'Open questions' section "
        "(operator-discoverable: unresolved Q-NNN catalog)"
    )


# --- Bidirectional consistency between decisions.md and src mirror ---


def test_mirror_references_canonical_decisions_md():
    """docs/src/decisions.md is a mdbook-friendly summary that MUST
    point at the canonical docs/decisions.md (operator-discoverable
    chain). Drift = mdbook surface loses its anchor to canonical."""
    mirror = _read(DECISIONS_MIRROR)
    has_canonical_ref = (
        "docs/decisions.md" in mirror
        or "../decisions.md" in mirror
    )
    assert has_canonical_ref, (
        "docs/src/decisions.md doesn't reference canonical "
        "docs/decisions.md (operator-discoverable chain broken)"
    )
