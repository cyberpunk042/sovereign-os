"""R384 (E10.M28) — handoff INDEX consistency lint.

Mirrors tests/lint/test_sdd_index_consistency.py for the handoff
directory. Catches: handoff files authored without INDEX entry (next
session reading INDEX misses them) OR INDEX cites a file that doesn't
exist (dead link).

Same SDD-037 cross-validation pattern — bidirectional consistency.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HANDOFF_DIR = REPO_ROOT / "docs" / "handoff"
HANDOFF_INDEX = HANDOFF_DIR / "INDEX.md"


def _existing_handoff_files() -> set[str]:
    """Return set of NNN-slug.md basenames in docs/handoff/ (excluding INDEX.md)."""
    out: set[str] = set()
    for f in HANDOFF_DIR.glob("*.md"):
        if f.name == "INDEX.md":
            continue
        if re.match(r"^\d{3}-", f.name):
            out.add(f.name)
    return out


def _index_referenced_files() -> set[str]:
    """Extract NNN-slug.md filenames mentioned in INDEX.md markdown links."""
    if not HANDOFF_INDEX.is_file():
        return set()
    body = HANDOFF_INDEX.read_text(encoding="utf-8")
    # Match `[<text>](NNN-slug.md)` patterns
    return set(re.findall(r"\(([0-9]{3}-[\w-]+\.md)\)", body))


def test_handoff_dir_exists():
    assert HANDOFF_DIR.is_dir(), f"missing {HANDOFF_DIR}"


def test_handoff_index_exists():
    assert HANDOFF_INDEX.is_file(), f"missing {HANDOFF_INDEX}"


def test_every_handoff_file_in_index():
    """Every NNN-slug.md file in docs/handoff/ MUST be referenced
    from INDEX.md."""
    existing = _existing_handoff_files()
    referenced = _index_referenced_files()
    missing_from_index = existing - referenced
    assert not missing_from_index, (
        f"handoff files exist but not listed in INDEX.md: "
        f"{sorted(missing_from_index)}. Add an entry to INDEX.md."
    )


def test_every_index_entry_has_file():
    """Every NNN-slug.md referenced from INDEX.md MUST correspond to
    a real file."""
    existing = _existing_handoff_files()
    referenced = _index_referenced_files()
    dangling = referenced - existing
    assert not dangling, (
        f"INDEX.md references non-existent files: {sorted(dangling)}. "
        f"Either author the missing handoff OR fix INDEX.md."
    )


def test_handoff_006_present():
    """Sanity: R381 shipped 006-verbatim-preservation-arc.md — must
    be present + in INDEX."""
    existing = _existing_handoff_files()
    referenced = _index_referenced_files()
    assert "006-verbatim-preservation-arc.md" in existing, (
        "006-verbatim-preservation-arc.md missing from docs/handoff/"
    )
    assert "006-verbatim-preservation-arc.md" in referenced, (
        "006-verbatim-preservation-arc.md not referenced from INDEX.md"
    )


def test_handoff_numbering_sequence():
    """Handoff filenames should be NNN-prefix, sequentially numbered
    starting from 001. Gaps allowed (numbering may skip if a handoff
    is superseded + deleted)."""
    existing = _existing_handoff_files()
    nums = sorted(int(re.match(r"^(\d{3})-", f).group(1)) for f in existing)
    assert nums, "no numbered handoff files found"
    # No duplicate numbers
    assert len(nums) == len(set(nums)), (
        f"duplicate handoff numbers: {[n for n in nums if nums.count(n) > 1]}"
    )
    # Lowest is 001
    assert nums[0] == 1, (
        f"handoff sequence should start at 001; lowest is {nums[0]:03d}"
    )
