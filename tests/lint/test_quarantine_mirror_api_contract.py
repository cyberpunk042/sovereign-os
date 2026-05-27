"""M060 D-17 (R10121-R10122) — quarantine mirror API + webapp contract.

CROSS-REPO READ-ONLY MIRROR (closes the MS042 loop: selfdef /v1/quarantine
source ← sovereign-os mirror). The dashboard HTML shipped with inline MOCK +
referenced /api/d-17/*; this locks the full §1g stack + the frontend rewire:

  core    scripts/mirror/selfdef-quarantine-mirror.py
  cli     sovereign-osctl quarantine-mirror {snapshot,summaries}
  api     scripts/operator/quarantine-mirror-api.py
  webapp  webapp/d-17-quarantine/index.html (now fetches /api/d-17/*)
  service systemd/system/sovereign-quarantine-mirror-api.service

Authoritative quarantine archive lives in selfdef (MS042, SDD-064). sovereign-os
renders it READ-ONLY — trace/release/forfeit are selfdefctl + MS003 (IPS) only.
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
CORE = REPO_ROOT / "scripts" / "mirror" / "selfdef-quarantine-mirror.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "quarantine-mirror-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-quarantine-mirror-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-17-quarantine" / "index.html"

_MIRROR = {
    "schema_version": "1.0.0", "captured_at": "2026-05-27T20:00Z",
    "summaries": [{"severity": "critical", "quarantined": 1, "released_24h": 0,
                   "forfeited_24h": 1}],
    "entries": [
        {"quarantine_id": "qr-001", "tool": "untrusted-bin", "declarer": "ext-fp",
         "blocked_at": "2026-05-27T19:30Z", "updated_at": "2026-05-27T19:30Z",
         "state": "quarantined", "max_severity": "critical",
         "mismatches": [{"field": "secret_access", "declared": "none",
                         "observed": "keyring:x", "severity": "critical"}],
         "trace_id": "t1"},
        {"quarantine_id": "qr-bad", "state": "weird"},  # invalid state normalised
    ],
}


def _write_mirror() -> str:
    fd, path = tempfile.mkstemp(prefix="quarantine-mirror-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_MIRROR, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, mirror: str):
    env = {
        "QUARANTINE_MIRROR_API_BIND": "127.0.0.1",
        "QUARANTINE_MIRROR_API_PORT": str(port),
        "SOVEREIGN_OS_SELFDEF_QUARANTINE_MIRROR": mirror,
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
    raise RuntimeError("quarantine-mirror-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_projects_mirror():
    assert CORE.is_file(), f"core missing: {CORE}"
    mirror = _write_mirror()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "snapshot", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_SELFDEF_QUARANTINE_MIRROR": mirror},
        )
        d = json.loads(out.stdout)
        assert d["mirror_status"] == "online"
        assert [s["severity"] for s in d["summaries"]] == [
            "critical", "major", "minor", "informational"]
        ids = {e["quarantine_id"] for e in d["entries"]}
        assert ids == {"qr-001", "qr-bad"}
        bad = [e for e in d["entries"] if e["quarantine_id"] == "qr-bad"][0]
        assert bad["state"] == "quarantined"  # invalid 'weird' normalised
    finally:
        os.unlink(mirror)


def test_core_offline_graceful():
    out = subprocess.run(
        ["python3", str(CORE), "snapshot", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_SELFDEF_QUARANTINE_MIRROR": "/tmp/sovereign-os-no-quar-mirror.json"},
    )
    d = json.loads(out.stdout)
    assert d["mirror_status"] == "offline"
    assert len(d["summaries"]) == 4 and d["entries"] == []


def test_frontend_rewired_to_live_mirror():
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-17/snapshot" in html
    assert "publisher /api/d-17/snapshot when wired" not in html
    assert "trace-untrust" not in html and "shell-runner-evil" not in html
    assert "READ-ONLY" in html or "read-only" in html


def test_api_daemon_present():
    assert API_DAEMON.is_file()


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [ln for ln in body.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    found = False
    for ln in active:
        if "QUARANTINE_MIRROR_API_BIND=" in ln:
            assert "QUARANTINE_MIRROR_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "QUARANTINE_MIRROR_API_BIND=0.0.0.0" not in ln, ln
    assert found


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_quarantine_mirror():
    body = OSCTL.read_text(encoding="utf-8")
    assert "quarantine-mirror)" in body
    assert "scripts/mirror/selfdef-quarantine-mirror.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"quarantine-mirror"' in body and "8114" in body


# ---- live endpoints --------------------------------------------------------

def test_snapshot_endpoint_matches_dashboard_contract():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        status, d = _get(port, "/api/d-17/snapshot")
        assert status == 200
        assert set(d) >= {"mirror_status", "summaries", "entries"}
        e = d["entries"][0]
        for k in ("quarantine_id", "tool", "declarer", "state", "max_severity", "mismatches"):
            assert k in e
        m = e["mismatches"][0]
        for k in ("field", "declared", "observed", "severity"):
            assert k in m
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_offline_endpoint_graceful():
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-no-quar-mirror.json")
    try:
        _, d = _get(port, "/api/d-17/snapshot")
        assert d["mirror_status"] == "offline" and d["entries"] == []
        assert len(d["summaries"]) == 4
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
        assert "D-17" in html and "quarantine" in html
        assert "/api/d-17/snapshot" in html
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_readonly_mutation_rejected():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        for method in ("POST", "PUT", "DELETE"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/d-17/snapshot", method=method, data=b"{}")
            try:
                urllib.request.urlopen(req, timeout=3)
                raised = False
            except urllib.error.HTTPError as e:
                raised = (e.code == 405)
            assert raised, f"{method} must be 405 (read-only mirror)"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_version_declares_mirror_doctrine():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-17-quarantine"
        assert "READ-ONLY" in d["mirror_doctrine"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)
