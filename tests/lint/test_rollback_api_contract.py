"""M060 D-08 (R10097-R10101) — rollback-points API + webapp surface contract.

Drives the D-08 cockpit dashboard from a shell to PRODUCTION: the dashboard
HTML shipped with inline MOCK data and referenced a future /api/d-08/* backend.
This locks the full §1g 8-surface stack now wired AND the frontend fetch-rewire:

  core    scripts/lifecycle/rollback-points.py  (ZFS snapshots + git history + dry-run)
  cli     sovereign-osctl rollback {snapshot,preview,commits}
  api     scripts/operator/rollback-api.py  (read-only HTTP)
  webapp  webapp/d-08-rollback-points/index.html   (now fetches /api/d-08/*)
  service systemd/system/sovereign-rollback-api.service

The core joins the ZFS snapshot inventory (M068) to the MS041 commit history
(git log) + a READ-ONLY dry-run rollback preview (R10099). Per operator §1g
(verbatim): "We do not minimize anything." Read-only — rollback-apply (R10100)
is an MS003-signed CLI verb (MS043 R10212).
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE = REPO_ROOT / "scripts" / "lifecycle" / "rollback-points.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "rollback-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-rollback-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-08-rollback-points" / "index.html"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "ROLLBACK_API_BIND": "127.0.0.1",
        "ROLLBACK_API_PORT": str(port),
        "SOVEREIGN_OS_GIT_REPO": str(REPO_ROOT),
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
    raise RuntimeError("rollback-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=4) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_present_and_snapshot_model():
    assert CORE.is_file(), f"core missing: {CORE}"
    out = subprocess.run(
        ["python3", str(CORE), "snapshot", "--json"],
        capture_output=True, text=True, timeout=20, check=True,
        env={**os.environ, "SOVEREIGN_OS_GIT_REPO": str(REPO_ROOT)},
    )
    d = json.loads(out.stdout)
    for k in ("snapshotTotal", "commits24h", "diskGib", "oldestAge",
              "lastRollback", "snapshots", "timeline"):
        assert k in d, f"missing key {k}"
    assert isinstance(d["snapshots"], list) and isinstance(d["timeline"], list)
    assert isinstance(d["commits24h"], int) and d["commits24h"] >= 0
    # ZFS absent in CI → empty snapshot inventory (graceful), never a crash
    assert d["snapshotTotal"] == len(d["snapshots"])


def test_core_preview_is_readonly_dryrun():
    out = subprocess.run(
        ["python3", str(CORE), "preview", "--to", "rpool/sovereign-os@pre-x", "--json"],
        capture_output=True, text=True, timeout=20, check=True,
        env={**os.environ, "SOVEREIGN_OS_GIT_REPO": str(REPO_ROOT)},
    )
    d = json.loads(out.stdout)
    assert d["target"] == "rpool/sovereign-os@pre-x"
    assert "lines" in d and isinstance(d["lines"], list) and d["lines"]
    # the plan emits the apply command but never executes it
    assert d["apply_cmd"].startswith("sovereign-osctl rollback apply")
    assert any("DRY-RUN" in ln["t"] for ln in d["lines"])
    assert any("MS003 operator signature" in ln["t"] for ln in d["lines"])


def test_frontend_rewired_to_live_api():
    """The D-08 webapp must fetch the live publisher API, not ship mock seed."""
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-08/snapshot" in html, "webapp must fetch /api/d-08/snapshot"
    assert "/api/d-08/preview?to=" in html, "webapp must fetch the preview endpoint"
    # the inline mock-seed rows must be gone
    assert "rpool/sovereign-os@pre-M080" not in html, "stale mock seed still present"
    assert "mock seed data" not in html and "mock dry-run output" not in html


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
        if "ROLLBACK_API_BIND=" in ln:
            assert "ROLLBACK_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "ROLLBACK_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set ROLLBACK_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_rollback():
    body = OSCTL.read_text(encoding="utf-8")
    assert "rollback)" in body, "osctl missing rollback dispatch case"
    assert "scripts/lifecycle/rollback-points.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"rollback"' in body, "master-dashboard missing rollback route"
    assert "8111" in body, "rollback route must declare port 8111"


# ---- live endpoints (the exact d-08 fetch contract) -----------------------

def test_snapshot_endpoint_matches_dashboard_contract():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        status, d = _get(port, "/api/d-08/snapshot")
        assert status == 200
        for k in ("snapshotTotal", "commits24h", "diskGib", "oldestAge",
                  "lastRollback", "snapshots", "timeline"):
            assert k in d
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_preview_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        status, d = _get(port, "/api/d-08/preview?to=rpool%2Fsovereign-os%40pre-x")
        assert status == 200
        assert d["target"] == "rpool/sovereign-os@pre-x"
        assert isinstance(d["lines"], list) and d["lines"]
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_preview_missing_target_400():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/d-08/preview", timeout=3)
            code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        assert code == 400, "preview without ?to= must be a 400"
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_webapp_served():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-08" in html and "rollback points" in html
        assert "/api/d-08/snapshot" in html
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_readonly_post_rejected():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/d-08/snapshot", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (read-only surface)"
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_version_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-08-rollback-points"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3)
