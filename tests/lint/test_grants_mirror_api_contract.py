"""M060 D-13 (R10114-R10115) — filesystem-grants mirror API + webapp contract.

Drives the D-13 cockpit dashboard from a shell to PRODUCTION as a CROSS-REPO
READ-ONLY MIRROR: the dashboard HTML shipped with inline MOCK data + referenced
a future /api/d-13/* backend. This locks the full §1g stack + the frontend
fetch-rewire:

  core    scripts/mirror/selfdef-grants-mirror.py  (reads selfdef MS007 mirror)
  cli     sovereign-osctl grants-mirror {snapshot,summaries}
  api     scripts/operator/grants-mirror-api.py  (read-only HTTP)
  webapp  webapp/d-13-filesystem-grants/index.html  (now fetches /api/d-13/*)
  service systemd/system/sovereign-grants-mirror-api.service

The authoritative grant state lives in SELFDEF (the IPS). sovereign-os renders
selfdef's published grant mirror READ-ONLY — grant ops are selfdefctl + MS003
on the IPS side only (R10115). Per operator §1g: "We do not minimize anything."
The project boundary is enforced: no IPS logic in sovereign-os; mutation → 405.
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
CORE = REPO_ROOT / "scripts" / "mirror" / "selfdef-grants-mirror.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "grants-mirror-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-grants-mirror-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-13-filesystem-grants" / "index.html"

# Mirrors the REAL selfdef-grants-mirror::GrantsMirrorSnapshot 1.0.0 (verified
# against crates/selfdef-grants-mirror/src/lib.rs): {schema_version, captured_at,
# summaries, grants, signature} — NO top-level `pending` (pending grants are
# grants[state==pending]) + an MS003 signature.
_MIRROR = {
    "schema_version": "1.0.0", "captured_at": "2026-05-27T20:00Z",
    "signature": "MS003:deadbeefcafe",
    "summaries": [
        {"kind": "filesystem", "active": 8, "pending": 1, "expired_24h": 4,
         "revoked_24h": 1, "quarantined": 0},
        {"kind": "capability", "active": 12, "pending": 2, "quarantined": 1},
    ],
    "grants": [
        {"grant_id": "gr-01", "kind": "filesystem", "scope": "/home/user/**",
         "reason": "authoring", "issued_at": "2026-05-27T19:00Z",
         "expires_at": "2026-05-27T20:00Z", "ttl_seconds": 3600, "profile": "private",
         "actor": "operator-fp", "state": "active", "trace_id": "t1"},
        # a pending-state grant — the D-13 "pending requests" view derives from this
        {"grant_id": "gr-px1", "kind": "network", "scope": "hf.co:443",
         "reason": "hf fetch", "issued_at": "2026-05-27T19:30Z",
         "expires_at": "2026-05-27T20:30Z", "ttl_seconds": 3600, "profile": "fast",
         "actor": "agent-fp", "state": "pending", "trace_id": "t2"},
        {"grant_id": "gr-bad", "kind": "bogus"},  # invalid kind → dropped
    ],
}


def _write_mirror() -> str:
    fd, path = tempfile.mkstemp(prefix="grants-mirror-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_MIRROR, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, mirror: str):
    env = {
        "GRANTS_MIRROR_API_BIND": "127.0.0.1",
        "GRANTS_MIRROR_API_PORT": str(port),
        "SOVEREIGN_OS_SELFDEF_GRANTS_MIRROR": mirror,
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
    raise RuntimeError("grants-mirror-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_present_and_projects_mirror():
    assert CORE.is_file(), f"core missing: {CORE}"
    mirror = _write_mirror()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "snapshot", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_SELFDEF_GRANTS_MIRROR": mirror},
        )
        d = json.loads(out.stdout)
        assert d["mirror_status"] == "online"
        # 5 grant kinds, zero-filled + canonical order
        assert [s["kind"] for s in d["summaries"]] == [
            "filesystem", "network", "capability", "communication", "sandbox"]
        # invalid-kind grant dropped; valid grants kept (gr-01 active, gr-px1 pending)
        assert [g["grant_id"] for g in d["grants"]] == ["gr-01", "gr-px1"]
        # pending is DERIVED from grants[state==pending] (no top-level pending in
        # the real selfdef snapshot); requester maps from the grant's actor
        assert [p["grant_id"] for p in d["pending"]] == ["gr-px1"]
        assert d["pending"][0]["requester"] == "agent-fp"
        # MS003 signature carried through from the real snapshot
        assert d["signature"] == "MS003:deadbeefcafe"
    finally:
        os.unlink(mirror)


def test_core_offline_graceful():
    out = subprocess.run(
        ["python3", str(CORE), "snapshot", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_SELFDEF_GRANTS_MIRROR": "/tmp/sovereign-os-no-grants-mirror.json"},
    )
    d = json.loads(out.stdout)
    assert d["mirror_status"] == "offline"
    assert len(d["summaries"]) == 5 and all(s["active"] == 0 for s in d["summaries"])
    assert d["grants"] == [] and d["pending"] == []


def test_frontend_rewired_to_live_mirror():
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-13/snapshot" in html, "webapp must fetch the mirror snapshot"
    assert "publisher endpoint /api/d-13/snapshot when wired" not in html, "stale mock comment present"
    assert "trace-07" not in html and "gr-px2" not in html, "stale mock seed rows present"
    # the read-only mirror doctrine must be visible
    assert "READ-ONLY" in html or "read-only" in html


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
        if "GRANTS_MIRROR_API_BIND=" in ln:
            assert "GRANTS_MIRROR_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "GRANTS_MIRROR_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set GRANTS_MIRROR_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_grants_mirror():
    body = OSCTL.read_text(encoding="utf-8")
    assert "grants-mirror)" in body, "osctl missing grants-mirror dispatch case"
    assert "scripts/mirror/selfdef-grants-mirror.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"grants-mirror"' in body, "master-dashboard missing grants-mirror route"
    assert "8113" in body, "grants-mirror route must declare port 8113"


# ---- live endpoints (the exact d-13 fetch contract) -----------------------

def test_snapshot_endpoint_matches_dashboard_contract():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        status, d = _get(port, "/api/d-13/snapshot")
        assert status == 200
        assert set(d) >= {"mirror_status", "summaries", "grants", "pending"}
        for s in d["summaries"]:
            for k in ("kind", "active", "pending", "expired_24h", "revoked_24h", "quarantined"):
                assert k in s
        g = d["grants"][0]
        for k in ("grant_id", "kind", "scope", "issued_at", "expires_at", "ttl_seconds", "state"):
            assert k in g
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_offline_endpoint_graceful():
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-no-grants-mirror.json")
    try:
        _, d = _get(port, "/api/d-13/snapshot")
        assert d["mirror_status"] == "offline"
        assert len(d["summaries"]) == 5 and d["grants"] == []
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
        assert "D-13" in html and "filesystem grants" in html
        assert "/api/d-13/snapshot" in html
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_readonly_mutation_rejected():
    """The mirror NEVER mutates IPS state — every write verb → 405 (R10115)."""
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        for method in ("POST", "PUT", "DELETE"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/d-13/snapshot", method=method, data=b"{}")
            try:
                urllib.request.urlopen(req, timeout=3)
                raised = False
            except urllib.error.HTTPError as e:
                raised = (e.code == 405)
            assert raised, f"{method} must be rejected 405 (read-only mirror)"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_version_declares_mirror_doctrine():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-13-filesystem-grants"
        assert "READ-ONLY" in d["mirror_doctrine"]
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)
