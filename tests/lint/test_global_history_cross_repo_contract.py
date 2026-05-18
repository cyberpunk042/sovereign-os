"""R465 — Cross-repo contract test: sovereign-os `global-history`
reads JSONL written in the format the selfdef-history-sink Rust crate
emits (SD-R-EVENT-LOG-1).

The selfdef crate writes records like:
    {"timestamp": "...", "source": "modules", "module": "...",
     "event": "...", "status": "...", "actor": "...", "detail": {...}}

The sovereign-os reader (`_read_modules`) consumes this. This test
verifies the contract end-to-end:
  - the env var name agreed on by both repos is honored
  - records produced in the documented format are read back
  - the operator's `--since` filter works against ISO timestamps
    matching the format the selfdef crate emits
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GH_PY = REPO_ROOT / "scripts" / "operator" / "global-history.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_global_history_honors_cross_repo_env_var_name():
    """R465: SOVEREIGN_OS_MODULES_LOG (the name the selfdef crate
    uses) MUST be honored by sovereign-os global-history.py."""
    body = _read(GH_PY)
    assert "SOVEREIGN_OS_MODULES_LOG" in body, (
        "global-history.py must honor SOVEREIGN_OS_MODULES_LOG — "
        "the env var name agreed with selfdef-history-sink crate "
        "(SD-R-EVENT-LOG-1)"
    )


def test_default_path_matches_selfdef_history_sink_default(tmp_path):
    """R465: both repos' DEFAULT path constants must match exactly."""
    body = _read(GH_PY)
    # The default in global-history.py
    assert "/var/log/sovereign-os/modules.jsonl" in body
    # The selfdef-history-sink Rust crate documents the SAME path as
    # DEFAULT_MODULES_LOG. (We don't import Rust code here; this test
    # just enforces the sovereign-os side of the contract has the
    # exact literal — drift detection.)


