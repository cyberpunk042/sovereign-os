"""Unit tests for the SDD-052 memory-change WRITE surface
`scripts/intelligence/memory-decide.py`: approve / reject sign-off on the M028
Memory OS `pending` queue + the `request` producer.

Covers the security-critical core: approve applies promote/pin (removes from the
queue), a pending `forget` is REFUSED (Stage 3 refuse-by-default), reject
discards, `_SAFE_ID` validation, DRY-RUN default (no state mutation without
--confirm), atomic write + history + `unsigned-pending-MS003` signature.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "scripts" / "intelligence" / "memory-decide.py"


def _load():
    spec = importlib.util.spec_from_file_location("memory_decide", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MD = _load()


@pytest.fixture()
def state(tmp_path, monkeypatch):
    """A crafted memory state with a pending promote / pin / forget."""
    st = tmp_path / "memory.json"
    st.write_text(json.dumps({"pending": [
        {"id": "mc-001", "op": "promote", "mtype": "semantic"},
        {"id": "mc-002", "op": "pin", "mtype": "episodic"},
        {"id": "mc-003", "op": "forget", "mtype": "working"},
    ]}))
    monkeypatch.setattr(MD, "MEMORY_STATE", st)
    monkeypatch.setattr(MD._core, "MEMORY_STATE", st)
    monkeypatch.setattr(MD, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(MD, "SPAN_STORE", tmp_path / "spans.jsonl")
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return st


# ── approve (applies promote/pin; refuses forget) ─────────────────────────────

def test_approve_promote_dry(state):
    r = MD.decide("mc-001", "approve")  # no --confirm → dry
    assert r["ok"] is True and r["dry_run"] is True
    assert r["op"] == "promote" and r["would"]["action"] == "apply promote"


def test_approve_pin_dry(state):
    r = MD.decide("mc-002", "approve")
    assert r["ok"] is True and r["op"] == "pin"


def test_approve_forget_refused(state):
    r = MD.decide("mc-003", "approve", confirm=True)
    assert r["ok"] is False and r["code"] == 2 and r["op"] == "forget"
    assert "forget is not wired yet" in r["error"] and "--force" in r["error"]
    # the pending forget must still be in the queue (not applied, not removed)
    assert "mc-003" in {p["id"] for p in json.loads(state.read_text())["pending"]}


def test_approve_promote_live_removes_and_records(state):
    r = MD.decide("mc-001", "approve", confirm=True)
    assert r["ok"] is True and r["applied"] is True
    assert r["signature"] == "unsigned-pending-MS003"
    st = json.loads(state.read_text())
    assert "mc-001" not in {p["id"] for p in st["pending"]}
    assert st["history"][0]["action"] == "approve" and st["history"][0]["change_id"] == "mc-001"
    assert st["history"][0]["op"] == "promote"


# ── reject (discards) ─────────────────────────────────────────────────────────

def test_reject_dry(state):
    r = MD.decide("mc-002", "reject")
    assert r["ok"] is True and r["would"]["action"] == "discard"


def test_reject_live_discards(state):
    r = MD.decide("mc-002", "reject", confirm=True)
    assert r["ok"] is True and r["applied"] is False
    assert "mc-002" not in {p["id"] for p in json.loads(state.read_text())["pending"]}


def test_reject_forget_allowed(state):
    # reject of a pending forget is fine (discarding, not deleting memory)
    r = MD.decide("mc-003", "reject", confirm=True)
    assert r["ok"] is True
    assert "mc-003" not in {p["id"] for p in json.loads(state.read_text())["pending"]}


# ── id / verb validation ──────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["a/b", "a b", "$(id)", "../x", ""])
def test_unsafe_id_rejected(state, bad):
    r = MD.decide(bad, "approve")
    assert r["ok"] is False and "unsafe change id" in r["error"]


def test_unknown_id_rejected(state):
    r = MD.decide("mc-999", "approve")
    assert r["ok"] is False and "no pending change resolved" in r["error"]


def test_unknown_verb_rejected(state):
    r = MD.decide("mc-001", "explode")
    assert r["ok"] is False and "unknown verb" in r["error"]


def test_confirm_still_dry_under_env(state, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_DRY_RUN", "1")
    r = MD.decide("mc-001", "approve", confirm=True)
    assert r["dry_run"] is True
    assert "mc-001" in {p["id"] for p in json.loads(state.read_text())["pending"]}


# ── request producer + audit trail ────────────────────────────────────────────

def test_request_mints_pending(state):
    r = MD.request("pin", mtype="value")
    assert r["ok"] is True and r["id"].startswith("mc-") and r["status"] == "pending"
    ids = {p["id"] for p in json.loads(state.read_text())["pending"]}
    assert r["id"] in ids


def test_request_rejects_bad_op(state):
    assert MD.request("obliterate")["ok"] is False


def test_live_decision_appends_ledger_and_span(state):
    MD.decide("mc-001", "approve", confirm=True)
    ledger = json.loads(MD.LEDGER.read_text().strip())
    assert ledger["verb"] == "approve" and ledger["id"] == "mc-001"
    span = json.loads(MD.SPAN_STORE.read_text().strip())
    assert span["ocsf_class"] == "5001" and span["operation"] == "memory_decision"
    assert span["attributes"]["change_id"] == "mc-001"
