"""M060 D-16 (R10120) — audit-chain mirror API + webapp contract.

CROSS-REPO READ-ONLY MIRROR: selfdef MS016 SHA-256-chained, MS049 13-field-
spanned, MS026 OCSF-categorized, MS003 verify-only audit chain source ←
sovereign-os D-16 mirror. The chain is APPEND-ONLY by MS016 R03567 doctrine —
the operator has NO mutation surface (no release, no replay, no edit); verify
/ show / export are selfdefctl + MS003 (IPS) only. This locks the full §1g
stack:

  core    scripts/mirror/selfdef-audit-mirror.py
  cli     sovereign-osctl audit-mirror {snapshot,integrity}
  api     scripts/operator/audit-mirror-api.py
  webapp  webapp/d-16-audit/index.html (fetches /api/d-16/*)
  service systemd/system/sovereign-audit-mirror-api.service

The audit chain is the IPS truth — every mutation verb on this surface → 405.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE = REPO_ROOT / "scripts" / "mirror" / "selfdef-audit-mirror.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "audit-mirror-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-audit-mirror-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-16-audit" / "index.html"

_MIRROR = {
    "schema_version": "1.0.0",
    "captured_at": "2027-01-15T08:00:00Z",
    "summaries": [
        {"category": "authority_decision", "total": 2,
         "allow": 1, "deny": 1, "ask": 0, "sandbox": 0},
        {"category": "process_activity", "total": 1,
         "allow": 1, "deny": 0, "ask": 0, "sandbox": 0},
    ],
    "integrity": {
        "head_hash": "b" * 64,
        "total_entries": 3,
        "continuous": True,
        "first_gap_at": None,
        "verified_at": "2027-01-15T08:00:00Z",
    },
    "spans": [
        {"trace_id": "t1", "profile": "careful", "model": "qwen3-coder-32b",
         "provider": "local-cuda", "hardware": "3090_logic",
         "tokens_prompt": 100, "tokens_completion": 50, "latency_ms": 1500,
         "cost_millicents": 5, "risk_score": 12, "memory_refs": [],
         "tool_refs": ["read-only-host"], "policy_result": "allow",
         "branch_id": "b1", "ocsf_category": "authority_decision",
         "closed_at": "2027-01-15T08:00:00Z",
         "prev_chain_hash": "", "chain_hash": "a" * 64, "signature": "s1"},
    ],
    "signature": "",
}


def _write_mirror() -> str:
    fd, path = tempfile.mkstemp(prefix="audit-mirror-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_MIRROR, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, mirror: str):
    env = {
        "AUDIT_MIRROR_API_BIND": "127.0.0.1",
        "AUDIT_MIRROR_API_PORT": str(port),
        "SOVEREIGN_OS_SELFDEF_AUDIT_MIRROR": mirror,
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen(
        ["python3", str(API_DAEMON)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    deadline = time.time() + 6
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("audit-mirror-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_projects_mirror_with_integrity():
    assert CORE.is_file(), f"core missing: {CORE}"
    mirror = _write_mirror()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "snapshot", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_SELFDEF_AUDIT_MIRROR": mirror},
        )
        d = json.loads(out.stdout)
        assert d["mirror_status"] == "online"
        assert d["integrity"]["total_entries"] == 3
        assert d["integrity"]["continuous"] is True
        assert d["integrity"]["head_hash"] == "b" * 64
        assert [s["trace_id"] for s in d["spans"]] == ["t1"]
        # spans preserve the chain-hash chain (prev → curr)
        assert d["spans"][0]["chain_hash"] == "a" * 64
        assert d["spans"][0]["prev_chain_hash"] == ""
    finally:
        os.unlink(mirror)


def test_core_offline_graceful():
    out = subprocess.run(
        ["python3", str(CORE), "snapshot", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_SELFDEF_AUDIT_MIRROR": "/tmp/sovereign-os-no-audit-mirror.json"},
    )
    d = json.loads(out.stdout)
    assert d["mirror_status"] == "offline"
    assert d["spans"] == []
    # integrity defaults are honest-empty (NOT fabricated valid state)
    assert d["integrity"]["total_entries"] == 0
    assert d["integrity"]["head_hash"] == ""


def test_integrity_subcommand_returns_integrity_only():
    mirror = _write_mirror()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "integrity", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_SELFDEF_AUDIT_MIRROR": mirror},
        )
        d = json.loads(out.stdout)
        # integrity subcommand returns the bare integrity object,
        # not the full snapshot (no `spans` or `summaries` keys)
        assert "head_hash" in d and "continuous" in d
        assert "spans" not in d and "summaries" not in d
    finally:
        os.unlink(mirror)


def test_frontend_fetches_live_mirror():
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-16/snapshot" in html
    # webapp must reflect the append-only doctrine — no mutation buttons
    # promising release/replay/edit, only verify/show/export copy-helpers
    assert "release" not in html.lower() or "release " not in html.lower()
    assert "READ-ONLY" in html or "read-only" in html
    assert "APPEND-ONLY" in html or "append-only" in html


def test_api_daemon_present():
    assert API_DAEMON.is_file()


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [ln for ln in body.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    found = False
    for ln in active:
        if "AUDIT_MIRROR_API_BIND=" in ln:
            assert "AUDIT_MIRROR_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "AUDIT_MIRROR_API_BIND=0.0.0.0" not in ln, ln
    assert found


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_audit_mirror():
    body = OSCTL.read_text(encoding="utf-8")
    assert "audit-mirror)" in body
    assert "scripts/mirror/selfdef-audit-mirror.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"audit-mirror"' in body and "8121" in body
    assert '"audit-mirror": "d-16-audit"' in body


# ---- live endpoints --------------------------------------------------------

def test_snapshot_endpoint_matches_dashboard_contract():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        status, d = _get(port, "/api/d-16/snapshot")
        assert status == 200
        assert set(d) >= {"mirror_status", "summaries", "integrity", "spans"}
        # integrity shape locked
        assert set(d["integrity"]) >= {"head_hash", "total_entries",
                                       "continuous", "first_gap_at", "verified_at"}
        # span shape locked
        s = d["spans"][0]
        for k in ("trace_id", "profile", "model", "provider", "hardware",
                  "tokens_prompt", "tokens_completion", "latency_ms",
                  "cost_millicents", "risk_score", "memory_refs", "tool_refs",
                  "policy_result", "branch_id", "ocsf_category", "closed_at",
                  "prev_chain_hash", "chain_hash", "signature"):
            assert k in s, f"missing span field: {k}"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_integrity_endpoint_returns_integrity_only():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        status, d = _get(port, "/api/d-16/integrity")
        assert status == 200
        assert "head_hash" in d and "total_entries" in d
        # bare integrity, not the snapshot wrapper
        assert "spans" not in d and "summaries" not in d
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_offline_endpoint_graceful():
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-no-audit-mirror.json")
    try:
        _, d = _get(port, "/api/d-16/snapshot")
        assert d["mirror_status"] == "offline"
        assert d["spans"] == []
        assert d["integrity"]["total_entries"] == 0
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_webapp_served():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-16" in html and "audit" in html.lower()
        assert "/api/d-16/snapshot" in html
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_readonly_mutation_rejected():
    """Audit chain is APPEND-ONLY (MS016 R03567); no release/replay/edit."""
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        for method in ("POST", "PUT", "DELETE"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/d-16/snapshot",
                method=method, data=b"{}")
            try:
                urllib.request.urlopen(req, timeout=3)
                raised = False
            except urllib.error.HTTPError as e:
                raised = (e.code == 405)
            assert raised, f"{method} must be 405 (append-only chain)"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_version_declares_mirror_doctrine():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-16-audit"
        assert "READ-ONLY" in d["mirror_doctrine"]
        assert "APPEND-ONLY" in d["mirror_doctrine"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)
