"""M060 D-01 (R10059-R10062) — active-sessions API + webapp surface contract.

Drives the D-01 cockpit dashboard from a shell to PRODUCTION: the dashboard
HTML existed but fetched `/api/sessions/active` (+ `/stream`) with no backend.
This locks the full §1g 8-surface stack now wired:

  core    scripts/lifecycle/session-registry.py  (M057 lifecycle projection)
  cli     sovereign-osctl sessions {active,summary,steps}
  api     scripts/operator/sessions-api.py  (read-only HTTP)
  webapp  webapp/d-01-active-sessions/index.html   (served by the api)
  service systemd/system/sovereign-sessions-api.service

The core reads the M057 lifecycle-engine session registry and projects each
task onto the 12-step lifecycle + the 9 task states (E0556). Per operator §1g
(verbatim): "We do not minimize anything." Read-only — hibernate/resume/kill
are MS003-signed CLI verbs.
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
CORE = REPO_ROOT / "scripts" / "lifecycle" / "session-registry.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "sessions-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-sessions-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-01-active-sessions" / "index.html"

# active + hibernated + blocked(waiting_user) + completed + a malformed entry.
_FIXTURE = {"sessions": [
    {"id": "sess-a1b2c3d4e5f6", "kind": "code", "profile": "careful", "state": "active",
     "step": 7, "srp_agent": "Logic Engine", "started_at": "2026-05-27T18:00:00Z",
     "eta_seconds": 900, "branch_count": 2},
    {"id": "sess-bbbb", "kind": "research", "profile": "private", "state": "hibernated",
     "step": 4, "srp_agent": "Oracle Core", "started_at": "2026-05-27T16:00:00Z",
     "branch_count": 1},
    {"id": "sess-cccc", "kind": "admin", "profile": "production", "state": "waiting_user",
     "step": 10, "branch_count": 0},
    {"id": "sess-dddd", "kind": "code", "profile": "fast", "state": "completed",
     "step": 12, "branch_count": 3},
    {"id": "sess-bad", "state": "bogus", "step": 99},
]}


def _write_registry() -> str:
    fd, path = tempfile.mkstemp(prefix="sessions-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_FIXTURE, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, registry: str):
    env = {
        "SESSIONS_API_BIND": "127.0.0.1",
        "SESSIONS_API_PORT": str(port),
        "SOVEREIGN_OS_SESSION_REGISTRY": registry,
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
    raise RuntimeError("sessions-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_present_and_projects_m057():
    assert CORE.is_file(), f"core missing: {CORE}"
    reg = _write_registry()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "active", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_SESSION_REGISTRY": reg},
        )
        d = json.loads(out.stdout)
        assert set(d) >= {"sessions", "summary"}
        # summary buckets: active=1, hibernated=1, blocked(waiting_user)=1, branches=6
        assert d["summary"] == {"active": 1, "hibernated": 1, "blocked": 1, "branches": 6}
        # step clamped to 1..12 + named from the M057 12-step table
        bad = [s for s in d["sessions"] if s["id"] == "sess-bad"][0]
        assert bad["step"] == 12 and bad["step_name"] == "Resume/Archive"
        # a present-but-unknown state is passed through unchanged (not relabeled)
        assert bad["state"] == "bogus"
    finally:
        os.unlink(reg)


def test_core_m057_steps_and_states_reference():
    """The 12 lifecycle steps + 9 task states must match M057 verbatim."""
    out = subprocess.run(
        ["python3", str(CORE), "steps", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    d = json.loads(out.stdout)
    assert d["lifecycle_steps"] == [
        "Intake", "Normalize", "Profile Resolve", "Map", "Plan/Compile", "Route",
        "Execute", "Observe", "Evaluate", "Commit/Rollback", "Learn", "Resume/Archive"]
    assert d["task_states"] == [
        "active", "paused", "waiting_user", "waiting_tool", "hibernated",
        "completed", "failed", "rolled_back", "archived"]
    assert "Text is payload inside typed state" in d["law"]


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
        if "SESSIONS_API_BIND=" in ln:
            assert "SESSIONS_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "SESSIONS_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set SESSIONS_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_sessions():
    body = OSCTL.read_text(encoding="utf-8")
    assert "sessions)" in body, "osctl missing sessions dispatch case"
    assert "scripts/lifecycle/session-registry.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"sessions"' in body, "master-dashboard missing sessions route"
    assert "8109" in body, "sessions route must declare port 8109"


# ---- live endpoints (the exact d-01 fetch contract) -----------------------

def test_active_endpoint_matches_dashboard_contract():
    reg = _write_registry()
    port = _free_port()
    proc = _spawn_api(port, reg)
    try:
        status, d = _get(port, "/api/sessions/active")
        assert status == 200
        assert set(d) >= {"sessions", "summary"}
        for k in ("active", "hibernated", "blocked", "branches"):
            assert k in d["summary"]
        s = d["sessions"][0]
        for k in ("id", "kind", "profile", "state", "step", "srp_agent",
                  "started_at", "eta_seconds", "branch_count"):
            assert k in s
        assert 1 <= s["step"] <= 12
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(reg)


def test_empty_registry_graceful():
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-nonexistent-sessions.json")
    try:
        _, d = _get(port, "/api/sessions/active")
        assert d["sessions"] == []
        assert d["summary"] == {"active": 0, "hibernated": 0, "blocked": 0, "branches": 0}
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_webapp_served():
    reg = _write_registry()
    port = _free_port()
    proc = _spawn_api(port, reg)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-01" in html and "active sessions" in html
        assert "/api/sessions/active" in html  # the dashboard fetches our endpoint
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(reg)


def test_readonly_post_rejected():
    reg = _write_registry()
    port = _free_port()
    proc = _spawn_api(port, reg)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/sessions/active", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (read-only surface)"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(reg)


def test_version_endpoint():
    reg = _write_registry()
    port = _free_port()
    proc = _spawn_api(port, reg)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-01-active-sessions"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(reg)
