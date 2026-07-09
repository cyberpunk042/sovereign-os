"""Unit tests for the SDD-064 M028 admission-lifecycle engine
`scripts/intelligence/memory-admit.py`.

Covers: value-driven admission gating (store-if triggers admit at stage `observe`;
ignore-if / low-trust / duplicate are NOT stored; a missing trigger + a bad type are
usage errors); the 11-stage `advance` progression (observe→…→archive, idempotent at
archive); DRY-RUN default; and the end-to-end admit→advance→reconcile that makes the
D-07 projection (memory.json counts + lifecycle) reflect the real store — while
PRESERVING the memory-decide-owned `pending`/`history` fields.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ADMIT_PATH = REPO_ROOT / "scripts" / "intelligence" / "memory-admit.py"


def _load():
    spec = importlib.util.spec_from_file_location("memory_admit", ADMIT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A = _load()
S = A._store  # the memory-store module the engine reuses


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "STORE", tmp_path / "store.json")
    monkeypatch.setattr(S, "CHANGES", tmp_path / "changes.json")
    monkeypatch.setattr(S, "SPAN_STORE", tmp_path / "spans.jsonl")
    monkeypatch.setattr(S, "MEMORY_STATE", tmp_path / "memory.json")
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return tmp_path


def _entries():
    return list(S._entries().values())


def _proj(store_dir):
    return json.loads((store_dir / "memory.json").read_text())


# ── admit: the value gate ─────────────────────────────────────────────────────

def test_admit_dry_run_no_store(store):
    r = A.admit(2, "a fact", trigger="user-corrected")  # no --confirm
    assert r["ok"] and r["admitted"] and r["dry_run"] and r["would"]["stage"] == "observe"
    assert _entries() == []  # dry-run stores nothing


def test_admit_store_if_admits_at_observe(store):
    r = A.admit(2, "a fact", trigger="user-corrected", confirm=True)
    assert r["ok"] and r["admitted"] and r["id"].startswith("mem-")
    assert r["stage"] == "observe"
    e = _entries()[0]
    assert e["stage"] == "observe" and e["type"] == 2 and e["admitted_via"] == "user-corrected"


@pytest.mark.parametrize("ig", ["transient", "low-trust", "duplicate", "noisy", "unverified"])
def test_admit_ignore_if_not_stored(store, ig):
    r = A.admit(2, "junk", ignore=ig, confirm=True)
    assert r["ok"] and r["admitted"] is False and ig in r["reason"]
    assert _entries() == []  # value-gated out, never stored


def test_admit_low_trust_not_stored(store):
    r = A.admit(3, "meh", trigger="new-fact", trust=10, confirm=True)
    assert r["admitted"] is False and "low-trust" in r["reason"]
    assert _entries() == []


def test_admit_duplicate_not_stored(store):
    A.admit(2, "same", trigger="user-corrected", confirm=True)
    r = A.admit(2, "same", trigger="user-corrected", confirm=True)
    assert r["admitted"] is False and r["reason"] == "duplicate"
    assert len(_entries()) == 1  # only the first landed


def test_admit_requires_a_trigger(store):
    r = A.admit(2, "x", confirm=True)  # neither --trigger nor --ignore
    assert r["ok"] is False and "store-if trigger" in r["error"]


def test_admit_bad_trigger_and_type_rejected(store):
    assert A.admit(2, "x", trigger="not-a-real-trigger", confirm=True)["ok"] is False
    assert A.admit(9, "x", trigger="user-corrected", confirm=True)["ok"] is False
    assert A.admit(2, "x", ignore="bogus", confirm=True)["ok"] is False


# ── advance: the 11-stage lifecycle ───────────────────────────────────────────

def test_advance_walks_the_lifecycle(store):
    mid = A.admit(1, "wm", trigger="tool-worked", confirm=True)["id"]
    assert A.advance(mid, confirm=True)["stage"] == "classify"
    assert A.advance(mid, confirm=True)["stage"] == "quarantine"


def test_advance_dry_run_no_move(store):
    mid = A.admit(1, "wm", trigger="tool-worked", confirm=True)["id"]
    r = A.advance(mid)  # dry
    assert r["dry_run"] and r["would"]["stage_transition"] == "observe→classify"
    assert _entries()[0]["stage"] == "observe"


def test_advance_idempotent_at_archive(store):
    mid = A.admit(1, "wm", trigger="tool-worked", confirm=True)["id"]
    last = None
    for _ in range(20):
        last = A.advance(mid, confirm=True)
    assert last["stage"] == "archive" and last.get("idempotent") is True


def test_advance_unknown_and_unsafe(store):
    assert A.advance("mem-nope", confirm=True)["ok"] is False
    assert "unsafe" in A.advance("a/b", confirm=True)["error"]


# ── reconcile: the D-07 projection reflects the store (Q-059-D/Q-060-D) ────────

def test_reconcile_projection_reflects_store_and_preserves_pending(store):
    # a pre-existing pending queue + history (memory-decide-owned) MUST survive
    (store / "memory.json").write_text(json.dumps(
        {"pending": [{"id": "mc-1", "op": "promote"}], "history": ["h1"]}))
    m1 = A.admit(2, "episodic fact", trigger="user-corrected", confirm=True)["id"]
    A.admit(3, "semantic fact", trigger="new-fact", confirm=True)
    A.advance(m1, confirm=True)  # move the episodic one to `classify`
    proj = _proj(store)
    assert proj["counts"]["episodic"] == 1 and proj["counts"]["semantic"] == 1
    assert proj["counts"]["working"] == 0
    assert proj["lifecycle"]["classify"] == 1 and proj["lifecycle"]["observe"] == 1
    # the memory-decide-owned fields are preserved untouched
    assert proj["pending"][0]["id"] == "mc-1" and proj["history"] == ["h1"]


def test_forget_reconciles_active_count(store):
    mid = A.admit(2, "will forget", trigger="user-corrected", confirm=True)["id"]
    assert _proj(store)["counts"]["episodic"] == 1
    S.forget(mid, confirm=True, force=True)  # tombstone → drops from active count
    assert _proj(store)["counts"]["episodic"] == 0
