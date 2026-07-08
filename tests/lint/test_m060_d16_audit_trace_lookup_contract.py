"""M060 D-16 audit-mirror `trace <id>` lookup contract.

M013 E0112 — "Tracing is crucial: trace_id / span_id / branch_id /
commit_id". The audit-mirror snapshot already carries trace_id per
span; this contract test locks the operator's ability to query ONE
trace by ID without piping the full snapshot through jq.

Locks:
  1. The reader script exposes a `trace` subcommand.
  2. `trace <unknown>` returns found=False + a `_hint` directing the
     operator to the IPS-side surface for full-chain queries
     (the published tail is bounded to 256 spans).
  3. `trace <known>` returns found=True + the span + chain walkers
     (prev_trace_id / next_trace_id).
  4. Exit code 1 on not-found, 0 on found — scripts can branch.
  5. The hint points at `selfdefctl audit show --trace-id` so the
     operator's fallback path is operator-actionable, not generic.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
READER_PATH = REPO_ROOT / "scripts" / "mirror" / "selfdef-audit-mirror.py"


def _run(*args: str, env_artifact: str | None = None, expect_exit: int | None = None) -> dict:
    """Run the reader with optional env-var pointing at a fixture
    artifact, return parsed JSON output."""
    env = {**os.environ, "PATH": "/usr/bin:/bin"}
    if env_artifact is not None:
        env["SOVEREIGN_OS_SELFDEF_AUDIT_MIRROR"] = env_artifact
    proc = subprocess.run(
        ["python3", str(READER_PATH), *args],
        env=env, capture_output=True, text=True, timeout=10, check=False,
    )
    if expect_exit is not None:
        assert proc.returncode == expect_exit, (
            f"expected exit {expect_exit}, got {proc.returncode}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    return json.loads(proc.stdout)


def _fixture_with_spans(trace_ids: list[str]) -> dict:
    spans = []
    prev_hash = ""
    for i, tid in enumerate(trace_ids):
        chain_hash = f"chain-{i:03}-hash"
        spans.append({
            "trace_id": tid,
            "profile": "careful",
            "model": "qwen3-coder-32b",
            "provider": "local-cuda",
            "hardware": "4090_logic",
            "tokens_prompt": 100,
            "tokens_completion": 50,
            "latency_ms": 1500,
            "cost_millicents": 1,
            "risk_score": 5,
            "memory_refs": [],
            "tool_refs": ["tests"],
            "policy_result": "allow",
            "branch_id": f"b{i}",
            "ocsf_category": "authority_decision",
            "closed_at": f"2027-01-15T08:00:{i:02}Z",
            "prev_chain_hash": prev_hash,
            "chain_hash": chain_hash,
            "signature": "sig",
        })
        prev_hash = chain_hash
    return {
        "schema_version": "1.0.0",
        "captured_at": "2027-01-15T08:00:00Z",
        "summaries": [
            {"category": "authority_decision", "total": len(spans),
             "allow": len(spans), "deny": 0, "ask": 0, "sandbox": 0},
        ],
        "integrity": {
            "head_hash": "a" * 64,
            "total_entries": len(spans),
            "continuous": True,
            "first_gap_at": None,
            "verified_at": "2027-01-15T08:00:00Z",
        },
        "spans": spans,
        "signature": "",
    }


def test_trace_subcommand_exists():
    """`trace` subcommand must accept a positional trace_id arg."""
    proc = subprocess.run(
        ["python3", str(READER_PATH), "trace", "--help"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert proc.returncode == 0
    assert "trace_id" in proc.stdout


def test_trace_unknown_returns_not_found_with_actionable_hint():
    """Unknown trace_id → found=False + hint pointing at the IPS-side
    fallback (selfdefctl audit show --trace-id ...)."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "audit.json")
        with open(p, "w") as f:
            json.dump(_fixture_with_spans(["t1", "t2", "t3"]), f)
        result = _run("trace", "nonexistent", env_artifact=p, expect_exit=1)
    assert result["found"] is False
    assert result["trace_id"] == "nonexistent"
    assert "_hint" in result
    # Operator-actionable fallback path.
    assert "selfdefctl audit show" in result["_hint"]
    assert "--trace-id" in result["_hint"]
    # Hint mentions the bounded-tail caveat (256 spans cap) so operator
    # knows WHY their trace might not be in the published mirror.
    assert "bounded tail" in result["_hint"]


