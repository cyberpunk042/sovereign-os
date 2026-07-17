"""M060 D-06 (R10088-R10092) — pending-approvals API + webapp surface contract.

Drives the D-06 cockpit dashboard from a shell to PRODUCTION: the dashboard
HTML existed but fetched `/api/approvals/pending` (+ `/api/operator-key/status`
+ `/stream`) with no backend. This locks the full §1g 8-surface stack:

  core    scripts/lifecycle/approval-queue.py  (queue + M065 gates + key presence)
  cli     sovereign-osctl approvals {pending,gates,key}
  api     scripts/operator/approvals-api.py  (read-only HTTP)
  webapp  webapp/d-06-pending-approvals/index.html   (served by the api)
  service systemd/system/sovereign-approvals-api.service

The core reads the approval queue + M065 Five Stage Gate state, and reports
MS003 operator-key PRESENCE only (never reads the key material). Operator
axiom (M065): "No PR opens past a gate without operator sign-off." Per §1g
(verbatim): "We do not minimize anything." Read-only — approve/deny/defer are
MS003-signed CLI verbs.
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
CORE = REPO_ROOT / "scripts" / "lifecycle" / "approval-queue.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "approvals-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-approvals-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-06-pending-approvals" / "index.html"

_QUEUE = {
    "profile": "autonomous",
    "gates": {"SG1": "signed", "SG2": "signed", "SG3": "pending",
              "SG4": "pending", "SG5": "bypassed"},
    "approvals": [
        {"id": "appr-001", "title": "L5 Commit: apply parser fix", "severity": "high",
         "gate": "L5→L6", "actor": "Logic Engine", "kind": "commit", "profile": "careful",
         "ts": "2026-05-27T18:30:00Z", "trace_id": "t-aaaa",
         "summary": "diff touches parser.rs; tests pass", "context": "3 files, +42 -12",
         "diff_url": "http://localhost/diff/1"},
        {"id": "appr-002", "title": "Ring 4 cloud call", "severity": "critical",
         "gate": "L4→L5", "actor": "Oracle Core", "kind": "cloud_call",
         "profile": "production", "ts": "2026-05-27T17:00:00Z",
         "summary": "external API for claim verification"},
        {"id": "appr-bad", "severity": "weird"},  # malformed → severity normalised
    ],
}
_KEY_STATUS = {"fingerprint": "SHA256:abcd1234", "source": "hardware-token",
               "expires_at": "2026-12-31T00:00:00Z", "hardware_token": True}


def _write_fixtures() -> tuple[str, str]:
    fd, queue = tempfile.mkstemp(prefix="approvals-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_QUEUE, fh)
    fd2, key = tempfile.mkstemp(prefix="keystatus-", suffix=".json")
    with os.fdopen(fd2, "w", encoding="utf-8") as fh:
        json.dump(_KEY_STATUS, fh)
    return queue, key


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, queue: str, key: str):
    env = {
        "APPROVALS_API_BIND": "127.0.0.1",
        "APPROVALS_API_PORT": str(port),
        "SOVEREIGN_OS_APPROVALS": queue,
        "SOVEREIGN_OS_OPERATOR_KEY_STATUS": key,
        "SOVEREIGN_OS_OPERATOR_KEY": "/tmp/sovereign-os-no-such-key",
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
    raise RuntimeError("approvals-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_present_and_aggregates():
    assert CORE.is_file(), f"core missing: {CORE}"
    queue, key = _write_fixtures()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "pending", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_APPROVALS": queue},
        )
        d = json.loads(out.stdout)
        assert set(d) >= {"approvals", "gates", "profile", "summary"}
        assert d["summary"] == {"pending": 3, "critical": 1, "high": 1,
                                "oldest_ts": "2026-05-27T17:00:00Z"}
        # critical sorts first; malformed severity normalised to medium
        assert d["approvals"][0]["id"] == "appr-002"
        assert [a["severity"] for a in d["approvals"] if a["id"] == "appr-bad"] == ["medium"]
        assert d["profile"] == "autonomous"
    finally:
        os.unlink(queue); os.unlink(key)


def test_core_m065_stage_gates():
    """The M065 Five Stage Gates SG1-SG5 must be present with after-PR + desc,
    and gate state validated against {pending,signed,bypassed}."""
    queue, key = _write_fixtures()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "gates", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_APPROVALS": queue},
        )
        g = json.loads(out.stdout)
        assert set(g) == {"SG1", "SG2", "SG3", "SG4", "SG5"}
        assert g["SG1"]["after_pr"] == 3 and "structural" in g["SG1"]["description"]
        assert g["SG5"]["after_pr"] == 10
        assert g["SG1"]["state"] == "signed" and g["SG5"]["state"] == "bypassed"
    finally:
        os.unlink(queue); os.unlink(key)


def test_core_operator_key_presence_only():
    """Key status reports presence + published fingerprint; never reads key material."""
    queue, key = _write_fixtures()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "key", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_OPERATOR_KEY_STATUS": key,
                 "SOVEREIGN_OS_OPERATOR_KEY": "/tmp/sovereign-os-no-such-key"},
        )
        k = json.loads(out.stdout)
        assert k["loaded"] is True and k["fingerprint"] == "SHA256:abcd1234"
        assert k["hardware_token"] is True
    finally:
        os.unlink(queue); os.unlink(key)


def test_api_daemon_present():
    assert API_DAEMON.is_file(), f"api daemon missing: {API_DAEMON}"


def test_systemd_unit_present():
    assert SYSTEMD_UNIT.is_file(), f"service unit missing: {SYSTEMD_UNIT}"


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [ln for ln in body.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    found = False
    for ln in active:
        if "APPROVALS_API_BIND=" in ln:
            assert "APPROVALS_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "APPROVALS_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set APPROVALS_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_approvals():
    body = OSCTL.read_text(encoding="utf-8")
    assert "approvals)" in body, "osctl missing approvals dispatch case"
    assert "scripts/lifecycle/approval-queue.py" in body


def test_master_dashboard_route_registered():
    # F-2026-072: the aggregator route table moved to the generated
    # config/dashboard-routes.yaml and uses the canonical catalog slug.
    routes = (REPO_ROOT / "config" / "dashboard-routes.yaml").read_text(encoding="utf-8")
    assert "d-06-pending-approvals" in routes, "aggregator table missing d-06-pending-approvals route"
    assert "8110" in routes, "d-06-pending-approvals route must declare port 8110"


# ---- live endpoints (the exact d-06 fetch contract) -----------------------

def test_pending_endpoint_matches_dashboard_contract():
    queue, key = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, queue, key)
    try:
        status, d = _get(port, "/api/approvals/pending")
        assert status == 200
        assert set(d) >= {"approvals", "gates", "profile", "summary"}
        for k in ("pending", "critical", "high", "oldest_ts"):
            assert k in d["summary"]
        for g in ("SG1", "SG2", "SG3", "SG4", "SG5"):
            assert g in d["gates"]
        a = d["approvals"][0]
        for k in ("id", "title", "severity", "gate", "actor", "kind", "profile", "ts"):
            assert k in a
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(queue); os.unlink(key)


def test_operator_key_status_endpoint():
    queue, key = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, queue, key)
    try:
        _, d = _get(port, "/api/operator-key/status")
        assert d["loaded"] is True and d["fingerprint"] == "SHA256:abcd1234"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(queue); os.unlink(key)


def test_empty_queue_graceful():
    _, key = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-nonexistent-approvals.json", key)
    try:
        _, d = _get(port, "/api/approvals/pending")
        assert d["approvals"] == [] and d["summary"]["pending"] == 0
        assert all(v == "pending" for v in d["gates"].values())
        assert d["profile"] == "private"  # MS040 R09535 offline default
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(key)


def test_webapp_served():
    queue, key = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, queue, key)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-06" in html and "pending approvals" in html
        assert "/api/approvals/pending" in html  # the dashboard fetches our endpoint
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(queue); os.unlink(key)


def test_readonly_post_rejected():
    queue, key = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, queue, key)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/approvals/pending", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (read-only surface)"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(queue); os.unlink(key)


def test_version_endpoint():
    queue, key = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, queue, key)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-06-pending-approvals"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(queue); os.unlink(key)
