"""Unit tests for scripts/lifecycle/approval-decide.py (SDD-048 Stage 1/2).

The D-06 decision-writer + minimal producer: approve/deny/defer transitions, the
`latest` convenience, _SAFE_VALUE id rejection, atomic queue write, the durable
JSONL ledger + OCSF-5001 span, DRY-RUN gating, and APR-<8hex> minting. Run as a
subprocess with a temp queue/ledger/span store (the module caches the queue path
at import), mirroring tests/lint/test_sovereign_osctl_rollback_apply.py.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "scripts" / "lifecycle" / "approval-decide.py"


def _run(args, tmp: Path, extra_env=None):
    env = {**os.environ,
           "SOVEREIGN_OS_APPROVALS": str(tmp / "approvals.json"),
           "SOVEREIGN_OS_APPROVAL_LEDGER": str(tmp / "ledger.jsonl"),
           "SOVEREIGN_OS_SPAN_STORE": str(tmp / "spans.jsonl")}
    if extra_env:
        env.update(extra_env)
    r = subprocess.run([sys.executable, str(CORE), *args],
                       capture_output=True, text=True, env=env)
    return json.loads(r.stdout), r.returncode


def _queue(tmp: Path) -> dict:
    return json.loads((tmp / "approvals.json").read_text())


def _seed(tmp: Path, sev="high", gate="SG1", title="t"):
    d, _ = _run(["request", "--title", title, "--severity", sev, "--gate", gate], tmp)
    return d["id"]


def test_request_mints_apr_id(tmp_path):
    d, rc = _run(["request", "--title", "gate sign-off", "--severity", "high", "--gate", "SG1"], tmp_path)
    assert rc == 0 and d["ok"] is True
    assert re.fullmatch(r"APR-[0-9a-f]{8}", d["id"]), d["id"]
    q = _queue(tmp_path)
    assert q["approvals"][0]["id"] == d["id"] and q["approvals"][0]["status"] == "pending"


def test_approve_confirm_signs_record_and_gate(tmp_path):
    rid = _seed(tmp_path, gate="SG1")
    d, rc = _run(["approve", rid, "--confirm", "--rationale", "reviewed"], tmp_path)
    assert rc == 0 and d["ok"] is True and d["status"] == "signed" and d["gate_signed"] == "SG1"
    assert d["signature"] == "unsigned-pending-MS003"
    q = _queue(tmp_path)
    assert q["approvals"][0]["status"] == "signed"
    assert q["gates"]["SG1"] == "signed"


def test_approve_without_confirm_is_dry_run(tmp_path):
    rid = _seed(tmp_path)
    d, rc = _run(["approve", rid], tmp_path)
    assert d["dry_run"] is True and d["would"]["status"] == "signed"
    assert _queue(tmp_path)["approvals"][0]["status"] == "pending"  # untouched


def test_dry_run_env_forces_noop_even_with_confirm(tmp_path):
    rid = _seed(tmp_path)
    d, _ = _run(["approve", rid, "--confirm"], tmp_path, extra_env={"SOVEREIGN_OS_DRY_RUN": "1"})
    assert d["dry_run"] is True
    assert _queue(tmp_path)["approvals"][0]["status"] == "pending"


def test_deny_keeps_gate_pending(tmp_path):
    rid = _seed(tmp_path, gate="SG2")
    d, _ = _run(["deny", rid, "--confirm"], tmp_path)
    assert d["status"] == "denied" and d["gate_signed"] is None
    q = _queue(tmp_path)
    assert q["approvals"][0]["status"] == "denied"
    assert q.get("gates", {}).get("SG2") in (None, "pending")  # NOT signed


def test_defer_sets_defer_until(tmp_path):
    rid = _seed(tmp_path)
    d, _ = _run(["defer", rid, "--confirm", "--until", "2026-08-01T00:00:00Z"], tmp_path)
    assert d["status"] == "deferred"
    rec = _queue(tmp_path)["approvals"][0]
    assert rec["status"] == "deferred" and rec["defer_until"] == "2026-08-01T00:00:00Z"


def test_latest_resolves_most_urgent(tmp_path):
    _seed(tmp_path, sev="low", gate="SG3", title="low one")
    hi = _seed(tmp_path, sev="critical", gate="SG1", title="urgent one")
    d, _ = _run(["approve", "latest", "--confirm"], tmp_path)
    assert d["id"] == hi and d["gate_signed"] == "SG1"


def test_unsafe_id_rejected(tmp_path):
    _seed(tmp_path)
    d, rc = _run(["approve", "pool/bad@snap", "--confirm"], tmp_path)
    assert d["ok"] is False and rc == 2
    assert "unsafe approval id" in d["error"]


def test_unknown_id_errors(tmp_path):
    _seed(tmp_path)
    d, rc = _run(["approve", "APR-deadbeef", "--confirm"], tmp_path)
    assert d["ok"] is False and "no approval resolved" in d["error"]


def test_decision_recorded_to_ledger_and_span(tmp_path):
    rid = _seed(tmp_path, gate="SG1")
    _run(["approve", rid, "--confirm"], tmp_path)
    ledger = [json.loads(x) for x in (tmp_path / "ledger.jsonl").read_text().splitlines() if x.strip()]
    assert len(ledger) == 1 and ledger[0]["id"] == rid and ledger[0]["verb"] == "approve"
    spans = [json.loads(x) for x in (tmp_path / "spans.jsonl").read_text().splitlines() if x.strip()]
    assert len(spans) == 1 and spans[0]["operation"] == "approval_decision"
    assert spans[0]["ocsf_class"] == "5001" and spans[0]["signature"] == "unsigned-pending-MS003"