def test_trace_known_returns_full_span_with_chain_walkers():
    """Known trace_id → found=True + the span + prev/next trace_id
    so operator can walk the chain."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "audit.json")
        with open(p, "w") as f:
            json.dump(_fixture_with_spans(["t1", "t2", "t3"]), f)
        result = _run("trace", "t2", env_artifact=p, expect_exit=0)
    assert result["found"] is True
    assert result["trace_id"] == "t2"
    assert result["span"]["trace_id"] == "t2"
    assert result["span"]["policy_result"] == "allow"
    # Chain walkers point at the adjacent spans.
    assert result["prev_trace_id"] == "t1"
    assert result["next_trace_id"] == "t3"


def test_trace_first_span_has_no_prev_walker():
    """The first span in the tail has no prev — None, not the empty
    string, so the operator can distinguish 'no prev' from 'prev with
    blank trace_id'."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "audit.json")
        with open(p, "w") as f:
            json.dump(_fixture_with_spans(["first", "second"]), f)
        result = _run("trace", "first", env_artifact=p, expect_exit=0)
    assert result["prev_trace_id"] is None
    assert result["next_trace_id"] == "second"


def test_trace_last_span_has_no_next_walker():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "audit.json")
        with open(p, "w") as f:
            json.dump(_fixture_with_spans(["first", "second"]), f)
        result = _run("trace", "second", env_artifact=p, expect_exit=0)
    assert result["prev_trace_id"] == "first"
    assert result["next_trace_id"] is None


def test_trace_offline_mirror_returns_not_found_with_hint():
    """When the mirror artifact is absent, the lookup must return
    found=False (honest) and the hint should still surface the
    fallback path."""
    with tempfile.TemporaryDirectory() as d:
        missing = os.path.join(d, "does-not-exist.json")
        result = _run("trace", "anything", env_artifact=missing, expect_exit=1)
    assert result["found"] is False
    assert result["mirror_status"] == "offline"


def test_trace_exit_code_distinguishes_found_vs_not_found():
    """The exit code is the script-friendly contract: 0 found, 1 not
    found OR offline. Other audit-mirror surfaces (e.g., m060-doctor
    follow-up scripts) branch on this without parsing JSON."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "audit.json")
        with open(p, "w") as f:
            json.dump(_fixture_with_spans(["t1"]), f)
        # Found.
        env = {**os.environ, "SOVEREIGN_OS_SELFDEF_AUDIT_MIRROR": p, "PATH": "/usr/bin:/bin"}
        proc = subprocess.run(
            ["python3", str(READER_PATH), "trace", "t1"],
            env=env, capture_output=True, text=True, timeout=10, check=False,
        )
        assert proc.returncode == 0
        # Not found.
        proc = subprocess.run(
            ["python3", str(READER_PATH), "trace", "t-missing"],
            env=env, capture_output=True, text=True, timeout=10, check=False,
        )
        assert proc.returncode == 1


def test_trace_does_not_break_existing_snapshot_or_integrity_verbs():
    """Adding the trace verb must NOT alter snapshot or integrity
    output — they're load-bearing for D-16 dashboard."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "audit.json")
        with open(p, "w") as f:
            json.dump(_fixture_with_spans(["t1", "t2"]), f)
        snap = _run("snapshot", env_artifact=p, expect_exit=0)
        integ = _run("integrity", env_artifact=p, expect_exit=0)
    assert snap["mirror_status"] == "online"
    assert len(snap["spans"]) == 2
    assert integ["total_entries"] == 2
    assert integ["continuous"] is True
