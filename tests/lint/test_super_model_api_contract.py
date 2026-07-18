"""M060 D-19 (R10124-R10125) — super-model-manifest API + webapp contract.

sovereign-os-NATIVE (the super-model manifest is sovereign-os's own version +
module-version table). The dashboard HTML shipped with inline MOCK arrays +
referenced /api/d-19/*; this locks the full §1g stack + the frontend rewire:

  core    scripts/manifest/super-model-manifest.py  (live catalog + git + toml)
  cli     sovereign-osctl super-model {snapshot,version,milestones}
  api     scripts/operator/super-model-api.py
  webapp  webapp/d-19-super-model-manifest/index.html (now fetches /api/d-19/*)
  service systemd/system/sovereign-super-model-api.service

The module-version table is computed from the LIVE milestone catalog
(backlog/milestones/M###-*.md ids/titles/R-row counts) + git HEAD version +
config/super-model-manifest.toml editorial overlay. Read-only — computed, not
mutated. Per operator §1g: "We do not minimize anything."
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
CORE = REPO_ROOT / "scripts" / "manifest" / "super-model-manifest.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "super-model-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-super-model-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-19-super-model-manifest" / "index.html"
MANIFEST_TOML = REPO_ROOT / "config" / "super-model-manifest.toml"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "SUPER_MODEL_API_BIND": "127.0.0.1",
        "SUPER_MODEL_API_PORT": str(port),
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
    raise RuntimeError("super-model-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=4) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_manifest_config_present():
    assert MANIFEST_TOML.is_file(), "editorial manifest config missing"


def test_core_computes_live_manifest():
    assert CORE.is_file(), f"core missing: {CORE}"
    out = subprocess.run(
        ["python3", str(CORE), "snapshot", "--json"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    d = json.loads(out.stdout)
    assert set(d) >= {"version", "phases", "milestones", "cross_refs"}
    v = d["version"]
    # live counts from the catalog/git — must be real, non-trivial
    assert v["super_model_id"].startswith("sovereign-os@")
    assert v["milestone_count"] >= 60, "must enumerate the live M### catalog"
    assert v["rrow_count"] > 1000, "must sum live R-rows from the catalog"
    # M053 11 build-phases from the manifest
    assert len(d["phases"]) == 11
    assert any(p["status"] == "current" for p in d["phases"])


def test_core_milestone_rows_are_live_catalog():
    """Every emitted milestone id must correspond to a real catalog file, and
    titles/R-row counts come from the live files (not hardcoded)."""
    out = subprocess.run(
        ["python3", str(CORE), "milestones", "--json"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    rows = json.loads(out.stdout)
    catalog = {p.name.split("-")[0] for p in (REPO_ROOT / "backlog" / "milestones").glob("M[0-9]*.md")}
    for r in rows:
        assert r["ms"] in catalog, f"emitted {r['ms']} has no catalog file"
        assert isinstance(r["rrows"], int)
    # M028 is a known catalog milestone with a real title + R-rows
    m028 = [r for r in rows if r["ms"] == "M028"]
    assert m028 and "Memory OS" in m028[0]["title"] and m028[0]["rrows"] > 0


def test_api_daemon_present():
    assert API_DAEMON.is_file()


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [ln for ln in body.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    found = False
    for ln in active:
        if "SUPER_MODEL_API_BIND=" in ln:
            assert "SUPER_MODEL_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "SUPER_MODEL_API_BIND=0.0.0.0" not in ln, ln
    assert found


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_super_model():
    body = OSCTL.read_text(encoding="utf-8")
    assert "super-model)" in body
    assert "scripts/manifest/super-model-manifest.py" in body


def test_master_dashboard_route_registered():
    # F-2026-072: the aggregator route table moved to the generated
    # config/dashboard-routes.yaml and uses the canonical catalog slug.
    routes = (REPO_ROOT / "config" / "dashboard-routes.yaml").read_text(encoding="utf-8")
    assert "d-19-super-model-manifest" in routes, "aggregator table missing d-19-super-model-manifest route"
    assert "8119" in routes, "d-19-super-model-manifest route must declare port 8119"


def test_frontend_rewired_to_live_api():
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-19/snapshot" in html
    assert "publisher /api/d-19/snapshot when wired" not in html
    # the hardcoded mock milestone array must be gone
    assert 'title:"Cognitive Compiler"' not in html and "Cognitive Compiler\",          family" not in html


# ---- live endpoints --------------------------------------------------------

def test_snapshot_endpoint_matches_dashboard_contract():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        status, d = _get(port, "/api/d-19/snapshot")
        assert status == 200
        assert set(d) >= {"version", "phases", "milestones", "cross_refs"}
        for k in ("super_model_id", "milestone_count", "rrow_count", "mirror_count", "shipped_count"):
            assert k in d["version"]
        m = d["milestones"][0]
        for k in ("ms", "title", "family", "status", "rrows", "tag"):
            assert k in m
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_webapp_served():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-19" in html and "super-model manifest" in html
        assert "/api/d-19/snapshot" in html
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_readonly_post_rejected():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/d-19/snapshot", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (computed, not mutated)"
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_version_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-19-super-model-manifest"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3)
