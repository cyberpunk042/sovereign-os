"""Unit tests for the SDD-061 M046 adapter GATE-PRODUCER
`scripts/inference/adapter-gate.py`: gate {human,snapshot,eval,oracle} advancing
the MS041 triple-gate from REAL evidence.

Covers: each gate advances its registry field to `passed` ONLY on real evidence
(SB-077 — honest-defer otherwise, never fabricate); the `gate_evidence` provenance
record; DRY-RUN default (no registry mutation without --confirm); `_SAFE_ID`
validation; idempotent already-passed; and the end-to-end proof that snapshot +
eval-record + human make `adapter-decide promote` succeed (the D-11 pill-green path).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = REPO_ROOT / "scripts" / "inference" / "adapter-gate.py"
DECIDE_PATH = REPO_ROOT / "scripts" / "inference" / "adapter-decide.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE = _load(GATE_PATH, "adapter_gate")
DECIDE = _load(DECIDE_PATH, "adapter_decide_for_gate")


@pytest.fixture()
def registry(tmp_path, monkeypatch):
    """A single pending adapter with all gates pending + a tmp eval store."""
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"adapters": {
        "a-x": {"status": "pending", "base_model": "qwen3-8b",
                "gates": {"snapshot": "pending", "test_eval": "pending",
                          "oracle": "pending", "human": "pending"}},
    }}))
    evals = tmp_path / "evals.jsonl"
    # point BOTH the gate module + its reader core at the tmp registry.
    monkeypatch.setattr(GATE, "ADAPTER_REGISTRY", reg)
    monkeypatch.setattr(GATE._af, "ADAPTER_REGISTRY", reg)
    monkeypatch.setattr(GATE, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(GATE, "SPAN_STORE", tmp_path / "spans.jsonl")
    monkeypatch.setattr(GATE._eval, "EVAL_STORE", evals)
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return {"reg": reg, "evals": evals, "tmp": tmp_path}


def _gates(reg: Path, aid: str = "a-x") -> dict:
    return json.loads(reg.read_text())["adapters"][aid]["gates"]


def _seed_eval(evals: Path, *, adapter_id="a-x", score=0.82, passed=True, ts="2026-07-09T00:00:00+00:00"):
    with evals.open("a") as fh:
        fh.write(json.dumps({"ts": ts, "task": "mmlu", "adapter_id": adapter_id,
                             "score": score, "passed": passed, "trace_id": "tr-1"}) + "\n")


# ── human gate (always producible — the operator attestation) ─────────────────

def test_human_dry_run_no_mutation(registry):
    r = GATE.gate_human("a-x")  # no --confirm
    assert r["ok"] is True and r["dry_run"] is True
    assert _gates(registry["reg"])["human"] == "pending"  # dry mutates nothing


def test_human_live_sets_passed_with_evidence(registry):
    r = GATE.gate_human("a-x", confirm=True, rationale="reviewed the diff")
    assert r["ok"] is True and r["gate"] == "human" and r["state"] == "passed"
    assert _gates(registry["reg"])["human"] == "passed"
    ge = json.loads(registry["reg"].read_text())["adapters"]["a-x"]["gate_evidence"]
    assert ge["human"]["attested_by"] == "operator" and ge["human"]["rationale"] == "reviewed the diff"


def test_human_idempotent(registry):
    GATE.gate_human("a-x", confirm=True)
    r = GATE.gate_human("a-x", confirm=True)
    assert r.get("idempotent") is True and _gates(registry["reg"])["human"] == "passed"


# ── eval gate (a real passing evals.jsonl record — SB-077) ────────────────────

def test_eval_no_record_defers(registry):
    r = GATE.gate_eval("a-x", confirm=True)
    assert r["ok"] is False and r.get("deferred") is True
    assert "no eval record" in r["error"]
    assert _gates(registry["reg"])["test_eval"] == "pending"  # not fabricated


def test_eval_failing_record_defers(registry):
    _seed_eval(registry["evals"], score=0.20, passed=False)
    r = GATE.gate_eval("a-x", confirm=True)
    assert r["ok"] is False and r.get("deferred") is True and "did not pass" in r["error"]
    assert _gates(registry["reg"])["test_eval"] == "pending"


def test_eval_passing_record_advances(registry):
    _seed_eval(registry["evals"], score=0.82, passed=True)
    r = GATE.gate_eval("a-x", confirm=True)
    assert r["ok"] is True and r["gate"] == "test_eval" and r["state"] == "passed"
    assert _gates(registry["reg"])["test_eval"] == "passed"
    ge = json.loads(registry["reg"].read_text())["adapters"]["a-x"]["gate_evidence"]
    assert ge["test_eval"]["score"] == 0.82 and ge["test_eval"]["trace_id"] == "tr-1"


def test_eval_uses_latest_record(registry):
    _seed_eval(registry["evals"], score=0.20, passed=False, ts="2026-07-08T00:00:00+00:00")
    _seed_eval(registry["evals"], score=0.90, passed=True, ts="2026-07-09T00:00:00+00:00")
    assert GATE.gate_eval("a-x", confirm=True)["ok"] is True  # latest passes


# ── snapshot gate (a real ZFS rollback-point — SDD-050) ───────────────────────

def test_snapshot_dry_defers(registry, monkeypatch):
    # without --confirm, rollback-points.create dry-runs → no real snapshot → defer
    monkeypatch.setattr(GATE._rollback, "create",
                        lambda dk, tag, confirm=False: {"dry_run": True, "would_run": ["zfs", "snapshot", tag]})
    r = GATE.gate_snapshot("a-x")
    assert r["ok"] is False and r.get("deferred") is True
    assert _gates(registry["reg"])["snapshot"] == "pending"


def test_snapshot_create_ok_advances(registry, monkeypatch):
    monkeypatch.setattr(GATE._rollback, "create",
                        lambda dk, tag, confirm=False: {"ok": True, "target": f"tank/models@{tag}", "dataset": "tank/models"})
    r = GATE.gate_snapshot("a-x", confirm=True)
    assert r["ok"] is True and r["state"] == "passed"
    assert _gates(registry["reg"])["snapshot"] == "passed"
    ge = json.loads(registry["reg"].read_text())["adapters"]["a-x"]["gate_evidence"]
    assert ge["snapshot"]["target"].startswith("tank/models@gate-a-x")


def test_snapshot_create_fail_defers(registry, monkeypatch):
    monkeypatch.setattr(GATE._rollback, "create",
                        lambda dk, tag, confirm=False: {"ok": False, "target": f"tank/models@{tag}", "error": "no zfs"})
    r = GATE.gate_snapshot("a-x", confirm=True)
    assert r["ok"] is False and r.get("deferred") is True
    assert _gates(registry["reg"])["snapshot"] == "pending"  # never fabricated


# ── oracle gate (probe + judge; honest-defer when unreachable) ────────────────

def test_oracle_unreachable_defers(registry, monkeypatch):
    monkeypatch.setattr(GATE, "_oracle_reachable", lambda ep: False)
    r = GATE.gate_oracle("a-x", confirm=True)
    assert r["ok"] is False and r.get("deferred") is True and "unreachable" in r["error"]
    assert _gates(registry["reg"])["oracle"] == "pending"


def test_oracle_reachable_pass_advances(registry, monkeypatch):
    monkeypatch.setattr(GATE, "_oracle_reachable", lambda ep: True)
    monkeypatch.setattr(GATE, "_oracle_judge", lambda aid, ep: "pass")
    r = GATE.gate_oracle("a-x", confirm=True)
    assert r["ok"] is True and r["state"] == "passed"
    assert _gates(registry["reg"])["oracle"] == "passed"


def test_oracle_reachable_fail_defers(registry, monkeypatch):
    monkeypatch.setattr(GATE, "_oracle_reachable", lambda ep: True)
    monkeypatch.setattr(GATE, "_oracle_judge", lambda aid, ep: "fail")
    r = GATE.gate_oracle("a-x", confirm=True)
    assert r["ok"] is False and r.get("deferred") is True
    assert _gates(registry["reg"])["oracle"] == "pending"


# ── id + resolution guards ────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["a/b", "a b", "$(id)", "../x", ""])
def test_unsafe_id_rejected(registry, bad):
    assert GATE.gate_human(bad, confirm=True)["ok"] is False


def test_unknown_adapter_rejected(registry):
    r = GATE.gate_human("nope", confirm=True)
    assert r["ok"] is False and "no adapter resolved" in r["error"]


def test_default_dry_run(registry):
    """No mutation without --confirm."""
    _seed_eval(registry["evals"], passed=True)
    GATE.gate_eval("a-x")  # no confirm
    assert _gates(registry["reg"])["test_eval"] == "pending"


# ── end-to-end: the D-11 pill-green promotion path ────────────────────────────

def test_end_to_end_gates_enable_promote(registry, monkeypatch):
    """register → snapshot + eval-record + human → _gate_unmet empty → promote."""
    # share the tmp registry + stores with the adapter-decide consumer.
    monkeypatch.setattr(DECIDE, "ADAPTER_REGISTRY", registry["reg"])
    monkeypatch.setattr(DECIDE._core, "ADAPTER_REGISTRY", registry["reg"])
    monkeypatch.setattr(DECIDE, "LEDGER", registry["tmp"] / "ledger.jsonl")
    monkeypatch.setattr(DECIDE, "SPAN_STORE", registry["tmp"] / "spans.jsonl")
    monkeypatch.setattr(GATE._rollback, "create",
                        lambda dk, tag, confirm=False: {"ok": True, "target": f"tank/models@{tag}"})
    _seed_eval(registry["evals"], passed=True)

    # promote refused before the gates advance
    assert DECIDE.decide("a-x", "promote", confirm=True)["ok"] is False

    GATE.gate_snapshot("a-x", confirm=True)
    GATE.gate_eval("a-x", confirm=True)
    GATE.gate_human("a-x", confirm=True)

    g = _gates(registry["reg"])
    assert g["snapshot"] == "passed" and g["test_eval"] == "passed" and g["human"] == "passed"
    assert DECIDE._gate_unmet(g) == []  # oracle_or_human satisfied by human
    r = DECIDE.decide("a-x", "promote", confirm=True)
    assert r["ok"] is True and r["status"] == "active"
