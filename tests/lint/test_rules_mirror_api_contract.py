"""M060 D-12 (R10113) — nftables rules mirror API + webapp contract.

Drives the D-12 networking cockpit dashboard to PRODUCTION as a CROSS-REPO
READ-ONLY MIRROR (SDD-063). Locks the full §1g stack + the frontend fetch-rewire:

  core    scripts/mirror/selfdef-rules-mirror.py   (reads selfdef MS007 mirror; canonical)
  cli     sovereign-osctl rules-mirror {snapshot,summaries}
  api     scripts/operator/rules-mirror-api.py      (read-only HTTP, :8133)
  webapp  webapp/d-12-networking/index.html         (now fetches /api/d-12/snapshot)
  service systemd/system/sovereign-rules-mirror-api.service

The authoritative nftables Ring-0-4 ruleset lives in SELFDEF (the IPS). sovereign-os
renders selfdef's published rules mirror READ-ONLY — nft rule ops are selfdefctl +
MS003 on the IPS side only (R10113). Per operator §1g: "We do not minimize anything."
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
CORE = REPO_ROOT / "scripts" / "mirror" / "selfdef-rules-mirror.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "rules-mirror-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-rules-mirror-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-12-networking" / "index.html"

# Mirrors the selfdef-rules-mirror::RulesMirrorSnapshot 1.0.0 (canonical core):
# named MS039 rings + nft dispositions + per-ring summaries + rich rule rows.
_MIRROR = {
    "schema_version": "1.0.0", "captured_at": "2026-05-27T20:00Z",
    "signature": "MS003:deadbeefcafe",
    "summaries": [
        {"ring": "sovereign_kernel", "rule_count": 4, "total_bytes": 47120,
         "total_packets": 412, "pending_l3": 0},
        {"ring": "cloud_external", "rule_count": 9, "total_bytes": 4452,
         "total_packets": 89, "pending_l3": 2},
    ],
    "rules": [
        {"handle": 100, "rule_id": "r-01", "ring": "sovereign_kernel",
         "table": "inet filter", "chain": "ring0-egress",
         "match_expr": "ip daddr 127.0.0.1 udp dport 8125", "disposition": "accept",
         "priority": 0, "packets": 412, "bytes": 47120,
         "installed_at": "2026-05-27T19:00Z", "installed_by": "selfdefctl",
         "signature": "MS003:aa"},
        {"handle": 106, "rule_id": "r-deny", "ring": "cloud_external",
         "table": "inet filter", "chain": "ring4-egress",
         "match_expr": "ip daddr 0.0.0.0/0", "disposition": "drop",
         "priority": 0, "packets": 89, "bytes": 4452},
        {"ring": "experimental"},  # no rule_id → dropped
    ],
}


def _write_mirror() -> str:
    fd, path = tempfile.mkstemp(prefix="rules-mirror-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_MIRROR, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, mirror: str):
    env = {
        "RULES_MIRROR_API_BIND": "127.0.0.1",
        "RULES_MIRROR_API_PORT": str(port),
        "SOVEREIGN_OS_SELFDEF_RULES_MIRROR": mirror,
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
    raise RuntimeError("rules-mirror-api failed to start within 6s")


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
            env={**os.environ, "SOVEREIGN_OS_SELFDEF_RULES_MIRROR": mirror},
        )
        d = json.loads(out.stdout)
        assert d["mirror_status"] == "online"
        assert [s["ring"] for s in d["summaries"]] == ["sovereign_kernel", "cloud_external"]
        # invalid rule (no rule_id) dropped; valid rules kept, disposition preserved
        assert [r["rule_id"] for r in d["rules"]] == ["r-01", "r-deny"]
        assert d["rules"][1]["disposition"] == "drop"
        assert d["signature"] == "MS003:deadbeefcafe"
    finally:
        os.unlink(mirror)


def test_core_offline_graceful():
    out = subprocess.run(
        ["python3", str(CORE), "snapshot", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_SELFDEF_RULES_MIRROR": "/tmp/sovereign-os-no-rules-mirror.json"},
    )
    d = json.loads(out.stdout)
    assert d["mirror_status"] == "offline"
    assert d["summaries"] == [] and d["rules"] == []


def test_frontend_rewired_to_live_mirror():
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-12/snapshot" in html, "webapp must fetch the mirror snapshot"
    # the stale mock banner must be gone (wired to the live producer now)
    assert "no /api/d-12/snapshot publisher wired yet" not in html
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
        if "RULES_MIRROR_API_BIND=" in ln:
            assert "RULES_MIRROR_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "RULES_MIRROR_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set RULES_MIRROR_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_rules_mirror():
    body = OSCTL.read_text(encoding="utf-8")
    assert "rules-mirror)" in body, "osctl missing rules-mirror dispatch case"
    assert "scripts/mirror/selfdef-rules-mirror.py" in body


def test_master_dashboard_route_registered():
    # F-2026-072: the aggregator route table moved to the generated
    # config/dashboard-routes.yaml and uses the canonical catalog slug.
    # F-2026-070: the d-12 rules-mirror was unified into sovereign-networking-api
    # (port 8139), which serves /api/d-12/snapshot alongside network-edge +
    # edge-firewall — so the d-12-networking route now declares the unified port.
    routes = (REPO_ROOT / "config" / "dashboard-routes.yaml").read_text(encoding="utf-8")
    d12 = [ln for ln in routes.splitlines() if "slug: d-12-networking," in ln]
    assert d12, "aggregator table missing d-12-networking route"
    assert "port: 8139" in d12[0], (
        "d-12-networking route must declare the unified networking-api port 8139 "
        f"(F-2026-070); got: {d12[0]}")


# ---- live endpoints (the exact d-12 fetch contract) -----------------------

def test_snapshot_endpoint_matches_dashboard_contract():
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        status, d = _get(port, "/api/d-12/snapshot")
        assert status == 200
        assert set(d) >= {"mirror_status", "summaries", "rules"}
        for s in d["summaries"]:
            for k in ("ring", "rule_count", "total_bytes", "total_packets", "pending_l3"):
                assert k in s
        r = d["rules"][0]
        for k in ("handle", "rule_id", "ring", "chain", "match_expr", "disposition",
                  "packets", "bytes"):
            assert k in r
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_offline_endpoint_graceful():
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-no-rules-mirror.json")
    try:
        _, d = _get(port, "/api/d-12/snapshot")
        assert d["mirror_status"] == "offline"
        assert d["summaries"] == [] and d["rules"] == []
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
        assert "D-12" in html
        assert "/api/d-12/snapshot" in html
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)


def test_readonly_mutation_rejected():
    """The mirror NEVER mutates IPS state — every write verb → 405 (R10113)."""
    mirror = _write_mirror()
    port = _free_port()
    proc = _spawn_api(port, mirror)
    try:
        for method in ("POST", "PUT", "DELETE"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/d-12/snapshot", method=method, data=b"{}")
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
        assert d["module"] == "d-12-networking"
        assert "READ-ONLY" in d["mirror_doctrine"]
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(mirror)
