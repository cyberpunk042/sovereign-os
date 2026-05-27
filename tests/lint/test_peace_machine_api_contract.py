"""M060 D-20 (R10126-R10128) — peace-machine-health API + webapp contract.

The LAST of the 21 M060 cockpit dashboards. sovereign-os-NATIVE (M059 sovereign
close). The dashboard HTML shipped with an inline MOCK + referenced /api/d-20/*;
this locks the full §1g stack + the frontend rewire:

  core    scripts/manifest/peace-machine.py  (5 M059 properties + live verdict)
  cli     sovereign-osctl peace-machine {snapshot,properties}
  api     scripts/operator/peace-machine-api.py
  webapp  webapp/d-20-peace-machine-health/index.html (now fetches /api/d-20/*)
  service systemd/system/sovereign-peace-machine-api.service

The 5 peace-machine properties (powerful/disciplined/reversible/flexible/
sovereign, dump 18338-18341) are static M059 doctrine; the live verdict is read
from the sovereign-os-peace-check validator. Read-only — the validator computes,
the dashboard renders; absent validator → "unknown" (never fabricates a PASS).
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
CORE = REPO_ROOT / "scripts" / "manifest" / "peace-machine.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "peace-machine-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-peace-machine-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-20-peace-machine-health" / "index.html"

_CHECK = {
    "overall": "degraded", "captured_at": "2026-05-27T20:00:00Z", "exit_code": 1,
    "properties": {"powerful": "healthy", "disciplined": "healthy",
                   "reversible": "healthy", "flexible": "degraded", "sovereign": "healthy"},
    "validator_log": [{"cls": "ok", "text": "peace-check START"},
                      {"cls": "warn", "text": "property 4/5 flexible PARTIAL"}],
}
_PROP_KEYS = ("powerful", "disciplined", "reversible", "flexible", "sovereign")


def _write_check() -> str:
    fd, path = tempfile.mkstemp(prefix="peace-check-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_CHECK, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, check: str):
    env = {
        "PEACE_MACHINE_API_BIND": "127.0.0.1",
        "PEACE_MACHINE_API_PORT": str(port),
        "SOVEREIGN_OS_PEACE_CHECK": check,
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
    raise RuntimeError("peace-machine-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_5_m059_properties_verbatim():
    assert CORE.is_file(), f"core missing: {CORE}"
    out = subprocess.run(
        ["python3", str(CORE), "properties", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_PEACE_CHECK": "/tmp/sovereign-os-no-peace.json"},
    )
    props = json.loads(out.stdout)
    assert [p["key"] for p in props] == list(_PROP_KEYS)
    # M059 verbatim quotes
    quotes = {p["key"]: p["quote"] for p in props}
    assert quotes["powerful"] == "powerful enough to act"
    assert quotes["sovereign"] == "sovereign enough that intelligence remains in the user's hands"


def test_core_offline_never_fabricates_pass():
    """Absent validator → every property 'unknown' + overall 'unknown' — the
    core NEVER reports a PASS it can't verify."""
    out = subprocess.run(
        ["python3", str(CORE), "snapshot", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_PEACE_CHECK": "/tmp/sovereign-os-no-peace.json"},
    )
    d = json.loads(out.stdout)
    assert d["validator_status"] == "offline"
    assert d["overall"] == "unknown" and d["exit_code"] is None
    assert all(p["status"] == "unknown" for p in d["properties"])


def test_core_online_verdict():
    check = _write_check()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "snapshot", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_PEACE_CHECK": check},
        )
        d = json.loads(out.stdout)
        assert d["validator_status"] == "online"
        assert d["overall"] == "degraded" and d["exit_code"] == 1
        by = {p["key"]: p["status"] for p in d["properties"]}
        assert by["flexible"] == "degraded" and by["powerful"] == "healthy"
    finally:
        os.unlink(check)


def test_api_daemon_present():
    assert API_DAEMON.is_file()


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [ln for ln in body.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    found = False
    for ln in active:
        if "PEACE_MACHINE_API_BIND=" in ln:
            assert "PEACE_MACHINE_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "PEACE_MACHINE_API_BIND=0.0.0.0" not in ln, ln
    assert found


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_peace_machine():
    body = OSCTL.read_text(encoding="utf-8")
    assert "peace-machine)" in body
    assert "scripts/manifest/peace-machine.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"peace-machine"' in body and "8120" in body


def test_frontend_rewired_to_live_api():
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-20/snapshot" in html
    assert "publisher /api/d-20/snapshot" not in html
    assert "sovereign-os-peace-check START (R09980)" not in html  # mock log gone
    assert "READ" in html or "read-only" in html or "Read-only" in html


# ---- live endpoints --------------------------------------------------------

def test_snapshot_endpoint_matches_dashboard_contract():
    check = _write_check()
    port = _free_port()
    proc = _spawn_api(port, check)
    try:
        status, d = _get(port, "/api/d-20/snapshot")
        assert status == 200
        assert set(d) >= {"overall", "exit_code", "properties", "validator_log"}
        assert len(d["properties"]) == 5
        for p in d["properties"]:
            for k in ("key", "name", "quote", "backed", "status"):
                assert k in p
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(check)


def test_offline_endpoint_graceful():
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-no-peace.json")
    try:
        _, d = _get(port, "/api/d-20/snapshot")
        assert d["overall"] == "unknown"
        assert all(p["status"] == "unknown" for p in d["properties"])
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_webapp_served():
    check = _write_check()
    port = _free_port()
    proc = _spawn_api(port, check)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-20" in html and "peace machine" in html
        assert "/api/d-20/snapshot" in html
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(check)


def test_readonly_post_rejected():
    check = _write_check()
    port = _free_port()
    proc = _spawn_api(port, check)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/d-20/snapshot", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (validator computes, not set here)"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(check)


def test_version_endpoint():
    check = _write_check()
    port = _free_port()
    proc = _spawn_api(port, check)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-20-peace-machine-health"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(check)
