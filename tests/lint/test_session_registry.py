#!/usr/bin/env python3
"""
tests/lint/test_session_registry.py — the parallel-session registry
(`docs/sdd/SESSIONS.md`) is the authoritative session→band map (SDD-980).

SDD-100 gives each parallel session a disjoint number band; SESSIONS.md makes
that map machine-readable so a session can identify itself and the auto-resolver
can attribute any number to a session. This lint enforces the registry's
integrity so the resolver can trust it:

  1. registered bands are well-formed (lo ≤ hi) and pairwise DISJOINT;
  2. every numbered SDD file's number falls inside exactly one registered band;
  3. every SDD's declared `Number band:` matches a registered session band
     (so a file's authorship signal always maps to a real session).

Stdlib + pytest only.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SDD_DIR = REPO / "docs" / "sdd"
SESSIONS = SDD_DIR / "SESSIONS.md"

_ROW_RE = re.compile(r"^\|\s*([a-z0-9-]+)\s*\|\s*(\d+)\s*[–-]\s*(\d+)\s*\|", re.M)
_FILE_RE = re.compile(r"^(\d+)-")
_BAND_RE = re.compile(r"Number band:\s*\*\*(\d+)\s*[–-]\s*(\d+)")


def _registry() -> dict[str, tuple[int, int]]:
    assert SESSIONS.is_file(), "docs/sdd/SESSIONS.md missing (the session registry, SDD-980)"
    reg = {m.group(1): (int(m.group(2)), int(m.group(3)))
           for m in _ROW_RE.finditer(SESSIONS.read_text(encoding="utf-8"))}
    assert reg, "SESSIONS.md declares no session rows"
    return reg


def test_registered_bands_wellformed_and_disjoint():
    reg = _registry()
    for sid, (lo, hi) in reg.items():
        assert lo <= hi, f"session {sid}: band {lo}-{hi} is inverted"
    items = list(reg.items())
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (a, (alo, ahi)), (b, (blo, bhi)) = items[i], items[j]
            assert ahi < blo or bhi < alo, (
                f"session bands overlap: {a} {alo}-{ahi} vs {b} {blo}-{bhi}"
            )


def test_every_sdd_number_falls_in_a_registered_band():
    reg = _registry()
    bands = list(reg.values())
    orphan = []
    for p in sorted(SDD_DIR.glob("*.md")):
        m = _FILE_RE.match(p.name)
        if not m:
            continue
        n = int(m.group(1))
        # historical pre-banding numbers (064–071) predate the scheme; the
        # registry starts at 100, so anything below the lowest band is exempt.
        if n < min(lo for lo, _ in bands):
            continue
        if not any(lo <= n <= hi for lo, hi in bands):
            orphan.append(f"{p.name} (number {n})")
    assert not orphan, (
        "SDD files whose number is in no registered session band "
        "(add the session row to SESSIONS.md, or renumber into a band):\n  "
        + "\n  ".join(orphan)
    )


def test_declared_bands_match_a_registered_session_band():
    reg = _registry()
    registered = set(reg.values())
    mismatched = []
    for p in sorted(SDD_DIR.glob("*.md")):
        if not _FILE_RE.match(p.name):
            continue
        bm = _BAND_RE.search(p.read_text(encoding="utf-8"))
        if not bm:
            continue
        band = (int(bm.group(1)), int(bm.group(2)))
        if band not in registered:
            mismatched.append(f"{p.name} declares {band[0]}-{band[1]}")
    assert not mismatched, (
        "SDD files declare a band that no session in SESSIONS.md owns "
        "(register the session, or fix the declaration):\n  "
        + "\n  ".join(mismatched)
    )
