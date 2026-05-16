"""Layer 1 — SDD INDEX consistency. Every SDD file referenced exists;
every SDD file in docs/sdd/ is in INDEX."""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SDD_DIR = REPO_ROOT / "docs" / "sdd"
INDEX = SDD_DIR / "INDEX.md"


def test_index_exists():
    assert INDEX.exists()


def test_every_sdd_file_in_index():
    """For each docs/sdd/NNN-*.md (except INDEX.md), expect a row in INDEX.md."""
    index_text = INDEX.read_text()
    sdd_files = sorted(p for p in SDD_DIR.glob("[0-9][0-9][0-9]-*.md"))
    assert sdd_files, "no SDD files found"
    for sdd in sdd_files:
        num = sdd.name[:3]
        # Expect '| NNN |' in the table
        assert re.search(rf"^\|\s*{num}\s*\|", index_text, re.M), (
            f"SDD {sdd.name} is missing from docs/sdd/INDEX.md"
        )


def test_every_index_row_has_file():
    """For each | NNN | row in INDEX.md, expect a matching docs/sdd/NNN-*.md."""
    index_text = INDEX.read_text()
    nums = re.findall(r"^\|\s*(\d{3})\s*\|", index_text, re.M)
    for num in nums:
        matching = list(SDD_DIR.glob(f"{num}-*.md"))
        assert matching, f"INDEX row for {num} has no matching docs/sdd/{num}-*.md"
