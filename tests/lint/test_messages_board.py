#!/usr/bin/env python3
"""
tests/lint/test_messages_board.py — integrity of the session message board
(`docs/sdd/MESSAGES.md`, SDD-981).

Keeps the append-only board well-formed so tooling can always parse it and no
message is silently addressed to a non-existent session:

  1. the board exists with its 7-column header;
  2. every data row has all 7 cells;
  3. every `from` / `to` is a registered session-id (SESSIONS.md), `operator`,
     or `all` (`to` only);
  4. every non-empty `re` references an existing msg-id;
  5. msg-ids are unique.

Stdlib + pytest only.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SDD_DIR = REPO / "docs" / "sdd"
BOARD = SDD_DIR / "MESSAGES.md"
SESSIONS = SDD_DIR / "SESSIONS.md"

_SESSION_RE = re.compile(r"^\|\s*([a-z0-9-]+)\s*\|\s*\d+\s*[–-]\s*\d+\s*\|", re.M)
_ROW_RE = re.compile(r"^\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|"
                     r"\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*(.*?)\s*\|\s*$")


def _sessions() -> set[str]:
    return set(_SESSION_RE.findall(SESSIONS.read_text(encoding="utf-8")))


def _rows() -> list[list[str]]:
    rows = []
    for line in BOARD.read_text(encoding="utf-8").splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.groups()]
        if cells[0] in ("msg-id",) or set(cells[0]) <= {"-"}:
            continue
        rows.append(cells)
    return rows


def test_board_exists_with_header():
    assert BOARD.is_file(), "docs/sdd/MESSAGES.md missing (the session board, SDD-981)"
    text = BOARD.read_text(encoding="utf-8")
    assert "| msg-id | utc | from | to | re | subject | body |" in text, \
        "MESSAGES.md missing its 7-column header row"


def test_every_from_and_to_is_valid():
    sessions = _sessions()
    senders = sessions | {"operator"}
    recipients = sessions | {"operator", "all"}
    bad = []
    for r in _rows():
        _id, _utc, frm, to = r[0], r[1], r[2], r[3]
        if frm not in senders:
            bad.append(f"{_id}: from '{frm}' is not a registered session/operator")
        if to not in recipients:
            bad.append(f"{_id}: to '{to}' is not a registered session/operator/all")
    assert not bad, "MESSAGES.md rows address unknown parties:\n  " + "\n  ".join(bad)


def test_re_references_resolve_and_ids_unique():
    rows = _rows()
    ids = [r[0] for r in rows]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    assert not dups, f"duplicate msg-ids in MESSAGES.md: {dups}"
    idset = set(ids)
    dangling = [f"{r[0]} → re {r[4]}" for r in rows if r[4] and r[4] not in idset]
    assert not dangling, "MESSAGES.md rows reply to a non-existent msg-id:\n  " + "\n  ".join(dangling)
