"""M060 D-18 (R10123) — trust-scores mirror API + webapp contract.

CROSS-REPO READ-ONLY MIRROR (the MS042 trust-score pair to D-17): selfdef
/v1/trust-scores source ← sovereign-os D-18 mirror. The dashboard HTML shipped
with inline MOCK + referenced /api/d-18/*; this locks the full §1g stack + the
frontend rewire:

  core    scripts/mirror/selfdef-trust-score-mirror.py
  cli     sovereign-osctl trust-mirror {snapshot,bands}
  api     scripts/operator/trust-mirror-api.py
  webapp  webapp/d-18-trust-scores/index.html (now fetches /api/d-18/*)
  service systemd/system/sovereign-trust-mirror-api.service

Authoritative per-tool trust scores live in selfdef (MS042). sovereign-os
renders READ-ONLY — score reset is selfdefctl + MS003 (IPS) only.
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
CORE = REPO_ROOT / "scripts" / "mirror" / "selfdef-trust-score-mirror.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "trust-mirror-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-trust-mirror-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-18-trust-scores" / "index.html"

_MIRROR = {
    "schema_version": "1.0.0", "captured_at": "2026-05-27T20:00Z",
    "tools": [
        {"tool": "rg", "declarer": "operator-fp", "current_score": 1000,
         "executions_total": 4827, "mismatches_total": 0,
         "history": [{"score_after": 1000, "reason": "baseline"}],
         "last_trace_id": "tl", "signature": "sg"},
        {"tool": "untrusted-bin", "current_score": 50, "executions_total": 3,
         "mismatches_total": 47, "history": [{"score_after": 1000}, {"score_after": 50}]},
    ],
}


def _write_mirror() -> str:
    fd, path = tempfile.mkstemp(prefix="trust-mirror-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_MIRROR, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, mirror: str):
    env = {
        "TRUST_MIRROR_API_BIND": "127.0.0.1",
        "TRUST_MIRROR_API_PORT": str(port),
        "SOVEREIGN_OS_SELFDEF_TRUST_MIRROR": mirror,
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
    raise RuntimeError("trust-mirror-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_projects_mirror_with_band_derivation():
    assert CORE.is_file(), f"core missing: {CORE}"
    mirror = _write_mirror()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "snapshot", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_SELFDEF_TRUST_MIRROR": mirror},
        )
        d = json.loads(out.stdout)
        assert d["mirror_status"] == "online"
        by = {t["tool"]: t for t in d["tools"]}
        # band derived from the 0-1000 score when not published
        assert by["rg"]["band"] == "trusted"          # 1000 ≥ 800
        assert by["untrusted-bin"]["band"] == "untrusted"  # 50 < 200
        assert by["rg"]["history"], "history must be projected"
    finally:
        os.unlink(mirror)


def test_core_offline_graceful():
    out = subprocess.run(
        ["python3", str(CORE), "snapshot", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_SELFDEF_TRUST_MIRROR": "/tmp/sovereign-os-no-trust-mirror.json"},
    )
    d = json.loads(out.stdout)
    assert d["mirror_status"] == "offline" and d["tools"] == []


def test_frontend_rewired_to_live_mirror():
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-18/snapshot" in html
    assert "publisher /api/d-18/snapshot when wired" not in html
    assert "mkTool(" not in html and "flaky-tool" not in html
    assert "READ-ONLY" in html or "read-only" in html


def test_api_daemon_present():
    assert API_DAEMON.is_file()


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [ln for ln in body.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    found = False
    for ln in active:
        if "TRUST_MIRROR_API_BIND=" in ln:
            assert "TRUST_MIRROR_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "TRUST_MIRROR_API_BIND=0.0.0.0" not in ln, ln
    assert found


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_trust_mirror():
    body = OSCTL.read_text(encoding="utf-8")
    assert "trust-mirror)" in body
    assert "scripts/mirror/selfdef-trust-score-mirror.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"trust-mirror"' in body and "8115" in body


# ---- live endpoints --------------------------------------------------------

def test_snapshot_endpoint_matches_dashboard_contract():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        status, d = _get(port, "/api/d-18/snapshot")
        assert status == 200
        assert set(d) >= {"mirror_status", "tools"}
        t = d["tools"][0]
        for k in ("tool", "declarer", "current_score", "band",
                  "executions_total", "mismatches_total", "history"):
            assert k in t
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_offline_endpoint_graceful():
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-no-trust-mirror.json")
    try:
        _, d = _get(port, "/api/d-18/snapshot")
        assert d["mirror_status"] == "offline" and d["tools"] == []
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
        assert "D-18" in html and "trust scores" in html
        assert "/api/d-18/snapshot" in html
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_readonly_mutation_rejected():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        for method in ("POST", "PUT", "DELETE"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/d-18/snapshot", method=method, data=b"{}")
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
        assert d["module"] == "d-18-trust-scores"
        assert "READ-ONLY" in d["mirror_doctrine"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)