def test_reader_accepts_selfdef_history_sink_record_shape(tmp_path):
    """End-to-end: synthesize a JSONL file in the EXACT format the
    selfdef-history-sink Rust crate writes, point global-history at
    it, and verify the record is read back."""
    log_path = tmp_path / "modules.jsonl"
    # The record shape selfdef-history-sink writes (matches the
    # HistoryEvent serde derive: timestamp + source + module + event
    # + status + actor? + detail?):
    records = [
        {
            "timestamp": "2026-05-18T15:00:00Z",
            "source": "modules",
            "module": "agent-guard",
            "event": "installed",
            "status": "ok",
            "actor": "selfdefctl",
            "detail": {"version": "1.0.0"},
        },
        {
            "timestamp": "2026-05-18T15:01:00Z",
            "source": "modules",
            "module": "polarproxy",
            "event": "feature-toggled",
            "status": "ok",
        },
        {
            "timestamp": "2026-05-18T15:02:00Z",
            "source": "modules",
            "module": "agent-guard",
            "event": "policy-applied",
            "status": "failed",
            "detail": {"reason": "test"},
        },
    ]
    log_path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    # Use the cross-repo agreed env var name AND a far-past --since.
    result = subprocess.run(
        ["python3", str(GH_PY), "recent",
         "--source", "modules",
         "--since", "2020-01-01T00:00:00Z",
         "--limit", "50", "--json"],
        capture_output=True, text=True, timeout=10,
        env={**os.environ,
             "SOVEREIGN_OS_MODULES_LOG": str(log_path)},
    )
    assert result.returncode == 0, (
        f"global-history recent failed: stderr={result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    events = data.get("events", [])
    # All 3 records MUST appear (timestamps are after 2020-01-01)
    assert len(events) == 3, (
        f"expected 3 records, got {len(events)}: {events}"
    )
    # Each must be tagged source=modules
    for e in events:
        assert e["source"] == "modules"
    # Actions / events from selfdef should be preserved
    actions = [e.get("action") for e in events]
    assert "installed" in actions or any(
        "installed" in str(a) for a in actions
    )


def test_reader_filters_by_since_correctly(tmp_path):
    """R465: --since cutoff MUST honor selfdef-emitted timestamps."""
    log_path = tmp_path / "modules.jsonl"
    log_path.write_text(json.dumps({
        "timestamp": "2020-01-01T00:00:00Z",
        "source": "modules",
        "module": "old",
        "event": "ancient",
        "status": "ok",
    }) + "\n")
    # --since in the future = zero results
    result = subprocess.run(
        ["python3", str(GH_PY), "recent",
         "--source", "modules",
         "--since", "2099-01-01T00:00:00Z",
         "--json"],
        capture_output=True, text=True, timeout=10,
        env={**os.environ,
             "SOVEREIGN_OS_MODULES_LOG": str(log_path)},
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data.get("events", []) == []


def test_reader_skips_malformed_lines(tmp_path):
    """R465: best-effort reader — bad lines don't kill the stream."""
    log_path = tmp_path / "modules.jsonl"
    body = "\n".join([
        "not-json",
        json.dumps({
            "timestamp": "2026-05-18T15:00:00Z",
            "source": "modules",
            "module": "ok-record",
            "event": "ok",
            "status": "ok",
        }),
        "{broken",
        "",
    ])
    log_path.write_text(body)
    result = subprocess.run(
        ["python3", str(GH_PY), "recent",
         "--source", "modules",
         "--since", "2020-01-01T00:00:00Z",
         "--json"],
        capture_output=True, text=True, timeout=10,
        env={**os.environ,
             "SOVEREIGN_OS_MODULES_LOG": str(log_path)},
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    events = data.get("events", [])
    assert len(events) == 1
    assert events[0].get("source") == "modules"


def test_legacy_env_var_still_honored_as_fallback(tmp_path):
    """R465: backwards compatibility — older env var name still works
    when the cross-repo name is absent."""
    log_path = tmp_path / "modules.jsonl"
    log_path.write_text(json.dumps({
        "timestamp": "2026-05-18T15:00:00Z",
        "source": "modules",
        "module": "via-legacy-env",
        "event": "ok",
        "status": "ok",
    }) + "\n")
    env = {k: v for k, v in os.environ.items()
           if k != "SOVEREIGN_OS_MODULES_LOG"}
    env["SOVEREIGN_OS_GLOBAL_HISTORY_MODULES_LOG"] = str(log_path)
    result = subprocess.run(
        ["python3", str(GH_PY), "recent",
         "--source", "modules",
         "--since", "2020-01-01T00:00:00Z",
         "--json"],
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    events = data.get("events", [])
    assert len(events) == 1


def test_cross_repo_env_var_takes_precedence(tmp_path):
    """R465: when BOTH env vars are set, the cross-repo name
    (SOVEREIGN_OS_MODULES_LOG) MUST win."""
    primary = tmp_path / "primary.jsonl"
    legacy = tmp_path / "legacy.jsonl"
    primary.write_text(json.dumps({
        "timestamp": "2026-05-18T15:00:00Z",
        "source": "modules",
        "module": "primary-wins",
        "event": "ok",
        "status": "ok",
    }) + "\n")
    legacy.write_text(json.dumps({
        "timestamp": "2026-05-18T15:00:00Z",
        "source": "modules",
        "module": "legacy-loses",
        "event": "ok",
        "status": "ok",
    }) + "\n")
    env = {**os.environ,
           "SOVEREIGN_OS_MODULES_LOG": str(primary),
           "SOVEREIGN_OS_GLOBAL_HISTORY_MODULES_LOG": str(legacy)}
    result = subprocess.run(
        ["python3", str(GH_PY), "recent",
         "--source", "modules",
         "--since", "2020-01-01T00:00:00Z",
         "--json"],
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    events = data.get("events", [])
    assert len(events) == 1
    # The "detail" field is a stringified-dump in global-history;
    # check for the module name there.
    blob = json.dumps(events[0])
    assert "primary-wins" in blob, (
        f"expected primary-wins record; got {blob}"
    )
