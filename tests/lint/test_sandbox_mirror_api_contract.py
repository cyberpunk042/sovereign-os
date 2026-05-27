"""M060 D-15 (R10118-R10119) — sandboxes mirror API + webapp contract.

CROSS-REPO READ-ONLY MIRROR (completes the 4 selfdef-mirror cockpit dashboards:
D-13/D-15/D-17/D-18). The dashboard HTML shipped with inline MOCK + referenced
/api/d-15/*; this locks the full §1g stack + the frontend rewire:

  core    scripts/mirror/selfdef-sandbox-mirror.py
  cli     sovereign-osctl sandbox-mirror {snapshot,summaries}
  api     scripts/operator/sandbox-mirror-api.py
  webapp  webapp/d-15-sandboxes/index.html (now fetches /api/d-15/*)
  service systemd/system/sovereign-sandbox-mirror-api.service

Authoritative sandbox-allocation state lives in selfdef (MS032/MS036).
sovereign-os renders READ-ONLY — checkpoint/release are selfdefctl + MS003 (IPS).
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
CORE = REPO_ROOT / "scripts" / "mirror" / "selfdef-sandbox-mirror.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "sandbox-mirror-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-sandbox-mirror-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-15-sandboxes" / "index.html"

_MIRROR = {
    "schema_version": "1.0.0", "captured_at": "2026-05-27T20:00Z",
    "summaries": [{"tier": "tier-a", "running": 4, "idle": 1, "released_24h": 12},
                  {"tier": "tier-d", "checkpointed": 1, "quarantined": 1}],
    "allocations": [
        {"allocation_id": "al-01", "tier": "tier-a", "ms032_tier": 1,
         "isolation": "host_seccomp", "tool": "rg", "profile": "private",
         "actor": "operator-fp", "allocated_at": "2026-05-27T19:00Z",
         "release_at": "2026-05-27T19:30Z", "ttl_seconds": 1800,
         "resident_mb": 28, "cpu_percent": 8, "state": "running", "trace_id": "t1"},
        {"allocation_id": "al-bad", "tier": "bogus"},  # invalid tier → dropped
    ],
}


def _write_mirror() -> str:
    fd, path = tempfile.mkstemp(prefix="sandbox-mirror-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_MIRROR, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, mirror: str):
    env = {
        "SANDBOX_MIRROR_API_BIND": "127.0.0.1",
        "SANDBOX_MIRROR_API_PORT": str(port),
        "SOVEREIGN_OS_SELFDEF_SANDBOX_MIRROR": mirror,
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
    raise RuntimeError("sandbox-mirror-api failed to start within 6s")


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
            env={**os.environ, "SOVEREIGN_OS_SELFDEF_SANDBOX_MIRROR": mirror},
        )
        d = json.loads(out.stdout)
        assert d["mirror_status"] == "online"
        assert [s["tier"] for s in d["summaries"]] == ["tier-a", "tier-b", "tier-c", "tier-d"]
        assert [a["allocation_id"] for a in d["allocations"]] == ["al-01"]  # bogus tier dropped
    finally:
        os.unlink(mirror)


def test_core_offline_graceful():
    out = subprocess.run(
        ["python3", str(CORE), "snapshot", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_SELFDEF_SANDBOX_MIRROR": "/tmp/sovereign-os-no-sandbox-mirror.json"},
    )
    d = json.loads(out.stdout)
    assert d["mirror_status"] == "offline"
    assert len(d["summaries"]) == 4 and d["allocations"] == []


def test_frontend_rewired_to_live_mirror():
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-15/snapshot" in html
    assert "publisher /api/d-15/snapshot when wired" not in html
    assert "criu-paused" not in html and "firecracker_microvm\",tool" not in html
    assert "READ-ONLY" in html or "read-only" in html


def test_api_daemon_present():
    assert API_DAEMON.is_file()


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [ln for ln in body.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    found = False
    for ln in active:
        if "SANDBOX_MIRROR_API_BIND=" in ln:
            assert "SANDBOX_MIRROR_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "SANDBOX_MIRROR_API_BIND=0.0.0.0" not in ln, ln
    assert found


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_sandbox_mirror():
    body = OSCTL.read_text(encoding="utf-8")
    assert "sandbox-mirror)" in body
    assert "scripts/mirror/selfdef-sandbox-mirror.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"sandbox-mirror"' in body and "8116" in body


# ---- live endpoints --------------------------------------------------------

def test_snapshot_endpoint_matches_dashboard_contract():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        status, d = _get(port, "/api/d-15/snapshot")
        assert status == 200
        assert set(d) >= {"mirror_status", "summaries", "allocations"}
        a = d["allocations"][0]
        for k in ("allocation_id", "tier", "ms032_tier", "isolation", "tool",
                  "profile", "state", "resident_mb", "cpu_percent", "release_at"):
            assert k in a
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_offline_endpoint_graceful():
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-no-sandbox-mirror.json")
    try:
        _, d = _get(port, "/api/d-15/snapshot")
        assert d["mirror_status"] == "offline" and d["allocations"] == []
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
        assert "D-15" in html and "sandboxes" in html
        assert "/api/d-15/snapshot" in html
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_readonly_mutation_rejected():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        for method in ("POST", "PUT", "DELETE"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/d-15/snapshot", method=method, data=b"{}")
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
        assert d["module"] == "d-15-sandboxes"
        assert "READ-ONLY" in d["mirror_doctrine"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)
