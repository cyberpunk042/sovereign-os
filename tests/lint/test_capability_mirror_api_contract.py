"""M060 D-14 (R10116-R10117) — capability-tokens mirror API + webapp contract.

CROSS-REPO READ-ONLY MIRROR. The dashboard HTML shipped with inline MOCK +
referenced /api/d-14/*; this locks the full §1g stack + the frontend rewire
(incl. the empty-tokens guard for the 64-bit capability_word bit-decoder):

  core    scripts/mirror/selfdef-capability-mirror.py
  cli     sovereign-osctl capability-mirror {snapshot,summaries}
  api     scripts/operator/capability-mirror-api.py
  webapp  webapp/d-14-capability-tokens/index.html (now fetches /api/d-14/*)
  service systemd/system/sovereign-capability-mirror-api.service

Authoritative capability-token state lives in selfdef (MS035 64-bit
capability_word + MS039 Ring 0..4). sovereign-os renders READ-ONLY — token
issue/revoke are selfdefctl + MS003 (IPS).
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
CORE = REPO_ROOT / "scripts" / "mirror" / "selfdef-capability-mirror.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "capability-mirror-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-capability-mirror-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-14-capability-tokens" / "index.html"

_MIRROR = {
    "schema_version": "1.0.0", "captured_at": "2026-05-27T20:00Z",
    "summaries": [{"ring": "ring0", "active": 2}, {"ring": "ring3", "active": 5, "quarantined": 1}],
    "tokens": [
        {"token_id": "tok-r0", "capability_word": "0xff00ffff00aa55c0",
         "actor": "selfdef-daemon", "trust_ring": "ring0", "authority_level": "l6_persist",
         "allowed_tools": ["audit.write", "grant.issue"], "sandbox_tier": "A",
         "state": "active", "parent_token_id": ""},
        {"token_id": "tok-bad", "trust_ring": "bogus"},  # invalid ring → dropped
    ],
}


def _write_mirror() -> str:
    fd, path = tempfile.mkstemp(prefix="capability-mirror-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_MIRROR, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, mirror: str):
    env = {
        "CAPABILITY_MIRROR_API_BIND": "127.0.0.1",
        "CAPABILITY_MIRROR_API_PORT": str(port),
        "SOVEREIGN_OS_SELFDEF_CAPABILITY_MIRROR": mirror,
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
    raise RuntimeError("capability-mirror-api failed to start within 6s")


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
            env={**os.environ, "SOVEREIGN_OS_SELFDEF_CAPABILITY_MIRROR": mirror},
        )
        d = json.loads(out.stdout)
        assert d["mirror_status"] == "online"
        assert [s["ring"] for s in d["summaries"]] == ["ring0", "ring1", "ring2", "ring3", "ring4"]
        assert [t["token_id"] for t in d["tokens"]] == ["tok-r0"]  # bogus ring dropped
        assert d["tokens"][0]["capability_word"].startswith("0x")
    finally:
        os.unlink(mirror)


def test_core_offline_graceful():
    out = subprocess.run(
        ["python3", str(CORE), "snapshot", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_SELFDEF_CAPABILITY_MIRROR": "/tmp/sovereign-os-no-cap-mirror.json"},
    )
    d = json.loads(out.stdout)
    assert d["mirror_status"] == "offline"
    assert len(d["summaries"]) == 5 and d["tokens"] == []


def test_frontend_rewired_to_live_mirror():
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-14/snapshot" in html
    assert "publisher /api/d-14/snapshot when wired" not in html
    assert "tok-r0-daemon" not in html  # stale mock seed gone
    # the empty-tokens guard for the bit-decoder must be present
    assert "(seed.tokens || []).length" in html or "seed.tokens || []" in html
    assert "READ-ONLY" in html or "read-only" in html


def test_api_daemon_present():
    assert API_DAEMON.is_file()


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [ln for ln in body.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    found = False
    for ln in active:
        if "CAPABILITY_MIRROR_API_BIND=" in ln:
            assert "CAPABILITY_MIRROR_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "CAPABILITY_MIRROR_API_BIND=0.0.0.0" not in ln, ln
    assert found


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_capability_mirror():
    body = OSCTL.read_text(encoding="utf-8")
    assert "capability-mirror)" in body
    assert "scripts/mirror/selfdef-capability-mirror.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"capability-mirror"' in body and "8118" in body


# ---- live endpoints --------------------------------------------------------

def test_snapshot_endpoint_matches_dashboard_contract():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        status, d = _get(port, "/api/d-14/snapshot")
        assert status == 200
        assert set(d) >= {"mirror_status", "summaries", "tokens"}
        t = d["tokens"][0]
        for k in ("token_id", "capability_word", "actor", "trust_ring",
                  "authority_level", "allowed_tools", "sandbox_tier", "state", "parent_token_id"):
            assert k in t
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_offline_endpoint_graceful():
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-no-cap-mirror.json")
    try:
        _, d = _get(port, "/api/d-14/snapshot")
        assert d["mirror_status"] == "offline" and d["tokens"] == []
        assert len(d["summaries"]) == 5
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
        assert "D-14" in html and "capability tokens" in html
        assert "/api/d-14/snapshot" in html
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_readonly_mutation_rejected():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        for method in ("POST", "PUT", "DELETE"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/d-14/snapshot", method=method, data=b"{}")
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
        assert d["module"] == "d-14-capability-tokens"
        assert "READ-ONLY" in d["mirror_doctrine"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)
