"""Unit tests for the SDD-051 adapter WRITE surface
`scripts/inference/adapter-decide.py`: promote (MS041 triple-gate
refuse-by-default) / demote / rollback / register.

Covers the security-critical core: the gate enforcement (promote refuses unless
snapshot + test_eval + (oracle OR human) all `passed`), the status-transition
guards, `_SAFE_ID` validation, DRY-RUN default (no registry mutation without
--confirm), atomic write + history append + `unsigned-pending-MS003` signature.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "scripts" / "inference" / "adapter-decide.py"


def _load():
    spec = importlib.util.spec_from_file_location("adapter_decide", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AD = _load()


@pytest.fixture()
def registry(tmp_path, monkeypatch):
    """A crafted promotion registry: a-ready (gates pass, pending), a-unmet
    (gates fail, pending), a-active (active)."""
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"adapters": {
        "a-ready": {"status": "pending", "base_model": "qwen3-8b",
                    "gates": {"snapshot": "passed", "test_eval": "passed",
                              "oracle": "passed", "human": "pending"}},
        "a-unmet": {"status": "pending", "base_model": "qwen3-8b",
                    "gates": {"snapshot": "passed", "test_eval": "pending",
                              "oracle": "pending", "human": "pending"}},
        "a-active": {"status": "active", "base_model": "qwen3-8b",
                     "gates": {"snapshot": "passed", "test_eval": "passed",
                               "oracle": "passed", "human": "passed"}},
    }}))
    monkeypatch.setattr(AD, "ADAPTER_REGISTRY", reg)
    monkeypatch.setattr(AD._core, "ADAPTER_REGISTRY", reg)
    monkeypatch.setattr(AD, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(AD, "SPAN_STORE", tmp_path / "spans.jsonl")
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return reg


# ── promote gate (refuse-by-default) ──────────────────────────────────────────

def test_promote_dry_run_when_gates_pass(registry):
    r = AD.decide("a-ready", "promote")  # no --confirm → dry
    assert r["ok"] is True and r["dry_run"] is True
    assert r["would"]["status_transition"] == "pending→active"


def test_promote_refused_when_gate_unmet(registry):
    r = AD.decide("a-unmet", "promote")
    assert r["ok"] is False and r["code"] == 2
    assert "MS041 triple-gate not satisfied" in r["error"]
    assert "test_eval" in r["error"] and "oracle_or_human" in r["error"]


@pytest.mark.parametrize("missing", ["snapshot", "test_eval", "oracle_human"])
def test_promote_refused_per_missing_gate(registry, missing):
    gates = {"snapshot": "passed", "test_eval": "passed",
             "oracle": "passed", "human": "pending"}
    if missing == "snapshot":
        gates["snapshot"] = "pending"
    elif missing == "test_eval":
        gates["test_eval"] = "pending"
    else:
        gates["oracle"] = "pending"  # human already pending → oracle_or_human unmet
    reg = json.loads(registry.read_text())
    reg["adapters"]["a-ready"]["gates"] = gates
    registry.write_text(json.dumps(reg))
    r = AD.decide("a-ready", "promote", confirm=True)
    assert r["ok"] is False and "MS041 triple-gate" in r["error"]


def test_promote_live_transitions_and_records(registry):
    r = AD.decide("a-ready", "promote", confirm=True)
    assert r["ok"] is True and r["status"] == "active"
    assert r["signature"] == "unsigned-pending-MS003"
    reg = json.loads(registry.read_text())
    assert reg["adapters"]["a-ready"]["status"] == "active"
    assert reg["adapters"]["a-ready"]["signature"] == "unsigned-pending-MS003"
    assert reg["history"][0]["action"] == "promote"
    assert reg["history"][0]["adapter_id"] == "a-ready"


# ── demote / rollback + guards ────────────────────────────────────────────────

def test_demote_requires_active(registry):
    assert AD.decide("a-ready", "demote")["ok"] is False  # a-ready is pending
    r = AD.decide("a-active", "demote")
    assert r["ok"] is True and r["would"]["status_transition"] == "active→pending"


def test_rollback_any_status_dry(registry):
    r = AD.decide("a-active", "rollback")
    assert r["ok"] is True and r["would"]["status_transition"] == "active→rolled-back"


def test_rollback_live(registry):
    r = AD.decide("a-active", "rollback", confirm=True)
    assert r["ok"] is True and r["status"] == "rolled-back"
    assert json.loads(registry.read_text())["adapters"]["a-active"]["status"] == "rolled-back"


# ── id validation + resolution ────────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["a/b", "a b", "$(id)", "../x", ""])
def test_unsafe_id_rejected(registry, bad):
    r = AD.decide(bad, "promote")
    assert r["ok"] is False and "unsafe adapter id" in r["error"]


def test_unknown_id_rejected(registry):
    r = AD.decide("no-such-adapter", "promote")
    assert r["ok"] is False and "no adapter resolved" in r["error"]


def test_unknown_verb_rejected(registry):
    r = AD.decide("a-ready", "explode")
    assert r["ok"] is False and "unknown verb" in r["error"]


def test_confirm_still_dry_under_env(registry, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_DRY_RUN", "1")
    r = AD.decide("a-ready", "promote", confirm=True)
    assert r["dry_run"] is True
    assert json.loads(registry.read_text())["adapters"]["a-ready"]["status"] == "pending"


# ── register producer + audit trail ───────────────────────────────────────────

def test_register_mints_pending(registry):
    r = AD.register("a-new", base_model="qwen3-8b")
    assert r["ok"] is True and r["status"] == "pending"
    reg = json.loads(registry.read_text())
    assert reg["adapters"]["a-new"]["status"] == "pending"
    assert reg["adapters"]["a-new"]["gates"]["snapshot"] == "pending"
    # a freshly-registered adapter cannot promote (gates unmet)
    assert AD.decide("a-new", "promote", confirm=True)["ok"] is False


def test_register_rejects_duplicate(registry):
    assert AD.register("a-ready")["ok"] is False


def test_live_decision_appends_ledger_and_span(registry):
    AD.decide("a-ready", "promote", confirm=True)
    ledger = json.loads(AD.LEDGER.read_text().strip())
    assert ledger["verb"] == "promote" and ledger["id"] == "a-ready"
    span = json.loads(AD.SPAN_STORE.read_text().strip())
    assert span["ocsf_class"] == "5001" and span["operation"] == "adapter_decision"
    assert span["attributes"]["adapter_id"] == "a-ready"
