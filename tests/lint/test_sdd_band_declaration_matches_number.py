#!/usr/bin/env python3
"""
tests/lint/test_sdd_band_declaration_matches_number.py — the declared
`Number band:` of every SDD must actually contain that SDD's number (SDD-980).

Each banded SDD declares its session's band in its body:
`> Number band: **950–999 (phase-1 audit session)** …`. That declared range is
the file's AUTHORSHIP signal — which session wrote it — and the auto-resolver
(`scripts/git/sdd_conflict_resolver.py`) trusts it: on a duplicate number it
renumbers whichever file's declared band does NOT contain the number.

So a STALE declaration (a renumbered file still naming its old band) would
mis-route the resolver. This happened for real: SDD-800 (renumbered from a dup
974) kept declaring `950–999` in its body long after it moved to the 800 band.
This lint makes that class of drift impossible: if a file declares a band, that
band must contain its number. Files that declare no band (historical/pre-banding)
are skipped — the resolver treats those as "cannot attribute → warn", which is
the safe behaviour.

Stdlib + pytest only.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SDD_DIR = REPO / "docs" / "sdd"

_FILE_RE = re.compile(r"^(\d+)-")
_BAND_RE = re.compile(r"Number band:\s*\*\*(\d+)\s*[–-]\s*(\d+)")


def test_every_declared_band_contains_the_file_number():
    stale = []
    for p in sorted(SDD_DIR.glob("*.md")):
        m = _FILE_RE.match(p.name)
        if not m:
            continue
        n = int(m.group(1))
        bm = _BAND_RE.search(p.read_text(encoding="utf-8"))
        if not bm:
            continue  # no declaration → resolver warns (safe); not this lint's job
        lo, hi = int(bm.group(1)), int(bm.group(2))
        if not (lo <= n <= hi):
            stale.append(f"{p.name}: numbered {n} but declares band {lo}-{hi}")
    assert not stale, (
        "SDD files declare a band that does not contain their number "
        "(stale after a renumber?) — this misroutes the SDD-980 auto-resolver:\n  "
        + "\n  ".join(stale)
    )
