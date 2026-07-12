#!/usr/bin/env python3
"""
tests/lint/test_sdd_numbers_unique.py — SDD/mandate number uniqueness (SDD-100).

The parallel-session band scheme (SDD-100) exists so two sessions never claim the
same SDD number. But nothing ENFORCED it — SDD-206 was taken by BOTH the gateway
safety spine and (briefly) the compute plane before this lint. This closes that
gap: SDD file numbers, `docs/sdd/INDEX.md` rows, and the mandate's `E11.M###` row
headers must each be unique. A collision fails here, not silently on merge.

Stdlib + pytest only.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SDD_DIR = REPO / "docs" / "sdd"
INDEX = SDD_DIR / "INDEX.md"
MANDATE = REPO / "docs" / "standing-directives" / "2026-05-17-operator-mandate.md"


def _dups(numbers) -> list:
    return sorted(n for n, c in Counter(numbers).items() if c > 1)


def test_sdd_file_numbers_are_unique():
    # every docs/sdd/NNN-*.md must carry a distinct NNN
    nums = [m.group(1) for f in SDD_DIR.glob("*.md")
            if (m := re.match(r"^(\d+)-", f.name))]
    assert nums, "no numbered SDD files found"
    assert not _dups(nums), f"duplicate SDD file numbers: {_dups(nums)}"


def test_index_rows_are_unique():
    nums = re.findall(r"^\| (\d+) \|", INDEX.read_text(encoding="utf-8"), re.MULTILINE)
    assert not _dups(nums), f"duplicate SDD-INDEX rows: {_dups(nums)}"


def test_mandate_row_headers_are_unique():
    # only ROW HEADERS (^| E11.M### |), not numbers referenced in prose
    heads = re.findall(r"^\| E11\.M(\d+) \|", MANDATE.read_text(encoding="utf-8"), re.MULTILINE)
    assert heads, "no E11.M### mandate rows found"
    assert not _dups(heads), f"duplicate mandate E11.M### rows: {_dups(heads)}"


def test_every_sdd_file_has_an_index_row():
    files = {m.group(1) for f in SDD_DIR.glob("*.md")
             if (m := re.match(r"^(\d+)-", f.name))}
    index_nums = set(re.findall(r"^\| (\d+) \|", INDEX.read_text(encoding="utf-8"), re.MULTILINE))
    missing = sorted(files - index_nums, key=int)
    assert not missing, f"SDD files with no INDEX row: {missing}"
