"""Unit tests for the SDD-053 session-lifecycle WRITE surface
`scripts/lifecycle/session-decide.py`: hibernate / resume / kill (+ hibernate-all).

Covers the security-critical core: the M057 state-machine guards (hibernate←active,
resume←hibernated, kill refused on terminals; kill→archived), `_SAFE_ID`
validation, DRY-RUN default (no registry mutation without --confirm), atomic write
+ `unsigned-pending-MS003` signature, and the bulk hibernate-all.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "scripts" / "lifecycle" / "session-decide.py"


def _load():
    spec = importlib.util.spec_from_file_location("session_decide", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SD = _load()


@pytest.fixture()
def registry(tmp_path, monkeypatch):
    """A crafted session registry: active / hibernated / terminal."""
    reg = tmp_path / "sessions.json"
    reg.write_text(json.dumps({"sessions": [
        {"id": "s-a", "state": "active", "step": 7},
        {"id": "s-a2", "state": "active", "step": 5},
        {"id": "s-h", "state": "hibernated", "step": 7},
        {"id": "s-done", "state": "archived", "step": 12},
    ]}))
    monkeypatch.setattr(SD, "SESSION_REGISTRY", reg)
    monkeypatch.setattr(SD._core, "SESSION_REGISTRY", reg)
    monkeypatch.setattr(SD, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(SD, "SPAN_STORE", tmp_path / "spans.jsonl")
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return reg


def _states(reg):
    return {s["id"]: s["state"] for s in json.loads(reg.read_text())["sessions"]}


# ── hibernate / resume / kill guards ──────────────────────────────────────────

def test_hibernate_active_dry(registry):
    r = SD.decide("s-a", "hibernate")
    assert r["ok"] is True and r["dry_run"] is True
    assert r["would"]["state_transition"] == "active→hibernated"


def test_hibernate_requires_active(registry):
    r = SD.decide("s-h", "hibernate")  # already hibernated
    assert r["ok"] is False and "must be 'active'" in r["error"]


def test_resume_requires_hibernated(registry):
    assert SD.decide("s-a", "resume")["ok"] is False  # active, not hibernated
    r = SD.decide("s-h", "resume")
    assert r["ok"] is True and r["would"]["state_transition"] == "hibernated→active"


def test_kill_non_terminal_to_archived(registry):
    r = SD.decide("s-a", "kill")
    assert r["ok"] is True and r["would"]["state_transition"] == "active→archived"


def test_kill_refused_on_terminal(registry):
    r = SD.decide("s-done", "kill")
    assert r["ok"] is False and "terminal state" in r["error"]


def test_hibernate_live_transitions_and_records(registry):
    r = SD.decide("s-a", "hibernate", confirm=True)
    assert r["ok"] is True and r["state"] == "hibernated"
    assert r["signature"] == "unsigned-pending-MS003"
    assert _states(registry)["s-a"] == "hibernated"


def test_kill_live(registry):
    r = SD.decide("s-a", "kill", confirm=True)
    assert r["ok"] is True and r["state"] == "archived"
    assert _states(registry)["s-a"] == "archived"


# ── id / verb validation + dry-run safety ─────────────────────────────────────

@pytest.mark.parametrize("bad", ["a/b", "a b", "$(id)", "../x", ""])
def test_unsafe_id_rejected(registry, bad):
    r = SD.decide(bad, "kill")
    assert r["ok"] is False and "unsafe session id" in r["error"]


def test_unknown_id_rejected(registry):
    r = SD.decide("s-nope", "kill")
    assert r["ok"] is False and "no session resolved" in r["error"]


def test_unknown_verb_rejected(registry):
    r = SD.decide("s-a", "explode")
    assert r["ok"] is False and "unknown verb" in r["error"]


def test_confirm_still_dry_under_env(registry, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_DRY_RUN", "1")
    r = SD.decide("s-a", "hibernate", confirm=True)
    assert r["dry_run"] is True
    assert _states(registry)["s-a"] == "active"


# ── hibernate-all (bulk) ──────────────────────────────────────────────────────

def test_hibernate_all_dry_only_actives(registry):
    r = SD.hibernate_all()
    assert r["dry_run"] is True
    assert set(r["would"]["hibernate"]) == {"s-a", "s-a2"} and r["would"]["count"] == 2


def test_hibernate_all_live(registry):
    r = SD.hibernate_all(confirm=True)
    assert r["ok"] is True and r["count"] == 2 and set(r["hibernated"]) == {"s-a", "s-a2"}
    st = _states(registry)
    assert st["s-a"] == "hibernated" and st["s-a2"] == "hibernated"
    assert st["s-h"] == "hibernated" and st["s-done"] == "archived"  # untouched


# ── audit trail ───────────────────────────────────────────────────────────────

def test_live_decision_appends_ledger_and_span(registry):
    SD.decide("s-a", "hibernate", confirm=True)
    ledger = json.loads(SD.LEDGER.read_text().strip())
    assert ledger["verb"] == "hibernate" and ledger["id"] == "s-a"
    span = json.loads(SD.SPAN_STORE.read_text().strip())
    assert span["ocsf_class"] == "5001" and span["operation"] == "session_decision"
    assert span["attributes"]["session_id"] == "s-a"
