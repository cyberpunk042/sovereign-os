#!/usr/bin/env python3
"""
tests/lint/test_session_comms.py — functional test of the session communication
protocol (`scripts/git/session_comms.py`, SDD-981).

Loads the CLI module against a hermetic tmp board + registry and pins the
protocol contract: identity from the branch, addressed + broadcast delivery,
append-only union-safety, DERIVED answered-state, and threading.

Stdlib + pytest only.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[2] / "scripts" / "git" / "session_comms.py"

SESSIONS_MD = """# sessions
| session-id | band | e11 | branch | purpose | status |
|---|---|---|---|---|---|
| phase-1-audit | 950–999 | E11.M950–M999 | `claude/sovereign-os-audit-*` | audit | active |
| cockpit-wasm | 800–899 | E11.M800–M899 | `claude/*cockpit-wasm*` | bridge | active |
"""


def _load(tmp: Path, branch: str = "claude/sovereign-os-audit-x"):
    spec = importlib.util.spec_from_file_location("session_comms_uut", MODULE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sdd = tmp / "docs" / "sdd"
    sdd.mkdir(parents=True, exist_ok=True)
    (sdd / "SESSIONS.md").write_text(SESSIONS_MD)
    m.REPO = tmp
    m.SDD_DIR = sdd
    m.SESSIONS = sdd / "SESSIONS.md"
    m.BOARD = sdd / "MESSAGES.md"
    m._current_branch = lambda: branch  # deterministic identity
    return m


class _NS(dict):
    __getattr__ = dict.get


def test_whoami_resolves_from_branch(tmp_path):
    m = _load(tmp_path, branch="claude/sovereign-os-audit-tg0zyk")
    assert m.whoami() == "phase-1-audit"
    m2 = _load(tmp_path, branch="claude/feature-cockpit-wasm-1")
    assert m2.whoami() == "cockpit-wasm"
    m3 = _load(tmp_path, branch="claude/some-other")
    assert m3.whoami() == "unknown"


def test_post_and_inbox_direct_and_broadcast(tmp_path):
    m = _load(tmp_path)  # phase-1-audit
    m.cmd_post(_NS(to="cockpit-wasm", re="", subject="band", body="confirm 800-899", from_=None))
    m.cmd_post(_NS(to="all", re="", subject="live", body="resolver merged", from_=None))
    # cockpit sees BOTH (direct + broadcast), operator sees only the broadcast
    cockpit = m._addressed_to(m._load(), "cockpit-wasm")
    operator = m._addressed_to(m._load(), "operator")
    assert {x.subject for x in cockpit} == {"band", "live"}
    assert {x.subject for x in operator} == {"live"}


def test_answered_is_derived_from_replies(tmp_path):
    m = _load(tmp_path)
    m.cmd_post(_NS(to="cockpit-wasm", re="", subject="band", body="confirm", from_=None))
    msgs = m._load()
    band = next(x for x in msgs if x.subject == "band")
    # before any reply → open for cockpit
    assert not m._is_answered(msgs, band, "cockpit-wasm")
    # cockpit replies → answered for cockpit, still open for a bystander
    m.cmd_reply(_NS(id=band.id, to=None, subject=None, body="ok", from_="cockpit-wasm"))
    msgs = m._load()
    assert m._is_answered(msgs, band, "cockpit-wasm")
    assert not m._is_answered(msgs, band, "phase-1-audit")


def test_inbox_exit_code_signals_open(tmp_path):
    m = _load(tmp_path, branch="claude/feature-cockpit-wasm-1")  # whoami=cockpit-wasm
    # empty inbox → 0
    assert m.cmd_inbox(_NS(for_=None, all_=False)) == 0
    # a message addressed to cockpit → 1 (open)
    m.cmd_post(_NS(to="cockpit-wasm", re="", subject="hi", body="x", from_="phase-1-audit"))
    assert m.cmd_inbox(_NS(for_=None, all_=False)) == 1


def test_reply_to_unknown_id_errors(tmp_path):
    m = _load(tmp_path)
    with pytest.raises(SystemExit):
        m.cmd_reply(_NS(id="does-not-exist", to=None, subject=None, body="x", from_=None))


def test_unknown_recipient_rejected(tmp_path):
    m = _load(tmp_path)
    with pytest.raises(SystemExit):
        m.cmd_post(_NS(to="nobody", re="", subject="x", body="y", from_=None))


def test_pipes_and_newlines_survive_roundtrip(tmp_path):
    m = _load(tmp_path)
    body = "a | b\nc"  # pipe + newline would break the table if not escaped
    m.cmd_post(_NS(to="operator", re="", subject="s | t", body=body, from_=None))
    got = m._load()[0]
    assert got.subject == "s | t"
    assert "|" in got.body and got.body == "a | b / c"  # newline flattened, pipe kept


def test_thread_follows_reply_chain(tmp_path):
    m = _load(tmp_path)
    m.cmd_post(_NS(to="cockpit-wasm", re="", subject="root", body="1", from_=None))
    root = m._load()[0]
    m.cmd_reply(_NS(id=root.id, to=None, subject=None, body="2", from_="cockpit-wasm"))
    reply = next(x for x in m._load() if x.re == root.id)
    m.cmd_reply(_NS(id=reply.id, to=None, subject=None, body="3", from_="phase-1-audit"))
    by_id = {x.id: x for x in m._load()}
    # every message resolves back to the same root
    assert all(m._in_thread(x, root.id, by_id) for x in m._load())


def test_two_independent_appends_both_parse(tmp_path):
    """Union-merge safety proxy: two separate appends (as two branches would do)
    both end up as parseable rows — no coordination, no lost message."""
    m = _load(tmp_path)
    m.cmd_post(_NS(to="all", re="", subject="from-a", body="x", from_="phase-1-audit"))
    m.cmd_post(_NS(to="all", re="", subject="from-b", body="y", from_="cockpit-wasm"))
    subjects = {x.subject for x in m._load()}
    assert {"from-a", "from-b"} <= subjects
