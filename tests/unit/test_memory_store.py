"""Unit tests for the SDD-059 M028 memory-entry store + soft-delete forget + undo
`scripts/intelligence/memory-store.py`.

Covers: register mints an active entry; forget is REFUSE-by-default (`--force`
CLI-only); forget `--force` SOFT-DELETES (tombstone `state:forgotten` + ledger the
prior state — never a hard remove); undo RESTORES the tombstoned entry + marks the
change reversed; already-reversed / unknown / unsafe rejects; DRY-RUN default (no
mutation); type validation.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "scripts" / "intelligence" / "memory-store.py"


def _load():
    spec = importlib.util.spec_from_file_location("memory_store", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MS = _load()


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(MS, "STORE", tmp_path / "store.json")
    monkeypatch.setattr(MS, "CHANGES", tmp_path / "changes.json")
    monkeypatch.setattr(MS, "SPAN_STORE", tmp_path / "spans.jsonl")
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return tmp_path


def _mk(mtype=3):
    return MS.register(mtype, summary="a fact")["id"]


def _state(mid):
    return next(e["state"] for e in MS.store_list() if e["id"] == mid)


# ── register (producer) ───────────────────────────────────────────────────────

def test_register_mints_active(store):
    r = MS.register(3, summary="x")
    assert r["ok"] is True and r["id"].startswith("mem-") and r["state"] == "active"
    assert _state(r["id"]) == "active"


@pytest.mark.parametrize("bad", [0, 9, 99, "x"])
def test_register_rejects_bad_type(store, bad):
    assert MS.register(bad)["ok"] is False


# ── forget (refuse-by-default + soft-delete) ──────────────────────────────────

def test_forget_refused_without_force(store):
    mid = _mk()
    r = MS.forget(mid)  # no --force
    assert r["ok"] is False and "forget refused" in r["error"] and "--force" in r["error"]
    assert _state(mid) == "active"  # untouched


def test_forget_force_dry_run_no_mutation(store):
    mid = _mk()
    r = MS.forget(mid, force=True)  # dry (no --confirm)
    assert r["ok"] is True and r["dry_run"] is True
    assert r["would"]["reversible"] is True
    assert _state(mid) == "active"  # dry-run mutates nothing


def test_forget_force_live_soft_deletes_and_ledgers(store):
    mid = _mk()
    r = MS.forget(mid, confirm=True, force=True)
    assert r["ok"] is True and r["state"] == "forgotten" and r["change_id"].startswith("chg-")
    assert _state(mid) == "forgotten"  # tombstoned, NOT hard-removed
    assert mid in {e["id"] for e in MS.store_list()}  # still present (soft-delete)
    led = json.loads((store / "changes.json").read_text())["changes"]
    assert led[0]["op"] == "forget" and led[0]["mem_id"] == mid
    assert led[0]["prev"]["state"] == "active" and led[0]["reversed"] is False


def test_forget_already_forgotten(store):
    mid = _mk()
    MS.forget(mid, confirm=True, force=True)
    r = MS.forget(mid, confirm=True, force=True)
    assert r["ok"] is False and "already forgotten" in r["error"]


@pytest.mark.parametrize("bad", ["a/b", "a b", "$(id)", ""])
def test_forget_unsafe_id(store, bad):
    assert MS.forget(bad, force=True)["ok"] is False


def test_forget_unknown_id(store):
    assert MS.forget("mem-nope", force=True)["ok"] is False


# ── undo (restore) ────────────────────────────────────────────────────────────

def test_undo_restores_tombstoned_entry(store):
    mid = _mk()
    cid = MS.forget(mid, confirm=True, force=True)["change_id"]
    assert _state(mid) == "forgotten"
    r = MS.undo(cid, confirm=True)
    assert r["ok"] is True and r["restored_state"] == "active"
    assert _state(mid) == "active"
    led = json.loads((store / "changes.json").read_text())["changes"]
    assert led[0]["reversed"] is True


def test_undo_dry_run_no_mutation(store):
    mid = _mk()
    cid = MS.forget(mid, confirm=True, force=True)["change_id"]
    r = MS.undo(cid)  # dry
    assert r["dry_run"] is True and _state(mid) == "forgotten"


def test_undo_already_reversed(store):
    mid = _mk()
    cid = MS.forget(mid, confirm=True, force=True)["change_id"]
    MS.undo(cid, confirm=True)
    r = MS.undo(cid, confirm=True)
    assert r["ok"] is False and "already reversed" in r["error"]


def test_undo_unknown_and_unsafe(store):
    assert MS.undo("chg-nope")["ok"] is False
    assert "unsafe" in MS.undo("a/b")["error"]
