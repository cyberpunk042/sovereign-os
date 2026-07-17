"""M060 D-02 (R10063-R10068) — profile-choices mirror API + webapp contract.

CROSS-REPO READ-ONLY MIRROR — the LAST full dashboard of the 21-dashboard M060
catalog. The D-02 webapp already fetched /api/profile/show (the six-profile
envelopes are static client-side doctrine); this ships the backend mirror:

  core    scripts/mirror/selfdef-profile-mirror.py
  cli     sovereign-osctl profile-mirror show
  api     scripts/operator/profile-mirror-api.py  (serves /api/profile/show)
  webapp  webapp/d-02-profile-choices/index.html  (already fetches it)
  service systemd/system/sovereign-profile-mirror-api.service

Authoritative profile-authority state lives in selfdef (MS040 six-profile
matrix). sovereign-os renders READ-ONLY — profile switch is `sovereign profile
set` + MS003 (IPS). Offline → MS040 R09535 default (Private).
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
CORE = REPO_ROOT / "scripts" / "mirror" / "selfdef-profile-mirror.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "profile-mirror-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-profile-mirror-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-02-profile-choices" / "index.html"

_MIRROR = {
    "schema_version": "1.0.0", "active": "careful", "since": "2026-05-27T18:00Z",
    "actor": "operator-fp", "envelope": "L0-L4 gated · Ring 0-2",
    "history": [{"ts": "2026-05-27T18:00Z", "from": "private", "to": "careful",
                 "actor": "operator-fp", "rationale": "code session",
                 "signature": "sig-abc123def456"}],
}


def _write_mirror() -> str:
    fd, path = tempfile.mkstemp(prefix="profile-mirror-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_MIRROR, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, mirror: str):
    env = {
        "PROFILE_MIRROR_API_BIND": "127.0.0.1",
        "PROFILE_MIRROR_API_PORT": str(port),
        "SOVEREIGN_OS_SELFDEF_PROFILE_MIRROR": mirror,
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
    raise RuntimeError("profile-mirror-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_projects_mirror():
    assert CORE.is_file(), f"core missing: {CORE}"
    mirror = _write_mirror()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "show", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_SELFDEF_PROFILE_MIRROR": mirror},
        )
        d = json.loads(out.stdout)
        assert d["mirror_status"] == "online"
        assert d["active"] == "careful" and d["envelope"] == "L0-L4 gated · Ring 0-2"
        assert d["history"][0]["to"] == "careful"
    finally:
        os.unlink(mirror)


def test_core_offline_ms040_default():
    """Offline → the MS040 R09535 Private default (never crash)."""
    out = subprocess.run(
        ["python3", str(CORE), "show", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_SELFDEF_PROFILE_MIRROR": "/tmp/sovereign-os-no-profile-mirror.json"},
    )
    d = json.loads(out.stdout)
    assert d["mirror_status"] == "offline"
    assert d["active"] == "private"
    assert "no Ring 4" in d["envelope"] and d["history"] == []


def test_core_invalid_active_falls_back_private():
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump({"active": "bogus-profile"}, fh)
    try:
        out = subprocess.run(
            ["python3", str(CORE), "show", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_SELFDEF_PROFILE_MIRROR": path},
        )
        assert json.loads(out.stdout)["active"] == "private"
    finally:
        os.unlink(path)


def test_api_daemon_present():
    assert API_DAEMON.is_file()


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [ln for ln in body.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    found = False
    for ln in active:
        if "PROFILE_MIRROR_API_BIND=" in ln:
            assert "PROFILE_MIRROR_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "PROFILE_MIRROR_API_BIND=0.0.0.0" not in ln, ln
    assert found


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_profile_mirror():
    body = OSCTL.read_text(encoding="utf-8")
    assert "profile-mirror)" in body
    assert "scripts/mirror/selfdef-profile-mirror.py" in body


def test_master_dashboard_route_registered():
    # F-2026-072: the aggregator route table moved to the generated
    # config/dashboard-routes.yaml and uses the canonical catalog slug.
    routes = (REPO_ROOT / "config" / "dashboard-routes.yaml").read_text(encoding="utf-8")
    assert "d-02-profile-choices" in routes, "aggregator table missing d-02-profile-choices route"
    assert "8117" in routes, "d-02-profile-choices route must declare port 8117"


# ---- live endpoints --------------------------------------------------------

def test_show_endpoint_matches_dashboard_contract():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        status, d = _get(port, "/api/profile/show")
        assert status == 200
        for k in ("active", "since", "actor", "envelope", "history"):
            assert k in d, f"missing {k} (the D-02 webapp reads it)"
        h = d["history"][0]
        for k in ("ts", "from", "to", "actor", "rationale", "signature"):
            assert k in h
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_webapp_served_and_already_fetches():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-02" in html and "profile choices" in html
        assert "/api/profile/show" in html  # webapp already wired to our endpoint
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_readonly_mutation_rejected():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        for method in ("POST", "PUT", "DELETE"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/profile/show", method=method, data=b"{}")
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
        assert d["module"] == "d-02-profile-choices"
        assert "READ-ONLY" in d["mirror_doctrine"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)
